---
pubDatetime: 2025-05-22
tags: [.NET, 微服务, HTTP, 高可用, 后端开发, Polly, Resilience]
slug: resilient-http-dotnet-practices
source: https://learn.microsoft.com/en-us/dotnet/core/resilience/http-resilience?tabs=dotnet-cli
title: .NET打造高可用HTTP应用：Resilience关键实践全解
description: 面向.NET后端开发者，深入讲解如何用Microsoft.Extensions.Http.Resilience和Polly构建企业级高可用HTTP请求，涵盖重试、熔断、超时、并发控制等完整策略，助力微服务与分布式系统提升健壮性。
---

# .NET打造高可用HTTP应用：Resilience关键实践全解

> 面向企业级.NET后端开发者、架构师与微服务实践者，全面梳理如何用Resilience模式和Polly提升HTTP通讯的健壮性与容错能力。

---

## 引言：HTTP请求“不掉线”，业务才能“不断线” 🚦

在现代分布式系统和微服务架构中，HTTP请求是服务间通信的主力军。然而，网络抖动、下游服务雪崩、突发流量洪峰等问题，常常让我们“猝不及防”。如何让你的HTTP调用既能自动重试、限流，又能智能熔断和快速恢复？微软官方的 [Microsoft.Extensions.Http.Resilience](https://www.nuget.org/packages/Microsoft.Extensions.Http.Resilience) + 开源利器 [Polly](https://github.com/App-vNext/Polly) 为.NET开发者提供了开箱即用的韧性（Resilience）解决方案。

本文将手把手带你用.NET构建高可用的HTTP客户端，详解核心设计理念与实战配置，助你轻松迈进“业务不中断”的新时代！

---

## .NET HTTP Resilience 基石：一图看懂策略链路

首先来看一个标准HTTP GET请求在Resilience Pipeline下的流程：

![Example HTTP GET workflow with resilience pipeline](https://learn.microsoft.com/en-us/dotnet/core/resilience/media/http-get-comments-flow.png)

如上图所示，每个请求都会经过一系列Resilience策略过滤与保护——从限流、超时、重试到熔断和最终响应。这就是为什么即使网络波动或下游偶发异常，你的系统也能平稳应对、自动恢复。

---

## 1. 快速集成：Resilience Handler一键接入

### 1.1 安装依赖

在你的.NET项目中加入Resilience包：

```bash
dotnet add package Microsoft.Extensions.Http.Resilience --version 8.0.0
```

### 1.2 配置HttpClient与Resilience Handler

无论是传统ServiceCollection还是现代HostApplicationBuilder方式，都支持链式配置：

```csharp
var services = new ServiceCollection();
services.AddHttpClient<ExampleClient>(client =>
    client.BaseAddress = new("https://jsonplaceholder.typicode.com"))
    .AddStandardResilienceHandler();
```

或者推荐使用泛型Host：

```csharp
using Microsoft.Extensions.Hosting;

HostApplicationBuilder builder = Host.CreateApplicationBuilder(args);
builder.Services.AddHttpClient<ExampleClient>(client =>
    client.BaseAddress = new("https://jsonplaceholder.typicode.com"))
    .AddStandardResilienceHandler();
```

---

## 2. 标准Resilience策略全解：让“健壮”成为默认

### 2.1 策略链路分层

默认情况下，标准Resilience Handler包含如下五大策略：

| 顺序 | 策略                   | 作用                                                         | 默认配置           |
| ---- | ---------------------- | ------------------------------------------------------------ | ------------------ |
| 1    | 限流RateLimiter        | 限制并发请求数，防止资源耗尽                                 | 队列0，许可1000    |
| 2    | 总超时TotalTimeout     | 限定整体请求生命周期（含重试），避免请求“吊死”               | 30秒               |
| 3    | 重试Retry              | 对瞬时故障（如500+、408、429等）自动重试，支持指数退避与抖动 | 最大3次，2s延迟    |
| 4    | 熔断CircuitBreaker     | 出错率高时自动切断通路，防止雪崩                             | 出错比10%，采样30s |
| 5    | 单次超时AttemptTimeout | 每次尝试的最大时长                                           | 10秒               |

> ⚡ **说明**：标准策略已覆盖业界大多数场景，如需自定义可进一步扩展。

### 2.2 精细化控制重试行为

有些HTTP方法（如POST/DELETE）若被自动重试，可能引发副作用（如数据重复）。可以通过如下方式禁用对这些方法的自动重试：

```csharp
httpClientBuilder.AddStandardResilienceHandler(options => {
    options.Retry.DisableFor(HttpMethod.Post, HttpMethod.Delete);
});
```

或者一键禁用所有“非幂等”方法的重试：

```csharp
httpClientBuilder.AddStandardResilienceHandler(options => {
    options.Retry.DisableForUnsafeHttpMethods();
});
```

---

## 3. 高级玩法：Hedging与多活路由助力秒级切换

### 3.1 并行Hedging机制简介

Hedging策略不仅重试慢请求，还能并发向多个Endpoint发起请求。适用于多活部署、蓝绿发布和A/B测试等场景。

```csharp
httpClientBuilder.AddStandardHedgingHandler(builder =>
{
    builder.ConfigureWeightedGroups(options =>
    {
        options.SelectionMode = WeightedGroupSelectionMode.EveryAttempt;
        options.Groups.Add(new WeightedUriEndpointGroup
        {
            Endpoints =
            {
                new() { Uri = new("https://example.net/api/a"), Weight = 33 },
                new() { Uri = new("https://example.net/api/b"), Weight = 33 },
                new() { Uri = new("https://example.net/api/c"), Weight = 33 }
            }
        });
    });
});
```

> 🏁 **应用场景举例**：A/B测试、主备集群自动切换等。

### 3.2 图示解释（策略权重A/B/C组）

> _每组权重决定请求分配比例。组数决定最大hedging尝试次数。_

---

## 4. 灵活自定义：Pipeline自助拼装

### 4.1 自定义组合示例

比如想要更激进的Retry+自定义熔断+自定义超时：

```csharp
httpClientBuilder.AddResilienceHandler("CustomPipeline", builder =>
{
    builder.AddRetry(new HttpRetryStrategyOptions
    {
        BackoffType = DelayBackoffType.Exponential,
        MaxRetryAttempts = 5,
        UseJitter = true
    });
    builder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
    {
        SamplingDuration = TimeSpan.FromSeconds(10),
        FailureRatio = 0.2,
        MinimumThroughput = 3,
        ShouldHandle = args =>
            ValueTask.FromResult(args is { Outcome.Result.StatusCode: HttpStatusCode.RequestTimeout or HttpStatusCode.TooManyRequests })
    });
    builder.AddTimeout(TimeSpan.FromSeconds(5));
});
```

### 4.2 动态热更新策略（支持热加载配置）

结合`appsettings.json`和Options模式，实现不中断运行的策略动态调整。

---

## 5. 实战落地：服务注入与调用模式

```csharp
IHost host = builder.Build();
var client = host.Services.GetRequiredService<ExampleClient>();
await foreach(var comment in client.GetCommentsAsync())
{
    Console.WriteLine(comment);
}
```

当网络或服务异常时，Resilience Pipeline会自动保护你的业务不中断！

---

## 常见问题FAQ & 踩坑提醒

- **gRPC与Resilience Handler冲突**：升级`Grpc.Net.ClientFactory`至2.64.0+。
- **Application Insights丢失监控**：先注册AI，再注册Resilience功能。

---

## 总结与思考 💡

通过微软官方Resilience包和Polly策略体系，.NET开发者可以轻松为企业级HTTP请求加上“防摔护甲”。只需一行代码，就能拥抱限流、超时、重试、熔断、hedging等行业最佳实践。无论是微服务、云原生还是传统单体系统，都能受益于高可用架构的红利。
