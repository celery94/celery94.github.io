---
pubDatetime: 2026-04-07T07:54:00+08:00
title: "HybridCache in ASP.NET Core .NET 10 完全指南"
description: "深入解析 ASP.NET Core .NET 10 中的 HybridCache：L1/L2 双层架构、防雪崩保护原理（100 并发仅触发 1 次数据库查询）、基于 Tag 的批量失效、Redis L2 配置与 IDistributedCache 迁移指南，附 BenchmarkDotNet 性能数据。"
tags: ["dotnet", "caching", "aspnet-core", "redis", "performance"]
slug: "hybridcache-in-aspnet-core"
ogImage: "../../assets/716/01-cover.webp"
source: "https://codewithmukesh.com/blog/hybridcache-in-aspnet-core/"
---

我在每个需要 Redis 缓存的项目里，都要手写一套 `IDistributedCache` 扩展方法——`GetOrSetAsync`、`TryGetValue`、`SetAsync`，带泛型，几十行样板代码，项目换了再复制一遍。HybridCache 用一个 `GetOrCreateAsync` 调用让这些代码全部成了历史。但这还不是最重要的。最重要的是防雪崩（stampede protection）。我对着一个冷缓存发了 100 个并发请求，用 `IMemoryCache` 跑了 100 次数据库查询，用 HybridCache 只跑了 1 次。

这篇文章会带你完整走过 HybridCache 在 ASP.NET Core .NET 10 中的所有内容——L1/L2 架构、完整 API 接口、基于 Tag 的失效、Redis 作为 L2 的配置方式、与 `IDistributedCache` 的对比迁移，以及附有日志证据的防雪崩演示和 BenchmarkDotNet 数据。

## HybridCache 是什么

HybridCache 是一个 .NET 库（.NET 9 GA，.NET 10 稳定），通过单一的 `GetOrCreateAsync` 方法提供统一的缓存 API，把 L1 内存缓存与可选的 L2 分布式缓存结合在一起，同时内置防雪崩保护和基于 Tag 的失效机制。它通过 `Microsoft.Extensions.Caching.Hybrid` NuGet 包发布，是微软官方推荐用于新 ASP.NET Core 项目的缓存方案。

L1/L2 架构的工作方式：

**L1（内存层）**：每个应用实例维护自己的进程内内存缓存，和 `IMemoryCache` 一样。命中 L1 是纳秒级，零序列化。

**L2（分布式层）**：可选的外部缓存（Redis、SQL Server 或任何 `IDistributedCache` 实现）。L1 未命中时，HybridCache 先检查 L2，再触发数据库查询。L2 层的数据需要序列化，跨实例共享。

**工厂执行**：L1 和 L2 都未命中时，HybridCache 执行你的工厂委托（数据库查询），把结果写入 L1 和 L2，然后返回。关键在于：同一个 Key 的并发调用中，只有一个调用者执行工厂，其余全部等待结果。

.NET Blog GA 公告里把它描述为 `IDistributedCache` 和 `IMemoryCache` 的"直接替代"，基本准确，后面会补充一些细节。

HybridCache 与手动组合 `IMemoryCache` + `IDistributedCache` 的本质区别是：它自动处理两层之间的协作。你不需要写"先检查 L1、再检查 L2、再查数据库、再填两层缓存"的逻辑，一次方法调用搞定一切。防雪崩保护让你永远不会遇到缓存未命中时 100 个并发请求同时打数据库的情况。

## 什么时候用 HybridCache

下面是三种缓存方案的完整对比：

| 指标 | IMemoryCache | IDistributedCache | HybridCache |
|------|-------------|------------------|-------------|
| 数据范围 | 单进程 | 跨实例共享 | L1 本地 + L2 共享 |
| 网络延迟 | 无 | 1-5ms | L1 无，L2 1-5ms |
| 重启后存活 | 否 | 是 | L2：是 |
| 序列化 | 无（存引用） | 必须（JSON/二进制） | L1 无，L2 必须 |
| 防雪崩 | 否（手写 SemaphoreSlim） | 否（手写） | 是（内置） |
| Tag 失效 | 否 | 否（手写） | 是（RemoveByTagAsync） |
| GetOrCreateAsync | 有（但无防雪崩） | 否（需扩展方法） | 有（含防雪崩） |
| 最低版本 | 全版本 | 全版本 | .NET 9+ |

