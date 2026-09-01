---
pubDatetime: 2026-09-01T11:20:00+08:00
title: "Specification、Repository 怎么区分"
description: "Specification、Repository 与 Query Object 在 .NET 里各回答什么问题？本文用接口草图、职责表和选型矩阵讲清三者的边界，并拆解常见误用：把查询包当规格、用规格做授权或校验、一有规则就上规则引擎。"
tags: ["C#", ".NET", "设计模式", "架构"]
slug: "specification-vs-repository-vs-query-object"
ogImage: "../../assets/1048/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/29/specification-vs-repository-vs-query-object-in-net"
---

项目里引入 `ISpecification<T>` 之后，最常见的问题是：「既然有了 Specification，Repository 是不是可以不要了？」反过来的声音也有：Repository 到底该不该接收规格，还是把查询直接放进专门的类里。

Nick Cosentino（Dev Leader）2026 年 8 月 29 日的这篇文章给出了一条干净的判定标准：**这三个名字不是竞争关系，它们回答三个不同的问题**。Specification 命名判据，Repository 中介对持久化对象的访问，Query Object 表达一次数据库查询。它们能协作，但谁替代不了谁。

本文以该文为底，保留全部接口草图和对比表，并补上三处针对易混点的解释和一份「三问自检」。先记住开场结论，再逐层确认你的项目属于哪一种情况。

## 先看每个抽象回答什么问题

三个词都来自 Fowler 与 Evans 的经典描述，职责各不相同：

| 抽象          | 核心问题                             | 典型输出                       | 自然归属               |
| ------------- | ------------------------------------ | ------------------------------ | ---------------------- |
| Specification | 候选对象是否满足命名的条件？         | bool、谓词或判据表达式         | 领域或应用层代码       |
| Repository    | 应用如何通过受控边界访问持久化对象？ | 实体、投影、计数或操作结果     | 应用接口背后的基础设施 |
| Query Object  | 这个用例对应什么样的数据库查询？     | 投影结果、分页、标量或查询模型 | 应用层或数据访问代码   |

历史版本的 Specification 是封装后的谓词：某个条件成立与否，可能用于选择、校验性检查，或描述「要构建什么」。Repository 的职责在 Fowler 的描述里很明确：通过集合风格的接口在领域层与数据映射层之间做中介，客户端可以提交判据（包括 Specification），但持久化访问由 Repository 把守。Query Object 则更窄：它代表一条数据库查询，把面向对象的判据翻译成查询语言，存在的理由就是拉数据，不承载「领域真理」。

一个容易踩的点：现代库常常把完整的查询包（判据、排序、include、投影、分页、跟踪标志、标签）也叫作 Specification。这是合法的包内术语——但架构上它的行为更像「命名查询描述」，而不是历史上那个纯谓词模式。**类名叫 Specification 不代表它就是业务规则。**

## 接口草图：边界一眼可见

不需要框架就能看清差别。以下只是草图，不是实现规范：

```csharp
public interface IDomainSpecification<in T>
{
    bool IsSatisfiedBy(T candidate);
}

public interface IExpressionSpecification<T>
{
    Expression<Func<T, bool>> Criteria { get; }
}

public interface IRepository<T> where T : class
{
    Task<T?> GetByIdAsync(Guid id, CancellationToken cancellationToken);

    Task<IReadOnlyList<T>> ListAsync(
        IExpressionSpecification<T> specification,
        CancellationToken cancellationToken);
}
```

Specification 携带判据，Repository 接受判据并控制执行。没有任何接口规定「所有查询必须走 Repository」，也没有规定 Specification 必须知道数据怎么存。

Query Object 则可以独占一个用例形状的结果：

```csharp
public interface IQueryObject<TResult>
{
    Task<TResult> ExecuteAsync(CancellationToken cancellationToken);
}

public sealed record CustomerSummary(Guid Id, string DisplayName);

public sealed record CustomerSummaryPage(
    IReadOnlyList<CustomerSummary> Items,
    int TotalCount);
```

这种形状换来不同的取舍：查询契约直接表达调用方需要的结果，不再假装每次取数都是对领域实体做集合操作。分页、排序、分组、投影都是这个用例的一部分，它们不该被隐藏进一个泛型 `ListAsync(ISpecification<T>)` 的隐含约定里。

## Specification vs Repository：把判据和执行分开

区分 Specification 和 Repository 的关键，是**把判据与执行分离**。

纯 Specification 可以直接在内存里对对象求值；表达式版 Specification 把判据暴露给数据提供方检查。两种情况下它的中心含义都是「这些条件定义了一次匹配」。Repository 则协调对持久化对象的访问：应用 Specification、追加强制租户约束、物化结果、保存变更，或暴露用例专用方法。Repository 边界同样是你阻止调用方依赖 Provider 特有 `IQueryable<T>` 行为的地方。

该怎么侧重：

