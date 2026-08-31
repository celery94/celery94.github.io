---
pubDatetime: 2026-08-31T09:38:27+08:00
title: ".NET 10 GC Handle：更安全的原生互操作"
description: "梳理 .NET 10 泛型 GC Handle API、.NET 9 弱内部指针句柄和 Android 双 GC 桥接机制，说明类型安全、性能收益、适用场景与生命周期风险。"
tags: [".NET", "Garbage Collection", "Interop", "Runtime"]
slug: "dotnet-gc-handle-updates"
ogImage: "../../assets/1045/01-cover.jpg"
source: "https://www.awise.us/2026/08/23/gc-handle.html"
---

把一个托管对象交给原生库时，真正棘手的是保证那个指针大小的值在原生代码使用期间仍然有效，并在结束后及时释放。

GC Handle 就是 CLR 为这类场景准备的低层机制。它在 GC 能理解的对象图之外，建立一条由运行时跟踪的引用。原生代码只保存句柄值，回到托管代码后再取回对象。

.NET 9 和 .NET 10 对这套机制做了两组很有代表性的改进：开发者获得了类型更明确的公开 API，CoreCLR 内部则增加了两种句柄，用来处理可移动对象中的地址，以及 .NET 与 Java 两套 GC 共同管理对象的难题。

## GC Handle 解决什么问题

CoreCLR 使用追踪式垃圾回收。GC 从局部变量、静态字段和运行时维护的根出发，沿引用关系找出仍然可达的对象。普通托管代码只要保持引用，运行时就能判断对象是否存活。

原生互操作会打破这个简单模型。例如，一个 C API 接收 `void* context`，稍后在回调中原样传回。这个值对 C 来说只是一串地址位，GC 无法仅凭它推断某个托管对象仍被使用。

GC Handle 提供了三个能力：

- 让托管对象在原生调用期间保持存活；
- 把句柄转换为 `IntPtr`，经过原生代码传递后再恢复；
- 在确实需要稳定地址时固定对象，阻止 GC 移动它。

句柄也带来责任。忘记释放强句柄会让对象长期存活，长时间固定对象会限制堆压缩，错误的句柄类型或并发释放还可能造成崩溃和数据损坏。

## .NET 10 把句柄语义写进类型

传统 `GCHandle` 通过 `GCHandleType` 区分普通、弱引用和固定句柄。调用方拿到的始终是同一个结构体，因此一些错误只能运行时发现。最典型的例子，是对没有固定对象的句柄调用 `AddrOfPinnedObject()`。

.NET 10 增加了几个职责分开的类型：

| 新类型               | 对应旧用法                       | 主要用途                                     |
| -------------------- | -------------------------------- | -------------------------------------------- |
| `GCHandle<T>`        | `GCHandleType.Normal`            | 强引用并以具体类型读取目标                   |
| `WeakGCHandle<T>`    | `Weak` / `WeakTrackResurrection` | 允许目标被回收，通过 `TryGetTarget` 尝试读取 |
| `PinnedGCHandle<T>`  | `GCHandleType.Pinned`            | 固定目标并取得对象数据地址                   |
| `GCHandleExtensions` | 手工处理数组或字符串地址         | 取得固定数组或字符串的数据指针               |

这种拆分带来三个直接收益。

第一，`Target` 已经是 `T`，调用方不再从 `object` 强制转换。第二，只有 `PinnedGCHandle<T>` 暴露取地址能力，很多类型不匹配可以在编译期被挡住。第三，这些结构体实现 `IDisposable`，可以用 `using` 明确限定句柄寿命。

```csharp
using System.Runtime.InteropServices;

static nint CreateContext(TextWriter writer)
{
    var handle = new GCHandle<TextWriter>(writer);
    return GCHandle<TextWriter>.ToIntPtr(handle);
}

static void WriteFromCallback(nint context, string message)
{
    var handle = GCHandle<TextWriter>.FromIntPtr(context);
    handle.Target.WriteLine(message);
}

static void ReleaseContext(nint context)
{
    var handle = GCHandle<TextWriter>.FromIntPtr(context);
    handle.Dispose();
}
```

这个简化示例刻意把创建、回调和释放分开，因为真实 C API 往往会跨越多个调用保存 context。若原生函数只在当前调用内同步使用句柄，优先把句柄放进 `using`：

```csharp
using var handle = new GCHandle<TextWriter>(Console.Out);
nint context = GCHandle<TextWriter>.ToIntPtr(handle);

NativeCall(context);
```

无论使用哪种写法，都要让释放时机与原生端最后一次使用保持一致。`Dispose` 之后继续使用旧的 `IntPtr` 属于悬空句柄；复制结构体也不会复制底层句柄资源，多个副本并发释放同一资源同样危险。

## 泛型句柄为什么还能更快

原文用 BenchmarkDotNet 比较读取旧 `GCHandle.Target` 与新 `GCHandle<T>.Target`。在作者使用 .NET 10.0.9 的机器上，新类型的平均耗时约为旧类型的 74%。这是纳秒级微基准结果，不能直接换算成应用整体提升，但它说明了 API 设计如何减少热路径上的工作。

旧 API 读取目标时需要处理未初始化句柄、清除固定标志，并把 `object` 检查和转换为目标类型。泛型句柄已经通过类型表达了这些前提，JIT 生成的核心路径可以接近一次句柄解引用。

性能优化的优先顺序仍然很清楚：先根据生命周期和是否需要稳定地址选择正确句柄，再在高频互操作路径上测量读取成本。单次回调里省下零点几纳秒，通常比不上错误固定对象、泄漏句柄或频繁跨越托管边界带来的成本。

