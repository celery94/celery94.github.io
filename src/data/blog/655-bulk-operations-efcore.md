---
pubDatetime: 2026-03-23T10:00:00+08:00
title: "EF Core 10 批量操作全攻略：插入、更新、删除的策略与性能对比"
description: "系统介绍 EF Core 10 中批量操作的五种方案——SaveChanges 批处理、AddRange、ExecuteUpdate/ExecuteDelete、第三方 BulkExtensions——配合真实基准测试数据与决策矩阵，帮助你在正确的场景选对工具。"
tags: ["dotnet", "efcore", "performance", "entity-framework", "csharp"]
slug: "bulk-operations-efcore"
ogImage: "../../assets/655/01-cover.png"
source: "https://codewithmukesh.com/blog/bulk-operations-efcore/"
---

你写了一个 CSV 导入接口，需要往数据库插入 50,000 条产品记录。代码很简单：循环调用 `context.Products.Add(product)`，最后一次 `SaveChanges()`。运行之后等了五分钟，请求超时了。

EF Core 在帮你生成 50,000 条独立的 `INSERT` 语句，每一条都是一次数据库往返。

批量操作就是为解决这个问题而存在的。

![EF Core 批量操作概念图](../../assets/655/01-cover.png)

---

## 什么是批量操作

批量操作是指用一条或少数几条 SQL 命令一次性影响多行，而不是逐条处理。在 EF Core 10 里，批量操作分三类：

- **批处理 SaveChanges**：EF Core 把多条语句合并成更少的数据库往返
- **基于集合的操作**（`ExecuteUpdate` / `ExecuteDelete`）：LINQ 直接翻译成 SQL `UPDATE` / `DELETE`，不加载实体
- **第三方批量库**（如 EFCore.BulkExtensions）：利用数据库专有特性实现极限吞吐

理解这三类之间的核心区别是：**被跟踪的操作**（经由变更追踪器）和**未跟踪的操作**（直接执行 SQL）。这个区别对拦截器、全局查询过滤器和审计日志都有重大影响。

---

## SaveChanges 的内置批处理

在引入专用 API 之前，先了解 EF Core 本身已经做了什么。调用 `SaveChanges()` 时，EF Core 不是一条条发送 SQL，而是把多条语句合并进更少的数据库往返。

```csharp
// EF Core 会自动把这些操作合并批处理
foreach (var product in products)
{
    context.Products.Add(product);
}
await context.SaveChangesAsync(ct);
```

EF Core 10 配合 PostgreSQL 使用带 `RETURNING` 子句的 `MERGE` 语句，把多条插入合并为一条命令。默认的批次上限是每次往返 42 条语句。插入 100 个实体时，EF Core 大约发送 3 次批处理命令，而不是 100 次。

可以在 `DbContext` 配置中调整批次大小：

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString, npgsql =>
        npgsql.MaxBatchSize(100))); // PostgreSQL 默认是 42
```

增大 `MaxBatchSize` 会减少往返次数，但每条 SQL 命令会更大。对 PostgreSQL 而言，42–100 之间效果最好；超过 200 很少能带来收益，反而可能触及参数上限。

内置批处理对很多场景已经够用，但它仍然要求把每个实体加载到内存并经由变更追踪器生成 SQL。当记录数达到数万乃至十万级别时，这部分开销就会显现出来。

---

## 批量插入：AddRange + SaveChanges

对批量插入最简单的优化是用 `AddRange()` 替代循环里的 `Add()`。两者最终都会被变更追踪器管理，但 `AddRange()` 让 EF Core 知道你在批量添加多个实体，可以优化检测和批处理逻辑。

```csharp
app.MapPost("/products/bulk", async (
    List<CreateProductRequest> requests,
    AppDbContext context,
    CancellationToken ct) =>
{
    var products = requests.Select(r => new Product
    {
        Name = r.Name,
        Price = r.Price,
        Category = r.Category,
        CreatedAt = DateTime.UtcNow
    }).ToList();

    context.Products.AddRange(products);
    await context.SaveChangesAsync(ct);

    return Results.Created($"/products", new { Count = products.Count });
});
```

生成的 SQL 使用批处理插入：

```sql
-- EF Core 把这些合并成带 RETURNING 的多行 INSERT
INSERT INTO "Products" ("Name", "Price", "Category", "CreatedAt")
VALUES (@p0, @p1, @p2, @p3),
       (@p4, @p5, @p6, @p7),
       (@p8, @p9, @p10, @p11)
