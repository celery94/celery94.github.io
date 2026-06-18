---
pubDatetime: 2026-06-18T08:10:00+08:00
title: "Entity Framework Core 完全指南：.NET 10 数据访问"
description: "一份 EF Core 全景图：DbContext 的设计角色、Change Tracking 的原理与陷阱、LINQ 到 SQL 的翻译、迁移管理、EF6 差异对比，以及什么时候该用 EF Core、什么时候该切到 Dapper 或原生 SQL。"
tags: ["C#", ".NET", "EF Core", "ORM", "数据库", "LINQ"]
slug: "entity-framework-core-dotnet-complete-guide"
source: "https://www.devleader.ca/2026/06/17/entity-framework-core-in-net-the-complete-guide"
ogImage: "../../assets/888/01-cover.png"
---

## EF Core 是什么

Entity Framework Core 是微软官方的跨平台开源 ORM。它让你用 C# 类和 LINQ 查询来操作关系数据库，而不是手写 SQL 字符串。EF Core 负责把 C# 代码翻译成目标数据库的正确 SQL 方言。

支持的数据库通过对应的 provider 包接入：

- **SQL Server** — `Microsoft.EntityFrameworkCore.SqlServer`
- **SQLite** — `Microsoft.EntityFrameworkCore.Sqlite`
- **PostgreSQL** — `Npgsql.EntityFrameworkCore.PostgreSQL`
- **MySQL / MariaDB** — `Pomelo.EntityFrameworkCore.MySql`
- **内存数据库** — `Microsoft.EntityFrameworkCore.InMemory`（测试利器）

![EF Core Complete Guide](../../assets/888/02-efcore-header.png)

## 必须搞懂的三个核心概念

### DbContext — EF Core 的心脏

`DbContext` 承担两个角色：

- **工作单元（Unit of Work）** — 追踪一次请求或操作期间对所有实体的变更，调用 `SaveChangesAsync()` 时一次性提交到数据库
- **连接管理器** — 管理数据库连接的生命周期，包括打开、复用和关闭

每次与数据库的交互都通过一个 `DbContext` 实例。你从 `DbContext` 派生出自定义 context 类，通过 `DbSet<T>` 属性暴露数据库表：

```csharp
public class BloggingContext : DbContext
{
    public BloggingContext(DbContextOptions<BloggingContext> options)
        : base(options) { }

    public DbSet<Blog> Blogs { get; set; }
    public DbSet<Post> Posts { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Blog>(entity =>
        {
            entity.HasKey(b => b.BlogId);
            entity.Property(b => b.Url).IsRequired().HasMaxLength(500);
        });

        modelBuilder.Entity<Post>(entity =>
        {
            entity.HasKey(p => p.PostId);
            entity.HasOne(p => p.Blog)
                  .WithMany(b => b.Posts)
                  .HasForeignKey(p => p.BlogId);
        });
    }
}
```

`OnModelCreating` 是使用 Fluent API 配置模型的地方。你也可以用 Data Annotations（直接标注在实体类上），但 Fluent API 控制力更强，且能保持领域模型干净不沾基础设施代码。

### DbSet<T> 与实体类

`DbSet<T>` 代表数据库中的一张表。`context.Blogs` 查询的就是 Blogs 表，往 `context.Blogs` 里添加实体，EF Core 会自动排队等待下次 `SaveChanges` 插入。

实体类就是普通的 C# 类 — POCO。EF Core 靠惯例自动映射：名为 `Id` 或 `{ClassName}Id` 的属性默认为主键。你不用继承任何基类或实现任何接口，领域对象保持纯净。

### Change Tracking — 最强大也最容易被误解的特性

当你通过 `DbContext` 加载实体时，EF Core 在 change tracker 中记录它们的原始状态。调用 `SaveChangesAsync()` 时，EF Core 对比所有被追踪实体的当前状态与原始快照，生成最小集合的 INSERT、UPDATE、DELETE 语句。

这意味着你通常不需要显式标记某物为"已修改"。加载实体、改个属性、调 `SaveChangesAsync()` 即可 — EF Core 自己能判断出什么变了。

