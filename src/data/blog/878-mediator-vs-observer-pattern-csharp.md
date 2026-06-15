---
pubDatetime: 2026-06-15T08:05:42+08:00
title: "Mediator 与 Observer 模式对比：C# 中如何选对对象通信方式"
description: "当多个对象需要通信时，Mediator 和 Observer 两种模式都能降低耦合，但实现思路截然不同。本文用同一套订单通知系统，从通信模型、耦合结构、路由能力、扩展性和 C# 原生支持几个维度做对比，帮你判断什么时候该用集中协调，什么时候该用广播通知。"
tags: ["C#", "设计模式", "Mediator", "Observer", ".NET"]
slug: "mediator-vs-observer-pattern-csharp"
ogImage: "../../assets/878/01-cover.png"
source: "https://www.devleader.ca/2026/06/14/mediator-vs-observer-pattern-in-c-key-differences-explained"
---

当两个或多个对象需要互相通信，你有两种主流的做法：把通信逻辑装进一个中心协调器，或者让消息源向所有订阅者广播。前者是 Mediator（中介者）模式，后者是 Observer（观察者）模式。

二者都能解决对象之间的耦合问题，但它们解决的方式完全不同。选错了模式，你会发现自己一直在跟设计较劲，而不是从中受益。

这篇文章用同一个订单通知系统的场景，把两种模式各实现一遍，然后从通信模型、耦合结构、路由能力、扩展性和 C# 内建支持这五个维度帮你理清在什么情况下该用哪种。

---

## Mediator 模式：集中协调

Mediator 模式的核心是一个中心协调器，负责管理多个参与者（Participant / Colleague）之间的通信。参与者之间不直接对话，所有消息都走协调器中转——它接收消息、执行路由逻辑、再把消息投递给目标对象。

参与者只知道协调器的接口，彼此之间没有直接引用。这种设计把一张复杂的多对多网状关系压成了一颗干净的中心星型拓扑。当交互规则需要调整时，你只改一处，而不是在各处散落的依赖里翻找。

Form 对话框是典型的例子：勾选一个 checkbox 要禁用某个 text field、触发另一处的校验、还要有条件地显示提交按钮。如果没有中心协调器，每个 UI 组件都得持有其他组件的直接引用；有了协调器，每个组件只跟一个接口打交道，协调逻辑集中管理。

---

## Observer 模式：广播通知

Observer 模式在 Subject（发布者）和它的 Subscriber（订阅者）之间建立一种一对多的依赖关系。Subject 状态变化时，挨个通知所有注册的订阅者，每个订阅者自己决定怎么响应。Subject 不知道、也不关心订阅者拿这条消息去干嘛——它负责广播，播完就过。

这种广播模型是事件驱动架构的基础。Subject 维护一个订阅者列表，提供订阅和取消订阅的方法，发布时迭代列表挨个调用。订阅者注册自己并实现一个通知接口。通信是单向的：从 Subject 向外，覆盖所有监听者。

C# 通过 `event`、`delegate` 和 `IObservable<T>` 内建支持了这种模式。这让 Observer 成为当你只需要简单发布-订阅语义时阻力最小的选择。它特别适合每个订阅者独立运作、不需要知道其他订阅者存在的场景。

---

## 核心区别：主动协调 vs 被动广播

Mediator 和 Observer 之间最根本的差异在于"谁来控制通信流向"。

**Mediator 模式里，协调器是主动参与者。** 它收到一方的消息后，做出有意识的决定：消息发给谁、什么条件下发、要不要先做变换。协调器知道所有参与者的存在，主动编排它们的交互。消息先流进中枢，中枢再选择性地分发出去。

**Observer 模式里，Subject 是被动广播者。** 它把通知推给每一个注册的订阅者，不做过滤、不设路由。Subject 不知道订阅者是谁、有多少、拿到通知后做什么。消息从 Subject 向外，均匀地流到所有接收方。

