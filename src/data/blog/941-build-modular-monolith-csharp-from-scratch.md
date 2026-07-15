---
pubDatetime: 2026-07-15T13:16:21+08:00
title: "从零构建 C# 模块化单体：一步步搭起来"
description: "模块化单体保留单体部署的简单性，同时用边界上下文隔离让大项目持续可维护。这篇从创建方案结构开始，一步步搭起 Projects 和 Tasks 两个模块，再通过 Contracts 集成事件和 MediatR 打通跨模块通信，代码全部来自可运行的参考工程。"
tags: ["模块化单体", "Modular Monolith", "ASP.NET Core", ".NET", "架构"]
slug: "build-modular-monolith-csharp-from-scratch"
ogImage: "../../assets/941/01-cover.png"
source: "https://www.devleader.ca/2026/07/14/how-to-build-a-modular-monolith-in-c-from-scratch-stepbystep-guide"
---

模块化单体这个说法你大概听说过不少次了，听多了就觉得这应该是个值得试试的架构。直觉没错——它保留了单体一次部署的简单，同时用边界上下文的隔离保证大项目持续可维护。

这篇从零起步，不靠模板，搭一个能跑起来的 .NET 9 模块化单体。先从 Projects 模块入手，然后接上 Tasks 模块，展示跨模块通信怎么做又不打破封装。所有代码都来自可运行的参考工程。

## 前提条件

- .NET 9 SDK，PATH 里能调到
- ASP.NET Core minimal API 的基础理解
- Entity Framework Core 基础（迁移、DbContext）
- NuGet 引入 MediatR（用来做进程内事件发布）

开发阶段用 SQLite，不需要跑数据库服务。

## 第一步：搭建方案结构

目录布局是模块化单体里最重要的决策。每个模块自带四层：Domain、Application、Infrastructure 和 Contracts。Host 项目只是薄薄的组合根，把它们全串起来。

```bash
dotnet new sln -n ModularMonolithDemo

# Host（组合根）
dotnet new webapi -n Host -o src/Host --no-https

# Projects 模块各层
dotnet new classlib -n Projects.Domain     -o src/Modules/Projects/Projects.Domain
dotnet new classlib -n Projects.Application -o src/Modules/Projects/Projects.Application
dotnet new classlib -n Projects.Infrastructure -o src/Modules/Projects/Projects.Infrastructure
dotnet new classlib -n Projects.Contracts  -o src/Modules/Projects/Projects.Contracts

# Tasks 模块（第七步用到）
dotnet new classlib -n Tasks.Domain        -o src/Modules/Tasks/Tasks.Domain
dotnet new classlib -n Tasks.Application   -o src/Modules/Tasks/Tasks.Application
dotnet new classlib -n Tasks.Infrastructure -o src/Modules/Tasks/Tasks.Infrastructure
dotnet new classlib -n Tasks.Contracts     -o src/Modules/Tasks/Tasks.Contracts

# Notifications 模块
dotnet new classlib -n Notifications.Application   -o src/Modules/Notifications/Notifications.Application
dotnet new classlib -n Notifications.Infrastructure -o src/Modules/Notifications/Notifications.Infrastructure

# 全部加入 solution
dotnet sln add src/Host/Host.csproj
dotnet sln add src/Modules/Projects/Projects.Domain/Projects.Domain.csproj
# ... 其余同理
```

依赖规则很严格：**Domain 不依赖任何东西**。Application 依赖 Domain，Infrastructure 依赖 Application。Contracts 只是薄薄一层，只有发布方和消费方会引用。

```bash
# Application 依赖 Domain 和 Contracts
dotnet add src/Modules/Projects/Projects.Application reference \
    src/Modules/Projects/Projects.Domain
dotnet add src/Modules/Projects/Projects.Application reference \
    src/Modules/Projects/Projects.Contracts

# Infrastructure 依赖 Application（传递依赖 Domain）
dotnet add src/Modules/Projects/Projects.Infrastructure reference \
    src/Modules/Projects/Projects.Application
```

这个引用图强制领域模型永不泄漏到模块之外。Host 项目只知道 Application 接口和 Infrastructure 扩展方法，碰不到领域内部细节。

## 第二步：Domain 层

Domain 层只放实体，别的什么都不放：没有 EF Core、没有 MediatR、没有 HTTP。纯粹的业务逻辑。

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
    public void Cancel()   => Status = ProjectStatus.Cancelled;
}
```

私有构造函数 + 静态 `Create` 工厂方法确保每个 `Project` 实例创建时就是合法的。实体是 `internal sealed`，Domain 程序集之外没法直接实例化。

## 第三步：Application 层

Application 层定义了三样东西：**公开接口** `IProjectsModule`、**内部 DbContext 接口** `IProjectsDbContext`、**内部实现** `ProjectsModule`。

公开接口只用基本类型和 record，不暴露 Domain 类型、不暴露 EF Core 类型，消费者不会背上额外依赖。这是模块化单体的关键规矩。

```csharp
namespace Projects.Application;

