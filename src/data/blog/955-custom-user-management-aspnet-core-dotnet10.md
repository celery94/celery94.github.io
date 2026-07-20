---
pubDatetime: 2026-07-21T08:37:06+08:00
title: "ASP.NET Core 自定义用户管理：从注册到管理员面板"
description: "MapIdentityApi 能快速搭好注册登录，但一碰到自定义字段、用户列表、角色管理和管理员端点就到头了。本文用一套 .NET 10 Minimal API，完整覆盖自定义用户模型、管理员 CRUD、角色分配、锁定/禁用、自助资料页和密码重置流程。"
tags: ["ASP.NET Core", "Identity", "用户管理", "Minimal API", ".NET 10"]
slug: "custom-user-management-aspnet-core-dotnet10"
ogImage: "../../assets/955/01-cover.png"
source: "https://codewithmukesh.com/blog/custom-user-management-in-aspnet-core/"
---

`MapIdentityApi()` 一条调用就能拿到注册、登录、token 刷新，看起来很诱人。但一旦需要注册时多填个 `FirstName`、需要管理员列出所有用户、需要给用户分配角色——这个快捷方式就到头了。

**ASP.NET Core 自定义用户管理**，就是在 Identity 之上自己写端点。你保留 Identity 的用户存储、密码哈希、角色和锁定机制，但完全控制 HTTP 层面的行为和返回数据。这比听起来要写的代码少得多。

## MapIdentityApi 停在哪

`MapIdentityApi` 暴露了十个固定端点。你加不了自定义字段到 `/register` 请求体，改不了路由名，也没有列表用户或管理员管理用户的端点。这些限制在 `dotnet/aspnetcore` 仓库的 [#50303](https://github.com/dotnet/aspnetcore/issues/50303) 和 [#47288](https://github.com/dotnet/aspnetcore/issues/47288) 里有明确记录。

所以真实应用需要自定义注册字段、管理界面或角色管理的时刻，你就停止调用 `MapIdentityApi`，自己写端点。本文构建的端点如下：

| 分组 | 端点 | 用途 |
|---|---|---|
| Auth | `POST /auth/register` | 注册（带自定义字段） |
| Auth | `POST /auth/login` | 登录，返回 JWT |
| Auth | `POST /auth/forgot-password` `.../reset-password` | 密码重置 |
| Auth | `POST /auth/confirm-email` | 邮箱确认 |
| Admin | `GET /api/admin/users` | 用户列表（分页、搜索、含角色） |
| Admin | `GET /api/admin/users/{id}` | 单个用户 |
| Admin | `PUT` / `DELETE /api/admin/users/{id}` | 更新或删除 |
| Admin | `POST` / `DELETE /api/admin/users/{id}/roles` | 分配或移除角色 |
| Admin | `POST .../lock` `.../unlock` | 锁定/解锁（安全锁定） |
| Admin | `POST .../disable` `.../enable` | 禁用/启用（管理员开关） |
| Self | `GET` / `PUT /api/me` | 读或更新自己的资料 |
| Self | `POST /api/me/change-password` | 修改自己的密码 |

## 项目配置

从 .NET 10 Web API 开始。关键选择是用 `AddIdentity` 而非 `AddIdentityApiEndpoints`——前者保留完整 Identity 引擎但把端点留给你。

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseInMemoryDatabase("CustomUserManagementDb"));

builder.Services
    .AddIdentity<ApplicationUser, IdentityRole>(options =>
    {
        options.User.RequireUniqueEmail = true;
        options.Password.RequiredLength = 6;
        options.Lockout.MaxFailedAccessAttempts = 5;
        options.Lockout.DefaultLockoutTimeSpan = TimeSpan.FromMinutes(5);
    })
    .AddEntityFrameworkStores<AppDbContext>()
    .AddDefaultTokenProviders();
```

`AddDefaultTokenProviders()` 是邮箱确认和密码重置令牌生效的前提，别跳过。

## 扩展 IdentityUser 加自定义字段

这是 `MapIdentityApi` 做不到的第一件事。`IdentityUser` 自带 `Id`、`Email`、`UserName`、`PasswordHash` 和锁定相关列。加自己的字段只需要继承它：

```csharp
public class ApplicationUser : IdentityUser
{
    public string FirstName { get; set; } = string.Empty;
    public string LastName { get; set; } = string.Empty;
    public string? ProfilePictureUrl { get; set; }
    public bool IsActive { get; set; } = true;
    public DateTimeOffset CreatedOn { get; set; } = DateTimeOffset.UtcNow;
}
```

DbContext 指向你的自定义用户类型，新列自动落到 `AspNetUsers` 表：

```csharp
public class AppDbContext(DbContextOptions<AppDbContext> options)
    : IdentityDbContext<ApplicationUser>(options);
