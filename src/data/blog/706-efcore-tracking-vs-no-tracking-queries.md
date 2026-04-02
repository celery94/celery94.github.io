---
pubDatetime: 2026-04-02T09:00:00+08:00
title: "EF Core 10 追踪与非追踪查询：基准测试与决策指南"
description: "深入解析 EF Core 的 Change Tracker 机制，通过 BenchmarkDotNet 实测数据对比 Tracking、AsNoTracking、AsNoTrackingWithIdentityResolution 三种模式的性能差异，并给出在 ASP.NET Core Web API 中如何选择的完整决策指南。"
tags: ["EF Core", ".NET", "Performance", "ASP.NET Core"]
slug: "efcore-tracking-vs-no-tracking-queries"
ogImage: "../../assets/706/01-cover.png"
source: "https://codewithmukesh.com/blog/tracking-vs-no-tracking-queries-efcore/"
---

每次通过 Entity Framework Core 执行查询时，后台都会发生一件你可能从未留意的事：EF Core 会对返回的每一个实体拍一张"快照"，存入内部的 Change Tracker。调用 `SaveChanges()` 时，它通过逐一比对当前值与快照来生成正确的 SQL。这就是 EF Core 能"神奇地"知道哪些行需要更新的原因。

这份魔法有代价。对每个被追踪的实体，EF Core 都需要分配快照内存、维护标识解析（identity resolution）的内部数据结构，并在 `SaveChanges()` 时执行比较逻辑。加载 10 条记录时开销可以忽略不计；加载 10,000 条记录时，内存与 CPU 的消耗就相当可观了。

修复方法很直接：如果不打算修改数据，就告诉 EF Core 不要追踪。但**知道在哪里该这么做**——以及理解其中的权衡——才是大多数教程没讲清楚的地方。

![封面](../../assets/706/01-cover.png)

## Change Tracking 是什么

Change Tracking 是 EF Core 用于检测实体修改、从而生成正确 SQL 的机制。查询实体时，EF Core 将其原始属性值的快照存入 `ChangeTracker`；调用 `SaveChanges()` 时，它把当前值与快照对比，**只生成真正发生变化的列的 UPDATE 语句**。

每个被追踪实体都处于以下五个状态之一：

| 状态 | 含义 | `SaveChanges` 行为 |
|------|------|-------------------|
| `Unchanged` | 从数据库加载后无修改 | 跳过 |
| `Modified` | 加载后有属性变更 | 生成 UPDATE |
| `Added` | 新附加到上下文 | 生成 INSERT |
| `Deleted` | 标记为删除 | 生成 DELETE |
| `Detached` | 未被上下文追踪 | 不可见 |

一个最小示例：

```csharp
var movie = await context.Movies.FirstOrDefaultAsync(m => m.Id == id);
// 此时 EF Core 持有 movie 的原始快照，状态为 Unchanged

movie.Title = "New Title";
// 状态自动变为 Modified

await context.SaveChangesAsync();
// EF Core 比对快照，只生成针对 Title 列的 UPDATE
```

Change Tracker 还承担两项额外职责：**标识解析**（同一主键只返回一个对象实例）和**导航属性自动填充**（加载关联实体时自动连接引用）。关掉追踪，这两项也一并关掉。

## 追踪查询（默认行为）

默认情况下，所有返回实体类型的查询都是追踪查询：

```csharp
// 追踪查询（默认行为）
var movies = await context.Movies.ToListAsync();
// EF Core 现在追踪所有返回的 Movie 实体
// 任何修改都会被 SaveChanges() 检测到
```

追踪查询对 CRUD 操作至关重要。典型更新端点示例：

```csharp
app.MapPut("/api/movies/{id}", async (int id, UpdateMovieRequest req, MovieDbContext db, CancellationToken ct) =>
{
    var movie = await db.Movies.FirstOrDefaultAsync(m => m.Id == id, ct);
    // 追踪查询——EF Core 快照原始值
    if (movie is null) return Results.NotFound();

    movie.Title = req.Title;
    // 状态从 Unchanged 变为 Modified

    await db.SaveChangesAsync(ct);
    // EF Core 比对快照，生成精确的 UPDATE（只更新变化的列）
    return Results.NoContent();
});
```