RETURNING "Id";
```

**适用场景**：数千条以内的插入，`AddRange` + `SaveChanges` 通常就够了。你可以得到完整的变更追踪，拦截器会触发，生成值（如 `Id`）会返回，审计日志也正常工作。

**不适用场景**：超过 10,000 条记录时，创建实体实例、追踪它们、检测变更的开销就会累积成性能瓶颈。

---

## 基于集合的更新：ExecuteUpdate

`ExecuteUpdate` 从 EF Core 7 引入，在 EF Core 10 中继续可用。它把 LINQ 查询直接翻译成 SQL `UPDATE` 语句，不加载实体，不经过变更追踪器，SQL 在数据库端直接执行。

### 更新单个属性

```csharp
// 停用 90 天内未更新的所有产品
var affectedRows = await context.Products
    .Where(p => p.LastModified < DateTime.UtcNow.AddDays(-90))
    .ExecuteUpdateAsync(setters => setters
        .SetProperty(p => p.IsActive, false), ct);
```

生成的 SQL：

```sql
UPDATE "Products"
SET "IsActive" = FALSE
WHERE "LastModified" < @p0;
-- @p0 = '2025-11-18T00:00:00Z'
```

### 更新多个属性

```csharp
// 对电子产品打九折并标记促销
await context.Products
    .Where(p => p.Category == "Electronics" && p.Price > 500)
    .ExecuteUpdateAsync(setters => setters
        .SetProperty(p => p.Price, p => p.Price * 0.9m)
        .SetProperty(p => p.IsOnSale, true)
        .SetProperty(p => p.LastModified, DateTime.UtcNow), ct);
```

注意 `SetProperty` 的第二个参数可以是引用当前值的 lambda（`p => p.Price * 0.9m`），这是做相对更新——递增计数器、应用百分比、拼接字符串——而不需要先把实体加载进来。

### 返回受影响的行数

`ExecuteUpdate` 返回受影响的行数，适合用于并发检查和日志记录：

```csharp
var updated = await context.Products
    .Where(p => p.Id == productId && p.Version == expectedVersion)
    .ExecuteUpdateAsync(setters => setters
        .SetProperty(p => p.Price, newPrice)
        .SetProperty(p => p.Version, p => p.Version + 1), ct);

if (updated == 0)
{
    return Results.Conflict("Product was modified by another user.");
}
```

这是手动乐观并发的推荐模式——因为 `ExecuteUpdate` 绕过了 EF Core 内置的并发令牌检查。

---

## 基于集合的删除：ExecuteDelete

`ExecuteDelete` 和 `ExecuteUpdate` 工作方式相同——把 LINQ 的 `Where` 子句翻译成 SQL `DELETE`，不加载实体直接执行。

```csharp
// 删除所有"已停产"分类的产品
var deleted = await context.Products
    .Where(p => p.Category == "Discontinued")
    .ExecuteDeleteAsync(ct);
```

```sql
DELETE FROM "Products" WHERE "Category" = 'Discontinued';
```

### 级联删除注意事项

如果实体存在从属关系（如 `Product` → `OrderItems`），数据库的级联规则生效，而不是 EF Core 的。外键设置为 `CASCADE` 时数据库处理；设置为 `RESTRICT` 时 `ExecuteDelete` 会抛出数据库异常。

```csharp
// 先删除子表，再删除主表
await context.OrderItems
    .Where(oi => oi.Product.Category == "Discontinued")
    .ExecuteDeleteAsync(ct);

await context.Products
    .Where(p => p.Category == "Discontinued")
    .ExecuteDeleteAsync(ct);
```

### ExecuteDelete 与软删除的陷阱

这里有一个在生产环境中真实发生过的场景。团队有一个定时清理任务：

```csharp
// 看起来没问题——删除过期促销
await context.Products
    .Where(p => p.PromoExpiresAt < DateTime.UtcNow)
    .ExecuteDeleteAsync(ct);
```

这段代码工作了几个月，直到团队引入了带全局查询过滤器的软删除。他们期望 `ExecuteDelete` 会调用 `SaveChangesInterceptor` 并把 `IsDeleted` 设为 `true`，而不是真正删除记录。

结果它没有。`ExecuteDelete` 生成的是原始 SQL `DELETE`——完全绕过了拦截器和变更追踪器。那些促销产品永远消失了，没有 `IsDeleted` 标记，没有审计日志，也无法恢复。

正确的修复方案是对有软删除的实体切换回跟踪操作：

```csharp
// 安全版本——会经过拦截器和软删除逻辑
var expiredProducts = await context.Products
    .Where(p => p.PromoExpiresAt < DateTime.UtcNow)
    .ToListAsync(ct);

