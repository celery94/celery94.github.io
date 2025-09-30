---
pubDatetime: 2025-09-30
title: 在 ASP.NET Core 中构建基于权限的授权体系：从角色到细粒度访问控制
description: 深入探讨如何在 ASP.NET Core 中实现基于角色的访问控制（RBAC），通过自定义授权处理器、权限声明转换和扩展方法，构建灵活、可维护的企业级授权系统，避免硬编码角色检查带来的维护噩梦。
tags:
  [".NET", "ASP.NET Core", "Security", "Authorization", "Clean Architecture"]
slug: aspnetcore-rbac-permission-based-authorization
source: https://www.milanjovanovic.tech/blog/building-secure-apis-with-role-based-access-control-in-aspnetcore
---

在企业级应用中，授权往往从简单的"是否为管理员"判断开始，但随着业务复杂度提升，硬编码的角色检查会演变成难以维护的技术债务。真正可扩展的授权体系应该建立在权限（Permission）之上，让角色成为权限的载体，而非判断依据。本文将展示如何在 ASP.NET Core 中构建细粒度的权限授权系统，从自定义授权处理器到生产环境的优化策略。

## 理解 RBAC 的三层架构

基于角色的访问控制（Role-Based Access Control，RBAC）本质上是一个三层映射关系：用户被分配到角色，角色包含权限，权限定义具体操作。这种分层设计的优势在于解耦：当需要调整某个角色的权限范围时，只需修改角色与权限的关联，无需触碰用户分配逻辑。

传统的授权实现常见的做法是在代码中直接检查 `User.IsInRole("Admin")`，这种方式存在三个主要问题：首先，角色名称以字符串形式散落在代码各处，重命名或调整角色体系需要全局搜索替换；其次，业务规则与代码强耦合，新增角色或调整权限边界都需要修改代码并重新部署；最后，无法灵活支持"一个用户拥有多个角色"或"临时授予某个用户特定权限"的场景。

权限驱动的授权体系则把焦点从"你是谁"转移到"你能做什么"。例如定义 `users:read`、`orders:create`、`reports:export` 这样的权限标识符，然后在授权检查点验证用户是否拥有对应权限，而不关心这些权限来自哪个角色。角色成为权限的打包单位，`Manager` 角色可能包含 `users:read`、`reports:export` 等权限，调整角色定义只需更新数据库关联表，代码逻辑保持不变。

这种架构还支持更灵活的扩展：可以为特定用户添加额外权限而无需创建新角色，也能实现权限的临时授予与回收。当系统演进到需要支持多租户、资源级权限（如"只能编辑自己创建的订单"）时，也能在此基础上平滑扩展。

## 实现自定义授权处理器

ASP.NET Core 的授权框架围绕策略（Policy）和需求（Requirement）构建。要实现权限检查，需要创建一个同时实现 `IAuthorizationRequirement` 和 `AuthorizationHandler<T>` 的类型，把需求定义与验证逻辑封装在一起：

```csharp
using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;

public class PermissionAuthorizationRequirement(params string[] allowedPermissions)
    : AuthorizationHandler<PermissionAuthorizationRequirement>, IAuthorizationRequirement
{
    public string[] AllowedPermissions { get; } = allowedPermissions;

    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        PermissionAuthorizationRequirement requirement)
    {
        foreach (var permission in requirement.AllowedPermissions)
        {
            bool found = context.User.FindFirst(c =>
                c.Type == CustomClaimTypes.Permission &&
                c.Value == permission) is not null;

            if (found)
            {
                context.Succeed(requirement);
                break;
            }
        }

        return Task.CompletedTask;
    }
}

public static class CustomClaimTypes
{
    public const string Permission = "permission";
}
```

这个处理器的核心逻辑是遍历用户的声明（Claims），查找类型为 `permission` 且值匹配任一所需权限的声明。注意这是"或"逻辑：只要用户拥有其中一个权限即可通过验证。如果业务场景要求同时具备多个权限，可以改为在循环外统一判断或改用"与"逻辑。

当找到匹配的权限时，调用 `context.Succeed(requirement)` 并提前退出，避免无谓的遍历。如果所有权限都不匹配，方法返回时 `context` 未被标记为成功，授权框架会拒绝请求。

权限声明的来源通常是在用户认证时写入 JWT 或 Cookie。在生成访问令牌时，需要查询用户的角色及其关联的权限，然后把权限作为声明注入：

