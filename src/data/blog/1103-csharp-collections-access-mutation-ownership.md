---
pubDatetime: 2026-10-21T08:00:00+08:00
title: "C# 集合选型：访问语义与所有权边界"
description: "List 不是默认答案：先回答访问、相等性、顺序、可变性和所有权这五个问题，再选集合类型。本文附 .NET 10 的实跑输出，并给出一份可以照着走的接口检查清单。"
tags: ["C#", ".NET", "Collections", "API Design"]
slug: "csharp-collections-access-mutation-ownership"
ogImage: "../../assets/1103/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/20/collections-in-c-access-mutation-and-ownership-explained"
---

一个 `GetPendingAsync()` 方法返回 `IReadOnlyList<Request>`。调用方觉得拿到了只读数据，把它存进字段当作快照。之后别处继续往底层 `List<Request>` 里 `Add`，那个「快照」的 `Count` 也跟着涨了。

类型没有骗人。`IReadOnlyList<T>` 只承诺「不能通过这个接口改结构」，从来没承诺「之后不会再变」。这类 bug 的根源不在方法用错，而在于把集合类型当成了存储偏好，忽略了它同时是一份契约：能对外提供哪些操作、按什么规则判等、顺序有没有保证、哪一层可以变、以及谁拥有这份数据。

Nick Cosentino 在 Dev Leader 的这篇文章正是按这组契约拆解集合的。下面沿这条主线重述，并以文中三个示例为基础，连同两个补充场景在 .NET 10（SDK 10.0.401）上实际跑了一遍。哪些输出是文档承诺、哪些只是这一次观察到的结果，后文会分别标注——这是原文没有展开、但在真实项目里最容易出错的地方。

## 先说清数据要满足什么

选集合之前，先回答应用对这份数据提的问题。同一个 `string` 元素，在不同的容器里含义完全不同：

| 应用要回答的问题 | 合适的形状                | 它不承诺什么               |
| ---------------- | ------------------------- | -------------------------- |
| 第几个元素是什么 | `List<T>` / 数组          | 位置不是稳定的身份         |
| 这个值出现过吗   | `HashSet<T>`              | 不承诺任何顺序             |
| 这个键对应什么值 | `Dictionary<TKey,TValue>` | 枚举顺序未定义             |
| 谁先来的         | `Queue<T>`                | 只描述取出顺序             |
| 谁最后来的       | `Stack<T>`                | 只描述取出顺序             |
| 调用方能遍历什么 | `IEnumerable<T>`          | 不承诺快照，也不承诺不可变 |

这张表的作用是排除错误选项，不是给性能打分。需要保留重复事件的场景，不能因为集合查重方便就把重复丢掉；需要按标识符找值的场景，也不能靠记住列表下标——插入会移动下标。

还有一条容易漏的边界：`List<T>` 保留你添加的顺序和位置，但它不会自动排序。界面要按字母序展示时，排序必须显式做一次；下标不会因为元素内容变了而自己重排。

## 同一份输入，两种模型

三个提交里有两个只有大小写不同。展示要保留全部三条，查重按「标识符不区分大小写」的规则：

```csharp
using System;
using System.Collections.Generic;

var submissions = new List<string> { "REQ-1", "req-1", "REQ-2" };
var knownIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

foreach (var submission in submissions)
{
    var firstAppearance = knownIds.Add(submission);
    Console.WriteLine($"{submission}: first appearance = {firstAppearance}");
}

Console.WriteLine($"Submissions: {submissions.Count}");
Console.WriteLine($"Distinct identifiers: {knownIds.Count}");
Console.WriteLine($"Set order: {string.Join(",", knownIds)}");
```

在 .NET 10 上运行的实际输出：

```text
REQ-1: first appearance = True
req-1: first appearance = False
REQ-2: first appearance = True
Submissions: 3
Distinct identifiers: 2
Set order: REQ-1,REQ-2
```

前三行逐项输出以及后面两个计数都是确定性结果：列表保留三条，集合在它自己的比较器下认为只有两个标识符。两个计数互为补充，不是彼此的修正——一个回答提交了几次，另一个回答出现了多少个标识符。

最后一行是陷阱。`Set order: REQ-1,REQ-2` 看起来像插入顺序，`HashSet<T>` 的文档却写得很明确：集合中的元素**没有特定顺序**。

这次输出与插入顺序一致，原因是当前实现按内部条目数组的顺序遍历，而删除元素会留下空槽、后续添加会复用空槽。这一点做过验证：用一批乱序 ID，只调用 `Add` 时枚举顺序与插入顺序完全一致；删掉中间一项再添加新项，新项就出现在空出来的位置上。所以「看起来有序」是无保证的实现细节，不是语义承诺。把这一行当成展示顺序写进接口约定，测试会通过，线上会偶发错乱。

