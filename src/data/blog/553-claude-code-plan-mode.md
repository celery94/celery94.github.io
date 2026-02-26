---
pubDatetime: 2026-02-26
title: "Claude Code 的 Plan Mode: 用 AI 写代码前先想清楚"
description: "介绍 Claude Code 的 Plan Mode，通过真实的 ASP.NET Core 案例演示如何在 AI 编程中实践 '先规划后编码' 的工作流，包括 4 阶段流程、计划编辑技巧和日常使用建议。"
tags: ["Claude Code", "AI", "Developer Productivity"]
slug: "claude-code-plan-mode"
source: "https://codewithmukesh.com/blog/plan-mode-claude-code/"
---

我让 Claude 给一个现有的 ASP.NET Core API 添加软删除功能，没有任何规划，也没加任何约束，就一句话："给所有实体加上软删除"。15 分钟后，结果一团糟：Claude 修改了 14 个文件，加了一个全局查询过滤器导致 3 个已有接口崩掉，还把 `DbContext` 改得和我的迁移历史冲突，甚至给不需要软删除的表也加了 `DeletedAt` 字段。

接下来我花了 30 分钟手动撤销所有改动，一个文件一个文件地改回去。

解决办法不是写更好的提示词，是在编码之前先做规划。这是和 AI 编码助手协作时最被低估的习惯。

## 为什么规划是最被低估的 AI 编程习惯

以下是 AI 编程新手常见的模式：

1. 输入一个模糊的提示，比如"给我的 API 加上认证"
2. AI 立刻开始写代码，速度快、很自信，但会犯隐蔽的错误
3. 修正了一个问题，AI 又引入了另一个问题
4. 反复修正三次后，上下文已经被各种失败方案污染了
5. 最终放弃，从头开始，浪费了 30 多分钟

AI 编码助手太急于执行了。它们被训练成尽可能有帮助，所以一收到方向就开始写代码。没有约束的情况下，它们会对你的架构、模式、偏好做出假设，这些假设像滚雪球一样叠加，最终导致一连串错误决策。

经过几个月的追踪，规律很明确：跳过规划环节时，大约 40% 的概率需要从头重做。不仅浪费时间，还浪费 Token、动力和耐心。

规划会翻转这个局面。你不再让 AI 朝着某个随机方向冲刺，而是强制它：

- 先阅读你的代码库
- 提出澄清性问题
- 提出实现方案
- 等你批准后再动任何文件

这个方法适用于任何 AI 编码工具，但 Claude Code 通过专门的 Plan Mode 让它变得更加实用，强制在执行之前进行只读分析。

> 我遵循的规则：如果能用一句话描述出确切的 diff，就跳过规划。如果不能，就先规划。这条规则比任何提示词工程技巧都节省时间。

## 什么是 Plan Mode

Plan Mode 是 Claude Code 中的一种只读运行模式。在这个模式下，Claude 可以分析你的整个代码库、提出澄清性问题、生成详细的实现计划，但不能修改文件、运行命令或执行任何代码。它把思考和行动分离了。

在 Plan Mode 中，Claude 可以使用以下只读工具：

| 工具            | 功能                     |
| --------------- | ------------------------ |
| Read            | 查看文件内容             |
| Glob            | 按模式搜索文件           |
| Grep            | 用正则搜索文件内容       |
| LS              | 列出目录内容             |
| WebSearch       | 搜索网络文档             |
| WebFetch        | 获取并分析网页           |
| Task            | 创建研究子代理           |
| AskUserQuestion | 向你提出多选题来澄清需求 |

它不能做的事：写文件、编辑文件、运行 shell 命令、执行测试或对项目做任何改动。Claude 被强制思考，不能行动。

这一点很重要，因为 Claude Code 的 Explore Subagent（一个 Haiku 驱动的专用子代理）会在 Plan Mode 期间自动启动，高效搜索你的代码库，同时节省上下文 Token。你可以获得深入的研究结果，而不会耗尽主要的上下文窗口。

Plan Mode 与 Normal Mode、Auto-Accept Mode 的对比：

| 模式             | 行为                                    | 适用场景                                     |
| ---------------- | --------------------------------------- | -------------------------------------------- |
| Normal Mode      | Claude 在每次文件编辑和命令前都请求许可 | 默认模式。需要审查每一步的小型定向改动       |
| Auto-Accept Mode | Claude 无需许可直接执行                 | 规划后的受信操作。批量执行已批准的计划       |
| Plan Mode        | 只读。Claude 只能分析和规划             | 复杂任务、不熟悉的代码、多文件改动、架构决策 |

