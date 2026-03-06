---
pubDatetime: 2026-03-04
title: "GitHub Copilot CLI 使用全览：把终端变成真正的编程代理"
description: "GitHub 官方文档把 Copilot CLI 的关键工作流讲清楚了：信任目录、工具审批、Plan mode、内置 Agent、自定义指令、MCP 与上下文管理。这篇文章把这些能力翻成开发者真正会用的操作手册。"
tags: ["GitHub Copilot", "CLI", "Agent", "Developer Productivity"]
slug: "github-copilot-cli-agents-overview"
source: "https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-agents/overview"
---

很多人第一次运行 `copilot`，盯着终端里那句“是否信任当前目录”，会先停一下。这个停顿很正常。GitHub Copilot CLI 不是只会聊天的命令行助手，它会读文件、改文件、跑命令，必要时还会把工作拆给别的 agent。你把它当成终端版聊天窗口，很容易误判它；把它当成一个带安全闸门的编程代理，很多设计一下就说得通了。

GitHub 官方这篇文档在 2026 年 3 月 4 日有更新，重点不是宣传安装方式，而是回答一个更实际的问题：进入 Copilot CLI 之后，怎样才能既高效又不失控地工作。Copilot CLI 目前覆盖所有 Copilot 计划；如果你的资格来自组织分配，管理员还得先在组织设置里启用对应策略。

## 第一次启动，边界先讲明白

进入一个包含代码的目录后，直接运行 `copilot`，CLI 会先确认你是否信任当前文件夹。这一步很关键，因为从这一刻开始，Copilot 就可能在这个目录及其子目录里读取、修改甚至执行内容。

这套信任模型给了你三种强度不同的选择：

| 选项 | 含义 | 适合什么情况 |
| --- | --- | --- |
| `Yes, proceed` | 只在当前会话信任这个目录 | 临时试用、陌生仓库 |
| `Yes, and remember this folder for future sessions` | 后续进入该目录不再重复询问 | 你长期维护、完全信任的仓库 |
| `No, exit (Esc)` | 直接结束当前会话 | 目录来源不明，或你还没审过内容 |

> 终端里的代理能力，价值和风险是一体两面。目录信任这一步，不是打扰，是护栏。

如果你还没有登录 GitHub，CLI 会提示你执行 `/login`。完成认证之后，就可以直接输入自然语言请求，问问题也行，修 bug、加功能、搭一个新项目也行。

## 真正的门槛，不在提示词，在审批模型

Copilot CLI 真正和普通命令行聊天工具拉开距离的地方，是它会尝试调用工具。只要动作可能修改文件或执行命令，比如 `chmod`、`sed`、`node` 这类操作，它就会停下来向你申请权限。

这里有三个选项。你可以只批准这一次，也可以批准这个工具在当前会话中后续都不再询问，还可以直接拒绝。GitHub 文档专门拿 `rm` 举例，不是吓人，而是提醒你别把“省一次确认”理解成“没有代价”。一旦把危险命令整场放行，CLI 的行动边界就真的打开了。

拒绝也不是死路。你可以在拒绝后直接补一句新的要求，让 Copilot 换条路继续做。官方给的例子很实用：

```text
Continue the previous task but include usage instructions in the script
```

这就是 Copilot CLI 的工作方式。它不是一台只会机械执行命令的自动机，而是会在约束里继续协商的代理。

## 顺手程度，取决于你会不会这几组动作

Plan mode（规划模式）很值得早点养成习惯。按 `Shift+Tab` 就能在执行模式和规划模式之间切换，先让 Copilot 给出实现方案，再决定要不要真正动代码。你只要做过几次跨文件改动，就会知道这一步有多省返工。

如果 Copilot 还在 “Thinking”，你已经发现方向不对，按 `Esc` 立刻打断。终端代理最怕的不是慢，而是你明知道它偏了，还放任它继续跑。

给提示补上下文也很直接。输入 `@` 加相对路径，比如 `Explain @config/ci/ci-required-checks.yml` 或 `Fix the bug in @src/app.js`，CLI 会把目标文件内容带进当前提示。路径输入过程中还会给自动补全，方向键选中，`Tab` 补齐。

当任务需要动到当前目录外的文件时，你可以手动扩展信任范围，或者直接切换工作目录：

```shell
/add-dir /path/to/directory
/cwd /path/to/directory
```

有些时候你根本不需要模型推理，只想借着 Copilot 的界面顺手跑个命令。这时在输入前加 `!` 就够了：

