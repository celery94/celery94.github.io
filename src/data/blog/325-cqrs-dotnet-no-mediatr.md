---
pubDatetime: 2025-05-18
tags: [.NET, CQRS, Clean Architecture, MediatR, 企业应用, 架构设计, 后端开发]
slug: cqrs-dotnet-no-mediatr
source: https://www.milanjovanovic.tech/blog/cqrs-pattern-the-way-it-should-have-been-from-the-start
title: 不依赖MediatR，打造更轻量的.NET CQRS架构 —— 从源码到生产的实战演绎
description: MediatR转向商业化后，越来越多.NET团队开始重新思考CQRS实现之道。本文从实际工程出发，手把手教你用最简单的接口与装饰器模式，实现可维护、可扩展、易测试的CQRS应用管道，并附真实代码与架构剖析，助力你的企业级项目走得更远！
---

# 不依赖MediatR，打造更轻量的.NET CQRS架构 —— 从源码到生产的实战演绎

## 引言：MediatR商业化，.NET团队该如何选择？

2024年，MediatR宣布对企业用户采取商业授权，这无疑让不少.NET团队陷入了技术选型的再思考。对于关注可维护性、扩展性和团队自控力的开发者而言，“CQRS=使用MediatR”已经不再是唯一答案。  
事实上，CQRS（命令查询职责分离）是一种思想和设计模式，而非某个库的专利。有没有更优雅、更可控的方法实现CQRS？答案是肯定的！本文将带你用最简洁的接口与装饰器实现方式，搭建一套轻量级CQRS管道，让你的架构既专业又透明，代码风格也更加.NET原生。

## 为什么要“去MediatR”？CQRS本质与团队收益

在许多企业项目中，MediatR常被用作命令与查询分发器，但其实际“魔法”大部分都可以由简单、可控的接口与装饰器模式替代。  
摒弃MediatR，你将获得：

- 🔍 代码执行路径完全可控，调试和排查更直观
- 💡 DI依赖关系简洁明确，减少“黑盒”魔法
- 🚦 更易于定制扩展，例如日志、验证、事务等横切逻辑
- 🧪 测试友好、团队上手快

> CQRS本质在于**意图分离**：写操作(Command)和读操作(Query)各自独立，不混淆。

## 核心实现步骤 & 代码实录

### 一、定义基础接口——让命令与查询各司其职

我们只需要几个Marker Interface（标记接口）：

```csharp
// ICommand.cs
public interface ICommand;
public interface ICommand<TResponse>;

// IQuery.cs
public interface IQuery<TResponse>;
```

紧接着，定义Handler合约：

```csharp
// ICommandHandler.cs
public interface ICommandHandler<in TCommand>
    where TCommand : ICommand
{
    Task<Result> Handle(TCommand command, CancellationToken cancellationToken);
}

public interface ICommandHandler<in TCommand, TResponse>
    where TCommand : ICommand<TResponse>
{
    Task<Result<TResponse>> Handle(TCommand command, CancellationToken cancellationToken);
}

// IQueryHandler.cs
public interface IQueryHandler<in TQuery, TResponse>
    where TQuery : IQuery<TResponse>
{
    Task<Result<TResponse>> Handle(TQuery query, CancellationToken cancellationToken);
}
```

这些接口极其精简，却为后续所有扩展打下了坚实基础。

### 二、实战演练：命令处理器实现

以“完成待办事项”为例：

```csharp
// CompleteTodoCommand.cs
public sealed record CompleteTodoCommand(Guid TodoItemId) : ICommand;

// CompleteTodoCommandHandler.cs
internal sealed class CompleteTodoCommandHandler(
    IApplicationDbContext context,
    IDateTimeProvider dateTimeProvider,
    IUserContext userContext)
    : ICommandHandler<CompleteTodoCommand>
{
    public async Task<Result> Handle(CompleteTodoCommand command, CancellationToken cancellationToken)
    {
        TodoItem? todoItem = await context.TodoItems
            .SingleOrDefaultAsync(
                t => t.Id == command.TodoItemId && t.UserId == userContext.UserId,
                cancellationToken);

        if (todoItem is null)
            return Result.Failure(TodoItemErrors.NotFound(command.TodoItemId));

        if (todoItem.IsCompleted)
            return Result.Failure(TodoItemErrors.AlreadyCompleted(command.TodoItemId));

        todoItem.IsCompleted = true;
        todoItem.CompletedAt = dateTimeProvider.UtcNow;
        todoItem.Raise(new TodoItemCompletedDomainEvent(todoItem.Id));

        await context.SaveChangesAsync(cancellationToken);
        return Result.Success();
    }
}
```

