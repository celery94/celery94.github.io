---
pubDatetime: 2026-04-24T10:10:00+08:00
title: "C# 中 Feature Slicing 与 Clean Architecture 该选哪个？"
description: "Feature Slicing 和 Clean Architecture 常被当作对立选项，其实它们解决的问题完全不同。本文从依赖方向、代码组织、团队规模等维度对比两者，并给出实际决策框架。"
tags: ["C#", "Software Architecture", "Clean Architecture", "Feature Slicing"]
slug: "feature-slicing-vs-clean-architecture-csharp"
ogImage: "../../assets/753/01-cover.jpg"
source: "https://www.devleader.ca/2026/04/23/feature-slicing-vs-clean-architecture-in-c-which-one-should-you-use"
---

Feature Slicing 和 Clean Architecture 是 C# 社区讨论最多的两种代码组织方式，很多人把它们当成非此即彼的选择。实际上两者并不冲突：它们解决的问题不同、适用的尺度不同，甚至可以在同一个项目里共存。

这篇文章会诚实对比两者的取舍：各自擅长什么、哪里容易踩坑，以及一个可以直接落地的决策框架。

## 两种方法各自解决什么问题

在直接对比之前，先明确它们的设计初衷。

**Clean Architecture**（与 Hexagonal / Ports-and-Adapters / Onion Architecture 密切相关，只是分层约定略有不同）解决的是**依赖方向**问题。核心原则是业务逻辑不依赖基础设施。领域层和应用层对数据库、HTTP、外部服务一无所知，这些知识放在外层，且外层只能向内层依赖。

**Feature Slicing**（功能切片）解决的是**内聚性和可发现性**问题。核心原则是把同一个业务功能相关的代码放在一起。不再按技术层分散存放，而是把每个功能需要的所有东西收进一个文件夹。

这是两个不同的关注点。依赖方向和代码组织是正交的结构维度。

## Clean Architecture 在 C# 中的典型结构

一个 Clean Architecture 的 .NET 解决方案通常包含四个项目：

```
TaskTracker/
  TaskTracker.Domain/          <- 实体、领域逻辑，无外部依赖
  TaskTracker.Application/     <- 用例、端口（接口）、应用服务
  TaskTracker.Infrastructure/  <- EF Core、外部 API、端口的实现
  TaskTracker.Api/             <- ASP.NET Core、控制器、DI 注册
```

依赖规则：

- `Domain` 零外部依赖
- `Application` 只依赖 `Domain`
- `Infrastructure` 依赖 `Application` 和 `Domain`
- `Api` 依赖所有层

代码层面，领域实体自己封装行为：

```csharp
// TaskTracker.Domain/Entities/TaskEntity.cs
namespace TaskTracker.Domain.Entities;

public sealed class TaskEntity
{
    public Guid Id { get; private set; }
    public string Title { get; private set; } = string.Empty;
    public bool IsCompleted { get; private set; }
    public DateTimeOffset CreatedAt { get; private set; }

    public void Complete()
    {
        if (IsCompleted)
        {
            throw new InvalidOperationException("Task is already completed.");
        }

        IsCompleted = true;
    }
}
```

应用层通过接口与基础设施解耦：

```csharp
// TaskTracker.Application/Tasks/ITaskRepository.cs
namespace TaskTracker.Application.Tasks;

public interface ITaskRepository
{
    Task<TaskEntity?> GetByIdAsync(Guid id, CancellationToken cancellationToken);
    Task<IReadOnlyList<TaskEntity>> GetByProjectAsync(Guid projectId, CancellationToken cancellationToken);
    void Add(TaskEntity task);
    Task SaveChangesAsync(CancellationToken cancellationToken);
}
```

```csharp
// TaskTracker.Application/Tasks/CompleteTaskService.cs
namespace TaskTracker.Application.Tasks;

public sealed class CompleteTaskService
{
    private readonly ITaskRepository _repository;

    public CompleteTaskService(ITaskRepository repository)
    {
        _repository = repository;
    }

    public async Task<CompleteTaskResult> CompleteAsync(
        Guid taskId,
        CancellationToken cancellationToken = default)
    {
        var task = await _repository.GetByIdAsync(taskId, cancellationToken);

        if (task is null)
        {
            return CompleteTaskResult.NotFound;
        }

        try
        {
            task.Complete();
        }
        catch (InvalidOperationException)
        {
            return CompleteTaskResult.AlreadyCompleted;
        }

        await _repository.SaveChangesAsync(cancellationToken);
        return CompleteTaskResult.Success;
    }
}
```

这种结构强制了干净的依赖图。应用服务不知道任务存在 SQL Server、PostgreSQL 还是内存列表里，由基础设施层决定。

## Feature Slicing 在 C# 中的典型结构

Feature Slicing 按业务能力而非技术层来组织同一个应用：

