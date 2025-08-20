---
pubDatetime: 2025-08-20
tags:
  ["aspnetcore", "dotnet", "api", "problemdetails", "error-handling", "web-api"]
slug: aspnet-core-problem-details-comprehensive-guide
source: https://www.milanjovanovic.tech/blog/problem-details-for-aspnetcore-apis
title: ASP.NET Core Problem Details 完整指南：构建标准化 API 错误响应的最佳实践
description: 深入探索 ASP.NET Core 中的 Problem Details 标准，从基础概念到高级实现，包含全局错误处理、IExceptionHandler、IProblemDetailsService 等核心特性的完整实战指南。
---

# ASP.NET Core Problem Details 完整指南：构建标准化 API 错误响应的最佳实践

## Problem Details：API 错误处理的标准化革命

在构建 HTTP API 时，提供一致且信息丰富的错误响应对于良好的开发者体验至关重要。传统的 HTTP 状态码虽然能够表明请求的结果，但往往无法提供足够的错误详情来帮助客户端理解和处理问题。这正是 Problem Details 标准存在的意义。

Problem Details 是一种机器可读的格式，专门用于在 HTTP API 响应中指定错误信息。它基于 RFC 9457（替代了之前的 RFC 7807）标准，定义了一种 JSON（和 XML）文档格式来描述问题的详细信息。

这种标准化的错误响应格式不仅提高了 API 的专业性，更重要的是它为客户端应用程序提供了统一的错误处理机制。无论是移动应用、Web 前端还是其他微服务，都可以依赖相同的错误响应结构来实现健壮的错误处理逻辑。

## Problem Details 核心结构解析

### 标准字段定义

Problem Details 响应包含五个核心字段，每个字段都有其特定的用途和语义：

**type** - 问题类型的标识符，通常是一个 URI，指向问题类型的文档。它为客户端提供了关于错误类别的机器可读信息。

**title** - 问题的简短、人类可读的摘要。这个字段应该保持不变，即使对于相同类型的不同实例也是如此。

**status** - HTTP 状态码的副本，为了方便客户端处理而包含在响应体中。

**detail** - 针对这个特定问题实例的人类可读解释。与 title 不同，detail 可以针对具体情况提供更详细的描述。

**instance** - 标识问题特定出现的 URI 引用。它通常包含请求的方法和路径，有助于调试和日志关联。

### 标准响应示例

以下是一个典型的 Problem Details 响应示例：

```json
{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.5",
  "title": "Not Found",
  "status": 404,
  "detail": "The habit with the specified identifier was not found",
  "instance": "PUT /api/habits/aadcad3f-8dc8-443d-be44-3d99893ba18a"
}
```

这个响应清晰地传达了错误的性质、HTTP 状态、具体描述以及发生错误的请求上下文。客户端可以解析这些信息来提供有意义的用户反馈或实现自动化的错误处理逻辑。

## ASP.NET Core 中的 Problem Details 实现

### 基础配置与中间件设置

在 ASP.NET Core 中实现 Problem Details 非常直观。框架提供了内置的支持，只需要几行配置代码：

```csharp
var builder = WebApplication.CreateBuilder(args);

// 添加 Problem Details 服务
builder.Services.AddProblemDetails();

var app = builder.Build();

// 配置异常处理中间件，将未处理的异常转换为 Problem Details 响应
app.UseExceptionHandler();

// 为空的非成功响应返回 Problem Details 响应
app.UseStatusCodePages();

app.Run();
```

这个基础配置实现了以下功能：

- `AddProblemDetails()` 注册了 Problem Details 格式所需的服务
- `UseExceptionHandler()` 添加了异常处理中间件，自动捕获未处理的异常
- `UseStatusCodePages()` 确保即使是没有响应体的错误状态码也会被转换为 Problem Details 格式

当应用程序遇到未处理的异常时，会自动生成如下格式的响应：

```json
{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.6.1",
  "title": "An error occurred while processing your request.",
  "status": 500
}
```

### 高级异常处理器实现

对于更复杂的应用场景，可以创建自定义的异常处理器来精确控制不同类型异常的处理方式：

