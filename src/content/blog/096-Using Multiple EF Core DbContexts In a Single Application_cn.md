---
pubDatetime: 2024年4月11日
tags: [C#, efcore]
source: https://www.milanjovanovic.tech/blog/using-multiple-ef-core-dbcontext-in-single-application
author: Milan Jovanović
title: 在单个应用程序中使用多个EF Core DbContext
description: Entity Framework Core（EF Core）是.NET中一个流行的ORM，允许您操作SQL数据库。EF Core使用DbContext，它代表了与数据库的会话，负责跟踪变更、执行数据库操作以及管理数据库连接。
---

> ## 摘录
>
> Entity Framework Core（EF Core）是.NET中一个流行的ORM，允许您处理SQL数据库。EF Core使用DbContext，它代表了与数据库的会话，并负责跟踪变更、执行数据库操作以及管理数据库连接。
>
> 原文 [在单个应用程序中使用多个EF Core DbContext](https://www.milanjovanovic.tech/blog/using-multiple-ef-core-dbcontext-in-single-application)

---

**Entity Framework Core (EF Core)** 是.NET中一个流行的ORM，允许您操作SQL数据库。EF Core使用`DbContext`，它代表了与数据库的会话，并负责跟踪变更、执行数据库操作以及管理数据库连接。

通常情况下，整个应用程序只会有一个`DbContext`。

但是如果您需要使用**多个DbContext**该怎么办？

在本周的通讯中，我们将探讨：

- 何时您可能需要使用多个DbContext
- 如何创建多个DbContext
- 使用多个DbContext的好处是什么

让我们深入了解！

## 为什么使用多个DbContext？

有几种情况下使用**多个DbContext可能是有用的。**

**多数据库**  
您的应用程序需要操作多个SQL数据库吗？然后您被迫使用多个DbContext，每一个都专用于特定的SQL数据库。

**分离关注点**  
如果您构建的应用程序有一个复杂的领域模型，通过在几个DbContext之间分离关注点，您可能会看到改进，每一个都负责领域模型的一个特定区域。

**模块化单体**  
当您构建一个**模块化单体**时，使用多个DbContext是实用的，因为您可以为每个`DbContext`配置不同的**数据库架构**，在数据库级别提供逻辑分离。

**读副本**  
您可以配置一个单独的`DbContext`实例来访问数据库的读副本，并使用该`DbContext`进行只读查询。您还可以在`DbContext`级别配置`QueryTrackingBehavior.NoTracking`以提高查询性能。

## 在单个应用程序中创建多个DbContext

下面是如何轻松配置多个DbContext。假设我们的应用程序中有一个`CatalogDbContext`和一个`OrderDbContext`。我们想使用以下限制来配置它们：

- 两个DbContext使用**相同的数据库**
- 每个DbContext有一个**单独的数据库架构**

```csharp
public class CatalogDbContext : DbContext
{
    public DbSet<Product> Products { get; set; }

    public DbSet<Category> Categories { get; set; }
}

public class OrderDbContext : DbContext
{
    public DbSet<Order> Orders { get; set; }

    public DbSet<LineItem> LineItems { get; set; }
}
```

首先我们需要使用DI容器配置`CatalogDbContext`和`OrderDbContext`。您可以通过调用`AddDbContext`方法并指定正在配置的`DbContext`，然后使用SQL提供者特定方法传递连接字符串来实现。在这个例子中，我使用`UseSqlServer`方法连接到SQL Server。

```csharp
using Microsoft.EntityFrameworkCore;

services.AddDbContext<CatalogDbContext>(options =>
    options.UseSqlServer("CONNECTION_STRING"));

services.AddDbContext<OrderDbContext>(options =>
    options.UseSqlServer("CONNECTION_STRING"));
```

如果您只是想在同一个架构中使用两个DbContext，那么这就是您需要的所有配置。您现在可以在应用程序中注入`DbContext`实例并使用它们。

然而，如果您想为每个`DbContext`配置不同的架构，那么您还需要重写`OnModelCreating`方法并使用`HasDefaultSchema`指定自定义架构。

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

使用多个DbContext的限制：

1. 因为**EF Core**不知道它们是否使用相同的数据库，所以不可能在不同的`DbContext`实例之间进行连接操作。
2. 如果DbContexts使用同一个数据库，那么事务才会起作用。您必须创建一个新的事务并通过[调用`UseTransaction`方法](https://www.milanjovanovic.tech/blog/working-with-transactions-in-ef-core#using-existing-transactions-with-ef-core)在DbContexts之间共享它。

**迁移历史表**

如果您决定为每个`DbContext`使用不同的架构，您会不愉快地发现默认架构不适用于迁移历史表。

您需要通过调用`MigrationsHistoryTable`方法并指定迁移历史将存储的表名和架构来配置这一点。在这个例子中，我使用了`HistoryRepository.DefaultTableName`常量，但如果您想要，也可以指定自定义表名。

```csharp
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Migrations;

services.AddDbContext<CatalogDbContext>(options =>
    options.UseSqlServer(
        "CONNECTION_STRING",
        o => o.MigrationsHistoryTable(
            tableName: HistoryRepository.DefaultTableName,
            schema: "catalog")));

services.AddDbContext<OrderDbContext>(options =>
    options.UseSqlServer(
        "CONNECTION_STRING",
        o => o.MigrationsHistoryTable(
            tableName: HistoryRepository.DefaultTableName,
            schema: "order")));
```

## 使用多个DbContext的好处

使用多个DbContext可以为您的应用程序提供几个好处：

- 关注点分离
- 更好的性能
- 更多的控制权和安全性

每个DbContext可以负责应用程序数据的一个特定子集，这有助于组织代码并使其更加模块化。

当您将数据访问分离到多个DbContext时，应用程序可以减少争用风险并提高并发性，这可以提高性能。

如果您使用多个DbContext，您可以配置更细粒度的访问控制来提高应用程序的安全性。您还可以优化性能和资源使用。

## 总结

在单个应用程序中使用**多个EF Core DbContext**是直接的，并且有许多好处。

对于读取密集型应用程序，您可以配置一个单独的`DbContext`以默认关闭查询跟踪并获得改善的性能。

此外，如果您正在构建一个**模块化单体**，使用多个DbContext是实用的。您可以将DbContexts配置为**不同的数据库架构**，在数据库级别提供逻辑分离。
