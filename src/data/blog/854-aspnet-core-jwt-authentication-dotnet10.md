---
pubDatetime: 2026-06-08T08:07:19+08:00
title: "ASP.NET Core JWT 认证：从登录到角色授权"
description: "JWT 认证适合 SPA、移动端和服务间 API，但它不是只加一个 Bearer 包那么简单。这篇基于 .NET 10 Minimal API，梳理登录签发、JwtBearer 验证、受保护路由、角色授权、测试步骤和生产环境安全边界。"
tags: ["ASP.NET Core", ".NET", "JWT", "Authentication"]
slug: "aspnet-core-jwt-authentication-dotnet10"
ogImage: "../../assets/854/01-cover.png"
source: "https://codewithmukesh.com/blog/jwt-authentication-in-aspnet-core/"
---

JWT authentication 在 ASP.NET Core 里很常见，尤其是前端是 React/Angular、移动端 App，或者 API 需要被多个服务调用时。它的核心思路很直接：用户登录后拿到一个签名 token，后续每次请求都把它放进 `Authorization: Bearer <token>`，API 验证签名和过期时间，再决定是否放行。

Mukesh Murugan 这篇 .NET 10 教程的价值在于把完整路径串起来了：Identity 负责用户和密码，`JsonWebTokenHandler` 负责生成 token，`AddJwtBearer` 负责验证 token，Minimal API endpoint 再用 `.RequireAuthorization()` 和 role policy 做访问控制。下面按可落地的顺序整理一遍。

## 先认清 JWT

JWT 是 JSON Web Token 的缩写。它通常长成三段，用点分开：

```text
header.payload.signature
```

`header` 描述 token 类型和签名算法，`payload` 放 claims，比如用户 ID、邮箱、角色、过期时间，`signature` 则是用服务端密钥对前两段签名后的结果。

这里有个新手很容易忽略的点：**payload 只是 Base64 编码，不是加密**。任何拿到 token 的人都可以读出 payload 内容。签名只能证明内容没有被篡改，不能隐藏内容。所以 JWT 里不要放密码、密钥、身份证号、银行卡号，甚至不该放任何“泄露后会出事”的敏感信息。

## 适用场景

JWT 不是所有 ASP.NET Core 应用的默认答案。原文给了一个很实用的取舍：

- SPA、移动端、跨域前后端分离 API：JWT bearer token 通常合适。
- MVC/Razor Pages 这类同域服务端渲染应用：cookie authentication 更自然。
- 需要快速生成 Identity-backed token endpoint：可以看 `MapIdentityApi`，但控制力会少一些。
- 机器到机器、第三方系统集成：API key 有时更合适，因为它识别的是应用，不是用户。

这篇教程选择 JWT，是因为目标是 Minimal API + 前后端分离风格的 Web API。

## 准备项目

原文使用 .NET 10 Minimal API。JWT 和 Identity 需要这两个包：

```powershell
dotnet add package Microsoft.AspNetCore.Authentication.JwtBearer --version 10.0.0
dotnet add package Microsoft.AspNetCore.Identity.EntityFrameworkCore --version 10.0.0
```

示例为了开箱即跑，使用 EF Core InMemory provider：

```powershell
dotnet add package Microsoft.EntityFrameworkCore.InMemory --version 10.0.0
```

InMemory 适合教程和本地演示。真实项目要换成 SQL Server、PostgreSQL 或你正在使用的数据库，用户表和角色表仍然可以由 ASP.NET Core Identity 管理。

## 用户与 Identity

不要自己写密码哈希。原文用 ASP.NET Core Identity 管用户、密码和角色，并扩展 `IdentityUser` 增加姓名字段：

```csharp
public class ApplicationUser : IdentityUser
{
    public string FirstName { get; set; } = string.Empty;
    public string LastName { get; set; } = string.Empty;
}
```

DbContext 继承 `IdentityDbContext<ApplicationUser>`，这样 Identity 需要的用户、角色、claim、login 等表结构都会被纳入模型。

