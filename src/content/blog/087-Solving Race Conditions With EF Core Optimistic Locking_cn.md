---
pubDatetime: 2024-04-06
tags: []
source: https://www.milanjovanovic.tech/blog/solving-race-conditions-with-ef-core-optimistic-locking
author: Milan Jovanović
title: 使用 EF Core 乐观锁解决竞态条件
description: 编写代码时，你有多频繁地考虑并发冲突？
  你为一个新功能编写代码，确认它工作正常，然后就此打住。
  但是一周后，你发现自己引入了一个恶劣的错误，因为你没有考虑并发。
  最常见的问题是两个竞争线程执行相同功能的竞态条件。如果在开发过程中不考虑这一点，就会引入使系统处于损坏状态的风险。
---

# 使用 EF Core 乐观锁解决竞态条件

> 原文链接 [Solving Race Conditions With EF Core Optimistic Locking](https://www.milanjovanovic.tech/blog/solving-race-conditions-with-ef-core-optimistic-locking)

编写代码时，你有多频繁地考虑并发冲突？

你为一个新功能编写代码，确认它工作正常，然后就此打住。

但是一周后，你发现自己引入了一个恶劣的错误，因为你没有考虑并发。

最常见的问题是两个竞争线程执行相同功能的竞态条件。如果在开发过程中不考虑这一点，就会引入使系统处于损坏状态的风险。

然后，我会向你展示如何使用 EF Core 乐观并发来解决这一竞态条件。

## 这段代码有什么问题？

这段代码片段中隐藏着一个竞态条件。

你看出来了吗？

```csharp
public Result<Guid> Handle(
    ReserveBooking command,
    AppDbContext dbContext)
{
    var user = dbContext.Users.GetById(command.UserId);
    var apartment = dbContext.Apartments.GetById(command.ApartmentId);
    var (startDate, endDate) = command;

    if (dbContext.Bookings.IsOverlapping(apartment, startDate, endDate))
    {
        return Result.Failure<Guid>(BookingErrors.Overlap);
    }

    var booking = Booking.Reserve(apartment, user, startDate, endDate);

    dbContext.Add(booking);

    dbContext.SaveChanges();

    return booking.Id;
}
```

调用 `IsOverlapping` 是一个乐观的检查，以查看是否存在指定日期的预订。

```csharp
if (dbContext.Bookings.IsOverlapping(apartment, startDate, endDate)) { }
```

如果它返回 `true`，我们尝试对公寓进行重复预订。因此，我们返回失败，并且方法完成。

但如果它返回 `false`，我们保留预订并调用 `SaveChanges` 将更改保存到数据库中。

问题就在这里。

存在并发请求通过 `IsOverlapping` 检查并尝试预留预订的机会。没有任何并发控制，两个请求都将成功，我们将在数据库中遇到不一致的状态。

那么我们如何解决这个问题？

## 使用 EF Core 的乐观并发

悲观并发方法在修改数据之前为数据获取锁。这种方法更慢，并导致竞争事务被阻塞，直到释放锁。EF Core 默认不支持这种方法。

你也可以使用 EF Core 的乐观并发来解决这个问题。它不会锁定任何数据，但如果自查询以来数据已更改，则任何数据修改都将无法保存。

要在 EF Core 中实现乐观并发，你需要将某个属性配置为*并发令牌*。它随实体一起加载和跟踪。当你调用 `SaveChanges` 时，EF Core 将比较并发令牌的值与数据库中的值。

假设我们使用的是 SQL Server，它具有原生的 [`rowversion`](https://learn.microsoft.com/en-us/sql/t-sql/data-types/rowversion-transact-sql?view=sql-server-ver16) 列。`rowversion` 在行更新时自动变化，因此它是并发令牌的绝佳选项。

要将 `byte[]` 属性配置为并发令牌，你可以用 `Timestamp` 属性装饰它。它将在 SQL Server 中映射为 `rowversion` 列。

```csharp
public class Apartment
{
    public Guid Id { get; set; }

    [Timestamp]
    public byte[] Version { get; set; }
}
```

我更喜欢另一种方法，因为属性会污染实体。

你可以使用 Fluent API 做到相同的事情。我甚至会使用阴影属性来从实体类中隐藏并发令牌。

```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Apartment>()
        .Property<byte[]>("Version")
        .IsRowVersion();
}
```

准确的配置将根据你所使用的数据库而有所不同，因此请检查文档。

## 乐观并发实际如何工作

当我们配置了并发令牌后，情况就发生了变化。

加载 `Apartment` 实体时，EF 也将加载并发令牌。

```sql
SELECT a.Id, a.Version
FROM Apartments a
WHERE a.Id = @p0
```

当我们调用 `SaveChanges` 时，更新语句将比较并发令牌的值与数据库中的值：

```sql
UPDATE Apartments a
SET a.LastBookedOnUtc = @p0
WHERE a.Id = @p1 AND a.Version = @p2;
```

如果数据库中的 `rowversion` 发生变化，更新的行数将为 `0`。

EF Core 期望更新 `1` 行，因此它将抛出 `DbUpdateConcurrencyException`，你需要处理这个异常。

## 处理并发异常

现在你知道了如何使用 EF Core 的乐观并发，你可以修复之前的代码片段。

如果两个并发请求通过了 `IsOverlapping` 检查，只有一个能完成 `SaveChanges` 调用。另一个并发请求将在数据库中遇到 `Version` 不匹配并抛出 `DbUpdateConcurrencyException`。

在出现并发冲突的情况下，我们需要添加一个 `try-catch` 语句来捕获 `DbUpdateConcurrencyException`。如何处理实际异常取决于你的业务需求。有时候，[竞态条件](https://go.particular.net/milanjovanovic/raceconditions)甚至可能不存在。

```csharp
public Result<Guid> Handle(
    ReserveBooking command,
    AppDbContext dbContext)
{
    var user = dbContext.Users.GetById(command.UserId);
    var apartment = dbContext.Apartments.GetById(command.ApartmentId);
    var (startDate, endDate) = command;

    if (dbContext.Bookings.IsOverlapping(apartment, startDate, endDate))
    {
        return Result.Failure<Guid>(BookingErrors.Overlap);
    }

    try
    {
        var booking = Booking.Reserve(apartment, user, startDate, endDate);

        dbContext.Add(booking);

        dbContext.SaveChanges();

        return booking.Id;
    }
    catch (DbUpdateConcurrencyException)
    {
        return Result.Failure<Guid>(BookingErrors.Overlap);
    }
}
```

## 什么时候应该使用乐观并发？

乐观并发认为最佳场景也是最有可能的场景。它假设事务之间的冲突将不频繁，并不会在数据上获取锁。这意味着你的系统可以更好地扩展，因为没有阻塞减慢性能。

然而，你仍然需要预期并发冲突，并实施自定义逻辑来处理它们。

如果你的应用程序预期冲突不会太多，使用乐观并发是个好选择。

另一个使用乐观并发的理由是，当你不能在事务的整个长度上持有数据库的打开连接时。这对于悲观锁定是必需的。
