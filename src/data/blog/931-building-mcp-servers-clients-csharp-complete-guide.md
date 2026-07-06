---
pubDatetime: 2026-07-06T21:05:01+08:00
title: "在 C# 中构建 MCP 服务器和客户端：完整指南"
description: "从零构建 MCP Server 和 Client：Stdio 与 Streamable HTTP 传输、工具/资源/提示词的定义方式、依赖注入、安全认证、Azure 部署，以及 MCP Inspector 调试方法。"
tags:
  [
    "MCP",
    "Model Context Protocol",
    "C#",
    ".NET",
    "AI",
    "Agent",
    "ASP.NET Core",
    "Microsoft.Extensions.AI",
  ]
slug: "building-mcp-servers-clients-csharp-complete-guide"
source: "https://www.devleader.ca/2026/07/06/building-mcp-servers-and-clients-in-c-the-complete-guide"
ogImage: "../../assets/931/01-cover.png"
---

Model Context Protocol (MCP) 正在成为连接 C# 应用与 AI Agent 的标准协议。它让 LLM 和 Copilot 通过统一的 JSON-RPC 合约发现和调用外部工具、读取资源和复用提示词模板——不需要为每个 Agent 框架硬编码一套集成。

C# 官方 SDK（`ModelContextProtocol` 系列 NuGet 包，最新稳定版 1.4.0）提供了从 Stdio 进程通信到 ASP.NET Core HTTP 托管、从依赖注入到 `Microsoft.Extensions.AI` 桥接的完整方案。本文覆盖构建 MCP Server 和 Client 的全流程。

## 三思而后装：三个包怎么选

C# SDK 分三个 NuGet 包，选错会导致不必要的依赖。

**`ModelContextProtocol.Core`**：只需要客户端或底层 Server API，最小依赖集。适合库或受限应用。

**`ModelContextProtocol`**：大多数本地 Server 和 Client 的首选。它引用 `ModelContextProtocol.Core`，增加了 Hosting、DI、Stdio 传输支持和基于 Attribute 的工具/资源/提示词发现。做本地 MCP Server（被 VS Code、Claude Desktop 等作为子进程启动）用这个。

**`ModelContextProtocol.AspNetCore`**：通过 HTTP 托管远程 MCP Server 时加这个。它引用 `ModelContextProtocol`，增加 HTTP Server 支持和 `MapMcp()` 端点映射。

区分清楚：Stdio 本地 Server 用 `ModelContextProtocol` 就够了；远程 HTTP Server 再加 `ModelContextProtocol.AspNetCore`。

## 最小 Stdio Server：一个 Echo 工具

Stdio 是最常见的 MCP Server 起点——客户端启动你的进程，通过 stdin 发 JSON-RPC，从 stdout 读 JSON-RPC。关键是：**应用日志别写 stdout**，stdout 承载协议消息，日志走 stderr。

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using ModelContextProtocol.Server;
using System.ComponentModel;

var builder = Host.CreateApplicationBuilder(args);

// Stdio MCP 用 stdout 承载 JSON-RPC，日志必须走 stderr
builder.Logging.AddConsole(options =>
{
    options.LogToStandardErrorThreshold = LogLevel.Trace;
});

builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithToolsFromAssembly();

await builder.Build().RunAsync();

