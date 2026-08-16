---
pubDatetime: 2026-08-17T07:33:20+08:00
title: "用 C# 构建你的第一个 MCP Server"
description: "基于官方 ModelContextProtocol SDK 2.x 与 .NET 10，从空项目构建一个真实可用的 NuGet 版本查询 MCP Server：工具定义、stdio 与 HTTP 双传输、SDK 2.0 变更和排查清单。"
tags: ["MCP", "Dotnet", "AI", "Claude Code"]
slug: "build-mcp-server-csharp"
ogImage: "../../assets/1001/01-cover.jpg"
source: "https://codewithmukesh.com/blog/build-mcp-server-csharp/"
---

编程助手会一本正经地写出不存在的 NuGet 包版本号，也完全不知道你的内部 API、数据库和本地文件里有什么。MCP（Model Context Protocol）Server 补的正是这个缺口：把模型做不了、看不到的事情，包成带类型描述的工具，让任何 MCP 客户端都能调用。

本文以 Mukesh Murugan 2026 年 8 月的教程为基础，用官方 ModelContextProtocol C# SDK 和 .NET 10，从空文件夹构建一个真实可用的 MCP Server——一个帮编码助手查询 NuGet 真实版本的工具。除了 stdio 版本，还会跑通 HTTP 版本，并专门说明 SDK 2.0 相对 1.x 改了什么：现在网上大部分教程（包括 AI 助手给的答案）描述的仍是 1.x 行为。

适合会写 C#、想给编程助手接上自己系统或数据的开发者。读完你会得到：一套可以照着执行的步骤、两个真实工具、两种传输的接线方式，以及一份服务器不工作时的排查清单。

## MCP Server 是什么

MCP Server 是一个通过 Model Context Protocol 向 AI 客户端暴露「带类型工具」的小程序。客户端启动时问服务器有哪些工具、读每个工具的 JSON schema，然后在提示词需要模型自己做不了的工作时调用它们。MCP 是 Anthropic 发起的开放规范，C# SDK 现在由社区与 Microsoft 共同维护。

一个有用的心智模型：MCP 之于 AI 工具，就像 OpenAPI 之于 HTTP API。它是一份契约——「我能做什么、参数是什么、返回什么」。任何兼容客户端都读得懂这份契约，所以同一个 server 无需适配就能在 VS Code、Visual Studio、Claude Code、Cursor 里工作。C# SDK 负责 JSON-RPC 的底层通信，你只需要写普通 C# 方法并加上特性。

## 什么时候值得自己写一个

模型不知道你的系统。它访问不了内部 API、工单系统、数据库，也不知道任何实时状态。工具补上这个缺口，而且是以任何客户端都能消费的方式。

更实际的理由是：逻辑你已经有了。领域服务、EF Core 查询、集成代码都在 C# 里，MCP Server 只是把这些逻辑里「精选的一小片」暴露给 agent，不用为此用 Python 重写一遍。作者自己的例子：他 .NET Claude Code kit 里基于 Roslyn 的 server，让 agent 直接问编译器「这个符号在哪里被使用」，而不是靠 grep 猜。

**什么时候不该写。** 如果一个 agent 已经能拿 bearer token 和 OpenAPI 文档直接调你的 REST API，MCP Server 的收益就很小——多一个进程、多一件要版本管理的东西、多一种故障模式。

满足至少一条再动手：

- 需要 agent 通过 HTTP 拿不到的本地访问：文件系统、运行中的进程、本地数据库、CLI
- API 面太大不适合直接交给模型：300 个端点是噪音，8 个命名清楚的工具才可用
- 想要「类型化发现」：客户端启动时学习参数，调用前完成校验
- 要在不会暴露到网络的信任边界内运行

一条都不满足？把 OpenAPI 文档写好就收工。

## 五个包，从哪个开始

SDK 在 2.x 拆成五个包。很多老教程只说三个——那在 2.0 之前是对的。

