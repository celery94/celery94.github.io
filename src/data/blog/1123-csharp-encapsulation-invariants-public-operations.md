---
pubDatetime: 2026-10-30T09:35:00+08:00
title: "C# 封装：用公开操作守住不变量"
description: "从一个最小值大于最大值的区间讲起，说清楚封装要守的是对象的不变量：构造与变更共用一条校验、用公开操作替代逐字段赋值，以及 readonly 和只读视图各自的边界。"
tags: ["C#", ".NET", "Encapsulation", "OOP", "API Design"]
slug: "csharp-encapsulation-invariants-public-operations"
ogImage: "../../assets/1123/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/29/encapsulation-in-c-preserve-invariants-through-public-operations"
---

一个价格区间对象，最小值 8、最大值 3。两个字段各自都是合法的 `int`，放在一起什么都不是。这种状态不会在 setter 里报错，因为单独看每一次赋值，字段本身都没毛病。

封装要处理的就是这件事。它的边界落在「调用方被允许执行哪些操作」上，把字段改成 private 只是给这个边界腾出位置。当一个对象里有两个或更多值必须同时成立，就要把「一次状态转移」做成一个公开操作，让校验和赋值绑在一起。

Nick Cosentino 用三个小程序讲了这条线索：一个区间对象、一个只读字段持有者、一个日志集合。原文明说三个示例没有编译运行过，行为是从代码和当前微软文档推出来的，也不涉及并发或持久化。下面的代码出自原文，推断的部分我会标出来。

## 不变量先写成一句人话

不变量是模型打算一直保持为真的条件。区间的例子是：两个边界都非负，并且最小值不大于最大值。这些规则是例子自带的，C# 不会自动把任何规则套到 `int` 或属性上。

限制成员访问——这是封装在文档里的定义——只给了你一个可以执行规则的位置，不告诉你需要哪些规则。规则得自己写下来，用一句普通话说清楚合法的状态长什么样。

容易出问题的地方在于，这句话经常需要两个值才能说完。「最大值非负」和「最大值不小于最小值」看着都像在描述最大值，其实是两个不同的承诺。逐个属性检查，第二个承诺会被漏掉。

操作一次接收属于同一次转移的一组值，一起校验，然后通过对象正常的查询把新状态暴露出去。调用方表达的是意图，不用再执行一串互不相关的赋值。

对没有任何约束的数据，public setter 更省事；命名操作让关系变得可见，代价是多一个行为、多一份错误契约。哪种都不普适，不变量本身解释了这段代码为什么需要比 setter 更多的东西。

## 构造函数是第一个边界

构造函数文档的说法是「构造器用来保证实例在创建时有效」，所以构造器是建立区间初始规则的位置。只校验之后的变更、放行非法的初始值是行不通的。

第一个示例在给任何一个字段赋值之前先校验这一对值：

```csharp
using System;

namespace RangeExample;

internal static class Program
{
    private static void Main()
    {
        var range = new QuantityRange(2, 8);
        range.ChangeBounds(3, 10);

        Console.WriteLine($"{range.Minimum} to {range.Maximum}");
    }
}

public sealed class QuantityRange
{
    private int _minimum;
    private int _maximum;

    public QuantityRange(int minimum, int maximum)
    {
        ValidateBounds(minimum, maximum);
        _minimum = minimum;
        _maximum = maximum;
    }

    public int Minimum => _minimum;
    public int Maximum => _maximum;

    public void ChangeBounds(int minimum, int maximum)
    {
        ValidateBounds(minimum, maximum);

        _minimum = minimum;
        _maximum = maximum;
    }

    private static void ValidateBounds(int minimum, int maximum)
    {
        if (minimum < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(minimum));
        }

        if (maximum < minimum)
        {
            throw new ArgumentOutOfRangeException(
                nameof(maximum),
                "Maximum must be at least minimum.");
        }
    }
}
```

公开属性只允许观察，不允许赋值。`ChangeBounds` 代表一次逻辑转移。构造和变更共用 `ValidateBounds`，两条入口于是描述同一个合法状态，不会出现「构造函数查得少一点」这种漂移。

校验在两次赋值之前完成，所以校验抛异常时旧的这一对值原封不动。这个保证的范围有限：它不是并发保证。示例没有锁，也没有事务存储，它说明的是校验和变更的先后顺序，不是多线程同时访问时的安全。

## 有构造函数不等于对象处处有效

别因为对象有构造函数就假设它在任何意义上都「有效」。这个示例只校验自己的区间规则，它不知道某个客户是否有权选这个区间，不知道这个区间是否和存储里的记录一致，也不知道别的进程有没有改过另一个值。

