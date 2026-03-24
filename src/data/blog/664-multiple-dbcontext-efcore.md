---
pubDatetime: 2026-03-24T09:40:00+08:00
title: "EF Core 10 多 DbContext：多数据库、模式隔离与迁移管理"
description: "系统讲解 EF Core 10 中多 DbContext 的使用场景与实现——多数据库配置、同库 schema 隔离、读写分离、跨上下文事务、迁移独立管理，包含常见错误和决策矩阵。"
tags: ["dotnet", "EF Core", "ASP.NET Core", "Database"]
slug: "multiple-dbcontext-efcore"
ogImage: "../../assets/664/01-cover.png"
source: "https://codewithmukesh.com/blog/multiple-dbcontext-efcore/"
---

大多数 EF Core 教程只展示一个 DbContext、一个数据库、一套迁移。小项目够用。但当应用规模增长——出现独立的分析数据库、按模块划分的领域边界、供报表使用的读副本——就需要在同一个应用里使用多个 DbContext。

这时问题才真正开始有意思。EF Core 原生支持多 DbContext，但围绕依赖注入、迁移、事务、schema 隔离有几个容易踩的坑，不提前知道的话会浪费大量时间。本文通过一个具体的 ASP.NET Core Web API 示例，覆盖所有主要场景。

![多 DbContext 封面](../../assets/664/01-cover.png)

## 什么时候用多个 DbContext

多 DbContext 是指在同一应用中定义多个继承自 `DbContext` 的类，每个类对应一组实体、一个数据库，或一个领域边界。以下是真实世界里需要这样做的场景：

| 场景 | 描述 | 例子 |
|---|---|---|
| 多数据库 | 每个上下文连接不同数据库 | 业务 DB + 分析 DB |
| 限界上下文（DDD） | 同一数据库，不同 schema，不同实体集 | Catalog schema + Ordering schema |
| 模块化单体 | 每个模块拥有自己的上下文和 schema | 用户模块 + 计费模块 |
| 读副本 | 专用只读上下文指向读副本 | 报表查询 |
| 多租户 | 每个租户独立上下文/数据库 | SaaS 按租户隔离 |
| 混合存储 | 一个上下文用 PostgreSQL，另一个用 Cosmos | 关系型 + 文档存储 |

### 什么时候不该拆分

不要只因为应用有很多实体就创建多个 DbContext。一个包含 50 个实体的单一上下文完全没问题，EF Core 能很好地处理大型模型。只有在真正有架构原因时才拆分：独立数据库、模块隔离、或限界上下文边界。

判断标准：如果两组实体永远不需要跨表 join 且生命周期不同（分开部署、由不同团队维护、存储在不同数据库），它们属于不同的 DbContext。如果它们频繁 join 且共享事务，保留在同一个上下文里。

## 多 DbContext 配置步骤

用一个具体例子来说明：扩展 Movie API，增加一个独立的 Analytics 数据库，用于追踪 API 使用事件。Movie 数据库存储领域数据，Analytics 数据库存储事件日志。

### 第一步：定义实体

```csharp
// 原有的 Movie 实体
public class Movie
{
    public Guid Id { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Genre { get; set; } = string.Empty;
    public decimal Rating { get; set; }
    public int ReleaseYear { get; set; }
}

// 新增的分析事件实体
public class ApiEvent
{
    public Guid Id { get; set; }
    public string Endpoint { get; set; } = string.Empty;
    public string Method { get; set; } = string.Empty;
    public int StatusCode { get; set; }
    public long DurationMs { get; set; }
    public DateTime OccurredAt { get; set; } = DateTime.UtcNow;
}
```

### 第二步：创建独立的 DbContext 类

每个上下文管理自己的实体集与数据库连接。关键细节：构造函数必须用 `DbContextOptions<TContext>`（泛型版本），而不是非泛型的 `DbContextOptions`：

```csharp
public class MovieDbContext(DbContextOptions<MovieDbContext> options) : DbContext(options)
{
    public DbSet<Movie> Movies => Set<Movie>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Movie>(entity =>
        {
            entity.HasKey(m => m.Id);
            entity.Property(m => m.Title).HasMaxLength(300).IsRequired();
            entity.Property(m => m.Genre).HasMaxLength(100).IsRequired();
            entity.Property(m => m.Rating).HasColumnType("decimal(3,1)");
        });
    }
}

public class AnalyticsDbContext(DbContextOptions<AnalyticsDbContext> options) : DbContext(options)
{
    public DbSet<ApiEvent> ApiEvents => Set<ApiEvent>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<ApiEvent>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Endpoint).HasMaxLength(500).IsRequired();
            entity.Property(e => e.Method).HasMaxLength(10).IsRequired();
        });
    }
}
```

