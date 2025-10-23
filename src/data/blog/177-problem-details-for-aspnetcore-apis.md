---
pubDatetime: 2024-10-19
tags: [".NET", "ASP.NET Core"]
source: https://www.milanjovanovic.tech/blog/problem-details-for-aspnetcore-apis
author: Milan Jovanović
title: ASP.NET Core API 的问题详情
description: 了解如何在 ASP.NET Core 中利用问题详情创建一致且信息丰富的 API 错误响应，以提升开发者体验并符合 RFC 9457。本指南详细介绍了 .NET 8 和 9 的最新功能，演示如何实现自定义异常处理程序、利用 IProblemDetailsService，并应用最佳实践来增强 API 的错误处理能力。
---

在开发 HTTP API 时，提供一致且信息丰富的错误响应对于顺畅的开发者体验至关重要。ASP.NET Core 中的**问题详情**提供了一个标准化的解决方案，确保您的 API 能够有效且统一地传达错误信息。

在本文中，我们将探讨**问题详情**的最新发展，包括：

- 新的 [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) 改进了问题详情标准
- 使用 .NET 8 的 `IExceptionHandler` 进行全局异常处理
- 使用 `IProblemDetailsService` 自定义问题详情

让我们深入了解这些功能，看看它们如何改善您的 API 错误处理。

## [理解问题详情](https://www.milanjovanovic.tech/blog/problem-details-for-aspnetcore-apis#understanding-problem-details)

问题详情是一种机器可读的格式，用于指定 HTTP API 响应中的错误信息。HTTP 状态码并不总是包含足够的错误详细信息。问题详情规范定义了一种 JSON（和 XML）文档格式来描述问题。

问题详情包括：

- `type`：标识问题类型的 URI 引用
- `title`：问题类型的简短人类可读摘要
- `status`：HTTP 状态码
- `detail`：此问题发生的特定解释
- `instance`：标识此问题特定发生情况的 URI 引用

[RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) 取代了 [RFC 7807](https://www.rfc-editor.org/rfc/rfc7807)，引入了改进，如明确类型字段的使用以及提供扩展**问题详情**的指南。

以下是一个问题详情响应示例：

```
Content-Type: application/problem+json

{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.5",
  "title": "Not Found",
  "status": 404,
  "detail": "未找到指定标识符的习惯",
  "instance": "PUT /api/habits/aadcad3f-8dc8-443d-be44-3d99893ba18a"
}
```

## [实现问题详情](https://www.milanjovanovic.tech/blog/problem-details-for-aspnetcore-apis#implementing-problem-details)

让我们看看如何在 ASP.NET Core 中实现问题详情。我们希望为未处理的异常返回一个问题详情响应。通过调用 `AddProblemDetails`，我们正在配置应用程序以使用问题详情格式处理失败的请求。使用 `UseExceptionHandler`，我们在请求管道中引入了一个异常处理中间件。通过添加 `UseStatusCodePages`，我们引入了一个中间件，它将把具有空主体的错误响应转换为问题详情响应。

```
var builder = WebApplication.CreateBuilder(args);

// 添加使用问题详情格式的服务
builder.Services.AddProblemDetails();

var app = builder.Build();

// 将未处理的异常转换为问题详情响应
app.UseExceptionHandler();

// 为（空的）非成功响应返回问题详情响应
app.UseStatusCodePages();

app.Run();
```

当我们遇到未处理的异常时，它将被转换为问题详情响应：

```
Content-Type: application/problem+json

{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.6.1",
  "title": "处理请求时发生错误。",
  "status": 500
}
```

现在，让我们探索如何自定义此响应。

## [全局错误处理](https://www.milanjovanovic.tech/blog/problem-details-for-aspnetcore-apis#global-error-handling)

我们有几种选择来[实现全局错误处理](https://www.milanjovanovic.tech/blog/global-error-handling-in-aspnetcore-8)。最流行的方法是创建自定义异常处理中间件。您可以将 API 请求包裹在 `try-catch` 语句中，并根据捕获的异常返回响应。

在 .NET 8 中，我们可以使用内置异常处理中间件中运行的 `IExceptionHandler`。此处理程序允许您为特定异常定制问题详情响应。从 `TryHandleAsync` 方法返回 `true` 会短路管道并返回 API 响应。如果返回 `false`，则链中的下一个处理程序尝试处理异常。

我们可以将不同的异常类型映射到适当的 HTTP 状态码，为 API 消费者提供更精确的错误信息。

以下是 `CustomExceptionHandler` 实现的示例：

```
internal sealed class CustomExceptionHandler : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        int status = exception switch
        {
            ArgumentException => StatusCodes.Status400BadRequest,
            _ => StatusCodes.Status500InternalServerError
        };
        httpContext.Response.StatusCode = status;

        var problemDetails = new ProblemDetails
        {
            Status = status,
            Title = "发生错误",
            Type = exception.GetType().Name,
            Detail = exception.Message
        };

        await httpContext.Response.WriteAsJsonAsync(problemDetails, cancellationToken);

        return true;
    }
}

// 在 Program.cs 中
builder.Services.AddExceptionHandler<CustomExceptionHandler>();
```

## [使用 ProblemDetailsService](https://www.milanjovanovic.tech/blog/problem-details-for-aspnetcore-apis#using-the-problemdetailsservice)

调用 `AddProblemDetails` 注册了 `IProblemDetailsService` 的默认实现。`IProblemDetailsService` 将根据 `ProblemDetails.Status` 设置响应状态码。

以下是如何在 `CustomExceptionHandler` 中使用它：

```
public class CustomExceptionHandler(IProblemDetailsService problemDetailsService) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        var problemDetails = new ProblemDetails
        {
            Status = exception switch
            {
                ArgumentException => StatusCodes.Status400BadRequest,
                _ => StatusCodes.Status500InternalServerError
            },
            Title = "发生错误",
            Type = exception.GetType().Name,
            Detail = exception.Message
        };

        return await problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            Exception = exception,
            HttpContext = httpContext,
            ProblemDetails = problemDetails
        });
    }
}
```

这种方法看起来与我们向响应体写入的方式非常相似。然而，使用 `IProblemDetailsService` 提供了一种简单的方法来定制所有问题详情响应。

我们可以在控制器中使用 `Problem` 方法，或在最小 API 中使用 `Results.Problem` 返回问题详情。这些方法遵循配置的定制问题详情（更多信息将在下一节中介绍）。

```
IdentityUser identityUser = new() { UserName = registerUserDto.UserName, Email = registerUserDto.Email };
IdentityResult result = await userManager.CreateAsync(identityUser, registerUserDto.Password);

if (!result.Succeeded)
{
    // 返回 Results.Problem - 最小 API
    return Problem(
        type: "Bad Request",
        title: "身份验证失败",
        detail: result.Errors.First().Description,
        statusCode: StatusCodes.Status400BadRequest);
}
```

## [定制问题详情](https://www.milanjovanovic.tech/blog/problem-details-for-aspnetcore-apis#customizing-problem-details)

我们可以将委托传递给 `AddProblemDetails` 方法，以设置 `CustomizeProblemDetails`。您可以使用它为所有问题详情响应添加额外信息。

这是解决跨领域问题的绝佳场所，比如设置 `instance` 值和添加诊断信息。

```
builder.Services.AddProblemDetails(options =>
{
    options.CustomizeProblemDetails = context =>
    {
        context.ProblemDetails.Instance =
            $"{context.HttpContext.Request.Method} {context.HttpContext.Request.Path}";

        context.ProblemDetails.Extensions.TryAdd("requestId", context.HttpContext.TraceIdentifier);

        Activity? activity = context.HttpContext.Features.Get<IHttpActivityFeature>()?.Activity;
        context.ProblemDetails.Extensions.TryAdd("traceId", activity?.Id);
    };
});
```

这种定制为每个问题详情响应添加了请求路径、请求 ID 和跟踪 ID，从而增强了错误的可调试性和可追溯性。

```
Content-Type: application/problem+json

{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.5",
  "title": "Not Found",
  "status": 404,
  "instance": "PUT /api/habits/aadcad3f-8dc8-443d-be44-3d99893ba18a",
  "traceId": "00-63d4af1807586b0d98901ae47944192d-9a8635facb90bf76-01",
  "requestId": "0HN7C8PRNMGIA:00000001"
}
```

您可以使用 `traceId` 在像 Seq 这样的监控系统中找到分布式跟踪和日志。

![Seq 用户界面显示具有与问题详情响应相同的跟踪标识符的分布式跟踪。](https://www.milanjovanovic.tech/blogs/mnw_112/seq_tracing.png?imwidth=3840)

## [处理特定异常（状态码）](https://www.milanjovanovic.tech/blog/problem-details-for-aspnetcore-apis#handling-specific-exceptions-status-codes)

.NET 9 引入了一种更简单的方法来将异常映射到状态码。对于喜欢抛出异常的人来说，这是个好消息。您可以使用 `状态码选择器` 定义映射。这使得在整个 API 中保持一致的错误响应更容易。

```
app.UseExceptionHandler(new ExceptionHandlerOptions
{
    StatusCodeSelector = ex => ex switch
    {
        ArgumentException => StatusCodes.Status400BadRequest,
        NotFoundException => StatusCodes.Status404NotFound,
        _ => StatusCodes.Status500InternalServerError
    }
});
```

如果您将此与设置 `StatusCode` 的 `IExceptionHandler` 一起使用，则会忽略 `状态码选择器`。

## [总结](https://www.milanjovanovic.tech/blog/problem-details-for-aspnetcore-apis#takeaway)

在您的 ASP.NET Core API 中实现问题详情不仅仅是一种最佳实践，它还是一种改善 API 消费者开发者体验的标准。通过提供一致、详细且结构良好的错误响应，您可以让客户端更容易理解和优雅地处理错误场景。

当您在自己的项目中实施这些实践时，您会发现更多的方法来根据您的特定需求定制问题详情。我分享了在我的用例中效果良好的方法。

问题详情只是我即将推出的 [**REST API 课程**](https://www.milanjovanovic.tech/rest-apis-in-aspnetcore) 中涵盖的最佳实践之一。如果您正在寻找一份全面的指南，请查看。
