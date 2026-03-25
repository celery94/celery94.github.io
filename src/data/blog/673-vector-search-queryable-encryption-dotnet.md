---
pubDatetime: 2026-03-25T09:40:00+08:00
title: "在 .NET 中构建向量搜索与可查询加密的安全 AI 系统"
description: "面向 .NET 架构师和高级工程师的深度技术文章。结合向量搜索、LLM 嵌入与加密计算，探讨如何在合规要求严格的企业环境中，构建兼顾性能与隐私保护的生产级 AI 系统。"
tags: [".NET", "C#", "AI", "Encryption", "Vector Search", "Architecture"]
slug: "vector-search-queryable-encryption-dotnet"
ogImage: "../../assets/673/01-cover.png"
source: "https://dev.to/topuzas/vector-search-and-queryable-encryption-in-net-engineering-secure-ai-systems-at-scale-2ocg"
---

企业 AI 系统正面临一个三重约束：数据量以向量形式爆炸式增长、隐私法规（GDPR、HIPAA、EU AI Act）从学术讨论变成合规强制项，以及一个核心技术难题——**如何在加密数据上执行向量相似度搜索**。

这篇文章是 Ali Suleyman TOPUZ 为 .NET 架构师和安全工程师写的深度技术指南。它不是 Hello World 教程，而是面向生产环境的系统设计，说清楚怎么把向量搜索、LLM 嵌入和隐私计算整合进真实的 .NET 应用。

![向量搜索与加密 AI 系统架构概念图](../../assets/673/01-cover.png)

## 背景：三个汇聚的转折点

驱动这个话题的是三件正在同时发生的事：

1. **非结构化数据的高维化**：文本、图像、音频越来越多以高维向量表示（例如 OpenAI text-embedding-3-small 产出 1536 维的 float 数组）。
2. **隐私保护从可选变成必选**：监管机构要求数据在存储和处理过程中始终保持保护状态，不只是传输层面的加密。
3. **向量搜索与加密之间的矛盾**：向量相似度计算依赖原始数值，而加密会破坏这种可计算性。突破这一矛盾，是企业 AI 系统的核心挑战。

## 核心架构组件

### 向量嵌入服务层

这一层负责把原始业务数据转换成向量表示。在 .NET 中有几个关键设计决策：

- **隔离部署**：用 ASP.NET Core Minimal APIs + `System.Threading.RateLimiting` 对 LLM 上游调用进行限流保护，防止延迟和成本失控。
- **零拷贝数据处理**：在热路径中使用 `ReadOnlyMemory<float>` 或 `Span<float>`，避免高频数组分配带来的 GC 压力。

### 向量存储层

两种主流选型，适用场景不同：

| 方案 | 特点 | 适用场景 |
|---|---|---|
| PostgreSQL + pgvector | ACID 合规，支持关系查询，通过 Npgsql 集成 | 需要关联业务数据的系统 |
| Qdrant | Rust 构建的专用向量数据库，gRPC 支持良好 | 要求 P99 < 50ms、复杂元数据过滤的场景 |

## 领域模型定义

从类型安全的模型开始。核心原则是**把向量数据与业务元数据分离**：

```csharp
public sealed record VectorDocument
{
    public required Guid Id { get; init; }
    public required ReadOnlyMemory<float> Vector { get; init; }
    public required VectorMetadata Metadata { get; init; }
    public string? EncryptionScheme { get; init; }
}

public sealed record VectorMetadata(string Domain, string Source, int ModelVersion);
```

`EncryptionScheme` 字段记录当前向量使用的加密方案，方便在解密时选择正确的策略。

## 安全向量搜索服务

`SecureVectorSearchService` 是整个架构的核心，演示了"生成嵌入 → 加密 → 搜索"的完整流程：

```csharp
public class SecureVectorSearchService(
    IVectorEmbeddingService embeddingService,
    IVectorStore vectorStore,
    IVectorEncryptionService encryptionService,
    ILogger<SecureVectorSearchService> logger)
    : ISecureVectorSearchService
{
    public async Task<IReadOnlyList<VectorSearchResult>> SearchProtectedAsync(
        string plainTextQuery,
        CancellationToken ct = default)
    {
        // 1. 生成嵌入向量
        var rawVector = await embeddingService.GenerateEmbeddingAsync(plainTextQuery, ct);

        // 2. 应用搜索优化加密（如保序加密或同态加密）
        // 该步骤允许数据库在不看到原始值的情况下执行距离计算
        var searchToken = encryptionService.EncryptForSearch(rawVector);

        var request = new VectorSearchRequest
        {
            QueryVector = searchToken, // 传递加密后的 token
            TopK = 10,
            UseEncryption = true
        };

        // 3. 执行搜索并记录可观测指标
        var sw = Stopwatch.StartNew();
        try
        {
            return await vectorStore.SearchAsync(request, ct);
        }
        finally
        {
            logger.LogInformation("Vector search completed in {Elapsed}ms",
                sw.Elapsed.TotalMilliseconds);
        }
    }
}
```

关键设计点：`EncryptForSearch` 使用**搜索优化加密**（保序加密或同态加密），允许向量数据库在密文状态下执行距离计算，数据库侧始终看不到原始向量。

## 距离计算的性能优化

在内存中执行向量相似度计算时（例如缓存层的二次排序），.NET 9 的 `TensorPrimitives` 提供了 SIMD 硬件加速，让多个浮点运算在一个 CPU 时钟周期内并行完成：

```csharp
// SIMD 优化的点积计算（.NET 9）
float similarity = TensorPrimitives.Dot(vectorA.Span, vectorB.Span);
```

相比普通 for 循环，这在高维向量场景下有数倍的吞吐量提升。

## 生产环境可观测性

在生产环境中，不可度量的系统无法管理。原文给出了三个关键指标和目标：

| 指标 | 工具 | P99 目标 |
|---|---|---|
| 嵌入生成延迟 | Azure Monitor | < 200ms |
| 向量索引搜索 | Prometheus / Grafana | < 50ms |
| 解密开销 | 自定义 DotNetCounters | < 5ms |

此外还有两个需要持续监控的质量指标：

- **向量漂移（Vector Drift）**：监控嵌入的统计分布。如果新嵌入与基线之间的平均距离持续增大，说明底层模型可能需要重新训练。
- **召回率 vs. 延迟**：用 OpenTelemetry 追踪 HNSW `ef_search` 参数对搜索精度和延迟的权衡，找到适合业务场景的平衡点。

## 设计取舍与边界

这套架构的适用前提：团队愿意承接加密方案选型和密钥管理的额外工程复杂度。保序加密和同态加密各有信息泄露风险和计算开销，选型需要结合具体合规要求和性能预算。对于不需要加密计算的场景，标准 pgvector + AES-at-rest 往往就够了。

## 参考

- [Vector Search and Queryable Encryption in .NET — Ali Suleyman TOPUZ](https://dev.to/topuzas/vector-search-and-queryable-encryption-in-net-engineering-secure-ai-systems-at-scale-2ocg)
- [原文 Medium 版本](https://topuzas.medium.com/vector-search-and-queryable-encryption-in-net-engineering-secure-ai-systems-at-scale-b30dea8f8551)