### 不推荐用 HybridCache 的场景

- **单实例 API 且不需要 L2**：只跑一个 Pod 的话，`IMemoryCache` + `GetOrCreateAsync` 更简单，没有额外抽象层。
- **Redis 原生功能**：如果你需要 pub/sub、sorted set、Lua 脚本等 Redis 特有数据结构，直接用 `StackExchange.Redis`。HybridCache 把 Redis 当作 key-value L2，高级能力用不上。
- **会话或用户状态**：HybridCache 为读密集型共享数据设计（商品目录、配置、字典表）。用户专属的 Session 数据用 `IDistributedCache` + Redis 更合适，L1 缓存对用户专属数据价值不大。

对于新的 .NET 10 项目，即使没配置 L2，HybridCache 也能提供防雪崩保护和 Tag 失效，这两个能力 `IMemoryCache` 永远不会有。加了第二个 Pod 时，追加 Redis 作为 L2，代码完全不变。

## 配置 HybridCache

安装包：

```bash
dotnet add package Microsoft.Extensions.Caching.Hybrid --version 10.4.0
```

在 `Program.cs` 中注册：

```csharp
#pragma warning disable EXTEXP0018

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHybridCache(options =>
{
    options.DefaultEntryOptions = new HybridCacheEntryOptions
    {
        LocalCacheExpiration = TimeSpan.FromMinutes(5),
        Expiration = TimeSpan.FromMinutes(30)
    };
    options.MaximumPayloadBytes = 1024 * 1024; // 1 MB 最大缓存条目
});
```

几个关键说明：

`#pragma warning disable EXTEXP0018` 是必需的。HybridCache API 在 .NET 10 中仍标记为 `[Experimental]`，不加这个 pragma 会报编译错误。这不意味着库不稳定——它从 .NET 9 已经 GA，生产可用。Experimental 标志只代表 API 签名在未来小版本中可能调整。核心的 `GetOrCreateAsync` 和 `RemoveByTagAsync` API 从 .NET 9 GA 起就稳定了。也可以在 `.csproj` 中加 `<NoWarn>EXTEXP0018</NoWarn>` 全局屏蔽。

`DefaultEntryOptions` 设置全局默认的过期时间，对没有自定义选项的条目生效。`LocalCacheExpiration` 控制 L1 生存时间，`Expiration` 控制 L2 生存时间。

`MaximumPayloadBytes` 限制单条缓存条目的最大体积。超出限制的条目会被静默跳过（不缓存）。建议始终设置，防止意外缓存一个巨大的对象图把内存打爆。

不配置任何 L2 时，HybridCache 本身就是一个纯内存缓存，但同时具备防雪崩保护和 Tag 失效。

## HybridCache 的四个方法

整个 API 只有四个方法。

### GetOrCreateAsync（主力方法）

90% 的情况下你用这个。它一次调用完成完整的 cache-aside 模式：

```csharp
var product = await hybridCache.GetOrCreateAsync(
    $"product:{id}",                              // 缓存 Key
    async ct => await context.Products            // 工厂（未命中时执行）
        .AsNoTracking()
        .FirstOrDefaultAsync(p => p.Id == id, ct),
    new HybridCacheEntryOptions                   // 可选的每条目选项
    {
        LocalCacheExpiration = TimeSpan.FromMinutes(5),
        Expiration = TimeSpan.FromMinutes(30)
    },
    tags: ["products"],                           // 用于批量失效的 Tag
    cancellationToken: cancellationToken);
```

调用流程：

1. 检查 L1（内存）。命中则立即返回，零序列化，纳秒级。
2. L1 未命中且配了 L2，检查 L2（Redis）。命中则反序列化，写入 L1，返回。
3. 两层都未命中，对该 Key 加锁（防雪崩）。只有一个调用者执行工厂委托，其余并发调用者等待结果。
4. 把结果写入 L1 和 L2（如配置），返回值。

工厂委托接收一个 `CancellationToken` 参数 `ct`，始终用它而不是捕获外层的 cancellation token，因为 HybridCache 内部管理工厂的取消逻辑。

### SetAsync（直接写入）

