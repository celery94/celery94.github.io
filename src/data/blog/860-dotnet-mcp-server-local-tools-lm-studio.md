---
pubDatetime: 2026-06-08T09:03:15+08:00
title: "用 .NET 写一个简单 MCP Server：从 stdio 到本地工具"
description: "MCP Server 可以让 Cursor、VS Code、LM Studio 等 AI 客户端发现并调用你定义的本地工具。这篇基于 Paul Michaels 的示例，梳理 .NET MCP Server 的最小注册、tool attribute、DI 注入、LM Studio 工具、客户端配置和日志注意事项。"
tags: [".NET", "MCP", "AI", "LM Studio"]
slug: "dotnet-mcp-server-local-tools-lm-studio"
ogImage: "../../assets/860/01-cover.png"
source: "https://pmichaels.net/mcp-server-dotnet/"
---

MCP（Model Context Protocol）可以把 AI 客户端和你的本地代码接起来：客户端发现你暴露的工具，理解工具描述和参数 schema，然后在合适的时候调用它。Paul Michaels 这篇文章用 .NET 写了一个很小的 MCP Server，目标是让 Cursor、VS Code、LM Studio 这类工具可以调用本地文件操作和本地 LLM。

它的重点不在“大而全的框架”，而在最小可运行路径：注册 MCP Server，选择 stdio transport，从 assembly 发现工具，再用 attribute 把普通 C# 方法变成可调用 tool。

## 最小服务端

核心 `Program.cs` 大概就这几步：

```csharp
var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddSingleton<McpFileLogger>();
builder.Services.AddSingleton<LmStudioClient>(sp =>
{
    var logger = sp.GetRequiredService<McpFileLogger>();
    return new LmStudioClient(baseUrl, configModel, logger);
});

builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithToolsFromAssembly();

await builder.Build().RunAsync();
```

三个调用分别对应三件事：

- `AddMcpServer()`：把 MCP Server 注册进 DI 容器。
- `WithStdioServerTransport()`：使用 stdin/stdout 和 MCP client 通信。
- `WithToolsFromAssembly()`：扫描当前 assembly，自动发现工具。

这也是 MCP Server 的基础形状：它不是一个普通 Web API，不是开一个 HTTP endpoint 等人请求，而是由 AI 客户端按 MCP 协议启动并通过 stdio 对话。

## 定义工具

在 .NET MCP SDK 里，一个工具可以只是一个带 attribute 的静态方法。原文用文件创建做例子：

```csharp
[McpServerToolType]
public static class FileTools
{
    [McpServerTool,
     Description("Creates or overwrites a file at the specified path with the given content.")]
    public static string CreateFile(
        McpFileLogger logger,
        [Description("Full or relative path where the file will be created")]
        string path,
        [Description("Content to write into the file")]
        string content)
    {
        var resolvedPath = Path.GetFullPath(path);
        var directory = Path.GetDirectoryName(resolvedPath);

        if (!string.IsNullOrEmpty(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(resolvedPath, content);

        return
            $"Successfully created file at: {resolvedPath} ({content.Length} bytes)";
    }
}
```

这里有几个关键点：

`[McpServerToolType]` 标记这个类里有 MCP tools。

`[McpServerTool]` 标记具体方法是工具。

`Description` 很重要。AI 客户端会读它来判断什么时候调用这个工具，也会用参数上的描述生成输入 schema。

`McpFileLogger` 不是用户输入参数，而是从 DI 容器自动注入。也就是说，工具方法可以同时接收“客户端提供的参数”和“服务端注入的依赖”。

追加文件工具也类似：

```csharp
[McpServerTool,
 Description("Appends content to an existing file, or creates the file if it does not exist.")]
public static string AppendToFile(
    McpFileLogger logger,
    [Description("Full or relative path to the file")]
    string path,
    [Description("Content to append to the file")]
    string content)
{
    var resolvedPath = Path.GetFullPath(path);
    var directory = Path.GetDirectoryName(resolvedPath);

    if (!string.IsNullOrEmpty(directory))
    {
        Directory.CreateDirectory(directory);
    }

    File.AppendAllText(resolvedPath, content);
    return $"Appended {content.Length} bytes to: {resolvedPath}";
}
```

这类工具写起来很轻，但文件系统工具一定要谨慎。真实项目里最好限制工作目录、校验路径、避免任意覆盖敏感文件，并把危险操作做成需要确认的流程。

## 接上 LM Studio

原文还加了一个 LLM-backed tool，让 MCP client 可以通过本地 LM Studio 模型拿回复：

