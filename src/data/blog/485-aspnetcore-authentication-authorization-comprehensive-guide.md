---
pubDatetime: 2025-10-16
title: ASP.NET Core 认证与授权完全指南：从 JWT 到属性化授权
description: 系统化学习 ASP.NET Core 中的认证授权机制，涵盖 JWT、基于角色、基于声明和属性化授权四种模式，附完整代码示例和最佳实践。
tags: ["ASP.NET Core", "Security", "Authentication", "Authorization", "JWT"]
slug: aspnetcore-authentication-authorization-comprehensive-guide
source: https://antondevtips.com/blog/authentication-and-authorization-best-practices-in-aspnetcore
---

认证与授权是现代应用安全的两根支柱。许多开发者在理解这两个概念时容易混淆：认证验证用户的身份（**你是谁**），而授权确定认证后的用户可以执行哪些操作（**你能做什么**）。在互联网应用日益受到攻击的今天，理解并正确应用经过验证的安全模式对防止未授权访问和数据泄露至关重要。

本文将深入探讨在 ASP.NET Core 中实现认证和授权的四种主要模式，从入门的 JWT 令牌认证到高级的属性化授权，提供完整的代码示例和实践建议。

## JWT 令牌认证：无状态的身份验证

JSON Web Token（JWT）是当代应用中最流行且安全的认证方式之一。相比传统的基于会话的认证，JWT 支持无状态认证，这使得在微服务和分布式系统中扩展应用变得更加简便。

JWT 的核心优势在于其自包含性——令牌包含用户信息和权限声明，服务器无需查询数据库即可验证其有效性。这种设计特别适合现代云原生应用，其中水平扩展和负载均衡是常见需求。

### 配置 JWT 认证

首先，在 `appsettings.json` 中定义认证配置：

```json
{
  "AuthConfiguration": {
    "Key": "your_secret_key_here_change_it_please",
    "Issuer": "DevTips",
    "Audience": "DevTips"
  }
}
```

接下来，在 `Program.cs` 中配置 JWT Bearer 认证：

```csharp
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
        ValidateAudience = true,
        ValidateLifetime = true,
        ValidateIssuerSigningKey = true,
        ValidIssuer = builder.Configuration["AuthConfiguration:Issuer"],
        ValidAudience = builder.Configuration["AuthConfiguration:Audience"],
        IssuerSigningKey = new SymmetricSecurityKey(
            Encoding.UTF8.GetBytes(builder.Configuration["AuthConfiguration:Key"]!))
    };
});

builder.Services.AddAuthorization();
```

然后，注册认证和授权中间件到请求管道：

```csharp
var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseAuthentication();
app.UseAuthorization();
```

### JWT 令牌安全最佳实践

在处理 JWT 令牌时，需要遵循以下关键的安全原则：

**令牌有效期**：设置较短的令牌生命周期（通常 15-30 分钟）并实现刷新令牌机制。过长的有效期意味着被盗令牌可被利用更长时间；过短的有效期则会频繁需要用户重新认证。刷新令牌应该长期存储在服务器端，用户可以在主令牌过期时获取新令牌。

**签名算法**：采用强大的加密算法（如 HMAC-SHA256 或 HMAC-SHA512）和足够长的密钥。弱密钥容易被暴力破解，从而伪造有效的令牌。

**令牌验证**：严格执行所有验证参数的检查，包括发行者、受众、生命周期和签名密钥。任何验证环节的松动都会成为安全漏洞。

## 使用 ASP.NET Core Identity 进行用户认证

在现实应用中，用户凭证必须安全地存储。永远不要以明文形式保存密码，而应使用强大的哈希算法（如 bcrypt）或 ASP.NET Core Identity 内置的密码哈希器。

以下是使用 ASP.NET Core Identity 和 JWT 实现登录端点的示例：

