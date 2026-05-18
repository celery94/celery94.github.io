---
pubDatetime: 2026-05-18T09:40:00+08:00
title: "EF Core 10 大性能陷阱（以及如何修复）"
description: "开发环境测试通过、生产环境响应爆炸——这 10 个 EF Core 查询模式问题会在真实流量下把接口拖垮。每个问题都有 .NET 10 下的具体修复代码。"
tags: ["EF Core", "dotnet", "性能优化", "Entity Framework"]
slug: "ef-core-performance-mistakes"
ogImage: "../../assets/804/01-cover.png"
source: "https://codewithmukesh.com/blog/ef-core-performance-mistakes/"
---

![EF Core 10大性能陷阱封面](../../assets/804/01-cover.png)

上个月我帮一位同事调查一个"接口慢"的问题，整整花了三个小时。那个接口返回 50 条订单列表，响应时间是 4 秒。问题找到之后，修复就一行：加了一个 `.Select()` 投影，只返回响应真正需要的字段。响应时间从 4 秒降到了 80 毫秒。

这就是 EF Core 让人头疼的地方。它让你很容易写出一些查询：在有 10 行种子数据的开发环境里运行得飞快，到了生产环境面对 10 万行数据时直接崩掉。代码编译通过，测试全绿，一切看起来都正常——直到真实流量打过来，接口开始爬行。

这篇文章梳理了生产 .NET 代码库里最常见的 10 个 EF Core 性能问题，以及每个问题在 .NET 10 / EF Core 10 下的具体修复方案。

## 什么算 EF Core 性能问题

EF Core 性能问题的共同特征：代码在开发环境是正确的，但在生产负载下会急剧劣化。这 10 个问题有三个共同点：代码编译通过、测试通过、只有真实数据量和并发量出现时才暴露。

EF Core 10 的运行时已经比以前快了许多——JIT 对实体化热路径的内联更好，泛型特化的开销更低，还新增了一等公民 `LeftJoin` 和 `RightJoin` 操作符。但这些都不能帮你绕过下面这 10 个问题。**性能来自你写的查询模式，不来自框架版本号。**

## 如何发现这些问题

修复之前先量。开发阶段发现 EF Core 问题最快的方式是把生成的 SQL 打印出来：

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString)
           .LogTo(Console.WriteLine, LogLevel.Information)
           .EnableSensitiveDataLogging(builder.Environment.IsDevelopment()));
```

打开一个接口，如果控制台里出现了 50 个独立的 `SELECT`，那就是 N+1。如果一个 `SELECT` 为 20 条实体返回了 10000 行，那就是笛卡尔积爆炸。如果每个读取查询里都能看到 `__EFCore_OriginalValues_` 快照列，那就是变更追踪在你永远不会更新的数据上空转。

还可以用 `dotnet-trace`、MiniProfiler 或 EF Core Power Tools 做更深入的分析，但上面那个 `LogTo` 一行代码能在 5 分钟内找出 80% 的问题。

## 第 1 个：N+1 查询问题

这是 EF Core 性能杀手里的头号。你用一次查询加载了一批实体，然后代码在访问关联导航属性时，对每个实体各自触发一次单独的数据库查询。

**问题代码：**

```csharp
var orders = await context.Orders.ToListAsync(ct);

foreach (var order in orders)
{
    // 每次访问这里都会向数据库发一条独立的 SELECT
    Console.WriteLine($"{order.Customer.Name} - {order.Total}");
}
```

100 条订单就是 101 次查询。1000 条订单就是 1001 次数据库往返，而这本来应该是一次查询能搞定的。

**修复方案：**

```csharp
// 方案一：用 Include 预先加载
var orders = await context.Orders
    .Include(o => o.Customer)
    .ToListAsync(ct);

// 方案二：投影到 DTO（通常更好）
var orders = await context.Orders
    .Select(o => new OrderListItem
    {
        Id = o.Id,
        CustomerName = o.Customer.Name,
        Total = o.Total
    })
    .ToListAsync(ct);
