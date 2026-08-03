---
pubDatetime: 2026-08-03T10:00:00+08:00
title: "NLog 完整指南：.NET 灵活日志框架上手"
description: "用 .NET 8+ 示例讲透 NLog 三大概念：Targets 定去向、Renderers 定格式、Rules 定路由，覆盖双配置与结构化日志，适合 ASP.NET Core 和 Worker Service 开发者。"
tags: ["NLog", ".NET", "Logging", "ASP.NET Core"]
slug: "nlog-dotnet-complete-guide-flexible-logging"
ogImage: "../../assets/988/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/01/nlog-in-net-complete-guide-to-flexible-logging"
---

在 .NET 日志框架的讨论里，Serilog 往往占据大部分注意力，但 NLog 是一个同样久经考验的选择：它从 2006 年就开始运行在生产系统里，而且它的配置模型非常独特——**Targets（日志去哪里）、Layout Renderers（日志长什么样）、Rules（哪些日志走哪条路）** 三个独立关注点互相组合，能表达出相当灵活的路由架构。

这篇文章面向想给 ASP.NET Core 或 Worker Service 接入 NLog 的 .NET 开发者。读完你会掌握：如何安装和注册 NLog、XML 与 appsettings.json 两种配置方式、三大核心概念、结构化日志输出，以及用 AsyncWrapper 做性能优化——全部基于 .NET 8 及以上的可运行示例。

如果你还在对比各家日志框架，可以先看 Dev Leader 的《Logging in .NET: The Complete Developer's Guide》了解全貌，再决定是否投入某个具体框架。

## NLog 是什么，为什么用它

NLog 是一个免费开源的 .NET 日志平台。整个系统由三个核心概念组成：

- **Targets**：日志输出到哪里——文件、数据库、控制台、Seq、Elasticsearch，或自定义目的地。
- **Layout Renderers**：每条日志里出现什么——时间戳、日志级别、logger 名称、结构化属性、HTTP 请求上下文。
- **Rules**：哪些 logger 写入哪些 target、最低日志级别是什么、带什么过滤器。

这种分离让 NLog 组合性极强：把 debug 日志路由到滚动文件、把错误路由到数据库、把致命告警路由到邮件——全部不用改一行应用代码。开启热重载（`autoReload="true"`）后，甚至可以在不重启服务的情况下修改运行时的路由行为。

NLog 支持 .NET 8、.NET 9、.NET Standard 2.0 和 .NET Framework 4.6+。ASP.NET Core 的主集成包是 `NLog.Web.AspNetCore`，它提供 HTTP 相关的 layout renderers 和干净的 host builder 扩展。

## 安装 NLog

前置条件：.NET 8+ SDK 和一个现有的 ASP.NET Core 或 Worker Service / 控制台项目。

对于 ASP.NET Core 应用，安装：

```bash
dotnet add package NLog.Web.AspNetCore
```

这个包会作为依赖拉入基础 `NLog` 包，同时带来 `${aspnet-*}` 系列 layout renderers（请求 URL、用户身份、trace identifier）和 `UseNLog()` host builder 扩展。

对于 Worker Service 或控制台应用，安装：

```bash
dotnet add package NLog
dotnet add package NLog.Extensions.Logging
```

## 在 ASP.NET Core (.NET 8) 中设置

NLog 与 `Microsoft.Extensions.Logging` 集成，所以业务代码继续使用熟悉的 `ILogger<T>`，只有注册部分是 NLog 专属的。最小化的 `Program.cs` 如下：

```csharp
using NLog.Web;

var logger = NLogBuilder
    .ConfigureNLog("nlog.config")
    .GetCurrentClassLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);

    builder.Logging.ClearProviders();
    builder.Host.UseNLog();

    builder.Services.AddControllers();
    // ... other service registrations

    var app = builder.Build();
    app.MapControllers();
    app.Run();
}
catch (Exception ex)
{
    logger.Fatal(ex, "Application startup failed");
    throw;
}
finally
{
    NLog.LogManager.Shutdown();
}
```

`try/catch/finally` 这个模式很重要。外层 `logger` 实例在 DI 容器初始化之前就捕获启动阶段的致命错误；`finally` 里的 `NLog.LogManager.Shutdown()` 负责在进程退出前冲刷所有缓冲消息——跳过这一步，进程退出时可能丢失最后几条日志。

## 两种配置方式

