---
pubDatetime: 2026-06-26T08:56:13+08:00
title: "EF Core vs Dapper：.NET 数据访问怎么选"
description: "EF Core 和 Dapper 的争论几乎出现在每个 .NET 项目里。事实是：没有哪个工具绝对更好——它们解决不同抽象层级的问题。这篇文章从性能、查询控制、迁移、学习曲线等维度逐项对比，给出决策矩阵和一个生产级的混合使用模式。"
tags: ["EF Core", "Dapper", ".NET", "ORM", "Performance"]
slug: "ef-core-vs-dapper-dotnet-comparison"
ogImage: "../../assets/905/01-cover.png"
source: "https://www.devleader.ca/2026/06/25/ef-core-vs-dapper-in-net-when-to-use-each"
---

选数据访问库是那种静悄悄影响后续一切的决定。EF Core vs Dapper 的争论几乎出现在每个 .NET 项目里，两边都有热情的支持者。现实是：没有哪个工具绝对更好。它们在不同抽象层级解决不同问题——知道你的问题到底是什么，才是选对工具的关键。

## 两个工具分别是什么

**EF Core** 是 Microsoft 构建的完整 ORM。它提供 code-first 建模、数据库迁移、LINQ 到 SQL 翻译、变更追踪和 scaffolding。设计目标是开发者生产力——让你用 C# 思考领域模型而不是写 SQL。

在 EF Core 10 中，预编译查询（AOT）已生产可用，LINQ 翻译持续改进，SQLite 日期时间处理也更完善。JSON 列支持和复杂类型（EF Core 8）仍是关键特性。

**Dapper** 是 Stack Overflow 团队创建的 micro-ORM。它只做一件事：把 SQL 查询结果映射到 C# 对象。没有 LINQ 翻译、没有迁移、没有变更追踪、没有代码生成。你写 SQL，Dapper 跑 SQL，你拿到对象。整个库就是 `IDbConnection` 上的一层薄扩展。

## 逐项对比

| 维度        | EF Core                                                    | Dapper                                         |
| ----------- | ---------------------------------------------------------- | ---------------------------------------------- |
| 抽象层级    | 高（C# 描述意图，EF 生成 SQL）                             | 低（自己写 SQL，Dapper 管映射）                |
| 原始性能    | 良好（`AsNoTracking` + 编译查询后接近 Dapper）             | 极佳（几乎无 ADO.NET 之上的额外开销）          |
| 查询控制    | 高（LINQ 覆盖 90%，`FromSqlRaw` 兜底）                     | 完全控制（你写的 SQL 就是最终执行的 SQL）      |
| 数据库迁移  | 内置（`dotnet ef migrations add`）                         | 无（需配合 FluentMigrator / DbUp / Liquibase） |
| 学习曲线    | 中等（需理解 DbContext 生命周期、变更追踪、LINQ 翻译陷阱） | 低（会 SQL 就会 Dapper）                       |
| 团队适配    | 适合 C# 思维、对象优先的团队                               | 适合 SQL 思维、查询优先的团队                  |
| 复杂 Schema | 优秀（多对多、继承映射、owned types、temporal tables）     | 有限（多结果集、复杂 join 需手动处理）         |

## 同一个查询，两种写法

以"按标签查询已发布的博客文章及其作者"为例：

```csharp
// EF Core：LINQ + Include + AsNoTracking
public async Task<IReadOnlyList<BlogPostSummary>> GetPublishedByTagAsync(
    string tag, CancellationToken ct = default)
{
    return await db.BlogPosts
        .AsNoTracking()
        .Where(p => p.IsPublished && p.Tags.Contains(tag))
        .OrderByDescending(p => p.PublishedAt)
        .Select(p => new BlogPostSummary(
            p.Id, p.Title, p.Author.DisplayName, p.PublishedAt))
        .ToListAsync(ct);
}

// Dapper：手写 SQL，精确控制
const string sql = """
    SELECT p.Id, p.Title, a.DisplayName AS AuthorName, p.PublishedAt
    FROM BlogPosts p
    INNER JOIN Authors a ON a.Id = p.AuthorId
    WHERE p.IsPublished = 1 AND p.Tags LIKE @TagPattern
    ORDER BY p.PublishedAt DESC
    """;

var results = await db.QueryAsync<BlogPostSummary>(
    new CommandDefinition(sql, new { TagPattern = $"%{tag}%" },
        cancellationToken: ct));
```

EF Core 版本更重构安全（重命名 C# 属性不会静默破坏查询），Dapper 版本让你精确控制 SQL 且没有意外。

