---
pubDatetime: 2026-03-12T13:47:31+00:00
title: "N-Layered、Clean、Vertical Slice 到底怎么选：2025 年 .NET 架构取舍，别再站教派"
description: "Anton 这篇架构对比文最有价值的地方，不是再讲一遍概念定义，而是把 N-Layered、Clean Architecture、Vertical Slice Architecture 各自适合什么团队、什么复杂度、什么演进阶段说清楚了。真相通常不是选边站，而是按业务复杂度、团队协作方式和未来演进成本做取舍。"
tags: ["Architecture", ".NET", "Clean Architecture", "Vertical Slice"]
slug: "n-layered-vs-clean-vs-vertical-slice-architecture"
ogImage: "../../assets/599/01-cover.png"
source: "https://antondevtips.com/blog/n-layered-vs-clean-vs-vertical-slice-architecture"
---

![架构取舍概念图](../../assets/599/01-cover.png)

软件架构这事，最容易吵成宗教战争。有人觉得 N-Layered 老土，一看就是 CRUD 年代遗产；有人把 Clean Architecture 当成工程自律的分水岭；还有人一上来就说 Vertical Slice 才是现代团队的答案，谁还在按技术层分目录谁就落后了。

但真到项目里，架构从来不是投票选教主。你最后选的，通常不是“最先进”的那一个，而是**在当前业务复杂度、团队熟练度和演进压力下，最不容易把自己玩死的那一个。**

Anton 这篇文章的价值，就在于它没有停留在教科书式定义，而是把 N-Layered、Clean Architecture、Vertical Slice Architecture 各自会在哪里变顺手，哪里会开始难受，说得比较接地气。尤其在 2025 年这个节点，它还多了一层现实语境：AI 可以帮你更快写代码，但它并不会自动替你选对结构。相反，架构越混，AI 往里一扎，噪音只会更大。

## N-Layered 为什么一直没死，而且短期内也死不了

先说最常见、也最常被嫌弃的 N-Layered。典型长相就是 Controller、Service、Repository、Model 这一套，逻辑按技术职责横着切开。大多数 .NET 开发者一看就懂，这也是它能活这么久的根本原因。

它最大的优点从来都不是“优雅”，而是**低认知门槛**。新同事来了，知道接口放哪，服务放哪，数据访问放哪，几乎不用额外培训就能开始动手。对小团队、小项目、CRUD 比重很高的系统，这种熟悉感非常值钱。

问题也恰恰藏在它的熟悉感里。因为太顺手了，所以大家很容易一路往同一个 Controller、同一个 Service 上叠方法。刚开始只是 `GetById`、`Create`、`Update`、`Delete`，后来就长出各种按用户、按状态、按时间区间、按业务动作的接口。Controller 越长越胖，Service 越来越像一个什么都知道的大总管，Repository 不是太碎，就是开始跨实体乱长。

这类结构一开始看上去很清晰，时间一久就会暴露一个经典问题：**目录是分层了，业务却没有真正被组织起来。** 你想改一个发货功能，得同时在 Controller、Service、Repository、DTO、Mapper 之间来回蹦。每个文件都“各司其职”，但一个用例的完整实现被切得七零八落。

这就是为什么很多团队嘴上没否定 N-Layered，身体却越来越诚实地对它失去耐心。不是它不能做事，而是它对复杂度的耐受性不算高。

## 真正让 N-Layered 难受的，不是项目变大，而是业务关系变复杂

很多人一提架构升级，第一反应是“等项目大了再说”。这话只对一半。

真正把 N-Layered 拖进泥里的，通常不是代码行数，而是跨实体、跨流程、跨状态转换的业务逻辑开始变多。比如一开始你只是查 Shipment、查 Order，看起来一个实体一套 Repository 很合理。可一旦需求变成“查某个订单下的所有发货及其条目，再结合历史状态做判断”，你很快就会开始纠结：这方法到底放 `ShipmentRepository`、`OrderRepository`，还是再建个 service 来拼？

这时候 N-Layered 最常见的两个坏结果会一起出现：

