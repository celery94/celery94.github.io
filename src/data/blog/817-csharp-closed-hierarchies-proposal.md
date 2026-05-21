---
pubDatetime: 2026-05-21T13:22:23+08:00
title: "C# 封闭层次结构提案：用 closed 修饰符终结 switch 默认分支"
description: "C# 语言设计团队正在提案一个新的 closed 修饰符，允许将类声明为封闭层次结构，把继承限制在同一程序集内。一旦穷举了所有派生类，switch 表达式就不再需要 default 分支，同时编译器也能更精准地检查类型转换的有效性。"
tags: ["CSharp", "语言设计", "模式匹配", "类型系统"]
slug: "csharp-closed-hierarchies-proposal"
ogImage: "../../assets/817/01-cover.png"
source: "https://github.com/dotnet/csharplang/blob/main/proposals/closed-hierarchies.md"
---

C# 长期以来缺少一种方式来表达"这个类只打算由我自己扩展"。你可以用 `sealed` 防止任何人继承，也可以什么都不做让任何人继承，但没有一个中间状态：**我的程序集内部可以继承，外部不行**。

这个提案（Champion issue [#9499](https://github.com/dotnet/csharplang/issues/9499)）试图填补这个空白，核心是新增一个 `closed` 修饰符。

## 问题在哪里

假设你在写一个表示网关状态的类型：

```csharp
// 程序集 1
public record class GateState;
public record class Closed : GateState;
public record class Open(float Percent) : GateState;
```

在程序集 3 里消费时，想用 switch 表达式处理所有情况：

```csharp
string description = state switch
{
    Closed => "closed",
    Open(var percent) => $"{percent}% open"
    // 编译器警告：switch 不完整，GateState 未被覆盖
};
```

编译器不知道 `GateState` 是不是还有其他子类——毕竟任何程序集都能派生它。所以你必须加一个 `default` 或通配符分支，哪怕你完全清楚它永远不会匹配。

## closed 修饰符做了什么

加上 `closed` 之后，派生关系就被锁定在同一程序集内：

```csharp
// 程序集 1
public closed record class GateState;
public record class Closed : GateState;           // 合法，同程序集
public record class Open(float Percent) : GateState; // 合法，同程序集

// 程序集 2
public record class Locked : GateState; // 错误：GateState 是 closed 类
```

这样编译器就能确认：`GateState` 的所有直接派生类都在程序集 1 里，集合是已知的、完整的。消费代码的 switch 表达式只要覆盖所有派生类，就不需要 default 分支，也不会收到警告。

## 几条关键规则

**closed 类隐式 abstract。** 你不能直接实例化一个 closed 类，也不能给它加 `sealed` 或 `static`。

**派生类不自动 closed。** 一个派生自 closed 类的类，除非它自己也显式声明 `closed`，否则仍然是开放的。

**跨程序集阻断，跨模块同理。** 提案要求子类型必须和基类型位于同一模块（module）。

**泛型子类的限制。** 如果一个泛型类直接派生自 closed 类，它的所有类型参数必须出现在基类的类型实参里：

```csharp
closed class C<T> { ... }

class D1<U> : C<U> { ... }    // 合法，U 用在了 C<U> 里
class D2<V> : C<V[]> { ... }  // 合法，V 用在了 C<V[]> 里
class D3<W> : C<int> { ... }  // 错误，W 没有出现在基类里
```

这条规则是为了保证穷举分析的确定性：对于 `C<string>`，每个合法的泛型派生类都有且只有一个对应的实例化版本。

## switch 穷举性的具体行为

覆盖了所有直接派生类，switch 就被认为是穷举的：

```csharp
CC cc = ...;
_ = cc switch
{
    CO co => ...,
    // 不会有"switch 不完整"的警告
};
```

反过来，如果覆盖了所有子类后还多写了一个基类的 case，编译器会报错——这个分支永远无法到达：

```csharp
_ = cc switch
{
    CO co => ...,
    CC cc => ..., // 错误：这个 case 无法被匹配
};
```

有两种情况下即使声明了 closed 也无法做到穷举：

**子类不可访问。** 如果某个派生类是 `protected` 或在访问者看不到的命名空间里，那消费代码无法枚举出完整集合，switch 需要额外处理：

```csharp
closed class C;
class D1 : C;
class Container
{
    protected class D2 : C;
}

class Program
{
    int M(C c) => c switch
    {
        D1 => 1,
        // 警告：switch 不完整，C 未被处理（D2 不可访问）
    };
}
```

**泛型类型参数不"可言说"（speakable）。** 如果类型参数本身没有名字（例如来自方法泛型但不能被具化），编译器无法确认穷举是否成立：

```csharp
int M<X>(C<X> c) where X : C => c switch
{
    D1<X> => 1,
    // 警告：D2<...> 的对应实例化对 X 而言不明确
};
```

## 封闭层次结构的接口转换约束

当一个 closed 类的层次结构里所有类型都是 `sealed` 或自身也是 closed 时，提案称之为"密封层次结构"（sealed hierarchy）。

此时会引入一条接口可转换性限制：如果某个接口 `I` 没有被 closed 类本身或其任何子类实现，那么从 closed 类向 `I` 的显式转换就是非法的：

```csharp
var c = new C();
var i = (I)c; // 错误

closed class C { }
sealed class D1 : C { }
sealed class D2 : C { }
interface I { }
```

这和对 sealed 类的现有规则类似——如果编译器能确认转换永远不会成功，就直接报错。

## 编译器如何阻止其他语言绕过限制

closed 类在元数据里会带上 `[Closed]` attribute 和 `[CompilerFeatureRequired("ClosedClasses")]`。后者加在所有构造函数上：

```csharp
// 低层次元数据视图
[Closed]
class C1
{
    [CompilerFeatureRequired("ClosedClasses")]
    public C1() { }

    [CompilerFeatureRequired("ClosedClasses")]
    public C1(int param) { }
}
```

一个旧版本的编译器（例如 .NET 8 SDK 编译的项目）如果试图从 C1 派生，会看到 `C1.C1()` 需要 `ClosedClasses` 功能，从而报错。这确保了其他语言或旧版工具链无法悄悄绕过封闭限制。

## 潜在风险

提案也诚实地列出了两个问题：

**给现有类加 closed 是破坏性变更。** 如果你的类已经发布出去，外部程序集可能有派生类，加 closed 会直接断掉它们。在设计时就要想好这个长期契约。

**其他语言理论上仍然可能绕过。** 提案的 `CompilerFeatureRequired` 方案依赖其他编译器"配合"尊重这个属性。如果某个非主流工具链不遵守，理论上仍然可以生成违规的派生类，在运行时破坏穷举假设。

## 备选方案和可选功能

提案也提到了几个未选择的方向：

- 用 `[Closed]` attribute 而不是修饰符，保持语法轻量，但表达力弱一些
- 把允许的子类写成显式列表（类似 Java sealed），允许包括外部程序集的类
- 把子类范围收窄到文件或嵌套类

关于"是否允许 interface 也支持 closed"，提案倾向于未来可以扩展，但规则会更复杂（interface 的协变/逆变、多继承等问题需要额外处理）。

## 参考

- [Closed Hierarchies 提案原文（dotnet/csharplang）](https://github.com/dotnet/csharplang/blob/main/proposals/closed-hierarchies.md)
- [Champion issue #9499](https://github.com/dotnet/csharplang/issues/9499)
- [§10.3.5 Explicit reference conversions（C# 标准）](https://github.com/dotnet/csharpstandard/blob/draft-v8/standard/conversions.md#1035-explicit-reference-conversions)
