---
pubDatetime: 2026-07-23T08:17:51+08:00
title: "Microsoft Agent Framework Harness 正式发布：一行代码把 Chat Client 变成生产级 Agent"
description: "Agent Framework 的 Harness 正式发布，带来函数调用、规划、记忆、审批、上下文压缩、遥测等 9 项内置能力，同时支持 Python 和 .NET。一次调用就能从裸 Chat Client 跨越到完整 Agent 运行时，省掉大量胶水代码。"
tags: ["Agent Framework", "Agent Harness", ".NET", "Python", "AI Agent"]
slug: "microsoft-agent-framework-harness-released"
ogImage: "../../assets/965/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/the-microsoft-agent-framework-harness-is-now-released"
---

一个语言模型本身只能生成文本。要让它调用工具、执行多步任务、记住做过什么、一直干到任务完成——你得在模型外面包一层运行时。这层运行时，就是 Agent Harness。

2026 年 7 月 22 日，Microsoft Agent Framework 的 Harness 正式发布。它同时提供 **Python** 和 **.NET** 两个版本，把 Agent 开发中最繁琐的那部分胶水代码替你写好了。

## 什么是 Agent Harness？

如果你之前手写过 Agent 循环，下面这段代码你大概很熟悉：

1. 用户发一条消息
2. 发给模型，模型决定调用哪个工具
3. 你执行工具，把结果塞回上下文
4. 再发给模型，看它还要不要继续调工具
5. 重复 2-4，直到模型觉得任务完成了
6. 把最终结果返回给用户

看起来简单，做起来一堆坑：上下文会不会爆？聊天历史怎么持久化？工具调用要不要审批？怎么记录日志？崩溃了怎么恢复？

Harness 做的事情，就是把上面这个循环连同周边能力打包成一个经过生产验证的即用型方案。

用原文的话说：它是一个 **opinionated, fully customizable, batteries-included agent**——有主见（默认行为合理）、全可定制（每个模块都能拆换）、自带电池（开箱即用）。

## Harness 里包了什么？

Harness 内部其实就是一个 chat-client agent（Python 里叫 `Agent`，.NET 里叫 `ChatClientAgent`），外面套了一层精心编排的 Agent Framework 功能。下面这 9 项全部默认开启，每一项都可以单独关闭或替换：

| 能力                    | 说明                                                     |
| ----------------------- | -------------------------------------------------------- |
| **Function invocation** | 自动工具调用循环，支持配置最大迭代次数                   |
| **History persistence** | 每次模型调用后自动保存聊天历史，崩溃可恢复、运行中可检查 |
| **Compaction**          | 上下文窗口管理，长任务不会溢出                           |
| **Todo & agent-mode**   | 内置待办列表 + 计划/执行模式切换                         |
| **File memory**         | 跨轮次的持久笔记和产物存储                               |
| **Skills**              | 渐进式技能发现与加载                                     |
| **Web search**          | 当底层推理服务提供内置搜索时，Agent 可直接联网查资料     |
| **Tool approval**       | 「不再询问」的常驻规则 + 安全调用的启发式自动批准        |
| **Telemetry**           | 内置 OpenTelemetry 追踪                                  |

你只需要提供两样东西：一个 chat client 和你的指令（instructions）+ 工具（tools）。其余全部有默认值。

## 快速上手

### .NET

```csharp
using Azure.AI.Projects;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

var endpoint = Environment.GetEnvironmentVariable("FOUNDRY_PROJECT_ENDPOINT")
    ?? throw new InvalidOperationException("FOUNDRY_PROJECT_ENDPOINT is not set.");
var deploymentName = Environment.GetEnvironmentVariable("FOUNDRY_MODEL") ?? "gpt-5.4";

// 构建一个由 Microsoft Foundry 项目支持的 IChatClient
IChatClient chatClient =
    new AIProjectClient(new Uri(endpoint), new DefaultAzureCredential())
        .GetProjectOpenAIClient()
        .GetResponsesClient()
        .AsIChatClient(deploymentName);

// 一行调用，包裹 Harness
AIAgent agent = chatClient.AsHarnessAgent(new HarnessAgentOptions
{
    ChatOptions = new ChatOptions
    {
        Instructions = "You are a helpful research assistant. Plan your work, then execute it.",
        Tools = [/* 你的自定义 AIFunction 工具 */],
    },
});

AgentRunResponse response = await agent.RunAsync(
    "Research the outlook for renewable energy stocks.");
Console.WriteLine(response.Text);
```

