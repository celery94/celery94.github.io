---
pubDatetime: 2026-03-23T14:00:00+08:00
title: "评测 System.Diagnostics.Metrics Source Generator：省了多少代码，值不值得用"
description: "Andrew Lock 详细拆解 Microsoft.Extensions.Telemetry.Abstractions 的指标 Source Generator：它生成了什么代码、带来哪些约束、强类型标签如何使用，以及为什么他最终认为手写代码往往更好。"
tags: [".NET", "C#", "Metrics", "Source Generator", "Observability"]
slug: "exploring-system-diagnostics-metrics-source-generators"
ogImage: "../../assets/661/01-cover.png"
source: "https://andrewlock.net/creating-strongly-typed-metics-with-a-source-generator/"
---

![评测 System.Diagnostics.Metrics Source Generator](../../assets/661/01-cover.png)

这是 Andrew Lock *System.Diagnostics.Metrics APIs* 系列的第 2 篇。上一篇展示了如何手写 `Meter` 和 `Instrument` 并接入 DI；这篇走得更深——引入 `Microsoft.Extensions.Telemetry.Abstractions` 的 Source Generator，观察它具体生成什么、有什么限制，以及最终值不值得用。

---

## 从手写代码出发

上一篇的示例是一个 ASP.NET Core 应用，用一个 `ProductMetrics` 类封装 `Counter<long>`，记录产品定价页面的访问次数：

```csharp
public class ProductMetrics
{
    private readonly Counter<long> _pricingDetailsViewed;

    public ProductMetrics(IMeterFactory meterFactory)
    {
        var meter = meterFactory.Create("MyApp.Products");
        _pricingDetailsViewed = meter.CreateCounter<int>(
            "myapp.products.pricing_page_requests",
            unit: "requests",
            description: "The number of requests to the pricing details page for the product with the given product_id");
    }

    public void PricingPageViewed(int id)
    {
        _pricingDetailsViewed.Add(delta: 1, new KeyValuePair<string, object?>("product_id", id));
    }
}
```

这是 Source Generator 要替换的起点。

---

## 引入 Source Generator

安装 NuGet 包：

```bash
dotnet add package Microsoft.Extensions.Telemetry.Abstractions
```

当前稳定版为 10.2.0。

### 改写 metrics helper 类

使用 Source Generator 后，`ProductMetrics` 变成这样：

```csharp
public partial class ProductMetrics  // 必须是 partial
{
    public ProductMetrics(IMeterFactory meterFactory)
    {
        var meter = meterFactory.Create("MyApp.Products");
        PricingPageViewed = Factory.CreatePricingPageViewed(meter);
    }

    internal PricingPageViewed PricingPageViewed { get; }

    private static partial class Factory
    {
        [Counter<int>("product_id", Name = "myapp.products.pricing_page_requests")]
        internal static partial PricingPageViewed CreatePricingPageViewed(Meter meter);
    }
}
```

变化要点：
- 类必须声明为 `partial`
- 用 `[Counter<int>]` 特性标注一个 `partial` 工厂方法，Source Generator 补全它的实现
- `PricingPageViewed` 从一个方法变成了一个属性，类型是生成的 `PricingPageViewed` 类

如果需要指定 `Unit`，要加 `#pragma` 因为该 API 目前仍是实验性的：

```csharp
#pragma warning disable EXTEXP0003
[Counter<int>("product_id", Name = "myapp.products.pricing_page_requests", Unit = "views")]
internal static partial PricingPageViewed CreatePricingPageViewed(Meter meter);
#pragma warning restore EXTEXP0003
```

一个**明显限制**：`Description` 属性在特性中根本不存在，无法通过 Source Generator 为指标添加描述信息。

### 调用方的变化

```csharp
// 之前
metrics.PricingPageViewed(id);

// 使用 Source Generator 后
metrics.PricingPageViewed.Add(value: 1, product_id: id);
```

---

## 生成了什么代码

Source Generator 实际上生成了两层代码。

**工厂方法层**：

```csharp
public partial class ProductMetrics
{
    private static partial class Factory
    {
        internal static partial PricingPageViewed CreatePricingPageViewed(Meter meter)
            => GeneratedInstrumentsFactory.CreatePricingPageViewed(meter);
    }
}
```

**真正的工厂实现**，用 `ConcurrentDictionary` 缓存同一 `Meter` 对应的 `Instrument` 实例：

```csharp
internal static partial class GeneratedInstrumentsFactory
{
    private static ConcurrentDictionary<Meter, PricingPageViewed> _pricingPageViewedInstruments = new();

    internal static PricingPageViewed CreatePricingPageViewed(Meter meter)
    {
        return _pricingPageViewedInstruments.GetOrAdd(meter, static _meter =>
        {
            var instrument = _meter.CreateCounter<int>("myapp.products.pricing_page_requests", "views");
            return new PricingPageViewed(instrument);
        });
    }
}
```

