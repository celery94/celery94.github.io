---
pubDatetime: 2026-06-15T07:51:43+08:00
title: "C# 中介者模式最佳实践：让代码组织经得起时间考验"
description: "中介者模式用起来不难，难的是用久了不烂。本文整理 6 条 C# 落地实践：接口隔离、按域拆分、避开上帝中介者、强类型通知、错误处理和测试策略，帮你在项目增长时守住可维护性。"
tags: ["C#", "设计模式", "中介者模式", ".NET"]
slug: "mediator-pattern-csharp-best-practices"
ogImage: "../../assets/876/01-cover.png"
source: "https://www.devleader.ca/2026/06/12/mediator-pattern-best-practices-in-c-code-organization-and-maintainability"
---

中介者模式的基本用法大多数人都知道：定义一个中介者，把对象之间的引用都收敛到它身上，让同事对象之间不再直接耦合。注册几个同事，消息从中心枢纽流过，搞定。

但把基本机制跑通只是开始。真正考验人的，是怎么让这个中介者在项目迭代一年之后依然不会变成一个没人敢碰的上帝对象。怎么让新增同事的行为不波及已有代码。怎么在由中介者连接的组件之间处理错误而不让整个链条一起炸掉。

这篇文章不重新讲中介者模式是什么，而是聚焦在 6 条落地实践上：接口隔离、按域聚焦、避开上帝中介者、强类型通知、错误处理和测试策略。

---

## 基础：给中介者和同事定义接口

所有可维护的中介者模式实现都建立在同一块基石上：面向接口编程，而不是面向具体类型。

当同事依赖一个具体的中介者类时，你已经制造了紧耦合——而紧耦合正是中介者模式本来要解决的问题。定义一个 `IMediator` 接口让同事引用，再定义一个 `IColleague` 接口让中介者操作。

```csharp
public interface IMediator
{
    void Notify(IColleague sender, string eventName);
}

public interface IColleague
{
    IMediator Mediator { get; set; }
}
```

再补一个基类，把通用的接线逻辑集中起来：

```csharp
public abstract class ColleagueBase : IColleague
{
    public IMediator Mediator { get; set; }

    protected ColleagueBase(IMediator mediator)
    {
        Mediator = mediator
            ?? throw new ArgumentNullException(nameof(mediator));
    }
}
```

面向接口带来两个直接收益。第一，测试时你可以换中介者的实现（mock 或 stub），同事代码一行不动。第二，新增同事类型不需要改中介者接口。在通过 `IServiceCollection` 注册 DI 时，注册的是接口而不是具体类型——这与控制反转的原则保持一致。

一个常见误区是「我们项目只有一个中介者，就别折腾接口了」。但这种状态是临时的。光测试就要求第二个实现（mock）。与其后面补，不如一开始就写对。

---

## 每个中介者只负责一个关注域

中介者应该协调一个有限的上下文，而不是做整个应用的通用消息总线。当一个中介者同时处理订单流程、用户认证和通知路由时，你只是给上帝对象换了个名字而已。这是中介者模式落地过程中最需要内化的一条实践。

反例——一个什么都管的中介者：

```csharp
// 坏：用一个中介者连接毫不相干的关注点
public class ApplicationMediator : IMediator
{
    private readonly OrderForm _orderForm;
    private readonly PaymentProcessor _payment;
    private readonly UserLogin _login;
    private readonly EmailNotifier _email;
    private readonly InventoryTracker _inventory;

    public ApplicationMediator(
        OrderForm orderForm, PaymentProcessor payment,
        UserLogin login, EmailNotifier email,
        InventoryTracker inventory)
    {
        _orderForm = orderForm;
        _payment = payment;
        _login = login;
        _email = email;
        _inventory = inventory;
    }

    public void Notify(IColleague sender, string eventName)
    {
        if (eventName == "OrderSubmitted")
        {
            _payment.ProcessPayment();
            _inventory.ReserveStock();
            _email.SendConfirmation();
        }
        else if (eventName == "LoginAttempted")
        {
            _login.ValidateCredentials();
        }
        else if (eventName == "PasswordReset")
        {
            _email.SendResetLink();
        }
        // 无穷无尽...
    }
}
```

修法很简单：按域拆分。每个中介者只管一组相关的交互：

```csharp
// 好：中介者作用域仅限订单处理
public sealed class OrderMediator : IMediator
{
    private readonly PaymentProcessor _payment;
    private readonly InventoryTracker _inventory;
    private readonly OrderConfirmationNotifier _notifier;

    public OrderMediator(
        PaymentProcessor payment,
        InventoryTracker inventory,
        OrderConfirmationNotifier notifier)
    {
        _payment = payment;
        _inventory = inventory;
        _notifier = notifier;
    }

    public void Notify(IColleague sender, string eventName)
    {
        switch (eventName)
        {
            case "OrderSubmitted":
                _payment.ProcessPayment();
                _inventory.ReserveStock();
                _notifier.SendConfirmation();
                break;
            case "OrderCancelled":
                _inventory.ReleaseStock();
                _notifier.SendCancellation();
                break;
        }
    }
}
```

