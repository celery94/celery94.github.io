---
pubDatetime: 2026-07-27T07:58:56+08:00
title: "OpenTelemetry in .NET：可观测性完整指南"
description: "从零开始理解 OpenTelemetry 在 .NET 中的三大信号——Trace、Metrics、Logs——如何用 System.Diagnostics 原生 API 统一采集，再通过 OTLP 导出到任意后端。包含快速上手代码、自定义 ActivitySource、Meter 设计、Serilog 配合以及生产环境 exporter 配置，读完能直接在自己的 ASP.NET Core 项目里落地可观测性。"
tags: ["OpenTelemetry", ".NET", "Observability", "ASP.NET Core", "Tracing", "Metrics", "Logging"]
slug: "opentelemetry-dotnet-complete-observability-guide"
ogImage: "../../assets/969/01-cover.png"
source: "https://www.devleader.ca/2026/07/25/opentelemetry-in-net-complete-observability-guide"
---

生产系统失败的方式，单元测试往往抓不到。一个全部测试通过的的服务，仍然可能有一个 48 小时才浮现的内存泄漏、一个在 1000 行数据时表现正常但 100 万行时超时的数据库查询、或者一个在高负载下间歇退化的下游依赖。要理解运行中的生产系统到底发生了什么，你需要可观测性（observability）——而 OpenTelemetry .NET 就是现代、厂商中立的方式。

OpenTelemetry 是一个 CNCF（Cloud Native Computing Foundation）旗下的开源可观测框架。它为捕获三种可观测信号——Traces（链路追踪）、Metrics（指标）、Logs（日志）——提供了统一 API，并以标准化格式输出到任何兼容的后端：Jaeger、Grafana、Azure Monitor、Datadog、Honeycomb、Seq 等等。你只 instrumentation 一次代码，后端切换通过配置完成，不动代码。

本文是 OpenTelemetry .NET 的完整指南。你会了解 OTel 是什么、.NET 的内置原语如何与它对齐、三类信号怎么配置、如何为业务逻辑写自定义 instrumentation、以及怎样搭建生产就绪的 exporter 配置。无论你是在新建一个 ASP.NET Core API，还是在给已有项目加可观测性，这里都是起点。

## OTel 是什么

OpenTelemetry 源于两个早期框架的合并：OpenCensus（来自 Google）和 OpenTracing（一个 CNCF 项目）。两者目标重叠，造成了 instrumentation 代码被绑定到特定厂商或后端的碎片化局面。OpenTelemetry 将它们统一为单一标准，背后几乎有所有主流可观测厂商支持。

OTel 定义了三样东西：

**API**：各语言记录遥测数据的接口。在 .NET 中，这些直接映射到 `System.Diagnostics.Activity`（Traces）、`System.Diagnostics.Metrics.Meter`（Metrics）和 `Microsoft.Extensions.Logging.ILogger`（Logs）——三者全在 .NET BCL 里。

**SDK**：收集、处理、采样、导出遥测数据的实现。.NET SDK 位于 `OpenTelemetry` NuGet 包系列中，通过 Listener 基础设施 hook 进 BCL 原语。

**数据格式**：传输遥测到后端的标准有线协议——主要是 OTLP（OpenTelemetry Protocol），使用 gRPC 或 HTTP/protobuf。

厂商中立这一点在实际中非常重要。你用 OTel API 写一次 instrumentation 代码。你可以把同一份遥测数据在开发时发到本地 Jaeger、在预发布环境发到 Grafana、在生产环境发到 Azure Monitor——只改配置，不改代码。这种可移植性是选择 OpenTelemetry .NET 而不是厂商 SDK 的最强理由之一。

## 为什么 .NET 应用需要可观测性

传统理解生产问题的方法是查日志文件。你在文本里搜 Error，尝试从时间戳和消息字符串还原出当时发生了什么。这种方法有用，但有限，在几个重要场景下会失效。

