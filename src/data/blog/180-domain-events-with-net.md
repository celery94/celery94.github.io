---
pubDatetime: 2024-10-06
tags: [".NET", "AI"]
source: https://developmentwithadot.blogspot.com/2024/10/domain-events-with-net.html
author: Ricardo Peres
title: Domain Events with .NET
description: Introduction Domain Events  is a pattern and concept made popular by Domain Driven Design . A Domain Event is something that happened on you...
---

## 引言

[领域事件](https://martinfowler.com/eaaDev/DomainEvent.html) 是一种由[领域驱动设计](https://en.wikipedia.org/wiki/Domain-driven_design)普及的模式和概念。领域事件是指系统中发生的某件事情，并希望让相关方知晓。这是一种以解耦的、通常是异步的方式发布信息的方法。发布者发布（引发）一个事件，而感兴趣的订阅者接收通知并据此采取行动。当然，订阅者也可以是发布者。

在这篇文章中，我将介绍一个用于 .NET 的领域事件库。这不是我第一次写关于在应用程序中解耦消息和订阅者的文章，几年前我实现了[Postal.NET](https://asp-blogs.azurewebsites.net/ricardoperes/Tags/Postal.NET)库，该库实现了类似的功能。

请注意，目前有很多实现，[MediatR](https://github.com/jbogard/MediatR)是首先想到的，但这是我的实现。我显然从其他实现中获得了一些想法，但我的实现与其他所有实现有实质性的不同。

## 概念

首先，介绍一些概念：

- **事件**：实现了 **IDomainEvent** 的某个类
- **发布者**：发布消息（事件）的地方
- **订阅者**：注册接收特定事件类型通知的地方
- **中介**：链接发布者和订阅者的桥梁
- **订阅**：对事件处理程序的具体注册
- **调度器**：实际调用订阅处理程序的地方
- **拦截器**：在事件发送给订阅者之前和之后可以对事件进行操作的处理程序

首先，声明一个用于标记领域事件的接口 **IDomainEvent**：

```csharp
public interface IDomainEvent { }
```

如你所见，这只是用于将某个类标记为领域事件。当然，你的事件类可以是任意复杂的。

现在来看发布者，**IEventsPublisher**：

```csharp
public interface IEventsPublisher
{
    Task Publish<TEvent>(TEvent @event, CancellationToken cancellationToken = default) where TEvent : IDomainEvent;
}
```

依然相当简单，它仅声明了一个泛型方法 **Publish**，泛型参数是一个领域事件。**Publish** 方法被声明为异步的。

订阅者是 **IEventsSubscriber**：

```csharp
public interface IEventsSubscriber
{
    Subscription Subscribe<TEvent>(Action<TEvent> action) where TEvent : IDomainEvent;
}
```

同样很简单：**Subscribe** 泛型方法接受一个泛型动作委托（[Action<T>](https://learn.microsoft.com/en-us/dotnet/api/system.action-1)）并返回一个 **Subscription** 实例。每当发布 **TEvent** 类型的事件时，该动作将被调用。

中介是 **IEventsMediator**：

```csharp
public interface IEventsMediator
{
    Task Publish<TEvent>(TEvent @event, CancellationToken cancellationToken = default) where TEvent : IDomainEvent;

    Subscription Subscribe<TEvent>(Action<TEvent> action) where TEvent : IDomainEvent;

    bool Unsubscribe(Subscription subscription);

    void AddInterceptor(IDomainEventInterceptor interceptor);
}
```

如你所见，**IEventsMediator** 接口有一些来自 **IEventsSubscriber** 和 **IEventsPublisher** 的方法，还有一些取消订阅和注册拦截器的方法。它将作为不同类之间的中介。然而，你不应该直接触碰这些方法，除了 **AddInterceptor**。

订阅是由类 **Subscription** 实现的，该类是 [可释放的](https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/dispose-pattern)：

```csharp
public class Subscription : IDisposable
{
    //细节在此不包括
}
```

这个类是可释放的原因是，如果我们想取消现有的订阅，只需调用其 [Dispose](https://learn.microsoft.com/en-us/dotnet/api/system.idisposable.dispose) 方法。这是一个 [不透明引用](https://en.wikipedia.org/wiki/Opaque_pointer)，你不用担心其内容。

接近尾声，这里是 **IEventsDispatcher** 接口：

```csharp
public interface IEventsDispatcher
{
    Task Dispatch<TEvent>(TEvent @event, IEnumerable<Subscription> subscriptions, CancellationToken cancellationToken = default);
}
```

这就是实际调用事件处理程序的地方，框架中包括许多实现：

- **SequentialEventsDispatcher**：同步且顺序地调用所有事件调度器
- **TaskEventsDispatcher**：异步且顺序地调用事件处理程序；这是默认的
- **ParallelEventsDispatcher**：并行调用事件处理程序
- **ThreadEventsDispatcher**：使用线程调用事件处理程序
- **ThreadPoolEventsDispatcher**：使用[管理线程池](https://learn.microsoft.com/en-us/dotnet/standard/threading/the-managed-thread-pool)中的线程调用事件处理程序

最后，拦截器 **IDomainEventInterceptor**：

```csharp
public interface IDomainEventInterceptor
{
    Task BeforePublish(IDomainEvent @event, CancellationToken cancellationToken = default);

    Task AfterPublish(IDomainEvent @event, CancellationToken cancellationToken = default);
}
```

还有一个抽象类使我们更容易：

```csharp
public abstract class DomainEventInterceptor : IDomainEventInterceptor
{
    public virtual Task BeforePublish(IDomainEvent @event, CancellationToken cancellationToken = default) { }

    public virtual Task AfterPublish(IDomainEvent @event, CancellationToken cancellationToken = default) { }
}
```

你可以继承 **DomainEventInterceptor** 并只实现你想要的方法。如你所见，**IDomainEventInterceptor** 类被设计为拦截系统中发布的所有事件，这就是为什么它接受一个 **IDomainEvent** 参数，这是所有事件必须遵循的接口。

## 使用

我们首先需要将领域事件框架注册到依赖注入（DI）中：

```csharp
builder.Services.AddDomainEvents();
```

然后，我们可以从中获取接口：

```csharp
var subscriber = serviceProvider.GetRequiredService<IEventsSubscriber>();
var publisher = serviceProvider.GetRequiredService<IEventsPublisher>();
```

当然，获取这些实例的最常见方式是通过 DI，例如，通过注入到控制器动作中：

```csharp
public async Task<IActionResult> Publish([FromServices] IEventsPublisher publisher, CancellationToken cancellationToken)
{
    await publisher.Publish(new SomeEvent(), cancellationToken);
    //...
}
```

当然，为了使其有用，我们首先需要注册一个事件处理程序：

```csharp
var subscription = subscriber.Subscribe<SomeEvent>(evt =>
{
    //处理事件
});
```

现在，每次我们发布一个事件（**Publish**），注册的处理程序将被调用。当我们不再需要它，并且不想收到更多事件通知时，我们可以取消订阅：

```csharp
subscription.Dispose();
```

如果出于某种原因，我们想要向系统添加一个拦截器，我们可以通过 **IEventsMediator** 接口来实现：正如我所说，这实际上是我们唯一需要直接访问它的时候：

```csharp
mediator.AddInterceptor(new SomeEventInterceptor());
```

这个方法接受一个拦截器实例，稍后我们将看到一种替代方法。

## 高级用法

## 类型化订阅

有时事情会更复杂。例如，假设我们想要一个合适的类来处理订阅。为此，我们有 **ISubscription<TEvent>** 接口：

```csharp
public interface ISubscription<TEvent> where TEvent : IDomainEvent
{
    Task OnEvent(TEvent @event, Subscription subscription);
}
```

**ISubscription<TEvent>** 接口指定了一个方法 **OnEvent**，该方法接收正在发布的事件以及引用的订阅。可以从此方法中安全地取消订阅，如我之前所示。这个类是由 DI 实例化的，这意味着你甚至可以向其注入其他类型。

以下是如何添加订阅的方法：

```csharp
builder.Services.AddDomainEvents()
    .AddSubscription<SomeEvent, SomeSubscription>();
```

其中 **SomeSubscription** 是一个实现了 **ISubscription<SomeEvent>** 的类。**AddSubscription** 方法可以在 **AddDomainEvents** 返回后调用。

## 类型化拦截器

我们已经了解了拦截器是如何工作的。基本上，每当事件发布时，无论它的类型是什么，都会调用拦截器。然而，如果我们想要的话，可以有一个类型化拦截器，它只针对特定事件类型调用：

```csharp
public interface IDomainEventInterceptor<TEvent> where TEvent : IDomainEvent
{
    Task OnEvent(TEvent event, Subscription subscription);
}
```

注册的方法是通过 **AddDomainEvents** 返回后的 **AddInterceptor** 调用：

```csharp
builder.Services.AddDomainEvents()
    .AddInterceptor<SomeEvent, SomeInterceptor>();
```

其中 **SomeInterceptor** 实现了 **IDomainEventInterceptor<SomeEvent>**。我没有包括 **SomeEvent** 或 **SomeInterceptor** 的代码，因为它们在这里不相关。重要的是要知道 **SomeInterceptor** 是由 DI 框架实例化的。

我们还可以通过这种方式注册一个普通（非泛型）的 **IDomainInterceptor**：

```csharp
builder.Services.AddDomainEvents()
    .AddInterceptor<SomeInterceptor>();
```

请注意，在这种情况下，这个 **AddInterceptor** 扩展方法只接受一个参数，即实现 **IDomainInterceptor** 的类型。

## 提供你自己的实现

可以为以下类型之一或多个提供你自己的实现：

- **IEventsPublisher**
- **IEventsSubscriber**
- **IEventsMediator**
- **IEventsDispatcher**

实现方法是在调用 **AddDomainEvents** / **AddDomainEventsFromAssembly** 之前在 DI 引擎上注册类型。当然，在更改这些之前，你应该知道自己在做什么！

## 自动连接类型

作为手动添加所有订阅和拦截器的替代方法，有一个扩展方法可以自动找到所有相关类型并注册它们，即 **AddDomainEventsFromAssembly**：

```csharp
builder.Services.AddDomainEventsFromAssembly(typeof(Program).Assembly);
```

具体来说，它注册了所有非抽象且非泛型的以下类型：

- **ISubscription<TEvent>**
- **IDomainEventInterceptor<TEvent>**
- **IDomainEventInterceptor**

关于这一点的最后一句话：你可以将 **AddDomainEventsFromAssembly** 与 **AddInterceptor** 和 **AddSubscription** 结合使用，例如，如果这些类型位于不同的程序集上。

## 领域事件选项

**DomainEventsOptions** 类可以用于向领域事件框架传递选项。截至目前，它包含单个属性：

```csharp
public class DomainEventsOptions
{
    public bool FailOnNoSubscribers { get; set; }
}
```

**FailOnNoSubscribers** 属性告诉框架，如果没有为特定事件注册事件处理程序，则抛出异常。设置此选项的方法是通过 **AddDomainEvents** / **AddDomainEventsFromAssembly** 方法的重载：

```csharp
builder.Services.AddDomainEvents(options =>
{
    options.FailOnNoSubscribers = true;
});
```

## 结论

就是这些。你可以通过获取 [NetDomainEvents](https://nuget.org/packages/NetDomainEvents) Nuget 包或查看 GitHub [仓库](https://github.com/rjperes/DomainEvents) 来自行查看。和往常一样，期待听到你的想法、问题、批评等！

源码： [https://github.com/rjperes/DomainEvents](https://github.com/rjperes/DomainEvents)

Nuget： [https://www.nuget.org/packages/NetDomainEvents](https://www.nuget.org/packages/NetDomainEvents)