- Repository 越写越胖，开始知道不该知道的别的实体
- Service 变成编排中心，里面全是拼接、协调、状态判断和防重复逻辑

再往后，重复逻辑、N+1 查询、测试困难、边界模糊这些老毛病就都冒出来了。

AI 在这里并没有把问题变小，反而会把它放大。因为 agent 很擅长在“结构已经清楚”的前提下快速补代码，但如果一个用例本身被切碎在很多层里，AI 往往只会更快地把相同模式复制十遍，而不是主动替你修正架构分裂的问题。

所以今天看 N-Layered，最该问的不是“它过不过时”，而是：**你的业务是不是还简单到配得上它的简单。** 如果答案是是，那它完全没问题；如果答案已经不是，那继续硬撑通常会让后面每次改动都更疼。

## Clean Architecture 值钱的地方，是把纪律内建进结构里

Anton 接着讲 Clean Architecture，这部分我基本认同。Clean Architecture 的核心好处，不是名字听起来更高级，而是它天生比 N-Layered 更强调边界和依赖方向。

Domain 放核心业务对象，Application 放用例，Infrastructure 放数据库、缓存、消息队列这类外部实现，Presentation 对接 Web API、gRPC、GraphQL 之类的外界入口。所有依赖尽量往里指，别让核心业务去认识外围实现。

这套东西真正值钱的地方，是它替团队把一些本来靠自觉的工程纪律，提前写进了结构里。你不用每次再争“Controller 能不能直接调 Repository”“某段规则应该放哪层”，因为架构本身已经给了很强的倾向。

对复杂业务域，这种纪律是有生产力的。因为复杂系统最怕的不是多写几个文件，而是边界长期被抹平。今天图快一点，明天借一下 Repository，后天在接口层补一段状态判断，看起来每次都只是“小例外”，一年之后整个系统就会变成没有规则的拼接艺术。

Clean Architecture 在这方面的意义，是让“正确做法”比“偷懒做法”更自然一些。

## 但 Clean 也很容易被写成一套漂亮的样板戏

不过，Clean Architecture 不是自动免疫过度设计。Anton 文里很实在地提到一个点：很多团队后来开始走向更务实的写法，比如直接在 Application 层用 EF Core，而不是再套一层 Repository。

这个争议在 .NET 圈已经聊很多年了，我自己的看法也偏实用派。`DbContext` 本身就已经带着 Repository / Unit of Work 的气质，如果你再为了“分层纯洁”硬包一层空壳 Repository，最后很容易变成对抽象再抽象，写出一堆没有含金量的接口。

这里最重要的不是“绝对不能直接用 EF Core”或者“Repository 一律过时”，而是你要知道自己在换什么：

- 你是为了真正隔离复杂查询和外部依赖而抽象
- 还是只是为了看起来更像标准答案

Anton 这里提到一个现实判断挺关键：多数生产系统不会频繁把数据库从一种范式切到另一种完全不同的存储。如果真的发生了，那通常也不是替换一层 Repository 就能轻松解决的事，而是整个访问模式都得重想。

这类话在 AI 时代更应该多讲一点。因为 AI 非常会生成“看起来像模板最佳实践”的代码，尤其喜欢补接口、补抽象、补中间层。你如果自己对 trade-off 没感觉，很容易让它把系统越写越像教程项目，而不是实际项目。

> Clean Architecture 最怕的，不是层多，而是每一层都显得很正确，但真正的业务复杂度并没有得到更好的表达。

## Rich Domain Model 这件事，AI 越强越不能省

Anton 在 Clean 这部分还讲了一个我觉得特别重要、但很多团队经常略过的点：贫血模型和充血模型。

如果你的实体只是公开属性的大号 DTO，所有规则都散落在 Handler、Service、Controller 甚至 Validator 里，那系统表面上是分层了，真正的业务知识却没有被收拢。谁都可以随便改状态、加条目、改地址，只要编译器不拦，逻辑就能一路漏过去。

而 Rich Domain Model 的思路，是把关键业务规则收回实体自己身上。创建走工厂方法，状态切换走显式行为方法，集合修改带校验，外部不能随便 public set。这样一来，业务约束就不再依赖“每个调用方都记得守规矩”。