```

成本就是一个类加一个泛型参数。

## 种子角色和超级管理员

管理员端点被调之前至少要有一个管理员存在。启动时种子角色和管理员账号：

```csharp
foreach (var role in new[] { "Admin", "User" })
{
    if (!await roleManager.RoleExistsAsync(role))
        await roleManager.CreateAsync(new IdentityRole(role));
}

if (await userManager.FindByEmailAsync("admin@example.com") is null)
{
    var admin = new ApplicationUser
    {
        UserName = "admin@example.com",
        Email = "admin@example.com",
        FirstName = "Super",
        LastName = "Admin",
        EmailConfirmed = true
    };
    await userManager.CreateAsync(admin, "Admin123!");
    await userManager.AddToRoleAsync(admin, "Admin");
}
```

`UserManager<ApplicationUser>` 和 `RoleManager<IdentityRole>` 是后面所有端点背后的引擎。

## 自定义注册端点

`MapIdentityApi` 不允许加的注册端点现在你自己写：接受额外字段、创建用户、加入默认 `User` 角色、触发邮箱确认：

```csharp
group.MapPost("/register", async (
    RegisterRequest request,
    UserManager<ApplicationUser> userManager,
    IEmailSender emailSender) =>
{
    var user = new ApplicationUser
    {
        UserName = request.Email,
        Email = request.Email,
        FirstName = request.FirstName,
        LastName = request.LastName
    };

    var result = await userManager.CreateAsync(user, request.Password);
    if (!result.Succeeded)
        return Results.ValidationProblem(result.ToProblemDictionary());

    await userManager.AddToRoleAsync(user, "User");

    var token = await userManager
        .GenerateEmailConfirmationTokenAsync(user);
    await emailSender.SendAsync(user.Email, "Confirm your email",
        $"Confirm with this token: {token}");

    var roles = await userManager.GetRolesAsync(user);
    return Results.Created(
        $"/api/admin/users/{user.Id}", user.ToResponse(roles));
});
```

关键习惯：**永远不直接返回 `ApplicationUser`**。它携带着 `PasswordHash`、安全戳和锁定内部状态。映射到你控制的响应 DTO：

```csharp
public record UserResponse(
    string Id, string Email, string FirstName, string LastName,
    string? ProfilePictureUrl, bool IsActive, bool IsLockedOut,
    DateTimeOffset CreatedOn, IEnumerable<string> Roles);
```

## 管理员端点

管理端点整组受角色保护：

```csharp
var group = app.MapGroup("/api/admin/users")
    .RequireAuthorization(policy => policy.RequireRole("Admin"));
```

### 用户列表：分页、搜索、含角色

`UserManager.Users` 是 `IQueryable`，所以可以搜、数、分页，再给每个用户附加角色：

```csharp
group.MapGet("/", async (
    UserManager<ApplicationUser> userManager,
    int page = 1, int pageSize = 10, string? search = null) =>
{
    pageSize = pageSize is < 1 or > 100 ? 10 : pageSize;

    var query = userManager.Users.AsNoTracking();
    if (!string.IsNullOrWhiteSpace(search))
    {
        var term = search.Trim();
        query = query.Where(u =>
            u.Email!.Contains(term) ||
            u.FirstName.Contains(term) ||
            u.LastName.Contains(term));
    }

    var totalCount = await query.CountAsync();
    var users = await query
        .OrderBy(u => u.Email)
        .Skip((page - 1) * pageSize)
        .Take(pageSize)
        .ToListAsync();

    var items = new List<UserResponse>();
    foreach (var user in users)
    {
        var roles = await userManager.GetRolesAsync(user);
        items.Add(user.ToResponse(roles));
    }

    return Results.Ok(new PagedResult<UserResponse>(
        items, page, pageSize, totalCount));
});
```

默认分页大小 10，上限 100——防止客户端一次拉整张用户表。

### 角色管理

两个小端点。先确认角色存在，再让 `UserManager` 做：

```csharp
group.MapPost("/{id}/roles", async (
    string id, AssignRoleRequest request,
    UserManager<ApplicationUser> userManager,
    RoleManager<IdentityRole> roleManager) =>
{
    var user = await userManager.FindByIdAsync(id);
    if (user is null) return Results.NotFound();
    if (!await roleManager.RoleExistsAsync(request.Role))
        return Results.BadRequest(
            $"Role '{request.Role}' does not exist.");
    await userManager.AddToRoleAsync(user, request.Role);
    return Results.NoContent();
});
```

### 锁定 vs 禁用：两种不同的阻断方式

这两个概念混的人很多：

| | 锁定（Lockout） | 禁用（IsActive） |
|---|---|---|
| 是什么 | Identity 内置安全机制 | 你自己加的自定义标志 |
| 触发方式 | 登录失败过多，或管理员主动锁定 | 管理员决定 |
| 持续时间 | 临时（自动过期） | 永久，直到管理员重新开启 |
| 用途 | 防暴力破解 | 停用账号、离职处理 |

**锁定**用 `SetLockoutEndDateAsync`：

```csharp
await userManager.SetLockoutEnabledAsync(user, true);
await userManager.SetLockoutEndDateAsync(
    user, DateTimeOffset.UtcNow.AddYears(100));
