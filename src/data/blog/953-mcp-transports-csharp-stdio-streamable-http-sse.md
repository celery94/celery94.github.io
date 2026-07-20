---
pubDatetime: 2026-07-21T08:01:20+08:00
title: "MCP 传输层选型：C# 中 stdio、Streamable HTTP 与 SSE 对比"
description: "MCP 传输层决定的不只是管道，还决定了进程边界、安全边界和服务端要记多少状态。本文逐个拆解 stdio、Streamable HTTP（无状态/有状态）和遗留 SSE 三种传输方式在 C# 中的行为、适用场景和迁移路径，附带决策速查表。"
tags: ["MCP", "C#", ".NET", "Streamable HTTP", "stdio"]
slug: "mcp-transports-csharp-stdio-streamable-http-sse"
ogImage: "../../assets/953/01-cover.png"
source: "https://www.devleader.ca/2026/07/17/mcp-transports-in-c-stdio-vs-streamable-http-vs-legacy-sse"
---

MCP 服务端写好了，工具注册了，接下来必须面对一个问题：客户端怎么连进来？这个选择不是"随便挑个管道"那么轻松——传输层决定了谁启动进程、凭据放哪、HTTP 基础设施参不参与、背压怎么处理、以及服务端能不能在两次调用之间保留会话状态。

C# SDK 1.4.0 提供了三种传输：stdio 用于本地下进程，Streamable HTTP 用于远程服务，遗留 SSE 仅作为兼容。本文把每种选项的行为、代码和取舍讲清楚。

## 一个心理模型：stdio 是本地关系，HTTP 是远程关系

在深入代码之前，先记住一个简单的分类：

- **stdio**：客户端启动服务端进程，stdin 写 JSON-RPC，stdout 读 JSON-RPC。适合 IDE、桌面应用、CLI 或本地 agent 运行时——服务端就活在调用者的进程树下。
- **Streamable HTTP**：服务端独立运行，客户端通过 HTTP 端点连接。适合远程服务、内部 API、云托管场景。
- **遗留 SSE**：已经 deprecated，仅用于迁移旧的 SSE 客户端。

这个分类决定了后面几乎所有设计选择。

## stdio：最直接的本地传输

stdio 是三种传输中最简单的一种。客户端启动服务端进程，往 `stdin` 写 JSON-RPC 消息，从 `stdout` 读 JSON-RPC 响应。协议规范明确说：stdout 是协议通道，不是日志通道。

这意味着 .NET 默认习惯要改。`Console.WriteLine` 会写到 stdout，会污染协议流。把日志定向到 stderr：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

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
```

配置量很小，这是 stdio 的吸引力之一。本地宿主可以直接启动你的可执行文件，管理它的生命周期，关闭工作区后终止进程。对本地开发工作流来说很自然。

代价是 stdio 不像共享服务。每个客户端进程通常会启动自己的服务端进程——对隔离性很好，但如果你需要多个客户端共享一个远程端点，就不是你想走的路。

另一个关键点是凭据。`StdioClientTransportOptions` 默认继承父进程的环境变量。对可信的一方服务端来说可能没问题，但对第三方或 marketplace 风格的服务端，这就是风险：

```csharp
using ModelContextProtocol.Client;

var environment = StdioClientTransportOptions
    .GetDefaultEnvironmentVariables();
environment["MY_SERVER_API_KEY"] = myServerApiKey;

var transport = new StdioClientTransport(new StdioClientTransportOptions
{
    Command = "my-mcp-server",
    Arguments = ["--workspace", workspacePath],
    InheritEnvironmentVariables = false,
    EnvironmentVariables = environment,
    ShutdownTimeout = TimeSpan.FromSeconds(10)
});

await using var client = await McpClient.CreateAsync(transport);
```

安全的做法：不要继承所有环境变量。从 SDK 的精选白名单开始，只加服务端需要的值。

## Streamable HTTP：推荐的远程传输

Streamable HTTP 是远程 MCP 服务端的推荐 HTTP 传输。在 C# SDK 中，服务端通过 `ModelContextProtocol.AspNetCore`、`WithHttpTransport(...)` 和 `MapMcp(...)` 来配置。

最小化的无状态 Streamable HTTP 服务端：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddMcpServer()
    .WithHttpTransport(options =>
    {
        options.Stateless = true;
    })
    .WithToolsFromAssembly();

var app = builder.Build();

app.MapMcp("/mcp");

app.Run();
```

