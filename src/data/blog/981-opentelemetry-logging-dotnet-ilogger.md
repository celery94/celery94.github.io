---
pubDatetime: 2026-07-29T12:03:40+08:00
title: "OpenTelemetry Logging in .NET：从 ILogger 到结构化日志导出"
description: "纯文本日志文件不够用了？本文带你从零配置 OpenTelemetry logging in .NET，覆盖 ILogger 无缝集成、trace context 自动关联、OTLP 导出、结构化日志解析和生产环境最佳实践。不需要改业务代码，你的日志就能和 traces、metrics 在同一个可观测后端里关联查询。"
tags: ["OpenTelemetry", ".NET", "Logging", "ILogger", "Observability"]
slug: "opentelemetry-logging-dotnet-ilogger"
ogImage: "../../assets/981/01-cover.png"
source: "https://www.devleader.ca/2026/07/28/opentelemetry-logging-net-ilogger-integration-and-structured-log-export"
---

如果你用 .NET 构建应用的时间够长，大概率碰到过这样的瓶颈：纯文本日志文件不够用了。日志量越来越大，排查问题越来越慢，你需要在成堆的文本文件里找某一个请求的上下文，这个过程痛苦到足以让你怀疑人生。

**OpenTelemetry logging in .NET 改变了这个局面。** 你不再只有孤立的日志文件，而是获得结构化的日志记录，它们和你的 traces、metrics 在同一个遥测管线中流动 —— 而且可以**自动关联回单次请求**。这是生产环境排障能力的一次实质性升级。

这篇文章来自 Dev Leader，类型是**教程/实操**。我会带你走完整套配置流程：`ILogger` 如何开箱即用集成、如何配置 exporter、trace 上下文如何自动出现在日志里、以及和 Serilog 相比怎么取舍。

