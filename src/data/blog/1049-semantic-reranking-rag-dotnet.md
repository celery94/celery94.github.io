---
pubDatetime: 2026-09-01T12:05:00+08:00
title: "Azure AI Search 语义重排：RAG 的第二级检索"
description: "语义重排不是召回：它只重排第一级检索给出的候选。本文讲清 Azure AI Search semantic ranker 的能力边界（top 50、2000 token、0–4 分），并用 C# 给出语义配置、查询和证据投影的完整示例。"
tags: ["RAG", "Azure AI Search", ".NET", "C#", "语义检索"]
slug: "semantic-reranking-rag-dotnet"
ogImage: "../../assets/1049/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/28/semantic-reranking-for-rag-in-net-a-secondstage-retrieval-model"
---

RAG 上线一段时间后，最常见的抱怨是「检索到了，但顺序不对」：正确的那条证据在第一页末尾，简单问题答得还行，稍微深一点就整段胡编。这时候最容易被建议的方案是「加个语义重排」。

Nick Cosentino（Dev Leader）2026 年 8 月 28 日的这篇文章先把概念钉死：**语义重排是第二级精度操作，不是第二段召回**。它不会发现缺失的文档，只对第一级检索已经返回的候选做一次更昂贵的相关性判断，把好结果挪到前面。所以它不能替代索引、查询嵌入、访问过滤或第一级检索——这些职责仍然属于前面的管道。

本文以该文为底，保留三份 C# 代码（语义配置、查询、证据投影），并把文中引用的 Azure 官方限制逐一核对到 2026-09-01 的最新文档。先记住一个设计约束：想让重排器发挥作用，必须先在候选集里找到有用的证据——**重排器修复的是「候选在但在不合适的位置」，不是「候选不在」**。

## 两级检索各自回答什么

- 第一级检索回答：哪些文档值得考虑？（候选生成）
- 第二级重排回答：这些候选里，哪个最能回答当前问题？（排序）

两者的失败模式也不同。相关片段不在候选集里，语义重排无能为力；相关片段在但顺序无用，重排能改变送到读者或生成提示词的内容。因此在 RAG 管道里最好保持三条明确的边界：

1. **候选检索**产出有界、授权的候选集；
2. **语义重排**按查询与文本的含义给这个集合重新打分排序；
3. **上下文组装**挑选最高分证据，并保留来源元数据。

这篇文章有意止步于第二条边界——候选怎么来属于前面的检索工作；排序怎么用属于后面的组装与生成。

## Azure semantic ranker 实际重排什么

Azure AI Search 的语义排名器是厂商特定、已正式发布的 **L2 排名能力**：查询侧功能，用语言理解模型作用于初始结果集。.NET SDK 里语义相关性值通过 `result.SemanticSearch.RerankerScore` 读出，查询响应里还能拿到抽取式标题（caption）或答案。

它最关键的边界是：**semantic ranker 最多只看前 50 条初始结果**。这直接决定你的第一级检索必须把有效证据放进这 50 条里，重排才有意义。一个很高的重排分数只说明「到站的候选质量好」，不证明别处没有更好的来源——它改进的是从已到站集合里的选择，不是全局召回。

另一个容易误会的点：该服务处理的是**文本**，不是把向量字段当文本。它使用索引语义配置里指定的文本字段来构造评估材料：摘要阶段每个文档最多 **2,000 个输入 token**，title 和 keywords 字段各限 **128 token**，剩余额度分配给 content。因此字段优先级本身就是相关性设计的一部分，尤其当一条源记录包含大段正文时。

这些都是服务边界，不是通用的重排规则。自托管 cross-encoder 或其他搜索提供商的输入限制、分值含义、配置要求都可以不同。别把 Azure 的约束当作普世真理搬进与厂商无关的抽象里。

## 把语义配置当检索模式的 schema

经典语义查询运行前，索引需要有**语义配置**：一个可选的 title 字段，加上按优先级排列的 content 与 keywords 字段。所选字段必须是 **searchable 且 retrievable 的字符串**（Edm.String、Collection(Edm.String) 或复杂类型的字符串子字段），且应当是能帮人理解记录的描述性文本，而不是不透明标识符。

一个反直觉的点：添加或更新语义配置**不会重建索引**，它只改变语义排名器用来摘要和评估候选的字段。这容易让人觉得配置是无害元数据，但改 title / content / keywords 的优先级会改变第二阶段模型看到的文本，从而改变结果顺序与摘要。**按检索行为来测试它**。

下面的示例改编自 Microsoft 当前的 Azure SDK 语义排名官方样例，为已有索引添加配置（Azure.Search.Documents 12.0.0——截至 2026-09-01 的 NuGet 最新稳定版）：

