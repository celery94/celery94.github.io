---
pubDatetime: 2026-03-17T15:42:46+08:00
title: "Outbox Pattern 扩展实践：每天处理 20 亿条消息"
description: "从 1,350 MPS 到 32,500 MPS，通过逐步优化 PostgreSQL 查询、批量更新和 RabbitMQ 批量发布，把 Outbox Pattern 扩展到每天处理超过 28 亿条消息。"
tags: ["C#", ".NET", "Outbox Pattern", "RabbitMQ", "MassTransit", "PostgreSQL", "性能优化"]
slug: "scaling-outbox-pattern-2b-messages-per-day"
ogImage: "../../assets/645/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/scaling-the-outbox-pattern"
---

![高速消息管道流量示意图](../../assets/645/01-cover.png)

实现 Outbox Pattern 不难，难的是把它推到极限。

起跑点是这样一个 `OutboxProcessor`：轮询未处理消息，逐条发布到 RabbitMQ，再逐条更新数据库状态。批次大小设为 1000，连续跑 1 分钟，结果是 81,000 条消息——约 1,350 MPS（每秒消息数）。

不算差。但如果目标是每天数十亿条消息，这个数字远不够用。下面是从这个基线出发，逐步把吞吐量拉到 32,500 MPS 的完整过程。

## 基准实现

初始代码结构很清晰：查询未处理消息、发布、更新。

```csharp
internal sealed class OutboxProcessor(NpgsqlDataSource dataSource, IPublishEndpoint publishEndpoint)
{
    private const int BatchSize = 1000;

    public async Task<int> Execute(CancellationToken cancellationToken = default)
    {
        await using var connection = await dataSource.OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);

        var messages = await connection.QueryAsync<OutboxMessage>(
            """
            SELECT *
            FROM outbox_messages
            WHERE processed_on_utc IS NULL
            ORDER BY occurred_on_utc LIMIT @BatchSize
            """,
            new { BatchSize },
            transaction: transaction);

        foreach (var message in messages)
        {
            var messageType = Messaging.Contracts.AssemblyReference.Assembly.GetType(message.Type);
            var deserializedMessage = JsonSerializer.Deserialize(message.Content, messageType);
            await publishEndpoint.Publish(deserializedMessage, messageType, cancellationToken);

            await connection.ExecuteAsync(
                "UPDATE outbox_messages SET processed_on_utc = @ProcessedOnUtc WHERE id = @Id",
                new { ProcessedOnUtc = DateTime.UtcNow, message.Id },
                transaction: transaction);
        }

        await transaction.CommitAsync(cancellationToken);
        return messages.Count;
    }
}
```

## 定位瓶颈

要改进，先弄清楚时间花在哪里。用 `Stopwatch` 把三个环节单独计时：

- 查询时间：约 70ms
- 发布时间：约 320ms
- 更新时间：约 300ms

发布和更新才是真正的瓶颈，接下来分别处理。

## 给查询加覆盖索引

当前查询走的是全表扫描，`EXPLAIN ANALYZE` 能看到：

```sql
Parallel Seq Scan on outbox_messages  (cost=0.00..47830.88 ...)
Execution Time: 124.298 ms
```

先把 `SELECT *` 改成只取需要的列，再创建一个覆盖索引（covering index）：

```sql
CREATE INDEX IF NOT EXISTS idx_outbox_messages_unprocessed
ON public.outbox_messages (occurred_on_utc, processed_on_utc)
INCLUDE (id, type, content)
WHERE processed_on_utc IS NULL
```

这个索引有三个设计点：

- `occurred_on_utc` 排序与 `ORDER BY` 一致，索引本身已排好序，查询不需要额外排序
- `INCLUDE` 的列可以直接从索引行返回，不用回表
- `WHERE processed_on_utc IS NULL` 在索引层面过滤已处理消息

加完索引后，执行计划变成纯 `Index Only Scan`：

```sql
Index Only Scan using idx_outbox_messages_unprocessed on outbox_messages
Execution Time: 0.189 ms
```

> PostgreSQL 的最大索引行大小是 2712B。`content` 列存放序列化 JSON，最容易超限。建议消息体保持精简；极端情况下可以把 `content` 从 `INCLUDE` 移除，接受一点性能代价。

**查询时间：70ms → 1ms（降幅 98.5%）**

## 并行发布消息

发布环节的问题是逐条 `await`，每条消息都要等待消息 broker 的确认后才处理下一条：

```csharp
foreach (var message in messages)
{
    // 等待 broker ack，再继续下一条
    await publishEndpoint.Publish(deserializedMessage, messageType, cancellationToken);
}
```

改成用 `Task.WhenAll` 并行发起所有发布任务：

```csharp
var publishTasks = messages
    .Select(message => PublishMessage(message, updateQueue, publishEndpoint, cancellationToken))
    .ToList();

await Task.WhenAll(publishTasks);
```

顺便加一个类型缓存，避免每条消息都重复做反射：

```csharp
private static readonly ConcurrentDictionary<string, Type> TypeCache = new();

private static Type GetOrAddMessageType(string typeName)
{
    return TypeCache.GetOrAdd(
        typeName,
        name => Messaging.Contracts.AssemblyReference.Assembly.GetType(name));
}
```

**发布时间：320ms → 289ms（降幅 9.8%）**

改善幅度不大，但这是后续并行优化的前提。

## 批量更新数据库

更新环节是逐条发 SQL，1000 条消息就要发 1000 次数据库请求。改成用 `VALUES` 子句构造一条批量 `UPDATE`：

