---
pubDatetime: 2026-07-28T13:39:18+08:00
title: "OpenTelemetry Metrics .NET：从 Counter、Histogram 到 IMeterFactory"
description: "全面拆解 .NET 中 OpenTelemetry 指标埋点：System.Diagnostics.Metrics 原生 API、四种仪器类型（Counter/Histogram/Gauge/UpDownCounter）的适用场景，以及为什么应该用 IMeterFactory 而不是 new Meter()。附完整代码示例和 Prometheus/OTLP 导出配置。"
tags: ["OpenTelemetry", ".NET", "Metrics", "Observability", "CSharp"]
slug: "opentelemetry-metrics-dotnet-counters-histograms-imeterfactory"
ogImage: "../../assets/976/01-cover.png"
source: "https://www.devleader.ca/2026/07/27/opentelemetry-metrics-net-counters-histograms-and-imeterfactory/"
---

如果你已经在 .NET 项目里接入了 OpenTelemetry 的 tracing，知道怎么用 `ActivitySource` 追踪单次请求的完整链路，那下一步很自然就会面对一个问题：**怎么把「一段时间内的聚合数据」埋进去？** 比如每分钟处理了多少订单、P95 响应时间是多少、当前排队中的任务数量——这些问题的答案不在单次 trace 里，而在 metrics 里。

这篇文章基于 Nick Cosentino 在 Dev Leader 上的系统梳理，把 OpenTelemetry metrics in .NET 的核心概念和实操要点串一遍：从 `System.Diagnostics.Metrics` 原生 API 讲起，到四种仪器类型的选型判断，再到 `IMeterFactory` 的 DI 集成和 Prometheus / OTLP 导出配置。

## Metrics vs Traces vs Logs：先搞清楚各自干什么

在动手写代码之前，值得先把三个信号的分工理清楚，不然很容易把 metrics 当 logs 用。

- **Logs** 是离散事件：「某件事发生了，这是当时的上下文细节。」
- **Traces** 是请求级时间线：「这一次请求里，经过的所有服务、每一步花了多久。」
- **Metrics** 是聚合统计：「过去一分钟内，大量事件的数值摘要。」

一个请求延迟的 histogram 指标不会告诉你某次具体请求花了多少毫秒——它告诉你的是过去一分钟内所有请求的延迟分布。从分布里可以推 P50/P95/P99，这些才是 SLO 追踪需要的东西。单次 trace 回答「为什么这次慢」，metrics 回答「整体是不是变慢了」。

这也解释了为什么 metrics 能做全量采集而不需要采样：trace 采样 1% 会漏掉 99% 的请求，而 counter 在每次请求上 +1，一个都不会少。两者互补——metrics 负责告警和趋势，traces 负责排查。

再加上结构化日志（[Structured logging in .NET](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)），observability 三根支柱就齐了：logs 给叙述，metrics 给数字，traces 给时间线。

## System.Diagnostics.Metrics：.NET 原生的指标 API

和 tracing 有 `System.Diagnostics.Activity` 一样，metrics 的基础设施在 `System.Diagnostics.Metrics` 命名空间里。核心类是 `Meter`——它是创建各种指标仪器的工厂。OpenTelemetry 对这层 API 的包装方式和它对 `ActivitySource` 的包装方式一致：**你的代码只用原生类型，OpenTelemetry 负责监听和导出**。

这意味着一个用 `System.Diagnostics.Metrics` 做埋点的库不需要直接依赖 OpenTelemetry SDK。宿主应用可以选自己的可观测方案——OpenTelemetry、自定义 `MeterListener`、或其他任何东西——库本身不用改。

`Meter` 是你写代码的入口。你通过它创建四种仪器：counter、histogram、gauge、up-down counter。每种仪器都有名称、可选单位和可选描述。名称最终会出现在你的 dashboard 和告警规则里。

## 为什么要用 IMeterFactory 而不是 new Meter()

