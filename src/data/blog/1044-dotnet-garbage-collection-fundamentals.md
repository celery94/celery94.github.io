---
pubDatetime: 2026-08-31T09:30:31+08:00
title: ".NET GC 基础：栈、堆、代际与压缩"
description: "从对象分配和一次垃圾回收过程出发，解释 .NET 托管堆、GC Roots、标记与压缩、Gen 0 到 Gen 2、LOH 和后台 GC，并纠正值类型必在栈上、每次收集都会完整压缩等常见误解。"
tags: [".NET", "Garbage Collection", "Memory", "Performance"]
slug: "dotnet-garbage-collection-fundamentals"
ogImage: "../../assets/1044/01-cover.jpg"
source: "https://ilovedotnet.org/blogs/garbage-collection-fundamentals-in-dotnet/"
---

服务运行数小时后，内存从 300 MB 涨到 1.2 GB。看到这条曲线时，很多人会立刻判断“GC 没有回收”。这个结论往往太早：对象不可达、托管堆回收、进程提交内存下降和操作系统回收物理页，是四个不同阶段。

理解 .NET 内存问题，需要先回答三个问题：对象实际存放在哪里，GC 如何判断对象仍然有用，回收后的空间怎样再次用于分配。

I Love DotNet 的 Garbage Collection Fundamentals 文章用栈、堆、虚拟内存以及标记、回收、压缩解释了基础过程。本文沿用这条主线，并补充几个影响排错的关键边界。

## 栈与托管堆承担不同职责

线程栈由一组 stack frame（栈帧）组成。方法调用时创建栈帧，返回时整体移除。局部变量、参数、返回地址和运行时维护的数据都可能出现在栈帧中，具体布局受 JIT 优化和平台调用约定影响。

托管堆保存由 CLR 管理的对象。常见 `class` 实例、数组、字符串和装箱后的值会分配在托管堆上。新对象通常从当前分配区域的空闲位置顺序取得空间，这条快路径接近移动指针，并不需要每次都在大量空洞中搜索。

一个常见教学说法是“值类型在栈上，引用类型在堆上”。它能帮助第一次理解复制行为，却无法准确描述存储位置。

值类型表示变量直接包含其数据，实际位置取决于它属于谁：

- 方法中的普通局部值可能放在栈上，也可能被 JIT 放进寄存器；
- `class` 的值类型字段跟随所属对象位于托管堆；
- 值类型数组的元素位于数组对象内部，也在托管堆；
- 值被装箱、闭包捕获或异步状态机提升后，可能进入堆对象。

引用类型变量保存的是引用。局部引用可能在栈或寄存器中，引用指向的对象位于托管堆。判断复制语义时看类型，判断存储位置时看上下文。

## 值复制与引用复制

值类型赋值会复制该值当前包含的数据。修改副本不会改变原变量：

```csharp
int handled = 250;
int checkpoint = handled;

handled = 0;
Console.WriteLine(checkpoint); // 250
```

引用类型赋值复制引用，两个变量随后指向同一个对象：

```csharp
public sealed class Invoice
{
    public decimal Amount { get; set; }
}

var invoice = new Invoice { Amount = 500m };
var copy = invoice;

invoice.Amount = 0m;
Console.WriteLine(copy.Amount); // 0
```

结构体若包含引用字段，复制结构体时也会复制该引用。两个结构体副本可以拥有独立的数值字段，同时指向同一个引用对象。`ref`、`in` 和 `out` 又会改变默认传递方式，因此“struct 永远完全独立”同样过于绝对。

## GC 从根开始寻找存活对象

GC 不需要判断业务上还会不会使用某个对象。它使用可达性规则：只要能从一组 GC Roots 沿引用路径到达对象，该对象就被视为存活。

常见根包括：

- JIT 报告的活动栈变量和 CPU 寄存器中的引用；
- 静态字段引用的对象；
- CLR 与用户代码创建的 GC handles；
- 与终结器处理相关的运行时引用。

假设根能到达 A，A 引用 C，C 又引用 E，那么 A、C、E 都存活。与任何根都没有路径的 F 即使内部仍有完整数据，也已经符合回收条件。

```text
GC Roots
  ├─ A ─ C ─ E   存活
  └─ B ─ D       存活

F、G             不可达
```

“符合回收条件”并不等于立即释放。GC 会根据分配量、各代阈值、内存压力和运行模式决定收集时机。

## 一次收集包含标记、规划与移动

从概念上看，回收过程可以分成三个动作。

### 标记存活对象

GC 暂停需要协调的托管线程，从 roots 遍历对象图，找出仍然可达的对象。JIT 提供精确的引用位置，因此 GC 可以区分普通数值与对象引用。

### 规划回收结果

不可达对象占用的区域可以重新使用。GC 会决定哪些对象需要移动、哪些引用需要更新，以及收集完成后的新布局。对于采用 sweep 的区域，空闲块会进入可重用列表。

### 移动并压缩

在适合压缩的托管堆区域，存活对象向连续方向移动，运行时同时更新所有相关引用。压缩消除存活对象之间的空洞，也让后续分配继续使用快速的顺序分配。

```text
收集前：A | 空 | B | 空 | C
压缩后：A | B  | C | 连续空闲区
```

“标记、回收、压缩”适合作为理解框架，实际实现更细致。并非每次 GC 都会移动整个托管堆，收集范围可能只覆盖年轻代，LOH 通常使用 sweep，固定对象也会限制可移动范围。

## 代际 GC 缩小常见收集范围

.NET 根据“多数对象寿命很短”的经验，把小对象堆分成三代：

- Gen 0：新分配的对象，收集最频繁；
- Gen 1：在 Gen 0 收集中存活的对象，承担缓冲作用；
- Gen 2：存活时间更长的对象，收集成本通常更高。