| 包                                    | 什么时候用                                       |
| ------------------------------------- | ------------------------------------------------ |
| ModelContextProtocol.Core             | 只要客户端或底层 server API，依赖最少            |
| ModelContextProtocol                  | 默认选择：stdio server、宿主、依赖注入、特性发现 |
| ModelContextProtocol.AspNetCore       | Server 通过 HTTP 访问                            |
| ModelContextProtocol.Extensions.Tasks | 客户端轮询完成的长时间任务                       |
| ModelContextProtocol.Extensions.Apps  | Server 下发的交互式 UI（实验性）                 |

从 ModelContextProtocol 开始即可，它会自动带入 Core。

## 创建项目

前置条件：.NET 10 SDK。

```bash
dotnet --version
```

官方有模板 `dotnet new mcpserver`（来自预览包 Microsoft.McpServer.ProjectTemplates），Microsoft Learn 的快速入门用的就是它。模板适合交付、不适合学习：它直接给你一个成品项目，你看不到每块拼图是干什么的。从一个空的控制台应用开始：

```bash
dotnet new console -n NuGetMcpServer
cd NuGetMcpServer
dotnet add package ModelContextProtocol --version 2.2.0
dotnet add package Microsoft.Extensions.Hosting --version 10.0.11
dotnet add package Microsoft.Extensions.Http --version 10.0.11
```

注意是控制台应用而不是 Web 应用：stdio 模式的 MCP Server 通过标准输入输出通信，整个过程不涉及任何 Web 服务器。

版本说明：原文写于 2.1.0 时期（2026-08-05 发布），当前最新稳定版是 2.2.0（2026-08-13 发布，只新增了混合有状态/无状态 HTTP 服务模式，并修复一处头部解码问题）。本文代码在两个版本上都能原样运行。

最终的项目结构：

```
NuGetMcpServer/
├── Services/
│   └── NuGetCatalogClient.cs   # 访问 NuGet feed
├── Tools/
│   └── NuGetTools.cs
├── Program.cs                  # 宿主 + 传输注册
└── NuGetMcpServer.csproj
```

## 第一个工具：Echo

工具就是类上的公开方法，两个特性让它可见：类上的 `[McpServerToolType]`，方法上的 `[McpServerTool]`。

```csharp
using System.ComponentModel;
using ModelContextProtocol.Server;

namespace NuGetMcpServer.Tools;

[McpServerToolType]
public sealed class EchoTools
{
    [McpServerTool(Name = "echo")]
    [Description("Repeats back whatever message it is given.")]
    public static string Echo(
        [Description("The message to repeat.")] string message) => $"You said: {message}";
}
```

`[Description]` 不是文档。它是模型决定「要不要调用这个工具」时唯一读的东西，也是模型理解每个参数含义的途径。描述含糊的工具会被忽略，或者更糟——被用莫名其妙的参数调用。写描述的标准：像在聊天里给新同事解释这个工具一样。

这是玩具版。下面做点值得留下的东西。

## 一个你会真正留下的工具：查 NuGet 版本

几乎每个 MCP 教程都停在 echo 或随机数，做完你还是不知道真实 server 长什么样。这里做一个解决真实问题的：编程助手会幻觉 NuGet 包版本。它会自信地写下 `<PackageReference Include="Serilog.AspNetCore" Version="8.0.1" />`，因为训练数据里有这个版本，然后你的构建失败。解法是给 agent 一个查真实答案的工具。

先写一个访问 NuGet 公共 feed 的薄客户端。Package Content API 列出一个包的所有已发布版本：

```csharp
using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using NuGet.Versioning;

namespace NuGetMcpServer.Services;

public sealed class NuGetCatalogClient(HttpClient httpClient)
{
    public async Task<IReadOnlyList<NuGetVersion>> GetVersionsAsync(
        string packageId,
        CancellationToken cancellationToken = default)
    {
        // The feed requires the package ID lowercased with ToLowerInvariant.
        var id = packageId.Trim().ToLowerInvariant();

        using var response = await httpClient.GetAsync(
            $"v3-flatcontainer/{id}/index.json",
            cancellationToken);

        if (response.StatusCode == HttpStatusCode.NotFound)
        {
            return [];
        }

        response.EnsureSuccessStatusCode();

        var index = await response.Content.ReadFromJsonAsync<VersionIndex>(cancellationToken);

        if (index?.Versions is not { Count: > 0 } versions)
        {
            return [];
        }

        return [.. versions
            .Select(v => NuGetVersion.TryParse(v, out var parsed) ? parsed : null)
            .Where(v => v is not null)
            .Select(v => v!)
            .OrderByDescending(v => v, VersionComparer.VersionRelease)];
    }

    private sealed record VersionIndex(
        [property: JsonPropertyName("versions")] IReadOnlyList<string>? Versions);
}
```