比较器本身也是领域决定，不是技术默认值。示例用 `OrdinalIgnoreCase`，是因为它把标识符定义成大小写不敏感；同样的规则套到密码、大小写敏感的令牌或任意用户可见文本上就是错的。选集合替代不了「什么算相等」这个业务判断。

## 键访问要求稳定的相等性

字典把一个键映射到一个值。不同的键可以指向相等的值，所以键唯一不蕴含值唯一——两个请求的状态都是 `Pending`，字典完全合法。

```csharp
using System;
using System.Collections.Generic;

var statuses = new Dictionary<string, string>(StringComparer.Ordinal)
{
    ["REQ-1"] = "Pending",
    ["REQ-2"] = "Pending"
};

if (statuses.TryGetValue("REQ-1", out var status))
{
    Console.WriteLine(status);
}
else
{
    Console.WriteLine("No status exists for that request.");
}

statuses["REQ-1"] = "Complete";
Console.WriteLine($"Associations: {statuses.Count}");
```

实际输出：

```text
Pending
Associations: 2
```

`Associations` 仍然是 2，因为索引器赋值是替换已有键的值，不是再插入一条。这个区别很容易在代码评审里被忽略：`dict[key] = value` 与 `dict.Add(key, value)` 的语义不同，后者在键已存在时会抛异常。`TryGetValue` 则把「不存在」变成显式分支，而不是让调用方把缺失当成查到了空值。

真正的坑在键的稳定性。字典文档的原话是：只要一个对象还被当作字典的键使用，它就不能以任何影响哈希值的方式改变。所以一个名字参与哈希计算的可变对象，不适合直接拿来当键——它的名字一改，条目还在哈希表里，但你已经找不到它了。`record` 对值语义的键是个不错的起点，但 `record` 里嵌了可变对象，并不自动让每个参与判等的属性都安全；需要稳定的是整条判等策略。

顺带修正一个常见说法：用键取值接近 O(1) 是平均意义上的描述，不是固定耗时承诺。哈希质量、冲突、扩容以及具体操作都会影响实际表现。

## 可变性有好几层

「改集合」至少包含四种不同动作：添加元素、删除元素、替换某个位置、修改已被引用的对象。它们作用在不同层面。

- `List<string>` 加一个字符串，`Count` 变，结构变了。
- `List<Request>` 改 `request.Status`，`Count` 不变，结构没变，但别人看到的数据变了。

把两者都叫「可变数据」，就丢掉了排错需要的信息。

接口层面同样如此。`IEnumerable<T>` 只暴露遍历，既没有 `Add` 也没有索引器，它不证明实现是不可变的。`IReadOnlyCollection<T>` 多了 `Count`，`IReadOnlyList<T>` 再加索引读取。`IReadOnlyList<T>` 的文档把边界写得很清楚：元素的数量和顺序是只读的，**元素内容不保证只读**。

所以返回值声明为 `IReadOnlyList<T>`，只说明调用方少了一组可用操作，不说明所有权转移，也不说明数据冻结。

## 只读视图不是快照

这是开头那个 bug 的机制，值得单独跑一遍：

```csharp
using System;
using System.Collections.Generic;

var source = new List<string> { "REQ-1", "REQ-2" };
IReadOnlyList<string> liveView = source.AsReadOnly();
IReadOnlyList<string> snapshot = Array.AsReadOnly(source.ToArray());

source.Add("REQ-3");

Console.WriteLine($"Live view count: {liveView.Count}");
Console.WriteLine($"Snapshot count: {snapshot.Count}");
```

实际输出：

```text
Live view count: 3
Snapshot count: 2
```

两个变量的声明类型一模一样，行为完全不同，差别来自背后存储的归属。`AsReadOnly()` 返回的是包装器，`ReadOnlyCollection<T>` 的文档明确写着：只读集合只是加了一层阻止修改的包装，如果底层集合发生变化，只读集合会反映这些变化。`Array.AsReadOnly(source.ToArray())` 先在数组上做了一次复制，所以新加的元素进不来。

复制也不是万能解。复制列表通常只复制引用，元素对象仍然共享：

