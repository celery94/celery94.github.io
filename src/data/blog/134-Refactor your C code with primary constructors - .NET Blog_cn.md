---
pubDatetime: 2024-05-09
tags: [".NET", "C#"]
source: https://devblogs.microsoft.com/dotnet/csharp-primary-constructors-refactoring/
author: David Pine
title: 使用C#主构造器重构你的代码 - .NET博客
description: 通过对Worker服务进行逐步重构，探索C# 12的主构造器。
---

# 使用C#主构造器重构你的代码 - .NET博客

> ## 摘录
>
> 通过对Worker服务进行逐步重构，探索C# 12的主构造器。
>
> 原文 [David Pine](https://devblogs.microsoft.com/dotnet/author/dapine/)，发表于2024年4月23日。

---

2024年4月23日

[C# 12作为.NET 8的一部分](https://learn.microsoft.com/dotnet/csharp/whats-new/csharp-12)引入了一系列引人注目的新特性！在这篇文章中，我们将探讨这些特性中的一个，特别是*主构造器*，解释其用途和相关性。然后，我们将演示一个示例重构，展示如何在你的代码中应用它，讨论优点和潜在的陷阱。这将帮助你理解变化的影响，并帮助你决定是否采用该特性。

## 主构造器 1️⃣

主构造器被认为是“日常C#”开发者的特性。它们允许你在单个简洁的声明中定义一个`class`或`struct`及其构造器。这可以帮助你减少需要编写的样板代码量。如果你一直在关注C#的版本，你可能已经熟悉了包含第一个主构造器示例的`record`类型。

### 与`record`类型的区别

[Record类型](https://learn.microsoft.com/dotnet/csharp/fundamentals/types/records)被引入作为`class`或`struct`的类型修饰符，简化了构建简单类（如数据容器）的语法。Record可以包括一个主构造器。这个构造器不仅生成一个后备字段，还为每个参数暴露了一个公共属性。与传统的`class`或`struct`类型不同，主构造器参数在类定义中处处可访问，records被设计为透明数据容器。它们固有地支持基于值的等价性，与它们作为数据持有者的预期角色相一致。因此，将它们的主构造器参数作为属性访问是合乎逻辑的。

### 重构示例✨

[.NET提供了许多模板](https://learn.microsoft.com/dotnet/core/tools/dotnet-new)，如果你曾创建过一个[Worker服务](https://learn.microsoft.com/dotnet/core/extensions/workers)，你可能已经看到了以下`Worker`类模板代码：

```csharp
namespace Example.Worker.Service
{
    public class Worker : BackgroundService
    {
        private readonly ILogger<Worker> _logger;

        public Worker(ILogger<Worker> logger)
        {
            _logger = logger;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                if (_logger.IsEnabled(LogLevel.Information))
                {
                    _logger.LogInformation("Worker运行于: {time}", DateTimeOffset.Now);
                }
                await Task.Delay(1000, stoppingToken);
            }
        }
    }
}
```

上述代码是一个简单的`Worker`服务，每秒记录一条消息。目前，`Worker`类有一个构造器，需要一个`ILogger<Worker>`实例作为参数，并将其分配给同类型的`readonly`字段。这种类型信息在两个地方出现，在构造器的定义中，也在字段本身中。这是C#代码中的一个常见模式，但是可以通过主构造器来简化。

值得一提的是，这个特定特性的重构工具在Visual Studio Code中不可用，但你仍然可以手动重构为主构造器。要在Visual Studio中使用主构造器重构此代码，你可以使用“使用主构造器（并移除字段）”重构选项。右键点击`Worker`构造器，选择“快速操作和重构...”（或按Ctrl + .），然后选择“使用主构造器（并移除字段）”。

结果代码现在类似于以下C#代码：

```csharp
namespace Example.Worker.Service
{
    public class Worker(ILogger<Worker> logger) : BackgroundService
    {
        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                if (logger.IsEnabled(LogLevel.Information))
                {
                    logger.LogInformation("Worker运行于: {time}", DateTimeOffset.Now);
                }
                await Task.Delay(1000, stoppingToken);
            }
        }
    }
}
```

就是这样，你已经成功地将`Worker`类重构为使用了主构造器！`ILogger<Worker>`字段已被移除，构造器被替换为主构造器。这使代码更加简洁，易于阅读。`logger`实例现在在整个类中都可用（因为它在作用域内），无需单独的字段声明。

## 其他考虑事项 🤔

主构造器可以移除你手写的在构造器中分配的字段声明，但有一个警告。如果你定义了字段为`readonly`，它们并不完全等价，因为对于非record类型，主构造器参数是可变的。所以，当你使用这种重构方法时，要注意你正在改变你的代码的语义。如果你想保持`readonly`行为，请使用字段声明代替，并使用主构造器参数分配字段：

```csharp
namespace Example.Worker.Service;

public class Worker(ILogger<Worker> logger) : BackgroundService
{
    private readonly ILogger<Worker> _logger = logger;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            if (_logger.IsEnabled(LogLevel.Information))
            {
                _logger.LogInformation("Worker运行于: {time}", DateTimeOffset.Now);
            }
            await Task.Delay(1000, stoppingToken);
        }
    }
}
```

## 额外的构造器 🆕

当你定义一个主构造器时，你仍然可以定义额外的构造器。然而，这些构造器需要调用主构造器。调用主构造器确保了类声明中处处初始化了主构造器参数。如果你需要定义额外的构造器，你必须使用`this`关键字调用主构造器。

```csharp
namespace Example.Worker.Service
{
    // 主构造器
    public class Worker(ILogger<Worker> logger) : BackgroundService
    {
        private readonly int _delayDuration = 1_000;

        // 次级构造器，调用主构造器
        public Worker(ILogger<Worker> logger, int delayDuration) : this(logger)
        {
            _delayDuration = delayDuration;
        }

        // 省略以简洁...
    }
}
```

添加构造器并不总是必需的。让我们做一些额外的重构，以引入一些其他特性！

## 额外重构 🎉

主构造器很棒，但我们还可以做更多工作来改进代码。

C#包含[文件作用域命名空间](https://learn.microsoft.com/dotnet/csharp/language-reference/keywords/namespace)。这是一个非常好的特性，它减少了一个嵌套级别并提高了可读性。继续使用前面的示例，在命名空间名称的末尾放置光标，然后按;键（这在Visual Studio Code中不支持，但你可以手动完成）。这将把命名空间转换为文件作用域命名空间。

经过几次额外编辑，最终重构的代码如下所示：

```csharp
namespace Example.Worker.Service;

public sealed class Worker(ILogger<Worker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            if (logger.IsEnabled(LogLevel.Information))
            {
                logger.LogInformation("Worker运行于: {time}", DateTimeOffset.Now);
            }

            await Task.Delay(1_000, stoppingToken);
        }
    }
}
```

除了重构为文件作用域命名空间外，我还添加了`sealed`修饰符，因为在多种情况下它带来了性能优势。最后，我还使用了[数字分隔符](https://learn.microsoft.com/dotnet/csharp/language-reference/builtin-types/integral-numeric-types#integer-literals)特性来更新传递给`Task.Delay`的数值字面量，以提高可读性。你知道还有很多方法可以简化你的代码吗？查看[C#中的新特性](https://learn.microsoft.com/dotnet/csharp/whats-new)以了解更多！

## 下一步 🚀

在你自己的代码中尝试这个！寻找机会重构你的代码以使用主构造器，看看它如何简化你的代码库。如果你在使用Visual Studio，检查重构工具。如果你在使用Visual Studio Code，你仍然可以手动重构。要了解更多，请探索以下资源：

- [C# 12中的主构造器](https://learn.microsoft.com/dotnet/csharp/whats-new/tutorials/primary-constructors)
- [Visual Studio: 额外的快速操作](https://learn.microsoft.com/visualstudio/ide/quick-actions?view=vs-2022)
- [Visual Studio Code: C# 快速动作和重构](https://code.visualstudio.com/docs/csharp/refactoring)