适合在创建或更新后预热缓存，而不是直接失效：

```csharp
await hybridCache.SetAsync(
    $"product:{product.Id}",
    product,
    new HybridCacheEntryOptions { LocalCacheExpiration = TimeSpan.FromMinutes(5), Expiration = TimeSpan.FromMinutes(30) },
    tags: ["products"],
    cancellationToken: cancellationToken);
```

### RemoveAsync（单条失效）

按 Key 从 L1 和 L2 移除一条缓存：

```csharp
await hybridCache.RemoveAsync($"product:{id}", cancellationToken);
```

### RemoveByTagAsync（批量失效）

这是 `IMemoryCache` 和 `IDistributedCache` 都没有的杀手级特性。移除所有带指定 Tag 的缓存条目：

```csharp
await hybridCache.RemoveByTagAsync("products", cancellationToken);
```

一次调用失效所有带 `"products"` Tag 的条目，不管单条 Key 是什么。

## HybridCacheEntryOptions 详解

```csharp
var options = new HybridCacheEntryOptions
{
    LocalCacheExpiration = TimeSpan.FromMinutes(5),   // L1 生存时间
    Expiration = TimeSpan.FromMinutes(30),            // L2 生存时间
    Flags = HybridCacheEntryFlags.None                // 默认行为
};
```

**为什么要两个过期时间？** 设想三个 API Pod 共用 Redis L2，Pod 1 把商品列表写入 L1。管理员更新了商品并失效了 Redis Key。如果 Pod 2 的 `LocalCacheExpiration` 是 30 分钟，它会用 L1 的旧数据服务长达 30 分钟；如果是 5 分钟，旧数据窗口就小得多。代价是更短的 L1 过期意味着更多 L2 网络调用，但数据更新鲜。

推荐默认比例：L1 5 分钟，L2 30 分钟（1:6）。变化频繁的数据（库存、订单数）可以把 L1 降到 1-2 分钟；极少变化的数据（权限集、配置）可以把 L1 提到 15 分钟。

`Flags` 选项：`HybridCacheEntryFlags.DisableLocalCacheRead` 跳过 L1 直接检查 L2，`DisableLocalCacheWrite` 阻止写入 L1。适合调试，或需要立即一致性时牺牲性能使用。

## 完整的 Product API 示例

### 数据层

```csharp
public class Product
{
    public Guid Id { get; set; }
    public string Name { get; set; } = default!;
    public string Description { get; set; } = default!;
    public decimal Price { get; set; }
    public string Category { get; set; } = default!;

    private Product() { }

    public Product(string name, string description, decimal price, string category)
    {
        Id = Guid.NewGuid();
        Name = name;
        Description = description;
        Price = price;
        Category = category;
    }
}

public record ProductCreationDto(string Name, string Description, decimal Price, string Category);
```

`Category` 字段是关键——它让我们可以按分类打 Tag，从而实现"只失效电子类商品"而不影响服装类缓存。

连接字符串配置（生产环境请用环境变量或 User Secrets）：

```json
"ConnectionStrings": {
  "Database": "Host=localhost;Database=hybridcaching;Username=postgres;Password=yourpassword;Include Error Detail=true"
}
```

### ProductService 完整实现