一次 Gen 0 收集只需处理年轻区域，无需反复扫描全部长期存活对象。对象在收集中存活后会被提升，直到进入 Gen 2。Gen 2 对象继续存活时仍留在 Gen 2。

代数描述的是相对年龄和收集范围，不能直接代表业务重要性。一个刚创建的大缓存仍是新对象，一个早已失去价值但仍被静态集合引用的对象可以长期留在 Gen 2。

## LOH 为大对象选择不同取舍

在 Windows 上，大小达到或超过 85,000 字节的对象通常进入 Large Object Heap（大对象堆，LOH）。复制大对象成本高，因此 LOH 一般通过 sweep 形成空闲列表，不像小对象堆那样在每次相关收集中进行常规压缩。

这带来两个实际影响：

- 大数组和大字符串的分配需要清零较多内存，本身就有成本；
- 大对象频繁分配和释放可能造成 LOH 空洞，并触发与 Gen 2 相关的昂贵收集。

需要时，可以把 `GCSettings.LargeObjectHeapCompactionMode` 设置为 `CompactOnce`，让下一次完整阻塞收集压缩 LOH。它适合经过测量后处理特定碎片问题，不应放进普通请求路径反复调用。

官方文档还说明，在容器内存硬限制等配置下，运行时可能自动压缩 LOH。LOH 行为具有平台和运行时版本差异，排查时应记录实际 .NET 版本与 GC 配置。

## Stop-the-World 不代表全部 GC 工作都阻塞应用

GC 移动对象或执行需要一致引用视图的阶段时，会暂停托管线程，这就是 Stop-the-World。暂停让应用线程无法在对象移动过程中继续使用旧地址。

现代 .NET 默认支持后台 GC。后台 Gen 2 收集的大部分工作可以在专用线程上与应用并行；期间若 Gen 0 或 Gen 1 空间不足，运行时仍可以执行前台年轻代收集。前台收集会暂停托管线程。

因此，分析 GC 不能只看“发生了几次”。更有用的指标包括：

- 各代收集次数与暂停总时长；
- 每秒分配字节和分配热点；
- GC 后存活堆大小；
- Gen 2 与 LOH 大小、碎片和固定对象；
- Server GC、Workstation GC 与后台 GC 配置；
- 暂停是否落在请求延迟高峰。

## 虚拟内存解释了进程内存曲线

托管堆位于进程的虚拟地址空间中。操作系统把虚拟页映射到物理内存或其他后备存储，每个进程看到独立的地址空间。

GC 回收对象后，CLR 可以立即复用相应托管堆空间，但不保证马上把所有已提交页面归还操作系统。因此：

- 托管堆中对象减少，进程 Working Set 可能暂时不变；
- 进程保留一段虚拟地址空间，不代表等量物理内存一直驻留；
- Working Set 下降，也可能来自操作系统换出冷页，而非 GC 消除了对象。

排查内存增长时，应把托管堆大小、Committed Bytes、Working Set、Private Bytes 和容器限制分开观察。只看任务管理器中的单条曲线很难定位根因。

## GC 不负责及时关闭外部资源

文件句柄、Socket、数据库连接和原生内存不属于普通托管内存。包装它们的托管对象即使已经不可达，也要等 GC 与终结器调度后才可能释放底层资源。

需要及时释放的资源应实现 `IDisposable` 或 `IAsyncDisposable`，由 `using` 或 `await using` 建立确定的生命周期：

```csharp
await using var connection = new SqlConnection(connectionString);
await connection.OpenAsync();

// 使用连接
```

`Dispose` 负责按时结束资源使用，GC 负责回收托管对象占用的内存。两者解决的问题不同。

## 一份排错顺序

遇到 .NET 内存或 GC 问题时，可以按以下顺序收集证据：

1. 确认运行时版本、Server/Workstation GC、后台 GC 和容器内存限制。
2. 用 `dotnet-counters` 观察分配速率、各代收集和托管堆大小。
3. 在稳定复现点采集 `dotnet-gcdump` 或 dump，比较对象类型、数量和保留路径。
4. 检查静态集合、事件订阅、缓存、计时器和长期任务形成的 GC roots。
5. 单独查看 LOH、固定对象和大型数组池的使用方式。
6. 对比 GC 暂停与业务延迟时间线，确认相关性后再优化。
7. 避免把 `GC.Collect()` 当作常规修复；强制完整收集可能增加暂停，也无法清除仍然可达的对象。

一个实用判断是：对象数量持续增长且存在不需要的保留路径，重点查引用关系；对象能被回收但分配速率过高，重点减少短命分配；托管堆稳定而进程内存仍高，再检查原生内存、线程栈、JIT、映射文件和操作系统页面行为。

.NET GC 的核心规则并不复杂：从 roots 判断可达性，优先回收年轻对象，在必要区域移动存活对象，并根据内存压力调节收集频率。真正影响排错质量的，是把类型语义、存储位置、托管堆、进程虚拟内存和外部资源分开观察。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践。

## 参考

- [I Love DotNet：Garbage Collection Fundamentals in .NET](https://ilovedotnet.org/blogs/garbage-collection-fundamentals-in-dotnet/)
- [Microsoft Learn：Fundamentals of garbage collection](https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/fundamentals)
- [Microsoft Learn：Automatic Memory Management](https://learn.microsoft.com/en-us/dotnet/standard/automatic-memory-management)
- [Microsoft Learn：The large object heap on Windows systems](https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/large-object-heap)
- [Microsoft Learn：Background garbage collection](https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/background-gc)
- [Microsoft Learn：Garbage collector configuration settings](https://learn.microsoft.com/en-us/dotnet/core/runtime-config/garbage-collector)
- [Microsoft Learn：C# value types](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/builtin-types/value-types)
