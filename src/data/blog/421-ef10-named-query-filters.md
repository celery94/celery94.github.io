---
pubDatetime: 2025-08-07
tags: [".NET", "Database"]
slug: ef10-named-query-filters
source: https://www.milanjovanovic.tech/blog/named-query-filters-in-ef-10-multiple-query-filters-per-entity
title: EF Core 10中的命名查询过滤器：多过滤条件的突破与实践
description: 深入解析Entity Framework 10最新的命名查询过滤器功能，详解其如何支持每个实体多个过滤器，为多租户、软删除等场景带来极大便利，并结合最佳实践进行拓展说明。
---

# EF Core 10中的命名查询过滤器：多过滤条件的突破与实践

Entity Framework Core（EF Core）一直以来以其灵活的数据访问与过滤机制备受开发者青睐。自引入全局查询过滤器（Global Query Filters）以来，开发者可以轻松为实体应用通用的查询条件，例如实现软删除（Soft Delete）和多租户（Multi-Tenancy）场景的数据隔离。

然而，**在EF Core 10之前，所有实体类型每次仅能定义一个全局查询过滤器**。这在复杂业务场景下颇为不便，例如需要同时支持软删除和多租户过滤时，开发者只能将所有条件组合到一个`&&`表达式中，既影响可维护性，也限制了灵活性。

EF Core 10的“命名查询过滤器（Named Query Filters）”功能应运而生。本文将深入解析该特性，分析其核心原理与优势，并结合实际业务场景给出最佳实践和代码示例，帮助你高效实现数据过滤与隔离。

---

## 全局查询过滤器回顾及痛点

在EF Core中，全局查询过滤器通常用于自动为实体查询加上`WHERE`条件，典型应用包括：

- 软删除：默认排除被标记为删除的记录。
- 多租户隔离：确保不同租户只能访问属于自己的数据。

以软删除为例，传统的定义方式如下：

```csharp
modelBuilder.Entity<Order>()
    .HasQueryFilter(order => !order.IsDeleted);
```

当对`Order`进行查询时，EF会自动加上`WHERE [IsDeleted] = 0`条件，无需在每个查询语句中重复添加。

但如果同时需要多租户过滤，只能将条件合并：

```csharp
modelBuilder.Entity<Order>()
    .HasQueryFilter(order => !order.IsDeleted && order.TenantId == tenantId);
```

这种写法存在明显问题：

- 无法单独开启/关闭某个过滤条件，只能全部禁用（通过`.IgnoreQueryFilters()`）。
- 条件复用和代码维护困难，易产生遗漏和安全隐患。

---

## EF Core 10：命名查询过滤器的突破

EF Core 10中引入的“命名查询过滤器”，允许**同一实体定义多个具名过滤条件**，并能在查询时**按需禁用某个或某些过滤器，而不是全部关闭**，极大提升了灵活性和安全性。

### 基本用法

新增的API如下：

```csharp
modelBuilder.Entity<Order>()
    .HasQueryFilter("SoftDeletionFilter", order => !order.IsDeleted)
    .HasQueryFilter("TenantFilter", order => order.TenantId == tenantId);
```

此时，EF会为`Order`实体分别注册“SoftDeletionFilter”和“TenantFilter”两个命名过滤器。

#### 查询时按需禁用过滤器

假如只想临时忽略软删除过滤条件，而保留租户隔离：

```csharp
var allOrders = await context.Orders
    .IgnoreQueryFilters(["SoftDeletionFilter"])
    .ToListAsync();
```

如不指定参数，`IgnoreQueryFilters()`则会禁用全部过滤器（与以往一致）。

---

## 推荐实践：常量化与封装

为避免魔法字符串带来的维护难题，强烈建议**将过滤器名称定义为常量**或枚举，并进行封装：

```csharp
public static class OrderFilters
{
    public const string SoftDelete = nameof(SoftDelete);
    public const string Tenant = nameof(Tenant);
}

modelBuilder.Entity<Order>()
    .HasQueryFilter(OrderFilters.SoftDelete, order => !order.IsDeleted)
    .HasQueryFilter(OrderFilters.Tenant, order => order.TenantId == tenantId);

// 查询扩展方法
public static IQueryable<Order> IncludeSoftDeleted(this IQueryable<Order> query) =>
    query.IgnoreQueryFilters([OrderFilters.SoftDelete]);
```

这种做法既提升了可读性，也便于集中管理过滤逻辑，避免因拼写错误导致的难查bug。

---

## 深入拓展：应用场景与对比分析

### 多过滤条件的最佳落地场景

1. **SaaS多租户应用**
   使用命名过滤器可以轻松为数据实现“租户隔离”与“软删除”双重防护，同时保障业务数据安全和可追溯性。

2. **数据敏感性处理**
   可为实体增加敏感数据过滤（如：仅显示审核通过的数据），并根据业务场景灵活启用/禁用。

3. **审计与多状态业务流程**
   针对复杂状态流转的实体，可以为每种状态单独定义命名过滤器，使得查询更灵活、业务更清晰。

### 与传统全局过滤的对比

| 特性             | 传统全局过滤器     | 命名查询过滤器（EF 10） |
| ---------------- | ------------------ | ----------------------- |
| 每实体可过滤数量 | 1                  | 多个                    |
| 过滤条件组合     | 必须合并成单表达式 | 各自独立，便于维护      |
| 查询时禁用灵活性 | 全部禁用           | 可逐项选择禁用          |
| 适用场景         | 简单单一条件过滤   | 复杂、多维度业务需求    |
| 安全性           | 较低（易漏或全关） | 更高，细粒度控制        |

---

## 总结与前瞻

EF Core 10的命名查询过滤器，完美解决了以往全局过滤器“一刀切”的缺陷，让开发者能针对每个业务维度定义、管理和动态控制过滤规则。无论是多租户隔离、软删除，还是更加复杂的数据筛选场景，这一特性的落地都将极大提升EF项目的数据安全性、可维护性与扩展性。

对于大型SaaS系统、数据安全敏感型项目或需要高可维护性的数据访问层，建议尽早升级并充分利用EF 10命名查询过滤器，打造更健壮和灵活的数据访问架构。

---

**参考链接：**

- [官方文档：EF Core Query Filters](https://learn.microsoft.com/en-us/ef/core/querying/filters)

如果你希望更深入学习.NET领域的架构模式、数据访问优化，推荐关注相关课程与社区动态。让我们共同迎接EF Core 10时代的高效与创新！

---
