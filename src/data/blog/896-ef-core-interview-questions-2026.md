---
pubDatetime: 2026-06-25T12:13:45+08:00
title: "30 道 EF Core 2026 面试真题：考官真正关心什么"
description: "2026 年的 EF Core 面试不再考什么是 ORM，而是场景题：查询返回 200 行却跑了 201 条 SQL、迁移在生产环境挂掉、后台任务因为多线程共用 DbContext 报错。本文梳理 30 道高频 EF Core 面试题，按考察维度分类，附带红牌答案和经典追问。"
tags: ["C#", "EF Core", "Interview", ".NET", "LINQ", "Change Tracking"]
slug: "ef-core-interview-questions-2026"
ogImage: "../../assets/896/01-cover.png"
source: "https://codewithmukesh.com/blog/efcore-interview-questions/"
---

## 面试题不在纸上，在线上

2026 年的 EF Core 面试，考官几乎不问概念定义了。他们问的是：你的查询返回 200 行但日志里跑了 201 条 SQL，排查思路是什么？迁移脚本在生产环境 apply 失败，你怎么处理？后台任务因为多线程共用 `DbContext` 抛异常，问题在哪？

这些问题暴露的不是“背没背过”，而是“有没有真的写过线上数据访问层”。

我面试过不少 .NET 开发者，EF Core 是区分普通候选人和强候选人的最快分界线。写 `.ToListAsync()` 谁都会，但解释清楚变更追踪器在做什么、为什么 EF Core 默认关掉懒加载、什么时候 `ExecuteUpdateAsync` 反而是错误选择——这才是考官想听到的。

下面是 30 道 EF Core 面试真问题，按考官实际的考察维度分成七个类别。每个问题背后附上红牌回答（直接挂的那种），以及考官最常接上的追问。

每道题都以 **EF Core 10 / .NET 10** 为准。

## 一、基础与 DbContext 生命周期

这组题看上去基础，但 junior 和 mid 的区分就在这里。生命周期问题尤其容易暴露只在 controller 里用过 EF Core 的人。

### Q1. DbContext 的生命周期为什么重要？

`DbContext` 默认注册为 **scoped**——每个 HTTP 请求一个实例。原因是：它的变更追踪器会累积实体的快照，你需要把它限定在一个工作单元内，用完就 dispose。

`DbContext` 不是线程安全的，也不适合长生命周期。如果把它注册成 singleton，两个并发请求共用同一个变更追踪器，你会得到竞态条件、脏数据，以及经典的 `InvalidOperationException: A second operation was started on this context instance before a previous operation completed`。

> **红牌回答：** "我注册成 singleton 方便复用。"——这是最容易搞崩 EF Core 生产环境的方式。

**追问：** "如果在 BackgroundService 里而不是 HTTP 请求里，怎么处理？"

### Q2. 把 DbContext 注入到 Singleton 后台服务为什么报错？

Singleton 不能依赖 scoped 服务——这叫**捕获依赖**。`DbContext` 要么被捕获后活一辈子（变更追踪器永不清空，无限增长），要么 DI 在启用 scope validation 时直接启动失败。

解法是注入 `IServiceScopeFactory`，每个工作单元自己创建 scope：

```csharp
public class OrderProcessor(IServiceScopeFactory scopeFactory)
    : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            using var scope = scopeFactory.CreateScope();
            var db = scope.ServiceProvider
                .GetRequiredService<AppDbContext>();
            await db.SaveChangesAsync(ct);
        }
    }
}
```

> **红牌回答：** "那把 DbContext 也改成 singleton 就匹配了。"——现在线程安全问题更严重了。

### Q3. AddDbContext 和 AddDbContextPool 有什么区别？

`AddDbContext` 每个 scope 新建一个 context 实例，用完丢弃。`AddDbContextPool` 维护一个可复用的实例池，在两次使用之间重置状态，避免高吞吐 API 上的分配和初始化开销。

面试官想听到的陷阱：池化会重置变更追踪器和大部分状态，但如果你在派生 `DbContext` 上存了自定义状态（租户 ID 字段、注入服务捕获的属性），这些状态会在请求之间泄漏，除非在 `OnConfiguring` 里或通过池化重置钩子单独处理。所以池化是性能优化，但前提是你的 context 除了 EF Core 自己管理的东西之外基本无状态。