Claude Code 创建者 Boris Cherny 自己使用的工作流是：在 Plan Mode 中开始，反复迭代直到计划正确，然后切换到 Auto-Accept 让 Claude 执行。他的大多数会话都从 Plan Mode 开始。

## 如何进入 Plan Mode

有多种方式可以激活 Plan Mode：

**键盘快捷键 Shift+Tab**

按 `Shift + Tab` 两次，在三种模式间循环切换。第一次按切换到 Auto-Accept Mode（底部显示 `⏵⏵ accept edits on`），第二次按激活 Plan Mode（底部显示 `⏸ plan mode on`）。

再按 `Shift + Tab` 切回 Normal Mode。

> Windows 用户注意：如果 `Shift + Tab` 只在 Normal 和 Auto-Accept 之间切换而跳过了 Plan Mode，改用 `Alt + M`。这是某些 Windows 终端配置的已知问题。

**/plan 命令**

从 Claude Code v2.1.0 开始，可以直接在提示中输入 `/plan` 进入 Plan Mode，不需要键盘快捷键，特别适合对话进行到一半时切换。

**CLI 参数：以 Plan Mode 启动**

启动一个直接进入 Plan Mode 的新会话：

```bash
claude --permission-mode plan
```

这是处理复杂任务时推荐的方式，一开始就进入正确的模式。

**无头 Plan Mode**

用于脚本或 CI 工作流，将 Plan Mode 与无头模式结合：

```bash
claude --permission-mode plan -p "Analyze the authentication system and suggest improvements"
```

**设为默认模式**

如果发现自己总是先进入 Plan Mode，可以把它设为默认：

```json
// .claude/settings.json
{
  "permissions": {
    "defaultMode": "plan"
  }
}
```

## 4 阶段工作流：探索、规划、实现、提交

Anthropic 的官方最佳实践推荐了一个结构化的 4 阶段工作流。

**阶段 1：探索（Plan Mode）**

阅读相关代码，在提出改动方案之前理解当前状态。

```
Read the /src/Features/Products directory and understand how
the existing product endpoints are structured. Also look at
how pagination is handled in any existing endpoint.
```

Claude 读取文件、搜索模式、建立理解，全程不修改任何内容。这个阶段很关键，因为它防止 Claude 对你的架构做出假设。

**阶段 2：规划（Plan Mode）**

让 Claude 根据它了解到的情况创建详细的实现计划。

```
I want to add advanced filtering and sorting to the Products
endpoint. Create a detailed plan. What files need to change?
What's the implementation order? What are the edge cases?
```

Claude 生成一个包含文件改动、实现顺序和注意事项的结构化计划。

**阶段 3：实现（Normal 或 Auto-Accept Mode）**

切出 Plan Mode（`Shift + Tab`），让 Claude 执行计划。

```
Implement the plan. Start with the query parameter models,
then the filter extensions, then update the endpoint.
Run the build after each step.
```

因为 Claude 在规划阶段已经有了上下文，执行更快也更准确。它知道要改哪些文件、按什么顺序、要遵守什么约束。

**阶段 4：提交（Normal Mode）**

让 Claude 创建描述性的 commit 并可选地创建 pull request。

```
Commit with a descriptive message and open a PR
```

关键洞察：阶段 1 和 2（探索 + 规划）在 Token 成本上最低，在结果价值上最高。

## 实战演示：规划一个 ASP.NET Core 功能

下面是一个真实的 Plan Mode 会话过程，目标是给现有的 Products 端点添加高级过滤、排序和基于游标的分页功能。

**第 1 步：进入 Plan Mode 并探索**

用 Plan Mode 启动 Claude Code：

```bash
claude --permission-mode plan
```

第一个提示让 Claude 理解现有代码：

```
Read the Products feature directory and understand:
1. How the current GetProducts endpoint works
2. What the Product entity looks like
3. How the DbContext is configured
4. Whether any other endpoint already implements pagination

Also check my CLAUDE.md for project conventions.
```

Claude 阅读相关文件后，发现了现有端点结构，识别出项目使用了 Minimal APIs 配合 Carter 库模式，确定了 EF Core 10 的 `DbContext`，以及目前没有端点实现分页。它还读取了 CLAUDE.md，了解到项目使用 `.slnx` 格式、用 Scalar 代替 Swagger，以及特定的项目结构。

**第 2 步：让 Claude 制定计划**

