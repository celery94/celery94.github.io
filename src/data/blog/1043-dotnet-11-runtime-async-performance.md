---
pubDatetime: 2026-08-31T09:24:36+08:00
title: ".NET 11 Runtime Async：异步为何更快"
description: "解析 .NET 11 Runtime Async 如何把异步控制流交给运行时和 JIT，减少同步完成路径上的状态机与对象分配，并结合作者微基准、官方 Preview 7 数据和启用方式说明性能收益、适用场景与预览限制。"
tags: [".NET 11", "C#", "Runtime Async", "Performance"]
slug: "dotnet-11-runtime-async-performance"
ogImage: "../../assets/1043/01-cover.jpg"
source: "https://medium.com/@skyake/how-fast-is-net-11-runtime-async-b9c821529cd5"
---

一个 `async` 方法可能从头到尾都没有真正暂停：缓存已经命中，`Task` 已经完成，调用链只是把结果向上传递。传统实现仍可能为这段代码准备状态机、awaiter 和返回对象。

.NET 11 的 Runtime Async 尝试把这笔成本推迟到真正发生暂停的时刻。同步完成的调用尽量像普通方法一样直接返回；遇到未完成的 `await` 后，运行时才保存恢复所需的状态。

Kai Sawano 的文章用生成代码和微基准展示了这条新路径。结合 .NET 官方文档可以得到一个更稳妥的结论：Runtime Async 对同步完成、调用层级深的异步代码最有吸引力，但它仍是预览功能，19.63× 等数字只能说明特定微基准中的上限，不能直接换算成应用吞吐量。

## 传统 async 把控制流提前拆开

C# 编译器通常会把 `async` 方法改写成状态机。每个可能暂停的位置对应一个状态，`MoveNext()` 负责继续执行，method builder 负责创建并完成对外返回的 `Task` 或 `ValueTask`。

```csharp
public async Task<int> GetValueAsync()
{
    await Task.Delay(1000);
    return 42;
}
```

概念上，它会变成以下流程：

```text
调用 MoveNext
  ├─ await 尚未完成：保存状态并注册 continuation
  └─ await 已经完成：继续执行并完成结果
```

这套模型让异步代码保持顺序写法，成熟且可靠。它也让 JIT 接手时看到的代码已经是 `MoveNext()`、awaiter 和 method builder 之间的协作，原始调用关系被拆散。大型 `MoveNext()` 难以内联，跨多个异步方法的同步快路径也较难一起优化。

成本在真正等待网络或磁盘时通常不突出，因为 I/O 延迟远高于几个对象和分支。缓存命中、已完成 `Task`、深层包装方法和高频短操作会把这部分固定开销放大。

`ValueTask`、任务缓存和手工消除多余 `async` 已经可以降低部分分配。它们需要开发者在 API 和代码结构上主动选择，JIT 仍缺少完整的原始异步控制流。

## Runtime Async 把暂停交给运行时

Runtime Async 保留熟悉的 C# 写法，编译结果和调用约定发生变化。方法在 IL 中标记为异步方法，`await` 通过 `AsyncHelpers` 表达，JIT 能直接看到原始控制流。

新的 Async Calling Convention 在普通参数之外传递一个 `Continuation`，返回时也多出一条 continuation 通道：

```text
(result, continuation) = Method(continuation, args)
```

第一次调用时，`continuation` 为 `null`。如果整个调用同步完成，方法直接返回结果和 `null`，调用者可以继续执行。目标架构允许时，普通结果与 continuation 分别通过寄存器传递。

遇到未完成的 await 后，JIT 才创建 continuation，保存跨暂停点仍然存活的局部变量、恢复位置以及结果或异常。待操作完成，运行时带着 continuation 再次进入方法，从保存位置继续。

这形成了清楚的按需成本：

```text
同步完成：直接返回结果，continuation = null
发生暂停：分配 continuation，保存必要状态，稍后恢复
```

对外部普通 C# 调用者，方法仍表现为 `Task<T>` 或 `ValueTask<T>`。运行时使用 thunk（薄适配层）连接普通调用约定与异步调用约定。若 JIT 能把适配层内联并证明对象不会逃逸，更多包装成本也有机会消失。

## 作者的基准测到了什么

原文比较了写作时最新的 .NET 11 日构建 Runtime Async（Async2）与 .NET 10 传统 async（Async1）。预热后，每项执行 1 亿次。结果如下：

| 场景                              | Runtime Async 相对传统 async 的速度 |
| --------------------------------- | ----------------------------------: |
| async 方法，不暂停                |                              19.63× |
| await 已完成的 Task               |                              12.02× |
| await 已完成的 ValueTask          |                               2.25× |
| `Task.Yield` 暂停                 |                               7.00× |
| ThreadPool continuation           |                               3.17× |
| TaskCompletionSource continuation |                               3.99× |
| 深层 async 状态机链               |                               7.40× |

分配结果也支持同一判断。作者测试中的“不暂停 async 方法”和“已完成 Task”从每次 72 B 降到 0 B；深层异步链从 301 B 降到 192 B。ThreadPool continuation 只从 160 B 降到 152 B，TaskCompletionSource 场景仍为 160 B。

这些数字最能说明同步快路径和深层调用链的潜力。它们还包含几个重要限制：

