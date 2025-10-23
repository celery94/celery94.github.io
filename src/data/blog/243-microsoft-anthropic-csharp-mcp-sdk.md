---
pubDatetime: 2025-04-03 08:43:46
tags: [".NET", "C#"]
slug: microsoft-anthropic-csharp-mcp-sdk
source: https://devblogs.microsoft.com/blog/microsoft-partners-with-anthropic-to-create-official-c-sdk-for-model-context-protocol
title: 微软携手Anthropic，推出适用于C#的Model Context Protocol官方SDK
description: 微软与Anthropic合作开发了适用于C#的Model Context Protocol (MCP)官方SDK，帮助开发者轻松实现AI模型与外部工具和数据源的集成。
---

# 微软携手Anthropic，推出适用于C#的Model Context Protocol官方SDK 🚀

微软近日宣布与Anthropic合作，共同开发适用于C#的Model Context Protocol (MCP)官方SDK。这款SDK旨在帮助开发者更轻松地将AI模型集成到C#应用中，同时支持创建符合MCP标准的服务器。🎉

## 什么是Model Context Protocol (MCP)？

Model Context Protocol (MCP) 是由Anthropic设计的一种开放协议，主要用于实现LLM（大语言模型）与外部工具和数据源的集成。它允许开发者构建自定义工具和数据源，并将其与LLM应用结合使用，从而扩展AI模型的功能。该协议自2024年11月发布以来，已经成为AI社区广泛使用的技术标准。

### MCP消息类型简介

MCP协议支持多种消息类型，用于客户端和服务器之间的通信。例如：

| 消息类型            | 描述                           |
| ------------------- | ------------------------------ |
| InitializeRequest   | 初始化连接时发送的请求         |
| ListToolsRequest    | 请求服务器提供可用工具列表     |
| CallToolRequest     | 调用服务器提供的工具           |
| ReadResourceRequest | 读取指定资源 URI 的请求        |
| PingRequest         | 用于检查对方是否存活的心跳请求 |

这些消息设计灵活，支持扩展，能够满足不同开发场景的需求。

![MCP通信示意图](https://devblogs.microsoft.com/wp-content/uploads/2025/04/mcp-diagram.png)

## 为什么选择C#？

微软之所以选择C#作为MCP SDK开发语言，是因为它拥有以下优势：

1. **企业级广泛使用**：C#在企业级开发中占据重要地位，是许多关键应用的首选语言。
2. **性能优化**：现代.NET框架性能优秀，支持容器化环境，能够在本地开发和生产环境中提供卓越表现。
3. **生态系统支持**：包括Visual Studio、Azure服务、Microsoft Teams等核心产品均基于C#开发。

通过官方C# SDK，开发者不仅能够轻松将AI模型集成到C#应用，还可以快速构建支持MCP协议的服务器。

## 快速上手：创建一个Echo Server 🌟

以下示例展示了如何使用MCP C# SDK创建一个简单的Echo Server，该服务器会将接收到的信息前缀为“hello”后返回。

### 安装必要依赖

创建一个新的dotnet控制台应用后，安装以下NuGet包：

```bash
dotnet add package Microsoft.Extensions.Hosting
dotnet add package ModelContextProtocol --prerelease
```

### 编写代码

将以下代码添加到`Program.cs`文件：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using ModelContextProtocol.Server;
using System.ComponentModel;

var builder = Host.CreateApplicationBuilder(args);
builder.Logging.AddConsole(consoleLogOptions =>
{
    // 将所有日志输出到stderr
    consoleLogOptions.LogToStandardErrorThreshold = LogLevel.Trace;
});
builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithToolsFromAssembly();
await builder.Build().RunAsync();

[McpServerToolType]
public static class EchoTool
{
    [McpServerTool, Description("Echoes the message back to the client.")]
    public static string Echo(string message) => $"hello {message}";
}
```

### 使用MCP Inspector测试服务器 🔍

要测试刚刚创建的服务器，可以使用[MCP Inspector](https://github.com/modelcontextprotocol/inspector)，一个用于调试MCP服务器的可视化工具。

无需安装Inspector，只需通过`npx`运行：

```bash
npx @modelcontextprotocol/inspector dotnet run
```

启动后，在浏览器中访问提示的URL即可查看Inspector界面。以下是操作步骤：

1. **连接服务器**：点击“Connect”按钮。
2. **列出工具**：点击“List Tools”按钮查看服务器提供的工具列表。
3. **运行工具**：选择Echo工具，输入消息并点击“Run Tool”按钮运行。

效果如下图所示：

![Inspector运行Echo工具](https://devblogs.microsoft.com/wp-content/uploads/2025/04/InspectorRunTool.png)

## 更多资源 📚

- [MCP C# SDK样例代码](https://github.com/modelcontextprotocol/csharp-sdk/tree/main/samples)
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
- [Model Context Protocol官网](https://modelcontextprotocol.io/introduction)

## 结语 💡

微软推出的MCP C# SDK为开发者提供了强大的工具，帮助他们更轻松地构建AI集成应用和支持MCP协议的服务器。该SDK目前仍处于预览阶段，但已经展示出极大的潜力。如果你对这项技术感兴趣，欢迎访问[GitHub仓库](https://github.com/modelcontextprotocol/csharp-sdk/issues)贡献代码或提出建议！

快来试试吧，让我们共同推动AI生态系统的发展！🌐