### 标识解析与导航属性

同一上下文中多次查询同一主键时，追踪查询返回**同一对象引用**：

```csharp
var m1 = await context.Movies.FirstOrDefaultAsync(m => m.Id == 1);
var m2 = await context.Movies.FirstOrDefaultAsync(m => m.Id == 1);
ReferenceEquals(m1, m2); // true — 同一对象
```

EF Core 还会自动填充导航属性：加载 `Review` 时，若 `Movie` 已被追踪，`Review.Movie` 引用会自动指向对应实体。

## 非追踪查询（AsNoTracking）

非追踪查询完全绕过 Change Tracker——不创建快照、不做标识解析、不填充导航属性。实体以普通对象形式返回，快速、轻量、完全独立：

```csharp
// 非追踪查询
var movies = await context.Movies
    .AsNoTracking()
    .ToListAsync();
```

这是 **EF Core 只读查询中影响最大的单项性能优化**。在 Web API 场景中，它适用于绝大多数端点：

```csharp
// 只读列表端点——适合 AsNoTracking
app.MapGet("/api/movies", async (MovieDbContext db, CancellationToken ct) =>
{
    return await db.Movies
        .AsNoTracking()
        .OrderByDescending(m => m.ReleaseDate)
        .ToListAsync(ct);
});
```

### 非追踪时的标识解析问题

不使用追踪时，相同实体出现多次会生成多个独立对象。比如 50 部电影共享 5 位导演，带 `.Include(m => m.Director)` 的非追踪查询会产生 **50 个 Director 对象**（而非 5 个）：

```csharp
var m1 = await context.Movies.AsNoTracking().FirstOrDefaultAsync(m => m.Id == 1);
var m2 = await context.Movies.AsNoTracking().FirstOrDefaultAsync(m => m.Id == 1);
ReferenceEquals(m1, m2); // false — 不同对象
```

对于大多数 API 场景（直接序列化为 JSON），这不重要。但如果需要内存中的对象标识一致性，请注意这一点。

## AsNoTrackingWithIdentityResolution：中间选项

EF Core 提供了第三个选项——兼顾非追踪的性能与追踪的标识解析：

```csharp
var movies = await context.Movies
    .AsNoTrackingWithIdentityResolution()
    .Include(m => m.Director)
    .ToListAsync();
```

- 实体**不被追踪**——`SaveChanges()` 不会持久化修改
- 执行**标识解析**——50 部电影共享 5 位导演时，只生成 5 个 Director 实例
- 后台运行一个临时 ChangeTracker 用于查询期间的去重，查询完毕后被 GC 回收

**使用条件（需同时满足）：**
1. 只读数据（不修改）
2. 使用 `.Include()` 加载关联实体
3. 关联实体被多个父实体共享（如多部电影同一导演、多个用户同一角色）

> **注意**：`AsNoTrackingWithIdentityResolution()` 不支持 Include 路径中存在循环引用，否则会触发运行时错误。

## 投影（Select）自动跳过追踪

这一点经常被忽视：**当投影结果不是实体类型时，自动绕过追踪**：

```csharp
// 不被追踪——结果是匿名类型
var summaries = await context.Movies
    .Select(m => new { m.Id, m.Title, m.ReleaseDate })
    .ToListAsync();
```

> **最佳实践**：列表端点优先使用投影而非 `AsNoTracking()`——只获取需要的列，更少的数据传输，更少的内存分配，且没有追踪开销。

但如果投影包含实体实例本身，那些实体仍然会被追踪：

```csharp
// m (Movie) 被追踪；DirectorName (string) 不被追踪
var results = await context.Movies
    .Select(m => new { Movie = m, DirectorName = m.Director!.Name })
    .ToListAsync();
```