[McpServerToolType]
public static class EchoTools
{
    [McpServerTool]
    [Description("将消息回显给客户端。")]
    public static string Echo(
        [Description("要回显的消息。")] string message) => $"hello {message}";
}
```

`[McpServerToolType]` 标记工具容器类，`[McpServerTool]` 标记可调用方法，`[Description]` 不只是给人看的注释——SDK 用它生成 JSON Schema，直接影响模型调用工具时的参数传递质量。描述越具体，模型传对参数的概率越高。

## 带依赖注入的工具

SDK 支持把已注册的服务注入工具方法，同时保持工具参数对客户端可见：

```csharp
[McpServerToolType]
public sealed class CustomerTools
{
    [McpServerTool]
    [Description("根据搜索词查找客户支持笔记。")]
    public static async Task<string> SearchSupportNotesAsync(
        SupportNoteSearchService searchService,
        [Description("客户名、账户ID或支持主题")] string query,
        [Description("返回笔记的最大数量")] int maxResults = 5)
    {
        var notes = await searchService.SearchAsync(query, maxResults);
        return string.Join("\n",
            notes.Select(n => $"- {n.Title}: {n.Summary}"));
    }
}
```

`SupportNoteSearchService` 来自 DI 容器，不会出现在工具的 JSON Schema 里。`query` 和 `maxResults` 是普通参数，会生成 Schema。

一个设计原则：MCP 工具应该为 Agent 使用场景塑造，不要盲目镜像每个领域方法。如果工具会修改状态、删除数据、发邮件或花钱，必须设计授权和人工审批。

## 资源和提示词

MCP 不仅支持工具（Tools），还支持资源（Resources）和提示词（Prompts）。工具是做动作，资源是读数据，提示词是指引方向。

```csharp
[McpServerResourceType]
public sealed class DocumentationResources
{
    [McpServerResource(
        UriTemplate = "docs://articles/{id}", Name = "Article")]
    [Description("按 ID 返回文章文本。")]
    public static TextResourceContents GetArticle(string id) => new()
    {
        Uri = $"docs://articles/{id}",
        MimeType = "text/markdown",
        Text = $"# Article {id}\n\n从真实内容存储加载。"
    };
}

[McpServerPromptType]
public sealed class ReviewPrompts
{
    [McpServerPrompt]
    [Description("为 C# 代码片段创建简短的代码审查提示词。")]
    public static ChatMessage CodeReview(
        [Description("要审查的 C# 代码。")] string code) =>
        new(ChatRole.User,
            $"请审查这段 C# 代码的正确性和可维护性：\n\n{code}");
}
```

实际使用中，把工具、资源和提示词当作不同的契约形态。混用会让客户端难以推理。

## 传输层：Stdio vs Streamable HTTP

**Stdio**：本地进程传输。客户端启动你的可执行文件，通过 stdin/stdout 通信。适合 IDE 插件、工作区工具、桌面端本地运行的 Server。简单但只适合单机场景。

**Streamable HTTP**：C# SDK 推荐用于远程 MCP Server。服务端用 `WithHttpTransport()`，客户端用 `HttpClientTransport`。Server 可以放在正常的 HTTP 基础设施后面，使用 ASP.NET Core 认证、日志追踪和水平扩展。

SSE（Server-Sent Events）已被 SDK 标记为遗留传输方式。SDK 诊断 `MCP9004` 将 `EnableLegacySse` 标记为过时。新项目默认用 Streamable HTTP，SSE 只用于迁移老客户端。

决策很简单：本地用 Stdio，远程用 Streamable HTTP。

## 在 ASP.NET Core 中托管远程 MCP Server

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddMcpServer()
    .WithHttpTransport(options =>
    {
        options.Stateless = true; // 不需要服务端到客户端请求时推荐
    })
    .WithToolsFromAssembly();

var app = builder.Build();
app.MapMcp("/mcp");
app.Run();

[McpServerToolType]
public static class TimeTools
{
    [McpServerTool]
    [Description("返回当前 UTC 时间，ISO 8601 格式。")]
    public static string GetUtcTime() => DateTimeOffset.UtcNow.ToString("O");
}
```

远程 Server 不只是 Stdio 示例套个 HTTP。你需要正常的 Web 应用纪律：允许的主机、限制性 CORS、认证、速率限制、结构化日志和遥测。无状态模式是生产的默认起点——避免会话黏连，水平扩展更容易。

## 构建 MCP 客户端

```csharp
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;

// Stdio 客户端
var transport = new StdioClientTransport(new StdioClientTransportOptions
{
    Name = "Everything",
    Command = "npx",
    Arguments = ["-y", "@modelcontextprotocol/server-everything"],
});

await using var client = await McpClient.CreateAsync(transport);

foreach (var tool in await client.ListToolsAsync())
{
    Console.WriteLine($"{tool.Name}: {tool.Description}");
}

var result = await client.CallToolAsync(
    "echo",
    new Dictionary<string, object?> { ["message"] = "Hello from C#!" },
    cancellationToken: CancellationToken.None);

Console.WriteLine(result.Content.OfType<TextContentBlock>().First().Text);
```

