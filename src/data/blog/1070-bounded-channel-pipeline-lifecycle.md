---
pubDatetime: 2026-09-16T07:28:00+08:00
title: ".NET 有界 Channel 管道的完整生命周期"
description: "有界 Channel 限制的是队列长度，不是应用里的在途消息数。本文用一份 net10.0 示例拆开准入、消息所有权、完成权、取消和两条收尾路径，并给出实测的在途峰值。"
tags: [".NET", "C#", "Channels", "并发编程", "架构"]
slug: "bounded-channel-pipeline-lifecycle"
ogImage: "../../assets/1070/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/15/build-a-bounded-processing-pipeline-with-systemthreadingchannels"
---

一个后台服务用 `Channel.CreateBounded<T>(capacity: 100)` 接收任务，容量看起来是安全阀。然后某个消费者的下游开始变慢：生产者卡在 `WriteAsync` 上不再返回，一个消费者抛异常退出，其余消费者还在读，任务永远不结束，进程关不掉。容量是设对了，问题出在别处——没人规定谁拥有消息、谁有权宣布「不会再有新消息」、故障时谁来收尾。

Dev Leader 的 Nick Cosentino 在 [Build a Bounded Processing Pipeline With System.Threading.Channels](https://www.devleader.ca/2026/09/15/build-a-bounded-processing-pipeline-with-systemthreadingchannels) 里的判断是：`Channel<T>` 的创建只是一个配置调用，真正需要设计的是一条从准入到关停的生命周期。下面沿着这条生命周期走一遍，并把原文的代码在本机跑起来核对。

## 有界只约束队列，不约束在途消息

微软的 [Channels 文档](https://learn.microsoft.com/en-us/dotnet/core/extensions/channels)把 `System.Threading.Channels` 定义为基于 FIFO 队列的异步生产者/消费者同步结构，并明确「有界 Channel 可以用任何大于零的容量创建」。容量改变的是准入契约：

- 未满时，`WriteAsync` 可以接纳下一个条目。
- 已满时，由 `BoundedChannelFullMode` 决定是等待还是丢弃。
- 消费者取走条目后，等待中的写入方才能继续。

关键在这句：**容量统计的是排队条目，不包括消费者正在处理的条目。**

所以 `capacity: 2` 配 3 个消费者时，同时在内存里的消息远不止 2 条：队列里最多 2 条，3 个消费者各持有 1 条，生产者手上还有 1 条正卡在等待中的 `WriteAsync` 里。原文给出的这个上界是 6，我在本机用 `capacity: 2`、`workerCount: 3`、400 条输入跑了一遍，采样到的在途峰值正好是 **6**。

这决定了容量该怎么选：它是队列上限，不是一个内存公式。同样是两个槽位，放两个 `long` ID 和放两块从 `MemoryPool` 租来的兆字节缓冲区，内存占用差几个数量级。如果消息大小差异很大，要按真实分布去量保留内存，并考虑大负载是不是该用「句柄」表示，而不是整块复制进队列。

消费者数量是另一个独立的限制。加消费者会提高「正在处理」的消息数，但不会改变队列缓冲量，同时会影响下游并发、外部服务压力和完成顺序。容量和 worker 数量应该分开配置、分开推理。

## Wait 模式把「无损」限定在准入这一层

`BoundedChannelFullMode.Wait` 的含义是：队列满时写入方等待。`WriteAsync` 在条目被接纳后完成，或者因为取消、Channel 关闭而结束；`TryWrite` 则立即返回能否写入。`Wait` 不会为了让位而主动丢弃条目。

这就是原文所说的「无损」的确切边界：一条消息要么成功写入（所有权移交），要么生产者拿到异常或取消。它不等于整个应用不会丢工作——进程崩溃照样清空内存状态，消费者也可能只完成一半就失败。

顺带核对一个容易被当成「优化」的细节：[官方文档的 full mode 表格](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.boundedchannelfullmode?view=net-10.0)里，`BoundedChannelFullMode.Wait` 本来就是默认值。示例里显式写出来是文档化意图，不是行为变更；真正会改变语义的是 `DropNewest`、`DropOldest` 和 `DropWrite` 这三个丢弃模式。

另外，等待是背压而不是并行：生产者让出执行权，消费者通过读取腾出空间，等待中的写入方不需要占用线程。这也是为什么 `Wait` 模式和「阻塞线程」不能混为一谈。

## 四个所有权状态，一个方向

生命周期之所以容易失控，是因为「谁负责释放」没有写下来。示例用一张所有权表把它固定住：

| 状态                | 所有者     | 清理责任                            |
| ------------------- | ---------- | ----------------------------------- |
| 消息已创建但未接纳  | 生产者     | `WriteAsync` 失败或被取消时负责释放 |
| `WriteAsync` 已完成 | 通道边界   | 保留到某个消费者读取为止            |
| 消息已被读取        | 消费者     | 处理结束后释放，处理失败也要释放    |
| 中止时残留在缓冲区  | 完成协调者 | 等 worker 停止后排空并释放          |

这份契约同时防住两种错误：重复释放和资源遗弃。它还让「写入成功」有了精确定义——那一刻生产者不再拥有这条消息。

示例用池化字节缓冲区来让清理在代码里可见，但这不是 Channels 的要求。一个只含字符串和数字的不可变记录可能压根不需要释放；所有权转移的规则一样成立，只是清理从「资源」变成了「逻辑」。

通道本身由创建它的方法拥有。生产者只拿到 writer，消费者只拿到 reader，任何一方都不能自行判断整条管道已经结束。

## 完整示例：一个生产者、三个消费者、一个协调者

示例面向 .NET 10 和 C# 14，开启可空引用类型；`System.Threading.Channels` 已包含在共享框架里，不需要额外 NuGet 包。

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <LangVersion>14.0</LangVersion>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
</Project>
```

消息类型把「资源所有权」写在类型上：`WorkItem` 持有池化缓冲区，`Dispose` 用 `Interlocked.Exchange` 保证只释放一次，并用静态计数器暴露当前在途实例数，方便验证不泄漏。

```csharp
using System.Buffers;
using System.Collections.Concurrent;
using System.Runtime.ExceptionServices;
using System.Text;
using System.Threading.Channels;

namespace BoundedChannelsPipeline;

public sealed record InputMessage(long Sequence, string Text);

public sealed class WorkItem : IDisposable
{
    private static int _activeCount;

    private readonly int _payloadLength;
    private IMemoryOwner<byte>? _payloadOwner;

    private WorkItem(
        long sequence,
        IMemoryOwner<byte> payloadOwner,
        int payloadLength)
    {
        Sequence = sequence;
        _payloadOwner = payloadOwner;
        _payloadLength = payloadLength;
        Interlocked.Increment(ref _activeCount);
    }

    public static int ActiveCount => Volatile.Read(ref _activeCount);

    public long Sequence { get; }

    public ReadOnlyMemory<byte> Payload
    {
        get
        {
            IMemoryOwner<byte> owner = _payloadOwner ??
                throw new ObjectDisposedException(nameof(WorkItem));
            return owner.Memory[.._payloadLength];
        }
    }

    public static WorkItem Create(InputMessage input)
    {
        int byteCount = Encoding.UTF8.GetByteCount(input.Text);
        IMemoryOwner<byte> owner = MemoryPool<byte>.Shared.Rent(byteCount);

        try
        {
            int bytesWritten = Encoding.UTF8.GetBytes(
                input.Text.AsSpan(),
                owner.Memory.Span);
            return new WorkItem(input.Sequence, owner, bytesWritten);
        }
        catch
        {
            owner.Dispose();
            throw;
        }
    }

    public void Dispose()
    {
        IMemoryOwner<byte>? owner =
            Interlocked.Exchange(ref _payloadOwner, null);

        if (owner is not null)
        {
            owner.Dispose();
            Interlocked.Decrement(ref _activeCount);
        }
    }
}

public sealed record PipelineRunResult(
    IReadOnlyList<long> ProcessedSequences);
```

协调者是整个设计里最重要的部分。它创建通道、启动生产者与消费者、等待第一个结果、在正常路径上完成 writer 让消费者排水，在异常路径上取消挂起操作、等待所有任务停下、再排空并释放缓冲区里残留的消息。

```csharp
public static class Program
{
    public static async Task Main()
    {
        InputMessage[] input =
        [
            new(0, "alpha"),
            new(1, "bravo"),
            new(2, "charlie"),
            new(3, "delta"),
            new(4, "echo"),
            new(5, "foxtrot")
        ];

        PipelineRunResult result = await RunPipelineAsync(
            input,
            capacity: 2,
            workerCount: 3,
            failOnSequence: null,
            CancellationToken.None);

        Console.WriteLine(
            $"Processed {result.ProcessedSequences.Count} messages.");
    }

    public static async Task<PipelineRunResult> RunPipelineAsync(
        IReadOnlyList<InputMessage> input,
        int capacity,
        int workerCount,
        long? failOnSequence,
        CancellationToken cancellationToken)
    {
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(capacity);
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(workerCount);

        Channel<WorkItem> channel = Channel.CreateBounded<WorkItem>(
            new BoundedChannelOptions(capacity)
            {
                FullMode = BoundedChannelFullMode.Wait,
                SingleWriter = true,
                SingleReader = workerCount == 1,
                AllowSynchronousContinuations = false
            });

        using CancellationTokenSource abort =
            CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);

        var consumerFailure = new TaskCompletionSource<Exception>(
            TaskCreationOptions.RunContinuationsAsynchronously);

        var processedSequences = new ConcurrentQueue<long>();

        Task producer = ProduceAsync(
            input,
            channel.Writer,
            abort.Token);

        var consumers = new Task[workerCount];
        for (int workerId = 0; workerId < workerCount; workerId++)
        {
            consumers[workerId] = ConsumeAsync(
                workerId,
                channel.Reader,
                consumerFailure,
                processedSequences,
                failOnSequence,
                abort.Token);
        }

        Task[] allTasks = [producer, .. consumers];
        bool writerCompleted = false;

        try
        {
            Task firstOutcome = await Task.WhenAny(
                producer,
                consumerFailure.Task);

            if (ReferenceEquals(firstOutcome, consumerFailure.Task))
            {
                Exception consumerError = await consumerFailure.Task;
                ExceptionDispatchInfo.Capture(consumerError).Throw();
                throw new InvalidOperationException("Unreachable.");
            }

            await producer;
            channel.Writer.Complete();
            writerCompleted = true;

            Task allConsumers = Task.WhenAll(consumers);
            Task drainOutcome = await Task.WhenAny(
                allConsumers,
                consumerFailure.Task);

            if (ReferenceEquals(drainOutcome, consumerFailure.Task))
            {
                Exception consumerError = await consumerFailure.Task;
                ExceptionDispatchInfo.Capture(consumerError).Throw();
                throw new InvalidOperationException("Unreachable.");
            }

            await allConsumers;
            await channel.Reader.Completion;

            return new PipelineRunResult(
                processedSequences.ToArray());
        }
        catch (Exception ex)
        {
            await abort.CancelAsync();

            if (!writerCompleted)
            {
                channel.Writer.Complete(ex);
            }

            await ObserveAllAsync(allTasks);
            DisposeBufferedMessages(channel.Reader);
            await ObserveCompletionAsync(channel.Reader.Completion);
            throw;
        }
    }
```

生产者只做一件事：把输入变成 `WorkItem`，写进通道，并在写入没有成功时释放自己创建的消息。注意 `ownershipTransferred` 这个标志——它把「谁负责释放」这件事交给了一次写入结果，而不是靠约定。

```csharp
    private static async Task ProduceAsync(
        IEnumerable<InputMessage> input,
        ChannelWriter<WorkItem> writer,
        CancellationToken cancellationToken)
    {
        foreach (InputMessage source in input)
        {
            WorkItem item = WorkItem.Create(source);
            bool ownershipTransferred = false;

            try
            {
                await writer.WriteAsync(item, cancellationToken);
                ownershipTransferred = true;
            }
            finally
            {
                if (!ownershipTransferred)
                {
                    item.Dispose();
                }
            }
        }
    }
```

消费者用 `using` 保证「处理失败也要释放」，并把第一个异常写进 `failureSignal`，让协调者不用等到生产者卡死才发现问题。

```csharp
    private static async Task ConsumeAsync(
        int workerId,
        ChannelReader<WorkItem> reader,
        TaskCompletionSource<Exception> failureSignal,
        ConcurrentQueue<long> processedSequences,
        long? failOnSequence,
        CancellationToken cancellationToken)
    {
        try
        {
            await foreach (WorkItem item in
                reader.ReadAllAsync(cancellationToken))
            {
                using (item)
                {
                    await ProcessAsync(
                        workerId,
                        item,
                        processedSequences,
                        failOnSequence,
                        cancellationToken);
                }
            }
        }
        catch (Exception ex)
        {
            failureSignal.TrySetResult(ex);
            throw;
        }
    }

    private static async Task ProcessAsync(
        int workerId,
        WorkItem item,
        ConcurrentQueue<long> processedSequences,
        long? failOnSequence,
        CancellationToken cancellationToken)
    {
        int delayMilliseconds = (int)(item.Sequence % 3) switch
        {
            0 => 45,
            1 => 15,
            _ => 30
        };

        await Task.Delay(
            TimeSpan.FromMilliseconds(delayMilliseconds),
            cancellationToken);

        if (item.Sequence == failOnSequence)
        {
            throw new InvalidOperationException(
                $"Processing failed for sequence {item.Sequence}.");
        }

        string text = Encoding.UTF8.GetString(item.Payload.Span);
        processedSequences.Enqueue(item.Sequence);
        Console.WriteLine(
            $"Worker {workerId} completed {item.Sequence}: {text}");
    }
```

最后三个辅助方法负责收尾。`ObserveAllAsync` 在 `WhenAll` 抛出后仍逐个读取 `task.Exception`，避免留下未观察的任务异常；`DisposeBufferedMessages` 在 worker 全部停止之后才排空通道；`ObserveCompletionAsync` 用 `ConfigureAwaitOptions.SuppressThrowing` 消费掉带异常的 `Completion`，因为主异常已经由协调者重新抛出。

```csharp
    private static async Task ObserveAllAsync(
        IReadOnlyCollection<Task> tasks)
    {
        try
        {
            await Task.WhenAll(tasks);
        }
        catch
        {
            foreach (Task task in tasks)
            {
                _ = task.Exception;
            }
        }
    }

    private static void DisposeBufferedMessages(
        ChannelReader<WorkItem> reader)
    {
        while (reader.TryRead(out WorkItem? item))
        {
            item.Dispose();
        }
    }

    private static async Task ObserveCompletionAsync(
        Task completion)
    {
        await completion.ConfigureAwait(
            ConfigureAwaitOptions.SuppressThrowing);
    }
}
```

## 把示例跑起来：三步验证

原文提到它用一个本地验证产物记录了四条检查，但那个产物链接（`/validation/wave2/seq8/result.json`）在我核对时返回 404，所以下面不依赖它，改成自己跑。我把上面这份 `Program.cs` 原样放进一个 `net10.0` 控制台项目，用 .NET SDK 10.0.301 编译运行（.NET 10 是 2025 年 11 月 11 日发布的 LTS，当前补丁为 10.0.12），并额外加了一行打印 `WorkItem.ActiveCount`。

**第一步，正常路径。** 直接 `dotnet run`，六条消息全部处理完，完成顺序和队列顺序不一致：

```text
Worker 1 completed 1: bravo
Worker 2 completed 2: charlie
Worker 2 completed 4: echo
Worker 0 completed 0: alpha
Worker 2 completed 5: foxtrot
Worker 1 completed 3: delta
Processed 6 messages.
ActiveCount after run: 0
```

原文贴出的示例输出里最后两条的顺序和这里相反，这正是它自己说明的那一点：worker 分配和完成顺序会变。`ActiveCount` 回到 0，说明这条路径没有遗漏释放。

**第二步，故障路径。** 把 `Main` 里的 `failOnSequence` 从 `null` 改成 `2`：

```text
Worker 1 completed 1: bravo
Caught: InvalidOperationException: Processing failed for sequence 2.
ActiveCount after run: 0
```

协调者抛出的是消费者原始的 `InvalidOperationException`，不是 `AggregateException`，说明 `ExceptionDispatchInfo.Capture(...).Throw()` 这条路径生效了；同时 `ActiveCount` 仍然回到 0，缓冲区里剩下的消息被正确排空释放。

**第三步，取消一条被容量卡住的生产者。** 把输入换成 500 条，容量仍是 2，用一个 60 毫秒后触发的 `CancellationTokenSource`：

```text
Worker 1 completed 1: msg-1
Worker 2 completed 2: msg-2
Worker 0 completed 0: msg-0
Worker 2 completed 4: msg-4
Caught: OperationCanceledException
ActiveCount after run: 0
```

`WriteAsync` 被取消后，生产者释放了手上那条还没移交的消息，`ActiveCount` 同样归零。

三步都通过，但要说清楚边界：这些结论只覆盖这个示例实现，不代表任何 Channels 设计自动获得同样的保证。验证方式也很便宜——`WorkItem.ActiveCount` 是刻意留出来的观测点，真实项目里等价的观测点是「未释放的缓冲区、流或租约计数」。

## SingleReader 和 SingleWriter 是承诺，不是配置

这两个选项经常被当成「我有几个消费者」来填，但它们不是 worker 数量设置。[`SingleReader` 的文档](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.channeloptions.singlereader?view=net-10.0)把语义写得很清楚：`true` 表示读取方**保证**任何时刻最多只有一个读取操作，`false` 表示不提供这种保证；打开它之后，通道可以据此优化某些操作。`SingleWriter` 同理。

换句话说，它们是通道创建者向实现作出的承诺，描述的是周围代码已经建立的访问模式，而不是让通道去创建 worker、调度工作或保证顺序。

示例里只有一个生产者任务，所以 `SingleWriter = true` 是诚实的；协调者会调用 `Complete`，但完成不算一次并发写入。消费者数量可配置，3 个消费者时可能有多个待处理读取，因此 `SingleReader = false`。如果 `workerCount` 是 1，设成 `true` 才诚实。

填错的代价是「没有保证」，而不是立刻报错——实现只是按一个不成立的承诺去优化。这一点值得亲手确认：我把 `SingleReader` 改成 `true` 同时保留 3 个消费者，用 2000 条消息、容量 16 跑了 4 次，每次都处理完 2000 条且无重复，没有任何可见异常。所以冒烟测试通过不能证明标志位填对了，只能说明这次没被触发。

`AllowSynchronousContinuations` 保持 `false` 也是同理。打开它可以让完成挂起异步操作的操作内联执行后续代码，在测量过的设计里可能有用，但它会把生产者的执行和消费者的后续行为耦合起来。

## 只有协调者能完成 writer

`ChannelWriter.Complete` 的契约是「不会再写入数据了」。示例里只有 `RunPipelineAsync` 调用它：生产者只写不完成，消费者只读也不完成。这样就没有多个参与者争抢着宣布通道的最终状态。

正常路径的顺序是固定的：

1. 启动生产者和所有消费者。
2. 等待生产者完成，或者等待第一个消费者失败。
3. `await producer`，确保它的异常或取消被观察到。
4. 调用一次 `Complete()`，因为不会再有消息被接纳。
5. 让消费者读完缓冲区里已有的内容。
6. 等待所有消费者，再等待 `channel.Reader.Completion`。

如果以后变成多个生产者，规则不变：协调者要等所有生产者任务成功结束，然后才完成一次 writer。单个生产者仍然不负责宣布通道关闭。

协调者的价值不在「找个地方放 `Complete`」，而在于它是唯一知道这些事的组件：所有写入方是否都结束了、管道该不该排水、以及哪个异常代表非正常结束。

## 取消停的是操作，完成关的是准入

通道的读写都接受取消令牌。取消一个挂起的 `WriteAsync` 会终止那次准入尝试；取消 [`ReadAllAsync`](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.channelreader-1.readallasync?view=net-10.0) 会停止该消费者的枚举，但已经就绪的数据仍可能在取消请求之后被交出。

两者都不会调用 `ChannelWriter.Complete`，也不会自行声明「再也不会有生产者写入」。取消和完成回答的是两个不同的问题：

- 取消要求一个挂起的操作停止等待或处理。
- writer 完成声明不会再有条目被写入。

示例用策略把二者连起来，而不是把它们混成同一个机制：生产者失败、消费者失败或调用方取消都会进入协调者的 `catch`，协调者取消那个链接的 `abort` 令牌来唤醒兄弟操作；如果 writer 还开着，再用触发异常完成它。

取消仍然是[协作式的](https://learn.microsoft.com/en-us/dotnet/standard/threading/cancellation-in-managed-threads)：示例里 `ProcessAsync`、`WriteAsync`、`ReadAllAsync` 都拿到链接令牌，真实的处理阶段必须把这个令牌继续传给它拥有的每一个可取消依赖。取消不会撤销已经处理完的消息，也不会回滚已经发生的外部副作用。

## FIFO 管的是队列，不是处理完成顺序

[Channels 文档](https://learn.microsoft.com/en-us/dotnet/core/extensions/channels)定义的 FIFO 契约作用在队列边界上：条目被接纳的顺序和从队列取出的顺序一致。示例只有一个生产者，所以消息序号同时反映了准入顺序；消费者总是先取走更早入队的条目。

但 3 个消费者可以用另一种顺序结束。FIFO 管的是「从队列移除」，不是「读取之后的处理何时完成」。消费者 0 读到序号 0、消费者 1 读到序号 1 之后，这两条消息已经不在通道里了，它们的处理耗时互相独立，序号 1 完全可能先完成——本机那六行输出就是例子。

「有序」在这类系统里至少指五种不同契约：生产者调用顺序、成功准入顺序、消费者读取顺序、处理完成顺序、结果发布顺序。示例只承诺前两者。如果最终输出必须按序号排列，就得加一个按序号键控的重排阶段，或者让顺序敏感的那一级只用一个消费者；不要指望通道会串行化「读取之后」发生的事。

## 两条收尾路径：正常排水与故障中止

正常关停的目标是排空已接纳的工作，而不是取消消费者。生产者结束后，协调者调用 `channel.Writer.Complete()`：准入关闭，缓冲区保留。[`ReadAllAsync`](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.channelreader-1.readallasync?view=net-10.0) 会继续交出可用条目，直到不可能再出现新数据；每个消费者在 `ProcessAsync` 返回后释放当前 `WorkItem`；最后协调者等待 `Task.WhenAll(consumers)` 和 `channel.Reader.Completion`。

排水的含义有四条：完成之后不再接纳新条目；每一条成功接纳的消息都仍然对消费者可用；方法在所有消费者任务结束前不返回；reader 完成确认不可能再读到数据。排水时间取决于工作负载，宿主可以在外层加一个时间预算，超时后取消——但那一刻路径已经从「正常排水」切换成「中止」。这两种关停值得分别命名，不要都叫「优雅退出」。

故障路径要解决的问题是另一种：消费者失败时生产者可能正卡在满队列上，没人关掉生命周期，生产者就会一直等。示例用一个 `consumerFailure` 信号让协调者尽快看到第一个消费者异常，然后在 `catch` 里按固定顺序处理：取消链接令牌让挂起的读写和处理停下；writer 还开着就用原始异常完成它；等待或观察生产者和每个消费者；worker 停止后排空通道里剩下的消息并逐条释放；观察 reader 的完成任务；最后重新抛出触发异常。

这个顺序不是随手排的：只要还有消费者可能读取，就不能安全释放缓冲区里的消息。协调者必须先等 worker 停止使用 reader，再接管剩下的内容。如果消息不持有可释放资源，清理循环可能什么都不做——但把所有权规则显式写出来，才能防止将来有人加上池化缓冲区、流或租约却没安排中止清理。

## 这套设计不承诺什么

这套设计只在进程存活期间、在有界的内存准入边界上无损。`Wait` 避免的是主动丢弃，它不会把 Channels 变成持久化 broker。示例不包括：

- 进程或机器故障后的恢复
- 跨应用重启的持久化
- 恰好一次的副作用
- 自动重试
- 与数据库或远程服务的事务性协调
- 多消费者下的 FIFO 处理完成顺序
- 任何特定的吞吐或延迟结果

有这些需求就得补机制：需要持久化的工作通常应该放进带显式确认与重投递模型的持久队列或 broker；「恰好一次」的说法要求每个相关副作用周围都有具体的事务或去重行为。

需要做决定的地方通常是这两条：**消息能不能容忍进程重启后丢失？** 能，Channels 是合适的进程内交接；不能，就换成持久化队列，或者让 Channel 只承担「从持久队列取出后的一次接力」。**最终输出要不要严格按序号？** 要，就把重排阶段或单消费者写进设计，而不是指望通道。

## 结论

有界 Channel 的创建只是配置调用，值得设计的是生命周期：容量和 `Wait` 定义准入，诚实的 reader/writer 标志描述并发，所有权决定谁释放每条消息，一个协调者定义完成，取消停的是操作而完成关的是准入，FIFO 描述队列而不必然描述处理完成顺序。

责任各有归属之后，模式本身很直白：生产者创建并移交消息，消费者处理并释放消息，协调者监督任务、正常排水、故障中止并清理残留。

如果你也在做 AI 助手、开发工具或 .NET 工程实践，Aide Hub 会继续分享这类「先把边界写清楚、再写实现」的落地经验。

## 参考

- [Build a Bounded Processing Pipeline With System.Threading.Channels — Nick Cosentino, Dev Leader](https://www.devleader.ca/2026/09/15/build-a-bounded-processing-pipeline-with-systemthreadingchannels)
- [Channels — .NET 官方文档](https://learn.microsoft.com/en-us/dotnet/core/extensions/channels)
- [BoundedChannelFullMode 枚举 — .NET 10 API](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.boundedchannelfullmode?view=net-10.0)
- [ChannelWriter&lt;T&gt;.WriteAsync 方法 — .NET 10 API](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.channelwriter-1.writeasync?view=net-10.0)
- [ChannelWriter&lt;T&gt;.Complete 方法 — .NET 10 API](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.channelwriter-1.complete?view=net-10.0)
- [ChannelReader&lt;T&gt;.ReadAllAsync 方法 — .NET 10 API](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.channelreader-1.readallasync?view=net-10.0)
- [ChannelOptions.SingleReader 属性 — .NET 10 API](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.channeloptions.singlereader?view=net-10.0)
- [ChannelOptions.AllowSynchronousContinuations 属性 — .NET 10 API](https://learn.microsoft.com/en-us/dotnet/api/system.threading.channels.channeloptions.allowsynchronouscontinuations?view=net-10.0)
- [Cancellation in managed threads — .NET 官方文档](https://learn.microsoft.com/en-us/dotnet/standard/threading/cancellation-in-managed-threads)
- [.NET Release Notes — dotnet/core](https://github.com/dotnet/core/blob/main/release-notes/README.md)
