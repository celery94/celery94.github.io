---
pubDatetime: 2026-08-25T13:50:00+08:00
title: "Azure AI Search 混合检索：BM25、向量与RRF"
description: "RAG 的第一阶段检索不该只会一种信号：精确词与概念相似各提供一批候选，再由 RRF 按名次融合。本文给出 Azure AI Search .NET 12 的混合查询示例、教学模型与排错边界。"
tags: ["Azure AI Search", "RAG", "C#", "向量检索"]
slug: "hybrid-search-rag-azure-ai-search"
ogImage: "../../assets/1023/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/24/hybrid-search-for-rag-in-net-bm25-vectors-and-reciprocal-rank-fusion"
---

RAG 应用的第一阶段检索，面对的查询通常同时包含两种需求：有些词必须精确命中——工单号、错误码、产品名、异常类型；有些意思只需要概念相近——用户用「连接超时后怎么回收连接」，源文档写的是「清理失败的数据库会话」。混合检索就是为这类查询设计的第一阶段候选召回方式：词法检索与向量检索并行执行，各自产生一份独立排名的候选清单，再用 Reciprocal Rank Fusion（RRF，倒数排名融合）把两份清单合并成一个有序结果。

本文依据 Nick Cosentino 在 Dev Leader 发布的文章整理，聚焦 Azure AI Search 上的一次直接检索请求——不涉及 Semantic Kernel 等框架封装。读完后，你会得到三样东西：一组防误解的心智模型（BM25 不会变成向量分数，RRF 融合的是名次而不是原始分值）、一段可运行的 `Azure.Search.Documents` 12 混合查询代码，以及一套区分「检索失败」和「生成失败」的排错边界。

## 先建立心智模型

混合检索需要一份同时具备两类字段的索引：`searchable` 文本字段给词法检索提供倒排索引，向量字段给稠密检索提供数值表示。Azure AI Search 把混合检索定义为「一次请求包含全文与向量查询，并行执行，再用 RRF 合并成一个结果集」。

关键是：这份共享索引很重要，但两份候选清单在概念上要保持分离：

- 词法检索回答「哪些文档含有查询中重要的词」；
- 稠密检索回答「哪些文档的向量最接近查询向量」；
- RRF 回答「哪些文档在多个清单里排名都靠前」。

这是检索的组合，而不是把每个相关性判断压成单一分数的邀请。尤其是：直接比较词法原始分与向量原始分得不出任何有用结论——它们来自不同的排名函数、量纲不同。Azure AI Search 融合的是名次，不是把两类原始值当作可互换的分数。

## 词法候选：保留精确的词语

词法检索从文本出发。在 Azure AI Search 中，全文查询搜索标记为 `searchable` 的字段，用 BM25 对匹配文档排名。当查询中的 token 精确形态携带意义时——票号、具名 API、异常类型、版本、法律术语、罕见内部短语——它最有用。

考虑问题「What changed in ERR-AUTH-4017?」稠密检索可以把附近解释与 authentication 关联起来，但无法保证这个精确 token 被表示得像词法匹配那样强势。反过来，文本查询「connection pool exhaustion」会返回重复这些词的素材，却可能漏掉描述「running out of database connections」的块。这是两种不同的候选召回失败模式，而非证明某一方普遍更优。

词法侧除了提供显式查询证据，还正常使用文本索引能力。Azure AI Search 的向量概览文档说明：文本字段与向量字段可以共存于同一索引，过滤器作用于可过滤的文本或数字字段，而不是作用于向量本身。

这个区分对 RAG 元数据很重要：请求可以用可过滤的文本或数字字段限制候选块的范围——文档状态、内容类型、服务端推导的访问域——同时文本查询仍然从 `searchable` 字段生成词法候选。过滤器是资格边界，BM25 是词法排名信号，两者职责分离后请求更容易推理。

## 稠密候选：覆盖改写与概念相似

稠密检索先用于兼容向量字段中存储向量的模型嵌入查询，再搜索最近邻向量。向量字段的维度必须与写入该字段内容的嵌入模型输出匹配。

稠密路径在「问题与相关块用不同词汇表达同一意思」时有用：用户问「How do I reclaim connections after a timeout?」，源文档写「disposing a failed database session」，没有任何精确短语重叠。如果查询与块的嵌入在该含义附近靠拢，向量检索就能把这块加入候选。

但稠密检索并不像人那样阅读文档，它只是按向量搜索配置比较查询向量与已索引向量。输出仍然是排名的候选清单，不是答案，也不保证每个返回块都支持未来的生成声明。RAG 应用应返回或保留块文本、来源标识与元数据，供引用与审查。

