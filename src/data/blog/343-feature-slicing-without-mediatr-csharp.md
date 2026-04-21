---
pubDatetime: 2026-04-20T08:17:09+08:00
title: "不用 MediatR 的 C# Feature Slicing：纯 Handler 直接干活"
description: "Feature slicing 的组织价值来自文件夹结构，而不是 MediatR。本文用 ASP.NET Core Minimal API 和纯 C# 类，从零搭建一个完整的 feature slice 架构，覆盖 handler 模式、跨切面关注点处理和 DI 注册，不依赖任何调度库。"
tags: ["CSharp", "ASP.NET Core", "Architecture", "Feature Slicing", "CQRS"]
slug: "feature-slicing-without-mediatr-csharp"
ogImage: "../../assets/343/01-cover.png"
source: "https://www.devleader.ca/2026/04/19/feature-slicing-without-mediatr-in-c-plain-handlers-that-actually-work"
---

几乎每一篇讲 C# feature slicing 的教程，最终都会走到同一个地方："这里你需要用 MediatR 来分发命令。"然后加一个 NuGet 包、一个 `IRequest<T>` 接口、一个 `CommandHandler : IRequestHandler<Command, Result>`，还有注册步骤和 pipeline behavior。

对很多团队来说，这些东西太多了。MediatR 从 v12 起对商业用途引入了收费许可证（具体条款请查阅 [MediatR 仓库](https://github.com/jbogard/MediatR)，政策可能变化）。间接层让堆栈追踪更难读，抽象层增加了团队需要学习和维护的概念。

关键结论摆在前面：**Feature slicing 不需要 MediatR。** 把代码组织成"一个 feature 一个文件夹"、用例自包含、职责清晰，这些好处来自文件夹结构本身，而不是任何调度库。本文用纯 C# 类和 ASP.NET Core Minimal API，从头搭一套可以直接用的 feature slice 架构。

## MediatR 到底解决了什么

在 feature-sliced 应用中，MediatR 解决两个问题：

- **Handler 发现**：给定一个命令对象，找到对应的 handler 类
- **Pipeline behavior**：把横切关注点（日志、验证、缓存）注入到分发路径中

不用 MediatR，这两个问题有直接的替代方案：

| MediatR 机制 | 纯 C# 替代 |
|---|---|
| `IRequest<T>` + `IRequestHandler<TRequest, TResult>` | 通过 DI 直接注入 handler 类 |
| `mediator.Send(command)` | `handler.HandleAsync(request)` |
| `IPipelineBehavior<TRequest, TResult>` | 装饰器模式或中间件 |
| assembly scan 自动注册 handler | `services.AddScoped<CreateTaskHandler>()` |

代价是：你写的代码会稍微显式一些。换来的是更少的抽象、更简单的依赖图、没有许可证顾虑。

## 搭一个完整的 feature slice

以任务管理应用为例，用户可以创建任务、完成任务、查询任务列表。

### Handler 模式

每个 feature 有一个 handler 类，带一个 `HandleAsync` 方法。不需要基类，也不需要接口：

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
            Title = request.Title.Trim(),
            Description = request.Description?.Trim(),
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

Handler 通过构造函数接收依赖，没有 `IMediator`。测试时只需构造 handler、传入真实或内存数据库上下文和假的 `TimeProvider`，调用 `HandleAsync` 验证结果即可。

### Endpoint 接线

Endpoint 把 HTTP 路由直接和 handler 连起来：

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
        .WithTags("Tasks")
        .Produces<CreateTaskResponse>(StatusCodes.Status201Created)
        .ProducesValidationProblem();
    }
}
```

ASP.NET Core 的 Minimal API DI 集成会从容器中自动解析 `CreateTaskHandler`。没有调度器，没有 pipeline——请求直接从 HTTP 绑定流到 handler。

### 状态变更 handler：CompleteTask

这个 handler 展示了更复杂的场景——更新已有状态并处理"找不到"的情况：

```csharp
// Features/Tasks/CompleteTask/CompleteTaskHandler.cs
namespace TaskTracker.Features.Tasks.CompleteTask;

public sealed record CompleteTaskResult(bool Found, bool AlreadyCompleted = false);

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

        if (task is null)
            return new CompleteTaskResult(Found: false);

        if (task.IsCompleted)
            return new CompleteTaskResult(Found: true, AlreadyCompleted: true);

        task.IsCompleted = true;
        task.CompletedAt = _time.GetUtcNow();

        await _db.SaveChangesAsync(cancellationToken);

        return new CompleteTaskResult(Found: true);
    }
}
```

```csharp
// Features/Tasks/CompleteTask/CompleteTaskEndpoint.cs
namespace TaskTracker.Features.Tasks.CompleteTask;

