---
pubDatetime: 2024-04-06
tags: [".NET", "C#"]
source: https://www.devleader.ca/2024/04/01/regex-options-in-csharp-beginners-guide-to-powerful-pattern-matching/
author: Nick Cosentino
title: C#中的Regex选项，模式匹配的初学者指南
description: 正则表达式对于模式匹配非常强大，但我们可以访问的C#中的regex选项是什么？它们有何作用，我们如何使用它们？
---

> ## 摘要
>
> 正则表达式对于模式匹配非常强大，但我们可以访问的C#中的regex选项是什么？它们有何作用，我们如何使用它们？
>
> 原文 [Regex Options in C# – A Beginner’s Guide to Powerful Pattern Matching](https://www.devleader.ca/2024/04/01/regex-options-in-csharp-beginners-guide-to-powerful-pattern-matching/)

---

正则表达式在匹配字符串模式和给开发人员头疼方面都非常强大。有些日子，我不确定它们做得更好的是什么！在C#中，当我们使用正则表达式时，我们可以使用一些方法，但我们也可以配置正则表达式来表现不同。在本文中，我们将一起查看C#中的regex选项，通过查看我们可以访问的一些初级regex方法，然后看到这些regex选项在行动中。

而且别担心：不仅有你可以复制和粘贴的代码示例，而且由于DotNetFiddle的帮助，你还可以直接在浏览器中尝试它们。

---

## 什么是正则表达式？

正则表达式，通常称为regex，是用于文本中模式匹配的强大工具。它们允许你定义一个搜索模式，可以用来查找、替换或操作字符串的特定部分。正则表达式提供了一种简洁和灵活的方式来搜索和识别文本数据中的特定模式。

在软件工程中，正则表达式特别适用于数据验证、文本解析和模式提取等任务。它们可以在广泛的场景中使用，包括Web开发、数据处理和文本分析。正则表达式可以通过提供更有效、更可靠的文本操作方法来节省你的时间和精力。

以下是一些你可以考虑使用正则表达式的实际示例：

1.  **验证电子邮件地址**：假设你正在开发一个Web应用程序，要求用户在注册过程中提供有效的电子邮件地址。使用正则表达式，你可以快速验证用户提供的电子邮件地址是否符合标准格式，确保其正确性再进行进一步处理。
2.  **搜索和替换文本**：想象你有一个大型文档，需要用另一个单词或短语替换文档中的所有特定单词或短语。而不是手动搜索整个文档，你可以使用正则表达式高效、准确地执行替换任务。
3.  **从文本中提取数据**：假设你有一个包含数据行的日志文件，但你只对检索特定信息感兴趣，例如时间戳或错误消息。正则表达式使你能够通过识别日志条目中的模式来提取相关数据，节省你在分析和排除问题时的宝贵时间。

这些只是几个可以在你的应用程序中利用正则表达式的示例。在C#中，.NET框架提供了一个regex库，为我们提供了匹配我们感兴趣的所有类型字符串的能力。在接下来的部分中，我将提供如何在C#中使用正则表达式的代码示例。

---

## 在C#中开始使用正则表达式

想要在C#中使用正则表达式，你需要了解如何创建和使用Regex对象，它是System.Text.RegularExpressions命名空间的一部分。因此，首先，让我们将这个命名空间包含在你的C#代码中。可以通过在C#文件顶部添加以下using语句来实现：

```csharp
using System.Text.RegularExpressions;
```

包含了命名空间后，你可以创建一个Regex对象来代表你的正则表达式模式。Regex类提供了各种构造函数，允许你指定模式及任何附加选项 — 但我们现在只会先从默认的C# regex选项开始。例如，要创建一个匹配字符串中“hello”单词的Regex对象，你可以使用以下代码：

```csharp
Regex regex = new Regex("hello");
```

### 使用Regex.Match in C#

创建了Regex对象后，你可以使用其方法在字符串上执行模式匹配操作。最常用的方法是 `Match`，它在给定字符串中搜索模式的第一次出现。这里有一个基本示例，演示如何在C#中使用正则表达式进行模式匹配：

```csharp
using System;
using System.Text.RegularExpressions;

string input = "Hello, World!";
Regex regex = new Regex("Hello");
Match match = regex.Match(input);

if (match.Success)
{
    Console.WriteLine($"Pattern found: {match.Value}");
}
else
{
    Console.WriteLine("Pattern not found.");
}
```

在这个示例中，我们创建了一个Regex对象来匹配单词“Hello”，然后使用`Match`方法在输入字符串“Hello, World!”中搜索匹配项。`Match`方法返回一个`Match`对象，它包含模式的第一次出现的信息。我们可以使用`Success`属性检查是否找到了匹配项，使用`Value`属性检索匹配的字符串。

你可以查看[这个dotnetfiddle来运行这个C# regex示例](https://dotnetfiddle.net/MnMJzL "DotNetFiddle - Regex")，直接在浏览器中！

### 使用Regex.Matches in C#

如果我们想匹配输入字符串中的多个部分呢？这就是`Matches`方法发挥作用的地方，它还会给我们提供一个`MatchCollection`返回类型来处理。让我们看看它如何操作：

```csharp
using System;
using System.Text.RegularExpressions;

string input = "Hello, World!";
Regex regex = new Regex("Hello");
MatchCollection matches = regex.Matches(input);

if (matches.Count &gt; 0)
{
Console.WriteLine("Pattern(s) found:");
foreach (Match match in matches)
{
Console.WriteLine($"\t {match.Value}");
}
}
else
{
    Console.WriteLine("Pattern not found.");
}
```

你可以在上面的示例中看到，如果我们可以枚举匹配集合，而不仅仅是处理单个。如果你想自己尝试并实验，你可以[使用这个dotnetfiddle来运行C#中的Regex.Matches示例](https://dotnetfiddle.net/jXDGrz "Regex.Matches in C# - DotNetFiddle")：

---

## C#中的各种Regex选项

在C#中使用正则表达式时，有几个选项可以用来修改模式匹配的行为。这些选项由`RegexOptions`枚举在C#中定义。[因为这是一个标志枚举](https://www.devleader.ca/2023/11/15/enums-in-csharp-a-simple-guide-to-expressive-code/ "CSharp中的枚举 – 简单指南到表达性代码")，我们可以组合不同的枚举值来混合和匹配这些C# regex选项，以获得我们想要的行为。

让我们更仔细地看看一些常用选项，并了解它们在不同场景中的用途，以便你可以做出明智的决策并更有效地利用C#中的regex！

### RegexOptions.Compiled

此选项通过将正则表达式模式预编译成程序集来改善性能。当反复使用相同的正则表达式模式时，它尤其有用。通过一次编译模式，后续匹配可以更高效地执行。要使用此选项，只需在创建Regex对象时添加RegexOptions.Compiled作为参数即可。

让我们考虑一个示例，我们可以使用BenchmarkDotNet对使用此选项或不使用此选项的结果进行基准测试：

```csharp
using System;
using System.Text.RegularExpressions;

using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Running;

[MemoryDiagnoser]
[ShortRunJob]
public sealed class EmailValidationBenchmark
{
    // 注意：你可以（也应该）扩展这个示例
    // 试试所有类型的电子邮件和电子邮件集合
    private const string TestEmail = "example@example.com";
    private const string Pattern = @"^[a-zA-Z0-9\._\+-]+@[a-zA-Z0-9\.-]+\.[a-zA-Z]{2,}$";

    private static readonly Regex EmailRegexCompiled = new Regex(
        Pattern,
        RegexOptions.Compiled
    );

    private static readonly Regex EmailRegexNonCompiled = new Regex(
        Pattern
    );

    [Benchmark]
    public bool ValidateEmailWithCompiledOption()
    {
        return EmailRegexCompiled.IsMatch(TestEmail);
    }

    [Benchmark(Baseline = true)]
    public bool ValidateEmailWithoutCompiledOption()
    {
        return EmailRegexNonCompiled.IsMatch(TestEmail);
    }
}

class Program
{
    static void Main(string[] args)
    {
        var summary = BenchmarkRunner.Run&lt;EmailValidationBenchmark&gt;();
    }
}
```

试试这个示例 — 或者，更好的是，试着为你自己的regex设置一个这样的基准测试，看看compiled是否对你有区别！你是否注意到内存使用方面的差异或者只是运行时间？

接下来，你要研究的问题：你是否想在每次使用它时都创建一个带有compiled标志的新regex，或者这样做是否有性能开销？测量一下，看看是否对复用的regex实例变量进行一次编译有好处！

### RegexOptions.IgnoreCase

此选项启用不区分大小写的匹配，允许正则表达式模式匹配大写和小写字符。这一点很重要，因为如果你还不知道 — 是的，regex将区分大小写。希望你还没有因此头疼太多！

通过使用此选项，当使用模式“apple”搜索单词“apple”时，启用RegexOptions.IgnoreCase将匹配“apple”、“Apple”和“APPLE”。要使用此选项，只需在创建Regex对象时包含RegexOptions.IgnoreCase作为参数即可。我们可以在以下示例中看到这个选项的操作：

```csharp
using System;
using System.Text.RegularExpressions;


string input1 = "I love eating apples!";
string input2 = "APPLES are great for health.";
string input3 = "Have you seen my Apple?";

Console.WriteLine($"Input 1 contains 'apple': {ContainsApple(input1)}");
Console.WriteLine($"Input 2 contains 'apple': {ContainsApple(input2)}");
Console.WriteLine($"Input 3 contains 'apple': {ContainsApple(input3)}");

static bool ContainsApple(string input)
{
    // 嗯...我们应该把这个拿出来
    // 并使用compiled标志吗？
    Regex appleRegex = new Regex(
        "apple",
        RegexOptions.IgnoreCase);
    return appleRegex.IsMatch(input);
}
```

### RegexOptions.Multiline

此选项改变模式中^和$锚点的行为。默认情况下，^匹配输入字符串的开始，$匹配输入字符串的结束。然而，启用RegexOptions.Multiline后，^还将匹配输入字符串中每一行的开始，$匹配每一行的结束。此选项在处理多行输入时特别有用。

要使用此选项，只需在创建Regex对象时包含RegexOptions.Multiline作为参数即可，就像你在下面这个例子中所看到的！我们将使用这段代码来查找以注释字符#开头的行：

```csharp
using System;
using System.Text.RegularExpressions;

string multiLineText =
    """
    这是一些示例文本。
    # 这是一个评论。
    还有另一行。
    # 又一个评论。
    """;

foreach (var comment in FindComments(multiLineText))
{
    Console.WriteLine(comment);
}

static string[] FindComments(string input)
{
// 使用RegexOptions.Multiline将^视为每一行的开始。
Regex commentRegex = new Regex("^#.*$", RegexOptions.Multiline);

var matches = commentRegex.Matches(input);
string[] comments = new string[matches.Count];
for (int i = 0; i &lt; matches.Count; i++)
{
comments[i] = matches[i].Value;
}

return comments;
}
```

如果你想在浏览器中玩转[这个示例，请查看这个DotNetFiddle](https://dotnetfiddle.net/e4X9ZP "C#中的Regex选项 - 多行在DotNetFiddle中")：

---

## 常见问题：C#中的Regex

### 什么是正则表达式？

正则表达式是一系列字符，形成一个搜索模式。它可以用来基于某些模式匹配、搜索或操作字符串。

### 为什么在C#编程中正则表达式很重要？

正则表达式在C#编程中很重要，因为它们提供了强大的模式匹配和字符串操作能力。它们可用于验证输入、提取信息、替换文本等。

### C#中的一些常见regex选项是什么？

在C#中使用正则表达式时需要考虑的一些常见选项包括RegexOptions.Compiled、RegexOptions.IgnoreCase和RegexOptions.Multiline。这些选项允许你优化正则表达式匹配、忽略大小写敏感性以及跨多行进行匹配，分别。