```csharp
public class ProductService(
    AppDbContext context,
    HybridCache cache,
    ILogger<ProductService> logger) : IProductService
{
    private const string AllProductsCacheKey = "products";

    public async Task<List<Product>> GetAllAsync(CancellationToken cancellationToken = default)
    {
        logger.LogInformation("Fetching data for key: {CacheKey}.", AllProductsCacheKey);

        var products = await cache.GetOrCreateAsync(
            AllProductsCacheKey,
            async ct =>
            {
                logger.LogInformation("Cache miss for key: {CacheKey}. Fetching from database.", AllProductsCacheKey);
                return await context.Products.AsNoTracking().ToListAsync(ct);
            },
            new HybridCacheEntryOptions
            {
                LocalCacheExpiration = TimeSpan.FromMinutes(5),
                Expiration = TimeSpan.FromMinutes(30)
            },
            tags: ["products"],
            cancellationToken: cancellationToken);

        return products ?? [];
    }

    public async Task<Product?> GetByIdAsync(Guid id, CancellationToken cancellationToken = default)
    {
        var cacheKey = $"product:{id}";
        logger.LogInformation("Fetching data for key: {CacheKey}.", cacheKey);

        return await cache.GetOrCreateAsync(
            cacheKey,
            async ct =>
            {
                logger.LogInformation("Cache miss for key: {CacheKey}. Fetching from database.", cacheKey);
                return await context.Products.AsNoTracking()
                    .FirstOrDefaultAsync(p => p.Id == id, ct);
            },
            tags: ["products"],
            cancellationToken: cancellationToken);
    }

    public async Task<List<Product>> GetByCategoryAsync(string category, CancellationToken cancellationToken = default)
    {
        var cacheKey = $"products:category:{category}";

        var products = await cache.GetOrCreateAsync(
            cacheKey,
            async ct => await context.Products.AsNoTracking()
                .Where(p => p.Category == category)
                .ToListAsync(ct),
            tags: ["products", $"category:{category}"],
            cancellationToken: cancellationToken);

        return products ?? [];
    }

    public async Task<Product> CreateAsync(ProductCreationDto request, CancellationToken cancellationToken = default)
    {
        var product = new Product(request.Name, request.Description, request.Price, request.Category);
        await context.Products.AddAsync(product, cancellationToken);
        await context.SaveChangesAsync(cancellationToken);

        logger.LogInformation("Invalidating cache for tags: products, category:{Category}.", request.Category);
        await cache.RemoveByTagAsync("products", cancellationToken);

        return product;
    }

    public async Task<Product?> UpdateAsync(Guid id, ProductCreationDto request, CancellationToken cancellationToken = default)
    {
        var product = await context.Products.FindAsync([id], cancellationToken);
        if (product is null) return null;

        product.Name = request.Name;
        product.Description = request.Description;
        product.Price = request.Price;
        product.Category = request.Category;

        await context.SaveChangesAsync(cancellationToken);

        logger.LogInformation("Invalidating cache for key: product:{ProductId} and tag: products.", id);
        await cache.RemoveAsync($"product:{id}", cancellationToken);
        await cache.RemoveByTagAsync("products", cancellationToken);

        return product;
    }

    public async Task<bool> DeleteAsync(Guid id, CancellationToken cancellationToken = default)
    {
        var product = await context.Products.FindAsync([id], cancellationToken);
        if (product is null) return false;

        context.Products.Remove(product);
        await context.SaveChangesAsync(cancellationToken);

        logger.LogInformation("Invalidating cache for key: product:{ProductId} and tag: products.", id);
        await cache.RemoveAsync($"product:{id}", cancellationToken);
        await cache.RemoveByTagAsync("products", cancellationToken);

        return true;
    }
}
```

几个关键模式：

- **每次 GetOrCreateAsync 都带 Tag**。`GetByCategoryAsync` 同时带 `["products", $"category:{category}"]`，可以精细化失效控制。
- **工厂委托统一用 `ct` 参数**，不捕获外层 cancellation token。
- **写操作在返回前失效缓存**，而不是返回后。如果在响应返回后才失效，并发请求可能在数据库写入和缓存失效之间把旧数据重新缓存进来。
- `UpdateAsync` 同时调用 `RemoveAsync`（精确失效单条）和 `RemoveByTagAsync`（批量失效列表缓存），确保各层都不残留旧数据。

### Minimal API 注册

```csharp
var products = app.MapGroup("/products").WithTags("Products");

products.MapGet("/", async (IProductService service, CancellationToken ct) =>
    TypedResults.Ok(await service.GetAllAsync(ct)));

products.MapGet("/{id:guid}", async (Guid id, IProductService service, CancellationToken ct) =>
{
    var product = await service.GetByIdAsync(id, ct);
    return product is not null ? TypedResults.Ok(product) : Results.NotFound();
});

products.MapGet("/category/{category}", async (string category, IProductService service, CancellationToken ct) =>
    TypedResults.Ok(await service.GetByCategoryAsync(category, ct)));

products.MapPost("/", async (ProductCreationDto request, IProductService service, CancellationToken ct) =>
{
    var product = await service.CreateAsync(request, ct);
    return TypedResults.Created($"/products/{product.Id}", product);
});

products.MapPut("/{id:guid}", async (Guid id, ProductCreationDto request, IProductService service, CancellationToken ct) =>
{
    var product = await service.UpdateAsync(id, request, ct);
    return product is not null ? TypedResults.Ok(product) : Results.NotFound();
});

products.MapDelete("/{id:guid}", async (Guid id, IProductService service, CancellationToken ct) =>
{
    var deleted = await service.DeleteAsync(id, ct);
    return deleted ? TypedResults.NoContent() : Results.NotFound();
});

builder.Services.AddScoped<IProductService, ProductService>();
```