```csharp
using System;
using System.Linq;
using Azure.Search.Documents.Indexes.Models;

static void AddSemanticConfiguration(
    SearchIndex index,
    string configurationName)
{
    index.SemanticSearch ??= new SemanticSearch();

    if (!index.SemanticSearch.Configurations.Any(
            configuration => configuration.Name == configurationName))
    {
        var fields = new SemanticPrioritizedFields
        {
            TitleField = new SemanticField("Title"),
            ContentFields = { new SemanticField("Content") },
            KeywordsFields = { new SemanticField("Tags") }
        };

        index.SemanticSearch.Configurations.Add(
            new SemanticConfiguration(configurationName, fields));
    }

    index.SemanticSearch.DefaultConfigurationName = configurationName;
}
```

优先级顺序要反映可检索记录的形状：短 title 提供上下文，content 字段装能回答问题的正文，keywords 补充领域词汇。文档也提醒：低优先级的长字段可能在进入排序模型前就被截断，所以把最有效的描述字段放在前面，是一项值得评估的数据决策。

另外一个例外值得知道：从 **2026-05-01-preview** 开始，受支持的 agentic retrieval（RAG）流程不要求显式语义配置——但该例外**不适用于经典语义排名查询**。本文的稳定边界就是经典配置。

## 把服务前提摆到明面上

语义重排在 Azure 上有硬性前提：可用区域、已有含富文本的索引、语义配置；鉴权建议 RBAC，不可行时 API-key 是替代方案；计费上，语义排名器从 **Free 计费计划**开始（在每个定价层都提供每月请求额度），额度用完后切 **Standard 计划**要求 **Basic 及以上服务层**。这些是服务关注点，不是 `SearchOptions` 对象的属性——文中 C# 类型配置的是 Azure AI Search，不是「所有向量数据库的语义排名」，也不构成可移植的「最佳重排器」模式。

## 从 .NET 发语义查询

配置就位后，语义重排就是一次查询请求：`QueryType` 设为 `SearchQueryType.Semantic`，指定配置名，并给出有意义的文本。两个常见坑：**空搜索文本或 `search=*` 没有相关性可重排**；**不要加 `orderBy` 子句**——Azure AI Search 对带字段排序的语义排名请求直接返回 HTTP 400。

```csharp
using System.Threading.Tasks;
using Azure.Search.Documents;
using Azure.Search.Documents.Models;

static async Task<SearchResults<SearchDocument>> SearchSemanticallyAsync(
    SearchClient searchClient,
    string question)
{
    var options = new SearchOptions
    {
        Size = 8,
        QueryType = SearchQueryType.Semantic,
        SemanticSearch = new SemanticSearchOptions
        {
            SemanticConfigurationName = "rag-content",
            QueryCaption = new QueryCaption(QueryCaptionType.Extractive)
            {
                HighlightEnabled = true
            }
        }
    };

    options.Select.Add("id");
    options.Select.Add("title");
    options.Select.Add("content");
    options.HighlightFields.Add("content");

    var response = await searchClient.SearchAsync<SearchDocument>(
        question,
        options);

    return response.Value;
}
```

这段代码没有嵌入客户端——它刻意只覆盖第二阶段，不假装自己负责候选构造；也没有 `orderBy`、没有空查询，两者都会破坏语义排名。

## 读重排分数：别把它变成普适阈值

Azure 的语义结果保留初始搜索分数，并新增 `RerankerScore`，官方文档定义分值范围 **4 到 0（高到低），越高语义相关性越强**（4.0 = 文档高度相关并完整回答问题）。这个分数适合巡检、排序和评估记录，但不是应用级的质量保证。

官方还警告：**分数分布会随基础设施状况和排名模型更新而变化**。不要拿一份测试语料上调出来的精细截止值当长期相关性策略。产品真需要阈值时，用有代表性的问题集评估，并在语料、配置或服务行为变化后复审。

一个小投影把初始分、厂商特有的重排分、caption 和应用元数据放在一起，比单独传文本给下一个组件更适合做 RAG 交接：

```csharp
using System.Collections.Generic;
using System.Linq;
using Azure.Search.Documents.Models;

public sealed record RerankedEvidence(
    string Id,
    string Title,
    double? InitialScore,
    double? RerankerScore,
    string? Caption);

static RerankedEvidence ToEvidence(
    SearchResult<SearchDocument> result)
{
    var caption = result.SemanticSearch?.Captions?.FirstOrDefault();

    return new RerankedEvidence(
        result.Document.GetString("id"),
        result.Document.GetString("title"),
        result.Score,
        result.SemanticSearch?.RerankerScore,
        caption?.Text);
}
```

关于 caption 的定位：官方文档明确语义摘要与答案是**索引正文的逐字摘录，不是生成的新文本**。这在 RAG 界面里很有价值——可以直接展示「为什么选中这条来源」，而不用让语言模型另写一条引用摘要。但应用仍然要在组装生成提示词之前保留来源标识、版本信息和授权上下文。