public static class CompleteTaskEndpoint
{
    public static void Map(IEndpointRouteBuilder routes)
    {
        routes.MapPost("/tasks/{taskId:guid}/complete", async (
            Guid taskId,
            CompleteTaskHandler handler,
            CancellationToken cancellationToken) =>
        {
            var result = await handler.HandleAsync(taskId, cancellationToken);

            return result switch
            {
                { Found: false } => Results.NotFound(),
                { AlreadyCompleted: true } => Results.Conflict("Task is already completed."),
                _ => Results.NoContent()
            };
        })
        .WithName("CompleteTask")
        .WithTags("Tasks");
    }
}
```

Handler 返回一个判别结果类型，而不是对预期业务状态抛异常。Endpoint 把这个结果翻译成对应的 HTTP 响应。业务逻辑和传输层分离得很清楚。

### 查询 handler：GetTasks

查询和命令遵循同样的模式——handler 类、请求类型、响应类型：

```csharp
// Features/Tasks/GetTasks/GetTasksQuery.cs
namespace TaskTracker.Features.Tasks.GetTasks;

public sealed record GetTasksQuery(Guid ProjectId, bool? IsCompleted = null);

public sealed record GetTasksResponse(
    Guid Id,
    string Title,
    bool IsCompleted,
    DateTimeOffset CreatedAt);

// Features/Tasks/GetTasks/GetTasksHandler.cs
namespace TaskTracker.Features.Tasks.GetTasks;

public sealed class GetTasksHandler
{
    private readonly AppDbContext _db;

    public GetTasksHandler(AppDbContext db) => _db = db;

    public async Task<IReadOnlyList<GetTasksResponse>> HandleAsync(
        GetTasksQuery query,
        CancellationToken cancellationToken = default)
    {
        var tasksQuery = _db.Tasks
            .Where(t => t.ProjectId == query.ProjectId)
            .AsQueryable();

        if (query.IsCompleted.HasValue)
            tasksQuery = tasksQuery.Where(t => t.IsCompleted == query.IsCompleted.Value);

        return await tasksQuery
            .OrderByDescending(t => t.CreatedAt)
            .Select(t => new GetTasksResponse(t.Id, t.Title, t.IsCompleted, t.CreatedAt))
            .ToListAsync(cancellationToken);
    }
}
```

## 不用 Pipeline 处理横切关注点

MediatR 用 `IPipelineBehavior<TRequest, TResponse>` 来插入日志、验证、性能监控等逻辑。没有 MediatR，有三种干净的替代方案：

### 方案一：装饰器模式

用装饰器包装 handler，通过组合（不是继承）添加行为。注意：不要继承具体 handler 类再用 `public new` 方法隐藏——如果装饰器被当作基类型存储或注入，额外行为会被无声绕过。

正确做法是写一个独立的包装类，持有内部 handler 作为依赖：

```csharp
// Shared/Decorators/LoggingCreateTaskHandler.cs
namespace TaskTracker.Shared.Decorators;

public sealed class LoggingCreateTaskHandler
{
    private readonly CreateTaskHandler _inner;
    private readonly ILogger<LoggingCreateTaskHandler> _logger;

    public LoggingCreateTaskHandler(
        CreateTaskHandler inner,
        ILogger<LoggingCreateTaskHandler> logger)
    {
        _inner = inner;
        _logger = logger;
    }

    public async Task<CreateTaskResponse> HandleAsync(
        CreateTaskRequest request,
        CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("Creating task: {Title}", request.Title);
        var stopwatch = Stopwatch.StartNew();

        var response = await _inner.HandleAsync(request, cancellationToken);

        _logger.LogInformation("Task created in {ElapsedMs}ms: {TaskId}",
            stopwatch.ElapsedMilliseconds, response.TaskId);

        return response;
    }
}
```

在 DI 中注册两个类，endpoint 改为接收 `LoggingCreateTaskHandler`：

```csharp
builder.Services.AddScoped<CreateTaskHandler>();
builder.Services.AddScoped<LoggingCreateTaskHandler>();
```

如果你需要多态（装饰器和真实 handler 可互换），可以定义一个最小接口，让两者都实现它。如果不想引入接口，endpoint 直接请求 `LoggingCreateTaskHandler` 即可。对于更复杂的场景，[Scrutor](https://github.com/khellang/Scrutor) 支持类似 MediatR pipeline behavior 的开放泛型装饰器。

### 方案二：中间件

对所有 HTTP 请求都适用的关注点（认证、异常处理、请求日志），应该放在 ASP.NET Core 中间件里，而不是 handler pipeline：

```csharp
app.UseMiddleware<RequestLoggingMiddleware>();
app.UseMiddleware<GlobalExceptionHandlerMiddleware>();
```

真正全局的关注点用中间件。只对特定 feature 有意义的关注点（输入验证、幂等性检查、领域范围的日志）用装饰器或 endpoint filter——中间件的范围太广了。

### 方案三：在 Endpoint 或 Handler 中内联验证

验证逻辑可以直接放在 endpoint 里，在调用 handler 之前执行：

```csharp
routes.MapPost("/tasks", async (
    CreateTaskRequest request,
    CreateTaskHandler handler,
    CreateTaskValidator validator,
    CancellationToken cancellationToken) =>
{
    var validationResult = validator.Validate(request);
    if (!validationResult.IsValid)
        return Results.ValidationProblem(validationResult.ToDictionary());

    var response = await handler.HandleAsync(request, cancellationToken);
    return Results.Created($"/tasks/{response.TaskId}", response);
});
```

也可以用 ASP.NET Core 内置的 endpoint filter，把验证做成可复用的过滤器：

```csharp
// Shared/Filters/ValidationFilter.cs
public sealed class ValidationFilter<TRequest> : IEndpointFilter
{
    private readonly IValidator<TRequest> _validator;

