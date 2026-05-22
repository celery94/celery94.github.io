---
pubDatetime: 2026-05-22T07:42:04+08:00
title: "ASP.NET Core 限流：从 429 到 Redis 的生产配置"
description: "ASP.NET Core 内置了限流中间件，但要在生产环境用好，还需要选对算法、显式返回 429、写入 Retry-After、按用户或 API Key 分区，并在多实例部署时补上 Redis 共享计数。"
tags: ["DotNet", "ASP.NET Core", "Rate Limiting", "Web API"]
slug: "aspnet-core-rate-limiting-net10-guide"
ogImage: "../../assets/818/01-cover.png"
source: "https://codewithmukesh.com/blog/rate-limiting-aspnet-core/"
---

限流，意思是限制某个调用方在一段时间内能发多少请求。它的作用很直接：在请求进入昂贵逻辑之前，先把异常流量挡住，避免数据库、第三方 API 或长耗时任务被单个用户拖垮。

Mukesh Murugan 这篇文章把 ASP.NET Core .NET 10 的限流讲得很完整：四种内置算法怎么选，`AddRateLimiter` 和 `UseRateLimiter` 怎么接，为什么拒绝时要返回 `429 Too Many Requests`，以及多实例部署为什么需要 Redis。Microsoft Learn 的 .NET 10 文档也确认，ASP.NET Core 提供了固定窗口、滑动窗口、令牌桶和并发限制四类限流器，并支持把策略挂到具体端点上。

## 先看一个场景

原文开头举了一个很真实的例子：一个免费用户对 pricing endpoint 写了循环请求。这个端点每次会访问 PostgreSQL，调用 Stripe 取套餐信息，还会预热缓存。三十秒内，数据库 CPU 到了 90%，其他客户开始超时。

这类问题靠扩容或缓存只能缓一阵。更直接的做法是在端点前面放限流器，超过规则的调用直接返回 429，后面的数据库和外部 API 根本不用参与。

ASP.NET Core 的限流中间件来自 `Microsoft.AspNetCore.RateLimiting`。单实例场景不需要第三方包，基本接法是：

```csharp
using Microsoft.AspNetCore.RateLimiting;
using System.Threading.RateLimiting;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;

    options.AddTokenBucketLimiter("public-api", opt =>
    {
        opt.TokenLimit = 100;
        opt.TokensPerPeriod = 100;
        opt.ReplenishmentPeriod = TimeSpan.FromMinutes(1);
        opt.QueueLimit = 0;
        opt.AutoReplenishment = true;
    });
});

var app = builder.Build();

app.UseRouting();
app.UseRateLimiter();

app.MapGet("/api/prices", () => Results.Ok())
   .RequireRateLimiting("public-api");

app.Run();
```

这里有两个点别省：`UseRateLimiter()` 要进入请求管线；如果你按端点挂策略，它要放在 `UseRouting()` 后面。`RejectionStatusCode` 也要显式设成 429，因为原文指出默认值是 503，这会让客户端误以为服务不可用。

## 四种算法怎么选

ASP.NET Core 提供的四种算法解决的问题不一样。

| 场景                    | 推荐算法                       | 原因                                           |
| ----------------------- | ------------------------------ | ---------------------------------------------- |
| 公开 REST API           | Token Bucket                   | 允许短时突发，同时控制长期平均速率             |
| 内部服务调用            | Fixed Window                   | 成本低，行为简单，可信网络里边界突发通常可接受 |
| 登录、OTP、重置密码     | Sliding Window                 | 更适合需要连续时间窗口约束的安全敏感端点       |
| 文件上传、报表、AI 推理 | Concurrency Limiter            | 限制同时进行的高成本工作                       |
| 多租户付费 API          | 按 API Key 分区的 Token Bucket | 不同套餐可以配置不同桶容量                     |

Fixed Window 是固定窗口。比如一分钟最多 1000 次，到了下一分钟计数清零。它简单便宜，但有边界突发问题：客户端可以在 59 秒打满一次，再在下一分钟 0 秒打满一次，短时间内接近两倍流量。

Sliding Window 把窗口切成多个小段，随着时间滑动回收旧段计数。它比固定窗口更平滑，适合登录和验证码这类端点。

Token Bucket 可以理解为桶里放令牌，请求进来要拿一个令牌，系统按固定节奏补令牌。它允许合理突发，也能约束长期平均速率，所以原文建议把它作为公开 API 的默认选择。

Concurrency Limiter 限的是“正在执行中的请求数量”。它不关心一分钟来了多少次，只关心当前同时有多少个高成本任务在跑。文件上传、PDF 渲染、AI 推理更适合这种限制。

## 拒绝响应要像 API

限流命中时，客户端最需要知道两件事：这次被拒绝了，以及多久之后再试。原文建议在 `OnRejected` 里返回 ProblemDetails，并写入 `Retry-After`。

