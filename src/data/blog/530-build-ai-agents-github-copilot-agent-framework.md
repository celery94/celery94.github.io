---
pubDatetime: 2026-01-28
title: "使用 GitHub Copilot SDK 和 Microsoft Agent Framework 构建 AI 代理"
description: "Microsoft Agent Framework 现已集成 GitHub Copilot SDK，使开发者能够构建功能强大的 AI 代理。本文介绍如何利用这一集成在 .NET 和 Python 中创建智能代理应用。"
tags: ["AI", ".NET", "Python", "GitHub Copilot", "Agent Framework"]
slug: "build-ai-agents-github-copilot-agent-framework"
source: "https://devblogs.microsoft.com/semantic-kernel/build-ai-agents-with-github-copilot-sdk-and-microsoft-agent-framework"
---

# 使用 GitHub Copilot SDK 和 Microsoft Agent Framework 构建 AI 代理

Microsoft Agent Framework 现已集成 GitHub Copilot SDK，为开发者提供了构建 AI 代理的强大工具。这一集成将 Agent Framework 的统一代理抽象与 GitHub Copilot 的丰富能力相结合，包括函数调用、流式响应、多轮对话、Shell 命令执行、文件操作、URL 获取以及 Model Context Protocol (MCP) 服务器集成。

## 为什么使用 Agent Framework 与 GitHub Copilot SDK？

虽然可以单独使用 GitHub Copilot SDK 构建代理，但通过 Agent Framework 使用它具有以下优势：

### 1. 统一的代理抽象

GitHub Copilot 代理实现了与框架中所有其他代理类型相同的接口（.NET 中的 `AIAgent`，Python 中的 `BaseAgent`）。这意味着你可以轻松切换提供商或组合使用，而无需重构代码。

### 2. 多代理工作流

可以将 GitHub Copilot 代理与其他代理（Azure OpenAI、OpenAI、Anthropic 等）组合，使用内置编排器实现顺序、并发、交接和群聊工作流。

### 3. 生态系统集成

访问完整的 Agent Framework 生态系统：声明式代理定义、A2A 协议支持，以及跨所有提供商一致的函数工具、会话和流式处理模式。

## 安装 GitHub Copilot 集成

### .NET

```bash
dotnet add package Microsoft.Agents.AI.GithubCopilot --prerelease
```

### Python

```bash
pip install agent-framework-github-copilot --pre
```

## 创建 GitHub Copilot 代理

入门非常简单。创建一个 `CopilotClient`（.NET）或 `GithubCopilotAgent`（Python）并开始与代理交互。

### .NET 示例

```csharp
using GitHub.Copilot.SDK;
using Microsoft.Agents.AI;

await using CopilotClient copilotClient = new();
await copilotClient.StartAsync();

AIAgent agent = copilotClient.AsAIAgent();

Console.WriteLine(await agent.RunAsync("什么是 Microsoft Agent Framework？"));
```

### Python 示例

```python
from agent_framework.github import GithubCopilotAgent

async def main():
    agent = GithubCopilotAgent(
        default_options={"instructions": "你是一个有用的助手。"},
    )

    async with agent:
        result = await agent.run("什么是 Microsoft Agent Framework？")
        print(result)
```

## 添加函数工具

通过自定义函数工具扩展代理，为其提供特定领域的能力。

### .NET 示例

```csharp
using GitHub.Copilot.SDK;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

AIFunction weatherTool = AIFunctionFactory.Create((string location) =>
{
    return $"{location} 的天气晴朗，最高温度 25℃。";
}, "GetWeather", "获取指定位置的天气信息。");

await using CopilotClient copilotClient = new();
await copilotClient.StartAsync();

AIAgent agent = copilotClient.AsAIAgent(
    tools: [weatherTool],
    instructions: "你是一个有用的天气代理。");

Console.WriteLine(await agent.RunAsync("西雅图的天气如何？"));
```

## 流式响应

为了提供更好的用户体验，可以在生成响应时进行流式传输，而不是等待完整结果。

### .NET 示例

```csharp
await using CopilotClient copilotClient = new();
await copilotClient.StartAsync();

AIAgent agent = copilotClient.AsAIAgent();

await foreach (AgentResponseUpdate update in agent.RunStreamingAsync("给我讲一个短故事。"))
{
    Console.Write(update);
}

Console.WriteLine();
```

## 多轮对话

使用会话（.NET）或线程（Python）在多次交互中维护对话上下文。

### .NET 示例

```csharp
await using CopilotClient copilotClient = new();
await copilotClient.StartAsync();

await using GithubCopilotAgent agent = new(
    copilotClient,
    instructions: "你是一个有用的助手。保持回答简短。");

AgentSession session = await agent.GetNewSessionAsync();

// 第一轮对话
await agent.RunAsync("我的名字是 Alice。", session);

// 第二轮对话 - 代理记住上下文
AgentResponse response = await agent.RunAsync("我的名字是什么？", session);
Console.WriteLine(response); // 应该提到 "Alice"
```