```csharp
public void AddRoutes(IEndpointRouteBuilder app)
{
    app.MapPost("/api/users/login", Handle);
}

private static async Task<IResult> Handle(
    [FromBody] LoginUserRequest request,
    IOptions<AuthConfiguration> authOptions,
    UserManager<User> userManager,
    SignInManager<User> signInManager,
    CancellationToken cancellationToken)
{
    var user = await userManager.FindByEmailAsync(request.Email);
    if (user is null)
    {
        return Results.NotFound("User not found");
    }

    var result = await signInManager.CheckPasswordSignInAsync(user, request.Password, false);
    if (!result.Succeeded)
    {
        return Results.Unauthorized();
    }

    var token = GenerateJwtToken(user, authOptions.Value);
    return Results.Ok(new { Token = token });
}
```

JWT 令牌生成助手方法：

```csharp
private static string GenerateJwtToken(User user, AuthConfiguration authConfiguration)
{
    var securityKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(authConfiguration.Key));
    var credentials = new SigningCredentials(securityKey, SecurityAlgorithms.HmacSha256);

    var claims = new[]
    {
        new Claim(JwtRegisteredClaimNames.Sub, user.Email!),
        new Claim("userid", user.Id)
    };

    var token = new JwtSecurityToken(
        issuer: authConfiguration.Issuer,
        audience: authConfiguration.Audience,
        claims: claims,
        expires: DateTime.Now.AddMinutes(30),
        signingCredentials: credentials
    );

    return new JwtSecurityTokenHandler().WriteToken(token);
}
```

这个令牌包含用户的电子邮件和用户 ID 声明，有效期为 30 分钟。对于需要更长会话的应用，应该实现刷新令牌机制。

在 Minimal API 中，使用 `RequireAuthorization()` 方法保护端点：

```csharp
app.MapPost("/api/books", Handle)
   .RequireAuthorization();
```

在控制器中，使用 `[Authorize]` 特性装饰类或方法即可。

## 基于角色的授权：RBAC

基于角色的访问控制（RBAC）是最直观的授权模式，通过将用户分组到角色并为这些角色定义访问权限来管理应用权限。这种方法在权限管理相对简单且层次清晰的应用中特别有效。

### 定义和使用角色

考虑一个内容管理系统，其中有两种角色：管理员（Admin）和作者（Author）。管理员可以管理用户和所有内容，而作者只能创建、编辑和删除自己的内容。

首先创建角色：

```csharp
var adminRole = new Role { Name = "Admin" };
var authorRole = new Role { Name = "Author" };

await roleManager.CreateAsync(adminRole);
await roleManager.CreateAsync(authorRole);
```

在授权服务中注册基于角色的策略：

```csharp
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("Admin", policy =>
    {
        policy.RequireRole("Admin");
    });

    options.AddPolicy("Author", policy =>
    {
        policy.RequireRole("Author");
    });

    options.AddPolicy("ContentEditor", policy =>
    {
        // 允许管理员和作者编辑内容
        policy.RequireRole("Admin", "Author");
    });
});
```

在 Minimal API 中应用策略：

```csharp
public void AddRoutes(IEndpointRouteBuilder app)
{
    app.MapPost("/api/books", Handle)
        .RequireAuthorization("ContentEditor");

    app.MapPost("/api/users", Handle)
        .RequireAuthorization("Admin");
}
```

### RBAC 的局限性

虽然 RBAC 简单易用，但当应用增长时，角色和权限的组合管理会变得复杂。例如，若需要支持十多个角色的各种权限组合，代码会快速变得难以维护。这时应考虑转向更灵活的授权模式。

## 基于声明的授权：更细粒度的权限控制

基于声明的授权（Claims-Based Authorization）提供了比角色更灵活的权限管理方式。不同于将权限固化到角色中，声明允许动态地为用户分配特定的权限，使应用能够适应复杂的业务规则。

### 为角色分配声明

在声明模型中，权限被表示为声明（Claim）。下面示例为不同角色分配特定的权限声明：

