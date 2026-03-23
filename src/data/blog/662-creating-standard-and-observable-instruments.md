---
pubDatetime: 2026-03-23T15:00:00+08:00
title: ".NET 七种指标类型详解：标准 Instrument 与 Observable Instrument 的区别和用法"
description: "Andrew Lock 逐一拆解 System.Diagnostics.Metrics 的全部七种 Instrument 类型——Counter、UpDownCounter、Gauge、Histogram 及其 Observable 版本——结合 .NET 运行时和 ASP.NET Core 的真实源码，讲清楚每种类型的适用场景和记录方式。"
tags: [".NET", "C#", "Metrics", "Observability", "ASP.NET Core"]
slug: "creating-standard-and-observable-instruments"
ogImage: "../../assets/662/01-cover.png"
source: "https://andrewlock.net/creating-standard-and-observable-instruments/"
---

![.NET 七种指标类型详解](../../assets/662/01-cover.png)

这是 Andrew Lock *System.Diagnostics.Metrics APIs* 系列的第 3 篇。前两篇介绍了 API 基础和 Source Generator，这篇专注于一个最基础的问题：.NET 提供了哪几种 `Instrument` 类型，它们有什么区别，该怎么选？

---

## 标准 Instrument vs Observable Instrument

在 System.Diagnostics.Metrics 的设计里，有**生产方**（app 记录指标）和**消费方**（读取指标的工具或库）之分。这两种角色的协作方式，决定了标准 Instrument 和 Observable Instrument 的根本区别：

- **标准 Instrument**：由生产方主动推送值。事件发生时，app 立即调用 `Add()` / `Record()` 等方法上报。
- **Observable Instrument**：由消费方拉取值。只有当消费方（如 `dotnet-counters`、OpenTelemetry 库）询问时，Instrument 才去读取并返回当前值。

Observable Instrument 适合两类场景：
1. 值本身是持续变化的，生产方不可能每次变化都主动上报（如 GC 堆大小）
2. 每次读取值有一定开销，更适合按需拉取而非持续推送（如 CPU 使用率）

---

## 七种 Instrument 类型

### Counter\<T\>

最基础的计数器，只增不减。每次事件发生时调用 `Add()` 上报增量。

**真实示例**：ASP.NET Core 异常处理中间件的异常计数

```csharp
_handlerExceptionCounter = _meter.CreateCounter<long>(
    "aspnetcore.diagnostics.exceptions",
    unit: "{exception}",
    description: "Number of exceptions caught by exception handling middleware.");

// 每次捕获异常时
var tags = new TagList();
tags.Add("error.type", exceptionName);
tags.Add("aspnetcore.diagnostics.exception.result", GetExceptionResult(result));
_handlerExceptionCounter.Add(1, tags);
```

`Counter<T>` 记录的是累计事件数，值只增不减（每次 `Add` 的 delta 应为正数，但可以大于 1）。

---

### ObservableCounter\<T\>

概念上与 `Counter<T>` 相同（单调递增），区别在于值只在被消费方观测时才计算。回调函数返回的是**当前总量**而非增量。

**真实示例**：.NET 运行时的 GC 堆总分配字节数

```csharp
s_meter.CreateObservableCounter(
    "dotnet.gc.heap.total_allocated",
    () => GC.GetTotalAllocatedBytes(),
    unit: "By",
    description: "The approximate number of bytes allocated on the managed GC heap since the process has started.");
```

每次被观测时，直接调用 `GC.GetTotalAllocatedBytes()` 返回当前累计值。

---

### UpDownCounter\<T\>

与 `Counter<T>` 类似，但可以上报正值或负值，适合追踪当前数量的变化（增加或减少）。

**真实示例**：ASP.NET Core 当前活跃 HTTP 请求数

```csharp
_activeRequestsCounter = _meter.CreateUpDownCounter<long>(
    "http.server.active_requests",
    unit: "{request}",
    description: "Number of active HTTP server requests.");

// 请求到达时
_activeRequestsCounter.Add(1, tags);

// 请求结束时
_activeRequestsCounter.Add(-1, tags);
```

消费方收到的是一系列加减增量，需要自行累加得到当前值。

---

### ObservableUpDownCounter\<T\>

与 `UpDownCounter<T>` 的语义相同（值可升可降），但只在被观测时才读取，且返回**当前绝对值**而非增量。

**真实示例**：.NET 运行时各代 GC 堆大小

