---
pubDatetime: 2026-03-16T04:49:52+00:00
title: "这个 Claude Code 最佳实践仓库，适合拿来整理自己的工作流"
description: "shanraisshan 做的 claude-code-best-practice 仓库，最有用的地方不是又总结了几十条零散技巧，而是把 Claude Code 里最容易混在一起的几层东西——commands、subagents、skills、MCP、memory、settings、workflows——放进同一张地图里。对刚开始搭自己的 agent 工作流的人来说，它更像一份可直接照着抄的目录，而不是一篇看完就忘的经验帖。"
tags: ["AI", "Claude", "Developer Workflows", "Agent Engineering"]
slug: "claude-code-best-practice-workflows"
ogImage: "../../assets/630/01-cover.png"
source: "https://github.com/shanraisshan/claude-code-best-practice"
---

![Claude Code 工作流地图概念图](../../assets/630/01-cover.png)

如果你最近在折腾 Claude Code，很容易掉进一种状态：看了很多零散技巧，也知道 slash commands、subagents、skills、MCP、hooks 这些词，但真要自己搭一套顺手的工作流，脑子里还是糊的。

`claude-code-best-practice` 这个仓库的价值，就在它没有只做“技巧收集站”，而是把 Claude Code 里几层经常被混用的能力，整理成一张能落地的结构图。你看完之后，至少会更清楚一件事：**自己现在缺的到底是一条 command、一只 subagent，还是一份 skill。**

这也是它跟很多“AI 编程神技合集”不太一样的地方。它不是在卖某个神奇 prompt，而是在帮你把工作流拆清楚。

## 它最值钱的是结构，不是清单

这个仓库首页第一眼看上去像大全，列了 commands、subagents、skills、hooks、MCP servers、settings、memory、checkpointing、CLI startup flags，还有一串近期热门能力，比如 `/btw`、scheduled tasks、agent teams、remote control、git worktrees。

但它真正有用的，不是“列得多”，而是每一项都尽量回答了同一个问题：**这玩意到底放在哪一层，它解决什么问题。**

比如首页那张概览表里，有几个区分就很适合新手立刻建立判断：

- **Commands** 更像用户主动触发的提示模板，用来编排工作流
- **Subagents** 是带独立上下文的自治执行者，适合隔离任务
- **Skills** 是注入到上下文里的知识或操作套路，偏复用和渐进展开
- **Hooks** 是跑在 agent loop 外面的确定性脚本
- **MCP Servers** 则是给模型接外部工具、数据库和 API 的接口层

这些词平时大家都会说，但很多文章其实讲不清边界。这个仓库的价值，正是把边界摆出来。对于想把 Claude Code 从“会聊天的终端 AI”用成“能稳定协作的工作环境”的人，这一步比再背十条 prompt 技巧重要得多。

## 它把 command、agent、skill 的关系讲明白了

仓库里最值得单独看的，不是某条 best practice，而是 `orchestration-workflow` 那份文档。

它用一个天气数据示例，把一条命令、一个带预加载 skill 的 agent、以及一个独立调用的 skill，怎么串起来工作，拆得很直白。

这份示例里有三个很具体的锚点：

1. **command 是入口**，负责跟用户交互和组织流程
2. **agent 带着预加载 skill 工作**，拿干净上下文去做数据获取
3. **skill 也可以独立调用**，不一定非得作为 agent 的附属品存在

这比单纯说“要学会编排 agent”有用得多。因为很多人刚开始折腾这类系统时，最容易犯的错，就是把所有能力都糊成一个大提示词，然后希望它自己长出结构。

但这份示例其实在提醒你：**工作流不是靠 prompt 越写越长长出来的，而是靠职责拆分长出来的。**

如果你要把这个思路挪到真实项目里，也很好迁移：

- command 负责接需求、追问缺失信息、决定下一步
- subagent 负责带着局部上下文去跑搜索、读代码、查资料、做审查
- skill 负责沉淀那些可复用的领域套路，比如“怎么写发布文章”“怎么做 API 风险检查”“怎么生成结构化总结”

一旦你这样想，很多之前模糊的设计决定就会清楚不少。

## 它不是教你堆功能，而是教你少混概念

