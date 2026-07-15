---
pubDatetime: 2026-07-15T13:43:36+08:00
title: "Agent Harness 能力扩展：Skills、Shell、CodeAct 和后台 Agent"
description: "Microsoft Agent Framework 的 Harness 提供了四种扩展 Agent 能力的方式：按需加载的 Skills、受限沙箱的 Shell 工具、让 Agent 自己写代码算结果的 CodeAct，以及并行委托子 Agent 的后台调度。这篇把每种能力的 .NET 和 Python 接入方式都走一遍。"
tags:
  ["Agent Framework", "Agent Harness", "Skills", "CodeAct", ".NET", "AI Agent"]
slug: "agent-harness-scaling-capabilities"
ogImage: "../../assets/942/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/agent-harness-scaling-the-claw-or-harness-capabilities"
---

这是"用 Microsoft Agent Framework 搭建你自己的 claw"系列的第三篇。上一篇让理财助手学会了安全读写你的数据——它会读取你的投资组合、交易前先跟你确认、记住你觉得重要的事。但它能做的工作还很有限：所有能力都塞在一个 prompt 里、一次只能做一件事、够不到文件访问工具之外来真正重组数据。

这一篇从四个方向把 claw 的能力放大：

1. **Skills**——把领域知识（估值、风险评分）打包成可发现的文件，Agent 按需加载，包括集中管理的 Foundry Skills
2. **Shell**——给 Agent 一个受限的 shell，用来整理和重组文件
3. **CodeAct**——让 Agent 自己写代码、跑代码，算出它查不到的答案
4. **后台 Agent**——把工作并发派给子 Agent，再汇总结果

## 按需教学：Skills

把所有指令塞进 system prompt 不具可扩展性——上下文膨胀，焦点稀释。**Skills** 的解决方式是用 `SKILL.md` 文件承载每个技能，Agent 只看到技能名称和一行描述，请求匹配时才逐步加载完整内容。

给 claw 配上两个文件型技能：`valuation`（估值）和 `risk-scoring`（风险评分）。

在 .NET 里，用 `AgentSkillsProviderBuilder` 构建自己的 provider：

```csharp
var skillsProvider = new AgentSkillsProviderBuilder()
    .UseFileSkills([skillsDir],
        scriptRunner: SubprocessScriptRunner.RunAsync)
    .Build();

AIAgent agent = chatClient.AsHarnessAgent(new HarnessAgentOptions
{
    DisableAgentSkillsProvider = true,
    AIContextProviders = [skillsProvider],
});
```

Python 里类似：

```python
from agent_framework import SkillsProvider

skills_provider = SkillsProvider.from_paths(
    skill_paths=[str(skills_dir)],
    script_runner=subprocess_script_runner,
)

agent = create_harness_agent(
    client=client,
    skills_provider=skills_provider,
)
```

现在说"帮我估算一下 MSFT 的估值"就会让 Agent 加载 `valuation` 技能、读取指南、跑脚本、给出公允价值估算。而系统 prompt 里一句关于估值和风险的内容都没写。

### 集中管理的 Foundry Skills

文件型技能随 Agent 一起部署，改了就得重新部署。**Foundry Skills** 反过来：在 Foundry 项目里发布和更新，Agent 运行时自动获取。

因为需要 Foundry endpoint，所以是选配。.NET 里通过 Foundry 的 MCP 端点实时发现：

```csharp
if (!string.IsNullOrWhiteSpace(toolboxUrl))
{
    var (mcpClient, _) = await FoundrySkills.ConnectAsync(
        toolboxUrl, credential);
    skillsBuilder.UseMcpSkills(mcpClient);
}
```

Python 里也是同样思路：连接到 Toolbox MCP endpoint，把 `MCPSkillsSource` 和本地的 `FileSkillsSource` 合并：

