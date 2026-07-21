---
pubDatetime: 2026-07-21T12:08:54+08:00
title: "EF Core 二级缓存：从零配置到避开生产事故"
description: "EF Core 10 没有内置二级缓存，但用 EFCoreSecondLevelCacheInterceptor 一行代码就能给查询加速 11 倍。这篇文章讲清楚安装、配置、Redis 切换、基准测试，以及 ExecuteUpdate 和分布式部署会让缓存变成定时炸弹的三个坑。"
tags: ["EF Core", ".NET", "Redis", "Caching", "Performance"]
slug: "ef-core-second-level-caching"
ogImage: "../../assets/959/01-cover.png"
source: "https://codewithmukesh.com/blog/ef-core-second-level-caching/"
---

`DbContext` 的变更追踪器是一级缓存，作用域仅限于单个上下文实例。你写了 `context.Products.Where(p => p.IsActive).OrderBy(p => p.Name).Take(100).ToListAsync()`，换一个请求再跑一次，EF Core 照样去数据库执行一遍 SQL —— 一级缓存只做实体身份解析，不做查询结果复用。

要跨请求复用查询结果，得加一个二级缓存。最常用的库是 **EFCoreSecondLevelCacheInterceptor**，它作为 EF Core 拦截器插进查询管线，把查询结果按生成的 SQL 做 key 存起来，`SaveChanges` 时自动失效。内存命中比直连数据库快约 11 倍，Redis 命中快约 2.5 倍。

但这不是没有代价的。`ExecuteUpdate`、原生 SQL、其他服务的写入 —— 这些东西完全绕过拦截器的自动失效机制，轻松让线上吃到几分钟前的脏数据。下面把配置、基准测试和三个最要命的坑一起讲清楚。

## 一级缓存 vs 二级缓存

先把概念对齐。EF Core 里有三层东西叫 "cache"，只有第二级能省掉数据库往返：

| | 一级缓存 | 二级缓存 |
|---|---|---|
| 本质 | 变更追踪器 / 身份映射 | 共享查询结果缓存 |
| 作用域 | 单个 DbContext | 跨上下文、跨请求 |
| 缓存什么 | 已追踪的实体实例（按主键） | 查询结果集（按 SQL + 参数） |
| 内置？ | 是 | 否 |
| 跳过 DB 往返？ | 只有 `Find`/`FindAsync` | 是，命中时 |

一个常见的误解：跑两次相同的 LINQ 查询不等于命中一级缓存。`context.Products.Where(...).ToList()` 每次都执行 SQL，只是返回时如果某一行已经在追踪中，EF Core 会把已有实例换给你。只有 `Find`/`FindAsync` 会在查库之前先看缓存。

EF Core 还有一个内部查询缓存（query cache），但它缓存的是 LINQ 到 SQL 的编译结果，不是查询结果本身。数据库照样查，只是省了翻译步骤。用 `dotnet ef dbcontext optimize` 生成编译模型也一样 —— 这是启动优化，不是结果缓存。

## 三步接入

前提：.NET 10、EF Core 10、Docker（跑 PostgreSQL 和 Redis）。完整示例在[作者的 GitHub 仓库](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/02-database-management-with-ef-core/ef-core-second-level-caching)。

v5 有个重要变化，几乎所有旧教程都写错了：**缓存提供程序被拆成了单独的 NuGet 包**。只装核心包不会有 `UseMemoryCacheProvider()` 方法。

```bash
dotnet add package EFCoreSecondLevelCacheInterceptor
dotnet add package EFCoreSecondLevelCacheInterceptor.MemoryCache
```

在 `Program.cs` 注册：

```csharp
builder.Services.AddEFSecondLevelCache(options =>
    options
        .UseMemoryCacheProvider()
        .ConfigureLogging(true)
        .UseCacheKeyPrefix("EF_")
        .UseDbCallsIfCachingProviderIsDown(TimeSpan.FromMinutes(1)));
```

然后把拦截器注入 `DbContext`：

