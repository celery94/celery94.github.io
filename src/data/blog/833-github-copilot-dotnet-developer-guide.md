---
pubDatetime: 2026-05-27T08:17:00+08:00
title: ".NET 开发者的 GitHub Copilot 实战手册：Chat、Agent 和 CLI 怎么选"
description: "GitHub Copilot 不只是代码补全。这篇来自微软 .NET 团队的指南把 Copilot 的使用面拆成 Chat（理解、规划）和 Agent（执行、验证）两类，给出 10 个真实 .NET 场景的 prompt 示例，帮你判断当前任务该用哪种模式。"
tags: ["DotNet", "GitHub Copilot", "AI", "开发工具"]
slug: "github-copilot-dotnet-developer-guide"
ogImage: "../../assets/833/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/doing-more-with-github-copilot"
---

![.NET 开发者的 GitHub Copilot 实战手册：Chat、Agent 和 CLI 怎么选](../../assets/833/01-cover.png)

大多数 .NET 开发者用 GitHub Copilot 的方式还停留在行内补全：Tab 一下，接受一段 LINQ、一个测试方法、一段 DTO 映射。补全确实好用，但更大的收益来自两个不同的方向——**Chat** 用来理解和规划，**Agent** 用来执行和交付。

微软 .NET 团队的 Wendy Breiding 写了一篇实战指南，核心观点很简单：别问"我该学 Copilot 的哪个功能"，问"手头这个任务，哪一部分可以委托出去"。然后根据任务性质，选对交互面——Visual Studio、VS Code、Copilot CLI 或云端 Agent。

## Chat 和 Agent 的分界线

实用判断规则：

- **用 Chat**：当你需要**理解、比较、规划、解释或起草**。
- **用 Agent**：当你需要**修改、验证、更新、重跑测试并交付一个可 review 的结果**。

具体来说：

| 任务描述                                   | 模式  |
| ------------------------------------------ | ----- |
| "解释这个 service，建议一个重构方案"       | Chat  |
| "实现这个重构，更新测试，保持公开契约不变" | Agent |
| "总结这个失败的构建，告诉我该检查什么"     | Chat  |
| "修复根因，重跑测试，总结 diff"            | Agent |

判断标准：如果你能用一句话描述 done 的定义，而且你愿意像 review 同事 PR 一样去 review 结果，它就适合交给 Agent。

## Chat 的五个真实场景

Chat 在你需要解释、比较、规划或基于实际项目上下文做定向代码生成时最有用。

### 场景一：在改代码之前先理解一个服务

你打开一个遗留的 ASP.NET Core 服务，发现一个类有五个依赖、几个 feature flag、业务逻辑埋在一个长方法里。别急着改，先用 Chat 搞清楚：

```
Explain what this service is responsible for, identify the key
dependencies, and point out which parts are business logic versus
infrastructure concerns. Then suggest a safe first refactor that
does not change behavior.
```

这比直接要求重写好得多。真正的瓶颈往往不是写代码，而是理解已有代码。

### 场景二：给业务逻辑生成测试

假设你有一个定价方法，涉及折扣、上限和地区税规则。你先手写第一个 happy-path 测试，然后用 Chat 补边界用例：

```
Create unit tests for this method using the same test style as this
project. Cover discount boundaries, null input handling, and the
case where the total is capped. Explain any edge cases you think
are easy to miss.
```

