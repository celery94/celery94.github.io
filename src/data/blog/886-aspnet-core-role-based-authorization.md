---
pubDatetime: 2026-06-18T08:00:00+08:00
title: "ASP.NET Core 角色授权实战：JWT + Minimal API + .NET 10"
description: "从零实现 ASP.NET Core .NET 10 的角色授权：把角色写入 JWT，用 RequireRole 保护 Minimal API 端点，理清 OR/AND 语义差异，以及解决角色死活不生效的 claim-mapping 陷阱。附带 GitHub 可运行源码。"
tags: ["ASP.NET Core", ".NET", "JWT", "授权", "Web API", "Minimal API"]
slug: "aspnet-core-role-based-authorization"
source: "https://codewithmukesh.com/blog/role-based-authorization-in-aspnet-core/"
ogImage: "../../assets/886/01-cover.png"
---

## 角色是怎么从数据库走到端点的

认证回答"你是谁"，授权回答"你能做什么"。在上一篇 [JWT 认证文章](https://codewithmukesh.com/blog/jwt-authentication-in-aspnet-core/) 里已经实现了用户登录拿 token，现在要做的就是把不同角色的人限制在不同端点前。

角色检查涉及三个地方，它们必须保持一致：

1. **Identity 存储** — ASP.NET Core Identity 在 `AspNetUsers` 和 `AspNetRoles` 表中维护用户和角色（演示项目用了内存数据库，不必搭 SQL Server）。
2. **JWT** — 登录时从 Identity 读出用户角色，写入 token 的 claims，一个角色一条 claim。
3. **ClaimsPrincipal** — 每次请求，JWT bearer 中间件验证 token 并从 claims 重建用户对象。`RequireRole` 和 `User.IsInRole()` 检查的是这个对象，不是数据库。

![角色从 Identity 存储到 JWT Claim 再到 ClaimsPrincipal 的流转](../../assets/886/02-roles-flow.png)

由此产生两个容易被忽略的事实：

- 角色检查永远不查数据库。token 签发后，里面带的角色就是唯一依据，这也是 JWT 能无状态横向扩展的根本原因。
- token 里的角色在下次登录前不会变。你把某人提为 Admin，他手里的旧 token 还是原来的角色，必须重新登录换 token。这就是为什么 token 要短时效、配 refresh token。

## 演示 API 的前置条件

演示项目基于 .NET 10，NuGet 包 `Microsoft.AspNetCore.Authentication.JwtBearer` 10.0.0 和 `Scalar.AspNetCore` 2.13.18。完整源码在 [GitHub](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/05-api-security/role-based-authorization-in-aspnet-core)。

场景是一个产品库存 API，三个角色、三个种子用户：

| 邮箱                       | 密码        | 角色           |
| -------------------------- | ----------- | -------------- |
| admin@codewithmukesh.com   | Admin123!   | Admin, Manager |
| manager@codewithmukesh.com | Manager123! | Manager        |
| user@codewithmukesh.com    | User123!    | User           |

注意 Admin 同时持有 Admin 和 Manager 两个角色，后面讲 AND 语义时会用到。

角色名放在一个静态类里，避免拼写错误。角色名作为 claim 值后是大小写敏感的，`"admin"` 和 `"Admin"` 是两个不同角色：

```csharp
// Entities/Roles.cs
public static class Roles
{
    public const string Admin = "Admin";
    public const string Manager = "Manager";
    public const string User = "User";
}
```

## 把角色写入 JWT

登录时从 Identity 读取用户角色，每个角色一条 `role` claim：

```csharp
// Auth/TokenService.cs
var claims = new List<Claim>
{
    new(JwtRegisteredClaimNames.Sub, user.Id),
    new(JwtRegisteredClaimNames.Email, user.Email!),
    new(JwtRegisteredClaimNames.Name, $"{user.FirstName} {user.LastName}"),
    new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
};

// 每个角色一条 "role" claim，RequireRole 后面要读的就是它
claims.AddRange(roles.Select(role => new Claim("role", role)));
```

把 manager 的 token 拿到 [jwt.io](https://jwt.io/) 解码，payload 里直接就是 `"role": "Manager"`。Admin 的 token 里是 `"role": ["Admin", "Manager"]` — 同类型多条 claim 自动折叠为数组。

关键认知：**角色只是一条名字约定好的 claim**，不是什么独立于 JWT 之外的机制。记住这句话，它是理解后续 claims-based 授权的基础。

接收端需要告诉 ASP.NET Core 用哪个 claim 名字存放角色，也就是 `RoleClaimType`：

```csharp
// Program.cs
.AddJwtBearer(options =>
{
    // 保持 claim 名字原样，不要让中间件做 legacy 重映射
    options.MapInboundClaims = false;
    options.TokenValidationParameters = new TokenValidationParameters
    {
        // ... issuer, audience, signing key 照常配 ...
        NameClaimType = JwtRegisteredClaimNames.Name,
        // RoleClaimType 必须和 TokenService 写入角色的 claim 名一致
        // 这两行不一致，所有角色检查返回 403
        RoleClaimType = "role"
    };
});
```

写入用 `"role"`，读取也用 `"role"`。一半以上"角色不生效"的 bug 就是这两行没对齐。后面有专门的排错章节。

## 用 RequireRole 保护端点

角色在 token 里、`RoleClaimType` 也配好了，保护端点只需要一行代码。下面是 Minimal API 风格的产品接口：

```csharp
// Endpoints/ProductEndpoints.cs
public static void MapProductEndpoints(this IEndpointRouteBuilder app)
{
    // 组级 RequireAuthorization()：/api/products 下所有端点都要有效 token
    var group = app.MapGroup("/api/products")
        .WithTags("Products")
        .RequireAuthorization();

    // 任何已认证用户都能看产品列表，不需要特定角色
    group.MapGet("/", (ProductStore store) =>
        Results.Ok(store.GetAll()));

    // 只有 Admin 能删除。Manager 调用会收到 403
    group.MapDelete("/{id:int}", (int id, ProductStore store) =>
            store.Delete(id) ? Results.NoContent() : Results.NotFound())
        .RequireAuthorization(policy =>
            policy.RequireRole(Roles.Admin));
}
```

两层控制：组级 `RequireAuthorization()` 说"必须登录才能碰 `/api/products` 下面的东西"，端点级 `RequireRole` 说"而且对这个端点，你还得是 Admin"。没 token 的人收到 `401`，已登录的 Manager 调 DELETE 收到 `403`。

`401` 和 `403` 的区别值得记住：`401` 是"我不知道你是谁"，`403` 是"我知道你是谁，答案是拒绝"。

如果用的是 Controller 而非 Minimal API，同样的检查是经典的 attribute 写法：

```csharp
[Authorize(Roles = "Admin")]
[HttpDelete("{id}")]
public IActionResult Delete(int id) { ... }
```

另外别忘了 `app.UseAuthentication()` 必须在 `app.UseAuthorization()` 前面。认证先搞清楚你是谁，授权再决定你能做什么。顺序反了，所有受保护调用全部失败。

## 多个角色：OR 还是 AND

这个问题几乎所有人都搞反过一次，因为回答取决于你怎么写。

### 一次调用里传多个角色 = OR

`RequireRole("Admin", "Manager")` 表示 Admin **或** Manager，满足任意一个就能过：

```csharp
// Admin 或 Manager 都能创建产品
group.MapPost("/", (CreateProductRequest request, ProductStore store) =>
    {
        var product = store.Add(request);
        return Results.Created($"/api/products/{product.Id}", product);
    })
    .RequireAuthorization(policy =>
        policy.RequireRole(Roles.Admin, Roles.Manager));
```

Controller 的 `[Authorize(Roles = "Admin,Manager")]` 行为相同 — Admin OR Manager。逗号读起来像"和"，语义上却是"或"，所以开发者经常搞反。

### 链式调用 = AND

链式写两个 `RequireRole`，调用者必须同时持有两个角色：

```csharp
// 同时需要 Admin 和 Manager 两个角色
group.MapGet("/audit", () =>
        Results.Ok("Stock audit report. You hold both the Admin and Manager roles."))
    .RequireAuthorization(policy => policy
        .RequireRole(Roles.Admin)
        .RequireRole(Roles.Manager));
```

Controller 里堆叠 attribute 实现 AND：

```csharp
[Authorize(Roles = "Admin")]
[Authorize(Roles = "Manager")]  // 必须同时满足两个 attribute
```

在演示项目里，种子 Admin 同时持有 Admin 和 Manager，所以 `/audit` 能过。Manager 只有一个角色，返回 `403`。

## 给角色检查起个名字：命名 Policy

内联 `RequireRole` 写一两个端点还行，三个端点需要同样的检查就该给它一个名字，集中定义一次。.NET 7 引入的 `AddAuthorizationBuilder()` 是 .NET 10 的标准写法：

```csharp
// Program.cs
builder.Services.AddAuthorizationBuilder()
    .AddPolicy("ManagerOnly", policy =>
        policy.RequireRole(Roles.Manager));
```

端点直接用名字引用：

```csharp
group.MapPut("/{id:int}/restock", (int id) =>
        Results.Ok($"Product {id} restocked."))
    .RequireAuthorization("ManagerOnly");
```

改一处，"ManagerOnly" 的含义在所有引用的端点上同时生效。这已经是 policy-based 授权的雏形了 — 在底层，就连内联 `RequireRole` 其实也会变成 policy。完整的 policy 体系（requirements、handlers、自定义规则）是这个系列的第三篇文章。

## 在代码里用 IsInRole 做分支

不是每个角色判断都是"放行或拒绝"。有些时候同一个端点要对不同角色返回不同数据。注入 `ClaimsPrincipal`，用 `IsInRole()` 做分支：

```csharp
group.MapGet("/dashboard", (ClaimsPrincipal user) =>
{
    var greeting = $"Hello {user.Identity?.Name}.";

    if (user.IsInRole(Roles.Admin))
    {
        return Results.Ok(
            $"{greeting} Full dashboard: sales, inventory, and user management.");
    }

    return user.IsInRole(Roles.Manager)
        ? Results.Ok($"{greeting} Manager dashboard: inventory and restock queue.")
        : Results.Ok($"{greeting} Your orders and saved items.");
});
```

`IsInRole("Admin")` 只是在问：这个 principal 有没有一条值为 `Admin` 的 role claim。数据还是那套数据，`RoleClaimType` 还是那套规则，区别只是在代码里命令式地判断而非声明式地要求。

一个经验法则：**答案是非黑即白的放行/拒绝，用 `RequireRole`；答案是"给他们看不一样的东西"，用 `IsInRole`**。如果发现自己写了一长串 `IsInRole` 的 if-else 来守卫访问，那这逻辑应该挪到 policy 里去。

## 验证：从头跑一遍

克隆 [GitHub 仓库](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/05-api-security/role-based-authorization-in-aspnet-core)，运行 `dotnet run --project RoleBasedAuth.Api`，打开 Scalar UI（`/scalar/v1`）或用 `requests.http` 文件。

按这个顺序验证：

- `GET /api/products`，不带 token → `401 Unauthorized`
- `GET /api/products`，用普通用户登录 → `200 OK`，任何已认证用户都能看
- `POST /api/products`，用 manager 登录 → `201 Created`，Manager 通过 Admin-OR-Manager 检查
- `POST /api/products`，用普通用户登录 → `403 Forbidden`
- `DELETE /api/products/1`，用 manager 登录 → `403 Forbidden`，只有 Admin 能删
- `DELETE /api/products/1`，用 admin 登录 → `204 No Content`
- `GET /api/products/audit`，用 admin 登录 → `200 OK`，同时持有 Admin 和 Manager
- `GET /api/products/audit`，用 manager 登录 → `403 Forbidden`，只有 Manager 不够

## 角色为什么不生效？排查指南

token 里明明有角色，但每个角色检查都返回 `403`。绝大多数情况是 claim 类型映射的问题。

旧的 JWT handler 有一个遗留兼容行为：当 `MapInboundClaims` 为 `true`（历史默认值），传入的 claim 名会被翻译成长长的 SOAP 风格 URI。你的 `role` claim 到了 `ClaimsPrincipal` 里变成了 `http://schemas.microsoft.com/ws/2008/06/identity/claims/role`。然后 `RequireRole` 按 `RoleClaimType` 的值去找 role — 什么都没找到，因为 claim 挂在另一个名字下面。检查静默失败：没有异常，没有日志，只有 `403`。

解决方案是让三样东西对齐：

1. **token 创建时写入的 claim 名** — 本教程用 `"role"`
2. **`MapInboundClaims = false`** — 让中间件不在传入时做任何重命名
3. **`RoleClaimType = "role"`** — 让角色检查去读你实际写入的那个 claim

调试时加一个诊断端点，直接看服务端实际拿到了什么 claims：

```csharp
group.MapGet("/debug/claims", (ClaimsPrincipal user) =>
        Results.Ok(user.Claims.Select(c => new { c.Type, c.Value })))
    .RequireAuthorization();
```

用出问题的 token 调它。如果 role claim 的 `Type` 是一个长 URL 而不是 `"role"`，bug 就找到了。上线前记得删掉这个端点 — 它暴露的信息比你愿意公开的多。

另外三个快速排查点：

- **每个请求都返回 403，包括登录？** 检查是不是把 `RequireAuthorization()` 加到了 auth 组本身上 — 登录端点必须保持匿名。
- **角色加上了但还是 403？** 用户手里的 token 签发时间早于角色变更。角色在登录时读取，重新登录一次就好了。这事每个人都中过一次招。
- **Scalar 里正常，前端 SPA 调就挂？** 通常是 [CORS](https://codewithmukesh.com/blog/cors-in-aspnet-core/) 在授权运行之前就拒绝了 preflight，不是角色问题。

## 什么时候角色检查开始不好用了

角色适合宽泛的用户分组。当你开始为单个能力发明角色名时，就该换工具了。

一开始总是很干净：`Admin`、`Manager`、`User`。然后业务要求"Manager 能补货但不能新增产品"，于是你加了 `SeniorManager`。然后是"客户管理员不能碰订单"，于是有了 `CustomerAdmin`、`OrderAdmin`。作者在生产系统里见过角色从 3 个膨胀到 15 个，端点上的检查变成了 `RequireRole("Admin", "OrderAdmin", "SeniorManager", "RegionalLead")`，而且没人能回答"RegionalLead 到底能做什么"而不去读完整个代码库。

角色描述的是"某人是谁"。业务反复追问的是"某人能做什么"，这是两个不同的问题。

经验法则：当你的访问模型稳定在 5 个以内分组，规则是"这个组能，那个组不能"时，角色授权是正确的选择。一旦你开始为一个单独的能力发明角色名 — 这意味着你在用角色名编码 claims — 就该换到 [claims-based 授权](https://codewithmukesh.com/blog/claims-based-authorization-in-aspnet-core/) 了。而当 claims 也不够表达时，[policy + 自定义 requirement](https://codewithmukesh.com/blog/policy-based-authorization-in-aspnet-core/) 接上。

这也是这个系列的后两篇文章。

如果你关注 .NET 开发、Web API 工程实践和 AI 辅助编程，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Role-Based Authorization in ASP.NET Core - A .NET 10 Guide](https://codewithmukesh.com/blog/role-based-authorization-in-aspnet-core/)
- [GitHub 示例源码](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/05-api-security/role-based-authorization-in-aspnet-core)
- [JWT Authentication in ASP.NET Core](https://codewithmukesh.com/blog/jwt-authentication-in-aspnet-core/)
- [Claims-Based Authorization in ASP.NET Core](https://codewithmukesh.com/blog/claims-based-authorization-in-aspnet-core/)
- [Policy-Based Authorization in ASP.NET Core](https://codewithmukesh.com/blog/policy-based-authorization-in-aspnet-core/)
- [Microsoft: Role-based authorization in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/security/authorization/roles?view=aspnetcore-10.0)
