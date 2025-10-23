---
pubDatetime: 2025-08-28
tags: [".NET", "AI", "DevOps"]
slug: building-generative-ai-applications-with-github-models-and-dotnet-aspire
source: https://www.milanjovanovic.tech/blog/building-generative-ai-applications-with-github-models-and-dotnet-aspire
title: Building Generative AI Applications with GitHub Models and .NET Aspire
description: 探索如何使用 GitHub AI 模型与 .NET Aspire 框架，构建强大且高效的生成式 AI 应用，从原理解析、开发示例到性能优化，全方位深度剖析。
---

# Building Generative AI Applications with GitHub Models and .NET Aspire

在当今 AI 快速发展的时代，生成式 AI 应用正日益成为开发者关注的热点。从智能文案生成到代码自动补全，背后都离不开强大的预训练模型和高效的开发框架。本文将带你全面了解如何结合 GitHub 提供的开源 AI 模型与 .NET Aspire 框架，快速构建高性能、可维护的生成式 AI 应用。

## 1 为什么选择 GitHub 模型与 .NET Aspire

GitHub 推出的 Copilot 以及其它开源大模型（如 CodeGen、CodeBERT）在代码生成和自然语言处理方面表现优异。它们经过海量开源仓库预训练，能够极大提高开发效率。与此同时，.NET Aspire 是微软开源的 .NET 高性能、模块化 Web 应用框架，具备以下优势：

- 原生支持依赖注入和中间件机制，方便扩展 AI 服务。
- 与 .NET 生态深度整合，可无缝引入 ML.NET、Azure Cognitive Services 等组件。
- 高并发、高吞吐，同时提供简洁的 API 调用风格。

两者结合，可以在短时间内搭建出既具备先进 AI 功能，又保持企业级可维护性的应用。

## 2 核心组件与工作原理

在应用架构上，我们主要包含三类组件。

1. 模型服务层
   使用 GitHub 提供的预训练模型，部署在 Docker 容器或云端服务（如 Azure Container Instances）。该服务对外暴露 RESTful 或 gRPC 接口，接收文本或代码片段，并返回预测结果。

2. .NET Aspire 应用层
   作为前端 UI 和业务逻辑的承载者，负责用户请求分发、结果缓存、权限控制以及与模型服务通信。

3. 持久化与缓存层
   结合 Redis、Cosmos DB 或 PostgreSQL 存储历史对话、用户设置以及模型调用日志，实现快速检索和可审计追踪。

下面展示一个简化的调用流程图：

1）用户在 Web 界面输入自然语言查询。
2）Aspire 将请求封装成 gRPC 消息，转发到模型服务。
3）模型服务进行推理，生成响应文本。
4）Aspire 接收结果，执行后处理（如高亮关键字、拼写纠错）。
5）最终结果渲染并返回给前端。

## 3 环境搭建与依赖

要开始动手，你需要具备以下环境：

- .NET 8.0 SDK
- Docker & Docker Compose
- GitHub 模型权重（可从 `ghcr.io/github/codebert-base` 等仓库拉取）
- Redis / PostgreSQL 实例（可本地或云端）

### 3.1 Docker Compose 配置

```yaml
version: "3.8"
services:
  ai-model:
    image: ghcr.io/github/codebert-base:latest
    restart: always
    ports:
      - "50051:50051"
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  aspire-web:
    build: .
    depends_on:
      - ai-model
      - redis
    ports:
      - "5000:80"
```

### 3.2 配置 .NET Aspire

在 `appsettings.json` 中添加模型服务与缓存配置：

```json
{
  "ModelService": {
    "Host": "localhost",
    "Port": 50051
  },
  "Redis": {
    "ConnectionString": "localhost:6379"
  }
}
```

## 4 实现关键代码

### 4.1 定义 gRPC 客户端

```csharp
public interface IAIModelClient
{
    Task<string> GenerateTextAsync(string prompt);
}

public class GrpcAIModelClient : IAIModelClient
{
    private readonly ModelService.ModelServiceClient _client;

    public GrpcAIModelClient(ModelService.ModelServiceClient client)
    {
        _client = client;
    }

    public async Task<string> GenerateTextAsync(string prompt)
    {
        var request = new GenerateRequest { Prompt = prompt, MaxTokens = 150 };
        var response = await _client.GenerateAsync(request);
        return response.Output;
    }
}
```

### 4.2 在 Aspire 中注册服务

```csharp
builder.Services.AddGrpcClient<ModelService.ModelServiceClient>(options =>
{
    var cfg = builder.Configuration.GetSection("ModelService");
    options.Address = new Uri($"http://{cfg["Host"]}:{cfg["Port"]}");
});
builder.Services.AddSingleton<IAIModelClient, GrpcAIModelClient>();
```

### 4.3 控制器示例

```csharp
[ApiController]
[Route("api/[controller]")]
public class GenerationController : ControllerBase
{
    private readonly IAIModelClient _aiClient;
    private readonly IDatabase _cache;

    public GenerationController(IAIModelClient aiClient, IConnectionMultiplexer redis)
    {
        _aiClient = aiClient;
        _cache = redis.GetDatabase();
    }

    [HttpPost]
    public async Task<IActionResult> Post([FromBody] PromptRequest req)
    {
        var cacheKey = $"gen:{req.UserId}:{req.Prompt.GetHashCode()}";
        if (await _cache.KeyExistsAsync(cacheKey))
        {
            var cached = await _cache.StringGetAsync(cacheKey);
            return Ok(new { Text = cached.ToString(), FromCache = true });
        }

        var result = await _aiClient.GenerateTextAsync(req.Prompt);
        await _cache.StringSetAsync(cacheKey, result, TimeSpan.FromMinutes(10));
        return Ok(new { Text = result, FromCache = false });
    }
}
```

## 5 性能优化与扩展

- 批量请求：将多条输入合并成一个批量调用，充分利用 GPU 并行。
- 模型量化与剪枝：使用 ONNX Runtime 或 NVIDIA TensorRT 对模型进行量化，减少延迟。
- 异步队列：对生成任务采用消息队列（如 Azure Service Bus、Kafka）调度，平滑突发流量。
- 安全与配额：在 Aspire 中添加限流中间件，并对用户身份进行鉴权，实现多租户隔离。

## 6 深度分析与最佳实践

生成式 AI 应用在实际落地中，往往要考虑以下几点：

1. Prompt 设计：通过链式提示（Chain-of-Thought）和少量示例（Few-Shot）提升结果准确度。
2. 上下文管理：长会话场景下，需要对历史对话进行摘要与截断，防止上下文过长。
3. 模型更新：定期拉取 GitHub 社区更新的权重，或 fine-tune 私有数据，以保持模型竞争力。
4. 成本控制：合理分配本地推理与云端 API 调用，使用 Spot 实例或预留实例降低开支。

## 7 总结

本文详细演示了如何结合 GitHub 预训练模型与 .NET Aspire 框架，快速打通从前端交互到 AI 推理的完整链路。通过模块化设计、缓存与限流机制，以及性能调优方案，你可以在生产环境中构建稳健、高效的生成式 AI 平台。未来可进一步引入多模态模型、强化学习策略等，持续提升用户体验与业务价值。
