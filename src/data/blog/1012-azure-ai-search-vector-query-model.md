---
pubDatetime: 2026-08-23T09:59:05+08:00
title: "Azure AI Search 向量查询：.NET 直连检索模型"
description: "已有向量索引时，怎么用 Azure.Search.Documents 发送正确的向量查询？本文拆解同一嵌入模型、字段名、VectorizedQuery、元数据过滤和分数含义，并给出上线前测试建议。"
tags: ["Azure AI Search", "Vector Search", ".NET", "C#", "RAG"]
slug: "azure-ai-search-vector-query-model"
ogImage: "../../assets/1012/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/20/vector-search-in-net-the-azure-ai-search-query-model"
---

在 Azure AI Search 的 .NET SDK 里，一次向量检索看上去只是把一个 `ReadOnlyMemory<float>` 交给 `SearchAsync<T>`。真正决定结果是否正确的是请求外面的合同：查询向量由哪个嵌入模型生成、索引向量字段叫什么、字段维度是多少、返回结果保留了哪些元数据。

这篇文章根据 Nick Cosentino 在 Dev Leader 的 2026 年 8 月文章整理，聚焦直接、第一阶段的向量查询。它假设你已经有一个带向量字段和向量搜索配置的索引，并且应用能够生成查询向量；不覆盖服务开通、连接器抽象、混合检索或第二阶段排序。读完你可以照着写出一个明确的检索请求，知道三类检索问题该从哪里查。

## 先确定适用边界

适合这篇文章的情况很清晰：

- 你已经有一个 Azure AI Search 索引。
- 索引里有向量字段、一个向量搜索 profile，以及对应的算法配置。
- 应用已经有能力生成与文档向量同源的嵌入。
- 你需要把向量检索作为独立组件接入 RAG 或语义搜索流程。

不适合的情况也很明确：还没有索引、需要从文本自动生成向量、需要关键词和向量融合、需要语义重排，这些属于另一类问题。这里只处理一个问题，就是把向量转换成一次正确的查询。

前置条件可以按官方快速入门来准备：一个可用的 Azure AI Search 服务、.NET 8 或更高版本，以及使用 Microsoft Entra ID 时必要的角色。如果采用推荐的角色授权，需要 `Search Service Contributor`、`Search Index Data Contributor`、`Search Index Data Reader` 这类权限，应用再用 `DefaultAzureCredential` 连接。

## 包版本与 API 版本的边界

截至 2026-08-23，NuGet 上 `Azure.Search.Documents` 的稳定版仍是 12.0.0，`12.1.0-beta.1` 是预览版。Azure AI Search 官方页面也把 Azure SDK for .NET 12 标为 Active。写稳定实现时，让包版本和 API 版本一起保持稳定，不要让预览包悄悄进入生产路径。

一个容易踩的坑来自旧代码：`2023-07-01-preview` 已经在 2024 年弃用，官方明确要求迁移到新版。搜索旧片段时先看版本号，不要因为示例能跑就照搬。

项目文件可以只引入实现所需的两个包：

```xml
<ItemGroup>
  <PackageReference Include="Azure.Identity" Version="1.17.1" />
  <PackageReference Include="Azure.Search.Documents" Version="12.0.0" />
</ItemGroup>
```

`Azure.Identity` 用来走 `DefaultAzureCredential`，`Azure.Search.Documents` 提供客户端和查询模型。版本号要按你的项目和权限现状调整，不需要机械复制。

## 索引侧先定好向量合同

装包不等于完成配置。查询能够直接命名一个向量字段，前提是索引里先有三个东西：向量字段、向量搜索 profile、profile 引用的算法配置。下面只展示这一小块合同，不创建服务资源，也不上传内容。

