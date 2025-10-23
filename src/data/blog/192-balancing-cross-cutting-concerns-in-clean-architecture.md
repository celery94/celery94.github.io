---
pubDatetime: 2024-01-20
tags: ["Architecture", "DevOps"]
slug: balancing-cross-cutting-concerns-in-clean-architecture
source: https://www.milanjovanovic.tech/blog/balancing-cross-cutting-concerns-in-clean-architecture
title: 在 Clean Architecture 中平衡跨切关注点：实现高效的软件架构
description: 探讨如何在 Clean Architecture 中管理和集成跨切关注点，确保系统的可维护性和可扩展性。适合对软件架构有深入理解的开发者。
---

# 在 Clean Architecture 中平衡跨切关注点：实现高效的软件架构 🎯

在软件开发中，跨切关注点（Cross-Cutting Concerns）是影响整个应用程序的重要方面。这些功能通常贯穿于多个层级和模块，例如认证与授权、日志记录、异常处理、验证和缓存等。在这篇文章中，我们将探讨如何在 Clean Architecture 中有效地集成这些关注点，以避免代码重复和组件间的紧密耦合。

## 什么是跨切关注点？

跨切关注点指的是那些需要贯穿于应用程序多个部分的功能。常见的包括：

- 🔐 认证与授权
- 📝 日志记录与跟踪
- ⚠️ 异常处理
- ✅ 数据验证
- 📦 缓存

在 Clean Architecture 中，处理跨切关注点对于确保系统的可维护性和扩展性至关重要。理想情况下，这些关注点应该与核心业务逻辑分开处理，以保持架构的清晰和适应性。

## 实现跨切关注点的方法

我们可以在基础设施层中实现跨切关注点，使用 ASP.NET Core 中间件、装饰器模式或 MediatR 管道行为等工具来管理这些关注点。

### 日志记录 📊

日志记录是软件开发中的基本功能，帮助开发者了解应用程序的行为。在 Clean Architecture 中，日志记录应该保持关注点分离。一个优雅的方法是使用 MediatR 的 `IPipelineBehavior` 来封装日志逻辑，使其成为独立的关注点。

```csharp
using Serilog.Context;

internal sealed class RequestLoggingPipelineBehavior<TRequest, TResponse>(
    ILogger<RequestLoggingPipelineBehavior<TRequest, TResponse>> logger)
    : IPipelineBehavior<TRequest, TResponse>
{
    public async Task<TResponse> Handle(
        TRequest request,
        RequestHandlerDelegate<TResponse> next,
        CancellationToken cancellationToken)
    {
        string requestName = typeof(TRequest).Name;
        logger.LogInformation("Processing request {RequestName}", requestName);

        TResponse result = await next();

        if (result.IsSuccess)
        {
            logger.LogInformation("Completed request {RequestName}", requestName);
        }
        else
        {
            using (LogContext.PushProperty("Error", result.Error, true))
            {
                logger.LogError("Completed request {RequestName} with error", requestName);
            }
        }

        return result;
    }
}
```

### 数据验证 🛡️

验证是保护系统免受错误数据侵入的关键措施。通过创建验证管道行为，可以将验证逻辑与业务逻辑分离，确保每个请求在进入核心处理逻辑之前都得到验证。

```csharp
internal sealed class ValidationPipelineBehavior<TRequest, TResponse>(
    IEnumerable<IValidator<TRequest>> validators)
    : IPipelineBehavior<TRequest, TResponse>
{
    public async Task<TResponse> Handle(
        TRequest request,
        RequestHandlerDelegate<TResponse> next,
        CancellationToken cancellationToken)
    {
        ValidationFailure[] validationFailures = await ValidateAsync(request);

        if (validationFailures.Length != 0)
        {
            throw new ValidationException(validationFailures);
        }

        return await next();
    }

    private async Task<ValidationFailure[]> ValidateAsync(TRequest request)
    {
        if (!validators.Any())
        {
            return [];
        }

        var context = new ValidationContext<TRequest>(request);

        ValidationResult[] validationResults = await Task.WhenAll(
            validators.Select(validator => validator.ValidateAsync(context)));

        ValidationFailure[] validationFailures = validationResults
            .Where(validationResult => !validationResult.IsValid)
            .SelectMany(validationResult => validationResult.Errors)
            .ToArray();

        return validationFailures;
    }
}
```

### 缓存 🚀

缓存旨在提高性能和可扩展性，通过快速访问层暂时存储数据，以减少重复获取或计算相同信息的需求。我们可以使用 Cache Aside 模式来实现缓存。

```csharp
internal sealed class QueryCachingPipelineBehavior<TRequest, TResponse>(
    ICacheService cacheService,
    ILogger<QueryCachingPipelineBehavior<TRequest, TResponse>> logger)
    : IPipelineBehavior<TRequest, TResponse>
{
    public async Task<TResponse> Handle(
        TRequest request,
        RequestHandlerDelegate<TResponse> next,
        CancellationToken cancellationToken)
    {
        TResponse? cachedResult = await cacheService.GetAsync<TResponse>(
            request.CacheKey,
            cancellationToken);

        string requestName = typeof(TRequest).Name;
        if (cachedResult is not null)
        {
            logger.LogInformation("Cache hit for {RequestName}", requestName);
            return cachedResult;
        }

        logger.LogInformation("Cache miss for {RequestName}", requestName);

        TResponse result = await next();

        if (result.IsSuccess)
        {
            await cacheService.SetAsync(
                request.CacheKey,
                result,
                request.Expiration,
                cancellationToken);
        }

        return result;
    }
}
```

## 接下来做什么？ 🔍

管理跨切关注点如日志记录、缓存、验证和异常处理不仅仅是技术实现的问题，更是与 Clean Architecture 核心原则对齐的问题。通过采用这些解耦技术，可以确保您的 .NET 项目更加稳健和易于维护。
