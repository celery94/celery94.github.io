---
pubDatetime: 2026-07-01T11:57:30+08:00
title: "HttpClient 流式传输：用 ResponseHeadersRead 和 ReadAsStreamAsync 处理海量数据"
description: "默认的 HttpClient 会把整个响应体缓存到内存再交给你，下载 1GB 文件就会占用 1GB 堆内存。本文讲解如何用 HttpCompletionOption.ResponseHeadersRead 开启流式读取，配合 ReadAsStreamAsync、DeserializeAsyncEnumerable、SseParser 等 API，将峰值内存从响应尺寸级降到缓冲区级（约 80KB），覆盖大文件下载、JSON 数组流式反序列化和 Server-Sent Events 三种真实场景。"
tags: ["C#", "HttpClient", ".NET", "Streaming"]
slug: "httpclient-streaming-responseheadersread-readasstreamasync"
ogImage: "../../assets/916/01-cover.png"
source: "https://www.devleader.ca/2026/06/30/httpclient-streaming-in-c-httpcompletionoption-readasstreamasync-and-serversent-events"
---

如果你用 `HttpClient` 下载过大文件或拉取过巨大的 JSON 载荷，大概率遇到过内存陡增的情况。这不是 bug，是默认行为——整个响应体会先完整下载到内存，控制权才交还给你。在 .NET 10 中，解决这个问题的工具已经足够成熟，而且比很多人想象的好用。

这篇文章会逐一拆解 `HttpCompletionOption.ResponseHeadersRead`、`ReadAsStreamAsync`、`JsonSerializer.DeserializeAsyncEnumerable` 和 .NET 内置的 Server-Sent Events 支持，并给出可以直接复制使用的代码示例。

## 默认问题：响应被全量缓存

调用 `GetStringAsync`、`GetByteArrayAsync` 或使用默认 completion option 的 `SendAsync` 时，ASP.NET 的 HttpClient 会在内部把整个响应体下载并缓存完，才让你的 `await` 返回。

```csharp
using var client = new HttpClient();

// 这一行返回之前，整个响应体已经全部在内存里了
string json = await client.GetStringAsync(
    "https://api.example.com/large-dataset");

// 可能 500MB 已经在堆上了——你还没开始处理
```

对于几十 KB 的小请求，这不是问题。对于 10MB 的 JSON 文件，有点浪费。对于 1GB 的文件下载、实时数据流或者永不结束的 SSE 连接，这就有问题了。

内存占用大致和响应体大小成正比——.NET 必须把数据存在某处。流式方案彻底改变了这个模型：不再是「全部下载，再处理」，而是「边收边处理」。

## HttpCompletionOption：两种完成模式

`HttpCompletionOption` 枚举只有两个值，它俩的差异就是 HttpClient 流式传输的关键。

**`ResponseContentRead`**（默认值）的意思是：任务要等到整个响应体下载并缓存完毕才算完成。`await` 不会在最后一个字节进内存之前返回。这是安全、简单的默认设置——但意味着完整载荷时刻都在内存里。

**`ResponseHeadersRead`** 的意思是：任务只要等到 HTTP 头部到达就返回，不等响应体。你的 `await` 很快返回，此时响应体还没开始下载——你拿到的是一个可以逐步读取的 `Stream`。

可以把它类比成订一本书：`ResponseContentRead` 是在印刷厂仓库外面等着整批印刷完成然后一次性全拿走；`ResponseHeadersRead` 是第一页刚下印刷机就接到电话——你可以边印边读。

```csharp
using var client = new HttpClient();

// 传 ResponseHeadersRead，头部一到就交还控制权
using var response = await client.SendAsync(
    new HttpRequestMessage(HttpMethod.Get,
        "https://api.example.com/large-dataset"),
    HttpCompletionOption.ResponseHeadersRead);

response.EnsureSuccessStatusCode();

// response.Content 此时还是流源，不是缓冲区
```

关键点：在这个阶段 `response.Content` 仍然连着网络套接字。数据是从服务端通过流在你读取时才流入的。如果你从不读取这个流，数据基本不会进入你的进程内存。

## ReadAsStreamAsync：拿到原始流

结合 `ResponseHeadersRead` 拿到响应之后，`ReadAsStreamAsync` 给你底层网络流的直接访问权。

