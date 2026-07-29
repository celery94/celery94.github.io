---
pubDatetime: 2026-07-29T12:03:40+08:00
title: "Clean Architecture vs 模块化单体：它们根本不是对手"
description: "在 .NET 架构讨论中，Clean Architecture 和 Modular Monolith 常被当作二选一的对手，但这是一种误解。两者工作在完全不同的抽象层级：一个管内部层次组织，一个管系统边界划分。本文从问题域、作用范围、部署模型到实战组合方式，把两者的区别和协作关系讲清楚。"
tags:
  [
    "Clean Architecture",
    "Modular Monolith",
    "CSharp",
    "Software Architecture",
    ".NET",
  ]
slug: "clean-architecture-vs-modular-monolith-csharp"
ogImage: "../../assets/980/01-cover.png"
source: "https://www.devleader.ca/2026/07/28/clean-architecture-vs-modular-monolith-in-c-whats-the-difference"
---

如果你在 .NET 架构讨论里待过一段时间，大概率听过「Clean Architecture」和「模块化单体」（Modular Monolith）这两个词被交替使用 —— 甚至更糟，被当成互斥的选项。「Clean Architecture vs 模块化单体」这个问题反复出现，而且几乎每次都会导致困惑，因为开发者总是把它框定为二选一。

但实际上它不是。

Nick Cosentino（Dev Leader）在最近的一篇文章里把这个问题拆得非常清楚：**这两种思路工作在完全不同的抽象层级上**，一旦你理解了这层区别，表面上的冲突就自然消解了。

这篇文章来自 Dev Leader，类型是**架构对比分析**。我会按原文结构展开：先分别讲清楚 Clean Architecture 和模块化单体各自解决什么问题，然后解析为什么它们不是竞争关系，最后给出单独使用和组合使用的场景判断。

## Clean Architecture 在 .NET 中是什么？

Clean Architecture 由 Robert C. Martin（Uncle Bob）推广，是一种组织**单个应用或服务内部结构**的方式。核心模型是一组同心圆环：

- **Domain**（最内层）：业务实体、值对象、领域逻辑
- **Application**：用例、应用服务、端口接口
- **Infrastructure**：数据库访问、外部 API、文件系统适配器
- **Presentation**：Controller、gRPC 端点、CLI 处理器

核心约束是**依赖规则**（Dependency Rule）：源代码依赖只能向内。Infrastructure 依赖 Application，Application 依赖 Domain，Domain 不依赖任何东西。你的业务逻辑与框架、数据库和外部关注点完全隔离。

```text
// Clean Architecture 单服务/单应用的文件夹结构
//
// MyApp/
//   MyApp.Domain/
//     Entities/
//       Project.cs             // 领域实体 —— 纯 C#，无框架依赖
//       ProjectStatus.cs       // 值对象或枚举
//
//   MyApp.Application/
//     UseCases/
//       CreateProjectUseCase.cs
//       GetProjectsQuery.cs
//     Interfaces/
//       IProjectRepository.cs  // 端口定义在 Application（而非 Infrastructure）
//     Services/
//       ProjectService.cs
//
//   MyApp.Infrastructure/
//     Persistence/
//       ProjectRepository.cs   // 实现 Application 中定义的 IProjectRepository
//       AppDbContext.cs
//     ExternalServices/
//       EmailNotificationService.cs
//
//   MyApp.Presentation/
//     Controllers/
//       ProjectsController.cs
//     Program.cs
```

注意 `ProjectRepository` 在 Infrastructure 中，实现的是 Application 层定义的接口。Infrastructure 引用了 Application —— 但 Application 不反过来引用 Infrastructure。这就是依赖规则的实际运作。

实际收益是**可测试性和长期灵活性**。你可以不碰领域模型就换掉数据库层，可以不启动真实数据库就测试应用用例。Clean Architecture 让最重要的代码 —— 领域层 —— 易于理解和测试。

