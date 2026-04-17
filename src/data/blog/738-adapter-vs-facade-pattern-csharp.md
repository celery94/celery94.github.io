---
pubDatetime: 2026-04-17T07:46:47+08:00
title: "C# 适配器模式 vs 外观模式：区别与选用指南"
description: "适配器模式和外观模式都是结构型设计模式，都涉及包装已有代码，但它们解决的是完全不同的问题。本文用 C# 代码示例逐一拆解两者的意图差异，并给出清晰的决策标准。"
tags: ["Design Patterns", "C#", "Structural Patterns"]
slug: "adapter-vs-facade-pattern-csharp"
ogImage: "../../assets/738/01-cover.png"
source: "https://www.devleader.ca/2026/04/15/adapter-vs-facade-pattern-in-c-key-differences-explained"
---

适配器（Adapter）和外观（Facade）都是结构型设计模式，都位于你的应用代码和外部代码之间。表面上看，两者都在"包装"别的类，但它们解决的问题完全不同。

用一句话直接点明：**适配器转换接口，外观简化子系统。** 搞清楚这一点，选型就不难了。

## 适配器模式：接口翻译

适配器的核心职责是让两个本不兼容的接口能够协作。你有一个客户端代码依赖的接口，你也有一个第三方类能做你想要的事，但它的方法签名、参数类型、返回值都和你的接口对不上。适配器就是中间的翻译层。

举个具体例子。你的应用依赖 `IPaymentProcessor` 接口，但你接入的是 Stripe，它暴露的是另一套 API：

```csharp
using System;

public interface IPaymentProcessor
{
    bool ProcessPayment(
        string customerId,
        decimal amount,
        string currency);
}

public sealed class StripeGateway
{
    public int CreateCharge(
        string accountRef,
        long amountInCents,
        string currencyCode,
        string description)
    {
        Console.WriteLine(
            $"Stripe charge: {amountInCents}" +
            $" {currencyCode} for {accountRef}");
        return 1;
    }
}
```

`IPaymentProcessor` 用 `decimal` 表示金额，`StripeGateway` 用 `long`（以分为单位）；方法名也不一样。适配器负责把这些差异一一抹平：

```csharp
using System;

public sealed class StripePaymentAdapter : IPaymentProcessor
{
    private readonly StripeGateway _stripe;

    public StripePaymentAdapter(StripeGateway stripe)
    {
        _stripe = stripe;
    }

    public bool ProcessPayment(
        string customerId,
        decimal amount,
        string currency)
    {
        long amountInCents = (long)(amount * 100);

        int chargeId = _stripe.CreateCharge(
            customerId,
            amountInCents,
            currency,
            $"Payment for customer {customerId}");

        return chargeId > 0;
    }
}
```

`StripePaymentAdapter` 实现了 `IPaymentProcessor`，把 `decimal` 转成 `long`，把 `ProcessPayment` 映射到 `CreateCharge`，把 `int` 结果转成 `bool`。客户端代码完全不需要知道底层是 Stripe——它只管调 `ProcessPayment`，拿到一个布尔值。

**适配器的关键特征**：只包装一个类，只负责转换，不添加功能，不简化逻辑。

## 外观模式：子系统简化

外观的核心职责是为复杂子系统提供一个统一的简化入口。不是"两个接口对不上"，而是"太多类需要按顺序协作，客户端没必要关心这些细节"。

同样用支付场景，但这次的复杂度来自多个子服务之间的协作：

