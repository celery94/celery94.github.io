---
pubDatetime: 2026-06-10T08:30:00+08:00
title: "Claude Code 进阶用法：.NET 项目里最值得落地的 20 个习惯"
description: "Mukesh Murugan 总结了 20 条面向 .NET 开发者的 Claude Code 进阶经验。本文把它们整理成五类可落地做法：验证循环、上下文管理、hooks 自动化、MCP/Roslyn 语义工具，以及 worktrees 和模型选择。"
tags: ["Claude Code", ".NET", "AI", "MCP", "开发工具"]
slug: "claude-code-advanced-tips-dotnet"
ogImage: "../../assets/865/01-cover.png"
source: "https://codewithmukesh.com/blog/claude-code-tips-advanced/"
---

![Claude Code 在 .NET 项目中的验证、上下文、Hooks 和 MCP 工作流](../../assets/865/01-cover.png)

很多 Claude Code 技巧文章会停在“怎么写提示词”。Mukesh Murugan 这篇更有价值的地方，是把问题拉回到工程现场：.NET 项目有编译、有测试、有 `bin/obj`、有 EF Core migration、有强类型系统，也有大型解决方案里的语义导航问题。

所以高级用法不是让 Claude “更聪明”，而是让它在更明确的边界里工作：能自己跑检查，知道什么时候清理上下文，重复规则交给 hooks，代码理解交给 Roslyn/MCP，大任务交给 worktrees 和 headless runs。

下面按实践价值重组原文的 20 条建议。读完后，你应该能给自己的 .NET 仓库整理出一套更稳的 Claude Code 工作方式。

## 先给检查

原文最重要的一条是：给 Claude 一个它自己能读取的 pass/fail 信号。没有机器可读的结果时，你就是唯一的验证循环，所有错误都等着你肉眼发现。

在 .NET 项目里，这个信号已经存在：

- `dotnet build` 捕捉类型错误、引用错误、API 幻觉。
- `dotnet test` 捕捉行为偏差和回归。
- `dotnet format` 捕捉风格和格式漂移。

更好的提示不是“请小心一点”，而是直接要求：

```text
完成每次修改后运行 dotnet build 和 dotnet test。
如果失败，读取错误并继续修复，直到两者都通过。
```

这会把 Claude 从“看起来写完了”拉回到“检查真的通过了”。对 C# 这种编译型语言来说，这一步比许多提示词技巧都更有效。

## 先计划再动手

多文件修改最容易出现的问题，是 Claude 很快给出一个干净实现，但它解决的是偏掉的问题。原文建议把探索和执行拆开：复杂任务先进 plan mode，让 Claude 只读代码、解释方案、等待你批准，再开始写文件。

适合 plan mode 的场景包括：

- 需要跨多个项目或多个层改动。
- 你自己也不熟悉相关代码。
- 任务涉及认证、权限、数据迁移、缓存、消息队列等边界。
- 你很难用一句话描述最终 diff。

如果是一个真正有表面积的新功能，原文还建议让 Claude 先“采访你”：让它不断提问，直到能写出完整 `SPEC.md`。然后开一个新会话，基于这份规格实现。这样执行阶段的上下文更干净，也不依赖一段混杂的聊天记忆。

## 拆小任务

人类喜欢把相关工作打包，因为感觉效率高。对 coding agent 来说，过大的任务会带来上下文抖动：读了太多文件、记住了太多中间方案，又过早宣布完成。

更稳的方式是把一个功能拆成单一目的的小任务。例如不要一次说“把订单模块改成新流程并补测试”，而是拆成：

- 找出当前订单处理入口和测试覆盖。
- 改一个核心接口或实体。
- 更新一个 handler。
- 补对应测试。
- 跑构建和测试，整理剩余问题。

小任务不只是减少出错，也让失败更容易恢复。一次失败只污染当前小上下文，不会拖累整个功能会话。

## 管理上下文

原文有一个很重要的判断：真正的瓶颈是 context，不是模型。质量通常会在窗口满之前就开始下降，所以要把上下文当预算花。

几个规则很实用：

