---
pubDatetime: 2026-03-24T09:20:00+08:00
title: "EF Core 10 数据初始化：HasData、UseSeeding 和 Program.cs 三种方式详解"
description: "系统介绍 EF Core 10 三种数据初始化策略——HasData、UseSeeding/UseAsyncSeeding 和自定义 Program.cs，覆盖选型决策矩阵、关联实体种入、环境差异化和常见问题排查，帮你从第一天起就选对方案。"
tags: ["dotnet", "EF Core", "ASP.NET Core", "Database"]
slug: "seeding-initial-data-efcore"
ogImage: "../../assets/663/01-cover.png"
source: "https://codewithmukesh.com/blog/seeding-initial-data-efcore/"
---

你把 API 部署到 staging，测试人员刚一登录就崩了——roles 表是空的，没有默认分类，没有 lookup 数据，没有管理员账号。数据库 schema 是对的，但里面什么都没有。

这是 .NET 项目里最常见的疏漏之一。你花时间把实体、配置和迁移做得很好，却忘了空数据库就是坏数据库。本文以 EF Core 10 为背景，走完三种初始化策略的完整实现过程，给出选型决策矩阵，重点讲清楚每种方法的坑点和适用边界。

![EF Core 数据初始化封面](../../assets/663/01-cover.png)

## 什么是数据初始化

数据初始化（Data Seeding）是在数据库首次创建或迁移执行时，预先填入一批必要数据的过程。应用通常依赖这些数据才能正常运行：角色定义、状态码、默认分类、测试记录等。

EF Core 10 提供三条主要路径：

- `HasData`：基于迁移的初始化，数据随 schema 历史一起被追踪
- `UseSeeding` / `UseAsyncSeeding`：运行时初始化，EF Core 9 引入，在 `EnsureCreated` 或 `Migrate` 时执行
- 自定义 `Program.cs`：在应用启动时手动执行，可完整访问 DI 容器

## 三种方式快速对比

| 方式       | 执行时机                 | 自动幂等   | DDD 支持       | 环境差异化        | 适合场景                |
| ---------- | ------------------------ | ---------- | -------------- | ----------------- | ----------------------- |
| HasData    | 迁移应用时               | 是         | 差（匿名对象） | 无                | 角色、状态码、枚举表    |
| UseSeeding | EnsureCreated/Migrate 时 | 否，需手动 | 好             | 有限              | 开发/测试数据、默认配置 |
| Program.cs | 应用启动时               | 否，需手动 | 好             | 完整（DI + 环境） | 需要 DI 服务的复杂场景  |

## 方式一：HasData — 基于迁移的初始化

### 基本用法

把 `HasData` 写在 `IEntityTypeConfiguration` 配置类里：

```csharp
public class MovieConfiguration : IEntityTypeConfiguration<Movie>
{
    public void Configure(EntityTypeBuilder<Movie> builder)
    {
        builder.ToTable("Movies");
        builder.HasKey(m => m.Id);
        builder.Property(m => m.Title).IsRequired().HasMaxLength(200);
        // ...其他属性配置

        // 种入默认电影
        builder.HasData(
            new
            {
                Id = Guid.Parse("d1a7b9c3-4e56-4f89-a123-b456c789d012"),
                Title = "The Shawshank Redemption",
                Genre = "Drama",
                ReleaseDate = new DateTimeOffset(new DateTime(1994, 9, 23), TimeSpan.Zero),
                Rating = 9.3,
                Created = new DateTimeOffset(new DateTime(2026, 1, 1), TimeSpan.Zero),
                LastModified = new DateTimeOffset(new DateTime(2026, 1, 1), TimeSpan.Zero)
            },
            new
            {
                Id = Guid.Parse("e2b8c0d4-5f67-4890-b234-c567d890e123"),
                Title = "The Dark Knight",
                Genre = "Action",
                ReleaseDate = new DateTimeOffset(new DateTime(2008, 7, 18), TimeSpan.Zero),
                Rating = 9.0,
                Created = new DateTimeOffset(new DateTime(2026, 1, 1), TimeSpan.Zero),
                LastModified = new DateTimeOffset(new DateTime(2026, 1, 1), TimeSpan.Zero)
            }
        );
    }
}
```

