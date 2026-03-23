---
pubDatetime: 2026-03-23T13:00:00+08:00
title: ".NET 指标入门：用 System.Diagnostics.Metrics API 创建和采集自定义指标"
description: "Andrew Lock 介绍 System.Diagnostics.Metrics API 的核心概念 Meter 与 Instrument，演示用 dotnet-counters 监控内置运行时指标，并手把手带你为 ASP.NET Core 应用添加自定义业务指标。"
tags: [".NET", "C#", "Metrics", "Observability", "ASP.NET Core"]
slug: "creating-and-consuming-metrics-with-system-diagnostics-metrics-apis"
ogImage: "../../assets/660/01-cover.png"
source: "https://andrewlock.net/creating-and-consuming-metrics-with-system-diagnostics-metrics-apis/"
---

![.NET 指标入门](../../assets/660/01-cover.png)

这是 Andrew Lock *System.Diagnostics.Metrics APIs* 系列的第 1 篇，也是整个系列的起点。如果你还没接触过 .NET 内置的指标体系，这篇文章是理解后续内容（Source Generator、Observable Instrument、MeterListener）的基础。

---

## 核心概念：Meter 与 Instrument

System.Diagnostics.Metrics API 在 .NET 6 中作为内置功能引入，也可通过 `System.Diagnostics.DiagnosticSource` NuGet 包在早期版本中使用。整套 API 的设计目标是与 OpenTelemetry 互通，因此可以接入大量现有的可观测性基础设施。

API 的核心是两个概念：

- **`Instrument`**：记录单个指标的流。比如"已售出的商品数"、"当前活跃请求数"、"每次请求的耗时"各是一个 `Instrument`。
- **`Meter`**：多个 `Instrument` 的逻辑分组。比如 `System.Runtime` Meter 包含运行时的所有内置指标，`Microsoft.AspNetCore.Hosting` Meter 包含 HTTP 请求相关指标。

### Instrument 的类型

| 类型 | Observable 版本 | 用途 |
|------|-----------------|------|
| `Counter<T>` | `ObservableCounter<T>` | 只增不减的计数（如请求总数） |
| `UpDownCounter<T>` | `ObservableUpDownCounter<T>` | 可正可负的计数（如当前活跃请求数、队列长度） |
| `Gauge<T>` | `ObservableGauge<T>` | 瞬时当前值，新值替换旧值（如内存用量） |
| `Histogram<T>` | — | 任意值的分布（如请求耗时） |

**标准 Instrument vs Observable Instrument** 的区别在于触发时机：
- 标准版：每次调用记录方法时立即触发
- Observable 版：只在消费方主动拉取时才读取（适合无需频繁刷新、读取本身有开销的指标）

---

## 用 dotnet-counters 监控内置指标

开发和调试阶段，`dotnet-counters` 是最方便的本地监控工具。安装：

```bash
dotnet tool install -g dotnet-counters
```

监控一个正在运行的进程（按名称或 PID）：

```bash
dotnet-counters monitor -n MyApp
# 或
dotnet-counters monitor -p 123
```

也可以直接启动并监控：

```bash
dotnet-counters monitor -- dotnet MyApp.dll
```

运行后，控制台会定期刷新输出各项指标的当前值，例如：

```
[System.Runtime]
    dotnet.gc.collections ({collection})
        gen0                    67
        gen1                     6
        gen2                     1
    dotnet.gc.heap.total_allocated (By)    4,134,656
    dotnet.process.cpu.time (s)
        system                   5.453
        user                     9.313
    dotnet.thread_pool.thread.count ({thread})    4
```

用 `--counters` 过滤只看特定 Meter：

```bash
dotnet-counters monitor --counters 'Microsoft.AspNetCore.Hosting' -- dotnet MyApp.dll
```

输出示例：

```
[Microsoft.AspNetCore.Hosting]
    http.server.active_requests ({request})
        GET http    0
    http.server.request.duration (s)
        GET 200 / 1.1 http 50    0
        GET 200 / 1.1 http 95    0
        GET 200 / 1.1 http 99    0
```

注意每个指标都有**标签（tags）**。`http.server.active_requests` 按 `http.request.method` 和 `url.scheme` 分组，`http.server.request.duration` 则额外包含状态码、路由、协议版本和百分位数。

