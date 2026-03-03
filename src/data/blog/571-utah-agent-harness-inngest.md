---
pubDatetime: 2026-03-03
title: "你的 AI Agent 需要的是 Harness，不是 Framework"
description: "Dan Farrelly 用 Inngest 构建了 Utah — 一个事件驱动的 Agent Harness，把 LLM 调用和工具执行变成可独立重试的步骤，解决了 Agent 开发中上下文管理、并发控制、可观测性等基础设施问题。本文是对这篇架构文章的深度解读。"
tags: ["AI", "Agent", "TypeScript", "Inngest"]
slug: "utah-agent-harness-inngest"
source: "https://x.com/djfarrelly/status/2028556984396452250"
---

在每个工程领域，harness 都指同一件事：把组件连接起来、保护它们、编排它们——但不做具体的工作本身。汽车线束把发动机、传感器和仪表板串联起来；测试 harness 让代码可重复、可观测；安全绳在你失足时接住你。

AI Agent 运行时需要同样的东西。LLM 是发动机，工具是外设，记忆是存储——但谁来把它们连接起来？当 LLM 在第五次迭代超时，谁来负责恢复？当两条消息并发到达，谁来防止碰撞？当 webhook 触发一个事件，谁来把它路由到正确的处理函数再发出正确的回复？

这就是 harness 要解决的问题。而几乎每个 Agent Framework 都在从头造轮子：自己的重试逻辑、自己的状态持久化、自己的任务队列、自己的事件路由。Dan Farrelly（Inngest）的判断是：这些问题已经被持久化事件驱动基础设施解决掉了，Agent 开发者不应该再解决一遍。

## 什么是 Utah

Utah 是 **Universally Triggered Agent Harness** 的缩写，一个 Telegram 和 Slack 上的对话 Agent，带工具、记忆、子 Agent 委派以及完整的持久化执行。代码量极少，没有框架依赖，只有 Inngest 函数、步骤和事件，围绕标准的 think → act → observe 循环。

"Universally Triggered"是关键。Telegram/Slack webhook、cron 调度、子 Agent 调用、函数间事件——Agent 本身不知道也不需要关心自己是怎么被触发的。触发源和工作解耦。今天加 Slack Bot，Agent 循环一行不改；harness 负责路由。

## 架构：事件驱动，解耦编排与执行

大多数 Agent 运行时把编排和执行混在一起。Utah 把它们分开：Telegram 或 Slack 的 webhook 打到 Inngest Cloud，一个 webhook transform 把原始 HTTP 载荷转换成有类型的 Inngest 事件；本地的 worker 拾取事件，运行 Agent 函数，然后触发一个独立的 reply 函数通过各自渠道的 API 发回响应。

Worker 通过 Inngest 的 `connect()` API 建立持久 WebSocket 连接，从本地机器（或 Mac Mini 或远程服务器）连到 Inngest Cloud，不需要公网端点。

## Agent 循环变成步骤

Utah 的 Agent 核心是 think → act → observe 循环。每次迭代调用 LLM，检查是否有工具调用，执行工具，把结果送回上下文。关键设计：**每次 LLM 调用和每次工具执行都是一个 Inngest step**。

```typescript
// 简化版——实际实现使用 pi-ai 的 provider-agnostic 类型
while (!done && iterations < config.loop.maxIterations) {
  iterations++;

  // 修剪旧工具结果，保持上下文聚焦
  pruneOldToolResults(messages);

  // 接近迭代上限时注入预算警告
  const messagesForLLM = addBudgetWarning(messages, iterations);

  // Think：调用 LLM
  const llmResponse = await step.run("think", async () => {
    return await callLLM(systemPrompt, messagesForLLM, tools);
  });

  const toolCalls = llmResponse.toolCalls;

  if (toolCalls.length > 0) {
    messages.push(llmResponse.message);

    // Act：把每个工具调用作为独立步骤执行
    for (const tc of toolCalls) {
      const result = await step.run(`tool-${tc.name}`, async () => {
        validateToolArguments(tool, tc);
        return await executeTool(tc.id, tc.name, tc.arguments);
      });
      // Observe：把结果送回消息列表
      messages.push(toolResultMessage(tc, result));
    }
  } else if (llmResponse.text) {
    // 没有工具调用——文本响应即最终回复
    finalResponse = llmResponse.text;
    done = true;
  }
}
```

