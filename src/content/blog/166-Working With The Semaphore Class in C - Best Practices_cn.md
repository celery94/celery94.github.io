---
pubDatetime: 2024-06-21
tags: []
source: https://code-maze.com/semaphore-introduction-csharp/
author: Georgios Panagopoulos
title: Working With The Semaphore Class in C# - Best Practices
description: In this article, we'll introduce the Semaphore class in C#. Comparing the Semaphore and SemaphoreSlim classes.
---

# 在C#中使用Semaphore类 - 最佳实践

> ## 摘要
>
> 在这篇文章中，我们将介绍C#中的Semaphore类。比较Semaphore和SemaphoreSlim类。

---

在这篇文章中，我们将介绍C#中的Semaphore类。我们将比较Semaphore和SemaphoreSlim类，并讨论使用信号量的最佳实践。

要下载本文的源代码，可以访问我们的[GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/threads-csharp/IntroductionToSemaphoreInCsharp)。

让我们开始吧。

## 什么是C#中的Semaphore类？

C#中的[Semaphore](https://learn.microsoft.com/en-us/dotnet/api/system.threading.semaphore?view=net-8.0)类是一种同步线程访问共享资源的机制。它比lock和[mutex](https://code-maze.com/csharp-how-to-use-mutex-class/)更灵活，因为它不限于定义它的上下文。换句话说，获取同步句柄的线程或进程可以与释放它的线程或进程不同。因此，**信号量支持更广泛的同步场景**。

让我们更详细地分析这个类。

## 初始化Semaphore C#类

使用信号量时，我们可以定义代码允许访问受保护资源或关键部分的最大线程数。这比允许单个线程的锁和mutex有所改进。在定义信号量时，我们可以指定以下设置：

```csharp
var semaphore = new Semaphore(initialCount: 2, maximumCount: 3);
```

在这里，我们创建了一个信号量，允许最多三个线程并行访问共享资源，并且我们最初将计数器设置为2。这类似于一个代码段允许三个持票人访问。

创建信号量后，我们可以调用`semaphore.WaitOne()`让运行的线程访问受保护代码。这也会减少信号量的内部计数器。

一旦线程完成关键操作，我们的代码可以调用`semaphore.Release()`以释放同步句柄。这将增加信号量的内部计数器。

还有一个`semaphore.Release(int count)`方法变体用于多次增加计数器。

如果信号量的内部计数器为零，任何调用`semaphore.WaitOne()`的线程将等待另一个线程调用`semaphore.Release()`。在访问经常被阻塞的情况下，会出现效率低下的情况，因为信号量会同步阻塞任何等待的线程。

到目前为止我们讨论的所有内容都适用于单个进程的线程，我们称这些类型的信号量为本地信号量。

## 命名信号量

命名信号量允许我们实现不同进程线程的同步。这类似于我们可以用mutex实现的效果。

我们可以通过在构造函数参数中设置名称来创建命名信号量：

```csharp
var namedSemaphore = new Semaphore(initialCount: 3, maximumCount: 3, "SemaphoreName");
```

**本地信号量的所有其他功能也适用于命名信号量**。

让我们看看本地信号量如何进行线程同步：

```csharp
public class ExampleWithSemaphore
{
    private static readonly ConcurrentQueue<string> _outputQueue = new();
    private static readonly Semaphore _semaphore = new(initialCount: 3, maximumCount: 3);
    public static async Task<IReadOnlyCollection<string>> AccessWithSemaphoreAsync(int sleepDelay)
    {
        var tasks = new Task[Constants.NumberOfThreads];
        for (int i = 0; i < Constants.NumberOfThreads; i++)
        {
            var processParams = new ProcessParams(i, sleepDelay);
            var task = WorkerWithSemaphoreAsync(processParams);
            tasks[i] = task;
        }
        await Task.WhenAll(tasks);
        return _outputQueue;
    }
    static async Task WorkerWithSemaphoreAsync(ProcessParams processParams)
    {
        _semaphore.WaitOne();
        await Task.Delay(processParams.SleepDelay);
        var output = string.Format("Semaphore: Thread {0} is accessing {1} at {2}",
                                   processParams.SequenceNo,
                                   nameof(_outputQueue),
                                   DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss.fff", CultureInfo.InvariantCulture));
        _outputQueue.Enqueue(output);
        _semaphore.Release();
    }
}
```

这里，我们初始化了一个信号量，并将初始计数和最大计数设置为三。方法`AccessWithSemaphoreAsync()`使用一个循环创建多个`Tasks`，这些任务将同时执行。它还将它们添加到一个`Task[]`中并等待它们完成。

