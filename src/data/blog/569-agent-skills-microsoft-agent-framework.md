---
pubDatetime: 2026-03-03
title: "用 Agent Skills 给你的智能体注入领域专业知识"
description: "Microsoft Agent Framework 新推出 FileAgentSkillsProvider，支持在运行时动态加载 Agent Skills，让智能体按需获取领域知识，无需修改核心指令，同时通过渐进式披露机制有效控制上下文窗口消耗。"
tags: ["AI Agents", "Microsoft Agent Framework", "Semantic Kernel", ".NET", "Python"]
slug: "agent-skills-microsoft-agent-framework"
source: "https://devblogs.microsoft.com/semantic-kernel/give-your-agents-domain-expertise-with-agent-skills-in-microsoft-agent-framework"
---

你有没有遇到这种情况：一个智能体需要同时处理报销审批、会议记录、安全合规三类任务，结果你把所有策略文档都塞进系统提示里，context 窗口用了大半，而 90% 的对话根本用不到这些内容？

这个问题现在有了正经的解法。Microsoft Agent Framework 新推出的 `FileAgentSkillsProvider`，让智能体可以在运行时按需发现并加载 Agent Skills，只在需要的时候才把相关领域知识拉进上下文。

## Agent Skills 是什么格式

Agent Skills 是一种简单的开放格式，核心是一个 `SKILL.md` 文件。这个 Markdown 文件用 YAML frontmatter 描述技能的名称和用途，正文则是具体的步骤指令。技能目录还可以包含可选的脚本、参考文档和静态资源：

```
expense-report/
├── SKILL.md                          # 必选 — frontmatter + 指令
├── scripts/
│   └── validate.py                   # 智能体可执行的代码
├── references/
│   └── POLICY_FAQ.md                 # 按需加载的参考文档
└── assets/
    └── expense-report-template.md    # 模板和静态资源
```

`SKILL.md` 只有 `name` 和 `description` 是必填的，其余字段都是可选的：

```yaml
---
name: expense-report
description: >-
  File and validate employee expense reports according to company policy.
  Use when asked about expense submissions, reimbursement rules, or spending limits.
license: Apache-2.0                   # 可选
compatibility: Requires python3       # 可选
metadata:                             # 可选
  author: contoso-finance
  version: "2.1"
---

## Instructions

1. Ask the employee for their receipt and expense details...
2. Validate against the policy in references/POLICY_FAQ.md...
```

`description` 字段非常关键——智能体正是靠它来判断什么时候该加载这个技能，所以描述里要说清楚技能做什么，以及何时应该用它。

## 渐进式披露：context 效率的关键

Agent Skills 的设计核心是**渐进式披露（Progressive Disclosure）**，技能内容分三个阶段进入上下文：

**广告阶段（~100 tokens/技能）**：技能名称和描述注入系统提示，智能体知道有哪些技能可用。

**加载阶段（建议 < 5,000 tokens）**：当某个任务匹配某个技能时，智能体调用 `load_skill` 拉取完整的 `SKILL.md` 指令。

**资源读取阶段（按需）**：智能体调用 `read_skill_resource` 获取技能包里附带的参考文档、模板或资产，只在真正需要时才发起请求。

这三段式设计让上下文窗口保持精简，同时在需要时提供完整的领域知识深度。如果你的智能体覆盖十几个不同领域，这个机制能大幅压低每次对话的 token 消耗。

## 创建一个技能

最简单的技能就是一个包含 `SKILL.md` 的文件夹：

```
skills/
└── meeting-notes/
    └── SKILL.md
```

```yaml
---
name: meeting-notes
description: >-
  Summarize meeting transcripts into structured notes with action items.
  Use when asked to process or summarize meeting recordings or transcripts.
---

## Instructions

1. Extract key discussion points from the transcript.
2. List any decisions that were made.
3. Create a list of action items with owners and due dates.
4. Keep the summary concise — aim for one page or less.
```

不需要脚本，不需要额外文件。需要扩展的时候再往里加 `references/`、`scripts/`、`assets/` 目录即可。如果嫌手写麻烦，还可以用 [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) 技能交互式生成新技能。

## 与智能体连接

`FileAgentSkillsProvider` 负责从文件系统目录发现技能，将其作为上下文提供者接入智能体。它会递归搜索配置路径（最多两级深度）查找 `SKILL.md` 文件，验证格式和资源后，把技能名称和描述注入到系统提示里。同时，它向智能体暴露两个工具：

