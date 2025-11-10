---
pubDatetime: 2025-11-10
title: 幂等消费者模式：.NET 分布式消息处理的必要之举
description: 深入探讨分布式系统中消息重复投递的问题，以及如何通过幂等消费者模式确保消息在重试场景下恰好处理一次。包含完整的 .NET 实现示例与最佳实践。
tags: [".NET", "Messaging", "Distributed Systems", "Design Patterns"]
slug: idempotent-consumer-pattern-dotnet
source: https://www.milanjovanovic.tech/blog/the-idempotent-consumer-pattern-in-dotnet-and-why-you-need-it
---

分布式系统本质上是不可靠的。网络会出现故障、消息可能丢失或延迟、服务实例可能崩溃。这些不确定因素是分布式计算的基本特征，任何试图忽视这一现实的系统架构最终都会在生产环境中遭遇微妙而致命的数据不一致问题。

分布式消息系统中最棘手的问题之一就是：**如何确保消息恰好被处理一次**？理论上，这在大多数系统中是无法绝对保证的。消息可能重复到达、可能顺序错乱、可能延迟数小时。如果你的系统设计建立在"每条消息必然恰好处理一次"的假设之上，那么隐性的数据损坏几乎是不可避免的。

好消息是：我们可以通过**幂等消费者（Idempotent Consumer）模式**来确保副作用（side effects）恰好执行一次，即使在重试和网络波动的情况下。本文将深入探讨这一模式的原理、实现方式，以及在 .NET 中的最佳实践。

## 分布式消息系统中的常见故障场景

让我们从一个具体的例子开始。假设你的服务在创建新笔记时发布一个事件：

```csharp
await publisher.PublishAsync(new NoteCreated(note.Id, note.Title, note.Content));
```

表面上看起来很简单——不需要关心 `publisher` 的具体实现或底层消息代理是什么（RabbitMQ、SQS、Azure Service Bus 等）。但在分布式网络环境中，很多事情可能会出错：

1. **发布方超时重试问题**
   - 发布方将消息发送到消息代理
   - 代理存储消息并发送 ACK（确认）
   - 网络故障：ACK 没有到达生产者
   - 生产者超时后重新发送消息
   - 代理现在有两条相同的 `NoteCreated` 事件

从生产者的角度，它"修复"了一次超时。但从消费者的角度，它收到了两条关于同一笔记创建的事件。

其他可能导致重复的来源包括：

- **代理重新投递**：消费者未能及时确认，代理认为消息未被成功处理
- **消费者失败与重试**：消费者处理消息时崩溃，重启后消息被重新投递

这意味着即使你在发布方"做得完全正确"，消费方仍然必须采取防御措施来应对重复消息。

## 发布方幂等性：让代理来处理重复

许多现代消息代理已经内置了通过**消息去重**来支持幂等发布的能力。只要你为每条消息赋予一个唯一的 `MessageId`，代理就能在配置的时间窗口内检测并忽略重复消息。

例如，Azure Service Bus 支持此功能，Amazon SQS 和其他代理也提供类似的保证。关键是为每条消息分配一个稳定的、能唯一标识逻辑事件的标识符。

发布 `NoteCreated` 事件时的做法：

```csharp
var message = new NoteCreated(note.Id, note.Title, note.Content)
{
    MessageId = Guid.NewGuid() // 或者使用 note.Id
};

await publisher.PublishAsync(message);
```

当网络故障导致重试时，代理看到相同的 `MessageId` 后就知道这是一条重复消息，会安全地丢弃它。这样你就获得了去重功能，无需维护额外的追踪表或状态存储。

**发布方幂等性解决的是生产者侧的问题**：网络重试、短暂故障、重复发送。

但它**无法处理消费者侧的问题**：当消息被重新投递给消费者，或消费者在处理过程中崩溃时会发生什么？这正是幂等消费者模式的用武之地。

## 在 .NET 中实现幂等消费者

下面是一个 `NoteCreated` 事件的幂等消费者实现示例：

```csharp
internal sealed class NoteCreatedConsumer(
    TagsDbContext dbContext,
    HybridCache hybridCache,
    ILogger<Program> logger) : IConsumer<NoteCreated>
{
    public async Task ConsumeAsync(ConsumeContext<NoteCreated> context)
    {
        // 1. 检查是否已处理过此消息
        if (await dbContext.MessageConsumers.AnyAsync(c =>
                c.MessageId == context.MessageId &&
                c.ConsumerName == nameof(NoteCreatedConsumer)))
        {
            return; // 重复消息，直接返回
        }

        var request = new AnalyzeNoteRequest(
            context.Message.NoteId,
            context.Message.Title,
            context.Message.Content);

        try
        {
            using var transaction = await dbContext.Database.BeginTransactionAsync();

            // 2. 执行确定性处理：从内容推导标签
            var tags = AnalyzeContentForTags(request.Title, request.Content);

            // 3. 持久化标签
            var tagEntities = tags.Select(ProjectToTagEntity(request.NoteId)).ToList();
            dbContext.Tags.AddRange(tagEntities);

            // 4. 记录该消息已被处理
            dbContext.MessageConsumers.Add(new MessageConsumer
            {
                MessageId = context.MessageId,
                ConsumerName = nameof(NoteCreatedConsumer),
                ConsumedAtUtc = DateTime.UtcNow
            });

            await dbContext.SaveChangesAsync();
            await transaction.CommitAsync();

            // 5. 更新缓存
            await CacheNoteTags(request, tags);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Error analyzing note {NoteId}", request.NoteId);
            throw; // 抛出异常触发重试
        }
    }
}
```

这是一个典型的幂等消费者实现，包含了几个关键细节。

### 关键点 1：幂等性键（Idempotency Key）

