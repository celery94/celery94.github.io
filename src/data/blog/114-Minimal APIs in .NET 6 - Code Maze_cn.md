---
pubDatetime: 2024-04-22
tags: [".NET", "ASP.NET Core"]
source: https://code-maze.com/dotnet-minimal-api/
author: Code Maze
title: .NET 6 中的最小化 API
description: 在本文中，我们将通过例子讲解 .NET 6 中最小化 API 的核心思想及基本概念。
---

# .NET 6 中的最小化 API

> ## 摘要
>
> 在本文中，我们将通过例子讲解 .NET 6 中最小化 API 的核心思想及基本概念。
>
> 原文 [Minimal APIs in .NET 6](https://code-maze.com/dotnet-minimal-api/) 由 [Code Maze](https://code-maze.com/) 发布。

---

在本文中，我们将介绍 .NET 6 中最小化 API 的核心思想和基本概念。但如果我们试图用一句话来解释，那就是它是一个不需要控制器的 API。

除了理论解释之外，我们还将深入代码，并展示如何实现具有所有 CRUD 操作的最小化 API。

要下载本文的源代码，您可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/aspnetcore-webapi/Minimal%20API)。

## 最小化 API 的起源

最小化 API 的故事始于 2019 年 11 月。开发者社区有机会看到 GO、Python、C# 和 JavaScript 实现的[分布式计算器](https://twitter.com/markrendle/status/1198324914102636545)。当社区开始比较用 C# 实现几乎相同的功能需要多少文件和代码行时，很明显，与其他语言相比，C# 似乎更加复杂。

想象一下，多年积累的概念和特性数量，对于新手来说，深入了解 .NET web 开发世界可能是多么的压倒性。因此，.NET Core 团队希望降低所有开发者（新手和老手）的复杂性，并拥抱极简主义。所以，如果我们想创建一个带有单个端点的简单 API，我们应该能够在一个文件中完成。但如果我们稍后需要切换回使用控制器，我们也应该能够做到。

让我们看看他们已经完成了什么。

## 如何设置最小化 API？