你完全可以直接 `new Meter("MyApp.Orders")`，但在应用代码里更推荐的方式是通过 DI 容器注入 `IMeterFactory`。这看起来只是个微小差异，实际有几个很实在的好处。

**可测试性**。注入 `IMeterFactory` 后，测试代码可以通过 `services.AddMetrics()` 注册真实实现，再用 `MeterListener` 观察指标值，不需要启动完整的 OpenTelemetry 管线。这和注入任何依赖而不是自己 new 的道理一样——解耦。

**生命周期管理**。`IMeterFactory` 管理它创建的 `Meter` 实例的生命周期。工厂在应用关闭时 dispose，它创建的所有 meter 也会随之清理，资源回收干净利落。

**一致性**。`IMeterFactory` 是 OpenTelemetry 管线的 `AddMeter()` 方法设计搭配的模式，完全融入 .NET 的 DI 生态。

> **注意**：`IMeterFactory` 在 .NET 8 中通过 `Microsoft.Extensions.Diagnostics` 引入。如果还在 .NET 6/7 上，可以直接 `new Meter(...)`，但会失去 DI 生命周期管理和可测试性优势。

这符合[依赖反转原则](https://www.devleader.ca/2026/06/15/dependency-inversion-principle-c-abstractions-over-concretions)——依赖 `IMeterFactory` 抽象，而不是 `Meter` 的具体构造函数。同样原则贯穿 [SOLID 设计指南](https://www.devleader.ca/2026/06/10/solid-principles-c-guide-complete-reference-for-net-10) 的所有部分。

下面是一个用 `IMeterFactory` 的完整示例：

```csharp
using System.Diagnostics.Metrics;

namespace MyApp.Services;

public class OrderMetrics : IDisposable
{
    private readonly Meter _meter;
    private readonly Counter<long> _ordersCreated;
    private readonly Histogram<double> _orderProcessingTime;
    private readonly ObservableGauge<int> _pendingOrders;
    private int _pendingOrderCount;

    public OrderMetrics(IMeterFactory meterFactory)
    {
        _meter = meterFactory.Create("MyApp.Orders");

        _ordersCreated = _meter.CreateCounter<long>(
            "orders.created",
            unit: "{orders}",
            description: "Total number of orders created");

        _orderProcessingTime = _meter.CreateHistogram<double>(
            "orders.processing_duration",
            unit: "ms",
            description: "Time to process an order in milliseconds");

        _pendingOrders = _meter.CreateObservableGauge<int>(
            "orders.pending",
            () => _pendingOrderCount,
            unit: "{orders}",
            description: "Current number of pending orders");
    }

    public void RecordOrderCreated(string region)
    {
        _ordersCreated.Add(1, new KeyValuePair<string, object?>(
            "region", region));
    }

    public void RecordProcessingTime(
        double milliseconds, bool success)
    {
        _orderProcessingTime.Record(milliseconds,
            new KeyValuePair<string, object?>(
                "success", success));
    }

    public void SetPendingOrderCount(int count) =>
        _pendingOrderCount = count;

    public void Dispose() => _meter.Dispose();
}
```

这个类封装了订单领域的所有指标仪器。它在 DI 中以 singleton 注册（因为指标仪器是长生命周期的有状态对象），对外暴露语义化方法而不是原始仪器。调用方不需要关心仪器类型——调用 `RecordOrderCreated()` 就行，剩下的由 `OrderMetrics` 处理。

## 四种仪器类型怎么选

OpenTelemetry metrics 提供了四种仪器类型，各有各的适用场景。选对了，dashboard 和告警才能回答你真正关心的问题。

### Counter：只增不减的累加器

`Counter<T>` 是单调递增的——只能往上走，`Add()` 只能传非负值。用来表达累积总量：已处理请求数、已创建订单数、错误次数、已发送消息数。

```csharp
_ordersCreated.Add(1, new KeyValuePair<string, object?>(
    "region", region));
```

每次调用都可以附加 tags（在 OpenTelemetry 术语中叫 attributes），按 region、status、HTTP method 等维度拆分。后端会把这些维度作为独立时间序列聚合，你可以在 dashboard 里按需筛选和分组。

**标签的黄金法则：只用低基数（low-cardinality）值。** 地区名、HTTP 状态码、布尔标志是好的标签值。用户 ID、订单 ID、请求 GUID 不是——它们会创建数百万条独立时间序列，拖垮你的 metrics 后端。

### Histogram：关心分布就用它

`Histogram<T>` 记录每次测量值并计算分布。每次调用 `Record()` 传入测量值。分布是 histogram 真正强大的地方——从分布中，后端可以在查询时计算任意百分位。

```csharp
public async Task<OrderResult> ProcessOrderAsync(Order order)
{
    var stopwatch = Stopwatch.StartNew();

    try
    {
        var result = await _orderProcessor.ProcessAsync(order);
        _metrics.RecordProcessingTime(
            stopwatch.Elapsed.TotalMilliseconds,
            success: result.IsSuccess);
        return result;
    }
    catch (Exception)
    {
        _metrics.RecordProcessingTime(
            stopwatch.Elapsed.TotalMilliseconds,
            success: false);
        throw;
    }
}
```

延迟、请求大小、处理时的队列深度——凡是你关心分布而非总量的地方，都用 histogram。用毫秒记录耗时然后查询 P95 延迟，比平均延迟更有 SLO 参考价值。平均值会掩盖一小部分极慢的请求，P95 和 P99 能把它们暴露出来。

代码里 `success` 标签的使用也很关键：你可以对比成功和失败请求的处理时间分布——这个维度能帮你定位故障发生在处理链路的哪个环节。

### ObservableGauge：按需读取的瞬时快照

`ObservableGauge<T>` 不记录单次测量值。它在 metrics 系统需要当前读数时调用一个回调函数。用于表达当前状态：队列深度、活跃连接数、缓存大小、线程池队列长度、内存使用量。

```csharp
_pendingOrders = _meter.CreateObservableGauge<int>(
    "orders.pending",
    () => _pendingOrderCount,
    unit: "{orders}",
    description: "Current number of pending orders");
```

回调由 metrics 管线在采集周期触发，不是每次请求触发。你的代码不推值，管线在需要时来拉。因此回调必须快且不阻塞——它应该读内存中的值（字段、缓存值、原子整数），而不是做数据库查询或 I/O。

Observable 仪器适合运行时健康指标：活跃连接、等待中的工作项、内存压力、缓存命中次数。不适合请求级的测量——那些交给 counter 和 histogram。

### UpDownCounter：可增可减的计数器

`UpDownCounter<T>` 像 counter 但可以双向变化。给 `Add()` 传正值递增，传负值递减。用于追踪当前进行中的数量：活跃请求、正在处理的项目、并发连接数。

```csharp
public class RequestTrackingMiddleware : IMiddleware
{
    private readonly UpDownCounter<long> _activeRequests;

    public RequestTrackingMiddleware(IMeterFactory meterFactory)
    {
        var meter = meterFactory.Create("MyApp.Http");
        _activeRequests = meter.CreateUpDownCounter<long>(
            "http.server.active_requests",
            unit: "{requests}",
            description: "Number of currently active HTTP requests");
    }

    public async Task InvokeAsync(
        HttpContext context, RequestDelegate next)
    {
        _activeRequests.Add(1,
            new KeyValuePair<string, object?>(
                "method", context.Request.Method));
        try
        {
            await next(context);
        }
        finally
        {
            _activeRequests.Add(-1,
                new KeyValuePair<string, object?>(
                    "method", context.Request.Method));
        }
    }
}
```

这个 [ASP.NET Core 中间件](https://www.devleader.ca/2026/06/07/aspnet-core-middleware-building-and-using-the-request-pipeline) 在请求到达时 +1，请求完成时 -1——放在 `finally` 块里确保异常和取消也正确处理。你随时可以看到当前有多少请求正在处理，还能按 HTTP method 维度拆分。

## 注册 OpenTelemetry Metrics 管线

定义好 `OrderMetrics` 类之后，还需要两件事：在 DI 中注册它，以及告诉 OpenTelemetry 去监听它的 meter。

```csharp
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<OrderMetrics>();

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService("MyApp", serviceVersion: "1.0.0"))
    .WithMetrics(metrics => metrics
        .AddMeter("MyApp.Orders")
        .AddAspNetCoreInstrumentation()
        .AddRuntimeInstrumentation()
        .AddPrometheusExporter()); // 或 AddOtlpExporter()

var app = builder.Build();
app.MapPrometheusScrapingEndpoint(); // 暴露 /metrics 端点
```

`AddMeter("MyApp.Orders")` 是最关键的注册调用。它告诉 OpenTelemetry 订阅所有同名 `Meter` 的测量值，不管这个 `Meter` 是怎么创建的。这和 tracing 里的 `AddSource()` 模式一样——每个 source 需要显式 opt-in。

`AddAspNetCoreInstrumentation()` 自动提供 HTTP 请求的指标：请求数、耗时、活跃请求数。`AddRuntimeInstrumentation()` 提供 GC 指标、线程池状态和内存压力——运行时健康指标应有尽有。光靠这两行，你已经拿到了一组很实用的基线指标，一行自定义代码都不用写。

### Prometheus vs OTLP

- `AddPrometheusExporter()` + `MapPrometheusScrapingEndpoint()` 暴露 `/metrics` 端点，Prometheus 按配置间隔来拉。这是 pull 模式，适合已经跑了 Prometheus 的场景。
- `AddOtlpExporter()` 在配置的推送间隔内向 OTLP 接收端（OpenTelemetry Collector、Grafana Agent 等）推送指标。这是 push 模式，更通用——OTLP 是 OpenTelemetry 标准协议，大多数现代后端直接支持。

你也可以同时用两个 exporter，SDK 会独立地向所有注册的导出器扇出数据。

## 指标命名规范

OpenTelemetry 为仪器名称定义了语义约定（semantic conventions）。遵循这些约定能让你的指标兼容社区的 dashboard 和告警规则。约定使用小写、点分隔的名称：

- `http.server.request.duration`——HTTP 服务端请求延迟 histogram
- `http.server.active_requests`——活跃请求 up-down counter
- `db.client.operation.duration`——数据库操作延迟 histogram
- `messaging.publish.duration`——消息发布延迟 histogram

自定义应用指标用服务名做前缀：`myapp.orders.created`、`myapp.payments.processing_duration`、`myapp.cache.hit_ratio`。

`unit` 参数遵循 UCUM（Unified Code for Units of Measure）标准：`ms` 表示毫秒，`s` 表示秒，`By` 表示字节，`{requests}` 或 `{orders}` 表示无量纲的命名事物计数。单位写对，工具才能正确格式化数值，团队看 dashboard 时也不用猜数字的量级。

## 用 IMeterFactory 测试指标

`IMeterFactory` 相对于 `new Meter()` 的一个具体好处是可测试。你不需要跑一个完整的 OpenTelemetry 管线就能验证指标类是否记录了正确的值。

```csharp
[Fact]
public void RecordOrderCreated_IncrementsCounter()
{
    var services = new ServiceCollection();
    services.AddMetrics(); // 注册 IMeterFactory
    services.AddSingleton<OrderMetrics>();

    var provider = services.BuildServiceProvider();
    var metrics = provider.GetRequiredService<OrderMetrics>();

    metrics.RecordOrderCreated("us-east");

    // IMeterFactory 创建的指标可通过 MeterListener 观察
    // 关键好处：你可以验证指标值而不耦合到特定 exporter
}
```

要想完整断言记录的值，可以搭配 `MeterListener` 在测试中订阅测量值。这让你能验证「某个仪器以正确的值和正确的标签发出了数据」，而不需要导出到任何后端。在[集成测试](https://www.devleader.ca/2026/06/08/testing-aspnet-core-web-api-webapplicationfactory-and-integration-tests)中尤其有价值——你不仅要确认功能正确，还要确认功能对应的指标确实被触发了。

`IMeterFactory` 的方式还意味着你可以在每个测试中创建独立指标实例，不会因为 `static` meter 的全局状态导致测试套件间的状态泄漏。

## 性能考量

对埋点开销的担心很常见。`System.Diagnostics.Metrics` API 的设计本身就是低开销的。当没有 listener 订阅某个 meter 时，`Add()` 和 `Record()` 调用的成本接近为零——运行时会检测到没有监听者并走短路路径。即使有 listener 活跃，counter 和 histogram 的热路径也精心避免了不必要的内存分配。

Histogram 的标签基数（cardinality）是最容易踩的性能坑。每组唯一的标签值组合都会在后端创建一条独立时间序列。把标签基数控制在低水平——用有界集合的分类标签，不要用每次请求都不同的标识符。

## 四种仪器速查表

| 仪器类型             | 方向     | 典型场景                 | 记录方式         |
| -------------------- | -------- | ------------------------ | ---------------- |
| `Counter<T>`         | 只增     | 请求总数、错误数、消息数 | `Add(非负值)`    |
| `Histogram<T>`       | 测量分布 | 延迟、请求大小、队列时间 | `Record(测量值)` |
| `ObservableGauge<T>` | 瞬时快照 | 队列深度、活跃连接、内存 | 回调函数返回     |
| `UpDownCounter<T>`   | 可增可减 | 进行中请求、并发操作     | `Add(正/负值)`   |

## 从哪里开始

不要一上来就把所有业务逻辑都埋上指标。现实的做法分三步：

1. **先跑基线**：加上 `AddRuntimeInstrumentation()` 和 `AddAspNetCoreInstrumentation()`，零自定义代码拿到 GC、线程池、HTTP 请求指标。
2. **再埋关键业务**：找到最关心的几个业务指标——订单量、支付延迟、用户注册——用 counter 和 histogram 埋进去。
3. **逐步补全**：随着对系统行为的理解加深，逐步添加 observable gauge 做健康监控，up-down counter 做并发追踪。

指标最有价值的时候，反映的是你的业务领域——订单、支付、用户、消息——而不仅仅是底层技术基础设施。

---

如果你关注 .NET 开发、可观测性实践和软件工程工具，可以关注 **Aide Hub**。这里会继续分享能落地的技术教程、工具评测和项目经验。

## 参考

- [OpenTelemetry Metrics .NET: Counters, Histograms, and IMeterFactory — Dev Leader](https://www.devleader.ca/2026/07/27/opentelemetry-metrics-net-counters-histograms-and-imeterfactory/)
- [OpenTelemetry in .NET: Complete Observability Guide](https://www.devleader.ca/2026/07/25/opentelemetry-dotnet-complete-observability-guide)
- [Structured Logging in .NET](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
- [Dependency Inversion Principle in C#](https://www.devleader.ca/2026/06/15/dependency-inversion-principle-c-abstractions-over-concretions)
- [SOLID Principles in C#](https://www.devleader.ca/2026/06/10/solid-principles-c-guide-complete-reference-for-net-10)
- [ASP.NET Core Middleware](https://www.devleader.ca/2026/06/07/aspnet-core-middleware-building-and-using-the-request-pipeline)
- [Testing ASP.NET Core with WebApplicationFactory](https://www.devleader.ca/2026/06/08/testing-aspnet-core-web-api-webapplicationfactory-and-integration-tests)
