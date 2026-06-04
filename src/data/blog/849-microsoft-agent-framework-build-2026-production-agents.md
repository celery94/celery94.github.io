---
pubDatetime: 2026-06-04T10:39:45+08:00
title: "Microsoft Agent Framework at Build 2026：从本地 Agent 到生产运行"
description: "Microsoft Agent Framework 在 Build 2026 公布了 Agent Harness、Foundry Hosted Agents、CodeAct 和 Handoff 等更新。这篇文章帮你看清这些能力分别解决什么问题，以及开发团队该怎样判断它们的实际价值。"
tags:
  [
    "Microsoft Agent Framework",
    "AI Agent",
    "Microsoft Foundry",
    ".NET",
    "Python",
  ]
slug: "microsoft-agent-framework-build-2026-production-agents"
ogImage: "../../assets/849/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-at-build-2026-announce/"
---

Microsoft Agent Framework 在 Build 2026 的这轮更新，重点很明确：让 Agent 从能在本地跑，走向更接近生产服务的运行方式。它讨论的内容并不只是一组 SDK API，还包括文件和命令访问、人工审批、会话状态、托管部署、观测、工具调用效率，以及多 Agent 之间的转交。

如果你已经在做 Agent 应用，这篇更新的价值在于帮你拆清楚几个问题：本地执行谁来管，部署之后状态怎么保留，多工具调用为什么会慢，多 Agent 协作怎样避免只停留在路由器层面。

## 背景脉络

原文提到，Microsoft Agent Framework，简称 MAF，已经在 2026 年 4 月 2 日达到 1.0 GA。这个版本把 AutoGen 和 Semantic Kernel 收敛到一个受支持的平台里，并在 .NET 和 Python 上提供一致的概念和 API。

这次 Build 2026 公布的内容，就是建立在 1.0 之上的补充。它覆盖四类场景：

- 本地 Agent 如何获得可控的执行环境。
- 本地 Agent 如何迁移到托管生产环境。
- 工具调用很多时，如何减少模型轮次和 token 消耗。
- 多 Agent 系统如何把控制权转给合适的下一个 Agent。

换句话说，这次更新更接近工程问题：Agent 已经能写出来之后，怎么让它稳定、可审计、可部署。

## Agent Harness

Agent Harness 可以理解成 Agent 的运行外壳。通俗地说，它负责把模型推理和真实操作连接起来，比如读写文件、运行命令、请求人工确认、管理长会话上下文。

原文把 Agent Harness 放在新增能力的第一位，因为很多 Agent 项目真正难的地方就在这里。模型可以决定下一步，但文件访问、shell 执行、审批规则、上下文压缩、任务列表、技能发现，这些都需要一个一致的运行层来承接。

这次 MAF 把这些能力作为内置构件提供，包括：

- 自动上下文压缩，用于长工具链调用，避免上下文窗口溢出。
- 默认指令和指令合并，让 Harness 指令和自定义 Agent 指令组合使用。
- `FileMemoryProvider`，按会话保存文件形式的记忆，默认路径类似 `agent-file-memory/{session}/`。
- `FileAccessProvider`，让 Agent 可以访问和修改需要处理的文件。
- `TodoProvider`，用于记录多步任务的待办、完成和删除。
- `AgentModeProvider`，支持 plan 和 execute 两种运行模式。
- `AgentSkillsProvider`，从文件系统发现和运行技能。
- `BackgroundAgentsProvider`，把子任务交给并行运行的子 Agent。
- 托管 web search 工具。
- .NET 中的沙箱 shell 执行。

这里最值得关注的是边界。Agent Harness 让开发者把“模型能做什么”和“程序允许它做什么”拆开处理。比如 shell 执行可以被沙箱包住，敏感工具可以走审批，存储后端也可以替换成文件系统、blob storage 或其他实现。

## Hosted Agents

Agent 在本地跑通之后，下一步通常会遇到部署问题。原文把 Foundry Hosted Agents 描述成一个从本地走向生产的入口：开发者把自己的 Agent 代码打包成容器，部署到 Foundry 管理的基础设施上。

它提供的重点能力包括：

- 空闲时 scale to zero，下次请求进来再拉起。
- 文件、磁盘状态和会话身份可以跨空闲期保留。
- 每个会话有独立的 VM 隔离沙箱。
- MAF 的 OpenTelemetry traces 可以进入 Application Insights。
- 平台处理部署、监控、评估和版本管理相关事项。

Microsoft Learn 的 Foundry Hosted Agents 文档还补充了几个前提：需要 Azure subscription、Azure Developer CLI 和 AI agent extension；本地测试时还需要 Foundry project、模型部署、Azure CLI 登录，以及 .NET 10 SDK 或 Python 3.10 以上环境。

这说明 Hosted Agents 更适合已经准备进入生产试运行的团队。它减少的是基础设施工作量，但并不会替你解决 Agent 逻辑、权限设计、工具安全和评估数据这些问题。

## CodeAct

