---
pubDatetime: 2026-08-26T19:19:00+08:00
title: "AgentHarness：把 Agent 运行时变得可验证"
description: "AgentHarness 处理的核心不只是调用模型，还包括会话持久化、运行时配置、队列、保存点、Hook 重入与恢复边界。本文依据 pi 的设计文档，拆解四类状态、一次 turn 的时序，以及哪些能力已实现、哪些仍在计划中。"
tags: ["AI Agent", "AgentHarness", "TypeScript", "软件架构"]
slug: "agentharness-lifecycle-design"
ogImage: "../../assets/1025/01-cover.jpg"
source: "https://github.com/earendil-works/pi/blob/137547a4/packages/agent/docs/agent-harness.md"
---

一个能调用模型的 Agent loop 并不难写。真正难处理的是运行中的变化：模型请求已经发出时，配置能不能修改？Hook 在事件里再次调用 Harness 会不会死锁？会话写入还没落盘时进程崩溃，队列和消息会不会丢失？

`AgentHarness` 的设计，正是围绕这些时间和状态问题展开。它位于低层 Agent loop 之上，负责会话持久化、运行时配置、资源解析、操作锁，以及扩展可以安全调用的变更语义。本文依据 `pi` 仓库在 commit `137547a4` 的 `agent-harness.md`，把这份设计文档整理成一张可检查的生命周期地图。

先给结论：Harness 的核心价值，是把「当前请求」「下一轮配置」「已持久化会话」和「等待落盘的写入」分开管理，再用明确的 phase 和 save point（保存点）规定它们何时交汇。Agent 的异步行为因此有了可以测试的顺序和边界。

## 四类状态要先分开

设计文档把 Harness 状态拆成四类。理解这四类状态，基本就掌握了后面所有时序规则：

| 状态                   | 含义                                                         | 读取或修改规则                                                 |
| ---------------------- | ------------------------------------------------------------ | -------------------------------------------------------------- |
| Harness config         | 应用或扩展最近设置的模型、工具、资源、提示词和流选项         | Getter 返回最新配置；Setter 可在 turn 运行时更新，影响后续快照 |
| Turn snapshot          | 某一次 LLM turn 使用的具体模型、工具、资源、提示词和会话分支 | 创建后保持稳定，不被运行中的配置修改影响                       |
| Session                | 已经持久化的会话条目和当前树叶节点                           | 读取只看已落盘状态，不包含排队中的写入                         |
| Pending session writes | 操作繁忙时接收、等待进入 Session 的写入                      | 必须持久化，在保存点、结算和失败清理阶段刷新                   |

这张表解决了一个经常被忽略的问题：`getModel()` 到底应该返回什么？答案是 Harness 当前配置里的模型，而非已经发出的 provider 请求正在使用的模型。后者属于某个 turn snapshot，二者不能混用。

## 一次 turn 的时序

结构性操作开始前，Harness 必须处于 `idle`，并在第一个 `await` 之前同步切换 phase。`prompt()`、`skill()`、`promptFromTemplate()` 都遵循相同的主流程：

```text
idle
  │
  ├─ 检查并切换为 turn
  ├─ createTurnState() 创建快照
  ├─ executeTurn() 执行低层 Agent loop
  ├─ 持久化 assistant 与 tool-result 消息
  ├─ 在 save point 刷新 pending writes
  ├─ 为下一轮创建新快照
  └─ 操作结束，恢复 idle
```

一个运行中的 turn 可以接受 `steer`、`followUp`、`nextTurn`、`abort` 和运行时配置 Setter。`prompt`、`skill`、`compact`、`navigateTree` 等结构性操作要求 Harness 空闲；繁忙时调用会收到 `AgentHarnessError`，错误码为 `busy`。

这样的区分让队列操作和结构操作拥有不同语义：队列可以在当前操作的安全点排入下一步内容，树导航和压缩则需要先等当前操作结束，避免两个结构变更同时改写会话树。

## 快照保护当前请求

快照机制解决的是「运行中改配置」的问题。

假设一个 turn 已经根据模型 A 创建了 provider request，此时应用调用 `setModel(模型 B)`。正确结果应当是：当前 provider request 继续使用模型 A，下一轮快照使用模型 B。相同规则适用于 thinking level、tools、active tools、resources、stream options、system prompt 和 derived session id。

系统提示词提供器也只在 `createTurnState()` 时调用一次。这个 turn 的后续逻辑都读取同一份结果，避免同一次请求在不同阶段得到不同的系统提示词。

资源数组、stream options 以及其中的 `headers`、`metadata` 会做浅复制。资源对象本身不会深复制；凭据则在每次 provider request 通过 `getApiKeyAndHeaders()` 重新解析，以便处理过期 token。这里体现的是两种不同需求：请求配置需要保持快照稳定，短期凭据需要保持可刷新。

