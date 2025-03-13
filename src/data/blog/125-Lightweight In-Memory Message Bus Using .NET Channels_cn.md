---
pubDatetime: 2024-05-02
tags:
  [
    .net,
    c#,
    messaging,
    integration-events,
    mediatr,
    channels,
    in-memory,
    message-bus,
    modular-monolith,
  ]
source: https://www.milanjovanovic.tech/blog/lightweight-in-memory-message-bus-using-dotnet-channels
author: Milan Jovanović
title: 使用.NET Channels构建轻量级内存中消息总线
description: 假设你正在构建一个模块化单体软件，这是一种软件架构，不同的组件被组织成松散耦合的模块。或者你可能需要异步处理数据。你将需要一个工具或服务来实现这一点。
---

# 使用.NET Channels构建轻量级内存中消息总线

> ## 摘要
>
> 假设你正在构建一个模块化单体软件，这是一种软件架构，不同的组件被组织成松散耦合的模块。或者你可能需要异步处理数据。你将需要一个工具或服务来实现这一点。

---

假设你正在构建一个模块化单体软件，这是一种软件架构，不同的组件被组织成松散耦合的模块。或者你可能需要异步处理数据。你将需要一个工具或服务来实现这一点。

在现代软件架构中，消息传递扮演着关键角色，使松散耦合的组件能够进行通信和协调。

内存中消息总线在高性能和低延迟是关键要求时特别有用。

在今天的问题中，我们将：

- 创建所需的消息抽象
- 使用channels构建一个内存中消息总线
- 实现一个集成事件处理器后台作业
- 演示如何异步发布和消费消息

## 何时使用内存中消息总线

我必须首先说明，内存中消息总线远非万能药。正如你即将了解到的，使用它有很多注意事项。

但首先，让我们从使用内存中消息总线的优点开始：

- 因为它在内存中工作，你可以拥有一个非常低延迟的消息系统
- 你可以实现组件之间的异步（非阻塞）通信

然而，这种方法有一些缺点：

- 如果应用程序进程崩溃，可能会丢失消息
- 它只在单个进程内工作，因此在分布式系统中不实用