```csharp
var updateSql =
    """
    UPDATE outbox_messages
    SET processed_on_utc = v.processed_on_utc,
        error = v.error
    FROM (VALUES
        {0}
    ) AS v(id, processed_on_utc, error)
    WHERE outbox_messages.id = v.id::uuid
    """;

var updates = updateQueue.ToList();
var paramNames = string.Join(",", updates.Select((_, i) => $"(@Id{i}, @ProcessedOn{i}, @Error{i})"));
var formattedSql = string.Format(updateSql, paramNames);

var parameters = new DynamicParameters();
for (int i = 0; i < updates.Count; i++)
{
    parameters.Add($"Id{i}", updates[i].Id.ToString());
    parameters.Add($"ProcessedOn{i}", updates[i].ProcessedOnUtc);
    parameters.Add($"Error{i}", updates[i].Error);
}

await connection.ExecuteAsync(formattedSql, parameters, transaction: transaction);
```

生成的 SQL 大概是这样：

```sql
UPDATE outbox_messages
SET processed_on_utc = v.processed_on_utc, error = v.error
FROM (VALUES
    (@Id0, @ProcessedOn0, @Error0),
    (@Id1, @ProcessedOn1, @Error1),
    -- ...
    (@Id999, @ProcessedOn999, @Error999)
) AS v(id, processed_on_utc, error)
WHERE outbox_messages.id = v.id::uuid
```

**更新时间：300ms → 52ms（降幅 82.6%）**

## 单机已到瓶颈

三项优化做完，连跑 1 分钟：162,000 条消息，约 2,700 MPS，折合每天 2.3 亿条。

各步骤耗时：查询 ~1ms、发布 ~289ms、更新 ~52ms。发布仍是主要瓶颈，继续往下走。

## 并行多个 Worker

要突破单个 processor 的上限，需要同时跑多个实例。核心问题是如何防止不同 worker 处理同一批消息。

PostgreSQL 的 `FOR UPDATE SKIP LOCKED` 正好解决这个问题：被某个事务锁住的行，其他查询直接跳过而不是等待。

```sql
SELECT id AS Id, type AS Type, content AS Content
FROM outbox_messages
WHERE processed_on_utc IS NULL
ORDER BY occurred_on_utc LIMIT @BatchSize
FOR UPDATE SKIP LOCKED
```

用 `Parallel.ForEachAsync` 模拟多实例并发：

```csharp
var parallelOptions = new ParallelOptions
{
    MaxDegreeOfParallelism = _maxParallelism,
    CancellationToken = cancellationToken
};

await Parallel.ForEachAsync(
    Enumerable.Range(0, _maxParallelism),
    parallelOptions,
    async (_, token) => { await ProcessOutboxMessages(token); });
```

5 个 worker 的结果：179,000 条/分钟，约 2,983 MPS——和单 worker 的 2,700 MPS 差不多。

原因在于发布时间：单 worker 约 289ms，5 个 worker 并发后发布时间飙到约 1,540ms，接近 289 × 5。每个 worker 都在等 broker 确认，并行没带来加速，反而变成了争用。

## 开启 RabbitMQ 批量发布

真正的突破来自 RabbitMQ 的批量发布特性。MassTransit 提供了 `ConfigureBatchPublish` 方法，开启后消息会在本地缓冲后批量发送，大幅减少网络往返。

```csharp
builder.Services.AddMassTransit(x =>
{
    x.UsingRabbitMq((context, cfg) =>
    {
        cfg.Host(builder.Configuration.GetConnectionString("Queue"), hostCfg =>
        {
            hostCfg.ConfigureBatchPublish(batch =>
            {
                batch.Enabled = true;
            });
        });

        cfg.ConfigureEndpoints(context);
    });
});
```

> `ConfigureBatchPublish` 在 MassTransit.RabbitMQ v8.3.2 中已被标记为废弃。该版本升级到了基于 TPL 和 async/await 重写的 `RabbitMQ.Client` v7，单升级客户端本身就能取得类似的性能提升。

5 个 worker + 批量发布，重新跑 1 分钟：**1,956,000 条消息，约 32,500 MPS，超过每天 28 亿条。**

## 关闭发布确认（不推荐）

还有一个选项：关闭 publisher confirmation（发送后不等 broker ack）。有消息丢失风险。

```csharp
hostCfg.PublisherConfirmation = false; // 有风险，不推荐生产使用
hostCfg.ConfigureBatchPublish(batch =>
{
    batch.Enabled = true;
});
```

关闭后约 37,000 MPS，比保留确认额外提升约 14%。这个取舍通常不值得。

## 生产落地的判断点

数字很漂亮，但几件事在实际落地时值得提前确认：

**消费者能跟上吗？** 把发送端优化到 32,500 MPS，如果消费者处理能力没有同步扩展，队列积压只会越来越深。优化不能只看一端。

**消息顺序不再保证**：`FOR UPDATE SKIP LOCKED` 加上并行 worker，消息到达消费者的顺序不再严格按 `occurred_on_utc` 排列。如果业务对顺序有要求，需要在消费者端引入 Inbox 模式来重排。

**幂等消费**：并行处理维持的是 at-least-once 语义，偶发的重复消息是正常现象。消费者必须设计成幂等的。

## 参考

- [Scaling the Outbox Pattern (2B+ messages per day)](https://www.milanjovanovic.tech/blog/scaling-the-outbox-pattern) — Milan Jovanović
- [Implementing the Outbox Pattern](https://www.milanjovanovic.tech/blog/implementing-the-outbox-pattern) — Milan Jovanović
- [Source code on GitHub](https://github.com/m-jovanovic/outbox-scaling) — m-jovanovic