```csharp
public class CustomExceptionHandler : IExceptionHandler
{
    private readonly ILogger<CustomExceptionHandler> _logger;

    public CustomExceptionHandler(ILogger<CustomExceptionHandler> logger)
    {
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        _logger.LogError(exception, "Exception occurred: {Message}", exception.Message);

        var problemDetails = CreateProblemDetails(exception, httpContext);

        httpContext.Response.StatusCode = problemDetails.Status ?? 500;

        await httpContext.Response.WriteAsJsonAsync(problemDetails, cancellationToken);

        return true; // 表示异常已被处理
    }

    private static ProblemDetails CreateProblemDetails(Exception exception, HttpContext context)
    {
        return exception switch
        {
            ArgumentException argEx => new ProblemDetails
            {
                Status = StatusCodes.Status400BadRequest,
                Title = "Bad Request",
                Detail = argEx.Message,
                Type = "https://httpstatuses.com/400",
                Instance = $"{context.Request.Method} {context.Request.Path}"
            },
            UnauthorizedAccessException => new ProblemDetails
            {
                Status = StatusCodes.Status401Unauthorized,
                Title = "Unauthorized",
                Detail = "You are not authorized to access this resource",
                Type = "https://httpstatuses.com/401",
                Instance = $"{context.Request.Method} {context.Request.Path}"
            },
            KeyNotFoundException => new ProblemDetails
            {
                Status = StatusCodes.Status404NotFound,
                Title = "Resource Not Found",
                Detail = "The requested resource could not be found",
                Type = "https://httpstatuses.com/404",
                Instance = $"{context.Request.Method} {context.Request.Path}"
            },
            InvalidOperationException invOpEx => new ProblemDetails
            {
                Status = StatusCodes.Status409Conflict,
                Title = "Operation Conflict",
                Detail = invOpEx.Message,
                Type = "https://httpstatuses.com/409",
                Instance = $"{context.Request.Method} {context.Request.Path}"
            },
            _ => new ProblemDetails
            {
                Status = StatusCodes.Status500InternalServerError,
                Title = "Internal Server Error",
                Detail = "An unexpected error occurred",
                Type = "https://httpstatuses.com/500",
                Instance = $"{context.Request.Method} {context.Request.Path}"
            }
        };
    }
}

// 在 Program.cs 中注册
builder.Services.AddExceptionHandler<CustomExceptionHandler>();
```

这个实现展示了如何根据不同的异常类型生成相应的 Problem Details 响应，同时保持一致的响应结构。

## IProblemDetailsService 深度应用

### 服务注入与使用模式

`IProblemDetailsService` 是 ASP.NET Core 提供的一个核心服务，它提供了生成和写入 Problem Details 响应的标准化方法。使用这个服务的主要优势是能够利用全局配置的自定义设置。

```csharp
public class AdvancedExceptionHandler : IExceptionHandler
{
    private readonly IProblemDetailsService _problemDetailsService;
    private readonly ILogger<AdvancedExceptionHandler> _logger;

    public AdvancedExceptionHandler(
        IProblemDetailsService problemDetailsService,
        ILogger<AdvancedExceptionHandler> logger)
    {
        _problemDetailsService = problemDetailsService;
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        _logger.LogError(exception, "Handling exception of type {ExceptionType}",
            exception.GetType().Name);

        var problemDetails = new ProblemDetails
        {
            Status = GetStatusCodeForException(exception),
            Title = GetTitleForException(exception),
            Detail = GetDetailForException(exception),
            Type = GetTypeUriForException(exception)
        };

        // 使用 IProblemDetailsService 来写入响应
        // 这样可以自动应用全局自定义设置
        return await _problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            Exception = exception,
            HttpContext = httpContext,
            ProblemDetails = problemDetails
        });
    }

    private static int GetStatusCodeForException(Exception exception)
    {
        return exception switch
        {
            ArgumentException or ArgumentNullException => StatusCodes.Status400BadRequest,
            UnauthorizedAccessException => StatusCodes.Status401Unauthorized,
            SecurityException => StatusCodes.Status403Forbidden,
            KeyNotFoundException or FileNotFoundException => StatusCodes.Status404NotFound,
            InvalidOperationException => StatusCodes.Status409Conflict,
            NotSupportedException => StatusCodes.Status422UnprocessableEntity,
            TimeoutException => StatusCodes.Status408RequestTimeout,
            _ => StatusCodes.Status500InternalServerError
        };
    }

    private static string GetTitleForException(Exception exception)
    {
        return exception switch
        {
            ArgumentException => "Invalid Argument",
            UnauthorizedAccessException => "Unauthorized Access",
            SecurityException => "Access Forbidden",
            KeyNotFoundException => "Resource Not Found",
            InvalidOperationException => "Invalid Operation",
            NotSupportedException => "Operation Not Supported",
            TimeoutException => "Request Timeout",
            _ => "Internal Server Error"
        };
    }

    private static string GetDetailForException(Exception exception)
    {
        // 在生产环境中，避免暴露敏感的错误详情
        return Environment.IsProduction()
            ? "An error occurred while processing your request."
            : exception.Message;
    }

    private static string GetTypeUriForException(Exception exception)
    {
        var statusCode = GetStatusCodeForException(exception);
        return $"https://httpstatuses.com/{statusCode}";
    }
}
```