**延迟排查。** 你的 API 慢了。日志显示请求耗时 2 秒。但慢在哪里？数据库查询？下游服务？序列化开销？JSON 解析？没有 Trace，你只能猜。有了 Trace，你看到的是一个时间轴，展示每一步操作及其耗时——慢的那一步立即暴露出来，并且能归属到具体的代码路径。

**跨服务关联。** 用户报告了一个错误。你在 API 服务里找到了日志条目。但真正失败的是三个跳之后的一个支付服务。没有分布式追踪，串联这两个日志条目需要一个手动传播的 correlation ID——如果你一开始就想到要加的话。OpenTelemetry 通过 W3C `traceparent` 头自动处理这种传播。

**主动健康监控。** 你想知道错误率是否低于 0.1%、p99 延迟是否在 500ms 以内——并且在这些阈值被突破时收到告警。基于日志的告警可以做，但成本高（每条日志都要传输和存储）而且有摄入延迟。Metrics 在导出前就聚合好了，存储便宜得多、查询更快，更适合做看板和规模化告警。

**错误的上下文诊断。** 当某个请求失败时，你需要：展示究竟发生了什么的 Trace、说明是孤立事件还是大面积回归的 Metrics、以及带完整错误细节和上下文的结构化 Logs。三种信号加在一起才讲得清完整故事。OpenTelemetry 让三者通过 trace ID 关联变得可行，你不用自己建这套关联体系。

## 可观测性的三大支柱

OpenTelemetry 把遥测组织为三种信号类型。理解每种信号是干什么的，有助于你决定要 instrumentation 什么、怎么 instrumentation。

| 信号 | 回答的问题 | 最适合 | 成本特征 |
|---|---|---|---|
| Traces | 这次请求中发生了什么，每步花了多长时间？ | 延迟分析、请求流可视化、根因排查 | 每个请求一条记录 |
| Metrics | 系统在聚合层面随时间表现得怎么样？ | 看板、SLO 追踪、告警 | 进程内聚合——非常便宜 |
| Logs | 这个时刻到底发生了什么？ | 详细调试、审计记录、结构化事件 | 每个显著事件一条记录 |

**Traces** 是一个 span 树，每个 span 代表一个离散工作单元——HTTP 请求、数据库查询、方法调用。Span 有开始时间、耗时、状态码（ok/error）、键值标签（attributes），还可以携带结构化事件记录。Trace 是延迟分析、请求流可视化和特定故障根因排查的工具。

**Metrics** 是一个测量序列——一个每次请求递增的 Counter、一个追踪请求耗时分布的 Histogram、一个报告当前内存使用量的 Gauge。Metrics 在导出前聚合，存储便宜、查询快，是看板、SLO 和告警的基础。

**Logs** 是一个结构化事件，带时间戳、严重级别、消息和任意键值属性。Logs 提供 Trace 和 Metrics 捕捉不到的细节——精确的错误消息、触发某个分支的具体输入、超时的 SQL 查询。OTel logging 与 tracing 一起配置时，log 记录自动打上当前 trace ID 和 span ID，让你在后端中可以从 trace 直接导航到关联的 log 条目。

三种信号协同工作。Trace 告诉你故障长什么样。Metrics 告诉你影响范围有多大。Logs 给你修复它的细节。

## .NET 如何实现 OpenTelemetry

OpenTelemetry .NET 最被低估的一点是：核心 API 已经在 .NET 运行时里了。微软在 OpenTelemetry 到达当前形态之前好几年就把 OTel 兼容原语内建进了标准库，然后把它们精确对齐到了 OTel 规范。

**`System.Diagnostics.Activity`** 是 .NET 的 trace span 实现。通过 `ActivitySource` 创建 `Activity`，在功能上等同于创建 OTel span。OTel SDK hook 进 `ActivityListener` 基础设施——这是运行时内建的发布/订阅机制——来从所有已注册的源收集 activity 并导出。

