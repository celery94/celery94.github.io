---
pubDatetime: 2026-05-09T08:42:00+08:00
title: "ASP.NET Core .NET 10 API Key 认证完全指南"
description: "生产级 API Key 认证在 ASP.NET Core .NET 10 中的完整实现：SHA-256 哈希存储、EF Core 数据库支持、AuthenticationHandler 集成、HybridCache 验证缓存、决策矩阵，以及完整源码参考。"
tags: ["dotnet", "aspnet-core", "authentication", "api-security"]
slug: "api-key-authentication-aspnet-core"
ogImage: "../../assets/785/01-cover.png"
source: "https://codewithmukesh.com/blog/api-key-authentication-aspnet-core/"
---

假设有个外部天气组件每天调用你的 API 一百万次。没有人坐在键盘前操作，没有 OAuth 流程，没有刷新 token 的逻辑——只是某个服务器每分钟悄悄打一次 `/forecast`。JWT 用在这里显得多余，Cookie 根本不适用。这个调用方真正需要的，是一个长期有效、可识别、可撤销的凭证，用来说明"我是这个客户端，让我进来"。这就是 API Key 的用途。在 .NET 10 里把它做对，是干净集成和凌晨两点被 Pastebin 泄漏告警之间的区别。

![ASP.NET Core API Key 认证完整流程图](../../assets/785/01-cover.png)

**API key 认证**是一种方案：客户端通过请求头发送预共享的密钥字符串，服务端将其与存储的哈希值比对，决定放行还是拒绝。推荐实现是自定义 `AuthenticationHandler<T>`，配合 EF Core 10 实现可撤销的哈希密钥存储，以及 HybridCache 实现亚毫秒级热路径验证。

本文从 5 分钟静态密钥快速上手，到带前缀（`sk_live_…`）、哈希、轮换、撤销、权限范围、HybridCache 验证、Scalar OpenAPI 集成和审计日志的完整生产实现，逐层讲清楚。同时提供一个决策矩阵，帮你在 API Key、JWT、OAuth 和 mTLS 之间做出正确选择。

---

## 什么是 API Key 认证

**API key 认证**让客户端通过一个预共享的字符串密钥向服务端表明身份。服务端将密钥与存储值（或其哈希）比对，放行或拒绝。这个密钥回答的是一个问题：**哪个应用在调用？** 它本身不识别具体用户。

三个让 API key 与众不同的特点：

- **长期有效**：密钥通常数月甚至数年有效，没有刷新流程
- **持有即使用**：任何拿到密钥的人都能使用，没有持有证明（PoP）层
- **应用身份，而非用户身份**：API key 说的是"我是 WeatherWidget 公司"，不是"我是 Mukesh，在下午三点登录"

最后一点是大多数团队用错的地方。API key 适合**机器对机器**（M2M）调用：合作方后端调你的 API、内部定时任务、Webhook 接收端。它不适合用户登录场景——你需要知道是谁点了按钮时，用 JWT、Cookie 或 OAuth。

OWASP API 安全 Top 10（2023）将 API2:2023 认证缺陷列为第二大关键 API 风险，明文 API key 存储和缺失轮换是其中的典型例子。本文会把这两个问题都修掉。

---

## 决策矩阵：API Key vs JWT vs OAuth vs mTLS

先选对工具，再写代码。

| 维度 | API Key | JWT | OAuth 2.0/OIDC | mTLS |
|------|---------|-----|---------------|------|
| 调用方类型 | 服务器、脚本、IoT | 服务器或用户 | 用户授权委托 | 服务器（高安全） |
| 识别用户？ | 否（仅应用） | 是 | 是 | 否（证书主体） |
| 有效期 | 月/年 | 分钟/小时 | 分钟（access）+ 天（refresh） | 证书有效期 |
| 撤销成本 | 低（数据库标记） | 高（等过期或黑名单） | 高（撤销 refresh token） | 高（证书吊销列表） |
| 权限粒度 | 每个密钥自定义 claims | 每个 token 的 claims | 通过 scope claim 丰富 | 原生没有 |
| 传输方式 | `X-API-Key` 请求头 | `Authorization: Bearer` | `Authorization: Bearer` | TLS 握手 |
| .NET 10 代码量 | ~50 行（自定义 handler） | `JwtBearer` 包 | OpenIddict / Duende | 内置 |
| 最适合 | Webhook、合作方 API、CLI、IoT | SPA、移动端、微服务 | 第三方应用授权 | 银行、监管行业 |

**结论**：调用方是服务器，选 API Key；调用方是人，选 JWT 或 OAuth。大多数生产系统会混用两者：OAuth 给用户，API key 给合作方集成和 Webhook。这正是 Stripe、GitHub 和主流 SaaS API 的模式。

---

## API Key 的内部结构

动手写代码之前，先搞清楚 2026 年一个 API key 长什么样。

