---
pubDatetime: 2026-03-27T14:30:00+08:00
title: "pi：一个可扩展的极简终端编程助手"
description: "pi（shittycodingagent.ai）是 Mario Zechner 开发的开源终端编程助手，支持 20 余个 AI 提供商，通过技能、扩展、提示模板和 Pi 包构建高度可定制的工作流，让 AI 编程工具真正适配你的开发习惯而不是反过来。"
tags: ["AI", "编程工具", "终端", "开源"]
slug: "pi-terminal-coding-agent"
ogImage: "../../assets/685/01-cover.png"
source: "https://shittycodingagent.ai/"
---

![pi 终端编程助手封面](../../assets/685/01-cover.png)

Mario Zechner 给自己的 AI 编程工具取了个域名叫 `shittycodingagent.ai`，页面上的第一句话是："There are many coding agents, but this one is mine."（有很多编程助手，但这个是我的。）

这种命名往往意味着作者对现有工具有明确的不满，然后做了一个他真正想要的东西。pi 就是这样——一个终端编程助手，核心设计原则是：让它适应你的工作流，而不是反过来。

GitHub 已有 28000+ Star，npm 包名是 `@mariozechner/pi-coding-agent`。

## 安装和快速开始

```bash
npm install -g @mariozechner/pi-coding-agent
```

认证方式有两种：使用 API Key 或直接通过订阅登录。

```bash
# 方式一：设置 API Key（以 Anthropic 为例）
export ANTHROPIC_API_KEY=sk-ant-...
pi

# 方式二：使用现有订阅登录
pi
/login  # 进入交互模式后选择提供商
```

启动后，pi 默认给模型提供四个工具：`read`、`write`、`edit`、`bash`，模型用这四个工具来完成你的请求。

## 支持的模型和提供商

pi 维护了一份所有支持工具调用的模型列表，随每个版本更新。支持的提供商覆盖面相当广：

**通过订阅认证：**
- Anthropic Claude Pro/Max
- OpenAI ChatGPT Plus/Pro（含 Codex）
- GitHub Copilot
- Google Gemini CLI

**通过 API Key：**
- Anthropic、OpenAI、Azure OpenAI、Google Gemini、Google Vertex、Amazon Bedrock  
- Mistral、Groq、Cerebras、xAI、OpenRouter
- 还有 Vercel AI Gateway、Hugging Face、Kimi For Coding 等

在交互模式里用 `/model`（或 Ctrl+L）随时切换，用 Ctrl+P / Shift+Ctrl+P 在预设的几个模型间循环切换。也可以在 `~/.pi/agent/models.json` 里添加自定义提供商，前提是它们支持 OpenAI、Anthropic 或 Google 兼容 API。

## 交互界面

启动后的界面分几个区域：顶部是启动信息（已加载的 AGENTS.md、提示模板、技能、扩展），中间是对话消息区，底部是编辑器和状态栏（显示工作目录、会话名、Token 用量、费用、当前模型）。

编辑器支持一些实用的快捷操作：

| 功能 | 操作 |
|------|------|
| 引用项目文件 | 输入 `@` 触发模糊搜索 |
| 路径补全 | Tab |
| 多行输入 | Shift+Enter（Windows Terminal 用 Ctrl+Enter）|
| 粘贴图片 | Ctrl+V（Windows 用 Alt+V）或直接拖到终端 |
| 运行命令并发给模型 | `!command` |
| 运行命令但不发给模型 | `!!command` |

在消息发送后、模型还在处理时，也可以继续输入：
- **Enter**：发送一个"引导消息"，在当前工具调用结束后立即送达
- **Alt+Enter**：发送"后续消息"，等模型完全完成所有工作后再送达

Shift+Tab 可以循环切换思考级别（off / minimal / low / medium / high）。

## 会话管理

会话自动保存到 `~/.pi/agent/sessions/`，按工作目录组织。

```bash
pi -c          # 继续最近的会话
pi -r          # 浏览历史会话并选择
pi --no-session  # 临时模式，不保存
```

**分支功能**是 pi 的亮点之一。按 Escape 两次（或输入 `/tree`）可以打开树形视图，看到完整的会话历史，选择任意一个节点继续，从那个点分叉出新的对话分支。所有历史都保存在同一个 JSONL 文件里，不会丢失。

