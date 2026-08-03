---
pubDatetime: 2026-08-03T09:33:00+08:00
title: "Squad 接入 Agent Framework：会学习的团队"
description: "Squad 是运行在 GitHub Copilot CLI 上的开源多智能体框架，会记住决策、沉淀技能。预览包 Squad.Agents.AI 把它包装成标准 AIAgent，一行 DI 注册即可接入 Agent Framework。"
tags: ["Agent Framework", "AI Agents", "GitHub Copilot", ".NET"]
slug: "squad-agents-ai-microsoft-agent-framework"
ogImage: "../../assets/986/01-cover.jpg"
source: "https://devblogs.microsoft.com/agent-framework/building-agent-teams-with-agent-framework-github-copilot-cli-and-squad/"
---

Microsoft Agent Framework（MAF）现在可以创建以 GitHub Copilot SDK 为后端的智能体：这类智能体天然具备执行 shell 命令、读写文件、抓取 URL、集成 MCP 服务器的编码能力。而 [Squad](https://github.com/bradygaster/squad) 是跑在 GitHub Copilot CLI/SDK 之上的开源多智能体框架——你描述一支小团队（一个协调者加若干各有章程的专家），协调者派活、让专家们讨论、最后交付结果。

两者组合的价值在于分工：MAF 提供智能体运行时、模型抽象、托管和遥测，Copilot CLI/SDK 提供一个已经会读仓库、改文件、跑终端的编码智能体，Squad 则贡献团队式编排。刚发布的预览包 `Squad.Agents.AI` 把这条缝补上了：一个 NuGet 包，一行 DI 注册，Squad 团队就成了 MAF 眼里的普通 `AIAgent`。

这篇文章面向已经在用或打算用 MAF 的 .NET 开发者。读完你会知道：怎么把 Squad 团队接进 `IServiceCollection`、这个包内部做了什么、以及「会学习的团队」和普通无状态智能体到底差在哪里。

## 官方支持：Copilot SDK 作为智能体后端

MAF 对 GitHub Copilot 的支持已经正式发布——C# 和 Python 的集成都在 v1.0 稳定版中（C# 包 `Microsoft.Agents.AI.GitHub.Copilot` 目前已是 1.x 系列）。最简单的用法是把 `CopilotClient` 通过扩展方法 `AsAIAgent()` 提升为 MAF 智能体，再挂上工具和指令：

```csharp
using GitHub.Copilot;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

AIFunction weatherTool = AIFunctionFactory.Create((string location) =>
{
    return $"The weather in {location} is sunny with a high of 25C.";
}, "GetWeather", "Get the weather for a given location.");

await using CopilotClient copilotClient = new();
await copilotClient.StartAsync();

AIAgent agent = copilotClient.AsAIAgent(
    tools: [weatherTool],
    instructions: "You are a helpful weather agent.");

Console.WriteLine(await agent.RunAsync("What's the weather like in Seattle?"));
```

这样创建的智能体背后是真实的 Copilot CLI 进程，具备编码场景需要的完整工具集。官方文档在 [MS Learn | Agent Framework | GitHub Copilot Agents](https://learn.microsoft.com/en-us/agent-framework/agents/providers/github-copilot)，.NET 和 Python 的示例分别在 [agent-framework 仓库](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/AgentProviders/github-copilot/Agent_With_GitHubCopilot) 的对应目录下。

## Squad：住在仓库里的智能体团队

Squad 的设计和「一个提示词扮演多个角色」的聊天机器人不同：每个团队成员以文件形式住在你的仓库里，拥有自己的上下文，只读自己该读的知识，并把学到的东西写回去。团队状态因此跨会话持久——这是后面所有能力的根基。

初始化一个团队只需三条命令：

```bash
npm install -g @bradygaster/squad-cli
squad init        # 生成 .squad/team.md 等团队文件
copilot --agent squad --yolo
```

`squad init` 会在项目里创建 `.squad/` 目录，里面是团队章程、成员和路由规则；`--yolo` 用于免去逐次批准工具调用。注意 Squad 目前仍是 Alpha 项目，API 和 CLI 命令可能变化。

## 一行 DI 注册：把团队变成 AIAgent

`Squad.Agents.AI` 是连接 Squad 与 MAF 的预览 NuGet 包（当前最新为 0.5.x 预览版，支持 net8.0/net9.0/net10.0）：

```bash
dotnet add package Squad.Agents.AI --prerelease
```

接入的完整代码只有这几行：

```csharp
using Microsoft.Agents.AI;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Squad.Agents.AI;

var builder = Host.CreateApplicationBuilder(args);
builder.Services.AddSquadAgent(o =>
{
    o.SquadFolderPath = @"C:\path\to\your\team-root";
});

using var host = builder.Build();
var squad = host.Services.GetRequiredService<AIAgent>();
var session = await squad.CreateSessionAsync();
var response = await squad.RunAsync("What can this Squad team do?", session);
Console.WriteLine(response.Text);
```

`AddSquadAgent()` 会把你的 Squad 团队同时注册成两个类型：`AIAgent`（MAF 通过标准抽象使用它）和 `SquadAgent`（需要 Squad 专属配置的调用方可以降级使用）。

## 原理：DelegatingAIAgent 包一层

`SquadAgent` 本身是一个极薄的组合类：Copilot SDK 已经知道怎么和 `copilot.exe` 通信，`Squad.Agents.AI` 只是把它指向 Squad 团队目录、建立会话，再把结果作为普通 `AIAgent` 交给 MAF。核心结构如下：

```csharp
public sealed class SquadAgent : DelegatingAIAgent
{
    public SquadAgent(SquadAgentOptions options)
        : base(BuildInnerAgent(options))   // 内部 AIAgent 传给基类
    {
    }

    // DelegatingAIAgent 会把 RunAsync、RunStreamingAsync、CreateSessionAsync
    // 全部转发给内部 agent，SquadAgent 本身不需要覆写任何方法。

    private static AIAgent BuildInnerAgent(SquadAgentOptions options)
    {
        // 1. Copilot SDK 客户端，指向 Squad 团队根目录
        var client = new CopilotClient(/* CLI path, env, token, etc. */);

        // 2. 会话启动时让 CLI 自动发现 .squad/ 文件夹，
        //    加载团队 agent、技能、指令和 MCP 服务器
        var teamRoot       = options.SquadFolderPath;
        var squadConfigDir = Path.Combine(teamRoot, ".squad");

        var sessionConfig = new SessionConfig
        {
            WorkingDirectory      = teamRoot,
            ConfigDirectory       = squadConfigDir,
            EnableConfigDiscovery = true,
            OnPermissionRequest   = PermissionHandler.ApproveAll,
        };

        // 3. 把 Copilot 客户端提升为 MAF AIAgent
        return client.AsAIAgent(sessionConfig, name: options.AgentName ?? "Squad");
    }
}
```

整个类没有协议转换、没有额外运行时，就是继承加委托。真正干活的三行是：构造 `CopilotClient`、配置指向团队 `.squad/` 目录的 `SessionConfig`、调用 `AsAIAgent()`。其中 `EnableConfigDiscovery` 是关键：它让 CLI 在会话开始时自动加载团队的章程、技能和 MCP 服务器，而不是让智能体每轮都用文件工具重新读一遍。

流式输出走同一套接口，`await foreach (var update in squad.RunStreamingAsync(prompt, session))` 即可逐块消费响应。完整源码在 [SquadAgent.cs](https://github.com/bradygaster/squad/blob/dev/src/Squad.Agents.AI/SquadAgent.cs)。

## 为什么值得：无状态智能体和自学习团队

MAF 的 workflow 可以把确定性步骤、无状态 AI 调用和精心提示词的专用智能体组合起来，但每次调用它们都从零开始——它们只知道提示词告诉它们的。Squad 不一样，它是一个**自学习团队**，使用越久积累的领域知识越多：

- **记住决策**：「这个服务选 Postgres 不选 Cosmos」被记录一次，之后每个专家每次调用都遵守，不用每次重讲架构。
- **抽取技能**：第一次摸索出部署流程时写成技能文件，第十次直接读技能执行，模式被复用而不是被重新发现。
- **服从纠正**：说过一次「我们不用那个库」，指令被捕获，团队之后不会再提——不是硬编码黑名单，是真的记住了。
- **新专家即时上手**：下个月加一个安全审查员，他第一次会话就继承完整的决策台账和技能库，像新人读团队 wiki。

这改变了 Squad 在 MAF 管线里的意义。四个典型的落地场景：

- **内容管线**：跑十次之后团队已经知道你的语气指南、上次否掉过哪些来源，不再重复争论已经解决的风格问题。
- **代码审查机器人**：记住代码库约定和历史审查结论（「这个模式我们不标记」），每次审查比上次更准。
- **客服升级**：见过产品此前的故障模式，知道「同步错误」通常意味着 token 过期而不是网络问题——无状态智能体每次都会追错根因。
- **发布就绪门禁**：知道「就绪」对你的项目具体意味着什么，因为发布标准是作为决策随时间沉淀下来的，而不是硬编码在提示词里。

换句话说，MAF 管线里的 Squad 槽位不是「调用一个 LLM」，而是「调用一支已经学习你的项目六周的团队」。主机只看到一个 `AIAgent`，底层是带着机构记忆在调度的协调者和专家。针对性智能体给你可重复性，Squad 给你**随时间变好的可重复性**。

## 进阶：多团队、BYOK 与可观测性

预览包还提供了几个值得注意的能力：

**多团队注册。** .NET 8+ 键控 DI 支持在同一个容器里注册多支团队，例如 `AddKeyedSquadAgent("research", ...)` 和 `AddKeyedSquadAgent("platform", ...)`，通过 `[FromKeyedServices("research")]` 在端点里解析。

**BYOK 令牌。** `ConfigureCopilotClient` 委托可以在 Squad 设置完标准值后定制底层的 `CopilotClientOptions`，比如从自己的凭据库注入 GitHub token 或自定义环境变量：

```csharp
builder.Services.AddSquadAgent(o =>
{
    o.SquadFolderPath = @"C:\team";
    o.ConfigureCopilotClient = clientOpts =>
    {
        clientOpts.GitHubToken = myVault.GetSecret("copilot-token");
    };
});
```

**子智能体可观测性。** 包默认对每次专家分发发射一个 OpenTelemetry span（`squad.subagent {Name}`，活 span 上带生命周期事件）。已经接入 Aspire、Jaeger 或 Application Insights 的主机无需额外管道就能看到完整的多智能体扇出：谁被问了、说了什么、花了多久，都和请求的其他部分在同一个 trace 里。关闭方式是把 `EmitSubagentActivities` 设为 `false`，改用 `OnSubagentTrace` 回调自行处理。

安全方面也做了默认处理：token 和密钥在 `ToString()` 输出中脱敏、不进 JSON 序列化，`ConfigureCopilotClient` 委托无法改动 `Cwd`/`CliPath`/`CliArgs`（防止把智能体路由到别的 CLI 进程）。另外包默认给 `copilot.exe` 传 `--agent squad`，让它加载 `.github/agents/squad.agent.md` 作为团队协调者的 agent 定义；文件不存在时静默跳过，不影响未初始化团队的降级使用。

## 前置条件与常见问题

接入前确认：

- .NET 10 SDK（`dotnet --version` 输出 10.x）
- GitHub Copilot CLI 在 `PATH` 中（`copilot --version` 可验证）
- 已用 `squad init` 初始化团队根目录
- Copilot 认证：本地先 `gh auth login` 或 `copilot auth login` 一次，最小路径不需要 app key

常见问题按优先级排查：会话中大量工具调用被逐个询问批准——用 `--yolo` 或在 `SessionConfig.OnPermissionRequest` 里配置 `PermissionHandler.ApproveAll`；`squad.agent.md` 不存在导致协调者不真正扇出——检查 `.github/agents/` 目录；团队目录路径写错——`SquadFolderPath` 必须是 `squad init` 初始化过的根目录，且包不会替你校验路径存在。

如果你的项目已经基于 MAF，想要一个随使用越变越懂你领域、又不用反复改写提示词的多智能体编排，`Squad.Agents.AI` 是目前最便宜的上车路径：框架的工作 MAF 团队做了，团队的工作 Squad 做了，中间的缝只有一次 DI 调用。包仍在预览阶段，API 可能变化，生产使用前建议盯一下仓库的变更记录。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Building agent teams with Agent Framework, GitHub Copilot CLI and Squad（原文）](https://devblogs.microsoft.com/agent-framework/building-agent-teams-with-agent-framework-github-copilot-cli-and-squad/)
- [Squad 仓库（bradygaster/squad）](https://github.com/bradygaster/squad)
- [Squad.Agents.AI 包说明](https://github.com/bradygaster/squad/blob/dev/src/Squad.Agents.AI/README.md)
- [MS Learn：Agent Framework 的 GitHub Copilot 智能体](https://learn.microsoft.com/en-us/agent-framework/agents/providers/github-copilot)
- [GitHub Copilot SDK](https://github.com/github/copilot-sdk)
- [.NET 示例：Agent_With_GitHubCopilot](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/AgentProviders/github-copilot/Agent_With_GitHubCopilot)
- [Python 示例：github_copilot](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/providers/github_copilot)
