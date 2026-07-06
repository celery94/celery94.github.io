---
pubDatetime: 2026-07-06T20:11:47+08:00
title: ".NET 日志记录：从 Console.WriteLine 到生产级可观测性"
description: "覆盖 ILogger、结构化日志、日志级别、源生成高性能日志、Serilog/NLog 对比、OpenTelemetry 集成和常见错误，适合 .NET 9/10 开发者从零搭建可用的日志体系。"
tags:
  [
    ".NET",
    "Logging",
    "ILogger",
    "Serilog",
    "NLog",
    "OpenTelemetry",
    "ASP.NET Core",
    "Structural Logging",
  ]
slug: "logging-in-dotnet-complete-developers-guide"
source: "https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide"
ogImage: "../../assets/926/01-cover.png"
---

从 `Console.WriteLine` 开始，到 `Debug.WriteLine`，再到 `Microsoft.Extensions.Logging`——很多 .NET 开发者走到第三步就停下了，因为日志跑通了，线上也没出问题。但当你真的需要在一百万条日志里找到某次支付失败的原因时，才发现早期的一些写法让排查变得异常困难。

这篇指南覆盖了 .NET 9 和 .NET 10 下日志记录的完整图景：`ILogger` 抽象、日志级别划分、结构化日志的正确写法、源生成高性能日志、Serilog/NLog 选型对比，以及 OpenTelemetry 如何把日志、追踪和指标串到一条管线里。

## ILogger 抽象：所有日志的起点

.NET 日志体系建立在 `ILogger` 接口之上。它不是某个具体实现，而是一层抽象——应用代码面向 `ILogger` 编程，底层由 Console、JsonConsole、Serilog 或其他 Provider 负责输出。这意味着你随时可以替换日志后端，不用改一行业务逻辑。

```csharp
using Microsoft.Extensions.Logging;

public class OrderService
{
    private readonly ILogger<OrderService> _logger;

    public OrderService(ILogger<OrderService> logger)
    {
        _logger = logger;
    }

    public void ProcessOrder(int orderId, string userId)
    {
        _logger.LogInformation(
            "Processing order {OrderId} for user {UserId}",
            orderId, userId);

        // 业务逻辑...

        _logger.LogInformation(
            "Order {OrderId} processed successfully", orderId);
    }
}
```

### 为什么用 ILogger&lt;T&gt; 而不是 ILogger

泛型版本 `ILogger<T>` 有三层好处：

- **分类名（Category）**：类型参数 T 自动成为日志分类名，出现在每条日志输出里。更重要的是，你可以按分类配置最低日志级别，把 ASP.NET Core、EF Core 等框架日志压到 Warning，只对业务代码开放 Information 和 Debug。
- **依赖注入开箱即用**：`CreateBuilder()` 内部已经调用了 `AddLogging()`，构造函数注入 `ILogger<T>` 就能用。
- **可测试**：既可以注入 `ILogger<T>` mock，也可以用 `Microsoft.Extensions.Logging.Testing` 包直接捕获日志条目做断言。

## 日志级别：不是越细越好

.NET 定义了六个日志级别，从最啰嗦到最严重依次排列：

| 级别        | 数值 | 什么时候用                      |
| ----------- | ---- | ------------------------------- |
| Trace       | 0    | 最细粒度的诊断（函数入口/出口） |
| Debug       | 1    | 开发期有用，生产环境关闭        |
| Information | 2    | 正常业务里程碑                  |
| Warning     | 3    | 意外但不阻断执行的情况          |
| Error       | 4    | 影响当前操作的失败              |
| Critical    | 5    | 系统级故障，需要立即关注        |
| None        | 6    | 完全关闭日志                    |

把什么都写成 `Information` 是最常见的错误——框架路由日志、EF Core SQL 日志和你的业务日志搅在一起，真正有用的信息被淹没了。一个实用的经验法则：

- **Information**：“订单 1234 已提交，用户 abc”——运营和业务关心的事件
- **Warning**：“外部支付 API 第 2 次重试中”——降级运行，还在正常服务
- **Error**：“订单 1234 支付失败：连接超时”——需要排查的可操作错误

按分类配置最低级别，在 `appsettings.json` 里安静地抑制框架日志：

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning",
      "Microsoft.EntityFrameworkCore.Database.Command": "Warning",
      "MyApp.OrderService": "Debug"
    }
  }
}
```

## 结构化日志：把日志写成可查询的数据

结构化日志的核心是把日志写成键值对，而不是拼成一段字符串。当你需要在一千万条日志里找到 `OrderId = 5678` 的所有记录时，结构化属性查询比全文搜索快几个数量级。

**错误写法——字符串拼接，丢掉结构化属性：**

```csharp
_logger.LogInformation(
    $"Order {orderId} placed by user {userId} for ${amount}");