两个细节值得注意。feed 对不存在的包返回 404，所以要先处理，再让 EnsureSuccessStatusCode 把其余状态变成异常。另外 NuGet 文档从不承诺 versions 数组有序，所以显式用 NuGetVersion 排序，而不是信任返回顺序——System.Version 做不了这件事，因为它不理解预发布版本（prerelease）的排序规则。补一个包：

```bash
dotnet add package NuGet.Versioning --version 7.9.0
```

然后是工具类。注意构造函数参数：工具类和其他 .NET 类一样走依赖注入。

```csharp
using System.ComponentModel;
using ModelContextProtocol.Server;
using NuGetMcpServer.Services;

namespace NuGetMcpServer.Tools;

[McpServerToolType]
public sealed class NuGetTools(NuGetCatalogClient catalog)
{
    [McpServerTool(Name = "get_latest_package_version")]
    [Description("Gets the latest stable version of a NuGet package. Call this before writing any code that references a package, so the version number is real and current.")]
    public async Task<string> GetLatestPackageVersionAsync(
        [Description("The exact NuGet package ID, for example ModelContextProtocol or Serilog.AspNetCore.")]
        string packageId,
        CancellationToken cancellationToken = default)
    {
        var versions = await catalog.GetVersionsAsync(packageId, cancellationToken);

        if (versions.Count == 0)
        {
            return $"No NuGet package was found with the ID '{packageId}'. Check the spelling.";
        }

        var latestStable = versions.FirstOrDefault(v => !v.IsPrerelease);

        return latestStable is null
            ? $"'{packageId}' has no stable release yet. The latest prerelease is {versions[0]}."
            : $"The latest stable version of {packageId} is {latestStable}.";
    }

    [McpServerTool(Name = "list_package_versions")]
    [Description("Lists the most recent versions of a NuGet package, newest first, including prereleases. Use this to check whether a specific version exists.")]
    public async Task<string> ListPackageVersionsAsync(
        [Description("The exact NuGet package ID.")] string packageId,
        [Description("How many versions to return. Defaults to 10, maximum 50.")] int count = 10,
        CancellationToken cancellationToken = default)
    {
        var versions = await catalog.GetVersionsAsync(packageId, cancellationToken);

        if (versions.Count == 0)
        {
            return $"No NuGet package was found with the ID '{packageId}'. Check the spelling.";
        }

        var take = Math.Clamp(count, 1, 50);
        var selected = versions.Take(take).Select(v => v.ToNormalizedString());

        return $"{packageId} versions (newest first): {string.Join(", ", selected)}";
    }
}
```

Math.Clamp 比看起来重要得多。参数是模型选的：一个要求 5000 个版本的模型会把版本字符串灌满上下文窗口、拖垮会话。把每个工具参数都当成不可信输入——因为选择它的确实是语言模型。这个习惯和你对公开 API 端点的防御是一样的。

不存在的包 ID 返回一句话而不是异常：模型读得到、能自我纠正；未处理异常只会让调用失败。

## 接上 stdio 传输

宿主里三处注册，外加一行比什么都重要的代码：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using NuGetMcpServer.Services;

var builder = Host.CreateApplicationBuilder(args);

// stdout carries the JSON-RPC stream. Anything else written there corrupts the
// protocol, so every log goes to stderr instead.
builder.Logging.AddConsole(options =>
{
    options.LogToStandardErrorThreshold = LogLevel.Trace;
});

builder.Services.AddHttpClient<NuGetCatalogClient>(client =>
{
    client.BaseAddress = new Uri("https://api.nuget.org/");
    client.Timeout = TimeSpan.FromSeconds(10);
});

builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithToolsFromAssembly();

