---
pubDatetime: 2026-07-27T08:12:28+08:00
title: "OpenTelemetry Traces .NET：ActivitySource、Span 与追踪管线"
description: "深入理解 OpenTelemetry Traces 在 .NET 中的实现：从 ActivitySource/Activity 的 span 创建、Tags/Events/Exception 的上下文增强，到 W3C traceparent 跨服务传播和 OTel tracing pipeline 配置。包含 OrderService → InventoryService 的完整分布式追踪示例，以及常见坑点和测试方法。"
tags: ["OpenTelemetry", ".NET", "Tracing", "ActivitySource", "ASP.NET Core", "Distributed Tracing", "Observability"]
slug: "opentelemetry-traces-dotnet-activitysource-spans-pipeline"
ogImage: "../../assets/970/01-cover.png"
source: "https://www.devleader.ca/2026/07/26/opentelemetry-traces-net-activitysource-spans-and-the-tracing-pipeline"
---

如果你曾盯着日志试图拼出一个跨多个服务的慢请求的完整路径，你就已经知道分布式追踪在 .NET 应用中的价值了。设置 OpenTelemetry Traces 能给你纯日志无法提供的可见性——不仅知道「发生了什么」，还知道「在哪里发生」「什么时候发生」以及「每步花了多长时间」。这篇文章完整讲解：Trace 和 Span 到底是什么、.NET 如何通过 `System.Diagnostics.Activity` 原生实现它们、以及怎样把 OpenTelemetry tracing pipeline 搭起来，让数据真正流到你能查询的后端。

Tracing 是可观测性三大支柱之一（另外两个是 Metrics 和 Logs）。它是给你一棵调用树的信号——让你以结构化视图看到一次请求穿过系统的完整旅程。下面从第一性原理出发，一路走到可运行的端到端示例。

## Trace 与 Span 是什么

一个 **trace** 代表一次请求穿越系统的完整旅程。每个 trace 有一个全局唯一的 **trace ID**——一个 128 位随机值，连接该请求触发的所有工作，不管跨了多少个服务或进程。

在 trace 内部，工作被组织为 **span**。每个 span 代表一个工作单元：处理一个 HTTP 请求、执行一条数据库查询、调用一个外部 API、发布一条消息。一个 span 有一个 **span ID**、一个开始时间戳、一个结束时间戳和一个状态。它可能还有一个 **parent span ID**，正是这个字段创建了你在 Jaeger 或 Honeycomb 的瀑布视图中看到的父子嵌套关系。

一个典型的 trace 可能长这样：

- **Root span**：`HTTP POST /orders`（总耗时 50ms）
- **Child span**：`ValidateOrder`（5ms）
- **Child span**：`INSERT orders`（12ms）
- **Child span**：`HTTP POST notification-service/send`（28ms）

Root span 在请求到达你的服务时启动。每项子操作为自己创建工作 span。当所有子 span 完成、root span 结束时，完整的 trace 在你的观测后端拼装出来。

**W3C Trace Context** 是跨服务边界传递这个上下文的标准。两个 HTTP 头——`traceparent` 和 `tracestate`——编码了 trace ID、parent span ID 和 trace flags。当你的服务发出一个带这些头的出站 HTTP 调用时，下游服务读到这些头之后，会把自己的 span 创建为发出调用的那个 span 的 child。这就是分布式追踪之所以“分布式”的关键。

## .NET 如何实现 Tracing：System.Diagnostics.Activity

有一个让很多 .NET 开发者惊讶的事实是：你不需要 OpenTelemetry SDK 也能**创建** trace 数据。`Activity` 从 .NET Core 2.0 起就在 `System.Diagnostics` 里了。`ActivitySource`——创建 `Activity` 实例的工厂，配合 OpenTelemetry 可以 hook 进去的 listener 架构——从 .NET 5 起引入。

`Activity` 是 .NET 对 span 的表示。`ActivitySource` 是创建 `Activity` 实例的工厂。OpenTelemetry 并不替换这些类型——它**监听**它们。当 SDK 配置好后，它 hook 进 `ActivitySource` 并导出捕获到的数据。

