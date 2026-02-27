---
pubDatetime: 2026-02-26
title: "GitHub Copilot SDK for .NET：把 Copilot 的 AI 能力直接嵌入你的 C# 应用"
description: "GitHub Copilot SDK for .NET 以技术预览形式发布，将 Copilot 的 Agent 运行时暴露为原生 .NET 库。本文覆盖核心架构、流式响应、工具调用、多模型路由以及与 Semantic Kernel 的对比。"
tags: [".NET", "GitHub Copilot", "AI", "C#"]
slug: "github-copilot-sdk-for-dotnet"
source: "https://www.devleader.ca/2026/02/26/github-copilot-sdk-for-net-complete-developer-guide"
---

![GitHub Copilot SDK for .NET 指南](../../assets/560/01-github-copilot-sdk-dotnet-guide.webp)

如果你正在写 .NET 应用，又想直接调用驱动 GitHub Copilot 的同一套 AI 引擎，GitHub Copilot SDK for .NET 值得关注。2026 年初以技术预览身份发布的这个 SDK，把 Copilot 完整的 Agent 能力暴露了出来：多轮对话、流式输出、工具调用、多模型路由，全部封装为一等公民级别的 .NET 库，可以直接嵌入你自己的应用。

## GitHub Copilot SDK for .NET 是什么

