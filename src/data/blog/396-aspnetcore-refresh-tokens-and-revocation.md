---
pubDatetime: 2025-07-01
tags: [".NET", "ASP.NET Core", "Security"]
slug: aspnetcore-refresh-tokens-and-revocation
source: https://antondevtips.com/blog/how-to-implement-refresh-tokens-and-token-revocation-in-aspnetcore
title: ASP.NET Core中实现Refresh Token与Token撤销的完整实践
description: 本文详细梳理了如何在ASP.NET Core项目中实现基于JWT的Refresh Token机制与Token撤销，深入讲解实现原理、关键代码、安全建议，并对动态权限变更场景下的Token失效做出实战拆解，适合有一定.NET开发基础的工程师深入参考。
---

---

# ASP.NET Core中实现Refresh Token与Token撤销的完整实践

现代Web应用的用户认证已经大面积采用了JWT（JSON Web Token）方案。与传统的Session机制相比，JWT天然具备无状态、易于扩展和性能高的特点。但这也带来了新的问题——**如何安全、优雅地处理Token过期，以及用户动态权限的变化？**

本文以ASP.NET Core为例，全面梳理JWT+Refresh Token的最佳实践，并结合代码详细拆解Token撤销、动态权限变更、令牌存储与安全细节，帮助你搭建可支撑生产级别的认证体系。

## 一、为什么要用Refresh Token？

JWT的设计初衷是将认证信息（如用户ID、角色、权限等）加密后直接存储在Token中，避免服务端维护Session。这让API服务易于横向扩展，却让**Token的有效期管理变得更为关键**：

- **Access Token**（访问令牌）通常只有5\~10分钟的短生命周期，一旦过期需重新获取，否则容易被攻击者利用。
- 用户频繁登录，体验极差。如何兼顾安全与易用？

**Refresh Token**机制应运而生：它是一种专门用于刷新Access Token的长期令牌，用户凭此无需反复登录即可获得新的访问令牌，大幅提升用户体验。

认证流程简述如下：

1. 用户首次登录后，服务端同时下发Access Token与Refresh Token。
2. 客户端安全保存（建议HttpOnly Cookie或安全本地加密）。
3. 当Access Token失效后，客户端用Refresh Token向服务端请求新的Access Token。
4. 服务端校验Refresh Token有效性，签发新Token并替换旧的Refresh Token，确保每次刷新都令前一个Refresh Token失效，最大限度防范重放攻击。
5. 客户端拿到新Token，用户无感知继续使用。

## 二、ASP.NET Core中Refresh Token的实现

下面以真实项目代码为例，梳理核心实现：

### 1. 基础认证配置

首先，配置JWT验证参数，设定Issuer、Audience及密钥等。

```csharp
var tokenValidationParameters = new TokenValidationParameters
{
    ValidateIssuer = true,
    ValidateAudience = true,
    ValidateLifetime = true,
    ValidateIssuerSigningKey = true,
    ValidIssuer = configuration["AuthConfiguration:Issuer"],
    ValidAudience = configuration["AuthConfiguration:Audience"],
    IssuerSigningKey = new SymmetricSecurityKey(
        Encoding.UTF8.GetBytes(configuration["AuthConfiguration:Key"]!))
};

services.AddSingleton(tokenValidationParameters);
services.AddAuthentication(options =>
{
    options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
    options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
})
.AddJwtBearer(options =>
{
    options.TokenValidationParameters = tokenValidationParameters;
});
```

### 2. Refresh Token数据模型设计

Refresh Token推荐采用数据库存储，支持灵活管理和撤销：

```csharp
public class RefreshToken
{
    public string Token { get; set; }
    public string JwtId { get; set; }
    public DateTime ExpiryDate { get; set; }
    public bool Invalidated { get; set; }
    public string UserId { get; set; }
    public User User { get; set; }
}
```

与用户实体绑定，支持后续查找与批量撤销。

### 3. 用户登录与Token签发

登录时返回Access Token和Refresh Token：

```csharp
public sealed record LoginUserResponse(string Token, string RefreshToken);
```

刷新接口定义：

```csharp
public sealed record RefreshTokenRequest(string Token, string RefreshToken);
public sealed record RefreshTokenResponse(string Token, string RefreshToken);
```

### 4. 刷新Token接口实现

刷新过程重点包括：

