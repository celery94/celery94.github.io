---
pubDatetime: 2026-05-06T08:20:00+08:00
title: ".NET AI 核心构建块：Microsoft.Extensions.AI 详解"
description: "微软发布了面向 .NET 开发者的 AI 基础构建块系列，本文聚焦第一块：Microsoft.Extensions.AI（MEAI）。它提供统一的 LLM 访问接口，支持 OpenAI、OllamaSharp、Azure OpenAI 等多家提供商，并内置结构化输出、中间件、多模态内容等能力，是构建 .NET 智能应用的基础。"
tags: [".NET", "AI", "Microsoft.Extensions.AI", "C#", "LLM"]
slug: "dotnet-ai-essentials-meai-building-blocks"
ogImage: "../../assets/772/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/dotnet-ai-essentials-the-core-building-blocks-explained/"
---

微软 .NET 团队正式推出了面向 .NET 开发者的 AI 构建块系列。这是一个四篇文章的系列，分别介绍四个核心组件：

- **Microsoft.Extensions.AI**：统一 LLM 接口访问
- **Microsoft.Extensions.VectorData**：语义搜索与向量持久化
- **Microsoft Agent Framework**：智能体工作流
- **Model Context Protocol（MCP）**：互操作性

本文是系列第一篇，专注于 `Microsoft.Extensions.AI`（以下简称 MEAI）。

![多路 AI 提供商数据流汇聚成统一管道的示意图](../../assets/772/01-cover.png)

## 什么是 Microsoft.Extensions.AI

MEAI 是 .NET 中与生成式 AI 交互的基础库，由原 Semantic Kernel 团队贡献了核心抽象与 API 设计，再结合 ASP.NET、Minimal APIs 和 Blazor 中已有的依赖注入、中间件、构建者模式等成熟实践。

如果你用过 Semantic Kernel，可以把 MEAI 理解为对 SK 基础层的替换和升级——更轻量，更专注于底层接口。

## 统一 API，切换提供商零成本

MEAI 最直接的价值是：不用再维护多套 SDK，用一套 API 就能对接 OpenAI、OllamaSharp、Azure OpenAI 等主流提供商。

以 OllamaSharp 为例，原始用法是这样的：

```csharp
var uri = new Uri("http://localhost:11434");
var ollama = new OllamaApiClient(uri)
{
    SelectedModel = "mistral:latest"
};
await foreach (var stream in ollama.GenerateAsync("How are you today?"))
{
    Console.Write(stream.Response);
}
```

原始 OpenAI SDK 用法：

```csharp
OpenAIResponseClient client = new("o3-mini", Environment.GetEnvironmentVariable("OPENAI_API_KEY"));

OpenAIResponse response = await client.CreateResponseAsync(
    [ResponseItem.CreateUserMessageItem("How are you today?")]
);
foreach (ResponseItem outputItem in response.OutputItems)
{
    if (outputItem is MessageResponseItem message)
    {
        Console.WriteLine($"{message.Content.FirstOrDefault()?.Text}");
    }
}
```

