---
pubDatetime: 2026-07-29T12:03:40+08:00
title: "MCP C# SDK v2.0 发布：无状态默认、原生 HTTP 与多轮交互"
description: "官方 MCP C# SDK v2.0 随 2026-07-28 协议修订发布。三大核心变化：默认无状态架构让服务器可以水平扩展、原生 HTTP header 支持让现有基础设施直接路由 MCP 流量、Multi Round-Trip Requests 用一个模式替代了 tools/prompts/resources 三种旧模式。本文梳理 v2.0 的全部关键更新和向后兼容策略。"
tags: ["MCP", "CSharp", ".NET", "ASP.NET Core", "SDK"]
slug: "mcp-csharp-sdk-v2"
ogImage: "../../assets/982/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/announcing-v20-of-the-official-mcp-csharp-sdk"
---

[Model Context Protocol (MCP) C# SDK](https://github.com/modelcontextprotocol/csharp-sdk) 正式发布了 **v2.0**，实现了 [2026-07-28 修订版 MCP 规范](https://modelcontextprotocol.io/specification/2026-07-28)。这是协议自发布以来最大的一次修订。

Jeff Handley 在 .NET Blog 上发布了这篇公告。这次更新与之前不同：早期版本是在协议已有形态上叠加能力，而 2026-07-28 修订回到了协议基础，重新思考了 MCP over HTTP 的工作方式。它让协议**默认无状态**，标准化了 HTTP 接口让普通 HTTP 基础设施可以直接路由 MCP 流量，并引入了 **Multi Round-Trip Requests** 让交互式工具不再需要长连接 session。

这个转变正好打在 .NET 的强项上。MCP over HTTP 本质上就是一个 web 负载，而 ASP.NET Core 一直专注的正是这版 MCP 规范关心的问题：路由、中间件、header、负载均衡、水平扩展。MCP C# SDK 直接构建在 ASP.NET Core 之上，新规范的很多要求对 .NET 来说已经是第二天性。

先说最重要的保证：**v2.0 向后兼容。** 升级 SDK 不会让你丢掉已有的客户端和服务器，v1 代码继续编译运行。

## 默认无状态

以前的规范中，通过 Streamable HTTP 调用一个工具意味着要先完成 `initialize` 握手，并且（在 v1 SDK 默认情况下）建立 session。服务器返回一个 `Mcp-Session-Id`，客户端必须在后续每个请求中携带它，把请求固定到最初颁发它的服务器实例上。水平部署需要 sticky routing 或 session 迁移才能正常工作。

2026-07-28 修订用自包含的请求替代了这种连接范围的设置：`initialize` / `initialized` 握手移除了（[SEP-2575](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2575)），`Mcp-Session-Id` header 也移除了（[SEP-2567](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2567)），协议版本和能力信息现在随每个请求携带。

**实际效果：任何服务器实例都可以处理任何请求**，水平部署不再需要 sticky session 和共享 session 存储。Serverless、多实例和边缘部署直接可用。

SDK 与规范同步前进：HTTP server transport 现在**默认无状态运行**。v1 默认配置有状态 session，v2 中 `HttpServerTransportOptions.Stateless` 默认值是 `true`：

```csharp
using ModelContextProtocol.Server;
using System.ComponentModel;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddMcpServer()
    .WithHttpTransport()   // 现在默认无状态
    .WithToolsFromAssembly();

var app = builder.Build();
app.MapMcp();
app.Run("http://localhost:3001");

[McpServerToolType]
public static class EchoTool
{
    [McpServerTool, Description("Echoes the message back.")]
    public static string Echo(string message)
        => $"hello {message}";
}
```

就这么简单。把它放在 round-robin 负载均衡器后面，想扩多少个实例就扩多少个，实例之间没什么需要同步的。容器化也很干净：一个无状态 MCP 服务器就是一个普通的 ASP.NET Core 应用，标准的 .NET 多阶段 `Dockerfile` 就能把它部署到任何容器运行的地方。

> 「无状态协议」不等于「无状态应用」。如果你的服务器需要跨调用保持状态，就做 HTTP API 一直以来的做法：从一个工具中创建显式句柄（`basketId`、`browserId`），然后让模型在后续调用中把它当作普通参数传回来。事实上，模型在一个调用和下一个调用之间串起一个标识符，往往比隐藏在传输元数据中的 session 状态更强大 —— 模型可以跨工具组合句柄、推理它们、在步骤之间交接它们。

当然，无状态是默认值，不是强制要求。如果你确实需要服务器到客户端的非请求消息或 session 范围的传输状态，仍然可以**主动选择**有状态模式。因为 session 现在是 opt-in，旧的 SSE 端点和一些仅限有状态的选项默认被关闭或标记为过时（诊断代码 `MCP9004` 和 `MCP9006`），你依赖旧行为时会收到友好提示。原则是「按需付费」—— 只有真正使用时才承担 session 的复杂性。

还有一个更微妙的原因让无状态成为默认值，这不止是为了扩展。因为 2026-07-28 的线格式完全移除了 `initialize` 握手和 `Mcp-Session-Id`，以 `Stateless = true` 运行是**向前兼容**的选择 —— 这种配置让你的服务器直接、原生化地与新协议客户端对话。旧客户端也不会被抛弃（服务器仍然为它们回退到旧握手），但新客户端得到的是没有阻碍的现代路径。

## 原生 HTTP 扩展能力

无状态化改变了 MCP 请求的形态：现在是一个单一的、自描述的 HTTP POST。这打开了一扇以前走不通的门：**你现有的 HTTP 基础设施终于可以把 MCP 当作普通流量处理**。不需要 sidecar，不需要 body 解析，不需要特殊处理。

2026-07-28 修订标准化了一小套 HTTP header，反映了中间件实际关心的字段（[SEP-2243](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2243)）。一个 `tools/call` 请求现在携带 `Mcp-Method: tools/call` 和 `Mcp-Name: get_order_status` 在 JSON-RPC body 旁边，所以负载均衡器、代理、网关、WAF 或可观测性工具可以**无需深度包解析就对 MCP 流量执行操作**。而且你可以用一个 attribute 把任何工具参数提升为 `Mcp-Param-*` header。

这正是地理分布式路由需要的场景。想象一个调用订单服务的工具部署在多个区域。工具接受 `region` 和 `orderId` 参数，全局负载均衡器需要把每个调用发送到同区域的部署。把 `region` 提升为 header，路由器就能直接根据它来分发，完全不需要读取请求 body：

```csharp
[McpServerTool(Name = "get_order_status"),
 Description("Gets order status from the regional orders service")]
public static async Task<OrderStatus> GetOrderStatusAsync(
    [McpParameter(Header = "Mcp-Param-region")]
    string region,
    string orderId)
{
    // region 现在同时存在于 JSON body 和 Mcp-Param-region header 中
    // 负载均衡器可以直接根据 header 做 geo-routing
    var client = _orderServiceClientFactory
        .GetClientForRegion(region);
    return await client.GetOrderStatusAsync(orderId);
}
```

## 请求用户输入

MCP 长期以来有一种尴尬局面：**工具可以向客户端请求额外输入**（比如 `Please approve this purchase`），但这需要服务器向客户端发送消息 —— 而服务器在非 streaming 的纯 HTTP 传输中无法做到这一点。你必须使用 SSE 或 WebSocket，这意味着要建立 session。现在情况变了。

2026-07-28 修订引入了一种机制，工具可以声明「我需要用户输入」（[SEP-2471](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2471)）。在服务器端，你的工具抛出一个包含输入 schema 的特定异常；SDK 处理剩下的部分 —— 客户端收到结构化响应，提示用户，收集答案，然后重放原始请求并附上用户的响应。不需要 session，不需要 WebSocket。

这种交互模式还有更进一步的能力，叫做 **Multi Round-Trip Requests（MRTR）**。这是 v2 中最具变革性的设计变化之一。

## Multi Round-Trip Requests（MRTR）

在 2026-07-28 修订之前，一个工具调用就是一次往返：客户端发送请求，服务器返回结果。如果你的工具需要跟用户多轮交互 —— 比如「你要查哪个账户？」→「你是指 Checking 还是 Savings？」—— 这在旧规范中是无法用纯 HTTP 原生支持的。长对话交互被强行塞进了 session + SSE/WebSocket 的架构里。

MRTR 改变了这个前提：它允许单个逻辑请求在客户端和服务器之间进行**多次往返**，而不需要长连接。

### Server 端支持 MRTR

在服务器端，当你的工具需要请求用户输入时，抛出一个 `McpServerToolNeedsUserInputException`：

```csharp
[McpServerTool, Description("Transfer funds between accounts")]
public static async Task<string> TransferAsync(
    string fromAccount,
    string toAccount,
    decimal amount)
{
    // 请求用户确认
    var confirmation = McpServerToolNeedsUserInputException
        .Create("Confirm transfer")
        .WithDescription(
            $"Transfer {amount:C} from {fromAccount} " +
            $"to {toAccount}?")
        .WithStringInput("confirmation",
            "Type 'yes' to confirm",
            required: true);

    throw confirmation;
}
```

SDK 自动处理协议的往返细节：客户端收到结构化响应，提示用户，收集输入，然后重放带有 `userInput` 响应的原始请求。你的工具最终重新执行，这次带上用户的回答。

### Client 端支持 MRTR

客户端使用 MRTR 同样简单。`IMcpClient` 接口新增了一个 `CallToolAsync` 重载，接受一个 `McpCallToolOptions` 参数：

```csharp
var options = new McpCallToolOptions
{
    UserInputHandler = async (request, ct) =>
    {
        Console.WriteLine(
            $"[User Input Needed] {request.Description}");
        // 提示用户并返回响应
        var answer = Console.ReadLine();
        return new McpUserInputResponse(
            new Dictionary<string, object>
            {
                ["confirmation"] = answer
            });
    }
};

var result = await client.CallToolAsync(
    "transfer", arguments, options);
```

`UserInputHandler` 委托在服务器请求用户输入时被调用，你的代码负责提示用户并返回响应。SDK 确保在 MRTR 序列中只调用你的 handler 一次，然后把用户的响应在重放请求时传回服务器。

### 一个模式替代三个

MRTR 最优雅的部分在于：它用一个统一的模式替代了旧的 `tools/*`、`prompts/*` 和 `resources/*` 三个独立机制。在 v2 中，这三者仅仅是 MRTR 交互的**不同风格**：

- `tools/call` 是「服务器做某事」的 MRTR 交互
- `prompts/get` 是「服务器生成提示」的 MRTR 交互
- `resources/read` 是「服务器读取资源」的 MRTR 交互

客户端代码不需要理解三种不同的模式。所有交互都遵循相同的请求-响应-可能继续的 MRTR 循环。

### MRTR 与向后兼容

对于 v1 客户端调用 v2 服务器：v2 SDK 自动检测不支持 MRTR 的旧客户端，并将多轮交互**压缩为单次执行**。如果服务器请求用户输入但客户端不支持，SDK 要么跳过交互（使用你提供的默认值），要么返回一个错误指示需要用户输入。

## 向后兼容的设计保证

v2.0 做了大量架构变更，但向后兼容性是一个经过审慎设计的承诺：

- **所有 v1 API 继续工作**。你在 v1 中使用的类、方法和模式在 v2 中都还在原来的位置
- 被标记为 `[Obsolete]` 的 API 仍然可以编译和运行，只是会收到迁移到新模式的诊断建议
- v1 客户端可以连接 v2 服务器，v2 客户端也可以连接 v1 服务器

升级的典型步骤：

1. 更新 NuGet 包到 v2.0
2. 检查构建警告（`MCP9000` 系列诊断码）—— 它们会提示哪里可以简化
3. 如果不想处理 session 了，移除显式的 session 配置即可 —— 无状态已经是默认值
4. 如果你使用了 SSE 或有状态 session，服务器继续工作，但你可能会看到 `MCP9004` 提示

## 包和目标框架

v2.0 的 NuGet 包结构保持了一致，同时增加了一些新包：

- `ModelContextProtocol` —— 核心抽象和类型
- `ModelContextProtocol.AspNetCore` —— ASP.NET Core 服务端集成
- `ModelContextProtocol.Client` —— 客户端实现
- 新增扩展包用于常见的集成场景（Apps 和 Tasks）

目标框架覆盖 `net8.0`、`net9.0` 和 `net10.0`，与 .NET 的 LTS 和 STS 发布节奏保持一致。

## 扩展：Apps 和 Tasks

v2 引入了一个新的扩展模型：**MCP Apps 和 MCP Tasks**。

**MCP App** 将多个工具捆绑为带有声明式清单的可部署包。你可以把一个 app 作为单个单元来分发、发现和安装。

**MCP Task** 将 MRTR 交互包装为带有明确定义边界的命名工作流。一个 task 声明它的输入 schema、它可能请求的用户输入，以及它的输出 schema —— 让客户端更好地推理和编排长时间运行的交互。

## 接下来

Jeff 在公告中提到团队已经在进行 v2.1 的规划，重点是：

- 更丰富的 App 清单，支持版本化和依赖声明
- Task 模板，让你能快速为新场景搭建 MRTR 交互骨架
- 与 .NET Aspire 的更深集成，让 MCP 服务器成为 Aspire 分布式应用的一等组件

## 总结

MCP C# SDK v2.0 是一次**根基性的更新**，不是叠加式的功能增加。三个最值得关注的变化：

1. **默认无状态**：`initialize` 握手和 `Mcp-Session-Id` 没了，任何服务器实例处理任何请求，水平扩展不再需要 sticky session。你的 MCP 服务器就是一个普通 ASP.NET Core 应用
2. **原生 HTTP**：`Mcp-Method`、`Mcp-Name`、`Mcp-Param-*` header 让负载均衡器和网关无需解析 body 就能路由 MCP 流量。现有的 HTTP 基础设施终于可以原生化处理 MCP 了
3. **Multi Round-Trip Requests**：一个模式替代了 tools/prompts/resources 三种旧模式。交互式工具再也不需要长连接 session —— 用户输入请求、表单、多步确认全部在无状态 HTTP 上运行

对于已经在生产环境跑 v1 的团队：v2 向后兼容，升级是安全的。对于新项目：直接上 v2，用默认无状态和 MRTR 构建，你获得的是一个天然的云原生 MCP 服务器。

## 参考

- [原文：Announcing v2.0 of the official MCP C# SDK — .NET Blog](https://devblogs.microsoft.com/dotnet/announcing-v20-of-the-official-mcp-csharp-sdk/)
- [MCP C# SDK GitHub](https://github.com/modelcontextprotocol/csharp-sdk)
- [MCP 2026-07-28 Specification](https://modelcontextprotocol.io/specification/2026-07-28)
- [MCP Specification Changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- [MCP Maintainers' 2026-07-28 Announcement](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)
- [v2 API Documentation](https://csharp.sdk.modelcontextprotocol.io/v2/api/)
