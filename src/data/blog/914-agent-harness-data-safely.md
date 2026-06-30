---
pubDatetime: 2026-06-30T07:40:43+08:00
title: "Agent Harness：安全地使用你的数据——文件访问、审批与持久记忆"
description: "Microsoft Agent Framework 系列第二篇：给个人财务助手加上文件读写、工具审批（手动/自动/自定义规则）和跨会话持久记忆（文件记忆 + Foundry 事实记忆），让 AI Agent 安全地触碰真实数据。"
tags: ["AI", "Agent Framework", ".NET", "Python"]
slug: "agent-harness-data-safely"
ogImage: "../../assets/914/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/agent-harness-working-with-your-data-safely"
---

这是 [Build your own claw and agent harness with Microsoft Agent Framework](https://devblogs.microsoft.com/agent-framework/build-your-own-claw-and-agent-harness-with-microsoft-agent-framework) 系列的第二篇。第一篇我们搭起了 harness，给个人财务助手加上了自定义工具、网页搜索和规划能力——它能**谈论**市场，但还不能触碰**你的**数据，也没有任何东西阻止它随意执行敏感操作。

这篇用 harness 内置的三项能力修复这两个问题：文件访问、审批和持久记忆。

## 文件访问：读你的真实数据

助手应该基于用户的**真实**持仓而不是编造的数字工作。harness 内置了文件访问 provider，通过 `file_access_*` 工具集暴露对指定文件夹的读、写、搜索能力：

```csharp
// .NET
AIAgent agent = chatClient.AsHarnessAgent(new HarnessAgentOptions
{
    FileAccessStore = new FileSystemAgentFileStore(
        Path.Combine(AppContext.BaseDirectory, "working")),
    ChatOptions = new ChatOptions { Instructions = instructions, Tools = [...] },
});
```

```python
# Python
from agent_framework import FileSystemAgentFileStore

agent = create_harness_agent(
    client=client,
    agent_instructions=FINANCE_INSTRUCTIONS,
    tools=[get_stock_price, place_trade],
    file_access_store=FileSystemAgentFileStore("working"),
)
```

agent 现在拥有六个文件工具——`file_access_read_file`、`file_access_save_file`、`file_access_list_files`、`file_access_list_subdirectories`、`file_access_search_files` 和 `file_access_delete_file`。指令中告诉它如何用这些工具：

> 用户的持仓在 portfolio.csv 里。回答持仓相关问题前先读它，未经要求永远不要修改它。被要求写报告时输出到 Markdown 文件（如 reports/portfolio-review.md）并告诉用户存在哪里。

现在"我的持仓里有什么？"会读真实行，"帮我写份持仓报告并保存"会生成你能打开的文件。

## 审批：守门高风险操作

读数据通常是安全的。**下单交易**永远不安全——那是带后果的动作，agent 没有人的同意绝不应该执行。

harness 有内置审批机制：标记工具需要审批，agent 会在工具运行前**暂停并询问**。

```csharp
// .NET：用 ApprovalRequiredAIFunction 包装
public static AIFunction CreatePlaceTradeTool() =>
    new ApprovalRequiredAIFunction(
        AIFunctionFactory.Create(PlaceTrade, "place_trade"));
```

```python
# Python：装饰器上设 approval_mode
@tool(approval_mode="always_require")
def place_trade(symbol: str, action: str, quantity: int) -> str:
    """Place a (simulated) buy or sell order."""
    ...
```

当模型决定调用 `place_trade` 时，harness 发出审批请求而不是直接运行函数，控制台呈现为 Approve / Deny 提示。批准则交易执行，拒绝则 agent 适应。

### 不用再问：Always-Approve

反复批准同一个工具是另一种摩擦。harness 内建了"常设审批"——"别再问我"的决定。一旦你信任某个调用，不会再被重复打扰。有两种模式：

- **总是批准这个工具（任何参数）**：此后任何 `place_trade` 调用自动批准
- **总是批准这个工具用这些参数**：只有参数完全匹配的那一次调用被自动批准

规则记录在**会话状态**中，持续到会话结束，不写入 agent 也不泄露到全新会话。`/session-export` 和 `/session-import` 跟记忆一样携带常设审批跨重启。

### 自动审批：保持安全路径无摩擦

默认每个 `file_access_*` 调用（甚至读操作）都要求审批。但总是被提示"读 portfolio.csv"很快就会乏味，还会冲淡真正有风险的调用（写文件或交易）需要你注意时的信号。

harness 让你提供**自动审批规则**：静默通过低风险调用的启发式规则。文件访问 provider 自带了一个现成的规则，自动批准**只读**工具（read、list、search），而仍然提示会**修改**存储的操作（save 和 delete）：

```csharp
// .NET
ToolApprovalAgentOptions = new ToolApprovalAgentOptions
{
    AutoApprovalRules = [FileAccessProvider.ReadOnlyToolsAutoApprovalRule],
},
```

### 自定义规则：自动批准小额交易

规则只是对挂起函数调用的一个回调，你可以编码任何策略。一个自然的规则：**低于 $1,000 的交易自动批准，其余的询问**：

```csharp
// .NET: Func<FunctionCallContent, ValueTask<bool>>
static async ValueTask<bool> AutoApproveSmallTrades(FunctionCallContent call)
{
    if (call.Name != "place_trade" || call.Arguments is null) return false;
    var symbol = call.Arguments["symbol"]?.ToString();
    var quantity = Convert.ToInt32(call.Arguments["quantity"]);
    var estimate = quantity * await GetPriceAsync(symbol!);
    return estimate < 1000m;
}
```

规则按顺序执行，第一个返回 `true` 的获胜，返回 `false` 只是让下一条规则（或手动提示）接手。

## 持久记忆：跨会话记忆

我们的助手应该跨会话记住用户的观察列表和他们告诉我们的关于自己的事。

harness 提供了**两种不同的记忆**：

| 维度 | 文件记忆 | Foundry 记忆 |
|------|---------|-------------|
| 粒度 | 粗——整个文件 | 细——独立事实 |
| 写入者 | agent 显式决定保存 | Foundry 自动提取 |
| 适用 | agent 策展的文档：观察列表、笔记、草稿 | 环境事实："偏好低风险 ETF""正在为买房储蓄" |
| 存储位置 | 你控制的文件夹 | Foundry 管理的记忆存储 |

通常两者都想要：文件记忆给 agent 有意维护的东西，Foundry 记忆给那些应该"自己粘住"的小事实。

### 文件记忆（粗粒度、显式）

文件记忆是 harness **内建**的，默认开启。agent 获得 `file_memory_*` 工具集，自己决定什么时候写文件。文件存在于工作文件夹下的 `agent-file-memory/<session-id>/` 子文件夹中，在同一台机器上跨运行自动持久。通过 `/session-export` 和 `/session-import` 可以在控制台应用重启后恢复记忆。

### Foundry 记忆（细粒度、自动）

Foundry 记忆工作方式完全不同：你不用告诉 agent，它也不决定"保存"什么。对话流动时，**Microsoft Foundry 自动提取持久事实**，在后续轮次中召回相关的——甚至在一个全新会话中。它需要记忆存储和嵌入模型，通过环境变量选择加入。

```csharp
// .NET
var foundryMemory = new FoundryMemoryProvider(
    projectClient, memoryStoreName,
    stateInitializer: _ => new(new FoundryMemoryProviderScope("claw-sample-user")));
await foundryMemory.EnsureMemoryStoreCreatedAsync(deploymentName, embeddingModel);

AIAgent agent = chatClient.AsHarnessAgent(new HarnessAgentOptions
{
    AIContextProviders = [foundryMemory],
    // ...
});
```

现在在一个会话里说"我是保守投资者，正在为两年后买房储蓄"，重启后问"你对我了解什么？"——它记得，因为 Foundry 悄悄存储了事实并召回了它。

## 动手跑

```
.NET:  dotnet run --project samples/02-agents/Harness/BuildYourOwnClaw/Claw_Step02_WorkingWithData
Python: uv run python/samples/02-agents/harness/build_your_own_claw/claw_step02_working_with_data.py
```

依次试试这些：
- **"我的持仓里有什么？"** —— agent 用 file_access 工具读 portfolio.csv
- **"帮我写一份 持仓简评并保存"** —— 起草报告并提示你**批准保存**
- **"我是保守投资者，正在为两年后买房储蓄"** —— Foundry 记忆记住的事实
- **"买 10 股 MSFT"** —— 调用 place_trade，**任何事发生之前你先被提示批准/拒绝**
- **"把 SPY 加到我的观察列表"** —— 保存到文件记忆的 watchlist.md

## 独立使用

harness 为你组装了所有这些，但没有任何东西锁在 harness 里面。每个功能都是普通的 context provider、middleware 或 agent decorator，你可以独立拿出来加到自己的 agent 里：

| 功能 | .NET | Python |
|------|------|--------|
| 文件访问 | `FileAccessProvider` — `Microsoft.Agents.AI` | `from agent_framework import FileAccessProvider` |
| 审批 | `ToolApprovalAgent` — `Microsoft.Agents.AI` | `from agent_framework import ToolApprovalMiddleware` |
| 文件记忆 | `FileMemoryProvider` — `Microsoft.Agents.AI` | `from agent_framework import FileMemoryProvider` |
| Foundry 记忆 | `FoundryMemoryProvider` — `Microsoft.Agents.AI.Foundry` | `from agent_framework.foundry import FoundryMemoryProvider` |

## 参考

- [Agent Harness: Working with your data, safely — Microsoft Agent Framework](https://devblogs.microsoft.com/agent-framework/agent-harness-working-with-your-data-safely/)
- [Meet your agent harness and claw (Part 1)](https://devblogs.microsoft.com/agent-framework/meet-your-agent-harness-and-claw/)
- [Build your own claw and agent harness](https://devblogs.microsoft.com/agent-framework/build-your-own-claw-and-agent-harness-with-microsoft-agent-framework/)
- [Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [What is memory? — Microsoft Foundry](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-memory)
