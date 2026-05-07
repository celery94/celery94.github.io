---
pubDatetime: 2026-05-07T07:56:35+08:00
title: "C# 外观模式实战：用一个订单处理系统讲清楚完整实现"
description: "外观模式的经典教程总爱拿「家庭影院遥控器」举例，实际开发中遇到的是支付、库存、通知三个子系统同时协调。本文从真实电商下单场景出发，完整实现 OrderFacade，覆盖设计、单元测试和依赖注入注册，一次讲清楚。"
tags: ["C#", "设计模式", "外观模式", "Architecture"]
slug: "facade-pattern-csharp-order-processing"
ogImage: "../../assets/779/01-cover.png"
source: "https://www.devleader.ca/2026/05/06/facade-pattern-realworld-example-in-c-complete-implementation"
---

大多数外观模式的教程都会给你一个家庭影院的例子：一个遥控器封装了电视、音响、蓝光播放器……理解概念没问题，但真的帮不到你当下的工作——你面对的是支付网关、库存系统、通知服务，还有把它们串起来的协调逻辑被复制粘贴在每一个 Controller 和后台任务里。

这篇文章从电商下单场景出发，完整实现一个 `OrderFacade`。内容覆盖：为什么需要外观、子系统设计、外观本身的实现、单元测试、依赖注入注册，以及几个常见问题的直接回答。代码可以直接编译运行。

![外观模式封面图](../../assets/779/01-cover.png)

## 没有外观时，Controller 长什么样

客户下单时，应用要做四件事：检查库存、扣款、预占库存、发送确认邮件。每件事属于不同的服务，有自己的接口和错误处理。

当 Controller 直接和每个子系统对话时：

```csharp
public class OrderController
{
    private readonly PaymentService _payment;
    private readonly InventoryService _inventory;
    private readonly NotificationService _notifications;

    public async Task<string> PlaceOrder(
        string customerId,
        List<OrderItem> items,
        PaymentDetails paymentInfo)
    {
        // 逐项检查库存
        foreach (var item in items)
        {
            bool inStock = await _inventory
                .CheckStockAsync(item.Sku, item.Quantity);
            if (!inStock)
                throw new InvalidOperationException(
                    $"Item {item.Sku} is out of stock.");
        }

        // 计算总金额
        decimal total = items.Sum(
            i => i.UnitPrice * i.Quantity);

        // 扣款
        var charge = await _payment.ChargeAsync(
            paymentInfo.CardToken, total, "usd");

        if (!charge.Success)
            throw new InvalidOperationException("Payment failed.");

        // 预占库存
        foreach (var item in items)
            await _inventory.ReserveAsync(item.Sku, item.Quantity);

        // 发送确认
        await _notifications.SendOrderConfirmationAsync(
            customerId, charge.TransactionId, items);

        return charge.TransactionId;
    }
}
```

问题不在某一行代码，而是这段协调逻辑会出现在每一个需要下单的地方——Controller、后台 Job、API 端点。任何一处需要变更（加入欺诈检测、税费计算），就要改所有地方。测试时每个 Controller 方法都要 Mock 三个服务。

外观模式的答案是：把这段协调逻辑放进一个专用类，调用方只管一个方法。

## 三个子系统

下面把三个子系统单独定义好，它们各自只负责自己的职责。

### 支付服务

```csharp
public sealed class PaymentResult
{
    public bool Success { get; init; }
    public string TransactionId { get; init; } = "";
    public string ErrorMessage { get; init; } = "";
}

public interface IPaymentService
{
    Task<PaymentResult> ChargeAsync(
        string cardToken, decimal amount, string currency);

    Task<PaymentResult> RefundAsync(
        string transactionId, decimal amount);
}

public sealed class PaymentService : IPaymentService
{
    public Task<PaymentResult> ChargeAsync(
        string cardToken, decimal amount, string currency)
    {
        // 模拟调用支付网关
        return Task.FromResult(new PaymentResult
        {
            Success = true,
            TransactionId = $"txn_{Guid.NewGuid():N}"
        });
    }

    public Task<PaymentResult> RefundAsync(
        string transactionId, decimal amount)
    {
        return Task.FromResult(new PaymentResult
        {
            Success = true,
            TransactionId = transactionId
        });
    }
}
```

