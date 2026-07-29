---
pubDatetime: 2026-07-29T12:03:40+08:00
title: "GitHub Copilot 实战工作流：驾驭 harness，而不是追新工具"
description: "每天都有新的 AI 工具、MCP 和工作流冒出来，但真正提升效率的关键不是追新，而是驾驭好你手里的 agent harness。本文分享一套经过验证的 GitHub Copilot 八步工作流，覆盖原型探索、系统规划、自动实现到交叉审查的完整链路，让你摆脱工具焦虑，回归可重复的高质量产出。"
tags: ["GitHub Copilot", "AI Coding", "Workflow", "Developer Tools"]
slug: "github-copilot-harness-workflow"
ogImage: "../../assets/979/01-cover.png"
source: "https://x.com/github/status/2082201573976056245"
---

如果你最近也被 AI 工具刷屏刷到焦虑，你不是一个人。

每天都有新工具、新 MCP、新模型、新技能、新工作流冒出来。社交平台上到处都是「我用这个神奇 prompt 彻底搞定了 AI 编程」之类的帖子。Burke Holland —— GitHub 的开发者关系工程师 —— 说他每天跟 AI 打交道，看到这些只想说一句：我不信。

他真正的体会是：**越少，反而越多**。真正让他生产力飙升的，不是装了多少插件、配了多少 MCP、玩了什么 trick，而是他**如何驾驭 harness（代理框架）本身**。

在这篇发布在 GitHub 官方 X 账号的长文中，Burke 分享了一套简单但完整的 GitHub Copilot 工作流。不依赖奇怪 prompt，不需要什么高深技能，只用 Copilot 已有的功能，就能大幅提升 AI 辅助开发的效率。

这篇文章的类型是 **教程/实操**，我会按照原文的八步结构来展开。读完你会带走一套可以立刻上手的、可重复的 AI 编码流程。

## 免责声明（原文就有，我也得说）

Burke 在文中特意强调了几点，我觉得很重要，先列出来：

- 他用「harness」和「GitHub Copilot」交替使用。Copilot 本质上就是一个 agent harness —— 一套代理框架
- 他不是说你永远不需要 skills、MCP、自定义指令或自定义 agent。事实上，他在文章里也用了几个。他的核心观点是：**你不需要这些东西也能高效地用好 AI**
- 市面上的「AI 垃圾」（slop）很多。随便让 agent 生成一个 skill，它都会高高兴兴给你吐出来，不管这 skill 能不能用。而这些东西很容易被发布到各种 registry 里

理解这些前提之后，我们进入正题。

## 1. 选一个工具，随便哪个都行

GitHub Copilot 家族里选项其实不少：CLI、新的 GitHub Copilot 桌面应用、VS Code、Visual Studio、JetBrains……这还只是部分。

好消息是，这些体验正在逐渐汇聚到同一套 harness 上。不同工具的具体细节可能有差异，但**核心工作流是一致的**。学会驾驭 harness 一次，到处都能用。

Burke 的建议是：如果你刚刚起步，从 **GitHub Copilot CLI** 开始。终端界面就是纯文本，没什么 UI 要学，输入 prompt，agent 就开始做事。交互更直接、更即时，而且说实话，很爽。

> 本文演示中他使用的是新的 GitHub Copilot 桌面应用，但这套 harness 在 CLI、VS Code 等所有地方都是一样的。

## 2. 开启 YOLO 模式

YOLO 模式也叫「Allow All」—— 让 agent 执行任何命令而不用每次都征得你同意。具体操作通常是聊天框里一个 `/allow-all` 命令。

不开的话，agent 每做一件事都会停下来等你批准。Burke 的观点很直接：

> Agent 需要**自主性**，你才能看到生产力的提升。如果每件事都要批准，不如自己动手。况且那种体验太痛苦了 —— 没人想整天坐在桌前按「批准」按钮。反复按「批准」只会训练你不去阅读被批准的内容，这完全违背了审批的初衷。

但安全怎么办？YOLO 模式下不建议在本地机器上直接跑 agent，尤其在工作环境里 —— 组织系统的数据是私有的，错误可能代价高昂。

好在有很多沙箱选项。最容易上手的是 **GitHub Codespaces** 或 **Development Containers**（dev containers）。在沙箱里跑 agent，安全又有保障。

## 3. 从原型开始

AI 最神奇的能力之一，就是可以**零成本快速原型任何东西**。历史上原型是一个完整的项目阶段，经常是奢侈品。现在一个 prompt 就能搞定。

Burke 举了 date picker（日期选择器）这个例子。看起来简单，实际上很复杂。想想你要处理的交互：

- 组件内部如何导航？
- 选中的日期长什么样？
- 选中一个范围长什么样？
- 用户如何在天、月、年之间切换？

他的做法是：先让 AI 生成 20 个原型变体，放在一个 HTML 文件里对比。

> Give me 20 mocks for a date picker web component. Put them all in an HTML file so I can compare.