```

投影通常是更好的选择，因为它同时解决了第 2 个问题。需要在后续逻辑里用到完整关联实体时用 `Include`，返回数据给客户端时用投影。

这个问题有一个隐藏变体：**JSON 序列化触发 N+1**。如果开了懒加载（见第 4 个问题），序列化器在写响应时会触发懒加载查询——查询日志里会出现从 `System.Text.Json` 内部发出的 SQL。这个坑我掉进去过好几次。

## 第 2 个：返回完整实体而不是投影

你从 API 接口返回完整的数据库实体，但客户端只需要三个字段。查询从磁盘加载了 20 列，把 20 个属性注水到被追踪的实体上，给变更检测做快照，然后把 20 个属性序列化成 JSON——客户端只用了其中三个。

**问题代码：**

```csharp
app.MapGet("/products", async (AppDbContext db, CancellationToken ct) =>
{
    var products = await db.Products.ToListAsync(ct);
    return Results.Ok(products);
});
```

这会加载所有列，包括 `Description`（可能是一个大文本字段）、`InternalNotes`、`CostPrice`，即便客户端只需要 `Id`、`Name` 和 `Price`。

**修复方案：**

```csharp
app.MapGet("/products", async (AppDbContext db, CancellationToken ct) =>
{
    var products = await db.Products
        .Select(p => new ProductListItem
        {
            Id = p.Id,
            Name = p.Name,
            Price = p.Price
        })
        .ToListAsync(ct);

    return Results.Ok(products);
});
```

通过 `Select()` 投影生成的 SQL 列更少，自动跳过变更追踪，防止宽表过度抓取，还给客户端提供了一个稳定的 DTO 契约。在一张 20 列、5000 行的表上，把 `ToListAsync()` 换成 3 列投影，通常能把响应体大小削减 70%，查询执行时间缩短 30% 到 50%。

经验规则：**所有列表接口都应该通过投影返回 DTO，绝不返回原始实体**。实体用于写路径和按 ID 查找，投影用于一切需要返回给客户端的场景。

## 第 3 个：忘记在只读查询上加 AsNoTracking

默认情况下，EF Core 通过 `ChangeTracker` 追踪它加载的每一个实体。这是 `SaveChanges()` 知道要更新什么的机制。但在典型的 API 里，80% 的接口都是读操作——加载数据、序列化、返回，从不调用 `SaveChanges()`。追踪在这里是纯开销。

**问题代码：**

```csharp
var orders = await context.Orders
    .Where(o => o.CreatedAt > DateTime.UtcNow.AddDays(-7))
    .ToListAsync(ct);
// 每一条订单都进了 ChangeTracker，EF 保留了所有属性的快照
// 用来检测永远不会发生的变更
```

**修复方案：**

```csharp
var orders = await context.Orders
    .AsNoTracking()
    .Where(o => o.CreatedAt > DateTime.UtcNow.AddDays(-7))
    .ToListAsync(ct);
```

或者在 `DbContext` 上全局设置，让安全选项成为默认值：

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString)
           .UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking));
```

把 `NoTracking` 设为默认后，只在真正需要追踪的写路径上调用 `.AsTracking()` 来按需开启。在约 10000 行数据集的基准测试中，`AsNoTracking()` 对纯读操作一贯快 20% 到 40%，内存压力和 GC 压力也更低。

注意：如果你用了乐观并发令牌（`[Timestamp]` 或 `xmin`），在导向 `SaveChanges()` 的查询上需要保留追踪。

## 第 4 个：生产环境开着懒加载

懒加载是一个功能——第一次访问导航属性时悄悄发一次数据库查询。听起来很方便，但在生产环境是灾难：查询会从你想不到的地方触发，比如 JSON 序列化内部、映射代码里、日志调用中。

**问题配置：**

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString)
           .UseLazyLoadingProxies()); // 不要这样做
```

这样一来，任何读取 `order.Customer.Name` 的代码都会触发查询。遍历导航属性的序列化器？查询。遍历所有属性的映射库？查询。调用 `ToString()` 的日志记录器？可能也有查询。最终是非确定性的 N+1 风暴，只在负载下才会出现。

**修复方案：**

```csharp
// 不要调用 UseLazyLoadingProxies，用显式预先加载或投影代替

// 方案一：显式预先加载
var order = await context.Orders
    .Include(o => o.Customer)
    .Include(o => o.LineItems)
    .FirstOrDefaultAsync(o => o.Id == id, ct);

// 方案二：更好——投影到你需要的确切数据
var orderDto = await context.Orders
    .Where(o => o.Id == id)
    .Select(o => new OrderDetail
    {
        Id = o.Id,
        CustomerName = o.Customer.Name,
        Items = o.LineItems.Select(i => new LineItemDto
        {
            ProductName = i.Product.Name,
            Quantity = i.Quantity
        }).ToList()
    })
    .FirstOrDefaultAsync(ct);