换一种比喻：Mediator 像空中交通管制员，知道每架飞机的位置和目的地，对每一架做有目的的路由；Observer 像气象广播站，发射信号，谁调对了频率都能收到同样的内容。这个区别直接决定了你的通信是"管理型"还是"广播型"。

---

## 同一场景的双实现

最直观的对比方式是把同一个需求用两种模式各写一遍。这里用订单通知系统：下单后，几个后台服务需要各自响应。

### Observer 版：事件广播

在这个版本里，`OrderService` 扮演 Subject，其他服务订阅订单事件并独立响应。`OrderService` 不知道订阅者拿通知去做什么。

```csharp
using System;
using System.Collections.Generic;

public interface IOrderObserver
{
    void OnOrderPlaced(string orderId, decimal amount);
}

public class OrderService
{
    private readonly List<IOrderObserver> _observers = new();

    public void Subscribe(IOrderObserver observer) =>
        _observers.Add(observer);

    public void Unsubscribe(IOrderObserver observer) =>
        _observers.Remove(observer);

    public void PlaceOrder(string orderId, decimal amount)
    {
        Console.WriteLine($"Order {orderId} placed for {amount:C}");

        // 向所有观察者广播
        foreach (var observer in _observers)
            observer.OnOrderPlaced(orderId, amount);
    }
}

public class InventoryService : IOrderObserver
{
    public void OnOrderPlaced(
        string orderId, decimal amount)
    {
        Console.WriteLine(
            $"  [Inventory] Reserving stock for {orderId}");
    }
}

public class EmailService : IOrderObserver
{
    public void OnOrderPlaced(
        string orderId, decimal amount)
    {
        Console.WriteLine(
            $"  [Email] Sending confirmation for {orderId}");
    }
}

public class AnalyticsService : IOrderObserver
{
    public void OnOrderPlaced(
        string orderId, decimal amount)
    {
        Console.WriteLine(
            $"  [Analytics] Recording {amount:C} sale");
    }
}
```

下单后，`OrderService` 向所有订阅者广播事件。库存服务、邮件服务、分析服务收到同样的通知，各自独立行动。`OrderService` 不协调它们的响应，也不关心执行顺序。它把事件推出去，每个订阅者在自己内部单独处理。

### Mediator 版：协调通知

在这个版本里，`OrderMediator` 扮演中心协调器。所有服务通过中介者通信，中介者决定如何路由和协调消息。

```csharp
using System;
using System.Collections.Generic;

public interface IOrderMediator
{
    void RegisterService(
        string name, IOrderParticipant service);

    void NotifyOrderPlaced(
        string orderId, decimal amount,
        IOrderParticipant sender);

    void NotifyInventoryConfirmed(
        string orderId, IOrderParticipant sender);
}

public interface IOrderParticipant
{
    void Receive(
        string eventType, string orderId, decimal amount);
}

public class OrderMediator : IOrderMediator
{
    private readonly Dictionary<string, IOrderParticipant>
        _services = new();

    public void RegisterService(
        string name, IOrderParticipant service)
    {
        _services[name] = service;
    }

    public void NotifyOrderPlaced(
        string orderId, decimal amount,
        IOrderParticipant sender)
    {
        Console.WriteLine(
            $"[Mediator] Coordinating order {orderId}");

        // 第 1 步：先锁定库存
        if (_services.TryGetValue("inventory", out var inv))
            inv.Receive("order_placed", orderId, amount);

        // 第 2 步：库存确认后发邮件
        if (_services.TryGetValue("email", out var email))
            email.Receive("order_placed", orderId, amount);

        // 第 3 步：最后记录分析数据
        if (_services.TryGetValue("analytics", out var analytics))
            analytics.Receive("order_placed", orderId, amount);
    }

    public void NotifyInventoryConfirmed(
        string orderId, IOrderParticipant sender)
    {
        // 库存确认只路由给邮件服务
        if (_services.TryGetValue("email", out var email))
            email.Receive(
                "inventory_confirmed", orderId, 0m);
    }
}

public class MediatedInventoryService : IOrderParticipant
{
    private readonly IOrderMediator _mediator;

    public MediatedInventoryService(
        IOrderMediator mediator) =>
        _mediator = mediator;

    public void Receive(
        string eventType, string orderId, decimal amount)
    {
        Console.WriteLine(
            $"  [Inventory] Reserving stock for {orderId}");

        // 通知中介者库存已确认
        _mediator.NotifyInventoryConfirmed(orderId, this);
    }
}

public class MediatedEmailService : IOrderParticipant
{
    public void Receive(
        string eventType, string orderId, decimal amount)
    {
        if (eventType == "inventory_confirmed")
        {
            Console.WriteLine(
                $"  [Email] Stock confirmed for {orderId}");
        }
        else
        {
            Console.WriteLine(
                $"  [Email] Sending confirmation for {orderId}");
        }
    }
}

public class MediatedAnalyticsService : IOrderParticipant
{
    public void Receive(
        string eventType, string orderId, decimal amount)
    {
        Console.WriteLine(
            $"  [Analytics] Recording {amount:C} sale");
    }
}
```