```csharp
public class AppDbContext(DbContextOptions<AppDbContext> options)
    : IdentityDbContext<ApplicationUser>(options)
{
}
```

在 `Program.cs` 里要注册 DbContext 和 Identity。教程用 InMemory database 是为了免掉迁移和数据库连接。

## JWT 配置

JWT 配置通常放在 `appsettings.json`，包括 issuer、audience、signing key 和过期时间。示例可以写在配置文件里，但生产环境不要提交真实 signing key。

```json
{
  "Jwt": {
    "Issuer": "https://localhost:5001",
    "Audience": "https://localhost:5001",
    "Key": "your-long-random-256-bit-secret-key",
    "ExpirationMinutes": 60
  }
}
```

几个字段要一一对上：

- `Issuer`：谁签发了 token。
- `Audience`：这个 token 是给谁用的。
- `Key`：用于签名和验证的密钥。
- `ExpirationMinutes`：访问 token 的有效期。

签发 token 和验证 token 时使用的 issuer、audience、key 必须完全一致。很多 401 问题，本质就是这几个值有一个字符不匹配。

## 生成 Token

.NET 10 中，原文建议使用 `JsonWebTokenHandler`，而不是更老的 `JwtSecurityTokenHandler`。生成 token 时通常要放入用户标识、邮箱、名称和角色 claims。

一个 token service 的核心逻辑大致是：

```csharp
var claims = new List<Claim>
{
    new("id", user.Id),
    new("email", user.Email!),
    new("name", user.UserName!)
};

foreach (var role in roles)
{
    claims.Add(new Claim("role", role));
}

var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtOptions.Key));
var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

var descriptor = new SecurityTokenDescriptor
{
    Issuer = jwtOptions.Issuer,
    Audience = jwtOptions.Audience,
    Subject = new ClaimsIdentity(claims),
    Expires = DateTime.UtcNow.AddMinutes(jwtOptions.ExpirationMinutes),
    SigningCredentials = credentials
};

var handler = new JsonWebTokenHandler();
return handler.CreateToken(descriptor);
```

这里有两个细节值得保留：

一是 role claim 的名字要和后面验证配置保持一致。原文使用 `"role"`，后面也显式配置 `RoleClaimType = "role"`。

二是 signing key 要足够长。HMAC SHA-256 至少需要 256 bit，太短会触发类似 `IDX10653` 的 key-size 错误，也会让签名安全性变差。

## 接入 JwtBearer

认证中间件要通过 `AddAuthentication().AddJwtBearer(...)` 接入。重点是 `TokenValidationParameters`。

```csharp
builder.Services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = jwtOptions.Issuer,
            ValidAudience = jwtOptions.Audience,
            IssuerSigningKey = new SymmetricSecurityKey(
                Encoding.UTF8.GetBytes(jwtOptions.Key)),
            NameClaimType = "name",
            RoleClaimType = "role",
            ClockSkew = TimeSpan.Zero
        };
    });

builder.Services.AddAuthorization();
```

`ClockSkew` 默认会给过期时间额外加一点宽限。教程里把它设成 `TimeSpan.Zero`，这样 token 到点就过期，测试时也更直观。

管道顺序也不能乱：

```csharp
app.UseAuthentication();
app.UseAuthorization();
```

认证必须在授权之前。先识别“你是谁”，才能判断“你能不能访问”。

## 注册与登录

注册接口负责创建用户。它接收邮箱、密码、姓名等字段，调用 `UserManager<ApplicationUser>.CreateAsync(...)`，由 Identity 完成密码哈希和用户持久化。

登录接口负责验证密码。如果邮箱和密码通过验证，就读取用户角色，调用 token service 生成 JWT，然后把 token 返回给客户端。

客户端拿到 token 后，后续请求要带上：

```http
Authorization: Bearer <token>
```

这一步是 JWT bearer flow 的核心。服务端不需要保存 access token；它只需要用 signing key 验证 token 是否由可信服务签发、是否过期、issuer/audience 是否正确。

## 保护路由

Minimal API 里保护 endpoint 可以直接链 `.RequireAuthorization()`：

