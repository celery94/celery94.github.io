---
pubDatetime: 2024-04-19
tags: [.net, asp.net core, c#, middleware]
source: https://www.devleader.ca/2024/04/18/api-key-authentication-middleware-in-asp-net-core-a-how-to-guide/
author: Nick Cosentino
title: ASP.NET Core 中的 API 密钥验证中间件
description: 想要在你的 ASP.NET Core 应用中添加 API 密钥验证中间件吗？查看这篇文章，了解一个简单的代码示例，展示给你如何操作！
---

> ## 摘录
>
> 想要在你的 ASP.NET Core 应用中添加 API 密钥验证中间件吗？查看这篇文章，了解一个简单的代码示例，展示给你如何操作！
>
> 原文 [API Key Authentication Middleware In ASP.NET Core](https://www.devleader.ca/2024/04/18/api-key-authentication-middleware-in-asp-net-core-a-how-to-guide/) 由 Nick Cosentino 撰写。

---

当我在准备一些特殊内容时，我发现自己需要将 API 密钥验证中间件集成到我的 ASP.NET Core 应用中。[我之前写过关于在 ASP.NET 中使用自定义中间件的内容](https://www.devleader.ca/2024/01/31/custom-middleware-in-asp-net-core-how-to-harness-the-power/ "ASP.NET Core 中的自定义中间件 – 如何发挥其威力！")，但我也一直在试图更好地记录这样的小代码变化，这样下次我再查找时就有一个简便的参考。

这意味着，你得到一些免费的代码和随之而来的参考指南！

---

ASP.NET Core 中的中间件是你可以添加到应用的管道中来处理请求和响应的代码。这些组件可以：

- 选择是否将请求传递给管道中的下一个组件
- 可以在管道中的下一个组件之前和之后执行工作。

在构建一个 ASP.NET Core 应用时，中间件可以用来实现身份验证、错误处理、日志记录和提供静态文件等功能。这个列表还在继续，你甚至可以[实现你自己的自定义中间件](https://www.devleader.ca/2024/01/31/custom-middleware-in-asp-net-core-how-to-harness-the-power/ "ASP.NET Core 中的自定义中间件 – 如何发挥其威力！")。如果你想了解更多关于中间件的信息以便开始，可以查看我写的这篇文章：

- [](https://www.devleader.ca/2024/01/31/custom-middleware-in-asp-net-core-how-to-harness-the-power/ "ASP.NET Core 中的自定义中间件 – 如何发挥其威力！")[ASP.NET Core 中的自定义中间件 – 如何发挥其威力！](https://www.devleader.ca/2024/01/31/custom-middleware-in-asp-net-core-how-to-harness-the-power/)

对于我们这里的用例，我们将研究向 ASP.NET Core 应用添加我们自己的自定义中间件。鉴于我们想要进行某种类型的 API 密钥验证，我们应该能够创建中间件来在密钥无效时停止处理，或者在密钥有效时继续处理。听起来够简单的，对吗？让我们继续看下去吧！

---

## API 密钥验证中间件示例代码

现在你已经了解了 ASP.NET core 中的中间件是什么，让我们来看一个例子。对于我的应用程序，我想要从请求头处理 API 密钥。当然，这可以通过不同的方式完成，比如使用查询参数，但我决定使用头部。

这是一个示例 API 密钥验证中间件代码片段：

```csharp
public async Task MyMiddleware(
    HttpContext context,
    RequestDelegate next)
{
    // if you wanted it as a query parameter, you'd
    // want to consider changing this part of the code!
    const string ApiKeyHeader = "<YOUR_HEADER_KEY_HERE>";
    if (!context.Request.Headers.TryGetValue(ApiKeyHeader, out var apiKeyVal))
    {
        context.Response.StatusCode = 401;
        await context.Response.WriteAsync("Api Key not found.");
        return;
    }

    const TheRealApiKey = "<YOUR_SECRET_API_KEY_HERE>";
    if (!string.Equals(TheRealApiKey, apiKeyVal, StringComparison.Ordinal))
    {
        context.Response.StatusCode = 401;
        await context.Response.WriteAsync("Invalid API Key.");
        return;
    }

    await next(context);
}
```

上面的代码非常代表了[责任链设计模式](https://www.devleader.ca/2024/01/05/chain-of-responsibility-pattern-in-c-simplified-how-to-guide/ "C# 中的责任链模式 – 简化操作指南")！我们的中间件处理程序可以采取行动，然后使用传入的上下文调用下一个委托——或者，通过写回一个响应并且不调用下一个处理程序来终止序列。但如果你想知道我们在哪里连接这个，那么查看这段代码片段：

```csharp
// "app" here is the WebApplication instance after
// being built by the web application builder
app.Use(MyMiddleware);
```

很可能你不希望在代码中直接有你的 API 密钥——实际上，我会说“请不要这样做！”这样你就不会意外地将一个秘密 API 密钥提交到你的源代码控制中。我们可以通过使用环境变量和应用配置来解决这个问题！所以在以下代码示例中，你可以看到在应用的配置中查找一个字符串值：

```csharp
// "app" here is the WebApplication instance after
// being built by the web application builder
var config = app.Configuration
var secretApiKey = config.GetValue<string>("<CONFIG_KEY_NAME>");
```

现在，你可以从配置实例中读取 API 密钥，而不是直接在代码中与硬编码的 API 密钥进行比较，这个配置实例可以通过环境变量填充！

---

## 在 C# 中使用这种方法与插件架构搭配

众所周知，[我喜欢在开发软件时使用插件架构](https://www.devleader.ca/2024/03/12/plugin-architecture-in-c-for-improved-software-design/ "C#中的插件架构，以实现更好的软件设计") —— 但这可能是你第一次阅读我的内容。所以剧透警告：我喜欢在设计软件系统时使用插件。

在我想要添加我的 API 密钥验证中间件的 ASP.NET Core 应用程序中，我有一个非常简单的加载方案，允许依赖项“挂钩”进入 Web 应用程序构建过程。这是通过几个基本步骤完成的：

- 我使用 Autofac 和程序集扫描寻找启动时要加载的带有 Autofac 模块的 DLL
- 这些 DLL 成为插件，所以按定义任何插件都可以使用依赖容器构建器来注册它们自己的依赖
- 注册过程的一部分意味着它们可以要求容器提供构建的 Web 应用程序实例
- 一旦它们有了 Web 应用程序实例，它们就能将自己的中间件挂接上去。

这是一个非常简单/天真的方法，因为对于中间件的排序或控制没有任何机会 —— 你只能勇往直前，并希望一切顺利。然而，这对于现在来说是可以的，因为我目前的中间件需求极其有限。如果/当需要时，我将为此创建一个排序方案。

那么我的插件代码是什么样的？几乎就是我们之前看到的，除了在 [Autofac 模块中](https://www.devleader.ca/2023/10/02/how-to-organize-autofac-modules-5-tips-for-organizing-code/ "如何组织 Autofac 模块：5条组织代码的提示")：

```csharp
internal sealed class ApiKeyModule : Module
{
    protected override void Load(ContainerBuilder builder)
    {
        builder
            .Register(ctx =>
            {
                var app = ctx.Resolve<WebApplication>();
                var config = ctx.Resolve<IConfiguration>();

                const string ApiKeyConfigKey = "API_CONFIG_KEY_NAME";
                Lazy<string?> lazyApiKey = new(() => config.GetValue<string>(ApiKeyConfigKey));

                app.Use(async (context, next) =>
                {
                    const string ApiKeyHeader = "HEADER_KEY_NAME";
                    if (!context.Request.Headers.TryGetValue(
                        ApiKeyHeader,
                        out var apiKeyVal))
                    {
                        context.Response.StatusCode = 401;
                        await context.Response.WriteAsync("Api Key not found.");
                        return;
                    }

                    var apiKey = lazyApiKey.Value;
                    if (!string.Equals(apiKey, apiKeyVal, StringComparison.Ordinal))
                    {
                        context.Response.StatusCode = 401;
                        await context.Response.WriteAsync("Invalid API Key.");
                        return;
                    }

                    await next(context);
                });

                // 这是用来帮助控制依赖项的排序
                // 以便应用程序不会在所有这些
                // 被解析之前启动！
                return new PostAppRegistrationDependencyMarker();
            })
            .SingleInstance();
    }
}
```

如果你想知道好处是什么：我从未需要触及我项目中的任何其他代码，我立即为每一个路线添加了 API 认证。这段代码\*目前\*在主程序集中，但我本可以将它添加到一个新项目中，构建 DLL，并将它丢入运行目录中以激活这种行为。

这就是使用插件构建的力量！
