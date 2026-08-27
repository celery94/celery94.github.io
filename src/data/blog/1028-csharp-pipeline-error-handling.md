---
pubDatetime: 2026-08-27T07:54:28+08:00
title: "C# 管道错误处理：Result、异常与短路"
description: "C# 管道要区分预期拒绝、意外异常和取消，并把短路、幂等、重试与遥测写进契约。本文用订单示例说明 Result 与异常的边界，以及副作用发生后的处理方式，帮助你减少重复副作用与误判。"
tags: ["C#", ".NET", "Pipeline", "Error Handling", "Result Pattern"]
slug: "csharp-pipeline-error-handling"
ogImage: "../../assets/1028/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/26/error-handling-in-c-pipelines-exceptions-results-and-shortcircuiting"
---

验证失败、请求取消、库存服务暂时不可用、代码缺陷，都可能让同一条 C# 管道停下来。调用方处理它们的方式却不同：业务拒绝需要稳定的错误码，取消需要保留协作语义，临时依赖故障可能值得重试，程序缺陷则需要带着原始堆栈交给更高层处理。

Dev Leader 在 2026 年 8 月 26 日发布的文章，用一个订单提交管道把这些边界串起来。它的核心建议可以概括为：预期结果用类型表达，意外故障继续抛出，取消单独传播；一旦管道开始产生外部副作用，还要明确幂等边界、重试归属和部分完成后的处理方式。

## 先把四种结果写进契约

一条管道至少需要区分下面四种可观察结果：

| 结果       | 推荐表示                    | 是否进入后续阶段     | 调用方通常要做什么       |
| ---------- | --------------------------- | -------------------- | ------------------------ |
| 成功       | `Succeeded<T>`              | 还存在下一阶段时继续 | 使用输出值               |
| 预期拒绝   | `Rejected`                  | 否                   | 按稳定错误码返回或展示   |
| 调用方取消 | 被取消的 `Task`             | 否                   | 保留取消语义，结束等待   |
| 意外失败   | 带原始异常的 faulted `Task` | 否                   | 在能恢复的边界处理或记录 |

预期拒绝属于业务契约的一部分。例如 SKU 缺失、数量超出范围、请求违反已公开的规则。应用通常希望把这类结果计数、映射为 API 响应，或交给用户修正，因此稳定的 code 比异常文本更合适。

意外失败代表阶段没有按正常契约完成。依赖不可用、文件损坏、代码不变量被破坏，都可能属于这一类。当前层只有在能够恢复，或确实能增加有用行为时才捕获异常；否则让更高层看到原始故障。

取消代表调用方、超时控制器或宿主请求停止工作。它与业务拒绝和依赖故障需要保持区分。这个区分会影响 API 状态、日志、指标和后续补偿动作。

下面的例子只定义两个 Result 分支：成功和预期拒绝。没有额外的 `Failed` 分支，意外异常仍通过异常机制传播。

```csharp
public abstract record PipelineResult<T>
{
    private PipelineResult()
    {
    }

    public sealed record Succeeded(T Value) : PipelineResult<T>;

    public sealed record Rejected(
        string Code,
        string Message) : PipelineResult<T>;
}
```

这里的重点在一致性：同一个条件不能因为换了一个阶段实现，就有时返回 `Rejected`，有时抛出异常。调用方只有在结果规则稳定时，才能可靠地组合多个阶段。

## 一个失败感知的订单管道

下面的完整示例不依赖第三方库，使用三个阶段：

1. 验证订单，发现业务问题时返回 `Rejected`。
2. 预留库存，只对明确的临时异常进行一次重试，并复用 `OperationId` 作为幂等键。
3. 生成收据。验证拒绝时，这一步和库存预留都不会执行。

可以用当前 .NET SDK 创建控制台项目：

```bash
dotnet new console -n PipelineFailureExample
cd PipelineFailureExample
```

将 `Program.cs` 替换为下面的代码，再运行 `dotnet run`。内存库存网关会故意让同一个幂等键的第一次调用失败，第二次调用成功，因此正常输入可以看到一次受控重试后的收据。

