---
pubDatetime: 2025-11-04
title: EF Core 10 新特性：LeftJoin 与 RightJoin 操作符的引入
description: 深入探讨 Entity Framework Core 10 中引入的全新 LeftJoin 和 RightJoin 操作符，了解其如何简化 LINQ 查询语法并提升代码可读性，替代传统的 GroupJoin 与 DefaultIfEmpty 组合模式。
tags: ["EF Core", ".NET", "LINQ", "数据库"]
slug: ef-core-10-leftjoin-rightjoin-operators
source: https://www.milanjovanovic.tech/blog/whats-new-in-ef-core-10-leftjoin-and-rightjoin-operators-in-linq
---

# EF Core 10 新特性：LeftJoin 与 RightJoin 操作符的引入

在数据库开发中，`LEFT JOIN` 和 `RIGHT JOIN` 是非常常用的操作，用于关联多个数据表并保留特定一侧的所有记录。然而在 Entity Framework Core 的早期版本中，实现左外连接一直是一个令人头疼的问题。开发者不得不使用 `GroupJoin`、`DefaultIfEmpty` 和 `SelectMany` 的复杂组合来达到目的，这使得代码晦涩难懂且难以维护。

随着 .NET 10 和 Entity Framework Core 10 的发布，微软终于为 LINQ 引入了一流的 `LeftJoin` 和 `RightJoin` 方法。这一改进极大地简化了代码结构，让查询意图更加清晰明了。本文将深入探讨这两个新操作符的使用方法、工作原理以及它们相比传统方法的优势。

## LEFT JOIN 的概念解析

在关系型数据库术语中，**LEFT JOIN**（左外连接）是一种连接操作，它会返回左表中的所有行，以及右表中与之匹配的行。当右表中没有匹配的记录时，结果集中右表的列会填充为 `null`。

这种连接方式的应用场景非常广泛。例如：
- 显示所有产品及其评论（即使某些产品没有评论）
- 列出所有用户及其可选的个人资料设置
- 展示所有订单及其可能存在的物流信息

从数据逻辑上讲，LEFT JOIN 确保了"主体数据"（左表）的完整性，不会因为关联数据（右表）的缺失而导致主体记录丢失。

下图直观展示了 LEFT JOIN 的工作原理：

![左外连接示意图](../../assets/516/left-join-animation.gif)