```csharp
var adminRole = new Role { Name = "Admin" };
var authorRole = new Role { Name = "Author" };

await roleManager.CreateAsync(adminRole);
await roleManager.CreateAsync(authorRole);

// 为管理员分配权限
await roleManager.AddClaimAsync(adminRole, new Claim("users:create", "true"));
await roleManager.AddClaimAsync(adminRole, new Claim("users:update", "true"));
await roleManager.AddClaimAsync(adminRole, new Claim("users:delete", "true"));

await roleManager.AddClaimAsync(adminRole, new Claim("books:create", "true"));
await roleManager.AddClaimAsync(adminRole, new Claim("books:update", "true"));
await roleManager.AddClaimAsync(adminRole, new Claim("books:delete", "true"));

// 为作者分配权限
await roleManager.AddClaimAsync(authorRole, new Claim("books:create", "true"));
await roleManager.AddClaimAsync(authorRole, new Claim("books:update", "true"));
await roleManager.AddClaimAsync(authorRole, new Claim("books:delete", "true"));
```

### 在端点中应用声明策略

定义 Minimal API 端点时，指定所需的权限声明：

```csharp
public void AddRoutes(IEndpointRouteBuilder app)
{
    app.MapPost("/api/books", Handle)
        .RequireAuthorization("books:create");

    app.MapDelete("/api/books/{id}", Handle)
        .RequireAuthorization("books:delete");

    app.MapPost("/api/users", Handle)
        .RequireAuthorization("users:create");

    app.MapDelete("/api/users/{id}", Handle)
        .RequireAuthorization("users:delete");
}
```

### 在 JWT 令牌中包含声明

生成 JWT 令牌时，应包含用户的所有权限声明，以便在客户端或网关进行本地验证而无需每次都查询服务器：

```csharp
private static string GenerateJwtToken(User user, AuthConfiguration authConfiguration)
{
    var securityKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(authConfiguration.Key));
    var credentials = new SigningCredentials(securityKey, SecurityAlgorithms.HmacSha256);

    var roleClaims = await userManager.GetClaimsAsync(user);
    var userRole = await userManager.GetRolesAsync(user);

    List<Claim> claims = [
        new(JwtRegisteredClaimNames.Sub, user.Email!),
        new("userid", user.Id),
        new("role", userRole.FirstOrDefault() ?? "User")
    ];

    foreach (var roleClaim in roleClaims)
    {
        claims.Add(new Claim(roleClaim.Type, roleClaim.Value));
    }

    var token = new JwtSecurityToken(
        issuer: authConfiguration.Issuer,
        audience: authConfiguration.Audience,
        claims: claims,
        expires: DateTime.Now.AddMinutes(30),
        signingCredentials: credentials
    );

    return new JwtSecurityTokenHandler().WriteToken(token);
}
```

解码后的 JWT 令牌示例如下所示，包含用户的完整权限清单：

```json
{
  "sub": "admin@test.com",
  "userid": "dc233fac-bace-4719-9a4f-853e199300d5",
  "role": "Admin",
  "users:create": "true",
  "users:update": "true",
  "users:delete": "true",
  "books:create": "true",
  "books:update": "true",
  "books:delete": "true",
  "exp": 1739481834,
  "iss": "DevTips",
  "aud": "DevTips"
}
```

### 注册声明策略

在授权服务中注册所有权限声明作为策略：

```csharp
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("books:create", policy => policy.RequireClaim("books:create", "true"));
    options.AddPolicy("books:update", policy => policy.RequireClaim("books:update", "true"));
    options.AddPolicy("books:delete", policy => policy.RequireClaim("books:delete", "true"));

    options.AddPolicy("users:create", policy => policy.RequireClaim("users:create", "true"));
    options.AddPolicy("users:update", policy => policy.RequireClaim("users:update", "true"));
    options.AddPolicy("users:delete", policy => policy.RequireClaim("users:delete", "true"));
});
```