```csharp
using System.Diagnostics;

var pipeline = new OrderPipeline(
    new ValidateOrderStage(),
    new ReserveInventoryStage(new InMemoryInventoryGateway()));

using var timeout = new CancellationTokenSource(
    TimeSpan.FromSeconds(5));

var submission = new OrderSubmission(
    Guid.NewGuid(),
    "BOOK-001",
    2);

PipelineResult<OrderReceipt> result =
    await pipeline.RunAsync(submission, timeout.Token);

Console.WriteLine(result switch
{
    PipelineResult<OrderReceipt>.Succeeded succeeded =>
        $"Succeeded: {succeeded.Value.ReservationId}",
    PipelineResult<OrderReceipt>.Rejected rejected =>
        $"Rejected: {rejected.Code}",
    _ => throw new InvalidOperationException(
        "Unknown pipeline result.")
});

public sealed record OrderSubmission(
    Guid OperationId,
    string Sku,
    int Quantity);

public sealed record ValidatedOrder(
    Guid OperationId,
    string Sku,
    int Quantity);

public sealed record InventoryReservation(
    Guid ReservationId,
    Guid OperationId,
    string Sku,
    int Quantity);

public sealed record OrderReceipt(
    Guid OperationId,
    Guid ReservationId);

public abstract record PipelineResult<T>
{
    private PipelineResult()
    {
    }

    public sealed record Succeeded(T Value) : PipelineResult<T>;

    public sealed record Rejected(
        string Code,
        string Message) : PipelineResult<T>;
}

public sealed class TransientInventoryException : Exception
{
    public TransientInventoryException(string message)
        : base(message)
    {
    }
}

public interface IInventoryGateway
{
    Task<InventoryReservation> ReserveAsync(
        Guid idempotencyKey,
        string sku,
        int quantity,
        CancellationToken cancellationToken);
}

public sealed class InMemoryInventoryGateway : IInventoryGateway
{
    private readonly object _sync = new();
    private readonly Dictionary<Guid, InventoryReservation>
        _reservations = new();
    private readonly HashSet<Guid> _failedFirstAttempts = new();

    public Task<InventoryReservation> ReserveAsync(
        Guid idempotencyKey,
        string sku,
        int quantity,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();

        lock (_sync)
        {
            if (_reservations.TryGetValue(
                idempotencyKey,
                out InventoryReservation existing))
            {
                return Task.FromResult(existing);
            }

            if (_failedFirstAttempts.Add(idempotencyKey))
            {
                throw new TransientInventoryException(
                    "Inventory dependency was temporarily unavailable.");
            }

            var reservation = new InventoryReservation(
                Guid.NewGuid(),
                idempotencyKey,
                sku,
                quantity);

            _reservations.Add(idempotencyKey, reservation);
            return Task.FromResult(reservation);
        }
    }
}

public sealed class ValidateOrderStage
{
    public Task<PipelineResult<ValidatedOrder>> ExecuteAsync(
        OrderSubmission input,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();

        if (string.IsNullOrWhiteSpace(input.Sku))
        {
            return Task.FromResult<PipelineResult<ValidatedOrder>>(
                new PipelineResult<ValidatedOrder>.Rejected(
                    "order.sku_required",
                    "A SKU is required."));
        }

        if (input.Quantity is < 1 or > 100)
        {
            return Task.FromResult<PipelineResult<ValidatedOrder>>(
                new PipelineResult<ValidatedOrder>.Rejected(
                    "order.quantity_out_of_range",
                    "Quantity must be between 1 and 100."));
        }

        return Task.FromResult<PipelineResult<ValidatedOrder>>(
            new PipelineResult<ValidatedOrder>.Succeeded(
                new ValidatedOrder(
                    input.OperationId,
                    input.Sku,
                    input.Quantity)));
    }
}

public sealed class ReserveInventoryStage
{
    private const int MaxAttempts = 2;
    private static readonly TimeSpan RetryDelay =
        TimeSpan.FromMilliseconds(25);

    private readonly IInventoryGateway _gateway;

    public ReserveInventoryStage(IInventoryGateway gateway)
    {
        _gateway = gateway;
    }

    public async Task<InventoryReservation> ExecuteAsync(
        ValidatedOrder input,
        CancellationToken cancellationToken)
    {
        for (int attempt = 1; attempt <= MaxAttempts; attempt++)
        {
            try
            {
                return await _gateway.ReserveAsync(
                    input.OperationId,
                    input.Sku,
                    input.Quantity,
                    cancellationToken);
            }
            catch (TransientInventoryException)
                when (attempt < MaxAttempts)
            {
                await Task.Delay(RetryDelay, cancellationToken);
            }
        }

        throw new InvalidOperationException(
            "The inventory retry loop ended unexpectedly.");
    }
}

public sealed class OrderPipeline
{
    private static readonly ActivitySource ActivitySource =
        new("PipelineFailureExample.OrderPipeline");

    private readonly ValidateOrderStage _validator;
    private readonly ReserveInventoryStage _inventory;

    public OrderPipeline(
        ValidateOrderStage validator,
        ReserveInventoryStage inventory)
    {
        _validator = validator;
        _inventory = inventory;
    }

    public async Task<PipelineResult<OrderReceipt>> RunAsync(
        OrderSubmission input,
        CancellationToken cancellationToken)
    {
        using Activity? activity = ActivitySource.StartActivity(
            "order.pipeline",
            ActivityKind.Internal);

        try
        {
            PipelineResult<ValidatedOrder> validation =
                await _validator.ExecuteAsync(
                    input,
                    cancellationToken);

            if (validation is
                PipelineResult<ValidatedOrder>.Rejected rejected)
            {
                activity?.SetTag("pipeline.outcome", "rejected");
                activity?.SetTag(
                    "pipeline.rejection.code",
                    rejected.Code);

                return new PipelineResult<OrderReceipt>.Rejected(
                    rejected.Code,
                    rejected.Message);
            }

            if (validation is not
                PipelineResult<ValidatedOrder>.Succeeded succeeded)
            {
                throw new InvalidOperationException(
                    "The validation stage returned an unknown result.");
            }

            InventoryReservation reservation =
                await _inventory.ExecuteAsync(
                    succeeded.Value,
                    cancellationToken);

            activity?.SetTag("pipeline.outcome", "succeeded");

            return new PipelineResult<OrderReceipt>.Succeeded(
                new OrderReceipt(
                    succeeded.Value.OperationId,
                    reservation.ReservationId));
        }
        catch (OperationCanceledException)
            when (cancellationToken.IsCancellationRequested)
        {
            activity?.SetTag("pipeline.outcome", "canceled");
            throw;
        }
        catch (Exception exception)
        {
            activity?.SetTag("pipeline.outcome", "failed");
            activity?.SetTag(
                "error.type",
                exception.GetType().Name);
            activity?.SetStatus(ActivityStatusCode.Error);
            throw;
        }
    }
}
```