```
TaskTracker/
  Features/
    Tasks/
      CompleteTask/
        CompleteTaskEndpoint.cs
        CompleteTaskHandler.cs
      CreateTask/
        CreateTaskEndpoint.cs
        CreateTaskHandler.cs
        CreateTaskRequest.cs
        CreateTaskResponse.cs
      GetTasks/
        GetTasksEndpoint.cs
        GetTasksHandler.cs
        GetTasksQuery.cs
        GetTasksResponse.cs
  Shared/
    Data/
      AppDbContext.cs
    Entities/
      TaskEntity.cs
  Program.cs
```

对应的 Handler 直接依赖 `DbContext`：

```csharp
// Features/Tasks/CompleteTask/CompleteTaskHandler.cs
namespace TaskTracker.Features.Tasks.CompleteTask;

public sealed class CompleteTaskHandler
{
    private readonly AppDbContext _db;
    private readonly TimeProvider _time;

    public CompleteTaskHandler(AppDbContext db, TimeProvider time)
    {
        _db = db;
        _time = time;
    }

    public async Task<CompleteTaskResult> HandleAsync(
        Guid taskId,
        CancellationToken cancellationToken = default)
    {
        var task = await _db.Tasks.FindAsync([taskId], cancellationToken);

        if (task is null) return new CompleteTaskResult(Found: false);
        if (task.IsCompleted) return new CompleteTaskResult(Found: true, AlreadyCompleted: true);

        task.IsCompleted = true;
        task.CompletedAt = _time.GetUtcNow();

        await _db.SaveChangesAsync(cancellationToken);
        return new CompleteTaskResult(Found: true);
    }
}
```

这个 Feature Slice Handler 直接依赖 `AppDbContext`，没有仓库接口、没有基础设施项目、没有领域层。代码更简单，但也更耦合于数据库实现。

## 直接对比

| 维度 | Feature Slicing | Clean Architecture |
|---|---|---|
| 主要目标 | 代码内聚性和可发现性 | 依赖方向和可测试性 |
| 按什么分组 | 业务功能 | 技术层 |
| 项目数量 | 通常 1 个（或少数几个） | 3-4 个（Domain、Application、Infrastructure、Api） |
| 基础设施耦合 | Handler 直接耦合数据库 | 应用层通过接口解耦 |
| 上手成本 | "打开功能文件夹即可" | "先理解层的依赖规则" |
| 新增功能 | 加一个文件夹 | 跨多个项目添加 |
| 业务逻辑位置 | Feature Handler | 领域实体和应用服务 |
| 可测试性 | 用内存数据库做集成测试 | 用 Mock 接口做单元隔离测试 |
| 可替换性 | 基础设施整体耦合 | 可替换基础设施而不碰业务逻辑 |

两种方法没有通吃所有维度的赢家，取舍是真实的。

## Feature Slicing 更适合的场景

**交付速度优先。** 新增功能就是加一个文件夹和几个文件，不需要定义接口、实现仓库、配置映射。对于大量 CRUD 风格的 API，这种摩擦成本的节省很可观。

**团队小或功能独立演进。** 两个开发者很少需要协调同一个功能时，按切片划分所有权很自然。每个人在自己的功能文件夹里工作，不用担心共享的服务或仓库类冲突。

**应用以 CRUD 或具体用例为主。** Feature Slicing 在功能能直接映射到 HTTP 端点时最顺手：创建、读取、更新、删除、状态流转。大部分 REST API 本质上都是这类应用。

**希望文件夹结构直接表达产品。** 打开 `Features/Tasks/` 看到 `CreateTask`、`CompleteTask`、`AssignTask`、`GetTasks`，几秒钟就能理解这个产品做什么。打开 `Services/TaskService.cs` 读 500 行代码，信息密度低得多。

## Clean Architecture 更适合的场景

**业务逻辑复杂，需要与基础设施隔离。** 当领域里有丰富的行为——带不变量的实体、聚合根、复杂状态流转——领域层给这些逻辑提供了一个远离 HTTP、数据库和外部服务的栖身之所。

**需要替换基础设施。** 如果你可能从 SQL Server 迁到 PostgreSQL，从 EF Core 切到 Dapper，或者从 REST API 改成事件驱动，Clean Architecture 的接口让这种替换可以不碰业务逻辑。Feature Slicing 的 Handler 是写死在它依赖的基础设施上的。

**多种交付机制共用同一套业务逻辑。** 同一个用例要通过 HTTP API、后台任务和 gRPC 三种方式执行时，Clean Architecture 的应用服务可以被三者复用而不重复。Feature Slice Handler 本质上就是 HTTP 端点处理者。

**长期可维护性比初期速度更重要。** Clean Architecture 的结构会引导新开发者："领域逻辑放到领域层，基础设施放到基础设施层。" 这些规则会随时间自我强化。

## 两者可以一起用吗？

可以，而且很多团队就是这么做的。最常见的组合是：**项目级别用 Clean Architecture，Application 层内部用 Feature Slicing。**

结构看起来像这样：