Inngest 自动为重复步骤 ID 加编号。`step.run("think")` 被调用十次时，Inngest 内部记录为 `think:0`、`think:1`……不需要自己管理唯一 ID。每个步骤独立可重试：如果第三次迭代的 LLM API 返回 500，Inngest 只重试那个步骤——第一、二次迭代的结果已经持久化，不会重新执行。这是持久化执行（durable execution）在 Agent 循环上的经典应用。

## 复用现有工具，不要重新造

Utah 没有手搓文件 I/O 和 shell 执行，它直接引入 `pi-coding-agent`——来自 OpenClaw/Pi 生态、经过实战验证的工具实现：

- `read`、`write`、`edit`——支持图片、二进制检测和智能截断的文件操作（`edit` 工具在上下文窗口利用率上表现突出）
- `bash`——可配置超时和输出截断的 shell 执行
- `grep`、`find`、`ls`——遵守 `.gitignore` 的搜索和导航

Utah 在此基础上加了几个自定义工具：`remember`（把笔记持久化到每日日志）、`web_fetch`、`delegate_task`。

```typescript
import { createReadTool, createWriteTool, createBashTool /* ... */ } from "@mariozechner/pi-coding-agent";

const tools = [
  createReadTool(config.workspace.root),
  createWriteTool(config.workspace.root),
  createBashTool(config.workspace.root),
  // ...
];
```

AI Agent 的工具体系和其他软件一样：用现有库，用 Inngest step 包一层，完成。

## 六个函数，不是一个单体

Utah 不是一个做所有事的函数，而是六个通过事件通信的函数：

```typescript
const functions = [
  handleMessage,      // 主 Agent 循环
  sendReply,          // 向渠道发回响应
  acknowledgeMessage, // 打字指示器——消息到达时立即触发
  failureHandler,     // 跨函数的全局错误处理
  heartbeat,          // 周期性定时检查
  subAgent,           // 通过 step.invoke() 运行隔离子 Agent
];
```

这个分离很重要。打字指示器在消息到达时立即触发，不用等 Agent 循环。Reply 函数处理 Telegram/Slack 特定的格式化和错误处理（比如 LLM 生成了格式错误的 HTML 时降级到纯文本）。失败处理器捕获所有函数中的未处理错误并通知用户。

每个函数有自己的重试策略、并发控制和触发条件。如果想让子 Agent 或扇出工作流在循环过程中向用户发送进度更新，只需要从新工具里发 `sendReply` 事件即可。

## 子 Agent：step.invoke() 的自然用途

有时 Agent 需要执行一个大任务——重构文件、研究主题、写文档——这种任务大到会吹爆上下文窗口。对于在单线程对话（比如 Telegram）中运行的通用 Agent，跨越几天的长会话本来就有上下文积累问题。

Utah 的 `delegate_task` 工具：当主 Agent 调用它时，用 `step.invoke()` 启动一个完全独立的 Agent 函数运行。子 Agent 把当前会话上下文分叉到自己的子会话（有独立的会话 key）中，专注于一个任务并返回摘要：

```typescript
// 主 Agent 调用 delegate_task 时：
const subResult = await step.invoke("sub-agent", {
  function: subAgent,
  data: {
    task: tc.arguments.task,
    subSessionKey: `sub-${sessionKey}-${Date.now()}`,
  },
});
```