我们需要有 [Visual Studio 2022](https://visualstudio.microsoft.com/vs/#download) 以及 ASP.NET 和 web 开发工作负载，以便继续阅读本文。

要创建一个最小化 API，我们将从 ASP.NET Core 空模板创建一个 C# 项目，并在附加信息对话框中取消选中所有复选框。这样做，我们将以四行代码结束 `Program` 类：

```csharp
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();
app.MapGet("/", () => "Hello World!");
app.Run();
```

就是这样。一旦我们运行我们的应用，我们将在浏览器中看到 `Hello World!` 消息。

让我们解释如何仅用四行代码就能拥有一个端点就绪的 API。

我们首先注意到缺少 `using` 指令。C#10 引入了全局 `using` 指令，如果启用了该特性，默认情况下会包含常见的 `using` 指令。由于其中之一是 `Microsoft.AspNetCore.Builder`，我们不需要编写任何东西。

然后我们可以看到 `MapGet`，`EndpointRouteBuilderExtensions` 类的一个扩展方法，它接受代理作为其参数之一。接受任何代理是另一个例子，其中 C#10 将最小化 API 做得很好。我们可以将任何方法传递给 `MapGet` 方法，编译器会尽力弄清楚如何将其转换为 `RequestDelegate`。如果它做不到，它会让我们知道。

最后，使用 `app.Run()` 方法，我们可以运行我们的应用。

### 依赖注入在最小化 API 中是如何工作的？

.NET 6 中 [依赖注入](https://code-maze.com/dependency-injection-aspnet/) (DI) 容器的一个新特性使我们能够知道哪种类型在容器中注册为可解析类型。这意味着我们可以在 `MapGet` 方法中的代理修正一些我们已经通过 DI 注册的类型，而不需要额外的属性或通过构造函数的注入。例如，我们可以写：

```csharp
app.MapGet("/", (IHttpClientFactory httpClientFactory) => "Hello World!"));
```

框架会知道 `IHttpClientFactory` 是作为可解析类型注册的。它可以访问 DI 容器并用注册的类型填充它。这在 .NET 6 之前是不可能的。

## 在最小化 API 中实现 CRUD 方法

在这个例子中，我们将使用 [Entity Framework Core](https://code-maze.com/entity-framework-core-series/) 内存数据库。你可以在 [ASP.NET Core 中通过单个请求创建多个资源](https://code-maze.com/aspnetcore-creating-multiple-resources-with-single-request/) 文章中找到详细的设置信息。

既然我们要操作文章，让我们创建一个 `Article` 类：

```csharp
public class Article
{
    public int Id { get; set; }
    public string? Title { get; set; }
    public string? Content { get; set; }
    public DateTime? PublishedAt { get; set; }
}
```

和一个 `ArticleRequest` 记录：

```csharp
public record ArticleRequest(string? Title, string? Content, DateTime? PublishedAt);
```

让我们首先实现 get 方法并解释发生了什么：

```csharp
app.MapGet("/articles", async (ApiContext context) => Results.Ok(await context.Articles.ToListAsync()));
app.MapGet("/articles/{id}", async (int id, ApiContext context) =>
{
    var article = await context.Articles.FindAsync(id);
    return article != null ? Results.Ok(article) : Results.NotFound();
});
```

对于这两种方法，我们都将路由模式作为第一个参数添加。在第一个 `MapGet` 实现中，`ApiContext` 在代理中解析，因为它被注册为一个可解析类型。在第二个 `MapGet` 实现中，我们在代理中添加了 `id` 作为额外参数。我们也可以更改参数的顺序：

```csharp
app.MapGet("/articles/{id}", async (ApiContext context, int id) =>
{
    var article = await context.Articles.FindAsync(id);
    return article != null ? Results.Ok(article) : Results.NotFound();
});
```

一切仍然可以正常工作。那是编译器尝试将任何代理解析为 `RequestDelegate` 的巧妙特性，并且它做得很好。

接着，让我们实现 POST 和 DELETE 方法：

```csharp
app.MapPost("/articles", async (ArticleRequest article, ApiContext context) =>
{
    var createdArticle = context.Articles.Add(new Article
    {
        Title = article.Title ?? string.Empty,
        Content = article.Content ?? string.Empty,
        PublishedAt = article.PublishedAt,
    });
    await context.SaveChangesAsync();
    return Results.Created($"/articles/{createdArticle.Entity.Id}", createdArticle.Entity);
});
app.MapDelete("/articles/{id}", async (int id, ApiContext context) =>
{
    var article = await context.Articles.FindAsync(id);
    if (article == null)
    {
        return Results.NotFound();
    }
    context.Articles.Remove(article);
    await context.SaveChangesAsync();
    return Results.NoContent();
});
```

最后，我们将实现 PUT 方法：

```csharp
app.MapPut("/articles/{id}", async (int id, ArticleRequest article, ApiContext context) =>
{
    var articleToUpdate = await context.Articles.FindAsync(id);

    if (articleToUpdate == null)
        return Results.NotFound();
    if (article.Title != null)
        articleToUpdate.Title = article.Title;
    if (article.Content != null)
        articleToUpdate.Content = article.Content;
    if (article.PublishedAt != null)
        articleToUpdate.PublishedAt = article.PublishedAt;
    await context.SaveChangesAsync();
    return Results.Ok(articleToUpdate);
});
```

由于我们想专注于最小化 API，我们的实现很简单，缺少适当的请求模型验证或使用 [AutoMapper](https://code-maze.com/automapper-net-core/) 进行映射。你可以在我们的 [ASP.NET Core Web API – Post, Put, Delete](https://code-maze.com/net-core-web-development-part6/) 文章中阅读如何正确应用这些。

有趣的是，`EndpointRouteBuilderExtensions` 类中没有 `MapPatch` 扩展方法。但我们可以使用 `MapMethods` 方法，它比前面的方法更健壮和适应性强：

```csharp
app.MapMethods("/articles/{id}", new[] { "PATCH" }, async (int id, ArticleRequest article, ApiContext context) => { ... });
```

如果你想以正确的方式实现 PATCH 方法，你可以在我们的 [在 ASP.NET Core 中使用 HttpClient 发送 HTTP PATCH 请求](https://code-maze.com/using-httpclient-to-send-http-patch-requests-in-asp-net-core/) 文章中了解更多。

### 如何使用 Swagger、认证和授权？

好消息是，设置和使用 Swagger 在 Minimal APIs 中与之前没有任何实质性的区别。你可以在我们的[在 ASP.NET Core Web API 中配置和使用 Swagger UI](https://code-maze.com/swagger-ui-asp-net-core-web-api/)文章中了解更多关于 Swagger 的信息及其配置方式。

认证和授权也是如此。唯一的新功能是向委托方法添加认证和授权属性（或任何属性）。这在早期版本的 C# 中是不可能的。因此，如果我们像在我们的[ASP.NET Core 使用 JWT 进行认证](https://code-maze.com/authentication-aspnetcore-jwt-1/)文章中实现认证，我们可以在我们的代表上添加 `[Authorize]` 属性：

```csharp
app.MapPut("/articles/{id}", [Authorize] async (int id, ArticleRequest article, ApiContext context) => { ... }
```

## 在 Minimal APIs 中组织代码

使用 minimal APIs 时，`Program` 类可能会变得相当庞大，包含很多代码行。为避免这种情况，让我们展示如何组织我们的代码。

我们打算将每个映射方法中的代码抽取到单独的 `ArticleService` 类中，该类将实现 `IArticleService` 接口（你可以在我们的源代码中找到实现）。然后，由于我们可以将我们的服务注入到委托方法中，我们可以更改我们的代码为：

```csharp
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext(opt => opt.UseInMemoryDatabase("api"));
builder.Services.AddScoped<IArticleService, ArticleService>();
var app = builder.Build();
app.MapGet("/articles", async (IArticleService articleService)
    => await articleService.GetArticles());
app.MapGet("/articles/{id}", async (int id, IArticleService articleService)
    => await articleService.GetArticleById(id));
app.MapPost("/articles", async (ArticleRequest articleRequest, IArticleService articleService)
    => await articleService.CreateArticle(articleRequest));
app.MapPut("/articles/{id}", async (int id, ArticleRequest articleRequest, IArticleService articleService)
    => await articleService.UpdateArticle(id, articleRequest));
app.MapDelete("/articles/{id}", async (int id, IArticleService articleService)
    => await articleService.DeleteArticle(id));
app.Run();
```

我们的 `Program` 类现在看起来更加有组织了。我们可以进一步将所有映射调用提取到一个单独的扩展方法中，但随着每次重构，我们都在与 minimal APIs 的原始思想——直截了当——背道而驰。

## 结语

在这篇文章中，我们讨论了 minimal API 的起源及其存在的动机。我们还展示了如何使用 CRUD 操作创建 minimal API。
