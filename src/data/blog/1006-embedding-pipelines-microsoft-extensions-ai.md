---
pubDatetime: 2026-08-18T07:49:00+08:00
title: "Microsoft.Extensions.AI 嵌入管道"
description: "嵌入生成在摄取与查询两处出现，需要同一个类型化边界。用 Microsoft.Extensions.AI 10.7 稳定 API 讲清嵌入管道：类型化契约、批量与单条生成、缓存与遥测装饰、嵌入身份与兼容性。"
tags: [".NET", "AI", "C#", "Architecture"]
slug: "embedding-pipelines-microsoft-extensions-ai"
ogImage: "../../assets/1006/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/16/embedding-pipelines-in-net-with-microsoftextensionsai"
---

`IEmbeddingGenerator` 给应用文本与检索用向量之间划了一条聚焦的边界。这条边界有价值，是因为嵌入生成出现在两个地方：语料进入系统时（摄取），以及用户提问时（查询）。两条路径应该共用同一个类型化契约，同时把缓存、追踪、限流和提供商专属配置留在清晰的接缝上。

Nick Cosentino（Dev Leader）这篇 2026 年 8 月的文章，基于 Microsoft.Extensions.AI.Abstractions 10.7.0 的稳定嵌入 API，讲的是**产生和处理嵌入**，不涉及选模型、也不实现向量库操作。配套的 RAG 工作流指南（Semantic Kernel 系列）是框架层面的补充读物。

适合：正在设计或维护 RAG 系统、想让嵌入步骤独立可理解、可替换的 .NET 开发者。读完你会得到：一个类型化嵌入边界、批量与单条生成的写法、缓存与遥测的组合方式，以及嵌入身份与兼容性怎么管理。

## 从一个类型化契约起步

嵌入是把输入表示成数值空间里的向量。检索系统嵌入文档块、嵌入问题，然后把向量交给检索层。嵌入生成器不决定哪些文档有效、块怎么存、答案怎么生成。

稳定的抽象是 `IEmbeddingGenerator<TInput, TEmbedding>`。文本管道里最常见的形态是 `IEmbeddingGenerator<string, Embedding<float>>`：`TInput` 描述送去嵌入的值，`Embedding<float>` 通过 `ReadOnlyMemory<float> Vector` 暴露向量。

10.7.0 的契约要求并发使用、使用期间不得释放实例，并警告调用方不要在并发调用间共享可变的 `EmbeddingGenerationOptions`（除非实现保证不会修改它）。

把契约做成一个小型应用服务的依赖，会让摄取代码对自己真正需要什么保持诚实，也让查询路径用同一个抽象、不必知道具体是哪个客户端在推理：

```csharp
using Microsoft.Extensions.AI;

public sealed record TextChunk(string Id, string Text);

public sealed record EmbeddedChunk(
    string Id,
    string Text,
    ReadOnlyMemory<float> Vector);

public sealed class ChunkEmbedder(
    IEmbeddingGenerator<string, Embedding<float>> generator)
{
    public async Task<IReadOnlyList<EmbeddedChunk>> EmbedAsync(
        IEnumerable<TextChunk> chunks,
        CancellationToken cancellationToken)
    {
        var chunkList = chunks.ToArray();

        GeneratedEmbeddings<Embedding<float>> embeddings =
            await generator.GenerateAsync(
                chunkList.Select(chunk => chunk.Text),
                cancellationToken: cancellationToken);

        return chunkList
            .Zip(
                embeddings,
                (chunk, embedding) => new EmbeddedChunk(
                    chunk.Id,
                    chunk.Text,
                    embedding.Vector))
            .ToArray();
    }
}
```

顺序很重要。方法接收一组输入、为每个输入返回一个嵌入：在调用生成器之前保留源 chunk 的 ID，代码就能把返回的向量和产生它的那个 chunk 精确对应起来。不要把向量当成脱离输入与语料元数据漂移的匿名 `float[]`。

