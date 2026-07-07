---
pubDatetime: 2026-07-07T16:05:00+08:00
title: "C# 模块化单体：.NET 开发者的完整实现指南"
description: "从零开始用 C# 构建一个模块化单体应用，覆盖模块封装、数据隔离与事件驱动通信。文章提供完整的项目结构和可直接运行的代码，帮助团队在不过度引入微服务复杂度的前提下提升架构可维护性。"
tags: ["CSharp", "Modular Monolith", "Architecture", ".NET", "MediatR", "EF Core"]
slug: "modular-monolith-csharp-dotnet-implementation-guide"
ogImage: "../../assets/932/01-cover.png"
source: "https://www.devleader.ca/2026/07/06/modular-monolith-in-c-complete-implementation-guide-for-net-developers"
---

模块化单体（Modular Monolith）是 .NET 新项目里最值得认真考虑的架构选择之一。它把微服务的组织思想搬进了单个进程——边界上下文、强制的模块隔离、事件驱动的跨模块通信——但绕开了分布式系统在 v1 阶段就让团队慢下来的所有运维成本。

这篇指南不会给你画箭头图，而是给一个可以 `dotnet run` 直接跑起来的实现。读完你会知道怎么组织项目结构、怎么干净地注册模块、怎么在模块间隔离数据、怎么用 MediatR 做跨模块事件通信。

如果你之前做的传统单体到了后期发现所有东西都搅在一起——Services 互相 new、Repository 随便跨域用、改一处崩一片——模块化单体就是那个让你不用上微服务也能解开这些结的办法。

## 四个核心原则

动手之前，先理清这四条原则。它们不是方向性建议，而是你通过项目结构可以强制执行的约束。

**1. 单一部署单元。** 整个应用以一个进程跑起来。没有服务网格，没有 Docker 编排，没有进程间调用。运行时保持简单，内部架构保持干净。

**2. 强制模块边界。** 每个模块只暴露一个公开接口，内部通过 `internal` 修饰符对项目外完全不可见。其他模块不能直接碰你的 Domain 实体，也不能直接访问你的 DbContext。

**3. 独立数据。** 每个模块拥有自己的数据存储。在这篇的实现里，每个模块一个单独的 SQLite 文件和独立的 `DbContext`。没有共享表，没有共享 ORM 上下文。

**4. 事件驱动的通信。** 模块之间不直接调用。一个模块的状态变化通过发布集成事件来通知其他模块，订阅方各管各的处理逻辑。这套机制本质上就是 Observer 模式在架构层面的放大。

四条原则是联动的。但凡违反其中一条，其他几条也会跟着崩塌。项目结构是让它们落实的关键。

## 方案结构概览

Demo 应用的实际目录布局：

```
modular-monolith-demo/
├── src/
│   ├── Host/
│   │   └── Program.cs                  ← 组合根
│   └── Modules/
│       ├── Projects/
│       │   ├── Projects.Domain/        ← internal 实体
│       │   ├── Projects.Application/   ← IProjectsModule（公开契约）
│       │   ├── Projects.Infrastructure/← EF Core DbContext、扩展方法
│       │   └── Projects.Contracts/     ← 集成事件（公开）
│       ├── Tasks/
│       │   ├── Tasks.Domain/
│       │   ├── Tasks.Application/
│       │   ├── Tasks.Infrastructure/
│       │   └── Tasks.Contracts/
│       ├── Users/
│       │   ├── Users.Domain/
│       │   ├── Users.Application/
│       │   ├── Users.Infrastructure/
│       │   └── Users.Contracts/
│       └── Notifications/
│           ├── Notifications.Application/
│           └── Notifications.Infrastructure/
└── tests/
    ├── ModularMonolith.UnitTests/
    └── ModularMonolith.IntegrationTests/
```

每个模块用四层结构：**Domain**、**Application**、**Infrastructure**、**Contracts**。Domain 和 Application 层对模块外部是 `internal` 的。Contracts 是公开的，供其他模块订阅事件。Application 层暴露一个公开接口（如 `IProjectsModule`、`ITasksModule`），这是 Host 和其他模块跟它交互的唯一入口。

## 实践一：模块封装

封装从 Domain 层做起。Domain 实体用 `internal sealed`——模块程序集之外的代码无法直接引用或实例化它们。

```csharp
// Projects.Domain/Project.cs
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
        {
            throw new ArgumentException(
                "Project name cannot be empty", nameof(name));
        }

        return new Project
        {
            Id = Guid.NewGuid(),
            Name = name,
            Description = description ?? string.Empty,
            Status = ProjectStatus.Active,
            CreatedAt = DateTime.UtcNow
        };
    }
}
```

