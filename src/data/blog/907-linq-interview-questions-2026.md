---
pubDatetime: 2026-06-29T07:18:03+08:00
title: "30 道 LINQ 面试题：2026 年真实会被问到的那些"
description: "覆盖 LINQ 基础、延迟执行、IEnumerable vs IQueryable、表达式树、.NET 9/10 新运算符和 EF Core 实战场景的 30 道面试题。每道题都包含好的回答、会挂的回答和典型追问，帮你理解 LINQ 的底层机制而不是只会链式调用。"
tags: ["CSharp", ".NET", "LINQ", "Interview", "EF Core"]
slug: "linq-interview-questions-2026"
ogImage: "../../assets/907/01-cover.png"
source: "https://codewithmukesh.com/blog/linq-interview-questions/"
---

2026 年的 LINQ 面试已经很少有"Select 是干什么的"这种题了。现在让你挂掉的是场景题：你的查询在你只想跑一次的时候跑了两次数据库，`.Where()` 报"could not be translated"，或者你在循环里拼了一个 filter 结果返回了错的行。这些东西能看出来你是不是真的理解 LINQ 编译成了什么，还是只在链式调用直到结果看起来对。

这篇文章整理了 **30 道 LINQ 面试题**，按面试轮次的实际流程分成 6 个类别。每题都包含：一个真实场景、怎么回答算过关、什么回答会直接挂、以及面试官可能接着追问什么。所有内容基于 **.NET 10 和 C# 14**，涵盖 .NET 9 新增的 `CountBy`、`AggregateBy`、`Index` 和 .NET 10 的原生 `LeftJoin`/`RightJoin`。

## 好的 LINQ 面试回答长什么样

一个靠谱的 LINQ 回答会做两件事：**解释查询什么时候执行、在哪里执行**（内存还是数据库），并且**说出取舍**。LINQ 表面看起来很简单，面试官用它来测试你看不看得懂底下的东西——延迟执行、表达式树、`IEnumerable` 和 `IQueryable` 的分岔。

## 一、LINQ 基础

这部分出现在筛选轮，看起来简单，但好的回答要展示你理解的是机制而不只是语法。

### Q1. 什么是 LINQ，它解决了什么问题？

LINQ（Language Integrated Query）让你用同一套运算符（`Where`、`Select`、`GroupBy`、`OrderBy`）在 C# 里查询集合、数据库、XML 等各种数据源。以前你得为内存数据写 `foreach`、为数据库写原生 SQL 字符串、为 XML 写 XPath——三套不同的思维模型。LINQ 给了你一套声明式的语法，编译期类型检查和 IntelliSense 贯穿始终。

关键是：**LINQ 是声明式的**——你描述要什么，而不是怎么循环和累加，由 provider 决定怎么执行。

**会挂的回答**："LINQ 就是在 C# 里写 SQL。"——那只是 LINQ to Entities；LINQ 可以对任何序列工作，大多数根本不碰数据库。

### Q2. 查询语法和方法语法有本质区别吗？

没有，它们编译成一样的东西。查询语法（`from x in source where ... select ...`）是语法糖，C# 编译器把它翻译成方法调用（`source.Where(...).Select(...)`）。功能完全等价，可以混用。

大部分时候用方法语法更自然，因为它能链式调用并且暴露了没有查询关键字的运算符（`Count`、`Any`、`First`、`Skip`/`Take`）。当查询有多个 `join` 或 `let` 子句、方法语法读起来费劲时，切回查询语法。

**会挂的回答**："查询语法更快"或"方法语法运行时更强"——它们生成同样的编译代码，差异只在可读性。

### Q3. 主要的 LINQ Provider 有哪些？

- **LINQ to Objects**：对内存中的 `IEnumerable<T>` 工作，运算符以编译后的 C# 委托执行
- **LINQ to Entities (EF Core)**：把查询翻译成 SQL 在数据库里运行
- **LINQ to XML**：查询 `XDocument`/`XElement` 树
- **PLINQ**：并行 LINQ，通过 `.AsParallel()` 把内存中的工作分散到多线程