代价是 change tracker 有开销。一个积累了数千个被追踪实体的 `DbContext` 会明显变慢。对于只读不写的场景，在查询上调用 `.AsNoTracking()` 跳过追踪 — 这是 EF Core 里性价比最高的单行性能优化。

## 在 .NET 10 中注册 EF Core

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<BloggingContext>(options =>
    options.UseSqlServer(
        builder.Configuration.GetConnectionString("DefaultConnection"),
        sqlOptions =>
        {
            sqlOptions.EnableRetryOnFailure(
                maxRetryCount: 5,
                maxRetryDelay: TimeSpan.FromSeconds(30));
        }));

var app = builder.Build();

// 开发/预发布环境启动时自动应用迁移
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<BloggingContext>();
    await db.Database.MigrateAsync();
}
```

`AddDbContext` 默认以 **scoped** 生命周期注册 — 每个 HTTP 请求一个实例。这是刻意的设计：`DbContext` 不是线程安全的，跨并发请求共享一个实例是数据损坏的温床。

## LINQ 查询：你写 C#，它出 SQL

EF Core 最大的卖点之一是 LINQ 翻译。你写普通的 C# LINQ 表达式，EF Core 在运行时翻译成目标数据库方言的 SQL。

```csharp
public record PostSummary
{
    public int PostId { get; init; }
    public string Title { get; init; } = string.Empty;
}

public async Task<List<PostSummary>> GetPostsByBlogAsync(
    BloggingContext context, int blogId, int maxCount = 10)
{
    return await context.Posts
        .Where(p => p.BlogId == blogId)
        .OrderBy(p => p.Title)
        .Take(maxCount)
        .Select(p => new PostSummary
        {
            PostId = p.PostId,
            Title = p.Title,
        })
        .AsNoTracking()
        .ToListAsync();
}
```

几个值得注意的点：

- 多个 `.Where()` 可以叠加 — 生成 SQL 时自动合并为 AND 条件
- `.Select()` 做投影意味着 EF Core 只查询你需要的列，而不是 `SELECT *`
- `.AsNoTracking()` 跳过 change tracking — 读操作更快、更省内存
- `.ToListAsync()` 是查询真正执行的点

最后一条很关键。EF Core 的 LINQ 查询使用**延迟执行** — 查询以表达式树的形式被逐步构建，只有调用物化方法（`ToListAsync()`、`FirstOrDefaultAsync()`、`CountAsync()`）时才真正打到数据库。搞不清这一点是意外 N+1 查询和双重枚举 bug 的主要来源。

EF Core 10 还改善了对更复杂 LINQ 模式的翻译，意味着更少出现"部分查询将在客户端执行而非数据库端"的警告。

## 迁移：让 Schema 跟着模型走

每次修改实体类或 `DbContext` 配置，创建一个新迁移来描述 schema 的增量：

```bash
# 改完模型后创建新迁移
dotnet ef migrations add AddBlogDescriptionColumn

# 把所有待迁移应用到目标数据库
dotnet ef database update