- 切换到无关任务时运行 `/clear`。
- 用 `/context` 看窗口里到底塞了什么。
- 在自然断点提前 compact，而不是等 Claude 开始遗忘。
- 长任务让 Claude 把进展写进 Markdown，再 `/clear` 后从文件恢复。
- 把探索交给 subagent，让主会话只接收摘要。

`CLAUDE.md` 也要克制。它会进入每次对话，越臃肿越浪费。里面适合放 Claude 无法自己推断、且经常会影响结果的规则，比如目标框架是 `.NET 10 / EF Core 10`、项目使用 `.slnx` 而不是 `.sln`、API 文档用 Scalar 而不是 Swagger、响应格式和架构边界是什么。

如果某条规则只是偶尔用到，放进 skill 或按需加载的文档更合适。原文还提醒：当 Claude 总是忽略某条规则时，可以用 `/memory` 查看实际加载了哪些 instruction 文件，很多时候规则只是被埋在太长的文件里。

## 权限要分层

一直批准 `dotnet build` 不是安全，只是噪音。噪音多了，人会习惯性点通过，真正危险的操作反而更容易混过去。

原文给了一个 `.claude/settings.json` 例子：把可信命令放进 `allow`，把危险命令放进 `ask`。

```json
{
  "permissions": {
    "allow": [
      "Bash(dotnet build:*)",
      "Bash(dotnet test:*)",
      "Bash(dotnet format:*)"
    ],
    "ask": ["Bash(dotnet ef database update:*)"]
  }
}
```

这样构建、测试、格式化不会反复打断，但数据库更新这类操作仍然需要人工确认。对团队来说，这个文件可以提交进仓库，让所有人继承同一组 guardrails。

## Hooks 胜过口头规则

写在 `CLAUDE.md` 里的“记得运行 format”只是建议。Claude 忙起来会忘。hook 则是确定性的：工具调用之后自动执行。