### 库存服务

```csharp
public interface IInventoryService
{
    Task<bool> CheckStockAsync(string sku, int quantity);
    Task ReserveAsync(string sku, int quantity);
    Task ReleaseAsync(string sku, int quantity);
}

public sealed class InventoryService : IInventoryService
{
    private readonly Dictionary<string, int> _stock = new()
    {
        ["SKU-001"] = 50,
        ["SKU-002"] = 120,
        ["SKU-003"] = 5
    };

    public Task<bool> CheckStockAsync(string sku, int quantity)
    {
        bool available = _stock.TryGetValue(sku, out int current)
            && current >= quantity;
        return Task.FromResult(available);
    }

    public Task ReserveAsync(string sku, int quantity)
    {
        if (_stock.ContainsKey(sku))
            _stock[sku] -= quantity;
        return Task.CompletedTask;
    }

    public Task ReleaseAsync(string sku, int quantity)
    {
        if (_stock.ContainsKey(sku))
            _stock[sku] += quantity;
        return Task.CompletedTask;
    }
}
```

### 通知服务

```csharp
public interface INotificationService
{
    Task SendOrderConfirmationAsync(
        string customerId, string orderId, decimal totalAmount);

    Task SendPaymentFailureAsync(
        string customerId, string reason);

    Task SendRefundConfirmationAsync(
        string customerId, string orderId, decimal refundAmount);
}

public sealed class NotificationService : INotificationService
{
    public Task SendOrderConfirmationAsync(
        string customerId, string orderId, decimal totalAmount)
    {
        Console.WriteLine(
            $"Order {orderId} confirmed for {customerId}. " +
            $"Total: {totalAmount:C}");
        return Task.CompletedTask;
    }

    public Task SendPaymentFailureAsync(
        string customerId, string reason)
    {
        Console.WriteLine($"Payment failed for {customerId}: {reason}");
        return Task.CompletedTask;
    }

    public Task SendRefundConfirmationAsync(
        string customerId, string orderId, decimal refundAmount)
    {
        Console.WriteLine(
            $"Refund of {refundAmount:C} issued for order {orderId}");
        return Task.CompletedTask;
    }
}
```

三个服务各自独立、可单独测试。问题从来不是它们本身，而是把它们串起来的那段逻辑。

## 外观的领域类型

在实现外观之前，先定义调用方真正关心的类型。这些类型属于外观层，与任何子系统的内部类型解耦：

```csharp
public sealed record OrderItem(
    string Sku, int Quantity, decimal UnitPrice);

public sealed record PaymentDetails(string CardToken);

public sealed record OrderRequest(
    string CustomerId,
    List<OrderItem> Items,
    PaymentDetails Payment);

public sealed record OrderResult
{
    public bool Success { get; init; }
    public string OrderId { get; init; } = "";
    public decimal TotalCharged { get; init; }
    public string ErrorMessage { get; init; } = "";
}
```

调用方只需要知道这四个类型，不需要了解卡 token 怎么传给支付网关、库存怎么按 SKU 查询，也不需要关心通知渠道的选择。

## 实现 OrderFacade

外观类协调三个子系统，对外只暴露两个方法：下单和退款。

