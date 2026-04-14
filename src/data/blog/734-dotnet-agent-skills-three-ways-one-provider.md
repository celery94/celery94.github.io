---
pubDatetime: 2026-04-14T10:00:00+08:00
title: ".NET Agent Skills：三种编写方式，一个 Provider 统一运行"
description: "微软 Agent Framework 为 .NET 开发者提供了三种 Skill 编写方式：文件式、类继承式和内联代码式，通过 AgentSkillsProviderBuilder 将它们自由组合进同一个 Provider，并支持脚本执行审批等生产特性。本文以一个 HR 自助服务 Agent 为例，逐步演示如何灵活叠加这三种方式。"
tags: ["Agent Framework", ".NET", "AI Agent", "C#"]
slug: "dotnet-agent-skills-three-ways-one-provider"
ogImage: "../../assets/734/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/agent-skills-in-net-three-ways-to-author-one-provider-to-run-them"
---

微软 Agent Framework 最新更新为 .NET 开发者提供了一套更灵活的 Skill 编写模型：**文件式、类继承式、内联代码式**，三种方式可以自由混合，共用同一个 `AgentSkillsProvider`。这不是为了覆盖所有可能场景而堆出来的功能，它解决的是一个真实问题——团队不同步时，怎样让 Agent 的能力持续向前走。

![三种 Agent Skills 编写方式汇聚到统一 Provider](../../assets/734/01-cover.png)

## 场景：HR 自助服务 Agent 的演进

原文用了一个 HR 自助服务 Agent 来串联三种方式，这个例子足够具体，值得照用。

Agent 从一个单一的"入职引导"技能起步。几周后，HR 系统团队把"福利登记"技能打成 NuGet 包发布了，你想直接集成进来。同时，另一个"请假余额"技能已经在开发中，但这个 sprint 结束前不会发布，你需要先写一个临时实现桥接过去。等人家的包发布，再把自己的临时实现删掉。

这三步——每一步都对 Agent 是一次真实可用的改进，彼此都不干扰。

---

## 第一步：文件式 Skill，支持脚本执行

入职引导以一个目录形式存在：

```
skills/
└── onboarding-guide/
    ├── SKILL.md
    ├── scripts/
    │   └── check-provisioning.py
    └── references/
        └── onboarding-checklist.md
```

`SKILL.md` 是这个 Skill 的描述文件：

```
---
name: onboarding-guide
description: >-
  Walk new hires through their first-week setup checklist. Use when a new
  employee asks about system access, required training, or onboarding steps.
---

## Instructions

1. Ask for the employee's name and start date if not already provided.
2. Run the `scripts/check-provisioning.py` script to verify their IT accounts are active.
3. Walk through the steps in the `references/onboarding-checklist.md` reference.
4. Follow up on any incomplete items.
```

Provider 初始化时传入脚本执行器 `SubprocessScriptRunner.RunAsync`，然后把 Provider 挂到 Agent 上：

```csharp
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using OpenAI.Responses;

string endpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")!;
string deploymentName = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT_NAME") ?? "gpt-4o-mini";

var skillsProvider = new AgentSkillsProvider(
    Path.Combine(AppContext.BaseDirectory, "skills"),
    SubprocessScriptRunner.RunAsync);

AIAgent agent = new AzureOpenAIClient(new Uri(endpoint), new DefaultAzureCredential())
    .GetResponsesClient()
    .AsAIAgent(new ChatClientAgentOptions
    {
        Name = "HRAgent",
        ChatOptions = new() { Instructions = "You are a helpful HR self-service assistant." },
        AIContextProviders = [skillsProvider],
    },
    model: deploymentName);

AgentResponse response = await agent.RunAsync("I just started here. What are the onboarding steps I need to follow?");
Console.WriteLine(response.Text);
```

Agent 会自动发现 `onboarding-guide` 这个 Skill，当请求匹配时加载它，并在需要的时候调用 Python 脚本检查账号状态。

