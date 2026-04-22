---
pubDatetime: 2026-04-22T09:40:00+08:00
title: "C# 状态模式完整实战指南：从接口到依赖注入"
description: "用订单处理状态机为例，逐步讲解如何在 C# 中实现状态模式：定义接口、创建具体状态类、构建上下文、添加转移事件、引入守卫条件，最后接入 DI 容器。"
tags: ["CSharp", "Design Patterns", "State Pattern", "Behavioral Patterns", "Dependency Injection"]
slug: "csharp-state-pattern-step-by-step-guide"
ogImage: "../../assets/747/01-cover.png"
source: "https://www.devleader.ca/2026/04/21/how-to-implement-state-pattern-in-c-stepbystep-guide"
---

![C# 状态模式实战封面](../../assets/747/01-cover.png)

一个对象根据自身状态改变行为，这是日常开发里很常见的需求。订单在草稿、待付款、处理中、已发货、已送达、已取消之间流转，每个阶段能做的操作不同。最直接的写法是一串 `switch` 或 `if-else`，但随着状态增多，这些分支会越来越难维护。

**状态模式**（State Pattern）的做法是：把每个状态的行为封装进独立的类，让上下文对象把调用委托给当前状态，而不是自己判断。这篇文章以订单处理为例，从零到完整演示如何在 C# 中实现状态模式，包括接口定义、具体状态类、上下文、转移事件、守卫条件，以及最后接入依赖注入容器。

## 前置条件

在开始之前，需要熟悉以下基础：

- **C# 接口和类**：状态模式的核心是一个接口加多个实现类，接口契约必须清晰。
- **组合优先于继承**：上下文通过组合持有状态对象，每个状态彼此独立。
- **依赖注入基础**：最后一步会用 `IServiceCollection` 注册服务，了解服务生命周期会有帮助。
- **.NET 8 或更高版本**：示例使用现代 C# 语法。

## 第一步：定义 IOrderState 接口

实现状态模式的第一步是定义状态接口。接口上的每个方法代表上下文可执行的一个操作，具体行为由当前激活的状态决定。

```csharp
public interface IOrderState
{
    string StatusName { get; }

    void Submit(OrderContext context);
    void Pay(OrderContext context);
    void Ship(OrderContext context);
    void Deliver(OrderContext context);
    void Cancel(OrderContext context);
}
```

每个方法都接收 `OrderContext` 作为参数，这是关键设计。具体状态在需要触发转移时，会调用 `context.TransitionTo(new SomeOtherState())`。没有这个反向引用，状态就无法推进工作流。

接口把所有可能操作都列出来——即使多数状态只处理其中一两个。草稿状态可以提交但不能发货，已送达状态什么都不能再做。接口覆盖全部操作，由具体状态决定接受哪些、拒绝哪些。这也是**控制反转**的体现：上下文依赖 `IOrderState` 抽象，从不直接引用具体状态类。

## 第二步：实现具体状态类

### 基类：提供默认拒绝行为

先写一个抽象基类，为所有方法提供默认的"操作不支持"行为，避免每个具体状态重复拒绝逻辑：

```csharp
public abstract class OrderStateBase : IOrderState
{
    public abstract string StatusName { get; }

    public virtual void Submit(OrderContext context)
    {
        Console.WriteLine(
            $"[{StatusName}] Cannot submit order " +
            $"in current state.");
    }

    public virtual void Pay(OrderContext context)
    {
        Console.WriteLine(
            $"[{StatusName}] Cannot process payment " +
            $"in current state.");
    }

    public virtual void Ship(OrderContext context)
    {
        Console.WriteLine(
            $"[{StatusName}] Cannot ship order " +
            $"in current state.");
    }

    public virtual void Deliver(OrderContext context)
    {
        Console.WriteLine(
            $"[{StatusName}] Cannot deliver order " +
            $"in current state.");
    }

    public virtual void Cancel(OrderContext context)
    {
        Console.WriteLine(
            $"[{StatusName}] Cannot cancel order " +
            $"in current state.");
    }
}
```

基类拒绝所有操作。具体状态只需重写当前阶段允许的方法，其余自动走拒绝路径。这让每个状态支持哪些转移一目了然。

### DraftState

```csharp
public sealed class DraftState : OrderStateBase
{
    public override string StatusName => "Draft";

    public override void Submit(OrderContext context)
    {
        Console.WriteLine("[Draft] Order submitted for payment.");
        context.TransitionTo(new PendingPaymentState());
    }

    public override void Cancel(OrderContext context)
    {
        Console.WriteLine("[Draft] Order cancelled.");
        context.TransitionTo(new CancelledState());
    }
}
```

### PendingPaymentState

```csharp
public sealed class PendingPaymentState : OrderStateBase
{
    public override string StatusName => "PendingPayment";

    public override void Pay(OrderContext context)
    {
        Console.WriteLine(
            "[PendingPayment] Payment received. " +
            "Order is now processing.");
        context.TransitionTo(new ProcessingState());
    }

    public override void Cancel(OrderContext context)
    {
        Console.WriteLine(
            "[PendingPayment] Order cancelled " +
            "before payment completed.");
        context.TransitionTo(new CancelledState());
    }
}
```

### ProcessingState

```csharp
public sealed class ProcessingState : OrderStateBase
{
    public override string StatusName => "Processing";

    public override void Ship(OrderContext context)
    {
        Console.WriteLine("[Processing] Order shipped.");
        context.TransitionTo(new ShippedState());
    }

    public override void Cancel(OrderContext context)
    {
        Console.WriteLine(
            "[Processing] Order cancelled. " +
            "Initiating refund.");
        context.TransitionTo(new CancelledState());
    }
}
```

### ShippedState

```csharp
public sealed class ShippedState : OrderStateBase
{
    public override string StatusName => "Shipped";

    public override void Deliver(OrderContext context)
    {
        Console.WriteLine("[Shipped] Order delivered successfully.");
        context.TransitionTo(new DeliveredState());
    }
}
```

### DeliveredState 和 CancelledState

```csharp
public sealed class DeliveredState : OrderStateBase
{
    public override string StatusName => "Delivered";
}

public sealed class CancelledState : OrderStateBase
{
    public override string StatusName => "Cancelled";
}
```

`DeliveredState` 和 `CancelledState` 是终态——什么都不重写，所有操作一律拒绝。

需要注意的是，每个状态只覆盖自己允许的转移。`DraftState` 只处理 `Submit` 和 `Cancel`。这是状态模式的核心优势：**每个状态的规则活在那个状态类里，而不是散落在上下文的条件分支里。**

原文作者也指出，这种结构与**策略模式**很像，但两者有本质区别：策略是由外部代码选择的算法，状态则是对象根据内部逻辑自行推进的工作流，状态之间相互知道彼此，而策略之间互不相识。

## 第三步：构建上下文类 OrderContext

上下文是客户端实际交互的对象。它持有当前状态，把所有调用委托给当前状态，自身不包含任何"我现在是哪个状态该怎么做"的判断逻辑。

```csharp
public sealed class OrderContext
{
    public IOrderState CurrentState { get; private set; }
    public string OrderId { get; }
    public decimal TotalAmount { get; }
    public bool HasShippingAddress { get; set; }

    public OrderContext(string orderId, decimal totalAmount)
    {
        OrderId = orderId;
        TotalAmount = totalAmount;
        CurrentState = new DraftState();

        Console.WriteLine(
            $"[Order {OrderId}] Created with " +
            $"total ${TotalAmount}. " +
            $"State: {CurrentState.StatusName}");
    }

    public void TransitionTo(IOrderState newState)
    {
        Console.WriteLine(
            $"[Order {OrderId}] Transitioning: " +
            $"{CurrentState.StatusName} -> " +
            $"{newState.StatusName}");
        CurrentState = newState;
    }

    public void Submit()  => CurrentState.Submit(this);
    public void Pay()     => CurrentState.Pay(this);
    public void Ship()    => CurrentState.Ship(this);
    public void Deliver() => CurrentState.Deliver(this);
    public void Cancel()  => CurrentState.Cancel(this);
}
```

客户端调用 `order.Ship()`，当前状态决定发生什么，上下文完全不管。`TransitionTo` 可以标记为 `internal`，这样只有同程序集内的状态类能触发转移，防止外部代码强制跳到非法状态——这是一个值得考虑的设计选择。

完整生命周期示例：

```csharp
var order = new OrderContext("ORD-001", 99.99m);

order.Submit();   // Draft -> PendingPayment
order.Pay();      // PendingPayment -> Processing
order.Ship();     // Processing -> Shipped
order.Deliver();  // Shipped -> Delivered

order.Cancel();   // 已送达，拒绝取消
```

## 第四步：添加状态转移事件

生产环境的状态机通常需要在转移时触发日志、通知或审计记录。把这些逻辑内嵌到每个状态类会造成散射，更好的方式是在上下文上暴露一个转移事件。

```csharp
public sealed class OrderContext
{
    public event EventHandler<StateTransitionEventArgs>? StateChanged;

    public IOrderState CurrentState { get; private set; }
    public string OrderId { get; }
    public decimal TotalAmount { get; }
    public bool HasShippingAddress { get; set; }

    public OrderContext(string orderId, decimal totalAmount)
    {
        OrderId = orderId;
        TotalAmount = totalAmount;
        CurrentState = new DraftState();
    }

    public void TransitionTo(IOrderState newState)
    {
        var previousState = CurrentState;
        CurrentState = newState;

        Console.WriteLine(
            $"[Order {OrderId}] " +
            $"{previousState.StatusName} -> " +
            $"{newState.StatusName}");

        StateChanged?.Invoke(
            this,
            new StateTransitionEventArgs(
                previousState.StatusName,
                newState.StatusName));
    }

    public void Submit()  => CurrentState.Submit(this);
    public void Pay()     => CurrentState.Pay(this);
    public void Ship()    => CurrentState.Ship(this);
    public void Deliver() => CurrentState.Deliver(this);
    public void Cancel()  => CurrentState.Cancel(this);
}

public sealed class StateTransitionEventArgs : EventArgs
{
    public string FromState { get; }
    public string ToState { get; }

    public StateTransitionEventArgs(string fromState, string toState)
    {
        FromState = fromState;
        ToState = toState;
    }
}
```

订阅方不需要知道状态内部实现：

```csharp
var order = new OrderContext("ORD-002", 149.50m);

order.StateChanged += (sender, args) =>
{
    Console.WriteLine(
        $"[Audit] Order transitioned from " +
        $"{args.FromState} to {args.ToState}");
};

order.Submit();
order.Pay();
order.Ship();
order.Deliver();
```

## 第五步：引入守卫条件

真实业务往往需要在转移前验证条件——比如"没有收货地址不能发货"。守卫条件把这类业务规则封装进状态自身，上下文不需要知道具体验什么。

更新后的 `ProcessingState`：

```csharp
public sealed class ProcessingState : OrderStateBase
{
    public override string StatusName => "Processing";

    public override void Ship(OrderContext context)
    {
        if (!context.HasShippingAddress)
        {
            Console.WriteLine(
                "[Processing] Cannot ship -- " +
                "no shipping address on file.");
            return;
        }

        if (context.TotalAmount <= 0)
        {
            Console.WriteLine(
                "[Processing] Cannot ship -- " +
                "invalid order total.");
            return;
        }

        Console.WriteLine(
            "[Processing] Guard conditions passed. " +
            "Order shipped.");
        context.TransitionTo(new ShippedState());
    }

    public override void Cancel(OrderContext context)
    {
        Console.WriteLine(
            "[Processing] Order cancelled. " +
            "Initiating refund.");
        context.TransitionTo(new CancelledState());
    }
}
```

验证效果：

```csharp
var order = new OrderContext("ORD-003", 75.00m);
order.HasShippingAddress = false;

order.Submit();
order.Pay();

order.Ship();
// Output: [Processing] Cannot ship --
//         no shipping address on file.

order.HasShippingAddress = true;
order.Ship();
// Output: [Processing] Guard conditions passed.
//         Order shipped.
```

如果验证逻辑复杂，可以提取到专用守卫类，状态调用守卫而不是把所有判断硬编码在方法里：

```csharp
public sealed class ShippingGuard
{
    public bool CanShip(
        OrderContext context,
        out string reason)
    {
        if (!context.HasShippingAddress)
        {
            reason = "No shipping address on file.";
            return false;
        }

        if (context.TotalAmount <= 0)
        {
            reason = "Invalid order total.";
            return false;
        }

        reason = string.Empty;
        return true;
    }
}
```

新增守卫时只需修改对应的状态类，不会影响上下文或其他状态——符合开闭原则。

## 第六步：接入依赖注入

生产应用里，上下文通常注册为瞬态或作用域服务（每个订单一个实例），而守卫、工厂等共享服务可以是单例。

由于每个 `OrderContext` 需要唯一的订单 ID 和金额，直接注册类型行不通。原文推荐注册工厂委托：

```csharp
using Microsoft.Extensions.DependencyInjection;

var services = new ServiceCollection();

services.AddSingleton<ShippingGuard>();

services.AddTransient<Func<string, decimal, OrderContext>>(
    sp => (orderId, totalAmount) =>
    {
        var context = new OrderContext(
            orderId,
            totalAmount);
        return context;
    });

var provider = services.BuildServiceProvider();

var createOrder = provider
    .GetRequiredService<Func<string, decimal, OrderContext>>();

var order = createOrder("ORD-DI-001", 250.00m);
order.HasShippingAddress = true;

order.Submit();
order.Pay();
order.Ship();
order.Deliver();

Console.WriteLine(
    $"Final state: {order.CurrentState.StatusName}");
```

对于需要向状态注入依赖的场景，可以引入状态工厂：

```csharp
public interface IOrderStateFactory
{
    IOrderState CreateDraft();
    IOrderState CreateProcessing(ShippingGuard shippingGuard);
}

public sealed class OrderStateFactory : IOrderStateFactory
{
    private readonly ShippingGuard _shippingGuard;

    public OrderStateFactory(ShippingGuard shippingGuard)
    {
        _shippingGuard = shippingGuard;
    }

    public IOrderState CreateDraft()
    {
        return new DraftState();
    }

    public IOrderState CreateProcessing(
        ShippingGuard shippingGuard)
    {
        return new ProcessingState();
    }
}
```

注册：

```csharp
services.AddSingleton<IOrderStateFactory, OrderStateFactory>();
```

工厂让状态创建集中管理，也方便测试时替换 mock 工厂。上下文依赖工厂抽象，而不是直接 `new` 具体状态。

## 常见错误

**把转移逻辑写在上下文里**：如果上下文有 `switch` 或 `if-else` 判断当前状态，说明模式没用对。所有操作应该委托给当前状态，由状态决定是否允许并如何转移。

**静默处理非法转移**：如果 `DraftState.Ship()` 什么都不做也不打印任何信息，调试工作流 bug 会非常痛苦。非法操作要明确反馈——打印消息或抛异常都行。

**状态间的循环依赖**：StateA 直接 `new StateB`，StateB 直接 `new StateA`，会造成紧耦合。用工厂创建状态，或保证状态只引用接口而不引用具体类。

**接口方法过多**：`IOrderState` 上的每个方法，所有具体状态都得处理。如果某个操作只有一个状态支持，考虑放在上下文上而不是接口上，或者拆出独立接口。

**忽略线程安全**：多线程并发调用同一个上下文时，状态切换可能出现竞争。需要在 `TransitionTo` 上加同步，或改用不可变状态（每次转移返回新上下文而非修改旧的）。

## FAQ 摘要

**状态模式和策略模式有什么区别？**

策略模式让外部代码选择算法，策略之间互不知晓。状态模式里对象根据内部逻辑自行推进，状态之间知道彼此存在并主动触发转移。简单说：策略是"怎么做"，状态是"我现在是什么"。

**枚举 + switch 和状态模式怎么选？**

状态不多、逻辑简单时枚举更直接。但当每个状态有不同的业务规则和副作用时，状态模式更易维护——新增状态只需加一个类，而枚举方案需要更新所有 switch，违背开闭原则。

**如何测试？**

单独测试每个具体状态：创建上下文，设置到目标状态，依次调用各方法，验证合法操作触发预期转移、非法操作被拒绝。也可以端到端跑完整生命周期，验证每个中间状态。用接口 mock 上下文可以让单元测试更干净。

**状态模式能和其他模式组合吗？**

可以。**装饰器模式**可以包装状态类，添加日志或权限检查而不修改状态本身。**命令模式**可以把每次转移封装成可重放操作，支持审计和撤销。状态工厂本身就是工厂模式的自然运用。

## 参考

- [How to Implement State Pattern in C#: Step-by-Step Guide](https://www.devleader.ca/2026/04/21/how-to-implement-state-pattern-in-c-stepbystep-guide)
- [Strategy Design Pattern in C# — Complete Guide with Examples](https://www.devleader.ca/2026/03/02/strategy-design-pattern-in-c-complete-guide-with-examples)
- [Command Design Pattern in C# — Complete Guide with Examples](https://www.devleader.ca/2026/04/14/command-design-pattern-in-c-complete-guide-with-examples)
- [IServiceCollection in C# — Simplified Beginner's Guide for Dependency Injection](https://www.devleader.ca/2024/02/21/iservicecollection-in-c-simplified-beginners-guide-for-dependency-injection)
