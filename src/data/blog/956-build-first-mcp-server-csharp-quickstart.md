---
pubDatetime: 2026-07-21T08:42:00+08:00
title: "从零搭建你的第一个 MCP 服务端（C# 快速上手）"
description: "用 C# 搭建一个本地 stdio MCP 服务端的最短路径：控制台应用、官方 SDK、通用 Host、一个属性标注的工具方法，配好 VS Code 或 Claude Desktop 就能跑。不涉及远程传输、认证和部署，只讲第一个能工作的 MCP 服务端。"
tags: ["MCP", "C#", ".NET", "MCP Server", "stdio"]
slug: "build-first-mcp-server-csharp-quickstart"
ogImage: "../../assets/956/01-cover.png"
source: "https://www.devleader.ca/2026/07/10/build-your-first-mcp-server-in-c-a-stepbystep-quickstart"
---

想用 C# 搭一个 MCP 服务端，最快有用的路径是本地 stdio 服务端：一个控制台应用、官方 C# SDK、通用 Host、加一个 AI 宿主能发现和调用的工具方法。本文不讲远程传输、认证和部署，只讲第一个能本地跑通、能接入 VS Code 或 Claude Desktop 的 MCP 服务端。

## 先理解 stdio 的形状

本地 stdio MCP 服务端由宿主作为子进程启动。宿主通过 stdin 向你的进程写 JSON-RPC 消息，你的服务端通过 stdout 回 JSON-RPC 响应。

这个设计简单且可移植，但有一个首次实现时几乎必踩的坑：**stdout 不是日志通道**。任何 `Console.WriteLine`、启动横幅、调试输出或写入 stdout 的默认日志都会污染协议流。

所以第一条规则：用 `ModelContextProtocol` 做本地 stdio 服务端，用 `Microsoft.Extensions.Hosting` 让配置方式跟现代 .NET 一致，日志走 stderr，工具保持小、描述清晰、调用安全。

## 创建项目

从普通控制台应用开始：

```console
dotnet new console -n FirstMcpServer
cd FirstMcpServer
dotnet add package ModelContextProtocol --version 1.4.0
dotnet add package Microsoft.Extensions.Hosting
```

包的选择有讲究。`ModelContextProtocol.Core` 是更精简的客户端和底层 API。`ModelContextProtocol.AspNetCore` 用于 HTTP 模式。对本地 MCP 服务端，`ModelContextProtocol` 是正确的包——它包含 Host 和依赖注入扩展、stdio 传输支持、以及基于属性的工具发现。

## 写 Program.cs

用最少的代码搭起一个可工作的服务端：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using ModelContextProtocol.Server;
using System.ComponentModel;

