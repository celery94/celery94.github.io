---
pubDatetime: 2026-05-08T10:20:00+08:00
title: "C# Regex.Replace 与 Regex.Split 全解析：MatchEvaluator、EnumerateSplits 与替换语法"
description: "Regex.Replace 和 Regex.Split 是 C# 文本转换的主力 API。本文从基础用法讲到 MatchEvaluator 动态替换、替换字符串语法、GeneratedRegex 性能优化，再到 .NET 8 新增的零分配 EnumerateSplits，并附多个生产级实用示例。"
tags: ["CSharp", "Regex", "dotnet"]
slug: "csharp-regex-replace-split-matchevaluator-enumeratesplits"
ogImage: "../../assets/781/01-cover.png"
source: "https://www.devleader.ca/2026/05/06/c-regex-replace-and-split-matchevaluator-enumeratesplits-and-substitutions"
---

`Regex.Replace` 和 `Regex.Split` 是 C# 文本处理的两把主刀。无论是脱敏日志、格式化日期、拆分配置字符串，还是对大文本做高吞吐流式处理，这两个方法覆盖了绝大多数场景。.NET 7 和 .NET 8 还分别引入了 `[GeneratedRegex]` 和 `EnumerateSplits`，让性能敏感路径也有了零分配选项。

本文系统梳理这套 API 的全貌：从最基础的字面替换，到 `MatchEvaluator` 动态逻辑，再到 `EnumerateSplits` 的零分配拆分，每个要点都配有可直接运行的代码示例。

## Regex.Replace 基础

`Regex.Replace` 查找所有匹配并逐一用替换字符串（或回调）取代，返回新字符串，原字符串不变。

最简单的形式是把所有匹配替换为字面字符串：

```csharp
using System.Text.RegularExpressions;

var regex = new Regex(@"\d{4}");
string result = regex.Replace("Card: 4242 4242 4242 4242", "****");
Console.WriteLine(result); // Card: **** **** **** ****
```

静态调用适合一次性场景：

```csharp
string result = Regex.Replace("Hello   World", @"\s+", " ");
Console.WriteLine(result); // Hello World
```

### 限制替换次数

`count` 参数只替换前 N 个匹配，后面的保持不变：

```csharp
var regex = new Regex(@"foo", RegexOptions.IgnoreCase);
string result = regex.Replace("foo FOO foo", "bar", count: 2);
Console.WriteLine(result); // bar bar foo
```

### 指定起始位置

`startat` 参数跳过输入开头的一段，从指定字符偏移开始匹配。配合 `count` 可以精确控制哪些匹配被替换：

```csharp
var regex = new Regex(@"\d+");
string result = regex.Replace("1 2 3 4 5", "X", count: 2, startat: 2);
Console.WriteLine(result); // 1 X X 4 5
```

## 替换字符串中的替换语法

替换字符串有自己的一套语法，可以直接引用捕获组内容，不需要写回调。这是最快的结构化重排方式（比如日期格式转换、给匹配加 HTML 标签），因为不涉及 `MatchEvaluator` 委托调用。

.NET 支持的替换令牌：

| 令牌 | 含义 |
|---|---|
| `$1`、`$2` | 第 1、2 个捕获组的内容 |
| `${name}` | 命名捕获组的内容 |
| `$0` 或 `$&` | 整个匹配文本 |
| `` $` `` | 匹配前的文本 |
| `$'` | 匹配后的文本 |
| `$+` | 最后一个捕获组的内容 |
| `$$` | 字面量 `$` |

### 用命名反向引用重排日期

命名组让替换字符串几乎像模板一样可读：

```csharp
var regex = new Regex(@"(?<year>\d{4})-(?<month>\d{2})-(?<day>\d{2})");
string result = regex.Replace("Date: 2026-05-09", "${day}/${month}/${year}");
Console.WriteLine(result); // Date: 09/05/2026
```

### 用 $0 包装匹配内容

`$0`（等同于 `$&`）插入整个匹配文本，适合给所有匹配加标记，无需定义捕获组：

```csharp
var regex = new Regex(@"\d+");
string result = regex.Replace("Score: 42, Bonus: 100", "<b>$0</b>");
Console.WriteLine(result); // Score: <b>42</b>, Bonus: <b>100</b>
```

## MatchEvaluator：动态替换逻辑

`MatchEvaluator` 是一个 `Func<Match, string>` 委托，每个匹配都会调用一次，你可以在里面访问捕获组、位置、长度，并返回任意字符串。

### 基本用法

```csharp
var regex = new Regex(@"\d+");

string result = regex.Replace(
    "The price is 100 and tax is 15",
    match =>
    {
        int value = int.Parse(match.Value);
        return $"${value * 1.20:F2}";
    });

Console.WriteLine(result);
// The price is $120.00 and tax is $18.00
```

`Match` 对象提供完整上下文，包括命名组：

