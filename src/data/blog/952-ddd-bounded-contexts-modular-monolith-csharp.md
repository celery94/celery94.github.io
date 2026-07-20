---
pubDatetime: 2026-07-21T07:51:06+08:00
title: "DDD 限界上下文在模块化单体中的实践：C# 代码指南"
description: "DDD 理论让人望而生畏，但限界上下文落在模块化单体里其实很自然——每个模块就是一个限界上下文。本文用 C# 项目里实打实的领域实体、集成事件和跨上下文处理器，讲清怎么做、为什么这么做，以及在什么阶段别做过头。"
tags: ["DDD", "限界上下文", "模块化单体", "C#", "领域驱动设计"]
slug: "ddd-bounded-contexts-modular-monolith-csharp"
ogImage: "../../assets/952/01-cover.png"
source: "https://www.devleader.ca/2026/07/18/ddd-and-bounded-contexts-in-a-modular-monolith-with-c-a-practical-guide"
---

DDD 的书翻起来确实不轻松。限界上下文、通用语言、上下文映射……理论堆在一起，很容易让人搁下书问一句：代码怎么写？

好消息是，**DDD 限界上下文在 C# 模块化单体里**，恰恰是 DDD 最自然、最容易落地的那块。你得到核心收益——清晰的业务边界、独立的领域模型、解耦的模块通信——却不用背上微服务的运维成本。

这篇文章不谈大词，直接看一个真实模块化单体项目里的代码：领域实体怎么定义、集成事件怎么设计、跨上下文处理器怎么写。读完你应该能立刻上手，至少知道从哪下手。

## 每个模块就是一个限界上下文

理解 DDD 限界上下文，最直接的办法是：**你项目里的每个模块，就是一个限界上下文**。

这不是类比，是结构规则。以原文项目为例，四个模块精确映射到四个限界上下文：

- `Projects` 模块 → Projects 限界上下文
- `Tasks` 模块 → Tasks 限界上下文
- `Users` 模块 → Users 限界上下文
- `Notifications` 模块 → Notifications 限界上下文

每个模块有自己的 Domain 层，有自己的领域模型。没有两个模块共享一个领域实体。模块的边界，就是上下文的边界。

好处很明显：不用在白板上画概念线，直接在项目结构里画，用 C# 的 `internal` 访问修饰符强制执行。

## 怎么找出你的限界上下文

拆模块之前，先问自己三个问题：

**聚合度**：哪些概念天然在一起？`TaskItem`、`TaskStatus` 和任务分配逻辑应该在一个模块里。用户认证、项目计费不该跟它们挤在一起。

**语言**：系统里哪些部分有自己独特的词汇？如果"任务"这个词在不同代码区指完全不同的数据结构，那些部分就该分到不同上下文。

**归属**：哪个团队或功能域对什么负责？组织边界常常揭示出自然上下文边界。

在原文系统里，Projects 拥有项目及其生命周期（Active、Completed、Cancelled）。Tasks 拥有工作项和分配、完成流程。Users 拥有身份和资料。Notifications 拥有消息投递——它不关心项目和任务的业务规则，只知道"有件事发生了，用户应该知道"。

注意 Notifications 是一个消费型上下文。它只对其他上下文的事件做出反应，不持有那些领域的业务逻辑。这是一个真实的限界上下文——只是比较薄。

## 上下文内部的领域模型

定好限界上下文后，每个上下文拿到自己的领域模型。在 C# 里，这部分代码放在对应模块的 `*.Domain` 项目里。关键规则：**领域实体对它所在的上下文是 `internal` 的**，模块外部不能直接引用它们。

来看 Projects 模块里的 `Project` 实体：

