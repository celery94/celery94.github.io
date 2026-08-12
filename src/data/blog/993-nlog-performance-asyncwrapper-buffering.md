---
pubDatetime: 2026-08-12T11:22:00+08:00
title: "NLog 性能调优：AsyncWrapper 与缓冲日志"
description: "高峰流量下日志拖慢请求？用 AsyncWrapper 把 I/O 移出调用线程、BufferingWrapper 批量写库，配合参数调优、文件 target 优化与 BenchmarkDotNet 基准，得到生产级高吞吐 NLog 配置。"
tags: ["NLog", ".NET", "CSharp", "Logging", "Performance"]
slug: "nlog-performance-asyncwrapper-buffering"
ogImage: "../../assets/993/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/11/nlog-performance-asyncwrapper-buffering-and-highthroughput-logging-in-net"
---

当应用每秒处理几百个请求之后，日志很快会成为性能瓶颈。默认情况下 NLog 在**调用线程上同步写日志**：每次 `_logger.LogInformation(...)` 都要等磁盘或网络 I/O 完成才返回，请求延迟被一点点累积放大。

这篇教程解决的就是这个问题。你会学到：用 `AsyncWrapper` 把写日志变成入队操作、用 `BufferingWrapper` 把逐条写入变成批量写入、如何调文件 target 的参数、如何用 BenchmarkDotNet 量化每一次改动，最后拿到一份可以直接用的生产级高吞吐配置模板。