NLog 支持两种配置风格，按团队习惯任选其一。

### 方式一：nlog.config（XML）

经典做法是在项目根目录放一个 XML 文件：

```xml
<?xml version="1.0" encoding="utf-8" ?>
<nlog xmlns="http://www.nlog-project.org/schemas/NLog.xsd"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      autoReload="true"
      throwConfigExceptions="true"
      internalLogLevel="Warn"
      internalLogFile="${basedir}/internal-nlog.txt">
  <targets>
    <target xsi:type="File"
            name="appFile"
            fileName="${basedir}/logs/app-${shortdate}.log"
            layout="${longdate}|${uppercase:${level}}|${logger}|${message} ${exception:format=tostring}" />
    <target xsi:type="Console"
            name="console"
            layout="${level:truncate=4:uppercase=true}|${logger:shortName=true}|${message} ${exception:format=message}" />
  </targets>

  <rules>
    <logger name="Microsoft.*" maxlevel="Info" final="true" />
    <logger name="System.Net.Http.*" maxlevel="Info" final="true" />
    <logger name="*" minlevel="Debug" writeTo="appFile,console" />
  </rules>
</nlog>
```

然后要在 `.csproj` 里把该文件设为复制到输出目录：

```xml
<ItemGroup>
  <Content Include="nlog.config">
    <CopyToOutputDirectory>Always</CopyToOutputDirectory>
  </Content>
</ItemGroup>
```

几个关键配置项：`autoReload` 让配置变更热加载；`throwConfigExceptions` 让配置错误在启动时暴露而不是静默降级；`internalLogLevel` 与 `internalLogFile` 记录 NLog 自身的诊断日志，排查"日志不出现"问题时的第一现场。

### 方式二：appsettings.json

如果团队希望所有配置集中在一处，可以改用 `appsettings.json`。使用 `NLog.Extensions.Logging`（通用 host 应用）或 `NLog.Web.AspNetCore`（ASP.NET Core）时，调用 `UseNLog()` 后 NLog 会自动读取 JSON 里的 `NLog` 段：

```json
{
  "NLog": {
    "autoReload": true,
    "throwConfigExceptions": true,
    "internalLogLevel": "Warn",
    "extensions": [{ "assembly": "NLog.Web.AspNetCore" }],
    "targets": {
      "appFile": {
        "type": "File",
        "fileName": "${basedir}/logs/app-${shortdate}.log",
        "layout": "${longdate}|${uppercase:${level}}|${logger}|${message} ${exception:format=tostring}"
      },
      "console": {
        "type": "Console",
        "layout": "${level:truncate=4:uppercase=true}|${logger:shortName=true}|${message}"
      }
    },
    "rules": [
      { "logger": "Microsoft.*", "maxLevel": "Info", "final": true },
      { "logger": "System.Net.Http.*", "maxLevel": "Info", "final": true },
      { "logger": "*", "minLevel": "Debug", "writeTo": "appFile,console" }
    ]
  }
}
```

`Program.cs` 相应改为基于配置的注册，不再显式调用 `ConfigureNLog`：

```csharp
using NLog.Web;

var builder = WebApplication.CreateBuilder(args);

builder.Logging.ClearProviders();
builder.Host.UseNLog();

// NLog reads from builder.Configuration automatically when NLog section is present
```

JSON 方式在容器化环境里尤其顺手：配置覆盖来自环境变量或 Azure App Configuration，全部走同一套配置管线。

## 核心概念：Targets

Targets 定义日志输出到哪里。NLog 内置几十种 target，并提供了可扩展的 target API 支持自定义目的地：

| Target        | 包                   | 用途                             |
| ------------- | -------------------- | -------------------------------- |
| File          | 内置                 | 滚动日志文件，带归档             |
| Console       | 内置                 | 终端输出，适合容器               |
| Database      | 内置                 | 直接写入 SQL Server / PostgreSQL |
| Network       | 内置                 | UDP/TCP 转发到 syslog 接收端     |
| Mail          | 内置                 | 关键错误发送邮件                 |
| Seq           | NLog.Targets.Seq     | 自托管的结构化日志服务器         |
| Elasticsearch | Elastic.NLog.Targets | ELK 栈采集                       |

> 版本提示：`Database`、`Mail` 这类 target 的内置状态和功能细节在 NLog 5.x 与 NLog 6 之间可能有差异（当前 NuGet 上 NLog 6.1.x 为最新稳定版）。配置前务必在官方 NLog target 文档里核对当前的 target 列表与能力。

