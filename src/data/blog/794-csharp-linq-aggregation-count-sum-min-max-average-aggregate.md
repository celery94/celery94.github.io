---
pubDatetime: 2026-05-14T13:25:00+08:00
title: "C# LINQ 聚合操作全解：Count、Sum、Min、Max、Average 与 Aggregate"
description: "LINQ 聚合操作覆盖从计数、求和到自定义折叠的完整场景。本文结合 Order/Product/SalesData 领域模型，演示所有聚合操作符的用法，重点解析 Count vs Any 性能陷阱、.NET 6 新增的 MinBy/MaxBy 如何单次遍历直接拿到元素，以及 Aggregate 如何在一次遍历中同时计算多个统计值。"
tags: ["C#", ".NET", "LINQ"]
slug: "csharp-linq-aggregation-count-sum-min-max-average-aggregate"
ogImage: "../../assets/794/01-cover.png"
source: "https://www.devleader.ca/2026/05/12/linq-aggregation-in-c-count-sum-min-max-average-and-aggregate"
---

![C# LINQ 聚合操作漫画封面](../../assets/794/01-cover.png)

把一个序列化简为一个有意义的值，是数据密集型 .NET 应用中最频繁的操作之一。LINQ 的聚合操作符从最平凡的 `Count`、`Sum`，到灵活的 `Aggregate`，覆盖了几乎所有场景。.NET 6 还补充了 `MinBy` 和 `MaxBy`——这两个等待已久的操作符能直接返回具有最小或最大投影值的**元素**，而不仅仅是那个值本身。

这篇文章完整走过所有聚合操作符，重点讲清楚 `Count` vs `Any` 的性能陷阱，以及 `Aggregate` 如何把多次遍历压缩成一次高效折叠。

## 领域模型

后面的例子都基于 Order、Product、SalesData 三个 record：

```csharp
namespace DevLeader.LinqAggregation;

public record Order(int Id, string CustomerId, string Status, decimal Total, DateTimeOffset PlacedAt);
public record Product(int Id, string Name, string Category, decimal Price, int StockLevel);
public record SalesData(string Region, string ProductId, int UnitsSold, decimal Revenue, DateTimeOffset Period);
```

## Count 和 LongCount

`Count()` 返回序列中的元素数量（`int`）；`Count(predicate)` 只统计满足条件的元素：

```csharp
IEnumerable<Order> orders = GetOrders();

int total        = orders.Count();
int pendingCount = orders.Count(o => o.Status == "Pending");
int paidCount    = orders.Count(o => o.Status == "Paid");

Console.WriteLine($"Total: {total}, Pending: {pendingCount}, Paid: {paidCount}");
```

对于可能超过 `int.MaxValue`（约 21 亿）的超大序列，用 `LongCount()` 返回 `long`：

```csharp
long recordCount = GetAllAuditLogs().LongCount();
```

实际上 `LongCount` 很少用到，主要在日志、遥测或数据仓库等大规模场景下才需要。

### Count vs Any：一个常见性能陷阱

这是 LINQ 里最常见的误用之一：

```csharp
// ❌ Count() 必须遍历整个序列 — O(n)
if (orders.Count(o => o.Status == "Pending") > 0)
{
    Console.WriteLine("有待处理订单");
}

// ✅ Any() 找到第一个匹配就停止 — O(1) 最优
if (orders.Any(o => o.Status == "Pending"))
{
    Console.WriteLine("有待处理订单");
}
```

`Any(predicate)` 在找到第一个匹配元素后立即短路，`Count(predicate)` 无论如何都要扫描全部元素才能给出准确计数。当序列很大、数据源是数据库查询或具体化代价高时，差距非常明显。

同样，判断序列是否为空时：

```csharp
// ❌ 遍历整个序列
if (orders.Count() == 0) { }

// ✅ 只看第一个元素
if (!orders.Any()) { }
```

**原则**：做存在性检查用 `Any()`，真正需要数量时才用 `Count()`。

## Sum 和 Average

`Sum(selector)` 和 `Average(selector)` 接受一个投影函数，先把每个元素映射到数值再聚合：

```csharp
IEnumerable<Order> orders = GetOrders();

decimal totalRevenue  = orders.Sum(o => o.Total);
decimal averageOrder  = orders.Average(o => o.Total);

Console.WriteLine($"总收入: ${totalRevenue:F2}");
Console.WriteLine($"平均订单: ${averageOrder:F2}");
```

**两个边界情况要注意**：

- `Sum` 对空序列或全 null 元素返回 **0**，不会抛异常。
- `Average` 对空序列抛出 `InvalidOperationException`，用前需要用 `Any()` 保护：

```csharp
IEnumerable<Order> recentOrders = GetRecentOrders();
decimal? safeAverage = recentOrders.Any()
    ? recentOrders.Average(o => o.Total)
    : null;
```

实际场景——按地区汇总收入：

```csharp
IEnumerable<SalesData> sales = GetSalesData();

var revenueByRegion = sales
    .GroupBy(s => s.Region)
    .Select(g => new
    {
        Region       = g.Key,
        TotalRevenue = g.Sum(s => s.Revenue),
        AverageUnits = g.Average(s => s.UnitsSold)
    })
    .OrderByDescending(x => x.TotalRevenue);

foreach (var row in revenueByRegion)
    Console.WriteLine($"{row.Region}: ${row.TotalRevenue:F0} 收入, {row.AverageUnits:F1} 平均件数");
```

## Min 和 Max

`Min(selector)` 和 `Max(selector)` 返回投影后的最小/最大**标量值**，不是元素本身：

```csharp
IEnumerable<Product> products = GetProducts();

decimal cheapest      = products.Min(p => p.Price);
decimal mostExpensive = products.Max(p => p.Price);

Console.WriteLine($"价格区间: ${cheapest:F2} -- ${mostExpensive:F2}");
```

如果需要最便宜的那个 `Product` 对象，老写法得遍历两次，还有潜在 bug：

```csharp
// .NET 6 之前 — 两次遍历，价格相同时行为不确定
decimal minPrice      = products.Min(p => p.Price);
Product? cheapestOld  = products.FirstOrDefault(p => p.Price == minPrice);
```

## MinBy 和 MaxBy（.NET 6）：直接拿元素

`MinBy(keySelector)` 和 `MaxBy(keySelector)` 单次遍历，直接返回具有最小或最大 key 值的**元素**：

```csharp
// .NET 6 — 单次遍历，直接返回元素
Product? cheapestNew  = products.MinBy(p => p.Price);
Product? mostExpensive = products.MaxBy(p => p.Price);

Console.WriteLine($"最便宜: {cheapestNew?.Name} 售价 ${cheapestNew?.Price:F2}");
Console.WriteLine($"最贵: {mostExpensive?.Name} 售价 ${mostExpensive?.Price:F2}");
```

当多个元素共享相同的最小/最大 key 时，`MinBy`/`MaxBy` 返回**第一个**遇到的元素，与 `OrderBy().First()` 的语义一致。

实际场景——找最优销售地区：

```csharp
IEnumerable<SalesData> sales = GetSalesData();

// 单条记录里收入最高的
SalesData? topPeriod = sales.MaxBy(s => s.Revenue);
Console.WriteLine($"最高单期: {topPeriod?.Region} — ${topPeriod?.Revenue:F2}");

// 按地区汇总后，找收入最低的地区
var revenueSummary = sales
    .GroupBy(s => s.Region)
    .Select(g => (Region: g.Key, Total: g.Sum(s => s.Revenue)));

(string Region, decimal Total) worstRegion = revenueSummary.MinBy(r => r.Total);
Console.WriteLine($"最低收入地区: {worstRegion.Region} (${worstRegion.Total:F2})");
```

## Aggregate：自定义折叠

`Aggregate` 是最通用的聚合操作符，接受一个种子值和一个累加函数，把序列"折叠"成任意结果：

```csharp
IEnumerable<Order> orders = GetOrders();

// 把订单 ID 拼成逗号分隔字符串
string orderList = orders.Aggregate(
    string.Empty,
    (acc, order) => string.IsNullOrEmpty(acc)
        ? order.Id.ToString()
        : $"{acc},{order.Id}");

Console.WriteLine($"订单列表: {orderList}");
```

实际场景——计算叠加折扣的复合系数：

```csharp
decimal[] discounts = [0.10m, 0.05m, 0.15m]; // 10%、5%、15%

// 乘法叠加折扣因子
decimal combinedFactor = discounts.Aggregate(
    1.0m,
    (factor, discount) => factor * (1 - discount));

Console.WriteLine($"综合折扣因子: {combinedFactor:P2}"); // 例如 72.54%
```

### 带结果投影的三参数重载

三参数重载在所有元素处理完成后，对累计结果再做一次投影：

```csharp
IEnumerable<SalesData> sales = GetSalesData();

// 一次遍历同时积累总和与计数，最后投影为平均值
decimal averageRevenue = sales.Aggregate(
    seed: (Total: 0m, Count: 0),
    func: (acc, s) => (acc.Total + s.Revenue, acc.Count + 1),
    resultSelector: acc => acc.Count > 0 ? acc.Total / acc.Count : 0m);

Console.WriteLine($"平均收入: ${averageRevenue:F2}");
```

这是**单次遍历的平均值**——避免了先 `Sum` 再 `Count` 的两次遍历。

## 一次遍历计算多个统计值

对同一个序列天真地多次调用聚合操作符意味着多次遍历。当数据源来自网络调用、文件读取或 EF Core 查询时，这个成本会很显著。用 `Aggregate` 把多个累加器合并成一次折叠：

```csharp
public record AggregateSummary(int Count, decimal Sum, decimal Min, decimal Max);

IEnumerable<Order> orders = GetOrders();

AggregateSummary summary = orders.Aggregate(
    new AggregateSummary(0, 0m, decimal.MaxValue, decimal.MinValue),
    (acc, order) => new AggregateSummary(
        acc.Count + 1,
        acc.Sum + order.Total,
        Math.Min(acc.Min, order.Total),
        Math.Max(acc.Max, order.Total)));

decimal average = summary.Count > 0 ? summary.Sum / summary.Count : 0m;

Console.WriteLine($"Count:   {summary.Count}");
Console.WriteLine($"Sum:     ${summary.Sum:F2}");
Console.WriteLine($"Min:     ${summary.Min:F2}");
Console.WriteLine($"Max:     ${summary.Max:F2}");
Console.WriteLine($"Average: ${average:F2}");
```

一次遍历，四个值。在 CQRS 查询处理器中，如果查询结果需要多个统计指标且数据来自外部服务，这个模式特别有价值。

## TryGetNonEnumeratedCount（.NET 6）

在进行需要计数的聚合（比如提前分配或日志记录）之前，先尝试无遍历获取数量：

```csharp
IEnumerable<Order> orders = GetOrders();

if (orders.TryGetNonEnumeratedCount(out int count))
{
    Console.WriteLine($"快速计数: {count}");
    // 可以直接用这个 count，不需要再遍历
}
else
{
    // 回退：必须遍历才能得到数量
    count = orders.Count();
}
```

对 `List<T>`、数组、`HashSet<T>`、`Dictionary<TKey,TValue>` 等实现了 `ICollection<T>` 的类型返回 `true`；对懒执行管道、`GroupBy` 结果等必须遍历才能确定长度的类型返回 `false`。

## 操作符选择速查

| 场景 | 推荐操作符 |
|------|-----------|
| 检查是否存在匹配元素 | `Any(predicate)` |
| 统计元素数量 | `Count()` / `Count(predicate)` |
| 投影值求和 | `Sum(selector)` |
| 投影值平均 | `Average(selector)` |
| 最小/最大标量值 | `Min(selector)` / `Max(selector)` |
| 最小 key 对应的元素（.NET 6+） | `MinBy(keySelector)` |
| 最大 key 对应的元素（.NET 6+） | `MaxBy(keySelector)` |
| 按 key 自定义累加（.NET 9） | `AggregateBy` |
| 按 key 计数（.NET 9） | `CountBy` |
| 通用折叠（带种子） | `Aggregate(seed, func)` |
| 通用折叠（带结果投影） | `Aggregate(seed, func, resultSelector)` |

.NET 9 新增的 `AggregateBy` 和 `CountBy` 对按 key 分组聚合比 `GroupBy` 更简洁，如果使用 .NET 9+ 可以优先考虑。

## 几个常见问题

**为什么应该用 `Any()` 而不是 `Count() > 0`？**  
`Any()` 找到第一个匹配元素就停止，最优 O(1)。`Count()` 无论如何都必须扫描全部元素，O(n)。存在性检查始终用 `Any()`。

**`Min` 和 `MinBy` 有什么区别？**  
`Min(selector)` 返回投影后的**最小值**（标量，如 `decimal`）；`MinBy(keySelector)` 返回具有最小 key 的**元素**。比如 `products.Min(p => p.Price)` 返回 `9.99m`，而 `products.MinBy(p => p.Price)` 返回价格为 `9.99m` 的那个 `Product` 对象。

**怎么一次遍历计算多个统计值？**  
用带 tuple 或 record 种子的 `Aggregate(seed, func)` 同时积累所有值，避免多次遍历。见上面的 `AggregateSummary` 例子。

**`Average` 会在空序列上抛异常吗？**  
是的，抛 `InvalidOperationException`。调用前用 `Any()` 保护，或用可空重载 `Average(Func<T, decimal?>)` 配合 null 条件处理。

**`Aggregate` 可以替代 foreach 循环吗？**  
可以，但仅限于"归约为单一结果"的纯变换场景。如果需要副作用（比如写入列表或打日志），`foreach` 更可读、更符合惯例。

## 小结

LINQ 聚合操作符提供了把序列化简为有意义值的完整工具箱：

- `Count` 和 `Any`：存在性检查用 `Any`，需要数量时才用 `Count`
- `Sum`、`Average`、`Min`、`Max`：标准数值聚合，都支持 selector
- `MinBy` / `MaxBy`（.NET 6）：单次遍历直接返回元素，告别两次遍历写法
- `Aggregate`：通用折叠，支持多值单次聚合和最终结果投影
- `TryGetNonEnumeratedCount`（.NET 6）：对集合类型快速获取数量，不触发遍历

这些操作符与 `GroupBy`、`Join`、过滤等操作自然组合，构建完整的数据处理管道。

## 参考

- [原文：LINQ Aggregation in C#: Count, Sum, Min, Max, Average, and Aggregate](https://www.devleader.ca/2026/05/12/linq-aggregation-in-c-count-sum-min-max-average-and-aggregate)