**永远用请求头，绝对不要用查询字符串。**

查询字符串的问题：
- 会以明文出现在服务器访问日志里
- 会出现在浏览器历史中
- 如果响应触发跳转，会出现在 Referer 头里
- CDN 和代理会缓存 URL——缓存的 GET 响应把密钥包进了缓存 key

事实上的请求头名称是 `X-API-Key`（`X-` 前缀虽已被 RFC 6648 废弃，但因为 AWS API Gateway、旧版 GitHub 等广泛采用，已成惯例）。有些 API 用 `Authorization: ApiKey <key>` 格式，两种都行，选一种坚持用。

### 密钥字符串的组成

一个好的 API key 有三部分：

```
sk_live_3K7s9x2mPq8vN4Lr6Hf2bT5wX1yZ8cD3eF7gH9jK
└──┬──┘└────────────────┬───────────────────────┘
   │                    │
 前缀            随机密钥（160-256 bits）
```

- **前缀**（`sk_live_`、`sk_test_`、`pk_live_`）：一眼看出密钥类型。`sk_` 是私密密钥，`pk_` 是可公开密钥，`_live` 是生产，`_test` 是沙盒。这个模式由 Stripe 推广，现在 GitHub、OpenAI、Anthropic 都在用。前缀**可以安全写入日志**，因为它不包含秘密。GitHub 的密钥扫描工具就是用 `ghp_` 等前缀来检测意外提交的 token。
- **随机密钥**：至少 128 bits 熵，推荐 256 bits。用 `RandomNumberGenerator.GetBytes()` 生成并进行 Base64URL 编码。
- **总长度**：通常 32-48 个字符。

在 .NET 10 中生成密钥：

```csharp
using System.Security.Cryptography;

public static string GenerateApiKey(string prefix = "sk_live_")
{
    Span<byte> bytes = stackalloc byte[32]; // 256 bits
    RandomNumberGenerator.Fill(bytes);
    var secret = Convert.ToBase64String(bytes)
        .Replace('+', '-')
        .Replace('/', '_')
        .TrimEnd('=');
    return $"{prefix}{secret}";
}
```

`RandomNumberGenerator.Fill` 使用 OS 的加密随机源——Linux 从 `/dev/urandom` 读取，Windows 从 `BCryptGenRandom`。**不要用 `Random` 或 `Guid.NewGuid()`**：`Random` 是可预测的；`Guid` 只有 122 bits 熵，格式也容易被识别。

---

## 四种实现方式的对比

| 方式 | 运行位置 | 支持 `[Authorize]`？ | OpenAPI 集成？ | 推荐？ |
|------|----------|---------------------|--------------|--------|
| 中间件 | 整个管道 | 否 | 否（手动） | 跳过 |
| Authorization Filter | 每个控制器/Action | 间接 | 否 | 仅 MVC |
| Endpoint Filter | 每个端点/分组 | 否（自定义） | 手动 | 一次性可以 |
| **AuthenticationHandler&lt;T&gt;** | **认证中间件** | **是** | **是** | **推荐** |

用 `AuthenticationHandler<TOptions>` 的理由：

1. **`[Authorize]` 开箱即用**：handler 创建 `ClaimsPrincipal`，ASP.NET Core 认证管道与 JWT、Cookie 同等运行
2. **OpenAPI 集成一行搞定**：Scalar 和 Swagger UI 都会显示 Authorize 按钮
3. **策略开箱即用**：每个密钥的权限范围（`keys:read`、`keys:admin`）直接用标准 `[Authorize(Policy = "...")]`
4. **混用方案零成本**：合作方用 API key，用户用 JWT，同一个应用，无需纠结中间件顺序

中间件方式在旧文章里被广泛推荐——**2026 年新代码不要用**，它绕过了认证管道，无法与 `[Authorize]` 协同。

---

## 快速上手：静态密钥版本

先从最简单的生产形态开始：一个静态密钥，由 `AuthenticationHandler` 验证。对于内部 API 或 MVP 足够用。

### 项目初始化

```bash
dotnet new web -n ApiKeyAuth.Api
cd ApiKeyAuth.Api
dotnet add package Microsoft.AspNetCore.OpenApi --version 10.0.0
dotnet add package Scalar.AspNetCore --version 2.11.9
```

### Options 类

```csharp
using Microsoft.AspNetCore.Authentication;

namespace ApiKeyAuth.Api.Authentication;

public sealed class ApiKeyAuthenticationOptions : AuthenticationSchemeOptions
{
    public const string DefaultScheme = "ApiKey";
    public const string HeaderName = "X-API-Key";
}
```

继承 `AuthenticationSchemeOptions` 是标准模式，常量放在一起，后续引用 `ApiKeyAuthenticationOptions.DefaultScheme` 而不是魔法字符串。

### Handler 实现

