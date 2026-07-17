---
pubDatetime: 2026-07-17T08:03:52+08:00
title: "模块化单体中的通信模式：进程内事件与合约"
description: "模块化单体拆好了模块，但跨模块通信一不小心就会打破边界。本文用 .NET 9 示例项目讲清三种通信模式——模块接口、MediatR 进程内事件和共享合约，核心原则是只引用 Contracts 层，绝不跨模块引用 Application/Infrastructure。"
tags: ["模块化单体", "MediatR", "C#", ".NET", "架构模式"]
slug: "module-communication-modular-monolith-csharp"
ogImage: "../../assets/949/01-cover.png"
source: "https://www.devleader.ca/2026/07/16/module-communication-patterns-in-modular-monolith-c-inprocess-events-and-contracts"
---

你把应用切成了模块：Tasks、Projects、Notifications——每个有自己的文件夹、自己的 DbContext、自己的限界上下文。图纸上看起来很干净。

然后关键时刻来了：分配任务的操作需要通知 Notifications 模块。你手一伸，加了项目引用，写进 `.csproj`，就这么一下，你亲手建起来的墙开始塌了。**模块化单体中的模块通信**这个课题，正是区分"架构良好的模块化应用"和"穿模块外衣的大泥球"的关键。

本文用一份真实的 .NET 9 示例项目，过一遍模块间通信的三种具体模式、对应的代码、以及让模块不滑回大泥球的规则。

## 三种通信方式

动笔写代码之前，先把局面铺清楚。模块化单体里模块间的通信，实际可用的就三种：

**方式 A——模块接口（同步调用）**
每个模块暴露一个公开接口，比如 `ITasksModule` 或 `IProjectsModule`。系统其他部分依赖接口，永远不依赖具体实现。类型安全，适合需要马上拿到查询结果的场景。

**方式 B——进程内领域事件（MediatR）**
发布模块通过 MediatR 的 `IPublisher` 发出 `INotification`。感兴趣的模块注册 `INotificationHandler<T>` 然后响应。发布者不知道、也不关心谁在听。这是跨模块副作用的主力模式。

**方式 C——共享合约（事件和结果 DTO）**
合约项目只放公开面：事件 record 和结果 DTO。没有领域实体、没有 DbContext、没有内部服务。其他模块引用合约项目，不引用 Application 或 Infrastructure 项目。

这三种模式自然组合，实际项目里你全都会用到。

## 反模式：直接项目引用

这里有一个陷阱。你很容易就觉得从 `Tasks.Application` 加一个 `ProjectReference` 到 `Projects.Application` 没什么——毕竟就是想查一下项目名字。这是模块化单体里最常见的错误，也是悄悄毁掉架构的那一步。

```xml
<!-- ❌ 绝不引用其他模块的 Application 或 Infrastructure 层 -->
<ProjectReference
  Include="......ProjectsProjects.ApplicationProjects.Application.csproj" />
```

一旦你这么做，Tasks 就依赖了 Projects 的 EF Core 实体、它的 `DbContext` 和内部服务。Projects 内部任何重构都可能搞崩 Tasks。你重建了大泥球——只是多了一堆文件夹。

规则是硬的：**Application 和 Infrastructure 层绝不跨模块引用。**只有 Contracts 层是合法的跨模块引用。

看示例中 `Tasks.Application.csproj` 的结构：

```xml
<ItemGroup>
  <ProjectReference Include="..Tasks.DomainTasks.Domain.csproj" />
  <ProjectReference
    Include="..Tasks.ContractsTasks.Contracts.csproj" />
</ItemGroup>
```

Tasks.Application 只引用自己的 Domain 和自己的 Contracts。看不到任何其他模块的 Application 或 Infrastructure。

## 模式 1：用 MediatR 做进程内领域事件

MediatR 的 `INotification` / `INotificationHandler<T>` 是跨模块通信的主力。它本质是观察者模式——发布者广播事件，多个订阅者各自独立响应。

每个集成事件都放在合约项目里。`Tasks.Contracts/TaskEvents.cs` 的完整内容：

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

以及 `Projects.Contracts/ProjectCreatedEvent.cs`：

```csharp
using MediatR;

namespace Projects.Contracts;

public sealed record ProjectCreatedEvent(
    Guid ProjectId,
    string Name,
    string Description) : INotification;
```

