---
pubDatetime: 2026-03-13T08:27:29+00:00
title: "当终端里的 AI 不再只靠聊天，slash commands 才开始让 Copilot CLI 真像一个可控工具"
description: "GitHub 这篇 Copilot CLI slash commands cheat sheet 表面上是在列命令，真正值得带走的是另一层变化：它把终端里的 AI 交互从模糊自然语言，往更显式、更可预测、更可审计的工作流接口推进了一步。/clear、/cwd、/add-dir、/model、/delegate 这些命令真正解决的，不只是方便，而是让上下文、范围、权限和自动化都变得更可控。"
tags: ["GitHub Copilot", "CLI", "Developer Workflow", "AI Coding"]
slug: "copilot-cli-slash-commands"
ogImage: "../../assets/610/01-cover.png"
source: "https://github.blog/ai-and-ml/github-copilot/a-cheat-sheet-to-slash-commands-in-github-copilot-cli/"
---

![Copilot CLI Slash Commands 概念图](../../assets/610/01-cover.png)

很多人第一次用终端里的 AI 助手，最自然的姿势还是“把它当聊天框”。想到什么就打一段自然语言，想改代码也描述一下，想让它解释错误也问一句。这样当然能工作，但你用久了很快会发现一个问题：**聊天很灵活，但工作流不一定稳定。**

GitHub 这篇《A cheat sheet to slash commands in GitHub Copilot CLI》真正值得看的，不是那张速查表本身，而是它透露出来的一种产品方向：Copilot CLI 正在从“会聊天的终端助手”，往“有明确控制面的终端工具”走。

而 slash commands 就是这条路上最关键的一步。

## slash commands 真正改变的，不是输入形式，而是控制方式

表面看，slash commands 只是一些前面带 `/` 的命令：`/clear`、`/cwd`、`/model`、`/add-dir`、`/delegate`、`/share` 之类。它们听起来很像聊天系统里常见的快捷操作。

但如果只把它们理解成快捷键，反而低估了它们的价值。GitHub 自己在文里说得挺明白：相比自然语言 prompt，slash commands 的优势是 **speed、predictability、clarity、security、accessibility**。

这几个词翻成工程语言，其实可以浓缩成一句话：**slash commands 把一些本来模糊、隐式、靠猜的 AI 交互，变成了显式、稳定、可重复的终端控制面。**

自然语言的强项是开放表达；命令式接口的强项是确定性。Copilot CLI 现在做的，不是放弃自然语言，而是在那些最容易出错、最讲究边界和一致性的动作上，给你一层更可控的壳。

## /clear、/cwd、/add-dir 这一组，核心是在管“上下文和边界”

我觉得文章里最值得优先记住的，不一定是最花哨的命令，而是最底层那几个：`/clear`、`/cwd`、`/add-dir`、`/list-dirs`。

因为终端里的 AI 一旦开始深度参与开发，最容易出问题的往往不是“它会不会写”，而是：

- 它现在脑子里还带着多少旧上下文
- 它到底在看哪个目录
- 它被允许访问哪些文件
- 它有没有不小心跨到你不想让它碰的地方

`/clear` 解决的是上下文继承污染。你在一个任务里聊久了，Copilot 累积的上下文会越来越重，到了切任务的时候，这些历史很容易开始干扰后面的判断。这个命令本质上是在说：**AI 会记住很多东西，所以你需要一个显式的“清空工作记忆”动作。**

`/cwd` 解决的是工作范围焦点。终端里最可怕的一种错觉，就是你以为它在当前项目根目录，结果它其实还盯着另一个 repo，或者卡在错误的子目录。对复杂 monorepo 或多仓切换尤其明显。

`/add-dir` 和 `/list-dirs` 则更进一步，把文件访问边界做成了可见控制面。这个变化很关键，因为它把“AI 到底能看什么”从一种黑箱状态，变成了用户可以主动管理、主动核对的权限集合。

> 真正可用的终端 AI，不只是会回答问题，还得让你清楚知道它现在看了什么、在哪儿看、还能看哪里。

这就是为什么我觉得这一组命令比“更聪明的 prompt 技巧”更基础。因为它们解决的是 agent / assistant 系统最底层的可靠性前提：上下文正确，边界清楚。

## /model、/agent、/mcp 这组命令，说明 Copilot CLI 正在从单体助手变成可配置运行时

如果说上面那组命令是在管 scope，那么 `/model`、`/agent`、`/mcp` 这组，管的就是 runtime。

`/model` 的价值不只是“我可以切模型”，而是它承认一件现实：终端里的 AI 工作并不总是同一种任务。有些时候你想要更强 reasoning，有些时候你只想要快；有些时候你想拿 preview 模型试试；有些时候要排查“是不是模型行为变了”。

这意味着 Copilot CLI 不再只是一个固定黑箱，而是逐渐变成一个你可以调度不同模型能力的工作台。

`/agent` 的意义也类似。它说明 GitHub 不是只把 Copilot CLI 想成单一人格，而是在往“可切换 specialized agents”的方向走。不同 repo、不同 org、不同任务，可能挂不同 agent 配置，这其实是 agentic workflow 很自然的一步。

