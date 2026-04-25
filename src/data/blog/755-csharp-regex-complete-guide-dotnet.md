---
pubDatetime: 2026-04-25T09:50:00+08:00
title: "C# 正则表达式完全指南：从基础到现代 .NET API"
description: "系统梳理 C# 正则表达式的完整知识体系：核心方法（IsMatch/Match/Matches/Replace/Split）、RegexOptions 标志、命名捕获组、.NET 7+ 的 [GeneratedRegex] 编译时生成、NonBacktracking 安全模式，以及零分配的 Span 系列 API，并附性能对比和常见错误总结。"
tags: ["C#", ".NET", "Regex", "Performance", "Tutorial"]
slug: "csharp-regex-complete-guide-dotnet"
ogImage: "../../assets/755/01-cover.png"
source: "https://www.devleader.ca/2026/04/24/c-regex-complete-guide-to-regular-expressions-in-net"
---

![放大镜在字符流中精确提取匹配片段](../../assets/755/01-cover.png)

正则表达式是处理文本时最有力的工具之一——验证格式、提取数据、批量替换、按模式分割，全部由它一手包办。C# 通过 `System.Text.RegularExpressions` 命名空间提供了完整的正则支持，而且 .NET 7 和 .NET 8 带来了几个足以改变开发习惯的新 API，大多数人还没有用上。

这篇文章从命名空间的类型体系开始，逐一讲清核心方法、语法要素和 `RegexOptions`，再重点介绍 `[GeneratedRegex]`、`NonBacktracking`、`EnumerateMatches` 这些新 API 的用法和适用场景，最后给出性能对比和常见陷阱清单。

## 命名空间里有什么

`System.Text.RegularExpressions` 不只是一个 `Regex` 类，它的完整类型层次值得了解一下：

- `Regex` — 核心类，提供模式匹配、替换、分割
- `Match` — 单次匹配结果
- `MatchCollection` — 所有匹配结果的集合
- `Group` — 匹配中的一个捕获组
- `GroupCollection` — 一次匹配里所有组的集合
- `Capture` / `CaptureCollection` — 单个组内的多次捕获
- `RegexOptions` — 控制匹配行为的标志枚举
- `MatchEvaluator` — 用于自定义替换逻辑的委托

.NET 7+ 还新增了：

- `[GeneratedRegex]` 特性 — 编译时源码生成
- `ValueMatch` — `EnumerateMatches` 返回的 ref struct，零分配

## 六个核心方法

正则的日常使用基本覆盖在这六个方法里。选对方法既能让代码更易读，也能避免不必要的性能损耗。

### IsMatch — 判断是否存在匹配

最简单的一个，只返回 `true` / `false`：

```csharp
var regex = new Regex(@"^\d{3}-\d{4}$");

Console.WriteLine(regex.IsMatch("555-1234")); // True
Console.WriteLine(regex.IsMatch("5551234"));  // False
```

如果只需要知道"有没有"，用 `IsMatch` 而不是 `Match`，避免分配不必要的 `Match` 对象。

### Match — 找第一个匹配

返回一个 `Match` 对象，包含 `Value`（匹配文本）、`Index`（起始位置）、`Length`（长度）。使用前先判断 `match.Success`：

```csharp
var regex = new Regex(@"\w+");
var match = regex.Match("Hello world");

if (match.Success)
{
    Console.WriteLine(match.Value);  // Hello
    Console.WriteLine(match.Index);  // 0
    Console.WriteLine(match.Length); // 5
}
```

调用 `match.NextMatch()` 可以步进到下一个匹配，或者直接用 `Matches` 一次性拿到全部。

### Matches — 找全部匹配

返回一个 `MatchCollection`，支持 LINQ 查询，按从左到右的顺序包含所有非重叠匹配：

```csharp
var regex = new Regex(@"\d+");
var matches = regex.Matches("Price: $12, Qty: 3, Total: $36");

foreach (Match m in matches)
{
    Console.WriteLine(m.Value);
}
// 12  3  36
```

如果关心堆分配，用 `EnumerateMatches` 替代（见后文）。

### Replace — 替换匹配文本

简单替换用两参数重载，动态替换用 `MatchEvaluator` 委托：

```csharp
var regex = new Regex(@"\d{4}");

// 简单替换
string result = regex.Replace("Card: 4242 4242 4242 4242", "****");
// Card: **** **** **** ****

// MatchEvaluator：动态替换
string doubled = regex.Replace("4242 4242", m => (int.Parse(m.Value) * 2).ToString());
// 8484 8484
```

### Split — 按模式分割

比 `string.Split` 强大：分隔符可以是任意模式，不必是固定字符：