```

通过 `Include` 显式预先加载让依赖关系在代码里可见。投影让数据的形状成为契约的一部分。两者都能让你精确推断出哪些 SQL 会在什么时候运行、数据量有多大。

**在服务端 ASP.NET Core 应用上永远不要启用懒加载代理**。隐式查询触发与 HTTP 处理程序应该如何思考数据库访问的方式是不兼容的。

## 第 5 个：多个 Include 导致笛卡尔积爆炸

当你在一次查询中预先加载两个或更多集合导航属性时，EF Core 会生成 LEFT JOIN，产生笛卡尔积。一个有 10 个项目和 10 名员工的部门，数据库会返回 100 行。集合越多，行数相乘式增长。这叫笛卡尔积爆炸，和 N+1 是不同的问题。

**问题代码：**

```csharp
var departments = await context.Departments
    .Include(d => d.Projects)
    .Include(d => d.Employees)
    .ToListAsync(ct);
```

50 个部门、每个 20 个项目、每个 30 名员工：这一次查询就返回了 30000 行大部分是重复的部门数据。EF Core 在客户端去重，但网络传输和反序列化的代价已经付出去了。

**修复方案：**

```csharp
var departments = await context.Departments
    .AsSplitQuery()
    .Include(d => d.Projects)
    .Include(d => d.Employees)
    .ToListAsync(ct);
```

`AsSplitQuery()` 告诉 EF Core 对每个 `Include` 执行一次查询，然后在内存中拼接结果。你得到的是三个小查询而不是一个巨大的交叉连接查询。代价是这三次查询各自走一次网络。

判断规则：如果你加载 2 个以上集合，且笛卡尔积超过父实体数量的 10 倍，就用 `AsSplitQuery`；如果只有一个集合或乘数很小，默认单查询模式就够了。

也可以在 `DbContext` 级别全局设置：

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString, npgsql =>
        npgsql.UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery)));
```

## 第 6 个：实体化之后再过滤

这是隐形杀手。你先调用 `.ToListAsync()`，然后再对结果调用 `.Where()`。EF Core 把整张表加载进了内存，然后过滤在客户端进行。在有 10 万行的表上，你刚跑了一次全表扫描，只为了留下 12 条记录。

**问题代码：**

```csharp
// 括号让 ToListAsync() 在 Where() 之前执行
var orders = (await context.Orders.ToListAsync(ct))
    .Where(o => o.CreatedAt > DateTime.UtcNow.AddDays(-7))
    .Take(20);
```

SQL Server 把 `Orders` 表的每一行都流给了你的应用服务器，然后 C# 在数据已经在内存里的时候才做过滤。接口现在被网络 I/O 和表大小拖死了。

**修复方案：**

```csharp
var orders = await context.Orders
    .Where(o => o.CreatedAt > DateTime.UtcNow.AddDays(-7))
    .OrderByDescending(o => o.CreatedAt)
    .Take(20)
    .AsNoTracking()
    .ToListAsync(ct);
```

顺序很关键：**始终在实体化之前过滤、排序、分页**。`IQueryable<T>` 惰性构建 SQL 表达式树，只有 `ToListAsync()`、`FirstAsync()`、`CountAsync()` 等终止操作才会执行它。在终止操作之后做的任何操作都在内存对象上运行。

还有一个相关的反模式：客户端求值。如果你的 `Where` 谓词调用了 EF Core 无法转换成 SQL 的 C# 方法，EF Core 3+ 默认会抛出异常，而不是悄悄切换到客户端求值。这是特性，不是 bug。不要试图绕过它，重构查询。

## 第 7 个：加载实体只是为了批量更新或删除

你想把 10000 条订单标记为已归档，于是写了一个干净的 foreach 循环，加载每条订单，设置标志，调用 `SaveChanges()`。任务跑了 5 分钟，然后 CSV 导入接口超时，DBA 在晚上 11 点给你发消息。

**问题代码：**

```csharp
var oldOrders = await context.Orders
    .Where(o => o.CreatedAt < DateTime.UtcNow.AddYears(-1))
    .ToListAsync(ct);

foreach (var order in oldOrders)
{
    order.IsArchived = true;
}

await context.SaveChangesAsync(ct);
```