注意这里必须用匿名对象，而不是 `Movie.Create()`。`Movie` 实体有私有构造函数和私有 setter，`HasData` 无法调用工厂方法，只能靠属性名匹配来映射。所有映射到列的属性——包括基类里的 `Id`、`Created`、`LastModified`——都要写进去。

### 主键必须是固定值

这是 `HasData` 最常被忽视的一点：主键不能用 `Guid.NewGuid()`。如果主键是动态生成的，每次创建迁移时 EF Core 会认为这是"新数据"，生成 `DELETE + INSERT` 而不是 `UPDATE`。固定的 GUID 告诉 EF Core"这是同一条记录"，跨迁移保持一致。

### 生成迁移和应用

```bash
dotnet ef migrations add SeedDefaultMovies
dotnet ef database update
```

EF Core 会在迁移文件里生成 `INSERT` 语句，数据成为 schema 历史的一部分。之后修改了种入数据（比如把评分从 9.3 改成 9.4），下一次迁移会生成 `UPDATE` 语句——这是有意为之的设计，但要小心：如果用户已经通过 API 修改过这条记录，迁移会把他的变更覆盖掉。

### HasData 的限制

- 不支持导航属性，外键值必须手写
- 不能调用工厂方法，只能用匿名对象
- 无法按环境条件化——所有环境都用同一份数据
- 每次改动都会产生新的迁移文件
- 不允许动态值（`Guid.NewGuid()`、`DateTime.UtcNow` 必须硬编码）

`HasData` 的适用场景是那些"本质上属于 schema 的数据"：角色定义、状态枚举表、国家代码、权限类型。这类数据每个环境都需要，几乎不会变。

## 方式二：UseSeeding 和 UseAsyncSeeding — 运行时初始化

EF Core 9 引入了 `UseSeeding` 和 `UseAsyncSeeding` 回调，每次调用 `EnsureCreated`、`EnsureCreatedAsync`、`Migrate` 或 `MigrateAsync` 时都会执行。不像 `HasData`，这里可以直接调用实体工厂方法。

### 在 DbContext 里实现

```csharp
public class MovieDbContext(DbContextOptions<MovieDbContext> options) : DbContext(options)
{
    public DbSet<Movie> Movies => Set<Movie>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasDefaultSchema("app");
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(MovieDbContext).Assembly);
        base.OnModelCreating(modelBuilder);
    }

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        optionsBuilder
            .UseAsyncSeeding(async (context, _, cancellationToken) =>
            {
                if (!await context.Set<Movie>().AnyAsync(cancellationToken))
                {
                    var movies = new[]
                    {
                        Movie.Create("The Shawshank Redemption", "Drama",
                            new DateTimeOffset(new DateTime(1994, 9, 23), TimeSpan.Zero), 9.3),
                        Movie.Create("The Dark Knight", "Action",
                            new DateTimeOffset(new DateTime(2008, 7, 18), TimeSpan.Zero), 9.0),
                        Movie.Create("Inception", "Sci-Fi",
                            new DateTimeOffset(new DateTime(2010, 7, 16), TimeSpan.Zero), 8.8)
                    };

                    await context.Set<Movie>().AddRangeAsync(movies, cancellationToken);
                    await context.SaveChangesAsync(cancellationToken);
                }
            })
            .UseSeeding((context, _) =>
            {
                if (!context.Set<Movie>().Any())
                {
                    var movies = new[]
                    {
                        Movie.Create("The Shawshank Redemption", "Drama",
                            new DateTimeOffset(new DateTime(1994, 9, 23), TimeSpan.Zero), 9.3),
                        Movie.Create("The Dark Knight", "Action",
                            new DateTimeOffset(new DateTime(2008, 7, 18), TimeSpan.Zero), 9.0)
                    };

                    context.Set<Movie>().AddRange(movies);
                    context.SaveChanges();
                }
            });
    }
}
```