```csharp
using System.Net.Http;

using var client = new HttpClient();

using var response = await client.SendAsync(
    new HttpRequestMessage(HttpMethod.Get,
        "https://logs.example.com/stream"),
    HttpCompletionOption.ResponseHeadersRead);

response.EnsureSuccessStatusCode();

// ReadAsStreamAsync 返回原始网络流——不缓存
await using var stream = await response.Content.ReadAsStreamAsync();
using var reader = new StreamReader(stream);

while (!reader.EndOfStream)
{
    var line = await reader.ReadLineAsync();
    if (line is not null)
    {
        Console.WriteLine(line);
    }
}
```

注意 stream 前的 `await using`。`ReadAsStreamAsync` 返回的 `Stream` 包装了一个活跃的网络连接，正确 dispose 很重要——它告诉 HTTP 基础设施你已完成，连接可以归还到连接池。

如果你需要字节级控制，也可以手动读缓冲区：

```csharp
await using var stream = await response.Content.ReadAsStreamAsync();

var buffer = new byte[4096];
int bytesRead;

while ((bytesRead = await stream.ReadAsync(buffer)) > 0)
{
    // 处理 buffer[0..bytesRead]
}
```

这是 HttpClient 流式传输的基础。后续的进度汇报、JSON 反序列化、SSE 都建立在这个模式之上。

## 内存效率：前后对比

两种方式的内存差距非常明显。

**之前——缓存模式（ResponseContentRead，默认）：**

```csharp
using var client = new HttpClient();

// 内存峰值：整份响应加载完才交给你
byte[] data = await client.GetByteArrayAsync(
    "https://files.example.com/export-1gb.bin");

// 峰值内存 = 响应大小（1GB 文件就占 1GB）
Console.WriteLine($"Downloaded {data.Length:N0} bytes");
```

**之后——流式模式（ResponseHeadersRead + ReadAsStreamAsync）：**

```csharp
using var client = new HttpClient();

using var response = await client.SendAsync(
    new HttpRequestMessage(HttpMethod.Get,
        "https://files.example.com/export-1gb.bin"),
    HttpCompletionOption.ResponseHeadersRead);

response.EnsureSuccessStatusCode();

await using var stream = await response.Content.ReadAsStreamAsync();
await using var fileStream = new FileStream(
    "export-1gb.bin", FileMode.Create);

// 分块拷贝流——内存里一次只有一个缓冲区
await stream.CopyToAsync(fileStream);

// 峰值内存 ≈ 缓冲区大小（CopyToAsync 默认约 80KB）
Console.WriteLine("Download complete");
```

缓式版本中峰值内存跟随响应大小增长——1GB 响应意味着 1GB 堆；流式版本中峰值内存大致恒定在缓冲区大小（`CopyToAsync` 默认约 80KB）。总传输数据一样，只是内存曲线完全不同。

对于大型 JSON 载荷，差距更大，因为缓存模式在你摸到任何数据之前，已经同时分配了原始字节数组和反序列化后的对象图。

## 流式 JSON 反序列化：DeserializeAsyncEnumerable

`System.Text.Json` 从 .NET 5 起就支持通过 `JsonSerializer.DeserializeAsyncEnumerable<T>` 进行流式反序列化。这个方法从流中读取 JSON 数组，每解析出一个元素就 yield 出去，不先把整个数组载入内存。

服务端响应必须是一个 JSON 数组（或者是换行分隔 JSON）。满足这个前提后，客户端侧代码是这样：

```csharp
using System.Net.Http;
using System.Text.Json;

public sealed record WeatherReading(
    string Station,
    DateTimeOffset Timestamp,
    double TemperatureCelsius);

public static async Task ProcessWeatherDataAsync(
    HttpClient client, CancellationToken cancellationToken)
{
    using var response = await client.SendAsync(
        new HttpRequestMessage(HttpMethod.Get,
            "https://api.example.com/weather/readings"),
        HttpCompletionOption.ResponseHeadersRead,
        cancellationToken);

    response.EnsureSuccessStatusCode();

    await using var stream = await response.Content
        .ReadAsStreamAsync(cancellationToken);

    // 每解析出一个 WeatherReading 就 yield
    // 数组的其余部分还没下载
    await foreach (var reading in JsonSerializer
        .DeserializeAsyncEnumerable<WeatherReading>(
            stream,
            cancellationToken: cancellationToken))
    {
        await ProcessReadingAsync(reading, cancellationToken);
    }
}

private static async Task ProcessReadingAsync(
    WeatherReading reading, CancellationToken cancellationToken)
{
    // 你的业务逻辑——每条记录到达时调用
    Console.WriteLine(
        $"{reading.Station}: {reading.TemperatureCelsius:F1}°C " +
        $"at {reading.Timestamp}");
    await Task.Yield(); // 模拟异步工作
}
```

