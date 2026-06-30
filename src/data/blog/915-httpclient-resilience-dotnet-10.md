---
pubDatetime: 2026-06-30T12:06:42+08:00
title: "HttpClient 弹性策略：.NET 10 中的超时、重试与断路器"
description: "用 Microsoft.Extensions.Http.Resilience 一行代码给 HttpClient 加上重试、断路器、对冲和分层超时。对比 Polly 手写时代与现代表配式弹性管道，覆盖自定义配置、可观测性和生产级完整示例。"
tags: ["CSharp", ".NET", "HttpClient", "Resilience", "Polly"]
slug: "httpclient-resilience-dotnet-10"
ogImage: "../../assets/915/01-cover.png"
source: "https://www.devleader.ca/2026/06/29/httpclient-resilience-in-net-10-timeout-retry-and-circuit-breaker-with-microsoftextensionshttpresilience"
---

HTTP 调用会失败。这不是你代码里的 bug——这是分布式系统的固有属性。网络丢包、上游服务重启、负载均衡器超时、频率限制器回推。一个写好的 .NET 应用不会假装这些失败不会发生，而是从一开始就内建弹性。

`Microsoft.Extensions.Http.Resilience` 在 .NET 8 中引入，给你一等公民的重试、断路器、对冲和超时支持，不需要直接碰原始 Polly。本文展示它在 .NET 10 下的完整 API。

## 为什么 HTTP 调用会失败——而且这在意料之中

当你的服务调用外部 API 时，你把信任放在了进程和远程服务器之间的每一跳上：网卡、OS 网络栈、路由器、负载均衡器、TLS 终结器，最后才是服务本身。任何一个环节都可以引入延迟或彻底失败。

关键认知是大多数失败是**瞬态的**——它们自己会消失。滚动部署中重启的服务会暂时不可用几秒然后恢复健康。返回 HTTP 429 的限流器想让你慢下来稍后再试。片刻过载的上游会恢复。这些失败跟 404 Not Found 或 400 Bad Request 有本质区别，后者是永久性的：重试毫无意义甚至会让事情更糟。

一个可靠的弹性层做四件事：**重试**带退避和抖动的瞬态错误、**超时**挂起的请求、在明确下游不健康时**断开断路器**防止级联故障、以及需要低延迟保证时用**对冲**发送重复请求。

## HttpClient.Timeout vs CancellationToken

在深入弹性管道之前，先解开两个让很多开发者踩坑的超时机制。

`HttpClient.Timeout` 是**全局**设置，应用于该 `HttpClient` 实例发出的每个请求。超时时抛出 `TaskCanceledException`。`CancellationToken` 则每次请求传入，由调用方控制取消——用户按取消、ASP.NET Core 请求生命周期结束、或者你自己创建的 `CancellationTokenSource`。

当两者同时在作用时，谁先触发谁赢。弹性管道给你一个干净得多的第三种选择：**尝试超时**（每次单独尝试）和**总请求超时**（跨所有重试合计）。

## 旧方法 vs 新方法

如果你写过几年 .NET，几乎肯定直接用 Polly 跑过。以前每个项目以类似这样的代码开头：

```csharp
var retryPolicy = Policy
    .Handle<HttpRequestException>()
    .WaitAndRetryAsync(3,
        attempt => TimeSpan.FromSeconds(Math.Pow(2, attempt)),
        (ex, ts, attempt, ctx) => logger.LogWarning(...));

var cbPolicy = Policy
    .Handle<HttpRequestException>()
    .CircuitBreakerAsync(5, TimeSpan.FromSeconds(30));

var combined = Policy.WrapAsync(retryPolicy, cbPolicy);
```

这能工作，但有实实在在的摩擦：版本耦合、样板代码、没有内建遥测、不知道 HTTP 语义。

`Microsoft.Extensions.Http.Resilience` 是微软对 Polly v8 的官方封装，替你做了所有接线，使用 HTTP 感知的默认值，集成 `ILogger` 和 `IMeterFactory`，不需要你在项目里直接引用 `Polly`。

## AddStandardResilienceHandler：一行搞定

```csharp
builder.Services
    .AddHttpClient<WeatherApiClient>(client =>
    {
        client.BaseAddress = new Uri("https://api.weather.example.com");
    })
    .AddStandardResilienceHandler();
```

这一行安装了四层管道：

| 层 | 策略 | 默认值 |
|----|------|--------|
| 1 | 总请求超时 | 30 秒 |
| 2 | 重试 | 3 次尝试，指数退避，2s 基础，启用抖动 |
| 3 | 断路器 | 30s 采样，100 最小吞吐，10% 失败率，5s 断开 |
| 4 | 尝试超时 | 每次 10 秒 |

