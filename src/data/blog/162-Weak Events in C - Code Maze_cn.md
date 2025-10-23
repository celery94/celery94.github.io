---
pubDatetime: 2024-06-11
tags: [".NET", "C#"]
source: https://code-maze.com/csharp-weak-events/
author: Satya Prakash
title: Weak Events in C#
description: Weak events in C# are used to prevent memory leaks in event-driven applications. Let's explore weak events and how to implement them.
---

# Weak Events in C#

> ## Excerpt
>
> Weak events in C# are used to prevent memory leaks in event-driven applications. Let's explore weak events and how to implement them.

---

我们在C#中使用弱事件来避免基于事件的应用程序中的内存泄漏。让我们进一步了解什么是弱事件，为什么需要它们，以及如何实现它们。

您可以访问我们的[GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/csharp-advanced-topics/WeakEventsInCSharp)下载这篇文章的源代码。

让我们开始吧。

## 什么是强事件和弱事件？

强[事件](https://code-maze.com/csharp-events/)是C#中事件的默认实现。它使对象能够在发生变化时通知其他对象。

让我们通过创建一个`Publisher`类来实际看一下：

```csharp
public class Publisher
{
    public event EventHandler? Event;
    public void RaiseEvent()
    {
        Event?.Invoke(this, EventArgs.Empty);
    }
}
```

现在，让我们创建一个`Subscriber`类来订阅`Event`事件：

```csharp
public class Subscriber
{
    public void HandleEvent(object sender, EventArgs e)
    {
        Console.WriteLine("Event received.");
    }
}
```

**当订阅事件时，我们在发布者和订阅者之间创建了一个强引用。这种强引用不允许[垃圾收集器（GC）](https://code-maze.com/csharp-managed-vs-unmanaged-code-garbage-collection/)收集订阅者对象，因为发布者仍然存在（即GC尚未收集它）。**

另一方面，**当创建弱事件时，事件处理程序在发布者和订阅者之间创建了一个弱引用。弱引用允许GC在没有其他强引用时收集对象。**

当我们触发一个事件时，弱引用会检查目标（订阅者）是否仍然存在。如果存在，应用程序会调用事件处理程序。然而，如果目标已被收集，则弱引用从事件处理程序列表中移除。

## 我们为什么需要弱事件？

要理解为什么我们需要弱事件，我们需要回顾默认事件的实现。

让我们想象一个数据提供服务，它会定期触发事件以更新应用程序UI的一部分。`Publisher`类可以代表这个服务，而`Subscriber`类则代表UI组件。

当这些UI组件订阅服务的事件时，服务对每个UI组件中的事件处理程序持有强引用。如果我们假设用户可以按需移除这些UI组件，我们会希望GC在这些组件不再需要时释放内存。

然而，由于服务持有强引用，GC无法回收这些UI组件使用的内存。这导致了内存泄漏：

```csharp
var publisher = new Publisher();
var subscriber = new Subscriber();
publisher.Event += subscriber.HandleEvent;
publisher.RaiseEvent();
subscriber = null;
GC.Collect();
publisher.RaiseEvent();
```

在这里，我们通过将`subscriber`对象显式设置为`null`来模拟组件的移除。然后，我们使用`GC.Collect()`方法强制进行垃圾收集。然而，由于`publisher`持有强引用，它仍然不适合垃圾收集。

当我们运行应用程序时，它在垃圾收集过程之后仍会触发事件：

```bash
Event received.
Event received.
```

**通过使用弱引用，我们确保事件订阅不会阻止订阅者的垃圾收集。**因此，弱事件通过确保对象在不再需要时被收集来更有效地管理内存。

## 如何实现弱事件

我们可以使用`WeakReference`类来实现一个弱事件机制。`WeakReference`类对对象持有一个弱引用。这确保了应用程序在没有其他强引用时不会阻止垃圾收集器收集对象。

让我们创建一个`WeakEvent`类：

```csharp
public class WeakEvent<TEventArgs> where TEventArgs : EventArgs
{
    private readonly List<WeakReference<EventHandler<TEventArgs>>> _eventHandlers = [];
}
```

\_eventHandlers字段维护一组对事件处理程序的弱引用。这使订阅者能够订阅发布者触发的事件，而不创建强引用：

接下来，让我们添加一个`AddEventHandler()`方法以添加事件处理程序：

```csharp
public void AddEventHandler(EventHandler<TEventArgs> handler)
{
    if (handler == null) return;
    _eventHandlers.Add(new WeakReference<EventHandler<TEventArgs>>(handler));
}
```

另一个`RemoveEventHandler()`方法用于移除事件处理程序：

```csharp
public void RemoveEventHandler(EventHandler<TEventArgs> handler)
{
    var eventHandler = _eventHandlers.FirstOrDefault(wr =>
    {
        wr.TryGetTarget(out var target);
        return target == handler;
    });
    if (eventHandler != null)
    {
        _eventHandlers.Remove(eventHandler);
    }
}
```

最后，添加一个`RaiseEvent()`方法：

```csharp
public void RaiseEvent(object sender, TEventArgs e)
{
    foreach (var eventHandler in _eventHandlers.ToArray())
    {
        if (eventHandler.TryGetTarget(out var handler))
        {
            handler(sender, e);
        }
    }
}
```

此方法通过调用所有订阅的事件处理程序来触发事件。我们使用`TryGetTarget()`方法来检索目标事件处理程序。如果成功，它会使用提供的发送者和事件参数调用事件处理程序。

现在，创建一个`WeakReferenceSubscriber`类作为我们的订阅者：

```csharp
public class WeakReferenceSubscriber
{
    public void Subscribe(WeakReferencePublisher publisher)
    {
        publisher.Event.AddEventHandler(HandleEvent);
    }
    public void HandleEvent(object? sender, EventArgs e)
    {
        Console.WriteLine("Weak Event received.");
    }
}
```

这将订阅`WeakReferencePublisher`类：

```csharp
public class WeakReferencePublisher
{
    public WeakEvent<EventArgs> Event { get; } = new WeakEvent<EventArgs>();
    public void RaiseEvent()
    {
        Event.RaiseEvent(this, EventArgs.Empty);
    }
}
```

现在，如果我们在移除订阅者后尝试触发事件，应用程序不会触发后续事件：

```csharp
var weakEventPublisher = new WeakReferencePublisher();
var weakEventSubscriber = new WeakReferenceSubscriber();
weakEventSubscriber.Subscribe(weakEventPublisher);
weakEventPublisher.RaiseEvent();
weakEventSubscriber = null;
GC.Collect();
weakEventPublisher.RaiseEvent();
```

弱引用允许GC收集不再存活的订阅者对象：

```bash
Weak Event received.
```

这防止了我们在默认事件实现中遇到的内存泄漏。

## 结论

在本文中，我们了解了C#中的弱事件。我们看到了它们如何提供一种处理事件而不创建强引用的方法。通过使用弱引用，我们可以确保垃圾收集器在不需要时从内存中移除订阅者对象。
