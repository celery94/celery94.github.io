---
pubDatetime: 2026-08-12T14:53:00+08:00
title: "NLog vs Serilog：2026 该怎么选"
description: "NLog 与 Serilog 是 .NET 最常用的两个日志库。本文从配置风格、结构化日志、路由能力、性能、生态与迁移成本六个维度对比，给出决策矩阵、适用场景与 FAQ。"
tags: ["NLog", "Serilog", "Logging", ".NET", "Observability"]
slug: "nlog-vs-serilog-which-to-choose"
ogImage: "../../assets/999/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/13/nlog-vs-serilog-in-net-which-should-you-choose"
---

NLog vs Serilog 是 .NET 社区最常见的日志之争。两个库都成熟、久经生产考验，都能通过 `Microsoft.Extensions.Logging` 的 `ILogger<T>` 接入 ASP.NET Core——也就是说，任何一个都能以最小的设置量装进应用。但它们做出了非常不同的设计选择，而这些差异在规模变大时会变得显著。

Nick Cosentino（Dev Leader）在 2026 年 8 月的这篇指南从生产环境真正关心的维度对比两者：配置风格、结构化日志支持、性能、规则与过滤能力、生态大小、迁移路径。读完后你会清楚哪个库适合你的团队和场景——也会看到哪些场景下答案是诚实的「两个都行」。

这篇文章适合：正在为 .NET 项目选日志库、或者在 NLog 与 Serilog 之间摇摆的开发者。如果你对某个库还不熟，本站的 NLog 入门与完整指南、以及作者配套的 Serilog 完整指南是起点。

## TL;DR 决策矩阵

先给需要快速答案的团队：

| 维度          | NLog 胜                       | Serilog 胜                              | 平手                     |
| ------------- | ----------------------------- | --------------------------------------- | ------------------------ |
| 配置风格      | ops 团队管理 XML/JSON         | dev 团队偏好 C# fluent API              | —                        |
| 规则/路由能力 | ✅ 按名字+级别+条件的复杂路由 | —                                       | —                        |
| 结构化日志    | —                             | ✅ 一等公民消息模板、对象 destructuring | —                        |
| 性能          | —                             | —                                       | ✅ 配 async wrapper 都快 |
| 生态大小      | —                             | ✅ 更多 sinks、更多社区扩展             | —                        |
| AOT / .NET 8+ | ✅ NLog 6 完整 AOT 支持       | ⚠️ AOT 支持在改善但未完全               | —                        |
| 学习曲线      | 较陡（XML 配置）              | 较浅（fluent C#）                       | —                        |
| 迁移成本      | 低（都用 ILogger<T>）         | 低（都用 ILogger<T>）                   | —                        |

一句话版本：**团队有强 ops 文化、配置文件和代码分离，选 NLog；团队写 C#、要最丰富的结构化日志和大生态，选 Serilog。** 对大多数新建 .NET 应用，Serilog 略占优——但 NLog 在路由和企业配置上有独特优势，依然是优秀选择。

## 配置风格：最明显的差异

评估特性、性能或生态之前，先问一个问题：**你们组织的日志配置归谁管？**

**NLog：配置文件优先。** 配置放在 `nlog.config`（XML）或 `appsettings.json`，支持热重载（`autoReload="true"`），可以由部署管道按环境切换：

```xml
<?xml version="1.0" encoding="utf-8" ?>
<nlog xmlns="http://www.nlog-project.org/schemas/NLog.xsd"
      autoReload="true">
  <targets>
    <target xsi:type="File" name="file"
            fileName="${basedir}/logs/${shortdate}.log"
            layout="${longdate}|${level:uppercase=true}|${message}${exception:format=tostring}" />
  </targets>
  <rules>
    <logger name="Microsoft.*" maxlevel="Info" final="true" />
    <logger name="*" minlevel="Info" writeTo="file" />
  </rules>
</nlog>
```

targets 和 rules 可以不重新编译就改。运维团队压制一个吵闹的命名空间、把错误重定向到新 target，改一个文件重启（或等热重载）即可——不需要开发者。