这种分离是刻意的。如果你用 `ActivitySource` 来给一个类库做 instrumentation，宿主应用可以选择接入 OpenTelemetry（或任何其他 listener），不用改你的库代码。依赖倒置原则在这里起作用：你的库依赖的是一个抽象（`ActivitySource`），不是一个具体的 exporter。

`ActivitySource` 通常是所属类的一个静态字段：

```csharp
using System.Diagnostics;

namespace MyApp.Services;

public class OrderService
{
    // One ActivitySource per component -- static, named, versioned
    private static readonly ActivitySource _activitySource =
        new("MyApp.OrderService", "1.0.0");

    public async Task<Order> ProcessOrderAsync(int orderId)
    {
        // StartActivity returns Activity? -- null when no listener is registered
        using var activity = _activitySource.StartActivity("ProcessOrder");
        activity?.SetTag("order.id", orderId);

        // ... business logic ...

        return await GetOrderAsync(orderId);
    }
}
```

几个关键细节：source 是 **static** 的——每个组件建一个，不是每个请求或每次方法调用建一个。你选择的名字是之后在 SDK 中注册时用的标识符。`StartActivity` 返回 `Activity?`，因为如果没有 listener 注册，它返回 `null` 且开销近乎为零。空条件操作符 `?.` 优雅地处理这种情况。`using` 声明确保 activity 在方法返回时被释放（并结束）——即使抛了异常也一样，释放行为会记录结束时间戳。

## 搭建 OpenTelemetry Traces .NET 管线

要让 trace 数据真正流到某个地方，你需要通过 OpenTelemetry SDK 注册一个 listener。首先在项目里添加这些 NuGet 包：

```xml
<PackageReference Include="OpenTelemetry" Version="1.9.0" />
<PackageReference Include="OpenTelemetry.Extensions.Hosting" Version="1.9.0" />
<PackageReference Include="OpenTelemetry.Instrumentation.AspNetCore" Version="1.9.0" />
<PackageReference Include="OpenTelemetry.Exporter.Console" Version="1.9.0" />
```

然后在 `Program.cs` 里配置管线：

```csharp
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService(
            serviceName: "MyApp",
            serviceVersion: "1.0.0"))
    .WithTracing(tracing => tracing
        .AddSource("MyApp.OrderService")      // register your ActivitySource
        .AddAspNetCoreInstrumentation()        // auto-instrument incoming HTTP
        .AddHttpClientInstrumentation()        // auto-instrument outgoing HTTP
        .AddConsoleExporter());                // swap for AddOtlpExporter() in production

var app = builder.Build();
// ... rest of startup
```

`AddSource("MyApp.OrderService")` 调用激活了你的 `ActivitySource`。没有它，每次 `StartActivity()` 都返回 `null`，没有任何 span 被捕获。名字必须跟你在 `ActivitySource` 构造函数里传的字符串完全一致。

`ConfigureResource` 配合 `AddService` 在所有导出 span 上设置 `service.name` 属性——你的观测后端靠它知道是**哪个**服务产生了这条 trace。缺少这个是最常见的坑之一：没有 service name 的 trace 很难过滤和查询。

## 自动 Instrumentation vs 手动 Instrumentation

OpenTelemetry for .NET 提供了两种互补的 span 创建方式，理解什么时候用哪种很重要。

**自动 instrumentation** 意味着 SDK 自动为常见操作用成 span，不需要你写任何 tracing 代码：

- `AddAspNetCoreInstrumentation()` 为每个入站 HTTP 请求创建 span，填充路由、方法和状态码
- `AddHttpClientInstrumentation()` 为每次 `HttpClient` 调用创建 span，并自动注入 W3C trace context 头
- `AddSqlClientInstrumentation()` 捕获数据库查询 span
- `AddEntityFrameworkCoreInstrumentation()` 包装 EF Core 查询

这些 span 告诉你系统的边界发生了什么——入站请求、出站请求、数据库调用。你免费获得它们。

**手动 instrumentation** 意味着你在自己的业务逻辑里显式创建 span。用于 SDK 看不到的操作：处理一个批处理、执行一个业务规则、跑一个后台任务、调用一个内部服务层。这就是 `ActivitySource.StartActivity()` 的用武之地。

