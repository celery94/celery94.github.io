---
pubDatetime: 2024-04-19
tags: [".NET", "ASP.NET Core"]
source: https://www.devleader.ca/2024/01/31/custom-middleware-in-asp-net-core-how-to-harness-the-power/
author: Nick Cosentino
title: 在ASP.NET Core中使用自定义Middleware - 如何发挥其强大作用
description: 了解不同类型的middleware以及如何在ASP.NET Core中实现自定义middleware，解决web开发中的常见挑战！
---

# 在ASP.NET Core中使用自定义Middleware - 如何发挥其强大作用

> ## 摘要
>
> 了解不同类型的middleware以及如何在ASP.NET Core中实现自定义middleware，解决web开发中的常见挑战！
>
> 原文 [Custom Middleware in ASP.NET Core - How to Harness the Power](https://www.devleader.ca/2024/01/31/custom-middleware-in-asp-net-core-how-to-harness-the-power/)

---

ASP.NET Core的middleware在web开发中是一个至关重要的组件，对于C#开发人员来说，深入理解其工作原理是必不可少的。简而言之，middleware是位于web应用程序与服务器之间的软件，帮助管理请求和控制数据流。不仅有内置的middleware供我们使用，我们还可以在ASP.NET Core中利用自定义middleware！

深入理解ASP.NET Core中的middleware非常重要，因为它可以决定web应用程序的性能和稳定性。此外，它可以帮助C#开发人员解决web开发中的特定挑战，并提升用户体验。本文旨在教你如何通过工作代码示例来发挥自定义middleware在ASP.NET Core中的强大作用。

通过阅读本文，你将能够在ASP.NET Core中创建自定义middleware，并解决常见问题，使你能够构建无缝的web应用程序！让我们深入了解！

---

## 理解ASP.NET Core Middleware

ASP.NET Core middleware是位于web服务器与应用程序代码之间的软件。其主要目的是在请求和响应进出应用程序时进行处理。Middleware可以在请求和响应管道中添加、修改或删除数据，允许开发者自定义应用程序与web服务器的交互方式。

ASP.NET Core中有各种类型的middleware，每种类型都在web开发中服务于独特的目的。身份验证middleware负责用户身份验证，而路由middleware根据请求的URL和HTTP方法将传入的请求引导到适当的端点。静态文件middleware提供图片、JavaScript和CSS文件等静态文件，而会话middleware则使得服务器端数据存储对用户会话可用。

### ASP.NET Core中的Middleware类型

以下是ASP.NET Core中一些不同middleware类型的更详细概述：

- **身份验证Middleware**：为用户请求提供身份验证机制，并向应用程序组件断言用户身份。对于现代应用程序来说，安全至关重要，而身份验证middleware让开发者为他们的应用程序实现安全的身份验证。
- **路由Middleware**：根据请求的URL和HTTP方法将传入的HTTP请求定向到适当的端点。路由middleware确保应用程序仅响应符合预期结构和格式的请求。
- **静态文件Middleware**：向客户端提供静态文件，如图片、JavaScript和CSS文件。这样可以防止服务器处理静态文件的请求，从而释放资源以处理动态请求。
- **会话Middleware**：使服务器端数据存储对用户会话可用。Session middleware让开发者存储和检索可以跨多个请求访问的会话数据。

Middleware可用于解决web开发中的特定挑战。例如，如果需要记录传入的请求，可以使用middleware来拦截传入的请求并将它们记录到文件中。如果应用程序需要身份验证，则可以实现满足其特定需求的自定义身份验证middleware。ASP.NET Core中有许多middleware，每个都是为特定需求构建的，开发者可以使用它们来定制他们的应用程序。

---

Middleware是ASP.NET Core中的一个强大功能，允许开发者自定义[请求和响应管道](https://www.devleader.ca/2024/01/12/how-to-implement-the-pipeline-design-pattern-in-c/ "如何在C#中实现管道设计模式")。以下是在ASP.NET Core中创建middleware的分步指南：

1.  在Visual Studio中创建一个新的ASP.NET Core项目（或打开您自己现有的项目）。
2.  打开项目中的Startup.cs文件，找到具有IApplicationBuilder参数的Configure方法。如果你正在处理一个已有的项目，或者最小API项目，这可能已经移动了。
3.  通过在IApplicationBuilder参数上调用Use方法并传入一个代表你的middleware逻辑的委托来注册middleware。
4.  使用Run方法来配置管道中的最后一个middleware。

```csharp
public void Configure(IApplicationBuilder app)
{
    app.Use(async (context, next) =&gt;
    {
        // 你的middleware代码逻辑在这里
        await next.Invoke();
    });

    app.Run(async (context) =&gt;
    {
        await context.Response.WriteAsync("Hello, world!");
    });
}
```

此示例创建了两个middleware组件，第一个处理每个请求，第二个仅处理管道中的最后一个步骤。请注意，Use方法将middleware添加到管道中，而Run方法用于操作响应。

### 在ASP.NET Core中实现自定义Middleware

在ASP.NET Core中创建自定义middleware是一个直接的过程，涉及实现IMiddleware接口。以下是在ASP.NET Core中创建自定义middleware的分步指南：

1.  创建一个定义middleware的新类。在这个类中，实现IMiddleware接口，这要求你实现一个InvokeAsync方法。
2.  通过将你的代码逻辑添加到InvokeAsync方法中来编写middleware的逻辑。

以下是自定义middleware实现的示例代码：

```csharp
public class CustomMiddleware : IMiddleware
{
    public async Task InvokeAsync(HttpContext context, RequestDelegate next)
    {
        // 你的middleware代码逻辑在这里
        await next(context);
    }
}
```

你现在可以将你的新自定义middleware添加到管道中了。为此，请更新Startup.cs文件中的Configure方法，添加你的自定义middleware：

```csharp
public void Configure(IApplicationBuilder app)
{
    app.UseMiddleware&lt;CustomMiddleware&gt;();

    app.Run(async (context) =&gt;
    {
        await context.Response.WriteAsync("Hello, world!");
    });
}
```

通过遵循这些步骤，你可以将你的自定义middleware添加到[请求和响应管道](https://www.devleader.ca/2024/01/12/how-to-implement-the-pipeline-design-pattern-in-c/ "如何在C#中实现管道设计模式")中，这允许你根据应用程序的特定需求控制请求的处理方式。在实现自定义middleware时，请确保遵循实现和测试middleware的[最佳实践](https://www.devleader.ca/2023/10/18/blazor-unit-testing-best-practices-how-to-master-them-for-development-success/)，以确保你的middleware高效且无错误。[测试覆盖率很重要](https://www.devleader.ca/2023/12/25/why-test-coverage-can-be-misleading-how-to-avoid-false-confidence/ "为什么测试覆盖率可能误导 – 如何避免过度自信")，用来建立信心！

---

## 在ASP.NET Core中面临的Middleware常见挑战

与任何技术一样，C#开发人员在使用ASP.NET Core中的middleware时可能会遇到一些常见挑战。以下是你可能遇到的一些问题：

- **兼容性问题**：一些middleware组件可能与应用程序中使用的其他middleware组件或第三方库不兼容。这可能导致运行时错误或意外行为。
- **性能问题**：设计不良的middleware可能会导致性能问题，降低应用程序的响应速度和速度。
- **安全风险**：配置不当或设计不良的middleware可能会引入安全风险，使应用程序容易受到XSS或CSRF攻击。

你之前尝试过实现middleware吗？你遇到了哪些其他问题？

### 在ASP.NET Core中排查Middleware问题

面对middleware挑战时，开发人员可以[实施各种排查策略](https://www.devleader.ca/2023/11/22/how-to-implement-the-strategy-pattern-in-c-for-improved-code-flexibility/)并采用最佳实践来识别和解决middleware问题。以下是在ASP.NET Core中排查middleware问题的一些提示：

- **检查日志消息**：查看应用程序的日志消息以获得更多问题的洞察。日志可以帮助识别问题发生的位置、原因以及需要修复的内容。
- **使用调试工具**：调试工具，如断点和逐步执行代码，对于跟踪执行路径和了解问题在应用程序中的发生位置很有用。如果你已经在生产环境中运行了，这可能就不那么有效了！
- **隔离测试**：考虑隔离测试middleware以识别它在问题中的作用。这可以帮助识别middleware组件是否是问题的来源，或者它是否受到其他组件的影响。这就是为什么[采用不同的测试方法至关重要](https://www.devleader.ca/2021/05/07/tldr-unit-vs-functional-tests/ "测试：单元测试与功能测试的快速概述")。
- **遵循最佳实践**：坚持遵循实施和测试middleware的[最佳实践](https://learn.microsoft.com/en-us/aspnet/core/test/middleware?view=aspnetcore-8.0)。确保你的middleware代码清晰高效并正确处理错误。测试对于确保middleware代码高效且无bug至关重要。

通过遵循这些排查技巧和最佳实践，开发者可以有效地解决ASP.NET Core中的middleware挑战。这确保了他们的应用程序性能最佳、安全并且免受意外错误的影响。

---

## 总结ASP.NET Core中的自定义Middleware

本文详细介绍了ASP.NET Core中的middleware及其在web开发中的重要性。我们介绍了ASP.NET Core中的不同类型的middleware以及如何在web开发中使用middleware。此外，我们还讨论了在使用middleware时面临的常见挑战及其解决方案。一些简单的代码示例希望能帮你朝正确的方向前进！

Middleware在web开发中非常有价值，因为它允许C#开发人员添加功能、修改请求以及执行内置功能无法完成的其他操作。此外，middleware可以帮助简化开发过程并增强整体用户体验 — 如果正确完成的话！

---

## 常见问题解答：ASP.NET Core中的自定义Middleware

### 什么是ASP.NET Core middleware？

ASP.NET Core middleware是位于web服务器和应用程序之间的一个组件，它在它们之间拦截和处理请求和响应。

### middleware在ASP.NET Core中的目的是什么？

ASP.NET Core中middleware的目的是在不修改应用程序代码的情况下，向web应用程序添加额外的功能，如身份验证、日志记录、缓存和安全性。

### middleware如何解决web开发中的特定挑战？

middleware可以通过提供应用程序代码不提供的自定义功能来解决web[开发中的特定挑战](https://www.devleader.ca/?p=5748)。例如，自定义middleware可以处理请求的节流和速率限制、为性能缓存数据或为审计目的记录数据。

### 如何在ASP.NET Core中创建自定义middleware？

要在ASP.NET Core中创建自定义middleware，你可以按照以下步骤操作：

1.  创建一个实现`IMiddleware`接口的类。
2.  将middleware类添加到ASP.NET Core依赖注入容器中。
3.  在middleware类的`InvokeAsync`方法中编写middleware逻辑。

### 在ASP.NET Core中使用middleware时面临的一些常见挑战是什么？

在ASP.NET Core中使用middleware时面临的一些常见挑战包括：

- Middleware顺序：如果没有以正确的顺序添加middleware，可能无法按预期工作。
- 请求/响应处理：如果middleware没有正确处理请求或响应，可能会导致应用程序出现问题。
- 覆盖现有的middleware：如果自定义middleware覆盖了内置middleware，可能会导致应用程序出现冲突。
