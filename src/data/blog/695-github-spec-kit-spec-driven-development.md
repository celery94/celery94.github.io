---
pubDatetime: 2026-03-31T14:53:00+08:00
title: "GitHub Spec Kit：用规格说明驱动 AI 编程的开源工具包"
description: "Spec Kit 是 GitHub 开源的规格驱动开发（SDD）工具包，把需求规格变成 AI 可执行的开发流程，覆盖从建项到实现的全链路。本文介绍其核心理念、安装方式、开发流程和扩展生态。"
tags: ["AI编程", "GitHub", "开发工具", "Spec-Driven Development"]
slug: "github-spec-kit-spec-driven-development"
ogImage: "../../assets/695/01-cover.png"
source: "https://github.com/github/spec-kit"
---

![Spec Kit 封面](../../assets/695/01-cover.png)

Vibe Coding 很有趣，但当项目稍大一点，纯靠 prompt 驱动的开发流程就容易散架——需求没理清、步骤跳来跳去、AI 生成的代码偏离意图。Spec Kit 要解决的就是这个问题：在你和 AI 之间加一层结构化的规格说明，让 AI 按规格而不是凭感觉来写代码。

Spec Kit 是 GitHub 官方开源的 Spec-Driven Development（规格驱动开发）工具包，目前在 GitHub 上已有 83.9k 星，支持 20 多种 AI 编程代理，社区扩展和贡献者数量都在快速增长。

## 规格驱动开发是怎么回事

传统的软件开发里，规格说明只是中间产物——写完就扔，真正干活的还是代码。Spec-Driven Development 反过来：把规格说明抬到核心位置，让它直接驱动实现。

具体到 Spec Kit 的场景：你先用自然语言描述要做什么（specification），工具帮你把它拆成技术方案（plan）和任务列表（tasks），然后 AI 代理按计划逐步实现。整个过程是多步精炼，不是一句 prompt 生成全部代码。

这背后的核心假设是：AI 擅长按照清晰的规格来执行，但不擅长从模糊的需求里独立做端到端的判断。你负责"做什么"和"为什么"，AI 负责"怎么做"。

## 安装 Specify CLI

Spec Kit 提供了一个名为 `specify` 的 CLI 工具，基于 Python，用 `uv` 安装。

### 一次性安装（推荐）

```bash
# 安装指定版本（推荐，vX.Y.Z 替换为最新 release tag）
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z

# 或安装 main 分支最新版
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
```

安装完成后，`specify` 命令会直接在 PATH 中可用。

### 免安装运行

```bash
uvx --from git+https://github.com/github/spec-kit.git@vX.Y.Z specify init <项目名>
```

### 系统要求

