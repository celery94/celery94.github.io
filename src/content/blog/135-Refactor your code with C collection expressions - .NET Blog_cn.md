---
pubDatetime: 2024-05-09
tags: [C# 12, refactoring, C#, .NET]
source: https://devblogs.microsoft.com/dotnet/refactor-your-code-with-collection-expressions/
author: David Pine
title: 使用C#集合表达式重构您的代码 - .NET博客
description: 探索使用集合表达式和集合初始化器在多种目标类型上进行C# 12重构场景。
---

# 使用C#集合表达式重构您的代码 - .NET博客

> ## 摘要
>
> 探索使用集合表达式和集合初始化器在多种目标类型上进行C# 12重构场景。
>
> 原文 [Refactor your code with collection expressions - .NET Blog](https://devblogs.microsoft.com/dotnet/refactor-your-code-with-collection-expressions/)

---

2024年5月8日

这篇文章是覆盖各种重构场景的系列文章中的第二篇，这些场景探索了C# 12的特性。在这篇文章中，我们将看到如何使用集合表达式重构代码，我们将学习集合初始化器、各种表达式用法、支持的集合目标类型以及扩展语法。这个系列将如何展开：

1.  [使用主构造函数重构你的C#代码](https://devblogs.microsoft.com/dotnet/csharp-primary-constructors-refactoring/)
2.  使用集合表达式重构你的C#代码（本文）
3.  通过别名化任意类型来重构你的C#代码
4.  使用默认lambda参数来重构你的C#代码

这些特性继续我们的旅程，使我们的代码更加可读和可维护，这些被认为是开发者应该知道的“日常C#”特性。

## 集合表达式 🎨

C# 12引入了集合表达式，提供了一种*简单且一致的语法*，适用于许多不同的集合类型。使用集合表达式初始化集合时，编译器生成的代码在功能上等同于使用集合初始化器。该特性强调了*一致性*，同时允许编译器优化降级的C#代码。当然，每个团队都会决定采用哪些新特性，如果你喜欢这种新语法，你可以尝试并引入，因为所有之前初始化集合的方式仍将继续工作。

通过集合表达式，元素以开方括号`[`和闭方括号`]`之间的内联元素序列出现。阅读下文以了解更多有关集合表达式的工作方式。

### 初始化 🌱

C#为初始化不同集合提供了多种语法。集合表达式取代了所有这些语法，让我们先看看你可以用不同方法初始化一个整数数组，如下所示：

```csharp
var numbers1 = new int[3] { 1, 2, 3 };

var numbers2 = new int[] { 1, 2, 3 };

var numbers3 = new[] { 1, 2, 3 };

int[] numbers4 = { 1, 2, 3 };
```

所有四个版本在功能上是等同的，编译器为每个版本生成的代码都是相同的。最后一个示例与新的集合表达式语法相似。如果你稍微眯一下眼睛，你可以将大括号`{`和`}`想象成方括号`[`和`]`，那么你就会读到新的集合表达式语法。集合表达式不使用大括号。这是为了避免与现有语法，特别是在模式中使用`{ }`表示任何非空，的歧义。

最后一个示例是唯一一个显式声明类型的示例，而不是依赖于`var`。以下示例创建了一个`List<char>`：

```csharp
List<char> david = [ 'D', 'a', 'v', 'i', 'd' ];
```

再次说明，集合表达式不能与`var`关键字一起使用。你必须声明类型，因为集合表达式目前没有一个*自然*类型，可以转换成多种[集合类型](https://devblogs.microsoft.com/dotnet/refactor-your-code-with-collection-expressions/#supported-collection-types-)。支持分配给`var`的功能仍在考虑中，但团队尚未确定什么应该是自然类型。换句话说，当你编写以下代码时，C#编译器会报错CS9176: 集合表达式没有目标类型：

```csharp
// 错误 CS9176: 集合表达式没有目标类型
var collection = [1, 2, 3];
```

你可能会问自己，“有了所有这些不同的初始化集合的方法，我为什么要使用新的集合表达式语法？”答案是，使用集合表达式，你可以以一致的方式表达集合。这可以帮助使你的代码更可读和可维护。我们将在接下来的部分中探索更多优点。

### 集合表达式变体 🎭

你可以使用以下语法表达一个集合是*空的*：

```csharp
int[] emptyCollection = [];
```

空集合表达式初始化是替代使用`new`关键字的代码的绝佳替代品，因为它通过编译器优化来避免为某些集合类型分配内存。例如，当集合类型是数组`T[]`时，编译器生成一个`Array.Empty<T>()`，这比`new int[] { }`更有效。另一个快捷方式是使用集合表达式中的元素数量来设置集合大小，例如`new List<int>(2)`对于`List<T> x = [1, 2];`。

集合表达式还允许你在不声明显式类型的情况下分配给接口。编译器确定用于`IEnumerable<T>`、`IReadOnlyList<T>`和`IReadOnlyCollection<T>`等类型的类型。如果实际使用的类型很重要，你会希望声明它，因为如果出现更有效的类型，这可能会改变。同样，在编译器不能生成更有效代码的情况下，例如当集合类型是`List<T>`时，编译器生成一个`new List<int>()`，这在功能上是等同的。

使用空集合表达式的优势有三方面：

- 它提供了一种初始化所有集合的一致方式，无论它们的目标类型是什么。
- 它允许编译器生成高效的代码。
- 它减少了要编写的代码量。例如，你可以简单地写`[]`，而不是写`Array.Empty<T>()`或`Enumerable.Empty<T>()`。

关于高效生成的代码的更多细节：使用`[]`语法生成已知的IL。这允许运行时通过重用`Array.Empty<T>`的存储（对于每个`T`），或者更积极地内联代码来进行优化。

空集合有它们的用途，但你可能需要一个带有一些初始值的集合。你可以使用以下语法初始化带有单个元素的集合：

```csharp
string[] singleElementCollection =
[
    "one value in a collection"
];
```

初始化单个元素集合与初始化多个元素的集合类似。你可以通过添加其他字面值来初始化带有多个元素的集合，使用以下语法：

```csharp
int[] multipleElementCollection = [1, 2, 3 /* 任意数量的元素 */];
```

**一点历史**

---

早期的特性提议包括“集合字面量”这个短语——如果你听到过这个术语与此特性有关，这似乎是显而易见和合乎逻辑的，特别是考虑到前几个例子。所有的元素都是以字面值的形式表达的。但你并不局限于使用字面值。实际上，你可以很容易地用变量来初始化集合，只要类型相对应（当它们不对应时，有一个隐式转换可用）。

让我们看另一个代码示例，但这次使用*扩展元素*，以包括另一个集合的元素，使用以下语法：

```csharp
int[] oneTwoThree = [1, 2, 3];
int[] fourFiveSix = [4, 5, 6];

int[] all = [.. fourFiveSix, 100, .. oneTwoThree];

Console.WriteLine(string.Join(", ", all));
Console.WriteLine($"Length: {all.Length}");
// 输出：
//   4, 5, 6, 100, 1, 2, 3
//   长度：7
```

扩展元素是一个强大的特性，它允许你将另一个集合的元素包含在当前集合中。扩展元素是以简洁的方式合并集合的绝佳方式。扩展元素中的表达式必须是可枚举的（可以用`foreach`迭代）。更多信息，请参阅[扩展 ✨](https://devblogs.microsoft.com/dotnet/refactor-your-code-with-collection-expressions/#spread-)部分。

### 支持的集合类型 🎯

集合表达式可以与许多目标类型一起使用。该特性识别表示集合的类型的“形状”。因此，大多数你熟悉的集合默认情况下都是支持的。对于不匹配该“形状”的类型（主要是只读集合），你可以应用属性来描述构建器模式。BCL中需要属性/构建器模式方法的集合类型已经被更新。

你不太可能需要考虑如何选择目标类型，但如果你对规则感到好奇，请参阅[C#语言参考：集合表达式——转换](https://learn.microsoft.com/dotnet/csharp/language-reference/operators/collection-expressions#conversions)。

集合表达式尚不支持字典。你可以找到一个提议来扩展该特性[C#特性提议：字典表达式](https://github.com/dotnet/csharplang/issues/7822)。

### 重构场景 🛠️

集合表达式在许多场景中都很有用，例如：

- 初始化声明非空集合类型的空集合：
  - 字段。
  - 属性。
  - 局部变量。
  - 方法参数。
  - 返回值。
  - 作为最终避免异常的合并表达式。
- 向希望集合类型参数的方法传递参数。

让我们用这一节来探索一些示例用法场景，并考虑潜在的重构机会。当你定义一个包含非空集合类型的字段和/或属性的`class`或`struct`时，你可以用集合表达式来初始化它们。例如，考虑以下例子`ResultRegistry`对象：

```csharp
namespace Collection.Expressions;

public sealed class ResultRegistry
{
    private readonly HashSet<Result> _results = new HashSet<Result>();

    public Guid RegisterResult(Result result)
    {
        _ = _results.Add(result);

        return result.Id;
    }

    public void RemoveFromRegistry(Guid id)
    {
        _ = _results.RemoveWhere(x => x.Id == id);
    }
}

public record class Result(
    bool IsSuccess,
    string? ErrorMessage)
{
    public Guid Id { get; } = Guid.NewGuid();
}
```

在前面的代码中，结果注册表类包含一个用`new HashSet<Result>()`构造表达式初始化的私有`_results`字段。在你选择的IDE中（支持这些重构特性），右键点击`new`关键字，选择`Quick Actions and Refactorings...`（或按Ctrl + .），并选择`Collection initialization can be simplified`：

代码更新为使用集合表达式语法，如下所示的代码：

```csharp
private readonly HashSet<Result> _results = [];
```

之前的代码使用`new HashSet<Result>()`构造表达式实例化`HashSet<Result>`。然而，在这种情况下`[]`是相同的。

## 扩展 ✨

许多流行的编程语言，如Python和JavaScript/TypeScript等，提供了他们的*扩展*语法变体，它是处理集合的简洁方式。在C#中，*扩展元素*是用来表达将各种集合合并成单个集合的语法。

**正确的术语**

---

*扩展元素*通常与“扩展操作符”这个术语混淆。在C#中，没有所谓的“扩展操作符”。`..`表达式不是一个操作符，它是*扩展元素*语法的一部分表达式。按定义，这种语法与操作符的语法不一致，因为它不对其操作数执行操作。例如，`..`表达式已经存在于范围的*切片模式*中，也出现在[列表模式](https://learn.microsoft.com/dotnet/csharp/language-reference/operators/patterns#list-patterns)中。

那么*扩展元素*到底是什么？它将被“扩展”的集合中的单个值放在目标集合的那个位置。*扩展元素*功能还带来了一个重构机会。如果你有调用`.ToList`或`.ToArray`的代码，或者你想使用急切评估，你的IDE可能会建议使用*扩展元素*语法。例如，考虑以下代码：

```csharp
namespace Collection.Expressions;

public static class StringExtensions
{
    public static List<Query> QueryStringToList(this string queryString)
    {
        List<Query> queryList = (
            from queryPart in queryString.Split('&')
            let keyValue = queryPart.Split('=')
            where keyValue.Length is 2
            select new Query(keyValue[0], keyValue[1])
        )
        .ToList();

        return queryList;
    }
}

public record class Query(string Name, string Value);
```

前面的代码可以被重构为使用*扩展元素*语法，考虑以下代码，它移除了`.ToList`方法调用，并使用表达式主体方法作为另一个重构的版本：

```csharp
public static class StringExtensions
{
    public static List<Query> QueryStringToList(this string queryString) =>
    [
        .. from queryPart in queryString.Split('&')
           let keyValue = queryPart.Split('=')
           where keyValue.Length is 2
           select new Query(keyValue[0], keyValue[1])
    ];
}
```

## `Span<T>`和`ReadOnlySpan<T>`支持 📏

集合表达式支持`Span<T>`和`ReadOnlySpan<T>`类型，这些类型用于表示任意内存的连续区域。你可以从它们提供的性能改进中受益，即使你不直接在代码中使用它们。集合表达式允许运行时提供优化，尤其是在集合表达式被用作参数时选择使用span的重载。

如果你的应用程序使用spans，你也可以直接分配给span：

```csharp
Span<int> numbers = [1, 2, 3, 4, 5];
ReadOnlySpan<char> name = ['D', 'a', 'v', 'i', 'd'];
```

如果你在使用 `stackalloc` 关键字，这里甚至提供了一个重构来使用集合表达式。例如，考虑以下代码：

```csharp
namespace Collection.Expressions;

internal class Spans
{
    public void Example()
    {
        ReadOnlySpan<byte> span = stackalloc byte[10]
        {
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10
        };

        UseBuffer(span);
    }

    private static void UseBuffer(ReadOnlySpan<byte> span)
    {
        // TODO:
        //   使用span...

        throw new NotImplementedException();
    }
}
```

如果你右键点击 `stackalloc` 关键字，选择 `Quick Actions and Refactorings...`（或按 Ctrl + .），并选择 `Collection initialization can be simplified`：

代码被更新为使用集合表达式语法，如下代码所示：

```csharp
namespace Collection.Expressions;

internal class Spans
{
    public void Example()
    {
        ReadOnlySpan<byte> span =
        [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10
        ];

        UseBuffer(span);
    }

    // 省略，以简洁为目的...
}
```

更多信息，请查看 [`Memory<T>` 和 `Span<T>` 使用指南](https://learn.microsoft.com/dotnet/standard/memory-and-spans/memory-t-usage-guidelines)。

## 语义考虑 ⚙️

当用集合表达式初始化集合时，编译器生成的代码在功能上等同于使用集合初始化器。有时，生成的代码比使用集合初始化器更高效。考虑以下示例：

```csharp
List<int> someList = new() { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 };
```

集合初始化器的规则*要求*编译器为初始化器中的每个元素调用 `Add` 方法。然而，如果你使用集合表达式语法：

```csharp
List<int> someList = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
```

编译器生成的代码会改为使用 `AddRange`，这可能更快或更优化。编译器能够进行这些优化是因为它知道集合表达式的目标类型。

## 下一步 🚀

一定要在你自己的代码中试试这个！不久后查看本系列的下一篇文章，我们将探索如何通过别名来重构你的C#代码。同时，你可以在以下资源中了解更多关于集合表达式的信息：

- [C# 功能提案：集合表达式](https://learn.microsoft.com/dotnet/csharp/language-reference/proposals/csharp-12.0/collection-expressions)
- [C# 语言参考：集合表达式](https://learn.microsoft.com/dotnet/csharp/language-reference/operators/collection-expressions)
- [C# 文档：集合](https://learn.microsoft.com/dotnet/csharp/language-reference/builtin-types/collections)