### 控制器中的 Problem Details 使用

在控制器中，可以使用内置的 `Problem` 方法或 Minimal API 中的 `Results.Problem` 来返回 Problem Details 响应：

```csharp
[ApiController]
[Route("api/[controller]")]
public class UsersController : ControllerBase
{
    private readonly IUserService _userService;
    private readonly ILogger<UsersController> _logger;

    public UsersController(IUserService userService, ILogger<UsersController> logger)
    {
        _userService = userService;
        _logger = logger;
    }

    [HttpPost]
    public async Task<IActionResult> CreateUser(CreateUserRequest request)
    {
        try
        {
            var result = await _userService.CreateUserAsync(request);

            if (!result.IsSuccess)
            {
                return Problem(
                    title: "User Creation Failed",
                    detail: result.ErrorMessage,
                    statusCode: StatusCodes.Status400BadRequest,
                    type: "https://api.example.com/problems/user-creation-failed",
                    instance: HttpContext.Request.Path
                );
            }

            return CreatedAtAction(nameof(GetUser), new { id = result.User.Id }, result.User);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error creating user");

            return Problem(
                title: "Internal Server Error",
                detail: "An unexpected error occurred while creating the user",
                statusCode: StatusCodes.Status500InternalServerError,
                type: "https://api.example.com/problems/internal-error"
            );
        }
    }

    [HttpGet("{id}")]
    public async Task<IActionResult> GetUser(int id)
    {
        var user = await _userService.GetUserByIdAsync(id);

        if (user == null)
        {
            return Problem(
                title: "User Not Found",
                detail: $"User with ID {id} does not exist",
                statusCode: StatusCodes.Status404NotFound,
                type: "https://api.example.com/problems/user-not-found",
                instance: HttpContext.Request.Path
            );
        }

        return Ok(user);
    }
}
```

## Problem Details 全局自定义与扩展

### 配置全局自定义选项

ASP.NET Core 允许通过 `AddProblemDetails` 方法的配置委托来自定义所有 Problem Details 响应：

```csharp
builder.Services.AddProblemDetails(options =>
{
    options.CustomizeProblemDetails = context =>
    {
        var httpContext = context.HttpContext;
        var problemDetails = context.ProblemDetails;

        // 添加请求实例信息
        problemDetails.Instance = $"{httpContext.Request.Method} {httpContext.Request.Path}";

        // 添加请求 ID 用于跟踪
        problemDetails.Extensions.TryAdd("requestId", httpContext.TraceIdentifier);

        // 添加分布式跟踪 ID
        var activity = httpContext.Features.Get<IHttpActivityFeature>()?.Activity;
        if (activity != null)
        {
            problemDetails.Extensions.TryAdd("traceId", activity.Id);
            problemDetails.Extensions.TryAdd("spanId", activity.SpanId.ToString());
        }

        // 添加时间戳
        problemDetails.Extensions.TryAdd("timestamp", DateTimeOffset.UtcNow);

        // 添加 API 版本信息
        if (httpContext.Request.Headers.TryGetValue("X-API-Version", out var apiVersion))
        {
            problemDetails.Extensions.TryAdd("apiVersion", apiVersion.ToString());
        }

        // 在开发环境中添加详细的调试信息
        if (context.HttpContext.RequestServices
                .GetService<IWebHostEnvironment>()?.IsDevelopment() == true)
        {
            if (context.Exception != null)
            {
                problemDetails.Extensions.TryAdd("exceptionType", context.Exception.GetType().Name);
                problemDetails.Extensions.TryAdd("stackTrace", context.Exception.StackTrace);
            }
        }

        // 添加帮助链接
        problemDetails.Extensions.TryAdd("helpLink", "https://api.example.com/help/errors");
    };
});
```