这也是为什么查询嵌入与文档嵌入必须视为一份兼容契约：被索引的内容与被搜索的查询，需要预期的向量形状和嵌入空间关系。任何嵌入生成服务都要在发出 Azure AI Search 请求之前守住这条契约。

## RRF 把候选名次变成一个响应

RRF 是 Azure AI Search 混合检索中的合并步骤：接收多份已经排名的结果清单，按位置分配贡献值，求和，再对合并结果排序。一个在两份清单中都靠前的块获得双份贡献；只在单份清单出现的块，只要位置够强也能返回。

标准形式为：

```text
RRF(document) = Σ 1 / (rank + k)
```

其中 `rank` 是文档在某份候选清单中的位置，`k` 是 RRF 常数。Azure AI Search 明确说明其 RRF 常数与向量查询的近邻数量是两回事：向量数量控制多少稠密候选进入合并；RRF 常数塑造排名位置如何贡献到融合顺序。

这个公式也解释了 RRF 为何是词法与稠密检索之间的现实桥梁：它使用位置，而不直接算术组合 BM25 与向量相似度分数。一个文档可以单独从任一路径受益，无需假装底层分数共享量纲。

融合分数只负责排列服务响应，它不是「第一块就足够回答」的声明，也不代表所有候选价值相等，更不意味着检索文本可以当作可信指令。融合只完成第一阶段候选的合并；地面真相、来源归因与后续应用策略仍是独立职责。

## 一次调用完成混合查询

下面的示例使用当前活跃的 .NET SDK 线 `Azure.Search.Documents` 12，把文本查询与 `VectorizedQuery` 放进同一次 `SearchClient.SearchAsync<T>` 调用。不需要第二次请求手工连接两份结果，示例中也没有配置第二阶段的语义排序。

```csharp
using Azure;
using Azure.Search.Documents;
using Azure.Search.Documents.Models;
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

public sealed class RagChunk
{
    public string Id { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public string SourceUri { get; set; } = string.Empty;
    public string TenantId { get; set; } = string.Empty;
}

public static class HybridSearch
{
    public static async Task<IReadOnlyList<RagChunk>> FindCandidatesAsync(
        SearchClient client,
        string question,
        ReadOnlyMemory<float> queryVector,
        CancellationToken cancellationToken)
    {
        var vectorQuery = new VectorizedQuery(queryVector)
        {
            KNearestNeighborsCount = 20,
            Fields = { "contentVector" }
        };

        var options = new SearchOptions
        {
            Filter = "tenantId eq 'contoso'"
        };
        options.Select.Add(nameof(RagChunk.Id));
        options.Select.Add(nameof(RagChunk.Content));
        options.Select.Add(nameof(RagChunk.SourceUri));
        options.VectorSearch = new VectorSearchOptions
        {
            Queries = { vectorQuery }
        };

        Response<SearchResults<RagChunk>> response =
            await client.SearchAsync<RagChunk>(
                question,
                options,
                cancellationToken);

        var chunks = new List<RagChunk>();
        await foreach (SearchResult<RagChunk> result
            in response.Value.GetResultsAsync())
        {
            chunks.Add(result.Document);
        }

        return chunks;
    }
}
```

`question` 参数是词法输入，`queryVector` 是稠密输入，两者同时出现在同一次调用中，这就是混合查询。示例中的过滤器是刻意用的普通语法，让检索机制保持可见；生产应用中，应该从服务端验证的访问策略构造过滤器，并确保 `Select` 的字段包含答案路径需要的来源元数据。

候选召回与 RRF 合并都由服务端完成，你的代码只消费一个有序响应。这与「发一次词法查询、发一次向量查询、再在应用代码里比较或合并它们的分数」完全不同。

可选的全语义排序是 RRF 之后独立的后置阶段，不属于 RRF 本身；启用时 Azure 在 `@search.rerankerScore` 中报告结果，示例有意省略了该配置。

## 一个小型 RRF 模型，理解而非替代

混合请求的 RRF 实现由 Azure AI Search 拥有，不要为了重建服务响应而重复实现它。但一个独立的迷你模型能讲清「为什么名次是融合输入」「为什么在两份清单都出现的文档获得双份贡献」：

