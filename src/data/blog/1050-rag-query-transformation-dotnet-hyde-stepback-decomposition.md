---
pubDatetime: 2026-09-02T10:08:00+08:00
title: "RAG 查询变换：HyDE、Step-Back 与分解"
description: "三种查询变换都不是改写：HyDE 造假设文档当检索键、Step-Back 上移抽象层级、分解拆多跳问题。本文用与模型和向量库无关的 .NET 契约实现它们，并给出合并与基线对照评估。"
tags: [".NET", "RAG", "AI", "Architecture", "Embeddings"]
slug: "rag-query-transformation-dotnet-hyde-stepback-decomposition"
ogImage: "../../assets/1050/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/01/rag-query-transformation-in-net-hyde-stepback-and-decomposition"
---

用户只问了一个问题，检索层却可能用好几个「问题」去找证据：一篇假设的说明文档、一个更上位的原理、几条拆开的子问题。这就是 RAG 查询变换（query transformation）——在 embedding 和搜索之前改变检索输入。它有一个必须守住的边界：**变换改变的是证据怎么被找到，不是答案可以引用什么**。询问者的问题仍然是一个，应用的搜索输入可以变成几个；但最终回答只能依据检索返回的真实语料块，任何由模型生成的文本都只是检索键，不是证据，也不能作为引用来源。

这个边界把三种常被混为一谈的技术分开：HyDE 用假设文档改变**检索表示**，Step-Back 把问题**上移一个抽象层级**，分解把一个问题拆成**多个独立的证据请求**。它们针对的检索失败不同，代价也不同，所以不应该「装上就完事」。

需要先说明一个 .NET 开发者最容易踩的坑：Microsoft.Extensions.AI 不提供 HyDE、Step-Back 或问题分解的内置 API。它能给你的是 `IEmbeddingGenerator<TInput, TEmbedding>`、`Embedding<float>.Vector` 和 `GenerateVectorAsync` 这类嵌入工具（本文示例用 10.7.0 验证，NuGet 最新已到 10.9.0；官方 API 文档中可选参数 `EmbeddingGenerationOptions` 位于 `CancellationToken` 之前）。文本生成属于另一个边界，要自己接。这也意味着查询变换本质上是你自己的应用逻辑，而不是某个框架的开关。

## 先跑一版基线：原问题直接检索

在加任何一次模型调用之前，先定义原问题能检索到什么。基线负责固定五个变量：用户提供的词汇、embedding 模型、检索过滤器、候选数量和语料库版本。没有它，一个「看起来变好了」的变换结果没有可比对象。

典型的密集检索流程里，问题变成向量，检索器返回带分数的语料块。用最少的契约把这个流程固定下来：

```csharp
using Microsoft.Extensions.AI;

public sealed record RetrievalHit(
    string DocumentId,
    string ChunkId,
    string Text,
    double Score);

public interface IVectorRetriever
{
    Task<IReadOnlyList<RetrievalHit>> SearchAsync(
        ReadOnlyMemory<float> queryVector,
        CancellationToken cancellationToken);
}

public sealed class BaselineQueryRetriever(
    IEmbeddingGenerator<string, Embedding<float>> embeddingGenerator,
    IVectorRetriever retriever)
{
    public async Task<IReadOnlyList<RetrievalHit>> SearchAsync(
        string question,
        CancellationToken cancellationToken)
    {
        ReadOnlyMemory<float> vector = await embeddingGenerator
            .GenerateVectorAsync(question, cancellationToken: cancellationToken);

        return await retriever.SearchAsync(vector, cancellationToken);
    }
}
```

这段代码刻意没有 `HydeAsync`、`StepBackAsync` 或 `DecomposeAsync` 方法。这类命名会暗示 Microsoft.Extensions.AI 定义了某种库契约，而实际上没有。产生文本的组件应该待在本地接口的另一侧，embedding 与检索则保持独立可测。

这个位置也是与既有系统保持清晰边界的地方：查询变换不是新的文档摄取流程、不是 agent 循环、也不是 web 搜索兜底，它只是对**已有语料**的搜索输入做决策。

## 一个契约接住所有变换

最简单的有用契约是：从原问题产生零到多个字符串。基线策略只返回原问题；变换策略可以返回原问题加上一个或多个附加检索键。检索层不需要知道某个键为什么存在。