### 创建特定领域的 Problem Details

对于复杂的业务应用，可以创建特定领域的 Problem Details 类来封装业务特定的错误信息：

```csharp
public class ValidationProblemDetails : ProblemDetails
{
    public ValidationProblemDetails(IDictionary<string, string[]> errors)
    {
        Title = "One or more validation errors occurred.";
        Status = StatusCodes.Status400BadRequest;
        Type = "https://api.example.com/problems/validation-error";

        Errors = errors ?? throw new ArgumentNullException(nameof(errors));
    }

    public IDictionary<string, string[]> Errors { get; }
}

public class BusinessRuleProblemDetails : ProblemDetails
{
    public BusinessRuleProblemDetails(string businessRule, string violation)
    {
        Title = "Business Rule Violation";
        Status = StatusCodes.Status422UnprocessableEntity;
        Type = "https://api.example.com/problems/business-rule-violation";
        Detail = violation;

        BusinessRule = businessRule;
    }

    public string BusinessRule { get; }
}

public class RateLimitProblemDetails : ProblemDetails
{
    public RateLimitProblemDetails(int retryAfterSeconds)
    {
        Title = "Rate Limit Exceeded";
        Status = StatusCodes.Status429TooManyRequests;
        Type = "https://api.example.com/problems/rate-limit-exceeded";
        Detail = "The request rate limit has been exceeded. Please retry after the specified time.";

        RetryAfterSeconds = retryAfterSeconds;
    }

    public int RetryAfterSeconds { get; }
}
```

### 中间件级别的 Problem Details 处理

创建专门的中间件来处理特定类型的错误，提供更精细的控制：

```csharp
public class ProblemDetailsMiddleware
{
    private readonly RequestDelegate _next;
    private readonly IProblemDetailsService _problemDetailsService;
    private readonly ILogger<ProblemDetailsMiddleware> _logger;

    public ProblemDetailsMiddleware(
        RequestDelegate next,
        IProblemDetailsService problemDetailsService,
        ILogger<ProblemDetailsMiddleware> logger)
    {
        _next = next;
        _problemDetailsService = problemDetailsService;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (Exception exception)
        {
            await HandleExceptionAsync(context, exception);
        }
    }

    private async Task HandleExceptionAsync(HttpContext context, Exception exception)
    {
        _logger.LogError(exception, "An unhandled exception occurred");

        var problemDetails = exception switch
        {
            ValidationException validationEx => new ValidationProblemDetails(validationEx.Errors),
            BusinessRuleException businessEx => new BusinessRuleProblemDetails(
                businessEx.RuleName, businessEx.Message),
            RateLimitException rateLimitEx => new RateLimitProblemDetails(rateLimitEx.RetryAfterSeconds),
            _ => new ProblemDetails
            {
                Status = StatusCodes.Status500InternalServerError,
                Title = "Internal Server Error",
                Type = "https://api.example.com/problems/internal-error"
            }
        };

        await _problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            Exception = exception,
            HttpContext = context,
            ProblemDetails = problemDetails
        });
    }
}

// 在 Program.cs 中注册中间件
app.UseMiddleware<ProblemDetailsMiddleware>();
```

## .NET 9 中的增强功能

### 简化的状态码映射

.NET 9 引入了一个更简洁的方式来映射异常类型到 HTTP 状态码，通过 `StatusCodeSelector` 属性：

```csharp
app.UseExceptionHandler(new ExceptionHandlerOptions
{
    StatusCodeSelector = ex => ex switch
    {
        ArgumentException => StatusCodes.Status400BadRequest,
        ArgumentNullException => StatusCodes.Status400BadRequest,
        UnauthorizedAccessException => StatusCodes.Status401Unauthorized,
        SecurityException => StatusCodes.Status403Forbidden,
        KeyNotFoundException => StatusCodes.Status404NotFound,
        FileNotFoundException => StatusCodes.Status404NotFound,
        InvalidOperationException => StatusCodes.Status409Conflict,
        NotSupportedException => StatusCodes.Status422UnprocessableEntity,
        TimeoutException => StatusCodes.Status408RequestTimeout,
        _ => StatusCodes.Status500InternalServerError
    }
});
```