生产环境的高吞吐场景下，给任意 target 包一层 `AsyncWrapper` 几乎是必须的：

```xml
<target xsi:type="AsyncWrapper" name="asyncFile" queueLimit="10000" overflowAction="Discard">
  <target xsi:type="File" fileName="${basedir}/logs/app-${shortdate}.log" />
</target>
```

`AsyncWrapper` 把写入工作卸载到后台线程。没有它，每条日志语句都会阻塞调用线程，等待磁盘 I/O 或一次网络往返。

## 核心概念：Layout Renderers

Layout renderers 是组成日志消息格式的 `${}` 标记。常用的有：

| Renderer                       | 输出                             |
| ------------------------------ | -------------------------------- |
| `${longdate}`                  | `2026-08-01 21:00:00.0000`       |
| `${level}`                     | Info, Warn, Error                |
| `${logger}`                    | 完全限定的类名                   |
| `${message}`                   | 日志消息文本                     |
| `${exception:format=tostring}` | 带完整堆栈的异常                 |
| `${callsite}`                  | 类 + 方法名                      |
| `${aspnet-request-url}`        | HTTP 请求 URL（仅 ASP.NET Core） |
| `${event-properties:item=X}`   | 结构化日志属性值                 |

`${event-properties}` 是 NLog 结构化日志的关键。当你写 `LogInformation("Order {OrderId} received", orderId)` 时，NLog 会把 `OrderId` 捕获为命名属性。在 layout 里用 `${event-properties:item=OrderId}` 引用它；或者用带 `includeAllProperties="true"` 的 `JsonLayout` 把所有属性作为 JSON 文档整体输出。

## 核心概念：Rules

Rules 把 logger 与 target 连接起来。每条 rule 指定一个 logger 名称模式、最低（可选最高）日志级别，以及要写入的 target 列表：

```xml
<rules>
  <!-- Silence framework noise - final="true" stops further rule evaluation -->
  <logger name="Microsoft.*" maxlevel="Info" final="true" />
  <logger name="System.Net.Http.*" maxlevel="Info" final="true" />

  <!-- Application logs go to file -->
  <logger name="*" minlevel="Debug" writeTo="appFile" />

  <!-- Errors also route to a secondary target -->
  <logger name="*" minlevel="Error" writeTo="errorFile" />
</rules>
```

`final="true"` 是一个关键属性。没有它，匹配一条 rule 后 NLog 会继续求值后续 rule；有了它，求值在首次匹配处停止。这就是压制 Microsoft 框架的嘈杂日志、同时不丢失自己应用日志的办法。

## 在服务里使用 ILogger

注册完成后，整个应用照常使用标准 `ILogger<T>`：

```csharp
public sealed class OrderService
{
    private readonly ILogger<OrderService> _logger;

    public OrderService(ILogger<OrderService> logger)
    {
        _logger = logger;
    }

    public async Task ProcessOrderAsync(int orderId)
    {
        _logger.LogInformation("Processing order {OrderId}", orderId);

        try
        {
            // ... business logic
            _logger.LogInformation("Order {OrderId} processed successfully", orderId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to process order {OrderId}", orderId);
            throw;
        }
    }
}
```

消息模板要用命名占位符（`{OrderId}`）而不是字符串插值。字符串插值会丢掉属性结构——而对 Seq 或 Elasticsearch 这类 target，正是这个结构让日志变得可查询。

## 用 NLog 做结构化日志

结构化日志把日志事件作为结构化数据输出，而不是扁平字符串。NLog 通过 `JsonLayout` 支持：

```xml
<target xsi:type="File" name="jsonFile" fileName="${basedir}/logs/structured-${shortdate}.json">
  <layout xsi:type="JsonLayout" includeAllProperties="true" includeEventProperties="true">
    <attribute name="time" layout="${longdate}" />
    <attribute name="level" layout="${level}" />
    <attribute name="logger" layout="${logger}" />
    <attribute name="message" layout="${message}" />
    <attribute name="exception" layout="${exception:format=tostring}" encode="false" />
  </layout>
</target>
```

设置 `includeAllProperties="true"` 后，消息模板里的任何命名属性都会成为顶层 JSON 字段。对 `LogInformation("Order {OrderId} from {CustomerId}", 42, "CUST-7")` 会产出：

