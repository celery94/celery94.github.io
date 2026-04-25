---
pubDatetime: 2026-04-25T10:00:00+08:00
title: "AI Agent 对话历史存储模式：Microsoft Agent Framework 的架构选择"
description: "在哪里存对话历史，是构建 AI Agent 时最关键的架构决策之一。本文系统梳理服务端管理与客户端管理两种根本模式、线性与可分叉的会话模型，以及 Microsoft Agent Framework 如何通过 AgentSession 和 ChatHistoryProvider 抽象屏蔽差异，并附三种 Responses API 配置模式的完整代码示例。"
tags: ["AI", "Agent", "Microsoft Agent Framework", ".NET", "Architecture"]
slug: "chat-history-storage-patterns-microsoft-agent-framework"
ogImage: "../../assets/756/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/chat-history-storage-patterns-in-microsoft-agent-framework"
---

![对话气泡流分叉为服务端云存储与本地客户端存储两条路径](../../assets/756/01-cover.png)

构建 AI Agent 时，大家通常把精力放在模型选型、工具接入和 Prompt 工程上。但有一个更基础的架构问题常常被忽视：**对话历史存在哪里？**

这个选择直接决定了用户能不能续接之前的对话、能不能并行探索不同回答方向、能不能在隔天重新打开对话时让 Agent 还记得昨天说了什么。它还牵涉隐私合规、服务商依赖度，以及你愿意花多少工程成本来维护对话状态。

## 两种根本模式

### 服务端管理（Service-Managed）

AI 服务负责在自己的服务器上存储对话状态。Agent Framework 只在 `AgentSession` 里保存一个引用（比如 `conversation_id` 或 `thread_id`），服务在处理每次请求时自动加载相关历史。

**优势：**
- 客户端实现更简单
- 服务自动处理上下文窗口管理和压缩（compaction）
- 内置跨会话持久化
- 每次请求的 payload 更小（只传一个引用 ID，不传完整历史）

**代价：**
- 数据存在服务商服务器上
- 无法控制哪些上下文被纳入请求
- 无法自定义压缩策略——模型总结、截断哪些消息全由服务决定
- 与特定服务商的会话状态绑定

### 客户端管理（Client-Managed）

Agent Framework 在本地维护完整的对话历史（在 `AgentSession` 或关联的历史提供者中），每次请求时把相关消息一并发送。服务是无状态的——处理完请求就忘。

**优势：**
- 完全掌控数据存储位置和隐私
- 换服务商无需迁移状态
- 精确控制每次请求发送哪些上下文
- 完全掌控压缩策略：截断、总结、滑动窗口、工具调用折叠
- 可以实现自定义上下文策略

**代价：**
- 每次请求 payload 更大
- 客户端必须处理上下文窗口限制
- 随着对话增长，必须自己实现并维护压缩策略
- 客户端逻辑更复杂

## 两种服务端存储形态

不是所有的服务端管理都一样，存储形态决定了你能构建什么样的用户体验。

### 线性（单线程）对话

最传统的聊天模型：消息形成一个有序序列，每条新消息追加到末尾，无法分叉或回退。

典型实现：Microsoft Foundry Prompt Agents、OpenAI Responses + Conversations API。

适合：客服机器人、简单问答流程、需要严格审计轨迹的场景。

局限：无法"回头"尝试不同回答，无法并行探索不同对话路径。

### 可分叉（Forking）对话

现代 Responses API 引入了更灵活的模型：每个响应都有唯一 ID，新请求可以引用任意一个历史响应作为续接点，从而实现对话树的分叉。

典型实现：Microsoft Foundry Responses 端点、Azure OpenAI Responses API、OpenAI Responses API。

适合：探索型和头脑风暴应用、A/B 测试不同回答策略、"撤销"和"重试"功能、树形结构对话 UI、多路径探索的 Agentic 工作流。

## 客户端管理的隐藏复杂度：压缩策略

服务端管理历史时，服务也顺带处理了压缩——把对话上下文保持在模型的 token 限制之内。你不用操心，但也无从控制。

客户端管理时，压缩成了你的责任。随着对话增长，必须采用明确的策略防止上下文窗口溢出并控制成本。常见方案：

- **截断（Truncation）**：超过阈值后丢弃最老的消息
- **滑动窗口（Sliding window）**：只保留最近 N 轮
- **总结（Summarization）**：用 LLM 生成摘要替换更早的消息
- **工具调用折叠（Tool-call collapse）**：把冗长的工具调用/结果对替换为紧凑的摘要

Agent Framework 提供了所有这些模式的内置压缩策略，不需要从头实现。但你仍然需要选择、配置并维护适合自己场景的策略——这是服务端管理所没有的工作量。

## Agent Framework 的抽象层

Microsoft Agent Framework 提供了一个统一编程模型，不管底层用哪种存储模式，应用代码都保持一致。

### AgentSession：统一的对话容器

每次对话都用一个 `AgentSession` 表示。它负责：

- 存储服务端特定标识（线程 ID、响应 ID）
- 保存本地状态（客户端管理场景下的历史记录，或自定义数据库存储的标识符）
- 提供序列化支持，以便跨应用重启持久化

```csharp
// C# — 不管用哪个服务商，用法完全相同
AgentSession session = await agent.CreateSessionAsync();

var first = await agent.RunAsync("My name is Alice.", session);
var second = await agent.RunAsync("What is my name?", session);

// 底层细节由 session 处理：
// - 服务端管理：内部追踪 conversation_id
// - 客户端管理：在本地累积历史
```