```csharp
using Azure.Search.Documents.Indexes.Models;

public static class ChunkIndexDefinition
{
    public static SearchIndex Create()
    {
        var vectorSearch = new VectorSearch();
        vectorSearch.Algorithms.Add(
            new HnswAlgorithmConfiguration("chunk-hnsw"));
        vectorSearch.Profiles.Add(
            new VectorSearchProfile(
                name: "chunk-vector-profile",
                algorithmConfigurationName: "chunk-hnsw"));

        return new SearchIndex("knowledge-chunks")
        {
            Fields =
            {
                new SimpleField("Id", SearchFieldDataType.String)
                {
                    IsKey = true,
                    IsFilterable = true
                },
                new SearchableField("Content"),
                new VectorSearchField(
                    "ContentVector",
                    vectorSearchDimensions: 1536,
                    vectorSearchProfileName: "chunk-vector-profile"),
                new SimpleField("SourceUri", SearchFieldDataType.String),
                new SimpleField("TenantId", SearchFieldDataType.String)
                {
                    IsFilterable = true
                }
            },
            VectorSearch = vectorSearch
        };
    }
}
```

这里的 `ContentVector` 是索引里的字段名，与 C# 属性命名习惯无关。查询代码必须使用索引字符串里出现的同一个名字。`1536` 只是示例嵌入大小，适合某些常见模型，不代表所有模型；应该填你实际嵌入模型输出的维度。

更值得记住的合同是：文档向量和查询向量必须来自同一个嵌入空间。维度相同是必要条件，却不能证明语义兼容。模型版本或向量化方式换了，旧文档向量就和新查询向量不再可互换，需要重索引受影响的语料。

## 查询侧把维度检查放在网络请求之前

不要把维度错误留到 Azure AI Search 返回异常才暴露。用一个小的合同对象把字段名和维度收在同一个地方，查询向量进入 `VectorizedQuery` 前先自检。

```csharp
using Azure.Search.Documents.Models;

public sealed record VectorFieldContract(string Name, int Dimensions)
{
    public VectorizedQuery CreateQuery(
        ReadOnlyMemory<float> vector,
        int topK)
    {
        if (vector.Length != Dimensions)
        {
            throw new ArgumentException(
                $"Expected {Dimensions} dimensions, but received {vector.Length}.",
                nameof(vector));
        }

        return new VectorizedQuery(vector)
        {
            KNearestNeighborsCount = topK,
            Fields = { Name }
        };
    }
}
```

`VectorizedQuery` 表示调用方已经生成好的原始向量，`KNearestNeighborsCount` 决定要返回多少个近邻，`Fields` 指定查询命中哪个向量字段。字段名准确是最容易忽略的一点：一个索引可以有多个向量字段，SDK 不会替猜测，必须明确告诉它比较哪一列。

这段代码没有假装知道向量从哪里来。嵌入可以来自 Azure OpenAI、内部嵌入服务或其他提供方；对直接查询来说，重要的是向量数量和嵌入空间都匹配。

## 用 SearchClient 发送直连向量请求

`SearchClient` 在创建时就绑定了索引名，`SearchAsync<T>` 会把返回字段映射到 .NET 类型。结果类型尽量小，避免检索层在内存里变成第二份文档库。

```csharp
using Azure.Identity;
using Azure.Search.Documents;
using Azure.Search.Documents.Models;

public sealed record SearchChunk(
    string Id,
    string Content,
    string SourceUri,
    string TenantId);

public sealed record RetrievedChunk(
    SearchChunk Document,
    double? Score);

public static class ChunkSearch
{
    public static async Task<IReadOnlyList<RetrievedChunk>> SearchAsync(
        Uri endpoint,
        string indexName,
        ReadOnlyMemory<float> queryVector,
        CancellationToken cancellationToken)
    {
        var client = new SearchClient(
            endpoint,
            indexName,
            new DefaultAzureCredential());

        var contract = new VectorFieldContract("ContentVector", 1536);
        var response = await client.SearchAsync<SearchChunk>(
            new SearchOptions
            {
                VectorSearch = new VectorSearchOptions
                {
                    Queries = { contract.CreateQuery(queryVector, topK: 5) }
                },
                Select = { "Id", "Content", "SourceUri", "TenantId" }
            },
            cancellationToken);

        var chunks = new List<RetrievedChunk>();
        await foreach (SearchResult<SearchChunk> result in
            response.Value.GetResultsAsync())
        {
            chunks.Add(new RetrievedChunk(
                result.Document,
                result.Score));
        }

        return chunks;
    }
}
```

