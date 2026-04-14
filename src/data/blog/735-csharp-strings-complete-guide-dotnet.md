---
pubDatetime: 2026-04-14T11:56:52+08:00
title: "C# 字符串完全指南：.NET 字符串操作全解析"
description: "从不可变性原理到 SearchValues 的 SIMD 加速，全面梳理 .NET 字符串的核心机制、常用 API、各种字面量语法、性能优化手段与比较最佳实践，帮你在不同场景下选对工具，写出既正确又高效的字符串处理代码。"
tags: ["CSharp", ".NET", "String", "Performance"]
slug: "csharp-strings-complete-guide-dotnet"
ogImage: "../../assets/735/01-cover.png"
source: "https://www.devleader.ca/2026/04/13/c-strings-complete-guide-to-string-manipulation-in-net"
---

![C# 字符串完全指南封面](../../assets/735/01-cover.png)

C# 字符串操作是每个 .NET 开发者每天都绕不开的事。字符串出现在应用的每一层——解析用户输入、格式化日志、序列化数据、构造查询。真正理解字符串在 .NET 里的工作方式，不只是知道怎么用，而是能在正确的场景选对工具，避免隐性的性能问题和跨平台 bug。

这篇指南从 .NET 字符串的基本机制讲起，覆盖各种字面量形式、常用 API、比较最佳实践，一直到 .NET 6/7/8/9 引入的现代高性能工具。

## 字符串在 .NET 里怎么运作

在 C# 里，`string` 是 `System.String` 的关键字别名。.NET 字符串最重要的特性是**不可变性**：一旦创建，内容就无法修改。任何看起来像"修改"字符串的操作，实际上都是在堆上创建了一个全新的字符串对象。

```csharp
var original = "Hello";
var modified = original + ", World"; // 创建新字符串，original 不变
Console.WriteLine(original);  // Hello
Console.WriteLine(modified);  // Hello, World
```

不可变性带来三个直接影响：

- 多个引用可以安全地指向同一个字符串，不存在互相污染的风险
- 运行时可以通过**字符串驻留（interning）**复用相同的字符串字面量
- 在循环中大量拼接字符串会产生大量短命对象，给 GC 施压

理解不可变性，才能在 `StringBuilder`、`Span<char>`、插值字符串处理器之间做出准确的选择——这些内容在后面都会覆盖到。

## 字符串字面量的几种写法

C# 支持多种字面量形式，选对形式能减少转义符噪音、提升可读性，甚至消除运行时分配。

### 普通字面量

用双引号包围，支持 `\n`、`\t`、`\\` 等转义序列：

```csharp
var path = "C:\\Users\\Nick\\Documents";
var newLine = "Line one\nLine two";
var tab = "Column1\tColumn2";
```

### 逐字字符串（@"..."）

`@` 前缀禁用转义处理，反斜杠变成普通字符，适合文件路径和 Windows 注册表键：

```csharp
var path = @"C:\Users\Nick\Documents";
var multiLine = @"Line one
Line two
Line three";
```

### 原始字符串字面量（.NET 6 / C# 11+）

三个或更多双引号包围，几乎不需要任何转义符，适合嵌入 JSON、XML、正则表达式：

```csharp
var json = """
    {
        "name": "Nick",
        "role": "developer"
    }
    """;

var regex = """^\d{3}-\d{4}$""";

// 内部需要三引号时，用四引号来定界
var withQuotes = """"
    She said """Hello World"""
    """";
```

原始字符串字面量会根据结束引号的缩进位置自动裁掉左边的空白，写多行内容时无需手动对齐。

### 插值字符串（$"..."）

`$` 前缀允许在字符串中直接嵌入 C# 表达式，是日常格式化的首选：

```csharp
var name = "Nick";
var count = 42;
var message = $"Hello, {name}! You have {count} messages.";
```

`@` 和 `$` 可以组合使用（`@$"..."`），原始字符串字面量也支持插值（`$"""`）：

```csharp
var greeting = $"""
    Hello, {name}!
    You have {count} unread messages.
    """;
```

### UTF-8 字符串字面量（.NET 7+）

`u8` 后缀直接生成 `ReadOnlySpan<byte>`，包含字符串的 UTF-8 编码字节，是编译期特性，运行时零开销：

```csharp
ReadOnlySpan<byte> utf8Hello = "Hello, World!"u8;
ReadOnlySpan<byte> contentType = "application/json"u8;
```

适合需要 UTF-8 字节的网络协议或文件 I/O 场景——字节直接嵌入程序集，无需运行时编码转换。

## 常用字符串方法

.NET 提供了丰富的字符串 API。这里整理最常用的几类，并标注哪些有现代高性能替代方案。

### 搜索与检查

```csharp
var text = "The quick brown fox jumps over the lazy dog";

bool hasQuick = text.Contains("quick");
bool startsWithThe = text.StartsWith("The");
bool endsWithDog = text.EndsWith("dog");

int index = text.IndexOf("fox");        // 16
int lastIndex = text.LastIndexOf("o");  // 41

// 零分配检查（.NET 5+）
bool containsSpan = text.AsSpan().Contains("fox".AsSpan(), StringComparison.Ordinal);
```

性能敏感路径优先使用 `Span<char>` 重载，避免堆分配。

### 修改字符串

因为字符串不可变，所有"修改"方法都返回新实例：

```csharp
var original = "  Hello, World!  ";

var trimmed = original.Trim();                    // "Hello, World!"
var upper = original.Trim().ToUpperInvariant();   // "HELLO, WORLD!"
var lower = original.Trim().ToLowerInvariant();   // "hello, world!"
var replaced = original.Replace("World", "Nick"); // "  Hello, Nick!  "

// 范围切片（.NET 5+）
var sliced = "Hello, World!"[7..]; // "World!"
```

### 分割与合并

```csharp
var csv = "alpha, beta, gamma, delta";
string[] parts = csv.Split(',');

// 移除空项并自动去除空白（.NET 5+）
string[] cleaned = csv.Split(',',
    StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

var rejoined = string.Join(", ", parts); // "alpha, beta, gamma, delta"

// 对 Span 做 Join（.NET 6+）
var joined = string.Join('-', parts.AsSpan(0, 2)); // "alpha-beta"
```

`TrimEntries` 省去了后续的 `.Select(s => s.Trim())` 调用，是 .NET 5 里一个很实用的小改进。

### 格式化

```csharp
double pi = 3.14159265;

var formatted = pi.ToString("F4");      // "3.1416"
var currency = 1234.5m.ToString("C2"); // "$1,234.50"

// 复合格式化（多语言化和日志场景仍有用）
var message = string.Format("Value: {0:F2}", pi);

// 插值（日常推荐）
var modern = $"Value: {pi:F4}";
```

## 字符串比较的正确姿势

字符串比较是跨平台和国际化应用里常见的 bug 来源。核心规则只有一条：**始终传入明确的 `StringComparison` 参数**。

```csharp
var a = "Hello";
var b = "hello";

// ✅ 正确：序数比较，与文化无关
bool equal = string.Equals(a, b, StringComparison.OrdinalIgnoreCase);

// ❌ 避免：会分配新字符串，在某些文化下还可能得到错误结果
bool bad = a.ToLower() == b.ToLower();

// ✅ 用于排序和有序集合
var comparer = StringComparer.OrdinalIgnoreCase;
var sorted = new SortedDictionary<string, int>(comparer);
```

`StringComparison.OrdinalIgnoreCase` 是大多数非语言类比较的正确默认：文件路径、命令名、配置键、标识符。只有在需要遵循本地化规则的用户界面文本场景，才考虑 `CurrentCulture` 或 `InvariantCulture`。

## StringBuilder：循环拼接的正确工具

在循环中拼接字符串时，`+` 运算符每次都创建新字符串。`StringBuilder` 维护内部缓冲区，避免了中间字符串的产生：

```csharp
using System.Text;

// ❌ 性能差：每次循环都创建新字符串
var bad = "";
for (var i = 0; i < 1000; i++)
{
    bad += i.ToString();
}

// ✅ 高效：复用内部缓冲区
var sb = new StringBuilder(capacity: 4096);
for (var i = 0; i < 1000; i++)
{
    sb.Append(i);
}
var result = sb.ToString();
```

提前估算容量（`capacity` 参数）可以进一步减少内部扩容次数。.NET 6 引入的插值字符串处理器让一次性格式化场景下的插值同样高效，不需要额外引入 `StringBuilder`。

## Span\<char\> 和 ReadOnlySpan\<char\>：零分配切片

`Span<char>` 和 `ReadOnlySpan<char>` 是栈上的切片类型，让你在不产生堆分配的情况下操作字符串的子序列：

```csharp
var line = "2026-05-01T21:00:00Z";

// 零分配切片
ReadOnlySpan<char> datePart = line.AsSpan(0, 10);  // "2026-05-01"
ReadOnlySpan<char> timePart = line.AsSpan(11, 8);  // "21:00:00"

// 直接从 Span 解析，无需中间字符串
bool parsed = int.TryParse(datePart[0..4], out int year);
Console.WriteLine(year); // 2026
```

`string.Create()` 则允许你写入一个全新的字符串，同样无需中间分配：

```csharp
var id = 42;
var name = "Nick";
var key = string.Create(name.Length + 10, (id, name), static (span, state) =>
{
    var (id, name) = state;
    name.AsSpan().CopyTo(span);
    span[name.Length] = '-';
    id.TryFormat(span[(name.Length + 1)..], out _);
});
Console.WriteLine(key); // Nick-42
```

## SearchValues：SIMD 加速的多字符搜索（.NET 8+）

在字符串中查找多个字符里的任意一个时，.NET 8 引入的 `SearchValues<T>` 利用 SIMD 向量化实现极快的搜索速度，远超手动遍历或传入 char 数组的 `IndexOfAny`：

```csharp
using System.Buffers;

// 声明为静态只读字段，一次构建，多次复用
private static readonly SearchValues<char> _delimiters =
    SearchValues.Create(",;|\t");

public static int FindFirstDelimiter(ReadOnlySpan<char> text)
{
    return text.IndexOfAny(_delimiters);
}
```

`SearchValues` 最适合热路径——解析器、分词器、日志处理器——需要对大量文本扫描分隔符的场景。构建 `SearchValues` 对象有一次性开销，务必声明为 `static readonly` 字段。

## 现代 .NET 字符串 API 速查

| API / 特性 | 引入版本 | 用途 |
| --- | --- | --- |
| 原始字符串字面量 `"""..."""` | .NET 6 / C# 11 | 无转义多行字符串 |
| UTF-8 字符串字面量 `"..."u8` | .NET 7 | 编译期 `ReadOnlySpan<byte>` |
| `SearchValues<char>` | .NET 8 | 向量化多字符搜索 |
| 插值字符串处理器 | .NET 6 | 热路径下零分配插值 |
| `string.Create()` | .NET 5 | 无分配字符串构建 |
| `Span<char>` 集成 | .NET Core 2.1+ | 零分配子字符串切片 |
| Split 的 `TrimEntries` | .NET 5 | 分割时自动去除空白 |

## 实战：高效解析 CSV 行

下面的例子综合使用了 `Span<char>` 切片、`SearchValues` 和 `Split` 选项，处理包含引号字段的 CSV 行：

```csharp
using System.Buffers;

namespace StringDemo;

public static class CsvParser
{
    private static readonly SearchValues<char> _specialChars =
        SearchValues.Create(",\"");

    public static IReadOnlyList<string> ParseLine(string line)
    {
        // 快速路径：无特殊字符
        if (line.AsSpan().IndexOfAny(_specialChars) < 0)
        {
            return line.Split(',');
        }

        // 慢速路径：处理带引号的字段
        var fields = new List<string>();
        var span = line.AsSpan();

        while (!span.IsEmpty)
        {
            if (span[0] == '"')
            {
                span = span[1..]; // 跳过开头引号
                var end = span.IndexOf('"');
                fields.Add(end < 0 ? span.ToString() : span[..end].ToString());
                if (end >= 0) span = span[(end + 1)..];
                else break;
            }
            else
            {
                var comma = span.IndexOf(',');
                if (comma < 0)
                {
                    fields.Add(span.ToString());
                    break;
                }
                fields.Add(span[..comma].ToString());
                span = span[(comma + 1)..];
            }

            if (!span.IsEmpty && span[0] == ',')
                span = span[1..];
        }

        return fields;
    }
}
```

快速路径用 `SearchValues` 快速判断是否需要进入复杂解析，慢速路径用 `Span<char>` 切片避免子字符串分配——这是实际 .NET 项目里现代 API 与经典算法结合的典型方式。

## 性能选型速查

| 场景 | 推荐工具 |
| --- | --- |
| 单次简单拼接 | `+` 或插值字符串 |
| 循环中构建字符串 | `StringBuilder` |
| 解析子字符串 | `ReadOnlySpan<char>` + `AsSpan()` |
| 多字符搜索 | `SearchValues<char>`（.NET 8+） |
| UTF-8 协议字节 | `"..."u8` 字面量（.NET 7+） |
| 构建新字符串 | `string.Create()` |
| 大小写不敏感比较 | `StringComparison.OrdinalIgnoreCase` |

## 常见问题

**`string` 和 `String` 有区别吗？**

没有。`string` 是 `System.String` 的 C# 关键字别名，在代码里用 `string`（惯用法），调用静态方法时两种写法都可以，很多人也用小写形式调用 `string.IsNullOrEmpty`。

**为什么 C# 字符串是不可变的？**

不可变性让字符串可以安全地跨线程共享，支持字符串驻留，也简化了推理。代价是频繁修改时需要用 `StringBuilder` 或 `Span<char>` 来避免过多分配。

**什么时候用 `StringBuilder`，什么时候用插值字符串？**

单次格式化用插值字符串——可读性好，.NET 6+ 编译器已经优化了插值字符串处理器。多步条件拼接或循环中构建，用 `StringBuilder`。

**`OrdinalIgnoreCase` 是什么？**

它按字节比较字符（使用不变量大写规则），速度快，与文化无关，是比较标识符、文件名、URL、配置键的正确默认选项。不要用 `ToLower()` 做比较——会分配新字符串，在某些文化下还可能出错。

**原始字符串字面量是什么？**

C# 11 / .NET 6+ 引入，用三个或更多双引号包围，内部的反斜杠和双引号都无需转义，适合嵌入 JSON、XML、SQL 和正则表达式。

**`SearchValues` 怎么提升搜索性能？**

`SearchValues<char>`（.NET 8+）预计算 SIMD 优化的查找表，搜索速度远超 char 数组版的 `IndexOfAny`，在长字符串上尤其明显。把它声明为 `static readonly` 字段，只付一次构建成本。

## 参考

- [原文：C# Strings: Complete Guide to String Manipulation in .NET](https://www.devleader.ca/2026/04/13/c-strings-complete-guide-to-string-manipulation-in-net)
