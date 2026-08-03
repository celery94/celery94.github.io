---
pubDatetime: 2026-08-03T10:28:00+08:00
title: "从生成代码到可信代码：微软开源单测 agent"
description: "微软开源 polyglot 单测生成 agent（code-testing-generator），四步工作流让测试可运行、可被发现、断言有效；152 任务基准完成率 92.1% 对 78.9%，附安装与试用方法。"
tags: ["AI Agents", "Unit Testing", ".NET", "GitHub Copilot"]
slug: "polyglot-unit-testing-agent"
ogImage: "../../assets/989/01-cover.jpg"
source: "https://devblogs.microsoft.com/dotnet/polyglot-unit-testing-agent"
---

对编码 agent 最常见的请求只有一行：**Generate unit tests.（生成单元测试）**。但这行请求留下了太多开放问题——哪些代码需要测试？项目用哪个测试框架？测试放在哪里？构建怎么发现它们？测试到底该检查什么？

微软 .NET 团队为此发布了开源的 polyglot 单测生成 agent：**code-testing-generator**，位于 [dotnet/skills](https://github.com/dotnet/skills) 仓库的 `dotnet-test` 插件中。它的做法是：先学习仓库，再写测试，然后证明这些测试确实有效。本文整理它的工作流设计、官方基准数据和安装试用方法，帮助判断它值不值得进入你的工具链。

先说清它的边界：这个 agent 只写**单元测试**，会隔离被测代码、mock 外部服务和外部依赖；集成测试、端到端测试、浏览器测试和性能测试都不在它当前范围内。而且它的目标不只是让测试通过——它还会检查断言质量、请求的场景是否全覆盖，以及仓库正常的测试命令能否发现新测试。

## Prompt 之后发生了什么

这个 agent 不会拿到请求就动手写测试。它的工作流分四步：学习仓库 → 确定工作量 → 计划并写测试 → 验证测试价值。

### 第一步：从仓库学习

agent 先在仓库里搜索需要测试的代码，检测语言和测试框架，并查看现有测试——新测试放在哪里、长什么样，都从已有惯例里学。它还会找出正确的构建和运行测试命令。

这一步专门防一个常见问题：新测试项目单独构建能通过，但因为没加进 solution 或仓库的测试命令，在 CI 里**永远不运行**。agent 会确认仓库如何发现测试，并验证新测试出现在其中。

### 第二步：选择合适的工作量

一个方法不需要大规划，整个 solution 才需要。agent 有三条路径：

- **Direct（直接）**：读相关代码、写测试、验证结果。
- **Single pass（单趟）**：研究和规划一次，然后一次实现完。
- **Iterative（迭代）**：重复循环，覆盖大请求或达到覆盖率目标。

### 第三步：计划并写测试

任务较大时，agent 会列出需要测试的代码清单，从简单代码开始，再处理依赖更多的代码，并把每个行为映射到对应的测试文件。计划严格跟随请求范围——只请求一个模块，就不会改动仓库里所有测试项目。

写作过程中它遵循本地约定并持续跑测试：生成的代码不编译就修复；断言错误就回读源码改正测试。两条硬约束值得注意：**测试生成期间不改动生产代码**；避免会调用外部 URL、打开端口或依赖精确计时的单元测试。

### 第四步：检查测试真的有用

一个测试可以通过但毫无价值——比如只检查结果不为 null，测错了方法，甚至方法永远返回默认值时它照样通过。提交前 agent 会做这些检查：

- 考虑小的代码改动应该让测试失败——一种轻量级变异测试。
- 查找薄弱或缺失的断言。
- 确认每个请求的场景都有对应测试。
- 构建整个 workspace 并运行完整测试套件。
- 确认仓库的测试命令能找到新测试。

## 官方基准：可靠性是最大增益

微软用内部单测基准（152 个来自真实仓库的任务，部分 prompt 详细、部分模糊）做了对比：同一模型下，装了插件的 agent 在 GitHub Copilot 里完成了 **140/152（92.1%）**，而没用插件的 stock Copilot 完成 **120/152（78.9%）**，失败减少 **63%**。

任务通过的硬标准是：仓库能构建；所有测试通过；至少新增一个测试；没有删除任何已有测试。

### 模糊提示才是分水岭

按提示类型拆分后结论非常清晰：

| Prompt 类型           | 专用 agent  | Stock Copilot |
| --------------------- | ----------- | ------------- |
| 模糊提示（89 个任务） | 79（88.8%） | 59（66.3%）   |
| 详细提示（63 个任务） | 61（96.8%） | 61（96.8%）   |

详细提示下两者打平，全部 20 个净增益都来自模糊提示——失败从 30 降到 10。这正是这个 agent 的设计目标：**替开发者做 prompt 里没写的调研**。基准里还有 15 个任务要求为特定 diff 写测试，agent 全部通过，stock Copilot 一个都没过。

### 不是多写测试，而是更可靠

配对对比 152 个任务：双方都通过 119 个；只有专用 agent 通过 21 个；只有 stock 通过 1 个；双方都失败 11 个。

| 指标             | 专用 agent       | Stock Copilot    |
| ---------------- | ---------------- | ---------------- |
| 完成任务         | 140/152（92.1%） | 120/152（78.9%） |
| 构建成功的方案   | 148              | 145              |
| 最终测试套件通过 | 149              | 147              |
| 生成的测试数     | 6,963            | 7,129            |
| 平均行覆盖率     | 72.4%            | 72.2%            |
| 平均分支覆盖率   | 49.8%            | 49.1%            |
| 平均任务耗时     | 359 秒           | 380 秒           |

专用 agent 生成的测试少了 2.3%，平均覆盖率几乎相同，但完成的任务更多、平均快约 5.5%。增益来自**可靠性**，而不是产出了更多测试。

### 跨模型、跨语言都有效

基准里 45 个 .NET 任务用三个模型各跑一遍：

| 模型             | 专用 agent     | Stock Copilot  | 失败减少 |
| ---------------- | -------------- | -------------- | -------- |
| Claude Opus 4.8  | 43/45（95.6%） | 35/45（77.8%） | 80%      |
| GPT-5.5          | 41/45（91.1%） | 36/45（80.0%） | 56%      |
| Claude Haiku 4.5 | 34/45（75.6%） | 25/45（55.6%） | 45%      |

工作流对每个模型都有帮助：Opus 上净增 8 胜 0 负；Haiku 多完成了 9 个 C# 任务。更有意思的发现是，**强工作流能把中档模型拉到接近顶级模型**——全 152 个任务里，专用 GPT-5.5 达到 90.1%，比专用 Opus 差不到 2 个点，比 stock Opus 高出 11 个点以上。

agent 内置 .NET、Python、TypeScript、JavaScript、Java、Go、Ruby、Rust、Swift、Kotlin、PowerShell、C++ 的语言指南，学习各仓库约定而不是到处套 C# 模式。同一轮 Opus 运行里：Go 15 个任务全部通过（stock 66.7%），Python 完成率从 40.0% 翻倍到 86.7%。当然不是每种语言都更好——PowerShell 上 stock 多过了 1 个任务；这些分组样本较小，官方把它定位为"有用信号"而非承诺。

### 更难的第二个基准：SWE Atlas

团队还跑了 SWE Atlas 的 44 个单测任务（该基准用代码变更验证测试能否抓住 bug）：专用 agent 完成 16/44（36.4%），stock 12/44（27.3%），且没有出现 stock-only 的胜利；生成的 550 个测试里有 360 个抓住了注入的 bug（stock 为 493 和 316）。完成率明显低于内部基准——SWE Atlas 很难，官方直言还有大量改进空间。

## 经验与下一步

官方总结中最清晰的结论：双方都能产出有效结果时，质量指标各有胜负——stock 在断言深度和覆盖率上略高，专用 agent 在测试卫生（结构干净、避免慢或脆弱模式）上略高。由于专用组包含了 stock 未完成的更难任务，这不能当作直接的质量排名，但为下一步改进指明了方向：**更深的断言和错误路径测试，同时保持测试卫生**。

效率方面，按完成任务口径，专用 agent 每条任务多用了约 3.2% 的 recorded tokens（含缓存输入，不直接代表成本）。目前这些结果只覆盖单元测试，官方在探索同一工作流用于其他测试类型的可能性，但没有已承诺的计划。

## 如何试用

插件完全开源，目前在 GitHub Copilot CLI 可用，Visual Studio Code 和 VS Code Insiders 通过插件支持（仍为预览），Visual Studio 支持在开发中。安装步骤：

```text
/plugin marketplace add dotnet/skills
/plugin install dotnet-test@dotnet-agent-skills
```

重启 CLI 后，从 agent 列表选择 `code-testing-generator`，然后就可以试试开头那句 prompt：

```text
Generate unit tests.
```

也可以指定范围：为一个函数、一个模块，或某个具体的覆盖率目标生成测试。建议认真审查它产出的计划、测试和最终检查报告——官方那句收尾说得很到位：**好测试不是"生成"出来的，而是被规划、构建、运行和检查出来的，这正是他们正在构建的信任闭环。**

## 参考

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践，欢迎关注并留言你想看的主题。

- [From generated code to trusted code with a unit-test agent（原文）](https://devblogs.microsoft.com/dotnet/polyglot-unit-testing-agent)
- [dotnet/skills 仓库](https://github.com/dotnet/skills)
- [dotnet-test 插件](https://github.com/dotnet/skills/tree/main/plugins/dotnet-test)
- [code-testing-generator agent 定义](https://github.com/dotnet/skills/blob/main/plugins/dotnet-test/agents/code-testing-generator.agent.md)
- [SWE Atlas 基准](https://github.com/scaleapi/SWE-Atlas)