这样就实现了流式传输 + 增量反序列化。返回百万条记录的 JSON 数组，也能一条一条流过，内存开销只相当于一条记录——而不是一百万条。

需要考虑的一个点是流中可能出现格式损坏的 JSON。如果服务端在数组中间发出一个损坏或截断的元素，`DeserializeAsyncEnumerable` 会在解析失败的节点抛出 `JsonException`。坏元素之前已经 yield 的记录已经被处理了——没法「撤回」。正确策略是用 try/catch 包住 `await foreach`，判断解析失败是不可恢复的还是可以接受的：

```csharp
public static async Task ProcessWeatherDataSafeAsync(
    HttpClient client, CancellationToken cancellationToken)
{
    using var response = await client.SendAsync(
        new HttpRequestMessage(HttpMethod.Get,
            "https://api.example.com/weather/readings"),
        HttpCompletionOption.ResponseHeadersRead,
        cancellationToken);

    response.EnsureSuccessStatusCode();

    await using var stream = await response.Content
        .ReadAsStreamAsync(cancellationToken);

    try
    {
        await foreach (var reading in JsonSerializer
            .DeserializeAsyncEnumerable<WeatherReading>(
                stream,
                cancellationToken: cancellationToken))
        {
            if (reading is null) continue;
            await ProcessReadingAsync(reading, cancellationToken);
        }
    }
    catch (JsonException ex)
    {
        // 部分数据已经被处理——记日志后决定是否重试
        Console.WriteLine(
            $"JSON parse failed mid-stream: {ex.Message}");
    }
}
```

这在实践中很有意义，因为流式 API 在高负载下有时会发出不完整响应。把第一批成功反序列化的记录视为有用数据而不是整批丢弃，通常对分析和遥测管线来说是正确的选择。

## 大文件下载与进度报告

流式传输天然支持进度报告，而使用 `GetByteArrayAsync` 这类缓存辅助方法是不可能做到的——等你拿到字节数组时下载早结束了。流式模式下你能观察每一块数据。

```csharp
using System.Net.Http;

public static async Task DownloadWithProgressAsync(
    HttpClient client,
    string url,
    string outputPath,
    IProgress<double>? progress,
    CancellationToken cancellationToken = default)
{
    using var response = await client.SendAsync(
        new HttpRequestMessage(HttpMethod.Get, url),
        HttpCompletionOption.ResponseHeadersRead,
        cancellationToken);

    response.EnsureSuccessStatusCode();

    // Content-Length 可能不存在（如 chunked transfer encoding）
    long? totalBytes = response.Content.Headers.ContentLength;

    await using var networkStream = await response.Content
        .ReadAsStreamAsync(cancellationToken);
    await using var fileStream = new FileStream(
        outputPath,
        FileMode.Create,
        FileAccess.Write,
        FileShare.None,
        bufferSize: 81920,
        useAsync: true);

    var buffer = new byte[81920];
    long bytesDownloaded = 0;
    int read;

    while ((read = await networkStream.ReadAsync(
        buffer, cancellationToken)) > 0)
    {
        await fileStream.WriteAsync(
            buffer.AsMemory(0, read), cancellationToken);
        bytesDownloaded += read;

        if (progress is not null && totalBytes.HasValue)
        {
            progress.Report(
                (double)bytesDownloaded / totalBytes.Value * 100.0);
        }
    }
}

// 用法
var progressReporter = new Progress<double>(
    pct => Console.Write($"\r{pct:F1}%"));
await DownloadWithProgressAsync(client,
    "https://files.example.com/large.zip",
    "large.zip",
    progressReporter);
```

`IProgress<T>` 模式和 UI 框架对接也很流畅——传入一个把更新调度到 UI 线程的 `Progress<double>`，就能在 WPF 或 MAUI 应用中获得实时下载进度，不额外适配逻辑。

## Server-Sent Events 与 HttpClient

Server-Sent Events 是一种基于纯 HTTP 的服务端到客户端单向实时数据协议。每条事件的格式是 `data: <payload>`，以空行分隔。连接一直保持开启，服务端按需推送。

