---
pubDatetime: 2024-03-20
tags: [".NET", "C#", "Memory", "Span", "内存管理", "性能优化"]
source: https://code-maze.com/csharp-using-memory/
author: Muhammad Afzal Qureshi
title: 在 C# 中使用 Memory 实现高效的内存管理
description: 本文展示了在 C# 中使用 Memory 替代 Span 来克服一些限制，以及性能基准测试
---

# 在 C# 中使用 Memory 实现高效的内存管理

> ## 摘要
>
> 本文展示了在 C# 中使用 Memory 替代 Span 来克服一些限制，以及性能基准测试
>
> 原文地址：[Using Memory For Efficient Memory Management in C#](https://code-maze.com/csharp-using-memory/)

---

在编程语言中，有效的内存管理是一个关键方面，特别是当性能和效率至关重要时。在 C# 中，开发者可以访问一个强大的 API，Memory<T>，使他们能够灵活且高效地使用内存。在本文中，我们将深入探讨 Memory<T>，探索其特性、优势、所有权模型和实际使用场景。

要下载本文的源代码，您可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/csharp-advanced-topics/MemoryInCSharp)。

让我们开始吧。

我们使用 [Span](https://code-maze.com/csharp-span-to-improve-application-performance/) 来提供一个内存安全的表示连续内存区域的表达。就像 `Span<T>`，`Memory<T>` 代表一个连续的内存区域。**然而，它可以存在于管理的堆以及栈上，而不仅仅是栈上像 `Span` 一样**。一个 `Span` 是一个存储在栈上的 `ref struct`，有一些限制。如果我们不正确使用 span 或任何其他 `ref struct`，编译器会通知我们。

现在我们已经了解了 `Memory<T>`，让我们看看如何创建它：

```csharp
var numbers = new int[] { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 };
var memory = new Memory<int>(numbers);
```

我们初始化一个整数数组，从那个数组中，我们创建一个 `Memory<int>` 类型的新实例。

现在，让我们查看 `Memory<T>` 的其他用例。

## 在栈和堆上分配 Memory<T>

与仅限于栈的 `Span<T>` 不同，我们可以在栈和堆上分配 `Memory<T>`：

```csharp
public static void WorksWithBothStackAndHeap()
{
    Span<int> stackSpan = stackalloc int[3];
    stackSpan[0] = 1;
    stackSpan[1] = 2;
    stackSpan[2] = 3;
    var stackMemory = stackSpan.ToArray().AsMemory();
    var heapArray = new[] { 4, 5, 6 };
    var heapMemory = heapArray.AsMemory();
    Console.WriteLine("Stack Memory:");
    foreach (var item in stackMemory.Span)
    {
        Console.WriteLine(item);
    }
    Console.WriteLine("\nHeap Memory:");
    foreach (var item in heapMemory.Span)
    {
        Console.WriteLine(item);
    }
}
```

首先，我们创建 `stackSpan`，它是一个通过 `stackalloc` 在栈上分配的 `Span<T>`。

然后，我们将它转换为数组并使用 `ToArray()` 方法，用 `AsMemory()` 方法从中创建一个 `Memory<T>`。这导致 `stackMemory` 成为一个表示与 `stackSpan` 相同数据的 `Memory<T>`，但它在堆上分配，因为在 .NET 中数组总是在堆上分配的。

我们定义 `heapArray` 作为一个我们在堆上分配的数组，并使用 `AsMemory()` 方法创建 `heapMemory`。这导致 `heapMemory` 成为一个表示与 `heapArray` 相同数据的 `Memory<T>`，也在堆上分配。

最后，我们展示了 `stackMemory` 和 `heapMemory` 的内容。

## 在 C# 中带有异步方法的 Memory<T>

现在，让我们在异步代码中使用 `Memory<T>`：

```csharp
public static async Task ProcessMemoryAsync(Memory<int> memory)
{
    await Task.Delay(1000);
    for (var index = 0; index < memory.Span.Length; index++)
    {
        var item = memory.Span[index];
        Console.WriteLine(item);
    }
}
```

在这里，我们使用 `Task.Delay()` 模拟异步操作，然后我们通过 `memory.Span` 访问内存中的数据，并将其打印到控制台。由于是 `ref struct`，我们不能在异步代码中使用 `Span<T>`，这在异步代码中是不可能的。

## AsMemory() 扩展方法

**扩展方法 `String.AsMemory()` 允许我们从一个字符串中创建一个 `Memory<char>` 对象，而不复制底层数据**。当需要将子字符串传递给接受 `Memory<T>` 参数的方法而不想增加额外的内存分配时，这非常有用：

```csharp
public static void StringAsMemoryExtensionMethod()
{
    const string str = "Hello Code Maze";
    var memory = str.AsMemory();
    var slice = memory.Slice(6, 8);
    Console.WriteLine(slice.ToString()); // "Code Maze"
}
```

首先，我们使用 `AsMemory()` 扩展方法从一个字符串创建一个 `Memory<char>`。然后，我们切割这个 `Memory<char>` 以获得一个表示原始字符串的一部分的新 `Memory<char>`。最后，我们通过使用 `ToString()` 方法将这个切片转换为字符串来显示它。

接下来，让我们关注高级内存管理技巧。

## 所有权模型和 IMemoryOwner 接口

`MemoryPool<T>.Rent()` 方法返回 `IMemoryOwner<T>` 接口，该接口作为内存块的所有者。共享池允许租用内存块。当不再使用内存时，块的所有者负责处理它。让我们以使用 `IMemoryOwner<T>` 和 `MemoryPool<T>` 的示例来看看：

```csharp
public static void UseMemoryOwner()
{
    using IMemoryOwner<int> owner = MemoryPool<int>.Shared.Rent(10);
    var memory = owner.Memory;
    for (var i = 0; i < memory.Length; i++)
    {
        memory.Span[i] = i;
    }
    foreach (var item in memory.Span)
    {
        Console.WriteLine(item);
    }
}
```

首先，我们从共享池中使用 `MemoryPool<int>.Shared.Rent()` 方法租用一个内存块。这返回一个拥有已租用内存块的 `IMemoryOwner<int>`。

接下来，我们使用 `owner.Memory` 属性检索代表此内存块的 `Memory<int>`。我们使用这个 `Memory<int>` 来存储一些数据，然后显示这些数据。

最后，我们使用 using 语句处理 `IMemoryOwner<int>`。**这将内存块返回给池，使其可用于后续的 `Rent()` 调用。**

现在我们已经全面了解了 `Memory<T>`，让我们看看使用 `Memory<T>` 进行文件 I/O 操作的实际用例。

## 在 C# 中使用 Memory<T> 的实际场景

我们可以在一个实际场景中使用 `MemoryPool<T>`、`IMemoryOwner<T>` 和 `IMemoryOwner.Memory` 属性。

在这种情况下，我们将创建一个方法，该方法将数据从文件读取到一个租用的内存块中，处理数据，然后将内存返回到池中：

```csharp
public static async Task ProcessFileAsync(string filePath)
{
    using var owner = MemoryPool<byte>.Shared.Rent(4096);
    Memory<byte> buffer = owner.Memory.Slice(0, 4096);
    await using FileStream stream = File.OpenRead(filePath);
    int bytesRead;
    while ((bytesRead = await stream.ReadAsync(buffer)) > 0)
    {
        var data = buffer.Slice(0, bytesRead);
        for (var index = 0; index < data.Span.Length; index++)
        {
            var b = data.Span[index];
            Console.Write((char)b);
        }
        Console.WriteLine();
    }
}
```

首先，在 `ProcessFileAsync()` 方法中，我们通过调用 `MemoryPool<byte>.Shared.Rent()` 方法从共享池中获取内存块。这个方法返回一个拥有内存块的 `IMemoryOwner<byte>` 接口。

接着，我们使用 `owner.Memory` 属性检索一个代表内存块的 `Memory<byte>` 对象。然后，我们使用这个 `Memory<byte>` 对象作为缓冲区，通过 `FileStream.ReadAsync()` 方法从文件中读取数据。读取数据后，我们通过打印到控制台来处理它。

最后，在 `ProcessFileAsync()` 方法中使用 using 语句处理 `IMemoryOwner<byte>` 接口。这个动作将内存块返回到池中，使其可用于后续的 `Rent()` 调用。

## 结论

对于重视性能和效率的应用程序的开发者来说，Memory<T> 是一个灵活且强大的内存管理 API，在 C# 中大有裨益。通过能够在栈和堆上分配、与字符串的互操作以及所有权模型，Memory<T> 是一项宝贵的资产。通过理解和利用 Memory<T>，C# 开发者可以优化内存使用，提高应用程序性能，并构建更健壮、可伸缩的软件解决方案。