这些职责属于别的边界。把它们分开，既能防止一个小模型变成杂七杂八检查的堆放处，也不影响它守住自己那份含义。

## 属性也是行为

属性可以拒绝非法的赋值，而不是照单存下——访问器本来就是方法，微软的属性指南也把校验列为它的用途之一。

但属性级校验和操作级校验不能互换。如果调用方分别改两个相关的值，中间那一对可能违反规则。把区间从 2..8 挪到 10..12，先调哪个 setter 都不对：先改最小值得到 10..8，这个中间态非法；先改最大值得到 2..12，状态合法但已经不是调用方要的区间。公开操作直接描述目标区间，对象自己处理表示方式，不用让每个调用方去发现一个安全的调用顺序。

错误也更好解释：非法的最大值在替换旧值之前就被拒绝，不会出现「改了一半」的状态。悄悄忽略非法赋值会让调用方猜自己的请求到底成功没有。

这个示例用异常表达非法参数。换成另一种 API，用有明确文档的返回类型表达预期内的拒绝也完全可以。要点是失败要显式，对象的状态要与承诺的失败行为一致。

封装也不要求给每个类型配一个接口。一个带有意义操作的公开类本身就已经是边界了；只有当一个只暴露部分能力的接口能一句话说清它承诺什么，为它多抽一层才值得。

## readonly 冻不住它指向的对象

readonly 这个词听起来比它实际的保证更强。微软的 readonly 参考文档说的是：readonly 引用字段始终指向同一个对象，但那个对象的数据仍然可以变。

第二个示例在不暴露字段的前提下演示了这个区别。持有者收到一个列表，而另一个变量还指着同一个列表，可以往里加东西：

```csharp
using System;
using System.Collections.Generic;

namespace SharedReferenceExample;

internal static class Program
{
    private static void Main()
    {
        var numbers = new List<int> { 4 };
        var holder = new NumberHolder(numbers);

        numbers.Add(9);
        Console.WriteLine(holder.Count);
    }
}

public sealed class NumberHolder
{
    private readonly List<int> _numbers;

    public NumberHolder(List<int> numbers)
    {
        if (numbers is null)
        {
            throw new ArgumentNullException(nameof(numbers));
        }

        _numbers = numbers;
    }

    public int Count => _numbers.Count;
}
```

`_numbers` 一次都没被重新赋值，列表的成员照样通过另一个引用变了。按代码推，`numbers.Add(9)` 之后会打印 2——4 和 9 都在里面。微软关于对象引用的说明支持这个判断：给类引用赋值不会创建另一个对象。

这是一条浅边界。它管住的是字段的重新赋值，管不住所有能到达的变更。如果容器对象控制着这个列表的全部引用，私有 readonly 列表完全合理；如果调用方留着自己传进来的那个列表，保证就变了味。

构造函数注入不消除这些别名。把参数类型改成只读接口也不消除：输入契约能限制接收方看得见的操作，证明不了没有别人能改底层实例。

所以封装评审要顺着引用走，不能只数访问修饰符。问三个问题：谁能拿到这个对象、他们能对它做什么、模型是否依赖这些操作不发生。

## View 会跟着底层变，快照不会

只读视图说的是：消费者不能通过这个视图改集合的成员。快照说的是：返回的成员对应某一时刻，之后成员再怎么变都不跟着动。