```csharp
public sealed class OrderFacade
{
    private readonly InventoryService _inventory;
    private readonly PaymentService _payment;
    private readonly ShippingService _shipping;
    private readonly NotificationService _notification;

    public OrderFacade(
        InventoryService inventory,
        PaymentService payment,
        ShippingService shipping,
        NotificationService notification)
    {
        _inventory = inventory;
        _payment = payment;
        _shipping = shipping;
        _notification = notification;
    }

    public bool PlaceOrder(
        string customerId,
        string productId,
        int quantity,
        decimal totalPrice)
    {
        if (!_inventory.CheckStock(productId, quantity))
        {
            return false;
        }

        if (!_payment.ChargeCustomer(customerId, totalPrice))
        {
            return false;
        }

        _inventory.ReserveStock(productId, quantity);

        string tracking = _shipping.CreateShipment(
            customerId,
            productId,
            quantity);

        _notification.SendOrderConfirmation(
            customerId,
            tracking);

        return true;
    }
}
```

`OrderFacade` 把库存检查、收款、预留库存、创建发货单、发送通知全部封在一个 `PlaceOrder` 方法里。客户端调用一个方法，不需要知道内部的执行顺序或哪些服务参与其中。

**外观的关键特征**：协调多个类，定义一个全新的简化接口，管理工作流和调用顺序。

## 核心差异：意图

作者用了一个很直观的类比：

- **适配器**类似出国旅行时用的电源转换插头。你的笔记本是美国插头，欧洲插座的形状不同。转换器让两者能配合使用，电气系统本身没有变化，转换器只是让两个不兼容的形状能接上。

- **外观**类似酒店礼宾员。你想预订晚餐、叫出租车、买剧院门票，不需要分别打三个电话，告诉礼宾员你的需求，他在背后协调一切。

一个是"转换器"，一个是"调度员"，角色截然不同。

## 对比总结

| 维度 | 适配器 | 外观 |
|---|---|---|
| 首要意图 | 转换接口 | 简化子系统访问 |
| 作用范围 | 包装单个类 | 协调多个类 |
| 接口来源 | 实现已有的预期接口 | 定义全新的简化接口 |
| 包装对象数量 | 一个 | 多个 |
| 典型触发场景 | 接口不兼容 | 子系统太复杂 |
| 结构特征 | 类实现接口 A，包装类 B | 类包装服务 C、D、E、F |

## 同一场景，两种解法

### 适配器：让税务计算器适配

你的应用期望 `ITaxCalculator` 接口，但要接入的第三方税务引擎签名完全不同：

```csharp
public interface ITaxCalculator
{
    decimal CalculateTax(
        decimal subtotal,
        string stateCode);
}

public sealed class ThirdPartyTaxEngine
{
    public double ComputeSalesTax(
        double price,
        string jurisdiction,
        int taxYear)
    {
        Console.WriteLine(
            $"Computing tax for {jurisdiction}, " +
            $"year {taxYear}");
        return price * 0.08;
    }
}

public sealed class TaxEngineAdapter : ITaxCalculator
{
    private readonly ThirdPartyTaxEngine _engine;

    public TaxEngineAdapter(ThirdPartyTaxEngine engine)
    {
        _engine = engine;
    }

    public decimal CalculateTax(
        decimal subtotal,
        string stateCode)
    {
        double result = _engine.ComputeSalesTax(
            (double)subtotal,
            stateCode,
            DateTimeOffset.UtcNow.Year);

        return (decimal)result;
    }
}
```

适配器把 `decimal` 转成 `double`，把 `stateCode` 映射到 `jurisdiction`，还帮第三方 API 补上了 `taxYear` 参数（我们的接口不需要暴露这个细节）。进一个类，出一个类，纯粹翻译。

### 外观：简化结账流程

外观不是转换接口，而是把多个结账相关服务的调用封在一起：