EF Core 刚才加载了 10000 行的所有列，创建了 10000 个被追踪的实体实例，对所有实例做了变更检测，然后生成了 10000 个独立的 `UPDATE` 语句（即使是批量的，也是 10000 条），只是为了翻转一个布尔列。

**修复方案（EF Core 10 集合操作）：**

```csharp
await context.Orders
    .Where(o => o.CreatedAt < DateTime.UtcNow.AddYears(-1))
    .ExecuteUpdateAsync(updates => updates
        .SetProperty(o => o.IsArchived, true)
        .SetProperty(o => o.ArchivedAt, DateTime.UtcNow), ct);
```

一条 SQL 语句，不加载实体，不做变更追踪，没有每行一次的往返。只是一条在数据库服务器上运行的 `UPDATE`。删除也一样：

```csharp
await context.Orders
    .Where(o => o.IsArchived && o.CreatedAt < DateTime.UtcNow.AddYears(-3))
    .ExecuteDeleteAsync(ct);
```

在我的 EF Core 10 批量操作基准测试中，`ExecuteUpdateAsync` 和 `ExecuteDeleteAsync` 比加载再 `SaveChanges` 模式快 **300 到 500 倍**。

注意：这两个方法完全绕过了变更追踪，意味着 EF Core 拦截器不会触发，全局查询过滤器不会应用到更新谓词（需要你自己加），`SaveChanges` 里的审计日志逻辑也不会运行。如果你需要拦截器行为，就用 `SaveChanges` 接受这个代价。

## 第 8 个：列表接口没有分页

你的 `/products` 接口返回整张 `Products` 表。开发环境有 50 行，没问题。生产环境里目录导入任务一夜之间加了 20 万个 SKU。第二天早上，每个加载这个接口的面板都卡住了，APM 工具开始报警。

**问题代码：**

```csharp
app.MapGet("/products", async (AppDbContext db, CancellationToken ct) =>
{
    var products = await db.Products.AsNoTracking().ToListAsync(ct);
    return Results.Ok(products);
});
```

**修复方案（偏移分页）：**

```csharp
app.MapGet("/products", async (
    int page,
    int pageSize,
    AppDbContext db,
    CancellationToken ct) =>
{
    page = Math.Max(1, page);
    pageSize = Math.Clamp(pageSize, 1, 100);

    var query = db.Products.AsNoTracking().OrderBy(p => p.Id);

    var totalCount = await query.CountAsync(ct);
    var items = await query
        .Skip((page - 1) * pageSize)
        .Take(pageSize)
        .Select(p => new ProductListItem
        {
            Id = p.Id,
            Name = p.Name,
            Price = p.Price
        })
        .ToListAsync(ct);

    return Results.Ok(new { items, totalCount, page, pageSize });
});
```

两点要注意。第一，**服务端必须限制 `pageSize` 的上限**，永远不要信任客户端会传一个合理的值。第二，对于超过百万行的表，从偏移分页（`Skip`/`Take`）切换到基于游标的键集分页。偏移分页强迫数据库对每一页都计数并跳过行，页码越大越慢。键集分页用索引列上的 `WHERE` 子句，无论分页深度如何都能保持恒定的性能。

**从第一天起就给所有列表接口加分页，即使表现在还很小。**

## 第 9 个：过滤列或连接列上缺少数据库索引

EF Core 给了你漂亮的 LINQ 查询，数据库愉快地运行它。没有索引的情况下，数据库每次都在做全表扫描。开发环境 10000 行，很快；生产环境 1000 万行，同样的查询要 8 秒。

**问题配置：**

```csharp
public class Product
{
    public Guid Id { get; set; }
    public string Sku { get; set; } = null!;
    public string Name { get; set; } = null!;
    public Guid CategoryId { get; set; }
    // 没有声明任何索引
}
```

每个 `Where(p => p.Sku == sku)` 或在 `CategoryId` 上做连接的查询都是全表扫描。

**修复方案（Fluent API）：**

```csharp
public class ProductConfiguration : IEntityTypeConfiguration<Product>
{
    public void Configure(EntityTypeBuilder<Product> builder)
    {
        builder.HasIndex(p => p.Sku).IsUnique();
        builder.HasIndex(p => p.CategoryId);
        builder.HasIndex(p => new { p.CategoryId, p.CreatedAt }); // 复合索引
    }
}
```

或者用实体上的 `[Index]` 属性：

```csharp
[Index(nameof(Sku), IsUnique = true)]
[Index(nameof(CategoryId))]
[Index(nameof(CategoryId), nameof(CreatedAt))]
public class Product { /* ... */ }
```

