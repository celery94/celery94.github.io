---
pubDatetime: 2025-06-26
tags: [".NET", "ASP.NET Core", "Performance"]
slug: caching-in-aspnetcore-improving-application-performance
source: https://www.milanjovanovic.tech/blog/caching-in-aspnetcore-improving-application-performance
title: ASP.NET Core 中的缓存：提升应用性能的关键技术
description: 了解如何在 ASP.NET Core 应用程序中实现缓存，提升性能和可伸缩性。本文涵盖了缓存的类型、策略以及解决缓存相关问题的方法。
---

# ASP.NET Core 中的缓存：提升应用性能的关键技术

缓存是显著提升应用程序性能的最简单技术之一。它通过将数据临时存储在访问速度更快的位置，从而减少对原始数据源（如数据库或外部API）的访问频率，进而降低延迟、减少服务器负载、增强可伸缩性并改善用户体验。

在本文中，我们将深入探讨如何在 ASP.NET Core 应用程序中实现缓存，包括不同类型的缓存、常见的缓存策略以及如何解决缓存相关的问题。

## 缓存如何提升应用程序性能

缓存通过以下方式显著提高应用程序性能：

- **更快的N数据检索**：缓存的数据通常存储在内存（RAM）中，比从数据库或API等原始数据源检索快得多。
- **减少数据库查询**：频繁访问的数据被缓存后，可以显著减少数据库查询次数，从而减轻数据库服务器的负载。
- **降低CPU使用率**：渲染网页或处理API响应可能消耗大量CPU资源。缓存结果减少了重复性CPU密集型任务的需要。
- **应对高并发流量**：通过减少后端系统的负载，缓存使应用程序能够处理更多的并发用户和请求。
- **分布式缓存**：像 Redis 这样的分布式缓存解决方案允许跨多个服务器扩展缓存，进一步提高性能和韧性。

在一个最近的项目中，我们使用 Redis 将系统扩展到支持超过1,000,000名用户。当时我们只有一个带有读副本的SQL Server实例用于报告。可见缓存的强大之处！

## ASP.NET Core 中的缓存抽象

ASP.NET Core 提供了两种主要的缓存抽象：

- `IMemoryCache`：将数据存储在Web服务器的内存中。它使用简单，但不适用于分布式场景。
- `IDistributedCache`：为分布式应用程序提供了更健壮的解决方案。它允许您将缓存数据存储在像 Redis 这样的分布式缓存中。

要使用这些服务，我们需要将其注册到依赖注入（DI）容器中。`AddDistributedMemoryCache` 会配置 `IDistributedCache` 的内存实现，但它本身并不是分布式缓存。

```csharp
builder.Services.AddMemoryCache();

builder.Services.AddDistributedMemoryCache();
```

### 使用 IMemoryCache

以下是如何使用 `IMemoryCache` 的示例。我们首先检查缓存中是否存在该值，如果存在则直接返回。否则，我们必须从数据库中获取该值并将其缓存起来以供后续请求使用。

```csharp
app.MapGet(
    "products/{id}",
    (int id, IMemoryCache cache, AppDbContext context) =>
    {
        if (!cache.TryGetValue(id, out Product product))
        {
            product = context.Products.Find(id);

            var cacheEntryOptions = new MemoryCacheEntryOptions()
                .SetAbsoluteExpiration(TimeSpan.FromMinutes(10))
                .SetSlidingExpiration(TimeSpan.FromMinutes(2));

            cache.Set(id, product, cacheEntryOptions);
        }

        return Results.Ok(product);
    });
```

缓存过期是另一个重要的议题。我们希望移除未使用的或过时的缓存条目。您可以通过 `MemoryCacheEntryOptions` 来配置缓存过期策略。例如，我们可以设置 `AbsoluteExpiration`（绝对过期时间）和 `SlidingExpiration`（滑动过期时间）来控制缓存条目何时过期。

## Cache-Aside 模式

Cache-Aside 模式是最常见的缓存策略。它的工作原理如下：

1.  **检查缓存**：首先在缓存中查找所需数据。
2.  **从源获取（如果缓存未命中）**：如果数据不在缓存中，则从原始数据源获取。
3.  **更新缓存**：将获取到的数据存储到缓存中，以供后续请求使用。

以下是如何将 Cache-Aside 模式实现为 `IDistributedCache` 的扩展方法：

```csharp
public static class DistributedCacheExtensions
{
    public static DistributedCacheEntryOptions DefaultExpiration => new()
    {
        AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(2)
    };

    public static async Task<T> GetOrCreateAsync<T>(
        this IDistributedCache cache,
        string key,
        Func<Task<T>> factory,
        DistributedCacheEntryOptions? cacheOptions = null)
    {
        var cachedData = await cache.GetStringAsync(key);

        if (cachedData is not null)
        {
            return JsonSerializer.Deserialize<T>(cachedData);
        }

        var data = await factory();

        await cache.SetStringAsync(
            key,
            JsonSerializer.Serialize(data),
            cacheOptions ?? DefaultExpiration);

        return data;
    }
}
```