```csharp
namespace Projects.Domain;

internal sealed class Project
{
    public Guid Id { get; private set; }
    public string Name { get; private set; } = string.Empty;
    public string Description { get; private set; } = string.Empty;
    public ProjectStatus Status { get; private set; }
    public DateTime CreatedAt { get; private set; }

    private Project() { }

    public static Project Create(string name, string description)
    {
        if (string.IsNullOrWhiteSpace(name))
            throw new ArgumentException(
                "Project name cannot be empty", nameof(name));

        return new Project
        {
            Id = Guid.NewGuid(),
            Name = name,
            Description = description ?? string.Empty,
            Status = ProjectStatus.Active,
            CreatedAt = DateTime.UtcNow
        };
    }

    public void Complete() => Status = ProjectStatus.Completed;
    public void Cancel() => Status = ProjectStatus.Cancelled;
}
```

几点关键设计：

- 类是 `internal sealed`——`Projects.Domain` 程序集之外谁也用不了。
- 构造函数是私有的，只能通过工厂方法 `Create` 创建。
- 所有 setter 都是 `private`，状态变更必须走 `Complete()`、`Cancel()` 这种显式方法。
- 零框架依赖。没有 EF Core 特性、没有 `[JsonProperty]`、没有 Data Annotations。领域模型和基础设施完全隔开。

再看 Tasks 模块的 `TaskItem`：

```csharp
namespace Tasks.Domain;

internal sealed class TaskItem
{
    public Guid Id { get; private set; }
    public Guid ProjectId { get; private set; }
    public string Title { get; private set; } = string.Empty;
    public string Description { get; private set; } = string.Empty;
    public TaskStatus Status { get; private set; }
    public Guid? AssignedUserId { get; private set; }
    public DateTime CreatedAt { get; private set; }

    private TaskItem() { }

    public static TaskItem Create(
        Guid projectId, string title, string description)
    {
        if (string.IsNullOrWhiteSpace(title))
            throw new ArgumentException(
                "Task title cannot be empty", nameof(title));
        if (projectId == Guid.Empty)
            throw new ArgumentException(
                "Project ID is required", nameof(projectId));

        return new TaskItem
        {
            Id = Guid.NewGuid(),
            ProjectId = projectId,
            Title = title,
            Description = description ?? string.Empty,
            Status = TaskStatus.Todo,
            CreatedAt = DateTime.UtcNow
        };
    }

    public void Assign(Guid userId)
    {
        if (userId == Guid.Empty)
            throw new ArgumentException(
                "User ID is required", nameof(userId));
        AssignedUserId = userId;
        if (Status == TaskStatus.Todo)
            Status = TaskStatus.InProgress;
    }

    public void Complete() => Status = TaskStatus.Completed;
}
```

`TaskItem` 是 `Tasks.Domain` 命名空间里的 `internal sealed`，和 `Project` 完全分开。它们住在不同限界上下文里，不能互相引用。

`Assign` 方法封装了业务规则：分配任务后自动从 `Todo` 切到 `InProgress`。这条规则留在领域对象里，不在 service 或 controller 里。

## 通用语言：每个上下文讲自己的话

同一个词在不同上下文里有不同含义——这事儿太常见了，在业务系统里几乎是必然的，但愿意认真对待它的人不多。

在 Tasks 模块里，"任务"是包含状态、指定人、描述、完整生命周期的富实体。在 Projects 模块里，"任务"可能只是一个数字——"这个项目有 5 个打开任务"——从查询算出来的一个整数，根本不是领域对象。

如果你试图让两个上下文共享一套 `Task` 概念，你会搞出一个臃肿的怪物实体：每个属性都是可选的，每个方法都有别扭的条件分支，一个上下文的需求修改反过来把另一个上下文干碎了。

解法很简单：让每个上下文定义自己的术语。Projects 只需要任务数，它就只跟"数"打交道。Tasks 需要完整实体，它就拿到完整实体。它们不需要在一套 `Task` 类上达成共识。

## 共享内核：Contracts 放什么

既然模块不能引用彼此的领域对象，它们怎么通信？靠 `*.Contracts` 项目。Contracts 是模块间唯一共享的东西——但只放集成事件和 DTO，永远不放领域实体。