原文示例是用 `PostToolUse` hook 匹配 `Write|Edit`，拿到被编辑文件路径后对该文件运行 `dotnet format`：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | xargs -I{} dotnet format --include {}"
          }
        ]
      }
    ]
  }
}
```

同理，测试更适合放在提交门口，而不是每次编辑中途都打断 Claude。可以在 `git commit` 或 `Stop` hook 里跑测试。原文提到一个细节：hook 用 exit code `2` 可以把失败反馈给 Claude，让它继续修复，而不是被当成普通错误忽略。

## 技能沉淀流程

重复流程适合变成 skill：创建 vertical slice、按团队约定跑 EF Core migration、发 PR 前检查、生成 API endpoint 模板等。

skill 的好处是“需要时才加载”。它不像 `CLAUDE.md` 那样每次占上下文，又比临时复制一段提示词更稳定。原文也提到，Claude Code 现在把 custom slash commands 合并进 skills，所以复用命令优先考虑 skill 格式。

一个好 skill 不必长，但要写清楚：

- 什么时候使用。
- 要读取哪些文件。
- 允许做什么，不允许做什么。
- 完成后必须跑哪些验证。
- 输出什么结果给用户。

这类沉淀比“每次重新提醒 Claude”更适合团队协作。

## 给它 .NET 感知

默认情况下，Claude 读代码像读文本。大型 C# 解决方案里，仅靠 grep 很快会遇到边界：接口实现、引用关系、诊断信息、泛型约束、重载解析，都不是简单文本匹配能稳定解决的。

原文建议接入 Roslyn-based MCP server。通过 MCP，Claude 可以调用类似 `find_references`、find symbol、diagnostics 这类语义操作。它查找接口实现时，不必把一堆文件塞进上下文，而是向工具要一个精确结果。

另一个建议是 Context7：让 Claude 能拿到版本对应的实时文档，减少“看起来像真的、实际已过期”的 API。尤其是 ASP.NET Core、EF Core 这类版本变化快的库，当前文档能减少很多编译失败。

但 MCP server 不是越多越好。原文提醒：每个连接的 MCP server 都会把工具定义注入上下文，即使没用也占窗口。实际项目里控制在 3 到 4 个更稳。

## 提示里写类型

C# 的强类型系统不只是代码里的约束，也应该进入提示词。

模糊描述：

```text
写一个处理订单的方法。
```

更好的描述：

```text
添加一个方法，接收 Order 实体，返回 ProcessingResult。
遵守现有 IOrderProcessor 接口约定，并补充对应单元测试。
```

后者让 Claude 贴近真实模型，不会自己发明输入输出形状。原文把这点称为 .NET 开发者的优势：你已经有类型、接口和领域对象，就应该在 prompt 里直接引用它们。

## 警惕旧二进制

原文有一条很贴近编译型语言：Claude 有时会跳过 rebuild，拿旧 binary 跑测试，然后围绕一个不存在的问题来回修。

当测试结果和代码直觉不一致时，先怀疑 build，而不是业务逻辑。更稳的做法是把 `dotnet build` 和测试放进同一个 hook 或验证流程里，确保测试跑的是当前源码对应的输出。

这条对 .NET 特别重要，因为 `bin/obj` 的旧输出、生成代码、source generator、测试发现缓存，都可能让 agent 误判。

## 并行用 worktrees

两个 Claude 会话在同一个 checkout 里改文件，冲突会很快变糟。对 .NET 来说，还会额外争用 `bin` 和 `obj` 输出。

原文建议用 git worktrees。`claude --worktree feature-x` 可以创建隔离 worktree 和分支，让一个会话构建功能 A，另一个会话重构功能 B。冲突只在合并时出现，而不是在同一个目录里互相踩文件。

这适合真正独立的任务。不要把强耦合的两半功能拆到两个 worktree 里并行做，否则只是把冲突推迟到合并阶段。

## 大批量任务用 headless

对于大规模机械改动，比如从 .NET Framework 迁移到 .NET 10，原文不建议让一个交互式会话背着几百个文件跑到底。

更稳的方式是：

1. 先生成文件列表。
2. 用两三个文件测试 prompt。
3. 调整到稳定。
4. 用 `claude -p "..."` 对每个文件跑独立上下文。
5. 最后统一构建、测试、审查 diff。

原文还提醒：截至 2026 年中，headless 和 SDK usage 会走单独的 Agent SDK credit pool，而不是交互式订阅额度。如果把它放进 CI，要提前考虑预算。

## 模型要匹配任务

不要为不需要推理的工作付费。原文的模型选择建议可以整理成一张表：

| 任务                             | 模型           | Effort       |
| -------------------------------- | -------------- | ------------ |
| 架构决策、复杂调试               | Opus           | high         |
| 常规 endpoint、handler、refactor | Sonnet         | medium       |
| 脚手架、样板代码、简单编辑       | Sonnet         | low / medium |
| 代码库搜索、查找所有用法         | Haiku subagent | low          |

核心原则很朴素：Opus 用在架构和难调试上，Sonnet 承担日常实现，Haiku subagent 做搜索。再配合 `/model` 和 `/effort` 调整，避免所有任务都用同一档成本。

## 最值得先做的三件事

如果只挑三条落地，原文作者的判断是：

- 验证循环：让 Claude 自己跑 `dotnet build` 和 `dotnet test`。
- 上下文卫生：`/clear`、`/context`、提前 compact、精简 `CLAUDE.md`。
- 一个确定性的 hook：例如 `PostToolUse` 后自动 `dotnet format`。

我也赞同这个优先级。很多团队一上来就接一堆 MCP server、写 300 行 `CLAUDE.md`、做复杂 slash command，但最基础的交付方式仍然是“写完了你帮我看看”。先把检查和上下文管住，再去加 MCP、skills、worktrees，收益会更稳定。

Claude Code 真正能帮上忙的时候，不是它像聊天机器人一样回答得更好，而是它进入了你的工程系统：有规格、有验证、有权限、有自动化、有语义工具，也有清晰的停止条件。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [20 Advanced Claude Code Tips for .NET Developers](https://codewithmukesh.com/blog/claude-code-tips-advanced/)
- [Model Context Protocol 文档](https://code.claude.com/docs/en/mcp)
- [Anthropic support: Agent SDK credit pool](https://support.claude.com/en/articles/15036540)
