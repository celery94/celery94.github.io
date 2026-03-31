---
pubDatetime: 2026-03-31T07:20:00+08:00
title: "在 Claude Code 里直接调用 OpenAI Codex：codex-plugin-cc 上手指南"
description: "OpenAI 官方发布了 codex-plugin-cc，让 Claude Code 用户在不离开当前终端的情况下直接调用 Codex 进行代码审查、任务委托和后台作业管理。本文梳理安装步骤和核心命令，帮你快速上手。"
tags: ["Claude Code", "OpenAI Codex", "AI工具", "代码审查", "开发工具"]
slug: "codex-plugin-for-claude-code"
ogImage: "../../assets/692/01-cover.png"
source: "https://github.com/openai/codex-plugin-cc"
---

OpenAI 在 2026 年 3 月底悄悄发布了一个官方插件仓库 [codex-plugin-cc](https://github.com/openai/codex-plugin-cc)，专门解决一个实际问题：如果你平时主要用 Claude Code 开发，但偶尔也想用 Codex 做代码审查或任务委托，之前就必须在两个工具之间来回切换。这个插件消除了这个摩擦点，让你直接在 Claude Code 的对话里触发 Codex 的能力。

截至发布时该仓库已有 851 个 star，是 OpenAI 的官方发布，值得关注。

![封面：OpenAI Codex 与 Claude Code 协作](../../assets/692/01-cover.png)

## 能做什么

安装插件后，Claude Code 里会多出以下斜杠命令：

| 命令 | 用途 |
|---|---|
| `/codex:review` | 对当前未提交变更或指定分支跑一次只读 Codex 代码审查 |
| `/codex:adversarial-review` | 可引导的"对抗式"审查，重点质疑设计和实现决策 |
| `/codex:rescue` | 把任务移交给 Codex 子 Agent，让它去研究 bug、尝试修复 |
| `/codex:status` | 查看当前仓库正在跑或最近完成的 Codex 作业 |
| `/codex:result` | 取回已完成作业的结果，附带 session ID |
| `/codex:cancel` | 取消后台运行的作业 |
| `/codex:setup` | 检查 Codex 是否已安装并登录 |

这些命令均支持 `--background` 参数，适合需要运行较长时间的代码审查或任务。

## 前置条件

在安装插件之前，确认以下几点：

- **ChatGPT 订阅**（含免费版）或 **OpenAI API key**。Codex 的用量会计入你的 Codex 配额，[定价文档](https://developers.openai.com/codex/pricing)有具体说明。
- **Node.js 18.18 或更高版本**。

## 安装步骤

### 第一步：添加插件市场

在 Claude Code 对话框中输入：

```
/plugin marketplace add openai/codex-plugin-cc
```

这一步告诉 Claude Code 去哪里找这个插件。

### 第二步：安装插件

```
/plugin install codex@openai-codex
```

### 第三步：重新加载插件

```
/reload-plugins
```

插件安装后需要重载才能生效。

### 第四步：检查环境

```
/codex:setup
```

`/codex:setup` 会检测 Codex CLI 是否安装、是否已登录。如果检测到 Codex 尚未安装但系统有 npm，它会提示你自动安装；如果已安装但未登录，它会提示你运行登录命令。

安装成功后，你应该能在 Claude Code 的 `/agents` 列表里看到 `codex:codex-rescue` 子 Agent。

### 可选：手动安装 Codex CLI

如果更倾向于自己安装 Codex，可以单独运行：

```bash
npm install -g @openai/codex
```

如果 Codex 已经安装但还没登录：

```bash
!codex login
```

`!` 前缀让 Claude Code 直接在 shell 里执行该命令。

## 核心命令详解

### /codex:review

对当前工作区的未提交变更，或者相对于某个基准分支的差异，运行一次 Codex 代码审查。效果和在 Codex 里直接跑 `/review` 等价。

```
/codex:review
/codex:review --base main
/codex:review --background
```

这是只读命令，不会修改代码。建议多文件变更时加 `--background`，避免等待。

### /codex:adversarial-review

在 `/codex:review` 的基础上加了"方向引导"的能力——审查时会主动质疑设计决策、权衡取舍和潜在假设。适合在上线前验证你的方案是否真的合理，而不只是代码细节对不对。

```
/codex:adversarial-review
/codex:adversarial-review --base main challenge whether this was the right caching and retry design
/codex:adversarial-review --background look for race conditions and question the chosen approach
```

同样是只读，不修改代码。

### /codex:rescue

把任务移交给 Codex 子 Agent 处理，适合：

- 排查为什么测试开始失败
- 让 Codex 尝试修一个 bug
- 继续上次的 Codex 任务
- 用成本更低的小模型跑一次快速诊断

```
/codex:rescue investigate why the tests started failing
/codex:rescue fix the failing test with the smallest safe patch
/codex:rescue --resume apply the top fix from the last run
/codex:rescue --model gpt-5.4-mini --effort medium investigate the flaky integration test
/codex:rescue --model spark fix the issue quickly
/codex:rescue --background investigate the regression
```

`spark` 是 `gpt-5.3-codex-spark` 的别名，速度更快。

如果省略 `--model` 和 `--effort`，Codex 会自行选择默认值。如果不加 `--resume` 或 `--fresh`，插件会询问是否继续当前仓库最近一次的 rescue 作业。

你也可以直接用自然语言描述任务，插件会理解：

```
Ask Codex to redesign the database connection to be more resilient.
```

### /codex:status 和 /codex:result

后台任务启动后，用这两个命令跟进进度：

```
/codex:status
/codex:result
/codex:result task-abc123
```

`/codex:result` 的输出里会包含 Codex session ID，你可以用 `codex resume <session-id>` 在 Codex 里直接打开那次会话，做进一步跟进或延续。

## 后台任务的典型用法

多文件审查和任务委托通常需要一些时间，推荐的工作流是：

```
/codex:adversarial-review --background
/codex:rescue --background investigate the flaky test
```

然后继续做自己的事，隔一段时间回来查结果：

```
/codex:status
/codex:result
```

## 可选功能：审查门控

`/codex:setup --enable-review-gate` 可以开启一个 Stop hook：Claude Code 在准备结束响应之前，会先触发一次 Codex 审查，如果发现问题就阻止 Claude 提交结果，让 Claude 先修完再说。

```
/codex:setup --enable-review-gate
/codex:setup --disable-review-gate
```

官方在文档里标注了警告：这个功能可能产生长时间的 Claude-Codex 调用循环，消耗配额很快。**只在你打算主动监控会话时开启**。

## 配置定制

插件底层使用的是本地 Codex CLI 和 [Codex app server](https://developers.openai.com/codex/app-server)，读取的也是你已有的 Codex 配置文件。如果你之前就在用 Codex，已有的配置、登录状态和 API key 会自动继承。

如果想为某个项目固定使用特定模型和推理强度，在项目根目录创建 `.codex/config.toml`：

```toml
model = "gpt-5.4-mini"
model_reasoning_effort = "xhigh"
```

用户级配置在 `~/.codex/config.toml`，项目级配置在 `.codex/config.toml`（需要该项目被标记为受信任才会加载）。

## 关于 Codex 账号

插件本身不引入独立的 Codex 账号体系，它透传的是你本地 Codex CLI 的认证状态。

- 已经在本机用过 Codex：直接可用，无需重新登录。
- 从未用过 Codex、只用 Claude Code：需要先跑 `/codex:setup` 确认状态，然后用 `!codex login` 登录 ChatGPT 账号或 OpenAI API key。

## 参考

- [openai/codex-plugin-cc on GitHub](https://github.com/openai/codex-plugin-cc)
- [Codex CLI 文档](https://developers.openai.com/codex/cli/)
- [Codex App Server](https://developers.openai.com/codex/app-server)
- [Codex 定价说明](https://developers.openai.com/codex/pricing)
- [Codex 配置参考](https://developers.openai.com/codex/config-reference)