```csharp
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Options;

namespace ApiKeyAuth.Api.Authentication;

public sealed class ApiKeyAuthenticationHandler(
    IOptionsMonitor<ApiKeyAuthenticationOptions> options,
    ILoggerFactory logger,
    UrlEncoder encoder,
    IConfiguration configuration)
    : AuthenticationHandler<ApiKeyAuthenticationOptions>(options, logger, encoder)
{
    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Headers.TryGetValue(
                ApiKeyAuthenticationOptions.HeaderName, out var providedKey))
        {
            return Task.FromResult(AuthenticateResult.NoResult());
        }

        var expectedKey = configuration["ApiKey:Value"];
        if (string.IsNullOrEmpty(expectedKey))
        {
            return Task.FromResult(
                AuthenticateResult.Fail("API key is not configured on the server."));
        }

        var providedBytes = Encoding.UTF8.GetBytes(providedKey.ToString());
        var expectedBytes = Encoding.UTF8.GetBytes(expectedKey);

        if (providedBytes.Length != expectedBytes.Length ||
            !CryptographicOperations.FixedTimeEquals(providedBytes, expectedBytes))
        {
            return Task.FromResult(AuthenticateResult.Fail("Invalid API key."));
        }

        var claims = new[]
        {
            new Claim(ClaimTypes.Name, "static-client"),
            new Claim("client_id", "static-client")
        };
        var identity = new ClaimsIdentity(claims, Scheme.Name);
        var principal = new ClaimsPrincipal(identity);
        var ticket = new AuthenticationTicket(principal, Scheme.Name);

        return Task.FromResult(AuthenticateResult.Success(ticket));
    }
}
```

两个值得关注的细节：

- **缺少请求头时返回 `AuthenticateResult.NoResult()`**：这表示"未作决定"而不是"失败"，允许其他认证方案继续尝试。如果直接返回 `Fail`，混用多个认证方案会变得麻烦。
- **`CryptographicOperations.FixedTimeEquals` 比较**：普通的 `string.Equals` 一遇到不匹配字符就立刻返回。攻击者通过测量响应时间可以逐字节推导出密钥。`FixedTimeEquals` 无论字节在哪里开始不同，耗时始终相同——这是**时序攻击防护**。

### 接入 Program.cs

```csharp
using ApiKeyAuth.Api.Authentication;
using Microsoft.AspNetCore.Authentication;
using Scalar.AspNetCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenApi();
builder.Services
    .AddAuthentication(ApiKeyAuthenticationOptions.DefaultScheme)
    .AddScheme<ApiKeyAuthenticationOptions, ApiKeyAuthenticationHandler>(
        ApiKeyAuthenticationOptions.DefaultScheme, _ => { });
builder.Services.AddAuthorization();

var app = builder.Build();

app.MapOpenApi();
app.MapScalarApiReference();

app.MapGet("/public", () => "anyone can read this");

app.MapGet("/secure", () => "only callers with a valid API key see this")
   .RequireAuthorization();

app.Run();
```

在 `appsettings.Development.json` 里配置静态密钥（正式环境用环境变量或密钥管理服务）：

```json
{
  "ApiKey": {
    "Value": "sk_live_3K7s9x2mPq8vN4Lr6Hf2bT5wX1yZ8cD3eF7gH9jK"
  }
}
```

验证效果：

```bash
# 应该返回 401
curl http://localhost:5000/secure

# 应该返回内容
curl -H "X-API-Key: sk_live_3K7s9x2mPq8vN4Lr6Hf2bT5wX1yZ8cD3eF7gH9jK" http://localhost:5000/secure
```

这个版本大约 60 行，对于单一可信客户端在生产环境也够用。但一旦有两个客户端就撑不住了：增加客户端需要重新部署，撤销密钥也需要重新部署，没有审计记录，而且密钥在 `appsettings.json` 里——这是 API key 出现在 Pastebin 上最常见的原因。

---

## 生产级实现：哈希 + 数据库存储

真正的生产实现需要六个属性：

1. 每个客户端有唯一密钥
2. 数据库存哈希，不存明文
3. 明文密钥只在颁发时展示一次
4. 每个密钥有过期时间和显式撤销机制
5. 每个密钥携带权限范围（细粒度授权）
6. 每次请求更新"最后使用时间"便于审查

### `ApiKey` 实体

```csharp
namespace ApiKeyAuth.Api.Entities;

public class ApiKey
{
    public Guid Id { get; set; } = Guid.NewGuid();

    // 明文密钥的前 12 个字符（如 "sk_live_3K7s"）
    // 用于索引查询和审计日志，不泄露秘密
    public string Prefix { get; set; } = default!;

    // 完整明文密钥的 SHA-256 哈希，十六进制编码
    public string KeyHash { get; set; } = default!;

    public string Name { get; set; } = default!;
    public string OwnerId { get; set; } = default!;

    // 逗号分隔的权限范围（"keys:read", "keys:admin"）
    public string Scopes { get; set; } = string.Empty;

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? ExpiresAt { get; set; }
    public DateTime? RevokedAt { get; set; }
    public DateTime? LastUsedAt { get; set; }

    public bool IsActive(TimeProvider time) =>
        RevokedAt is null && (ExpiresAt is null || ExpiresAt > time.GetUtcNow());
}
```