**`System.Diagnostics.Metrics.Meter`** 及其 instrument 类型（`Counter<T>`、`Histogram<T>`、`ObservableGauge<T>`）是 .NET 的 metrics 原语。OTel SDK hook 进 `MeterListener` 基础设施来收集 metric 读数并通过配置的管道导出。

**`Microsoft.Extensions.Logging.ILogger`** 是 .NET 的 logging 抽象。OTel SDK 提供了一个 `ILoggerProvider` 实现，从标准 `ILogger` 管道接收日志记录，与 traces 和 metrics 一起导出。

实际后果是：如果你的库或框架代码已经在用 `Activity`、`Meter` 或 `ILogger`，它已经在产生 OTel 兼容的遥测。ASP.NET Core、Entity Framework Core、gRPC 和其他框架组件内部就在使用这些原语。给一个已有的 ASP.NET Core 应用添加 OpenTelemetry，几乎不用多少代码就能浮现大量 instrumentation 数据——框架自己的遥测本来就已经在那里了，等着被收集。

## 关键 NuGet 包

开始用 OpenTelemetry .NET 需要几个包：

- **`OpenTelemetry.Extensions.Hosting`**——与 `WebApplicationBuilder` 和 `IHostBuilder` 的核心集成。提供 `AddOpenTelemetry()` 扩展方法。
- **`OpenTelemetry.Instrumentation.AspNetCore`**——ASP.NET Core 请求处理的自动 instrumentation：HTTP span、路由模板、响应状态码。
- **`OpenTelemetry.Instrumentation.Http`**——出站 `HttpClient` 请求的自动 instrumentation：span 创建和 W3C `traceparent` 头注入。
- **`OpenTelemetry.Exporter.Console`**——把遥测输出到 stdout。本地开发和初始设置阶段极有用。
- **`OpenTelemetry.Exporter.OpenTelemetryProtocol`**——通过 OTLP 导出到任何兼容后端：Jaeger、Grafana、Seq、Honeycomb 等。
- **`OpenTelemetry.Instrumentation.Runtime`**——.NET 运行时 metrics：GC 暂停时间、堆大小、线程池队列长度、异常率。

如果部署在 Azure，**`Azure.Monitor.OpenTelemetry.AspNetCore`** 提供一次调用就导出三类信号到 Application Insights 的集成，不需要单独的 OTel collector。如果有自建 Prometheus 基础设施，**`OpenTelemetry.Exporter.Prometheus.AspNetCore`** 暴露一个 `/metrics` scrape 端点。

## 快速上手：三信号一次性配置

最快接入 OpenTelemetry .NET 的方式，就是在 `Program.cs` 里加几行。下面这个配置能捕获 HTTP 请求 trace、基础 ASP.NET Core metrics 和结构化 log——全部导出到 Console，不需要额外基础设施你就能马上看到。

```csharp
// NuGet packages needed:
// OpenTelemetry.Extensions.Hosting
// OpenTelemetry.Instrumentation.AspNetCore
// OpenTelemetry.Instrumentation.Http
// OpenTelemetry.Exporter.Console

using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService("MyApp", serviceVersion: "1.0.0"))
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddConsoleExporter())
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddConsoleExporter());

builder.Logging.AddOpenTelemetry(logging =>
{
    logging.IncludeFormattedMessage = true;
    logging.AddConsoleExporter();
});

var app = builder.Build();
app.MapGet("/", () => "Hello, observability!");
app.Run();
```

运行起来，发一个请求，你就能在控制台看到 trace 数据、metrics 记录和 log 输出——三类信号，零额外基础设施。Console exporter 是推荐的方式：在接入真实后端前，先确认你的 instrumentation 是否正常工作。一旦本地看到预期的 span 和 metrics，切换到 OTLP 只需一行改动。

## Trace 深入：为业务逻辑自定义 ActivitySource

