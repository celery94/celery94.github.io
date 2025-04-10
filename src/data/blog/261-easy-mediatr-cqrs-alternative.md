---
pubDatetime: 2025-04-10 12:37:03
tags: [C#, .NET, CQRS, Mediator, 开发者工具]
slug: easy-mediatr-cqrs-alternative
source: https://dev.to/criscoelho/developing-your-easy-alternative-to-the-mediatr-library-in-c-1og2
title: 为C#/.NET项目开发一个简单的MediatR替代方案：实现CQRS模式
description: 本文深入探讨如何为C#/.NET开发一个简单的CQRS模式替代方案，取代被广泛使用的MediatR库。通过四个接口和调度器的实现，轻松打造属于自己的中介者模式。
---

# 为C#/.NET项目开发一个简单的MediatR替代方案：实现CQRS模式 🚀

近年来，**MediatR** 库因其在实现CQRS（Command Query Responsibility Segregation）模式中的优秀表现，成为了C#/.NET开发者的首选。然而，最近有传言称该库将由开源转为商业化，这引发了社区广泛关注。🤔

如果您也在寻找一种轻量级替代方案，希望摆脱对外部库的依赖，那么本文将为您提供一条清晰的实现路径！我们将通过简单的接口和调度器，实现基本的命令与查询分离，让您的项目更灵活、更高效。

## 为什么需要一个替代方案？🤷‍♂️

MediatR 由著名开发者 **Jimmy Bogard** 创建，他同时也是 AutoMapper 的作者。虽然这两个库在.NET开发中发挥了重要作用，但随着它们商业化的消息传出，许多开发者开始考虑替代方案。

其实，无论是CQRS还是Mediator模式，开发者都可以自行实现基本功能，以满足大多数应用场景的需求。本篇文章将向您展示如何一步步实现一个轻量级的 CQRS 替代方案。

---

## 实现替代方案的步骤 🛠️

### 第一步：创建接口

我们需要定义四个接口来支持命令和查询操作。这些接口是系统中所有命令处理器和查询处理器的基础：

1. **IQueryHandler**  
   定义查询处理器。
   ![IQueryHandler](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fd66gcaaqm14fz7p4qfob.png)

2. **IQueryDispatcher**  
   定义查询调度器。
   ![IQueryDispatcher](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2F8ytznkei5jxagxe051mi.png)

3. **ICommandHandler**  
   定义命令处理器。
   ![ICommandHandler](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fsp1ea81kib0gr5n7fltf.png)

4. **ICommandDispatcher**  
   定义命令调度器。
   ![ICommandDispatcher](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2F7spp7e9jaq4l9nqn0ayh.png)

---

### 第二步：实现调度器

调度器的核心功能是通过 `IServiceProvider` 动态获取具体的处理器实例，并执行查询或命令操作。

#### 查询调度器

```csharp
public class QueryDispatcher : IQueryDispatcher
{
    private readonly IServiceProvider _serviceProvider;

    public QueryDispatcher(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public TResult Dispatch<TQuery, TResult>(TQuery query) where TQuery : class
    {
        var handler = _serviceProvider.GetService<IQueryHandler<TQuery, TResult>>();
        return handler.Handle(query);
    }
}
```

#### 命令调度器

```csharp
public class CommandDispatcher : ICommandDispatcher
{
    private readonly IServiceProvider _serviceProvider;

    public CommandDispatcher(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public void Dispatch<TCommand>(TCommand command) where TCommand : class
    {
        var handler = _serviceProvider.GetService<ICommandHandler<TCommand>>();
        handler.Handle(command);
    }
}
```

---

### 第三步：实现查询与处理逻辑 🌟

接下来，我们以用户查询为例，创建以下内容：

#### 1. 数据传输对象（DTO）

```csharp
public class UserResponseDto
{
    public int Id { get; set; }
    public string Name { get; set; }
}
```

#### 2. 查询类

```csharp
public class GetUserByIdQuery
{
    public int Id { get; set; }

    public GetUserByIdQuery(int id)
    {
        Id = id;
    }
}
```

#### 3. 查询处理器

```csharp
public class GetUserByIdQueryHandler : IQueryHandler<GetUserByIdQuery, UserResponseDto>
{
    public UserResponseDto Handle(GetUserByIdQuery query)
    {
        // 模拟数据库查询
        return new UserResponseDto { Id = query.Id, Name = "John Doe" };
    }
}
```

---

### 第四步：控制器调用示例 📡

在控制器中，我们注入 `IQueryDispatcher` 并调用查询方法：

```csharp
[ApiController]
[Route("api/[controller]")]
public class UsersController : ControllerBase
{
    private readonly IQueryDispatcher _queryDispatcher;

    public UsersController(IQueryDispatcher queryDispatcher)
    {
        _queryDispatcher = queryDispatcher;
    }

    [HttpGet("{id}")]
    public IActionResult GetUserById(int id)
    {
        var query = new GetUserByIdQuery(id);
        var result = _queryDispatcher.Dispatch<GetUserByIdQuery, UserResponseDto>(query);
        return Ok(result);
    }
}
```

---

### 第五步：注册依赖注入服务 🛠️

最后，在 `Program.cs` 中注册服务：

```csharp
builder.Services.AddScoped<IQueryHandler<GetUserByIdQuery, UserResponseDto>, GetUserByIdQueryHandler>();
builder.Services.AddScoped<IQueryDispatcher, QueryDispatcher>();
```

---

## 总结 ✨

通过以上步骤，我们成功实现了一个轻量级的 CQRS 替代方案，能够满足绝大多数项目需求。以下是本解决方案的优点：

1. **简单易用**：无需学习复杂库的使用方法。
2. **灵活定制**：可以根据需求添加日志、验证等功能。
3. **解耦性强**：实现了命令与查询逻辑的分离。

虽然这个实现无法完全替代 MediatR 的全部功能，但对于大多数场景来说，它已经足够强大。希望本文能为您提供灵感，让您的项目更加高效！
