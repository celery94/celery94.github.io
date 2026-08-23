---
pubDatetime: 2026-08-23T16:12:00+08:00
title: "C# 异步流水线：顺序等待、取消与完成"
description: "已经会用 async/await 后，如何把多个有依赖的 I/O 步骤组成正确流水线？本文用完整可运行示例讲清顺序等待、取消传播、任务完成信号与资源释放边界，并列出常见错误。"
tags: ["C#", ".NET", "Async/Await", "CancellationToken", "Pipeline"]
slug: "csharp-async-pipeline-await-cancellation-completion"
ogImage: "../../assets/1013/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/22/async-pipelines-in-c-await-cancellation-and-completion"
---

处理文本导入时，经常遇到加载文档、规范化内容、写回文件这类必须按顺序执行的步骤。每一步都可能等待 I/O，但下一步又依赖上一步的输出。这篇文章围绕一个完整例子，说明怎样用 `Task` 和 `await` 把这些步骤整理成明确的流水线，并在取消、完成、资源释放三个边界上做对。适合已经了解基本 `async/await`，想把多个依赖步骤整理成统一生命周期的 C# 开发者。

本文根据 Nick Cosentino 在 Dev Leader 于 2026 年 8 月发布的文章整理，文中示例以 2026 年 8 月仍是受支持 `.NET 10` LTS、默认使用 C# 14 为基线。你可以直接照着代码运行；如果想先补基础的 `async/await` 概念，可以看原文推荐的入门文章。

## 顺序执行不等于并行

一个可用的流水线模型有三个简单组成：

- 每个阶段接收一个明确类型的输入。
- 每个阶段返回 `Task<TOutput>`。
- 下一个阶段只在前一个阶段的任务被 `await` 并得到输出后启动。

这里的顺序来自依赖关系。比如 `ImportRequest -> LoadedDocument -> NormalizedDocument -> ImportReceipt`，规范化步骤必须拿到已经加载的文档，写入步骤必须拿到已经规范化的内容。让后一个阶段提前运行，只会把真实依赖藏进状态、回调或事件里。

顺序执行也不同于单线程执行。`await` 会暂停当前异步方法，让未完成的 I/O 操作自行推进；续体可能在不同线程恢复。文章关心的保证是单次流水线内阶段的先后，线程身份属于另一件事。

最后要明确一点：多个阶段依次 `await` 表示它们有依赖，所以不会并行。它也不会自动带来吞吐量的提升。

## 完整示例：一次文档导入

先创建一个面向 `net10.0` 的控制台项目，并启用可空引用类型：

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
```

把下面代码放进 `Program.cs`。它读取一个文本文件，把连续空白压缩成单个空格，再写入另一个文件，所有阶段共享同一个取消令牌。

```csharp
using System.Text;

namespace AsyncPipelineExample;

public sealed record ImportRequest(
    string SourcePath,
    string DestinationPath);

public sealed record LoadedDocument(
    string SourcePath,
    string DestinationPath,
    string Content);

public sealed record NormalizedDocument(
    string DestinationPath,
    string Content);

public sealed record ImportReceipt(
    string DestinationPath,
    int CharacterCount);

public interface IAsyncStage<TInput, TOutput>
{
    Task<TOutput> ExecuteAsync(
        TInput input,
        CancellationToken cancellationToken);
}

public sealed class LoadDocumentStage
    : IAsyncStage<ImportRequest, LoadedDocument>
{
    public async Task<LoadedDocument> ExecuteAsync(
        ImportRequest input,
        CancellationToken cancellationToken)
    {
        await using FileStream stream = new(
            input.SourcePath,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            bufferSize: 4096,
            FileOptions.Asynchronous);

        using StreamReader reader = new(
            stream,
            Encoding.UTF8,
            detectEncodingFromByteOrderMarks: true,
            bufferSize: 4096,
            leaveOpen: true);

        string content = await reader.ReadToEndAsync(cancellationToken);

        return new LoadedDocument(
            input.SourcePath,
            input.DestinationPath,
            content);
    }
}

public sealed class NormalizeDocumentStage
    : IAsyncStage<LoadedDocument, NormalizedDocument>
{
    public Task<NormalizedDocument> ExecuteAsync(
        LoadedDocument input,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();

        string normalized = string.Join(
            ' ',
            input.Content.Split(
                (char[]?)null,
                StringSplitOptions.RemoveEmptyEntries));

        return Task.FromResult(
            new NormalizedDocument(
                input.DestinationPath,
                normalized));
    }
}

public sealed class WriteDocumentStage
    : IAsyncStage<NormalizedDocument, ImportReceipt>
{
    public async Task<ImportReceipt> ExecuteAsync(
        NormalizedDocument input,
        CancellationToken cancellationToken)
    {
        await File.WriteAllTextAsync(
            input.DestinationPath,
            input.Content,
            Encoding.UTF8,
            cancellationToken);

        return new ImportReceipt(
            input.DestinationPath,
            input.Content.Length);
    }
}

