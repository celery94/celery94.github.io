---
pubDatetime: 2024-04-22
tags: ["Productivity", "Tools"]
source: https://www.milanjovanovic.tech/blog/ef-core-raw-sql-queries
author: Milan Jovanović
title: EF Core 原生 SQL 查询
description: EF Core 在即将到来的版本中获得了许多新的和令人兴奋的功能。
---

# EF Core 原生 SQL 查询

> ## 摘要
>
> EF Core 在即将到来的版本中获得了许多新的和令人兴奋的功能。
>
> 原文 [EF Core Raw SQL Queries](https://www.milanjovanovic.tech/blog/ef-core-raw-sql-queries)

---

**EF Core** 在即将到来的版本中获得了许多新的和令人兴奋的功能。

**EF7** 引入了使用 **SQL** 查询返回**标量类型**的支持。

现在我们在 **EF8** 中获得了使用原生 **SQL 查询**查询**未映射类型**的支持。

这正是 **Dapper** 开箱即用所提供的，看到 **EF Core** 追赶上来是件好事。

- [原生 SQL 查询](https://www.milanjovanovic.tech/blog/ef-core-raw-sql-queries?utm_source=Twitter&utm_medium=social&utm_campaign=15.04.2024#ef-core-and-sql-queries)
- [使用 LINQ 组合 SQL 查询](https://www.milanjovanovic.tech/blog/ef-core-raw-sql-queries?utm_source=Twitter&utm_medium=social&utm_campaign=15.04.2024#composing-sql-queries-with-linq)
- [使用 SQL 执行数据修改](https://www.milanjovanovic.tech/blog/ef-core-raw-sql-queries?utm_source=Twitter&utm_medium=social&utm_campaign=15.04.2024#sql-queries-for-data-modifications)

## EF Core 和 SQL 查询

**EF7** 增加了对返回标量类型的**原生 SQL 查询**的支持。**EF8** 在此基础上又进一步，允许原生 SQL 查询返回任何可映射类型，而无需将其包含在 **EF 模型**中。

你可以使用 `SqlQuery` 和 `SqlQueryRaw` 方法查询未映射类型。

`SqlQuery` 方法使用字符串插值来参数化查询，从而防范 SQL 注入攻击。

这里是一个返回 `OrderSummary` 列表的示例查询：

```csharp
var startDate = new DateOnly(2023, 1, 1);

var ordersIn2023 = await dbContext
    .Database
    .SqlQuery<OrderSummary>(
        $"SELECT * FROM OrderSummaries AS o WHERE o.CreatedOn >= {startDate}")
    .ToListAsync();
```

这将是发送给数据库的 **SQL**：

```sql
SELECT * FROM OrderSummaries AS o WHERE o.CreatedOn >= @p0
```

用于查询结果的类型可以有一个参数化的构造函数。属性名称不需要与数据库中的列名匹配，但必须与结果集中的值的名称匹配。

你还可以执行原生 SQL 查询并返回结果，使用：

- 视图
- 函数
- 存储过程

## 使用 LINQ 组合 SQL 查询

关于 `SqlQuery` 的一个有趣之处是，它返回的是 `IQueryable`，可以进一步使用 **LINQ** 组合。

在调用 `SqlQuery` 后你可以添加一个 `Where` 语句：

```csharp
var startDate = new DateOnly(2023, 1, 1);

var ordersIn2023 = await dbContext
    .Database
    .SqlQuery<OrderSummary>("SELECT * FROM OrderSummaries AS o")
    .Where(o => o.CreatedOn >= startDate)
    .ToListAsync();
```

然而，生成的 **SQL** 并不是最优的：

```sql
SELECT s.Id, s.CustomerId, s.TotalPrice, s.CreatedOn
FROM (
    SELECT * FROM OrderSummaries AS o
) AS s
WHERE s.CreatedOn >= @p0
```

另一种可能性是结合使用 `OrderBy` 语句与 `Skip` 和 `Take`：

```csharp
var startDate = new DateOnly(2023, 1, 1);

var ordersIn2023 = await dbContext
    .Database
    .SqlQuery<OrderSummary>(
        $"SELECT * FROM OrderSummaries AS o WHERE o.CreatedOn >= {startDate}")
    .OrderBy(o => o.Id)
    .Skip(10)
    .Take(5)
    .ToListAsync();
```

对于上一个查询，这将是生成的 **SQL**：

```sql
SELECT s.Id, s.CustomerId, s.TotalPrice, s.CreatedOn
FROM (
    SELECT * FROM OrderSummaries AS o WHERE o.CreatedOn >= @p0
) AS s
ORDER BY s.Id
OFFSET @p1 ROWS FETCH NEXT @p2 ROWS ONLY
```

如果你想知道，性能与使用 `Select` 投影的 **LINQ** 查询相似。

我运行了一些基准测试，没有注意到任何显著的性能改进。

如果你更喜欢写 **SQL** 或者你想从视图、函数和存储过程获取数据，这个功能将非常有用。

## 使用 SQL 查询进行数据修改

如果你想用 **SQL** 修改数据库中的数据，通常会写一个不返回结果的查询。

SQL 查询可以是一个 `UPDATE` 或 `DELETE` 语句，甚至是一个存储过程调用。

你可以使用 `ExecuteSql` 方法与 **EF Core** 执行这类查询：

```csharp
var startDate = new DateOnly(2023, 1, 1);

dbContext.Database.ExecuteSql(
    $"UPDATE Orders SET Status = 5 WHERE CreatedOn >= {startDate}");
```

`ExecuteSql` 也通过参数化参数防止 SQL 注入，就像 `SqlQuery` 一样。

在 **EF7** 中，你可以使用 **LINQ** 和 `ExecuteUpdate` 方法编写上述查询。还有 `ExecuteDelete` 方法用于删除记录。

## 总结

**EF7** 引入了返回**标量**值的原生 SQL 查询的支持。

**EF8** 将增加对使用 `SqlQuery` 和 `SqlQueryRaw` 返回**未映射类型**的**原生 SQL 查询**的支持。

我喜欢 **EF** 正在走的方向，为查询数据库引入更多的灵活性。

性能不如 **Dapper**，遗憾。但它足够接近，网络成本将成为更大的因素。

我可能将来只会使用 **EF**，因为它覆盖了更多的用例。