```csharp
s_meter.CreateObservableUpDownCounter(
    "dotnet.gc.last_collection.heap.size",
    GetHeapSizes,
    unit: "By",
    description: "The managed GC heap size (including fragmentation), as observed during the latest garbage collection.");

private static IEnumerable<Measurement<long>> GetHeapSizes()
{
    GCMemoryInfo gcInfo = GC.GetGCMemoryInfo();
    for (int i = 0; i < s_maxGenerations; ++i)
    {
        yield return new Measurement<long>(
            gcInfo.GenerationInfo[i].SizeAfterBytes,
            new KeyValuePair<string, object?>("gc.heap.generation", s_genNames[i]));
    }
}
```

这里回调返回一个 `IEnumerable<Measurement<long>>`，每个元素对应一个 GC 代，用标签（`gc.heap.generation`）区分。

---

### Gauge\<T\>

记录"非累加"的即时值，新值会覆盖旧值。适合表达某个时刻的实际状态，而不是累计量。

`Gauge<T>` 在 .NET 9 才被引入，Andrew 在运行时和框架代码中没找到任何真实使用案例，于是自己造了一个例子——温度传感器：

```csharp
var instrument = _meter.CreateGauge<double>(
    name: "locations.room.temperature",
    unit: "°C",
    description: "Current room temperature");

// 温度变化时
instrument.Record(newTemperature, new KeyValuePair<string, object?>("room", "office"));
```

每次调用 `Record()` 上报最新温度，不关心之前的值。

---

### ObservableGauge\<T\>

概念与 `Gauge<T>` 相同（即时绝对值），但只在被观测时由回调函数提供值。这是 Observable 版本里历史最久的一个，在 .NET 6 就有了。

**真实示例**：进程 CPU 使用率

```csharp
_ = meter.CreateObservableGauge(
    name: "process.cpu.utilization",
    observeValue: CpuPercentage);

private double CpuPercentage()
{
    // 返回 [0, 1] 之间的 CPU 使用率
}
```

来自 `Microsoft.Extensions.Diagnostics.ResourceMonitoring` 包，每次观测时调用 `CpuPercentage()` 获取当前 CPU 使用率。

---

### Histogram\<T\>

记录任意分布的值，通常用于后续聚合统计（如 p50、p90、p99 百分位数，或绘制直方图）。没有 Observable 版本——返回分布数据的"快照"在概念上说不通。

**真实示例**：ASP.NET Core HTTP 请求耗时

```csharp
_requestDuration = _meter.CreateHistogram<double>(
    "http.server.request.duration",
    unit: "s",
    description: "Duration of HTTP server requests.",
    advice: new InstrumentAdvice<double>
    {
        HistogramBucketBoundaries = new[] { 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10 }
    });

// 请求结束时
var duration = Stopwatch.GetElapsedTime(startTimestamp, currentTimestamp);
_requestDuration.Record(duration.TotalSeconds, tags);
```

这里还演示了 `InstrumentAdvice<T>`：可以给消费方提供建议配置（如直方图分桶边界），让消费方知道如何最好地处理这些数据。

Histogram 里附带了大量标签（HTTP 方法、状态码、路由、协议版本等），这些标签让消费方可以从同一份数据派生出多种维度的分析，比如按路由统计请求数、按状态码统计错误率等。

---

## 选型小结

| 类型 | 方向 | 推送方式 | 典型场景 |
|------|------|----------|----------|
| `Counter<T>` | 只增 | 主动推送增量 | 请求数、异常数 |
| `ObservableCounter<T>` | 只增 | 拉取时返回总量 | GC 总分配字节 |
| `UpDownCounter<T>` | 增减 | 主动推送增量 | 活跃请求数、队列长度 |
| `ObservableUpDownCounter<T>` | 增减 | 拉取时返回绝对值 | 各代堆大小 |
| `Gauge<T>` | 任意即时值 | 主动推送新值 | 传感器读数 |
| `ObservableGauge<T>` | 任意即时值 | 拉取时由回调提供 | CPU 使用率 |
| `Histogram<T>` | 任意分布 | 主动推送每个样本 | 请求耗时、响应大小 |

判断用 Observable 还是标准版，核心问题是：值的产生是由业务事件驱动（用标准版），还是需要主动查询某个系统状态（用 Observable 版）？

---

## 参考

- [Creating standard and "observable" instruments – Andrew Lock](https://andrewlock.net/creating-standard-and-observable-instruments/)
- [System.Diagnostics.Metrics APIs 系列](https://andrewlock.net/series/system-diagnostics-metrics-apis/)
- [.NET Runtime 内置指标](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/built-in-metrics-runtime)
- [ASP.NET Core 内置指标](https://learn.microsoft.com/en-us/aspnet/core/log-mon/metrics/built-in)