public interface IProjectsModule
{
    Task<CreateProjectResult> CreateProjectAsync(
        string name, string description,
        CancellationToken cancellationToken = default);
    Task<GetProjectResult?> GetProjectAsync(
        Guid projectId,
        CancellationToken cancellationToken = default);
    Task<IReadOnlyList<ProjectListResult>> ListProjectsAsync(
        CancellationToken cancellationToken = default);
}

public sealed record CreateProjectResult(
    Guid ProjectId, string Name, string Description);
public sealed record GetProjectResult(
    Guid ProjectId, string Name, string Description, string Status);
public sealed record ProjectListResult(
    Guid ProjectId, string Name, string Status);
```

实现里注入 MediatR 的 `IPublisher`，保存之后发布 `ProjectCreatedEvent`——这就是跨模块信号，其他模块（比如 Notifications）可以响应，而 Projects 模块完全不关心谁在听。

```csharp
public async Task<CreateProjectResult> CreateProjectAsync(
    string name, string description,
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
```

## 第四步：Infrastructure 层

Infrastructure 层提供 EF Core 实现，并且负责向 DI 容器注册一切。

```csharp
namespace Projects.Infrastructure;

public sealed class ProjectsDbContext : DbContext, IProjectsDbContext
{
    DbSet<Project> IProjectsDbContext.Projects => Set<Project>();

    public ProjectsDbContext(
        DbContextOptions<ProjectsDbContext> options) : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Project>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Name)
                .IsRequired().HasMaxLength(200);
            entity.Property(e => e.Description).HasMaxLength(1000);
        });
    }
}
```

`DbSet<Project>` 通过显式接口实现暴露，保证 `ProjectsDbContext` 不会把实体类型泄漏到 Application 接口允许之外。

注册方法：

```csharp
public static class ProjectsModuleExtensions
{
    public static IServiceCollection AddProjectsModule(
        this IServiceCollection services, string connectionString)
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

Host 只需要调一个 `AddProjectsModule`，模块里啥都藏好了。

## 第五步：Contracts 集成事件

Contracts 程序集很薄，只放集成事件。一个模块广播事件时，消费者只需要引用 Contracts，不需要引用 Application 或 Domain。

```csharp
using MediatR;

namespace Projects.Contracts;

public sealed record ProjectCreatedEvent(
    Guid ProjectId, string Name, string Description) : INotification;
```

这就是整个文件。Contracts 的职责是为模块之间提供共享词汇，不放任何逻辑。

## 第六步：Host 组合根

Host 的 `Program.cs` 是组合根。它知道所有模块以便注册它们，但不含业务逻辑。

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddMediatR(cfg =>
{
    cfg.RegisterServicesFromAssembly(typeof(Program).Assembly);
    cfg.RegisterServicesFromAssembly(typeof(IProjectsModule).Assembly);
    cfg.RegisterServicesFromAssembly(typeof(ITasksModule).Assembly);
});

builder.Services.AddProjectsModule("Data Source=projects.db");
builder.Services.AddTasksModule("Data Source=tasks.db");
builder.Services.AddNotificationsModule();

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var projectsDb = scope.ServiceProvider
        .GetRequiredService<ProjectsDbContext>();
    await projectsDb.Database.EnsureCreatedAsync();
}

app.MapPost("/projects",
    async (CreateProjectRequest request, IProjectsModule module) =>
{
    var result = await module.CreateProjectAsync(
        request.Name, request.Description);
    return Results.Created($"/projects/{result.ProjectId}", result);
});

app.MapGet("/projects/{id:guid}",
    async (Guid id, IProjectsModule module) =>
{
    var result = await module.GetProjectAsync(id);
    return result == null ? Results.NotFound() : Results.Ok(result);
});