```csharp
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

var permissions = await (
        from role in dbContext.Roles
        join userRole in dbContext.UserRoles on role.Id equals userRole.RoleId
        join permission in dbContext.RolePermissions on role.Id equals permission.RoleId
        where userRole.UserId == user.Id
        select permission.Name)
    .Distinct()
    .ToArrayAsync();

List<Claim> claims =
[
    new(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
    new(JwtRegisteredClaimNames.Email, user.Email!),
    ..roles.Select(r => new Claim(ClaimTypes.Role, r)),
    ..permissions.Select(p => new Claim(CustomClaimTypes.Permission, p))
];

var tokenDescriptor = new SecurityTokenDescriptor
{
    Subject = new ClaimsIdentity(claims),
    Expires = DateTime.UtcNow.AddMinutes(expirationMinutes),
    SigningCredentials = credentials,
    Issuer = issuer,
    Audience = audience
};

var tokenHandler = new JsonWebTokenHandler();
string accessToken = tokenHandler.CreateToken(tokenDescriptor);
```

这种方式把权限直接嵌入令牌，客户端每次请求时携带令牌，服务端解析声明即可完成授权判断，无需额外的数据库查询。但要注意令牌大小：如果用户拥有大量权限，令牌可能超过 HTTP 头大小限制，此时需要考虑服务端权限解析方案。

## 构建开发者友好的 API 接口

直接在每个端点配置授权策略虽然可行，但代码冗长且不易维护。通过扩展方法可以大幅提升开发体验。首先为策略构建器添加权限验证的扩展方法：

```csharp
using Microsoft.AspNetCore.Authorization;

public static class PermissionExtensions
{
    public static void RequirePermission(
        this AuthorizationPolicyBuilder builder,
        params string[] allowedPermissions)
    {
        builder.AddRequirements(new PermissionAuthorizationRequirement(allowedPermissions));
    }
}
```

定义权限常量以避免魔法字符串：

```csharp
public static class Permissions
{
    public const string UsersRead = "users:read";
    public const string UsersUpdate = "users:update";
    public const string UsersDelete = "users:delete";
    public const string OrdersCreate = "orders:create";
    public const string ReportsExport = "reports:export";
}
```

在 Minimal API 中使用扩展方法：

```csharp
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

app.MapGet("api/users/me", async (
    [FromServices] ApplicationDbContext dbContext,
    ClaimsPrincipal user) =>
{
    var userId = int.Parse(user.FindFirstValue(JwtRegisteredClaimNames.Sub)!);

    var userDto = await dbContext.Users
        .AsNoTracking()
        .Where(u => u.Id == userId)
        .Select(u => new UserDto
        {
            Id = u.Id,
            Email = u.Email,
            FirstName = u.FirstName,
            LastName = u.LastName
        })
        .SingleOrDefaultAsync();

    return Results.Ok(userDto);
})
.RequireAuthorization(policy => policy.RequirePermission(Permissions.UsersRead));
```

对于 MVC 控制器，可以创建自定义特性：

```csharp
using Microsoft.AspNetCore.Authorization;

[AttributeUsage(AttributeTargets.Method | AttributeTargets.Class)]
public class RequirePermissionAttribute : AuthorizeAttribute
{
    public RequirePermissionAttribute(params string[] permissions)
        : base(policy: string.Join(",", permissions))
    {
    }
}
```

需要在依赖注入容器中注册对应的策略：

```csharp
builder.Services.AddAuthorizationBuilder()
    .AddPolicy(Permissions.UsersRead,
        policy => policy.RequirePermission(Permissions.UsersRead))
    .AddPolicy(Permissions.UsersUpdate,
        policy => policy.RequirePermission(Permissions.UsersUpdate))
    .AddPolicy(Permissions.UsersDelete,
        policy => policy.RequirePermission(Permissions.UsersDelete));
```

使用时非常简洁：

```csharp
[RequirePermission(Permissions.UsersUpdate)]
public async Task<IActionResult> UpdateUser(int id, UpdateUserRequest request)
{
    // 业务逻辑
}
```

这种封装让授权检查的意图清晰可见，同时保持了类型安全和可测试性。

## 生产环境的优化策略

基础实现已经能够满足大多数场景，但在生产环境中还需要考虑性能与可维护性的进一步提升。

### 使用枚举替代字符串常量

字符串常量虽然简单，但缺乏编译期检查，拼写错误只能在运行时发现。可以改用枚举提升类型安全：

```csharp
public enum Permission
{
    UsersRead,
    UsersUpdate,
    UsersDelete,
    OrdersCreate,
    OrdersView,
    ReportsExport
}
```

在声明与检查时需要进行字符串转换：

```csharp
public static class PermissionExtensions
{
    public static string ToClaimValue(this Permission permission)
    {
        return permission.ToString().ToLowerInvariant().Replace("_", ":");
    }

    public static Permission? FromClaimValue(string value)
    {
        var enumName = value.Replace(":", "_");
        return Enum.TryParse<Permission>(enumName, ignoreCase: true, out var result)
            ? result
            : null;
    }
}
```

这样既保留了枚举的类型安全，又能与字符串形式的声明系统兼容。

