---
pubDatetime: 2026-07-15T14:20:19+08:00
title: "EF Core 批量插入终极指南：从 AddRange 到原始 COPY 的六种策略"
description: "EF Core 10 没有内置批量插入 API。这篇从最慢的逐行 SaveChanges 到最快的 Npgsql 二进制 COPY，把六种插入策略全部跑通 BenchmarkDotNet，附带基准数据、参数上限陷阱、内存开销和实际选型建议。"
tags:
  ["EF Core", "Entity Framework Core", "批量插入", "性能", ".NET", "Benchmark"]
slug: "ef-core-bulk-insert-fastest-way"
ogImage: "../../assets/943/01-cover.png"
source: "https://codewithmukesh.com/blog/ef-core-bulk-insert/"
---

EF Core 批量插入最快的方法是别让 EF Core 来做插入。真到了量大的时候，用数据库自己的批量复制协议：PostgreSQL 的二进制 `COPY` 或 SQL Server 的 `SqlBulkCopy`。几千行以内，`AddRange` 加一次 `SaveChanges` 完全够用。但有一件事要先说清楚：**EF Core 10 没有内置的批量插入 API**，吞吐量永远取决于你愿意离 change tracker 多远。

我在 .NET 10 和 EF Core 10 上对 PostgreSQL 17 把六种插入策略全跑了一遍 BenchmarkDotNet——从所有人起步时都会写的那种朴素循环，到原始二进制 `COPY`。最慢和最快之间差了不止几倍，是超过两个数量级。

## EF Core 有没有内置的批量插入

没有。EF Core 10 没提供 `ExecuteInsert` 之类的东西。EF Core 7 加了 `ExecuteUpdate` 和 `ExecuteDelete` 做集合级的更新和删除，但官方文档明确写了插入不在支持范围内：**插入必须通过 `DbSet<TEntity>.Add` 和 `SaveChanges()` 完成**。

这意味着每次原生 EF Core 插入都要走 change tracker：你创建实体实例，EF 跟踪它们，`SaveChanges` 把标记为 `Added` 的实体转成 SQL。正常请求里保存一个订单，这套机制刚好是你需要的。但当你从 CSV 导入往里灌 50000 行时，这就是纯开销。

## 为什么我的批量插入这么慢

最常见的原因就是把 `SaveChanges()` 放在循环里面。每次调用就是一次数据库往返，插入 10000 行就是 10000 次顺序往返。

```csharp
// 最慢的写法，绝对不要这么做
foreach (var product in products)
{
    context.Products.Add(product);
    await context.SaveChangesAsync(ct); // 每行一次往返
}
```

本地数据库一次往返几毫秒看着不贵，乘上 10000 加上到真服务器的网络延迟，这就是把两秒的导入变成五分钟的那种代码。这种写法在小数据量测试里能跑通，code review 也看不出毛病，上线就炸。

把 `SaveChanges` 移到循环外面，让 EF Core 自动批处理：

```csharp
foreach (var product in products)
    context.Products.Add(product);
await context.SaveChangesAsync(ct); // 一次调用，批量往返
```

### AddRange 比 foreach 循环快吗

快一点，而且读起来更干净。但在 EF Core 10 里差异远没有以前大，因为 `Add` 在循环里只对刚加的单实体图跑局部变更检测，不是全量扫描。那个"AddRange 比 Add 循环快十倍"的说法是 EF6 时代的遗产。

所以用 `AddRange` 因为更干净、边际上快一点，别当它是魔法开关：

```csharp
context.Products.AddRange(products);
await context.SaveChangesAsync(ct);
```

## 上万行该怎么做

分块插入，在块之间调 `ChangeTracker.Clear()`。即使用了 `AddRange`，每一个加进去的实体都会在内存里被跟踪直到 context 被清掉或释放。100000 个实体塞进一个 context，就是 100000 个被跟踪对象加上它们的变更快照。在内存受限的容器里这就是 `OutOfMemoryException`。

```csharp
context.ChangeTracker.AutoDetectChangesEnabled = false;
foreach (var chunk in products.Chunk(5000))
{
    context.Products.AddRange(chunk);
    await context.SaveChangesAsync(ct);
    context.ChangeTracker.Clear(); // 清掉跟踪，释放内存
}
```