`SubprocessScriptRunner` 只是负责调用脚本，不做沙箱处理。生产环境里需要自行添加资源限制、输入验证和审计日志。

---

## 第二步：类继承式 Skill，来自 NuGet 包

HR 系统团队发布了 `Contoso.Skills.HrEnrollment`，内部实现继承了 `AgentClassSkill<T>`，用 `[AgentSkillResource]` 和 `[AgentSkillScript]` 属性标注资源和脚本，框架通过反射自动发现：

```csharp
// 包内的实现
using System.ComponentModel;
using System.Text.Json;
using Microsoft.Agents.AI;

public sealed class BenefitsEnrollmentSkill : AgentClassSkill<BenefitsEnrollmentSkill>
{
    public override AgentSkillFrontmatter Frontmatter { get; } = new(
        "benefits-enrollment",
        "Enroll an employee in health, dental, or vision plans. Use when asked about benefits sign-up, plan options, or coverage changes.");

    protected override string Instructions => """
        Use this skill when an employee asks about enrolling in or changing their benefits.
        1. Read the available-plans resource to review current offerings and pricing.
        2. Confirm the plan the employee wants to enroll in.
        3. Use the enroll script to complete the enrollment.
        """;

    [AgentSkillResource("available-plans")]
    [Description("Health, dental, and vision plan options with monthly pricing.")]
    public string AvailablePlans => """
        ## Available Plans (2026)
        - Health: Basic HMO ($0/month), Premium PPO ($45/month)
        - Dental: Standard ($12/month), Enhanced ($25/month)
        - Vision: Basic ($8/month)
        """;

    [AgentSkillScript("enroll")]
    [Description("Enrolls an employee in the specified benefit plan. Returns a JSON confirmation.")]
    private static string Enroll(string employeeId, string planCode)
    {
        bool success = HrClient.EnrollInPlan(employeeId, planCode);
        return JsonSerializer.Serialize(new { success, employeeId, planCode });
    }
}
```

`[AgentSkillResource]` 可以标注属性，也可以标注方法。方法形式适合需要在读取时动态计算内容，或者需要通过 `IServiceProvider` 注入服务的场景。`[AgentSkillScript]` 只能标注方法，同样支持 `IServiceProvider` 参数获取注入的服务。

将这个 Skill 和已有的文件式 Skill 合并，改用 `AgentSkillsProviderBuilder`：

```csharp
// dotnet add package Contoso.Skills.HrEnrollment
var skillsProvider = new AgentSkillsProviderBuilder()
    .UseFileSkill(Path.Combine(AppContext.BaseDirectory, "skills"))  // 文件式：入职引导
    .UseSkill(new BenefitsEnrollmentSkill())                         // 类继承式：来自 NuGet 的福利登记
    .UseFileScriptRunner(SubprocessScriptRunner.RunAsync)            // 文件脚本的执行器
    .Build();
```

不需要额外路由逻辑。两个 Skill 都会被广播到 Agent 的系统提示中，Agent 根据员工的问题自行决定加载哪个。

---

## 第三步：内联式 Skill，快速桥接

"请假余额"技能还在开发中，不想等。用 `AgentInlineSkill` 直接在应用代码里定义一个临时实现：

```csharp
using System.Text.Json;
using Microsoft.Agents.AI;

var timeOffSkill = new AgentInlineSkill(
    name: "time-off-balance",
    description: "Calculate an employee's remaining vacation and sick days. Use when asked about available time off or leave balances.",
    instructions: """
        Use this skill when an employee asks how many vacation or sick days they have left.
        1. Ask for the employee ID if not already provided.
        2. Use the calculate-balance script to get the remaining balance.
        3. Present the result clearly, showing both used and remaining days.
        """)
    .AddScript("calculate-balance", (string employeeId, string leaveType) =>
    {
        // 临时实现，NuGet 包发布后替换
        int totalDays = HrDatabase.GetAnnualAllowance(employeeId, leaveType);
        int daysUsed = HrDatabase.GetDaysUsed(employeeId, leaveType);
        int remaining = totalDays - daysUsed;
        return JsonSerializer.Serialize(new { employeeId, leaveType, totalDays, daysUsed, remaining });
    });
```