```

**正确写法——消息模板：**

```csharp
_logger.LogInformation(
    "Order {OrderId} placed by {UserId} for {Amount:C}",
    orderId, userId, amount);
```

`{OrderId}`、`{UserId}`、`{Amount}` 这些花括号语法是**消息模板**，不是字符串插值。框架会把它们作为独立属性记录到日志事件中。后续在 Seq、Elasticsearch、Azure Monitor 或 Splunk 里做结构化查询时，过滤的是属性而不是文本，效率和精度都完全不一样。

## 高性能日志：源生成 LoggerMessage

从 .NET 6 开始，推荐的高性能写法是用 `[LoggerMessage]` 源生成器属性。.NET 9/10 内置的 Roslyn 分析器 `CA1848` 会在热路径代码中标记普通的 `LogInformation()` 调用，建议迁移到源生成版本。

为什么源生成的日志性能更好：

- **值类型零装箱**：参数在编译期就已确定类型
- **只在需要时才分配字符串**：日志级别被过滤掉时不会触发任何字符串分配
- **编译期校验**：模板语法错误直接报编译错误，而不是运行时才发现

```csharp
public partial class OrderService
{
    private readonly ILogger<OrderService> _logger;

    public OrderService(ILogger<OrderService> logger)
    {
        _logger = logger;
    }

    public void ProcessOrder(int orderId, string userId)
    {
        LogProcessingOrder(_logger, orderId, userId);
    }

    [LoggerMessage(
        Level = LogLevel.Information,
        Message = "Processing order {OrderId} for user {UserId}")]
    private static partial void LogProcessingOrder(
        ILogger logger, int orderId, string userId);

    [LoggerMessage(
        Level = LogLevel.Information,
        Message = "Order {OrderId} processed successfully")]
    private static partial void LogOrderComplete(
        ILogger logger, int orderId);
}
```

`partial` 方法声明告诉源生成器在编译期生成实现代码，最终产物是一个强类型、零分配的日志调用。对大多数应用代码的性能差异可以忽略，但在高吞吐量服务中——或者只要 `CA1848` 触发了——就应该用这种写法。

## 内置 Provider 和 JSON Console

.NET 自带几个 Provider：

- **Console**：标准输出。容器化应用的首选——Docker 和 Kubernetes 日志聚合器会自动收集 stdout。
- **Debug**：Visual Studio 输出窗口，仅开发期。
- **EventLog**：Windows 事件日志，传统本地部署场景。
- **EventSource**：ETW / `dotnet-trace`，用于生产诊断和性能分析。

对云原生部署，JSON Console 输出往往是正确选择：

```csharp
builder.Logging.AddJsonConsole(options =>
{
    options.JsonWriterOptions = new JsonWriterOptions { Indented = false };
    options.IncludeScopes = true;
    options.TimestampFormat = "yyyy-MM-ddTHH:mm:ss.fffZ";
});
```

JSON 输出意味着你的日志聚合器（Fluent Bit、Logstash、Azure Monitor）收到的是机器可直接解析的结构化条目，不需要额外写正则去拆字段。

## 第三方日志库选型

内置 Provider 满足基本需求，生产环境通常会引入第三方库。

**Serilog** 是 .NET 生态使用最广的结构化日志库。它通过 `Serilog.Extensions.Logging` 桥接到 `ILogger`，代码继续使用 `ILogger<T>`，底层由 Serilog 负责输出。Serilog 4.x + `Serilog.AspNetCore 10.0.0` 完整支持 .NET 9/10，包括 AOT 和剪裁。关键优势：100+ 个 Sink（Seq、Elasticsearch、Splunk、Azure Table Storage 等）、丰富的 Enrichment API、以及与 Seq 的优秀本地开发体验。

**NLog** 是一个成熟的、支持 XML 配置的日志框架，适合需要复杂路由规则的场景——例如把 Warning 路由到数据库，Error 同时写文件和发邮件。NLog 6.x 支持 .NET 6-10。

**MEL 内置**：部署到 Azure 时通过 `AddApplicationInsightsTelemetry()` 原生集成 Application Insights。对于简单的云原生应用，JSON Console Provider 往往就够了。

快速对比：

| 维度               | MEL 内置                 | Serilog            | NLog          |
| ------------------ | ------------------------ | ------------------ | ------------- |
| Sink/Target 数量   | Console, Debug, EventLog | 100+ 个包          | 60+ 个 Target |
| 结构化日志         | 通过 Provider            | 原生（消息模板）   | 原生          |
| Enrichment         | 仅 Scopes                | 丰富（按属性追加） | 丰富          |
| 配置方式           | appsettings.json         | 代码 + appsettings | XML + 代码    |
| AOT 支持 (.NET 10) | 是                       | 是 (4.x)           | 部分          |
| 热路径性能         | 好（源生成）             | 优秀（异步 Sink）  | 好            |

## 日志作用域：一次绑定，全局生效

`BeginScope` 让你在一个代码块内为所有日志条目附加共享上下文，不用每一行都手动传参：

```csharp
public async Task<IActionResult> PlaceOrder(OrderRequest request)
{
    using var scope = _logger.BeginScope(new Dictionary<string, object>
    {
        ["RequestId"] = HttpContext.TraceIdentifier,
        ["UserId"] = request.UserId,
        ["Operation"] = "PlaceOrder"
    });

    _logger.LogInformation(
        "Validating order for {ItemCount} items", request.Items.Count);
    // 验证逻辑...

    _logger.LogInformation("Committing order to database");
    // 持久化逻辑...

    _logger.LogInformation("Order placement complete");
    return Ok();
}
```

`using var scope` 内部所有 `LogInformation` 调用都自动带上 `RequestId`、`UserId` 和 `Operation`。Serilog、NLog 和 MEL 的 JSON Console Provider 都支持传播 Scope 属性。这个模式在中间件里尤为好用——一个 HTTP 请求的所有日志自动共享关联 ID。

## OpenTelemetry：日志、追踪、指标合一

OpenTelemetry (OTel) 是开放的可观测性标准。在 .NET 9/10 中它深度集成，允许通过单一管线输出日志、分布式追踪和指标，并且三者之间自动关联。

```csharp
builder.Services.AddOpenTelemetry()
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddRuntimeInstrumentation())
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation())
    .WithLogging(logging => logging
        .AddConsoleExporter())
    .UseOtlpExporter();
