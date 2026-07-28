---
pubDatetime: 2026-07-28T08:46:54+08:00
title: "用 MCP Inspector 调试 C# MCP Server：从连接到排错"
description: "MCP Inspector 是官方 MCP 服务器调试工具。本文覆盖 C# 场景下的 stdio 和 Streamable HTTP 两种连接方式、工具/资源/提示词的交互测试、JSON-RPC 原始日志解读、五种 .NET 常见故障模式，以及从 Inspector 导出 mcp.json 配置的完整流程。"
tags: ["mcp", "model-context-protocol", "csharp", "dotnet", "debugging", "tutorial", "aspnet-core"]
slug: "debugging-csharp-mcp-server-with-mcp-inspector"
ogImage: "../../assets/974/01-cover.png"
source: "https://www.devleader.ca/2026/07/27/testing-and-debugging-your-c-mcp-server-with-mcp-inspector/"
---

如果你已经搭建好了一个 C# MCP Server，现在需要验证它真的在按 MCP 协议工作，**MCP Inspector** 应该是你调试流程的第一站。它是一个官方出品的交互式工具，能连接你的 MCP Server、列出能力、调用工具、读取资源、尝试提示词，还能直接查看 JSON-RPC 的原始流量——不需要猜你的编辑器或 agent 框架在背后做了什么。

