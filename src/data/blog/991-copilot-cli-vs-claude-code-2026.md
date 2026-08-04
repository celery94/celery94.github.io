---
pubDatetime: 2026-08-04T07:39:25+08:00
title: "Copilot CLI vs Claude Code 怎么选"
description: "GitHub 生态与 Claude 生态的终端 AI 编程代理怎么选？本文从安装认证、自定义指令、权限、MCP、模型、子代理到无头自动化逐项对比，并给出 GitHub 重度团队和 Claude 重度团队各自的选型建议。"
tags: ["GitHub Copilot", "Claude Code", "CLI", "AI 编程", "开发工具"]
slug: "copilot-cli-vs-claude-code-2026"
ogImage: "../../assets/991/01-cover.jpg"
source: "https://www.devleader.ca/2026/07/31/github-copilot-cli-vs-claude-code-which-terminal-agent-should-you-use-in-2026"
---

2026 年，终端里的 AI 编程代理已经成为日常开发的基础设施。如果你正在 GitHub Copilot CLI 和 Claude Code 之间做选择，你面对的不是「哪个更强」，而是两个**重心完全不同**的产品：一个生长在 GitHub 生态里，一个围绕 Claude 模型家族构建。

Nick Cosentino（Dev Leader）在 2026 年 7 月底的这篇文章里，以一名 .NET 开发者的视角把两个工具从头到尾比了一遍——安装、认证、计费、自定义指令、权限、MCP、模型、子代理、无头自动化，最后给出明确的选型建议。本文按同样的框架整理成中文重述，并对照双方 2026 年 8 月的最新官方文档核对了易变信息。

他的结论可以一句话概括：**两个我都用。** 对住在 GitHub issues、PR、Actions 和 Copilot 策略里的 .NET 开发者，Copilot CLI 是更自然的默认选择；对以 Claude 为中心的工作流，Claude Code 无可替代。关键在于先认清各自的主场。

## 两个产品的出发点完全不同

GitHub 官方文档把 Copilot CLI 描述为**终端代理**：回答问题、编写和调试代码、与 GitHub.com 交互、处理 issue、检查 pull request、创建 PR。它内置 GitHub MCP 服务器，使用 GitHub 认证，要求活跃的 Copilot 订阅。Copilot CLI 在 2026 年 2 月 25 日正式 GA，此后保持高频更新。

Claude Code 则从 Claude 出发。Anthropic 把它定位为覆盖终端、IDE、桌面应用和浏览器的代理式编码工具：终端 CLI 能编辑文件、运行命令、使用 MCP、创建提交和 PR、运行子代理、执行非交互式提示。但产品的中心是 Claude 模型家族和 Anthropic 的工作流——`CLAUDE.md`、子代理、skills、hooks、memory。

没有哪一方自动更好：当工作从 issue、PR 或仓库策略开始时，GitHub 集成减少摩擦；当团队标准化在 Claude、直接使用 Anthropic API 或依赖 Claude 专属能力时，Claude-first 工作流更有吸引力。

## 对比总表