> **红牌回答：** "池化总是更好，到处都用。"——如果你的 context 带请求级状态就不行。

**追问：** "怎么安全地把 tenant ID 传进池化的 context？"

### Q4. Code-First 还是 Database-First？

EF Core 没有 EDMX，也没有可视化 Model-First 设计器——那是老 Entity Framework 6 的东西。EF Core 只给你两条路：**code-first**（你写实体和配置，迁移生成 schema）和**逆向工程**（`Scaffold-DbContext` 从已有数据库生成模型）。

我的默认选择是 code-first，因为模型在源码管理里，变更在 PR 里可审查，迁移给你一份可部署的历史。只有接手一个你不拥有、且已有复杂数据库的项目时，才用逆向工程。

> **红牌回答：** "我用 EDMX 设计器。"——EF Core 里没有这东西，这说明你只碰过 EF6。

## 二、查询与 LINQ 翻译

这组题目测的是你是否理解 C# LINQ 最终变成 SQL——以及当它变不过去的时候会发生什么。

### Q5. IQueryable 和 IEnumerable 在 EF Core 里有什么区别？

`IQueryable<T>` 构建表达式树，EF Core 把它翻译成 SQL，**在数据库端执行**。`IEnumerable<T>` 是**在内存里**对已经拉回的对象跑 LINQ。

这就是一次高效查询和一次全表扫描进内存的区别：

```csharp
// SQL 端执行：WHERE IsActive = 1，只返回匹配行
var active = await db.Products
    .Where(p => p.IsActive).ToListAsync();

// 危险：AsEnumerable() 先把全部行拉进内存，再用 C# 过滤
var bad = db.Products.AsEnumerable()
    .Where(p => p.IsActive).ToList();
```

一旦调用 `AsEnumerable()`、`ToList()` 或 `foreach`，组合就停止了，之后的一切都在客户端跑。我尽量把查询保持为 `IQueryable`，直到最后一刻。

> **红牌回答：** "它们基本一样，都是集合。"——这种误解会直接上线全表加载。

### Q6. .Where() 抛出 "Could Not Be Translated"，发生了什么？

EF Core 试图把 C# 表达式翻译成 SQL 但做不到——通常是因为你在查询里调了一个自定义方法或没有 SQL 等价物的 .NET API。

从 EF Core 3.0 开始，框架**拒绝对这类表达式做静默客户端求值**（这曾经导致不可见的 N+1 和全扫）。修复手段按优先级：改写成可翻译的谓词（直接比较原始列）、在 `AsEnumerable()` 之后处理不可翻译的部分（如果已过滤到小集）、或者把逻辑推到计算列或 `FromSql` 里。

> **红牌回答：** "加 `.AsEnumerable()` 放在 `.Where()` 前面就行了。"——这通过加载整张表来消除异常，代价不对。

### Q7. First、Single、Find 有什么区别？

`First`/`FirstOrDefault` 返回第一条匹配行，允许多条命中。`Single`/`SingleOrDefault` 断言恰好一条匹配，两条就抛异常——用来表达"重复就是 bug"的场景。`Find` 比较特殊：它**先查变更追踪器**，实体不在内存里才打数据库，所以用主键查找时可以省一次往返。

> **红牌回答：** "都一样，我就用 First。"——那你丢掉了 Single 的正确性保障和 Find 的缓存。

### Q8. EF Core 里怎么写左连接？

EF Core 没有 `LeftJoin` 关键字（除非你用 EF Core 10 的新操作符）；经典写法是 `GroupJoin` + `SelectMany` + `DefaultIfEmpty`，生成 SQL `LEFT JOIN`：

```csharp
var query =
    from o in db.Orders
    join c in db.Customers on o.CustomerId equals c.Id into grp
    from c in grp.DefaultIfEmpty()
    select new { o.Id, CustomerName = c != null ? c.Name : "(none)" };
```

`DefaultIfEmpty()` 就是让它从内连接变成左连接的那个调用。大多数情况下，如果有导航属性我直接用它投影，让 EF Core 自己搞定 join。

> **红牌回答：** "EF Core 做不了左连接。"——它能做，你只是需要正确的 LINQ 形状。

