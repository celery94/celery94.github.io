---
pubDatetime: 2026-03-23T12:00:00+08:00
title: "用 MeterListener 在进程内采集 .NET 指标"
description: "Andrew Lock 详解如何用 MeterListener 在进程内订阅 System.Diagnostics.Metrics 的 Instrument，涵盖回调配置、observable 触发、标签处理与线程安全聚合，并通过 Spectre.Console 实时展示 ASP.NET Core 运行时指标。"
tags: [".NET", "C#", "Metrics", "Observability", "ASP.NET Core"]
slug: "recording-metrics-in-process-using-meterlistener"
ogImage: "../../assets/659/01-cover.png"
source: "https://andrewlock.net/recording-metrics-in-process-using-meterlistener"
---

![用 MeterListener 在进程内采集 .NET 指标](../../assets/659/01-cover.png)

这是 Andrew Lock *System.Diagnostics.Metrics APIs* 系列的第 4 篇。前几篇覆盖了如何创建各种 `Instrument`、如何用 `dotnet-counters` 消费指标，以及 Source Generator 的使用。这篇聚焦的问题是：如果不想依赖外部采集工具，想在自己的服务进程内直接拿到指标数据，该怎么做？

答案是使用 `MeterListener`。

> 注意：生产环境中通常应选择 OpenTelemetry 或 Datadog 这类完整方案。`MeterListener` 更适合需要在进程内做轻量自定义采集的场景，比如健康检查、自适应限流、本地调试仪表盘等。

---

## 示例场景：自测负载下的实时指标表格

Andrew 的示例是一个最简 ASP.NET Core 应用，它在启动后会自己向自己发起 HTTP 请求（4 路并发），目标是用一个 Spectre.Console 实时表格展示运行时指标：

```
┌────────────────────────────────────────────┬─────────────────────────┬─────────────┐
│ Metric                                     │ Type                    │       Value │
├────────────────────────────────────────────┼─────────────────────────┼─────────────┤
│ aspnetcore.routing.match_attempts          │ Counter                 │     250,428 │
│ dotnet.gc.heap.total_allocated             │ ObservableCounter       │ 849,743,376 │
│ http.server.active_requests                │ UpDownCounter           │           4 │
│ dotnet.gc.last_collection.heap.size (gen0) │ ObservableUpDownCounter │   2,497,080 │
│ process.cpu.utilization                    │ ObservableGauge         │         36% │
│ http.server.request.duration               │ Histogram               │     0.011ms │
└────────────────────────────────────────────┴─────────────────────────┴─────────────┘
```

应用本身很简单，关键在数据采集层——`MetricManager`。

---

## MetricManager：封装 MeterListener

Andrew 创建了 `MetricManager` 类来封装所有与 `MeterListener` 的交互。它的公开 API 极简：

```csharp
public class MetricManager : IDisposable
{
    public void Dispose();
    public MetricValues GetMetrics();
}
```

每次调用 `GetMetrics()` 就拿到一个快照，包含关心的所有指标当前值。

---

## 第一步：创建 MeterListener 并配置回调

```csharp
public MetricManager()
{
    _listener = new()
    {
        InstrumentPublished = OnInstrumentPublished
    };

    // 为不同值类型注册回调（long 和 double 覆盖了这里用到的所有 Instrument）
    _listener.SetMeasurementEventCallback<long>(OnMeasurementRecordedLong);
    _listener.SetMeasurementEventCallback<double>(OnMeasurementRecordedDouble);

    // 启动监听，同时触发对已发布 Instrument 的 OnInstrumentPublished 调用
    _listener.Start();
}
```

几个关键点：

- **`InstrumentPublished` 回调**：每当有新的 `Instrument` 注册时触发，`Start()` 调用时也会对已有的 Instrument 各触发一次。由这里决定要不要订阅某个 Instrument。
- **`SetMeasurementEventCallback<T>()`**：按值类型注册回调。`Instrument` 支持 `byte`/`short`/`int`/`long`/`float`/`double`/`decimal`——建议全部注册。之所以按类型分开而不是用 `object` 统一处理，是为了**零分配**，体现了 System.Diagnostics.Metrics 对性能的重视。

---

## 第二步：选择要订阅哪些 Instrument

`OnInstrumentPublished` 决定哪些指标会触发回调，不感兴趣的直接忽略：

```csharp
private void OnInstrumentPublished(Instrument instrument, MeterListener listener)
{
    string meterName = instrument.Meter.Name;
    string instrumentName = instrument.Name;

    var enable = meterName switch
    {
        "Microsoft.AspNetCore.Routing" => instrumentName == "aspnetcore.routing.match_attempts",
        "System.Runtime"               => instrumentName is "dotnet.gc.heap.total_allocated"
                                          or "dotnet.gc.last_collection.heap.size",
        "Microsoft.AspNetCore.Hosting" => instrumentName is "http.server.active_requests"
                                          or "http.server.request.duration",
        "Microsoft.Extensions.Diagnostics.ResourceMonitoring"
                                       => instrumentName == "process.cpu.utilization",
        _ => false
    };

    if (enable)
    {
        // 启用该 Instrument，并把 MetricManager 自身作为 state 传入
        listener.EnableMeasurementEvents(instrument, state: this);
    }
}
```