## 配置 Redis 作为 L2

### Docker Compose

```yaml
services:
  redis:
    image: redis:7.4
    container_name: redis
    ports:
      - "6379:6379"
    command: redis-server --requirepass yourpassword --appendonly yes
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

启动：`docker-compose up -d`

### Program.cs 注册

安装包：

```bash
dotnet add package Microsoft.Extensions.Caching.StackExchangeRedis --version 10.0.0
```

添加连接字符串到 `appsettings.json`（生产环境请用环境变量）：

```json
{
  "ConnectionStrings": {
    "Database": "Host=localhost;Database=hybridcaching;Username=postgres;Password=yourpassword;Include Error Detail=true",
    "Redis": "localhost:6379,password=yourpassword,abortConnect=false"
  }
}
```

注册服务：

```csharp
#pragma warning disable EXTEXP0018

builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration.GetConnectionString("Redis");
    options.InstanceName = "myapp:";
});

builder.Services.AddHybridCache(options =>
{
    options.DefaultEntryOptions = new HybridCacheEntryOptions
    {
        LocalCacheExpiration = TimeSpan.FromMinutes(5),
        Expiration = TimeSpan.FromMinutes(30)
    };
    options.MaximumPayloadBytes = 1024 * 1024;
});
```

HybridCache 会自动检测 `IDistributedCache` 的注册（来自 `AddStackExchangeRedisCache`）并将其用作 L2，不需要手动接线，注册顺序也不影响。

`abortConnect=false` 的作用：StackExchange.Redis 在 Redis 启动时不抛异常，而是在后台重试连接。生产环境建议始终设置为 `false`。

`InstanceName` 作为 Redis Key 前缀，避免多个应用共用同一个 Redis 实例时的 Key 冲突。

配置后 HybridCache 工作在完整的 L1+L2 模式：

- 第一次请求（冷启动）：L1 未命中，L2 未命中，工厂执行，结果写入两层。
- 同一 Pod 第二次请求：L1 命中，零网络调用，纳秒级。
- 不同 Pod 的请求：L1 未命中（不同进程），L2 命中（Redis），反序列化后写入该 Pod 的 L1。
- L1 过期（5 分钟）后：命中 L2，重新填充 L1。
- L2 过期（30 分钟）后：两层都未命中，工厂重新执行。

## Tag 失效的工作原理

考虑这个场景：

| 缓存 Key | Tags |
|---------|------|
| `products`（全量） | `["products"]` |
| `products:category:Electronics` | `["products", "category:Electronics"]` |
| `products:category:Clothing` | `["products", "category:Clothing"]` |
| `product:{id1}`（电子类） | `["products"]` |
| `product:{id2}`（服装类） | `["products"]` |

**场景一：新建商品**，调用 `RemoveByTagAsync("products")`，失效所有带 `"products"` Tag 的条目。全量列表、所有分类列表、所有单条商品全部失效。这是最保守也最安全的做法，因为新商品同时影响全量列表和分类列表。

**场景二：仅失效某分类**（例如电子类价格批量更新），调用 `RemoveByTagAsync("category:Electronics")`，只失效 `products:category:Electronics`，服装类和全量列表缓存不受影响。

**场景三：更新单条商品** 可以组合使用：`RemoveAsync($"product:{id}")` 精确失效单条，再用 `RemoveByTagAsync("products")` 失效列表缓存。

Tag 失效的真正价值在有 20+ 个缓存 Key 的实际应用中体现。手动跟踪每次写操作要删哪些 Key，极容易漏掉一个。Tags 让你可以用"失效所有商品数据"的思维写代码，而不是罗列一串 Key 祈祷不遗漏。

## 防雪崩：日志证据

缓存雪崩（也叫 thundering herd）：商品目录缓存到期的那一刻，100 个请求同时打来。有了 `IMemoryCache`，100 个请求全部看到缓存未命中，100 个数据库查询同时发出。如果一次查询需要 500ms，数据库连接池只有 20 个连接，剩余 80 个请求排队，超时开始级联，API 返回 500 错误。

**IMemoryCache 的行为（无保护）**：

```csharp
// 100 并发请求，各自独立触发工厂
var products = await cache.GetOrCreateAsync("products", async entry =>
{
    var count = Interlocked.Increment(ref _factoryExecutionCount);
    logger.LogWarning("IMemoryCache factory executing. Execution #{Count}", count);
    await Task.Delay(200, cancellationToken); // 模拟慢速数据库查询
    return await context.Products.AsNoTracking().ToListAsync(cancellationToken);
});
```

预期输出：

```
warn: IMemoryCache factory executing. Execution #1
warn: IMemoryCache factory executing. Execution #2
...
warn: IMemoryCache factory executing. Execution #97
warn: IMemoryCache factory executing. Execution #98
```

`IMemoryCache.GetOrCreateAsync` 不对同一 Key 加锁，所有并发调用者都看到空缓存并执行工厂。

**HybridCache 的行为（内置保护）**：

```csharp
var products = await cache.GetOrCreateAsync(
    "stampede-test-products",
    async ct =>
    {
        var count = Interlocked.Increment(ref _factoryExecutionCount);
        logger.LogWarning("HybridCache factory executing. Execution #{Count}", count);
        await Task.Delay(200, ct);
        return await context.Products.AsNoTracking().ToListAsync(ct);
    },
    tags: ["stampede-test"],
    cancellationToken: cancellationToken);