`Projects.Contracts` 里的 `ProjectCreatedEvent`：

```csharp
using MediatR;

namespace Projects.Contracts;

public sealed record ProjectCreatedEvent(
    Guid ProjectId,
    string Name,
    string Description) : INotification;
```

`Tasks.Contracts` 里的事件：

```csharp
using MediatR;

namespace Tasks.Contracts;

public sealed record TaskAssignedEvent(
    Guid TaskId,
    Guid ProjectId,
    Guid UserId,
    string TaskTitle) : INotification;

public sealed record TaskCompletedEvent(
    Guid TaskId,
    Guid ProjectId,
    string TaskTitle) : INotification;
```

注意对比：领域实体是 `internal sealed class`，Contracts 是 `public sealed record`。Contracts 故意公开，因为它们要跨上下文边界。但它们不携带行为——只是"发生了什么事"的数据快照。

为什么 contracts 可以携带领域实体的数据但不携带实体本身？因为领域实体有业务逻辑。如果你把 `Tasks.Domain.TaskItem` 传给 Notifications 模块，相当于把 `Assign()` 和 `Complete()` 也塞给了它。Notifications 没有业务理由去调这些方法。更糟的是，你改了 `TaskItem`，可能顺带把 Notifications 搞崩了。

Contracts 层是一道刻意设计的防火墙。它说：这是允许你看到的数据，仅此而已。

## 上下文映射：跨上下文通信

有了 Contracts 之后，上下文通过发布和订阅事件来通信。发布者不知道谁在监听——它只管抛出事件。订阅者各自独立响应。

下面是 Notifications 模块对 `TaskAssignedEvent` 的处理器：

```csharp
using MediatR;
using Tasks.Contracts;

namespace Notifications.Application.Handlers;

internal sealed class TaskAssignedEventHandler
    : INotificationHandler<TaskAssignedEvent>
{
    private readonly INotificationStore _notificationStore;

    public TaskAssignedEventHandler(INotificationStore notificationStore)
    {
        _notificationStore = notificationStore;
    }

    public Task Handle(
        TaskAssignedEvent notification,
        CancellationToken cancellationToken)
    {
        var message = $"Task assigned: {notification.TaskTitle} " +
            $"to user {notification.UserId}";
        _notificationStore.Add(message);
        return Task.CompletedTask;
    }
}
```

处理器是 `internal sealed`——它住在 Notifications 模块内部，外部看不见。唯一的外部依赖是 `Tasks.Contracts`，而这是明确允许的，因为 Contracts 就是上下文间的公开 API。对 `Tasks.Domain` 零引用。Notifications 上下文只知道它需要知道的：有一个任务被分配了、哪个任务、分配给谁。

Tasks 模块负责发布事件。它不知道 Notifications 在监听。这是干净的上下文映射——DDD 术语里叫 Customer/Supplier 模式，Notifications 遵循 Tasks 发布的事件格式。

## 反模式：跨上下文共享领域对象

显式列出不该做的事，因为这个坑踩的人太多了。

假设你受不了每次都要新建 `TaskAssignedEvent`，决定直接把 `Tasks.Domain.TaskItem` 传给 Notifications 模块。处理器的签名变成：

```csharp
// ❌ 别这么干
public Task Handle(Tasks.Domain.TaskItem taskItem, ...)
{
    // Notifications 现在看到了 TaskStatus、Assign()、Complete()……
    // 没有一个它应该关心的
}
```

现在 Notifications 已经耦合到了 Tasks 的领域模型。对 `TaskItem` 的任何改动都可能炸掉 Notifications 处理器。`TaskItem` 上的 `internal` 修饰符本应在编译时拦住你——但如果你的项目结构允许直接引用 `Tasks.Domain`，编译器不会救你。

