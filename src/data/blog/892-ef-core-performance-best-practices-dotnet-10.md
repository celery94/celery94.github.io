---
pubDatetime: 2026-06-24T10:23:21+08:00
title: "EF Core 性能优化最佳实践（.NET 10）"
description: "EF Core 查询慢、内存高、启动卡，大多不是框架的锅，而是几个关键用法没对齐。这篇文章整理 10 个可落地的性能优化技巧，从 AsNoTracking 到编译查询、从批量操作到慢查询日志，附带优先级排序和实操代码。"
tags: ["C#", ".NET", "EF Core", "性能优化"]
slug: "ef-core-performance-best-practices-dotnet-10"
ogImage: "../../assets/892/01-cover.png"
source: "https://www.devleader.ca/2026/06/23/ef-core-performance-best-practices-in-net-10"
---

EF Core 是 .NET 世界里最主流的 ORM，但它也是最容易在不知不觉中吃掉你应用性能的地方。变更追踪、全字段加载、N+1 查询——这几样东西对开发体验很友好，对生产吞吐量很不友好。

好消息是，绝大多数 EF Core 性能问题都有固定的解法，而且大多数改动只需要加一行代码。这篇文章按优先级整理了 10 个技巧，从最快的胜利到需要一点成本的高级手段，每条都附带能直接用的代码。

## AsNoTracking：10 分钟见效的改动

EF Core 的变更追踪很聪明。它盯着你加载的每个实体、检测属性变化、自动生成 UPDATE 语句。当你需要 load-modify-save 模式时，这套机制无可替代。

问题在于：**多数查询根本不需要追踪**。API 响应、报表数据、列表页，这些都是只读场景，追踪器却照样在背后记录快照、维护标识映射，白白吃掉 CPU 和内存。

`AsNoTracking()` 的作用就是一句话关掉这一切：

```csharp
// 有追踪开销 —— 每个实体都进变更追踪器
var trackedPosts = await dbContext.BlogPosts
    .Where(p => p.IsPublished)
    .ToListAsync();

// 无追踪 —— 更快、内存更低，适合只读场景
var readOnlyPosts = await dbContext.BlogPosts
    .AsNoTracking()
    .Where(p => p.IsPublished)
    .ToListAsync();
```

什么时候用：所有只读查询。什么时候不用：需要 load-modify-save 的场景，没追踪就没有变更检测。

一个实用模式：全局配置 `UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking)`，然后在需要修改的地方用 `AsTracking()` 显式切回来。

## 编译查询：消除热路径的重复翻译开销

每次执行 LINQ 查询，EF Core 都要把它翻译成 SQL。翻译结果会被缓存，但缓存键的生成和查找本身也有开销。对于每秒执行成千上万次的查询，这点开销会累积。

`EF.CompileAsyncQuery` 把翻译工作提前到启动阶段，之后每次调用直接用编译好的委托，跳过了翻译和缓存查找：

```csharp
private static readonly Func<AppDbContext, int, Task<BlogPost?>> GetPostById =
    EF.CompileAsyncQuery((AppDbContext db, int id) =>
        db.BlogPosts
            .AsNoTracking()
            .Where(p => p.Id == id && p.IsPublished)
            .FirstOrDefault());

public async Task<BlogPost?> GetPublishedPostAsync(int id)
{
    return await GetPostById(_dbContext, id);
}
```

注意编译查询是 `static` 字段，类加载时创建一次，所有实例共享。上下文和参数每次调用时传入，EF Core 会正确处理。

适合编译查询的信号：你的遥测数据里排名前几的数据库操作调用频率。不是每个查询都值得编译，但热路径上的那几个，做了就有效果。

## 编译模型：大表结构的启动加速

EF Core 启动时会根据实体类型、关系、属性配置在内存里构建一个模型。对于 50 个实体类型以上的项目，这个构建过程可能吃掉几百毫秒的冷启动时间。对经常扩容缩容的容器应用来说，几百毫秒不是一个可以忽略的数值。

解决方法是用 `dotnet ef dbcontext optimize` 生成编译模型：

```bash
dotnet ef dbcontext optimize --output-dir CompiledModels --namespace MyApp.Data.CompiledModels
```

然后在配置里注册：

```csharp
protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
{
    optionsBuilder
        .UseSqlServer(connectionString)
        .UseModel(MyAppDbContextModel.Instance);
}
```

每次改实体配置或增减实体后都要重新生成。这是开发者一次性操作，收益体现在启动速度上。EF Core 10 把预编译查询能力推到了生产就绪状态。

## 避免 N+1：最常见的性能陷阱