### 为什么用 SHA-256 哈希？

哈希 API key 的目的和哈希密码一样：数据库被窃取时，攻击者拿到的是哈希，不是可直接使用的凭证。

对密码，你需要慢哈希（Argon2id、高迭代 PBKDF2），因为密码是低熵的，人们会选"password123"。对 API key，你需要快哈希（SHA-256），原因：

- **高熵**：256 bits 的随机密钥在计算上无法暴力破解，慢哈希毫无收益
- **验证在每次请求时运行**：Argon2id 每次 100ms 会把 API 吞吐量限制在每核 ~10 RPS，SHA-256 只需微秒
- **不需要 salt**：每个密钥本身已经是随机唯一的

```csharp
using System.Security.Cryptography;
using System.Text;

public static class ApiKeyHasher
{
    public static string Hash(string plaintextKey)
    {
        Span<byte> hash = stackalloc byte[32];
        SHA256.HashData(Encoding.UTF8.GetBytes(plaintextKey), hash);
        return Convert.ToHexString(hash);
    }

    public static bool Verify(string plaintextKey, string storedHash)
    {
        var computed = Hash(plaintextKey);
        return CryptographicOperations.FixedTimeEquals(
            Encoding.UTF8.GetBytes(computed),
            Encoding.UTF8.GetBytes(storedHash));
    }
}
```

`SHA256.HashData` 是 `SHA256` 类上的一次性静态 API，比旧版 `SHA256.Create()` 实例模式更快、更低分配，[CA1850](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1850) 分析器也推荐它。

### EF Core 数据库配置

```csharp
using ApiKeyAuth.Api.Entities;
using Microsoft.EntityFrameworkCore;

namespace ApiKeyAuth.Api.Data;

public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<ApiKey> ApiKeys => Set<ApiKey>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<ApiKey>(entity =>
        {
            entity.HasKey(k => k.Id);
            entity.Property(k => k.Prefix).IsRequired().HasMaxLength(20);
            entity.Property(k => k.KeyHash).IsRequired().HasMaxLength(64);
            entity.Property(k => k.Name).IsRequired().HasMaxLength(100);
            entity.Property(k => k.OwnerId).IsRequired().HasMaxLength(100);
            entity.Property(k => k.Scopes).HasMaxLength(500);

            // KeyHash 是实际查找列——唯一索引，O(log n) 查询
            entity.HasIndex(k => k.KeyHash).IsUnique();

            // Prefix 索引用于管理/审计查询
            entity.HasIndex(k => k.Prefix);
        });
    }
}
```

`KeyHash` 的唯一索引让数据库端查询达到 O(log n)。非唯一的 Prefix 索引纯粹用于管理查询。

### 颁发新密钥

```csharp
public sealed record IssueApiKeyRequest(string Name, string OwnerId, string[] Scopes, int? TtlDays);
public sealed record IssueApiKeyResponse(Guid Id, string Name, string PlaintextKey, string Prefix, DateTime? ExpiresAt);

app.MapPost("/admin/keys", async (
    IssueApiKeyRequest request,
    AppDbContext db,
    TimeProvider time,
    CancellationToken ct) =>
{
    var plaintext = ApiKeyGenerator.Generate("sk_live_");

    var entity = new ApiKey
    {
        Prefix = plaintext[..12],
        KeyHash = ApiKeyHasher.Hash(plaintext),
        Name = request.Name,
        OwnerId = request.OwnerId,
        Scopes = string.Join(',', request.Scopes),
        ExpiresAt = request.TtlDays is { } days
            ? time.GetUtcNow().AddDays(days).UtcDateTime
            : null
    };

    db.ApiKeys.Add(entity);
    await db.SaveChangesAsync(ct);

    return Results.Created(
        $"/admin/keys/{entity.Id}",
        new IssueApiKeyResponse(entity.Id, entity.Name, plaintext, entity.Prefix, entity.ExpiresAt));
})
.RequireAuthorization("admin");
```

明文密钥在 `IssueApiKeyResponse` 中**只返回一次**。客户端必须自己保存——因为我不再拥有它（只有哈希）。这和 GitHub personal access token 的体验一样：现在复制，否则再生成一个。

这里用 `TimeProvider.GetUtcNow()` 而不是 `DateTime.UtcNow`，因为 `TimeProvider` 是 .NET 8+ 的可测试时间抽象——测试项目用 `FakeTimeProvider` 来测试过期逻辑，无需 `Thread.Sleep`。

### 生产版 Handler

