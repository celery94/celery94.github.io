---
pubDatetime: 2026-08-29T19:55:00+08:00
title: "ASP.NET Core 请求超时：让取消真正传到底"
description: "ASP.NET Core 默认不会限制端点执行时间。本文用 .NET 8+ 内置中间件设置请求期限，并把取消信号传给 EF Core 与 HttpClient，附验证方法和排错边界。"
tags: ["ASP.NET Core", ".NET", "C#", "CancellationToken", "Resilience"]
slug: "aspnet-core-request-timeout-cancellation"
ogImage: "../../assets/1034/01-cover.jpg"
source: "https://milanjovanovic.tech/blog/your-aspnetcore-endpoints-dont-have-a-timeout"
---

一个 ASP.NET Core 接口执行了 30 秒，并不代表框架会在某个固定时刻替你结束它。Kestrel 有请求头、数据速率等传输层限制，反向代理也可能先返回超时，但应用里的端点代码默认没有统一的执行期限。

从 .NET 8 开始，可以用内置 Request Timeouts 中间件给请求设置期限。它的核心动作很克制：期限到达后取消 `HttpContext.RequestAborted`，再等待业务代码响应这个取消信号。数据库查询、外部 HTTP 调用和其他异步任务只有接收到同一个 `CancellationToken`，才有机会及时停下来。

所以，真正需要检查的是一条完整链路：

```text
请求期限
  -> HttpContext.RequestAborted
  -> 端点参数
  -> 应用服务
  -> EF Core / HttpClient / 消息客户端
```

下面用一个可运行的 Minimal API 示例把这条链路接起来。

## 先给一个端点设置 3 秒期限

前置条件是 .NET 8 或更高版本。新建项目：

```bash
dotnet new web -n RequestTimeoutDemo
cd RequestTimeoutDemo
```

把 `Program.cs` 替换为：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRequestTimeouts();

var app = builder.Build();

app.UseRequestTimeouts();

app.MapGet("/reports", async (CancellationToken cancellationToken) =>
{
    await Task.Delay(TimeSpan.FromSeconds(10), cancellationToken);
    return Results.Ok(new { status = "ready" });
})
.WithRequestTimeout(TimeSpan.FromSeconds(3));

app.Run();
```

这里有三个容易漏掉的点：

1. `AddRequestTimeouts` 只注册服务，不会自动给端点设置期限。
2. `UseRequestTimeouts` 把中间件加入请求管线。如果项目显式调用 `UseRouting`，它要放在 `UseRouting` 后面。
3. Minimal API 会把端点参数里的 `CancellationToken` 绑定到 `HttpContext.RequestAborted`。

启动应用时不要附加调试器：

```bash
dotnet run --no-launch-profile
```

根据终端显示的地址请求接口，例如：

```bash
curl -i http://localhost:5000/reports
```

大约 3 秒后，`Task.Delay` 收到取消信号并抛出取消异常。异常在响应开始前回到中间件时，默认结果是空响应体的 `504 Gateway Timeout`。

官方文档明确说明，调试器附加时该中间件不会触发。因此，在 IDE 中按 F5 运行后看到 10 秒等待或 `200 OK`，先用无调试方式重测。

## 504 不等于后台工作已经停止

把示例中的 `cancellationToken` 从 `Task.Delay` 删除：

```csharp
await Task.Delay(TimeSpan.FromSeconds(10));
```

期限仍会到达，业务代码却没有观察取消信号。中间件不会强制终止线程，也不会自动调用 `HttpContext.Abort()`；处理程序可能继续执行，最后仍返回 `200 OK`。

这解释了一个常见误会：请求超时中间件提供协作式取消。它能发出停止信号，无法保证每个依赖都执行了停止动作。即使客户端收到了 `504`，仍要借助日志或链路追踪确认数据库查询、HTTP 请求和其他耗时任务是否结束。

## 把令牌传到 EF Core 和 HttpClient

端点接到令牌后，应继续传给应用服务和所有支持取消的异步 API。EF Core 示例可以这样写：

```csharp
public Task<Order?> GetByIdAsync(
    Guid id,
    CancellationToken cancellationToken)
{
    return dbContext.Orders
        .AsNoTracking()
        .SingleOrDefaultAsync(
            order => order.Id == id,
            cancellationToken);
}
```

EF Core 会把令牌交给底层数据库提供程序。最终能否中止查询，取决于具体提供程序是否支持和响应取消。应用层传递令牌仍然是必要条件；令牌在中途丢失，数据库驱动就收不到它。

调用外部服务时也要传入令牌：

```csharp
public async Task<WeatherDto?> GetWeatherAsync(
    HttpClient httpClient,
    CancellationToken cancellationToken)
{
    using var request = new HttpRequestMessage(
        HttpMethod.Get,
        "/weather/today");

    using var response = await httpClient.SendAsync(
        request,
        cancellationToken);

    response.EnsureSuccessStatusCode();

    return await response.Content.ReadFromJsonAsync<WeatherDto>(
        cancellationToken);
}
```

`HttpClient.Timeout` 仍然有效，单次请求传入的取消令牌也会参与控制；两者中更短的期限会先产生效果。实践中要明确每层负责什么：端点期限表示这次入站请求还值得继续处理多久，依赖自身的超时则保护连接与资源。它们需要相互协调，避免下游超时长于上游太多，导致无效工作继续占用资源。

同一个 `RequestAborted` 还会在客户端断开连接时被取消。即使暂时没有配置请求期限，把令牌贯穿调用链也能减少客户端离开后的无效计算。

## 用命名策略区分端点

小型查询、报表导出和流式连接的时间预算差异很大。可以在注册阶段定义命名策略：

```csharp
builder.Services.AddRequestTimeouts(options =>
{
    options.AddPolicy(
        "api-read",
        TimeSpan.FromSeconds(3));

    options.AddPolicy(
        "report-export",
        TimeSpan.FromSeconds(30));
});
```

映射端点时选择对应策略：

```csharp
app.MapGet("/orders/{id:guid}", GetOrder)
    .WithRequestTimeout("api-read");