关键区分：LINQ to Objects 在内存里执行委托，LINQ to Entities 构建表达式树然后由 provider 翻译成 SQL。

**会挂的回答**："它们都一样，LINQ 就是跑查出来的。"——内存 provider 和数据库 provider 的执行模型完全不同，这个差异是后面 N 道题存在的原因。

### Q4. 扩展方法和 Lambda 怎么让 LINQ 工作的？

LINQ 运算符不是 C# 内置的——它们是定义在 `IEnumerable<T>`（`System.Linq.Enumerable`）和 `IQueryable<T>`（`System.Linq.Queryable`）上的**扩展方法**。这就是为什么 `using System.Linq;` 之后它们才出现在列表上。每个运算符接收一个 lambda 描述每个元素的逻辑，比如 `p => p.Price > 100`。

面试官会追问的是这个 lambda 变成了什么。对 LINQ to Objects，lambda 编译成 `Func<>` 委托直接执行。对 `IQueryable`，同样的 lambda 编译成 `Expression<Func<>>`——一个数据结构，provider 会检查和翻译。相同的语法，运行时行为完全不同。

**会挂的回答**："Lambda 就是更短的匿名方法。"——对委托来说没错，但漏掉了在 `IQueryable` 上 lambda 变成表达式树而非可执行代码。

### Q5. Select 和 SelectMany 有什么区别？

`Select` 把每个元素投影成一个结果——一对一。`SelectMany` 把每个元素投影成一个**序列**，然后把这些序列全部展平——一对多展开。

```csharp
customers.Select(c => c.Orders);       // IEnumerable<List<Order>> 嵌套
customers.SelectMany(c => c.Orders);   // IEnumerable<Order> 展平
```

在查询语法里，第二个 `from` 子句底层就是 `SelectMany`。

**会挂的回答**："它们基本可以互用。"——把 `SelectMany` 的地方用了 `Select`，拿到的是一个 `IEnumerable<List<T>>` 再加一个让人困惑的二层循环。

## 二、执行模型

这是 LINQ 的核心，是区分调试过查询的人和只写过查询的人的分水岭。

### Q6. LINQ 查询什么时候真正执行？延迟是怎么实现的？

大多数 LINQ 运算符使用**延迟执行**：用 `Where`、`Select`、`OrderBy` 构建查询时不运行任何东西，只是组合了一个工作描述。查询只有在被枚举时才执行——调用 `ToList`、`ToArray`、`Count`、`First` 或用 `foreach` 遍历。

对 LINQ to Objects，运算符是用了 `yield return` 的**迭代器方法**——调用 `Where` 只是返回一个迭代器对象，谓词在你逐个拉元素时才惰性运行。对 `IQueryable`，延迟方式不同：运算符构建表达式树，数据库在枚举之前不会收到任何东西。

**会挂的回答**："查询在我写下 `Where` 的时候就跑了。"——那你怎么解释一个你"已经跑了"的查询在后面的 `foreach` 里突然又打了一次数据库。

### Q7. 哪些运算符会强制执行，哪些保持惰性？

经验法则：返回另一个序列的运算符是**惰性的**（延迟的），返回单个值或物化集合的运算符是**即时的**。

- **延迟**（返回 `IEnumerable`/`IQueryable`）：`Where`、`Select`、`SelectMany`、`OrderBy`、`Take`、`Skip`、`Distinct`、`GroupBy`、`Cast`
- **即时**（返回单个值或新集合）：`ToList`、`ToArray`、`ToDictionary`、`Count`、`Sum`、`First`/`FirstOrDefault`、`Single`、`Any`、`All`、`Max`

心智测试：如果返回类型还是个序列，就还没执行。一旦你要一个值或一个具体集合，整条链就跑起来。

**会挂的回答**："`OrderBy` 会立即执行，因为它要排序。"——它仍然是延迟的，排序发生在枚举时而不是调用 `OrderBy` 时。

### Q8. ToList、ToArray 和 AsEnumerable 有什么区别？

