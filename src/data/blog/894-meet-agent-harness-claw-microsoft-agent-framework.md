---
pubDatetime: 2026-06-24T12:49:32+08:00
title: "认识 Agent Harness：用 Microsoft Agent Framework 三步搭建个人理财助手"
description: "Microsoft Agent Framework 的 harness 把 agent 开发里最繁琐的部分——工具调用、会话持久化、计划模式、网页搜索——打包成一个调用。这篇文章用个人理财助手做例子，分三步把它搭起来：构造 chat client、包装成 harness、在交互式控制台里跑起来。"
tags: [".NET", "Agent Framework", "AI", "Python"]
slug: "meet-agent-harness-claw-microsoft-agent-framework"
ogImage: "../../assets/894/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/meet-your-agent-harness-and-claw/"
---

"Claw" 这个词在 agent 开发圈子里指的是围绕一个大模型做的一套完整循环——工具调用、计划、记忆、多步执行。Microsoft Agent Framework 把它叫做 **agent harness**，而且把它做成了一个你几乎不用写胶水代码的东西。

这篇文章是系列教程的第一篇，目标是用 harness 搭一个**个人理财助手**：能查股价、能搜财经新闻、能在 plan 模式下做多步分析。标题里的"三步"是实际的代码量——构造 chat client、包装成 harness、在控制台里跑。框架已经把函数调用、历史持久化、计划模式和网页搜索塞进了 `AsHarnessAgent` 这一个调用里，你只需要提供"你的 agent 跟别人不一样的地方"：指令和自定义工具。