# 生成 SQL 脚本供审核或生产部署
dotnet ef migrations script --idempotent --output migration.sql
```

迁移文件默认放在项目的 `Migrations` 文件夹里。每个文件包含两个方法：`Up()` 执行变更，`Down()` 回滚。EF Core 在 `__EFMigrationsHistory` 表中追踪哪些迁移已应用。

`--idempotent` 标记会生成检查型 SQL — 每条迁移执行前先检查是否已应用过，非常适合生产部署流水线。

一条黄金法则：**除非你完全清楚自己在做什么，永远不要手改生成的迁移文件**。如果需要自定义操作（重命名列、种子数据），追加在 `Up()` 中生成代码的后面，不要修改自动生成的部分。

## EF Core vs EF6

如果你用过经典的 Entity Framework 6（.NET Framework 版本），EF Core 会让你感觉熟悉但又处处不同。

**EF Core 大幅改进的地方：**

- **性能** — 快得多，尤其是在查询编译和批量操作上。查询结果缓存让重复执行的查询只付一次编译成本
- **跨平台** — Linux、macOS、Docker 容器都能跑。EF6 只支持 Windows
- **多 provider 支持** — PostgreSQL、SQLite、MySQL 都一等公民。EF6 主要围绕 SQL Server 构建
- **现代 C#** — records、nullable reference types、value objects。EF6 诞生时这些语言特性还不存在
- **更好的查询翻译** — EF Core 现在很少 fallback 到客户端求值。EF6 会静默地把大段查询放在进程内执行，拉回来比需要多得多的数据

到了 EF Core 10，对所有真实场景来说它基本是 EF6 的超集。几乎没有任何理由在新项目上选择 EF6。

## EF Core vs Dapper vs 原生 ADO.NET

| 场景                             | 工具    |
| -------------------------------- | ------- |
| 标准 CRUD、明确领域模型          | EF Core |
| 需要 schema 管理和版本控制的迁移 | EF Core |
| 团队偏好写 C# 而非 SQL           | EF Core |
| 跨数据库可移植性                 | EF Core |
| 极致查询性能、最小开销           | Dapper  |
| 复杂 SQL / 存储过程 / 动态 SQL   | Dapper  |
| 底层连接和事务控制               | ADO.NET |
| 写数据库 provider 或框架层       | ADO.NET |

好消息是你不用只选一个。EF Core 暴露了 `FromSqlRaw` 和 `ExecuteSqlRawAsync` 用于在需要时降级到原生 SQL，同时保留 ORM 的其他所有好处。很多成熟的 .NET 应用用 EF Core 做标准数据访问，用 Dapper 处理复杂报表和分析查询。

## 直接注入还是 Repository 模式

最简单的方式是直接把 `DbContext` 注入到 service 或 Minimal API handler 中。这对中小型应用完全够用 — 不要为不需要的东西加抽象层。

```csharp
public class BlogService(BloggingContext context)
{
    public async Task<Blog?> GetBlogByIdAsync(int id)
    {
        return await context.Blogs
            .Include(b => b.Posts)
            .AsNoTracking()
            .FirstOrDefaultAsync(b => b.BlogId == id);
    }
}
```

对于更大的应用 — 特别是需要为可测试性抽象数据层或强制模块边界时 — Repository 模式更自然。Repository 夹在业务逻辑和 `DbContext` 之间，只暴露对每个聚合有意义的操作。

关于该不该在 EF Core 上加 Repository 层，.NET 社区一直有争议 — 毕竟 `DbSet<T>` 本身就在很多方面充当了 Repository 的角色。答案是看团队需求和业务逻辑层对 EF Core 的耦合容忍度。

## 查询日志：看清生成的 SQL

能看见 EF Core 生成的 SQL 对于调试查询行为和上线前捕捉性能问题至关重要：

```csharp
builder.Services.AddDbContext<BloggingContext>(options =>
{
    options.UseSqlServer(connectionString);

    // 只在开发环境启用 — 会在日志中暴露参数值
    if (builder.Environment.IsDevelopment())
    {
        options.EnableSensitiveDataLogging();
        options.EnableDetailedErrors();
    }

    options.LogTo(
        message => Console.WriteLine(message),
        LogLevel.Information);
});
```

这是 EF Core 九篇文章集群的总览篇。后续的文章分别深入：起步安装、CRUD 操作、迁移策略、LINQ 查询技巧、关系配置、性能优化、单元与集成测试、EF Core vs Dapper 逐项对比。这篇总览给你地图，后面每一篇带你走完具体的领土。

## 参考

- [Entity Framework Core in .NET: The Complete Guide](https://www.devleader.ca/2026/06/17/entity-framework-core-in-net-the-complete-guide)
- [LINQ in C# Complete Guide](https://www.devleader.ca/2026/05/07/linq-in-c-complete-guide-to-language-integrated-query-net-6-9)
- [LINQ Deferred Execution in C#](https://www.devleader.ca/2026/05/15/linq-deferred-execution-in-c-when-queries-execute-and-multiple-enumeration-pitfalls)
- [Logging in .NET Complete Guide](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
