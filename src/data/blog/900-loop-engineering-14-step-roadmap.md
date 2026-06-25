---
pubDatetime: 2026-06-25T12:48:27+08:00
title: "Loop Engineering 实战路线：从手动 Prompt 到自主循环的 14 步"
description: "从 Prompter 升级为 Loop Designer 的完整路线图。14 步覆盖自检决策、五大核心组件、构建顺序、安全陷阱和思维转变，每一步都附带 Codex 和 Claude Code 的具体操作对照。"
tags: ["AI Agent", "Loop Engineering", "Claude Code", "Codex", "Agent"]
slug: "loop-engineering-14-step-roadmap"
ogImage: "../../assets/900/01-cover.png"
source: "https://x.com/0xCodez/status/2064374643729773029"
---

大多数开发者还在手工 prompt coding agent——打字、等待、读 diff、再打字。10 个 builder 里至少有 9 个没写过一条自动 prompt agent 的循环：没有自动化，没有状态文件，没有验证器，没有调度机制。

杠杆支点已经变了——从"你自己写 prompt"变成了"你设计一个替你写 prompt 的系统"。

Anthropic 工程师现在的每日代码合并量是 2024 年的八倍。这个数字有争议，但机制没有争议：他们不再一行一行推着 agent 走，他们设计 Loop，Loop 推着 agent 跑。

下面是 14 步完整路线图，分成三个阶段的实战方法。

## 第一阶段：先想清楚要不要上 Loop

### 01. Loop Engineering 是什么

两年以来，你使用 coding agent 的方式从未变过：写一条 prompt → 给上下文 → 读回复 → 写下一句 prompt。Agent 是工具，你全程握着它。

这一页在翻过去。

Loop Engineering 是造一台小机器，让它自己在后台做到：**发现**该做什么、**交给** agent 执行、**检查**结果、**记录**发生了什么、**决定**下一步。你设计一次，之后系统自己跑。

Addy Osmani 把它拆成六个部分：

```text
找活 → 拆任务 → 交给 agent → 检查结果 → 记录状态 → 决定下一步
```

### 02. 动手前先过四道闸

Loop 有条件地成立。四条全满足才值得上。缺一条，架构成本会超过收益：

1. **任务会重复发生。** 至少在每周的频次上重复出现。一次性任务一条好 prompt 更快更便宜。如果工作不重复到每周至少来一次，你没有 Loop，你只是跑了一次脚本。
2. **验证可以自动化。** Loop 需要能自动判定失败的东西：测试套件、类型检查、lint、构建。没有自动检查等于你还在椅子上读每一份 diff——而这恰恰是 Loop 被设计出来要取代的事。
3. **token 预算能承受浪费。** Loop 会重读上下文、重试、探索。不管这一轮有没有产出，token 都在烧。这项技术跟预算成正比——对有免费用量的人它显而易见，对计量付费的人它可能是个坑。
4. **Agent 拥有资深工程师的工具。** 日志、复现环境、运行自己写的代码并看到哪里出错的能力。没有这些，Loop 在盲目迭代。

### 03. 谁赚、谁亏

经济账不是普适的。说 Loop 显而易见的人通常没有 token 限额。觉得这事在冒险的人通常正用着 $20 的消费级套餐、用重型验证循环撞上限或等着意外账单。

**现在该上 Loop 的：** 有强测试套件的代码库、有预算的团队、任务重复且可机器检验的场景。

**现在该跳过的：** 消费套餐的独立开发者、没有自动验证的代码、审查带宽而非打字速度才是真实瓶颈的团队。

### 04. 30 秒 Loop 决策清单

战略决策做了四条判别法，战术层面再跑这五条快速清单。缺一条就维持手动 prompt：

1. 任务至少每周发生一次
2. 测试、类型检查、构建或 lint 能拒绝错误输出
3. Agent 能运行自己改过的代码
4. Loop 有硬停止条件（token 预算 / 迭代次数 / 时限）
5. 不可逆的操作（合并、部署、依赖变更）前有人工审批

