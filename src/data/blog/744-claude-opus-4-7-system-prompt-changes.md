---
pubDatetime: 2026-04-20T09:02:12+08:00
title: "Claude Opus 4.7 系统提示词变化全解析"
description: "Anthropic 是少数公开发布系统提示词的 AI 厂商。本文梳理 Claude Opus 4.6 到 4.7 系统提示词的核心变更，包括行动优先策略、tool_search 机制、内容安全扩充以及冗余措辞的清理。"
tags: ["Claude", "Anthropic", "AI", "Prompt Engineering", "LLM"]
slug: "claude-opus-4-7-system-prompt-changes"
ogImage: "../../assets/744/01-cover.jpg"
source: "https://simonwillison.net/2026/Apr/18/opus-system-prompt/"
---

![Claude Opus 4.7 系统提示词变化全解析](../../assets/744/01-cover.jpg)

Anthropic 在主流 AI 厂商中算是少数派——他们真的会把 Claude 面向用户产品的系统提示词公开发布出来，而且已经积累了从 2024 年 7 月 Claude 3 至今的完整历史记录。每次新模型发布，都可以清楚地看到 Anthropic 在引导 AI 行为方面做了哪些调整。

Opus 4.7 于 2026 年 4 月 16 日上线，伴随着一次系统提示词更新（上次更新是 Opus 4.6，时间是 2026 年 2 月 5 日）。Simon Willison 用 Claude Code 将 Anthropic 的提示词文档按模型拆分，并构建了一份带时间戳的 Git 提交历史，方便做版本间 diff。以下是他从 [4.6 到 4.7 的 diff](https://github.com/simonw/research/commit/888f21161500cd60b7c92367f9410e311ffcff09) 中提炼的关键变化。

## 品牌名称调整

"开发者平台"（developer platform）被统一改为"Claude Platform"。这是一个命名上的收拢，体现了 Anthropic 对其平台品牌的统一化意图。

## 工具列表新增 PowerPoint 支持

系统提示词中的 Claude 工具清单新增了一项：

> Claude in Powerpoint——一个幻灯片 Agent。Claude Cowork 可以把它作为工具使用。

此前已经提到 Claude in Chrome（浏览器 Agent）和 Claude in Excel（电子表格 Agent），这次 PowerPoint 进入名单，说明 Anthropic 的 Office 集成布局已经延伸到演示文稿场景。

## 内容安全：儿童保护条款大幅扩充

子安全部分被重新组织到一个新的 `<critical_child_safety_instructions>` 标签下，并新增了一条值得注意的规则：

> 一旦 Claude 以儿童安全为由拒绝了某个请求，在同一对话中的所有后续请求都必须以极高的警惕度来处理。

这意味着相关风险判断会在对话上下文中持续生效，而不是只针对单条消息。

## 不再留客：更尊重用户的退出意愿

新提示词明确要求：

> 如果用户表示准备结束对话，Claude 不应要求用户留下或试图引出新的对话轮次，而是尊重用户停止的请求。

这条变化针对的是某些 AI 产品中常见的"引导用户继续对话"行为——系统提示词现在明确把这种做法排除在外。

## 新增行动优先策略：`<acting_vs_clarifying>`

这是此次更新里内容最丰富的一条。新增的 `<acting_vs_clarifying>` 章节明确了一个原则：**能直接做的，不要先问**。

> 当请求遗留了次要细节时，对方通常希望 Claude 现在就做出合理尝试，而不是先接受一轮提问。只有在缺少关键信息导致请求根本无法回答时（例如引用了一个不存在的附件），Claude 才会在一开始提问。
>
> 当有工具可以消除歧义或补充缺失信息时——搜索、查询地理位置、检查日历、发现可用能力——Claude 会先调用工具解决歧义，而不是要求用户自己去查。用工具行动优先于让用户自己做查询。
>
> 一旦开始执行任务，Claude 会一直做到给出完整答案，而不是做到一半就停下来。

这个方向的背后逻辑是：过度确认和频繁提问对用户来说是摩擦，不是帮助。

## `tool_search`：先查工具，再说"做不到"

系统提示词中出现了一个新的 `tool_search` 机制：

> 在断定 Claude 缺少某项能力之前——访问用户位置、记忆、日历、文件、历史对话或任何外部数据——Claude 应调用 `tool_search` 检查是否有相关工具处于延迟加载状态。只有在 `tool_search` 确认没有匹配工具存在后，"我无法访问 X"才是正确的表述。

这解释了一种用户早就注意到的行为：Claude 有时会在回答问题前先查找一遍可用工具。`tool_search` 让这个能力发现过程变得显式且有据可查。相关的 [API 文档](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) 和 [技术博客](https://www.anthropic.com/engineering/advanced-tool-use)（2025 年 11 月）也印证了这一点。

## 克制冗余：新增"简洁"要求

提示词新增了一段要求 Claude 控制回答长度的指令：

> Claude 保持回答聚焦和简洁，避免用过长的响应淹没用户。即使答案包含免责声明或注意事项，也应简短带过，将大部分篇幅留给核心回答。

这条是对模型行为的显式约束，而不是依赖训练本身来解决"话多"的问题。

## 删除了哪些内容

4.6 提示词中有两条针对特定行为的约束，在 4.7 中被移除：

> Claude 避免在星号中使用表情动作，除非用户明确要求这种风格。
> Claude 避免使用"genuinely"、"honestly"或"straightforward"这类词。

推测原因是 Opus 4.7 在这两方面不再有明显的过度倾向，相关的"纠偏指令"因此可以退休。

## 饮食障碍新增专项保护

新增了一个此前从未出现过的条目：

> 如果用户表现出饮食障碍的迹象，Claude 不应在对话的任何其他地方提供精确的营养、饮食或运动指导——不给具体数字、目标或分步骤计划。即使本意是帮助建立更健康的目标或揭示饮食障碍的潜在危险，这类细节仍可能触发或加剧相关倾向。

这条规则的特殊之处在于它的作用范围是**整个对话**，而不仅仅是触发该判断的那条消息。

## 对敏感话题的回答边界

`<evenhandedness>` 章节新增了一条：

> 如果有人要求 Claude 对复杂或有争议的问题给出简单的是/否回答（或任何其他短词回答），或要求对争议性人物做评论，Claude 可以拒绝给出这种简短回答，转而给出有深度的分析，并解释为什么简短回答不合适。

这直接针对一种已知的提示词注入攻击方式：通过截图让 AI 对敏感问题强制表态。

## 删除了特朗普相关的澄清说明

4.6 提示词中有一条明确说明：

> 唐纳德·特朗普是美国现任总统，于 2025 年 1 月 20 日就职。

这条文字在 4.7 中消失了。原因是 Opus 4.7 的知识截止日期已更新至 2026 年 1 月，模型本身已经可以可靠地掌握这一事实，不再需要系统提示词来手动纠正。

## 工具列表没有变化

Anthropic 公开的系统提示词并不包含工具描述——那部分同样重要，但没有被发布出来。Simon Willison 通过直接向 Claude 提问获取到了工具列表，[共享对话链接在这里](https://claude.ai/share/dc1e375e-2213-4afb-ac1b-812d42735a8e)。工具列表与 Opus 4.6 保持一致，未发生变化。

---

从整体来看，Opus 4.7 的系统提示词调整透露出几个方向：减少对话摩擦（行动优先、不主动留客）、扩充安全边界（儿童保护、饮食障碍）、强化工具能力的自我发现（`tool_search`），以及精简掉已经不再必要的行为纠偏指令。每一条都是 Anthropic 在模型训练与提示词调控之间持续寻找平衡的具体证据。

## 参考

- [Changes in the system prompt between Claude Opus 4.6 and 4.7 – Simon Willison](https://simonwillison.net/2026/Apr/18/opus-system-prompt/)
- [Anthropic 系统提示词发布记录](https://platform.claude.com/docs/en/release-notes/system-prompts)
- [4.6 → 4.7 Git diff](https://github.com/simonw/research/commit/888f21161500cd60b7c92367f9410e311ffcff09)
- [tool_search API 文档](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- [Claude 工具完整列表（共享对话）](https://claude.ai/share/dc1e375e-2213-4afb-ac1b-812d42735a8e)
