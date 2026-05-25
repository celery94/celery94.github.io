---
title: "IAsyncEnumerable<T>：流式处理数据，不把所有东西塞进内存"
description: "用 IAsyncEnumerable<T> 替换 ToListAsync()，将内存从 O(n) 压到 O(1)。本文提供 4 个生产级模式（EF Core、HttpClient、文件流、ASP.NET Core Controller），以及 4 种常见坑和修复方法。"
pubDatetime: 2026-05-25T07:45:00+08:00
tags:
  - C#
  - .NET
  - ASP.NET Core
  - 性能优化
  - 异步编程
author: "celery94"
ogImage: "../../assets/827/01-cover.png"
---

![IAsyncEnumerable 流式处理](../../assets/827/01-cover.png)

> 原文：[IAsyncEnumerable\<T\> in C#: Streaming Data Without Loading Everything into Memory](https://adrianbailador.github.io/blog/53-iasyncenumerable-csharp-streaming-data/)
> 作者：Adrian Bailador · Apr 05, 2026

---

我的 API 在生产环境崩了。500,000 条数据库记录，一个 `List<T>`，加上 8GB 内存的服务器。算术根本行不通。

我盯着日志看了两个小时才弄明白发生了什么。修复只用了十分钟。这就是我学到的经验——希望能帮你省去同样的麻烦。

## 问题所在

你肯定写过这种代码：

```csharp
// ❌ 问题：100 万条记录全部加载进内存
public async Task<List<LogEntry>> GetAllLogsAsync()
{
    return await _context.LogEntries.ToListAsync(); // 定时炸弹
}
```

数据量少时没问题。但当数据集超出 RAM 容量的那一天，这个无辜的 `ToListAsync()` 就变成了定时炸弹。

## IAsyncEnumerable\<T\> 是什么？

C# 8.0（.NET Core 3.0）引入的 `IAsyncEnumerable<T>` 让你能**异步地流式处理数据**——逐条处理到达的数据，而不是在处理前把整个集合装进内存。就像逐页阅读一本书，而不是先把整本书复印一遍。

```csharp
// ✅ 解决方案：数据到达时流式处理
public IAsyncEnumerable<LogEntry> StreamLogsAsync()
{
    return _context.LogEntries.AsAsyncEnumerable(); // 内存友好
}
```

---

## 四个生产级模式

以下是最常用的四种模式——都是真正上过生产的东西，不是理论。

### 模式一：Entity Framework Core 流式查询

这是大多数人的起点，也有充分的理由。如果你用 EF Core 且有持续增长的表，迟早需要这个模式。

```csharp
public class LogRepository
{
    private readonly AppDbContext _context;

    public LogRepository(AppDbContext context)
    {
        _context = context;
    }

    /// <summary>
    /// 按条件流式读取日志，不把所有数据加载进内存。
    /// WARNING: 谨慎配合 OrderBy/Limit 使用。
    /// </summary>
    public async IAsyncEnumerable<LogEntry> StreamLogsAsync(
        DateTime from,
        DateTime to,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        await foreach (var log in _context.LogEntries
            .Where(l => l.Timestamp >= from && l.Timestamp <= to)
            .AsAsyncEnumerable()
            .WithCancellation(ct))
        {
            yield return log;
        }
    }

    /// <summary>
    /// 分批导出以防止连接超时。
    /// </summary>
    public async IAsyncEnumerable<IReadOnlyList<LogEntry>> StreamBatchedLogsAsync(
        int batchSize = 1000,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        var query = _context.LogEntries
            .OrderBy(l => l.Id)
            .AsAsyncEnumerable();

        var batch = new List<LogEntry>(batchSize);

        await foreach (var log in query.WithCancellation(ct))
        {
            batch.Add(log);

            if (batch.Count >= batchSize)
            {
                yield return batch.ToList();
                batch.Clear();
            }
        }

        // 不要漏掉最后一个不足 batchSize 的批次
        if (batch.Count > 0)
            yield return batch;
    }
}
```

### 模式二：HttpClient 流式 JSON 解析

返回数千条记录的第三方 API 出乎意料地常见。没有流式处理时，你要缓冲完整响应才能反序列化第一个对象。这里的关键是 `HttpCompletionOption.ResponseHeadersRead`——别忘了加。

```csharp
public class StreamingApiClient
{
    private readonly HttpClient _httpClient;
    private readonly JsonSerializerOptions _jsonOptions;

    public StreamingApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            DefaultBufferSize = 4096 // 根据你的 payload 大小调整
        };
    }

    /// <summary>
    /// 从 NDJSON 端点流式获取数据。
    /// 每行是一个独立的 JSON 对象。
    /// </summary>
    public async IAsyncEnumerable<T> StreamFromNdJsonAsync<T>(
        string url,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        using var response = await _httpClient.GetAsync(
            url,
            HttpCompletionOption.ResponseHeadersRead, // 关键：流式，不缓冲
            ct);

        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        using var reader = new StreamReader(stream, Encoding.UTF8);

        string? line;
        while ((line = await reader.ReadLineAsync(ct)) != null)
        {
            if (string.IsNullOrWhiteSpace(line))
                continue;

            // 逐行独立反序列化
            var item = JsonSerializer.Deserialize<T>(line, _jsonOptions);

            if (item != null)
                yield return item;
        }
    }

    /// <summary>
    /// 使用 System.Text.Json 内置异步反序列化流式处理。
    /// 要求 JSON 数组格式：[{}, {}, {}]
    /// </summary>
    public async IAsyncEnumerable<T> StreamJsonArrayAsync<T>(
        string url,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        using var response = await _httpClient.GetAsync(
            url,
            HttpCompletionOption.ResponseHeadersRead,
            ct);

        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(ct);

        await foreach (var item in JsonSerializer.DeserializeAsyncEnumerable<T>(
            stream,
            _jsonOptions,
            ct))
        {
            if (item != null)
                yield return item;
        }
    }
}
```

### 模式三：文件处理流水线

CSV 导入、日志分析、数据迁移——任何逐行读取文件并处理每行的场景。关键洞察：你可以把多个 `IAsyncEnumerable<T>` 方法串成流水线，无论文件多大，内存占用都保持不变。

```csharp
public class LogFileProcessor
{
    /// <summary>
    /// 在流水线中读取、转换、写入日志。
    /// 无论文件多大，内存使用量始终恒定。
    /// </summary>
    public async IAsyncEnumerable<ProcessedLog> ProcessLogFileAsync(
        string filePath,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        await foreach (var rawLog in ReadLinesAsync(filePath, ct))
        {
            // 实时转换——无内存堆积
            if (TryParseLog(rawLog, out var parsed))
            {
                var enriched = await EnrichLogAsync(parsed, ct);
                yield return enriched;
            }
        }
    }

    private static async IAsyncEnumerable<string> ReadLinesAsync(
        string path,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        using var reader = new StreamReader(path, Encoding.UTF8);

        string? line;
        while ((line = await reader.ReadLineAsync(ct)) != null)
        {
            yield return line;
        }
    }

    private static bool TryParseLog(string raw, out ParsedLog parsed)
    {
        // 你的解析逻辑
        parsed = default!;
        return true;
    }

    private static async Task<ProcessedLog> EnrichLogAsync(
        ParsedLog log,
        CancellationToken ct)
    {
        // 异步丰富（例如查询用户信息）
        await Task.Delay(1, ct); // 模拟异步操作
        return new ProcessedLog(log);
    }
}

public record ParsedLog(string Timestamp, string Level, string Message);
public record ProcessedLog(ParsedLog Original);
```

### 模式四：Controller Action 流式响应

ASP.NET Core 原生支持 `IAsyncEnumerable<T>` 返回类型——自动序列化为 NDJSON，并立即开始向客户端发送数据。客户端不需要等待完整数据集；第一条记录就绪后就立刻开始接收。

```csharp
[ApiController]
[Route("api/[controller]")]
public class ReportsController : ControllerBase
{
    private readonly IReportService _reportService;

    public ReportsController(IReportService reportService)
    {
        _reportService = reportService;
    }

    /// <summary>
    /// 直接向客户端流式传输 CSV 数据。
    /// 客户端立即开始接收，服务器无缓冲。
    /// </summary>
    [HttpGet("export")]
    public IAsyncEnumerable<ReportRow> ExportData(
        [FromQuery] DateTime from,
        [FromQuery] DateTime to,
        CancellationToken ct)
    {
        // ASP.NET Core 自动将 IAsyncEnumerable 序列化为 NDJSON
        return _reportService.StreamReportAsync(from, to, ct);
    }

    /// <summary>
    /// 自定义 Server-Sent Events (SSE) 流式传输。
    /// </summary>
    [HttpGet("live-events")]
    public async IAsyncEnumerable<ServerSentEvent> GetLiveEvents(
        [EnumeratorCancellation] CancellationToken ct)
    {
        await foreach (var evt in _reportService.SubscribeToEventsAsync(ct))
        {
            yield return new ServerSentEvent
            {
                Id = evt.Id,
                Event = evt.Type,
                Data = JsonSerializer.Serialize(evt.Payload)
            };
        }
    }
}

public record ReportRow(string Id, string Name, decimal Value);
public record ServerSentEvent(string Id, string Event, string Data);
```

---

## 性能对比：数字说话

### 旧方式：List（Before）

```csharp
// 内存：O(n) — 随数据集大小线性增长
// 首条输出时间：O(n) — 等待全部数据
public async Task<List<LargeRecord>> ProcessAllRecordsAsync()
{
    var allRecords = await _repository.GetAllAsync();

    var processed = new List<LargeRecord>();
    foreach (var record in allRecords)
    {
        processed.Add(await ProcessAsync(record));
    }

    return processed;
}

// 调用侧——内存在这里暴涨
var results = await ProcessAllRecordsAsync();
foreach (var item in results)
{
    await WriteToDiskAsync(item);
}
```

**100 万条记录 × 100KB/条——实际发生的事：**

- 峰值内存：~95 GB（是的，GB）
- 首条输出时间：等待 45 秒
- 结果：`OutOfMemoryException`——服务器先于你放弃

### 新方式：IAsyncEnumerable（After）

```csharp
// 内存：O(1) — 无论数据集多大，始终恒定
// 首条输出时间：O(1) — 立即流式传输
public async IAsyncEnumerable<LargeRecord> ProcessAllRecordsAsync(
    [EnumeratorCancellation] CancellationToken ct = default)
{
    await foreach (var record in _repository.StreamAllAsync(ct))
    {
        yield return await ProcessAsync(record);
    }
}

// 调用侧——内存占用恒定
await foreach (var item in ProcessAllRecordsAsync().WithCancellation(ct))
{
    await WriteToDiskAsync(item);
}
```

**同样 100 万条记录——完全不同的结果：**

- 峰值内存：~150 MB（无论数据集多大，始终恒定）
- 首条输出时间：50ms——客户端几乎立即开始接收
- 结果：流式平稳，服务器保持健康

---

## 常见错误及修复

每一条我都踩过，你不必重蹈覆辙。

### 错误一：忘记 CancellationToken

```csharp
// ❌ 糟糕：流式中途无法取消
public async IAsyncEnumerable<Item> GetItemsAsync()
{
    await foreach (var item in _source.GetAsync())
    {
        yield return item; // 无法取消！
    }
}

// ✅ 正确：始终包含取消支持
public async IAsyncEnumerable<Item> GetItemsAsync(
    [EnumeratorCancellation] CancellationToken ct = default)
{
    await foreach (var item in _source.GetAsync().WithCancellation(ct))
    {
        yield return item;
    }
}
```

**关键点**：`[EnumeratorCancellation]` 特性让调用方能通过 `.WithCancellation(ct)` 传入取消令牌。没有它，你的流式操作就是无法被客户端断开连接所打断的黑洞。

### 错误二：用 ToListAsync() 把流式缓冲掉了

```csharp
// ❌ 糟糕：你刚把自己的努力全抵消掉了
public async Task<List<Item>> GetItemsAsync() // 返回 List<T>，不是 IAsyncEnumerable
{
    var items = new List<Item>();
    await foreach (var item in _source.GetAsync())
    {
        items.Add(item);
    }
    return items;
}

// ✅ 正确：直接返回 IAsyncEnumerable<T>
public IAsyncEnumerable<Item> GetItemsAsync(CancellationToken ct)
{
    return _source.GetAsync(); // 直接传递
}
```

### 错误三：资源过早释放

```csharp
// ❌ 糟糕：reader 在第一次 yield 时就被释放
public async IAsyncEnumerable<string> ReadFileAsync(string path)
{
    using var reader = new StreamReader(path); // 第一次 yield 时即释放！

    while (await reader.ReadLineAsync() is { } line)
    {
        yield return line; // reader 已经释放了
    }
}

// ✅ 正确：保持作用域存活
public async IAsyncEnumerable<string> ReadFileAsync(
    string path,
    [EnumeratorCancellation] CancellationToken ct = default)
{
    using var reader = new StreamReader(path);

    try
    {
        while (await reader.ReadLineAsync(ct) is { } line)
        {
            yield return line;
        }
    }
    finally
    {
        // 迭代完成或中断时才释放 reader
    }
}
```

### 错误四：未配置 DbContext 生命周期

```csharp
// ❌ 糟糕：ASP.NET Core 中，Scoped DbContext 在流式中途被释放
[HttpGet("stream")]
public async IAsyncEnumerable<Order> GetOrders()
{
    var db = _serviceProvider.GetRequiredService<OrderDbContext>();
    // Action 方法返回后，db 就会被释放！

    await foreach (var order in db.Orders.AsAsyncEnumerable())
    {
        yield return order; // DbContext 在这里已被释放
    }
}

// ✅ 正确：使用工厂模式用于流式场景
public class StreamingOrderService
{
    private readonly IDbContextFactory<OrderDbContext> _contextFactory;

    public async IAsyncEnumerable<Order> StreamOrdersAsync(
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        await using var db = await _contextFactory.CreateDbContextAsync(ct);

        await foreach (var order in db.Orders.AsAsyncEnumerable().WithCancellation(ct))
        {
            yield return order;
        }
    }
}
```

---

## 何时用，何时不用

**适合流式处理的场景：**
- 超过几千条的数据集
- 内存资源受限的环境
- 需要实时传递给客户端的数据
- 文件处理与数据迁移

**不适合流式处理的场景：**
- 数据量小（几百条以内）
- 需要 `Count()`、`OrderBy()`、聚合等需要全集的操作
- 结果必须随机访问（索引访问）

---

## 小结

同样 100 万条记录，选择不同，结果天差地别：

| | List\<T\> | IAsyncEnumerable\<T\> |
|---|---|---|
| 内存复杂度 | O(n) | O(1) |
| 首条输出时间 | 等待全部完成 | 立即 |
| 100 万×100KB | ~95 GB，OOM | ~150 MB，稳定 |
| 可取消 | 不便 | 内置支持 |

`IAsyncEnumerable<T>` 不是用来替换所有 `List<T>` 的银弹——但当你处理大数据集、文件流、外部 API 响应或实时事件时，它就是那个让服务器不崩溃的关键。

---

## 参考链接

- [IAsyncEnumerable\<T\> in C#: Streaming Data Without Loading Everything into Memory](https://adrianbailador.github.io/blog/53-iasyncenumerable-csharp-streaming-data/) — Adrian Bailador
- [IAsyncEnumerable\<T\> Interface — Microsoft Docs](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.iasyncenumerable-1)
- [Async streams — C# Language Reference](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/statements/iteration-statements#await-foreach)