## BenchmarkDotNet 基准测试

用真实数据来验证。以下是三种追踪模式在不同数据集大小下的对比（PostgreSQL 17 + EF Core 10 + .NET 10）：

```csharp
[MemoryDiagnoser]
[SimpleJob(RuntimeMoniker.Net100)]
public class TrackingBenchmarks
{
    private MovieDbContext _context;

    [Params(100, 1000, 10000)]
    public int RowCount { get; set; }

    [GlobalSetup]
    public void GlobalSetup()
    {
        var options = new DbContextOptionsBuilder<MovieDbContext>()
            .UseNpgsql(connectionString)
            .Options;
        _context = new MovieDbContext(options);
        // 数据库已预置 RowCount 条 Movie + Director 数据
    }

    [Benchmark(Baseline = true)]
    public Task Tracking() =>
        _context.Movies.ToListAsync();

    [Benchmark]
    public Task NoTracking() =>
        _context.Movies.AsNoTracking().ToListAsync();

    [Benchmark]
    public Task NoTrackingWithIdentityResolution() =>
        _context.Movies.AsNoTrackingWithIdentityResolution().ToListAsync();
}
```

**测试结论：**

| 指标 | 结论 |
|------|------|
| 速度 | `AsNoTracking` 在大数据集下约比追踪查询快 **2 倍**（10K 行：31ms vs 68ms） |
| 内存 | 内存分配降低约 **50%**——快照存储是最大的开销 |
| 标识解析 | `AsNoTrackingWithIdentityResolution` 比普通 `AsNoTracking` 有额外开销，但仍快于全追踪 |
| 小数据集 | 100 行时差异很小（1.8ms vs 1.2ms）——不要过度优化 |

## 决策指南

| 场景 | 推荐模式 | 原因 |
|------|---------|------|
| GET 列表端点（分页/过滤） | `AsNoTracking()` | 只读，通常返回多行，性能收益最大 |
| GET 详情端点（纯展示） | `AsNoTracking()` | 只读，单实体，不需要修改 |
| GET 详情 → 然后更新（同请求） | 默认（追踪） | `SaveChanges()` 需要变更检测 |
| Include + 共享关联实体 | `AsNoTrackingWithIdentityResolution()` | 防止内存中出现重复关联对象 |
| Select 投影为 DTO/匿名类型 | 无需额外标注 | 匿名类型和 DTO 天然不被追踪 |
| 循环批量导入/大数据集处理 | `AsNoTracking()` + `ChangeTracker.Clear()` | 防止 Change Tracker 跨批次积累实体 |
| 后台作业读取大数据集 | `AsNoTracking()` | 降低长时间运行操作的内存压力 |

### 批量处理时使用 ChangeTracker.Clear()

在循环处理大数据集时，被追踪的实体会不断积累在 `ChangeTracker` 中，逐渐消耗更多内存，并拖慢每次 `SaveChanges()` 的速度：

```csharp
for (int page = 0; page < totalPages; page++)
{
    var movies = await context.Movies
        .Skip(page * 500)
        .Take(500)
        .ToListAsync();

    foreach (var movie in movies)
        RecalculateRating(movie);

    await context.SaveChangesAsync();

    // 清空 Change Tracker——释放所有已追踪实体
    context.ChangeTracker.Clear();
}
```

不调用 `ChangeTracker.Clear()` 的话，处理到第 10 批时，上下文已持有 5,000 个被追踪实体，每次后续 `SaveChanges()` 都要扫描它们。

## 全局设为非追踪默认值

如果你的大多数查询都是只读的（这对 Web API 来说很典型），可以在 `DbContext` 级别将默认追踪行为改为非追踪：

```csharp
// 注册时设置默认值
builder.Services.AddDbContext<MovieDbContext>(options =>
    options
        .UseNpgsql(connectionString)
        .UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking));
```