在 C# 中用 HttpClient 消费 SSE 天然适合 `ResponseHeadersRead`。从 .NET 9 开始还可以用 `System.Net.ServerSentEvents` 命名空间中的 `SseParser` 进行健壮解析。先理解协议层面的做法，再看惯用方式。

**底层 SSE 读取：**

```csharp
using System.Net.Http;
using System.Net.Http.Headers;
using System.Runtime.CompilerServices;

public static async IAsyncEnumerable<string> ReadSseDataAsync(
    HttpClient client,
    string url,
    [EnumeratorCancellation] CancellationToken cancellationToken = default)
{
    using var request = new HttpRequestMessage(HttpMethod.Get, url);

    // 服务端期望 Accept: text/event-stream 来启用 SSE 模式
    request.Headers.Accept.Add(
        new MediaTypeWithQualityHeaderValue("text/event-stream"));

    using var response = await client.SendAsync(
        request,
        HttpCompletionOption.ResponseHeadersRead,
        cancellationToken);

    response.EnsureSuccessStatusCode();

    await using var stream = await response.Content
        .ReadAsStreamAsync(cancellationToken);
    using var reader = new StreamReader(stream);

    while (!cancellationToken.IsCancellationRequested)
    {
        var line = await reader.ReadLineAsync(cancellationToken);

        if (line is null) break; // 服务端关闭了连接

        if (line.StartsWith("data: ", StringComparison.Ordinal))
        {
            yield return line["data: ".Length..];
        }
        // 跳过 event:、id:、retry: 行和空白分隔行
    }
}
```

**.NET 10 中使用 SseParser 的惯用写法：**

```csharp
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.ServerSentEvents;

public static async Task ConsumeStockPricesAsync(
    HttpClient client, CancellationToken cancellationToken)
{
    using var request = new HttpRequestMessage(HttpMethod.Get,
        "https://api.example.com/stocks/stream");
    request.Headers.Accept.Add(
        new MediaTypeWithQualityHeaderValue("text/event-stream"));

    using var response = await client.SendAsync(
        request,
        HttpCompletionOption.ResponseHeadersRead,
        cancellationToken);

    response.EnsureSuccessStatusCode();

    await using var stream = await response.Content
        .ReadAsStreamAsync(cancellationToken);

    // SseParser 处理多行 data、事件类型筛选和 id 追踪
    await foreach (SseItem<string> sseItem in SseParser
        .Create(stream).EnumerateAsync(cancellationToken))
    {
        Console.WriteLine($"[{sseItem.EventType}] {sseItem.Data}");
    }
}
```

`SseParser` 实现了完整的 SSE 规范——多行 `data` 字段、`event` 类型过滤、`id` 追踪——不用自己解析协议。

几个关键 API：

- `SseParser.Create(stream)` — 为普通 Stream 创建解析器，默认返回 `SseItem<string>`
- `SseParser.Create(stream, dataParser)` — 加上自定义 `dataParser` 委托，可以解析出 `SseItem<T>` 类型
- `.EnumerateAsync(cancellationToken)` — 返回 `IAsyncEnumerable<SseItem<T>>`，配合 `await foreach` 使用
- 每个 `SseItem<T>` 暴露 `.EventType`（对应的 `event:` 字段，默认 `"message"`）、`.Data`（反序列化的载荷）、`.EventId`（`id:` 字段，用于重连）

**带类型的 SSE 解析器：**

```csharp
await foreach (SseItem<StockPrice> item in SseParser.Create(stream,
    (eventType, data) => JsonSerializer.Deserialize<StockPrice>(data)!)
    .EnumerateAsync(cancellationToken))
{
    Console.WriteLine($"{item.EventType}: " +
        $"{item.Data.Symbol} @ {item.Data.Price}");
}
```

这样免去了循环内手动调用 `JsonSerializer.Deserialize`，解析逻辑集中在一处。

## 性能考量：何时流、何时不流

不是每个 HTTP 响应都值得流化。选错方案只会增加代码复杂度却无实际收益。可以参考这个决策表：

