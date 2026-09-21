---
pubDatetime: 2026-09-21T08:36:00+08:00
title: "TPL Dataflow 流水线要写对生命周期"
description: "大多数 Dataflow 示例只把三个块 LinkTo 起来就结束。把容量、并发与顺序、完成传播、故障与取消这四项配齐，才是一条调用方敢持有的流水线；文末另附背压语义与版本核对结论。"
tags: ["TPL Dataflow", ".NET 10", "C# 14", "并发", "Pipeline Pattern"]
slug: "build-a-tpl-dataflow-pipeline-in-modern-net"
ogImage: "../../assets/1077/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/19/build-a-tpl-dataflow-pipeline-in-modern-net"
---

`LinkTo` 连接两个块，只要一行。可当订单卡在中间、Ctrl+C 之后进程不肯退出、或者取消之后你只拿到一个 `TaskCanceledException` 而不知道哪一步真的坏了，问题都不在 `LinkTo` 上。

Nick Cosentino 在 [Build a TPL Dataflow Pipeline in Modern .NET](https://www.devleader.ca/2026/09/19/build-a-tpl-dataflow-pipeline-in-modern-net) 里给出的判断是：块的拓扑结构只是骨架，真正需要提前写下来的是**生命周期**——容量、并发与顺序、完成传播、故障与取消。他的示例在 .NET 10 上用三个块组成一条线性流水线，然后把这四个决策逐个显式写进代码。

原文的示例可以直接跑，也把决策讲清楚了。下面的重述会在两处补上原文没有展开的部分：一是 `SendAsync` 返回 `false` 的语义边界，二是这个包在 .NET 10 里其实已经内置，固定版本的真正理由和版本现状。

## TPL Dataflow 该用在哪

架构层面的 Pipeline Pattern 比任何一个库都宽泛，它描述的是带有明确输入输出契约的有序阶段。TPL Dataflow 只是其中一种实现：让每个阶段拥有独立的调度策略和可配置的消息流。

官方文档把数据流块分成三类：

- **执行块**运行委托。`TransformBlock<TInput,TOutput>` 产生输出，`ActionBlock<TInput>` 是终点消费者。
- **缓冲块**保留并暴露消息，不做常规变换。
- **分组块**把消息合并成批次或集合。

原文的示例只用了两个 transform 加一个 action。这个规模足够展示真实结构，又不会把例子变成分支工作流——分支、谓词、连接和动态链接都会带来更多归属问题，在工作负载真正需要之前，线性图更划算。

选择依据可以简化成一句话：**当每个阶段需要不同的容量或不同的并发度时，Dataflow 才值回它多出来的那层生命周期管理成本**。小的顺序变换直接用方法组合更清楚；一进一出的一次交接，有界 Channel 就够了。原文的观点是，如果块级配置和显式链接能让处理模型更容易理解，这笔开销就值得。

## 环境与版本

示例面向 .NET 10 与 C# 14（.NET 10 于 2025-11-11 发布，是 LTS）。这里有一个容易误导人的细节需要先说清楚。

.NET 官方文档的安装说明写明：**TPL Dataflow（`System.Threading.Tasks.Dataflow` 命名空间）自 .NET 6 起已包含在框架内**，只有 .NET Framework 和 .NET Standard 项目才需要安装 [System.Threading.Tasks.Dataflow NuGet 包](https://www.nuget.org/packages/System.Threading.Tasks.Dataflow)。所以在 .NET 10 上你什么都不装也能写这段代码。

原文仍然显式固定包版本，目的是让示例可复现，并且排除 11.0 预览线。这不是错误，但要理解它的实际含义：一旦引用这个包，包内的程序集就会覆盖共享框架里的版本，你确实拿到了自己钉住的那一份。

版本现状（2026-09-21 核对）：

| 版本        | 状态                                      |
| ----------- | ----------------------------------------- |
| 10.0.10     | 原文钉住的版本，2026-07-15 发布           |
| 10.0.11     | 2026-08-12 发布                           |
| 10.0.12     | 目前最新的 10.0.x 稳定版，2026-09-09 发布 |
| 11.0.0-rc.1 | 预览线，2026-09-09 发布，示例明确排除     |

也就是说原文钉的版本仍然有效，只是不再是该线的最新补丁；生产项目照常走依赖审查流程升级即可，需要预览特性时再单独评估风险。

工程文件：

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <LangVersion>14.0</LangVersion>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference
      Include="System.Threading.Tasks.Dataflow"
      Version="10.0.10" />
  </ItemGroup>

</Project>
```

## 先定契约，再搭块

示例处理的是一条小订单路径：归一化入站订单、异步补充风控信息、在终点写入回执。

原文把可运营的决策单独列成表，而不是散落在构造函数里：

| 决策       | 示例取值                                 | 理由                             |
| ---------- | ---------------------------------------- | -------------------------------- |
| 容量       | 每个块都给正的有界容量                   | 避免进程内无上限堆积             |
| 归一化并发 | 2                                        | 演示同步变换里的条目并发         |
| 补全并发   | 4                                        | 允许多个独立异步调用重叠         |
| 终点并发   | 1                                        | 让终点副作用串行                 |
| 顺序       | 每个块 `EnsureOrdered = true`            | 保持变换输出的发布顺序           |
| 取消       | 每个块与每次发送共用同一个链接令牌       | 调用方取消或块故障后释放挂起工作 |
| 链接完成   | `PropagateCompletion = true`             | 让正常完成与故障穿过线性图       |
| 入站       | 检查过的 `SendAsync`                     | 观察背压、取消与拒绝             |
| 关闭       | 头部 `Complete()`，等待终点 `Completion` | 排空已接受的工作并观察图的结果   |

这些值是示例输入，不是通用调参建议。容量 16、并发 4 对于大消息、稀缺的下游连接池或 CPU 密集的委托都可能不合适。**重点在于这条流水线把决策暴露出来，而不是依赖默认值**。

把策略命名成独立类型，比把字面量撒进各个块构造函数更容易被测试和诊断复用：

```csharp
using System.Threading.Tasks.Dataflow;

namespace ModernDataflowPipeline;

public sealed record DataflowStageSettings(
    int BoundedCapacity,
    int MaxDegreeOfParallelism,
    bool EnsureOrdered)
{
    public ExecutionDataflowBlockOptions CreateOptions(
        CancellationToken cancellationToken)
    {
        if (BoundedCapacity <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(BoundedCapacity));
        }

        if (MaxDegreeOfParallelism <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(MaxDegreeOfParallelism));
        }

        return new ExecutionDataflowBlockOptions
        {
            BoundedCapacity = BoundedCapacity,
            MaxDegreeOfParallelism =
                MaxDegreeOfParallelism,
            EnsureOrdered = EnsureOrdered,
            CancellationToken = cancellationToken
        };
    }
}
```

它不负责选出正确的数值，只是给配置、测试和诊断一个显式表示。链接完成保留在图这一层，因为它描述的是块之间的关系，而不是单个阶段的执行策略。

## 完整的有界流水线

下面是原文的 `Program.cs`。消息用不可变 record，但 record 里只放值类型成员；如果消息携带可变集合或需要释放的资源，流水线还得额外定义归属与清理规则。

```csharp
using System.Collections.Concurrent;
using System.Runtime.ExceptionServices;
using System.Runtime.CompilerServices;
using System.Threading.Tasks.Dataflow;