抽象并不承诺「文档嵌入和查询嵌入因为都是 float 就兼容」——那是应用契约。把嵌入模型标识和向量维度与索引语料一起存储，再用配置为同一表示的查询生成器查询。不同的向量形状、或不同嵌入契约下生成的向量，需要显式的迁移与重新索引计划。

## 批量生成让摄取有节制

嵌入调用有边界成本：工作要离开应用、在执行方里跑、再返回结果。`GenerateAsync` 把批量显式化：摄取时一组 chunk 可以通过一次操作完成，应用同时保留它们的身份。

批量不是构建无界列表的许可。批次大小要有界，适配实现与它文档化的输入限制。嵌入抽象提供的是集合操作，不提供统一的批次大小、令牌策略或重试策略：

```csharp
using Microsoft.Extensions.AI;

public sealed class EmbeddingBatchProcessor(
    IEmbeddingGenerator<string, Embedding<float>> generator)
{
    public async Task<IReadOnlyList<ReadOnlyMemory<float>>> CreateVectorsAsync(
        IEnumerable<string> texts,
        int batchSize,
        CancellationToken cancellationToken)
    {
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(batchSize);

        var vectors = new List<ReadOnlyMemory<float>>();

        foreach (string[] batch in texts.Chunk(batchSize))
        {
            GeneratedEmbeddings<Embedding<float>> generated =
                await generator.GenerateAsync(
                    batch,
                    cancellationToken: cancellationToken);

            vectors.AddRange(generated.Select(embedding => embedding.Vector));
        }

        return vectors;
    }
}
```

这个方法有一个重要局限：光有向量列表不足以上索引。生产摄取还需要文本或它的稳定引用、chunk 顺序、源身份、源修订、访问元数据和创建向量的嵌入契约。这个管道的边界设计，就是为了让嵌入步骤能独立被理解。

用户问题通常不需要批量。`GenerateVectorAsync` 直接表达单输入场景，返回原始向量值，检索实现收到向量即可，不必耦合任何提供商客户端：

```csharp
using Microsoft.Extensions.AI;

public sealed record EmbeddedQuery(
    string Text,
    ReadOnlyMemory<float> Vector);

public sealed class QueryEmbedder(
    IEmbeddingGenerator<string, Embedding<float>> generator)
{
    public async Task<EmbeddedQuery> EmbedAsync(
        string question,
        CancellationToken cancellationToken)
    {
        ReadOnlyMemory<float> vector = await generator.GenerateVectorAsync(
            question,
            cancellationToken: cancellationToken);

        return new EmbeddedQuery(question, vector);
    }
}
```

摄取路径和问题路径应该在同一个兼容边界汇合，而不是各抄一段提供商专属代码。这个区别在语料需要重新嵌入时尤其有用：应用记录旧嵌入契约，通过同一个生成器边界构建新表示，验证检索行为，然后才退役旧表示。

## 在生成器之前处理文本与失败

生成器收到的文本，应该已经通过应用对来源的规则。这不意味着每条管道都需要一个复杂的规范化框架，而是你要决定这些规则住在哪里：例如摄取路径可以拒绝空 chunk、保留产生 chunk 的源修订、在任何向量创建前应用文档化的文本预处理策略。

这很重要，因为**改变预处理就是改变被索引的表示**。折叠空白、去掉样板文本、改变切分方式，都会改变送给生成器的输入。把预处理版本和模型标识一起记录，把两者的任何变更都当成新的嵌入契约——后面缓存键的例子也是这个原因。

查询路径同样需要清楚的策略。用户问题可能为空、超过应用定义的请求限制、或因为调用方断开被取消。这些是应用层结果，不该让向量库去解释。在调用生成器之前检查它们，把请求取消令牌传下去，嵌入无法进行时返回受控结果。

还要避免用全零向量悄悄替换失败的嵌入。占位向量在下一层看起来有效，但它不代表产生它的文本：摄取时污染索引，查询时生成无关候选。让嵌入操作带着足够上下文失败，调用方可以重试、记录失败、或让该源修订不进可检索语料。

