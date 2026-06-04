---
pubDatetime: 2026-06-04T07:57:01+08:00
title: "ASP.NET Core Web API 认证与授权：JWT 和策略怎么配"
description: "这篇文章用 ASP.NET Core Web API 的真实配置串起认证与授权：JWT Bearer 如何验证请求、Token 怎么签发、Authorize 和策略怎样保护端点，以及资源级权限该放在哪里判断。"
tags: ["ASP.NET Core", "Authentication", "Authorization", "JWT", ".NET"]
slug: "authentication-authorization-aspnet-core-web-api-jwt-policies"
ogImage: "../../assets/848/01-cover.png"
source: "https://www.devleader.ca/2026/06/03/authentication-and-authorization-in-aspnet-core-web-api-jwt-and-policies"
---

Web API 的安全配置很容易被写成一堆属性和中间件调用。真正上手时，开发者更容易卡在几个具体问题：Token 到底验证哪些字段，`UseAuthentication()` 和 `UseAuthorization()` 谁在前，角色检查什么时候够用，资源归属又该在哪里判断。

原文把 ASP.NET Core Web API 的认证与授权放在一条完整链路里讲，示例目标是 .NET 10。这里保留它的主线，并补上更适合照着检查的说明。读完后，你应该能把 JWT Bearer 认证、`[Authorize]`、策略授权和资源级授权放到各自正确的位置。

## 先分清职责

认证负责确认“调用者是谁”。在 ASP.NET Core 里，请求进来后，认证中间件会调用默认认证方案的处理器。JWT Bearer 场景下，处理器通常读取 `Authorization: Bearer ...` 请求头，验证 Token，通过后生成 `ClaimsPrincipal`，并写入 `HttpContext.User`。

授权负责判断“这个调用者能不能做这件事”。它会读取前面生成的 `ClaimsPrincipal`，再结合端点上的 `[Authorize]`、角色、声明或自定义策略，决定放行、返回 401，还是返回 403。

这两个步骤分开配置，也分开失败。Token 无效通常是认证失败。Token 有效但角色、声明或资源权限不满足，通常是授权失败。

## 配好 JWT 验证

JWT Bearer 配置要解决两个问题：注册认证方案，以及告诉框架如何验证传入的 Token。原文强调，至少要验证签发方、受众、有效期和签名密钥。Microsoft Learn 的 JWT Bearer 文档也把签名、issuer、audience、expiration 列为 API 需要验证的核心项。

下面是一个典型的 `Program.cs` 配置：

```csharp
using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

var jwtSection = builder.Configuration.GetSection("Jwt");
var secretKey = jwtSection["SecretKey"]
    ?? throw new InvalidOperationException("JWT SecretKey is not configured.");

builder.Services.AddAuthentication(options =>
{
    options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
    options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
})
.AddJwtBearer(options =>
{
    options.TokenValidationParameters = new TokenValidationParameters
    {
        ValidateIssuer = true,
        ValidIssuer = jwtSection["Issuer"],

        ValidateAudience = true,
        ValidAudience = jwtSection["Audience"],

        ValidateLifetime = true,
        ClockSkew = TimeSpan.FromSeconds(30),

        ValidateIssuerSigningKey = true,
        IssuerSigningKey = new SymmetricSecurityKey(
            Encoding.UTF8.GetBytes(secretKey))
    };
});

builder.Services.AddAuthorization();

var app = builder.Build();

app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();
app.Run();
```

这里有三个检查点：

- `ValidateIssuer`：确认 Token 是预期签发方发的。
- `ValidateAudience`：确认 Token 是发给当前 API 的。
- `ValidateIssuerSigningKey`：确认 Token 没被篡改，签名密钥可信。

`ClockSkew` 是容易被忽略的配置。JWT 里有过期时间，但多台机器的时钟可能有轻微偏差。默认偏移是 5 分钟。原文示例改成 30 秒，适合想减少宽限时间的 API。测试时如果设成 `TimeSpan.Zero`，分布式环境里可能会遇到刚签发的 Token 偶发验证失败。

