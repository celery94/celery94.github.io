---
pubDatetime: 2026-04-01T09:40:00+08:00
title: "工厂方法模式实战：用支付系统讲清楚 C# 完整实现"
description: "用电商支付场景从零搭建工厂方法模式：定义接口、实现多个支付处理器、编写抽象创建者和具体子类，再集成 DI 容器并演示测试写法，让你真正看懂这个模式在生产代码里如何解决扩展性问题。"
tags: ["C#", "设计模式", "工厂方法", ".NET"]
slug: "factory-method-pattern-csharp-payment-system"
ogImage: "../../assets/696/01-cover.png"
source: "https://www.devleader.ca/2026/03/31/factory-method-pattern-realworld-example-in-c-complete-implementation"
---

设计模式教程最常见的毛病是举例太假——用"圆形"和"动物"来讲工厂方法，看完还是不知道该怎么用到真实代码里。这篇文章换一个思路：用一个支付处理系统来演示工厂方法模式（Factory Method Pattern）的完整实现，这种系统在电商或 SaaS 产品里随处可见。

读完你会看到：这个模式到底解决了什么扩展性问题，每一步设计背后的理由是什么，以及怎么让它跟 ASP.NET Core 的依赖注入和单元测试配合工作。

## 目录

## 问题：多个支付渠道，代码乱成一团

设想你在给电商平台开发支付模块，需要同时支持 Stripe（信用卡）、PayPal（电子钱包）和银行转账（企业客户）。三家的 API 风格不同、认证方式不同、响应格式也不同。

最直接的写法是在业务代码里堆 `if/else`：

```csharp
// 问题：创建逻辑散落在各处
public class OrderService
{
    public PaymentResult ProcessPayment(
        Order order, string provider)
    {
        if (provider == "stripe")
        {
            var stripe = new StripePaymentHandler();
            stripe.SetApiKey(config["StripeKey"]);
            return stripe.Charge(order.Total);
        }
        else if (provider == "paypal")
        {
            var paypal = new PayPalPaymentHandler();
            paypal.SetClientId(config["PayPalClientId"]);
            paypal.SetSecret(config["PayPalSecret"]);
            return paypal.ExecutePayment(order.Total);
        }
        else if (provider == "bank")
        {
            var bank = new BankTransferHandler();
            bank.SetRoutingInfo(config["BankRouting"]);
            return bank.InitiateTransfer(order.Total);
        }

        throw new ArgumentException(
            $"Unknown provider: {provider}"
        );
    }
}
```

这段代码有几个明显问题：每加一个支付渠道就要改 `OrderService`；创建逻辑、配置和使用全部混在一起；想单独测试某个渠道，还得把其他渠道的依赖一起处理。这正是工厂方法模式要解决的问题。

## 第一步：定义产品接口

所有支付处理器都必须实现同一个接口，这是整个模式的基础。接口捕获每个渠道都必须支持的核心行为：

```csharp
// Product 接口：每个支付处理器都必须实现
public interface IPaymentHandler
{
    string ProviderName { get; }

    Task<PaymentResult> ProcessPaymentAsync(
        PaymentRequest request);

    Task<RefundResult> ProcessRefundAsync(
        string transactionId,
        decimal amount);

    Task<PaymentStatus> CheckStatusAsync(
        string transactionId);
}

// 支付系统的数据契约
public record PaymentRequest(
    decimal Amount,
    string Currency,
    string CustomerEmail,
    Dictionary<string, string> Metadata);

public record PaymentResult(
    bool Success,
    string TransactionId,
    string Message);

public record RefundResult(
    bool Success,
    string RefundId,
    string Message);

public enum PaymentStatus
{
    Pending,
    Completed,
    Failed,
    Refunded
}
```

接口用了异步方法，因为支付都涉及网络调用，这是实际生产场景的真实需要。Record 类型保证数据契约简洁且不可变。

## 第二步：实现各个支付处理器

每个处理器（Concrete Product）实现 `IPaymentHandler`，封装自己渠道的具体行为。

### Stripe 处理器

