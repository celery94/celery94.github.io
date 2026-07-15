---
pubDatetime: 2026-07-15T08:28:41+08:00
title: "Serilog vs Microsoft.Extensions.Logging：本就不是二选一"
description: "MEL 是日志抽象层，Serilog 是日志实现引擎，它们互补而不是竞争。这篇从架构、sink 生态、结构化能力、性能差异和迁移步骤几个角度，帮你判断什么时候 MEL 够用、什么时候值得上 Serilog。"
tags: ["Serilog", "Microsoft.Extensions.Logging", "结构化日志", ".NET", "日志"]
slug: "serilog-vs-microsoft-extensions-logging"
ogImage: "../../assets/939/01-cover.png"
source: "https://www.devleader.ca/2026/07/13/serilog-vs-microsoftextensionslogging-which-should-you-use/"
---

Serilog 和 Microsoft.Extensions.Logging 哪个更好？这个问题从 .NET Core 早期就开始被反复问，但它本身就是个范畴错误。MEL 是日志**抽象层**，Serilog 是日志**实现引擎**，大多数生产环境里你会同时用两个，不是挑一个。

把分层搞清楚了，决策就很自然：你的代码永远面向 `ILogger<T>` 接口写，背后由 Serilog 管线负责处理、结构化、发送。下面是两者的边界、什么时候 MEL 内置 provider 就够了、什么时候 Serilog 能多给你些什么。

## MEL 是什么

`Microsoft.Extensions.Logging` 是 .NET 内置的日志抽象层，所有 .NET 6+ 项目模板里都有。它提供：

- `ILogger<T>` 和 `ILogger` 接口，你的代码只管调它
- `ILoggerProvider` 和 `ILoggerFactory`，负责把日志事件路由给 provider
- 日志级别、category 和作用域 `BeginScope()`
- `[LoggerMessage]` 源生成器，热路径零分配
- 内置 provider：Console、Debug、EventSource、EventLog（Windows）
- 通过 `appsettings.json` 的 `"Logging"` 小节配置

MEL 是 .NET 生态里所有组件——ASP.NET Core、EF Core、HttpClientFactory 和几乎所有正经库——打日志的统一入口。你配好了 MEL，就是在决定应用程序里**所有**日志的去向。

### MEL 架构

```
应用代码 → ILogger<T>
              ↓
       ILoggerFactory
              ↓
  [ILoggerProvider1] → Console
  [ILoggerProvider2] → Debug
  [ILoggerProvider3] → Serilog  ← (Serilog.Extensions.Logging)
```

MEL 把日志事件同时发给一个或多个已注册的 provider。provider 就是实际的 sink，决定日志最终去哪。内置 provider 随 .NET 出厂；第三方库比如 Serilog、NLog、log4net 把自己注册成 provider 接入这条链路。

## Serilog 是什么

Serilog 是第三方的 .NET 结构化日志库。它的核心设计目标很明确：把日志事件的数据作为结构化的对象保留下来，而不是压扁成字符串。

Serilog 提供：

- 自己原生的 `Serilog.ILogger`（独立于 MEL）
- 一个对象解构管线，模板里用 `@notation` 展开复杂对象
- 庞大的 sink 生态：Seq、Elasticsearch、Application Insights、Azure、SQL Server 等等
- Enricher，自动给每条日志附加上下文
- Sub-logger、日志事件过滤、最小级别覆写
- ASP.NET Core 集成 `Serilog.AspNetCore`（含请求日志中间件）
- `Serilog.Extensions.Logging` 桥，把 Serilog 注册为 MEL 的 provider

### Serilog 作为 MEL Provider

```csharp
builder.Host.UseSerilog((ctx, services, config) =>
    config
        .ReadFrom.Configuration(ctx.Configuration)
        .ReadFrom.Services(services)
        .Enrich.FromLogContext()
        .WriteTo.Console()
        .WriteTo.Seq("http://localhost:5341"));
```