这种方法特别适合于简单的状态码映射场景，但需要注意的是，如果同时使用了 `IExceptionHandler` 并且该处理器设置了 `StatusCode`，那么 `StatusCodeSelector` 会被忽略。

### 优先级处理机制

在 .NET 9 中，异常处理的优先级顺序如下：

1. 自定义 `IExceptionHandler` 实现
2. `StatusCodeSelector` 配置
3. 默认的 Problem Details 响应

```csharp
public class PriorityExceptionHandler : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        // 只处理特定类型的异常
        if (exception is not ValidationException validationException)
        {
            return false; // 让其他处理器处理
        }

        var problemDetails = new ValidationProblemDetails(validationException.Errors);

        await httpContext.Response.WriteAsJsonAsync(problemDetails, cancellationToken);

        return true; // 异常已被处理
    }
}

// 注册多个处理器，按照注册顺序执行
builder.Services.AddExceptionHandler<PriorityExceptionHandler>();
builder.Services.AddExceptionHandler<GeneralExceptionHandler>();
```

## 生产环境最佳实践

### 安全性考虑

在生产环境中，错误响应的安全性至关重要。需要避免暴露敏感信息：

```csharp
public class ProductionExceptionHandler : IExceptionHandler
{
    private readonly IProblemDetailsService _problemDetailsService;
    private readonly ILogger<ProductionExceptionHandler> _logger;
    private readonly IWebHostEnvironment _environment;

    public ProductionExceptionHandler(
        IProblemDetailsService problemDetailsService,
        ILogger<ProductionExceptionHandler> logger,
        IWebHostEnvironment environment)
    {
        _problemDetailsService = problemDetailsService;
        _logger = logger;
        _environment = environment;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        // 记录详细的错误信息到日志
        _logger.LogError(exception, "Exception occurred: {ExceptionType} - {Message}",
            exception.GetType().Name, exception.Message);

        var problemDetails = CreateSafeProblemDetails(exception, httpContext);

        return await _problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            Exception = exception,
            HttpContext = httpContext,
            ProblemDetails = problemDetails
        });
    }

    private ProblemDetails CreateSafeProblemDetails(Exception exception, HttpContext context)
    {
        var isProduction = _environment.IsProduction();

        return exception switch
        {
            ArgumentException when !isProduction => new ProblemDetails
            {
                Status = StatusCodes.Status400BadRequest,
                Title = "Bad Request",
                Detail = exception.Message, // 开发环境显示详细信息
                Type = "https://httpstatuses.com/400"
            },
            ArgumentException => new ProblemDetails
            {
                Status = StatusCodes.Status400BadRequest,
                Title = "Bad Request",
                Detail = "The request contains invalid parameters", // 生产环境使用通用信息
                Type = "https://httpstatuses.com/400"
            },
            UnauthorizedAccessException => new ProblemDetails
            {
                Status = StatusCodes.Status401Unauthorized,
                Title = "Unauthorized",
                Detail = "Authentication credentials are required",
                Type = "https://httpstatuses.com/401"
            },
            _ when !isProduction => new ProblemDetails
            {
                Status = StatusCodes.Status500InternalServerError,
                Title = "Internal Server Error",
                Detail = exception.Message, // 开发环境显示实际错误
                Type = "https://httpstatuses.com/500"
            },
            _ => new ProblemDetails
            {
                Status = StatusCodes.Status500InternalServerError,
                Title = "Internal Server Error",
                Detail = "An unexpected error occurred", // 生产环境隐藏详情
                Type = "https://httpstatuses.com/500"
            }
        };
    }
}
```

### 性能优化策略

对于高流量的 API，可以实现缓存和预构建的 Problem Details 响应：

