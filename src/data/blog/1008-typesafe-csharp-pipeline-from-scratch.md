---
pubDatetime: 2026-08-19T08:25:00+08:00
title: "从零构建类型安全的 C# 管道"
description: "从零实现一个类型安全的 C# 同步管道：IStage 泛型契约、Pipeline 两段组合、编译期类型检查、不可变消息与异常传播，附完整代码、执行顺序分析和常见陷阱。"
tags: [".NET", "C#", "Architecture", "Pipeline"]
slug: "typesafe-csharp-pipeline-from-scratch"
ogImage: "../../assets/1008/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/18/build-a-typesafe-c-pipeline-from-scratch"
---

Dev Leader 的 Nick Cosentino 在 2026 年 8 月发布了一篇《Build a Type-Safe C# Pipeline From Scratch》，用一份不依赖任何 NuGet 包的代码，演示了怎么用 C# 泛型写出「连接错了就编不过」的管道。这篇文章把它整理成一篇可以照着做的中文教程。

要解决的问题：很多管道示例每一级都是 `string -> string`，拼起来容易，但真实的处理流程通常会改变数据形态——文本变成对象、对象经过校验、校验后的对象再汇总成结果。如果中间都用 `object` 传递，编译器就帮不上忙，错误要等到运行时强转失败才发现。

读完这篇，你会得到：一个可直接运行的 `IStage<TInput, TOutput>` 契约、一个两段式的 `Pipeline<TInput, TIntermediate, TOutput>` 组合类，以及一份完整的订单解析 → 校验 → 汇总示例，最后还会梳理执行顺序、不可变消息和常见「丢类型安全」的写法。

## 前置条件

- **.NET 10 SDK**（.NET 10 于 2025 年 11 月发布，是当前 LTS 版本）
- **C# 14**（随 .NET 10 一起提供）
- 启用 nullable reference types（`#nullable enable`）
- 不需要任何 NuGet 包

本文的管道是刻意保持小型的同步实现：没有 async、没有取消令牌、没有依赖注入容器、没有队列、没有 TPL Dataflow，也不做性能调优。先理解「类型安全组合」这件事本身，再决定要不要引入更重的机制。

## 管道要解决的类型问题

假设一条订单处理流水线：

```text
OrderText -> ParsedOrder -> ValidatedOrder -> OrderSummary
```

解析器只懂文本；校验器只懂解析出来的字段；汇总器只接受已经通过校验的订单。每个边界携带的语义都不一样——不只是换了个变量名。

要做到这一点，契约可以定义得非常小：

```csharp
IStage<TInput, TOutput>
```

一个实现接收 `TInput`、返回 `TOutput`。组合两段时，需要一个额外的类型参数来表示跨过边界的值：

```text
TInput -> TIntermediate -> TOutput
```

第一个参数必须可赋值给 `IStage<TInput, TIntermediate>`，第二个参数必须可赋值给 `IStage<TIntermediate, TOutput>`。边界保住了，合法的泛型接口变体（variance）转换也仍然被允许。

## 完整实现

下面是整份示例代码，可以放在一个文件里运行。它包含接口、组合类、四个消息记录（record）和三个处理阶段。