namespace ModernDataflowPipeline;

public sealed record RawOrder(
    int Id,
    string Customer,
    decimal Amount);

public sealed record NormalizedOrder(
    int Id,
    string Customer,
    decimal Amount);

public sealed record EnrichedOrder(
    int Id,
    string Customer,
    decimal Amount,
    string RiskBand);

public sealed record OrderReceipt(
    int Id,
    string Customer,
    decimal Amount,
    string RiskBand,
    DateTimeOffset PersistedAt);

public static class Program
{
    public static async Task Main()
    {
        using var shutdown = new CancellationTokenSource();

        ConsoleCancelEventHandler cancelHandler = (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            shutdown.Cancel();
        };

        Console.CancelKeyPress += cancelHandler;

        try
        {
            IReadOnlyList<OrderReceipt> receipts =
                await OrderDataflowPipeline.RunAsync(
                    orderCount: 50,
                    shutdown.Token);

            Console.WriteLine(
                $"Persisted {receipts.Count} receipts.");
        }
        catch (OperationCanceledException)
            when (shutdown.IsCancellationRequested)
        {
            Console.WriteLine("Pipeline cancellation was requested.");
        }
        finally
        {
            Console.CancelKeyPress -= cancelHandler;
        }
    }
}

public static class OrderDataflowPipeline
{
    public static async Task<IReadOnlyList<OrderReceipt>> RunAsync(
        int orderCount,
        CancellationToken cancellationToken,
        int? normalizeFailureId = null,
        int? enrichFailureId = null)
    {
        using var pipelineCancellation =
            CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken);

