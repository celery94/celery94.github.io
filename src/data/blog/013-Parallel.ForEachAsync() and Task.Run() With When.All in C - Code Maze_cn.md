---
pubDatetime: 2024-02-20T15:06:39
tags: [".NET", "C#"]
source: https://code-maze.com/csharp-parallel-foreachasync-and-task-run-with-when-all/
author: Aneta Muslic
title: Parallel.ForEachAsync() 和 Task.Run() 结合 When.All 在 C# 中的应用
description: 在本文中，我们比较了两种不同的方法，Parallel.ForEachAsync 和 Task.WhenAll，用于并行执行重复的异步方法。
---

# Parallel.ForEachAsync() 和 Task.Run() 结合 When.All 在 C# 中的应用

> ## 摘录
>
> 在本文中，我们比较了两种不同的方法，Parallel.ForEachAsync 和 Task.WhenAll，用于并行执行重复的异步方法。
>
> 本文翻译自 文章 [Parallel.ForEachAsync() and Task.Run() with When.All in C#](https://code-maze.com/csharp-parallel-foreachasync-and-task-run-with-when-all/)。

---

并行编程是 .NET 领域中一个常见且广泛的概念。在这篇文章中，我们比较了在执行重复的异步任务时，我们用来实现它的两种众所周知的方法。我们将看看它们在底层如何工作，并比较每一个的优缺点。

要下载本文的源代码，您可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/threads-csharp/ParallelProgrammingDifferences)。

让我们开始吧。

## 并行编程