```csharp
public interface IOrderFacade
{
    Task<OrderResult> PlaceOrderAsync(OrderRequest request);

    Task<OrderResult> RefundOrderAsync(
        string customerId, string orderId, List<OrderItem> items);
}

public sealed class OrderFacade : IOrderFacade
{
    private readonly IPaymentService _payment;
    private readonly IInventoryService _inventory;
    private readonly INotificationService _notifications;

    public OrderFacade(
        IPaymentService payment,
        IInventoryService inventory,
        INotificationService notifications)
    {
        _payment = payment;
        _inventory = inventory;
        _notifications = notifications;
    }

    public async Task<OrderResult> PlaceOrderAsync(OrderRequest request)
    {
        // 第一步：校验所有商品库存
        foreach (var item in request.Items)
        {
            bool inStock = await _inventory
                .CheckStockAsync(item.Sku, item.Quantity);

            if (!inStock)
            {
                return new OrderResult
                {
                    Success = false,
                    ErrorMessage = $"Item {item.Sku} is out of stock."
                };
            }
        }

        // 第二步：计算总金额
        decimal total = request.Items.Sum(
            i => i.UnitPrice * i.Quantity);

        // 第三步：扣款
        var paymentResult = await _payment.ChargeAsync(
            request.Payment.CardToken, total, "usd");

        if (!paymentResult.Success)
        {
            await _notifications.SendPaymentFailureAsync(
                request.CustomerId, paymentResult.ErrorMessage);

            return new OrderResult
            {
                Success = false,
                ErrorMessage = "Payment processing failed."
            };
        }

        // 第四步：预占库存
        foreach (var item in request.Items)
            await _inventory.ReserveAsync(item.Sku, item.Quantity);

        // 第五步：发送确认通知
        await _notifications.SendOrderConfirmationAsync(
            request.CustomerId, paymentResult.TransactionId, total);

        return new OrderResult
        {
            Success = true,
            OrderId = paymentResult.TransactionId,
            TotalCharged = total
        };
    }

    public async Task<OrderResult> RefundOrderAsync(
        string customerId, string orderId, List<OrderItem> items)
    {
        decimal refundAmount = items.Sum(i => i.UnitPrice * i.Quantity);

        // 第一步：处理退款
        var refundResult = await _payment.RefundAsync(
            orderId, refundAmount);

        if (!refundResult.Success)
        {
            return new OrderResult
            {
                Success = false,
                ErrorMessage = "Refund processing failed."
            };
        }

        // 第二步：释放库存
        foreach (var item in items)
            await _inventory.ReleaseAsync(item.Sku, item.Quantity);

        // 第三步：通知客户
        await _notifications.SendRefundConfirmationAsync(
            customerId, orderId, refundAmount);

        return new OrderResult
        {
            Success = true,
            OrderId = orderId,
            TotalCharged = -refundAmount
        };
    }
}
```

注意 `PlaceOrderAsync` 里的顺序：库存校验在扣款之前。如果某个 SKU 没货，直接返回失败，不会产生任何扣款。如果扣款失败，外观负责发送付款失败通知，调用方完全不用关心这个分支。

这就是外观模式的核心价值——调用方只看到成功或失败的结果，看不到多步骤之间的协调细节。

## 使用外观后的 Controller

有了外观之后，Controller 变成什么样子：

```csharp
public class OrderController
{
    private readonly IOrderFacade _orderFacade;

    public OrderController(IOrderFacade orderFacade)
    {
        _orderFacade = orderFacade;
    }

    public async Task<OrderResult> PlaceOrder(
        string customerId,
        List<OrderItem> items,
        string cardToken)
    {
        var request = new OrderRequest(
            CustomerId: customerId,
            Items: items,
            Payment: new PaymentDetails(cardToken));

        return await _orderFacade.PlaceOrderAsync(request);
    }
}
```

没有库存循环，没有支付错误处理，没有通知调用。Controller 只做一件事：构建请求，委托给外观。

对比文章开头的版本，差距一目了然。

## 单元测试

外观的单元测试验证的是编排逻辑——每个子系统是否在正确的时机以正确的参数被调用。