| 侧重                                | 好处                                                   | 成本与风险                       |
| ----------------------------------- | ------------------------------------------------------ | -------------------------------- |
| 只用 Specification，不要 Repository | 命名规则可复用，直连数据访问已经合适时不必加持久化门面 | 执行策略仍由调用方或别的服务负责 |
| Repository 接收 Specification       | 集中持久化访问，把 Provider 执行留在接口后面           | 容易变成方法薄弱的通用大杂烩     |
| Repository 暴露用例专用方法         | 重要操作可发现，查询行为受约束                         | 方法变多，接口维护成本上升       |

其中第二行最值得警惕：应用需要大量互不相关的投影和结果形状时，`ListAsync(ISpecification<T>)` 会积累 include、分页、跟踪、授权等隐性约定。到这一步，用例专用的 Query Object 反而表达得更清楚。

## Specification vs Query Object：判据还是结果形状

两者重叠的地方是都包含过滤判据，意图不同。Specification 在判据有稳定的领域名字时最强：账号满足续费资格、订单需要人工复核、候选落在搜索边界内——这条规则可能被多个决策复用。Query Object 在「这次取数操作本身」是概念时最强：加载账号看板、返回分页支持队列、算月度汇总——投影、排序、分组、分页和数据库相关的选择经常就是用例本身。

| 设计信号                             | Specification              | Query Object   |
| ------------------------------------ | -------------------------- | -------------- |
| 命名的布尔条件才是主要概念           | 强契合                     | 可能，但更宽泛 |
| 精确结果形状才是主要概念             | 有限契合                   | 强契合         |
| 需要在内存领域决策中复用             | 强契合                     | 弱契合         |
| join、分组、投影、分页定义了整个操作 | 查询包能承载，但含义被撑大 | 天然契合       |
| 调用方希望收到一个专用结果           | 投影也可以                 | 天然契合       |

现代意义上的「查询规格」可以合理描述为一种专门的 Query Object。标签没有诚实契约重要：如果对象携带查询塑形状态，就把它当作查询描述来建档，不要因为类名里有 Specification 就把它宣传成纯业务规则。

## Predicate 不等于 Specification

.NET 里的 `Predicate<T>` 是返回 Boolean 的委托，`customer => customer.IsActive` 是谓词。Specification 在谓词之外增加了**身份与意图**：`ActiveCustomerSpecification` 给条件一个名字、一个可复用的类型，以及领域测试的落脚点，还可能支持组合或描述性元数据。

但这份额外结构不是自动有价值的。谓词只出现一次、语境中含义明显、没有独立业务意义时，内联 lambda 更清楚——给每个 `Where` 子句建一个类，制造的是仪式感而不是更好的设计。**命名与复用得偿所失时才用 Specification，条件局部且简单时就用普通谓词。**