运行这段代码时，正常输入会先遇到一次 `TransientInventoryException`，随后用相同的 `OperationId` 完成库存预留并输出 `Succeeded`。把数量改成 `0`，验证阶段会输出 `Rejected: order.quantity_out_of_range`，库存网关不会被调用。

这段示例故意把职责切得很窄：验证阶段决定业务拒绝，库存阶段拥有临时错误的重试，管道 runner 负责短路和结果映射，遥测只记录有限的状态值。代码没有承诺通用回滚、exactly-once 或适用于所有依赖的重试策略。

## Result 与异常各自处理什么

Microsoft 的 [.NET 异常最佳实践](https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices)建议，常见条件应尽量用正常控制流处理，无法恢复的异常交给调用栈更高处。放到管道里，可以这样分界：

- 预期拒绝是业务可以预见、调用方需要分支处理的结果，用 `Rejected(Code, Message)` 表达。
- 依赖故障、损坏数据或不变量破坏属于异常，保留异常类型和堆栈，让能恢复的边界决定处理方式。
- 对于高频且可预见的解析失败，优先考虑 `TryParse` 这类已有的非异常 API。

Result 的优点是把普通分支写进方法签名。调用方看到 `Task<PipelineResult<ValidatedOrder>>`，就知道必须处理验证失败。稳定 code 也可以映射为 HTTP 状态、界面消息和测试断言，不必解析异常文本。

它的代价是状态数量增加。每加入一个 Result 分支，所有调用方都多一个需要理解的状态。把十几种未定义清楚的故障都塞进 Result，调用链可能比小型异常层次更难读，也容易把原始堆栈压扁成字符串。

异常的价值在于保留诊断路径，并打断正常数据流。阶段只有在能够恢复，或需要补充上下文后重新抛出时才应该捕获异常。模型选择可以不同，边界需要稳定且能被调用方理解。

## 短路必须写进组合契约

短路表示管道在终态出现后，刻意停止调用后续阶段。它不等于吞掉错误，也不等于返回一个默认值继续运行。

