---
pubDatetime: 2025-03-30 18:52:03
tags: ["AI", "Productivity"]
slug: domain-events-loosely-coupled-systems
source: 自媒体原创
title: 从领域事件到松耦合系统：如何用EF Core和MediatR构建高效架构
description: 探讨领域事件在构建松耦合系统中的核心作用，详细分析其实现方法、技术工具以及一致性问题的解决方案，助力技术开发者优化系统架构。
---

# 从领域事件到松耦合系统：如何用EF Core和MediatR构建高效架构

在软件开发中，**如何构建松耦合的系统**一直是技术领域的热门话题，也是系统架构设计中的核心挑战之一。随着领域驱动设计（DDD）的流行，领域事件（Domain Events）作为一种重要的战术模式，越来越受到技术开发者的青睐。今天，我们将深入探讨领域事件的定义、实现方式以及相关技术工具（EF Core和MediatR）的应用，帮助您轻松构建高效松耦合系统。

---

## 什么是领域事件？🤔

### 定义与作用

领域事件是指在某个领域中已经发生的**事实**，它不可更改，是系统业务逻辑的自然输出。通过领域事件，我们可以显式地表达业务逻辑中的副作用，并实现多个聚合之间的解耦。

### 核心优势

- **分离关注点**：将核心领域逻辑与副作用处理分离，提高代码的可维护性。
- **触发跨聚合的副作用**：支持内部多个聚合之间的通信。
- **提升可扩展性**：通过订阅领域事件，可以轻松地扩展系统功能。

---

## 领域事件 VS 集成事件 📤

虽然领域事件与集成事件在语义上都表示过去发生的事情，但它们的**意图和应用场景**有所不同：

| 特性         | 领域事件           | 集成事件                      |
| ------------ | ------------------ | ----------------------------- |
| **适用范围** | 单一领域内         | 跨子系统、微服务              |
| **传输方式** | 内存消息总线       | 消息队列（如RabbitMQ、Kafka） |
| **处理方式** | 同步或异步         | 完全异步                      |
| **目的**     | 触发领域内的副作用 | 通知其他系统                  |

示例：领域事件可以用来更新订单状态，而集成事件则可以通知库存系统减少库存。

---

## 如何实现领域事件 🌟

### 设计领域事件的基本原则

1. **不可变性**：领域事件是事实，应该具备不可变性。
2. **命名约定**：使用过去时态命名事件，例如`OrderCompletedDomainEvent`。
3. **信息设计**：根据业务需求决定领域事件的“胖瘦”，即事件中包含的信息量。

#### 示例代码：定义领域事件

使用`MediatR`库实现领域事件的抽象：

```csharp
using MediatR;

public interface IDomainEvent : INotification
{
}
```

定义具体的领域事件：

```csharp
public class CourseCompletedDomainEvent : IDomainEvent
{
    public Guid CourseId { get; init; }
}
```

---

## 从领域中触发事件 🚀

### 实现领域事件的触发机制

通过创建一个`Entity`基类来管理领域事件的触发和存储：

```csharp
public abstract class Entity : IEntity
{
    private readonly List<IDomainEvent> _domainEvents = new();

    public IReadOnlyList<IDomainEvent> GetDomainEvents()
    {
        return _domainEvents.ToList();
    }

    public void ClearDomainEvents()
    {
        _domainEvents.Clear();
    }

    protected void RaiseDomainEvent(IDomainEvent domainEvent)
    {
        _domainEvents.Add(domainEvent);
    }
}
```

在实体中触发领域事件：

```csharp
public class Course : Entity
{
    public Guid Id { get; private set; }

    public void Complete()
    {
        RaiseDomainEvent(new CourseCompletedDomainEvent { CourseId = this.Id });
    }
}
```

---

## 使用EF Core发布领域事件 📡

EF Core作为一个强大的ORM工具，可以用来发布领域事件。通过重写`SaveChangesAsync`方法，我们可以在保存数据库记录后发布领域事件。

### 发布时机的选择

1. **保存前**：领域事件与数据库保存共享事务，保证立即一致性。
2. **保存后**：领域事件单独事务，支持最终一致性（推荐）。

#### 示例代码：发布领域事件

```csharp
public class ApplicationDbContext : DbContext
{
    public override async Task<int> SaveChangesAsync(
        CancellationToken cancellationToken = default)
    {
        var result = await base.SaveChangesAsync(cancellationToken);
        await PublishDomainEventsAsync();
        return result;
    }

    private async Task PublishDomainEventsAsync()
    {
        var domainEvents = ChangeTracker
            .Entries<Entity>()
            .Select(entry => entry.Entity)
            .SelectMany(entity =>
            {
                var domainEvents = entity.GetDomainEvents();
                entity.ClearDomainEvents();
                return domainEvents;
            })
            .ToList();

        foreach (var domainEvent in domainEvents)
        {
            await _publisher.Publish(domainEvent);
        }
    }
}
```

---

## 使用MediatR处理领域事件 🛠️

MediatR提供了方便的发布-订阅模式，可以轻松实现领域事件的处理逻辑。

### 示例代码：事件处理器

```csharp
public class CourseCompletedDomainEventHandler
    : INotificationHandler<CourseCompletedDomainEvent>
{
    private readonly IBus _bus;

    public CourseCompletedDomainEventHandler(IBus bus)
    {
        _bus = bus;
    }

    public async Task Handle(
        CourseCompletedDomainEvent domainEvent,
        CancellationToken cancellationToken)
    {
        await _bus.Publish(
            new CourseCompletedIntegrationEvent(domainEvent.CourseId),
            cancellationToken);
    }
}
```

---

## 一致性问题与Outbox模式 📦

### 为什么需要Outbox模式？

在领域事件发布后，如果事件处理失败可能导致系统状态的不一致。Outbox模式通过将事件存储到数据库的单独表中，确保领域事件与业务数据的原子性。

### Outbox模式的工作流程

1. 在数据库中保存业务数据和领域事件。
2. 使用后台任务异步处理事件。
3. 确保事件的可靠交付。

---

## 结尾总结 🙌

领域事件是构建松耦合系统的重要工具，能有效分离核心业务逻辑与副作用处理。通过结合EF Core和MediatR，我们可以轻松实现领域事件的发布与订阅。虽然领域事件的最终一致性带来了挑战，但使用Outbox模式可以很好地解决这一问题。

### 互动环节 🎯

你认为领域事件在构建分布式系统中的未来应用场景有哪些？欢迎在评论区留言讨论！

👉 如果你喜欢这篇文章，记得点赞、收藏并分享给你的开发朋友们！

🚀 更多技术干货，欢迎关注我们的公众号！
