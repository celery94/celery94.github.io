---
pubDatetime: 2026-10-27T08:52:00+08:00
title: "C# List 与 HashSet：序列与成员资格"
description: "同一个产品编号出现两次，该保留还是合并？用 .NET 10 的实跑输出拆开 List 与 HashSet：位置、比较器、哈希身份和保序去重的差别，最后给一份能照着改的选型判断。"
tags: ["C#", ".NET", "Collections", "List", "HashSet"]
slug: "csharp-list-vs-hashset-sequence-vs-membership"
ogImage: "../../assets/1118/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/26/list-and-hashset-in-c-ordering-membership-and-equality"
---

一个导入采购行的接口把同一批数据交给两段代码。审计页要显示每一行，同一个产品编号出现两次就得显示两条；校验逻辑只想知道这个编号以前有没有出现过。有人为了省事，把展示用的 `List<string>` 换成 `HashSet<string>`，编译通过，测试全绿，上线后报表少了几行——重复的采购行被当成冗余消掉了。

容器类型在这里就成了一句业务判断：一次出现算一次事件，还是只算一个成员。`List<T>` 保存序列，位置和每一次出现都在里面；`HashSet<T>` 保存成员资格，由比较器决定谁和谁是同一个成员，顺序不写进契约。两者回答的问题不同，所以换容器等于改数据含义，和性能档位无关。下面每条输出都来自在 .NET 10（SDK 10.0.402）上实际跑过的代码，原文的示例则是文档中给出的写法、没有执行记录。跑一遍的价值在于把「文档承诺」和「这一次观察到的结果」分开，这个区分在真实项目里最容易踩。

## `List<T>` 保住的是位置和每一次出现

Microsoft 对 `List<T>` 的说明是「可按整数索引访问的强类型列表」：索引从 0 开始，允许重复元素，也不保证有序（[List&lt;T&gt; 文档](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.list-1?view=net-10.0)）。三点合起来才是完整承诺——它保存当前这个序列长什么样，仅此而已。

```csharp
var submissions = new List<string> { "P-100", "P-200", "P-100" };
Console.WriteLine($"Occurrences: {submissions.Count}");
Console.WriteLine($"Second submission: {submissions[1]}");

submissions.Insert(0, "P-050");

Console.WriteLine($"New second submission: {submissions[1]}");
Console.WriteLine(string.Join(", ", submissions));
```

.NET 10 上实际输出：

```text
Occurrences: 3
Second submission: P-200
New second submission: P-100
P-050, P-100, P-200, P-100
```

插入一行 `P-050` 之后，原来的第二个元素 `P-200` 变成第三个，「第二个」现在是 `P-100`。如果另一张表存了「产品在列表第 1 位」这个信息，插入之后它指向的就是另一个产品。下标是位置，位置会变，产品标识不会。

需要展示顺序时，`List<T>` 必须显式排序一次，它不会自己排。`Sort` 用的是内省排序，文档注明实现为不稳定排序：两个键相等的元素，前后顺序不保证保留。要稳定顺序就换 LINQ 的 `OrderBy`，它明确承诺稳定排序。另外 `List<T>` 文档里有一句很容易被跳过的话——这个类同时使用相等比较器和排序比较器，`Contains`、`IndexOf`、`Remove` 走前者，`Sort`、`BinarySearch` 走后者。同一个类型里，判等和排序走的是两套独立的规则，改一个不必然影响另一个。

## 成员资格由比较器决定

`HashSet<T>` 的文档定义很直白：不含重复元素，元素没有特定顺序。它内部按哈希值定位，比较器决定两个值算不算同一个成员。

```csharp
var approvedCodes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

Console.WriteLine($"Add P-100: {approvedCodes.Add("P-100")}");
Console.WriteLine($"Add p-100: {approvedCodes.Add("p-100")}");
Console.WriteLine($"Add P-200: {approvedCodes.Add("P-200")}");

Console.WriteLine($"Members: {approvedCodes.Count}");
Console.WriteLine($"Contains P-100: {approvedCodes.Contains("P-100")}");
Console.WriteLine($"Contains P-300: {approvedCodes.Contains("P-300")}");
```

```text
Add P-100: True
Add p-100: False
Add P-200: True
Members: 2
Contains P-100: True
Contains P-300: False
```

`Add` 直接返回这次是否新增，比先 `Contains` 再 `Add` 少一次查找，也避开了两次调用之间被别人插进同一个值的窗口。第二个 `p-100` 没有成为新成员，是因为集合用了 `StringComparer.OrdinalIgnoreCase`。集合并没有把存进去的字符串改写成统一大小写，它只是在判等时忽略大小写。这层差别很要命：下游接口要大写编码时，得单独做一次规范化，别指望比较器顺手修好。

