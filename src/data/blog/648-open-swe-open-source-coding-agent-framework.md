---
pubDatetime: 2026-03-18T12:43:29+08:00
title: "Open SWE：面向工程团队的开源编码 Agent 框架"
description: "LangChain 发布 Open SWE，一个基于 Deep Agents 和 LangGraph 构建的开源编码 Agent 框架。它提炼了 Stripe、Ramp、Coinbase 等公司内部编码 Agent 的共同架构模式，包括隔离沙箱、精选工具集、子 Agent 编排和开发者工作流集成，可作为团队构建内部 AI 编码助手的起点。"
tags: ["AI Agent", "LangChain", "Open Source", "Coding Agent", "LangGraph"]
slug: "open-swe-open-source-coding-agent-framework"
ogImage: "../../assets/648/01-cover.png"
source: "https://x.com/LangChain/status/2033959303766512006"
---

![Open SWE 编码 Agent 框架](../../assets/648/01-cover.png)

过去一年，多家工程团队独立构建了各自的内部编码 Agent：Stripe 有 [Minions](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents)，Ramp 有 [Inspect](https://modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal)，Coinbase 有 Cloudbot。这三个系统都通过 Slack、Linear 和 GitHub 集成进开发者日常工作流，而不是要求工程师切换到新的工具界面。

它们是独立开发的，但最终收敛到了几乎相同的架构决策：隔离的云沙箱、精心挑选的工具集、子 Agent 编排、与开发工作流的深度集成。这种收敛本身就说明一些事情——在生产环境里部署编码 Agent，这些组件可能是必要的。

LangChain 在 2026 年 3 月发布了 [Open SWE](https://github.com/langchain-ai/open-swe)，一个把这些模式提炼成可复用形式的开源框架，基于 Deep Agents 和 LangGraph 构建，MIT 授权。

## 生产部署的共同模式

Stripe 的工程团队公开提到，他们的 Agent 有大约 500 个工具，但这些工具是精心筛选维护的，而不是随时间堆积下来的。这个细节值得注意：**工具的质量比数量更重要**。一个 Agent 拥有 50 个可靠、定义清晰的工具，比拥有 500 个描述模糊的工具要好用得多。

这三家公司还共同选择了以下架构：

- **隔离执行环境**：每个任务在专属的云沙箱中运行，有完整权限但在严格边界内，任何错误都被限制在沙箱内而不会影响生产系统。
- **Slack 作为主入口**：Agent 集成到工程师已经在用的沟通工具里，而不是引入新界面。
- **启动时注入完整上下文**：在任务开始前就拉取 Linear issue、Slack 线程或 GitHub PR 的完整信息，减少 Agent 在执行过程中通过工具调用反复查询上下文的开销。
- **子 Agent 编排**：复杂任务拆分给专门的子 Agent，每个子 Agent 有独立的上下文和聚焦的职责。

## Open SWE 的架构

Open SWE 把这七个组件都做成了可插拔的：

**1. Agent Harness：基于 Deep Agents 组合**

Open SWE 不是从零开始构建 Agent 逻辑，而是组合在 Deep Agents 框架上。这和 Ramp 团队在 OpenCode 上构建 Inspect 的做法类似。组合的好处在于：当底层框架（Deep Agents）在上下文管理、规划效率、token 优化等方面有改进时，Open SWE 可以直接获益，而不需要重新构建上层定制逻辑。

**2. 沙箱：隔离的云执行环境**

每个任务在独立的 Linux 云沙箱中运行，仓库被克隆进去，Agent 获得完整 Shell 权限。沙箱内的错误不会影响外部系统。Open SWE 开箱支持 Modal、Daytona、Runloop 和 LangSmith 作为沙箱提供商，也可以实现自己的后端。

每个对话线程复用同一个沙箱，跟进消息会路由到同一个运行中的 Agent；如果沙箱变得不可达，会自动重建。

**3. 工具集：精选，不堆积**

Open SWE 默认工具集（通过 shell 工具）：`write_file`、`str_replace`、`view_file`、`find_file`、`run_command`、`github` 工具组。加上 Deep Agents 内置的：`read_file`、`write_file`、`edit_file`、`ls`、`glob`、`grep`、`write_todos`、`task`（子 Agent 生成）。

这个工具集是刻意保持精简的。需要内部 API、定制部署系统或专属测试框架时，可以显式添加。

**4. 上下文工程：AGENTS.md + 任务上下文**

上下文来自两个层次：仓库根目录的 `AGENTS.md` 文件在沙箱中被读取并注入系统提示，可以编码代码规范、测试要求、架构决策和团队惯例；任务启动前，完整的 Linear issue（标题、描述、评论）或 Slack 线程历史被组装好传入 Agent，不需要额外的工具调用。

**5. 编排：子 Agent + 中间件**

两种机制配合使用。子 Agent 由主 Agent 通过 `task` 工具生成，每个子 Agent 有自己独立的上下文、待办列表和文件操作，不同子任务的会话历史互不污染。

中间件提供确定性的钩子：

- `check_message_queue_before_model`：在下一次模型调用前注入跟进消息（比如 Agent 运行中途到来的 Slack 消息），让用户可以实时提供补充输入
- `open_pr_if_needed`：如果 Agent 完成工作但没有主动开 PR，中间件自动提交并开 PR，作为安全兜底
- `ToolErrorMiddleware`：统一处理工具调用错误

这种把"模型驱动"和"中间件驱动"分开的设计，让关键步骤的可靠性有了保障，不完全依赖模型的判断。

**6. 调用入口：Slack、Linear、GitHub**

三个入口各有分工——Slack 里 @ bot 并可通过 `repo:owner/name` 指定仓库；Linear 里 `@openswe` 评论 issue，Agent 读取完整 issue 上下文后用 👀 确认并回复结果；GitHub 上 `@openswe` 标记 Agent 创建的 PR 来处理 review 反馈。每次调用生成确定性的线程 ID，跟进消息始终路由到同一个运行中的 Agent。

**7. 验证：提示驱动 + 安全兜底**

Agent 被指示在提交前运行 lint、格式化工具和测试。`open_pr_if_needed` 中间件是最后一道安全网。可以通过添加额外的中间件来扩展验证层：CI 检查、视觉验证或审批门控。

## Deep Agents 做了什么

Open SWE 依赖 Deep Agents 处理几个在长任务中容易出问题的地方：

文件上下文很快就会很大——命令输出、搜索结果、文件内容——Deep Agents 通过基于文件的内存管理把大结果卸载出去，而不是全部堆在对话历史里。`write_todos` 工具提供结构化的任务分解方式，方便在多步骤任务中追踪进度和调整计划。子 Agent 隔离让不同子任务的上下文互不干扰。中间件钩子让在 Agent 循环特定位置注入确定性逻辑成为可能。

## 多少定制空间

框架的每个主要组件都是可替换的：沙箱提供商可以换，模型默认是 Claude Opus 4 但可以按子任务配置不同模型，工具可以增减，触发器可以修改或新增（邮件、webhook、自定义 UI），系统提示和 AGENTS.md 逻辑可以定制，中间件可以加验证、审批门控和日志钩子。

LangChain 把 Open SWE 定位为"可定制的起点，而不是成品"。这个措辞是准确的——它提炼了生产部署的共同模式，但组织特定的工具、内部集成和流程仍然需要自己来做。

## 参考

- [Open SWE announcement (LangChain)](https://x.com/LangChain/status/2033959303766512006) — LangChain
- [Open SWE GitHub](https://github.com/langchain-ai/open-swe) — langchain-ai
- [Deep Agents 文档](https://docs.langchain.com/oss/python/deepagents/overview) — LangChain
- [Stripe Minions](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents) — Stripe Engineering
- [Ramp Inspect](https://modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal) — Modal
- [Coinbase Cloudbot](https://www.coinbase.com/blog/building-enterprise-AI-agents-at-Coinbase) — Coinbase
- [LangSmith Sandboxes](https://blog.langchain.com/introducing-langsmith-sandboxes-secure-code-execution-for-agents/) — LangChain