> 管理标签基数（可能值的数量）是可观测性中的重要课题。标签基数过高会带来存储成本上升和性能问题，这一限制通常由指标导出目标系统（如 Prometheus、Datadog）来把控。

---

## 创建自定义指标

内置指标覆盖了运行时和框架层面的通用数据，但业务逻辑相关的指标需要自己创建。下面以一个产品定价页面的请求计数为例，演示完整的实现路径。

### 第一步：创建 Meter 和 Instrument

用 `IMeterFactory`（来自 DI）创建 `Meter`，避免使用全局静态变量：

```csharp
public class ProductMetrics
{
    private readonly Counter<long> _pricingDetailsViewed;

    public ProductMetrics(IMeterFactory meterFactory)
    {
        var meter = meterFactory.Create("MyApp.Products");

        _pricingDetailsViewed = meter.CreateCounter<long>(
            "myapp.products.pricing_page_requests",
            unit: "requests",
            description: "The number of requests to the pricing details page for the given product_id");
    }

    public void PricingPageViewed(int id)
    {
        _pricingDetailsViewed.Add(
            delta: 1,
            new KeyValuePair<string, object?>("product_id", id));
    }
}
```

几点说明：
- **Meter 命名**：仿照内置 Meter 的命名风格，用应用名称加类别作前缀（`MyApp.Products`）
- **Instrument 命名**：遵循 OpenTelemetry 命名规范，小写加点分隔（`myapp.products.pricing_page_requests`）
- **类型选择**：请求数选 `Counter<long>`——`long` 而非 `int` 是因为高流量服务的请求数可能超过 `int.MaxValue`
- **标签**：用 `product_id` 标签区分不同商品，消费方可以按商品维度聚合或过滤

### 第二步：注册到 DI 并使用

```csharp
var builder = WebApplication.CreateBuilder(args);

// 注册为单例
builder.Services.AddSingleton<ProductMetrics>();

var app = builder.Build();

// 在路由处理程序中注入并使用
app.MapGet("/product/{id}", (int id, ProductMetrics metrics) =>
{
    metrics.PricingPageViewed(id);
    return $"Details for product {id}";
});

app.Run();
```

### 第三步：用 dotnet-counters 验证

启动应用后，在另一个终端：

```bash
dotnet-counters monitor -n MyApp --counters MyApp.Products
```

访问几次 `/product/{id}`，控制台输出会出现：

```
[MyApp.Products]
    myapp.products.pricing_page_requests (requests)
        product_id
        ----------
        1                  1
        234                1
        5                  4
```

`unit` 参数将默认的 `Count` 替换为 `requests`，`description` 虽然在 `dotnet-counters` 中不显示，但其他导出器（如 Prometheus 的 HELP 注释）可能会用到。

---

## 内置指标参考

.NET 和 ASP.NET Core 提供了大量内置 Meter，覆盖运行时、网络、扩展库等层面：

- [ASP.NET Core 内置指标](https://learn.microsoft.com/en-us/aspnet/core/log-mon/metrics/built-in)
- [.NET Runtime 内置指标](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/built-in-metrics-runtime)
- [System.Net 内置指标](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/built-in-metrics-system-net)
- [.NET Extensions 内置指标](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/built-in-metrics-diagnostics)

---

## 小结

System.Diagnostics.Metrics API 的使用路径很清晰：

1. 用 `IMeterFactory.Create()` 创建 `Meter`，命名遵循 OpenTelemetry 规范
2. 在 `Meter` 上调用 `CreateCounter<T>()`、`CreateHistogram<T>()` 等方法创建 `Instrument`
3. 在业务逻辑中调用封装好的记录方法
4. 配合 `dotnet-counters` 本地验证，生产环境接入 OpenTelemetry 导出器

本系列后续文章会覆盖 Observable Instrument 的实现细节、Source Generator 的使用，以及如何用 `MeterListener` 在进程内消费指标数据。

## 参考

- [Creating and consuming metrics with System.Diagnostics.Metrics APIs – Andrew Lock](https://andrewlock.net/creating-and-consuming-metrics-with-system-diagnostics-metrics-apis/)
- [System.Diagnostics.Metrics APIs 系列](https://andrewlock.net/series/system-diagnostics-metrics-apis/)
- [dotnet-counters 文档](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/dotnet-counters)
- [OpenTelemetry .NET 指标入门](https://github.com/open-telemetry/opentelemetry-dotnet/tree/main/docs/metrics/getting-started-prometheus-grafana)
