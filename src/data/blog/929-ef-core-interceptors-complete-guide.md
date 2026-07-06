---
pubDatetime: 2026-07-06T20:24:07+08:00
title: "EF Core Interceptors 完全指南：审计字段、软删除和慢查询日志"
description: "详解 EF Core 10 的 7 种 Interceptor 类型，从 SaveChangesInterceptor 自动填充审计字段，到 DbCommandInterceptor 捕获慢查询，再到作用域服务注入的正确方式和常见陷阱。"
tags:
  [
    "EF Core",
    "Entity Framework Core",
    "Interceptor",
    "Audit Logging",
    "Soft Delete",
    ".NET 10",
    "Dependency Injection",
  ]
slug: "ef-core-interceptors-complete-guide"
source: "https://codewithmukesh.com/blog/ef-core-interceptors/"
ogImage: "../../assets/929/01-cover.png"
---

EF Core 的 Interceptor 是“数据库调用的中间件”——它挂在 EF Core 的执行管线里，可以在 `SaveChanges` 之前自动填充审计字段、在 SQL 执行之后标记慢查询、甚至直接拦截并取消某个操作。

这篇文章覆盖 EF Core 10 的 7 种 Interceptor 接口、注册方式、最常见的审计字段和软删除实现、作用域服务注入的正确姿势，以及容易被忽略的几个坑。完整代码已在作者 GitHub 上可运行。

## Interceptor 是什么

每次 EF Core 做一件有意义的事——打开连接、构建 SQL、执行 `SaveChanges`——它都给已注册的 Interceptor 一个机会，在操作之前和之后运行你的代码。

和普通日志不同的是，Interceptor **可以改变结果**。日志只能观察；Interceptor 可以修改 SQL、取消命令、替换 EF Core 看到的结果、或者吞掉异常。这种能力让它们成为横切数据库关注点的天然工具，但也意味着用之前要想清楚。

一个 Interceptor 运行在基础设施层，低于业务逻辑。它会在每一次 `SaveChanges` 时触发——不管调用来自 Controller、后台任务还是单元测试。这对审计字段是正确的行为，但对只应该在特定场景下触发的业务规则来说是错误的选择。

## EF Core 10 的 7 种 Interceptor

| Interceptor                      | 挂载点                  | 典型场景                               |
| -------------------------------- | ----------------------- | -------------------------------------- |
| `ISaveChangesInterceptor`        | `SaveChanges` 前后      | 审计字段、软删除、领域事件、发件箱模式 |
| `IDbCommandInterceptor`          | SQL 命令执行前后        | 慢查询日志、添加 Query Hint、修改 SQL  |
| `IDbConnectionInterceptor`       | 连接打开和关闭          | 按租户切换连接串、获取 Access Token    |
| `IDbTransactionInterceptor`      | Begin、Commit、Rollback | 自定义事务日志                         |
| `IMaterializationInterceptor`    | 查询结果构造实体实例    | 设置非映射属性、向实体注入服务         |
| `IQueryExpressionInterceptor`    | LINQ 表达式树编译前     | 向所有查询注入排序或过滤               |
| `IIdentityResolutionInterceptor` | 跟踪实体主键冲突        | 合并两个同主键的已跟踪实例             |

几个关键的实现细节：

- **命令、连接、事务拦截器只对关系型数据库有效**，InMemory Provider 不触发。
- `IMaterializationInterceptor`、`IQueryExpressionInterceptor`、`IIdentityResolutionInterceptor` 实现了 `ISingletonInterceptor`——EF Core 在所有 DbContext 间共享同一实例，所以必须无状态且线程安全。
- 前四种有内置的 no-op 基类（`SaveChangesInterceptor`、`DbCommandInterceptor` 等），继承基类只需覆写你关心的一个或两个方法。后三种没有基类，直接实现接口。

## 注册 Interceptor

在 `OnConfiguring` 中注册：

```csharp
public class AppDbContext : DbContext
{
    private static readonly SlowQueryInterceptor _slowQuery = new();

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
        => optionsBuilder.AddInterceptors(_slowQuery);
}
```

对无状态的 Interceptor 用 `static readonly` 单例，避免每次创建新实例。

在 ASP.NET Core 中用 `AddDbContext` 注册：

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connStr).AddInterceptors(new SlowQueryInterceptor()));
```

一个有用的细节：即使你用了 `AddDbContext`，`OnConfiguring` 仍然会执行，两者都会被调用。所以 `OnConfiguring` 适合放“无论上下文怎么构建都要生效”的配置，包括 Migration 时 Design-Time Factory 创建的上下文。

## 审计字段：SaveChangesInterceptor

这是 Interceptor 最常见的用途——每个实体自动填上 `CreatedAtUtc`、`UpdatedAtUtc`、`CreatedBy`、`UpdatedBy`，不需要在每个 Handler 里手动写。

先定义两个标记接口：

```csharp
public interface IAuditable
{
    DateTime CreatedAtUtc { get; set; }
    string? CreatedBy { get; set; }
    DateTime? UpdatedAtUtc { get; set; }
    string? UpdatedBy { get; set; }
}