```csharp
builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;

    options.OnRejected = async (context, cancellationToken) =>
    {
        var httpContext = context.HttpContext;

        if (context.Lease.TryGetMetadata(
                MetadataName.RetryAfter,
                out var retryAfter))
        {
            httpContext.Response.Headers.RetryAfter =
                ((int)retryAfter.TotalSeconds).ToString();
        }

        var problem = new ProblemDetails
        {
            Status = StatusCodes.Status429TooManyRequests,
            Title = "Too many requests",
            Detail = "Rate limit exceeded. Retry after the indicated delay.",
            Instance = httpContext.Request.Path
        };

        await httpContext.Response.WriteAsJsonAsync(
            problem,
            cancellationToken);
    };
});
```

`Retry-After` 是客户端退避重试的依据。没有这个头，很多客户端会立刻重试，结果把剩余容量继续消耗掉。

## 按调用方分区

只注册一个全局限流器，所有人会共用一个计数器。更常见的做法是按用户、IP 或 API Key 分区。分区的意思是给不同调用方各自分配一套计数。

```csharp
options.GlobalLimiter =
    PartitionedRateLimiter.Create<HttpContext, string>(httpContext =>
    {
        var userId = httpContext.User.Identity?.IsAuthenticated == true
            ? httpContext.User.FindFirst("sub")?.Value ?? "unknown"
            : "anonymous";

        return RateLimitPartition.GetTokenBucketLimiter(
            partitionKey: userId,
            factory: _ => new TokenBucketRateLimiterOptions
            {
                TokenLimit = 200,
                TokensPerPeriod = 200,
                ReplenishmentPeriod = TimeSpan.FromMinutes(1),
                QueueLimit = 0,
                AutoReplenishment = true
            });
    });
```

这里要小心两类问题。

如果按 IP 分区，而应用在反向代理后面，先确认 forwarded headers 已经配置好。否则 `RemoteIpAddress` 可能一直是代理地址，所有用户会挤进同一个桶。

如果按租户头或其他用户输入分区，必须先验证这个值。原文提醒，直接把 `X-Tenant-Id` 这种未验证输入当分区键，会让攻击者制造大量唯一键，导致内存里的 limiter 实例暴涨。

## 多实例要共享计数

ASP.NET Core 内置限流器是内存内、单实例的。应用只有一个节点时没问题。部署到多个副本后，每个副本都有自己的计数器。

原文给出的关键结论是：如果配置 `PermitLimit = 100`，部署 3 个副本，实际集群上限会变成 `100 x 3 = 300`。负载均衡和会话粘滞都不能让计数自动同步。

需要跨实例统一限流时，可以接 Redis backplane。原文使用的是 `RedisRateLimiting.AspNetCore`，版本锚点是 `1.2.0`。这属于第三方包，因为 ASP.NET Core 内置中间件本身不负责分布式计数。

```bash
dotnet add package RedisRateLimiting.AspNetCore
dotnet add package StackExchange.Redis
```

生产环境里，Redis 连接也要和普通基础设施一样监控：连接失败、延迟变高、Redis 重启，都可能影响限流判断。

## 需要测试什么

限流配置不适合只靠肉眼检查。至少写集成测试确认两件事：

- 超过上限后返回 `429 Too Many Requests`
- 响应里有 `Retry-After`

测试时还要注意计数器生命周期。原文提到，limiter 通常是单例，多个测试共享同一个 `WebApplicationFactory` 时，计数可能互相污染。可以为每个测试创建独立 factory，或给测试端点加一个每次不同的分区头。

## 上线前检查

可以按这张清单过一遍：

- `RejectionStatusCode` 明确设为 429
- `OnRejected` 写入 `Retry-After`
- 拒绝响应返回 ProblemDetails，并带 trace 信息
- 日志里记录被拒绝的调用方身份
- 多实例部署已经接 Redis，或明确接受按实例放大的上限
- IP 分区前已经配置并验证 forwarded headers
- 租户或 API Key 查询做了缓存，别每个请求都查数据库
- 用户输入成为分区键前已经通过白名单校验
- 健康检查、指标、OpenAPI 文档这类端点按需使用 `[DisableRateLimiting]`
- 集成测试覆盖 429 和 `Retry-After`
- 做过压力测试，确认拒绝比例符合配置

## 结语

ASP.NET Core 的限流中间件已经覆盖了大多数 API 场景。真正容易出问题的地方在细节：算法选错、拒绝时返回 503、忘写 `Retry-After`、未分区、多实例下还用内存计数。

如果只是给公开 API 加一个默认保护，可以从 Token Bucket 开始。如果是登录、验证码、密码重置，用 Sliding Window。高成本任务优先看 Concurrency Limiter。只要服务跑在多个副本上，就要认真处理共享计数。

## 参考

- [Rate Limiting in ASP.NET Core (.NET 10) - Complete Guide](https://codewithmukesh.com/blog/rate-limiting-aspnet-core/)
- [Rate limiting middleware in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/performance/rate-limit?view=aspnetcore-10.0)
- [示例源码：rate-limiting-aspnet-core](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/05-api-security/rate-limiting-aspnet-core)