两种方式可以干净地叠加。一个 trace 可能有来自 `AddAspNetCoreInstrumentation` 的自动 root span，然后是你手动在服务层内部创建的子 span。自动 span 处理 HTTP 边界；你的手动 span 解释内部发生了什么。生产环境里 OpenTelemetry traces .NET 服务实际看起来就是这种组合。

## 创建父子 Span：Tags、Events 与 Exception

有用的 trace 不只是创建 span——还要用上下文来充实它们。下面是一个更完整的示例，展示了 tags、events 和异常记录：

```csharp
public async Task<bool> ValidateAndChargeAsync(
    int orderId, decimal amount)
{
    using var activity = _activitySource.StartActivity(
        "ValidateAndCharge",
        ActivityKind.Internal);

    activity?.SetTag("order.id", orderId);
    activity?.SetTag("charge.amount", amount);

    try
    {
        // ValidateOrder becomes a child span automatically
        // -- Activity.Current flows through async/await
        using var validateActivity =
            _activitySource.StartActivity("ValidateOrder");
        var isValid = await ValidateOrderAsync(orderId);

        if (!isValid)
        {
            activity?.SetStatus(ActivityStatusCode.Error,
                "Order validation failed");
            return false;
        }

        activity?.AddEvent(new ActivityEvent("ValidationPassed"));

        using var chargeActivity =
            _activitySource.StartActivity("ChargeCustomer");
        chargeActivity?.SetTag("payment.provider", "Stripe");
        await ChargeAsync(amount);

        activity?.SetStatus(ActivityStatusCode.Ok);
        return true;
    }
    catch (Exception ex)
    {
        activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
        activity?.RecordException(ex);
        // records type, message, and stack trace
        throw;
    }
}
```

`ValidateOrder` 和 `ChargeCustomer` 是 `ValidateAndCharge` 的子 span，因为创建它们时 `Activity.Current` 已经被设为父 span。这通过 `AsyncLocal<T>` 自动跨越 async/await 流动——你不需要把 activity 作为方法参数传递。

**Tags**（属性）是操作的键值描述符。尽量使用 OpenTelemetry 语义约定，如 `http.method`、`db.system`、`messaging.system`——这让你的数据兼容标准看板和告警规则。

**Events** 是带时间戳的注解，标记 span **期间**发生的某事，区别于 span 自身的元数据。适用于重试尝试、缓存命中、进度里程碑。

**`RecordException`** 把异常作为结构化事件加入，含类型、消息和堆栈。配合 `SetStatus(Error)`，这让 span 浮现在错误率视图里，并让异常在你的后端里可查询。

## 完整跨服务追踪示例

下面展示 trace span 如何通过 `HttpClient` 跨越服务边界，配合 W3C context propagation：

```csharp
// OrderService -- the upstream caller
public class OrderService
{
    private static readonly ActivitySource _activitySource =
        new("MyApp.OrderService", "1.0.0");

    private readonly HttpClient _httpClient;

    public OrderService(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<OrderResult> PlaceOrderAsync(OrderRequest request)
    {
        using var activity = _activitySource.StartActivity(
            "PlaceOrder", ActivityKind.Internal);

        activity?.SetTag("order.customer_id", request.CustomerId);
        activity?.SetTag("order.item_count", request.Items.Count);

        try
        {
            // HttpClientInstrumentation auto-injects traceparent header here
            // The downstream service reads it, creates child spans under this trace
            var response = await _httpClient.PostAsJsonAsync(
                "/api/inventory/reserve", request.Items);

            response.EnsureSuccessStatusCode();

            activity?.SetTag("inventory.reserved", true);
            activity?.SetStatus(ActivityStatusCode.Ok);

            return new OrderResult(Success: true);
        }
        catch (HttpRequestException ex)
        {
            activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
            activity?.RecordException(ex);
            throw;
        }
    }
}

// InventoryService -- the downstream receiver
// Program.cs for InventoryService:
builder.Services.AddOpenTelemetry()
    .ConfigureResource(r => r.AddService("MyApp.Inventory", "1.0.0"))
    .WithTracing(t => t
        .AddSource("MyApp.InventoryService")
        .AddAspNetCoreInstrumentation()
        // reads traceparent header, creates child span
        .AddOtlpExporter());
```