重试和断路器都是 HTTP 感知的——自动处理 `HttpRequestException`、`TaskCanceledException` 和瞬态状态码（408、429、5xx），还自动遵守 `Retry-After` 响应头。

## 自定义标准管道

标准默认值是好起点，大多数真实服务需要调优：

```csharp
.AddStandardResilienceHandler(options =>
{
    options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(45);
    options.Retry.MaxRetryAttempts = 5;
    options.Retry.BackoffType = DelayBackoffType.Exponential;
    options.Retry.Delay = TimeSpan.FromMilliseconds(500);
    options.Retry.UseJitter = true;  // 必须开！
    options.CircuitBreaker.FailureRatio = 0.2;
    options.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(20);
    options.CircuitBreaker.MinimumThroughput = 20;
    options.CircuitBreaker.BreakDuration = TimeSpan.FromSeconds(10);
    options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(8);
});
```

**抖动**值得特别一说。当多个服务实例同时碰到错误，它们都在相同间隔安排第一次重试。没有抖动你会得到**重试风暴**——同步的流量尖峰会把上游再次打垮。抖动随机化退避窗口让重试自然分散。

## 断路器

断路器有三个状态：**Closed**（正常）、**Open**（跳闸，立刻失败不碰下游——抛出 `BrokenCircuitException`，同时保护你的服务和挣扎中的下游）、**Half-open**（断开时间过后允许一次探测请求，成功则闭合，失败则重新断开）。

快速失败是断路器最重要的属性。一个死掉的下游不应该让每个调用方都等满超时。断路器把多秒的挂起变成即时失败，让服务优雅降级而不是耗尽所有线程在等待中。

## 对冲：延迟敏感场景的并行请求

重试是顺序的：试一次，等，再试。这对正确性可以但引入延迟。对读密集、幂等的端点（搜索、自动补全、商品列表），对冲更合适。

对冲在首次请求没有响应后延迟一小段时间发一个重复请求。先到的响应获胜，另一个被取消。是投机性的——用稍多的容量换可预测的响应时间。

```csharp
.AddStandardHedgingHandler(options =>
{
    options.Hedging.Delay = TimeSpan.FromMilliseconds(200);
    options.Hedging.MaxHedgedAttempts = 3;
    options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(5);
});
```

规则：只对幂等请求用对冲（GET、HEAD、只读 POST）。支付提交会对冲出重复扣款。延迟仔细选——太短每次请求都翻倍负载，太长对尾部延迟没帮助。

## 每端点超时：ResiliencePropertyKey

同一个 `HttpClient` 里不同操作需要不同超时。快速自动补全应该快速失败，批量导出可以等更久：

```csharp
// 定义 key
public static class ResilienceKeys
{
    public static readonly ResiliencePropertyKey<TimeSpan> RequestTimeout = new("http-request-timeout");
}

// 管道中动态读取
pipeline.AddTimeout(new TimeoutStrategyOptions
{
    TimeoutGenerator = static args =>
    {
        if (args.Context.Properties.TryGetValue(ResilienceKeys.RequestTimeout, out var timeout))
            return new ValueTask<TimeSpan>(timeout);
        return new ValueTask<TimeSpan>(TimeSpan.FromSeconds(10));
    }
});

// 调用时设置
var context = ResilienceContextPool.Shared.Get(cancellationToken);
context.Properties.Set(ResilienceKeys.RequestTimeout, TimeSpan.FromSeconds(2));
request.SetResilienceContext(context);
```

## 可观测性

`Microsoft.Extensions.Http.Resilience` 相比原始 Polly 最强的论据之一是遥测免费来。

**日志**自动产生。每次弹性事件——重试尝试、断路器状态变化、超时——通过 `ILogger` 在合适级别记录。重试尝试 Warning 级别、断路器断开 Error 级别。

**指标**通过 `System.Diagnostics.Metrics` 发出，集成 OpenTelemetry：

```csharp
builder.Services.AddOpenTelemetry()
    .WithMetrics(metrics => metrics
        .AddMeter("Microsoft.Extensions.Http.Resilience")
        .AddPrometheusExporter());
```

关键指标包括每次尝试延迟、管道端到端耗时和断路器状态转换。

## 完整示例

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .WithMetrics(m => m.AddMeter("Microsoft.Extensions.Http.Resilience"));

