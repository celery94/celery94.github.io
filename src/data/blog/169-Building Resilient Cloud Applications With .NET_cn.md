---
pubDatetime: 2024-08-02
tags: [".NET", "Architecture"]
source: https://www.milanjovanovic.tech/blog/building-resilient-cloud-applications-with-dotnet?utm_source=Twitter&utm_medium=social&utm_campaign=29.07.2024
author: Milan Jovanović
title: 使用 .NET 构建高可用云应用程序
description: 通过将应用程序设计成具有高可用性，您可以在遇到困难时创建健壮且可靠的系统。在本期新闻通讯中，我们将探索在 .NET 中构建高可用系统的一些工具和技术。
---

# 使用 .NET 构建高可用云应用程序

> ## 摘要
>
> 通过将应用程序设计成具有高可用性，您可以在遇到困难时创建健壮且可靠的系统。在本期新闻通讯中，我们将探索在 .NET 中构建高可用系统的一些工具和技术。

---

感谢我们的赞助商使这份新闻通讯对读者免费：

使用 [**Postman Flows**](https://learning.postman.com/docs/postman-flows/gs/flows-overview/) 可视化构建 API 应用程序。Postman Flows 是一个用于为 API 优先的世界构建 API 驱动应用程序的可视化工具。您可以使用 Flows 链接请求、处理数据，并在 Postman 工作空间中创建实际的工作流程。[**立即开始**](https://learning.postman.com/docs/postman-flows/gs/flows-overview/)。

[**构建 Blazor Web 应用程序的九大最佳实践**](https://www.telerik.com/blogs/blazor-basics-9-best-practices-building-blazor-web-applications?utm_medium=cpm&utm_source=milanjovanovic&utm_campaign=blazor-general-awareness)：在本文中，您将学习来自 .NET 开发者和 YouTube 影响者 Claudio Bernasconi 关于构建 Blazor Web 应用程序的九大最佳实践。 [**点击阅读**](https://www.telerik.com/blogs/blazor-basics-9-best-practices-building-blazor-web-applications?utm_medium=cpm&utm_source=milanjovanovic&utm_campaign=blazor-general-awareness)。

从我在微服务系统中的工作经验来看，事情并不总是按计划进行。网络请求会随机失败，应用服务器会超载，并且会出现意外错误。这就是高可用性的用武之地。

高可用应用程序能够从短暂的故障中恢复并继续运行。高可用性是通过设计能够优雅地处理故障并快速恢复的应用程序来实现的。

通过将应用程序设计成具有高可用性，您可以在遇到困难时创建健壮且可靠的系统。

在本期新闻通讯中，我们将探索在 .NET 中构建高可用系统的一些工具和技术。

## 高可用性：为什么需要关注

发送 HTTP 请求是服务之间远程通信的一种常见方法。然而，HTTP 请求容易因网络或服务器问题而失败。这些故障可能会中断服务的可用性，特别是随着依赖关系的增加，级联故障的风险也会增加。

那么，如何提高应用程序和服务的高可用性呢？

以下是一些提高高可用性的策略：

- **重试**：对由于短暂错误导致失败的请求进行重试。
- **超时**：取消超过指定时间限制的请求。
- **备用**：为失败的操作定义替代操作或结果。
- **断路器**：暂时中止与不可用服务的通信。

您可以单独或组合使用这些策略，以实现最佳的 HTTP 请求高可用性。

让我们看看如何在 .NET 应用程序中引入高可用性。

## 高可用管道

使用 .NET 8，将高可用性集成到您的应用程序变得更加简单。我们可以使用 `Microsoft.Extensions.Resilience` 和 `Microsoft.Extensions.Http.Resilience`，它们是基于 [Polly](https://github.com/App-vNext/Polly) 构建的。Polly 是一个 .NET 高可用性和短暂故障处理库。Polly 允许我们定义诸如重试、断路器、超时、速率限制、备用和对冲之类的高可用性策略。

Polly 在其最新版本（V8）中引入了一个新的 API 结构，这是与 Microsoft 合作实现的。您可以在这个 [**视频**](https://youtu.be/PqVQFUCTzUM) 中了解更多关于 Polly V8 API 的信息。

如果您之前使用的是 `Microsoft.Extensions.Http.Polly`，建议您切换到上述的其中一个软件包。

首先，我们安装所需的 NuGet 包：

```powershell
Install-Package Microsoft.Extensions.Resilience
Install-Package Microsoft.Extensions.Http.Resilience
```

要使用高可用性，您必须首先构建一个由高可用性[策略](https://www.pollydocs.org/strategies/)组成的管道。我们配置为管道一部分的每个策略将按配置顺序执行。顺序对于高可用性管道是重要的，请记住这一点。

我们首先创建一个 `ResiliencePipelineBuilder` 实例，该实例允许我们配置高可用性策略。

```csharp
ResiliencePipeline pipeline = new ResiliencePipelineBuilder()
    .AddRetry(new RetryStrategyOptions
    {
        ShouldHandle = new PredicateBuilder().Handle<ConflictException>(),
        Delay = TimeSpan.FromSeconds(1),
        MaxRetryAttempts = 2,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true
    })
    .AddTimeout(new TimeoutStrategyOptions
    {
        Timeout = TimeSpan.FromSeconds(10)
    })
    .Build();

await pipeline.ExecuteAsync(
    async ct => await httpClient.GetAsync("https://modularmonolith.com", ct),
    cancellationToken);
```

以下是我们添加到高可用管道中的内容：

- `AddRetry` - 配置一个重试高可用性策略，我们可以通过传入 `RetryStrategyOptions` 实例进一步配置。我们可以为 `ShouldHandle` 属性提供一个谓词，以定义高可用性策略应处理的异常。重试策略还伴随一些合理的[默认值](https://www.pollydocs.org/strategies/retry.html#defaults)。
- `AddTimeout` - 配置一个超时策略，如果在超时前未完成代理，将引发 `TimeoutRejectedException`。我们可以通过传入 `TimeoutStrategyOptions` 实例提供自定义超时。默认超时时间为 30 秒。

最后，我们可以构建高可用管道并获取配置好的 `ResiliencePipeline` 实例，该实例将应用相应的高可用策略。要使用 `ResiliencePipeline`，我们可以调用 `ExecuteAsync` 方法并传入代理。

## 高可用管道和依赖注入

每次使用高可用管道时都要进行配置是很麻烦的。 .NET 8 引入了一个新的扩展方法用于 `IServiceCollection` 接口，允许我们通过依赖注入注册高可用管道。

与其每次手动配置高可用性，不如通过名称请求预先配置的管道。

我们首先调用 `AddResiliencePipeline` 方法，允许我们配置高可用管道。每个高可用管道都需要一个唯一的键。我们可以使用这个键解析相应的高可用管道实例。

在此示例中，我们传入一个 `string` 键，允许我们配置非泛型的 `ResiliencePipelineBuilder`。

```csharp
services.AddResiliencePipeline("retry", builder =>
{
    builder.AddRetry(new RetryStrategyOptions
    {
        Delay = TimeSpan.FromSeconds(1),
        MaxRetryAttempts = 2,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true
    });
})
```

但是，当调用 `AddResiliencePipeline` 时，我们还可以指定泛型参数。这允许我们使用 `ResiliencePipelineBuilder<TResult>` 配置类型化高可用管道。使用这种方法，我们可以访问[对冲](https://www.pollydocs.org/strategies/hedging.html)和[备用](https://www.pollydocs.org/strategies/fallback.html)策略。

在以下示例中，我们通过调用 `AddFallback` 配置备用策略。这允许我们提供一个备用值，该值可以在失败的情况下返回。备用值可以是静态值，也可以来自另一个 HTTP 请求或数据库。

```csharp
services.AddResiliencePipeline<string, GitHubUser?>("gh-fallback", builder =>
{
    builder.AddFallback(new FallbackStrategyOptions<GitHubUser?>
    {
        FallbackAction = _ =>
            Outcome.FromResultAsValueTask<GitHubUser?>(GitHubUser.Empty)
    });
});
```

要使用通过依赖注入配置的高可用管道，我们可以使用 `ResiliencePipelineProvider`。它提供 `GetPipeline` 方法以获取管道实例。我们必须提供注册高可用管道时使用的键。

```csharp
app.MapGet("users", async (
    HttpClient httpClient,
    ResiliencePipelineProvider<string> pipelineProvider) =>
{
    ResiliencePipeline<GitHubUser?> pipeline =
        pipelineProvider.GetPipeline<GitHubUser?>("gh-fallback");

    var user = await pipeline.ExecuteAsync(async token =>
        await httpClient.GetAsync("api/users", token),
        cancellationToken);
})
```

## 高可用策略和 Polly

[高可用策略](https://www.pollydocs.org/strategies/) 是 Polly 的核心组件。它们设计用于在引入额外高可用层的同时运行自定义回调。我们不能直接运行这些策略，而是通过高可用管道执行它们。

Polly 将高可用策略分为**响应式**和**主动式**。响应式策略处理特定异常或结果。主动式策略决定是否通过使用速率限制器或超时高可用策略取消或拒绝回调的执行。

Polly 具有以下内建高可用策略：

- **重试**：经典的“再试一次”的方法。非常适合处理临时的网络故障。您可以配置重试次数，甚至添加一些随机性（抖动）以避免在所有人同时重试时系统过载。
- **断路器**：类似于电气断路器，它防止对故障系统的重击。如果错误累积，断路器会暂时“跳闸”以给系统时间恢复。
- **备用**：如果主要调用失败，则提供一个安全的默认响应。它可能是缓存结果或简单的“服务不可用”消息。
- **对冲**：同时发出多个请求，采用第一个成功的响应。如果您的系统有多种处理方式，这很有用。
- **超时**：通过在超时后终止请求来防止请求永远挂起。
- **速率限制**：节流传出的请求以防止过度调用外部服务。

## HTTP 请求高可用性

向外部服务发送 HTTP 调用是您的应用程序与外界互动的方式。这些服务可能是第三方服务，如支付网关和身份提供商，也可能是您的团队拥有和运营的其他服务。

`Microsoft.Extensions.Http.Resilience` 库附带现成的高可用管道，用于发送 HTTP 请求。

我们可以使用 `AddStandardResilienceHandler` 方法为传出的 [**HttpClient 请求**](https://www.milanjovanovic.tech/blog/the-right-way-to-use-httpclient-in-dotnet) 添加高可用性。

```csharp
services.AddHttpClient<GitHubService>(static (httpClient) =>
{
    httpClient.BaseAddress = new Uri("https://api.github.com/");
})
.AddStandardResilienceHandler();
```

这也意味着您可以消除之前用于高可用性的所有 [**委托处理程序**](https://www.milanjovanovic.tech/blog/extending-httpclient-with-delegating-handlers-in-aspnetcore)。

标准高可用处理程序结合了五个 Polly 策略来创建适用于大多数场景的高可用管道。标准管道包含以下策略：

- **速率限制**：限制发送到依赖关系的并发请求最大数量。
- **总请求超时**：引入总超时，包括任何重试尝试。
- **重试**：如果由于超时或短暂错误导致请求失败，则重试该请求。
- **断路器**：如果检测到太多故障，则阻止进一步发送请求。
- **尝试超时**：为单个请求引入超时。

您可以通过配置 `HttpStandardResilienceOptions` 自定义标准高可用管道的任何方面。

## 收获

高可用性不仅仅是一个流行词汇；它是构建可靠软件系统的核心原则。我们很幸运能有像 `Microsoft.Extensions.Resilience` 和 Polly 这样的强大工具，可以用它们来设计能够优雅地处理任何短暂故障的系统。

良好的[**监控和可观察性**](https://www.milanjovanovic.tech/blog/introduction-to-distributed-tracing-with-opentelemetry-in-dotnet)对于理解高可用机制在生产环境中的工作情况至关重要。记住，目标不是消除故障，而是优雅地处理它们并保持应用程序的正常运行。

准备更深入地了解高可用架构吗？我的高级课程 [**构建模块化单体应用架构**](https://www.milanjovanovic.tech/modular-monolith-architecture) 将为您提供设计和实现健壮、可扩展系统的技能。查看 [**模块化单体应用架构**](https://www.milanjovanovic.tech/modular-monolith-architecture)。

**挑战**：看看您现有的 .NET 项目。是否有任何关键领域，通过应用一些我们在这里讨论的技术，可以显著提高高可用性？选择一个并尝试应用一些我们讨论的技术。
