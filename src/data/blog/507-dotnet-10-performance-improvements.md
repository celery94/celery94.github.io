---
pubDatetime: 2025-10-26
title: .NET 10 性能改进：系统性优化的艺术
description: 深入解析 .NET 10 中数百项性能优化改进,包括 JIT 编译器增强、逃逸分析与栈分配、去虚拟化、边界检查消除、LINQ 优化、集合改进、网络性能提升等核心技术,展示如何通过系统性的微小改进实现显著的性能提升
tags: [".NET", "Performance", "JIT", "Optimization", "Memory"]
slug: dotnet-10-performance-improvements
source: https://devblogs.microsoft.com/dotnet/performance-improvements-in-net-10/
---

## 引言:冰块贸易的启示

十九世纪的美国北部,每到冬季,湖泊表面便会结冰。精明的商人们意识到这是一座季节性的金矿。最成功的冰块采收作业如同一台精密机器运转:工人们会清除湖面积雪使冰层长得更厚实,用马拉犁在冰面划出规整的网格,然后切割出数百磅重的标准冰块。这些冰块沿着水道漂向岸边,再被撬上斜坡运入仓库保存。

仓储本身就是一门艺术。巨型木制冰库可容纳数万吨冰块,内衬隔热材料(通常是稻草)。如果做得好,冰块可在炎夏中保持数月;做得差,打开门就是一滩冰水。对于长途运输(通常通过船运),每一度温差、隔热层的每道裂缝、运输中的每一天延误,都意味着更多融化和损失。

波士顿的"冰王"弗雷德里克·都德(Frederic Tudor)痴迷于系统性效率改进。竞争对手眼中无法避免的损耗,在他看来都是可解决的问题。经过试验,他采用廉价的锯木废料作为隔热材料,其性能远超稻草,大幅减少了融化损失。在采收效率上,他的团队采用了纳撒尼尔·怀斯(Nathaniel Jarvis Wyeth)的网格刻线系统,生产出规格统一的冰块,可以紧密堆叠,最小化船舱中的空气间隙暴露。为缩短从岸边到船舶的关键时间,都德在码头附近建设了港口基础设施和仓库,大大加快了装卸速度。从工具到冰库设计再到物流,每一项改进都放大了前一项的效果,将高风险的地方性生意转变为可靠的全球贸易。凭借都德的增强措施,他的坚实冰块最终抵达了哈瓦那、里约热内卢,甚至十九世纪三十年代需要航行四个月才能到达的加尔各答。他的性能提升使得产品能在此前不可想象的旅程中生存。

让都德的冰块能够环游半个地球的,并非某个宏大的创意,而是大量小改进的叠加,每一项都倍增着前一项的效果。在软件开发中,同样的原理成立:性能的巨大飞跃很少来自单一的全面改变,而是来自数百甚至数千个有针对性的优化,这些优化累积起来才产生变革性的效果。.NET 10 的性能故事并非关于某个魔法般的想法,而是关于在这里削减几纳秒,在那里节省几十字节,精简那些被执行数万亿次的操作。

在本文中,我们将深入探讨 .NET 10 自 .NET 9 以来的数百项微小但有意义且不断累积的性能改进(如果您从 LTS 版本即 .NET 8 升级,还会看到 .NET 9 中所有改进的叠加效果)。让我们系统地了解这些改进如何共同构建起 .NET 10 的性能优势。

## JIT 编译器:性能优化的核心

Just-In-Time(JIT)编译器是 .NET 性能优化中最具影响力的领域之一。每个 .NET 应用程序,无论是小型控制台工具还是大规模企业服务,最终都依赖 JIT 将中间语言(IL)代码转换为优化的机器码。JIT 生成代码质量的任何提升都会在整个生态系统中产生连锁反应,无需开发者更改任何代码,甚至无需重新编译 C# 源码即可获得性能改进。.NET 10 在这方面带来了诸多突破性优化。

### 去抽象化:消除抽象层的性能开销

