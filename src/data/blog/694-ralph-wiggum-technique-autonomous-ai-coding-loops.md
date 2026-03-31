---
pubDatetime: 2026-03-31T14:10:00+08:00
title: "Ralph Wiggum 技术：让 AI 编程代理自主运转数小时"
description: "Geoffrey Huntley 创建的 Ralph Wiggum 技术，通过定义完成状态让 AI 代理自主循环工作，已成为 Claude Code 官方插件。本文介绍其核心原理、适用场景与实际限制。"
tags: ["AI编程", "Claude Code", "自动化", "AI代理"]
slug: "ralph-wiggum-technique-autonomous-ai-coding-loops"
ogImage: "../../assets/694/01-cover.png"
source: "https://x.com/milan_milanovic/status/2038866383191044427"
---

大多数人使用 AI 编程代理的方式是：发一条 prompt，等结果，再发一条，再等结果，人始终在回路里。这个模式本身并没有问题，但它有一个隐性上限——每一步都需要人来审核和推进。

Ralph Wiggum 技术要解决的，就是这个瓶颈。

## 它是什么

Ralph Wiggum 技术由 Geoffrey Huntley 于 2025 年中期创建，以《辛普森一家》里那个习惯性向前倒下的角色命名。核心思路出奇地简单：

```bash
while :; do cat PROMPT.md | claude-code; done
```

把 AI 代理放进一个 Bash 循环，让它不断工作、失败、重试、迭代，直到满足"完成"条件。进度保存在 git 历史里，不在上下文窗口里。每一轮新循环从上一轮停下的地方继续。

目前，Ralph 已经是 Claude Code 的官方插件，Vercel Labs 也为 AI SDK 构建了自己的实现。

![推文图片](../../assets/694/tweet-image.jpg)

## 真实案例说明它能做什么

**数字层面**的一些参照点：

- 一场 Y Combinator 黑客松，团队一夜之间交付了 6 个代码仓库，API 费用总计 $297
- 一位开发者用 Ralph 完成了一份价值 $5 万的合同
- Huntley 本人跑了一个持续 3 个月的循环，从零构建了一门完整的编程语言 CURSED，包含编译器、LLVM 后端和标准库

**操作层面**同样有具体例子：将数百个文件从 Jest 迁移到 Vitest、在 14 小时无人值守的情况下把 React v16 升级到 v19、趁睡觉时批量补全整个目录的测试覆盖率。

## 关键原则

**每轮循环只做一件事。** 这一点 Huntley 在原文里反复强调。原因在于上下文窗口有限（约 170k），放进去的东西越多，输出质量越差。单一任务让代理专注推理，而不是在五个不同问题之间来回切换。

**"完成"必须可被验证。** Ralph 最适合那些能用测试套件或构建步骤判断是否完成的任务。模糊的"感觉对了"不够用，需要有明确的回压机制——可以是类型检查、静态分析、单元测试，只要能快速转动这个轮子即可。

**进度在 git 里，不在上下文窗口里。** 每轮循环结束前提交代码，下一轮循环从 git 历史拿到上下文。这个设计让循环可以无限延续，哪怕中途崩溃也能恢复。

**子代理负责繁重的分配工作。** 主上下文窗口作为调度器，把搜索文件系统、汇总测试结果这类"分配密集"的操作交给子代理处理，主循环把上下文留给推理。

## 需要注意的限制

**Token 费用是真实的成本。** 在大型代码库上跑 50 轮循环，API 费用可能达到 $50 到 $100+。使用前要给迭代次数设上限。

**非确定性是 Ralph 的阿喀琉斯之踵。** LLM 运行 ripgrep 后可能错误地判断某段代码尚未实现，从而重复实现。解决办法是在 prompt 里明确写一条"指示牌"：在修改之前先用子代理搜索代码库，不要假设某功能没有被实现。

**醒来可能面对一个不能编译的代码库。** 这不是偶发情况，而是常态之一。这时需要判断：是 `git reset --hard` 重来，还是用新的 prompt 序列把 Ralph 拉回正轨。

**工程师的判断仍然不可替代。** 模糊的需求、架构决策、安全敏感的代码——这些依然需要人来处理。Ralph 自动化的是机械性工作，不是背后的判断。

## 适用边界

Huntley 自己的结论很直接：

> 不管怎样，我绝对不会在现有的代码库里用 Ralph。

作为 Greenfield 项目的引导技术，它能帮你跑完大约 90% 的进度。在有良好测试覆盖的重复性任务上效果最好，在模糊的、需要频繁产品判断的场景下表现欠佳。

我们正在经历的转变是：从逐步指挥代理，到编写能让软件自主收敛到可工作状态的 prompt。这是一种不同的技能，但值得培养。

## 参考

- [原推文 - Dr Milan Milanović](https://x.com/milan_milanovic/status/2038866383191044427)
- [Ralph Wiggum as a "software engineer" - Geoffrey Huntley](https://ghuntley.com/ralph)
- [Y Combinator 黑客松实际案例报告](https://github.com/repomirrorhq/repomirror/blob/main/repomirror.md)
