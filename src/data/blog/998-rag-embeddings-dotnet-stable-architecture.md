---
pubDatetime: 2026-08-12T14:46:00+08:00
title: ".NET RAG 稳定架构：边界先于实现"
description: "RAG 不是聊天功能，是数据系统。本文给出与模型、向量库、框架无关的稳定架构：来源溯源、嵌入边界、授权检索、引用契约、删除闭环，附可编译的概念性 C# 契约代码。"
tags: ["RAG", "AI", "Dotnet", "Architecture", "Embeddings"]
slug: "rag-embeddings-dotnet-stable-architecture"
ogImage: "../../assets/998/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/12/rag-and-embeddings-in-net-a-stable-architecture-guide"
---

RAG 和 embeddings 在 .NET 里最容易理解错的方式，是把它们当成一个聊天功能。它们实际上是一个**以生成文本结尾的数据系统**。一个有用的回答，依赖四件事依次成立：来源变成可信的 chunk、查询变成兼容的向量、检索尊重访问规则、最终回答展示它的证据。任何一条边界出错，系统都可以照样自信地输出——但内容可能是错的、过时的，或者越权的。

Nick Cosentino（Dev Leader）在 2026 年 8 月的这篇指南只讲架构层：**刻意不选模型、不选向量数据库、不选编排框架**。那些是实现决策，应该在契约、数据所有权和失败处理都清楚之后再做。如果你要框架级实现，他已有的 Semantic Kernel RAG 指南是配套读物；这篇要建立的是任何实现都必须保留下来的系统骨架。

这篇文章适合：正在设计或维护 RAG 系统、担心「换向量库就得重写」的 .NET 开发者。读完你会得到四条稳定边界、一份可编译的概念性 C# 契约，以及一套事故时可以问的问题。

## 两条路径：摄取与回答

RAG 的实际流程有两条完全不同的路径：

- **摄取路径（ingestion）**：接纳来源 → 提取并分块 → 记录溯源与权限 → 生成 embeddings → 写入可搜索的表示
- **回答路径（answer）**：认证调用者 → 推导访问范围 → 嵌入问题 → 检索合格证据 → 构建有界上下文 → 生成回答 → 返回引用

**生成放在最后是有原因的**：它不应该拥有身份、来源准入、文档生命周期或检索策略。应用应该能换掉模型客户端而不重写删除工作流，换掉索引而不丢失溯源。

这个分离也解释了为什么简单原型看起来「能工作」：硬编码的样本语料没有权限变化、没有畸形上传、没有索引滞后、没有过期缓存，也不需要解释为什么检索到某个结果。生产数据全都有。

## 摄取是经过审计的转换

摄取把源文档变成派生数据，而派生数据并不比源数据低一等——chunk、embedding、索引、响应缓存都能影响用户看到什么。

第一步是在分块之前分配**持久的文档身份**：保留源 URI 或仓库身份、修订版本、摄取时间戳、内容哈希、准入主体。然后把文档身份和授权元数据**携带到每个 chunk 上**——一个没有来源和访问范围的 chunk，是「等待变成安全 bug 的孤儿」。

OWASP RAG Security Cheat Sheet 明确要求：摄取时哈希文档、保留溯源、扫描内容、只准入批准来源。这些不是 embedding 调用旁边的装饰，而是让后续调查和删除成为可能的控制。

原文给出了一份 provider-neutral 的领域模型，所有例子合成一个可编译的 C# 10+ 概念文件。第一块是共享 using 和必须活过分块的溯源记录：

```csharp
using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace RagArchitecture;

public sealed record SourceDocument(
    string Id,
    Uri SourceUri,
    string Title,
    string Version,
    DateTimeOffset IngestedAt,
    string IngestedBy,
    string Sha256,
    IReadOnlySet<string> AllowedPrincipals);

public sealed record DocumentChunk(
    string Id,
    string DocumentId,
    int Ordinal,
    string Text,
    SourceDocument Source);

public static class DocumentIntegrity
{
    public static string CreateSha256(string content)
    {
        return Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(content)));
    }
}
```

**分块是检索设计决策，不是 SDK 复选框**：chunk 要保留足够多的局部语义来回答问题，又要足够小，让检索集不至于挤掉答案。边界策略、重叠策略、提取器版本都应该是显式摄取配置。架构层面的要点更简单：**改分块策略等于产生一个新的派生语料**，推广之前需要评估。

摄取 worker 应该先**暂存（stage）**文档：验证类型和来源、规范化文本、计算哈希、分配元数据，然后**只有整个文档成功后才让它的 chunk 可检索**。这避免了「半本新手册和半本旧手册并存可搜索」的尴尬状态，也给删除一个稳定键：源文档 ID。

## Provider-neutral 的嵌入边界

嵌入生成器接收文本、产生向量。向量搜索拿查询向量和索引向量比较，所以文档与查询的表示必须和索引配置兼容（Azure AI Search 文档明确这一点）。如果系统要改这个契约，迁移必须是刻意的：**版本化嵌入模型 → 重新嵌入受影响的 chunk → 重新评估检索 → 旧表示安全后才退役**。