这个仓库还有一个我比较认同的地方：它虽然收了很多 feature，但整体气质并不是“Claude Code 什么都能做”，而是“不同能力各自该放在哪”。

比如它把 memory 单独拎出来，强调 `CLAUDE.md`、rules、项目级 memory 这些持久上下文能力；也把 settings、permissions、sandbox、model config 这些配置层能力单列；甚至 checkpointing、rewind、compact、clear 这种会话控制能力，也没有混进 agent 技巧里一起讲。

这看上去像整理目录，实际是在帮你避免一个很常见的问题：**什么都想靠 agent 自己理解，最后什么都缠在上下文里。**

做 agent 工作流，最怕的不是能力少，而是层次乱。你本来该放进配置的东西，写进 prompt；本来该做成 skill 的东西，塞进 command；本来该让独立 agent 处理的任务，又硬压在主上下文里。结果不是系统更聪明，而是越来越黏。

这仓库的作用，就是把这种黏糊状态拆开。

## 适合谁看，适合抄什么

这仓库最适合三类人。

### 刚开始搭个人工作流的人

如果你已经在用 Claude Code，但还停留在“开终端、贴需求、等输出”的阶段，这仓库很适合拿来当路线图。你不一定要整套照搬，但可以先按它的分类问自己：

- 我有没有高频重复任务，适合做成 command？
- 我有没有需要隔离上下文的任务，适合扔给 subagent？
- 我有没有某类固定写法、固定流程，适合沉淀成 skill？

只要把这三问想清楚，工作流就已经往前走了一大步。

### 已经在玩多 agent，但越搭越乱的人

很多人做多 agent 的第一反应，是先设很多角色：planner、coder、reviewer、tester、researcher。看上去很完整，实际经常只是把 handoff 复杂度做上去了。

这个仓库虽然不是专门批判多 agent，但它通过 command、agent、skill、memory、settings 的分层，间接给了一个很实用的提醒：**先拆职责，再拆角色。**

尤其是你看到它把 command 当 orchestrator、把 skill 当可复用知识、把 agent 当执行单元时，会更容易意识到，不是每个问题都值得拉出一个“新角色”。

### 想把经验变成团队资产的人

它还有一个很实际的价值：适合拿来当团队内部约定的模板。

因为很多团队踩的坑不是不会用 Claude Code，而是每个人都在用自己的土办法，最后谁都接不上谁。这个仓库这种“把能力分层、把目录摆出来、把实现和 best practice 对照放一起”的写法，很适合拿来改造成团队自己的操作手册。

## 也别把它当成唯一答案

当然，这仓库也不是“照抄就赢”的万能钥匙。

它更像一份持续更新的实践索引，优点是广，缺点也正是广。很多条目给你的是入口，不是已经替你做完取舍的最终方案。比如首页收进去的 hot features，从 scheduled tasks 到 agent teams，再到 remote control，看完会让人很想什么都试一遍。

但真正在项目里落地时，重点通常不是“把功能补齐”，而是**哪一层真的值得加复杂度**。

如果你现在还是单人使用、任务边界也不复杂，那最值得先抄的，往往不是 agent teams 这种更重的协作机制，而是：

- 把高频动作做成 command
- 把常见套路做成 skill
- 把需要隔离噪音的任务丢给 subagent
- 把 memory 和 settings 整理干净

先把这些基础层搭顺，收益通常比追最新 feature 更直接。

## 这仓库真正提供的是一张地图

我觉得 `claude-code-best-practice` 最值得看的，不是它告诉你“Claude Code 原来还能这样”，而是它把一堆原本容易混成一坨的能力，重新摆成了一张地图。

地图的价值，不是替你走路，而是让你少绕弯。

如果你正准备给自己搭一套 Claude Code 工作流，这仓库很适合先收藏、再按自己的使用频率往里挑。别一上来全学，先把 command、subagent、skill 这三层分清楚，再决定下一步补什么。这样搭出来的系统，通常会比“先堆满功能再慢慢理”顺手得多。

## 参考

- [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) — GitHub
- [Orchestration Workflow](https://github.com/shanraisshan/claude-code-best-practice/blob/main/orchestration-workflow/orchestration-workflow.md) — shanraisshan
- [Claude Code Documentation](https://code.claude.com/docs/en/features-overview) — Anthropic