### Python

```python
import asyncio

from agent_framework import create_harness_agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential


async def main() -> None:
    # FoundryChatClient 从环境变量读取 FOUNDRY_PROJECT_ENDPOINT 和 FOUNDRY_MODEL
    client = FoundryChatClient(credential=AzureCliCredential())

    # 一行调用构建完整 Agent：规划、记忆、压缩、审批、搜索、遥测全部内置
    agent = create_harness_agent(
        client=client,
        agent_instructions="You are a helpful research assistant. Plan your work, then execute it.",
        tools=[],  # 在这里添加你自己的 callable 工具
    )

    response = await agent.run(
        "Research the outlook for renewable energy stocks."
    )
    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
```

可以看到，不管是 Python 还是 .NET，核心调用的形状是一样的：你给一个 chat client、一段指令、一组工具，调一次 `run`，剩下的由 Harness 接管。

## 适合做什么？

原文给出了三类典型场景：

**研究助理**：把研究主题拆成 todo，在计划模式和行动模式之间切换，联网搜索，自主推进计划。

**数据处理 Agent**：读取文件夹里的一批文件做分析，文件操作带审批门控——敏感文件先问过你才打开。

**领域助手**：原文作者举了一个个人理财 "claw" 的例子——你可以把自定义工具、记忆、技能、规划组合进一个 Agent，一个功能一个功能地往上加，而不是一次搞定所有复杂度。

如果你对「自己从零搭建一个 claw」感兴趣，官方有一个四集的系列教程——从最小 Harness 开始，一步步加上数据文件读写、审批、Skills、后台 Agent、Shell 工具、CodeAct，最后到可观测性和生产部署。这个系列同时在 .NET 和 Python 下给出可运行示例。

## 还有哪些功能在预览？

下面这些功能代码已经在仓库里了，开了能用，但团队还想再打磨一下，目前 opt-in 时会有警告：

- **Background agents**：把子任务委托给其他 Agent 并发执行
- **File access**：限定工作目录的读写文件工具
- **Looping**：自动重复调用 Agent 直到满足完成条件
- **Shell tooling**：执行 Shell 命令（来自 alpha 阶段的 tools 包）

## 小结

Agent Harness 解决的是一个很实际的问题：把「模型能做什么」和「Agent 需要做什么」之间的差距填平。它不会让你写的 Agent 变聪明——聪明是模型的事——但它会让你写 Agent 的体验不再是「先搭一个月的脚手架」。

如果你已经在用 Agent Framework，Harness 是最自然的下一个要了解的东西。如果你还没用过 Agent Framework，Harness 是一个很好的起点——不需要理解所有内部概念，一行代码就能先跑起来，之后再按需定制。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 **Aide Hub**。这里会持续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [The Microsoft Agent Framework Harness is now released](https://devblogs.microsoft.com/agent-framework/the-microsoft-agent-framework-harness-is-now-released/)
- [Agent Harnesses on Microsoft Learn](https://learn.microsoft.com/agent-framework/agents/harness)
- [.NET Samples: dotnet/samples/02-agents/Harness](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/Harness)
- [Python Samples: python/samples/02-agents/harness](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/harness)
- [Build your own claw and agent harness with Microsoft Agent Framework](https://devblogs.microsoft.com/agent-framework/build-your-own-claw-and-agent-harness-with-microsoft-agent-framework/)