## Save point 是唯一的交汇处

保存点发生在 assistant turn 以及对应的 tool-result 消息完成之后。此时 Harness 按顺序做三件事：

1. 先保存本轮 Agent 已产生的消息。
2. 再刷新操作期间积累的 pending session writes。
3. 如果低层 loop 还要继续，再创建下一份 turn snapshot，并应用新的配置。

这个顺序直接决定了会话的可读历史：扩展在当前 turn 中追加的写入，不能插到 Agent 已经产生的消息之前。文档还要求 `message_end` 的持久化发生在订阅者通知之前；这样订阅者即使随后失败，已提交的消息也不会从会话中消失。

Hook 或 subscriber 在提交之后抛错时，状态变化不会回滚，公共方法会以 `AgentHarnessError` 拒绝，并保留 `hook` 原因。这个选择很实际：持久化和通知属于两个阶段，事后回滚存储往往比报告通知失败更危险。

## Session 不只是聊天记录

在这份设计里，Session 是所有需要恢复的 Agent 状态的追加式日志，内容包括：

- 模型和 thinking level 变化；
- 会话树叶节点和分支摘要；
- compaction、custom message、custom entry；
- `steer`、`followUp`、`nextTurn` 队列；
- 操作、turn、provider request 和 tool call 的持久化记录；
- 操作繁忙时接收的 pending session writes。

`setLeafId()` 也属于持久化变更。它会追加一条带 `targetId` 的 leaf entry，而不是只修改内存中的游标。重新打开存储后，系统可以根据最新的叶节点相关条目重建当前会话树位置。

`abort()` 有两个容易被误解的边界：它会终止低层运行并清空 steering/follow-up 队列，但不会清除 `nextTurn()` 已排入的消息，也不会丢弃 pending session writes。前者会在下一次用户发起的 turn 前插入，后者会在下一个保存点、`agent_end` 或失败清理时刷新。

## Hook 需要控制面与观察面

文档关联的 `hooks.md` 给出了一套最终设计。它把事件处理分成两个层面：

- `observe()` 只观察事件，返回值被忽略，订阅者错误不应影响 Agent 执行；
- `on(type, handler)` 参与该事件的业务语义，返回值可能修改上下文、阻止工具调用或取消会话操作。

事件自己携带结果类型，处理器因此可以获得类型安全的返回值。不同事件的合并规则也不一样：

| 事件                      | 处理语义                                             |
| ------------------------- | ---------------------------------------------------- |
| `context`                 | 按注册顺序变换消息，每个处理器看到前一个处理器的结果 |
| `before_provider_payload` | 逐个修改 payload，后一个处理器看到前一个处理器的补丁 |
| `before_agent_start`      | 汇总注入消息，并按顺序串接 system prompt             |
| `tool_call`               | 顺序执行，遇到 `block` 立即停止                      |
| `tool_result`             | 累积 content、details、isError 等补丁                |
| `session_before_*`        | 顺序执行，遇到 cancel 立即返回                       |

Harness 本身只需要调用 `this.hooks.emit(event, signal)`，不保存处理器、不拼接监听器，也不替扩展决定注册策略。工具、命令、快捷键、模型注册等能力属于注册表，应该放在更上层的 `CodingAgentHooks` 或扩展宿主中。

这里必须标出状态边界：主文档把通用 Hook/Event extension mechanism 标为“已设计，尚未实现”。`hooks.md` 是最终设计文档，不能当成当前公开 API 已经全部可用的证明。

## 半持久化恢复比完整恢复更现实

`durable-harness.md` 没有承诺把整个 Harness 序列化。模型对象、工具实现、扩展处理器、资源加载器、系统提示词回调和认证提供器，都是由宿主应用在恢复时重新创建的运行时依赖。

更现实的目标是半持久化：Session 保存追加式状态，Harness 保存自己拥有的队列、操作和 pending writes；恢复时由宿主重新注册兼容的模型、工具、扩展、资源、Hook 和认证提供器。

恢复流程可以概括为：

```text
重新注册运行时依赖
        │
打开 Session 并归约日志
        │
恢复会话树、配置、队列、pending writes 和未完成操作
        │
校验依赖版本或稳定标识
        │
按保守策略处理未完成操作
```

默认恢复策略应当偏保守：未完成的 Agent turn 和 provider request 标记为 interrupted；未完成的 tool call 不自动重试，除非工具明确声明幂等或可安全重试；压缩和树导航只有在缺少最终条目时才考虑重跑。

原因在于 provider stream 无法从中途恢复，工具调用还可能已经产生外部副作用。恢复逻辑不能仅凭「上次没有写完结果」就再次执行一个扣款、发消息或删除资源的工具。

## 可观测性应当保持被动

关联的 observability 设计把可观测性与 Hook 控制面分开。一次用户 turn 可以形成一棵 trace/span 因果树，例如：