```csharp
[McpServerToolType]
public static class LmStudioTools
{
    [McpServerTool,
     Description("Send a message to the local LLM and get a chat-style response.")]
    public static async Task<string> ChatWithLlm(
        LmStudioClient lmStudio,
        McpFileLogger logger,
        [Description("The message or prompt to send to the LLM")]
        string message)
    {
        var response = await lmStudio.ChatAsync(message);
        return response;
    }
}
```

`LmStudioClient` 是一个 `HttpClient` wrapper，调用 LM Studio 的 OpenAI-compatible endpoint：

```text
http://localhost:1234/v1/chat/completions
```

因为它已经注册进 DI 容器，MCP SDK 会自动把它注入到工具方法里。这样工具本身不需要知道客户端如何创建、模型地址如何配置，只负责调用依赖。

## 包和配置

原文使用的 MCP SDK 包仍是 preview：

```powershell
Install-Package ModelContextProtocol -Version 0.9.0-preview.2
```

项目还需要标准 hosting 包：

```xml
<ItemGroup>
  <PackageReference Include="Microsoft.Extensions.Hosting" Version="9.0.0" />
  <PackageReference Include="ModelContextProtocol" Version="0.9.0-preview.2" />
</ItemGroup>
```

这里的版本来自原文示例。实际新项目要先检查 NuGet 上当前版本，尤其是 preview 包，API 名称和注册方式可能会变化。

## 接入客户端

有了 server 之后，需要告诉 AI 客户端怎么启动它。很多客户端使用类似这样的 MCP 配置：

```json
{
  "mcpServers": {
    "mcp-server-offline-llm": {
      "command": "C:\\path\\to\\publish\\McpServerOfflineLlm.exe",
      "args": []
    }
  }
}
```

原文提醒：这个 exe 最好是 self-contained 发布。否则目标机器需要安装对应 .NET SDK 或 runtime，客户端启动 server 时可能找不到依赖。

## 日志别写 stdout

这是 stdio transport 下最容易踩的坑。

MCP 协议用 stdin/stdout 通信，所以你不能随手 `Console.WriteLine` 调试。stdout 上出现的任何内容，都可能被客户端当作 MCP message 解析，直接破坏协议。

调试输出应该写到 stderr：

```csharp
Console.Error.WriteLine("Bad things happened!");
Console.Error.WriteLine("Or... good things happened - all are errors!");
```

更稳妥的做法是像原文那样写一个文件 logger，或者接入不会污染 stdout 的 logging sink。

## 意图分类

文章最后还提到一个 standalone host：先用 LLM 判断用户意图，再决定是否调用工具。

做法是让模型输出结构化 JSON：

```json
{
  "intent": "create_file",
  "confidence": 0.95,
  "reason": "Explicit create with path and content",
  "path": "C:\\temp\\notes.txt",
  "content": "Hello World"
}
```

如果 `confidence` 高于阈值，比如 `0.8`，host 就调用 MCP tool；否则回退到普通聊天。为了让输出更稳定，分类调用使用低 temperature，比如 `0.1`。

这个模式挺实用：不要靠关键词判断“用户是不是想创建文件”，而是让模型把意图、置信度和参数结构化出来。只是它也更需要安全边界：低置信度不执行，危险工具要确认，路径和内容要校验。

## 实践建议

如果你想照着搭一个最小 MCP Server，可以按这个顺序来：

1. 创建 .NET worker/console host。
2. 注册需要注入到工具里的服务，比如 logger、文件服务、LLM client。
3. 调用 `AddMcpServer().WithStdioServerTransport().WithToolsFromAssembly()`。
4. 用 `[McpServerToolType]` 和 `[McpServerTool]` 标记工具类和方法。
5. 给工具和参数写清楚 `Description`，让 AI 客户端知道什么时候调用。
6. 发布 self-contained exe，并在客户端 MCP config 里配置 `command`。
7. 日志写 stderr 或文件，不要污染 stdout。
8. 对文件、命令、网络等危险工具加权限和路径限制。

原文最值得带走的一点是：MCP Server 本身并不复杂。复杂的是你暴露什么工具、工具说明是否清楚、执行边界是否安全，以及 AI 客户端在什么条件下应该调用它。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Creating a Simple MCP Server in .NET](https://pmichaels.net/mcp-server-dotnet/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [ModelContextProtocol NuGet Package](https://www.nuget.org/packages/ModelContextProtocol)
- [offline-ai sample project](https://github.com/pcmichaels/offline-ai)
