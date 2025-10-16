---
pubDatetime: 2025-03-28 08:14:28
tags: [".NET", "ASP.NET Core"]
slug: aspnet-core-middleware-guide
source: https://codewithmukesh.com/blog/middlewares-in-aspnet-core/
title: 掌握ASP.NET Core中间件的核心原理与最佳实践，一文全解析！
description: ASP.NET Core中的中间件是构建高效Web API的重要组件。本文详细解析中间件的定义、工作原理、执行顺序、内置功能、自定义实现及最佳实践，为技术学习者提供深度技术支持。
---

# 掌握ASP.NET Core中间件的核心原理与最佳实践，一文全解析！🚀

ASP.NET Core 是现代 Web 开发的强大框架，而其中的 **中间件（Middleware）** 是其请求处理流水线的核心组件。理解中间件的工作方式、执行顺序以及如何自定义它们，对开发高效、可维护的 Web API 至关重要。本文将带您深入了解 ASP.NET Core 中间件的方方面面，帮助您掌握这一关键技术。

---

## 什么是ASP.NET Core中的中间件？

**中间件** 是 ASP.NET Core 请求处理流水线中的基础模块，它由一系列组件组成，用于处理 HTTP 请求和响应。每个中间件组件都可以拦截、修改或终止请求，从而实现日志记录、身份验证、错误处理等功能。

当一个请求进入应用时，它会依次经过注册好的中间件，最终生成响应并返回给客户端。这个流程的灵活性使得开发者能够以结构化的方式处理复杂任务，例如：

- 用户身份验证与授权
- 错误日志记录
- 响应内容压缩
- 自定义路由规则

中间件按照注册顺序依次执行，其执行顺序对应用功能至关重要。例如，身份验证中间件必须在授权中间件之前运行，以确保先确认用户身份再检查访问权限。

---

## 中间件如何工作？🤔

每个中间件组件遵循以下模式：

1. 接收 `HttpContext` 对象（当前请求和响应的所有信息）。
2. 进行请求处理（如修改数据、检查权限）。
3. 决定是否将请求传递给下一个中间件，或者直接生成响应。

如果一个中间件通过调用 `await next()` 将请求传递下去，那么该请求会继续流经后续的中间件；否则，中间件可以直接生成响应并“短路”流水线。

### 工作示例：请求处理流程

以下是一个简单示例，展示了三个中间件的执行流程：

```csharp
app.Use(async (context, next) => {
    Console.WriteLine("Middleware 1: Incoming request");
    await next();  // 继续下一个中间件
    Console.WriteLine("Middleware 1: Outgoing response");
});

app.Use(async (context, next) => {
    Console.WriteLine("Middleware 2: Incoming request");
    await next();
    Console.WriteLine("Middleware 2: Outgoing response");
});

app.Run(async (context) => {
    Console.WriteLine("Middleware 3: Handling request and terminating pipeline");
    await context.Response.WriteAsync("Hello, world!");
});
```

### 执行流程：

```plaintext
Middleware 1: Incoming request
Middleware 2: Incoming request
Middleware 3: Handling request and terminating pipeline
Middleware 2: Outgoing response
Middleware 1: Outgoing response
```

注意：`app.Run()` 会终止流水线，后续的中间件将不再执行。

---

## ASP.NET Core内置中间件✨

ASP.NET Core 提供了一系列内置中间件，可以快速实现常见功能：

1. **异常处理中间件**：捕获未处理的异常并统一返回错误信息。

   ```csharp
   app.UseExceptionHandler("/Home/Error");
   ```

2. **路由中间件**：将请求映射到适当的控制器或端点。

   ```csharp
   app.UseRouting();
   ```

3. **身份验证和授权中间件**：确保用户身份和权限验证。

   ```csharp
   app.UseAuthentication();
   app.UseAuthorization();
   ```

4. **静态文件中间件**：直接提供 HTML、CSS 等静态资源。

   ```csharp
   app.UseStaticFiles();
   ```

5. **CORS 中间件**：允许跨域资源共享。

   ```csharp
   app.UseCors(options =>
       options.WithOrigins("https://example.com")
              .AllowAnyMethod()
              .AllowAnyHeader());
   ```