```csharp
public sealed class OrderFacadeTests
{
    private readonly Mock<IPaymentService> _mockPayment;
    private readonly Mock<IInventoryService> _mockInventory;
    private readonly Mock<INotificationService> _mockNotifications;
    private readonly OrderFacade _facade;

    public OrderFacadeTests()
    {
        _mockPayment = new Mock<IPaymentService>();
        _mockInventory = new Mock<IInventoryService>();
        _mockNotifications = new Mock<INotificationService>();

        _facade = new OrderFacade(
            _mockPayment.Object,
            _mockInventory.Object,
            _mockNotifications.Object);
    }

    [Fact]
    public async Task PlaceOrderAsync_AllItemsInStock_ReturnsSuccess()
    {
        var items = new List<OrderItem>
        {
            new("SKU-001", 2, 25.00m),
            new("SKU-002", 1, 15.00m)
        };

        _mockInventory
            .Setup(i => i.CheckStockAsync(
                It.IsAny<string>(), It.IsAny<int>()))
            .ReturnsAsync(true);

        _mockPayment
            .Setup(p => p.ChargeAsync(
                It.IsAny<string>(), It.IsAny<decimal>(), It.IsAny<string>()))
            .ReturnsAsync(new PaymentResult
            {
                Success = true,
                TransactionId = "txn_abc123"
            });

        var request = new OrderRequest(
            "cust_001", items, new PaymentDetails("tok_visa"));

        var result = await _facade.PlaceOrderAsync(request);

        Assert.True(result.Success);
        Assert.Equal("txn_abc123", result.OrderId);
        Assert.Equal(65.00m, result.TotalCharged);

        _mockNotifications.Verify(
            n => n.SendOrderConfirmationAsync(
                "cust_001", "txn_abc123", 65.00m),
            Times.Once);
    }

    [Fact]
    public async Task PlaceOrderAsync_ItemOutOfStock_ReturnsFailure()
    {
        var items = new List<OrderItem>
        {
            new("SKU-999", 1, 50.00m)
        };

        _mockInventory
            .Setup(i => i.CheckStockAsync("SKU-999", 1))
            .ReturnsAsync(false);

        var request = new OrderRequest(
            "cust_002", items, new PaymentDetails("tok_visa"));

        var result = await _facade.PlaceOrderAsync(request);

        Assert.False(result.Success);
        Assert.Contains("out of stock", result.ErrorMessage);

        // 库存不足时，不应该尝试扣款
        _mockPayment.Verify(
            p => p.ChargeAsync(
                It.IsAny<string>(), It.IsAny<decimal>(), It.IsAny<string>()),
            Times.Never);
    }

    [Fact]
    public async Task PlaceOrderAsync_PaymentFails_NotifiesCustomer()
    {
        var items = new List<OrderItem>
        {
            new("SKU-001", 1, 30.00m)
        };

        _mockInventory
            .Setup(i => i.CheckStockAsync(
                It.IsAny<string>(), It.IsAny<int>()))
            .ReturnsAsync(true);

        _mockPayment
            .Setup(p => p.ChargeAsync(
                It.IsAny<string>(), It.IsAny<decimal>(), It.IsAny<string>()))
            .ReturnsAsync(new PaymentResult
            {
                Success = false,
                ErrorMessage = "Card declined"
            });

        var request = new OrderRequest(
            "cust_003", items, new PaymentDetails("tok_declined"));

        var result = await _facade.PlaceOrderAsync(request);

        Assert.False(result.Success);

        // 扣款失败要通知客户
        _mockNotifications.Verify(
            n => n.SendPaymentFailureAsync("cust_003", "Card declined"),
            Times.Once);

        // 扣款失败后不应该预占库存
        _mockInventory.Verify(
            i => i.ReserveAsync(It.IsAny<string>(), It.IsAny<int>()),
            Times.Never);
    }

    [Fact]
    public async Task RefundOrderAsync_ValidOrder_ReleasesInventory()
    {
        var items = new List<OrderItem>
        {
            new("SKU-001", 2, 25.00m)
        };

        _mockPayment
            .Setup(p => p.RefundAsync("txn_abc123", 50.00m))
            .ReturnsAsync(new PaymentResult
            {
                Success = true,
                TransactionId = "txn_abc123"
            });

        var result = await _facade.RefundOrderAsync(
            "cust_001", "txn_abc123", items);

        Assert.True(result.Success);

        _mockInventory.Verify(
            i => i.ReleaseAsync("SKU-001", 2),
            Times.Once);

        _mockNotifications.Verify(
            n => n.SendRefundConfirmationAsync(
                "cust_001", "txn_abc123", 50.00m),
            Times.Once);
    }
}
```

