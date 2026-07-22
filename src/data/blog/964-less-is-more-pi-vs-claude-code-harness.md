---
pubDatetime: 2026-07-22T05:16:01+08:00
title: "Less is More：当精简的 Harness 在基准测试中击败了功能完备的对手"
description: "Databricks 百万行代码基准测试揭示了一个反直觉的结果：Pi 每轮发送的上下文仅为 Claude Code 的约 1/3，但任务完成率持平。这篇文章深入分析两种截然不同的 harness 设计哲学，以及为什么在 Transformer 架构下"更少的信息"反而能带来更好的决策质量。"
tags:
  - ai
  - coding-agent
  - pi
  - claude-code
  - benchmark
  - transformer
  - harness
slug: "less-is-more-pi-vs-claude-code-harness"
source: "https://x.com/Salad95238547/status/2079508549382644194"
ogImage: "../../assets/964/01-cover.png"
---

最近，Databricks 发布了一项引人注目的基准测试。他们从自己的**百万行生产代码库**中提取任务——Scala、Rust、TypeScript、Protobuf、Bazel 全栈覆盖。任务来自真实工程师的 Pull Request，测试由真实的测试套件评判，不用 LLM judge。

他们横向对比了多个 coding agent harness（包括 Claude Code、Pi、Codex 等），搭配多种模型（Opus 4.8、Sonnet 5、GPT 5.4 Mini、GLM 5.2）。结果中有一个数据格外醒目：**同一模型下，Pi 每轮发送的上下文仅为 Claude Code 的约 1/3，但是任务完成率持平。**

这意味着什么？意味着有大量的 token 在 Claude Code 的上下文窗口中并没有转化为实际的任务生产力。这篇文章会拆解两个 harness 在设计哲学上的根本分歧，以及为什么"更少的信息"在 Transformer 架构下可能反而更好。

## Harness 是什么，为什么它如此重要

在讨论具体设计之前，需要先厘清一个概念。当我们说"Claude Code"或"Pi"时，我们说的不是模型，而是 **harness**——模型的运行环境。

一个 coding agent harness 做三件事：

1. **构造上下文**：撰写 system prompt，决定每轮给模型看什么信息
2. **提供工具**：定义模型可以调用的工具（读文件、执行命令、编辑代码……）
3. **管理对话**：决定历史消息如何保留、压缩或丢弃

模型本身的能力是固定的：它通过标准的 API 协议（system prompt + tool definitions + messages）接收请求，不知道也不关心自己跑在哪个 harness 里。从模型的视角看，Pi 发来的请求和 Claude Code 发来的请求在**格式上完全一致**，只是内容不同。

因此，harness 的设计本质上是一个**信息架构**问题：在模型有限的上下文窗口里，放什么、不放什么、以什么形式放。

## 两种截然不同的设计哲学

### Claude Code：信息最大化

Claude Code 的设计假设是：**模型需要尽可能完整的上下文来做出好决策。**

它的 system prompt 包含详细的行为规则（安全策略、权限分类、git 操作规范、PR 创建模板……），每轮通过 system-reminder 注入环境状态（MCP server 连接状态、deferred tools 列表、git status 快照），加载全部的项目配置文件，提供几十个工具的完整定义。

这种设计的逻辑很直觉：信息越多，模型的决策质量越高。Harness 的角色是**搬运工**，尽可能把能找到的信息全部送到模型面前。

### Pi：信息精简

Pi 的设计假设恰恰相反：**模型足够聪明，给它精选过的关键信息就够了。**

它的 system prompt 只有约 170 行，核心就一句"You are an expert coding assistant"加上工具列表。没有详细的行为规则，没有 MCP，没有 system-reminder 注入。默认只给模型 4 个工具（read、bash、edit、write），而不是几十个。需要 grep / find / ls？通过 bash 调用就好。需要搜索？bash 里组合一下也能完成。

把 RISC 和 CISC 的类比用在这里其实很贴切：Pi 像 RISC——指令集精简，每条指令做很少的事，但组合起来灵活高效。Claude Code 像 CISC——指令集庞大，每条指令功能完备，但增加了调度和选择的复杂度。

## 精简具体发生在哪里

### 1. 工具输出的激进截断

这是效果最直接的一层。Pi 对每个工具的输出设了两个限制：**2000 行或 50KB，先到先截**。

一次 `npm install` 输出 3000 行依赖解析日志，Pi 只保留最后 2000 行（对 bash 是尾部截断，因为错误信息通常在最后）。多余的部分写入临时文件，只把路径告诉模型。如果模型需要看前面的内容，它可以自己去 read 那个文件。

每次工具调用节省几 KB 看起来不多，但一个任务下来可能有 10-20 次工具调用，而且这些输出不仅在当轮计费，**在后续每一轮都作为历史上下文重复发送**。累积效应非常显著。

### 2. 结构化的上下文压缩

当上下文接近窗口限制时，Pi 的 compaction 系统用 LLM 生成一份结构化摘要来替代原始历史：

- **保留最近约 20K tokens 原文不动**，只压缩更早的历史。模型手头的工作不受影响。
- **新对话合并到旧摘要上**，不是每次重新生成。即使经过多次压缩，摘要大小是有界的。
- **摘要末尾标注哪些文件读过、改过**，让模型不需要重新读文件来恢复上下文。