- 比较跨越 .NET 10 与 .NET 11，除 Runtime Async 外还可能包含其他运行时改进；
- 每项重复 1 亿次，固定开销比真实 I/O 更容易成为主角；
- Fibonacci 和已完成任务适合观察调用成本，无法代表数据库、HTTP 和消息处理的端到端延迟；
- 日构建仍在快速变化，结果会随 JIT、运行时和硬件更新。

因此，19.63× 应看作特定同步完成微基准的结果。一个请求若主要等待 20 毫秒数据库查询，即使 async 框架成本缩短几十纳秒，用户看到的总延迟也不会缩短 19 倍。

## 官方 Preview 7 数据给出了交叉证据

.NET 11 Preview 7 的运行时发布说明记录了相似方向的改进：

- 对已完成 `Task` 连续 await 1 亿次的紧密循环，从约 191 ms 降到约 32 ms；
- `await Task.Yield()` 循环 1000 万次，从约 723 ms 降到约 534 ms；
- async 版本进入分层编译，热方法可以得到 Tier 1 优化；
- JIT 识别 `Task.FromResult`、`Task.CompletedTask` 和常见 `ValueTask` 工厂，折叠更多快路径；
- 尾部 await、continuation 缓存和无效 `ExecutionContext` 恢复继续减少开销。

官方数字同样来自针对单一行为的基准。它们证明具体优化已经进入产品代码，也提醒我们收益会随暂停方式变化：已完成 Task 的快路径改善明显，真正调度和恢复的 `Task.Yield` 改善相对温和。

## 当前如何启用

截至 2026 年 8 月，Runtime Async 是 .NET 11 的预览功能。`net11.0` 项目可以在项目文件中显式开启：

```xml
<PropertyGroup>
  <TargetFramework>net11.0</TargetFramework>
  <Features>runtime-async=on</Features>
</PropertyGroup>
```

官方文档说明，`net11.0` 项目不再需要额外设置 `EnablePreviewFeatures`。旧的 `DOTNET_RuntimeAsync` 和 `UNSUPPORTED_RuntimeAsync` 环境变量已经移除。若需要在项目级关闭，可设置：

```xml
<PropertyGroup>
  <UseRuntimeAsync>false</UseRuntimeAsync>
</PropertyGroup>
```

.NET 运行库自身已用 `runtime-async=on` 编译，这给功能兼容性和性能提供了大范围验证。应用项目仍需主动开启，预览阶段不宜在缺少回归测试的生产系统中直接切换。

Runtime Async 当前面向 `Task`、`Task<T>`、`ValueTask` 和 `ValueTask<T>`。规范草案仍列出 by-ref、异常处理块中的暂停点等限制，工具链和诊断支持也在继续完善。

## 哪些项目值得优先测试

以下特征越明显，Runtime Async 越值得建立对照实验：

- 大量 async API 经常从缓存或内存同步完成；
- 调用链有多层只负责转发结果的异步包装；
- 每个请求包含许多短小 await，吞吐量受 CPU 和分配影响；
- Gen0、Task 分配或 async 状态机出现在性能剖析热点中；
- 需要更清楚的实时调用栈用于 profiler、调试器或诊断日志。

主要耗时来自远程 I/O、业务算法或锁竞争时，应先处理真正的瓶颈。Runtime Async 也无法消除必须发生的暂停、线程池排队和 `ExecutionContext` 中确实需要传递的状态。

## 用 A/B 测试判断真实收益

评估时，准备两个 Release 构建：一个开启 Runtime Async，一个设置 `UseRuntimeAsync=false`。保持 SDK、运行时、机器、启动参数和流量完全一致，再比较：

1. 业务端到端吞吐量与 P50、P95、P99 延迟；
2. 每次请求分配量、Gen0 频率和 GC 暂停；
3. CPU profile 中 async thunk、continuation 和任务相关热点；
4. 冷启动、预热过程和稳定运行后的差异；
5. 异常、取消、`AsyncLocal`、自定义 awaiter、NativeAOT 与 ReadyToRun 路径；
6. 依赖库混用传统 async 和 Runtime Async 时的行为。

微基准可以确认某条路径是否变快，生产决策需要业务负载。若吞吐量改善小于测量噪声，继续使用默认实现更稳妥；若分配和 CPU 热点明显下降，再扩大测试范围。

Runtime Async 的关键变化很克制：保留原始异步控制流，让 JIT 看见同步快路径，并在真实暂停时才保存状态。它让 async 更接近按实际使用付费，也把优化从开发者手工选择 `ValueTask` 和消除包装，推进到运行时可以统一处理的层面。现阶段最合适的动作是用 .NET 11 预览版建立 A/B 数据，持续关注兼容性与正式发布状态。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践。

## 参考

- [Kai Sawano：How Fast is .NET 11 Runtime Async?](https://medium.com/@skyake/how-fast-is-net-11-runtime-async-b9c821529cd5)
- [Kai Sawano：Runtime Async Benchmark Gist](https://gist.github.com/hez2010/d1802e7c7ab10e21a92dcba2afe0a58d)
- [Microsoft Learn：What's new in the .NET 11 runtime](https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/runtime)
- [.NET：.NET 11 Preview 7 Runtime Release Notes](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/preview7/runtime.md)
- [.NET Runtime：Runtime Async specification draft](https://github.com/dotnet/runtime/blob/main/docs/design/specs/runtime-async.md)
- [.NET Runtime：CLR ABI async calling convention](https://github.com/dotnet/runtime/blob/main/docs/design/coreclr/botr/clr-abi.md#async)
