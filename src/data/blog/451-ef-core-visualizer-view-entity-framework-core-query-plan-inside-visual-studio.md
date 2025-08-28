---
pubDatetime: 2025-08-28
tags: [".NET", "Entity Framework", "Visual Studio", "Performance", "Debugging"]
slug: ef-core-visualizer-view-entity-framework-core-query-plan-inside-visual-studio
source: https://devblogs.microsoft.com/dotnet/ef-core-visualizer-view-entity-framework-core-query-plan-inside-visual-studio
title: EFCore.Visualizer – 在 Visual Studio 中查看 Entity Framework Core 查询计划
description: 了解如何使用 EFCore.Visualizer 扩展在 Visual Studio 中直接查看和分析 Entity Framework Core 查询的执行计划，优化数据库查询性能。
---

Entity Framework Core 是一个功能强大的 ORM 框架，为当今的许多应用程序提供动力。使用 EF Core，开发者可以编写强类型的 LINQ 查询，框架会将其转换为目标数据库的 SQL 查询。凭借高级功能如包含嵌套集合和延迟加载，Entity Framework Core 让开发者免于编写样板数据访问代码。

## 问题分析

虽然 LINQ 查询通常会被转换为性能良好的 SQL 查询，但随着模式变得更大、查询变得更复杂，生成的 SQL 可能会变得次优。缺少数据库索引也可能导致查询执行缓慢，从而降低应用程序性能。