## 三、加载策略

怎么加载关联数据是 EF Core 性能问题的最常见来源，每组面试至少会出其中一道。

### Q9. EF Core 默认是懒加载、饥加载还是显式加载？

EF Core 加载关联数据有三种方式：**饥加载**（`Include`，查询时一次性加载）、**显式加载**（`context.Entry(x).Reference(...).Load()`，你主动触发）、**懒加载**（访问导航属性时自动加载）。

关键事实：**懒加载在 EF Core 里默认关闭。** 你必须安装 `Microsoft.EntityFrameworkCore.Proxies`、调用 `UseLazyLoadingProxies()`、并把导航属性标为 `virtual`。这和老 EF6 完全相反——EF6 懒加载默认开启。知道这个翻转是一个快速的资历信号。

> **红牌回答：** "懒加载默认开着，和 Entity Framework 一样。"——这对 EF6 是对的，对 EF Core 是错的，也告诉我你实际用过哪个。

### Q10. 为什么 Web API 里懒加载危险？

两个原因。第一，它隐藏 N+1：一个 `foreach` 遍历订单，每次访问 `order.Customer` 就触发一次查询，因为它是隐式的，在 SQL Profiler 抓到之前你看不到。第二，懒加载需要一个存活的 `DbContext`。在 Web API 里，context 在请求末就 dispose 了，之后访问导航属性抛 `ObjectDisposedException`——这是实体逃逸到 serializer 或后台延续时的经典 bug。

我的规则：在 API 里保持懒加载关闭，用 `Include` 或投影显式加载。懒加载在桌面应用里（有长生命周期 context）更站得住。

> **红牌回答：** "我打开懒加载就不用操心加载了。"——这正是你上线 N+1 的方式。

### Q11. Include 和 Projection 什么时候分别用？

`Include` 拉回完整的关联实体并追踪——当你需要修改对象图时用它。用 `Select` 投影到 DTO **只拉你需要的列**，更快更轻——只读响应用它：

```csharp
// 投影：一条查询，只取三列，没有追踪开销
var dtos = await db.Orders
    .Select(o => new OrderDto(o.Id, o.Total, o.Customer.Name))
    .ToListAsync();
```

我对 GET 端点的默认选择是投影。只在加载一个即将修改的聚合时才用 `Include`。

> **红牌回答：** "我总用 Include 保险。"——你在为了返回三个字段加载整个实体图。

### Q12. 你 Include 了三个集合后返回行数爆炸了，怎么回事？

这是**笛卡尔积爆炸**。每个集合的 `Include` 都 join 一张表，SQL 把行乘起来：100 个订单各带 10 条 items 和 5 个 tags，可能返回 5000 行重复数据，EF Core 再在内存里去重。查询变慢、带宽吃紧。

修复方式是 `AsSplitQuery()`——每个集合单独发一条 SQL，而不是一次巨大的 join。取舍：分拆查询走多次往返，且不包在同一个快照里，所以对必须完美一致的集合，我会保持单查询或包在事务里。

> **红牌回答：** "多加几个 Include。"——这只会让爆炸更大。

## 四、N+1 与性能

这是 senior 轮的核心。考官期望你诊断，而不只是下定义。

### Q13. 日志显示查 50 张发票用了一条查询，然后又跑了 50 条查询。这是什么？怎么更早发现问题？

这是经典的 **N+1 查询问题**：一次查询拿父列表，然后每个父实体再跑一次查询拿关联属性。它发生在懒加载或你忘了 `Include` 的时候，当代码迭代并碰到导航属性就触发。

除了用饥加载或投影修复，面试官真正问的是你**怎么在上线前发现它**。我在开发环境接上 EF Core 日志，让每条查询都可见；我看到一波相同参数化的查询就是一个味道。在热点路径上，我会在集成测试里断言查询数量，这样回归会在构建阶段失败，而不是在用户那炸掉。

> **红牌回答：** "关掉懒加载就行了。"——这只掩盖了一个原因，没有给你检测下一个的方法。

**追问：** "怎么写一个测试，让它在端点突然发了 50 条查询时失败？"

### Q14. 编译查询什么时候真正值得用？

