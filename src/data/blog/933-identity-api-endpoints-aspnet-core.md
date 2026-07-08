---
pubDatetime: 2026-07-08T12:27:22+08:00
title: "ASP.NET Core Identity API 端点：什么时候该用，什么时候该跑"
description: "MapIdentityApi 一行代码就能给你 /register、/login、/refresh 等 10 个认证端点，但它发的 token 不是 JWT。本文讲清这个取舍：什么时候用它省掉几天开发，什么时候必须自己接管。"
tags:
  [
    "ASP.NET Core",
    "Identity",
    "JWT",
    "authentication",
    ".NET",
    "Minimal API",
  ]
slug: "identity-api-endpoints-aspnet-core"
source: "https://codewithmukesh.com/blog/identity-endpoints-aspnet-core/"
ogImage: "../../assets/933/01-cover.png"
---

给 API 加注册和登录，这事太熟悉了。建 `User` 模型、配 Identity、写 `LoginController`、发 JWT、加 refresh token——半天起步，光是重复代码就能写到手酸。.NET 8 开始有了一个省事的选项：`MapIdentityApi()`，一行调用就挂上 10 个端点。省掉的时间是真的，但隐藏的代价也是真的。问题是：这两个真相怎么权衡。

## 什么是 Identity API 端点

Identity API 端点是一组预建的 Minimal API 端点——`/register`、`/login`、`/refresh` 等等——由 ASP.NET Core 通过一次 `MapIdentityApi<TUser>()` 调用挂载，底层直接复用 ASP.NET Core Identity 的 `UserManager`、`SignInManager` 和密码散列。从 .NET 8 引入，.NET 10 仍然在用。

在 .NET 8 之前，把 Identity 接到 API 上要么得拖上 Razor Pages（那是给 MPA 准备的全套 UI，和 JSON API 格格不入），要么全手写。`MapIdentityApi` 把这个缺口补上了：它是 JSON API 版的旧 Identity UI，底下那套用户存储和密码散列跟原来一模一样，上面换成了 HTTP 端点前端可以直接调用。

## 三行配置

这是完整的最小搭建：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseInMemoryDatabase("IdentityDemo"));

builder.Services.AddAuthorization();

builder.Services.AddIdentityApiEndpoints<IdentityUser>()
    .AddEntityFrameworkStores<AppDbContext>();

var app = builder.Build();

app.MapIdentityApi<IdentityUser>();
app.Run();
```

`AppDbContext` 就是标准的 `IdentityDbContext`：

```csharp
public class AppDbContext(DbContextOptions<AppDbContext> options)
    : IdentityDbContext<IdentityUser>(options);