`UseAuthentication()` 要放在 `UseAuthorization()` 前面。认证先把 `HttpContext.User` 填好，授权才能基于身份做判断。顺序反过来时，授权看到的可能还是匿名用户。

## 签发 Token

认证中间件只负责验证 Token。Token 通常由登录接口签发。原文用 `JwtSecurityTokenHandler` 创建一个自签发 JWT，适合一些自管身份的系统。生产系统也可能把签发工作交给 Auth0、Microsoft Entra ID、Duende IdentityServer 这类外部身份服务。

自签发 Token 的核心是：用同一组 issuer、audience 和 signing key 签发，再由前面的 `TokenValidationParameters` 验证。

```csharp
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.IdentityModel.Tokens;

[ApiController]
[Route("api/[controller]")]
public sealed class AuthController : ControllerBase
{
    private readonly IUserService _userService;
    private readonly IConfiguration _configuration;

    public AuthController(
        IUserService userService,
        IConfiguration configuration)
    {
        _userService = userService;
        _configuration = configuration;
    }

    [HttpPost("login")]
    [AllowAnonymous]
    public async Task<IActionResult> Login(LoginRequest request)
    {
        var user = await _userService.ValidateCredentialsAsync(
            request.Email, request.Password);

        if (user is null)
        {
            return Unauthorized(new { message = "Invalid credentials." });
        }

        var token = GenerateToken(user);
        return Ok(new { token });
    }

    private string GenerateToken(ApplicationUser user)
    {
        var jwtSection = _configuration.GetSection("Jwt");
        var secretKey = jwtSection["SecretKey"]!;
        var signingKey = new SymmetricSecurityKey(
            Encoding.UTF8.GetBytes(secretKey));

        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
            new(JwtRegisteredClaimNames.Email, user.Email),
            new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString()),
            new(ClaimTypes.Name, user.DisplayName)
        };

        foreach (var role in user.Roles)
        {
            claims.Add(new Claim(ClaimTypes.Role, role));
        }

        var descriptor = new SecurityTokenDescriptor
        {
            Subject = new ClaimsIdentity(claims),
            Issuer = jwtSection["Issuer"],
            Audience = jwtSection["Audience"],
            Expires = DateTime.UtcNow.AddHours(1),
            SigningCredentials = new SigningCredentials(
                signingKey, SecurityAlgorithms.HmacSha256)
        };

        var handler = new JwtSecurityTokenHandler();
        var token = handler.CreateToken(descriptor);
        return handler.WriteToken(token);
    }
}
```

几个细节要提前定好：

- 生产环境不要把签名密钥提交进源码仓库。原文建议开发环境可以用 `appsettings.json`，生产环境改用环境变量或 Azure Key Vault。
- HMAC-SHA256 的密钥至少要 256 bit，也就是 32 字节。太短会在启动或验证时出错。
- JWT 只是 Base64 编码，内容可以被客户端读到。不要把敏感数据塞进 claims。
- `sub`、`email`、`role` 这类 claims 只放授权判断确实需要的内容。

## 用 Authorize 保护端点

`[Authorize]` 是最直接的保护方式。放在 Controller 上会保护整个 Controller，放在 Action 上只保护某个接口。

```csharp
[ApiController]
[Route("api/[controller]")]
[Authorize]
public sealed class ProfileController : ControllerBase
{
    [HttpGet("me")]
    public IActionResult GetMe()
    {
        return Ok(new
        {
            Name = User.Identity?.Name,
            Claims = User.Claims.Select(c => new { c.Type, c.Value })
        });
    }
}
```

登录接口、健康检查、公开文档这类入口可以用 `[AllowAnonymous]` 放开。这个属性会覆盖更高层级的 `[Authorize]`。

