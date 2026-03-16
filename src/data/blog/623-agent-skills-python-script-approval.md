---
pubDatetime: 2026-03-16T01:28:11+00:00
title: "Microsoft Agent Framework 的 Agent Skills 在 Python 里更新了什么"
description: "Microsoft 这篇更新最值得看的，不是又多了几个 API 名字，而是 Agent Skills 终于从“可读取的技能包”往“可执行、可审批、可动态生成内容的能力单元”走了一步。对 Python 开发者来说，这次新增的 code-defined skills、script execution 和 human approval，补上的不是花哨功能，而是把技能系统往真实生产环境推近的那几块关键拼图。"
tags: ["AI", "Python", "Agent Skills", "Microsoft Agent Framework"]
slug: "agent-skills-python-script-approval"
ogImage: "../../assets/623/01-cover.png"
source: "https://devblogs.microsoft.com/agent-framework/whats-new-in-agent-skills-code-skills-script-execution-and-approval-for-python"
---

![Python Agent Skills 与脚本审批概念图](../../assets/623/01-cover.png)

Agent Skills 这个方向一直有个很实际的问题：如果技能只是一些能被 agent 读取的说明文件，它当然有用，但能力边界也很快会碰到天花板。你可以把知识、规范、流程塞进去，却很难让它和真实系统状态发生更深的连接，更别说安全地触发动作。

Microsoft 这篇更新的价值，就在于它把 Python 版 Agent Framework 的技能能力往前推了一步。新增的几件事看起来分散，实际上是同一个方向上的连续补强：**技能不再只是静态说明目录，而开始变成可代码定义、可动态取数、可执行脚本、还能接入人工审批的能力单元。**

这不是“功能更多了”这么简单。对做 agent 系统的人来说，这一步意味着 skills 终于开始像一个真正可落地的工程接口，而不是只适合做 prompt 附件的知识容器。

## 这次更新最核心的变化，是 skill 终于不必只能活在文件夹里

文章一开头讲的 code-defined skills，其实击中的就是原来 file-based skills 的一个天然限制。

之前的技能模型很适合做那种可分享、可落盘、可随项目一起分发的静态能力包：一个目录，带上 `SKILL.md` 和若干资源文件，agent 需要时去加载。这个模式没问题，而且很适合团队协作和知识复用。

但现实里并不是所有 skill 都天然长成一个目录。有些技能内容来自数据库，有些说明本来就应该跟应用代码一起演化，还有些资源在读取时就需要执行逻辑，不能只靠静态文本提前写死。

这就是 code-defined skills 的意义。你可以直接在 Python 代码里创建 `Skill` 实例，定义名称、描述、内容和资源，而不用先落到文件系统。这个变化看起来朴素，实际非常重要，因为它把 skill 从“磁盘上的包”变成了“程序里的对象”。

这意味着几件事一下子顺了很多：

- skill 可以和应用本身的配置、环境、数据库更自然地连起来
- skill 的定义能跟业务代码一起版本化和测试
- 动态生成的知识不必再硬塞回静态文件结构

对于真正要把 agent 塞进系统里的团队来说，这种灵活性比“多一个装饰器”值钱得多。

## 动态资源补上的，是 agent 最容易缺的那块“活信息”

这次我觉得另一个很关键的点，是资源不再只能是静态文本，而可以通过 `@skill.resource` 在读取时现算。

这听起来像个实现细节，其实很像 skill 体系走向实用化的一道分水岭。因为很多 agent 系统的问题，不是不会说，而是**上下文经常是过期的**。

如果一个 skill 讲的是团队规范、环境配置、项目状态、值班名单、内部策略，这些信息往往都不适合靠人手维护一份静态副本。静态 copy 最大的问题不是写起来麻烦，而是它一旦过期，agent 就会带着过时上下文一本正经地胡说。

动态资源把这个问题缓和了很多。你可以在资源读取时去拿环境变量、查数据库、调内部 API，把最新状态组织成 skill 资源再交给 agent。这样一来，skill 还是 skill，但它承载的就不只是“知识”，而是“带时效性的系统上下文”。

这点放在今天的 agent 语境里特别重要。很多团队已经不缺 prompt 了，真正缺的是**稳定、可控、实时的上下文入口**。动态资源正好补的是这个口子。

## script execution 让 skill 从“会告诉你怎么做”变成“能真的做一点事”

如果说 code-defined skills 解决的是定义方式，dynamic resources 解决的是信息时效，那 script execution 补上的就是行动能力。

以前 skill 更像说明书。它可以告诉 agent 某件事应该怎么处理，也可以给一堆相关资料，但真正要触发动作，通常还得靠别的工具链。现在技能本身可以带脚本，而且 agent 能通过 `run_skill_script` 去执行它们。

这里 Microsoft 做了一个挺清楚的区分：

- **代码定义的脚本**，直接在进程内作为函数调用
- **文件型脚本**，由你提供 `SkillScriptRunner`，自己控制怎么执行

这个设计很合理。因为“让脚本能运行”不是难点，难点在于**把执行权交出去时，边界由谁来控**。

