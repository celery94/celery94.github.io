---
pubDatetime: 2025-05-22
tags: [".NET", "ASP.NET Core", "C#", "Architecture"]
slug: resilient-api-dotnet9
source: https://thecodeman.net/posts/building-resilient-api-in-aspnet-core-9
title: ASP.NET Core 9高可用API设计：全面解读Microsoft.Extensions.Resilience实战
description: 深入剖析.NET 8/9内置的Resilience库，教你如何用Retry、Timeout、断路器等策略打造企业级高可用API。
---

# ASP.NET Core 9高可用API设计：全面解读Microsoft.Extensions.Resilience实战

> 在微服务和云原生大行其道的今天，你的.NET API准备好面对不稳定的外部服务和网络波动了吗？本文将结合微软官方新库Microsoft.Extensions.Resilience，带你掌握现代分布式系统下的高可用API设计要领！

---

## 引言：云端API，如何应对不稳定世界？

想象一下：你辛苦开发的后端API，明明本地一切OK，可上线后各种503、Timeout、外部接口波动……😱。  
如何让你的API在遇到网络抖动、服务超时、第三方接口不稳定时依然表现稳健？  
.NET 8/9起，微软官方推出了“Resilience”库——自带Retry、Timeout、断路器等能力，不再依赖三方Polly，原生支持HttpClientFactory、依赖注入和OpenTelemetry。  
今天我们就用一篇通俗易懂但极具技术深度的图文，带你玩转Resilience，打造企业级高可用API！

---

## 正文

### 1. Resilience库是什么？一站式弹性利器

**Microsoft.Extensions.Resilience** 是微软为.NET生态提供的内置弹性处理库，核心能力包括：

- **自动重试（Retry）**：失败后自动再次发起请求
- **超时控制（Timeout）**：避免接口长时间挂起
- **断路器（Circuit Breaker）**：连续失败后临时切断请求，防止雪崩
- **请求限速（Rate Limiting）**：限制调用频率，保护下游服务
- **备选请求（Hedging）**：主请求慢就同时发出备用请求，提高成功率
- **降级兜底（Fallback）**：关键路径失败时给出备选结果，提升用户体验

这些策略均可自由组合，通过声明式管道实现，无缝集成到ASP.NET Core项目中。

---

### 2. 快速上手：项目集成与基础代码结构

#### ① 安装依赖包

```bash
dotnet add package Microsoft.Extensions.Http.Resilience
dotnet add package Microsoft.Extensions.Resilience
```

#### ② 构建你的Resilience管道

以最常见的Retry+Timeout为例：

```csharp
builder.Services.AddResiliencePipeline("default-pipeline", builder =>
{
    builder.AddRetry(new RetryStrategyOptions
    {
        MaxRetryAttempts = 3,
        Delay = TimeSpan.FromMilliseconds(300),
        BackoffType = DelayBackoffType.Exponential,
        ShouldHandle = new PredicateBuilder().Handle<HttpRequestException>()
    });
    builder.AddTimeout(TimeSpan.FromSeconds(2));
});
```

### 3. 各策略详解+实战代码

#### ✅ Retry（重试策略）

- 应对：网络闪断/临时故障
- 核心参数：最大重试次数、延迟、指数退避、处理哪些异常

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

> 三次重试，延迟递增（300ms/600ms/1200ms），仅处理HttpRequestException。

#### ⏰ Timeout（超时策略）

- 应对：接口慢响应，防止线程阻塞
- 实战配置：

```csharp
builder.Services.AddResiliencePipeline("timeout-pipeline", builder =>
{
    builder.AddTimeout(TimeSpan.FromSeconds(2));
});
```

> 超过2秒未响应即超时，触发后续处理（如重试或兜底）。

#### 🚦 Circuit Breaker（断路器）

- 应对：下游接口持续故障，防止级联雪崩
- 实战配置：

```csharp
builder.Services.AddResiliencePipeline("cb-pipeline", builder =>
{
    builder.AddCircuitBreaker(new CircuitBreakerStrategyOptions
    {
        FailureRatio = 0.5, // 故障率50%
        MinimumThroughput = 10,
        SamplingDuration = TimeSpan.FromSeconds(30),
        BreakDuration = TimeSpan.FromSeconds(15)
    });
});
```

> 连续失败比例超50%且调用量超10，则“断路”15秒。

#### ⚡ Hedging（备选并发）

- 应对：主请求慢/有概率失败时，提前发起并行请求兜底
- 实战配置：

```csharp
builder.Services.AddResiliencePipeline<string, string>("hedging-pipeline", builder =>
{
    builder.AddHedging(new HedgingStrategyOptions<string>
    {
        MaxHedgedAttempts = 3,
        DelayGenerator = args => new ValueTask<TimeSpan>(
            args.AttemptNumber <= 1 ? TimeSpan.Zero : TimeSpan.FromSeconds(-1))
    });
});
```

> 首两次请求并行发起，最多四次尝试，大大提升极端情况下成功率。

#### 🛟 Fallback（降级兜底）

- 应对：所有方案都失败后提供保底返回值，保障系统韧性
- 实战配置：

```csharp
builder.Services.AddResiliencePipeline<string, string?>("fallback-pipeline", builder =>
{
    builder.AddFallback(new FallbackStrategyOptions<string?>
    {
        FallbackAction = _ => Outcome.FromResultAsValueTask<string?>(string.Empty)
    });
});
```

> 出错时返回空字符串或自定义消息，而不是直接抛异常。

#### 🚥 Rate Limiter（限流）

- 应对：防止接口被过载或被第三方限流
- 实战配置：

```csharp
builder.Services.AddResiliencePipeline("ratelimiter-pipeline", builder =>
{
    builder.AddRateLimiter(new SlidingWindowRateLimiter(
        new SlidingWindowRateLimiterOptions
        {
            PermitLimit = 100,
            SegmentsPerWindow = 4,
            Window = TimeSpan.FromMinutes(1)
        }));
});
```

> 每分钟最多100次调用，细粒度分段统计。

---

### 4. 全局自动化应用：ResiliencePipelineProvider接入业务代码

在ASP.NET Core Minimal API中应用弹性策略，不需要每次手动组合管道。利用`ResiliencePipelineProvider`即可按Key自动应用：

```csharp
app.MapGet("/subscribers", async (
    HttpClient httpClient,
    ResiliencePipelineProvider<string> pipelineProvider,
    CancellationToken cancellationToken) =>
{
    var pipeline = pipelineProvider.GetPipeline<Subscriber?>("fallback-pipeline");
    return await pipeline.ExecuteAsync(
        async token => await httpClient.GetFromJsonAsync<Subscriber>("api/subscribers", token),
        cancellationToken);
});
```

> 按需选择不同策略，灵活应对不同业务场景！

---

## 总结与思考

微软官方的Resilience库让.NET开发者无需再手写复杂的熔断与重试逻辑，只需声明式地组合策略，即可快速实现**企业级高可用API**。  
建议每个对外或依赖第三方服务的接口，至少配备Retry+Timeout+断路器三件套！  
随着分布式系统愈发普及，这将是你架构“稳”的重要基石。
