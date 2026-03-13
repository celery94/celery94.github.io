---
pubDatetime: 2026-03-13T00:15:15+00:00
title: "Agent Harness 到底在补哪块：Microsoft Agent Framework 正在把 agent 从会说话，推到真能干活"
description: "Microsoft 这篇关于 Agent Harness 的文章，真正有意思的不是又多了一个术语，而是它把 agent 落地时最容易被忽视的三层能力摊开了：shell / filesystem 执行、approval 控制、长会话 compaction。模型负责推理，harness 负责把推理安全地接到现实执行上。"
tags: ["Agent Framework", "AI Agents", "Microsoft", "Developer Tools"]
slug: "agent-framework-agent-harness"
ogImage: "../../assets/600/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/agent-harness-in-agent-framework"
---

![Agent Harness 概念图](../../assets/600/01-cover.png)

现在聊 agent，很容易被讨论带偏。大家一张口就是 planning、多 agent、memory、workflow orchestration，听上去都挺高级。但真把一个 agent 放到生产环境里，最难的部分往往不是“它会不会想”，而是**它怎么安全、可控、持续地干活**。

Microsoft 这篇关于 Agent Framework 的 `Agent Harness`，值钱的地方就在这儿。它不是在发明另一个花里胡哨的 agent 名词，而是在补那层长期被忽略、却决定 agent 能不能落地的执行胶水：模型推理怎么接到 shell、文件系统、审批流和长会话上下文管理上。

换句话说，model 负责想，harness 负责让它别乱动、还能一直动。这听起来像基础设施细节，实际上恰恰是 agent 系统和 demo 之间最关键的分水岭。

## Agent 真正缺的，常常不是脑子，而是手脚和护栏

一个只能输出文字的模型，很容易让人误以为 agent 只要“更会规划”就够了。可一旦你想让它检查工作区、执行命令、改文件、跑验证、保留多轮任务上下文，问题立刻就从 prompt 设计，变成了系统设计。

这就是 `Agent Harness` 这个概念存在的意义。Microsoft 对它的定位很直接：这是模型推理接入真实执行环境的那一层。它管的不是 abstract intelligence（抽象智能），而是三件非常具体的事：

- shell 和 filesystem 怎么接给 agent
- 哪些动作要经过 approval
- 长会话怎么在上下文预算内继续保持连续性

这三件事放在一起看，就会发现一个挺现实的结论：**真正能落地的 agent，不只是“能调用工具”，而是有一套明确的执行边界管理。**

AI 这两年已经把“生成答案”这部分做得越来越强，但“让答案转成受控行动”依然是工程问题。你不给这层设计，agent 不是太弱，就是太莽。

## Shell Harness 解决的，不是能不能执行命令，而是谁来为执行负责

文章第一部分讲 shell 和 filesystem harness，这一段特别关键。因为很多人一说 tool use，默认以为“给模型一个 terminal 就好了”。现实里这通常是事故预备役。

Microsoft 给了两类思路：**本地 shell** 和 **托管 shell**。

本地 shell 的价值在于，agent 直接在宿主机旁边干活，能接近你的真实工作区、真实文件、真实依赖环境。这对很多开发场景很诱人，比如查代码、跑测试、看目录结构、读日志、验证某个命令输出。

但本地执行一旦没护栏，风险也非常朴素：删文件、跑错命令、泄漏环境信息、把一个“帮我看看”变成“顺手全改了”。所以 Microsoft 特别强调 **approval flow**，包括 Python 和 .NET 版本里都演示了在 shell 执行前显式审批。

这其实点中了 agent 产品化里一个经常被忽略的问题：大家太爱谈“autonomy（自主性）”，却不太爱谈“accountability（可追责性）”。可真到生产环境，后者往往更重要。谁批准了命令？命令参数是什么？执行发生在什么上下文？为什么这一步允许，下一步不允许？这些问题都属于 harness，不属于模型本身。

> 一个能跑命令的 agent 不稀奇，稀奇的是它每次跑命令前后，你都知道发生了什么、为什么发生、边界在哪里。

所以这篇里本地 shell 最值得记住的不是代码片段，而是产品立场：**把执行权交给 agent，不等于把控制权也一起交出去。**

## Hosted Shell 的意义，是把执行环境从“我的机器”挪到“可管理环境”

文章接着讲 hosted shell，也就是让 agent 在 provider-managed environment 里执行命令，而不是直接动本地机器。这部分看起来像部署细节，实际上是 agent 迈向企业化的一个很明显信号。

因为一旦你不希望 agent 直接碰开发者本机，或者你想统一环境、统一权限、统一审计、统一资源隔离，托管执行就很自然会变成更合理的选择。

这背后反映的是 agent 系统从“个人工作台助手”向“平台级能力”演进的方向。前者追求方便，后者追求可治理。你会发现很多真正准备给团队、组织、甚至客户用的 agent，最终都得回答这些问题：

- 命令在哪跑
- 文件在哪读写
- 权限怎么隔离
- 输出怎么记录
- 环境怎么复现

Hosted shell 正是在回答这些问题。它不是为了让 agent 看起来更炫，而是为了让执行环境不再绑死在某一台开发机上。

AI 在这里改写的，也不是“是否需要执行环境”，而是执行环境需要更像 compute substrate（计算底座），而不是聊天窗口旁边临时借来的 terminal。这个变化非常像早年 CI/CD 从“我本地能跑”走向“流水线可复现”的那一步。

## Approval 不是保守，它是在把 agent 的主动性变成可用能力

这篇虽然没有把 approval 单独写成一章，但其实它贯穿全文。无论是本地 shell 还是托管 shell，真正决定 agent 是否能上线的，不是它能不能调用工具，而是调用时有没有适当的审批模式和边界控制。

