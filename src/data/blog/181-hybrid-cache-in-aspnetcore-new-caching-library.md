---
pubDatetime: 2024-11-16
tags: []
source: https://www.milanjovanovic.tech/blog/hybrid-cache-in-aspnetcore-new-caching-library
author: Milan Jovanović
title: ASP.NET Core中的混合缓存 - 新的缓存库
description: HybridCache in .NET 9 combines fast in-memory caching with distributed caching, solving common problems like cache stampede while adding features like tag-based invalidation. This guide shows you how to use HybridCache in your applications, from basic setup to real-world usage patterns with Entity Framework Core and minimal APIs.
---

# ASP.NET Core中的混合缓存 - 新的缓存库

.NET 9 引入了`混合缓存`，这是一个结合了两种方法优势的新库。它可以防止常见的缓存问题，如缓存雪崩。同时，它还增加了一些有用的功能，比如基于标签的失效和更好的性能监控。

在本周的文章中，我将向您展示如何在应用程序中使用`混合缓存`。

## [什么是混合缓存？](#what-is-hybridcache)

ASP.NET 核心中的传统缓存选项有其局限性。内存缓存速度快，但局限于一个服务器。分布式缓存可以跨服务器工作，但速度较慢。

[混合缓存](https://learn.microsoft.com/en-us/aspnet/core/performance/caching/hybrid)结合了这两种方法并添加了重要功能：

- 两级缓存（L1/L2）
  - L1：快速的内存缓存
  - L2：分布式缓存（Redis、SQL 服务器等）
- 防止[缓存雪崩](https://en.wikipedia.org/wiki/Cache_stampede)（当许多请求同时命中空缓存时）
- 基于标签的缓存失效
- 可配置的序列化
- 指标和监控

L1 缓存在您的应用程序内存中运行。L2 缓存可以是 Redis、SQL 服务器或任何其他分布式缓存。如果您不需要分布式缓存，可以仅使用混合缓存的 L1 缓存。

## [安装混合缓存](#installing-hybridcache)

安装`Microsoft.Extensions.Caching.Hybrid` NuGet 包：

```
Install-Package Microsoft.Extensions.Caching.Hybrid
```

将`混合缓存`添加到您的服务中：

```
builder.Services.AddHybridCache(options =>
{
    // 缓存项的最大大小
    options.MaximumPayloadBytes = 1024 * 1024 * 10; // 10MB
    options.MaximumKeyLength = 512;

    // 默认超时时间
    options.DefaultEntryOptions = new HybridCacheEntryOptions
    {
        Expiration = TimeSpan.FromMinutes(30),
        LocalCacheExpiration = TimeSpan.FromMinutes(30)
    };
});
```

对于自定义类型，您可以添加自己的序列化器：

```
builder.Services.AddHybridCache()
    .AddSerializer<CustomType, CustomSerializer>();
```

## [使用混合缓存](#using-hybridcache)

`混合缓存`提供了几个方法来处理缓存数据。最重要的是`获取或创建异步`、`设置异步`和各种移除方法。让我们来看看如何在实际场景中使用每一个。

### [获取或创建缓存条目](#getting-or-creating-cache-entries)

`获取或创建异步`方法是您处理缓存数据的主要工具。它会自动处理缓存命中和未命中。如果数据不在缓存中，它会调用您的工厂方法来获取数据，缓存它，然后返回。

这是一个获取产品详细信息的端点：

```
app.MapGet("/products/{id}", async (
    int id,
    HybridCache cache,
    ProductDbContext db,
    CancellationToken ct) =>
{
    var product = await cache.GetOrCreateAsync(
        $"product-{id}",
        async token =>
        {
            return await db.Products
                .Include(p => p.Category)
                .FirstOrDefaultAsync(p => p.Id == id, token);
        },
        cancellationToken: ct
    );

    return product is null ? Results.NotFound() : Results.Ok(product);
});
```

在这个例子中：

- 每个产品的缓存键是唯一的
- 如果产品在缓存中，会立即返回
- 如果不在，工厂方法将运行以获取数据
- 其他对同一产品的并发请求会等待第一个请求完成

### [直接设置缓存条目](#setting-cache-entries-directly)

有时您需要直接更新缓存，比如在修改数据之后。`设置异步`方法处理这个问题：

```
app.MapPut("/products/{id}", async (int id, Product product, HybridCache cache) =>
{
    // 首先更新数据库
    await UpdateProductInDatabase(product);

    // 然后更新缓存并自定义过期时间
    var options = new HybridCacheEntryOptions
    {
        Expiration = TimeSpan.FromHours(1),
        LocalCacheExpiration = TimeSpan.FromMinutes(30)
    };

    await cache.SetAsync(
        $"product-{id}",
        product,
        options
    );

    return Results.NoContent();
});
```

关于`设置异步`的关键点：

- 它更新 L1 和 L2 缓存
- 您可以为 L1 和 L2 指定不同的超时时间
- 它会覆盖同一键的任何现有值

### [使用缓存标签](#using-cache-tags)

标签对于管理一组相关的缓存条目非常有用。您可以使用标签一次性使多个条目失效：

```
app.MapGet("/categories/{id}/products", async (
    int id,
    HybridCache cache,
    ProductDbContext db,
    CancellationToken ct) =>
{
    var tags = [$"category-{id}", "products"];

    var products = await cache.GetOrCreateAsync(
        $"products-by-category-{id}",
        async token =>
        {
            return await db.Products
                .Where(p => p.CategoryId == id)
                .Include(p => p.Category)
                .ToListAsync(token);
        },
        tags: tags,
        cancellationToken: ct
    );

    return Results.Ok(products);
});

// 使某个分类中的所有产品失效的端点
app.MapPost("/categories/{id}/invalidate", async (
    int id,
    HybridCache cache,
    CancellationToken ct) =>
{
    await cache.RemoveByTagAsync($"category-{id}", ct);

    return Results.NoContent();
});
```

标签的用途包括：

- 使某个分类中的所有产品失效
- 清除特定用户的所有缓存数据
- 当某些内容更改时刷新所有相关数据

### [移除单个条目](#removing-single-entries)

对于特定项的直接缓存失效，使用`移除异步`：

```
app.MapDelete("/products/{id}", async (int id, HybridCache cache) =>
{
    // 首先从数据库中删除
    await DeleteProductFromDatabase(id);

    // 然后从缓存中移除
    await cache.RemoveAsync($"product-{id}");

    return Results.NoContent();
});
```

`移除异步`：

- 从 L1 和 L2 缓存中移除项目
- 立即生效，无延迟
- 如果键不存在，则不执行任何操作
- 可以安全地多次调用

请记住，`混合缓存`为您处理了分布式缓存、序列化和雪崩保护的所有复杂性。您只需专注于缓存键以及何时使缓存失效即可。

## [添加 Redis 作为 L2 缓存](#adding-redis-as-l2-cache)

要使用 [Redis](https://redis.io/) 作为您的分布式缓存：

1.  安装`Microsoft.Extensions.Caching.StackExchangeRedis` NuGet 包：

```
Install-Package Microsoft.Extensions.Caching.StackExchangeRedis
```

2.  配置 Redis 和`混合缓存`：

```
// 添加 Redis
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = "your-redis-connection-string";
});

// 添加混合缓存 - 它将自动使用 Redis 作为 L2
builder.Services.AddHybridCache();
```

`混合缓存`将自动检测并使用 Redis 作为 L2 缓存。

## [总结](#summary)

`混合缓存`简化了 .NET 应用程序中的缓存。它结合了快速的内存缓存和分布式缓存，防止了诸如缓存雪崩之类的常见问题，并且在单服务器和分布式系统中都能很好地工作。

从默认设置和基本使用模式开始 - 该库设计为易于使用，同时解决复杂的缓存问题。