为什么必须用泛型版本：注册多个 DbContext 时，EF Core 需要知道哪份 `DbContextOptions` 属于哪个上下文。如果用非泛型的 `DbContextOptions`，两个上下文会收到同一份选项——同一个连接字符串，这意味着其中一个静默地连到了错误的数据库。泛型版本 `DbContextOptions<MovieDbContext>` 确保每个上下文获得自己的配置。

### 第三步：在 DI 中注册

每个上下文用独立的 `AddDbContext` 调用，各自配置连接字符串：

```csharp
builder.Services.AddDbContext<MovieDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("MovieDb")));

builder.Services.AddDbContext<AnalyticsDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("AnalyticsDb")));
```

`appsettings.json` 里配置两个连接字符串（注意端口不同，分别对应两个 PostgreSQL 实例）：

```json
{
  "ConnectionStrings": {
    "MovieDb": "Host=localhost;Port=5432;Database=movies;Username=postgres;Password=postgres",
    "AnalyticsDb": "Host=localhost;Port=5433;Database=analytics;Username=postgres;Password=postgres"
  }
}
```

### 第四步：在端点中注入使用

每个端点只注入它需要的上下文：

```csharp
// Movie 端点 - 只用 MovieDbContext
app.MapGet("/api/movies", async (MovieDbContext db, CancellationToken ct) =>
{
    var movies = await db.Movies.AsNoTracking().ToListAsync(ct);
    return Results.Ok(movies);
});

// Analytics 端点 - 只用 AnalyticsDbContext
app.MapGet("/api/analytics/events", async (AnalyticsDbContext analytics, CancellationToken ct) =>
{
    var events = await analytics.ApiEvents
        .AsNoTracking()
        .OrderByDescending(e => e.OccurredAt)
        .Take(100)
        .ToListAsync(ct);
    return Results.Ok(events);
});

// 同时使用两个上下文的端点
app.MapGet("/api/movies/{id:guid}", async (Guid id,
    MovieDbContext db, AnalyticsDbContext analytics, CancellationToken ct) =>
{
    var movie = await db.Movies.FindAsync([id], ct);
    if (movie is null) return Results.NotFound();

    analytics.ApiEvents.Add(new ApiEvent
    {
        Id = Guid.CreateVersion7(),
        Endpoint = $"/api/movies/{id}",
        Method = "GET",
        StatusCode = 200,
        DurationMs = 0
    });
    await analytics.SaveChangesAsync(ct);

    return Results.Ok(movie);
});
```

每个上下文是独立的——自己的连接、自己的变更跟踪器、自己的 `SaveChanges()` 作用域。

## 迁移管理

多个 DbContext 时，`dotnet ef` CLI 不知道该用哪个，不指定上下文会报：

```
More than one DbContext was found. Specify which one to use.
```

### 迁移命令

始终通过 `--context` 指定上下文，用 `--output-dir` 分开存放迁移文件：

```bash
dotnet ef migrations add InitialMovies --context MovieDbContext --output-dir Migrations/MovieDb
dotnet ef migrations add InitialAnalytics --context AnalyticsDbContext --output-dir Migrations/AnalyticsDb

dotnet ef database update --context MovieDbContext
dotnet ef database update --context AnalyticsDbContext
```

### 迁移历史表冲突

EF Core 默认把迁移历史存在 `__EFMigrationsHistory` 表里。当两个上下文目标是同一个数据库时（比如只是不同 schema），会在这张表上冲突。解决方案是配置独立的历史表：

```csharp
builder.Services.AddDbContext<MovieDbContext>(options =>
    options.UseNpgsql(connectionString, npgsql =>
        npgsql.MigrationsHistoryTable("__MovieMigrations", "movies")));

builder.Services.AddDbContext<AnalyticsDbContext>(options =>
    options.UseNpgsql(connectionString, npgsql =>
        npgsql.MigrationsHistoryTable("__AnalyticsMigrations", "analytics")));
```

### 推荐的项目结构

```
MultiDbDemo.Api/
├── Data/
│   ├── MovieDbContext.cs
│   └── AnalyticsDbContext.cs
├── Migrations/
│   ├── MovieDb/
│   │   ├── 20260212_InitialMovies.cs
│   │   └── MovieDbContextModelSnapshot.cs
│   └── AnalyticsDb/
│       ├── 20260212_InitialAnalytics.cs
│       └── AnalyticsDbContextModelSnapshot.cs
```

CI/CD 建议：在部署流水线里分别对每个上下文执行迁移。一个失败时，另一个数据库不受影响——这是独立上下文带来的可独立部署性的体现。

## Schema 隔离：同一数据库，不同 Schema

有时不需要独立数据库，只需要在同一数据库内做逻辑隔离。模块化单体架构里很常见，每个模块在自己的 schema 下维护一组表：