## .NET 9 的弱内部指针句柄

公开泛型 API 解决的是开发者如何安全表达句柄意图。CoreCLR 还需要处理一个更底层的问题：原生运行时结构可能保存托管对象内部某个字段的地址，而对象会随着 GC 压缩移动。

.NET 9 加入了弱内部指针句柄 `HNDTYPE_WEAK_INTERIOR_POINTER`。它同时关联托管对象与一个位于原生或固定内存中的指针槽。对象移动后，GC 会更新这个指针槽，让它继续指向对象的新地址或对象内部的对应位置。

它是弱句柄，因此不会仅凭这条关系强行延长目标寿命。CoreCLR 最初用它维护可回收类型对应的 `MethodTable`、`MethodDesc` 等原生结构中的托管指针，随后也用于可回收程序集的静态变量内存管理。

应用代码不会直接创建这种句柄。它展示的关键设计是：当原生结构必须观察一个会移动的托管地址时，让 GC 负责更新地址，比长期固定对象更适合运行时内部的长期关系。

## .NET 10 如何协调 .NET 与 Java 两套 GC

.NET 10 为 Android 应用使用 CoreCLR 提供了实验支持。这个场景有两套相互独立的垃圾回收器：CoreCLR 只能看到 .NET 对象图，Java GC 只能看到 Java 对象图，而一个业务对象可能在两边各有一个互操作实例。

最直观的做法，是让 .NET 句柄强引用 .NET 对象，再用 JNI global reference 强引用 Java 对象。这样双方都一直存活；当两个对象只剩下彼此关联、外部已经无法访问时，两套 GC 仍会认为它们活着，形成跨堆循环泄漏。

.NET 10 新增的交叉引用句柄 `HNDTYPE_CROSSREFERENCE` 让两边共同完成判断。一次桥接处理大致经历以下步骤：

1. CoreCLR 找出仅靠交叉引用句柄存活的 .NET 对象，并暂时延长它们的寿命。
2. 运行时把相关 .NET 对象图压缩为强连通分量，再把必要关系映射到配对的 Java 对象。
3. Java 侧把 global reference 临时降为弱引用，并触发 Java GC。
4. 仍能从任一堆外部到达的 Java 对象继续存活，弱引用随后恢复为强引用。
5. 两边都不可达的配对对象释放交叉引用句柄，对应 .NET 对象可在后续 GC 中回收。

强连通分量的作用是把彼此循环引用的一组 .NET 对象当作一个整体处理，只把分量之间真正影响可达性的边复制到 Java 侧。这样无需完整复制整个 .NET 堆，也能让 Java GC 参与最终判断。

这套机制属于运行时和 Android 互操作层的实现细节。Microsoft Learn 目前仍把 Android 上的 CoreCLR 标为实验功能，并明确提示应用体积、调试和部分诊断能力仍有限，不建议用于生产环境。

## 选择句柄时看三件事

日常开发很少需要直接使用 GC Handle。P/Invoke 能在调用期间自动固定或复制参数时，交给 marshaller 通常更安全。只有原生代码要跨调用保存托管上下文、需要长期回调，或 API 明确要求稳定数据地址时，才值得直接管理句柄。

可以按三个问题选择：

1. 目标是否必须保持存活？需要就用 `GCHandle<T>`；允许回收就考虑 `WeakGCHandle<T>`。
2. 原生端是否必须持有对象数据地址？只有确实需要稳定地址时才用 `PinnedGCHandle<T>`，并尽量缩短固定时间。
3. 谁知道原生端已经用完？由这一方负责触发唯一一次释放，并确保之后没有回调。

还要保留几条安全边界：

- 不要从任意整数恢复句柄，也不要用错误的泛型或句柄类型解释同一个值；
- 不要假设 `Dispose` 可以与读取或另一次释放安全并发；
- 弱句柄读取成功后，应使用返回的强局部引用完成当前操作，避免再次读取时目标已经变化；
- 固定对象会影响 GC 移动和压缩，长期缓冲区可评估非托管内存或专门的固定对象堆策略；
- 微基准只证明具体读取路径的差异，应用级收益需要按真实回调频率重新测量。

.NET 10 的泛型句柄让强、弱、固定三种语义更清楚，也把资源释放纳入 `using` 能表达的范围。两个内部句柄则揭示了 GC 的另一面：当普通对象引用无法描述地址更新或跨运行时生命周期时，新的句柄类型可以给收集器增加一套精确规则。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践。

## 参考

- [Austin Wise：What's new with CoreCLR GC handles in .NET 9 and .NET 10](https://www.awise.us/2026/08/23/gc-handle.html)
- [Microsoft Learn：GCHandle<T>](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.gchandle-1?view=net-10.0)
- [Microsoft Learn：WeakGCHandle<T>](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.weakgchandle-1?view=net-10.0)
- [Microsoft Learn：PinnedGCHandle<T>](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.pinnedgchandle-1?view=net-10.0)
- [dotnet/runtime：GCHandle<T> API proposal](https://github.com/dotnet/runtime/issues/94134)
- [dotnet/runtime：Weak interior pointer handle](https://github.com/dotnet/runtime/pull/100446)
- [dotnet/runtime：Cross-reference handles](https://github.com/dotnet/runtime/pull/116310)
- [Microsoft Learn：.NET MAUI for .NET 10 中的实验性 CoreCLR](https://learn.microsoft.com/en-us/dotnet/maui/whats-new/dotnet-10?view=net-maui-10.0#experimental-coreclr)