总的来说，[并行编程](https://code-maze.com/csharp-async-vs-multithreading/)涉及使用多个线程或处理器来同时执行任务。它旨在通过将任务划分为可以同时处理的更小部分来提高性能和响应性。

除了提高性能和响应性之外，使用并行编程还有其他一些优势。首先，通过将任务分解为并发子任务，我们可以有效地减少整体执行时间。另一个额外的好处是，由于同时处理多个任务，吞吐量得到了增强。此外，以并行方式运行任务有助于我们确保可伸缩性，因为它能有效地在处理器之间分配任务。这允许在添加资源时，性能能够无缝地扩展。

我们在处理并行编程时应考虑的另一件事是我们尝试并行化的进程类型。在本文中，我们将提到 I/O-bound 和 CPU-bound 进程。

**I/O bound processes 是指计算持续时间由等待输入/输出操作的时间决定的过程，这方面的一个例子是数据库调用。另一方面，我们有 CPU-bound processes。在这种情况下，CPU 的性能决定了任务的持续时间，一个例子是执行一些重度数字计算的方法。**

既然我们已经简要了解了并行编程和不同类型的进程，那么让我们快速设置一切并看看它的实际操作。

## 设置异步方法

由于我们已经有一篇深入探讨[如何异步执行多个任务](https://code-maze.com/csharp-execute-multiple-tasks-asynchronously/)的优秀文章，在这里我们将仅为`Task.WhenAll()`方法创建一个基线，我们将在比较这两种方法时对其进行修改。

我们从默认的 web-API 项目开始，扩展 `WeatherForecastController` 方法，增加一个可以多次运行的异步方法：

```csharp
[HttpGet("weather-forecast-when-all", Name = "GetWeatherForecastWhenAll")]
public async Task<IEnumerable<WeatherForecast>> GetWeatherForecastWhenAll()
{
    var result1 = await AsyncMethod();
    var result2 = await AsyncMethod();
    var result3 = await AsyncMethod();
    var result = result1.Concat(result2).Concat(result3);
    return result;
}
private static async Task<IEnumerable<WeatherForecast>> AsyncMethod()
{
    await Task.Delay(250);
    return Enumerable.Range(6, 5).Select(index => new WeatherForecast
    {
        Date = DateOnly.FromDateTime(DateTime.Now.AddDays(index)),
        TemperatureC = new Random().Next(-20, 55),
        Summary = Summaries[new Random().Next(Summaries.Length)]
    })
    .ToArray();
}
```

**在进程类型的上下文中，`AsyncMethod()` 模拟 I/O-bound 过程，而任务延迟代表了子系统响应的等待时间。**

在我们配置好所有东西后，让我们看看如何并行执行这些任务。

## 使用 Task.WhenAll

首先，我们需要重构 `GetWeatherForecastWhenAll()` 方法，以使用 `Task.WhenAll()` 方法。它接受一个任务的枚举并且在集合中所有单独的任务完成运行后返回一个新的完成任务：

```csharp
[HttpGet("weather-forecast-when-all", Name = "GetWeatherForecastWhenAll")]
public async Task<IEnumerable<WeatherForecast>> GetWeatherForecastWhenAll()
{
    var tasks = new List<Task<IEnumerable<WeatherForecast>>>();
    var result1 = AsyncMethod();
    var result2 = AsyncMethod();
    var result3 = AsyncMethod();
    tasks.Add(result1);
    tasks.Add(result2);
    tasks.Add(result3);
    var combinedResults = await Task.WhenAll(tasks);
    var result = combinedResults.SelectMany(cr => cr);
    return result;
}
```

我们定义了一个空的任务列表。接下来，我们三次调用`AsyncMethod()`方法，而没有使用await关键字。**这将开始一个接一个地执行这些任务，而不等待它们完成**。这正是我们想要的，因为我们将这些任务添加到我们的`tasks`列表中，并使用`Task.WhenAll()`来等待它们全部完成。

最后，当所有任务都完成了，我们将保存结果的 `combinedResults` 变量进行扁平化处理，并将结果返回给用户。

**我们在使用任务的并行执行时需要牢记线程使用情况。一次性启动太多线程会增加上下文切换的开销，并可能影响整个应用程序的效率。同时，我们也不希望阻塞主线程。**因此，让我们看看我们如何能更好地理解这个方法在底层关于线程的工作方式。

### 线程处理

我们首先给线程添加日志记录功能：

```csharp
[HttpGet("weather-forecast-when-all", Name = "GetWeatherForecastWhenAll")]
public async Task<IEnumerable<WeatherForecast>> GetWeatherForecastWhenAll()
{
    Console.WriteLine($"GetWeatherForecastWhenAll started on thread: {Environment.CurrentManagedThreadId}");
    var tasks = new List<Task<IEnumerable<WeatherForecast>>>();
    var result1 = AsyncMethod();
    var result2 = AsyncMethod();
    var result3 = AsyncMethod();
    tasks.Add(result1);
    tasks.Add(result2);
    tasks.Add(result3);
    var combinedResults = await Task.WhenAll(tasks);
    var result = combinedResults.SelectMany(cr => cr);
    Console.WriteLine($"GetWeatherForecastWhenAll started on thread: {Environment.CurrentManagedThreadId}");

    return result;
}
private static async Task<IEnumerable<WeatherForecast>> AsyncMethod()
{
    Console.WriteLine($"AsyncMethod started on thread: {Environment.CurrentManagedThreadId}");

    await Task.Delay(250);
    Console.WriteLine($"AsyncMethod completed on thread: {Environment.CurrentManagedThreadId}");

    return Enumerable.Range(6, 5).Select(index => new WeatherForecast
    {
        Date = DateOnly.FromDateTime(DateTime.Now.AddDays(index)),
        TemperatureC = new Random().Next(-20, 55),
        Summary = Summaries[new Random().Next(Summaries.Length)]
    })
    .ToArray();
}
```

这里，我们在每个方法的开始和结束处都添加了一个 `Console.WriteLine()` 语句。在那里，我们使用 `Environment.CurrentManagedThreadId` 打印方法开始和结束时所在的线程。

现在，如果我们执行我们的请求，在输出窗口中我们可以看到线程的行为方式：

```bat
GetWeatherForecastWhenAll started on thread: 16
AsyncMethod started on thread: 16
AsyncMethod started on thread: 16
AsyncMethod started on thread: 16
AsyncMethod completed on thread: 7
AsyncMethod completed on thread: 16
AsyncMethod completed on thread: 15
GetWeatherForecastWhenAll completed on thread: 7
```

让我们分解一下，以理解发生了什么。

当我们发送一个HTTP请求时，[线程池中的一个线程](https://code-maze.com/csharp-tasks-vs-threads/)被分配来处理它。在我们的例子中，这是线程编号16。然后，当我们调用我们的异步方法，并且我们不使用`await`关键字时，任务通常会在相同的线程上开始执行，即16。

但是，当一个异步操作遇到`await`关键词时，在我们的例子中是对`Task.WhenAll()`的`await`，它会在等待任务完成的期间，将当前线程释放到线程池。当等待的操作完成并且我们想要返回结果时，继续执行的操作不一定会在原始线程上恢复。这就是为什么我们看到一些任务在不同的线程上结束，而不是它们开始的线程。

除了不使用 `await` 关键字来创建任务，我们还可以使用 `Task.Run()` 方法，那么我们来看一下它。

### 使用 Task.Run 与 Task.WhenAll

通过使用 [Task.Run()](https://code-maze.com/csharp-task-run-vs-task-factory-startnew/) 方法来执行任务，我们确保每个新任务在一个[单独的线程](https://code-maze.com/csharp-new-thread/)上执行：

```csharp
[HttpGet("weather-forecast-when-all", Name = "GetWeatherForecastWhenAll")]
public async Task<IEnumerable<WeatherForecast>> GetWeatherForecastWhenAll()
{
    var result1 = Task.Run(() => AsyncMethod());
    var result2 = Task.Run(() => AsyncMethod());
    var result3 = Task.Run(() => AsyncMethod());
    var combinedResults = await Task.WhenAll(result1, result2, result3);
    var result = combinedResults.SelectMany(cr => cr);
    return result;
}
```

在这里，我们使用 `Task.Run()` 方法来连续三次执行 `AsyncMethod()`。再次强调，通过跳过 `await` 关键字，我们没有等待任何方法完成，而是并行运行它们，并在 `Task.WhenAll()` 上等待它们的结果。

现在，让我们再来看一看执行请求时的输出日志：

```bat
GetWeatherForecastWhenAll started on thread: 20
AsyncMethod started on thread: 19
AsyncMethod started on thread: 21
AsyncMethod started on thread: 13
AsyncMethod completed on thread: 21
AsyncMethod completed on thread: 13
AsyncMethod completed on thread: 20
GetWeatherForecastWhenAll completed on thread: 20
```

这次，我们看到每个新任务在一个新线程上开始执行。当使用 `Task.Run()` 时，我们预期会有这种行为，因为它的目的是将工作从当前线程中卸载。与前一个示例相同，由于 `async/await` 的性质和线程池分配线程，任务完成时在的线程与最初开始的线程不同。

**使用 `Task.Run()` 需要谨慎，因为它可能有一些缺点。由于它将工作卸载到新线程，任何时候它处理大量任务时都可以创建大量线程，每个线程消耗资源，可能导致线程池饥饿。**

现在我们已经看到了如何明确地将每个任务卸载到一个新线程，让我们来看看我们如何可以使用另一种方法来并行执行这些任务。

我们并行化这项工作的另一种方式是使用`Parallel.ForEachAsync()`方法：

```csharp
[HttpGet("weather-forecast-parallel", Name = "GetWeatherForecastParallelForEachAsync")]
public async Task<IEnumerable<WeatherForecast>> GetWeatherForecastParallelForEachAsync()
{
    Console.WriteLine($"GetWeatherForecastParallelForEachAsync started on thread:
    {Environment.CurrentManagedThreadId}");
    ParallelOptions parallelOptions = new()
    {
        MaxDegreeOfParallelism = 3
    };
    var resultBag = new ConcurrentBag<IEnumerable<WeatherForecast>>();
    await Parallel.ForEachAsync(Enumerable.Range(0, 3), parallelOptions, async (index, _) =>
    {
        var result = await AsyncMethod();
        resultBag.Add(result);
    });
    Console.WriteLine($"GetWeatherForecastParallelForEachAsync completed on thread:
    {Environment.CurrentManagedThreadId}");
    return resultBag.SelectMany(cr => cr);
}
```

首先，我们设置 `MaxDegreeOfParallelism` 值。**通过这个设置，我们定义了有多少并发操作运行。** **如果没有设置，它将使用底层调度器提供的尽可能多的线程**。为了确定 CPU 进程的这个值，请从 `Environment.ProcessorCount` 开始。对于 I/O 绑定的进程，这个值更难确定，因为它依赖于 I/O 子系统，包括网络延迟、数据库响应等等。所以，在处理 I/O 绑定进程时，我们需要通过不同值的测试来确定最佳值以实现最大并行化。

之后，我们定义了一个 `ConcurrentBag` 用于我们的结果，这是一个线程安全的集合，因为我们使用任务的并行执行并在循环中处理结果。允许我们安全地修改集合，而不用担心并发修改异常。最后，我们设置 `Parallel.ForEachAsync()` 方法运行三次，并设置选项，在循环内部，我们等待每个结果并将其添加到 `resultBag` 中。

**在使用 `Parallel.ForEachAsync()` 方法时要提到的一点是，它有其底层的分区。这种分区将输入数据划分为可管理的批次，并将每个批次分配给不同的线程进行并行处理。** 批次的确切大小由框架根据可用处理器的数量和输入数据的特性等因素动态确定。因此，通过定义 `MaxDegreeOfParallelism`，我们定义了同时执行的批处理任务的数量。

关于线程使用，由于我们没有显式地更改线程分配，线程的分配就像在传统的 `async/await` 过程中一样。使用 `Task.WhenAll()` 的线程使用有一个不同之处是，由于我们在循环内对每个调用都使用了 `await` 关键字，所以大多数任务很可能都在它们各自的线程上开始。

现在，让我们看一下在这种情况下 `Task.Run()` 方法的表现。

### 使用 Task.Run 与 Parallel.ForEachAsync 结合使用

我们来修改我们的方法，以使用 `Task.Run()` 生成任务：

```csharp
[HttpGet("weather-forecast-parallel", Name = "GetWeatherForecastParallelForEachAsync")]
public async Task<IEnumerable<WeatherForecast>> GetWeatherForecastParallelForEachAsync()
{
    Console.WriteLine($"GetWeatherForecastParallelForEachAsync started on thread:
    {Environment.CurrentManagedThreadId}");
    ParallelOptions parallelOptions = new()
    {
        MaxDegreeOfParallelism = 3
    };
    var resultBag = new ConcurrentBag<IEnumerable<WeatherForecast>>();
    await Parallel.ForEachAsync(Enumerable.Range(0, 3), parallelOptions, async (index, _) =>
    {
        var result = await Task.Run(() => AsyncMethod());
        resultBag.Add(result);
    });
    Console.WriteLine($"GetWeatherForecastParallelForEachAsync completed on thread:
    {Environment.CurrentManagedThreadId}");
    return resultBag.SelectMany(cr => cr);
}
```

**然而，在这种情况下，这可能不是最佳方法。**如我们已经看到的，`Parallel.ForEachAsync()`有一个内置的分区器，它创建任务批次并在单个线程中处理它们。但通过使用`Task.Run()`，我们将每个任务卸载到它自己的线程中。因此，在这种情况下使用`Task.Run()`，破坏了使用`Parallel.ForEachAsync()`来分块任务并使用更少线程的好处。

我们在尝试并行化任务时可能会遇到的另一个问题是使用`Parallel.ForEach()`方法。

### 需要避免的 Parallel.ForEach 的陷阱

`Parallel.ForEach()` 方法，虽然与 `Parallel.ForEachAsync()` 相似，但缺少处理异步工作的设计能力。然而，我们仍然可以遇到一些将其与异步任务一起使用的例子。

所以让我们快速检查为什么这些方法可能不是最佳解决方案，并看看它们的缺点。

我们常见的一种做法是在同步代码中使用`GetAwaiter().GetResult()`来强制等待结果：

```csharp
Parallel.ForEach(Enumerable.Range(0, 3), parallelOptions, (index, _) =>
{
   var result = AsyncMethod().GetAwaiter().GetResult();
   resultBag.Add(result);
});
```

我们应该避免这种方法，因为通过使用`GetAwaiter().GetResult()`，我们阻塞了调用线程，这是`async/await`的一个反模式。这可能会导致死锁、性能下降和丧失上下文切换的好处。

另一种方法涉及使用 async void：

```csharp
Parallel.ForEach(Enumerable.Range(0, 3), parallelOptions, async (index, _) =>
{
   var result = await AsyncMethod();
   resultBag.Add(result);
});
```

在这种方法中，我们遇到了另一个反模式，那就是使用`async/void`。这是一个众所周知的不良实践，有几个[避免使用它的理由](https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming)。其中一个理由是我们无法在catch块中捕获异常。

正如我们所看到的，这两种方法都涉及使用反模式来使 `Parallel.ForEach()` 与异步方法兼容。**由于它们都不是推荐的并行化实现方式，随着 .NET 6 引入 `Parallel.ForEachAsync()`，我们有了一个更好的方法来在 for-each 循环中处理异步任务。**

既然我们已经了解了不应该做什么，那就让我们总结一下到目前为止我们学到的所有内容吧！

就像编程中的所有内容一样，我们如何利用这篇文章中的知识取决于应用程序的特定需求。然而，在选择合适的方法时，我们应该考虑几个因素。

**当我们讨论可以从并行化中受益的 CPU-bound 任务时，`Parallel.ForEachAsync()` 的使用显得尤为突出。**它的主要好处是能够高效地将工作负载分布到多个处理器核心上。此外，通过设置 `MaxDegreeOfParallelism`，我们可以控制我们想要强加的并发级别。正如我们所见，我们可以轻松确定那个值。

**另一方面，当处理 I/O-bound 任务时，这些操作涉及等待外部资源，`Task.WhenAll()` 成为了更好的选择。**它允许我们并发执行多个异步任务，而不阻塞调用线程。这使它成为数据库查询或网络请求等场景的有效选项。另一个好处是，我们不需要在循环内处理结果，但我们可以等待所有任务完成后再操作结果。

然而，需要注意的是，`Task.WhenAll()` 缺乏内置的分区器，如果在循环中使用而没有适当的节流机制，可能会导致无限数量的任务被启动。因此，根据我们正在执行的任务数量，可能需要创建我们自己的分区策略，或选择使用 `Parallel.ForEachAsync()` 作为解决方案。

我们提到的另一件事是使用 `Task.Run()` 初始化任务。当我们想要对线程有显式控制时可以使用这种方法，但请记住，如果同时启动了太多线程，这可能会导致线程池枯竭。

## 总结

在本文中，我们将探讨两种我们用来并行执行重复任务的方法。我们了解了这两种方法如何在底层使用线程和划分给定的任务。同时，我们也看到了使用`Task.Run()`时的不同之处，以及它在两种选项中的表现如何。最后，我们将提供在不同情况下哪种方法最适用的指导。