这里使用的是只传 `SearchOptions` 的 `SearchAsync<T>` 重载，因此请求不包含全文搜索文本，是纯向量请求。`VectorSearchOptions.Queries` 放入 `VectorizedQuery`，`Select` 把返回字段限制为应用真正需要的列。

官方文档说明，`SearchAsync<T>` 支持字段映射，并通过 `GetResultsAsync()` 做异步结果遍历。查询结果很多时，这个方法会按需继续发起后续请求，`await foreach` 正好适合处理这种流式结果。

## 分数只说明这次排序

`SearchResult<T>.Score` 是 `double?` 类型的相关性分数，含义是文档相对本次查询返回的其他文档的排序依据。它不是置信度百分比，也不能直接当成「回答正确」的概率。

向量查询的分数会依赖索引配置的相似度指标。Azure OpenAI 嵌入模型通常配 cosine，Azure AI Search 会把 cosine 分数转换成单调下降的排序分数，原始 cosine 相似度不会直接出现在结果里。官方说明显示 cosine 向量分数的范围大致是 0.333 到 1.00，低分仍可能出现在结果列表里，因为向量查询总是返回与查询最近的若干邻居。

实际使用方式应该是：分数帮你判断两个结果为什么这样排序，是否需要把 top-K 调大或调小，以及某个阈值下的结果是否值得交给下游模型。是否回答正确，最终要靠评估数据验证，不能只信一个数值。

## 元数据过滤放在非向量字段上

向量字段本身不能做 filter。权限范围、来源类别、生命周期状态这类边界，应该放在普通文本或数字字段上。

```csharp
using Azure.Search.Documents;
using Azure.Search.Documents.Models;

public static class ScopedChunkSearch
{
    public static Task<Response<SearchResults<SearchChunk>>> SearchAsync(
        SearchClient client,
        ReadOnlyMemory<float> queryVector,
        CancellationToken cancellationToken)
    {
        var contract = new VectorFieldContract("ContentVector", 1536);

        return client.SearchAsync<SearchChunk>(
            new SearchOptions
            {
                VectorSearch = new VectorSearchOptions
                {
                    Queries = { contract.CreateQuery(queryVector, topK: 5) }
                },
                Filter = "TenantId eq 'contoso'",
                Select = { "Id", "Content", "SourceUri", "TenantId" }
            },
            cancellationToken);
    }
}
```

`contoso` 只是示例。生产环境应该从经过认证的服务端策略构造租户边界，不能接受浏览器传来的任意 filter 当作授权依据。这里体现的是索引结构分工：`ContentVector` 存数值，`TenantId` 存可过滤元数据，向量查询和权限边界各自有明确位置。

## 三类错误分开诊断

检索结果不对时，先说清是哪一类失败：

- 维度不匹配：查询向量和字段维度不一样，属于合同错误，先修嵌入生成或索引字段。
- 嵌入模型不兼容：维度一样但模型不同，属于数据迁移错误，需要受控重索引。
- 结果看似合理但缺少来源：属于检索质量错误，需要评估查询、检查语料或调整查询策略。

这三类问题对应的修复完全不同。把它们都笼统称为「向量搜索不准」，会让排障绕远路。先确认字段、嵌入合同、查询向量、元数据边界和语料，再决定改哪里。

## 上线前先验证合同和结果集

第一层验证不需要真实查询。`VectorFieldContract` 已经让维度错误在发起网络调用前失败，这层测试便宜且确定。还可以测字段名，防止模型或 schema 迁移时悄悄丢掉 `Id`、`SourceUri` 这些用于追踪来源的字段。

