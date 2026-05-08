---
pubDatetime: 2026-05-08T10:40:00+08:00
title: "C# LINQ 完整指南：从基础操作到 .NET 6-10 新增 API"
description: "本文系统梳理 C# LINQ 全部核心操作符——过滤、投影、排序、分组、联接、集合运算、聚合与元素访问，并对 .NET 6-10 新增 API（DistinctBy、MinBy、Chunk、CountBy、AggregateBy、Index、LeftJoin 等）逐一对比说明，附生产级代码示例。"
tags: ["CSharp", "LINQ", "dotnet"]
slug: "csharp-linq-complete-guide-dotnet-6-9"
ogImage: "../../assets/782/01-cover.png"
source: "https://www.devleader.ca/2026/05/07/linq-in-c-complete-guide-to-language-integrated-query-net-69"
---

LINQ（Language Integrated Query）是 C# 3.0 引入的特性，也是 .NET 开发者最常用的工具之一。它让你能用声明式、可组合的 API 查询、转换和聚合数据集合，无论数据来自内存列表、数据库还是自定义数据源。相比嵌套循环和索引变量，LINQ 写出来的代码更清楚地表达"要什么"，而非"怎么做"。

本文覆盖所有主要操作符分类，并对 .NET 6 到 .NET 10 的新增 API 逐一比较，每节都附可直接使用的代码示例。

## LINQ 是什么

LINQ 是定义在 `IEnumerable<T>` 和 `IQueryable<T>` 上的一组扩展方法。`IEnumerable<T>` 路径在内存中操作（LINQ to Objects），`IQueryable<T>` 则构建表达式树，由 provider 在运行时翻译为 SQL 或其他查询语言（Entity Framework Core 是最典型的例子）。

LINQ 有两种语法形式：

```csharp
// 查询语法 -- 类 SQL 关键字
var cheapItems =
    from p in products
    where p.Price < 50
    orderby p.Name
    select p.Name;

// 方法语法 -- 现代 C# 首选
var cheapItems =
    products
        .Where(p => p.Price < 50)
        .OrderBy(p => p.Name)
        .Select(p => p.Name);
```

两种形式编译结果相同。方法语法更受欢迎：支持全部操作符（部分操作符没有查询语法等价形式），可组合性更强，IDE 补全体验也更好。

## 过滤：Where、Any、All、Contains、OfType

过滤是最常见的 LINQ 操作。`Where` 接受谓词返回所有满足条件的元素；`Any` 和 `All` 回答存在性和全称性问题，找到答案就短路：

```csharp
public sealed record Order(int Id, string CustomerId, decimal Total, bool IsShipped);

// Where -- 基本和复合谓词
IEnumerable<Order> largeUnshipped =
    orders.Where(o => !o.IsShipped && o.Total > 500m);

// Any -- 找到第一个匹配就停止
bool hasPending = orders.Any(o => !o.IsShipped);

// All -- 遇到第一个不满足就停止；空集合返回 true
bool allShipped = orders.Any() && orders.All(o => o.IsShipped);

// OfType -- 按运行时类型过滤异质集合
IEnumerable<PremiumOrder> premiumOnly =
    mixedOrders.OfType<PremiumOrder>();
```

> 始终用 `Any()` 替代 `Count() > 0`——`Any()` 在第一个元素处短路，`Count()` 要遍历整个集合。

## 投影：Select 和 SelectMany

`Select` 把每个元素变换为新类型；`SelectMany` 把嵌套序列展平为单一流：

