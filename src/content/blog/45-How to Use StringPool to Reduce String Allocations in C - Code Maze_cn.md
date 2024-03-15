---
pubDatetime: 2024-03-15
tags: [C#, StringPool]
source: https://code-maze.com/csharp-use-stringpool-to-reduce-string-allocations/
author: Osman Sokuoglu
title: 如何在 C# 中使用 StringPool 来减少字符串分配 - Code Maze
description: 本文探讨了如何使用 C# 中的 StringPool 来减少字符串分配，包括示例代码和基准测试部分。
---

# 如何在 C# 中使用 StringPool 来减少字符串分配 - Code Maze

> ## 摘录
>
> 本文探讨了如何使用 C# 中的 StringPool 来减少字符串分配，包括示例代码和基准测试部分。
>
> 原文 [How to Use StringPool to Reduce String Allocations in C# - Code Maze](https://code-maze.com/csharp-use-stringpool-to-reduce-string-allocations/)

---

在软件开发中，有效的内存管理扮演着至关重要的角色，它是提高我们应用程序性能的秘密武器。当使用 C# 代码工作时，管理字符串这一常见任务，显著影响我们程序的内存使用情况。由于 .NET 字符串是不可变的，重复分配重复的字符串可能会导致过度的内存消耗和性能下降。

为了解决这个问题，.NET 社区引入了 **StringPool**，这是一个强大的辅助类，通过重用字符串优化内存使用，从而提高程序效率。本文深入探讨了如何使用 **StringPool** 来减少字符串分配，提供了示例代码和基准测试部分，以全面理解这一概念。

要下载本文的源代码，您可以访问我们的 [GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/dotnet-performance/HowToUseStringPool)。

让我们从回顾一下字符串和 StringBuilder 开始。

## 回顾字符串和 StringBuilder

如我们已经提到的，.NET 中的字符串是不可变的，禁止在创建后更改它们的值。任何看似修改字符串的操作实际上都会生成一个新的字符串实例，导致增加了内存分配。相比之下，StringBuilder 提供了可变性，能够在不需要新实例的情况下修改其内容。这一属性使 StringBuilder 更适合需要大量字符串连接或操作的场景。

想要深入了解 StringBuilder，请探索我们的文章 [C# 中的 StringBuilder](https://code-maze.com/stringbuilder-csharp/)。

有了这个理解，让我们深入探讨 `StringPool`。

## 理解 StringPool

`StringPool` 主动管理一集合字符串实例，其主要目的是在生成大量字符串对象时减少内存分配，特别是来自字符或字节值缓冲区的字符串。它通过重用池中的现有字符串实例实现此目的，每次都不需要分配新的实例。

当我们的应用程序需要一个新字符串时，我们可以查询 `StringPool` 看是否已经存在一个匹配的版本。找到匹配后，它会检索现有实例而不是生成一个新的。这种方式有助于更有效的内存管理策略，特别是在需要重复创建相同字符串值的场景中。

`StringPool` 为管理字符串驻留提供了一种独特的数据结构，驻留是存储每个不同字符串的单一副本的方法。虽然语言运行时通常自动处理字符串驻留，但 `StringPool` **允许我们主动配置和重置池**。

### 语法和用法

要使用 `StringPool`，我们需要包含 [CommunityToolkit.HighPerformance](https://www.nuget.org/packages/CommunityToolkit.HighPerformance/) 包：

```
dotnet add package CommunityToolkit.HighPerformance
```

添加完毕后，让我们创建一个辅助类来探索使用场景：

```csharp
public class StringPoolHelper
{
    private readonly Dictionary<string, string> _cache = [];
    private StringPool _myPool;
    public bool Init(int poolSize)
    {
        _myPool = new StringPool(poolSize);
        var value1 = _myPool.GetOrAdd("codemaze");
        var value2 = _myPool.GetOrAdd("codemaze"u8, Encoding.UTF8);
        return ReferenceEquals(value1, value2);
    }
}
```

在这里，我们创建了一个 `StringPoolHelper` 类。我们包括了一个 `Init()` 方法，用于初始化 `StringPool` 的私有实例。我们提供一个 `poolSize` 以确定池的大小。最后，我们调用 `StringPool.GetOrAdd()` 两次，将相同的字符串添加到我们的池中。

我们的目标是展示第二次尝试添加实际上返回了相同的 `string` 实例，而不是创建一个新的。我们通过在最后一行调用 `Object.ReferenceEquals()` 来比较 `value1` 和 `value2` 实例的引用来实现这一点。

`GetOrAdd()` 方法作为 `StringPool` 的主要接口，具有三个重载：`GetOrAdd(string)`、`GetOrAdd(ReadOnlySpan<char>)` 和 `GetOrAdd(ReadOnlySpan<byte>, Encoding)`。在我们的示例中，我们使用了这些方法重载的第一个和最后一个。

现在，让我们调用 `Init()` 方法：

```csharp
var referenceEquals = StringPoolHelper.Init();
Console.WriteLine($"Shared Reference Equals : {referenceEquals}");
```

当我们运行并检查结果时，我们看到 `value1` 和 `value2` 的引用是相等的。换句话说，我们的池只创建了一次 `string` 实例。

### 属性

`StringPool` 类包含两个属性：

| 属性   | 描述                                           |
| ------ | ---------------------------------------------- |
| Shared | 静态属性，提供可重复使用的单例实例，用于访问。 |
| Size   | 实例属性，表示当前池中可以存储多少个字符串。   |

`StringPool.Shared` **实例有效地池化了字符串实例，提供了线程安全的访问，无需手动同步。** 它与 `ArrayPool.Shared` 类似，因为它们都为一般应用场景配置了最佳设置，提供了改进的性能和资源利用率。我们将在后续示例中将其应用优先考虑，而不是手动初始化自定义实例，**因为它优化了大多数应用场景。**

那么，让我们在实践中展示这些属性，我们从 `Size` 开始，创建一个 `GetMyPoolSize()` 方法，它返回我们在 `Init()` 方法中初始化的池的大小：

```csharp
public int GetMyPoolSize() => _myPool.Size;
```

现在，让我们看看静态 `StringPool.Shared` 属性：

```csharp
public static bool UseSharedInstance()
{
    var value1 = StringPool.Shared.GetOrAdd("codemaze");
    var value2 = StringPool.Shared.GetOrAdd("codemaze"u8, Encoding.UTF8);
    return ReferenceEquals(value1, value2);
}
```

在这里，我们引入了 `UseSharedInstance()` 方法，它与我们的 `Init()` 方法类似，但这次我们使用 `StringPool.Shared` 实例。因此，我们将在后续示例中优先利用它。

### 方法

`StringPool` 类提供了几个方法。我们已经考虑了 `GetOrAdd()` 方法。注意，这个方法有接受 `ReadOnlySpan<char>` 和 `ReadOnlySpan<Byte>, Encoding` 作为输入的重载。我们已经知道，这个方法检索一个与输入内容（转换为 Unicode）匹配的缓存字符串实例，并在与 `Encoding` 参数一起使用时，根据输入参数创建新的实例（如果未找到匹配）。

让我们回顾一些其他可用的方法：`Add(String)`——这个方法将一个字符串添加到池中。请注意，如果两次执行添加操作，池中只会添加一个字符串——因为这个方法内部检查了重复。`TryGet(ReadOnlySpan<Char>, out String)` 尝试检索一个与提供的输入内容匹配的缓存字符串实例（如果可用）。如果未找到值，则返回 `false`。`Reset()` 重置当前池实例及其关联的映射，使所有内部集合和数据结构恢复到初始状态。

## 在何处 StringPool 有助于减少字符串分配

让我们检查一些使用 `StringPool` 显著影响管理和最小化字符串分配的场景。首先，让我们定义一个辅助方法：

```csharp
private static string CombineSpan(ReadOnlySpan<char> first, ReadOnlySpan<char> second)
{
    var combinedSpan = SpanOwner<char>.Allocate(first.Length + second.Length);
    var combined = combinedSpan.Span;
    first.CopyTo(combined);
    second.CopyTo(combined[first.Length..]);
    return StringPool.Shared.GetOrAdd(combinedSpan.Span);
}
```

在这里，我们创建了一个 `CombineSpan()` 方法，它接受两个 `ReadOnlySpan<char>` 参数。（在我们的 GitHub 仓库中，我们实际上创建了两个重载，一个带有两个参数，一个带有三个参数，但为简洁起见，这里只显示了第一个）。我们使用 `ReadOnlySpan<char>` 对象是因为我们不想在方法中执行任何字符串连接。使用 `StringPool` 的目标是尽可能避免创建新的 `string` 对象。**由于字符串的不可变性，连接会导致创建一个新的字符串实例**。

为了进一步减少任何新的内存分配，我们还使用了来自高性能工具包的 `SpanOwner<char>`，它利用了共享的 [ArrayPool](https://code-maze.com/csharp-arraypool-memory-optimization/) 进行缓冲区租用。

在最后一行，我们使用 `SpanOwner<char>.Span` 值查询 `StringPool` 以检索字符串实例。如果值已存在于池中，则返回现有实例，否则，在返回之前将新字符串创建并添加到池中。

### 在缓存中使用 StringPool 减少字符串分配

在缓存场景中，当基于输入参数或标识符动态生成键时，使用 `StringPool` 来内部缓存键可以简化缓存查找操作并最小化内存使用：

```csharp
public bool AddUser(ReadOnlySpan<char> nameSpan, ReadOnlySpan<char> emailSpan)
{
    var cacheKey = CombineSpan("USER_", nameSpan);
    var cacheValue = StringPool.Shared.GetOrAdd(emailSpan);
    _cache[cacheKey] = cacheValue;
    return true;
}
public string GetUser(ReadOnlySpan<char> nameSpan)
{
    var cacheKey = CombineSpan("USER_", nameSpan);
    return _cache.TryGetValue(cacheKey, out var value) ? value : string.Empty;
}
```

在这个示例中，我们引入了两个方法，旨在管理缓存场景。`AddUser()` 方法负责缓存用户数据。我们通过调用辅助方法 `CombineSpan()` 构造缓存键，而不是针对每个请求生成新的缓存键。

接下来，我们尝试从我们的池中检索值（在本例中是电子邮件实例）。最后，使用我们的缓存键，我们设置缓存值。

以相反的方式，我们使用 `GetUser()` 方法从缓存中检索用户数据。我们再次利用我们的辅助方法来构造缓存键。然后，我们使用此键访问缓存值。如果未找到值，我们返回空字符串。

### 在请求 URL 管理中使用 StringPool 减少字符串分配

在 Web 应用程序中，常规处理和处理 URL。对频繁访问的 URL 段或模式进行内部处理，可以优化内存使用，从而加快 URL 处理速度。例如，我们的应用程序可能有一个公开可达的 API，我们可能想要跟踪来自特定客户端的请求数量。

为了处理这个需求，我们可以使用 `StringPool` 来减少字符串分配并提升整体应用性能，而不是通过创建字符串实例和字符串操作来处理：

```csharp
public static string GetHostName(ReadOnlySpan<char> urlSpan)
{
    var offset = urlSpan.IndexOf([':', '/', '/']);
    var start = offset == -1 ? 0 : offset + 3;
    var end = start + urlSpan[start..].IndexOf('/');
    if (end == -1)
        return string.Empty;
    var hostName = urlSpan[start..end];
    return StringPool.Shared.GetOrAdd(hostName);
}
```

在这里，我们从给定的 `urlSpan` 中提取主机名，它由 `ReadOnlySpan<char>` 表示。我们首先通过搜索 `://` 的出现来找到 URL 中主机名的起始位置。然后，通过搜索下一个 `/` 的出现来确定主机名的结束位置。最后，我们从共享池实例中获取 `hostName`，确保高效的内存利用，并可能防止重复分配。

### 在本地化中使用 StringPool 减少字符串分配

在国际化和本地化任务中，当我们需要将字符串翻译成不同语言时，使用 `StringPool` 对本地化字符串的键或标识符进行内部处理，可以提高性能并简化语言资源管理：

```csharp
public string Translate(ReadOnlySpan<char> keySpan, ReadOnlySpan<char> langSpan)
{
    const string prefix = "LOCALIZATION_";
    var calculatedKey = CombineSpan(prefix, langSpan, keySpan);
    _cache.TryGetValue(calculatedKey, out var value);
    return value ?? calculatedKey;
}
```

在这个场景中，我们引入了 `Translate()` 方法以获取指定语言中的键的翻译。我们通过调用辅助方法 `CombineSpan()` 来组合 `LOCALIZATION_` 前缀、`langSpan` 值和提供的 `keySpan`，以形成翻译键。然后，我们尝试从翻译缓存中检索本地化值，并在翻译缓存中找到结果时返回，或者如果未找到则返回计算出的键。

## 性能比较

到目前为止，我们已经探讨了 `StringPool` 的概念以及其在优化字符串分配中的潜力。现在，我们准备就 `string`、`StringBuilder` 和 `StringPool` 在速度、内存分配和效率方面的性能进行比较。为了简化这一比较，我们将利用 [BenchmarkDotNet](https://code-maze.com/benchmarking-csharp-and-asp-net-core-projects/) 库进行基准测试。

### 准备工作

我们将创建一个包含 1024 个字符的字符数组。然后在每个基准测试方法中，我们将循环指定的迭代次数，从字符数组中创建长度为 64 的字符串。我们将对迭代次数为 1,000；10,000；和 100,000 的情况进行基准测试。

来看看这些方法：

````csharp
[Benchmark]
public IList<string> UseString()
{
    _dest.Clear();
    var startIndex = 0;
    for (var i = 0; i < Iterations; i++)
    {
        if (startIndex + ChunkSize > _charArray.Length)
        {
            startIndex = 0;
        }
        _dest.Add(new string(_charArray, startIndex, ChunkSize));
        startIndex += ChunkSize;
    }
    return _dest;
}
[Benchmark]
public IList<string> UseStringPool()
{
    _dest.Clear();
    var startIndex = 0;
    for (var i = 0; i < Iterations; i++)
    {
        if (startIndex + ChunkSize > _charArray.Length)
        {
            startIndex = 0;
        }
        ReadOnlySpan<char> span = _charArray.AsSpan(startIndex, ChunkSize);
        _dest.Add(StringPool.Shared.GetOrAdd(span));
        startIndex += ChunkSize;
    }
    return _dest;
}
```markdown
[Benchmark]
public IList<string> UseStringBuilder()
{
    _dest.Clear();
    var sb = new StringBuilder();
    var startIndex = 0;
    for (var i = 0; i < Iterations; i++)
    {
        if (startIndex + ChunkSize > _charArray.Length)
        {
            startIndex = 0;
        }
        sb.Append(_charArray.AsSpan(startIndex, ChunkSize));
        _dest.Add(sb.ToString());
        sb.Clear();
        startIndex += ChunkSize;
    }
    return _dest;
}
````

在这里，我们为 `string`、`StringPool` 和 `StringBuilder` 定制了三种基准测试方法。在循环的每次迭代中，我们基于来自我们的 `_charArray` 的一个块创建一个字符串实例。然后我们将每个字符串存储在列表中并最终返回列表。这有助于防止字符串创建被优化掉。

### 基准测试

现在我们准备运行我们的基准测试并分析结果。**重要的是要注意，由于** `StringPool` **的重点是减少内存分配，我们在基准测试中的主要关注点更多是在分配上而不是速度**：

| 方法             | 迭代次数 |         平均 |      Gen0 |      Gen1 |     Gen2 | 分配的内存 |
| ---------------- | -------- | -----------: | --------: | --------: | -------: | ---------: |
| UseString        | 1000     |     22.00 us |   69.4885 |    6.2256 |        - |   152000 B |
| UseStringBuilder | 1000     |     30.27 us |   68.5425 |    9.8267 |        - |   152424 B |
| UseStringPool    | 1000     |     90.21 us |         - |         - |        - |          - |
|                  |          |              |           |           |          |            |
| UseString        | 10000    |    388.20 us |  273.4375 |  226.0742 |        - |  1520000 B |
| UseStringBuilder | 10000    |    435.84 us |  272.9492 |  226.5625 |        - |  1520424 B |
| UseStringPool    | 10000    |    924.97 us |         - |         - |        - |          - |
|                  |          |              |           |           |          |            |
| UseStringPool    | 100000   |  8,882.90 us |         - |         - |        - |        6 B |
| UseStringBuilder | 100000   | 17,424.78 us | 3000.0000 | 2062.5000 | 562.5000 | 15200686 B |
| UseString        | 100000   | 19,311.59 us | 3000.0000 | 2093.7500 | 562.5000 | 15200250 B |

正如我们的基准测试结果所示，`StringPool` **在有效的内存管理方面表现出色，在所有迭代中展示最小的内存分配。**有趣的是，当我们进行到100,000次迭代时，我们看到 `UseStringPool` 方法大约比其他方法性能好两倍。这是由于对垃圾收集器加大的压力，这可以通过检查基准测试的 Gen0、Gen1 和 Gen2 列来看出。这正是 `StringPool` 被创造出来的那种情景。

基准测试有助于强调基于我们应用程序的独特要求和限制选择最合适方法的重要性。`StringPool` 不一定是日常任务的正确工具，但在那些我们预期将生成几个重复字符串的场景中，它可以帮助减少内存压力并可能提高应用程序性能。

## 结论

在本文中，我们深入探讨了 C# 中 `StringPool` 的概念以及**我们如何使用 StringPool 来减少字符串分配，从而提高内存效率。**通过掌握 C# 中字符串管理的细节并有效地使用 StringPool，我们可以显著提升我们应用程序的性能，尤其是**在重复使用字符串值的情况下。**
