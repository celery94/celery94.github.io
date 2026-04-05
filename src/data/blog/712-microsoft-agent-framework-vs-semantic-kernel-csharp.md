---
pubDatetime: 2026-04-05T09:40:00+08:00
title: "Microsoft Agent Framework vs Semantic Kernel：C# 中如何选择"
description: "Microsoft Agent Framework（MAF）和 Semantic Kernel 都是微软出品的 .NET AI Agent 框架，但设计目标差距显著。本文用对比表格、代码示例和决策指南，帮你在两者之间做出清晰的技术选型判断。"
tags: ["C#", ".NET", "AI", "Semantic Kernel", "Agent"]
slug: "microsoft-agent-framework-vs-semantic-kernel-csharp"
ogImage: "../../assets/712/01-cover.jpg"
source: "https://www.devleader.ca/2026/04/04/microsoft-agent-framework-vs-semantic-kernel-which-to-use-in-c"
---

同样是微软出品，同样面向 .NET AI Agent 开发——但 Microsoft Agent Framework（MAF）和 Semantic Kernel（SK）面向的场景差距比名字暗示的大得多。如果你正在选，这篇文章会直接给你答案：它们分别擅长什么、在哪些场景下更合适，以及什么情况下两个都用才说得通。

有一点要先说清楚：MAF 目前还是预览版（1.0.0-rc1），API 在 GA 正式发布前仍可能变动。

## MAF 是什么