这里直接调用 `Movie.Create()`——工厂方法会验证输入、设置时间戳、返回正确初始化的实体。不需要匿名对象，不需要硬编码 GUID，领域规则同样生效。

### 幂等性是必须的

与 `HasData` 不同，`UseSeeding` 回调在每次 `EnsureCreated` 或 `Migrate` 被调用时都会执行。如果你不检查数据是否已存在，每次应用重启都会插入重复记录，甚至主键冲突导致启动失败。

最简单的检查方式：

```csharp
if (!await context.Set<Movie>().AnyAsync(cancellationToken))
```

如果需要更细粒度的控制——比如逐条检查某条记录是否存在：

```csharp
var exists = await context.Set<Movie>()
    .AnyAsync(m => m.Title == "The Shawshank Redemption", cancellationToken);
if (!exists)
{
    context.Set<Movie>().Add(
        Movie.Create("The Shawshank Redemption", "Drama",
            new DateTimeOffset(new DateTime(1994, 9, 23), TimeSpan.Zero), 9.3));
    await context.SaveChangesAsync(cancellationToken);
}
```

### 为什么要同时实现两个回调

`UseAsyncSeeding` 在异步方法（如 `EnsureCreatedAsync`、`MigrateAsync`）中执行；`UseSeeding` 是同步方法的回调。在 ASP.NET Core 里几乎总是用异步，但 EF Core 要求同步版本作为兜底。如果只实现了 `UseAsyncSeeding`，而某条代码路径调用了 `EnsureCreated`（同步），就不会有任何数据被种入——且是静默失败，没有任何报错。

## 方式三：自定义 Program.cs 初始化

在 `UseSeeding` 存在之前（EF Core 8 及更早），标准做法是在 `Program.cs` 里创建 service scope 然后手动种入数据。这种方式依然有效，尤其是当种入逻辑需要访问 DI 容器中的服务时。

```csharp
var app = builder.Build();

await using (var scope = app.Services.CreateAsyncScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<MovieDbContext>();
    var logger = scope.ServiceProvider.GetRequiredService<ILogger<Program>>();

    await dbContext.Database.MigrateAsync();

    if (!await dbContext.Movies.AnyAsync())
    {
        logger.LogInformation("Seeding default movie data...");

        var movies = new[]
        {
            Movie.Create("The Shawshank Redemption", "Drama",
                new DateTimeOffset(new DateTime(1994, 9, 23), TimeSpan.Zero), 9.3),
            Movie.Create("The Dark Knight", "Action",
                new DateTimeOffset(new DateTime(2008, 7, 18), TimeSpan.Zero), 9.0),
            Movie.Create("Inception", "Sci-Fi",
                new DateTimeOffset(new DateTime(2010, 7, 16), TimeSpan.Zero), 8.8)
        };

        await dbContext.Movies.AddRangeAsync(movies);
        await dbContext.SaveChangesAsync();
        logger.LogInformation("Seeded {Count} default movies", movies.Length);
    }
}
```

适合用这种方式的场景：

- 种入逻辑需要 `ILogger`、`IConfiguration` 或其他自定义服务
- 需要跨多个 DbContext 种入数据
- 种入逻辑复杂到值得抽成独立的 service 类
- 使用 EF Core 8 或更早版本没有 `UseSeeding` 的情况

## 关联实体的种入

### HasData：用外键值，不用导航属性

`HasData` 不支持导航属性，必须直接写外键值：

