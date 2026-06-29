---
pubDatetime: 2026-06-29T07:38:39+08:00
title: "用 NATS JetStream 在 .NET 中快速搭建持久化消息队列"
description: "从零开始用 NATS JetStream 在 .NET 中搭建持久化工作队列。覆盖 Core NATS vs JetStream 的区别、Docker 部署、DI 注册、发布消费的完整代码，以及「先处理再 Ack」的可靠性规则。"
tags: [".NET", "NATS", "JetStream", "Messaging", "ASP.NET Core"]
slug: "nats-jetstream-dotnet-getting-started"
ogImage: "../../assets/910/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/getting-started-with-nats-jetstream-in-dotnet"
---

.NET 开发者需要消息队列时，通常直奔 RabbitMQ、Azure Service Bus，或者干脆拿一张 Postgres 表顶上。NATS 几乎从来不在讨论范围内。这挺可惜的——它悄悄成了我在这类场景里最喜欢的工具。

NATS 是一个 Go 写的消息系统，单二进制运行，无外部依赖。**JetStream** 是它上面的持久化层，把它变成了一个真正支持至少一次投递（at-least-once delivery）的队列。而它的 [.NET 客户端](https://github.com/nats-io/nats.net) 用起来很舒服。

## Core NATS vs JetStream

NATS 有两层，区别很重要。

**Core NATS** 是即发即忘的 pub/sub——你发布到某个 subject，那一刻订阅了的人才能收到。如果没人监听，消息就丢了。适合实时通知，但不适合工作队列。

**JetStream** 是加在上面的持久化层。它把发布到 subject 的消息捕获到磁盘上的 stream 里，消费者可以之后来读，甚至重启之后也可以。正是这个持久化把一个 subject 变成了持久队列。

简单说：Core NATS 在没人订阅时丢消息，JetStream 把它持久化到文件存储的 stream 里，稍后再投递。

## 为什么值得一试

从我常用那些 broker 转过来，几个东西让我印象深刻：

- **小。** 官方服务器镜像大约 18 MB，单个 Go 二进制，没有 ZooKeeper 或 Erlang 要维护。
- **快。** Core NATS 单节点能推每秒百万条小消息。JetStream 加上了磁盘持久化所以慢一些，但仍然轻松达到每秒几十万条。
- **运行成本低。** 服务器空闲只占几十 MB 内存，可以跟你的应用跑在一起。
- **按 stream 灵活配置。** 每个 stream 独立设置存储和保留策略，同一个服务器可以同时跑一个缓存和一个严格的工作队列。

## 搭起来

需要服务器和两个 NuGet 包。

用 JetStream 模式启动服务器，`-js` 开启 JetStream，`-sd` 指定数据目录让 stream 在重启后存活：

```yaml
# docker-compose.yml
nats:
  image: nats:2.14-alpine
  command: ['-js', '-sd', '/data']
  ports: ['4222:4222']
  volumes:
    - nats-data:/data
  restart: unless-stopped
```

添加客户端和 DI 集成包：

```bash
dotnet add package NATS.Net
dotnet add package NATS.Extensions.Microsoft.DependencyInjection
```

然后在 `Program.cs` 中接入。`AddNatsClient` 注册一个多路复用、自动重连的连接，下一行暴露一个可以在任何地方注入的 JetStream 上下文：

```csharp
// Program.cs
builder.Services.AddNatsClient(nats =>
    nats.ConfigureOptions(opts => opts with { Url = "nats://localhost:4222" }));

builder.Services.AddSingleton(sp =>
    sp.GetRequiredService<INatsConnection>().CreateJetStreamContext());
```

## 发布任务

JetStream 上下文注入之后，一个 Minimal API 端点一行调用就能发布。`Job` 是个普通 record，`NATS.Net` 自动帮你序列化成 JSON，所以你可以直接用类型化消息，不需要额外设置。`EnsureSuccess` 在 stream 没存储消息时抛异常：

```csharp
app.MapPost("/jobs", async (CreateJob request, INatsJSContext js, CancellationToken ct) =>
{
    var job = new Job(Guid.NewGuid(), request.Payload);

    PubAckResponse ack = await js.PublishAsync("jobs.work", job, cancellationToken: ct);
    ack.EnsureSuccess();

    return Results.Accepted($"/jobs/{job.Id}");
});
```

## 在 Worker 中处理任务

`BackgroundService` 是消费者的天然归属。它在启动时创建 stream 和持久消费者，然后在循环中拉取消息。每个运行中的实例共享 `workers` 消费者，所以它们竞争任务，每个任务只跑一次：

```csharp
public class JobWorker(INatsJSContext js) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        // 创建 stream —— 只在不存在时创建
        await js.CreateStreamAsync(new StreamConfig("JOBS", ["jobs.work"])
        {
            Retention = StreamConfigRetention.Workqueue, // ack 后移除消息
            Storage   = StreamConfigStorage.File          // 持久化到磁盘
        }, ct);

        // 创建消费者 —— 多实例共享、竞争式消费
        var consumer = await js.CreateOrUpdateConsumerAsync("JOBS", new ConsumerConfig("workers")
        {
            AckPolicy  = ConsumerConfigAckPolicy.Explicit,
            AckWait    = TimeSpan.FromSeconds(30), // 必须超过最坏情况的处理时间
            MaxDeliver = 5                          // 5 次尝试后丢弃毒消息
        }, ct);

        await foreach (var msg in consumer.ConsumeAsync<Job>(cancellationToken: ct))
        {
            await ProcessAsync(msg.Data, ct);  // 副作用
            await msg.AckAsync(cancellationToken: ct); // 再 ack
        }
    }
}
```

用 `builder.Services.AddHostedService<JobWorker>()` 注册。worker 是单例，如果需要 `DbContext` 等 scoped 依赖，通过 `IServiceScopeFactory` 解析。

两个 stream 设置决定了队列行为：

- **Storage**：`File`（磁盘，重启后存活）或 `Memory`（更快但重启丢失）
- **Retention**：
  - `Limits`（默认）：保留每条消息直到达到时间、大小或数量上限。stream 是可回放的日志，读取不会移除消息。
  - `Workqueue`：消费者 ack 后立即删除消息，stream 本身就是队列，FIFO 顺序投递。
  - `Interest`：只有在还有消费者需要时才保留，所有感兴趣的消费者 ack 后删除。

**工作队列用 `Workqueue` + `File`。**

## 先处理，再 Ack

仔细看 worker 循环：先处理，再 ack。这个顺序是让 JetStream 可靠的规则，大多数快速入门都略过了。

**副作用完成之后再 ack，绝不反过来。**

JetStream 给你至少一次投递。如果 worker 跑了任务但在 ack 之前崩溃，JetStream 会重新投递它。但如果在工作完成之前就 ack，崩溃后任务被标记为已完成却什么都没产出。

反过来说，一个任务可能被执行不止一次，所以你的处理器必须是幂等的。通常的做法是跟踪已经处理过的消息并跳过重复，在和副作用同一个事务里做。我在 [The Idempotent Consumer Pattern in .NET](https://www.milanjovanovic.tech/blog/the-idempotent-consumer-pattern-in-dotnet-and-why-you-need-it) 里覆盖了完整模式。至少一次投递只有在读 stream 的处理器是幂等的前提下才成立。

## 总结

NATS JetStream 用单个 18 MB 的二进制给你一个持久化、至少一次投递的工作队列，而且可以干净地嵌入 ASP.NET Core 应用：从 endpoint 发布，在 `BackgroundService` 里处理，工作完成后再 ack。

我一开始是带着怀疑去试的，半心半意地预期会想念 RabbitMQ。结果它说服了我：易于运维、没有意外、负载更大时可以用基于 Raft 的复制来集群。现在它是我想加个队列又不想在 broker 上费脑筋时的第一选择。

如果你还没试过，把容器跑起来，发布一条消息。上手就这么简单。

## 参考

- [Getting Started With NATS JetStream in .NET — Milan Jovanović](https://www.milanjovanovic.tech/blog/getting-started-with-nats-jetstream-in-dotnet)
- [NATS.Net GitHub](https://github.com/nats-io/nats.net)
- [NATS JetStream Docs](https://docs.nats.io/nats-concepts/jetstream)
- [The Idempotent Consumer Pattern in .NET](https://www.milanjovanovic.tech/blog/the-idempotent-consumer-pattern-in-dotnet-and-why-you-need-it)
