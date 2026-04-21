---
pubDatetime: 2026-04-21T15:11:41+08:00
title: ".NET 中的解释器模式：把业务规则变成可组合的表达式"
description: "解释器模式（Interpreter Pattern）能把硬编码的 if-else 业务规则拆解成可组合、可配置的表达式树。本文用折扣规则引擎为例，演示如何在 .NET 中用终止表达式、逻辑组合器和配置解析器，让规则引擎摆脱重新部署的束缚。"
tags: ["Design Patterns", ".NET", "C#", "Architecture"]
slug: "interpreter-pattern-in-dotnet"
ogImage: "../../assets/745/01-cover.png"
source: "https://thecodeman.net/posts/interpreter-pattern-in-dotnet"
---

折扣引擎最初很简单：订单满 $100 打九折。一个条件，一条规则。

后来市场部要求加上：VIP 客户且订单超过 $200 时打八折。再后来：购物车里有"电子产品"或订单超过 $500 时包邮。再后来：活跃 2 年以上且本月没用过优惠券的老客户享受 5% 忠诚优惠。

一年后，那个折扣方法变成了 150 行嵌套条件，没人愿意碰它：

```csharp
public decimal CalculateDiscount(Order order, Customer customer)
{
    if (customer.IsVip && order.Total > 200)
        return order.Total * 0.20m;
    else if (order.Total > 100)
        return order.Total * 0.10m;
    else if (order.Items.Any(i => i.Category == "Electronics") || order.Total > 500)
        return 0; // Free shipping instead
    else if (customer.ActiveYears >= 2 && !customer.UsedCouponThisMonth)
        return order.Total * 0.05m;
    // 20 more conditions...
    return 0;
}
```

每条新规则都要改代码、重新部署、跑一遍全量测试。市场部改个规则，开发团队就要走一次发布流程，而且没人能一眼读懂完整的规则集合。

## 真正的症结

这些规则本质上是**业务逻辑**，它变化频繁，但被锁进了编译好的代码里。你需要一种方式把规则表示成**数据**——可以被解析、组合、在运行时动态求值。

## 解释器模式是什么

解释器模式为某种语言定义一套文法，并提供一个解释器来对该语言中的表达式求值。文法中的每条规则变成一个类，复杂规则由简单规则组合而来。

核心结构分两类：

- **终止表达式（Terminal Expression）**：直接映射一个原子条件，比如"订单金额 > 阈值"
- **非终止表达式（Non-terminal Expression）**：逻辑组合器，AND / OR / NOT，负责把原子条件拼装成复合规则

## 在 .NET 中实现

先定义上下文和表达式接口：

```csharp
// Context 持有表达式求值所需的数据
public class RuleContext
{
    public Order Order { get; init; } = null!;
    public Customer Customer { get; init; } = null!;
}

// 抽象表达式接口
public interface IExpression
{
    bool Interpret(RuleContext context);
}
```

接下来是四个终止表达式，每个对应一个原子条件：

```csharp
// 订单总额 > 阈值
public class OrderTotalGreaterThan : IExpression
{
    private readonly decimal _threshold;
    public OrderTotalGreaterThan(decimal threshold) => _threshold = threshold;
    public bool Interpret(RuleContext context)
        => context.Order.Total > _threshold;
}

// 客户是否 VIP
public class CustomerIsVip : IExpression
{
    public bool Interpret(RuleContext context)
        => context.Customer.IsVip;
}

// 客户活跃年限 >= 最小年数
public class CustomerActiveYears : IExpression
{
    private readonly int _minYears;
    public CustomerActiveYears(int minYears) => _minYears = minYears;
    public bool Interpret(RuleContext context)
        => context.Customer.ActiveYears >= _minYears;
}

// 订单包含指定品类
public class OrderContainsCategory : IExpression
{
    private readonly string _category;
    public OrderContainsCategory(string category) => _category = category;
    public bool Interpret(RuleContext context)
        => context.Order.Items.Any(i =>
            i.Category.Equals(_category, StringComparison.OrdinalIgnoreCase));
}
```

然后是三个逻辑组合器（非终止表达式）：

```csharp
// AND：两个表达式同时为真
public class AndExpression : IExpression
{
    private readonly IExpression _left;
    private readonly IExpression _right;

    public AndExpression(IExpression left, IExpression right)
    {
        _left = left;
        _right = right;
    }

    public bool Interpret(RuleContext context)
        => _left.Interpret(context) && _right.Interpret(context);
}

// OR：任意一个表达式为真
public class OrExpression : IExpression
{
    private readonly IExpression _left;
    private readonly IExpression _right;

    public OrExpression(IExpression left, IExpression right)
    {
        _left = left;
        _right = right;
    }

    public bool Interpret(RuleContext context)
        => _left.Interpret(context) || _right.Interpret(context);
}

// NOT：对表达式取反
public class NotExpression : IExpression
{
    private readonly IExpression _expression;
    public NotExpression(IExpression expression) => _expression = expression;
    public bool Interpret(RuleContext context)
        => !_expression.Interpret(context);
}
```

有了这些积木，组合规则变得非常直观：

