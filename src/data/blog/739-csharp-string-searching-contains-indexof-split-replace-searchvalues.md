---
pubDatetime: 2026-04-17T08:52:15+08:00
title: "C# 字符串搜索：Contains、IndexOf、Split、Replace 与 SearchValues 完全指南"
description: "系统梳理 C# 字符串搜索的核心 API：从 Contains、IndexOf、Split、Replace，到 .NET 8 引入的 SIMD 向量化 SearchValues，覆盖各 API 的使用场景、性能特征与最佳实践，附日志解析和模板引擎完整示例。"
tags: ["CSharp", "dotnet", "字符串", "性能优化"]
slug: "csharp-string-searching-contains-indexof-split-replace-searchvalues"
ogImage: "../../assets/739/01-cover.jpg"
source: "https://www.devleader.ca/2026/04/16/c-string-searching-contains-indexof-split-replace-and-searchvalues"
---

![C# 字符串搜索封面](../../assets/739/01-cover.jpg)

字符串搜索是 .NET 应用里最高频的操作之一。解析日志、处理用户输入、分词、提取固定格式字段——这些场景几乎每天都会碰到。这篇文章系统梳理 C# 里的核心字符串搜索 API，从你每天都在用的 `Contains` 和 `IndexOf`，到 .NET 8 引入的 SIMD 向量化 `SearchValues<char>`，帮你在正确的场景选对工具。

## Contains：存在性检查

`Contains` 是最简单的存在性检查，直接告诉你子串或字符是否存在于字符串中：

```csharp
var text = "The quick brown fox jumps over the lazy dog";

bool hasFox   = text.Contains("fox");                                     // True
bool hasCAT   = text.Contains("cat");                                     // False
bool hasFoxCI = text.Contains("FOX", StringComparison.OrdinalIgnoreCase); // True
```

需要大小写不敏感时，务必传入 `StringComparison`。不带参数的重载是大小写敏感的顺序比较。

### 单字符检查更快

只需检测单个字符时，`char` 重载比传单字符字符串更快，因为它跳过了子串搜索的初始化开销：

```csharp
bool hasComma = text.Contains(','); // 比 text.Contains(",") 更快
bool hasDot   = text.Contains('.');
```

### 基于 Span 的无分配检查

如果你已经持有 `ReadOnlySpan<char>`，可以直接用扩展方法，不需要创建临时字符串：

```csharp
ReadOnlySpan<char> span = "Hello, World!".AsSpan();
bool hasCom = span.Contains(",".AsSpan(), StringComparison.Ordinal);
```

## IndexOf 与 LastIndexOf：定位位置

需要知道子串在哪里，而不仅仅是"有没有"时，`IndexOf` 和 `LastIndexOf` 返回零基索引，找不到则返回 -1：

```csharp
var path = "/usr/local/bin/dotnet";

int firstSlash  = path.IndexOf('/');                                      // 0
int lastSlash   = path.LastIndexOf('/');                                  // 14
int dotnetStart = path.IndexOf("dotnet");                                 // 15

// 从指定位置开始搜索
int secondSlash = path.IndexOf('/', 1);                                   // 4

// 配合 StringComparison
int pos = path.IndexOf("BIN", StringComparison.OrdinalIgnoreCase);       // 11
```

使用返回值前一定要先检查是否为 -1，否则在后续字符串截取时会引发异常。

### IndexOfAny 与 LastIndexOfAny

`IndexOfAny` 从字符集合中找第一个匹配的字符：

```csharp
var line       = "Name: Nick; Role: Admin";
var delimiters = new[] { ':', ';', ',' };

int firstDelim = line.IndexOfAny(delimiters);    // 4（"Name" 后面的 ':'）
int lastDelim  = line.LastIndexOfAny(delimiters); // 17（"Role" 后面的 ':'）
```

对长字符串或热路径而言，这个方式并不是最高效的——`SearchValues` 在这里更合适（见下文）。

## Split：字符串分词

`Split` 按分隔符拆分字符串：

```csharp
var csv = "alpha,beta,,gamma, delta";

// 基础拆分
string[] parts = csv.Split(',');
// ["alpha", "beta", "", "gamma", " delta"]

// 去除空项
string[] noEmpty = csv.Split(',', StringSplitOptions.RemoveEmptyEntries);
// ["alpha", "beta", "gamma", " delta"]

// 去除空项并修剪空格（.NET 5+）
string[] cleanParts = csv.Split(',',
    StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
// ["alpha", "beta", "gamma", "delta"]
```

`TrimEntries`（.NET 5 引入）省去了以前需要额外调用 LINQ `.Select(s => s.Trim())` 的麻烦。

### 带数量限制的 Split

传入 count 参数可以限制返回的元素数量。达到上限后，最后一个元素包含剩余的完整字符串（含未消费的分隔符）：

```csharp
var log = "2026-05-06 21:00:00 INFO Server started";
string[] parts = log.Split(' ', 4);
// ["2026-05-06", "21:00:00", "INFO", "Server started"]
```

### 多分隔符 Split

输入使用多种分隔符时，传入字符数组：

```csharp
var text = "one|two,three;four";
string[] parts = text.Split(new[] { '|', ',', ';' });
// ["one", "two", "three", "four"]
```

### 基于 Span 的零分配拆分（.NET 6+）

对性能敏感的场景，`MemoryExtensions.Split` 返回 `Range` 值，指向原始字符串内的位置，不产生任何中间字符串分配：

```csharp
var line = "alpha,beta,gamma";
Span<Range> ranges = stackalloc Range[10];
int count = line.AsSpan().Split(ranges, ',');

for (var i = 0; i < count; i++)
{
    var part = line.AsSpan(ranges[i]); // 每个字段都无分配
    Console.WriteLine(part.ToString());
}
```

## Replace：字符串替换

`Replace` 返回一个新字符串，其中所有匹配项被替换：

```csharp
var text = "Hello, World! World!";

// 替换字符串
string replaced  = text.Replace("World", "Nick");
// "Hello, Nick! Nick!"

// 替换字符
string noCommas  = text.Replace(',', ';');

// 大小写不敏感替换（.NET 5+）
string ciReplaced = text.Replace("WORLD", "Nick", StringComparison.OrdinalIgnoreCase);
// "Hello, Nick! Nick!"
```

注意：即使没有找到匹配项，`Replace` 也会分配一个新字符串。对热路径来说，可以先用 `Contains` 检查，再决定是否替换：

```csharp
var result = text.Contains("World", StringComparison.OrdinalIgnoreCase)
    ? text.Replace("World", "Nick", StringComparison.OrdinalIgnoreCase)
    : text;
```

## Substring 与 Range 运算符

`Substring` 提取子串；C# 8+ 引入的范围运算符 `[..]` 是更现代的写法：

```csharp
var text = "Hello, World!";

// 传统 Substring
string sub1 = text.Substring(7, 5); // "World"
string sub2 = text.Substring(7);    // "World!"

// 范围运算符（C# 8+）
string ranged1 = text[7..12]; // "World"
string ranged2 = text[7..];   // "World!"
string ranged3 = text[..5];   // "Hello"
string last4   = text[^4..];  // "ld!"（^ 表示从末尾计算）
```

两种方式本质相同，都会分配新字符串。如果不需要完整字符串对象，用 `AsSpan()` 做零分配切片：

```csharp
ReadOnlySpan<char> span      = text.AsSpan(7, 5);    // 零分配
ReadOnlySpan<char> rangeSpan = text.AsSpan()[7..12]; // 同样零分配
```

## SearchValues：SIMD 向量化搜索（.NET 8+）

`SearchValues<T>` 是针对字符集合搜索的高性能解决方案。它使用平台相关的 SIMD 指令（SSE2、AVX2 或 ARM NEON）一次扫描多个字符，在长字符串上比 `IndexOfAny(char[])` 快得多：

```csharp
using System.Buffers;

public static class Tokenizer
{
    // 构建一次，多次复用——初始化有一次性开销
    private static readonly SearchValues<char> _whitespace =
        SearchValues.Create(" \t\n");

    private static readonly SearchValues<char> _urlSpecialChars =
        SearchValues.Create("/?#%&=+@");

    private static readonly SearchValues<char> _htmlSpecialChars =
        SearchValues.Create("<>&'");

    public static int FindFirstWhitespace(ReadOnlySpan<char> text)
        => text.IndexOfAny(_whitespace);

    public static bool ContainsUrlSpecialChar(ReadOnlySpan<char> url)
        => url.IndexOfAny(_urlSpecialChars) >= 0;

    public static bool NeedsHtmlEncoding(ReadOnlySpan<char> text)
        => text.IndexOfAny(_htmlSpecialChars) >= 0;
}
```

`SearchValues` 必须声明为 `static readonly` 字段——它的构造会预建内部优化数据结构，这个开销只在启动时付一次。

### SearchValues 的字符串版本（.NET 9+）

.NET 9 把 `SearchValues` 从单字符扩展到完整字符串，内部使用 Aho-Corasick 算法实现高效的多模式同时匹配：

```csharp
// .NET 9+
SearchValues<string> httpMethods = SearchValues.Create(
    ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    StringComparison.OrdinalIgnoreCase);

bool isHttpMethod = "get".AsSpan().ContainsAny(httpMethods); // True
```

## 实战：日志解析器

下面这个解析器综合使用了 `SearchValues`、`Split` 和 Span 操作。它先用 `SearchValues` 做快速预检，跳过不可能包含日志级别的行，再运行成本更高的 `Split`：

```csharp
using System.Buffers;

public readonly record struct LogEntry(string Timestamp, string Level, string Message);

public static class LogParser
{
    private static readonly SearchValues<char> _levelChars =
        SearchValues.Create("DIWEF"); // Debug, Info, Warn, Error, Fatal

    public static LogEntry? Parse(string line)
    {
        if (string.IsNullOrWhiteSpace(line))
            return null;

        // 快速预检：必须包含日志级别字符
        if (line.AsSpan().IndexOfAny(_levelChars) < 0)
            return null;

        // 格式："2026-05-06 21:00:00 INFO Message content here"
        var parts = line.Split(' ', 4, StringSplitOptions.TrimEntries);
        if (parts.Length < 4)
            return null;

        return new LogEntry(
            Timestamp: $"{parts[0]} {parts[1]}",
            Level:     parts[2],
            Message:   parts[3]);
    }

    public static IEnumerable<LogEntry> ParseLines(IEnumerable<string> lines)
    {
        foreach (var line in lines)
        {
            var entry = Parse(line);
            if (entry.HasValue)
                yield return entry.Value;
        }
    }
}
```

## 实战：简单模板引擎

`Replace` 可以用来构建一个轻量的具名变量模板引擎，把 `{Key}` 占位符替换为字典中的值，大小写不敏感：

```csharp
public static class TemplateEngine
{
    public static string Render(
        string template,
        IReadOnlyDictionary<string, string> variables)
    {
        var result = template;
        foreach (var (key, value) in variables)
            result = result.Replace(
                $"{{{key}}}", value,
                StringComparison.OrdinalIgnoreCase);
        return result;
    }
}

// 使用示例
var template = "Hello, {Name}! You have {Count} messages.";
var vars = new Dictionary<string, string>
{
    { "Name", "Nick" },
    { "Count", "42" }
};
var rendered = TemplateEngine.Render(template, vars);
// "Hello, Nick! You have 42 messages."
```

## 性能对比

选哪个 API，主要取决于你需要的是存在性检查、位置定位，还是完整子串提取，以及当前场景对内存分配的容忍度：

| API | 是否分配 | 性能说明 |
|---|---|---|
| `Contains(string)` | 否 | O(N\*M) 最坏情况 |
| `IndexOf(char)` | 否 | .NET 6+ 已向量化 |
| `IndexOfAny(char[])` | 否 | 比 `SearchValues` 慢 |
| `SearchValues.IndexOfAny` | 否 | SIMD 向量化，多字符搜索最快 |
| `Split(char)` | 是（数组）| 零分配可用 Span split |
| `Replace(string, string)` | 是（新字符串）| 未命中时也分配，可先 `Contains` 检查 |
| `Substring` / `[..]` | 是（新字符串）| 零分配用 `AsSpan()` |

基本原则：只需判断是否存在用 `Contains`，需要位置用 `IndexOf`，多字符搜索的热路径用 `SearchValues`，需要零分配拆分用 Span split。

## 参考

- [C# String Searching: Contains, IndexOf, Split, Replace, and SearchValues](https://www.devleader.ca/2026/04/16/c-string-searching-contains-indexof-split-replace-and-searchvalues) — Dev Leader
