---
pubDatetime: 2026-03-19T16:00:00+08:00
title: "用后台响应处理 AI Agent 的长时间运行操作"
description: "Microsoft Agent Framework 引入后台响应机制，让 AI Agent 可以在后台处理耗时的复杂推理、长内容生成任务，客户端通过 continuation token 轮询结果或断点续传流式输出，彻底解决连接超时和进度丢失问题。"
tags: ["AI", "Agent Framework", "Microsoft", ".NET", "Python", "Background Processing"]
slug: "handling-long-running-operations-background-responses"
source: "https://devblogs.microsoft.com/agent-framework/handling-long-running-operations-with-background-responses"
---

AI Agent 在处理复杂任务时，往往需要几分钟的推理时间——深度研究、多步骤分析、长篇内容生成都是典型场景。传统的请求-响应模式下，客户端要么傻等连接，要么超时失败，所有进度归零。

Microsoft Agent Framework 的**后台响应（Background Responses）**功能解决了这个问题：发起任务后立刻拿到一个 continuation token，应用可以按自己的节奏轮询结果，断线后也能从断点精确恢复流式输出。该功能在 .NET 和 Python SDK 中均已可用。

## 工作原理

启用后台响应后，送出请求时会有两种情况：

1. **立即完成** — 如果 Agent 不支持后台处理，直接返回最终响应，无 continuation token。
2. **后台处理** — 如果 Agent 支持后台处理，立即返回 continuation token，Agent 在后台继续运行。

continuation token 记录了当前操作的状态。当它为 `null`（.NET）或 `None`（Python）时，说明操作已完成——可能是成功、失败，也可能是等待用户进一步输入。

## 适用场景

后台响应适合以下类型的 Agent 任务：

- **复杂推理** — o3、GPT-5.2 等推理模型需要较长时间处理多步问题
- **长内容生成** — 详细报告、深度分析、多章节文档
- **网络条件不稳定** — 移动端、边缘部署或任何可能断线的环境
- **异步用户体验** — "提交后离开"模式，用户稍后回来查看结果

## 非流式：轮询等待完成

最简单的用法是发起后台任务，然后轮询结果。

### .NET

```csharp
AIAgent agent = new AzureOpenAIClient(
    new Uri("https://<myresource>.openai.azure.com"),
    new DefaultAzureCredential())
    .GetResponsesClient("<deployment-name>")
    .AsAIAgent();

AgentRunOptions options = new()
{
    AllowBackgroundResponses = true // 启用后台响应
};

AgentSession session = await agent.CreateSessionAsync();

// 发起任务 — 可能立即完成，也可能返回 continuation token
AgentResponse response = await agent.RunAsync(
    "Write a detailed market analysis for the Q4 product launch.", session, options);

// 轮询直到完成
while (response.ContinuationToken is not null)
{
    await Task.Delay(TimeSpan.FromSeconds(2));

    options.ContinuationToken = response.ContinuationToken;
    response = await agent.RunAsync(session, options);
}

Console.WriteLine(response.Text);
```

### Python

```python
import asyncio
from agent_framework.openai import OpenAIResponsesClient

agent = OpenAIResponsesClient(model_id="o3").as_agent(
    name="researcher",
    instructions="You are a helpful research assistant.",
)

session = await agent.create_session()

# 发起后台任务
response = await agent.run(
    messages="Write a detailed market analysis for the Q4 product launch.",
    session=session,
    options={"background": True},
)

# 轮询直到完成
while response.continuation_token is not None:
    await asyncio.sleep(2)
    response = await agent.run(
        session=session,
        options={"continuation_token": response.continuation_token},
    )

print(response.text)
```

关键点：

- 如果没有返回 continuation token，说明操作已立即完成，无需轮询。
- 每次轮询时，把上一次拿到的 token 传入下一次请求。
- 当 token 为 `null`/`None` 时，表示已拿到最终结果。

## 流式输出 + 断点续传