```csharp
using Microsoft.Extensions.AI;

public delegate Task<IReadOnlyList<string>> QueryTransform(
    string question,
    CancellationToken cancellationToken);

public sealed class TransformedQueryRetriever(
    IEmbeddingGenerator<string, Embedding<float>> embeddingGenerator,
    IVectorRetriever retriever,
    QueryTransform transform)
{
    public async Task<IReadOnlyList<IReadOnlyList<RetrievalHit>>> SearchAsync(
        string question,
        CancellationToken cancellationToken)
    {
        IReadOnlyList<string> retrievalKeys = await transform(
            question,
            cancellationToken);

        var searches = retrievalKeys.Select(async key =>
        {
            ReadOnlyMemory<float> vector = await embeddingGenerator
                .GenerateVectorAsync(key, cancellationToken: cancellationToken);

            return await retriever.SearchAsync(vector, cancellationToken);
        });

        return await Task.WhenAll(searches);
    }
}
```

`QueryTransform` 刻意保持 provider-neutral：它的实现可以是调用模型、确定性改写规则，也可以是经审阅的词表扩展。应用拥有校验、日志策略、取消，以及「是否把生成文本送去检索」的决策权。模型专用的提示词不是可移植的 .NET API，应该留在 provider 适配器里，而不是伪装成库接口。

原问题通常应该保留在检索键中。它保住了直达精确术语、标识符和原始措辞的路线，这条路线在更抽象的键里很容易丢失。键一多，候选集就需要明确的合并策略——看完全部三种变换再处理它。

## HyDE：嵌入的是假设文档，不是答案

HyDE（Hypothetical Document Embeddings，假设文档嵌入）最初是为零样本稠密检索提出的。做法是让语言模型生成一份与问题相关的**假设文档**，把生成结果嵌入后，用它的向量去语料库检索真实文档。原论文明确写了：生成的文档可能包含错误细节。所以它只是一个检索键，不是证据，更不是要展示给读者看的内容。

为什么这个思路有用？一句简短的「为什么索引返回过时的策略？」在 embedding 空间里，可能和一段解释性叙述更接近，而不是和语料里确切的措辞更接近。假设的解释性文档正好补上这个词汇缺口。但检索仍然必须返回语料里的 chunk，最终 grounding 也必须来自这些 chunk。

实现上这个限制应该可见：假设文档是附加键，原问题保留。上面那个本地 `QueryTransform` 契约足以表达这个规则，不需要把文本生成指令包装成发明出来的 API。下游的答案组装器拿到的应该是检索 chunk 及其溯源，而不是把假设文档当成引用候选。

HyDE 也不是衡量本语料检索质量的手段的替代品。论文报告的是它自己零样本设置下的研究结果，不代表换一个 embedding 模型、换一个领域、换一组查询分布也能普遍提升。被精确产品名、错误码或短标识符主导的语料，行为可能和解释性散文为主的语料非常不同。

## Step-Back：检索支配性概念

Step-Back Prompting 描述的做法是：从细节密集的问题中提炼高层概念和第一性原理，再用抽象结果引导推理。放到检索时间，有用的适配是加一个表达**支配概念**的搜索键——这个键不是回答原问题，而是点出语料可能以哪个概念解释这个问题。

它和改写有本质区别。改写通常保持近似相同的细节层级；Step-Back 故意向上移动：

| 原问题                               | 可能的 Step-Back 检索意图        |
| ------------------------------------ | -------------------------------- |
| 「为什么删除的手册还出现在回答里？」 | 「派生索引的删除传播与过期检索」 |
| 「权限更新后策略结果缺失，为什么？」 | 「授权元数据与检索过滤的一致性」 |

这个方向只有在语料里确实存在能帮助回答具体问题的概念材料时才有用。Step-Back 键也可能宽过头：检索回一堆入门材料，挤掉关于真实问题的证据。所以把它当作**一个**可辨识的检索键，与基线合并后检查候选集的变化，而不是替换检索策略。

顺带一提，这里和语料准备有天然联系：chunk 边界决定了宽泛原理和具体流程是共存于一个 chunk，还是被拆到不同位置。变换无法修复一个相关事实从未以可检索形式进入索引的语料——这通常要回到分块策略上解决。

## 分解：多跳问题变成多个证据请求

问题分解解决的是另一种检索失败。有些问题需要来自多个来源的事实：整个问题合成一个向量，会低估解决它所需的各个独立事实。

