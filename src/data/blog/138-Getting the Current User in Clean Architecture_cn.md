---
pubDatetime: 2024-05-13
tags: [".NET", "C#", "Architecture"]
source: https://www.milanjovanovic.tech/blog/getting-the-current-user-in-clean-architecture?utm_source=Twitter&utm_medium=social&utm_campaign=06.05.2024
author: Milan Jovanović
title: 在 Clean Architecture 中获取当前用户
description: 你构建的应用服务于你的用户（客户），以帮助他们解决一些问题。通常你需要知道当前应用的用户是谁，这是一个常见的需求。
---

# 在 Clean Architecture 中获取当前用户

> ## 摘要
>
> 你构建的应用服务于你的用户（客户），以帮助他们解决一些问题。通常你需要知道当前应用的用户是谁，这是一个常见的需求。
>
> 原文 [Getting the Current User in Clean Architecture](https://www.milanjovanovic.tech/blog/getting-the-current-user-in-clean-architecture?utm_source=Twitter&utm_medium=social&utm_campaign=06.05.2024) 由 [Milan Jovanović](https://www.milanjovanovic.tech/) 发表。

---

你构建的应用服务于你的用户（客户）以帮助他们解决一些问题。通常你需要知道当前应用的用户是谁。

在 Clean Architecture 使用场景中，如何获取当前用户的信息？

Use cases 存在于应用层，你不能引入外部关注点。否则，你将会违反依赖规则。

假设你想知道当前用户是谁，以确定他们是否可以访问某些资源。这是你典型的基于资源的授权检查。但你必须与身份提供者交互来获得这些信息。这违反了 [在 Clean Architecture 中的依赖规则。](https://www.milanjovanovic.tech/blog/clean-architecture-and-the-benefits-of-structured-software-design)

我见过这个问题让一些初次接触 Clean Architecture 的开发人员感到困惑。

在今天的问题中，我将向你展示如何以一种清洁的方式访问当前用户的信息。

## 从抽象开始

Clean Architecture 的内层为外部关注点定义了抽象。从应用层的视角来看，认证和用户身份是外部关注点。

Infrastructure 层处理外部关注点，包括认证和身份管理。这里是你将实现抽象的地方。

我首选的方法是创建一个 `IUserContext` 抽象。我需要的主要信息是当前用户的 `UserId`。但你可以根据需要将 `IUserContext` 扩展为包含任何其他数据。

````csharp
public interface IUserContext
{
    bool IsAuthenticated { get; }

    Guid UserId { get; }
}
```

让我们看看如何实现 `IUserContext`。

## 实现 UserContext

`UserContext` 类是 Infrastructure 层中的 `IUserContext` 实现。我们需要注入 `IHttpContextAccessor`，它允许我们通过 `User` 属性访问 [`ClaimsPrincipal`](https://learn.microsoft.com/en-us/dotnet/api/system.security.claims.claimsprincipal?view=net-8.0)。`ClaimsPrincipal` 为你提供了访问当前用户声明的方法，包含所需的信息。

在这个示例中，如果任何属性评估为 `null` 我会抛出一个异常。你可以决定是否让抛出异常对你来说有意义。

我还想在这里分享一个关于 `IHttpContextAccessor` 的重要备注。我们使用它来访问 `HttpContext` 实例 — **它只在一个 API 请求期间存在**。在 API 请求之外，`HttpContext` 会为 null，并且在访问其属性时 `UserContext` 会抛出异常。

```csharp
internal sealed class UserContext(IHttpContextAccessor httpContextAccessor)
    : IUserContext
{
    public Guid UserId =>
        httpContextAccessor
            .HttpContext?
            .User
            .GetUserId() ??
        throw new ApplicationException("User context is unavailable");

    public bool IsAuthenticated =>
        httpContextAccessor
            .HttpContext?
            .User
            .Identity?
            .IsAuthenticated ??
        throw new ApplicationException("User context is unavailable");
}
````

这里是在 `UserContext.UserId` 属性中使用的 `GetUserId` 扩展方法。它寻找一个名为 `ClaimTypes.NameIdentifier` 的声明，并将该值解析为 `Guid`。你可以替换这个类型以匹配你的系统中的用户身份。

```csharp
internal static class ClaimsPrincipalExtensions
{
    public static Guid GetUserId(this ClaimsPrincipal? principal)
    {
        string? userId = principal?.FindFirstValue(ClaimTypes.NameIdentifier);

        return Guid.TryParse(userId, out Guid parsedUserId) ?
            parsedUserId :
            throw new ApplicationException("User id is unavailable");
    }
}
```

## 使用当前用户信息

现在你有了 `IUserContext`，你可以从应用层使用它。

一个常见的需求是检查当前用户是否可以访问某些资源。

这里有一个使用 `GetInvoiceQueryHandler` 的示例，它查询数据库以获取发票。在将结果投影到 `InvoiceResponse` 对象后，我们检查当前用户是否是发票的发行对象。你也可以将此检查作为数据库查询的一部分。但在内存中执行它让你可以在未授权时向用户返回不同的响应。例如，一个 [403 Forbidden](https://www.rfc-editor.org/rfc/rfc7231#section-6.5.3) 可能是合适的。

```csharp
class GetInvoiceQueryHandler(IAppDbContext dbContext, IUserContext userContext)
    : IQueryHandler<GetInvoiceQuery, InvoiceResponse>
{
    public async Task<Result<InvoiceResponse>> Handle(
        GetInvoiceQuery request,
        CancellationToken cancellationToken)
    {
        InvoiceResponse? invoiceResponse = await dbContext
            .Invoices
            .ProjectTo<InvoiceResponse>()
            .FirstOrDefaultAsync(
                invoice => invoice.Id == request.InvoiceId,
                cancellationToken);

        if (invoiceResponse is null ||
            invoiceResponse.IssuedToUserId != userContext.UserId)
        {
            return Result.Failure<InvoiceResponse>(InvoiceErrors.NotFound);
        }

        return invoiceResponse;
    }
}
```

## 总结

将用户标识和认证整合进 [Clean Architecture](https://www.milanjovanovic.tech/blog/why-clean-architecture-is-great-for-complex-projects) 不必破坏你的设计的完整性。应用层应该保持与外部关注点如身份管理的解耦。

我们通过 `IUserContext` 接口抽象用户相关信息，并在 Infrastructure 层中实现它，遵守了 [Clean Architecture 的依赖规则](https://www.milanjovanovic.tech/blog/clean-architecture-and-the-benefits-of-structured-software-design)。

通过这一策略，你可以有效地管理用户信息，支持授权检查，确保你的应用保持稳健并能适应未来的变化。

记住，关键在于定义清晰的抽象并尊重架构的边界。