```csharp
var namePattern = new Regex(@"(?<first>\w+)\s+(?<last>\w+)");

string result = namePattern.Replace(
    "John Smith and Jane Doe",
    match =>
    {
        var first = match.Groups["first"].Value;
        var last  = match.Groups["last"].Value;
        return $"{last}, {first}";
    });

Console.WriteLine(result); // Smith, John and Doe, Jane
```

### 条件替换

当替换结果依赖匹配内容本身时，`MatchEvaluator` 是正确选择——比如只高亮保留字，普通标识符原样输出：

```csharp
var regex = new Regex(@"(?<word>[a-zA-Z]+)");
var reserved = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
    { "class", "public", "private", "static", "void", "return" };

string highlighted = regex.Replace(
    "public static void Main()",
    match =>
    {
        var word = match.Groups["word"].Value;
        return reserved.Contains(word) ? $"<b>{word}</b>" : word;
    });

Console.WriteLine(highlighted); // <b>public</b> <b>static</b> <b>void</b> Main()
```

## 与 [GeneratedRegex] 配合

生产代码推荐用 `[GeneratedRegex]` 在编译期生成正则，避免运行时编译开销，同时兼容所有 `Replace` 重载（含 `MatchEvaluator` 形式）。要求 `static partial` 方法 + `partial` 类：

```csharp
using System.Text.RegularExpressions;

public partial class TextProcessor
{
    [GeneratedRegex(
        @"(?<number>\d+(?:\.\d+)?)",
        RegexOptions.None,
        matchTimeoutMilliseconds: 500)]
    private static partial Regex NumberPattern();

    public static string NormalizeNumbers(string input)
    {
        return NumberPattern().Replace(input, match =>
        {
            if (!double.TryParse(match.Groups["number"].Value, out double val))
                return match.Value;
            return val.ToString("N2");
        });
    }
}
```

## Regex.Split：按模式拆分

`Regex.Split` 在所有匹配位置切开字符串，返回 `string[]`。相比 `string.Split`，分隔符可以是任意正则模式：

```csharp
var regex = new Regex(@"[,;\s]+");
string[] tokens = regex.Split("alpha, beta;  gamma\tdelta");

foreach (var t in tokens)
    Console.WriteLine(t);
// alpha / beta / gamma / delta
```

### 限制结果数量

`count` 参数控制最多分成几段，最后一段包含剩余所有内容，适合"取前几个字段、其余作为整体"的场景：

```csharp
var regex = new Regex(@"\s+");
string[] parts = regex.Split("one two three four five", count: 3);

Console.WriteLine(parts[0]); // one
Console.WriteLine(parts[1]); // two
Console.WriteLine(parts[2]); // three four five
```

### 在结果中保留分隔符

如果拆分模式包含捕获组，捕获的内容会穿插在结果数组里。这是一种同时保留分隔符类型的分词方式：

```csharp
var regex = new Regex(@"([,;])");
string[] tokens = regex.Split("a,b;c,d");

foreach (var t in tokens)
    Console.WriteLine($"'{t}'");
// 'a' / ',' / 'b' / ';' / 'c' / ',' / 'd'
```

## EnumerateSplits（.NET 8+）：零分配拆分

`Regex.EnumerateSplits` 是 .NET 8 新增的 API，不返回 `string[]`，而是通过 `SplitEnumerator` 逐一产生 `Range` 值，指向原字符串的对应区间。没有数组分配，没有子字符串分配：

```csharp
// .NET 8+ 专用
var regex = new Regex(@"[,;]+");
var input = "alpha,beta;gamma,delta";

foreach (var range in regex.EnumerateSplits(input))
{
    Console.WriteLine(input[range]);
}
// alpha / beta / gamma / delta
```

与旧方式的对比：

```csharp
var regex = new Regex(@"\s+");
string input = GetLargeString(); // 假设 10MB 文本

// 旧方式：分配 string[] + N 个子字符串对象
string[] parts = regex.Split(input);

// .NET 8 新方式：只分配枚举器结构体，无额外堆分配
foreach (var range in regex.EnumerateSplits(input))
{
    ProcessSegment(input.AsSpan(range));
}
```

`EnumerateSplits` 特别适合流式处理、日志解析等"顺序消费、不需要随机访问全部段"的场景。

### 配合 ReadOnlySpan 使用

`EnumerateSplits` 的重载也接受 `ReadOnlySpan<char>`，支持从栈内存、`ArrayPool` 切片或内存映射文件中拆分，全程零字符串分配：

```csharp
ReadOnlySpan<char> span = "one::two::three".AsSpan();
var regex = new Regex(@"::");

foreach (var range in regex.EnumerateSplits(span))
{
    var segment = span[range];
    Console.WriteLine(segment.ToString());
}
// one / two / three
```

## 实用示例

以下示例均以 `[GeneratedRegex]` 编写，适合直接用于生产代码。

### 规范化空白