摘要格式清晰：`## Goal`（目标）、`## Progress`（进度，分 Done / In Progress）、`## Key Decisions`（关键决策及原因）、`<modified-files>`（修改过的文件列表）。这比让模型自己从原始对话中推断状态要高效得多。

### 3. 精简的 System Prompt

Pi 的 system prompt 信任模型的内在能力。它不告诉模型"用 Read 而不是 cat"——模型的训练数据里已经包含了这类最佳实践。它不列出 50 条行为规则——模型已经知道不该在代码里硬编码密钥。

**技能（skills）也是懒加载的**：system prompt 里只放 name + description + file path，模型需要时自己 read 对应的文件。不需要时，这些内容完全不占上下文。

### 4. 干净的消息协议

每轮发送给模型的消息中，Pi 不注入任何环境元信息。没有 git status 快照，没有 MCP server 状态，没有 deferred tools 列表，没有项目配置全文重发。模型看到的就是纯粹的对话：user、assistant、toolResult，没有额外噪声。

这一点很容易被低估。每一次环境状态注入都是对模型注意力的额外争夺。模型在阅读当前错误信息和用户最新指令的同时，还要"看到"并"忽略"那些在当前步骤无关的环境元数据。

## 为什么"更少"反而"更好"

这是整篇文章最核心的问题。直觉上，信息越多决策越好。但对于当前的 Transformer 架构，这个直觉在两个层面上是错的。

**注意力稀释。** Transformer 的 self-attention 机制要求每个 token 对所有其他 token 计算注意力权重。当上下文从 20K tokens 膨胀到 60K tokens 时，真正相关的信息（当前报错信息、用户的具体要求）在注意力分配中被稀释了。30 个工具定义让模型在每次决策时面对更大的搜索空间，不如 4 个工具让选择变得确定。system prompt 里的 50 条行为规则互相竞争注意力，不如 5 条规则都被模型充分理解和执行。

**过度约束的反效果。** Claude Code 的 system prompt 中有大量对强模型来说是冗余的规则。"不要在 URL 参数里放敏感数据"、"git commit 消息格式"、"用 they/them 代词"——这些模型的训练数据早已覆盖。这些规则不仅占用 token，还有一个微妙的负面效应：**它们暗示模型不具备这些判断力**。过度具体的指令可能导致模型在没有明确指令的场景下反而犹豫不决——"这个情况 system prompt 没有覆盖到，我是否应该保守行事？"

Pi 的做法是信任模型的通用智能，只在真正需要偏离默认行为时才给出指令。这种信任本身可能就是一种更优的设计策略。

## 为什么不同模型在 Pi 上表现都不错

Databricks 测试的一个值得注意的结果是：不只是 Claude，**各家模型在 Pi 上的表现普遍不错**。

这引出了一个更深层的问题：Claude 是在 Anthropic 自己的 harness 上做了后训练的，为什么它在 Pi 这个第三方 harness 上也能好用？GPT 和 GLM 同理。

答案是：**模型的后训练绑定的是协议层，不是 harness 层。**

所有主流模型的 tool-use 能力都是在标准的 function calling 协议上训练的：接收 JSON schema 格式的工具定义，生成结构化的工具调用，处理工具返回结果。这个协议是通用的。Pi 使用的是完全相同的协议，只是定义了更少的工具、更短的描述。

从任何模型的视角看，Pi 发来的请求就是一个标准 API 调用：一段简短的 system prompt、4 个工具定义、一组消息。模型不知道自己跑在 Pi 上还是 Claude Code 上，它只是在做自己被训练的事情：理解指令、调用工具、解决问题。

而且，精简的上下文对所有模型都有利。一个被训练得擅长处理复杂场景的模型，面对更简单的场景只会更轻松，不会更困难。

## 启示

这篇文章不是在说 Pi 比 Claude Code 好，而是在揭示一个更普遍的工程原则：**在模型能力快速提升的背景下，信息架构的设计重心正在从"补足模型短板"转向"为模型清场"。**

几年前，模型容易犯低级错误，所以 harness 要写大量的 guardrail 和 checklist 来约束它。但当模型已经足够聪明、自己就知道不该在 URL 里放密钥时，那些 guardrail 从"保护"变成了"噪音"。

Databricks 的基准测试给出的是一个具体的数据信号：在当前这个模型能力水平下，**信息精简已经开始在投入产出比上超越信息堆砌**。这不是说所有场景都应该砍掉信息，但至少说明，对于每一个被放进上下文窗口的 token，我们都应该问一句：它真的在帮助模型做更好的决策吗？

---

如果你关注 AI 编程工具、模型能力分析和软件工程实践，可以关注 **Aide Hub**。这里会持续分享能落地的工具观察、技术分析和项目经验。

## 参考

- [Less is More: 当精简的 Harness 击败了功能完备的对手 — SaladDay on X](https://x.com/Salad95238547/status/2079508549382644194)
- [Benchmarking Coding Agents on Databricks' Multi-Million Line Codebase](https://www.databricks.com/blog/benchmarking-coding-agents-databricks-multi-million-line-codebase)
