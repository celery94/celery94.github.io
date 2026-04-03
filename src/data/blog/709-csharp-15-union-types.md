---
pubDatetime: 2026-04-03T09:23:00+08:00
title: "C# 15 的 Union 类型：编译器帮你管住多类型变量"
description: "C# 15 引入 union 关键字，允许声明一个封闭的类型集合，编译器负责穷举检查。本文解析 union 类型的语法、工作原理、实际用途，以及如何在 .NET 11 Preview 2 中动手试用。"
tags: ["CSharp", ".NET", "Pattern Matching"]
slug: "csharp-15-union-types"
ogImage: "../../assets/709/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/csharp-15-union-types/"
---

C# 长期以来缺少一个"这个变量只能是这几种类型之一"的原生表达方式。现在从 .NET 11 Preview 2 开始，C# 15 带来了 `union` 关键字，正式填上这个空缺。

## 之前的写法有什么问题

当一个方法需要返回几种可能的类型时，C# 以前有几条路：

- **用 `object`**：没有任何类型约束，调用方需要写防御性逻辑，根本不知道里面会出现什么类型。
- **用标记接口或抽象基类**：限制了类型范围，但这个"集合"永远是开放的——任何人都能再实现该接口或继承该基类，编译器无法认为集合已经关闭。而且这两种方式都要求类型之间有公共祖先，如果你想联合 `string` 和 `Exception`，或者 `int` 和 `IEnumerable<T>`，根本行不通。

Union 类型解决这些问题的方式很直接：声明一个封闭的 case 类型集合，类型之间不需要任何亲缘关系，集合之外的类型根本加不进来，编译器对 `switch` 表达式执行穷举检查，覆盖所有 case 才算完整。

## 基础语法

最简单的声明长这样：

```csharp
public record class Cat(string Name);
public record class Dog(string Name);
public record class Bird(string Name);

public union Pet(Cat, Dog, Bird);
```

这一行宣告 `Pet` 是一个新类型，变量可以持有 `Cat`、`Dog` 或 `Bird` 中的任意一个。编译器从每种 case 类型到 union 类型提供隐式转换，直接赋值就行：

```csharp
Pet pet = new Dog("Rex");
Console.WriteLine(pet.Value); // Dog { Name = Rex }

Pet pet2 = new Cat("Whiskers");
Console.WriteLine(pet2.Value); // Cat { Name = Whiskers }
```

如果赋了 `Pet` 不认识的类型，编译器直接报错。

对一个确定非空的 `union` 实例使用 `switch` 表达式，覆盖所有 case 类型就能满足穷举要求，不需要 discard `_` 或 default 分支：

```csharp
string name = pet switch
{
    Dog d => d.Name,
    Cat c => c.Name,
    Bird b => b.Name,
};
```

模式匹配作用于 union 的 `Value` 属性，这个"解包"是自动的——你写 `Dog d`，编译器替你检查 `Value`。`var` 和 `_` 是两个例外，它们匹配 union 值本身。

如果之后给 `Pet` 增加第四种 case 类型，所有没有处理它的 `switch` 表达式都会产生编译器警告。这是 union 类型的核心价值之一：漏掉的 case 在构建期就暴露，不用等到运行时。

## null 的处理

`union` 的默认值里 `Value` 是 null。如果 case 类型里有可空类型（比如 `int?` 或 `Bird?`），所有对该 `Pet` 实例的 `switch` 表达式都需要一个 `null` 分支：

```csharp
Pet pet = default;

var description = pet switch
{
    Dog d => d.Name,
    Cat c => c.Name,
    Bird b => b.Name,
    null => "no pet",
};
// description is "no pet"
```

## 实际场景：`OneOrMore<T>`

有些 API 既接受单个值，也接受集合。Union 可以带 body，在其中放辅助成员，就像给普通类型加方法一样：

```csharp
public union OneOrMore<T>(T, IEnumerable<T>)
{
    public IEnumerable<T> AsEnumerable() => Value switch
    {
        T single => [single],
        IEnumerable<T> multiple => multiple,
        null => []
    };
}
```

`AsEnumerable()` 必须处理 `null` case——`Value` 属性的默认 null 状态是 `maybe-null`，这是为联合类型的数组或默认值场景提供正确警告所必需的规则。

调用方只管传哪种形式方便，`AsEnumerable()` 负责归一：