远程 Server 用 `HttpClientTransport` 连接 Streamable HTTP 端点。客户端安全同样重要——启动 Stdio Server 时不要随意把环境变量传给不受信任的子进程；HTTP 客户端应把 MCP 端点当作特权 API 对待。

## 接入 Microsoft.Extensions.AI

C# SDK 的最大亮点之一是 `McpClientTool` 继承自 `AIFunction`，意味着 MCP Server 暴露的工具可以直接传给 `IChatClient`：

```csharp
IList<McpClientTool> tools = await client.ListToolsAsync();
IChatClient chatClient = /* 已配置的 Chat Client */;

var response = await chatClient.GetResponseAsync(
    "使用可用工具总结 Contoso 的支持笔记。",
    new ChatOptions { Tools = [.. tools] });

Console.WriteLine(response.Text);
```

一个 MCP Server 暴露一次能力，不同的 Agent 框架通过公共的函数抽象消费——减少胶水代码。无论是直接用 `Microsoft.Extensions.AI`，还是 Semantic Kernel 和 Agent Framework，同一个 MCP Server 都能复用。

## 安全：认证、授权和最小权限

远程 MCP Server 是 Agent 的 API 面，安全不能事后补救。C# SDK 的受保护 Server 示例使用 JWT Bearer Token 认证、`RequireAuthorization()` 保护 `MapMcp()` 端点、`[Authorize]` Attribute 标注工具和资源。未授权项可以从列表操作中过滤，禁止的单独操作返回 JSON-RPC 错误。

工具设计上保持最小权限：只读工具先上线，涉及修改状态、删除数据或花钱的操作必须配授权和人工审批。

## 部署到 Azure

两条路：

- **Azure Functions**：有 MCP 绑定扩展，支持把 Functions 暴露为 MCP 工具/资源/提示词，C# 用 Isolated Worker 模式。适合操作本质上是无状态的函数，且需要 Serverless 扩缩特性。
- **容器化 ASP.NET Core（Container Apps）**：当 Server 有多个工具、复杂认证、共享服务或自定义路由时更灵活。对中间件、托管行为、可观测性和后台服务的控制更细。

没有普适答案——选什么取决于认证模型、冷启动容忍度、会话需求、可观测性要求和 Server 需要多少 ASP.NET Core 的表面积。

## 用 MCP Inspector 调试

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) 是官方调试工具，基于 React 的 Web UI + Node.js 代理，支持 Stdio、SSE 和 Streamable HTTP：

```bash
npx @modelcontextprotocol/inspector
```

Inspector 能列出工具、资源和提示词，交互式调用工具。如果 Inspector 列不出你的工具，问题大概率在 Server 注册、进程启动、stdout/stderr 行为或传输配置上。如果 Inspector 能用但目标 Host 不行，问题在 Host 配置。

注意 Inspector 安全警告：它的代理可以启动本地进程，正常开发时应绑定 localhost，不要暴露到不信任的网络。

如果你关注 .NET 开发、AI Agent 和工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程和技术观察。

## 参考

- [原文: Building MCP Servers and Clients in C#](https://www.devleader.ca/2026/07/06/building-mcp-servers-and-clients-in-c-the-complete-guide)
- [MCP 官方文档](https://modelcontextprotocol.io/docs/getting-started/intro)
- [C# SDK GitHub](https://github.com/modelcontextprotocol/csharp-sdk)
- [C# SDK 传输层文档](https://csharp.sdk.modelcontextprotocol.io/concepts/transports/transports.html)
- [C# SDK 身份认证文档](https://csharp.sdk.modelcontextprotocol.io/concepts/identity/identity.html)
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
- [Azure Functions MCP 绑定](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-mcp)
- [Microsoft Learn MCP Server 快速入门](https://learn.microsoft.com/en-us/dotnet/ai/quickstarts/build-mcp-server)
