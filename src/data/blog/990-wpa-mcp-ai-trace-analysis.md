---
pubDatetime: 2026-08-03T14:02:00+08:00
title: "WPA MCP 预览：用 AI 分析 Windows trace"
description: "Windows Performance Analyzer 集成 GitHub Copilot 的早期预览：自然语言提问 trace 分析，快速定位 CPU、延迟与瓶颈根因。目前仅支持 Copilot 订阅，附示例 prompt 与设置。"
tags: ["Windows", "Performance", "MCP", "AI Agents"]
slug: "wpa-mcp-ai-trace-analysis"
ogImage: "../../assets/990/01-cover.jpg"
source: "https://devblogs.microsoft.com/performance-diagnostics/introducing-wpa-mcp-early-preview-of-ai-assisted-trace-analysis-in-windows-performance-analyzer"
---

Windows Performance Analyzer（WPA）是理解 Windows 系统性能最强大的工具之一，工程师用它调查 Event Tracing for Windows（ETW）trace，覆盖 CPU、内存、磁盘、网络、调度、输入等系统领域。但强大伴随复杂：一条 trace 的数据量极大，要找到正确的信号，你得知道打开哪些表、哪些列有用、怎么过滤出正确的时间范围，还要把多条证据串起来定位根因——这套知识往往卡在少数专家手里。

微软正在开发 **WPA MCP**（Early Preview），目标就是把这条工作流变简单：把 GitHub Copilot CLI 带进 WPA 的 trace 分析流程，用自然语言提问代替手动翻图表。

## WPA MCP 是什么

WPA MCP 把 GitHub Copilot CLI 接入 WPA 的 trace 分析工作流。不用每次从手动浏览图表和表格开始，你可以用自然语言直接问 trace 相关的问题。WPA MCP 帮 Copilot 把意图翻译成 trace 数据探索，总结相关发现，并引导后续分析。

具体来说，GitHub Copilot 会根据 prompt 检查可用的 trace 数据、识别相关的表和信号，输出一份分析，帮你决定下一步看哪里。

## 为什么做这个

性能分析常常被专家知识卡住。熟练的 WPA 用户能快速行动，但新手和偶尔使用的用户往往不知道从哪开始；即便是专家，也要花不少时间跨视图关联活动才能得出有用结论。WPA MCP 想降低这个摩擦：

- 用自然语言问题开始调查
- 更快找到相关的 WPA 表、图和时间范围
- 识别高成本的 CPU 活动、调用栈、输入延迟、回归等症状
- 不重启调查就能继续追问
- 更快从 trace 探索走到可行动的结论