## 启用权限控制

默认情况下，代理无法执行 Shell 命令、读写文件或获取 URL。要启用这些功能，需要提供一个权限处理程序来批准或拒绝请求。

### .NET 示例

```csharp
static Task<PermissionRequestResult> PromptPermission(
    PermissionRequest request, PermissionInvocation invocation)
{
    Console.WriteLine($"\n[权限请求: {request.Kind}]");
    Console.Write("批准？(y/n): ");

    string? input = Console.ReadLine()?.Trim().ToUpperInvariant();
    string kind = input is "Y" or "YES" ? "approved" : "denied-interactively-by-user";

    return Task.FromResult(new PermissionRequestResult { Kind = kind });
}

await using CopilotClient copilotClient = new();
await copilotClient.StartAsync();

SessionConfig sessionConfig = new()
{
    OnPermissionRequest = PromptPermission,
};

AIAgent agent = copilotClient.AsAIAgent(sessionConfig);

Console.WriteLine(await agent.RunAsync("列出当前目录中的所有文件"));
```

## 连接 MCP 服务器

GitHub Copilot 代理支持连接到本地（stdio）和远程（HTTP）MCP 服务器，使代理能够访问外部工具和数据源。

### .NET 示例

```csharp
await using CopilotClient copilotClient = new();
await copilotClient.StartAsync();

SessionConfig sessionConfig = new()
{
    OnPermissionRequest = PromptPermission,
    McpServers = new Dictionary<string, object>
    {
        // 本地 stdio 服务器
        ["filesystem"] = new McpLocalServerConfig
        {
            Type = "stdio",
            Command = "npx",
            Args = ["-y", "@modelcontextprotocol/server-filesystem", "."],
            Tools = ["*"],
        },
        // 远程 HTTP 服务器
        ["microsoft-learn"] = new McpRemoteServerConfig
        {
            Type = "http",
            Url = "https://learn.microsoft.com/api/mcp",
            Tools = ["*"],
        },
    },
};

AIAgent agent = copilotClient.AsAIAgent(sessionConfig);

Console.WriteLine(await agent.RunAsync("在 Microsoft Learn 上搜索 'Azure Functions' 并总结热门结果"));
```

## 多代理工作流

Agent Framework 的一个关键优势是能够在多代理工作流中组合 GitHub Copilot 与其他代理。在下面的示例中，Azure OpenAI 代理起草营销标语，GitHub Copilot 代理进行审查——所有这些都作为顺序管道进行编排。

### .NET 示例

```csharp
using Azure.AI.OpenAI;
using Azure.Identity;
using GitHub.Copilot.SDK;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.GithubCopilot;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Extensions.AI;

// 创建 Azure OpenAI 代理作为文案撰写者
var endpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")!;
var deploymentName = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT_NAME") ?? "gpt-4o-mini";
var chatClient = new AzureOpenAIClient(new Uri(endpoint), new AzureCliCredential())
    .GetChatClient(deploymentName)
    .AsIChatClient();

ChatClientAgent writer = new(chatClient,
    "你是一个简洁的文案撰写者。根据提示提供一个简洁有力的营销句子。",
    "writer");

// 创建 GitHub Copilot 代理作为审查者
await using CopilotClient copilotClient = new();
await copilotClient.StartAsync();

GithubCopilotAgent reviewer = new(copilotClient,
    instructions: "你是一个深思熟虑的审查者。对前一条助手消息给出简短反馈。");

// 构建顺序工作流：writer -> reviewer
Workflow workflow = AgentWorkflowBuilder.BuildSequential([writer, reviewer]);

// 运行工作流
await using StreamingRun run = await InProcessExecution.StreamAsync(workflow, input: prompt);
await run.TrySendMessageAsync(new TurnToken(emitEvents: true));

await foreach (WorkflowEvent evt in run.WatchStreamAsync())
{
    if (evt is AgentResponseUpdateEvent e)
    {
        Console.Write(e.Update.Text);
    }
}
```

这个示例展示了单个工作流如何组合来自不同提供商的代理。你可以将这种模式扩展到并发、交接和群聊工作流。

## 总结

Microsoft Agent Framework 的 GitHub Copilot SDK 集成使构建利用 GitHub Copilot 能力的 AI 代理变得简单。通过在 .NET 和 Python 中支持函数工具、流式传输、多轮对话、权限控制和 MCP 服务器，你可以构建与代码、文件、Shell 命令和外部服务交互的强大代理应用程序。

## 相关资源

- [GitHub Copilot SDK](https://github.com/github/copilot-sdk)
- [Microsoft Agent Framework on GitHub](https://github.com/microsoft/agent-framework)
- [Agent Framework 入门教程](https://learn.microsoft.com/agent-framework/tutorials/overview)

---

_本文内容翻译并整理自 Microsoft DevBlogs，原文作者：Dmytro Struk，发布日期：2026年1月27日。_