await builder.Build().RunAsync();
```

LogToStandardErrorThreshold 是整份文件里最重要的一行。stdio 模式下，stdout 就是协议通道。一个 Console.WriteLine、一条启动横幅、一个写到 stdout 的日志，客户端就会在 JSON-RPC 该出现的位置看到垃圾，然后直接断开连接，还不给任何有用的错误。这是第一个 MCP Server 跑不起来的头号原因。

WithToolsFromAssembly() 扫描当前程序集里带 `[McpServerToolType]` 的类；AddHttpClient&lt;NuGetCatalogClient&gt; 注册类型化客户端，NuGetTools 的构造注入由此解析。想用 Serilog？规则一样：sink 必须写到 stderr（Console.Error）。

```bash
dotnet build
```

## 不用 IDE 也能测试

用 MCP Inspector。它会启动你的 server、列出暴露的工具，并允许手工调用：

```bash
npx @modelcontextprotocol/inspector dotnet run
```

它会打开一个浏览器界面。永远先在这里测：Inspector 看不到你的工具，任何 IDE 都看不到，而且它能更快地告诉你为什么。

也可以直接从终端驱动。把三条 JSON-RPC 消息存到 probe.jsonl：

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_latest_package_version","arguments":{"packageId":"ModelContextProtocol"}}}
```

然后把文件喂进去，最后一行之后让管道多开几秒：

```bash
{ cat probe.jsonl; sleep 4; } | dotnet run
```

那个 sleep 在干实事：如果最后一条消息写完 stdin 立刻关闭，宿主会在工具调用完成 HTTP 请求前开始关停，你会什么都看不到——看起来和服务器坏了一模一样，实际不是。

返回长这样：

```json
{
  "result": {
    "content": [
      {
        "type": "text",
        "text": "The latest stable version of ModelContextProtocol is 2.2.0."
      }
    ]
  },
  "id": 2,
  "jsonrpc": "2.0"
}
```

这是上面代码的真实返回格式，也是核对版本的方式（原文发布时这里返回 2.1.0）。

握手里有一处细节值得停下来看：2025-11-25 是 initialize 接受的最新协议修订。请求这个 SDK 实际对齐的修订，服务器会拒绝：

```json
{
  "error": {
    "code": -32022,
    "message": "Protocol version '2026-07-28' is not available through the initialize handshake.",
    "data": {
      "supported": ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"],
      "requested": "2026-07-28"
    }
  },
  "id": 1,
  "jsonrpc": "2.0"
}
```

这个错误就是 2.0 变更的具体化：2026-07-28 修订移除了 initialize 握手，改从 discovery 端点协商；握手保留着纯粹是为了让旧客户端继续工作。

生成的 schema 里还有个细节：CancellationToken 不是工具参数。SDK 把它从 schema 中剥离、从请求里提供——你拿到取消能力，模型看不到它。

## 接入 VS Code 与 Claude Code

VS Code 在工作区里建 .vscode/mcp.json：

```json
{
  "servers": {
    "nuget": {
      "type": "stdio",
      "command": "dotnet",
      "args": ["run", "--project", "NuGetMcpServer/NuGetMcpServer.csproj"]
    }
  }
}
```

VS Code 从工作区根目录运行 MCP server，所以路径相对的是根目录，不是配置文件所在目录。

Claude Code 用项目根目录的 .mcp.json，结构几乎一样，只有一个会让你浪费时间的差别：顶层键是 mcpServers，不是 servers。

```json
{
  "mcpServers": {
    "nuget": {
      "command": "dotnet",
      "args": ["run", "--project", "NuGetMcpServer/NuGetMcpServer.csproj"]
    }
  }
}
```

Claude Code 把没有 type 的条目当 stdio 处理，所以可以不写。也可以让 CLI 来写：`claude mcp add nuget -- dotnet run --project NuGetMcpServer/NuGetMcpServer.csproj`。

重启客户端，问一个只有工具能回答的问题：Serilog.AspNetCore 的最新稳定版是多少？如果 agent 没调用工具直接回答了，就在提示词里点名工具名——模型觉得自己已经知道答案时就会跳过工具，而这正是这个 server 要解决的失败模式。

## stdio 还是 HTTP

stdio 把 server 作为客户端的子进程运行；HTTP 把它作为客户端通过网络访问的服务运行。大部分决策其实是「谁来运行它」。

