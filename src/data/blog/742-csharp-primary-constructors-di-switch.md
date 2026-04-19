---
pubDatetime: 2026-04-19T13:40:00+08:00
title: "为什么我在 C# 依赖注入中改用主构造函数"
description: "C# 12 将主构造函数扩展到普通类，作者起初持保留态度，但在多个项目中使用后改变了看法。本文梳理了主构造函数在 DI 服务类中消除样板代码的实际效果、用于领域实体的注意事项，以及一个必须了解的可变捕获陷阱，帮助你判断在哪些场景下值得切换。"
tags: ["CSharp", "DotNet", "依赖注入", "设计模式"]
slug: "csharp-primary-constructors-di-switch"
ogImage: "../../assets/742/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/why-i-switched-to-primary-constructors-for-di-in-csharp"
---

![为什么我在 C# 依赖注入中改用主构造函数](../../assets/742/01-cover.png)

Milan Jovanović 在最近一篇文章里分享了他改用主构造函数做依赖注入的经历。起初他持观望态度，C# 12 把主构造函数从 `record` 类型扩展到普通类和结构体时，他的第一反应是：用隐式可变捕获替代显式 `readonly` 字段，这感觉像是用便利换安全。但在多个项目中真正用过之后，他改变了主意。

这篇文章的价值不在于"主构造函数好不好"这个宽泛判断，而在于它把适用场景、具体陷阱、以及仍然需要传统构造函数的情况都梳理清楚了。

## 传统写法的样板代码有多重

先看 Milan 之前的服务类长什么样：

```csharp
public class OrderService
{
    private readonly IOrderRepository _orderRepository;
    private readonly ILogger<OrderService> _logger;

    public OrderService(
        IOrderRepository orderRepository,
        ILogger<OrderService> logger)
    {
        _orderRepository = orderRepository;
        _logger = logger;
    }

    public async Task<Order?> GetOrderAsync(Guid id)
    {
        _logger.LogInformation("Fetching order {OrderId}", id);
        return await _orderRepository.GetByIdAsync(id);
    }
}
```

字段声明、构造函数参数列表、构造函数体里的赋值——三套代码表达同一件事。每增加一个依赖，就要在三个地方同步修改。

切换到主构造函数之后：

```csharp
public class OrderService(
    IOrderRepository orderRepository,
    ILogger<OrderService> logger)
{
    public async Task<Order?> GetOrderAsync(Guid id)
    {
        logger.LogInformation("Fetching order {OrderId}", id);
        return await orderRepository.GetByIdAsync(id);
    }
}
```

字段声明没了，构造函数体没了，赋值语句没了。参数直接在整个类体内可用。

## 服务类是主构造函数最合适的地方

Milan 举了一个更贴近实际的结账服务示例，四个依赖，用主构造函数写出来：

```csharp
public class CheckoutService(
    IPaymentProcessor paymentProcessor,
    IOrderRepository orderRepository,
    ILogger<CheckoutService> logger,
    IOptions<CheckoutOptions> options)
{
    public async Task<CheckoutResult> ProcessAsync(
        Cart cart,
        CancellationToken ct = default)
    {
        var settings = options.Value;

        if (cart.Total < settings.MinimumOrderAmount)
        {
            logger.LogWarning("Order below minimum: {Total}", cart.Total);
            return CheckoutResult.BelowMinimum;
        }

        var order = Order.Create(cart);

        await paymentProcessor.ChargeAsync(order, ct);
        await orderRepository.SaveAsync(order, ct);

        logger.LogInformation("Checkout complete for order {OrderId}", order.Id);
        return CheckoutResult.Success;
    }
}
```

四个依赖，零样板。类从上到下读下来没有噪音。

这个模式之所以在服务类里效果好，是因为 DI 容器负责提供依赖，你只需要使用，不需要在构造时做验证或转换。主构造函数刚好契合这个使用模式。

## 用于领域实体时要注意一个细节

Milan 也在领域实体和值对象里用主构造函数来强制必填参数：

```csharp
public class Order(Guid customerId, Money total)
{
    public Guid Id { get; } = Guid.NewGuid();
    public Guid CustomerId { get; } = customerId;
    public Money Total { get; } = total;
    public OrderStatus Status { get; private set; } = OrderStatus.Pending;
    public DateTime CreatedAt { get; } = DateTime.UtcNow;

    public void Confirm()
    {
        if (Status != OrderStatus.Pending)
        {
            throw new InvalidOperationException(
                $"Cannot confirm order in {Status} status.");
        }
        Status = OrderStatus.Confirmed;
    }
}
```

这里有个和服务类不同的关键细节：`customerId` 和 `total` 被赋值给了属性（`= customerId`），而不是直接在方法体内使用参数变量。这个区别会引出下面说的陷阱。

## 必须知道的可变捕获陷阱

这是 Milan 一开始最担心的地方，也是他持观望态度这么久的原因。

主构造函数参数不是 `readonly` 字段。

当你在类体内直接使用主构造函数参数时，编译器把它们捕获为**可变变量**，背后不会生成 `readonly` 的字段。这意味着下面这段代码完全合法：

```csharp
public class OrderService(
    IOrderRepository orderRepository,
    ILogger<OrderService> logger)
{
    public async Task<Order?> GetOrderAsync(Guid id)
    {
        logger.LogInformation("Fetching order {OrderId}", id);
        return await orderRepository.GetByIdAsync(id);
    }

    public void SomeOtherMethod()
    {
        // This compiles. No warning. No error.
        orderRepository = null!;
        logger = null!;
    }
}
```

编译器不会报警告，也不会报错误。用传统构造函数 + `private readonly` 字段，编译器会立刻阻止你；用主构造函数，它保持沉默。

如果你确实需要不可变性保证，可以显式赋值给 `readonly` 字段：

```csharp
public class OrderService(
    IOrderRepository orderRepository,
    ILogger<OrderService> logger)
{
    private readonly IOrderRepository _orderRepository = orderRepository;
    private readonly ILogger<OrderService> _logger = logger;

    // ...
}
```

但这样你就失去了主构造函数带来的大部分好处，回到了字段声明加赋值的写法，只是语法换了个位置。

Milan 的实际经验是：在 DI 服务类里，他从没真正踩到这个坑。你不太可能在方法中间手滑把 `logger` 重新赋值。但在实体类或值类型里，不可变性本身就是需求，这时要格外谨慎。领域实体场景下，他选择把参数赋值给属性（像前面 `Order` 的例子），而不是直接用参数变量，这样属性本身可以声明为 `get;` 只读。

## 这三种情况他仍然用传统构造函数

主构造函数不是万能的。Milan 列了三种仍然选择传统写法的场景：

**需要复杂验证逻辑时。** 比如 `EmailAddress` 值对象在赋值前要检查格式，这种逻辑必须放在构造函数体里，主构造函数在类体开始前没有执行逻辑的地方：

```csharp
public class EmailAddress
{
    private readonly string _value;

    public EmailAddress(string value)
    {
        if (string.IsNullOrWhiteSpace(value) || !value.Contains('@'))
        {
            throw new ArgumentException("Invalid email address.", nameof(value));
        }
        _value = value;
    }
}
```

**需要多个构造函数重载时。** 主构造函数只支持一个签名。如果需要重载，只能用 `this(...)` 链接次级构造函数，很快就会变得混乱。

**依赖项过多时（5个以上）。** 一旦超过 5 个依赖，主构造函数那一行就很难读了。但这通常是类职责过多的信号，重构才是正解，不是靠格式技巧绕过去。

## 总结：哪些场景值得切换

Milan 的结论很清楚：

- **DI 服务类**：全面切换，样板代码减少明显，值得。
- **领域实体**：可以用，但把参数赋给属性，不要在方法体内直接用参数变量。
- **可变捕获陷阱**：知道它的存在就好，在服务类里几乎不会真正触发问题。
- **验证逻辑重、需要多重载、依赖项很多**：继续用传统构造函数。

主构造函数在 DI 服务类这个场景下的收益是真实的——类更短、更易读，代码从上到下没有噪音。陷阱也是真实存在的，但只要知道它，就能在合适的地方选择合适的方式。

## 参考

- [Why I Switched to Primary Constructors for DI in C#](https://www.milanjovanovic.tech/blog/why-i-switched-to-primary-constructors-for-di-in-csharp) — Milan Jovanović