```csharp
public class StripePaymentHandler : IPaymentHandler
{
    public string ProviderName => "Stripe";

    public async Task<PaymentResult> ProcessPaymentAsync(
        PaymentRequest request)
    {
        // 生产环境这里会调用 Stripe API
        Console.WriteLine(
            $"[Stripe] Processing {request.Currency} " +
            $"{request.Amount} for {request.CustomerEmail}"
        );

        await Task.Delay(100); // 模拟 API 调用

        var transactionId = $"stripe_{Guid.NewGuid():N}";
        return new PaymentResult(
            true, transactionId,
            "Payment processed via Stripe");
    }

    public async Task<RefundResult> ProcessRefundAsync(
        string transactionId, decimal amount)
    {
        Console.WriteLine(
            $"[Stripe] Refunding {amount} for " +
            $"transaction {transactionId}"
        );

        await Task.Delay(50);

        return new RefundResult(
            true,
            $"refund_{Guid.NewGuid():N}",
            "Refund processed via Stripe");
    }

    public async Task<PaymentStatus> CheckStatusAsync(
        string transactionId)
    {
        await Task.Delay(30);
        return PaymentStatus.Completed;
    }
}
```

### PayPal 处理器

```csharp
public class PayPalPaymentHandler : IPaymentHandler
{
    public string ProviderName => "PayPal";

    public async Task<PaymentResult> ProcessPaymentAsync(
        PaymentRequest request)
    {
        Console.WriteLine(
            $"[PayPal] Creating payment of " +
            $"{request.Currency} {request.Amount}"
        );

        await Task.Delay(150); // PayPal API 通常稍慢

        var transactionId = $"paypal_{Guid.NewGuid():N}";
        return new PaymentResult(
            true, transactionId,
            "Payment processed via PayPal");
    }

    public async Task<RefundResult> ProcessRefundAsync(
        string transactionId, decimal amount)
    {
        Console.WriteLine(
            $"[PayPal] Issuing refund of {amount}"
        );

        await Task.Delay(100);

        return new RefundResult(
            true,
            $"pp_refund_{Guid.NewGuid():N}",
            "Refund processed via PayPal");
    }

    public async Task<PaymentStatus> CheckStatusAsync(
        string transactionId)
    {
        await Task.Delay(50);
        return PaymentStatus.Completed;
    }
}
```

### 银行转账处理器

```csharp
public class BankTransferHandler : IPaymentHandler
{
    public string ProviderName => "BankTransfer";

    public async Task<PaymentResult> ProcessPaymentAsync(
        PaymentRequest request)
    {
        Console.WriteLine(
            $"[Bank] Initiating transfer of " +
            $"{request.Currency} {request.Amount}"
        );

        await Task.Delay(200); // 银行转账发起耗时更长

        var transactionId = $"bank_{Guid.NewGuid():N}";
        // 银行转账在确认前会保持 pending 状态
        return new PaymentResult(
            true, transactionId,
            "Transfer initiated - pending confirmation");
    }

    public async Task<RefundResult> ProcessRefundAsync(
        string transactionId, decimal amount)
    {
        Console.WriteLine(
            $"[Bank] Processing refund of {amount}"
        );

        await Task.Delay(150);

        return new RefundResult(
            true,
            $"bank_ref_{Guid.NewGuid():N}",
            "Bank refund initiated");
    }

    public async Task<PaymentStatus> CheckStatusAsync(
        string transactionId)
    {
        await Task.Delay(80);
        // 银行转账会在 Pending 状态停留更长时间
        return PaymentStatus.Pending;
    }
}
```

三个处理器各有不同的行为特征：Stripe 立即完成、PayPal 响应稍慢、银行转账返回 Pending 状态。这些差异在真实支付集成中是实际存在的。

## 第三步：抽象创建者

抽象创建者（Abstract Creator）是工厂方法模式的核心。它声明工厂方法，同时包含使用产品的业务逻辑——但它不知道具体产品是什么类型：