`AddAspNetCoreInstrumentation` 和 `AddHttpClientInstrumentation` 提供的自动 instrumentation 捕获了请求处理的外层：入站 HTTP 请求、匹配到的路由、响应状态码。这是有价值的上下文。但真正有意思的信息通常在业务逻辑里——库存可用性检查、定价计算、欺诈检测调用。

自定义 tracing 的做法是：创建一个 `ActivitySource`（.NET 中 OTel `Tracer` 的等价物），然后在你想观测的操作周围启动 `Activity`：

```csharp
using System.Diagnostics;

namespace MyApp.Services;

public class CheckoutService
{
    private static readonly ActivitySource _activitySource =
        new("MyApp.Checkout", "1.0.0");
    private readonly ILogger<CheckoutService> _logger;

    public CheckoutService(ILogger<CheckoutService> logger)
    {
        _logger = logger;
    }

    public async Task<CheckoutResult> CheckoutAsync(
        Cart cart, string userId)
    {
        using var activity = _activitySource.StartActivity("Checkout");
        activity?.SetTag("cart.item_count", cart.Items.Count);
        activity?.SetTag("user.id", userId);

        _logger.LogInformation(
            "Starting checkout for user {UserId} with {ItemCount} items",
            userId, cart.Items.Count);

        try
        {
            var result = await ProcessCheckoutAsync(cart);
            activity?.SetStatus(ActivityStatusCode.Ok);
            return result;
        }
        catch (Exception ex)
        {
            activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
            activity?.RecordException(ex);
            throw;
        }
    }
}
```

几个值得留意的细节：

- **`activity?.` 空条件操作符**是刻意的。当没有 listener 注册到该 source 时——即 OTel 没配置，或者采样决定不记录这个 trace——`StartActivity` 返回 `null`。你的业务代码应该优雅处理 null，而不是抛 `NullReferenceException`。
- **`RecordException`** 把结构化事件加到 span 上，包含异常类型、消息和堆栈。这比纯 error status 更有用——观测后端可以跨所有 span 索引和搜索异常，通常能让你不用手动关联日志条目就发现错误模式。
- **Tags 尽量遵循 OpenTelemetry 语义约定**。OTel 项目发布了常见领域的标准属性名：`user.id`、`db.system`、`http.method`、`messaging.system` 等等。使用标准名称，你的遥测数据就能在理解 OTel 约定的后端中跟开箱即用的看板和查询直接适配。
- **记得注册你的 `ActivitySource`**：在 `WithTracing(...)` 配置中加上 `.AddSource("MyApp.Checkout")` 或 `.AddSource("MyApp.*")`。少了这一步，span 虽然创建了但会被静默丢弃。

## Metrics 深入：Counter、Histogram 与 Gauge

Metrics 是生产监控中最具成本效益的可观测信号。不像 Trace（每个请求一条记录）和 Log（每个显著事件一条记录），Metrics 在导出前就在进程内聚合好了。10,000 个请求的 histogram 变成一组紧凑的桶计数。这让 metrics 存储便宜、查询快，很适合高流量生产系统。

OpenTelemetry .NET 使用 `System.Diagnostics.Metrics`——跟你不使用 OTel 直接用的 BCL API 是一样的：

```csharp
using System.Diagnostics;
using System.Diagnostics.Metrics;

public class ApiMetrics : IDisposable
{
    private readonly Meter _meter;
    private readonly Counter<long> _requestsTotal;
    private readonly Histogram<double> _requestDuration;

    public ApiMetrics(IMeterFactory meterFactory)
    {
        _meter = meterFactory.Create("MyApp.Api");

        _requestsTotal = _meter.CreateCounter<long>(
            "api.requests.total",
            description: "Total API requests processed");

        _requestDuration = _meter.CreateHistogram<double>(
            "api.request.duration",
            unit: "ms",
            description: "Request processing duration");
    }

    public void RecordRequest(
        string endpoint, int statusCode, double durationMs)
    {
        var tags = new TagList
        {
            { "endpoint", endpoint },
            { "status_code", statusCode }
        };
        _requestsTotal.Add(1, tags);
        _requestDuration.Record(durationMs, tags);
    }

    public void Dispose() => _meter.Dispose();
}
```