比较器属于领域规则，不属于代码风格。机器标识可以接受大小写不敏感，访问令牌不行。一个项目里图省事全都用同一个比较器，等于悄悄放宽了「相等」的定义。

默认比较器同样在替你做决定。`List<T>.Contains` 没有接受比较器的重载，它固定用默认相等比较器；要换规则，得用 LINQ 的 `Contains(value, comparer)` 或者自己写判断。没有重写相等语义的引用类型只认引用，比如 `byte[]`：

```csharp
var first = new byte[] { 1, 2, 3 };
var second = new byte[] { 1, 2, 3 };
var listOfBytes = new List<byte[]> { first };
var setOfBytes = new HashSet<byte[]> { first };

Console.WriteLine($"List contains equal content: {listOfBytes.Contains(second)}");
Console.WriteLine($"Set adds equal content: {setOfBytes.Add(second)}");
Console.WriteLine($"Set count: {setOfBytes.Count}");
```

```text
List contains equal content: False
Set adds equal content: True
Set count: 2
```

两个内容完全相同的数组算两个成员：`List<T>.Contains` 返回 `False`，`HashSet<T>.Add` 还当它是新的。看起来像 bug，其实比较器从头到尾没看内容。

## 相等性和顺序是两套策略

把这两件事混在一起的代价，在展示逻辑里最常见。用户名按字母序显示，唯一性却由不可变的账号 ID 决定。如果代码拿用户名比较来决定两个对象是不是同一个人，改一次显示名就可能合并或拆分账号。

`List<T>` 那句「同时使用两个比较器」还有一层含义：两个比较器可以完全不同。相等比较器回答「是不是同一个」，排序比较器回答「谁排前面」。对集合来说，连排序契约都没有。一次运行里 `HashSet<T>` 恰好按插入顺序打印，只说明这一次的哈希布局是这样；换元素、换数量、换运行时都可能变。所以顺序要从显式的有序结构里拿，别从集合枚举里顺出来。

## 存入哈希集合的标识必须稳定

哈希集合先用哈希值找候选桶，再用比较器确认相等。对象存进去以后，如果参与哈希的字段变了，后续查找会按新哈希去另一个桶里找，原来那条记录还留在旧位置。[Dictionary&lt;TKey,TValue&gt; 文档](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.dictionary-2?view=net-10.0)把这条要求写得很明确：对象作为键期间，不能改变任何影响哈希值的东西。HashSet 基于同一个模型，要求相同。

用 record 这种值语义类型做标识，是最省事的写法：

```csharp
var selectedProducts = new HashSet<ProductId>
{
    new ProductId("catalog", 100),
    new ProductId("catalog", 200)
};
var sameProduct = new ProductId("catalog", 100);

Console.WriteLine($"Contains same product: {selectedProducts.Contains(sameProduct)}");

var labels = new Dictionary<ProductId, string>
{
    [sameProduct] = "Updated display name"
};

Console.WriteLine(labels[sameProduct]);

public sealed record ProductId(string Catalog, int Number);
```

```text
Contains same product: True
Updated display name
```

`ProductId` 是 record，相等由 `Catalog` 和 `Number` 决定，内容相同就是同一个成员。显示名放在字典的值里，改名不影响身份——名字可以变，标识不能。

反过来，把一个参与哈希的字段可变的对象放进去，会得到这个结果：

```csharp
var mutable = new MutableCode { Value = "P-100" };
var members = new HashSet<MutableCode> { mutable };
Console.WriteLine($"Before: count={members.Count}, contains={members.Contains(mutable)}");

mutable.Value = "P-200";
Console.WriteLine($"After: count={members.Count}, contains={members.Contains(mutable)}");

public sealed class MutableCode
{
    public string Value { get; set; } = "";

    public override int GetHashCode() => StringComparer.Ordinal.GetHashCode(Value);

    public override bool Equals(object? obj) =>
        obj is MutableCode other && StringComparer.Ordinal.Equals(Value, other.Value);
}
```

```text
Before: count=1, contains=True
After: count=1, contains=False
```

计数还是 1，用自己的引用去查却返回 `False`。对象还在集合里，但已经不在能查到的位置上，`Remove` 同样找不到它。要避免这种情况，不必把整个对象改成不可变，只要保证参与身份的那几个字段在存储期间不变。

## 保序去重需要两份职责

有些场景两个都要：去掉重复，同时保留第一次出现的顺序。集合单凭自己不承诺顺序，列表单凭自己不保证唯一，于是两份结构各管一件事。

```csharp
var source = new[] { "P-200", "P-100", "p-200", "P-300", "P-100" };
var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
var firstOccurrences = new List<string>();

foreach (var code in source)
{
    if (seen.Add(code))
    {
        firstOccurrences.Add(code);
    }
}

Console.WriteLine(string.Join(", ", firstOccurrences));
```