`ToList()` 和 `ToArray()` 都**立即执行查询**并把结果复制到内存——一个 `List<T>` 或 `T[]`。默认用 `ToList()`，灵活（可增删）；结果固定大小或想稍微省内存时用 `ToArray()`。

`AsEnumerable()` 完全不一样——它不执行任何东西，只是把编译期类型从 `IQueryable<T>` 变成 `IEnumerable<T>`，强制后面的每个运算符在内存里作为 LINQ to Objects 执行而不是翻译成 SQL。这是个带刃的工具。

**会挂的回答**："`AsEnumerable` 跟 `ToList` 一样会跑查询。"——它不物化任何东西，只是翻转了数据库/内存求值的边界。

### Q9. 你传了一个 IEnumerable 发现数据库被查了两次，发生了什么？

这是**多重枚举**。因为查询是延迟的，你手里的 `IEnumerable` 是一份**配方**而不是结果。每次有东西枚举它——一个 `foreach`、一个 `.Count()`、然后一个 `.Any()`——整条查询从头重跑一次，每次都打数据库。

```csharp
IEnumerable<Order> orders = db.Orders.Where(o => o.IsOpen); // 还没跑
if (orders.Any())                  // 查询 #1
    Process(orders.Count());       // 查询 #2
foreach (var o in orders) { ... }  // 查询 #3
```

修复：用 `ToList()` 物化一次，然后操作列表。这也是为什么分析器会报 `Possible multiple enumeration of IEnumerable`——不是风格问题，是真实的 bug。

### Q10. 这段循环打印什么，为什么？

经典的延迟执行陷阱——在循环里构建查询并捕获循环变量：

```csharp
var numbers = new[] { 1, 2, 3 };
for (int i = 0; i < 3; i++)
    queries.Add(numbers.Where(n => n > i)); // 'i' 被引用捕获

foreach (var q in queries)
    Console.WriteLine(q.Count()); // 打印 0, 0, 0 —— 不是 2, 1, 0
```

每个 lambda 捕获的是**变量** `i`，而不是它当时的值。因为执行被延迟到 `Count()` 调用，那时 `i` 已经是 3，所以每个查询都在过滤 `n > 3`，全返回 0。修复：把 `i` 拷贝到一个循环局部变量（`int local = i;`）让每个闭包捕获自己的值。注意 C# 5 起 `foreach` 变量是每次迭代独立的，但 `for` 计数器不是——这坑还在。

## 三、IEnumerable vs IQueryable

这个类别测试你是否理解：同样的 LINQ 代码，根据静态类型不同，可以有两种完全不同的运行方式。

### Q11. IEnumerable 和 IQueryable 的本质区别是什么？

`IEnumerable<T>` 代表内存中的序列；它的 LINQ 运算符接收 `Func<>` 委托，在你进程里作为编译后的 C# 执行。`IQueryable<T>` 代表对一个外部数据源的查询；它的运算符接收 `Expression<Func<>>`，构建一棵**表达式树**，由 provider（如 EF Core）翻译——通常是 SQL——然后在**数据库里**运行。

实际后果是过滤在哪里发生：保持查询为 `IQueryable` 直到最后时刻，`Where` 变成 SQL `WHERE`；一旦变成 `IEnumerable`，后面的所有东西都在本地跑。

```csharp
// IQueryable: WHERE IsActive=1 在 SQL 里跑，只返回匹配的行
var good = await db.Products.Where(p => p.IsActive).ToListAsync();

// IEnumerable: 先把所有行拉进内存，再在 C# 里过滤
var bad = db.Products.AsEnumerable().Where(p => p.IsActive).ToList();
```

**会挂的回答**："它们都是你可以遍历的集合。"——这种误解就是全表加载跑到生产环境的原因。

### Q12. 什么是表达式树，EF Core 怎么用它？

表达式树是一个**把代码表示为数据的结构**——一棵描述操作（二元比较、成员访问、常量）的节点树，而非编译好的可执行指令。当你对 `IQueryable` 写 `p => p.Price > 100` 时，编译器不产出委托，而是产出 `Expression<Func<Product, bool>>`——一个 EF Core 可以遍历的对象。