每次 EF Core 跑 LINQ 查询，它会把表达式树编译成 SQL 然后缓存起来。编译查询（`EF.CompileAsyncQuery`）跳过这个缓存查找，直接给你一个预构建的委托，每次调用省几微秒。

这**只在真正的热点路径上有意义**——每秒几千次的查询，而且你已经把数据库端的瓶颈都解决了。99% 的情况下内置查询缓存足够，编译查询是可读性换优化的过早优化。我只在 profiler 指向查询编译开销时才上它。

> **红牌回答：** "我每个查询都编译，性能会更好。"——现在你到处加了复杂度，收益只存在于少数几个地方。

### Q15. 什么时候用 AsNoTracking，有什么坑？

`AsNoTracking` 告诉 EF Core 不用为返回的实体创建变更追踪快照。对只读查询来说，这是实实在在的内存和 CPU 节省，所以我对所有不修改结果的查询都用它。

面试官想听的坑：没有追踪，EF Core **默认不做标识解析**，所以如果同一行在结果里出现两次（比如通过 join），你会得到两个不同的对象实例而不是同一个共享引用。如果这很重要，用 `AsNoTrackingWithIdentityResolution`。还有，显然你不能对 no-tracking 实体调 `SaveChanges` 来持久化修改——你得先 attach。

> **红牌回答：** "我到处加 AsNoTracking，因为更快。"——那你的更新是怎么工作的？它还会破坏你可能依赖的引用相等。

### Q16. 查询在测试数据上很快，生产环境超时，你怎么诊断？

不靠猜——看 SQL。先调 `query.ToQueryString()` 拿到生成的准确 SQL，然后在数据库里跑并看执行计划。这会告诉我到底是缺索引、顺序扫描，还是烂 join。

常见原因和修复：过滤或外键列上缺索引（`builder.HasIndex(...)`）、加载整实体但投影就够了、笛卡尔积需要 `AsSplitQuery`、返回了无边界结果集需要分页。纪律是先测量、改一样、再测量。

> **红牌回答：** "把 command timeout 调大。"——这只会把 30 秒的查询变成 90 秒的查询，什么都没修。

### Q17. 需要处理一百万行数据，应用内存爆了怎么办？

`ToListAsync()` 把每一行都缓冲到内存——这就是 OOM。对大数据集，我用 `AsAsyncEnumerable()` 流式处理，一行一行来，永远不全量驻留：

```csharp
await foreach (var row in db.LargeTable.AsAsyncEnumerable())
{
    // 逐行处理，内存只保留一行
}
```

如果只是批量更新数据库，用 `ExecuteUpdateAsync` 直接在服务端跑，连行都不拉回来。重点是：你必须知道数据量级，针对不同量级选不同策略。

> **红牌回答：** "加内存。"——这是运维答案，不是开发答案。

## 五、迁移

### Q18 - Q21（迁移四连）

面试里迁移的考察点集中在：`EnsureCreated` vs `Migrate` 的区别（前者跳过迁移历史表，适合测试和 demo；后者记录迁移历史，是生产环境的唯一正确方式）、迁移脚本里的数据操作（`migrationBuilder.Sql("UPDATE ...")` 里写啥）、`__EFMigrationsHistory` 表的角色、以及生产环境回滚策略（EF Core 没有原生回滚，靠生成下一条"反向"迁移）。

要点：**不要在 `Up` 方法里做不可逆的数据变更。** 如果必须做，确保 `Down` 方法能复原，并且迁移脚本本身经过 CI 测试。

## 六、变更追踪与保存

### Q22 - Q26（变更追踪五连）

这部分考官盯的是你对 `SaveChanges` 全流程的理解：

- **ChangeTracker 怎么决定 INSERT / UPDATE / DELETE？** 它会对比 entry 的 `OriginalValues` 和 `CurrentValues`，标记 `EntityState`。
- **`SaveChanges` 和 `SaveChangesAsync` 的内部区别？** 不仅是同步/异步，异步版本用 `async/await` 全链路，避免阻塞线程。
- **`ExecuteUpdateAsync` vs 先查再改再 `SaveChanges`？** 前者是一条 SQL 直接在数据库跑，速度快得多，但**绕过变更追踪器**——之后内存里的实体仍然是旧值。如果后续逻辑依赖被追踪实体的最新状态，就会出 bug。
- **并发冲突怎么处理？** EF Core 用乐观并发控制（`[ConcurrencyCheck]` 或 `IsRowVersion`），`SaveChanges` 时如果原始值不匹配当前数据库值，抛 `DbUpdateConcurrencyException`。你需要决定是客户端优先（重试）、数据库优先（覆盖）、还是合并。
- **`IExecutionStrategy` 是什么？** EF Core 的重试策略抽象，允许你在瞬态错误（比如死锁）时自动重试整个事务。