这个点值得单拎出来说，因为现在很多 agent 讨论有一种危险倾向：把“少审批”误解成“更智能”，把“强控制”误解成“用户体验差”。这在 demo 里可能成立，在真实系统里通常很幼稚。

审批的价值，不只是拦风险，也是在建立一种协作关系：

- agent 可以提出动作
- 系统可以展示动作细节
- 人可以批准、拒绝、修改
- 会话可以带着审批结果继续往下走

这样一来，agent 就不是一个偷偷摸摸的黑盒自动化，而是一个能被监督、能被插手、能被中途刹车的执行体。

对开发者工具尤其如此。因为很多命令的危险性，不是由命令名决定的，而是由上下文决定的。`cat` 可能很安全，`git clean -fdx` 可能很刺激，`python manage.py migrate` 在测试环境和生产环境也完全不是一回事。approval 的作用，就是把这种上下文判断重新放回系统和人手里，而不是让模型独自揣测。

这也是 AI 时代一个越来越清楚的现实：**真正好用的 agent，不是完全不需要人，而是知道什么时候该自己动，什么时候该把决定权还给人。**

## Context Compaction 才是长会话 agent 不发疯的关键基础设施

文章第三部分讲 context compaction，这部分我反而觉得最容易被低估。

很多人现在用 agent，已经不满足于单轮问答，而是想让它在长会话里持续推进任务：记住前面的决策、保留工具调用结果、基于旧上下文继续做下一步。但上下文窗口再大，也不是无限的。会话越长、工具结果越多、历史越复杂，迟早会碰到 token 预算和注意力稀释的问题。

Microsoft 在 Agent Framework 里把 compaction 做成内建能力，本质上是在承认一个现实：**长会话不是把历史无限堆着，而是要有策略地压缩、保留、丢弃。**

文里给了两种典型方向：

- Python 里的 sliding window，保留最近几组关键上下文
- .NET 里的 compaction pipeline，把 tool result compaction、sliding window、truncation 这些策略串起来

这件事的意义非常大。因为 agent 长会话最常见的问题，不是“忘得太快”，而是“记了一堆不该继续完整重放的东西”。尤其工具调用结果一多，模型很容易被海量旧输出拖住，成本涨、响应慢、重点还会开始发散。

如果说 planning 是让 agent 起跑别偏，那 compaction 就是在保证它跑远了也别背着一麻袋无关历史硬撑。

## Compaction 背后真正的问题，是上下文该被当成日志，还是工作记忆

我觉得这篇在 compaction 上虽然写得克制，但它隐含了一个更大的设计判断：会话历史不应该被简单看成原样回放日志，而应该更像 working memory（工作记忆）。

这两种思路差很多。

如果把历史当日志，你会倾向于“尽量都留着”。这样做对审计有帮助，但对模型工作未必有帮助。

如果把历史当工作记忆，你就会更关心：

- 哪些是当前任务还需要的事实
- 哪些只是旧工具输出，不值得反复塞回上下文
- 哪些结论应该保留，哪些中间推导可以压缩
- 哪些会话状态该转为 summary，而不是原始 transcript

今天越来越多 agent 系统开始意识到，长会话质量不只是靠大窗口模型硬扛，还得靠 memory policy（记忆策略）。这篇文章把 compaction 放到 harness 视角里，其实挺准确：这不是 prompt trick，这是 runtime 设计。

AI 改变的是，我们越来越敢让模型处理长链路任务；没变的是，任何长链路系统都需要垃圾回收机制。对 agent 来说，compaction 某种意义上就是上下文层的 GC。

## 这篇文章真正传递的，不是三个 feature，而是一种 agent 基础设施观

如果把全文压成一句话，我会这么概括：**Agent Harness 是把“模型会调用工具”升级成“系统知道怎么把工具调用变成安全、持续、可管理的执行”。**

Microsoft 这里选的三个例子也很有代表性：shell、approval、compaction。看似分散，其实都在回答同一个问题：当 agent 不再只是聊天，而要长期参与实际工作流时，运行时层到底要承担什么责任。

这也是为什么我觉得这篇比很多“agent architecture overview”类文章更实在。它没有把重点放在愿景和 buzzword 上，而是在补那些你真做系统时绕不过去的基础问题：

- agent 怎么接环境
- 动作怎么被控制
- 会话怎么持续

这些问题不 glamorous，但决定了 agent 能不能从 demo 变成 production。

## 今天做 agent，最该补的可能不是更多编排，而是更成熟的 harness 设计

现在很多团队一聊 agent，就忍不住先冲 orchestration、多 agent 协作、自动分工、复杂规划树。这些东西当然有用，但如果 harness 层没站稳，上层编排越复杂，事故半径往往越大。

你让一个 agent 能调十个工具，不代表它就可靠；你让它开三个子 agent，也不代表它就真的能交活。先把执行环境、审批机制、上下文压缩这些基础件做扎实，反而更接近真实生产力。

这也是 AI 改变工作方式的一条典型路径：先不是“更像人”，而是先更像一个可治理的系统组件。Agent Harness 这篇文章透露出来的，正是这种成熟方向。它不只是让 agent 更能做事，而是让系统更有机会对 agent 做的事负责。

对开发工具、企业内部助手、自动化工作流、代码 agent 来说，这一步都很关键。因为用户最终要的从来不是“这个模型看起来像会干活”，而是“它真的能在我的环境里干活，而且别给我捅娄子”。

## 参考

- [Agent harness in Agent Framework](https://devblogs.microsoft.com/agent-framework/agent-harness-in-agent-framework) — Microsoft DevBlogs
- [Agent Framework Documentation](https://learn.microsoft.com/agent-framework/) — Microsoft Learn
- [Agent Framework GitHub examples](https://github.com/microsoft/agent-framework) — Microsoft
