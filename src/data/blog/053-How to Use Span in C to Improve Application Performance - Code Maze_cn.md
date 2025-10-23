---
pubDatetime: 2024-03-20
tags: [".NET", "C#", "Performance"]
source: https://code-maze.com/csharp-span-to-improve-application-performance/
author: Code Maze
title: 如何使用 C# 中的 Span 来提升应用程序性能
description: 在本文中，我们将学习如何在 C# 中使用 Span 来替换字符串和集合，以提升我们应用程序的性能
---

# 如何使用 C# 中的 Span 来提升应用程序性能

> ## 摘要
>
> 在本文中，我们将学习如何在 C# 中使用 Span 来替换字符串和集合，以提升我们应用程序的性能
>
> 原文地址：[How to Use Span in C# to Improve Application Performance](https://code-maze.com/csharp-span-to-improve-application-performance/)

---

在软件开发中，性能始终是一个重要因素。这不只是框架开发者必须考虑的问题。当 .NET 团队发布了 `Span<>` 结构时，它使得开发者能够正确使用时提升应用性能。在本文中，我们将了解 C# 中的 Span，它是如何实现的，以及我们如何使用它来提升性能。

要下载本文的源代码，你可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/csharp-advanced-topics/SpanInCsharp)。

让我们开始吧。

## 理解 C# 中的 Span<T>

首先，让我们来看看 `Span<>` 并了解它是如何在 .NET 中实现的。我们将看到为什么使用 Span 编码虽然受限，却能提高性能。

`Span<>` 是连续任意内存区域的无分配表示。`Span<>` 被实现为一个包含对对象 `T` 的 `ref` 和长度的 `ref struct` 对象。这意味着在 C# 中的 Span 将始终被分配到栈内存，而非堆内存。让我们考虑一下 `Span<>` 的简化实现：

```csharp
public readonly ref struct Span<T>
{
    private readonly ref T _pointer;
    private readonly int _length;
}
```

这个例子实现允许我们看到 span 的主要组成部分。这有一个指向类型为 `T` 的堆上对象的引用和一个长度。

使用 `Span<>` 会带来性能的提升，因为它们总是分配在栈上。由于垃圾回收不必频繁暂停执行以清理堆上没有引用的对象，应用程序运行得更快。暂停应用程序来回收垃圾始终是一个昂贵的操作，应尽可能避免。`Span<>` 操作可以像操作数组一样高效。索引到 span 中不需要计算索引的内存地址。

C# 中 Span 的另一个实现是 `ReadOnlySpan<>`。它是一个结构体，与 `Span<>` 完全相同，但其索引器返回的是 `readonly ref T`，而不是 `ref T`。这使我们能够使用 `ReadOnlySpan<>` 来表示如 `String` 这样的不可变数据类型。

Span 可以使用其他值类型，如 `int`、`byte`、`ref structs`、`bool` 和 `enum`。Span 不能使用类型如 `object`、`dynamic` 或 `interfaces`。

### Span 的限制

Span 的实现限制了其在代码中的使用，但相反地，它提供了 span 的有用属性。

编译器将引用类型对象分配在堆上，这意味着 **我们不能将 span 作为引用类型中的字段使用。** 更具体地说，`ref struct` 对象不能像其他值类型对象那样被装箱。出于同样的原因，Lambda 表达式也不能使用 span。Span 在异步编程中也不能跨越 `await` 和 `yield` 边界。

在所有情况下，Span 都不适当。**因为我们使用 Span 在栈上分配内存，我们必须记住栈内存比堆内存少。** 我们在选择使用 Span 还是字符串时必须考虑这一点。

如果我们想在异步编程中使用类似 Span 的类，我们可以利用 `Memory<>` 和 `ReadOnlyMemory<>`。我们可以从数组创建一个 `Memory<>` 对象并像我们看到的那样切片，我们可以用 Span 做。一旦我们能同步运行代码，我们就可以从 `Memory<>` 对象获取一个 span。

## 如何使用 ReadOnlySpan 代替 String

