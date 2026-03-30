---
pubDatetime: 2026-03-31T09:40:00+08:00
title: "用 Coding Agent Explorer 实时观察 Claude Code Hooks"
description: "Claude Code 的 Hook 系统让你可以在每个工具调用、文件读写、Shell 命令执行之前或之后插入自定义逻辑。本文介绍 Hook 是什么、能做什么，并用开源工具 Coding Agent Explorer 实时可视化 Hook 事件，帮你真正看清 AI 编码代理的内部行为。"
tags: ["Claude Code", "AI", "AgentDev", ".NET"]
slug: "exploring-claude-code-hooks-with-coding-agent-explorer"
ogImage: "../../assets/689/01-cover.png"
source: "https://nestenius.se/ai/exploring-claude-code-hooks-with-the-coding-agent-explorer-net/"
---

Claude Code 在工作时做了哪些事，默认对你是不可见的。它读了哪些文件、执行了哪些命令、请求了哪些权限，全部发生在黑盒子里。但 Claude Code 提供了一套 Hook 机制，让你可以在每个关键节点拦截和观测它的行为。

本文是 [Coding Agent Explorer](https://github.com/tndata/CodingAgentExplorer) 系列的第二篇，专注于 Claude Code 的 Hook 系统：Hook 是什么、能用来做什么，以及如何通过 HookAgent 工具把 Hook 事件实时推送到 Coding Agent Explorer 的仪表盘。

系列导航：

- Part 1 – [Introducing the Coding Agent Explorer (.NET)](https://nestenius.se/ai/introducing-the-coding-agent-explorer-net/)
- Part 2 – 用 Coding Agent Explorer 实时观察 Claude Code Hooks（本文）
- Part 3 – 用 Coding Agent Explorer 可视化 MCP 请求（即将发布）

下图展示了整体数据流：Claude Code 触发 Hook 事件，HookAgent 接收并转发，Coding Agent Explorer 仪表盘实时呈现。

![Claude Code Hooks 与 HookAgent 和 Coding Agent Explorer 的整体流程](https://nestenius.se/wp-content/uploads/2026/03/claude-code-hooks-hookagent-coding-agent-explorer-diagram.png)

## Claude Code Hooks 是什么

Hook 本质上是一条 Shell 命令，Claude Code 在特定时机调用它，并通过标准输入（stdin）传入一段描述事件的 JSON。这意味着你可以编写任意程序来接收这份数据，然后决定允许、阻止，或记录这次操作。

触发 Hook 的时机包括：

- 读取或写入文件
- 执行 Shell 命令
- 请求操作权限
- 会话开始或结束
- 用户提交 Prompt

## Hooks 能做什么

Hooks 让 Claude Code 从黑盒变成可观测、可控制、可扩展的系统。常见用途包括：

- 在工具执行前强制执行安全策略
- 记录并审计工具调用日志
- 触发外部自动化流程
- 向外部系统发送通知（Slack、CI 等）

简而言之，Hooks 让你从单纯观察代理行为，变成能够主动控制它如何运行。

## 示例：阻止访问敏感文件

最典型的用例是拦截 `PreToolUse` 事件，禁止代理访问不该碰的文件。

假设有一个 `Secret.key` 文件，你绝不希望 Claude Code 读到它。当代理尝试访问时，你的 `PreToolUse` Hook 会拦截请求，检查文件路径，如果命中敏感文件，就返回**非零退出码**并附带错误消息。Claude Code 会尊重这个响应，停止操作，继续下一步而不打开该文件。

当 Claude Code 尝试读取 `secret.key` 时，它通过 stdin 发送给 Hook 的 JSON 大概是这样：

```json
{
  "session_id": "9ec4714b-3475-4773-b4af-3f70d7fe68f7",
  "transcript_path": "C:\\Users\\Tore\\.claude\\projects\\C--Conf\\9ec4714b-3475-4773-b4af-3f70d7fe68f7.jsonl",
  "cwd": "C:\\MyApp",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Read",
  "tool_input": {
    "file_path": "C:\\MyApp\\Secret.key"
  },
  "tool_use_id": "toolu_01BQ4EQBtbxbFRoTEc1CXRgf"
}
```

## Hook 如何控制 Claude Code 的行为

Hook 不只是用于观察，它可以直接影响 Claude Code 被允许做什么。

Hook 运行结束后，它会返回一个退出码和一条可选消息，Claude Code 用这两项内容决定接下来的行动：

- **退出码 0**：允许操作继续
- **非零退出码**：阻止操作

那条可选消息同样重要。当操作被阻止时，消息会被传回 Claude Code，成为模型上下文的一部分。代理不会简单失败，而是收到可用于调整行为的反馈。换句话说，退出码负责执行决策，消息负责引导后续行为。

## 支持哪些 Hook 事件

Claude Code 提供四类可 Hook 的事件：

- **工具事件**：PreToolUse、PostToolUse、PostToolUseFailure……
- **会话事件**：SessionStart、SessionEnd、PreCompact……
- **子代理生命周期**：SubagentStart、SubagentStop、TaskCompleted……
- **用户交互**：UserPromptSubmit、Notification、PermissionRequest……

`PreToolUse` 和 `PostToolUse` 是实践中最有用的两个事件，它们在每次工具调用时触发，无论是文件读写、Bash 命令、Web 抓取还是 MCP 工具调用，覆盖了代理的全部行动。

## Hooks 对安全的意义

注册 `PreToolUse` Hook 后，你的代码会在每个工具执行**之前**运行，让你有机会检查、阻止或记录代理的每一次尝试。这是限制 Claude Code 与工具和文件交互方式的实用手段：

- 阻止读写敏感文件（证书、`.env` 文件、私钥、配置目录）
- 禁止特定 Shell 命令运行
- 定义代理被允许访问的清单

因为 Hook 运行在**你的环境中**，它在工具执行前必然被调用，不能仅凭 Prompt 操纵来绕过。Hooks 还提供了一定程度上对**提示注入攻击**的防御：如果一个恶意文件包含让 Claude Code 泄露数据的隐藏指令，`PreToolUse` Hook 可以在文件系统操作发生前就阻断它。

不过需要清楚：**Hooks 是防护层之一，不是唯一的安全边界**。它们应当与其他控制措施结合使用，在 Shell 访问开放的情况下尤其如此。

## 如何用 Coding Agent Explorer 实时观察 Hook 事件

这就是 [Coding Agent Explorer](https://github.com/tndata/CodingAgentExplorer) 和配套的 [HookAgent 工具](https://github.com/tndata/CodingAgentExplorer/tree/main/HookAgent) 的用武之地。

### HookAgent 是什么

HookAgent 是一个随 Coding Agent Explorer 附带的小型 CLI 工具，充当 Claude Code Hook 系统与 Coding Agent Explorer 仪表盘之间的桥梁。

它的核心职责很简单：

1. 从 stdin 读取传入的 Hook 事件
2. 附加 Claude Code 的环境变量（如 `CLAUDE_PROJECT_DIR`、`CLAUDE_SESSION_ID`）
3. 通过单次 HTTP POST 请求，把一切转发给 Coding Agent Explorer

如果 Explorer 没有运行，HookAgent 立即退出，Claude Code 继续正常工作。可观测性始终是可选的。

## 上手步骤

整个配置过程大约五分钟。

### 前置条件

- [.NET 10 SDK](https://dot.net/) 已安装
- [Coding Agent Explorer](https://github.com/tndata/CodingAgentExplorer) 源码已下载
- Claude Code 已安装

详细的安装和初始配置方法，请参考 [Introducing the Coding Agent Explorer](https://nestenius.se/ai/introducing-the-coding-agent-explorer-net/)。

### 第一步：编译 HookAgent

在 Coding Agent Explorer 根目录打开终端，运行对应平台的发布脚本：

**Windows：**
```
publish.bat
```

**macOS / Linux：**
```bash
bash publish.sh
```

脚本会把 Coding Agent Explorer 和 HookAgent 一起编译到 `Published` 文件夹：

```
Published/CodingAgentExplorer      ← 代理与仪表盘
Published/HookAgent/HookAgent.exe  ← HookAgent（Windows 为 .exe，macOS/Linux 无扩展名）
```

### 第二步：创建工作目录

创建一个新文件夹用于运行 Claude（本例命名为 `MyApp`），然后把 `Published` 中的 `HookAgent` 文件夹复制进去：

**Windows：**
```
C:\MyApp\HookAgent\HookAgent.exe
```

**macOS / Linux：**
```
~/MyApp/HookAgent/HookAgent
```

### 第三步：配置 Claude Code Hooks

Coding Agent Explorer 为每个平台都提供了现成的 `settings.json` 示例文件。

在工作目录（`MyApp`）中创建 `.claude` 文件夹（如果不存在），然后将对应平台的示例文件复制进去：

- **Windows：**`HookAgent\Sample-Settings-Windows\settings.json`
- **macOS / Linux：**`HookAgent/Sample-Settings-LinuxMacOS/settings.json`

目录结构最终应如下：

**Windows：**
```
C:\MyApp\
    HookAgent\HookAgent.exe
    .claude\settings.json
```

**macOS / Linux：**
```
~/MyApp/
    HookAgent/HookAgent
    .claude/settings.json
```

这会把 HookAgent 注册为所有 Claude Code Hook 事件的处理程序。你可以删掉不需要的事件。完整的事件列表和 `settings.json` 语法见 [Claude Code hooks 参考文档](https://code.claude.com/docs/en/hooks)。

`settings.json` 中的 `"matcher": ".*"` 是一个正则表达式，匹配工具名称。`.*` 匹配所有工具，Hook 会对该事件下的每次工具调用触发。你也可以缩小范围，例如 `"matcher": "Bash"` 只在 Bash 工具调用时触发。

> **注意：** Claude Code 在所有平台（包括 Windows）都通过 bash 运行 Hook 命令。命令路径始终使用正斜杠。Windows 示例用 `HookAgent/HookAgent.exe`，macOS/Linux 示例用 `HookAgent/HookAgent`。

### 第四步：验证 Hooks 是否注册成功

从工作目录启动 Claude Code，运行 `/hooks` 命令：

```
/hooks
```

Claude Code 会列出所有已配置的 Hook 事件及其对应命令。你应该能看到所有事件都指向 HookAgent。如果列表为空或有缺失，检查 `.claude/settings.json` 是否在正确的目录，以及 JSON 格式是否有效。

确认 Hooks 注册成功后，退出 Claude Code，继续下一步。

### 第五步：启动 Coding Agent Explorer

从 Coding Agent Explorer 文件夹启动：

```
dotnet run
```

Windows 上浏览器会自动打开。macOS 和 Linux 上需要手动打开 `https://localhost:5001`。

别忘了按照上一篇文章的说明在 Claude Code 中启用代理。

### 第六步：测试 HookAgent

Explorer 运行后，在正式启动 Claude Code 会话之前，先手动测试 HookAgent：

**Windows (PowerShell)：**
```powershell
'{"hook_event_name":"UserPromptSubmit","session_id":"test"}' | HookAgent\HookAgent.exe
```

**Windows (cmd)：**
```cmd
echo {"hook_event_name":"UserPromptSubmit","session_id":"test"} | HookAgent\HookAgent.exe
```

**macOS / Linux：**
```bash
echo '{"hook_event_name":"UserPromptSubmit","session_id":"test"}' | HookAgent/HookAgent
```

如果配置正确，一个 `UserPromptSubmit` 事件应该立即出现在仪表盘的 Conversation View 中。记得勾选 Conversation View 里的 "Hook Events" 复选框，否则 Hook 事件会被隐藏。

### 第七步：运行 Claude

从工作目录启动 Claude Code：

```
claude
```

Hook 事件会从启动那一刻开始持续出现在 Conversation View 中，记录 Claude Code 的每一步行动。

## 实时观察 Hook 事件的效果

一切就绪后，Conversation View 变成一条实时时间线，Hook 事件和 API 调用交织呈现。你能看到:清完整画面，而不只是 API 请求。

以下是修复一个 bug 时的典型时间线：

```
13:42:01  SessionStart
13:42:03  UserPromptSubmit "Fix the null reference exception in UserService.cs"
13:42:03  POST /v1/messages  (Claude 思考应对策略)
13:42:05  PreToolUse Read   (即将读取 UserService.cs)
13:42:05  PostToolUse Read  (文件内容已返回)
13:42:05  POST /v1/messages  (Claude 分析代码)
13:42:08  PreToolUse Edit   (即将写入修复内容)
13:42:08  PostToolUse Edit  (文件已更新)
13:42:08  POST /v1/messages  (Claude 确认修复完成)
13:42:10  Stop
```

不到 10 秒，Claude Code 发起了 3 次 LLM 请求和 2 次工具调用。没有 Hooks，你只能看到 API 请求；有了 Hooks，你看到的是完整故事。

点击时间线上的任意 Hook 事件，可以展开完整的 JSON 载荷，例如：

```json
{
  "session_id": "814cc648-5d90-44e2-9239-144ad62abc76",
  "transcript_path": "C:\\Users\\Tore\\.claude\\projects\\C--Conf\\814cc648-5d90-44e2-9239-144ad62abc76.jsonl",
  "cwd": "C:\\Conf",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Glob",
  "tool_input": {
    "pattern": "**/UserService.cs"
  },
  "tool_use_id": "toolu_019GP34HeFh8N4QkWQWdAyUA"
}
```

## Hook 事件完整参考

截至目前，Claude Code 支持以下 Hook 事件。完整的最新参考见 [Claude Code hooks 官方文档](https://code.claude.com/docs/en/hooks)。

| 事件 | 触发时机 |
|---|---|
| `SessionStart` | 会话开始或恢复 |
| `UserPromptSubmit` | 用户提交 Prompt |
| `PreToolUse` | 任意工具执行前 |
| `PostToolUse` | 工具执行成功后 |
| `PostToolUseFailure` | 工具执行失败后 |
| `PermissionRequest` | Claude Code 请求权限时 |
| `Stop` | Claude 完成响应 |
| `SubagentStart` | 子代理启动 |
| `SubagentStop` | 子代理完成执行 |
| `Notification` | Claude Code 发送通知 |
| `PreCompact` | 上下文压缩前 |
| `ConfigChange` | 设置文件发生变化 |
| `TeammateIdle` | 代理团队协作事件 |
| `TaskCompleted` | 任务标记为完成 |
| `SessionEnd` | 会话终止 |

`PreToolUse` 和 `PostToolUse` 是实践中覆盖面最广的两个事件：

- **`PreToolUse`**：在这里执行规则——阻止访问敏感文件、拒绝危险 Shell 命令、记录代理即将执行的行动
- **`PostToolUse`**：在这里响应结果——工具成功后触发，工具失败时 `PostToolUseFailure` 触发，并提供错误详情

常见用途：文件修改后自动运行测试、写入后触发 Lint 或格式化、记录操作到审计日志、通知 Slack 或 CI 流水线。

## Hooks 的安全边界说明

`PreToolUse` 能阻止**直接**工具调用（如读取 `secret.key`），但不能提供真正的沙箱。

模型可能通过以下方式绕过：

- 生成脚本（如 Bash 或 PowerShell）间接读取文件
- 请求访问更广泛的目录
- 使用其他工具或工作流绕过特定路径检查

而且，朴素的路径检查（简单字符串匹配）可能被路径变体、编码或路径遍历模式绕过，实际使用时需要对输入进行规范化和严格校验。

如果需要强保障，应配合环境级别的控制：

- 在容器、虚拟机或受限工作区中运行 Claude Code
- 限制文件系统权限，仅暴露允许的目录
- 禁用或严格限制 Shell 访问
- 使用允许列表而非阻止列表

**Hooks 最适合定位为告警和可观测性层，不是主要的安全边界。**

## 下一步

本系列下一篇将介绍 **MCP Observer**：一个新功能，用于拦截和检查 Claude Code 与任意 Model Context Protocol (MCP) 服务器之间的流量。如果你想了解 `Microsoft Learn` 或 `Context7` 等 MCP 工具在 Claude Code 使用时底层究竟在做什么，那篇文章正是为你准备的。

完整项目开源，地址：[github.com/tndata/CodingAgentExplorer](https://github.com/tndata/CodingAgentExplorer)。

## 参考

- [原文：Exploring Claude Code Hooks with the Coding Agent Explorer (.NET)](https://nestenius.se/ai/exploring-claude-code-hooks-with-the-coding-agent-explorer-net/)
- [Coding Agent Explorer（GitHub）](https://github.com/tndata/CodingAgentExplorer)
- [HookAgent 工具](https://github.com/tndata/CodingAgentExplorer/tree/main/HookAgent)
- [Claude Code hooks 官方文档](https://code.claude.com/docs/en/hooks)
- [Part 1 – Introducing the Coding Agent Explorer (.NET)](https://nestenius.se/ai/introducing-the-coding-agent-explorer-net/)