EF Core 的查询 provider 遍历这棵树，认出"成员访问 `Price`，大于，常量 `100`"，然后产出匹配的 SQL `WHERE Price > 100`。因为它是数据，EF Core 可以检查和翻译它；编译后的 `Func<>` 对它来说是一个不透明的黑盒。这就是 `IQueryable` 能变成 SQL 而 `IEnumerable` 不能的全部原因。

### Q13. Func 和 Expression\<Func\> 有什么区别，为什么 EF Core 需要后者？

`Func<Product, bool>` 是编译好的委托——你可以调用但无法检查的可执行代码。`Expression<Func<Product, bool>>` 是同一个 lambda 以表达式树的形式表示——你可以分析但不能直接调用（需要先 `.Compile()`）。

EF Core 的 `IQueryable.Where` 接收 `Expression` 形式，正是因为它需要**读取**逻辑来翻译成 SQL。如果 EF 接收普通的 `Func`，它就没东西可翻译了，只能把所有行拉到内存里再跑委托。这就是为什么在 EF 期望 `Expression` 的地方传 `Func`，会悄悄把你掉到客户端求值。

### Q14. AsEnumerable 和 AsQueryable 的边界翻转在哪里？

`AsEnumerable()` 把 `IQueryable` 向下转为 `IEnumerable`，之后每个运算符都在**内存里**执行。`AsQueryable()` 把 `IEnumerable` 向上转为 `IQueryable`，通常是为了满足期望 `IQueryable` 的 API 签名或动态构建查询；在内存数据上它仍然在内存里执行。

使用 `AsEnumerable()` 要有目的：当查询的一部分无法翻译成 SQL 时，让数据库先做重过滤，然后 `AsEnumerable()` 在已经缩小的集合上本地完成无法翻译的部分。永远不要把 `AsEnumerable()` 放在最前面来消除翻译错误。

### Q15. .Where() 报"Could Not Be Translated"，怎么回事？

EF Core 想把你的 LINQ 翻译成 SQL，但碰到了没有 SQL 等价物的东西——通常是谓词里的自定义 C# 方法或 .NET API 调用。从 EF Core 3.0 起，框架拒绝静默地把它转到客户端执行（以前会导致不可见的全表扫描）。

修复按顺序：重写谓词让 EF 能翻译原始列；在集合已经很小之后用显式 `AsEnumerable()` 把无法翻译的部分后移；或者把逻辑推进计算列或原始 SQL。**绝对不要**在最前面加 `AsEnumerable()` 让错误消失——那是把整张表装进内存，错误的取舍。

## 四、运算符细节

### Q16. First、FirstOrDefault、Single 和 SingleOrDefault 有什么区别？

它们在两个维度上不同：期望多少个匹配，没有匹配时做什么。

- **First**——返回第一个匹配；序列为空抛异常
- **FirstOrDefault**——返回第一个匹配，空则返回 default；不抛
- **Single**——断言恰好一个匹配；零个或多个都抛异常
- **SingleOrDefault**——返回唯一匹配或 default，但多于一个时仍然抛

"可能有多个取第一个"时用 `First`/`FirstOrDefault`；"多于一个就是 bug"时——比如按唯一键查找——用 `Single`/`SingleOrDefault`，它把这个假设显式化并大声失败。

### Q17. 怎么用 GroupBy 做分组，包括复合键？

`GroupBy` 按一个选择器把序列分区成组。每个组是 `IGrouping<TKey, TElement>`——有 `Key` 并且自身可枚举。

```csharp
// 单键
var byCategory = products
    .GroupBy(p => p.Category)
    .Select(g => new { g.Key, Total = g.Sum(p => p.Price) });

// 复合键：匿名类型有内建的值相等
var byCatYear = products
    .GroupBy(p => new { p.Category, Year = p.CreatedAt.Year })
    .Select(g => new { g.Key.Category, g.Key.Year, Count = g.Count() });
```