```csharp
// Creator：声明工厂方法，包含使用产品的业务逻辑
public abstract class PaymentProcessorCreator
{
    // 工厂方法——子类决定实例化哪个处理器
    public abstract IPaymentHandler CreateHandler();

    // 使用工厂方法的模板方法
    public async Task<PaymentResult> ProcessOrderPaymentAsync(
        Order order)
    {
        var handler = CreateHandler();

        Console.WriteLine(
            $"Processing order {order.OrderId} via " +
            $"{handler.ProviderName}"
        );

        var request = new PaymentRequest(
            order.Total,
            order.Currency,
            order.CustomerEmail,
            new Dictionary<string, string>
            {
                ["orderId"] = order.OrderId,
                ["source"] = "web"
            });

        var result = await handler.ProcessPaymentAsync(
            request);

        if (result.Success)
        {
            Console.WriteLine(
                $"Payment successful: {result.TransactionId}"
            );
        }
        else
        {
            Console.WriteLine(
                $"Payment failed: {result.Message}"
            );
        }

        return result;
    }

    public async Task<RefundResult> ProcessRefundAsync(
        string transactionId, decimal amount)
    {
        var handler = CreateHandler();

        Console.WriteLine(
            $"Processing refund via {handler.ProviderName}"
        );

        return await handler.ProcessRefundAsync(
            transactionId, amount);
    }
}

// 订单数据类型
public record Order(
    string OrderId,
    decimal Total,
    string Currency,
    string CustomerEmail);
```

`ProcessOrderPaymentAsync` 是一个模板方法，业务流程固定写在抽象创建者里，而具体用哪个处理器由子类通过 `CreateHandler()` 决定。这个分离使得业务流程在所有支付渠道之间保持一致。

## 第四步：具体创建者

每个具体创建者（Concrete Creator）只覆盖工厂方法，返回对应的处理器。这些类故意写得很简单，因为它们的职责就是决定创建哪个产品：

```csharp
public class StripePaymentCreator
    : PaymentProcessorCreator
{
    public override IPaymentHandler CreateHandler()
    {
        return new StripePaymentHandler();
    }
}

public class PayPalPaymentCreator
    : PaymentProcessorCreator
{
    public override IPaymentHandler CreateHandler()
    {
        return new PayPalPaymentHandler();
    }
}

public class BankTransferCreator
    : PaymentProcessorCreator
{
    public override IPaymentHandler CreateHandler()
    {
        return new BankTransferHandler();
    }
}
```

每个创建者精简到位。没有条件判断，没有配置混杂，只有在构建方式变化时才需要改动。

## 第五步：组装整个系统

客户端代码通过抽象创建者工作，可以在不修改任何代码的情况下切换支付渠道：

```csharp
public class CheckoutService
{
    private readonly PaymentProcessorCreator _paymentCreator;

    // 创建者通过注入传入——客户端不直接引用具体处理器
    public CheckoutService(
        PaymentProcessorCreator paymentCreator)
    {
        _paymentCreator = paymentCreator;
    }

    public async Task<PaymentResult> CheckoutAsync(
        Order order)
    {
        Console.WriteLine(
            $"Starting checkout for order {order.OrderId}"
        );

        var result = await _paymentCreator
            .ProcessOrderPaymentAsync(order);

        if (result.Success)
        {
            Console.WriteLine("Checkout complete!");
        }

        return result;
    }
}

// 使用示例
var order = new Order(
    "ORD-12345", 99.99m, "USD", "customer@email.com");

// 通过 Stripe 支付
var stripeCheckout = new CheckoutService(
    new StripePaymentCreator());
await stripeCheckout.CheckoutAsync(order);

// 通过 PayPal 支付——同一接口，不同渠道
var paypalCheckout = new CheckoutService(
    new PayPalPaymentCreator());
await paypalCheckout.CheckoutAsync(order);
```

`CheckoutService` 对 Stripe、PayPal 或银行转账一无所知，完全通过抽象 `PaymentProcessorCreator` 运作。结账逻辑与支付渠道彻底解耦。

## 扩展系统：添加加密货币支付