```csharp
public class HighPerformanceExceptionHandler : IExceptionHandler
{
    private static readonly ConcurrentDictionary<Type, ProblemDetails> _problemDetailsCache = new();
    private readonly IProblemDetailsService _problemDetailsService;
    private readonly ILogger<HighPerformanceExceptionHandler> _logger;

    public HighPerformanceExceptionHandler(
        IProblemDetailsService problemDetailsService,
        ILogger<HighPerformanceExceptionHandler> logger)
    {
        _problemDetailsService = problemDetailsService;
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        // 获取缓存的 Problem Details 模板
        var problemDetails = _problemDetailsCache.GetOrAdd(
            exception.GetType(),
            static exceptionType => CreateProblemDetailsTemplate(exceptionType)
        );

        // 创建响应的副本以避免修改缓存的实例
        var responseProblemDetails = new ProblemDetails
        {
            Status = problemDetails.Status,
            Title = problemDetails.Title,
            Type = problemDetails.Type,
            Detail = GetSafeDetail(exception),
            Instance = $"{httpContext.Request.Method} {httpContext.Request.Path}"
        };

        // 复制扩展属性
        foreach (var extension in problemDetails.Extensions)
        {
            responseProblemDetails.Extensions[extension.Key] = extension.Value;
        }

        return await _problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            Exception = exception,
            HttpContext = httpContext,
            ProblemDetails = responseProblemDetails
        });
    }

    private static ProblemDetails CreateProblemDetailsTemplate(Type exceptionType)
    {
        return exceptionType.Name switch
        {
            nameof(ArgumentException) => new ProblemDetails
            {
                Status = StatusCodes.Status400BadRequest,
                Title = "Bad Request",
                Type = "https://httpstatuses.com/400"
            },
            nameof(UnauthorizedAccessException) => new ProblemDetails
            {
                Status = StatusCodes.Status401Unauthorized,
                Title = "Unauthorized",
                Type = "https://httpstatuses.com/401"
            },
            nameof(KeyNotFoundException) => new ProblemDetails
            {
                Status = StatusCodes.Status404NotFound,
                Title = "Not Found",
                Type = "https://httpstatuses.com/404"
            },
            _ => new ProblemDetails
            {
                Status = StatusCodes.Status500InternalServerError,
                Title = "Internal Server Error",
                Type = "https://httpstatuses.com/500"
            }
        };
    }

    private static string GetSafeDetail(Exception exception)
    {
        // 在生产环境中返回通用错误信息
        return Environment.IsProduction()
            ? "An error occurred while processing your request."
            : exception.Message;
    }
}
```

## 监控与调试集成

### 与分布式跟踪的集成

Problem Details 可以与 OpenTelemetry 和分布式跟踪系统无缝集成：

```csharp
builder.Services.AddProblemDetails(options =>
{
    options.CustomizeProblemDetails = context =>
    {
        var httpContext = context.HttpContext;
        var problemDetails = context.ProblemDetails;

        // 获取当前活动的跟踪信息
        var activity = Activity.Current;
        if (activity != null)
        {
            problemDetails.Extensions.TryAdd("traceId", activity.TraceId.ToString());
            problemDetails.Extensions.TryAdd("spanId", activity.SpanId.ToString());

            // 添加跟踪链接，便于在监控系统中查找
            var traceUrl = $"https://your-tracing-system.com/trace/{activity.TraceId}";
            problemDetails.Extensions.TryAdd("traceUrl", traceUrl);
        }

        // 添加相关性 ID
        if (httpContext.Request.Headers.TryGetValue("X-Correlation-ID", out var correlationId))
        {
            problemDetails.Extensions.TryAdd("correlationId", correlationId.ToString());
        }

        // 添加请求指纹，用于去重和分析
        var requestFingerprint = GenerateRequestFingerprint(httpContext.Request);
        problemDetails.Extensions.TryAdd("requestFingerprint", requestFingerprint);
    };
});

static string GenerateRequestFingerprint(HttpRequest request)
{
    var fingerprint = $"{request.Method}:{request.Path}:{request.QueryString}";
    using var sha256 = SHA256.Create();
    var hashBytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(fingerprint));
    return Convert.ToBase64String(hashBytes)[..12]; // 取前12个字符作为指纹
}
```

### 结构化日志记录

将 Problem Details 与结构化日志记录结合，提供完整的可观测性：