```json
{
  "time": "2026-08-01 21:00:00.0000",
  "level": "Info",
  "logger": "MyApp.OrderService",
  "message": "Order 42 from CUST-7",
  "OrderId": 42,
  "CustomerId": "CUST-7"
}
```

这样的输出可以直接在 Seq、Kibana 或 Grafana Loki 里查询，不需要任何额外的解析管线。

## 性能：AsyncWrapper 与高吞吐日志

日志最容易拖慢应用的方式，就是让写日志阻塞业务线程。`AsyncWrapper` 通过队列 + 后台线程解决这个问题，但两个参数需要按场景调：

- `queueLimit`：队列最大容量（示例里是 10000）。超出后的行为由 `overflowAction` 决定。
- `overflowAction`：队列满时的策略——`Discard`（丢弃新消息，保吞吐）、`Block`（阻塞调用线程，保完整）、`Grow`（扩容队列，保消息但耗内存）。

另外注意：`<targets>` 上的 `async="true"` 属性会一次性给所有 target 套上异步行为。两种方式选一种用，千万不要同时用，否则会双重包装。原文章的系列篇目里还有专门讲 AsyncWrapper 调优和高吞吐日志的章节，值得跟进。

## NLog 在 .NET 日志生态里的位置

.NET 的日志生态层次很清晰：最上层是 `Microsoft.Extensions.Logging` 抽象，所有 `ILogger<T>` 调用都流经它；抽象之下再插入具体 provider——NLog、Serilog 或其他实现。应用代码与具体框架完全解耦。

NLog 的 `NLog.Extensions.Logging`（ASP.NET Core 用 `NLog.Web.AspNetCore`）就是这个 provider，负责把 `Microsoft.Extensions.Logging` 的调用翻译进 NLog 内部管线。选择框架前值得理解这套抽象与 provider 的关系——Serilog 与 Microsoft.Extensions.Logging 的对比文章把这一点讲得很透，同样的推理也适用于评估 NLog；而 Serilog 的完整指南提供了直接对照的另一面。

## 常见问题

**NLog 在 .NET 里用来做什么？** 结构化和非结构化应用日志。它提供可配置的管线，根据日志级别、logger 名称和自定义过滤条件，把日志路由到一个或多个目的地——文件、数据库、邮件、Seq 或 Elasticsearch 等聚合工具，并通过 `Microsoft.Extensions.Logging` 集成让业务代码始终只用 `ILogger<T>`。

**NLog 能同时写多个 target 吗？** 能。定义多个 target 并为每个创建 rule 即可。一条日志可以同时匹配多条非 final rule，同一事件同时写入文件、数据库和控制台。需要独占路由时（比如压制某个嘈杂框架 logger），用 `final="true"` 停止后续求值。

**怎么排除"日志没写出来"的问题？** 优先检查三处：`nlog.config` 是否设置了 `CopyToOutputDirectory=Always`；配置里的 `internalLogFile` 是否有 NLog 自身的报错；rule 的 `minlevel` / logger 名称模式是否匹配到了实际 logger（如 `Microsoft.*` 规则误吞了应用日志）。

## 适用边界

NLog 适合需要文件热重载配置、细粒度规则路由、或希望配置和代码分离的团队；如果更偏好 C# 流式配置 API 和 sink 生态，Serilog 是常见替代。两者在应用代码层的集成方式完全一致，选择通常取决于配置风格偏好和具体 target/sink 生态。本文覆盖了从安装到生产使用的完整路径，但没有展开每个内置 target 的细节参数——那部分在官方文档和原文章的系列篇目里。

## 参考

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践，欢迎关注并留言你想看的主题。

- [NLog in .NET: Complete Guide to Flexible Logging（原文）](https://www.devleader.ca/2026/08/01/nlog-in-net-complete-guide-to-flexible-logging)
- [NLog 官方 target 文档](https://nlog-project.org/config/?tab=targets)
- [Logging in .NET: The Complete Developer's Guide](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
- [Serilog vs Microsoft.Extensions.Logging: Which Should You Use?](https://www.devleader.ca/2026/07/13/serilog-vs-microsoftextensionslogging-which-should-you-use)
- [Serilog in .NET: Complete Guide to Structured Logging](https://www.devleader.ca/2026/07/05/serilog-in-net-complete-guide-to-structured-logging)
