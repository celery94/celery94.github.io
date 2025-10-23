---
pubDatetime: 2025-08-27
tags: ["Productivity", "Tools", "Database"]
slug: ef-core-10-named-query-filters-multiple-filters-per-entity
source: https://www.milanjovanovic.tech/blog/named-query-filters-in-ef-10-multiple-query-filters-per-entity
title: EF Core 10 中的命名查询过滤器：每个实体支持多个查询过滤器
description: EF Core 10 引入了命名查询过滤器功能，允许为单个实体附加多个过滤器并按名称管理，解决了长期以来每个实体只能有一个过滤器的限制。
---

Entity Framework Core 的全局查询过滤器一直是为实体的所有查询自动应用通用条件的便捷方式。它们在[软删除](https://www.milanjovanovic.tech/blog/implementing-soft-delete-with-ef-core)和[多租户](https://www.milanjovanovic.tech/blog/multi-tenant-applications-with-ef-core)等场景中特别有用，您希望为每个查询自动添加相同的 `WHERE` 子句。

然而，EF Core 之前的版本存在一个重大限制：每个实体类型只能定义一个过滤器。如果您需要组合多个条件（例如，软删除和租户隔离），您要么必须编写显式的 `&&` 表达式，要么在特定查询中手动禁用和重新应用过滤器。

EF 10 改变了这一切。新的命名查询过滤器功能允许您为单个实体附加多个过滤器并按名称引用它们。然后您可以根据需要禁用单个过滤器，而不是一次性关闭所有过滤器。

让我们探索这个新功能，了解它为什么重要，以及一些实际的使用方法。

## 什么是查询过滤器？

如果您已经使用 EF Core 一段时间，您可能已经熟悉[全局查询过滤器](https://learn.microsoft.com/en-us/ef/core/querying/filters)。查询过滤器是 EF 自动应用于特定实体类型的所有查询的条件。在底层，EF 会在查询该实体时添加一个 `WHERE` 子句。典型用途包括：

• **软删除**：过滤掉 IsDeleted 为 true 的行，这样已删除的记录默认不会出现在查询中
• **多租户**：按 TenantId 过滤，使每个租户只能看到自己的数据

例如，软删除过滤器可能这样配置：

```csharp
modelBuilder.Entity<Order>()
    .HasQueryFilter(order => !order.IsDeleted);
```

启用过滤器后，`Orders` 上的每个查询都会自动排除软删除的记录。要包含已删除的数据（比如用于管理员报告），您可以在查询上调用 `IgnoreQueryFilters()`。缺点是该实体上的所有过滤器都会被禁用，这可能会意外泄露您不打算显示的数据。

## 使用多个查询过滤器

到目前为止，EF 每个实体只允许一个查询过滤器。如果您在同一个实体上调用 `HasQueryFilter` 两次，第二次调用会覆盖第一次。要组合过滤器，您必须使用 `&&` 编写单个表达式：

```csharp
modelBuilder.Entity<Order>()
    .HasQueryFilter(order => !order.IsDeleted && order.TenantId == tenantId);
```

这种方法有效，但无法选择性地禁用一个条件。`IgnoreQueryFilters()` 会禁用两个条件，迫使您手动重新应用仍需要的过滤器。EF 10 引入了更好的替代方案：命名查询过滤器。

要为实体附加多个过滤器，请使用名称调用 `HasQueryFilter`：

```csharp
modelBuilder.Entity<Order>()
    .HasQueryFilter("SoftDeletionFilter", order => !order.IsDeleted)
    .HasQueryFilter("TenantFilter", order => order.TenantId == tenantId);
```

在底层，EF 创建由您提供的名称标识的单独过滤器。现在您可以只关闭软删除过滤器，同时保持租户过滤器：

```csharp
// 返回当前租户的所有订单（包括软删除的）
var allOrders = await context.Orders.IgnoreQueryFilters(["SoftDeletionFilter"]).ToListAsync();
```

如果您省略参数数组，`IgnoreQueryFilters()` 会禁用该实体的所有过滤器。

## 提示：为过滤器名称使用常量

命名过滤器使用字符串键。在整个代码库中硬编码这些名称容易引入拼写错误和脆弱的魔法字符串。为避免这种情况，请为过滤器名称定义常量或枚举，并在需要的地方重复使用它们。例如：

```csharp
public static class OrderFilters
{
    public const string SoftDelete = nameof(SoftDelete);
    public const string Tenant = nameof(Tenant);
}

modelBuilder.Entity<Order>()
    .HasQueryFilter(OrderFilters.SoftDelete, order => !order.IsDeleted)
    .HasQueryFilter(OrderFilters.Tenant, order => order.TenantId == tenantId);

// 稍后在您的查询中
var allOrders = await context.Orders.IgnoreQueryFilters([OrderFilters.SoftDelete]).ToListAsync();
```

在单一位置定义过滤器名称减少了重复并提高了可维护性。另一个最佳实践是将忽略调用包装在扩展方法或存储库中，这样消费者根本不用直接与过滤器名称交互。例如：

```csharp
public static IQueryable<Order> IncludeSoftDeleted(this IQueryable<Order> query)
    => query.IgnoreQueryFilters([OrderFilters.SoftDelete]);
```

这使您的意图明确，并将过滤器逻辑集中在一个地方。

## 总结

EF 10 中命名查询过滤器的引入消除了 EF [全局查询过滤器](https://www.milanjovanovic.tech/blog/how-to-use-global-query-filters-in-ef-core)功能的一个长期限制。您现在可以：

• 为单个实体附加多个过滤器并单独管理它们
• 使用 `IgnoreQueryFilters(["FilterName"])` 在 LINQ 查询中选择性地禁用特定过滤器
• 简化[软删除](https://www.milanjovanovic.tech/blog/implementing-soft-delete-with-ef-core)加[多租户](https://www.milanjovanovic.tech/blog/multi-tenant-applications-with-ef-core)等常见模式，而无需复杂的条件逻辑

命名查询过滤器可以成为保持查询清洁和域逻辑封装的强大工具。

无论您是在构建隔离租户数据的 SaaS 应用程序，还是确保已删除的记录保持隐藏直到您明确需要它们，EF 10 的命名查询过滤器都提供了您一直在等待的灵活性。