注意这里使用 `RequireClaim` 而非 `RequireRole` 进行声明验证。

## 属性化授权：资源级别的访问控制

虽然基于角色和声明的授权在许多场景中足够，但当访问决策涉及用户属性和资源属性的复杂交互时，则需要属性化授权（Attribute-Based Access Control，ABAC）。

典型场景包括：允许作者只编辑自己的书籍；允许区域经理管理特定区域内的内容。

### 实现自定义授权需求和处理器

首先定义自定义授权需求：

```csharp
public class BookAuthorRequirement : IAuthorizationRequirement
{
}
```

实现授权处理器，检查当前用户是否为书籍的作者：

```csharp
public class BookAuthorHandler : AuthorizationHandler<BookAuthorRequirement, Book>
{
    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        BookAuthorRequirement requirement,
        Book resource)
    {
        var userId = context.User.FindFirst("userid")?.Value;
        if (userId is not null && userId == resource.AuthorId)
        {
            context.Succeed(requirement);
        }

        return Task.CompletedTask;
    }
}
```

在依赖注入容器中注册处理器：

```csharp
builder.Services.AddScoped<IAuthorizationHandler, BookAuthorHandler>();
```

### 在端点中使用自定义授权

保护 API 端点需要首先通过基础权限检查（如 `books:update`），然后在处理器中进行资源级别的验证：

```csharp
app.MapPut("/api/books/{id}", Handle)
    .RequireAuthorization("books:update");

private static async Task<IResult> Handle(
    [FromRoute] Guid id,
    [FromBody] UpdateBookRequest request,
    IBookRepository repository,
    IAuthorizationService authService,
    ClaimsPrincipal user,
    CancellationToken cancellationToken)
{
    var book = await repository.GetByIdAsync(id, cancellationToken);
    if (book is null)
    {
        return Results.NotFound($"Book with id {id} not found");
    }

    var requirement = new BookAuthorRequirement();
    var authResult = await authService.AuthorizeAsync(user, book, requirement);

    if (!authResult.Succeeded)
    {
        return Results.Forbid();
    }

    book.Title = request.Title;
    book.Year = request.Year;

    await repository.UpdateAsync(book, cancellationToken);

    return Results.NoContent();
}
```

这种方法确保只有书籍的原创作者能够编辑它。通过比较用户的 `userid` 声明与书籍的作者 ID，系统可以精确控制资源访问权限。

## 选择合适的授权策略

在为应用选择授权模式时，需要根据具体业务需求权衡复杂性和灵活性：

**基于角色的授权（RBAC）**最适合权限模式相对固定、用户分类清晰的应用。例如，电子商务平台中的普通用户、商家、管理员。这种方法简单直观，易于理解和维护。

**基于声明的授权**适用于需要更精细权限控制的场景。通过动态分配权限声明，可以灵活调整用户能力而无需修改代码。许多复杂的 SaaS 应用采用这种模式，支持租户级别的权限配置。

**属性化授权（ABAC）**适合权限决策取决于动态属性的场景——用户属性、资源属性、环境属性等。这是最灵活的方案，但也最复杂。协作编辑工具、多租户平台和权限管理高度精细的系统通常需要 ABAC。

## 总结

认证与授权是应用安全的基础。本文介绍了在 ASP.NET Core 中实现这两个关键功能的四种主要模式。从无状态的 JWT 令牌认证，到逐步递进的三种授权策略，开发者可以根据应用的具体需求选择合适的组合方案。

JWT 令牌认证提供了现代、可扩展的用户身份验证机制。基于角色的授权简单易用，适合权限层次分明的应用。基于声明的授权提供更多灵活性，支持动态权限管理。属性化授权则在必要时为资源级访问控制提供强大的支持。

理解这些模式之间的区别和适用场景，将帮助你设计更安全、更可维护的应用架构。在生产环境中实现时，记住始终优先考虑安全性，定期审计权限配置，确保系统抵御常见的认证和授权漏洞。
