---
pubDatetime: 2026-05-29T08:03:54+08:00
title: "给研究型 AI 代理一份验证清单：让工具脚本从猜测变成契约"
description: "AI 研究代理给出的“dead code 检测脚本”看着合理，跑起来却漏掉了一整类问题。微软 ISE 团队复盘了这件事，并给出一份四段式验证清单——把使用场景、排除项、检测类、验证用例一项项写清楚，工具脚本才能从猜测变成可被验证的契约。"
tags: ["AI", "GenAI", "研究代理", "工程实践", "代码质量"]
slug: "verification-driven-tooling-prompts"
ogImage: "../../assets/841/01-cover.png"
source: "https://devblogs.microsoft.com/ise/verification-driven-tooling-prompts/"
---

![裂柱、0/1/2/3 阶梯与盖印契约：从似是而非的脚本走到可验证的工具契约](../../assets/841/01-cover.png)

让 AI 研究代理（research agent）调研一下“怎么做 dead code 检测”，它能在几分钟内给你一份看起来非常合理的工具清单和脚本。脚本能跑、能找出一批文件、能产出报告。问题是：**它漏掉的那些类型的死代码，你自己一开始也没意识到。**

微软 ISE 团队最近一篇博客把这件事拆得很清楚：作者 Dexter Williams 在帮一个团队做 dead code 检测脚本时踩了这个坑，复盘后给出一份四段式的“验证清单”，专门用来约束研究代理的输出。本文按原文展开，把这份清单和它背后的判断说人话讲一遍。

## 一个一句话需求带来的隐性盲区

需求看起来简单：

> 一条命令，安全地找出并清理 dead code。

团队用 GenAI 研究代理调研工具方案，最后落地的脚本只用了静态分析层：

