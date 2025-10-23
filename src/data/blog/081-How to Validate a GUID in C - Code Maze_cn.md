---
pubDatetime: 2024-04-03
tags: [".NET", "C#"]
source: https://code-maze.com/csharp-how-to-validate-a-guid/
author: Osman Sokuoglu
title: 如何在 C# 中验证 GUID
description: 本文深入探讨了如何在 C# 中验证字符串表示的 GUID 的几种方法，并提供了示例代码片段。
---

> ## 摘要
>
> 本文深入探讨了如何在 C# 中验证字符串表示的 GUID 的几种方法，并提供了示例代码片段。
>
> 原文 [How to Validate a GUID in C#](https://code-maze.com/csharp-how-to-validate-a-guid/) 由 Osman Sokuoglu 撰写。

---

在本文中，我们将探讨几种方法来验证 C# 中的字符串表示的 GUID。

## GUID 长什么样？

**“GUID”** 一词最初由微软引入，作为更广泛术语“通用唯一标识符”（UUID）的特定版本。随着时间的推移，这些术语已变得可互换，并且根据 [RFC 4122](https://datatracker.ietf.org/doc/html/rfc4122) 标准化使用。在 C# 中，GUID 是一个 128 位的唯一标识符，通常表示为 32 个字符的十六进制字符串，格式为 **“xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx”**，其中每个“x”表示一个十六进制数字（0-9，A-F）。

GUID 在编程中扮演着关键角色，作为分布式系统和应用程序中的通用唯一标识符。它们 **提供了一种可靠的生成标识符的机制，这些标识符极不可能发生冲突或被复制。** GUID 在各种场景中得到广泛使用，包括作为数据库中的主键、唯一约束、会话标识符和资源命名等。

欲深入了解，请参考我们的综合文章 [在 C# 中使用 Guid](https://code-maze.com/csharp-guid-class/)。

## 在 C# 中验证 GUID 的方法

鉴于它们在我们的实现中的多样应用和关键作用，GUID 值得特别关注。特别是，在处理预计为 GUID 但以字符串或其他格式到达的数据时，**验证传入值的真实性变得至关重要，以保持数据完整性并确保涉及 GUID 的操作的正确性。**

让我们探索一些方法，以确定字符串是否包含 GUID 或仅仅是字符序列。

### 正则表达式

利用正则表达式使我们能识别字符串中的 GUID。我们知道 GUID 遵循固定长度的 36 个字符，包括连字符。通过编写与 GUID 格式对齐的正则表达式模式，我们可以精确地定位字符串中的 GUID 出现。

让我们利用正则表达式的强大功能来识别字符串是否为 GUID：

```csharp
public partial class GuidHelper
{
    [GeneratedRegex("^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")]
    private static partial Regex GuidValidatorRegex();
}
```

这里，我们引入了一个 `GuidHelper` 类来简化 GUID 验证过程。在这个类中，我们利用创新的 `GeneratedRegex` 属性。它接收一个正则表达式模式，并利用 **Roslyn 源生成器** 的能力，在编译时而不是运行时动态生成正则表达式的源代码。这种方法承诺更快的正则执行，从而提升应用程序的整体性能。为此，我们定义了一个名为 `GuidValidatorRegex()` 的部分方法，它返回 `Regex` 类型的响应，并使用 `GeneratedRegex` 属性强化其功能。

在制定模式时，我们指定输入必须由连字符分隔为五部分。第一部分应该是 8 个字符长，最后一部分 12 个字符长，其余部分各 4 个字符。每部分必须由数字（0-9）或从 A 到 F 的字符组成。总长度，包括连字符，是 36 个字符。

让我们看看如何使用这个特性：

```csharp
public static bool ValidateWithRegex(string input)
{
    return GuidValidatorRegex().IsMatch(input);
}
```

这里，我们建立了一个帮助方法 `ValidateWithRegex()`，它接受一个字符串输入参数。在这个方法中，我们使用先前定义的 `GuidValidatorRegex()` 函数并调用 `IsMatch()` 方法来验证输入字符串。

用 GUID 和非 GUID 输入调用此方法：

```csharp
var guidString = Guid.NewGuid().ToString();
const string nonGuidString = "loremipsum-sid-dolar-amet-34648208e86d";
const string messageFormat = "{0} | guidString is {1}, nonGuidString is {2}";
Message("Regex", GuidHelper.ValidateWithRegex(guidString), GuidHelper.ValidateWithRegex(nonGuidString));
```

现在让我们检查结果：

```plaintext
Regex | guidString is GUID, nonGuidString is not a GUID
```

正如预期的那样，我们的 `guidString` 是一个有效的 GUID，而我们的 `nonGuidString` 不是。

### 用 Guid.Parse 来验证 GUID

我们可以使用 C# 中的 `Guid.Parse()` 方法将字符串或字符跨度转换为 GUID 值。它首先从输入中去除任何前导或尾随的空白字符，然后处理剩余字符以生成 GUID。如果该方法在解析字符串时遇到困难，它会立即抛出一个 [FormatException](https://learn.microsoft.com/en-us/dotnet/api/system.formatexception?view=net-8.0)。

让我们使用这个方法来验证字符串是否是 GUID：

```csharp
public static bool ValidateWithGuidParse(string input)
{
    try
    {
        Guid.Parse(input);
    }
    catch (FormatException)
    {
        return false;
    }
    return true;
}
```

这里，我们引入了 `ValidateWithGuidParse()` 方法，它接受一个字符串输入参数。在这个方法中，我们在 [try-catch](https://code-maze.com/try-catch-block-csharp/) 块中使用 `Guid.Parse()` 方法。如果输入有效，不会抛出异常。然而，如果提供了无效输入，该方法将引发 `FormatException`。

从这一点开始，我们将省略调用和验证结果的步骤，因为它们与正则表达式方法中使用的步骤非常相似。

### Guid.ParseExact 来验证 GUID

验证字符串是否为 GUID 的另一个重要工具是 C# 中的 `Guid.ParseExact()` 方法。像 `Guid.Parse()` 方法一样，它是 `System.Guid` 命名空间的一部分，用于将字符串表示的 **GUID** 解析为 `Guid` 结构。有一个区别！它需要一个格式参数，允许我们强制对输入字符串采用特定格式，并相比 `Guid.Parse()` 方法提供了更多控制解析过程的选择。

格式参数指定 GUID 字符串的格式设置，决定了分隔符的放置和类型（例如，连字符、大括号）。它支持各种格式说明符：

| 格式 | 描述                                                                                             |
| ---- | ------------------------------------------------------------------------------------------------ |
| N    | 表示没有连字符的 32 位数字（例如，“6F9619FF8B86D011B42D00C04FC964FF”）。                         |
| D    | 以标准 8-4-4-4-12 格式用连字符分隔的 32 位数字（例如，“6F9619FF-8B86-D011-B42D-00C04FC964FF”）。 |
| B    | 以大括号括起来且用连字符分隔的 32 位数字（例如，“{6F9619FF-8B86-D011-B42D-00C04FC964FF}”）。     |
| P    | 以括号括起来且用连字符分隔的 32 位数字（例如，“(6F9619FF-8B86-D011-B42D-00C04FC964FF)”）。       |

这种方法通过确保对特定格式要求的遵循，提高了验证和解析 GUID 字符串的精确度和灵活性。

让我们利用这种方法来验证一个 GUID：

```csharp
public static bool ValidateWithGuidParseExact(string input, string format)
{
    try
    {
        Guid.ParseExact(input, format);
    }
    catch (FormatException)
    {
        return false;
    }
    return true;
}
```

这里，我们定义了 `ValidateWithGuidParseExact()` 方法。在方法内部，我们用传入的 `input` 参数和 `"D"` 格式参数调用 `Guid.ParseExact()` 方法。同样，如果提供了无效输入，该方法将引发 `FormatException`。

### Guid.TryParse 来验证 GUID

与 `Guid.Parse()` 和 `Guid.ParseExact()` 方法相比，`Guid.TryParse()` 提供了验证字符串是否为 GUID 的一种更安全的方法。与其抛出异常，`Guid.TryParse()` 返回一个布尔值，表示解析操作的成功与否。

让我们展示其用法：

```csharp
public static bool ValidateWithGuidTryParse(string input)
{
    return Guid.TryParse(input, out Guid _);
}
```

这里，我们创建了 `ValidateWithGuidTryParse()` 方法。它简单地调用并返回 `Guid.TryParse()` 方法的结果。

### Guid.TryParseExact 来验证 GUID

如果我们倾向于避免异常的复杂性，并且我们的字符串严格符合预定义的 GUID 格式，那么让我们使用 `Guid.TryParseExact()` 方法。与 `Guid.ParseExact()` 方法类似，这种方法要求字符串在去除任何前导或尾随的空白字符后，精确匹配由格式参数指定的格式。如果输入为 null 或不符合指定格式，方法将返回 false 而不抛出异常：

```csharp
public static bool ValidateWithGuidTryParseExact(string input, string format)
{
    return Guid.TryParseExact(input, format, out Guid _);
}
```

这里，我们引入了 `ValidateWithGuidTryParseExact()` 方法，它根据 `format` 参数对参数 `input` 进行验证。在方法中，我们使用了 `Guid.TryParseExact()` 方法并返回了它的结果。

### Guid 构造函数

当谈到编程中的解决方案时，通常有多种方法可供选择。鉴于我们的目标是验证字符串是否代表一个 GUID，我们可能会间接地将 `new Guid()` 结构用作验证方法。我们知道，向 `new Guid()` 构造函数传递一个值会在它是有效的 GUID 时生成一个成功的实例。然而，如果输入格式不适合 GUID，我们将遇到 `FormatException` 错误。

让我们将想要做的事情封装到一个方法中：

```csharp
public static bool ValidateWithNewGuid(string input)
{
    try
    {
        var _ = new Guid(input);
    }
    catch (FormatException)
    {
        return false;
    }
    return true;
}
```

这里，我们建立了 `ValidateWithNewGuid()` 方法，它接受一个 `input` 参数。在这个方法中，我们尝试使用 `new Guid(input)` 在 try-catch 块内初始化 `Guid` 的实例。如果遇到异常，这表明输入字符串不是有效的 GUID 字符串。

## 比较 GUID 验证方法的性能

到目前为止，我们已经探讨了验证字符串是否为 GUID 的各种方法。现在，我们准备比较这些方法在速度、内存分配和效率方面的性能。为了简化这一比较，我们将利用 [BenchmarkDotNet](https://code-maze.com/benchmarking-csharp-and-asp-net-core-projects/) 库进行基准测试：

| 方法                             | 迭代次数 |           平均 |      Gen0 |       分配 |
| -------------------------------- | -------- | -------------: | --------: | ---------: |
| UseValidateWithGuidTryParse      | 1000     |       7.879 us |         - |          - |
| UseValidateWithGuidTryParseExact | 1000     |      10.049 us |         - |          - |
| UseValidateWithRegex             | 1000     |      27.901 us |         - |          - |
| UseValidateWithGuidParse         | 1000     |   1,982.312 us |   19.5313 |   280002 B |
| UseValidateWithNewGuid           | 1000     |   2,015.921 us |   19.5313 |   280002 B |
| UseValidateWithGuidParseExact    | 1000     |   2,285.830 us |   19.5313 |   280002 B |
|                                  |          |                |           |            |
| UseValidateWithGuidTryParse      | 10000    |      80.765 us |         - |          - |
| UseValidateWithGuidTryParseExact | 10000    |     100.864 us |         - |          - |
| UseValidateWithRegex             | 10000    |     196.133 us |         - |          - |
| UseValidateWithGuidParse         | 10000    |  19,848.870 us |  218.7500 |  2800012 B |
| UseValidateWithNewGuid           | 10000    |  20,104.729 us |  218.7500 |  2800012 B |
| UseValidateWithGuidParseExact    | 10000    |  22,864.219 us |  218.7500 |  2800012 B |
|                                  |          |                |           |            |
| UseValidateWithGuidTryParse      | 100000   |     808.876 us |         - |          - |
| UseValidateWithGuidTryParseExact | 100000   |   1,023.358 us |         - |        1 B |
| UseValidateWithRegex             | 100000   |   1,942.818 us |         - |        2 B |
| UseValidateWithNewGuid           | 100000   | 199,408.744 us | 2000.0000 | 28000133 B |
| UseValidateWithGuidParse         | 100000   | 200,091.890 us | 2000.0000 | 28000133 B |
| UseValidateWithGuidParseExact    | 100000   | 229,846.689 us | 2000.0000 | 28000133 B |

很明显，使用 `Guid.TryParse()` 和 `Guid.TryParseExact()` 的技术在执行时间和内存使用方面持续胜过依赖正则表达式或手动验证方法如 `ValidateWithRegex()` 或 `ValidateWithNewGuid()` 的技术。

`TryParse()` 方法 **在所有测试迭代中表现出显著更低的平均执行时间，凸显出它们在性能效率方面的优越性。** 此外，**它们几乎不需要内存分配，几乎没有** `Gen0` **垃圾收集，使它们不仅速度更快，而且也是 GUID 验证任务更为资源高效的选择。**

## 结论

在本文中，我们探讨了几种方法来验证字符串是否在 C# 中表示一个 GUID。无论是**通过正则表达式，还是内置解析方法如 Guid.TryParse()，或基于字符串长度和格式的手动验证，我们都有一系列工具可以有效地验证 GUID。** 每种方法都根据可读性、性能和精确度的优势提供了不同的选择，使我们能够根据我们的具体需求选择最合适的方法。