| 维度            | GitHub Copilot CLI                                                                                                               | Claude Code                                                              |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 产品哲学        | 面向 Copilot 订阅者的 GitHub 集成终端代理                                                                                        | 横跨终端、IDE、桌面、Web 的 Claude-first 编码代理                        |
| 安装            | `npm install -g @github/copilot`、WinGet、Homebrew cask、安装脚本                                                                | 原生安装器、Homebrew cask、WinGet、Linux 包管理器                        |
| 认证与计费      | 活跃 Copilot 订阅；高级请求与 GitHub AI Credits                                                                                  | Pro/Max/Team/Enterprise/Console 账号或受支持第三方提供商；API token 计费 |
| 自定义指令      | `.github/copilot-instructions.md`、`.github/instructions/**/*.instructions.md`、`AGENTS.md`，以及根目录 `CLAUDE.md`、`GEMINI.md` | `CLAUDE.md`、`.claude/rules/`、导入、自动记忆                            |
| 权限            | 工具审批提示、受信任目录、`--allow-tool`、`--deny-tool`、`--allow-all`、沙箱预览                                                 | 权限规则与模式、`/permissions`、allow/ask/deny、plan 模式、bypass 模式   |
| MCP             | 内置 GitHub MCP；`/mcp add`、`copilot mcp add`、`~/.copilot/mcp-config.json`                                                     | `claude mcp add`、`.mcp.json`、用户/项目作用域、HTTP/stdio/WebSocket     |
| 模型            | 经 Copilot 多模型可选（Anthropic、OpenAI、Google），默认 Claude Sonnet 4.5                                                       | Claude 模型别名：`sonnet`、`opus`、`haiku`、`fable` 等                   |
| GitHub 原生工作 | 检查 issue/PR/Actions、创建 issue、创建 PR、内置 GitHub MCP                                                                      | GitHub Actions、GitHub App 支持、git 操作                                |
| 无头与 CI       | `copilot -p`、`-s`、`--no-ask-user`、工具 allow/deny 标志                                                                        | `claude -p`、`--bare`、结构化 JSON 输出、受允许工具列表                  |
| 子代理          | 内置代理与 `/fleet` 并行子代理                                                                                                   | 内置子代理、自定义子代理、后台代理、代理团队                             |
| .NET on GitHub  | 与 GitHub 托管的 .NET 仓库、PR、issue、Actions、Copilot 策略契合                                                                 | 适合 Claude 为中心的编码循环                                             |

两张表读完，你会发现这不是「功能有无」的差异，而是**默认值与治理方式**的差异。下面展开几个决定选型的关键点。

## 安装、认证与计费

Copilot CLI 的官方安装路径是 npm、WinGet、Homebrew 和安装脚本。npm 包名为 `@github/copilot`，命令是 `copilot`，要求 Node.js 22+；Windows 上还需要 PowerShell 6+ 和活跃的 Copilot 订阅：

```bash
# GitHub Copilot CLI via npm，要求 Node.js 22+
npm install -g @github/copilot

# Windows 包管理器
winget install GitHub.Copilot

# macOS 和 Linux Homebrew cask
brew install --cask copilot-cli
```

认证沿用 GitHub 模型：运行 `copilot login`、用 `/login`，或通过 `COPILOT_GITHUB_TOKEN`、`GH_TOKEN`、`GITHUB_TOKEN` 提供带 Copilot Requests 权限的 fine-grained PAT。官方命令参考明确说明经典 `ghp_` PAT 不受支持。

Claude Code 的安装同样简单，但账号模型不同：原生安装命令、Homebrew、WinGet、Linux 包管理器都可用，命令是 `claude`。账号要求 Pro、Max、Team、Enterprise 或 Console 之一，也支持 Amazon Bedrock、Google Cloud Agent Platform 和 Microsoft Foundry 等第三方提供商：

```bash
# Windows
winget install Anthropic.ClaudeCode

# macOS 或 Linux
brew install --cask claude-code
```

计费是现实问题：Copilot CLI 走 Copilot 订阅 + GitHub AI Credits 模型；Claude Code 可以订阅制也可以 API token 制，Anthropic 的成本文档特别强调，实际用量随模型选择、代码库规模、子代理、MCP 服务器和自动化程度大幅波动。如果组织已经有 Copilot 席位，这个对比某种意义上就是「要不要再开一条计费通道」。

## 自定义指令：AGENTS.md vs CLAUDE.md

这是两个工具在仓库行为层面最重要的差异，也是团队最容易踩坑的地方。

GitHub 官方文档确认，Copilot CLI 支持 `.github/copilot-instructions.md`、路径级 `.github/instructions/**/*.instructions.md`、`AGENTS.md`，而且根目录的 `CLAUDE.md` 和 `GEMINI.md` 可以作为备选。多个指令文件会**合并加载**而不是优先级回退。这意味着：仓库里已有的 `AGENTS.md` 能被 Copilot CLI 直接读取；为 Claude Code 写的 `CLAUDE.md` 也能给 Copilot CLI 提供有用的上下文。