|                   | stdio              | Streamable HTTP          |
| ----------------- | ------------------ | ------------------------ |
| 谁启动            | 客户端，作为子进程 | 你，作为托管服务         |
| 用户              | 本机一个人         | 多台机器、多人           |
| 认证              | 进程边界就是边界   | 必须做，是你的责任       |
| 网络暴露          | 无                 | 真实存在，需要认真对待   |
| 本地文件/进程访问 | 有                 | 取决于宿主是否允许       |
| 扩展              | 每客户端一个进程   | 水平扩展，2.x 无粘性会话 |
| 最适合            | 开发者工具         | 共享的内部服务           |

作者的默认选择是 stdio：没有网络面、没有认证可错、没有部署。多人或多机器需要同一个 server 时再用 HTTP，并接受一个事实——你刚刚领了一个认证问题。

## 同一套工具跑在 HTTP 上

HTTP 版是一个复用同一批工具类的 ASP.NET Core 应用：

```bash
dotnet add package ModelContextProtocol.AspNetCore --version 2.2.0
```

```csharp
using NuGetMcpServer.Services;
using NuGetMcpServer.Tools;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHttpClient<NuGetCatalogClient>(client =>
{
    client.BaseAddress = new Uri("https://api.nuget.org/");
    client.Timeout = TimeSpan.FromSeconds(10);
});

builder.Services
    .AddMcpServer()
    .WithHttpTransport()
    .WithTools<NuGetTools>();

var app = builder.Build();

app.MapMcp("/mcp");

app.Run();
```

WithTools&lt;NuGetTools&gt;() 注册指定的类——工具在引用的项目而不是本程序集时用它。其余就是普通的 minimal API 宿主：你熟悉的中间件、配置、托管全都适用。示例里把 feed 地址硬编码没问题，真实项目请用 options 模式挪进配置。

这里是 2.x 和其他教程描述的剧烈分歧点：SDK 2.x 的 WithHttpTransport() 默认无状态。原文实测：不握手直接 POST tools/list，服务器照常回答；1.x 下这个请求会因为没有会话被拒绝。

无状态意味着没有 Mcp-Session-Id 头、没有服务器端会话状态、前面不需要粘性会话——负载均衡器后面放两个副本就能工作。需要旧行为就显式要：

```csharp
.WithHttpTransport(options => options.Stateless = false)
```

2.2.0 更进一步：新增 HttpServerSessionMode 混合模式，让 2025-11-25 与 2026-07-28 两类客户端共享同一个端点。无状态也让容器化部署变得简单——副本之间没有会话亲和性要维护。网络上跑的 server，进真实环境之前必须先上认证。

## SDK 2.0 改了什么

2.0.0（2026-07-28）让 C# SDK 与 MCP 规范修订 2026-07-28 对齐。如果你在读旧教程，或者在问 2026 年 8 月之前训练的 AI 助手，下表就是它们答错的地方。完整细节见 v2.0.0 release notes 与 .NET Blog 公告。

| 领域                     | 1.x                           | 2.x                                     |
| ------------------------ | ----------------------------- | --------------------------------------- |
| HTTP 状态                | 带 Mcp-Session-Id 的会话      | 默认无状态                              |
| 握手                     | initialize / initialized      | discovery 优先，旧对端回退              |
| Roots、Sampling、Logging | 支持                          | 废弃（MCP9005）                         |
| 会话级状态               | 支持                          | 告警（MCP9006）                         |
| 旧 SSE 端点              | 支持                          | 告警（MCP9004）                         |
| Tasks                    | 在主包里                      | 移至 Extensions.Tasks，线级不兼容       |
| 非对象工具结果           | 包成 { "result": value }      | 直接返回原始值                          |
| OAuth 回调               | AuthorizationRedirectDelegate | AuthorizationCallbackHandler（MCP9007） |
| Tool.inputSchema         | 可选                          | 必填，缺失抛 JsonException              |

这些 MCP90xx 代码是编译期诊断。如果构建把警告当错误处理，升级到 2.x 会在你迁移或抑制之前直接断掉。