```csharp
#nullable enable

using System.Globalization;

namespace DevLeader.TypeSafePipeline;

public interface IStage<in TInput, out TOutput>
{
    TOutput Execute(TInput input);
}

public sealed class Pipeline<TInput, TIntermediate, TOutput>
    : IStage<TInput, TOutput>
{
    private readonly IStage<TInput, TIntermediate> _first;
    private readonly IStage<TIntermediate, TOutput> _second;

    public Pipeline(
        IStage<TInput, TIntermediate> first,
        IStage<TIntermediate, TOutput> second)
    {
        _first = first;
        _second = second;
    }

    public TOutput Execute(TInput input)
    {
        var intermediate = _first.Execute(input);

        return _second.Execute(intermediate);
    }
}

public sealed record OrderText(string Value);

public sealed record ParsedOrder(
    string OrderId,
    string CustomerId,
    decimal Subtotal,
    int ItemCount);

public sealed record ValidatedOrder(
    string OrderId,
    string CustomerId,
    decimal Subtotal,
    int ItemCount);

public sealed record OrderSummary(
    string OrderId,
    string CustomerId,
    decimal Subtotal,
    decimal Tax,
    decimal Total,
    int ItemCount);

public sealed class ParseOrderStage
    : IStage<OrderText, ParsedOrder>
{
    public ParsedOrder Execute(OrderText input)
    {
        ArgumentNullException.ThrowIfNull(input);

        var parts = input.Value.Split(
            '|',
            StringSplitOptions.TrimEntries);

        if (parts.Length != 4)
        {
            throw new FormatException(
                "Expected orderId|customerId|subtotal|itemCount.");
        }

        if (!decimal.TryParse(
                parts[2],
                NumberStyles.Number,
                CultureInfo.InvariantCulture,
                out var subtotal))
        {
            throw new FormatException("Subtotal is not a valid decimal.");
        }

        if (!int.TryParse(
                parts[3],
                NumberStyles.Integer,
                CultureInfo.InvariantCulture,
                out var itemCount))
        {
            throw new FormatException("Item count is not a valid integer.");
        }

        return new ParsedOrder(
            parts[0],
            parts[1],
            subtotal,
            itemCount);
    }
}

public sealed class ValidateOrderStage
    : IStage<ParsedOrder, ValidatedOrder>
{
    public ValidatedOrder Execute(ParsedOrder input)
    {
        ArgumentNullException.ThrowIfNull(input);

        if (string.IsNullOrWhiteSpace(input.OrderId))
        {
            throw new ArgumentException(
                "Order ID is required.",
                nameof(input));
        }

        if (string.IsNullOrWhiteSpace(input.CustomerId))
        {
            throw new ArgumentException(
                "Customer ID is required.",
                nameof(input));
        }

        if (input.Subtotal < 0m)
        {
            throw new ArgumentOutOfRangeException(
                nameof(input),
                "Subtotal cannot be negative.");
        }

        if (input.ItemCount <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(input),
                "Item count must be positive.");
        }

        return new ValidatedOrder(
            input.OrderId,
            input.CustomerId,
            input.Subtotal,
            input.ItemCount);
    }
}

public sealed class SummarizeOrderStage
    : IStage<ValidatedOrder, OrderSummary>
{
    private const decimal TaxRate = 0.13m;

    public OrderSummary Execute(ValidatedOrder input)
    {
        ArgumentNullException.ThrowIfNull(input);

        var tax = decimal.Round(
            input.Subtotal * TaxRate,
            2,
            MidpointRounding.AwayFromZero);

        return new OrderSummary(
            input.OrderId,
            input.CustomerId,
            input.Subtotal,
            tax,
            input.Subtotal + tax,
            input.ItemCount);
    }
}

public sealed class OrderPipelineExample
{
    private readonly IStage<OrderText, OrderSummary> _pipeline;

    public OrderPipelineExample()
    {
        var parseThenValidate =
            new Pipeline<OrderText, ParsedOrder, ValidatedOrder>(
                new ParseOrderStage(),
                new ValidateOrderStage());

        _pipeline =
            new Pipeline<OrderText, ValidatedOrder, OrderSummary>(
                parseThenValidate,
                new SummarizeOrderStage());
    }

    public OrderSummary Run(string orderText)
    {
        return _pipeline.Execute(new OrderText(orderText));
    }
}
```

运行方式：创建 `OrderPipelineExample`，调用 `Run` 传入类似 `ORD-001|CUST-42|100.00|3` 的文本，得到 `OrderSummary`（含 `Subtotal`、按 13% 计算的 `Tax` 和 `Total`）。

## 逐块拆解：三个关键设计