很多 Agent 慢，并不一定是模型能力不够。原文指出，一类常见瓶颈来自工具编排开销：Agent 连续调用很多小工具时，每个工具调用都可能变成一次模型轮次，延迟和 token 都会上升。

CodeAct 的做法是让模型写一段短 Python 程序，通过 `call_tool(...)` 调用你的工具，然后在沙箱里一次执行并返回汇总结果。这样可以把“选工具、等待、再选工具”的循环压缩成一次代码执行。

原文给了一个代表性工作负载数据，任务是跨很多用户计算订单总额，涉及几十次工具调用：

| 方式     | 时间   | Tokens |
| -------- | ------ | ------ |
| 传统方式 | 27.81s | 6,890  |
| CodeAct  | 13.23s | 2,489  |
| 改善     | 52.4%  | 63.9%  |

CodeAct 当前通过 `agent-framework-hyperlight` alpha 包提供。Hyperlight 的作用是给模型生成的代码提供微型 VM 沙箱。Microsoft Learn 文档把它描述为当前 Agent Framework 中 CodeAct 的已记录后端，可以暴露 `execute_code` 工具，并通过 `call_tool(...)` 调用 provider 拥有的 host tools。

这里的收益很直接：工具调用越多、每一步越轻，CodeAct 越可能减少等待和 token。相反，如果任务只需要一两个工具，或者每个工具本身很重，收益就会小很多。

## Copilot SDK

原文还提到 GitHub Copilot SDK integration 已经进入 1.0。MAF 现在支持把 GitHub Copilot SDK 作为后端，用标准 MAF 编程模型接入 Copilot 的编码相关能力，比如 shell execution、file operations、URL fetching 和 MCP server integration。

这一点对开发工具类 Agent 比较有意义。Copilot agent 仍然是标准 MAF agent，所以可以继续使用 tools、instructions、streaming、sessions、MCP servers 和 OpenTelemetry observability。

如果你的 Agent 面向代码工作，重点可以看它是否能把已有 MAF 结构和 Copilot 的开发能力接起来。这里需要继续关注权限、执行环境和组织内使用限制。

## Handoff

多 Agent 系统常见的第一版做法，是用一个 router 把请求转给某个 specialist。问题在于，真实对话经常会出现追问、缺上下文、任务中途换方向等情况。只靠一次路由，很容易卡住。

MAF 的 Handoff orchestration 用有向图表达转交关系。开发者声明参与 Agent 和它们之间允许的边，框架会注入 handoff tools，让 Agent 在需要时把控制权交给另一个 Agent。

原文示例里有三个 Agent：

- `Triage`：接收用户请求并转给合适的 specialist。
- `Billing`：处理账单问题。
- `Tech`：处理技术支持问题。

开发者仍然控制拓扑和护栏，Agent 负责在运行中做转交决定。这个边界很重要，因为它避免了把所有控制权都交给模型，也避免了把多 Agent 写成固定脚本。

## 怎么判断价值

这次 Build 2026 更新可以按三个层次理解。

第一层是本地运行。Agent Harness 解决的是“Agent 能不能安全地操作真实环境”。文件、命令、审批、上下文、技能和任务列表都属于这一层。

第二层是生产运行。Foundry Hosted Agents 解决的是“Agent 运行在哪里，状态和观测怎么管理”。它对已经有 Agent 原型、准备接入真实用户的团队更有价值。

第三层是执行效率和协作结构。CodeAct 关注多工具调用的成本，Handoff 关注多 Agent 转交的控制边界。它们适合在 Agent 工作流变复杂之后再引入。

对开发团队来说，比较稳妥的顺序是先把 Harness 边界设计清楚，再考虑托管部署；等真实任务里出现明显工具调用开销，再评估 CodeAct；等一个 Agent 无法自然覆盖多个领域，再考虑 Handoff。

## 适用边界

这篇原文属于发布汇总，很多能力已经给出代码片段和方向，但仍需要结合正式文档检查版本、可用区域、包名和预览状态。

比如 Foundry Hosted Agents 文档目前仍提示 preview；CodeAct 相关能力也提到 `agent-framework-hyperlight` alpha 包。团队如果要用于生产环境，应该把这些状态纳入技术选型，而不能只看发布文章里的能力清单。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能实际使用的工具教程、技术观察和项目经验。

## 参考

- [Microsoft Agent Framework at BUILD 2026: Agent Harness, Hosted Agents, CodeAct, and more](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-at-build-2026-announce/)
- [Agent Harness in Agent Framework](https://devblogs.microsoft.com/agent-framework/agent-harness-in-agent-framework)
- [Foundry Hosted Agents](https://learn.microsoft.com/en-us/agent-framework/hosting/foundry-hosted-agent)
- [Hyperlight CodeAct](https://learn.microsoft.com/en-us/agent-framework/integrations/hyperlight)
- [CodeAct in Agent Framework: Faster Agents with Fewer Model Turns](https://devblogs.microsoft.com/agent-framework/codeact-with-hyperlight)
