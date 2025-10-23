---
pubDatetime: 2025-05-16
tags: [".NET", "Architecture"]
slug: dotnet-redis-pubsub-messaging
source: https://www.milanjovanovic.tech/blog/simple-messaging-in-dotnet-with-redis-pubsub
title: 在.NET中用Redis Pub/Sub实现简单高效的消息通信
description: 深入解析如何利用Redis Pub/Sub在.NET应用中实现实时消息通信、缓存失效通知等分布式场景，配合代码实战与架构思路，助力后端开发者快速上手。
---

# 在.NET中用Redis Pub/Sub实现简单高效的消息通信 🚀

## 引言：Redis，不只是缓存！

当你在做.NET后端开发时，Redis可能早已是你缓存优化的常用工具。不过，Redis的能力远不止于此！它还内置了一个被低估的利器——**Pub/Sub（发布/订阅）机制**。通过Redis Channels，你可以轻松地在不同服务间实现实时消息推送，打造高效的分布式通信方案。今天，我们就来深入探讨如何在.NET项目中玩转Redis Pub/Sub，助你解决如缓存同步、实时通知等实际痛点。

> Redis Pub/Sub=“轻量消息中枢”，让你的分布式系统更灵活、更有弹性！

---

## 1. Redis Channels是什么？——消息通信的高速公路 🛣️

Redis Channels是基于[发布/订阅模式](https://en.wikipedia.org/wiki/Publish%E2%80%93subscribe_pattern)（Pub/Sub）的命名通信通道，每个通道都有唯一名字，比如`notifications`、`updates`等。  
**发布者（Producer）** 通过`PUBLISH`指令往通道发送消息；**订阅者（Consumer）** 通过`SUBSCRIBE`指令监听并消费消息。

### 结构示意图

![Redis channel with publisher and three subscribers.](https://www.milanjovanovic.tech/blogs/mnw_100/redis_channel.png?imwidth=3840)

如图，一个Channel可以有多个发布者和多个订阅者，实现“一发多收”，非常适合广播类场景。

#### 注意事项：

- **无消息持久化**：如果没有订阅者，消息会直接丢弃。
- **交付语义：At-most-once**。也就是说，消息最多投递一次，可能丢失。

---

## 2. 哪些场景适合用Redis Pub/Sub？🤔

Redis Channels并不适合“丢消息就炸锅”的核心业务，但对于**偶尔丢失消息可接受、追求实时性**的场景，它是优雅且高效的选择：

- **社交动态推送**：新内容发布，实时广播给在线用户。
- **体育比分直播**：赛事得分变动，即时通知订阅用户。
- **IM/聊天室**：实时聊天消息推送。
- **协作编辑器**：文档多人编辑时，变更同步。
- **分布式缓存失效通知**：数据更新后，通知各节点清除本地缓存（详细见下文实战）。

⚠️ 如果你的业务对消息可靠性极高，请考虑Kafka、RabbitMQ等更专业的消息队列系统。

---

## 3. .NET项目实战：用StackExchange.Redis实现Pub/Sub 💻

让我们直接上手，用.NET主流库[StackExchange.Redis](https://stackexchange.github.io/StackExchange.Redis/)实现一个最简的生产者+消费者模型。

### 1）安装依赖

```shell
Install-Package StackExchange.Redis
```

如果本地没装Redis，可以用Docker一键启动：

```shell
docker run -it -p 6379:6379 redis
```

### 2）实现Producer（消息生产者）

```csharp
public class Producer(ILogger<Producer> logger) : BackgroundService
{
    private static readonly string ConnectionString = "localhost:6379";
    private static readonly ConnectionMultiplexer Connection =
        ConnectionMultiplexer.Connect(ConnectionString);

    private const string Channel = "messages";

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var subscriber = Connection.GetSubscriber();

        while (!stoppingToken.IsCancellationRequested)
        {
            var message = new Message(Guid.NewGuid(), DateTime.UtcNow);
            var json = JsonSerializer.Serialize(message);

            await subscriber.PublishAsync(Channel, json);

            logger.LogInformation(
                "Sending message: {Channel} - {@Message}", message);

            await Task.Delay(5000, stoppingToken);
        }
    }
}
```

### 3）实现Consumer（消息消费者）

```csharp
public class Consumer(ILogger<Consumer> logger) : BackgroundService
{
    private static readonly string ConnectionString = "localhost:6379";
    private static readonly ConnectionMultiplexer Connection =
        ConnectionMultiplexer.Connect(ConnectionString);

    private const string Channel = "messages";

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var subscriber = Connection.GetSubscriber();

        await subscriber.SubscribeAsync(Channel, (channel, message) =>
        {
            var msg = JsonSerializer.Deserialize<Message>(message);

            logger.LogInformation(
                "Received message: {Channel} - {@Message}",
                channel,
                msg);
        });
    }
}
```

### 4）运行效果图

![Pub/Sub demo.](https://www.milanjovanovic.tech/blogs/mnw_100/redis_pub_sub.gif?imwidth=3840)

---

## 4. 实践案例：用Pub/Sub做分布式缓存失效通知 🧹

在大型分布式系统中，常见的缓存策略是“本地内存缓存+全局Redis缓存”。  
但数据库数据变更时，如何及时同步所有节点的本地缓存？

**方案：用Redis Pub/Sub做缓存失效广播！**

每个应用实例都运行一个后台服务，监听`cache-invalidation`通道：

```csharp
public class CacheInvalidationBackgroundService(
    IServiceProvider serviceProvider)
    : BackgroundService
{
    public const string Channel = "cache-invalidation";

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await subscriber.SubscribeAsync(Channel, (channel, key) =>
        {
            var cache = serviceProvider.GetRequiredService<IMemoryCache>();
            cache.Remove(key);
            return Task.CompletedTask;
        });
    }
}
```

当数据库发生变更时，只需publish对应key到该Channel，各节点即刻同步清理内存缓存。  
即使个别节点短暂掉线而未收到通知也无大碍，因为重启后缓存本就会失效。这种方式既简单又高效，极大提升了数据一致性体验！

---

## 5. 总结与延伸 📚

- Redis Pub/Sub为.NET带来了“轻量级实时通信”能力，适合非强一致性但追求效率的场景；
- 在分布式缓存同步、即时推送、协作编辑等领域表现优秀；
- 实现简单，上手迅速，却不适用于强可靠性的核心消息流转。

未来，如果你想进一步研究更复杂的分布式架构和消息总线设计，强烈推荐了解[Modular Monolith Architecture](https://www.milanjovanovic.tech/modular-monolith-architecture?utm_source=article_page)等先进架构理念！

---

## 你的看法和实践？

你是否已经在生产环境用过Redis Pub/Sub？遇到哪些坑？  
欢迎在评论区留言交流 👇 或把本文转发给同样关注.NET与分布式系统的朋友们！

如果你喜欢这样的技术深度分享，也别忘了点赞关注哦～ 🔥
