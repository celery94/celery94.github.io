---
pubDatetime: 2026-07-03T10:11:56+08:00
title: "Claude Code 提示词库：覆盖 .NET 开发全流程的 11 条提示词"
description: "一份针对 .NET 开发者的 Claude Code 提示词库，覆盖从需求头脑风暴到现代化审计的 11 个阶段。每条提示词都带禁止项指令，帮你减少 AI 生成不是你想要的代码。可直接复制使用。"
tags:
  [
    "Claude Code",
    "Prompt-Engineering",
    ".NET",
    "AI-Coding-Assistant",
    "Developer-Productivity",
  ]
slug: "claude-code-prompts-dotnet-copy-paste-library"
ogImage: "../../assets/924/01-cover.png"
source: "https://codewithmukesh.com/blog/claude-code-prompts-dotnet/"
---

Mukesh Murugan 在真实 .NET 10 项目上反复打磨了一套 Claude Code 提示词，覆盖了从第一个想法到季度审计的完整开发流程。这些提示词有两个特点：每条都有"禁止项"指令，而且可以直接复制到终端里用。

作者把提示词理论写在了[提示工程指南](/blog/prompt-engineering-claude-code-dotnet/)里，本文是实践篇。他按工作流阶段整理了 11 条提示词，每条都遵循同样的结构：上下文、任务、约束、禁止项、验证。

## 为什么提示词需要"禁止项"

一条够用的 Claude Code 提示词有五个部分：**上下文**（先读什么）、**任务**（产出什么）、**约束**（版本和约定）、**禁止项**（不要做什么）、**验证**（怎么证明做对了）。缺任何一块，产出可能编译通过，但不是你想要的。

禁止项尤其重要。Claude 在 .NET 场景里的失败模式很少是"不知道"，更多是"太主动"。不加约束时，它会走统计上最常见的那条路：Swashbuckle 而不是 Scalar、在 EF Core 上面再套一层 Repository、为两个字段的映射装上 AutoMapper、每个端点都塞 try/catch。这些做法本身没错，但在你的代码库里就是错的。