```csharp
var regex = new Regex(@"[,;\s]+");
string[] parts = regex.Split("alpha, beta;  gamma delta");
// ["alpha", "beta", "gamma", "delta"]
```

## 常用语法速查

| 元素 | 含义 |
|------|------|
| `.` | 除换行符外的任意字符 |
| `\d` / `\D` | 数字 / 非数字 |
| `\w` / `\W` | 单词字符 / 非单词字符 |
| `\s` / `\S` | 空白 / 非空白 |
| `^` / `$` | 字符串（或行）的开头 / 结尾 |
| `\b` | 单词边界 |
| `*` / `+` / `?` | 零或多 / 一或多 / 零或一 |
| `{n,m}` | n 到 m 次重复 |
| `[abc]` / `[^abc]` | 字符类 / 否定字符类 |
| `(abc)` | 捕获组 |
| `(?:abc)` | 非捕获组 |
| `(?<name>...)` | 命名捕获组 |
| `a\|b` | 分支 |

## RegexOptions 控制匹配行为

`RegexOptions` 是一个标志枚举，可以用 `|` 组合多个选项：

```csharp
// 大小写不敏感
var ci = new Regex(@"hello", RegexOptions.IgnoreCase);
Console.WriteLine(ci.IsMatch("HELLO")); // True

// Multiline：^ 和 $ 匹配每行的边界
var ml = new Regex(@"^\d+", RegexOptions.Multiline);
var matches = ml.Matches("42\n99\n7");
Console.WriteLine(matches.Count); // 3

// ExplicitCapture：只捕获命名组（减少不必要分配）
var ec = new Regex(
    @"(?<year>\d{4})-(?<month>\d{2})-(?<day>\d{2})",
    RegexOptions.ExplicitCapture);

// IgnorePatternWhitespace：允许在模式里写注释
var commented = new Regex(@"
    \d{3}   # 区号
    -       # 分隔符
    \d{4}   # 号码
", RegexOptions.IgnorePatternWhitespace);
```

## 命名捕获组

比数字下标更可维护，尤其是模式复杂时：

```csharp
var regex = new Regex(@"(?<year>\d{4})-(?<month>\d{2})-(?<day>\d{2})");
var match = regex.Match("Date: 2026-05-07");

if (match.Success)
{
    Console.WriteLine(match.Groups["year"].Value);  // 2026
    Console.WriteLine(match.Groups["month"].Value); // 05
    Console.WriteLine(match.Groups["day"].Value);   // 07
}
```

## 静态方法 vs 实例方法

静态方法内部维护一个缓存（默认 15 条），适合偶尔调用的场景。实例方法适合高频复用：

```csharp
// 静态 — 一次性使用时方便
bool match = Regex.IsMatch("hello", @"\w+");

// 实例 — 同一模式多次复用
var regex = new Regex(@"\w+", RegexOptions.Compiled);
```

不过对于 .NET 7+ 项目，两者都可以让路给 `[GeneratedRegex]`。

## 现代 .NET API（.NET 7+）

这一批 API 才是真正值得关注的改进，不是小修小补——它们直接改变了正则的性能上限和安全边界。

### [GeneratedRegex] — 编译时源码生成

.NET 7 引入，通过 Roslyn 源码生成器在**构建时**把模式编译成 IL，彻底消除运行时的启动开销：

```csharp
using System.Text.RegularExpressions;

public partial class EmailValidator
{
    [GeneratedRegex(
        @"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        RegexOptions.IgnoreCase,
        matchTimeoutMilliseconds: 500)]
    private static partial Regex EmailPattern();

    public static bool IsValidEmail(string input)
        => EmailPattern().IsMatch(input);
}
```

要求：方法必须是 `static partial`，返回 `Regex`，类必须是 `partial`。相比 `RegexOptions.Compiled`（仍在运行时编译），`[GeneratedRegex]` 零启动成本，是热路径上的最优选择。

### RegexOptions.NonBacktracking — 线性时间安全模式

传统正则使用回溯，某些模式遇到恶意输入会触发灾难性回溯（ReDoS）。`NonBacktracking` 采用 NFA/DFA 方法，时间复杂度 O(n)：

```csharp
var regex = new Regex(
    @"^(a+)+$",
    RegexOptions.NonBacktracking,
    TimeSpan.FromMilliseconds(500));

// 即使面对恶意构造的输入也安全
bool result = regex.IsMatch("aaaaaaaaaaaaaaaaaaaaaaaaaX");
```

权衡：`NonBacktracking` 不支持反向引用和环视（lookahead/lookbehind），最适合处理不可信输入的校验场景。

### EnumerateMatches — 零分配迭代（.NET 7+）

`Regex.EnumerateMatches` 返回 `ValueMatch` ref struct，不分配 `MatchCollection` 或 `Match` 对象。只有 `Index` 和 `Length`，自己切片原始字符串取值：