```csharp
builder.Services.AddDbContext<AppDbContext>((serviceProvider, options) =>
    options
        .UseNpgsql(connectionString)
        .AddInterceptors(serviceProvider.GetRequiredService<SecondLevelCacheInterceptor>()));
```

`SecondLevelCacheInterceptor` 是个 `DbCommandInterceptor`。执行查询时它先把 SQL 和参数值拼成缓存 key，命中就直接返回缓存里的结果集，不执行命令。

### 按查询缓存 vs 全局缓存

推荐按查询显式缓存，每条读路径自己做决定：

```csharp
var products = await context.Products
    .Where(p => p.IsActive)
    .OrderBy(p => p.Name)
    .Take(100)
    .Cacheable(CacheExpirationMode.Absolute, TimeSpan.FromMinutes(5))
    .ToListAsync(ct);
```

`CacheExpirationMode` 有三种：`Absolute`（固定时长后过期）、`Sliding`（空闲时长后过期）、`NeverRemove`。

全局缓存用 `CacheAllQueries` 更省事但更危险 —— 它会把所有读都缓存，包括你没仔细想过的查询：

```csharp
builder.Services.AddEFSecondLevelCache(options =>
    options
        .UseMemoryCacheProvider()
        .CacheAllQueries(CacheExpirationMode.Absolute, TimeSpan.FromMinutes(30))
        .SkipCachingCommands(commandText =>
            commandText.Contains("NEWID()", StringComparison.OrdinalIgnoreCase)));
```

## 切换到 Redis

单机部署时内存提供程序够用。多实例部署就必须上 Redis，否则一个节点 `SaveChanges` 只会清掉自己的本地缓存，其他节点继续返回旧数据。

```bash
dotnet add package EFCoreSecondLevelCacheInterceptor.StackExchange.Redis
```

```csharp
builder.Services.AddEFSecondLevelCache(options =>
    options
        .UseStackExchangeRedisCacheProvider("localhost:6379", TimeSpan.FromMinutes(5))
        .ConfigureLogging(true)
        .UseCacheKeyPrefix("EF_"));
```

注意 Redis 提供程序的签名：它接收连接字符串和一个 `TimeSpan`，形参名叫 `timeout`，但它不是连接超时 —— 是缓存过期时长。

如果你已经在用 .NET 10 的 `HybridCache`（L1 内存 + L2 Redis + 缓存击穿保护），还可以装 `EFCoreSecondLevelCacheInterceptor.HybridCache` 包，先注册 `AddHybridCache()`，再把拦截器指过去。

## 基准测试：命中到底快多少

用 BenchmarkDotNet 对一张 5000 行的 Products 表跑了同一个查询 `Products.Where(p => p.IsActive).OrderBy(p => p.Name).Take(100)`：

| 方式 | 均值 | 相对数据库 |
|---|---|---|
| 无缓存（数据库直连） | 1,440 µs | 基准 |
| 内存缓存命中 | 129 µs | ~11x 更快 |
| Redis 缓存命中 | 569 µs | ~2.5x 更快 |

环境：BenchmarkDotNet 0.15.4、.NET 10、EF Core 10、PostgreSQL 17、Redis 7（Docker 本地），3 次预热 + 10 次迭代。

这个数据库查询本身很快（~1.4ms），索引良好，本地运行。如果数据库更慢或者远程部署，命中收益还会更大。注意缓存不减少内存分配（内存命中反而从 ~137 KB 涨到 ~160 KB，因为需要反序列化），收益在延迟和数据库负载，不在内存。

老实说：只有查询重复频率高、底层读操作昂贵时，这些数字才成立。一个 cheap 的索引查询在本地跑已经很快，Redis 命中可能接近它的成本。缓存对写操作毫无帮助，命中率低时连查询、序列化和失效开销都在亏。

## 脏数据：自动失效的盲区

这是二级缓存最容易出事的地方。拦截器对 `SaveChanges` 的自动失效没问题 —— 它检查变更追踪器，知道哪些表变了，把相关缓存全部清掉。