*图片来源：[Data School](https://dataschool.com/how-to-teach-people-sql/left-right-join-animated/)*

从图中可以看出，左表的所有记录都会保留在结果集中，而右表只有匹配的记录才会出现，未匹配的部分用 null 填充。

## 传统方法：GroupJoin + DefaultIfEmpty 组合

在 .NET 10 之前，要在 LINQ 中实现左外连接，开发者必须使用一个复杂的模式：首先执行 `GroupJoin` 创建分组，然后对每个分组使用 `DefaultIfEmpty` 方法来确保左侧记录即使没有匹配项也会被保留，最后用 `SelectMany` 展平结果。

这种方法虽然功能完整，但代码冗长且不直观。让我们看看两种传统写法。

### 查询语法（Query Syntax）

使用 LINQ 查询表达式语法的左外连接实现如下：

```csharp
var query =
    from product in dbContext.Products
    join review in dbContext.Reviews on product.Id equals review.ProductId into reviewGroup
    from subReview in reviewGroup.DefaultIfEmpty()
    orderby product.Id, subReview.Id
    select new
    {
        ProductId = product.Id,
        product.Name,
        product.Price,
        ReviewId = (int?)subReview.Id ?? 0,
        Rating = (int?)subReview.Rating ?? 0,
        Comment = subReview.Comment ?? "N/A"
    };
```

这段代码的工作流程如下：
1. 使用 `join ... into` 语法创建分组连接
2. 使用 `from ... in reviewGroup.DefaultIfEmpty()` 确保即使某个产品没有评论，该产品记录也会出现在结果中
3. 在投影中对可能为 null 的字段使用 null 合并操作符 `??`

EF Core 会将上述 LINQ 查询转换为以下 SQL：

```sql
SELECT
    p."Id" AS "ProductId",
    p."Name",
    p."Price",
    COALESCE(r."Id", 0) AS "ReviewId",
    COALESCE(r."Rating", 0) AS "Rating",
    COALESCE(r."Comment", 'N/A') AS "Comment"
FROM "Products" AS p
LEFT JOIN "Reviews" AS r ON p."Id" = r."ProductId"
ORDER BY p."Id", COALESCE(r."Id", 0)
```

可以看到，生成的 SQL 相当简洁清晰，但 LINQ 代码却显得繁琐。

### 方法语法（Method Syntax）

使用方法链式调用的写法更为复杂：

```csharp
var query = dbContext.Products
    .GroupJoin(
        dbContext.Reviews,
        product => product.Id,
        review => review.ProductId,
        (product, reviewList) => new { product, subgroup = reviewList })
    .SelectMany(
        joinedSet => joinedSet.subgroup.DefaultIfEmpty(),
        (joinedSet, review) => new
        {
            ProductId = joinedSet.product.Id,
            joinedSet.product.Name,
            joinedSet.product.Price,
            ReviewId = (int?)review!.Id ?? 0,
            Rating = (int?)review!.Rating ?? 0,
            Comment = review!.Comment ?? "N/A"
        })
    .OrderBy(result => result.ProductId)
    .ThenBy(result => result.ReviewId);
```

这个实现包含以下步骤：
1. **GroupJoin**：按照连接键对两个集合进行分组，将每个产品与其对应的评论列表关联
2. **SelectMany + DefaultIfEmpty**：展平分组结果，当某个产品没有评论时，`DefaultIfEmpty` 会插入一个 null 对象，确保该产品仍然出现在结果中
3. **投影**：创建最终的匿名类型结果，并处理可能的 null 值

尽管这种方法在逻辑上是正确的，但对于如此常见的数据库操作来说，代码过于冗长。很多开发者宁愿编写两个独立的查询，或者错误地使用内连接（从而丢失数据），也不愿意写这么复杂的代码。

## EF Core 10 的新方式：LeftJoin 方法

现在，有了 EF Core 10，我们可以用更直观的方式表达左外连接的意图。新的 `LeftJoin` 方法是 LINQ 的一流成员，EF Core 会将其直接转换为 SQL 的 `LEFT JOIN`。

```csharp
var query = dbContext.Products
    .LeftJoin(
        dbContext.Reviews,
        product => product.Id,
        review => review.ProductId,
        (product, review) => new
        {
            ProductId = product.Id,
            product.Name,
            product.Price,
            ReviewId = (int?)review.Id ?? 0,
            Rating = (int?)review.Rating ?? 0,
            Comment = review.Comment ?? "N/A"
        })
    .OrderBy(x => x.ProductId)
    .ThenBy(x => x.ReviewId);
```

生成的 SQL 与之前完全相同，但代码变得简洁易懂。

### LeftJoin 的优势

使用新的 `LeftJoin` 方法有以下显著优势：

1. **意图清晰**：当你看到 `LeftJoin` 时，你立即知道这是一个左外连接操作，无需解析复杂的 `GroupJoin` 和 `DefaultIfEmpty` 组合
2. **代码简洁**：减少了代码量，消除了 `GroupJoin`、`DefaultIfEmpty` 和 `SelectMany` 的嵌套结构
3. **结果一致**：保留左表的所有记录，右表的匹配记录可能为 null，与数据库 LEFT JOIN 的语义完全一致
4. **更易维护**：新开发者更容易理解代码意图，降低了学习曲线

### 注意事项

需要特别注意的是，截至目前，C# 的查询语法（`from ... select ...` 形式）尚未支持 `left join` 或 `right join` 关键字。因此，你只能使用上述的方法语法来调用 `LeftJoin`。这是一个语言层面的限制，未来版本的 C# 可能会添加相应的查询语法支持。

## 同样新增的 RightJoin 方法

除了 `LeftJoin`，EF Core 10 还引入了 `RightJoin` 方法。与左外连接相反，**RIGHT JOIN**（右外连接）保留右表的所有行，只返回左表中与之匹配的行。EF Core 会将 `RightJoin` 转换为 SQL 的 `RIGHT JOIN`。

虽然在实际应用中 RIGHT JOIN 使用频率相对较低（因为大多数情况下可以通过调换表的顺序来使用 LEFT JOIN 达到相同效果），但在某些场景下，从右侧集合出发的查询逻辑可能更自然。

### RightJoin 示例

```csharp
var query = dbContext.Reviews
    .RightJoin(
        dbContext.Products,
        review => review.ProductId,
        product => product.Id,
        (review, product) => new
        {
            ProductId = product.Id,
            product.Name,
            product.Price,
            ReviewId = (int?)review.Id ?? 0,
            Rating = (int?)review.Rating ?? 0,
            Comment = review.Comment ?? "N/A"
        });
```

在这个例子中，我们从 `Reviews` 集合开始，但最终保留的是所有 `Products` 记录（无论它们是否有评论）。这在某些报表场景中可能更符合业务逻辑的表达方式。

生成的 SQL 如下：

```sql
SELECT
    p."Id" AS "ProductId",
    p."Name",
    p."Price",
    COALESCE(r."Id", 0) AS "ReviewId",
    COALESCE(r."Rating", 0) AS "Rating",
    COALESCE(r."Comment", 'N/A') AS "Comment"
FROM "Reviews" AS r
RIGHT JOIN "Products" AS p ON r."ProductId" = p."Id"
```

### 何时使用 RightJoin

使用 `RightJoin` 的典型场景包括：
- 查询逻辑从次要实体开始，但需要保留主要实体的完整性
- 某些复杂的多表连接中，调换顺序会导致逻辑混乱
- 维护现有 SQL 查询的语义一致性（如从 SQL 迁移到 LINQ）

不过在大多数情况下，通过调整查询顺序使用 `LeftJoin` 会更符合开发者的阅读习惯。

## 实际应用建议

在实际项目中使用 `LeftJoin` 和 `RightJoin` 时，有一些最佳实践值得遵循：

### 1. 处理可空类型

在投影结果中，务必正确处理来自右表（对于 LEFT JOIN）或左表（对于 RIGHT JOIN）的可空字段：

```csharp
ReviewId = (int?)review.Id ?? 0,
Comment = review.Comment ?? "N/A"
```

使用 null 合并操作符 `??` 或 null 条件操作符 `?.` 可以避免运行时的 null 引用异常。

### 2. 保持投影简洁

只选择实际需要的列，避免拉取整个实体对象。这不仅能减少网络传输量，还能提升查询性能：

```csharp
// 推荐：只选择需要的字段
select new { product.Name, review.Rating }

// 避免：拉取所有字段
select new { product, review }
```

### 3. 为连接键添加索引

外连接的性能很大程度上依赖于连接键上是否有索引。确保参与连接的字段（如 `ProductId`、`ReviewId` 等）都有适当的索引：

```csharp
// 在 EF Core 配置中
modelBuilder.Entity<Review>()
    .HasIndex(r => r.ProductId);
```

良好的索引策略能显著提升复杂查询的执行效率。

### 4. 考虑数据量

当左表数据量很大时，左外连接可能会产生大量结果行。考虑使用分页或过滤条件来限制结果集大小：

```csharp
var query = dbContext.Products
    .Where(p => p.IsActive)  // 先过滤
    .LeftJoin(...)
    .Take(100);  // 限制结果数量
```

## 与旧方法的对比总结

| 特性 | GroupJoin + DefaultIfEmpty | LeftJoin / RightJoin |
|------|---------------------------|---------------------|
| 代码行数 | 较多（需要多步操作） | 较少（一步完成） |
| 可读性 | 低（需要理解复杂组合） | 高（意图明确） |
| 学习曲线 | 陡峭 | 平缓 |
| SQL 生成 | 相同 | 相同 |
| 支持版本 | EF Core 1.0+ | EF Core 10.0+ |
| 查询语法支持 | 支持 | 暂不支持 |

可以看出，新的操作符在保持功能完整性的同时，大幅提升了代码的可读性和可维护性。

## 迁移策略

如果你的项目已经使用了 `GroupJoin` 和 `DefaultIfEmpty` 组合，并计划升级到 EF Core 10，可以考虑以下迁移策略：

1. **逐步替换**：先在新功能中使用 `LeftJoin`，逐步重构旧代码
2. **编写单元测试**：确保重构后的查询结果与原来一致
3. **性能对比**：在生产环境样本数据上对比重构前后的性能

大多数情况下，由于生成的 SQL 相同，性能不会有显著变化，但代码的可维护性会得到极大改善。

## 总结

Entity Framework Core 10 引入的 `LeftJoin` 和 `RightJoin` 操作符是一个看似简单但影响深远的改进。它们解决了长期以来困扰 .NET 开发者的一个痛点：如何在 LINQ 中优雅地表达外连接。

左外连接和右外连接在实际应用中非常常见，几乎每个数据驱动的应用都会用到这些操作。新的操作符让代码的意图与底层数据库操作的语义完美对齐，降低了认知负担，提升了开发效率。

现在，开发者不再有借口跳过正确的外连接实现，也不会因为代码复杂而选择错误的内连接。随着 .NET 生态的不断完善，这类贴近实际需求的改进会让开发体验越来越好。

如果你正在使用或计划使用 .NET 10，强烈建议尝试这些新特性，让你的 LINQ 查询更加清晰易懂。

## 参考资源

- [Microsoft Learn - What's New in EF Core 10](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/whatsnew)
- [Microsoft Docs - Enumerable.LeftJoin Method](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable.leftjoin)
- [Microsoft Docs - Enumerable.RightJoin Method](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable.rightjoin)
- [LINQ Join Operations](https://learn.microsoft.com/en-us/dotnet/csharp/linq/standard-query-operators/join-operations)