context.Products.RemoveRange(expiredProducts);
await context.SaveChangesAsync(ct); // 拦截器把 DELETE 转换为 UPDATE SET IsDeleted = true
```

或者用 `ExecuteUpdate` 手动设置软删除标志：

```csharp
await context.Products
    .Where(p => p.PromoExpiresAt < DateTime.UtcNow)
    .ExecuteUpdateAsync(setters => setters
        .SetProperty(p => p.IsDeleted, true)
        .SetProperty(p => p.DeletedAt, DateTime.UtcNow), ct);
```

**结论**：如果实体参与了软删除，永远不要对它用 `ExecuteDelete`。

---

## 在事务中包裹批量操作

`ExecuteUpdate` 和 `ExecuteDelete` 各自在独立的隐式事务中执行。如果需要多个操作同时成功或回滚，需要用显式事务包裹：

```csharp
await using var transaction = await context.Database.BeginTransactionAsync(ct);

try
{
    // 步骤 1：停用过期产品
    await context.Products
        .Where(p => p.ExpiresAt < DateTime.UtcNow)
        .ExecuteUpdateAsync(setters => setters
            .SetProperty(p => p.IsActive, false), ct);

    // 步骤 2：删除已停用产品的订单项
    await context.OrderItems
        .Where(oi => !oi.Product.IsActive)
        .ExecuteDeleteAsync(ct);

    // 步骤 3：写入清理日志
    context.AuditLogs.Add(new AuditLog
    {
        Action = "BulkCleanup",
        Timestamp = DateTime.UtcNow,
        Details = "Deactivated expired products and removed their order items"
    });
    await context.SaveChangesAsync(ct);

    await transaction.CommitAsync(ct);
}
catch
{
    await transaction.RollbackAsync(ct);
    throw;
}
```

可以在同一个事务里混用 `ExecuteUpdate`、`ExecuteDelete` 和跟踪的 `SaveChanges`——它们共享同一个数据库连接。注意跟踪的 `AuditLog` 实体不会"看到" `ExecuteUpdate`/`ExecuteDelete` 的变更，因为那些操作绕过了变更追踪器。

---

## 第三方库：什么时候需要

对于极大数据量的插入（50K+ 行），原生的 `AddRange` + `SaveChanges` 仍然要把所有实体加载进内存并经由变更追踪器生成 SQL。这就是第三方批量库的用武之地。

### EFCore.BulkExtensions

[EFCore.BulkExtensions](https://github.com/borisdj/EFCore.BulkExtensions) 是一个 MIT 协议的开源库，提供 `BulkInsert`、`BulkUpdate`、`BulkDelete` 和 `BulkInsertOrUpdate`（upsert）。它使用数据库专有的批量复制协议——SQL Server 用 `SqlBulkCopy`，PostgreSQL 用 `COPY`——完全绕过 EF Core 的变更追踪器。

```bash
dotnet add package EFCore.BulkExtensions --version 8.1.3
```

```csharp
using EFCore.BulkExtensions;

// 批量插入——使用 PostgreSQL COPY 协议
var products = GenerateProducts(50_000);
await context.BulkInsertAsync(products, cancellationToken: ct);