设计模式在各层自然集成。比如 Decorator 模式很适合在 Infrastructure 层包装横切关注点（缓存、日志），不修改 Application 层；Factory Method 模式适合在 Domain 层做复杂实体的构造。

## 模块化单体是什么？

模块化单体是一种**系统级部署拓扑**。它是一个单一的可部署单元 —— 一个进程、一个二进制 —— 但功能模块之间有**强制的边界**。每个模块对应领域驱动设计（DDD）中的一个限界上下文（Bounded Context）。

关键词是「强制」。普通单体里，隐式依赖无处不在，任何功能可以引用任何其他功能的代码。模块化单体把这些边界变得**显式**，并从代码层面刻意阻止跨模块耦合 —— 通常通过 C# 的 `internal` 访问修饰符、架构测试，或两者兼用。

每个模块通常拥有：

- 自己的领域模型和业务逻辑
- 自己的数据模型或数据库 schema（通常是一个独立的 `DbContext`）
- 自己的公共契约（通过 Contracts 项目暴露给其他模块）
- 自己的内部实现（对系统其余部分完全不可见）

```text
// 模块化单体项目结构
//
// Solution: MyApp.sln
//
//   Modules/
//     Projects/
//       Projects.Contracts/       // 公共 API —— 其他模块可见
//         IProjectsModule.cs      // 其他模块可以调用的接口
//         ProjectSummaryDto.cs    // 跨模块通信的 DTO
//
//       Projects.Domain/          // internal —— 模块外不可见
//         Project.cs
//         ProjectStatus.cs
//
//       Projects.Application/     // internal —— 模块外不可见
//         CreateProjectUseCase.cs
//         IProjectRepository.cs
//
//       Projects.Infrastructure/  // internal —— 模块外不可见
//         ProjectRepository.cs
//         ProjectsDbContext.cs
//
//     Billing/
//       Billing.Contracts/
//       Billing.Domain/
//       Billing.Application/
//       Billing.Infrastructure/
//
//   Host/
//     MyApp.Api/                  // 薄宿主 —— 把模块串联起来
//       Program.cs
```

`Projects.Domain`、`Projects.Application`、`Projects.Infrastructure` 程序集内部全部使用 `internal` 类。只有 `Projects.Contracts` 被设计为可被其他模块引用。这种硬边界在**编译期**就阻止了意外的跨模块耦合 —— 而不仅仅是靠约定。

最大的好处是：你获得了微服务的许多优势 —— 清晰的所有权、独立的特性演进、缩小变更的爆炸半径 —— **但没有分布式系统的运维开销**。模块间没有网络调用，没有分布式事务，没有 service mesh。

## 关键洞察：两者工作在不同层级

这是大多数开发者在比较这两种方法时忽略的核心问题：**它们回答的是完全不同的问题**。

**Clean Architecture 回答的是**：_如何组织单个边界内的代码？_ 它是关于单个模块或服务内部的层次纪律。它告诉你如何把领域逻辑和数据库关注点分开，如何确保基础设施实现是可替换的。

**模块化单体回答的是**：_如何把系统划分为独立单元？_ 它是关于系统级别的边界纪律。它告诉你一个功能领域在哪里结束、另一个在哪里开始，以及如何防止这些领域随时间推移纠缠在一起。

这就是为什么把它们当成竞争对手完全说不通。Clean Architecture 是一种**内部架构模式**，模块化单体是一种**系统分解策略**。你可以在模块化单体的每个模块内部使用 Clean Architecture，也可以构建一个模块化单体让每个模块内部只用简单的三层结构，不做完整的 port-and-adapter 分离。

**它们是正交的维度 —— 它们组合，而非竞争。**

Onion Architecture 是 Clean Architecture 的近亲，遵循同样的逻辑：Onion 定义了单个单元内部如何分层（Domain 在中心，应用服务在下一环，Infrastructure 在最外层），而模块化单体定义了系统被划分为多少个独立单元。

## 对比一览