`/mcp` 就更直接了：它把 Model Context Protocol 相关配置搬进 CLI 里管理。`show / add / edit / delete / disable / enable` 这些动作，看起来只是配置维护，但背后意味着终端 AI 的外部能力来源已经开始模块化、服务化。模型不只是跟你对话，而是在一个可插拔的工具生态里运行。

这几条命令放在一起，信号很明确：**Copilot CLI 正在从“一个能回答问题的 AI”变成“一个可配置的 agent runtime 入口”。**

## /delegate 和 /share 这类命令的重点，是把 AI 输出从一次性对话变成团队工件

很多终端 AI 工具一个很大的问题，是它们的产出太像即时聊天：当下看着挺有用，但很难进入团队流程。你问完、它答完、终端一滚，很多上下文就蒸发了。

GitHub 这里用 `/delegate` 和 `/share` 给出的方向，我觉得很对。

`/delegate <prompt>` 不只是“让 AI 干活”，而是直接把活转成 PR 级别的可 review 工件。这一步非常重要，因为它让 AI 改动不再停留在对话层，而开始进入团队已有的代码流转机制里：branch、review、merge、审计、回滚，全都能接上。

`/share [file|gist]` 也是类似思路。把整个 session 导出成 markdown 或 gist，本质上是在给 AI 对话加上可归档、可异步交接、可附着到 issue/PR 的能力。它不是“顺手分享一下”，而是在解决一个更大的问题：**AI 辅助工作如果不能形成工件，就很难真正进入团队协作。**

这也是为什么我觉得这篇文章看似在讲命令，实际上在讲一件更深的事——终端里的 AI，正在被推着从临时助手，变成团队工作流里的正式参与者。

## cheat sheet 最容易被误读的地方，是把它当记忆题，而不是工作流设计题

文里最后给了一张很典型的 quick reference 表，看起来特别适合收藏转发。GitHub 甚至说，如果只记住三个命令，先记 `/clear`、`/cwd`、`/model`。

这当然没错，但我觉得真正不该带走的用法，是把这堆命令当成“背下来就会更高效”的命令表。

更好的理解方式是：这些命令分别在帮你显式地控制四类事情——

- **context**：`/clear`、`/session`、`/usage`
- **scope**：`/cwd`、`/add-dir`、`/list-dirs`
- **runtime/config**：`/model`、`/theme`、`/agent`、`/mcp`
- **handoff / collaboration**：`/delegate`、`/share`

一旦你这么看，这张 cheat sheet 就不是背诵材料，而更像是一张终端 AI 控制面地图。它告诉你：在一个成熟的 CLI AI 工作流里，哪些维度必须被显式管理。

这也解释了为什么我觉得 slash commands 特别适合终端场景。因为终端用户本来就习惯把复杂系统压缩成一组稳定命令。现在 AI 也开始走同样的路：不是所有事都靠聊天来完成，而是把一部分高频、高风险、需要确定性的动作，重新命令化。

## GitHub 这篇文章真正透露的，是“AI as CLI interface”开始成型了

我其实挺喜欢文末那句 vibe：stay focused and let Copilot handle the busywork。乍一看像营销文案，细想还挺准确。

终端一直是开发者最讲究“不要打断流”的地方。你不想频繁切 UI，不想在网页和 IDE、聊天窗口之间来回跳，不想为了一个简单动作再写一长段 prompt。slash commands 的意义，恰恰就是把 AI 接进终端已有的节奏里，而不是逼你进入另一种交互范式。

这件事跟“AI as text”逐渐走向“AI as execution”是同一条线。Copilot CLI 里的 slash commands，本质上是在把 AI 操作系统的一部分暴露成命令接口。你不是单纯跟模型说话，而是在通过命令调度一个具备上下文、权限、模型、工具、协作能力的工作流系统。

![GitHub Copilot 原文配图](../../assets/610/02-copilot-logo.png)

## 如果把这篇文章压成一句话

我会这么总结：**slash commands 真正让 Copilot CLI 更像一个开发工具，而不只是一个终端聊天对象。**

它们把上下文、目录范围、文件权限、模型选择、MCP 配置、PR 委托和会话分享，都变成了显式动作。这样一来，你对 AI 的使用就不再只是“问得好不好”，而开始变成“控得稳不稳”。

这也是终端 AI 接下来最值得关注的方向。不是再多几个花哨指令，而是越来越多关键工作流会被转成明确、可预测、可审计的命令面。对开发者来说，这比单纯“更会聊天”重要得多，因为它更接近真正能日用、能协作、能上线的工具形态。

## 参考

- [A cheat sheet to slash commands in GitHub Copilot CLI](https://github.blog/ai-and-ml/github-copilot/a-cheat-sheet-to-slash-commands-in-github-copilot-cli/) — GitHub Blog
- [GitHub Copilot CLI documentation](https://docs.github.com/copilot/how-tos/use-copilot-agents/github-copilot-in-the-cli) — GitHub Docs
- [Power agentic workflows in your terminal with GitHub Copilot CLI](https://github.blog/ai-and-ml/github-copilot/power-agentic-workflows-in-your-terminal-with-github-copilot-cli/) — GitHub Blog
