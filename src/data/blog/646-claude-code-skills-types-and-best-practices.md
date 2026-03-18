---
pubDatetime: 2026-03-18T10:24:37+08:00
title: "Claude Code Skills 的九种类型与写法技巧"
description: "Anthropic 内部已有数百个 Skills 在真实运行，这篇文章总结了从实践中归纳出的 Skills 分类方式，以及写好一个 Skill 的关键技巧：Description 是给模型读的触发条件，而不是摘要；Gotchas Section 是信息密度最高的部分；Skill 是一个文件夹，不是一个 Markdown 文件。"
tags: ["Claude Code", "AI 工具", "Agent", "开发工具", "Skills"]
slug: "claude-code-skills-types-and-best-practices"
ogImage: "../../assets/646/01-cover.png"
source: "https://x.com/trq212/status/2033949937936085378"
---

![Claude Code Skills 概念图](../../assets/646/01-cover.png)

Skills 是 Claude Code 里最常被使用的扩展点，但灵活性也意味着"不知道怎么做才对"。Anthropic 内部已有数百个 Skills 在跑，Thariq（@trq212）把他们的实践经验整理成了这篇文章，分两块：Skills 大概能做什么用，以及怎么写才好用。

一个容易误会的事情是，Skills 不只是 Markdown 文件。官方文档里说的是"文件夹"——可以包含脚本、assets、数据、配置，Claude 可以发现、读取、操作这些文件。真正有意思的 Skill 往往就在这个结构里做文章。

## 九种 Skill 类型

Anthropic 在整理内部所有 Skills 后，发现它们大致聚拢成 9 类：

**1. 库与 API 参考（Library & API Reference）**  
解释如何正确使用某个库、CLI 或 SDK，尤其是内部库或 Claude 容易用错的通用库。通常包含一组参考代码片段，加上一个"踩坑列表"。例子：内部计费库的边界情况、内部 CLI 的每条子命令示例。

**2. 产品验证（Product Verification）**  
描述如何测试和验证代码是否正确。常搭配 Playwright、tmux 等工具。验证类 Skill 有时值得专门让工程师花一周时间打磨——包括让 Claude 录制测试视频，或在每个步骤做编程断言。

**3. 数据获取与分析（Data Fetching & Analysis）**  
接入数据和监控系统，包含带凭证的数据获取库、仪表盘 ID、常见查询模式。例如："要看 signup → activation → paid 的漏斗，join 哪些事件表，canonical user_id 在哪张表"。

**4. 业务流程自动化（Business Process & Team Automation）**  
把重复工作流打包成一条命令。通常指令本身不复杂，但可能依赖其他 Skills 或 MCPs。把执行结果存进日志文件可以帮助模型保持一致性、回顾历史执行情况。

**5. 代码脚手架（Code Scaffolding & Templates）**  
为特定功能生成样板代码，尤其适合脚手架里有自然语言要求、不能完全靠代码覆盖的情况。例如：带你的 auth、日志、部署配置的新应用模板。

**6. 代码质量与审查（Code Quality & Review）**  
可以包含确定性脚本来保证鲁棒性，也可以配合 Git hook 或 GitHub Action 自动触发。典型例子：派一个"fresh eyes"子 agent 来批评代码，实现修复，持续迭代直到问题降低到小挑剔为止。

**7. CI/CD 与部署（CI/CD & Deployment）**  
帮你拉取、推送、部署代码，通常引用其他 Skills 来收集数据。例如：监控 PR → 重试 flaky CI → 解决合并冲突 → 启用自动合并。

**8. 运行手册（Runbooks）**  
接收一个症状（Slack 线程、告警、错误特征），走完多步工具调查，生成结构化报告。例如：给定 request ID，从每个可能触达它的系统里拉取匹配日志。

**9. 基础设施运维（Infrastructure Operations）**  
执行例行维护和操作流程，部分涉及破坏性操作，加护栏很有意义。例如：找到孤儿 Pod/卷 → 发到 Slack → 等待期 → 用户确认 → 级联清理。

## 写法技巧

### Description 是触发条件

Claude Code 启动 session 时，会把每个可用 Skill 的 description 列出来扫一遍，再决定"有没有 Skill 适合这个请求"。所以 description 不是摘要，不是给人读的，它是触发条件——告诉模型什么时候调用这个 Skill。写的时候要问：Claude 看到这个 description，能不能判断出"这个请求该用这个 Skill"？

### Gotchas Section 信息密度最高

Thariq 把"Gotchas Section"称为信息密度最高的部分。这一节应该从 Claude 真实踩过的坑里积累，而不是预先设计。好的 Skill 会随着时间迭代，每次 Claude 遇到新边界情况就更新一次。

### Skill 是文件夹

用文件系统做"渐进披露"（Progressive Disclosure）。告诉 Claude 文件夹里有什么文件，它会在合适时机去读。最简单的形式：把详细 API 签名和用法示例拆到 `references/api.md`。高级一点：在 `assets/` 里放模板文件，让 Claude 复制使用；在 `scripts/` 里放可组合的工具脚本。

### 给 Claude 脚本，不要让它重造轮子

给 Claude 代码，它就能把 token 花在"该做什么"上，而不是重写样板。一个数据分析 Skill 里可以预置一组从事件源取数据的辅助函数，Claude 在接到"星期二发生了什么"这类问题时，直接组合这些函数生成分析脚本。

### 不要把 Claude 逼进死路

Skills 是复用的，不要把指令写得太死。给 Claude 它需要的信息，同时留出适应情况的空间。

### 按需 Hook

Skills 可以注册只在调用时激活、session 结束后失效的 Hook。典型例子：

- `/careful`：通过 PreToolUse matcher 拦截 `rm -rf`、`DROP TABLE`、强制推送、`kubectl delete`。不总是开，只在你知道自己要碰生产环境的时候挂上
- `/freeze`：阻止任何不在特定目录里的 Edit/Write。调试时有用："我只想加日志，但我一直会顺手改掉不相关的东西"

### 记忆与数据存储

Skill 可以在自身目录里存数据来实现记忆——简单到 append-only 文本日志，复杂到 SQLite 都行。一个 standup-post Skill 可以维护一个 `standups.log`，每次运行时 Claude 读取自己的历史，知道昨天写了什么。注意：Skill 升级可能会删掉目录里的数据，建议用 `${CLAUDE_PLUGIN_DATA}` 这个稳定路径来存持久化数据。

## 分发与度量

小团队把 Skills check 进 repo（放在 `./.claude/skills` 下）就够了。但每个 check 进来的 Skill 都会给模型增加一点上下文。规模变大之后，内部插件市场可以让团队自己选择安装哪些。

Anthropic 通过一个 PreToolUse Hook 记录 Skill 调用，方便找出哪些 Skill 受欢迎、哪些触发率低于预期。

Skills 之间可以相互依赖——在指令里直接引用其他 Skill 的名字，模型会在安装的情况下调用它，不需要原生的依赖管理机制。

## 参考

- [Lessons from Building Claude Code: How We Use Skills](https://x.com/trq212/status/2033949937936085378) — Thariq (@trq212)
- [Claude Code Skills 文档](https://code.claude.com/docs/en/skills)
- [Claude Code Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Skill Creator 介绍](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills)
