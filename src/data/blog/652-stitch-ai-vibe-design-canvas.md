---
pubDatetime: 2026-03-19T13:00:00+08:00
title: "Google Stitch：用自然语言「氛围设计」UI 的 AI 原生画布"
description: "Google Labs 将 Stitch 升级为 AI 原生软件设计画布，引入无限画布、设计 Agent、DESIGN.md 设计系统、交互原型、语音设计和 MCP 集成，让任何人都能从自然语言直达高保真 UI 设计。"
tags: ["AI", "Design", "Google Labs", "UI/UX", "Vibe Design", "MCP"]
slug: "stitch-ai-vibe-design-canvas"
source: "https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-ai-ui-design/"
---

Google Labs 在 2026 年 3 月 18 日宣布 [Stitch](https://stitch.withgoogle.com/) 的重大升级——从一个设计辅助工具，演变为一个 **AI 原生软件设计画布**。任何人都可以用自然语言，直接生成、迭代和协作高保真 UI 设计。

Google Labs VP Josh Woodward 用了一个词来描述这种工作方式：**vibe design（氛围设计）**。类比 vibe coding，你不必从线框图开始，而是描述业务目标、期望用户感受，或者贴一张正在激励你的参考图，AI 帮你把这些模糊想法快速变成具体的 UI 方案。

---

## 新无限画布

Stitch 的界面完全重做，核心是一块 **AI 原生的无限画布**，可以把文字、图片、代码直接拖进来作为上下文。设计过程天然是发散再收敛的——你会走好几条路，最后才落定。无限画布给了这个过程足够的空间，而不是把所有想法挤进同一个文件。

---

## 设计 Agent 与 Agent Manager

新版 Stitch 随画布配套了一个新的**设计 Agent**，能在整个项目演化过程中跨阶段推理。除了单线程设计，还有新的 **Agent Manager**：

- 跟踪整个项目的进度
- 支持同时在多个方向上并行探索
- 保持工作区的组织结构清晰

对于需要快速验证多种设计方向的场景，这个功能会大幅压缩决策周期。

---

## DESIGN.md：可移植的设计系统

Stitch 引入了 **DESIGN.md**——一个对 Agent 友好的 Markdown 文件，用来承载设计规则和设计系统。

- **导入**：可以从任意 URL 提取设计系统
- **导出**：把当前项目的设计规则导出为 DESIGN.md
- **跨工具**：在不同 Stitch 项目之间复用，也可以导入 VS Code、AI Studio 等开发工具

这意味着你不必每次从零搭建设计系统。品牌色、字体规范、组件规则，写进 DESIGN.md，拿来即用。

---

## 静态稿变可交互原型

设计完静态页面后，Stitch 可以一键把它转成**可交互原型**：

1. 把多个页面「Stitch」在一起，定义跳转关系
2. 点击 **Play** 直接预览完整的应用交互流程
3. Stitch 会根据点击逻辑**自动推断并生成下一个页面**，把用户路径补全

这个反馈循环极短——改一个按钮样式或者重构整个流程，都能在几秒内看到效果。

---

## 用声音设计

Stitch 支持**语音输入**，你可以直接对画布说话：

- 实时设计评审：「这个导航栏的层级结构是不是有问题？」
- 语音采访式设计：Agent 会问你问题，帮你把想法转成页面
- 即时修改：「给我三个不同的菜单选项」「把这个页面换成深色配色」

AI 在这里扮演的角色类似设计搭档——它质疑你的想法、帮你发现新方向，同时保持你在创作心流中。

---

## 连接开发工具链：MCP、SDK 与导出

设计完成后，Stitch 可以作为整个团队工作流的桥梁：

- **[MCP Server](https://stitch.withgoogle.com/docs/mcp/setup/)**：任何支持 MCP 的 AI 工具都能调用 Stitch 的能力
- **[SDK](https://github.com/google-labs-code/stitch-sdk)**：程序化接入 Stitch
- **[Skills](https://github.com/google-labs-code/stitch-skills)**（2.4k stars）：可复用的 Agent 技能模块
- **导出到开发工具**：支持导出到 AI Studio、Antigravity 等，设计师和开发者的上下文保持同步

---

## 适合谁用

- **专业设计师**：需要快速探索几十个方向，而不是在一条路上深挖
- **创业者 / PM**：脑子里有想法，但没有设计背景，想直接把 idea 变成可以给开发者看的高保真稿
- **全栈开发者**：设计完之后直接导出代码可用的资产，不用在工具之间反复切换

Stitch 目前可在 [stitch.withgoogle.com](https://stitch.withgoogle.com/) 免费试用。
