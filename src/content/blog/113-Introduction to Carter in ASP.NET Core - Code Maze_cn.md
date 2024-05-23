---
pubDatetime: 2024-04-22
tags: [".NET", "Carter", "ASP.NET Core"]
source: https://code-maze.com/aspnetcore-introduction-to-carter/
author: Ivan Gechev
title: ASP.NET Core 中引入 Carter
description: 在这篇文章中，我们将深入探讨 Carter 库以及如何在我们的 ASP.NET Core 项目中使用它。
---

# ASP.NET Core 中引入 Carter

> ## 摘录
>
> 在这篇文章中，我们将深入探讨 Carter 库以及如何在我们的 ASP.NET Core 项目中使用它。
>
> 原文 [Introduction to Carter in ASP.NET Core](https://code-maze.com/aspnetcore-introduction-to-carter/)

---

在这篇文章中，我们将深入探讨 Carter 库以及如何在我们的 ASP.NET Core 项目中使用它。

要下载此文章的源代码，你可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/dotnet-client-libraries/IntroductionToCarter)。

## 什么是 Carter 库

[Carter](https://github.com/CarterCommunity/Carter) 库是一个开源项目，为 ASP.NET Core 应用程序提供抽象层。这一层作为管理我们的 minimal API 的方式，使我们能够轻松高效地进行管理。该包提供了一组接口和方法，帮助我们管理端点。

那么，让我们来看看实际的操作：

```csharp
app.MapGet("/books", async (IBookService service) =>
{
    var books = await service.GetAllAsync();
    return Results.Ok(books);
})
.WithOpenApi();
app.MapGet("/books/{id:guid}", async (Guid id, IBookService service) =>
{
    var book = await service.GetByIdAsync(id);
    return Results.Ok(book);
})
.WithOpenApi();
app.MapPost("/books", async (CreateBookRequest request, IBookService service) =>
{
    var book = await service.CreateAsync(request);
    return Results.Created($"/books/{book.Id}", book);
})
.WithOpenApi();
// 其他 CRUD 端点 PUT，DELETE
```

这里，我们有一个管理图书应用的 minimal API，带有 CRUD 端点。此外，端点位于我们的 `Program` 类中，占用大约 40 行。

**这已经开始变得难以导航和维护了。随着我们的应用程序增长，它只会变得更复杂**。这就是 Carter 发挥作用的地方。

如果你想要详细了解 minimal API，请查看我们的文章 [Minimal APIs in .NET 6](https://code-maze.com/dotnet-minimal-api/)。

接下来，我们将看到它如何让我们的生活变得更简单。

## 在 ASP.NET Core Minimal API 中使用 Carter 的方法

在我们对代码做任何事情之前，我们需要安装 Carter 库:

```bash
dotnet add package Carter
```

一旦完成，我们就可以开始使用它了：

```csharp
public class BookModule : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
    }
}
```

库围绕模块展开，所以我们首先创建 `BookModule` 并实现 `ICarterModule` 接口。接口带有 `AddRoutes()` 方法。

让我们实现它：

```csharp
public class BookModule : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        app.MapGet("/books", async (IBookService service) =>
        {
            var books = await service.GetAllAsync();
            return Results.Ok(books);
        })
        .WithOpenApi();
        app.MapGet("/books/{id:guid}", async (Guid id, IBookService service) =>
        {
            var book = await service.GetByIdAsync(id);
            return Results.Ok(book);
        })
        .WithOpenApi();
        // 其他 CRUD 端点 POST，PUT，DELETE
    }
}
```

`AddRoutes()` 方法接受一个 `IEndpointRouteBuilder` 类型的参数。多亏了这个，**我们唯一需要做的就是将我们的端点从 `Program` 类移动到 `AddRoutes()` 方法中**。

接下来，我们必须注册我们的模块：

```csharp
builder.Services.AddCarter();
```

在我们的 `Program` 类中，我们使用服务集合上的 `AddCarter()` 扩展方法。这将扫描我们的项目以寻找所有 `ICarterModule` 接口的实现，并以 _Singleton_ 生命周期将它们注册。

最后，我们映射我们的端点：

```csharp
app.MapCarter();
```

我们在我们的 `WebApplication` 实例上调用 `MapCarter()` 方法。通过这样做，我们映射了我们的端点，并使它们对我们的 API 的任何用户可见。

## Carter 和 ASP.NET Core 中的模型验证

有了 Carter，我们还得到了与之集成的 **[FluentValidation](https://code-maze.com/fluentvalidation-in-aspnet/)，这是与 Carter NuGet 包一起安装的**。那么，让我们使用它：

```csharp
public class CreateBookRequestValidator : AbstractValidator<CreateBookRequest>
{
    public CreateBookRequestValidator()
    {
        RuleFor(x => x.Title).NotNull().NotEmpty();
        RuleFor(x => x.Author).NotNull().NotEmpty();
        RuleFor(x => x.ISBN).NotNull().NotEmpty();
    }
}
```

我们从创建 `CreateBookRequestValidator` 类开始。接下来，我们实现了 `AbstractValidator<T>` 抽象类，其中 `T` 是我们的 `CreateBookRequest` 实体。之后，我们编写了一些验证规则 - 在我们的情况下，我们希望 `Title`、`Author` 和 `ISBN` 属性不为 `null` 或空。

让我们将验证集成到我们的 `CREATE` 端点中：

```csharp
app.MapPost("/books", async (
    HttpContext context,
    CreateBookRequest request,
    IBookService service) =>
{
    var result = context.Request.Validate(request);
    if (!result.IsValid)
    {
        context.Response.StatusCode = (int)HttpStatusCode.UnprocessableEntity;
        await context.Response.Negotiate(result.GetFormattedErrors());
        return Results.UnprocessableEntity();
    }
    var book = await service.CreateAsync(request);
    return Results.Created($"/books/{book.Id}", book);
})
.WithOpenApi();
```

在我们的 `BookModule` 类中，我们对我们的 `/books` 端点进行了一些更新。我们首先添加了请求的 `HttpContext` 作为参数。

然后，我们使用 `Validate()` 方法，这是我们从 Carter 获得的 `HttpRequest` 类上的扩展方法，传递 `CreateBookRequest` 参数。该方法使用 `IValidatorLocator` 接口的内部实现尝试解析一个适当的验证器。因此，这消除了我们需要在 DI 容器中注册我们的 `CreateBookRequestValidator` 的需求。如果没有匹配的验证器，我们将收到一个 `InvalidOperationException` 异常。

最后，我们使用另外两个 Carter 方法 - `Negotiate()` 和 `GetFormattedErrors()`。通过后者，我们获得了格式化的输出，每个遇到的错误在验证器中的属性名称和错误消息。`Negotiate()` 方法在当前的 `HttpResponse` 实例上执行内容协商，并尝试在可能的情况下使用一个接受的媒体类型，如果找不到 - 它将默认为 _application/json_。

## 在 ASP.NET Core 中使用 Carter 进行高级端点配置

有了 Carter，我们可以进一步进行一些高级配置：

```csharp
public class BookModule : CarterModule
{
    public BookModule()
        : base("/api")
    {
        WithTags("Books");
        IncludeInOpenApi();
    }
    public override void AddRoutes(IEndpointRouteBuilder app)
    {
        // CRUD 端点
    }
}
```

这里，我们让我们的 `BookModule` 类实现 `CarterModule` 抽象类而不是 `ICarterModule` 接口。我们之后所做的第一件事是在 `AddRoutes()` 方法中添加 `override` 操作符。

接下来，我们为 `BookModule` 类创建一个构造函数，调用 `CarterModule` 的基本构造函数，并向它传递 `/api`。这将在此模块中的所有端点前添加 _/api_ 的前缀。在构造函数内部，我们使用 `WithTags()` 方法将所有端点分组到 _Books_ 标签下。

最后，我们调用 `IncludeInOpenApi()` 方法。通过它，我们向模块中的所有端点添加 OpenAPI 注释，并将所有路由包含在 OpenAPI 输出中。因此，我们不需要在所有端点上调用 `WithOpenApi()` 方法。

**Carter 库还为我们提供了各种其他方法，用于进一步定制我们的模块。**例如，如果我们的应用程序已经设置了授权，我们可以通过调用 `RequireAuthorization()` 方法为给定模块的所有端点激活它。如果我们有[速率限制设置](https://code-maze.com/aspnetcore-web-api-rate-limiting/)，我们可以使用 `RequireRateLimiting()` 方法并传递速率限制策略的名称来登记端点，或者我们可以使用 `DisableRateLimiting()` 方法来禁用速率限制。

## 结论

在这篇文章中，我们探索了 Carter 库以及它提供的管理 ASP.NET Core API 的流畅方法。通过利用其模块结构，我们可以有效地将我们的端点组织到单独的模块中，从而增强代码的可读性和可维护性。
