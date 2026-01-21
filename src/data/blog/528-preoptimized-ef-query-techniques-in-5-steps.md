---
pubDatetime: 2026-01-19
title: "EF Core 预优化指南：5 个写出高性能查询的技巧"
description: "提倡“预优化”理念：与其事后重构，不如一开始就写出正确的 EF Core 查询。本文介绍了 5 个基础技巧，涵盖字段投影、Eager Loading、NoTracking、避免笛卡尔积和拆分查询。"
tags: ["EF Core", ".NET", "Performance", "C#", "SQL"]
slug: "preoptimized-ef-query-techniques-in-5-steps"
source: "https://thecodeman.net/posts/preoptimized-ef-query-techniques-5-steps-to-success"
---

# 预先优化的 EF Query 技术：5 个成功步骤

## 背景

我们经常听到关于优化某段代码或查询的讨论，这通常指的是**“重构一开始没有写好的代码”**。

例如，有人在 `foreach` 循环中放置了数据库调用。过了一段时间，他发现这是一个性能问题，于是“优化”了代码。实际上，这并不叫优化，这只是把代码改成了一开始就该有的样子。

对于 Entity Framework Core，我们可以遵循许多规则来避免这些低级错误。与其等待性能瓶颈出现再去亡羊补牢，不如在编写代码的最初阶段就采用“预优化”的思维。即使是初学者，也应该尽量在第一遍写代码时就符合这些最佳实践。

今天，我将介绍编写 EF Core 查询时应遵循的 5 个基本技巧。

## 1. 只获取你需要的字段 (Projection)

这个技巧的核心是通过只选择特定操作所需的字段，而不是获取整个实体对象，来优化数据检索。这种方法可以显著提高应用程序的性能。

**反例与正例：**

假设数据库中的 `Employees` 表有许多字段，但在展示层我们只需要名字和邮箱。

```csharp
// 推荐做法：使用 Select 进行投影
var employeeList = context.Employees
    .Select(e => new EmployeeDto
    {
        Name = e.Name,
        Email = e.Email
    })
    .ToList();
```

通过这样做，我们避免了“提取所有数据”的浪费。

**为什么要这样做？**

1.  **减少数据传输 (Reduced Data Transfer)**：获取更少的字段意味着从数据库传输到应用程序的数据量更少，这对网络性能至关重要。
2.  **降低内存使用 (Lower Memory Usage)**：加载更少的字段意味着在应用程序中占用更少的内存，这对于处理大数据集非常重要。
3.  **提高查询性能 (Improved Query Performance)**：数据库引擎检索和传输的数据更少，查询执行速度更快。
4.  **减少实体跟踪开销 (Decreased Entity Tracking Overhead)**：投影出的 DTO 或匿名对象通常不会被 EF Core 更改追踪器跟踪，节省了额外的开销（除非你显式要求）。

## 2. 避免 N+1 查询

N+1 查询是数据库操作中常见的性能杀手，尤其是在使用 ORM 时。它发生在你先使用 1 个查询获取对象列表，然后循环遍历这些对象，为每个对象再执行 1 个查询来获取相关数据。如果是 100 个对象，就是 1 + 100 次查询。

**问题代码：**

```csharp
// 1 次查询
var blogs = context.Blogs.ToList();

foreach (var blog in blogs)
{
    // N 次查询：每次访问 Posts 都会触发数据库调用
    var posts = blog.Posts; 

    foreach (var post in posts)
    {
        Console.WriteLine(post.Title);
    }
}
```

**修复代码 (Eager Loading)：**

```csharp
// 在一次查询中获取所有博客及其文章
var blogs = context.Blogs
    .Include(b => b.Posts)
    .ToList();

foreach (var blog in blogs)
{
    // 数据已在内存中，无需额外查询
    foreach (var post in blog.Posts)
    {
        Console.WriteLine(post.Title);
    }
}
```

**关键点：**

*   **Include 方法**：告诉 EF Core 在初始查询中就加载相关的 `Posts`。
*   **单一查询执行**：`context.Blogs.Include(b => b.Posts).ToList()` 会生成并执行一条包含 JOIN 的 SQL 语句，一次性取回所有数据。
*   **简化逻辑**：代码意图更明确，即我们需要博客及其文章。

## 3. 使用 .AsNoTracking()