一条"不要 XXX"的指令能在代码生成前就把默认路径堵上，比生成后再审查、再撤销省事得多。Anthropic 的[最佳实践文档](https://www.anthropic.com/engineering/claude-code-best-practices)也强调了这个点：有明确目标和约束的具体指令能显著提升首次成功率。

还有一个容易被忽略的细节：**禁止项最好带着它的正向替身一起出现**。比如"不要加 Swashbuckle，只使用 Scalar"。禁令堵住默认路径，正向部分告诉 Claude 该往哪走。只禁不给替代，等于让模型自行发挥。

下面所有提示词里的 `<尖括号>` 都是占位符，用之前替换掉。

## 阶段 1：需求头脑风暴

作者说他每个跳过思考直接写代码的项目，到第三周都还了债。这个提示词逼着你先把对话聊透。它和 [Plan Mode](/blog/plan-mode-claude-code/) 天然搭配——Plan Mode 会阻止 Claude 在思考阶段碰文件。

```
我要构建：<用一句话描述功能或应用>。
进入 Plan Mode。在你提出任何方案之前，先向我提问：用户是谁、规模多大、有哪些已有系统、有什么约束条件。
等我的回答。然后给出候选方案，包括各方案的诚实取舍分析，以及你自己会选哪一个。

规则：
- 不要写代码或创建文件。
- 不要假设这是全新项目。先问清楚已有系统。
- 不要为了凑数列出你根本不推荐的方案。
- 不要默认同意我的判断。如果简化版能交付 80% 的价值，你要据理力争。
```

最后一条规则是作者拒绝删掉的——一个永远同意的助手只是橡皮图章，不是合作者。

## 阶段 2：技术调研（拒绝过时答案）

Claude 的训练数据有截止日期，NuGet 没有。任何"XX 场景下最好的库是什么"的提示词，如果不强制验证，Claude 会给出关于 6 到 18 个月前版本的自信回答。

```
我需要为 <问题，例如 ASP.NET Core API 的后台任务> 选一个库。

用网页搜索、官方文档和 GitHub 做调研。对每个候选库报告：最新稳定版本、.NET 10 兼容性、许可证、
最近 12 个月的发布节奏、未解决 issue 的健康状况。
输出一张对比表，然后根据我的场景 <团队规模、部署环境、约束条件> 给出一段推荐。

规则：
- 不要凭记忆引用版本号或功能声明。训练数据本身就是过时的。每个事实都要验证。
- 不要列超过 4 个候选。像高级工程师一样做筛选。
- 不要推荐过去一年没有发布记录的库，除非它确实功能完备，并且要明确说明这一点。
- 如果两个选项难分伯仲，就说难分伯仲。不要硬选赢家。
```

## 阶段 3：选架构

这是大多数开发者不会写的提示词，但它的影响时间最长。关键在于把架构师真正会问的输入喂给 Claude，同时禁掉它最习惯的默认答案。

```
帮我为一个新的 .NET 10 应用选择架构。

应用描述：<一段话描述>。
团队：<人数> 个开发者，<经验水平>。
部署：<单机 / 容器 / 云 PaaS>。
领域：<CRUD 为主 / 复杂业务规则 / 多重集成>。

对比 Vertical Slice Architecture、Clean Architecture 和 Modular Monolith，针对这个应用
做评分：首次交付功能的速度、新人上手成本、可测试性、应对需求变化的弹性。
最后给出一个推荐，附上它对应的目录树。

规则：
- 不要讨论微服务。不在本次决策范围内。
- 不要因为 Clean Architecture 流行就默认选它。根据我的实际需求论证你提出的每一层。
- 不要为我没描述过的问题提前做抽象。
- 不要写代码。只做推理和结构分析。
- 如果我的需求不足以支撑那么多分层，直接说"这属于过度设计"。我要诚实的答案，不要漂亮的答案。
```

如果希望先有一个人类视角的判断做参照，作者在之前写过 [Clean Architecture in .NET](/blog/clean-architecture-dotnet/) 和[什么时候微服务才真的有价值](/blog/when-to-use-microservices/)。

## 阶段 4：脚手架搭建

阶段 1 的审批闸门是整个提示词的精髓。审一个目录树只要 30 秒，审 40 个生成文件要一小时，而且审到后面你会不自觉接受一些不该接受的东西。

```
为 <应用名> 搭建基础方案，使用我们确定的架构：<vertical slice / clean architecture / modular monolith>。

技术栈：.NET 10、ASP.NET Core Minimal APIs、EF Core 10、xUnit v3。
解决方案格式：.slnx。API 参考 UI：Scalar，通过 AddOpenApi() 和 MapScalarApiReference() 实现。

步骤：
1. 先给我看完整的目录树。停下，等我审批。
2. 用 dotnet CLI 创建项目，配置引用关系，在 Directory.Build.props 中启用 Nullable 和 TreatWarningsAsErrors。
3. 只加一个 health endpoint。其他什么都不要。
4. 运行 dotnet build 并给我看输出。

规则：
- 不要加 Swashbuckle 或 Swagger UI。只用 Scalar。
- 不要加 MediatR、AutoMapper 或 Repository 层。模式按功能需求决定，不预装。
- 不要创建 WeatherForecast 或任何示例实体。
- 除非经过我同意，不要安装技术栈之外的任何包。
```

## 阶段 5：横切关注点一次性搞定

异常处理、日志和验证影响到每一个请求，所以作者在脚手架搭好后一次性配好，并且提示词里要指名具体原语。模糊版本（"加错误处理"）的结局就是 try/catch 糊墙。

```
为这个解决方案配置横切关注点。先读 Program 文件和目录结构，确保一切落在合适位置。

1. 全局异常处理：用 IExceptionHandler，返回 RFC 9457 ProblemDetails 响应。
2. Serilog 结构化日志：Development 环境输出到控制台，Production 输出 JSON，启用请求日志中间件。
3. FluentValidation 接入端点管道，验证失败时返回 400 ProblemDetails 并附带字段级错误。
4. 做完后，从 health endpoint 抛一个测试异常，调用它，给我看返回的 ProblemDetails JSON，然后删掉测试代码。

规则：
- 不要在 endpoint 或 handler 里放 try/catch。异常归 IExceptionHandler 管。
- 不要吞掉异常然后返回 200。要大声失败。
- 不要记录请求体、token 或连接字符串。
- 不要自己写 ASP.NET Core 已经内置的中间件。
```

第 4 步是作者在这套提示词里最喜欢的一个模式：让 Claude 自证配置能正常工作，然后自己清理掉测试代码。相关阅读：[全局异常处理](/blog/global-exception-handling-in-aspnet-core/)、[Serilog 结构化日志](/blog/structured-logging-with-serilog-in-aspnet-core/)、[FluentValidation](/blog/fluentvalidation-in-aspnet-core/)。

## 阶段 6：EF Core 数据持久化

EF Core 是 AI 无约束输出伤害最大的地方，因为错误是静默的。`EnsureCreated` 在第一次迁移之前都好好的；忘记 `AsNoTracking` 在性能分析之前都好好的。这个提示词在源头上就把这些坑都禁了。

```
为这个解决方案加入 EF Core 10 持久化，数据库用 PostgreSQL。
先读现有的实体和功能。然后：

1. 创建 DbContext，每个实体一个 IEntityTypeConfiguration 类。不要把所有配置塞进 OnModelCreating。
2. 配置表名，给所有 string 列设 max length，根据代码中可见的查询模式建索引。
3. 添加初始迁移，在接触任何数据库之前，用 dotnet ef migrations script 给我看 SQL。
4. 通过配置文件管理连接字符串。不要硬编码。

规则：
- 不要用 EnsureCreated。迁移是修改 schema 的唯一路径。
- 不要启用懒加载代理。
- 不要从任何公共方法返回 IQueryable。
- 不要省略 CancellationToken。每个异步 EF Core 调用都要接受它。
- 只读查询必须用 AsNoTracking，除非 handler 会修改实体。
```

迁移脚本审查这一步帮作者抓出的错误列类型比任何代码审查都多。如果对 EF Core 查询行为还不太确定，作者的 [EF Core 性能坑](/blog/ef-core-performance-mistakes/) 解释了为什么这些禁止项存在。

## 阶段 7：在已有代码库里加功能

这是作者运行最频繁的提示词，也是它第一个被转成技能的。最关键的一句是"先读最近一个功能目录"——它把你自己的代码库变成了规格。

```
添加一个新功能：<一句话描述，例如"客户可以在订单发货前取消订单">。

在写任何代码之前，先完整读一遍最近的功能目录——endpoint、handler、validator、tests——列出你看到的约定。
严格按照这些约定实现。

然后实现：请求/响应契约、验证、包含真实业务规则的 handler、endpoint 映射、DI 注册。
业务规则：<规则 1>、<规则 2>。
最后写测试，证明每条规则成立。

规则：
- 不要引入新模式、新包或新目录约定。即使你不同意现有约定，也要照做，把反对意见列在末尾。
- 不要碰无关文件。如果有重构冲动，记下来，别动手。
- 不要把业务规则留成 TODO 桩。完整实现它们。
- 除非 dotnet build 和 dotnet test 都通过，否则不要报告完成。
```

对付这个提示词的高风险变体（大重构、框架升级），作者在隔离的 [git worktree](/blog/git-worktrees-claude-code/) 里跑，避免坏掉的 session 污染主工作区。

## 阶段 8：有用的单元测试

让 AI 写"单元测试"，默认产出是覆盖率表演——40 个测试在证明 C# 语言本身还能正常工作。这里的禁止项就是为了消灭这一类测试。

```
为 <类或 handler> 写单元测试。xUnit v3。优先用真实对象和手写 fake；只有在接口确实需要模拟时才上 mocking 库。

覆盖：正常路径、每一条业务规则拒绝场景、审查者会追问的边界情况——空集合、边界值、已取消的 token。
测试命名：Method_Scenario_ExpectedOutcome。

规则：
- 不要测试框架本身。不写"证明 EF Core 能存数据"或"证明 FluentValidation 能校验"的测试。
- 不要断言日志输出或私有状态。只验证可观测行为。
- 测试之间不要共享可变状态。
- 不要把十个断言塞进一个 [Fact]。一个行为一个测试。
- 如果这个类很难测试，停下并告诉我。这是设计气味需要修复，不是 mocking 的拼图游戏。
```

## 阶段 9：用真实数据库做集成测试

EF Core 的 InMemory provider 不是关系型数据库的测试替身——它直接跳过了事务、约束和 SQL 翻译。所以这里第一条禁止项没有商量余地。Testcontainers 在一个用完即弃的 Docker 容器里给你真实的数据库引擎。

```
用 WebApplicationFactory 和 Testcontainers for PostgreSQL 为这个 API 搭建集成测试。

1. 一个共享的 collection fixture：启动 Postgres 容器，运行 EF Core 迁移，暴露配置好的 HttpClient。
2. 每个测试之间通过重置表来实现隔离。不要每个测试启动一个新容器。
3. 为 <endpoint> 写测试：成功场景、校验失败时断言 ProblemDetails 响应体、未授权请求。
4. 运行整套测试，给我看总结。

规则：
- 不要用 EF Core InMemory provider。真实数据库，或者别测。
- 不要通过被测 API 来创建测试数据。直接通过 DbContext 播种。
- 不要只断言状态码。断言响应体。
- 不要留下孤儿容器。fixture 负责完整生命周期。
```

## 阶段 10：接入 Aspire

Aspire 把 docker-compose 文件、硬编码的连接字符串和"我机器上能跑"的入门文档一次性替代了。版本验证规则在这里比任何地方都重要——Aspire 迭代很快，过时的包版本是 Claude 最常犯的 Aspire 错误。

```
为这个解决方案加入 Aspire 编排。

1. 创建 AppHost 和 ServiceDefaults 项目。先在 NuGet 上确认最新的稳定 Aspire 包版本——不要相信记忆。
2. 把 PostgreSQL 作为容器资源移入 AppHost，通过 WithReference 传给 API。
   删掉 appsettings 文件里的连接字符串。
3. 把 ServiceDefaults 接入 API：OpenTelemetry、健康检查、服务发现、弹性处理器。
4. 启动 AppHost，确认 dashboard 上展示了一条命中数据库的 API 请求的 trace。给我看证据。

规则：
- 不要把旧连接字符串作为 fallback 保留。一个数据源。
- 不要加 Docker Compose 或 Kubernetes 清单。Aspire 负责本地编排。
- 不要跳过 dashboard 验证。"能编译"不等于"能工作"。
```

如果对 Aspire 还不熟，[官方 Aspire 文档](https://learn.microsoft.com/en-us/dotnet/aspire/get-started/aspire-overview) 覆盖了基本模型，作者也写过一篇完整教程：[Aspire for .NET Developers](/blog/aspire-for-dotnet-developers-deep-dive/)。

## 阶段 11：现代化审计

作者每季度对长期项目跑一次，也在往老代码库里加大功能之前跑。只报告不改动的约束是它能在日常中随意跑的原因。

```
对照当前 .NET 最佳实践审计这个解决方案。只报告，不改动任何东西。

检查：目标框架、运行 dotnet list package --outdated 的结果（实际执行）、已弃用或已废弃的包、
过时 API 的使用、nullable 注解缺口、sync-over-async 和缺失 CancellationToken 的地方、
以及能真正简化现有代码的 C# 14 特性。

输出一张表：发现项、文件、风险、工作量、建议。然后停下，让我选哪些要修。

规则：
- 不要在这个阶段修任何东西。只报告。
- 不要把风格偏好标记为发现项。能正常工作的惯用代码不是缺陷。
- 不要在没有列出破坏性变更的情况下推荐大版本升级。
- 不要相信训练数据中的"最新"版本。通过 CLI 输出和 nuget.org 验证。
```

## 元规则：重复三次的提示词就该变成技能

这套提示词库用几周之后自然会浮现一个规律：**同一条提示词贴到第三次，它就不再是一条提示词，而是一个技能了。**

技能是把同样的指令放进仓库里的 `SKILL.md` 文件，用斜杠命令调用，和代码一起做版本控制。上面那条加功能的提示词，在作者的项目里变成了 `/feature <描述>`。单元测试的提示词变成了 `/unit-tests <类名>`。粘贴板和技能文件包含的是完全相同的文字——区别在于技能不会漂移，不会从某个陈旧的笔记里复制到一个过时版本，而且每次改进都能在一个地方集中生效。

作者的转换标准很简单：每个项目只跑一次的提示词留在这个库里（头脑风暴、架构选择、脚手架、Aspire 搭建）。每周都跑的提示词变成技能（加功能、单元测试、集成测试、审计）。重复是信号，三次是阈值。

[Claude Code 官方提示词库](https://code.claude.com/docs/en/prompt-library)的结尾也给了同样的建议：一条提示词在你的项目里稳定下来之后，把它保存为技能，整个团队都能用斜杠命令调用。

## 作者的实际使用感受

跑了好几个月真实 .NET 项目之后，作者的排名是：加功能的提示词（阶段 7）产生的总价值最高，因为它跑得最频繁；但架构选择的提示词（阶段 3）每次调用的价值最高。在脚手架之前有一次好的架构讨论，能省掉十次事后的重构。

他观察到一个最常见的错误：开发者把提示词存在某个"死"的地方——笔记应用、wiki 页面、钉住的聊天。提示词就是代码。把一次性提示词放在仓库根目录的 `prompts.md` 里，把重复使用的转成技能，让它们通过 PR 像其他一切一样进化。

还有一个提醒：禁止项是护栏，不是保证。Claude 偶尔还是会迈过一条，尤其是长 session 后期，规则已经滚出最近注意力窗口时。解决方法不是把提示词写得更长，而是把硬规则移到项目的 memory file 里（那里一直加载着），保持 session 提示词短小，而且用审查初级工程师 PR 的标准来看 diff——因为这就是 AI 到目前为止挣到的信任水平。

以下是 11 条提示词的整体速览：

| 阶段          | 目标                       | 最重要的禁止项                 |
| ------------- | -------------------------- | ------------------------------ |
| 1. 头脑风暴   | 候选方案 + 推荐            | 不要默认同意我的判断           |
| 2. 技术调研   | 验证过的对比表             | 不要凭记忆引用版本号           |
| 3. 架构选择   | 一个有说服力的推荐         | 不要默认选 Clean Architecture  |
| 4. 脚手架     | 审批后的目录树，然后建项目 | 不要未经许可安装包             |
| 5. 横切关注点 | 异常、日志、验证           | 不要在 endpoint 里加 try/catch |
| 6. 数据持久化 | DbContext + 审查过的迁移   | 不要用 EnsureCreated           |
| 7. 加功能     | 匹配约定的 vertical slice  | 不要引入新模式                 |
| 8. 单元测试   | 行为测试，命名清晰         | 不要测试框架本身               |
| 9. 集成测试   | Testcontainers 真实数据库  | 不要用 InMemory provider       |
| 10. Aspire    | 编排 + 验证过的 trace      | 不要保留 fallback 连接字符串   |
| 11. 审计      | 发现项表格，不改动         | 不要在这个阶段修任何东西       |

## 提示词出问题时怎么排查

**Claude 装了被你明确禁止的包。** 你的规则很可能埋在一大段文字中间了。把规则列表保持精简（4-6 条），放在提示词末尾——对绝对禁令，再用 settings 里的 deny 规则兜底，让 tool call 本身被拦截。

**Claude 忽略了你代码库的约定。** 你告诉了它要建什么，但没告诉它要先读什么。阶段 7 里那个"先读最近一个功能目录"就是解法：不要假设 Claude 会主动探索。

**它用的版本是过时的。** 这是预期行为，不是 bug。训练数据永远落后于 NuGet。任何涉及包版本的提示词都必须有一条"验证，不要相信记忆"的指令，就像阶段 2、10、11 那样。

**产出太多审不过来。** 你跳过了审批闸门。在大量生成之前加一步"给我看计划，然后停下"，就像阶段 4 在目录树处的审批。审计划便宜，审 40 个文件贵。

**一条提示词在 A 仓库好用，在 B 仓库不好用。** 提示词在补偿缺失的项目上下文。把稳定的规则（技术栈、约定、禁止的包）移到那个仓库的 memory file 里，让 session 提示词只关注任务本身。

## 关键要点

- 每一条可靠的 Claude Code 提示词都有五个部分：上下文、任务、约束、禁止项和验证。
- 禁止项是提示词里含金量最高的几行，因为 Claude 的失败模式是太主动而不是不知道——它会加你没要求的流行方案。
- 强制验证步骤：审过的目录树、迁移 SQL、通过的测试运行、dashboard traces。"能编译"不等于"能工作"。
- 永远不要让 AI 凭记忆引用包版本。每一条调研、脚手架和审计提示词都需要显式的验证指令。
- 同一条提示词贴到第三次，把它转成技能。一次性的留在库里，每周用的变成斜杠命令。

## 总结

这套提示词库的核心不是 11 段文字，而是一套思维框架：在让 AI 干活之前，先想清楚**它不该做什么**。把占位符填上、保留禁止项、加一个自证步骤，你会发现自己花在撤销 AI 热情上的时间大幅减少。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [原文：Claude Code Prompts for .NET Developers - codewithmukesh](https://codewithmukesh.com/blog/claude-code-prompts-dotnet/)
- [Anthropic Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Claude Code Official Prompt Library](https://code.code.com/docs/en/prompt-library)
- [Microsoft EF Core Migrations Overview](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/)
- [Microsoft .NET Aspire Overview](https://learn.microsoft.com/en-us/dotnet/aspire/get-started/aspire-overview)
