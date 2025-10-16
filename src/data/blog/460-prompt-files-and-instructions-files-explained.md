---
pubDatetime: 2025-09-18
tags: [".NET", "AI", "Productivity", "Tools"]
slug: prompt-files-and-instructions-files-explained
source: https://devblogs.microsoft.com/dotnet/prompt-files-and-instructions-files-explained
title: Prompt 文件与 Instructions 文件详解：为 Copilot 提供长期规则与一次性任务上下文
description: 系统梳理 Prompt 文件与 Instructions 文件的定位、适用场景与最佳实践，帮助你在 VS Code、Visual Studio 与 GitHub 上高效定制 Copilot，既能统一团队规范，也能为特定任务提供精准上下文。
---

## 概览

GitHub Copilot 正在从“代码补全工具”进化为“智能编码代理”。要想让它在你的代码库里发挥最大价值，关键在于给它清晰的“规则”和“任务说明”。这正是 Instructions 文件与 Prompt 文件的职责所在：

- Instructions 文件：用来“设定长期规则与约束”，在仓库或特定语言范围内持续生效。
- Prompt 文件：用来“描述一次性的具体任务”，在会话或某个文件/场景中临时生效。

## 为什么要区分两类文件？

- 关注点不同：
  - Instructions：强调“恒定规则与边界”（代码风格、命名、允许的自动化范围）。
  - Prompts：强调“一次性目标”（让 Copilot 为某个场景生成/修改代码或文档）。
- 生命周期不同：
  - Instructions：提交到仓库后，自动随每次请求应用（全局或按文件类型）。
  - Prompts：按需调用，适合复用常见工作流或特定任务。
- 组合更强：用 Instructions 打造“护栏”，用 Prompts 加速“具体任务”，既安全又高效。

## 什么是 Instructions 文件？

- 定义：通常命名为 `copilot-instructions.md`，用于定义“Copilot 在本仓库/特定范围内应遵守的规则与边界”。
- 放置位置：
  - 全局：`.github/copilot-instructions.md`
  - 按类型：`.github/instructions/` 下为 `.cs`、`.razor` 等特定文件类型提供指令（仅在匹配的请求中生效）。
- 适用场景：
  - 团队协作统一风格与规则（命名规范、提交格式、限制高风险变更）。
  - 开源项目引导外部贡献者符合项目约定。

### Instructions 文件应包含什么？

建议结构（可按需裁剪）：

- 目的与范围：一句话说明该文件控制什么与不控制什么（路径/语言/排除项）。
- 项目概览：运行时/平台、主要技术栈、目标受众。
- 工具与版本：关键 SDK/CLI 及版本要求。
- 构建/运行/测试命令：最小可复现命令（Windows 下给 PowerShell 示例）。
- 代码规范与格式化：使用何工具（如 dotnet format、prettier）、命名规则、风格约定。
- API/数据契约：重要 DTO/JSON 结构或数据库关键字段（避免暴露机密）。
- 允许的自动化操作：如“修复拼写/格式化/小范围重构/补充测试”。
- 需要人工审核的操作：如“数据库迁移/大重构/生产配置/依赖重大升级”。
- 输出与补丁规则：变更展示方式、提交信息格式、PR 模板或要求。
- 失败与回滚策略：构建/测试失败时如何处理，何时回滚，通知谁。
- 维护说明：由谁维护、何时更新版本。

### Instructions 文件示例骨架

```markdown
# Repository-wide Copilot Instructions

- Scope: src/**/\*.cs, src/**/\*.razor; exclude: src/Generated/**, vendor/**
- Runtime: .NET 9/10; Node 20 for tooling

## Build/Run/Test (PowerShell)

- Build: dotnet build
- Test: dotnet test
- Run: dotnet run --project src/App/App.csproj

## Conventions

- C# style: dotnet format; nullable enabled; PascalCase for public APIs
- Commit: feat/fix/docs style; imperative mood; link issue when applicable

## Allowed Autonomous Actions

- Safe refactors within a single file with tests
- Add/adjust unit tests; fix typos; run formatters

## Require Human Review

- DB schema/migrations; infra changes; dependency major bumps

## Output & PR

- Provide patch diff per file; include test evidence and lint results

## Failure Handling

- If build/test fails: revert, summarize root cause, propose fix options
```

小贴士：本仓库已配有 `/.github/copilot-instructions.md`（如有），你可以在此基础上补充“范围、命令、允许/禁止清单”等高价值信息。

## 什么是 Prompt 文件？

- 定义：为某个“具体任务/会话”准备的提示文件，用于给 Copilot 提供更详细的上下文与步骤。
- 放置位置：`.github/prompts/[name].prompt.md`
- 调用方式：
  - VS Code 聊天：输入 `/[name]` 即可调用。
  - Visual Studio 聊天：输入 `#[name]` 调用。
