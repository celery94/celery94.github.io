---
pubDatetime: 2025-07-26
tags: ["Productivity", "Tools", "Database"]
slug: ef-core-10-named-query-filters
source: https://www.milanjovanovic.tech/blog/named-query-filters-in-ef-10-multiple-query-filters-per-entity
title: EF Core 10 Named Query Filters：每个实体多条件过滤的新时代
description: 本文详细解读了Entity Framework Core 10最新引入的Named Query Filters特性，展示如何为每个实体配置多个独立过滤器，并结合实际场景分析多过滤器对软删除、多租户等复杂需求的价值与实践技巧。
---

# EF Core 10 Named Query Filters：每个实体多条件过滤的新时代

## EF Core Query Filters 的现状与痛点

Entity Framework Core（EF Core）作为.NET主流ORM，其“全局查询过滤器（Global Query Filters）”功能长期以来极大方便了开发者在全局范围对实体进行统一条件过滤。最常见的用法莫过于软删除（soft delete）和多租户（multi-tenancy）——这些场景都需要在每次查询实体时自动附加条件，如：

```csharp
modelBuilder.Entity<Order>()
    .HasQueryFilter(order => !order.IsDeleted);
```

这种做法下，所有针对Order的查询，都会自动过滤掉IsDeleted为true的记录，实现了“逻辑删除”的效果。同理，多租户方案中会自动附加TenantId的过滤条件，确保数据隔离。

但在EF Core 10之前，**每个实体只能设置一个全局过滤器**。一旦需要软删除+多租户等多重条件时，只能把所有条件写到一个`&&`表达式中。例如：

```csharp
modelBuilder.Entity<Order>()
    .HasQueryFilter(order => !order.IsDeleted && order.TenantId == tenantId);
```

这样做的问题很明显：当某些场景需要临时忽略其中一个过滤条件时，只能调用`IgnoreQueryFilters()`，但会直接禁用所有过滤器，可能导致数据泄露风险。例如，只想查出已删除的数据，却顺带忽略了租户隔离，严重影响安全性和可维护性。

## EF Core 10 的突破：Named Query Filters

EF 10 彻底改变了这一局面，**引入了“Named Query Filters”**（命名查询过滤器），允许在同一个实体上同时定义多个具名过滤器，并且可以在查询时选择性禁用某一个或多个过滤器。

### 配置多个过滤器

通过为`HasQueryFilter`方法传递名字参数，实现为每个实体定义多个独立过滤器：

```csharp
modelBuilder.Entity<Order>()
    .HasQueryFilter("SoftDeletionFilter", order => !order.IsDeleted)
    .HasQueryFilter("TenantFilter", order => order.TenantId == tenantId);
```

这样EF在底层分别存储、维护这些过滤条件。你可以灵活地按需启用或禁用某个过滤器：

```csharp
// 只忽略软删除过滤器，保留租户过滤器
var allOrders = await context.Orders.IgnoreQueryFilters(["SoftDeletionFilter"]).ToListAsync();
```

如果不传参数，`IgnoreQueryFilters()`仍会禁用所有过滤器。

## 代码实践与最佳实践

在实际开发中，直接用字符串作为过滤器名字会带来“魔法字符串”困扰，易出错且难以维护。推荐方式是使用常量或枚举集中管理过滤器名称：

```csharp
public static class OrderFilters
{
    public const string SoftDelete = nameof(SoftDelete);
    public const string Tenant = nameof(Tenant);
}

modelBuilder.Entity<Order>()
    .HasQueryFilter(OrderFilters.SoftDelete, order => !order.IsDeleted)
    .HasQueryFilter(OrderFilters.Tenant, order => order.TenantId == tenantId);
```

查询时亦使用常量，防止拼写错误：

```csharp
var allOrders = await context.Orders.IgnoreQueryFilters([OrderFilters.SoftDelete]).ToListAsync();
```

进一步，可以将“忽略过滤器”操作封装为扩展方法或仓储模式，减少业务代码对具体过滤器名的感知，提高可维护性。例如：

```csharp
public static IQueryable<Order> IncludeSoftDeleted(this IQueryable<Order> query)
    => query.IgnoreQueryFilters([OrderFilters.SoftDelete]);
```

## 场景价值与对比分析

### 多租户+软删除的完美解决方案

在SaaS、多租户系统中，“租户隔离”和“软删除”往往需要同时满足。以往方案，要么通过组合条件让查询表达式越来越复杂，要么临时禁用所有过滤器冒数据风险。EF 10的Named Query Filters极大提升了场景解耦和安全性：

- **高可维护性**：每个过滤条件独立定义、独立管理
- **最小权限原则**：只在需要时临时关闭某个过滤器，安全边界清晰
- **单一职责**：每个过滤器职责分明，便于测试和扩展

### 兼容性与升级建议

由于EF 10引入的新API与旧版本不同，升级前需关注：

- 旧项目若需兼容多过滤场景，建议升级至EF 10，充分利用具名过滤器能力
- 可将原有的复合过滤器表达式逐步迁移到Named Query Filters方案，代码更清晰
- 测试覆盖点应关注多过滤器协作、禁用时的安全性

## 总结与展望

EF Core 10的Named Query Filters突破了单实体只能有一个过滤器的限制，极大提升了复杂业务场景下的灵活性与安全性。对于实现如软删除、多租户、权限过滤等场景提供了官方最佳实践。开发者应优先考虑升级与采用该特性，进一步提升项目的可维护性、扩展性和安全边界。

未来，随着EF生态不断完善，预计Named Query Filters还会与领域事件、审计日志等高级功能深度结合，为企业级应用打下更坚实的基础。

---

**参考与延伸阅读：**

- [EF Core官方文档：全局查询过滤器](https://learn.microsoft.com/en-us/ef/core/querying/filters)
- [如何实现软删除](https://www.milanjovanovic.tech/blog/implementing-soft-delete-with-ef-core)
- [多租户应用与EF Core](https://www.milanjovanovic.tech/blog/multi-tenant-applications-with-ef-core)
- [博客原文：Named Query Filters in EF 10](https://www.milanjovanovic.tech/blog/named-query-filters-in-ef-10-multiple-query-filters-per-entity)