```csharp
// 规则 1：VIP 客户 AND 订单超过 $200
var vipHighValueRule = new AndExpression(
    new CustomerIsVip(),
    new OrderTotalGreaterThan(200));

// 规则 2：购物车有电子产品 OR 订单超过 $500（包邮）
var freeShippingRule = new OrExpression(
    new OrderContainsCategory("Electronics"),
    new OrderTotalGreaterThan(500));

// 规则 3：活跃 2 年以上 AND 不是 VIP（老客户但还没升级）
var loyaltyRule = new AndExpression(
    new CustomerActiveYears(2),
    new NotExpression(new CustomerIsVip()));

// 求值
var context = new RuleContext { Order = order, Customer = customer };

if (vipHighValueRule.Interpret(context))
    discount = 0.20m;
else if (loyaltyRule.Interpret(context))
    discount = 0.05m;
```

规则是可组合的数据结构，可以存储、序列化，也可以从配置文件构建。

## 为什么这样更好

**规则是数据，不是代码**。可以把规则定义存在数据库里，在运行时构建表达式树，加新规则不需要重新发布。

**可组合**。AND、OR、NOT 可以随意组合任意表达式。复杂规则从经过单独测试的简单组件拼接而来。

**可测试**。每个表达式就是一个类、一个方法。`OrderTotalGreaterThan` 可以完全独立于其他表达式测试。

## 进阶：从配置构建规则树

更进一步，可以从 JSON 或数据库配置里解析规则：

```csharp
public class RuleEngine
{
    public IExpression BuildFromConfig(RuleDefinition definition)
    {
        return definition.Type switch
        {
            "OrderTotalGreaterThan" =>
                new OrderTotalGreaterThan(definition.GetParam<decimal>("threshold")),
            "CustomerIsVip" =>
                new CustomerIsVip(),
            "CustomerActiveYears" =>
                new CustomerActiveYears(definition.GetParam<int>("years")),
            "OrderContainsCategory" =>
                new OrderContainsCategory(definition.GetParam<string>("category")),
            "AND" =>
                new AndExpression(
                    BuildFromConfig(definition.Left!),
                    BuildFromConfig(definition.Right!)),
            "OR" =>
                new OrExpression(
                    BuildFromConfig(definition.Left!),
                    BuildFromConfig(definition.Right!)),
            "NOT" =>
                new NotExpression(BuildFromConfig(definition.Left!)),
            _ => throw new InvalidOperationException($"Unknown rule type: {definition.Type}")
        };
    }
}

// JSON 规则定义示例
// {
//   "type": "AND",
//   "left": { "type": "CustomerIsVip" },
//   "right": { "type": "OrderTotalGreaterThan", "params": { "threshold": 200 } }
// }
```

这样，市场部可以在管理后台直接定义规则，规则引擎解析后求值，完全不需要改代码。

## 进阶：数值表达式求值器

同样的机制也能用于数值计算，比如动态计算价格字段：

```csharp
public interface IMathExpression
{
    decimal Evaluate(Dictionary<string, decimal> variables);
}

public class NumberLiteral : IMathExpression
{
    private readonly decimal _value;
    public NumberLiteral(decimal value) => _value = value;
    public decimal Evaluate(Dictionary<string, decimal> variables) => _value;
}

public class Variable : IMathExpression
{
    private readonly string _name;
    public Variable(string name) => _name = name;
    public decimal Evaluate(Dictionary<string, decimal> variables) => variables[_name];
}

public class Multiply : IMathExpression
{
    private readonly IMathExpression _left, _right;
    public Multiply(IMathExpression left, IMathExpression right)
    { _left = left; _right = right; }
    public decimal Evaluate(Dictionary<string, decimal> variables)
        => _left.Evaluate(variables) * _right.Evaluate(variables);
}

// 表达式：price * quantity * (1 - discountRate)
var totalExpr = new Multiply(
    new Multiply(new Variable("price"), new Variable("quantity")),
    new Subtract(new NumberLiteral(1), new Variable("discountRate")));

var vars = new Dictionary<string, decimal>
{
    ["price"] = 29.99m, ["quantity"] = 3, ["discountRate"] = 0.10m
};

var total = totalExpr.Evaluate(vars); // 80.973
```

## 不适合使用的场景

原文给出了三个明确的反例：

**文法复杂时不要用**。如果你的语言有循环、函数或复杂语法，请用专业的解析器生成器（ANTLR）或现有的脚本引擎（Roslyn、Lua）。解释器模式扩展性不够，不适合复杂语言。

**性能敏感路径不要用**。每次 `Interpret()` 调用都会遍历整个表达式树。如果是高频路径，每秒要跑百万次评估，用编译后的表达式（`Expression<T>.Compile()`）会快几个数量级。

**规则几乎不变时不要用**。如果规则一年才改一次，搭建一套解释器的成本远大于收益，直接写条件判断反而更清晰。

## 要点总结

- 解释器模式把文法规则映射成类，让业务规则可组合、可动态配置
- AND、OR、NOT 组合器可以从简单原子条件构建出任意复杂的规则
- 规则可以存储在数据库里，在运行时从配置构建
- 适合：规则引擎、折扣计算器、简单 DSL
- 不适合：复杂语言文法、性能敏感的求值路径

## 参考

- [Interpreter Pattern in .NET - TheCodeMan](https://thecodeman.net/posts/interpreter-pattern-in-dotnet)