```
Plan the implementation for adding advanced filtering, sorting,
and cursor-based pagination to the GetProducts endpoint.

Requirements:
- Filter by: name (contains), category (exact), price range (min/max), isActive
- Sort by: name, price, createdDate (ascending/descending)
- Cursor-based pagination with configurable page size
- Return pagination metadata in response headers

Use the patterns from my existing codebase. Don't introduce
new libraries, use what's already in the project.
```

Claude 通过 AskUserQuestion 工具提出澄清问题，比如：

> "对于基于游标的分页，你偏好哪种方式？"
> A) 使用主键的 Keyset 分页（性能最好）
> B) 带游标编码的 Offset 分页（更灵活）
> C) 让我说明我偏好的方式

选择 A 后，Claude 又询问了过滤组合逻辑（AND 还是 OR）、默认排序顺序和最大页大小。根据回答，生成了一份计划。

**第 3 步：审查并编辑计划**

Claude 输出了一份结构化计划（简略版）：

```
## Implementation Plan: Advanced Filtering for Products

### Files to Create
1. Features/Products/Models/ProductFilter.cs：查询参数模型
2. Features/Products/Extensions/ProductQueryExtensions.cs：IQueryable 扩展方法

### Files to Modify
1. Features/Products/GetProducts.cs：更新端点以接受过滤参数
2. Features/Products/Models/ProductResponse.cs：添加分页元数据

### Implementation Order
1. 创建带验证的过滤模型
2. 创建用于过滤/排序的 IQueryable 扩展方法
3. 实现基于游标的分页逻辑
4. 更新端点把所有部分串联起来
5. 用 Scalar API 浏览器测试

### Edge Cases
- 空的过滤参数应返回未过滤的结果
- 无效的排序列应回退到默认值（CreatedDate desc）
- 已删除记录的游标应跳到下一个有效记录
```

这时候按 `Ctrl+G` 可以在默认编辑器中打开计划，直接编辑：删除不需要的步骤、添加 Claude 遗漏的约束、重新排列优先级。修改会自动同步回 Claude 的上下文。

> 提示：不要试图通过对话来描述计划的修改。按 `Ctrl+G`，直接编辑计划文件并保存，更快也更精确。

**第 4 步：切换到执行**

计划审查和编辑完成后，按 `Shift + Tab` 切到 Auto-Accept Mode，让 Claude 实现：

```
Implement the plan. After each file, run dotnet build to verify
there are no compilation errors.
```

因为 Claude 已经探索了代码库，而且方案已经获批，所以执行过程没有意外。没有不该有的全局查询过滤器，没有不必要的抽象，也没有动不该动的文件。

整个实现花了大约 12 分钟。不做规划的话，同样的任务之前要花 35 分钟以上，还要重做两次。

## 像专家一样编辑计划

**Ctrl+G：在编辑器中打开**

当 Claude 在 Plan Mode 中生成计划时，按 `Ctrl+G` 在默认编辑器中打开它。编辑、保存、关闭，Claude 会自动接收你的改动。

常见的编辑操作包括：

- 移除添加不必要抽象的步骤
- 添加约束，如"不要修改现有的迁移文件"
- 重新排列优先级，先实现最关键的部分
- 添加测试要求，如"在实现之前先为游标边界情况写测试"

**/plan open：文件系统访问**

Claude 把计划文件写到文件系统中。默认位置在 `~/.claude/plans/`，文件名是随机生成的，比如 `jaunty-petting-nebula.md`。运行 `/plan open` 可以直接在编辑器中打开当前计划文件。

**计划存放位置的配置**

默认的 `~/.claude/plans/` 位置有两个问题：随机文件名让你很难事后找到特定计划，全局目录意味着所有项目的计划混在一起。

建议：将计划存储在项目目录中，并提交到版本控制。计划是决策记录，它们记录了你为什么这样构建，这些上下文在代码审查、新人上手和半年后回头看代码时非常有价值。

在 `.claude/settings.json` 中配置项目本地的计划存储：

```json
{
  "plansDirectory": "./docs/plans"
}
```

相对路径从工作区根目录解析。实践中可以这样做：

- 将计划存储在 `docs/plans/` 并提交到 git
- Claude 生成计划后，把随机文件名重命名为描述性名称，比如 `2026-02-25-add-product-filtering.md`
- 对于重要功能，计划可以直接作为 PR 描述
- 快速任务的计划不用保存，它在会话中已经发挥了作用

> 提示：把 `plansDirectory` 添加到项目级的 `.claude/settings.json`（不是用户级的），这样团队成员克隆仓库后，计划会保存到同一个位置。