N+1 是 EF Core 里最经典的性能问题，值得花一点篇幅说清楚。

场景是这样的：你加载了一组 `Author` 实体，然后循环访问每个作者的 `Posts` 导航属性。如果 `Posts` 没有被提前加载，EF Core 会为每个作者单独发一条 SQL。1 条查作者 + N 条查文章 = N+1 条查询。

```csharp
// 问题写法 —— 1 条查作者，每个作者 1 条查文章
var authors = await dbContext.Authors.ToListAsync();
foreach (var author in authors)
{
    var postCount = author.Posts.Count; // 每次触发一次懒加载
}

// 正确写法 —— 1 条（或 AsSplitQuery 下 2 条）查询搞定
var authors = await dbContext.Authors
    .Include(a => a.Posts)
    .AsNoTracking()
    .ToListAsync();
```

怎么发现自己有没有 N+1：开 EF Core 日志，看日志里是否有结构相同、只是参数值不同的重复查询——这就是 N+1 的典型指纹。

## Split Queries：多集合 Include 的避坑姿势

`Include()` 解决了 N+1，但它自己也有一个坑：当你同时 Include 多个集合导航属性时，EF Core 会用 JOIN 把它们拼成一条 SQL。JOIN 的结果是笛卡尔积——如果一条 `Order` 有 50 个 `OrderItems` 和 5 条 `Payments`，单条 JOIN 就产出 250 行，是你实际需要的 5 倍。数据量一大，带宽和内存直接爆炸。

`AsSplitQuery()` 的做法是把每个集合拆成独立查询，数据在应用内存里组装，不在数据库里膨胀：

```csharp
// 单条 JOIN 查询 —— 笛卡尔爆炸风险
var orders = await dbContext.Orders
    .Include(o => o.OrderItems)
    .Include(o => o.Payments)
    .AsNoTracking()
    .ToListAsync();

// 拆分查询 —— 每集合一条 SQL，无笛卡尔膨胀
var ordersSplit = await dbContext.Orders
    .Include(o => o.OrderItems)
    .Include(o => o.Payments)
    .AsSplitQuery()
    .AsNoTracking()
    .ToListAsync();
```

代价是：拆分后的查询不在同一个事务里执行，如果两个查询之间数据变了，可能出现短暂不一致。大多数只读场景都能接受，需要严格事务一致性时可以用显式事务或退回到单条查询。也可以设为全局默认：

```csharp
optionsBuilder.UseSqlServer(connectionString,
    o => o.UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery));
```

## 批量操作：ExecuteUpdateAsync 和 ExecuteDeleteAsync

在 EF Core 7 之前，想批量更新或删除一批记录，必须先加载到内存、逐个修改、再调 `SaveChanges`。对于几千行数据的操作，这意味着几千次实体往返和变更追踪开销。

EF Core 7 引入的 `ExecuteUpdateAsync` 和 `ExecuteDeleteAsync` 直接跳过实体加载，把 LINQ 表达式翻译成一条 SQL `UPDATE` 或 `DELETE`：

```csharp
// 旧写法 —— 先加载全部实体到内存，再逐行保存
var oldPosts = await dbContext.BlogPosts
    .Where(p => p.PublishDate < DateTimeOffset.UtcNow.AddYears(-3))
    .ToListAsync();
foreach (var post in oldPosts)
{
    post.IsArchived = true;
}
await dbContext.SaveChangesAsync();

// 新写法 —— 一条 UPDATE，零实体加载
await dbContext.BlogPosts
    .Where(p => p.PublishDate < DateTimeOffset.UtcNow.AddYears(-3))
    .ExecuteUpdateAsync(s => s.SetProperty(p => p.IsArchived, true));

// 直接 DELETE 也可以
await dbContext.AuditLogs
    .Where(log => log.CreatedAt < DateTimeOffset.UtcNow.AddMonths(-6))
    .ExecuteDeleteAsync();
```

需要注意一点：这两个方法完全绕过了变更追踪器，不会触发 `SaveChanges` 拦截器、领域事件和值生成器。如果你的业务逻辑依赖这些钩子，要么退回到 load-modify-save 模式，要么在批量操作旁手动触发领域事件。

## Select 投影：只取你要的列

加载完整实体是图省事的写法，但很浪费。如果你的 `BlogPost` 有 20 个属性——包括 `Content` 这样的长文本字段——只为了显示标题和发布时间就加载 20 列，带宽和内存都被白白消耗了。

用 `Select()` 投影到 DTO，只取你需要的列：