对大多数远程服务端，`Stateless = true` 是应该优先评估的起点。1.4.0 SDK 文档建议显式设置 `Stateless`，而不是依赖当前默认值。在稳定版 1.4.0 中，文档描述的当前默认是有状态的（为了向后兼容），但仍然推荐多数 HTTP 服务端使用无状态模式。

无状态模式把每个请求当作独立的。没有 `Mcp-Session-Id` 要跟踪，没有服务端会话内存，不需要为扩缩容做会话亲和。如果工具接收输入、调用 API、查询数据、返回结果，且不需要在请求之间记住客户端，无状态就是更简单的模型。

有状态 Streamable HTTP 仍然有效，适用于：服务端需要向客户端发请求、未经请求的通知、资源订阅、或者不能跨并发代理泄露的客户端状态。代价是每个会话的内存占用、重启行为，以及在多实例部署时的会话亲和需求。

## Streamable HTTP 客户端与会话恢复

客户端通过 `HttpClientTransport` 连接 MCP 端点。SDK 支持 `HttpTransportMode.StreamableHttp`，默认的自动检测模式会先尝试 Streamable HTTP，然后回退到 SSE：

```csharp
using ModelContextProtocol.Client;

var transport = new HttpClientTransport(new HttpClientTransportOptions
{
    Endpoint = new Uri("https://mcp.example.com/mcp"),
    TransportMode = HttpTransportMode.StreamableHttp,
    ConnectionTimeout = TimeSpan.FromSeconds(30),
    AdditionalHeaders = new Dictionary<string, string>
    {
        ["Authorization"] = $"Bearer {accessToken}"
    }
});

await using var client = await McpClient.CreateAsync(transport);
```

会话恢复仅适用于有状态会话。SDK 文档展示了 `KnownSessionId` 和 `McpClient.ResumeSessionAsync(...)`——在客户端遇到可恢复的中断、且服务端仍保有会话时有用：

```csharp
var transport = new HttpClientTransport(new HttpClientTransportOptions
{
    Endpoint = new Uri("https://mcp.example.com/mcp"),
    KnownSessionId = previousSessionId
});

await using var client = await McpClient.ResumeSessionAsync(
    transport,
    new ResumeClientSessionOptions
    {
        ServerCapabilities = previousServerCapabilities,
        ServerInfo = previousServerInfo
    });
```

不要把会话恢复当作持久化应用状态。它是传输/会话层的恢复机制。长时间运行的工作流状态应该放在传输会话之外。

## DNS 重绑定与 CORS：HTTP 就得承担 HTTP 的安全责任

Streamable HTTP 规范的安全警告：验证 `Origin` 头、本地服务端绑定到 localhost 而非所有接口、要求正确的认证。CORS 控制哪些浏览器来源可以调用服务端，但它不能替代认证和主机验证。

如果 MCP 传输是 HTTP，它就继承了 HTTP 的安全义务。限制主机名。需要 CORS 时限制浏览器来源。只包含你模式需要的头：`Content-Type`、`Authorization`、`MCP-Protocol-Version`，以及使用会话或恢复功能时的会话相关头。

## 遗留 SSE：仅用于迁移

遗留 SSE 是 MCP 传输选型中文档最要仔细读的部分。C# SDK 1.4.0 传输文档说新实现应优先使用 Streamable HTTP。v1.2.0 发布说明也明确了一个破坏性行为变更：遗留 SSE 端点默认禁用。

具体来说：`MapMcp()` 默认不再映射 `/sse` 和 `/message` 路由。启用属性是 `HttpServerTransportOptions.EnableLegacySse`，它被标记为 `[Obsolete]`，诊断代码 `MCP9004`。遗留 SSE 还需要有状态模式——当 `Stateless = true` 时，遗留 SSE 端点不会映射。

为什么这么强硬？背压问题。遗留 SSE 把请求和响应通道分开了。客户端 POST JSON-RPC 消息到 `/message`，收到 `202 Accepted` 后马上返回，响应通过另一个长连接的 `/sse` GET 流到达。这意味着 POST 端没有 HTTP 层面的背压来限制并发——客户端可以一直提交工作而不等之前的工具调用完成。Streamable HTTP 把 POST 响应保持打开直到处理器完成，自然地把请求完成和连接用量绑在一起。

如果你必须临时支持旧客户端，这样启用：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddMcpServer()
    .WithHttpTransport(options =>
    {
        options.Stateless = false;

#pragma warning disable MCP9004
        options.EnableLegacySse = true;
#pragma warning restore MCP9004
    })
    .WithToolsFromAssembly();

