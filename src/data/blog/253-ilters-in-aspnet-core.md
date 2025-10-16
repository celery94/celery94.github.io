---
pubDatetime: 2025-04-07 06:49:17
tags: [".NET", "ASP.NET Core"]
slug: filters-in-aspnet-core
source: Code with Mukesh
title: 玩转 ASP.NET Core 中的过滤器（Filters）：从入门到实战！
description: 探索 ASP.NET Core 中的过滤器，了解其概念、类型、执行顺序，以及实际应用场景。还将对比过滤器与中间件的适用情况，帮助开发者构建高效、安全的 Web API！
---

# 玩转 ASP.NET Core 中的过滤器（Filters）：从入门到实战！ 🚀

作为一名后端开发工程师，你是否常常为代码中重复的验证、日志记录或错误处理逻辑感到头疼？如果是的话，那么 ASP.NET Core 的过滤器（Filters）将成为你的救星！在这篇文章中，我们将深入探讨过滤器的概念、类型、执行顺序，以及实际应用场景，并对比过滤器与中间件的适用情况，帮助你构建高效、安全的 Web API。

## 什么是过滤器（Filters）？🤔

过滤器是 ASP.NET Core 中的一种组件，允许你在 HTTP 请求处理的特定阶段执行自定义逻辑。这些逻辑通常包括日志记录、授权验证、异常处理和请求/响应数据修改等操作。

ASP.NET Core 提供了以下几种内置过滤器类型：

- **授权过滤器（Authorization Filters）**：用于控制用户是否有权限访问资源。
- **资源过滤器（Resource Filters）**：在模型绑定之前或请求处理之后运行，用于缓存或性能优化。
- **动作过滤器（Action Filters）**：围绕控制器动作方法执行逻辑，可用于日志记录或结果修改。
- **异常过滤器（Exception Filters）**：捕获未处理异常并返回标准化响应。
- **结果过滤器（Result Filters）**：在动作结果生成后执行，用于格式化响应或添加头部信息。

此外，从 .NET 7 开始，针对 Minimal APIs 引入了 **端点过滤器（Endpoint Filters）**，它们更轻量级且专注于特定路由的逻辑处理。

## 为什么以及何时使用过滤器？🎯

### 为什么使用过滤器：

1. **关注点分离**：将通用逻辑与控制器代码分离，使代码更清晰易维护。
2. **代码复用**：避免在多个动作方法中重复相同逻辑。
3. **统一策略**：集中管理授权、日志记录或错误处理规则。
4. **增强可维护性**：模块化设计使代码更易扩展。

### 何时使用过滤器：

- 需要在动作方法前后执行逻辑，如参数验证、日志记录等。
- 希望全局应用某些规则，如统一格式化响应或捕获所有异常。
- 构建 Minimal API 时，想为特定端点添加轻量级逻辑。

如果你的需求涉及整个 HTTP 请求生命周期或跨所有端点，则应该考虑使用中间件，而非过滤器。

## ASP.NET Core 中的五大过滤器类型 🌟

### 1. 授权过滤器（Authorization Filters）

授权过滤器是请求管道的第一道关卡，它决定用户是否有权访问某个资源。通过内置的 `[Authorize]` 或自定义实现，你可以轻松管理权限。

#### 示例：自定义授权过滤器

```csharp
public class CustomAuthFilter : IAuthorizationFilter
{
    public void OnAuthorization(AuthorizationFilterContext context)
    {
        var isAuthorized = context.HttpContext.User.Identity?.IsAuthenticated ?? false;
        if (!isAuthorized)
        {
            context.Result = new UnauthorizedResult();
        }
    }
}
```

注册方式：

```csharp
services.AddControllers(options =>
{
    options.Filters.Add<CustomAuthFilter>();
});
```

### 2. 资源过滤器（Resource Filters）

资源过滤器运行于模型绑定之前，用于优化性能或提前短路请求。它们非常适合实现缓存或验证请求头等操作。

#### 示例：检查请求头