内嵌函数适合轻量、确定、可测试的逻辑，比如单位换算、结构转换、校验规则这种纯函数式任务。它们不需要外部执行器，直接跑就行。

文件型脚本就不一样了。它更像把 skill 和实际运行环境打通，这时候 subprocess 怎么起、沙箱怎么做、权限给多少、输出怎么收、日志怎么打，都不能交给框架替你脑补。Microsoft 这篇文章也很老实，直接说示例 runner 只是演示，生产环境必须自己补沙箱、资源限制、参数校验和审计。

这点我挺认同。**agent 能执行脚本，不代表框架应该替你决定安全边界。** 把执行能力开放出来，同时把控制权留给应用侧，这才是更像工程产品的做法。

## human approval 不是拖慢 agent，而是在关键地方把责任链接回来

很多 agent 产品一说到 approval，就容易讲成“为了安全，我们不得不加一个确认框”。但这篇更新里，我觉得 approval 的意义更像是：**当 skill 开始具备可执行能力，系统必须有办法把最终决定权接回人手里。**

Python 版现在可以通过 `require_script_approval=True` 把所有脚本执行都挂到人工审批后面。agent 想执行时，不会直接动手，而是先返回 approval request，让应用自己决定批不批。

这套模式最值得肯定的地方，是它没有把“审批”做成框架里的装饰性概念，而是做成了工作流的一部分：

- agent 发起脚本执行请求
- 应用层拿到函数名和参数
- 人或上层系统决定批准还是拒绝
- agent 再根据批准结果继续往下走

这样一来，approval 就不只是一个 yes/no 开关，而是 agent loop 里的一个显式节点。它很适合那些真正有副作用的动作，比如部署、配置变更、生产环境操作、批量数据处理。

这也正是今天很多 agent 系统最该认真补上的一课：**自动化能力越强，审批和审计越不能停留在“回头查日志”层面。** 最稳妥的办法，是在动作发生之前就让责任边界清楚可见。

## 这次更新真正把 Agent Skills 往“生产可用”推近了一截

把这几个功能放在一起看，你会发现它们不是零散增强，而是在把 skills 从知识层推向执行层：

- code-defined skills 让 skill 更容易嵌进应用代码和运行时环境
- dynamic resources 让 skill 能提供最新上下文，而不是静态副本
- script execution 让 skill 可以直接承载动作能力
- approval 让这些动作在关键场景下仍然受人类控制

这套组合最有意思的地方，是它比“多几个工具调用”更进一步。它开始把 **知识、上下文、执行、治理** 放进同一个 skill 抽象里。

如果这个方向继续走下去，skills 就不会只是“给 agent 加专业知识”的包装，而会慢慢变成一种很像插件接口的能力边界：既能教 agent 怎么理解领域问题，也能给它有限而受控的行动入口。

## AI 已经让 agent 更会动手，但真正稀缺的是受控动手

放在更大的 AI 工程语境里，这篇更新也很有代表性。现在很多框架都在往“agent 更能干”这个方向狂奔，但真正到了企业环境，大家最关心的往往不是“它能不能做”，而是：

- 它做这件事前读到的上下文是不是最新的
- 它执行时有没有被限制在正确边界里
- 它的动作有没有人能批准、拒绝和追溯
- 这套能力能不能随着应用代码一起维护，而不是散落在神秘配置里

Microsoft 这次给 Python Agent Skills 补的，恰恰就是这些现实问题的接口。它没有试图用一个“超强 autonomous agent”故事把一切包圆，而是很务实地把技能系统往真实部署条件下推进了一步。

这比单纯再秀一轮 agent demo 有价值得多。因为真正能进生产的，不是最会表演的 agent，而是**最能被约束、被审计、被嵌入现有工程体系的 agent**。

## 对 Python 开发者来说，最值得带走的判断

如果你已经在看 Microsoft Agent Framework，这篇更新最该记住的不是 API 细节，而是技能系统的角色变了。

它不再只是让 agent 多读几份说明文档，而是在往一个更完整的能力单元演化：能定义、能取数、能执行、能审批。对于需要把 agent 接进内部系统、运维流程、数据校验、业务工作流的团队来说，这个方向是对的。

当然，这不代表你应该立刻把所有动作都塞进 skill script 里。真正成熟的做法，还是先分清楚哪些逻辑适合做成 skill，哪些动作必须审批，哪些脚本必须沙箱化，哪些上下文应该动态读取。

但至少现在，Python 版 Agent Framework 已经把这些事情需要的基础钩子给出来了。剩下的问题不再是“框架支不支持”，而是你准备怎么把它接进自己的工程纪律里。

## 参考

- [What’s New in Agent Skills: Code Skills, Script Execution, and Approval for Python](https://devblogs.microsoft.com/agent-framework/whats-new-in-agent-skills-code-skills-script-execution-and-approval-for-python/) — Microsoft DevBlogs
- [Agent Skills documentation on Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/agents/skills) — Microsoft Learn
- [Python samples on GitHub](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/skills) — Microsoft Agent Framework
