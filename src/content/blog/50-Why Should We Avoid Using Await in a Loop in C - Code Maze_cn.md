---
pubDatetime: 2024-03-17
tags: []
source: https://code-maze.com/csharp-avoid-await-in-loop/
author: Anaedobe Nneka
title: 为什么我们应该避免在C#循环中使用Await - Code Maze
description: 在本文中，我们将探讨在循环中使用await关键字适当的场景以及不适当的场景。
---

# 为什么我们应该避免在C#循环中使用Await - Code Maze

> ## 摘录
>
> 在本文中，我们将探讨在循环中使用await关键字适当的场景以及不适当的场景。
>
> 原文 [Why Should We Avoid Using Await in a Loop in C# - Code Maze](https://code-maze.com/csharp-avoid-await-in-loop/)

---

在软件开发中，仔细考虑何时在for或for-each循环中使用await关键字是至关重要的，以防止效率低下和性能问题。在本文中，我们将探讨在循环中使用await关键字适当的场景以及不适当的场景。

要下载本文的源代码，您可以访问我们的 [GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/async-csharp/AwaitInForEachLoops)。

让我们开始吧。

## 循环中发生的基本操作

循环通过特定的方法迭代，直到满足特定条件。**虽然在循环中采用异步编程通过使用**`await`**关键字是很诱人的，如果awaited方法可以并发运行，这样做可能会适得其反**，从而忽视了循环的固有特性。要了解更多关于异步编程的信息，请查看我们的文章：[如何异步执行多个任务](https://code-maze.com/csharp-execute-multiple-tasks-asynchronously/)。

## 在循环中添加await关键字会发生什么？

**通过在我们的循环中使用**`await`，**我们暂停迭代以允许awaited方法执行，然后继续执行下一次迭代**。因此，在我们的循环中使用`await`意味着我们正在同步执行循环内的所有操作。

让我们看看在循环中使用await：

```csharp
public static async Task<List<int>> ResultAsync(int delayMilliseconds = 1000)
{
    var numbers = new List<int> { 10, 20, 30, 40, 50, 60, 70, 80, 90 };
    var result = new List<int>();
    foreach (var number in numbers)
    {
        Console.WriteLine($"Processing {number}");
        await Task.Delay(delayMilliseconds);
        Console.WriteLine($"Processed {number}");
        result.Add(number);
    }
    Console.WriteLine("Done Processing");
    return result;
}
```

这里我们在`Task.Delay()`中添加了`await`关键字。这意味着我们必须等待`Task.Delay()`完成之后才能完成循环中剩余的工作并继续到下一个迭代。

在循环中使用await便于元素在循环中的有序执行。当我们“等待”一些额外的长时间运行任务的完成时，我们的代码会暂停。然而，这也意味着完全迭代我们的集合可能需要很长时间。

现在，让我们来看看控制台输出：

```shell
Processing 10
Processed 10
Processing 20
Processed 20
Processing 30
Processed 30
Processing 40
Processed 40
Processing 50
Processed 50
Processing 60
Processed 60
Processing 70
Processed 70
Processing 80
Processed 80
Processing 90
Processed 90
Done Processing
```

在这里，我们观察到程序按照我们在列表中提供它们的顺序正确地处理了数字。在处理过程中没有发生顺序错乱。

## 避免在循环中使用await以使循环异步

由于我们知道在循环中使用await使其同步执行，我们可以探究如何使我们的for-each循环异步执行。这也通过使用`Task.WhenAll()`来练习并行。**简单来说**，`Task.WhenAll()`**允许我们同时等待多个方法，并在它们全部完成时返回一个已完成的任务**。

让我们探索使用`Task.WhenAll()`来提高循环使用时的吞吐量：

```csharp
public static async Task<List<Task>> ResultAsync(int delayMilliseconds = 1000)
{
    var numbers = new List<int> { 10, 20, 30, 40, 50, 60, 70, 80, 90 };

    var result = new List<Task>();

    foreach (int number in numbers)
    {
        result.Add(ProcessNumberAsync(number, delayMilliseconds));
    }

    await Task.WhenAll(result);

    Console.WriteLine("Done Processing");

    return result;
}

public static async Task ProcessNumberAsync(int number, int delayMilliseconds)
{
    Console.WriteLine($"Processing {number}");
    // 模拟一个异步操作
    await Task.Delay(delayMilliseconds);

    Console.WriteLine($"Processed {number}");
}
```

这里我们没有在for-each循环中添加`await`关键字。我们简单地迭代每个数字，为它们每个人启动一个`ProcessNumberAsync()`任务。我们将这些任务添加到一个列表中，然后将列表传递给`Task.WhenAll()`。在for-each循环外部，我们只需等待`Task.WhenAll()`完成后再返回结果。

比较我们的两个示例方法，不在循环中使用await的执行速度更快。

我们还应该注意的是，与我们的同步for-each不同，在我们的`Task.WhenAll()`中，`ProcessNumberAsync()`任务的执行不保证按任何特定顺序进行，因为每个`Task`都是异步计算的。

再次，让我们来看看控制台输出：

```shell
Processing 10
Processing 20
Processing 30
Processing 40
Processing 50
Processing 60
Processing 70
Processing 80
Processing 90
Processed 90
Processed 80
Processed 50
Processed 40
Processed 30
Processed 20
Processed 70
Processed 60
Processed 10
Done Processing
```

正如预期，结果显示数字的处理顺序不具体。它们的打印顺序与列表中的排列不同。同时，我们不必等待一个数字处理完毕再处理下一个数字。

## 何时权衡二者之间的选择

`Task.WhenAll()` 使得跟踪执行顺序变得困难，因为操作可能会并行完成。另一方面，循环中使用await使得通过等待完成再继续到下一个迭代，能够跟踪执行。

此外，当`Task.WhenAll()`中的任何一个awaited任务抛出异常时，管理异常变得更具挑战性，因为异常会传播到等待的线程。当我们在for循环中await每个任务时，我们对异常情况有更清晰的视野。然而，由于强制线性处理循环中的每一步，交易代价可能是性能的降低。

当多个任务彼此独立操作时，使用`Task.WhenAll()`非常有用。这意味着任务的执行不依赖于前一个任务的结果。

在两种方法之间的选择取决于我们旨在实现的特定目标。

## 结论

当方法需要特定的执行序列时，我们在for-each循环中使用await关键字。相反，当执行顺序不是关键时，使用Task.WhenAll()旨在提高性能。