    public ValidationFilter(IValidator<TRequest> validator) => _validator = validator;

    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var request = context.Arguments.OfType<TRequest>().FirstOrDefault();

        if (request is not null)
        {
            var result = await _validator.ValidateAsync(request);
            if (!result.IsValid)
                return Results.ValidationProblem(result.ToDictionary());
        }

        return await next(context);
    }
}
```

然后在 endpoint 上挂载：

```csharp
routes.MapPost("/tasks", async (CreateTaskRequest request, CreateTaskHandler handler, ...) =>
{
    // ...
})
.AddEndpointFilter<ValidationFilter<CreateTaskRequest>>();
```

## Program.cs 中的注册

直接注册方式显式且清晰，中小型项目完全够用：

```csharp
builder.Services.AddScoped<CreateTaskHandler>();
builder.Services.AddScoped<CompleteTaskHandler>();
builder.Services.AddScoped<GetTasksHandler>();
builder.Services.AddScoped<CreateProjectHandler>();
builder.Services.AddScoped<GetProjectsHandler>();
```

对于大型项目，按约定扫描注册可以让 `Program.cs` 保持简短：

```csharp
// 使用 Scrutor
builder.Services.Scan(scan => scan
    .FromAssemblyOf<Program>()
    .AddClasses(classes => classes.Where(t => t.Name.EndsWith("Handler")))
    .AsSelf()
    .WithScopedLifetime());
```

这样你就拥有和 MediatR handler 扫描一样的自动发现能力，而不需要引入包依赖。

## MediatR 什么时候还值得用

说清楚：MediatR 本身没有问题。有些场景它是合理的选择：

- **复杂 pipeline behavior**，需要对每个命令以不同逻辑运行——MediatR 的泛型 `IPipelineBehavior<TRequest, TResponse>` 处理这个很干净
- **大型团队**，行为契约（`IRequest<T>` / `IRequestHandler<TRequest, TResult>`）能减少关于 handler 结构的分歧
- **已有 MediatR 的存量代码库**，移除它的代价超过了收益

重点不是 MediatR 不好，而是 feature slicing 不依赖它。组织价值是结构性的，而不是调度器给的。

## 常见问题

**Feature slicing 需要 MediatR 吗？**

不需要。Feature slicing 是基于文件夹结构和内聚性的代码组织方式。MediatR 是一些团队配合使用的调度库，两者是独立的。

**不用 MediatR 的 handler 更难测试吗？**

往往更简单。直接在测试里构造 handler 类并调用 `HandleAsync`，没有 mediator 需要 mock。handler 的依赖就是构造函数参数，在测试中直接传入即可。

**怎么让 Program.cs 不因为直接注册而越来越长？**

小项目显式注册没问题，可读性好。大项目用约定扫描（Scrutor 或自定义反射），把"所有名称以 Handler 结尾的类型都注册为 Scoped"做成一行代码搞定。

**没有 MediatR，还能用 CQRS 吗？**

当然可以。CQRS 是分离读写的设计模式，MediatR 是让 CQRS 分发更方便的机制。`CreateTaskHandler`（命令）和 `GetTasksHandler`（查询）放在不同文件夹里，CQRS 意图通过命名和结构就体现出来了，不需要任何调度框架。

---

MediatR v12 的许可证变化让很多团队开始评估替代方案。对于新项目，直接 handler 分发在 feature-sliced 结构下能给你 MediatR 大部分能力，而且依赖更少、移动部件更简单。

## 参考

- [Feature Slicing Without MediatR in C#: Plain Handlers That Actually Work](https://www.devleader.ca/2026/04/19/feature-slicing-without-mediatr-in-c-plain-handlers-that-actually-work) — Dev Leader
- [MediatR GitHub Repository](https://github.com/jbogard/MediatR)
- [Scrutor — Assembly scanning and decoration extensions for Microsoft.Extensions.DependencyInjection](https://github.com/khellang/Scrutor)
