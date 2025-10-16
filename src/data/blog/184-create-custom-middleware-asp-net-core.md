---
pubDatetime: 2025-03-13
tags: [".NET", "ASP.NET Core"]
slug: create-custom-middleware-asp-net-core
source: https://www.milanjovanovic.tech/blog/3-ways-to-create-middleware-in-asp-net-core
title: 如何在ASP.NET Core中创建自定义中间件：三种实现方法
description: 探讨在ASP.NET Core中创建自定义中间件的三种方式：使用请求委托、按约定创建中间件及基于工厂的中间件。提供详细代码示例和实现步骤，帮助开发者扩展框架功能。
---

# 如何在ASP.NET Core中创建自定义中间件：三种实现方法

在ASP.NET Core应用程序中，中间件允许我们在执行HTTP请求之前或之后引入额外的逻辑。虽然框架内置了许多中间件，但我们可能需要定义自定义的中间件来满足特定需求。本文将介绍三种创建自定义中间件的方法：使用请求委托（Request Delegates）、按约定创建中间件（By Convention）以及基于工厂的中间件（Factory-Based）。

## 使用请求委托添加中间件

第一种方法是通过编写请求委托来定义中间件。通过在`WebApplication`实例上调用`Use`方法，并提供一个带有两个参数的lambda方法即可实现。第一个参数是`HttpContext`，第二个参数是请求管道中的下一个请求委托`RequestDelegate`。

```csharp
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.Use(async (context, next) =>
{
    // 在请求之前添加代码

    await next(context);

    // 在请求之后添加代码
});
```

通过等待`next`委托，您可以继续执行请求管道。您可以通过不调用`next`来短路管道。

## 按约定添加中间件

第二种方法需要创建一个代表中间件的类。我们必须遵循创建此类的约定，以便在应用程序中将其用作中间件。

```csharp
public class ConventionMiddleware(
    RequestDelegate next,
    ILogger<ConventionMiddleware> logger)
{
    public async Task InvokeAsync(HttpContext context)
    {
        logger.LogInformation("Before request");

        await next(context);

        logger.LogInformation("After request");
    }
}
```

约定要求包括：

- 在构造函数中注入`RequestDelegate`
- 定义带有`HttpContext`参数的`InvokeAsync`方法
- 调用`RequestDelegate`并传递`HttpContext`实例

要使用此中间件，我们还需调用`UseMiddleware`方法：

```csharp
app.UseMiddleware<ConventionMiddleware>();
```

## 基于工厂的中间件

第三种方法同样需要创建一个代表中间件的类，但这次我们将实现`IMiddleware`接口。这个接口只有一个方法 - `InvokeAsync`。

```csharp
public class FactoryMiddleware(ILogger<FactoryMiddleware> logger) : IMiddleware
{
    public async Task InvokeAsync(HttpContext context, RequestDelegate next)
    {
        logger.LogInformation("Before request");

        await next(context);

        logger.LogInformation("After request");
    }
}
```

由于`FactoryMiddleware`类将在运行时从依赖注入中解析，因此需要注册为服务：

```csharp
builder.Services.AddTransient<FactoryMiddleware>();
```

然后像前面的示例一样，告知应用程序使用我们的工厂中间件：

```csharp
app.UseMiddleware<FactoryMiddleware>();
```

## 关于强类型的一点看法

我非常推崇尽可能地使用强类型。在这三种方法中，使用`IMiddleware`接口的方式最符合这一要求。这也是我实现中间件的首选方式。由于我们实现了接口，因此很容易创建一个通用解决方案，以确保永远不会忘记注册您的中间件。您可以使用反射扫描实现了`IMiddleware`接口的类，并将它们添加到依赖注入，同时通过调用`UseMiddleware`将它们添加到应用程序。