差异很明显。Mediator 控制执行顺序——先锁定库存、再发邮件、最后记录分析数据。它还能把库存确认事件只路由给邮件服务，而不是广播给所有人。每个服务通过中心中枢通信，而不是订阅广播。这种集中协调就是两种模式最本质的分野。

---

## 耦合的差异

两种模式都比直接对象-对象耦合要好，但解耦方向不同。

**Observer 通过事件接口耦合。** Subject 依赖 `IOrderObserver` 接口，每个订阅者实现这个接口。订阅者之间互不知晓，也不依赖 Subject 的具体实现。新增订阅者不需要改动 Subject 或已有订阅者——这点跟依赖注入通过抽象实现松耦合异曲同工。

**Mediator 通过中心中枢耦合。** 所有参与者依赖协调器接口，协调器又依赖所有参与者的接口——它知道每个参与者的存在和能力。新增参与者意味着要更新协调逻辑。代价是复杂度从分散的直接依赖集中到了一个地方，让整个通信流的理解和修改变得更容易。

取舍很清晰：Observer 将知识分散，Mediator 将知识集中。两种模式都没有消除耦合，只是把耦合搬到了不同的位置。问题在于你的系统更需要分散的独立性，还是集中的控制力。

---

## 什么时候选 Mediator

当你的通信需求涉及参与者之间的**主动协调**时，选 Mediator。

**复杂的多对多交互。** 如果多个对象之间需要互相通信，并且交互有规则、条件或顺序要求，中心协调器来兜底。N 个对象直接通信会产生 N×(N-1)/2 条连接，Mediator 压成 N 条，全部经过一个中枢。

**协调式工作流。** 当对某个事件的响应依赖于另一个参与者的状态或输出时，你需要协调逻辑。比如"给服务 A 发通知"必须发生在"服务 B 确认某件事"之后。这种情况下 Mediator 天然匹配。

**解开面条式依赖。** 当你发现一堆对象之间互相引用、通信路径绕来绕去时，引入中心协调器能解开这张网。每个对象只依赖协调器接口，系统更容易理解和测试。

**选择性路由。** 当不同消息需要根据条件到达不同接收方时，协调器的路由逻辑直接处理。Observer 没有内建的选择性投递机制——它对所有人广播一切。

---

## 什么时候选 Observer

当你的通信需求是**不需要协调的简单广播**时，选 Observer。

**一对多通知。** 当一个源头要通知多个消费者，且每个消费者独立行动时，Observer 是最自然的匹配。配置变更广播、领域事件通知、实时数据推送都是典型用例。

**最大化可扩展性。** 新增订阅者不需要改动任何已有代码。Subject 通过接口广播，任何实现该接口的类都能订阅。这种开闭原则的契合度让它特别适合订阅者预计会持续增长的场景。

**独立响应。** 每个订阅者在隔离中处理通知，不需要跟其他订阅者协调时，广播模型保持简单。每个订阅者独立封装、独立测试。