对本文来说的好消息：基础没变。AddMcpServer()、两个特性和 WithStdioServerTransport() 在 2.x 与 1.x 行为相同；稳定且未废弃的 1.x API 依然编译。破坏集中在 HTTP 会话、废弃能力和实验性的 Tasks 预览上。

## 我的判断：什么时候值得写

作者建完这个 server 后的诚实结论：工具描述才是真正的工程，协议是简单的那部分。让 server 跑起来只要 20 分钟；让模型用对的参数调对的工具要更久，而杠杆几乎总是 `[Description]` 的措辞，不是代码。

第二句话：建一个你自己真正需要的工具，而不是五个看起来有用的。这个 NuGet server 存在，是因为作者受够了修生成代码里的包版本——一个真实、反复出现的烦恼，而且有清晰的信号判断工具是否生效。一个没人调用的工具什么都教不了你。

工具数量保持在低位：每暴露一个工具，模型每轮都要多权衡一个选项。八个犀利的工具胜过三十个含糊的。边界也要清楚：工具用来做模型自己做不了的工作；给 agent 指令和上下文，skills 更轻，且不需要 server。

## 服务器不工作时的排查清单

- **工具没出现在客户端**：检查两个特性——类上 `[McpServerToolType]`、方法上 `[McpServerTool]`，且类必须在 WithToolsFromAssembly() 扫描的程序集里；工具在别处就用 WithTools&lt;T&gt;()。
- **客户端连上立刻断开**：有东西写到了 stdout。找 Console.WriteLine、没有 LogToStandardErrorThreshold 的日志、或会 echo 任何内容的包装脚本。手工运行 server，确认 stdout 开头字节是 JSON。
- **报「The command "dnx" ... was not found」**：dnx 从 .NET 10 SDK 开始自带，安装 .NET 10 SDK。
- **agent 不调用你的工具就回答**：在提示词里点名工具名；还不行就是 `[Description]` 太含糊，或者模型觉得自己的知识够用。
- **升到 2.x 构建报 MCP9005 / MCP9007**：在用废弃能力，查上面的迁移表。
- **工具调用卡住**：给 HttpClient 设超时。没有超时，一个慢依赖会拖停整个会话，还不给任何反馈。

## 小结

MCP Server 在 C# 里只有很少的代码量：一个控制台应用、一个包、两个特性、一个宿主。官方 SDK 处理 JSON-RPC、schema 生成和取消，剩下你写普通 C#，把心思放在工具设计上。

决定成败的是两件不起眼的事：保持 stdout 干净；把 `[Description]` 写成「模型是唯一读者」——因为它就是。如果你在 SDK 2.x 上，记住 HTTP 默认值变了：无状态是新常态，网上大量资料还没跟上。

完整可运行的 stdio 与 HTTP 两版代码在原文的 GitHub 仓库里：clone 下来、把客户端指过去、问它一个包版本，就完成了你的第一次验证。

Aide Hub 持续分享 AI 助手、开发工具与软件工程实践。如果你想先跑通本文的 MCP Server 再决定要不要深入，可以从 MCP Inspector 和排查清单开始，遇到问题欢迎在评论区留言。

## 参考

- [Build Your First MCP Server in C# with the Official SDK（原文，Mukesh Murugan）](https://codewithmukesh.com/blog/build-mcp-server-csharp/)
- [modelcontextprotocol/csharp-sdk | GitHub](https://github.com/modelcontextprotocol/csharp-sdk)
- [csharp-sdk v2.0.0 Release Notes](https://github.com/modelcontextprotocol/csharp-sdk/releases/tag/v2.0.0)
- [Announcing v2.0 of the official MCP C# SDK | .NET Blog](https://devblogs.microsoft.com/dotnet/announcing-v20-of-the-official-mcp-csharp-sdk/)
- [Quickstart: Build your first MCP server | Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/ai/quickstarts/build-mcp-server)
- [Model Context Protocol 规范](https://modelcontextprotocol.io/)
- [NuGet Package Content API | Microsoft Learn](https://learn.microsoft.com/en-us/nuget/api/package-base-address-resource)
- [示例代码：build-mcp-server-csharp | GitHub](https://github.com/codewithmukesh/claude-code-for-dotnet-developers/tree/main/modules/04-mcp-plugins/build-mcp-server-csharp)