规则很简单：在 `*.Domain` 项目里的东西是 `internal` 的。如果它需要跨上下文边界，就创建一个 contract。写合约类的那点摩擦是故意的——它在逼你仔细想清楚你到底在暴露什么。

## 实际 DDD：别一开始就全上

DDD 有太多概念了：聚合、聚合根、值对象、仓储、领域服务、领域事件、工厂。不是每个项目都需要所有东西。事实上，一上来就全上，是通向过度设计的最靠谱路线。

模块化单体给了你一个务实的起点：

1. **先把模块边界画对**——这是 DDD 里杠杆效应最高的决策。其他都是锦上添花。
2. **用实体和工厂方法**——`Project.Create()`、`TaskItem.Create()`，验证逻辑写在工厂里。简单、管用。
3. **跨上下文通信用集成事件**——MediatR 的 `INotification` + `*.Contracts` 项目就够你用很久。
4. **确实需要时再加仓储**——应用层放仓储接口，基础设施层提供 EF Core 实现。有正经持久化逻辑时再加，别提前建。
5. **看到 string/primitive 滥用时再加值对象**——如果 `Email` 以裸 `string` 出现在五个地方，就包一个带验证的值对象。别提前做。

不需要第一天就上聚合根，也不需要第一天就上领域事件（区别于集成事件）。从基本功开始：干净的模块边界、`internal` 领域模型、`public` contracts、事件驱动的跨上下文通信。你已经有了很好的基础，需要时再加更重的 DDD 机制。

## 常见问题

### 模块和限界上下文是一回事吗？

在这个架构下，是的。每个模块就是一个限界上下文。模块边界（靠项目引用和 `internal` 修饰符强制执行）就是限界上下文边界。1:1 映射让事情干净、易管。更复杂的系统里偶尔会出现一个模块包含多个限界上下文的情况，但那是以后的事，不是起点。

### 限界上下文应该共享数据库 Schema 吗？

它们可以——在模块化单体里，它们通常共享一个数据库实例。但每个上下文应该拥有自己的表。`Projects` 模块写 `projects` 表，`Tasks` 模块写 `tasks` 表。两个模块不直接查对方的表。跨上下文查询通过集成事件或显式 API 调用完成，不在表之间做 JOIN。

### 两个限界上下文能引用同一个数据库实体 ID 吗？

能，而且这很正常。Tasks 上下文里的 `TaskItem` 有一个 `ProjectId`（Guid），它引用了项目，但它不引用 `Project` 实体——只持有一个原始外键。如果 Tasks 上下文需要项目信息，通过事件或 API 获取，不加载 `Project` 领域对象。

### 跨限界上下文的事务怎么办？

你基本不这么做。如果一个操作必须在两个上下文间保持原子性，通常意味着这些概念本来就应该在同一个上下文里。当真的需要跨上下文一致性时，用 outbox 模式——把事件写到和领域变更相同的数据库事务里，异步处理。这是刻意的最终一致性——是特性，不是 bug。

### 需要反破坏层（ACL）吗？

在模块化单体里你控制所有代码，通常不需要 ACL。你同时控制事件的发布方和消费方，可以干净地设计 contracts。ACL 更适合集成外部系统——那些你控制不了数据模型的场景，需要在外部概念和自己的领域语言之间做翻译。

## 结语

DDD 限界上下文在模块化单体里不是什么高深的论文课题。它就是一个很实在的想法：在代码里画出干净的边界，用访问修饰符和项目引用强制执行它们，让每个限界上下文完整拥有自己的领域模型，只通过公开 contracts 跨越边界通信。

这三条规则——`internal` 领域实体、`public` contracts、事件驱动跨上下文通信——已经够你开一条很稳的船。先把这些做扎实，复杂度上来时再加 DDD 的其他武器。

## 参考

- [原文：DDD and Bounded Contexts in a Modular Monolith with C#](https://www.devleader.ca/2026/07/18/ddd-and-bounded-contexts-in-a-modular-monolith-with-c-a-practical-guide)
