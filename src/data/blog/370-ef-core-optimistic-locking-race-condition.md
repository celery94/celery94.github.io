---
pubDatetime: 2025-06-18
tags: [EF Core, 并发控制, 乐观锁, .NET, 软件架构]
slug: ef-core-optimistic-locking-race-condition
source: https://www.milanjovanovic.tech/blog/solving-race-conditions-with-ef-core-optimistic-locking
title: 使用 EF Core 乐观锁定机制解决并发冲突与竞态条件
description: 本文面向中高级 .NET 开发者，系统讲解了在实际开发中如何识别并解决并发冲突，详细解析 EF Core 乐观并发控制的原理、应用及代码实现，并结合典型场景分析其优势与挑战，帮助开发者构建健壮可靠的业务系统。
ogImage: "@/assets/cover/370.png"
---

# 使用 EF Core 乐观锁定机制解决并发冲突与竞态条件

## 引言

在企业级应用开发中，数据一致性与并发安全始终是软件架构设计的核心问题之一。尤其是在多线程或高并发环境下，**竞态条件（Race Condition）**极易导致业务逻辑混乱甚至数据损坏。以预订系统为例，如果不恰当处理并发访问，可能会出现同一房源被多次预订的严重错误。本文将结合真实代码示例，深入剖析如何利用 **Entity Framework Core（EF Core）** 的乐观并发控制机制，有效防止此类竞态问题，提升系统健壮性。

## 并发冲突与竞态条件：背景及问题分析

并发冲突指多个线程或请求同时访问和修改同一份数据时，由于缺乏合理的同步机制，导致数据状态异常。在现实开发中，开发者经常忽略这类隐蔽风险。例如，假设有如下预订处理逻辑：

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

**问题分析：**  
上面代码虽然做了重叠预订检查，但在高并发场景下，两次请求可能几乎同时通过 `IsOverlapping` 检查，然后各自插入预订，造成业务冲突。这种“先查询后更新”的模式在没有并发控制的情况下无法保证数据一致性。

## 乐观并发控制原理及 EF Core 实现

针对上述问题，常见的解决方案包括**悲观锁定**和**乐观锁定**：

- **悲观锁定（Pessimistic Locking）**：对关键资源加锁，阻塞其他并发操作。实现简单但性能低下，EF Core 原生不支持。
- **乐观锁定（Optimistic Locking）**：假定冲突较少，不主动加锁。提交时校验关键字段（如版本号），发现数据已变更则拒绝保存。适合高吞吐、高可扩展场景。

EF Core 支持乐观并发控制，只需为实体配置“并发标记（Concurrency Token）”，如 SQL Server 的 `rowversion` 字段。

### 实体配置方式

1. **属性注解方式**

```csharp
public class Apartment
{
    public Guid Id { get; set; }

    [Timestamp]
    public byte[] Version { get; set; }
}
```

2. **Fluent API 方式（推荐，避免污染实体模型）**

```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    modelBuilder.Entity<Apartment>()
        .Property<byte[]>("Version")
        .IsRowVersion();
}
```

> ⚠️ 不同数据库对并发控制字段支持方式不同，请查阅对应文档。

### 工作机制详解

当启用乐观锁后：

- 查询实体时会一同加载并发标记（如 `Version`）。
- 更新或插入时，EF Core 生成带有版本号校验的 SQL 语句。例如：

```sql
UPDATE Apartments
SET LastBookedOnUtc = @p0
WHERE Id = @p1 AND Version = @p2;
```

- 若期间其他请求已修改该实体，则 `Version` 不匹配，无行被更新，EF Core 抛出 `DbUpdateConcurrencyException`。

### 代码实现与异常处理

改进后的预订处理如下：

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
        // 并发冲突时返回重叠错误
        return Result.Failure<Guid>(BookingErrors.Overlap);
    }
}
```

通过捕获并处理 `DbUpdateConcurrencyException`，确保即使极端并发场景下，也不会出现重复预订等业务异常。

## 乐观并发控制的适用场景与挑战

**优势：**

- 性能优异，无需长时间持有数据库连接。
- 避免大范围阻塞，适合大部分高并发 Web 应用。
- 与 DDD、CQRS 等架构理念高度契合。

**挑战：**

- 并发冲突需业务层显式处理，如重试、用户提示等。
- 在极高冲突概率场景下（如金融系统），需谨慎评估乐观锁适用性。
- 某些批量操作/聚合操作时处理复杂度提升。

## 结论与建议

乐观并发控制是现代企业级系统确保数据一致性的利器。对于大多数以读为主、写冲突概率低的业务系统（如电商、SaaS 管理后台等），建议优先采用 EF Core 的乐观锁机制，通过配置实体版本号和合理的异常处理，大幅降低竞态风险。对于特殊高风险领域，可考虑配合消息队列、事件溯源等高级技术进一步增强一致性保障。

> 🛡️ **最佳实践建议：**
>
> - 所有涉及关键业务约束（如不可重复预订、唯一库存分配等）的领域逻辑，务必使用并发控制机制。
> - 针对高频冲突场景及时监控、优化业务流程或采用专用分布式锁方案。
> - 加强单元测试和集成测试覆盖多线程及高并发边界情形。

通过合理运用 EF Core 乐观锁，让你的系统在面对瞬时高并发时依然稳定可靠，为业务创新保驾护航！