```csharp
public class ObservableExceptionHandler : IExceptionHandler
{
    private readonly IProblemDetailsService _problemDetailsService;
    private readonly ILogger<ObservableExceptionHandler> _logger;

    public ObservableExceptionHandler(
        IProblemDetailsService problemDetailsService,
        ILogger<ObservableExceptionHandler> logger)
    {
        _problemDetailsService = problemDetailsService;
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        var problemDetails = CreateProblemDetails(exception, httpContext);

        // 结构化日志记录
        using var scope = _logger.BeginScope(new Dictionary<string, object>
        {
            ["TraceId"] = Activity.Current?.TraceId.ToString() ?? "unknown",
            ["SpanId"] = Activity.Current?.SpanId.ToString() ?? "unknown",
            ["RequestId"] = httpContext.TraceIdentifier,
            ["RequestPath"] = httpContext.Request.Path,
            ["RequestMethod"] = httpContext.Request.Method,
            ["StatusCode"] = problemDetails.Status,
            ["ExceptionType"] = exception.GetType().Name,
            ["ProblemType"] = problemDetails.Type
        });

        _logger.LogError(exception,
            "Request {RequestMethod} {RequestPath} failed with {ExceptionType}: {ExceptionMessage}",
            httpContext.Request.Method,
            httpContext.Request.Path,
            exception.GetType().Name,
            exception.Message);

        return await _problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            Exception = exception,
            HttpContext = httpContext,
            ProblemDetails = problemDetails
        });
    }

    private static ProblemDetails CreateProblemDetails(Exception exception, HttpContext context)
    {
        var (status, title, type) = exception switch
        {
            ArgumentException => (400, "Bad Request", "https://httpstatuses.com/400"),
            UnauthorizedAccessException => (401, "Unauthorized", "https://httpstatuses.com/401"),
            SecurityException => (403, "Forbidden", "https://httpstatuses.com/403"),
            KeyNotFoundException => (404, "Not Found", "https://httpstatuses.com/404"),
            InvalidOperationException => (409, "Conflict", "https://httpstatuses.com/409"),
            NotSupportedException => (422, "Unprocessable Entity", "https://httpstatuses.com/422"),
            TimeoutException => (408, "Request Timeout", "https://httpstatuses.com/408"),
            _ => (500, "Internal Server Error", "https://httpstatuses.com/500")
        };

        return new ProblemDetails
        {
            Status = status,
            Title = title,
            Type = type,
            Detail = Environment.IsProduction()
                ? "An error occurred while processing your request."
                : exception.Message,
            Instance = $"{context.Request.Method} {context.Request.Path}"
        };
    }
}
```

## 客户端集成最佳实践

### .NET 客户端处理

为客户端应用程序创建强类型的 Problem Details 处理：

```csharp
public class ProblemDetailsHttpClient
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<ProblemDetailsHttpClient> _logger;

    public ProblemDetailsHttpClient(HttpClient httpClient, ILogger<ProblemDetailsHttpClient> logger)
    {
        _httpClient = httpClient;
        _logger = logger;
    }

    public async Task<ApiResult<T>> GetAsync<T>(string endpoint)
    {
        try
        {
            var response = await _httpClient.GetAsync(endpoint);

            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<T>(content);
                return ApiResult<T>.Success(data);
            }

            return await HandleProblemDetailsResponse<T>(response);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error calling endpoint {Endpoint}", endpoint);
            return ApiResult<T>.Failure("Network error occurred");
        }
    }

    private async Task<ApiResult<T>> HandleProblemDetailsResponse<T>(HttpResponseMessage response)
    {
        var contentType = response.Content.Headers.ContentType?.MediaType;

        if (contentType == "application/problem+json")
        {
            var problemContent = await response.Content.ReadAsStringAsync();
            var problemDetails = JsonSerializer.Deserialize<ProblemDetails>(problemContent);

            _logger.LogWarning("API returned problem details: {Title} - {Detail}",
                problemDetails?.Title, problemDetails?.Detail);

            return ApiResult<T>.Failure(
                problemDetails?.Detail ?? "An error occurred",
                problemDetails?.Title,
                (int?)problemDetails?.Status);
        }

        return ApiResult<T>.Failure($"Request failed with status code {response.StatusCode}");
    }
}

public class ApiResult<T>
{
    public bool IsSuccess { get; private set; }
    public T? Data { get; private set; }
    public string? ErrorMessage { get; private set; }
    public string? ErrorTitle { get; private set; }
    public int? StatusCode { get; private set; }

    private ApiResult() { }

    public static ApiResult<T> Success(T? data) => new()
    {
        IsSuccess = true,
        Data = data
    };

    public static ApiResult<T> Failure(string errorMessage, string? errorTitle = null, int? statusCode = null) => new()
    {
        IsSuccess = false,
        ErrorMessage = errorMessage,
        ErrorTitle = errorTitle,
        StatusCode = statusCode
    };
}
```

