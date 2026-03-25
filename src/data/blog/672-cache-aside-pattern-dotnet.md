---
pubDatetime: 2026-03-25T09:40:00+08:00
title: "Cache-Aside 模式在 .NET 中的实践"
description: "Cache-Aside（懒加载）是 .NET 应用中最常见的缓存策略之一。本文讲解它的执行流程、.NET 实现方式、过期策略选择，以及缓存失效、缓存雪崩等常见问题的处理方法。"
tags: [".NET", "C#", "Caching", "Architecture", "Performance"]
slug: "cache-aside-pattern-dotnet"
ogImage: "../../assets/672/01-cover.png"
source: "https://malshikay.medium.com/cache-aside-pattern-in-net-44f0d9a76b65"
---

数据库调用通常是 ASP.NET Core 应用中开销最大的操作。合理引入缓存，可以让读多写少的接口响应时间从几百毫秒降到几毫秒。

Cache-Aside 模式（又称 Lazy Loading，懒加载缓存）是 .NET 生态里最主流的缓存策略。它的核心是：**应用代码自己决定何时读缓存、何时写缓存**，缓存层本身不会自动同步数据库。

![Cache-Aside 缓存模式概念图](../../assets/672/01-cover.png)

## 执行流程

每次读取数据时，流程如下：

1. 先查缓存
2. 缓存命中 → 直接返回
3. 缓存未命中 → 查数据库
4. 将结果写入缓存
5. 返回数据给调用方

这样只有真正被访问过的数据才会进入缓存，不会无差别地预热全部数据。

## 适合这个模式的场景

Cache-Aside 在以下情况效果最好：

- 数据读取频繁，但更新不频繁
- 允许短暂的数据一致性延迟
- 从数据库拉取数据的代价较高

典型的业务场景包括：商品或商品目录数据、用户资料、配置项和参考数据、读多写少的 API 端点。

## 用 IMemoryCache 实现

`IMemoryCache` 是 ASP.NET Core 内置的内存缓存接口，适合单实例部署场景。

### 服务类结构

```csharp
public class ProductService
{
    private readonly IMemoryCache _cache;
    private readonly AppDbContext _dbContext;

    public ProductService(IMemoryCache cache, AppDbContext dbContext)
    {
        _cache = cache;
        _dbContext = dbContext;
    }
}
```

### Cache-Aside 核心逻辑

```csharp
public async Task<Product> GetProduct(int id)
{
    var cacheKey = $"product_{id}";

    if (!_cache.TryGetValue(cacheKey, out Product product))
    {
        product = await _dbContext.Products.FindAsync(id);

        if (product != null)
        {
            var options = new MemoryCacheEntryOptions()
                .SetSlidingExpiration(TimeSpan.FromMinutes(5))
                .SetAbsoluteExpiration(TimeSpan.FromMinutes(30));

            _cache.Set(cacheKey, product, options);
        }
    }

    return product;
}
```

这段代码的行为：**第一次请求**查数据库并写入缓存；**后续请求**直接命中缓存，不再触及数据库；**缓存过期后**，下一次请求重新触发数据库查询。

## 过期策略怎么选

过期策略直接影响缓存命中率和数据新鲜度，需要根据业务场景权衡。

### 滑动过期（Sliding Expiration）

只要缓存条目在指定时间窗口内持续被访问，它就不会过期。适合热点数据，避免频繁访问的数据被驱逐。

### 绝对过期（Absolute Expiration）

从写入起计算固定时长，到期即删除，不论是否被访问。可以保证数据定期刷新，防止长期使用陈旧数据。

### 组合使用

上面代码中同时设置了两者：滑动 5 分钟 + 绝对 30 分钟。滑动过期处理热点，绝对过期兜底，在性能和数据新鲜度之间取得平衡。

## 数据更新时的缓存失效

缓存一致性是 Cache-Aside 的主要挑战。数据库写入之后，必须同步处理缓存，否则下次读取会拿到旧数据。

常见做法是**写入数据库后立即删除对应缓存条目**，让下一次读请求自然触发缓存重建：

```csharp
public async Task UpdateProduct(Product product)
{
    _dbContext.Products.Update(product);
    await _dbContext.SaveChangesAsync();

    var cacheKey = $"product_{product.Id}";
    _cache.Remove(cacheKey);
}
```

## 常见问题及应对

### 缓存雪崩（Cache Stampede）

当某个高频缓存条目过期时，大量并发请求同时穿透到数据库，造成瞬时压力。

应对方式：引入锁机制、请求合并（request coalescing），或者在高并发场景下切换到 Redis 等分布式缓存。

### 数据过时（Stale Data）

缓存未及时失效时，读到的是旧数据。应对方式：缩短过期时间，或改用事件驱动失效（数据变更时主动推送删除缓存）。

### 内存压力（Memory Pressure）

内存缓存直接占用应用进程内存。应对方式：限制缓存总大小，避免缓存大对象，多实例部署时改用分布式缓存。

## 多实例部署与分布式缓存

`IMemoryCache` 是进程内缓存，每个应用实例维护独立的缓存副本。在负载均衡环境下，同一个用户的请求可能落到不同实例，缓存数据不一致。

这时需要引入 Redis 等分布式缓存。Cache-Aside 的逻辑不变，只是换一个缓存提供方。分布式缓存能带来跨实例共享、更好的一致性和水平扩展能力。

## 实践建议

- 使用有意义的缓存键，建议加上实体类型前缀，例如 `product_123`
- 不要缓存 `null` 或无效数据，除非有明确的业务理由
- 监控缓存命中率和未命中率，用指标驱动调整策略
- 过期时长应与业务对数据新鲜度的要求对齐，而不是图方便拍一个固定值
- 配合日志和指标，让缓存行为可观测

## 参考

- [Cache-Aside Pattern in .NET — Yohan Malshika](https://malshikay.medium.com/cache-aside-pattern-in-net-44f0d9a76b65)