```csharp
public sealed class CheckoutFacade
{
    private readonly ITaxCalculator _tax;
    private readonly IPaymentProcessor _payment;
    private readonly InventoryService _inventory;
    private readonly ShippingService _shipping;

    public CheckoutFacade(
        ITaxCalculator tax,
        IPaymentProcessor payment,
        InventoryService inventory,
        ShippingService shipping)
    {
        _tax = tax;
        _payment = payment;
        _inventory = inventory;
        _shipping = shipping;
    }

    public bool Checkout(
        string customerId,
        string productId,
        int quantity,
        decimal unitPrice,
        string stateCode)
    {
        decimal subtotal = unitPrice * quantity;
        decimal tax = _tax.CalculateTax(subtotal, stateCode);
        decimal total = subtotal + tax;

        if (!_inventory.CheckStock(productId, quantity))
        {
            return false;
        }

        if (!_payment.ProcessPayment(customerId, total, "USD"))
        {
            return false;
        }

        _inventory.ReserveStock(productId, quantity);
        _shipping.CreateShipment(customerId, productId, quantity);

        return true;
    }
}
```

外观协调了四个服务：税务计算、库存核查、支付、发货。客户端只需要调用 `Checkout`，不需要关心这些服务的调用顺序。

## 组合使用

两个模式并不互斥。在实际项目中，常见的组合方式是**在外观内部使用适配器**：适配器在边界处把第三方 API 规范化，外观在上层把多个服务的协作封装成简洁入口。

```csharp
// 适配器让第三方税务引擎符合 ITaxCalculator
var taxAdapter = new TaxEngineAdapter(
    new ThirdPartyTaxEngine());

// 适配器让 Stripe 符合 IPaymentProcessor
var paymentAdapter = new StripePaymentAdapter(
    new StripeGateway());

// 外观使用适配后的接口和原生服务
var checkout = new CheckoutFacade(
    taxAdapter,
    paymentAdapter,
    new InventoryService(),
    new ShippingService());

// 客户端只调这一个方法
checkout.Checkout(
    "cust-123",
    "prod-456",
    quantity: 2,
    unitPrice: 49.99m,
    stateCode: "WA");
```

外观不在乎它的依赖是适配器还是原生实现，它只面向接口工作。这种分层方式和依赖注入（DI）、控制反转（IoC）原则天然契合——每层都依赖抽象，而非具体实现。

## 如何选择

按顺序问自己几个问题：

1. **接入的是单个外部类，接口不匹配？** → 用适配器。问题是接口不兼容，适配器负责翻译。
2. **面对的是复杂子系统，客户端需要更简单的交互方式？** → 用外观。问题是复杂度，外观提供统一入口。
3. **两者都需要？** → 两者都用。在边界处用适配器规范化第三方接口，在上层用外观提供简洁 API。
4. **类已经兼容你的接口，只是需要加行为？** → 不是这两个，而是装饰器模式（Decorator）。
5. **需要在运行时切换可互换的算法？** → 不是这两个，而是策略模式（Strategy）。

## 常见错误

**用外观包装单个类**：如果你的"外观"只有一个依赖，它大概率是适配器。外观是为了协调多个组件，不是给单个类加一层包装。

**适配器变成垃圾桶**：适配器只负责翻译，不应该加入业务逻辑、重试机制、日志记录。这些横切关注点属于装饰器，业务逻辑属于领域层。保持适配器精简。

**外观变成上帝对象**：外观应该服务于一个有边界的子系统，不是整个应用的唯一入口。如果你的外观有十五个依赖和三十个方法，需要拆分——每个用例或功能领域一个聚焦的外观。

**忽视可测试性**：适配器应该让第三方代码可测试（通过接口 mock）；外观应该让复杂工作流可测试（把协调逻辑隔离出来）。如果适配器依赖具体类、外观不通过构造函数注入服务，可测试性的优势就丢失了。

## 总结

适配器和外观都站在你的应用代码和外部复杂性之间，但它们的工作层次不同：适配器在类级别做接口翻译，外观在子系统级别做工作流封装。

判断标准很简单：你面对的是"两个接口对不上"，还是"太多东西需要协调"？前者用适配器，后者用外观，两者都有时两者都用。

## 参考

- [Adapter vs Facade Pattern in C#: Key Differences Explained](https://www.devleader.ca/2026/04/15/adapter-vs-facade-pattern-in-c-key-differences-explained)