| 场景                        | 推荐方式                               | 原因                                 |
| --------------------------- | -------------------------------------- | ------------------------------------ |
| 响应体小于约 1MB            | `GetStringAsync` / `GetByteArrayAsync` | 缓存快速、简单、开销可以忽略         |
| 响应体超过约 10MB           | `ResponseHeadersRead` + 流式读取       | 避免大量堆分配和 GC 压力             |
| 含大量元素的 JSON 数组      | `DeserializeAsyncEnumerable`           | 逐条处理、常量内存                   |
| 文件下载                    | `ResponseHeadersRead` + 手动缓冲循环   | 支持进度报告，不驻留文件内容到内存   |
| Server-Sent Events 或实时流 | `ResponseHeadersRead` + `SseParser`    | 连接没有时间上限，缓存不可行         |
| 高频小请求（REST）          | 默认缓存模式                           | 简单为王，对小载荷上流式纯属额外开销 |

核心判断标准：流式在**尺寸大**或**时长无界**时最有用。对于返回几 KB JSON 的日常 REST 调用，默认的缓存辅助方法完全够用，而且更好用。

## CancellationToken 与流式操作

流式连接本质上是长期存在的。规范的取消机制不能省——取消不当可能导致 socket 泄漏、线程池线程卡死或静默丢数据。

上面每个示例中的流式方法都接收 `CancellationToken`。关键在于一路传递它——传给 `SendAsync`、传给 `ReadAsStreamAsync`、传给每次 `ReadAsync` 或 `ReadLineAsync` 调用。

```csharp
using System.Net.Http;

public static async Task StreamWithTimeoutAsync(
    HttpClient client,
    string url,
    CancellationToken externalCancellation)
{
    // 把 30 秒超时和外部取消信号组合
    using var timeoutCts = new CancellationTokenSource(
        TimeSpan.FromSeconds(30));
    using var linkedCts = CancellationTokenSource
        .CreateLinkedTokenSource(
            externalCancellation, timeoutCts.Token);

    CancellationToken token = linkedCts.Token;

    try
    {
        using var response = await client.SendAsync(
            new HttpRequestMessage(HttpMethod.Get, url),
            HttpCompletionOption.ResponseHeadersRead,
            token);

        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content
            .ReadAsStreamAsync(token);
        using var reader = new StreamReader(stream);

        while (!reader.EndOfStream)
        {
            token.ThrowIfCancellationRequested();

            var line = await reader.ReadLineAsync(token);
            Console.WriteLine(line);
        }
    }
    catch (OperationCanceledException)
        when (timeoutCts.IsCancellationRequested)
    {
        Console.WriteLine(
            "Stream read timed out after 30 seconds.");
    }
    catch (OperationCanceledException)
    {
        Console.WriteLine(
            "Stream read was cancelled by the caller.");
    }
}
```

两点注意事项：

- 不要把 `HttpClient.Timeout` 设成 `Timeout.InfiniteTimeSpan` 而不搭配每次请求的 `CancellationToken` 安全网——这会禁用整个客户端级别的请求超时。但当像上面完整示例那样每条请求都配一个 `CancellationTokenSource` 兜底时，设成 `InfiniteTimeSpan` 对长期流式下载反而是正确做法。
- 取消时务必 dispose response 和 stream——`using` 和 `await using` 语句会自动处理，即便有异常抛出。

## 背压与 IAsyncEnumerable 管道

`IAsyncEnumerable` 在 HttpClient 流式传输中的一个细微但重要的优势是天然提供背压。消费者控制节奏——如果你的处理很慢，网络读取就跟着放慢——永远不会堆出一个无边界的未处理数据队列。

下面是一个将流式 HTTP 响应暴露为类型化 `IAsyncEnumerable<T>` 的封装：

```csharp
using System.Net.Http;
using System.Runtime.CompilerServices;
using System.Text.Json;

public static async IAsyncEnumerable<T> StreamJsonAsync<T>(
    HttpClient client,
    string url,
    JsonSerializerOptions? options = null,
    [EnumeratorCancellation] CancellationToken cancellationToken = default)
{
    using var response = await client.SendAsync(
        new HttpRequestMessage(HttpMethod.Get, url),
        HttpCompletionOption.ResponseHeadersRead,
        cancellationToken);

    response.EnsureSuccessStatusCode();

    await using var stream = await response.Content
        .ReadAsStreamAsync(cancellationToken);

    await foreach (var item in JsonSerializer
        .DeserializeAsyncEnumerable<T>(
            stream,
            options,
            cancellationToken))
    {
        yield return item;
    }
}

// 调用方控制节奏——慢的 ProcessAsync 会拖慢整个管道
await foreach (var record in StreamJsonAsync<LogEntry>(
    client, "https://api.example.com/logs"))
{
    await ProcessAsync(record);
    // 下一次网络读取会等到这里返回
}
```

