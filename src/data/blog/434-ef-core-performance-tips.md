---
pubDatetime: 2025-08-15
tags: ["Entity Framework", "EF Core", "性能优化", "数据库"]
slug: ef-core-performance-tips
source: https://thecodeman.net/posts/4-entity-framework-tips-to-improve-performances
title: 提升EF Core性能的4个实用技巧
description: 本文深入探讨如何通过4个实用技巧大幅提升Entity Framework Core的性能，包括避免循环查询、仅选择必要字段、使用NoTracking和SplitQuery。每个技巧配有示例代码与性能基准图，适合初学者和有经验的开发者。
---

## 提升EF Core性能的4个实用技巧

Entity Framework Core（EF Core）提供了极高的开发效率，但ORM的抽象也可能隐藏昂贵的数据库操作。下面我把原来的四个技巧扩展为更专业的说明：原理、适用场景、折衷与进阶实践（包含代码示例与测量建议），便于在工程化场景中落地。

### 1) 避免在循环中对数据库发起查询（N+1）——原理与应对

问题：在循环体内对数据库逐条查询会导致大量往返（RTT）与多次查询计划解析，表现为“N+1 查询”问题（主查询1次 + 每条记录一个额外查询）。在高并发或数据量大的场景，这会迅速成为瓶颈。

对策：一次性按集合或批量查询，或采用关联加载（Include/ThenInclude）与投影（Select）来减少往返次数。

示例（坏）：

```csharp
for (int i = 0; i < ids.Count; i++)
{
    var e = context.MyEntities.FirstOrDefault(x => x.Id == ids[i]);
    // 每次循环发一条 SQL
}
```

改进（好）：一次性查询并在内存中处理：

```csharp
var entities = context.MyEntities
    .Where(e => ids.Contains(e.Id))
    .ToList(); // 单次 SQL

// 或者按键构建字典以 O(1) 查找
var map = entities.ToDictionary(e => e.Id);
```

进阶建议：

- 对于分页场景，尽量使用Keyset（基于索引的游标）分页代替 Skip/Take，以避免大偏移带来的索引扫描。
- 当需要加载复杂导航集合且集合较大时，使用分步查询（见第4点SplitQuery）或按需分页加载导航集合。

性能测量：开启EF Core日志（LogLevel.Information/Debug）观察生成的 SQL；使用数据库的慢查询日志或执行计划（EXPLAIN/SET STATISTICS）验证总SQL次数与时间。

### 2) 只选择需要的字段（Projection）——减少传输与内存

原理：默认实体查询会把表的所有列映射到实体属性，数据库发送与反序列化成本高。通过投影到匿名类型或DTO，仅检索必要列可显著减少网络带宽、IO与GC压力。

示例：

```csharp
// 好：只查询必要列到 DTO
var results = context.Orders
    .Where(o => o.Status == OrderStatus.Paid)
    .Select(o => new OrderDto { Id = o.Id, Total = o.TotalAmount, CustomerName = o.Customer.Name })
    .ToList();

// 不好：加载完整 Order 实体和大量导航
var all = context.Orders.ToList();
```

进阶：

- 对于只读展示页，用投影构建 DTO 并标记成无跟踪（AsNoTracking）以获得最大收益。
- 若投影包含导航属性，应注意产生的 JOIN 可能导致重复行；在必要时配合 GroupBy 或使用 AsSplitQuery/Distinct。

注意事项：

- 不要把投影后再 Attach 到 DbContext 期待 EF 能跟踪更新（投影结果通常是非实体类型）。

### 3) AsNoTracking 与 AsNoTrackingWithIdentityResolution 的使用场景

原理：默认情况下，EF Core 会将查询出的实体放进 ChangeTracker，以便后续变更检测与保存，但这会带来内存与 CPU 成本。对于只读场景禁用跟踪可以显著提高吞吐。

API 对比：

- AsNoTracking(): 不对实体做跟踪，适用于大多数只读查询。
- AsNoTrackingWithIdentityResolution(): 在只读场景下保留同一主键的对象引用一致性（避免重复实体）——适用于当你需要在投影或多个 Include 中仍然希望实体引用唯一时。

示例：

```csharp
var list = context.Products
    .AsNoTracking()
    .Where(p => p.IsActive)
    .ToList();

// 包含多个 Include 且仍希望保持实体引用一致
var complex = context.Orders
    .Include(o => o.Items)
    .ThenInclude(i => i.Product)
    .AsNoTrackingWithIdentityResolution()
    .ToList();
```

