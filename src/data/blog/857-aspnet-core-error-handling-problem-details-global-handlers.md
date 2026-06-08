---
pubDatetime: 2026-06-08T08:27:26+08:00
title: "ASP.NET Core 错误处理：Problem Details 和全局异常处理"
description: "ASP.NET Core Web API 的错误处理不该只返回空的 500。这篇按 .NET 10 语境梳理 Problem Details、UseExceptionHandler、IExceptionHandler、验证错误、日志和开发/生产差异，帮助你做出一致、可追踪、不过度暴露的错误响应。"
tags: ["ASP.NET Core", ".NET", "Web API", "Error Handling"]
slug: "aspnet-core-error-handling-problem-details-global-handlers"
ogImage: "../../assets/857/01-cover.png"
source: "https://www.devleader.ca/2026/06/05/error-handling-in-aspnet-core-web-api-problem-details-and-global-handlers"
---

ASP.NET Core Web API 的错误处理，最怕两件事：客户端只拿到一个空的 `500 Internal Server Error`，或者每个 endpoint 都返回一套不同格式的错误。前者没法排查，后者没法稳定解析。

Dev Leader 这篇文章围绕 .NET 10 讲了一套比较完整的做法：用 RFC 9457 Problem Details 统一错误格式，用 `UseExceptionHandler` 接住未处理异常，用 `IExceptionHandler` 拆分异常映射逻辑，再用 `traceId`、结构化日志和环境区分，让生产错误既可追踪，又不泄露内部细节。

## 统一格式

Problem Details 是 HTTP API 错误响应的标准格式。现在对应的是 RFC 9457，它定义了 `application/problem+json` 以及几个常见字段：

- `type`：错误类型 URI，可以指向你的错误文档，也可以是 `about:blank`。
- `title`：这一类错误的人类可读摘要。
- `status`：HTTP 状态码。
- `detail`：这一次错误的具体说明，注意不要暴露敏感内部信息。
- `instance`：这一次错误实例，常见是请求路径。

在 .NET 10 里，最小配置很简单：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddProblemDetails();

var app = builder.Build();

app.UseExceptionHandler();
app.UseStatusCodePages();

app.MapControllers();
app.Run();
```

`AddProblemDetails()` 启用标准响应支持。`UseExceptionHandler()` 接住未处理异常。`UseStatusCodePages()` 可以把 routing 产生的裸 404、405 等状态码也转成 Problem Details。

一个 500 响应大概会长这样：

```json
{
  "type": "https://tools.ietf.org/html/rfc9457",
  "title": "An error occurred while processing your request.",
  "status": 500,
  "detail": null,
  "instance": "/api/orders/42",
  "traceId": "00-a1b2c3d4e5f6-b7c8d9e0f1a2-00"
}
```

`traceId` 很关键。客户端拿着它来报错，你可以在日志和分布式追踪里反查到同一次请求。

## 全局入口

`UseExceptionHandler` 是 ASP.NET Core 错误处理的全局入口。它包住后面的 middleware pipeline，把未处理异常转成可控响应。

小应用里可以直接用 lambda：

```csharp
app.UseExceptionHandler(exceptionHandlerApp =>
{
    exceptionHandlerApp.Run(async context =>
    {
        var feature = context.Features.Get<IExceptionHandlerFeature>();
        var exception = feature?.Error;

        var status = exception switch
        {
            NotFoundException => StatusCodes.Status404NotFound,
            UnauthorizedAccessException => StatusCodes.Status403Forbidden,
            _ => StatusCodes.Status500InternalServerError
        };

        var problemDetails = new ProblemDetails
        {
            Status = status,
            Title = status == 500
                ? "An unexpected error occurred"
                : exception?.Message,
            Detail = status == 500 ? null : exception?.Message,
            Instance = context.Request.Path
        };

        problemDetails.Extensions["traceId"] =
            Activity.Current?.Id ?? context.TraceIdentifier;

        context.Response.StatusCode = status;
        context.Response.ContentType = "application/problem+json";

        await context.Response.WriteAsJsonAsync(problemDetails);
    });
});
```

这能跑，但当异常类型越来越多时，lambda 里会堆出一堵 `switch` 或 `if/else`。它不好测，也不好维护。更适合生产项目的是 `IExceptionHandler`。

## Handler 链

`IExceptionHandler` 从 .NET 8 开始提供，在 .NET 10 里已经是很顺手的做法。你把不同异常映射拆成多个类，注册到 DI，ASP.NET Core 按注册顺序依次调用。某个 handler 返回 `true`，表示已经处理，后续 handler 不再执行；返回 `false`，交给下一个 handler。

这很像 Chain of Responsibility：每个 handler 只关心自己能处理的异常。

领域异常可以映射成 422：

```csharp
public sealed class DomainExceptionHandler : IExceptionHandler
{
    private readonly ILogger<DomainExceptionHandler> _logger;