与许多编程语言一样,.NET 历来存在"抽象惩罚"——使用接口、迭代器和委托等高级语言特性时可能产生额外的分配和间接调用开销。近年来,JIT 编译器在优化消除这些抽象层方面不断进步,使开发者能够编写简洁的代码同时获得出色的性能。.NET 10 延续了这一传统。其结果是,惯用的 C# 代码(使用接口、`foreach` 循环、Lambda 表达式等)的执行速度越来越接近精心优化的手工代码。

#### 对象栈分配:逃逸分析的新突破

.NET 10 中最令人兴奋的去抽象化进展之一是扩展了逃逸分析以支持对象的栈分配。逃逸分析是一种编译器技术,用于确定在方法中分配的对象是否会"逃逸"该方法,即判断该对象在方法返回后是否仍可访问(例如被存储在字段中或返回给调用者),或者是否以运行时无法追踪的方式使用(比如传递给未知的被调用方)。如果编译器能够证明对象不会逃逸,那么该对象的生命周期就限定在方法内,可以在栈上分配而非堆上。栈分配成本更低(只需指针碰撞即可分配,方法退出时自动释放),并减少 GC 压力,因为对象根本不需要 GC 追踪。

.NET 9 已经引入了一些有限的逃逸分析和栈分配支持,.NET 10 在此基础上大幅扩展。其中一个关键改进是教会 JIT 如何对委托进行逃逸分析,特别是证明委托的 `Invoke` 方法(由运行时实现)不会保存 `this` 引用。如果逃逸分析能证明委托的对象引用不会以其他方式逃逸,委托实质上可以被"蒸发"掉。

考虑以下基准测试代码:

```csharp
using BenchmarkDotNet.Attributes;

[MemoryDiagnoser]
public class DelegateStackAllocation
{
    [Benchmark]
    [Arguments(42)]
    public int Sum(int y)
    {
        Func<int, int> addY = x => x + y;
        return DoubleResult(addY, y);
    }

    private int DoubleResult(Func<int, int> func, int arg)
    {
        int result = func(arg);
        return result + result;
    }
}
```

这段 C# 代码的背后,编译器需要创建一个 `Func<int, int>` 委托,该委托"捕获"了局部变量 `y`。这意味着编译器需要将 `y` "提升"为一个对象的字段(不再是真正的局部变量),委托则指向该对象上的一个方法,从而可以访问 `y`。这大致就是 C# 编译器生成的 IL 在反编译为 C# 后的样子:

```csharp
public int Sum(int y)
{
    <>c__DisplayClass0_0 c = new();
    c.y = y;
    Func<int, int> func = new(c.<Sum>b__0);
    return DoubleResult(func, c.y);
}

private sealed class <>c__DisplayClass0_0
{
    public int y;
    internal int <Sum>b__0(int x) => x + y;
}
```