```csharp
OneOrMore<string> tags = "dotnet";
OneOrMore<string> moreTags = new[] { "csharp", "unions", "preview" };

foreach (var tag in tags.AsEnumerable())
    Console.Write($"[{tag}] ");
// [dotnet]

foreach (var tag in moreTags.AsEnumerable())
    Console.Write($"[{tag}] ");
// [csharp] [unions] [preview]
```

## 自定义 Union 类型（适配已有库）

`union` 声明是一个语法糖。编译器生成一个 struct，每种 case 类型对应一个构造函数，`Value` 属性类型是 `object?`，值类型会装箱存储。大多数场景这样就够了。

但有些社区库已经有自己的 union 类实现，并且有特定的存储策略。这些库不需要改用 `union` 语法，只要给类或 struct 加 `[System.Runtime.CompilerServices.Union]` 特性，再满足基本约定——一个或多个公共的单参数构造函数（定义 case 类型）加一个公共 `Value` 属性——编译器就会把它识别为 union 类型。

对于含值类型 case 的性能敏感场景，库还可以实现无装箱访问模式：添加 `HasValue` 属性和 `TryGetValue` 方法，让编译器在做模式匹配时避开装箱。完整细节见 [union 类型语言参考](https://learn.microsoft.com/dotnet/csharp/language-reference/builtin-types/union#custom-union-types)。

## 配套提案：封闭层级与封闭枚举

Union 类型解决的是"对一组封闭类型进行穷举匹配"，与之相关的还有两个在规划中的提案：

- **封闭层级（Closed hierarchies）**：给类加 `closed` 修饰符，阻止在定义程序集之外定义派生类，让对类层级的穷举匹配成为可能。
- **封闭枚举（Closed enums）**：`closed enum` 禁止创建除已声明成员之外的枚举值，使对枚举的穷举匹配更严格。

这三个特性合在一起，构成 C# 完整的穷举性故事：union 针对封闭类型集合，closed hierarchies 针对密封类层级，closed enums 针对固定枚举值。后两个提案目前还未承诺进入某个具体版本，欢迎参与讨论和设计。

## 如何现在就试用

Union 类型从 .NET 11 Preview 2 开始可用，步骤：

1. 下载安装 [.NET 11 Preview SDK](https://dotnet.microsoft.com/download/dotnet)。
2. 创建或更新项目，目标框架设为 `net11.0`。
3. 在项目文件中加入 `<LangVersion>preview</LangVersion>`。

**早期预览版的注意事项**：.NET 11 Preview 2 的运行时里还没有 `UnionAttribute` 和 `IUnion` 接口，需要自己在项目里声明，或者从文档仓库拉取 [RuntimePolyfill.cs](https://github.com/dotnet/docs/blob/e68b5dd1e557b53c45ca43e61b013bc919619fb9/docs/csharp/language-reference/builtin-types/snippets/unions/RuntimePolyfill.cs)：

```csharp
namespace System.Runtime.CompilerServices
{
    [AttributeUsage(AttributeTargets.Class | AttributeTargets.Struct,
        AllowMultiple = false)]
    public sealed class UnionAttribute : Attribute;

    public interface IUnion
    {
        object? Value { get; }
    }
}
```

加完这两个类型，就能正常声明和使用 union：

```csharp
public record class Cat(string Name);
public record class Dog(string Name);

public union Pet(Cat, Dog);

Pet pet = new Cat("Whiskers");
Console.WriteLine(pet switch
{
    Cat c => $"Cat: {c.Name}",
    Dog d => $"Dog: {d.Name}",
});
```

proposal specification 里的部分特性尚未实现（如 union 成员提供者），会在后续预览版中跟进。IDE 支持将在下一个 Visual Studio Insiders 版本中到位，当前的 C# DevKit Insiders 已包含支持。

试用之后，可以在 [GitHub 上的 unions 讨论贴](https://github.com/dotnet/csharplang/discussions/9663)分享反馈，这个设计还在定稿过程中。

## 参考

- [Explore union types in C# 15（原文）](https://devblogs.microsoft.com/dotnet/csharp-15-union-types/)
- [Union types — 语言参考](https://learn.microsoft.com/dotnet/csharp/language-reference/builtin-types/union)
- [Unions — 特性规范](https://learn.microsoft.com/dotnet/csharp/language-reference/proposals/unions)
- [C# 15 新特性](https://learn.microsoft.com/dotnet/csharp/whats-new/csharp-15)
- [unions 讨论贴（GitHub）](https://github.com/dotnet/csharplang/discussions/9663)