```csharp
public sealed record Category(string Name, IReadOnlyList<Product> Products);
public sealed record Product(string Sku, string Name, decimal Price);

// Select -- 投影到新类型
IEnumerable<string> skus = products.Select(p => p.Sku);

// Select 带索引（.NET 6+）
IEnumerable<(int Index, string Sku)> indexed =
    products.Select((p, i) => (i, p.Sku));

// .NET 9 -- Index() 取代 Select((item, i) => ...) 写法
IEnumerable<(int Index, Product Item)> withIndex =
    products.Index();

// SelectMany -- 展平所有分类下的商品
IEnumerable<Product> allProducts =
    categories.SelectMany(c => c.Products);

// SelectMany 带结果选择器 -- 保留父级上下文
IEnumerable<(string CategoryName, string Sku)> flat =
    categories.SelectMany(
        c => c.Products,
        (c, p) => (c.Name, p.Sku));
```

## 排序：OrderBy、ThenBy、Order（.NET 7）

LINQ 排序是稳定排序——相等元素保持原始相对顺序：

```csharp
public sealed record Product(string Sku, string Name, decimal Price, int Stock);

// 多键排序
IOrderedEnumerable<Product> sorted =
    products
        .OrderBy(p => p.Price)
        .ThenByDescending(p => p.Stock);

// .NET 7 之前 -- 对自然可比类型排序需要多写一个 key selector
IEnumerable<decimal> sortedPrices = prices.OrderBy(x => x);

// .NET 7 -- Order() 和 OrderDescending() 省去冗余的 key selector
IEnumerable<decimal> sortedPricesNew = prices.Order();
IEnumerable<string> sortedNamesDesc = names.OrderDescending();
```

`Order()` 和 `OrderDescending()` 要求类型实现 `IComparable<T>`。对复杂类型仍需用 `OrderBy(keySelector)` 或自定义 `IComparer<T>`。

## 分组：GroupBy、ToLookup、CountBy / AggregateBy（.NET 9）

```csharp
public sealed record Sale(string Region, string ProductSku, decimal Amount);

// GroupBy -- 延迟执行，枚举时缓冲各组数据
IEnumerable<IGrouping<string, Sale>> byRegion =
    sales.GroupBy(s => s.Region);

foreach (var group in byRegion)
    Console.WriteLine($"{group.Key}: {group.Sum(s => s.Amount):C}");

// ToLookup -- 立即执行，支持按键随机访问
ILookup<string, Sale> lookup = sales.ToLookup(s => s.Region);
IEnumerable<Sale> westSales = lookup["West"];

// .NET 9 -- CountBy：按键计数，无需具体化分组
IEnumerable<KeyValuePair<string, int>> regionCounts =
    sales.CountBy(s => s.Region);

// .NET 9 -- AggregateBy：按键累积，无需 GroupBy + 聚合
IEnumerable<KeyValuePair<string, decimal>> regionTotals =
    sales.AggregateBy(
        keySelector: s => s.Region,
        seedSelector: _ => 0m,
        func: (acc, s) => acc + s.Amount);
```

`CountBy` 和 `AggregateBy` 不具体化分组子序列，对大数据集只需要汇总值时节省大量内存。

## 联接：Join、GroupJoin、LeftJoin / RightJoin（.NET 10）、Zip

```csharp
public sealed record Customer(int Id, string Name);
public sealed record Order(int Id, int CustomerId, decimal Total);

// 内联接
var customerOrders =
    customers.Join(
        orders,
        c => c.Id,
        o => o.CustomerId,
        (c, o) => new { c.Name, o.Total });

// GroupJoin -- 左联接 + 分组；所有客户都包含在内
var customersWithTotals =
    customers.GroupJoin(
        orders,
        c => c.Id,
        o => o.CustomerId,
        (c, orderGroup) => new
        {
            c.Name,
            Total = orderGroup.Sum(o => o.Total)
        });

// .NET 10 之前 -- 左联接需要 GroupJoin + SelectMany + DefaultIfEmpty
var leftJoinOld =
    customers
        .GroupJoin(orders, c => c.Id, o => o.CustomerId,
            (c, og) => new { c, og })
        .SelectMany(
            x => x.og.DefaultIfEmpty(),
            (x, o) => new { x.c.Name, OrderTotal = o?.Total ?? 0 });

// .NET 10 -- LeftJoin 作为一级操作符
var leftJoined =
    customers.LeftJoin(
        orders,
        c => c.Id,
        o => o.CustomerId,
        (c, o) => new { c.Name, OrderTotal = o?.Total ?? 0 });

// .NET 10 -- RightJoin
var rightJoined =
    orders.RightJoin(
        customers,
        o => o.CustomerId,
        c => c.Id,
        (o, c) => new { c.Name, OrderTotal = o?.Total ?? 0 });
```