角色授权适合简单场景：

```csharp
[Authorize(Roles = "Admin")]
[HttpGet("admin-report")]
public IActionResult GetAdminReport()
{
    return Ok();
}
```

多个角色可以用逗号分隔：

```csharp
[Authorize(Roles = "Admin,Manager")]
```

这个判断是“满足其中一个角色即可”。如果访问规则开始变多，直接把角色字符串散落在各个端点上会难维护，这时应该改用策略。

## 把规则收进策略

策略授权把访问规则集中定义，再通过名字应用到端点。Microsoft Learn 对策略授权的解释是：角色和声明底层都可以表达为 requirement、handler 和 policy。通俗地说，策略就是把“怎样才算有权限”写成可复用规则。

原文使用 `AddAuthorizationBuilder()`，这是 .NET 8 之后更顺手的写法：

```csharp
using Microsoft.AspNetCore.Authorization;

builder.Services.AddAuthorizationBuilder()
    .AddPolicy("AdminOnly", policy =>
        policy.RequireRole("Admin"))
    .AddPolicy("SeniorDeveloperOrAbove", policy =>
        policy.RequireRole("Senior", "Lead", "Principal", "Admin"))
    .AddPolicy("VerifiedEmail", policy =>
        policy.RequireClaim("email_verified", "true"))
    .AddPolicy("MinimumAge", policy =>
        policy.Requirements.Add(new MinimumAgeRequirement(18)));

builder.Services.AddScoped<IAuthorizationHandler, MinimumAgeHandler>();

public sealed record MinimumAgeRequirement(int MinimumAge)
    : IAuthorizationRequirement;

public sealed class MinimumAgeHandler
    : AuthorizationHandler<MinimumAgeRequirement>
{
    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        MinimumAgeRequirement requirement)
    {
        var birthDateClaim = context.User.FindFirst("birthdate");
        if (birthDateClaim is null ||
            !DateOnly.TryParse(birthDateClaim.Value, out var birthDate))
        {
            return Task.CompletedTask;
        }

        var age = DateOnly.FromDateTime(DateTime.UtcNow).Year - birthDate.Year;
        if (age >= requirement.MinimumAge)
        {
            context.Succeed(requirement);
        }

        return Task.CompletedTask;
    }
}
```

应用策略时只引用名字：

```csharp
[ApiController]
[Route("api/[controller]")]
[Authorize(Policy = "SeniorDeveloperOrAbove")]
public sealed class AdminReportsController : ControllerBase
{
    [HttpGet]
    public IActionResult GetReports()
    {
        return Ok();
    }
}
```

策略适合这些情况：

- 权限需要多个角色或声明共同参与。
- 规则要在多个端点复用。
- 规则需要数据库、外部服务或业务对象参与判断。
- 你希望能单独测试权限逻辑。

自定义 handler 可以注入 scoped 或 transient 服务，所以复杂规则不用硬塞进 Controller。

## 资源级授权

有些权限不能只靠端点属性判断。比如“只有文档所有者能编辑文档”。这里必须先加载文档，拿到 `OwnerId`，再拿当前用户和文档做比较。

原文把这种模式称为 resource-based authorization。Microsoft Learn 也说明，资源级授权不能只依赖声明式属性，因为属性执行时资源还没被加载。做法是注入 `IAuthorizationService`，在 Action 里显式调用。

```csharp
[ApiController]
[Route("api/[controller]")]
[Authorize]
public sealed class DocumentsController : ControllerBase
{
    private readonly IDocumentService _documentService;
    private readonly IAuthorizationService _authorizationService;

    public DocumentsController(
        IDocumentService documentService,
        IAuthorizationService authorizationService)
    {
        _documentService = documentService;
        _authorizationService = authorizationService;
    }

    [HttpPut("{id:int}")]
    public async Task<IActionResult> Update(
        int id,
        UpdateDocumentRequest request)
    {
        var document = await _documentService.GetByIdAsync(id);
        if (document is null)
        {
            return NotFound();
        }

        var authResult = await _authorizationService
            .AuthorizeAsync(User, document, "DocumentOwner");

        if (!authResult.Succeeded)
        {
            return Forbid();
        }

        var updated = await _documentService.UpdateAsync(id, request);
        return Ok(updated);
    }
}
```

