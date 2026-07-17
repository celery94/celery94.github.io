---
pubDatetime: 2026-07-17T08:11:31+08:00
title: "Kimi K3 与鹈鹕测试：跑一次 Prompt 比看 Benchmark 表格更有用"
description: '月之暗面发布 Kimi K3，2.8T 参数，$3/$15 定价，7 月底开源。Simon Willison 用他 21 个月的鹈鹕骑自行车 benchmark 做了测试，发现模型花 13241 个推理 token 生成一只鹈鹕，以及一个隐藏的 85 token system prompt。这篇分析聊聊 K3 的实际表现，和一个"玩笑 benchmark"为什么至今还能告诉我们真实的事。'
tags: ["Kimi", "Moonshot", "LLM", "benchmark", "AI"]
slug: "kimi-k3-pelican-benchmark"
ogImage: "../../assets/950/01-cover.jpg"
source: "https://simonwillison.net/2026/Jul/16/kimi-k3/"
---

月之暗面（Moonshot AI）今天发布了 Kimi K3——一个 2.8T 参数的新模型，自称"首个开源 3T 级模型"。它比 DeepSeek V4 Pro 的 1.6T 大了一截，定价也跟上了 Claude Sonnet 的档位：$3/百万输入 token，$15/百万输出 token，是目前中国 AI 实验室发布的最贵模型。

Simon Willison 第一时间跑了他那个著名的测试——让模型生成一只骑自行车的鹈鹕 SVG。这个测试已经 21 个月了，最初是个玩笑，后来意外地跟模型质量有不错的正相关，再后来这种相关性断裂了。但 Simon 说，他仍然从中得到了不少价值。

## K3 的规格和定价

先说硬数据。K3 基于 Kimi Delta Attention（KDA）和 Attention Residuals（AttnRes）两个新架构组件构建，MoE 结构激活 896 个专家中的 16 个，配合 Stable LatentMoE 框架。支持原生视觉能力和 100 万 token 上下文窗口，模型权重承诺在 7 月 27 日前开源。

定价是个值得注意的信号。K3 的 $3/$15 定价比 K2.6（$0.95/$4）翻了 3 到 4 倍，直接对位 Anthropic 的 Claude Sonnet 级别。这在过去中国 AI 模型的定价策略里是不常见的——通常会有明显的价格优势。

Simon 引用了 Artificial Analysis 的几个数据：

- 在私有的长周期知识工作评估中，K3 的 Elo 达到 1547，相比 K2.6 提升了 732 分，仅次于 Claude Fable 5
- 单任务成本 $0.94，接近 GPT-5.6 Sol 的 $1.04，约为 Claude Opus 4.8（$1.80）的一半
- 输出 token 用量比 K2.6 减少了 21%

在 Arena.ai 的前端代码竞技场中，K3 排到了第一，超过了 Claude Fable 5。

## 一只鹈鹕，25 美分

Simon 通过 OpenRouter 调用 K3，用他的 LLM CLI 工具跑了这条 prompt：

```
llm -m openrouter/moonshotai/kimi-k3 'Generate an SVG of a pelican riding a bicycle'
```

结果生成了这样一只鹈鹕：

![Kimi K3 生成的鹈鹕骑自行车 SVG](../../assets/950/02-kimi-k3-pelican.jpg)

这个简单的请求花了 95 个输入 token 和 16658 个输出 token，其中 13241 个是推理 token，只有 3417 个是实际输出。总花费 25 美分。

然后 Simon 用这只鹈鹕图片测了 K3 的视觉能力——让它写 alt text。结果是 822 输入 token + 243 输出 token，花了 0.6 美分，描述非常准确：

> 卡通风格，一只白鹈鹕戴着红围巾，骑着红色自行车，走在有白色虚线的灰色路面上；大橙色喙和蹼状橙色脚在蹬车，身后有白色运动线；背景是浅蓝色天空、白云、黄色太阳、两只小黑鸟和带小白花的绿草地。

## 鹈鹕暴露了什么

几条有趣的观察：

**1. 只有一个推理档位——"max"。** K3 目前只能全速思考，没有办法调低 effort。这就是为什么生成一只鹈鹕要烧掉 13241 个推理 token。

**2. 隐藏 system prompt 疑似存在。** "Generate an SVG of a pelican riding a bicycle" 这句话在 OpenAI tokenizer 里数出来 10 个 token，在 Anthropic 的 tokenizer 里也是 10-30 个不等。但 K3 报告了 95 个输入 token。有人测试发了一个 "hi"，K3 报告了 86 个 token。这暗示模型可能在用户看不到的地方挂了一个大约 85 token 的系统提示词，而且它拒绝泄露。