    public DomainExceptionHandler(
        ILogger<DomainExceptionHandler> logger)
    {
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        if (exception is not DomainException domainException)
        {
            return false;
        }

        _logger.LogWarning(
            domainException,
            "Domain rule violated: {ErrorCode} -- {Message}",
            domainException.ErrorCode,
            domainException.Message);

        var problemDetails = new ProblemDetails
        {
            Status = StatusCodes.Status422UnprocessableEntity,
            Title = "Business rule violation",
            Detail = domainException.Message,
            Type = "https://api.example.com/errors/domain"
        };

        problemDetails.Extensions["errorCode"] =
            domainException.ErrorCode;
        problemDetails.Extensions["traceId"] =
            Activity.Current?.Id ?? httpContext.TraceIdentifier;

        httpContext.Response.StatusCode =
            StatusCodes.Status422UnprocessableEntity;

        await httpContext.Response.WriteAsJsonAsync(
            problemDetails,
            cancellationToken);

        return true;
    }
}
```

再加一个兜底 handler 处理其他未预期异常：

```csharp
public sealed class GlobalExceptionHandler : IExceptionHandler
{
    private readonly ILogger<GlobalExceptionHandler> _logger;

    public GlobalExceptionHandler(
        ILogger<GlobalExceptionHandler> logger)
    {
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        _logger.LogError(
            exception,
            "Unhandled exception: {ExceptionType} on {Method} {Path}",
            exception.GetType().Name,
            httpContext.Request.Method,
            httpContext.Request.Path);

        var problemDetails = new ProblemDetails
        {
            Status = StatusCodes.Status500InternalServerError,
            Title = "An unexpected error occurred",
            Type = "https://tools.ietf.org/html/rfc9457"
        };

        problemDetails.Extensions["traceId"] =
            Activity.Current?.Id ?? httpContext.TraceIdentifier;

        httpContext.Response.StatusCode =
            StatusCodes.Status500InternalServerError;

        await httpContext.Response.WriteAsJsonAsync(
            problemDetails,
            cancellationToken);

        return true;
    }
}
```

注册顺序就是尝试顺序：

```csharp
builder.Services.AddExceptionHandler<DomainExceptionHandler>();
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddProblemDetails();

