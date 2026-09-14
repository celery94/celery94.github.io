---
pubDatetime: 2026-09-14T08:22:00+08:00
title: "不常用的 LINQ 方法速查：版本与易错点"
description: "Where 和 Select 之外，LINQ 还有一批很少用到但很省事的方法。本文按聚合、集合运算、连接、切片、排序和分组配对整理，核对每个方法在哪个 .NET 版本加入，并标出空序列、去重和延迟执行这些容易踩的边界。"
tags: [".NET", "LINQ", "C#", ".NET 9", ".NET 10"]
slug: "less-known-linq-methods-reference"
ogImage: "../../assets/1065/01-cover.jpg"
source: "https://developmentwithadot.blogspot.com/2026/09/less-known-linq-methods.html"
---

「按键分组求和」你写了一个循环加一个字典；「取序列最后两个元素」你写了 `list.Count - 2`；「两个序列按主键取交集」你建了两个 `HashSet`。这三件事 LINQ 里都有现成方法，只是平时想不起来。

Ricardo Peres 在 [Less Known LINQ Methods](https://developmentwithadot.blogspot.com/2026/09/less-known-linq-methods.html) 里列了十几组不常被提起的 `Enumerable` 扩展方法，每组配一个最小例子。原文是按方法名字母序排的，读起来像字典。本文换个组织方式——按你手上的任务分类，并补上原文没写的一件事：**每个方法属于哪个 .NET 版本**。这一点很关键，因为其中几个是 .NET 9 和 .NET 10 才有的，而你手上的项目未必能升级。清单里的版本我都对着 `dotnet/runtime` 的发布标签核对过。

## 先看版本表

| 方法                                                                                               | 引入版本                        |
| -------------------------------------------------------------------------------------------------- | ------------------------------- |
| `Aggregate`、`ToLookup`、`Except`、`Intersect`、`Union`、`Zip`（双序列）、`SkipWhile`、`TakeWhile` | LINQ 原始（.NET 3.5）           |
| `Append`、`Prepend`、`TakeLast`                                                                    | .NET Core 2.0                   |
| `Chunk`、`MaxBy`、`MinBy`、`ExceptBy`、`IntersectBy`、`UnionBy`、`Zip`（三序列）                   | .NET 6                          |
| `AggregateBy`、`CountBy`、`Index`、`Order`、`OrderDescending`                                      | .NET 9                          |
| `LeftJoin`、`RightJoin`                                                                            | .NET 10                         |
| `FullJoin`                                                                                         | .NET 11（预览版，正式版未发布） |

`FullJoin` 这一行值得单独说：原文写的是「will come in .NET 11+」，这个判断是准确的。我在 `dotnet/runtime` 上核对了三个发布标签——`LeftJoin.cs` 和 `RightJoin.cs` 在 `v10.0.0` 里已经存在，而 `FullJoin.cs` 只出现在 `main` 分支，没有进 `v10.0.0`。所以你在 .NET 10 上写 `FullJoin` 会编译不过。

## 聚合与计数

`Aggregate` 把整个序列压成一个值；`AggregateBy` 先按键分组，再对每组做同样的累积（.NET 9）。

```csharp
// 整体求积
var product = new[] { 2, 3, 4 }.Aggregate((acc, x) => acc * x); // 24

// 按首字母分组累加长度
var words = new[] { "apple", "ant", "bear", "bee" };
var lengthSums = words.AggregateBy(
    keySelector: w => w[0],
    seed: 0,
    func: (acc, w) => acc + w.Length);
// 'a' -> 8, 'b' -> 7
```

注意 `Aggregate` 不带 seed 的重载在空序列上会抛 `InvalidOperationException`——它没有「初始值」可以返回。`AggregateBy` 的 `seed` 是必填参数，所以不存在这个问题。

`CountBy` 按键计数，返回的是 `IEnumerable<KeyValuePair<TKey, int>>`（.NET 9）。它内部只维护一张「键 → 计数」的字典，不会像 `GroupBy` 那样为每个键建立分组对象，所以在只需要计数时更省：

```csharp
var words = new[] { "cat", "car", "dog", "duck", "diver" };
var counts = words.CountBy(w => w[0]);
// 'c' -> 2, 'd' -> 3
```

## 集合运算与去重

`Except`、`Intersect`、`Union` 都返回**去重后**的结果——这是最常被忽略的语义。`Except` 返回的是「第一个序列中、不在第二个序列里」的元素，而且结果本身按默认比较器去重：

```csharp
var a = new[] { 1, 1, 2, 3, 4 };
var b = new[] { 2, 4 };
a.Except(b);     // 1, 3（重复的 1 只留一个）
a.Intersect(b);  // 2, 4
a.Union(b);      // 1, 2, 3, 4
```

按「元素的某个键」而不是整个元素比较，用 `By` 变体（.NET 6 加入）：

```csharp
var people = new[] { ("Red", 1), ("Green", 2), ("Blue", 3) };
var excludeIds = new[] { 2 };
people.ExceptBy(excludeIds, p => p.Item2);   // Red, Blue

var products = new[] { (Id: 1, Name: "A"), (Id: 2, Name: "B") };
var activeIds = new[] { 2 };
products.IntersectBy(activeIds, p => p.Id);  // (2, "B")
```

`UnionBy` 在按键去重时**保留第一次出现的元素**：

```csharp
var first = new[] { (Id: 1, Name: "Ana") };
var more = new[] { (Id: 1, Name: "Ana (dup)"), (Id: 2, Name: "Ricardo") };
first.UnionBy(more, p => p.Id); // (1, "Ana"), (2, "Ricardo")
```

## 连接两段序列

`LeftJoin` 和 `RightJoin` 在 .NET 10 才有了语言层面的支持，语义就是你熟悉的 SQL 外连接：

```csharp
var employees = new[] { (Id: 1, Name: "Ana"), (Id: 2, Name: "Ricardo") };
var managers = new[] { (Id: 2, Manager: "Jemma") };

var left = employees.LeftJoin(
    managers, e => e.Id, m => m.Id,
    (e, m) => new { e.Name, Manager = m?.Manager });
// (Ana, null), (Ricardo, Jemma)
```

`FullJoin` 保留两侧的全部元素，没有匹配的一侧用默认值填充（.NET 11 才有）：

```csharp
var managers2 = new[] { (Id: 2, Manager: "Joao"), (Id: 3, Manager: "Jemma") };

var full = employees.FullJoin(
    managers2, e => e.Id, m => m.Id,
    (e, m) => new { e?.Name, m?.Manager });
// (Ana, null), (Ricardo, Joao), (null, Jemma)
```

在 EF Core 里这几个方法有额外的现实约束：LINQ 能翻译，不代表 EF 能翻译。EF Core 10 会把 `LeftJoin`/`RightJoin` 翻译成 SQL 的 `LEFT JOIN`/`RIGHT JOIN`，但用的是它们自己的 LINQ 识别逻辑，超出范围的写法依然会在运行时抛翻译失败。写之前先 `ToQueryString()` 看一眼。

## 位置、切片与索引

`Chunk` 把序列切成固定大小的数组，最后一块可能不满（.NET 6）：

```csharp
Enumerable.Range(1, 7).Chunk(3);
// [1,2,3], [4,5,6], [7]
```

`SkipWhile` 和 `TakeWhile` 都是**按位置**判断，不是过滤：

```csharp
var numbers = new[] { 1, 2, 3, 4, 1 };
numbers.TakeWhile(n => n < 3);  // 1, 2 —— 遇到 3 就停
numbers.SkipWhile(n => n < 3);  // 3, 4, 1 —— 条件后面再成立也不会重新开始跳过
numbers.Where(n => n < 3);      // 1, 2, 1 —— 这才是过滤
```

`TakeLast(n)` 取末尾 n 个元素（.NET Core 2.0），比手算下标安全：

```csharp
new[] { 1, 2, 3, 4, 5 }.TakeLast(2); // 4, 5
```

`Index()` 把元素和它的零基下标配成元组（.NET 9），替代手写的计数器：

```csharp
foreach (var (index, value) in new[] { "a", "b", "c" }.Index())
{
    Console.WriteLine($"{index}: {value}"); // 0: a, 1: b, 2: c
}
```

## 排序与极值

`Order()` 是 `OrderBy(x => x)` 的简写，元素本身必须可比较，也可以传入自己的 `IComparer<T>`；`OrderDescending()` 是它的降序版本（两者都是 .NET 9）：

```csharp
new[] { 3, 1, 2 }.Order();            // 1, 2, 3
new[] { 3, 1, 2 }.OrderDescending();  // 3, 2, 1
```

`MaxBy`/`MinBy` 返回的是**元素**，不是键值（.NET 6）——这正是它们和 `Max`/`Min` 的区别：

```csharp
var people = new[] { (Name: "Ana", Age: 30), (Name: "Ricardo", Age: 25) };
people.MinBy(p => p.Age); // (Ricardo, 25)
```

空序列上的行为分两种：键是值类型时抛 `InvalidOperationException`，键是引用类型时返回 `null`。`MaxBy` 的源码注释写得很明确——「如果 `TKey` 是引用类型，且序列为空或只包含 null，本方法返回 null」。所以 `people.MinBy(p => p.Age)` 在空列表上会抛，`people.MinBy(p => p.Name)` 在空列表上返回 null，两者别写成同一套处理。

## 追加、查找与配对

`Append` 和 `Prepend` 在两端各加一个元素，**不修改原序列**（.NET Core 2.0）：

```csharp
var numbers = new[] { 2, 3, 4 };
var withEnds = numbers.Prepend(1).Append(5); // 1, 2, 3, 4, 5
// numbers 仍然是 2, 3, 4
```

`ToLookup` 建一个「一个键对应多个值」的不可变结构，而且是**立即求值**的：

```csharp
var words = new[] { "apple", "ant", "bear", "bee" };
var lookup = words.ToLookup(w => w[0]);
foreach (var w in lookup['a']) { Console.WriteLine(w); } // apple, ant
// lookup['z'] 是空序列，不是 null，也不会抛
```

这是它和 `GroupBy` 最容易混淆的地方：`GroupBy` 延迟执行、每次枚举都可能重新分组，`ToLookup` 在调用的那一刻就把数据装好了，之后查多少次都不会再碰源序列。数据量小、要反复按键查的时候用 `ToLookup`；只是遍历一次就别多花这份内存。

`Zip` 按位置把两个（或三个，.NET 6）序列配对，**以最短的为准**，多出来的元素直接丢掉：

```csharp
var names = new[] { "Ana", "Ricardo", "Third" };
var ages = new[] { 30, 25 };
names.Zip(ages, (n, a) => $"{n} is {a}");
// "Ana is 30", "Ricardo is 25" —— "Third" 被静默丢弃
```

## 易错点速查

| 你想做的事           | 方法                                  | 边界                                                    |
| -------------------- | ------------------------------------- | ------------------------------------------------------- |
| 整体压成一个值       | `Aggregate`                           | 不带 seed 的重载在空序列上抛异常                        |
| 分组求和             | `AggregateBy`（.NET 9）               | `seed` 必填                                             |
| 分组计数             | `CountBy`（.NET 9）                   | 不分配分组对象，比 `GroupBy` 省                         |
| 取差集 / 交集 / 并集 | `Except` / `Intersect` / `Union`      | 结果**去重**                                            |
| 按键取差集 / 交集    | `ExceptBy` / `IntersectBy`（.NET 6）  | 按键比较，元素本身不变                                  |
| 按键合并去重         | `UnionBy`（.NET 6）                   | 保留第一次出现的元素                                    |
| 外连接               | `LeftJoin` / `RightJoin`（.NET 10）   | EF Core 能翻译的写法有限，先看 `ToQueryString()`        |
| 全外连接             | `FullJoin`（.NET 11）                 | .NET 10 上不存在，编译不过                              |
| 分块                 | `Chunk`（.NET 6）                     | 最后一块不满                                            |
| 从开头取 / 跳过      | `TakeWhile` / `SkipWhile`             | 按位置判断，不是过滤                                    |
| 取末尾 n 个          | `TakeLast`                            | 只需一次枚举，比手算下标安全                            |
| 带下标遍历           | `Index`（.NET 9）                     | 返回元组，元素名是 `Index` 与 `Item`                    |
| 按自身排序           | `Order` / `OrderDescending`（.NET 9） | 元素必须实现 `IComparable`；可传 `IComparer<T>`         |
| 取最大 / 最小的元素  | `MaxBy` / `MinBy`（.NET 6）           | 返回元素而非键；空序列时值类型抛异常、引用类型返回 null |
| 两端追加             | `Append` / `Prepend`                  | 返回新序列，不改原序列                                  |
| 一键多值查找         | `ToLookup`                            | 立即求值；缺失的键返回空序列而不是 null                 |
| 按位置配对           | `Zip`                                 | 以最短序列为准，多余元素被丢弃                          |

还有一条贯穿全表的：除了 `ToLookup`、`CountBy`、`AggregateBy` 这类明确聚合的方法，上面大多数方法都是**延迟执行**的。写成 `var q = source.Where(...)` 不会做任何事，直到你枚举它——这也意味着如果 `source` 是会变化的集合，`q` 的结果取决于你什么时候枚举。

写代码时真正的浪费，往往不是选错了方法，而是不知道它已经存在。Aide Hub 会继续整理这类「先查再写」的 .NET 与 C# 清单，包括 API 版本边界和踩坑记录。如果你有哪个 LINQ 方法是在线上出过事故之后才记住的，欢迎发来补充。

## 参考

- [Less Known LINQ Methods](https://developmentwithadot.blogspot.com/2026/09/less-known-linq-methods.html)（原文，Ricardo Peres）
- [Enumerable 类 API](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable)
- [Enumerable.FullJoin](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable.fulljoin)
- [Enumerable.AggregateBy](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable.aggregateby)
- [Enumerable.CountBy](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable.countby)
- [Enumerable.Index](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable.index)
- [Enumerable.MaxBy](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable.maxby)
- [dotnet/runtime 源码](https://github.com/dotnet/runtime/tree/main/src/libraries/System.Linq/src/System/Linq)