// Upsert——根据主键决定插入或更新
var productsToUpsert = GetUpdatedProductFeed();
await context.BulkInsertOrUpdateAsync(productsToUpsert, cancellationToken: ct);
```

### Entity Framework Extensions（付费）

[Entity Framework Extensions](https://entityframework-extensions.net/) 是 ZZZ Projects 出品的商业库，功能更全面——`BulkMerge`、`BulkSynchronize`、条件批量操作等。起步价每年 $599。

### 什么时候该用第三方库

大多数 Web API 从来不需要第三方批量库。作者的判断：

- `AddRange + SaveChanges` 能处理 90% 的真实插入场景（数千条以内）
- `ExecuteUpdate` / `ExecuteDelete` 已覆盖所有基于集合的更新/删除需求，无需引入库
- 第三方库在以下情况才有意义：数据导入（CSV 上传、ETL 管道、数据迁移）且记录数超过 10K 条，或者需要 EF Core 原生不支持的 upsert 语义

最常见的错误是一开始就引入批量库。在 `SaveChanges` 实际变慢之前先别加这个依赖。

---

## 性能基准测试

所有基准测试使用 [BenchmarkDotNet](https://benchmarkdotnet.org/)，测试实体是有 6 列的 `Product`（Id、Name、Price、Category、IsActive、CreatedAt），运行环境为 .NET 10 + EF Core 10 + PostgreSQL 17（Docker），M2 MacBook Pro。

### 插入基准

| 方式 | 100 条 | 1K 条 | 10K 条 | 100K 条 | 内存（100K）|
|------|--------|-------|--------|---------|------------|
| 逐条 Add + SaveChanges | 45 ms | 380 ms | 3,800 ms | 41,200 ms | 285 MB |
| AddRange + SaveChanges | 12 ms | 95 ms | 920 ms | 9,500 ms | 180 MB |
| BulkExtensions BulkInsert | 8 ms | 35 ms | 180 ms | 1,200 ms | 42 MB |
| 原生 Npgsql COPY | 5 ms | 18 ms | 95 ms | 650 ms | 28 MB |

`AddRange` 比逐条插入快 4 倍。100–1,000 条时，`AddRange` 与批量库的差距很小，仅毫秒级。10K+ 时差距就拉开了：`BulkInsert` 在 10K 时快 5 倍，100K 时快 8 倍，内存占用少 77%。

### 更新基准

| 方式 | 100 条 | 1K 条 | 10K 条 | 100K 条 |
|------|--------|-------|--------|---------|
| 加载 + 修改 + SaveChanges | 38 ms | 310 ms | 3,200 ms | 35,800 ms |
| ExecuteUpdate | 3 ms | 3 ms | 4 ms | 5 ms |
| BulkExtensions BulkUpdate | 10 ms | 22 ms | 85 ms | 520 ms |

`ExecuteUpdate` 是第一梯队——无论匹配多少行，它发送的都是单条 SQL，始终 3–5 ms。跟踪方式（加载 + 修改 + 保存）随数据量线性增长，超过 1,000 条就会很痛苦。`BulkUpdate` 介于两者之间，适合需要对每行设置不同值（`ExecuteUpdate` 只能对所有匹配行应用同一转换）的场景。

### 删除基准

| 方式 | 100 条 | 1K 条 | 10K 条 | 100K 条 |
|------|--------|-------|--------|---------|
| 加载 + Remove + SaveChanges | 35 ms | 290 ms | 2,900 ms | 32,000 ms |
| ExecuteDelete | 2 ms | 2 ms | 3 ms | 4 ms |
| BulkExtensions BulkDelete | 8 ms | 18 ms | 65 ms | 380 ms |

和更新一样——`ExecuteDelete` 靠单条 SQL `DELETE` + `WHERE` 子句大幅领先。先查询再逐条删除是最差的选择，因为它先把所有匹配行查出来跟踪，然后逐条生成 `DELETE`。

---

## 决策矩阵

| 场景 | 推荐方案 | 说明 |
|------|---------|----|
| 插入 10–10K 条 | AddRange + SaveChanges | 批处理自动处理，支持变更追踪、生成 ID、拦截器 |
| 插入 10K–100K+ 条（数据导入）| BulkInsert（EFCore.BulkExtensions）| 快 8 倍、省 77% 内存 |
| 按条件统一更新多行 | ExecuteUpdate | 单条 SQL，始终用这个 |
| 每行更新不同值 | 加载 + 修改 + SaveChanges | ExecuteUpdate 不支持按行差异化值 |
| 每行不同值且 10K+ 规模 | BulkUpdate（EFCore.BulkExtensions）| 跟踪更新太慢但每行值不同时 |
| 按条件删除 | ExecuteDelete | 单条 SQL，最快 |
| 有软删除的实体删除 | ExecuteUpdate（设 IsDeleted = true）| ExecuteDelete 会绕过拦截器和全局过滤器 |
| Upsert（插入或更新）| BulkInsertOrUpdate（EFCore.BulkExtensions）| EF Core 原生不支持 upsert |
| 混合操作 | 显式事务包裹各操作 | 在单个事务中组合不同方案 |

---

## 生产环境常见陷阱

### 1. ExecuteUpdate/ExecuteDelete 绕过拦截器

如果你依赖 `SaveChangesInterceptor` 做审计追踪、软删除或时间戳更新，`ExecuteUpdate` 和 `ExecuteDelete` 会完全跳过它们。

**修复**：对需要拦截器行为的实体，使用跟踪操作；或者在 `ExecuteUpdate` 调用里手动包含审计字段：

```csharp
await context.Products
    .Where(p => p.Id == productId)
    .ExecuteUpdateAsync(setters => setters
        .SetProperty(p => p.Price, newPrice)
        .SetProperty(p => p.LastModifiedBy, currentUser)
        .SetProperty(p => p.LastModifiedAt, DateTime.UtcNow), ct);