app.UseExceptionHandler();
```

把领域异常、NotFound、Conflict、Validation、兜底异常拆开后，每个 handler 都短小、可测试、边界清晰。

## 全局扩展字段

有些字段希望出现在所有 Problem Details 响应里，不只是异常响应，也包括 404、401、验证失败。这时用 `AddProblemDetails` 的 `CustomizeProblemDetails`。

```csharp
builder.Services.AddProblemDetails(options =>
{
    options.CustomizeProblemDetails = context =>
    {
        context.ProblemDetails.Extensions["traceId"] =
            Activity.Current?.Id
            ?? context.HttpContext.TraceIdentifier;

        context.ProblemDetails.Extensions["nodeId"] =
            Environment.MachineName;

        context.ProblemDetails.Extensions["timestamp"] =
            DateTimeOffset.UtcNow.ToString("o");
    };
});
```

这样客户端可以用统一逻辑处理错误：每个错误都有可追踪 ID、时间戳，以及你决定公开的上下文。

需要注意的是，`errorCode` 这类只对某些异常有意义的字段，最好放在对应 `IExceptionHandler` 里加，不要全局塞一个空值。

## 验证错误

带 `[ApiController]` 的 controller 在模型验证失败时，会自动短路并返回 `ValidationProblemDetails`。你不需要在每个 action 里写：

```csharp
if (!ModelState.IsValid)
{
    ...
}
```

默认验证响应通常是 400：

```json
{
  "type": "https://tools.ietf.org/html/rfc9457",
  "title": "One or more validation errors occurred.",
  "status": 400,
  "errors": {
    "Email": ["The Email field is not a valid e-mail address."],
    "Name": ["The Name field is required."]
  },
  "traceId": "00-a1b2c3..."
}
```

如果你的团队希望语义验证失败返回 422，可以替换 `InvalidModelStateResponseFactory`：

```csharp
builder.Services.Configure<ApiBehaviorOptions>(options =>
{
    options.InvalidModelStateResponseFactory = context =>
    {
        var problemDetails =
            new ValidationProblemDetails(context.ModelState)
            {
                Type = "https://api.example.com/errors/validation",
                Title = "Validation failed",
                Status = StatusCodes.Status422UnprocessableEntity
            };

        problemDetails.Extensions["traceId"] =
            context.HttpContext.TraceIdentifier;

        return new UnprocessableEntityObjectResult(problemDetails)
        {
            ContentTypes = { "application/problem+json" }
        };
    };
});
```

400 和 422 都有人用。比较稳的约定是：结构问题、类型错误、缺字段用 400；请求语法没问题但违反业务语义时用 422。真正重要的是一致，并写进 API 文档。

## Filter 还是 Handler

Exception filter 和 `IExceptionHandler` 都能处理异常，但层级不同。

`IExceptionFilter` / `IAsyncExceptionFilter` 属于 MVC 范围。它们只捕获 MVC action 内部抛出的异常，不处理 middleware、Minimal API handler、后台服务里的异常。它适合“某个 controller 或 action 要特殊处理”的场景。

`IExceptionHandler` 是 pipeline-wide。只要异常向上冒泡经过 middleware pipeline，它都能接住。对于纯 Web API，除非你确实需要 action 级差异，否则更推荐把全局错误处理放在 `IExceptionHandler` 链里。

## 日志怎么打

错误响应给客户端看，日志给自己排查。两者要配合。

记录异常时，不要只写 `exception.Message`。要把整个异常对象传给 logger，这样 stack trace、inner exception、异常类型都能保留下来：

```csharp
_logger.LogError(
    exception,
    "Order processing failed for OrderId {OrderId} -- {ExceptionType}",
    orderId,
    exception.GetType().Name);
```

也不要在每一层 catch 后都 log 再 throw。一个异常被记录三四次，只会制造噪音。通常在最外层的全局 handler 记录一次，配上结构化字段和 traceId，就够排查。

## 开发和生产

开发环境需要完整错误细节，生产环境不能暴露内部信息。

```csharp
if (app.Environment.IsDevelopment())
{
    app.UseDeveloperExceptionPage();
}
else
{
    app.UseExceptionHandler();
    app.UseHsts();
}
```

`UseDeveloperExceptionPage` 会暴露 stack trace、内部路径、query string 等信息，开发时很好用，生产环境不能开。线上应确保 `ASPNETCORE_ENVIRONMENT` 是 `Production`，并且不要用别的条件绕过 `IsDevelopment()`。

## 实践顺序

一套生产可用的 ASP.NET Core Web API 错误处理，可以按这个顺序落地：

1. 注册 `AddProblemDetails()`。
2. 在 pipeline 前面放 `UseExceptionHandler()`。
3. 用多个 `IExceptionHandler` 拆分异常映射，最后留一个兜底 handler。
4. 用 `CustomizeProblemDetails` 加 `traceId`、`timestamp` 等全局扩展。
5. 让 `[ApiController]` 自动返回验证错误，必要时统一 400/422 约定。
6. 在全局 handler 里记录完整异常对象，避免多层重复日志。
7. 开发环境用 `UseDeveloperExceptionPage`，生产环境只返回安全的 Problem Details。

这样的好处是，客户端永远拿到可解析格式，开发者永远有 traceId 可以追，生产环境不会把 stack trace 和内部路径直接送出去。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Error Handling in ASP.NET Core Web API: Problem Details and Global Handlers](https://www.devleader.ca/2026/06/05/error-handling-in-aspnet-core-web-api-problem-details-and-global-handlers)
- [Handle errors in ASP.NET Core web APIs - Microsoft Learn](https://learn.microsoft.com/en-us/aspnet/core/web-api/handle-errors)