现在 `OrderMediator` 心里只有订单。登录逻辑在另一个中介者里。修改一个域的中介者不会波及另一个域。

再来一个聊天室中介者的例子，它不涉及任何持久化或业务逻辑：

```csharp
public sealed class ChatRoomMediator : IMediator
{
    private readonly List<IChatParticipant> _participants = new();

    public void Register(IChatParticipant participant)
    {
        _participants.Add(participant);
        participant.Mediator = this;
    }

    public void Notify(IColleague sender, string eventName)
    {
        if (eventName == "MessageSent" &&
            sender is IChatParticipant chatSender)
        {
            foreach (var participant in _participants)
            {
                if (participant != sender)
                {
                    participant.ReceiveMessage(chatSender.LastMessage);
                }
            }
        }
    }
}
```

两个中介者各管一个域，互不打扰。域的分界线本身就是一个很好的设计文档。

---

## 用强类型通知替代字符串匹配

字符串事件名既脆弱又不可发现。拼错一个 `"OrderSubmitted"`，编译器帮不了你，只有运行时才知道——通常是在生产环境。

把事件提升为类型：

```csharp
public interface IMediator<TNotification>
{
    void Notify(IColleague sender, TNotification notification);
}

public sealed record OrderNotification(
    OrderNotificationType Type,
    string OrderId);

public enum OrderNotificationType
{
    Submitted,
    Cancelled,
    PaymentConfirmed,
    Shipped
}
```

这样一来，中介者的实现变得既类型安全又可预测：

```csharp
public sealed class OrderMediator : IMediator<OrderNotification>
{
    private readonly PaymentProcessor _payment;
    private readonly InventoryTracker _inventory;

    public OrderMediator(
        PaymentProcessor payment,
        InventoryTracker inventory)
    {
        _payment = payment;
        _inventory = inventory;
    }

    public void Notify(IColleague sender, OrderNotification notification)
    {
        switch (notification.Type)
        {
            case OrderNotificationType.Submitted:
                _payment.ProcessPayment(notification.OrderId);
                _inventory.ReserveStock(notification.OrderId);
                break;
            case OrderNotificationType.Cancelled:
                _inventory.ReleaseStock(notification.OrderId);
                break;
        }
    }
}
```

编译期就能保证通知结构正确。新增类型时，IDE 会提示所有需要处理的 switch 分支。而且 `record` 天然带着值相等语义，测试断言也好写了很多。

---

## 在中介传递中处理错误

当一个同事通知中介者，而中介者又把消息分发到多个同事时，一个同事出问题不该把整个通知链条打断。

考虑聊天室场景——一个参与者离线或崩溃时，其他参与者应该继续收到消息：

```csharp
public sealed class ResilientChatMediator : IMediator
{
    private readonly List<IChatParticipant> _participants = new();
    private readonly ILogger<ResilientChatMediator> _logger;

    public ResilientChatMediator(ILogger<ResilientChatMediator> logger)
    {
        _logger = logger;
    }

    public void Notify(IColleague sender, string eventName)
    {
        foreach (var participant in _participants)
        {
            if (participant == sender) continue;

            try
            {
                participant.ReceiveMessage(
                    ((IChatParticipant)sender).LastMessage);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex,
                    "Failed to notify {Participant}", participant.Name);
            }
        }
    }
}
```

在通知循环里包一层 try-catch，记日志但不阻断。坏掉的同事自己承担后果，所有正常的同事不受影响。这是中介者层级的容错——不影响业务逻辑本身。

---

## 什么时候该拆分中介者

并不是一定要等到上帝对象成型了才行动。下面几个信号出现时，就该考虑拆分了：

- 一个中介者的 `Notify` 方法里 `if` / `switch` 分支超过 8 到 10 个
- 构造函数参数超过 5 个
- 测试文件需要 mock 大量无关依赖才能验证单个通知路径
- `Notify` 里的分支处理了属于不同业务域的事件

拆分后的一个通用模式是注册表式的中介者——把通知处理逻辑进一步抽象：

```csharp
public interface INotificationHandler<TNotification>
{
    void Handle(TNotification notification);
}

public sealed class RegistryMediator<TNotification>
{
    private readonly List<INotificationHandler<TNotification>>
        _handlers = new();

    public void Register(INotificationHandler<TNotification> handler)
    {
        _handlers.Add(handler);
    }

    public void Publish(TNotification notification)
    {
        foreach (var handler in _handlers)
        {
            handler.Handle(notification);
        }
    }
}
```

每个 handler 只处理一种通知，遵循单一职责。中介者退化为一个轻量的注册表，负责路由和分发——这本身就是一个单一关注点。

---

## 测试策略：同事和中介者分开测

**测试同事（隔离）**：同事不应该感知真实中介者的存在。注入一个 `Mock<IMediator<TNotification>>`，验证同事在正确时机调用了正确的方法。