`UseSerilog()` 会替换掉所有其他 MEL provider，把所有 `ILogger<T>` 调用导入 Serilog 管线。你的应用代码一行不动——照样调 `_logger.LogInformation(...)`，只是背后处理这些事件的引擎换成了 Serilog。

## 核心差异：抽象 vs 实现

| 关注点            | MEL                  | Serilog                                 |
| ----------------- | -------------------- | --------------------------------------- |
| 代码调用的接口    | ✅ `ILogger<T>`      | ❌（用 MEL 接口）                       |
| 结构化日志管线    | ❌ 有限              | ✅ 完整管线                             |
| Sink 生态         | ❌ 4 个内置          | ✅ 100+ 社区 sink                       |
| Enricher          | ❌ 只有 scope        | ✅ 完整 API                             |
| Sub-logger 和过滤 | ❌                   | ✅                                      |
| 请求日志中间件    | ❌                   | ✅ `UseSerilogRequestLogging()`         |
| 源生成日志        | ✅ `[LoggerMessage]` | ✅（通过 MEL 桥）                       |
| appsettings 配置  | ✅                   | ✅ via `Serilog.Settings.Configuration` |
| 需要 NuGet        | 否（内置）           | 是                                      |

**正确的理解**：MEL 定义接口，Serilog 是引擎。它们是互补的，不是竞争的。

## MEL 内置 Provider 什么时候够用

有些场景，MEL 自带的 provider 完全够用：

**小型内部工具**：控制台程序或者后台服务，打日志只是为了开发调试看两眼的，内置 Console provider 足够了。

**简单的 Azure 托管应用**：Azure App Service 会自动捕获 `ILogger<T>` 控制台输出，如果你装了 `Microsoft.ApplicationInsights`，还会自动导到 Application Insights。不需要 Serilog。

**本地开发**：Console 和 Debug provider 在开发时足够反馈。

**Azure Functions + Application Insights**：Azure Functions 跟 Application Insights 通过 MEL 的集成很紧密，在这里加 Serilog 是增加复杂度而不增加收益。

核心问题不是"该不该用 Serilog"，而是"我需不需要 MEL 内置 provider 给不了的能力"。

## Serilog 真正值钱的场景

### 1. Seq：本地开发和自托管日志

Seq 是 Serilog 的杀手级搭档。它是一个结构化日志服务器，一行 Docker 就能本地跑起来：

```bash
docker run -d --name seq -p 5341:5341 -p 8081:80 -e ACCEPT_EULA=Y datalust/seq
```

```csharp
.WriteTo.Seq("http://localhost:5341")
```

Seq 的查询界面可以写这种句子：

```
select OrderId, Amount, ElapsedMs from stream
where @Level = 'Warning' and ElapsedMs > 500
```

前提是日志是结构化数据——字符串没法查。Seq + Serilog 是让 .NET 应用最快获得结构化可观测性的方案。

### 2. 多个 Sink 配不同级别过滤

```csharp
.WriteTo.Console(restrictedToMinimumLevel: LogEventLevel.Information)
.WriteTo.File("logs/errors.txt", restrictedToMinimumLevel: LogEventLevel.Error)
.WriteTo.Seq("http://localhost:5341", restrictedToMinimumLevel: LogEventLevel.Debug)
```

MEL 也能路由到多个 provider，但在 `appsettings` 里做每个 provider 的最小级别配置很别扭。Serilog 的 sink 级过滤清爽又灵活。

### 3. Elasticsearch、OpenSearch 和可观测后端

要把日志送到 ELK、OpenSearch、Datadog、Grafana Loki，Serilog 有维护良好的 sink，输出的 JSON 格式是对口后端能直接消费的。MEL 的内置 provider 不具备这些能力。

```bash
dotnet add package Serilog.Sinks.Elasticsearch
```