摄取时通常意味着暂存派生工作：为一个源修订创建 chunk 和向量，确认每个所需嵌入都已返回，然后才让其他组件把修订提供给检索。嵌入抽象不定义这个事务边界，但它的类型化批量结果让边界实现起来很直接——一个批次要么给应用每个输入对应的向量，要么让应用把修订留在待定状态。

重试的范围也因此受限：重试瞬时生成器失败应该复用同一文本与嵌入契约；操作者改了预处理或模型配置后的重试不是同一操作——它产生新表示，需要新元数据和一次有意的评估。

## 横切行为：缓存与遥测

嵌入生成是放横切行为的好地方，因为每个摄取与查询请求都经过它。Microsoft.Extensions.AI 提供 `EmbeddingGeneratorBuilder<TInput, TEmbedding>` 组合实现与装饰器，包括分布式缓存和 OpenTelemetry 插桩。

装饰器的顺序有行为：缓存包在追踪外面，和追踪包在缓存外面，留下的追踪足迹不同。没有哪个顺序普遍正确，关键是决定你的遥测要观察应用代码发出的每个请求、只观察真正到达底层生成器的工作、还是通过独立信号两者都要。

下面的工厂把实现与缓存作为依赖收进来，刻意不构造提供商客户端——凭据、端点配置和模型命名留在应用的组合根：

```csharp
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Caching.Distributed;

public static class EmbeddingPipeline
{
    public static IEmbeddingGenerator<string, Embedding<float>> Create(
        IEmbeddingGenerator<string, Embedding<float>> innerGenerator,
        IDistributedCache cache,
        EmbeddingContract contract,
        string sourceName)
    {
        var cachedGenerator =
            new DistributedCachingEmbeddingGenerator<string, Embedding<float>>(
                innerGenerator,
                cache)
            {
                CacheKeyAdditionalValues =
                new object[]
                {
                    contract.GeneratorName,
                    contract.ModelId,
                    contract.Dimensions,
                    contract.NormalizationVersion
                }
            };

        return new EmbeddingGeneratorBuilder<string, Embedding<float>>(
                cachedGenerator)
            .UseOpenTelemetry(sourceName: sourceName)
            .Build();
    }
}
```

`DistributedCachingEmbeddingGenerator` 用 `CacheKeyAdditionalValues` 扩充缓存键，所以这条管道把嵌入契约的每个字段都放进每个键。它缓存的是**已完成**的嵌入、不是进行中的请求，所以并发的缓存未命中仍可能重复工作；装饰器的并发安全取决于它的 `IDistributedCache`。

OpenTelemetry 回答的是另一个问题：一次嵌入请求期间发生了什么。10.7.0 里 `OpenTelemetryEmbeddingGenerator.EnableSensitiveData` 默认 `false`，除非设置 `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`。要显式设置并审查它——开启后可能记录敏感的附加属性。

需要限流或其他 builder 没提供的策略时，`DelegatingEmbeddingGenerator<TInput, TEmbedding>` 是文档化的扩展点：它把调用转发给内层生成器，让一个专注的装饰器强制一个关注点。

## 缓存与遥测需要嵌入身份

只按输入文本缓存很诱人，但同一段文本可能在多个契约下嵌入。显式身份让这个操作边界可见：

```csharp
public sealed record EmbeddingContract(
    string GeneratorName,
    string ModelId,
    int Dimensions,
    string NormalizationVersion);
```

维度包含在内，因为检索索引通常期望固定向量形状；模型 ID 与规范化版本包含在内，因为即使维度数不变，语义表示也可能变化。

追踪时，作者希望有足够信息把请求和它的行为连起来，而不暴露输入：有用的信号包括嵌入契约标识、请求的值的数量、向量维度、缓存结果与耗时。

## 提供商适配器放在哪里

`IEmbeddingGenerator<string, Embedding<float>>` 是抽象，不是嵌入模型或网络协议。具体应用仍然要注册或创建做推理的实现。稳定版 10.7.0 包含基于 OpenAI 2.11.0 构建的 `Microsoft.Extensions.AI.OpenAI`；而 OpenAI .NET 2.12.0 已标记为稳定版。