AI 一次性生成了各种不同布局的原型。其中一个 mock 从年份视图开始，这让他想到：自己的 date picker 应该支持用户先缩放到年份，再进入月份，最后才是具体日期。**这些细节你不看到方案是不会意识到的。**

不限于视觉任务。比如要加一个新的 API 端点，他也会让 AI 先生成可视化的方案对比：

> Create a visual mockup of the API for this project. Add five options for how we could handle a new API endpoint that allows the user to download their analytics data.

GitHub Copilot 桌面应用支持 Mermaid 图表，agent 会用 Markdown 渲染出五种不同的 API 设计方案，一目了然。

核心逻辑是：**一切都有细节，原型让你提前发现这些细节**，避免花大量时间和 token 在返工上。

他还推荐：日常工作用中等规模模型（如 GPT 5.6 Terra 或 Claude Sonnet），中等推理水平就够了。**在同一特性、bug 或改进上，尽量不切换模型和推理水平**，因为 prompt 缓存会持续生效 —— 只要你不变模型或推理水平，之前的聊天会被缓存，后续请求享受折扣。

## 4. 系统性地规划

搞清楚自己真正想要什么之后（通常跟你一开始以为的不一样），就该规划实现了。

在 GitHub Copilot 中切换到 plan 模式，不用开新会话：

> /plan Build a date picker web component. I want the user to be able to zoom in and out of years, months, and days.

这个 prompt 其实很模糊，但没关系，这正是这个步骤的意义所在。

理论上，只要写出完美的 prompt 加上完美的上下文和完美的顺序，模型可以一次搞定。**理论上。**

实际上没人能做到。规划模式的厉害之处在于：它会替你把那些你自己手写代码时必须逐一回答的问题问出来：

- 起始日期和结束日期能不能是同一天？
- 部分选择是否有效？
- 用户能不能清除日期？
- 「今天」是否始终可见？
- 是否允许手动输入？
- 日期以什么格式存储？
- 是否允许粘贴日期？

这个列表可以一直延伸下去。你不可能想全这些边界条件，**但模型能帮你挖出很多你没想到的**。

想让 plan 模式更凶猛？安装 Matt Pocock 的 **grill-me** skill：

> /plan /grill-me Build a date picker web component. I want the user to be able to zoom in and out of years, months, and days.

规划这一步最关键的不是全盘接受 AI 的建议 —— 那样就丧失规划的价值了。**关键是深度参与问题，引导模型。**这就是你的专业判断上场的时候。

你还可以反过来问模型。Burke 在截图里被问到「non-contiguous dates」是什么意思，他虽然大概知道，但还是让模型解释清楚，确保双方理解一致。**规划过程即使被你打断追问，也会继续进行。**

## 5. 用 Autopilot 自动实现

规划完成后，GitHub Copilot 通常会提示你切换到 **Autopilot** 模式并开始实现。

Autopilot 是一个内置的循环机制。它会**强制模型持续工作**，确保模型真的完成了计划中的每一项 —— 而不是说「我做好了」但实际上漏了一堆东西。

在这个阶段，GitHub Copilot 会自动充当**编排器**：

- 需要读取代码库文件时，用「Explore」子 agent（小模型）
- 遇到相对复杂的操作时，用「General Purpose」子 agent（大模型）

当然你可以通过自定义 agent 和指令来精细控制编排，但**即使你对这些东西一无所知，子 agent 和多模型工作流的好处也是开箱即用的**。

## 6. 人工审查与迭代

这是让人最有成就感的一步。你可以看到 AI 创造了什么。

但大概率你不会一次得到完全想要的结果。这很正常，也是预期之中的。模型不能读心，而且容易出错。**持续迭代直到你真正满意。**不管是纯代码还是 UI 改进，这一步**你的品味决定了最终成品的质量**。

Burke 拿到的 date picker 初版就有不少问题：

- 动画不一致
- 鼠标悬停在已选日期上时文字因为颜色对比度不够读不清
- 不需要在顶部显示「12 YEARS」
- 点击「Today」不会在月视图或年视图里跳转到具体日期

而且他不喜欢设计本身 —— **看起来太像 AI 做的了**（因为确实就是 AI 做的）。

于是他切换到跟进模式，用自己创建的 CSS 框架 **Postrboard** 作为 skill 来规范视觉。对话非常口语化，不必过度思考 prompt：

> ok - we don't need a landing page here - just the component, output and settings panel in a minimal setting. Use the /postboard skill for the design and colors.

> For the date picker, when I click on the day, it tries to zoom in, but can't because there is nothing to zoom to. There should be no zoom there.

> It doesn't need to say "Zoom Out" at the top

> When I mouse over a month or year that contains the selected day, I cannot read the hover text.

> When I click "Today" it should take me to that day view, even if I'm on the month or the year.

> The months don't need numbers under them and they don't need to be in boxes

> Same goes for years. And it doesn't need to say "12 years" at the top.

注意这里有多**口语化**。不必过度设计 prompt，有问题就直接说问题。如果你有上下文，你就有了 prompt。