所以 embeddings 放在一个本地边界后面：应用拥有文本准备、模型版本记录、重试策略和是否索引的决策；provider 实现只拥有远程或本地推理调用。Microsoft 的 `IEmbeddingGenerator<TInput, TEmbedding>` 是一个有用的集成缝，但应用契约不应依赖框架特定的类型。

```csharp
public sealed record EmbeddingVector(
    string ModelId,
    ReadOnlyMemory<float> Values)
{
    public int Dimensions => Values.Length;
}

public interface IEmbeddingGenerator
{
    Task<EmbeddingVector> GenerateAsync(
        string text,
        CancellationToken cancellationToken);
}

public sealed record AccessScope(IReadOnlySet<string> PrincipalIds);

public sealed record RetrievalRequest(
    EmbeddingVector QueryVector,
    AccessScope Access,
    int MaximumResults);
```

注意这里**缺了什么**：provider 客户端、API key、用户提供的 tenant filter。这些关注点真实存在，但属于各自的边界。**访问范围必须由服务端从已认证的调用者推导，而不是信任浏览器在 JSON 里带的 tenant ID。**

向量只是检索信号之一。精确标识符、产品代码、日期和名字通常需要词法匹配。**混合检索**（hybrid）组合词法与向量候选生成，**重排序**（reranking）是在候选集上的后期精度步骤——它们解决不同的问题，不要因为某个存储产品暴露了一个 `SearchAsync` 方法就把它们压成一个概念。架构应该能分别表示：词法检索、稠密检索、融合、元数据过滤、可选二阶段 reranker。

## 围绕检索结果和引用构建

面向回答生成的 RAG 系统，检索应该产出**带证据的结果**而不是纯文本：选中了哪个 chunk、来自哪个来源修订、在哪个访问范围下、分数多少。生成器可以消费文本，但应用必须在 prompt 之外保留这些证据。

这对调试至关重要：坏回答可能来自没有相关 chunk、排序太弱、过滤过宽、来源修订缺失、或者综合得不好。没有类型化的检索结果，每一种失败看起来都像「模型编造了答案」。

```csharp
public sealed record RetrievedChunk(DocumentChunk Chunk, double Score);

public interface IChunkIndex
{
    Task ReplaceDocumentAsync(
        SourceDocument document,
        IReadOnlyList<IndexedChunk> chunks,
        CancellationToken cancellationToken);

    Task<IReadOnlyList<RetrievedChunk>> SearchAsync(
        RetrievalRequest request,
        CancellationToken cancellationToken);

    Task DeleteByDocumentIdAsync(
        string documentId,
        CancellationToken cancellationToken);
}

public sealed record IndexedChunk(
    DocumentChunk Chunk,
    EmbeddingVector Vector);

public sealed record Citation(
    string DocumentId,
    string ChunkId,
    Uri SourceUri,
    string Title,
    string Version,
    string Sha256);
```

**引用是契约，不是渲染细节**：它让 UI 能显示来源链接，让运维能回放一次响应，让审查者能确认回答引用的修订确实是实际检索到的那份。这比要求模型在散文里编造脚注强得多。

Microsoft 的安全多租户 RAG 架构指南把访问边界说得很明确：身份流过请求路径，只有授权的 grounding 数据能到达模型；存储前面放 API 层，让授权和过滤不散落在应用各处。这正好映射到 `AccessScope` 和 `IChunkIndex`：索引实现返回候选之前先强制作用域。

## 回答组装契约保持显式

回答组装边界保留「用户问题 → 选中的 chunk → 生成文本 → 返回引用」之间的链接。它不决定检索到的 chunk 是否可信，也不授予授权——那些决策发生在来源准入和检索阶段。

```csharp
public sealed record UserQuestion(string Text);

public sealed record GeneratedAnswer(
    string Text,
    IReadOnlyList<string> SupportingChunkIds);

public interface IAnswerGenerator
{
    Task<GeneratedAnswer> GenerateAsync(
        UserQuestion question,
        IReadOnlyList<RetrievedChunk> evidence,
        CancellationToken cancellationToken);
}

public sealed record RagAnswer(
    string Text,
    IReadOnlyList<Citation> Citations);

public interface IRagAnswerResult;

public sealed record GroundedRagAnswer(RagAnswer Answer) : IRagAnswerResult;

public sealed record AnswerWithheld(string Reason) : IRagAnswerResult;

public interface IAnswerComposer
{
    Task<IRagAnswerResult> ComposeAsync(
        GeneratedAnswer generated,
        IReadOnlyList<RetrievedChunk> evidence,
        CancellationToken cancellationToken);
}
```

两个契约细节值得强调：

