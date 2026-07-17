---
pubDatetime: 2026-07-17T07:54:12+08:00
title: "ASP.NET Core 内置 Rate Limiter：不装库也能做限流"
description: "ASP.NET Core 自 .NET 7 起内置四种限流算法，配合 GlobalLimiter 和分区键可以实现按用户、IP 或 API Key 的精细限流。本文覆盖算法选择、分区策略、429 响应和队列配置，附完整 C# 代码。"
tags: ["ASP.NET Core", "Rate Limiting", "C#", ".NET", "限流"]
slug: "rate-limiting-aspnet-core-built-in"
ogImage: "../../assets/948/01-cover.png"
source: "https://thecodeman.net/posts/rate-limiting-in-aspnet-core-built-in-ratelimiter"
---

有个客户的登录端点稳定跑了两年，然后一个撞库脚本在周末发现了它，每秒几千个请求砸上去。端点没有以有趣的方式崩溃——它只是把整个数据库一起拖垮了，所有功能都慢到爬行，因为它们共享同一个连接池。

修复方案不是加服务器，是加一个限制。那个端点从任何单个 IP 每分钟接收请求都不该超过个位数，但当时什么都没拦。修复手段就是限流。在 ASP.NET Core 里，这件事不需要再装第三方库了。

**ASP.NET Core 内置限流**从 .NET 7 开始就内置在框架里。`Microsoft.AspNetCore.RateLimiting` 里的 `RateLimiter` 中间件提供四种算法——固定窗口、滑动窗口、令牌桶和并发——用这几行配置就能保护端点。

## 四种限流器，各自适合什么场景

内置中间件提供了四种算法，它们不可互换。每种对流量塑形的方式不同，选错的结果要么太松，要么无意中伤到正常用户。

**固定窗口**按固定时间片计数——每分钟 100 次，每个整分钟清零。简单，但有个已知弱点：调用方可以在 11:59:59 发 100 次，12:00:00 再发 100 次，一秒多钟内溜过 200 次。

**滑动窗口**通过把窗口切分成多个段来修复这个问题，段随时间向前滚动，窗口边界的突发会被近期的计数兜住。开销稍高，公平性更好。

**令牌桶**模拟一个以稳定速率补充令牌的桶。每个请求消耗一个令牌，桶空了就受限。适合需要**允许突发**的场景——用户可以一次花光整桶令牌，然后等它慢慢补充。

**并发**完全不按时间计数。它限制的是**同时运行**的请求数。适合昂贵的端点——报表生成、文件导出——这里的问题不是速率，而是一次跑十个。

## 最小可用配置

两步：注册服务，加中间件。一个固定窗口限流器，对所有端点生效：

```csharp
using System.Threading.RateLimiting;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRateLimiter(options =>
{
    options.AddFixedWindowLimiter("fixed", limiter =>
    {
        limiter.PermitLimit = 100;              // 100 次请求
        limiter.Window = TimeSpan.FromMinutes(1); // 每分钟
        limiter.QueueProcessingOrder =
            QueueProcessingOrder.OldestFirst;
        limiter.QueueLimit = 0;  // 立即拒绝，不排队
    });
});

var app = builder.Build();

app.UseRateLimiter();

app.MapGet("/reports", () => Results.Ok("数据就绪"))
   .RequireRateLimiting("fixed");

app.Run();
```

`RequireRateLimiting("fixed")` 把命名策略绑定到端点。中间件存在不等于限流生效——你得显式为端点选择策略。

一个容易踩的坑：**`UseRateLimiter` 要放在路由之后**，但又得早到能保护后面真正干活的部分。在 Minimal API 里路由是隐式的，所以放在 `var app = builder.Build()` 之后就行。如果你有 `UseAuthentication` / `UseAuthorization`，要主动决定在认证前还是认证后限流——认证**前**限流可以保护认证系统本身免于被攻击，这对登录端点通常是你想要的。

换成滑动窗口只需要一行改动：

```csharp
builder.Services.AddRateLimiter(options =>
{
    options.AddSlidingWindowLimiter("sliding", limiter =>
    {
        limiter.PermitLimit = 100;
        limiter.Window = TimeSpan.FromMinutes(1);
        limiter.SegmentsPerWindow = 6; // 6 个滚动段，每段 10 秒
        limiter.QueueLimit = 0;
    });
});
```

## 真正重要的部分：分区

单个全局限流器几乎不是你想要的。"所有用户加起来每分钟 100 次"意味着一个吵闹的客户端可以吃光整个预算，饿死所有人。你需要的是**按用户**、或按 IP、或按 API Key 来限流。这就是分区做的事——给每个调用方自己的配额桶。

下面是一个全局限流器，按已认证用户分区，匿名调用方回退到 IP：

```csharp
builder.Services.AddRateLimiter(options =>
{
    options.GlobalLimiter =
        PartitionedRateLimiter.Create<HttpContext, string>(
            context =>
    {
        var partitionKey = context.User.Identity?.Name
            ?? context.Connection.RemoteIpAddress?.ToString()
            ?? "anonymous";

        return RateLimitPartition.GetFixedWindowLimiter(
            partitionKey, _ =>
            new FixedWindowRateLimiterOptions
            {
                PermitLimit = 100,
                Window = TimeSpan.FromMinutes(1),
                QueueLimit = 0
            });
    });

    options.RejectionStatusCode =
        StatusCodes.Status429TooManyRequests;
});
```