```csharp
// GenreConfiguration 种入父实体
builder.HasData(
    new
    {
        Id = Guid.Parse("a1b2c3d4-0000-0000-0000-000000000001"),
        Name = "Drama",
        Created = new DateTimeOffset(new DateTime(2026, 1, 1), TimeSpan.Zero),
        LastModified = new DateTimeOffset(new DateTime(2026, 1, 1), TimeSpan.Zero)
    }
);

// MovieConfiguration 用 GenreId 外键引用
builder.HasData(
    new
    {
        Id = Guid.Parse("d1a7b9c3-4e56-4f89-a123-b456c789d012"),
        Title = "The Shawshank Redemption",
        GenreId = Guid.Parse("a1b2c3d4-0000-0000-0000-000000000001"), // 外键指向 Drama
        ReleaseDate = new DateTimeOffset(new DateTime(1994, 9, 23), TimeSpan.Zero),
        Rating = 9.3,
        Created = new DateTimeOffset(new DateTime(2026, 1, 1), TimeSpan.Zero),
        LastModified = new DateTimeOffset(new DateTime(2026, 1, 1), TimeSpan.Zero)
    }
);
```

EF Core 会在迁移中自动处理插入顺序，但两端数据都必须在 `HasData` 里定义，否则迁移会因外键约束失败。

### UseSeeding：父实体先 SaveChanges

使用 `UseSeeding` 时，必须先保存父实体，再保存子实体：

```csharp
.UseAsyncSeeding(async (context, _, cancellationToken) =>
{
    // 1. 先种入类型数据（父实体）
    if (!await context.Set<Genre>().AnyAsync(cancellationToken))
    {
        var genres = new[]
        {
            Genre.Create("Drama"),
            Genre.Create("Action"),
            Genre.Create("Sci-Fi")
        };
        await context.Set<Genre>().AddRangeAsync(genres, cancellationToken);
        await context.SaveChangesAsync(cancellationToken); // 先提交
    }

    // 2. 再种入电影数据（子实体）
    if (!await context.Set<Movie>().AnyAsync(cancellationToken))
    {
        var drama = await context.Set<Genre>()
            .FirstAsync(g => g.Name == "Drama", cancellationToken);

        var movie = Movie.Create("The Shawshank Redemption", drama.Id,
            new DateTimeOffset(new DateTime(1994, 9, 23), TimeSpan.Zero), 9.3);

        await context.Set<Movie>().AddAsync(movie, cancellationToken);
        await context.SaveChangesAsync(cancellationToken);
    }
})
```

注意两个独立的 `SaveChangesAsync` 调用——第一次提交让数据库里有了 Genre，第二次才能引用它的 Id。合并成一次 `SaveChanges` 会导致外键约束错误。

## 按环境差异化种入

`UseSeeding` 相比 `HasData` 的一个重要优势是可以感知运行环境。开发环境需要大量测试记录方便验证分页和过滤，生产环境只需要必要的参考数据。自定义 `Program.cs` 方式可以访问 `IHostEnvironment`：

```csharp
await using (var scope = app.Services.CreateAsyncScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<MovieDbContext>();
    var environment = scope.ServiceProvider.GetRequiredService<IHostEnvironment>();

    await dbContext.Database.MigrateAsync();

    if (!await dbContext.Movies.AnyAsync())
    {
        // 任何环境都种入核心参考数据
        var essentialMovies = new[]
        {
            Movie.Create("The Shawshank Redemption", "Drama",
                new DateTimeOffset(new DateTime(1994, 9, 23), TimeSpan.Zero), 9.3),
            Movie.Create("The Dark Knight", "Action",
                new DateTimeOffset(new DateTime(2008, 7, 18), TimeSpan.Zero), 9.0)
        };
        await dbContext.Movies.AddRangeAsync(essentialMovies);

        // 开发环境额外种入 50 条测试数据
        if (environment.IsDevelopment())
        {
            var testMovies = Enumerable.Range(1, 50)
                .Select(i => Movie.Create(
                    $"Test Movie {i}",
                    i % 3 == 0 ? "Drama" : i % 3 == 1 ? "Action" : "Sci-Fi",
                    new DateTimeOffset(new DateTime(2020, 1, i % 28 + 1), TimeSpan.Zero),
                    Math.Round(i % 10 * 1.0, 1)))
                .ToArray();
            await dbContext.Movies.AddRangeAsync(testMovies);
        }

        await dbContext.SaveChangesAsync();
    }
}
```

