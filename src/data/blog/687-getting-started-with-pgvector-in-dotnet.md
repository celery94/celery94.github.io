---
pubDatetime: 2026-03-30T09:40:00+08:00
title: "在 .NET 中使用 pgvector 实现向量搜索入门"
description: "如果你的数据已经存储在 PostgreSQL 中，不需要额外的向量数据库。本文介绍如何通过 pgvector 扩展，配合 .NET Aspire、Ollama 和 Dapper，在现有 PostgreSQL 中实现语义相似度搜索。"
tags: ["PostgreSQL", "pgvector", "DotNet", "向量搜索", "AI"]
slug: "getting-started-with-pgvector-in-dotnet"
ogImage: "../../assets/687/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/getting-started-with-pgvector-in-dotnet-for-simple-vector-search?utm_source=newsletter&utm_medium=email&utm_campaign=tnw187"
---

Pinecone、Qdrant、Weaviate 这些专用向量数据库确实很强，但如果你的数据本来就在 PostgreSQL 里，多加一套新系统是真的有必要吗？

[pgvector](https://github.com/pgvector/pgvector) 是一个 PostgreSQL 扩展，直接在你现有的数据库里加上了向量存储和相似度搜索能力。启用扩展、加个向量列，就可以开始查询了，不需要额外部署或同步数据。

这篇文章会带你走完完整流程：

- 什么是向量搜索，以及什么时候用得上
- 用 .NET Aspire 和 Ollama 搭建环境
- 用 MEAI（Microsoft.Extensions.AI）生成嵌入向量，用 Dapper 存储
- 用余弦距离做语义相似度查询

## 向量搜索能解决什么问题

传统数据库查询靠的是精确匹配。你搜索"authentication"，就只能找到包含这个词的行。"login"、"sign-in"、"identity verification"这些语义上相近的词，`LIKE` 查询是找不到的。

向量搜索的思路不同：它比的是**含义**，而不是文字。

做法是把文本用机器学习模型转成一组数字（embedding，嵌入向量）。语义接近的文本会产生接近的向量。查询时，不是去匹配关键词，而是找数据库里距离最近的向量。

**常见使用场景：**

- **语义搜索**：按含义找结果，而不只是关键词
- **RAG（检索增强生成）**：给 LLM 提供相关上下文
- **推荐系统**：「喜欢 X 的用户也喜欢 Y」
- **去重**：找语义上近似的重复内容

核心判断很简单：**如果你已经在用 PostgreSQL，pgvector 不需要你另外引入任何基础设施。**

## 用 .NET Aspire 搭建环境

我们用 .NET Aspire 来启动一个带 pgvector 的 PostgreSQL 容器，以及一个运行 [qwen3-embedding](https://ollama.com/library/qwen3-embedding) 嵌入模型的 Ollama 实例。

在 AppHost 项目里配置如下：

```csharp
var builder = DistributedApplication.CreateBuilder(args);

var ollama = builder.AddOllama("ollama")
    .WithLifetime(ContainerLifetime.Persistent)
    .WithDataVolume()
    .WithGPUSupport();

var embeddingModel = ollama.AddModel("qwen3-embedding:0.6b");

var postgres = builder.AddPostgres("postgres", port: 6432)
    .WithLifetime(ContainerLifetime.Persistent)
    .WithDataVolume()
    .WithImage("pgvector/pgvector", "pg17")
    .AddDatabase("articles");

builder.AddProject<Projects.PgVector_Articles>("pgvector-articles")
    .WithReference(embeddingModel)
    .WithReference(postgres)
    .WaitFor(embeddingModel)
    .WaitFor(postgres);

builder.Build().Run();
```

几个关键点：

- `pgvector/pgvector:pg17` 是预装了 pgvector 扩展的 PostgreSQL 17 镜像
- `WithLifetime(ContainerLifetime.Persistent)` 让容器在应用重启后继续运行，不会丢数据
- `WaitFor` 确保数据库和模型就绪后 API 才启动

如果不用 Aspire，直接用 `docker compose` 启动同一个镜像，然后指定连接字符串即可。

## 配置 API 项目

API 项目需要安装几个包：

```bash
dotnet add package Aspire.Npgsql
dotnet add package Pgvector.Dapper
dotnet add package CommunityToolkit.Aspire.OllamaSharp
```

`Pgvector.Dapper` 提供了 `Vector` 类型的 Dapper 处理器。除此之外，pgvector 官方也提供了 [Npgsql](https://github.com/pgvector/pgvector-dotnet/tree/master/src/Pgvector) 和 [EF Core](https://github.com/pgvector/pgvector-dotnet/tree/master/src/Pgvector.EntityFrameworkCore) 版本，可按需选用。

在 `Program.cs` 中注册服务：

```csharp
builder.AddOllamaApiClient("ollama-qwen3-embedding")
    .AddEmbeddingGenerator();

builder.AddNpgsqlDataSource("articles", configureDataSourceBuilder: b =>
{
    b.UseVector();
});

SqlMapper.AddTypeHandler(new VectorTypeHandler());
```

- `AddEmbeddingGenerator()` 注册了 `IEmbeddingGenerator<string, Embedding<float>>`，使用 Microsoft.Extensions.AI 抽象
- `UseVector()` 在 Npgsql 数据源上启用 pgvector 类型映射
- `VectorTypeHandler` 让 Dapper 能够序列化和反序列化 `Vector` 参数

## 初始化数据库

存向量之前，需要先启用 pgvector 扩展并建表。可以通过一个 `/init` 接口来完成：

```csharp
app.MapPost("/init", async (NpgsqlDataSource dataSource) =>
{
    await using var conn = await dataSource.OpenConnectionAsync();

    await using var enableExt = new NpgsqlCommand(
        "CREATE EXTENSION IF NOT EXISTS vector", conn);
    await enableExt.ExecuteNonQueryAsync();

    conn.ReloadTypes();

    await conn.ExecuteAsync(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            embedding vector(1024) NOT NULL
        )
        """);

    await conn.ExecuteAsync(
        """
        CREATE INDEX IF NOT EXISTS articles_embedding_idx
        ON articles USING hnsw (embedding vector_cosine_ops)
        """);

    return Results.Ok("Database initialized.");
});
```

几个需要注意的地方：

- `CREATE EXTENSION IF NOT EXISTS vector` 在数据库中启用 pgvector
- `embedding vector(1024)` 定义了一个 1024 维的向量列，与 `qwen3-embedding:0.6b` 模型的输出维度匹配
- `conn.ReloadTypes()` 刷新 Npgsql 的类型缓存，让它能识别新建的 `vector` 类型
- **HNSW 索引**（Hierarchical Navigable Small World）配合 `vector_cosine_ops`，启用基于余弦距离的近似最近邻搜索

没有索引时，pgvector 会对每一行做顺序扫描——几百行数据没问题，但数据量增长后 HNSW 索引能让查询保持快速。

## 生成并存储嵌入向量

核心逻辑：把文章内容转成向量，存入数据库。

```csharp
app.MapPost("/embeddings/generate", async (
    BlogService blogService,
    IEmbeddingGenerator<string, Embedding<float>> embeddingGenerator,
    NpgsqlDataSource dataSource,
    ILogger<Program> logger) =>
{
    await using var conn = await dataSource.OpenConnectionAsync();
    conn.ReloadTypes();

    int count = 0;

    foreach (var articleUrl in File.ReadAllLines("sitemap_urls.txt"))
    {
        var (title, content) = await blogService.GetTitleAndContentAsync(articleUrl);

        var embedding = await embeddingGenerator.GenerateAsync(content);

        await conn.ExecuteAsync(
            "INSERT INTO articles (url, title, embedding) VALUES (@url, @title, @embedding)",
            new
            {
                url = articleUrl,
                title,
                embedding = new Vector(embedding.Vector.ToArray())
            });

        count++;
        logger.LogInformation("Processed ({Count}): {Url}", count, articleUrl);
    }

    return Results.Ok(new { processed = count });
});
```

`embeddingGenerator.GenerateAsync(content)` 把文本发给 Ollama 模型，返回一个向量。用 `Pgvector.Vector` 包一层，剩下的交给 Dapper。

`IEmbeddingGenerator` 是与提供商无关的抽象。如果以后要换成 OpenAI 或 Azure OpenAI，只需改 `Program.cs` 里的注册代码，接口层代码保持不变。

## 用余弦距离做相似度搜索

搜索时，把查询文本转成向量，然后找数据库里最近的几个向量：

```csharp
app.MapGet("/search", async (
    string query,
    IEmbeddingGenerator<string, Embedding<float>> embeddingGenerator,
    NpgsqlDataSource dataSource,
    int limit = 5) =>
{
    var searchEmbedding = await embeddingGenerator.GenerateAsync(query);

    await using var con = await dataSource.OpenConnectionAsync();
    con.ReloadTypes();

    var embedding = new Vector(searchEmbedding.Vector.ToArray());

    var results = await con.QueryAsync<SearchResult>(
        @"""
        SELECT title, url, embedding <=> @embedding as distance
        FROM articles
        ORDER BY embedding <=> @embedding
        LIMIT @limit
        """,
        new { embedding, limit });

    return Results.Ok(new { query, results });
});

record SearchResult(string Title, string Url, double Distance);
```

`<=>` 是 pgvector 的**余弦距离**操作符，值越小表示越相似。按距离升序排列，取前 N 条。

一个查询"how to secure an API"会找到涉及身份验证、JWT 校验、授权的文章，即使它们一个字都没提"secure an API"。

pgvector 支持三种距离操作符：

| 操作符 | 含义           | 对应索引操作        |
| ------ | -------------- | ------------------- |
| `<->`  | L2（欧氏）距离 | `vector_l2_ops`     |
| `<=>`  | 余弦距离       | `vector_cosine_ops` |
| `<#>`  | 内积（取负）   | `vector_ip_ops`     |

文本嵌入通常选余弦距离。

**注意**：查询文本必须用**同一个模型**来生成向量。不同模型对应不同的嵌入空间，跨模型比较是无意义的。

## 几点延伸补充

**内存占用和 halfvec**：`vector(1024)` 加上 HNSW 索引，100 万行数据大约需要 10-12 GB 内存。如果数据量大，可以考虑 PostgreSQL 的 `halfvec(1024)`（float16，而不是 float32），存储和内存减半，检索召回率损失不到 1%。

**嵌入模型的选择**：本文用的是本地 Ollama 模型，适合开发和成本敏感的场景。如果要用云端服务，OpenAI 的 embedding API、Azure OpenAI 都可以通过换 `IEmbeddingGenerator` 的注册方式无缝切换，接口代码不用改。

**向量存在关系型数据旁边**：pgvector 最大的优势是向量和关系数据住在同一张表里，可以直接 JOIN、过滤、分页，不用在两套系统之间同步数据。

## 小结

已经在用 PostgreSQL 的项目，不需要专用向量数据库就能加上语义搜索。pgvector 作为一个扩展，启用后立刻就能用。

这篇文章覆盖了完整的工作流：

- **pgvector** 是 PostgreSQL 扩展，启用后获得原生 `vector` 列类型
- **.NET Aspire** 用少量配置就能启动带 pgvector 的 PostgreSQL 和 Ollama
- **嵌入向量** 通过 `IEmbeddingGenerator` 和 `qwen3-embedding` 模型生成
- **相似度搜索** 用 `<=>` 余弦距离操作符找最近匹配
- **HNSW 索引** 在数据量增长时保持查询性能

向量数据和关系数据住在一起，JOIN、过滤、分页都能直接用，不需要维护额外的基础设施。

## 参考

- [原文：Getting Started With PgVector in .NET for Simple Vector Search](https://www.milanjovanovic.tech/blog/getting-started-with-pgvector-in-dotnet-for-simple-vector-search)
- [pgvector GitHub 仓库](https://github.com/pgvector/pgvector)
- [pgvector-dotnet（Dapper、Npgsql、EF Core 支持）](https://github.com/pgvector/pgvector-dotnet)
- [Microsoft.Extensions.AI 介绍](https://www.milanjovanovic.tech/blog/working-with-llms-in-dotnet-using-microsoft-extensions-ai)
- [HNSW 算法（Wikipedia）](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world)
