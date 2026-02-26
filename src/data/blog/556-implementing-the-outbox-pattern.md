---
pubDatetime: 2026-02-26
title: "实现 Outbox 模式"
description: "在分布式系统中，保存数据和发送消息是两个独立操作，任何一个失败都会导致不一致。Outbox 模式将消息发布纳入数据库事务，通过后台处理器可靠投递，从根本上解决这个问题。"
tags: ["Architecture", ".NET", "Messaging", "Distributed Systems"]
slug: "implementing-the-outbox-pattern"
source: "https://www.milanjovanovic.tech/blog/implementing-the-outbox-pattern"
---

# 实现 Outbox 模式

一个微服务需要把新订单保存到数据库，同时通知其他系统。如果保存成功但通知失败，订单存在了却没人知道。如果通知发出去了但保存回滚了，其他系统以为有新订单，实际上并没有。

这个问题在分布式系统中反复出现：发邮件确认订单、通知库存服务扣减、告诉支付系统扣款。每一个场景都涉及本地数据变更加上一次外部通信，两步操作，任何一步失败都是灾难。

Outbox 模式的核心思路是：不要直接发消息，把消息和业务数据写进同一个事务。一个后台进程负责从 Outbox 表取出消息并发布到消息队列。

## 没有 Outbox 时会出什么问题

看一个典型的命令处理器：

```csharp
public class CreateOrderCommandHandler(
    IOrderRepository orderRepository,
    IProductInventoryChecker inventoryChecker,
    IUnitOfWork unitOfWork,
    IEventBus eventBus) : IRequestHandler<CreateOrderCommand, OrderDto>
{
    public async Task<OrderDto> Handle(CreateOrderCommand request, CancellationToken cancellationToken)
    {
        var order = new Order(request.CustomerId, request.ProductId, request.Quantity, inventoryChecker);

        await orderRepository.AddAsync(order);

        await unitOfWork.CommitAsync(cancellationToken);

        // 数据库事务已经提交

        await eventBus.Send(new OrderCreatedIntegrationEvent(order.Id));

        return new OrderDto { Id = order.Id, Total = order.Total };
    }
}
```

事务提交之后、事件发送之前，应用可能崩溃。或者消息代理恰好不可用。两种情况的结果一样：订单创好了，但下游系统一无所知。

这不是偶发问题，而是架构层面的缺陷。把"保存数据"和"发送消息"当成两个独立步骤，就注定了不一致的可能性。

## Outbox 的实现

先建表。以 PostgreSQL 为例：

```sql
CREATE TABLE outbox_messages (
    id UUID PRIMARY KEY,
    type VARCHAR(255) NOT NULL,
    content JSONB NOT NULL,
    occurred_on_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    processed_on_utc TIMESTAMP WITH TIME ZONE NULL,
    error TEXT NULL
);

-- 对未处理消息的查询会频繁执行，加个索引
CREATE INDEX IF NOT EXISTS idx_outbox_messages_unprocessed
ON outbox_messages (occurred_on_utc, processed_on_utc)
INCLUDE (id, type, content)
WHERE processed_on_utc IS NULL;
```

`content` 列用 `jsonb` 类型，方便后续按需查询和索引 JSON 内容。

对应的 C# 实体：

```csharp
public sealed class OutboxMessage
{
    public Guid Id { get; init; }
    public string Type { get; init; }
    public string Content { get; init; }
    public DateTime OccurredOnUtc { get; init; }
    public DateTime? ProcessedOnUtc { get; init; }
    public string? Error { get; init; }
}
```

写入 Outbox 的方法：

```csharp
public async Task AddToOutbox<T>(T message, NpgsqlDataSource dataSource)
{
    var outboxMessage = new OutboxMessage
    {
        Id = Guid.NewGuid(),
        OccurredOnUtc = DateTime.UtcNow,
        Type = typeof(T).FullName, // 反序列化时需要类型信息
        Content = JsonSerializer.Serialize(message)
    };

    await using var connection = await dataSource.OpenConnectionAsync();
    await connection.ExecuteAsync(
        @"""
        INSERT INTO outbox_messages (id, occurred_on_utc, type, content)
        VALUES (@Id, @OccurredOnUtc, @Type, @Content::jsonb)
        """,
        outboxMessage);
}
```

关键在于：这条 INSERT 和业务数据的写入共用同一个数据库事务。事务提交，消息就一定在；事务回滚，消息也跟着消失。不存在中间状态。

