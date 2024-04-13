---
pubDatetime: 2024-04-13
tags: [efcore]
source: https://www.milanjovanovic.tech/blog/a-clever-way-to-implement-pessimistic-locking-in-ef-core?utm_source=newsletter&utm_medium=email&utm_campaign=tnw85
author: Milan Jovanović
title: 在 EF Core 中实现悲观锁定的巧妙方法
description: 有时，特别是在高流量场景下，你绝对需要确保一次只能有一个进程修改一条数据。Entity Framework Core 是一个极好的工具，但它没有直接的悲观锁定机制。在本文中，我将展示我们如何使用原生 SQL 查询解决这个问题。
---

> ## 摘录
>
> 有时，特别是在高流量场景下，你绝对需要确保一次只能有一个进程修改一条数据。Entity Framework Core 是一个极好的工具，但它没有直接的悲观锁定机制。在本文中，我将展示我们如何使用原生 SQL 查询解决这个问题。
>
> 原文 [A Clever Way To Implement Pessimistic Locking in EF Core](https://www.milanjovanovic.tech/blog/a-clever-way-to-implement-pessimistic-locking-in-ef-core?utm_source=newsletter&utm_medium=email&utm_campaign=tnw85)

---

有时，特别是在高流量场景下，你绝对需要确保一次只能有一个进程修改一条数据。

设想你正在为一场广受欢迎的音乐会搭建票务销售系统。顾客们急切地抢购票务，最后几张可能会同时售罄。如果不小心处理，多个顾客可能会认为他们已经确保了最后的座位，导致超额预订和失望！

Entity Framework Core 是一个极好的工具，但它没有直接的悲观锁定机制。[乐观锁定](https://www.milanjovanovic.tech/blog/solving-race-conditions-with-ef-core-optimistic-locking)（使用版本控制）可以工作，但在高争用场景下，可能导致大量重试。

那么，我们如何使用 EF Core 解决这个问题呢？

## 场景详述

以下是一个简化的代码片段，用于说明我们的票务挑战：

```csharp
public async Task Handle(CreateOrderCommand request)
{
    await using DbTransaction transaction = await unitOfWork
        .BeginTransactionAsync();

    Customer customer = await customerRepository.GetAsync(request.CustomerId);

    Order order = Order.Create(customer);
    Cart cart = await cartService.GetAsync(customer.Id);

    foreach (CartItem cartItem in cart.Items)
    {
        // 哦哦...如果同时有两个请求到达这里怎么办？
        TicketType ticketType = await ticketTypeRepository.GetAsync(
            cartItem.TicketTypeId);

        ticketType.UpdateQuantity(cartItem.Quantity);

        order.AddItem(ticketType, cartItem.Quantity, cartItem.Price);
    }

    orderRepository.Insert(order);

    await unitOfWork.SaveChangesAsync();

    await transaction.CommitAsync();

    await cartService.ClearAsync(customer.Id);
}
```

上面的示例虽然是构造的，但应足以解释问题。在结账时，我们验证了每张票的 `AvailableQuantity`。

如果我们收到同时购买同一张票的并发请求会发生什么？

最坏的情况是我们最终“超额销售”了票。并发请求可能看到有票可卖并完成结账。

那么，我们如何解决这个问题呢？

## 原生 SQL 来救援！

由于 EF Core 并不直接提供悲观锁定，我们将用一些好旧的 SQL 来解决。我们将使用 `GetWithLockAsync` 替换获取票务的 `GetAsync` 调用。

幸运的是，EF Core 通过[原生 SQL 查询](https://www.milanjovanovic.tech/blog/ef-core-raw-sql-queries)使这变得简单：

```csharp
public async Task<TicketType> GetWithLockAsync(Guid id)
{
    return await context
        .TicketTypes
        .FromSql(
            $@"
            SELECT id, event_id, name, price, currency, quantity
            FROM ticketing.ticket_types
            WHERE id = {id}
            FOR UPDATE NOWAIT") // PostgreSQL: 立刻锁定或失败
        .SingleAsync();
}
```

理解其中的奥秘：

- `FOR UPDATE NOWAIT`：这是 PostgreSQL 中悲观锁定的核心。它告诉数据库“抓住这一行，为我锁定，如果它已经被锁定，立即抛出一个错误。”
- **错误处理**：我们会将 `GetWithLockAsync` 调用包装在一个 `try-catch` 块中，以优雅地处理锁定失败，或者重试，或者通知用户。

由于 EF Core 没有内置的方式添加查询提示，我们不得不编写原生 SQL 查询。我们可以使用 PostgreSQL 的 `SELECT FOR UPDATE` 语句获取选定行的行级锁。任何竞争事务都将被阻塞，直到当前事务释放锁。这是实现悲观锁定的一种非常简单的方式。

## 锁定的各种类型以及何时使用它们

为了防止操作等待其他事务释放任何锁定的行，您可以将 `FOR UPDATE` 与以下选项结合使用：

- `NO WAIT` - 如果行不能被锁定则报告错误，而不是等待。
- `SKIP LOCKED` - 跳过任何不能被锁定的选定行。

跳过锁定的行带有一个警告 - 你将从数据库获得不一致的结果。然而，这可以用来避免锁争用，当多个消费者访问类似队列的表时。实现[Outbox 模式](https://www.milanjovanovic.tech/blog/outbox-pattern-for-reliable-microservices-messaging)是这种方法的一个很好的例子。

**SQL Server**：你会使用 `WITH (UPDLOCK, READPAST)` 查询提示以获得类似效果。

## 悲观锁定与串行化事务

**串行化**事务提供最高级别的数据一致性。它们保证所有事务执行得好像它们是严格顺序进行，即使它们是同时发生的。这消除了诸如脏读（看到未提交的数据）或不可重复读（数据在读取之间更改）等异常的可能性。

这是它的工作原理：

- 当事务在串行化隔离级别下开始时，数据库锁定事务可能访问的所有数据。
- 这些锁会一直保持，直到整个事务被提交或回滚。
- 任何尝试访问锁定数据的其他事务将被阻塞，直到第一个事务释放其锁。

虽然串行化事务提供了最终的隔离，但它们带来了显著的成本：

- **性能开销**：锁定大量数据可能会严重影响性能，特别是在高并发场景下。
- **死锁**：由于进行了大量的锁定，死锁的风险更高。当两个或更多事务等待彼此持有的锁时，就会发生死锁，从而创建僵局。

使用 `SELECT FOR UPDATE` 的悲观锁定提供了更有针对性的数据隔离方法。你显式地锁定需要修改的特定行。尝试访问被锁定行的其他事务将被阻塞，直到锁被释放。

通过仅锁定必需的数据，悲观锁定避免了与锁定所有内容相关的性能开销。由于你锁定的资源更少，发生死锁的可能性较低。

## 何时使用每种方法

最佳方法取决于你的具体需求：

- **串行化事务**：适用于涉及高度敏感数据的情况，其中即使是最轻微的不一致也是不可接受的。示例包括财务交易和医疗记录更新。
- **悲观锁定**：对于大多数用例，尤其是在高流量应用程序中，是一个很好的选择。它提供了强一致性，同时保持良好的性能并降低死锁风险。

## 主要收获

我希望这次对悲观锁定的探索对你有所帮助。如果你的场景中数据一致性绝对至关重要，悲观锁定是你工具箱中的一个强大工具。

无论是 **串行化事务**还是使用 `SELECT FOR UPDATE` 的悲观锁定，都是确保数据一致性的绝佳选项。在做出选择时，考虑所需的隔离级别、潜在的性能影响和发生死锁的可能性。

今天就到这里。保持优秀，我们下周见。

---
