---
pubDatetime: 2026-03-30T11:50:03+08:00
title: "用 BoundedChannel + SignalR 构建高吞吐实时数据管道"
description: "本文介绍如何在 .NET 中用 System.Threading.Channels 的 BoundedChannel 搭配 SignalR，实现从 NATS 消费高速数据、批量刷新并广播到实时看板的生产级管道模式。"
tags: ["dotnet", "SignalR", "Channels", "NATS", "实时", "高性能"]
slug: "high-throughput-real-time-bounded-channel-signalr"
ogImage: "../../assets/688/01-cover.jpg"
source: "https://thecodeman.net/posts/high-throughput-real-time-data-bounded-channel-signalr"
---

如果你做过遥测采集、传感器数据流或交易逐笔行情，多半遇到过这个问题：生产者的速度远超消费者。NATS 每秒能推几千条消息，但 SignalR Hub、数据库写入端或下游 API 根本跟不上逐条处理。

解法说起来直接：加一个支持批处理的队列。.NET 内置的 `System.Threading.Channels` 就给了我们这个东西，不依赖任何外部库。

这篇文章展示如何用 `BoundedChannel<T>` 搭配 SignalR，构建一条从 NATS 到客户端看板的完整数据管道：

- 从 NATS 高速消费数据点
- 写入容量 10,000 的 `BoundedChannel`（单读者模式）
- 按批次刷新——1,000 条满了或 50ms 计时到期，先到先触发
- 通过 SignalR `DataPointHub` 将每批数据广播给所有连接的看板

## 为什么要用 BoundedChannel

`System.Threading.Channels` 提供两种通道：

- `Channel.CreateUnbounded<T>()`：无容量上限，流量峰值时会吃光内存
- `Channel.CreateBounded<T>(capacity)`：固定容量，内置背压机制

高吞吐场景始终选有界通道，原因有三：

**背压**：通道满时，生产者会等待，服务不会因内存耗尽崩溃。

**单读者优化**：声明 `SingleReader = true` 后，运行时内部可以省掉加锁开销。

**可预测的内存占用**：你提前决定最多缓冲多少条，不用猜测峰值。

把它想象成一根固定管径的管道——你控制水流量。

## 第一步：数据模型

定义流经通道的值类型：

```csharp
public sealed record DataPointValue(
    string SensorId,
    double Value,
    DateTime Timestamp);
```

简单、不可变。从 NATS 收到的每一条读数都映射到这个类型。

## 第二步：配置分发选项

批次大小和刷新间隔不应硬编码，从配置文件读取：

```csharp
public sealed class DataPointDispatchOptions
{
    public int ChannelCapacity { get; set; } = 10_000;
    public int BatchSize      { get; set; } = 1_000;
    public int FlushIntervalMs{ get; set; } = 50;
    public bool SingleReader  { get; set; } = true;
    public bool SingleWriter  { get; set; } = false;
}
```

对应的 `appsettings.json`：

```json
{
  "DataPointDispatch": {
    "ChannelCapacity": 10000,
    "BatchSize": 1000,
    "FlushIntervalMs": 50,
    "SingleReader": true,
    "SingleWriter": false
  }
}
```

`SingleReader: true`：只有一个消费者，运行时可以去掉同步开销。  
`SingleWriter: false`：多个 NATS 订阅回调会并发写入，不能声明单写者。

## 第三步：SignalR Hub

Hub 本身刻意做得很薄，只是广播端点：

```csharp
public sealed class DataPointHub : Hub
{
    public override async Task OnConnectedAsync()
    {
        await base.OnConnectedAsync();
    }
}
```

Hub 上不暴露任何方法——服务端主动推送，客户端只负责监听。

客户端（JavaScript）连接示例：

```javascript
const connection = new signalR.HubConnectionBuilder()
    .withUrl("/data-point-hub")
    .withAutomaticReconnect()
    .build();

connection.on("ReceiveDataPoints", (batch) => {
    // batch 是 { sensorId, value, timestamp } 的数组
    updateDashboard(batch);
});

await connection.start();
```

