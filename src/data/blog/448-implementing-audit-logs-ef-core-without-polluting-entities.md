---
pubDatetime: 2025-08-26
tags: ["EF Core", "审计日志", "ASP.NET Core", ".NET", "数据库设计"]
slug: implementing-audit-logs-ef-core-without-polluting-entities
source: https://blog.elmah.io/implementing-audit-logs-in-ef-core-without-polluting-your-entities/
title: 在 EF Core 中实现审计日志，无需污染实体
description: 学习如何在 Entity Framework Core 项目中优雅地实现动态审计日志功能，追踪数据变更的完整历史记录，同时保持代码的整洁性。
---

# 在 EF Core 中实现审计日志，无需污染实体

现代应用程序大多都需要对数据库实体的历史变更进行审计日志记录。审计日志为您提供了所有变更的洞察，包括时间戳和负责这些变更的用户。这些日志确保了透明度，允许利益相关者观察到对业务关键数据做了什么变更、何时做的变更以及谁做的变更。此外，许多监管合规要求应用程序维护历史轨迹。今天，我将向您展示如何在 Entity Framework Core (EF Core) 项目中优雅而动态地添加审计日志。

![实现审计日志](https://blog.elmah.io/content/images/2025/07/implementing-audit-logs-in-ef-core-without-polluting-your-entities-o-1.png)

## 什么是审计日志？

审计日志（或审计轨迹）是业务活动和事件的详细、按时间顺序的记录。这些历史数据对于维护可见性、增强调试、满足合规性和确保问责制至关重要。

审计轨迹对以下方面是必要的：

### 符合行业法规

诸如 CIS、DSS、SOC 2 和 PCI 等法规通常要求强大的审计日志记录。为了满足这些合规标准，公司必须实施详细的日志记录作为关键要求。

### 识别和修复错误

审计轨迹包含有关每个事务的详细信息，清楚地识别哪些值被更改以及何时发生。这样的信息有助于确定数据在何处被错误更新或变得不一致。例如，如果学生抱怨他们在学校系统中的基本信息不正确，管理员可以追踪谁插入了错误数据以及何时发生的。

### 保持数据完整性

日志还作为意外更改的恢复机制，有助于维护系统可靠性。

### 通过审计洞察增强安全性

审查审计日志使组织能够详细检查谁做了什么、如何做以及何时做。他们可以轻松地指出任何未经授权的访问、可疑模式或特权滥用。这一活动提供了当前设置中的差距和风险的清晰图像，并推荐新的安全程序。

## 在 EF Core 中实现审计日志

在了解了日志的重要性之后，让我们探索如何将它们添加到基于 EF Core 的项目中。我将使用以 PostgreSQL 为数据源的 ASP.NET Core API 示例。该项目代表一个连接申请人、招聘公司和职位发布的求职门户。

### 步骤 1：创建项目

```bash
dotnet new webapi -n JobAppApi
cd JobAppApi
```

### 步骤 2：安装必要的 NuGet 包

```bash
dotnet add package Microsoft.EntityFrameworkCore
dotnet add package Npgsql.EntityFrameworkCore.PostgreSQL
dotnet add package Microsoft.EntityFrameworkCore.Design
dotnet add package Microsoft.AspNetCore.Authentication.JwtBearer
```

### 步骤 3：定义基础可审计接口

```csharp
public interface IAuditableEntity
{
    DateTimeOffset CreatedAtUtc { get; set; }
    DateTimeOffset? UpdatedAtUtc { get; set; }
    string CreatedBy { get; set; }
    string? UpdatedBy { get; set; }
}
```

这些属性需要在此接口的所有实现中存在。虽然您可以争论这实际上污染了实体，因此与本文的标题冲突，但许多公司无论如何都在所有实体上都有这些属性。如果您希望不在所有实体上都有属性并且仍然让审计日志工作，您可以查看 EF Core 的影子属性功能。

### 步骤 4：定义数据模型

**Applicant** 代表求职候选人：

```csharp
public class Applicant : IAuditableEntity
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Skill { get; set; } = string.Empty;
    public Guid UserId { get; set; }

    public DateTimeOffset CreatedAtUtc { get; set; }
    public DateTimeOffset? UpdatedAtUtc { get; set; }
    public string CreatedBy { get; set; } = null!;
    public string? UpdatedBy { get; set; }

    [ForeignKey(nameof(UserId))]
    public virtual User User { get; set; }
}
```

**Company** 模型创建职位发布：

```csharp
public class Company: IAuditableEntity
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Industry { get; set; } = string.Empty;
    public Guid UserId { get; set; }

    public DateTimeOffset CreatedAtUtc { get; set; }
    public DateTimeOffset? UpdatedAtUtc { get; set; }
    public string CreatedBy { get; set; } = null!;
    public string? UpdatedBy { get; set; }

    [ForeignKey(nameof(UserId))]
    public virtual User User { get; set; }
}
```

**JobPost** 代表职位：

```csharp
public class JobPost : IAuditableEntity
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Title { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public Guid CompanyId { get; set; }
    public Company Company { get; set; } = null!;

    public DateTimeOffset CreatedAtUtc { get; set; }
    public DateTimeOffset? UpdatedAtUtc { get; set; }
    public string CreatedBy { get; set; } = null!;
    public string? UpdatedBy { get; set; }
}
```

通用 **User** 用于登录：

```csharp
public class User: IAuditableEntity
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Name { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;

    public DateTimeOffset CreatedAtUtc { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? UpdatedAtUtc { get; set; }
    public string CreatedBy { get; set; } = null!;
    public string? UpdatedBy { get; set; }

    public virtual ICollection<Applicant> Applicants { get; set; }
    public virtual ICollection<Company> Companies { get; set; }
}
```

> **注意**：在本文中，我们将以明文形式存储用户密码。在真实系统中，您永远不应该这样做。由于本文已经相当长，我决定为了简单起见这样做。始终使用经过验证的算法（如 PBKDF2、bcrypt 或 ASP.NET Core 的 `PasswordHasher<TUser>`）对密码进行哈希和加盐。

### 步骤 5：配置数据库上下文

```csharp
public class ApplicationDbContext: DbContext
{
    public DbSet<Applicant> Applicants => Set<Applicant>();
    public DbSet<Company> Companies => Set<Company>();
    public DbSet<JobPost> JobPosts => Set<JobPost>();
    public DbSet<User> Users => Set<User>();

    public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options) : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ApplicationDbContext).Assembly);
    }
}
```

### 步骤 6：实现审计枚举和类

```csharp
public enum TrailType : byte
{
    None = 0,
    Create = 1,
    Update = 2,
    Delete = 3
}
```

**AuditTrail** 模型：

```csharp
public class AuditTrail
{
    public Guid Id { get; set; }
    public Guid? UserId { get; set; }
    public string EntityName { get; set; } = null!;
    public string? PrimaryKey { get; set; }
    public TrailType TrailType { get; set; }
    public DateTimeOffset DateUtc { get; set; }

    public Dictionary<string, object?> OldValues { get; set; } = [];
    public Dictionary<string, object?> NewValues { get; set; } = [];
    public List<string> ChangedColumns { get; set; } = [];
}
```

配置 `AuditTrail` 到 `DbContext`：

```csharp
public class AuditTrailConfiguration : IEntityTypeConfiguration<AuditTrail>
{
    public void Configure(EntityTypeBuilder<AuditTrail> builder)
    {
        builder.ToTable("audit_trails");
        builder.HasKey(e => e.Id);
        builder.HasIndex(e => e.EntityName);

        builder.Property(e => e.Id);
        builder.Property(e => e.UserId);
        builder.Property(e => e.EntityName).HasMaxLength(100).IsRequired();
        builder.Property(e => e.PrimaryKey).HasMaxLength(100);
        builder.Property(e => e.DateUtc).IsRequired();
        builder.Property(e => e.TrailType).HasConversion<string>();

        builder.Property(e => e.OldValues).HasColumnType("jsonb");
        builder.Property(e => e.NewValues).HasColumnType("jsonb");
        builder.Property(e => e.ChangedColumns).HasColumnType("jsonb");
    }
}
```

### 步骤 7：重写 DbContext 的默认 SaveChangesAsync 方法

修改 `SaveChangesAsync` 以集成每个创建、更新和删除操作的审计轨迹创建：

```csharp
public override async Task<int> SaveChangesAsync(CancellationToken cancellationToken = default)
{
    var userId = _sessionProvider.GetUserId();

    SetAuditableProperties(userId);
    var auditEntries = HandleAuditingBeforeSaveChanges(userId);

    if (auditEntries.Any())
        await AuditTrails.AddRangeAsync(auditEntries, cancellationToken);

    return await base.SaveChangesAsync(cancellationToken);
}

private void SetAuditableProperties(Guid? userId)
{
    const string system = "system";
    foreach (var entry in ChangeTracker.Entries<IAuditableEntity>())
    {
        if (entry.State == EntityState.Added)
        {
            entry.Entity.CreatedAtUtc = DateTimeOffset.UtcNow;
            entry.Entity.CreatedBy = userId?.ToString() ?? system;
        }
        else if (entry.State == EntityState.Modified)
        {
            entry.Entity.UpdatedAtUtc = DateTimeOffset.UtcNow;
            entry.Entity.UpdatedBy = userId?.ToString() ?? system;
        }
    }
}

private List<AuditTrail> HandleAuditingBeforeSaveChanges(Guid? userId)
{
    var entries = ChangeTracker.Entries<IAuditableEntity>()
        .Where(e => e.State == EntityState.Added || e.State == EntityState.Modified || e.State == EntityState.Deleted);

    var auditTrails = new List<AuditTrail>();

    foreach (var entry in entries)
    {
        var audit = new AuditTrail
        {
            Id = Guid.NewGuid(),
            UserId = userId,
            EntityName = entry.Entity.GetType().Name,
            DateUtc = DateTimeOffset.UtcNow
        };

        foreach (var prop in entry.Properties)
        {
            if (prop.Metadata.IsPrimaryKey())
            {
                audit.PrimaryKey = prop.CurrentValue?.ToString();
                continue;
            }

            if (prop.Metadata.Name.Equals("PasswordHash")) continue;

            var name = prop.Metadata.Name;

            switch (entry.State)
            {
                case EntityState.Added:
                    audit.TrailType = TrailType.Create;
                    audit.NewValues[name] = prop.CurrentValue;
                    break;
                case EntityState.Deleted:
                    audit.TrailType = TrailType.Delete;
                    audit.OldValues[name] = prop.OriginalValue;
                    break;
                case EntityState.Modified:
                    if (!Equals(prop.OriginalValue, prop.CurrentValue))
                    {
                        audit.TrailType = TrailType.Update;
                        audit.ChangedColumns.Add(name);
                        audit.OldValues[name] = prop.OriginalValue;
                        audit.NewValues[name] = prop.CurrentValue;
                    }
                    break;
            }
        }

        if (audit.TrailType != TrailType.None)
            auditTrails.Add(audit);
    }

    return auditTrails;
}
```

### 步骤 8：配置用户会话提供者

定义接口和类以从 `HttpContextAccessor` 获取 `UserId`：

```csharp
public interface ICurrentSessionProvider
{
    Guid? GetUserId();
}

public class CurrentSessionProvider: ICurrentSessionProvider
{
    private readonly Guid? _currentUserId;

    public CurrentSessionProvider(IHttpContextAccessor accessor)
    {
        var userId = accessor.HttpContext?.User.FindFirstValue(ClaimTypes.NameIdentifier);
        if (Guid.TryParse(userId, out var id))
            _currentUserId = id;
    }

    public Guid? GetUserId() => _currentUserId;
}
```

在 `Program.cs` 中注册新服务：

```csharp
builder.Services.AddHttpContextAccessor();
builder.Services.AddScoped<ICurrentSessionProvider, CurrentSessionProvider>();
```

### 步骤 9：配置 JWT 认证

在 `appsettings.json` 中配置 JWT 值：

```json
"JwtSettings":
{
    "SecretKey": "this_is_super_secret_key_please_change_it",
    "Issuer": "yourapp.com",
    "Audience": "yourapp.com",
    "ExpiryMinutes": 60
}
```

添加 `JwtSettings` 模型：

```csharp
public class JwtSettings
{
    public string SecretKey { get; set; } = string.Empty;
    public string Issuer { get; set; } = string.Empty;
    public string Audience { get; set; } = string.Empty;
    public int ExpiryMinutes { get; set; }
}
```

在 `Program.cs` 中注入 JWT 授权：

```csharp
var jwtSettings = builder.Configuration.GetSection("JwtSettings");
builder.Services.Configure<JwtSettings>(jwtSettings);
var secretKey = jwtSettings["SecretKey"]!;
var key = Encoding.ASCII.GetBytes(secretKey);

builder.Services.AddAuthentication(options =>
{
    options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
    options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
})
.AddJwtBearer(options =>
{
    options.RequireHttpsMetadata = false;
    options.SaveToken = true;
    options.TokenValidationParameters = new TokenValidationParameters
    {
        ValidateIssuer = true,
        ValidateAudience = true,
        ValidateLifetime = true,
        ValidateIssuerSigningKey = true,
        ValidIssuer = jwtSettings["Issuer"],
        ValidAudience = jwtSettings["Audience"],
        IssuerSigningKey = new SymmetricSecurityKey(key)
    };
});
```

## 测试和验证

该解决方案提供了完整的审计日志功能，可以追踪：

1. **创建操作**：记录新实体的所有属性值
2. **更新操作**：记录更改的字段及其旧值和新值
3. **删除操作**：记录被删除实体的所有属性值
4. **用户追踪**：通过 JWT 令牌识别执行操作的用户

审计轨迹存储在独立的 `audit_trails` 表中，使用 JSONB 列存储旧值、新值和更改的列，提供了灵活且高效的存储方案。

## 合规性考虑

在实际生产环境中，需要注意以下合规性问题：

1. **密码安全**：绝不应以明文形式存储密码
2. **PII 数据**：审计日志可能包含个人身份信息，需要符合 GDPR、HIPAA 等法规
3. **数据脱敏**：可以引入 `AuditIgnore` 属性来保持某些信息不被记录到审计表中

## 结论

审计日志是任何应用程序的关键方面，既有法律目的也有技术目的。它使公司能够查看何时以及对应用程序进行了哪些更改，以及谁进行了这些更改。这些洞察不仅有助于调试，还有助于识别系统安全和授权方面的不足。此外，许多法律机构（如 CIS 和 DSS）都包括详细的日志记录要求。

这个解决方案提供了一个在基于 EF Core 的项目中实现日志记录的分步解决方案，利用了 API 项目。通过重写 `SaveChangesAsync` 方法，我们能够自动拦截所有数据更改并创建相应的审计记录，而无需在业务逻辑中添加额外的代码。

这种方法的主要优势包括：

- **自动化**：无需手动编写审计代码
- **一致性**：所有实体变更都会被统一记录
- **灵活性**：支持复杂的数据类型和 JSON 存储
- **性能**：使用 JSONB 提供高效的查询能力
- **可扩展性**：易于添加新的审计功能和过滤规则

通过这种方式，开发团队可以专注于业务逻辑的实现，而审计功能会在后台自动运行，确保所有重要的数据变更都得到适当的记录和追踪。