Claude Code 的原生指令文件是 `CLAUDE.md`。Anthropic 的记忆文档写得很明确：**Claude Code 读 `CLAUDE.md`，不读 `AGENTS.md`**。如果仓库已经用 `AGENTS.md`，官方推荐的做法是建一个 `CLAUDE.md` 用 `@AGENTS.md` 导入它：

```markdown
@AGENTS.md

## Claude Code

Use plan mode for multi-file refactors and keep test output concise.
```

这个小小的文件能防止规则漂移。如果你两个工具都用，不要维护两份相同的工程规则——**保持单一事实来源，再把每个代理接进去**。

## 权限与审批：风险都在这

能写文件、能执行 shell 命令的代理，既是杠杆也是风险。原文把权限章节称为任何对比文章「最重要的部分」，这一点完全成立。

Copilot CLI 在项目目录启动时会询问目录信任。当 Copilot 想使用可能修改或执行文件的工具时，你可以选择批准一次、在当前会话内批准、或拒绝并给出反馈。自动化场景下，官方文档记录了 `--allow-tool`、`--deny-tool`、`--allow-all-tools`、`--allow-all`、`--yolo`、`--allow-all-paths`、`--no-ask-user` 等标志：

```bash
copilot -p "Summarize the branch and run the affected tests" \
  --allow-tool='read,shell(git status),shell(dotnet test)' \
  --deny-tool='shell(git push)' \
  --no-ask-user
```

Claude Code 的权限模型同样成熟：allow/ask/deny 三态，权限模式包括 `default`、`acceptEdits`、`plan`、`auto`、`dontAsk`、`bypassPermissions`，`/permissions` 命令管理规则。Anthropic 明确警告 `bypassPermissions` 只应放在容器或虚拟机等隔离环境里。

两个工具的建议是一致的：**仓库安全时放宽读权限，写权限收窄，shell 自动批准必须慎重**。在 .NET 仓库里预批准 `dotnet test` 是合理的；`git push`、部署脚本、数据库脚本和大范围包管理器命令则值得更多审视。

## MCP：两边都强，但 Copilot 内置 GitHub

2026 年再讨论终端代理，「支持不支持 MCP」已经不是问题，两边都是成熟的 MCP 客户端。真正的区别在默认值和治理。

Copilot CLI **默认内置 GitHub MCP 服务器**。如果你的工作从 GitHub issues、PR、Actions、仓库搜索或项目工作流开始，这是很大的加分项。额外服务器通过 `/mcp add`、`copilot mcp add` 或手动编辑 `~/.copilot/mcp-config.json` 配置，支持本地 STDIO 和远程 HTTP 服务器（SSE 出于兼容仍支持，但在 MCP 规范中已弃用）。

Claude Code 的 MCP 支持同样全面：`claude mcp add`、用户/项目作用域、`.mcp.json`、远程 HTTP、本地 stdio、WebSocket 配置，还有 MCP 审批工具、已配置服务器的 OAuth 登录、插件提供的 MCP 服务器和延迟工具搜索。

如果 MCP 计划涉及内部系统、数据库、遥测或工单系统，决定因素不是「哪个工具有 MCP」，而是**你如何约束这些 MCP 工具**——最小权限原则在这里同样适用。

## 模型选择：广度 vs Claude 深度

Copilot CLI 在 Copilot 产品边界内提供跨提供商的模型选择：Anthropic 的 Claude Opus/Sonnet 系列、OpenAI 的 GPT Codex 模型、Google 的 Gemini 模型，以及 Claude Haiku 等更快模型。我核对 npm 页面时，Copilot CLI 的默认模型仍是 Claude Sonnet 4.5；脚本里可以用 `--model` 或 `COPILOT_MODEL` 指定。

Claude Code 专注 Claude 模型与别名：`sonnet`、`opus`、`haiku`、`fable`、`best`、`opusplan` 等。需要说明的是，**别名指向的版本会随时间更新**：按 Anthropic 最新模型配置文档，Anthropic API 上 `sonnet` 解析为 Sonnet 5，`opus` 已解析为 Opus 5；原文写作时的 7 月版本中 `opus` 还指向 Opus 4.8（v2.1.219 起升级）。具体解析取决于提供商、版本、账号访问和组织设置。