Microsoft Agent Framework 是一个相对较新的轻量级库，目标是让在 .NET 里构建 AI Agent 尽量简单。它原生构建在 [Microsoft.Extensions.AI](https://learn.microsoft.com/en-us/dotnet/ai/microsoft-extensions-ai) 之上，直接使用 `IChatClient` 抽象，与整个 Microsoft.Extensions 生态系统融合，几乎不需要额外的粘合代码，也不需要学习新的 DI 模式或配置方式。

MAF 刻意保持轻量：公开 API 面很小，几行代码就能跑起来一个功能性 Agent。工具注册通过 `AIFunctionFactory.Create()` 来完成，它用普通 C# 委托和反射生成可调用的工具描述，如果你用过 ASP.NET Core 的 minimal API，会觉得很熟悉。

因为基于 `IChatClient`，MAF 天然是 provider 无关的。你已经搭好的 `IChatClient` 中间件——限流、可观测性、重试——会直接应用到 MAF Agent 上，不需要额外桥接。

## Semantic Kernel 是什么

Semantic Kernel 是微软推出的成熟 AI 编排框架，已经持续开发多年。它积累了完善的插件生态、内置的内存和 Embedding 支持、多 Agent 编排原语，以及丰富的 LLM 连接器。

SK 以自己的 `Kernel` 类型作为核心编排对象。函数注册为插件，由规划器或 Agent 循环根据对话上下文来调用。这个设计能力很强，代价是需要理解更多概念、配置更多基础设施。

如果你需要结构化插件层次、RAG 管道、向量数据库集成，或多 Agent 协调工作流，SK 对这些场景都有专门的基础设施。

## 能力对比

| 维度 | Microsoft Agent Framework | Semantic Kernel |
|---|---|---|
| 成熟度 | 公开预览（1.0.0-rc1） | 正式发布（GA） |
| API 复杂度 | 低 | 中高 |
| Microsoft.Extensions.AI 集成 | 原生（IChatClient） | 部分（通过适配器） |
| 插件/工具系统 | `AIFunctionFactory.Create()` | `[KernelFunction]` + Plugin 类 |
| 内存 / Embedding | 无内置支持 | 内置（`IMemoryStore`） |
| 向量数据库 | 无内置支持 | 支持（Azure AI Search、Qdrant 等） |
| 多 Agent 编排 | 基础 | 丰富（`AgentGroupChat`、选择策略等） |
| LLM 连接器 | 任意 `IChatClient` provider | 直接连接器（OpenAI、Azure OpenAI 等） |
| 依赖注入 | 原生 .NET DI | 基于 Kernel 的 DI |
| 社区 / 生态 | 较小（早期阶段） | 成熟且庞大 |
| 上手难度 | 低 | 中等 |
| 适合场景 | 简单、职责单一的 Agent | 功能丰富的复杂 Agent 系统 |

核心取舍很清楚：MAF 赢在简单、生态融合和开发体验；SK 赢在深度、成熟度和功能广度。

## MAF 的优势

对于新项目，MAF 最大的吸引力在于它需要的样板代码极少。如果你已经在用 `IChatClient`，MAF 感觉像自然延伸，而不是需要学习的新框架。

工具注册用委托完成，不需要继承特殊基类、不需要维护属性装饰的插件类层次结构、不需要在调用函数前先配置 Kernel builder。对于小而专注的 Agent，这直接意味着更快的开发速度和更易读的代码库。

MAF 对 `IChatClient` 中间件投入较多的团队特别友好。任何你已经搭建的管道——日志、限流、内容过滤、重试策略——都会自动应用到 MAF Agent 上，不需要额外的抽象层来传递。

另外，没有 `Kernel` 依赖意味着 MAF 能干净地融入微服务式架构，Agent 逻辑可以作为独立的、可替换的组件存在，而不是一个重量级编排器。

## Semantic Kernel 的优势

一旦需求超出简单的对话循环，SK 的成熟度优势就会变得无法忽视。结构化插件层次、自动调用、函数链、插件级配置——SK 对所有这些都有成熟的模式。

内置的内存和 Embedding 支持是另一个显著差异点。SK 包含文本 Embedding 生成、语义记忆和向量数据库集成的一等抽象。你可以构建 RAG 管道和长期记忆功能，而不需要引入额外库。MAF 在这方面没有等价的开箱即用支持。

SK 的多 Agent 支持也丰富得多。`AgentGroupChat` 及相关原语能够以可组合、可配置的方式协调多个 Agent，MAF 目前没有等效的编排脚手架。

最后，SK 拥有更大的社区、更多的文档、更多的第三方集成，以及更长的生产运行记录。如果你在构建一个需要长期维护、团队会持续扩大的系统，这些生态积累的价值很容易被早期低估。

## 代码对比

以下四个示例展示了两种框架完成同一任务的写法。MAF 示例基于 1.0.0-rc1 预览 API，GA 前可能变动。

### 创建基础 Agent

**Semantic Kernel 写法：**

```csharp
using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.Agents;
using Microsoft.SemanticKernel.ChatCompletion;

var kernel = Kernel.CreateBuilder()
    .AddAzureOpenAIChatCompletion(
        deploymentName: "gpt-4o",
        endpoint: "https://your-endpoint.openai.azure.com/",
        apiKey: "your-api-key")
    .Build();

var agent = new ChatCompletionAgent
{
    Name = "CodingAssistant",
    Instructions = "You are a helpful C# coding assistant.",
    Kernel = kernel
};

await foreach (var message in agent.InvokeAsync(
    new ChatMessageContent(AuthorRole.User, "What is a record type in C#?")))
{
    Console.WriteLine(message.Content);
}
```

**Microsoft Agent Framework 写法：**

```csharp
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

IChatClient chatClient = new AzureOpenAIClient(
    new Uri("https://your-endpoint.openai.azure.com/"),
    new AzureKeyCredential("your-api-key"))
    .GetChatClient("gpt-4o")
    .AsIChatClient();

IAIAgent agent = chatClient.AsAIAgent(
    instructions: "You are a helpful C# coding assistant.");

AgentResponse response = await agent.RunAsync("What is a record type in C#?");
Console.WriteLine(response.Text);
```

SK 版本提供更多配置钩子，接入完整的 SK 生态；MAF 版本简洁，完全依托 `IChatClient`，没有引入任何新抽象。

### 函数和工具注册

**Semantic Kernel 使用 `[KernelFunction]`：**

```csharp
using Microsoft.SemanticKernel;
using System.ComponentModel;

public class WeatherPlugin
{
    [KernelFunction("get_weather")]
    [Description("Gets the current weather for a city")]
    public string GetWeather(
        [Description("The name of the city")] string city)
    {
        return $"It is 22°C and sunny in {city}.";
    }
}

kernel.Plugins.AddFromType<WeatherPlugin>();
```

**Microsoft Agent Framework 使用 `AIFunctionFactory`：**

```csharp
using Microsoft.Extensions.AI;

var getWeather = AIFunctionFactory.Create(
    ([Description("The name of the city")] string city) =>
        $"It is 22°C and sunny in {city}.",
    name: "get_weather",
    description: "Gets the current weather for a city");

IAIAgent agent = chatClient.AsAIAgent(
    instructions: "You are a weather assistant.",
    tools: [getWeather]);
```

`[KernelFunction]` 在大型代码库里更结构化，IDE 可发现性好；`AIFunctionFactory` 接线更快，适合不需要正式插件类的单一职责 Agent。

### 多轮对话

**Semantic Kernel 使用 `ChatHistory`：**

```csharp
using Microsoft.SemanticKernel.ChatCompletion;

var history = new ChatHistory();
history.AddSystemMessage("You are a concise technical assistant.");

var chatService = kernel.GetRequiredService<IChatCompletionService>();

history.AddUserMessage("What is dependency injection?");
var reply1 = await chatService.GetChatMessageContentAsync(history);
history.AddAssistantMessage(reply1.Content ?? string.Empty);

history.AddUserMessage("Can you show a C# constructor injection example?");
var reply2 = await chatService.GetChatMessageContentAsync(history);
Console.WriteLine(reply2.Content);
```

**Microsoft Agent Framework 使用 Session：**

```csharp
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

IAIAgent agent = chatClient.AsAIAgent(
    instructions: "You are a concise technical assistant.");

AgentSession session = await agent.CreateSessionAsync();

AgentResponse reply1 = await agent.RunAsync("What is dependency injection?", session);
AgentResponse reply2 = await agent.RunAsync("Can you show a C# constructor injection example?", session);
Console.WriteLine(reply2.Text);
```

两者都支持多轮记忆。SK 的 `ChatHistory` 更显式，可以在任何时候检查和修改消息列表；MAF 的 Session 更封装，Agent 在内部管理状态，你只需传递 `AgentSession` 作为句柄。

### 依赖注入配置

**Semantic Kernel 在 ASP.NET Core 中：**

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddKernel()
    .AddAzureOpenAIChatCompletion(
        deploymentName: "gpt-4o",
        endpoint: builder.Configuration["AzureOpenAI:Endpoint"]!,
        apiKey: builder.Configuration["AzureOpenAI:ApiKey"]!);

builder.Services.AddTransient<WeatherPlugin>();
builder.Services.AddTransient<IAgentService, SkAgentService>();
```

**Microsoft Agent Framework 在 ASP.NET Core 中：**

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<IChatClient>(sp => new AzureOpenAIClient(
    new Uri(builder.Configuration["AzureOpenAI:Endpoint"]!),
    new AzureKeyCredential(builder.Configuration["AzureOpenAI:ApiKey"]!))
    .GetChatClient("gpt-4o")
    .AsIChatClient());

builder.Services.AddSingleton<IAIAgent>(sp =>
    sp.GetRequiredService<IChatClient>().AsAIAgent(instructions: "You are a helpful assistant."));
builder.Services.AddTransient<IAgentService, MafAgentService>();
```

MAF 的 DI 配置更精简，因为它直接继承标准的 Microsoft.Extensions 注册模式，不需要理解 `AddKernel()` builder 和 SK 专属扩展方法。

## 选 MAF 的条件

以下情况 MAF 是更好的选择：

- 绿地项目，没有现有的 SK 代码库需要考虑
- Agent 职责聚焦、边界清晰——一个只调用几个工具的单一用途 Agent，不需要 SK 的完整编排机制
- 你已经在 Microsoft.Extensions.AI 生态上投入较多，希望 `IChatClient` 中间件在所有 AI 调用上统一生效
- 团队把简单快速放在功能广度之前——MAF 从想法到可工作原型更快
- 能接受依赖一个预览 API（1.0.0-rc1）在 GA 前可能有变动

## 选 Semantic Kernel 的条件

以下情况 SK 是更强的选择：

- 需要 RAG 管道或向量数据库集成——MAF 目前没有等效的内置支持，SK 的内存层经过生产验证
- Agent 需要复杂的插件编排，包括自动调用、函数链和插件级配置——`[KernelFunction]` 模型和插件注册表在大型函数库场景下扩展性更好
- 构建带选择策略、群组对话和终止条件的多 Agent 系统——SK 的 `AgentGroupChat` 在这方面远比 MAF 目前提供的能力丰富
- 有现有的 SK 代码库——没有充分理由为同一职责引入第二个框架
- 需要生产稳定性——SK 已 GA，在生产系统中运行多年；MAF 仍是候选版本

## 两者一起用

这是一个合理的架构模式，不只是外交上的折中。在大型 SK 编排系统里，如果包含几个职责单一的内层 Agent——比如处理简单查询或执行窄范围任务——这些内层 Agent 可以用 MAF 实现，同时保持编排层在 SK 中。

基于 `IChatClient` 的 MAF Agent 可以作为 LLM provider 在 SK 工作流内部组合。两个框架在运行时层面并不互斥。可以把它理解为：SK 负责高层编排和插件管理，MAF 负责不需要完整 Kernel 实例的叶节点 Agent。

## 决策表

| 场景 | 选择 |
|---|---|
| 新项目、简单 Agent、已使用 Microsoft.Extensions.AI | MAF |
| 新项目、需要复杂插件或多 Agent 编排 | Semantic Kernel |
| 需要 RAG 或语义记忆 | Semantic Kernel |
| 现有 Semantic Kernel 代码库 | 继续用 SK |
| 需要 GA 稳定性 | Semantic Kernel |
| 绿地项目、最小样板代码优先 | MAF |
| 需要复杂编排层 + 轻量叶节点 Agent | 两者结合 |
| 团队不熟悉 SK、用例边界清晰 | 先试 MAF |
| 长期维护、团队持续增长的系统 | Semantic Kernel |

如果你处于中间地带——SK 的完整功能集有点多余，但 MAF 的预览状态又让你不放心——务实的答案是先用 SK，等 MAF 正式 GA 后再重新评估。随着 MAF 的成熟，两者之间的差距会逐步缩小。

## 常见问题

**MAF 能用于生产环境吗？**

目前还不行。MAF 处于公开预览阶段（1.0.0-rc1），API 在 GA 前可能变动。对稳定性要求严格的生产系统，SK 是更安全的选择。MAF 很适合原型开发和能接受偶尔 breaking change 的绿地项目。

**MAF 和 SK 支持同样的 LLM Provider 吗？**

MAF 通过 Microsoft.Extensions.AI 的 `IChatClient` 抽象做到 provider 无关，任何实现了 `IChatClient` 的 provider 都能用。SK 则有针对 OpenAI、Azure OpenAI、Hugging Face 等的直接连接器包。主流 provider 的覆盖面相近，但机制不同：MAF 依赖 Microsoft.Extensions.AI 适配层，SK 有自己的一等连接器包。

**两个框架的函数调用哪个更好用？**

都支持函数和工具调用，但风格不同。SK 用 `[KernelFunction]` 属性装饰插件方法，在大型代码库里可发现性、文档和结构化注册都更好。MAF 用 `AIFunctionFactory.Create()` 配合委托，轻量，小型 Agent 上更易上手。工具多了之后 SK 的插件注册表扩展性更好；场景简单时 MAF 的委托方式能省掉不少噪音。

**需要保护代码免受 MAF API 变化影响怎么做？**

把 MAF 集成隐藏在自己代码的 service 接口后面。如果 `ChatAgent` API 在 RC 和 GA 之间变动，影响范围应该只限于适配或实现层，而不是你的领域逻辑。这是依赖预览版本的通用最佳实践，不需要 MAF 专属的变通方案。

## 参考

- [Microsoft Agent Framework vs Semantic Kernel: Which to Use in C#](https://www.devleader.ca/2026/04/04/microsoft-agent-framework-vs-semantic-kernel-which-to-use-in-c)
- [Microsoft.Extensions.AI 文档](https://learn.microsoft.com/en-us/dotnet/ai/microsoft-extensions-ai)
- [Semantic Kernel Agents in C# – Complete Guide](https://www.devleader.ca/2026/02/28/semantic-kernel-agents-in-c-complete-guide-to-ai-agents)
- [Semantic Kernel Plugins Complete Guide](https://www.devleader.ca/2026/02/27/semantic-kernel-plugins-in-c-the-complete-guide)
- [Multi-Agent Orchestration with Semantic Kernel](https://www.devleader.ca/2026/03/10/multi-agent-orchestration-with-semantic-kernel-in-c-agentgroupchat-and-selection-strategies)