如果希望实时看到进度，同时保留后台处理的好处，可以用流式模式。每个流式更新都携带 continuation token，连接断开后用它从断点恢复。

### .NET

```csharp
AgentRunOptions options = new()
{
    AllowBackgroundResponses = true
};

AgentSession session = await agent.CreateSessionAsync();

AgentResponseUpdate? latestUpdate = null;

await foreach (var update in agent.RunStreamingAsync(
    "Write a detailed market analysis for the Q4 product launch.", session, options))
{
    Console.Write(update.Text);
    latestUpdate = update;

    // 模拟网络中断
    break;
}

// 从断点精确恢复
options.ContinuationToken = latestUpdate?.ContinuationToken;
await foreach (var update in agent.RunStreamingAsync(session, options))
{
    Console.Write(update.Text);
}
```

### Python

```python
session = await agent.create_session()

last_token = None

# 开始流式传输，启用后台模式
async for update in agent.run(
    messages="Write a detailed market analysis for the Q4 product launch.",
    stream=True,
    session=session,
    options={"background": True},
):
    last_token = update.continuation_token
    if update.text:
        print(update.text, end="", flush=True)

    # 模拟网络中断
    break

# 使用保存的 token 恢复流式传输
if last_token is not None:
    async for update in agent.run(
        stream=True,
        session=session,
        options={"continuation_token": last_token},
    ):
        if update.text:
            print(update.text, end="", flush=True)
```

关键点：

- 每个流式更新都携带 continuation token，始终保存最新的那个。
- 连接断开后，用保存的 token 从中断处恢复，不丢失任何内容。
- 即使客户端断开，Agent 也会在服务端继续处理。

## 内置容错能力

后台响应的实际价值之一是对连接问题的天然弹性。Agent 在服务端持续运行，与客户端状态无关：

- **网络中断** — 客户端重连后用最后保存的 continuation token 继续。
- **客户端重启** — 把 token 持久化到存储，从新进程恢复操作。
- **超时保护** — 长时间任务不会因为连接超时而中途失败。

生产环境建议将 continuation token 持久化到数据库或缓存，让操作不仅能抵御网络抖动，还能在整个应用重启后恢复。对于 Agent 任务可能运行数分钟的企业场景，这一点尤为重要。

## 典型用例

### 合规文档生成

企业合规团队用 Agent 生成监管申报文件，需要模型推理复杂法规，耗时可能达数分钟。后台响应让应用提交请求后展示进度条，轮询结果，无需担心请求在生成过程中超时。

### 研究与分析

金融服务 Agent 需要对市场数据、SEC 公告和新闻做深度综合分析。后台响应让应用在推理模型工作期间释放 UI，结果准备好后再通知用户。

### 批处理流水线

数据工程团队对大型数据集批量运行 Agent 提取信息。每条任务可能需要较长推理时间。后台响应让流水线并行提交任务、轮询完成情况，单条失败不影响其余进度。

## 最佳实践

- **合理的轮询间隔** — 从 2 秒开始，对运行时间较长的任务考虑指数退避。
- **始终检查 null token** — 这是操作完成的信号，不要跳过。
- **持久化 continuation token** — 对可能跨越用户会话或应用重启的操作，必须将 token 存入持久存储。

## 支持的 Agent

后台响应目前完整支持基于 Responses API 的 [OpenAI](https://learn.microsoft.com/en-us/agent-framework/agents/providers/openai) 和 [Azure OpenAI](https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-openai) 提供商——对应 .NET 中的 `ChatClientAgent` 和 Python 中的 `Agent`。`A2AAgent` 对后台响应的支持目前有限，改进计划已在路线图中。

可访问结果的时间窗口受底层服务数据保留策略的限制。

## 参考链接

- [后台响应文档（Microsoft Learn）](https://learn.microsoft.com/en-us/agent-framework/agents/background-responses)
- [Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [讨论社区](https://github.com/microsoft/agent-framework/discussions)
