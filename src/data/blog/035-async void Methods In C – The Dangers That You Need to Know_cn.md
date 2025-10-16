---
pubDatetime: 2024-03-08
tags: [".NET", "C#"]
source: https://www.devleader.ca/2024/03/07/async-void-methods-in-c-the-dangers-that-you-need-to-know/
author: Nick Cosentino
title: C#中的async void方法 - 你需要了解的危险
description: 通过清晰的代码示例了解为什么C#中的async void方法可能是危险的。非常适合希望了解风险的初学者软件工程师。
---

# C#中的async void方法 - 你需要了解的危险

> ## 摘要
>
> 通过清晰的代码示例了解为什么C#中的async void方法可能是危险的。非常适合希望了解风险的初学者软件工程师。
>
> 原文 [Async Void Methods In C# – The Dangers That You Need To Know](https://www.devleader.ca/2024/03/07/async-void-methods-in-c-the-dangers-that-you-need-to-know/)

---

`async void`方法在C#中是许多开发者在[编写async await代码](https://www.devleader.ca/2024/02/27/async-await-in-c-3-beginner-tips-you-need-to-know/ "C#中的async await: 你需要知道的3个初学者技巧")时遇到的问题来源。我们被建议使用的模式当然是`async Task`，但在某些情况下——比如C#中的事件处理器——方法签名就是不兼容。

在本文中，我将解释为什么C#中的`async void`方法是你想要避免的东西。我们将通过比较`async void`和`async Task`的代码示例来更好地理解，并且我还会解释如果你别无选择只能使用`async void`该怎么办。

---

## C#中什么是async void方法？

在C#中，`async void`方法是一种定义不返回值的异步方法的方式。这些方法通常用于事件处理器或其他情况，其中强制方法签名不支持`Task`返回类型，而是强制`void`。

`async void`方法通过在方法签名前使用`async`关键字，后跟返回类型`void`来定义。例如：

```csharp
public async void SomeMethod()
{
    // 这里是代码
}
```

与返回`Task`或`Task<T>`的常规异步方法相比，有几个重要的区别需要注意。而当我说“重要”时，我的意思是“你真的需要尽可能地避免这样做，以免给自己带来头痛”。

### CSharp中async void与async Task的区别

`async void`方法和`async Task`方法之间的主要区别之一在于异常处理方式。

在`async Task`方法中，发生的任何异常都会被返回的`Task`对象捕获。这允许调用代码处理异常或等待`Task`以后观察任何异常。这就是C#中整个async await基础架构如何构建的原因。这经常是你会看到async await被引入到代码库中，然后所有的调用代码开始转换为也是async await的原因——你真的需要它在那里。

另一方面，`async void`方法不能被直接等待，任何在其中发生的异常将会冒泡到……哪里？最初启动异步方法的SynchronizationContext。即使[来自Microsoft的Stephen Cleary在他的文章中提到](https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming "Async/Await - 最佳异步编程实践")：

> 对于async void方法，没有Task对象，因此从async void方法抛出的任何异常将直接在启动async void方法时活动的SynchronizationContext上抛出。**图2**演示了从async void方法抛出的异常无法自然捕获的情况。
>
> **[Stephen Cleary](https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming "Async/Await - 最佳异步编程实践")**

### async Task与async void方法的代码示例对比

通过比较使用这些模式的相同代码布局的两种变化来看看问题如何出现会很有帮助。考虑以下使用async Task的示例：

```csharp
public async Task ProcessDataAsync()
{
    // 一些异步操作
}

public async void HandleButtonClick(object sender, EventArgs e)
{
    try
    {
        await ProcessDataAsync();
    }
    catch (Exception ex)
    {
        // 处理异常
    }
}
```

在这段代码中，如果`ProcessDataAsync`事件处理器方法中发生异常，它将被`HandleButtonClick`方法中的try-catch块捕获，并可以适当处理。然而，如果`HandleButtonClick`事件处理器方法被定义为`` `async void` ``，那么`ProcessDataAsync`抛出的任何异常都会绕过catch块并可能导致应用程序崩溃：

```csharp
public async void ProcessDataAsync()
{
    // 一些异步操作
}

public async void HandleButtonClick(object sender, EventArgs e)
{
    try
    {
        ProcessDataAsync();
    }
    catch (Exception ex)
    {
        // 这永远不会捕获异步异常！
    }
}
```

---

本文你可能注意到的共同主题是，C#中的`async void`方法是危险的，你应该尽量避免使用。以下是我们遇到的一些`async void`方法的挑战，希望能让你远离它们（除非别无选择）：

1.  **错误传播**：`async void`方法不允许错误被捕获或传播。当发生异常时，异常逃逸到同步上下文，通常导致未处理的异常，可能会崩溃应用程序。
2.  **等待行为**：与`async Task`方法不同，`async void`方法不能被等待。这可能导致控制异步操作流程的问题，可能引起竞态条件或以意外的顺序执行操作。
3.  **调试难度**：调试`async void`方法中的异常更加困难，因为调用堆栈可能无法准确地表示抛出异常时的执行流，使识别和修复错误的过程复杂化。

---

## 处理C#中async void方法的最佳实践

[在处理C#中的async void方法时，认识到它们的潜在危险并遵循最佳实践以确保健壮可靠的代码库是很重要的](https://www.devleader.ca/2023/01/27/async-void-how-to-tame-the-asynchronous-nightmare/ "async void — 如何驯服异步噩梦")。以下是谨慎处理async void方法的一些建议：

1.  尽可能避免使用`async void`：`async void`方法通常应该被避免，特别是在异常处理和错误恢复至关重要的场景中。[虽然async void方法看起来方便，但它们缺乏传播异常的能力，可能导致不可预测的程序行为](https://www.devleader.ca/2023/01/27/async-void-how-to-tame-the-asynchronous-nightmare/ "async void — 如何驯服异步噩梦")。相反，考虑使用`async Task`方法，这可以提供更好的错误处理能力。
2.  使用`async Task`：通过使用`async Task`返回类型来异步方法，你可以利用Task内置的异常处理机制。这使你能够适当地捕获和处理异常，确保你的代码保持对执行流程的控制。使用`async Task`方法还允许更好的代码可维护性、可测试性和比`async void`更少的神秘问题。
3.  处理`async void`方法中的异常：如果你必须使用`async void`方法，重要的是要正确处理异常，以防止它们悄无声息地传播并导致意外的系统行为。一种实现[方法是将代码包含在try/catch块中](https://www.devleader.ca/2023/02/14/async-eventhandlers-a-simple-safety-net-to-the-rescue/ "Async事件处理器 - 救命的简单安全网")。在catch块中，你可以记录异常并相应地处理它，比如向用户显示错误消息或回滚任何相关操作。
4.  记录和监控异步操作：使用`async void`方法时，日志记录和监控变得更加关键。由于这些方法没有返回类型，确定它们的完成或识别任何潜在问题变得挑战。实施健壮的日志记录和监控系统，例如使用Serilog等日志框架或利用应用洞察，可以帮助跟踪异步操作的进展和状态，帮助调试和故障排除。

### 对C#中的async void方法使用Try/Catch

[我之前写过尝试使用这种代码的几种不同方式](https://www.devleader.ca/2023/02/14/async-eventhandlers-a-simple-safety-net-to-the-rescue/ "Async事件处理器 - 救命的简单安全网")，但最后看来确保在每个`async void`方法体中使用try/catch包围似乎是最直接的。也许有人可以创建一个Rosyln分析器来强制执行这个？

以下是演示如何在整个`async void`代码体中使用try-catch的示例：

```csharp
public async void DoSomethingAsync()
{
    try
    {
        // 执行异步操作
        await Task.Delay(1000);
        await SomeAsyncMethod();
    }
    catch (Exception ex)
    {
        // TODO: ... 无论你需要做什么来正确报告
        // 在你的async void调用中的问题，以便你
        // 可以更有效地调试它们。

        // 记录异常并适当处理
        Logger.Error(ex, "执行DoSomethingAsync时出错");
        // 显示错误消息或采取必要行动
        DisplayErrorMessage("哎呀！出了些问题。请稍后再试。");
    }
}
```

通过遵守这些最佳实践，你可以减少与`async void`方法相关的风险，并避免一堆没完没了的头痛。记住，尽可能优先使用`async Task`方法以实现更好的异常处理和对异步执行流程的控制——除非绝对必要，*真的*不要添加`async void`。

---

## C#中async void方法的总结

总之，C#中的`async void`方法因几个原因可能是危险的，你会想要优先不使用它们。有不幸的情况是，API和方法签名不一致，例如事件处理器，但除此之外，尽力避免使用这些。

通过使用`async void`，[我们失去了适当等待或处理异常的能力](https://www.devleader.ca/2023/01/27/async-void-how-to-tame-the-asynchronous-nightmare/ "async void — 如何驯服异步噩梦")。这可能导致未处理的异常和我们代码中的意外行为。为了避免这些风险，我建议尽可能使用`async Task`方法，让我们能够等待结果、处理异常，并更好地控制代码的执行流。它促进了更好的错误处理并提高了整体代码质量。当别无选择时，[确保你包围了整个async void方法的try/catch](https://www.devleader.ca/2023/02/14/async-eventhandlers-a-simple-safety-net-to-the-rescue/ "Async事件处理器 - 救命的简单安全网")，并投入适当的错误处理/记录/报告。

谨慎地对待异步编程，并不断寻求加深你对该主题的理解！如果你觉得这有用，而且你正在寻找更多的学习机会，考虑[订阅我的免费每周软件工程简报](https://subscribe.devleader.ca/ "订阅Dev Leader Weekly")，并查看我在[YouTube上的免费视频](https://www.youtube.com/@devleader?sub_confirmation=1 "Dev Leader - YouTube")！[如果你想与我和其他软件工程师就这些主题交流，请查看我的Discord社区](https://www.devleader.ca/discord-community-access/ "Discord社区访问")！

---

## 常见问题解答：C#中的async void方法

### 什么是async void方法？

C#中的async void方法是使用async关键字但具有void返回类型的方法。它们通常用于事件处理器或顶级入口点。

### async void方法与async Task方法有什么区别？

主要区别在于异常处理方式。async void方法不允许适当的异常处理，如果未捕获异常，可能导致应用程序崩溃。另一方面，async Task方法允许更好的错误处理和异常传播。

### 使用async void方法的危险是什么？

使用async void方法可能导致未处理的异常，进而导致应用程序崩溃。缺乏错误处理和异常传播使得从失败中恢复和处理变得困难。

### 为什么应该优先选择async Task而不是async void？

async Task方法提供更好的错误处理和异常传播控制。它们还允许更容易地组合异步操作，并使从失败中恢复和处理变得更加容易。

### 处理async void方法的最佳实践是什么？

建议尽可能避免使用async void方法。相反，应使用async Task方法。如果必须使用async void方法，则应实现适当的异常处理，例如使用try/catch块，并应到位异步操作的日志记录和监控。