**Serilog：代码优先的 fluent API。** 配置是一串读起来像句子的 C# builder 链：

```csharp
Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Information()
    .MinimumLevel.Override("Microsoft", LogEventLevel.Warning)
    .Enrich.FromLogContext()
    .Enrich.WithMachineName()
    .WriteTo.Console()
    .WriteTo.File("logs/app-.log", rollingInterval: RollingInterval.Day)
    .CreateLogger();
```

IntelliSense 支持好、编译期校验、和 .NET DI 自然集成。代价是改配置要改代码、重新部署。对全栈团队这不是问题；对 dev/ops 分离的企业是摩擦点。Serilog 也支持通过 `Serilog.Settings.Configuration` 用 `appsettings.json` 配置，取两者之长。

## 结构化日志：Serilog 的 destructuring 优势

两个库都支持带消息模板的结构化日志——`{PropertyName}` 标记会成为日志事件上的命名属性而不是格式化文本：

```csharp
// Both NLog and Serilog handle this identically via ILogger<T>
_logger.LogInformation("Order {OrderId} placed by {CustomerId} totalling {Amount:C}",
    order.Id, order.CustomerId, order.Total);
```

在 `ILogger<T>` 下，两个库收到相同的 `EventId`、`LogLevel`、消息模板和参数值。差别在于**复杂对象**的处理。

Serilog 的 `@` destructuring 操作符把整个对象序列化成结构化数据，而不是调用 `ToString()`：

```csharp
// Serilog-native API
Log.Information("Order {@Order} was placed", order);
// → order.Id, order.Items[], order.Total captured as structured fields

// NLog equivalent: must use explicit properties or JsonLayout
_logger.LogInformation("Order placed: {OrderJson}", JsonSerializer.Serialize(order));
```

在 Seq、Elasticsearch 或任何结构化日志查看器里，`@` 前缀让整个对象图成为嵌套的结构化字段——这是 Serilog 的招牌差异。NLog 用 `JsonLayout` 和 `${all-event-properties}` 也能达到类似效果，但需要按 target 显式配置布局。重度使用结构化查询（按 `order.CustomerId` 过滤）的团队，Serilog 的一等公民 destructuring 是实打实的优势。

## 规则与路由：NLog 的主场

NLog 的规则引擎比 Serilog 的 level override 强大得多，这是 NLog 赢得最清楚的地方。

**NLog：按 logger、按级别、按条件路由。** 一条日志事件可以基于 logger 名、级别范围和表达式条件路由到不同 target，全部无需代码：

```xml
<rules>
  <!-- Audit logs → dedicated audit file, stop here -->
  <logger name="SecurityAudit" minlevel="Info" writeTo="auditFile" final="true" />
  <!-- Performance metrics → metrics target, stop here -->
  <logger name="Performance.*" minlevel="Info" writeTo="metricsTarget" final="true" />
  <!-- EF Core query noise → discard -->
  <logger name="Microsoft.EntityFrameworkCore.Database.Command" maxlevel="Info" final="true" />
  <!-- Framework warnings → file only -->
  <logger name="Microsoft.*" minlevel="Warn" writeTo="file" final="true" />
  <!-- Application → console + file -->
  <logger name="*" minlevel="Debug" writeTo="console,file" />
</rules>
```

`when` 条件语法还能在规则内做事件级过滤——忽略健康检查端点、节流重复消息、按消息内容路由。

**Serilog：最小级别 + 过滤器。** 主要路由机制是按源上下文的 `MinimumLevel.Override`：

```csharp
new LoggerConfiguration()
    .MinimumLevel.Override("Microsoft", LogEventLevel.Warning)
    .MinimumLevel.Override("Microsoft.EntityFrameworkCore.Database.Command", LogEventLevel.Warning)
    .WriteTo.Console()
    .WriteTo.File(...)
    .CreateLogger();
```

Serilog 也支持通过 `.WriteTo.Logger(...)` 建带独立 sinks 和级别的 sub-logger：