```text
P-200, P-100, P-300
```

输出顺序来自 `source` 的遍历顺序和 `firstOccurrences` 的追加顺序，不依赖枚举 `seen`，这条性质可以放心依赖。保留的也是第一次出现的拼写 `P-200`。如果业务需要统一成大写，那是另一次转换，不要合并进来——判等规则和显示格式各自独立。

代价也得算清楚。两份结构多一份内存，多一层必须同步的状态。这里是方法内的临时变量，同步问题不存在；一旦变成跨方法共享的字段，每次增删都要同时维护两边，还得指定谁负责。

## O(1) 不等于更快

`HashSet<T>.Contains` 的[文档](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.hashset-1.contains?view=net-10.0)写的是 O(1)。这是算法层面的刻画，不能读成每次查询耗时相同：哈希计算、比较器的比较次数、碰撞处理都要花时间。一个昂贵的比较器会让看起来很轻的查询变重。

`List<T>` 的成员查询是线性扫描，但它不总是错的。本来就持有短序列、只问一次「在不在」时，再建一个集合要付构建成本和内存，未必划算。反过来，对一个大集合反复查成员资格，集合的价值才出来。哪边更合适取决于数据规模、操作组合和比较器成本，这些参数只能在自己的负载上量。

## 只读接口挡不住底层改动

`List<T>` 和 `HashSet<T>` 都是可变集合。通过 `IEnumerable<T>` 或 `IReadOnlyList<T>` 返回，限制的只是调用方在这个接口上的操作，底层对象照样能被别人改：

```csharp
var live = new List<string> { "P-100" };
var view = (IReadOnlyList<string>)live;

Console.WriteLine($"View count: {view.Count}");
live.Add("P-200");
Console.WriteLine($"View count after Add: {view.Count}");
```

```text
View count: 1
View count after Add: 2
```

视图的 `Count` 跟着底层列表涨了。同样，集合的拷贝也只是外层拷贝，元素还是同一批引用。

## 换容器等于改语义

回到开头那批采购行。同样的原始数据，两行同一编号，可能是两次购买、两条待合并的数量，也可能是一次重复传输。三种解释对应三种选择：保留每次出现就用列表；只关心编号是否出现过就用集合；要把数量累加到编号上，就需要带值的键模型，那是字典的地盘。

换容器的时间点也很关键。列表把「这两行是什么关系」留给后面的代码解释；集合在插入那一刻就把重复判掉了，出现次数这个信息直接消失。等到报表对不上再回头找，原始数据已经不在内存里。

比较器的变更同样是语义变更。把集合从区分大小写改成不区分，容器类型一个字没改，成员数却可能从 4 变成 3。同一个 `source` 交给默认比较器会输出 `P-200, P-100, p-200, P-300`，四条全保留；换成 `StringComparer.OrdinalIgnoreCase`，就是前面那个三条的版本。这类改动对调用方是可见的，应当当成破坏性变更处理，而不是一次内部优化。

## 先回答一次出现代表什么

改集合类型之前，先看这段代码有没有读下标、有没有依赖到达顺序。有，就留在序列上。只做存在性判断时，换集合，并把比较器写成显式的。既要唯一又要顺序，就用集合判重、列表记首次出现，并接受两份状态的维护成本。改完再看一眼有没有依赖枚举顺序，以及参与哈希的字段会不会在存储期间变化。

比较器最容易被漏掉：它把业务上「算同一个东西」的规则写进了容器，而这条规则通常没有测试覆盖。先给比较器补一个用例，里面放一次重复和一个近似值（大小写不同、空白不同、引用不同但内容相同），再动容器，会安全得多。

## 参考

- [List and HashSet in C#: Ordering, Membership, and Equality（原文，Nick Cosentino / Dev Leader）](https://www.devleader.ca/2026/10/26/list-and-hashset-in-c-ordering-membership-and-equality)
- [List&lt;T&gt; 类（按索引访问、允许重复、不保证有序）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.list-1?view=net-10.0)
- [HashSet&lt;T&gt; 类（无重复元素、元素无特定顺序）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.hashset-1?view=net-10.0)
- [HashSet&lt;T&gt;.Contains 方法（描述为 O(1) 操作）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.hashset-1.contains?view=net-10.0)
- [List&lt;T&gt;.Sort 方法（实现为不稳定排序）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.list-1.sort?view=net-10.0)
- [Dictionary&lt;TKey,TValue&gt; 类（键的哈希值必须稳定）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.dictionary-2?view=net-10.0)
- [Enumerable.OrderBy 方法（稳定排序）](https://learn.microsoft.com/en-us/dotnet/api/system.linq.enumerable.orderby?view=net-10.0)