```text
pi.agent.prompt
  └─ pi.agent.turn
       ├─ pi.ai.provider.request
       ├─ pi.agent.tool_call
       └─ pi.agent.session.append_entry
```

核心包只发出运行时无关的结构化事件，由 Node、浏览器或其他运行时适配器决定是否映射到 OpenTelemetry、Sentry、日志或自定义指标。Node 环境可以使用 `AsyncLocalStorage` 保存异步链上下文，浏览器和 Worker 则使用自己的适配器；Node 专属 API 不应进入通用核心。

可观测性事件默认只带 provider、model、session id、entry type、tool name、状态码、token 数、耗时和费用等安全元数据。prompt、completion、tool arguments、shell output、文件内容、请求体和 API key 必须保持关闭，内容采集需要显式开启并经过脱敏。

另一个关键边界是：观察者不能改变 Pi 的执行结果。Hook 是控制面，可以阻止或修改；observability subscriber 是被动记录器，错误应当被吞掉或隔离。

## 当前实现与计划方向

主文档在 commit `137547a4` 中已经给出了清晰的状态列表。可以按下面的方式阅读：

| 范围                                                     | 文档标记的状态                              |
| -------------------------------------------------------- | ------------------------------------------- |
| `createTurnState()`、`applyTurnState()`、`executeTurn()` | 已加入，用于快照创建、应用和执行            |
| 显式 phase、save point、队列消息、pending write 刷新     | 已加入，仍有结算时序和 abort barrier 审计项 |
| `setLeafId()` 的持久化叶节点条目                         | 已加入                                      |
| `getTools()`、`getActiveTools()` 与工具更新可观测事件    | 剩余工作                                    |
| 每个 Harness 的模型注册表                                | 计划中                                      |
| 通用 Hook/Event 扩展机制                                 | 已设计，尚未实现                            |
| 半持久化恢复原型                                         | 计划中                                      |
| 最终生命周期硬化测试、广泛重入测试                       | 计划中                                      |
| 自动压缩、retry、coding-agent 迁移                       | 计划中                                      |

文档还建议把 Harness 测试按领域拆开，并使用 `pi-ai` 的 faux provider 做确定性测试：

```bash
npm run test:harness
npm run coverage:harness
```

覆盖率命令针对 `test/harness/**/*.test.ts` 和 Harness 直接调用的运行时代码。它们是仓库文档给出的验证入口，文章并未在 `pi` 源码仓库中执行这些命令。

## 评审这类 Agent runtime 设计时看什么

如果你正在实现自己的 Harness，可以把下面六个问题当作评审清单：

1. 当前配置和 in-flight 请求是否有清晰的快照边界？
2. 队列、会话写入和 Agent 消息是否有确定的持久化顺序？
3. Hook 在 busy、settled、abort 和失败阶段重入时，是否会死锁或乱序？
4. Getter 返回的是最新配置，还是误把当前 turn snapshot 暴露出去？
5. 崩溃恢复是否默认保护幂等性，避免重复执行外部副作用？
6. 可观测性是否保持被动，且默认不会采集 prompt、文件和密钥？

这些问题比“有没有更多 Agent 工具”更能决定运行时是否可靠。一个拥有很多 API 的 loop，如果没有时序契约，扩展越多，越难解释偶发错误。

## 结论

`AgentHarness` 的设计重点，是给异步 Agent 增加一套可验证的时间语义：Harness config 面向未来，turn snapshot 保护当前请求，Session 保存过去，pending writes 等待安全交汇。phase 限制结构变更，save point 决定配置何时生效，Hook 与 observability 分别承担控制和记录。

这份文档最值得借鉴的地方，也在于它没有把所有目标都写成已完成能力。通用 Hook、半持久化恢复、自动压缩、重试和最终重入测试都被明确列为后续工作。实现 Agent runtime 时，先写出状态分类、事件顺序、失败策略和恢复边界，再扩展工具数量，系统会更容易测试，也更容易解释。

## 参考

- [pi：AgentHarness lifecycle（原文，commit 137547a4）](https://github.com/earendil-works/pi/blob/137547a4/packages/agent/docs/agent-harness.md)
- [pi：AgentHarness hooks design（同一 commit）](https://github.com/earendil-works/pi/blob/137547a47012119310fe13a8a542cac5ba63c521/packages/agent/docs/hooks.md)
- [pi：Durable AgentHarness and session design（同一 commit）](https://github.com/earendil-works/pi/blob/137547a47012119310fe13a8a542cac5ba63c521/packages/agent/docs/durable-harness.md)
- [pi：Observability Design Notes（同一 commit）](https://github.com/earendil-works/pi/blob/137547a47012119310fe13a8a542cac5ba63c521/packages/agent/docs/observability.md)