写入侧也是同样模式——EF Core 通过变更追踪自动生成 INSERT，Dapper 需要手写 INSERT 语句。

## 混合使用：两者放一个项目里

这是成熟 .NET 应用最务实的答案。不需要二选一然后到处用同一个。

常见模式：**EF Core 管所有写入和复杂领域操作**（变更追踪和迁移的价值在这里），**Dapper 管读取投射和报表查询**（原始性能和控制在这里）。

```csharp
public sealed class OrderService(AppDbContext db)
{
    // EF Core 管领域写入
    public async Task PlaceOrderAsync(PlaceOrderRequest request,
        CancellationToken ct = default)
    {
        var order = new Order { ... };
        db.Orders.Add(order);
        await db.SaveChangesAsync(ct);
    }

    // Dapper 管读取投射，复用同一个连接
    public async Task<IReadOnlyList<OrderSummaryDto>>
        GetCustomerOrderSummaryAsync(int customerId,
            CancellationToken ct = default)
    {
        var connection = db.Database.GetDbConnection();
        const string sql = """
            SELECT o.Id, o.PlacedAt, o.Status,
                   SUM(l.Quantity * l.UnitPrice) AS TotalAmount
            FROM Orders o
            INNER JOIN OrderLines l ON l.OrderId = o.Id
            WHERE o.CustomerId = @CustomerId
            GROUP BY o.Id, o.PlacedAt, o.Status
            """;
        var results = await connection.QueryAsync<OrderSummaryDto>(
            sql, new { CustomerId = customerId });
        return results.AsList();
    }
}
```

`db.Database.GetDbConnection()` 让 Dapper 复用 EF Core 管理的数据库连接。如果在事务作用域内，Dapper 也可以通过 `db.Database.CurrentTransaction?.GetDbTransaction()` 参与同一个事务。

## 决策矩阵

| 场景                       | 推荐          | 理由                                  |
| -------------------------- | ------------- | ------------------------------------- |
| 标准 CRUD 应用             | EF Core       | 开发效率、迁移、变更追踪物有所值      |
| 极端性能要求               | Dapper        | 最小开销，完全 SQL 控制               |
| 简单脚本或 ETL             | Dapper        | 不需要完整 ORM                        |
| 快速原型、约定驱动         | EF Core       | Scaffolding + 迁移 + LINQ 大幅减样板  |
| 遗留库 + 存储过程          | Dapper 或混合 | 存储过程结果自然地映射到 Dapper       |
| 复杂领域模型               | EF Core       | Owned types、继承、导航属性是 EF 强项 |
| 读密集型报表查询           | Dapper        | 手写 SQL，无变更追踪开销              |
| 新项目、团队会 C# 不会 SQL | EF Core       | LINQ 覆盖多数场景，减少上下文切换     |

## 关于性能数据

你在网上看到的 benchmark——"Dapper 比 EF Core 快 2 倍"或者"带编译查询的 EF Core 只慢 5% "——除非跟你的场景匹配，否则都该持怀疑态度。

性能高度依赖：(1) 查询复杂度——简单 `SELECT * WHERE Id = @Id` 会放大 Dapper 优势，带 join 的复杂聚合是另一回事；(2) 连接池配置——对短查询来说，连接开/关开销可能比 ORM 开销大得多；(3) 变更追踪范围——读路径加 `AsNoTracking()` 可以消掉大部分差距；(4) 编译查询——EF Core 编译查询缓存 LINQ 翻译结果，能让热路径性能非常接近 Dapper。

正确做法：用 BenchmarkDotNet，在近似生产的硬件上、针对你的实际数据库和实际查询做 benchmark。

## 结论

**选 EF Core，当你**：在构建标准 .NET 应用且开发者效率是关键，需要框架管理 schema 迁移，团队习惯 C# 和对象思维多于 SQL，以及处理复杂领域模型。

**选 Dapper，当你**：团队 SQL 熟练，处理遗留数据库或大量存储过程，需要报表查询的原始性能，或构建简单数据访问脚本不需要完整 ORM。

**两个都用，当你**：应用有分明的读写模式——EF Core 管领域写入侧（变更追踪和迁移有回报），Dapper 管读取投射侧（要完全 SQL 控制和最小开销）。这不是妥协，而是很多成熟 .NET 应用在生产中使用的架构决策。

两个工具都没错。错的是教条式地选一个工具然后把它强塞进所有场景——包括另一个工具显然更适合的那些。

> 如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [原文：EF Core vs Dapper in .NET: When to Use Each](https://www.devleader.ca/2026/06/25/ef-core-vs-dapper-in-net-when-to-use-each)