```csharp
.WriteTo.Logger(lc => lc
    .Filter.ByIncludingOnly(e => e.Properties.ContainsKey("AuditEvent"))
    .WriteTo.File("audit-.log", rollingInterval: RollingInterval.Day))
```

这覆盖大多数真实需求。但路由逻辑能塞进 3-4 个 `MinimumLevel.Override` 时 Serilog 很干净；需要按类目路由到 6 个 target、带级别范围和条件时，NLog 的规则更好管理。

## 性能：配置方式比选库更重要

在实际生产量级（每秒数百到数千事件），两个库配置了 async wrapper 后表现相近。同步 vs 异步的模式远比选哪个库重要。

- **NLog**：`AsyncWrapper` 和 `BufferingWrapper` 把调用线程和 I/O 解耦。典型数字：同步文件写 ~0.5–2 ms/调用（I/O 密集）；`AsyncWrapper` 入队 ~50–200 ns/调用（内存密集）；吞吐上限由后台线程写速决定，与调用者无关
- **Serilog**：`WriteTo.Async(...)` 提供等价的异步缓冲。默认队列 10,000 事件，可用 `bufferSize` 和 `blockWhenFull` 调整

两个库的 async 入队开销都在 ~100–200 ns 量级，都很少成为配置良好的生产系统的瓶颈——瓶颈几乎总是底层 I/O（磁盘写、数据库插入、HTTP 调用）。

## 生态：Serilog 的 sinks 长尾

输出目的地两个库都很多。实际差异在长尾：**Serilog 有 200+ 社区维护的 sinks**，覆盖广且更新及时——存储（File、MSSqlServer、MongoDB、AzureBlobStorage）、可观测性（Seq、Elasticsearch、Datadog）、云（AzureEventHub、ApplicationInsights、AWSCloudWatch）、消息（Kafka、RabbitMQ）。**NLog 有 70+ 官方和社区 targets**：File、ColoredConsole、Database、Seq、ElasticSearch、Mail、Slack、Web.AspNetCore，主流需求都覆盖。需要小众云服务时，Serilog 更可能有维护中的社区 sink。

## ILogger 集成：拉平差距的关键

两者都注册为 `ILoggerProvider`，从 MEL 抽象层收到相同的事件：

```csharp
// NLog integration
builder.Logging.AddNLog();

// Serilog integration
builder.Host.UseSerilog();
```

接入后，应用代码用 `ILogger<T>`，**从不直接 import NLog 或 Serilog 的命名空间**。两者之间切换只需改 `Program.cs` 里一行——服务和控制器代码一行都不用动。代价是：在 `ILogger<T>` 下，Serilog 的 `@` destructuring 这类原生差异只能通过库的原生 API 使用。

## 迁移：比想象中便宜

因为都走 `ILogger<T>`，迁移成本低于多数团队的预期：

- **NLog → Serilog**：移除 `NLog.Web.AspNetCore`，加 `Serilog.AspNetCore`；`AddNLog()` 换成 `UseSerilog()`；重写配置（NLog XML rules → Serilog fluent 或 appsettings.json）；自定义 target 迁移为自定义 sink（接口一样，基类不同）；验证 layout renderer → output template 产出等价
- **Serilog → NLog**：反向同样过程，fluent sink 配置翻译成 NLog targets 和 rules，enricher 换成 MDLC 或 NLog 内置 renderer

应用代码完全不用动。小应用一天完成；带自定义 sink/target 或复杂路由的大应用，预算一个 sprint。

## 什么时候选哪个

**选 NLog**：运维团队（而非开发者）管理日志配置，需要不改代码部署就能变的 XML/JSON 配置；需要复杂日志路由（不同命名空间按级别范围、名字模式、条件路由到不同 target）；需要最完整的 Native AOT 支持（NLog 6 比 Serilog 在 AOT 上走得远）；在扩展已有 NLog 代码库；需要不重启的热重载配置。