```csharp
using System.Collections.Generic;
using System.Linq;

public static class ReciprocalRankFusion
{
    public static IReadOnlyList<string> Fuse(
        IEnumerable<IReadOnlyList<string>> rankedLists,
        int rankConstant = 60)
    {
        return rankedLists
            .SelectMany(list => list.Select(
                (documentId, index) => new
                {
                    DocumentId = documentId,
                    Contribution = 1d / (index + 1 + rankConstant)
                }))
            .GroupBy(item => item.DocumentId)
            .OrderByDescending(group => group.Sum(item => item.Contribution))
            .Select(group => group.Key)
            .ToArray();
    }
}
```

如果词法检索排名 A、B、C，稠密检索排名 B、D、A，那么 B 与 A 从两份清单各得一份贡献，它们的相对结果取决于各自位置；C 与 D 各得一份。方法使用从 1 开始的名次，因为列表索引从 0 开始，而检索位置惯例从 1 开始。

`rankConstant` 在这里暴露，只是让数学形式显式化，不是给 Azure 服务的调参指令。文档说明了服务的 RRF 常数，托管操作自己应用合并行为——此示例是名次融合的教学辅助，不是托管操作的替代品。

## 融合之后的 RAG 边界

融合响应是一组候选。答案路径仍要做：保留来源信息、选择提供给模型的有界上下文、为实际用作证据的素材附上引用。好的检索结果不等于正确的生成答案。

这个边界对排错尤其有用：

- 如果答案缺少相关来源——检查词法查询、查询嵌入、向量字段兼容性、元数据资格与融合候选位置，这些都在候选检索内部；
- 如果相关来源在候选里，但答案没有反映它——失败发生在候选检索之后，属于生成或上下文组装环节。

把这两个问题分开，可以避免把每个坏答案都当成笼统的模型问题。Azure AI Search 的 API 版本指南确认 `Azure.Search.Documents` 12 是当前的 .NET SDK，并说明此前的 2023-07-01-preview REST API 已于 2024 年 4 月 8 日弃用、2024 年 7 月 8 日起不再支持。实现应当留在服务文档化的当前稳定面上，并保持概念区分：词法候选、稠密候选，然后是名次融合。

## 常见问题

- **BM25 会搜索向量字段吗？** 不会。BM25 是 `searchable` 文本字段的词法排名路径，向量查询针对向量字段；两条路径可以指向同一篇文档，但字段与排名方法不同。
- **向量检索需要精确关键词匹配吗？** 不需要。它按配置的相似度关系对向量排名，措辞不同也能召回概念相关的文本；但它不会取代词法检索对标识符等精确词的价值。
- **RRF 是把 BM25 分数和向量分数相加吗？** 不是。RRF 依据文档在各自排名清单中的名次合并贡献，避免假设不同算法的原始分数共享量纲。
- **混合请求能用过滤器吗？** 可以。向量查询可以包含作用于可过滤文本或数字字段的过滤表达式；把过滤器视为资格规则，并将过滤、词法排名、稠密排名、融合分开对待。
- **融合后的结果就是 RAG 答案吗？** 不是。它是有序候选清单；RAG 应用仍需选择证据、构建有界上下文、生成响应并保留引用。

## 总结

混合检索更容易排错的前提，是每个操作只干一件事：词法检索保留精确查询语言，稠密检索补充概念匹配，RRF 把两份排名候选合成为服务响应。把这条顺序在代码与遥测里保持可见，再把拿到的块当作证据候选而不是完成的答案。

这项能力适合所有把 RAG 当做生产管道而不是演示应用的团队。如果你的索引里只有向量字段、检索结果在数字和准确术语上经常失手，这可能就是下一步要加的检索信号；反过来，如果已经有文本检索，也只差一步：把相同的文档切块编码成向量，放入同一索引，然后把两类查询合并成一次混合调用。

如果这类 AI 助手、开发工具和软件工程实践对你有帮助，欢迎关注 Aide Hub。这里会继续记录可验证的工具与工程经验。

## 参考

- [Nick Cosentino：Hybrid Search for RAG in .NET: BM25, Vectors, and Reciprocal Rank Fusion（原文）](https://www.devleader.ca/2026/08/24/hybrid-search-for-rag-in-net-bm25-vectors-and-reciprocal-rank-fusion)
- [Azure AI Search：hybrid search overview](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview)
- [Azure AI Search：hybrid search ranking（BM25 与 RRF）](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)
- [Azure AI Search：vector search overview（过滤器与字段）](https://learn.microsoft.com/en-us/azure/search/vector-search-overview)
- [Azure AI Search：vector search quickstart（VectorizedQuery）](https://learn.microsoft.com/en-us/azure/search/search-get-started-vector)
- [Azure AI Search：API 版本指南（SDK 12 与 2023-07-01-preview 弃用）](https://learn.microsoft.com/en-us/azure/search/search-api-versions)