匿名类型作为键天然支持复合分组，因为它有值相等判断。注意在 EF Core 中，`GroupBy` 后跟聚合能翻译成 SQL `GROUP BY`，但 `GroupBy` 返回实际元素组的通常不能翻译，会回退到客户端求值。

### Q18. LINQ 怎么写内连接和左连接？

内连接只保留两边都匹配的行：

```csharp
var matched =
    from o in orders
    join c in customers on o.CustomerId equals c.Id
    select new { o.Id, c.Name };
```

左连接——保留所有订单即使没有匹配的客户——传统上需要 `GroupJoin` + `SelectMany` + `DefaultIfEmpty`：

```csharp
var leftJoined =
    from o in orders
    join c in customers on o.CustomerId equals c.Id into grp
    from c in grp.DefaultIfEmpty()
    select new { o.Id, CustomerName = c == null ? "(none)" : c.Name };
```

`DefaultIfEmpty()` 是把内连接变成左连接的关键——右边没有匹配时提供一个 null。在 EF Core 中，如果有导航属性，通常直接投影导航属性让 EF 生成 join。

### Q19. .NET 10 的 Join 有什么变化？

.NET 10 给 LINQ 添加了原生 `LeftJoin` 和 `RightJoin` 运算符。它们用一次可读的调用替代了 `GroupJoin` + `SelectMany` + `DefaultIfEmpty` 的别扭组合：

```csharp
var leftJoined = orders.LeftJoin(
    customers,
    o => o.CustomerId,
    c => c.Id,
    (o, c) => new { o.Id, CustomerName = c == null ? "(none)" : c.Name });
```

结果选择器里内部元素是可空的（`Func<TOuter, TInner?, TResult>`），恰好对应"没有匹配"的情况。EF Core 10 把这些运算符翻译成 SQL `LEFT JOIN`/`RIGHT JOIN`。注意它们是运算符，没有对应的查询语法关键字。

### Q20. Aggregate 怎么用？

`Aggregate` 通过把一个累加器穿进每个元素，把序列折叠成一个值：

```csharp
var totalChars = words.Aggregate(0, (sum, w) => sum + w.Length);
var csv = names.Aggregate((a, b) => $"{a}, {b}");
```

它是通用的 reduce——`Sum`、`Count`、`Min`、`Max` 都是它的特化版本。只在没有内建运算符能满足你需要的 fold 时才用显式 `Aggregate`，因为命名运算符读起来更清楚。

### Q21. Any vs All，为什么优先用 Any() 而不是 Count() > 0？

`Any()` 至少有一个匹配时返回 true（无谓词则检查是否有任意元素）。`All()` 每个元素都匹配时返回 true——空序列返回 true（虚空真），很多人没想到。

检查存在性用 `Any()` 而非 `Count() > 0`：`Any()` 在第一个命中时就短路；`Count()` 走完整条序列。在 EF Core 里差距更大：`Any()` 翻译成 SQL `EXISTS` 可以提前停，而 `Count() > 0` 发出完整的 `COUNT(*)`。结果一样，工作量大不同。

## 五、现代 .NET 与性能

### Q22. .NET 9 的 CountBy 加了什么？

`CountBy` 一次调用按键计数，返回 `IEnumerable<KeyValuePair<TKey, int>>`。它替代了常见的 `GroupBy(...).Select(g => ... g.Count())` 模式，并且不用为每个组分配中间集合：

```csharp
// .NET 9
var perDept = employees.CountBy(e => e.Department);

// 替代写法 —— GroupBy 先物化每个组再计数
var perDept = employees.GroupBy(e => e.Department)
    .Select(g => new { Dept = g.Key, Count = g.Count() });
```

收益在两方面：可读性好，而且 `GroupBy` 在每个键上都构建子集合，`CountBy` 只维护每个键的运行计数。在大内存序列上这个差距可测量。

### Q23. .NET 9 的 AggregateBy 和 Index 是什么？

**AggregateBy**——按键聚合一次完成，跟 `CountBy` 一样但适用于任何 fold 而不只是计数：

```csharp
var totals = employees.AggregateBy(
    e => e.Department, seed: 0m, (total, e) => total + e.Salary);
```