订单例子里，验证拒绝是终态，因为库存阶段只接受 `ValidatedOrder`。runner 将 `Rejected<ValidatedOrder>` 转换为 `Rejected<OrderReceipt>` 后立即返回，库存预留和收据生成都不会发生。

不同组合可以有不同规则：

- 单个订单的校验失败，通常结束这条订单管道；
- 批量内容中某一项被过滤，其他项可能继续处理；
- 安全检查失败，可能终止整个请求；
- 警告结果带着可用输出，可能允许后续阶段继续。

后续阶段能否接受某个结果，应该由类型和组合契约表达。用 `null`、`default` 或空字符串表示「停止」会混淆缺失数据、实现缺陷和业务拒绝，也让错误更晚才暴露。

## 取消保持协作语义

Task-based .NET API 通过 `CancellationToken` 支持协作取消。调用方发出取消请求后，执行代码需要在合适的检查点观察 token 并尽快结束；它不会强制终止一个完全忽略 token 的远程操作。

管道要把 token 传给每个可等待的阶段、外部调用和重试延迟。示例捕获的是 `OperationCanceledException`，并且只在传入的 token 已经请求取消时标记为 `canceled`，之后使用 `throw;` 继续向上传播。

取消发生在副作用之后时，已经完成的库存预留不会自动消失。若业务要求释放库存，需要显式的补偿操作、事务、过期机制或后续 reconciliation 流程。取消表示停止等待和继续执行，不提供回滚承诺。

因此，不要把取消包装成 `Rejected("canceled")`，也不要因为某一步在副作用后观察到取消就返回成功。调用方需要知道任务是否被取消，以及系统是否留下了需要处理的部分效果。

## 副作用让重试变成正确性问题

纯验证通常可以重复执行。库存预留、扣款、发布消息和发送邮件会改变外部状态，第一次请求可能已经成功，只是响应在返回途中丢失。此时再次调用可能产生重复效果。

