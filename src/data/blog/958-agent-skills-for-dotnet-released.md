---
pubDatetime: 2026-07-21T08:56:18+08:00
title: "Agent Skills for .NET 正式发布：可复用的 Agent 领域技能包"
description: "Microsoft Agent Framework 的 Agent Skills for .NET 已从实验性预览毕业，[Experimental] 标签移除，API 稳定。团队现在可以构建、独立发布和组合 Agent 技能包——包含指令、参考资料和脚本，agent 按需加载，附带生产级审批、沙箱和缓存控制。"
tags: [".NET", "Agent Framework", "Agent Skills", "AI Agent", "Microsoft"]
slug: "agent-skills-for-dotnet-released"
ogImage: "../../assets/958/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/agent-skills-for-net-is-now-released"
---

Agent Skills for .NET 在 Microsoft Agent Framework 中已从实验性预览毕业——`[Experimental]` 标签已移除，API 稳定。你现在可以给 .NET agent 提供可复用的领域专业知识包——包含指令、参考文档和脚本，agent 只在任务需要时才加载。

## Agent Skills 是什么

Agent Skills 是一种开放格式，用于打包 agent 按需发现和使用的领域专业知识。每个 skill 包含元数据和指令——对基于文件的 skill 来说是 `SKILL.md` 文件，对代码定义的 skill 来说是等价属性——可选附带脚本、参考文档和其他资源。

Agent 只在需要时加载它需要的东西，通过四阶段渐进式暴露保持上下文窗口精简：广播 skill 名称 → 加载指令 → 读取资源 → 运行脚本。

结果是 agent 获得专业化能力，却不膨胀其核心指令或上下文窗口——而你写一次专业能力，就能在所有需要它的 agent 之间复用。

## 你能用它做什么

**统一执行企业策略**：把公司的 HR 政策、报销规则或 IT 安全指引打包成 skill。面向员工的 agent 在有人问"协同办公空间能报销吗"时加载对应政策 skill，直接从政策本身回答。每个员工得到同样的、可审计的基于原文的回答。

**把支持手册变成可重复的工作流**：把支持团队的故障排查指南变成 skill。客户报告问题时，agent 加载匹配的手册并遵循文档步骤——无论哪个 agent 实例处理请求，解决方案保持一致。

**组合来自多个团队的 skill**：不同团队可以独立编写和维护 skill——作为共享仓库里的文件目录，或作为内部 NuGet 源的包——你无需跨团队协调就能组合进一个 agent。Agent 根据每个 skill 的描述决定用哪个；你不需要写路由逻辑。

## 三种编写方式

发布版支持三种编写风格，各团队按自己的工作方式选择。三种方式接入同一个 provider，agent 在运行时对它们一视同仁：

- **基于文件的 skill**：一个包含 `SKILL.md`、可选脚本和参考文档的目录。适合放在共享仓库里、由非开发者或跨职能团队维护的 skill。
- **基于类的 skill**：C# 类打包指令、资源和脚本，可通过标准 .NET 工作流分发，包括内部 NuGet 包。
- **代码定义的 skill**：直接在应用代码里创建的 skill。适合需要动态生成或绑定应用状态的场景。

## 为生产环境构建

给 agent 新能力只有在你能治理它怎么用时才有价值。这个版本包含了在产线运行 skill 所需的控制：

- **人在回路审批**：skill provider 暴露三个 agent 调用的工具——`load_skill`（加载指令）、`read_skill_resource`（读资源）、`run_skill_script`（跑脚本）。三者默认都需要审批，没有人在回路就不能加载或执行。对可信操作可选择性放宽。
- **受控脚本执行**：基于类和代码定义的 skill 脚本在进程内运行。文件式脚本交给你自己提供的 runner，你控制沙箱、资源限制和审计日志。
- **过滤**：只向特定 agent 暴露共享 skill 库中精选的子集，可通过可感知请求 agent 或租户的谓词做上下文判断。
- **缓存**：skill 解析一次后复用，可选的 per-key 隔离让一个 provider 向不同 agent 或租户提供不同 skill 集。
- **可扩展源管道**：底层源类现在是公开的，当 builder 不满足需求时可以组合自定义管道或从自己的注册中心集成 skill。

## 快速上手

```csharp
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;

var skillsProvider = new AgentSkillsProvider(
    Path.Combine(AppContext.BaseDirectory, "skills"),
    SubprocessScriptRunner.RunAsync);

AIAgent agent = new AzureOpenAIClient(
        new Uri(endpoint), new DefaultAzureCredential())
    .GetResponsesClient()
    .AsAIAgent(new ChatClientAgentOptions
    {
        Name = "MyAgent",
        ChatOptions = new() {
            Instructions = "You are a helpful assistant." },
        AIContextProviders = [skillsProvider],
    },
    model: deploymentName);

AgentResponse response = await agent.RunAsync(
    "Help me with onboarding.");
Console.WriteLine(response.Text);
```

## 为什么重要

Agent Skills 给了你一个标准方式来打包、分发和治理 agent 的领域专业知识。团队独立编写 skill，builder 把它们组合进一个 provider，审批机制让任何重要操作都有人在回路。现在 .NET API 已经稳定发布，你可以在生产环境上构建，不再需要应对实验性 API 的变动。

## 参考

- [原文：Agent Skills for .NET Is Now Released](https://devblogs.microsoft.com/agent-framework/agent-skills-for-net-is-now-released/)
- [Agent Skills 文档](https://learn.microsoft.com/en-us/agent-framework/agents/skills)
- [GitHub 示例](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/AgentSkills)
- [Agent Skills 规范](https://agentskills.io)