`internal sealed` 是有实际含义的。`sealed` 阻止无意的继承，`internal` 让这个类对 `Projects.Domain` 程序集之外完全不可见。Host 项目不能直接访问 `Project`——它只能通过 `IProjectsModule` 操作。

Application 层的模块实现遵循同样的访问规则：

```csharp
// Projects.Application/ProjectsModule.cs
namespace Projects.Application;

internal sealed class ProjectsModule : IProjectsModule
{
    private readonly IProjectsDbContext _dbContext;
    private readonly IPublisher _publisher;

    public ProjectsModule(
        IProjectsDbContext dbContext, IPublisher publisher)
    {
        _dbContext = dbContext;
        _publisher = publisher;
    }

    public async Task<CreateProjectResult> CreateProjectAsync(
        string name,
        string description,
        CancellationToken cancellationToken = default)
    {
        var project = Project.Create(name, description);

        _dbContext.Projects.Add(project);
        await _dbContext.SaveChangesAsync(cancellationToken);

        await _publisher.Publish(
            new Contracts.ProjectCreatedEvent(
                project.Id, project.Name, project.Description),
            cancellationToken);

        return new CreateProjectResult(
            project.Id, project.Name, project.Description);
    }
}
```

整个模块的公开表面积只有 `IProjectsModule` 接口和几个结果 record 类型。Host 通过扩展方法干净地注册：

```csharp
// Projects.Infrastructure/ProjectsModuleExtensions.cs
namespace Projects.Infrastructure;

public static class ProjectsModuleExtensions
{
    public static IServiceCollection AddProjectsModule(
        this IServiceCollection services,
        string connectionString)
    {
        services.AddDbContext<ProjectsDbContext>(options =>
            options.UseSqlite(connectionString));

        services.AddScoped<IProjectsDbContext>(
            sp => sp.GetRequiredService<ProjectsDbContext>());
        services.AddScoped<IProjectsModule, ProjectsModule>();

        return services;
    }
}
```

`Program.cs` 里的调用只有一行：`builder.Services.AddProjectsModule("Data Source=projects.db")`。独立、自包含、可替换。如果你后续要给某个模块加日志、缓存之类的横切关注点，Decorator 模式可以自然地叠加在这层注册机制上。

## 实践二：事件驱动的跨模块通信

模块之间不直接调用，而是发布集成事件。Notifications 模块是最直观的例子：它完全不关心 Users、Projects、Tasks 内部怎么工作，只订阅它们的公开事件。

事件契约放在每个模块的 `Contracts` 项目中，和模块接口一起，是少数可以对外公开的东西：

```csharp
// Tasks.Contracts/TaskEvents.cs
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

这些是 MediatR 的 `INotification` record，不可变、自描述、版本友好。Tasks 模块从自己的 `TasksModule` 发布它们：

```csharp
// Tasks.Application/TasksModule.cs (AssignTaskAsync)
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

Notifications 模块处理这个事件——不需要任何对 `Tasks.Application` 或 `Tasks.Infrastructure` 的依赖：

```csharp
// Notifications.Application/Handlers/EventHandlers.cs
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
            $"assigned to user {notification.UserId}";
        _notificationStore.Add(message);
        return Task.CompletedTask;
    }
}
```

这就是 MediatR 作为进程内中介者的典型用法——发布者和订阅者完全解耦。以后要加一个新模块来响应 `TaskAssignedEvent`（比如一个做工时统计的 Billing 模块），只加一个 handler 就行，Tasks 模块一行都不用改。

## 实践三：数据隔离

每个模块有自己的 `DbContext` 和自己的 SQLite 文件。这个约束在 Infrastructure 层强制执行。

```csharp
// Tasks.Infrastructure/TasksDbContext.cs
public sealed class TasksDbContext
    : DbContext, ITasksDbContext
{
    DbSet<TaskItem> ITasksDbContext.Tasks => Set<TaskItem>();

    public TasksDbContext(
        DbContextOptions<TasksDbContext> options) : base(options)
    {
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<TaskItem>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.ProjectId).IsRequired();
            entity.Property(e => e.Title)
                .IsRequired().HasMaxLength(200);
            entity.Property(e => e.Description).HasMaxLength(1000);
            entity.Property(e => e.Status).IsRequired();
            entity.Property(e => e.AssignedUserId);
            entity.Property(e => e.CreatedAt).IsRequired();
        });
    }
}
```

`TasksDbContext` 实现了 `ITasksDbContext`，这是 Application 层访问数据库的唯一途径。具体的 DbContext 实例不会暴露到 Infrastructure 项目之外。`ITasksDbContext` 接口抽象了 EF Core 的细节，单元测试也因此变得简单。