```csharp
.WriteTo.Elasticsearch(new ElasticsearchSinkOptions(new Uri("http://localhost:9200"))
{
    AutoRegisterTemplate = true,
    IndexFormat = "dotnet-logs-{0:yyyy.MM.dd}"
})
```

### 4. 结构化请求日志

`UseSerilogRequestLogging()` 把 ASP.NET Core 默认的逐事件打散日志（开始、结束、header、状态码）替换成一条结构化事件，包含耗时、状态码、路径和请求方法：

```
[13:15:22 INF] HTTP GET /api/orders 200 45ms
```

还带 `MachineName`、`RequestId`、`SourceContext` 和通过 `IDiagnosticContext` 加进来的自定义属性。MEL 内置 provider 没有等价物。

### 5. 解构复杂对象

```csharp
_logger.LogInformation("Created order {@Order}", order);
```

用 `@notation`，Serilog 会把 `Order` 对象解构成结构化字段——`order.Id`、`order.CustomerId`、`order.Items.Count` 在 Seq 或 Elasticsearch 里都变成可查询字段。MEL 用 Console provider 只会调一下 `ToString()`。

## 从 MEL 内置迁移到 Serilog

迁移是渐进式的，应用代码一句不动：

**第一步：装包**

```bash
dotnet add package Serilog.AspNetCore
dotnet add package Serilog.Settings.Configuration
dotnet add package Serilog.Sinks.Console
dotnet add package Serilog.Sinks.File
```

**第二步：把 `builder.Logging` 换成 `builder.Host.UseSerilog()`**

```csharp
// 删掉这句也行——UseSerilog 会覆写
// builder.Logging.AddConsole();

builder.Host.UseSerilog((ctx, services, config) =>
    config
        .ReadFrom.Configuration(ctx.Configuration)
        .ReadFrom.Services(services)
        .Enrich.FromLogContext()
        .WriteTo.Console(new ExpressionTemplate(
            "[{@t:HH:mm:ss} {@l:u3}] {#if SourceContext is not null}{" +
            "Substring(SourceContext, LastIndexOf(SourceContext, '.') + 1)}: {#end}{@m}\n{@x}"))
        .WriteTo.File("logs/app.log", rollingInterval: RollingInterval.Day));
```

**第三步：加上启动期 bootstrap logger**

```csharp
Log.Logger = new LoggerConfiguration()
    .WriteTo.Console()
    .CreateBootstrapLogger();

try
{
    // builder 的配置...
    builder.Host.UseSerilog(...);
    var app = builder.Build();
    await app.RunAsync();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Application terminated unexpectedly");
}
finally
{
    await Log.CloseAndFlushAsync();
}
```

**第四步：把日志配置移到 Serilog 小节**

```json
{
  "Serilog": {
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft.AspNetCore": "Warning",
        "Microsoft.EntityFrameworkCore.Database.Command": "Warning"
      }
    }
  }
}
```

MEL 的 `"Logging"` 小节可以删掉了——Serilog 接管之后它不再起作用。

## 源生成日志 + Serilog

`[LoggerMessage]` 源生成完全穿过 MEL 桥到 Serilog：

```csharp
public static partial class AppLoggers
{
    [LoggerMessage(EventId = 100, Level = LogLevel.Information,
        Message = "Order {OrderId} processed in {ElapsedMs}ms")]
    public static partial void OrderProcessed(
        this ILogger logger, string orderId, long elapsedMs);
}
```

```csharp
_logger.OrderProcessed(order.Id, stopwatch.ElapsedMilliseconds);
```

事件穿过 Serilog 管线：enricher 补上机器名、correlation ID 和用户上下文，再路由给 Seq、Elasticsearch 或任何配好的 sink。你拿到零分配日志**同时**拿到 Serilog 的完整管线。

## 性能差异

对高吞吐场景，两边都能跑得很快，关键看怎么配：

