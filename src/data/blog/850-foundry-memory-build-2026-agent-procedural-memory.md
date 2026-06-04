---
pubDatetime: 2026-06-04T10:47:43+08:00
title: "Foundry Memory at Build 2026：让 Agent 记住步骤和边界"
description: "Microsoft Foundry 在 Build 2026 更新了 Agent memory，重点从个性化扩展到可靠执行。本文梳理 procedural memory、管理 UI、TTL、多模态、direct memory commands 和 file-based memory 的实际意义。"
tags: ["Microsoft Foundry", "AI Agent", "Agent Memory", "STATE-Bench", "Azure"]
slug: "foundry-memory-build-2026-agent-procedural-memory"
ogImage: "../../assets/850/01-cover.png"
source: "https://devblogs.microsoft.com/foundry/memory-build2026/"
---

Microsoft Foundry 这篇 Build 2026 更新，讲的是 Agent memory。它的重点从“记住用户喜欢什么”，扩展到一个更工程化的问题：Agent 能不能从过去的任务里学到可复用步骤，之后遇到相似任务时更稳定地执行。

如果你正在做客服、审批、订单、差旅这类多步骤 Agent，这篇更新值得看。因为很多失败来自流程执行问题：跳过校验、误用工具、漏掉政策检查，或者在相似任务里反复犯同一种错。

## 记忆的新重点

原文开头把背景说得很清楚：memory 一直关系到个性化和连续性，但当客户把 Agent 从 demo 推到生产环境后，可靠性变得同样重要。

这次更新围绕几个能力展开：

- procedural memory，用来保存可复用的执行流程。
- Foundry portal 里的 memory 管理体验，支持查看和 CRUD 操作。
- Memory TTL，用来设置记忆的保留时间。
- multimodal support，让 Agent 可以理解并记住图片里的信息。
- direct memory commands，让用户明确要求 Agent 记住或忘记某件事。
- Microsoft Agent Framework 的 file-based memory，让本地开发可以用 Markdown 文件起步。

这些能力合在一起，说明 Agent memory 的方向正在变化。它不只服务于“下次聊天更像认识你”，也服务于“下次执行同类任务时更少漏步骤”。

## 流程记忆

procedural memory 可以翻译成“流程记忆”。通俗地说，它保存的是“什么情况下该按哪些步骤做”。

原文给出的失败例子很具体：企业 Agent 可能知道正确事实，仍然会因为没有执行正确流程而失败。比如跳过 validation step，误用 tool，漏掉 required policy check，或在类似任务中重复错误模式。

procedural memory 的工作方式分两步。

第一步，系统摄取并审计 agent trajectories。这里的 trajectory 可以理解为 Agent 完成任务时留下的执行轨迹，包括对话、工具调用、结果和中间决策。系统会从中识别成功模式、低效路径和缺失步骤，再提取结构化流程记忆。

这些流程记忆会记录两类信息：

- when to use：任务上下文、前置条件和触发信号。
- what to do：有序动作、必需检查和工具使用方式。

第二步，Agent 遇到相似任务时，系统检索相关流程并注入上下文。这样 Agent 会看到明确的步骤级约束，比如必须做哪些验证、工具参数该怎么填、哪些政策检查不能省。

这类记忆对企业任务很关键。因为企业任务常常会改变系统状态：退款、改订单、更新账号、确认资格。漏一步可能带来真实成本。

## 评估证据

原文提到，Microsoft 几周前发布了 STATE-Bench，全称是 Stateful Task Agent Evaluation Benchmark。它是一个开源、memory-agnostic 的 benchmark，用来衡量 Agent 是否能在真实企业任务中随着经验改善。

这里的 memory-agnostic 是指它不限定你使用哪一种记忆实现。你可以带自己的 memory 系统来测试，重点看 Agent 表现有没有变好。

STATE-Bench 的发布文章补充了更多信息：它覆盖 customer support、travel、shopping 三个领域，共 450 个任务，任务包含 policy compliance、information synthesis 和 multi-step reasoning procedures。

它关注三类特征：

- Procedural：Agent 必须按领域流程执行，例如查 booking、验证资格、检查政策、计算费用、确认后再执行。
- Stateful：任务会改变数据库状态，例如退款记录、booking status、account updates。
- User experience：除了任务成功，还评估用户交互质量。

这比单纯测试“能不能从 50 轮前找回一个名字”更接近生产环境。原文还提到，在启用 procedural memory 后，Microsoft 在 STATE-Bench 和 Tau-Bench 评估里看到约 5% 改善。

这个数字不该被解读成所有 Agent 都会自动提升 5%。更合理的理解是：如果你的任务包含重复流程、工具调用和政策检查，流程记忆开始有可测量价值。

## 管理和可见性

企业团队使用 memory 时，另一个问题是透明度。Agent 记住了什么，为什么记住，能不能改，能不能删，这些都不能靠猜。

这次 Foundry portal 增加了 memory 管理体验。开发者可以直接查看 stored memories，并对单个 memory item 做 CRUD 操作。CRUD 是 create、read、update、delete 的缩写，意思是创建、读取、更新和删除。