这件事今天反而更重要。因为 AI 能很快给你生成一堆 handler、DTO mapping、validation、endpoint glue code，但越是这些胶水代码变便宜，**真正应该珍惜的就越是那些承载业务规则、能防止系统跑偏的核心模型。**

换句话说，AI 改变了外围代码的生产成本，没有改变领域规则需要有稳定归宿这件事。你越依赖 agent，加法越快，越需要一个不会随便被绕过的业务核心。

## Vertical Slice 为什么这几年越看越顺眼

然后就是现在很红的 Vertical Slice Architecture。它的吸引力非常直接：按功能切，不按技术职责切。一个用例相关的 endpoint、handler、validator、mapping、数据访问都尽量放在同一个 slice 里。

这套结构最大的优势不是理论，而是导航体验。你想改 `CreateShipment`，不需要在 `Controllers`、`Services`、`Repositories`、`CommandHandlers`、`DTOs` 来回穿梭，直接进对应 feature 文件夹就能看到一整条链路。对于以需求交付速度为核心的团队，这种组织方式几乎天然讨喜。

Anton 说 VSA 的强项包括 feature-focused、易扩展、低耦合、好维护，这些都成立。尤其是在功能边界比较清晰、不同 feature 复杂度差异又比较大的系统里，Vertical Slice 往往比统一分层更贴近真实开发过程。

因为团队实际接活时，接的从来不是“我要改 Service 层”，而是“我要做用户注册”“我要加发货审核”“我要补退款流程”。VSA 正好把代码组织成接近这种工作方式的样子。

AI 对这种结构也比较友好。因为一个 slice 的上下文更集中，agent 更容易在局部范围内理解完整用例、做出一致改动、减少在多层目录里乱窜的概率。它不一定自动让设计更好，但至少更容易拿到足够清晰的任务边界。

## Vertical Slice 不是银弹，它最大的风险是“每片都挺独立，然后全局慢慢散掉”

当然，VSA 也不是天降神结构。Anton 提到的几个问题也是真问题：可能出现代码重复、跨切关注点需要额外设计、大型系统里 slice 和文件数量会很多。

这里最要命的其实不是“文件多”，而是**如果团队没有共识，Vertical Slice 很容易从 feature 聚合，滑向 feature 各写各的。**

今天这个 slice 用直接 DbContext，明天那个 slice 搞一套 repository，后天另一个 slice 又把 validation、error handling、logging 写成完全不同的姿势。局部看都能跑，全局看像一个技术拼盘。

所以 VSA 真正需要的，不是更少规则，而是更轻但更稳的规则。比如：

- cross-cutting concerns 统一走 middleware / pipeline
- 哪类复杂逻辑要回收进 domain
- 哪些通用查询该提炼，哪些重复是可接受的
- feature folder 的命名和内部组织怎么约定

也就是说，VSA 适合减少“无意义分层跳转”，但它并不等于放弃架构约束。你只是把约束从“技术层边界”更多转向“feature 内聚 + 核心规则一致性”。

## 最靠谱的答案，往往不是三选一，而是 Clean 的骨架加 Vertical Slice 的组织方式

Anton 最后的推荐，是 **Clean Architecture + Vertical Slices**。我觉得这是这篇文章真正有含金量的地方。

因为它不是简单折中，而是把两种结构各自最值钱的部分拼到一起：

- 用 Clean Architecture 保住核心边界、依赖方向和复杂业务的秩序
- 用 Vertical Slice 把 Application / Presentation 这些最常变动的实现，按用例聚在一起，降低导航和开发成本

这种组合特别适合中大型应用、模块化单体、业务规则不轻、团队又希望保持交付速度的场景。Domain 和 Infrastructure 继续承担稳定骨架，具体 feature 则按 slice 组织。你既不会完全回到技术文件夹大散装，也不至于因为追求纯 slice 而把核心规则冲淡。

