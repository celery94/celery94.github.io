---
pubDatetime: 2026-01-10
title: "从第一性原理解决消息顺序问题"
description: "探讨分布式系统中消息顺序处理的演进路径，从领域事件到 Outbox 模式，再到 Saga 工作流，揭示如何在保证可靠性的同时实现按聚合根有序处理。"
tags: ["Architecture", "Messaging", "Saga", "Distributed Systems"]
slug: "solving-message-ordering-from-first-principles"
source: "https://www.milanjovanovic.tech/blog/solving-message-ordering-from-first-principles"
---

# 从第一性原理解决消息顺序问题

大多数系统不需要全局消息顺序，它们需要的是更简单且更实用的东西：**事件必须按聚合根有序处理**。

按 `OrderId`、`InvoiceId`、`CustomerId` 或任何聚合边界来处理。这个范围可以根据需求调整得更宽或更窄。

这最初看起来是一个事件处理问题，但如果你遵循需求的逻辑推导，最终会得到一个工作流。而这个工作流有一个名字：**Saga**。

## 领域事件看似完美的解决方案

[领域事件](https://www.milanjovanovic.tech/blog/how-to-use-domain-events-to-build-loosely-coupled-systems)之所以吸引人，是因为它们源于第一性原理：

- 聚合改变状态
- 发出描述发生了什么的事件
- 处理器响应并执行有用的工作

心智模型也很清晰：

> "状态变更 → 事件 → 反应"

典型的例子：

- `OrderPlaced`（订单已下）
- `PaymentCaptured`（支付已捕获）
- `OrderShipped`（订单已发货）

但是有个问题。**当你尝试将领域事件用于集成时，它们会变得脆弱**。

如果直接从事务中发布，你就将业务正确性与不可靠的副作用耦合在一起：

- 事务成功但发布失败
- 发布成功但事务回滚
- 消费者处理重复消息
- 重试导致重新排序

所以我们保留模型，但强化交付机制。

## Outbox 使发布可靠（但不保证顺序）

使用 [Outbox 模式](https://www.milanjovanovic.tech/blog/implementing-the-outbox-pattern)，我们在同一个事务中存储即将发出的事件和聚合更新。

然后后台发布器读取 Outbox 并将事件推送到队列。

这解决了可靠性问题：

- 如果事务提交，事件就会被持久化
- 如果发布器崩溃，稍后可以恢复
- 可以安全地重试

现在我们已经使事件发布变得可靠。

但我们还没有使事件处理变得有序。

## 竞争消费者很好，直到顺序重要时

一旦事件到达队列，我们通常使用最简单的扩展方式：[竞争消费者](https://www.milanjovanovic.tech/blog/event-driven-architecture-in-dotnet-with-rabbitmq)。

多个实例从同一队列消费以提高吞吐量。

这很好用……直到顺序变得重要。

同一个 `OrderId` 的两个事件可能同时被处理：

- 消费者 A 接收到 `PaymentCaptured`
- 消费者 B 接收到 `OrderPlaced`
- 副作用乱序执行

即使事件是按顺序发布的，重试和重新交付也可能打乱处理顺序。

现在你有了一个只在负载下才出现的微妙 bug。

这就是关键认识：**队列扩展工作，但不保留你的不变性**。

## 我们真正想要的是按聚合根排序

你不需要为所有事情建立一个有序队列。

你需要多条独立的有序线，每个聚合一条。

这通常成立，因为：

- 聚合已经定义了一致性边界
- 事件自然按顺序产生（v1、v2、v3...）
- "正确"的顺序就是聚合自己的时间线

如果我们能保证一次只有一个处理器处理给定聚合的事件，大部分问题就消失了。

最直接的解决方案也是最简单的：**对整个流使用单个消费者**。

这强制执行排序（假设事件按顺序发布）。

但它有一个明显的缺点。

## 单个消费者解决了顺序但限制了规模

一个消费者意味着：

- 吞吐量上限（一个工作者）
- 负载下的延迟峰值
- 扩展变成垂直而非水平

即使你的事件很轻量，你也在人为地限制系统瓶颈。

所以我们想要：

- 按聚合根排序
- 水平扩展
- 可靠性（Outbox 仍然保留）

这就是团队经常"发明"下一步的地方。

## 从处理器发布下一条消息

如果竞争消费者破坏了顺序，一个自然的想法是：

> "不要让队列决定下一步是什么，我们来决定。"

我们不再将所有事件倾倒到队列中让消费者竞争，而是转向链式方法：

1. 为聚合处理一条消息
2. 完成后，发布下一条要处理的消息

现在，系统每次为每个聚合处理一条消息。

这是关键时刻：

**你已经停止构建"事件处理器"。**

**你已经开始构建工作流。**

而这个工作流就是……一个 Saga。

## 恭喜，你构建了一个编排式 Saga

[编排式 Saga](https://www.milanjovanovic.tech/blog/orchestration-vs-choreography) 是一种工作流，其中：

- 每个步骤响应一个事件
- 执行工作
- 发出下一个事件以触发下一步

没有单一的中央协调器。

相反，我们有一条事件链："当 X 发生时，执行 Y，然后发布 Z"。

这种模式自然适合你的新需求：

- 保留按聚合根排序（链是顺序的）
- 可以跨聚合扩展（许多链并行执行）
- 每个步骤都是隔离的且可重试的

它还强制执行有用的规范：

- "下一步是什么？"变得明确
- 步骤之间的边界变得更清晰
- 你可以将工作流作为序列观察

但编排有一个限制：控制是分布式的，因此跟踪进度和处理异常可能会变得混乱。

所以我们采取最后一步。

## 如果想要控制，引入状态机 Saga

当工作流变得重要时，你通常想要：

- 一个知道当前状态的单一位置
- 进度的可见性（"我们卡在哪里？"）
- 明确的超时和重试
- 失败时的补偿操作

这时你从编排转向通过[状态机 Saga](https://www.milanjovanovic.tech/blog/implementing-the-saga-pattern-with-masstransit) 进行协调：

- Saga 保存工作流状态
- 事件驱动转换
- Saga 决定接下来发布什么消息
- 你获得控制和可观察性

顺便说一下，这并不取代 Outbox。

你仍然需要可靠的发布。

你只是使工作流变得明确了。

## 消息代理支持有助于排序，而非正确性

值得指出的是，你不必总是自己构建这些。

许多流行的消息代理为按键（你的聚合 ID）的有序处理提供技术原语：

- [Amazon SQS FIFO 消息组](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/using-messagegroupid-property.html)（按键）
- [Azure Service Bus 会话](https://learn.microsoft.com/en-us/azure/service-bus-messaging/message-sessions)（按键）
- [Kafka 分区](https://developer.confluent.io/courses/apache-kafka/partitions/)日志（键 → 分区 → 有序流）
- [RabbitMQ "单活动消费者"](https://www.rabbitmq.com/docs/consumers?#single-active-consumer)风格语义（按队列）

这些特性可以消除竞争消费者最常见的失败模式：并发处理同一聚合的消息。

但即使有完美的按聚合根排序，你仍然需要围绕它的模式来保持系统正确：

- Outbox 可靠地发布（如果事件丢失，排序就没用了）
- [幂等消费者](https://www.milanjovanovic.tech/blog/idempotent-consumer-handling-duplicate-messages) / Inbox，因为重试和重复仍然会发生
- 一致性边界（事务内和事务外可以安全做什么）
- 超时 + 补偿，当"有序序列"实际上是可能部分失败的业务工作流时

所以代理级别的排序是一个很好的基础。它减少了偶然的复杂性。只是当业务需要时，它不会消除显式建模长时间运行工作的需求。

## 总结

如果你从第一性原理遵循这个问题：

- 聚合定义了排序重要的边界
- Outbox 使事件发布可靠
- 竞争消费者破坏了按聚合根的顺序
- 单个消费者恢复顺序但限制了吞吐量
- 发布"下一条消息"为每个聚合创建顺序进度
- 这种顺序进度就是 Saga（首先是编排，需要控制时是状态机）

所以你不是偶然重新发明了什么。

你发现了"大规模按聚合根有序处理"不是队列特性。

**它是一个工作流。而 Saga 是我们在分布式系统中建模工作流的方式。**

一旦你这样看待它，你就不再为排序保证与队列作斗争了。

你设计业务实际需要的工作流。