**1. 契约只声明一次转换。** `IStage<in TInput, out TOutput>` 用 `in` 标记被消费的输入、用 `out` 标记被返回的输出，这是 C# 允许的泛型接口变体标注。变体是灵活性，但真正的组合保证来自相邻的泛型类型。

**2. 组合类恰好装两个阶段。** `Pipeline<TInput, TIntermediate, TOutput>` 自己也是一个 `IStage<TInput, TOutput>`，`Execute` 里先调 `_first`、把中间值存下来、再传给 `_second`。

**3. 嵌套组合构建长管道。** 上面的例子用两个 `Pipeline` 实例拼出三个阶段：`parseThenValidate` 本身是 `IStage<OrderText, ValidatedOrder>`，它可以作为外层管道的第一段，第二段接 `SummarizeOrderStage`。嵌套的结果还是一个合法的 stage，调用方只需要面对 `IStage<OrderText, OrderSummary>` 这一个契约，不需要知道内部有几段。

## 类型安全到底怎么起作用

看第一段组合：

```csharp
Pipeline<OrderText, ParsedOrder, ValidatedOrder>
```

编译器会生成两条赋值要求：

1. 第一个参数可赋值给 `IStage<OrderText, ParsedOrder>`；
2. 第二个参数可赋值给 `IStage<ParsedOrder, ValidatedOrder>`。

现在故意把解析器和校验器调换：

```csharp
new Pipeline<OrderText, ParsedOrder, ValidatedOrder>(
    new ValidateOrderStage(),
    new ParseOrderStage())
```

在原文的 `net10.0` + C# 14 验证环境里，这段代码编译失败：`ValidateOrderStage` 不可赋值给 `IStage<OrderText, ParsedOrder>`，`ParseOrderStage` 不可赋值给 `IStage<ParsedOrder, ValidatedOrder>`。错误在**组装管道的那个位置**就暴露了，而不是等生产数据流到错误的阶段才炸。

这就是类型安全管道的实际价值：代码把路线写进类型，编译器负责强制执行。

## 为什么不用 object 契约

`IStage<object, object>` 什么都能装，但代价是把正确性推给强转和运行时检查：

```text
object -> cast -> object -> cast -> object
```

编译器无法判断下一段要的是解析后的订单、校验后的订单还是完全不相关的客户记录。失败的强转变成运行时问题；漏掉一个阶段也可能看不出来，因为所有连接的名义类型都一样。泛型在每个边界保留真实的表示类型，这正是泛型对比运行时强转的核心优势之一。

序列化边界、插件边界确实可能用统一信封，但即使如此，信封里也通常应该放带判别式的契约、schema 标识或类型化的 payload 访问，而不是把任意 `object` 当成进程内阶段 API 的常态。

## 执行顺序是组合的一部分

`Pipeline` 先调 `_first.Execute` 再调 `_second.Execute`，没有事件、订阅者集合或无序注册表——顺序是结构性的，由构造函数参数和嵌套泛型类型表达。想把校验挪到解析之前，你需要一组能让那个转换成立的类型；当前契约正确地阻止了这件事。

这和用多播委托拼结果管道不同：C# 多播委托可以持有多个方法、按序调用，但只返回调用列表中最后一个方法的返回值，而且整个调用列表必须共享同一个签名。这对「前一个返回值变成后一个输入」的异构转换是很差的组合模型。本文用的是通过类型化接口的普通方法调用，每个中间结果都被显式捕获并传递。

## 不可变消息与独占所有权

示例用 sealed 位置记录（positional record）作为消息契约：属性默认 init-only，构造后不能重新赋值；每个阶段返回新表示，而不是改传入的对象。收益是：

- 阶段不能悄悄改动更早阶段还在引用的数据；
- 每次转换清楚显示哪些值被保留、删除或新增；
- 失败的阶段不会留下改了一半的消息；
- 测试可以整体比较值，不用窥探私有可变状态。

