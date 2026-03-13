---
pubDatetime: 2026-03-13T05:44:05+00:00
title: "把知识写进 Markdown，把动作交给 MCP：Agent 架构里最该拆开的，可能根本不是模型，而是 know 和 do"
description: "The New Stack 这篇文章最有价值的地方，不是简单唱衰 MCP，而是把很多团队今天在 agent 系统里最容易混掉的两类问题拆开了：知识问题和执行问题。团队规范、工作流、语气、判断边界这类“know”适合进 SKILL.md；API 调用、数据库查询、消息发送这类“do”才适合进 MCP。真正成熟的方向不是二选一，而是把 Markdown skills 放在上层，让 MCP 回到执行层。"
tags: ["AI Agents", "MCP", "Agent Skills", "AI Architecture"]
slug: "markdown-skills-vs-mcp"
ogImage: "../../assets/607/01-cover.png"
source: "https://thenewstack.io/skills-vs-mcp-agent-architecture/"
---

![Markdown Skills 与 MCP 分层概念图](../../assets/607/01-cover.png)

过去一年里，很多团队做 agent 的姿势都挺像：一遇到新需求，先找 MCP server；没有就自己包一个；能不能做先不说，反正先把工具面拉满。结果是 agent 一启动，先吞下一大坨 tool schema，几十上百个能力摆在眼前，token 先烧一轮，真正该做的任务还没开始，脑子已经被工具目录塞满了。

The New Stack 这篇《The case for running AI agents on Markdown files instead of MCP servers》抓到的问题很准：**很多团队并不是 MCP 用错了，而是拿 MCP 去解决了本来不该由它解决的问题。**

文章最重要的判断可以压成一句话：agent 系统里有两类完全不同的事情，一类是“需要知道什么”，另一类是“需要做什么”。你把这两类混在一起，系统就会又贵、又重、又难维护。

## 真正该拆开的，不是 MCP 和 skills 谁更高级，而是 know 和 do

这篇文章一上来举的例子很猛：Brad Feld 把整家公司很多日常工作跑在十几份 Markdown 文件上。邮件草拟、客服分流、董事会指标准备、产品发布流程，都不是靠一个巨大的 Web 应用或复杂 orchestration runtime，而是靠结构化 Markdown 文档去教 Claude Code 怎么做事。

注意这里最值得看的不是“Markdown 也能跑公司”，而是这套结构的分工方式。访问 Gmail、Linear、Help Scout 这些外部系统，确实还是通过 MCP servers 完成；但真正定义 workflow、guardrails、语气、判断逻辑的部分，并不住在 MCP 里，而是住在 skill files 里。

这就点到了一个今天特别常见的架构误区。很多人一说 agent 能力，就直接把“知道规则”和“执行动作”打成一个包，统一放进 tools。结果工具层开始承担两份本不属于同一层的责任：

- 一边承载 API / database / message queue 的运行时调用
- 一边偷偷承载团队自己的流程知识、语气规范、判断约束

这就是系统越长越臃肿的起点。

> agent 想完成任务时，真正先该问的不是“用哪个 server”，而是“它现在缺的是知识，还是缺的是执行权”。

## 知识问题，天然更像 Markdown；执行问题，天然更像 MCP

文章里把问题分成两类，我觉得特别适合拿来当架构检查表。

第一类是 knowledge problem（知识问题）。比如：编码规范、部署流程、工单 triage 规则、客服回复语气、团队怎么用 GitHub、什么时候该升级优先级、什么情况下必须 escalation。这些东西通常变化没有那么快，很多时候是周、月级别迭代；可以用自然语言说清楚；而且大多数都完全塞得进上下文窗口。

第二类是 execution problem（执行问题）。比如：查数据库、发邮件、建 issue、读 Slack、打 API、写消息队列、调外部服务。这里已经不是“告诉 agent 怎么做得好”这么简单了，而是需要 runtime、认证、网络访问、状态管理和错误处理。

一旦这么分，你会发现很多团队过去堆出来的 MCP server，实际上是在拿运行时基础设施去包知识层内容。有人想让 agent 理解“我们团队怎么提 PR”，于是搞了个巨大的 GitHub MCP server，把所有 repo / issue / PR / branch / review / CI 操作全端上来。agent 当然“能用”，但它为此要先读一大份 schema，理解一堆根本不是当前任务必需的能力。

如果你真正缺的是“我们团队用 GitHub 的方式”，一份 SKILL.md 可能就够了：

- 用 `gh` CLI
- 提交前先跑测试
- 默认 squash merge
- commit message 走 conventional commits
- 某些目录改动必须找谁 review

这类内容本质上是 institutional knowledge（组织知识），不需要一个活着的 server 才能存在。

## 这篇文章真正值钱的地方，是把 skill + MCP 的混合层讲清楚了

如果文章只是停在“Markdown 比 MCP 好”，那就太糙了。它真正成熟的部分，在于承认第三种最常见的现实：**agent 不只是需要知道，也不只是需要做，而是需要“知道怎么把事做对”，然后再去执行。**

这就是 hybrid case，也是大多数生产系统真正该采用的结构。

skill 文件负责把 workflow、顺序、边界条件、判断准则写清楚；MCP 则作为底层 execution layer，被 skill 在必要时调用。换句话说，skills 决定 agent 怎么思考，MCP 决定 agent 怎么动手。

文章举的客服分流例子就很典型。一个好的 support triage skill，应该知道：

- 怎么按严重程度分类
- 面向不同客户层级用什么语气
- 什么时候该直接解决，什么时候必须升级
- internal note 里要包含哪些上下文

这些都属于“知道怎么做得好”。真正去读会话、打标签、发回复，那才是 Help Scout MCP server 该做的事。