var builder = Host.CreateApplicationBuilder(args);

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
    [Description("Echoes the provided message back to the caller.")]
    public static string Echo(
        [Description("The message to echo.")] string message) =>
        $"Hello from C#: {message}";
}
```

逐行解释：

- `Host.CreateApplicationBuilder(args)` 提供标准 .NET Host 行为。
- `AddMcpServer()` 注册服务端服务。
- `WithStdioServerTransport()` 告诉 SDK 通过 stdin/stdout 通信。
- `WithToolsFromAssembly()` 扫描当前程序集，寻找工具类型和工具方法。
- `LogToStandardErrorThreshold = LogLevel.Trace` 让所有日志级别都走 stderr，避免污染 stdout 协议流。

属性是发现契约。`[McpServerToolType]` 标记包含工具的类，`[McpServerTool]` 标记可被调用的方法，`[Description]` 告诉宿主和模型这个工具做什么、每个参数是什么意思。

## 写一个稍有用的工具

Echo 能证明服务端跑通了，但现实中的第一个工具应该做点有用的事而不碰生产系统：

```csharp
[McpServerToolType]
public static class DeveloperTools
{
    [McpServerTool]
    [Description("Formats a concise engineering work item summary.")]
    public static string FormatWorkItem(
        [Description("The short title of the work item.")] string title,
        [Description("The priority from 1 to 5, where 1 is highest.")] int priority,
        [Description("Optional implementation note or risk.")] string? note = null)
    {
        var normalizedPriority = Math.Clamp(priority, 1, 5);
        var noteLine = string.IsNullOrWhiteSpace(note)
            ? "No additional implementation notes."
            : note.Trim();

        return $"Title: {title.Trim()}\n" +
               $"Priority: P{normalizedPriority}\n" +
               $"Note: {noteLine}";
    }
}
```

参数描述是契约的一部分，不是装饰。一个模糊的参数名比如 `text` 给模型的指引远不如 "The short title of the work item" 清晰。

## 本地运行

```console
dotnet run --project .\FirstMcpServer.csproj
```

别指望看到一个 web 服务器的欢迎消息。stdio MCP 服务端在 stdin 上等待协议消息。直接跑看起来像卡住了——这可能是正常的。有意义的测试是：宿主能不能启动它、初始化 MCP 会话、列出工具、调用其中一个。

## 接入 VS Code

在 VS Code 的 `mcp.json` 里配置：

```json
{
  "servers": {
    "first-mcp-server": {
      "type": "stdio",
      "command": "dotnet",
      "args": [
        "run",
        "--project",
        "C:\\dev\\FirstMcpServer\\FirstMcpServer.csproj"
      ]
    }
  }
}
```

用项目文件的绝对路径。宿主重新加载配置后，应该能启动进程并发现 `Echo` 和 `FormatWorkItem` 等工具。

## 接入 Claude Desktop

Claude Desktop 使用类似 JSON 配置：

```json
{
  "mcpServers": {
    "first-mcp-server": {
      "command": "dotnet",
      "args": [
        "run",
        "--project",
        "C:\\dev\\FirstMcpServer\\FirstMcpServer.csproj"
      ]
    }
  }
}
```

注意的是，VS Code 和 Claude Desktop 都只是宿主示例。服务端的契约是 MCP。同一个本地 stdio 模式可以被任何兼容客户端消费，只要它们能启动你的进程并说 MCP 协议。

## 常见首次运行错误

**协议损坏**：宿主报非法 JSON、意外 token 或初始化失败——先查 stdout 污染。搜代码里有没有 `Console.WriteLine`，有没有写入 stdout 的日志提供者，有没有启动横幅。

**工具发现不到**：宿主连上了但没显示你的工具——确认三点：类有 `[McpServerToolType]`，方法有 `[McpServerTool]`，服务端注册了 `.WithToolsFromAssembly()`。

**启动配置问题**：宿主无法启动服务端——手动在终端跑同样的命令。验证项目路径，验证 SDK 已安装，验证 `dotnet restore` 成功。

**包版本不对**：复制代码编译不过——检查 `ModelContextProtocol` 的安装版本。SDK 在快速演进，本文基于稳定版 1.4.0。

## 这个例子够用和不够用时

够用：个人或团队的开发者工具，跑在 IDE 或桌面 AI 宿主旁边。适合仓库助手、本地诊断、格式化工具、只读查询工具和安全内部流程的包装器。

不够用：需要共享远程服务、浏览器访问、集中认证、多租户控制或云部署。这些需求会推向 ASP.NET Core、Streamable HTTP、CORS、认证和运维可观测性。

## 自检清单

- 项目是控制台应用，编译通过
- 安装了 `ModelContextProtocol` 和 `Microsoft.Extensions.Hosting`
- `Program.cs` 用了 `Host.CreateApplicationBuilder(args)`
- 日志通过 `LogToStandardErrorThreshold` 走 stderr
- services 链式调用了 `AddMcpServer().WithStdioServerTransport().WithToolsFromAssembly()`
- 工具类有 `[McpServerToolType]`
- 工具方法有 `[McpServerTool]` 和有信息量的 `[Description]`
- 宿主配置指向了正确的项目或可执行文件路径

## 结语

搭第一个 C# MCP 服务端的最简单方式就是保持无聊：控制台应用、`ModelContextProtocol`、`Microsoft.Extensions.Hosting`、stdio 传输、程序集扫描工具、清晰描述、日志走 stderr。这给你一个可工作的基线，不拖入远程托管、认证、部署。

基线跑通之后再做明智取舍：加更多有用的工具、决定服务端是否留在本地、需不需要打包、该不该变成远程。但先把 stdio 服务端跑通——它验证了整个契约从头到尾是通的。

## 参考

- [原文：Build Your First MCP Server in C#](https://www.devleader.ca/2026/07/10/build-your-first-mcp-server-in-c-a-stepbystep-quickstart)
