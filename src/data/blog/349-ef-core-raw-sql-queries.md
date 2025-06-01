---
pubDatetime: 2025-06-01
tags: [EF Core, .NET, 数据库, 后端开发, 性能优化]
slug: ef-core-raw-sql-queries
source: https://www.milanjovanovic.tech/blog/ef-core-raw-sql-queries
title: EF Core 8新特性：原生SQL查询与未映射类型支持全解析
description: 深度解析EF Core 7/8关于原生SQL查询的新特性，涵盖查询未映射类型、LINQ组合SQL、数据修改及性能对比，帮助.NET开发者灵活高效地操作数据库。
---

# EF Core 8新特性：原生SQL查询与未映射类型支持全解析

在.NET领域，Entity Framework Core（简称EF Core）一直是主流的ORM框架之一。随着EF Core 7和即将发布的EF Core 8陆续加入许多令人兴奋的新特性，数据库操作正变得更加灵活和强大。对于关注数据库性能和复杂场景下数据访问的开发者来说，这些变化值得重点关注。

本文将带你系统梳理EF Core 7/8关于原生SQL查询的进化历程，深入解析其对未映射类型的支持，并结合代码示例和实际应用场景，帮助你高效驾驭数据层。👨‍💻

---

## 引言：ORM还是原生SQL？我们可以都要！

许多.NET开发者都有这样的体验：ORM（如EF Core）极大提升了数据访问的便利性，但在复杂查询或性能瓶颈场景下，仍然希望能直接编写高效、可控的原生SQL语句。以往这两者很难兼得——而如今，EF Core正在向Dapper等轻量级ORM靠拢，让“写SQL也能用EF Core”成为现实。

---

## EF7/EF8：原生SQL查询能力全面升级

### 1️⃣ EF7初步支持：标量类型原生SQL查询

自EF Core 7起，开发者可以通过原生SQL查询直接返回标量（scalar）类型数据，而不再局限于实体模型。这意味着你可以利用数据库的计算能力，高效获取统计、汇总等信息。

```csharp
var result = await dbContext.Database
    .SqlQuery<int>("SELECT COUNT(*) FROM Orders")
    .ToListAsync();
```

### 2️⃣ EF8重大突破：支持未映射类型

进入EF Core 8时代，最受欢迎的新特性之一就是——**支持原生SQL查询返回未映射（unmapped）类型**。这让EF Core和Dapper的体验愈发接近，无需为每一个查询结果专门建立实体模型。

#### 示例：直接用自定义类型接收SQL结果

```csharp
public record OrderSummary(int Id, int CustomerId, decimal TotalPrice, DateTime CreatedOn);

var startDate = new DateOnly(2023, 1, 1);
var ordersIn2023 = await dbContext.Database
    .SqlQuery<OrderSummary>(
        $"SELECT * FROM OrderSummaries WHERE CreatedOn >= {startDate}")
    .ToListAsync();
```

> 🔒 `SqlQuery`方法采用字符串插值自动参数化，有效防止SQL注入。

对应生成的SQL如下：

```sql
SELECT * FROM OrderSummaries WHERE CreatedOn >= @p0
```

除了普通表，还可以灵活查询视图(View)、函数(Function)、存储过程(Stored Procedure)等返回结果。

---

## LINQ与原生SQL的完美融合

让人惊喜的是，通过`SqlQuery`返回的是`IQueryable<T>`，你可以在原生SQL结果基础上继续用LINQ进行二次筛选、排序、分页等操作。

#### 示例：SQL+LINQ组合

```csharp
var startDate = new DateOnly(2023, 1, 1);
var pagedOrders = await dbContext.Database
    .SqlQuery<OrderSummary>("SELECT * FROM OrderSummaries")
    .Where(o => o.CreatedOn >= startDate)
    .OrderBy(o => o.Id)
    .Skip(10)
    .Take(5)
    .ToListAsync();
```

生成的SQL：

```sql
SELECT s.Id, s.CustomerId, s.TotalPrice, s.CreatedOn
FROM (
    SELECT * FROM OrderSummaries WHERE CreatedOn >= @p0
) AS s
ORDER BY s.Id
OFFSET @p1 ROWS FETCH NEXT @p2 ROWS ONLY
```

> 📝 虽然这种模式下性能接近LINQ投影查询，但没有明显优势。如果你习惯写SQL，这种方式会非常友好。

---

## 数据库修改也能用原生SQL

不仅仅是查询！如果你需要批量更新或删除数据，EF Core同样支持通过`ExecuteSql`执行任意SQL（如UPDATE/DELETE），并自动参数化保证安全。

#### 示例：批量更新订单状态

```csharp
var startDate = new DateOnly(2023, 1, 1);
dbContext.Database.ExecuteSql(
    $"UPDATE Orders SET Status = 5 WHERE CreatedOn >= {startDate}");
```

> 推荐优先使用`ExecuteUpdate`/`ExecuteDelete`进行LINQ风格操作，但复杂场景可直接用SQL。

---

## 性能对比：与Dapper谁更快？

经实际测试，EF Core 8新的SQL能力在大多数场景下和Dapper性能差距并不大。网络延迟往往是主要瓶颈。对于习惯全栈用EF的团队来说，已经足够实用。

---

## 总结：EF Core 8，为你而来！

- **EF7** 支持原生SQL查询标量数据
- **EF8** 支持直接返回未映射类型
- 支持用LINQ组合原生SQL结果，实现分页、筛选等操作
- 数据修改可安全执行原生SQL

未来的数据访问，将变得更加灵活、高效和安全。你会考虑把Dapper替换成全用EF Core吗？还是会在不同场景灵活切换？欢迎留言讨论你的观点👇

---

> 💬 **你怎么看待EF Core 8这些新变化？你会在实际项目中尝试用原生SQL+LINQ组合吗？欢迎在评论区分享经验，或者转发给你的.NET同事一起探讨！**

---

【参考与延伸阅读】

- [原文链接：EF Core Raw SQL Queries](https://www.milanjovanovic.tech/blog/ef-core-raw-sql-queries)
- [Pragmatic REST APIsNEW](https://www.milanjovanovic.tech/pragmatic-rest-apis?utm_source=article_page)
- [Modular Monolith Architecture](https://www.milanjovanovic.tech/modular-monolith-architecture?utm_source=article_page)