```csharp
app.MapGet("/profile", (ClaimsPrincipal user) =>
{
    return Results.Ok(new
    {
        Name = user.Identity?.Name,
        Email = user.FindFirstValue("email")
    });
})
.RequireAuthorization();
```

没有 token 或 token 无效时，返回 401。token 有效但权限不够时，返回 403。

角色授权可以继续加 policy：

```csharp
app.MapGet("/admin", () => Results.Ok("Admin only"))
    .RequireAuthorization(policy => policy.RequireRole("Admin"));
```

如果你发现 `[Authorize(Roles = "Admin")]` 或 `RequireRole("Admin")` 总是 403，要优先检查 `RoleClaimType` 是否和 token 里的角色 claim 名称一致。原文把二者都设为 `"role"`，避免 .NET 默认 claim 映射带来的混乱。

## 怎么测试

最小验证路径可以这样走：

1. 调用注册接口，创建一个用户。
2. 调用登录接口，拿到 JWT。
3. 不带 token 访问受保护 endpoint，应返回 401。
4. 带 `Authorization: Bearer <token>` 再访问，应返回 200。
5. 访问要求 Admin 角色的 endpoint，普通用户应返回 403。
6. 给用户添加 Admin 角色，重新登录拿新 token，再访问 Admin endpoint，应返回 200。

这里要注意“重新登录”。角色写进 JWT 后，已经签发出去的旧 token 不会自动变化。你给用户加了角色，客户端要拿到新的 token，role claim 才会出现在请求里。

## 安全边界

原文的安全建议很实际，可以直接当检查清单：

- 不要提交 signing key。开发时用 user secrets，线上用环境变量或云密钥服务。
- 使用足够长、随机的 key。HS256 至少 256 bit。
- access token 要短期有效，常见范围是 15 到 60 分钟。
- 全站使用 HTTPS，不要让 bearer token 在明文 HTTP 上传输。
- payload 不放秘密，因为 JWT 默认不是加密格式。
- 分布式系统里可以考虑 RS256：签发服务用私钥签名，其他服务用公钥验证。

JWT 最大的现实限制是：access token 一旦签发，在过期前通常不能直接撤回。要兼顾安全和体验，需要 refresh token。原文把 refresh token 放到单独文章里讲，这个边界是合理的；不要把 access token 生命周期拉得很长来“省事”。

## 常见故障

`401`：先检查请求有没有带 `Authorization: Bearer <token>`，再检查 issuer、audience、key 是否和签发时一致，最后确认 `UseAuthentication()` 在 `UseAuthorization()` 前面。

`403`：认证通过了，但角色或策略没过。检查 token 里有没有角色 claim，`RoleClaimType` 是否配置成同一个 claim 名。

`IDX10653` 或 key-size 错误：signing key 太短。换成足够长的随机密钥。

token 过期时间不符合预期：检查 `ClockSkew`。默认宽限会让 token 看起来比配置的过期时间更“耐用”。

`user.Identity.Name` 是空：设置 `NameClaimType`，并确认 token 中确实有对应 claim。

## 收个尾

JWT 认证的代码不只是“生成一个字符串”。一套完整实现至少要把这些事对齐：Identity 管用户和密码，token service 生成带 claims 的签名 token，`JwtBearer` 用同一组 issuer/audience/key 验证，认证中间件排在授权中间件之前，路由用 `.RequireAuthorization()` 和 role policy 表达访问规则。

真正上线时，还要把 signing key 移出配置文件，缩短 access token 生命周期，补上 refresh token，并明确哪些 claim 可以放进 payload。把这些边界想清楚，JWT 才是可靠的 API 认证方案，而不是一串看起来能用的 bearer token。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [JWT Authentication in ASP.NET Core - A Complete .NET 10 Guide](https://codewithmukesh.com/blog/jwt-authentication-in-aspnet-core/)
- [Configure JWT bearer authentication in ASP.NET Core - Microsoft Learn](https://learn.microsoft.com/en-us/aspnet/core/security/authentication/configure-jwt-bearer-authentication)