注意几个关键断言：库存不足时验证付款从未被调用；付款失败时验证库存预占从未发生。这些断言验证的是外观的顺序逻辑——如果协调代码散落在各个 Controller 里，这类 bug 很难被测试覆盖到。

## 注册到依赖注入容器

因为外观依赖的是接口，替换实现只需要改一行注册：

```csharp
using Microsoft.Extensions.DependencyInjection;

public static class OrderServiceRegistration
{
    public static IServiceCollection AddOrderProcessing(
        this IServiceCollection services)
    {
        services.AddSingleton<IPaymentService, PaymentService>();
        services.AddSingleton<IInventoryService, InventoryService>();
        services.AddSingleton<INotificationService, NotificationService>();
        services.AddTransient<IOrderFacade, OrderFacade>();

        return services;
    }
}
```

在 `Program.cs` 里一行搞定：

```csharp
builder.Services.AddOrderProcessing();
```

以后把 `PaymentService` 替换成 Stripe 集成，只改注册那行。外观不变，Controller 不变。

## 适合用外观的场景

电商下单是教科书级别的场景，但相同的结构适用于：

- **用户注册流程**：校验、创建账号、发欢迎邮件、分配资源
- **报表生成管道**：查询数据、聚合计算、生成文件、推送到存储
- **任何需要按顺序触碰多个服务的业务操作**

判断是否需要外观，看一个信号：同样的多服务协调逻辑是否在多个地方重复出现。一旦有复制粘贴，就该提取成一个专用类。

外观不违反单一职责原则——外观的职责就是编排，不实现支付、不管库存、不发通知，只协调。这是一个职责、一个变化轴。

## 外观 vs 适配器 vs 策略

容易混淆的三个模式：

- **适配器**：把一个接口翻译成另一个，解决接口不兼容的问题
- **外观**：简化对一组已经能正常工作的接口的访问，不翻译
- **策略**：允许在运行时替换可互换的算法，外观不做替换

实践中这些模式经常组合使用。外观内部可以用适配器来规范化第三方 API，也可以用策略模式在多个支付提供商之间选择。

## 常见问题

**外观应该暴露子系统的所有方法吗？**  
不。只暴露调用方真正需要的高层操作。`OrderFacade` 只暴露 `PlaceOrderAsync` 和 `RefundOrderAsync`，不暴露检查库存、单独扣款或发邮件的方法。如果调用方需要直接操作子系统，让它依赖子系统接口即可。

**外观可以调用另一个外观吗？**  
可以，而且挺常见。一个大型应用可能有 `OrderFacade` 在下单时委托给 `ShippingFacade`。注意不要产生循环依赖，依赖关系要保持单向流动。

**多个子系统的错误怎么处理？**  
优先设计成让错误不需要补偿。本文例子里库存校验在扣款之前，所以不存在「扣款成功但库存不够再退款」的场景。对于更复杂的流程，可以考虑命令模式（Command Pattern）来实现补偿事务。

**对性能有影响吗？**  
外观只增加一次方法调用，开销可以忽略不计。没有多余的网络调用或 I/O，只是把协调逻辑搬进了一个专用类。

## 参考

- [原文：Facade Pattern Real-World Example in C#: Complete Implementation](https://www.devleader.ca/2026/05/06/facade-pattern-realworld-example-in-c-complete-implementation)
- [适配器模式 C# 完整指南](https://www.devleader.ca/2026/04/07/adapter-design-pattern-in-c-complete-guide-with-examples)
- [命令模式 C# 完整指南](https://www.devleader.ca/2026/04/14/command-design-pattern-in-c-complete-guide-with-examples)
- [控制反转（IoC）简介](https://www.devleader.ca/2024/01/07/what-is-inversion-of-control-a-simplified-beginners-guide)