两者的 API 形状完全不同。MEAI 引入了 `IChatClient` 接口来统一它们。OllamaSharp 已原生实现该接口；OpenAI 客户端则需要通过适配器包（[Microsoft.Extensions.AI.OpenAI](https://www.nuget.org/packages/Microsoft.Extensions.AI.OpenAI/)）转换：

```csharp
IChatClient client =
    new OpenAIClient(key).GetChatClient("o3-mini").AsIChatClient();
```

转换之后，发送请求的代码对所有提供商完全一致：

```csharp
await foreach (ChatResponseUpdate update in client.GetStreamingResponseAsync("How are you today?"))
{
    Console.Write(update);
}
```

同一段业务代码，背后接的是哪家服务，换个 `IChatClient` 实例就行。

## 结构化输出：省掉解析代码

结构化输出让你能直接拿到强类型对象，而不是从字符串里手工解析 JSON。MEAI 把这件事简化到了极致。

先看使用原始 OpenAI SDK 的写法：

```csharp
class Family
{
    public List<Person> Parents { get; set; }
    public List<Person>? Children { get; set; }

    class Person
    {
        public string Name { get; set; }
        public int Age { get; set; }
    }
}

ChatCompletionOptions options = new()
{
    ResponseFormat = StructuredOutputsExtensions.CreateJsonSchemaFormat<Family>("family", jsonSchemaIsStrict: true),
    MaxOutputTokenCount = 4096,
    Temperature = 0.1f,
    TopP = 0.1f
};

List<ChatMessage> messages =
[
    new SystemChatMessage("You are an AI assistant that creates families."),
    new UserChatMessage("Create a family with 2 parents and 2 children.")
];

ParsedChatCompletion<Family?> completion = chatClient.CompleteChat(messages, options);
Family? family = completion.Parsed;
```

使用 MEAI 的泛型扩展方法，同样的目标只需这几行：

```csharp
class Family
{
    public List<Person> Parents { get; set; }
    public List<Person>? Children { get; set; }

    class Person
    {
        public string Name { get; set; }
        public int Age { get; set; }
    }
}

var family = await client.GetResponseAsync<Family>(
[
    new ChatMessage(ChatRole.System, "You are an AI assistant that creates families."),
    new ChatMessage(ChatRole.User, "Create a family with 2 parents and 2 children.")
]);
```

`GetResponseAsync<T>` 内部会自动构造 Schema、发送请求、反序列化结果。不用手写 `ResponseFormat`，不用手写 `JsonSerializer.Deserialize`。

## 请求与响应的标准化

`ChatOptions` 类统一了所有提供商的调参接口，包括：

- **temperature（温度）**：控制输出随机性。低温度（如 0.1）让模型更确定，输出更贴近事实，适合分类、摘要；高温度（如 0.9）引入更多随机性，适合创意写作或头脑风暴
- **最大 Token 数**：控制输出长度
- 其他采样参数（TopP、频率惩罚等）

在返回结果中，`UsageDetails` 实例包含本次请求消耗的 Token 数，方便你在成本敏感场景下做监控和控制。

## 中间件：在请求管道中插入逻辑

.NET Web 开发者对中间件不陌生，ASP.NET 的请求管道就是这个模型。MEAI 把同样的机制引入到了 LLM 调用流程里，让你可以在请求到达模型之前或响应返回之后插入逻辑：

- 过滤敏感内容
- 限流或熔断
- 遥测与追踪

MEAI 内置了日志和 OpenTelemetry（OTEL）中间件。以下示例展示如何通过构建者模式给任意 `IChatClient` 加上这两种能力：

```csharp
public IChatClient BuildEnhancedChatClient(
    IChatClient innerClient,
    ILoggerFactory? loggerFactory = null)
{
    var builder = new ChatClientBuilder(innerClient);

    if (loggerFactory is not null)
    {
        builder.UseLogging(loggerFactory);
    }

    var sensitiveData = false; // 调试时改为 true

    builder.UseOpenTelemetry(
        configure: options =>
            options.EnableSensitiveData = sensitiveData);

    return builder.Build();
}
```

OTEL 事件可以推送到 Application Insights 等云服务，或者在使用 .NET Aspire 时直接显示在 Aspire 仪表板上——Aspire 已经更新以支持智能应用的额外上下文，LLM 相关的追踪会用"✨"图标标记。

## DataContent：多模态对话

现代 AI 模型不只处理文本，越来越多的多模态模型可以接收图像、音频，并返回同类内容。MEAI 中的内容类型都派生自 `AIContent`：

- `TextContent`：文本（最常用）
- `DataContent`：任意媒体类型（字节数组 + MIME 类型）
- `ErrorContent`：带错误码的详细错误信息
- `FunctionCallContent`：工具调用请求
- `HostedFileContent`：引用 AI 服务托管的资源
- `UriContent`：Web 引用

其中 `DataContent` 最为通用。想让模型分析一张照片？传入字节数组加 MIME 类型就行：

```csharp
var instructions = "You are a photo analyst able to extract the utmost detail from a photograph and provide a description so thorough and accurate that another LLM could generate almost the same image just from your description.";

var prompt = new TextContent("What's this photo all about? Please provide a detailed description along with tags.");

var image = new DataContent(File.ReadAllBytes(@"c:\photo.jpg"), "image/jpeg");

var messages = new List<ChatMessage>
{
    new(ChatRole.System, instructions),
    new(ChatRole.User, [prompt, image])
};

record ImageAnalysis(string Description, string[] tags);

var analysis = await chatClient.GetResponseAsync<ImageAnalysis>(messages);
```

用户消息里同时包含文字和图片，MEAI 负责把它组装成提供商接受的格式。

## 其他能力

除了本文介绍的内容，MEAI 还提供：

- **取消令牌（Cancellation tokens）**：保持应用响应性
- **内置错误处理和弹性机制**
- **向量和嵌入的基础原语**（为 VectorData 系列铺垫）
- **图像生成**接口

## 系列延伸

这是四篇系列文章的第一篇，后续三篇将分别介绍：

1. **Microsoft.Extensions.VectorData**：向量扩展与语义搜索（Part 2）
2. **Microsoft Agent Framework**：智能体框架（Part 3）
3. **Model Context Protocol（MCP）**：互操作性（Part 4）

如果你想马上动手，可以参考以下资源：

- [MEAI 源码仓库](https://github.com/dotnet/extensions/blob/main/src/Libraries/Microsoft.Extensions.AI.Abstractions/)
- [MEAI 示例代码](https://github.com/dotnet/ai-samples/tree/main/src/microsoft-extensions-ai)
- [官方文档：Microsoft Extensions for AI](https://learn.microsoft.com/dotnet/ai/microsoft-extensions-ai)
- [快速入门：构建 AI 聊天应用](https://learn.microsoft.com/dotnet/ai/quickstarts/build-chat-app?pivots=openai)

## 参考

- [.NET AI Essentials – The Core Building Blocks Explained](https://devblogs.microsoft.com/dotnet/dotnet-ai-essentials-the-core-building-blocks-explained/)
- [Microsoft.Extensions.AI.OpenAI NuGet 包](https://www.nuget.org/packages/Microsoft.Extensions.AI.OpenAI/)
- [Microsoft Extensions for AI 文档](https://learn.microsoft.com/dotnet/ai/microsoft-extensions-ai)
