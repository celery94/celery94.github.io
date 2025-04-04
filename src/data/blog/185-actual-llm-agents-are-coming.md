---
pubDatetime: 2025-03-15
tags: [AI, LLM, Agents, Reinforcement Learning, Technology]
slug: actual-llm-agents-are-coming
source: https://vintagedata.org/blog/posts/designing-llm-agents
title: 实际的LLM代理即将到来：探索人工智能的新前沿
description: 本文探讨了大型语言模型（LLM）代理系统的最新发展，包括强化学习、搜索策略以及未来应用的潜力。
---

# 实际的LLM代理即将到来：探索人工智能的新前沿

## 代理系统的革命性进展

近年来，代理系统在人工智能领域无处不在。然而，最具影响力的研究进展似乎并未受到足够的关注。在2025年1月，OpenAI发布了[DeepResearch](https://cdn.openai.com/deep-research-system-card.pdf)，这是O3模型的一个专门变体，用于网页和文档搜索。得益于“强化学习在这些浏览任务上的训练”，Deep Research能够制定搜索策略、交叉引用来源，并基于中间反馈处理查询中的小众知识。Claude Sonnet 3.7似乎在代码领域成功应用了相同的配方，其模型在复杂编程任务序列中超越了现有模型的协调。

正如William Brown所[言](https://www.youtube.com/watch?v=JIsgyk0Paic)，“**LLM代理可以执行长期多步骤任务**”。这一进展引发了一个问题：LLM代理究竟是什么？

## LLM代理定义及其挑战

在2024年12月，Anthropic[揭示](https://www.anthropic.com/engineering/building-effective-agents)了一个新的定义：“LLM动态指挥其自身过程和工具使用，保持对任务完成方式的控制。”相比之下，更常见的代理系统形式被称为*工作流程*，“LLM和工具通过预定义的代码路径进行协调”。如最近被热议的Manus AI就符合这一定义。

然而，工作流程系统存在根本性的局限性：

- 无法有效规划，常常陷入困境。
- 记忆能力差，难以维持任务超过5-10分钟。
- 长期行动效果不佳，动作序列常因复合错误效应而失败。

## 简单LLM代理的教训

代理概念几乎与基础语言模型完全冲突。在经典代理研究中，代理在受约束的环境中活动。基础语言模型却是相反：

- 代理记忆其环境，而基础模型只能对上下文窗口内的信息做出反应。
- 代理受到有限理性的约束，而基础模型生成任何可能的文本。
- 代理能够制定长期策略，而语言模型只能执行单一推理任务。

一种调和LLM与代理化的方法是通过预定义输出来准备提示和规则。然而，这种方法常受到Richard Sutton所谓的[痛苦教训](http://www.incompleteideas.net/IncIdeas/BitterLesson.html)影响。痛苦教训强调在长远看来，硬编码知识到模型中并不奏效。

## RL+Reasoning：成功的配方

尽管公开信息有限，但Anthropic、OpenAI、DeepMind等实验室正在探索LLM代理的训练方法。类似于经典代理，LLM代理通过强化学习进行训练，有迷宫和最终奖励。验证器是验证奖励是否达成的过程，可以围绕非严格可验证输出构建。

LLM代理通过**草稿**进行训练，即整个文本生成并评估。这涉及到让模型生成逻辑序列，然后评估结果。当前，DeepSeek的GRPO方法与文本生成结合，是训练LLM代理的首选方法。

## 如何扩展？

虽然建立基础构件很重要，但要从此到OpenAI DeepResearch等能够处理长序列动作的代理，还有一段距离。开放RL推理研究主要集中于数学领域，但对于许多领域尤其是搜索，我们没有足够的数据。

一种方法是直接通过**模拟**生成数据。经典RL模型不需要过去的例子，通过广泛搜索推断约束和策略。一旦转移到搜索，RL方法会让模型自由旅行，并奖励它找到正确答案。

## 实际应用：从理论到实践

Anthropic定义强调了LLM代理“动态指挥其自身过程和工具使用，保持对任务完成方式的控制”。这种能力在搜索中尤为明显。未来的搜索过程可能如下：

- 分析查询、分解并进行假设。
- 如果查询不明确，用户可能立即得到提示。
- 模型可以立即进行专业化资源搜索。
- 搜索序列经过学习和训练。
- 步骤和过程作为内部推理轨迹记录。

### 结论：民主化与未来展望

当前只有大实验室能够开发实际LLM代理，它们拥有所有筹码：知识、数据以及将模型转化为产品的总体愿景。然而，这种技术集中并不是一种理想状态。鉴于其巨大的颠覆和价值捕获潜力，我相信民主化训练和部署实际LLM代理变得至关重要。

2025年是否会成为代理之年？我们拭目以待。