Question Decomposition 论文描述了这样的管道：把多跳问题分解成子问题、为每个子问题检索段落、合并候选、再对合并池重排序。它的前提对任何自实现都有用：**每个子问题都应该独立可理解，能检索到整体答案中某一部分的证据**。

但不要默认分解所有查询。直接的事实问题只会被拆出重复搜索。以下情况才算候选：比较类问题需要两个事实、序列类问题需要前置知识、或者结论依赖分布在不同文档里的证据。

结果需要保留结构，应用才能知道哪个子问题产生了哪些候选：

```csharp
public sealed record SubQuestion(
    string Id, string Text);

public sealed record CandidateSet(
    string RetrievalKeyId,
    IReadOnlyList<RetrievalHit> Hits);

public static class Decomposition
{
    public static IReadOnlyList<SubQuestion> KeepDistinct(
        IEnumerable<SubQuestion> subQuestions)
    {
        return subQuestions
            .Where(question => !string.IsNullOrWhiteSpace(question.Text))
            .DistinctBy(question => question.Text.Trim(),
                StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }
}
```

子问题由变换生产者提供；这段纯 BCL 代码负责保持稳定 ID、去掉重复文本。保留溯源不是洁癖：当合并结果出乎意料时，你能分辨它来自基线、抽象概念、假设文档、还是某个特定子问题。它也让「发生了很多次检索」不再是 trace 里唯一能解释结果的东西。

## 合并候选：先做身份去重，不做排序

多个检索键产生多个候选列表。论文的做法是把各子问题找到的段落聚合成扩展池，再用**原始复杂问题**对池子做一次重排序。下面这个示例只实现聚合部分。

每个候选有复合身份 `(DocumentId, ChunkId)`——仅在单个文档内唯一的 chunk ID，不能和另一个文档的 chunk 合并：

```csharp
public sealed record CandidateIdentity(
    string DocumentId,
    string ChunkId);

public sealed record MergedCandidate(
    CandidateIdentity Identity,
    IReadOnlySet<string> RetrievalKeyIds);

public static class CandidateMerge
{
    public static IReadOnlyList<MergedCandidate> ByDocumentAndChunk(
        IEnumerable<CandidateSet> candidateSets)
    {
        return candidateSets
            .SelectMany(set => set.Hits.Select(hit => (set.RetrievalKeyId, hit)))
            .GroupBy(item => new CandidateIdentity(
                item.hit.DocumentId,
                item.hit.ChunkId))
            .OrderBy(group => group.Key.DocumentId, StringComparer.Ordinal)
            .ThenBy(group => group.Key.ChunkId, StringComparer.Ordinal)
            .Select(group => new MergedCandidate(
                group.Key,
                group
                    .Select(item => item.RetrievalKeyId)
                    .ToHashSet(StringComparer.Ordinal)))
            .ToArray();
    }
}
```

结果是确定性的、按身份排序的池子，保留每个候选来自哪个检索键，**刻意不做**原始分数合并和相关性排序。这里有明确区分：**候选合并不是重排序**。合并决定哪些身份限定过的结果可供后续选择；排序策略决定它们的优先顺序。被引用的分解管道也做了同样的「先聚合、后重排」区分，所以它的评估结果并不表示这个未排序池子已经是最终结果列表。

## 评估：变换只是检索假设

论文把检索结果和最终答案分开报告，这是检索证据属于工作本身、而不是事后补充的原因。

本地对比的做法是：准备一组经人工审阅的问题，为每个问题标注「应该支撑答案」的文档限定 chunk ID；用**同一个**语料版本、embedding 模型、过滤器和候选预算，分别跑基线和每种变换，先逐个查询检查结果，再选择聚合度量。

这是确定性的 recall-at-K 辅助方法，它只检查预期 chunk ID 是否出现在检索结果前缀里，不判断生成答案是否正确：

```csharp
public sealed record RetrievalJudgment(
    string QuestionId,
    IReadOnlySet<CandidateIdentity> ExpectedCandidateIds);

public static class RetrievalMetrics
{
    public static double RecallAtK(
        RetrievalJudgment judgment,
        IReadOnlyList<RetrievalHit> hits,
        int k)
    {
        if (judgment.ExpectedCandidateIds.Count == 0)
        {
            return 0;
        }

        int found = hits
            .Take(k)
            .Select(hit => new CandidateIdentity(
                hit.DocumentId,
                hit.ChunkId))
            .Distinct()
            .Count(judgment.ExpectedCandidateIds.Contains);

        return (double)found / judgment.ExpectedCandidateIds.Count;
    }
}
```

