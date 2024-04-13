---
pubDatetime: 2024-04-13
tags: ["Rate Limiting", "ASP.NET Core"]
source: https://www.milanjovanovic.tech/blog/advanced-rate-limiting-use-cases-in-dotnet?utm_source=Twitter&utm_medium=social&utm_campaign=08.04.2024
author: Milan Jovanović
title: 在 .NET 中高级限流应用场景
description: 限流是指限制对您的应用程序的请求数量。它通常在特定时间窗口内或基于其他一些标准应用。
---

> ## 摘录
>
> 限流是指限制对您的应用程序的请求数量。它通常在特定时间窗口内或基于其他一些标准应用。
>
> 原文 [**Advanced Rate Limiting Use Cases In .NET**](https://www.milanjovanovic.tech/blog/advanced-rate-limiting-use-cases-in-dotnet?utm_source=Twitter&utm_medium=social&utm_campaign=08.04.2024) 由 Milan Jovanović 撰写。

---

**限流**是指限制对您的应用程序的请求数量。它通常在特定时间窗口内或基于其他标准应用。

它有几个帮助原因：

- 提高安全性
- 防护DDoS攻击
- 防止应用服务器过载
- 通过防止不必要的资源消耗来降低成本

**.NET 7** 带来了**内置限流器**，但您需要知道如何正确实施它。否则您可能会使系统停滞不前 - 我们不希望这样。

在本周的新闻通讯中，我会教您：

- 如何按 **IP 地址** 限制用户
- 如何按他们的 **身份** 限制用户
- 如何在 **反向代理** 上应用 **限流**

所以，让我们深入了解！

## .NET 7 中的内置限流

从 .NET 7 开始，我们可以在 `Microsoft.AspNetCore.RateLimiting` 命名空间中使用内置的**限流中间件**。API 非常直接，您可以通过几行代码创建一个限流策略。

我们可以使用四种**限流算法**之一：

- 固定窗口
- 滑动窗口
- 令牌桶
- 并发性

以下是通过调用 `AddTokenBucketLimiter` 方法来定义**限流策略**的方法：

```csharp
builder.Services.AddRateLimiter(rateLimiterOptions =>
{
    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;

    rateLimiterOptions.AddTokenBucketLimiter("token", options =>
    {
        options.TokenLimit = 1000;
        options.ReplenishmentPeriod = TimeSpan.FromHours(1);
        options.TokensPerPeriod = 700;
        options.AutoReplenishment = true;
    });
});
```

现在您可以在您的端点或控制器上引用 `token` 限流策略。

您还必须将 `RateLimitingMiddleware` 添加到请求管道：

```csharp
app.UseRateLimiter();
```

您可以在[**这里了解更多关于 .NET 7 中的限流**](https://www.milanjovanovic.tech/blog/how-to-use-rate-limiting-in-aspnet-core)，所以我不会深入基础原理。

## 按 IP 地址限流用户

我刚才展示的方法存在一个**问题** - **限流策略**是全局的并且**适用于所有用户**。

大多数时候，您不希望这样做。限流应该是细粒度的并且适用于**单个用户**。

幸运的是，您可以通过创建 `RateLimitPartition` 实现这一点。

`RateLimitPartition` 有两个组件：

- 分区键
- 限流策略

以下是如何定义具有固定窗口策略的限流器，并且**分区键**是用户的**IP 地址**：

```csharp
builder.Services.AddRateLimiter(options =>
{
    options.AddPolicy("fixed-by-ip", httpContext =>
        RateLimitPartition.GetFixedWindowLimiter(
            partitionKey: httpContext.Connection.RemoteIpAddress?.ToString(),
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 10,
                Window = TimeSpan.FromMinutes(1)
            }));
});
```

按**IP 地址**限流可以为**未经认证的用户**提供一个好的安全层。您不知道谁在访问您的系统，并且不能应用更细致的限流。这可以帮助保护系统免受试图进行 DDoS 攻击的恶意用户的伤害。

您还可以使用 `CreateChained` API [**创建链式限流器**](https://learn.microsoft.com/en-us/aspnet/core/performance/rate-limit?view=aspnetcore-7.0#create-chained-limiters)。它允许您传入多个 `PartitionedRateLimiter`，这些限流器组合成一个 `PartitionedRateLimiter`。链式限流器依次（一个接一个）运行所有输入限流器。

如果您的应用程序运行在**反向代理**后面，您需要确保不要限制代理的 IP 地址。反向代理通常使用 `X-Forwarded-For` 头**转发**原始 IP 地址。因此，您可以将其用作**分区键**：

```csharp
builder.Services.AddRateLimiter(options =>
{
    options.AddPolicy("fixed-by-ip", httpContext =>
        RateLimitPartition.GetFixedWindowLimiter(
            httpContext.Request.Headers["X-Forwarded-For"].ToString(),
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 10,
                Window = TimeSpan.FromMinutes(1)
            }));
});
```

## 按身份限流用户

如果您要求用户**认证**以访问您的 API，您可以确定当前用户是谁。然后您可以使用用户的**身份**作为 `RateLimitPartition` 的**分区键**。

以下是您如何创建这样的限流策略：

```csharp
builder.Services.AddRateLimiter(options =>
{
    options.AddPolicy("fixed-by-user", httpContext =>
        RateLimitPartition.GetFixedWindowLimiter(
            partitionKey: httpContext.User.Identity?.Name?.ToString(),
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 10,
                Window = TimeSpan.FromMinutes(1)
            }));
});
```

我使用 `HttpContext` 上的 `User.Identity` 值获取当前用户的 `Name` 声明。这通常对应于 JWT 内部的 `sub` 声明 - 即用户标识符。

## 在反向代理上应用限流

在健壮的实现中，你想在请求触及你的 API 之前在**反向代理**级别上**限流**。如果您有一个分布式系统，这是一个要求。否则，您的系统将无法正确工作。

有许多反向代理实现可供选择。

**YARP** 是一个与 .NET 集成良好的反向代理。这不足为奇，因为它是用C#写的。您可以在[**这里了解更多关于使用 YARP 构建 API 网关**](https://www.milanjovanovic.tech/blog/implementing-an-api-gateway-for-microservices-with-YARP) 的信息。

要在 **YARP** 上实施反向代理的限流，您需要：

- 定义限流策略（在前面的示例中已覆盖）
- 为 YARP 设置中的路由配置 `RateLimiterPolicy`

```json
"products-route": {
  "ClusterId": "products-cluster",
  "RateLimiterPolicy": "sixty-per-minute-fixed",
  "Match": {
    "Path": "/products/{**catch-all}"
  },
  "Transforms": [
    { "PathPattern": "{**catch-all}" }
  ]
}
```

内置限流中间件使用**内存中**的存储来跟踪请求数量。如果你想在高可用性设置中运行你的反向代理，你将需要使用**分布式缓存**。值得研究的一个好选择是使用 [**Redis 后端进行限流。**](https://github.com/cristipufu/aspnetcore-redis-rate-limiting)

## 结束思考

使用 `PartitionedRateLimiter`，您可以轻松创建细粒度的限流策略。

两种常见的方法是：

- 按**IP 地址**限流
- 按**用户标识符**限流

看到 .NET 团队推出限流功能，我真的很兴奋。但是，当前实施方式有其缺点。主要问题是它只在**内存中**工作。对于**分布式**解决方案，您需要自己实现一些东西或使用外部库。

您可以使用 **YARP** 反向代理来构建健壮且可扩展的分布式系统。并且只需几行代码即可在反向代理级别添加**限流**。我在我的系统中广泛使用它。

---