```

**禁用**是 `IsActive` 字段，Identity 不认识它，你必须在登录端点自己强制执行：

```csharp
var user = await userManager.FindByEmailAsync(request.Email);
if (user is null || !user.IsActive)
    return Results.Unauthorized();
```

## 自助资料端点

登录用户管理自己的账号。核心规则：用户 ID 从 JWT 中读取，不从请求体获取，确保用户只能改自己的记录：

```csharp
var group = app.MapGroup("/api/me")
    .RequireAuthorization();

group.MapGet("/", async (
    ClaimsPrincipal principal,
    UserManager<ApplicationUser> userManager) =>
{
    var user = await GetCurrentUserAsync(principal, userManager);
    if (user is null) return Results.Unauthorized();
    var roles = await userManager.GetRolesAsync(user);
    return Results.Ok(user.ToResponse(roles));
});
```

改密码一行搞定——`ChangePasswordAsync` 自动验证当前密码：

```csharp
var result = await userManager.ChangePasswordAsync(
    user, request.CurrentPassword, request.NewPassword);
return result.Succeeded
    ? Results.NoContent()
    : Results.ValidationProblem(result.ToProblemDictionary());
```

## 邮箱确认和密码重置

Identity 生成安全令牌；你来决定怎么投递。投递是一个缝——生产环境用 SendGrid、Amazon SES 或 SMTP 实现 `IEmailSender` 接口。

密码重置是两个端点。`forgot-password` 始终返回 `204`，即使邮箱不存在——防止被人用来探测注册邮箱：

```csharp
var user = await userManager.FindByEmailAsync(request.Email);
if (user is not null)
{
    var token = await userManager
        .GeneratePasswordResetTokenAsync(user);
    await emailSender.SendAsync(user.Email!,
        "Reset your password",
        $"Reset with this token: {token}");
}
return Results.NoContent();
```

## 什么时候自己写 vs 用外部服务

| 维度 | MapIdentityApi | 自定义用户管理 | 外部服务 (Entra/Auth0) |
|---|---|---|---|
| 搭建成本 | 最低（一行） | 中等（自己写端点） | 中高（搭/配一个服务） |
| 自定义字段 | 不行 | 可以 | 可以 |
| 管理员用户管理 | 不行 | 可以，完全自定义 | 可以，在对方后台 |
| 角色管理 API | 不行 | 可以 | 可以 |
| 社交/SSO 登录 | 不支持 | 不支持 | 内置 |
| 用户数据归属 | 你 | 你 | 服务方 |

判断标准：你拥有用户且需要真正控制他们——自定义字段、管理员面板、角色管理——但不需要 SSO 或社交登录时，自己写。这覆盖了大多数业务 API 和 SaaS 后端。

一旦需求中出现社交登录、跨应用 SSO 或企业身份（SAML、SCIM），就用外部服务。手写联邦身份是时间黑洞。

## 常见坑

- **`RequireRole("Admin")` 对管理员也返 403**：令牌里的角色 claim 类型必须匹配。如果用的是 `role`，JWT 选项里设 `RoleClaimType = "role"`。
- **新注册用户查不到角色**：角色在 `CreateAsync` 之后分配。种子时确保角色在 `AddToRoleAsync` 之前已创建。
- **密码重置令牌始终无效**：你忘了 `AddDefaultTokenProviders()`。
- **锁定用户没效果**：`SetLockoutEndDateAsync` 只在锁启用后才生效——先调 `SetLockoutEnabledAsync(user, true)`。
- **401 vs 403**：无令牌或无效令牌返 `401`（未认证）。有令牌但无 `Admin` 角色返 `403`（已认证但无权限）。
- **已禁用用户仍能登录**：`IsActive` 是你自己的标志，Identity 不认识。你必须在登录端点自己检查。

## 结语

ASP.NET Core 自定义用户管理不是一个要安装的框架——是你在 Identity 之上搭建的一层薄但整齐的代码。保留 Identity 的用户存储、密码哈希、角色和锁定，扩展 `IdentityUser` 加自己的字段，通过你控制的端点暴露 `UserManager` 和 `RoleManager`。

整个东西放在一个 Minimal API 项目里。克隆、F5、顺着 `requests.http` 文件跑一遍就看到所有端点的运行效果。当你拥有用户且需要真正控制他们时才自己写——需要 SSO 或社交登录时才用外部服务。

## 参考

- [原文：Custom User Management in ASP.NET Core Web API (.NET 10)](https://codewithmukesh.com/blog/custom-user-management-in-aspnet-core/)
