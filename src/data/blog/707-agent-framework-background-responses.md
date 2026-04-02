---
pubDatetime: 2026-04-02T10:00:00+08:00
title: "用 Background Responses 处理 AI Agent 的长时运行操作"
description: "Microsoft Agent Framework 的 Background Responses 特性让你把耗时的 AI Agent 任务卸载到后台执行：获取 continuation token、轮询完成状态、流式断点续传，以及在 .NET 与 Python 中的完整实现示例。"
tags: ["AI Agent", "Microsoft Agent Framework", ".NET", "Python"]
slug: "agent-framework-background-responses"
ogImage: "../../assets/707/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/handling-long-running-operations-with-background-responses/"
---

由推理模型驱动的 AI Agent 可能需要花数分钟处理复杂问题——深度研究、多步分析、大篇幅内容生成。在传统的请求-响应模式下，这意味着客户端需要一直等待，连接可能超时，或者更糟——静默失败并丢失所有进度。

Microsoft Agent Framework 的 **Background Responses** 特性让你把这些长时运行的操作卸载到后台，让应用无论 Agent 需要多长时间都能保持响应和弹性。

![封面](../../assets/707/01-cover.png)

## 工作原理

启用 Background Responses 后，向 Agent 发送请求时会发生以下两种情况之一：

- **立即完成**——如果 Agent 不支持后台处理，它会在当前请求内同步完成并直接返回最终结果，不会生成 continuation token。
- **后台处理**——如果 Agent 支持后台处理，它会在后台开始工作，并返回一个 **continuation token**，你用它来检查进度或恢复流式输出。

Continuation token 捕获了操作的当前状态。当它为 `null`（.NET）或 `None`（Python）时，操作已完成——响应已就绪、操作失败，或需要进一步输入。

## 适用场景

Background Responses 适用于以下 Agent 任务：

| 场景 | 说明 |
|------|------|
| **复杂推理** | 使用 o3、GPT-5.2 等需要时间推理多步问题的模型 |
| **长内容生成** | 生成详细报告、大量分析或多部分文档 |
| **不稳定网络环境** | 移动客户端、边缘部署等连接可能中断的场景 |
| **异步用户体验** | "提交后离开"模式——用户提交任务后稍后查看结果 |

## 方式一：轮询等待完成（非流式）

最简单的用法是启动后台任务，然后轮询直到结果就绪。

**C# (.NET)：**

```csharp
AIAgent agent = new AzureOpenAIClient(new DefaultAzureCredential())
    .GetResponsesClient("your-model-deployment")
    .AsAIAgent();

AgentRunOptions options = new()
{
    AllowBackgroundResponses = true  // 启用后台响应
};

AgentSession session = await agent.CreateSessionAsync();

// 启动任务——可能立即完成，或返回 continuation token
AgentResponse response = await agent.RunAsync("Analyze this dataset...", session, options);

// 轮询直到完成
while (response.ContinuationToken != null)
{
    await Task.Delay(TimeSpan.FromSeconds(2));
    options.ContinuationToken = response.ContinuationToken;
    response = await agent.RunAsync(session, options);
}

Console.WriteLine(response.Text);
```

**Python：**

```python
from agent_framework.openai import OpenAIResponsesClient

agent = OpenAIResponsesClient(model_id="your-model").as_agent(
    name="my-agent",
    instructions="You are a helpful assistant.",
)

session = await agent.create_session()

# 启动后台任务
response = await agent.run(
    messages="Analyze this dataset...",
    session=session,
    options={"allow_background_responses": True},
)

# 轮询直到操作完成
while response.continuation_token is not None:
    await asyncio.sleep(2)
    response = await agent.run(
        session=session,
        options={"continuation_token": response.continuation_token},
    )

print(response.text)
```

**关键要点：**
- 如果没有返回 continuation token，说明操作已立即完成，无需轮询。
- 将每次响应中的 continuation token 传入下一次轮询调用。
- Token 为 `null`/`None` 时，即为最终结果。

## 方式二：流式输出 + 断点续传

对于更流畅的用户体验，你可以实时流式接收结果，同时仍能享受后台处理的好处。每个流式更新都携带 continuation token，因此如果连接中断，可以从中断处精确恢复。

**C# (.NET)：**

