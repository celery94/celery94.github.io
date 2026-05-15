---
pubDatetime: 2026-05-15T08:59:00+08:00
title: "C# LINQ 连接完全指南：Join、GroupJoin、LeftJoin、RightJoin 与 Zip"
description: "全面讲解 C# LINQ 的各类连接操作——从 Join 内连接、GroupJoin 分组连接，到 .NET 10 新增的 LeftJoin 与 RightJoin，再到 Zip 位置配对。每种操作对应 SQL 场景，含完整代码示例。"
tags: ["CSharp", "LINQ", "dotnet", "dotnet10"]
slug: "csharp-linq-joins-complete-guide"
ogImage: "../../assets/795/01-cover.png"
source: "https://www.devleader.ca/2026/05/14/linq-joins-in-c-join-groupjoin-leftjoin-rightjoin-and-zip"
---

![C# LINQ 连接完全指南封面](../../assets/795/01-cover.png)

只要你处理过两个内存集合的关联查询，就一定遇到过 LINQ 连接的问题。`Join` 处理简单的等值内连接够用，但一旦需要保留没有匹配项的行——也就是左外连接——历史写法会变成繁琐的 `GroupJoin` + `SelectMany` + `DefaultIfEmpty` 三步组合。这个问题在 .NET 10 里得到了解决：新增了直接可用的 `LeftJoin` 和 `RightJoin` 操作符。

本文覆盖 LINQ 连接的完整图谱：内连接、分组连接、左/右外连接、交叉连接，以及按位置配对的 `Zip`，每种都附有贴近实际业务的例子和对应的 SQL 写法。

## 领域模型

文中所有示例统一使用 Customer / Order / Product 三个实体：

```csharp
namespace DevLeader.LinqJoins;

public record Customer(int Id, string Name, string Region);
public record Order(int Id, int CustomerId, int ProductId, int Quantity, DateTimeOffset PlacedAt);
public record Product(int Id, string Name, decimal UnitPrice, string Category);
```

这三个实体提供了自然的连接场景：客户的订单、订单上的商品、没有下单的客户，等等。

## Join：内连接

`Join` 根据键选择器匹配两个序列中的元素，双侧都没有匹配到的元素会被丢弃——这等同于 SQL 的 `INNER JOIN`。

```csharp
namespace DevLeader.LinqJoins;

IEnumerable<Customer> customers = GetCustomers();
IEnumerable<Order> orders       = GetOrders();

// 内连接：只保留有过至少一笔订单的客户
var customerOrders = customers.Join(
    inner:            orders,
    outerKeySelector: c => c.Id,
    innerKeySelector: o => o.CustomerId,
    resultSelector:   (customer, order) => new
    {
        customer.Name,
        customer.Region,
        order.Id,
        order.PlacedAt,
        order.Quantity
    });

foreach (var row in customerOrders)
{
    Console.WriteLine($"{row.Name} ({row.Region}) -- Order #{row.Id} on {row.PlacedAt:d}");
}
```

对应 SQL：

```sql
SELECT c.Name, c.Region, o.Id, o.PlacedAt, o.Quantity
FROM Customers c
INNER JOIN Orders o ON c.Id = o.CustomerId
```

### 三表连接

链式连接就是把第一次连接的结果作为下一次连接的外序列：

```csharp
namespace DevLeader.LinqJoins;

IEnumerable<Product> products = GetProducts();

// Customers -> Orders -> Products（三表内连接）
var orderDetails = customers
    .Join(orders,
          c => c.Id,
          o => o.CustomerId,
          (c, o) => new { Customer = c, Order = o })
    .Join(products,
          co => co.Order.ProductId,
          p => p.Id,
          (co, p) => new
          {
              co.Customer.Name,
              ProductName = p.Name,
              p.UnitPrice,
              co.Order.Quantity,
              LineTotal = p.UnitPrice * co.Order.Quantity
          });

foreach (var detail in orderDetails)
{
    Console.WriteLine(
        $"{detail.Name} bought {detail.Quantity}x {detail.ProductName} " +
        $"= ${detail.LineTotal:F2}");
}
```

三表以上的链式连接会变得很冗长。如果查询逻辑在多处重复，考虑把它收敛到专门的查询处理器里，而不是散落在各个控制器 Action 里。

## GroupJoin：旧式左外连接写法

.NET 10 之前，实现左外连接需要 `GroupJoin` + `SelectMany` + `DefaultIfEmpty` 三步：

```csharp
namespace DevLeader.LinqJoins;

// .NET 10 之前的左外连接——客户及其所有订单（无订单时为 null）
var leftJoinOld = customers.GroupJoin(
    orders,
    c => c.Id,
    o => o.CustomerId,
    (customer, matchedOrders) => new { customer, matchedOrders })
    .SelectMany(
        x => x.matchedOrders.DefaultIfEmpty(),
        (x, order) => new
        {
            x.customer.Name,
            OrderId   = order?.Id,
            OrderDate = order?.PlacedAt
        });

foreach (var row in leftJoinOld)
{
    Console.WriteLine(row.OrderId.HasValue
        ? $"{row.Name} -- Order #{row.OrderId} on {row.OrderDate:d}"
        : $"{row.Name} -- (no orders)");
}
```

这段代码能用，但意图被淹没在三层嵌套里。对有 SQL 背景的开发者来说，`GroupJoin` + `SelectMany` + `DefaultIfEmpty` 的组合特别难读。

### GroupJoin 的真正用途

`GroupJoin` 有自己合理的使用场景：当你确实需要每个外部元素对应一个**子集合**时：

```csharp
namespace DevLeader.LinqJoins;

// 客户及其订单集合（不展开）
var customersWithOrders = customers.GroupJoin(
    orders,
    c => c.Id,
    o => o.CustomerId,
    (customer, matchedOrders) => new
    {
        customer.Name,
        Orders     = matchedOrders.ToList(),
        TotalSpend = matchedOrders.Sum(o => o.Quantity) // 简化示例
    });

foreach (var row in customersWithOrders)
{
    Console.WriteLine($"{row.Name}: {row.Orders.Count} orders");
}
```

**结论**：`GroupJoin` 适合"一对多且需要完整子集合"的场景。其他需要左外连接语义的情况，用下面的 .NET 10 新操作符更清晰。

## .NET 10：LeftJoin

`LeftJoin` 正是为替代 `GroupJoin`/`SelectMany`/`DefaultIfEmpty` 这个写法而加入 .NET 10 的。它的 API 和 `Join` 完全一致，语义上保证外侧（左侧）的每个元素都出现在结果里：

```csharp
namespace DevLeader.LinqJoins;

// .NET 10 写法——与上面三步组合结果相同，可读性大幅提升
var leftJoin = customers.LeftJoin(
    orders,
    c => c.Id,
    o => o.CustomerId,
    (customer, order) => new
    {
        customer.Name,
        customer.Region,
        OrderId   = order?.Id,
        OrderDate = order?.PlacedAt
    });

foreach (var row in leftJoin)
{
    Console.WriteLine(row.OrderId.HasValue
        ? $"{row.Name} ({row.Region}) -- Order #{row.OrderId}"
        : $"{row.Name} ({row.Region}) -- (no orders)");
}
```

对应 SQL：

```sql
SELECT c.Name, c.Region, o.Id, o.PlacedAt
FROM Customers c
LEFT JOIN Orders o ON c.Id = o.CustomerId
```

结果选择器里的 `order` 参数是可空的——当内侧没有匹配元素时它就是 `null`，和 SQL `LEFT JOIN` 的行为一致。

### 用默认值替代 null

如果你不想在结果里出现 null，可以在结果选择器里投影成带默认值的类型：

```csharp
namespace DevLeader.LinqJoins;

public record OrderSummary(int? Id, DateTimeOffset? PlacedAt, bool HasOrder);

var leftJoinWithDefault = customers.LeftJoin(
    orders,
    c  => c.Id,
    o  => o.CustomerId,
    (c, o) => new
    {
        c.Name,
        Summary = o is null
            ? new OrderSummary(null, null, false)
            : new OrderSummary(o.Id, o.PlacedAt, true)
    });
```

## .NET 10：RightJoin

`RightJoin` 保留每个内侧（右侧）元素，外侧没有匹配的情况下填 `null`，等同于 SQL 的 `RIGHT JOIN`，与 `LeftJoin` 对称：

```csharp
namespace DevLeader.LinqJoins;

IEnumerable<Order>    allOrders   = GetAllOrders();   // 可能含无效客户的孤儿订单
IEnumerable<Customer> activeUsers = GetActiveCustomers();

// 每笔订单都出现——包括没有匹配客户的孤儿订单
var rightJoin = activeUsers.RightJoin(
    allOrders,
    c => c.Id,
    o => o.CustomerId,
    (customer, order) => new
    {
        CustomerName = customer?.Name ?? "(orphaned)",
        order.Id,
        order.PlacedAt
    });

foreach (var row in rightJoin)
{
    Console.WriteLine($"Order #{row.Id} -- Customer: {row.CustomerName}");
}
```

对应 SQL：

```sql
SELECT COALESCE(c.Name, '(orphaned)'), o.Id, o.PlacedAt
FROM Customers c
RIGHT JOIN Orders o ON c.Id = o.CustomerId
```

`RightJoin` 实际使用频率低于 `LeftJoin`——你总可以交换参数顺序，改用 `LeftJoin` 达到同样效果。但有了两个操作符，代码可以直接匹配你的思维模型："从订单出发，可选地带入客户数据"，不用为了凑成左连接而调换序列顺序。

> **IQueryable\<T\> 注意**：`LeftJoin` 和 `RightJoin` 是 .NET 10 加入的 LINQ to Objects 操作符。`IQueryable<T>` 提供程序（如 Entity Framework Core）对这两个操作符的翻译支持可能落后于运行时发布，使用前请查阅对应提供程序的发行说明。

## Zip：位置配对

`Zip` 不是关系连接——它按**位置**配对两个序列的元素：序列 A 的第一个元素和序列 B 的第一个元素配对，以此类推。如果一个序列比另一个长，多余的元素会被静默丢弃（双参数重载）。

```csharp
namespace DevLeader.LinqJoins;

string[] customerNames = ["Alice", "Bob", "Carol"];
int[]    loyaltyPoints = [1200, 450, 3300];

// 按位置配对
IEnumerable<(string Name, int Points)> paired = customerNames.Zip(loyaltyPoints);

foreach ((string name, int points) in paired)
{
    Console.WriteLine($"{name}: {points} points");
}
```

带结果选择器的写法：

```csharp
IEnumerable<string> summary = customerNames.Zip(
    loyaltyPoints,
    (name, points) => $"{name} has {points} loyalty points");
```

.NET 6+ 还提供三序列重载：

```csharp
string[]  names  = ["Alice", "Bob", "Carol"];
int[]     orders = [12, 5, 22];
decimal[] spend  = [4200m, 320m, 8500m];

IEnumerable<(string, int, decimal)> triples = names.Zip(orders, spend);
```

`Zip` 适合把标签列表和值配对、或交错两个已对齐排序的列表。**如果对应元素的位置可能漂移，请用 `Join` 做键连接，而不是 `Zip`。**

## 用 SelectMany 实现交叉连接

交叉连接产生两个序列所有元素的笛卡尔积，LINQ 通过 `SelectMany` 实现：

```csharp
namespace DevLeader.LinqJoins;

string[] sizes  = ["S", "M", "L", "XL"];
string[] colors = ["Red", "Blue", "Green"];

// 所有尺码-颜色组合
IEnumerable<string> skus = sizes.SelectMany(
    _ => colors,
    (size, color) => $"{size}-{color}");

foreach (string sku in skus)
{
    Console.WriteLine(sku); // S-Red, S-Blue, ... XL-Green
}
```

交叉连接的结果规模是两个序列长度之积，成本较高——确认确实需要完整笛卡尔积再用。

## LINQ 连接与 SQL 连接对照表

| SQL 连接 | .NET 10 之前的写法 | .NET 10+ 写法 |
|---|---|---|
| INNER JOIN | `Join()` | `Join()` |
| LEFT OUTER JOIN | `GroupJoin().SelectMany().DefaultIfEmpty()` | `LeftJoin()` |
| RIGHT OUTER JOIN | 反向 `GroupJoin()` 变通写法 | `RightJoin()` |
| CROSS JOIN | `SelectMany()` | `SelectMany()` |
| FULL OUTER JOIN | `LeftJoin` 结果 `Concat` `RightJoin` 结果 | 手动实现，无内置 |

全外连接（FULL OUTER JOIN）在 LINQ 里没有单一内置操作符，需要把 `LeftJoin` 的结果和过滤后的 `RightJoin` 结果拼接起来。这种需求足够罕见，通常按需封装一个小扩展方法即可。

## 几点实践建议

**大序列在连接前先物化**：如果两侧序列都是懒求值的，`Join` 会对每个外侧元素重新枚举内侧序列一次。对内侧序列先调用 `.ToList()`。

**复杂连接放进查询处理器**：涉及客户、订单、商品三表的查询不该散落在控制器 Action 里，而应收敛到独立的查询处理器，和它服务的功能放在一起。

**枚举状态字段是常见的连接键**：如果你在用枚举列做连接，注意值的规范化。

**相似度连接用不上 LINQ 的等值判断**：如果你在找"相近"的商品而非精确匹配，等值连接帮不上忙，考虑语义搜索方案。

## 常见问题

### Join 和 GroupJoin 的区别是什么？

`Join` 产生扁平序列，每个外侧元素与每个匹配的内侧元素一一配对。`GroupJoin` 产生的序列里，每个外侧元素对应一个**集合**，包含所有匹配的内侧元素。`GroupJoin` 是 .NET 10 之前实现左外连接的基础，但它在"需要分组结果而非展开投影"时同样有价值。

### .NET 10 之前怎么做左外连接？

用 `GroupJoin` 加 `SelectMany` 加 `DefaultIfEmpty`：
```csharp
outer.GroupJoin(inner, outerKey, innerKey, (o, matches) => new { o, matches })
     .SelectMany(x => x.matches.DefaultIfEmpty(), (x, i) => resultSelector(x.o, i))
```
.NET 10 及以上直接用 `LeftJoin`。

### 如何在 LINQ 里用多个键连接？

在两侧的键选择器里都传匿名类型或值元组：
```csharp
.Join(inner,
      o => new { o.CategoryId, o.RegionId },
      i => new { i.CategoryId, i.RegionId },
      ...)
```
匿名类型使用结构相等，只要两侧属性名和类型一致就能正常工作。

### 什么时候用 Zip 而不是 Join？

元素通过**位置**而非共享键对应时用 `Zip`。常见场景：把一批值和预生成的标签列表配对，或交错两个有意对齐排序的序列。需要按键字段做关系匹配时，始终优先用 `Join`、`LeftJoin` 或 `RightJoin`。

## 小结

LINQ 连接覆盖了宽广的数据关联场景：

- **`Join`** 适合等值内连接，不匹配的行不需要保留时用它，干净高效
- **`GroupJoin`** 适合"一个外侧元素对应一组内侧元素"的场景，不该再被当成左连接变通写法
- **.NET 10 的 `LeftJoin` 和 `RightJoin`** 彻底取代了 `GroupJoin`/`SelectMany`/`DefaultIfEmpty` 的繁琐写法——只要你在 .NET 10 上，就该把旧写法换掉
- **`Zip`** 处理位置配对，不能替代键连接
- **`SelectMany` 实现交叉连接**功能强大但代价高，谨慎使用

## 参考

- [原文：LINQ Joins in C#: Join, GroupJoin, LeftJoin, RightJoin, and Zip](https://www.devleader.ca/2026/05/14/linq-joins-in-c-join-groupjoin-leftjoin-rightjoin-and-zip)