当 `OrderService` 发起 HTTP 调用时，`AddHttpClientInstrumentation` 把 `traceparent` 注入请求头。当 `InventoryService` 收到请求，`AddAspNetCoreInstrumentation` 读取这些头，把入站 span 创建为远程父 span 的 child。两个服务发出的是**同一个 trace ID** 的 span——它们在观测后端里显示为一条连通的 trace。

## 常见坑点

团队在给 .NET 应用加 OpenTelemetry traces 时会反复踩的几个坑：

**不释放 Activity。** 如果你用 `StartActivity()` 创建了 `Activity` 但从不释放它，span 永远不会结束。你的 trace 里会有一个永远不会出现在后端里的鬼影 open span。修复方式始终是 `using` 声明或显式 `Dispose()` 调用——即使在 error path 上也要执行。上面例子里的 `try/catch` 是刻意的——`using` 包裹整个块。

**缺少 `service.name`。** 没有 `ConfigureResource(r => r.AddService(...))`，你的 span 导出时没有 service name 属性。大多数观测后端会接受它们，但按服务过滤变得不可能，UI 通常显示为未命名或未知服务。当 trace 在后端里看起来不对劲时，这是第一件要排查的事。

**忘记 `AddSource()`。** 如果 `StartActivity()` 在生产环境总是返回 `null` 但在测试里正常工作，检查你的 source 名是否注册了。`AddSource()` 里的 source 名必须跟传给 `new ActivitySource(...)` 的字符串**完全一致**——大小写敏感。

**采样盲区。** SDK 默认使用 `ParentBased` sampler，依从入站 trace context。在开发环境这通常没问题。生产环境高流量时，你通常需要 head-based sampling 来减少数据量。如果采样太激进，你会丢失罕见事件的 trace。在上生产前务必弄明白你的采样配置。

**过度 instrumentation。** 在每一个私有方法上加手动 span 制造的是噪音而非信号。Span 应该代表有实际时长和上下文的操作。一个在微秒以下跑完的三行辅助方法不需要 span。

## 将 Trace 与 Log 关联

Tracing 跟结构化日志关联在一起后才真正发挥威力。现代 .NET logging 自动跟当前 trace 关联——使用 OpenTelemetry logging 集成时，`Activity.Current` 的 `TraceId` 和 `SpanId` 被注入到每个 log scope 里。

如果你用 Serilog enrichers，可以自动给每个 log 条目打上当前 trace 和 span ID。在观测后端里，你可以从一条 log 条目跳转到对应的 trace span，看到完整的请求上下文——这正是把 log 调试从猜测变成导航的那种关联。

类似地，ASP.NET Core middleware 可以用请求级上下文来增强当前 span——用户 ID、租户 ID、关联头——这样请求里的每个子 span 都继承那些上下文。middleware 增强 `Activity.Current`，然后这些数据就出现在所有下游 span 里，不需要改任何业务逻辑。

## 如何测试 Trace 是否正确

你可以在单元测试和集成测试里用 `ActivityListener` 捕获 activity，不需要跑任何 OpenTelemetry 基础设施：

```csharp
var recorded = new List<Activity>();
var listener = new ActivityListener
{
    ShouldListenTo = src => src.Name == "MyApp.OrderService",
    Sample = (ref ActivityCreationOptions<ActivityContext> _) =>
        ActivitySamplingResult.AllData,
    ActivityStopped = a => recorded.Add(a)
};
ActivitySource.AddActivityListener(listener);

// Run your code, then assert on `recorded`
```

这是验证 instrumentation 正确且不会静默回退的 solid pattern。Tag 名称和操作名称是你的可观测契约的一部分——去测它们。

## 常见问题

### Trace 和 Span 有什么区别？

Trace 是一次请求的完整画面——它触发的所有工作，跨所有服务和进程。Span 是那个 trace 内的单个工作单元。Trace 由 span 组成。每个 span 恰好属于一个 trace（通过 trace ID 标识），并且可以有一个嵌套在它下面的父 span。

### 为什么 ActivitySource.StartActivity() 返回 null？

