---
pubDatetime: 2026-04-12T16:40:00+08:00
title: "用 Microsoft.Extensions.Resilience 构建弹性 ASP.NET Core API"
description: "介绍如何在 .NET 10 中使用 Microsoft.Extensions.Resilience 为 API 添加重试、超时、熔断、对冲、降级和限流六大弹性策略，并给出生产环境推荐的组合管道配置。"
tags: [".NET", "ASP.NET Core", "Resilience", "微服务"]
slug: "building-resilient-apis-aspnet-core"
ogImage: "../../assets/726/01-cover.jpg"
source: "https://thecodeman.net/posts/building-resilient-api-in-aspnet-core"
---

生产环境里，每一个你调用的外部接口迟早都会出问题——数据库超时、第三方服务返回 503、网络抖动 200ms、下游微服务正在部署……这些不是极端情况，而是常态。

区别在于：应用是直接崩，还是优雅地恢复。

过去在 .NET 里实现弹性，通常要手动集成 Polly。它能用，但配置繁琐。现在 .NET 官方提供了第一方库：**Microsoft.Extensions.Resilience**，基于 Polly v8 构建，与 `HttpClientFactory`、依赖注入、结构化日志和 OpenTelemetry 原生集成。

这篇文章逐一介绍六种弹性策略，并给出生产环境推荐的管道组合。

## 安装依赖

在 .NET 10 项目中运行：

```bash
dotnet add package Microsoft.Extensions.Http.Resilience
dotnet add package Microsoft.Extensions.Resilience
```

- `Microsoft.Extensions.Http.Resilience`：用于 HTTP 请求的弹性封装
- `Microsoft.Extensions.Resilience`：用于任意异步操作的通用弹性

## 弹性管道是什么

核心概念：把多个弹性策略串成一条管道，每个策略负责一种故障场景，按你定义的顺序依次执行。

```csharp
ResiliencePipeline pipeline = new ResiliencePipelineBuilder()
    .AddRetry(new RetryStrategyOptions
    {
        ShouldHandle = new PredicateBuilder().Handle<ConflictException>(),
        Delay = TimeSpan.FromSeconds(2),
        MaxRetryAttempts = 3,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true
    })
    .AddTimeout(new TimeoutStrategyOptions
    {
        Timeout = TimeSpan.FromSeconds(5)
    })
    .Build();

await pipeline.ExecuteAsync(
    async ct => await httpClient.GetAsync("/api/weather", ct),
    cancellationToken);
```

如果 HTTP 调用抛出 `ConflictException`，重试策略最多重试 3 次，使用指数退避加抖动。如果整个操作超过 5 秒，超时策略直接终止。

**顺序很重要**：外层策略先执行，内层策略在外层保护下运行。

## 重试策略

分布式系统里瞬时故障很常见——网络抖动、服务短暂过载。重试策略在失败后等一段时间再尝试，给系统恢复的机会。

```csharp
builder.Services.AddResiliencePipeline("retry-pipeline", builder =>
{
    builder.AddRetry(new RetryStrategyOptions
    {
        MaxRetryAttempts = 3,
        Delay = TimeSpan.FromMilliseconds(300),
        BackoffType = DelayBackoffType.Exponential,
        ShouldHandle = new PredicateBuilder().Handle<HttpRequestException>()
    });
});
```

这个配置最多重试 3 次，延迟依次是约 300ms、600ms、1200ms。

**为什么用指数退避**：如果服务过载，每 300ms 发一次请求只会让它更堵。退避给它喘息空间。

**为什么用抖动（`UseJitter = true`）**：如果 50 个客户端都在完全相同的时间间隔重试，会形成"重试风暴"。加入随机偏移让请求分散开来。

## 超时策略

没有超时保护，一个永远不响应的外部服务会让线程一直挂着，消耗连接池，最终拖垮整个应用。

```csharp
builder.Services.AddResiliencePipeline("timeout-pipeline", builder =>
{
    builder.AddTimeout(TimeSpan.FromSeconds(2));
});
```

外部服务 2 秒没响应，操作以 `TimeoutRejectedException` 失败。

**重要的顺序规则**：超时和重试组合时，超时应该是内层策略（后加入）。这样每次尝试都有独立的超时，超时后重试策略可以继续下一次尝试。

## 熔断策略

熔断器是我在生产中用得最顺手的策略之一。没有熔断器，应用会持续向已经崩溃的服务发请求，白白浪费资源，甚至级联失败。

```csharp
builder.Services.AddResiliencePipeline("cb-pipeline", builder =>
{
    builder.AddCircuitBreaker(new CircuitBreakerStrategyOptions
    {
        FailureRatio = 0.5,
        MinimumThroughput = 10,
        SamplingDuration = TimeSpan.FromSeconds(30),
        BreakDuration = TimeSpan.FromSeconds(15)
    });
});
```