## 排序、引用、生成三件事分开

第二阶段排序的价值，在管道保留三个独立产物时最容易推理：

1. **候选元数据**：记录第一级检索当时考虑了什么；
2. **重排证据**：记录 Azure 如何排序候选、返回了哪个抽取式 caption；
3. **答案证据**：只记录响应实际使用的来源。

这三份记录让排错不再是玄学。一个差答案可能来自：候选检索漏掉了相关文档；语义配置把错误的文本排在了前面；上下文组装丢掉了最好的证据；或生成阶段超出了来源。**把这四种失败都叫「重排器的问题」，会掩盖你真正需要修的地方。**

## 用代表性问法评估排序变化

第二阶段的成败标准是：它是否改进了用户真正会问的问题的证据顺序。准备一个小评估集——问题、期望的来源或片段 ID、语料修订号——在语义配置改动前后各跑一遍，然后人工检查失败案例，而不是盯着单个分数。这让排序成为可观察的行为，而不是配置假设。

比如：某条期望来源**在初始候选集里、但排在无用的位置**——这正是重排器该发力的案例。此时检查配置的 title/content/keywords 字段有没有足够的描述性语言让语义排名器区分结果，就把「排序不对」的观察连到了「改字段优先级」的可执行动作上。

| 评估字段     | 含义                                     |
| ------------ | ---------------------------------------- |
| Question     | 用户会怎么问（不要用文档里的原话）       |
| Expected IDs | 人工标注的期望来源片段                   |
| Rank Before  | 改动前该来源在候选/重排后的位置          |
| Rank After   | 改动后的位置                             |
| Notes        | 失败归因：候选缺失 / 字段描述不足 / 其他 |

边界也要清楚：重排器能改进结果顺序，不能保证生成器不胡说；反过来，一个看似可靠的答案也可能被「缺少有用细节」的排序拖累。衡量重排的价值时，只看证据顺序这一层。

（针对最常见问题的直接回答：语义重排能找回第一级检索没返回的文档吗？不能。semantic ranker 只看前 50 条初始结果，所以第一级检索的设计与评估才是召回的天花板。）

Aide Hub 会继续分享 RAG 与 .NET 的落地实践——把管道边界画清楚，把厂商能力核对准确，少一点「RAG 魔法」，多一点可观察、可评估、可改进的小步骤。

## 参考

- 《[Semantic Reranking for RAG in .NET: A Second-Stage Retrieval Model](https://www.devleader.ca/2026/08/28/semantic-reranking-for-rag-in-net-a-secondstage-retrieval-model)》，Nick Cosentino，2026-08-28（本文原文）
- Microsoft Docs：[Azure AI Search 语义排名概述](https://learn.microsoft.com/en-us/azure/search/semantic-search-overview)（L2、top 50、2000/128 token、0–4 分、逐字摘要）
- Microsoft Docs：[配置语义排名](https://learn.microsoft.com/en-us/azure/search/semantic-how-to-configure)（无需重建索引、2026-05-01-preview 例外）
- Microsoft Docs：[发起语义查询](https://learn.microsoft.com/en-us/azure/search/semantic-how-to-query-request)（`search=*` 无评分、`orderBy` 返回 400）
- Microsoft Docs：[启用或停用语义排名计费](https://learn.microsoft.com/en-us/azure/search/semantic-how-to-enable-disable)（Free / Standard 计划与 Basic+）
- Microsoft 官方样例：[quickstart-semantic-ranking/QueryIndex/Program.cs](https://raw.githubusercontent.com/Azure-Samples/azure-search-dotnet-samples/main/quickstart-semantic-ranking/QueryIndex/Program.cs)
- Microsoft 官方样例：[QueryIndex.csproj](https://raw.githubusercontent.com/Azure-Samples/azure-search-dotnet-samples/main/quickstart-semantic-ranking/QueryIndex/QueryIndex.csproj)（Azure.Search.Documents 12.0.0）
- Dev Leader：[RAG and Embeddings in .NET: A Stable Architecture Guide](https://www.devleader.ca/2026/08/12/rag-and-embeddings-in-net-a-stable-architecture-guide)
- Dev Leader：[Vector Search in .NET: The Azure AI Search Query Model](https://www.devleader.ca/2026/08/20/vector-search-in-net-the-azure-ai-search-query-model)
- Dev Leader：[RAG with Semantic Kernel in C#](https://www.devleader.ca/2026/03/01/rag-with-semantic-kernel-in-c-complete-guide-to-retrievalaugmented-generation)

（说明：SDK 版本、top 50、token 限制、分值范围、计费计划与预览例外均已按 2026-09-01 的最新官方文档核对；原文发布于 2026-08-28。）