public interface ISoftDeletable
{
    bool IsDeleted { get; set; }
    DateTime? DeletedAtUtc { get; set; }
}
```

Interceptor 继承 `SaveChangesInterceptor`，覆写 `SavingChanges` 和 `SavingChangesAsync`：

```csharp
public sealed class AuditableInterceptor(ICurrentUser currentUser)
    : SaveChangesInterceptor
{
    public override InterceptionResult<int> SavingChanges(
        DbContextEventData eventData, InterceptionResult<int> result)
    {
        ApplyAudit(eventData.Context);
        return base.SavingChanges(eventData, result);
    }

    public override ValueTask<InterceptionResult<int>> SavingChangesAsync(
        DbContextEventData eventData, InterceptionResult<int> result,
        CancellationToken ct = default)
    {
        ApplyAudit(eventData.Context);
        return base.SavingChangesAsync(eventData, result, ct);
    }

    private void ApplyAudit(DbContext? context)
    {
        if (context is null) return;
        context.ChangeTracker.DetectChanges();
        var now = DateTime.UtcNow;
        var user = currentUser.UserId ?? "system";

        foreach (var entry in context.ChangeTracker.Entries<IAuditable>())
        {
            if (entry.State == EntityState.Added)
            {
                entry.Entity.CreatedAtUtc = now;
                entry.Entity.CreatedBy = user;
            }
            else if (entry.State == EntityState.Modified)
            {
                entry.Entity.UpdatedAtUtc = now;
                entry.Entity.UpdatedBy = user;
            }
        }

        foreach (var entry in context.ChangeTracker.Entries<ISoftDeletable>())
        {
            if (entry.State == EntityState.Deleted)
            {
                entry.State = EntityState.Modified;
                entry.Entity.IsDeleted = true;
                entry.Entity.DeletedAtUtc = now;
            }
        }
    }
}
```

第二层循环是软删除：当实体被标记为 `Deleted` 时，把状态改回 `Modified` 并设置 `IsDeleted = true`。EF Core 会发 `UPDATE` 而不是 `DELETE`，行留在表里。

记得在 `OnModelCreating` 中配全局查询过滤器隐藏已删除行：

```csharp
modelBuilder.Entity<Product>().HasQueryFilter(p => !p.IsDeleted);
```

### 为什么必须同时覆写同步和异步方法

很多人只覆写了 `SavingChangesAsync`，然后某个代码路径调了同步的 `SaveChanges()`——审计字段静默丢失，没有任何错误。EF Core 调用的是你没覆写的方法，也就是基类的空操作。规则：要么两个都覆写，要么明确禁止其中一种并抛出异常。

## 注入当前用户（作用域服务）

`AuditableInterceptor` 需要 `ICurrentUser`——一个从 HTTP 请求中读取当前用户的**作用域服务**。Interceptors 和作用域服务不会自动配合。

**错误做法**（大量博客文章会这样写）：

```csharp
// 错误——单例 Interceptor 不能依赖作用域服务
builder.Services.AddSingleton<AuditableInterceptor>();
```

单例创建一次永久存活，无法持有每次请求不同的 `ICurrentUser`。

**正确做法**：把 Interceptor 注册为 Scoped，然后通过 `AddDbContext` 的 `(sp, options)` 重载解析：

```csharp
builder.Services.AddHttpContextAccessor();
builder.Services.AddScoped<ICurrentUser, CurrentUser>();
builder.Services.AddScoped<AuditableInterceptor>();

builder.Services.AddDbContext<AppDbContext>((sp, options) =>
    options.UseNpgsql(connStr)
        .AddInterceptors(sp.GetRequiredService<AuditableInterceptor>()));