生产规模的 metrics 设计注意事项：

- **在 DI 代码里用 `IMeterFactory`**。它正确处理 `Meter` 生命周期并与 OTel 的 meter 收集管道集成。避免在生产服务里直接用 `new Meter(...)`。
- **小心高基数标签**。有很多唯一值的标签——原始 user ID、完整 URL、每个单独错误消息——会导致基数爆炸。你的后端会为每种唯一标签组合创建独立的时序，规模大了成本会很高。用低基数标签：状态码、路由模板（不是原始路径）、服务名、预定义分类。
- **按测量内容选择 instrument 类型**。`Counter<T>` 用于只增不减的值（已处理的请求、已发送的字节、遇到的错误）。`Histogram<T>` 用于关心百分位数的分布（延迟、负载大小）。`ObservableGauge<T>` 用于测量本身有成本、应按需执行的点值（活跃连接数、队列深度）。`UpDownCounter<T>` 用于既可增也可减的值（进行中的请求、缓存条目）。

## Logging 深入：结构化日志与 Trace 关联

OpenTelemetry 不会替换你的 logging 设置，而是增强它。你继续用 `ILogger<T>`，跟之前完全一样。OTel logging 集成加了两件事：将 log 记录路由到 OTel 导出管道（发到跟 trace 同一个后端），以及自动给每条 log 记录加上当前 trace ID 和 span ID（来自环境的 `Activity`）。

自动注解才是让这种组合真正有用的东西。当你在 Grafana Tempo 里调查一个 trace 并想看到那个确切请求的详细 log 记录时，你用 trace ID 点一下就跳转到 Grafana Loki 里关联的 log 条目。不需要手动交叉引用。不需要 grep request ID 考古。

对于已经在用 Serilog 的团队，两者可以高效共存。Serilog 有丰富得多的 sink 生态——文件轮转、Seq、Elasticsearch、Slack 等等。OpenTelemetry 的 log 导出聚焦在 OTLP 管道。你可以让 `ILogger` 输出同时走两条路：Serilog 处理它配置的 sink，OTel 处理 OTLP 导出和 trace ID 注解。`builder.Logging.AddOpenTelemetry(...)` 调用 hook 进 `ILogger`，所以任何通过 `ILogger<T>` 写入的 log 记录同时流过两条管道——Serilog 拿到后做 sink 路由，OTel 拿到后做后端导出和 trace 关联。

如果你从头建一个新系统，且主要观测后端支持 OTLP，单用 OpenTelemetry 是稳妥选择。如果你已有 Serilog 配置且 sink 有实际价值，在它旁边加 OTel 就能增加分布式追踪和 metrics，而不打乱你的 log 路由。

## ASP.NET Core 自动集成覆盖了什么

`AddAspNetCoreInstrumentation()` hook 进 ASP.NET Core 中间件管道，自动为每个入站 HTTP 请求创建 span。每个 span 捕获 HTTP 方法、匹配到的路由模板（不是原始 URL——这是刻意的，避免 URL 参数造成基数爆炸）、响应状态码、任何逃出管道的异常、以及完整的请求耗时。

它还会自动读取入站 W3C `traceparent` 头并建立父上下文。结合 `AddHttpClientInstrumentation()` 用于出站调用，你不用在 controller 里写一行 span 创建的代码，就能获得 HTTP 服务通信的端到端分布式追踪。

## Exporters：把遥测送到你的后端

Exporter 负责序列化遥测并把它们从进程内送出到存储和可视化后端。OpenTelemetry .NET 提供几种选择，覆盖从开发到生产的不同阶段。

