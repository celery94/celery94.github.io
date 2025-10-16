---
pubDatetime: 2025-09-02
tags: [".NET", "ASP.NET Core", "AI", "Security"]
  [
    "ASP.NET Core",
    "Authorization",
    "Claims",
    "Security",
    "RBAC",
    "Authentication",
  ]
slug: master-claims-transformation-for-flexible-aspnetcore-authorization
source: https://www.milanjovanovic.tech/blog/master-claims-transformation-for-flexible-aspnetcore-authorization
title: 掌握声明转换，实现灵活的 ASP.NET Core 授权
description: 了解如何在 ASP.NET Core 中实现声明转换，弥合外部身份提供者与应用授权需求之间的差距，并通过 RBAC 示例展示实用方法。
---

在现代 ASP.NET Core 应用程序中，基于声明（Claims）的授权机制是核心的授权方式。然而，外部身份提供者（Identity Provider, IDP）颁发的访问令牌可能并不总是与应用程序内部的授权需求完全一致。

外部 IDP（如 Microsoft Entra ID（前身为 Azure AD）或 Auth0）可能有自己的声明架构，或者可能不会直接颁发应用程序授权逻辑所需的所有声明。

解决方案？声明转换（Claims Transformation）。

声明转换允许您在应用程序使用声明进行授权之前修改声明。在本文中，我们将：

- 探索 ASP.NET Core 中声明转换的概念
- 通过实际示例探索 `IClaimsTransformation` 接口
- 讨论安全性和 RBAC（基于角色的访问控制）的考虑事项

## 声明转换的工作原理

如图所示，声明转换流程如下：

1. 用户通过身份提供者进行身份验证
2. 用户调用后端 API 并提供访问令牌
3. 后端 API 执行声明转换和授权
4. 如果用户被正确授权，后端 API 返回响应

让我们看看如何在 ASP.NET Core 中实现这一点。

## 简单的声明转换

声明可以从受信任身份提供者颁发的任何用户或身份数据创建。声明是一个名称-值对，表示主体的身份，而不是主体可以做什么。

ASP.NET Core 中声明转换的核心是 `IClaimsTransformation` 接口。

它公开了一个用于转换声明的方法：

```csharp
public interface IClaimsTransformation
{
    Task<ClaimsPrincipal> TransformAsync(ClaimsPrincipal principal);
}
```

以下是使用 `IClaimsTransformation` 添加自定义声明的简单示例：

```csharp
internal static class CustomClaims
{
    internal const string CardType = "card_type";
}

internal sealed class CustomClaimsTransformation : IClaimsTransformation
{
    public Task<ClaimsPrincipal> TransformAsync(ClaimsPrincipal principal)
    {
        if (principal.HasClaim(claim => claim.Type == CustomClaims.CardType))
        {
            return Task.FromResult(principal);
        }

        ClaimsIdentity claimsIdentity = new ClaimsIdentity();

        claimsIdentity.AddClaim(new Claim(CustomClaims.CardType, "platinum"));

        principal.AddIdentity(claimsIdentity);

        return Task.FromResult(principal);
    }
}
```

`CustomClaimsTransformation` 类应注册为服务：

```csharp
builder.Services
    .AddTransient<IClaimsTransformation, CustomClaimsTransformation>();
```

最后，您可以定义一个使用此声明的自定义授权策略：

```csharp
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy(
        "HasPlatinumCard",
        builder => builder
            .RequireAuthenticatedUser()
            .RequireClaim(CustomClaims.CardType, "platinum"));
});
```

使用 `IClaimsTransformation` 时有一些注意事项：

- **可能多次执行**：`TransformAsync` 方法可能会被多次调用。声明转换应该是幂等的，以避免向 `ClaimsPrincipal` 多次添加相同的声明。
- **潜在的性能影响**：由于它在身份验证请求时执行，请注意转换逻辑的性能，特别是如果涉及外部调用（数据库、API）。在适当的地方考虑缓存。

## 使用声明转换实现 RBAC

基于角色的访问控制（RBAC）是一种授权模型，其中权限分配给角色，用户被授予角色。声明转换有助于顺利实现 RBAC。通过添加角色声明和潜在的权限声明，可以简化整个应用程序的授权逻辑。另一个好处是您可以保持访问令牌较小且不包含任何角色或权限声明。

让我们考虑一个场景，您的应用程序在细粒度级别管理资源，但您的身份提供者只提供粗粒度角色，如 `Registered` 或 `Member`。您可以使用声明转换将 `Member` 角色映射到特定的细粒度权限，如 `SubmitOrder` 和 `PurchaseTicket`。

以下是更复杂的 `CustomClaimsTransformation` 实现。我们使用 `GetUserPermissionsQuery` 发送数据库查询并获取 `PermissionsResponse`。`PermissionsResponse` 包含用户的权限，这些权限被添加为自定义声明。

```csharp
internal sealed class CustomClaimsTransformation(
    IServiceProvider serviceProvider)
    : IClaimsTransformation
{
    public async Task<ClaimsPrincipal> TransformAsync(
        ClaimsPrincipal principal)
    {
        if (principal.HasClaim(c => c.Type == CustomClaims.Sub ||
                                    c.Type == CustomClaims.Permission))
        {
            return principal;
        }

        using IServiceScope scope = serviceProvider.CreateScope();

        ISender sender = scope.ServiceProvider.GetRequiredService<ISender>();

        string identityId = principal.GetIdentityId();

        Result<PermissionsResponse> result = await sender.Send(
            new GetUserPermissionsQuery(identityId));

        if (result.IsFailure)
        {
            throw new ClaimsAuthorizationException(
                nameof(GetUserPermissionsQuery), result.Error);
        }

        var claimsIdentity = new ClaimsIdentity();

        claimsIdentity.AddClaim(
            new Claim(CustomClaims.Sub, result.Value.UserId.ToString()));

        foreach (string permission in result.Value.Permissions)
        {
            claimsIdentity.AddClaim(
                new Claim(CustomClaims.Permission, permission));
        }

        principal.AddIdentity(claimsIdentity);

        return principal;
    }
}
```

现在 `ClaimsPrincipal` 包含权限作为自定义声明，您可以做一些有趣的事情。例如，您可以实现基于权限的 `AuthorizationHandler`：

```csharp
internal sealed class PermissionAuthorizationHandler
    : AuthorizationHandler<PermissionRequirement>
{
    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        PermissionRequirement requirement)
    {
        HashSet<string> permissions = context.User.GetPermissions();

        if (permissions.Contains(requirement.Permission))
        {
            context.Succeed(requirement);
        }

        return Task.CompletedTask;
    }
}
```

## 要点总结

声明转换是在身份提供者提供的声明和 ASP.NET Core 应用程序需求之间架起桥梁的优雅方式。`IClaimsTransformation` 接口使您能够自定义当前 `ClaimsPrincipal` 的声明。无论您需要添加角色、将外部组映射到内部权限，还是从用户配置文件中提取其他信息，声明转换都提供了这样做的灵活性。

但是，在使用声明转换时，请记住几个关键考虑事项：

- 声明转换在每个请求上执行
- `IClaimsTransformation` 应该是幂等的。如果多次执行，它不应该向 `ClaimsPrincipal` 添加现有声明
- 高效地设计您的转换，如果您正在获取外部数据来丰富声明，请考虑缓存结果
