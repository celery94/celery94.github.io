---
pubDatetime: 2026-11-04T08:41:31+08:00
title: "C# 多态：base 引用和接口引用调用谁"
description: "同一条调用语句，换成 base 引用或接口引用结果就变了。三个例子在 .NET 10 SDK 上实测，讲清 override、new 隐藏、显式接口实现的选成员与派发规则，以及编译器建议背后两种不同行为。"
tags: ["C#", ".NET", "Polymorphism"]
slug: "csharp-polymorphism-base-interface-dispatch"
ogImage: "../../assets/1134/01-cover.png"
source: "https://www.devleader.ca/2026/11/03/polymorphism-in-c-what-runs-through-base-and-interface-references"
---

`concrete` 和 `throughBase` 指向同一个对象，两行调用的输出一样。在派生类里把 `override` 改成 `new`，两行立刻分开：`hidden message` 和 `base message`。对象没换，调用语句也没换，变的是这个成员和基类成员之间的关系。

Dev Leader 的这篇文章把三类调用放在一起对照：`override` 走运行期派发，`new` 隐藏按编译期类型选，显式接口实现只认接口那一头。作者注明三段示例代码没有编译也没有运行，结论按文档推导。我在 .NET 10 SDK 10.0.402 上把它们跑了一遍，输出与原文一致；下面给实测结果，另外补了两个原文没做的实验。

## 调用只认点左边那个变量的类型

`throughBase.Render()` 这一行，编译器先看 `throughBase` 声明成什么类型，从它的成员表里挑出 `Render`，再看这个成员是不是虚方法。只有虚成员才需要第二个问题：运行期类型是谁。两件事分开看，前面那些「同一个对象结果不同」的场景就不再矛盾。

对象的身份从头到尾没变，三例里的 `ReferenceEquals` 都是 `True`。参考类型是同一个对象的一扇窗，换窗只换你能看到哪些成员。

## override 之后，基类引用也跑派生实现

```csharp
public class MessageRenderer
{
    public virtual string Render() => "message";
}

public sealed class DecoratedRenderer : MessageRenderer
{
    public override string Render() => $"[{base.Render()}]";
}

// Program.Main
var concrete = new DecoratedRenderer();
MessageRenderer throughBase = concrete;

Console.WriteLine(concrete.Render());
Console.WriteLine(throughBase.Render());
Console.WriteLine(ReferenceEquals(concrete, throughBase));
```

```text
[message]
[message]
True
```

基类引用没有强制基类实现。文档的原话是 CLR 在运行时查对象的类型，再调那个 override。`base.Render()` 是派生代码主动回头调基类，跟变量声明成什么类型无关；它在这里出现，是因为 override 的作者要复用基类产出的字符串。

## 把 override 换成 new，两行就分开了

```csharp
public class MessageRenderer
{
    public virtual string Render() => "base message";
}

public sealed class HiddenRenderer : MessageRenderer
{
    public new string Render() => "hidden message";
}

// Program.Main
var concrete = new HiddenRenderer();
MessageRenderer throughBase = concrete;

Console.WriteLine(concrete.Render());
Console.WriteLine(throughBase.Render());
Console.WriteLine(ReferenceEquals(concrete, throughBase));
```

```text
hidden message
base message
True
```

文档对隐藏的表述很直接：方法选哪个取决于变量的编译期类型，跟对象的运行期类型无关。两个变量仍然指向同一个对象，差别来自成员表和「有没有 override」这两件事。

把 `new` 删掉再跑，输出还是这两行，只多一条警告：

```text
warning CS0114: 'HiddenRenderer.Render()' hides inherited member 'MessageRenderer.Render()'.
```

编译器的建议是「加 override，或者加 new」。这两个建议指向两种行为，实测差别不小：换成 `override` 之后，第二行变成 `hidden message`，两行一致；保持 `new`，第二行始终是 `base message`。`new` 的作用是承认这里有个独立成员，它没有把关系改成覆写。

## 选成员发生在派发之前

原文讲重载时只给了结论，没给例子。补一个实测的：

```csharp
public class Base
{
    public virtual string Describe(object value) => "base-object";
}

public sealed class Derived : Base
{
    public override string Describe(object value) => "override-object";
    public string Describe(string value) => "derived-string";
}

// Program.Main
Base throughBase = new Derived();
Derived concrete = new Derived();

Console.WriteLine(throughBase.Describe("x"));  // override-object
Console.WriteLine(concrete.Describe("x"));     // derived-string
```