- **Console exporter**——写到 stdout。只适合本地开发和初始配置验证，不要用于生产。
- **OTLP exporter**——生产标准。通过 OTLP（gRPC 或 HTTP/protobuf）发送遥测到任何兼容后端。几乎所有现代观测平台都支持 OTLP：Jaeger、Grafana Tempo、Grafana Loki、Seq、Honeycomb 等等。通过 `OTEL_EXPORTER_OTLP_ENDPOINT` 环境变量配置端点，不同环境切换很方便。
- **Prometheus exporter**（仅 metrics）——暴露一个 `/metrics` scrape 端点，Prometheus 按配置的时间间隔轮询。如果你已经有 Prometheus 基础设施且不想引入 OTel collector，这是正确选项。
- **Azure Monitor exporter**——`Azure.Monitor.OpenTelemetry.AspNetCore` 用一个包引用、一行配置就把三信号全导出到 Application Insights。是 Azure 部署团队的推荐路径。

下面是使用 OTLP 且基于环境配置的生产就绪 setup：

```csharp
// Production setup with OTLP and environment-based config
builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService(
            serviceName: builder.Configuration["Otel:ServiceName"] ?? "MyApp",
            serviceVersion: builder.Configuration["Otel:ServiceVersion"] ?? "1.0.0")
        .AddAttributes(new Dictionary<string, object>
        {
            ["deployment.environment"] = builder.Environment.EnvironmentName
        }))
    .WithTracing(tracing => tracing
        .AddSource("MyApp.*")
        .AddAspNetCoreInstrumentation(o =>
        {
            o.Filter = ctx => !ctx.Request.Path.StartsWithSegments("/health");
        })
        .AddHttpClientInstrumentation()
        .AddOtlpExporter())
    .WithMetrics(metrics => metrics
        .AddMeter("MyApp.*")
        .AddAspNetCoreInstrumentation()
        .AddRuntimeInstrumentation()
        .AddOtlpExporter());

builder.Logging.AddOpenTelemetry(logging =>
{
    logging.IncludeFormattedMessage = true;
    logging.IncludeScopes = true;
    logging.AddOtlpExporter();
});
```

tracing 配置中的健康检查过滤器（`o.Filter = ctx => !ctx.Request.Path.StartsWithSegments("/health")`）值得强调。健康检查端点通常被负载均衡器和编排器每隔几秒就调用一次，从 tracing 角度看几乎没价值，反而在 trace 后端里制造了显著噪音。过滤掉它们能减少存储成本，让你的 trace 聚焦在实际业务操作上。

`AddRuntimeInstrumentation()` 给 metrics 增加了一组有价值的 .NET 运行时健康指标：GC 暂停时长、堆代大小、线程池队列深度、锁争用和异常率。这些让你能观察运行时本身的健康状况，而不只是应用逻辑。内存泄漏、线程池耗尽和 GC 压力往往在表现为延迟或错误之前，就首先出现在这些指标里。

## 分布式追踪与多服务关联

OpenTelemetry .NET 使用 W3C Trace Context 标准进行分布式追踪。当配置了 `AddHttpClientInstrumentation()`，每个出站 HTTP 请求自动注入 `traceparent` 头。当下游服务配置了 `AddAspNetCoreInstrumentation()`，入站 `traceparent` 头被自动读取并用作该请求根 span 的父上下文。

结果是：一个单一的 trace ID 串联起调用链中跨所有服务的 span。在你的观测后端里，你看到完整的调用树——Service A 调用 Service B 调用 Service C——作为一个统一时间轴，每次跳转之间的网络延迟都清晰可见。

对于不使用 HTTP 的服务通信——消息队列、gRPC stream、自定义协议——上下文传播需要用 `Propagators.DefaultTextMapPropagator` 手动调用 `Inject` 和 `Extract`。这在不是所有服务交互都是同步 HTTP 调用的架构中尤其相关。

同样的分布式追踪机制在模块化单体架构中同样有效。在单体里，上下文通过内存中的 `Activity` 状态流动，而不是 HTTP 头，但 trace 树结构完全一样。当你从单体迁移到微服务时，OTel instrumentation 原封不动地延续——你只是看到之前在进程内的调用现在变成了网络跳转。