`LeftJoin` 和 `RightJoin` 是开发者手写了十几年的 `GroupJoin + SelectMany + DefaultIfEmpty` 模式的直接替代品。

## 集合运算：Distinct、DistinctBy、Union、Intersect、Except

```csharp
// Distinct -- 使用默认相等比较
IEnumerable<string> uniqueSkus = skus.Distinct();

// .NET 6 之前 -- DistinctBy 需要 GroupBy 变通
IEnumerable<Product> uniqueByNameOld =
    products
        .GroupBy(p => p.Name)
        .Select(g => g.First());

// .NET 6 -- DistinctBy：按投影键去重
IEnumerable<Product> uniqueByName =
    products.DistinctBy(p => p.Name);

// Union、Intersect、Except -- 序列上的集合运算
IEnumerable<string> allSkus    = catalogSkus.Union(warehouseSkus);
IEnumerable<string> inBoth     = catalogSkus.Intersect(warehouseSkus);
IEnumerable<string> orphans    = warehouseSkus.Except(catalogSkus);

// .NET 6 -- ExceptBy、IntersectBy、UnionBy：按键做集合运算
IEnumerable<Product> newArrivals =
    incomingProducts.ExceptBy(
        existingProducts.Select(p => p.Sku),
        p => p.Sku);
```

## 聚合：Count、Sum、Min、Max、Average、Aggregate、MinBy/MaxBy

```csharp
// 基本聚合
int orderCount      = orders.Count();
decimal totalRevenue = orders.Sum(o => o.Total);
decimal avgOrder    = orders.Average(o => o.Total);

// .NET 6 之前 -- MinBy/MaxBy 需要手写 Aggregate
Order mostExpensiveOld = orders.Aggregate((a, b) => a.Total > b.Total ? a : b);

// .NET 6 -- MinBy 和 MaxBy：返回整个元素而非仅键值
Order mostExpensive = orders.MaxBy(o => o.Total)!;
Order cheapest      = orders.MinBy(o => o.Total)!;

// Aggregate -- 通用折叠/归约
string skuList = products
    .Select(p => p.Sku)
    .Aggregate((a, b) => $"{a}, {b}");

// .NET 6 -- TryGetNonEnumeratedCount：快速计数无需遍历
if (orders.TryGetNonEnumeratedCount(out int count))
    Console.WriteLine($"Fast count: {count} orders");
```

`MinBy` 和 `MaxBy` 在需要最小/最大值对应的整个对象时特别有用，不再只能拿到键值本身。

## 元素访问：First、Last、Single、ElementAt、Chunk

```csharp
// First/Last -- 空集合时抛异常；用 *OrDefault 变体安全访问
Order latestOrder  = orders.OrderByDescending(o => o.PlacedAt).First();
Order? maybeFirst  = orders.FirstOrDefault(o => o.CustomerId == "C001");

// Single -- 期望恰好一个元素（0 或 2+ 个时抛异常）
Order exactOrder = orders.Single(o => o.Id == 42);

// ElementAt -- 按索引随机访问
Order thirdOrder = orders.ElementAt(2);

// .NET 6 之前 -- 分批需要手写 Skip/Take 循环
var batches = new List<Order[]>();
for (int i = 0; i < orders.Count; i += 100)
    batches.Add(orders.Skip(i).Take(100).ToArray());

// .NET 6 -- Chunk：把序列切成固定大小的批次
foreach (Order[] batch in orders.Chunk(100))
    await ProcessBatchAsync(batch);
```