- 校验Access Token数字签名
- 提取JWT Id，与数据库中Refresh Token一一比对
- 检查Refresh Token未过期、未被撤销
- 创建新Token，旧Refresh Token从库中移除

核心逻辑片段如下：

```csharp
public async Task<Result<RefreshTokenResponse>> RefreshTokenAsync(
    string token, string refreshToken, CancellationToken cancellationToken = default)
{
    var validatedToken = GetPrincipalFromToken(token, _tokenValidationParameters);
    if (validatedToken is null) return Failure("Invalid token");

    var jti = validatedToken.Claims.SingleOrDefault(x => x.Type == JwtRegisteredClaimNames.Jti)?.Value;
    if (string.IsNullOrEmpty(jti)) return Failure("Invalid token");

    var storedRefreshToken = await _dbContext.RefreshTokens.FirstOrDefaultAsync(x => x.Token == refreshToken, cancellationToken);
    if (storedRefreshToken is null || DateTime.UtcNow > storedRefreshToken.ExpiryDate || storedRefreshToken.Invalidated || storedRefreshToken.JwtId != jti)
        return Failure("Refresh token不合法或已失效");

    var userId = validatedToken.Claims.FirstOrDefault(x => x.Type == "userid")?.Value;
    var user = await _userManager.FindByIdAsync(userId);
    if (user is null) return Failure("用户不存在");

    var (newToken, newRefreshToken) = await GenerateJwtAndRefreshTokenAsync(user, refreshToken);
    return Success(new RefreshTokenResponse(newToken, newRefreshToken));
}
```

**注意每次刷新时都要使旧Refresh Token失效，防止被重用攻击。**

## 三、Refresh Token的安全细节

Refresh Token机制本身不是银弹，只有遵循如下安全措施才能真正防护风险：

- **令牌存储：** 强烈建议前端使用HttpOnly Cookie存储Token，杜绝XSS风险。
- **Token轮换（Rotation）：** 每次刷新必生成新Refresh Token，并删除旧Token，降低泄露风险。
- **Token撤销（Revocation）：** 支持主动失效，便于处理用户登出、密码变更、敏感操作后重签等场景。
- **Token绑定：** 可将Token与设备、IP等进行绑定，实现异常行为检测。
- **权限最小化：** Refresh Token本身不应有访问敏感资源的权限，只能用于获取新的Access Token。

**Access Token建议5-10分钟短有效期，Refresh Token可根据业务调整为1天\~1月。对于金融/高敏系统可进一步缩短并强化行为分析。**

## 四、动态权限变更与Token撤销

在实际业务中，往往需要在用户权限或角色变更后，实时收回已有Token的访问能力。实现方法如下：

- **批量撤销所有相关Refresh Token**，并通过内存缓存或分布式缓存（如Redis）记录已失效Token的JwtId。
- **自定义中间件**，每次API访问时自动检测当前Token是否被撤销。

例如，更新用户角色后批量撤销相关Token：

```csharp
// 查询所有未失效的Refresh Token
var refreshTokens = await _dbContext.RefreshTokens
    .Where(rt => rt.UserId == userId && !rt.Invalidated)
    .ToListAsync(cancellationToken);

foreach (var refreshToken in refreshTokens)
{
    refreshToken.Invalidated = true;
    refreshToken.UpdatedAtUtc = DateTime.UtcNow;
    _memoryCache.Set(refreshToken.JwtId, RevocatedTokenType.RoleChanged);
}
await _dbContext.SaveChangesAsync(cancellationToken);
```

**中间件实现Token撤销检测：**

```csharp
public class CheckRevocatedTokensMiddleware
{
    public async Task InvokeAsync(HttpContext context)
    {
        var jwtId = context.User.FindFirst(JwtRegisteredClaimNames.Jti);
        if (jwtId != null && _memoryCache.Get<RevocatedTokenType?>(jwtId.Value) != null)
        {
            context.Response.StatusCode = StatusCodes.Status401Unauthorized;
            return;
        }
        await _next(context);
    }
}
```

配合`HostedService`在服务重启时自动恢复撤销状态，保证高可用。

## 五、总结与实战建议

Refresh Token和Token撤销机制极大提升了用户体验与系统安全性。掌握这些原理和落地细节，将帮助你构建更加健壮的分布式认证架构：

- 保证所有Token的生命周期与存储安全；
- 动态管理用户权限变化，实现实时权限下发与撤销；
- 结合缓存与数据库，兼顾性能与一致性。
