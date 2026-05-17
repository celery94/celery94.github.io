---
pubDatetime: 2026-05-17T16:20:10+08:00
title: "用例半成功怎么办：在 .NET 中为局部失败设计恢复策略"
description: "一个订单用例同时调用支付、数据库和邮件服务，支付成功却因数据库提交失败导致重复扣款——这类局部失败是分布式系统最常见的隐患。本文将副作用分为三类：事务性、外部可逆、外部不可逆，并给出对应策略：事务提交放最后、不可逆副作用走 Outbox 模式、外部调用用幂等键或补偿事件。"
tags: [".NET", "架构设计", "分布式系统", "Outbox模式", "幂等性"]
slug: "dotnet-usecase-partial-failure-design"
ogImage: "../../assets/797/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/when-your-use-case-half-succeeds-designing-for-partial-failure-in-dotnet?utm_source=newsletter&utm_medium=email&utm_campaign=tnw194"
---

多年来，我追过一类反复出现的支持工单，叫做"重复扣款"。

用户只操作了一次，却被收了两次钱。更诡异的地方在于，每个子系统对"到底发生了什么"都有不同的答案——支付提供方收到了钱，订单系统把订单回滚成草稿状态，用户还收到了一封"支付失败，请重试"的邮件。一次用户操作，留下了三套相互矛盾的记录。

用例看起来像一个事务，因为它就是一个方法调用。但只要它触及了多个系统，你就在和**局部失败**打交道。

这篇文章讲三件事：

- 所有副作用能落入的三个类别
- 如何设计一个"出错大声说、恢复有把握"的用例
- 什么时候用 Outbox 模式，什么时候用其他方法

![订单处理三条路径，其中支付路径出现裂口](../../assets/797/01-cover.png)

## 看起来没问题的代码

一个典型的"下订单"用例，我写过不下百遍，你也一样：

```csharp
internal sealed class PlaceOrder(
    IOrderRepository orders,
    IPaymentService payments,
    IEmailService emails,
    IUnitOfWork unitOfWork)
{
    public async Task<Result> ExecuteAsync(PlaceOrderRequest request, CancellationToken ct)
    {
        var order = Order.Create(request.CustomerId, request.Items);
        orders.Insert(order);

        await payments.ChargeAsync(order.Id, order.Total, ct);

        await emails.SendOrderConfirmationAsync(order.Id, ct);

        await unitOfWork.SaveChangesAsync(ct);

        return Result.Success();
    }
}
```

这个方法里有三个副作用，坐落在一个"看上去是单一事务边界"的方法里，它们之间没有任何协调。

如果 `SaveChangesAsync` 在 `ChargeAsync` 成功之后抛出异常，你就拿走了客户的钱但丢失了订单。如果 `SendOrderConfirmationAsync` 抛出，订单和扣款都完成了，但邮件没发出去。如果你天真地重试，就会二次扣款。

这个用例"能用"，直到哪天它不能用——而且每次出问题，都以不同的方式出问题。

## 三类副作用

动手写任何恢复代码之前，先把每个副作用归入这三个类别之一：