`GlobalLimiter` 在**每个请求**上执行，不需要 `RequireRateLimiting`。分区键是整件事的关键：选一个能标识你要限流的调用方的东西。已登录用户用用户名，匿名用 IP，公开 API 用 API Key。搞错了——比如选了一个每个请求都相同的值——你就又回到单一全局桶了。

注意 `RejectionStatusCode`。默认拒绝状态码是 **503**，这具有误导性——被限流不是服务器错误，是客户端请求频率太高。设成 **429 Too Many Requests**，客户端和监控系统才能正确解读。

分区键里还有两件事要搞对。第一，`RemoteIpAddress` 在反向代理或 CDN 后面拿到的是**代理的 IP** 而不是客户端的——于是所有匿名调用方落进同一个分区，你的按 IP 限流悄无声息地变成了全局限流。加上 `UseForwardedHeaders` 并信任你的代理，让 `RemoteIpAddress` 反映 `X-Forwarded-For` 里的真实客户端。第二，`User.Identity?.Name` 只有在认证执行后才有值，所以按用户分区需要 `UseRateLimiter` 放在 `UseAuthentication` **之后**——和前面登录端点限流的顺序正相反。按端点选顺序，或者跑两个策略。

## 给客户端一个正经的 429

一个裸 429 空 body 是不礼貌的。好的 429 告诉调用方要等多久。令牌桶和窗口限流器通过元数据暴露重试延迟，用 `OnRejected` 来捕获：

```csharp
builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode =
        StatusCodes.Status429TooManyRequests;

    options.OnRejected = async (context, cancellationToken) =>
    {
        if (context.Lease.TryGetMetadata(
            MetadataName.RetryAfter, out var retryAfter))
        {
            context.HttpContext.Response.Headers.RetryAfter =
                ((int)retryAfter.TotalSeconds).ToString();
        }

        context.HttpContext.Response.ContentType =
            "application/json";
        await context.HttpContext.Response.WriteAsJsonAsync(new
        {
            error = "请求过于频繁，请稍后重试。"
        }, cancellationToken);
    };

    options.AddTokenBucketLimiter("api", limiter =>
    {
        limiter.TokenLimit = 50;          // 桶容量 50
        limiter.TokensPerPeriod = 10;     // 每 10 秒...
        limiter.ReplenishmentPeriod =
            TimeSpan.FromSeconds(10);      // ...补充 10 个
        limiter.QueueLimit = 0;
        limiter.AutoReplenishment = true;
    });
});
```

`Retry-After` 头决定了客户端是体面地退避还是持续撞墙重试。

## 排队还是直接拒绝

每个限流器都有 `QueueLimit`。设为 `0`，超限请求立即拒绝——是公开 HTTP 端点的正确默认值，因为排队等待的调用方就是占用连接的调用方。设为大于零，超限请求会**等**一个许可证，按 `QueueProcessingOrder` 指定的顺序。

排队对并发限流器有意义——你宁愿让第十一个请求等一下，也不想直接拒绝它：

```csharp
options.AddConcurrencyLimiter("expensive-export", limiter =>
{
    limiter.PermitLimit = 5;   // 最多 5 个导出同时跑
    limiter.QueueLimit = 20;   // 最多 20 个排队等
    limiter.QueueProcessingOrder =
        QueueProcessingOrder.OldestFirst;
});
```

但对于登录端点，你需要 `QueueLimit = 0`。给撞库攻击排队等于让几千个连接开着等放行——你把限流变成了缓慢的连接泄露。

## 在端点上应用策略

两种方式：流式 API 或特性标注。Minimal API 用流式：

```csharp
var api = app.MapGroup("/api").RequireRateLimiting("api");

api.MapGet("/products", GetProducts);  // 继承 "api"
api.MapPost("/orders", CreateOrder);   // 继承 "api"

app.MapPost("/auth/login", Login)
   .RequireRateLimiting("login-strict"); // 自己的更严策略
```

Controller 上用特性，`[DisableRateLimiting]` 可以给受限制的 Controller 里某个 Action 打孔：

```csharp
[EnableRateLimiting("api")]
public class ProductsController : ControllerBase
{
    [HttpGet]
    public IActionResult List() => Ok(_service.All());

    [HttpGet("health")]
    [DisableRateLimiting] // 健康检查不应该被限流
    public IActionResult Health() => Ok("healthy");
}
```

## 诚恳的限制：这是单实例的

内置限流器把计数器存在**内存里，单进程内**。在负载均衡器后面跑三个 API 实例，每个实例独立执行限流——"每分钟 100 次"的上限在全集群变成实际约 300 次，而且取决于均衡器怎么分发流量还会不均匀。

对于单实例，或者"大致这么多就行"的粗粒度保护，这完全够用，也是我大多数时候用的。但如果你需要硬性的、集群范围的限制——比如付费 API 层级，限制数字写在合同里——内存限流器做不到。你需要 Redis 之类的分布式计数器来支持自定义 `RateLimiter`。在上线之前搞清楚你处于哪种情况，别等超额账单来的时候才发现。

## 参考

- [原文：Rate Limiting in ASP.NET Core Without a Library](https://thecodeman.net/posts/rate-limiting-in-aspnet-core-built-in-ratelimiter)
- [官方文档：ASP.NET Core Rate Limiting Middleware](https://learn.microsoft.com/en-us/aspnet/core/performance/rate-limit)