builder.Services
    .AddHttpClient<WeatherApiClient>(client =>
    {
        client.BaseAddress = new Uri(
            builder.Configuration["WeatherApi:BaseUrl"]!);
        client.DefaultRequestHeaders.Add("Accept", "application/json");
    })
    .AddResilienceHandler("weather-pipeline", pipeline =>
    {
        pipeline.AddTimeout(TimeSpan.FromSeconds(30));          // 总预算
        pipeline.AddRetry(new HttpRetryStrategyOptions
        {
            MaxRetryAttempts = 4,
            BackoffType = DelayBackoffType.Exponential,
            Delay = TimeSpan.FromMilliseconds(500),
            UseJitter = true,
        });
        pipeline.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
        {
            SamplingDuration = TimeSpan.FromSeconds(20),
            MinimumThroughput = 15,
            FailureRatio = 0.2,
            BreakDuration = TimeSpan.FromSeconds(10),
        });
        pipeline.AddTimeout(TimeSpan.FromSeconds(6));           // 每次尝试
    });

var app = builder.Build();
app.MapControllers();
app.Run();

// 类型化客户端
public sealed class WeatherApiClient(HttpClient httpClient, ILogger<WeatherApiClient> logger)
{
    public async Task<CurrentWeather?> GetCurrentWeatherAsync(
        string city, CancellationToken ct = default)
    {
        var response = await httpClient.GetAsync(
            $"/v2/weather/current?city={Uri.EscapeDataString(city)}", ct);
        if (response.StatusCode == HttpStatusCode.NotFound) return null;
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<CurrentWeather>(ct);
    }
}
```

## 总结

HTTP 失败不是例外——是分布式系统的基线现实。`Microsoft.Extensions.Http.Resilience` 让在 .NET 中处理它们变得实际：四种互补策略（带抖动的重试、断路器、对冲、分层超时）全部接入 `IHttpClientFactory`、DI、日志和指标，样板代码最少。

决策指南：
- 想立刻拿到合理默认值并能通过选项自定义时用 **AddStandardResilienceHandler**
- 需要显式控制管道组合、自定义 `ShouldHandle` 谓词或不同客户端用不同策略时用 **AddResilienceHandler**
- 只在幂等、延迟敏感的端点上，且能吸收额外上游负载时用 **AddStandardHedgingHandler**
- **保守调优超时**：从默认值开始，用真实流量测量，然后收紧

## 常见问题

**Q: 需要单独加 Polly 依赖吗？**
不需要。`Microsoft.Extensions.Http.Resilience` 传递依赖 `Polly.Core`，但你的项目文件只需要引用前者，不用加 `Polly` 或 `Polly.Core`。

**Q: AddStandardResilienceHandler 的默认行为是什么？**
瞬态 HTTP 错误（408、429、5xx 和 `HttpRequestException`）上最多重试 3 次，从 2 秒开始指数退避带抖动，遵守 `Retry-After` 头，重试层外包裹断路器和超时。总操作预算 30 秒。

**Q: 断路器和重试怎么交互？**
断路器在标准管道中位于重试层的内部。每次重试尝试穿过断路器。如果失败率超过阈值，断路器断开并开始即时拒绝尝试——网络调用发生之前。断路器断开时间里失败立刻返回，不烧时间。

**Q: 什么时候用对冲代替重试？**
操作幂等、下游通常健康但偶尔慢、需要低 p99 延迟时。搜索和自动补全是好场景，写操作和任何有副作用的不是。

**Q: 怎么测试弹性管道？**
用集成测试配合返回受控错误响应的测试 HTTP 服务器。WireMock.Net 或 `WebApplicationFactory` 测试替身先返回 503 再返回 200 可以验证重试正确触发、断路器如期断开、客户端能处理 `BrokenCircuitException`。

**Q: CancellationToken 在重试等待中被取消会怎样？**
管道立即尊重取消。如果调用方在指数退避等待期间取消，操作抛出 `OperationCanceledException` 而非继续下一次尝试。

## 参考

- [HttpClient Resilience in .NET 10 — Dev Leader](https://www.devleader.ca/2026/06/29/httpclient-resilience-in-net-10-timeout-retry-and-circuit-breaker-with-microsoftextensionshttpresilience)
- [HttpClient in C#: The Complete Guide](https://www.devleader.ca/2026/06/26/httpclient-in-c-the-complete-guide-for-net-developers)
- [Microsoft.Extensions.Http.Resilience docs](https://learn.microsoft.com/dotnet/core/diagnostics/built-in-metrics-diagnostics)