`[EnumeratorCancellation]` 属性很重要——它让 `await foreach (... cancellationToken: token)` 正常工作，将取消令牌注入 `IAsyncEnumerator<T>` 而无须额外重载。

对比 `Channel<T>` 或 `BlockingCollection<T>` 的做法，生产者按网络交付速度推数据，如果消费者慢就会在内存中积压出一个大队列。`IAsyncEnumerable` 的拉模型彻底避免了这个问题。

## 完整示例：流式传输 1GB 响应

下面是一个完整、自包含的示例，组合了本文所有技术：流式传输 1GB 响应、报告进度、支持取消、内存不超过一个缓冲区大小。

```csharp
using System.Net.Http;
using System.Net.Http.Headers;

public sealed record StreamingProgress(
    long BytesRead,
    long? TotalBytes,
    double? PercentComplete)
{
    public override string ToString() =>
        TotalBytes.HasValue
            ? $"{BytesRead:N0} / {TotalBytes.Value:N0} bytes " +
              $"({PercentComplete:F1}%)"
            : $"{BytesRead:N0} bytes (total unknown)";
}

public sealed class LargeFileStreamer
{
    private const int BufferSize = 131_072; // 128KB

    private readonly HttpClient _client;

    public LargeFileStreamer(HttpClient client)
    {
        _client = client;
    }

    /// <summary>
    /// 将大文件下载到磁盘，不将响应体缓存到内存。
    /// 无论响应多大，峰值内存约等于缓冲区大小（128KB）。
    /// </summary>
    public async Task DownloadAsync(
        string url,
        string outputPath,
        IProgress<StreamingProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(
            HttpMethod.Get, url);

        // 选择流式——任务在头部到达时完成，不等响应体缓存
        using var response = await _client.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);

        response.EnsureSuccessStatusCode();

        long? totalBytes = response.Content.Headers.ContentLength;

        await using var networkStream = await response.Content
            .ReadAsStreamAsync(cancellationToken);
        await using var fileStream = new FileStream(
            outputPath,
            FileMode.Create,
            FileAccess.Write,
            FileShare.None,
            bufferSize: BufferSize,
            useAsync: true);

        var buffer = new byte[BufferSize];
        long totalBytesRead = 0;
        int bytesRead;

        while ((bytesRead = await networkStream.ReadAsync(
            buffer, cancellationToken)) > 0)
        {
            // 每次只写入本次读到的字节
            await fileStream.WriteAsync(
                buffer.AsMemory(0, bytesRead), cancellationToken);
            totalBytesRead += bytesRead;

            if (progress is not null)
            {
                double? percent = totalBytes.HasValue
                    ? (double)totalBytesRead / totalBytes.Value * 100.0
                    : null;

                progress.Report(new StreamingProgress(
                    totalBytesRead, totalBytes, percent));
            }
        }
    }
}

// ------ 程序入口 ------
var handler = new SocketsHttpHandler
{
    // 允许响应无限流式传输，不设读取超时
    ResponseDrainTimeout = Timeout.InfiniteTimeSpan
};

var client = new HttpClient(handler)
{
    // 禁用全局请求超时——上面的 CancellationTokenSource 是每请求的安全网
    Timeout = Timeout.InfiniteTimeSpan
};

var streamer = new LargeFileStreamer(client);

using var cts = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) =>
    { e.Cancel = true; cts.Cancel(); };

var progress = new Progress<StreamingProgress>(
    p => Console.Write($"\r{p}    "));

try
{
    await streamer.DownloadAsync(
        "https://files.example.com/one-gigabyte-export.bin",
        "one-gigabyte-export.bin",
        progress,
        cts.Token);

    Console.WriteLine("\nDone.");
}
catch (OperationCanceledException)
{
    Console.WriteLine("\nCancelled.");
}
```

几点值得单独说明：

