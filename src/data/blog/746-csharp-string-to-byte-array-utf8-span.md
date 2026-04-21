---
pubDatetime: 2026-04-21T15:48:44+08:00
title: "C# 字符串转字节数组：UTF-8、编码方式与 Span 零分配技巧"
description: "C# 字符串转字节数组是网络传输、流写入、哈希计算等场景的基础操作。本文覆盖从 Encoding.UTF8.GetBytes() 到 Span<byte>、stackalloc、u8 字面量、MemoryMarshal 的全套方法，并给出选型决策表和常见错误分析。"
tags: ["C#", ".NET", "Performance", "Language Features"]
slug: "csharp-string-to-byte-array-utf8-span"
ogImage: "../../assets/746/01-cover.png"
source: "https://www.devleader.ca/2026/04/20/c-string-to-byte-array-utf8-encoding-and-span-conversions"
---

字符串转字节数组是 .NET 开发中随处可见的基础操作：写入流、发送 HTTP 请求体、计算哈希、存储二进制数据——这些场景都需要先把字符串编码成字节。

方法有好几种，选哪种取决于三件事：字符串是不是编译期常量、数据量大不大、这段代码对堆分配是否敏感。

## 编码方式先搞清楚

在写代码之前，有一点必须明确：**字符串不是字节，字节也不是字符串**。

.NET `string` 内部用 UTF-16 存储，每个字符占 2 或 4 个字节。把它转成字节数组时，你必须选定一种编码标准：

- **UTF-8**：变长编码，每字符 1–4 字节。ASCII 字符只占 1 字节。互联网的通用标准。
- **UTF-16**：.NET 内部编码。与 Windows API 或遗留系统互操作时才用。
- **ASCII**：每字符 1 字节，只覆盖 128 个字符。含非 ASCII 字符时会静默丢失数据。
- **ISO-8859-1 / Latin-1**：1 字节，覆盖西欧字符。

绝大多数情况下，**UTF-8 是正确选择**——紧凑、通用、所有 Web 标准都用它。

## 方法一：Encoding.UTF8.GetBytes()（最简）

```csharp
using System.Text;

var text = "Hello, World!";
byte[] bytes = Encoding.UTF8.GetBytes(text);

Console.WriteLine(bytes.Length);  // 13
Console.WriteLine(bytes[0]);      // 72 ('H' 的 ASCII/UTF-8 值)
```

`Encoding.UTF8` 是静态、线程安全的单例，不需要每次 `new` 一个。这个方法会分配一个新的 byte[]。

如果想精确预分配缓冲区，先调 `GetByteCount` 再编码：

```csharp
var text = "Hello, 世界";
int byteCount = Encoding.UTF8.GetByteCount(text); // 13 + 6 = 19

byte[] buffer = new byte[byteCount];
int written = Encoding.UTF8.GetBytes(text, buffer);
Console.WriteLine($"Encoded {written} bytes");
```

## 方法二：Span&lt;byte&gt; 编码（零分配，.NET 5+）

如果手边已经有一块缓冲区（比如从 `ArrayPool` 租来的，或栈上分配的），可以直接写入，完全不产生新的堆分配：

```csharp
using System.Buffers;
using System.Text;

public static class Utf8Encoder
{
    public static int EncodeToRentedBuffer(string text, out byte[] rentedBuffer)
    {
        int maxByteCount = Encoding.UTF8.GetMaxByteCount(text.Length);
        rentedBuffer = ArrayPool<byte>.Shared.Rent(maxByteCount);

        int written = Encoding.UTF8.GetBytes(text, rentedBuffer);
        return written;
    }
}
```

对于长度不超过约 256 个字符的字符串，用 `stackalloc` 把缓冲区分配在栈上，彻底绕开 GC：

```csharp
Span<byte> stackBuffer = stackalloc byte[256];
var text = "Hello, World!";

int written = Encoding.UTF8.GetBytes(text.AsSpan(), stackBuffer);
var encoded = stackBuffer[..written];

Console.WriteLine($"Encoded {written} bytes");
```

`Encoding.UTF8.GetBytes(ReadOnlySpan<char>, Span<byte>)` 这个重载特别适合编码子字符串，不用先创建中间字符串对象。

## 方法三：u8 字面量（.NET 7+，编译期零成本）

当字符串是编译期常量时，用 `u8` 后缀直接得到 UTF-8 字节，运行时没有任何转换开销：

```csharp
// 编译期 UTF-8 字节，零运行时成本
ReadOnlySpan<byte> hello = "Hello, World!"u8;
ReadOnlySpan<byte> contentType = "application/json"u8;
ReadOnlySpan<byte> crlf = "\r\n"u8;

Console.WriteLine(hello.Length);  // 13
```

这些字节直接嵌入编译后的程序集，访问速度和普通只读数据一样快。

如果需要跨异步边界传递或存为字段，`ReadOnlySpan<byte>` 是 ref struct，只能存在栈上，要转成 `ReadOnlyMemory<byte>`：

```csharp
private static readonly ReadOnlyMemory<byte> JsonContentType =
    "application/json"u8.ToArray();
```