```

`.WithLogging()` 把 `ILogger` 桥接到 OTel 管线。如果你处在分布式追踪的 Span 中，`ILogger` 发出的日志条目会自动携带当前的 `TraceId` 和 `SpanId`。从一条错误告警拿到 Trace ID，就能拉出这次完整调用链上的所有日志——跨多个服务。

## 常见错误清单

**记录敏感数据**：永远不要把密码、Token、信用卡号或 PII 写进日志。这既是 GDPR/PCI-DSS 合规问题，也是安全风险。

```csharp
// 错误——日志里出现了密码
_logger.LogInformation(
    "Login attempt: user={User} password={Password}", user, password);

// 正确
_logger.LogInformation("Login attempt for user {User}", user);
```

**用字符串插值替代消息模板**：字符串插值会立即分配字符串，同时丢失了结构化属性。

```csharp
// 错误——丢失了 OrderId 的结构化属性
_logger.LogInformation($"Order {orderId} placed");

// 正确——OrderId 被捕获为独立属性
_logger.LogInformation("Order {OrderId} placed", orderId);
```

**在紧密循环内不加级别检查就打日志**：

```csharp
// 错误——即使 Debug 级别被关闭，每次循环仍在计算参数
foreach (var item in items)
{
    _logger.LogDebug("Processing item: " + item.Id);
}

// 正确——使用源生成日志或 IsEnabled 检查
foreach (var item in items)
{
    LogProcessingItem(_logger, item.Id);
}

[LoggerMessage(Level = LogLevel.Debug, Message = "Processing item {ItemId}")]
private static partial void LogProcessingItem(ILogger logger, int itemId);
```

**不按分类设置最低级别**：所有分类都留 `Information` 会把 ASP.NET Core 路由日志、EF Core SQL、HttpClient 追踪和你的业务日志搅在一起。务必在 `appsettings.json` 中为框架分类设置覆盖规则。

## 2026 年的选型建议

一个实用的决策框架：

- **新建 .NET 10 云原生应用**：JSON Console + OpenTelemetry。如果需要多 Sink 支持或本地 Seq 仪表盘，加 Serilog。
- **部署到 Azure 的 ASP.NET Core API**：MEL + Application Insights Exporter 覆盖大部分场景。
- **高流量微服务**：源生成 `[LoggerMessage]` + Serilog 异步 Sink，把日志 I/O 从热路径移出去。
- **需要复杂路由规则的企业应用**：NLog 的 XML 配置提供最灵活的路由能力。

如果你关注 .NET 开发、工具实践和可运维的软件工程，可以关注 Aide Hub。这里会继续分享能落地的教程、工具分析和工程观察。

## 参考

- [原文：Logging in .NET: The Complete Developer's Guide](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
- [Microsoft.Extensions.Logging 官方文档](https://learn.microsoft.com/en-us/dotnet/core/extensions/logging)
- [源生成 LoggerMessage 文档](https://learn.microsoft.com/en-us/dotnet/core/extensions/logging/source-generation)
- [CA1848 分析器规则](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1848)
- [Serilog GitHub](https://github.com/serilog/serilog)
- [NLog 官网](https://nlog-project.org/)
- [Serilog.AspNetCore NuGet](https://www.nuget.org/packages/Serilog.AspNetCore)
- [.NET 可观测性与 OpenTelemetry](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/observability-with-otel)