**适合做第一个 Loop 的场景：** CI 失败分类、依赖升级 Pr、lint 修复、flaky test 复现、强测试代码库的 issue→PR。

**不该 Loop 化的：** 架构重写、认证/支付代码、生产部署、模糊产品需求、"做完"靠人判断的东西。

## 第二阶段：五大核心组件

### 05. Automation（心跳）

自动化让 Loop 从一个"你跑了一次的东西"变成一个真正的 Loop。它按日程、按事件、按条件触发。

Claude Code 三件套：

```text
/loop 30m /goal All tests in test/auth pass and lint is clean.
  Scan src/auth for new failures, propose fixes in claude/auth-fixes,
  open draft PR when goal condition holds.

▲ Claude
  CronCreate(*/30 * * * * : auth quality loop)
  Stop condition: tests pass + lint clean (verified by checker)
  ✓ Scheduled. Will continue past intermediate completions
  until /goal condition is met by independent checker
```

Codex Automations 标签页里：选项目、设 prompt、设频率、选本地 checkout 或后台 worktree。有结果的进 Triage 收件箱，没结果的自动归档。

`/loop` 按间隔重跑，`/goal` 跑到条件被验证为真。一个单独的校验模型检查完成状态——干活的和判分的不是同一个 agent。

### 06. Worktree（并行不冲突）

两个 agent 同时操作同一份文件，跟两个工程师脑交到同一个插槽上是同一种痛苦。**Git worktree** 解决这个问题：给每个 agent 在独立分支上开辟独立工作目录，共享同一份仓库历史。

Codex 内建 worktree 支持，Claude Code 直出 `--worktree` 参数，sub-agent 的 `isolation: worktree` 配置让每个帮手的 checkout 互不干扰、跑完自动清理。

Worktree 消除了文件冲突，但你仍然是天花板——审查带宽决定了能同时跑多少个并行 agent，不是工具。

### 07. Skill（知识写入一次，每次读取）

Skill 解决的是"每次启动 agent 都像金鱼一样重新解释整个项目"的毛病。格式统一：一个文件夹，里面放 SKILL.md 保存指令和元数据，可选脚本、引用和资源。

对 Loop 特别重要：没有 Skill 的 Loop 每轮都要从零推演出整个项目上下文。有了 Skill，意图得以累积——写法约定、构建步骤、"上次因为那个事我们再也不这样做了"——在外部写一次，每次读进来。

```markdown
---
name: ci-triage
description: Classify CI failures by root cause
  (env, flake, real bug, dependency, infra),
  draft fixes for the easy ones, escalate the rest.
---

## Classification rules

- env: missing secret, wrong env var, infra not provisioned. #human
- flake: passes on retry without code change. # retry once, then file
- bug: deterministic failure tied to recent commit. # draft fix
- dependency: failure tied to a version bump. # draft rollback

## Never do

- Disable failing tests
- Modify CI config without human approval
- Touch src/payments/ or src/billing/

## State

Update STATE.md after each run: files checked, classifications,
PRs opened, items escalated.
```

### 08. Connector（让 Loop 触碰真实工具）

一个只能看到文件系统的 Loop 是个微型 Loop。通过 MCP（Model Context Protocol），Connector 让 agent 读取 issue tracker、查询数据库、打 staging API、在 Slack 里发消息。

这是"agent 说这里有修复"和"Loop 自己开 PR、关联 Linear 工单、CI 绿了之后在频道里通知"之间的区别。

回报最快的 Connector 排序：**GitHub**（读仓库、创建分支、开 PR）→ **Linear / Jira**（更新工单、关联 PR）→ **Slack**（推送分类结果、早上汇报通宵跑的结果）→ **Sentry**（调查告警、高频错误的自动修复）。

### 09. Sub-agent（写手和审手分开）

Loop 里最有用的结构性技巧就是把干活的 agent 和检查的 agent 拆开。

