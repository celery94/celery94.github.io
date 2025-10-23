---
pubDatetime: 2024-03-25
tags: [".NET", "C#", "Performance"]
source: https://code-maze.com/csharp-how-to-convert-readonlymemory-to-a-byte-array/
author: Robinson Small
title: 如何在C#中将ReadOnlyMemory转换为字节数组
description: 本文解释了如何在C#中使用 MemoryMarshal.AsBytes() 将 ReadOnlyMemory 转换为字节数组，包括示例和用例。
---

> ## 摘要
>
> 本文解释了如何在C#中使用 MemoryMarshal.AsBytes() 将 ReadOnlyMemory 转换为字节数组，包括示例和用例。
>
> 原文 [How to Convert ReadOnlyMemory to a Byte Array in C#](https://code-maze.com/csharp-how-to-convert-readonlymemory-to-a-byte-array/)

---

在这篇文章中，我们深入探讨了C#内存结构，重点关注 **ReadOnlyMemory<T>** 和 **byte\[\]** 类型。我们的目标是了解如何将ReadOnlyMemory转换为字节数组，特别是使用 **MemoryMarshal.AsBytes()** 方法。我们还探讨了适用这种转换的场景。

要下载本文的源代码，你可以访问我们的 [GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/collections-arrays/HowToConvertReadOnlyMemoryToByteArrayInCSharp)。

那么，让我们开始吧！

在Patreon上支持Code Maze，去除广告同时获得我们产品的最佳折扣！

## 理解ReadOnlyMemory和字节数组

C#中的 [ReadOnlyMemory](https://learn.microsoft.com/en-us/dotnet/api/system.readonlymemory-1?view=net-8.0) 结构提供了类似数组的连续内存区域的只读视图。这个结构在性能关键性场景下表现出色，在不创建堆上副本的情况下，我们希望处理现有数据。它通过引用现有内存而不是分配新空间来实现这一效率。此外，`ReadOnlyMemory<T>` 通过防止我们在处理数组、字符串或任何其他内存段的一部分时意外修改数据，来促进数据安全。

相反，[byte](https://learn.microsoft.com/en-us/dotnet/api/system.byte?view=net-8.0) 数组是一种可变数据结构。它表示用于存储二进制数据的固定大小内存缓冲区，如文件 I/O 和网络通信等操作中。

现在，让我们来看看如何从 `ReadOnlyMemory<T>` 获取一个 `byte[]`。

虽然 `ReadOnlyMemory<T>` 提供了一个内存视图，但它并不直接暴露底层bytes。因此在这一部分，我们将探索针对特定场景如何获取它们。

引入 `MemoryMarshal`，这是 `System.Runtime.InteropServices` 命名空间中的一个实用类，为与内存相关的类型如 `ReadOnlyMemory<T>` 和 `Span<T>` 的交互提供功能。更多信息见 [MemoryMarshal](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.memorymarshal?view=net-8.0)。

让我们来看看如何使用 `MemoryMarshal.AsBytes()` 方法将ReadOnlyMemory转换为字节数组：

```csharp
public static byte[] ReadOnlyMemoryToByteArray<T>(ReadOnlyMemory<T> input) where T : struct
{
    return MemoryMarshal.AsBytes(input.Span).ToArray();
}
```

在这里，我们定义了一个泛型方法`ReadOnlyMemoryToByteArray<T>()`，它接受一个`ReadOnlyMemory<T>`并将其转换为字节数组。首先要注意的是我们的泛型类型约束`struct`。`MemoryMarshal.AsBytes()`仅对基本类型有效。

在适当地设置了约束以后，我们可以进入到过程的核心，即使用`ReadOnlyMemory<T>` 结构上的`Span`属性获取一个`ReadOnlySpan<T>`，然后将其传递给`MemoryMarshal.AsBytes()`。这个方法将我们的输入重新解释为bytes，返回覆盖相同内存区域的`ReadOnlySpan<byte>`。我们最后的步骤是调用`ToArray()`方法在span上，它将span复制到我们返回的新分配的`byte[]`中。

现在，让我们来测试一下我们的方法：

```csharp
var byteArray = ReadOnlyMemoryToByteArray<int>(new int[] { 1, 2, 3 });
Console.WriteLine(BitConverter.ToString(byteArray));
byteArray = ReadOnlyMemoryToByteArray("foo".AsMemory());
Console.WriteLine(BitConverter.ToString(byteArray));
```

在这里，我们创建了一个`ReadOnlyMemory<int>`和`ReadOnlyMemory<char>`，然后将它们传递给我们的`ReadOnlyMemoryToByteArray()`方法。然后我们使用`BitConverter.ToString()`在控制台上将字节显示为字符串：

```shell
01-00-00-00-02-00-00-00-03-00-00-00
66-00-6F-00-6F-00
```

所以正如我们在这些代码示例中看到的，`MemoryMarshal.AsBytes()`方法简化了将ReadOnlyMemory转换为字节数组的过程。接下来，让我们讨论一下转换的一些用例。

## 转换的用例

将`ReadOnlyMemory<T>`转换为`byte[]`的一些常见场景包括：

- 与期望字节数组的API进行互操作
- 将数据写入I/O流
- 加密操作

在与旧API或库进行互操作时，有些可能不支持`ReadOnlyMemory<T>`。相反，它们要求数据作为`byte[]`。尽管，.NET的最新版本已经添加了支持`ReadOnlyMemory<T>`和`ReadOnlySpan<T>`的方法重载，在这里，我们专注于符合本主题标准的API。在实际情况下，如果可能的话，最好使用新的重载。

考虑`.NET Core 3.0之前的FileStream.Write()`和来自`System.IO`和`System.Security.Cryptography`命名空间的`SHA256.ComputeHash()`方法。

让我们探索一个与这两个API一起工作的示例：

```csharp
byte[] SaveText(string path, ReadOnlyMemory<char> text)
{
    using var stream = new FileStream(path, FileMode.Create, FileAccess.Write);
    byte[] byteArray = MemoryMarshal.AsBytes(text.Span).ToArray();
    stream.Write(byteArray, 0, byteArray.Length);

    using var hashAlgorithm = SHA256.Create();
    return hashAlgorithm.ComputeHash(byteArray);
}
```

在这里，我们的方法将一些文本转换为数组并将其保存到磁盘，然后返回它的哈希。我们将文本以`ReadOnlyMemory<char>`形式传递。接下来，我们通过与我们之前示例中相同的过程将其转换为`byte[]`，然后使用`FileStream.Write()`方法将其写入磁盘。最后，我们使用`SHA256.ComputeHash()`方法对其进行哈希处理，并返回结果。

下面是使用`BitConverter.ToString()`方法转换的哈希结果：

```shell
3F-AE-AF-C2-8D-3C-31-E6-D7-BF-62-8A-53-43-8E-7D-24-A8-68-16-F1-5D-10-F6-BA-54-E1-8F-8F-EC-26-C2
```

现在，让我们了解一下何时使用`ReadOnlyMemory<T>`与字节数组的性能考虑。

## 性能考虑

需要注意的是，`MemoryMarshal.AsBytes()`并不重新分配或复制`ReadOnlyMemory<T>`的底层内存。它只是提供相同的新视图，使其快速且高效。

作为一般指导原则，**我们在数据不会被修改的时候使用`ReadOnlyMemory<T>`。** 访问数据就地进行，无需复制，提高了访问速度。另一方面，当我们需要数据的副本时，例如将其保存到磁盘或通过网络发送时，我们使用`byte[]`。换句话说，**在工作流程的最后阶段，当我们确定需要修改数据时，我们使用`byte[]`。**

然而，与`byte[]`相比，`Memory<T>`和`Span<T>`带来了许多好处。因此，如果我们使用的API支持它们中的任何一个，我们应该考虑使用它。`Memory<T>`和`Span<T>`是提供可变的、内存高效的方式来访问现有数组的结构体。有关更多信息，请参阅[Memory](https://code-maze.com/csharp-using-memory/)和[Span](https://code-maze.com/csharp-span-to-improve-application-performance/)。

## 结论

在这篇文章中，我们探讨了如何在C#中将ReadOnlyMemory转换为字节。我们使用MemoryMarshal.AsBytes()方法首先将我们的ReadOnlyMemory<T>解释为ReadOnlySpan<byte>。然后我们使用ToArray()来复制底层的字节数组。最后，我们考察了这种类型转换有用的性能考虑和场景。