- `load_skill`：当智能体判断用户请求匹配某个技能域时，调用此工具获取完整的 `SKILL.md` 指令，从而获得处理该任务的详细步骤指导。
- `read_skill_resource`：获取技能包里附带的补充文件（参考资料、模板、资产），让智能体在需要时拉取额外上下文。

## 在 .NET 中使用

```bash
dotnet add package Microsoft.Agents.AI --prerelease
dotnet add package Microsoft.Agents.AI.OpenAI --prerelease
dotnet add package Azure.AI.OpenAI --prerelease
dotnet add package Azure.Identity
```

配置 Provider 并创建智能体：

```csharp
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using OpenAI.Responses;

// 从 'skills' 目录发现技能
var skillsProvider = new FileAgentSkillsProvider(
    skillPath: Path.Combine(AppContext.BaseDirectory, "skills"));

// 创建带技能提供者的智能体
AIAgent agent = new AzureOpenAIClient(
    new Uri(endpoint), new DefaultAzureCredential())
    .GetResponsesClient(deploymentName)
    .AsAIAgent(new ChatClientAgentOptions
    {
        Name = "SkillsAgent",
        ChatOptions = new()
        {
            Instructions = "You are a helpful assistant.",
        },
        AIContextProviders = [skillsProvider],
    });

// 智能体自动发现并加载匹配的技能
AgentResponse response = await agent.RunAsync(
    "Summarize the key points and action items from today's standup meeting.");
Console.WriteLine(response.Text);
```

## 在 Python 中使用

```bash
pip install agent-framework --pre
```

```python
from pathlib import Path
from agent_framework import FileAgentSkillsProvider
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity.aio import AzureCliCredential

# 从 'skills' 目录发现技能
skills_provider = FileAgentSkillsProvider(
    skill_paths=Path(__file__).parent / "skills"
)

# 创建带技能提供者的智能体
agent = AzureOpenAIChatClient(credential=AzureCliCredential()).as_agent(
    name="SkillsAgent",
    instructions="You are a helpful assistant.",
    context_providers=[skills_provider],
)

# 智能体自动发现并加载匹配的技能
response = await agent.run(
    "Summarize the key points and action items from today's standup meeting."
)
print(response.text)
```

配置完成后，智能体自动发现可用技能，当用户的任务匹配某个技能域时就会调用它。你不需要写任何路由逻辑，智能体自己从系统提示中读取技能描述，自行决定何时加载。

## 实际能解决哪些问题

**企业合规场景**：把公司 HR 政策、报销规则、IT 安全指南打包成技能。员工问"可以报销共享办公空间吗"时，智能体加载对应的政策技能，给出准确的、有政策依据的回答，而不需要把所有政策一直挂在上下文里。

**客户支持场景**：把支持团队的排障指南做成技能。客户反馈问题时，智能体加载对应的操作手册并按文档步骤处理，不管哪个智能体实例接单，处理方式都保持一致。

**多团队技能库**：不同团队可以独立维护自己的技能，用 `FileAgentSkillsProvider` 同时指向多个目录来合并使用：

```csharp
// .NET
var skillsProvider = new FileAgentSkillsProvider(
    skillPaths: [
        Path.Combine(AppContext.BaseDirectory, "company-skills"),
        Path.Combine(AppContext.BaseDirectory, "team-skills"),
    ]);
```

```python
# Python
skills_provider = FileAgentSkillsProvider(
    skill_paths=[
        Path(__file__).parent / "company-skills",
        Path(__file__).parent / "team-skills",
    ]
)
```

每个路径可以指向单个技能文件夹，也可以指向包含多个技能子目录的父目录。

## 安全方面要注意

把技能当作开源依赖来对待——只使用来自可信来源的技能，加入智能体之前先审查内容。技能指令会注入到智能体的上下文中，能影响其行为，所以引入新包时该有的尽职调查，引入新技能时同样要做。

## 接下来的方向

团队计划在框架里继续扩展 Agent Skills 的支持，即将推出的功能包括：

- **程序化技能（Programmatic skills）**：通过 API 动态创建和注册技能，支持运行时生成或修改技能的场景，而不局限于静态文件。
- **技能执行（Agent skill execution）**：支持智能体执行技能包内的脚本，让技能从单纯的指令和参考资料扩展到主动执行代码。

相关资源：
- [Agent Skills 文档（Microsoft Learn）](https://learn.microsoft.com/en-us/agent-framework/agents/skills)
- [.NET 示例](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/AgentSkills)
- [Python 示例](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/skills/basic_skill)