_每一个命令都是一个不可变对象（record），Handler专注业务逻辑，无需任何“魔法分发”。_

### 三、装饰器模式：日志、验证等横切关注点优雅插入

#### 日志装饰器

```csharp
internal sealed class LoggingCommandHandler<TCommand, TResponse>(
    ICommandHandler<TCommand, TResponse> innerHandler,
    ILogger<CommandHandler<TCommand, TResponse>> logger)
    : ICommandHandler<TCommand, TResponse>
    where TCommand : ICommand<TResponse>
{
    public async Task<Result<TResponse>> Handle(TCommand command, CancellationToken cancellationToken)
    {
        logger.LogInformation("Processing command {Command}", typeof(TCommand).Name);
        Result<TResponse> result = await innerHandler.Handle(command, cancellationToken);

        if (result.IsSuccess)
            logger.LogInformation("Completed command {Command}", typeof(TCommand).Name);
        else
            logger.LogError("Completed command {Command} with error", typeof(TCommand).Name);

        return result;
    }
}
```

#### 验证装饰器（以FluentValidation为例）

```csharp
internal sealed class ValidationCommandHandler<TCommand, TResponse>(
    ICommandHandler<TCommand, TResponse> innerHandler,
    IEnumerable<IValidator<TCommand>> validators)
    : ICommandHandler<TCommand, TResponse>
    where TCommand : ICommand<TResponse>
{
    public async Task<Result<TResponse>> Handle(TCommand command, CancellationToken cancellationToken)
    {
        // 验证逻辑略...
        // 通过则调用 innerHandler.Handle
        // 否则直接返回错误
    }
}
```

_每个装饰器只关心一件事，可以自由组合和扩展。_

### 四、依赖注入 & 装饰器注册——Scrutor助力自动化

利用[Scrutor](https://github.com/khellang/Scrutor)自动扫描并注册所有handler：

```csharp
services.Scan(scan => scan.FromAssembliesOf(typeof(DependencyInjection))
    .AddClasses(classes => classes.AssignableTo(typeof(IQueryHandler<,>)), publicOnly: false)
        .AsImplementedInterfaces().WithScopedLifetime()
    .AddClasses(classes => classes.AssignableTo(typeof(ICommandHandler<>)), publicOnly: false)
        .AsImplementedInterfaces().WithScopedLifetime()
    .AddClasses(classes => classes.AssignableTo(typeof(ICommandHandler<,>)), publicOnly: false)
        .AsImplementedInterfaces().WithScopedLifetime());
```

装饰器注册示例：

```csharp
services.Decorate(typeof(ICommandHandler<,>), typeof(ValidationDecorator.CommandHandler<,>));
services.Decorate(typeof(IQueryHandler<,>), typeof(LoggingDecorator.QueryHandler<,>));
// 顺序很重要，最外层先注册
```

### 五、API调用体验：无“ISender”，直接注入清晰明了

在Minimal API或Controller中直接注入ICommandHandler即可：

```csharp
app.MapPut("todos/{id:guid}/complete", async (
    Guid id,
    ICommandHandler<CompleteTodoCommand> handler,
    CancellationToken cancellationToken) =>
{
    var command = new CompleteTodoCommand(id);
    Result result = await handler.Handle(command, cancellationToken);
    return result.Match(Results.NoContent, CustomResults.Problem);
});
```

_调用链直观、类型安全，消除中间“魔法”层。_

## 结论：让CQRS回归本质，为企业应用保驾护航 🚀

CQRS不等于MediatR，也不需要复杂的第三方框架。一组简单接口，加上装饰器和自动扫描注册，你就拥有了完全可控、可扩展、易于测试的现代企业级架构。  
别再迷信“黑盒魔法”，拥抱自解释、自管理的代码体系吧！
