---
pubDatetime: 2024-04-10
tags: ["Productivity", "Tools"]
source: https://www.milanjovanovic.tech/blog/how-to-use-ef-core-interceptors?utm_source=Twitter&utm_medium=social&utm_campaign=08.04.2024
author: Milan Jovanović
title: 如何使用 EF Core 拦截器
description:
  EF Core 是我最喜欢的 .NET 应用程序的 ORM。然而，它许多极好的特性有时候会被忽视。例如，查询分割、查询过滤器和拦截器。
  EF 拦截器很有趣，因为你可以用它们做强大的事情。例如，你可以接入物化操作、处理乐观并发错误或添加查询提示。
  最实用的用例是在向数据库保存更改时添加行为。
---

# 如何使用 EF Core 拦截器

> ## 摘要
>
> EF Core 是我最喜欢的 .NET 应用程序的 ORM。然而，它许多极好的特性有时候会被忽视。例如，查询分割、查询过滤器和拦截器。
> EF 拦截器很有趣，因为你可以用它们做强大的事情。例如，你可以接入物化操作、处理乐观并发错误或添加查询提示。
> 最实用的用例是在向数据库保存更改时添加行为。
>
> 原文 [How To Use EF Core Interceptors](https://www.milanjovanovic.tech/blog/how-to-use-ef-core-interceptors?utm_source=Twitter&utm_medium=social&utm_campaign=08.04.2024) 作者 [Milan Jovanović](https://www.milanjovanovic.tech/)

---

EF Core 是我最喜欢的 .NET 应用程序的 ORM。然而，它许多极好的特性有时候会被忽视。例如，[**查询分割**](https://www.milanjovanovic.tech/blog/how-to-improve-performance-with-ef-core-query-splitting)、[**查询过滤器**](https://www.milanjovanovic.tech/blog/how-to-use-global-query-filters-in-ef-core)和拦截器。

EF 拦截器很有趣，因为你可以用它们做强大的事情。例如，你可以接入物化操作、处理乐观并发错误或添加查询提示。

最实用的用例是在向数据库保存更改时添加行为。

今天我想向你展示三个独特的 EF Core 拦截器用例：

- 审计日志
- 发布域事件
- 持久化邮箱消息

## [什么是 EF 拦截器？](https://www.milanjovanovic.tech/blog/how-to-use-ef-core-interceptors?utm_source=Twitter&utm_medium=social&utm_campaign=08.04.2024#what-are-ef-interceptors)

[EF Core 拦截器](https://learn.microsoft.com/en-us/ef/core/logging-events-diagnostics/interceptors)允许你拦截、更改或抑制 EF Core 操作。每个拦截器实现 `IInterceptor` 接口。一些常见的派生接口包括 `IDbCommandInterceptor`、`IDbConnectionInterceptor` 和 `IDbTransactionInterceptor`。

最受欢迎的是 `ISaveChangesInterceptor`。它允许你在保存更改前后添加行为。

拦截器在配置上下文时为每个 `DbContext` 实例注册。

```csharp
public interface IInterceptor { }
```

你不必直接实现这些接口。最好使用具体实现并重写需要的方法。

例如，我将向你展示如何使用 `SaveChangesInterceptor`。

## 使用 EF 拦截器进行审计日志

在某些应用程序中，实体更改的审计日志是一个有价值的功能。每次创建或修改实体时，你都会写入额外的审计信息。审计日志还可以包含完整的前/后值，具体取决于你的需求。

然而，让我们用一个简单的例子来使它易于理解。

我有一个 `IAuditable` 接口，包含两个代表实体何时被创建或修改的属性。

```csharp
public interface IAuditable
{
    DateTime CreatedOnUtc { get; }

    DateTime? ModifiedOnUtc { get; }
}
```

接下来，我将实现一个 `UpdateAuditableInterceptor` 拦截器来写入审计值。它使用 `ChangeTracker` 来找到所有的 `IAuditable` 实例并设置相应的属性值。

我想强调的是，我在这里重写了 `SavingChangesAsync` 方法。`SavingChangesAsync` 在数据库保存更改之前运行，并且在 `UpdateAuditableInterceptor` 中应用的任何更新也是当前数据库事务的一部分。

这个实现可以很容易地扩展以包含有关当前用户的信息。

```csharp
internal sealed class UpdateAuditableInterceptor : SaveChangesInterceptor
{
    public override ValueTask<InterceptionResult<int>> SavingChangesAsync(
        DbContextEventData eventData,
        InterceptionResult<int> result,
        CancellationToken cancellationToken = default)
    {
        if (eventData.Context is not null)
        {
            UpdateAuditableEntities(eventData.Context);
        }

        return base.SavingChangesAsync(eventData, result, cancellationToken);
    }

    private static void UpdateAuditableEntities(DbContext context)
    {
        DateTime utcNow = DateTime.UtcNow;
        var entities = context.ChangeTracker.Entries<IAuditable>().ToList();

        foreach (EntityEntry<IAuditable> entry in entities)
        {
            if (entry.State == EntityState.Added)
            {
                SetCurrentPropertyValue(
                    entry, nameof(IAuditable.CreatedOnUtc), utcNow);
            }

            if (entry.State == EntityState.Modified)
            {
                SetCurrentPropertyValue(
                    entry, nameof(IAuditable.ModifiedOnUtc), utcNow);
            }
        }

        static void SetCurrentPropertyValue(
            EntityEntry entry,
            string propertyName,
            DateTime utcNow) =>
            entry.Property(propertyName).CurrentValue = utcNow;
    }
}
```

## 使用 EF 拦截器发布域事件

EF 拦截器的另一个用例是[**发布域事件。**](https://www.milanjovanovic.tech/blog/how-to-use-domain-events-to-build-loosely-coupled-systems) 域事件是一个 DDD 战术模式，用于创建松耦合系统。

域事件允许你显式地表达副作用，并在域中提供更好的关注点分离。

你可以创建一个从 `MediatR.INotification` 派生的 `IDomainEvent` 接口。这允许你使用 `IPublisher` 来发布域事件并异步处理它们。

```csharp
using MediatR;

public interface IDomainEvent : INotification
{
}
```

然后，我将创建一个 `PublishDomainEventsInterceptor`，它也继承自 `SaveChangesInterceptor`。然而，这次我们在数据库保存更改之后使用 `SavedChangesAsync` 来发布域事件。

这有两个重要的意义：

1.  整个工作流现在最终是一致的。域事件处理器将在原始事务完成后保存更改到数据库。
2.  如果任何域事件处理器失败，我们冒着请求失败的风险，即使初始事务已经成功完成。

你可以通过使用[**邮箱**](https://www.milanjovanovic.tech/blog/outbox-pattern-for-reliable-microservices-messaging)使这个过程更可靠。

```csharp
internal sealed class PublishDomainEventsInterceptor : SaveChangesInterceptor
{
    private readonly IPublisher _publisher;

    public PublishDomainEventsInterceptor(IPublisher publisher)
    {
        _publisher = publisher;
    }

    public override async ValueTask<int> SavedChangesAsync(
        SaveChangesCompletedEventData eventData,
        int result,
        CancellationToken cancellationToken = default)
    {
        if (eventData.Context is not null)
        {
            await PublishDomainEventsAsync(eventData.Context);
        }

        return result;
    }

    private async Task PublishDomainEventsAsync(DbContext context)
    {
        var domainEvents = context
            .ChangeTracker
            .Entries<Entity>()
            .Select(entry => entry.Entity)
            .SelectMany(entity =>
            {
                List<IDomainEvent> domainEvents = entity.DomainEvents;

                entity.ClearDomainEvents();

                return domainEvents;
            })
            .ToList();

        foreach (IDomainEvent domainEvent in domainEvents)
        {
            await _publisher.Publish(domainEvent);
        }
    }
}
```

## 使用 EF 拦截器存储邮箱消息

与其作为 EF 事务的一部分[**发布域事件**](https://www.milanjovanovic.tech/blog/how-to-use-domain-events-to-build-loosely-coupled-systems)，不如将它们转换为邮箱消息。

这里有一个 `InsertOutboxMessagesInterceptor` 正是做这件事。

它重写了 `SavingChangesAsync` 方法。这意味着它在当前的 EF 事务中运行，保存更改之前。

`InsertOutboxMessagesInterceptor` 将任何域事件转换为 `OutboxMessage` 并将其添加到相应的 `DbSet<OutboxMessage>` 中。这意味着它们将与同一事务中的任何现有更改一起保存到数据库中。

这是一个原子操作。

要么一切都成功，要么一切都失败。

没有 `PublishDomainEventsInterceptor` 中的中间状态。

然后你可以创建一个后台工作器来处理邮箱消息。

这就是你如何使用 EF Core 实现[**邮箱模式**](https://www.milanjovanovic.tech/blog/outbox-pattern-for-reliable-microservices-messaging)。

```csharp
using Newtonsoft.Json;

public sealed class InsertOutboxMessagesInterceptor : SaveChangesInterceptor
{
    private static readonly JsonSerializerSettings Serializer = new()
    {
        TypeNameHandling = TypeNameHandling.All
    };

    public override ValueTask<InterceptionResult<int>> SavingChangesAsync(
        DbContextEventData eventData,
        InterceptionResult<int> result,
        CancellationToken cancellationToken = default)
    {
        if (eventData.Context is not null)
        {
            InsertOutboxMessages(eventData.Context);
        }

        return base.SavingChangesAsync(eventData, result, cancellationToken);
    }

    private static void InsertOutboxMessages(DbContext context)
    {
        context
            .ChangeTracker
            .Entries<Entity>()
            .Select(entry => entry.Entity)
            .SelectMany(entity =>
            {
                List<IDomainEvent> domainEvents = entity.DomainEvents;

                entity.ClearDomainEvents();

                return domainEvents;
            })
            .Select(domainEvent => new OutboxMessage
            {
                Id = domainEvent.Id,
                OccurredOnUtc = domainEvent.OccurredOnUtc,
                Type = domainEvent.GetType().Name,
                Content = JsonConvert.SerializeObject(domainEvent, Serializer)
            })
            .ToList();

        context.Set<OutboxMessage>().AddRange(outboxMessages);
    }
}
```

## 使用依赖注入配置 EF 拦截器

EF 拦截器应该是轻量级且无状态的。你可以通过调用 `AddInterceptors` 并传入拦截器实例将它们添加到 `DbContext` 中。

我喜欢使用依赖注入来配置拦截器有两个原因：

- 它也允许我在拦截器中使用 DI（请注意它们是单例）
- 简化使用 `AddDbContext` 将拦截器添加到 `DbContext` 的操作

这里是如何将 `UpdateAuditableInterceptor` 和 `InsertOutboxMessagesInterceptor` 与 `ApplicationDbContext` 配置的示例：

```csharp
services.AddSingleton<UpdateAuditableInterceptor>();
services.AddSingleton<InsertOutboxMessagesInterceptor>();

services.AddDbContext<IApplicationDbContext, ApplicationDbContext>(
    (sp, options) => options
        .UseSqlServer(connectionString)
        .AddInterceptors(
            sp.GetRequiredService<UpdateAuditableInterceptor>(),
            sp.GetRequiredService<InsertOutboxMessagesInterceptor>()));
```

## 结束语

拦截器允许你对 EF Core 操作几乎做任何事情。但是，拥有巨大的力量也伴随着巨大的责任。你应该意识到拦截器会影响性能。向外部服务的调用或处理事件会减慢操作速度。

记住，你不必一定要使用 EF 拦截器。通过重写 `DbContext` 上的 `SaveChangesAsync` 方法并添加你的自定义逻辑，你可以实现相同的行为。

我在本周的问题中向你展示了几个实用的 EF 拦截器用例。

但是，如果你想看到更多示例，我还有一些视频关于：

- [**审计日志**](https://youtu.be/mAlO3OuoQvo)
- [**发布域事件**](https://youtu.be/AHzWJ_SMqLo)
- [**实现邮箱模式**](https://youtu.be/XALvnX7MPeo)

---