这里 `[Authorize]` 只保证调用者已经登录。真正的“能不能改这份文档”，由 `DocumentOwner` 策略和对应 handler 处理。多租户系统、行级数据权限、按资源归属控制读写时，都应该优先考虑这种写法。

## Minimal API 写法

Minimal API 使用同一套认证和授权服务，只是应用方式从属性变成扩展方法。基础保护可以写在路由组上：

```csharp
var protectedGroup = app.MapGroup("/api/protected")
    .RequireAuthorization();

protectedGroup.MapGet("/profile", (ClaimsPrincipal user) =>
{
    return Results.Ok(new
    {
        Name = user.Identity?.Name,
        Claims = user.Claims.Select(c => new { c.Type, c.Value })
    });
});

protectedGroup.MapGet("/admin-only", () =>
{
    return Results.Ok("Admin content");
})
.RequireAuthorization("AdminOnly");
```

`ClaimsPrincipal` 可以直接作为 handler 参数注入。公开端点可以在组级保护下再调用 `.AllowAnonymous()`。

## 常见坑

`UseAuthentication()` 漏掉或顺序放错，是最常见的问题。表现可能是 `HttpContext.User` 没有预期身份，受保护端点一直返回 401，或者策略看起来没有生效。先检查中间件顺序。

`ValidateAudience` 不要关。原文提醒，如果 API 只检查签名，却不检查 audience，那么别的服务签发的有效 Token 也可能被当前 API 接受。每个 API 都应该有明确 audience。

`ClockSkew` 不要在分布式环境里过分收紧。测试环境里设为 0 可以暴露边界问题，但生产环境通常需要给机器时钟留一点余量。

签名密钥不要进仓库。生产环境使用环境变量或密钥管理服务。开发环境可以用 .NET Secret Manager，避免把真实密钥写进项目文件。

Token 过期后不要只靠延长访问 Token 生命周期。面向用户的应用更常见的做法是短期 access token 加长期 refresh token。refresh token 应存服务端，最好只存哈希，退出登录时可以删除或吊销。

测试受保护端点时有两条路。你可以用测试环境的签名密钥生成真实 JWT，再放进请求头。也可以注册一个测试认证方案，直接返回固定的 `ClaimsPrincipal`，这样测试更快，也更容易覆盖不同角色和声明。

## 实践建议

小型 API 可以先用 `[Authorize]` 和少量角色判断起步。只要规则开始重复，或者同一个规则出现在多个端点，就把它收成命名策略。

涉及具体数据归属时，不要在属性里硬猜。先把资源加载出来，再用 `IAuthorizationService.AuthorizeAsync` 结合当前用户和资源做判断。

JWT 配置要优先保证完整验证：签名、issuer、audience、过期时间都要检查。配置能跑起来只是第一步，更关键的是确认它只接受应该被接受的 Token。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能直接用于项目的工具教程、技术观察和项目经验。

## 参考

- [Authentication and Authorization in ASP.NET Core Web API: JWT and Policies](https://www.devleader.ca/2026/06/03/authentication-and-authorization-in-aspnet-core-web-api-jwt-and-policies)
- [Configure JWT bearer authentication in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/security/authentication/configure-jwt-bearer-authentication?view=aspnetcore-10.0)
- [Policy-based authorization in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/security/authorization/policies?view=aspnetcore-10.0)
- [Resource-based authorization in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/security/authorization/resource-based?view=aspnetcore-10.0)
- [Authentication and authorization in Minimal APIs](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/security?view=aspnetcore-10.0)