**事务性（Transactional）**  
活在数据库事务里。包括数据库插入、更新，以及在进程内派发的[领域事件](https://www.milanjovanovic.tech/blog/how-to-use-domain-events-to-build-loosely-coupled-systems)。

**外部可逆（External and reversible）**  
一个你可以补偿的 API 调用。扣款 → 退款。锁定库存 → 释放库存。

**外部不可逆（External and irreversible）**  
发出去的邮件、推送出去的 Webhook、已发出的短信。一旦发出，无法撤回。

**类别决定策略。不存在一条"好好处理错误"的万能规则能覆盖这三类。**

## 策略一：把事务性工作放到最后

第一步是机械性的调整：任何事务性工作都应该**最后提交**，在所有外部调用已经成功（或已被明确容忍）之后。

```csharp
public async Task<Result> ExecuteAsync(PlaceOrderRequest request, CancellationToken ct)
{
    var order = Order.Create(request.CustomerId, request.Items);

    var charge = await payments.ChargeAsync(order.Id, order.Total, ct);
    if (charge.IsFailure) return charge;

    order.MarkPaid(charge.Value.TransactionId);

    orders.Insert(order);

    await unitOfWork.SaveChangesAsync(ct);

    return Result.Success();
}
```

你不一定总能这样排序——有时候你需要先有数据库 ID 才能调用外部服务。这没关系。关键不是排序本身，而是**提交时，所有你承诺已完成的工作都真的已经完成了**。

## 策略二：把不可逆副作用移到用例外部

这是 [Outbox 模式](https://www.milanjovanovic.tech/blog/implementing-the-outbox-pattern)发挥作用的地方。

不要直接在用例里发邮件，而是触发一个 `OrderPlaced` [领域事件](https://www.milanjovanovic.tech/blog/how-to-use-domain-events-to-build-loosely-coupled-systems)，让一个 Outbox 调度器在事务提交后再去处理它：

```csharp
public async Task<Result> ExecuteAsync(PlaceOrderRequest request, CancellationToken ct)
{
    var order = Order.Create(request.CustomerId, request.Items);

    var charge = await payments.ChargeAsync(order.Id, order.Total, ct);
    if (charge.IsFailure) return charge;

    order.MarkPaid(charge.Value.TransactionId);

    orders.Insert(order);
    order.Raise(new OrderPlacedEvent(order.Id));

    await unitOfWork.SaveChangesAsync(ct);

    return Result.Success();
}
```

邮件不再是用例的负担。如果事务提交，事件也随之提交——它们在同一次写操作里。如果事务没有提交，事件就永远不会离开数据库，邮件也就不会发出去。一个单独的后台 worker 负责把事件转换成邮件，有它自己的重试逻辑和[幂等性](https://www.milanjovanovic.tech/blog/the-idempotent-consumer-pattern-in-dotnet-and-why-you-need-it)保证。

## 策略三：让外部调用幂等或可补偿

支付调用是最危险的那个。如果它成功了但事务回滚，你就拿了无法解释来源的钱。

你**不该**做的，是静默吞掉错误：

```csharp
try
{
    await payments.ChargeAsync(order.Id, order.Total, ct);
}
catch
{
    // shrug
}
```

症状从日志里消失了，钱还是走了，下次用户重试你又扣一次。

我实际用的两种方法，可以组合使用。

### 方法 A：幂等键

大多数严肃的支付提供方（Stripe、Adyen、Braintree）支持在扣款时附带一个**幂等键**。相同的 key 重试只是一个空操作，会返回原来的结果。这里最自然的 key 就是订单 ID：

```csharp
var charge = await payments.ChargeAsync(
    new ChargeRequest
    {
        OrderId = order.Id,
        Amount = order.Total,
        IdempotencyKey = order.Id.ToString()
    },
    ct);
```

现在可以安全重试这个用例了。如果上一次尝试扣款成功但在提交之前崩溃了，下一次尝试会从提供方拿回**相同的**扣款结果，而不是产生新的扣款，订单最终被持久化。

### 方法 B：通过领域事件补偿

幂等键只在你能用相同输入重放时有效。有时候不行——用户已经放弃了，请求被取消了，或者失败是永久性的。

这时候，钱是真实存在的，必须退回去。把失败本身也建模成一个一等公民事件，在带外（out-of-band）执行退款：

```csharp
public async Task<Result> ExecuteAsync(PlaceOrderRequest request, CancellationToken ct)
{
    var order = Order.Create(request.CustomerId, request.Items);

    var charge = await payments.ChargeAsync(order.Id, order.Total, ct);
    if (charge.IsFailure) return charge;

    order.MarkPaid(charge.Value.TransactionId);

    try
    {
        orders.Insert(order);
        order.Raise(new OrderPlacedEvent(order.Id));
        await unitOfWork.SaveChangesAsync(ct);
    }
    catch (Exception ex)
    {
        await outbox.PublishAsync(
            new PaymentFailedEvent(
                order.Id,
                charge.Value.TransactionId,
                order.Total,
                Reason: ex.Message),
            ct);

        throw;
    }

    return Result.Success();
}
```

一个后台消费者订阅 `PaymentFailedEvent`，用 transactionId 作为自己的幂等键去执行退款。这把一个复杂的跨进程补偿，变成了一个普通的、可观测的、可重试的[消息处理器](https://www.milanjovanovic.tech/blog/idempotent-consumer-handling-duplicate-messages)。

实践中，方法 A 用于瞬时失败，方法 B 用于永久失败。两者并不互斥。

## 什么时候该用 Saga

上面的策略适用于：一个用例在单个服务内协调少量副作用。一旦工作跨越多个服务、且需要在进程重启后继续，你就进入了 [Saga](https://www.milanjovanovic.tech/blog/implementing-the-saga-pattern-with-masstransit) 的领域。

判断标准：**如果恢复逻辑能装进脑子里，设计良好的用例就足够了。装不下，就用 Saga。**

## 小结

用例是**意图（intent）**的单元，不是**原子性（atomicity）**的单元。

- **事务性**工作最后和数据库一起提交
- **不可逆**副作用走 Outbox 模式，不在用例里直接触发
- **外部可逆**调用优先用幂等键，其次用补偿事件
- **永远不要**静默吞掉失败来让用例"看起来成功了"

我调查过的大多数事件驱动系统里的生产 bug，根源都是一个对自己是否成功撒了谎的用例。不再撒谎，系统就会变得好推理得多。

---

如果你关注 .NET 架构设计、分布式系统和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [When Your Use Case Half-Succeeds: Designing for Partial Failure in .NET](https://www.milanjovanovic.tech/blog/when-your-use-case-half-succeeds-designing-for-partial-failure-in-dotnet) - Milan Jovanović
- [Implementing the Outbox Pattern](https://www.milanjovanovic.tech/blog/implementing-the-outbox-pattern) - Milan Jovanović
- [How to Use Domain Events to Build Loosely Coupled Systems](https://www.milanjovanovic.tech/blog/how-to-use-domain-events-to-build-loosely-coupled-systems) - Milan Jovanović
- [The Idempotent Consumer Pattern in .NET](https://www.milanjovanovic.tech/blog/the-idempotent-consumer-pattern-in-dotnet-and-why-you-need-it) - Milan Jovanović
- [Implementing the Saga Pattern with MassTransit](https://www.milanjovanovic.tech/blog/implementing-the-saga-pattern-with-masstransit) - Milan Jovanović
