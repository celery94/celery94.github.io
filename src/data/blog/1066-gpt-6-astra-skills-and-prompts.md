---
pubDatetime: 2026-09-14T08:26:00+08:00
title: "GPT-6 Astra：删掉多余的技能与提示词"
description: "新模型更强，旧提示词却可能变成负担。本文整理 OpenAI 对 GPT-6 Astra 的行为说明，并给出缩短 skill 描述、给 AGENTS.md 加触发条件、把边界说到可执行的具体做法和迁移清单。"
tags: ["GPT-6 Astra", "Codex", "AGENTS.md", "Prompt Engineering", "OpenAI"]
slug: "gpt-6-astra-skills-and-prompts"
ogImage: "../../assets/1066/01-cover.jpg"
source: "https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra"
---

过去一年里，为了让编码 agent 老老实实干活，你在 `AGENTS.md` 和各个 skill 里攒了一堆约束：每次编辑前先读三份文档、写完必须跑测试、动手前先问一句、不要自作主张往下做。这些规则在当时是对的。

换成 GPT-6 Astra 之后，同一批规则会开始起反作用。OpenAI 在 [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) 里的核心观点是：模型变强之后，**为旧模型写的脚手架应当被削掉**，而不是继续叠加。这篇是经验建议，而配套的 [Using GPT-6 Astra](https://developers.openai.com/api/docs/guides/latest-model) 官方指南给出了更具体的模型行为和可直接粘贴的提示词。本文把两者对齐起来，按「skill → AGENTS.md → 提示词 → 迁移清单」整理成一份可执行的清理流程。

先说清归属：下面关于 Astra 行为的所有描述都来自 OpenAI 自己的文档与公告，属于厂商声明，不是独立验证过的结果。可执行的部分是那些提示词和清理动作。

## 三种形式，同一个问题

要清理的东西散落在三个地方，它们的加载时机完全不同：

| 形式                            | 什么时候进上下文                     | 清理重点                           |
| ------------------------------- | ------------------------------------ | ---------------------------------- |
| skill 的 `name` + `description` | 始终在上下文里，模型靠它决定要不要用 | 描述要短，只回答「什么时候用」     |
| skill 的正文与 `references/`    | 命中之后才加载                       | 根文档做路由器，细节放引用文件     |
| `AGENTS.md`                     | 在这个仓库里工作时加载               | 把无条件要求改成条件指引           |
| 任务提示词                      | 每次请求                             | 定义「完成」的样子，而不是描述步骤 |

前两项属于上下文成本，后两项属于行为约束。清理思路是一样的：**问每一句话「模型现在还需要它吗」**。

## skill 描述要短，判断标准是触发条件

OpenAI 说，很多人已经习惯给项目打包一堆 skill，每个 skill 的名字和描述都会进模型上下文。当 skill 太多时，Codex 会开始截短这些描述来腾空间，模型看到的每段描述反而更少，也就更难挑对工具；描述之间还会互相矛盾或过度强调触发时机，让模型加载了帮不上忙的说明。

官方给的好坏对照很直观：

> Bad: Create and validate Postgres schema migrations. Use when working with databases, queries, models, or persistence.
> Good: Create and validate Postgres schema migrations. Use when adding or changing a migration, or reviewing its rollout.

坏版本会让模型在碰到任何跟数据库有关的事情时都想加载它；好版本把触发条件收窄到「新增、修改或评审迁移」这一件事。这不是措辞问题，而是把一个高频误触发改成了精确触发。

第二点是渐进披露：读一个 skill 就消耗上下文，让你更快逼近 compaction，还会引入和当前任务无关的说明。对包含多条工作流的 skill，根文档应该是一个最小的路由，只告诉模型该去哪里看，而不是让它把所有内容读一遍。官方构建 skill 的文档把这条写得更直接：`description` 决定模型什么时候考虑这个 skill，详细流程、格式和安全说明放在正文里（[Build skills](https://developers.openai.com/plugins/build/skills.md)）。

第三点最反直觉：**很多 skill 被写成了详细的行程表或菜谱，而模型已经不再需要**。原文的说法是，模型理解含糊和歧义的能力变强了，过于具体的指引在以前有帮助，现在反而会拖累结果。判断标准可以很简单——如果一段说明是在描述「步骤该长什么样」，而模型自己也知道，删掉；如果它描述的是「这个团队特有的约定」，保留。

最后一条容易被忽略：仓库里的 skill 不只你自己的 agent 会用，其他贡献者的 agent、乃至别的模型都会读。对别的模型有用的指引，可能恰好把 Astra 约束死。写之前先想清楚这份说明留给谁用。

## AGENTS.md：把无条件要求改成条件指引

`AGENTS.md` 是跨 agent 的公开约定，[agents.md](https://agents.md) 自称已被超过 6 万个开源项目采用。它在你的仓库里随处生效，所以每一条都值得定期重新问一遍是否还需要。

原文举的例子是「每次编辑前读一堆文档」：

> Bad: Before every edit, read architecture.md, database.md, and deployment.md.
> Good: Use architecture.md for service boundaries, database.md for schema changes, and deployment.md when preparing a deployment.

坏版本会把一个改错别字的任务也变成通读三份文档。好版本保留了文档的价值，但把它变成按需触发。附带条件也很实际：文档本身得跟着更新，否则指向过期内容是负收益。

官方指南在同一方向上给了更硬的提醒：GPT-6 Astra 更能遵循长指令，但也**更容易受上下文中的信息影响**——skill 里含糊或互相矛盾的说明可能让它中途停下来不干活。官方因此明确建议审计模型能读到的 skill 和其他文件（`AGENTS.md` 属于这一类）。换句话说，`AGENTS.md` 不再只是「写了就更好」的加分项，写得含糊是有成本的。

## 模型已经会做的事，就别再要求

原文最实用的一条观察是关于测试的：以前的模型需要被鼓励去跑测试、检查自己的结果，所以你的 `AGENTS.md` 里很可能留着「改完必须运行测试」。Astra 自己就会做这件事，于是同一条指令变成了多余动作的来源。

官方指南把同一现象描述得更细：对编码任务，Astra 在认为任务完成前倾向做得比较彻底；对较小的任务，这可能产生超出任务需要的测试。官方给的校准提示词是：

```text
Do not write tests for reversible, low-impact changes that mirror the implementation. If you do choose to verify your work with tests, make sure that the tests are meaningful and necessary to verify implementation.

Run tests appropriate to the change and complete required checks. Once those pass, broaden or repeat testing only when new changes, failures, or unresolved concerns justify it; otherwise, continue toward completing the task.
```

注意这里的做法不是「删掉测试要求」，而是把它从无条件改成有判断标准的条件：低影响且可逆的改动不写镜像测试，通过之后的扩大验证需要有新理由。

第二类要删的是「跑测试前先问我」。原文建议用 `AGENTS.md` 明确授权安全的特定流程，例如本地测试套件：

> The local tests use disposable fixtures and have no production access. Run them, fix failures caused by the requested change, and rerun affected tests without asking for approval at each step.

这句话的结构值得照抄：先说清为什么安全（一次性 fixture、无生产访问），再说清授权范围（运行、修复与本次改动相关的失败、重跑受影响用例），最后才说不要每步都问。

## 持久性：先把「完成」定义出来

如果你习惯的是 GPT-5.6 Sol 那种一次接下需求就长时间连续推进的风格，Astra 会让你觉得它更犹豫：它可能做出第一版实现就回来找你 review，而活儿还没干完。

官方指南解释了原因：Astra 被设计成更主动的协作者，当额外输入可能实质改变结果时，它更倾向于问用户——这会导致在你期待它做合理假设并继续下去的地方停下来。

处理办法不是把「不要问我」写成硬规则，而是把完成条件写进请求。原文的建议是：如果任务包含「让实现跑起来、检查结果、修掉失败的部分」，就把这些明确写进请求；反过来，如果你写「第一版实现后停下来等我 review」，模型就会被拉向那个更早的停止点——先确认那个停止点是不是你真的需要的。

官方给了两段可直接使用的提示词。一段用于提高自主性：

```text
You should infer the user's intent and task scope from the instructions and prior conversation context. Your job is to bias towards action and carry the user's intended task to completion.

When the user expresses intent to perform new work or fix an existing issue, persist until the user's intended goal is complete. Progress autonomously towards the user's goal (e.g. creating isolated worktrees / checkouts if needed, resolving merge conflicts, read-only actions, creating draft PRs etc.) unless they are clearly destructive or irreversible.
```

另一段把「先做完能做的、再让人审批具体结果」写成规则：

```text
Before asking the user clarifying questions, you should complete the work that is already authorized from context and necessary to make the proposed action concrete and reviewable. The user should be approving a concrete, reviewable result. ... You don't need user permission for reversible tasks, read-only actions, reviews or fixes, or anything for which authorization is provided earlier in the session or strongly implied from the task instruction.

Do not introduce unsolicited warnings, disclaimers, approval flows, or safety/compliance checklists due to hypothetical risk.
```

最后一句是这次清理里最值得单独拎出来的：为了防旧模型越界而加的免责声明和审批流程，在 Astra 上属于「基于假设风险」的多余动作。

## 边界：把「别乱来」改成「可以做到这里」

原文对边界的判断是：你当初写下那些强硬措辞，可能是因为之前的模型会擅自替你做决定，所以要求它必须先问。这个出发点没错，但 Astra 是 OpenAI 目前最对齐的模型，会在确认安全的前提下行动——所以那套措辞可能被认真执行到过头的程度，在该继续的地方停下来。

这里有一个风险边界需要自己判断：把审批要求放宽的前提是操作可逆。原文和官方指南给的分类是一致的——只读操作、review、修复、可逆改动不需要逐步审批；部署、写外部系统、合并 PR、发布站点这类要么不可逆、要么影响外部的动作，仍然应当让人审批「一个具体的结果」，而不是在动手前审批一个想法。

## 冲突怎么办：把指令优先级写明白

当 `AGENTS.md`、skill 正文和用户当场说的话互相矛盾时，模型需要一个排序规则。官方给的提示词只有两句：

```text
The user's instructions take precedence over guidelines provided in a skill. If explicit user instructions conflict with a skill's instructions, prioritize the user's instructions.
```

更有用的是第二段，它把「审计」变成模型可以执行的动作：

```text
If a skill causes you to ask for permission or confirmation, pause, leave requested work unfinished, or diverge from the user's intent, name and link to the exact SKILL.md file you read, quote the relevant instruction, and briefly explain how it applies. Distinguish explicit skill requirements from your interpretation of guidelines.
```

把它和原文结尾的建议接起来，就是一套完整的清理流程：让 Astra 按这篇文章的标准审计你自己的 skill 和 `AGENTS.md`，要求它逐条指名文件、引用原文、说明影响，然后你再决定删哪一条。比起自己一条条重读，这个做法的好处是它会指出你根本没想到的静默冲突——尤其是当你装了十几个 skill 的时候。

## 迁移清单：模型之外的改动

原文只讲了 skill、`AGENTS.md` 和提示词，但同一份官方指南里还有一批 API 侧的变更，换模型时容易漏：

- 把 `model` 设为 `gpt-6-astra`。
- 移除 `temperature`、`top_p`、`top_logprobs`；Chat Completions 还要移除 `logprobs`，Responses 要从 `include` 里去掉 `message.output_text.logprobs`。
- 推理强度不支持 `none`。如果原来用的是 `none` 或 `minimal`，从 `low` 起步再比对结果；其余情况保持现有的有效强度。
- 工具调用需要 Responses API。
- 从 GPT-5.5 或更早版本迁移时，把 `prompt_cache_retention` 换成 `prompt_cache_options.ttl` 并设为 `"30m"`。
- EU 数据驻留下 Fast mode 不可用，需改用 Standard 处理；Fast mode 本身不包含延迟 SLA。
- 新增能力包括异步工具调用（`async: true` 加原始 `call_id` 回填结果）、mid-turn steering（工作中追加修正）、用 `configuration_update` 在不重写前缀的前提下调整推理强度，以及针对错位的异步监控告警。

## 可以照着做的清理清单

- 把每个 skill 的 `description` 缩到「做什么 + 什么时候用」两句话，触发条件写成具体动作，不写「涉及 X 就使用」。
- 多工作流的 skill 把根文档改成路由，细节移进 `references/`，并写明什么时候读哪个文件。
- 删掉那些只是在复述模型已知步骤的「菜谱式」段落。
- 给 `AGENTS.md` 里的每条文档引用加上触发条件，把「每次编辑前读」改成「做 X 时读」。
- 删掉「必须写测试 / 必须跑测试」这类无条件要求，换成按影响面和可逆性判断的标准。
- 用 `AGENTS.md` 明确授权安全的重复性流程（本地测试套件、一次性 fixture），写清为什么安全。
- 把任务请求里的「完成」写具体：实现跑通、验证结果、修掉失败。
- 把不可逆动作的审批保留在「具体结果」上，删掉基于假设风险的一般性审批和免责声明。
- 加上用户指令优先于 skill 的规则，以及让模型指名冲突指令的审计提示词。
- 让 Astra 按上面这套标准审计一遍你的 skill 和 `AGENTS.md`，再动手删。

新模型发布时，大家的第一反应通常是加规则；值得做的往往是减法。Aide Hub 会继续跟踪这类 agent 工作方式的变更，并把官方文档里能落地的部分整理成清单。如果你在清理旧提示词时发现了哪条规则其实一直在帮倒忙，欢迎发来说明。

## 参考

- [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)（原文，OpenAI）
- [Using GPT-6 Astra：Prompting best practices 与迁移清单](https://developers.openai.com/api/docs/guides/latest-model)
- [Build skills：OpenAI 官方 skill 编写文档](https://developers.openai.com/plugins/build/skills)
- [agents.md：AGENTS.md 开放格式](https://agents.md)
- [skill-creator（OpenAI 官方 skill 源文件）](https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md)
- [Codex 仓库中的 openai-docs skill](https://github.com/openai/codex/tree/main/codex-rs/skills/src/assets/samples/openai-docs)