```csharp
[GeneratedRegex(@"\s+", RegexOptions.None, matchTimeoutMilliseconds: 200)]
private static partial Regex WhitespacePattern();

public static string NormalizeWhitespace(string input)
    => WhitespacePattern().Replace(input.Trim(), " ");
```

### camelCase 转 kebab-case

零宽断言 `(?<=[a-z0-9])(?=[A-Z])` 匹配小写字母和大写字母之间的位置，插入连字符后再全部小写，适合从 C# 属性名生成 CSS 类名或 URL slug：

```csharp
[GeneratedRegex(@"(?<=[a-z0-9])(?=[A-Z])", RegexOptions.None, matchTimeoutMilliseconds: 200)]
private static partial Regex CamelToKebabPattern();

public static string ToKebabCase(string input)
    => CamelToKebabPattern().Replace(input, "-").ToLowerInvariant();

// "myPropertyName" → "my-property-name"
```

### 日志脱敏

后向断言 `(?<=(password|token|key)=)` 只匹配值部分，键名保留在日志里，便于排查问题同时保护敏感信息。HTTP 参数名不区分大小写，务必加 `IgnoreCase`：

```csharp
[GeneratedRegex(@"(?<=(password|token|key)=)[^\s&""]+",
    RegexOptions.IgnoreCase, matchTimeoutMilliseconds: 500)]
private static partial Regex SensitiveValuePattern();

public static string ScrubSecrets(string logLine)
    => SensitiveValuePattern().Replace(logLine, "***");

// "token=abc123&other=value" → "token=***&other=value"
```

### 简单 CSV 拆分

对没有带引号字段的 CSV，正则拆分比 `string.Split(',')` 更灵活，能处理逗号后的可选空格：

```csharp
[GeneratedRegex(@",\s*", RegexOptions.None, matchTimeoutMilliseconds: 200)]
private static partial Regex CsvSplitPattern();

public static string[] SplitCsv(string line) => CsvSplitPattern().Split(line);
```

> 如果 CSV 字段中可能包含带引号的逗号，请使用专门的 CSV 解析库，不要用正则。

## 多步文本转换管道

实际项目里很少只做一次替换，往往需要链式转换：规范化空白、解码 HTML 实体、重排日期格式、脱敏……

**链式调用**是最易读、最易测试的方式，适合转换步骤不多、字符串长度适中的情况：

```csharp
public static string NormalizeInput(string input)
{
    // 每步独立，顺序只在步骤之间有交互时才重要
    input = WhitespacePattern().Replace(input.Trim(), " ");
    input = HtmlEntityPattern().Replace(input, DecodeHtmlEntity);
    input = DateFormatPattern().Replace(input, @"${year}-${month}-${day}");
    return input;
}
```

**单次遍历**用一个组合模式 + `MatchEvaluator` 覆盖所有转换，适合超长字符串需要减少遍历次数的场景，但维护成本更高：

```csharp
var combinedPattern = new Regex(
    @"(?<whitespace>\s{2,})" +
    @"|(?<entity>&amp;|&lt;|&gt;|&quot;)" +
    @"|(?<date>(?<y>\d{4})/(?<m>\d{2})/(?<d>\d{2}))",
    RegexOptions.None, TimeSpan.FromSeconds(1));

string result = combinedPattern.Replace(input, m =>
{
    if (m.Groups["whitespace"].Success) return " ";
    if (m.Groups["entity"].Success)    return DecodeEntity(m.Value);
    if (m.Groups["date"].Success)
        return $"{m.Groups["y"]}-{m.Groups["m"]}-{m.Groups["d"]}";
    return m.Value;
});
```

大多数场景链式调用更合适——先测量，再优化。

## 何时不用正则

正则有一定开销。以下情况优先考虑更简单的选项：

- **字面替换**：`string.Replace` 总是更快
- **单字符分隔**：`string.Split(char)` 比 `Regex.Split` 快
- **嵌套结构或上下文相关语法**：考虑专用解析器库

适合用正则的情况：
- 分隔符是模式而非字面量
- 替换结果依赖匹配内容（MatchEvaluator）
- 替换字符串需要命名捕获组
- 需要限制替换次数或从指定位置开始

## 参考

- [原文：C# Regex Replace and Split: MatchEvaluator, EnumerateSplits, and Substitutions](https://www.devleader.ca/2026/05/06/c-regex-replace-and-split-matchevaluator-enumeratesplits-and-substitutions)
- [.NET 文档：Regex.Replace](https://learn.microsoft.com/dotnet/api/system.text.regularexpressions.regex.replace)
- [.NET 文档：Regex.Split](https://learn.microsoft.com/dotnet/api/system.text.regularexpressions.regex.split)
- [.NET 文档：Regex.EnumerateSplits (.NET 8+)](https://learn.microsoft.com/dotnet/api/system.text.regularexpressions.regex.enumeratesplits)
- [.NET 文档：GeneratedRegexAttribute](https://learn.microsoft.com/dotnet/api/system.text.regularexpressions.generatedregexattribute)