最重要的是：**不要满足于 AI 输出的「够用就行」。坚持质量，对此毫不妥协。**判断什么是好结果、什么不是，这个能力是你不可替代的价值。AI 永远替代不了你的人类触感和创造力。

## 7. Rubber Duck 交叉审查

迭代到你满意的状态后，做一次最终审查。

让 GitHub Copilot 做一次 **Rubber Duck review**。直接说出来就行：

> Perform a rubber duck review on this date picker component implementation

Rubber Duck review 的有趣之处在于：Copilot 会**让另一个 AI 模型家族的模型来做审查**。比如 Burke 用的是 GPT 5.6 Terra，审查就会交给 Sonnet。不同模型训练在不同的数据上，有**不同的盲区**。Rubber Duck review 能捕获单个模型可能遗漏的问题。

而且你可以在工作流的**任何阶段**使用它 —— 原型可以 review，规划也可以 review，完全取决于你想不想要第二意见。

想更进一步？把 Rubber Duck 和 Autopilot 结合起来，让不同模型在循环中协作改进：

> /autopilot rubber duck this date picker implementation. When you have the result, review it carefully and make any necessary adjustments. Repeat the rubber duck review until both you and the reviewing model agree that the only items that remain have diminishing returns.

这一步会消耗更多 token，但你是在**给代码做实战强化**。把它想成对未来自己的投资 —— 你不会再被那些现在就处理掉的问题困扰。

## 8. 收工，提交

做完 Rubber Duck review 之后，代码可以 stage、commit、进入下一个特性了。

Burke 的建议是：接下来要做跟这个 date picker 无关的事情时，**开一个新的聊天会话**。可以把聊天会话看作「按主题划分」—— 话题开始偏离太多时，就该开新会话了。

最后他展示了最终版本的 date picker，并且说了一句很坦率的话：

> 我知道这是一个有点「人造感」的例子，但我们能不能停下来想一想：现在用 AI 能做多少事了？做一个 date picker 曾经是最难的事情之一，你随便问问那些自己写过 date picker 的前辈们就知道了。

## 事情不必复杂

这套简单的工作流对大多数人来说完全够用。

简单还有另一个好处：**帮你多任务并行**。保持简单，你更容易记住哪个 agent 处于什么状态、上次做了什么。别忘了**你的上下文窗口也有限**。

AI 领域现在有很多事可以做 —— MCP server、skills、指令、自定义 agent、工作流、loop、agent 调度 agent、虚拟开发团队……可能性没有上限。

但 Burke 最后提醒：**现在没人真正知道自己在做什么，大家都在摸索**。今天看似神奇的 AI 咒语，明天可能就是反模式。

> 专注于用最简单的方式，拿到可重复的高质量结果。学会驾驭 harness，你就没问题了。

---

## 我的几点总结

Burke 这篇文章的价值不在于他教了什么奇技淫巧，而在于他**帮你降低了认知负荷**。

八步工作流拆开来看，每一步都不复杂：

1. **选一个工具**：别纠结，选离你最近的那个
2. **开 YOLO 模式**：给 agent 充分自主权，但要在沙箱里跑
3. **先做原型**：用 20 个变体探索方案空间，提前发现细节
4. **系统规划**：让模型帮你问出边界条件，深度参与而不是全盘接受
5. **自动实现**：用 Autopilot 循环确保计划每一项都完成
6. **人工迭代**：别满足于「够用」，你的品味决定最终质量
7. **交叉审查**：让不同模型家族的 AI 互相审查，捕获盲区
8. **交付，然后开新会话**

整个流程里最打动我的有两句话：

一句是：「如果你有上下文，你就有了 prompt」—— 不必过度设计提示词，口语化地跟 agent 协作就好。

另一句是：「不要满足于 AI 输出的『够用就行』。坚持质量，毫不妥协。判断什么是好结果的能力，是你不可替代的价值。」

如果你也受够了每天追新工具的疲惫，不妨试试这套工作流。把注意力从「下一个更好的 AI 工具是什么」转移到「我现在用的这个 harness，我真正驾驭好了吗」。

## 参考

- [原文：The harness is all you need (mostly) — @github on X](https://x.com/github/status/2082201573976056245)
- [GitHub Copilot 官方文档](https://docs.github.com/copilot)
- [GitHub Copilot CLI](https://docs.github.com/copilot/github-copilot-in-the-cli)
- [GitHub Copilot 桌面应用](https://docs.github.com/copilot/concepts/agents/github-copilot-app)
- [Autopilot 文档](https://docs.github.com/copilot/concepts/agents/copilot-cli/autopilot)
- [Rubber Duck Review 文档](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/rubber-duck)
- [GitHub Codespaces](https://docs.github.com/codespaces/overview)
- [grill-me skill by Matt Pocock](https://www.skills.sh/mattpocock/skills/grill-me)
- [Postrboard CSS Framework](https://burkeholland.github.io/postrboard-design)