**利用 C# 语言特性。** C# 的 event 和 delegate 原生实现了 Observer 模式。如果你的通知需求能干净地映射到事件语义，用内建语言支持省去自建实现的成本。

---

## 性能与可扩展性

Observer 在增加订阅者方面扩展性好——向 N 个订阅者广播是 O(N)，新增订阅者不影响 Subject 或已有订阅者。但需要选择性通知时会出问题：向 100 个订阅者广播，实际上只有 3 个关心这件事，剩下的 97 次调用都是浪费。你可以用筛选订阅或类型化接口缓解，但会增加复杂度。

Mediator 在增加交互规则方面扩展性好——新的协调逻辑进一个地方，不用改参与者。但代价是如果协调逻辑不加节制地膨胀，协调器会变成"上帝对象"。一个协调器处理几十种消息类型和路由规则会非常难维护。

高吞吐场景下，广播模型可能更高效，因为没有中心路由开销。复杂交互场景下，协调器能短路掉或条件性地投递消息，反而减少了不必要的处理。问题在于你的瓶颈是通知量还是交互复杂度。

---

## 组合使用两种模式

Mediator 和 Observer 不是二选一。在实际系统中，两种模式经常配合。一个协调器可以在内部管理参与者交互的同时，通过事件订阅机制向外做广播。

下面的例子中，`ObservableOrderMediator` 在保持内部协调的同时，向外部监控系统广播事件：

```csharp
using System;
using System.Collections.Generic;

public interface IProcessingObserver
{
    void OnProcessingEvent(
        string eventType, string details);
}

public class ObservableOrderMediator : IOrderMediator
{
    private readonly Dictionary<string, IOrderParticipant>
        _services = new();

    private readonly List<IProcessingObserver>
        _monitors = new();

    public void AddMonitor(IProcessingObserver monitor) =>
        _monitors.Add(monitor);

    public void RegisterService(
        string name, IOrderParticipant service)
    {
        _services[name] = service;
        BroadcastEvent("registration",
            $"{name} registered");
    }

    public void NotifyOrderPlaced(
        string orderId, decimal amount,
        IOrderParticipant sender)
    {
        // Mediator 协调
        if (_services.TryGetValue("inventory", out var inv))
            inv.Receive("order_placed", orderId, amount);

        if (_services.TryGetValue("email", out var email))
            email.Receive("order_placed", orderId, amount);

        // Observer 广播给外部监控
        BroadcastEvent("order_placed",
            $"Order {orderId} processed for {amount:C}");
    }

    public void NotifyInventoryConfirmed(
        string orderId, IOrderParticipant sender)
    {
        if (_services.TryGetValue("email", out var email))
            email.Receive(
                "inventory_confirmed", orderId, 0m);

        BroadcastEvent("inventory_confirmed",
            $"Stock confirmed for {orderId}");
    }

    private void BroadcastEvent(
        string eventType, string details)
    {
        foreach (var monitor in _monitors)
            monitor.OnProcessingEvent(eventType, details);
    }
}
```

协调器负责服务间的订单处理（Mediator 模式），同时向监控组件广播处理事件（Observer 模式）。审计日志、指标仪表盘、告警系统都可以订阅，而协调器不需要知道它们内部的逻辑。内部用协调，外部用广播——每个模式在同一个系统里解决不同的通信需求。

---

## 对比速查表

| 维度        | Mediator                  | Observer                          |
| ----------- | ------------------------- | --------------------------------- |
| 通信模型    | 多对多，通过中心中枢      | 一对多广播                        |
| 控制方式    | 协调器主动路由消息        | Subject 被动广播                  |
| 参与者感知  | 协调器知道所有参与者      | Subject 不知道观察者              |
| 路由能力    | 选择性、条件性投递        | 所有人都收到每条通知              |
| 协调能力    | 参与者之间有主动协调      | 订阅者之间无协调                  |
| 新增参与者  | 可能需要改协调器          | 不必改动已有代码                  |
| 复杂度位置  | 集中在 Mediator           | 分散在各 Observer                 |
| C# 内建支持 | 无                        | event / delegate / IObservable<T> |
| 典型场景    | 工作流编排、UI 面板、聊天 | 事件、数据绑定、通知              |