> 本文是 [Build your own claw with Microsoft Agent Framework](https://devblogs.microsoft.com/agent-framework/build-your-own-claw-and-agent-harness-with-microsoft-agent-framework/) 系列的第一篇，作者 Wes Steyn。示例同时覆盖 .NET 和 Python。

## 第一步：构造 Chat Client

一切从 chat client 开始——它负责和大模型对话。你需要指定端点、认证方式和模型部署名。示例用的是 Microsoft Foundry + Responses API。

**.NET：**

```csharp
var endpoint = Environment.GetEnvironmentVariable("FOUNDRY_PROJECT_ENDPOINT")
    ?? throw new InvalidOperationException("FOUNDRY_PROJECT_ENDPOINT is not set.");
var deploymentName = Environment.GetEnvironmentVariable("FOUNDRY_MODEL") ?? "gpt-5.4";

IChatClient chatClient =
    new AIProjectClient(new Uri(endpoint), new DefaultAzureCredential())
        .GetProjectOpenAIClient()
        .GetResponsesClient()
        .AsIChatClient(deploymentName);
```

**Python：**

```python
client = FoundryChatClient(credential=AzureCliCredential())
```

`FOUNDRY_PROJECT_ENDPOINT` 是你的 Foundry 项目端点，`FOUNDRY_MODEL` 是模型部署名（例如 `gpt-5.4`）。认证方面，本地开发用 `DefaultAzureCredential`（.NET）或 `AzureCliCredential`（Python）就行，生产环境应该换成 `ManagedIdentityCredential`。

使用 Microsoft Foundry 只是示例——harness 可以和任何 chat client 配合：Azure OpenAI、OpenAI、Anthropic、Google Gemini、Ollama 都行。参考 [.NET AgentProviders](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/AgentProviders) 和 [Python providers](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/providers) 了解每种客户端的构造方式。

## 第二步：包装成 Harness

有了 chat client 之后，把它包进 harness，注入两样东西：agent 的**指令**和一个**自定义工具**。

### 指令（Instructions）

指令告诉 agent 它是做什么的。示例里是一个理财助手：

```
你是个人理财和投资助手。当被问到股票时，用 get_stock_price 工具查询当前价格，
用网页搜索获取最新消息、财报或分析师评论。

工作风格：
- 永远用工具验证数据，不要依赖记忆。股价在变。
- 引用网页来源时在文中标注。
- 把用户的关注列表保存在 watchlist.md 文件中：查看列表时读取，增删时更新。
```

### 自定义工具

工具就是一个模型可以调用的函数。这里暴露一个 `get_stock_price`，框架根据函数签名和参数描述自动生成 JSON schema：

**.NET：**

```csharp
[Description("Gets the latest (delayed, illustrative) stock price for a ticker symbol.")]
public static StockQuote GetStockPrice(
    [Description("The stock ticker symbol, e.g. MSFT or AAPL.")] string symbol)
{
    return new StockQuote(symbol.ToUpperInvariant(), price, "USD", DateTimeOffset.UtcNow);
}

public static AIFunction CreateGetStockPriceTool() =>
    AIFunctionFactory.Create(GetStockPrice, "get_stock_price");
```

**Python：**

```python
def get_stock_price(
    symbol: Annotated[str, "The stock ticker symbol, e.g. MSFT or AAPL."],
) -> dict[str, object]:
    """Get the latest (delayed, illustrative) stock price for a ticker symbol."""
    return {"symbol": ticker, "price": round(price, 2), "currency": "USD", "as_of": ...}
```

示例用的是内存中的模拟数据，不需要外部依赖。真实场景下换成行情 API 就行。

### 组装

指令和工具都准备好之后，一行代码创建 agent：

**.NET：**

```csharp
AIAgent agent = chatClient.AsHarnessAgent(new HarnessAgentOptions
{
    ChatOptions = new ChatOptions
    {
        Instructions = instructions,
        Tools = [StockTools.CreateGetStockPriceTool()],
    },
});
```

**Python：**

```python
agent = create_harness_agent(
    client=client,
    agent_instructions=FINANCE_INSTRUCTIONS,
    tools=get_stock_price,
)
```

这一个调用就包含了：函数调用、每次服务调用的历史持久化、用于计划的 `TodoProvider` 和 `AgentModeProvider`，以及**网页搜索**——全部默认开启，且逐项可配置。

这就是为什么网页搜索和计划"凭空就能用"。你没写过一行网页搜索代码——harness 默认附加了一个托管网页搜索工具。问一句 "Any recent news on NVDA?" 开箱就工作。同样，因为 harness 内置了 `TodoProvider` 和 `AgentModeProvider`，在 plan 模式下说 "Review my watchlist and recommend some stocks to add"，agent 会自动输出计划、写 todo 列表、然后切到 execute 模式执行。

## 第三步：在 Harness Console 中运行

最后一步，把 agent 交给交互式控制台。这是一个流式终端 UI，内置 `/todos`、`/mode`、`/exit` 命令，输出按模式着色（青色是 planning，绿色是 execution）。

**.NET：**

```csharp
await HarnessConsole.RunAgentAsync(
    agent,
    userPrompt: "Ask about a stock or say 'review my watchlist' to get started.",
    new HarnessConsoleOptions { /* observers + command handlers */ });
```

**Python：**

```python
await run_agent_async(
    agent,
    session=agent.create_session(),
    observers=build_observers_with_planning(agent),
    initial_mode="plan",
    title="💹 Finance Assistant",
)
```

运行命令：

```bash
# .NET
cd dotnet
dotnet run --project samples/02-agents/Harness/BuildYourOwnClaw/Claw_Step01_MeetYourClaw

# Python
uv run python/samples/02-agents/harness/build_your_own_claw/claw_step01_meet_your_claw.py
```

推荐按这个顺序试试：

1. `/mode execute`——切出默认的 plan 模式，快速查询不需要计划。
2. `What's the price of MSFT?`——看 agent 调用你的 `get_stock_price` 工具。
3. `Any recent news on NVDA?`——看它自动调用网页搜索。
4. `Add MSFT, NVDA and SPY to my watch list`——看它写文件记忆。
5. `/mode plan`——切回 plan 模式做复杂的多步任务。
6. `Review my watchlist and recommend some stocks to add`——看它先规划、再提问澄清、最后切到 execute 模式执行。输入 `/todos` 查看 todo 列表，`/mode` 查看当前模式。

### 保存与恢复会话

控制台还支持把整个会话持久化到磁盘。底层原理是序列化 `AgentSession` 对象（包含对话历史和上下文提供者状态）为 JSON：

- `/session-export my-session.json`——保存当前会话（包括 watchlist 记忆）到文件。
- `/exit`，重新启动——回到新的空会话。
- `/session-import my-session.json`——从磁盘恢复保存的会话。
- `/mode execute`，然后问 `What's on my watchlist?`——agent 从恢复的记忆中作答，无需重新输入。

## Plan 模式的原理

为什么 plan 模式下 agent 会问问题、请求批准，而 execute 模式下直接干活？答案在**结构化输出**上。

Harness 内置两种模式——`plan`（默认）和 `execute`。控制台的 planning observer 在两种模式下行为不同。execute 模式下模型输出普通文本直接干活。plan 模式下，控制台通过设置 JSON schema 要求模型输出结构化响应，而不是自由文本：

```csharp
// 控制台的 planning observer 中，仅在 plan 模式下：
options.ResponseFormat = ChatResponseFormat.ForJsonSchema<PlanningResponse>();
```

这个 schema 把模型输出限制为两种形态之一：

- **Clarification**（澄清）：模型不确定你想要什么，返回一个或多个问题。每个问题可以带 `Choices`（可选项），控制台把它们渲染成可选择项（也可以自由输入）。
- **Approval**（批准）：模型有了计划，返回一条 `Message` 作为计划摘要。控制台把它渲染成"批准并切换到 execute 模式"的提示，你不点头就不执行。

这就是计划模式有"想法"的原因：agent 先收集信息、展示计划、你批准后才进入 execute 模式按 todo 列表执行。`PlanningResponse` 类型在两种语言的控制台示例中都有完整源码，你可以复制并根据自己的 UX 修改 schema——不同的问题类型、更丰富的批准流程。

## 按需关闭功能

Harness 默认开启的所有功能——todos、agent modes、网页搜索、文件记忆、文件访问、工具审批——都可以单独关闭。如果某个功能不适合你的场景，一个选项就能关。

**.NET：**

```csharp
AIAgent agent = chatClient.AsHarnessAgent(new HarnessAgentOptions
{
    DisableTodoProvider = true,
    DisableWebSearch = true,
    ChatOptions = new ChatOptions { Instructions = instructions, Tools = [/* ... */] },
});
```

**Python：**

```python
agent = create_harness_agent(
    client=client,
    agent_instructions=FINANCE_INSTRUCTIONS,
    tools=get_stock_price,
    disable_todo=True,
    disable_web_search=True,
)
```

常见的 .NET 开关：`DisableTodoProvider`、`DisableAgentModeProvider`、`DisableWebSearch`、`DisableFileMemory`、`DisableFileAccess`、`DisableToolApproval`。Python 对应 `disable_todo`、`disable_mode`、`disable_memory`、`disable_web_search`。

## 拆开来用：这些构建块不依赖 Harness

Harness 帮你把这些都连起来了，但每个功能都是独立的。网页搜索只是一个 **tool**，模式和 todos 各自是普通的 **context provider**——你可以只拿你想要的部分，加到任何 agent 上，不需要套上完整的 harness。

| 功能      | .NET                                              | Python                                          |
| --------- | ------------------------------------------------- | ----------------------------------------------- |
| 网页搜索  | `HostedWebSearchTool` — `Microsoft.Extensions.AI` | `chat_client.get_web_search_tool()`             |
| 计划模式  | `AgentModeProvider` — `Microsoft.Agents.AI`       | `from agent_framework import AgentModeProvider` |
| Todo 列表 | `TodoProvider` — `Microsoft.Agents.AI`            | `from agent_framework import TodoProvider`      |

在 .NET 中，模式和 todo provider 在 `Microsoft.Agents.AI` 包里，托管网页搜索工具来自 `Microsoft.Extensions.AI`。Python 中三个都在 `agent-framework` 包里。Provider 通过 agent 的 context providers 接入，网页搜索通过 tools 接入——和 harness 帮你做的一样。

## 总结

这篇覆盖了 harness 的第一个里程碑：一个能查股价、搜网页、在 plan 模式下做多步分析的 agent，全在三步代码内完成。

Harness 的价值不在于提供了什么新能力——函数调用、计划、网页搜索在 agent 开发中都不是新鲜事。它的价值在于**默认集成**：这些能力开箱就有、互相协作、而且每一项都可以拆出来单独用。

系列后续会进入更深入的话题：Part 2 给 agent 加上文件访问和审批门控，Part 3 扩展能力，Part 4 进入生产就绪。可运行的示例代码在 [.NET samples](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/Harness/BuildYourOwnClaw/Claw_Step01_MeetYourClaw) 和 [Python samples](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness/build_your_own_claw)。

如果你关注 AI 助手、开发工具和 Agent Framework 实践，可以关注 Aide Hub。这里会继续分享能落地的 agent 开发教程和技术观察。

## 参考

- [Meet your agent harness and claw](https://devblogs.microsoft.com/agent-framework/meet-your-agent-harness-and-claw/)
- [Overview: Build your own claw and agent harness with Microsoft Agent Framework](https://devblogs.microsoft.com/agent-framework/build-your-own-claw-and-agent-harness-with-microsoft-agent-framework/)
- [.NET AgentProviders Samples](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/AgentProviders)
- [Python Providers Samples](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/providers)
- [Agent Framework Documentation - Providers](https://learn.microsoft.com/agent-framework/agents/providers)
- [.NET Harness Console Sample](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/Harness/Harness_Shared_Console)
- [Python Harness Console Sample](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness/console)