`state` 参数在回调中原样传回，用于避免闭包或字典查找，是进一步减少分配的设计。如果想订阅所有 Instrument，一行就够：

```csharp
private void OnInstrumentPublished(Instrument instrument, MeterListener listener)
    => listener.EnableMeasurementEvents(instrument, state: this);
```

---

## 第三步：触发 Observable Instrument 上报值

**标准 Instrument**（`Counter`、`UpDownCounter`、`Histogram`）在每次调用记录方法时立即触发回调。

**Observable Instrument**（`ObservableCounter`、`ObservableUpDownCounter`、`ObservableGauge`）不会主动推送值，需要消费方主动"拉取"——调用 `RecordObservableInstruments()`：

```csharp
public MetricValues GetMetrics()
{
    // 触发所有已启用的 Observable Instrument 去读取当前值，并调用回调
    _listener.RecordObservableInstruments();

    // 读取字段值并返回快照
    return new MetricValues( ... );
}
```

---

## 第四步：在回调中聚合数据

这里有一个关键区分：

- **Counter / UpDownCounter**：每次回调传入的是**增量**，需要累加到运行总值
- **Observable 系列**：回调传入的是**当前完整值**，直接替换即可

```csharp
private static void OnMeasurementRecordedLong(Instrument instrument, long measurement,
    ReadOnlySpan<KeyValuePair<string, object?>> tags, object? state)
{
    var handler = (MetricManager)state!;
    switch (instrument.Name)
    {
        case "aspnetcore.routing.match_attempts":   // Counter：累加
            Interlocked.Add(ref handler._matchAttempts, measurement);
            break;

        case "dotnet.gc.heap.total_allocated":       // ObservableCounter：替换
            Interlocked.Exchange(ref handler._totalHeapAllocated, measurement);
            break;

        case "http.server.active_requests":          // UpDownCounter：累加
            Interlocked.Add(ref handler._activeRequests, measurement);
            break;

        case "dotnet.gc.last_collection.heap.size":  // ObservableUpDownCounter：按 tag 替换
            foreach (var tag in tags)
            {
                if (tag is { Key: "gc.heap.generation", Value: string gen })
                {
                    switch (gen)
                    {
                        case "gen0": Interlocked.Exchange(ref handler._heapSizeGen0, measurement); break;
                        case "gen1": Interlocked.Exchange(ref handler._heapSizeGen1, measurement); break;
                        case "gen2": Interlocked.Exchange(ref handler._heapSizeGen2, measurement); break;
                        case "loh":  Interlocked.Exchange(ref handler._heapSizeLoh,  measurement); break;
                        case "poh":  Interlocked.Exchange(ref handler._heapSizePoh,  measurement); break;
                    }
                }
            }
            break;
    }
}
```

`dotnet.gc.last_collection.heap.size` 展示了**标签（tags）**的用法：同一个 Instrument 按 `gc.heap.generation` 标签区分不同代的堆大小，每次 `RecordObservableInstruments()` 会为每个代各触发一次回调。

对于 Histogram，Andrew 选择只统计两个值：总请求数和区间内的平均时延（每次 `GetMetrics()` 后重置区间计数器）：

```csharp
case "http.server.request.duration":  // Histogram
    Interlocked.Increment(ref handler._totalRequestCount);
    lock (handler._durationLock)
    {
        handler._intervalRequests++;
        handler._totalDuration += measurement;
    }
    break;
```

由于测量值可能与读取并发，大部分字段使用 `Interlocked` 保证原子性；不能用 `Interlocked` 的地方用 `lock`。

---

## 第五步：用 BackgroundService 展示结果

Andrew 创建了一个 `BackgroundService`，每秒调用一次 `GetMetrics()` 并更新 Spectre.Console 的实时表格：

```csharp
await AnsiConsole.Live(table).StartAsync(async ctx =>
{
    while (!stoppingToken.IsCancellationRequested)
    {
        await Task.Delay(TimeSpan.FromSeconds(1), stoppingToken);
        RenderMetricValues(table, ctx, manager.GetMetrics());
    }
});
```

注册到 DI：

```csharp
builder.Services.AddHostedService<MetricDisplayService>();
builder.Services.AddResourceMonitoring(); // 提供 process.cpu.utilization
```

---

## 小结

`MeterListener` 的核心使用步骤：

1. 创建实例，设置 `InstrumentPublished` 回调
2. 用 `SetMeasurementEventCallback<T>()` 注册各类型的测量回调
3. 调用 `Start()`
4. 在 `OnInstrumentPublished` 中用 `EnableMeasurementEvents()` 选择要订阅的 Instrument
5. 在测量回调中区分标准 Instrument（累加）和 Observable Instrument（替换）
6. 需要 Observable Instrument 的最新值时，显式调用 `RecordObservableInstruments()`

这套 API 的设计处处为性能考量：按类型分开的回调、`state` 参数传递上下文、`ReadOnlySpan` 传递标签——都是为了把分配降到最低。如果需要更通用、生产级的采集方案，则应使用 OpenTelemetry。

## 参考

- [Recording metrics in-process using MeterListener – Andrew Lock](https://andrewlock.net/recording-metrics-in-process-using-meterlistener)
- [System.Diagnostics.Metrics APIs 系列](https://andrewlock.net/series/system-diagnostics-metrics-apis/)
- [Overview of .NET observability with OpenTelemetry](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/observability-with-otel)