这基本也是很多成熟团队最后会走到的状态：不是严格信某一种“原教旨架构”，而是经过几轮折腾后，保留真正有复利的约束，去掉只是增加样板代码的部分。

AI 也在把这种趋势推得更明显。因为一旦 agent 能快速补足样板代码，你会更清楚地看到什么结构是在保护复杂度，什么结构只是在制造 ceremony（仪式感）。真正有价值的，是能让人和 AI 都更容易理解系统边界的组织方式。

## 2025 年到底怎么选，别看口号，看四件事

如果把这篇文章翻译成更实用的决策逻辑，我会建议你看四个维度。

### 第一，看业务逻辑到底有多重

如果项目主要是增删改查，规则少，状态流转轻，跨实体协作不复杂，N-Layered 完全够用。你没必要为一个轻系统预付一堆架构税。

如果核心价值来自复杂规则、状态机、约束、权限、跨聚合行为，那就别迷恋简单分层了，Clean 至少该进场，Rich Domain Model 更该认真考虑。

### 第二，看团队是按技术分工，还是按 feature 交付

如果团队天然按功能迭代，每次开发都是围绕一个个用例推进，那 Vertical Slice 会很顺手。因为它让代码结构更贴近团队协作方式。

如果团队还比较依赖传统技术层分工，或者成员对 feature 聚合不熟，那直接硬切 VSA 反而可能先制造混乱。

### 第三，看未来一年是稳定维护，还是持续演进

短生命周期项目、原型、POC、边界很清晰的小系统，别过度设计。反过来，如果系统明显会持续长大、接更多外部系统、不断演化业务边界，那前期结构就值得多花点心思。

### 第四，看你是否准备好和 AI 一起维护这个系统

这条是以前没有、现在越来越该加的维度。架构不只是给人看的，也是在给 agent 喂上下文。

- N-Layered 在简单项目里很容易让 AI 上手
- 但业务一复杂，AI 会在散落的层之间来回复制样板
- Vertical Slice 更利于局部理解和 feature 级修改
- Clean + 清晰边界能减少 agent 乱跨层、乱依赖、乱塞逻辑的概率

所以今天选架构，已经不能只问“人维护起来怎么样”，还得问“AI 介入后会不会把噪音进一步放大”。

## 真正该避免的，不是选错风格，而是选了不适合当前复杂度的纪律成本

Anton 这篇最后给的推荐是：大多数 2025 年的新项目，优先考虑 Clean Architecture + Vertical Slices。我觉得这判断挺稳，但我会补一句：**前提是你的业务复杂度和团队成熟度配得上它。**

别把“更高级的架构”误解成“对所有项目都更好”。对一个 2 人团队、目标明确的 CRUD 后台，你用 N-Layered 很可能是更聪明的决定。对一个准备演进成模块化单体、业务规则越来越重的系统，你还死守最传统的 Controller-Service-Repository，大概率是在给未来埋雷。

架构从来不是身份标签，而是复杂度管理工具。AI 时代这件事只会更明显。因为代码生成越来越便宜，真正贵的东西变成了：边界清不清楚、规则有没有归宿、一个 feature 到底能不能被快速理解和安全修改。

所以真结论可能没有那么戏剧化：

- 小而直白，用 N-Layered，别装复杂
- 业务变重，用 Clean 保纪律
- 追求交付效率，用 Vertical Slice 保内聚
- 又复杂又想快，Clean + Vertical Slice 通常最均衡

这不是站队，这是把架构当工程，而不是当审美。

## 参考

- [N-Layered vs Clean vs Vertical Slice Architecture: Choosing the Right Approach for .NET Projects in 2025](https://antondevtips.com/blog/n-layered-vs-clean-vs-vertical-slice-architecture) — Anton Martyniuk
- [Vertical Slice Architecture — The Best Ways to Structure Your Project](https://antondevtips.com/blog/vertical-slice-architecture-the-best-ways-to-structure-your-project) — Anton Martyniuk
- [Refactoring a Modular Monolith without MediatR in .NET](https://antondevtips.com/blog/refactoring-a-modular-monolith-without-mediatr-in-dotnet) — Anton Martyniuk