块大小 1000 到 10000 是个合理起点，按行宽微调。这套保持在原生 EF Core 范畴内，意味着生成的 ID 和拦截器都还在。对大了但不算巨量的导入，这是甜点区。

## 为什么小数据量能跑大数据量就挂

罪魁祸首通常是数据库的参数上限。EF Core 批量插入把每个值都变成查询参数，两个主流 Provider 都对单命令的参数数量有硬上限：

- **SQL Server：2100 个参数**每命令。报错信息是："The incoming request has too many parameters. The server supports a maximum of 2100 parameters."
- **PostgreSQL：65535 个参数**每命令，因为线协议用 16 位整数编码参数数量。

这里有坑。批量插入约等于 `行数 × 每行列数` 个参数。宽表很容易就炸了——一个 60 列的表，每批才 40 行就已经 2400 个参数，超了 SQL Server 的线。这也是为什么 SQL Server 的默认批处理上限是保守的 42。

参数上限虽然通常写在文档里，但真正踩到的时候心态还是会崩。顺便提三个也常挂的场景：**命令超时**（默认 30 秒，用 `context.Database.SetCommandTimeout(120)` 拉高）、**一个超大事务包住所有行**（分块提交更健康）、**重复主键**（插入前先去重，或走 upsert）。

## 绝对最快的批量插入

用数据库自己的批量复制协议，跳过 EF Core。PostgreSQL 上就是二进制 `COPY`，SQL Server 上是 `SqlBulkCopy`。两者都用数据库自己的格式流式写行，没有按行参数绑定，没有变更跟踪，这就是它们远胜其他方案的原因。

### PostgreSQL：Npgsql 二进制 COPY

Npgsql 的二进制导入是往 PostgreSQL 灌数据最快的方式，大约是普通 `INSERT` 的 3 倍：

```csharp
await using var writer = await connection.BeginBinaryImportAsync(
    "COPY \"Products\" (\"Name\", \"Sku\", \"Price\",
     \"Category\", \"CreatedAtUtc\") FROM STDIN (FORMAT BINARY)", ct);

foreach (var product in products)
{
    await writer.StartRowAsync(ct);
    await writer.WriteAsync(product.Name, NpgsqlDbType.Varchar, ct);
    await writer.WriteAsync(product.Sku, NpgsqlDbType.Varchar, ct);
    await writer.WriteAsync(product.Price, NpgsqlDbType.Numeric, ct);
    await writer.WriteAsync(product.Category, NpgsqlDbType.Varchar, ct);
    await writer.WriteAsync(product.CreatedAtUtc,
        NpgsqlDbType.TimestampTz, ct);
}

await writer.CompleteAsync(ct); // 必调——跳过就全部回滚
```

坑只有一个：`CompleteAsync()` 是必须的。如果在没调用它的情况下 dispose 了 writer，Npgsql 会认为导入失败，把一切回滚。不报错、没数据、空表。

### SQL Server：SqlBulkCopy

```csharp
using var bulk = new SqlBulkCopy(connectionString)
{
    DestinationTableName = "dbo.Products",
    BatchSize = 10_000,
    BulkCopyTimeout = 120
};
bulk.ColumnMappings.Add("Name", "Name");
// ... 其余列映射

await bulk.WriteToServerAsync(dataTable, ct);
```

列映射要显式写；不写的话是按位置映射，列顺序变一下就悄悄出错。`SqlBulkCopyOptions.TableLock` 在自己拥有的表上能开最小日志，大导入时有实打实的速度提升。

两个原生路径的代价也一样：不返回生成的 ID，不触发拦截器，审计戳和软删除逻辑都不会跑。

## 什么时候用批量插入库

当你想要接近原生路径的速度、同时还想用 EF Core 实体而不是手写 `COPY` 流的时候。两个主流方案都在你的 `DbContext` 上加一个 `BulkInsert`，底层用 Provider 的批量协议——SQL Server 上 `SqlBulkCopy`，PostgreSQL 上二进制 `COPY`。

**Entity Framework Extensions** 是成熟的全功能方案：`BulkInsert`、`BulkUpdate`、`BulkDelete`、`BulkMerge`（upsert）——还附带 `BulkSynchronize` 和 `BulkSaveChanges`，直接挂在 context 上。覆盖面最广：SQL Server、PostgreSQL、MySQL、Oracle、SQLite。官方基准测试显示比原生快最多 14 倍、节省 94% 保存时间。它是付费库，每月发布新版本时会刷新试用。