### JavaScript/TypeScript 客户端处理

```typescript
interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  [key: string]: any;
}

interface ApiResponse<T> {
  success: boolean;
  data?: T;
  problem?: ProblemDetails;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`);

      if (response.ok) {
        const data = await response.json();
        return { success: true, data };
      }

      return await this.handleProblemDetailsResponse<T>(response);
    } catch (error) {
      console.error("Network error:", error);
      return {
        success: false,
        problem: {
          title: "Network Error",
          detail: "A network error occurred while making the request",
          status: 0,
        },
      };
    }
  }

  private async handleProblemDetailsResponse<T>(
    response: Response
  ): Promise<ApiResponse<T>> {
    const contentType = response.headers.get("content-type");

    if (contentType?.includes("application/problem+json")) {
      const problemDetails: ProblemDetails = await response.json();

      console.warn("API returned problem details:", problemDetails);

      return {
        success: false,
        problem: problemDetails,
      };
    }

    return {
      success: false,
      problem: {
        title: "Request Failed",
        detail: `Request failed with status code ${response.status}`,
        status: response.status,
      },
    };
  }
}

// 使用示例
const apiClient = new ApiClient("https://api.example.com");

async function fetchUserData(userId: number) {
  const result = await apiClient.get<User>(`/users/${userId}`);

  if (result.success) {
    console.log("User data:", result.data);
  } else {
    const problem = result.problem!;
    console.error(
      `Error ${problem.status}: ${problem.title} - ${problem.detail}`
    );

    // 根据错误类型显示不同的用户界面
    switch (problem.status) {
      case 404:
        showUserNotFoundMessage();
        break;
      case 401:
        redirectToLogin();
        break;
      case 500:
        showGenericErrorMessage();
        break;
      default:
        showErrorMessage(problem.detail || "An unknown error occurred");
    }
  }
}
```

## 总结与未来展望

Problem Details 标准为 ASP.NET Core API 的错误处理提供了统一、专业的解决方案。通过本文的深入探讨，我们了解了从基础实现到高级自定义的完整流程。

### 核心收益总结

**标准化错误响应** - Problem Details 提供了一致的错误响应格式，使得客户端可以依赖统一的错误处理逻辑，大大简化了错误处理的复杂性。

**改善开发者体验** - 通过结构化的错误信息，API 消费者能够更容易地理解和处理错误情况，从而提高了整体的开发效率。

**增强可观测性** - 结合分布式跟踪和结构化日志，Problem Details 为系统监控和故障排查提供了强大的支持。

**生产就绪** - 通过安全性考虑和性能优化，Problem Details 可以安全地应用于生产环境，提供可靠的错误处理机制。

### 实施建议

在项目中引入 Problem Details 时，建议采用渐进式的方法：

首先，从基础配置开始，确保所有未处理的异常都能转换为标准的 Problem Details 响应。然后，根据业务需求创建自定义的异常处理器，为不同类型的异常提供合适的状态码和错误信息。

接下来，配置全局自定义选项，添加跟踪信息、请求 ID 等调试辅助信息。对于复杂的业务场景，可以创建特定领域的 Problem Details 类来封装业务特定的错误信息。

最后，在客户端应用程序中实现相应的 Problem Details 处理逻辑，确保错误信息能够正确传达给最终用户。

Problem Details 不仅仅是一个技术标准，更是构建高质量 API 的重要基石。随着微服务架构和分布式系统的普及，统一的错误处理机制变得越来越重要。ASP.NET Core 对 Problem Details 的原生支持，为开发者提供了构建专业、可靠 API 的强大工具。