子 Agent 运行一个全新的 Agent 循环，有自己的上下文窗口，工具集相同（去掉 `delegate_task`，防止递归），返回摘要给父 Agent。父 Agent 看到的就是一个工具结果："这是我做的事情。"编排处理好了，不需要 Agent 间协议，函数调用函数就够了。

## 单例并发：一个对话，一次运行

每个"渠道"使用渠道专用的 session key 定义"对话"。对单线程渠道（比如 Telegram），是 chat ID；对支持线程的平台（比如 Slack），是渠道加线程。

如果一个对话中连续发来多条消息，你不想让第一个 Agent 循环还在跑、第二个循环又响应——你要让 Agent 拿到两条消息的上下文。Utah 的选择是取消当前循环、用完整上下文重启。配置只需一行：

```typescript
singleton: { key: "event.data.sessionKey", mode: "cancel" },
```

做了两件事：基于 sessionKey 的单例并发——每个聊天同时只有一个 Agent 运行，没有竞态，没有交错响应；新消息取消当前运行——用户在 Agent 还在处理时发来新消息，当前运行取消，新运行用最新消息启动。

传统方案：为每个用户建队列、管理锁、处理取消逻辑。Inngest 方案：一行配置。

## 踩过的坑

上下文管理才是真正的挑战。最难的问题不是调用 LLM，而是管理送进 LLM 的内容。Utah 使用的工具每次调用可能返回几千个字符，几次迭代之后上下文就膨胀了，模型开始迷失方向——出现过 Agent 不断调用工具、无法产出响应的情况。

Utah 的修复是两级上下文修剪：

```typescript
const PRUNING = {
  keepLastAssistantTurns: 3,
  softTrim: { maxChars: 4000, headChars: 1500, tailChars: 1500 },
  hardClear: { threshold: 50_000, placeholder: "[Tool result cleared]" },
};
```

旧工具结果会被软截断（保留头尾）或在总上下文过大时完全清空。最近三次迭代始终保留完整。

在此之上，还有针对整个会话的压缩机制——当估算的 token 数超过阈值时，在下次运行前先对对话历史做摘要。修剪处理单次运行内的上下文；压缩处理跨运行的积累。另外还加了预算警告（Agent 迭代次数不多时注入系统消息提示它收尾）和溢出恢复（LLM 返回上下文太大的错误时强制压缩消息并重试，不浪费一次迭代）。

LLM 多提供商支持也是一个收益。Utah 不直接调用 Anthropic SDK，使用 `pi-ai` 这个 provider-agnostic 的 LLM 抽象层，支持 Anthropic、OpenAI 和 Google。切换提供商只改配置：

```typescript
llm: {
  provider: "anthropic", // 或 "openai" 或 "google"
  model: "claude-sonnet-4-20250514",
},
```

## 下一步

Utah 现在是单人本地运行的 harness，但核心架构支持更多可能。接下来计划探索可插拔沙箱、外部状态和记忆，让 Utah 能在 serverless 上运行。还会基于 `step.waitForEvent()` 构建人在循环中的审批流。最终目标是让 Utah 能"写自己"——构建新的 Agent 和工作流、创建新的 webhook、通过 API 监控自身。

源码已作为参考实现发布在 GitHub：[https://github.com/inngest/utah](https://github.com/inngest/utah)

如果你在构建 AI Agent 时遇到了同样的墙——状态管理、重试、并发、可观测性——这套基础设施的原语可能早就存在了。

## 参考

- [原文](https://x.com/djfarrelly/status/2028556984396452250) — Dan Farrelly (@djfarrelly), Inngest
- [Utah GitHub 仓库](https://github.com/inngest/utah) — 源码参考实现
- [Inngest step.invoke() 文档](https://www.inngest.com/docs/guides/invoking-functions-directly?ref=x-utah-1)
- [Inngest 单例并发文档](https://www.inngest.com/docs/guides/singleton?ref=x-utah-1)
- [pi-coding-agent（@mariozechner）](https://github.com/badlogic/pi-mono) — 工具实现来源
