---
pubDatetime: 2026-04-07T15:54:00+08:00
title: ".NET 中不变性（Immutability）的价值"
description: "不可变对象一旦创建就无法修改，这看起来是个限制，实则是一种设计力量。本文从数据完整性、线程安全、可预测性等角度，结合 C# 代码示例，解释为什么现代 .NET 开发应将不可变作为默认选项，以及如何用 record、Builder 模式和 with 表达式实现它。"
tags: ["dotnet", "C#", "Immutability"]
slug: "value-of-immutability-in-dotnet"
ogImage: "../../assets/718/01-cover.jpg"
source: "https://barretblake.dev/posts/development/2026/03/value-of-immutability"
---

不可变性（Immutability）：状态一旦确定，便不可更改。

程序员在刚接触这个概念时，往往会觉得它是一种麻烦——如果对象不能修改，那每次需要改数据岂不是要创建新对象？但只要经历过一次"数据在某个不知道的地方被某段不知道的代码改掉"所导致的 bug，多半会改变这个看法。

Barret Blake 最近写了一篇文章，系统梳理了不可变对象在 .NET 中的价值、常见反对意见，以及实际使用时的模式和陷阱。本文根据原文整理。

![不可变性封面图](../../assets/718/01-cover.jpg)

## 什么是不可变对象

代码里的不可变对象，指的是一旦创建就不能修改其字段或属性的对象。在 C# 里有几种写法：

**用 `init` 访问器**：属性只能在构造时赋值，之后无法更改。

```csharp
public class MutableAddress {
    public string Street1 { get; set; }
    public string Street2 { get; set; }
    public string City { get; set; }
    public string State { get; set; }
    public string Zip { get; set; }
}

public class ImmutableAddress {
    public string Street1 { get; init; }
    public string Street2 { get; init; }
    public string City { get; init; }
    public string State { get; init; }
    public string Zip { get; init; }
}
```

`MutableAddress` 的属性有 `set` 访问器，可以随时修改。`ImmutableAddress` 把 `set` 换成了 `init`，意味着这些值只能在对象构造时设置，之后就不能再改了。

**其他写法**：让 setter 私有（`{ get; private set; }`）、只保留 getter、或把字段标为 `readonly`。还可以把类声明为 `sealed`，防止子类引入可变行为。

**record 类型**：`record` 默认就是不可变的，语法也更简洁：

```csharp
public record ImmutableAddress(string Street1, string Street2, string City, string State, string Zip);
```

当然，record 也可以被写成可变的，但默认行为是不可变。

**不可变集合**：`System.Collections.Immutable` 命名空间里提供了 `ImmutableList<T>`、`ImmutableDictionary<T, V>` 等类型，一旦创建就无法添加或删除元素。

这些是实现手段，更关键的问题是：**为什么要这样做？**

## 可变对象带来的问题

原文列了六个主要原因，干净利落：

**数据完整性**。代码里的对象不是数据的权威来源，背后通常有一个数据库。对象在内存里"漂着"，改了它的值却没写回数据库，就出现了数据不一致。不可变对象迫使你把修改立刻持久化到数据源，而不是先改内存再说。

**线程安全**。不可变对象天然是线程安全的。多线程同时读一个永远不会变的对象，不存在竞争条件，也不需要加锁或其他同步机制。

**可预测性**。如果一个对象的状态在整个生命周期里保持一致，副作用就少很多。那类"数据在某处被不知名代码改掉"的 bug，基本就消失了。

**安全传递**。可以把不可变对象随便传给任何方法，甚至复制多份，都不担心调用方改掉原始值。

**缓存更简单**。对象不会变，缓存里的值也不需要同步。

**内存效率**。编译器知道一个不可变值不会改变大小，可以更高效地分配和管理内存。不可变对象一旦放进内存，就很少需要再移动。

## 那些反对意见

原文也直接回应了几个常见质疑：

> "需要改值时必须创建新对象，性能开销太大。"

早年确实如此。但在现代运行时和编译器优化下，创建一个新对象的开销几乎可以忽略不计。这个理由已经站不住脚了。

> "我们用的是有状态的领域模型（stateful domain model）。"

没问题。创建新版本，持久化回数据源，然后继续。

> "改造遗留代码太麻烦了。"

原文说得很直接：这不是不做的理由，旧代码迟早要清理。

> "增加了复杂度！"

可能有一点点。但在现代应用里这点复杂度微乎其微，只是一种不同的思维方式。

## 两个实用模式

当需要更新不可变对象的某个值时，有两种常见做法：

### Builder 模式

用 record 作为不可变对象，用配套的 builder 类来创建新版本，同时在 `Build()` 方法里集中处理验证逻辑：

```csharp
public record Address(string Street1, string Street2, string City, string State, string Zip);

public class AddressBuilder {
    public string Street1 { get; set; } = new();
    public string? Street2 { get; set; } = new();
    public string City { get; set; } = new();
    public string State { get; set; } = new();
    public string Zip { get; set; } = new();

    public AddressBuilder(string street1, string city, string state, string zip, string street2 = null) {
        Street1 = street1;
        Street2 = street2;
        City = city;
        State = state;
        Zip = zip;
    }

    public virtual Address Build() {
        if (string.IsNullOrEmpty(Street1)) throw new ValidationException("Street1 must have a value");
        return new Address(this.Street1, this.Street2, this.City, this.State, this.Zip);
    }
}
```

调用起来很干净：

```csharp
var newAddress = new AddressBuilder("123 Any st", "MyCity", "ST", "12345").Build();
```

### `with` 表达式

如果不需要验证，record 内置的 `with` 表达式更简便：

```csharp
Address newAddress = currentAddress with { Street1 = "New street value" };
```

`newAddress` 是一个新的 record 对象，除了 `Street1` 被替换，其余字段和 `currentAddress` 完全一致。

## 两个需要注意的陷阱

**高频循环里的性能**。虽然单次创建对象的开销很小，但如果在一个需要处理大量对象的紧循环里不断创建新实例，累积起来的开销还是不可忽略的。高频变化的场景未必适合不可变。

**浅不变性 vs 深不变性**。这是更微妙的问题。一个对象本身是不可变的，不代表它持有的引用类型字段也是不可变的。比如 `Address` record 里有一个 `List<Phone>` 字段，这个字段的引用本身不能被替换，但 `List<Phone>` 里的内容仍然可以增删。如果要做到真正的深不变性（deep immutability），需要确保对象树上的每一层都是不可变的。

## 什么时候用可变，什么时候用不可变

这是开发者社区里频繁讨论的话题。目前比较主流的共识是：**默认优先不可变，除非有明确理由选择可变**。

判断标准主要看一个对象被创建后需要改变的频率和可能性：

- 日期、地址、个人信息、历史数据、统计数字——改动概率低，首选不可变。
- 实时传感器数据（温度、转速、电压）、UI 状态管理对象——高频变化，可变更合适。

有个 C# 细节值得一提：字符串（`string`）其实一直都是不可变的，只不过是在语言层面对用户透明。改一个字符串的值，底层实际上是创建了一个新的字符串对象，把引用指向它，旧的留给垃圾回收。这是语言从早期就确定下来的内存管理机制。

## 结尾

早年 C# 里，性能开销让不可变对象成了不太受欢迎的选项。现在这个顾虑基本消失了，好处远大于代价。设计对象类型时，默认倾向不可变，只有当场景确实需要频繁修改时，再选择可变。

## 参考

- [The Value of Immutability in .NET — Barret Codes](https://barretblake.dev/posts/development/2026/03/value-of-immutability)