## OpenTelemetry .NET vs Serilog：什么时候用哪个

已经跑 Serilog 的团队常问：「如果我已经 log 一切了，还需要 OpenTelemetry 吗？」

它们服务的是不同的目的。

| 能力 | OpenTelemetry .NET | Serilog |
|---|---|---|
| 分布式追踪 | ✓ 内建 | ✗ 不可用 |
| Metrics 聚合 | ✓ 内建 | ✗ 不可用 |
| 结构化日志 | ✓ 通过 ILogger | ✓ 原生 |
| Log 路由 sink | Console、OTLP | 30+ sink（文件、Seq、Elasticsearch 等） |
| 厂商中立传输 | ✓ OTLP 标准 | ✗ 每个 sink 专用 |
| Trace-log 关联 | ✓ 通过 trace ID 自动 | 手动（需要单独的 tracing 库） |

Serilog 是一个结构化日志库，有丰富的输出 sink 生态：文件、数据库、Seq、Elasticsearch、Splunk、Slack 等等。如果你的主要观测需求是有灵活目标和格式的结构化日志路由，Serilog 很出色。它不提供分布式追踪或 metrics。

OpenTelemetry 提供跨三信号的统一遥测和厂商中立传输。它在分布式追踪和 metrics 聚合方面很强。它的 logging 集成稳定但不如 Serilog 的 sink 生态那么丰富。

**两者一起用**是合理的生产配置。Serilog 处理丰富的 log sink 路由和格式化。OpenTelemetry 收集 `ILogger` 输出来做 OTLP 导出和 trace ID 注解。任何通过 `ILogger<T>` 写入的 log 记录同时流过两条管道。

## 生产落地路线图

OpenTelemetry .NET 上生产的实际路径是迭代式的：

1. **本地先用 Console exporter。** 加上前面展示的 quick-start 配置，跑起你的应用。确认正常请求的控制台里能看到 trace 和 metric 输出。这验证了你的 instrumentation 连线正确，然后再引入真实后端。
2. **给关键业务操作加自定义 span。** 找出应用里最重要的 3-5 个工作流，给它们加 `ActivitySource` span。不要早期就过度 instrumentation——聚焦在那些理解时序和参数确实有助于排查问题的操作上。
3. **预发布环境切换到 OTLP。** 用 Docker Compose 跑一套 Grafana 栈（Tempo + Loki + Prometheus），或者用托管的 OTel 后端的免费 tier（Honeycomb 或 Grafana Cloud）。验证你的 trace 端到端出现，包括多服务的分布式 trace。
4. **为你的 SLO 添加 metrics。** 定义你的服务等级目标——请求率、错误率、延迟百分位数——然后创建具体追踪这些目标的 metric instrument。基于这些 metrics 搭建看板和告警。
5. **用 ParentBasedSampler 上生产。** Trace 采样从 10-20% 起步。要确保错误 trace 始终被捕获，可以考虑定制 sampler 在检测到错误时返回 `RecordAndSample`，或者在 OTel Collector 里使用 tail-based sampling——根据 trace 结果做事后采样决策。

OTel SDK 的配置模型完全是基于代码的，这意味着你可以用环境变量和 `IConfiguration` 来驱动 exporter 端点、采样率和服务名——不同环境之间不需要代码变更。

## 常见问题

### OpenTelemetry .NET 和传统 logging 有什么区别？

OpenTelemetry .NET 是一个以统一、厂商中立格式收集 trace、metric、log 的可观测 SDK。传统 logging 库聚焦于 log 记录。OTel 增加了分布式 trace（可视化跨服务的请求流和延迟）和 metrics（聚合健康监控），并自动通过 trace ID 关联三种信号。关键实际区别：OTel 不仅能展示 log 了什么，还能展示一次请求跨多个服务执行的完整结构和时序——这是纯日志文件做不到的。