```csharp
using System;
using System.Collections.Generic;

var live = new List<Request> { new("REQ-1", "Pending") };
var copied = new List<Request>(live);
live[0].Status = "Complete";

Console.WriteLine($"copy[0].Status: {copied[0].Status}  sameRef: {ReferenceEquals(live[0], copied[0])}");

public sealed class Request(string id, string status)
{
    public string Id { get; } = id;
    public string Status { get; set; } = status;
}
```

实际输出 `copy[0].Status: Complete  sameRef: True`。外层结构独立了，元素状态没有独立。想要真正隔离，得让元素本身不可变，或者在复制时把元素投影成与业务对象脱钩的 DTO。

复制还有成本边界。它要把当前所有元素读出来，并为新结构单独分配存储。对一次有界响应合适；对无界数据源或大查询，如果调用方只需要一个答案，复制就是纯浪费。

## 消费顺序不是展示顺序

队列先取出最早剩下的项，栈先取最后加入的项。这是消费顺序，不是展示顺序。

用列表也能模拟待办：按下标取第一个、按下标删除。但那样一来，「先进先出」这条策略藏在所有人对下标的默契里，而不是写在 API 上。`Queue<T>` 的 `Enqueue` 与 `Dequeue`、`Stack<T>` 的 `Push` 与 `Pop`，把策略变成了签名的一部分。

这里也要防止过度解读。队列不是后台处理系统：它没有持久化、确认、重试策略，也没有异步等待契约。栈能表示撤销历史，但不会自动实现撤销——你仍然需要一个反向操作，以及「新操作发生时重做历史怎么办」的规则。集合提供顺序，工作流提供含义。

对于队列和栈的常规消费，`TryDequeue` / `TryPop` 让「空」成为显式结果。返回 `false` 只说明这一次没有取到元素，不说明所有生产者都已结束，也不说明整个流程完成。

## 枚举是具体集合的契约

`foreach` 只是请求数据源逐个给出元素，它不会在循环开始时统一复制一份。于是物化列表、惰性序列和并发字典在「循环期间发生修改」时会表现出不同行为。

在 .NET 10 上跑一个最能说明问题的场景：遍历 `List<T>` 时往同一个列表里添加元素。

```csharp
using System;
using System.Collections.Generic;

var list = new List<int> { 1, 2, 3 };
foreach (var n in list)
{
    list.Add(n);
}
```

实际输出，堆栈行已省略：

```text
Unhandled exception. System.InvalidOperationException: Collection was modified; enumeration operation may not execute.
```

异常类型是 `InvalidOperationException`，这是 `List<T>` 的版本检查在起作用。但不要把这条经验推广成「任何集合的任何修改都会让枚举失效」——这个反向结论同样是错的。枚举行为取决于具体操作、具体集合和具体版本。

并发字典就是现成的反例。它的枚举器文档说明：枚举器可以安全地与字典的读写并发使用，但它**不表示字典在某一时刻的快照**，通过枚举器看到的内容可能包含调用 `GetEnumerator` 之后发生的修改。也就是说，写入期间遍历是被支持的，但你拿不到一份一致的历史版本。

结论落到接口设计上：如果一份报表依赖「成员在本次输出期间保持一致」，那么返回一个 `IEnumerable<T>` 是不够的。快照或同步策略必须由提供方建立，并且要让调用方知道边界在哪。

## 共享集合需要共享规则

普通集合 API 不保证并发修改安全。只读包装也救不了：如果另一个引用仍能写底层集合，包装层照样会反映变化。连复制都需要一个安全的获取策略——复制期间如果有写入，复制出来的内容本身就是不确定的。

锁是一种办法，前提是所有相关读写方都用同一把锁。并发集合是另一种办法，前提是只用它明确支持的操作。两者都不等于「周边业务行为自动变成原子操作」。

举个具体的复合动作：读到某个请求状态，然后据此决定是否追加一条通知。状态可能在读取和通知之间改变。把字典查找换成线程安全的实现，并不会把「查找 + 判断 + 发通知」合成一个不可分割的动作。

真正的设计问题是：哪个条件必须同时成立？哪些动作可以容忍别的线程插进来？这两个问题不回答，选什么集合都是在猜。

## 把一条需求走完整条链

把前面几节收束到一个具体需求上：界面需要按到达顺序展示前 20 条请求（含重复提交），并且响应创建之后，展示的标识符不能再变。

这个需求同时包含三件事：顺序、重复、成员稳定。

- 按位置和重复来描述，`List<T>` 是自然的形状。
- 成员稳定需要一次外层复制，`AsReadOnly()` 提供不了。
- 如果 `Request` 元素本身带有可变的状态历史，还要再做一个决定：界面是想通过共享对象看到实时状态，还是想看到响应生成那一刻捕获的值？浅复制支持前者，但无法默默承诺后者。