```python
# Python
session = agent.create_session()

first = await agent.run("My name is Alice.", session=session)
second = await agent.run("What is my name?", session=session)
```

### ChatHistoryProvider：可插拔的存储后端

需要客户端管理存储时，历史提供者让你控制历史存在哪里、如何检索：

```csharp
// C# — 内置内存提供者（最简单，默认选项）
AIAgent agent = chatClient.AsAIAgent(new ChatClientAgentOptions
{
    ChatOptions = new() { Instructions = "You are a helpful assistant." },
    ChatHistoryProvider = new InMemoryChatHistoryProvider()
});

// 自定义数据库提供者（你来实现）
AIAgent agent = chatClient.AsAIAgent(new ChatClientAgentOptions
{
    ChatOptions = new() { Instructions = "You are a helpful assistant." },
    ChatHistoryProvider = new DatabaseChatHistoryProvider(dbConnection)
});
```

```python
# Python
from agent_framework import InMemoryHistoryProvider

agent = OpenAIChatCompletionClient().as_agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
    context_providers=[InMemoryHistoryProvider("memory", load_messages=True)],
)
```

**关键设计原则：切换服务端管理和客户端管理时，应用代码不需要改变。**

### 透明模式切换

比如你从 OpenAI Chat Completions（客户端管理）迁移到 Responses API（服务端管理+分叉），Agent 调用代码完全不变：

```csharp
// C# — Chat Completions 和 Responses API 调用方式相同
var response = await agent.RunAsync("Hello!", session);
```

`session` 和 `provider` 在背后处理所有差异。这种解耦在实验不同服务商、迁移服务、构建服务商无关应用时很有价值。

## Responses API 的三种配置模式

大多数 AI 服务的存储模式是固定的，但 Responses API（Microsoft Foundry、OpenAI、Azure OpenAI 均支持）是个例外——它通过 `store` 参数可配置。

### 模式一：服务端存储 + 分叉（默认）

最简配置，直接从 Responses 客户端创建 Agent。服务存储所有内容，支持通过响应 ID 分叉。

```csharp
// C# — Responses API，store=true（默认）
AIAgent agent = new OpenAIClient("<your_api_key>")
    .GetResponseClient("gpt-5.4-mini")
    .AsAIAgent(
        instructions: "You are a helpful assistant.",
        name: "ForkingAgent");

AgentSession session = await agent.CreateSessionAsync();
var response1 = await agent.RunAsync("What are three good vacation spots?", session);
// session 内部追踪响应 ID，可以从此处分叉出新的对话分支
```

### 模式二：客户端管理（store=false）

同样的 Responses 客户端，但禁用服务端存储。Agent Framework 在客户端管理历史，完全控制持久化和压缩。

```csharp
// C# — Responses API，store=false
AIAgent agent = new OpenAIClient("<your_api_key>")
    .GetResponseClient("gpt-5.4-mini")
    .AsIChatClientWithStoredOutputDisabled()
    .AsAIAgent(new ChatClientAgentOptions
    {
        ChatOptions = new() { Instructions = "You are a helpful assistant." },
        ChatHistoryProvider = new InMemoryChatHistoryProvider()
    });

AgentSession session = await agent.CreateSessionAsync();
var response = await agent.RunAsync("Hello!", session);
// 历史存在 InMemoryChatHistoryProvider 里，不在服务端。
// 你来控制压缩。
```

### 模式三：线性对话（Conversations API）

基于 Responses 构建，提供线性线程模型。先在服务端创建一个对话，再把 session 与它绑定。

```csharp
// C# — Responses API + Conversations（通过 Foundry）
AIProjectClient aiProjectClient = new(new Uri(endpoint), new DefaultAzureCredential());

FoundryAgent agent = aiProjectClient
    .AsAIAgent("gpt-5.4-mini",
        instructions: "You are a helpful assistant.",
        name: "ConversationAgent");

// 一次调用创建服务端对话并绑定到 session
ChatClientAgentSession session = await agent.CreateConversationSessionAsync();

Console.WriteLine(await agent.RunAsync("What is the capital of France?", session));
Console.WriteLine(await agent.RunAsync("What about Germany?", session));
// 两条响应都属于同一个线性对话线程，由服务管理
```

## 如何选择

选择存储模式时，可以沿着这几个维度判断：

1. **数据主权**：对话数据是否必须留在自己的基础设施里？如果是，客户端管理是唯一选项。
2. **用户体验**：需要支持"重试"、"分叉"或并行探索吗？需要可分叉的服务端管理（Responses API）或客户端管理。
3. **工程成本**：愿意实现并维护压缩策略吗？如果否，服务端管理更省心。
4. **服务商绑定**：应用是否需要跨服务商可移植？客户端管理的状态不依赖任何服务商。

核心原则：**根据实际需求选择（隐私、控制权、功能），而不是只图一开始方便**。正确的存储模式会让你的应用在长期维护上更有竞争力。

## 参考

- [原文：Chat History Storage Patterns in Microsoft Agent Framework](https://devblogs.microsoft.com/agent-framework/chat-history-storage-patterns-in-microsoft-agent-framework)
- [Microsoft Agent Framework: Conversations & Memory 文档](https://learn.microsoft.com/agent-framework/agents/conversations/)
- [Microsoft Agent Framework: Provider 指南](https://learn.microsoft.com/agent-framework/agents/providers/)
