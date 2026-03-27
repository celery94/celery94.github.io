---
pubDatetime: 2026-03-27T09:40:00+08:00
title: "把 AI 编程工作流设计成状态机：与 Nick Tune 的对话"
description: "PayFit 高级首席工程师 Nick Tune 分享了他如何把 AI 编程工作流建模成带类型约束的状态机，配合 TDD、依赖检查和 CodeRabbit，让 Claude 从需求到 PR 全程自主交付，同时保持代码质量不失控。"
tags: ["AI", "Claude", "Workflow", "TDD", "Architecture"]
slug: "agentic-code-workflows-nick-tune"
ogImage: "../../assets/677/01-cover.png"
source: "https://newsletter.techworld-with-milan.com/p/agentic-code-workflows-with-nick"
---

![把 AI 编程工作流设计成状态机](../../assets/677/01-cover.png)

AI 编程工具涌现的这两年里，大多数人用 Claude 或 Copilot 解决的是"写个函数、改个 bug"这类局部问题。Nick Tune 走得更远——他把整个软件交付流程设计成一台状态机，让 Claude 能从需求文档一路跑到 Pull Request，中途的每个关键节点都有确定性校验，任何偏差都会在提交前被拦下来。

Nick 是 [PayFit](https://payfit.com/)（欧洲薪酬 HR 公司）的 Senior Staff Software Engineer，也是 Manning 出版的 [Architecture Modernization](https://amzn.to/47Ysx1A) 一书的作者，专注遗留系统现代化、领域驱动设计和持续交付。这篇文章是 Tech World With Milan 对他的专访整理，记录了他在 AI 辅助编程上具体怎么做。

## 怎么看待 AI 工具的使用边界

Nick 的基本态度是"到处用，然后量化结果"。他提到一个例子：高峰期积压了大量客户支持工单，他给自己划了一小时，试着用 AI 构建一套支持工单处理工具（UI + 子 Agent 调查模块）。三天内工具的收益就抵消了开发投入，到周末他感觉整体效率提升了 20—40%。

关键不是工具本身多先进，而是他发现一个中等复杂 bug 竟然跨越了 3 个代码库、需要关联 3 个数据源才能定位根因——Claude 在他处理另一个问题时把这件事悄悄做完了。

他的经验是：**给自己设一个时间盒（timebox），先跑通 ROI，再决定要不要深挖**。有些时候 AI 就是浪费时间，但那也是信息——知道什么不值得做，本身就有价值。

## 把工作流建模成状态机

这是 Nick 最核心的设计思路，也是他区别于大多数人的地方。

他把开发流程里的关键阶段定义成状态，每个状态有明确的：

- **可转移到的下一状态**（`canTransitionTo`）
- **该状态允许的操作**（`allowedWorkflowOperations`）
- **全局禁止、但本阶段例外的命令**（`allowForbidden`）
- **转移前必须满足的条件**（`transitionGuard`）

比如"提交 PR"这个状态的定义：

```ts
export const submittingPrState: ConcreteStateDefinition = {
  emoji: '🚀',
  agentInstructions: 'states/submitting-pr.md',
  canTransitionTo: ['AWAITING_CI', 'BLOCKED'],
  allowedWorkflowOperations: ['record-pr'],
  forbidden: { write: true },

  allowForbidden: { bash: ['git push', 'gh pr'] },

  transitionGuard: (ctx) => {
    if (!ctx.state.prNumber) return fail('prNumber not set. Run record-pr first.')
    return pass()
  },
}
```

每条消息都会带上当前状态的 emoji 前缀（如 🚀SUBMITTING），让你随时知道 Agent 在哪个阶段。Agent 试图切换到不允许的状态时，系统会自动把当前阶段的指令重新注入到错误信息里，让它自行纠正。

整套逻辑是真实的代码，可以写单元测试覆盖所有状态转换——这正是他反复强调的**确定性**。他的开源项目 [living-architecture](https://github.com/NTCoding/living-architecture) 里有完整示例。

## 先写 PRD，再让 Agent 动手

代码开始之前，Nick 会花相当多时间在需求文档（PRD）上。他有一个专门的 [PRD 专家 Agent](https://github.com/NTCoding/claude-skillz/blob/main/system-prompts/prd-expert.md)，设定成"教练"角色——主动追问和挑战他的判断，而不是机械地记录。

他用的 PRD 模板包含：

1. **Problem** — 谁的问题，为什么重要
2. **Design Principles** — 优化什么、权衡什么
3. **What We're Building** — 带验收标准的需求
4. **What We're NOT Building** — 显式边界
5. **Success Criteria** — 怎么判断成功
6. **Open Questions** — 未解决的不确定性
7. **Milestones** — 阶段里程碑 + 可交付成果
8. **Parallelization** — 哪些工作流可以并行
9. **Architecture** — 架构评审时补充

PRD 完成后，他会通过命令把任务创建成 GitHub Issue，这样后续 PR 在关联 Issue 时，人工审查者和 AI 审查工具都能追溯到完整的需求背景。

对于遗留系统迁移类项目，他还有一批专门的 Agent 自动扫描代码库、识别 API 端点、对比目标系统，输出草稿 ADR 供人审阅。他给这些 Agent 的指令非常精确——"为每个 API 端点启用一个独立的子 Agent 进行全链路分析（用独立子 Agent 控制上下文窗口使用量）"。

## 让 Claude 自主实现功能

需求明确后，Nick 的默认做法是"踢一脚，不管了"——他启动 Claude，Claude 会自主走完从需求到 PR 的全程。这套流程用 `docs/workflow.md` 文件描述每个状态要用什么命令，混合了 Slash 命令和实际代码。

他用 pre-commit hook 保证 Claude **不能提交无法编译或 lint 不过的代码**，同时直接屏蔽了 `git commit --no-verify`，让 Agent 没有绕过门禁的机会。

对于 `git push` 这个命令，他设了一个 hook 拦截：

```json
{
  "pattern": "/\bgit\s+push\b/",
  "reason": "Blocked: Direct git push bypasses required workflow. Use /complete-task command instead, which runs the complete verification pipeline (lint, test, code review, PR submission) and prevents orphaned changes."
}
```

Agent 必须通过 `/complete-task` 这个命令才能推送，而这个命令会强制跑完验证流水线（lint、测试、代码评审、PR 提交），整套流程有单元测试确认每次运行顺序一致。

## 代码质量靠规则，不靠嘱咐

Nick 的经验是：每次 Agent 产出了有问题的代码，就往规则集里加一条约束，让同类问题以后不可能再出现。他把这叫做"持续改进测试线束"。

他有大量 ESLint 规则：文件大小上限、函数复杂度、命名规则、代码注释规范，以及**禁用语法**（在 TypeScript 里不准用 `as` 和 `let`，强制类型安全和不可变代码）。

架构层面，他用 [dependency-cruiser](https://github.com/NTCoding/living-architecture/blob/main/eslint.config.mjs) 执行模块边界规则。比如这条规则确保同个 DDD 垂直切片里的功能不能引用另一个切片：

```json
{
  "name": "no-cross-feature-imports",
  "severity": "error",
  "comment": "Features must not import from other features",
  "from": { "path": "features/([^/]+)/.+" },
  "to": {
    "path": "features/([^/]+)/.+",
    "pathNot": "features/$1/.+"
  }
}
```

架构文档同样作为规则来源，有对应的 dependency-cruiser 规则做执行层，"即使 Claude 犯了错，pre-commit hook 和 PR 检查也会失败"。

## 代码评审的分层设计

评审这件事 Nick 是分层做的：

1. **CodeRabbit** — 配置了读取所有编码规范和 ADR，能识别违规、存储历史教训，支持 "下次记得检查 X" 这类反馈
2. **本地评审 Agent** — 代码评审、架构评审、测试评审、QA 检查（功能是否符合需求）、bug 检查，五个独立 Agent
3. **人工自查** — Nick 自己一定会过一遍每个 PR

他也指出 AI 代码评审里一个常见陷阱：不要说"按这些原则评审代码"，要说"对每个修改的文件，逐条检查每项评审原则，用代码 CR-001 这样的格式输出一张审查表"。强制 Agent 逐行核对，而不是让它自行判断重要性。

## TDD：严格的红绿循环

Nick 把 Claude 跑进一个结构化的 TDD 状态机里，每次状态转换都有前置条件和后置条件要验证。以 RED 状态为例，它的前置条件是"测试已写入且正在失败"，必须满足的后置条件是：

- 测试通过（绿色输出）
- 代码编译通过
- Lint 通过
- 只实现了错误信息要求的最小量代码
- 把所有成功输出原文展示给用户

RED → GREEN 的转换只有在全部条件满足时才允许触发。这套状态定义是 XML 风格的结构化文档，目前靠 prompt 执行，Nick 说将来考虑换成确定性代码。

他的测试 lint 规则同样严格：100% 覆盖率（否则构建失败）、单个测试最多 4 个断言、禁用条件断言、测试文件大小上限 400 行（强制拆分成有意义的分组）。

## 自定义 CLI 和系统提示技巧

Nick 有一套[自制的 CLI 工具](https://github.com/NTCoding/claude-skillz/tree/main/claude-launcher)来启动 Claude Code。它根据不同的角色预设构建系统提示，然后用 `claude --system-prompt` 启动会话。

比如 `cl prd opus` 会用 [PRD 专家的系统提示](https://github.com/NTCoding/claude-skillz/blob/main/system-prompts/prd-expert.md) 启动一个专门用于需求讨论的会话，不会把测试规则、代码规范之类的内容塞进来。

他总结了这样做的好处：把内容嵌入系统提示比会话开始后读文件合规率更高，专用系统提示也避免了加载不必要的内容降低注意力。

## 一个实用建议

Nick 的最后一条建议很简单：**遇到重复性、让你烦躁的工作，想想能不能做个 CLI 命令、UI 或知识管理工具来自动化它**。AI 让构建这类简单工具的成本几乎趋近于零。

他自己在等 Claude 完成一个 terminal 的工作时，就用另一个 terminal 里的 Claude 顺手构建下一个小工具——这种并行本身就是效率乘数。

## 参考

- [原文：Agentic code workflows with Nick Tune](https://newsletter.techworld-with-milan.com/p/agentic-code-workflows-with-nick)
- [Nick Tune 的开源项目 living-architecture](https://github.com/NTCoding/living-architecture)
- [Nick 的 Claude 技能集（claude-skillz）](https://github.com/NTCoding/claude-skillz/tree/main/separation-of-concerns)
- [Nick 的自定义 CLI（claude-launcher）](https://github.com/NTCoding/claude-skillz/tree/main/claude-launcher)
- [Nick 的 TDD 流程定义](https://github.com/NTCoding/claude-skillz/tree/main/tdd-process)