```csharp
// 过度加载 —— 拉了全部列，包括大字段 Content
var posts = await dbContext.BlogPosts
    .Where(p => p.IsPublished)
    .AsNoTracking()
    .ToListAsync();

// 投影 —— SQL 只 SELECT Id, Title, PublishDate
var postSummaries = await dbContext.BlogPosts
    .Where(p => p.IsPublished)
    .OrderByDescending(p => p.PublishDate)
    .Select(p => new BlogPostSummaryDto(p.Id, p.Title, p.PublishDate))
    .ToListAsync();

public record BlogPostSummaryDto(int Id, string Title, DateTimeOffset PublishDate);
```

EF Core 会把 `Select()` 表达式的投影列翻译成 SQL 的指定列查询。列表页、首页、摘要视图——这些场景基本都应该用投影。投影结果不是实体，不会被追踪，所以连 `AsNoTracking()` 都可以省略（留着也不碍事）。

## DbContext 生命周期与连接池

`DbContext` 设计上就是短生命周期的。它维护着数据库连接、追踪着加载过的实体、累积着待提交的变更。让它活太久会出问题。

在 ASP.NET Core 里，用默认的 scoped 注册就行——每个 HTTP 请求一个实例，请求结束自动释放：

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(connectionString));
```

后台服务（`IHostedService`、`BackgroundService`）不能直接注入 `DbContext`，因为那不是 request scope。改用 `IDbContextFactory<T>`：

```csharp
builder.Services.AddDbContextFactory<AppDbContext>(options =>
    options.UseSqlServer(connectionString));

public class DataCleanupService : BackgroundService
{
    private readonly IDbContextFactory<AppDbContext> _contextFactory;

    public DataCleanupService(IDbContextFactory<AppDbContext> contextFactory)
    {
        _contextFactory = contextFactory;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await using var context = await _contextFactory
                .CreateDbContextAsync(stoppingToken);

            await context.AuditLogs
                .Where(l => l.CreatedAt < DateTimeOffset.UtcNow.AddMonths(-6))
                .ExecuteDeleteAsync(stoppingToken);

            await Task.Delay(TimeSpan.FromHours(1), stoppingToken);
        }
    }
}
```

EF Core 底层通过 `SqlConnection` 的 ADO.NET 连接池自动管理连接复用。保持 context 短生命周期，连接池就能高效工作。连接耗尽的问题，大多是因为 context 被持有太久造成的。

## 查询计划缓存与参数化查询

EF Core 会自动缓存编译好的查询计划。相同结构的查询第二次执行时，跳过翻译步骤直接复用缓存。对吞吐量影响很大。

缓存被破坏的场景：用字符串拼接构造动态查询，每次都改变了查询表达式树的结构。

```csharp
// 破坏缓存 —— 每次调用生成不同的 raw SQL 字符串
var filter = $"%{searchTerm}%";
var posts = await dbContext.BlogPosts
    .FromSqlRaw($"SELECT * FROM BlogPosts WHERE Title LIKE '{filter}'")
    .ToListAsync();

// 保持缓存 —— LINQ 参数化查询，计划可复用
var posts = await dbContext.BlogPosts
    .Where(p => EF.Functions.Like(p.Title, $"%{searchTerm}%"))
    .AsNoTracking()
    .ToListAsync();
```

EF Core 的 LINQ 翻译总是生成参数化 SQL——参数值每次不同，但查询计划相同。尽量用 LINQ 表达式而不是拼 raw SQL。必须用 raw SQL 时，用 `FromSqlInterpolated` 代替 `FromSqlRaw`，它会自动参数化插值变量，同时防止查询计划缓存失效和 SQL 注入。

## 用 Serilog 记录慢查询

没测量的就不要谈优化。EF Core 内置了对 `ILogger` 框架的支持，和 Serilog 结合后可以得到结构化的查询日志，方便在生产环境里定位慢查询。

推荐的做法是设一个最小执行时间阈值，只记录真正超过性能预算的查询，而不是打满应用日志：

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
{
    options.UseSqlServer(connectionString)
           .UseLoggerFactory(LoggerFactory.Create(lb =>
               lb.AddSerilog()))
           .EnableDetailedErrors();
    // .EnableSensitiveDataLogging()  // 仅开发环境，会泄露参数值
});

builder.Host.UseSerilog((ctx, config) =>
{
    config
        .ReadFrom.Configuration(ctx.Configuration)
        .Enrich.FromLogContext()
        .WriteTo.Console()
        .WriteTo.File("logs/app-.log", rollingInterval: RollingInterval.Day)
        .WriteTo.Logger(lc => lc
            .Filter.ByIncludingOnly(e =>
                e.Properties.TryGetValue("ElapsedMilliseconds", out var ms) &&
                ms is ScalarValue sv &&
                sv.Value is long ms2 &&
                ms2 > 500)
            .WriteTo.File("logs/slow-queries-.log", rollingInterval: RollingInterval.Day));
});
```

