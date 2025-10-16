---
pubDatetime: 2024-02-29
tags: [".NET", "C#", "AI"]
source: https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/
author: Nick Cosentino
title: async await 在 C# 中：3 个初学者必知的提示
description: 通过这三个初学者提示深入了解 C# 中的 async await。学习如何编写 async await 代码，处理多个异常，并避免可怕的死锁！
---

# async await 在 C# 中：3 个初学者必知的提示

> ## 摘录
>
> 通过这三个初学者提示深入了解 C# 中的 async await。学习如何编写 async await 代码，处理多个异常，并避免可怕的死锁！
>
> 原文：[Async Await In C#: 3 Beginner Tips You Need To Know](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/)

---

Async await 在 C# 中是一个特性，允许你编写易于阅读和维护的异步代码。它极大简化了你通过提供一个结构化的方式来等待任务及其结果来处理异步操作的方式。随着电脑在性能和核心数量上的扩展，以及我们与许多外部服务互操作的日益增长的需求，async await 在 C# 中可以让我们的开发工作变得更容易。

在接下来的几个部分，我将突出介绍使用 C# 中的 async await 的 3 个初学者提示。每个提示都会配有一个代码示例，让你看到这些概念的实际应用。这些[提示将涵盖错误处理、](https://www.devleader.ca/2023/10/22/how-to-handle-exceptions-in-csharp-tips-and-tricks-for-streamlined-debugging/)取消和性能优化等重要方面，因此你将开始编写异步代码。

---

## 本文内容：C# 中的 async await

- [提示 1：了解 C# 中 async await 的基础](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-tip-1-understand-the-basics-of-async-await-in-c)
- [提示 2：使用 async await 处理多个异常](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-tip-2-proper-exception-handling-with-async-await)
- [提示 3：使用 async await 避免死锁](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-tip-3-avoiding-deadlocks-with-async-await)
  - [停止阻塞你的异步调用！](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-stop-blocking)
  - [在 C# 中使用 ConfigureAwait(false) 和 Async Await](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-using-configureawaitfalse)
- [结论](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-conclusion)
- [常见问题解答：C# 中的 async await](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-frequently-asked-questions-async-await-in-c)
  - [C# 中的 async await 用途是什么？](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-what-is-the-purpose-of-understanding-async-await-in-c)
  - [如何在 C# 中定义一个异步方法？](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-how-do-you-define-an-async-method-in-c)
  - [在 C# 中 'await' 关键字的目的是什么？](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-what-is-the-purpose-of-the-await-keyword-in-c)
  - [如何处理 async await 代码中的异常？](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-how-can-you-handle-exceptions-in-async-await-code)
  - [在 async await 代码中 'ConfigureAwait(false)' 的目的是什么？](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-what-is-the-purpose-of-configureawaitfalse-in-async-await-code)
  - [C# 中的 Task 是什么？](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/#aioseo-what-is-a-task-in-c)

---

## 提示 1：了解 C# 中 async await 的基础

在 C# 中，async await 是两个特殊的关键字，用于处理异步代码执行。异步编程能够让我们编写 C# 代码，它可以同时进行多个操作，提高应用程序的整体性能和响应能力。在 C# 中，一个任务代表了一个异步操作，它被用来封装一个可能[与其他任务并发执行的工作单元](https://www.devleader.ca/2023/01/22/tasks-backgroundworkers-and-threads-simple-comparisons-for-concurrency/)。当使用 async/await 时，你可以使用任务以一种结构化的方式处理和管理异步操作。

要在 C# 中定义一个异步方法，你需要在方法签名中添加 async 修饰符。例如：

```
public async Task DoAsyncWork()
{
    // Asynchronous code here
}
```

在上面的示例中，方法 `DoAsyncWork` 被声明为异步并返回一个 `Task`。这表明该方法将执行异步操作，并且可以被等待。

在异步方法中，你可以使用 await 关键字来标示执行应该等待异步操作完成的点。例如：

```
public async Task DoAsyncWork()
{
    // 执行异步操作
    await Task.Delay(1000);

    // 继续其他操作
}
```

在上面的示例中，`await Task.Delay(1000)` 语句将暂停该方法的执行，直到 `Task.Delay` 操作完成。这允许其他代码，如其他异步任务，同时执行。通过使用任务，你可以 [利用 C# 中的异步编程能力](https://www.devleader.ca/2024/01/31/custom-middleware-in-asp-net-core-how-to-harness-the-power/)。

---

## 提示 2：使用 async await 处理多个异常

[异常处理是编写任何软件应用程序的重要方面](https://www.devleader.ca/2023/10/22/how-to-handle-exceptions-in-csharp-tips-and-tricks-for-streamlined-debugging/ "如何用 CSharp 处理异常 – 为流线型调试提供的技巧与窍门")。在 C# 中处理异步代码时，由于代码的异步性质，可能会遇到一些挑战。在某些情况下，在执行异步代码时可能会发生多个异常。能够有效地处理和聚合这些异常非常重要。为了处理多个异常，C# 提供了 `AggregateException` 类，它允许我们将多个异常作为一个实体进行分组和管理。

当多个异常在异步操作中发生时，`AggregateException` 类收集这些异常，并允许我们集中访问和处理它们。这对于我们需要在异步操作期间处理所有生成的异常的场景特别有用。为了使用 `AggregateException` 类处理异常，我们可以将可能抛出异常的代码包裹在一个 try-catch 块中。在 catch 块中，我们可以访问 `AggregateException` 的 `InnerExceptions` 属性，以访问发生的每个单独异常。

以下是如何使用 `AggregateException` 类在异步代码中处理和聚合异常的示例：

```
try
{
    await SomeAsyncOperation();
}
catch (AggregateException ex)
{
    foreach (var innerException in ex.InnerExceptions)
    {
        // 处理每个单独异常
        Console.WriteLine($"Exception: {innerException.Message");
    }
}
```

在上面的示例中，`SomeAsyncOperation` 表示可能抛出一个或多个异常的异步操作。通过在 try-catch 块中包裹 `await` 语句并捕获一个 `AggregateException`，我们能够访问和处理在异步操作中发生的每一个单独异常。通过使用 `AggregateException` 类正确处理和聚合异步代码中的异常，我们可以确保我们的代码可以优雅地处理在异步操作期间可能发生的任何预期之外的错误。

---

## 提示 3：使用 async await 避免死锁

死锁可能发生在两个或多个任务无限期地等待彼此完成，导致没有任务可以继续进行的状态。

### 停止阻塞你的异步调用！

在异步方法中导致死锁的最常见原因之一包括在异步方法内部使用 `Task.Result` 或 `Task.Wait` 方法，这会阻塞主线程并可能导致死锁。避免异步代码死锁的最好建议是：

> “不要在异步代码上阻塞”
>
> [Stephen Cleary](https://blog.stephencleary.com/2012/07/dont-block-on-async-code.html "不要阻塞异步代码")

他在他的文章中指出，停止阻塞这个提示（stop blocking）或紧接这个提示的提示（配置 awaiter）都能帮助预防死锁……但仅仅依赖于下一个模式会有更多风险。也就是说，在这两个建议中，让你的 C# 代码全程都使用 async await 是更安全的选择。

这意味着我们不会有类似于以下的情况：

```
public class MyController(
  IWeatherService _weatherService) :
  ApiController
{
  public string GetWeatherData()
  {
    var weatherData = _weatherService.GetWeatherData(...).Result;
    return Results.OK(weatherData);
  }
}
```

相反，我们会使顶层也是异步的：

```
public class MyController(
  IWeatherService _weatherService) :
  ApiController
{
  public async Task<string> GetWeatherData()
  {
    var weatherData = await _weatherService.GetWeatherData(...);
    return Results.OK(weatherData);
  }
}
```

只要我们引入 `.Result` 或 `.Wait()` 调用，我们就实际上在阻塞 — 并且在应用程序变得更为复杂时，这是可能导致死锁的关键情况之一。

### 在 C# 中使用 ConfigureAwait(false) 和 Async Await

为了防止死锁，可以使用带有 `false` 参数的 `ConfigureAwait` 方法。这指示 `await` 操作符不捕获当前的同步上下文，允许继续操作在来自线程池的任何可用线程上执行 — 不仅仅是开始调用的线程！

使用 `ConfigureAwait(false)`，我们可以明确指出我们不需要捕获原始同步上下文，从而预防死锁问题。请记住，只有在绝对必要的情况下才应使用 `ConfigureAwait(false)`，因为如果代码依赖于捕获的同步上下文来满足特定的需求，这可能会引入潜在的问题。例如，如果你正在运行 UI 逻辑，并且你回到执行时不在 UI 线程上，你可能会遇到一些意外！

让我们看一个例子来说明使用 `ConfigureAwait(false)` 来防止死锁：

```
public async Task<string> GetDataAsync()
{
    // 注意：假设我们在某个给定的线程上进入这个方法

    // 在 ConfigureAwait 上使用 false 参数
    await SomeAsyncMethod().ConfigureAwait(false);

    // 注意：我们可能会在与开始这个方法时不同的线程上！

    return ProcessData();
}
```

在上面的示例中，通过使用 `ConfigureAwait(false)` 来等待 `SomeAsyncMethod`。这允许代码的继续执行在任何可用的线程上，确保不捕获同步上下文并防止潜在的死锁。

同时 Stephen Cleary 也说了这将帮助预防死锁，他还补充说：

> 使用 `ConfigureAwait(false)` 来避免死锁是一种危险的做法。你必须对由阻塞代码调用的所有方法的传递闭包中的 _每一个_ `await` 使用 `ConfigureAwait(false)`， _包括所有第三方和第二方代码_。使用 `ConfigureAwait(false)` 来避免死锁最多就是[一种权宜之计](https://msdn.microsoft.com/en-us/magazine/mt238404.aspx?WT.mc_id=DT-MVP-5000058))。
>
> [Stephen Cleary](https://blog.stephencleary.com/2012/07/dont-block-on-async-code.html)

---

## 结论

在这篇文章中，我讨论了使用 C# 中的 async await 编写并发代码的 3 个初学者提示。Async await in C# 可能一开始会有点难以吸收，所以你需要一些时间和实践才会感到更自然！

我们已经看到了异步等待关键字使用的基础 — 有了这些，你现在可以编写异步代码了！从那里，我们看了在异步等待代码路径中如何出现多个异常，并如何导航它。我们最后总结了一些通过两种可能性来预防死锁的想法。

在 C# 中学习和实践 async await 是你渴望了解和练习的事情！如果你觉得这很有用，并且你正在寻找更多的学习机会，考虑[订阅我的免费每周软件工程通讯](https://subscribe.devleader.ca/ "订阅开发领袖周刊")，并查看我在 [YouTube 上的免费视频](https://www.youtube.com/@devleader "开发领袖 - YouTube")！

---

## 常见问题解答：C# 中的 async await

### C# 中的 async await 用途是什么？

了解 C# 中的 async await 对于有效处理异步操作并创建更流畅、更响应迅速的代码很重要。

### 如何在 C# 中定义一个异步方法？

在 C# 中，异步方法是通过在方法签名中使用 'async' 关键字并指定返回类型为 'Task' 或 'Task<T>' 来定义的，其中 'T' 代表返回值的类型。

### 在 C# 中 'await' 关键字的目的是什么？

'await' 关键字的目的是标示一个异步操作完成，代码才可在该点继续执行。

### 如何处理 async await 代码中的异常？

可以像同步代码一样使用 try-catch 块处理 async await 代码中的异常。然而，需要仔细考虑如何在处理嵌套任务时正确处理异常。

### ‘ConfigureAwait(false)’ 在异步等待代码中的目的是什么？

‘ConfigureAwait(false)’ 被用来指定一个异步方法不需要回到它被调用的原始上下文中继续执行，这在某些情况下可以避免死锁。

### 在 C# 中什么是 Task？

在 C# 中，Task 代表一个可能返回结果或不返回结果的异步操作。它提供了一种管理和等待异步操作完成的方式。