| 维度         | Clean Architecture           | 模块化单体                           |
| ------------ | ---------------------------- | ------------------------------------ |
| 解决什么问题 | 单个单元内部的耦合           | 系统级别单元之间的耦合               |
| 作用范围     | 单个项目或服务内部结构       | 多模块系统组织                       |
| 部署模型     | 未指定                       | 单个可部署单元                       |
| 数据库       | 未指定                       | 通常每个模块独立 schema 或 DbContext |
| 核心收益     | 可测试、依赖反转的内部结构   | 独立特性演进，无需微服务复杂度       |
| 核心约束     | 依赖规则 —— 依赖只能向内     | 模块边界强制（internal、测试或工具） |
| 团队适配     | 任何规模团队构建单个内聚服务 | 中大型团队，有明确的特性领域划分     |

## 两者能组合使用吗？

**可以 —— 而且这通常是对严肃生产系统推荐的做法。** Clean Architecture vs 模块化单体的问题不应该是「我该选哪个」，而应该是「我在哪个层级应用哪一个」。

当你把 Clean Architecture 应用到模块化单体的每个模块内部时，你会得到一个：

- **模块边界阻止了跨领域耦合**（模块化单体的贡献）
- **内部层次边界阻止了框架耦合，保持业务逻辑可测试**（Clean Architecture 的贡献）
- **每个模块都可以在需要时独立抽取为微服务**

这种组合有时被称为「具有 Clean 内部的模块化单体」（Modular Monolith with Clean Internals）。对于构建复杂 C# 应用的团队来说，这是架构上的甜点位置 —— 今天拥有微服务就绪的能力，但没有微服务的复杂度。

来看看组合后的实际代码结构。每个模块变成一个微型的 Clean Architecture 系统，拥有自己的 Domain、Application 和 Infrastructure 层 —— 全部隐藏在 Contracts 边界之后：

```csharp
// 组合方案：每个模块内部使用 Clean Architecture
//
// Module: Projects

// ----- Projects.Domain（最内层 —— 无其他层依赖）-----
namespace Projects.Domain;

public sealed class Project
{
    public Guid Id { get; init; }
    public string Name { get; init; }
    public ProjectStatus Status { get; init; }

    private Project(Guid id, string name, ProjectStatus status)
    {
        Id = id;
        Name = name;
        Status = status;
    }

    public static Project Create(string name) =>
        new(Guid.NewGuid(), name, ProjectStatus.Active);

    public Project Archive() =>
        new(Id, Name, ProjectStatus.Archived);
}

public enum ProjectStatus { Active, Archived }

// ----- Projects.Application（只依赖 Domain —— 定义端口）-----
namespace Projects.Application;

using Projects.Domain;

// 端口定义在 Application —— Infrastructure 来实习
public interface IProjectRepository
{
    Task<Project?> GetByIdAsync(
        Guid id, CancellationToken ct = default);
    Task AddAsync(
        Project project, CancellationToken ct = default);
}

public sealed class CreateProjectUseCase
{
    private readonly IProjectRepository _repository;

    public CreateProjectUseCase(IProjectRepository repository)
    {
        _repository = repository;
    }

    public async Task<Guid> ExecuteAsync(
        string name,
        CancellationToken ct = default)
    {
        var project = Project.Create(name);
        await _repository.AddAsync(project, ct);
        return project.Id;
    }
}

// ----- Projects.Infrastructure（适配器 —— 依赖 Application 和 Domain）-----
namespace Projects.Infrastructure;

using Microsoft.EntityFrameworkCore;
using Projects.Application;
using Projects.Domain;

// internal sealed —— 模块外不可见
internal sealed class ProjectRepository : IProjectRepository
{
    private readonly ProjectsDbContext _dbContext;

    public ProjectRepository(ProjectsDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public async Task<Project?> GetByIdAsync(
        Guid id, CancellationToken ct = default) =>
        await _dbContext.Projects
            .FirstOrDefaultAsync(p => p.Id == id, ct);

    public async Task AddAsync(
        Project project, CancellationToken ct = default)
    {
        await _dbContext.Projects.AddAsync(project, ct);
        await _dbContext.SaveChangesAsync(ct);
    }
}

// ----- Projects.Contracts（公共接口 —— 其他模块唯一能看到的东西）-----
namespace Projects.Contracts;

public interface IProjectsModule
{
    Task<Guid> CreateProjectAsync(
        string name,
        CancellationToken ct = default);
}
```