- `ReplaceDocumentAsync` 是**文档级推广边界**：实现先暂存该修订的每个 chunk 和向量，整个操作成功后才让该修订可检索；失败时要保留旧修订或返回失败
- `IAnswerComposer` 在检索没有合格证据、或 `SupportingChunkIds` 出现证据之外的 ID 时，必须返回 `AnswerWithheld`——**不能返回带着缩短引用列表的生成文本**

## 授权、安全与删除是检索需求

授权必须在 prompt 构造之前完成。每个 chunk 都需要访问控制元数据，检索边界用服务端推导的作用域强制执行。**文本进入 LLM 上下文之后再过滤已经太晚**——OWASP 要求访问控制在内容到达模型之前完成。模型不能是「调用者能不能看这个 chunk」的权威。

检索到的文本是数据，不是指令。OWASP 建议：清晰分隔检索内容、限制 chunk 的数量和总大小、扫描可疑内容、验证输出、保留完整管道痕迹。这些控制降低风险，但不会让 prompt injection 变得不可能——所以来源准入、最小权限和输出控制要协同工作。

embeddings 值得和源文本同样的对待。**embeddings 不是匿名数据**（OWASP 明确提醒），需要与来源等效的访问控制。向量索引是安全敏感的派生存储：写入只给摄取服务，查询只能穿过检索边界。

删除闭环：当来源被移除、取代或失去权限时，删除它的 chunk、embeddings 和缓存响应，并保留审计事件。`IChunkIndex` 的删除操作很小，但它代表一条触及所有派生工件的工作流——**一个缺失的源文档，不能因为它的 embedding 被遗忘而仍然可检索**。

## 让质量与运维在用户报告之前可见

把**评估**和**可观测性**分开：

- 评估回答「检索是否找到有用证据、回答是否被证据支持」
- 可观测性解释「这次请求实际发生了什么」：来源修订、嵌入模型 ID、检索数量、应用的访问范围、选中的 chunk ID、各阶段延迟、缓存决策

评估要**分开做**：检索可能漏掉需要的 chunk，可能返回太多无关上下文，也可能证据没问题但生成器写出了无依据的回答。用一小批人工评审的问题（带预期文档或 chunk ID），比一个宽泛的基准分数更早暴露这些失败。评估数据也有生命周期：语料修订会让预期的 chunk ID 失效，即使应用代码没变——每个测试用例都要记录语料修订。

追踪 ID 应该连接摄取、检索、生成和删除，但默认不要把原始敏感 prompt 或文档放进遥测。目标是**可回放的证据，而不是第二个无治理的语料副本**。

这套架构在事故时给你一组可回答的问题：这个 chunk 被批准了吗？哪个来源修订产生了它？检索发生时调用者有访问权吗？回答限于检索到的证据吗？缓存是否跨越了权限变化？这些问题之所以可回答，是因为系统保留了需要的契约。

## 常见问题

**RAG 和 embeddings 的最小架构是什么？** 至少要有：来源溯源、chunk 身份、嵌入边界、带服务端强制访问范围的检索、回答边界、引用。在语料变得难以推理之前，加上显式删除和遥测路径。

**embeddings 能取代关键词搜索吗？** 不能。embeddings 检索概念相似性，关键词检索保留精确词法信号。它们是独立的候选生成器，必要时再加融合策略。

**每个回答都要存引用吗？** 存储构造引用所需的证据（来源、chunk、修订、哈希）。是否展示给用户是产品决策，但保留证据让验证和运维成为可能。

**可以在模型看到文本之后再强制授权吗？** 不能作为保护机密性的控制。授权要在检索和 prompt 构造之前完成，生成后控制只是次要防线。

**源文档变更或删除怎么办？** 用源文档 ID 找到所有派生 chunk 和向量，删除或重建，使权限作用域的缓存失效，记录结果。把这条工作流当作摄取设计的一部分，而不是事后清理。

**有引用就自动是事实吗？** 不是。引用只显示检索到了哪些证据，不证明检索完整、来源最新、或生成措辞忠实于来源。评估和来源治理仍然必要。

## 稳定的心智模型

RAG 里持久的部分不是一个包调用，而是一条**责任链**：

> 批准来源 → 版本化 chunk → 兼容 embedding → 授权检索 → 检索证据 → 引用回答 → 来源变更 → 完整删除

先建这些边界。然后模型客户端、向量存储、混合策略、reranker 或框架都可以演化，而不至于把整个系统变成一次重写。

## 参考

- [RAG and Embeddings in .NET: A Stable Architecture Guide（原文，Nick Cosentino）](https://www.devleader.ca/2026/08/12/rag-and-embeddings-in-net-a-stable-architecture-guide)
- [Secure multitenant RAG architecture | Microsoft Learn](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/secure-multitenant-rag)
- [Vector search overview | Microsoft Learn（Azure AI Search）](https://learn.microsoft.com/en-us/azure/search/vector-search-overview)
- [OWASP RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)
- [IEmbeddingGenerator<TInput, TEmbedding> | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/ai/iembeddinggenerator)