注意 record 只提供浅层不可变：如果里面放一个 `List<string>`，调用方仍然可以改这个列表。所以管道消息要二选一：像本示例一样只用不可变成员，或者把可变对象的独占所有权交给某一个阶段、不在别处共享。避免多个阶段同时持有并修改同一个集合的模糊中间态。

## 终点结果是一个真实类型

`OrderSummary` 是这条管道的终点表示，不在管道内部被打印，也不藏在共享 context 字典里。`OrderPipelineExample.Run` 直接把它返回给调用方——控制台可以格式化、Web 端点可以序列化、测试可以比较、持久化适配器可以存储，都不需要改动三个转换阶段。

另外，阶段类型也防止了「不小心跳过校验」：`SummarizeOrderStage` 接受 `ValidatedOrder` 而不是 `ParsedOrder`，调用方没法把解析器的输出直接喂给汇总器，除非写显式转换或改契约。

## 失败传播基线

本实现不构建 result 类型，也没有恢复策略：畸形输入和非法值直接抛异常。如果某个阶段抛异常，`Pipeline.Execute` 不捕获，下一段不会执行，异常一路传到调用方。没有默认值传给下一段，也没有构造到一半的 `OrderSummary`。生产设计应该决定「预期拒绝」是否放进类型化结果、哪些失败算异常，但那是独立于「证明异构组合可行」的另一个话题。

## 扩展：加一个阶段

加阶段 = 定义一个新的输入到输出契约，并在兼容边界组合它。比如未来要把 `OrderSummary` 变成 `InvoiceDocument`：

```csharp
Pipeline<OrderText, OrderSummary, InvoiceDocument>
```

已有管道已经实现了 `IStage<OrderText, OrderSummary>`，可以直接和 `IStage<OrderSummary, InvoiceDocument>` 组合。不需要新基类，不需要给中央 switch 加分支，编译器仍然会验证新边界。

代价是：阶段越多，嵌套泛型越啰嗦。这种啰嗦本身就是类型路径的证据，但在超大组合里会伤可读性。精心设计的 builder 可以藏起部分嵌套、同时保留编译期转换——但如果 builder 把阶段存成 `object`，那只是把类型检查挪出了视线。

## 怎么读嵌套组合

把 `Pipeline<OrderText, ParsedOrder, ValidatedOrder>` 从左往右读成一句话：「接受 `OrderText`，跨过 `ParsedOrder` 边界，返回 `ValidatedOrder`」。构造函数参数必须提供让这句话成立的两个阶段契约。

再看外层 `Pipeline<OrderText, ValidatedOrder, OrderSummary>`：第一段已经知道怎么把 `OrderText` 变成 `ValidatedOrder`（内部有两段也没关系），第二段把 `ValidatedOrder` 变成 `OrderSummary`。外层管道看到的是一个兼容的 `IStage<OrderText, ValidatedOrder>`。

给中间组合按含义命名，而不是按机制命名：`parseThenValidate` 比 `pipeline1` 传达的信息多。如果一条路线难命名，它可能塞了太多职责，或者跨过了值得单独抽象出来的领域边界。

## 常见的「丢类型安全」写法

1. **`List<object>` 存异构阶段。** 看起来可配置，但每次执行都要在运行时重新发现输入输出类型，反射、强转或 dynamic 调用取代了泛型保证。
2. **可变的万能 context。** 一个阶段写 `"ParsedOrder"` 键、另一个阶段读它，一个拼写错误就是运行时缺陷。context 可以承载共享元数据，但不应取代沿路线流动的主类型值。
3. **每段都返回同一个宽基类。** 当所有表示真的共享一个稳定契约时有用；当每段都要立刻把基类强转回具体子类型时就有害。
4. **只在 `Build()` / `Execute()` 时校验兼容性的 builder。** 流式 API 只有在每个方法把当前输出类型带进下一步选择时才有帮助。藏起泛型嵌套是合理的，抹掉泛型关系不是。