- [ruff](https://github.com/astral-sh/ruff) — 解析 Python AST，找未使用的 import 和变量
- [vulture](https://github.com/jendrikseipp/vulture) — 通过代码结构分析找未被引用的定义
- [biome](https://github.com/biomejs/biome) — TypeScript/JavaScript 的 AST linter，处理 unused imports
- [knip](https://github.com/webpro-nl/knip) — 跟踪 import/export 图，找未使用的模块

跑出来的报告看着挺像那么回事。但事后再回头看，团队发现一个关键盲区：

- **运行时信号没接入**：比如代码覆盖率（code coverage）这类信号被完全跳过了
- **未被使用的 `private` 成员漏检**：所选工具都是基于 AST 的 linter 或 import 图分析器，没有任何一个做完整的 type-aware 语义分析
- **脚本生成后没再回头修补**这些漏洞

原文中作者用一句话点出了根本问题：

> GenAI can accelerate the wrong thing. It can assemble a plausible-looking tooling script quickly, but a plausible script is not the same as a correct one.

“合理”和“正确”是两件事。研究代理擅长前者，但前者并不会自动变成后者。

## 错在哪一步：让代理推荐了工具，但没让它证明覆盖

原文反思的核心结论是：**对一个已经走入维护期的成熟代码库，让研究代理“设计一个新工具”这个问法本身就是错的。**

理由很直接：dead code 检测在主流语言里是一个被研究透了的问题，每个生态都已经有相对成熟的工具。这种情况下，团队真正需要的不是新工具，而是**一份说明现有工具能覆盖到哪、还差什么的判断**。

所以问研究代理的方式要换：

> 不要让它“设计一个工具”，而是让它“推荐一组现有工具，并证明它们满足某份验证清单”。

整篇文章的方法论建议，本质上就是把这句话操作化。

## 验证清单：四段式约束研究代理的输出

ISE 团队把验证清单的产出拆成 4 段，从 Part 0 到 Part 3。每一段都有清楚的目的、输入和产物。

### Part 0：收集检测用例

在让代理产出任何清单之前，先要从你自己的代码库里把“具体例子”准备好——既包括应该被识别为 dead code 的例子，也包括不该被标记的例子。

两种收集方式：

- **人工巡检**：自己翻代码库，把典型例子记下来
- **代理辅助发现**：让代理扫一遍代码库，列出候选

注意这里的目标不是“现在就把所有 dead code 找出来”——那是最终脚本的任务。Part 0 要的是**覆盖不同检测分类和不同排除场景的代表性样本**，作为后面 Part 1–3 的输入。

### Part 1：定义排除项（exclusions）

让代理列出在你的环境里**明确不算 dead code**的内容。原文特别强调一句：

> This is the part an agent will likely skip, and it is also the part that prevents tooling from turning into a false-positive generator.

排除项是代理最容易跳过、也是最能决定工具会不会变成误报机器的一段。代理给出的排除项实际上构成了团队和工具之间的契约。

常见可以让代理识别的排除类别：

- 生成代码、vendored artifact
- 在生产里可能被打开的 feature-flag 代码
- 仅在测试里使用的 helper 与 fixture
- **依赖注入 / 服务注册**：类型名或程序集出现在配置里，容器启动时按名加载
- **插件注册和动态加载**：类型只通过注册表里的字符串被引用

这几类典型场景在 AST 层面看就是“没人 import”，但在运行时是真正被用的——它们的存在意义在于，决定一份 dead code 工具会不会“把生产代码误判成垃圾”。

### Part 2：定义检测类（detection classes）

让代理把 Part 0 的用例归纳成**检测类**，而不是直接对应工具。这里关键词是“类”：要的是“这一类问题”，而不是“ruff 能发现这条”。

一份实用起点：

- **Semantic unused members**：未被使用的成员，需要类型感知/语义分析
- **Unused exports and orphan files**：export 出去但没人 import，或孤立文件
- **Unused dependencies**：依赖装了但实际没人 import
- **Unused imports and locals**：基础 lint 类问题
- **Dynamic and reflective usage**：通过字符串、反射、注册表动态引用

只有把问题落到“类”上，下一步才能问“这个类是不是被现有工具覆盖了”。这也正是原文那个项目最初的真实漏洞：检测类里漏掉了 semantic unused members，所以选完工具后这个分类就再没人管过。

### Part 3：为每个检测类做一个验证用例（verification case）

每一个检测类，代理都要交出一份验证用例，至少包含：

1. 一段最小化的代码示例，应该被该类工具识别为 dead code
2. 该被运行的精确命令
3. 期望看到的结果

原文里有一段需要单独抄下来：

> These are not unit tests for your product. They are capability tests for your tooling.

这些不是给业务代码写的单元测试，而是给**工具自己**写的能力测试——证明你选的这套工具确实能覆盖你声明的检测类。

而且作者直接给出一条判别规则：

> If the agent cannot produce a verification case for a detection class, it cannot prove that recommended tools will cover it.

代理交不出某个检测类的验证用例，就说明它没法证明所选工具能覆盖这一类。这种情况下不该接受这个推荐结果。

### 输出格式：两张可以直接抄走的表

原文给了两张示意表，分别对应“要被标记”和“不能被标记”。

**检测类验证表（要被标记）**

| 检测类                          | 验证示例                                          | 执行命令                      |
| ------------------------------- | ------------------------------------------------- | ----------------------------- |
| Semantic unused members         | 加一个未被使用的 private 方法                     | 跑一次语义/类型感知检查       |
| Unused exports and orphan files | export 一个无人 import 的符号；或新建一个孤立文件 | 跑基于 import/export 图的分析 |
| Unused dependencies             | 加一个从未被 import 的依赖                        | 跑依赖分析                    |
| Unused imports and locals       | 加一个 unused import 和 unused local              | 跑 linter 检查                |
| Dynamic and reflective usage    | 加一个通过注册表动态引用的符号（如插件）          | 跑完整脚本，确认没被错标      |

**排除项验证表（不能被标记）**

| 排除类          | 验证示例                      | 执行命令                   |
| --------------- | ----------------------------- | -------------------------- |
| Generated code  | 一个应被忽略的 generated 目录 | 跑完整脚本，确认无 finding |
| Plugin registry | 一个通过注册表加载的符号      | 跑完整脚本，确认未被错标   |

两张表合起来，正反两个方向都能验证。验证清单的价值在这里就完整了：**它不仅说明工具能找出什么，也证明它不会乱标什么。**

## 还要注意：研究代理“继承下来的提示”会带来漂移

文末作者补了一段关于提示工程的提醒，对实际使用 GenAI 调研工具同样重要。

研究代理通常自带一套**基线指令（baseline instructions）**——比如它能不能写代码、能不能调用工具、输出该怎么排版。你写的任务级 prompt 是叠加在这些基线指令之上的。

如果你的 prompt 和基线指令冲突，或者完全没意识到基线指令在那里，代理可能会按一种你没预期的方式解读你的请求。原文给了一个反例对比：

- 那次 dead code 调研：研究代理的基线写明“do not implement”，作者的 prompt 是“分析工具并给出推荐”——两者兼容，结果可控
- 如果作者的 prompt 是“写代码并测”，或者基线限定“只动 Python 文件”而 prompt 要它分析 TypeScript，结果就会不完整或不正确

把它当成验证工作的一部分：

- 先弄清楚研究代理继承了哪些基线指令
- 写任务级 prompt 时**补足**而不是**反驳**这些基线

这一条的意义是：验证清单约束的是“代理交付物”，但前提是“代理本身”要先被理解到能被约束。

## 收尾：把工具脚本从“猜测”升级为“契约”

原文最后留下的判断很短：

> The biggest win is not a specific tool. It is a repeatable process you can trust.

> When code production accelerates, verification becomes a limiting factor. A verification checklist turns tooling prompts from a guess into a contract.

把这段话翻成可操作的语言：

- 真正能复用的，不是某一份脚本，而是“怎么让 AI 推荐的工具方案可被验证”的流程
- AI 让代码产出加速以后，**验证能力**会成为新的瓶颈
- 一份验证清单的核心作用，是把工具相关 prompt 从“先看着合理”升级到“可以被签收的契约”

下次让研究代理帮你调研一个工具方案时，先准备好 Part 0 的代表性用例，再让它依次产出 Part 1–3。这一套流程不复杂，但能在你接受推荐之前，把代理“看起来很在行”的部分和“真的覆盖到了”的部分区分开。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- 原文：[Verification-driven tooling prompts for fast-moving codebases](https://devblogs.microsoft.com/ise/verification-driven-tooling-prompts/)（Dexter Williams，ISE Developer Blog，2026-05-28）
- [ruff](https://github.com/astral-sh/ruff)
- [vulture](https://github.com/jendrikseipp/vulture)
- [biome](https://github.com/biomejs/biome)
- [knip](https://github.com/webpro-nl/knip)
