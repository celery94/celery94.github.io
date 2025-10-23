---
pubDatetime: 2024-04-13
tags: [".NET", "ASP.NET Core"]
source: https://www.milanjovanovic.tech/blog/how-to-use-rate-limiting-in-aspnet-core
author: Milan Jovanović
title: 如何在 ASP.NET Core 中使用速率限制
description: 速率限制是一种限制对服务器或API请求数量的技术。
---

# 如何在 ASP.NET Core 中使用速率限制

> ## 摘要
>
> 速率限制是一种限制对服务器或API请求数量的技术。
> 在给定时间段内引入限制，以防止服务器过载并防止滥用。
> 在ASP.NET Core 7中，我们有一个内置的速率限制中间件，易于集成到您的API中。
> 我们将介绍四种速率限制算法：- 固定窗口 - 滑动窗口 - 令牌桶 - 并发
> 让我们看看如何使用速率限制。
>
> 原文 [Milan Jovanović](https://www.milanjovanovic.tech/blog/how-to-use-rate-limiting-in-aspnet-core)

---

速率限制是一种限制对服务器或API请求数量的技术。

在给定时间段内引入限制，以防止服务器过载并防止滥用。

在 ASP.NET Core 7 中，我们有一个内置的速率限制中间件，易于集成到您的API中。

我们将介绍四种速率限制算法：

- [固定窗口](https://www.milanjovanovic.tech/blog/how-to-use-rate-limiting-in-aspnet-core#fixed-window-limiter)
- [滑动窗口](https://www.milanjovanovic.tech/blog/how-to-use-rate-limiting-in-aspnet-core#sliding-window-limiter)
- [令牌桶](https://www.milanjovanovic.tech/blog/how-to-use-rate-limiting-in-aspnet-core#token-bucket-limiter)
- [并发](https://www.milanjovanovic.tech/blog/how-to-use-rate-limiting-in-aspnet-core#concurrency-limiter)

让我们看看如何使用速率限制。

## 什么是速率限制？

速率限制是关于限制对API的请求数量，通常在特定时间窗口或基于其他标准内。

这在几个方面是实用的：

- 防止服务器或应用程序的过载
- 提高安全性并防范DDoS攻击
- 通过防止不必要的资源使用来减少成本

在多租户应用程序中，每个唯一用户可以对API请求的数量有限制。

## 配置速率限制

ASP.NET Core 7在`Microsoft.AspNetCore.RateLimiting`命名空间中引入了内置的速率限制中间件。

要在您的应用程序中添加速率限制，首先需要注册速率限制服务：

```csharp
builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;

    // 我们稍后将讨论添加特定的速率限制策略。
});
```

我建议将`RejectionStatusCode`更新为`429 (请求过多)`，因为它更正确。默认值是`503 (服务不可用)`。

您还必须应用`RateLimitingMiddleware`：

```csharp
app.UseRateLimiter();
```

这就是您所需要的全部。

让我们看看我们可以使用的速率限制算法。

## 固定窗口限制器

`AddFixedWindowLimiter`方法配置一个固定窗口限制器。

`Window`值确定时间窗口。

当时间窗口到期时，将启动一个新的，请求限制将被重置。

```csharp
builder.Services.AddRateLimiter(rateLimiterOptions =>
{
    rateLimiterOptions.AddFixedWindowLimiter("fixed", options =>
    {
        options.PermitLimit = 10;
        options.Window = TimeSpan.FromSeconds(10);
        options.QueueProcessingOrder = QueueProcessingOrder.OldestFirst;
        options.QueueLimit = 5;
    });
});
```

## 滑动窗口限制器

滑动窗口算法与固定窗口相似，但它引入了窗口中的段。

以下是其工作原理：

- 每个时间窗口被分成多个段
- 窗口每个段间隔滑动一个段
- 段间隔为(window_time)/(segments_per_window)
- 当一个段到期时，在该段内的请求被加到当前段

`AddSlidingWindowLimiter`方法配置一个滑动窗口限制器。

```csharp
builder.Services.AddRateLimiter(rateLimiterOptions =>
{
    rateLimiterOptions.AddSlidingWindowLimiter("sliding", options =>
    {
        options.PermitLimit = 10;
        options.Window = TimeSpan.FromSeconds(10);
        options.SegmentsPerWindow = 2;
        options.QueueProcessingOrder = QueueProcessingOrder.OldestFirst;
        options.QueueLimit = 5;
    });
});
```

## 令牌桶限制器

令牌桶算法与滑动窗口相似，但不是添加过期段中的请求，而是在每个补给周期后添加固定数量的令牌。

令牌的总数永远不会超过令牌限制。

`AddTokenBucketLimiter`方法配置一个令牌桶限制器。

```csharp
builder.Services.AddRateLimiter(rateLimiterOptions =>
{
    rateLimiterOptions.AddTokenBucketLimiter("token", options =>
    {
        options.TokenLimit = 100;
        options.QueueProcessingOrder = QueueProcessingOrder.OldestFirst;
        options.QueueLimit = 5;
        options.ReplenishmentPeriod = TimeSpan.FromSeconds(10);
        options.TokensPerPeriod = 20;
        options.AutoReplenishment = true;
    });
});
```

当`AutoReplenishment`为`true`时，一个内部计时器将每个`ReplenishmentPeriod`执行一次并补充令牌。

## 并发限制器

并发限制器是最直接的算法，它仅限制并发请求的数量。

`AddConcurrencyLimiter`方法配置一个并发限制器。

```csharp
builder.Services.AddRateLimiter(rateLimiterOptions =>
{
    rateLimiterOptions.AddConcurrencyLimiter("concurrency", options =>
    {
        options.PermitLimit = 10;
        options.QueueProcessingOrder = QueueProcessingOrder.OldestFirst;
        options.QueueLimit = 5;
    });
});
```

在这种情况下没有时间成分参与。唯一的参数是并发请求的数量。

## 在您的API中使用速率限制

现在我们已经配置了我们的速率限制策略，让我们看看我们如何在我们的API中使用它们。

在控制器和极简API端点之间有轻微的差异，所以我将在不同的示例中介绍它们。

**控制器**

要在控制器上添加速率限制，我们使用`EnableRateLimiting`和`DisableRateLimiting`属性。

`EnableRateLimiting`可以应用于控制器或单独的端点上。

```csharp
[EnableRateLimiting("fixed")]
public class TransactionsController
{
    private readonly ISender _sender;

    public TransactionsController(ISender sender)
    {
        _sender = sender;
    }

    [EnableRateLimiting("sliding")]
    public async Task<IActionResult> GetTransactions()
    {
        return Ok(await _sender.Send(new GetTransactionsQuery()));
    }

    [DisableRateLimiting]
    public async Task<IActionResult> GetTransactionById(int id)
    {
        return Ok(await _sender.Send(new GetTransactionByIdQuery(id)));
    }
}
```

在前面的示例中：

- `TransactionsController`中的所有端点将使用**固定窗口**策略
- `GetTransactions`端点将使用**滑动窗口**策略
- `GetTransactionById`端点将不应用任何速率限制

**极简APIs**

在极简API端点中，您可以通过调用`RequireRateLimiting`并指定策略名称来配置速率限制策略。

我们在此示例中使用**令牌桶**策略。

```csharp
app.MapGet("/transactions", async (ISender sender) =>
{
    return Results.Ok(await sender.Send(new GetTransactionsQuery()));
})
.RequireRateLimiting("token");
```

## 结束语

很棒，我们可以快速地在ASP.NET Core中引入**速率限制**。

您可以从现有的一个速率限制算法中选择：

- 固定窗口
- 滑动窗口
- 令牌桶
- 并发

如果您想了解更多关于速率限制的信息，这里有一些资源：

- [速率限制模式](https://learn.microsoft.com/en-us/azure/architecture/patterns/rate-limiting-pattern)
- [为 .NET 宣布速率限制](https://devblogs.microsoft.com/dotnet/announcing-rate-limiting-for-dotnet/)

我很兴奋能在我的项目中尝试速率限制。

---
