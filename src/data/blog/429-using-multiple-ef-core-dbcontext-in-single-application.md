---
pubDatetime: 2025-08-11
tags:
  ["EF Core", "DbContext", ".NET", "Entity Framework", "Database Architecture"]
slug: using-multiple-ef-core-dbcontext-in-single-application
source: https://www.milanjovanovic.tech/blog/using-multiple-ef-core-dbcontext-in-single-application
title: 在单个应用中使用多个 EF Core DbContext
description: 深入解析在单个 .NET 应用中使用多个 EF Core DbContext 的动机、实现方式、常见限制与最佳实践，包括不同数据库架构、读写分离以及性能优化等实战场景。
---

---

# 在单个应用中使用多个 EF Core DbContext

## 为什么要使用多个 DbContext

在多数 .NET 应用中，我们往往只使用一个 `DbContext` 来管理与数据库的交互。但在一些特定场景下，使用多个 DbContext 不仅是可行的，还能带来架构与性能上的好处。

**1. 多数据库支持**
当应用需要同时访问多个 SQL 数据库时，必须为每个数据库配置独立的 `DbContext`，从而实现物理上的连接隔离。

**2. 分离关注点**
复杂领域模型的应用中，可以将不同的业务域拆分到多个 `DbContext` 中。例如，`CatalogDbContext` 负责商品目录，而 `OrderDbContext` 处理订单与交易，从而降低模型复杂度。

**3. 模块化单体架构（Modular Monolith）**
通过为每个模块分配单独的数据库 Schema，可以在物理数据库层面实现逻辑隔离，有助于模块间的独立演化。

**4. 读写分离与性能优化**
在高并发场景下，可为只读操作配置访问数据库只读副本的 `DbContext`，并通过设置 `QueryTrackingBehavior.NoTracking` 提升查询性能。

---

## 如何在单个应用中配置多个 DbContext

以下示例展示了如何在一个应用中同时配置 `CatalogDbContext` 与 `OrderDbContext`，它们共享同一个数据库，但使用不同的 Schema。

```csharp
public class CatalogDbContext : DbContext
{
    public DbSet<Product> Products { get; set; }
    public DbSet<Category> Categories { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasDefaultSchema("catalog");
    }
}

public class OrderDbContext : DbContext
{
    public DbSet<Order> Orders { get; set; }
    public DbSet<LineItem> LineItems { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasDefaultSchema("order");
    }
}
```

在 `Startup` 或依赖注入配置中注册多个 DbContext：

```csharp
services.AddDbContext<CatalogDbContext>(options =>
    options.UseSqlServer("CONNECTION_STRING"));

services.AddDbContext<OrderDbContext>(options =>
    options.UseSqlServer("CONNECTION_STRING"));
```

若使用不同的 Schema，还需为迁移历史表单独指定 Schema：

```csharp
services.AddDbContext<CatalogDbContext>(options =>
    options.UseSqlServer(
        "CONNECTION_STRING",
        o => o.MigrationsHistoryTable(
            HistoryRepository.DefaultTableName,
            "catalog")));

services.AddDbContext<OrderDbContext>(options =>
    options.UseSqlServer(
        "CONNECTION_STRING",
        o => o.MigrationsHistoryTable(
            HistoryRepository.DefaultTableName,
            "order")));
```

---

## 多 DbContext 的限制与注意事项

1. **跨 DbContext 不能直接 Join**
   EF Core 无法在两个不同的 `DbContext` 间执行直接连接查询，即便它们指向同一数据库。

2. **事务管理需共享连接**
   仅当多个 DbContext 连接同一数据库时，事务才能共享。需要通过 `UseTransaction` 手动共享事务对象。

3. **迁移历史表 Schema 不自动继承**
   必须显式调用 `MigrationsHistoryTable` 指定迁移历史表的位置，否则 EF Core 会使用默认 Schema。

---

## 多 DbContext 带来的好处

- **更好的关注点分离**：业务代码更清晰，数据访问逻辑更易维护。
- **性能提升**：减少无关数据跟踪，提高并发性能。
- **更精细的安全控制**：为不同 DbContext 配置不同的权限策略。

在构建复杂、可扩展的 .NET 应用时，恰当利用多个 DbContext 能有效提升架构灵活性与可维护性。