Osmani 的说法一针见血：写了代码的那个模型"批改自己作业时太心软了"。第二个 agent，用不同的指令、有时换不同的模型，专门抓第一个自说自话的漏洞。

这是 Anthropic 2024 年 12 月工程文章里提到的 evaluator-optimizer 模式：一个模型生成，另一个批判，循环往复。

- **Codex**：在 `.codex/agents/` 里用 TOML 定义自定义 agent，可指定模型和推理强度。安全审查跑强模型高 effort，扫描用便宜快模型。
- **Claude Code**：在 `.claude/agents/` 里配 sub-agent 和 agent teams，典型分工：一个探索、一个实现、一个按 spec 验证。

在 Loop 里尤其关键——Loop 是在你没盯着的时候跑的，一个你信得过的校验者是你敢走开的唯一理由。Sub-agent 多烧 token（每个都做自己的模型和工具调用），但把钱花在需要第二意见的地方。

## 第三阶段：正确构建或者别构建

### 10. State File（agent 会忘，文件不会）

这句话听着太朴素，实际是所有能跑起来的 Loop 的脊梁。一份 Markdown 文件、一个 Linear 看板、一段 JSON——任何活在单一对话之外、记录着"做了什么、下一步是什么"的东西。

Osmani 的定律：**agent 会忘，repo 不会。** 没有持久状态的 Loop，每轮从零开始；有状态的 Loop，从断点继续。

```text
# Loop state · ci-triage

## Last run
2026-06-09 03:30 UTC · 7 failures classified, 3 fixes drafted, 4 escalated

## In progress
- claude/fix-auth-token-refresh — tests passing locally, awaiting CI
- claude/fix-flaky-payment-webhook — retry pattern applied, monitoring

## Completed today
- claude/bump-axios-1.7.4 → merged (CI green, deps loop verified)

## Escalated to humans
- src/billing/refund.ts — tests failing in 3 ways, root cause unclear

## Lessons learned
- 2026-06-08: PowerShell hits TLS 1.2 issue on this Windows runner. Use bash.
- 2026-06-07: tests/e2e/checkout requires Stripe webhook secret in env. Skip if missing.
```

两种落地方式：**Markdown 在 repo 里**（根目录 STATE.md，版本受控，diff 可读，适合个人和小团队），**外部系统**（Linear、GitHub Issues、数据库，跨 repo 存活、可查询、团队可见）。

长跑 Loop 容易漂移出目标的话，在状态文件旁边放一份不动的高层 spec——VISION.md 或 AGENTS.md——agent 每轮重读。状态告诉它"现在在哪"，spec 告诉它"要去哪里"。

### 11. 最小可用 Loop

四条判别法都满足了？先搭能跑的最小 Loop，再上花活。四个零件，不用 swarm：

1. **一个 Automation。** 按日程触发，到条件就停。
2. **一个 Skill。** 一份 SKILL.md 存着每轮都要用的项目上下文。
3. **一个 State File。** 记录完成和待做的事。明天的跑是从续跑开始而不是重起。
4. **一个 Gate。** 测试、类型检查、构建——能自动判定失败的机制。**这是决定 Loop 是帮手还是吞钱机器的分水岭。**

顺序严格：先手动跑通一次 → 转成 Skill → 包上 Loop → 再调度。跳过顺序是 Loop 在生产里炸掉的经典路径。

真正要盯的指标是**每次采纳变更的成本**——不是 token 消耗量、不是尝试了多少个任务、不是开了多少个 Loop。采纳率低于 50%，审查工作其实没省下来，Loop 在亏。

### 12. Ralph Wiggum Loop（静默失败）

工程师 Geoffrey Huntley 记录并命名了这个失败模式：agent 本该只在完成时才发射完成标记，但它提前发射了。Loop 从半截活上退出。没有硬门的 Loop 不会崩溃，它只在沉默中烧钱。

成因：没有真正的验证器（只有第二个 agent 被要求"审核"却没有客观信号）、软完成条件（"agent 觉得做完了"代替了测试通过）、没有硬停顿。

