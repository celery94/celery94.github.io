---
pubDatetime: 2026-03-31T09:40:00+08:00
title: "Coding Agent Explorer：用 .NET 工具看透 AI 编码代理的内部行为"
description: "AI 编码代理越来越普及，却对大多数开发者来说是个黑盒。Coding Agent Explorer 是一个开源 .NET 工具，作为反向代理坐落在 Claude Code 和 Anthropic API 之间，把每一次 API 调用、工具调用和上下文细节实时呈现在仪表盘上，让你真正看清代理在做什么。"
tags: ["Claude Code", "AI", "AgentDev", ".NET", "开源工具"]
slug: "introducing-coding-agent-explorer-dotnet"
ogImage: "../../assets/690/01-cover.png"
source: "https://nestenius.se/ai/introducing-the-coding-agent-explorer-net/"
---

AI 编码代理正在成为日常开发流程的一部分，但对于大多数开发者来说，它们仍然是个黑盒：你输入一条 Prompt，代码变化就神奇地出现了，中间发生了什么完全不透明。

[Coding Agent Explorer](https://github.com/tndata/CodingAgentExplorer) 是一个开源 .NET 工具，专门用来解决这个问题。它目前支持 Claude Code，作为反向代理坐落在 Claude Code 和 Anthropic API 之间，把每一条请求和响应都实时展示在一个 Web 仪表盘上，让你能看清代理的每一个决策。

这篇文章是 Coding Agent Explorer 系列的第一篇：

- Part 1 – Coding Agent Explorer 介绍（本文）
- [Part 2 – 用 Coding Agent Explorer 实时观察 Claude Code Hooks](https://nestenius.se/ai/exploring-claude-code-hooks-with-the-coding-agent-explorer-net/)
- Part 3 – 用 Coding Agent Explorer 可视化 MCP 请求（即将发布）

## 什么是 Agentic Development

在传统的 AI 辅助编码中，你可能会得到自动补全建议，或者向聊天机器人提问然后把答案复制进代码。Agentic development（代理式开发）走得更远。

代理会在你的开发环境中自主运行：读取文件、搜索代码库、执行命令、修改代码，甚至验证自己的修改。它不是在建议代码，而是代表你行动，在一个循环中完成多步任务：思考该做什么 → 执行动作 → 观察结果 → 决定下一步。

目前这个领域已经出现了一批工具：[Claude Code](https://code.claude.com/docs)、[GitHub Copilot](https://github.com/features/copilot)、[Cursor](https://cursor.com/)、[Windsurf](https://windsurf.com/)、[Lovable](https://lovable.dev/)……这些工具正在迅速改变开发者编写软件的方式。但代理越自主，就越有必要理解它实际上在做什么。

## 为什么要做这个工具

作者 Tore Nestenius 是一名讲师，长期为开发者提供技术培训。他的习惯是为每个复杂概念创建动手工具，帮助学员建立正确的心智模型，而不只是照着文档走一遍。这和他之前为讲解 Azure 而创建的 [CloudDebugger](https://github.com/tndata/CloudDebugger) 是同一思路。

AI 编码代理开始成为开发者日常工具后，他发现同样的需求出现了：代理的体验像魔法，背后的原理很难说清楚。他想要一个能让你"窥视黑盒"的工具：看到每一次 API 调用、每次工具调用、以及代理在每个时间点的决策。

## Coding Agent Explorer 是什么

Coding Agent Explorer 是一个 .NET **反向代理**加**实时 Web 仪表盘**的组合。它坐落在 Claude Code 和 Anthropic API 之间，拦截所有来回的请求和响应，并在仪表盘中实时展示。

技术栈：

- **.NET 10** 和 **ASP.NET Core**
- **[YARP](https://dotnet.github.io/yarp/index.html)**（Yet Another Reverse Proxy）负责代理层
- **[SignalR](https://learn.microsoft.com/en-us/aspnet/core/signalr/introduction)** 负责代理到仪表盘的实时通信
- 前端是纯 **HTML/JS/CSS**，无框架依赖，容易贡献

## 三种探索视图

仪表盘提供三个互补视图，从不同角度呈现同一份数据。

### HTTP Inspector

HTTP Inspector 是原始、详细的视图。它以表格形式展示每次 API 调用：时间戳、HTTP 方法、使用的模型、Token 数量、响应耗时。

点击任意一行可以查看完整细节：

- 请求和响应头（完整内容）
- 请求和响应体（格式化显示）
- 实时响应数据（可以看到代理收到的完整原始响应流）
- Token 用量明细：输入 Token、输出 Token、缓存创建 Token、缓存读取 Token
- 性能指标：总耗时和首 Token 延迟（TTFT）

这个视图在你想理解 API 通信技术细节时最有价值——代理发给模型的完整请求、模型返回了什么、每步耗时多久。

### Conversation View

Conversation View 将同样的 API 数据渲染成聊天式格式，更容易理解。你看到的不是原始 HTTP 流量，而是对话的展开过程：

- **系统 Prompt**：设定代理行为的完整指令集
- **用户消息**：你输入的 Prompt
- **助手响应**：代理的推理过程
- **工具调用**：Read、Write、Bash、Grep、Glob 等，以及每次调用的完整参数
- **工具结果**：每次调用的返回结果
- **MCP 工具使用**：代理如何向 LLM 呈现和调用 MCP 服务器

大段内容可以折叠，每条消息都附有 Token 和字符数统计，让你感受到对话的每个部分消耗了多少上下文。

这是作者在培训中使用最多的视图，因为它直接回答"代理在想什么"——如何拆解问题、选择哪些工具、如何迭代走向完成。

### MCP Observer

MCP Observer 会在后续博客文章中介绍，用于拦截和检查 Claude Code 与 MCP 服务器之间的流量。

## 能从中学到什么

有了对 API 调用的监控，你会发现很多从外部看不出来的东西：

**Prompt 是怎么构建的。** 你会看到 Claude Code 发给模型的真实系统 Prompt，内容远比你预期的详细——工具使用指令、安全规则、代码风格要求等。

**工具使用模式。** 你会看到模型如何选择和调用 Read、Write、Bash、Grep、Glob 等工具，如何在编辑前读取文件，如何搜索代码，如何验证自己的修改。

**Token 经济学。** 你会看到什么在消耗 Token，以及 Prompt 缓存是如何工作的——缓存创建 Token（模型存储 Prompt 前缀时）和缓存读取 Token（重用缓存前缀时），这对理解性能和成本至关重要。

**代理对话循环。** 你能看到代理和 API 的来回交互：模型生成响应（可能包含工具调用）→ 代理执行工具 → 把结果发回给模型 → 直到任务完成。

**多模型执行。** 观察任务如何在 Haiku 和 Opus 等模型之间分配。

**实时观察。** 整个对话在代理工作时实时展开。如果 Claude Code 有时"思考"一段时间才响应，Conversation View 会告诉你它在做什么：可能同时在读多个文件、搜索代码模式，或者在开始生成响应之前分析代码。

## 上手步骤

让 Coding Agent Explorer 跑起来只需几分钟（完整细节见 [GitHub README](https://github.com/tndata/CodingAgentExplorer)）。

**前置条件：** 需要安装 [.NET 10 SDK](https://dotnet.microsoft.com/en-us/download)。

### 第一步：克隆并运行

```bash
git clone https://github.com/tndata/CodingAgentExplorer.git
cd CodingAgentExplorer
dotnet run
```

这会启动三个端点：

- 反向代理：端口 `8888`
- Web 仪表盘：端口 `5000`（HTTP）和 `5001`（HTTPS）

仪表盘会在浏览器中自动打开。

### 第二步：把 Claude Code 指向代理

**Windows (cmd)：**
```cmd
set ANTHROPIC_BASE_URL=http://localhost:8888
```

**Windows (PowerShell)：**
```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8888"
```

仓库里还提供了 `EnableProxy.bat` 和 `DisableProxy.bat` 脚本方便使用。这些设置只影响当前终端会话，关闭终端就会自动清除。

### 第三步：正常使用 Claude Code

所有 API 调用都会流经代理，并实时出现在仪表盘中。

> **安全说明：** 代理只监听 localhost，不会暴露到网络。API Key（`x-api-key` 和 `Authorization` 头）会从存储的请求数据中自动脱敏。捕获的数据仅保存在内存中（最多 1000 条请求），不写入磁盘，应用停止后数据清空。

## FAQ

**支持 Claude Code 之外的编码代理吗？**  
暂时不支持。目前只支持通过 Anthropic API 使用的 Claude Code。其他代理的支持在路线图上，可以在 [GitHub Issues](https://github.com/tndata/CodingAgentExplorer/issues) 提建议。

**代理会影响 Claude Code 的性能吗？**  
影响极小。代理只是在流量通过时捕获数据，不会以有意义的方式修改或延迟请求和响应。

**我的 API Key 安全吗？**  
安全。API Key 会自动从所有存储的请求数据中脱敏。代理只监听 localhost，所有捕获数据仅在内存中保留，停止应用后消失。

**我需要修改自己的代码吗？**  
不需要。你只需要设置一个环境变量（`ANTHROPIC_BASE_URL`）把 Claude Code 指向代理。其他一切照常工作。

**可以用于生产环境吗？**  
不建议。Coding Agent Explorer 是开发和教学工具，不适合生产使用。在本地想学习、调试、或演示编码代理的工作原理时使用它。

## 参考

- [原文：Introducing the Coding Agent Explorer (.NET)](https://nestenius.se/ai/introducing-the-coding-agent-explorer-net/)
- [Coding Agent Explorer（GitHub）](https://github.com/tndata/CodingAgentExplorer)
- [Part 2 – 用 Coding Agent Explorer 实时观察 Claude Code Hooks](https://nestenius.se/ai/exploring-claude-code-hooks-with-the-coding-agent-explorer-net/)
- [.NET 10 SDK 下载](https://dotnet.microsoft.com/en-us/download)
- [YARP 文档](https://dotnet.github.io/yarp/index.html)