`ProjectRepository` 是 `internal sealed` —— 模块程序集之外的任何代码都不能直接引用它。`IProjectRepository` 端口在 `Projects.Application` 中，也是 internal。只有 `Projects.Contracts` 暴露了公共接口。**这是模块边界在编译期发挥作用，而不仅仅是靠约定。**

Observer 模式在模块边界层面特别有用：一个模块通过共享契约发出领域事件，其他模块订阅并响应，无需直接耦合到发出模块的内部实现。

## 什么时候只用 Clean Architecture，不用模块化单体？

Clean Architecture 不做模块分解是合理的选择，当：

- 你在构建**中小型应用**，只有单个内聚的领域
- 你有一个**小团队**（2-5 个开发者），模块项目的开销不值得
- 你**时间紧迫**，想要可测试的内部结构但不做完整的模块分解
- 业务领域不够复杂，不需要划分明确的限界上下文

这些情况下，单个 Clean Architecture 应用加上组织良好的命名空间，能给你大部分收益 —— 可测试的领域逻辑、可替换的基础设施、依赖反转的层次 —— 而不需要完整模块化的项目结构开销。

## 什么时候只用模块化单体，不用 Clean Architecture？

一个务实的模块化单体 —— 不在每个模块内部严格做 Clean Architecture 分层 —— 在以下情况是合理的：

- 你想要**模块边界纪律**，但领域逻辑很薄 —— 主要是 CRUD，业务复杂性低
- 团队偏好更简单的技术栈，完整的 port-and-adapter 分离带来的摩擦超过了它的收益
- 你在**从遗留的大泥球单体迁移**，正在逐步引入模块边界
- 有些模块目前还看不出 Clean Architecture 分层的价值

这种场景下，每个模块内部可能只是一个简单的三层结构（Domain、Services、Data），不做完整的 Application/Infrastructure 接口抽象。你仍然能获得模块边界的系统级收益 —— 独立数据所有权、编译期边界强制、清晰的团队职责 —— 而不需要到处应用同样水平的内部严格性。

这是一个有效的务实选择。

## 什么时候把两者组合使用？

在 C# 中组合 Clean Architecture 和模块化单体，值得投入的时机是：

- 你有**中大型团队**（6+ 开发者），有明确的特性团队或所有权区域
- 你的**领域确实复杂**，有多个以不同速度演进的限界上下文
- 你想要**微服务就绪**能力 —— 能把模块抽取为独立服务而不需要重写
- 你需要**模块边界层和内部层次层的双重独立可测试性**
- 你在构建一个**长期维护的产品**，架构债务会迅速累积

Nick 说这是他在一个全新产品、领域确实复杂、团队会维护多年的场景下会选择的方案。模块边界保护你不陷入「一切依赖一切」的失败模式 —— 这种模式会杀死大型单体里的生产力。Clean Architecture 的内部结构保护每个模块的业务逻辑不被框架锁定，确保用例保持可测试。

两者合在一起，给你一个**容易修改、容易测试、容易理解的系统** —— 而且在你真正需要微服务之前，不用承担它们的运维成本。

## 常见问题

### 模块化单体和 Clean Architecture 是同一个东西吗？

不是。它们在不同层级解决不同的问题。Clean Architecture 定义如何组织单个单元内的代码 —— 层次、依赖方向、port-and-adapter 分离。模块化单体定义如何将整个系统划分为独立单元，放在单个部署中。你可以只用其中一个，也可以在同一个系统中组合两者。

### Clean Architecture 需要模块化单体结构吗？