每个线程调用一次`WorkerWithSemaphoreAsync()`方法。命令`_semaphore.WaitOne()`和`_semaphore.Release()`控制对共享资源（一个持有每个并发任务生成值的[ConcurrentQueue](https://code-maze.com/csharp-concurrentqueue/)）的访问。我们还调用`await Task.Delay(processParams.SleepDelay)`来模拟一个长时间运行的操作，就像我们的应用程序进行网络调用一样。

让我们运行代码并查看输出：

```bash
Executing with Semaphore...
Semaphore: Thread 2 is accessing _outputQueue at 2024-06-06 22:27:13.286
Semaphore: Thread 0 is accessing _outputQueue at 2024-06-06 22:27:13.286
Semaphore: Thread 1 is accessing _outputQueue at 2024-06-06 22:27:13.286
Semaphore: Thread 5 is accessing _outputQueue at 2024-06-06 22:27:13.347
Semaphore: Thread 4 is accessing _outputQueue at 2024-06-06 22:27:13.347
Semaphore: Thread 3 is accessing _outputQueue at 2024-06-06 22:27:13.347
Semaphore: Thread 6 is accessing _outputQueue at 2024-06-06 22:27:13.411
Semaphore: Thread 7 is accessing _outputQueue at 2024-06-06 22:27:13.411
Semaphore: Thread 8 is accessing _outputQueue at 2024-06-06 22:27:13.411
Semaphore: Thread 9 is accessing _outputQueue at 2024-06-06 22:27:13.474
```

我们可以观察到任务以三组完成执行。这是因为我们的信号量允许最多三个线程访问代码的关键部分。使用lock或mutex时不可能实现这样的并行性。一般来说，允许的并行性越多，执行时间就越快。

然而，正如我们所提到的，每当一个线程调用`semaphore.WaitOne()`并且信号量的计数器为零时，执行将被阻塞，我们的程序会显得不那么响应。出于这个原因，我们可以选择使用`SemaphoreSlim`类，我们将在下一部分进行介绍。

## SemaphoreSlim C#类

SemaphoreSlim是信号量的一个变种，它允许我们在其他线程获得对受保护资源的访问权时指示线程进行异步等待。SemaphoreSlim使用[Task](https://code-maze.com/csharp-tasks-vs-threads/)的API，可以使用[async and await](https://code-maze.com/asynchronous-programming-with-async-and-await-in-asp-net-core/)。

顾名思义，SemaphoreSlim是一种**仅适用于单个应用程序线程的轻量级信号量类型**。SemaphoreSlim不支持命名信号量，不同的进程不能共享相同的SemaphoreSlim同步句柄。

### 初始化SemaphoreSlim类

我们可以创建一个SemaphoreSlim对象，并提供初始计数和最大计数：

```csharp
var semaphoreSlim = new SemaphoreSlim(initialCount: 3, maxCount: 3);
```

在这里，我们创建了一个SemaphoreSlim对象，它允许最多三个线程并行访问共享资源，并且我们最初将计数器设置为3。

线程可以通过调用`await semaphoreSlim.WaitAsync()`进入受保护代码。这也会减少信号量的内部计数器。更重要的是，当计数器为零时，执行线程将不得不异步等待**。** 这对我们的代码来说是一个很大的好处，因为在等待另一个线程通过调用`semaphoreSlim.Release()`增加计数器时，.NET运行时可以使用该线程来执行其他代码片段。

让我们看看SemaphoreSlim如何管理同步：

```csharp
public class ExampleWithSemaphoreSlim
{
    private static readonly ConcurrentQueue<string> _outputQueue = new();
    private static readonly SemaphoreSlim _semaphoreSlim = new(3, 3);
    public static async Task<IReadOnlyCollection<string>> AccessWithSemaphoreSlimAsync(int sleepDelay)
    {
        var tasks = new Task[Constants.NumberOfThreads];
        for (int i = 0; i < Constants.NumberOfThreads; i++)
        {
            var processParams = new ProcessParams(i, sleepDelay);
            var task = WorkerWithSemaphoreSlimAsync(processParams);
            tasks[i] = task;
        }
        await Task.WhenAll(tasks);
        return _outputQueue;
    }
    static async Task WorkerWithSemaphoreSlimAsync(ProcessParams processParams)
    {
        if (processParams is null)
            return;
        await _semaphoreSlim.WaitAsync();
        await Task.Delay(processParams.SleepDelay);
        var output = string.Format("SemaphoreSlim: Thread {0} is accessing {1} at {2}",
                                   processParams.SequenceNo,
                                   nameof(_outputQueue),
                                   DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss.fff", CultureInfo.InvariantCulture));
        _outputQueue.Enqueue(output);
        _semaphoreSlim.Release();
    }
}
```

这里，我们初始化了一个具有三个线程的`SemaphoreSlim`对象。方法`AccessWithSemaphoreSlimAsync()`使用一个循环创建多个将并行运行的任务对象。它还将它们添加到一个`Task[]`对象中，以便稍后共同引用它们。

每个任务由包含受保护代码的方法`WorkerWithSemaphoreSlimAsync()`创建。这里的所有代码都是非阻塞的。我们使用await关键字来调用`_semaphoreSlim.WaitAsync()`，并使用`await Task.Delay(processParams.SleepDelay)`来模拟一个长时间运行的操作。与之前一样，并发任务将一个值写入`ConcurrentQueue`中。

让我们运行代码并观察输出：

```bash
Executing with SemaphoreSlim...
SemaphoreSlim: Thread 1 is accessing _outputQueue at 2024-06-06 22:27:13.536
SemaphoreSlim: Thread 0 is accessing _outputQueue at 2024-06-06 22:27:13.536
SemaphoreSlim: Thread 2 is accessing _outputQueue at 2024-06-06 22:27:13.536
SemaphoreSlim: Thread 4 is accessing _outputQueue at 2024-06-06 22:27:13.598
SemaphoreSlim: Thread 5 is accessing _outputQueue at 2024-06-06 22:27:13.598
SemaphoreSlim: Thread 3 is accessing _outputQueue at 2024-06-06 22:27:13.598
SemaphoreSlim: Thread 8 is accessing _outputQueue at 2024-06-06 22:27:13.660
SemaphoreSlim: Thread 7 is accessing _outputQueue at 2024-06-06 22:27:13.660
SemaphoreSlim: Thread 6 is accessing _outputQueue at 2024-06-06 22:27:13.660
SemaphoreSlim: Thread 9 is accessing _outputQueue at 2024-06-06 22:27:13.723
```

在这里，所有线程的执行时间与我们的信号量示例中的时间类似。这是因为我们再次允许三个线程访问代码的关键部分。在一个简单的代码示例中并不明显，但主要的区别在于在`await _semaphoreSlim.WaitAsync()`上时我们的程序的线程没有被阻塞。运行时可以在系统的其他部分使用等待的线程，从而更好地使用系统资源。

## SemaphoreFullException错误

调用`semaphore.Release()`时，我们有责任确保可以增加内部计数器而不违反我们设置的信号量对象的最大限制。

让我们看看多次调用`semaphore.Release()`如何导致错误：

```csharp
public static void ReleaseMultipleTimes()
{
    var semaphore = new Semaphore(initialCount: 2, maximumCount: 2);
    semaphore.WaitOne();
    semaphore.Release();
    semaphore.Release();
}
```

在这里，我们创建了一个`initialCount`和`maximumCount`为2的信号量对象。

然后我们调用`semaphore.WaitOne()`，内部计数器减少到1。接下来，我们调用`semaphore.Release()`，计数器的值增加到2。

最后，我们再次调用`semaphore.Release()`，我们的代码抛出一个`SemaphoreFullException`，因为计数器不能超过最大计数。

## 信号量最佳实践

让我们看看使用信号量时应该遵循哪些最佳实践，以实现最佳性能，避免陷阱，并促进代码的可维护性。

### **正确初始化**

我们应该明智地选择最大和初始计数。较高的最大计数将带来较高的并行度和更好的性能。缺点是，随着线程数量的增加，我们也增加了竞争条件和其他并发问题的机会。

### **选择正确的信号量类型**

我们应该根据代码的需要选择正确的信号量类型（Semaphore、SemaphoreSlim、本地和命名信号量）。使用跨多个进程的信号量（命名信号量）时要谨慎，因为它们限制了系统的可扩展性。这是因为集群中的所有服务器共享相同的锁。

### **正确等待和释放**

我们应该始终确保`WaitOne`/`WaitAsync`与`Release`匹配。这样信号量的计数才能保持准确。我们可以使用try/finally块来确保即使发生异常也调用`Release`。

### **避免死锁**

由于信号量指示线程阻塞和等待，它们很容易导致死锁。我们应该确保所有获取信号量的代码路径也释放它。

此外，我们应该尽量避免嵌套信号量，因为在不同顺序中获取多个信号量会导致死锁。这将简化我们代码的理解并提高其可维护性。

### **限制信号量的范围**

为优化性能，我们应该尽量缩小信号量的范围，避免争用。我们应该使用信号量来保护尽可能少的代码，尽快退出代码块。除非必要，我们应优先使用局部或实例级信号量而不是全局信号量。

### **为信号量对象命名**

我们应该为信号量命名，以记录其在代码中的目的和行为，使其他人（以及未来的自己）更容易理解和维护。

## 结论

在这篇文章中，我们介绍了C#的信号量类，它允许我们同步线程和进程对代码关键部分的访问。我们还讨论了SemaphoreSlim类，并将其与Semaphore类进行了比较。

最后，我们探讨了在C#和.NET中使用信号量时应遵循的最佳实践。
