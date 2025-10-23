---
pubDatetime: 2024-05-19
tags: [".NET", "ASP.NET Core"]
source: https://www.milanjovanovic.tech/blog/3-ways-to-create-middleware-in-asp-net-core
author: Milan Jovanović
title: ASP.NET Core中创建中间件的3种方式
description: 中间件让我们在执行HTTP请求之前或之后引入额外的逻辑。你已经在使用框架中可用的许多内置中间件。
---

# ASP.NET Core中创建中间件的3种方式

> ## 摘要
>
> 在这个新闻稿中，我们将介绍在ASP.NET Core应用程序中创建中间件的三种方法。中间件允许我们在执行HTTP请求之前或之后引入额外的逻辑。你已经在使用框架中可用的许多内置中间件。我将向你展示如何定义自定义中间件的三种方法：通过请求委托、按约定和基于工厂。
>
> 原文 [ASP.NET Core中创建中间件的3种方式](https://www.milanjovanovic.tech/blog/3-ways-to-create-middleware-in-asp-net-core)

---

在这个新闻稿中，我们将介绍在**ASP.NET Core**应用程序中创建中间件的三种方法。

**中间件**允许我们在执行HTTP请求之前或之后引入额外的逻辑。

你已经在使用框架中可用的许多内置中间件。

让我们逐一查看它们，并了解如何在代码中实现它们。

## 通过请求委托添加中间件

定义中间件的第一种方法是编写一个**请求委托**。

你可以通过在`WebApplication`实例上调用`Use`方法并提供一个带有两个参数的lambda方法来实现。第一个参数是`HttpContext`，第二个参数是管道中的实际下一个请求委托`RequestDelegate`。

以下是这样做的样子：

```csharp
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.Use(async (context, next) =>
{
    // 在请求前添加代码。

    await next(context);

    // 在请求后添加代码。
});
```

通过等待`next`委托，你正在继续请求管道的执行。你可以通过不调用`next`委托来*短路*管道。

这种`Use`方法的重载是**Microsoft**建议的。

## 按约定添加中间件

第二种方法要求我们创建一个将代表我们中间件的类。我们在创建这个类时必须遵循约定，以便我们能将其作为中间件在我们的应用程序中使用。

我首先将向你展示这个类的样子，然后解释我们这里遵循的约定。

以下是这个类的样子：

```csharp
public class ConventionMiddleware(
    RequestDelegate next,
    ILogger<ConventionMiddleware> logger)
{
    public async Task InvokeAsync(HttpContext context)
    {
        logger.LogInformation("请求前");

        await next(context);

        logger.LogInformation("请求后");
    }
}
```

我们遵循的约定有几条规则：

- 我们需要在构造函数中注入一个`RequestDelegate`
- 我们需要定义一个带有`HttpContext`参数的`InvokeAsync`方法
- 我们需要调用`RequestDelegate`并将`HttpContext`实例传递给它

还有一件事是必需的，那就是告诉我们的应用程序使用这个中间件。

我们可以通过调用`UseMiddleware`方法来实现：

```csharp
app.UseMiddleware<ConventionMiddleware>();
```

有了这个，我们就拥有了一个功能性的中间件。

## 添加基于工厂的中间件

第三种，也是最后一种方法要求我们也创建一个将代表我们中间件的类。

但是，这次我们要实现`IMiddleware`接口。这个接口只有一个方法 - `InvokeAsync`。

以下是这个类的样子：

```csharp
public class FactoryMiddleware(ILogger<FactoryMiddleware> logger) : IMiddleware
{
    public async Task InvokeAsync(HttpContext context, RequestDelegate next)
    {
        logger.LogInformation("请求前");

        await next(context);

        logger.LogInformation("请求后");
    }
}
```

`FactoryMiddleware`类在运行时将通过依赖注入解析。

因此，我们需要将其注册为服务：

```csharp
builder.Services.AddTransient<FactoryMiddleware>();
```

与前一个示例一样，我们需要告诉我们的应用程序使用我们的基于工厂的中间件：

```csharp
app.UseMiddleware<FactoryMiddleware>();
```

有了这个，我们就拥有了一个功能性的中间件。

## 关于强类型的话

我非常支持尽可能使用**强类型**。在我刚刚展示的三种方法中，使用`IMiddleware`接口的方式最能满足这个约束。这也是我**首选**的实现**中间件**的方式。

由于我们正在实现一个接口，创建一个通用解决方案以确保你永不忘记注册你的中间件变得非常容易。

你可以使用反射来扫描实现`IMiddleware`接口的类并将它们添加到依赖注入中，并通过调用`UseMiddleware`将它们添加到应用程序中。