每次服务端刷新一批数据，所有连接的客户端立刻收到。

## 第四步：构建 DataPointService

核心在这里。一个 `BackgroundService`，拥有通道并运行两个并发循环：

- **写入侧**：NATS 订阅回调把数据点压入通道
- **读取侧**：刷新循环按批次排干通道，通过 SignalR 广播

```csharp
public sealed class DataPointService : BackgroundService
{
    private readonly Channel<DataPointValue> _channel;
    private readonly IHubContext<DataPointHub> _hubContext;
    private readonly DataPointDispatchOptions _options;
    private readonly INatsConnection _natsConnection;
    private readonly ILogger<DataPointService> _logger;

    public DataPointService(
        IHubContext<DataPointHub> hubContext,
        IOptions<DataPointDispatchOptions> options,
        INatsConnection natsConnection,
        ILogger<DataPointService> logger)
    {
        _hubContext = hubContext;
        _options    = options.Value;
        _natsConnection = natsConnection;
        _logger     = logger;

        _channel = Channel.CreateBounded<DataPointValue>(
            new BoundedChannelOptions(_options.ChannelCapacity)
            {
                SingleReader = _options.SingleReader,
                SingleWriter = _options.SingleWriter,
                FullMode     = BoundedChannelFullMode.Wait
            });
    }

    public ChannelWriter<DataPointValue> Writer => _channel.Writer;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var consumerTask = ConsumeFromNatsAsync(stoppingToken);
        var flushTask    = FlushLoopAsync(stoppingToken);

        await Task.WhenAll(consumerTask, flushTask);
    }
}
```

构造函数中用 `FullMode = Wait` 创建有界通道：缓冲区满到 10,000 条时，NATS 回调会暂停等待，直到读取端释放出空间——这就是背压在起作用。

`ExecuteAsync` 启动两个并发循环，贯穿服务整个生命周期。

## 第五步：从 NATS 消费数据

写入侧订阅 NATS 主题，把每条消息推入通道：

```csharp
private async Task ConsumeFromNatsAsync(CancellationToken stoppingToken)
{
    await foreach (var msg in _natsConnection
        .SubscribeAsync<DataPointValue>("datapoints.>", cancellationToken: stoppingToken))
    {
        if (msg.Data is null) continue;

        await _channel.Writer.WriteAsync(msg.Data, stoppingToken);
    }

    _channel.Writer.Complete();
}
```

`SubscribeAsync` 返回 `IAsyncEnumerable`，每条消息到达后直接落入通道。取消令牌触发时，循环退出，调用 `Writer.Complete()` 通知读取端不再有新数据。

通配符主题 `datapoints.>` 意味着订阅 `datapoints` 命名空间下所有主题，如 `datapoints.soil`、`datapoints.temperature` 等。

## 第六步：批量刷新循环

这是关键所在。读取端尽量快地排干条目，直到满足以下任一条件：

- 收集到 `BatchSize`（1,000）条
- `FlushIntervalMs`（50ms）计时到期
- 服务正在关闭

```csharp
private async Task FlushLoopAsync(CancellationToken stoppingToken)
{
    var batch  = new List<DataPointValue>(_options.BatchSize);
    var reader = _channel.Reader;

    while (!stoppingToken.IsCancellationRequested)
    {
        batch.Clear();

        using var cts = CancellationTokenSource
            .CreateLinkedTokenSource(stoppingToken);
        cts.CancelAfter(TimeSpan.FromMilliseconds(_options.FlushIntervalMs));

        try
        {
            while (batch.Count < _options.BatchSize)
            {
                var item = await reader.ReadAsync(cts.Token);
                batch.Add(item);
            }
        }
        catch (OperationCanceledException)
        {
            // 50ms 到期或服务停止，把已收集的数据刷出去
        }

        if (batch.Count > 0)
        {
            await BroadcastBatchAsync(batch);
        }
    }

    // 服务停止后排干剩余条目
    while (reader.TryRead(out var remaining))
    {
        batch.Add(remaining);
    }

    if (batch.Count > 0)
    {
        await BroadcastBatchAsync(batch);
    }
}
```