但下面这些操作完全绕过变更追踪器，拦截器看不见：

- **`ExecuteUpdate` / `ExecuteDelete`**：直接发 SQL，不走 `SaveChanges`，缓存继续返回旧行
- **原生 SQL**（`ExecuteSqlRaw`、`ExecuteSqlInterpolated`）：同样问题
- **其他服务、数据库 Job、存储过程**写同一个表：库对它们零感知

这些情况下，缓存数据一直脏到 TTL 过期。修法：注入 `IEFCacheServiceProvider`，写完手动失效：

```csharp
app.MapPost("/products/deactivate-old", async (
    AppDbContext context,
    IEFCacheServiceProvider cache,
    CancellationToken ct) =>
{
    var affected = await context.Products
        .Where(p => p.CreatedAtUtc < DateTime.UtcNow.AddYears(-1))
        .ExecuteUpdateAsync(s => s.SetProperty(p => p.IsActive, false), ct);

    cache.InvalidateCacheDependencies(
        new EFCacheKey(new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "EF_Products"
        }));

    return Results.Ok(new { Deactivated = affected });
});
```

注意 `EF_` 前缀。库把每个缓存查询的依赖存为前缀 + 表名，你配了 `UseCacheKeyPrefix("EF_")` 之后，依赖键就变成了 `EF_Products`，不是 `Products`。传裸表名不会报错，也不匹配任何东西，数据继续脏。`ClearAllCachedEntries()` 直接清空整个缓存，绕过了前缀陷阱，代价是全局失效。

记住一条规则：**变更追踪器看不见的写操作，缓存也看不见**。任何用了 `ExecuteUpdate`/`ExecuteDelete` 或原生 SQL 的代码路径，必须自己负责手动失效。

### 多实例陷阱

内存二级缓存是进程内缓存。扩展到三个 Pod，Pod A 上的 `SaveChanges` 只清掉 A 的本地缓存，B 和 C 继续从自己的缓存里返回旧数据。QA 环境只有一个实例所以测不出来，生产环境准时爆炸。

唯一的解法是共享缓存：用 Redis 提供程序，或者 `HybridCache` + 分布式 L2 + 背板，让失效跨实例传播。多副本部署时，内存二级缓存对任何要求一致性的数据都不安全。

### 多租户陷阱

缓存 key 是生成的 SQL + 参数值。多租户应用里如果你的租户过滤器没有变成真正的 SQL 参数，两个租户会生成相同的缓存 key，A 的数据就可能返回给 B。这不是脏数据问题，是数据泄露问题。

有两层修复，两层都做：第一，确认租户标识在生成 SQL 里确实是参数，不是常量。第二，把租户写进缓存 key 本身。`UseCacheKeyPrefix` 有一个重载接收 `Func<IServiceProvider, string>`，每次请求重新计算：

```csharp
builder.Services.AddEFSecondLevelCache(options =>
    options
        .UseMemoryCacheProvider()
        .UseCacheKeyPrefix(sp =>
            "EF_" + sp.GetRequiredService<ITenantContext>().TenantId + "_"));
```

这样租户 A 和 B 的 key 前缀永远不同，不可能碰撞。但前缀也影响依赖键名，手动失效时需要用同样的前缀。

## 什么情况下别用二级缓存

二级缓存最适合读多写少的变化缓慢数据：分类、国家、配置、产品目录，以及能容忍轻度过期的昂贵聚合查询。

不要缓存以下内容：

- **易变数据**：频繁修改 → 频繁失效 → 几乎没命中 → 纯亏
- **按用户或按租户的敏感数据**：key 碰撞风险 + 低命中率
- **脏读会导致正确性问题的数据**：账户余额、结账库存、权限判断
- **非确定性查询**：用了 `DateTime.Now`、`Guid.NewGuid()`、`RANDOM()` 的查询，`Take()` 如果顺序不稳定也同理

## 二级缓存 vs HybridCache vs 手动缓存