顺便澄清一个常见误解：**Specification 不是 GoF（Gang of Four）23 个设计模式之一**。1994 年的那本书收录创建型、结构型和行为型模式，Specification 不在其中；它的谱系来自领域驱动设计与企业应用架构，包括 Evans 与 Fowler 的材料。之所以总被混淆，是因为 Specification 的实现内部常常用 GoF 模式：[Composite](https://www.devleader.ca/2026/04/02/composite-design-pattern-in-c-complete-guide-with-examples) 表达 AND/OR/NOT 判据树，[Strategy](https://www.devleader.ca/2026/03/02/strategy-design-pattern-in-c-complete-guide-with-examples) 切换判据的求值或翻译算法。用 GoF 模式实现另一个设计的局部，不会把那个设计加进 GoF 目录。

## 三种常见混点：校验、授权、规则引擎

规格模式之后总连着三件事，恰好是三个把「布尔规则」和「更大系统」混在一起的坑。

### 校验：布尔规则不是校验系统

历史文献把校验列为 Specification 的用途之一，但一个 Boolean 规则不等于完整校验系统。真实校验常常还需要：稳定的错误码、人能读的消息、涉及的字段或领域成员、一次响应里报多个失败、对畸形输入的边界行为。

Microsoft 的领域模型校验指南把聚合不变量保持在领域模型内，并把 Specification 加 Notification 作为进阶方案讨论。这是个有用的分离：Specification 提供可复用的规则谓词，通知或结果适配器提供结构化失败；聚合仍然负责强制合法的状态转换。请求校验是另一条边界——它回答「输入是否齐全、格式是否正确、可否处理」，领域 Specification 不该负责解析传输格式或复刻模型绑定。

### 授权：行过滤不是授权策略

Specification 可以过滤「当前用户似乎相关的记录」，但这不是授权策略。ASP.NET Core 基于策略的授权通过 handler 对用户与（需要时）资源评估 requirement，拥有认证身份、声明、需求、成功与失败这些安全语义。

`document => document.OwnerId == userId` 这样的数据判据支撑行选择，但它本身不能证明当前主体被允许读取、修改、导出或披露该文档。判据可以被漏掉、组合错误或绕过。安全决策需要显式的策略执行和测试，且测试不能依赖「恰好先调了某次 Repository 或 Specification 调用」。

### 规则引擎：更大问题的答案

Specification 通常是代码中的确定性判据；规则引擎解决更广的运行模型。Microsoft RulesEngine 官方文档描述的是：工作流、多输入、作用域参数、结果树、动作，以及通过外部配置提供的规则——这些能力支持「规则由外部编写、存储、分组、求值并通过运行时执行行动」的场景。

| 需求                 | Specification  | 规则引擎             |
| -------------------- | -------------- | -------------------- |
| 代码里的小型命名谓词 | 强契合         | 通常过度             |
| 领域决策中的布尔复用 | 强契合         | 可能                 |
| 外部规则配置         | 非固有         | 强契合               |
| 工作流与动作执行     | 保持分离       | 引擎模型支持         |
| 跨多规则的丰富结果树 | 需要单独适配器 | 自然能力             |
| 规则变更的运营治理   | 应用自身责任   | 常是平台设计的一部分 |

不要因为有了几个 Specification 就搬进规则引擎——额外的运行时、配置、可观测性和治理成本是真实的。反之，当外部编写和流程执行是实际需求时，也别把一组布尔对象硬撑成自研规则平台。

## 选型矩阵：按职责而不是按模式数量

最终决策总是从**主导职责**开始：

| 情况                             | 倾向                       | 为什么                              |
| -------------------------------- | -------------------------- | ----------------------------------- |
| 一个局部、读起来清楚的过滤条件   | 内联谓词                   | 名字和类几乎没有增量价值            |
| 可复用的领域条件                 | 纯 Specification           | 规则获得身份，且不耦合持久化        |
| 可复用、需要 Provider 检查的判据 | 表达式 Specification       | Provider 能检查表达式               |
| 对领域对象的受控持久化边界       | Repository                 | 访问与物化留在集合风格契约后面      |
| 用例专用投影、分组或分页         | Query Object               | 操作与结果形状是显式的              |
| 结构化的领域规则失败             | Specification 加结果适配器 | 布尔规则与失败报告保持分离          |
| 用户/资源访问决策                | 授权策略                   | 安全语义属于 requirement 与 handler |
| 外部配置的工作流与动作           | 规则引擎                   | 问题超出了代码级谓词                |

再配合「三问自检」：**什么需要名字**（判据会跨用例复用吗）、**什么需要执行**（谁控制持久化访问和物化）、**什么需要边界**（授权、校验、规则治理各自独立）。三问回答完毕，抽象自然浮出来。

没有普适赢家。取舍是「清晰」对「仪式感」：每个抽象应该消除它负责的那份歧义；如果只是把一句短表达式挪到另一个文件里，它就没有赚到更多。

（针对文首问题的一句直接回答：Repository 可以执行 Specification——Fowler 的 Repository 原文明确允许把声明式查询规格提交给 Repository，规格提供判据，Repository 控制持久化访问与执行。反过来，不用 Repository 也没问题：纯 Specification 内存求值、表达式 Specification 由应用或数据访问代码直接应用，Repository 本身是独立架构选择。）

Aide Hub 会继续分享 .NET 软件工程与架构实践——把模式讲清楚，把边界画出来，少一点「哪个更强」的争论，多一点「这里该归于谁」的判断。

## 参考

- 《[Specification vs Repository vs Query Object in .NET](https://www.devleader.ca/2026/08/29/specification-vs-repository-vs-query-object-in-net)》，Nick Cosentino，2026-08-29（本文原文）
- Fowler：[Specification（Evans & Fowler）](https://martinfowler.com/apsupp/spec.pdf)
- Fowler：[Repository](https://martinfowler.com/eaaCatalog/repository.html)
- Fowler：[Query Object](https://martinfowler.com/eaaCatalog/queryObject.html)
- Microsoft Docs：[Predicate<T>](https://learn.microsoft.com/en-us/dotnet/api/system.predicate-1?view=net-10.0)
- Microsoft Docs：[领域模型层验证](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/domain-model-layer-validations)
- Microsoft Docs：[ASP.NET Core 基于策略的授权](https://learn.microsoft.com/en-us/aspnet/core/security/authorization/policies?view=aspnetcore-10.0)
- Microsoft：[RulesEngine 官方文档](https://microsoft.github.io/RulesEngine/)
- Dev Leader：[Strategy 设计模式完整指南](https://www.devleader.ca/2026/03/02/strategy-design-pattern-in-c-complete-guide-with-examples)
- Dev Leader：[Composite 设计模式完整指南](https://www.devleader.ca/2026/04/02/composite-design-pattern-in-c-complete-guide-with-examples)
- 《[Design Patterns](https://www.informit.com/store/design-patterns-elements-of-reusable-object-oriented-9780201633610)》出版方页面（GoF 1994 目录）