> **红牌回答（通用）：** 对变更追踪一问三不知，表示"我从来不看它，SaveChanges 就行了"。

## 七、高级话题

### Q27 - Q30（高级四连）

- **`IDbContextFactory<T>` 的适用场景**：Blazor Server（component 生命周期 != scope）、BackgroundService、任何需要手动管理 context 生命周期的场景。
- **EF Core 拦截器能做什么？** 挂查询、命令执行、连接、事务等生命周期事件。典型用途：自动填充审计字段、软删除过滤、查询标签、性能监控。使用拦截器（`DbCommandInterceptor`、`SaveChangesInterceptor`）而不是到处散落代码。
- **`Owned` 类型（值对象）怎么配置？** `modelBuilder.Entity<Order>().OwnsOne(o => o.Address)`，地址字段扁平化到同一张表，或分表存储。适合值对象模式（DDD），但注意 owned 类型不能单独追踪、不能有导航属性指向它。
- **EF Core 10 有什么值得关注的新特性？** `LeftJoin`/`RightJoin` 原生 LINQ 操作符、具名查询过滤器（一个实体支持多个 filter，按场景激活）、更好的预编译模型支持、`ExecuteUpdate`/`ExecuteDelete` 增强。

## 八、5 个直接让面试官 pass 掉的 EF Core 错误

**1. 给 DbContext 注册 Singleton。** 这是最经典的。`DbContext` 不是线程安全的，变更追踪器会无限膨胀。面试官听到这句话立刻知道你没写过生产级数据访问。

**2. 在 API 里默认打开懒加载。** 你会把 N+1 问题散布到整个代码库，而且根本看不见。在 Web API 里，懒加载几乎永远是反模式。

**3. 不知道 Client vs Server 求值的区别。** 调 `AsEnumerable()` 或 `ToList()` 太早，把过滤从数据库拉到内存——你这是把 SQL Server 的工作给 C# 做。

**4. 用 `EnsureCreated` 管理生产数据库。** `EnsureCreated` 不维护迁移历史。Schema 变了它不知道怎么改——只会建新。生产环境永远用 `Migrate()`。

**5. async 测试里忘了 await。** `ToListAsync` 返回 `Task`。不 await 你的测试永远通过，因为什么都没执行。测试标记为 `async Task`，**所有异步调用前面加 await**。

## 小结

2026 年的 EF Core 面试已经不再是定义考试，而是场景诊断。考官想看你面对已知模式能不能说出本质、能不能指出陷阱、能不能给出默认推荐并说明何时偏离。

准备时，关注这几个方向：**变更追踪器的工作原理**、**查询什么时候从服务端变成客户端**、**加载策略和 N+1 的关系**、**并发与重试机制**、**迁移实践**。如果这些地方你都能讲出三个要点和对应的代码，EF Core 面试轮就已经拿下了。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [30 EF Core Interview Questions That Actually Get Asked in 2026 — codewithmukesh](https://codewithmukesh.com/blog/efcore-interview-questions/)
- [.NET Interview Questions Hub](https://codewithmukesh.com/blog/dotnet-interview-questions/)
- [Lazy Loading in EF Core — Microsoft Docs](https://learn.microsoft.com/en-us/ef/core/querying/related-data/lazy)
- [AsSplitQuery — Microsoft Docs](https://learn.microsoft.com/en-us/ef/core/querying/single-split-queries)
- [Tracking vs No-Tracking Queries in EF Core](https://codewithmukesh.com/blog/tracking-vs-no-tracking-queries-efcore/)
- [Fluent API Entity Configuration in EF Core](https://codewithmukesh.com/blog/fluent-api-entity-configuration-efcore/)