```

预期输出：

```
warn: HybridCache factory executing. Execution #1
```

只有一次。只有一条数据库查询。其余 99 个请求等待第一个完成并共享结果。HybridCache 内部使用基于 `SemaphoreSlim` 的 Key 级加锁机制——第一个调用者持锁执行工厂，后续对同一 Key 的并发调用等锁，不重复执行工厂。

这一个特性就足以让你从 `IMemoryCache` 切换到 HybridCache。手写 `SemaphoreSlim` 包装缓存代码既容易出错又容易忘记加。HybridCache 把防雪崩变成了默认行为。

## BenchmarkDotNet 性能数据

HybridCache L1 缓存命中约 0.05 微秒，比原始 `IMemoryCache`（0.02μs）慢 30 纳秒，比 Redis `IDistributedCache` 调用（1200μs）快 24000 倍。

| 测试方法 | 平均耗时 | 内存分配 |
|---------|---------|---------|
| SingleProduct_DatabaseFetch | ~500 μs | ~8 KB |
| SingleProduct_MemoryCacheHit | ~0.02 μs | 0 B |
| SingleProduct_RedisCacheHit | ~1,200 μs | ~4 KB |
| SingleProduct_HybridCache_L1Hit | ~0.05 μs | ~200 B |
| AllProducts_DatabaseFetch (1000) | ~12,000 μs | ~650 KB |
| AllProducts_MemoryCacheHit (1000) | ~0.02 μs | 0 B |
| AllProducts_RedisCacheHit (1000) | ~3,500 μs | ~420 KB |
| AllProducts_HybridCache_L1Hit (1000) | ~0.08 μs | ~400 B |

测试环境：.NET 10.0.0，PostgreSQL 17 + Redis 7.4 在 Docker Desktop 上运行，Windows 11，10 次迭代取平均值。

**分析**：HybridCache L1 比原始 `IMemoryCache` 慢不到 1 微秒，多出的那点分配来自 HybridCache 的内部状态对象。在 HTTP 请求级别完全感知不到这 30 纳秒的差异——仅 HTTP pipeline 就有 50-200μs 开销。真正值得关注的比较是 HybridCache L1（0.05μs）vs Redis（1200μs），前者快了 24000 倍。L1 层的意义在于：你享受 Redis 的跨实例一致性，99% 的请求却以内存速度响应。

## 从 IDistributedCache 迁移

**迁移前**：有一个 50+ 行的 `DistributedCacheExtensions.cs`，包含泛型 `SetAsync<T>`、`TryGetValue<T>`、`GetOrSetAsync<T>`，每次都要手动序列化/反序列化：

```csharp
// 旧写法：手写扩展方法 + 手动序列化
var products = await cache.GetOrSetAsync(
    "products",
    async () => await context.Products.AsNoTracking().ToListAsync(cancellationToken),
    new DistributedCacheEntryOptions().SetAbsoluteExpiration(TimeSpan.FromMinutes(20)),
    cancellationToken);