第二层验证需要一组经过人工确认的语料问题。每个问题记录预期来源或 chunk 标识、嵌入模型修订号、索引版本和 top-K。这样做的重点是让后续变化可解释，不需要把某个分数当成绝对标准。比如某个来源突然从结果里消失，你就能判断是语料、嵌入合同、字段还是查询行为变了。

元数据过滤也要单独测：一个能返回合格 chunk 的正例，和一个能把范围外内容排除掉的负例。过滤器属于检索请求的一部分，应该出现在测试夹具和上线评审中，不能只放在 UI 便利层里。

## 常见问题

**应该用哪个 NuGet 包？** 用 `Azure.Search.Documents` 12.0.0 稳定版，当前 12.1.0-beta.1 仍是预览。它提供 `SearchClient`、`SearchOptions`、`VectorSearchOptions` 和 `VectorizedQuery`。预览包只有在明确接受其 API 生命周期后才使用。

**向量字段会自动生成嵌入吗？** 不会。直接向量查询中，应用提供查询向量；只有单独配置了集成向量化，服务才会在索引或查询阶段生成嵌入。字段本身只是定义向量存储位置和搜索 profile。

**为什么必须写字段名？** 一个索引可以有多个向量字段。`VectorizedQuery.Fields` 明确告诉 SDK 比较哪个 `Collection(Edm.Single)` 字段，避免把同一文档的不同表示混在一起。

**返回分数是置信度吗？** 不是。它是这次查询内的相关性排序值，cosine 模式下还被服务转换过。要判断答案是否靠谱，需要应用级评估，不能用单个分数下结论。

**能直接过滤向量字段吗？** 不能。把可过滤元数据放到普通非向量字段，例如服务端租户范围或来源状态，再让向量查询只处理向量字段。

**什么时候改向量维度？** 只有当你明确改变嵌入合同并准备重索引受影响向量时才改。新查询向量不会因为也是浮点数组，就自然兼容旧语料。

## 总结

Azure AI Search 的 .NET 直连向量查询有一个小而清晰的模型：配置维度正确的向量字段，生成同嵌入空间的查询向量，创建 `VectorizedQuery`，写对字段名，请求有限数量的近邻，并保留让结果可解释的元数据。

SDK 调用本身很短，真正值得花心思的是它周围的合同。检索看起来不对时，从索引字段、嵌入模型、查询向量、元数据边界和语料逐项检查，通常比把问题当成一次 API 调用的神秘行为更快得到答案。

如果你正在把 Azure AI Search 接入 RAG，或者想继续看 .NET 与 AI 的工程实践，欢迎关注 Aide Hub。我们会继续分享 AI 助手、开发工具和软件工程实践。

## 参考

- [Vector Search in .NET: The Azure AI Search Query Model（原文，Nick Cosentino）](https://www.devleader.ca/2026/08/20/vector-search-in-net-the-azure-ai-search-query-model/)
- [Vector search in Azure AI Search（官方概览）](https://learn.microsoft.com/en-us/azure/search/vector-search-overview)
- [Create a vector query in Azure AI Search（官方查询指南）](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-query)
- [Relevance in vector search（官方分数说明）](https://learn.microsoft.com/en-us/azure/search/vector-search-ranking)
- [Quickstart: Vector search（官方 .NET 快速入门）](https://learn.microsoft.com/en-us/azure/search/search-get-started-vector)
- [Azure AI Search API versions（官方 API 版本）](https://learn.microsoft.com/en-us/azure/search/search-api-versions)
- [VectorizedQuery Class（.NET API 参考）](https://learn.microsoft.com/en-us/dotnet/api/azure.search.documents.models.vectorizedquery?view=azure-dotnet)
- [SearchClient.SearchAsync Method（.NET API 参考）](https://learn.microsoft.com/en-us/dotnet/api/azure.search.documents.searchclient.searchasync?view=azure-dotnet)
- [SearchResult<T>.Score Property（.NET API 参考）](https://learn.microsoft.com/en-us/dotnet/api/azure.search.documents.models.searchresult-1.score?view=azure-dotnet)