不需要。Clean Architecture 纯粹是关于单个应用的内部层次结构。它不关心你的系统有多少个模块、模块之间如何通信、如何部署。你可以把 Clean Architecture 用在一个单项目应用中、一个微服务内部、或者模块化单体的每个模块内部。

### Onion Architecture vs 模块化单体有什么区别？

Onion Architecture 是 Clean Architecture 的变体，使用同样的同心圆模型，Domain 在中心。跟 Clean Architecture 一样，它也是关于单个单元的内部结构 —— 依赖向内、领域与基础设施隔离。模块化单体是关于系统分解为独立的限界上下文。它们工作在不同层级，完全兼容。很多团队在模块化单体结构内部使用 Onion Architecture。

### 模块化单体可以迁移到微服务吗？

可以 —— 这恰恰是模块化单体方法的主要动机之一。因为每个模块已经有清晰的边界、自己的数据模型和公共契约，把它抽取为独立服务是一个**定义良好的操作**，而不是全代码库重写。如果每个模块内部还用了 Clean Architecture，抽取过程会更干净，因为领域和应用逻辑没有框架依赖来增加复杂度。

### 在 C# 中如何强制模块边界？

最实用的方法是 `internal` 访问修饰符加上每个模块一个专门的 `Contracts` 项目。Internal 的类和接口对其他程序集是不可见的，所以跨模块的实现级耦合在编译期就被阻止了。你可以用架构测试库（如 ArchUnitNET 或 NetArchTest）在 CI 中强制边界规则，违规就构建失败。

### 每个模块都应该在内部使用 Clean Architecture 吗？

不一定。正确答案取决于模块的复杂度。一个简单 CRUD 模块、业务逻辑很少，可能从完整的 port-and-adapter 分离中获益不大。一个有复杂领域行为的模块 —— 定价规则、工作流编排、业务不变量 —— 会获益很多。**在领域复杂度值得投入的地方用 Clean Architecture，在不值得的地方用更简单的内部结构。**

### 模块化单体和分层单体有什么区别？

传统的分层单体（Presentation → Business Logic → Data Access）按技术关注点组织代码，所有特性共享同样的层次。模块化单体按业务领域优先组织代码 —— 每个模块有自己的层次、自己的数据访问、自己的领域模型。分层单体在系统中产生**横向耦合**，跨越所有功能。模块化单体在每个功能领域内产生**纵向内聚**，让每个功能独立可变。

## 总结

Clean Architecture vs 模块化单体这个话题，本质上是**一个被错误框定的选择**。

Clean Architecture 告诉你**如何在边界内部组织代码** —— 层次、依赖反转、port-and-adapter 纪律。模块化单体告诉你**首先在哪里画边界** —— 系统有多少个模块、它们如何通信、如何保持彼此解耦。

对于只有单个内聚领域的小型应用，单独用 Clean Architecture 就能给你可测试、可维护的内部结构，不需要不必要的结构开销。对于复杂领域、有明确所有权区域的中大型团队，模块化单体给你边界纪律，防止代码库被自己的重量压垮。当你把两者组合起来，你获得的是两个方向上的最佳实践：模块结构带来的系统级隔离，以及 Clean Architecture 带来的内部层次纪律。

**这种组合 —— 每个模块内部具有 Clean 结构的模块化单体 —— 是你在做需要长期维护的项目时，值得追求的架构配置。**

选择匹配你实际所解决问题的模式就好。当领域足够复杂、团队足够大时，不要犹豫同时拿起两者。

## 参考

- [原文：Clean Architecture vs Modular Monolith in C#: What's the Difference? — Dev Leader](https://www.devleader.ca/2026/07/28/clean-architecture-vs-modular-monolith-in-c-whats-the-difference)
- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Domain-Driven Design by Eric Evans](https://www.domainlanguage.com/ddd/)
- [NetArchTest — Architecture Tests for .NET](https://github.com/BenMorris/NetArchTest)
- [ArchUnitNET](https://github.com/TNG/ArchUnitNET)