我们使用 `JsonSerializer` 来管理数据到 JSON 字符串的序列化和反序列化。`SetStringAsync` 方法也接受一个 `DistributedCacheEntryOptions` 参数来控制缓存过期。

以下是如何使用这个扩展方法的示例：

```csharp
app.MapGet(
    "products/{id}",
    (int id, IDistributedCache cache, AppDbContext context) =>
    {
        var product = cache.GetOrCreateAsync($"products-{id}", async () =>
        {
            var productFromDb = await context.Products.FindAsync(id);

            return productFromDb;
        });

        return Results.Ok(product);
    });
```

## 内存缓存的优缺点

### 优点：

- 极快的访问速度。
- 实现简单。
- 没有外部依赖。

### 缺点：

- 服务器重启后缓存数据会丢失。
- 受限于单个服务器的内存（RAM）。
- 缓存数据不能在应用程序的多个实例之间共享。

## 使用 Redis 实现分布式缓存

[Redis](https://redis.io/) 是一种流行的内存数据存储，常被用作高性能的分布式缓存。要在 ASP.NET Core 应用程序中使用 Redis，您可以使用 `StackExchange.Redis` 库。

此外，还有一个 `Microsoft.Extensions.Caching.StackExchangeRedis` 库，它允许您将 Redis 与 `IDistributedCache` 集成。

首先，您需要安装 NuGet 包：

```bash
Install-Package Microsoft.Extensions.Caching.StackExchangeRedis
```

以下是如何在 DI 中配置它，通过提供 Redis 的连接字符串：

```csharp
string connectionString = builder.Configuration.GetConnectionString("Redis");

builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = connectionString;
});
```

另一种方法是注册一个 `IConnectionMultiplexer` 作为服务。然后，我们将使用它为 `ConnectionMultiplexerFactory` 提供一个函数。

```csharp
string connectionString = builder.Configuration.GetConnectionString("Redis");

IConnectionMultiplexer connectionMultiplexer =
    ConnectionMultiplexer.Connect(connectionString);

builder.Services.AddSingleton(connectionMultiplexer);

builder.Services.AddStackExchangeRedisCache(options =>
{
    options.ConnectionMultiplexerFactory =
        () => Task.FromResult(connectionMultiplexer);
});
```

现在，当您注入 `IDistributedCache` 时，它将在底层使用 Redis。

## 缓存雪崩与 HybridCache

ASP.NET Core 中的内存缓存实现容易受到竞态条件的影响，这可能导致缓存雪崩。当并发请求遇到缓存未命中并尝试从数据源获取数据时，就会发生 [缓存雪崩](https://en.wikipedia.org/wiki/Cache_stampede)。这可能使您的应用程序过载，从而抵消缓存的好处。

加锁是解决缓存雪崩问题的一种方案。.NET 提供了许多 [加锁和并发控制](https://www.milanjovanovic.tech/blog/introduction-to-locking-and-concurrency-control-in-dotnet-6) 的选项。最常用的加锁原语是 `lock` 语句和 `Semaphore`（或 `SemaphoreSlim`）类。

以下是如何使用 `SemaphoreSlim` 在获取数据前引入加锁：

```csharp
public static class DistributedCacheExtensions
{
    private static readonly SemaphoreSlim Semaphore = new SemaphoreSlim(1, 1);

    // 参数为简洁起见省略
    public static async Task<T> GetOrCreateAsync<T>(...)
    {
        // 从缓存中获取数据，如果存在则返回

        // 缓存未命中
        try
        {
            await Semaphore.WaitAsync();

            // 检查数据是否已被其他请求添加到缓存中

            // 如果没有，继续获取数据并缓存
            var data = await factory();

            await cache.SetStringAsync(
                key,
                JsonSerializer.Serialize(data),
                cacheOptions ?? DefaultExpiration);
        }
        finally
        {
            Semaphore.Release();
        }

        return data;
    }
}
```

上述实现存在锁争用问题，因为所有请求都必须等待信号量。一个更好的解决方案是基于 `key` 值进行加锁。

.NET 9 引入了一种新的缓存抽象，称为 [`HybridCache`](https://www.milanjovanovic.tech/blog/hybrid-cache-in-aspnetcore-new-caching-library)，旨在解决 `IDistributedCache` 的缺点。您可以在 [Hybrid cache documentation](https://learn.microsoft.com/en-us/aspnet/core/performance/caching/hybrid) 中了解更多信息。

## 总结

缓存是提升Web应用程序性能的强大技术。ASP.NET Core 的缓存抽象使得实现各种缓存策略变得非常简单。

我们可以选择 `IMemoryCache` 用于内存缓存，选择 `IDistributedCache` 用于分布式缓存。

以下是一些总结性指导原则：

- 对于简单的内存缓存，使用 `IMemoryCache`。
- 实现 Cache-Aside 模式以最大程度地减少数据库访问。
- 考虑使用 Redis 作为高性能的分布式缓存实现。
- 使用 `IDistributedCache` 在多个应用程序实例之间共享缓存数据。