**Index**——把每个元素和它的位置配对，返回 `IEnumerable<(int Index, T Item)>`，替代了容易用错的 `Select((item, i) => ...)` 重载：

```csharp
foreach (var (i, name) in names.Index())
    Console.WriteLine($"{i}: {name}");
```

### Q24. 查询慢，因为加载完再过滤——bug 在哪？

最常见的 LINQ 性能 bug：**物化太早，然后在内存里过滤**。

```csharp
// BUG: ToList() 把整张表拉到内存，再在 C# 里过滤
var open = db.Orders.ToList().Where(o => o.IsOpen).Take(20);

// FIX: 在 SQL 里过滤和分页，只物化最后 20 行
var open = await db.Orders.Where(o => o.IsOpen).Take(20).ToListAsync();
```

规则：**最后物化**——在所有过滤、投影和分页应用之后，绝不之前。

### Q25. LINQ 什么时候不是对的选择？

LINQ 是可读性的默认选项但不是免费的。链上每个运算符分配一个迭代器，lambda 可能分配闭包，逐元素委托调用也不免费。在真正的热路径上——跑几百万次的紧循环或低分配例程——普通 `for`/`foreach` 循环或 `Span<T>`（LINQ 不直接支持）可以明显更快且分配更少。

规则：先写 LINQ，因为可读。只在 profiler 证明 LINQ 版本真的在拖后腿时，再把具体热路径改写成手动循环。过早去 LINQ 化是用可读性换你测不出来的收益。

## 六、EF Core 与实战

### Q26. 怎么用 Skip 和 Take 分页，规模上去后的坑是什么？

`Skip(n).Take(m)` 是标准的偏移分页：

```csharp
var page = await db.Products
    .OrderBy(p => p.Id)  // 分页前必须排序，否则页面可能重叠或漏行
    .Skip((pageNumber - 1) * pageSize)
    .Take(pageSize)
    .ToListAsync();
```

两件事值得说：第一，分页前必须 `OrderBy`，否则数据库没有定义的行顺序。第二，偏移分页在深层页上会退化：`Skip(100000)` 仍然让数据库数过去十万行。大数据集用键集（游标）分页——`Where(p => p.Id > lastSeenId).Take(pageSize)`，用索引查找而不是计数。

### Q27. 你的端点返回了 50 行，日志显示 51 条查询——这是什么？

N+1 查询问题：一条查询加载了 50 个父行，然后 EF Core 每行再发一条查询加载关联的导航属性——51 次往返拿回一条 join 就能取到的数据。通常来自懒加载，或者遍历了你忘了 `Include` 的导航属性。

修复：用 `Include` 一次加载关联数据，或者更好的做法，用 `Select` 只投影你需要的字段到 DTO，让 EF 发出一条 join 查询且不过度拉取。在开发环境开启 EF Core 查询日志能提前发现——一连串相同的参数化查询就是信号。

### Q28. 什么时候用 AsNoTracking，有什么坑？

`AsNoTracking` 告诉 EF Core 不要为查询返回的实体创建变更追踪快照。只读查询——GET 端点、报表、任何你不需要修改的东西——都应该加，对内存和 CPU 是真实节省。

坑：不加追踪时 EF Core 默认不做身份解析（identity resolution），所以同一条记录如果在结果中出现两次（通过 join），你会拿到两个不同的对象实例而不是同一个共享引用。如果这很关键，用 `AsNoTrackingWithIdentityResolution`。而且你显然不能对没追踪的实体调 `SaveChanges`。

### Q29. 怎么异步跑 LINQ 查询？为什么不能直接 await 一个普通查询？

你 await 的是**物化运算符**，不是查询本身。EF Core 提供执行运算符的异步版本——`ToListAsync`、`FirstOrDefaultAsync`、`SingleOrDefaultAsync`、`CountAsync`、`AnyAsync`——你应该 await 它们。