- `HttpClient.Timeout = Timeout.InfiniteTimeSpan` 在这里是有意为之——因为我们在流式传输大文件，不希望读到一半被超时打断。每请求的取消由 `CancellationTokenSource` 兜底。
- `ResponseDrainTimeout = Timeout.InfiniteTimeSpan` 配置在 `SocketsHttpHandler` 上，防止基础设施在排流慢时过早放弃 stream。
- `buffer.AsMemory(0, bytesRead)` 确保每次只写入真正读到的字节（最后一块时 buffer 没填满也照样正确）。

## 常见问题

### 什么是 HttpCompletionOption.ResponseHeadersRead？

它告诉 `HttpClient` 一旦收到 HTTP 响应头就让 `SendAsync` 任务完成，不等响应体下载完毕。这样你可以把响应体当作流来逐步处理，这是 HttpClient 流式传输的基础。

### 怎么在 C# 中不把 HTTP 响应全部加载到内存里？

给 `SendAsync` 传 `HttpCompletionOption.ResponseHeadersRead`，然后调用 `ReadAsStreamAsync()` 获取响应内容的流。用 `ReadAsync` 分块读取或用 `CopyToAsync` 拷贝到文件。响应体永远不会以完整字节数组形态出现在内存中。

### .NET 10 中能用取消令牌配合 ReadAsStreamAsync 吗？

可以。`ReadAsStreamAsync` 从 .NET 5 起就直接接收 `CancellationToken`。把令牌传给 `SendAsync`、`ReadAsStreamAsync` 以及后续每次 `ReadAsync` 或 `ReadLineAsync` 调用。令牌被取消时，流会被关闭，正在进行的读取会抛出 `OperationCanceledException`。

### HttpClient 流式传输怎么配合 Server-Sent Events？

用 `ResponseHeadersRead` 拿到长期响应，设好 `Accept: text/event-stream` 头，然后持续从流中读行。从 .NET 9 起用 `SseParser.Create(stream).EnumerateAsync()` 处理 SSE 线格式，每个事件产生一个 `SseItem<string>` 对象。

### ResponseContentRead 和 ResponseHeadersRead 的内存差异有多大？

用 `ResponseContentRead`，峰值内存等于响应体大小——1GB 响应占 1GB 堆。用 `ResponseHeadersRead` 和流式读取，峰值内存约等于读缓冲大小（通常 4KB 到 128KB），和总响应大小无关。

### 下载大文件时怎么报告进度？

用 `ResponseHeadersRead` 手动循环读取响应体。读 `response.Content.Headers.ContentLength` 得到总大小，记录每块读取的字节数，通过 `IProgress<T>` 报告进度。`ContentLength` 对 chunked transfer 可能为 null，此时只能报告已下载字节数，不能报告百分比。

### IAsyncEnumerable 怎么帮到 HTTP 流式传输？

`IAsyncEnumerable<T>` 是异步序列接口——类似 `IEnumerable<T>` 但每个元素需要 await。在 HttpClient 流式传输中它提供天然背压：下一次网络读取要等消费者调用 `MoveNextAsync()` 才发生。这防止了快速网络压垮慢速处理器，内存始终可控。

## 小结

HttpClient 流式传输属于那种「默认情况下没事，直到事大了才意识到有问题」的话题。一旦你需要处理大文件、长期事件流或者那种本质上是分页但写成一个大 JSON 数组的 API，缓存模式就撑不住了。

好消息是改起来不复杂。`HttpCompletionOption.ResponseHeadersRead` 让你退出自动缓存，`ReadAsStreamAsync` 给你原始网络流，`JsonSerializer.DeserializeAsyncEnumerable` 在结构化数据场景下不需要物化整个集合，`IAsyncEnumerable<T>` 把所有东西串成尊重背压和取消的管道。

这些不是什么高深冷僻的 API——它们是 .NET 10 中处理实质性 HTTP 数据传输的正确工具。越熟练地使用它们，就越不太可能在流量高峰期不小心把一个 500MB 的响应体缓存进内存。

---

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [HttpClient Streaming in C#: HttpCompletionOption, ReadAsStreamAsync, and Server-Sent Events](https://www.devleader.ca/2026/06/30/httpclient-streaming-in-c-httpcompletionoption-readasstreamasync-and-serversent-events)
- [HttpClient in C#: The Complete Guide](https://www.devleader.ca/2026/06/26/httpclient-in-c-the-complete-guide-for-net-developers)
- [How To Handle Exceptions in CSharp](https://www.devleader.ca/2023/10/22/how-to-handle-exceptions-in-csharp-tips-and-tricks-for-streamlined-debugging)
