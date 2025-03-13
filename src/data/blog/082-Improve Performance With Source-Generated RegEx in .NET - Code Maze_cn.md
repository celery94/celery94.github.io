---
pubDatetime: 2024-04-06
tags: [C#, .NET, RegEx, Source-Generated, Performance]
source: https://code-maze.com/csharp-improve-performance-with-source-generated-regex/
author: Ivan Gechev
title: 使用Source-Generated的RegEx在.NET中提高性能
description: 在本文中，我们将探讨Source-Generated的RegEx及其如何在我们的.NET应用程序中提高性能。
---

> ## 摘录
>
> 在本文中，我们将探讨Source-Generated的RegEx及其如何在我们的.NET应用程序中提高性能。
>
> 原文 [Improve Performance With Source-Generated RegEx in .NET](https://code-maze.com/csharp-improve-performance-with-source-generated-regex/)

---

在这篇文章中，我们将探讨代码生成的RegEx及其如何在我们的.NET应用程序中提高性能。

要下载本文的源代码，您可以访问我们的[GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/dotnet-performance/ImprovePerformanceWithSourceGeneratedRegEx)。

## RegEx是如何工作的？

正则表达式对编程世界至关重要，但我们知道它们在.NET中是如何工作的吗？

让我们来看一个例子：

```csharp
public static class PasswordValidator
{
    public static bool ValidatePasswordWithRegularRegEx(string password)
    {
        var regex = new Regex(@"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\da-zA-Z]).{8,}$");
        return regex.IsMatch(password);
    }
}
```

在`ValidatePasswordWithRegularRegEx()`方法内，我们通过向构造函数传递一个模式来创建`Regex`类的新实例。我们可以使用这个模式来验证密码是否至少为8个字符长。它还检查密码是否至少包含一个：小写字母、大写字母、数字和特殊字符。

当我们使用`Regex`类的构造函数或其一种静态方法时，会发生几件事。首先，编译器解析我们传递的模式以确保其有效性。然后将模式转换为该模式的节点树表示。接下来，将树转换为内部`RegexInterpreter`引擎可以解释的一组指令。最后，当我们尝试根据该模式匹配某些内容时，内部正则表达式解释器会遍历这些指令并将它们与输入进行比较。

## 编译过的RegEx是如何工作的？

在.NET中，我们还有一个使用编译过的RegEx的选项：

```csharp
public static bool ValidatePasswordWithCompiledRegEx(string password)
    => Regex.IsMatch(
        password,
        @"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\da-zA-Z]).{8,}$",
        RegexOptions.Compiled);
```

我们创建了`ValidatePasswordWithCompiledRegEx()`方法，并使用静态的`IsMatch()`方法返回一个结果。向该方法中传递我们希望验证的密码、模式，并使用`RegexOptions.Compiled`枚举值，我们指定我们的应用程序必须使用编译过的正则表达式。

当我们这样做时，直到为`RegexInterpreter`引擎生成指令的步骤都将是相同的。但然后，编译器将进一步处理这些指令，并首先将它们转换成IL指令，然后转换成多个`DynamicMethod`实例。因此，当我们尝试进行匹配时，编译器不会使用解释器，而是执行这些`DynamicMethod`实例。**这使得匹配输入更快，但由于我们需要执行额外的操作，因此成本更高。**

随着.NET 7的推出，我们获得了一种新的使用正则表达式的方式：

```csharp
public static partial class PasswordValidator
{
    public static bool ValidatePasswordWithSourceGeneratedRegEx(string password)
        => PasswordRegEx().IsMatch(password);
    [GeneratedRegex(@"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\da-zA-Z]).{8,}$")]
    private static partial Regex PasswordRegEx();
}
```

我们创建了返回`Regex`实例的部分方法`PasswordRegEx()`。接下来，我们用`GeneratedRegex`属性对该方法进行装饰。然后，我们也将我们的类标记为`partial`。最后，我们创建了`ValidatePasswordWithSourceGeneratedRegEx()`方法并返回`IsMatch()`方法调用的结果，该结果我们从`PasswordRegEx()`方法中获取。

当我们在返回`Regex`实例的`partial`方法上使用`GeneratedRegex`属性时，内部源代码生成器会识别到这一点，并在幕后提供所有必要的逻辑。

> 如果你想了解更多关于源代码生成器及其如何工作的信息，你可以查看我们的文章[源代码生成器在C#中的应用](https://code-maze.com/csharp-source-generators/)。

### 在.NET中源生成的RegEx如何提高性能？

通过源生成的代码，我们可以进行检查：

```csharp
/// <summary>缓存的，线程安全的单例实例。</summary>
internal static readonly PasswordRegEx_0 Instance = new();

/// <summary>初始化实例。</summary>
private PasswordRegEx_0()
{
    base.pattern = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[^\\da-zA-Z]).{8,}$";
    base.roptions = RegexOptions.None;
    ValidateMatchTimeout(Utilities.s_defaultTimeout);
    base.internalMatchTimeout = Utilities.s_defaultTimeout;
    base.factory = new RunnerFactory();
    base.capsize = 1;
}
```

最显眼的一点是，我们现在得到了一个内部的线程安全实例，它也被缓存了。源代码生成器不仅仅是初始化一个新的`Regex`实例。它产生的代码在很多方面都类似于当我们使用`RegexOptions.Compiled`时编译器产生的代码。我们得到了编译过的正则表达式的所有好处，以及一些启动相关的好处。

此外，代码与编译器产生的`DynamicMethod`实例非常相似。然后由编译器负责将生成的代码转换为IL代码，这可以带来进一步的优化和性能提升。例如，如果生成的代码产生了一个`switch`语句，那么编译器就有很多方法可以在生成的IL代码中改进它。这是当我们实例化或使用静态`Regex`方法时无法获得的。

## 测量源生成的RegEx的性能提升

让我们开始安装BenchmarkDotnet包：

```bash
dotnet add package BenchmarkDotnet
```

然后，让我们创建我们的基准测试类：

```csharp
[MemoryDiagnoser(true)]
[Config(typeof(StyleConfig))]
public class RegexBenchmarks
{
    private const string Password = "c0d3-MaZ3-Pa55w0rd";
    [Benchmark(Baseline = true)]
    public void RegularRegex()
        => PasswordValidator.ValidatePasswordWithRegularRegEx(Password);
    [Benchmark]
    public void CompiledRegex()
        => PasswordValidator.ValidatePasswordWithCompiledRegEx(Password);
    [Benchmark]
    public void SourceGeneratedRegex()
        => PasswordValidator.ValidatePasswordWithSourceGeneratedRegEx(Password);
    private class StyleConfig : ManualConfig
    {
        public StyleConfig()
            => SummaryStyle = SummaryStyle.Default.WithRatioStyle(RatioStyle.Trend);
    }
}
```

首先，我们创建了`RegexBenchmarks`类。然后，我们用`MemoryDiagnoser`和`Config`属性对其进行了装饰。通过前者我们将衡量[内存分配](https://code-maze.com/csharp-memory-allocation-optimization-with-benchmarkdotnet/)，而后者将向我们展示与使用`RegularRegex()`相比改进的比率。

剩下最后一步：

```csharp
BenchmarkRunner.Run<RegexBenchmarks>();
```

在我们的`Program`类中，我们注册了基准测试类，并将我们的应用程序设置为*Release*模式。

接下来，让我们运行基准测试：

| 方法                 |        均值 |      错误 |     标准差 |          比率 |   Gen0 |   Gen1 | 分配的内存 |
| -------------------- | ----------: | --------: | ---------: | ------------: | -----: | -----: | ---------: |
| RegularRegex         | 3,951.07 ns | 78.745 ns | 135.831 ns |      baseline | 0.9918 | 0.0153 |     6288 B |
| CompiledRegex        |    85.42 ns |  0.263 ns |   0.233 ns | 47.45x faster |      - |      - |          - |
| SourceGeneratedRegex |    71.34 ns |  0.358 ns |   0.299 ns | 56.71x faster |      - |      - |          - |

当我们看到结果时，我们看到使用新的`Regex`实例的方法的执行时间为*3,951.07纳秒*，这也是我们的基准。它分配了*6288字节*的内存，并且是三种方法中最慢的。

第二位，我们有编译过的RegEx方法，运行时间为*85.42纳秒*，比基准方法快47.45倍，且没有内存分配。

**最后，我们有源生成的方法，比编译的方法快约*14纳秒*。** 使用它，我们也看到与我们的基准相比，RegEx性能提高了56倍。

## 结论

在本文中，我们探讨了在.NET应用程序中使用源生成的RegEx以提高性能的利用方法。当比较传统的RegEx初始化、编译过的RegEx和源生成的RegEx时，我们看到有显著的性能差异。编译过的RegEx方法展示了明显的速度提升，比传统的RegEx使用快约47倍。然而，源生成的RegEx方法甚至超过了这一点，展示了约5600%的惊人速度改进。这些发现强调了在优化我们的.NET应用程序性能方面，源生成的RegEx的潜在性能增加潜力。