| | EF 二级缓存 | 手动 cache-aside | 输出缓存 |
|---|---|---|---|
| 缓存什么 | 查询结果集，按 SQL key | 你放什么就是什么，按语义 key | 整个 HTTP 响应 |
| 失效方式 | `SaveChanges` 自动（不含 bulk/raw） | 自己写，精确覆盖每个路径 | 按 tag 或时长 |
| 控制力 | 低：透明，SQL key | 高：自己管 key/TTL/缓存内容 | 中 |
| 适用场景 | 读多写少的参考数据，最少代码 | 精确失效、缓存 DTO、覆盖 bulk/外部写 | 多用户相同的读端点 |
| 主要风险 | bulk/raw/外部写后过期 | 要写和维护更多代码 | 粒度粗 |

我的选择：想让读为主的应用用最少代码加速参考数据，用 EF 二级缓存，但要确保 bulk 写入路径有手动失效。如果失效必须精确，或者想缓存投影 DTO 而非实体结果集，或者写操作经常走 `ExecuteUpdate` 或其他服务 —— 用手动 cache-aside + HybridCache，每条路径自己控制失效。

## 验证缓存是否命中

打开日志 `ConfigureLogging(true)`，拦截器会把每次查询是命中还是落库打出来。最快的验证方式就是看日志，再结合数据库查询指标：缓存正确配置后，预热完成时对应读路径的查询数量应该降到几乎为零。

## Troubleshooting

**`UseMemoryCacheProvider()` 不存在**

你用了 v5 但只装了核心包。补装提供程序包：`.MemoryCache`、`.StackExchange.Redis` 或 `.HybridCache`。

**更新后缓存仍返回旧数据**

写操作绕过了变更追踪器。`ExecuteUpdate`、`ExecuteDelete` 和原生 SQL 不触发自动失效。注入 `IEFCacheServiceProvider`，写完后调 `InvalidateCacheDependencies` 或 `ClearAllCachedEntries`。

**本地缓存正常，生产返回过期数据**

多实例部署但用的内存提供程序。换成 Redis 或 HybridCache。

**缓存从来不命中**

两个常见原因：一是查询参数每次都在变（时间戳或 GUID），每次产生不同的缓存 key；二是查询包在显式事务里。库默认禁用显式事务中的缓存，所以每个请求都用 `BeginTransaction` 的仓储层永远命中不了。打开 `ConfigureLogging(true)` 确认是哪种情况，然后要么稳定参数，要么开 `AllowCachingWithExplicitTransactions(true)`。

**`InvalidateCacheDependencies` 执行了但数据还是旧的**

表名缺了缓存 key 前缀。依赖存的是前缀 + 表名，配了 `UseCacheKeyPrefix("EF_")` 就要传 `EF_Products`，不是 `Products`。不匹配时不会报错，看起来像是执行成功了。

**一个租户看到另一个租户的数据**

租户过滤器不是真正的 SQL 参数，不同租户共享了缓存 key。确保租户标识在 SQL 里参数化，并且用 `UseCacheKeyPrefix` 的动态重载把租户 ID 编进 key 前缀。

## 小结

EF Core 10 没有内置二级缓存，但 EFCoreSecondLevelCacheInterceptor 用三行配置就能接入。它加速只承担读负载、不增加写路径的 API，性能收益在 2.5x 到 11x 之间；但 `ExecuteUpdate`、原生 SQL、外部写入和多实例/多租户场景下的自动失效盲区，是你上线前必须塞进测试用例的东西。按查询显式缓存是更安全的默认选择，Redis/HybridCache 是生产多副本的底线。

## 参考

- [原文：Second-Level Caching in EF Core 10: The Complete Guide](https://codewithmukesh.com/blog/ef-core-second-level-caching/)
- [EFCoreSecondLevelCacheInterceptor GitHub](https://github.com/VahidN/EFCoreSecondLevelCacheInterceptor)
- [示例仓库](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/02-database-management-with-ef-core/ef-core-second-level-caching)
- [EF Core 高级性能主题](https://learn.microsoft.com/en-us/ef/core/performance/advanced-performance-topics)