然后 `dotnet ef migrations add AddProductIndexes` 和 `dotnet ef database update`。索引会增加写入性能的开销和存储占用，所以不要给每一列都加索引。**对热路径查询里出现在 `WHERE`、`JOIN`、`ORDER BY` 子句中的列加索引。** 经验规则：如果一个查询在热路径上，且过滤的列有几千个以上的不同值，这列就需要索引。

## 第 10 个：热路径上没有使用编译查询

每次执行 LINQ 查询，EF Core 都要遍历表达式树并把它翻译成 SQL。大多数查询只需要几微秒，感知不到。但在每秒触发数千次的热路径上，这个翻译开销会积累起来。EF Core 支持编译查询——把 LINQ 到 SQL 的翻译编译一次，然后无限次复用这个委托。

**问题代码（热路径上）：**

```csharp
app.MapGet("/products/{id:guid}", async (
    Guid id,
    AppDbContext db,
    CancellationToken ct) =>
{
    var product = await db.Products
        .AsNoTracking()
        .FirstOrDefaultAsync(p => p.Id == id, ct);

    return product is null ? Results.NotFound() : Results.Ok(product);
});
```

这段代码是正确的，但在一个服务 5000 RPS 的接口上，LINQ 翻译代价不可忽视。

**修复方案（EF.CompileAsyncQuery）：**

```csharp
private static readonly Func<AppDbContext, Guid, CancellationToken, Task<Product?>> GetProductById =
    EF.CompileAsyncQuery((AppDbContext db, Guid id, CancellationToken ct) =>
        db.Products
            .AsNoTracking()
            .FirstOrDefault(p => p.Id == id));

app.MapGet("/products/{id:guid}", async (
    Guid id,
    AppDbContext db,
    CancellationToken ct) =>
{
    var product = await GetProductById(db, id, ct);
    return product is null ? Results.NotFound() : Results.Ok(product);
});
```

在我对单行主键查找的基准测试中，编译查询比等效的即席 LINQ 查询一贯快 **30 到 60%**。EF Core 9 还引入了实验性的预编译查询特性（与 .NET NativeAOT 支持绑定），在大量查询执行的工作负载上差距更大，不过仍处于预览阶段。

**编译查询适用于少数关键接口，而不是代码库里的每一个查询。先性能分析，再编译真正热的那 5%。**

## 用什么：决策矩阵

这些修复方案之间有重叠。以下是我决定先用哪个的规则：

| 症状 | 首选修复 | 然后 |
|------|----------|------|
| 接口返回完整实体，响应体大 | 通过 Select 投影 | 再加 AsNoTracking |
| 一次请求触发 50+ 条 SQL | 加 Include 或投影 | 检查是否开了懒加载 |
| 一次查询为 50 个实体返回 30000 行 | AsSplitQuery | 或用 Select 投影具体列 |
| 批量更新或删除很慢 | ExecuteUpdateAsync / ExecuteDeleteAsync | 50K+ 行考虑 EFCore.BulkExtensions |
| 列表接口在负载下超时 | 加分页 | 再加 AsNoTracking + 投影 |
| WHERE 查询很慢 | 在过滤列上加索引 | 用 EXPLAIN 验证 SQL |
| 高 RPS 热接口 | 用 EF.CompileAsyncQuery 编译查询 | 对稳定读考虑 HybridCache |

经验规则：先修最便宜、影响最大的问题，然后再次测量。大多数 API 只需要修三个问题（投影、AsNoTracking、分页），就能从第 80 百分位跳到第 95 百分位，根本不用碰高级技术。

## EF Core 10 的开箱即用改进

EF Core 10 让其中一些问题更容易修复：

- **`LeftJoin` 和 `RightJoin` 一等公民**：不再需要笨拙的 `GroupJoin` + `SelectMany` + `DefaultIfEmpty` 写法，更简洁的 LINQ，相同的 SQL，更少的坑。

- **分割查询的一致排序**：EF Core 10 修复了一个微妙的正确性问题——`AsSplitQuery` 结合 `Take` 和 `Include` 时，子查询排序可能遗漏主键导致非确定性结果。现在对所有分割查询统一应用相同的排序。

- **更快的实体化**：.NET 10 的 JIT 改进（实体化热路径内联更好、反虚拟化更强、泛型特化开销更低）让每个 EF Core 查询不改一行代码就运行得更快。