工厂方法模式最大的优势在于扩展有多容易。假设业务要加入加密货币支付，只需新建两个类，不碰任何现有代码——不改 `CheckoutService`，不改抽象创建者，不改已有的处理器：

```csharp
// 新产品——无需修改现有代码
public class CryptoPaymentHandler : IPaymentHandler
{
    public string ProviderName => "Crypto";

    public async Task<PaymentResult> ProcessPaymentAsync(
        PaymentRequest request)
    {
        Console.WriteLine(
            $"[Crypto] Processing {request.Amount} " +
            $"crypto payment"
        );

        await Task.Delay(300); // 等待区块链确认

        return new PaymentResult(
            true,
            $"crypto_{Guid.NewGuid():N}",
            "Crypto payment submitted to blockchain");
    }

    public Task<RefundResult> ProcessRefundAsync(
        string transactionId, decimal amount)
    {
        return Task.FromResult(new RefundResult(
            false, "",
            "Crypto refunds are not supported"));
    }

    public async Task<PaymentStatus> CheckStatusAsync(
        string transactionId)
    {
        await Task.Delay(100);
        return PaymentStatus.Pending;
    }
}

// 新创建者——无需修改现有代码
public class CryptoPaymentCreator
    : PaymentProcessorCreator
{
    public override IPaymentHandler CreateHandler()
    {
        return new CryptoPaymentHandler();
    }
}
```

就这些。开放/关闭原则（Open/Closed Principle）得到完整满足：系统对扩展开放（新增支付渠道），对修改关闭（现有代码不动）。

## 集成 ASP.NET Core 依赖注入

在真实的 ASP.NET Core 应用中，把创建者注册到 DI 容器，根据配置或运行时上下文解析：

```csharp
// 在 Program.cs 中注册
builder.Services.AddKeyedSingleton<PaymentProcessorCreator>(
    "stripe", (_, _) => new StripePaymentCreator());
builder.Services.AddKeyedSingleton<PaymentProcessorCreator>(
    "paypal", (_, _) => new PayPalPaymentCreator());
builder.Services.AddKeyedSingleton<PaymentProcessorCreator>(
    "bank", (_, _) => new BankTransferCreator());

// 根据客户选择的支付方式解析
app.MapPost("/checkout", async (
    [FromBody] CheckoutRequest request,
    [FromKeyedServices("stripe")]
    PaymentProcessorCreator defaultCreator,
    IServiceProvider sp) =>
{
    // 根据支付方式选择对应创建者
    var creator = sp.GetKeyedService<PaymentProcessorCreator>(
        request.PaymentMethod) ?? defaultCreator;

    var checkout = new CheckoutService(creator);
    var order = new Order(
        request.OrderId,
        request.Amount,
        "USD",
        request.Email);

    return await checkout.CheckoutAsync(order);
});
```

这种写法利用控制反转（IoC）管理工厂的生命周期，同时保留了工厂方法模式的多态创建能力。

## 测试：最直接的好处

工厂方法模式让测试变得极其简单，你可以创建专门的测试工厂，返回行为可预测的实现：

```csharp
// 测试用处理器——结果完全可控
public class TestPaymentHandler : IPaymentHandler
{
    public string ProviderName => "Test";
    public bool ShouldSucceed { get; set; } = true;

    public Task<PaymentResult> ProcessPaymentAsync(
        PaymentRequest request)
    {
        return Task.FromResult(new PaymentResult(
            ShouldSucceed,
            "test_transaction_123",
            ShouldSucceed ? "Success" : "Failed"));
    }

    public Task<RefundResult> ProcessRefundAsync(
        string transactionId, decimal amount)
    {
        return Task.FromResult(new RefundResult(
            true, "test_refund_123", "Refunded"));
    }

    public Task<PaymentStatus> CheckStatusAsync(
        string transactionId)
    {
        return Task.FromResult(PaymentStatus.Completed);
    }
}

// 测试用创建者
public class TestPaymentCreator : PaymentProcessorCreator
{
    private readonly TestPaymentHandler _handler = new();

    public TestPaymentHandler Handler => _handler;

    public override IPaymentHandler CreateHandler()
        => _handler;
}

// 单元测试示例
[Fact]
public async Task Checkout_WithSuccessfulPayment_Completes()
{
    // Arrange
    var creator = new TestPaymentCreator();
    var service = new CheckoutService(creator);
    var order = new Order(
        "TEST-001", 50.00m, "USD", "test@example.com");

    // Act
    var result = await service.CheckoutAsync(order);

    // Assert
    Assert.True(result.Success);
    Assert.Equal("test_transaction_123",
        result.TransactionId);
}

[Fact]
public async Task Checkout_WithFailedPayment_ReturnsFailure()
{
    // Arrange
    var creator = new TestPaymentCreator();
    creator.Handler.ShouldSucceed = false;
    var service = new CheckoutService(creator);
    var order = new Order(
        "TEST-002", 75.00m, "USD", "test@example.com");

    // Act
    var result = await service.CheckoutAsync(order);

    // Assert
    Assert.False(result.Success);
}
```