        CancellationToken pipelineToken =
            pipelineCancellation.Token;

        var receipts = new ConcurrentQueue<OrderReceipt>();

        var normalize = new TransformBlock<RawOrder, NormalizedOrder>(
            order => Normalize(order, normalizeFailureId),
            new ExecutionDataflowBlockOptions
            {
                BoundedCapacity = 16,
                MaxDegreeOfParallelism = 2,
                EnsureOrdered = true,
                CancellationToken = pipelineToken
            });

        var enrich = new TransformBlock<NormalizedOrder, EnrichedOrder>(
            order => EnrichAsync(
                order,
                enrichFailureId,
                pipelineToken),
            new ExecutionDataflowBlockOptions
            {
                BoundedCapacity = 8,
                MaxDegreeOfParallelism = 4,
                EnsureOrdered = true,
                CancellationToken = pipelineToken
            });

        var persist = new ActionBlock<EnrichedOrder>(
            async order =>
            {
                await Task.Delay(
                    TimeSpan.FromMilliseconds(5),
                    pipelineToken);

                receipts.Enqueue(
                    new OrderReceipt(
                        order.Id,
                        order.Customer,
                        order.Amount,
                        order.RiskBand,
                        DateTimeOffset.UtcNow));
            },
            new ExecutionDataflowBlockOptions
            {
                BoundedCapacity = 8,
                MaxDegreeOfParallelism = 1,
                EnsureOrdered = true,
                CancellationToken = pipelineToken
            });

        var linkOptions = new DataflowLinkOptions
        {
            PropagateCompletion = true
        };

        using IDisposable normalizeToEnrich =
            normalize.LinkTo(enrich, linkOptions);

        using IDisposable enrichToPersist =
            enrich.LinkTo(persist, linkOptions);

        var firstFault =
            new TaskCompletionSource<ExceptionDispatchInfo>(
                TaskCreationOptions.RunContinuationsAsynchronously);

        Task[] completionMonitors =
        [
            MonitorCompletionAsync(
                normalize.Completion,
                firstFault,
                pipelineCancellation,
                cancellationToken),
            MonitorCompletionAsync(
                enrich.Completion,
                firstFault,
                pipelineCancellation,
                cancellationToken),
            MonitorCompletionAsync(
                persist.Completion,
                firstFault,
                pipelineCancellation,
                cancellationToken)
        ];

