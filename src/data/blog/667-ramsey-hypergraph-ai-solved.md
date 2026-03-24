---
pubDatetime: 2026-03-24T15:17:00+08:00
title: "AI 解开顶级数学竞赛难题：超图 Ramsey 问题被 GPT-5.4 Pro 攻克"
description: "FrontierMath 中的超图 Ramsey 型问题长期被认为需要专家 1-3 个月才能解决，近日由 GPT-5.4 Pro 首次给出正确构造方案，随后 Claude Opus 4.6、Gemini 3.1 Pro 等多个模型也相继完成了求解。本文解析这道题的数学背景、难点所在，以及 AI 解法的意义。"
tags: ["AI", "数学", "FrontierMath", "组合数学", "GPT-5"]
slug: "ramsey-hypergraph-ai-solved"
ogImage: "../../assets/667/01-cover.webp"
source: "https://epoch.ai/frontiermath/open-problems/ramsey-hypergraphs"
---

FrontierMath 是 Epoch AI 构建的一套专门用于评估 AI 数学能力的难题集，其中有一类题被称为 Open Problems——题目正式、考查真实研究能力、答案不存在于现有文献中。超图 Ramsey 型问题（A Ramsey-style Problem on Hypergraphs）就是其中一道，由北卡罗来纳大学夏洛特分校副教授 Will Brian 提供。

这道题被评为"中等有趣"，数学界有约 10 名研究者对它高度熟悉，5-10 人曾认真尝试过求解，估计一位专家需要 1-3 个月才能得出答案。上个月，GPT-5.4 Pro 在 Kevin Barreto 和 Liam Price 的引导下给出了完整构造，Will Brian 随后确认了解法的正确性。

## 这道题到底在问什么

先从定义说起。一个**超图（hypergraph）** $(V, \mathcal{H})$ 由顶点集 $V$ 和超边集 $\mathcal{H}$ 组成，每条超边可以包含任意数量的顶点（而不像普通图那样只能连两个点）。

题目引入了"划分"的概念：如果存在 $D \subseteq V$ 和 $\mathcal{P} \subseteq \mathcal{H}$，使得 $|D| = n$，且 $D$ 中每个顶点恰好属于 $\mathcal{P}$ 中的某一条超边，我们就说这个超图**包含大小为 $n$ 的划分**。

然后定义序列 $H(n)$：在所有没有孤立顶点、且不包含大小超过 $n$ 的划分的超图中，顶点数的最大值就是 $H(n)$。

直觉上，$H(n)$ 描述了"用最多 $n$ 个超边元素的一次划分里能覆盖多少顶点"的"反极限"——我们想让超图尽量大，但同时避免出现大的划分。这个序列与无穷级数的同时收敛性研究有密切联系。

**已知下界**由以下递推给出：

$$k_1 = 1, \quad k_n = \left\lfloor \frac{n}{2} \right\rfloor + k_{\lfloor n/2 \rfloor} + k_{\lfloor (n+1)/2 \rfloor}$$

研究者相信现有下界在渐近意义上仍不是最优的。题目的目标是找到新构造，将下界改进一个常数倍，即证明 $H(n) \geq c \cdot k_n$，其中 $c > 1$，且这一改进在 $n = 15$ 时已经生效。

## 题目的三个层次

FrontierMath 把这道题分成三个难度层次来测试 AI：

**热身题**：找一个无孤立顶点的超图，满足 $|V| \geq 64$，$|\mathcal{H}| \leq 20$，且不包含大小超过 20 的划分。这个构造已知，用于核查模型是否理解基本概念。

**单次挑战**：条件改成 $|V| \geq 66$，这个构造目前尚无文献记载，也几乎无法靠暴力搜索完成。

**完整问题**：给出一个对所有 $n$ 都适用的算法，接受 $n$ 作为输入，输出一个见证 $H(n) \geq c \cdot k_n$ 的超图字符串。要求对 $n \leq 100$ 在普通笔记本上 10 分钟内跑完。

这道完整题需要找到一个系统性的构造方案，不是凑出几个例子就够了。

## AI 的尝试历程

在 GPT-5.4 Pro 求解之前，多个强力模型都折戟了：

| 模型 | 挑战层次 | 结果 |
|------|----------|------|
| GPT-5.2 Pro | 热身题 | 未解出 |
| GPT-5.2 Pro | 单次挑战 | 未解出 |
| GPT-5.2 Pro | 完整问题 | 未解出 |
| Gemini 3 Deep Think | 完整问题 | 未解出 |
| **GPT-5.4 Pro** | **完整问题** | **✓ 已解出** |

GPT-5.4 Pro 是第一个完整解出这道题的模型，完整对话记录已公开。在这之后，Epoch AI 建立了更通用的测试框架，随后又有三个模型通过了完整问题：Claude Opus 4.6（max 推理）、Gemini 3.1 Pro，以及 GPT-5.4（xhigh）。

## Will Brian 的评价

题目贡献者 Will Brian 在确认解法后写道：

> "这是一个让我十分兴奋的解法，针对的是一道我本人很感兴趣的问题。我之前就想过 AI 这种思路是否可行，但感觉推导会很繁琐。现在我看到它确实行得通，而且非常漂亮。这个解法消除了我们下界构造中的一处低效，在某种程度上也呼应了我们上界构造的精细结构。下界和上界的吻合程度对于 Ramsey 类问题来说已经相当好了，我很想进一步弄明白为什么能配合得这么好。"

Brian 计划将这一解法整理成正式论文，并可能纳入 AI 解法带来的后续延伸工作。Barreto 和 Price 受邀作为论文的共同作者。

## 这件事的意义

这不是一道课本题，也不是有标准答案可以查到的题。它来自一个活跃的研究方向，专家也需要花好几个月才能搞定。GPT-5.4 Pro 能给出正确的构造，并且解法被专家评价为"消除了已有构造的低效""呼应了上界结构"，说明模型不只是在模拟已知路径，而是做出了真正有数学意义的推进。

当然，这还是在有经验的研究者引导下完成的——Barreto 和 Price 设计了对话流程，引导模型聚焦在正确的子问题上。但即便如此，原来需要几个月的工作被压缩到了一次会话中，这本身已经说明了很多。

Epoch AI 的这套 Open Problems 系列，正是为了寻找这样的边界：哪些问题 AI 已经能独立或协助解决，哪些还需要人来引路，哪些目前完全做不到。随着 GPT-5.2 连热身题都解不出、而 GPT-5.4 能完整求解，这条边界正在向前移动。

## 参考

- [原文页面](https://epoch.ai/frontiermath/open-problems/ramsey-hypergraphs)
- [完整解题 PDF（GPT-5.4 Pro）](https://epoch.ai/files/open-problems/hypergraph-ramsey-gpt-5-4-pro-solution.pdf)
- [GPT-5.4 Pro 对话记录](https://epoch.ai/files/open-problems/gpt-5-4-pro-hypergraph-ramsey.txt)
- [FrontierMath Open Problems](https://epoch.ai/frontiermath/open-problems)