包装器不是冻结的副本，只读视图会跟着底层集合变。这组差别站内那篇 [C# 集合选型：访问语义与所有权边界](https://celery94.github.io/posts/csharp-collections-access-mutation-ownership/) 用可运行示例跑过；这里要问的是另一个问题：一个类把内部集合交出去，同时开了哪几条路。

第三个示例把两种选择刻意放在一起。它自己持有列表，不接受外部保留的列表。`View` 包住当前列表，`GetSnapshot` 把整数元素拷进一个新数组再把数组包起来：

```csharp
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace CollectionBoundaryExample;

internal static class Program
{
    private static void Main()
    {
        var readings = new ReadingLog();
        readings.Add(12);

        var view = readings.View;
        var snapshot = readings.GetSnapshot();

        readings.Add(15);

        Console.WriteLine($"View count: {view.Count}");
        Console.WriteLine($"Snapshot count: {snapshot.Count}");
    }
}

public sealed class ReadingLog
{
    private readonly List<int> _readings = new();
    private readonly ReadOnlyCollection<int> _view;

    public ReadingLog()
    {
        _view = _readings.AsReadOnly();
    }

    public IReadOnlyList<int> View => _view;

    public void Add(int reading)
    {
        if (reading < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(reading));
        }

        _readings.Add(reading);
    }

    public IReadOnlyList<int> GetSnapshot()
    {
        return Array.AsReadOnly(_readings.ToArray());
    }
}
```

`List.ToArray` 把元素拷到新数组，`Array.AsReadOnly` 返回一个包装。两个操作目的不同：拷贝把成员的存储分开，包装限制通过返回的集合做修改。

照代码推，这段跑起来会看到 `View.Count` 是 2、`Snapshot.Count` 是 1。同一个返回类型，两种时间语义。

示例用整数，所以拷元素就等于隔离；如果列表装的是可变类实例，拷数组之后装的还是同一批实例——冻结成员不等于冻结元素。快照要新建一份存储，实时视图省掉这次拷贝、代价是跟着模型之后的添加一起变；这是取舍，不是基准测试结果，也不说明哪个在应用里更快。

命名能让人发现差别：`View` 暗示持续观察，`GetSnapshot` 暗示某一刻的独立快照，这比一个泛泛的 `Items` 好——后者的时间行为没法猜。但命名替代不了文档：要拿报表的调用方需要一份固定的成员，要盯实时变化的调用方需要实时视图，两种时间语义和可变语义都要写进注释，别让人从返回类型反推。

## 集合怎么暴露本身就是不变量的一部分

假设这个日志只允许非负读数。把内部那个可变的列表直接返回，就等于开了一条不经过 `Add` 也能塞进负数的路。校验还在，但公开边界不再要求所有成员变更都走它。

返回包装封死了通过这个返回 API 的那条路。它不证明所有能想到的变更都不可能，这个例子也没把访问控制当成安全沙箱——它说的是给调用方提供了哪些普通的集合操作。

输入集合同理。如果合法状态依赖成员稳定，直接存下调用方持有的可变列表，等于把自己的假设交给对方保管。构造时拷贝成员可以分开这层边界，元素引用仍然要单独分析。

集合类型本身怎么选是另一个问题，这里只讨论它对封装边界的影响。

## 不可变要限定范围

构造之后再也不变的对象能简化一部分状态推理。但「不可变」需要一个明确的边界：只有标量属性稳定？成员也稳定？集合里的对象是否也稳定？

微软的 record 文档明确列了带可变属性的 record，也说明 init-only 属性是浅层不可变。`record` 这个关键字本身就回答不了上面三个问题。

回头看这三个示例里的四种保证：区间可变但封装住了；持有者的 readonly 字段指向共享的可变数据；日志的视图跟着底层列表变；`GetSnapshot` 把整数成员固定在某一刻。四种承诺不该贴同一个「不可变」标签。

## 判断要不要这么写

这套写法有成本，不是所有类都配得上。

字段之间没有关系、校验只在入口做一次、生命周期内不再变化，这种 DTO 或消息契约用 public setter 就够，硬加一层操作只是多写代码。字段之间互相约束、而且每次变更都要保持同一个条件，才需要把转移做成操作。

落地时按这个顺序走：

1. 把不变量写成一句不带术语的话，比如「最小值不大于最大值」。
2. 列出所有能让这句话变假的入口：构造函数、每个公开方法、每个返回出去的引用、每个传进来的引用。
3. 每个入口要么自己校验，要么根本不给出去。
4. 把这句话写进注释或测试名，后来的人才知道这条边界有主。

第 2 步是关键，也是最容易跳过的一步。访问修饰符只回答了「谁能在源码里写这个字段」，没回答「谁能在运行时改变这个对象能观察到的状态」。readonly 字段和只读视图容易被当成后者的答案：它们各自只封了一条路，同时留下了另一条。

## 参考

- [Encapsulation in C#: Preserve Invariants Through Public Operations](https://www.devleader.ca/2026/10/29/encapsulation-in-c-preserve-invariants-through-public-operations)
- [Microsoft：Object-Oriented Programming (C#)](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/object-oriented/)
- [Microsoft：Constructors (C# programming guide)](https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/classes-and-structs/constructors)
- [Microsoft：Properties (C# programming guide)](https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/classes-and-structs/properties)
- [Microsoft：Objects (C# fundamentals)](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/object-oriented/objects)
- [Microsoft：readonly keyword (C# reference)](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/keywords/readonly)
- [Microsoft：ReadOnlyCollection&lt;T&gt;](https://learn.microsoft.com/en-us/dotnet/api/system.collections.objectmodel.readonlycollection-1?view=net-10.0)
- [Microsoft：Record types (C# reference)](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/builtin-types/record)