### 已经在用 Application Insights，还需要 OpenTelemetry 吗？

如果你在 Azure 上且目前直接使用 Application Insights SDK，迁移到 OpenTelemetry 越来越是推荐路径。微软一直在基于 OTel instrumentation 构建 Application Insights，`Azure.Monitor.OpenTelemetry.AspNetCore` 包把基于 OTel 的遥测导出到 Application Insights，观测后端不变。好处是可移植性：你的 instrumentation 代码兼容任何 OTel 兼容后端，将来如果需要增加第二个后端或切换提供商时更灵活。

### OpenTelemetry .NET 对应用性能有什么影响？

OTel SDK 的设计目标是尽量降低开销。当采样配置了（比如 10% trace 采样），未采样的请求只产生 `Activity` null 检查的小量分配开销。被采样的请求有可测量但通常很小的开销，来自 span 创建、标签附加和导出队列写入。Metrics 是最便宜的信号——它们在进程内聚合，导出成本被大量测量分摊。大多数 Web API 工作负载下，中等采样率时 OTel 开销远低于每请求 1ms。如果你对性能特别敏感，请对你的具体工作负载做基准测试。

### OpenTelemetry 能用在模块化单体里，还是只能用于微服务？

OpenTelemetry 在任何 .NET 应用中都运行良好，包括模块化单体。在单体里，所有模块运行在同一进程内，span 上下文通过内存中的 `Activity` 状态流动——不涉及 HTTP 头。你仍然能得到展示请求如何流经模块、时间花在哪里、错误从哪产生的完整 trace 树。当最终走向微服务时，OTel instrumentation 原封不动地延续。原来在内存中链接的 span 变成通过 `traceparent` 头在 HTTP 上链接，但在后端里 trace 结构看起来一样。

### 生产环境 .NET 应用该用什么 exporter？

大多数生产 setup 下，推荐通过 `OpenTelemetry.Exporter.OpenTelemetryProtocol` 使用 OTLP。几乎所有现代观测后端都支持它，且给你不修改应用代码就能切换后端的灵活性。如果在 Azure 上，`Azure.Monitor.OpenTelemetry.AspNetCore` 提供了更简单的 Application Insights 单调用集成。如果你有已有 Prometheus 基础设施，Prometheus exporter 为 metrics 增加了 scrape 端点。本地开发阶段，Console exporter 是验证 instrumentation 的最快方式。

### Trace、Metrics、Logs 在 OpenTelemetry 中有什么区别？

Trace 捕获单个请求的结构和时序——展示发生了什么、按什么顺序、每步花了多长时间。它们是延迟分析和特定故障根因排查的正确工具。Metrics 捕获跨时间的聚合测量——请求计数、错误率、耗时分布——是看板、SLO 监控和规模化告警的正确工具。Logs 捕获带完整上下文的、离散的时间点事件。三者都由 OTel SDK 采集，并且在配置到一起时，log 记录自动打上 trace ID，让你能够在后端中在 trace 和关联 log 条目之间直接导航。

## 参考

- [OpenTelemetry in .NET: Complete Observability Guide — Dev Leader](https://www.devleader.ca/2026/07/25/opentelemetry-in-net-complete-observability-guide)
- [OpenTelemetry 官方文档](https://opentelemetry.io/docs/languages/net/)
- [Logging in .NET 指南 — Dev Leader](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
- [Serilog in .NET 指南 — Dev Leader](https://www.devleader.ca/2026/07/05/serilog-in-net-complete-guide-to-structured-logging)
- [ASP.NET Core Web API 完整指南 — Dev Leader](https://www.devleader.ca/2026/05/30/aspnet-core-web-api-in-net-the-complete-guide)

如果你关注 .NET 开发、可观测性实践和 AI 辅助编程，可以关注 **Aide Hub**。这里会继续分享能落地的技术教程、工具评测和架构实践。
