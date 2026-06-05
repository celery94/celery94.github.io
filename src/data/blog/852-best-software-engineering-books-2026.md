---
pubDatetime: 2026-06-05T08:15:00+08:00
title: "2026 软件工程书单：按你当下的问题来选书"
description: "Dr. Milan Milanović 整理了一份按问题域归类的软件工程书单，涵盖编码思维、架构、分布式系统、AI 工程和职业发展等 8 个方向共 18 本书。不按热门程度排列，而是按「你此刻卡在哪」来组织。"
tags: ["Software Engineering", "Books", "Career", "Architecture", "AI"]
slug: "best-software-engineering-books-2026"
ogImage: "../../assets/852/01-cover.png"
source: "https://newsletter.techworld-with-milan.com/p/best-software-engineering-books-2026"
---

Dr. Milan Milanović 在 2024 年分享过一份"不会变的基础知识"清单，两年后他做了精简迭代——去掉了泛泛的推荐，只保留他自己反复用过、私下推给同事、并且依然会继续推荐的书。这份 2026 版书单的核心逻辑不是"你应该读哪些书"，而是"**你此刻卡在哪个问题上，就读对应的书**"。

他把 18 本书拆进 8 个问题域，每本都带了简短但具体的判断。下面按他的分组来走一遍。

## 代码思维

这一组的书讲的是工程师怎么看待代码这件事——不局限于语法，而是关于心智模型和职业判断。

### The Pragmatic Programmer（David Thomas & Andrew Hunt）

推荐理由二十年来没变过：这不是一本教你怎么写代码的书，而是一本教你**怎么成为一个更专业的工程师**的书。它覆盖了责任意识、消除重复、为变更设计、保持技术敏感度等话题。20 周年纪念版已经更新了内容。

Milanović 说他在做 coaching 时，每当有人问"怎么在工作中变得更专业"，他推荐的就是这本。

### Clean Code（Robert C. Martin）

这本书的名气不用多说。Milanović 给了它一个坦率的评价：有些规则已经过时了，比如强制把函数拆得很小会导致大量碎片化的调用；但**命名、测试、代码结构**这些核心概念今天依然成立。他建议把这本书和下一本搭配着读。

### A Philosophy of Software Design（John Ousterhout）

Milanović 称这是他"希望更早读到"的一本书。Clean Code 侧重告诉你做什么，这本书则解释**复杂性是怎么累积起来的，以及如何用抽象和信息隐藏来对抗它**。

书中两个核心观点他花了很久才消化：类应该"深"（deep classes），接口应该简单；以及"设计两遍"（design it twice）到底意味着什么。这本书也有争议——它赞成代码注释、认为 TDD 有害——但 Milanović 说他反复重读的就是这本。如果你在维护大型代码库或正在往 senior 方向走，这是他最强调的一本。

## 工程法则

### Laws of Software Engineering（Dr. Milan Milanović）

这是他本人花了两年写成的书，2026 年 4 月刚发布。定位很明确：填补其他书不碰的那块空白——**软件工程中的实证法则和原理**。

书中整理了 63 条以上法则，横跨架构与复杂性、人与团队、时间与规划、质量与维护、规模与性能、编码与设计、决策与偏见七个领域。每条法则都讲清楚它说什么、从哪来、什么时候适用、在真实项目里长什么样。

这些知识大部分工程师会在职业生涯中通过犯错、事后复盘、同事口口相传来慢慢学到——这本书把它们系统化了。序言由 Thoughtworks CTO Emerita Dr. Rebecca Parsons 和 Google Cloud AI 工程总监 Addy Osmani 撰写。

## 架构

他认为每个 senior 工程师或架构师都应该读这一组。

### Fundamentals of Software Architecture（Mark Richards & Neil Ford）

如果你想系统学习软件架构，Milanović 推荐这本作为第一本。内容包括架构风格、权衡分析、fitness functions、以及怎样记录对未来有用的架构决策。他说在读这本书之前，架构对他来说比实际上更抽象。

两位作者后来又出了《Head First Software Architecture》，对初学者更友好。

### Software Architecture: The Hard Parts（Neal Ford 等）

这本是进阶版。基础那本给你框架，这本带你走进复杂性：**怎么拆单体、每种模式在什么情况下有用、怎么在模式之间做权衡**。Milanović 说他是在做复杂项目时读的这本。

### Domain-Driven Design Quickly（Abel Avram & Floyd Marinescu）

作为 DDD 的入门读物，他建议在读 Eric Evans 那本 500 页原版之前先看这本。写法清晰，带一个完整的实例，也介绍了六边形架构。

## 系统与数据

### Designing Data-Intensive Applications 第 2 版（Martin Kleppmann & Chris Riccomini）