技巧在于关联的 `CancellationTokenSource`：创建一个 50ms 后过期的令牌，内层循环拼命读，直到批次满、计时到期或服务关闭。三种情况都会把已收集到的数据刷出去。

外层循环退出后，用 `TryRead` 排干剩余条目，保证不丢数据。

## 第七步：通过 SignalR 广播

```csharp
private async Task BroadcastBatchAsync(List<DataPointValue> batch)
{
    try
    {
        await _hubContext.Clients.All.SendAsync(
            "ReceiveDataPoints",
            batch);

        _logger.LogDebug("Broadcasted {Count} data points", batch.Count);
    }
    catch (Exception ex)
    {
        _logger.LogError(ex, "Failed to broadcast {Count} data points", batch.Count);
    }
}
```

从 Hub 类外部推送消息，要用 `IHubContext<DataPointHub>` 而不是直接操作 Hub 实例。`try/catch` 确保单次广播失败不会搞垮整个服务。

## 第八步：注册服务

在 `Program.cs` 中完成注册：

```csharp
builder.Services.Configure<DataPointDispatchOptions>(
    builder.Configuration.GetSection("DataPointDispatch"));

builder.Services.AddSignalR();
builder.Services.AddHostedService<DataPointService>();

var app = builder.Build();

app.MapHub<DataPointHub>("/data-point-hub");

app.Run();
```

配置来自 `appsettings.json`，通道在内部创建，两个循环随宿主启动自动运行。

## 整体数据流

```
NATS → SubscribeAsync → Channel.Writer → [BoundedChannel 10K]
     → Channel.Reader → Batch (1000条 / 50ms) → SignalR Hub → Clients
```

NATS 全速推送，通道吸收突发流量，刷新循环高效聚批，SignalR 每次刷新把一批数据送到所有看板。没有逐条处理，没有 `Task.Delay` 轮询，没有手动线程管理。

## 性能对比

朴素做法：每条消息调用一次 `SendAsync`。5,000 条/秒就是 5,000 次 SignalR 广播。

批量做法：大约每秒 5 次（每次 1,000 条），或者低流量时每 50ms 一次——广播次数从几千次降到几十次。

这个模式还带来：

- **背压**：生产者跟不上时自动减速，内存占用可预测
- **低延迟**：50ms 计时触发保证即使低流量时客户端也能在 50ms 内看到更新
- **优雅停机**：服务停止前排干剩余条目，不会丢数据
- **可配置**：批次大小、通道容量、刷新间隔全部在 `appsettings.json` 中调整

## 参数调优建议

默认值（容量 10,000 / 批次 1,000 / 间隔 50ms）适合大多数实时看板场景，以下情况需要调整：

| 场景 | 建议 |
|---|---|
| 高突发、低稳态流量 | 增大 `ChannelCapacity`，避免突发触发背压 |
| 对延迟极度敏感 | 将 `FlushIntervalMs` 降到 10–20ms，代价是更频繁的小批量 |
| 单条消息 payload 较大 | 减小 `BatchSize`，控制每次 SignalR 消息的体积 |
| 需要多个消费者（如同时写数据库） | 将 `SingleReader` 改为 `false` |

调参前最好先用真实负载做基准测试。通道本身性能出色，瓶颈通常在下游消费端。

## 参考

- [原文：High-Throughput Real-Time Data with BoundedChannel and SignalR](https://thecodeman.net/posts/high-throughput-real-time-data-bounded-channel-signalr)
- [Real-Time applications with SignalR](https://thecodeman.net/posts/real-time-dotnet-applications-with-signalr)
- [Background Tasks in .NET 8](https://thecodeman.net/posts/background-tasks-in-dotnet8)
- [A Friendly Introduction to NATS: Real-Time Messaging for .NET Developers](https://thecodeman.net/posts/introduction-to-nats-real-time-messaging)
