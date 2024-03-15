---
pubDatetime: 2024-03-15
tags: [".NET", "Minimal API", "C#"]
source: https://code-maze.com/aspnetcore-automatic-registration-of-minimal-api-endpoints/
author: Ivan Gechev
title: 在 .NET 中自动注册 Minimal API 端点 - Code Maze
description: 在本文中，我们将探讨如何通过自动注册改进我们的 .NET Minimal API 端点。
---

> ## 摘要
>
> 在本文中，我们将探讨如何通过自动注册改进我们的 .NET Minimal API 端点。
>
> 原文 [Automatic Registration of Minimal API Endpoints in .NET - Code Maze](https://code-maze.com/aspnetcore-automatic-registration-of-minimal-api-endpoints/)

---

在这篇文章中，我们将探讨如何通过自动注册来改进我们的 .NET Minimal API 端点。

要下载本文的源代码，您可以访问我们的 [GitHub repository](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/aspnetcore-webapi/AutomaticRegistrationOfMinimalAPIs)。

让我们深入了解！

## Minimal API 设置

在本文中，我们将使用一个表示基本学校系统的 [Minimal API](https://code-maze.com/dotnet-minimal-api/)，重点关注两个关键端点：

```csharp
app.MapGet("/students", async (IStudentService service) =>
{
    var student = await service.GetAllAsync();

    return Results.Ok(student);
})
.WithOpenApi();

app.MapGet("/students/{id:guid}", async (Guid id, IStudentService service) =>
{
    var student = await service.GetByIdAsync(id);

    return Results.Ok(student);
})
.WithOpenApi();

app.MapPost("/students", async (StudentForCreationDto dto, IStudentService service) =>
{
    var student = await service.CreateAsync(dto);

    return Results.Created($"/students/{student.Id}", student);
})
.WithOpenApi();

// 其他 CRUD 端点 PUT, DELETE
```

首先，我们有 `students` 端点，拥有所有基本的 CRUD 操作，用于创建、读取、更新和删除。

然后我们有第二个端点：

```csharp
app.MapGet("/teachers", async (ITeacherService service) =>
{
    var teacher = await service.GetAllAsync();
    return Results.Ok(teacher);
})
.WithOpenApi();
app.MapGet("/teachers/{id:guid}", async (Guid id, ITeacherService service) =>
{
    var teacher = await service.GetByIdAsync(id);
    return Results.Ok(teacher);
})
.WithOpenApi();
// 其他 CRUD 端点 POST, PUT, DELETE
```

`teachers` 端点拥有与 `students` 端点相同的 CRUD 动作。

**我们已经可以感觉到，我们的 `Program` 类变得越来越长，难以导航了**。这只是两个端点，添加更多时会发生什么？我们还有服务注册，以及我们需要正确配置应用程序的所有其他设置。事情很容易失控。

让我们看看如何使我们的 Minimal API 端点更易于管理！

## 使用扩展方法注册 Minimal API 端点

**[扩展方法](https://code-maze.com/csharp-static-members-constants-extension-methods/#extensionmethods) 是 .NET 中我们可以用来更好管理端点的一个很好的工具：**

```csharp
public static class StudentEndpoint
{
    public static void RegisterStudentEndpoint(this IEndpointRouteBuilder routeBuilder)
    {
        routeBuilder.MapGet("/students", async (IStudentService service) =>
        {
            var student = await service.GetAllAsync();
            return Results.Ok(student);
        })
        .WithOpenApi();
        // 为了简洁省略
    }
}
```

我们首先创建 `StudentEndpoint` 类，将其标记为 `static`，因为我们不需要创建这种类型的实例。

然后我们做的下一件事是创建 `RegisterStudentEndpoint()` 方法，它扩展了 `IEndpointRouteBuilder` 接口，扩展 `IEndpointRouteBuilder` 接口的原因是我们的 `WebApplication` 实例实现了它，并且还使用它来在我们的应用程序中映射端点和路由。

在我们的 `RegisterStudentEndpoint()` 方法中，我们使用了从 `IEndpointRouteBuilder` 接口获得的已经熟悉的 `Map()` 方法来注册我们 `students` 端点的所有路由。

还有最后一件事我们需要做：

```csharp
app.RegisterStudentEndpoint();
```

在我们的 `Program` 类中，通过调用我们刚定义的 `RegisterStudentEndpoint()` 方法替换我们所有的 `students` 端点路由注册。通过这样做，我们为我们的端点注册了所有路由，并使我们的代码库更容易阅读和维护。

## 使用反射注册 Minimal API 端点

**[反射](https://code-maze.com/csharp-reflection/) 是 .NET 中最强大的功能之一。毫不奇怪，我们可以使用它来注册我们的端点。** 那么，让我们看看如何做到这一点。

### 定义端点及其抽象

首先，我们需要一个表示我们端点的抽象：

```csharp
public interface IMinimalEndpoint
{
    void MapRoutes(IEndpointRouteBuilder routeBuilder);
}
```

在这里，我们定义了 `IMinimalEndpoint` 接口，带有一个方法 `MapRoutes()`，它将我们已经熟悉的 `IEndpointRouteBuilder` 接口的一个实例作为参数。

完成这步之后，我们继续进行下一步：

```csharp
public class TeacherEndpoint : IMinimalEndpoint
{
    public void MapRoutes(IEndpointRouteBuilder routeBuilder)
    {
        routeBuilder.MapGet("/teachers", async (ITeacherService service) =>
        {
            var teacher = await service.GetAllAsync();
            return Results.Ok(teacher);
        })
        .WithOpenApi();
        // 为了简洁省略
    }
}
```

首先，我们创建 `TeacherEndpoint` 类并实现 `IMinimalEndpoint` 接口。然后，在 `MapRoutes()` 方法中，我们放置了我们在 `Program` 类中用于 `teachers` 端点的所有路由。

通过这种方式，我们有了一种在应用程序中定义端点和路由的简便方法。

### 为 Minimal API 端点注册定义扩展方法

为了使这一切工作，我们需要一些扩展方法。让我们定义我们的第一个方法：

```csharp
public static class MinimalEndpointExtensions
{
    public static IServiceCollection AddMinimalEndpoints(this IServiceCollection services)
    {
        var assembly = typeof(Program).Assembly;
        var serviceDescriptors = assembly
            .DefinedTypes
            .Where(type => !type.IsAbstract &&
                           !type.IsInterface &&
                           type.IsAssignableTo(typeof(IMinimalEndpoint)))
            .Select(type => ServiceDescriptor.Transient(typeof(IMinimalEndpoint), type));
        services.TryAddEnumerable(serviceDescriptors);
        return services;
    }
}
```

首先，我们创建 `MinimalEndpointExtensions` 类，它将包含我们需要的所有扩展方法。然后，我们创建 `AddMinimalEndpoints()` 方法，它扩展了 `IServiceCollection` 接口。

接下来，我们检索 `Program` 类所在的 `Assembly`，过滤其 `DefinedTypes` 属性（它保存了程序集中所有类型的信息），以找到所有既不是抽象的也不是接口的类型。此外，我们添加了一个最终条件，该条件使用 `IsAssignableTo()` 方法，将程序集中的类型与实现 `IMinimalEndpoint` 接口的类型进行匹配。

然后，对于每个匹配的类型，我们使用 `Select()` 方法为 `IMinimalEndpoint` 类型和具体类型创建一个 _Transient_ 服务的 `ServiceDescriptor`。

最后，我们使用 `TryAddEnumerable()` 方法将我们所有的 `ServiceDescriptor` 实例添加到 `IServiceCollection` 中。`TryAddEnumerable()` 方法将仅在尚未注册的情况下注册每个描述符。

**为了使这一切工作，我们应用程序中的所有端点都必须实现 `IMinimalEndpoint` 接口。**

现在，让我们定义我们的第二个扩展方法：

```csharp
public static IApplicationBuilder RegisterMinimalEndpoints(this WebApplication app)
{
    var endpoints = app.Services
        .GetRequiredService<IEnumerable<IMinimalEndpoint>>();
    foreach (var endpoint in endpoints)
    {
        endpoint.MapRoutes(app);
    }
    return app;
}
```

在这里，我们创建了 `RegisterMinimalEndpoints()` 方法，它扩展了 `WebApplication` 类。在此方法中，我们使用 `GetRequiredService()` 方法获取实现我们的 `IMinimalEndpoint` 接口的所有服务。然后，我们遍历所有匹配的服务，并调用它们的 `MapRoutes()` 方法。

现在，我们需要进行最后的处理：

```csharp
builder.Services.AddMinimalEndpoints();
```

首先，在我们的 `Program` 类中，我们在服务集合上调用 `AddMinimalEndpoints()` 扩展方法，以注册所有实现 `IMinimalEndpoint` 接口的实现。

然后，在我们构建应用程序后添加最后一个方法调用：

```csharp
app.RegisterMinimalEndpoints();
```

再次，在 `Program` 类中，我们在我们的 `WebApplication` 实例上使用 `RegisterMinimalEndpoints()` 扩展方法 - 这样我们将注册我们拥有的每个端点的所有路由。

## 选择正确的方法来注册 Minimal API 端点

扩展方法和反射都赋予了我们自动注册 Minimal API 端点的能力。

然而，在我们做出选择之前，有几件事我们必须考虑。

### 项目规模

对于具有预定数量端点的小型项目，**使用扩展方法确保简单和清晰**。另一方面，对于更大或不断增长的代码库，**基于反射的注册为我们提供了更多的灵活性和可扩展性**。

### 维护和清晰度

**当我们使用扩展方法时**，我们获得了很好的关注点分离以及显式注册。这使我们的代码易于维护和理解。

**反射基于注册**，另一方面，为我们提供了动态行为。但我们必须记住，它可能使我们的代码变得不那么透明，更难以理解。

### 约定和灵活性

**反射**允许我们基于强制约定或运行时条件动态注册端点，这使它适用于复杂场景。

相比之下，当我们使用**扩展方法**时，我们得到了更确定的方法，但我们必须格外注意保持端点之间的一致性。

## 结论

在这篇文章中，我们探索了自动注册 Minimal API 端点的两种不同方法。通过使用扩展方法或反射，我们可以增强应用程序代码的结构和可读性。这些技术使我们能够更轻松地导航和扩展我们的项目，为 .NET 中高效和可扩展的 API 开发奠定了基础。