**什么时候编辑，什么时候重新提问**

| 情况                           | 建议                                        |
| ------------------------------ | ------------------------------------------- |
| 计划结构对但细节有误           | 编辑：`Ctrl+G`，修改细节                    |
| Claude 完全误解了需求          | 重新提问："这不是我的意思，让我澄清一下..." |
| 想添加 Claude 没考虑到的约束   | 编辑：直接添加到计划文件                    |
| 计划太复杂，想简化             | 编辑：删除不需要的部分                      |
| 想让 Claude 探索完全不同的方案 | 重新提问："不用 X，我们考虑 Y 方案"         |

## 什么时候需要规划，什么时候跳过

不是每个任务都需要计划。过度规划简单任务和对复杂任务规划不足一样浪费时间。

**一句话规则**

如果你能用一句话描述出确切的 diff，就跳过规划。这直接来自 Anthropic 的官方最佳实践：

> "当你对方案不确定、改动涉及多个文件、或者你不熟悉要修改的代码时，规划最有用。如果你能用一句话描述 diff，就跳过规划。"

**决策矩阵：.NET 场景**

| 任务                          | 推荐模式    | 原因                                                 |
| ----------------------------- | ----------- | ---------------------------------------------------- |
| 修复响应消息中的拼写错误      | Normal      | 一个文件一行代码，不需要规划                         |
| 给现有 DTO 添加新属性         | Normal      | 改动明确，单个文件                                   |
| 添加 EF Core 迁移             | Normal      | 直接运行 dotnet ef migrations add                    |
| 添加新的 CRUD 端点            | Plan Mode   | 多个文件（模型、端点、验证、DB 配置）                |
| 从 Repository 模式重构到 CQRS | Plan Mode   | 影响 10+ 文件的架构变更                              |
| 添加全局异常处理              | Plan Mode   | 涉及中间件、错误模型和每个端点的错误契约             |
| 更新 NuGet 包到最新版本       | Auto-Accept | 机械性任务，让 Claude 直接做                         |
| 给 API 添加认证               | Plan Mode   | 架构决策（JWT 还是 Cookie、中间件放置、Claims 结构） |
| 跨实体实现软删除              | Plan Mode   | 跨切面关注点，影响多个实体、过滤器和查询             |
| 全代码库重命名变量            | Auto-Accept | 机械性的查找替换，不需要判断                         |
| 给项目添加 Docker 支持        | Plan Mode   | 配置决策（多阶段构建、端口、卷、compose 设置）       |
| 修复一个失败的单元测试        | Normal      | 排查并修复，通常在一个文件内                         |

**经验法则**

- 1~2 个文件，改动明确 → Normal Mode 或 Auto-Accept
- 3+ 个文件，有任何不确定性 → Plan Mode
- 涉及架构决策 → 始终用 Plan Mode
- 不熟悉的代码库 → 始终用 Plan Mode

## Plan Mode + CLAUDE.md：强强联合

其他指南没有提到的一点：Plan Mode 的输出质量与你的 CLAUDE.md 质量直接相关。

当 Claude 进入 Plan Mode 并阅读你的代码库时，它也会读取你的 CLAUDE.md。如果那个文件包含了你的架构、编码标准、偏好模式和测试方案，生成的计划就会尊重所有这些约束。

没有 CLAUDE.md，Claude 可能会：

- 添加通用的 Repository 层（而你用的是 CQRS）
- 使用 Swagger（而你用的是 Scalar）
- 创建 `.sln` 文件（而你用的是 `.slnx`）
- 使用 `DateTime.Now`（而你的标准要求 `DateTimeOffset.UtcNow`）

有了好的 CLAUDE.md，Claude 的计划从一开始就遵循你的约定，不需要任何修正。

建议在项目上第一次使用 Plan Mode 之前就写好 CLAUDE.md。花 30 分钟写它，能省下几个小时的计划修正。

**CLAUDE.md 中应该写什么**

重点写 Claude 无法从代码中推断出的内容：

```markdown
# Architecture

- Minimal APIs with Carter library pattern (not controllers)
- Feature-folder structure: Features/[Feature]/[Endpoints, Models, Extensions]
- No generic repository pattern, query directly with DbContext

# Testing

- xUnit + FluentAssertions + NSubstitute
- Integration tests use WebApplicationFactory
- Run: dotnet test --no-build

# Conventions

- Scalar for API docs (not Swagger)
- .slnx solution format
- DateTimeOffset.UtcNow (never DateTime.Now)
- CancellationToken on every async method
```