Microsoft Learn 的 memory 文档也给出了一组更具体的管理接口：创建 memory store、更新属性、列出 store、创建 memory item、读取 item、列出 item、更新 item、删除 item，以及按 scope 删除某个用户或团队的记忆。

这里的 scope 是 memory 的隔离键。你可以把它理解成“这条记忆属于谁”。文档建议在使用 memory search tool 时把 scope 设为 `{{$userId}}`，系统可以从 `x-memory-user-id` 请求头解析最终用户身份。直接调用底层 memory API 时，需要自己显式传入 scope。

这个细节很重要。Agent memory 一旦进入生产环境，隔离错误会比“记错一句偏好”严重得多。最基本的要求是不同用户、团队或租户的记忆不能串到一起。

## TTL 和用户控制

原文这次还提到 Memory TTL。TTL 是 Time-to-Live，意思是生存时间。创建 memory store 时可以配置默认 TTL，让旧的、价值较低的记忆自动退休。

TTL 有两个现实用途：

- 改善检索质量，避免旧信息长期干扰新任务。
- 控制存储成本，避免 memory store 无限增长。

原文给出的 Python 配置片段里，`default_ttl_seconds=30 * 24 * 60 * 60`，也就是默认 30 天。

```python
options = MemoryStoreDefaultOptions(
    chat_summary_enabled=True,
    user_profile_enabled=True,
    procedural_memory_enabled=True,
    default_ttl_seconds=30 * 24 * 60 * 60,
    user_profile_details=(
        "Avoid irrelevant or sensitive data, such as age, financial details, "
        "or anything not useful for personalizing future conversations."
    ),
)
```

direct memory commands 解决的是另一个用户体验问题：用户可以明确告诉 Agent 记住或忘记某件事。对用户来说，这比被动猜测系统是否记录了信息更清楚。

Microsoft Learn 的最佳实践里也强调了类似要求：实现按用户隔离的访问控制，只存必要数据，支持隐私和合规，允许用户访问和删除数据，记录删除操作，监控 memory 使用，并在产品界面里说明保留策略。

## 多模态记忆

multimodal support 让 Agent 可以理解并记住图片里的信息。原文提到，这对 e-commerce 和 customer support 场景尤其有用。

举个更贴近日常开发的例子：用户上传商品照片、故障截图、收据、包装标签或 UI 错误界面时，Agent 不只需要回答当前问题，也可能需要记住与后续处理相关的信息。

这类能力也要谨慎使用。图片里的信息可能包含地址、订单号、联系人、价格、设备序列号或敏感业务内容。是否写入长期 memory，应该由明确的规则控制，不能把“看过”自动等同于“应该长期保存”。

## 文件记忆

原文还提到，memory 也会通过 file-based memory 进入 Microsoft Agent Framework。它的目标是降低开发者起步成本：一开始可以用 Markdown 文件做本地 memory，方便检查、理解和版本管理；应用成熟后，再沿着相同开发模型扩展到更完整的存储和管理形态。

原文给出的 Python 示例大致是这样：

```python
from agent_framework import Agent, MemoryContextProvider, MemoryFileStore

store = MemoryFileStore(
    base_path=Path("./memory"),
    owner_state_key=MEMORY_OWNER_STATE_KEY,
)

memory_provider = MemoryContextProvider(store=store)

agent = Agent(
    client=client,
    name="MemoryDemoAgent",
    instructions="You are a helpful assistant.",
    context_providers=[memory_provider],
)
```

这个设计对早期原型很友好。文件记忆可以直接打开看，也容易纳入测试和版本记录。等系统需要托管、隔离、审计和规模化存储时，再迁移到 Foundry Agent Service 的 memory store。

## 实践判断

如果你正在评估 Agent memory，可以按四个问题来判断这次更新是否相关。

你的 Agent 是否经常重复执行相似流程？如果是，procedural memory 可能比普通偏好记忆更有价值。

你的任务是否会改变系统状态？如果会，STATE-Bench 这类评估方式更有参考意义，因为它关心工具执行、政策检查和最终状态。

你的产品是否需要用户信任？如果需要，管理 UI、CRUD、scope、TTL、删除记录和 direct memory commands 都要进入设计清单。

你的团队是否还在原型阶段？如果是，file-based memory 可以先让开发者看清 memory 到底存了什么，再决定是否接入托管 memory store。

这篇更新最值得带走的判断是：Agent memory 的难点不只是“记得多”，还包括“记得准、用得对、能解释、能删除、能过期”。当 Agent 开始执行真实业务时，这些边界会决定它能走多远。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能实际使用的工具教程、技术观察和项目经验。

## 参考

- [Making agent memory more reliable, transparent, and production-ready](https://devblogs.microsoft.com/foundry/memory-build2026/)
- [Create and use memory in Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/memory-usage?pivots=python)
- [Introducing STATE-Bench: A benchmark for AI agent memory](https://opensource.microsoft.com/blog/2026/05/19/introducing-state-bench-a-benchmark-for-ai-agent-memory/)
- [microsoft/STATE-Bench](https://github.com/microsoft/STATE-Bench)