```csharp
using Z.EntityFramework.Extensions;
await context.BulkInsertAsync(products);
await context.BulkMergeAsync(products); // 批量 upsert
```

**EFCore.BulkExtensions** 是社区方案，年收入约 100 万美元以下的个人和组织免费，之上需要付费商用许可。一个独立的 `EFCore.BulkExtensions.MIT` 包保持在旧的 MIT 条款下：

```csharp
using EFCore.BulkExtensions;
await context.BulkInsertAsync(products, cancellationToken: ct);
```

用 `BulkInsert` 时注意：默认不填充实体里数据库生成的 ID。需要的话就设 `SetOutputIdentity = true`，但它不是免费的，要走临时表和 `OUTPUT`/`MERGE` 路径关联主键。

## 基准数据：各种方案差多少

我用 BenchmarkDotNet 在 .NET 10 + EF Core 10 上对 Docker 里的 PostgreSQL 17 跑了全部六种策略。实体是普通 8 列 `Product`。绝对时间取决于你的硬件、表宽、索引和网络延迟，**相对排序**才是稳定的结论。

| 策略                                 | 1000 行 | 10000 行  | 分配（10K） |
| ------------------------------------ | ------- | --------- | ----------- |
| `Add` + `SaveChanges` 每行           | 975 ms  | ~31500 ms | ~24.7 GB    |
| `AddRange` + 一次 `SaveChanges`      | 73 ms   | 685 ms    | 102 MB      |
| `AddRange`，AutoDetectChanges 关     | 62 ms   | 658 ms    | 97 MB       |
| 分块 `AddRange` + `Clear()`          | 70 ms   | 670 ms    | 97 MB       |
| `EFCore.BulkExtensions` `BulkInsert` | 54 ms   | 150 ms    | 4 MB        |
| 原始 Npgsql 二进制 `COPY`            | 50 ms   | 120 ms    | 0.5 MB      |

要点：逐行 `SaveChanges` 是灾难，随行数线性增长；`AddRange` + 一次 `SaveChanges` 对几千行足够好；从 `EFCore.BulkExtensions` 和原始 `COPY` 开始拉开差距，且差距随行数扩大。内存同样重要：原生跟踪路径分配大得多，`BulkInsert` 和原始 `COPY` 流式处理几乎不涨。

## 实际选型建议

从原生起步，只在真实数字告诉你不够时才爬梯子。

| 场景                          | 方案                            | 原因                          |
| ----------------------------- | ------------------------------- | ----------------------------- |
| ≤2000 行，正常请求            | `AddRange` + 一次 `SaveChanges` | 批处理能搞定，ID 和拦截器都在 |
| 2000-50000 行，需要 ID/拦截器 | 分块 `AddRange` + `Clear()`     | 保持原生，控制内存            |
| 10000+ 行，用实体，在意速度   | 批量库 `BulkInsert`             | 批量协议 + EF 手感            |
| 海量一次性导入/ETL            | 原始 `COPY` / `SqlBulkCopy`     | 最快，无跟踪，无参数天花板    |
| 宽表撞参数上限                | 原始 `COPY` / `SqlBulkCopy`     | 流式绕过 2100/65535 限制      |

越多像"灌洪水一样倒数据进去、不拿回来"，就越往右走。越多像"保存应用还要继续用的实体"，就越往左走。

## 关键要点

- EF Core 10 没有原生批量插入——所有插入都走 `Add`/`AddRange` + `SaveChanges` 和 change tracker
- 头号错误是循环里调 `SaveChanges`——移出来让 EF Core 批处理
- `AddRange` + 一次 `SaveChanges` 是几千行以内的正确默认做法
- 绝对最快是原始 Cooy / SqlBulkCopy，跳过参数绑定和跟踪
- 注意参数上限（SQL Server 2100、PostgreSQL 65535），原生路径不返回生成 ID、不触发拦截器
- 批量插入后需要生成 ID？要么走原生 `SaveChanges` 路径，要么给 `SetOutputIdentity = true` 付一笔性能代价

## 参考

- [原文链接](https://codewithmukesh.com/blog/ef-core-bulk-insert/)
- [示例仓库](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/02-database-management-with-ef-core/ef-core-bulk-insert)