一个不该有的坏习惯：在生产环境里硬编码管理员密码。初始凭据应该来自环境变量或密钥管理服务，绝对不要写在代码里。

## 常见问题排查

### HasData 产生空迁移

执行 `dotnet ef migrations add` 后生成的迁移里什么都没有。

原因通常是 `HasData` 所在的配置类没有被 `ApplyConfigurationsFromAssembly` 发现。确认 `OnModelCreating` 里有这一行：

```csharp
modelBuilder.ApplyConfigurationsFromAssembly(typeof(MovieDbContext).Assembly);
```

同时检查配置类是否为 `public`——`internal` 类不会被程序集扫描发现。

### UseSeeding 反复产生重复记录

每次应用重启都出现重复数据，说明幂等检查缺失或不正确。确保种入前检查数据是否存在：

```csharp
if (!await context.Set<Movie>().AnyAsync(cancellationToken))
```

如果按记录检查，用唯一业务属性（如 `Title`），不要用 `Id`——因为 `Guid.NewGuid()` 每次不一样。

### HasData 和私有构造函数冲突

用实体实例调用 `HasData` 时，EF Core 抛出"cannot be added"错误。解决方法是改用匿名对象：

```csharp
// 不能这样用（私有构造函数）
builder.HasData(Movie.Create("Title", "Genre", date, 9.0));

// 应该这样用（匿名对象，所有属性都要写）
builder.HasData(new
{
    Id = Guid.Parse("..."),
    Title = "...",
    Genre = "...",
    ReleaseDate = date,
    Rating = 9.0,
    Created = timestamp,
    LastModified = timestamp
});
```

### UseSeeding 不执行

实现了 `UseAsyncSeeding` 但数据库里没有数据。检查两点：一是启动时是否调用了 `EnsureCreatedAsync()` 或 `MigrateAsync()`，回调只在这两个方法里触发；二是是否同时实现了同步版本 `UseSeeding`，如果某条代码路径调用了同步的 `EnsureCreated`，异步回调不会被执行。

### HasData 种入外键约束失败

迁移因外键约束错误而失败。确认被引用的父实体的种入数据也已定义——如果 `GenreConfiguration.HasData()` 里没有 Id 为 X 的数据，就不能在 `MovieConfiguration.HasData()` 里用 `GenreId = X`。两端都必须有定义，EF Core 会自动处理生成迁移里的插入顺序。

## 选哪种方式

原作者的推荐逻辑很清晰：

**用 `HasData`**：数据本质上属于 schema 的一部分——角色定义、状态枚举表、国家代码、权限类型。这类数据每个环境都要有，几乎不会变，迁移历史里有清晰的审计记录。

**用 `UseSeeding`/`UseAsyncSeeding`**：应用层级的种入数据——默认分类、开发环境的示例记录、初始配置值。这是 EF Core 10 大多数场景的首选，可以调用工厂方法，不会让迁移文件膨胀，环境感知能力有限但够用。

**用自定义 `Program.cs`**：需要 DI 服务时——外部 API 拉取参考数据、日志、跨多个 DbContext 种入、复杂业务逻辑。

最常见的错误是把 `HasData` 用在所有场景，结果迁移文件里堆满了数据更新，匿名对象维护起来很痛苦，也没有办法按环境种不同的数据。

## 参考

- [Seeding Initial Data in EF Core 10 - HasData vs UseSeeding](https://codewithmukesh.com/blog/seeding-initial-data-efcore/) - 原文
- [EF Core Data Seeding 官方文档](https://learn.microsoft.com/en-us/ef/core/modeling/data-seeding)
- [UseSeeding EF Core 9 新特性](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-9.0/whatsnew#use-seeding-methods)
