---
pubDatetime: 2024-04-11
tags: ["Productivity", "Tools"]
source: https://www.milanjovanovic.tech/blog/working-with-transactions-in-ef-core#using-existing-transactions-with-ef-core
author: Milan Jovanović
title: 在 EF Core 中处理事务
description: 每位与 SQL 数据库打交道的软件工程师都需要了解事务。由于大部分时间SQL数据库会被像EF Core这样的ORM抽象出来，因此理解如何使用可用的抽象来处理事务变得十分重要。
---

> ## 摘要
>
> 每位与 SQL 数据库打交道的软件工程师都需要了解事务。由于大部分时间SQL数据库会被像EF Core这样的ORM抽象出来，因此理解如何使用可用的抽象来处理事务变得十分重要。
>
> 原文 [在 EF Core 中处理事务](https://www.milanjovanovic.tech/blog/working-with-transactions-in-ef-core#using-existing-transactions-with-ef-core)

---

每位与 **SQL数据库** 打交道的软件工程师都需要了解**事务**。既然大部分时间**SQL数据库**会被像**EF Core**这样的ORM抽象化，理解如何使用可用的抽象来处理**事务**就非常重要了。

所以今天，我将向你展示如何在 **EF Core** 中处理**事务**。

这里是我们将要覆盖的内容：

- 默认事务行为
- 创建事务
- 使用现有事务

让我们深入了解。

## 默认事务行为

什么是 **EF Core** 中的**默认**事务**行为**？

默认情况下，对`SaveChanges`的单次调用中所做的所有更改都将在一个事务中应用。如果其中的任何更改失败，整个事务将被回滚，不会对数据库应用任何更改。只有当所有更改都成功持久化到数据库时，对`SaveChanges`的调用才能完成。

这是 **SQL数据库** 的一个绝佳特性，它为我们解决了许多头痛问题。我们不必担心数据库保持在不一致的状态，因为数据库**事务**可以为我们做这项工作。

让我们来看一个例子。

```csharp
using var context = new ShoppingContext();

context.LineItems.Add(new LineItem
{
    ProductId = productId,
    Quantity = quantity
});

var stock = context.Stock.FirstOrDefault(s => s.ProductId == productId);

stock.Quantity -= quantity;

context.SaveChanges();
```

因为我们在添加一个`LineItem`，并在同一作用域内减少了`Stock`数量，所以对`SaveChanges`的调用将在一个事务内应用这两个更改。我们可以保证数据库将保持在一个**一致的状态**。

## 使用 EF Core 创建事务

如果你想在使用 **EF Core** 时对**事务**有更多的控制怎么办？

你可以通过访问`DbContext`实例上可用的`Database`门面并调用`BeginTransaction`手动创建一个事务。

这里有一个例子，我们有多次对`SaveChanges`的调用。在默认情况下，这两次调用将在它们自己的事务中运行。这留下了第二次对`SaveChanges`的调用失败并使数据库处于不一致状态的可能性。

```csharp
using var context = new ShoppingContext();
using var transaction  = context.Database.BeginTransaction();

try
{
    context.LineItems.Add(new LineItem
    {
        ProductId = productId,
        Quantity = quantity
    });

    context.SaveChanges();

    var stock = context.Stock.FirstOrDefault(s => s.ProductId == productId);

    stock.Quantity -= quantity;

    context.SaveChanges();

    // 当我们提交更改时，它们将被应用到数据库。
    // 如果任何命令失败，事务将自动回滚。
    transaction.Commit();
}
catch (Exception)
{
    transaction.Rollback();
}
```

我们调用`BeginTransaction`来手动开始一个新的**数据库事务**。这将创建一个新的事务并返回它，以便我们在完成操作时可以`Commit`事务。你还想在代码周围添加一个`try-catch`块，以便在发生任何异常时可以`Rollback`事务。

## 在 EF Core 中使用现有事务

使用EF Core `DbContext`创建事务并不是唯一的选项。你可以创建一个`SqlTransaction`实例并将其传递给**EF Core**，这样EF Core应用的更改就可以在相同的**事务**中被提交了。

这是我的意思：

```csharp
using var sqlConnection = new SqlTransaction(connectionString);
sqlConnection.Open();

using var transaction = sqlConnection.BeginTransaction();

try
{
    using var context = new ShoppingContext();

    // 告诉EF Core使用一个现有的事务。
    context.UseTransaction(transaction);

    context.LineItems.Add(new LineItem
    {
        ProductId = productId,
        Quantity = quantity
    });

    context.SaveChanges();

    var stock = context.Stock.FirstOrDefault(s => s.ProductId == productId);

    stock.Quantity -= quantity;

    context.SaveChanges();

    transaction.Commit();
}
catch (Exception)
{
    transaction.Rollback();
}
```

## 总结

**EF Core** 对**事务**有出色的支持，使用起来非常简单。

你有三种可用的选项：

- 依赖默认事务行为
- 创建一个新事务
- 使用一个现有事务

大多数时候，你想依赖默认行为而不必考虑太多。

一旦你需要执行多次`SaveChanges`调用，你应该手动创建一个事务，并自己管理该事务。

下周见，祝你有一个美好的星期六。

---