`.AsNoTracking()` 是一个非常有效的性能优化手段，适用于**只读**场景（即你只打算读取数据，而不打算更新或删除它）。

**示例：**

```csharp
var products = context.Products
    .AsNoTracking()
    .ToList();
// 仅用于展示，不进行修改
```

**为什么要这样做？**

1.  **性能提升**：在大规模应用或大数据集下效果尤为明显。查询执行更快，内存占用更少。
2.  **减少开销**：EF Core 不需要为这些实体建立快照或维护状态信息，直接跳过更改追踪逻辑。

**注意事项：**

*   **不适用于 CUD 操作**：如果你计划更新 (Update)、删除 (Delete) 实体，不要使用 `AsNoTracking`，因为 EF Core 需要追踪实体状态才能将更改保存回数据库。
*   **最适合无状态操作**：例如 API 的 GET 请求，通常只需要返回数据给客户端，不需要在当前上下文中保持实体状态。

## 4. 避免笛卡尔积爆炸 (Cartesian Explosion)

笛卡尔积爆炸是指查询由于不正确的连接 (Join) 方式，意外产生了不成比例的大量记录，严重影响性能。

**反例 (笛卡尔积)：**

假设我们想列出所有书籍及其作者，但写出了错误的 LINQ 查询：

```csharp
// 错误查询：导致笛卡尔积
var query = from a in context.Authors
            from b in context.Books
            select new { a.Name, b.Title };

var results = query.ToList(); 
```

在这个查询中，我们错误地将**每个**作者与**每本**书进行了组合（Cross Join），无论这本书是否由该作者编写。如果作者有 100 人，书有 1000 本，结果将是 100,000 条记录。

**正例 (正确连接)：**

```csharp
// 正确查询：使用 Join
var query = from a in context.Authors
            join b in context.Books on a.AuthorId equals b.AuthorId
            select new { a.Name, b.Title };

var results = query.ToList();
```

**影响：**

*   **性能下降**：数据库需要处理海量数据，查询变慢。
*   **资源密集**：消耗大量 CPU 和内存。
*   **结果不准确**：结果中充斥着重复或无关的数据，毫无意义。

## 5. 使用 AsSplitQuery()

在 EF Core 5.0 及更高版本中，`.AsSplitQuery()` 允许将包含集合关联的单一查询拆分为多个 SQL 查询。这在处理复杂查询或大型数据集时能显著提高性能。

**背景：**

默认情况下，EF Core 会尝试使用 JOIN 在单个 SQL 查询中获取所有相关数据。对于简单关系这很有效，但如果你加载一个包含大量子实体的集合（例如一名作者有 1000 本书），单个 JOIN 查询会导致主实体的数据（作者信息）在每一行子实体（书）中重复，造成数据冗余和传输浪费（这也称为数据爆炸）。

**未使用 AsSplitQuery (默认行为):**

```csharp
var authors = context.Authors
    .Include(a => a.Books)
    .ToList();
// 生成 1 条 SQL，使用 LEFT JOIN，可能导致数据冗余传输
```

**使用 AsSplitQuery (优化后):**

```csharp
var authors = context.Authors
    .Include(a => a.Books)
    .AsSplitQuery()
    .ToList();
// 生成 2 条 SQL：一条查 Authors，一条查 Books，然后在内存中组装
```

**收益与权衡：**

*   **收益**：避免了 JOIN 带来的数据冗余，减少了内存开销，对于包含大型集合的查询，执行计划通常更高效。
*   **权衡**：会导致更多的数据库往返次数 (Round-Trips)。在数据库延迟较高的环境中需要权衡使用。它并不总是最好的选择，但在特定的大数据量场景下非常有效。

## 总结

不要等到由于粗心和代码写得不好而遇到性能问题时可以“优化”。从一开始就尽力遵循这些基本原则。考虑到 EF Core 如今的强大功能，只要遵循这些基础，通常就能满足绝大多数性能需求。

除了这些，还有很多其他的最佳实践值得学习，但这 5 点是迈向高性能 EF Core 之旅的坚实第一步。

---
**参考资料：**
*   [Pre-Optimized EF Query Techniques 5 Steps to Success](https://thecodeman.net/posts/preoptimized-ef-query-techniques-5-steps-to-success)