DDIA 可能是软件工程领域被引用最多的一本书。第二版 2026 年 3 月以电子书和纸质版同步发行，新增了 AI 数据系统和新的分布式系统模式的内容。将近 700 页，Milanović 承认不容易全部理解，但作为 senior 工程师，工作中会遇到书里大部分问题。

### Understanding Distributed Systems（Roberto Vitillo）

如果你需要一本比 DDIA 更容易上手的分布式系统入门书，Milanović 推荐这本。它覆盖了通信、API、协调、事务、可扩展性、弹性等主要话题，特点是**对任何阶段的读者都可理解**。他说这是他在假期里愉快读完的一本书。

## AI 工程

这是 2026 版书单新增的板块，聚焦在有 LLM 参与的系统如何设计得可靠、可维护。

### The Hundred-Page Language Models Book（Andriy Burkov）

如果你想真正理解 LLM 是怎么工作的，Milanović 推荐这本。Burkov 从 ML 基础一路讲到 RNN 再到 Transformer，每一步都配 Python 代码和 Jupyter Notebook。序言由 word embedding 的原始创造者之一 Tomáš Mikolov 撰写。可在 thelmbook.com 免费阅读。

### AI Engineering（Chip Huyen）

Burkov 的书偏理论，Huyen 这本则进入生产现实：模型选择、评估、MLOps、多智能体系统、扩展。Milanović 认为这可能是目前**构建 AI 应用的最佳指南**。

## 测试

### The Art of Unit Testing（Roy Osherove）

虽然这个类别可以推好几本，Milanović 这次只保留了一本。这本书详细讲了怎么写单元测试、怎么划定测试范围、测什么。第三版覆盖了现代语言和工具链。它不只能帮你抓 bug，更能帮你**安全地重构代码**。

## 实践与交付

### Accelerate（Nicole Forsgren, Jez Humble & Gene Kim）

基于研究写成的书，探讨了什么让高效能技术组织与众不同。作者识别出四个指标：部署频率、前置时间、变更失败率、平均恢复时间——也就是 DORA 指标。Milanović 的建议很直接：在任何关于生产力的讨论之前，先把这本书读了。

### Refactoring（Martin Fowler）

是的，就是那本《重构》。Milanović 指出一个容易被忽略的事实：我们更多时候是在**改现有系统**，而不是从零构建新系统。重构就是在不改变外部行为的前提下改善内部结构。第二版用 JavaScript 替代了第一版的 Java。

## 职业发展

### The Software Engineer's Guidebook（Gergely Orosz）

很少有人专门为软件工程师的职业路径写一本书。Gergely 做了这件事。这本书覆盖了从 junior 到 staff 的成长路径、绩效评估、以及如何成为一个更有效的 IC。目前是 Amazon #1 畅销书，已翻译成 6 种语言。

Orosz 同时也是 The Pragmatic Engineer newsletter 的作者，Milanović 称其为"业内最好的 newsletter"。

### Deep Work（Cal Newport）

这不是一本软件书，但 Milanović 认为它对职业生涯帮助很大。核心观点：**长时间高度聚焦于困难问题的能力是稀缺且有价值的**。这种能力是区分优秀工程师和普通工程师的关键。书中给出了具体的提升策略。

## 从哪开始

文末有一张决策图，核心思路是：选匹配你当下困境的那本，而不是按榜单顺序读。

Milanović 的原话是："Pick the book that matches where you're stuck right now."

具体对应关系：

| 你的困境             | 推荐起点                                |
| -------------------- | --------------------------------------- |
| 不知道怎么把代码写好 | _A Philosophy of Software Design_       |
| 想变得更专业         | _The Pragmatic Programmer_              |
| 需要理解架构决策     | _Fundamentals of Software Architecture_ |
| 在处理分布式系统     | _Understanding Distributed Systems_     |
| 要做 AI 功能或产品   | _AI Engineering_                        |
| 团队交付质量不稳定   | _Accelerate_                            |
| 在改遗留代码         | _Refactoring_                           |
| 想规划职业成长       | _The Software Engineer's Guidebook_     |

这份书单的价值不在于它列了哪些书，而在于每一本都带着一个**具体的适用信号**：你遇到什么问题时，这本书恰好能帮上忙。

## 参考

- [原文：The Software Engineering Books I keep recommending](https://newsletter.techworld-with-milan.com/p/best-software-engineering-books-2026)
- [Milanović 2024 年文章：Learn things that don't change](https://newsletter.techworld-with-milan.com/p/learn-things-that-dont-change)
- [Laws of Software Engineering 官网](https://lawsofsoftwareengineering.com/book/)
- [The Hundred-Page Language Models Book](https://thelmbook.com/)
- [The Software Engineer's Guidebook](https://www.engguidebook.com/)