把它加入 Provider：

```csharp
var skillsProvider = new AgentSkillsProviderBuilder()
    .UseFileSkill(Path.Combine(AppContext.BaseDirectory, "skills"))  // 文件式：入职引导
    .UseSkill(new BenefitsEnrollmentSkill())                         // 类继承式：福利登记
    .UseSkill(timeOffSkill)                                          // 内联式：临时桥接
    .UseFileScriptRunner(SubprocessScriptRunner.RunAsync)
    .Build();
```

等正式包发布，把 `timeOffSkill` 从 Builder 里删掉，换成类继承式版本，其他地方不用动。

`AgentInlineSkill` 也支持动态资源。通过 `.AddResource()` 传入工厂委托，每次 Agent 读取资源时都会调用，可以从数据库或配置系统实时取值：

```csharp
var hrPoliciesSkill = new AgentInlineSkill(
    name: "hr-policies",
    description: "Current HR policies on leave, remote work, and conduct.",
    instructions: "Read the policies resource and answer the employee's question.")
    .AddResource("policies", () =>
    {
        // 每次都取最新版本
        return PolicyRepository.GetActivePolicies();
    });
```

内联 Skill 不仅适合临时桥接，也适合这些场景：需要在运行时从数据中生成 Skill（比如按业务单元或地区批量构建），或者需要捕获调用现场的状态而不想依赖 DI 容器时。这些情况下，内联方式是更自然的选择，而不是类继承方式的妥协。

---

## 第四步：脚本执行前要求人工审批

`check-provisioning.py` 查询生产基础设施，`enroll` 脚本写入 HR 系统，这些都有实际副作用。生产环境里加上 `UseScriptApproval(true)`：

```csharp
var skillsProvider = new AgentSkillsProviderBuilder()
    .UseFileSkill(Path.Combine(AppContext.BaseDirectory, "skills"))
    .UseSkill(new BenefitsEnrollmentSkill())
    .UseSkill(timeOffSkill)
    .UseFileScriptRunner(SubprocessScriptRunner.RunAsync)
    .UseScriptApproval(true)  // 开启审批
    .Build();
```

开启后，Agent 需要执行脚本时会暂停，返回一个审批请求，等应用层收到决策后再继续。审批通过则执行并继续回答，拒绝则告知 Agent 操作未被授权。详细的审批处理模式可以参考 [Tool approval 文档](https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval?pivots=programming-language-csharp)。

---

## 还能做什么

**按名称过滤共享目录中的 Skill**，避免全部加载：

```csharp
var approvedSkills = new HashSet<string> { "onboarding-guide", "benefits-enrollment" };

var skillsProvider = new AgentSkillsProviderBuilder()
    .UseFileSkill(Path.Combine(AppContext.BaseDirectory, "all-skills"))
    .UseFilter(skill => approvedSkills.Contains(skill.Frontmatter.Name))
    .Build();
```

如果组织维护了一个共享 Skill 库，每个 Agent 只取自己需要的子集，用这个就够了。

---

## 适用边界

这套模型最适合这几类情况：

- 多团队分别维护各自的 Skill，通过 NuGet 独立发布，消费方自由组合
- Agent 功能需要持续迭代，每次只增加一个技能，不打乱已有结构
- 某些脚本有真实副作用，需要在生产部署中加入人工审批环节

如果项目只有一两个简单 Skill 且不需要频繁变更，`AgentSkillsProvider` 单独用文件目录方式已经够用，不必引入 Builder 的额外复杂度。

## 参考

- [Agency Skills documentation on Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/agents/skills)
- [.NET samples on GitHub](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/AgentSkills)
- [原文：Agent Skills in .NET: Three Ways to Author, One Provider to Run Them](https://devblogs.microsoft.com/agent-framework/agent-skills-in-net-three-ways-to-author-one-provider-to-run-them)