        try
        {
            await foreach (RawOrder order in ReadOrdersAsync(
                orderCount,
                pipelineToken))
            {
                bool accepted = await normalize.SendAsync(
                    order,
                    pipelineToken);

                if (!accepted)
                {
                    try
                    {
                        await normalize.Completion;
                    }
                    catch
                    {
                    }

                    if (firstFault.Task.IsCompletedSuccessfully)
                    {
                        ExceptionDispatchInfo rejectionFault =
                            await firstFault.Task;
                        rejectionFault.Throw();
                    }

                    throw new InvalidOperationException(
                        "The head block declined an order.");
                }
            }

            normalize.Complete();

            await persist.Completion;
            await Task.WhenAll(completionMonitors);

            return receipts.ToArray();
        }
        catch (Exception caught)
        {
            ExceptionDispatchInfo caughtFault =
                ExceptionDispatchInfo.Capture(caught);

            pipelineCancellation.Cancel();
            normalize.Complete();

            await ObserveAllCompletionsAsync(
                normalize.Completion,
                enrich.Completion,
                persist.Completion);

            await Task.WhenAll(completionMonitors);

            if (firstFault.Task.IsCompletedSuccessfully)
            {
                ExceptionDispatchInfo originalFault =
                    await firstFault.Task;
                originalFault.Throw();
            }

            caughtFault.Throw();
            throw new InvalidOperationException("Unreachable.");
        }
        finally
        {
            pipelineCancellation.Cancel();
        }
    }

    private static NormalizedOrder Normalize(
        RawOrder order,
        int? failureId)
    {
        if (order.Id == failureId)
        {
            throw new InvalidDataException(
                $"Normalize failed for order {order.Id}.");
        }

        ArgumentException.ThrowIfNullOrWhiteSpace(order.Customer);

        if (order.Amount <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(order),
                "Order amount must be positive.");
        }

        return new NormalizedOrder(
            order.Id,
            order.Customer.Trim(),
            decimal.Round(order.Amount, 2));
    }

    private static async Task<EnrichedOrder> EnrichAsync(
        NormalizedOrder order,
        int? failureId,
        CancellationToken cancellationToken)
    {
        await Task.Delay(
            TimeSpan.FromMilliseconds(10),
            cancellationToken);

        if (order.Id == failureId)
        {
            throw new TimeoutException(
                $"Enrich failed for order {order.Id}.");
        }

        string riskBand = order.Amount >= 1_000m
            ? "review"
            : "standard";

        return new EnrichedOrder(
            order.Id,
            order.Customer,
            order.Amount,
            riskBand);
    }

    private static async IAsyncEnumerable<RawOrder> ReadOrdersAsync(
        int orderCount,
        [EnumeratorCancellation]
        CancellationToken cancellationToken)
    {
        for (int index = 1; index <= orderCount; index++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            await Task.Delay(
                TimeSpan.FromMilliseconds(1),
                cancellationToken);

            yield return new RawOrder(
                index,
                $" Customer {index} ",
                25m + index);
        }
    }

    private static async Task MonitorCompletionAsync(
        Task completion,
        TaskCompletionSource<ExceptionDispatchInfo> firstFault,
        CancellationTokenSource pipelineCancellation,
        CancellationToken callerToken)
    {
        try
        {
            await completion;
        }
        catch (Exception exception)
        {
            Exception originalException =
                UnwrapSingleException(exception);

            if (originalException is not OperationCanceledException ||
                !pipelineCancellation.IsCancellationRequested)
            {
                firstFault.TrySetResult(
                    ExceptionDispatchInfo.Capture(
                        originalException));
            }

            if (!callerToken.IsCancellationRequested)
            {
                pipelineCancellation.Cancel();
            }
        }
    }

    private static Exception UnwrapSingleException(
        Exception exception)
    {
        while (exception is AggregateException aggregate)
        {
            AggregateException flattened = aggregate.Flatten();
            if (flattened.InnerExceptions.Count != 1)
            {
                return flattened;
            }

            exception = flattened.InnerExceptions[0];
        }

        return exception;
    }

    private static async Task ObserveAllCompletionsAsync(
        params Task[] completions)
    {
        try
        {
            await Task.WhenAll(completions);
        }
        catch
        {
        }
    }
}
```

结构上分两半。正常路径只有一个入站所有者：`RunAsync` 负责发送消息，并在数据源结束后调用 `normalize.Complete()`；两条链接把完成状态从 `normalize` 传到 `enrich` 再到 `persist`，方法最后等待 `persist.Completion` 作为整张图的终局。

异常路径的目的完全不同：它监视每个块的完成，**在协同取消掩盖问题之前**先抓住第一个故障，取消共享令牌让被推迟的 `SendAsync`、异步委托或等待中的块停下来，完成头部阻止继续接收，等所有块收尾，再用 `ExceptionDispatchInfo` 抛出被捕获的那个异常。

原文记录了[本地 Dataflow 生命周期验证](https://www.devleader.ca/2026/09/19/build-a-tpl-dataflow-pipeline-in-modern-net)：还原 `System.Threading.Tasks.Dataflow` 10.0.10、在 `net10.0` 与 C# 14 下构建、跑通正常路径，并确定性地验证归一化与补全故障以原始的 `InvalidDataException` 和 `TimeoutException` 冒出来，而不是变成通用拒绝或兄弟块取消。

## 容量就是背压决策

[`BoundedCapacity`](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowblockoptions.boundedcapacity?view=net-10.0) 的默认值是无界。无界默认会把一次临时速率失配变成持续增长的内存占用，所以示例给每个块都配了正容量。

容量是按块算的，不是整张图一个全局数字：

- 归一化块最多持有自己配置的容量。
- 补全块有独立容量，同时最多有四个委托调用在执行。
- 终点块有自己的容量，只有一个委托在执行。

而且 [`BoundedCapacity` 的记账规则](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowblockoptions.boundedcapacity?view=net-10.0)把正在处理的条目也算进去，所以它不是队列长度的显示值，而是那个边界上的**持有量上限**。

这里有一个原文描述得比较含糊、值得单独讲清的点：**背压不是通过 `SendAsync` 的返回值传达的，而是通过它保持未完成来传达的**。当头部无法立刻接收条目时，[`SendAsync`](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowblock.sendasync?view=net-10.0) 会一直不完成，直到目标把消息推迟（postpone）结束。生产者跑不过这张图。

返回值 `false` 表达的是另一件事：目标拒绝接收，通常因为它已经完成或因故障进入不再接收新消息的状态。取消则会让返回的任务进入取消态，而不是返回 `false`。这三种结果必须分开处理——只 check 异常会漏掉普通的拒绝，只 check `false` 又会把取消误判成拒绝。示例的做法是检查每次结果，并在把 `false` 当作通用拒绝之前先等一次头部完成。

### 把容量当成一份连通的预算

三个容量为 16、8、8 的块，并不会构成一条 32 个可互换槽位的队列。每个块持有的消息处于不同的表示和生命周期阶段：补全后的订单可能比原始订单更大，终点块持有的消息还可能对应一个仍在进行的外部操作或资源。

所以实际的内存占用由消息大小、活跃委托数量和消息等待的位置共同决定。头部容量大可以让生产者一直跑，但终点饱和时多出来的工作仍然留在内存里；下游容量太小会带来有用的背压，也可能在上游本该靠一点缓冲吸收正常波动时让上游闲着。

起点应该是保守的正值，然后观察发送等待多久、每个块持有多少条目、终端依赖的限制、分配速率和尾部延迟。只有当证据显示更多缓冲能带来有用的重叠或吸收预期突发时，才提高某个容量。如果吞吐持平而内存与延迟都在涨，那更大的缓冲只是在掩盖瓶颈。

## 并发与顺序是两个开关

[`MaxDegreeOfParallelism`](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.executiondataflowblockoptions.maxdegreeofparallelism?view=net-10.0) 控制一个执行块能同时处理多少条消息，它是块内的条目并发，**不会让同一个条目的后续阶段并行**。

补全块可以同时处理四张订单，但单张订单仍然必须先归一化再补全再落库；与此同时，后面订单的归一化可以和前面订单的补全重叠。这种跨条目的阶段并发，才是独立调度块带来的收益。

[`EnsureOrdered`](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowblockoptions.ensureordered?view=net-10.0) 同样需要显式指定。对并行执行的 transform 块，`true` 会保持输出发布顺序，即使后面的委托先跑完。代价是先完成的结果要等前面的条目。

这个保证有边界：`EnsureOrdered = true` 不能撤销委托内部已经发生的外部副作用。四个委托并发调用外部服务时，调用和返回的顺序仍然可能不同。示例把终点动作设为 `MaxDegreeOfParallelism = 1`，因为演示需要回执有序落库。真实项目要明确到底哪一种顺序重要：进入顺序、块输出顺序、副作用顺序，还是最终结果顺序。

提高并行度只有在工作负载、依赖和机器都允许时才换来吞吐。它也可能增加争用、下游压力、分配、连接占用和重排等待。这些数值属于经过测量的配置，不属于复制来的性能结论。

## 完成是整张图的生命周期

每个块都暴露 `Completion` 任务；[`DataflowLinkOptions.PropagateCompletion`](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowlinkoptions.propagatecompletion?view=net-10.0) 决定链接是否把完成状态传给目标。

`PropagateCompletion` 默认是 `false`，所以示例在两条线性链接上都显式设为 `true`。不设的话，完成头部不会自动完成下游块，即使入站已经结束，终点的 `Completion` 也可能永远不完成。

正常关闭的顺序是刻意的：

1. 结束消息生产。
2. 对头部块调用 `Complete()`。
3. 让已接受的消息流经下游块。
4. 让完成状态沿两条链接传播。
5. 等待终点块的 `Completion`。

只等头部只能证明很少的事。等待终点块，才是「补全与落库已经排空，或者下游图已经故障/取消」的证据。

`LinkTo` 返回的 `IDisposable` 也归方法所有，释放即移除链接。长生命周期静态图可以把链接保留到应用结束，动态图则需要明确的下链策略。示例让链接存活到流水线完成或失败。

## 故障与取消要协同

官方指引说明，执行块委托里未处理的异常会让该块进入故障状态。配合 `PropagateCompletion = true`，故障会顺流而下并让终点块也故障。

但只有故障传播对有界图来说不够：生产者可能正卡在一个[被推迟的 `SendAsync`](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowblock.sendasync?view=net-10.0) 上等待已满的目标。所以示例监视所有块的完成，在任一首先故障时取消共享令牌，把挂起的发送和配合取消的委托放出来。

链接令牌有两个输入：

- 调用方取消，例如 Ctrl+C 或宿主关闭。
- 块故障后请求的内部取消。

每个相关块通过 `ExecutionDataflowBlockOptions` 拿到这个令牌，异步委托观察它，异步数据源观察它，每次 `SendAsync` 也接收它。按 [.NET 的协作式取消模型](https://learn.microsoft.com/en-us/dotnet/standard/threading/cancellation-in-managed-threads)，取消请求的是配合，不是回滚已完成的工作——取消前已经完成的外部副作用依然存在，除非应用另有补偿机制。

还有一处必须区分的语义：调用方发起的取消正常会产生与取消关联的 `OperationCanceledException`，而校验失败或下游依赖异常是故障。不要因为用了共享取消，就把每个故障重写成取消。原始终局失败要保留并如实上报，示例里那个 `firstFault` 容器就是干这个的。

## 它不保证什么

这条流水线在内存里运行。进程终止，缓冲的消息就不是可恢复的积压。它不提供事务处理、持久检查点、进程丢失后的自动重放，也不提供恰好一次的副作用。

它也不会让可变依赖变安全。`MaxDegreeOfParallelism = 4` 的块可能并发调用委托，委托里共用的客户端、缓存、集合、计数器或领域对象必须支持这种访问方式，或者按调用隔离。

有界容量同样不是性能保证。它限制块的持有量并向上游传递压力，至于某个容量对工作负载是有利还是有害，取决于消息大小、服务时间、突发形状、垃圾回收、下游配额和有用重叠的多少。

需要在进程重启后恢复、延迟执行、跨服务恢复、持久化编排状态或运维重放时，就该用持久化消息中间件或工作流引擎。Dataflow 可以存在于某个 worker 内部，但它不该被描述成持久化边界。

## 一条可以照着走的完整链路

把上面的内容压成可执行顺序：

1. 建 `net10.0` 控制台项目，启用可空引用类型，把 `LangVersion` 设为 `14.0`。
2. 决定要不要显式引用 `System.Threading.Tasks.Dataflow`：.NET 10 里它已经内置，固定版本是为了可复现和排除预览线，不是为了拿到能用的 API。
3. 写下容量、并发、顺序、取消、链接完成、入站方式和关闭方式，再动手搭块。
4. 给每个执行块传 `BoundedCapacity`、`MaxDegreeOfParallelism`、`EnsureOrdered` 和同一个 `CancellationToken`；需要外部并发安全或有顺序要求的终点阶段，把并发压到 1。
5. 两条线性链接都设 `PropagateCompletion = true`，并保留 `LinkTo` 返回的句柄。
6. 入站只留一个所有者：检查每次 `SendAsync` 的结果，生产结束后对头部调用一次 `Complete()`。
7. 等待终点 `Completion`，不要只等头部。
8. 监视所有块的完成，抓住第一个故障后取消共享令牌，最后用 `ExceptionDispatchInfo` 抛出原始异常。

### 怎么验证

正常路径应当打印 50 条回执：

```bash
dotnet run
```

`dotnet run` 只跑正常路径，故障路径需要你在 `Main` 里改成下面两次调用之一（`normalizeFailureId` 和 `enrichFailureId` 是 `RunAsync` 自带的可选参数，示例默认不传）：

```csharp
// 第 7 号订单在归一化阶段抛 InvalidDataException
await OrderDataflowPipeline.RunAsync(
    50, shutdown.Token, normalizeFailureId: 7);