6. **HTTPS 重定向**：强制所有请求使用 HTTPS。
   ```csharp
   app.UseHttpsRedirection();
   ```

这些内置中间件大大简化了开发过程，让开发者无需重复造轮子。

---

## 如何编写自定义中间件？

当内置中间件不能完全满足需求时，可以编写自定义中间件来实现特定功能。

### 步骤一：创建中间件类

```csharp
public class CustomMiddleware {
    private readonly RequestDelegate _next;

    public CustomMiddleware(RequestDelegate next) {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context) {
        Console.WriteLine("Custom Middleware: Request Processing Started");
        await _next(context); // 调用下一个中间件
        Console.WriteLine("Custom Middleware: Response Sent");
    }
}
```

### 步骤二：注册中间件

在 `Program.cs` 文件中添加以下代码：

```csharp
app.UseMiddleware<CustomMiddleware>();
```

### 示例：日志记录中间件

以下是一个记录所有 HTTP 请求和响应状态码的自定义中间件：

```csharp
public class RequestLoggingMiddleware {
    private readonly RequestDelegate _next;
    private readonly ILogger<RequestLoggingMiddleware> _logger;

    public RequestLoggingMiddleware(RequestDelegate next, ILogger<RequestLoggingMiddleware> logger) {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context) {
        _logger.LogInformation($"Incoming Request: {context.Request.Method} {context.Request.Path}");
        await _next(context);
        _logger.LogInformation($"Response Status Code: {context.Response.StatusCode}");
    }
}
```

注册方法：

```csharp
app.UseMiddleware<RequestLoggingMiddleware>();
```

---

## 中间件最佳实践✅

为了确保您的应用性能稳定且易于维护，请遵循以下最佳实践：

### 1. 保持轻量级

中间件应专注于单一功能，避免执行复杂计算或长时间阻塞任务。

### 2. 正确排序

按逻辑顺序排列中间件，例如：

- 异常处理 > 身份验证 > 授权 > 路由 > 自定义处理

### 3. 优先使用内置中间件

充分利用内置功能，如异常处理、身份验证、静态文件服务等。

### 4. 避免阻塞调用

始终使用异步方法进行请求处理，以提高性能。

```csharp
// 好的实践
public async Task InvokeAsync(HttpContext context) {
    var result = await SomeLongRunningOperation();
    await context.Response.WriteAsync(result);
}
```

### 5. 使用扩展方法简化代码

通过扩展方法注册中间件，可使代码更简洁、模块化。

```csharp
public static class CustomMiddlewareExtensions {
    public static IApplicationBuilder UseCustomMiddleware(this IApplicationBuilder builder) {
        return builder.UseMiddleware<CustomMiddleware>();
    }
}
```

---

## 推荐的执行顺序（BONUS）🔥

以下是建议的 ASP.NET Core 中间件执行顺序：

```csharp
var app = builder.Build();

app.UseExceptionHandler("/error");      // 捕获全局异常
app.UseHttpsRedirection();              // 强制 HTTPS
app.UseRouting();                       // 路由配置
app.UseCors();                          // 跨域资源共享
app.UseAuthentication();                // 身份验证
app.UseAuthorization();                 // 授权检查
app.UseMiddleware<CustomMiddleware>();  // 自定义逻辑（如日志记录）
app.UseEndpoints(endpoints =>           // 最终路由匹配
{
    endpoints.MapControllers();
});

app.Run();
```

### 为什么这样排序？

- 异常处理优先确保任何错误都被捕获。
- HTTPS 重定向尽早保护通信安全。
- 身份验证必须在授权之前运行。
- 自定义逻辑放在控制器处理之前以优化数据流。

---

## 总结🎯

通过学习 ASP.NET Core 的 **中间件**，您可以深入理解应用如何处理 HTTP 请求并优化其性能。掌握如何正确设计、排序和使用中间件，不仅能提高开发效率，还能让您的 API 更加安全和可维护。

本文涵盖了：

- 中间件的基本概念及工作原理；
- 内置中间件与其用途；
- 自定义实现方法；
- 最佳实践和推荐执行顺序。