```csharp
public class CatalogDbContext(DbContextOptions<CatalogDbContext> options) : DbContext(options)
{
    public DbSet<Movie> Movies => Set<Movie>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasDefaultSchema("catalog");

        modelBuilder.Entity<Movie>(entity =>
        {
            entity.HasKey(m => m.Id);
            entity.Property(m => m.Title).HasMaxLength(300).IsRequired();
        });
    }
}

public class OrderingDbContext(DbContextOptions<OrderingDbContext> options) : DbContext(options)
{
    public DbSet<Rental> Rentals => Set<Rental>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasDefaultSchema("ordering");

        modelBuilder.Entity<Rental>(entity =>
        {
            entity.HasKey(r => r.Id);
            entity.Property(r => r.MovieTitle).HasMaxLength(300).IsRequired();
        });
    }
}
```

两个上下文连接同一个数据库，但操作不同的 schema（`catalog.Movies` vs `ordering.Rentals`）。这样做的收益：

- **逻辑隔离**：每个模块只能看到自己的表
- **独立迁移**：给 Catalog 加列不会碰 Ordering 的迁移
- **基础设施简单**：单一数据库，没有跨库复杂度

同样要记得配置独立的迁移历史表，否则共享同一个数据库的多个上下文会在 `__EFMigrationsHistory` 上冲突。

## 读副本模式

多 DbContext 的一个实用场景是在数据库级别分离读写操作。创建一个指向主库的写上下文和一个指向读副本并默认开启 `NoTracking` 的读上下文：

```csharp
// 写上下文 - 主库
public class MovieDbContext(DbContextOptions<MovieDbContext> options) : DbContext(options)
{
    public DbSet<Movie> Movies => Set<Movie>();
}

// 只读上下文 - 读副本
public class MovieReadDbContext(DbContextOptions<MovieReadDbContext> options) : DbContext(options)
{
    public DbSet<Movie> Movies => Set<Movie>();
}
```

注册时配置不同的连接字符串，并为读上下文开启全局 NoTracking：

```csharp
builder.Services.AddDbContext<MovieDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("MovieDb")));

builder.Services.AddDbContext<MovieReadDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("MovieDbReplica"))
           .UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking));
```

写操作端点注入 `MovieDbContext`，读操作端点注入 `MovieReadDbContext`。读副本承担所有查询压力，主库只处理写入——这是读密集型 API 的重要横向扩展手段。

**注意**：只对写上下文（主库）执行迁移。读副本通过数据库复制机制接收 schema 变更，不需要也不应该跑 EF Core 迁移。

## 跨上下文事务

一个常见问题：能否把两个不同 DbContext 的操作包在一个事务里？可以——但只有当它们连接的是同一个数据库且使用同一个数据库连接时才行：

```csharp
app.MapPost("/api/movies", async (CreateMovieRequest request,
    MovieDbContext movieDb, AnalyticsDbContext analyticsDb, CancellationToken ct) =>
{
    var connection = movieDb.Database.GetDbConnection();
    await connection.OpenAsync(ct);

    await using var transaction = await connection.BeginTransactionAsync(ct);

    try
    {
        // 共享连接和事务给第二个上下文
        analyticsDb.Database.SetDbConnection(connection);
        await analyticsDb.Database.UseTransactionAsync(transaction, ct);

        var movie = new Movie
        {
            Id = Guid.CreateVersion7(),
            Title = request.Title,
            Genre = request.Genre,
            Rating = request.Rating,
            ReleaseYear = request.ReleaseYear
        };
        movieDb.Movies.Add(movie);
        await movieDb.SaveChangesAsync(ct);

        analyticsDb.ApiEvents.Add(new ApiEvent
        {
            Id = Guid.CreateVersion7(),
            Endpoint = "/api/movies",
            Method = "POST",
            StatusCode = 201,
            DurationMs = 0
        });
        await analyticsDb.SaveChangesAsync(ct);

        await transaction.CommitAsync(ct);
        return Results.Created($"/api/movies/{movie.Id}", movie);
    }
    catch
    {
        await transaction.RollbackAsync(ct);
        throw;
    }
});
```

几个约束要清楚：

- **两个上下文必须指向同一个数据库**。跨数据库分布式事务大多数云数据库不支持
- 必须显式共享 `DbConnection` 和 `DbTransaction`
- 如果是不同数据库，需要用最终一致性模式——Outbox Pattern 或消息队列

## DbContext 池化

高吞吐量 API 可以用 `AddDbContextPool` 代替 `AddDbContext`，它复用 DbContext 实例而不是每个请求新建，降低分配开销：

```csharp
builder.Services.AddDbContextPool<MovieDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("MovieDb")));

builder.Services.AddDbContextPool<AnalyticsDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("AnalyticsDb")));
```