同一个对象，同一个实参 `"x"`，输出不同。走 base 引用时，基类只提供 `Describe(object)`，选中虚成员，运行期跑 override。走派生引用时，`string` 到 `string` 的转换比到 `object` 更近，编译器先选中那个非虚的 `Describe(string)`，虚方法根本没参与。

看一个可疑调用时，分别写清参考类型、实参类型和候选成员，再问谁提供实现。成员选错了，后面的派发规则再背也没用。

## 显式接口实现只能从接口那头进

```csharp
public sealed class ReservationSummary : IDisplayText, IAuditText
{
    public string Describe() => "Reservation summary";

    string IDisplayText.GetText() => "Your reservation is confirmed.";
    string IAuditText.GetText() => "reservation:confirmed";
}
```

```text
Reservation summary
Your reservation is confirmed.
reservation:confirmed
```

两个接口签名相同，各给一份实现。类上没有公开的 `GetText`，直接写 `summary.GetText()` 编译不过：

```text
error CS1061: 'ReservationSummary' does not contain a definition for 'GetText'
and no accessible extension method 'GetText' accepting a first argument of type
'ReservationSummary' could be found.
```

这条错误信息容易让人以为是少了 using 或者访问修饰符，其实是这个成员本来就不在类的公开面上。显式实现的代价也在这里：调用方必须拿到接口引用。如果这个操作本来就属于类的正常 API，写成公开方法更好找。

## 默认实现和静态抽象成员走另一套规则

原文提到现代接口不再只是空声明，这部分补两个实测。

默认接口成员只能通过接口引用访问。写一个空实现类，`asInterface.Greet()` 能跑，`greeter.Greet()` 编译报 CS1061，跟显式实现是同一个表现。

```csharp
public interface IGreeter
{
    string Greet() => "default implementation";
}

public sealed class Greeter : IGreeter { }
```

静态抽象成员离实例派发更远。接口里声明 `static abstract string Name()`，`Circle` 实现成返回 `circle`；调用方写 `GetName<T>() where T : IShape`，方法体里直接用 `T.Name()`，`GetName<Circle>()` 的结果是 `circle`。这类成员由类型实参在编译期确定，不进实例的虚方法表。

这两个机制都不该混进「base 引用跑派生实现」的解释里。原文在这一点上说得克制，我同意。

## 跑对了方法，也不代表行为对

派发只回答「哪段代码运行」。它不保证这段代码满足调用方的期待：`Render()` 返回了字符串，格式却可能不符合下游解析；接口实现编译通过，语义可能违反契约。

想在契约层面推理，去看 LSP 和接口设计那类材料，别继续研究派发表。原文把两者分开，界线划得对。

## 排查顺序：先写四样东西

点左边变量的声明类型、实参类型、被选中的成员、这个成员是否 virtual 且被 override。四样写全，绝大多数「为什么跑了那个方法」就有答案了。

| 写法              | 选成员依据         | 谁提供实现                |
| ----------------- | ------------------ | ------------------------- |
| 虚成员被 override | 参考类型找到成员   | 对象运行期类型的 override |
| `new` 隐藏成员    | 参考类型           | 参考类型自己的成员        |
| 显式接口实现      | 接口引用           | 该接口对应的实现          |
| 静态抽象成员      | 类型实参（编译期） | 类型实参指定的实现        |

审 PR 时看到 `new`，值得问一句它是不是有意隐藏；看到 `override` 里调 `base`，确认基类行为是必需的，而不是习惯性补上。反过来，如果你想靠切换引用类型来「调用基类实现」，那条路不存在，只有 `base` 关键字能进去。

## 参考

- [Polymorphism in C#: What Runs Through Base and Interface References?](https://www.devleader.ca/2026/11/03/polymorphism-in-c-what-runs-through-base-and-interface-references)
- [Polymorphism - C#](https://learn.microsoft.com/dotnet/csharp/fundamentals/object-oriented/polymorphism)
- [Explicit interface implementation](https://learn.microsoft.com/dotnet/csharp/programming-guide/interfaces/explicit-interface-implementation)
- [Interfaces - C#](https://learn.microsoft.com/dotnet/csharp/fundamentals/types/interfaces)
- [new modifier](https://learn.microsoft.com/dotnet/csharp/language-reference/keywords/new-modifier)