注意几点：

- 都是 `sealed record`——不可变，带结构相等性。
- 实现 `INotification`，不是 `IRequest<T>`。没有返回值，发出就不管。
- 放在 `*.Contracts` 项目里，只依赖 `MediatR.Contracts`——不依赖任何领域实体或应用服务。
- 只携带原始数据（Guid、string）。没有领域对象跨边界泄露。

### 合约项目里放什么

合约项目是模块的公开 API 面。把它理解成模块稳定、向外的词汇表。

**应该放：**

- 集成事件（`INotification` 实现）
- 模块接口方法返回的结果 record
- 真正必要的情况下，共享值对象——但尽量保持面最小

**不应该放：**

- 领域实体（`TaskItem`、`Project` 等）
- `DbContext` 实现
- 基础设施配置或内部服务

看 `Notifications.Application.csproj` 怎么从结构上执行这条规则：

```xml
<ItemGroup>
  <ProjectReference Include="....UsersUsers.ContractsUsers.Contracts.csproj" />
  <ProjectReference Include="....ProjectsProjects.ContractsProjects.Contracts.csproj" />
  <ProjectReference Include="....TasksTasks.ContractsTasks.Contracts.csproj" />
</ItemGroup>
```

Notifications 依赖三个合约项目——从来不是任何其他模块的 Application 或 Infrastructure 层。哪怕 Tasks 完全重写内部领域模型，能影响 Notifications 的唯一破坏性变更只来自 `Tasks.Contracts`。

## 发布事件

事件从应用层发布，在状态变更持久化之后。`Tasks.Application/TasksModule.cs` 的 `AssignTaskAsync` 方法展示了这个模式：

```csharp
public async Task<AssignTaskResult> AssignTaskAsync(
    Guid taskId,
    Guid userId,
    CancellationToken cancellationToken = default)
{
    var task = await _dbContext.Tasks
        .FirstOrDefaultAsync(t => t.Id == taskId, cancellationToken);

    if (task == null)
    {
        return new AssignTaskResult(taskId, userId, false);
    }

    task.Assign(userId);
    await _dbContext.SaveChangesAsync(cancellationToken);

    await _publisher.Publish(
        new Contracts.TaskAssignedEvent(
            task.Id, task.ProjectId, userId, task.Title),
        cancellationToken);

    return new AssignTaskResult(taskId, userId, true);
}
```

顺序是故意的：

1. 加载聚合。
2. 执行领域操作。
3. 持久化变更。
4. 发布事件。

在保存之后发布确保了事件反映的是已提交状态。如果保存失败，就不发事件——行为一致，不需要 saga 或发件箱。对纯进程内单体来说这是正确的做法。后续如果把模块提取为独立服务，替换成事务性发件箱即可。

`IPublisher` 通过构造函数注入。`TasksModule` 不知道谁在听，甚至不知道有没有人在听。

## 处理事件

Notifications 模块监听来自多个模块的事件。所有 handler 都是 `internal sealed`——它们是实现细节，模块之外完全不可见。

`Notifications.Application/Handlers/EventHandlers.cs` 中的 `TaskAssignedEventHandler`：

```csharp
internal sealed class TaskAssignedEventHandler
    : INotificationHandler<TaskAssignedEvent>
{
    private readonly INotificationStore _notificationStore;

    public TaskAssignedEventHandler(
        INotificationStore notificationStore)
    {
        _notificationStore = notificationStore;
    }

    public Task Handle(
        TaskAssignedEvent notification,
        CancellationToken cancellationToken)
    {
        var message =
            $"任务已分配: {notification.TaskTitle} 分配给用户 {notification.UserId}";
        _notificationStore.Add(message);
        return Task.CompletedTask;
    }
}
```

`internal sealed` 修饰符很关键。`Notifications.Application` 之外没有任何东西能直接实例化或引用 `TaskAssignedEventHandler`。MediatR 通过程序集扫描在启动时发现它——不需要逐 handler 显式注册。

同一个文件里还有 `ProjectCreatedEvent`、`TaskCompletedEvent` 和 `UserRegisteredEvent` 的 handler——全是 `internal sealed`，发布这些事件的模块完全不知道它们存在。Tasks 模块发布事件，不知道 `TaskAssignedEventHandler`。Notifications 模块处理事件，不知道任务是怎么分配的。