每次对比都记录：变换类型、检索键、语料版本、embedding 模型标识符、过滤器、top-K、合并后的候选 ID 和判定结果。这些字段让审阅者能判断结果变化到底来自变换、检索池、还是之后的排序策略。

原论文证明了这些方法值得尝试，但没有提供可以迁移到你语料的结果。把基线当对照，准备一组覆盖四类问题的人工审阅集——直接问题、词汇缺口问题、抽象偏重的问题、多跳问题——这是比「HyDE 一定有效」更扎实的评估基础。

## 怎么选：三类问题对应三种变换

把方法还原成检索假设，选择就清楚了：

| 你怀疑的失败             | 变换      | 前提                 | 主要风险                  |
| ------------------------ | --------- | -------------------- | ------------------------- |
| 用户词汇与语料表述不一致 | HyDE      | 语料以解释性散文为主 | 假设文档被当成证据引用    |
| 细节问题缺概念入口       | Step-Back | 语料含对应的概念材料 | 键太宽，检索回入门内容    |
| 答案依赖多个来源的事实   | 分解      | 子问题可独立检索     | 直接问题被拆出重复搜索    |
| 直接事实问题             | 不变换    | 基线核对过召回       | 白白增加延迟和 token 成本 |

几个常见问题，答案都在前面的边界里：HyDE 没有「总是用」的说法，它的作用取决于语料、embedding 模型和查询集；Step-Back 与改写不同，改写通常保住细节层级，Step-Back 刻意上移；HyDE 生成的文档可能含有编造细节，只能当检索键，回答中只能引用真实语料块；多个变换键的候选先按文档限定身份去重并保留溯源，融合或重排序作为独立策略另行评估。

## 落地清单

把这篇文章压缩成可执行步骤：

1. **先有基线**：原问题直接嵌入检索，记录语料版本、模型、过滤器、候选数。
2. **保留原问题**：任何变换都把它留在检索键里，保住精确措辞路线。
3. **每个变换键可标识**：trace 里能区分基线、抽象概念、假设文档、某个子问题。
4. **同一个已验证的嵌入 seam**：模型专用指令留在 provider 适配器，不伪装成库 API。
5. **合并保留 provenance**：按 `(DocumentId, ChunkId)` 身份去重，排序另行评估。
6. **对照人工审阅的基线**：先逐查询检查，再上聚合指标。

HyDE 改变检索表示，Step-Back 改变抽象层级，分解把一个问题变成多个证据请求——这是三种关于「语料如何表达知识」的不同假设，应该被当作不同的假设来对待。这样得到的是一个能从自己语料上学习的检索系统，而不是一个悄悄积累聪明提示词的系统。

如果你正在搭建或维护 .NET RAG，Aide Hub 会继续分享 AI 助手、开发工具与软件工程实践。

## 参考

- 原文：Nick Cosentino, [RAG Query Transformation in .NET: HyDE, Step-Back, and Decomposition](https://www.devleader.ca/2026/09/01/rag-query-transformation-in-net-hyde-stepback-and-decomposition)
- [HyDE: Precise Zero-Shot Dense Retrieval without Relevance Labels](https://arxiv.org/abs/2212.10496)
- [Take a Step Back: Evoking Reasoning via Abstraction in Large Language Models](https://arxiv.org/abs/2310.06117)
- [Question Decomposition for Retrieval-Augmented Generation](https://arxiv.org/abs/2507.00355)
- Microsoft Learn, [IEmbeddingGenerator<TInput, TEmbedding>](https://learn.microsoft.com/en-us/dotnet/ai/iembeddinggenerator)
- Microsoft Learn, [GenerateVectorAsync API 参考](https://learn.microsoft.com/en-us/dotnet/api/microsoft.extensions.ai.embeddinggeneratorextensions.generatevectorasync)
- Dev Leader, [RAG with Semantic Kernel in C# 完整指南](https://www.devleader.ca/2026/03/01/rag-with-semantic-kernel-in-c-complete-guide-to-retrievalaugmented-generation)
- Dev Leader, [Chunking Strategies for RAG with Semantic Kernel in C#](https://www.devleader.ca/2026/03/16/chunking-strategies-for-rag-with-semantic-kernel-in-c-fixedsize-sentence-and-semantic-chunking)