`ToArray()` 只在启动时分配一次，之后整个应用生命周期内复用，没有额外分配。

## 方法四：MemoryMarshal 获取 UTF-16 原始字节

有时候需要字符串的 UTF-16 原始字节（比如写入 Windows Named Pipe 或 COM 接口）：

```csharp
using System.Runtime.InteropServices;

var text = "Hello";
ReadOnlySpan<byte> utf16Bytes = MemoryMarshal.AsBytes(text.AsSpan());

Console.WriteLine(utf16Bytes.Length); // 10 —— 每个字符 2 字节
```

这是零拷贝操作，不分配任何内存，只是把字符串内部 UTF-16 缓冲区当成字节视图来看。注意：字节序是平台相关的（现代硬件通常是小端序）。

## 方法五：字节数组转回字符串

反向操作用 `Encoding.UTF8.GetString()`，编码方式必须和编码时一致，否则得到乱码：

```csharp
byte[] bytes = new byte[] { 72, 101, 108, 108, 111 }; // "Hello"
string text = Encoding.UTF8.GetString(bytes);
Console.WriteLine(text); // Hello

// Span 重载，避免额外拷贝
ReadOnlySpan<byte> span = bytes.AsSpan();
string fromSpan = Encoding.UTF8.GetString(span);
```

对于来自网络或文件的大型字节数组，优先用 Span 重载。

## 选型决策表

| 场景 | 推荐方法 |
|---|---|
| 通用场景，允许分配 | `Encoding.UTF8.GetBytes(string)` |
| 复用池化缓冲区 | `Encoding.UTF8.GetBytes(ReadOnlySpan<char>, Span<byte>)` |
| 编译期常量字符串 | `"..."u8` 字面量（.NET 7+） |
| 短字符串（< 256 字符）免堆分配 | `stackalloc` + `Encoding.UTF8.GetBytes` |
| 存为字段 / 跨异步边界 | `"..."u8.ToArray()` 一次性分配 |
| UTF-16 互操作 | `MemoryMarshal.AsBytes(text.AsSpan())` |

## 性能横向对比

| 方法 | 是否分配 | 备注 |
|---|---|---|
| `Encoding.UTF8.GetBytes(string)` | 是（byte[]） | 简单，多数场景够用 |
| `GetBytes(Span<char>, Span<byte>)` | 否 | 复用缓冲区的最佳选择 |
| `"..."u8` 字面量 | 否 | 零成本，仅限编译期常量 |
| `stackalloc` 缓冲 | 否（栈上） | 短字符串的最优解 |
| `ArrayPool` 缓冲 | 否（池化） | 大字符串或变长字符串的最优解 |

## 实战：HTTP 请求体

```csharp
public async Task<HttpResponseMessage> PostJsonAsync(
    string url, string json, CancellationToken cancellationToken = default)
{
    var bytes = Encoding.UTF8.GetBytes(json);
    var content = new ByteArrayContent(bytes);
    content.Headers.ContentType = new MediaTypeHeaderValue("application/json")
    {
        CharSet = "utf-8"
    };
    return await _httpClient.PostAsync(url, content, cancellationToken);
}
```

高吞吐场景下（每秒发送大量请求），换成 `ArrayPool<byte>` 租借缓冲区，请求完成后归还。

## 实战：计算 SHA-256 哈希

```csharp
// 简单版
public static string ComputeSha256(string input)
{
    var bytes = Encoding.UTF8.GetBytes(input);
    var hash = SHA256.HashData(bytes);
    return Convert.ToHexString(hash).ToLowerInvariant();
}

// 零分配版（使用 stackalloc）
public static string ComputeSha256Fast(string input)
{
    Span<byte> inputBytes = stackalloc byte[Encoding.UTF8.GetMaxByteCount(input.Length)];
    int inputLength = Encoding.UTF8.GetBytes(input, inputBytes);
    inputBytes = inputBytes[..inputLength];

    Span<byte> hash = stackalloc byte[32]; // SHA-256 固定 32 字节
    SHA256.HashData(inputBytes, hash);

    return Convert.ToHexString(hash).ToLowerInvariant();
}
```

零分配版对短字符串的输入编码和哈希输出都用 `stackalloc`，完全不碰堆内存。

## 三个常见错误

**用 ASCII 处理通用文本**：ASCII 只覆盖 128 个字符，包含任何非英文字符时会静默替换成问号，数据悄无声息地损坏了。始终用 UTF-8。

**每次 new 一个 Encoding 实例**：`Encoding.UTF8` 已经是线程安全单例，`new UTF8Encoding()` 浪费内存，增加 GC 压力。

**把字符串转字节再做比较**：这会产生两个临时字节数组，立即丢弃。直接用 `string.Equals(a, b, StringComparison.OrdinalIgnoreCase)` 即可。

## 参考

- [C# String to Byte Array: UTF-8, Encoding, and Span Conversions - Dev Leader](https://www.devleader.ca/2026/04/20/c-string-to-byte-array-utf8-encoding-and-span-conversions)