```

### 2. 变更追踪器状态不同步

在同一个 `DbContext` 范围内混用跟踪操作和 `ExecuteUpdate`/`ExecuteDelete`，变更追踪器不知道批量操作的变更：

```csharp
var product = await context.Products.FindAsync(productId);
// product.Price 是 100，已被变更追踪器跟踪

await context.Products
    .Where(p => p.Id == productId)
    .ExecuteUpdateAsync(setters => setters
        .SetProperty(p => p.Price, 200m), ct);
// 数据库里 Price 现在是 200，但跟踪的实体还是 100

product.Name = "Updated Name";
await context.SaveChangesAsync(ct);
// SaveChanges 检测到 Name 变了，但同时也"检测到" Price 应该是 100
// 这会覆盖 ExecuteUpdate 的更改！
```

**修复**：不要在同一个 `DbContext` 范围内对同一实体混用跟踪和未跟踪操作。用了 `ExecuteUpdate` 之后，重新加载实体或使用新的 `DbContext`。

### 3. 大量插入可能触及内存上限

即使用 `AddRange`，插入 100K 个实体也会在内存里创建 100K 个被跟踪的对象。在 512 MB 容器上这可能触发 `OutOfMemoryException`。

**修复**：把大批量插入分成 5,000–10,000 条的块，每块调用一次 `SaveChanges()`，或者切换到 `BulkInsert`：

```csharp
// 不使用 BulkExtensions 时的分块方案
foreach (var chunk in products.Chunk(5000))
{
    context.Products.AddRange(chunk);
    await context.SaveChangesAsync(ct);
    context.ChangeTracker.Clear(); // 释放跟踪的实体
}
```

### 4. ExecuteUpdate 不支持导航属性

在 `SetProperty` 的 lambda 里不能引用导航属性，否则运行时会抛出异常：

```csharp
// 这样不行
await context.Products
    .ExecuteUpdateAsync(setters => setters
        .SetProperty(p => p.Category.Name, "Updated"), ct); // 抛出异常！
```

**修复**：用子查询加 `Select`，或直接更新关联实体。

---

## 排错指南

**ExecuteUpdate/ExecuteDelete 抛出"could not be translated"**
LINQ 表达式包含无法翻译成 SQL 的方法或属性。简化 `Where` 子句——避免 `ToString()`、复杂字符串操作或自定义方法，坚持使用基本比较、`Contains()` 和算术。

**批量插入时"Cannot insert duplicate key"**
数据中在唯一约束上存在重复。插入前过滤重复项，或使用 EFCore.BulkExtensions 的 `BulkInsertOrUpdate` 做 upsert。

**大批量 SaveChanges 超时**
增加命令超时：`options.UseNpgsql(conn, o => o.CommandTimeout(120))`。同时考虑把大批量分成 5,000–10,000 条的块。

**大量 AddRange 操作内存飙升**
变更追踪器把所有实体保存在内存里。在批次间调用 `context.ChangeTracker.Clear()`，或切换到 `BulkInsert`。

**ExecuteDelete 违反外键约束**
数据库强制引用完整性。先删除从属实体，或在数据库 schema 中配置级联删除。

---

## 关键结论

- `AddRange` + `SaveChanges` 是 ~10K 行以内插入的首选，简单、有变更追踪，EF Core 的批处理让它对大多数 API 足够快
- `ExecuteUpdate` 和 `ExecuteDelete` 对基于集合的操作快得多——无论行数多少都是单条 SQL
- 第三方批量库（EFCore.BulkExtensions）只在原生方案实际不够时才值得引入——通常是 10K+ 插入或需要 upsert
- `ExecuteUpdate`/`ExecuteDelete` 绕过变更追踪器、拦截器和软删除模式，这是第一号生产陷阱
- 在优化前先用 BenchmarkDotNet 测量自己的具体场景，相对性能规律一致，但绝对数字因环境而异

---

## 参考

- [Bulk Operations in EF Core 10 - Benchmarking Insert, Update, and Delete Strategies](https://codewithmukesh.com/blog/bulk-operations-efcore/)
- [EFCore.BulkExtensions GitHub](https://github.com/borisdj/EFCore.BulkExtensions)
- [Microsoft Learn - ExecuteUpdate and ExecuteDelete](https://learn.microsoft.com/en-us/ef/core/saving/execute-insert-update-delete)
- [BenchmarkDotNet](https://benchmarkdotnet.org/)
