---
pubDatetime: 2026-07-22T07:28:25+08:00
title: "在 C# 里写一个 MCP 客户端：连接、发现、调用工具"
description: "MCP 协议让 AI 应用能发现和调用外部工具，但客户端怎么写？这篇文章从零搭起一个 MCP 客户端，覆盖 stdio 和 HTTP 两种传输方式、工具发现与调用、内容块处理、通知注册以及生命周期管理，每一步都有可运行的代码。"
tags: ["MCP", "C#", ".NET", "AI", "Client"]
slug: "building-mcp-client-csharp"
ogImage: "../../assets/962/01-cover.png"
source: "https://www.devleader.ca/2026/07/21/building-an-mcp-client-in-c-connecting-discovering-and-calling-tools"
---

一个 MCP 客户端坐在你的应用和 MCP 服务器之间。宿主机可以是 IDE、聊天应用、后台服务或 Agent 运行时，服务器暴露自己的能力，客户端负责创建会话、问服务器"你有什么能力"、然后用正确的参数调正确的接口。

MCP 客户端提供了一种"协议级"的方式去对接外部工具，不用把每个工具都提前写死在宿主应用里。当然它不是必须跟 Agent 框架绑定 —— 一个控制台应用、一个 Worker、一个 Web 后端，都可以作为 MCP 客户端来用。

目前 NuGet 上的稳定版是 `ModelContextProtocol` `1.4.0`，`2.0.0-preview.1` 也已经列出。SDK 更新很快，安装前最好去 NuGet 确认一下最新版本。包选择上，`ModelContextProtocol.Core` 是最小依赖集，只有客户端和底层 API；`ModelContextProtocol` 额外附带宿主和 DI 相关能力，官方文档推荐大部分项目从这个包开始。

## 用 StdioClientTransport 建一个最简客户端

Stdio 是本地进程传输。你的应用启动一个服务器进程，客户端通过 stdin/stdout 跟它通信。桌面工具、IDE 集成、本地自动化脚本最适合用这种方式，因为服务器可以跑在用户旁边，访问本地环境。

当前 SDK API 是 `StdioClientTransport` 加 `McpClient.CreateAsync`。`CreateAsync` 连接到服务器并返回一个已连接的 `McpClient`。`McpClient` 实现了 `IAsyncDisposable`，用 `await using` 确保关停和传输清理按预期执行：

```csharp
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;

var transport = new StdioClientTransport(new StdioClientTransportOptions
{
    Name = "Everything",
    Command = "npx",
    Arguments = ["-y", "@modelcontextprotocol/server-everything"],
    ShutdownTimeout = TimeSpan.FromSeconds(10)
});

await using var client = await McpClient.CreateAsync(transport);

IList<McpClientTool> tools = await client.ListToolsAsync();
foreach (var tool in tools)
{
    Console.WriteLine($"{tool.Name}: {tool.Description}");
}

CallToolResult result = await client.CallToolAsync(
    "echo",
    new Dictionary<string, object?> { ["message"] = "Hello MCP!" },
    cancellationToken: CancellationToken.None);

Console.WriteLine(result.Content.OfType<TextContentBlock>().First().Text);
```

这就是最小可用的 MCP 客户端：启动服务器、列出工具、调用 `echo`、读取返回的文本块。这里用 SDK 里的参考 everything server 只是为了验证客户端逻辑。

关键的规矩：stdout 归协议用。服务器日志应该打到 stderr。从客户端这边，`StdioClientTransportOptions.StandardErrorLines` 可以捕获 stderr 输出做诊断，不会污染 JSON-RPC 消息流。

## Stdio 的安全问题：环境变量继承

`StdioClientTransportOptions.InheritEnvironmentVariables` 默认是 `true`。也就是说，子进程服务器会继承客户端进程的环境变量。如果服务器是你自己写的，问题不大。如果是第三方的、不受信任的服务器，这就麻烦了 —— 环境变量里通常有 token、API key、代理配置、内部端点。

SDK 提供了 `StdioClientTransportOptions.GetDefaultEnvironmentVariables()` 作为更安全的起点。它返回一个精简的变量集合 —— 像 PATH 相关的东西 —— 不会把父进程的所有秘密都传下去。实践模式是：

- 设 `InheritEnvironmentVariables = false`
- 从 `GetDefaultEnvironmentVariables()` 起步
- 只加服务器真正需要的，比如 `MY_MCP_SERVER_MODE`
- 用 `StandardErrorLines` 做诊断

