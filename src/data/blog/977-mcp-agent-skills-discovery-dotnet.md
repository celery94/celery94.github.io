---
pubDatetime: 2026-07-28T23:14:41+08:00
title: "从 MCP 服务器发现 Agent Skills：.NET 中的一次发布、随处可用"
description: "Microsoft Agent Framework 新能力：Agent 可以从 MCP 服务器按需发现和加载 Agent Skills，技能作者只需发布一次。本文介绍 MCP 技能的工作机制、两种分发模式（skill-md 和 archive），以及如何在 .NET 项目中接入。"
tags: [".NET", "Agent Skills", "MCP", "Agent Framework"]
slug: "mcp-agent-skills-discovery-dotnet"
ogImage: "../../assets/977/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/discover-agent-skills-from-mcp-servers-in-net/"
---

你的 Agent 现在可以从 MCP 服务器上直接发现和加载 [Agent Skills](https://agentskills.io/) 了 —— 不用把技能文件夹打包进每个应用，也不用逐个部署拷贝。你只需要让 Agent 指向一个 MCP 服务器，它就会自动拉取所需的技能。

对技能作者来说，这意味着你可以在一处发布技能，让整个组织的 Agent 都自动获取。对团队管理者来说，费用政策、合规流程、数据分析手册这些领域知识，可以在服务器上统一维护、统一版本、统一推送，完全不碰应用代码。

这项能力通过 `Microsoft.Agents.AI.Mcp` NuGet 包提供，目前已在 .NET 中正式可用。

## 什么是 MCP 技能

Agent Skill 是一套可移植的指令、资源和脚本包，采用「渐进式信息披露」模式：Agent 先看到技能的简短摘要，只有当任务确实匹配时，才去加载完整指令和资源。

MCP 技能沿用了同样的模式，但技能本体存放在 MCP 服务器上，而不是本地磁盘或代码里。服务器通过 `skill://index.json` 这个发现文档来广告自己的技能，框架再通过已认证的 MCP 连接拉取对应的技能内容。

.NET 实现支持两种分发形式：

- **skill-md**：服务器把技能的 `SKILL.md` 和配套资源作为 MCP 资源暴露出来。框架在 Agent 加载技能时逐文件按需获取。
- **archive**：技能被打包成单个压缩包（ZIP、TAR 或 gzip 压缩的 TAR）。框架下载后，在受控目录里解压并对外提供解压后的文件。

两种形式通过同一套 Builder API 消费，你的 Agent 代码不关心技能到底以哪种方式打包。

## 这为什么重要

**一次发布，随处可用。** 平台或领域团队把技能发布到 MCP 服务器上。任何建立了连接的 Agent 都能获取 —— 不需要按 Agent 打包、不需要拷贝文件夹、不需要重新构建。

**更新技能不用重新部署 Agent。** 服务器上的技能内容变了，连接的 Agent 下次发现时自然拿到新版本。规则和手册在服务器上演进，不在下游的每个应用里各自维护。

**跨 Agent 的一致性。** 同样的技能、从同一个来源、到达每一个 Agent。这就是「每个团队各自维护一份费用政策」和「只有一份费用政策，所有人都用这份」之间的区别。

**远程内容有边界保护。** 通过 MCP 到达的技能保持了与本地技能相同的渐进式信息披露规范，并且对压缩包解压和脚本执行有明确的控制项（后面会细讲）。

> 注意：MCP 技能 API 目前是实验性的，未来版本可能会有调整。MCP 技能规范本身也还在演进中。

## 接入步骤

先安装 NuGet 包：

```bash
dotnet add package Microsoft.Agents.AI.Mcp --prerelease
```

连接到托管技能的 MCP 服务器，然后在 `AgentSkillsProviderBuilder` 上调用 `UseMcpSkills` 扩展方法将其注册为技能来源：

```csharp
using Microsoft.Agents.AI;
using ModelContextProtocol.Client;

// 连接到托管技能的 MCP 服务器
await using McpClient client = await McpClient.CreateAsync(
    new StdioClientTransport(new()
    {
        Name = "skills-server",
        Command = "dotnet",
        Arguments = [skillsServerPath, "--server"],
    }));

// 构建一个通过 MCP 发现技能的 skills provider
var skillsProvider = new AgentSkillsProviderBuilder()
    .UseMcpSkills(client)
    .Build();
```

把 provider 添加到 Agent 的 context providers 里，框架就会在 system prompt 里把服务器上的技能广告给 Agent，Agent 随后可以像对待本地技能一样加载和阅读它们：

```csharp
using Azure.AI.OpenAI;
using Azure.Identity;
using OpenAI.Responses;

AIAgent agent = new AzureOpenAIClient(
    new Uri(endpoint), new DefaultAzureCredential())
    .GetResponsesClient()
    .AsAIAgent(new ChatClientAgentOptions
    {
        Name = "SkillsAgent",
        ChatOptions = new()
        {
            Instructions = "You are a helpful assistant. " +
                "Use available skills to answer the user.",
        },
        AIContextProviders = [skillsProvider],
    },
    model: deploymentName);

AgentResponse response = await agent.RunAsync(
    "Summarize our expense reimbursement limits " +
    "for international travel.");
Console.WriteLine(response.Text);
```

Agent 在 system prompt 中看到技能广告，当用户请求匹配时，自动加载对应内容。对于 `skill-md` 类型的技能，框架在 Agent 加载技能时从服务器拉取 `SKILL.md`；对于 `archive` 类型，框架使用从服务器下载并本地解压的技能包。两种情况下，引用的资源都按需读取。

## 场景一：一个中心技能服务器服务多个 Agent

假设平台团队负责公司的运营知识 —— 费用政策、事件响应手册、数据分类指南。他们把这些以 `skill-md` 形式托管在 MCP 服务器上。财务助手、值班机器人和数据治理 Agent 都通过同一段 `UseMcpSkills(client)` 代码连接到同一台服务器。

三个 Agent 都没有把任何技能打包在自身内部。当平台团队在服务器上更新费用政策，三个 Agent 下一次发现时自动反映变更 —— 不需要跨团队协调发布。

而且，`UseMcpSkills` 是往 builder 里加一个 `source`，你可以把本地技能和服务器技能组合在同一个 provider 里：

```csharp
var skillsProvider = new AgentSkillsProviderBuilder()
    .UseFileSkill(Path.Combine(AppContext.BaseDirectory, "local-skills"))
    // 团队自有技能，在本地磁盘
    .UseMcpSkills(client)
    // 共享技能，来自服务器
    .Build();
```

这也覆盖了 [Microsoft Foundry Toolbox](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/skills?pivots=rest-api)：如果你的组织通过 Foundry Skills API 管理技能并把它们挂到 toolbox，`UseMcpSkills` 连接该 toolbox 的 MCP endpoint 的方式和连接任何其他 MCP 服务器完全一样。你在 Foundry 里编写和版本管理技能，.NET Agent 通过 MCP 发现它们，不需要额外的集成工作。

## 场景二：安全地分发压缩包技能

有些技能会捆绑多个参考文件 —— 模板、查找表、检查清单。以 `archive` 形式打包，服务器可以一次性把整套资源分发下去。

但压缩包解压意味着把远程内容写入本地磁盘，必须有安全边界：一个压缩包可能比预期更大、解压后急剧膨胀、或者包含超出预期的文件数量。没有限制的话，一个恶意或损坏的压缩包可能耗尽 Agent 所在机器的磁盘、内存或 CPU。

为此，`AgentMcpSkillsSourceOptions` 提供了一套选项，让你精确限定压缩包在解压和对外提供服务前允许消耗的资源上限：

```csharp
using Microsoft.Agents.AI;

var skillsProvider = new AgentSkillsProviderBuilder()
    .UseMcpSkills(client, new AgentMcpSkillsSourceOptions
    {
        ArchiveSkillsDirectory = Path.Combine(
            AppContext.BaseDirectory, "extracted-skills"),
        ArchiveMaxFileCount = 50,
        ArchiveMaxSizeBytes = 2 * 1024 * 1024,
        // 限制下载体积
        ArchiveMaxUncompressedSizeBytes = 4 * 1024 * 1024,
        // 限制解压后总大小
    })
    .Build();
```

三项限制各自防范一类攻击：

- `ArchiveMaxSizeBytes` 限制下载的压缩包大小，防范超大 payload。
- `ArchiveMaxUncompressedSizeBytes` 限制解压后的总大小，防范「压缩炸弹」—— 传输时很小、解压后膨胀到几个 G 的存档。
- `ArchiveMaxFileCount` 限制单个压缩包内允许的文件数量，防范过量文件的存档。

框架下载压缩包，校验是否在限制范围内，在 `ArchiveSkillsDirectory` 下解压，然后对外提供解压后的 `SKILL.md` 和资源。超出任一限制的压缩包会被跳过，不可信服务器无法利用技能分发来压垮宿主机。

还有一个重要的信任边界：**archive 类型的技能中捆绑的脚本永远不会被执行。** 从远程 MCP 服务器下载的可执行内容默认视为不可信 —— 框架会提供技能的指令和资源，但不会运行它的脚本。

技能治理模型的其他部分同样适用。`load_skill`、`read_skill_resource`、`run_skill_script` 等技能工具默认需要人工审批，在 Agent 行动之前给你一个检查点。

## 小结

MCP 技能把 Agent Skills 从「嵌入到每个应用里的东西」变成了「可以集中分发的基础设施」。一次编写，托管在 MCP 服务器上，让每个 Agent 按需发现 —— 集中更新、集中治理，不管以 `skill-md` 资源还是 `archive` 压缩包的形式到达，消费方式完全一致。

对要围绕共享领域知识构建多个 Agent 的团队来说，这就是从「维护无数份拷贝」到「维护一个源头」的区别。

## 参考

- [原文：Discover Agent Skills from MCP servers in .NET](https://devblogs.microsoft.com/agent-framework/discover-agent-skills-from-mcp-servers-in-net/)
- [MCP-based skills 文档](https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-csharp#mcp-based-skills)
- [MCP-based skills 示例](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/AgentSkills/Agent_Step06_McpBasedSkills)
- [Skills in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/skills?pivots=rest-api)
- [Agent Skills for .NET Is Now Released](https://devblogs.microsoft.com/agent-framework/agent-skills-for-net-is-now-released/)
- [Agent Skills in .NET: three ways to author](https://devblogs.microsoft.com/agent-framework/agent-skills-in-net-three-ways-to-author-one-provider-to-run-them/)