如果你是第一次接触 .NET 日志体系，建议先看 Nick 的 [Logging in .NET Complete Guide](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide) 打底。想了解完整的 OpenTelemetry 图景，可以看 [OpenTelemetry in .NET: Complete Observability Guide](https://www.devleader.ca/2026/07/25/opentelemetry-dotnet-complete-observability-guide)。

## 可观测性的第三根支柱

可观测性通常用三种信号来描述：**traces、metrics 和 logs**。每一种回答不同的问题，缺了任何一个或它们之间互相断开，你就会丢失一些关键信息。

- **Traces** 告诉你「发生了什么」—— 一个请求由哪些操作组成，每一步花了多长时间
- **Metrics** 告诉你「规模多大」—— 每秒多少请求、p99 延迟在哪里、堆内存消耗了多少
- **Logs** 告诉你「具体细节」—— 实际值是什么、错误消息说了什么、系统在某个精确时刻处于什么状态

这三种信号在**互相关联**时威力翻倍。如果你能在查看一个慢 trace 时直接跳转到那个请求发出的日志行，排障时间会大幅缩短。如果你的日志携带了业务逻辑设置的结构化字段，你就能像查数据库一样来过滤和查询它们，而不是在字符串里大海捞针。

这就是正确配置 OpenTelemetry logging in .NET 之后的状态。日志自动从当前活跃的 span 中获取 `traceId` 和 `spanId`，你可以在 Grafana、Seq 或 Azure Monitor 等后端中在不同信号之间自由跳转。**没有这种关联，你仍然在猜哪个日志行属于哪个请求。**

另一个好处是一致性。你的服务名称、版本和环境信息是 traces、metrics 和 logs 共享的 Resource 的一部分。后端工具可以通过 `service.name` 过滤，就能获取所有三种信号类型的关联数据，不需要任何额外配置。

## ILogger 如何与 OpenTelemetry 集成

OpenTelemetry logging in .NET 最让人舒服的一点是：**你几乎不需要改现有代码**。`ILogger<T>` 接口已经是 .NET 的一等抽象，OpenTelemetry SDK 在 Provider 层面接入 —— 不是在调用点。

也就是说，你继续写 `_logger.LogInformation(...)`，跟今天一模一样。OpenTelemetry logging provider 捕获这些事件，转换成 `LogRecord` 对象，然后传递给你配置的 exporter —— console、OTLP，或两者都有。**没有新的日志 API 要学，不需要在现有日志调用里加特殊属性。**

Provider 模型是这一切运转的基础。.NET 的日志基础设施（`Microsoft.Extensions.Logging`）围绕 Provider 构建。每个 Provider 接收所有通过配置过滤器的日志事件，然后按自己的方式导出。OpenTelemetry Provider 只是这个列表中的又一个条目，跟 console provider、debug provider 或你可能有的 Serilog 集成并列。

这跟 Serilog 的工作方式有本质区别。Serilog 通常**替换** `Microsoft.Extensions.Logging` 管线，在 sink 层面接管或者成为主 logger。OpenTelemetry 的方式是**坐在标准基础设施旁边**，扩展它而不是替换它。两者的详细对比，可以看 [Serilog vs Microsoft.Extensions.Logging](https://www.devleader.ca/2026/07/13/serilog-vs-microsoftextensionslogging-which-should-you-use)。

## 从零配置 OpenTelemetry Logging

入口是 `Program.cs` 中的 `builder.Logging.AddOpenTelemetry()`。这会在 .NET 日志基础设施中注册 OpenTelemetry log provider，然后你链式配置 exporter 和其他选项：

```csharp
using OpenTelemetry.Logs;
using OpenTelemetry.Resources;

var builder = WebApplication.CreateBuilder(args);

builder.Logging.AddOpenTelemetry(logging =>
{
    logging.IncludeFormattedMessage = true;
    logging.IncludeScopes = true;
    logging.ParseStateValues = true;

    logging.AddConsoleExporter(); // 本地开发用
    // 生产环境替换为:
    // logging.AddOtlpExporter();
});

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService("MyApp", serviceVersion: "1.0.0"))
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation());
        // traces 和 logs 共享相同的 Resource 配置
```

几点值得展开：

- `IncludeFormattedMessage = true` 告诉 SDK 在 `LogRecord` 中也存储完整的格式化日志字符串，而不仅仅是原始结构化属性。默认只捕获结构化属性 —— 这在程序化查询日志时通常就是你想要的 —— 但在人类可读的查看器中，有格式化消息会很方便
- Resource 配置（`ConfigureResource`）在 tracing 和 logging 之间共享。你的 `service.name` 和 `service.version` 属性会同时出现在 trace span 和 log record 上。**这是一个关键设计点：你定义服务身份一次，它自动流向所有信号**
- Console exporter 底层使用 `SimpleLogRecordExportProcessor`，每条日志同步导出。开发环境没问题。生产环境用 OTLP exporter，默认使用 `BatchLogRecordExportProcessor`

## Trace Context 自动关联

这就是 OpenTelemetry logging in .NET 在生产排障中真正发光的地方。

当你在一个活跃的 `Activity`（映射到 OpenTelemetry span）内部发出日志时，SDK 自动从 `Activity.Current` 捕获 `TraceId` 和 `SpanId`，并将它们包含在日志记录中。

**你不需要为此写任何额外代码。它自动发生。**

```csharp
using System.Diagnostics;
using Microsoft.Extensions.Logging;

namespace MyApp.Services;

public class PaymentService
{
    private static readonly ActivitySource _activitySource =
        new("MyApp.Payments");
    private readonly ILogger<PaymentService> _logger;
    private readonly IPaymentGateway _paymentGateway;

    public PaymentService(
        ILogger<PaymentService> logger,
        IPaymentGateway paymentGateway)
    {
        _logger = logger;
        _paymentGateway = paymentGateway;
    }

    public async Task<PaymentResult> ProcessAsync(
        PaymentRequest request)
    {
        using var activity = _activitySource
            .StartActivity("ProcessPayment");
        activity?.SetTag(
            "payment.method", request.Method);

        // 这条日志自动包含 traceId 和 spanId
        // 因为 Activity.Current 已被设置
        _logger.LogInformation(
            "Processing payment {PaymentId} with method {Method}",
            request.PaymentId,
            request.Method);

        var result = await _paymentGateway
            .ChargeAsync(request);

        if (!result.Success)
        {
            _logger.LogError(
                "Payment {PaymentId} failed: {Reason}",
                request.PaymentId,
                result.ErrorMessage);
        }

        return result;
    }
}
```

当你在可观测性后端查看这条日志时，你不仅能看到消息和结构化字段（`PaymentId`、`Method`），还能看到 `traceId` 和 `spanId`。从那里，你可以直接跳转到对应的 trace，查看完整请求链路 —— 包括计时、下游调用和错误。**这就是从猜谜到精准排障的转变。**

## 日志类别、过滤与 Scopes

`ILogger` 的 category（类别）机制映射到 OpenTelemetry 的 `CategoryName` 属性。如果你用的是 `ILogger<PaymentService>`，category 就是 `MyApp.Services.PaymentService`。这让后端可以按组件过滤日志 —— 只看 Payment 模块的日志，而不是整个应用的所有日志。

日志过滤在 .NET 的日志基础设施层面配置，在 OpenTelemetry Provider 看到事件之前就已经生效。所以过滤足够早，不会浪费导出带宽：

```csharp
builder.Logging.AddFilter("MyApp.Services.Payments",
    LogLevel.Debug);
builder.Logging.AddFilter("Microsoft.EntityFrameworkCore",
    LogLevel.Warning);
```

紧接着就是 `IncludeScopes`。在 .NET 中，`ILogger.BeginScope()` 让你把键值对附着到某个 scope 内的所有日志事件上。当 `IncludeScopes = true` 时，这些 scope 值被序列化为 log record 上的属性。这在为请求的 `RequestId`、`UserId` 或 `TenantId` 等上下文信息做标注时非常有用：

```csharp
using (_logger.BeginScope(
    new Dictionary<string, object>
    {
        ["OrderId"] = orderId,
        ["CustomerId"] = customerId
    }))
{
    // 这个 scope 内的所有日志都会携带 OrderId 和 CustomerId
    _logger.LogInformation("Processing order");
}
```

## 日志级别映射

.NET 的 `LogLevel` 枚举和 OpenTelemetry 的 severity 之间的映射是**自动且直接**的，但知道具体映射关系有助于你在后端设置告警规则：

| .NET LogLevel | OpenTelemetry Severity |
| ------------- | ---------------------- |
| `Trace`       | `TRACE` (1)            |
| `Debug`       | `DEBUG` (5)            |
| `Information` | `INFO` (9)             |
| `Warning`     | `WARN` (13)            |
| `Error`       | `ERROR` (17)           |
| `Critical`    | `FATAL` (21)           |

OpenTelemetry severity 的数值范围是 1-24，以上映射由 SDK 自动处理。如果你在 Grafana 或 Azure Monitor 中按 severity 过滤，这里就是你看到的对应关系。

## 用 OTLP 导出到生产环境

Console exporter 适合开发，但生产环境需要把日志发送到真正的后端。OTLP（OpenTelemetry Protocol）是标准方式：

```csharp
builder.Logging.AddOpenTelemetry(logging =>
{
    logging.IncludeFormattedMessage = true;
    logging.IncludeScopes = true;
    logging.ParseStateValues = true;

    logging.AddOtlpExporter(options =>
    {
        options.Endpoint = new Uri(
            "https://api.honeycomb.io/v1/logs");
        options.Headers = "x-honeycomb-team=your-api-key";
        options.Protocol =
            OpenTelemetry.Exporter.OtlpExportProtocol.HttpProtobuf;
    });
});
```

OTLP exporter 默认使用 `BatchLogRecordExportProcessor`，它会缓冲日志记录然后批量发送。默认批次大小在多数场景下够用，但高吞吐量服务可以调整：

```csharp
logging.AddOtlpExporter(options =>
{
    options.BatchExportProcessorOptions = new()
    {
        MaxQueueSize = 4096,
        MaxExportBatchSize = 512,
    };
});
```

## ParseStateValues 和 IncludeFormattedMessage

这两个选项经常被一起打开，但它们做的是不同的事：

- `ParseStateValues = true`：SDK 解析日志消息模板中命名的结构化值，并将它们作为 `LogRecord` 上的独立属性暴露。所以 `"Processing payment {PaymentId}"` 会产生一个叫 `PaymentId` 的属性，你可以直接在后端中查询和过滤
- `IncludeFormattedMessage = true`：SDK 同时存储插值完成后的完整字符串。这在以文本为主的查看器中非常有用，但会**增加每个日志记录的载荷**

这两个都设为 `true` 通常是最佳默认值 —— 结构化属性用于查询，格式化消息用于可读性。但如果日志量很大、带宽是个问题，关闭 `IncludeFormattedMessage` 可以显著减小载荷。

## Batch 与 Simple Log Processor

| Processor                        | 行为                     | 适用场景    |
| -------------------------------- | ------------------------ | ----------- |
| `SimpleLogRecordExportProcessor` | 每条日志同步导出         | 开发 / 测试 |
| `BatchLogRecordExportProcessor`  | 缓冲日志，按批次异步导出 | 生产环境    |

Console exporter 默认用 Simple。OTLP exporter 默认用 Batch。简单规则：生产环境永远用 Batch，因为同步导出每条日志会拖慢应用的热路径。

## OpenTelemetry Logging vs Serilog

这不一定是二选一。实际上很多人**同时使用**。

- **单独用 OpenTelemetry logging**：当你想要通过 OTLP 协议导出到可观测后端、不需要 Serilog 丰富的 sink 生态、而且想要 traces 和 metrics 在同一管线中自动关联时
- **单独用 Serilog**：当你需要特定的 sink（比如写到本地滚动文件，或有特定格式要求的第三方），或者你不想引入 OpenTelemetry SDK 的额外依赖时
- **两者共用**：OpenTelemetry 处理到你后端的关联导出，Serilog 处理本地文件日志或特殊格式。两者可以在同一个 `Microsoft.Extensions.Logging` 管线中共存

如果你刚开始构建一个新的 .NET 应用并且打算使用可观测性平台，**直接上 OpenTelemetry** 的长期摩擦最小。如果你有一个已有的 Serilog 配置跑得很好，**不需要急着换** —— 你随时可以之后在它旁边加上 OpenTelemetry。

## 常见问题

### OpenTelemetry logging 会替换 ILogger 吗？

不会。OpenTelemetry 是一个 **Provider**，接入 .NET 已有的 `ILogger` 基础设施。你继续注入 `ILogger<T>` 并调用同样的方法。OpenTelemetry 捕获这些调用产生的日志事件，但你现有的日志代码一行都不需要改。

### trace context 怎么自动进入日志的？

当 ASP.NET Core 收到一个请求时，它创建一个 `Activity`（.NET 的 span 表示）。任何在该请求处理过程中发出的日志调用，都会自动获取 `Activity.Current?.TraceId` 和 `Activity.Current?.SpanId`。OpenTelemetry log provider 在生成每条 `LogRecord` 时做这件事 —— 你不需要写任何桥接代码。

### ParseStateValues 和 IncludeFormattedMessage 有什么区别？

`ParseStateValues` 解析模板中的结构化值（`{PaymentId}`），让它们成为后端中可查询的独立属性。`IncludeFormattedMessage` 存储最终渲染的字符串。两者一起打开是最常见的配置，能同时满足查询和可读性需求。

### 能同时使用 OpenTelemetry logging 和 Serilog 吗？

可以。你可以在 `Microsoft.Extensions.Logging` 管线中同时有 Serilog provider 和 OpenTelemetry provider。两者会收到相同的日志事件，各自独立导出。常见模式：Serilog 处理本地文件，OpenTelemetry 处理 OTLP 导出到中央平台。

### IncludeScopes 是做什么的，应该开启吗？

开启后，通过 `ILogger.BeginScope()` 设置的键值对会作为属性附着在每个 log record 上。如果你使用 scope 来传播 RequestId、UserId 或 TenantId 等上下文，你会希望开启这个选项，这样这些值就会出现在你导出的日志中。

### 生产环境应该用哪个 exporter？

**OTLP**。它使用高效的二进制协议（protobuf），支持批量导出，是所有主流可观测性后端的标准协议。Console exporter 只适合本地开发。

### .NET LogLevel 如何映射到 OpenTelemetry severity？

`Trace→TRACE(1)`, `Debug→DEBUG(5)`, `Information→INFO(9)`, `Warning→WARN(13)`, `Error→ERROR(17)`, `Critical→FATAL(21)`。映射是自动的，不需要手动配置。

## 总结

OpenTelemetry logging in .NET 最打动人的地方在于它的**非侵入性**。你不需要学新的日志 API，不需要在每个调用点手动传递 trace context，不需要为不同后端写不同的导出代码。

核心就三步：

1. `builder.Logging.AddOpenTelemetry()` 注册 provider
2. 配置 `IncludeFormattedMessage`、`ParseStateValues`、`IncludeScopes` 按需开启
3. 选择 exporter —— Console 用于开发，OTLP 用于生产

结果是一个**日志、traces、metrics 三合一的可观测性管线**。你的日志自动获得 trace context，在后端中可以跨信号导航，排障从猜谜变成精准定位。

如果你正在开始一个新的 .NET 项目，并且计划使用可观测性平台，直接上 OpenTelemetry 是长期摩擦最小的选择。如果你已经有了 Serilog 或其它方案跑得很好，OpenTelemetry 可以优雅地坐到它旁边 —— 扩展，而不是替换。

## 参考

- [原文：OpenTelemetry Logging .NET: ILogger Integration and Structured Log Export — Dev Leader](https://www.devleader.ca/2026/07/28/opentelemetry-logging-net-ilogger-integration-and-structured-log-export)
- [Logging in .NET Complete Guide](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
- [OpenTelemetry in .NET: Complete Observability Guide](https://www.devleader.ca/2026/07/25/opentelemetry-dotnet-complete-observability-guide)
- [Serilog vs Microsoft.Extensions.Logging](https://www.devleader.ca/2026/07/13/serilog-vs-microsoftextensionslogging-which-should-you-use)
- [OpenTelemetry .NET SDK](https://github.com/open-telemetry/opentelemetry-dotnet)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