```csharp
AgentRunOptions options = new()
{
    AllowBackgroundResponses = true  // 启用后台响应
};

AgentSession session = await agent.CreateSessionAsync();

AgentResponseUpdate? latestUpdate = null;

// 开始流式接收
await foreach (var update in agent.RunStreamingAsync("Generate a report...", session, options))
{
    Console.Write(update.Text);
    latestUpdate = update;
}

// 模拟网络中断后，从断点精确恢复
options.ContinuationToken = latestUpdate?.ContinuationToken;

await foreach (var update in agent.RunStreamingAsync(session, options))
{
    Console.Write(update.Text);
}
```

**Python：**

```python
session = await agent.create_session()
last_token = None

# 启动带后台支持的流式输出
async for update in agent.run(
    messages="Generate a report...",
    stream=True,
    session=session,
    options={"allow_background_responses": True},
):
    last_token = update.continuation_token
    if update.text:
        print(update.text, end="")

# 模拟网络中断后，用最后一个 continuation token 恢复流
if last_token:
    async for update in agent.run(
        stream=True,
        session=session,
        options={"continuation_token": last_token},
    ):
        if update.text:
            print(update.text, end="")
```

**关键要点：**
- 每次流式更新都包含 continuation token——保存最新的那个。
- 如果流中断，用保存的 token 从该精确位置恢复。
- 即使客户端断开连接，Agent 也会在服务端继续处理。

## 内置容错能力

Background Responses 的实用价值之一在于对连接问题的弹性：Agent 无论客户端连接发生什么都会在服务端继续处理，你无需自己构建容错机制：

- **网络中断**——客户端可以用最后的 continuation token 重新连接并恢复。
- **客户端重启**——把 continuation token 持久化到存储中（数据库或缓存），从新进程接续操作。
- **超时保护**——长时运行任务不会因连接持有时间过长而失败。

> **生产环境建议**：将 continuation token 持久化存储（数据库或缓存），让操作不仅能从网络抖动中恢复，还能从完整的应用重启中恢复。这对 Agent 任务可能运行数分钟的企业场景尤其有价值。

## 真实场景举例

**企业合规报告**：合规团队用 Agent 生成监管文件，需要模型梳理复杂指引，可能耗时数分钟。应用提交请求后向用户展示进度指示器并轮询结果——不存在请求中途超时的风险。

**金融深度分析**：金融服务 Agent 跨市场数据、SEC 文件和新闻进行深度分析，推理模型需要时间综合多源信息。后台响应让应用启动分析后释放 UI，结果就绪时通知用户。

**大数据集批处理**：数据工程团队对大数据集运行 Agent 提取洞察，每条数据可能需要较长的推理时间。后台响应让流水线并行提交任务、轮询完成，并在不影响其他任务进度的情况下处理个别失败。

## 使用建议

- **合理设置轮询间隔**——从 2 秒间隔开始，对于运行更久的任务考虑指数退避。
- **始终检查 null continuation token**——这是处理完成的信号。
- **持久化 continuation token**——对于可能跨越用户会话或应用重启的操作。

## 支持范围

Background Responses 在使用 **Azure OpenAI** 提供商的 Responses API 时完全支持——.NET 中通过 `ChatClientAgent`，Python 中通过对应客户端。`ChatCompletions` API 对后台响应的支持有限，计划在后续版本改进。

可访问响应数据的时间受底层服务数据保留策略的约束。

## 快速上手

- [Microsoft Learn：Background Responses 文档](https://learn.microsoft.com/agent-framework)
- [Microsoft Agent Framework GitHub 仓库](https://github.com/microsoft/agent-framework)
- [GitHub 讨论区](https://github.com/microsoft/agent-framework/discussions)——提交反馈、提问、与社区交流

## 总结

Background Responses 通过 continuation token 机制，把长时运行的 AI Agent 任务从"阻塞请求"变成"可随时恢复的异步操作"。核心优势：

| 能力 | 传统模式 | Background Responses |
|------|---------|---------------------|
| 连接超时风险 | 高 | 无 |
| 网络中断恢复 | 从头重来 | 从断点续传 |
| 客户端响应性 | 阻塞等待 | 立即释放 |
| 容错复杂度 | 需要自建 | 内置支持 |

对于任何使用推理模型或生成长篇内容的 Agent 应用，这个特性都值得优先考虑引入。

## 参考

- [原文：Handling Long-Running Operations with Background Responses](https://devblogs.microsoft.com/agent-framework/handling-long-running-operations-with-background-responses/)
- [Microsoft Agent Framework 官方博客](https://devblogs.microsoft.com/agent-framework/)