额外的好处是：如果 trace 里包含相同的上下文，它还能用于重复性的调查工作流。可以从 Microsoft Store 下载最新预览版 WPA 试用（[商店链接](https://apps.microsoft.com/detail/9N58QRW40DFW)）。

## 当前预览版支持范围

这个 Early Preview 目前**只支持 GitHub Copilot**，需要有效的 GitHub Copilot 订阅；其他 AI 助手、模型提供商和 MCP 客户端都不在支持范围内。因为是早期预览，用户体验、支持场景、设置要求和功能行为在正式发布前都可能变化。

## 工作方式

预览版的工作流把 GitHub Copilot CLI 嵌进 WPA，但不取代现有的分析体验：

1. 在 WPA 中打开一条 trace
2. 点击 WPA 窗口右上角的 GitHub Copilot 按钮
3. 在 Copilot 面板里提出 trace 分析问题
4. 审查生成的分析和支持信号
5. 用后续问题继续缩小调查范围

## 示例分析流

从一条描述详细的 prompt 开始效果最好：说清楚观察到的症状、受影响的时间范围、相关的用户或系统活动。这些上下文能帮 LLM 聚焦调查。官方示例 prompt：

> Analyze this trace and tell me why the machine was slow. Prioritize evidence that explains perceived slowness such as hangs, delayed input response, long ready times, CPU starvation, disk bottlenecks, memory pressure, paging, service contention, and problematic drivers. Use the trace to distinguish between system-wide bottlenecks and activity isolated to a single app or service and create a digestible report based on the insights you received from the trace.

拿到初始回复后，可以基于输出继续问更聚焦的问题：

- 哪些进程对延迟贡献最大？
- 受影响时间范围内，哪些调用栈最贵？
- 什么证据支持这个结论？/ 哪些表支持这个结论？
- 系统是 CPU 密集、卡在 I/O 上，还是在等别的资源？

需要强调的是，这个对话式工作流**不取代**对 trace 本身的检查。它的价值在于让你更快形成假设、找到相关证据、决定下一步聚焦哪里。更多示例见 [Microsoft Docs 文档](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpa-mcp-early-preview-july-2026)。另外，作为负责任 AI 的保障，MCP 可能会请求访问它生成的文本或 JSON 文件的权限。

## 新增设置

随 WPA MCP 一起发布了一组新设置，可以从 File 菜单或启动器画面进入：

**MCP server 部分**

- **Server status**：显示 WPA MCP 服务器的状态信息。
- **Start with WPA**：控制 WPA MCP 是否在 GitHub Copilot CLI 于 WPA 内启动时自动启动，默认开启。如果关闭，可以手动输入 `/MCP` 并从可用 MCP 服务器列表中选择 WPA-MCP。
- **MCP tools**：只读查看 WPA MCP 用来查询 trace 数据的工具列表。

**Copilot CLI 设置**

- **Play sound for Notifications**：GitHub Copilot CLI 不在焦点时播放通知声音。
- **Disabled MCP Server**：禁用 WPA 调查用不到的 MCP 服务器，减少 Copilot CLI 启动时间、降低上下文噪音。
- **Screen Reader Optimization**：与 GitHub Copilot CLI 中的屏幕阅读器优化设置保持一致。

## 关于 LLM 生成分析的重要提醒

WPA MCP 通过 GitHub Copilot 使用大语言模型能力。LLM 生成的响应可能因运行而异，也可能不完整或出错。官方明确建议：把 Copilot 输出当作**助手生成的起点，而不是最终诊断**。

采取行动之前，应该对照底层 WPA trace 数据验证结论：复查引用的表、图、时间范围、进程、线程和调用栈，证据不清楚时继续追问。

## 试用与反馈

Early Preview 的目标是搞清楚 AI 辅助在真实 WPA 调查中到底哪里最有价值。团队特别想收集这些反馈：prompt 质量、trace 分析准确性、有用的后续工作流、缺失的场景，以及 Copilot 应该在哪些地方暴露更多支持证据。反馈入口是 Copilot 按钮旁边的反馈按钮，或 Feedback Hub（WIN + F）下的 Settings > Start Menu。

## 适用边界

这篇文章的价值判断很明确：它适合已经会用 WPA 但想提速的人，以及被 WPA 门槛挡住的初学者；不适合把它当成自动诊断工具——LLM 输出必须人工对照 trace 验证。目前只支持 GitHub Copilot 订阅用户，其他 AI 客户端要等后续版本。相关背景可以看团队上个月发布的 [ETW MCP 介绍](https://devblogs.microsoft.com/performance-diagnostics/etw-mcp-intro/)（headless 的 ETL trace 分析），两条路线互补。

## 参考

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践，欢迎关注并留言你想看的主题。

- [Introducing WPA MCP: Early Preview（原文）](https://devblogs.microsoft.com/performance-diagnostics/introducing-wpa-mcp-early-preview-of-ai-assisted-trace-analysis-in-windows-performance-analyzer)
- [WPA MCP Early Preview 官方文档](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpa-mcp-early-preview-july-2026)
- [Microsoft Store 上的 WPA 预览版](https://apps.microsoft.com/detail/9N58QRW40DFW)
- [Introducing the ETW MCP: AI-assisted ETL trace analysis](https://devblogs.microsoft.com/performance-diagnostics/etw-mcp-intro/)
