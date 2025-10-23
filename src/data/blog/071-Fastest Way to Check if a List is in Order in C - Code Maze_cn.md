---
pubDatetime: 2024-03-29
tags: [".NET", "C#"]
source: https://code-maze.com/csharp-fastest-way-to-check-if-a-list-is-in-order/
author: Jeff Shergalis
title: C#中检查列表排序的最快方法
description: 探索高效的C#技术来检查列表排序，侧重于编程中的速度和性能优化
---

> ## 摘要
>
> 探索高效的C#技术来检查列表排序，侧重于编程中的速度和性能优化
>
> 原文 [Fastest Way to Check if a List is in Order in C#](https://code-maze.com/csharp-fastest-way-to-check-if-a-list-is-in-order/)

---

在本文中，我们将研究不同的技术，以检查C#中的列表是否有序。我们将先介绍若干技术，包括并行处理。最后，我们将运行一系列基准测试，以帮助我们选择最适合我们用例的选项。

要下载本文的源代码，可以访问我们的 [GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/collections-lists/FastestWayToCheckIfListIsOrdered)。

那么，让我们开始吧！

## 初始设置

在我们开始检查不同的方法之前，我们需要有一些数据可以使用，所以让我们定义一个简单的 `Employee` [记录](https://code-maze.com/csharp-records/)来使用：

```csharp
public record Employee(string Name, DateTime BirthDate, double Salary) : IComparable<Employee>
{
    public int CompareTo(Employee? other)
        => BirthDate.CompareTo(other?.BirthDate);
}
```

我们的 `Employee` 有3个属性：`Name`、`BirthDate` 和 `Salary`。我们还实现了 `IComparable<Employee>` 接口，按 `BirthDate` 对员工进行排序。

接下来，让我们定义一个要用于检验我们方法的员工列表：

```csharp
List<Employee> employees = [
    new Employee("Jack", new DateTime(1998, 11, 1), 3_000),
    new Employee("Danniel", new DateTime(2000, 3, 2), 2_500),
    new Employee("Maria", new DateTime(2001, 5, 23), 4_300),
    new Employee("Angel", new DateTime(2001, 7, 14), 1_900)
];
```

最后，让我们定义一个静态的 `ListOrderValidators` 类来包含我们的不同实现：

```csharp
public static class ListOrderValidators {}
```

**有一点很重要，即在我们的每种方法中，我们定义“排序”为列表以升序排列。**

## 使用循环检查列表排序的方法

在这一部分，我们将探索使用 _for/while循环_ 来判断列表是否有序的几种技术。

### 使用标准For循环检查列表排序

首先，让我们看一下一个最简单的方法，使用 `for` 循环迭代整个列表：

```csharp
public static bool IsOrderedUsingForLoop<T>(List<T> list, IComparer<T>? comparer = default)
{
    if (list.Count <= 1)
        return true;
    comparer ??= Comparer<T>.Default;
    for (var i = 1; i < list.Count; i++)
    {
        if (comparer.Compare(list[i - 1], list[i]) > 0)
            return false;
    }
    return true;
}
```

正如我们在大多数方法中所做的，我们传入一个 `List<T>` 和我们希望使用的 `IComparer<T>` 来定义我们的排序定义。第二件事是检查列表中的项目数量。如果列表为空或只有一个项目，我们认为它是“排序过的”，简单地返回true。

现在，让我们来看看代码。正如我们已经提到的，我们允许提供一个用户定义的 `IComparer<T>`。在缺少调用者提供的比较器的情况下，我们使用类型的默认比较器。现在有了我们的比较器，我们简单地迭代列表，从第二个元素开始。对于每次迭代，我们检查列表中当前元素与前一个元素是否正确排序。

总的来说，这个方法简单直接。它具有 **O(N)**（线性）的运行时间，因此随着列表大小的增加，它也具有相当好的扩展性。

### 使用Span和For循环检查列表排序

这个第二种方法与我们的第一种方法非常相似，但现在我们使用 `Span<T>` 来稍微提高一点性能。更深入地了解 `Span<T>` 以及它如何帮助提高我们代码性能，请查看我们的文章“[如何在C#中使用Span来提高应用程序性能](https://code-maze.com/csharp-span-to-improve-application-performance/)”：

```csharp
public static bool IsOrderedUsingForLoopWithSpan<T>(List<T> list, IComparer<T>? comparer = default)
{
    if (list.Count <= 1)
        return true;
    comparer ??= Comparer<T>.Default;
    var span = CollectionsMarshal.AsSpan(list);
    for (var i = 1; i < span.Length; i++)
    {
        if (comparer.Compare(span[i - 1], span[i]) > 0)
            return false;
    }
    return true;
}
```

在我们的初始检查和检索比较器之后，我们接下来使用 `CollectionsMarshall.AsSpan()` 从 `System.Runtime.InteropServices` 命名空间获取列表上的 `Span`。之后，代码与我们的第一种方法相同。我们迭代我们的span，检查是否每两个连续的项目都按正确的顺序排列。

### 使用Span.Sort进行比较

在我们的第三种方法中，我们不是将连续的元素相互比较，而是首先将元素复制到一个新的集合中。接下来，我们对新集合进行排序，最后比较两个集合：

```csharp
public static bool IsOrderedUsingSpanSort<T>(List<T> list, IComparer<T>? comparer = default)
{
    if (list.Count <= 1)
        return true;
    T[]? array = null;
    try
    {
        comparer ??= Comparer<T>.Default;
        var listSpan = CollectionsMarshal.AsSpan(list);
        var length = listSpan.Length;
        array = ArrayPool<T>.Shared.Rent(length);
        var arraySpan = array.AsSpan(0, length);
        listSpan.CopyTo(arraySpan);
        arraySpan.Sort(comparer);
        for (var i = 0; i < length; i++)
        {
            if (comparer.Compare(listSpan[i], arraySpan[i]) != 0)
                return false;
        }
        return true;
    }
    finally
    {
        if (array is not null)
            ArrayPool<T>.Shared.Return(array);
    }
}
```

与我们之前的方法一样，我们再次使用 `CollectionsMarshal.AsSpan()` 在我们的列表上获取一个span。接下来，我们从 [ArrayPool](https://code-maze.com/csharp-arraypool-memory-optimization/) 租用一个数组，并在其上取一个span。此后，我们将我们的列表复制到span中。

设置的最后一步是对span进行排序。最后，我们迭代这两个集合，比较每个元素是否相等。**我们最后一步是确保将租用的数组归还给** `ArrayPool`，我们通过 `finally` 块来处理。

### 使用Enumerator检查列表排序

本节的最后一种方法涉及到使用 `IEnumerator<>` 遍历集合：

```csharp
public static bool IsOrderedUsingEnumerator<T>(IList<T> list, IComparer<T>? comparer = default)
{
    if (list.Count <= 1)
        return true;
    comparer ??= Comparer<T>.Default;
    var previous = list[0];
    using var enumerator = list.GetEnumerator();
    enumerator.MoveNext();
    while (enumerator.MoveNext())
    {
        var current = enumerator.Current;
        if (comparer.Compare(previous, current) > 0)
            return false;
        previous = current;
    }
    return true;
}
```

首先，我们定义了一个指向列表第一个元素的 `previous` 变量。随后，我们通过调用 `GerEnumerator()` 创建枚举器。由于我们想在列表的第二个元素上开始比较，我们在开始通过枚举器迭代我们的集合之前执行了一次 `MoveNext()`。

在 `while` 循环中，我们首先移动到集合中的下一个元素，并将其存储为 `current` 元素。然后我们将 `current` 与 `previous` 进行比较，以确保它们按正确的顺序排列。最后，在开始下一次迭代之前，我们将 `previous` 设置为 `current` 并循环。

## 使用LINQ检查列表排序

在这一部分中，我们将检查使用LINQ来确定列表是否有序的一些技术。虽然它们可能不是最有效的方法，但它们通常产生更简单、更易读的代码。那么让我们深入研究。

### 使用Order和Enumerators检查列表排序

我们在这一部分的第一个方法有点像混合体。我们使用 `Enumerable.Order()` 来获取我们集合的 `IOrderedEnumerable<T>`，然后使用枚举器进行迭代：

```csharp
public static bool IsOrderedUsingLinqWithOrder<T>(IList<T> list, IComparer<T>? comparer = default)
{
    if (list.Count <= 1)
        return true;
    comparer ??= Comparer<T>.Default;
    var orderedList = list.Order(comparer);
    var index = 0;
    using var enumerator = orderedList.GetEnumerator();
    while (enumerator.MoveNext() && index < list.Count)
    {
        if (comparer.Compare(list[index++], enumerator.Current) != 0)
            return false;
    }
    return true;
}
```

在这里，与我们之前涉及枚举器的例子不同，我们不需要担心 `current` 和 `previous` 值。我们迭代有序的可枚举对象，将当前元素与原始列表中相同位置的元素进行比较。如果元素不相等，即它们的比较不为0，那么我们就知道列表是无序的。

### 使用LINQ的Order和SequenceEqual方法检查列表排序

我们首先使用 [LINQ](https://code-maze.com/linq-csharp-basic-concepts/) `Order()` 方法，该方法允许我们按升序枚举序列中的元素：

```csharp
public static bool IsOrderedUsingLinqWithSequenceEqual<T>(IList<T> list, IComparer<T>? comparer = default,
    IEqualityComparer<T>? equalityComparer = default)
{
    if (list.Count <= 1)
        return true;
    comparer ??= Comparer<T>.Default;
    equalityComparer ??= EqualityComparer<T>.Default;
    var orderedList = list.Order(comparer);
    return list.SequenceEqual(orderedList, equalityComparer);
}
```

这种方法的一个显著区别是需要一个单独的 `IEqualityComparer<T>`。这是因为 `SequenceEqual()` 在确定两个元素是否相等时使用此比较器。因此，除了获取一个比较器对象之外，我们还确保我们有一个等值比较器。

接下来，我们使用 `Order()` 方法创建一个 `IOrderedEnumerable<T>`，传入我们的 `IComparer<T>`。最后，我们调用 `SequenceEqual()` 将我们的原始列表与有序列表按元素逐个进行比较。

### 使用Zip方法检查列表排序

我们可以用于检查列表是否有序的另一种有趣的方法是 `Zip()` 方法，它允许我们将两个集合“合并”在一起：

```csharp
public static bool IsOrderedUsingLinqWithZip<T>(IList<T> list, IComparer<T>? comparer = default)
{
    if (list.Count <= 1)
        return true;
    comparer ??= Comparer<T>.Default;
    return !list
            .Zip(list.Skip(1), (a, b) => comparer.Compare(a, b) <= 0)
            .Contains(false);
}
```

在 `Zip()` 方法中，我们使用2个集合 - 原始列表和新列表，其中只省略了第一个元素。然后我们将集合“合并”或合并成一个新集合，其中元素定义为源列表元素的比较。最后，使用LINQ `Contains()` 我们搜索合并后的集合中的 `false`，这表明我们的列表是无序的。

## 使用任务并行库检查列表排序

对于我们的最后一组方法，让我们看看我们如何使用**任务并行库**提高列表排序验证的性能。该库允许我们轻松并行化for循环，这有助于加快数据列表的处理。当处理较大的列表和集合时，这尤其有用。

### 使用Parallel.For检查列表排序

**任务并行库**中的 `Parallel.For()` 方法允许我们以并行方式运行 _for 循环_ 的迭代，从而可能加速我们的列表处理。与传统的 for 循环一样，`Parallel.For` 允许我们在需要时监控并提前从循环中退出，允许我们对传统循环的同样细致的控制。

让我们定义 `IsOrderedUsingParallelFor()` 方法：

```csharp
public static bool IsOrderedUsingParallelFor<T>(IList<T> list, IComparer<T>? comparer = default)
{
    if (list.Count <= 1)
        return true;
    comparer ??= Comparer<T>.Default;
    var result = Parallel.For(1, list.Count, (index, state) =>
    {
        if (!state.IsStopped && comparer.Compare(list[index - 1], list[index]) > 0)
            state.Stop();
    });
    return result.IsCompleted;
}
```

`Parallel.For()` 有几种重载，但我们调用的是接受3个参数的版本：一个**包含性**的 _起始索引_，一个**排除性**的 _结束索引_，以及一个 `Action<int, ParallelLoopState>`。正如我们的简单 for 循环案例一样，我们从第二个元素（索引1）开始我们的迭代，并将集合中的每个元素与前一个元素进行比较。**请注意，我们还检查循环状态，以确保我们没有在另一个线程中触发停止条件**。

如果我们发现任何无序元素，我们将调用 `state.Stop()`，向并行循环发出提前**退出**并停止进一步处理的信号。最后，我们返回 `result.IsCompleted`，如果所有列表元素都已检查，表示列表是有序的。如果在任何工作线程中调用了 `state.Stop()`，则 `IsCompleted` 将为 false。

### 使用 Parallel.For 和分区检查列表顺序

与我们之前的示例类似，我们再次调用了 `Parallel.For()`，但增加了一些涉及将我们的集合划分为块的额外复杂性。然后我们并行处理这些块。这可以通过更好的数据本地化来帮助提高性能。为了帮助计算最优的块大小，我们使用 `Environment.ProcessorCount` 来确定当前进程可用的逻辑处理器数量：

```csharp
public static bool IsOrderedUsingParallelForPartitioned<T>(List<T> list, IComparer<T>? comparer = default)
{
    const int minPartitionLength = 4;
    if (list.Count <= 1)
        return true;
    comparer ??= Comparer<T>.Default;
    var length = list.Count;
    var maxPartitions = 1 + (length - 1) / minPartitionLength;
    var partitions = Math.Min(Environment.ProcessorCount, maxPartitions);
    if (partitions == 1)
        return IsOrderedUsingForLoopWithSpan(list, comparer);
    var partitionSize = 1 + (length - 1) / partitions;
    var options = new ParallelOptions {MaxDegreeOfParallelism = partitions};
    var result = Parallel.For(0, partitions, options,
        (partitionIndex, state) =>
        {
            var low = partitionIndex * partitionSize;
            var high = Math.Min(length, low + partitionSize + 1) - 1;
            for (var i = low; i < high && !state.IsStopped; i++)
            {
                if (comparer.Compare(list[i], list[i + 1]) > 0)
                    state.Stop();
            }
        });
    return result.IsCompleted;
}
```

首先，我们基于一个简单的计算计算我们希望的最大分区数量，该计算确保我们至少有 1 个分区，并且表明一个分区中最少的元素数量应该是 4。根据这个计算，我们根据计算出的 `maxPartitions` 和处理器数量之间的最小值计算出实际的分区数量。

一旦我们确定了分区数量，再次检查，如果分区数量是 1。在单个分区的情况下，我们简单地调用 `IsOrderedUsingForLoopWithSpan()` 方法。

既然我们确定了至少有 2 个分区，我们就根据集合长度和我们的分区数量计算分区的长度。接下来，我们构造一个 `ParallelOptions` 对象，定义我们所希望的最大并行度。

### 调用 Parallel.For

准备工作全部完成后，我们现在准备调用 `Parallel.For()`。这一次，我们使用了四个参数的重载版本，它接受一个 `fromInclusive` 索引、一个 `toInclusive` 索引、一个 `ParallelOptions` 对象，最后是 `body`，这是一个 `Action<int, ParallelLoopState>`。因为我们分区了我们的集合，我们定义了我们的索引从 0 到我们的分区数量。我们传递我们的 `options` 对象，它设置了最大并行度，然后最终我们定义了我们的 `body`。

我们开始根据正在处理的分区来计算我们的起始索引（`low`）。接着，我们根据实际集合长度和基于我们起始索引和分区大小的计算之间的最小值来定义我们的结束索引（`high`）。注意，我们还从这个值中减去了一（这种重要性将在我们检查下面部分时变得明显）。

有了我们的索引计算，我们现在可以开始循环遍历我们的集合，从 `low` 值开始，结束于 `high` 值。在 for 循环内部，我们比较 `list[i]` 与 `list[i+1]` 的值（这就是为什么我们最初从我们的 `high` 值中减去了 1）。如果我们发现一个无序的元素，我们调用 `state.Stop()` 来跳出循环，并指示所有其他并行循环停止。

最后，就像我们在简单的 `Parallel.For()` 实现中所做的那样，我们返回 `result.IsCompleted` 来指示列表是否有序。

### 结合 Parallel.For 和 Spans

对于这最后一种方法，我们将在分区数据上的并行处理的思想与我们的 `Action` lambda 中对分区进行 span 的想法结合起来：

```csharp
public static bool IsOrderedUsingParallelForPartitionedWithSpans<T>(
    List<T> list, IComparer<T>? comparer = default)
{
    // ...为简洁起见，省略...
    var result = Parallel.For(0, partitions, options,
        (partitionIndex, state) =>
        {
            var low = partitionIndex * partitionSize;
            if (low >= length)
                return;
            var high = Math.Min(length, low + partitionSize + 1);
            var span = CollectionsMarshal.AsSpan(list)[low..high];
            for (var i = 0; i < span.Length - 1 && !state.IsStopped; i++)
            {
                if (comparer.Compare(span[i], span[i + 1]) > 0)
                    state.Stop();
            }
        });
    return result.IsCompleted;
}
```

这个方法的初始化设置与之前的相同，因此为了简洁，我们已将其删除。我们的主要关注点是 `Parallel.For()` 的 lambda 体，我们在此处对集合进行 span 并对其操作。

我们的索引计算几乎与之前的方法相同，但有两个小小的异常。首先，我们检查我们的 `low` 索引是否超出了数组长度，如果是，我们简单地返回。由于我们的分区计算的性质，由于四舍五入，可能会有一个“额外”的分区。第二个异常是我们没有从我们的 `high` 索引中减去 1，因为我们使用 `low` 和 `high` 来切割我们的 span。按照计算，我们使用 `CollectionMarshal.AsSpan()` 来获取我们列表的 span 并将其切割为我们分区的大小。

接下来，我们开始在 span 上循环。**注意，在这里，我们是从 0 开始，并循环到 span 末尾减 1。span 本身根据我们创建的切片计算偏移量。**在循环内部，我们执行我们的连续项比较，如果我们找到无序项，调用 `state.Stop()`。最后，如之前一样，我们返回 `result.IsCompleted`。

## 使用性能基准测试比较各种方法

现在，让我们看看我们检查的所有方法在速度上如何相比。我们将运行性能基准测试，比较它们检查列表是否按顺序所需的时间。

为此，我们将使用 [BenchmarkDotnet](https://code-maze.com/benchmarking-csharp-and-asp-net-core-projects/) 库来运行使用所有不同方法的性能基准测试。我们将测试分别拥有 **10,000**; **25,000**; 和 **1,000,000** 个元素的输入列表。

说到这，让我们看看结果：

| 方法                                          | 长度    |        平均时间 | 分配的内存 |
| --------------------------------------------- | ------- | --------------: | ---------: |
| IsOrderedUsingSpans                           | 10000   |      4.903 微秒 |          - |
| IsOrderedUsingParallelForPartitionedWithSpans | 10000   |      8.778 微秒 |     3870 B |
| IsOrderedUsingForLoop                         | 10000   |      9.823 微秒 |          - |
| IsOrderedUsingParallelForPartitioned          | 10000   |     10.506 微秒 |     4006 B |
| IsOrderedUsingEnumerator                      | 10000   |     18.279 微秒 |       40 B |
| IsOrderedUsingParallelFor                     | 10000   |     21.752 微秒 |     5498 B |
| IsOrderedUsingSpanSort                        | 10000   |     56.526 微秒 |          - |
| IsOrderedUsingLinqWithOrder                   | 10000   |     73.764 微秒 |    40112 B |
| IsOrderedUsingLinqWithZip                     | 10000   |     79.241 微秒 |      272 B |
| IsOrderedUsingLinqWithSequenceEqual           | 10000   |     92.499 微秒 |    40152 B |
|                                               |         |                 |            |
| IsOrderedUsingSpans                           | 25000   |     12.757 微秒 |          - |
| IsOrderedUsingParallelForPartitionedWithSpans | 25000   |     13.564 微秒 |     4153 B |
| IsOrderedUsingParallelForPartitioned          | 25000   |     16.702 微秒 |     4233 B |
| IsOrderedUsingForLoop                         | 25000   |     25.091 微秒 |          - |
| IsOrderedUsingParallelFor                     | 25000   |     34.593 微秒 |     5279 B |
| IsOrderedUsingEnumerator                      | 25000   |     47.508 微秒 |       40 B |
| IsOrderedUsingSpanSort                        | 25000   |    143.391 微秒 |          - |
| IsOrderedUsingLinqWithZip                     | 25000   |    206.634 微秒 |      272 B |
| IsOrderedUsingLinqWithOrder                   | 25000   |    224.838 微秒 |   100123 B |
| IsOrderedUsingLinqWithSequenceEqual           | 25000   |    265.513 微秒 |   100163 B |
|                                               |         |                 |            |
| IsOrderedUsingParallelForPartitionedWithSpans | 1000000 |    337.040 微秒 |     5010 B |
| IsOrderedUsingParallelForPartitioned          | 1000000 |    421.753 微秒 |     5135 B |
| IsOrderedUsingSpans                           | 1000000 |    602.323 微秒 |          - |
| IsOrderedUsingParallelFor                     | 1000000 |    744.821 微秒 |     5488 B |
| IsOrderedUsingForLoop                         | 1000000 |  1,129.064 微秒 |        1 B |
| IsOrderedUsingEnumerator                      | 1000000 |  2,004.603 微秒 |       41 B |
| IsOrderedUsingSpanSort                        | 1000000 |  7,802.513 微秒 |       12 B |
| IsOrderedUsingLinqWithZip                     | 1000000 |  9,308.523 微秒 |      278 B |
| IsOrderedUsingLinqWithOrder                   | 1000000 | 10,472.187 微秒 |  4000235 B |
| IsOrderedUsingLinqWithSequenceEqual           | 1000000 | 12,084.804 微秒 |  4000275 B |

基于我们的基准测试，对于小于或等于 25,000 个元素的较小列表，`IsOrderedUsingSpans()` 表现最佳。然而，在 25,000 个元素标记附近，`IsOrderedUsingParallelForPartitionedWithSpans()` 开始与标准迭代方法缩小差距。随着列表大小的增加，`IsOrderedUsingParallelForPartitionedWithSpans()` 成为明显的赢家。尽管设置有些复杂，但如果我们知道我们正在处理大型列表，那么性能提升是值得的复杂性。

我们的基准测试清楚地表明，运行 `Parallel.For()` 选项有一些开销，这就是为什么只有在我们知道将处理较大集合时，才推荐使用这些技术。一个很好的方法是创建一个混合方法，它根据列表的大小在标准 for 循环和 `Parallel.For()` 之间进行选择。

与任何方法一样，我们需要考虑性能、可扩展性和代码维护。如果这是我们的应用程序每天只执行一次的操作，那么可能只选择直接的 for 循环配合 span 就足够了。如果我们每分钟都在处理大量集合，那么我们的应用程序很可能会从探索更并行的方法中受益。

## 结论

每种方法都有其自身的优点和缺点。作为开发人员，我们需要考虑我们的用例，并选择最适合我们手头问题的选项。
