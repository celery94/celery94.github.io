---
pubDatetime: 2026-08-18T07:48:00+08:00
title: "Codex 多代理编排：给 Sol 一个团队"
description: "GPT-5.6 Sol 有了团队才更有意思。整理 Codex Multi-Agent V2 的实战编排：Scout/Worker/智能 Worker 分工、推理档位匹配、上下文继承、并发预算与技能固化，附作者编排技能原文。"
tags: ["AI", "Agent", "Productivity", "Tools"]
slug: "codex-multi-agent-orchestration-practical-guide"
ogImage: "../../assets/1007/01-cover.jpg"
source: "https://x.com/pvncher/status/2080707291603407077"
---

OpenAI Codex DX 团队的 eric provencher 在 2026 年 7 月发了一篇 X 长文，标题是「Practical multi-agent orchestration in Codex」，目前已有 51.7 万次观看、4300+ 收藏。核心论点一句话：GPT-5.6 Sol 在有一个团队可以协作时尤其有意思——Codex 新的 Multi-Agent V2 工具给了 Sol 和 Terra 一种自然的方式来委托任务、共享更新、在复杂任务中协调。

这不是产品公告，而是一份实战编排指南：怎么给代理分工、怎么匹配推理强度、怎么决定上下文继承、怎么把模式固化成 skill。作者本职就是 Codex 开发者体验团队的人，文中建议可操作性强。

适合：已经在用 Codex（或同类 agent 工具）、想让多代理协作从「偶尔灵光」变成「可复现」的开发者。读完你会得到：一套默认分工方案、三个可调旋钮（推理档位、上下文继承、并发预算），以及可以直接抄的编排 skill。

## 什么时候需要多代理

作者的建议很克制：Ultra 让代理协调成为默认，但**留给高 stakes 的工作**——那些歧义大或上下文分散、值得用额外深度去换的任务。

其他任务不需要上 Ultra：一段短 prompt 或一个 skill 就能让 Sol Medium 表现出同样的协作行为——它一边和你保持对话，一边在后台组织工作。给对推动，Sol 可以把宽泛请求拆成聚焦的分配，带进其他代理，并判断什么问题值得更深推理。默认路径是轻量协作，而不是一上来就开全队。

## 让推理匹配工作

可以让 Sol 把活委托给 Terra 之类的其他模型，但最简单的设置是**保持同一个模型家族，只调推理强度**，配上明确角色：

- **Scout（侦察兵）——GPT-5.6 Sol Light**：回答窄的、只读的问题：定位文件、追踪一条代码路径、找到相关测试。
- **Worker（工人）——GPT-5.6 Sol Medium**：实现有明确范围的改动、跑检查、做支撑性工作。
- **Smart worker（智能工人）——GPT-5.6 Sol High**：接手困难的实现、消解歧义、在有用时协调其他代理帮忙。

作者提醒把这些角色当成有用的默认值，不是教条。Sol Light 保留了找到有用上下文的判断力，只是不在发现阶段花那么多推理。

## 让团队自己协调

协调者（coordinator）是主要委托方：分配实质工作、避免重复调查、跟踪每个代理在做什么。Scouts 可以并行调查；职责清楚时，workers 之间可以直接共享实现。

代理之间还可以通过一个带独立收件箱的公共消息系统直接通信：scout 发现 worker 需要的东西时，它能识别这个依赖并直接把发现传过去，不必等协调者中转。

并发按线程可配置，**默认四个代理（含协调者）**。在这个预算内，一个智能 worker 可以协调一个 scout 加一个 worker，协调者也可以派三个 scout 分头调查不同问题。

## 选择代理继承什么上下文

分叉对话历史（forking）帮助代理理解更大的目标和早前的决策；而 `fork_turns: "none"` 给代理一个全新、聚焦的任务。作者指出，全新上下文的代理仍然能识别队友需要信息并独立联系它们——所以「干净开局」不等于「各干各的」。

继承父上下文的代理也可能看到父级的编排指令。当代理应该保持叶子节点时，给它一句短边界：

> Complete this assignment directly. Do not spawn other agents; your parent's delegation instructions apply only to your parent.

（直接完成这个任务。不要派生出其他代理；你父级的委托指令只适用于你的父级。）

全新上下文的代理不会继承任务专属的工具或安全边界，所以任何必要限制都要直接写进给它的任务里。

## 把模式固化成 skill

作者把整篇文章的指导汇总成了一个可直接使用的 skill（provencher/codex-skills 仓库的 orchestrate/SKILL.md），内容可以当作协调者的常驻指令：

> 保持对用户可用，同时委托实质工作。用 `reasoning_effort: "low"` 和 `fork_turns: "none"` 并行派出窄的、只读的 scout。常规实现用 `reasoning_effort: "medium"`，更困难的问题用 `"high"`。给每个代理明确的所有权，避免重叠分配，告诉叶子 worker 不要委托。汇总结果，审批权留在用户手里。

skill 的开头说明也值得抄：**在任务体量大时使用；琐碎任务不需要它**——这是「多代理不是默认」在工程上的落地。

## 调节旋钮

作者建议从这些默认值开始，然后实验四个维度：推理强度、上下文继承、委托权限、代理间协作方式。目标不是把每个旋钮调到最大，而是理解哪些设置能让团队推动工作前进，又不花超过任务所需的推理。

## 值得记住的反对意见

文章评论区有一条高质量的反对：MaMFlux 认为多代理不该是默认——一个强模型已经能在连贯上下文中分解紧密耦合的工作；额外代理带来交接成本、上下文丢失和令牌开销，只有当工作真正可并行时才有意义。

这条批评和作者的建议并不冲突，反而互相印证：作者自己也说 Ultra 留给高 stakes 工作、琐碎任务不需要 skill。多代理编排的正确姿势是「按需开火」，不是「默认全开」。

## 小结

这份指南的价值在于把多代理从玄学变成旋钮：角色分工（Scout/Worker/Smart worker）、推理档位（low/medium/high）、上下文继承（fork_turns）、并发预算（默认 4）、叶子边界（一句指令）。再往上，是一个可以直接放进仓库的 skill。

如果你在 Codex 里试多代理，建议路径：先抄 orchestrate skill 跑一个中等任务，把推理档位和并发数各调一次，记录 token 与结果质量的变化，再决定哪些任务值得动用 Ultra。评论区的反对意见提醒我们：代理协调是手段，任务完成才是目的。

Aide Hub 持续分享 AI 助手、开发工具与软件工程实践。如果你也在调 Codex 或同类工具的多代理参数，欢迎分享你的旋钮组合。

## 参考

- [Practical multi-agent orchestration in Codex（原文，eric provencher）](https://x.com/pvncher/status/2080707291603407077)
- [provencher/codex-skills（orchestrate skill 仓库）| GitHub](https://github.com/provencher/codex-skills)
- [orchestrate/SKILL.md 原文](https://raw.githubusercontent.com/provencher/codex-skills/main/orchestrate/SKILL.md)
- [OpenAI Codex 文档](https://developers.openai.com/codex/)