两种模式都能降低直接依赖。选择的依据是你的问题需要的是受管理的协调还是独立的通知。

---

## 常见问题

### Mediator 和 Observer 在 C# 中的核心区别是什么？

通信控制。Mediator 通过一个协调器集中管理通信，主动在参与者之间路由消息。Observer 从 Subject 向所有订阅者广播通知，没有路由和协调。协调器决定谁收什么，Subject 给所有人发一样的东西。

### Mediator 能完全替代 Observer 吗？

技术上可以——让协调器向所有参与者广播消息就能模拟 Observer 的行为。但如果你只需要简单广播，这样做徒增复杂度。为单纯的广播场景引入中心协调器是多此一举。Observer 更简单、有 C# 原生支持，适合订阅者独立行动的场景。

### 两种模式在耦合上有什么不同？

Observer 耦合 Subject 到一个订阅接口，订阅者之间互不知晓。Mediator 耦合所有参与者到一个协调器接口，协调器又知道所有参与者。Observer 耦合最小且分散；Mediator 耦合集中但覆盖面广。二者都比直接的对象间依赖好得多。

### MediatR 是 Mediator 模式的实现吗？

MediatR 的灵感来自 Mediator 概念，但功能更接近请求/响应派发管线。它将请求路由到处理器，而不是在已知参与者之间做双向通信。经典 Mediator 要求参与者知道协调器并通过它通信。MediatR 更像一个带管线行为的消息派发器。

### 什么时候该从 Observer 重构到 Mediator？

当你的订阅者开始需要协调时考虑重构。如果通知顺序变得重要，你却在挣扎着控制它；如果订阅者需要基于其他订阅者的状态来反应；如果你发现自己反复筛选通知只发一部分订阅者——这些都是广播模型已经不够用的信号。移到中心协调器能让散落各处的协调逻辑收敛到一处。

### 哪种模式更容易做单元测试？

两种模式都能提高可测试性，但方式不同。Observer 中，你订阅一个模拟订阅者然后验证它收到了正确的通知。Mediator 中，你通过 Mock 协调器接口测试每个参与者，再通过 Mock 参与者接口测试协调器本身。交互复杂时集中式更容易测，因为所有协调逻辑在一个类里；交互简单时广播式更容易测，因为每个订阅者完全独立。

---

## 总结

Mediator 和 Observer 的选择归根到底是通信形状的问题。

当你的对象需要受管理的、有条件的、有顺序的通信——选 Mediator。

当你的对象需要简单的、独立的、一对多的通知——选 Observer。

当你的系统同时需要广播事件和协调交互——把它们组合起来。

每一种模式解决一类通信问题。把模式匹配到问题，你的设计才能保持干净、可持续。

---

## 参考

- [Mediator vs Observer Pattern in C#: Key Differences Explained](https://www.devleader.ca/2026/06/14/mediator-vs-observer-pattern-in-c-key-differences-explained)
- [Observer Design Pattern in C#: Complete Guide](https://www.devleader.ca/2026/03/26/observer-design-pattern-in-c-complete-guide-with-examples)
- [MediatR (GitHub)](https://github.com/jbogard/MediatR)
- [IObservable<T> (Microsoft Docs)](https://learn.microsoft.com/en-us/dotnet/api/system.iobservable-1)
- [Command Design Pattern in C#](https://www.devleader.ca/2026/04/14/command-design-pattern-in-c-complete-guide-with-examples)
- [Chain of Responsibility Pattern in C#](https://www.devleader.ca/2026/05/25/chain-of-responsibility-design-pattern-in-c-complete-guide-with-examples)
- [Facade Design Pattern in C#](https://www.devleader.ca/2026/04/26/facade-design-pattern-in-c-complete-guide-with-examples)