**选 Serilog**：团队偏好带 IntelliSense 和编译期校验的 C# fluent 配置；重度使用 `@` 对象 destructuring、需要日志查看器里的丰富结构化数据；需要 Serilog 大生态里的特定 sink（尤其较新的云平台）；新建 greenfield .NET 应用想要最大社区支持和文档；团队已深度投入 Serilog enrichers 与 MEL 集成模式。

## 诚实的答案

2026 年的大多数新 .NET 项目，Serilog 略占优：生态更大、结构化日志默认更好、对 fluent API 团队学习曲线更平缓。NLog 在企业环境有自己的位置：运维团队拥有日志配置、复杂路由是真需求、AOT 敏感场景。它不是劣质库——它做了不同的取舍，对某些团队和架构是更合适的。

实际建议：**还没开始就试 Serilog；如果发现路由不够用、或 ops 团队需要 XML 配置，NLog 是通过 `ILogger<T>` 迁移成本近零的出色替代。**

## 常见问题

**NLog 和 Serilog 谁更快？** 配置了 async wrapper 后都快，每次调用的差异可忽略（~50–200 ns）。真正的性能决定因素是是否用 async wrapper 包住 target、文件 target 是否配 `keepFileOpen="true"`。两者都不太可能成为生产 ASP.NET Core 应用的瓶颈。

**能同时用 NLog 和 Serilog 吗？** 技术上可以——两者都通过 `ILoggerProvider` 注册。但同时跑两个框架意味着所有日志事件流过两条管道，开销翻倍，生产环境不推荐。选一个做 MEL provider。

**NLog 支持像 Serilog 那样的结构化日志吗？** 支持。消息模板（同样的 `{PropertyName}` 语法）、`JsonLayout` 输出 JSON、`${all-event-properties}` 捕获所有命名属性。差异在对象 destructuring：Serilog 原生的 `@` 操作符自动序列化整个对象图，NLog 需要显式配置才能达到等价的结构化输出。

**NLog 还在积极维护吗？** 是。NLog 6.0（2025 年发布）带来 Native AOT 支持、改进的 JSON 配置和 .NET 8 优化，核心维护者活跃、定期发版。NLog 不是遗留库。

**该从 NLog 迁到 Serilog 吗？** 现状工作良好就不值得为迁移而迁移——两者通过 `ILogger<T>` 提供等价质量。只在有具体需求（Serilog 独有的 sink、NLog 配置无法干净满足的结构化需求）时才迁。

**ASP.NET Core 用哪个更好？** 都有 first-class 支持：Serilog 用 `Serilog.AspNetCore` 的 `UseSerilog()`，NLog 用 `NLog.Web.AspNetCore`。Serilog 的请求日志中间件（`UseSerilogRequestLogging()`）很流行——把冗长的内置请求日志换成每个请求一行结构化摘要，NLog 没有直接等价物（可用规则和过滤器实现类似效果）。

## 总结

记住五个关键差异：**配置风格**（NLog = XML/JSON 配置文件，ops 友好；Serilog = C# fluent，dev 友好）、**路由能力**（NLog 规则引擎处理复杂按命名空间/级别路由；Serilog 的 level override 覆盖多数情况但复杂扇形路由不够灵活）、**结构化日志**（Serilog 的 `@` destructuring 和原生 ILogger 更丰富；走 MEL 两者都行）、**生态**（Serilog sinks 更多，NLog 覆盖常见目的地）、**迁移成本**（近零——应用接口都是 `ILogger<T>`）。

## 参考

- [NLog vs Serilog in .NET: Which Should You Choose?（原文，Nick Cosentino）](https://www.devleader.ca/2026/08/13/nlog-vs-serilog-in-net-which-should-you-choose)
- [NLog 6.0 Major Changes（官方，AOT 支持与破坏性变更）](https://nlog-project.org/2025/04/29/nlog-6-0-major-changes.html)
- [Serilog 官方文档（sinks 与配置）](https://serilog.net/)
- [Logging in .NET | Microsoft Learn（Microsoft.Extensions.Logging 与 ILogger<T>）](https://learn.microsoft.com/en-us/dotnet/core/extensions/logging)