```csharp
var regex = new Regex(@"\d+");
var input = "Items: 10, 20, 30, 40";

foreach (ValueMatch match in regex.EnumerateMatches(input))
{
    var slice = input.AsSpan(match.Index, match.Length);
    Console.WriteLine(slice.ToString());
}
// 10  20  30  40
```

高吞吐场景下，堆分配是可量化的成本。`EnumerateMatches` 是这种场景的正确选择。

### EnumerateSplits — 零分配分割（.NET 8+）

类似地，`Regex.EnumerateSplits` 返回 `Range` structs，避免 `string[]` 分配。适合流式处理大文件或 CSV/TSV 分词：

```csharp
var regex = new Regex(@"[,;]+");
var input = "alpha,beta;gamma,,delta";

foreach (var range in regex.EnumerateSplits(input))
{
    Console.WriteLine(input[range]);
}
```

## 生产环境必须设置超时

没有超时，一个写得不好的模式加上恶意输入就能让应用挂起。始终传入 `matchTimeout`：

```csharp
var regex = new Regex(
    @"\w+",
    RegexOptions.None,
    TimeSpan.FromMilliseconds(500));

try
{
    var matches = regex.Matches(untrustedInput);
}
catch (RegexMatchTimeoutException ex)
{
    Console.WriteLine($"Regex timed out: {ex.Message}");
}
```

使用 `[GeneratedRegex]` 时，直接在特性里设置：

```csharp
[GeneratedRegex(@"\w+", RegexOptions.None, matchTimeoutMilliseconds: 500)]
private static partial Regex WordPattern();
```

## 在代码库中组织正则模式

把 `[GeneratedRegex]` 集中在一个 `static partial` 类里，比散落在各处的内联字符串更易维护：

```csharp
namespace MyApp.Validation;

public static partial class ValidationPatterns
{
    [GeneratedRegex(
        @"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        RegexOptions.IgnoreCase,
        matchTimeoutMilliseconds: 500)]
    public static partial Regex Email();

    [GeneratedRegex(
        @"^\+?[1-9]\d{1,14}$",
        RegexOptions.None,
        matchTimeoutMilliseconds: 500)]
    public static partial Regex PhoneE164();
}
```

## 线程安全性

`Regex` 实例对所有匹配操作（`IsMatch`、`Match`、`Matches`、`Replace`、`Split`）都是线程安全的，可以跨线程共享，无需加锁。`[GeneratedRegex]` 生成的静态方法本质上是单例，线程安全且零额外同步开销。

## 性能对比

| 方式 | 编译时机 | 匹配速度 | 内存分配 | 适用场景 |
|------|----------|----------|----------|----------|
| `new Regex(pattern)` | 运行时（解释） | 较慢 | 较高 | 一次性使用 |
| `new Regex(pattern, Compiled)` | 运行时（JIT） | 快 | 较低 | 高频复用 |
| `[GeneratedRegex]` | 构建时 | 最快 | 最低 | 热路径 |
| `NonBacktracking` | 零/低 | O(n) 线性 | 低 | 不可信输入校验 |

## 常见错误

**在循环里创建 `Regex` 实例。** 每次 `new Regex(pattern)` 都会解析和编译模式。热循环里这等于把编译开销乘以迭代次数。把实例提升到 `static readonly` 字段，或用 `[GeneratedRegex]`。

**忘记 `@` 前缀。** `@"\d+"` 正确，`"\d+"` 中的 `\d` 会被 C# 当作转义序列处理导致问题。正则模式几乎总应使用逐字字符串字面量。

**校验模式未加锚定。** `\d{5}` 会匹配 `"abc12345xyz"` 里的 12345。用于校验时必须加 `^` 和 `$`：`^\d{5}$`。

**面向用户的模式不设超时。** 任何处理用户提供数据的模式，不加超时就存在 ReDoS 风险。在 `[GeneratedRegex]` 或 `Regex` 构造函数里设置 `matchTimeoutMilliseconds`。

**模式过于复杂。** 超过两三行的正则，考虑拆成多个简单模式或换成小型状态机。复杂模式对 `[GeneratedRegex]` 的优化效果也更有限。

## 参考

- [原文：C# Regex: Complete Guide to Regular Expressions in .NET](https://www.devleader.ca/2026/04/24/c-regex-complete-guide-to-regular-expressions-in-net)
- [Microsoft Docs: System.Text.RegularExpressions](https://learn.microsoft.com/en-us/dotnet/api/system.text.regularexpressions)
- [Microsoft Docs: .NET Regular Expressions](https://learn.microsoft.com/en-us/dotnet/standard/base-types/regular-expressions)