app.MapGet("/reports/{id:guid}", ExportReport)
    .WithRequestTimeout("report-export");

app.MapGet("/events", StreamEvents)
    .DisableRequestTimeout();
```

Server-Sent Events、WebSocket、长轮询和大型上传通常需要更长的专用策略，或显式调用 `DisableRequestTimeout()`。流式响应开始后，中间件已经无法把响应替换成干净的 `504`。

如果一项工作确实需要几分钟，更稳妥的接口设计通常是先返回 `202 Accepted` 和任务标识，再由后台处理，客户端通过查询或通知获取结果。这样，请求连接的存活时间不会绑住整个任务生命周期。

## 自定义超时响应

默认空白 `504` 不利于客户端识别错误。可以用策略统一状态码和响应体：

```csharp
using Microsoft.AspNetCore.Http.Timeouts;

builder.Services.AddRequestTimeouts(options =>
{
    options.AddPolicy(
        "api-read",
        new RequestTimeoutPolicy
        {
            Timeout = TimeSpan.FromSeconds(3),
            TimeoutStatusCode = StatusCodes.Status504GatewayTimeout,
            WriteTimeoutResponse = async context =>
            {
                context.Response.ContentType = "application/problem+json";
                await context.Response.WriteAsync(
                    """{"title":"Request timed out","status":504}""");
            }
        });
});
```

只有在响应尚未开始、取消异常回到中间件时，这段超时响应才有机会写出。端点若吞掉取消异常并返回正常结果，或提前写入响应头与响应体，最终行为会不同。

## 排查没有生效的超时

遇到端点超过期限却迟迟不返回时，按这个顺序检查：

1. **没有设置策略**：只调用 `AddRequestTimeouts()` 和 `UseRequestTimeouts()` 不会产生默认期限；还要使用 `WithRequestTimeout`、特性、命名策略或默认策略。
2. **中间件顺序错误**：显式使用路由中间件时，把 `UseRequestTimeouts()` 放在 `UseRouting()` 后。
3. **调试器仍在附加**：退出调试模式，从命令行启动后再测。
4. **令牌没有继续传递**：检查每层方法签名和每个 I/O 调用，找到令牌中断的位置。
5. **同步阻塞忽略取消**：`Thread.Sleep`、同步数据库调用或长时间 CPU 循环不会自然响应令牌。CPU 循环需要主动检查 `ThrowIfCancellationRequested()`。
6. **取消异常被吞掉**：捕获 `OperationCanceledException` 后返回成功，会改变中间件原本的 `504` 行为。
7. **响应已经开始**：流式输出或提前写响应后，中间件无法重新写入完整超时结果。
8. **代理先超时**：网关、负载均衡器或反向代理的期限更短时，客户端会先看到代理生成的响应。此时要同时查看应用日志，确认应用内工作是否已经取消。

## 验收清单

上线前至少验证一次真实依赖：

- 给一个调用 EF Core 或 `HttpClient` 的端点设置合理期限。
- 人为让依赖响应时间超过该期限。
- 在无调试器环境请求端点，确认收到预期的 `504` 或自定义响应。
- 从日志或链路追踪确认取消信号到达依赖层，耗时工作没有继续运行。
- 检查代理超时、端点期限和下游超时的先后关系。
- 为流式连接和长任务准备专用策略。

请求超时真正解决的问题，是让已经失去价值的工作尽快释放资源。先从最慢、并发量最高的一个端点开始，把 `CancellationToken` 从入口传到最深的 I/O 调用，再用一次故障演练确认整条链路确实响应了取消。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践。如果你的 ASP.NET Core 服务偶尔出现请求堆积，可以先记录最慢端点的期限、取消日志与下游耗时，再决定每类接口的策略。

## 参考

- [Your ASP.NET Core Endpoints Don't Have a Timeout（Milan Jovanović 原文）](https://milanjovanovic.tech/blog/your-aspnetcore-endpoints-dont-have-a-timeout)
- [Request timeouts middleware in ASP.NET Core（Microsoft Learn）](https://learn.microsoft.com/en-us/aspnet/core/performance/timeouts)
- [Asynchronous Programming - EF Core（Microsoft Learn）](https://learn.microsoft.com/en-us/ef/core/miscellaneous/async)
- [HttpClient.Timeout Property（Microsoft Learn）](https://learn.microsoft.com/en-us/dotnet/api/system.net.http.httpclient.timeout)
