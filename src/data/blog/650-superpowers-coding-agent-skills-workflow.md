---
pubDatetime: 2026-03-18T13:02:39+08:00
title: "Superpowers：给编码 Agent 装上工作流技能库"
description: "Superpowers 是一套给 Claude Code、Cursor、Codex 等 AI 编码工具用的可组合技能框架，通过自动触发的 skills 把 TDD、需求提炼、任务分解、并行子 agent 等流程变成 agent 的默认行为，而不是可选建议。"
tags: ["AI", "Coding Agent", "Claude Code", "Developer Tools", "TDD", "Workflow"]
slug: "superpowers-coding-agent-skills-workflow"
ogImage: "../../assets/650/01-cover.png"
source: "https://github.com/obra/superpowers"
---

![开发者被技能卡片环绕的工作流插图](../../assets/650/01-cover.png)

AI 编码工具越来越多，但有一个问题大多数工具没解决：agent 知道怎么写代码，但不知道什么时候该暂停、该问什么、该按什么顺序来。结果就是你说"帮我做这个功能"，agent 直接开写，写完你发现方向偏了，或者根本没测试，或者任务太大一次写不下来。

Superpowers 是 Jesse Vincent（来自 Prime Radiant）做的一套开源框架，解决的就是这个问题。93k+ stars，目前支持 Claude Code、Cursor、Codex、OpenCode、Gemini CLI。它不是 IDE 插件，也不是新的 AI 模型，而是一组 Markdown 写成的"技能文件（skills）"，加上让 agent 知道什么时候调用它们的初始指令。

## 工作方式

核心机制很简单：把工作流规则写成 SKILL.md 文件，告诉 agent 在什么情况下自动加载它。因为技能是文档，不是代码，所以平台无关——同一套技能文件可以给 Claude Code 用，也可以给 Cursor 或 Gemini CLI 用。

触发是自动的。你不用每次手动输入 `/brainstorm` 或者 `/tdd`，agent 在遇到匹配的场景时（比如开始写功能、调试 bug、准备提交）会自己去找相关技能应用。README 里说得很直接：它们是强制工作流，不是建议。

## 七步标准流程

Superpowers 的核心是一条有顺序的完整链路，每一步都对应一个技能：

1. **brainstorming** — 写代码之前先触发。通过追问把模糊需求变成具体设计，分段展示让你能逐块确认，最后保存设计文档。
2. **using-git-worktrees** — 设计确认后建 worktree，在新分支上跑项目初始化，确认测试基线干净。
3. **writing-plans** — 把设计拆成每个 2~5 分钟的小任务，每个任务包含精确的文件路径、完整代码和验证步骤。原文描述是"清晰到一个没有判断力、不懂项目上下文、还不爱写测试的初级工程师也能照着做"。
4. **subagent-driven-development / executing-plans** — 按计划执行：对每个任务派出独立的子 agent，两级审查（先看是否符合规格，再看代码质量），或批量执行加人工检查点。
5. **test-driven-development** — 实现阶段强制 RED-GREEN-REFACTOR：先写失败测试，确认它失败，再写刚好让它通过的代码，提交，然后重构。在测试通过前写的代码会被删掉。
6. **requesting-code-review** — 每个任务完成后触发。按严重程度报告问题，关键问题会阻断后续进度。
7. **finishing-a-development-branch** — 所有任务完成后，验证测试、展示操作选项（合并 / PR / 保留 / 放弃），清理 worktree。

这个链路的一个实际效果是：Claude 在这套框架下能持续自主工作好几个小时，而不偏离你最开始确认的计划。

## 技能库

除了核心链路，Superpowers 还包含独立可用的技能：

**测试**：`test-driven-development` — 含常见测试反模式参考

**调试**：
- `systematic-debugging` — 四阶段根因分析（含根因追踪、纵深防御、条件等待技术）
- `verification-before-completion` — 确认问题真的被修复了，而不是症状消失了

**协作流程**：`brainstorming`、`writing-plans`、`executing-plans`、`dispatching-parallel-agents`、`requesting-code-review`、`receiving-code-review`、`using-git-worktrees`、`finishing-a-development-branch`、`subagent-driven-development`

**元技能**：`writing-skills`（按最佳实践创建新技能，含测试方法）

## 安装

Claude Code 可以直接从官方插件市场装：

```bash
/plugin install superpowers@claude-plugins-official
```

Cursor 在 Agent 聊天里：

```
/add-plugin superpowers
```

Codex 或 OpenCode 需要手动初始化——告诉它们去拉对应的 INSTALL.md，按里面的步骤做就行：

```
Fetch and follow instructions from https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/.codex/INSTALL.md
```

Gemini CLI：

```bash
gemini extensions install https://github.com/obra/superpowers
```

验证是否安装成功：新开一个会话，说"帮我规划这个功能"，如果 brainstorming 技能自动触发了，就说明装好了。

## 适用边界

Superpowers 解决的问题是：agent 有能力，但缺少结构化的工作流约束。它不会让一个糟糕的模型变好，也不会替你做技术决策，但它会阻止 agent 跳过设计直接开写，阻止它在没测试的情况下宣布完成。

对于已经用上 AI 编码工具的开发者，如果你发现 agent 经常偏题、任务一大就失控、或者测试总是事后补的，这套框架值得一试。对于偶尔用 agent 做小改动的场景，结构反而会是额外开销。

## 参考

- [obra/superpowers on GitHub](https://github.com/obra/superpowers)
- [Superpowers for Claude Code（作者博文）](https://blog.fsck.com/2025/10/09/superpowers/) — Jesse Vincent
- [Prime Radiant](https://primeradiant.com/) — 项目背后的团队