```

注意用的是 `AddIdentityApiEndpoints`，不是更老的 `AddIdentity`。前者启用了 API 专用的 bearer token 支持。`MapIdentityApi` 默认把端点挂到根路径（`/register`、`/login` 等）。要加命名空间的话，套一层路由组就行：

```csharp
app.MapGroup("/account").MapIdentityApi<IdentityUser>();
```

## MapIdentityApi 到底挂载了哪些端点

一共 10 个：

| 方法 | 路由 | 用途 |
|------|------|------|
| POST | `/register` | 用邮箱和密码创建新用户 |
| POST | `/login` | 登录，返回 cookie 或 bearer token |
| POST | `/refresh` | 用 refresh token 换新的 access token |
| GET | `/confirmEmail` | 通过邮件发送的链接确认邮箱 |
| POST | `/resendConfirmationEmail` | 重发确认邮件 |
| POST | `/forgotPassword` | 发起密码重置（发送重置码） |
| POST | `/resetPassword` | 用重置码完成密码重置 |
| POST | `/manage/2fa` | 启用、禁用或重置双因素认证 |
| GET | `/manage/info` | 读取当前用户的邮箱和 claims |
| POST | `/manage/info` | 更新当前用户的邮箱或密码 |

这覆盖了第一方账户的完整生命周期：注册、确认、登录、保持登录、忘记密码、开 2FA。对很多应用来说确实够了。

有一个端点是缺席的：`/logout`。`MapIdentityApi` 没有映射这个。cookie 客户端需要自己用 `SignInManager.SignOutAsync()` 补一个；token 客户端直接在客户端把 token 扔掉就行。这个不对称是提前预告：这套端点覆盖了常见路径，剩下的你得自己来，而且没有留什么扩展缝。

## Cookie 还是 Token？那条没人看的默认规则

调用 `AddIdentityApiEndpoints` 时，cookie 和 token 认证会同时启用。`/login` 返回哪个，取决于一个查询参数：

```
POST /login?useCookies=true    → 返回 Set-Cookie 头，浏览器自动携带
POST /login                    → 在响应体里返回 token
```

微软官方建议：**浏览器应用优先用 cookie，不用 token**。原文是这么写的：“We recommend using cookies for browser-based applications, because, by default, the browser automatically handles them without exposing them to JavaScript。”也就是说，把 bearer token 存 `localStorage` 来认证浏览器应用——这正是 cookie 默认方案要让你绕开的事。

Token 模式返回的结构长这样：

```json
{
  "tokenType": "Bearer",
  "accessToken": "CfDJ8N...很长的加密字符串...",
  "expiresIn": 3600,
  "refreshToken": "CfDJ8N...另一个加密字符串..."
}
```

默认 access token 有效期 1 小时，refresh token 14 天。两者都可以通过 `BearerTokenOptions` 的 `BearerTokenExpiration` 和 `RefreshTokenExpiration` 调整。后续请求带着 access token 正常走 bearer 头，过期后调 `/refresh`：

```
Authorization: Bearer CfDJ8N...
```

表面上看，跟 JWT 流程一模一样。但那个 `accessToken` 不是 JWT。

## 关键坑点：那个 Token 不是 JWT

把 token 模式拿到的 `accessToken` 贴进 jwt.io，解不出来。没有 header、没有 payload、没有可读的 claims——它就是一段加密的 opaque blob。

这是故意的，也是关于 Identity API 端点最重要的一件事。微软文档明确写了："The tokens aren't standard JSON Web Tokens (JWTs). The use of custom tokens is intentional, as the built-in Identity API is meant primarily for simple scenarios."这个 token 是一段用 Data Protection 加密的字符串，只有签发它的应用自己能读。微软也说了它 "isn't intended to be a full-featured identity service provider or token server"。

这个设计选择带来的后果，决定了这套端点能不能放进你的架构：

- **除了签发它的应用，没有任何东西能读这个 token。** JWT 拿着签名密钥，任何服务都能验。这个 token 什么信息都不携带。API 网关、第二个微服务、下游 API——都看不懂它，除非回调签发应用。
- **你没法往里面塞自定义 claims。** 没有 `tenant_id`，没有其他服务能读的 `role`，没有 `subscription_tier`。Token 只是指向服务端 session 的钥匙，不是信息的载体。
- **它只在一个应用内部有效。** 一旦你的系统超过“一个 API + 它自己的前端”的规模，opaque token 就不够了。

对一个自包含的“SPA + 它的 API”，这些不重要——同一个应用签发和验证 token，opaque blob 完全够用。对需要跨服务共享身份的场景，这就是一堵墙。区别就在这。

## 什么时候可以用

`MapIdentityApi` 适合下面这些条件全部成立的时候：

- **第一方认证。** 用户直接用邮箱密码在你的应用注册和登录。没有联合 Google、微软或者企业 IdP。
- **同一个应用签发和消费 token。** SPA、Blazor WebAssembly 或移动应用，对着它自己的 API。没有第二个服务需要独立验证 token。
- **默认用户结构够用。** 邮箱、密码、Identity 标准字段。不在注册时收集自定义字段，也不往 token 塞自定义 claims。
- **你今天就想上线。** 原型、内部工具、MVP、副项目、课程 demo。这些端点把一整天的认证开发压缩成三行。

这不是小范围。大量真实项目就是“一个 SPA 加上它背后的 API，邮箱密码登录”。对这种项目，`MapIdentityApi` 是正确的选择，自己写属于多余。注册、邮箱确认、密码重置、refresh token、2FA——全都有框架团队帮你测好维护好。

## 什么时候不能碰

但凡下面任何一条在你的路线图上，直接走人：

- **你需要真正的 JWT。** 只要另一个服务、网关、API 需要不带回调就能验证这个 token，你就需要一个带可读 claims 的签名 JWT。opaque token 干不了。这是团队最常见拆掉端点重来的原因。
- **你需要社交登录或 OIDC。** "Sign in with Google" 或任何 OpenID Connect 供应商不在这套端点的范围里。只支持第一方。后面再拼 OIDC 上去就得换一个完全不同的体系。
- **你需要自定义注册字段。** `/register` 的请求体是固定的 `{ email, password }`。想在注册时收集 `FirstName`、`CompanyName`、`TenantId`？端点体改不了。只能拦截然后事后 patch，这很脆。
- **你需要禁用或重命名端点。** `/register` 永远公开，没有内置开关可以移除它。所以一个只允许邀请的应用没法简单关掉注册。也没法重命名路由——这就是 `/manage/info` 这种别扭路径的源头。（`dotnet/aspnetcore` 仓库上分别有 issue #50303 和 #57899 在讨论端点过滤和自定义的问题。）
- **你需要精细控制认证流程。** 自定义锁定策略、每次登录的审计日志、按客户不同的 token 生命周期——端点是个黑盒。你能配置的都只是 Identity 暴露出来的 options，仅此而已。

规律就是了：每个“不能碰”的原因，都是因为端点没有给你留那条缝。它们是有意封闭的。这让它们快，也让它们在需求增长时变成死胡同。

## 决策对比

.NET API 认证的三条现实路径：

| 维度 | Identity API 端点 | 自己写 JWT | OIDC Provider |
|------|-------------------|-----------|---------------|
| 搭建成本 | 最低（3 行） | 中等 | 中高 |
| Token 类型 | Opaque，仅本应用 | 签名 JWT，带你的 claims | 签名 JWT / OIDC |
| 自定义 claims | 不支持 | 支持 | 支持 |
| 社交/外部登录 | 不支持 | 能写但麻烦 | 内置 |
| 跨微服务可用 | 否 | 是 | 是 |
| 自定义注册字段 | 不支持 | 支持 | 支持（需配置） |
| 禁用/自定义端点 | 不支持 | 完全控制 | 完全控制 |
| 维护负担 | 框架负责 | 你负责 | 供应商负责 |

Identity 端点和完整 OIDC Provider 分别站在两端。**自己写 JWT 是务实的中位**，覆盖“我需要真正的 claims token，但不想跑 Keycloak”这个非常常见的场景。

## 脱身方案：留着 Identity，扔掉 MapIdentityApi

ASP.NET Core Identity 和 `MapIdentityApi` 不是一回事。`MapIdentityApi` 只是暴露 Identity 的**一种**方式，而且是封闭的方式。你可以保留 Identity 所有有价值的东西——用户存储、密码散列、锁定策略、`SignInManager`、2FA——然后不调 `MapIdentityApi`，自己写一个返回真正的 JWT 的登录端点。

注册 Identity 时用 `AddIdentity`，不用 `AddIdentityApiEndpoints`：

```csharp
builder.Services.AddIdentity<IdentityUser, IdentityRole>()
    .AddEntityFrameworkStores<AppDbContext>();