判断标准很简单：连接两个不兼容的阶段时，编译器会不会在那一行拒绝？如果不会，这个抽象就没提供类型安全管道该有的主要收益。

## 什么时候这个实现是合适的尺寸

适合用这种类型安全管道的情况：

- 阶段是同步的、进程内的；
- 每个条目走一条线性的、有依赖的路线；
- 阶段之间表示类型会变化；
- 编译期组合比运行时重配置更有价值；
- 几个显式的阶段对象比一个框架更清楚。

别把它硬撑成任务调度器：它没有缓冲、背压、取消、并行 worker、持久化状态或生命周期协调——对这些场景来说，缺失恰恰是特性。反过来，如果整个操作只是某个内聚类里两个显而易见的私有方法调用，这个抽象可能也不必要：管道模式在「命名阶段和契约能厘清职责」时有用，在「类型给本来直接可读的逻辑套上仪式」时就没用。

## 常见问题

**为什么不把所有阶段都做成同一个消息类型？** 当每个阶段真的消费和产出同一种表示时可以。异构类型在含义变化时更好：`ParsedOrder` 和 `ValidatedOrder` 即使部分属性相同，传达的保证也不同。

**为什么用接口而不是 `Func`？** 命名接口给阶段一个稳定的语义契约，每个实现可以有描述性类型名。C# 委托是类型安全的方法引用，适合轻量的单阶段；接口方案避免了用多播委托组合中间结果，也让完整示例保持显式。

**`Pipeline` 类支持任意数量的阶段吗？** 它一次组合两个，但结果也实现 `IStage<TInput, TOutput>`，所以可以嵌套成更长的管道。示例就是两个 `Pipeline` 实例拼出三个阶段。

**record 是深层不可变的吗？** 不是。位置属性是 init-only，但被引用的可变对象仍然能变。用不可变成员，或对可变值建立独占所有权。

**校验失败会怎样？** 校验阶段抛异常，组合停止，汇总阶段不被调用，异常到达调用方。这是基线传播规则，不是完整的生产失败模型。

**能并行跑阶段吗？** 这个实现不行：每个阶段都需要前一段的输出，解析必须产出校验要消费的值，校验必须产出汇总要消费的值。它是有意保持同步和顺序的。

## 小结

一个有用的类型安全管道不需要包，也不需要复杂的 builder，需要的是诚实的契约：`IStage<TInput, TOutput>` 定义一次转换，`Pipeline<TInput, TIntermediate, TOutput>` 组合两个兼容的转换，嵌套组合在不抹掉类型的前提下搭出更长路线，不可变消息让状态变化可见，最终结果通过显式的终点类型离开管道。

建议的下一步：把上面的代码复制进一个 `net10.0` 控制台项目跑通，然后故意调换一次阶段顺序，观察编译错误出现在哪一行；再试着自己加一个 `InvoiceDocument` 阶段，感受「改契约就能让编译器帮你把关」的过程。等需求真正需要 async、取消或背压时，再在保留这条类型边界的思路下去扩展。

Aide Hub 持续分享 AI 助手、开发工具与软件工程实践。如果你也在折腾 C# 管道、责任链或类似的分阶段处理设计，欢迎分享你的组合写法。

## 参考

- [Build a Type-Safe C# Pipeline From Scratch（原文，Nick Cosentino）](https://www.devleader.ca/2026/08/18/build-a-typesafe-c-pipeline-from-scratch)
- [Generic types and methods（C# 泛型）| Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/types/generics)
- [Variance in generic interfaces（泛型接口变体）| Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/concepts/covariance-contravariance/variance-in-generic-interfaces)
- [Records documentation（记录类型）| Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/types/records)
- [Using delegates（委托）| Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/delegates/using-delegates)
- [.NET support policy（.NET 10 支持基线）| Microsoft](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)
- [C# language versioning | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/language-versioning)
