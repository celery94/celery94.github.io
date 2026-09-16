---
pubDatetime: 2026-09-16T07:39:00+08:00
title: "用 GitHub Copilot SDK 接进 .NET 应用"
description: "Copilot SDK 已 GA，把 Copilot CLI 的 agent 运行时搬进你自己的应用。本文拆开 SDK、Agent Framework 与应用三层职责，讲清工具暴露和工具批准两套开关，以及认证、额度与数据留存的实际边界。"
tags: ["GitHub Copilot", "AI Agent", ".NET", "MCP", "架构"]
slug: "github-copilot-sdk-interview-coach-app"
ogImage: "../../assets/1071/01-cover.jpg"
source: "https://devblogs.microsoft.com/blog/build-an-interview-coach-app-with-the-github-copilot-sdk"
---

假设你已经有一个跑在 Microsoft Foundry 上的多 agent 应用：五个分工不同的角色用 handoff 串起来，工具通过 MCP 调用，界面是 Blazor。现在你想让它在 Copilot 订阅下也能跑——需要改多少代码？

微软的 Justin Yoo 在 [Build an interview coach app with the GitHub Copilot SDK](https://developer.microsoft.com/blog/build-an-interview-coach-app-with-the-github-copilot-sdk/) 里给出的答案是：如果抽象层选对了，只需要换一个 provider。他用一个 .NET 示例 Interview Coach 演示了这件事：同一套 specialist 提示词、同一套 MCP 工具、同一个界面，Copilot 作为另一个模型来源接进来。

真正值得学的是这个「只换一层」是怎么做到的，以及在换的过程中，哪些边界必须重新声明。

## Copilot SDK 到底是什么

[GitHub Copilot SDK](https://github.com/github/copilot-sdk) 暴露的是 Copilot CLI 背后那套引擎：一个已经投产的 agent 运行时，可以通过代码调用。它的官方定位很直白——「Agents for every app」，你定义 agent 行为，Copilot 负责规划、工具调用等环节。

几个当前事实值得先确认：

- SDK 已经 GA，并遵循语义化版本。截至本文核对时，[`GitHub.Copilot.SDK`](https://www.nuget.org/packages/GitHub.Copilot.SDK) 最新稳定版是 1.0.13，Agent Framework 侧的适配包 `Microsoft.Agents.AI.GitHub.Copilot` 是 1.21.0。
- 官方提供 Node.js、Python、Go、.NET、Java、Rust 六种语言。其中 Node.js、Python、.NET 三个 SDK 会**自动带上 Copilot CLI 运行时**，不需要你另外安装 CLI。
- 所有 SDK 都通过 JSON-RPC 与 Copilot CLI 的服务模式通信，SDK 负责管理 CLI 进程的生命周期。你也可以连接一个已经跑起来的外部 CLI，用于调试或让多个客户端共享同一个服务端。
- .NET 包在构建时会按 RID 下载对应版本的 CLI 运行时，并用该发布版本的 `SHA256SUMS.txt` 校验；在受限环境里可以用 MSBuild 属性换镜像地址或直接指定本地二进制。

对应用开发者来说，它的价值不是「多一个模型供应商」，而是**复用一套 agent 运行时**：规划、工具调用循环、流式事件、会话与上下文压缩这些事你不用自己写。官方文档明确说不需要自己搭 orchestration。

## 三层职责，各管一件事

示例 Interview Coach 的结构是：Blazor 前端把消息发给 .NET agent 服务的 `/ag-ui` 端点，Agent Framework 运行选中的 agent 或 handoff 工作流，模型提出工具调用，应用代码通过 MCP 客户端执行，结果回给模型再流式返回前端。

这里有三层，职责不重叠：

| 层              | 负责什么                                               |
| --------------- | ------------------------------------------------------ |
| Copilot SDK     | 模型交互、工具调用循环、会话生命周期                   |
| Agent Framework | 把 specialist 表示成 `AIAgent`，管理它们之间的 handoff |
| 应用程序        | 界面、业务流程、面试提示词、工具实现                   |

原文把这句写得很准：Copilot 负责一个 specialist 的模型交互与工具执行，Agent Framework 负责连接 specialist 并管理交接，应用指令描述面试本身该怎么做。

所以「换 provider」之所以只动一处，是因为 Copilot 通过适配器参与了同一个 `AIAgent` 接口。`behavioural_interviewer` 的提示词里写着要用 STAR 方法（Situation、Task、Action、Result）、一次问一个问题、给出反馈并记录对话——这些不需要因为底层换模型而改写。Foundry 那条路径也保留着，两者是并列的 provider 选择。

适配器的形状很短：

```csharp
private static AIAgent CreateCopilotRunAgent(
    CopilotClient client,
    string name,
    string description,
    string? model,
    string instructions,
    IList<AITool>? tools)
{
    return client.AsAIAgent(
        CreateCopilotSessionConfig(model, instructions, tools),
        ownsClient: false,
        name: name,
        description: description);
}
```

`ownsClient: false` 是关键的一行：包装出来的 agent 不接管共享 `CopilotClient` 的所有权，客户端生命周期仍由应用管理。如果这里用默认值，每次创建 agent 都会让包装层以为自己该负责销毁客户端。

## 给 Copilot 面试工具，而不是一个编码环境

这是整套设计里最容易被跳过、又最该看仔细的一段。

Copilot CLI 本身带着 shell、文件读写、抓取 URL 这些能力。一个面试教练没有理由执行 shell 命令，也不需要改应用的源码。示例的做法是在**创建客户端时**就把模式收窄：

```csharp
builder.Services.AddSingleton(_ => new CopilotClient(new CopilotClientOptions
{
    BaseDirectory = Path.Combine(Path.GetTempPath(), "interview-coach-copilot"),
    GitHubToken = githubToken,
    Mode = CopilotClientMode.Empty,
    UseLoggedInUser = string.IsNullOrWhiteSpace(githubToken),
}));
```

`CopilotClientMode.Empty` 让内置的 shell、文件系统和编码工具保持关闭，agent 只能用适配器显式交给它的工具。示例的 provider 说明里也确认了这一点。

然后在会话配置里只列出自己的工具：

```csharp
internal static SessionConfig CreateCopilotSessionConfig(
    string? model,
    string instructions,
    IList<AITool>? tools)
{
    var copilotTools = ToCopilotTools(tools);

    return new SessionConfig
    {
        AvailableTools = copilotTools.Select(tool => $"custom:{tool.Name}").ToList(),
        Model = string.IsNullOrWhiteSpace(model) ? Constants.DefaultModel : model,
        OnPermissionRequest = PermissionHandler.ApproveAll,
        SystemMessage = new SystemMessageConfig
        {
            Mode = SystemMessageMode.Append,
            Content = instructions,
        },
        Tools = copilotTools,
    };
}
```

三个字段各管一件事：`Tools` 提供自定义工具的定义和可调用处理器；`AvailableTools` 说明这个 agent 允许用哪些工具；`custom:` 前缀用来选中你提供的这些工具，而不是 Copilot CLI 的内置工具。`SystemMessage.Mode = Append` 表示把面试指令追加到系统提示后面，而不是整段替换。

这里有个命名规则容易踩坑，值得单独记住：通过 `McpServers` 配置的 MCP 工具，其运行时名字是 `<server-key>-<tool-name>`；在 `AvailableTools` 和 `ExcludedTools` 里应该用带来源限定的 `mcp:<server-key>-<tool-name>`。而 `CustomAgents[].Tools` 和 `DefaultAgent.ExcludedTools` 里则直接用 `<server-key>-<tool-name>`。示例之所以用 `custom:`，是因为它的 MCP 工具是通过 Agent Framework 的 `AITool` 列表交进来的，不是走 `SessionConfig.McpServers`。

## 「给了哪些工具」和「批不批准」是两套开关

原文有一句值得展开的判断：工具选择控制的是暴露面，但它不是一条完整的安全边界。这句话背后其实是两层机制，官方资料分开写，读的时候很容易混起来。

**第一层是暴露。** Copilot SDK 的 FAQ 写得很直接：默认情况下，SDK 会暴露 Copilot CLI 的一手工具，效果类似用 `--allow-all` 跑 CLI；工具执行仍然受各 SDK 的权限处理器约束，应用可以批准、拒绝或自定义。也就是说，**默认的「可用工具集」是宽的**。

**第二层是批准。** 每次工具执行前都会问 `OnPermissionRequest`；如果不提供处理器，权限请求会作为事件抛出来挂起，等消费方自己解决。Agent Framework 的 Copilot provider 文档因此从另一个角度描述同一件事：默认情况下 agent 不能执行 shell 命令、读写文件或抓取 URL，要开启这些能力得通过 `SessionConfig` 提供权限处理器。

两句话不矛盾，但含义完全不同：一个说「默认暴露得很多」，另一个说「默认什么也执行不了」。把两层分开看就清楚了——**暴露决定有哪些工具摆在桌面上，批准决定每一次调用要不要放行。**

示例的选择是：暴露层收得很紧（`CopilotClientMode.Empty` 加一份显式工具清单），批准层放得很松（`PermissionHandler.ApproveAll`）。这组合在示例里是合理的，因为它已经确保桌面上只有自己的工具；但它也说明为什么原文特别提醒「工具选择不是完整的安全边界」：如果哪天有人在 `AvailableTools` 里放进了内置工具，`ApproveAll` 会一并放行，权限层不会帮你兜住。

真要收紧，抓手有三个：

- 把 `PermissionHandler.ApproveAll` 换成自定义处理器，按 `PermissionRequest` 的具体类型判断。示例所属框架的文档给了一个可直接抄的形状：匹配 `PermissionRequestShell` 就拒绝，其余批准一次。
- 用 `ApprovalRequiredAIFunction` 包住敏感工具。Agent Framework 会把这种工具转成 `OnPreToolUse` 上的 `ask`，交回你的 `OnPermissionRequest` 决策。
- 注意 `ApproveAll` 的适用条件：它只在托管设置（managed settings）关闭时有效，如果 `EnableManagedSettings` 为 true，第一次权限请求就会抛异常。另外，如果你自己提供了 `OnPreToolUse` 钩子，Agent Framework 就不会再装默认的审批钩子，此时每个标了审批必需的工具有没有真的被拦住，责任全在你。

## handoff 要在运行期补齐工具

Agent Framework 的 handoff 是网状拓扑，没有中心调度器，每个 agent 自己决定何时把控制权交出去。示例把五个角色串成一条主链，`triage` 既是入口也是兜底：

```csharp
var workflow = AgentWorkflowBuilder
    .CreateHandoffBuilderWith(triageAgent)
    .WithHandoffs(triageAgent, [receptionistAgent, behaviouralAgent, technicalAgent, summariserAgent])
    .WithHandoffs(receptionistAgent, [behaviouralAgent, triageAgent])
    .WithHandoffs(behaviouralAgent, [technicalAgent, triageAgent])
    .WithHandoffs(technicalAgent, [summariserAgent, triageAgent])
    .WithHandoff(summariserAgent, triageAgent)
    .Build();
```

五个角色和它们各自的工具范围：

| Agent                     | 职责                       | 可用的 MCP 工具           |
| ------------------------- | -------------------------- | ------------------------- |
| `receptionist`            | 收集文档、建立会话         | MarkItDown、InterviewData |
| `behavioural_interviewer` | 问经历类问题并反馈         | InterviewData             |
| `technical_interviewer`   | 问岗位相关问题并讨论       | InterviewData             |
| `summariser`              | 复盘记录并产出最终反馈     | InterviewData             |
| `triage`                  | 路由初始对话、处理方向变更 | 无                        |

MarkItDown 把文档转成 agent 能用的文本，InterviewData 提供创建、读取、更新面试记录的操作。五个角色的 MCP 客户端按 key 注册（`mcp-markitdown`、`mcp-interview-data`），工具在启动时通过 `ListToolsAsync()` 一次性取回。

问题出在这里：**handoff 的交接工具是运行期注入的，不是静态工具。** Agent Framework 在调用某个 agent 时会额外提供转移控制权的工具和附加指令；如果只把初始的 MCP 工具交给 Copilot，这些交接能力就丢了。

示例的适配器用一个包装层解决：每次调用时重新创建轻量 agent 包装，把静态工具和运行期工具合并后再交给 Copilot。源码里的注释写得很清楚——handoff orchestration 通过 `ChatClientAgentRunOptions` 提供转移工具，而 Copilot 适配器当前会忽略这些 run options，所以需要按调用重建。

```csharp
internal static IList<AITool> MergeCopilotTools(
    IList<AITool>? configuredTools,
    AgentRunOptions? options)
{
    var runTools = (options as ChatClientAgentRunOptions)?.ChatOptions?.Tools;

    return (configuredTools ?? [])
        .Concat(runTools ?? [])
        .DistinctBy(tool => tool.Name, StringComparer.Ordinal)
        .ToList();
}
```

`MergeCopilotInstructions` 做同样的事，把运行期指令追加到 specialist 的提示词末尾——`triage` 的初始指令需要它才能知道之前已经走到哪一步。合并后的工具按名字去重，避免同一个工具被交两次。这套处理对普通响应和流式响应都生效。

原文对这件事的定性很克制，也值得照抄这个态度：它描述的是 commit `68fd993` 那一版实现，而仓库使用浮动包版本，所以这是「这一版实现需要适配器兜底」，不等于每个 Copilot SDK 版本都有这个限制。集成运行时和编排框架时，值得先确认框架在调用时到底注入了什么。

还有一点：`AgentWorkflowBuilder` 的这类构建 API 在示例里是关掉 `MAAIW001` 警告使用的，注释写明该类型仅用于评估、可能变更或被移除。把 handoff 编排用在生产前，要先确认它对当前版本的稳定承诺。

## 我把示例用到的 API 形状编译验证了一遍

我没有在本机跑起整套示例——它需要容器引擎、Aspire CLI，以及一个 Cosmos DB 模拟器容器。我做的验证范围更小但更硬：把示例和原文用到的关键 API 形状抄进一个 `net10.0` 控制台项目，装上当前版本（`GitHub.Copilot.SDK` 1.0.13、`Microsoft.Agents.AI.GitHub.Copilot` 1.21.0、`Microsoft.Agents.AI.Workflows` 1.21.0），编译结果为 **0 个错误**。

覆盖到的形状包括：`CopilotClientOptions` 的 `BaseDirectory`／`GitHubToken`／`Mode`／`UseLoggedInUser`，`CopilotClientMode.Empty`，`SessionConfig` 的 `AvailableTools`／`Tools`／`Model`／`OnPermissionRequest`／`SystemMessage`，`PermissionHandler.ApproveAll`，`client.AsAIAgent(config, ownsClient: false, name:, description:)`，以及 `AgentWorkflowBuilder` 的 `CreateHandoffBuilderWith`／`WithHandoffs`／`WithHandoff`／`Build` 链式调用。我为验证写的是等价简化版（工具声明部分直接做了类型转换），没有连接 Copilot 运行时，也没有消耗账号的 Copilot 额度。

这条路径本身也值得说清楚：**原文的代码片段与仓库源码能对上，并且在当前包版本上仍然可编译。** 这是「照着抄不会立刻报错」的最低保证，不等于整套示例的运行时行为已被我复现。

## 自己接一下：最小路径

如果你想先确认这条路走得通再动大工程，官方的 [getting started](https://github.com/github/copilot-sdk/blob/main/docs/getting-started.md) 给了一个五行版本的起点。

前置条件：

- 一个拥有 Copilot 访问权限的 GitHub 账号（SDK 需要 Copilot 订阅，除非你走 BYOK 自带密钥）。
- .NET SDK（.NET 包本身面向 .NET Standard 2.0 兼容实现，.NET SDK 会在构建时带上 CLI 运行时，不需要单独装 CLI）。
- 本地认证：执行 `gh auth login` 并确认 `gh auth status` 正常。

```bash
dotnet new console -n CopilotDemo
cd CopilotDemo
dotnet add package GitHub.Copilot.SDK
```

把 `Program.cs` 换成：

```csharp
using GitHub.Copilot;

await using var client = new CopilotClient();
await using var session = await client.CreateSessionAsync(new SessionConfig
{
    Model = "auto",
    OnPermissionRequest = PermissionHandler.ApproveAll
});

var response = await session.SendAndWaitAsync(new MessageOptions { Prompt = "What is 2 + 2?" });
Console.WriteLine(response?.Data.Content);
```

`dotnet run` 之后应该看到输出 `4`。这一步验证的是「客户端能启动 CLI 运行时、能认证、能完成一次会话」，不涉及你自己的工具和界面。

跑通之后，按顺序加三样东西，每样都能独立验证：

1. **加流式**：设置 `Streaming = true`，订阅 `AssistantMessageDeltaEvent` 累积 `DeltaContent`，用 `SessionIdleEvent` 判断这一轮结束。预期结果是回答逐字出现，而不是等完整文本。
2. **加一个自定义工具**：用 `CopilotTool.DefineTool` 定义 `get_weather`，放进 `SessionConfig.Tools`。预期结果是问天气时 Copilot 会调用你的代码，并把返回值写进回答。
3. **改成项目里的形态**：把 `CopilotClientMode.Empty` 和 `AvailableTools` 加上，确认内置工具不再出现在桌面上。

常见的两个失败：

- **`401 Bad credentials`**：多半是配置里的显式 token 覆盖了本来能用的本地登录。先列一下用户机密，把过期的 token 覆盖项删掉，再确认 `gh auth status`。另外自动化场景建议用 `COPILOT_GITHUB_TOKEN`，并使用细粒度的 `github_pat_`、OAuth 用户令牌或 GitHub App 用户令牌，而不是经典的 `ghp_` 个人访问令牌。
- **模型不可用**：可用模型取决于 Copilot 套餐和组织策略。应用默认用 `gpt-5-mini`；需要确认账号能用哪些模型时，用 `CopilotClient.ListModelsAsync()` 查询，而不是照抄文档里的模型名。

## 跑整套示例要多准备什么

Copilot 路径的认证可以完全依赖本地已登录的 GitHub 凭据，也可以显式配置 token；配置了 token 就走 token。这条路径不需要额外的 Foundry 模型部署。

但其他服务还是要有：

- Aspire 启动各组件。
- MarkItDown 和本地 Cosmos DB 模拟器跑在容器里。
- InterviewData 现在用 Cosmos DB 存面试记录，取代了早先的 SQLite 存储；agent 仍然通过 MCP 访问记录。
- 保留 Foundry 配置的话，Aspire 会连资源带模型部署一起提供，Azure 访问用 `DefaultAzureCredential` 而不是 API key。

启动命令（仓库根目录、容器引擎已运行）：

```bash
aspire start --apphost ./apphost.cs -- --provider GitHubCopilot --mode HandOff
```

`--mode Single` 可以跑单 agent 版本，作为更简单的基线。**但要先看一眼 `apphost.settings.json`**：仓库 README 明确警告，默认 AppHost 会声明一个 Foundry 资源和模型部署，也就是说一次本地运行可能创建可计费的 Azure 资源。选 Copilot provider 能避开模型部署，但资源清单和环境清理这件事仍要自己确认。

另一个我在仓库里核实到的细节：DevUI 在 `Program.cs` 里是**刻意**对所有环境开放的，`AddDevUI(options => options.AllowRemoteAccess = true)` 和 `app.MapDevUI()` 两处都带着「便于在生产场景里检查 agent 状态」的注释。原文提到它把 DevUI 暴露到了开发环境之外，代码里的意图比这更明确——它是故意的，所以更要靠访问控制而不是环境判断来保护。

## 成本、数据和选型边界

这几条决定了它能不能用在真实场景，而不是 demo。

**额度计费。** SDK 请求按 Copilot CLI 的同一套模型计费：每个 prompt 都算进你账号的额度。可用模型与访问权限取决于套餐和组织策略。有现成的 Copilot 访问权限是个现实的好处，但它不等于无限或免费，也不等于给一个多用户的公开应用提供了认证设计方案。多租户和服务端部署是另一套题目，SDK 文档有单独的章节。

**数据留存。** 上传的文档字节留在 agent 进程的内存里：示例的上传端点把文件存进一个 `ConcurrentDictionary`，限制 10 MB，只接受 `.pdf`、`.docx`、`.doc`、`.txt`、`.md`、`.html`。UI 把返回的 URL 放进对话，MarkItDown 再从自己的容器去抓这个地址。进程重启，这些字节就没了；面试记录本身在 Cosmos 里，但界面消息列表和会话 ID 存在服务端 Blazor 线路（circuit）内存中，刷新页面会新建线路和会话。

**恢复与访问控制。** 示例没有实现完整的工作流恢复。仓库的架构文档把边界写得很直接：这是一个学习示例，要用在受限环境里，配合虚构输入；工具只操作传入的 ID，文档解析出来的内容是**不可信输入**。要处理真实简历，先做三件事——限制应用和开发工具的访问、复核每个工具的实际权限、定下数据留存策略。

**什么时候这套设计合适。** 如果缺的是一个进程内的 agent 运行时，你希望复用现成的 Copilot 访问权限，并且能接受额度按 prompt 计费、模型可用性受组织策略约束，那么「SDK 管运行时、Agent Framework 管编排、应用管行为」这三层切分很干净，换 provider 的成本也低。

如果需求是给大量外部用户提供稳定配额的服务，或者要求数据不出境、不能进第三方运行时，或者需要持久化的工作流恢复和精确的审计链路，那就该把模型来源和编排放在你能控制的基础设施里，而不是复用个人或组织的 Copilot 额度。

## 结论

把 Copilot 接进自己的 .NET 应用，代码改动可以很小，但边界必须重新声明一遍：暴露层用 `CopilotClientMode.Empty` 加显式工具清单决定桌面上有什么，批准层用权限处理器决定每一次调用放不放行，这两件事不要混成一件。handoff 这类由框架在运行期注入的工具和指令，需要在适配器里补齐。额度、模型可用性和数据留存都是真实约束，示例仓库自己也是这么标注的。

最省事的下一步：先用 `dotnet new console` 加一个 `GitHub.Copilot.SDK` 跑通「问一句、答一句」，确认认证和额度都没问题，再决定要不要把现有的 `AIAgent` 抽象指向 Copilot。

如果你也在做 AI 助手、开发工具或 .NET 工程实践，Aide Hub 会继续分享这类「先划清边界、再写集成」的落地经验。

## 参考

- [Build an interview coach app with the GitHub Copilot SDK — Justin Yoo, Microsoft for Developers](https://devblogs.microsoft.com/blog/build-an-interview-coach-app-with-the-github-copilot-sdk)
- [GitHub Copilot SDK 仓库（README、getting started、架构与认证文档）](https://github.com/github/copilot-sdk)
- [Copilot SDK for .NET API 参考](https://github.com/github/copilot-sdk/blob/main/dotnet/README.md)
- [Interview Coach 示例源码](https://github.com/Azure-Samples/interview-coach-agent-framework)
- [Interview Coach 架构参考](https://github.com/Azure-Samples/interview-coach-agent-framework/blob/main/docs/ARCHITECTURE.md)
- [Interview Coach 的 GitHub Copilot 配置指南](https://github.com/Azure-Samples/interview-coach-agent-framework/blob/main/docs/providers/GITHUB-COPILOT.md)
- [Agent Framework 的 GitHub Copilot provider](https://learn.microsoft.com/en-us/agent-framework/agents/providers/github-copilot)
- [Agent Framework 的 handoff 编排](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff)
- [Copilot SDK 认证说明](https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/authenticate)
- [GitHub Copilot 用量与计费](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing)