此后**所有查询默认非追踪**，需要追踪时显式使用 `AsTracking()`：

```csharp
// 默认非追踪，自动生效
var movies = await context.Movies.ToListAsync();

// 需要追踪时显式启用
var movie = await context.Movies.AsTracking().FirstOrDefaultAsync(m => m.Id == id);
movie.Title = "Updated";
await context.SaveChangesAsync();
```

> **推荐方案**：对大多数 Web API，将非追踪设为默认值是正确的选择。绝大多数端点是只读的，少数更新端点可以显式使用 `AsTracking()`。这样新端点默认快速，开发者必须有意识地为真正需要追踪的场景选择追踪。

## 常见陷阱

### 陷阱 1：用 AsNoTracking 后修改实体

```csharp
// BUG：这个更新会被静默忽略！
var movie = await context.Movies.AsNoTracking().FirstOrDefaultAsync(m => m.Id == id);
movie.Title = "Updated";
await context.SaveChangesAsync(); // 什么都不做——movie 未被追踪
```

**修复**：要么去掉 `AsNoTracking()`，要么显式附加实体：

```csharp
// 方案 1：使用追踪查询（推荐）
var movie = await context.Movies.FirstOrDefaultAsync(m => m.Id == id);

// 方案 2：附加游离实体并标记为已修改
context.Movies.Attach(movie);
context.Entry(movie).State = EntityState.Modified;
await context.SaveChangesAsync();
```

### 陷阱 2：全局设为非追踪后，更新端点忘记 AsTracking()

```csharp
// BUG：默认非追踪时，此更新静默失败！
var movie = await context.Movies.FirstOrDefaultAsync(m => m.Id == id);
movie.Title = "Updated";
await context.SaveChangesAsync(); // 静默失败——默认非追踪
```

**修复**：更新端点始终显式使用 `AsTracking()`：

```csharp
var movie = await context.Movies.AsTracking().FirstOrDefaultAsync(m => m.Id == id);
```

### 陷阱 3：DbContext 生命周期过长

如果 `DbContext` 的生命周期过长（如错误地注册为 Singleton），Change Tracker 会随时间积累实体，持续消耗内存。

**修复**：始终将 `DbContext` 注册为 **Scoped**（每次 HTTP 请求一个实例，这也是 `AddDbContext` 的默认行为）：

```csharp
// 正确——Scoped 生命周期（AddDbContext 的默认值）
builder.Services.AddDbContext<MovieDbContext>(options =>
    options.UseNpgsql(connectionString));
```

## 总结

| 特性 | 追踪查询 | AsNoTracking | AsNoTrackingWithIdentityResolution |
|------|---------|-------------|-----------------------------------|
| Change Tracker | ✅ 启用 | ❌ 跳过 | ❌ 跳过 |
| 快照存储 | ✅ 是 | ❌ 否 | ❌ 否 |
| 标识解析 | ✅ 是 | ❌ 否（重复对象） | ✅ 是 |
| 导航属性填充 | ✅ 自动 | ❌ 否 | ❌ 否 |
| 内存用量 | 高 | **~50% 更低** | 中等 |
| 查询速度（大数据集） | 基准 | **~2x 更快** | 比追踪快，比 AsNoTracking 慢 |
| 适用场景 | CRUD 操作 | 所有只读端点 | Include + 共享关联实体 |

**核心原则**：读多写少的 Web API，把非追踪设为默认值；真正需要写操作的端点，有意识地用 `AsTracking()` 选择追踪。这样性能默认最优，写操作也不会意外静默失败。

## 参考

- [原文：Tracking vs. No-Tracking Queries in EF Core 10](https://codewithmukesh.com/blog/tracking-vs-no-tracking-queries-efcore/)
- [Microsoft 官方 EF Core 变更追踪文档](https://learn.microsoft.com/en-us/ef/core/change-tracking/)
- [Microsoft EF Core 性能指南](https://learn.microsoft.com/en-us/ef/core/performance/)