`TasksDbContext` 完全不知道 `UsersDbContext` 或 `ProjectsDbContext` 的存在。没有跨上下文的导航属性，没有共享的迁移历史，没有跨越模块边界的外键。如果 Tasks 模块需要知道用户信息，它只存储一个 `UserId`——按标识引用，不做 ORM 级别的连接查询。

将来要把某个模块抽成独立服务时，数据边界已经在那里了。你只需要把 SQLite 换成真正的数据库实例。

## 实践四：Host 中的模块组合

Host 项目（`Program.cs`）是组合根，唯一同时知道所有模块的地方。

```csharp
// Host/Program.cs
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddMediatR(cfg =>
{
    cfg.RegisterServicesFromAssembly(typeof(Program).Assembly);
    cfg.RegisterServicesFromAssembly(typeof(IUsersModule).Assembly);
    cfg.RegisterServicesFromAssembly(
        typeof(IProjectsModule).Assembly);
    cfg.RegisterServicesFromAssembly(
        typeof(ITasksModule).Assembly);
    cfg.RegisterServicesFromAssembly(
        typeof(INotificationsModule).Assembly);
});

builder.Services.AddUsersModule("Data Source=users.db");
builder.Services.AddProjectsModule("Data Source=projects.db");
builder.Services.AddTasksModule("Data Source=tasks.db");
builder.Services.AddNotificationsModule();

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var usersDb = scope.ServiceProvider
        .GetRequiredService<UsersDbContext>();
    await usersDb.Database.EnsureCreatedAsync();

    var projectsDb = scope.ServiceProvider
        .GetRequiredService<ProjectsDbContext>();
    await projectsDb.Database.EnsureCreatedAsync();

    var tasksDb = scope.ServiceProvider
        .GetRequiredService<TasksDbContext>();
    await tasksDb.Database.EnsureCreatedAsync();
}
```

MediatR 的注册是唯一让所有模块 Application 程序集同时出现的地方。这是有意为之——MediatR 需要扫描程序集来连接 handler，Host 是做这件事最合适的位置。每个模块的扩展方法内部自行处理它需要的所有东西。

Host 不需要知道任何一个模块的内部实现。它只知道模块存在、模块有公开接口。这是正确的耦合层次。

## API 层

`Program.cs` 里的 API 端点很薄。它们接收 HTTP 请求，调用对应的模块接口，返回结果。业务逻辑不放在这里。

```csharp
app.MapPost("/users",
    async (RegisterUserRequest request, IUsersModule usersModule) =>
{
    var result = await usersModule.RegisterUserAsync(
        request.Name, request.Email);
    return Results.Created($"/users/{result.UserId}", result);
});

app.MapPost("/projects",
    async (CreateProjectRequest request,
        IProjectsModule projectsModule) =>
{
    var result = await projectsModule.CreateProjectAsync(
        request.Name, request.Description);
    return Results.Created(
        $"/projects/{result.ProjectId}", result);
});

app.MapPost("/tasks/{id:guid}/assign",
    async (Guid id, AssignTaskRequest request,
        ITasksModule tasksModule) =>
{
    var result = await tasksModule.AssignTaskAsync(
        id, request.UserId);
    return result.Success
        ? Results.Ok(result)
        : Results.NotFound();
});

app.MapGet("/notifications",
    (INotificationsModule notificationsModule) =>
{
    var result = notificationsModule.GetRecentNotifications();
    return Results.Ok(result);
});
```

每个端点只依赖一个模块接口。`/tasks/{id}/assign` 这个调用会触发整条事件链：task 被分配，`TaskAssignedEvent` 发布，Notifications 模块的 `TaskAssignedEventHandler` 执行，一条通知被存储。所有这一切在进程内同步完成，没有网络开销。

## 和传统单体比，好在哪

传统单体长着长着就变成了大泥球。Service 互相调、Repository 随便共享、一个 Domain 的业务规则漏到另一个 Domain。团队意识到问题的时候，拆开它要好几个月。

模块化单体从第一天就开始解决问题：

- **可测试性。** 每个模块能独立测试。单元测试 mock `IProjectsModule`。集成测试只启动这个模块的 DbContext，不需要把整坨应用拉起来。Demo 的测试套件按模块拆分了 `UnitTests` 和 `IntegrationTests`。
- **可替换性。** Notifications 模块成瓶颈了？把内存实现换成正经的消息队列 handler。接口不用变，其他模块完全不知道。
- **通向微服务的路径。** 如果某个模块确实需要独立扩缩容，直接抽出去。数据边界已经在了，事件契约已经在了，接口已经在了。你不是在重构，只是换了部署方式。
- **新人上手更快。** 新人可以先吃透一个模块，不需要立刻理解整个系统。`internal` 关键字物理上阻止了他们不小心把东西耦到一起。