一个更优雅的做法是结合领域事件（Domain Events）。聚合根在状态变更时抛出领域事件，在事务提交前将所有事件收集起来存入 Outbox 表。这个逻辑可以放在 Unit of Work 里，也可以用 EF Core 的拦截器（Interceptor）来实现。

## 后台处理器怎么跑

消息写进了 Outbox 表，还需要一个后台进程把它们发布出去。可以是独立部署的服务，也可以是同进程的后台任务。

这里用 Quartz 来调度定时任务：

```csharp
[DisallowConcurrentExecution]
public class OutboxProcessorJob(
    NpgsqlDataSource dataSource,
    IPublishEndpoint publishEndpoint,
    Assembly integrationEventsAssembly) : IJob
{
    public async Task Execute(IJobExecutionContext context)
    {
        await using var connection = await dataSource.OpenConnectionAsync();
        await using var transaction = await connection.BeginTransactionAsync();

        var messages = await connection.QueryAsync<OutboxMessage>(
            @"""
            SELECT id AS Id, type AS Type, content AS Content
            FROM outbox_messages
            WHERE processed_on_utc IS NULL
            ORDER BY occurred_on_utc LIMIT 100
            """,
            transaction: transaction);

        foreach (var message in messages)
        {
            try
            {
                var messageType = integrationEventsAssembly.GetType(message.Type);
                var deserializedMessage = JsonSerializer.Deserialize(message.Content, messageType);

                await publishEndpoint.Publish(deserializedMessage);

                await connection.ExecuteAsync(
                    @"""
                    UPDATE outbox_messages
                    SET processed_on_utc = @ProcessedOnUtc
                    WHERE id = @Id
                    """,
                    new { ProcessedOnUtc = DateTime.UtcNow, message.Id },
                    transaction: transaction);
            }
            catch (Exception ex)
            {
                await connection.ExecuteAsync(
                    @"""
                    UPDATE outbox_messages
                    SET processed_on_utc = @ProcessedOnUtc, error = @Error
                    WHERE id = @Id
                    """,
                    new { ProcessedOnUtc = DateTime.UtcNow, Error = ex.ToString(), message.Id },
                    transaction: transaction);
            }
        }

        await transaction.CommitAsync();
    }
}
```

`[DisallowConcurrentExecution]` 确保同一时刻只有一个实例在跑，避免重复发送。处理器每次拉一批未处理消息，逐条反序列化后发布到消息队列，成功就标记 `processed_on_utc`，失败就记录错误信息。

这是轮询（Polling）方式。另一种做法是用 PostgreSQL 的逻辑复制（Logical Replication），通过 WAL 流式推送变更给应用，实现推送式的 Outbox 处理器。选哪种取决于对延迟和复杂度的取舍。

## 需要注意的权衡

Outbox 模式提供的是**至少一次投递**（at-least-once delivery）。消息至少会被发送一次，但可能因为重试而发送多次。这意味着消费端必须做幂等处理，拿到重复消息不能产生重复副作用。

额外的数据库写入会增加负担。在高吞吐场景下，需要监控 Outbox 表的写入和查询性能，确保它不会成为瓶颈。

Outbox 处理器本身也需要重试机制。对瞬态故障使用指数退避，对持续性故障引入熔断器，防止在下游系统宕机时不断重试导致雪崩。

Outbox 表会持续增长。必须尽早规划清理策略，比如把已处理的消息归档到冷存储，或者在保留期过后直接删除。

## 怎么扩展

系统规模扩大后，单个 Outbox 处理器可能跟不上消息量，事件从产生到被消费的延迟会持续拉大。

最直接的做法是提高处理频率，每隔几秒跑一次而不是每分钟一次。也可以加大每次处理的批量，但要控制事务时间不能太长。

对于高吞吐场景，可以引入并行处理。多个处理器通过加锁机制分别认领一批消息，互不冲突地并行工作。`SELECT ... FOR UPDATE SKIP LOCKED` 是实现这一点的关键 SQL 语句，它让每个处理器跳过已被其他处理器锁定的行，只认领还没人处理的消息。

Outbox 模式把"发消息"从业务操作中解耦出来，用数据库事务的原子性做了担保。它增加了一些复杂度，但换来的是在故障场景下系统依然保持一致。在分布式系统里，这个交换很划算。
