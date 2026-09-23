---
pubDatetime: 2026-09-23T08:48:00+08:00
title: "EF Core Specification 性能与翻译陷阱"
description: "Specification 本身不决定 EF Core 查询快慢，决定性能的是它包住的查询信封。这篇给出从 provider 边界到执行计划的十条诊断路径，并补上 EF Core 10 三条影响取证结论的官方变化。"
tags: ["EF Core", ".NET 10", "Specification Pattern", "性能优化", "LINQ"]
slug: "ef-core-specification-pattern-performance"
ogImage: "../../assets/1084/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/22/specification-pattern-performance-and-ef-core-translation-traps"
---

一个 `ListAsync(specification)` 调用看起来只有一行。它背后至少有四个互不相同的环节：表达式树被翻译成 SQL、数据库挑执行计划、命令往返、行变成对象。性能问题几乎不出现在 Specification 这个名字上，而是出现在这四个环节里你没有看见的那一个。

Dev Leader 的 Nick Cosentino 在[原文](https://www.devleader.ca/2026/09/22/specification-pattern-performance-and-ef-core-translation-traps)里给出的做法是：先把 specification 定义成一个「查询信封」（query envelope），再逐层取证。他的结论是不要给 specification 贴「快」或「慢」的标签，要读 SQL、数命令、记耗时、看执行计划。

下面保留这条主线，并补三块原文没有展开的内容：EF Core 10 里三条直接影响取证结论的官方变化、怎么读诊断输出，以及我在本机复现这些行为时的实际记录。

验证环境是 .NET 10、EF Core 10.0.12、`Microsoft.EntityFrameworkCore.Sqlite`，配 4 行样例数据。SQLite 的翻译结果不能代表 SQL Server 或其他 provider，这一点原文也强调过。

## 先分清你手上的是谓词还是查询信封

只有 `IsSatisfiedBy` 的纯领域 specification 不生成 SQL。EF 翻译和数据库性能根本轮不到它，讨论它快慢没有意义。会走到数据库的是完整信封：条件，加上投影、排序、结果上界、加载策略、过滤器、标签和执行方式里的若干项。

把信封拆开，每一层各管一件事：

| 层                      | 决定什么                                        |
| ----------------------- | ----------------------------------------------- |
| criterion（条件）       | 哪些行可能匹配                                  |
| query shape（查询形状） | 请求哪些列、哪些关系、什么顺序、多大范围        |
| provider                | 哪些表达式节点和方法能被翻译                    |
| database                | 用哪套 schema、索引、统计信息和参数来定执行计划 |
| materialization（物化） | 行在哪个时刻变成 .NET 对象或值                  |

前两层是你写下的，后两层你控制不了。信封的价值是让这些决定有名字、可检查；风险是 `ListAsync(specification)` 把它们全藏起来。

## 翻译在 provider 边界失败，不会静默降级

表达式树合法，不等于 provider 支持它。C# 编译器只保证这个 lambda 能被表示成表达式树；把节点、成员和方法翻成数据库命令是 EF Core 和 provider 的活。

我本机跑的失败例子就是原文那个 helper 方法：

```csharp
public static bool HasPrefixIgnoreCase(string customerName, string prefix) =>
    customerName.StartsWith(prefix, StringComparison.OrdinalIgnoreCase);
```

把它放进 `Where`，执行时抛 `System.InvalidOperationException`，消息里明确写了 `could not be translated` 和 `Translation of method '...HasPrefixIgnoreCase' failed`，并提示要么改写，要么显式调用 `AsEnumerable` 或 `ToListAsync` 切到客户端求值。

这里有个长期被误传的点值得说清：**现代 EF Core 不会把无法翻译的 `Where` 悄悄降级成客户端过滤。** 客户端求值只在最终投影里被允许。所以「先在客户端筛一遍」不是默认行为，是需要你自己写出来的决定。

修正方式也不是「别用 helper 方法」，而是让会走到 provider 的表达式保持可翻译：

```csharp
var specification = new QuerySpecification<Order>(
    order => order.CustomerName.StartsWith(normalizedPrefix));
```

同一条查询在我的实验里翻出的是：

```sql
SELECT "o"."Id", "o"."CustomerName", "o"."CreatedAt"
FROM "Orders" AS "o"
WHERE NOT ("o"."IsDeleted") AND "o"."TenantId" = @ef_filter__TenantId
  AND "o"."CustomerName" LIKE 'Ac%'
ORDER BY "o"."CreatedAt" DESC, "o"."Id"
LIMIT @p
```

两个细节。`StartsWith` 变成了 `LIKE 'Ac%'`，这是 provider 自己的选择。`WHERE` 里除了我写的条件，还有两个全局过滤器的痕迹，见后面全局过滤器那一节。

`StartsWith` 同样不是跨 provider 的承诺。字符串比较的大小写和排序规则由 provider 和数据库决定，换 provider 就要重跑一遍。

### 版本与验证环境

原文的模型面向 .NET 10、C# 14 和 EF Core 10.0.10。EF Core 10.0 是 2025 年 11 月发布的 LTS，支持到 2028 年 11 月 10 日，需要 .NET 10 SDK 和运行时；写这篇时的最新补丁是 10.0.12，官方建议始终跟到最新补丁。

顺带一个真实的 provider 边界教训。我最初把 `CreatedAt` 写成 `DateTimeOffset`，SQLite 直接拒绝翻译排序：

```text
System.NotSupportedException: SQLite does not support expressions of type
'DateTimeOffset' in ORDER BY clauses. Convert the values to a supported type,
or use LINQ to Objects to order the results on the client side.
```

同一条 LINQ 在 SQL Server 上没有这个问题。这就是为什么「在 SQLite 上跑通了」不能当成别的 provider 的结论。

## 每一个物化调用都是一条边界

`IQueryable<T>` 在枚举之前只是表达式加 provider。`ToListAsync`、`SingleAsync`、`CountAsync`、`FirstOrDefaultAsync` 会执行查询；`AsEnumerable` 和 `AsAsyncEnumerable` 明确把后续组合切到客户端 LINQ，`ToList` 和 `ToArray` 把结果缓冲下来。

所以这两条链要区别对待：

```text
IQueryable -> Where -> Select -> Take -> ToListAsync
IQueryable -> ToListAsync -> Where -> Select
```

第二条在小数据集上和第一条返回同样的值，但请求的数据量完全不同：第一条让 provider 在数据库里过滤、投影、限行，第二条先把行搬过来再在 .NET 里处理。

实践约束有三条：终结操作要在 evaluator 或仓储里显式出现；`CancellationToken` 要传到终结操作上；`Compile()`、`AsEnumerable`、无界 `ToListAsync` 不要藏在条件组合的内部。

客户端边界不是禁忌。一个有界的小结果集如果需要 provider 翻不出来的本地转换，切到客户端是合理选择。取舍说清楚就行：服务端干活减少传输的行和列，客户端干活换来任意 .NET 行为。选之前先量实际数据量。

## 四件证据：SQL、命令数、耗时、行数

`ToQueryString()` 是调试产物。API 文档的原话是它「may not be suitable for direct execution」，只用于调试。有意思的是在 SQLite provider 上，EF Core 10 的 `ToQueryString()` 会先输出 `.param set` 声明再输出 SQL，看起来就是给 sqlite3 命令行直接用的——但文档的免责说明没变，所以看过 SQL 之后仍然要真跑一遍。

命令数用拦截器来数，原文给的就是这一种：

```csharp
public sealed class ReaderCommandCounter : DbCommandInterceptor
{
    private int _readerCommands;

    public int ReaderCommands => Volatile.Read(ref _readerCommands);

    public void Reset() => Interlocked.Exchange(ref _readerCommands, 0);

    public override ValueTask<InterceptionResult<DbDataReader>> ReaderExecutingAsync(
        DbCommand command,
        CommandEventData eventData,
        InterceptionResult<DbDataReader> result,
        CancellationToken cancellationToken = default)
    {
        Interlocked.Increment(ref _readerCommands);
        return ValueTask.FromResult(result);
    }
}
```

有了这四个数，症状就能对上原因：

| 看到的                                | 大概率是什么                                   |
| ------------------------------------- | ---------------------------------------------- |
| 命令数 1，SQL 里有 `WHERE` 和 `LIMIT` | 正常，过滤和限行都在服务端                     |
| 命令数随父行数线性增长                | N+1                                            |
| 返回行数远大于投影后的行数            | 笛卡尔积，或上界失效                           |
| SQL 里没有预期的 `WHERE`              | 过滤器被绕过，或已被 `IgnoreQueryFilters` 放开 |
| 命令数正常但耗时长                    | 去执行计划里找扫描和统计信息问题               |

### 内联常量在日志里的样子变了

这条直接影响取证。EF 记录 SQL 时默认不写参数值，因为可能含敏感信息；但 EF 有时会把参数内联进 SQL，以前这些值会照原样打进日志。EF Core 10 不再这样，内联参数默认被替换成 `?`。

我用 `EF.Constant(statuses).Contains(order.Status)` 打出来的命令日志是：

```text
Executed DbCommand (0ms) [Parameters=[@ef_filter__TenantId='?' (DbType = Guid)], ...]
SELECT "o"."Id", "o"."CreatedAt", "o"."CustomerName", "o"."IsDeleted", "o"."Status", "o"."TenantId"
FROM "Orders" AS "o"
WHERE NOT ("o"."IsDeleted") AND "o"."TenantId" = @ef_filter__TenantId
  AND "o"."Status" IN (?, ?)
```

发给数据库的 SQL 是带真实值的，只有日志被替换。拿日志里的 `?` 去比对数据库计划时要记住这一点；要看到真实值就得显式打开 `EnableSensitiveDataLogging`，生产环境要谨慎。

还有一条和 SQL 文本数量有关的 EF Core 10 变化：参数化集合的默认翻译从 JSON 数组改成了「每个值一个标量参数」，并且会填充参数列表。我传 8 个 `Guid`，生成的是：

```sql
IN (@ids1, @ids2, @ids3, @ids4, @ids5, @ids6, @ids7, @ids8, @ids9, @ids10)
```

后两个参数是填充出来的。含义是：不同基数仍然产生不同 SQL，但填充把 SQL 变体的数量压住了。这会影响「计划缓存里为什么还有多个变体」这类判断，也是审查 SQL 文本时容易看错的地方。

## 投影、上界、索引要一起判断

这四件事各有代价，不能只优化其中一个：

- **实体物化**支持变更跟踪和领域行为，但可能取回比这次读操作需要更多的状态。
- **DTO 投影**减少选取的数据，在没有投影实体时也避开了跟踪，代价是要有一份显式的结果约定。
- **硬性结果上界**保护内存和传输量，但调用方需要能知道可能还有更多结果。
- **索引**能帮到过滤和排序，但会增加写入和存储成本，而且优化器不一定选它。

索引这一点最容易被误导：**不要从 LINQ 形状或模型配置推断索引被用上了。** 用代表性参数去执行，然后在生产库上看执行计划。EF 的性能诊断文档把执行计划列为定位到问题查询之后的下一步。

## N+1 和笛卡尔积不是同一个问题

一个是命令数量问题，一个是单条查询的行放大问题，所以一种修法解决不了两种症状。

**N+1** 出现在加载父行之后，每一行再触发一次关联查询，常见来源是延迟加载或循环里的重复显式查询。命令日志或拦截器能看到重复往返。我的实验里，2 条父行加逐行查询是 3 条命令——结果完全正确，命令数已经不对了。

**笛卡尔积**出现在一条查询 join 了同级的多个集合导航时。数据库返回叉积，行被成倍放大，主体数据重复，`AsSplitQuery` 把叉积换成额外的命令。

两种模式都不绝对更好：

- 单查询省往返，但会传重复行。
- 拆分查询免掉同级叉积，但增加命令，可能缓冲中间结果，而且在多条命令之间发生并发修改时会读到不一致的数据。
- 投影常常能直接绕开整个实体图，只取这次读操作真正需要的列。

EF Core 10 修掉了拆分查询的一个隐患：带 `OrderBy` 和 `Take` 的拆分查询，以前子查询里的排序会漏掉并列值上的第二排序列，可能返回错误的数据；EF Core 10 让多条命令的排序保持一致。这降低了拆分查询的一致性风险，但命令之间仍然可能读到不同时间点的数据，取舍没有消失。

诊断顺序照旧是证据优先：数命令、看 SQL 里的 join 和选取列、记返回行数和载荷特征、对比投影、单查询和拆分查询三种方案、最后看执行计划并重复测量。

不要用 EF InMemory provider 做这件事：它不产生关系型 SQL，也证明不了 provider 的往返行为。

## 全局过滤器也算在有效 specification 里

全局查询过滤器是模型级谓词，EF 在你查这个实体时自动加上。这意味着**有效查询等于可见的 specification 条件加上每一个生效的全局过滤器。**

前面那段 SQL 里就有它们的痕迹：`WHERE NOT ("o"."IsDeleted") AND "o"."TenantId" = @ef_filter__TenantId`。注意租户 ID 是作为参数出现的，不是常量——这既让计划可以复用，也意味着过滤器状态改变了 SQL 形状和数据范围。

影响诊断的地方有几处：

- 租户或软删除过滤器会改写 `WHERE`。
- `IgnoreQueryFilters()` 会改变有效数据范围。
- 必需导航加上被过滤的主体，可能通过 inner join 把行直接删掉。
- 忽略过滤器状态的缓存键，会把两个语义不同的查询当成同一条。

EF Core 10 在这里加了一个实用能力：命名过滤器。

```csharp
entity.HasQueryFilter("SoftDeletionFilter", order => !order.IsDeleted);
entity.HasQueryFilter("TenantFilter", order => order.TenantId == tenantId);
```

并且可以按名字选择性绕过：

```csharp
var withDeleted = await db
    .Orders.IgnoreQueryFilters(["SoftDeletionFilter"])
    .CountAsync();
```

我的实验里，两个过滤器都生效时是 2 行；绕过软删除得到 3 行，多出来的是那条已删除的订单；绕过租户也是 3 行，但多出来的是另一个租户的数据——同一个数字，完全不同的行集合。

实践建议是把「绕过过滤器」当成需要审查的基础设施能力，而不是一个用户可控的 specification 选项。

## 编译查询和缓存键：先测量再优化

EF Core 已经按表达式树的形状缓存翻译结果，所以显式编译查询省下的是常规缓存查找那一步。它适合形状固定、参数是标量、并且经过测量的热路径。限制也很明确：一个编译查询绑定一个 EF 模型，形状固定，任意 specification 表达式不能当作它的通用参数，动态嵌入常量会导致反复编译。

更关键的是：**编译不会修复烂 SQL、过多的行或重复往返。** 它优化的是编译开销，不是查询本身。

缓存键那边，判断标准是相等的键是否意味着对这份缓存的用途来说等价的结果集。条件值必要但不充分，一个完整信封还会随这些维度变化：

- specification 名称和版本
- 租户或可见范围
- 投影或结果类型
- 排序和并列值排序列
- 页大小、偏移或游标
- 生效的或被绕过的全局过滤器
- 跟踪和标识解析模式
- 单查询或拆分查询的选择
- 数据版本或失效命名空间

这是工程判断，不是 EF Core 的保证，具体取决于缓存边界：每请求一份的私有缓存和跨租户共享的分布式缓存，隔离要求完全不同。紧凑的键好存但容易撞；完整的键降低碰撞风险，代价是归一化、版本管理和失效逻辑。**等价性说不清的时候，宁可不缓存结果，也不要缓存一个描述不全的查询。**

标签和缓存键要分开：查询标签是 SQL 注释，不可参数化，只该放稳定的、不含敏感信息的标识符；缓存键是应用基础设施，往往包含不该出现在 SQL 注释和日志里的值。

## 生产排查清单

按从边界向内的顺序走：

1. 确认模型：这是纯谓词、表达式条件，还是完整查询信封？
2. 找到物化点：`ToListAsync`、流式枚举、`AsEnumerable`，还是别的执行边界？
3. 在生产 provider 上复现，不要用 EF InMemory 判断 provider 行为。
4. 检查生成的 SQL：过滤、投影、排序、join、上界和参数化。
5. 执行并数命令：找 N+1、拆分查询和重复枚举。
6. 检查生效的全局过滤器，包括租户、软删除和绕过状态。
7. 采集命令耗时，用有界的诊断窗口或预生产环境。
8. 看执行计划，确认索引使用情况，找出扫描、昂贵 join 和错误的基数估计。
9. 一次只改一个查询形状决定：投影、加载策略、上界、排序或条件。
10. 重新测量，保持 provider、数据和方法可比。

这份清单避开两个常见错误：优化一条从没测量过的查询，以及把信封藏起来的默认值算到 Specification 模式头上。

## 结论：诊断你真正执行的那条查询

Specification 不会自动让 EF Core 变快或变慢。它的效果取决于里面装了什么、evaluator 又加了什么、物化发生在哪里、provider 怎么翻译这棵树、数据库怎么执行这条命令。

取舍是架构层面的：查询信封能集中条件，也能藏起昂贵的默认值。优先选那种把投影、include、过滤器、上界、标签和执行边界都暴露出来的设计，然后测量——读 SQL、数命令、记耗时、看计划、核对缓存标识、在生产 provider 上跑。

判断一条 specification 是否健康，靠的是这些证据，不是这个模式的名字，也不是一个编译通过的谓词单元测试。

下一步可以从最小的地方开始：把项目里的 `ListAsync(specification)` 挑一条出来，打开命令日志，看看它到底发了几条命令、SQL 里有没有你以为存在的 `WHERE`。这两个数字通常就够指向真正的问题。

如果你也在做 EF Core 的查询优化，Aide Hub 会继续写这类「官方文档里有、但踩过才知道」的工程细节，尽量把每条结论的版本和验证环境标清楚。

## 参考

- [Specification Pattern Performance and EF Core Translation Traps（原文）](https://www.devleader.ca/2026/09/22/specification-pattern-performance-and-ef-core-translation-traps)
- [What's New in EF Core 10](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/whatsnew)
- [EF Core releases and planning](https://learn.microsoft.com/en-us/ef/core/what-is-new/)
- [Client vs. Server Evaluation](https://learn.microsoft.com/en-us/ef/core/querying/client-eval)
- [Global Query Filters](https://learn.microsoft.com/en-us/ef/core/querying/filters)
- [Single vs. Split Queries](https://learn.microsoft.com/en-us/ef/core/querying/single-split-queries)
- [Query Tags](https://learn.microsoft.com/en-us/ef/core/querying/tags)
- [ToQueryString API reference](https://learn.microsoft.com/en-us/dotnet/api/microsoft.entityframeworkcore.entityframeworkqueryableextensions.toquerystring?view=efcore-10.0)
- [Advanced Performance Topics（编译查询与缓存）](https://learn.microsoft.com/en-us/ef/core/performance/advanced-performance-topics)
- [Performance Diagnosis](https://learn.microsoft.com/en-us/ef/core/performance/performance-diagnosis)