## 和微服务比，差在哪

差异不只是架构哲学的偏好，是实打实的运维现实。

| 维度 | 模块化单体 | 微服务 |
|---|---|---|
| 部署 | 单一进程 | 多个独立服务 |
| 通信 | 进程内、内存中 | 网络调用（HTTP、gRPC、消息总线） |
| 数据 | 独立 DbContext，同一进程 | 独立数据库，独立服务 |
| 故障模式 | 进程内异常 | 网络故障、超时、部分失败 |
| 开销 | 几乎为零 | 序列化、网络延迟、服务发现 |
| 团队结构 | 适合小到中型团队 | 需要每个服务有专门团队 |

Demo 里 `TasksModule` 发布 `TaskAssignedEvent` 的时候，MediatR 在同一进程、同一线程上把它交给 `TaskAssignedEventHandler`，没有序列化，没有重试逻辑，没有死信队列要管。这不是缺陷——它是在你需要快速迭代、快速交付的阶段里，合理的选择。

模块化单体用微服务 20% 的运维成本，拿到了它 80% 的组织收益。对大多数团队来说，这笔交易划得来。

## 常见问题

**和分层单体有什么区别？**

分层单体按技术关注点组织代码：Controllers、Services、Repositories、Data。模块化单体按业务领域组织。Projects 模块内部包含它的 Controllers、Services、Repositories 和数据。横切关注点通过事件或共享基础设施抽象处理，不是靠跨域调 Service 层。

**模块一定要用独立数据库吗？**

不必须，但至少要用独立的 DbContext 加独立的 schema 或表前缀。Demo 里用 SQLite，天然把文件分开。在生产环境你可能用一个 SQL Server 实例，每个模块一个 schema——`projects.Projects`、`tasks.Tasks`，诸如此类。目标是 ORM 层面不做跨模块 join。

**模块能同步通信吗？**

推荐的做法是通过 MediatR 做事件驱动通信。但如果确实需要同步读数据，模块也可以暴露只读的查询接口。规则只有一条：一个模块永远不直接修改另一个模块的数据。它可以通过约定的契约来读。

**跨多个模块的事务怎么处理？**

尽量避开。Demo 里 task 被分配时，Tasks 模块保存自己的状态然后发布事件。Notifications 模块在同一次请求里处理这个事件。如果通知写入失败，task 分配仍然成功。这是同一进程内的最终一致性——它比分布式事务简单太多，在绝大多数场景下是正确的取舍。

**团队扩大后怎么扩展？**

模块天然映射到团队所有权。每个模块是一个限界上下文，是小组或个人合理的代码所有权单元。`internal` 由编译器强制，这意味着康威定律在这里是正向作用的：团队边界和代码边界自然对齐。

**什么时候应该把模块抽成微服务？**

有数据驱动的明确理由时再动：模块有显著不同的扩容需求，你需要独立的部署周期，或者你的团队大到足以在线上自己伺候一个服务。不要预先抽取。等到痛点真实发生再说。模块化单体的价值就在于给了你这个选项，但不逼你现在就做决定。

**跨模块事件流在集成测试里怎么测？**

Demo 的集成测试项目展示了具体做法：用 `WebApplicationFactory` 在进程内启动完整应用，请求 API 端点，然后断言跨模块的状态结果。因为一切在进程内运行，事件处理路径不需要测试容器或消息总线模拟器。

## 总结

C# 模块化单体不是折中方案，它是一种有意识的架构选择。它给你强制的领域边界、可独立测试的模块，以及用到微服务的清晰迁移路径——同时还不需要第一天就背上分布式系统的运维脑负荷。

四条原则——单一部署、强制边界、独立数据、事件通信——相辅相成。项目结构把它们固化成约束。`internal` 关键字让编译器替你执行。MediatR 承担事件总线的角色，你不用自己造。

上手就从四层模块结构开始：Domain、Application、Infrastructure、Contracts。每个模块用自己的扩展方法注册。让 Host 做唯一的组合点。状态变化时发布集成事件。其余的事情会自然跟着这些决策走。

---

*如果你关注 .NET 架构、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的技术教程、架构观察和项目经验。*

## 参考

- [Modular Monolith in C#: Complete Implementation Guide for .NET Developers](https://www.devleader.ca/2026/07/06/modular-monolith-in-c-complete-implementation-guide-for-net-developers)