工作方式：

- 监控 30 秒内的调用
- 至少 10 次调用中有 50% 失败，熔断器打开
- 接下来 15 秒内所有调用立即失败，不发出网络请求
- 15 秒后进入半开状态，放行一个测试请求
- 测试成功则关闭熔断，恢复正常流量

任何调用外部 API 的服务都应该加这个。

## 对冲策略

对冲（Hedging）用于对延迟敏感的场景。与其等一个慢响应，不如并行发出多个请求，谁先返回用谁。

```csharp
builder.Services.AddResiliencePipeline<string, string>("gh-hedging", builder =>
{
    builder.AddHedging(new HedgingStrategyOptions<string>
    {
        MaxHedgedAttempts = 3,
        DelayGenerator = args =>
        {
            var delay = args.AttemptNumber switch
            {
                0 or 1 => TimeSpan.Zero,        // 并行模式
                _ => TimeSpan.FromSeconds(-1)    // 降级模式
            };
            return new ValueTask<TimeSpan>(delay);
        }
    });
});
```

这个配置最多发 4 个请求（1 个主请求 + 3 个对冲），前两个并行，后续的作为降级备用。第一个成功的结果胜出，其余请求取消。

在有多个服务副本的场景下效果特别好——可以把对冲请求路由到不同实例。

## 降级策略

降级是最后一道防线。与其返回 500 错误让用户看到崩溃页面，不如返回缓存数据或默认值。

```csharp
builder.Services.AddResiliencePipeline<string, string?>("gh-fallback", builder =>
{
    builder.AddFallback(new FallbackStrategyOptions<string?>
    {
        FallbackAction = _ =>
            Outcome.FromResultAsValueTask<string?>(string.Empty)
    });
});
```

实际项目里，这里通常返回缓存数据而不是空字符串。核心意图是：用户得到一个降级结果，而不是报错。

## 限流策略

调用有速率限制的第三方 API 时，最好在本地先做限流，避免被对方返回 429。

```csharp
builder.Services.AddResiliencePipeline("ratelimiter-pipeline", builder =>
{
    builder.AddRateLimiter(new SlidingWindowRateLimiter(
        new SlidingWindowRateLimiterOptions
        {
            PermitLimit = 100,
            SegmentsPerWindow = 4,
            Window = TimeSpan.FromMinutes(1)
        }
    ));
});
```

每分钟最多 100 个请求，窗口分为 4 段（每段 15 秒），流量分布更平滑。

## 在端点里使用管道

正式项目里不需要每次手动构建管道——注册一次，通过 `ResiliencePipelineProvider` 按名称取用。

```csharp
app.MapGet("/subscribers", async (
    HttpClient httpClient,
    ResiliencePipelineProvider<string> pipelineProvider,
    CancellationToken cancellationToken) =>
{
    var pipeline = pipelineProvider.GetPipeline<Subscriber?>("gh-fallback");

    return await pipeline.ExecuteAsync(
        async token =>
            await httpClient.GetFromJsonAsync<Subscriber>("api/subscribers", token),
        cancellationToken);
});
```

用 `AddResiliencePipeline("gh-fallback", ...)` 注册，用 `GetPipeline<T>()` 获取，干净、可测试、整个应用可复用。

## 生产推荐管道

跑过多个项目后，这是我对每个外部 HTTP 调用的最低配置：

```csharp
builder.Services.AddResiliencePipeline("production-pipeline", builder =>
{
    builder
        .AddRetry(new RetryStrategyOptions
        {
            MaxRetryAttempts = 3,
            Delay = TimeSpan.FromMilliseconds(500),
            BackoffType = DelayBackoffType.Exponential,
            UseJitter = true,
            ShouldHandle = new PredicateBuilder().Handle<HttpRequestException>()
        })
        .AddCircuitBreaker(new CircuitBreakerStrategyOptions
        {
            FailureRatio = 0.5,
            MinimumThroughput = 10,
            SamplingDuration = TimeSpan.FromSeconds(30),
            BreakDuration = TimeSpan.FromSeconds(15)
        })
        .AddTimeout(TimeSpan.FromSeconds(5));
});
```

**重试 → 熔断 → 超时**，这是每个外部调用的最低标准：

- 重试处理瞬时故障
- 熔断保护持续性故障，防止级联
- 超时确保单次调用不会永久阻塞

在此基础上，按需加入对冲和降级。

## 小结

`Microsoft.Extensions.Resilience` 把生产级弹性能力直接集成进了 .NET 的依赖注入和 HTTP 基础设施，不需要从头搭建。六种策略各司其职，可以自由组合。

从重试 + 熔断 + 超时开始，根据具体服务的特性调整阈值配置，然后上线。

## 参考

- [Building Resilient APIs in ASP.NET Core - TheCodeMan.net](https://thecodeman.net/posts/building-resilient-api-in-aspnet-core)