`Chunk` 是 .NET 6 最立竿见影的新 API 之一：批量发送邮件、批量数据库写入、限流 API 调用、并行处理都能直接用。

## 延迟执行与何时具体化

`IEnumerable<T>` 上的大多数 LINQ 操作符是惰性的——定义查询时不做任何工作，迭代时才执行：

```csharp
// 这一行什么都不做
IEnumerable<Product> query = products.Where(p => p.Price > 100);

// 过滤在这里发生 -- 每次迭代都会跑一遍
foreach (var p in query) Console.WriteLine(p.Name);

// 再次迭代时，过滤再跑一遍
int count = query.Count(); // 第二次完整遍历

// 需要稳定快照或多次迭代时，立即具体化
List<Product> snapshot = products.Where(p => p.Price > 100).ToList();
```

以下情况应调用 `ToList()` 或 `ToArray()`：
- 需要稳定快照（数据源可能在迭代期间变化）
- 结果要被多次迭代（避免重复计算成本）
- 查询捕获了作用域资源（如 `DbContext`），迭代前可能被 dispose

## .NET 6 到 .NET 10 新增 API 一览

| API | 版本 | 说明 |
|---|---|---|
| `DistinctBy(keySelector)` | .NET 6 | 按投影键去重 |
| `MinBy(keySelector)` | .NET 6 | 返回最小投影键对应的完整元素 |
| `MaxBy(keySelector)` | .NET 6 | 返回最大投影键对应的完整元素 |
| `ExceptBy / IntersectBy / UnionBy` | .NET 6 | 按键选择器做集合运算 |
| `Chunk(size)` | .NET 6 | 切分为固定大小批次 |
| `TryGetNonEnumeratedCount` | .NET 6 | 快速计数无需枚举 |
| `Order()` | .NET 7 | 对自然可比类型排序（无需键选择器） |
| `OrderDescending()` | .NET 7 | 降序排序（无需键选择器） |
| `CountBy(keySelector)` | .NET 9 | 按键计数，不具体化分组 |
| `AggregateBy(key, seed, func)` | .NET 9 | 按键累积，不需要 GroupBy |
| `Index()` | .NET 9 | 枚举时携带索引（取代 `Select((x, i) => ...)` 写法） |
| `LeftJoin(...)` | .NET 10 | 无需 GroupJoin 样板的左外联接 |
| `RightJoin(...)` | .NET 10 | 无需 GroupJoin 样板的右外联接 |

## 常见问题

**LINQ 支持数据库查询吗？**  
支持。当数据源实现 `IQueryable<T>`（如 Entity Framework Core 提供的），LINQ 表达式树会在执行时翻译为 SQL。但部分操作符无法翻译，会在运行时抛异常或强制客户端求值。开发阶段务必检查生成的 SQL。

**LINQ 是线程安全的吗？**  
在独立序列上并发运行 LINQ to Objects 操作是安全的，但 LINQ 不会让底层集合变成线程安全的。如果一个线程在修改 `List<T>` 的同时另一个线程在用 LINQ 迭代它，行为是未定义的。

**`GroupBy` 和 `CountBy`（.NET 9）有什么性能差别？**  
`GroupBy` 为每个分组分配一个 `IGrouping<K, T>` 对象，并把所有匹配元素缓冲到内存中。`CountBy` 只跟踪每个键的计数，从不具体化分组元素。对大型集合只需要频率统计时，`CountBy` 显著比 `GroupBy(...).Select(g => (g.Key, g.Count()))` 节省内存。

## 参考

- [原文：LINQ in C#: Complete Guide to Language Integrated Query (.NET 6-9)](https://www.devleader.ca/2026/05/07/linq-in-c-complete-guide-to-language-integrated-query-net-69)
- [.NET 文档：LINQ 概述](https://learn.microsoft.com/dotnet/csharp/linq/)
- [.NET 文档：System.Linq 命名空间](https://learn.microsoft.com/dotnet/api/system.linq)