这个分法妙就妙在：哪怕 MCP 断了，skill 仍然能输出一份像样的分析、草稿和建议；消失的是自动执行，不是思考能力。这是非常健康的分层。

## 50x 到 100x 的 token 差距，不只是省钱，更是在给 reasoning 腾地方

文里提到一个特别有传播力的数据：GitHub MCP server 的 tool schema 可能要吞掉两三万到五万 token，只是为了让 agent 知道“它能干什么”；而一份描述团队 GitHub workflow 的 SKILL.md 可能只要两三百 token，甚至 200 token 级别。

这差距不是小修小补，而是架构层级的浪费。

很多人看这种对比，第一反应是“哦，那只是 API bill 更贵”。其实更要命的不是钱，而是 reasoning budget（推理预算）被提前吃掉了。上下文窗口里每一段工具描述，都是模型没法用来思考你的真实任务的那部分空间。你给它塞了一座工具超市，它就得先逛完再决定买什么。

而 skill 文件的好处，是它给的不是“宇宙里一切可能做法”，而是“你这个团队此刻最该怎么做”。上下文更短，也更聚焦。很多时候 agent 表现变好，不只是因为 token 省了，而是因为输入终于不再那么稀释。

AI 时代一个很常被低估的事实是：**并不是给模型更多工具，它就一定更聪明；很多时候，是给它更少但更贴近任务的结构，它反而判断得更稳。**

## Git 友好的知识层，是 skills 最大但最容易被低估的优势

我很认同文章里强调的另一个点：skill 文件是纯文本，能进 git，能走 PR，能看 diff，能 blame，能做 branch 策略。这听起来像老生常谈，但其实决定了它是否适合在组织里长期活下来。

当 agent 行为被埋在 MCP server 代码里时，你想改一种回复语气、调整一个 triage 规则、更新某个升级判断，往往意味着改代码、重新部署、重新验证。而这些变化，很多时候根本不是“工程实现变化”，而是业务规则变化、沟通策略变化、组织约定变化。

把这类内容放进 Markdown skill，最大的好处就是它终于回到了可读、可审、可版本化的状态。产品、运营、支持、安全、工程这些角色都能看得懂，也能参与 review。它不再是“只有写 server 的人才能改”的黑箱。

这其实特别适合平台团队。因为一旦 agent 系统开始跨部门、跨团队扩展，真正难维护的从来不只是 API 连接，而是组织知识总在变。如果每次知识更新都要动一层 runtime 代码，系统迟早会越来越僵。

## 这篇文章和现在的 Agent Skills 趋势，其实在收敛到同一个方向

你把 Brad Feld 的 CompanyOS、Supabase 的 `agent-skills` repo、Microsoft 的 `.NET Skills Executor`、Claude Code 自己的 skills 机制放一起看，会发现方向已经很清楚了。

不是 MCP 失败了，而是行业正在慢慢达成一种更成熟的共识：

- **skills / SKILL.md** 负责知识、流程、语气、边界、顺序
- **MCP** 负责执行、连接、鉴权、状态、可观测性
- 真正好用的 agent 系统，是 skill 在上、MCP 在下，而不是 MCP 一层包打天下

这和前面你发过来的几篇 agent 文章其实是同一条线：Agent Framework 在补 runtime 和 orchestration，Foundry 在补模型平台和治理，MCP 在补工具执行边界，而 skills 则在补“团队自己的做事方法”这层最难标准化、却最决定效果的东西。

## 如果周一就要动手，该怎么改自己的 agent 架构

文章最后那段“Monday morning”建议挺实用，我按更工程一点的方式翻一下，基本可以变成三步：

1. **审你现有的 MCP servers**：每个 tool 问一句，它到底在解决知识问题，还是执行问题？
2. **先拆最贵的那批**：哪个 server schema 最重、token 最贵、知识掺得最多，先从它开始抽 SKILL.md
3. **做 standalone test**：断掉 MCP 之后，这个 skill 还能不能产出一份有用的分析、草稿、建议？如果能，说明知识层拆对了；如果完全瘫痪，说明你很可能还把执行逻辑和知识逻辑缠在一起

这个检查法很接地气，也很适合今天大多数 agent 项目。因为很多系统不是从白纸设计出来的，而是一边接工具一边长出来的。你现在回头重构，最现实的方式就是先按 know / do 做一次清账。

![原文配图：Markdown 与 MCP 架构讨论](../../assets/607/02-markdown-vs-mcp.jpg)

## 如果把这篇文章压成一句话

我会这么总结：**Markdown skills 不是为了替代 MCP，而是为了把本来就不该塞进 MCP 的知识层，从执行层里剥离出来。**

MCP 赢的是协议和运行时连接这场仗，这没有问题；但 agent 真正知道“你们团队怎么做事”的那部分，很多时候根本不需要一台活着的 server。它需要的是一份清楚、短小、可版本化、可 review、模型天然能理解的文档。

这也是为什么我越来越觉得，很多团队下一步真正该优化的，不是再多接几个 server，而是先把自己的 domain knowledge 写出来。agent 最缺的往往不是又一个工具，而是清楚的做事方法。把这一层写进 Markdown，再把动作交给 MCP，这可能才是更像生产系统的 agent 架构。

## 参考

- [The case for running AI agents on Markdown files instead of MCP servers](https://thenewstack.io/skills-vs-mcp-agent-architecture/) — The New Stack
- [CompanyOS](https://adventuresinclaude.ai/posts/2026-02-21-running-a-company-on-markdown-files/) — Brad Feld
- [MCP, Skills, and Agents](https://cra.mr/mcp-skills-and-agents/) — David Cramer
- [Supabase agent-skills repository](https://github.com/supabase-community/agent-skills) — Supabase Community
- [Model Context Protocol](https://modelcontextprotocol.io/) — MCP
