---
pubDatetime: 2026-06-08T07:56:14+08:00
title: "ASP.NET Core Middleware：把请求管道顺序讲清楚"
description: "ASP.NET Core middleware 看起来只是几行 app.Use，但真正影响线上行为的是管道模型、注册顺序、短路机制和 DI 生命周期。这篇用请求进入与响应返回的视角，把自定义中间件、IMiddleware、Correlation ID 和请求耗时记录讲清楚。"
tags: ["ASP.NET Core", ".NET", "Middleware", "C#"]
slug: "aspnet-core-middleware-request-pipeline"
ogImage: "../../assets/853/01-cover.png"
source: "https://www.devleader.ca/2026/06/07/aspnet-core-middleware-building-and-using-the-request-pipeline"
---

ASP.NET Core middleware 是很多 Web API 行为的底层形状：异常处理、静态文件、路由、CORS、认证、授权、限流、压缩、缓存，最终都会落到请求管道里。写 `app.Use(...)` 不难，难的是知道它会在什么时候执行、什么时候该调用 `next()`、放错顺序会带来什么后果。

Dev Leader 这篇文章把 middleware 当成一条双向管道来讲：请求进入时按注册顺序经过每一层，响应返回时再反向经过这些层。理解这个模型之后，很多“为什么我的认证/授权/CORS/日志不生效”的问题会变得好排查得多。

## 管道模型

每个 middleware 都拿到两个东西：当前请求的 `HttpContext`，以及代表下一个组件的 `RequestDelegate next`。调用 `await next(context)`，请求继续向后走；不调用，管道就在当前 middleware 结束，响应直接返回。

这个模型最容易用“套娃”理解：外层 middleware 包住内层 middleware，最里面才是 controller action 或 minimal API endpoint。它有两个动作窗口：

- 调用 `next()` 之前，可以处理请求，比如补 header、检查路径、创建日志 scope。
- 调用 `next()` 之后，可以处理响应，比如记录耗时、压缩响应体、根据状态码写日志。

文章里用 request timing 举了一个典型例子：进入 middleware 时启动计时器，`await next(context)` 之后停止计时器，再记录整个下游管道耗时。这个“前后各一次”的机会，就是 middleware 比普通 handler 更适合做横切关注点的原因。

## 注册方式

ASP.NET Core 常见的注册方式有几类，它们的语义并不一样。

`app.Use` 是最常用的形式：它可以在执行前后处理请求/响应，也可以决定是否调用下一个 middleware。简单安全响应头、轻量路径过滤、临时实验逻辑都可以先用它写。

```csharp
app.Use(async (context, next) =>
{
    context.Response.Headers["X-Frame-Options"] = "DENY";
    context.Response.Headers["X-Content-Type-Options"] = "nosniff";

    await next(context);
});
```

`app.Run` 是终止型 middleware。它没有 `next` 参数，执行到这里就不会再继续往后走。所以它通常只适合作为最后的 fallback。

`app.Map` 会按路径前缀分支，`app.MapWhen` 会按谓词分支，`app.UseWhen` 则是条件性插入一段 middleware，但条件分支结束后主管道还会继续。这几个 API 很适合把健康检查、管理端路径、某类特殊请求单独处理。

## 顺序很关键

Middleware 不是一个无序集合。注册顺序就是请求进入时的执行顺序，响应返回时则反过来执行。这个细节会直接影响安全性、性能和可观测性。

一条常见的 Web API 管道大概会长这样：

```csharp
app.UseExceptionHandler();
app.UseHsts();
app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRouting();
app.UseCors();
app.UseAuthentication();
app.UseAuthorization();
app.UseRateLimiter();
app.MapControllers();
```

这个顺序背后都有原因。`UseExceptionHandler` 应该尽量靠前，这样才能包住后面的组件并捕获下游异常。`UseRouting` 要在认证授权之前匹配 endpoint，CORS 通常放在 routing 之后、authorization 之前。`UseAuthentication` 必须在 `UseAuthorization` 之前，因为授权之前需要先把 `HttpContext.User` 填好。

原文特别提醒：顺序错误经常不是“马上崩掉”，而是变成更隐蔽的行为错误。例如授权先于认证时，授权逻辑拿到的用户主体可能没有被正确填充；异常处理中间件放得太晚时，前面组件抛出的异常不会被统一处理。

## 什么时候写类

几行以内的简单逻辑，用 inline `app.Use` 没问题。但只要逻辑开始需要依赖注入、复用、测试，最好把它挪到类里。原文推荐的方向是 `IMiddleware`。

`IMiddleware` 只要求实现一个方法：

```csharp
public sealed class RequestTimingMiddleware : IMiddleware
{
    private readonly ILogger<RequestTimingMiddleware> _logger;

    public RequestTimingMiddleware(ILogger<RequestTimingMiddleware> logger)
    {
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context, RequestDelegate next)
    {
        var stopwatch = Stopwatch.StartNew();

        try
        {
            await next(context);
        }
        finally
        {
            stopwatch.Stop();

            _logger.LogInformation(
                "HTTP {Method} {Path} responded {StatusCode} in {ElapsedMilliseconds}ms",
                context.Request.Method,
                context.Request.Path,
                context.Response.StatusCode,
                stopwatch.ElapsedMilliseconds);

            if (!context.Response.HasStarted)
            {
                context.Response.Headers["X-Response-Time-Ms"] =
                    stopwatch.ElapsedMilliseconds.ToString();
            }
        }
    }
}
```