```bash
# Copilot CLI：非交互任务固定模型
copilot -p "Review the staged C# changes for correctness" -s --model claude-sonnet-4.6

# Claude Code：会话级选择模型别名
claude --model sonnet
```

取舍很简单：Copilot CLI 在 Copilot 边界内给你更宽的多提供商选择；Claude Code 给你更深的 Claude 原生模型配置与别名体系。

## GitHub 原生工作与无头自动化

对 GitHub 重度团队来说，这里是 Copilot CLI 拉开差距的地方。官方文档展示的能力包括：列出打开的 PR、从指派的 issue 开始工作、创建 issue、检查 PR 变更、管理 PR，以及用内置 GitHub MCP 完成仓库搜索。它还能在 GitHub.com 上以你为作者创建 PR——这不是附属功能，这是产品的主场。

Claude Code 当然也能与 Git/GitHub 协作：官方文档覆盖 GitHub Actions、issue 和 PR 上的 `@claude` 提及、创建 PR，以及通过 Claude Code Action 做自动化。但这些是**集成进 GitHub**，与「GitHub 是产品原生平台」不是一回事。

无头执行方面，Copilot CLI 用 `-p`/`--prompt`，配 `-s`、`--no-ask-user`、`--secret-env-vars`、`--share`、`--agent`、模型标志和细粒度 allow/deny 控制；Claude Code 用 `claude -p`，官方建议脚本和 CI 场景加 `--bare`——它会跳过 hooks、skills、插件、MCP 服务器、自动记忆和 `CLAUDE.md` 的自动发现，启动上下文最小化：

```bash
claude --bare -p "Summarize the public API changes in this diff" \
  --allowedTools "Read" \
  --output-format json
```

对重复性工作流，原文的经验是：脚本需要 GitHub 上下文时用 Copilot CLI，想要结构化 Claude 输出时用 Claude Code。无论哪个，先只读启动、保留输出做审计，再考虑写能力的自动化。

## 子代理：/fleet vs 子代理体系

正经的代理工作很少是单线对话，子代理因此成为对比的核心。

Copilot CLI 内置 Explore、Task、General purpose、Code review、Research、Rubber duck 等代理，支持在 `.github/agents/` 和 `~/.copilot/agents/` 放自定义 `.agent.md`。`/fleet` 命令专门把复杂计划拆成独立子任务，通过子代理并行执行。GitHub 文档同时提醒成本问题：每个子代理都独立与 LLM 交互，并行工作会消耗更多 GitHub AI Credits。

Claude Code 内置 Explore、Plan、General-purpose 子代理，自定义子代理放在 `.claude/agents/` 和 `~/.claude/agents/`。子代理拥有独立的上下文窗口、提示、工具访问、模型设置和权限，还有后台代理与代理团队支持并行工作。

差异在编排风格：Copilot 的 `/fleet` 更贴近「实现计划执行」；Claude Code 的子代理模型配置自由度更高——尤其当你想要不同工具访问或不同模型别名的专职 worker 时。

## 怎么选：两条清晰的路径

**选 GitHub Copilot CLI，如果你的工作从 GitHub 开始、在 GitHub 结束。** 具体信号是：issue、PR、Actions、Copilot 订阅、组织策略、GitHub 原生评审流程是你工作的一部分；你需要一个能拉取 issue 和 PR 上下文进会话、用内置 GitHub MCP、跟随 `AGENTS.md`、在 Copilot 策略下跑多模型工作流、用 `/fleet` 并行、用 `copilot -p` 脚本化有边界任务的终端代理。对使用 GitHub 托管仓库的 .NET 团队，这是优先评估的路径。

**选 Claude Code，如果团队想要 Claude 为中心的编码代理。** 具体信号是：深度控制 Claude 模型别名、Anthropic 计费路径、Claude 专属的记忆（`CLAUDE.md`、`.claude/rules/`）、子代理、skills、hooks，以及结构化自动化（`claude -p`、JSON 输出、自定义子代理权限、Anthropic Console）。代价是 GitHub 集成不是产品的原生身份——它能和 GitHub 配合得很好，但每个任务都从 GitHub issue/PR 开始时，Copilot CLI 的阻抗失配更小。