EF Core 通过 `ILogger` 管道为每条数据库命令发出 `CommandExecutedEventData` 事件，其中 `ElapsedMilliseconds` 属性携带了执行时长。用 Serilog 子 logger 过滤出超过 500ms 的查询单独落盘，方便日常巡检和告警。

生产环境禁止开 `EnableSensitiveDataLogging()`——它会把实际参数值写进日志，包括密码、PII 和财务数据。只在本地调试单条查询时临时开，用完就关。

## 优先级排个序

如果你现在手上有一个 EF Core 项目需要优化，建议按这个顺序来——从投入产出比最高的开始：

**第一步，最大的回报、最小的改动：**

1. 所有只读查询加 `AsNoTracking()`——几处改动，即时效果。
2. 开日志找 N+1，用 `Include()` 修——通常每条查询改一行。
3. 批量更新/删除换成 `ExecuteUpdateAsync` / `ExecuteDeleteAsync`。

**第二步，优化热路径：**

4. 最高频的列表和首页接口加 `Select()` 投影。
5. 检查启动时间——如果慢，考虑编译模型。
6. 最高频的查询改成编译查询。

**第三步，处理边缘场景：**

7. 多条集合 Include 的大数据量查询评估 `AsSplitQuery()`。
8. 确认 web 应用用的是 scoped `DbContext`，后台服务用的是 `IDbContextFactory`。
9. 接上 Serilog 慢查询日志，跑几天看看有没有意料之外的慢查询。

EF Core 在正确使用的情况下是很快的。默认设置偏向正确性和开发体验，而不是原始吞吐量。上面对应的每一项调整，都是在把天平往性能方向拨，同时保持代码的可维护性。

## 常见问题

**EF Core 里最普遍的性能错误是什么？**

加载完整实体但不全用到，同时没加 `AsNoTracking()`。这两个问题叠加，足以让查询密集型应用的吞吐量差一个数量级。修复不需要深入理解 EF Core 内部机制，只需要在每条查询上手时养成习惯。

**什么时候用 AsNoTracking，什么时候用追踪查询？**

任何加载数据只读不写的场景都用 `AsNoTracking()`——API 响应、报表、仪表盘、投影。需要 load-modify-save 时才用追踪查询。一个安全默认：全局设 `NoTracking`，需要修改时用 `AsTracking()` 显式切回来。

**怎么检测 N+1 查询？**

开启 EF Core 日志，找结构相同但参数不同的重复查询。开发环境可以临时开 `EnableSensitiveDataLogging()` 看参数值确认模式。MiniProfiler、dotnet-monitor、SQL Server Profiler 等工具也能定位运行中的 N+1。

**ExecuteUpdateAsync 会绕过领域事件和拦截器吗？**

会。`ExecuteUpdateAsync` 和 `ExecuteDeleteAsync` 完全绕过了变更追踪器，不会触发 `SaveChanges` 拦截器、领域事件和值生成器。这是有意为之的性能取舍。如果业务规则依赖这些钩子，要么用传统的 load-modify-save，要么在批量操作旁手动触发领域事件。

**后台服务里怎么管理 DbContext 的生命周期？**

注入 `IDbContextFactory<T>` 而不是直接注入 `DbContext`。`DbContext` 是 scoped 的，不适合长生命周期服务。`IDbContextFactory<T>` 让你在每个工作单元里显式创建和释放短命的 context——和 web 请求里一样可控，只是手动管理。

如果你关注 .NET 开发、数据访问和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、性能优化经验和技术观察。

## 参考

- [EF Core Performance Best Practices in .NET 10](https://www.devleader.ca/2026/06/23/ef-core-performance-best-practices-in-net-10)
- [LINQ in C# Complete Guide](https://www.devleader.ca/2026/05/07/linq-in-c-complete-guide-to-language-integrated-query-net-6-9)
- [LINQ Deferred Execution in C#](https://www.devleader.ca/2026/05/15/linq-deferred-execution-in-c-when-queries-execute-and-multiple-enumeration-pitfalls)
- [How to Set Up Serilog in ASP.NET Core](https://www.devleader.ca/2026/07/07/how-to-set-up-serilog-in-aspnet-core-step-by-step-guide)
- [Logging in .NET Complete Guide](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