[Azure Pipes and Filters 模式](https://learn.microsoft.com/en-us/azure/architecture/patterns/pipes-and-filters)也提醒过类似问题：工作可能已完成，但确认信息失败，导致上游重试同一份输入。重试策略必须和幂等保护一起设计。

示例把稳定的 `OperationId` 传给库存边界。内存网关在同一个进程内按这个键保存 reservation；再次收到相同键时返回已经存在的 reservation。这里能得到的保证很窄：这个实现不会为相同键创建第二个库存预留。

它无法证明 exactly-once 执行，也不代表生产环境已经具备持久幂等。真实系统可以使用幂等键表、数据库唯一约束，或把已处理消息 ID 与业务更新放在同一事务中。每种方案都要处理保留时间、冲突、并发竞争和失败窗口。

副作用还会改变短路判断：库存阶段之前拒绝，外部状态尚未产生；库存阶段之后再失败，系统可能已经留下预留记录。管道需要暴露足够稳定的操作标识，让补偿任务能够找到这笔效果。

## 让一个边界拥有重试

重试会重复执行回调。若 HTTP client、库存阶段和调用方各自允许两次尝试，最坏情况可能形成 `2 × 2 × 2 = 8` 次依赖调用。嵌套策略还可能让每一层都误以为自己只做了少量尝试。

更容易审查的做法，是为每个可重试的外部边界指定一个 owner。示例中的 owner 是 `ReserveInventoryStage`，它只做下面几件事：

- 只捕获明确的 `TransientInventoryException`；
- 总共最多尝试两次；
- 两次调用使用相同的幂等键；
- 调用和等待都遵守 `CancellationToken`；
- 最后一次失败继续向上抛出。

验证失败没有重试价值，收据创建也没有被包进库存重试。25 毫秒只用于让示例快速运行，生产系统需要根据依赖 SLA、调用方总期限、退避、抖动和尝试预算设置参数。

如果 HTTP client 或弹性库已经自带重试，要把它算进整体调用次数。扩大一层「保险」并不会自动提高可靠性，可能让总期限耗尽，也可能重复没有幂等保护的副作用。

## 遥测记录结果，不记录一切输入

示例使用 `ActivitySource` 记录管道活动，并将 `pipeline.outcome` 控制在 `succeeded`、`rejected`、`canceled`、`failed` 四个值。拒绝是可预期的业务终态，通常不应直接算作系统错误；意外异常设置 error 状态；取消保留自己的分类。

指标和追踪标签应保持低基数。阶段名、有限的 outcome 值、受控的拒绝 code 和异常类型名可以作为维度；Operation ID、客户 ID、SKU、异常 message 和完整请求内容不适合直接放进广泛采集的指标维度。[OpenTelemetry .NET 指标建议](https://opentelemetry.io/docs/languages/dotnet/metrics/best-practices/)说明了高基数标签会带来存储和性能问题，[敏感数据处理指南](https://opentelemetry.io/docs/security/handling-sensitive-data/)则强调采集者需要自行判断和保护个人信息、凭据、会话令牌与财务数据。

如果需要把指标和单次追踪关联，优先使用 exemplars 或追踪上下文工具，避免把每一个 `TraceId`、`SpanId` 都变成指标标签。遥测的目标是看清管道行为，保留最少的业务数据即可。

## 常见问题

### 每个阶段都必须返回 Result 吗？

不用强制统一。调用方需要明确处理预期替代结果时，Result 很合适；阶段只有成功输出或意外失败时，清晰的 `Task<T>` 也足够。相关阶段之间保持一致，比所有方法套上同一个包装更重要。

### 拒绝结果要不要带可读消息？

可以带，但稳定契约应当是 code。消息可能变化、需要本地化，也不适合用来做分支判断。面向用户的消息还要避免暴露异常细节。

### 被拒绝后能继续后续阶段吗？

只有当组合契约为该结果定义了有效输入时才可以。订单验证拒绝没有 `ValidatedOrder`，因此这条管道应当停止；批处理场景则可以把被拒绝项记录下来，让其他项目继续。

### 幂等键能保证 exactly-once 吗？

不能自动保证。它可以在明确的边界内让相同键映射到一个逻辑效果，但调用本身仍可能发生多次，边界以外的副作用也需要自己的保护。

### 重试应该放在哪里？

放在最小、明确、可重复安全的外部操作周围，并指定唯一 owner。把确定性的验证、宽泛的多副作用区域和已经自带重试的 client 一起包进去前，先计算总尝试次数并确认每次重复都可接受。

## 把错误处理变成管道的一部分

C# 管道的错误处理从结果模型开始。预期拒绝用类型表达并触发短路，意外异常保留原始诊断路径，取消沿着 token 协作传播。开始产生外部副作用以后，幂等键、部分效果、补偿方式和重试 owner 都属于正确性设计。

可以用下面的清单检查一条新管道：

- 是否明确列出了成功、预期拒绝、取消和意外失败？
- 后续阶段是否只能接收合法输入，拒绝时是否立即停止？
- 每个 await 和外部调用是否接收取消 token？
- 哪个边界拥有重试，重复调用是否有幂等保护？
- 遥测是否只记录有限状态和安全的标识？

先让这些答案出现在代码契约和测试里，再决定是否需要更复杂的结果类型或弹性库，管道会更容易阅读、调试和维护。

如果你在实践 C#、.NET 和软件工程设计，欢迎关注 Aide Hub。这里会继续记录可验证的开发工具与工程经验。

## 参考

- [Dev Leader：Error Handling in C# Pipelines（原文）](https://www.devleader.ca/2026/08/26/error-handling-in-c-pipelines-exceptions-results-and-shortcircuiting)
- [.NET：Exception best practices](https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices-for-exceptions)
- [.NET：Task cancellation](https://learn.microsoft.com/en-us/dotnet/standard/parallel-programming/task-cancellation)
- [.NET：Cancellation in managed threads](https://learn.microsoft.com/en-us/dotnet/standard/threading/cancellation-in-managed-threads)
- [Azure Architecture Center：Pipes and Filters pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/pipes-and-filters)
- [Polly：Retry strategy](https://www.pollydocs.org/strategies/retry.html)
- [Polly：Timeout strategy](https://www.pollydocs.org/strategies/timeout.html)
- [.NET：Distributed tracing instrumentation walkthroughs](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/distributed-tracing-instrumentation-walkthroughs)
- [OpenTelemetry .NET：Metrics best practices](https://opentelemetry.io/docs/languages/dotnet/metrics/best-practices/)
- [OpenTelemetry：Handling sensitive data](https://opentelemetry.io/docs/security/handling-sensitive-data/)