内存中消息总线的一个实际用例是在构建模块化单体软件时。你可以使用集成事件实现[模块之间的通信](https://www.milanjovanovic.tech/blog/modular-monolith-communication-patterns)。当你需要将一些模块提取到一个单独的服务时，你可以用一个分布式的替换内存中的总线。

## 定义消息抽象

我们需要一些抽象来构建我们简单的消息系统。从客户端的角度来看，我们真正需要的只有两件事。一个是发布消息的抽象，另一个是定义消息处理器。

`IEventBus` 接口暴露了 `PublishAsync` 方法。这是我们用来发布消息的方法。还定义了一个泛型约束，只允许传入一个 `IIntegrationEvent` 实例。

```csharp
public interface IEventBus
{
    Task PublishAsync<T>(
        T integrationEvent,
        CancellationToken cancellationToken = default)
        where T : class, IIntegrationEvent;
}
```

我想用实际的 `IIntegrationEvent` 抽象，所以我将使用 [MediatR](https://github.com/jbogard/MediatR) 来支持 pub-sub。`IIntegrationEvent` 接口将继承自 `INotification`。这使我们能够使用 `INotificationHandler<T>` 轻松定义 `IIntegrationEvent` 处理器。此外，`IIntegrationEvent` 有一个标识符，所以我们可以跟踪它的执行。

抽象的 `IntegrationEvent` 作为具体实现的基类。

```csharp
using MediatR;

public interface IIntegrationEvent : INotification
{
    Guid Id { get; init; }
}

public abstract record IntegrationEvent(Guid Id) : IIntegrationEvent;
```

## 使用Channels的简单内存队列

`System.Threading.Channels` 命名空间提供了数据结构，用于异步在生产者和消费者之间传递消息。Channels实现了[生产者/消费者模式](https://en.wikipedia.org/wiki/Producer%E2%80%93consumer_problem)。生产者异步产生数据，消费者异步消费这些数据。这是构建松散耦合系统的基本模式之一。

采用 [.NET Channels](https://learn.microsoft.com/en-us/dotnet/core/extensions/channels) 的主要动机之一是它们出色的性能特征。与传统消息队列不同，Channels 完全在内存中操作。这有一个缺点，即如果应用崩溃，可能会导致消息丢失。

`InMemoryMessageQueue` 使用 `Channel.CreateUnbounded` 创建了一个无界的通道。这意味着通道可以有任意数量的读写者。它还暴露了一个 `ChannelReader` 和 `ChannelWriter`，允许消费者发布和消费消息。

```csharp
internal sealed class InMemoryMessageQueue
{
    private readonly Channel<IIntegrationEvent> _channel =
        Channel.CreateUnbounded<IIntegrationEvent>();

    public ChannelReader<IIntegrationEvent> Reader => _channel.Reader;

    public ChannelWriter<IIntegrationEvent> Writer => _channel.Writer;
}
```

你还需要将 `InMemoryMessageQueue` 作为单例注册到依赖注入中：

```csharp
builder.Services.AddSingleton<InMemoryMessageQueue>();
```

## 实现EventBus

现在，利用channels，`IEventBus` 的实现就很简单了。`EventBus` 类使用 `InMemoryMessageQueue` 来访问 `ChannelWriter` 并将事件写入通道。

```csharp
internal sealed class EventBus(InMemoryMessageQueue queue) : IEventBus
{
    public async Task PublishAsync<T>(
        T integrationEvent,
        CancellationToken cancellationToken = default)
        where T : class, IIntegrationEvent
    {
        await queue.Writer.WriteAsync(integrationEvent, cancellationToken);
    }
}
```

我们将以无状态的方式注册 `EventBus` 为单例服务，因为它无状态：

```csharp
builder.Services.AddSingleton<IEventBus, EventBus>();
```

## 消费集成事件

有了实现生产者的 `EventBus`，我们需要一种方式来消费发布的 `IIntegrationEvent`。我们可以使用内置的 `IHostedService` 抽象实现一个简单的[后台服务](https://www.milanjovanovic.tech/blog/running-background-tasks-in-asp-net-core)。

`IntegrationEventProcessorJob` 依赖于 `InMemoryMessageQueue`，但这次是为了读取（消费）消息。我们将使用 `ChannelReader.ReadAllAsync` 方法来获取一个 `IAsyncEnumerable`。这允许我们异步消费 `Channel` 中的所有消息。

`IPublisher` 来自 MediatR，帮助我们将 `IIntegrationEvent` 与相应的处理器连接起来。如果你想向事件处理程序注入作用域服务，重要的是要从自定义作用域解析它。

```csharp
internal sealed class IntegrationEventProcessorJob(
    InMemoryMessageQueue queue,
    IServiceScopeFactory serviceScopeFactory,
    ILogger<IntegrationEventProcessorJob> logger)
    : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await foreach (IIntegrationEvent integrationEvent in
            queue.Reader.ReadAllAsync(stoppingToken))
        {
            try
            {
                using IServiceScope scope = serviceScopeFactory.CreateScope();

                IPublisher publisher = scope.ServiceProvider
                    .GetRequiredService<IPublisher>();

                await publisher.Publish(integrationEvent, stoppingToken);
            }
            catch (Exception ex)
            {
                logger.LogError(
                    ex,
                    "Something went wrong! {IntegrationEventId}",
                    integrationEvent.Id);
            }
        }
    }
}
```

别忘了注册托管服务：

```csharp
builder.Services.AddHostedService<IntegrationEventProcessorJob>();
```

## 使用内存中消息总线

有了所有必要的抽象，我们最终可以使用内存中消息总线了。

`IEventBus` 服务将消息写入 `Channel` 并立即返回。这允许你以非阻塞方式发布消息，这可以提高性能。

```csharp
internal sealed class RegisterUserCommandHandler(
    IUserRepository userRepository,
    IEventBus eventBus)
    : ICommandHandler<RegisterUserCommand>
{
    public async Task<User> Handle(
        RegisterUserCommand command,
        CancellationToken cancellationToken)
    {
        // 首先，注册用户。
        User user = CreateFromCommand(command);

        userRepository.Insert(user);

        // 现在我们可以发布事件了。
        await eventBus.PublishAsync(
            new UserRegisteredIntegrationEvent(user.Id),
            cancellationToken);

        return user;
    }
}
```

这解决了生产者方面，但我们还需要为 `UserRegisteredIntegrationEvent` 消息创建一个消费者。因为我在这个实现中使用了 MediatR，这部分被极大地简化了。

我们需要为处理集成事件 `UserRegisteredIntegrationEvent` 定义一个 `INotificationHandler` 实现。这将是 `UserRegisteredIntegrationEventHandler`。

当后台作业从 `Channel` 读取 `UserRegisteredIntegrationEvent` 时，它将发布消息并执行处理程序。

```csharp
internal sealed class UserRegisteredIntegrationEventHandler
    : INotificationHandler<UserRegisteredIntegrationEvent>
{
    public async Task Handle(
        UserRegisteredIntegrationEvent event,
        CancellationToken cancellationToken)
    {
        // 异步处理事件。
    }
}
```

## 改进点

虽然我们的基本内存中消息总线是可行的，但有几个领域我们可以改进：

- **弹性** - 当我们遇到异常时，我们可以引入重试，这将提高消息总线的可靠性。
- **幂等性** - 问问自己是否想要处理相同的消息两次。[幂等消费者模式](https://www.milanjovanovic.tech/blog/idempotent-consumer-handling-duplicate-messages) 优雅地解决了这个问题。
- **死信队列** - 有时，我们可能无法正确处理消息。引入一个这些消息的持久存储是个好主意。这被称为[死信队列](https://aws.amazon.com/what-is/dead-letter-queue/)，它允许我们在以后进行故障排查。

我们已经讨论了使用 .NET Channels 构建内存中消息总线的关键方面。你可以通过实施改进来进一步扩展这一点，以获得更健壮的解决方案。

记住，这个实现只在一个进程内工作。如果你需要更可靠的解决方案，请考虑使用真正的消息代理。