`StartActivity()` 在没有 listener 订阅到该 source 时返回 `null`。这是设计如此——意味着未 instrument 的代码开销近乎为零。OpenTelemetry SDK 通过 `WithTracing()` 配置中的 `AddSource()` 订阅。如果你的 source 名跟你用 `AddSource()` 注册的不匹配，所有 `StartActivity()` 调用都静默返回 null。访问返回的 `Activity?` 时始终用空条件操作符（`?.`）。

### Activity.Current 如何通过 async/await 正确流动？

`Activity.Current` 的底层是 `AsyncLocal<Activity?>`，这意味着它在每次 `await` 边界被捕获，并在恢复时还原。当你 `await` 一个方法时，调用上下文——包括 `Activity.Current`——流进被调用方法。嵌套方法中创建的子 span 自动成为环境父 span 的 child，不需要任何参数传递。这正是 tracing 模型不侵入方法签名的原因。

### 什么时候用自动 instrumentation，什么时候用手动？

自动 instrumentation（通过 `AddAspNetCoreInstrumentation`、`AddHttpClientInstrumentation` 等）覆盖了服务边界处的系统级操作——入站请求、出站 HTTP 调用、数据库查询。在它覆盖的所有地方都用。手动 instrumentation 在服务**内部**增加上下文——业务操作、处理步骤、重要决策点。两者配合使用：自动 instrumentation 给你框架；手动 instrumentation 填充内部到底发生了什么。

### 如何在跨 HTTP 服务调用中传播 trace context？

`AddHttpClientInstrumentation()` 自动把 W3C Trace Context 头（`traceparent`、`tracestate`）注入出站 `HttpClient` 请求。下游服务的 `AddAspNetCoreInstrumentation()` 在入站请求中读取这些头，把该服务的 root span 创建为远程父 span 的 child。trace ID 在两个服务间共享，所以两个服务的 span 在你的后端里显示为一条连通的 trace。

### 应该用静态 ActivitySource 还是通过 DI 注入？

标准模式是每个组件用一个 `static readonly` 字段。`ActivitySource` 是轻量的，其标识是它的名字，不是它的实例。使用静态 source 的库代码不需要对 OpenTelemetry SDK 或应用 DI 容器有任何依赖。如果你需要 service name 或 version 在运行时来自配置，把 source 包装在一个注册到 DI 容器的小型 singleton 服务里。

## 总结

OpenTelemetry traces .NET 建立在一个干净的根基上。`System.Diagnostics.Activity` 和 `ActivitySource` 给你一个可移植、不依赖 SDK 的 tracing API。OpenTelemetry SDK 通过几行启动代码接入 listener 和 exporter。自动 instrumentation 处理系统边界；手动 instrumentation 填充业务逻辑。`Activity.Current` 的环境上下文模型也让 tracing 不侵入方法签名。

做好 OpenTelemetry traces .NET 的核心要点：每个组件一个 `static readonly ActivitySource`、对 `Activity?` 引用做 null 检查、用 `AddSource()` 注册 source、通过 `ConfigureResource` 设置 `service.name`、以及遵循语义约定命名你的 tag。有了这些基础，你的 trace 将真正有用——不管是排查一个慢请求、跨服务边界追踪错误、还是理解错误处理如何在你的分布式系统中传播。

从单个服务开始。导出到 Console。看到 span 出现。然后从那里向外扩展。

## 参考

- [OpenTelemetry Traces .NET — Dev Leader](https://www.devleader.ca/2026/07/26/opentelemetry-traces-net-activitysource-spans-and-the-tracing-pipeline)
- [OpenTelemetry in .NET: Complete Observability Guide — Dev Leader](https://www.devleader.ca/2026/07/25/opentelemetry-dotnet-complete-observability-guide)
- [OpenTelemetry 语义约定](https://opentelemetry.io/docs/specs/semconv/)
- [ASP.NET Core Web API 完整指南 — Dev Leader](https://www.devleader.ca/2026/05/30/aspnet-core-web-api-in-net-the-complete-guide)
- [Logging in .NET 指南 — Dev Leader](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)

如果你关注 .NET 开发、可观测性实践和 AI 辅助编程，可以关注 **Aide Hub**。这里会继续分享能落地的技术教程、工具评测和架构实践。