在 Visual Studio 里可以用 Test Agent；在 VS Code 或 CLI 里，用 [dotnet-test skill](https://github.com/dotnet/skills/tree/main/plugins/dotnet-test) 效果最好。这个场景强在你既要代码输出，又要推理——你想确认对的 case 被考虑到了。

### 场景三：改代码之前先做方案

一个 Controller 逻辑太重，你想把验证和编排搬到 Service 里。在动手之前先让 Chat 出方案：

```
Review this controller action and propose a refactor that moves
orchestration into a service without changing the HTTP contract.
Show the target shape of the controller, service interface, and
unit tests I should expect to update.
```

进入 Plan Mode，Copilot 会生成详细方案，等你确认后再由你或 Copilot 实施。

### 场景四：跨代码和配置的修改

典型的 .NET 场景不只改 C#，而是同时改 API、OpenAPI 描述、部署文件和文档。这时 VS Code 往往更合适：

```
I am adding a new optional region filter to this endpoint. Update
the ASP.NET Core handler, adjust the OpenAPI description, and
point out any config, docs, or client code that may also need
to change.
```

Chat 在这类场景里不像补全，更像一个工作伙伴——帮你跨整个 repo 思考，而不只盯着当前文件。

### 场景五：用 CLI 分析构建失败

`dotnet test` 或 `dotnet build` 失败时，CLI 是最自然的交互面，因为错误就在你的终端里：

```
Explain this build failure in plain English, tell me which project
likely introduced it, and suggest the next two commands I should
run to narrow it down.
```

或者：

```
This xUnit test is failing intermittently. Based on the output and
the file paths involved, what are the likely causes, and what
should I inspect first?
```

比把错误粘到搜索引擎里强，因为 CLI 能贴近你的实际 repo 和命令上下文。

## Agent 的五个真实场景

Agent 模式在任务是多步骤、有边界、结果可 review 时最有用。你不再只是要一个答案，你是在让 Copilot 执行一段工作。

### 场景一：补齐一个功能切片的测试缺口

一个新功能加到了 ASP.NET Core API 里，但只测了 happy path。这是 Agent 的强项：

```
Add missing unit tests for the CreateOrder flow. Cover validation
failures, duplicate order detection, and the downstream payment
timeout path. Keep the existing test style, do not rename public
APIs, and stop once the new tests pass.
```

为什么好用：范围清楚、影响面有界、有明确的完成定义、结果容易在 diff 里 review。

### 场景二：清理重复的重构

很多 .NET 仓库里积累了同一类问题：不一致的日志、nullable 警告、重复的 guard clause、旧的 result-handling 代码。这种活对人来说很烦，对 Agent 来说正合适：

```
Update the notification handlers in this project to use the shared
Result<T> pattern instead of throwing validation exceptions.
Preserve current behavior, update the affected unit tests, and
summarize which handlers changed.
```

不光鲜，但正是省时间的地方。

### 场景三：CLI 里的修复-验证循环

Agent 不只在云端工作。CLI 本身就适合"检查、运行、修复、重跑"的循环：

```
Investigate why dotnet test is failing in the Notifications.Tests
project, make the smallest fix that addresses the root cause,
rerun the relevant tests, and summarize the change.
```

整个工作流都在终端里完成。

### 场景四：云端 Agent 做有边界的多文件修改

云端 Agent 适合能在后台运行、完成后以草稿变更提交 review 的任务：

```
Add correlation ID propagation to the API and background worker
pipeline. Update middleware, logging enrichment, and the integration
tests that assert the header flows through. Do not change unrelated
logging format, and note any follow-up work if you find gaps
outside this slice.
```

够广，值得委托；够具体，能认真 review。

### 场景五：VS Code 做跨栈工作

有些 Agent 任务不纯是 C#，而是同时涉及 API、部署配置和文档：

```
Add support for a new beta environment flag. Update the .NET
configuration binding, the Bicep template, the GitHub Actions
workflow, and the deployment documentation. Keep naming consistent
with the existing environment settings.
```

工作分散在代码和周边资源之间，VS Code 往往是更舒服的交互面。

## 写好 prompt 的四个要素

对 .NET 场景来说，好的 prompt 通常包含四样东西：

1. **目标** — 你想做什么
2. **代码或命令输出** — 上下文
3. **约束** — 什么不能改
4. **期望的回答形状** — 你想要代码、方案还是解释

比如：

```
Refactor this background worker to make the retry policy easier
to test. Keep the public behavior the same, preserve structured
logging, and show me the test cases I should add.
```

比 `Improve this code.` 强得多。prompt 越像一条真实的 code review comment 或工程任务，回答越有用。

### .NET 专属的约束示例

这些约束写进 prompt 之后会明显提升结果质量：

- keep the public API unchanged
- follow the existing xUnit pattern
- preserve DI registration style
- update nullable annotations only in this project
- rerun the relevant tests, not the whole universe

细节决定了这是一次泛泛的 AI 对话，还是一段真正有用的工程工作流。

## 四个交互面怎么选

| 场景                                      | 推荐          |
| ----------------------------------------- | ------------- |
| 深入解决方案内部的 C# 工作                | Visual Studio |
| 跨代码、配置、文档的修改                  | VS Code       |
| 工作在终端里（构建失败、测试调试）        | Copilot CLI   |
| 有边界的任务，能后台跑、提交 draft review | 云端 Agent    |

原文作者的最后一句话：Copilot 对 .NET 开发者的真正价值不是能补几行 C#，而是它能帮你推理真实的工作，在任务足够明确时，替你执行一部分。

从你自己 backlog 里拿一个真实任务开始——理解一个服务、给关键逻辑加测试、修一个失败的构建、交出一个重复的重构。这才是 Copilot 从理论变成实用的起点。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Doing More with GitHub Copilot as a .NET Developer (Microsoft .NET Blog)](https://devblogs.microsoft.com/dotnet/doing-more-with-github-copilot)
- [dotnet-test skill (GitHub)](https://github.com/dotnet/skills/tree/main/plugins/dotnet-test)