首先，让我们讨论一下我们如何在操作 [strings](https://code-maze.com/csharp-string-methods/) 时使用 `ReadOnlySpan<>` 来获得我们寻求的性能优势。

目标是尽可能多地使用 span 而不是 `string`。理想情况是我们有最少数量的字符串，我们可以使用 span 来操作。

让我们考虑一个必须按行解析字符串的例子：

```csharp
public void ParseWithString()
{
    var indexPrev = 0;
    var indexCurrent = 0;
    var rowNum = 0;
    foreach (char c in _hamletText)
    {
        if (c == '\n')
        {
            indexCurrent += 1;
            var line = _hamletText.Substring(indexPrev, indexCurrent - indexPrev);
            if (line.Equals(Environment.NewLine))
                rowNum++;
            indexPrev = indexCurrent;
            continue;
        }
        indexCurrent++;
    }
    Console.WriteLine($"Number of empty lines in a file: {rowNum}");
}
```

首先，让我们使用字符串来回顾这个例子。我们试图确定文件中有多少个空行。要解析的文本存储在 `_hamletText` 字符串变量中。我们迭代测试字符串中的每个 `char`。如果我们找到一个新行字符 `\n`，我们使用 `Substring()` 来创建包含文本行的新字符串。如果那一行是空的，我们就增加我们的计数器。这里的关键是 `Substring()` 会在堆上创建一个 `string`。垃圾收集器将花时间销毁这些字符串。

现在，使用 `ReadOnlySpan<>` 进行同样的解析过程：

```csharp
public void ParseWithSpan()
{
    var hamletSpan = _hamletText.AsSpan();
    var indexPrev = 0;
    var indexCurrent = 0;
    var rowNum = 0;
    foreach (char c in hamletSpan)
    {
        if (c == '\n')
        {
            indexCurrent += 1;
            var slice = hamletSpan.Slice(indexPrev, indexCurrent - indexPrev);
            if (slice.Equals(Environment.NewLine, StringComparison.OrdinalIgnoreCase))
                rowNum++;
            indexPrev = indexCurrent;
            continue;
        }
        indexCurrent++;
    }
    Console.WriteLine($"Number of empty lines in a file: {rowNum}");
}
```

这里的过程相同，除了我们没有为每行创建额外的字符串。我们通过调用 `AsSpan()` 方法将文本字符串转换为 `ReadOnlySpan<>`。此外，我们使用 `Slice()` 方法而不是 `Substring()`。`Slice()` 返回表示子字符串的 `ReadOnlySpan<>`。在这种情况下，没有分配到堆上的东西。

回收内存中的对象会直接影响应用程序性能地暂停执行。将这些原则应用到包括日志子系统的大型生产软件中，我们可以看到这些性能增强是如何累积的。

`ReadOnlySpan<>` 包括许多我们与 `String` 相关联的熟悉函数。我们可以使用 `Contains()`、`EndsWith()`、`StartsWith()`、`IndexOf()`、`LastIndexOf()`、`ToString()` 和 `Trim()`。

## 如何使用 Span 代替集合

由于 spans 可以表示内存的连续部分，这意味着我们可以使用它们来操作 [arrays](https://code-maze.com/csharp-basics-arrays/) 和其他集合类型。

首先，让我们考虑使用数组的例子：

```csharp
int[] arr = new[] { 0, 1, 2, 3 };
Span<int> intSpan = arr;
var otherSpan = arr.AsSpan();
```

我们可以看到 C# 提供了从 `T[]` 到 `Span<T>` 的隐式转换，但我们也能够在数组上调用 `AsSpan()`。就像 `ReadOnlySpan<>` 一样，`Span<>` 提供了以无分配方式操作 span 的熟悉函数。

现在让我们看一个与 [collection](https://code-maze.com/csharp-list-collection/) 如 `List<>` 类似的例子：

```csharp
List<int> intList = new() { 0, 1, 2, 3 };
var listSpan = CollectionsMarshal.AsSpan(intList);
```

我们可以看到，使用集合的 span 不像使用数组那样简单。在这种情况下，我们必须使用 `CollectionMarshal.AsSpan()` 方法来获取集合作为 span。要使用 marshal，我们必须导入 `System.Runtime.InteropServices`。

## 使用基准测试

在本节中，我们将评估运行 `String` 和 `ReadOnlySpan<>` 示例代码的基准测试结果。

让我们讨论从这个基准比较中我们可能期望收到的结果。正如我们所知，使用 spans 通过不将新对象分配到堆上并使用更少的内存来提高性能。我们期望看到运行时间和分配的内存改善。

现在，让我们看看结果：

```csharp
|          Method |     Mean |    Error |   StdDev |   Gen 0 | Allocated |
|---------------- |---------:|---------:|---------:|--------:|----------:|
|   ParseWithSpan | 23.55 us | 0.109 us | 0.102 us |       - |         - |
| ParseWithString | 36.12 us | 0.064 us | 0.054 us | 16.7236 |  70,192 B |
```

从数据中我们可以看到，`ParseWithString()` 的平均时间为 36.12μs 并分配了 70.2kB (70,192B) 的内存。`ParseWithSpan()` 的平均时间为 23.55μs，并且没有分配额外的内存。结果正如我们所期待的。Span 函数运行得更快并分配了更少的内存。

## 结论

在这篇文章中，我们已经介绍了 spans 的实现，为什么使用它们能提高性能，以及如何在我们的代码中使用 spans。需要注意的是，.NET 开发团队正在积极支持 spans 在他们的库中的使用，并使它们的使用对开发者尽可能简单。.NET 团队已经为 `DateTime`、`TimeSpan`、`Int32`、`GUID`、`StringBuilder`、`System.Random` 等许多其他类支持 `Span<>`。了解如何使用 `Span<>` 很重要，因为它们将在未来的 .NET 代码中更加普遍，并可能在某些情况下成为标准。