不过这个做法也有兼容性代价。关掉继承可能搞坏依赖 `DOTNET_ROOT`、`JAVA_HOME`、`HTTP_PROXY` 这类变量的服务器。安全不是"永远不传环境变量"，而是"只传你明确知道需要的那个最小集合"。如果是内部可信服务器，继承通常可以接受；如果是任意第三方服务器，默认拒绝加显式 allowlist 才是正确起点。

## 通过 HTTP 连接

当 MCP 服务器是远程的、或者被多个客户端共享时，HTTP 是合适的形状。C# SDK 使用 `HttpClientTransport`，同时支持 Streamable HTTP 和旧的 SSE。传输模式默认是 `HttpTransportMode.AutoDetect`，先尝试 Streamable HTTP，不行再退回 SSE。

SSE 在当前 SDK 文档里已经被标为 legacy。新的 HTTP 服务器应该优先用 Streamable HTTP。自动检测对兼容性有好处，但如果你同时管着两端，显式指定 Streamable HTTP 更清晰。

| 客户端场景 | 传输选择 | 取舍 |
| --- | --- | --- |
| 本地开发工具 | stdio | 启动简单，但要关注环境变量继承 |
| 远程共享服务器 | Streamable HTTP | 适合常规 HTTP 基础设施，需要设计超时和生命周期 |
| 兼容过渡期 | AutoDetect 或 SSE | 迁移期间有用，但新项目不要再以 SSE 为默认 |

```csharp
using ModelContextProtocol.Client;

var transport = new HttpClientTransport(new HttpClientTransportOptions
{
    Name = "Remote MCP Server",
    Endpoint = new Uri("https://mcp.example.com/mcp"),
    TransportMode = HttpTransportMode.AutoDetect,
    ConnectionTimeout = TimeSpan.FromSeconds(30)
});

await using var client = await McpClient.CreateAsync(transport);

Console.WriteLine($"Connected to {client.ServerInfo.Name}");
Console.WriteLine($"Protocol version: {client.NegotiatedProtocolVersion}");
```

`HttpClientTransport` 构造函数可以接收一个 `HttpClient` 实例，`ownsHttpClient` 参数控制释放传输时是否也释放这个客户端。如果用工厂管理的 `HttpClient`，别让传输意外占有它。远程 MCP 认证（OAuth、token 等）值得单独展开，这里不深入。

## 发现工具、资源和提示词

`McpClient.CreateAsync` 之后，可以查看 `ServerCapabilities`、`ServerInfo`、`ServerInstructions`，然后列出工具、资源、资源模板和提示词。工具是可调用的函数，资源是可读的数据，提示词是可复用的模板。在客户端里把它们当成不同的契约来对待。

```csharp
await using McpClient client = await McpClient.CreateAsync(transport);

Console.WriteLine($"Server: {client.ServerInfo.Name} {client.ServerInfo.Version}");

IList<McpClientTool> tools = await client.ListToolsAsync();
IList<McpClientResource> resources = await client.ListResourcesAsync();
IList<McpClientPrompt> prompts = await client.ListPromptsAsync();

foreach (var prompt in prompts)
{
    Console.WriteLine($"Prompt: {prompt.Name} — {prompt.Description}");
}

if (resources.FirstOrDefault() is { } resource)
{
    ReadResourceResult read = await client.ReadResourceAsync(resource.Uri);
    foreach (var content in read.Contents.OfType<TextResourceContents>())
    {
        Console.WriteLine($"[{content.MimeType}] {content.Text}");
    }
}
```

发现阶段还有一个决策点：你的客户端是宽容的还是受限的。宽容的客户端列出一切，让上层规划器自己选。受限的客户端在把能力暴露给上层之前，先按工具名、注解、服务器身份或配置做过滤。对于大多数生产应用，建议对可能变更状态的工具加显式 allowlist —— 即使最终是模型来选工具，客户端仍然可以在暴露这一步就框定范围。

## 调用工具并处理内容块

SDK 提供了两种调用工具的方式：通过名字 `client.CallToolAsync(...)`，或者先拿到 `McpClientTool` 实例再用 `tool.CallAsync(...)`。后者适合想保持工具元数据和调用行为在一起的场景。

工具结果需要仔细处理。一次返回可以包含多个内容块，这些块可能是文本、图片、音频或内嵌资源。工具也可以返回 `IsError = true` 而不抛协议异常。这条区分很重要：工具错误是工具调用返回的一部分，协议失败才会以 `McpException` 的形式出现。