## MediatR 注册

要让发布/订阅通路工作，MediatR 必须在启动时扫描每个模块的应用程序集。`Host/Program.cs` 负责这件事：

```csharp
builder.Services.AddMediatR(cfg =>
{
    cfg.RegisterServicesFromAssembly(typeof(Program).Assembly);
    cfg.RegisterServicesFromAssembly(typeof(IUsersModule).Assembly);
    cfg.RegisterServicesFromAssembly(typeof(IProjectsModule).Assembly);
    cfg.RegisterServicesFromAssembly(typeof(ITasksModule).Assembly);
    cfg.RegisterServicesFromAssembly(
        typeof(INotificationsModule).Assembly);
});
```

每个 `RegisterServicesFromAssembly` 调用扫描一个模块的程序集，注册它找到的所有 `INotificationHandler<T>` 实现。Handler 可以是 `internal` 的，因为 MediatR 用反射——访问修饰符挡不住注册。

Host 项目是组合根。它知道每个模块的应用程序集，而且是唯一知道的项目。各个模块之间不互相引用。

## 模式 2：用于查询的模块接口

进程内事件适合发出后不管的通知。但有时候你需要一个同步结果："这个项目的状态是什么？""这个用户存在吗？"这些场景下，模块接口模式是正确的工具。

每个模块为它的操作暴露一个公开接口。`IProjectsModule`：

```csharp
namespace Projects.Application;

public interface IProjectsModule
{
    Task<CreateProjectResult> CreateProjectAsync(
        string name,
        string description,
        CancellationToken cancellationToken = default);

    Task<GetProjectResult?> GetProjectAsync(
        Guid projectId,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<ProjectListResult>> ListProjectsAsync(
        CancellationToken cancellationToken = default);
}

public sealed record GetProjectResult(
    Guid ProjectId, string Name,
    string Description, string Status);

public sealed record CreateProjectResult(
    Guid ProjectId, string Name, string Description);

public sealed record ProjectListResult(
    Guid ProjectId, string Name, string Status);
```

如果 Tasks 模块需要在创建任务前验证项目是否存在，它注入 `IProjectsModule` 并调用 `GetProjectAsync`。依赖在公开接口上，不在任何 Projects 实现类上。

返回类型是 `sealed record`，和接口定义在一起，形成了模块完整的公开 API 面。

## 怎么选模式

这是一个实用的决策指南：

| 场景                               | 模式                         | 原因                             |
| ---------------------------------- | ---------------------------- | -------------------------------- |
| 模块 A 通知模块 B 状态变化         | 进程内事件 (`INotification`) | 发布者与所有消费者解耦           |
| 多个模块需要响应同一个事件         | 进程内事件                   | MediatR 扇出给所有注册的 handler |
| 模块 A 需要读模块 B 拥有的数据     | 模块接口 (`IXxxModule`)      | 同步调用，返回类型化结果         |
| 模块 A 需要根据模块 B 的数据做校验 | 模块接口                     | 调用方在继续之前需要答案         |
| 模块 A 需要触发模块 B 的写操作     | 重新审视边界                 | 跨模块的写操作是一种设计坏味道   |

最后一行值得强调。如果你发现自己想调用另一个模块接口上的写操作，先停一下。这通常意味着要么限界上下文有问题——操作应该完全属于一个模块——要么你需要一个工作流层来协调两者。直接伸进另一个模块的写路径，是在最不该耦合的地方把模块耦合起来的最快方式。

## 未来提取为微服务

当你想把一个模块提取为独立服务时，工作范围是有限的：

- 把 `IPublisher.Publish` 替换为消息代理发布。
- 把进程内 `INotificationHandler<T>` 替换为消息消费者。
- 把 `IXxxModule` DI 注册替换为 HTTP 或 gRPC 客户端实现。

模块的内部代码——领域、应用逻辑、数据库 schema——不变。合约和接口保持稳定。这就是边界清晰的真正价值。

## 参考

- [原文：Module Communication Patterns in Modular Monolith C#](https://www.devleader.ca/2026/07/16/module-communication-patterns-in-modular-monolith-c-inprocess-events-and-contracts)
