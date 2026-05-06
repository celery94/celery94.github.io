---
pubDatetime: 2026-05-06T08:40:00+08:00
title: ".NET 向量数据实战：Microsoft.Extensions.VectorData 构建 RAG 应用"
description: "本文是 .NET AI 构建块系列第二篇，聚焦 Microsoft.Extensions.VectorData。通过统一抽象层，开发者可以用一套 API 操作 Qdrant、Redis、PostgreSQL、Azure AI Search 等多种向量数据库，轻松实现语义搜索、嵌入存储与 RAG 检索增强生成模式。"
tags: [".NET", "AI", "VectorData", "RAG", "语义搜索", "嵌入向量"]
slug: "dotnet-vector-data-building-blocks-ai-part2"
ogImage: "../../assets/773/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/vector-data-in-dotnet--building-blocks-for-ai-part-2/"
---

这是 .NET AI 构建块系列的第二篇。[第一篇](https://devblogs.microsoft.com/dotnet/dotnet-ai-essentials-the-core-building-blocks-explained/)介绍了 `Microsoft.Extensions.AI`，提供了统一的 LLM 访问接口。本文聚焦第二块：`Microsoft.Extensions.VectorData`。

![文档转化为向量点集群的抽象示意图](../../assets/773/01-cover.png)

## 为什么需要向量数据库

用 LLM 回答关于你自己产品文档的问题，模型并不会"凭空"知道这些内容。你的应用通常要经历这样的流程：

1. **将文档转化为嵌入向量**——数值化表示文本的语义含义
2. **把嵌入向量存入向量数据库**——同时保留原始文本内容
3. **把用户查询也转化为嵌入向量**——使用相同的模型
4. **做相似度搜索**——找出语义最相关的文档
5. **把检索到的上下文和查询一起发给 LLM**——让模型给出有根据的答案

这个模式叫做 **RAG（Retrieval-Augmented Generation，检索增强生成）**，是大多数企业 AI 应用的核心架构。

### 语义搜索 vs 关键词搜索

传统关键词搜索的问题可以用一个简单例子说明。假设数据库里有三条记录：

- Hall pass（通行证）
- Mountain pass（山口）
- Pass（动词，传递）

用户问"How do I get over the pass?"或"Where do I pick up a pass?"，两个查询都包含"pass"，关键词搜索会把三条记录全部返回，不管语义上哪条更相关。

语义搜索则不同，它把文本转成嵌入向量之后，"翻越山口"这个语义会匹配到"Mountain pass"，"领取通行证"会匹配到"Hall pass"——即使用词不同，语义意图能被正确理解。

向量数据库（如 Qdrant、Redis、SQL Server、Cosmos DB）专门用于存储和查询这类向量。`Microsoft.Extensions.VectorData` 提供了跨数据库的统一抽象，和 MEAI 统一 LLM 接口的思路完全一致。

## 统一接口，切换数据库零改动

先看直接使用 Qdrant 原生 SDK 的写法：

```csharp
var qdrantClient = new QdrantClient("localhost", 6334);

var collection = "my_collection";
await qdrantClient.CreateCollectionAsync(collection, new VectorParams
{
    Size = 1536,
    Distance = Distance.Cosine
});

var points = new List<PointStruct>
{
    new()
    {
        Id = new PointId { Uuid = Guid.NewGuid().ToString() },
        Vectors = embedding,
        Payload =
        {
            ["text"] = "Sample document text",
            ["category"] = "documentation"
        }
    }
};

await qdrantClient.UpsertAsync(collection, points);

var searchResults = await qdrantClient.SearchAsync(collection, queryEmbedding, limit: 5);
```

再看使用 `Microsoft.Extensions.VectorData` 抽象的写法：

```csharp
// 在向量存储上统一配置嵌入生成器
var embeddingGenerator = new OpenAIClient(apiKey)
    .GetEmbeddingClient("text-embedding-3-small")
    .AsIEmbeddingGenerator();

var vectorStore = new QdrantVectorStore(
    new QdrantClient("localhost"),
    ownsClient: true,
    new QdrantVectorStoreOptions { EmbeddingGenerator = embeddingGenerator });

var collection = vectorStore.GetCollection<string, DocumentRecord>("my_collection");
await collection.EnsureCollectionExistsAsync();

var record = new DocumentRecord
{
    Key = Guid.NewGuid().ToString(),
    Text = "Sample document text",
    Category = "documentation"
};

await collection.UpsertAsync(record);

var searchResults = collection.SearchAsync("find documents about sample topics", top: 5);
```

第二种写法只需要把 `QdrantVectorStore` 换成其他实现，业务逻辑完全不变——这就是抽象层的价值。

## 定义数据模型

向量数据扩展使用特性（Attribute）把 C# 类映射到向量数据库的 Schema：

```csharp
public class DocumentRecord
{
    [VectorStoreKey]
    public string Key { get; set; }

    [VectorStoreData]
    public string Text { get; set; }

    [VectorStoreData(IsIndexed = true)]
    public string Category { get; set; }

    [VectorStoreData(IsIndexed = true)]
    public DateTimeOffset Timestamp { get; set; }

    // 当向量存储上配置了 IEmbeddingGenerator 时，
    // 插入和搜索时嵌入向量会自动生成
    [VectorStoreVector(1536, DistanceFunction.CosineSimilarity)]
    public string Embedding => this.Text;
}
```

三个核心特性：

- **`[VectorStoreKey]`**：唯一标识每条记录的键
- **`[VectorStoreData]`**：可存储和检索的元数据字段；加 `IsIndexed = true` 表示这个字段支持过滤
- **`[VectorStoreVector]`**：向量字段，指定维度（1536 对应 OpenAI text-embedding-3-small）和距离函数

## 集合的增删改查

定义好数据模型之后，集合操作的 API 非常直观：

```csharp
// 获取或创建集合
var collection = vectorStore.GetCollection<string, DocumentRecord>("documents");

// 检查集合是否存在
bool exists = await collection.CollectionExistsAsync();
await collection.EnsureCollectionExistsAsync();

// 插入或更新记录
await collection.UpsertAsync(documentRecord);

// 批量操作
await collection.UpsertBatchAsync(documentRecords);

// 按键查询
var record = await collection.GetAsync("some-key");

// 删除记录
await collection.DeleteAsync("some-key");
await collection.DeleteBatchAsync(["key1", "key2", "key3"]);
```

这套 API 对所有支持的向量数据库都一样，换底层数据库不影响上层代码。

## 语义搜索

`SearchAsync` 是最核心的方法。当向量存储或集合上配置了 `IEmbeddingGenerator` 时，直接传查询文本，嵌入向量会自动生成：

```csharp
// 配置了 IEmbeddingGenerator 后，搜索时嵌入向量自动生成
await foreach (var result in collection.SearchAsync("What is semantic search?", top: 5))
{
    Console.WriteLine($"Score: {result.Score}, Text: {result.Record.Text}");
}
```

如果已经有预计算好的嵌入向量（比如批量处理时自己生成了），也可以直接传入：

```csharp
// 直接传入预计算的嵌入向量
ReadOnlyMemory<float> precomputedEmbedding = /* your embedding */;
await foreach (var result in collection.SearchAsync(precomputedEmbedding, top: 5))
{
    Console.WriteLine($"Score: {result.Score}, Text: {result.Record.Text}");
}
```

## 元数据过滤

向量相似度搜索可以和元数据过滤结合使用，缩小搜索范围：

```csharp
var searchOptions = new VectorSearchOptions<DocumentRecord>
{
    Filter = r => r.Category == "documentation" &&
                  r.Timestamp > DateTimeOffset.UtcNow.AddDays(-30)
};

var results = collection.SearchAsync("find relevant documentation", top: 10, searchOptions);
```

过滤条件用标准 LINQ 表达式写，支持：

- 等值比较（`==`、`!=`）
- 范围查询（`>`、`<`、`>=`、`<=`）
- 逻辑运算符（`&&`、`||`）
- 集合包含（`.Contains()`）

## 嵌入生成器的配置

推荐的做法是在向量存储层统一配置 `IEmbeddingGenerator`，插入和搜索时嵌入会自动处理：

```csharp
// 统一配置嵌入生成器
var embeddingGenerator = new OpenAIClient(apiKey)
    .GetEmbeddingClient("text-embedding-3-small")
    .AsIEmbeddingGenerator();

var vectorStore = new InMemoryVectorStore(new() { EmbeddingGenerator = embeddingGenerator });
var collection = vectorStore.GetCollection<string, DocumentRecord>("documents");
await collection.EnsureCollectionExistsAsync();

// 插入时自动生成嵌入
var record = new DocumentRecord
{
    Key = Guid.NewGuid().ToString(),
    Text = "Sample text to store"
};
await collection.UpsertAsync(record);

// 搜索时也自动生成嵌入
await foreach (var result in collection.SearchAsync("find similar text", top: 5))
{
    Console.WriteLine($"Score: {result.Score}, Text: {result.Record.Text}");
}
```

`InMemoryVectorStore` 特别适合本地开发和测试，不需要启动任何外部服务。

## 完整 RAG 实现示例

把 `Microsoft.Extensions.AI` 和 `Microsoft.Extensions.VectorData` 结合起来，一个简化的 RAG 实现如下：

```csharp
public async Task<string> AskQuestionAsync(string question)
{
    // 查找相关文档——嵌入自动生成
    var contextParts = new List<string>();
    await foreach (var result in collection.SearchAsync(question, top: 3))
    {
        contextParts.Add(result.Record.Text);
    }

    // 把检索结果拼成上下文
    var context = string.Join("\n\n", contextParts);

    // 构造带上下文的提示词
    var messages = new List<ChatMessage>
    {
        new(ChatRole.System,
            "Answer questions based on the provided context. If the context doesn't contain relevant information, say so."),
        new(ChatRole.User,
            $"Context:\n{context}\n\nQuestion: {question}")
    };

    // 调用 LLM 得到答案
    var response = await chatClient.GetResponseAsync(messages);
    return response.Message.Text;
}
```

这个模式把三件事串联起来：语义检索找相关文档、拼接上下文、让 LLM 基于事实作答——这正是 RAG 的核心思路。

## 支持的向量数据库

`Microsoft.Extensions.VectorData` 通过官方 connector 包支持多种主流向量数据库：

| 数据库 | NuGet 包 |
|--------|----------|
| Azure AI Search | `Microsoft.Extensions.VectorData.AzureAISearch` |
| Qdrant | `Microsoft.SemanticKernel.Connectors.Qdrant` |
| Redis | `Microsoft.SemanticKernel.Connectors.Redis` |
| PostgreSQL | `Microsoft.SemanticKernel.Connectors.Postgres` |
| Azure Cosmos DB (NoSQL) | `Microsoft.SemanticKernel.Connectors.AzureCosmosDBNoSQL` |
| SQL Server | `Microsoft.SemanticKernel.Connectors.SqlServer` |
| SQLite | `Microsoft.SemanticKernel.Connectors.Sqlite` |
| 内存（测试用） | `Microsoft.SemanticKernel.Connectors.InMemory` |

此外还支持 Elasticsearch、MongoDB、Weaviate、Pinecone 等，完整列表见[官方 connector 文档](https://learn.microsoft.com/semantic-kernel/concepts/vector-store-connectors/out-of-the-box-connectors/?pivots=programming-language-csharp)。

## 为什么单独设计成独立包

你可能会问，向量数据为什么不直接并入 `Microsoft.Extensions.AI` 核心包？

原因很简单：**不是每个 AI 应用都需要向量存储**。聊天机器人、文本分类、内容生成这类场景，只用 LLM 接口就够了。把向量数据独立出来，让核心包保持轻量，用到的时候再按需引入，符合 .NET 生态一贯的模块化设计思路。

## 后续

系列下一篇将介绍 **Microsoft Agent Framework**，展示如何把这些构建块组合成具备推理能力的智能体工作流。

当前可以参考以下资源开始实践：

- [AI 示例仓库](https://github.com/dotnet/ai-samples)
- [.NET AI 官方文档](https://learn.microsoft.com/dotnet/ai/)

## 参考

- [Vector Data in .NET – Building Blocks for AI Part 2](https://devblogs.microsoft.com/dotnet/vector-data-in-dotnet--building-blocks-for-ai-part-2/)
- [.NET AI Essentials – The Core Building Blocks Explained（系列第一篇）](https://devblogs.microsoft.com/dotnet/dotnet-ai-essentials-the-core-building-blocks-explained/)
- [VectorData out-of-the-box connectors 文档](https://learn.microsoft.com/semantic-kernel/concepts/vector-store-connectors/out-of-the-box-connectors/?pivots=programming-language-csharp)