每种上下文类型有自己的池，默认池大小是 1024 个实例。实例归还时会被重置（清空变更跟踪器，保留配置）。

注意：开启池化时不要在 DbContext 的字段里存储请求级别的状态，同一个实例会跨请求复用。如果上下文构造函数或字段有自定义状态，用 `AddDbContext` 而不是 `AddDbContextPool`。

## 常见错误

### 错误一：使用非泛型 DbContextOptions

```csharp
// 错误：两个上下文收到同一份选项
public class MovieDbContext(DbContextOptions options) : DbContext(options) { }
public class AnalyticsDbContext(DbContextOptions options) : DbContext(options) { }
```

DI 无法区分两者。两个上下文都会收到最后注册的那份 `DbContextOptions`，其中一个静默地连到了错误的数据库。

修复：始终用泛型版本：

```csharp
// 正确：每个上下文获得自己的类型化选项
public class MovieDbContext(DbContextOptions<MovieDbContext> options) : DbContext(options) { }
public class AnalyticsDbContext(DbContextOptions<AnalyticsDbContext> options) : DbContext(options) { }
```

### 错误二：迁移命令忘记指定 --context

```bash
# 报错：More than one DbContext was found
dotnet ef migrations add Initial

# 正确做法
dotnet ef migrations add Initial --context MovieDbContext --output-dir Migrations/MovieDb
```

### 错误三：同库两个上下文共用迁移历史表

当两个上下文目标同一个数据库但没有配置独立的历史表时，迁移会发生冲突。参考"迁移历史表"章节配置 `MigrationsHistoryTable`。

### 错误四：尝试跨上下文 Join

```csharp
// 不会编译——不同 DbContext 类型
var query = from m in movieDb.Movies
            join e in analyticsDb.ApiEvents on m.Id equals e.MovieId
            select new { m.Title, e.StatusCode };
```

EF Core 无法跨上下文 join。解决方案是分别查询再在内存里合并：

```csharp
var movies = await movieDb.Movies.AsNoTracking().ToListAsync(ct);
var events = await analyticsDb.ApiEvents.AsNoTracking().ToListAsync(ct);

var combined = from m in movies
               join e in events on m.Title equals e.Endpoint
               select new { m.Title, e.StatusCode };
```

数据量大时这明显低效。如果频繁需要跨实体查询，这些实体可能本来就应该在同一个上下文里。

## 分不分的决策矩阵

| 问题 | 建议拆分 | 建议合并 |
|---|---|---|
| 实体属于不同数据库？ | 必须拆——EF Core 要求 | 保持单一 |
| 实体由不同团队/模块维护？ | 拆——独立可部署 | 可能保持单一 |
| 需要读副本？ | 拆——读写分离上下文 | 保持单一 |
| 实体之间频繁 join？ | 保持单一——跨上下文 join 不可行 | 考虑拆分 |
| DbContext 有 100+ 实体，启动慢？ | 拆——减少模型编译时间 | 保持单一 |
| 模块化单体有限界上下文？ | 拆——每个模块一个上下文 | 保持单一 |

## 常见报错排查

**"More than one DbContext was found. Specify which one to use."**  
迁移命令缺少 `--context` 参数。始终指定：`dotnet ef migrations add Name --context YourDbContext`。

**"Unable to resolve service for type DbContextOptions while attempting to activate YourDbContext."**  
DbContext 构造函数用的是非泛型 `DbContextOptions`，改成 `DbContextOptions<YourDbContext>`。

**"The migration history table conflicts."**  
两个上下文目标同一个数据库但没有配置独立的历史表。在每个上下文的 `UseNpgsql`（或 `UseSqlServer`）调用里配置 `MigrationsHistoryTable`。

**"SaveChanges on one context rolls back when the other fails."**  
没有共享事务时，每个上下文的 `SaveChanges` 是独立的。如果需要原子性，必须共享 `DbConnection` 并使用 `UseTransactionAsync`；否则实现补偿逻辑或 Outbox Pattern。

**"My read replica context is running migrations and failing."**  
只对写上下文（主库）执行迁移。读副本通过数据库复制接收 schema 变更，把读上下文从迁移脚本里移除。

## 参考

- [Multiple DbContext in EF Core 10 - Scenarios, Setup & Migrations](https://codewithmukesh.com/blog/multiple-dbcontext-efcore/) - 原文
- [EF Core DbContext Configuration 官方文档](https://learn.microsoft.com/en-us/ef/core/dbcontext-configuration/)
- [EF Core migrations with multiple providers](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/providers)
- [EF Core advanced performance topics](https://learn.microsoft.com/en-us/ef/core/performance/advanced-performance-topics)