注册时分两步：先把 middleware 注册进 DI，再把它放进管道。

```csharp
builder.Services.AddTransient<RequestTimingMiddleware>();

app.UseMiddleware<RequestTimingMiddleware>();
```

这里的 `finally` 很重要。下游 middleware 或 controller 抛异常时，日志仍然应该写出来；如果响应 header 还没开始发送，也可以继续补上 `X-Response-Time-Ms`。

## Correlation ID

Correlation ID 是一个很实用的生产环境例子。每个请求都有一个唯一 ID：客户端传了 `X-Correlation-Id` 就沿用，没有传就由服务端生成。这个 ID 会写回响应 header，也会放进 logging scope，让同一个请求里的日志能串起来。

核心流程可以压缩成四步：

1. 从请求 header 读取 `X-Correlation-Id`。
2. 如果为空，生成一个新的 GUID。
3. 写入响应 header 和 `HttpContext.Items`。
4. 用 `ILogger.BeginScope` 把它带进结构化日志。

原文给出的实现使用 `IMiddleware`，并建议尽早注册，最好在 routing、authentication 和 controller 执行之前，这样后续所有日志都能拿到同一个 correlation ID。

```csharp
builder.Services.AddTransient<CorrelationIdMiddleware>();

app.UseMiddleware<CorrelationIdMiddleware>();
app.UseExceptionHandler();
app.UseRouting();
```

如果你用 Serilog 或其他结构化日志 provider，还要确认它支持并启用了 scope，否则 `BeginScope` 里的字段不会出现在最终日志中。

## 短路不是异常

不是所有 middleware 都应该调用 `next()`。有些场景就是要在当前层直接返回，比如健康检查、IP allowlist、缓存命中、限流拒绝。

```csharp
app.Use(async (context, next) =>
{
    var remoteIp = context.Connection.RemoteIpAddress?.ToString();
    var allowedIps = new[] { "127.0.0.1", "::1" };

    if (context.Request.Path.StartsWithSegments("/admin") &&
        !allowedIps.Contains(remoteIp))
    {
        context.Response.StatusCode = StatusCodes.Status403Forbidden;
        await context.Response.WriteAsync("Access denied.");
        return;
    }

    await next(context);
});
```

关键是要把短路当成明确设计，而不是漏掉 `next()`。如果一个 middleware 本应继续管道却没有调用 `next()`，后面的 routing、controller、日志和清理逻辑都不会执行，排查起来会很绕。

## 内置组件

ASP.NET Core 自带了很多 middleware。知道它们已经存在，可以少写不少自定义代码。

`UseStaticFiles` 会在 routing 之前服务 `wwwroot` 文件；`UseCors` 处理跨域预检和响应 header；`UseResponseCompression` 处理 gzip/brotli 压缩；`UseRateLimiter` 应用通过 `AddRateLimiter` 定义的限流策略；`UseOutputCache` 缓存 endpoint 响应；`UseRequestLocalization` 根据 `Accept-Language` 等信息设置 culture。

这些组件本质上都遵循同一个模型：在管道里包住后续处理逻辑，根据请求和响应生命周期添加横切行为。理解自定义 middleware，也就更容易理解这些内置组件为什么必须按特定顺序摆放。

## 和过滤器的边界

Middleware 适合“整个请求/响应生命周期”级别的关注点：请求耗时、Correlation ID、HTTPS 重定向、压缩、缓存、静态文件、健康检查、minimal API。它们不只服务 MVC action。

Action filter 更适合 MVC action 语境里的事情：模型状态处理、只针对 controller 的响应包装、依赖 action metadata 的逻辑。Filter 发生在 routing 和 model binding 之后，能看到 MVC 上下文；middleware 更早、更广，但不知道某些 MVC 细节。

一个实用判断是：如果行为应该覆盖静态文件、健康检查和 minimal API，就放在 middleware；如果它只关心 controller/action，并且需要 MVC 元数据，就放在 filter。

## 实践建议

写 middleware 时，可以按这几个问题自检：

- 它是不是横切关注点，而不是业务规则？
- 它是否必须覆盖所有请求，还是只覆盖 MVC action？
- 它有没有明确决定调用或不调用 `next()`？
- 它是否需要放在 routing、CORS、authentication、authorization 的特定位置？
- 它是否需要依赖注入、复用或单元测试？
- 它写响应 header 时，有没有考虑 `context.Response.HasStarted`？

原文最有价值的点，不是列了多少 API，而是把 middleware 还原成一条双向执行链。请求进入时顺序执行，响应返回时反向经过；有些组件会短路，有些组件要包住下游；复杂逻辑用 `IMiddleware` 接入 DI 和测试。把这几个点记住，ASP.NET Core 管道就不再是一串容易凭感觉排序的 `app.Use...`。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [ASP.NET Core Middleware: Building and Using the Request Pipeline](https://www.devleader.ca/2026/06/07/aspnet-core-middleware-building-and-using-the-request-pipeline)
- [ASP.NET Core Middleware - Microsoft Learn](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/middleware/?view=aspnetcore-10.0)