- **参数化集合的更好翻译**：EF Core 10 改变了 `IEnumerable.Contains` 的默认翻译，使用带填充的独立标量参数，给查询优化器提供更好的基数信息，同时保留查询计划缓存复用。

这些都不会替你修复那 10 个问题，它们让正确的模式稍微快一点，但救不了错误的模式。

## 关键要点

- **投影 + AsNoTracking + 分页是 80% 解决方案**。默认在所有列表接口上应用这三个。
- **N+1 是头号杀手**。在开发阶段用 `LogTo` 记录 SQL 来检测。用 `Include` 或投影修复。
- **懒加载代理不属于服务端 ASP.NET Core 应用**。使用显式预先加载或投影。
- **`AsSplitQuery` 用于笛卡尔积爆炸**，当你真的需要 2 个以上集合时用它。单集合 Include 默认单查询模式就够了。
- **`ExecuteUpdateAsync` 和 `ExecuteDeleteAsync` 快 300-500 倍**。任何不需要拦截器的批量写操作都用它们。
- **索引和查询结构同样重要**。分析你的热路径查询，给 `WHERE`、`JOIN`、`ORDER BY` 子句中的列加索引。
- **编译查询属于热的 5% 接口**。先性能分析，再编译。
- **每次改动前后都要测量**。用 `LogTo`、`dotnet-trace`、MiniProfiler 或 BenchmarkDotNet。没有测量的性能工作是玄学。

## 常见故障排查

**症状：查询在开发环境快，在生产环境慢。** 最常见的原因是缺索引。开发数据库通常只有几百行，生产有几百万行。100 行时全表扫描不可见，1000 万行时是灾难。在生产查询上运行 `EXPLAIN`（PostgreSQL）或 `SET SHOWPLAN_ALL ON`（SQL Server），检查顺序扫描或表扫描。

**症状：加了 Include 但查询返回了太多行。** 你可能遇到了笛卡尔积爆炸。切换到 `AsSplitQuery()` 或用 `Select()` 投影具体列而不是加载完整实体。

**症状：ExecuteUpdateAsync 运行了但审计日志没触发。** 设计如此。`ExecuteUpdateAsync` 和 `ExecuteDeleteAsync` 绕过变更追踪，意味着 EF Core 拦截器和 `SaveChanges` 里的任何代码都不运行。如果你需要这个行为，坚持用加载再 `SaveChanges` 的模式，或者把审计逻辑移到数据库触发器里。

**症状：全局启用 AsNoTracking 后 SaveChanges 不起作用了。** 把 `QueryTrackingBehavior.NoTracking` 设为默认后，需要在写路径的具体查询上加 `.AsTracking()` 来开启追踪。或者在调用 `SaveChanges` 之前手动附加实体。

**症状：索引没有被查询计划器使用。** 要么这列的基数很低（区分度很少，比如布尔值），要么查询被改写成了禁用索引的形式（比如把列包在函数里，如 `LOWER(Sku) = 'abc'`）。检查查询计划，重写 LINQ 让列保持不被包装。

## 总结

EF Core 很快。框架本身很少是瓶颈，你在它上面写的模式才是。这 10 个问题都来自同一个根本原因：写了看起来正确的代码，测试全绿，等到生产流量到来时才崩溃。

修复不是去学一个新框架，而是在每个接口上坚持应用同样无聊的纪律：投影、`AsNoTracking`、分页、显式预先加载、在过滤列上加索引、基于集合的批量操作，以及对懒加载保持警惕。把这些当作默认值，你就能绕过 90% 最终出现在故障报告里的 EF Core 性能痛点。

## 参考

- [原文：10 EF Core Performance Mistakes (and How to Fix Them) in .NET 10](https://codewithmukesh.com/blog/ef-core-performance-mistakes/)
- [Bulk Operations in EF Core 10 - Benchmarking Insert, Update, and Delete Strategies](https://codewithmukesh.com/blog/bulk-operations-efcore/)
- [Tracking vs. No-Tracking Queries in EF Core 10](https://codewithmukesh.com/blog/tracking-vs-no-tracking-queries-efcore/)
- [Pagination, Sorting & Searching in ASP.NET Core Web API](https://codewithmukesh.com/blog/pagination-sorting-searching-aspnet-core-webapi/)
- [Compiled Queries in EF Core - Benchmarks and Best Practices](https://codewithmukesh.com/blog/compiled-queries-efcore/)