**强类型包装器**：

```csharp
internal sealed class PricingPageViewed
{
    private readonly Counter<int> _counter;

    public PricingPageViewed(Counter<int> counter) => _counter = counter;

    public void Add(int value, object? product_id)
    {
        var tagList = new TagList
        {
            new KeyValuePair<string, object?>("product_id", product_id),
        };
        _counter.Add(value, tagList);
    }
}
```

这里有一个值得注意的设计：`ConcurrentDictionary` 的存在是为了支持同一个 `Instrument` 注册到多个 `Meter` 的场景。Andrew 对这个设计颇有疑问——在 OpenTelemetry 语境下，`Meter` 的概念基本是被忽略的，这种多 `Meter` 注册模式反而可能导致重复数据问题。

---

## 强类型标签

除了基本用法，Source Generator 还支持用一个 `struct` 封装所有标签，解决多参数顺序容易搞错的问题：

### 问题场景

```csharp
// 两个 int 参数，很容易传反
Add(order.Id, product.Id); // 不明显的 bug
```

### 解决方案：强类型标签结构体

```csharp
private static partial class Factory
{
    // 传 Type 而不是参数名列表
    [Counter<int>(typeof(PricingPageTags), Name = "myapp.products.pricing_page_requests")]
    internal static partial PricingPageViewed CreatePricingPageViewed(Meter meter);
}

public readonly struct PricingPageTags
{
    [TagName("product_id")]  // 自定义标签名
    public required string ProductId { get; init; }

    public required Environment Environment { get; init; }  // 枚举类型，标签名默认用属性名
}

public enum Environment { Development, QA, Production }
```

约束：
- 标签属性只能是 `string` 或 `enum` 类型
- 用 `[TagName]` 自定义标签名，否则默认用属性名

更新后的调用方：

```csharp
metrics.PricingPageViewed.Add(1, new PricingPageTags()
{
    ProductId = id.ToString(CultureInfo.InvariantCulture),
    Environment = ProductMetrics.Environment.Production,
});
```

生成的 `Add` 方法会把结构体"展开"为 `TagList`：

```csharp
public void Add(int value, PricingPageTags o)
{
    var tagList = new TagList
    {
        new KeyValuePair<string, object?>("product_id", o.ProductId!),
        new KeyValuePair<string, object?>("Environment", o.Environment.ToString()),
    };
    _counter.Add(value, tagList);
}
```

注意：`enum` 标签值通过 `.ToString()` 转成字符串，而 `enum.ToString()` 在 .NET 中[性能较差](https://andrewlock.net/updates-to-netescapaades-enumgenerators-new-apis-and-system-memory-support/#why-should-you-use-an-enum-source-generator-)，这是一个潜在的性能问题。

---

## 值得用吗

Andrew 的结论相当坦率：**大多数情况下，不值得。**

几个具体原因：

1. **节省的代码量很有限**：`Instrument` 本身只需一行 `CreateCounter<T>()`，helper 方法也就几行，Source Generator 节省不了多少
2. **API 能力反而受限**：不能设 `Description`，设 `Unit` 还要加 `#pragma`
3. **使用体验变差**：原本 `metrics.PricingPageViewed(productId: id)` 这样简洁的调用，变成了 `metrics.PricingPageViewed.Add(value: 1, product_id: id)`，还失去了有意义的参数名
4. **性能没有提升**：`TagList` 的使用方式和手写版本差不多，枚举 `.ToString()` 反而更慢
5. **生成了不必要的复杂度**：`ConcurrentDictionary` 支持的 "多 Meter" 场景在实践中几乎不需要

强类型标签这个用法有一定价值——尤其是标签数量多且类型相近时，结构体能有效防止参数传错。但这同样可以手写实现，不依赖生成器。

如果你正在使用 "同一 Instrument 注册到多个 Meter" 这个模式，或者你就是喜欢属性驱动的风格，Source Generator 还是可以考虑的。否则，手写版本更透明、更灵活，也更容易调优。

---

## 参考

- [Exploring the (underwhelming) System.Diagnostics.Metrics source generators – Andrew Lock](https://andrewlock.net/creating-strongly-typed-metics-with-a-source-generator/)
- [System.Diagnostics.Metrics APIs 系列](https://andrewlock.net/series/system-diagnostics-metrics-apis/)
- [Metrics source generator – Microsoft Docs](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/metrics-generator)
- [Strongly-typed metrics tags – Microsoft Docs](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/metrics-strongly-typed)