**上下文压缩**（Compaction）用于处理长会话。手动压缩用 `/compact`，也可以开启自动压缩——上下文溢出时自动触发，或在接近上限时提前触发。压缩是有损的，但完整历史仍然保留在文件里，随时可以通过 `/tree` 回溯。

## 定制化体系

pi 有四种定制机制，这也是它区别于其他工具的核心：

### 技能（Skills）

遵循 [Agent Skills 标准](https://agentskills.io/) 的按需能力包。在交互模式里用 `/skill:name` 调用，或者让模型自动加载。

技能文件放在 `~/.pi/agent/skills/`、`.pi/skills/` 或 `.agents/skills/` 里，是 Markdown 文件，里面写给模型看的说明。

### 扩展（Extensions）

TypeScript 模块，可以给 pi 添加自定义工具、命令、键绑定、事件处理器、UI 组件。

```typescript
export default function (pi: ExtensionAPI) {
  pi.registerTool({ name: "deploy", ... });
  pi.registerCommand("stats", { ... });
  pi.on("tool_call", async (event, ctx) => { ... });
}
```

扩展能做的事情范围很广：子 Agent、自定义编辑器、SSH 执行、MCP 集成、Git 检查点、自动提交，甚至让 Doom 在等待时运行。没有内置的功能，都可以通过扩展自己做或安装第三方包来实现。

### 提示模板（Prompt Templates）

可复用的 Markdown 提示文件，在编辑器里输入 `/templatename` 展开：

```markdown
<!-- ~/.pi/agent/prompts/review.md -->
Review this code for bugs, security issues, and performance.
Focus on: {{focus}}
```

### Pi 包

把扩展、技能、提示模板、主题捆绑成一个包，通过 npm 或 git 分发：

```bash
pi install npm:@foo/pi-tools
pi install git:github.com/user/repo
pi list
pi update
```

在 [npmjs.com](https://www.npmjs.com/search?q=keywords%3Api-package) 上搜索 `pi-package` 关键词可以找到社区包。

## 几个有意思的设计决定

README 里有一节"Philosophy"，把几个刻意不做的东西列了出来：

- **不内置 MCP**：作者写了一篇[博客文章](https://mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/)解释理由，认为用 CLI 工具加 README（即技能）可以达到同样效果
- **不内置子 Agent**：用 tmux 启动多个 pi 实例，或者用扩展自己实现
- **不内置权限弹窗**：在容器里跑，或通过扩展实现你自己需要的权限确认流程
- **不内置计划模式**：把计划写到文件里，或者用扩展实现
- **不内置 Todo**：作者认为这会让模型困惑，用 TODO.md 文件就好

这种设计理念的核心假设是：每个团队和项目的工作流需求不同，通用的内置实现往往不合适，提供一套好用的扩展机制比堆功能更有价值。

## 程序化使用

除了交互模式，pi 还支持：

**打印模式**（非交互）：
```bash
pi -p "总结这个代码库"
cat README.md | pi -p "总结这段文字"
```

**SDK**：
```typescript
import { createAgentSession } from "@mariozechner/pi-coding-agent";

const { session } = await createAgentSession({ ... });
await session.prompt("当前目录有哪些文件？");
```

**RPC 模式**（用于非 Node.js 集成）：
```bash
pi --mode rpc
```
RPC 模式通过 stdin/stdout 通信，使用 LF 分隔的 JSONL 格式。

## 当前特别说明

如果你现在去 GitHub 提 Issue，会发现 Issue Tracker 暂时关闭了——作者宣布了一个"OSS Weekend"（开源周末），从 2026 年 3 月 27 日到 4 月 6 日，新 Issue 会被自动关闭，需要支持的话去 Discord 找。这段时间的关闭是为了让作者有时间专注开发。

## 参考

- [官方网站 shittycodingagent.ai](https://shittycodingagent.ai/)
- [GitHub 仓库 badlogic/pi-mono](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent)
- [npm 包 @mariozechner/pi-coding-agent](https://www.npmjs.com/package/@mariozechner/pi-coding-agent)
- [作者博客：为什么要做 pi](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/)
- [Discord 社区](https://discord.com/invite/3cU7Bz4UPx)