```
TaskTracker.Domain/
  Entities/
    TaskEntity.cs
    ProjectEntity.cs

TaskTracker.Application/
  Features/                     <- Application 层内部按功能切片
    Tasks/
      CreateTask/
        CreateTaskCommand.cs
        CreateTaskCommandHandler.cs
        CreateTaskResult.cs
      CompleteTask/
        CompleteTaskCommand.cs
        CompleteTaskCommandHandler.cs
  Ports/                        <- 应用层暴露的接口
    ITaskRepository.cs

TaskTracker.Infrastructure/
  Repositories/
    TaskRepository.cs           <- 实现 ITaskRepository

TaskTracker.Api/
  Features/
    Tasks/
      CreateTask/
        CreateTaskEndpoint.cs
      CompleteTask/
        CompleteTaskEndpoint.cs
```

这种混合方案里，应用层按功能组织，获得了 Feature Slicing 的可发现性；同时 Clean Architecture 的依赖方向规则仍然生效：应用层只依赖领域实体和自己的接口，不依赖 EF Core。

这样既能保持功能切片的结构清晰度，又不牺牲 Clean Architecture 的长期灵活性。

## 实际决策框架

**选纯 Feature Slicing（不用 Clean Architecture）如果：**

- 团队小（1-5 人），追求快速交付
- 应用是 API 优先且以 CRUD 为主
- 业务逻辑薄，主要存在于数据库操作里
- 你更看重简单性而非最大灵活性

**选纯 Clean Architecture（不用 Feature Slicing）如果：**

- 领域复杂，业务规则丰富
- 团队需要显式结构来约束架构纪律
- 基础设施可替换是真实需求，不是理论假设
- 同一业务逻辑有多种交付机制

**选混合方案（Clean Architecture + Application 层内 Feature Slicing）如果：**

- 团队在扩张（5 人以上），需要明确的功能所有权
- 既有复杂领域逻辑，又有大量独立用例
- 想要长期可维护性，又不想放弃可发现性
- 系统在朝模块化演进，未来可能拆分成服务

## 常见问题

**Feature Slicing 比 Clean Architecture 更好吗？**

没有 universally better。Feature Slicing 在 CRUD 密集的 API 上擅长代码内聚和交付速度；Clean Architecture 在保护复杂业务逻辑和强制依赖边界上更强。取决于领域复杂度、团队规模和长期维护需求。

**两者能结合吗？**

能。常见的做法是用 Clean Architecture 做项目级别的依赖结构（Domain、Application、Infrastructure、Api），同时在 Application 层内部按功能切片组织用例。这样既有切片的结构清晰度，又有 Clean Architecture 的依赖保护。

**Feature Slicing 违反 Clean Architecture 原则吗？**

最简形式的 Feature Slicing（Handler 直接依赖 DbContext）确实违反了依赖倒置原则——Handler 依赖了基础设施。但这个违反是否重要，取决于项目需求。如果你需要基础设施可替换，就加上接口层；如果不需要，这种简单性可能值得接受耦合。

**Clean Architecture 相比 Feature Slicing 的主要优势是什么？**

业务逻辑与基础设施隔离。你可以不用真实数据库测试应用服务，也可以替换数据库而不碰业务逻辑。Feature Slicing 用隔离性换了简单性——Handler 直接耦合数据库。

**什么时候 Feature Slicing 比 Clean Architecture 更合适？**

应用以 CRUD 为主、团队小、交付速度比最大灵活性更重要的时候。另外，如果业务逻辑足够薄，一个厚重的领域层反而是不必要的开销。

**Vertical Slice Architecture 和 Clean Architecture 是什么关系？**

Vertical Slice Architecture 是 Feature Slicing 的一种变体，显式应用 CQRS（每个功能分命令和查询），通常用 MediatR 做调度。Clean Architecture 是另一个专注于依赖方向的结构模式。两者可以共存：一个 Vertical Slice 应用可以在项目层之间遵循 Clean Architecture 的依赖规则，同时在 Application 层内部按功能切片。

**从 Clean Architecture 重构到 Feature Slicing 有意义吗？**

看动机。如果团队觉得层结构混乱、功能难找，把 Application 层重构成 Feature Slices（同时保留 Clean Architecture 的项目结构）可以在不破坏架构收益的前提下提升可发现性。完全从 Clean Architecture 迁移到扁平的 Feature Slices 会丢掉基础设施隔离，这个取舍对你的项目是否值得，需要自己判断。

## 参考

- [Feature Slicing vs Clean Architecture in C#: Which One Should You Use?](https://www.devleader.ca/2026/04/23/feature-slicing-vs-clean-architecture-in-c-which-one-should-you-use) — 原文
- [C# Clean Architecture with MediatR](https://www.devleader.ca/2024/02/06/c-clean-architecture-with-mediatr-how-to-build-for-flexibility)
- [CQRS Pattern in C# and Clean Architecture](https://www.devleader.ca/2024/02/07/cqrs-pattern-in-c-and-clean-architecture-a-simplified-beginners-guide)
- [Vertical Slice Development](https://www.devleader.ca/2023/10/10/vertical-slice-development-a-comprehensive-how-to-for-modern-teams)