## 给 .NET 开发者的建议

原文的默认建议非常直接：**主要工作在 GitHub 上的 .NET 开发者，先上 GitHub Copilot CLI，等出现明确的 Claude 专属理由再加 Claude Code。**

这是基于工作流的判断。如果仓库使用 GitHub Actions、PR 检查、issue、Copilot 订阅、包发布和组织策略，Copilot CLI 已经站在你工作发生的房间里。同时，在让任何代理改代码之前，先把 .NET 工程标准写进指令文件（比如 HttpClient 规范、日志规范这些团队约定）。

但不要就此把 Claude Code 移出工具箱。如果团队已经在付 Claude 的钱、偏好 Claude 模型行为、需要结构化 JSON 自动化，或者重度使用 Claude Code 子代理，它可能是更好的日常主力。

## 常见问题

**2026 年把这两个工具放在一起比公平吗？**
公平。两者都是能读代码、改文件、跑命令、用 MCP、参与开发流程的终端编码代理。真正的决策点是 GitHub 原生集成、模型策略、权限控制、计费和团队工作流契合度。

**Copilot CLI 会读 CLAUDE.md 吗？**
会。GitHub 当前的自定义指令文档确认 Copilot CLI 支持 `AGENTS.md` 和根目录的 `CLAUDE.md`/`GEMINI.md` 作为备选。反向则不成立：Claude Code 只读 `CLAUDE.md` 不读 `AGENTS.md`，想共享一份指令就在 `CLAUDE.md` 里 `@AGENTS.md`。

**哪个 MCP 支持更好？**
两边都很强。Copilot CLI 内置 GitHub MCP；Claude Code 有详细的项目/用户级 MCP 配置、插件提供的服务器、OAuth 流程和多种传输方式。接内部系统时，重点是最小权限约束。

**GitHub 上的 .NET 团队应该标准化 Copilot CLI 吗？**
通常应该。它契合已经在用 Copilot 订阅、PR、issue、Actions 的团队。但如果组织标准化在 Claude 订阅或 Anthropic API 计费上，Claude Code 可能更合适。

**先选哪个？**
GitHub 重度的 .NET 开发者先选 Copilot CLI；Claude 重度或组织已管理 Claude Code 工作流的先选 Claude Code。

## 最后的结论

这个选择没有普适赢家。GitHub Copilot CLI 是 GitHub 原生 .NET 团队更强的默认项；Claude Code 在 Claude-first 工作流里更强——Claude 专属模型、子代理、记忆和结构化自动化都是它的主场。

选**默认值与你的约束匹配**的那个工具。然后收紧权限、写好指令、跑测试、审 diff。代理能加速循环，但工程决策仍然由你负责。

---

如果你也在评估 AI 编程工具和终端代理，欢迎关注 Aide Hub。我们会继续分享 AI 助手、开发工具和软件工程实践的一手评测与上手教程。

## 参考

- [GitHub Copilot CLI vs Claude Code: Which Terminal Agent Should You Use in 2026?（原文，Nick Cosentino）](https://www.devleader.ca/2026/07/31/github-copilot-cli-vs-claude-code-which-terminal-agent-should-you-use-in-2026)
- [GitHub Copilot CLI: The Complete Guide to the Agentic Terminal Agent（作者前作）](https://www.devleader.ca/2026/07/09/github-copilot-cli-the-complete-guide-to-the-agentic-terminal-agent)
- [About GitHub Copilot CLI - GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-copilot-cli)
- [Adding custom instructions for GitHub Copilot CLI - GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions)
- [How Claude remembers your project - Claude Code Docs](https://code.claude.com/docs/en/memory)
- [Model configuration - Claude Code Docs](https://code.claude.com/docs/en/model-config)
- [Configure permissions - Claude Code Docs](https://code.claude.com/docs/en/permissions)
- [Claude Code costs - Claude Code Docs](https://code.claude.com/docs/en/costs)
- [GitHub Copilot CLI is now generally available - GitHub Changelog](https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/)