截止 2026 年 7 月，NuGet 上的 `ModelContextProtocol`、`ModelContextProtocol.Core` 和 `ModelContextProtocol.AspNetCore` 稳定版是 1.4.0。本文验证的所有 Inspector 操作基于官方 [MCP Inspector 仓库](https://github.com/modelcontextprotocol/inspector) 的最新版本。

## MCP Inspector 是什么

MCP Inspector 由两个协作组件构成：一个基于 React 的 Web UI（客户端），以及一个 Node.js 代理服务器。代理扮演 MCP Client 的角色，通过 stdio、SSE 或 Streamable HTTP 连接你的 Server，浏览器 UI 提供 Tools / Resources / Prompts / Logs / Notifications / Request History 等标签页。

这个架构对 C# MCP Server 来说很重要。浏览器没法直接 `dotnet run` 然后走 stdin/stdout 说 JSON-RPC——Node 代理帮你做这件事，再把交互暴露给 React UI。对于 Streamable HTTP Server，代理同样提供一致的 Inspector 体验，把协议测试和你的目标 MCP 宿主隔离开。

**最大的好处就是隔离**。如果 MCP Inspector 连不上你的 Server 或列不出工具，问题出在 Server 启动、传输选择、端点 URL、schema 或协议输出上——不用先怀疑编辑器、agent 框架或桌面客户端。如果 Inspector 能正常工作但某个宿主不行，那问题大概率在那台宿主的配置上。

## 启动 MCP Inspector 连接 Stdio Server

最基础的启动方式：

```bash
npx @modelcontextprotocol/inspector -- dotnet run --project C:\dev\MyMcpServer\MyMcpServer.csproj
```

注意命令行中的分隔符规则：`--` 之前的部分属于 Inspector，之后的部分属于你的 Server。如果 Server 需要环境变量，用 `-e` 传参；如果需要给 `dotnet run` 传额外参数，再加一层 `--`：

```bash
npx @modelcontextprotocol/inspector `
  -e ASPNETCORE_ENVIRONMENT=Development `
  -e MY_SERVER_SETTING=local `
  -- dotnet run --project C:\dev\MyMcpServer\MyMcpServer.csproj -- --profile debug
```

这里有三层参数分界：`-e` 是 Inspector 的环境变量注入、第一个 `--` 之后是 Server 启动命令、第二个 `--` 之后的 `--profile debug` 会被传递给 `dotnet run` 进而到达你的 Server 进程。

Node.js 需要 `^22.7.5`，客户端 UI 默认在 `http://localhost:6274`，代理默认端口 `6277`，启动时打印 session token 和预填 URL。代理默认开启认证。

**用已编译的 exe 代替 `dotnet run` 可以去掉构建时间**，也更接近 stdio MCP 宿主启动 Server 的实际方式：

```bash
npx @modelcontextprotocol/inspector `
  -- C:\dev\MyMcpServer\bin\Debug\net10.0\MyMcpServer.exe `
  --workspace C:\dev\sample-workspace
```

快速迭代时用 `dotnet run --project`，调试进程启动行为时用编译好的 exe。速度和便利性之间的取舍。

## 连接 Streamable HTTP Server

如果你的 C# Server 走 ASP.NET Core + `ModelContextProtocol.AspNetCore` + `WithHttpTransport(...)` + `app.MapMcp()`，那就是 Streamable HTTP 模式。先启动 Server，再在 Inspector UI 选择 Streamable HTTP transport，输入端点 URL：

```
http://localhost:3001/mcp
```

一个常见错误是端点路径不匹配。`app.MapMcp()` 默认映射根路由；如果你显式写了 `app.MapMcp("/mcp")`，Inspector 就要连 `/mcp`。连到首页、Swagger 页面或旧的 SSE URL 都会导致 Inspector 在真正测试工具之前就失败。

如果你的 Server 内部调用了下游 HTTP 服务，Inspector 只能证明 MCP 契约正确——它不会自动让你的下游依赖变得可靠。

## 用 Inspector UI 测试工具、资源和提示词

连接成功后，先看能力列表。Tools 标签页列出了所有可用工具、描述、schema 和执行结果。对于使用 attribute discovery 的 C# Server——`[McpServerToolType]`、`[McpServerTool]`、`[Description]`——这里验证的就是这些元数据是否产出了你预期的契约。

实操流程很直接：列出工具 → 挑一个只读或低风险的工具 → 在自动生成的表单里填参数 → 调用 → 检查返回结果和原始请求/响应日志。

- **工具没出现**：通常是注册或发现的问题
- **工具出现了但参数不对**：通常是 C# 方法签名、描述或 schema 生成的问题
- **工具出现但调用失败**：通常是工具内部运行时行为或依赖的问题

Inspector 做的事情，用 C# SDK 代码来表达就是：

```csharp
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;

var transport = new StdioClientTransport(new StdioClientTransportOptions
{
    Name = "Local C# MCP Server",
    Command = "dotnet",
    Arguments = ["run", "--project", @"C:\dev\MyMcpServer\MyMcpServer.csproj"],
});

await using var client = await McpClient.CreateAsync(transport);

foreach (var tool in await client.ListToolsAsync())
    Console.WriteLine($"{tool.Name}: {tool.Description}");

var result = await client.CallToolAsync(
    "echo",
    new Dictionary<string, object?> { ["message"] = "hello from a harness" },
    cancellationToken: CancellationToken.None);

Console.WriteLine(result.Content.OfType<TextContentBlock>().First().Text);
```

MCP Inspector 提供的是一样的循环，但更少 harness 代码、更多可视化。Exploratory 调试时尤其有用——手动试参数、查看 schema 意外、快速定位哪个环节出了问题。

Resources 和 Prompts 标签页同样值得检查。工具能正常工作，但 resource URI 模板可能设计得很别扭；Server 初始化成功，但 prompt 生成的 message 形状不对。这些是工具调用覆盖不到的 bug 类型。

## 读原始 JSON-RPC 日志

Inspector 的真正价值在原始请求/响应日志。出问题时，不要停在红色错误横幅，直接读 JSON-RPC 负载。

**先看初始化**。客户端和 Server 协商协议版本和能力。初始化失败，后面的工具调用都毫无意义。官方 MCP 调试指南特别提到能力协商是常见问题，`-32602`（JSON-RPC 标准 invalid params）经常出现在这个阶段。如果看到这个码，对比客户端声明和 Server 期望。

**再看列表响应**。`tools/list`、`resources/list`、`prompts/list` 的返回内容告诉你 C# Server **实际**暴露了什么——这比「你以为自己注册了什么」可靠得多。对于 attribute-based 的 C# Server，日志可能揭示缺失的描述、意外的参数名、意外的必填字段，或者干脆没有工具。

**最后看 `tools/call`**。请求体里参数类型 C# 方法绑定不了，和绑定成功后在工具内部抛异常，是两种完全不同的失败。Inspector 日志帮你区分 schema 不匹配、校验失败、传输故障和应用层故障。

如果你同时收集了 Server 端日志，按时间和工具名把两边对起来。Inspector 的 JSON-RPC + Server 端日志 = 最短的排错回路。

## .NET MCP Server 五种常见故障模式

### 1. Stdout 污染

Stdio MCP 用 stdout 传输 JSON-RPC 协议消息。如果你的 C# Server 把普通日志、banner、`Console.WriteLine` 或诊断文本写到了 stdout，客户端就会在应该收到 JSON-RPC 的地方读到非协议文本。Inspector 可能初始化失败、断开连接或显示畸形响应。

修复：把日志定向到 stderr：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var builder = Host.CreateApplicationBuilder(args);

builder.Logging.AddConsole(options =>
{
    // 对 stdio MCP 来说，stdout 是协议通道，日志必须走 stderr
    options.LogToStandardErrorThreshold = LogLevel.Trace;
});

builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithToolsFromAssembly();

await builder.Build().RunAsync();
```

### 2. 传输或端点错误

Stdio Server 需要命令，Streamable HTTP Server 需要 URL。旧的 SSE URL 和 Streamable HTTP 端点不是一回事。C# SDK 传输文档明确说 Streamable HTTP 是远程 Server 的推荐传输方式，SSE 是旧方案且默认禁用。如果 Inspector 无法通过 HTTP 连接，先核对路由、协议、端口和传输选择，再改 Server 代码。

### 3. Schema 不匹配

C# 很容易表达可选参数、枚举、nullable、复杂对象和 service 参数。Inspector 显示实际到达 MCP 契约的东西。如果某个参数你期望有但没有、必填而你想设成可选、或者形状和你预期不同，用最小的合法输入去测试，然后对比 schema 和原始 `tools/call` 负载。

### 4. 环境漂移

Stdio 客户端启动你的进程时，工作目录和环境变量可能和你的终端不同。Inspector 的 `-e` 让你显式传环境变量，UI 也支持定制命令行参数和工作目录。如果工具在终端能跑但在 Inspector 不行，先检查命令、工作目录假设、必需文件和环境变量——不要直接认为 MCP 坏了。

### 5. 依赖行为

你的工具可能访问数据库、HTTP API、文件系统或容器化依赖。Inspector 能证明 MCP 路由和 JSON-RPC 在工作，但不能替代针对那些依赖的集成测试。如果需要在本地验证时隔离下游 HTTP 行为，Mock HttpClient 的 DelegatingHandler 方案更合适。如果 Server 依赖真实基础设施，Testcontainers 的重复化依赖设置是更好的选择。

## 从 Inspector 导出 mcp.json 配置

接通之后，Inspector 可以帮你把连接配置导出来。UI 提供两个导出按钮：

- **Server Entry**：复制单个 Server 配置，可贴到已有 `mcp.json` 的 `mcpServers` 下
- **Servers File**：复制一份完整的 `mcp.json` 格式，使用 `default-server` 作为键名

Stdio 模式导出的配置大致是：

```json
{
  "mcpServers": {
    "default-server": {
      "command": "dotnet",
      "args": ["run", "--project", "C:\\dev\\MyMcpServer\\MyMcpServer.csproj"],
      "env": {
        "ASPNETCORE_ENVIRONMENT": "Development"
      }
    }
  }
}
```

Streamable HTTP 模式则是：

```json
{
  "mcpServers": {
    "default-server": {
      "type": "streamable-http",
      "url": "http://localhost:3001/mcp",
      "note": "For Streamable HTTP connections, add this URL directly in your MCP Client"
    }
  }
}
```

导出是减少手工抄写错误的工具，不是免审通道。提交前删除 secret、用绝对路径（目标客户端可能从不可预测的工作目录启动）、把 `default-server` 改成有意义的名字。

## Inspector 之外的补充测试

MCP Inspector 适合交互式探索和诊断，但 Server 一旦变得重要，就需要自动化测试兜底。

**C# 小 harness**——一个命令行程序，启动 Server、列出工具、调用已知工具、断言返回形状——适合本地 stdio Server，因为它直接覆盖了进程启动行为。

**xUnit 集成测试**更适合让行为留在代码库里、在 CI 中跑。HTTP Server 可以用 ASP.NET Core 集成测试 host 整个应用然后通过 SDK 客户端调 MCP 端点。Stdio Server 可以启动编译好的 exe，断言关键工具能列出且返回预期结果。

取舍很简单：**Inspector 更快地诊断和发现，自动化测试更好地防回归**。用 Inspector 理解 bug，然后把重要教训升级为测试。

## 安全注意事项

因为 Inspector 的代理能启动本地进程并连接指定 MCP Server，把它当作有真实权限的本地开发者工具来对待。代理和客户端默认绑定 localhost，认证默认开启。保持默认即可，除非有明确可信的开发理由。

不要随便关认证。仓库文档有 `DANGEROUSLY_OMIT_AUTH=true` 选项且标注了危险——正常的 C# MCP Server 调试不需要它。如果用 Docker 跑 Inspector，端口绑定到 `127.0.0.1`。

另外，Inspector 可能把环境变量传给子进程。不要在生产调试 session 里粘贴生产 secret。用专用的本地凭据、有限范围的测试 token 或 mock 依赖。

## 总结

调试 C# MCP Server 时，先连上、验证能力协商、列出工具/资源/提示词、调一个简单工具、读 JSON-RPC 日志——然后才往外推：环境变量、端点路由、下游依赖、目标客户端。

这个顺序让调试始终建立在证据上。MCP Inspector 不能替代好的 .NET 测试、好的日志和好的 Server 设计。但它给了你在开始猜测之前最重要的东西：**协议层面的可见性**。

## 参考

- [Testing and Debugging Your C# MCP Server with MCP Inspector](https://www.devleader.ca/2026/07/27/testing-and-debugging-your-c-mcp-server-with-mcp-inspector/) — 原文
- [MCP Inspector 官方仓库](https://github.com/modelcontextprotocol/inspector)
- [MCP Inspector 官方文档](https://modelcontextprotocol.io/docs/tools/inspector)
- [MCP 调试指南](https://modelcontextprotocol.io/docs/tools/debugging)
- [C# MCP SDK 文档](https://csharp.sdk.modelcontextprotocol.io/)
- [ModelContextProtocol NuGet](https://www.nuget.org/packages/ModelContextProtocol)
