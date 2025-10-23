---
pubDatetime: 2025-07-12
tags: [".NET", "ASP.NET Core", "Architecture"]
slug: global-error-handling-in-aspnetcore
source: https://www.milanjovanovic.tech/blog/global-error-handling-in-aspnetcore-from-middleware-to-modern-handlers
title: ASP.NET Core 全局异常处理实践：从中间件到现代异常处理器
description: 本文详细解析了 ASP.NET Core 中的全局异常处理方式，包括经典中间件、标准化响应格式（IProblemDetailsService）、以及最新的 IExceptionHandler 的现代实践，帮助开发者打造健壮、可维护的 API 错误处理体系。
---

# ASP.NET Core 全局异常处理实践：从中间件到现代异常处理器

异常处理是任何后端应用架构中不可或缺的一环。对于 ASP.NET Core 开发者而言，如何设计一套高效、优雅、并能适应未来演进的全局异常处理机制，不仅关系到系统健壮性，也直接影响开发效率和 API 消费者体验。本文将系统梳理 ASP.NET Core 中主流的全局异常处理模式，结合最新特性与最佳实践，深入剖析中间件、标准化问题详情（ProblemDetails）、以及新引入的 IExceptionHandler 的使用场景与演化脉络。

## 从自定义中间件到标准响应格式

在 ASP.NET Core 项目中，最传统也是最常见的做法，是通过自定义中间件（Middleware）来捕获和处理未被上层捕捉的异常。这种方式结构简单，易于集成，但随着业务复杂度提升，也面临扩展性和标准化不足的问题。

**自定义异常处理中间件示例：**

```csharp
internal sealed class GlobalExceptionHandlerMiddleware(
    RequestDelegate next,
    ILogger<GlobalExceptionHandlerMiddleware> logger)
{
    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await next(context);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Unhandled exception occurred");

            // 设置状态码，并返回自定义 ProblemDetails 格式响应
            context.Response.StatusCode = ex switch
            {
                ApplicationException => StatusCodes.Status400BadRequest,
                _ => StatusCodes.Status500InternalServerError
            };

            await context.Response.WriteAsJsonAsync(
                new ProblemDetails
                {
                    Type = ex.GetType().Name,
                    Title = "An error occurred",
                    Detail = ex.Message
                });
        }
    }
}
```

要让该中间件生效，只需在请求管道中注册即可：

```csharp
app.UseMiddleware<GlobalExceptionHandlerMiddleware>();
```

这种做法适用于快速原型或简单项目，但随着异常种类增多（如验证异常、资源未找到等），代码会迅速膨胀，并且自定义序列化往往与业界标准（如 RFC 9457）存在差距。

## IProblemDetailsService：标准化你的错误响应

为了解决中间件方案的局限性，微软引入了 `IProblemDetailsService`，使开发者能够轻松生成符合标准的 ProblemDetails 响应，从而提升 API 的可用性和一致性。

**升级后的中间件示例：**

```csharp
internal sealed class GlobalExceptionHandlerMiddleware(
    RequestDelegate next,
    IProblemDetailsService problemDetailsService,
    ILogger<GlobalExceptionHandlerMiddleware> logger)
{
    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await next(context);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Unhandled exception occurred");

            context.Response.StatusCode = ex switch
            {
                ApplicationException => StatusCodes.Status400BadRequest,
                _ => StatusCodes.Status500InternalServerError
            };

            await problemDetailsService.TryWriteAsync(new ProblemDetailsContext
            {
                HttpContext = context,
                Exception = ex,
                ProblemDetails = new ProblemDetails
                {
                    Type = ex.GetType().Name,
                    Title = "An error occurred",
                    Detail = ex.Message
                }
            });
        }
    }
}
```

通过内置的 `IProblemDetailsService`，不仅减少了手动序列化的工作，还大大提升了异常响应的规范性。这一变化对于公共 API 特别重要，开发者可借助标准工具进行自动化对接和测试。

## IExceptionHandler：面向未来的异常处理体系

ASP.NET Core 8 开始，官方推荐使用更具现代化、解耦性强的 `IExceptionHandler` 接口。它允许针对不同异常类型编写专用处理器，实现关注点分离、可测试性和灵活扩展。

**自定义异常处理器的实现：**

```csharp
internal sealed class GlobalExceptionHandler(
    IProblemDetailsService problemDetailsService,
    ILogger<GlobalExceptionHandler> logger) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        logger.LogError(exception, "Unhandled exception occurred");

        httpContext.Response.StatusCode = exception switch
        {
            ApplicationException => StatusCodes.Status400BadRequest,
            _ => StatusCodes.Status500InternalServerError
        };

        return await problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = httpContext,
            Exception = exception,
            ProblemDetails = new ProblemDetails
            {
                Type = exception.GetType().Name,
                Title = "An error occurred",
                Detail = exception.Message
            }
        });
    }
}
```

在注册时：

```csharp
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddProblemDetails();
app.UseExceptionHandler();
```

该机制的核心优势在于，可按需注册多个异常处理器，并通过链式尝试处理，首个能处理的处理器返回 `true` 即终止后续处理，实现了类似责任链模式的灵活扩展。例如，可以针对 FluentValidation 验证异常实现专用处理器：

```csharp
internal sealed class ValidationExceptionHandler(
    IProblemDetailsService problemDetailsService,
    ILogger<ValidationExceptionHandler> logger) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        if (exception is not ValidationException validationException)
            return false;

        logger.LogError(exception, "Unhandled exception occurred");

        httpContext.Response.StatusCode = StatusCodes.Status400BadRequest;
        var context = new ProblemDetailsContext
        {
            HttpContext = httpContext,
            Exception = exception,
            ProblemDetails = new ProblemDetails
            {
                Detail = "One or more validation errors occurred",
                Status = StatusCodes.Status400BadRequest
            }
        };

        var errors = validationException.Errors
            .GroupBy(e => e.PropertyName)
            .ToDictionary(
                g => g.Key.ToLowerInvariant(),
                g => g.Select(e => e.ErrorMessage).ToArray()
            );
        context.ProblemDetails.Extensions.Add("errors", errors);

        return await problemDetailsService.TryWriteAsync(context);
    }
}
```

如此一来，验证失败时可自动返回字段级错误信息，极大提升前后端联调效率与用户体验。

## 实践建议与总结

回顾 ASP.NET Core 异常处理的发展历程，从最初的手写中间件，到 ProblemDetails 标准化响应，再到 IExceptionHandler 的高内聚、低耦合现代解法，每一步都在提升系统的健壮性和可维护性。建议新项目优先采用 IExceptionHandler 方案，利用其分层处理、易于测试和扩展的特点，打造一套适合自身业务的全局异常处理体系。

最重要的一点，异常处理绝不应成为事后的补丁，而应当是项目设计阶段就要关注的基础能力。早早建立统一、优雅的异常处理体系，将大幅降低生产事故带来的压力，也让系统长期演进更为顺畅。