- Linux / macOS / Windows
- Python 3.11+
- Git
- [uv](https://docs.astral.sh/uv/)
- 至少一个支持的 AI 编程代理

## 六步开发流程

Spec Kit 把一个功能的开发分成六个明确的阶段，对应六条斜杠命令。以一个照片管理应用为例，走一遍完整流程。

### 第 1 步：初始化项目

```bash
specify init my-project --ai copilot
```

这会创建项目目录，配置好对应 AI 代理的命令文件。`--ai` 参数指定你使用的代理，比如 `claude`、`copilot`、`cursor-agent`、`gemini` 等。

### 第 2 步：建立项目准则（Constitution）

在 AI 代理里执行：

```
/speckit.constitution 创建聚焦代码质量、测试标准、用户体验一致性和性能要求的项目准则
```

这一步生成项目的"宪法"——所有后续开发都要遵守的基本原则。它决定了 AI 在实现时的优先级和约束。

### 第 3 步：撰写规格说明（Specification）

```
/speckit.specify 构建一个照片管理应用，支持按日期分组的相册、主页拖拽排序、
相册内瓦片式预览。相册不支持嵌套。
```

描述"做什么"和"为什么"，不用指定技术栈。这是整个流程的核心输入。

### 第 4 步：生成技术方案（Plan）

```
/speckit.plan 使用 Vite，尽量少引入库依赖。使用原生 HTML/CSS/JavaScript。
图片不上传，元数据存本地 SQLite。
```

这一步把规格转化为技术选型和架构设计。

### 第 5 步：拆解任务（Tasks）

```
/speckit.tasks
```

从方案中生成可执行的任务列表，每个任务足够小、可独立验证。

### 第 6 步：开始实现（Implement）

```
/speckit.implement
```

AI 代理按任务列表逐个执行，生成代码。

整个流程是递进的：前一步的输出是下一步的输入。跳过中间步骤会导致后续质量下降。

## 可选的辅助命令

除了六步核心流程，Spec Kit 还提供了几个辅助命令：

| 命令 | 用途 |
|---|---|
| `/speckit.clarify` | 在生成方案前，补充和澄清规格说明中的模糊点 |
| `/speckit.analyze` | 在任务拆解后、实现前，做跨产物一致性检查 |
| `/speckit.checklist` | 生成定制化质量检查清单，像"给英文写单元测试"那样检验需求完整性 |

## 支持的 AI 代理

Spec Kit 目前支持 20+ 种 AI 编程代理，涵盖主流选项：

- **IDE 集成**：GitHub Copilot、Cursor、Windsurf、Kilo Code、Roo Code、Trae
- **CLI 工具**：Claude Code、Gemini CLI、Codex CLI、Qwen Code、opencode
- **其他**：Amp、Jules、Junie、SHAI、IBM Bob、Kiro CLI、Pi、Mistral Vibe 等

对于列表之外的代理，可以用 `--ai generic --ai-commands-dir <path>` 自行适配。

## 扩展和预设机制

Spec Kit 有两套自定义体系：

### 扩展（Extensions）——增加新能力

扩展引入新的命令和模板。社区已有 30 多个扩展，按功能分为五大类：

- **文档类（docs）**：规格说明的校验、质量分析、教育指南生成
- **代码类（code）**：代码审查、实现验证、任务完成检测
- **流程类（process）**：多代理编排、生命周期管理、质量门控
- **集成类（integration）**：Jira、Azure DevOps、GitHub Projects、Linear、Trello
- **可视化类（visibility）**：项目健康检查、工作流进度报告

```bash
# 搜索可用扩展
specify extension search

# 安装扩展
specify extension add <扩展名>
```

几个值得关注的扩展：

- **MAQA**：多代理 + QA 工作流，支持并行 Worktree 实现
- **spec-kit-review**：实现后的多维代码审查
- **spec-kit-verify**：将实现代码与规格交叉验证
- **spec-kit-jira / azure-devops**：自动同步任务到项目管理工具

### 预设（Presets）——改变已有行为

预设不增加新命令，而是覆盖模板和指令，用于执行组织标准、领域术语或合规要求。

```bash
specify preset search
specify preset add <预设名>
```

多个预设可以叠加，按优先级排序。

## 适用场景

根据 Spec Kit 项目文档，它被设计用于三类场景：

| 场景 | 说明 |
|---|---|
| 从零开始（Greenfield）| 从高层需求开始，经规格、方案、任务到实现 |
| 迭代增强（Brownfield）| 在已有代码库上加功能、做现代化改造 |
| 创意探索 | 对同一需求并行尝试不同技术栈和架构方案 |

社区已经提供了多个实战 Walkthrough，覆盖 .NET CLI、Spring Boot + React、ASP.NET 棕地项目、Jakarta EE 大型项目、Go + React 终端驱动等组合，可以直接参考。

## 它不做什么

Spec Kit 不会帮你写 prompt、不会自动选技术栈、也不会替你做产品决策。它的定位很明确：在你想清楚要做什么之后，帮你把这些想法结构化地喂给 AI 代理，减少中间的信息损耗。

如果你的项目只是写个小脚本或快速原型，直接 prompt 可能更快。Spec Kit 更适合需要多步骤、多文件、有明确质量要求的开发任务。

## 参考

- [Spec Kit GitHub 仓库](https://github.com/github/spec-kit)
- [Spec Kit 官方文档](https://github.github.io/spec-kit/)
- [Spec-Driven Development 完整方法论](https://github.com/github/spec-kit/blob/main/spec-driven.md)
- [社区扩展目录](https://github.com/github/spec-kit/blob/main/extensions/catalog.community.json)