EF Core 提供了一种简单的方法来[记录生成的查询](https://learn.microsoft.com/ef/core/logging-events-diagnostics/#simple-logging)和[识别慢查询](https://learn.microsoft.com/ef/core/performance/performance-diagnosis?tabs=simple-logging%2Cload-entities#identifying-slow-database-commands-via-logging)。这有时可能足够，但要真正找到问题的根源并了解数据库引擎如何执行查询，有必要探索[查询执行计划](https://learn.microsoft.com/sql/relational-databases/performance/execution-plans?view=sql-server-ver17)。

## 解决方案

[EFCore.Visualizer](https://marketplace.visualstudio.com/items?itemName=GiorgiDalakishvili.EFCoreVisualizer) 是一个 Visual Studio 扩展，用于在 Visual Studio 内部直接查看和分析查询计划。该扩展为 `IQueryable<>` 变量添加了调试器可视化器，显示生成的查询及其执行计划。

当您遇到断点并悬停在任何 `IQueryable` 变量上时，EFCore.Visualizer 会捕获查询，从数据库请求执行计划，并显示查询计划的可视化表示。可视化器适用于任何 EF Core 查询，无论是简单的 `Where` 子句还是包含连接、包含和聚合的复杂查询。该扩展支持每个主要的关系数据库管理系统：SQL Server、PostgreSQL、MySQL、SQLite 和 Oracle，会自动检测您的数据库提供程序。

通过将查询计划直接带入 Visual Studio，它消除了在 Visual Studio 和数据库管理工具之间切换以查看查询计划的需要，并缩短了开发者的内循环。开发者无需从 Visual Studio 复制查询到数据库管理工具、分析执行计划、切换回来、调整查询并重复上述步骤，而是可以在 Visual Studio 中直接查看查询计划，就在他们编写和调试代码的地方。

## 安装方法

开始使用 EFCore.Visualizer 非常简单。您可以通过在扩展管理器中搜索"EFCore.Visualizer"直接从 Visual Studio 内部安装扩展。或者，您可以从 [Visual Studio Marketplace](https://marketplace.visualstudio.com/items?itemName=GiorgiDalakishvili.EFCoreVisualizer) 下载它。

## 使用示例

为了演示扩展的使用，我将使用以下模型：

```csharp
public class BloggingContext : DbContext
{
    public DbSet<Blog> Blogs { get; set; }
    public DbSet<Post> Posts { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
        modelBuilder.Entity<Post>().HasIndex(p => p.PublishedAt);
    }
}

public class Blog
{
    public int BlogId { get; set; }
    public string Url { get; set; }

    public List<Post> Posts { get; } = new();
}

public class Post
{
    public int PostId { get; set; }
    public string Title { get; set; }
    public string Content { get; set; }

    public DateTimeOffset PublishedAt { get; set; }

    public int BlogId { get; set; }
    public Blog Blog { get; set; }
}
```

示例数据库在 `Posts` 表中有几千行数据。

安装后，开始调试并悬停在任何 `IQueryable` 实例上。在标准调试器工具提示中点击"查询计划可视化器"并查看生成的 SQL 和执行计划。

让我们首先编写一个查询来获取 2010 年写的所有文章并检查其执行计划：

```csharp
var postsQuery = bloggingContext.Posts.Where(post => post.PublishedAt.Year == 2010);
```

您可以看到，即使 `PublishedAt` 列上有索引，SQL Server 也不使用它。如果您查看生成的查询，您会注意到查询正在从 `PublishedAt` 列中提取年份，这使得查询变成[非SARGABLE](https://en.wikipedia.org/wiki/Sargable)的。

让我们在不改变语义的情况下重写查询，看看执行计划是什么样子的：

```csharp
var fromDate = new DateTime(2010, 1, 1);
var toDate = new DateTime(2011, 1, 1);

postsQuery = bloggingContext.Posts.Where(post => post.PublishedAt >= fromDate && post.PublishedAt < toDate);
```

如您所见，通过对查询的简单更改，数据库现在正在利用 `PublishedAt` 上的索引。

## 工作原理

可视化器的工作原理是将 LINQ 查询转换为 ADO.NET 命令，并从数据库引擎获取其计划。然后使用 [html-query-plan](https://github.com/JustinPealing/html-query-plan) 库为 SQL Server 渲染计划，使用 [pev2](https://github.com/dalibo/pev2/) 为 Postgres 渲染，或使用 [treeflex](https://github.com/dumptyd/treeflex) 为其他数据库渲染。

## 限制

当使用减少终止操作符（`Count()`、`Min()`、`First()` 等）时，可视化器不支持查询。此外，如果查询非常复杂或到数据库引擎的网络连接很慢，获取查询计划可能会超过自定义可视化器的5秒限制。遗憾的是，没有办法延长超时时间，但您可以为这个 [issue](https://github.com/microsoft/VSExtensibility/issues/325) 投票。

## 总结

作为开发者，我们都经历过这种情况——盯着一个慢查询，想知道数据库实际在做什么。如果您正在使用 Entity Framework Core 并想更好地了解查询性能，请尝试 [EFCore.Visualizer](https://marketplace.visualstudio.com/items?itemName=GiorgiDalakishvili.EFCoreVisualizer)。如果您想贡献或探索它的工作原理，源代码可在 [GitHub](https://github.com/Giorgi/EFCore.Visualizer) 上获取。

这个扩展是由 [Giorgi Dalakishvili](https://github.com/Giorgi) 开发的，它为 Entity Framework Core 开发者提供了一个强大的调试和性能优化工具。通过直接在 Visual Studio 中查看查询执行计划，开发者可以更快地识别和解决性能问题，提高应用程序的整体性能。

## 主要特性

- **支持多种数据库**：SQL Server、PostgreSQL、MySQL、SQLite 和 Oracle
- **可视化执行计划**：直观的图形界面显示查询执行步骤
- **无缝集成**：直接在 Visual Studio 调试器中使用
- **性能分析**：帮助识别查询性能瓶颈
- **开源项目**：可在 GitHub 上查看源代码和贡献

对于使用 Entity Framework Core 的 .NET 开发者来说，EFCore.Visualizer 是一个不可或缺的调试和性能优化工具。它简化了查询性能分析的流程，让开发者能够更高效地优化数据库查询。