```python
sources = [FileSkillsSource(str(skills_dir),
    script_runner=subprocess_script_runner)]

if toolbox_url:
    session = await _connect_foundry_toolbox(stack, toolbox_url)
    sources.append(MCPSkillsSource(client=session))

source = sources[0] if len(sources) == 1 \
    else AggregatingSkillsSource(sources)
skills_provider = SkillsProvider(DeduplicatingSkillsSource(source))
```

无论哪种方式，Agent 看到的都是一个统一的技能集。

Skills 不只是领域操作指南——也可以承载 Agent 的行为规则。比如发一个 `financial-agent-rules` 技能到 Foundry 工具箱，里面写"拒绝回答与理财无关的问题"，由于它的描述声明了"用于所有请求"，Agent 每次都会加载它。发完之后问"法国的首都是什么"，claw 会有礼貌地拒绝并引导你回到理财话题上。

## 伸手碰文件系统：Shell

文件访问能让 Agent 读写单文件，但**重组**一个乱糟糟的文件夹——移动、改名、批量操作——正是 shell 的活。比如用户的交易确认文件堆成一团：

```text
working/confirmations/
  trade confirmation 1.txt
  conf_AAPL.txt
  copy of trade 3.txt
  SPY sell.txt
```

Harness 可以把 **shell** 作为审批门控的 `run_shell` 工具暴露给 Agent。当然很危险，所以有两层防护：**工作目录限制**（每条命令都锚定到确认文件库，跑不出去）和**拒绝列表**（预过滤明显破坏性的命令）。

.NET：

```csharp
await using var shell = new LocalShellExecutor(
    new LocalShellExecutorOptions
{
    WorkingDirectory = vaultDir,
    ConfineWorkingDirectory = true,
    Policy = new ShellPolicy(denyList:
    [
        @"\brm\s+-rf\b", @"\bsudo\b",
        @":\(\)\s*\{", @"\bmkfs\b", @">\s*/dev/sd",
    ]),
    Timeout = TimeSpan.FromSeconds(15),
});

AIAgent agent = chatClient.AsHarnessAgent(
    new HarnessAgentOptions { ShellExecutor = shell });
```

Python：

```python
from agent_framework_tools.shell import LocalShellTool, ShellPolicy

shell = LocalShellTool(
    workdir=str(vault_dir),
    confine_workdir=True,
    policy=ShellPolicy(denylist=[
        r"\brm\s+-rf\b", r"\bsudo\b",
        r":\(\)\s*\{", r"\bmkfs\b", r">\s*/dev/sd",
    ]),
    timeout=15,
)
```

拒绝列表是 UX 护栏，不是安全边界。真正的隔离靠的是工作目录限制和审批弹窗。对不信任的输入，可以用 `DockerShellExecutor` 跑在沙箱里。

现在说"整理一下我的交易确认文件"——Agent 会检查文件夹、提出方案，然后让你逐条审批后把文件按 `年/月` 目录重组织。

## 让 Agent 自己算：CodeAct

有些问题不是查出来的，是**算**出来的。"我的投资组合值多少钱？"这类问题，让模型在脑子里做算术不如让它跑一小段代码。**CodeAct** 给了 Agent 一个沙箱化的解释器，它可以写代码然后跑。

.NET 里 CodeAct 基于 **Hyperlight**（微虚拟机，需要硬件虚拟化）：

```csharp
using HyperlightSandbox.Guest.Python;
using Microsoft.Agents.AI.Hyperlight;

var codeAct = new HyperlightCodeActProvider(
    HyperlightCodeActProviderOptions.CreateForWasm(
        PythonGuestModule.GetModulePath()));

AIAgent agent = chatClient.AsHarnessAgent(
    new HarnessAgentOptions
    {
        AIContextProviders = [skillsProvider, codeAct],
    });
```

Python 里用 **Monty**，纯跨平台解释器，不需要虚拟化：

```python
from agent_framework_monty import MontyCodeActProvider

context_providers = [
    skills_provider,
    MontyCodeActProvider(approval_mode="never_require")
]

agent = create_harness_agent(
    client=client,
    context_providers=context_providers,
)
```

