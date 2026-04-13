---
pubDatetime: 2026-04-13T11:32:59+08:00
title: "用 GPT-5.4 做前端开发，大多数人的姿势不对"
description: "GPT-5.4 在前端设计上确实有了显著提升，但大多数人还在用模糊的一句话提示，结果拿到的是通用布局、弱视觉层次和毫无个性的界面。这篇文章梳理了为什么会这样，以及从约束定义、视觉参考到 Frontend Skill 的具体改进方法。"
tags: ["GPT-5.4", "前端", "AI", "提示词工程", "UI 设计"]
slug: "gpt54-frontend-right-way"
ogImage: "../../assets/732/01-cover.jpg"
source: "https://x.com/JonsTechYT/status/2043324936853365125"
---

现在很多人都在用 AI 做前端，但多数成果都长得差不多——通用布局、没有个性、视觉层次模糊。OpenAI 的工程师在 GPT-5.4 发布时明确指出：这不是模型问题，是输入问题。当提示词不够明确，模型就会退回训练数据里最高频的模式，那些模式"可用但平庸"。

## 大多数人犯的错误

还在用"帮我做一个现代风格的仪表盘"这类提示。这给了模型太大的自由度，而模型会用那个自由度来填充最常见的 UI 模板：卡片组件堆叠、弱品牌标识、没有任何内容驱动的层次结构。

官方文档里说得很直白：**当提示词欠缺规格，模型就会倒向高频训练模式，产出功能可用但在设计感上远低于心理预期的结果。**

## 具体输入什么

要让 GPT-5.4 产出有设计质感的前端，提示词里至少要回答这几个问题：

- 这是什么产品，面向谁的
- 目标风格方向是什么（比如：极简暗色、Linear 风、品牌感强）
- 有哪些约束（移动端优先、无障碍对比度、字体限制）
- 需要处理哪些状态（加载中、空列表、错误提示）
- 内容是什么，不是 placeholder

把"帮我做一个面向自由职业者的财务 App"换成：自由职业者财务 App，极简暗色 UI，强排版，移动端优先，需要清晰的空状态/加载状态/错误状态，符合无障碍对比度要求，间距系统整洁。现在模型有真实的设计问题可以解决了。

## 别用一句话搞定所有事

好的前端不是一个 prompt 出来的。OpenAI 建议的工作流是：生成、检查、优化、再生成——把它当成和一个设计师合作，而不是操作一个生成器。

GPT-5.4 还新增了对 Playwright 的原生支持，可以在迭代过程中自己检查渲染效果、测试多个视口，甚至验证交互状态。这意味着你可以让它在改完之后自己跑一遍检查，而不只是依赖你的眼睛。

## 提前定义设计系统

官方文档里有一个具体建议：在开始构建之前，先让模型确立设计系统——颜色 token（`background`、`surface`、`accent`）、排版角色（`display`、`headline`、`body`、`caption`）。这个结构能让后续所有生成保持一致性，避免每次迭代都在零散地调整。

用 React + Tailwind 是目前 GPT-5.4 表现最好的组合，文档也明确推荐这个起点。

官方还有一段专门给固定元素和动效的约束建议，直接放进提示词有效：

```
Keep fixed or floating UI elements from overlapping text, buttons, or other 
key content across screen sizes. Place them in safe areas, behind primary 
content where appropriate, and maintain sufficient spacing.
```

## 提供视觉参考

附上截图或参考图，比光靠文字描述效果好一倍。模型会从图片里提取布局节奏、字号比例、间距系统、图像处理风格。如果你想要某种特定调性，可以先让模型生成几个情绪板（mood board）选项，确认后再开始构建，这样视觉方向从一开始就有锚点。

## 用 Frontend Skill 代替每次重复说明

这是多数人跳过的一步。OpenAI 在发布 GPT-5.4 时同步发布了一个 [`frontend-skill`](https://github.com/openai/skills/tree/main/skills/.curated/frontend-skill)，把设计原则、排版规范、构图规则和常见禁令打包成了可复用的上下文。

安装方式：

```bash
npx skills add https://github.com/anthropics/skills --skill frontend-design
```

不用它的代价是：每次对话都从零开始，同样的问题要修好几遍，输出风格每次都不一致。用了之后，模型有一套固定的设计判断框架，知道什么是"默认不用卡片"、什么是"首屏当海报来排版"、什么是"两种字体上限"。

Skill 里面有一条核心设计原则可以单独用：

```
Treat the first viewport as a poster, not a document.
```

首屏是海报，不是文档。这一条能排除掉大多数"看起来完整但设计感为零"的产出。

## 调低推理等级

这一点比较反直觉：对于简单页面，**不要用最高推理等级**。文档里明说了，低或中等推理等级在前端任务上往往给出更好的结果——模型更专注，不会过度分析，留给迭代的空间反而更大。复杂设计时再把推理调高。

## 给模型真实内容

用真实的文案和产品背景代替 placeholder。模型有了真内容，才能选择正确的页面结构、写出可信的章节标题、避免把营销页的每个区域都塞进一样的"功能特性"模式。

官方推荐的 landing page 基础叙事结构：

1. Hero：品牌/产品、承诺、CTA、一个主视觉
2. 支撑区：一个核心卖点或证明
3. 细节区：产品深度或使用场景
4. 结尾 CTA：转化

Hero 区有一条硬规则值得记住：如果去掉图片之后第一屏还能正常工作，说明这张图没有真正做事。

## 什么在变，什么没变

AI 没有在替代前端开发，它在替代的是重复性布局工作、低设计质量迭代和样板代码。真正的工作转移到了：给方向、定系统、判断输出。

GPT-5.4 确实在 UI 能力上有了提升——图像理解更强，能处理更复杂的交互，长任务下的连贯性更好。但这些提升只有在你给了足够好的输入时才能释放出来。模型的上限抬高了，瓶颈移到了提示词和工作流那一侧。

## 参考

- [Most People Are Using GPT-5.4 for Frontend Wrong — @JonsTechYT](https://x.com/JonsTechYT/status/2043324936853365125)
- [Designing Delightful Frontends with GPT-5.4 — OpenAI Developers](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4)
- [frontend-skill — OpenAI Skills Repository](https://github.com/openai/skills/tree/main/skills/.curated/frontend-skill)