// 第 7 号订单在补全阶段抛 TimeoutException
await OrderDataflowPipeline.RunAsync(
    50, shutdown.Token, enrichFailureId: 7);
```

两次都应该让调用方拿到原始的 `InvalidDataException` 或 `TimeoutException`，而不是 `TaskCanceledException`，也不是那句通用的 `"The head block declined an order."`。按 Ctrl+C 则应该看到取消被正常报告。这是这套结构的核心验证点：异常类型不对，多半是协同取消把第一个故障盖掉了。

### 常见问题

**`SendAsync` 返回 `false`，是被背压挡住了吗？** 不是。背压表现为发送任务保持未完成；`false` 表示目标已经完成或已故障、不再接收。取消则让任务进入取消态。

**等了终点 `Completion`，为什么回执数量还是不对？** 先确认入站所有者只调用了一次 `Complete()`，再确认两条链接都设了 `PropagateCompletion = true`。少一处，终点就可能提前或永不完成。

**进程退出时任务还在跑？** 检查被推迟的 `SendAsync` 是否拿到了会被取消的令牌。没有取消，它会一直等在一个已满的目标上。

**并发调大以后数据错乱？** 委托里的共享依赖不支持并发访问。要么按调用隔离，要么把该块的并发压到 1。

## 结语

一条能用的 TPL Dataflow 流水线，从来不是三个构造函数加 `LinkTo`。可交付的契约包括有界持有、显式的条目并发、明确的顺序范围、检查过的入站、协作式取消、传播的完成状态、对终点的观察，以及故障协同。

块图让这些策略变得可配置，但它不会替你做选择。固定稳定版本、把每个运营决策写下来、保留原始故障，在改动容量或并行度之前用真实负载做测量——这就是一段「能搬消息的 demo」和一条「调用方敢自己持有生命周期的流水线」之间的差别。

Aide Hub 会继续整理这类把并发原语用成可维护工程结构的实践，覆盖 .NET、AI 助手与软件工程。

## 参考

- [Build a TPL Dataflow Pipeline in Modern .NET](https://www.devleader.ca/2026/09/19/build-a-tpl-dataflow-pipeline-in-modern-net)（原文，Nick Cosentino）
- [Dataflow（Task Parallel Library）文档](https://learn.microsoft.com/en-us/dotnet/standard/parallel-programming/dataflow-task-parallel-library)
- [DataflowBlockOptions.BoundedCapacity](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowblockoptions.boundedcapacity?view=net-10.0)
- [DataflowBlock.SendAsync](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowblock.sendasync?view=net-10.0)
- [ExecutionDataflowBlockOptions.MaxDegreeOfParallelism](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.executiondataflowblockoptions.maxdegreeofparallelism?view=net-10.0)
- [DataflowBlockOptions.EnsureOrdered](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowblockoptions.ensureordered?view=net-10.0)
- [DataflowLinkOptions.PropagateCompletion](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.dataflowlinkoptions.propagatecompletion?view=net-10.0)
- [IDataflowBlock.Completion](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.dataflow.idataflowblock.completion?view=net-10.0)
- [System.Threading.Tasks.Dataflow（NuGet 版本列表）](https://www.nuget.org/packages/System.Threading.Tasks.Dataflow)
- [.NET 10 release notes](https://github.com/dotnet/core/blob/main/release-notes/10.0/10.0.0/README.md)