app.Run();
```

从 Host 的视角看，每个模块都一样：调扩展方法、注入接口。Host 永远不会伸进模块内部。

## 第七步：加第二个模块

模块化单体的真正检验是第二个模块能否保持规则。核心原则：**Tasks.Application 绝不能引用 Projects.Application**。如果需要处理 `ProjectCreatedEvent`，只引用 `Projects.Contracts`。

`ITasksModule` 形状和 `IProjectsModule` 一致：

```csharp
public interface ITasksModule
{
    Task<CreateTaskResult> CreateTaskAsync(
        Guid projectId, string title, string description,
        CancellationToken cancellationToken = default);
    Task<AssignTaskResult> AssignTaskAsync(
        Guid taskId, Guid userId,
        CancellationToken cancellationToken = default);
    Task<CompleteTaskResult> CompleteTaskAsync(
        Guid taskId, CancellationToken cancellationToken = default);
}
```

注册扩展方法形状也一样：

```csharp
public static IServiceCollection AddTasksModule(
    this IServiceCollection services, string connectionString)
{
    services.AddDbContext<TasksDbContext>(options =>
        options.UseSqlite(connectionString));
    services.AddScoped<ITasksDbContext>(
        sp => sp.GetRequiredService<TasksDbContext>());
    services.AddScoped<ITasksModule, TasksModule>();
    return services;
}
```

模式一目了然：每个模块都是自带存储、自带接口、自带注册方法的独立垂直切片。不用共享 DbContext，不用共享 Service，不用共享实体。

## 第八步：跨模块通信

跨模块通信靠 Contracts 事件和 MediatR 的 `IPublisher`。Tasks 模块在分配任务时发布 `TaskAssignedEvent`：

```csharp
// Tasks.Contracts
public sealed record TaskAssignedEvent(
    Guid TaskId, Guid ProjectId,
    Guid UserId, string TaskTitle) : INotification;
```

Notifications 模块监听这个事件，但它只知道 `Tasks.Contracts`，完全不知道 Tasks 模块内部的任何东西：

```csharp
internal sealed class TaskAssignedEventHandler
    : INotificationHandler<TaskAssignedEvent>
{
    private readonly INotificationStore _store;

    public TaskAssignedEventHandler(INotificationStore store) =>
        _store = store;

    public Task Handle(
        TaskAssignedEvent notification,
        CancellationToken cancellationToken)
    {
        _store.Add(
            $"Task assigned: {notification.TaskTitle} " +
            $"to user {notification.UserId}");
        return Task.CompletedTask;
    }
}
```

解耦是彻底的：Tasks 发事件——不知道有没有人听；Notifications 响应事件——不知道从哪来的。是 Observer 模式通过 MediatR 在内部跑的发布/订阅。

## 怎么看它跑通了没有

集成测试最实在。用 `WebApplicationFactory<Program>` 跑全链路：

```csharp
public class TaskAssignmentIntegrationTests
    : IClassFixture<WebApplicationFactory<Program>>
{
    [Fact]
    public async Task AssignTask_TriggersNotificationHandler()
    {
        var client = _factory.CreateClient();

        // 建用户
        var userResp = await client.PostAsJsonAsync(
            "/users", new { Name = "John", Email = "john@test.com" });
        var userId = (await userResp.Content
            .ReadFromJsonAsync<UserResult>())!.UserId;

        // 建项目
        var projResp = await client.PostAsJsonAsync(
            "/projects", new { Name = "P1", Description = "D1" });
        var projectId = (await projResp.Content
            .ReadFromJsonAsync<ProjectResult>())!.ProjectId;

        // 建任务并分配
        var taskResp = await client.PostAsJsonAsync(
            "/tasks", new { ProjectId = projectId,
                Title = "Test Task", Description = "Test" });
        var taskId = (await taskResp.Content
            .ReadFromJsonAsync<TaskResult>())!.TaskId;

        await client.PostAsJsonAsync(
            $"/tasks/{taskId}/assign", new { UserId = userId });

        // 验证跨模块通知
        var notifResp = await client.GetAsync("/notifications");
        var notifications = await notifResp.Content
            .ReadFromJsonAsync<List<string>>();

        Assert.Contains(notifications,
            n => n.Contains("Task assigned"));
    }
}
```

这个测试穿过三个不同模块——Users、Projects、Tasks——通过 HTTP 端点，然后验证 Notifications 模块收到了跨模块事件。没有 mock，没有 fake，跑的是真实管线。

## 小结

在 .NET 9 里从零搭一个模块化单体的路线很清楚：

1. **Domain 层**纯业务实体，不依赖任何东西
2. **Application 层**对外暴露接口和 record，收口内部实现
3. **Infrastructure 层**提供 EF Core 实现和 DI 注册
4. **Contracts 层**只放集成事件，模块之间只通过事件通信
5. **Host** 是薄薄的组合根，只负责注册和路由

核心纪律由项目引用层硬约束，不是靠约定。Application 层之间互相引用不了对方的类型时，意外的耦合就变成了编译错误而不是 code review 里的一句话。

## 参考

- [原文链接](https://www.devleader.ca/2026/07/14/how-to-build-a-modular-monolith-in-c-from-scratch-stepbystep-guide)