```

然后写一个自定义 `/auth/login`，靠 `SignInManager` 做密码校验，靠自己的 `TokenService` 签发 JWT：

```csharp
app.MapPost("/auth/login", async (
    LoginRequest request,
    UserManager<IdentityUser> userManager,
    SignInManager<IdentityUser> signInManager,
    TokenService tokenService) =>
{
    var user = await userManager.FindByEmailAsync(request.Email);
    if (user is null)
        return Results.Unauthorized();

    var result = await signInManager.CheckPasswordSignInAsync(
        user, request.Password, lockoutOnFailure: true);

    if (!result.Succeeded)
        return Results.Unauthorized();

    var roles = await userManager.GetRolesAsync(user);
    var token = tokenService.CreateToken(user, roles);

    return Results.Ok(new { accessToken = token });
});

public record LoginRequest(string Email, string Password);
```

`TokenService` 的写法可以照着前一篇 [JWT 认证指南](https://codewithmukesh.com/blog/jwt-authentication-in-aspnet-core/)来，再配上 refresh token 实现上篇里 `MapIdentityApi` 自带的那种“保持登录”体验。代价就多了一点点代码，但得到了完全没有墙的 token。

## 测试端点

`MapIdentityApi` 的快乐路径就是两个请求。注册：

```json
POST /register
{
  "email": "dev@example.com",
  "password": "Passw0rd!"
}
```

成功返回 `200 OK`，响应体为空。密码必须满足 Identity 的默认规则——至少六位，含大写、小写、数字、非字母字符——不满足会拿到一个 RFC 9457 Problem Details 格式的 `400`，逐条告诉你哪条规则没过。

然后登录拿 token：

```json
POST /login
{
  "email": "dev@example.com",
  "password": "Passw0rd!"
}
```

返回 `accessToken` / `refreshToken` 对。带 access token 调用受保护端点，`expiresIn` 到期后把 refresh token POST 到 `/refresh` 换一对新的。

## 原则：跟着产品方向选，别跟着今天选

如果用一句话总结：应用小到可以诚实保证未来不会有跨服务 token 或社交登录，那就用 Identity API 端点。SPA、Blazor 应用、移动端 MVP——直接上，三行是正确答案，多加一行都是多余的。

但如果你已经隐隐觉得“将来大概率要接 Google 登录”，或者“移动端 API 和 Web API 都要验证这个 token”，不要从 `MapIdentityApi` 开始再计划迁移。没有干净的迁移路径。opaque token 已经织进端点的工作方式里，换成 JWT 等于重写整个认证面。从第一天就上自定义 JWT 只费你一个下午，等上线以后从 Identity 端点迁走，费你一个迭代加一次安全评审。

所以做判断的时候要想清楚：你的产品是往一个自包含的 SPA 方向走，还是往多个服务的分布式方向走。路径不一样，起点就不一样。

## 参考

- [Identity API Endpoints in ASP.NET Core: When to Use Them (.NET 10)](https://codewithmukesh.com/blog/identity-endpoints-aspnet-core/)
- [Microsoft Learn - Identity API Authorization](https://learn.microsoft.com/en-us/aspnet/core/security/authentication/identity-api-authorization?view=aspnetcore-10.0)
- [MapIdentityApi<TUser> documentation](https://learn.microsoft.com/en-us/dotnet/api/microsoft.aspnetcore.routing.identityapiendpointroutebuilderextensions.mapidentityapi)
- [AddIdentityApiEndpoints documentation](https://learn.microsoft.com/en-us/dotnet/api/microsoft.extensions.dependencyinjection.identityservicecollectionextensions.addidentityapiendpoints)
- [Source code on GitHub](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/05-api-security/identity-endpoints-aspnet-core)