```csharp
public sealed class ApiKeyAuthenticationHandler(
    IOptionsMonitor<ApiKeyAuthenticationOptions> options,
    ILoggerFactory logger,
    UrlEncoder encoder,
    IApiKeyValidator validator)
    : AuthenticationHandler<ApiKeyAuthenticationOptions>(options, logger, encoder)
{
    protected override async Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Headers.TryGetValue(
                ApiKeyAuthenticationOptions.HeaderName, out var providedKey))
        {
            return AuthenticateResult.NoResult();
        }

        var key = providedKey.ToString();
        var result = await validator.ValidateAsync(key, Context.RequestAborted);

        if (!result.IsValid)
        {
            Logger.LogWarning(
                "API key authentication failed for prefix {Prefix}: {Reason}",
                result.Prefix ?? "(none)", result.Reason);
            return AuthenticateResult.Fail(result.Reason ?? "Invalid API key.");
        }

        var claims = new List<Claim>
        {
            new(ClaimTypes.NameIdentifier, result.KeyId!.Value.ToString()),
            new(ClaimTypes.Name, result.Name!),
            new("client_id", result.OwnerId!),
            new("api_key_prefix", result.Prefix!)
        };
        claims.AddRange(result.Scopes.Select(s => new Claim("scope", s)));

        var identity = new ClaimsIdentity(claims, Scheme.Name);
        var principal = new ClaimsPrincipal(identity);
        var ticket = new AuthenticationTicket(principal, Scheme.Name);

        return AuthenticateResult.Success(ticket);
    }
}
```

Handler 将查找委托给 `IApiKeyValidator`，这个分离使得在不改动 handler 的情况下叠加缓存成为可能。

### 验证器与 HybridCache

```csharp
public sealed record ApiKeyValidationResult(
    bool IsValid,
    string? Reason,
    Guid? KeyId,
    string? Name,
    string? OwnerId,
    string? Prefix,
    string[] Scopes)
{
    public static ApiKeyValidationResult Invalid(string reason, string? prefix = null) =>
        new(false, reason, null, null, null, prefix, []);
}

public interface IApiKeyValidator
{
    Task<ApiKeyValidationResult> ValidateAsync(string plaintextKey, CancellationToken ct);
}

public sealed class ApiKeyValidator(
    AppDbContext db,
    HybridCache cache,
    TimeProvider time) : IApiKeyValidator
{
    private static readonly TimeSpan CacheTtl = TimeSpan.FromMinutes(2);

    public async Task<ApiKeyValidationResult> ValidateAsync(
        string plaintextKey, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(plaintextKey))
            return ApiKeyValidationResult.Invalid("API key is empty.");

        var prefix = plaintextKey.Length >= 12 ? plaintextKey[..12] : plaintextKey;
        var hash = ApiKeyHasher.Hash(plaintextKey);

        // 用哈希作为缓存键，明文永远不进缓存
        var cached = await cache.GetOrCreateAsync(
            $"apikey:{hash}",
            async cancel => await LookupAsync(hash, cancel),
            new HybridCacheEntryOptions { Expiration = CacheTtl },
            cancellationToken: ct);

        if (cached is null)
            return ApiKeyValidationResult.Invalid("API key not found.", prefix);

        if (cached.RevokedAt is not null)
            return ApiKeyValidationResult.Invalid("API key has been revoked.", prefix);

        if (cached.ExpiresAt is { } exp && exp <= time.GetUtcNow())
            return ApiKeyValidationResult.Invalid("API key has expired.", prefix);

        // 异步更新最后使用时间，不阻塞请求
        _ = TouchLastUsedAsync(cached.Id);

        return new ApiKeyValidationResult(
            true, null, cached.Id, cached.Name, cached.OwnerId,
            cached.Prefix, cached.Scopes.Split(',', StringSplitOptions.RemoveEmptyEntries));
    }

    private async Task<ApiKey?> LookupAsync(string hash, CancellationToken ct)
        => await db.ApiKeys.AsNoTracking()
            .FirstOrDefaultAsync(k => k.KeyHash == hash, ct);

    private async Task TouchLastUsedAsync(Guid keyId)
    {
        try
        {
            await db.ApiKeys
                .Where(k => k.Id == keyId)
                .ExecuteUpdateAsync(s =>
                    s.SetProperty(k => k.LastUsedAt, time.GetUtcNow().UtcDateTime));
        }
        catch
        {
            // 遥测路径——不能因为审计失败而影响请求
        }
    }
}
```

两点值得注意：

- **缓存键是哈希，不是明文**：不让明文密钥在进程内存中停留超过必要时间，尤其在分布式缓存里可能通过 dump 或遥测泄漏。
- **`ExecuteUpdateAsync` 更新最后使用时间**：单条 SQL `UPDATE`，不加载实体，不追踪变更，无往返。异步触发即可——崩溃时丢失一个时间戳是可接受的，为写它而阻塞请求则不行。