前提是你已经在 ASP.NET Core 里接入过 NLog、了解 target 和规则的基本概念——如果还没有，先看本站的 [ASP.NET Core 集成 NLog 完整入门](https://celery94.github.io/blog/nlog-aspnet-core-getting-started)（对应作者系列文章的前一篇）。本文代码基于 .NET 8+ 与 NLog 5.x/6.x，涉及版本差异的地方会明确标注。

## 为什么同步日志伤性能

同步模式下，每次日志调用都会阻塞到写入完成：文件 target 等磁盘 I/O，数据库或远程 target 等网络 I/O。

先看数量级：一次文件同步写大约耗时 **0.1–1 ms**（取决于磁盘速度和操作系统缓冲）。假设应用每秒处理 1,000 个请求、每个请求记 5 条日志，那就是每秒 **5,000 次同步写**，全部竞争同一个文件句柄——即使有 OS 级写缓存，高负载下争用也会拖垮吞吐。

远程 target 更严重：

- **数据库 target**：每条日志一条 INSERT。每秒 1,000 条事件就是 1,000 次 INSERT，轻易打满共享 SQL Server 实例。
- **Seq / Elasticsearch target**：每条日志一次 HTTP POST，单次延迟 **5–50 ms**，同步写入在高负载下根本不现实。

NLog 的解决方案是 target wrapper（包装器）：把调用线程和 I/O 操作解耦。接下来是其中最核心的两个。

## AsyncWrapper：首要性能工具

`AsyncWrapper` 可以包住任何 NLog target，把全部 I/O 移到一个专用后台线程。调用线程只做一件事：把日志事件放进内存队列然后立即返回；后台线程从队列取事件、执行真正的写入。

```
调用线程 ──入队──▶ [内存队列] ──后台线程──▶ File / Database / Http target
```

### XML 配置

```xml
<targets>
  <target xsi:type="AsyncWrapper"
          name="asyncFile"
          queueLimit="10000"
          overflowAction="Discard"
          batchSize="200"
          timeToSleepBetweenBatches="0">
    <target xsi:type="File"
            name="innerFile"
            fileName="${basedir}/logs/${shortdate}.log"
            layout="${longdate}|${level:uppercase=true}|${logger:shortName=true}|${message}${exception:format=tostring}"
            keepFileOpen="true"
            concurrentWrites="false" />
    <!-- concurrentWrites removed in NLog 6; omit on NLog 6+ -->
  </target>
</targets>
```

注意 `File` 是**内层 target**，`AsyncWrapper` 站在它前面管理后台队列。内层 target 的所有配置选项照常生效——`AsyncWrapper` 只改变写入发生的时机，不改变写入方式。

### JSON 配置（appsettings.json）

同样的配置用 `appsettings.json` 表达，运行时行为完全一致。如果你的 DevOps 流程用环境变量注入连接字符串或日志级别，JSON 格式更合适——ASP.NET Core 的配置系统会自动合并 `appsettings.Production.json` 和环境变量，不需要改代码：

```json
{
  "NLog": {
    "targets": {
      "asyncFile": {
        "type": "AsyncWrapper",
        "queueLimit": 10000,
        "overflowAction": "Discard",
        "batchSize": 200,
        "timeToSleepBetweenBatches": 0,
        "target": {
          "type": "File",
          "name": "innerFile",
          "fileName": "${basedir}/logs/${shortdate}.log",
          "keepFileOpen": true
          // "concurrentWrites": false  -- removed in NLog 6; omit on NLog 6+
        }
      }
    }
  }
}
```

### 关键参数

`AsyncWrapper` 的默认值偏保守，是为了单服务器应用安全，而不是高吞吐最优。生产环境应针对自己的流量画像和内存约束逐项调整：

| 参数                        | 默认值  | 高负载推荐       | 说明                                                             |
| --------------------------- | ------- | ---------------- | ---------------------------------------------------------------- |
| `queueLimit`                | 10000   | 50000–100000     | 内存队列中最多容纳的事件数，达到上限触发溢出策略                 |
| `overflowAction`            | Discard | Discard 或 Block | Discard 满队列丢事件；Block 施加背压                             |
| `batchSize`                 | 200     | 500–1000         | 后台线程每轮写入的事件数                                         |
| `timeToSleepBetweenBatches` | 1（ms） | 0                | 设为 0 时仅在出现新日志时触发写入，吞吐最大；调大则降低 CPU 占用 |

一个勘误：原文表格把 `timeToSleepBetweenBatches` 的默认值写作 50ms，那是 NLog 4.6 之前的值；NLog 4.6 起官方默认已改为 1ms（wiki 有明确说明），代码默认值与官方文档一致。推荐值 0 不受影响。

### overflowAction 三种取舍

- **Discard**：队列满时丢弃日志事件，调用方永不阻塞。极端流量尖峰下日志会静默丢失。适合「可用性优先于日志完整性」的高优先级服务。
- **Block**：队列满时调用方阻塞，直到队列有空位。不丢事件，但请求处理线程会被卡住。适合日志完整性是合规要求的场景。
- **Grow**：队列无限扩容。生产环境禁用——流量尖峰时无界内存增长会直接 OOM。

### async="true" 简写

在 `appsettings.json` 的 `targets` 节顶部加 `"async": true`，会自动把所有 target 包进**默认参数**的 `AsyncWrapper`（queueLimit=10000、overflowAction=Discard）：

```json
{
  "NLog": {
    "targets": {
      "async": true,
      "file": {
        "type": "File",
        "fileName": "${basedir}/logs/${shortdate}.log"
      }
    }
  }
}
```

这是不需要精细控制时的零成本选项；需要逐 target 调参就用显式 `AsyncWrapper`。

## BufferingWrapper：数据库和远程 target 的批量写入

`BufferingWrapper` 在内存里累积日志事件，当**缓冲区满**或**刷新间隔到期**时批量刷出。和 `AsyncWrapper` 不同，它默认是同步的：后台线程发出一批数据后，要等这次刷写完成才继续处理下一批。

适用场景是能从批量 I/O 获益的 target：数据库（一批一次 INSERT，而不是一条一次）、HTTP 类 target（一批一次请求，而不是一条一次）。

```xml
<targets>
  <target xsi:type="BufferingWrapper"
          name="bufferedDb"
          bufferSize="100"
          flushTimeout="5000"
          slidingTimeout="false">
    <target xsi:type="Database"
            name="innerDb"
            dbProvider="MySql.Data.MySqlClient"
            connectionString="${environment:DB_CONNECTION_STRING}"
            commandText="INSERT INTO Logs (Timestamp, Level, Logger, Message, Exception)
                         VALUES (@time, @level, @logger, @msg, @exc)">
      <parameter name="@time" layout="${date:universalTime=true:format=o}" />
      <parameter name="@level" layout="${level:uppercase=true}" />
      <parameter name="@logger" layout="${logger:shortName=true}" />
      <parameter name="@msg" layout="${message}" />
      <parameter name="@exc" layout="${exception:format=tostring}" />
    </target>
  </target>
</targets>
```

`bufferSize="100"` 表示攒够 100 条刷一次；`flushTimeout="5000"` 保证即使缓冲区没满，5 秒后也会把剩余事件刷出去——低流量时段日志不会一直积压。

### 组合：AsyncWrapper + BufferingWrapper

数据库 target 要同时拿到「调用方不阻塞」和「批量写入」，就把 `BufferingWrapper` 放进 `AsyncWrapper` 里：

```xml
<targets>
  <target xsi:type="AsyncWrapper" name="asyncBufferedDb"
          queueLimit="50000" overflowAction="Discard">
    <target xsi:type="BufferingWrapper"
            bufferSize="200" flushTimeout="10000">
      <target xsi:type="Database" name="db" ... />
    </target>
  </target>
</targets>
```

这条链路的职责划分：

1. `AsyncWrapper` 立即返回给调用方——不阻塞；
2. `BufferingWrapper` 在后台线程上累积事件；
3. `Database` target 每轮收到 200 条事件，一次 INSERT 周期写入。

相比逐条同步写，数据库往返次数大幅下降。NLog 的 `Database` target 通过这组 wrapper 原生支持批量写入，写密集的生产服务可以放心用。

## 文件 target 调优

即使 `AsyncWrapper` 把写入移出了调用线程，文件 target 自己的配置仍决定后台线程的排空速度。两个经常被留在默认值的参数影响最大。

### keepFileOpen

NLog 5.x 中 `keepFileOpen` 默认是 `false`——每次写入都打开、关闭一次文件句柄。**NLog 6 把默认值改成了 `true`**。无论哪个版本，显式设置 `keepFileOpen="true"` 都能消除反复 open/close 的系统调用开销，仅这一项就能让文件 target 吞吐翻倍。

NLog 5.x 上开 `keepFileOpen="true"` 时，除非多个进程写同一文件，还要加 `concurrentWrites="false"`——并发写支持有锁开销，单进程写入不需要。**NLog 6 已从 `FileTarget` 整体移除 `ConcurrentWrites`**，配置里不要写它。

```xml
<!-- NLog 5.x: keepFileOpen + concurrentWrites="false" for single-process writers -->
<!-- NLog 6:   keepFileOpen only -- ConcurrentWrites was removed -->
<target xsi:type="File"
        fileName="${basedir}/logs/app.log"
        keepFileOpen="true"
        concurrentWrites="false" />
```

### 归档与滚动

按日期或大小滚动日志可以防止文件无限增长，但滚动检查有成本——NLog **每次写入都会检查滚动条件**。高吞吐应用建议用 `archiveAboveSize` 配一个较大阈值（如 `104857600` 即 100 MB），而不是每小时滚动，把滚动发生频率降到最低：

```xml
<target xsi:type="File"
        fileName="${basedir}/logs/app.log"
        archiveFileName="${basedir}/logs/archive/app.{#}.log"
        archiveAboveSize="104857600"
        archiveNumbering="Rolling"
        maxArchiveFiles="10"
        keepFileOpen="true"
        concurrentWrites="false" />
<!-- NLog 5.x only; omit on NLog 6+ -->
```

## 用 BenchmarkDotNet 量化配置

优化前先测量。凭直觉判断哪种配置最快往往不准——比如队列满且 `overflowAction="Block"` 的 `AsyncWrapper`，在短小突发流量下比同步日志还慢。BenchmarkDotNet 是 .NET 微基准的标准工具，作者有专门的[入门指南](https://www.devleader.ca/2024/03/05/how-to-use-benchmarkdotnet-6-simple-performance-boosting-tips-to-get-started)。

下面这个基准对比同步文件 target 和 `AsyncWrapper` 文件 target：

```csharp
using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Running;
using Microsoft.Extensions.Logging;
using NLog;
using NLog.Extensions.Logging;

public class NLogBenchmark
{
    private Microsoft.Extensions.Logging.ILogger _syncLogger = null!;
    private Microsoft.Extensions.Logging.ILogger _asyncLogger = null!;

    [GlobalSetup]
    public void Setup()
    {
        // Synchronous file target
        var syncConfig = new NLog.Config.LoggingConfiguration();
        var syncTarget = new NLog.Targets.FileTarget("syncFile")
        {
            FileName = "${basedir}/logs/sync-bench.log",
            KeepFileOpen = true,
            ConcurrentWrites = false
        };
        syncConfig.AddRuleForAllLevels(syncTarget);
        var syncFactory = LoggerFactory.Create(b => b.AddNLog(syncConfig));
        _syncLogger = syncFactory.CreateLogger<NLogBenchmark>();

        // Async file target
        var asyncConfig = new NLog.Config.LoggingConfiguration();
        var asyncTarget = new NLog.Targets.Wrappers.AsyncTargetWrapper(
            new NLog.Targets.FileTarget("asyncFile")
            {
                FileName = "${basedir}/logs/async-bench.log",
                KeepFileOpen = true,
                ConcurrentWrites = false
            })
        {
            QueueLimit = 50000,
            OverflowAction = NLog.Targets.Wrappers.AsyncTargetWrapperOverflowAction.Discard
        };
        asyncConfig.AddRuleForAllLevels(asyncTarget);
        var asyncFactory = LoggerFactory.Create(b => b.AddNLog(asyncConfig));
        _asyncLogger = asyncFactory.CreateLogger<NLogBenchmark>();
    }

    [Benchmark(Baseline = true)]
    public void SynchronousFileLogging()
    {
        _syncLogger.LogInformation("Order {OrderId} processed in {ElapsedMs}ms", 12345, 42);
    }

    [Benchmark]
    public void AsyncWrapperLogging()
    {
        _asyncLogger.LogInformation("Order {OrderId} processed in {ElapsedMs}ms", 12345, 42);
    }
}

class Program
{
    static void Main(string[] args) => BenchmarkRunner.Run<NLogBenchmark>();
}
```

运行结果有个常见陷阱：微基准里 `AsyncWrapper` 每次调用看起来快得多，因为调用方只入队，真正的 I/O 发生在后台线程、不计入单次调用耗时。端到端吞吐取决于 I/O 速度、队列深度和后台线程调度——**一定要用贴近生产的并发负载验证**，单线程基准会低估文件句柄或队列上的争用（可用多个并发 `Task` 模拟生产者/消费者）。

## 自定义 target：不要用 async void

如果你写自定义 target 做异步 I/O（比如向 webhook 发请求），很容易把 `Write` 写成 async——**别这么干**：

```csharp
// ❌ Dangerous -- async void, exceptions are unobserved
protected override async void Write(LogEventInfo logEvent)
{
    await _httpClient.PostAsync(_webhookUrl, BuildContent(logEvent));
}
```

NLog 的 `Write` 方法设计上就是同步的。`async void` 是 fire-and-forget，无法跟踪完成状态、无法捕获异常——一次失败的 HTTP 调用会静默终结方法。

正确做法是用 `Task.Run` 把工作丢到线程池，或者覆盖 `WriteAsyncTask`，这才是 NLog 正确的异步扩展点：

```csharp
// ✅ Correct async target extension point
protected override async Task WriteAsyncTask(LogEventInfo logEvent, CancellationToken cancellationToken)
{
    await _httpClient.PostAsync(_webhookUrl, BuildContent(logEvent), cancellationToken);
}
```

覆盖 `WriteAsyncTask` 后，异步调度由 NLog 管理；再包一层 `AsyncWrapper`，应用关闭时 NLog 会正确协调刷盘。

## AOT 与源码生成

NLog 6 支持 Native AOT，但有一些限制。`AsyncWrapper` 和 `BufferingWrapper` 在 NLog 6 中都是 AOT 兼容的——不过 AOT 兼容只覆盖 wrapper 本身，不代表任意基于反射的 target 扫描和扩展加载在裁剪（trimming）开启时也能工作。如果通过反射扫描注册 target 或扩展（比如用 Scrutor 这类库），发布时建议改为显式注册或源码生成方式。作者在[《Automatic Dependency Injection in C# with Needlr》](https://www.devleader.ca/2026/02/03/automatic-dependency-injection-in-c-the-complete-guide-to-needlr)里讲的源码生成注册原则同样适用于注册自定义 NLog target 类型。

## 生产配置模板

下面的完整模板组合了本文所有技巧：每个 target 独立异步包装、结构化 JSON target 加缓冲、文件参数调优、以及压制框架噪音的生产规则。可直接作为 ASP.NET Core 应用的 `nlog.config`：

```xml
<?xml version="1.0" encoding="utf-8" ?>
<nlog xmlns="http://www.nlog-project.org/schemas/NLog.xsd"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      autoReload="true">

  <targets>
    <!-- Async console target (dev-friendly, low overhead) -->
    <target xsi:type="AsyncWrapper"
            name="asyncConsole"
            queueLimit="10000"
            overflowAction="Discard">
      <target xsi:type="ColoredConsole"
              name="console"
              layout="${time}|${level:uppercase=true:padding=-5}|${logger:shortName=true}|${message}${exception:format=message}" />
    </target>

    <!-- Async rolling file target (high throughput) -->
    <target xsi:type="AsyncWrapper"
            name="asyncFile"
            queueLimit="50000"
            overflowAction="Discard"
            batchSize="500"
            timeToSleepBetweenBatches="0">
      <target xsi:type="File"
              name="file"
              fileName="${basedir}/logs/${shortdate}.log"
              archiveFileName="${basedir}/logs/archive/app.{#}.log"
              archiveAboveSize="104857600"
              archiveNumbering="Rolling"
              maxArchiveFiles="10"
              keepFileOpen="true"
              concurrentWrites="false"
              layout="${longdate}|${level:uppercase=true}|${mdlc:CorrelationId}|${logger:shortName=true}|${message}${exception:format=tostring}" />
    </target>

    <!-- Async buffered structured JSON target (for log aggregation) -->
    <target xsi:type="AsyncWrapper"
            name="asyncJson"
            queueLimit="100000"
            overflowAction="Discard">
      <target xsi:type="BufferingWrapper"
              name="bufferedJson"
              bufferSize="500"
              flushTimeout="5000">
        <target xsi:type="File"
                name="jsonFile"
                fileName="${basedir}/logs/structured-${shortdate}.json"
                keepFileOpen="true"
                concurrentWrites="false">
          <layout xsi:type="JsonLayout" includeAllProperties="true" excludeEmptyProperties="true">
            <attribute name="timestamp" layout="${date:universalTime=true:format=o}" />
            <attribute name="level" layout="${level:uppercase=true}" />
            <attribute name="logger" layout="${logger:shortName=true}" />
            <attribute name="correlationId" layout="${mdlc:CorrelationId}" />
            <attribute name="message" layout="${message}" />
            <attribute name="exception" layout="${exception:format=tostring}" />
          </layout>
        </target>
      </target>
    </target>
  </targets>

  <rules>
    <!-- Suppress EF Core query logging -->
    <logger name="Microsoft.EntityFrameworkCore.Database.Command" maxlevel="Info" final="true" />
    <!-- Suppress all Microsoft.*/System.* Debug/Info -->
    <logger name="Microsoft.*" maxlevel="Info" final="true" />
    <logger name="System.*" maxlevel="Info" final="true" />
    <!-- Framework warnings → file only -->
    <logger name="Microsoft.*" minlevel="Warn" writeTo="asyncFile" final="true" />
    <!-- Application → all targets -->
    <logger name="*" minlevel="Debug" writeTo="asyncConsole,asyncFile,asyncJson" />
  </rules>
</nlog>
```

注意：模板中的 `concurrentWrites` 是 NLog 5.x 专属，NLog 6+ 请删除该属性。这个配置提供：

- 三个 target 全部非阻塞异步写入；
- JSON target 500 条一批，降低刷写频率；
- 每个 target 独立的队列上限（console 处理快，队列就小）；
- 生产规则压掉框架噪音，同时保留全部应用日志。

## 常见问题

**`async="true"` 和显式 `AsyncWrapper` 有什么区别？**
`async="true"` 自动把所有 target 包进默认参数的 `AsyncWrapper`（queueLimit=10000、overflowAction=Discard）。显式 `AsyncWrapper` 可以逐 target 调 `queueLimit`、`overflowAction`、`batchSize`、`timeToSleepBetweenBatches`。快速上手用前者，需要细粒度吞吐控制用后者。

**`queueLimit` 该设多少？**
合理起点是 10,000–50,000 条。取决于你的突发流量画像和可用内存：按每条事件约 200 字节估算，50,000 条队列约占用 10 MB。用 NLog 内部日志（`internalLogLevel="Warn"`）观察负载下的队列利用率，如果出现事件被丢弃，就调大 `queueLimit` 或在源头降量。

**进程退出时 `AsyncWrapper` 会丢日志吗？**
不会。`AsyncWrapper` 通过 `NLog.LogManager.Shutdown()` 在关闭时刷空队列；使用 `NLog.Web.AspNetCore` 时宿主关闭会自动调用。手动接入 NLog 的话，在 `IHostApplicationLifetime.ApplicationStopped` 里调用 `LogManager.Shutdown()`，确保排队事件在进程退出前写完。

**什么时候用 `BufferingWrapper` 而不是 `AsyncWrapper`？**
target 能从批量 I/O 获益时用 `BufferingWrapper`——最常见的是数据库和 HTTP target：一次 100 行的 INSERT 远比 100 次单行 INSERT 快。`AsyncWrapper` 解决的是调用方阻塞，`BufferingWrapper` 解决的是 I/O 往返次数。两者组合使用效果最好：调用方不阻塞 + 批量写入。

**Linux 上 `keepFileOpen="true"` 会破坏日志轮转吗？**
不会。Linux 上打开的文件句柄不阻止文件被删除（inode 会保留到所有句柄释放）。`logrotate` 用 `copytruncate` 选项配合常开文件的应用；NLog 也支持 `autoFlush="true"` 和 `ArchiveOldFileOnStartup`。容器部署则建议直接写 stdout，让容器运行时处理日志收集，彻底绕开文件轮转。

**如何测量真实吞吐？**
用 BenchmarkDotNet 配真实的负载消息和真实 target（不要用 Null target），并在贴近生产请求模式的并发负载下测量。多个并发 `Task` 同时调用 logger，才能模拟 `AsyncWrapper` 队列上的真实生产者/消费者争用。

## 总结

NLog 性能优化的核心就三条：**`AsyncWrapper` 把 I/O 移出调用线程，`BufferingWrapper` 减少 I/O 往返，文件 target 保持文件打开**。多数应用把这三点配好，单次调用日志延迟就能降到微秒级。

实践建议：先在基准里量化当前配置，再逐项调整 `queueLimit`、`overflowAction`、`batchSize` 并复测；用 NLog 内部日志确认没有事件被丢弃；上线前用并发压测验证端到端吞吐。优化完吞吐之后，下一个问题往往是框架选型——NLog 的规则路由在复杂多 target 场景更强大，Serilog 的 sink 生态更广、代码优先配置更自然，按团队习惯取舍即可。

---

如果你也在搭建 .NET 应用的可观测性体系，欢迎关注 Aide Hub。我们会继续分享 ASP.NET Core、日志、监控和软件工程实践的一手教程。

## 参考

- [NLog Performance: AsyncWrapper, Buffering, and High-Throughput Logging in .NET（原文，Nick Cosentino）](https://www.devleader.ca/2026/08/11/nlog-performance-asyncwrapper-buffering-and-highthroughput-logging-in-net)
- [AsyncWrapper Target | NLog Wiki（官方参数默认值）](https://github.com/NLog/NLog/wiki/AsyncWrapper-target)
- [BufferingWrapper Target | NLog Wiki](https://github.com/NLog/NLog/wiki/BufferingWrapper-target)
- [NLog 6.0 Major Changes（官方，AOT 支持与 FileTarget 变更）](https://nlog-project.org/2025/04/29/nlog-6-0-major-changes.html)
- [How to Use BenchmarkDotNet: 6 Simple Performance Boosting Tips（作者）](https://www.devleader.ca/2024/03/05/how-to-use-benchmarkdotnet-6-simple-performance-boosting-tips-to-get-started)
- [Async Void Methods in C#: The Dangers（作者）](https://www.devleader.ca/2024/03/07/async-void-methods-in-c-the-dangers-that-you-need-to-know)
- [Automatic Dependency Injection in C# with Needlr（作者）](https://www.devleader.ca/2026/02/03/automatic-dependency-injection-in-c-the-complete-guide-to-needlr)