```csharp
try
{
    McpClientTool searchTool = (await client.ListToolsAsync())
        .Single(tool => tool.Name == "search_docs");

    CallToolResult result = await searchTool.CallAsync(
        new Dictionary<string, object?>
        {
            ["query"] = "HttpClient streaming",
            ["maxResults"] = 5
        });

    if (result.IsError is true)
    {
        string message = result.Content
            .OfType<TextContentBlock>()
            .FirstOrDefault()?.Text ?? "工具返回了错误。";
        Console.Error.WriteLine(message);
        return;
    }

    foreach (var block in result.Content)
    {
        switch (block)
        {
            case TextContentBlock text:
                Console.WriteLine(text.Text);
                break;
            case ImageContentBlock image:
                File.WriteAllBytes("tool-output.png",
                    image.DecodedData.ToArray());
                break;
            case EmbeddedResourceBlock embedded
                when embedded.Resource is TextResourceContents resource:
                Console.WriteLine($"Resource {resource.Uri}: {resource.Text}");
                break;
        }
    }
}
catch (McpException ex)
{
    Console.Error.WriteLine($"MCP 协议错误: {ex.Message}");
}
```

这边需要应用层做一点判断：如果结果直接给用户，文本可能就够了；如果结果是给 LLM 或另一个规划器用的，注解、结构化内容和内嵌资源就有意义；如果工具会改变状态，记录这次操作并保留足够上下文用于审计。

## 注册通知处理器

部分 MCP 服务器可以在工具列表、资源列表或提示词发生变化时通知已连接的客户端。C# SDK 里，`McpSession.RegisterNotificationHandler(...)` 由 `McpClient` 继承，返回一个 `IAsyncDisposable`，方便在客户端或功能作用域结束时取消注册。

注意：主动通知需要传输层能承载服务端到客户端的消息。Stdio 和有状态的 HTTP 可以做到，无状态的 Streamable HTTP 做不到 —— 因为每条消息都必须是客户端请求-响应流的一部分。

```csharp
await using McpClient client = await McpClient.CreateAsync(transport);

await using IAsyncDisposable subscription = client.RegisterNotificationHandler(
    NotificationMethods.ToolListChangedNotification,
    async (_, cancellationToken) =>
    {
        var updatedTools = await client.ListToolsAsync(
            cancellationToken: cancellationToken);
        Console.WriteLine($"工具列表变更。当前 {updatedTools.Count} 个工具可用。");
    });

await client.PingAsync(cancellationToken: CancellationToken.None);
```

实践模式是在客户端维护一个轻量能力缓存，收到列表变更通知时刷新。缓存失效逻辑保持简单：刷新失败就保留上次已知的安全列表，通过正常的可观测性路径记录失败日志。

## 生命周期和释放

MCP 客户端的生命周期从 `CreateAsync` 之前就开始了。你选传输方式、配安全和超时、决定谁持有 `HttpClient` 和 `ILoggerFactory`。`CreateAsync` 建立会话并跑初始化，之后客户端可以列能力、调工具、读资源、取提示词、注册处理器、ping 服务器。

释放不是走形式。对于 stdio，释放会按 `ShutdownTimeout` 给子进程时间平滑退出。对于 HTTP，释放是否结束会话取决于 `OwnsSession` 等选项，是否释放 `HttpClient` 取决于你配置的所有权。短生命周期的控制台应用直接 `await using` 到底；长生命周期服务则要把客户端当成一个需要健康检查、日志、取消令牌和重连逻辑的连接来对待。

## 常见陷阱

1. **假设服务器永不变化**。MCP 建立在发现之上。可以缓存，但要设计为工具列表、资源列表会变。
2. **把工具错误当异常**。`IsError = true` 是正常的工具返回结果，不是协议异常。客户端要检查这个属性和对应的内容块。
3. **stdio 环境变量太大方**。如果客户端启动不受信任的服务器，关掉继承，传一个显式的环境字典。
4. **过分绑定 SSE**。SDK 文档明确 SSE 是 legacy。远程服务器推荐 Streamable HTTP。
5. **忽略生命周期所有权**。如果客户端跑在 Web 应用或 Worker 里，想清楚在哪里创建、谁释放、取消令牌怎么流转、服务器断开时怎么办。

## 参考

- [Building an MCP Client in C#](https://www.devleader.ca/2026/07/21/building-an-mcp-client-in-c-connecting-discovering-and-calling-tools) - Dev Leader
- [MCP C# SDK GitHub](https://github.com/modelcontextprotocol/csharp-sdk)
- [C# SDK Getting Started](https://csharp.sdk.modelcontextprotocol.io/concepts/getting-started.html)
- [MCP Transports 文档](https://csharp.sdk.modelcontextprotocol.io/concepts/transports/transports.html)