### HybridCache 的延迟优势

HybridCache 是 .NET 9+ 的缓存原语，组合了内存（L1）和分布式（L2）缓存，内置防缓存击穿保护。对于 API key 验证，延迟数字很关键：

| 路径 | 典型延迟 | 估算吞吐量 |
|------|---------|-----------|
| 内存缓存命中（L1） | ~50 ns | ~20,000,000 ops/s |
| 分布式缓存命中（L2，本地 Redis） | ~500 µs | ~2,000 ops/s |
| 数据库查询（PostgreSQL，有索引） | ~1-3 ms | ~300-1,000 ops/s |

L1 命中比数据库查询快约 20,000 到 60,000 倍。任何有一定请求量的 API，热路径验证绝对不能每次都打数据库。

权衡是**撤销延迟**：TTL 2 分钟意味着撤销最多需要 2 分钟才能在所有实例上生效。对大多数应用来说可以接受。高安全场景可以把 TTL 降到 30 秒，或者对撤销密钥检查跳过 L1 缓存。

### 注册生产版本

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenApi();
builder.Services.AddDbContext<AppDbContext>(o =>
    o.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection")));

#pragma warning disable EXTEXP0018 // HybridCache 还在预览
builder.Services.AddHybridCache();
#pragma warning restore EXTEXP0018

builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddScoped<IApiKeyValidator, ApiKeyValidator>();

builder.Services
    .AddAuthentication(ApiKeyAuthenticationOptions.DefaultScheme)
    .AddScheme<ApiKeyAuthenticationOptions, ApiKeyAuthenticationHandler>(
        ApiKeyAuthenticationOptions.DefaultScheme, _ => { });

builder.Services.AddAuthorizationBuilder()
    .AddPolicy("keys:read", p => p.RequireClaim("scope", "keys:read"))
    .AddPolicy("keys:admin", p => p.RequireClaim("scope", "keys:admin"));

var app = builder.Build();

app.MapOpenApi();
app.MapScalarApiReference();
app.UseAuthentication();
app.UseAuthorization();

app.Run();
```

`AddAuthorizationBuilder` 是 .NET 8+ 的流式策略 API，比旧版 `AddAuthorization(o => o.AddPolicy(...))` 更简洁。`TimeProvider.System` 是生产实现，测试时替换为 `FakeTimeProvider`。

---

## 认证后授权：按密钥的权限范围

一个简单的 `[Authorize]` 只检查"调用方是否已认证"。真实 API 需要更细粒度的检查。权限范围已经作为 claims 嵌入，ASP.NET Core 策略系统自然处理：

```csharp
app.MapGet("/keys", async (AppDbContext db, CancellationToken ct) =>
        await db.ApiKeys.AsNoTracking().Select(k => new
        {
            k.Id, k.Prefix, k.Name, k.OwnerId, k.CreatedAt, k.ExpiresAt, k.LastUsedAt
        }).ToListAsync(ct))
   .RequireAuthorization("keys:read");

app.MapDelete("/keys/{id:guid}", async (
        Guid id, AppDbContext db, TimeProvider time, CancellationToken ct) =>
{
    var rows = await db.ApiKeys
        .Where(k => k.Id == id)
        .ExecuteUpdateAsync(s => s.SetProperty(k => k.RevokedAt, time.GetUtcNow().UtcDateTime), ct);
    return rows == 0 ? Results.NotFound() : Results.NoContent();
})
.RequireAuthorization("keys:admin");
```

带 `keys:read` 权限的密钥可以列出密钥，但不能撤销。带 `keys:admin` 的可以两者都做。颁发时把多个权限范围都加进逗号分隔的 `Scopes` 字段，就能一个密钥覆盖多个权限。

---

## 正确返回 401 / 403：RFC 9457 ProblemDetails

默认的 ASP.NET Core 401 响应是空响应体。对公共 API，需要机器可读的错误。RFC 9457 定义了标准 JSON 错误格式，ASP.NET Core 有内置支持。

**状态码区别很重要**：
- **401 Unauthorized**：不知道你是谁——没有密钥，或密钥无效
- **403 Forbidden**：知道你是谁，但你没有权限做这件事——密钥有效但缺少所需权限范围

```csharp
// 在 Program.cs 中注册全局 ProblemDetails 写入器
builder.Services.AddProblemDetails();

// 在 handler 中重写 HandleChallengeAsync (401) 和 HandleForbiddenAsync (403)
protected override async Task HandleChallengeAsync(AuthenticationProperties properties)
{
    Response.StatusCode = StatusCodes.Status401Unauthorized;
    Response.ContentType = "application/problem+json";

    var problemDetailsService = Context.RequestServices
        .GetRequiredService<IProblemDetailsService>();

    await problemDetailsService.WriteAsync(new ProblemDetailsContext
    {
        HttpContext = Context,
        ProblemDetails = new ProblemDetails
        {
            Status = StatusCodes.Status401Unauthorized,
            Title = "Unauthorized",
            Detail = "A valid API key is required. Send it in the X-API-Key header.",
            Type = "https://tools.ietf.org/html/rfc9110#section-15.5.2"
        }
    });
}
```

无密钥的请求现在返回：

```json
{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.2",
  "title": "Unauthorized",
  "status": 401,
  "detail": "A valid API key is required. Send it in the X-API-Key header."
}
```

---

## 在 OpenAPI 3.1 + Scalar 中文档化认证方案

ASP.NET Core .NET 10 内置 OpenAPI 3.1 生成（无需 Swashbuckle）。要让 Scalar UI 渲染 `X-API-Key` 请求头的 Authorize 按钮，添加文档转换器注册安全方案：

```csharp
using Microsoft.AspNetCore.OpenApi;
using Microsoft.OpenApi;

internal sealed class ApiKeySecuritySchemeTransformer : IOpenApiDocumentTransformer
{
    public Task TransformAsync(
        OpenApiDocument document,
        OpenApiDocumentTransformerContext context,
        CancellationToken cancellationToken)
    {
        var schemes = new Dictionary<string, IOpenApiSecurityScheme>
        {
            ["ApiKey"] = new OpenApiSecurityScheme
            {
                Type = SecuritySchemeType.ApiKey,
                Name = ApiKeyAuthenticationOptions.HeaderName,
                In = ParameterLocation.Header,
                Description = "API key sent in the X-API-Key header."
            }
        };

        document.Components ??= new OpenApiComponents();
        document.Components.SecuritySchemes = schemes;

        if (document.Paths is null) return Task.CompletedTask;

        foreach (var operation in document.Paths.Values.SelectMany(path => path.Operations ?? []))
        {
            operation.Value.Security ??= [];
            operation.Value.Security.Add(new OpenApiSecurityRequirement
            {
                [new OpenApiSecuritySchemeReference("ApiKey", document)] = []
            });
        }

        return Task.CompletedTask;
    }
}

// 在 Program.cs 中注册
builder.Services.AddOpenApi(options =>
{
    options.AddDocumentTransformer<ApiKeySecuritySchemeTransformer>();
});
```

> **注意**：`Microsoft.OpenApi 2.x`（随 `Microsoft.AspNetCore.OpenApi 10.0` 一同发布）将类型重组到根命名空间 `Microsoft.OpenApi`，并从 `OpenApiSecurityScheme` 中移除了 `Reference` 属性。引用现在通过专用引用类型如 `OpenApiSecuritySchemeReference` 处理。如果你在跟着旧版指南使用 `Microsoft.OpenApi.Models` 和 `OpenApiReference`，那是 .NET 9 的模式——上面的代码是 .NET 10 等价写法。

Scalar 现在会渲染 Authorize 按钮，用户粘贴一次密钥后，后续所有"Try it"调用都自动带上 `X-API-Key` 请求头。

---

## 审计日志

数据库支持密钥的全部意义在于能回答"凌晨三点是谁调用了 API"和"这个密钥还在用吗"这样的问题。

用 Serilog 请求日志加一个富集器，从 principal 里取出密钥前缀和 ID：

```csharp
app.UseSerilogRequestLogging(options =>
{
    options.EnrichDiagnosticContext = (ctx, http) =>
    {
        if (http.User.Identity?.IsAuthenticated == true)
        {
            ctx.Set("ApiKeyPrefix", http.User.FindFirst("api_key_prefix")?.Value);
            ctx.Set("ClientId", http.User.FindFirst("client_id")?.Value);
        }
    };
});
```

每条请求日志现在都包含 `ApiKeyPrefix` 和 `ClientId`。前缀可以安全写日志（不是秘密），完整密钥绝对不进日志。如果客户端说"我们在 09:42 UTC 收到了 403"，搜索 `ApiKeyPrefix = sk_live_3K7s` 就能找到对应的请求。

---

## 密钥轮换：不停机替换

API key 长期有效，但"长期"不应该意味着"从不替换"。应该按计划轮换（高敏感场景 90 天，合作方集成 1 年），以及在每次凭证暴露时轮换（员工离职、密钥出现在截图里等）。

**宽限期轮换流程**：

1. 为同一个 `OwnerId` 颁发新密钥，同样的权限范围。两个密钥现在都有效。
2. 把新密钥交给客户端，他们开始使用。
3. 等客户端确认迁移完成（手动确认，或审计日志里几百次成功调用）。
4. 通过设置 `RevokedAt` 撤销旧密钥。
5. 观察失败——仍在使用旧密钥的客户端会在缓存 TTL 窗口内收到 401。

这正是 Stripe 处理密钥轮换的方式。数据模型已经支持——`ApiKey` 里没有任何东西说一个客户端只能有一个密钥，颁发多少都可以，单独撤销。

---

## 生产常见错误

这些是每个团队的代码评审中都会出现的模式：

1. **把密钥存在 `appsettings.json` 里并提交**：密钥上 Pastebin 的头号路径。用环境变量、user-secrets 或密钥管理器（Azure Key Vault、AWS Secrets Manager）。
2. **数据库存明文密钥**：数据库 dump 泄漏即等于凭证泄漏。全部哈希。
3. **用 `string.Equals` 比较**：时序攻击。用 `CryptographicOperations.FixedTimeEquals`。
4. **把完整密钥写入日志**：即使是 `Debug` 级别，即使在错误消息里。前缀是安全的，其余是秘密。如果必须调试，做脱敏处理：`sk_live_3K7s********************`。
5. **把密钥放在 URL 里**：查询字符串会进访问日志、浏览器历史和 CDN 缓存。永远用请求头。
6. **不设过期时间**：没有过期时间的密钥会老化腐烂。哪怕是"永久"密钥也要设 TTL——1 年是个好默认值。
7. **不轮换**：即使做了哈希，一个存活 5 年的密钥有 5 年的时间可能已经泄漏。按计划轮换。
8. **`AddAuthentication()` 不指定默认方案**：同时注册 JWT 时，`Authorization: Bearer ...` 请求可能走错方案。要明确指定。
9. **HybridCache 里缓存明文密钥**：用哈希作为缓存键。明文只在请求中存在，然后消失。
10. **不分别测试 401 和 403**：大多数团队只测"成功路径 + 无效密钥"，漏掉"有效密钥但权限不足"——这是独立的 bug 类型。

---

## 生产发布清单

发布前逐项确认：

- [ ] 密钥至少 128 bits 熵（推荐 256 bits），使用 `RandomNumberGenerator` 生成
- [ ] 明文密钥在颁发时只向客户端展示一次
- [ ] 数据库只存 SHA-256 哈希，不存明文
- [ ] 比较使用 `CryptographicOperations.FixedTimeEquals`
- [ ] 密钥有标识类型的前缀（`sk_live_`、`sk_test_`）
- [ ] 密钥有 `ExpiresAt`（哪怕是 1 年后）
- [ ] 密钥可以不重新部署地撤销（`RevokedAt` 标记）
- [ ] 验证通过 HybridCache，TTL 30-300 秒，根据撤销延迟容忍度选择
- [ ] 认证失败返回 HTTP 401，权限不足返回 HTTP 403，都用 ProblemDetails（RFC 9457）
- [ ] OpenAPI 文档包含 `apiKey` 安全方案，Scalar/Swagger UI 显示 Authorize 按钮
- [ ] 每次请求日志包含 `ApiKeyPrefix` 和 `ClientId`，不包含明文
- [ ] 密钥轮换流程已文档化并测试
- [ ] HTTPS 已强制（`UseHttpsRedirection` + HSTS）；HTTP 请求被拒绝

---

## 关键结论

- 用 `AuthenticationHandler<TOptions>`，不用纯中间件或纯 filter。这是唯一与 `[Authorize]`、OpenAPI 和 ASP.NET Core 认证管道完整集成的方案。
- 数据库存 SHA-256 哈希。慢哈希（Argon2id、PBKDF2）对高熵随机密钥毫无收益，反而会拖累验证吞吐量。
- 始终用 `CryptographicOperations.FixedTimeEquals`——字符串比较上的时序攻击在公网暴露的 API 上是真实风险。
- 用前缀约定（`sk_live_…`），泄漏的密钥可以被扫描识别，前缀可以安全写日志。
- 用 HybridCache 缓存验证结果。L1 命中比数据库查询快约 20,000 到 60,000 倍——有一定请求量的 API，热路径绝对不能每次打数据库。
- 为 401 和 403 返回 RFC 9457 ProblemDetails，明确区分状态码——401 表示无密钥或无效密钥，403 表示密钥有效但缺少权限范围。

完整源码（包含 xUnit v3 集成测试套件，使用 `WebApplicationFactory` 和 `FakeTimeProvider` 做确定性过期测试）在 [GitHub 课程仓库](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/05-api-security/api-key-authentication-aspnet-core) 里。Demo 使用 EF Core 内存提供器，克隆后 `dotnet run` 即可运行，无需配置数据库。

---

## 参考

- [原文：API Key Authentication in ASP.NET Core (.NET 10) - Complete Guide](https://codewithmukesh.com/blog/api-key-authentication-aspnet-core/)
- [HybridCache in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/performance/caching/hybrid)
- [RFC 9457 - Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc9457)
- [CryptographicOperations.FixedTimeEquals](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.cryptographicoperations.fixedtimeequals)
- [CA1850 analyzer](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1850)
- [完整示例源码](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/05-api-security/api-key-authentication-aspnet-core)
