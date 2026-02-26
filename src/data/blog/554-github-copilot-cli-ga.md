---
pubDatetime: 2026-02-25
title: "GitHub Copilot CLI 正式发布：终端里的全能 AI 编程代理"
description: "GitHub Copilot CLI 正式面向所有付费 Copilot 订阅用户开放，从终端助手进化为完整的代理式开发环境，支持规划、构建、审查和跨会话记忆等功能。"
tags: ["GitHub Copilot", "AI", "CLI", "Developer Productivity"]
slug: "github-copilot-cli-ga"
source: "https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/"
---

GitHub Copilot CLI 正式面向所有付费 Copilot 订阅用户开放。这是一个终端原生的编程代理，将 GitHub Copilot 的能力直接带到命令行。

自 2025 年 9 月公开预览以来，团队根据用户反馈做了数百项改进。Copilot CLI 已经从一个终端助手成长为完整的代理式开发环境，能在不离开终端的情况下完成规划、构建、审查和跨会话记忆。

## 终端中的代理式开发

Copilot CLI 不只是一个聊天界面，它是一个自主编程代理，能够规划复杂任务、执行多步骤工作流、编辑文件、运行测试并持续迭代直到完成。你可以自由选择控制粒度，从逐步审批到完全自主运行。

主要能力包括：

- **Plan Mode**：按 `Shift+Tab` 切换到规划模式，Copilot 会分析你的请求、提出澄清性问题，并在写任何代码之前构建结构化的实现方案。审查并批准方案后，再由 Copilot 执行。
- **Autopilot Mode**：对于你信任 Copilot 可以端到端处理的任务，Autopilot 模式允许 Copilot 自主工作，执行工具、运行命令、持续迭代，无需中途停下来等待审批。
- **内置专用代理**：Copilot 会在适当的时候自动委派给专用代理（如 Explore 用于快速代码库分析、Task 用于运行构建和测试、Code Review 用于高质量的变更审查、Plan 用于实现方案规划），多个代理可以并行运行。
- **后台委派**：在提示前加 `&` 前缀，可以将工作委派给云端的 Copilot 编程代理，释放终端去做其他事。用 `/resume` 可以在本地和远程编程代理会话之间无缝切换。

## 模型自由选择

支持来自 Anthropic、OpenAI 和 Google 的最新模型，包括 Claude Opus 4.6、Claude Sonnet 4.6、GPT-5.3-Codex 和 Gemini 3 Pro。对于快速任务还有 Claude Haiku 4.5 等更轻量的模型可选。

你可以在会话中途用 `/model` 切换模型，通过配置调整扩展思考模型的推理强度，用 `Ctrl+T` 切换推理过程的可见性。

GPT-5 mini 和 GPT-4.1 包含在 Copilot 订阅中，不额外消耗高级请求配额。

## 通过 MCP、插件和技能扩展

Copilot CLI 内置 GitHub 的 MCP 服务器，并支持自定义 MCP 服务器来连接任何工具或服务。

- **插件**：用 `/plugin install owner/repo` 直接从 GitHub 仓库安装社区和自定义插件。插件可以打包 MCP 服务器、代理、技能和钩子。
- **Agent Skills**：通过 Markdown 技能文件教会 Copilot 专门的工作流。技能文件在相关时自动加载，跨 Copilot 编程代理、Copilot CLI 和 VS Code 通用。
- **自定义代理**：通过交互式向导或编写 `.agent.md` 文件创建专用代理，代理可以指定自己的工具、MCP 服务器和指令。
- **钩子**：在关键生命周期节点扩展行为。`preToolUse` 钩子可以拒绝或修改工具调用，`postToolUse` 钩子可以做自定义后处理。

## 审查、差异和撤销

- `/diff`：查看会话期间所有变更的语法高亮内联差异，可以添加行级评论并提交结构化反馈，在会话变更和分支差异之间切换。
- `/review`：在 CLI 中直接分析暂存或未暂存的代码变更，提交前快速做一次检查。
- **撤销/回退**：按 `Esc-Esc` 将文件变更回退到会话中的任意历史快照。

## 无限会话和仓库记忆

- **自动压缩**：当对话接近上下文窗口的 95% 时，Copilot 会自动在后台压缩历史。会话可以按需持续运行。
- **仓库记忆**：Copilot 会记住它在你的代码库中学到的约定、模式和偏好，让未来的工作更高效。
- **跨会话记忆**：可以查询过去会话中的工作内容、文件和 Pull Request。

## 全平台安装

Copilot CLI 支持 macOS、Linux 和 Windows，可以通过 npm、Homebrew、WinGet、Shell 安装脚本和独立可执行文件安装。Homebrew、WinGet 和脚本安装方式支持自动更新。Copilot CLI 也包含在默认的 GitHub Codespaces 镜像中，并作为 Dev Container Feature 提供。

## 精致的终端体验

自公开预览以来，团队在终端体验上投入了大量精力：

- **全屏模式**：支持鼠标文字选择、Page Up/Down 滚动和专用底部状态栏的全屏终端界面（目前作为 `/experimental` 功能提供）。
- **主题选择**：用 `/theme` 从内置主题中选择，包括 GitHub Dark、GitHub Light 和色盲友好变体。
- **Shell 集成**：Copilot 尊重你的 `$SHELL` 环境变量，支持 `!` 前缀直接执行 Shell 命令。
- **键盘优先导航**：完整的 UNIX 快捷键支持（`Ctrl+A/E/W/U/K`、`Alt+方向键`），`Ctrl+Z` 挂起/恢复，`?` 快速帮助叠加层。
- **无障碍**：屏幕阅读器模式、可配置的推理过程可见性、窄终端的响应式布局。

## 企业就绪

- 组织策略：管理员可以通过 Copilot 策略设置控制模型可用性。
- 网络访问管理：按订阅的 API 端点，遵循 GitHub 网络访问管理指南。
- 代理支持：HTTPS 代理支持。
- 认证：OAuth 设备流、GitHub CLI Token 复用，以及适合 CI/CD 的 `GITHUB_ASKPASS` 支持。
- 策略执行钩子：用 `preToolUse` 钩子执行文件访问策略、参数清理和自定义审批工作流。

## 快速上手

1. 用你偏好的方式安装 Copilot CLI
2. 运行 `copilot` 并用 GitHub 账号认证
3. 运行 `/init` 生成针对你项目的 Copilot 指令
4. 开始构建

Copilot CLI 可在 Copilot Pro、Pro+、Business 和 Enterprise 订阅中使用。Business 和 Enterprise 订阅用户需要管理员在 Policies 页面中启用 Copilot CLI。