NuGet 包名 [GitHub.Copilot.SDK](https://www.nuget.org/packages/GitHub.Copilot.SDK/)，这是一个跨平台 SDK，把 GitHub Copilot CLI 的 Agent 运行时开放给了应用开发者。你不再只能通过 IDE 插件使用 Copilot，而是可以把它的智能直接嵌入 .NET 控制台应用、ASP.NET Core API、后台服务或者 CLI 工具。

截至 2026 年 2 月，最新版本是 v0.1.25。SDK 源码和文档在官方 [GitHub 仓库](https://github.com/github/copilot-sdk)，入门指南在 [docs/getting-started.md](https://github.com/github/copilot-sdk/blob/main/docs/getting-started.md)。

它提供的核心能力包括：

- **多轮对话**：有状态的会话，跨轮次完整管理上下文
- **流式响应**：通过 `AssistantMessageDeltaEvent` 实时推送 token，实现低延迟的用户体验
- **工具调用**：使用 `Microsoft.Extensions.AI` 的 `AIFunctionFactory` 将 C# 方法注册为 AI 工具
- **多模型路由**：每个会话可以单独选择 GPT-5、Claude Sonnet 或其他模型
- **Microsoft Agent Framework 集成**：SDK 会话可以和 Microsoft Agent Framework 协同工作（集成模式仍在演进中，具体看 [SDK 仓库](https://github.com/github/copilot-sdk/tree/main/dotnet) 的最新更新）
- **会话钩子**：生命周期事件，用于监控、日志和流程控制

这不是简单地包了一层 REST API。它跑的是 Copilot CLI 同款的生产运行时，经过 Agent 式多步 AI 工作流的实战检验。

## 环境准备和安装

使用 GitHub Copilot SDK for .NET 需要满足以下条件：

- **.NET 8.0 或更高版本**
- **GitHub Copilot CLI**：已安装并完成认证（[安装指南](https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line/installing-github-copilot-in-the-cli)）
- **GitHub Copilot 订阅**：个人版、团队版或企业版均可

安装 SDK NuGet 包：

```bash
dotnet add package GitHub.Copilot.SDK
```

如果要使用工具调用功能（推荐一起装）：

```bash
dotnet add package Microsoft.Extensions.AI
```

Copilot CLI 充当本地的 Agent 宿主，SDK 与它通信。这种设计意味着 API 密钥和认证由 GitHub CLI 管理，不需要存储在你的应用代码里，安全性上是一个明显优势。

## 核心架构：CopilotClient 与 CopilotSession

SDK 围绕两个核心类构建，每个应用都会用到它们。

### CopilotClient

`CopilotClient` 管理与 Copilot CLI Agent 宿主的连接，负责启动、认证以及底层进程的生命周期。它实现了 `IAsyncDisposable`，所以应该搭配 `await using` 使用：

```csharp
using GitHub.Copilot.SDK;

await using var client = new CopilotClient();
await client.StartAsync();

Console.WriteLine("Connected to GitHub Copilot CLI agent");
```

客户端启动 Copilot CLI 进程并建立本地连接。如果需要自定义 CLI 路径或端口，可以传入 `CopilotClientOptions`。

### CopilotSession

`CopilotSession` 代表一次对话。每个 Session 拥有自己的模型配置、工具注册和对话历史。同样实现了 `IAsyncDisposable`：

```csharp
await using var session = await client.CreateSessionAsync(new SessionConfig
{
    Model = "gpt-5"  // 也可以用 "claude-sonnet-4.5"、"gpt-4.1" 等
});
```

同一个 Client 可以并发运行多个 Session，这为多 Agent 模式提供了基础，每个 Agent 拥有自己隔离的上下文。

### 发送消息

通过事件驱动的 API 发送消息并收集响应：

```csharp
var tcs = new TaskCompletionSource();
var responseBuilder = new System.Text.StringBuilder();

session.On(evt =>
{
    switch (evt)
    {
        case AssistantMessageEvent msg:
            responseBuilder.Append(msg.Data.Content);
            break;
        case SessionIdleEvent:
            tcs.TrySetResult();
            break;
        case SessionErrorEvent err:
            Console.WriteLine($"Error: {err.Data.Message}");
            tcs.TrySetException(new Exception(err.Data.Message));
            break;
    }
});

await session.SendAsync(new MessageOptions
{
    Prompt = "Explain what the GitHub Copilot SDK does in one paragraph."
});

await tcs.Task;
Console.WriteLine(responseBuilder.ToString());
```

## 实时流式响应

SDK 最吸引人的能力之一是实时流式输出。你不用等完整响应返回，而是可以在 token 到达时逐个显示，体验和 VS Code 里的 Copilot 聊天一模一样。

流式输出通过 `AssistantMessageDeltaEvent` 实现，每个 token 分块到达时触发：

```csharp
await using var client = new CopilotClient();
await client.StartAsync();

await using var session = await client.CreateSessionAsync(new SessionConfig
{
    Model = "gpt-5",
    Streaming = true
});

var tcs = new TaskCompletionSource();

session.On(evt =>
{
    switch (evt)
    {
        case AssistantMessageDeltaEvent delta:
            // 逐个 token 输出，不换行
            Console.Write(delta.Data.DeltaContent);
            break;
        case SessionIdleEvent:
            Console.WriteLine(); // 完整响应后换行
            tcs.TrySetResult();
            break;
        case SessionErrorEvent err:
            tcs.TrySetException(new Exception(err.Data.Message));
            break;
    }
});

await session.SendAsync(new MessageOptions
{
    Prompt = "Write a C# method that calculates the Fibonacci sequence."
});

await tcs.Task;
```

这种流式模式适用于任何需要响应速度的场景：Web 聊天界面、CLI 工具、终端应用，显示部分响应而不是让用户干等的体验差距非常大。

## 用 AIFunctionFactory 注册自定义 AI 工具

SDK 通过 `Microsoft.Extensions.AI` 来处理工具注册。这和 Semantic Kernel 以及其他 .NET AI 库用的是同一套工具抽象，你写的工具可以在不同 AI 框架之间复用。

`AIFunctionFactory.Create()` 把任意 C# 方法包装成 AI 可调用的函数：

```csharp
using Microsoft.Extensions.AI;
using GitHub.Copilot.SDK;

// 普通的 C# 方法就是工具
string GetCurrentTime() => DateTime.UtcNow.ToString("O");

async Task<string> SearchDocumentationAsync(string query)
{
    // 生产环境中调用真实的搜索 API
    await Task.Delay(50);
    return $"Found 3 results for '{query}' in the documentation.";
}

// 把工具注册到 Session
var tools = new[]
{
    AIFunctionFactory.Create(GetCurrentTime, "get_current_time",
        "Returns the current UTC time"),
    AIFunctionFactory.Create(SearchDocumentationAsync, "search_docs",
        "Searches the documentation for a given query")
};

await using var session = await client.CreateSessionAsync(new SessionConfig
{
    Model = "gpt-5",
    Tools = tools
});

await session.SendAsync(new MessageOptions
{
    Prompt = "What time is it, and can you search the docs for 'async patterns'?"
});
```

当 AI 判断需要调用工具时，会自动执行这些函数并把结果纳入响应。这和 Semantic Kernel 插件用的是同样的 Function Calling 模式。

## 多模型路由

GitHub Copilot SDK 的一个突出特性是原生的多模型支持。你不会被锁定在某一个模型上，而是可以按 Session 指定模型：

```csharp
// 用 GPT-5 处理复杂推理任务
await using var reasoningSession = await client.CreateSessionAsync(new SessionConfig
{
    Model = "gpt-5"
});

// 用 Claude Sonnet 做创意写作和长文生成
await using var creativeSession = await client.CreateSessionAsync(new SessionConfig
{
    Model = "claude-sonnet-4.5"
});

// 用 GPT-4.1 处理快速轻量级任务
await using var fastSession = await client.CreateSessionAsync(new SessionConfig
{
    Model = "gpt-4.1"
});
```

这种灵活性对成本优化和性能调优很有价值。不同类型的任务路由到最合适的模型，不需要改一行应用代码。

## Microsoft Agent Framework 集成

GitHub Copilot SDK 可以和 Microsoft Agent Framework 集成，后者也是 Semantic Kernel 的 Agent Framework 所使用的框架。你的 Copilot 驱动的 Agent 可以参与多 Agent 工作流，和 Semantic Kernel Agent、AutoGen Agent 并肩协作。

> Microsoft Agent Framework 通过 `AsAIAgent()` 的集成方式目前还在规划中，SDK 官方 README 尚未正式文档化。具体进展请关注[官方仓库](https://github.com/github/copilot-sdk/tree/main/dotnet)。

这一融合在 [Microsoft Semantic Kernel 博客](https://devblogs.microsoft.com/semantic-kernel/build-ai-agents-with-github-copilot-sdk-and-microsoft-agent-framework/) 中有记录，代表着 .NET AI Agent 生态走向统一的重要一步。

## GitHub Copilot SDK 和 Semantic Kernel 怎么选

两者都是微软生态中的一等公民 .NET AI 框架。选哪个，或者两个都用，是开发者经常碰到的问题。

核心区别在于定位：Copilot SDK 为开发者工作流场景优化，和 GitHub 深度集成；Semantic Kernel 是通用的 AI 编排框架，模型无关且面向企业。如果你在构建与代码仓库、Pull Request 或 GitHub 数据打交道的工具，Copilot SDK 能给你原生的上下文访问。如果是更广泛的企业 AI 应用，Semantic Kernel 的插件生态和向量存储集成更适合。

实际中，很多团队两个都用：Copilot SDK 负责面向开发者的工具，Microsoft Agent Framework 作为连接它们的桥梁。

## 会话生命周期与资源管理

`CopilotClient` 会启动一个后台进程，`CopilotSession` 持有一个活跃连接，所以正确管理资源对避免泄漏至关重要。SDK 全程设计为 `await using` 模式：

```csharp
// 正确模式：嵌套的 await using 确保按序释放
await using var client = new CopilotClient();
await client.StartAsync();

await using var session = await client.CreateSessionAsync(new SessionConfig
{
    Model = "gpt-5"
});

// 使用 session...

// session.DisposeAsync() 自动调用 → client.DisposeAsync() 自动调用
```

你已经熟悉的 C# async/await 模式直接适用。事件驱动的 `session.On(...)` API 是非阻塞的，用 `TaskCompletionSource` 收集响应是地道的 .NET 异步写法。

如果在 ASP.NET Core 中使用 SDK，把 `CopilotClient` 注册为 Singleton，每个请求或对话线程创建 Session，和你管理数据库连接的做法类似。你熟悉的 `IServiceCollection` 依赖注入模式在这里直接适用。

## 现在能用于生产吗

截至 2026 年初，SDK 标记为技术预览。API 可能在小版本之间变化。它适合内部工具和早期采用者的生产场景，但如果要用在关键生产系统中，先看看 [GitHub Releases 页面](https://github.com/github/copilot-sdk/releases) 的稳定性状态。

SDK 的方向很清楚：把 Copilot 从 IDE 插件变成可编程的 AI 基础设施。对于正在构建 AI 驱动的开发者工具的 .NET 团队来说，现在是开始探索集成的好时机。