```shell
!git clone https://github.com/github/copilot-cli
```

会话恢复也做得很像一个真正长期可用的工作台。你可以用 `--resume` 或 `/resume` 重新接回旧会话；如果只想快速回到最近一次本地会话，直接运行：

```shell
copilot --continue
```

## 指令、Agent 和技能，终于接上了

Copilot CLI 不只是一个单体 agent，它开始形成一套可以分工的工作模型。文档里列出的默认内置 agent 有四个，每个都对应很清晰的职责。

| Agent | 适合处理什么 |
| --- | --- |
| `Explore` | 快速分析代码库，回答结构和实现问题，不污染主上下文 |
| `Task` | 跑测试、跑构建、执行命令，成功时给摘要，失败时给完整输出 |
| `General-purpose` | 复杂多步骤任务，使用完整工具集单独开上下文处理 |
| `Code-review` | 对变更做低噪声审查，只抓真正的问题 |

模型可以自己决定要不要把任务委派给这些子 agent，你也可以手动点名。最直接的三种入口是 `/agent`、在提示里明确说 “use the refactoring agent”，或者直接在命令行里指定：

```shell
copilot --agent=refactor-agent --prompt "Refactor this code block"
```

自定义 agent 也不是纸上谈兵。GitHub 把作用域分成三层：用户级放在 `~/.copilot/agents`，仓库级放在 `.github/agents`，组织或企业级放在 `.github-private` 仓库里的 `/agents`。命名冲突时，系统级覆盖仓库级，仓库级再覆盖组织级。

和 agent 一起工作的，还有 custom instructions（自定义指令）与 skills（技能）。自定义指令支持三种载体：仓库级 `.github/copilot-instructions.md`、路径级 `.github/instructions/**/*.instructions.md`，以及 `AGENTS.md` 这类面向代理的说明文件。技能则更像面向特定任务的增强包，可以把说明、脚本和资源绑在一起，让 Copilot 对某类工作形成稳定套路。

## MCP 和上下文管理，开始变成日常操作

GitHub 给 Copilot CLI 预装了 GitHub MCP server，这样你在终端里就能直接碰 GitHub.com 上的资源。要继续扩展能力，直接运行 `/mcp add`，填完信息后按 `Ctrl+S` 保存。配置默认落在 `~/.copilot/mcp-config.json`，如果你改了 `XDG_CONFIG_HOME`，位置也会跟着变。

上下文管理同样不再是隐藏能力。`/usage` 用来看高级请求、会话时长、编辑代码行数和模型 token 分布；`/context` 负责展示当前上下文占用；`/compact` 用来手动压缩历史。更关键的是，Copilot CLI 会在上下文逼近 95% 时自动后台压缩，不打断当前工作流。

这类设计很实在。大家嘴上都说自己想要“长记忆”，真正把 CLI 用起来以后，最先遇到的问题其实是上下文窗口怎么别炸掉。

## 什么时候该放权，什么时候别碰 `--yolo`

官方文档提到 `--allow-all` 和 `--yolo`，本质上都是一次性打开所有权限。这当然很爽，尤其是在你完全信任目录、任务目标也很清楚的时候。但只要仓库稍微复杂一点，或者你还没想好边界，这两个选项就不该成为默认启动姿势。

同一组文档里还有一个很实用的小开关：`Ctrl+T`。它可以切换推理过程的可见性，而且设置会跨会话保留。复杂任务里，看看模型此刻在想什么，往往比盯着终端发呆更有价值。

真要查命令细节，也不必到处翻网页。CLI 自己就带入口：

```shell
copilot help
copilot help config
copilot help environment
copilot help logging
copilot help permissions
```

如果你已经习惯在编辑器里和 Copilot 对话，CLI 版本带来的不是“同一个聊天框换到终端里”，而是一套更像同事的协作模型。先把受信目录、Plan mode 和 `@文件` 用顺，再把 `/agent`、`/mcp add`、`/compact` 纳入日常节奏，终端就会开始像一个真正能干活的编程台。变化很明显。

## 参考

- [原文](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-agents/overview) — GitHub Docs
- [About GitHub Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli) — Copilot CLI 的定位、信任目录与工作方式
- [Installing GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli) — 安装方式与前置条件
- [Adding custom instructions for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/add-custom-instructions) — 自定义指令文件的组织方式
- [GitHub Copilot CLI command reference](https://docs.github.com/en/copilot/reference/cli-command-reference) — 命令行选项与 slash commands
- [Best practices for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices) — 日常使用建议