### 服务端权限解析

把所有权限都编码进 JWT 会导致令牌体积过大，尤其是用户拥有数十个权限时。更优的方案是在服务端动态加载权限，通过 `IClaimsTransformation` 接口实现：

```csharp
using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Caching.Memory;

public class PermissionClaimsTransformation(
    IPermissionService permissionService,
    IMemoryCache cache) : IClaimsTransformation
{
    private static readonly TimeSpan CacheDuration = TimeSpan.FromMinutes(5);

    public async Task<ClaimsPrincipal> TransformAsync(ClaimsPrincipal principal)
    {
        if (principal.Identity?.IsAuthenticated != true)
        {
            return principal;
        }

        var userId = principal.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (userId == null)
        {
            return principal;
        }

        var cacheKey = $"permissions:{userId}";

        var permissions = await cache.GetOrCreateAsync(cacheKey, async entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = CacheDuration;
            return await permissionService.GetUserPermissionsAsync(userId);
        });

        var claimsIdentity = (ClaimsIdentity)principal.Identity;
        foreach (var permission in permissions ?? [])
        {
            if (!claimsIdentity.HasClaim(CustomClaimTypes.Permission, permission))
            {
                claimsIdentity.AddClaim(new Claim(CustomClaimTypes.Permission, permission));
            }
        }

        return principal;
    }
}
```

在依赖注入容器中注册：

```csharp
builder.Services.AddScoped<IClaimsTransformation, PermissionClaimsTransformation>();
```

这个转换器在认证管道中自动运行，从数据库或缓存中加载用户权限并注入到声明集合。关键在于缓存策略：权限变更不频繁，5 到 15 分钟的缓存可以大幅减少数据库查询，同时保持足够的实时性。

如果权限需要立即生效，可以在权限变更时主动清除对应用户的缓存，或者使用分布式缓存（如 Redis）并通过发布/订阅机制通知所有节点清除缓存。

### 资源级权限的扩展

当授权逻辑需要检查资源所有权时（例如"只能删除自己创建的订单"），可以扩展需求类型：

```csharp
public class ResourcePermissionRequirement(
    string permission,
    string resourceType) : IAuthorizationRequirement
{
    public string Permission { get; } = permission;
    public string ResourceType { get; } = resourceType;
}

public class ResourcePermissionHandler(IHttpContextAccessor httpContextAccessor)
    : AuthorizationHandler<ResourcePermissionRequirement>
{
    protected override async Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        ResourcePermissionRequirement requirement)
    {
        if (!context.User.HasClaim(c =>
            c.Type == CustomClaimTypes.Permission &&
            c.Value == requirement.Permission))
        {
            return;
        }

        var httpContext = httpContextAccessor.HttpContext;
        if (httpContext == null)
        {
            return;
        }

        // 从路由或请求体中提取资源 ID
        var resourceId = httpContext.GetRouteValue("id")?.ToString();
        if (resourceId == null)
        {
            return;
        }

        var userId = context.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

        // 调用服务检查资源所有权
        // var hasAccess = await resourceService.CanAccessAsync(
        //     userId, requirement.ResourceType, resourceId);

        // if (hasAccess) context.Succeed(requirement);
    }
}
```

这种模式适合需要结合业务规则的场景，但要注意性能：每次授权检查都可能触发数据库查询，需要配合缓存和高效的查询设计。

## 小结

基于权限的授权体系把"你是谁"的判断转换为"你能做什么"的验证，通过分离角色与权限的映射关系，让授权逻辑与业务规则解耦。ASP.NET Core 的授权框架提供了扩展点，自定义 `AuthorizationHandler` 可以实现任意复杂度的权限检查逻辑，而扩展方法和自定义特性则让 API 接口保持简洁。

在生产环境中，通过枚举提升类型安全、使用 `IClaimsTransformation` 实现服务端权限加载、合理配置缓存策略，可以在保持灵活性的同时优化性能。当系统演进到需要支持资源级权限或多租户隔离时，这套架构也能平滑扩展。

关键在于前期设计好权限标识符的命名规范（如 `resource:action` 模式）、权限与角色的关联策略，以及缓存与失效机制，这样才能在业务复杂度提升时避免重构授权系统的噩梦。

## 参考资料

- [Building Secure APIs with Role-Based Access Control in ASP.NET Core](https://www.milanjovanovic.tech/blog/building-secure-apis-with-role-based-access-control-in-aspnetcore)
- [ASP.NET Core Authorization Documentation](https://learn.microsoft.com/en-us/aspnet/core/security/authorization/introduction)
- [Master Claims Transformation for Flexible ASP.NET Core Authorization](https://www.milanjovanovic.tech/blog/master-claims-transformation-for-flexible-aspnetcore-authorization)
