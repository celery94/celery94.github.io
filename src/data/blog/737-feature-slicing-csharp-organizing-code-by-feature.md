---
pubDatetime: 2026-04-16T10:33:00+08:00
title: "C# 功能切片：按业务功能组织代码"
description: "功能切片（Feature Slicing）是一种将代码按业务功能而非技术层次组织的方式。本文以 ASP.NET Core Minimal APIs 为例，展示如何构建真实的功能切片，包括请求/响应模型、处理器和端点的完整实现，无需 MediatR。"
tags: ["C#", ".NET", "架构", "代码组织", "ASP.NET Core", "Feature Slicing"]
slug: "feature-slicing-csharp-organizing-code-by-feature"
ogImage: "../../assets/737/01-cover.jpg"
source: "https://www.devleader.ca/2026/04/15/feature-slicing-in-c-organizing-code-by-feature"
---

![C# 功能切片：按业务功能组织代码](../../assets/737/01-cover.jpg)

打开一个 .NET 项目，发现要找"创建任务"的逻辑，需要翻 `Controllers`、`Services`、`Repositories`、`Models` 四个文件夹，每个里面找一个文件。这是分层架构的日常。规模小时感觉整洁，规模一大，改一个功能就要横跨四层。

**功能切片（Feature Slicing）** 的思路是：把一个功能所需的所有代码放到同一个文件夹里。

## 分层架构的问题

大多数 .NET 项目一开始是这样的结构：

```
TaskTracker/
  Controllers/
    TaskController.cs
    ProjectController.cs
    UserController.cs
  Services/
    TaskService.cs
    ProjectService.cs
    UserService.cs
  Repositories/
    TaskRepository.cs
    ProjectRepository.cs
    UserRepository.cs
  Models/
    TaskEntity.cs
    ProjectEntity.cs
```

要给"标记任务为完成"加功能，需要同时修改 `TaskController.cs`、`TaskService.cs`、`TaskRepository.cs`，可能还有 `TaskEntity.cs`。四个文件夹，四个文件。排查一个 bug 要在四层之间来回切换。

随着项目增长，Service 类积累了不相关功能的方法，Repository 变成上帝类，单个功能的内聚性不断下降。

## 功能切片长什么样

核心思路：按**做什么**分组，而不是按**是什么类型的代码**分组。

同一个任务追踪器，改用功能切片后：

```
TaskTracker/
  Features/
    Tasks/
      CreateTask/
        CreateTaskEndpoint.cs
        CreateTaskHandler.cs
        CreateTaskRequest.cs
        CreateTaskResponse.cs
      CompleteTask/
        CompleteTaskEndpoint.cs
        CompleteTaskHandler.cs
        CompleteTaskRequest.cs
      GetTasks/
        GetTasksEndpoint.cs
        GetTasksHandler.cs
        GetTasksResponse.cs
    Projects/
      CreateProject/
        CreateProjectEndpoint.cs
        CreateProjectHandler.cs
        CreateProjectRequest.cs
      GetProjects/
        GetProjectsEndpoint.cs
        GetProjectsHandler.cs
        GetProjectsResponse.cs
  Shared/
    Data/
      AppDbContext.cs
    Entities/
      TaskEntity.cs
      ProjectEntity.cs
  Program.cs
```

`CompleteTask` 拥有自己的端点、处理器和输入/输出类型。出了问题，打开 `CompleteTask` 文件夹，调查从这里开始，也在这里结束。

## 构建第一个功能切片

以 `CreateTask` 为例，使用 .NET 8/10 的 ASP.NET Core Minimal APIs，只依赖 Entity Framework Core，不引入 MediatR 等额外库。

### 请求和响应模型

每个切片有自己的数据契约，不与其他功能共享：

```csharp
// Features/Tasks/CreateTask/CreateTaskRequest.cs
namespace TaskTracker.Features.Tasks.CreateTask;

public sealed record CreateTaskRequest(
    string Title,
    string Description,
    Guid ProjectId);
```

```csharp
// Features/Tasks/CreateTask/CreateTaskResponse.cs
namespace TaskTracker.Features.Tasks.CreateTask;

public sealed record CreateTaskResponse(
    Guid TaskId,
    string Title,
    DateTimeOffset CreatedAt);
```

比如 `GetTasks` 也需要任务数据，它会定义自己的响应类型，只包含那个功能实际需要的字段。这种重复是有意为之——每个切片拥有自己的契约。

如果你对外发布稳定的 API 契约，可能需要在那个边界使用共享 DTO；但对于内部用例，每功能各自定义类型能保持切片独立。

### 处理器

处理器包含这个功能的业务逻辑，是一个普通的 C# 类，没有任何框架仪式：

```csharp
// Features/Tasks/CreateTask/CreateTaskHandler.cs
namespace TaskTracker.Features.Tasks.CreateTask;

public sealed class CreateTaskHandler
{
    private readonly AppDbContext _db;
    private readonly TimeProvider _time;

    public CreateTaskHandler(AppDbContext db, TimeProvider time)
    {
        _db = db;
        _time = time;
    }

    public async Task<CreateTaskResponse> HandleAsync(
        CreateTaskRequest request,
        CancellationToken cancellationToken = default)
    {
        var task = new TaskEntity
        {
            Id = Guid.NewGuid(),
            Title = request.Title,
            Description = request.Description,
            ProjectId = request.ProjectId,
            CreatedAt = _time.GetUtcNow(),
            IsCompleted = false
        };

        _db.Tasks.Add(task);
        await _db.SaveChangesAsync(cancellationToken);

        return new CreateTaskResponse(task.Id, task.Title, task.CreatedAt);
    }
}
```

没有包裹抽象的抽象，没有需要追踪的中介管道。一个接收请求、返回响应的类。可以通过提供真实或内存中的 `AppDbContext` 直接测试它。

### 端点

端点负责把 HTTP 路由和处理器连接起来：

```csharp
// Features/Tasks/CreateTask/CreateTaskEndpoint.cs
namespace TaskTracker.Features.Tasks.CreateTask;

public static class CreateTaskEndpoint
{
    public static void Map(IEndpointRouteBuilder routes)
    {
        routes.MapPost("/tasks", async (
            CreateTaskRequest request,
            CreateTaskHandler handler,
            CancellationToken cancellationToken) =>
        {
            var response = await handler.HandleAsync(request, cancellationToken);
            return Results.Created($"/tasks/{response.TaskId}", response);
        })
        .WithName("CreateTask")
        .WithTags("Tasks");
    }
}
```

### 注册到 Program.cs

在 `Program.cs` 中的注册清晰易读：

```csharp
// Program.cs
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlite(builder.Configuration.GetConnectionString("Default")));

// 每个功能注册一个处理器
builder.Services.AddScoped<CreateTaskHandler>();
builder.Services.AddScoped<CompleteTaskHandler>();
builder.Services.AddScoped<GetTasksHandler>();
builder.Services.AddScoped<CreateProjectHandler>();
builder.Services.AddScoped<GetProjectsHandler>();

var app = builder.Build();

// 每个功能映射一个端点
CreateTaskEndpoint.Map(app);
CompleteTaskEndpoint.Map(app);
GetTasksEndpoint.Map(app);
CreateProjectEndpoint.Map(app);
GetProjectsEndpoint.Map(app);

app.Run();
```

项目增长后，可以用反射或 Scrutor 自动化注册。早期开发阶段保持显式注册更便于追踪和调试。如果你要启用裁剪（trimming）或 Native AOT 发布，则优先使用显式注册或源生成器方式——反射扫描在没有显式根的情况下可能失效。

## 实际能感受到的优势

**查找代码变得可预期。** "完成任务"出了 bug，打开 `Features/Tasks/CompleteTask/` 就能找到所有相关代码。

**添加功能是增量式的，不会影响现有代码。** 新的功能切片不会触及已有代码，只需新建一个文件夹和几个文件，然后在 `Program.cs` 中注册。

**团队所有权和文件夹结构对齐。** 负责任务管理的开发者不需要了解项目管理的实现细节。

**删除功能很干净。** 如果功能真正隔离，删除它只需移除文件夹和注册行。如果涉及共享数据库迁移、授权策略或跨功能依赖，删除前要先审计这些部分。

**测试结构与功能结构镜像。** 测试项目可以用同样的 `Features/FeatureName/` 结构，每个功能一个测试文件，范围清晰。

## Shared 文件夹放什么

功能切片自包含，但有些东西确实是多个功能共同需要的，放在 `Shared/` 中：

- **AppDbContext**：所有功能共用一个数据库上下文
- **实体模型**：数据库表定义（不是 DTO，DTO 留在各功能内）
- **基础设施**：认证中间件、全局异常处理器
- **通用工具**：日期辅助、字符串扩展等真正通用的代码

实践判断标准：如果两个**不相关**的功能独立需要同一个概念，把它移到 `Shared/`。如果只有一个功能使用它，即便看起来将来可能被复用，也先放在那个功能的文件夹里。过早共享会制造和分层架构同样的耦合问题，只是换了个文件夹。

## 与垂直切片架构的关系

功能切片和**垂直切片架构（Vertical Slice Architecture）** 的概念高度重叠，但并不完全相同：

- **功能切片**指的是代码组织实践：一个文件夹对应一个功能，所有相关代码放在一起
- **垂直切片架构**在此基础上还包含用例边界约定，通常意味着 CQRS 和派发模式

这里展示的做法把 MediatR 视为可选的基础设施，而非必要依赖——它对日志和验证等管道行为有用，但不是获得组织化收益的前提。功能切片也与 CQRS 自然契合：当每个功能已经有了命令和查询对象，CQRS 的区分就变成命名和设计约定，而非结构变化。

## 适用场景

功能切片适合：

- 功能**独立演化**的应用（大多数 Web API 和 CRUD 类应用）
- **多人或多团队**协作的代码库
- 需要**快速交付**、希望每个新功能都是低风险增量的项目
- 想要**降低新人上手成本**的项目

在以下情况值得暂停考虑：

- 单个开发者、不足十个端点的小项目——开销是真实存在的，即便不大
- 共享领域逻辑真正跨越很多功能的应用，领域中心模型可能更合适
- 严格践行领域驱动设计、以领域模型为首要组织单元的团队

## 渐进式引入

功能切片不需要全面重写。选下一个要构建的功能，创建 `Features/FeatureName/` 文件夹，把它组织成切片。保留现有的分层代码，按能力逐步迁移。

目标不是完美的文件夹结构，而是更容易修改、更容易理解、更容易测试的代码。功能切片让你一次一个功能地向这个目标靠近。

## 参考

- [Feature Slicing in C#: Organizing Code by Feature](https://www.devleader.ca/2026/04/15/feature-slicing-in-c-organizing-code-by-feature)
- [Vertical Slice Architecture in C# - Examples on How to Streamline Code](https://www.devleader.ca/2023/10/03/vertical-slice-architecture-in-c-examples-on-how-to-streamline-code)
- [How to Master Vertical Slice Architecture - Techniques and Examples](https://www.devleader.ca/2023/10/12/how-to-master-vertical-slice-architecture-techniques-and-examples)
- [From Chaos to Cohesion: How To Organize Code For Vertical Slices](https://www.devleader.ca/2023/10/09/from-chaos-to-cohesion-how-to-organize-code-for-vertical-slices)