有了 CodeAct，说"算一下我投资组合的总价值"——Agent 会读持仓，写几行 Python 把股数乘以价格求和，跑代码，报告结果。整个计算过程有迹可循，不是猜的。

## 并行做事：后台 Agent

"研究一下 MSFT、NVDA 和 SPY"——一个一个查太慢，把所有网络搜索塞进主 Agent 又搞乱上下文。Harness 支持**后台 Agent**：交给 claw 一批子 Agent，让它把工作**委托**出去，并发执行，然后收结果。

先搭一个轻量的、只做网络搜索的研究 Agent：

```csharp
AIAgent research = chatClient.AsAIAgent(
    name: "TickerResearchAgent",
    description: "Search web for news about a stock ticker.",
    instructions: "Research one ticker, return 3-4 bullet points.",
    tools: [new HostedWebSearchTool()]);

AIAgent agent = chatClient.AsHarnessAgent(
    new HarnessAgentOptions
    {
        BackgroundAgents = [research],
    });
```

Python 也一样：

```python
research_agent = Agent(
    client,
    name="TickerResearchAgent",
    description="Search web for news about a stock ticker.",
    instructions="Research one ticker, return 3-4 bullet points.",
    tools=[client.get_web_search_tool()],
)

agent = create_harness_agent(
    client=client,
    background_agents=[research_agent],
)
```

这会给主 Agent 一套 `background_agents_*` 工具：它可以**启动**每个股票代码的研究任务，让它们并行跑，**检查**进度，再**收集**结果——汇总成一份报告。扇出扇入是 Agent 自己的决策，管线是 Harness 处理的。

## 可以跑起来试试

```bash
# .NET
cd dotnet
dotnet run --project samples/02-agents/Harness/BuildYourOwnClaw/Claw_Step03_ScalingCapabilities

# Python
uv run python/samples/02-agents/harness/build_your_own_claw/claw_step03_scaling_capabilities.py
```

然后按顺序试试：

1. `Value MSFT for me.`——加载 valuation 技能，跑脚本，给估值
2. `How risky is my portfolio?`——读 portfolio.csv，加载 risk-scoring 技能
3. `/mode plan`，然后 `Tidy up my trade confirmations.`——先进入计划模式检查文件夹并提案，审批后用 shell 执行
4. `Work out the total value of my portfolio.`——写 Python 算结果
5. `Research MSFT, NVDA and SPY.`——并发派给研究 Agent，汇总
6. `What's the capital of France?`——配置了 financial-agent-rules Foundry 技能后会礼貌拒绝

## 独立使用这些构建模块

每种能力都可以脱离 Harness 单独拿起来用：

| 能力       | .NET                                                           | Python                                                   |
| ---------- | -------------------------------------------------------------- | -------------------------------------------------------- |
| Skills     | `AgentSkillsProvider` — `Microsoft.Agents.AI`                  | `from agent_framework import SkillsProvider`             |
| Shell      | `LocalShellExecutor` — `Microsoft.Agents.AI.Tools.Shell`       | `from agent_framework_tools.shell import LocalShellTool` |
| CodeAct    | `HyperlightCodeActProvider` — `Microsoft.Agents.AI.Hyperlight` | `from agent_framework_monty import MontyCodeActProvider` |
| 后台 Agent | `BackgroundAgentsProvider` — `Microsoft.Agents.AI`             | `from agent_framework import BackgroundAgentsProvider`   |

## 参考

- [原文链接](https://devblogs.microsoft.com/agent-framework/agent-harness-scaling-the-claw-or-harness-capabilities)
- [Part 1 – Meet your agent harness and claw](https://devblogs.microsoft.com/agent-framework/meet-your-agent-harness-and-claw/)
- [Part 2 – Working with your data, safely](https://devblogs.microsoft.com/agent-framework/agent-harness-working-with-your-data-safely/)