```csharp
[Fact]
public void SubmitOrder_NotifiesMediator_WithSubmittedEvent()
{
    var mockMediator = new Mock<IMediator<OrderNotification>>();
    var orderForm = new OrderForm(mockMediator.Object);

    orderForm.Submit("ORD-123");

    mockMediator.Verify(
        m => m.Notify(
            orderForm,
            It.Is<OrderNotification>(n =>
                n.Type == OrderNotificationType.Submitted &&
                n.OrderId == "ORD-123")),
        Times.Once);
}
```

**测试中介者**：反过来，用 mock 替代它的同事，验证分发逻辑正确。这是真正在验证中介者的协调行为——而不是同事的实现细节。

```csharp
[Fact]
public void Notify_OrderSubmitted_ProcessesPaymentAndReservesStock()
{
    var mockPayment = new Mock<PaymentProcessor>();
    var mockInventory = new Mock<InventoryTracker>();
    var mediator = new OrderMediator(
        mockPayment.Object, mockInventory.Object);
    var sender = new Mock<IColleague>().Object;

    var notification = new OrderNotification(
        OrderNotificationType.Submitted, "ORD-456");

    mediator.Notify(sender, notification);

    mockPayment.Verify(
        p => p.ProcessPayment("ORD-456"), Times.Once);
    mockInventory.Verify(
        i => i.ReserveStock("ORD-456"), Times.Once);
}
```

接口的存在让这两种测试都非常干净——同事不知道中介者的实现，中介者也不知道同事的实现。

---

## 性能考量

默认的同步中介者在大多数业务场景里足够了。但如果你面对高吞吐场景——比如每秒数千条通知要通过中介者分发——需要考虑两点。

第一是分配开销。如果通知对象频繁创建，优先用 `record struct` 减少堆分配。第二是异步分发。当同事的执行涉及 I/O 或外部调用时，让中介者支持异步：

```csharp
public interface IAsyncMediator<TNotification>
{
    Task NotifyAsync(
        IColleague sender,
        TNotification notification,
        CancellationToken cancellationToken = default);
}
```

不过大多数应用不需要这个。优先让代码清晰，再按需优化。

---

## 项目中的代码组织

中介者相关文件的目录结构映射它的域边界是一个简单有效的做法：

```
src/
  OrderProcessing/
    IOrderMediator.cs
    OrderMediator.cs
    OrderForm.cs
    PaymentProcessor.cs
    Notifications/
      OrderNotification.cs
  Chat/
    IChatMediator.cs
    ChatRoomMediator.cs
    ChatParticipant.cs
```

每个域一个文件夹，里面放这个域的中介者、同事和通知类型。新同事进来时，放到对应的文件夹里即可。域之间的边界在文件系统上就看得见。

---

## 常见问题

**Q：上帝中介者反模式是什么，怎么避开？**

当一个中介者同时协调多个不相关的业务域时——比如订单处理、用户认证和通知都在同一个中介者里——就出现了上帝中介者。你会看到构造函数膨胀、`if` 分支爆炸、以及改一条通知路径就要跑全局回归。避开它的方法很简单：一个中介者只对应一个业务域。如果 `Notify` 里的分支横跨了不同团队的不同关注点，就是拆分信号。

**Q：怎么有效测试中介者模式代码？**

同事和中介者分开测。同事测试用 mock 中介者验证通知行为；中介者测试用 mock 同事验证分发逻辑。接口的存在让两端都只依赖抽象，注入 mock 时零成本。

**Q：该用字符串通知还是强类型通知？**

强类型。字符串只在运行时校验，拼错没提示，重构没法跟踪。用 `record` 定义通知类型，编译期就能保证结构正确，IDE 也能在 switch 里提示未覆盖的分支。

**Q：中介者模式跟事件总线或观察者模式有什么区别？**

观察者模式是 1 对多广播，订阅者直接注册到发布者上。事件总线是全局消息通道，通常底层依赖消息队列或内存中的发布-订阅机制。中介者模式的核心差异在于：它把组件之间的协调行为集中封装，这个封装本身可以被替换和测试。最接近的类比是机场塔台——不是飞机之间直接互喊，而是所有飞机只和塔台对话。

**Q：中介者在 C# 中的性能影响大吗？**

对大多数业务应用来说，中介者增加的那一层间接调用在当前硬件上是可忽略的。高吞吐场景下应关注分配开销（优先用 `record struct` 做通知对象）和异步分发需求。性能瓶颈更可能出在同事自身的实现上，而不是中介者的分发路径。

---

## 小结

中介者模式的核心价值不在模式本身——在怎么管好它。

一个被按域拆分、面向接口、使用强类型通知、内置错误隔离的 mediator，在项目增长两三年后依然可以安全地修改和测试。一个把所有东西塞在一个类里、靠字符串路由的 mediator，从第三个月开始就会变成人人绕行的禁区。

这 6 条实践可以概括成一句话：**让中介者聚焦、让通知类型化、让测试独立、让错误隔离、让代码按域组织。**

---

## 参考

- [Mediator Pattern Best Practices in C# — Dev Leader](https://www.devleader.ca/2026/06/12/mediator-pattern-best-practices-in-c-code-organization-and-maintainability)
- [C# Mediator Design Pattern Guide — Dev Leader](https://www.devleader.ca/2025/08/11/csharp-mediator-design-pattern-guide/)