从中可以看到,闭包导致两次分配:一次分配"显示类"(C# 编译器对这些闭包类型的命名),另一次分配委托。这就是 .NET 9 结果中 88 字节分配的来源:显示类 24 字节,委托 64 字节。

然而在 .NET 10 版本中,我们只看到 24 字节分配——JIT 成功消除了委托分配。对于 .NET 9 和 .NET 10,JIT 都能内联 `DoubleResult`,使得委托不会逃逸。但在 .NET 10 中,它能够对委托进行栈分配。

这个改进还使得数组的栈分配成为可能。考虑以下代码,其中需要分配一个数组来传递输入参数:

```csharp
[Benchmark]
public void ProcessStrings()
{
    Process(new string[] { "a", "b", "c" });
    
    static void Process(string[] inputs)
    {
        foreach (string input in inputs)
        {
            // 处理输入
        }
    }
}
```

在理想情况下,应该有一个接受 `ReadOnlySpan<string>` 而非 `string[]` 的 `Process` 方法重载,这样就能通过构造避免分配。但对于所有必须创建数组的情况,.NET 10 都能提供帮助。

在性能基准测试结果中,我们看到 .NET 9 有 48 字节的分配(数组对象本身),而 .NET 10 则没有分配。JIT 能够内联 `Process`,看到数组不会离开栈帧,于是对其进行栈分配。

当然,既然我们现在能够栈分配数组,我们也希望能处理数组的常见使用方式:通过 Span。相关改进教会逃逸分析能够推理结构体中的字段,这包括 `Span<T>`,因为它"只是"一个存储 `ref T` 字段和 `int` 长度字段的结构体。

```csharp
[Benchmark]
public void CopyBytes()
{
    byte[] _buffer = new byte[3];
    Copy3Bytes(0x12345678, _buffer);
}

private static void Copy3Bytes(int value, Span<byte> dest)
    => BitConverter.GetBytes(value).AsSpan(0, 3).CopyTo(dest);
```

在 .NET 9 中,我们得到预期的 32 字节分配(用于 `byte[]`)。在 .NET 10 中,通过内联 `GetBytes` 和 `AsSpan`,JIT 可以看到数组不会逃逸,并可以使用栈分配的版本来初始化 Span,就像它是从任何其他栈分配创建的一样(比如 `stackalloc`)。

#### 去虚拟化:加速接口调用

接口和虚方法是 .NET 和抽象的关键方面。能够"去虚拟化"这些抽象对 JIT 来说是一项重要工作,.NET 10 在这方面取得了显著进展。

虽然数组是 C# 和 .NET 提供的最核心特性之一,JIT 在优化数组的许多方面做得很好,但有一个特定领域一直让它头疼:数组的接口实现。运行时为 `T[]` 生成了一系列接口实现,由于它们的实现方式与 .NET 中其他所有接口实现都不同,JIT 一直无法应用相同的去虚拟化能力。对于深入研究微基准测试的人来说,这可能导致一些奇怪的观察。

考虑以下性能比较,使用 `foreach` 循环(通过枚举器)和 `for` 循环(索引访问)遍历 `ReadOnlyCollection<T>`:

```csharp
using System.Collections.ObjectModel;

[Benchmark]
public int SumEnumerable()
{
    ReadOnlyCollection<int> _list = new(Enumerable.Range(1, 1000).ToArray());
    int sum = 0;
    foreach (var item in _list)
    {
        sum += item;
    }
    return sum;
}

[Benchmark]
public int SumForLoop()
{
    ReadOnlyCollection<int> _list = new(Enumerable.Range(1, 1000).ToArray());
    int sum = 0;
    int count = _list.Count;
    for (int i = 0; i < count; i++)
    {
        sum += _list[i];
    }
    return sum;
}
```

当被问到"哪个会更快"时,显而易见的答案是 `SumForLoop`。毕竟,`SumEnumerable` 要分配一个枚举器,并且需要进行两倍数量的接口调用(每次迭代 `MoveNext` + `Current`,相比 `this[int]`)。然而,事实证明显而易见的答案是错的。在 .NET 9 中的计时结果显示 `SumEnumerable` 反而更快!

这背后的原因非常微妙。首先,需要知道 `ReadOnlyCollection<T>` 只是包装了一个任意的 `IList<T>`,`ReadOnlyCollection<T>` 的 `GetEnumerator()` 返回 `_list.GetEnumerator()`,并且 `ReadOnlyCollection<T>` 的索引器只是索引到 `IList<T>` 的索引器。在 .NET 9 中,JIT 难以去虚拟化对 `T[]` 接口实现的调用,因此它不会去虚拟化 `_list.GetEnumerator()` 调用或 `_list[index]` 调用。然而,返回的枚举器只是一个实现 `IEnumerator<T>` 的普通类型,JIT 可以很好地去虚拟化其 `MoveNext` 和 `Current` 成员。这意味着我们通过索引器实际上付出了更多代价,因为对于 N 个元素,我们要进行 N 次接口调用,而使用枚举器,我们只需要进行一次 `GetEnumerator` 接口调用,之后就没有更多接口调用了。

值得庆幸的是,这在 .NET 10 中已经得到解决。几个 PR 使得 JIT 能够去虚拟化数组的接口方法实现。现在,当我们运行相同的基准测试时(使用 `ToArray` 而不是 `ToList`),我们得到了更符合预期的结果,两个基准测试都从 .NET 9 提升到 .NET 10,并且 `SumForLoop` 在 .NET 10 上最快。

保护去虚拟化(Guarded Devirtualization, GDV)在 .NET 10 中也得到了改进。通过动态 PGO(Profile-Guided Optimization),JIT 能够对方法的编译进行插桩,然后使用生成的分析数据来发射优化版本的方法。它可以分析的内容之一是在虚拟分派中使用了哪些类型。如果一种类型占主导地位,它可以在代码生成中对该类型进行特殊处理,发射专门针对该类型定制的实现。这样就能在专用路径中实现去虚拟化,该路径由相关的类型检查"保护",因此称为"GDV"。然而在某些情况下(例如虚拟调用在共享泛型上下文中进行),GDV 不会生效。现在它会生效了。

```csharp
[Benchmark]
public bool CompareStrings()
    => GenericEquals("abc", "abc");

private static bool GenericEquals<T>(T a, T b)
    => EqualityComparer<T>.Default.Equals(a, b);
```

在这个基准测试中,我们在 .NET 9 到 .NET 10 之间看到了大约 1.86 倍的性能提升,这得益于改进的去虚拟化。

另一个改进通过在后期去虚拟化阶段后再次查找机会,帮助更多方法被内联。JIT 的优化分为多个阶段;每个阶段都可以做出改进,而这些改进可能会暴露额外的机会。如果这些机会只能被已经运行过的阶段利用,它们可能会被错过。但对于相对便宜的阶段,比如查找额外的内联机会,可以在足够多的其他优化发生后重复执行这些阶段,使其很可能富有成效。

### 边界检查消除

C# 是一种内存安全的语言,这是现代编程语言的重要方面。其关键组成部分是无法越过数组、字符串或 Span 的开头或结尾。运行时确保任何此类无效尝试都会产生异常,而不是被允许执行无效的内存访问。我们可以通过一个小基准测试看到这是什么样子:

```csharp
[Benchmark]
public int ReadArrayElement()
{
    int[] _array = new int[3];
    return _array[2];
}
```

这是一个有效的访问:`_array` 包含三个元素,`Read` 方法正在读取其最后一个元素。然而,JIT 不能 100% 确定此访问在边界内(可能有什么东西改变了 `_array` 字段中的内容使其变成更短的数组),因此它需要发射检查以确保我们不会越过数组的末尾。

查看 `Read` 生成的汇编代码:

```assembly
; Tests.Read()
push rax
mov rax,[rdi+8]
cmp dword ptr [rax+8],2
jbe short M00_L00
mov eax,[rax+18]
add rsp,8
ret
M00_L00:
call CORINFO_HELP_RNGCHKFAIL
int 3
```

在这段汇编中,`cmp` 指令从该地址的偏移量 8 处加载值;这恰好是数组对象中数组长度的存储位置。因此,这条 `cmp` 指令就是边界检查;它将 `2` 与该长度进行比较以确保在边界内。如果数组太短无法进行此访问,下一条 `jbe` 指令将分支到 `M00_L00` 标签,该标签调用 `CORINFO_HELP_RNGCHKFAIL` 辅助函数抛出 `IndexOutOfRangeException`。每当您在方法末尾看到这对 `call CORINFO_HELP_RNGCHKFAIL` / `int 3` 时,就意味着 JIT 在该方法中至少发射了一次边界检查。

当然,我们不仅想要安全,我们还想要出色的性能,如果每次从数组(或字符串或 Span)读取都产生这样的额外检查,对性能来说将是可怕的。因此,JIT 努力在能够通过构造证明访问安全时避免发射这些检查。每个 .NET 版本都会找到并实现更多避免先前生成的边界检查的机会。.NET 10 延续了这一趋势。

第一个示例涉及将数学运算的结果保证在边界内。改进教会 JIT 理解 `Log2` 等操作可能产生的最大值,如果该最大值在边界内,那么任何结果都保证在边界内。

```csharp
[Benchmark]
[Arguments(12345)]
public nint CountDigits(ulong value)
{
    ReadOnlySpan<byte> log2ToPow10 = [
        1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5,
        6, 6, 6, 7, 7, 7, 7, 8, 8, 8, 9, 9, 9, 10, 10, 10,
        10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 13, 14, 14, 14,
        15, 15, 15, 16, 16, 16, 16, 17, 17, 17, 18, 18, 18, 19,
        19, 19, 19, 20
    ];
    return log2ToPow10[(int)ulong.Log2(value)];
}
```

在 .NET 9 输出中存在边界检查,而在 .NET 10 输出中不存在。我选择这个基准测试案例并非巧合。这个模式出现在内部方法 `FormattingHelpers.CountDigits` 中,该方法被核心基元类型在其 `ToString` 和 `TryFormat` 实现中使用,以确定渲染数字所需的空间大小。由于这个例程足够核心,它使用了不安全代码来避免边界检查。通过此修复,代码已经改回使用简单的 Span 访问,并且即使使用更简单的代码,它现在也更快。

现在考虑以下代码:

```csharp
[Benchmark]
[Arguments(new int[] {1, 2, 3, 4, 5, 1})]
public bool StartAndEndAreSame(int[] ids)
    => ids[0] == ids[^1];
```

JIT 无法知道 `int[]` 是否为空,因此它确实需要边界检查;否则,访问 `ids[0]` 可能越过数组末尾。然而,这是我们在 .NET 9 上看到的:

```assembly
; .NET 9
; Tests.StartAndEndAreSame(Int32[])
push rax
mov eax,[rsi+8]
test eax,eax
je short M00_L00
mov ecx,[rsi+10]
lea edx,[rax-1]
cmp edx,eax
jae short M00_L00
mov eax,edx
cmp ecx,[rsi+rax*4+10]
sete al
movzx eax,al
add rsp,8
ret
M00_L00:
call CORINFO_HELP_RNGCHKFAIL
int 3
```

注意有两个跳转到处理失败边界检查的 `M00_L00` 标签……这是因为这里有两个边界检查,一个用于开始访问,一个用于结束访问。但这不应该是必要的。`ids[^1]` 与 `ids[ids.Length - 1]` 相同。如果代码成功访问了 `ids[0]`,这意味着数组至少有一个元素长度,如果它至少有一个元素长度,`ids[ids.Length - 1]` 将始终在边界内。因此,不应需要第二次边界检查。确实,得益于相关改进,这是我们现在在 .NET 10 上得到的(一个分支到 `M00_L00` 而不是两个):

```assembly
; .NET 10
; Tests.StartAndEndAreSame(Int32[])
push rax
mov eax,[rsi+8]
test eax,eax
je short M00_L00
mov ecx,[rsi+10]
dec eax
cmp ecx,[rsi+rax*4+10]
sete al
movzx eax,al
add rsp,8
ret
M00_L00:
call CORINFO_HELP_RNGCHKFAIL
int 3
```

对我来说,这里真正有趣的是移除边界检查的连锁效应。它不仅消除了边界检查典型的 `cmp/jae` 指令对。.NET 9 版本的代码有这样的序列:

```assembly
lea edx,[rax-1]
cmp edx,eax
jae short M00_L00
mov eax,edx
```

此时在汇编中,`rax` 寄存器存储的是数组的长度。它在计算 `ids.Length - 1` 并将结果存储到 `edx` 中,然后检查 `ids.Length-1` 是否在 `ids.Length` 的边界内(唯一不在边界内的情况是数组为空,使得 `ids.Length-1` 回绕到 `uint.MaxValue`);如果不在,它跳转到失败处理程序,如果在,它将已计算的 `ids.Length - 1` 存储到 `eax` 中。通过移除边界检查,我们摆脱了那两条中间指令,留下这些:

```assembly
lea edx,[rax-1]
mov eax,edx
```

这有点傻,因为这个序列只是在计算递减,只要修改标志是可以接受的,它可以只是:

```assembly
dec eax
```

正如您在 .NET 10 输出中看到的,这正是 .NET 10 现在所做的。

## LINQ:查询性能的持续优化

LINQ(Language Integrated Query)自 .NET 3.5 以来一直是 C# 中最具表现力的特性之一,它使开发者能够以声明式方式查询和转换数据。然而,早期的 LINQ 实现在性能上存在不少开销。近年来,.NET 团队在保持 LINQ API 简洁的同时,大幅优化了其底层实现。.NET 10 继续这一趋势。

### 改进的迭代器模式

其中一个关键优化涉及 LINQ 操作符如何链接在一起。许多 LINQ 操作符(如 `Where`、`Select`、`Skip` 和 `Take`)会返回实现了 `IEnumerable<T>` 的迭代器对象。在 .NET 10 中,这些迭代器的实现得到了优化,减少了分配和虚拟调用的开销。

例如,`Enumerable.Range` 方法在 .NET 10 中得到了显著改进。它现在返回一个更紧凑的迭代器结构,该结构可以在某些情况下被 JIT 完全去虚拟化。这意味着简单的 LINQ 查询链可以被编译为与手写的 `for` 循环几乎同样高效的机器码。

### SearchValues 优化

`SearchValues<T>` 是 .NET 8 中引入的类型,旨在优化在字符串或 Span 中搜索特定值集合的性能。.NET 10 扩展了其应用场景,使其能处理更复杂的模式匹配。

例如,当搜索多个字符时,`SearchValues` 现在可以利用 SIMD(单指令多数据)指令并行处理多个字符,在现代处理器上实现显著的吞吐量提升。这对于文本解析、日志处理和数据验证等场景特别有益。

```csharp
private static readonly SearchValues<char> s_whitespace = 
    SearchValues.Create(" \t\r\n");

[Benchmark]
public bool ContainsWhitespace(string input)
    => input.AsSpan().ContainsAny(s_whitespace);
```

在这个示例中,.NET 10 的 `SearchValues` 实现使用了向量化搜索,相比逐字符检查的简单实现,性能提升可达数倍。

## 集合:核心数据结构的优化

集合是几乎所有 .NET 应用程序的基础。`List<T>`、`Dictionary<TKey, TValue>` 和数组等类型被大量使用,因此对这些类型的任何优化都会对应用程序的整体性能产生广泛影响。

### List 泛型的改进

`List<T>` 是 .NET 中使用最广泛的集合类型之一。.NET 10 对其进行了多项增强:

1. **Remove 方法的优化**: `Remove` 方法现在使用更高效的内存移动策略,在移除元素时减少了 CPU 周期和内存带宽的消耗。

2. **Capacity 管理**: 当列表增长时,容量调整策略得到了改进,减少了不必要的重新分配次数。

3. **RemoveAll 的向量化**: `RemoveAll` 方法现在利用 SIMD 指令加速谓词评估和元素移除过程。

```csharp
[Benchmark]
public void RemoveEvenNumbers()
{
    List<int> numbers = new(Enumerable.Range(0, 10000));
    numbers.RemoveAll(n => n % 2 == 0);
}
```

这个看似简单的操作在 .NET 10 中的性能得到了显著提升,部分原因是改进的内存布局和 SIMD 优化。

### Dictionary<TKey, TValue> 的增强

字典是另一个关键的集合类型,在 .NET 10 中获得了多项改进:

1. **更好的哈希函数利用**: 字典现在能更有效地利用高质量的哈希函数,减少冲突和重新哈希的频率。

2. **TryAdd 的优化**: `TryAdd` 方法的路径得到了简化,减少了分支预测失败和不必要的内存访问。

3. **枚举性能**: 遍历字典的性能得到了改进,特别是在使用 `foreach` 时。

## 网络:更快的网络通信

现代应用程序严重依赖网络通信,因此网络栈的性能至关重要。.NET 10 在 HTTP 客户端、套接字和相关网络 API 方面带来了多项改进。

### HTTP/2 和 HTTP/3 优化

`HttpClient` 在 .NET 10 中获得了对 HTTP/2 和 HTTP/3 协议的优化支持:

1. **连接池改进**: HTTP/2 连接的重用策略得到了改进,减少了建立新连接的开销。

2. **流优先级**: HTTP/2 流的优先级处理得到了优化,使关键请求能更快得到响应。

3. **QUIC 性能**: 作为 HTTP/3 基础的 QUIC 协议实现得到了优化,减少了延迟和改善了在不稳定网络条件下的性能。

### Socket 改进

底层的 `Socket` API 也获得了性能提升:

1. **零拷贝发送和接收**: 在支持的平台上,现在可以使用零拷贝技术减少数据传输时的内存复制。

2. **异步操作的优化**: 异步套接字操作的路径得到了简化,减少了分配和上下文切换。

## JSON 序列化:更快的数据处理

JSON 是现代 Web 应用中数据交换的通用格式。`System.Text.Json` 在 .NET 10 中获得了多项性能改进。

### JsonElement 的增强

`JsonElement` 是用于表示 JSON 值的轻量级类型。.NET 10 为其添加了新的 `Parse` 方法,使得创建 `JsonElement` 实例更加高效,而无需首先创建 `JsonDocument`:

```csharp
// .NET 9 及更早版本
JsonElement element;
using (JsonDocument doc = JsonDocument.Parse(json))
{
    element = doc.RootElement.Clone();
}

// .NET 10
JsonElement element = JsonElement.Parse(json);
```

新的 `JsonElement.Parse` 方法避免了 `JsonDocument` 的开销和克隆操作,使得临时 JSON 解析更加高效。

### 流式写入 Base64 数据

对于需要在 JSON 中嵌入大量二进制数据的场景,.NET 10 添加了 `WriteBase64StringSegment` 方法,允许分段写入 Base64 编码的数据:

```csharp
writer.WriteStartObject();
writer.WritePropertyName("data");

// 分段写入 Base64 数据
while ((read = await stream.ReadAsync(buffer)) > 0)
{
    writer.WriteBase64StringSegment(
        buffer.AsSpan(0, read), 
        isFinalSegment: false);
}
writer.WriteBase64StringSegment(default, isFinalSegment: true);

writer.WriteEndObject();
```

这种方法消除了需要在内存中缓冲整个二进制数据的需求,大幅减少了内存占用和延迟。

## 诊断与监控

性能监控和诊断工具本身也需要高效。.NET 10 对 `Stopwatch`、`Activity` 和日志记录基础设施进行了优化。

### Stopwatch 的栈分配

多年来,许多代码库引入了基于结构体的 `ValueStopwatch`,因为 `Stopwatch` 是一个类,但它只是包装了一个 `long`(时间戳)。通过 .NET 10 中的逃逸分析和栈分配改进,现在可以直接使用 `Stopwatch` 而无需分配:

```csharp
Stopwatch sw = Stopwatch.StartNew();
// ... 测量的代码
sw.Stop();
TimeSpan elapsed = sw.Elapsed;
```

在许多情况下,JIT 现在能够栈分配 `Stopwatch` 实例,使其性能与手动使用 `Stopwatch.GetTimestamp` 方法相当,但语法更加简洁。

### Activity 的并发优化

`Activity` 类型用于分布式追踪。在 .NET 10 中,`ActivitySource` 维护监听器列表的方式得到了改进,从使用锁保护的列表切换到不可变数组。这大幅减少了启动和停止 `Activity` 时的线程竞争,这是高频操作,因此这一改进对分布式追踪场景产生了显著影响。

## 密码学:量子后安全

.NET 10 在密码学方面的大量工作集中在量子后密码学(Post-Quantum Cryptography, PQC)上。PQC 指的是一类旨在抵抗量子计算机攻击的密码算法。随着"现在收集,以后解密"攻击的威胁(资金雄厚的攻击者收集加密的互联网流量,期待将来能够解密并阅读)以及迁移关键基础设施所需的多年过程,向量子安全密码标准的过渡已成为紧迫的优先事项。

.NET 10 添加了对以下算法的支持:

- **ML-DSA**: 美国国家标准与技术研究院(NIST)的 PQC 数字签名算法
- **Composite ML-DSA**: 互联网工程任务组(IETF)草案规范,用于创建将 ML-DSA 与经典加密算法(如 RSA)结合的签名
- **SLH-DSA**: 另一个 NIST PQC 签名算法
- **ML-KEM**: NIST PQC 密钥封装算法

虽然这些 PQC 工作不是关于性能的,但它们的设计非常关注现代的考虑因素,性能是关键驱动因素。与从 `AsymmetricAlgorithm` 派生的旧类型围绕数组设计不同(span 支持是后来添加的),新类型以 Span 为中心设计,基于数组的 API 仅为方便而提供。

除了 PQC,还有一些密码学相关的更改专注于性能。在 Linux 上,改进了 OpenSSL "摘要"性能。.NET 的密码学栈构建在底层平台的本地密码库之上;在 Linux 上,这意味着使用 OpenSSL。通过相关改进,.NET 10 现在在 OpenSSL 3.x 上使用显式获取和缓存的方式,而不是依赖隐式获取,从而在 OpenSSL 基础平台上实现了更精简和更快的密码哈希操作。

## 其他零散改进

正如每个 .NET 版本一样,有大量 PR 以某种方式帮助提高了性能。这些改进越多,应用程序和服务的整体开销就越低。以下是本版本中的一些示例:

- **GC 改进**: DATAS(Dynamic Adaptation To Application Sizes)在 .NET 8 中引入,在 .NET 9 中默认启用。现在在 .NET 10 中,对 DATAS 进行了调优以改善其整体行为,减少不必要的工作,平滑暂停(尤其是在高分配率下),纠正可能导致额外短收集(gen1)的碎片计数,以及其他此类调整。净结果是更少的不必要收集,更稳定的吞吐量,以及对分配密集型工作负载更可预测的延迟。

- **GCHandle 优化**: 引入了强类型的 `GCHandle<T>`、`PinnedGCHandle<T>` 和 `WeakGCHandle<T>`,不仅解决了一些可用性问题,还能够削减旧设计带来的一些开销。

- **Mono 解释器**: Mono 解释器获得了对几个操作码的优化支持,包括开关、新数组和内存屏障。但可以说更有影响力的是一系列十几个 PR,使解释器能够在 WebAssembly(Wasm)中向量化更多操作。

- **FCALL 移除**: 大量 PR 致力于移除 FCALL,这些是从托管代码到运行时中本机代码的特殊调用路径。将这些转换为 QCALL(本质上只是对运行时公开的本机函数的 DllImport)提高了可靠性并可能提升性能。

- **格式化改进**: `DefaultInterpolatedStringHandler` 添加了 `Text` 属性,使其他代码能够访问已格式化的文本作为 `ReadOnlySpan<char>`,避免了必须先转换为字符串的开销。

- **通用数学转换**: 大多数使用各种基元实现的通用数学接口的 `TryConvertXx` 方法被标记为 `MethodImplOptions.AggressiveInlining`,帮助 JIT 意识到它们应该总是被内联。

- **字符串插值优化**: 在处理可空输入时移除了各种空检查,削减了一些插值操作的开销。

## 结论:系统性优化的力量

.NET 10 的性能故事是关于持续的、系统性的改进。就像弗雷德里克·都德的冰块贸易帝国不是建立在单一突破性创新上,而是建立在从采收到仓储再到运输的每个环节的细致优化之上一样,.NET 10 的性能提升来自于数百个针对性的改进。这些改进涉及 JIT 编译器、核心库、网络栈、JSON 处理等各个方面。

每一项改进可能只节省几纳秒或几个字节,但当这些操作被执行数十亿次时,累积效果变得显著。更重要的是,许多改进是自动的——开发者无需更改代码就能受益。只需升级到 .NET 10,现有应用程序就能获得这些性能提升。

最令人兴奋的是,这种改进的步伐没有放缓的迹象。每个 .NET 版本都带来新的优化,使平台变得更快、更高效。对于构建高性能、可扩展、可持续和经济高效应用程序的开发者来说,.NET 10 提供了实实在在的性能优势。

建议您下载并尝试 .NET 10 RC1,在您的工作负载上运行基准测试,测量影响,并分享您的体验。无论是看到令人惊喜的性能提升,还是发现需要修复的回归,甚至是发现进一步改进的机会,都欢迎反馈、提交问题,甚至发送 PR。每一点反馈都有助于让 .NET 变得更好。

祝编码愉快!