不需要 mock 真实的支付 API，不需要处理网络调用，不需要在测试环境里管理 API 密钥。你可以模拟成功、失败、部分退款等任意场景，测试完全隔离在本地。

## 适用场景

同样的方式可以用在很多其他场景：文档导出系统（PDF、CSV、Excel 导出器）、通知系统（邮件、短信、Push 通知处理器）、数据导入管道（不同文件格式的解析器）。

判断是否该用这个模式，可以问自己一个问题：**我有没有同一行为的多种实现，需要在运行时选择？** 如果有，而且每种实现复杂到需要独立的类来封装，工厂方法模式一般是合适的选择。

## 几个常见问题

**不同渠道的配置参数不一样怎么办？** 每个具体创建者可以通过构造函数接受自己的配置，抽象创建者不需要知道这些配置差异。

**和 switch 语句选支付渠道相比有什么区别？** Switch 语句把选择逻辑集中在一处，但违反开放/关闭原则——每加一个渠道都要改那个 switch。工厂方法把每个渠道的创建逻辑独立成类，新增渠道时不碰已有代码。

**只有一个支付渠道时需要用这个模式吗？** 不一定。如果确定只有一个渠道，这个模式会增加不必要的抽象层。但如果未来有扩展的可能性，早期投入是值得的——因为后期再来改动会更麻烦。

**渠道特有的功能（不在公共接口里的）怎么处理？** 用接口组合。为特有能力创建额外的接口（比如 `ICryptoPaymentHandler` 加一个 `GetBlockchainAddress` 方法），然后用模式匹配判断处理器是否支持该功能。

## 小结

这个支付处理系统的例子说明了工厂方法模式如何把一个僵硬、难维护的代码结构变成灵活可扩展的架构。

从最初的 `OrderService`——条件逻辑散落各处、每加一个渠道就要改类——到最终的架构：每个支付渠道被隔离在自己的处理器和工厂里，结账服务完全通过抽象运作，可测试、可扩展、易读懂。

这个模式的核心是在**做什么**（处理支付）和**怎么做**（通过具体渠道）之间建立清晰的边界。这个边界正是系统在增长和演化过程中保持可维护性的关键。把同样的思路用到你自己的领域，你会找到很多可以用工厂方法模式简化架构、让代码更抗变化的地方。

## 参考

- [原文：Factory Method Pattern Real-World Example in C#: Complete Implementation](https://www.devleader.ca/2026/03/31/factory-method-pattern-realworld-example-in-c-complete-implementation)
- [C# 接口的有效使用](https://www.devleader.ca/2023/09/11/oop-and-interfaces-in-c-how-to-use-them-effectively)
- [工厂模式示例（入门指南）](https://www.devleader.ca/2023/12/26/examples-of-the-factory-pattern-in-c-a-simple-beginners-guide)
- [开放/关闭原则（微软文档）](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles#openclosed)
- [Abstract Factory 设计模式完整指南](https://www.devleader.ca/2026/02/06/abstract-factory-design-pattern-in-c-complete-guide-with-examples)