- 适用场景：
  - 原型开发、脚手架生成、重复性工作流封装（如“创建 Analyzer”、“修复特定代码味道”）。
  - 新成员上手“标准任务”的统一入口。

### Prompt 文件应包含什么？

- 元数据：名称/作者/更新时间/适用范围（路径或语言）。
- 目的与一句话摘要：这份 Prompt 要驱动 Copilot 做什么。
- 人设与语气：简洁、保守、优先测试；遇到不确定先提问澄清。
- 允许的自动化操作与限额：可修改的文件类型/数量上限；不得改动的目录。
- 构建/运行/测试命令：在本地最小“冒烟验证”。
- Lint/Format 命令：如何快速校验风格一致性。
- 输出格式：Patch/PR 样式、提交信息范式、需要附带的验证证据。
- 异常处理：失败如何回退与重试，何时请人类确认。
- 例子：2–3 个“好/坏”示例，帮助 Copilot 对齐边界。

### Prompt 文件示例骨架

```markdown
---
mode: agent
---

目标：创建一个 Roslyn Analyzer，检测弱加密 API 的使用并给出替代建议。

范围：仅修改 src/Analyzers/** 与 tests/**；禁止改动 infra/\*\* 与生产配置。

要求：

- 先生成最小 Analyzer 与 CodeFix 骨架
- 覆盖以下用例：MD5.Create(), SHA1.Create(), RijndaelManaged (insecure modes), new HMACSHA1(), TripleDES
- 建议替代：SHA256、RandomNumberGenerator 或内部封装库

本地验证（PowerShell）：

- dotnet build
- dotnet test

输出：

- 以补丁形式逐文件展示变更
- 附带通过的测试摘要与关键实现说明
```

在 VS Code 中，打开聊天输入：`/CreateAnalyzer 检测项目中弱加密 API 的使用并替换为安全实现`，即可复用该 Prompt。

## 如何选择：Instructions vs. Prompts

| 维度     | Instructions 文件          | Prompt 文件                |
| -------- | -------------------------- | -------------------------- |
| 目标     | 长期规范与边界             | 一次性/可复用的具体任务    |
| 生效范围 | 仓库/语言/路径级别         | 会话/文件/局部场景         |
| 触发方式 | 自动随请求附加             | 聊天命令按需调用           |
| 风险控制 | 制定护栏（允许/禁止）      | 在护栏内执行操作           |
| 最佳实践 | 与 CI 规则、风格工具强绑定 | 与任务模板、复用清单强绑定 |

建议组合用法：

- 先写好 Instructions 做“护栏”，然后为常见任务沉淀 Prompt 做“加速器”。
- 团队评审 Prompt，确保它们不会引导越界或破坏既定规范。

## 落地清单（一步到位）

- 在 `.github/copilot-instructions.md` 定义：范围、构建/测试命令、允许/禁止清单、输出规范、回滚策略。
- 在 `.github/instructions/` 为 `.cs`、`.razor` 等按需细化子规则。
- 在 `.github/prompts/` 建立常用任务模板（脚手架、重构、质量保障任务）。
- 在 README/开发文档中说明：如何调用、如何新增、如何评审与版本管理。
- 在 CI 中强制：格式化与测试必须通过；必要时对高风险变更类型进行阻断或标记。

## 常见陷阱与规避

- 仅写“愿景口号”，没有“可执行命令与边界清单” → Copilot 很难稳定遵守。
- Prompt 过度自由，允许大范围修改 → 易产生意外扩散与难以审查的变更。
- 忽视平台差异（Windows/PowerShell vs. Bash）→ 命令不可复现。
- 输出格式不统一 → 代码评审与自动化校验困难。

## 进阶技巧（提高命中率与可维护性）

- 将“最小可运行命令”与“验证步骤”写进文件，让 Copilot 也能按步骤执行与校验。
- 为 Prompt 添加“文件/路径白名单 + 修改上限”，显式限制变更范围。
- 给出 2–3 个“好/坏示例”，让模型更好对齐你的质量标准。
- 定期清理与归档过期 Prompt，保持团队知识库“少而精”。

## 参考与延伸阅读

- 官方文档：Customize chat to your workflow（自定义 Copilot Chat）
- 示例仓库：awesome-copilot/instructions、awesome-copilot/prompts
- 相关：如何通过 Prompt 文件复用加速协作（本仓库相关文章）

---

通过将 Instructions 与 Prompt 文件结合使用，你可以既“立规矩”，又“提效率”。让 Copilot 成为真正的团队成员——稳定、可靠、可控，并持续复用团队的最佳实践。