```csharp
public class CustomResourceFilter : IResourceFilter
{
    public void OnResourceExecuting(ResourceExecutingContext context)
    {
        if (!context.HttpContext.Request.Headers.ContainsKey("X-Custom-Header"))
        {
            context.Result = new BadRequestObjectResult("缺少必要的请求头");
        }
    }

    public void OnResourceExecuted(ResourceExecutedContext context) {}
}
```

### 3. 动作过滤器（Action Filters）

动作过滤器围绕控制器动作运行，可以记录日志、修改输入或包装响应。

#### 示例：封装返回结果

```csharp
public class CustomActionFilter : IActionFilter
{
    public void OnActionExecuting(ActionExecutingContext context)
    {
        Console.WriteLine("Before action execution");
    }

    public void OnActionExecuted(ActionExecutedContext context)
    {
        if (context.Result is ObjectResult result)
        {
            result.Value = new { data = result.Value, wrapped = true };
        }
    }
}
```

### 4. 异常过滤器（Exception Filters）

当控制器或动作方法抛出未处理异常时，异常过滤器将介入处理，使你能够统一格式化错误响应。

#### 示例：自定义异常处理

```csharp
public class CustomExceptionFilter : IExceptionFilter
{
    public void OnException(ExceptionContext context)
    {
        context.Result = new ObjectResult(new
        {
            error = "服务器内部错误",
            details = context.Exception.Message
        })
        {
            StatusCode = 500
        };
        context.ExceptionHandled = true;
    }
}
```

### 5. 结果过滤器（Result Filters）

结果过滤器在动作结果生成后执行，可以修改返回值或添加额外信息。

#### 示例：标准化响应格式

```csharp
public class CustomResultFilter : IResultFilter
{
    public void OnResultExecuting(ResultExecutingContext context)
    {
        if (context.Result is ObjectResult objectResult)
        {
            objectResult.Value = new { success = true, data = objectResult.Value };
        }
    }

    public void OnResultExecuted(ResultExecutedContext context) {}
}
```

### 端点过滤器（Endpoint Filters）

端点过滤器专为 Minimal APIs 设计，允许你在特定路由上轻松添加逻辑。

#### 示例：简单日志记录

```csharp
public class LoggingEndpointFilter : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        Console.WriteLine("[Before] Executing endpoint");
        var result = await next(context);
        Console.WriteLine("[After] Executed endpoint");
        return result;
    }
}
```

应用到 Minimal API:

```csharp
app.MapGet("/hello", () => "Hello, World!")
   .AddEndpointFilter<LoggingEndpointFilter>();
```

## 过滤器与中间件的对比 🔍

| 特性         | 中间件                       | 过滤器                               |
| ------------ | ---------------------------- | ------------------------------------ |
| 应用范围     | 整个 HTTP 请求生命周期       | MVC 或 Minimal API 内部逻辑          |
| 知晓路由信息 | 否                           | 是                                   |
| 使用场景     | 通用操作（如身份认证、CORS） | 动作级别操作（如参数验证、响应包装） |

### 如何选择？

- **中间件**适用于所有请求，例如身份认证、日志记录等全局性操作。
- **过滤器**适用于具体控制器或动作，比如验证模型状态或格式化响应。

## 实战场景 🌈

1. **日志记录**：使用动作过滤器记录每个请求的开始时间和结束时间。
2. **验证模型**：通过动作过滤器检查 `ModelState` 并返回统一错误格式。
3. **结果包装**：使用结果过滤器封装返回数据，使 API 响应更一致。
4. **审计功能**：通过动作过滤器记录用户行为到数据库。

## 总结 🎉

ASP.NET Core 的过滤器是构建模块化、高效 Web API 的强大工具。它们帮助开发者解决跨领域问题，同时保持代码的简洁和易维护性。在不同场景中选择正确的过滤器类型，可以显著提升你的开发效率。

如果你觉得本文对你有帮助，不妨点赞分享给你的开发伙伴吧！💻