```csharp
if (await dbContext.MessageConsumers.AnyAsync(c =>
        c.MessageId == context.MessageId &&
        c.ConsumerName == nameof(NoteCreatedConsumer)))
{
    return;
}
```

幂等性键由两个部分组成：

- **`MessageId`**：从消息传输层获取（`context.MessageId`）
- **`ConsumerName`**：消费者的名称，确保不同的消费者可以安全地处理同一条消息

当重复消息到达时，你短路返回，不执行任何操作。

**重要的架构细节**：在 `MessageConsumers` 表上设置 `(MessageId, ConsumerName)` 的**唯一约束**，以防止并发处理同一消息时的竞态条件。即使并发处理相同消息，也只有一条记录能成功插入。

### 关键点 2：原子性副作用 + 幂等性记录

处理消息和存储消息消费者记录发生在同一个事务中：

```csharp
using var transaction = await dbContext.Database.BeginTransactionAsync();

// 写入标签
dbContext.Tags.AddRange(tagEntities);

// 写入消息-消费者记录
dbContext.MessageConsumers.Add(new MessageConsumer { ... });

await dbContext.SaveChangesAsync();
await transaction.CommitAsync();
```

这样做的价值：

- **处理失败**：如果处理失败，`MessageConsumers` 表中不会有记录，消息可以被重试
- **处理成功**：处理结果和 `MessageConsumer` 行一起被提交
- **避免不一致**：永远不会出现"工作已完成但消息未被标记"或反之的状态

**这就是幂等性的核心**：无论重试多少次，每条消息的逻辑工作恰好执行一次。

### 关键点 3：处理至少一次投递（At-Least-Once Delivery）

现实中的大多数系统都采用**至少一次**语义：

- 消费者处理消息
- ACK 失败或超时
- 代理重新投递
- 代码再次运行

使用此模式时，第二次运行会查询 `MessageConsumers` 表并提前返回，不会产生重复的副作用。这个方案很有效，但有一个需要特别注意的例外...

## 确定性处理器 vs 非确定性处理器

当消费者的处理程序调用数据库外的东西会怎样？比如邮件 API、支付网关或后台任务队列？

这些都是常见的副作用，也需要满足幂等性要求。然而这些调用位于事务边界之外。你的数据库可能成功提交了，但如果在获得外部服务的响应前网络中断，你无法判断该操作是否真的执行了。重试时，消费者可能会发送另一封邮件或对信用卡进行两次扣款。

你现在进入了**非确定性处理器**的复杂领域：无法安全重复的操作。

### 策略 1：在外部调用中使用幂等性键

如果外部服务支持，就传递一个稳定的标识符，比如消息的 `MessageId`。许多 API（包括支付处理器和电子邮件平台）允许你指定幂等性键头。该服务确保具有相同键的相同请求只执行一次。

```csharp
await emailService.SendAsync(new SendEmailRequest
{
    To = user.Email,
    Subject = "欢迎！",
    Body = "感谢您的注册。",
    IdempotencyKey = context.MessageId
});
```

即使请求被重试，提供商也会识别该键并跳过重复。这是最简单、最可靠的方式（如果外部依赖支持的话）。

### 策略 2：本地存储意图

如果外部服务不支持幂等性键，你可以模拟它的行为。在调用外部系统**之前**，在数据库中创建一条记录，存储预期执行的操作的意图。例如，创建一个 `PendingEmails` 表，记录哪些消息应该发送邮件，以消息 ID 或用户 ID 作为键。

后台进程可以定期读取这些待处理的记录并执行操作，确保处理一次。这使流程变得确定性的，但代价是增加复杂性：需要额外的表、后台工作程序和重试逻辑。除非副作用非常关键或不可逆（如支付或账户配置），否则这通常是过度设计。

**权衡来自于信心**。如果重复执行操作会带来真实的后果，就显式引入幂等性。如果后果较轻，重试操作可能是可接受的。

## 何时不需要幂等消费者

并非每个消费者都需要幂等性检查的开销。如果你的操作本身已经是幂等的，你通常可以跳过额外的表和事务逻辑。

**天然幂等的操作示例**：

- 更新投影（projection）
- 设置状态标志
- 刷新缓存

例如，"将用户状态设为 Active"或"重建读模型"等操作会覆盖状态而不是追加，本质上是幂等的。

有些处理程序也使用**前置条件检查**来避免重复。如果处理程序更新一个实体，它可以先检查该实体是否已处于所需状态，如果是就提前返回。这个简单的守卫子句通常就足够了。

**不要盲目地在任何地方应用幂等消费者模式**。只在能保护你免受真实伤害的地方应用它——即重复处理会导致财务或数据不一致的地方。对于其他情况，简单总是更好的。

## 总结

分布式系统本质上是不可预测的。重试、重复和部分故障是正常运作的一部分，你无法完全避免。但你可以设计你的系统，使这些问题的影响最小化。

**完整的可靠消息处理策略**：

1. **发布方**：利用消息代理内置的消息去重功能，为每条消息分配稳定的 `MessageId`，让代理自动处理重复。

2. **消费方**：应用幂等消费者模式，在数据库中跟踪已处理的消息，将消息处理的工作和幂等性记录保持在同一事务中。

3. **外部系统调用**：优先使用外部服务的幂等性键支持；如果不支持，考虑本地意图存储（但需要权衡复杂性）。

4. **选择性应用**：不是所有消费者都需要这个模式。对于天然幂等的操作或有简单前置条件检查的操作，可以跳过额外复杂性。

一旦你理解并应用了这些原则，你会开始在现实世界的系统中处处看到它们的身影。构建容错于重试的消费者，你的分布式系统会更加可靠。