进阶建议：

- 在 Web 请求中默认把查询设置为无跟踪（如果不需要在同一个请求内修改实体），可以将仓储层统一处理。
- 对于短生命周期上下文（例如每请求一个 DbContext），跟踪开销相对小，但在大批量读取时仍然受益明显。

测量方法：对比同一查询在 AsNoTracking 和 默认下的内存占用（dotnet-counters / Performance Profiler）与执行时间。

### 4) Include 的代价与 AsSplitQuery（避免笛卡尔爆炸）

问题：当使用 Include 加载多个一对多或多对多导航时，EF Core 默认会生成一个包含多个 JOIN 的单一 SQL（Single Query）。这会导致行重复（父行被子行重复展开），在父行与子行数量都较大时出现“笛卡尔爆炸”。

解决方案：

- 对于容易造成重复扩展的情况，使用 AsSplitQuery() 将查询拆成多条 SQL，各自加载父体与每个导航集合，然后在应用层合并（EF 会负责合并）。
- 当数据量不大且数据库侧 JOIN 性能优秀时，Single Query 可能更好（减少往返）。因此需要根据关系基数与索引情况权衡。

示例：

```csharp
// 可能导致笛卡尔爆炸的单条查询
var q1 = context.Authors
    .Include(a => a.Books)
    .Include(a => a.Addresses)
    .ToList();

// 拆分查询以避免重复传输
var q2 = context.Authors
    .Include(a => a.Books)
    .Include(a => a.Addresses)
    .AsSplitQuery()
    .ToList();
```

注意：AsSplitQuery 会产生多条 SQL，所以对数据库连接/网络延迟敏感的场景需谨慎；另外，EF Core 从某些版本开始对 Include 的行为与默认策略进行了改进（请参考你使用的 EF Core 版本文档）。

进阶优化（超出本文四招，但非常有用）：

- 编译查询（EF.CompileQuery / EF.CompileAsyncQuery）用于高重复查询以减少表达式树到 SQL 的开销；
- 批量更新/删除：EF Core 7+ 提供 ExecuteUpdate/ExecuteDelete，可在数据库端一次性执行更新或删除，避免加载到内存；对于更复杂或更高性能需求，可以使用第三方库（例如 EFCore.BulkExtensions）；
- 预准备语句与连接池：启用长期连接池与适当的命令超时，避免频繁建立/关闭连接；
- 索引与查询计划：确保对 WHERE/ORDER/GROUP BY 中使用的列建立合适索引，使用数据库分析工具查看查询计划。

示例：编译查询

```csharp
private static readonly Func<MyDbContext, int, MyEntity?> _compiledById =
    EF.CompileQuery((MyDbContext ctx, int id) =>
        ctx.MyEntities.FirstOrDefault(e => e.Id == id));

// 使用
var entity = _compiledById(context, 123);
```

更多测量建议：

- 在开发环境中使用 MiniProfiler、EF Core 日志和数据库执行计划联合追踪真实请求路径与热点 SQL；
- 写基准脚本（例如用 BenchmarkDotNet 或自定义负载脚本）在尽可能接近生产的数据集上验证优化带来的真实收益；
- 关注端到端成本：减少 SQL 数量 vs 减少单条 SQL 的复杂性（哪一项在你的环境中更重要）通常取决于网络延迟、数据库性能与数据基数。

## 实用清单（工程化建议）

- 在代码评审中检查是否存在循环内查询（N+1）；
- 使用投影（Select -> DTO）进行只读查询；
- 默认对只读查询使用 AsNoTracking；对复杂 Include 考虑 AsNoTrackingWithIdentityResolution；
- 对多个 Include 或高基数关系评估 AsSplitQuery 的利弊；
- 对高频查询使用编译查询；
- 使用数据库分析工具（慢查询日志、执行计划）验证优化效果；
- 在 CI 或本地构建小规模基准，保证优化不会引入语义错误。

## 小结

EF Core 的性能调优不是单次行为，而是一个持续的工程实践：先测量、再优化、再验证。本文把常见的四个技巧扩展为可操作的工程建议，并补充了进阶实践（编译查询、批量操作、索引与执行计划分析）。按需逐项实施并以数据驱动决策，通常能在不牺牲可维护性的前提下把性能提升数倍。