这些约束对 Claude 来说是隐形的，如果不写进 CLAUDE.md 就会导致计划偏离。

## 日常使用建议

**保持规划范围小**

规划你接下来 30 分钟内要实现的内容。覆盖 20 个文件的大型计划会失去连贯性，因为 Claude 的上下文会被填满。按块规划：

- 第一个计划：数据模型和迁移
- 第二个计划：端点和验证
- 第三个计划：测试

**在规划时启用扩展思考**

按 `Alt + T`（Windows/Linux） 或 `Option + T`（macOS）在 Plan Mode 中启用扩展思考，让 Claude 有更多空间来推理架构决策、边界情况和权衡。配合 Opus 4.6 的自适应推理，模型会根据复杂度动态分配思考深度。

当你需要 Claude 评估多种方案时特别有用，比如"这个端点应该用 Keyset 分页还是 Offset 分页？"

**用子代理做深度调研**

当你需要 Claude 在规划期间研究代码库的大部分内容时，告诉它使用子代理：

```
Use subagents to investigate how our authentication middleware
works and what claims are currently available in the pipeline.
```

子代理在独立的上下文窗口中运行并返回摘要，主会话保持干净，不会在探索上消耗主要上下文。

**两次修正失败后，重新开始**

如果你修正了 Claude 的计划两次但仍然不对，上下文已经被失败方案搞乱了。不要继续，运行 `/clear` 然后写一个更好的初始提示，融入第一次尝试中学到的东西。一个精确提示的全新会话几乎总是优于一个充满累积修正的长会话。

**长会话中保留计划上下文**

如果会话变长了，担心上下文压缩丢失重要的规划信息，可以使用：

```
/compact Focus on the Products filtering plan and implementation decisions
```

这告诉 Claude 在压缩时优先保留什么，确保你的计划在上下文管理中存活下来。

**当 Plan Mode 不够用时：Agent Teams**

对于跨多个有界上下文或需要并行工作流的大型功能，单个 Plan Mode 会话不够用。这时候可以使用 Claude Code Agent Teams，多个 Claude 实例通过共享任务列表来协调工作。

## 常见问题排查

**Windows 上 Shift+Tab 无法切换到 Plan Mode**

这是某些 Windows 终端配置的已知问题。`Shift + Tab` 可能只在 Normal 和 Auto-Accept 之间切换，跳过 Plan Mode。解决：改用 `Alt + M`，或直接在提示中输入 `/plan`。

**上下文压缩后 Plan Mode 丢失**

在早期版本中，切换到 Plan Mode 后可能在 Claude Code 自动压缩对话时被静默丢失。解决：这在 v2.1.47 中已修复，使用 `npm update -g @anthropic-ai/claude-code` 更新到最新版本。如果已是最新版仍有问题，在压缩后重新用 `/plan` 进入 Plan Mode。

**Claude 在执行时忽略计划约束**

你批准了计划、切换到执行，但 Claude 偏离了计划，添加了计划中没有的文件或模式。这通常是因为计划太模糊或执行提示没有引用计划。解决：切出 Plan Mode 后，明确说"严格按照计划实现，不要添加计划之外的任何内容。"同时在切换模式前用 `Ctrl+G` 让计划约束更明确。

**计划文件名随机，难以找到**

默认情况下计划文件放在 `~/.claude/plans/`，名称是自动生成的，如 `jaunty-petting-nebula.md`。解决：在项目的 `.claude/settings.json` 中将 `plansDirectory` 设为项目本地路径如 `./docs/plans`，然后在 Claude 生成计划后重命名为有意义的名称。

**Claude 的计划太泛或没有遵循你的模式**

Claude 生成的计划看起来合理但与你的项目架构或约定不匹配。解决：这几乎总是因为你的 CLAUDE.md 缺失或不完整。Claude 无法尊重它不知道的约定。在下次 Plan Mode 会话前写好包含架构、测试和编码约定的 CLAUDE.md。

## 总结

核心原则很简单：在构建之前先思考。AI 编码助手很强大，但没有计划的话，这种能力会被浪费，甚至造成破坏。

Claude Code 的 Plan Mode 是目前使用过的最好的规划实现。4 阶段工作流（探索 → 规划 → 实现 → 提交），配合好的 CLAUDE.md 和用 `Ctrl+G` 编辑计划的能力，创造了一个比让 AI 直接开干更快、更可预测的开发流程。

下次开始新会话时试试 Plan Mode。强制 Claude 先思考。编辑计划。然后执行。你会发现构建过程流畅了很多。