当响应是从共享状态组装出来的，复制本身也需要协调——安全复制发生在获取阶段，而不是拿到只读类型之后。于是就得到四个互相牵连的决定：**集合选择、返回接口、元素表示、同步策略**。

把契约写显式还有一个维护上的好处：后续开发者换内部实现时，只要可见行为不变就不会破坏调用方。反过来，如果调用方偷偷依赖了当前的枚举顺序，或者把返回值强转回 `List<T>` 去改，那么替换实现就会破坏 API 从未承诺过的东西。

具体做法很简单。先用一句话描述数据，例如「这些是按到达顺序捕获的标识符，保留重复」；然后逐项检查代码是否真的建立了这句话的每个部分。

## 接口检查清单

选型定下来之后，再拿这五条检查代码。它们查的是实际行为，不是文档措辞：

1. 除了方法签名，是否还有另一条能写到底层存储的路径？有，返回值就只是视图；确认没有写路径，才接近快照。
2. 返回类型给调用方的操作，比它真正需要的多吗？`List<T>` 会连索引器和 `Add` 一起交出去。
3. 元素是共享引用还是捕获值？元素可变时，谁可能在调用方拿到结果之后改它？
4. 复制或加锁写在哪一行？它覆盖了所有写入者，还是只保护了当前这条读路径？
5. 有没有一个会失败的测试：一边写、一边读，断言应当出现的现象？

五条里有任何一条答不上来，说明契约还没定，而不是集合选错了。

## 常见问题

**`List<T>` 是不是默认该用的集合？** 不是。它适合「按位置访问、允许重复」的数据。一组只需要先进先出消费的待办，用 `List<T>` 就得靠下标约定，而 `Queue<T>` 把这条策略直接写进签名。

**`HashSet<T>` 会保留插入顺序吗？** 不要依赖它。文档的模型就是没有特定顺序。如果输出顺序可观察，就需要单独的序列或显式排序，而不是指望集合。

**.NET 10 里 `Dictionary<TKey,TValue>` 的枚举顺序有保证吗？** 没有，文档描述为未定义。某次运行看到的排列不是公开契约。

**`IReadOnlyList<T>` 会让元素不可变吗？** 不会。它限制的是声明出来的集合操作，不是被引用对象的可变性。只读访问、结构独立、深层不可变是三件不同的事。

**复制一份集合就线程安全了吗？** 不是。复制必须先在安全的前提下取得，可变元素还可能被原集合和副本共享。

**`foreach` 会创建快照吗？** 不会普遍如此。它沿用数据源的枚举行为，具体规则看那个集合的文档。

## 收尾

集合类型的名字，最好能直接解释应用行为：序列、成员、关联、先进先出、后进先出。返回接口解释调用方能做哪些操作，所有权与同步策略解释什么会变、谁能改。

四件事对齐之后，就不存在「哪个集合最好」这个问题了。合适的标准只有一条：文档承诺的行为正好是应用需要的含义，所有权边界也能让下一个读代码的人看懂。

如果你正在整理 .NET 项目的接口约定，欢迎关注 Aide Hub。我们会继续分享语言特性背后的契约、可执行的验证方式，以及真实工程里的取舍。

## 参考

- [Collections in C#: Access, Mutation, and Ownership Explained（原文，Nick Cosentino / Dev Leader）](https://www.devleader.ca/2026/10/20/collections-in-c-access-mutation-and-ownership-explained)
- [List&lt;T&gt; 类（允许重复、按索引访问）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.list-1?view=net-10.0)
- [HashSet&lt;T&gt; 类（元素无特定顺序）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.hashset-1?view=net-10.0)
- [Dictionary&lt;TKey,TValue&gt; 类（键哈希必须稳定、枚举顺序未定义）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.dictionary-2?view=net-10.0)
- [IReadOnlyList&lt;T&gt; 接口（元素内容不保证只读）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.ireadonlylist-1?view=net-10.0)
- [ReadOnlyCollection&lt;T&gt; 类（包装器会反映底层变化）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.objectmodel.readonlycollection-1?view=net-10.0)
- [ConcurrentDictionary&lt;TKey,TValue&gt;.GetEnumerator（并发枚举不是时间点快照）](https://learn.microsoft.com/en-us/dotnet/api/system.collections.concurrent.concurrentdictionary-2.getenumerator?view=net-10.0)
- [Queue&lt;T&gt; 类](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.queue-1?view=net-10.0)
- [Stack&lt;T&gt; 类](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.stack-1?view=net-10.0)