修复方案就是第 11 步的 Gate——一个客观的、能判定失败的机制：测试过或不过、构建通过或不通过、lint 零或非零。不是在问一个验证器它怎么看。

其他值得知道的失效模式：长时间运行的**目标漂移**（每次压缩步骤都有信息丢失，"不要做 X"的限制在第 47 轮消失）、**自我偏好偏差**（干活模型给作业打 A+）、**agentic 懒惰**（提前宣布"差不多了"）。

### 13. 理解债与认知投降

这是 Loop 越**好**就越尖锐的失效模式，两个概念都来自 Osmani：

**理解债：** Loop 拉代码的速度越快，仓库内容和你理解之间的差距就越大。疼的账单不是 token 账单——是有天你要调试一个团队里没人读过的系统的那天。

**认知投降：** 停止形成自己的判断、接受 Loop 返回什么都行的倾向越来越强。带着判断力设计 Loop 是解药，为了逃避思考而设计 Loop 是加速器。同一个动作，相反的结果。

非技术缓解手段：**读 diff**（不读 Loop 交了什么就是在借复利利息）、**抽检闸门**（挑几个 Loop 开的 PR，验证批准它的测试真的抓住了你要防的失败模式）、**禁止 Loop 碰架构工作**（只让它做小范围机器可检查的改动）、**搭伙设计 Loop**（第二双眼睛在 Loop 设计阶段就能抓住盲点）。

### 14. 安全税

无人值守的 Loop 同时也是无人值守的攻击面。

- **生成代码未经审查就合入。** Loop 开 PR 的速度比人读得快。没有安全扫描卡口（SAST、依赖审计、密钥扫描），不安全代码自己合进去了。
- **Skill 作为注入向量。** 自动安装 Skill 的 Loop 会继承所有藏在描述里的 prompt injection。安装前审计 Skill 来源。
- **凭据散进日志。** 长跑 Loop 的调试日志会把密钥撒遍你不监控的日志文件。生产 Loop 里关掉 verbose 日志，清理真输出。
- **权限范围蠕变。** 一开始用只读权限测试，后来"就加一个"写权限，再也没审计过。每 30 天重新审计权限。

## 十个最常见的坑

- 没过四条判别法就开建 Loop
- 没有客观闸门（第二个 agent 只是第二个乐观主义）
- 同一个 agent 既写又验（自批自改永远 A+）
- 没有状态文件（明天从零开始而不是继续）
- 模糊的停止条件（"看着差不多就行"永远不会满足）
- 没有 token 预算上限（雄心勃勃的 Loop 烧掉你预期的 5-10 倍）
- 消费套餐上跑重型验证（token 账单和速率限制总有一个先到）
- 自动安装社区 Skill（17,022 个已审计 Skill 中有 520 个泄露凭据）
- Loop 碰判断型工作（架构、认证、支付、模糊产品需求）
- 不读 diff（理解债复利计息）

## 这支点已经移了

两年里，coding agent 的支点在 prompt 上——更好的 prompt、更好的上下文、更好的一次性输出。那个阶段在结束。

Agent 已经够好了，下一个支点在上一层：决定它们做什么、什么时候做、用什么闸门、什么状态在运行之间存留的那个系统。

但这篇文章的诚实版本不是"每个人都该赶紧建 Loop"。大多数开发者现在还不需要——直到任务重复、验证自动化、预算能承受浪费、agent 有资深工程师的工具。

那一刻还没到的时候，一条好 prompt 仍然是正确的答案。如果你关注 AI Agent、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Loop engineering: the 14-step roadmap - Codez (@0xCodez)](https://x.com/0xCodez/status/2064374643729773029)
- [Loop Engineering Clearly Explained - Akshay Pachaar](https://x.com/akshay_pachaar/status/2069118430582866051)
- [Addy Osmani: Loop Engineering](https://x.com/addyosmani)
- [Geoffrey Huntley: Ralph Wiggum Loop](https://x.com/GeoffreyHuntley)