**3. 视觉能力不错。** alt text 的生成质量很好，细节丰富且准确，说明原生多模态能力可用。

## 鹈鹕 benchmark 还能告诉我们什么

Simon 在他的文章中花了不少篇幅反思这个 benchmark 的意义。他的核心判断是：**别再拿鹈鹕来比较模型了。** GPT-5.6 和 Claude Fable 5 的鹈鹕质量已经被 GLM-5.2 超越，而他并不认为 GLM 是 Fable 级别的模型。

但他说他仍然从跑这个测试中获得相当多的价值：

1. **它是一个强制函数。** 如果你看到他晒了鹈鹕，说明他真的手动跑了这个模型。不管是走官方 API、OpenRouter 还是自己本地跑 llama.cpp，总之他亲自测过了。

2. **一个简单任务能暴露模型特征。** 比如 K3 这次就直接让人看到了：推理 token 的巨大开销、可能的隐藏 system prompt、以及仅支持 max effort 的状态。

3. **同一模型族内部的对比仍然有用。** K3 的鹈鹕相比 K2.5 有明显提升，这种跨代对比能直观感受模型进步。

4. **验证基础能力。** 能输出有效 SVG、有基本的几何和空间感知——这对能在本地跑的小模型是更重要的信号。

5. **它是一种传统。** Simon 说，每次 Hacker News 上他发文章发晚了，就会有人评论问"鹈鹕呢？"

他还提到，最近他特别受益于用同一句 prompt 在不同 effort level 下跑同一个模型——比如 GPT-5.6 家族的 [多个 effort 的鹈鹕矩阵](https://static.simonwillison.net/static/2026/gpt-5.6-pelicans.html)。但 K3 目前做不到这一点，因为只有一个 effort 档位。

鹈鹕最大的局限，Simon 也直说了：**它完全碰不到当今模型最核心的能力——agentic tool calling，以及在长对话中可靠操作工具的能力。**

## K3 在做什么

从月之暗面官方博客看，K3 的定位远不止对话模型。它被深度集成到了 Kimi 产品线里——Kimi.com、Kimi Work、Kimi Code——目标是成为长期编程任务、知识工作和推理上的 agentic 工具。

几个值得关注的能力：

- **长周期编程**：能在最少人工干预下持续编程，浏览大型仓库，编排终端工具
- **视觉驱动开发**：能结合截图迭代优化游戏开发、前端和 CAD
- **GPU 内核优化**：在 24 小时自主运行中，K3 对四种 GPU kernel 任务做了 profiling 和重写，性能接近 Fable 5
- **编译器开发**：从零构建了 MiniTriton——一个类 Triton 的编译器，有自己的 tile 级 IR 层、优化 pass 和 PTX 代码生成管线
- **芯片设计**：48 小时自主运行，使用开源 EDA 工具在 Nangate 45nm 工艺上完成了一颗芯片的设计

当然，这些案例来自官方博客的描述，需要在模型开源后才能独立验证。官方也坦承了 K3 的几个限制：对思考历史敏感、倾向于过度主动执行用户意图、用户体验上跟 Fable 5 和 GPT-5.6 Sol 仍有差距。

## 自己跑一次

Simon 这篇文章最打动我的一点是他说：**跑一次模型比看 benchmark 表格更重要。**

Benchmark 表格告诉你一个模型能做什么，但自己跑一次告诉你这个模型是怎么做的——它的 token 开销、推理深度、价格压力、奇怪的边缘行为。这些"非正式测试"无法放入任何 benchmark 排行榜，但它们往往决定了你是否真的想把这个模型放进自己的工作流里。

K3 的参数亮眼，benchmark 能打，定价大胆。但一只 25 美分的鹈鹕就暴露了隐藏 system prompt、单一的 max effort、和高昂的推理 token 开销。这些信息不会出现在月之暗面的发布博客里，但会决定你是否愿意为它买单。

7 月 27 日开源后，更多的人会用自己的方式测试它——不管是跑鹈鹕、写代码、还是部署 agent。那才是 K3 真正的考试。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Kimi K3, and what we can still learn from the pelican benchmark - Simon Willison](https://simonwillison.net/2026/Jul/16/kimi-k3/)
- [Kimi K3 官方博客 - Moonshot AI](https://www.kimi.com/blog/kimi-k3)
- [Kimi K3 的鹈鹕输出（Gist）](https://gist.github.com/simonw/66a2699eb1594258904c7b5102840dd6)
- [GPT-5.6 Pelican Matrix](https://static.simonwillison.net/static/2026/gpt-5.6-pelicans.html)
- [Six months in LLMs - Simon Willison](https://simonwillison.net/2025/Jun/6/six-months-in-llms/)