var app = builder.Build();

app.MapMcp("/mcp");

app.Run();
```

不要在帮助方法里偷偷压制这个警告不加注释。Obsolete 诊断是一个有用的提醒：这是兼容模式，不是新服务端的方向。

## SSE 迁移到 Streamable HTTP

实际迁移比很多人预期的小，但你需要同时改客户端端点和服务端期望。

**客户端**：从 SSE 路径移到 `MapMcp()` 映射的 MCP 端点。如果旧客户端指向 `https://mcp.example.com/sse`，Streamable HTTP 客户端应该指向根 MCP 端点如 `https://mcp.example.com/mcp`。用 `HttpTransportMode.AutoDetect` 时 SDK 先尝试 Streamable HTTP。如果确定服务端支持，显式设为 `HttpTransportMode.StreamableHttp`。

**服务端**：先迁移客户端，再移除 `EnableLegacySse`。过渡期间可以同时运行 Streamable HTTP 和遗留 SSE——设 `Stateless = false` 和 `EnableLegacySse = true`。Streamable HTTP 在 `MapMcp()` 路由上服务，遗留 SSE 客户端使用该路由下的 SSE 路径。最后一个遗留客户端迁移完成后，移除 opt-in 并考虑切到无状态模式。

安全的迁移步骤：

1. 盘点客户端——找到所有配置为 `/sse` 的客户端
2. 更新客户端端点——指向 `MapMcp()` 路由
3. 优先使用 Streamable HTTP——显式设置 `HttpTransportMode.StreamableHttp`
4. 运行过渡模式——只在需要时保留 `EnableLegacySse = true`
5. 移除 SSE opt-in——迁移完成后删除
6. 重新审视状态——如果不需要会话特性，切到 `Stateless = true`

## 决策速查表

| 判断条件 | 选 stdio | 选 Streamable HTTP 无状态 | 选 Streamable HTTP 有状态 | 遗留 SSE 兼容 |
|---|---|---|---|---|
| 进程模型 | 客户端启动服务端 | 服务端独立运行 | 服务端独立运行 | 已有 SSE 客户端存在 |
| 主要环境 | IDE、桌面、CLI、本地 agent | 远程服务、内部 API、云托管 | 远程服务需要会话特性 | 仅兼容过渡 |
| 客户端隔离 | 每客户端一个进程 | 请求独立 | 必须保留每客户端状态 | 遗留会话需要 |
| 服务端到客户端消息 | 通过进程连接自然支持 | 无状态模式不支持 | 支持 | 遗留客户端行为需要 |
| 扩缩容 | 非共享 HTTP 服务 | 更容易水平扩展 | 需要会话感知操作 | 需要有状态且存在背压问题 |
| 凭据关注 | 环境变量继承到子进程 | HTTP 认证与头 | HTTP 认证加会话保护 | HTTP 认证加遗留流行为 |

判断流程很简单：服务端是本地且由宿主启动 → stdio。服务端是远程或独立托管 → Streamable HTTP。先评估无状态，需要会话特性时再选有状态。遗留 SSE 只在迁移时临时开启。

## 常见踩坑

**把 stdout 当日志通道**：stdio 模式里 stdout 是协议流。日志走 stderr，把 stdout 留给 MCP 消息。

**环境变量全量继承**：第三方 stdio 服务端可能拿到父进程的凭据，除非你显式禁用继承或精选环境变量。

**习惯性用有状态模式**：如果不需要服务端到客户端请求、通知、订阅或每客户端状态，无状态模式通常更容易运维。

**开启遗留 SSE 然后忘了为什么**：`MCP9004` 废弃诊断就是为了让这个选择保持可见。如果服务端还需要 SSE，记下来哪些客户端依赖它、移除它之前要先完成什么。

## 结语

对大多数团队，决策树很短：本地、进程级、宿主启动 → stdio；远程、独立托管 → Streamable HTTP；先试无状态，会话特性真需要时再切有状态；遗留 SSE 只作临时兼容过渡。

传输层代码量不大，但运维后果不小。先按进程模型选传输，再按实际协议需求选状态模型。

## 参考

- [原文：MCP Transports in C#: stdio vs. Streamable HTTP vs. Legacy SSE](https://www.devleader.ca/2026/07/17/mcp-transports-in-c-stdio-vs-streamable-http-vs-legacy-sse)