你不能 `await db.Orders.Where(...)`，因为 `Where` 是延迟的，返回一个 `IQueryable`——还没有任何操作在飞。查询只在执行运算符枚举时才跑，所以这个运算符的异步版本才是返回 `Task` 的那个。注意标准 `System.Linq` 的运算符没有异步变体；异步的是来自 `Microsoft.EntityFrameworkCore` 的那套。

### Q30. 怎么用投影避免过度拉取？

用 `Select` 投影到 DTO 告诉 EF Core 只取你实际需要的列，而不是加载整个实体：

```csharp
var dtos = await db.Orders
    .Select(o => new OrderDto(o.Id, o.Total, o.Customer.Name))
    .ToListAsync();
```

对只读 GET 来说这应该是默认而不是 `Include`，`Include` 会加载你不需要的完整关联实体。投影还绕过了追踪开销和笛卡尔爆炸问题（`Include` 多个集合时会碰到，这时候 `AsSplitQuery()` 是备选方案）。原则：让数据库返回你打算返回的形状，不是你表的形状。

## 面试中最容易挂的 5 个 LINQ 错误

1. **不知道查询什么时候执行。** 解释不了延迟执行，所有关于性能和多重枚举的回答都站不住。
2. **把 IEnumerable 和 IQueryable 当一回事。** 这是 SQL `WHERE` 和全表加载到内存的区别，面试官专门考。
3. **用 AsEnumerable 消掉翻译错误。** 它"修好"异常的方式是把所有东西装进内存——完全反了。
4. **物化之后再过滤。** `ToList().Where(...)` 把整张表拉回来再丢掉大部分。最常见的 LINQ 性能 bug。
5. **停留在两三个版本前。** 不知道 `CountBy`/`Index`（.NET 9）或原生 `LeftJoin`/`RightJoin`（.NET 10）说明你停止了学习。

## 关键要点

- **延迟执行是核心概念。** 查询描述工作，枚举时才运行。这解释了多重枚举、循环变量陷阱和为什么异步用的是 `ToListAsync`。
- **IQueryable 变 SQL，IEnumerable 在内存里跑。** 把查询保持为 `IQueryable` 直到最后时刻，让过滤和分页推到数据库。
- **最后物化。** 所有过滤、投影、分页都应用完再调 `ToList`——绝不提前。
- **知道现代运算符。** `CountBy`、`AggregateBy`、`Index`（.NET 9）和原生 `LeftJoin`/`RightJoin`（.NET 10）是跟上平台的信号。
- **每个强回答都说出一个取舍。** 讲清楚 LINQ 做了什么、在哪里运行、代价是什么。

## 常见问题

**Q: 什么是延迟执行？**
延迟执行意味着构建 LINQ 查询（用 `Where`、`Select` 等）时不会立即运行，它们只是组合了一个"工作描述"。只有当查询被枚举时（比如调用 `ToList()`、`First()` 或用 `foreach` 遍历），整条链才真正执行。对 `IQueryable` 来说这意味着 SQL 只在枚举时才发给数据库。

**Q: 为什么 EF Core 里优先用 Any() 而非 Count() > 0？**
`Any()` 找到第一个匹配就短路返回，翻译成 SQL `EXISTS` 可以在数据库层面提前终止。`Count() > 0` 要走完所有匹配行，翻译成 SQL 是完整的 `COUNT(*)`。结果一样，效率差很多。

**Q: 面试里怎么回答 LINQ 执行位置的问题？**
先说是什么类型：`IEnumerable` 在内存里作为 C# 委托执行，`IQueryable` 被 EF Core 翻译成 SQL 在数据库里执行。然后指出实际影响——保持 `IQueryable` 让过滤下推到数据库，过早转成 `IEnumerable` 会把所有数据拉到客户端再过滤。

## 参考

- [30 LINQ Interview Questions — codewithmukesh](https://codewithmukesh.com/blog/linq-interview-questions/)
- [.NET Interview Questions Hub](https://codewithmukesh.com/blog/dotnet-interview-questions/)
- [30 EF Core Interview Questions](https://codewithmukesh.com/blog/efcore-interview-questions/)
- [45 .NET Web API Interview Questions](https://codewithmukesh.com/blog/dotnet-webapi-interview-questions/)