这些版本细节是易变的，也正是把适配器注册放在应用边缘、而不是把具体客户端散落在索引与查询类里的原因。上面的核心代码只要求 `IEmbeddingGenerator`，提供商注册可以独立版本化与测试。

这条边界也避免把通用嵌入管道变成选型文章：生成器的元数据与应用定义的嵌入契约，才是记录「实际用了什么」的正确位置。检索行为应该针对应用真正关心的语料与问题来评估，而不是从包名推断。

## 常见问题

- **IEmbeddingGenerator 在管道里做什么？** 接受输入值、异步返回它们的嵌入。对文本检索，`IEmbeddingGenerator<string, Embedding<float>>` 给应用代码一个生成向量的类型化位置，不依赖具体提供商客户端。
- **单个问题也要调 GenerateAsync 吗？** 可以，但 `GenerateVectorAsync` 是单输入的文档化便捷方法，返回 `ReadOnlyMemory<float>`，当下一个边界只接受一个查询向量时很方便。
- **批量会保证特定请求大小吗？** 不会。`GenerateAsync` 接受集合，但提供商限制与输入约束在通用契约之外。在应用代码里界定批次，并校验注册的具体实现的限制。
- **缓存键只放输入文本可以吗？** 可以，但风险是返回早期嵌入契约下创建的向量。`DistributedCachingEmbeddingGenerator` 支持通过 `CacheKeyAdditionalValues` 加入身份；把模型或生成器身份与文本预处理版本都放进去，表示变化时才会得到不同缓存条目。
- **UseOpenTelemetry 会记录文档文本吗？** `EnableSensitiveData` 默认 false，除非设置 `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`。显式设置并审查比假设部署默认值更安全。
- **ITextEmbeddingGenerationService 正式废弃了吗？** 作者没有下这个结论：已检查的当前源码确立了本文使用的 Microsoft.Extensions.AI 抽象，但没有确立旧 Semantic Kernel 接口的正式废弃状态。

## 保持边界小而可观测

嵌入管道在操作上更容易，当嵌入生成是一条小而类型化的边界：批量处理 chunk 同时保留身份；用同一个契约生成单个查询向量；用缓存与遥测装饰生成器；把这些关注点和它们服务的嵌入表示一起版本化。

剩下的系统可以专注自己的职责：切分准备源文本、检索找合格证据、生成解释证据。嵌入管道只做一件事，但它让周围的 RAG 系统更容易追踪和演化。

Aide Hub 持续分享 AI 助手、开发工具与软件工程实践。想把这套边界用起来，可以从 ChunkEmbedder + QueryEmbedder 两个小服务开始，再按需要加 EmbeddingContract 与缓存装饰。

## 参考

- [Embedding Pipelines in .NET with Microsoft.Extensions.AI（原文，Nick Cosentino）](https://www.devleader.ca/2026/08/16/embedding-pipelines-in-net-with-microsoftextensionsai)
- [IEmbeddingGenerator<TInput, TEmbedding> | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/ai/iembeddinggenerator)
- [IEmbeddingGenerator API 参考 | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/api/microsoft.extensions.ai.iembeddinggenerator-2)
- [dotnet/extensions v10.7.0 Release Notes](https://github.com/dotnet/extensions/releases/tag/v10.7.0)
- [OpenAI .NET 2.12.0 发布记录](https://github.com/openai/openai-dotnet/releases/tag/OpenAI_2.12.0)
- [DistributedCachingEmbeddingGenerator 源码（v10.7.0）](https://raw.githubusercontent.com/dotnet/extensions/v10.7.0/src/Libraries/Microsoft.Extensions.AI/Embeddings/DistributedCachingEmbeddingGenerator.cs)
- [OpenTelemetryEmbeddingGenerator 源码（v10.7.0）](https://raw.githubusercontent.com/dotnet/extensions/v10.7.0/src/Libraries/Microsoft.Extensions.AI/Embeddings/OpenTelemetryEmbeddingGenerator.cs)
- [RAG with Semantic Kernel in C#（作者配套指南）](https://www.devleader.ca/2026/03/01/rag-with-semantic-kernel-in-c-complete-guide-to-retrievalaugmentedgeneration)