```

**迁移后**：

```csharp
// 新写法：删掉扩展方法文件，替换注入类型
var products = await cache.GetOrCreateAsync(
    "products",
    async ct => await context.Products.AsNoTracking().ToListAsync(ct),
    new HybridCacheEntryOptions { LocalCacheExpiration = TimeSpan.FromMinutes(5), Expiration = TimeSpan.FromMinutes(20) },
    tags: ["products"],
    cancellationToken: cancellationToken);
```

**变化的内容**：

1. 删除扩展方法文件，`GetOrSetAsync`/`TryGetValue<T>`/`SetAsync<T>` 全部由 `HybridCache.GetOrCreateAsync` 和 `HybridCache.SetAsync` 替代。
2. 把注入类型从 `IDistributedCache` 换成 `HybridCache`，同时在 `Program.cs` 追加 `AddHybridCache()`（已有的 `AddStackExchangeRedisCache()` 保留）。
3. 把 `GetOrSetAsync` 换成 `GetOrCreateAsync`，注意工厂委托现在接收一个 `ct` 参数。
4. 把单条 `cache.RemoveAsync` 替换为 `cache.RemoveByTagAsync`，获得批量失效能力。
5. 在直接调用 HybridCache 方法的文件顶部加 `#pragma warning disable EXTEXP0018`。

**保持不变的内容**：缓存 Key 命名模式不变，过期策略逻辑不变（只是多了 `LocalCacheExpiration`），Redis 基础设施不变（`AddStackExchangeRedisCache` 留着）。

如果线上的 `IDistributedCache` 方案运行良好，没有必要紧急迁移。我的建议是在重大重构时顺带迁移，或者新增服务时直接用 HybridCache。

## 常见问题与解决方式

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 多 Pod 服务陈旧数据 | `LocalCacheExpiration` 相对 `Expiration` 太长 | 比例保持 1:6（5 分钟 L1，30 分钟 L2） |
| L2 反序列化报 `JsonException` | 部署后模型变更，Redis 里存的还是旧格式 | 版本化 Key（`"v2:products"`）或部署前失效 |
| 条目静默不缓存 | 序列化体积超出 `MaximumPayloadBytes` | 增大限制或改为缓存 DTO 而非完整实体图 |
| 写操作后命中率骤降 | Tag 粒度太粗，每次删全部 | 用更细化的 Tag（`"products:list"`、`"category:Electronics"`） |
| Redis 停服 API 仍可用 | L1 独立工作，L2 失败优雅降级 | 这是特性，不是 Bug |
| 有 L2 数据但工厂仍然执行 | Redis 超时或反序列化失败 | 检查 Redis 延迟和模型兼容性 |

## 总结

HybridCache 是 ASP.NET Core 一直应该内置的缓存库。它消除了 `IDistributedCache` 扩展方法的样板代码，解决了 `IMemoryCache` 无视的雪崩问题，在不需要你写管道代码的前提下提供了 L1+L2 的分层能力。

对于新的 .NET 10 项目，这是我的默认缓存选择。两行注册，零样板，生产级别的缓存能力开箱即用。

## 参考

- [原文：HybridCache in ASP.NET Core .NET 10 - Complete Guide](https://codewithmukesh.com/blog/hybridcache-in-aspnet-core/)
- [Microsoft 官方文档：HybridCache](https://learn.microsoft.com/en-us/aspnet/core/performance/caching/hybrid?view=aspnetcore-10.0)
- [NuGet：Microsoft.Extensions.Caching.Hybrid](https://www.nuget.org/packages/Microsoft.Extensions.Caching.Hybrid)
- [dotnet/extensions 仓库](https://github.com/dotnet/extensions)
- [示例代码仓库](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/04-performance-and-caching/hybridcache-in-aspnet-core)
