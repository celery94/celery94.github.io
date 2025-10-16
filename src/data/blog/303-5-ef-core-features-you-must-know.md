---
pubDatetime: 2025-05-05
tags: [".NET", "Database"]
slug: 5-ef-core-features-you-must-know
source: https://www.milanjovanovic.tech/blog/5-ef-core-features-you-need-to-know?utm_source=X&utm_medium=social&utm_campaign=05.05.2025
title: 你必须掌握的5个EF Core特性：.NET开发者高效进阶指南
description: 深入解析EF Core中五大关键特性，助力.NET开发者提升数据访问性能与开发效率，解决日常开发痛点，迈向中高级工程师进阶。
---

# 你必须掌握的5个EF Core特性：.NET开发者高效进阶指南

> 面向.NET开发者，特别是关注性能与效率的中高级程序员，这五个EF Core核心特性值得你花时间深入理解和实践！

## 引言

在日常.NET开发中，Entity Framework Core（简称EF Core）已经成为数据访问层的首选ORM。但你是否觉得，有时候数据操作“不够快”？又或是写了很多重复、低效的代码？其实，EF Core不断更新，已经内置了许多高效、实用的特性。  
本篇文章将带你梳理5个最值得关注的EF Core特性，帮你轻松应对复杂业务与性能瓶颈，让你的代码更优雅、运行更高效！🚀

---

## 一、Query Splitting：解决笛卡尔积爆炸，优化多集合预加载

有时，我们需要一次性加载实体及其多个集合导航属性，比如部门下的所有团队和员工。此时如果直接JOIN多张表，极易出现**笛卡尔积爆炸**问题，导致返回大量冗余数据，严重影响性能。

**传统写法：**

```csharp
var departments = dbContext.Departments
    .Include(d => d.Teams)
    .ThenInclude(t => t.Employees)
    .ToList();
```

这会生成单条SQL，但JOIN同级集合时结果集膨胀。

**Query Splitting优化：**

```csharp
var departments = dbContext.Departments
    .Include(d => d.Teams)
    .Include(d => d.Employees)
    .AsSplitQuery()
    .ToList();
```

`AsSplitQuery()`让EF Core为每个集合导航分别执行SQL，有效避免笛卡尔积。

⚠️ 需注意：Split Query会增加数据库往返次数，不适合高延迟场景，建议在性能分析后合理使用。

---

## 二、Bulk Updates & Deletes：批量更新/删除，大幅提升性能

EF Core 7起原生支持批量操作，新增`ExecuteUpdate`与`ExecuteDelete`方法，无需加载实体到内存，即可批量处理数据。

**示例：为Sales部门所有员工加薪5%**

```csharp
dbContext.Employees
    .Where(e => e.Department == "Sales")
    .ExecuteUpdate(e => e.SetProperty(emp => emp.Salary, emp => emp.Salary * 1.05));
```

只发出一次SQL命令，无需循环+保存，大型数据集下性能提升巨大！

**批量删除购物车：**

```csharp
dbContext.ShoppingCarts
    .Where(cart => cart.CreatedAt < DateTime.Now.AddYears(-1))
    .ExecuteDelete();
```

注意：这类操作**绕过了EF的ChangeTracker**，不会自动同步到DbContext中已追踪的实体，需要开发者手动处理缓存一致性。

---

## 三、Raw SQL Queries：强大原生SQL，灵活查询未映射类型

有时，我们需要从视图、存储过程或无实体映射的表获取数据。EF Core 8引入了更安全灵活的`SqlQuery`方法，可直接查询自定义类型：

```csharp
public class ProductSummary { public string Name; public int TotalSales; }

var summaries = dbContext.Database.SqlQuery<ProductSummary>(
    $"SELECT Name, SUM(Sales) AS TotalSales FROM SalesView GROUP BY Name"
);
```

- 支持LINQ组合过滤
- 参数化防止SQL注入（使用插值字符串）

适合复杂报表、聚合场景，兼具性能与灵活性。

---

## 四、Query Filters：全局条件过滤，轻松实现多租户/软删除

经常遇到类似“每次都要写租户过滤/软删除条件”的尴尬？`Query Filters`让你一次定义，全局生效！

**多租户过滤示例：**

```csharp
modelBuilder.Entity<Order>().HasQueryFilter(o => o.TenantId == currentTenantId);
```

以后对Order表的所有LINQ查询都会自动追加此条件，彻底摆脱重复where语句。

- 多个过滤器可用`&&`/`||`组合
- 特殊场景可用`IgnoreQueryFilters()`绕开全局过滤

---

## 五、Eager Loading：一次查询拿全相关数据

当需要同时操作主实体和其导航属性（如同时验证用户及其邮箱），用Eager Loading的`Include`方法能一次查全所需数据：

```csharp
var token = dbContext.EmailVerificationTokens
    .Include(t => t.User)
    .FirstOrDefault(t => t.Token == tokenValue);
```

避免多次数据库往返或N+1查询问题。  
⚠️ 若只需部分字段，可考虑投影（Select new）减少不必要的数据加载。

---

## 结语：精通EF Core，从掌握这些特性开始！

掌握这五大特性，将极大提升你的EF Core实际战斗力！记住：

- 性能优化先分析场景再用“神器”
- 灵活运用批量操作与原生SQL
- 全局过滤让代码更优雅可维护

EF Core在持续进化，关注官方文档和社区动态，不断吸收新技术，才能成为顶尖的.NET数据高手！

---

👀 你还遇到过哪些EF Core“坑”或者有实战技巧想分享？欢迎在评论区留言交流！  
👍 如果觉得有帮助，别忘了点赞+转发，让更多.NET同僚受益！