| 方式                                  | 分配   | 备注                   |
| ------------------------------------- | ------ | ---------------------- |
| `[LoggerMessage]` 源生成 + MEL        | 零分配 | 最快选项，Serilog 兼容 |
| `Serilog.ILogger` 消息模板            | 低     | 模板只解析一次         |
| `ILogger.LogInformation()` + Serilog  | 低     | MEL 桥有微小开销       |
| 字符串插值 `$"..."`                   | 高     | 被过滤时也分配         |
| `ILogger.LogInformation()` 不检查级别 | 中     | 被过滤时仍计算参数     |

MEL 桥给 `ILogger<T>` 调用加的开销用纳秒量级来算，大多数应用完全可以忽略。热路径用 `[LoggerMessage]` 源生成就好——不管你背后是 MEL 还是 Serilog 都能用。

## MEL 最低级别过滤的坑

MEL 自己有最低级别过滤，发生在 Serilog 管线**之前**。如果 MEL 把事件拦下来了，Serilog 根本看不到。要保证 MEL 把所有事件都传给 Serilog，把 MEL 最低级别设成 `Trace`：

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Trace"
    }
  },
  "Serilog": {
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft.AspNetCore": "Warning"
      }
    }
  }
}
```

或者清掉所有 MEL provider，让 Serilog 独揽大权：

```csharp
builder.Logging.ClearProviders();
builder.Host.UseSerilog(...);
```

## 常见问题

**该用 Serilog 还是 MEL？**

两个都用。代码面向 MEL 的 `ILogger<T>` 写，不绑定具体库。然后把 Serilog 配置成 MEL provider，拿到结构化日志、enricher 和完整 sink 生态。两者互补，不是二选一。

**Serilog 会替换掉 ILogger 吗？**

不会。用 `Serilog.AspNetCore` 之后你的代码仍然使用 `Microsoft.Extensions.Logging.ILogger<T>`。Serilog 通过 `UseSerilog()` 把自己注册为 MEL 的 provider，处理所有事件。注入点和调用点都不需要改。

**Serilog 为什么有自己的 ILogger 接口？**

Serilog 出现的时候 `Microsoft.Extensions.Logging` 还没标准化。`Serilog.ILogger` 支持 Serilog 特有功能，比如上下文 logger `ForContext<T>()`，用于 Serilog 配置 API。应用代码里始终用 `Microsoft.Extensions.Logging.ILogger<T>` 来做依赖注入和保持可移植性。

**MEL 的日志是结构化的吗？**

部分是。MEL 支持消息模板和命名参数（`"Order {OrderId} placed"`），当 provider 支持时能产出结构化输出。但 MEL 内置的 Console 和 Debug provider 不会把结构属性渲染成可查询格式。Serilog 和它的 sink 可以。

**Serilog 和 MEL 内置 provider 的性能差大吗？**

大多数应用忽略不计。Serilog 通过 MEL 桥调用和创建属性有微小开销，纳秒级别。`[LoggerMessage]` 源生成能完全避免分配，不管背后是 MEL 内置还是 Serilog 都一样工作。先 profiling 再优化。

**`[LoggerMessage]` 源生成能和 Serilog 一起用吗？**

能。源生成方法穿过 MEL `ILogger<T>` 接口，配了 `UseSerilog()` 就自然路由到 Serilog。零分配日志 + Serilog 的结构化管线、enricher 和 sink，两样都有。

**什么时候选 NLog 而不是 Serilog？**

NLog 是另一个优秀的 .NET 日志库，强项不太一样：条件日志更灵活，内置 target 更丰富，有些基础设施团队偏好 XML/NLog.config 的配置风格。Serilog 和 NLog 都能通过 MEL 的 provider 模式接入，选哪个更多是团队偏好。Serilog 在 .NET 开源社区生态更大，现代 .NET 文档里引用也更频繁。

## 参考

- [原文链接](https://www.devleader.ca/2026/07/13/serilog-vs-microsoftextensionslogging-which-should-you-use/)