public sealed class DocumentImportPipeline
{
    private readonly IAsyncStage<ImportRequest, LoadedDocument> _loader;
    private readonly IAsyncStage<LoadedDocument, NormalizedDocument> _normalizer;
    private readonly IAsyncStage<NormalizedDocument, ImportReceipt> _writer;

    public DocumentImportPipeline(
        IAsyncStage<ImportRequest, LoadedDocument> loader,
        IAsyncStage<LoadedDocument, NormalizedDocument> normalizer,
        IAsyncStage<NormalizedDocument, ImportReceipt> writer)
    {
        _loader = loader;
        _normalizer = normalizer;
        _writer = writer;
    }

    public async Task<ImportReceipt> RunAsync(
        ImportRequest request,
        CancellationToken cancellationToken)
    {
        LoadedDocument loaded = await _loader.ExecuteAsync(
            request,
            cancellationToken);

        NormalizedDocument normalized =
            await _normalizer.ExecuteAsync(
                loaded,
                cancellationToken);

        ImportReceipt receipt = await _writer.ExecuteAsync(
            normalized,
            cancellationToken);

        return receipt;
    }
}

public static class Program
{
    public static async Task Main()
    {
        string sourcePath = Path.Combine(
            AppContext.BaseDirectory,
            "pipeline-input.txt");

        string destinationPath = Path.Combine(
            AppContext.BaseDirectory,
            "pipeline-output.txt");

        await File.WriteAllTextAsync(
            sourcePath,
            "Pipeline    stages\nremain ordered.",
            Encoding.UTF8);

        var pipeline = new DocumentImportPipeline(
            new LoadDocumentStage(),
            new NormalizeDocumentStage(),
            new WriteDocumentStage());

        using var cancellationSource =
            new CancellationTokenSource(TimeSpan.FromSeconds(10));

        try
        {
            ImportReceipt receipt = await pipeline.RunAsync(
                new ImportRequest(sourcePath, destinationPath),
                cancellationSource.Token);

            Console.WriteLine(
                $"Wrote {receipt.CharacterCount} characters to " +
                $"{receipt.DestinationPath}.");
        }
        catch (OperationCanceledException)
            when (cancellationSource.IsCancellationRequested)
        {
            Console.WriteLine("The import was canceled.");
        }
        finally
        {
            File.Delete(sourcePath);
            File.Delete(destinationPath);
        }
    }
}
```

运行时，`LoadDocumentStage` 和 `WriteDocumentStage` 使用异步文件 API，这会让运行着的方法在 I/O 未完成时让出线程。`NormalizeDocumentStage` 的工作在内存中完成，所以它先检查取消状态，再返回 `Task.FromResult`。没有真实异步工作时不加 `async`，也不用 `Task.Run` 包装同步计算；后者只会引入提前安排的线程池调度，并不会让流水线更正确。

流水线本身只负责组合。它知道阶段顺序，并把上一个阶段的返回值传给下一个阶段。单个阶段需要什么输入、返回什么结果、怎样响应取消，都由 `IAsyncStage<TInput, TOutput>` 表达。

## `await` 之后的顺序能验证

只要阶段实现遵循一个约定，顺序就比较容易验证：只有前面阶段的任务完成后，后面阶段才拿到输入。`RunAsync` 中三次 `await` 都在当前一行上暂停，所以流程静态可见，不需要靠日志猜测某个阶段是否提前开始。

为了让成功路径更确定，示例把一段带多余空白和换行的文本写入输入文件。`NormalizeDocumentStage` 会把 `"Pipeline    stages\nremain ordered."` 处理成 `"Pipeline stages remain ordered."`，因此输出信息里的字符数会是 `31`。这里的字符来自实际写入内容，可用来检查格式化是否正确。

## 接口把生命周期收进一个任务

`IAsyncStage<TInput, TOutput>` 只有一次 `ExecuteAsync` 调用。它没有单独暴露 `Start` 和 `WaitForCompletionAsync`。把一次操作拆成两个方法，容易产生已经开始但没有 `await`、重复启动或提前释放等问题。一次调用返回一个任务，生命周期的起止边界就清楚。

接口还要求调用方显式传 `CancellationToken`。默认令牌在部分公共 API 里很方便，但放在阶段边界上，会让取消传播变得不可见。组合器无法偷偷调用一个不带令牌的重载，也就不会出现“外部取消只影响前半段”的状态。

阶段返回值还应该代表已经完成的工作。`WriteDocumentStage` 只有在 `WriteAllTextAsync` 完成后才返回 `ImportReceipt`。如果阶段返回一个尚未完成任务的句柄，下游代码就很难判断它能不能安全使用结果。

时间预算也应有明确归属。示例把十秒预算放在应用入口，并传给整条流水线。每个阶段各自再加一层无关超时并不会更清晰；多个互相独立的截止时间叠加，只会让调用方更难解释取消原因。

## 取消是一个传播的请求

.NET 的取消是协作式的。`CancellationTokenSource` 发出取消请求，参与代码需要接收令牌、在安全位置检查请求，然后自行停止。令牌不能强制展开任意方法，也不能撤销已经完成的工作。

示例里，同一个令牌传到了加载阶段、`StreamReader.ReadToEndAsync`、规范化阶段、写入阶段和 `File.WriteAllTextAsync`。任何一层丢掉令牌，取消都可能停在流水线中间，留下“上层已取消、下层还在写”的混淆生命周期。

同步阶段同样要配合。`NormalizeDocumentStage` 在处理前调用 `ThrowIfCancellationRequested()`。对于很短的字符串操作，一次检查足够；如果循环执行大量 CPU 计算，需要按不变式选择更多检查点。在共享状态修改到一半时取消，可能比继续执行更危险。

响应速度还取决于底层操作。传入令牌意味着底层的可取消操作了解请求，不代表任何机器指令都会立即中止。文档里描述这种行为时，通常说“请求取消”比“杀掉阶段”更准确。

创建 `CancellationTokenSource` 的一方拥有它。示例里的 `Main` 创建令牌源、把令牌传给流水线、等待完成，再用 `using` 释放。阶段只接收令牌，不会释放自己没有创建的资源。

## 取消保持为取消

流水线内部没有必要捕获每一次 `OperationCanceledException`。当前示例没有恢复动作，就让异常穿过返回的 `Task`。应用边界只有在自己的令牌源确实请求了取消时，才捕获并处理这个异常。

这样三种结果可以明确区分：

- 正常返回代表所有阶段完成。
- 取消路径代表协作请求停住了操作。
- 异常路径代表某个阶段出现了未预期的错误。

取消后不要返回默认的 `ImportReceipt`，那会让不完整的结果看起来成功。也不要为了加上下文把取消异常包成 `InvalidOperationException`，那样会抹掉调用方需要的语义。如果写入已经完成才收到取消，已写入文件仍然存在；如果写入中途被取消，是否可能留下部分文件、怎样处理，需要业务层明确说明，`CancellationToken` 自身不负责补偿或事务。

## 完成信号就是返回任务

这种直接组合模型不需要单独布尔状态。`RunAsync` 返回的 `Task<ImportReceipt>` 就是整条流水线的完成信号。阶段负责完成自己的任务，流水线按顺序等待，调用方负责等待流水线返回的任务。

流水线内部的 fire-and-forget 是危险的。假设写入阶段启动一个内部任务，却立刻返回收据，流水线会提前报告完成；内部异常可能无人观察，调用方也可能在写入仍在运行时释放依赖或退出进程。修复方向是让阶段把全部承诺工作放进一个任务，并只在该任务完成后再表示完成。

调用方也不能丢掉 `RunAsync` 返回的任务。入口可以直接 `await`，请求处理器可以把它纳入请求生命周期。外部组件若同时跟踪多条流水线，应按照自身生命周期保留并观察每条任务；把任务藏进静态集合或脱离的回调，并不能让完成信息更可靠。

`async void` 会破坏这条链。除了真正的 UI 或框架事件处理器，普通方法应返回 `Task`，这样调用方才有可能观察完成和异常。

## 资源在所有权边界释放

异步阶段经常接触生命周期短于流水线的资源，例如文件流、响应流或异步枚举器。`LoadDocumentStage` 创建了 `FileStream`，所以由它负责释放；代码用 `await using` 处理异步释放，`StreamReader` 先于底层流释放，`leaveOpen: true` 让顺序明确。

`DocumentImportPipeline` 没有实现 `IAsyncDisposable`。它只持有阶段引用，没有长期存活且需要异步清理的资源。加入空的 `DisposeAsync` 会暗示不存在的生命周期工作。

如果流水线确实创建并拥有一个长期资源，它才应该实现 `IAsyncDisposable`：先停止接收新执行，等待所有活动任务完成，再释放依赖。释放不能和仍在使用资源的阶段赛跑。消息所有权也要写清；示例传的是不可变记录和字符串，不需要下游释放。如果消息携带流，契约应说明是由产生阶段转移所有权，还是保留并负责释放。

## 常见错误

把异步流水线当成并行流水线。阶段之间有依赖，按顺序 `await` 保证顺序，不会重叠这些阶段。

在上一步输入还没出现时启动下一步。写入阶段需要规范化结果，就必须先等规范化完成。

用 `Task.Run` 包装本来的异步 I/O。文件、HTTP 和数据库 API 通常已经返回 `Task`；再加一层线程池调度，对当前顺序模型没有帮助。

在某一个边界丢掉取消令牌。外部传进来的令牌要进入真正执行工作的可取消操作。

吞掉异常或取消结果，仍然执行下一步。第二阶段没有产出时，第三阶段不能假装拿到合法输入；返回伪造值只会把故障推迟到更难定位的地方。

用多播委托组合返回结果的异步阶段。C# 委托规则下，只有最后一个返回值能直接取得；应该逐个显式调用并 `await` 每个返回任务的阶段。

## 适用边界

这种直接组合适合单个对象沿已知顺序前进、阶段主要等待 I/O 的场景。类型转换清晰可见，调用方也能用一个任务代表完整操作。

它不适合作为通用编排模型。业务流需要分支、等待外部事件或跨进程重启继续时，线性进程内流水线往往不够；这些需求应该在设计时单独引入持久化和调度机制，让执行模型变化成为显式架构决策。

## 验证方式

在项目目录运行 `dotnet run`，成功路径会输出类似：

```text
Wrote 31 characters to /path/to/bin/Debug/net10.0/pipeline-output.txt.
```

路径会随平台和输出目录变化。运行结束后，`finally` 会删除输入和输出文件，所以不需要手动清理。

验证取消路径时，可以在传入流水线前调用 `cancellationSource.Cancel()`，再执行 `RunAsync`。此时读取或规范化阶段会观察到取消，`catch` 分支的 `IsCancellationRequested` 为真，控制台显示 `The import was canceled.`。

如果只改了阶段顺序或某个阶段返回伪造结果，最直接的检查是看输出字符数、文件内容以及是否出现未观察异常。更完整的做法是给每个阶段单元测试：成功路径返回完成结果，取消路径抛出 `OperationCanceledException`，异常路径只传播原错误。

## 常见问题

**每个阶段都 `await`，流水线会变同步吗？** 不会。阶段按依赖顺序等待，但 `await` 会在 I/O 未完成时让出执行。顺序描述依赖关系，同步描述另一种执行行为。

**每个阶段方法都要写 `async` 吗？** 不需要。`Task.FromResult` 可以返回已经完成的结果；只有方法需要等待异步工作或需要状态机控制流时，才使用 `async`。不要为了“看起来异步”加延迟或 `Task.Run`。

**`CancellationTokenSource` 应该在哪里创建？** 在拥有取消策略的边界创建，比如请求处理器、命令处理器或应用入口，并把令牌向下传递。创建者在参与工作完成后释放令牌源。

**阶段应该捕获 `OperationCanceledException` 吗？** 只有阶段有清理或跨契约翻译等具体责任时才捕获。没有恢复动作时直接让取消传播，避免把取消改造成普通故障。

**流水线什么时候实现 `IAsyncDisposable`？** 当它拥有需要异步清理、且生命周期超过单次阶段调用的资源时。决定依据是资源所有权，方法出现 `await` 本身并不足以决定释放契约。

## 总结

一个正确的 C# 异步流水线可以保持得很简单：每个阶段接收明确输入，返回 `Task<TOutput>`，按依赖顺序 `await`，把同一个 `CancellationToken` 传进所有可取消边界，并让返回任务代表整次执行。阶段只负责自己拥有的资源，调用方负责等待和观察结果。

这个模型刻意保持顺序。它解决的是非阻塞等待和生命周期清晰，没有宣称依赖阶段能够并行。未来如果执行模型需要变化，应作为独立的架构决策处理。

如果你正在写后端处理流程，或者想继续看 .NET 与 C# 的工程实践，欢迎关注 Aide Hub。我们会继续分享 AI 助手、开发工具和软件工程实践。

## 参考

- [Async Pipelines in C#: Await, Cancellation, and Completion（原文，Nick Cosentino）](https://www.devleader.ca/2026/08/22/async-pipelines-in-c-await-cancellation-and-completion/)
- [Asynchronous programming with async and await（官方异步编程指南）](https://learn.microsoft.com/en-us/dotnet/csharp/asynchronous-programming/)
- [await operator（官方运算符文档）](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/await)
- [Cancellation in managed threads（官方取消指南）](https://learn.microsoft.com/en-us/dotnet/standard/threading/cancellation-in-managed-threads)
- [Task-based asynchronous programming（官方任务取消指南）](https://learn.microsoft.com/en-us/dotnet/standard/parallel-programming/task-cancellation)
- [Task Class（官方 API 参考）](https://learn.microsoft.com/en-us/dotnet/api/system.threading.tasks.task?view=net-10.0)
- [Implement a DisposeAsync method（官方异步释放指南）](https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/implementing-disposeasync)
- [Using delegates（官方委托指南）](https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/delegates/using-delegates)
- [C# language versioning（官方语言版本说明）](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/language-versioning)