```

因为 `AddDbContext` 把上下文和 options 注册为 Scoped，这个 lambda 每次请求用请求自己的 `IServiceProvider` 执行，所以 `GetRequiredService` 返回的 Interceptor 携带了当前请求的 `ICurrentUser`。生命周期对齐。

`ICurrentUser` 实现本身很普通：

```csharp
public sealed class CurrentUser(IHttpContextAccessor accessor) : ICurrentUser
{
    public string? UserId =>
        accessor.HttpContext?.User.FindFirstValue(ClaimTypes.NameIdentifier);
}
```

注意：如果用了 `AddDbContextPool` 而不是 `AddDbContext`，Options 只构建一次并在池中共享，Scoped 的 Interceptor 无法按请求解析。用 Pooling 时保持 Interceptor 无状态，在方法内部通过 `eventData.Context` 获取作用域服务。

## 慢查询日志：DbCommandInterceptor

`DbCommandInterceptor` 工作在 SQL 层面，适合做诊断。`CommandExecutedEventData` 携带了 `Duration`：

```csharp
public sealed class SlowQueryInterceptor(
    ILogger<SlowQueryInterceptor> logger)
    : DbCommandInterceptor
{
    private const int SlowThresholdMs = 500;

    public override DbDataReader ReaderExecuted(
        DbCommand command,
        CommandExecutedEventData eventData,
        DbDataReader result)
    {
        Log(command, eventData);
        return base.ReaderExecuted(command, eventData, result);
    }

    public override ValueTask<DbDataReader> ReaderExecutedAsync(
        DbCommand command,
        CommandExecutedEventData eventData,
        DbDataReader result,
        CancellationToken ct = default)
    {
        Log(command, eventData);
        return base.ReaderExecutedAsync(command, eventData, result, ct);
    }

    private void Log(DbCommand cmd, CommandExecutedEventData data)
    {
        if (data.Duration.TotalMilliseconds >= SlowThresholdMs)
        {
            logger.LogWarning(
                "Slow query {ElapsedMs}ms: {Sql}",
                data.Duration.TotalMilliseconds, cmd.CommandText);
        }
    }
}
```

超过 500ms 的查询会自动出现在日志里，带 SQL 和耗时。这比等用户抱怨页面慢快得多。

## 取消操作：InterceptionResult.Suppress()

每个拦截方法返回 `InterceptionResult`。原样返回则 EF Core 正常执行，但你可以调 `Suppress()` 告诉 EF Core 停下。

一个实用例子是消除删除时的并发异常。两个请求几乎同时删除同一行，第二个请求会报并发冲突——但行已被删了，最终状态正确：

```csharp
public InterceptionResult ThrowingConcurrencyException(
    ConcurrencyExceptionEventData eventData,
    InterceptionResult result)
{
    if (eventData.Entries.All(e => e.State == EntityState.Deleted))
        return InterceptionResult.Suppress();
    return result;
}
```

还有一个兄弟方法 `SuppressWithResult`，它取消操作并给 EF Core 返回一个你提供的替代结果。

## 什么时候不该用 Interceptor

| 你想做             | 正确工具                | 为什么不用 Interceptor      |
| ------------------ | ----------------------- | --------------------------- |
| 打审计字段         | SaveChangesInterceptor  | 这就是标准场景              |
| 软删除             | SaveChangesInterceptor  | 标准场景，配 Query Filter   |
| 隐藏已删除行       | 全局查询过滤器          | Interceptor 管写不管读      |
| 保存后发邮件/事件  | Domain Events / MediatR | 业务逻辑不属于基础设施层    |
| 按租户过滤查询     | 全局查询过滤器          | 比改表达式树简单安全        |
| 校验请求或整形响应 | Middleware 或 Filter    | Interceptor 永远看不到 HTTP |
| 慢查询日志         | DbCommandInterceptor    | 标准场景                    |

30 秒决策法则：只有在行为是横切的、位于基础设施层（不是业务规则）、且必须对每次保存或命令都触发时，才用 Interceptor。审计字段三项全满足。“注册后发欢迎邮件”三项全不满足。

## 容易踩的坑

- **Interceptor 在热路径中运行**。不要在内部发网络请求或调外部服务，数据库操作在等你。
- **共享实例必须线程安全**。一个 Interceptor 实例可能同时服务多个 DbContext。保持无状态。
- **读 ChangeTracker 前先调 DetectChanges()**。即使自动检测开着，显式调用也确保被改了字段但未标记的实体能被正确处理。
- **ExecuteUpdate/ExecuteDelete 绕过 ChangeTracker**。Interceptor 完全看不到这些批量操作。
- **优先继承基类而不是实现接口**。继承 `SaveChangesInterceptor` 只需覆写两个方法，而不是实现接口的全部方法。
- **三个单例 Interceptor 不要每次请求 new 一个**。会触发 `ManyServiceProvidersCreatedWarning` 并严重拖慢性能。

如果你关注 .NET 开发、EF Core 实践和工程经验，可以关注 Aide Hub。这里会继续分享能落地的教程和代码示例。

## 参考

- [原文: EF Core Interceptors: The Complete Guide (.NET 10)](https://codewithmukesh.com/blog/ef-core-interceptors/)
- [作者 GitHub 示例仓库](https://github.com/iammukeshm/efcore-interceptors)
- [EF Core 拦截器官方文档](https://learn.microsoft.com/en-us/ef/core/logging-events-diagnostics/interceptors)
