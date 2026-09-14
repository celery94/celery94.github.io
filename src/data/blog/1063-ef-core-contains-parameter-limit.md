---
pubDatetime: 2026-09-14T07:52:00+08:00
title: "EF Core 10 大列表查询：2098 参数悬崖"
description: "EF Core 10 把参数化集合默认翻译成每个值一个参数，可用上限其实是 2098；越界不报错，只是悄悄变慢。本文整理分桶补齐规则、七种写法的实测对比、计划缓存代价，以及复合键列表为什么必须换写法。"
tags: ["EF Core", ".NET 10", "SQL Server", "性能优化", "C#"]
slug: "ef-core-contains-parameter-limit"
ogImage: "../../assets/1063/01-cover.jpg"
source: "https://codewithmukesh.com/blog/ef-core-contains-large-list/"
---

一句 `ids.Contains(p.Id)` 在生产里跑得好好的，直到某个客户的 ID 列表涨到 1,800 个。查询开始变慢，但日志、异常收集器和 APM 里什么都看不到——EF Core 10 已经不在这里抛异常了。

Mukesh Murugan 在 [Filtering EF Core by a Large List: The 2,100 Parameter Wall](https://codewithmukesh.com/blog/ef-core-contains-large-list/) 里用一份可运行的工程把这件事从头测了一遍：七种写法、八种列表规模、一百万行数据。结论比「参数上限 2,100」这句话复杂得多：真正可用的是 2,098，而且最慢的区间就在上限之前——列表再长一个元素，查询反而快约 8 倍，因为它换了一种翻译方式。

本文按「上限是多少 → EF Core 10 怎么翻译 → 越界后发生什么 → 七种写法怎么选 → 复合键为什么是另一回事 → 怎么监控」的顺序整理，并核对了 EF Core 10.0.x 的源码与发布包，其中原文的一处按查询写法在发布包里并不存在。

## 上限是 2,098，不是 2,100

SQL Server 的容量表里写着「每个存储过程 2,100 个参数」。SqlClient 通过 `sp_executesql` 发送你的命令，而 `sp_executesql` 自己要用掉两个参数，所以一条查询实际能用的是 2,098。

EF Core 的 SQL Server 提供程序里就是这一行：

```csharp
private int MaxParameterCount => UseOldBehavior37336 ? 2100 : 2100 - 2;
```

这个数字是 EF Core 10.0.2 才修正的。前几个补丁里这段代码不太平：

| Issue                                                   | 症状                                               | 修复版本 |
| ------------------------------------------------------- | -------------------------------------------------- | -------- |
| [#37151](https://github.com/dotnet/efcore/issues/37151) | 参数数落在 2,070 到 2,100 之间时抛除零异常         | 10.0.1   |
| [#37152](https://github.com/dotnet/efcore/issues/37152) | 参数较多时查询生成速度明显慢于 EF Core 9           | 10.0.2   |
| [#37336](https://github.com/dotnet/efcore/issues/37336) | 上限仍按 2,100 计算，2,099 和 2,100 个参数执行失败 | 10.0.2   |

微软把这次翻译方式的改动标记为「低影响」。三个补丁修同一段逻辑，而 `#37336` 的正文只有一句话：「虽然最大值是 2098，因为 sp_executesql。」要在这块做基准测试，先升到 10.0.2 以上——目前 EF Core 10 的最新补丁是 10.0.12，作者的实测跑在 10.0.11 上。

## EF Core 10 换了翻译方式

EF Core 8 之前，集合是直接内联进 SQL 的常量：

```sql
WHERE [b].[Id] IN (1, 2, 3)
```

这带来计划缓存膨胀，所以 EF Core 8 改成单个 JSON 数组参数加 `OPENJSON`：

```sql
WHERE [b].[Id] IN (
    SELECT [i].[value]
    FROM OPENJSON(@__ids_0) WITH ([value] int '$') AS [i]
)
```

EF Core 10 又换了默认：每个值一个标量参数。

```sql
WHERE [p].[Id] IN (@ids1, @ids2, @ids3)
```

[官方说明](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/whatsnew#improved-translation-for-parameterized-collection)给的理由是：SQL 不随集合内容变化，保护计划缓存；同时又把集合的基数信息交给查询规划器。对常见场景这是笔好交易。

升级时还有一处要留意：参数名从 `@__ids_0` 变成了 `@ids1`。微软提醒这次改名会让服务器上几乎所有缓存计划失效，部署后会看到一次编译尖峰。

### 参数个数比列表长度多

EF 会对参数列表做分桶补齐（padding），让长度相近的集合生成同一条 SQL。8 个 ID 会发 10 个参数：

```sql
WHERE [p].[Id] IN (@ids1, @ids2, @ids3, @ids4, @ids5, @ids6, @ids7, @ids8, @ids9, @ids10)
```

`@ids9` 和 `@ids10` 重复了 `@ids8` 的值，结果不变。分桶规则微软没有写进文档，作者从源码里读出来并实测验证：

```csharp
protected override int CalculateParameterBucketSize(int count, RelationalTypeMapping elementTypeMapping)
{
    if (count <= 5) return 1;
    if (count <= 150) return 10;
    if (count <= 750) return 50;
    if (count <= 2000) return 100;
    if (count <= 2070) return 10; // try not to over-pad as we approach that limit
    if (count <= MaxParameterCount && UseOldBehavior37151) return 0;
    if (count <= MaxParameterCount) return 1; // just don't pad between 2070 and 2100, to minimize the crazy
    return 200;
}
```

对应到你的列表：

| 列表长度    | 实际发出的参数       | 例子          |
| ----------- | -------------------- | ------------- |
| 1–5         | 精确                 | 3 → 3         |
| 6–150       | 向上取到 10 的倍数   | 8 → 10        |
| 151–750     | 向上取到 50 的倍数   | 151 → 200     |
| 751–2,000   | 向上取到 100 的倍数  | 751 → 800     |
| 2,001–2,070 | 向上取到 10 的倍数   | 2,001 → 2,010 |
| 2,071–2,098 | 精确（1 表示不补齐） | 2,094 → 2,094 |

桶大小 1 就是不补齐，所以小列表和贴着上限的列表都发精确数量。实践含义是：只数列表长度会低估参数数量，751 个 ID 已经用掉 800 的额度；再叠上分页、软删除标记和全局查询过滤器贡献的参数，到顶的时间比你以为的早。

## 越界不是报错，是静默降级

作者在边界附近逐个取值，抓下 EF 实际发出的命令：

| 列表长度              | 参数个数              | 翻译方式               |
| --------------------- | --------------------- | ---------------------- |
| 2,096 / 2,097 / 2,098 | 2,096 / 2,097 / 2,098 | `IN (@ids1 ... @idsN)` |
| 2,099 及以上          | 1                     | `OPENJSON`             |

2,099 之后 SQL 退回 EF Core 8/9 的形态：

```sql
WHERE [p].[Id] IN (
    SELECT [__openjson0].[Value]
    FROM OPENJSON(@ids) WITH ([Value] int '$') AS [__openjson0]
)
```

这个判断发生在 `VisitIn` 里：超过上限的集合会交给一个「改用单参数、用 JSON 函数处理」的分支；如果服务器不支持 JSON，就退化成内联常量。两条路都不抛异常。

然后是一百万行表上的性能对比：

| 列表长度    | 平均耗时 | 分配内存 |
| ----------- | -------- | -------- |
| 2,098 个 ID | 34.6 ms  | 3,393 KB |
| 2,099 个 ID | 4.0 ms   | 743 KB   |

多一个 ID，快约 8 倍，内存少约 4.6 倍。慢的那一侧才是默认行为：大约从 1,000 个 ID 到 2,098 个 ID 都落在这条昂贵区间里，而代码里没有任何信号。

## 七种写法的实测

环境是一百万行 `Products`，主键聚集索引加一个非聚集索引，全部 `AsNoTracking`，BenchmarkDotNet 0.15.8、.NET 10.0.11、EF Core 10.0.11、SQL Server 2025 LocalDB。作者给的两个提示要一起读：10 和 100 个 ID 时除 `WhereBulkContains` 外所有方案都在 1–2 ms 内，BenchmarkDotNet 也警告迭代时间太短，那些行应当读作「都一样」；1,000–2,099 区间在笔记本级 LocalDB 上方差较大，看曲线形状而不是小数点后第三位。下面的表省掉了 2,099 和 10,000 两列，它们不改变结论。

| 方案                    | 1,000   | 2,098   | 5,000  | 100,000        |
| ----------------------- | ------- | ------- | ------ | -------------- |
| `Contains`（默认）      | 12.8 ms | 34.6 ms | 6.2 ms | 273 ms         |
| `EF.Parameter`          | 2.6 ms  | 4.3 ms  | 7.6 ms | 243 ms         |
| `EF.Constant`           | 3.6 ms  | 5.9 ms  | 102 ms | 失败（20.5 s） |
| 按 2,000 分块           | 16.0 ms | 34.3 ms | 72 ms  | 1,347 ms       |
| 手工临时表              | 5.8 ms  | 9.9 ms  | 93 ms  | 187 ms         |
| `WhereBulkContains`     | 9.3 ms  | 12.5 ms | 137 ms | 270 ms         |
| `WhereContains`（免费） | 8.4 ms  | 10.8 ms | 132 ms | 失败（19.8 s） |

四个可以直接用的结论：

- 默认模式最差的位置就在上限之前。2,098 个 ID 时 `EF.Parameter` 是 4.3 ms，默认是 34.6 ms——改一个词换 8 倍。
- 分块是最流行的答案，也是最弱的一个。它在任何规模下都不是最快的，100,000 个 ID 时 1.35 s，而临时表只要 187 ms，内存还多五倍。把一条查询拆成五十条意味着五十次往返，以及五十个结果集要在内存里拼起来。
- `EF.Constant` 到 2,098 之前很有竞争力，之后崩掉：5,000 个 ID 时 102 ms，100,000 个 ID 时 SQL Server 以「查询处理器内部资源不足，无法生成查询计划」直接拒绝。这是另一个失败点，来自 SQL 文本本身的体积，与参数数量无关，所以没有任何参数设置能救它。
- 临时表直到 100,000 才赢过内置方案。5,000 时默认模式是全表最快的；10,000 时 `EF.Parameter` 以 13.5 ms 对 14.8 ms 略胜，两者都比任何临时表方案快约七倍。

还有两个失败要单独说：`EF.Constant` 和 `WhereContains` 在 100,000 个 ID 时都不是快速失败，而是先跑 20.5 秒和 19.8 秒，全程占着一条连接。快速抛出的异常是一份缺陷报告；负载下一条连接被占二十秒是一次故障。

### 计划缓存：补齐在做实事

「内联常量会污染计划缓存」经常被当成口号用，作者直接数了：清空缓存后跑二十条不同长度的查询。

| 模式                          | 不同缓存计划数 |
| ----------------------------- | -------------- |
| `Parameter`（单个 JSON 参数） | 2              |
| 默认（多参数加补齐）          | 4              |
| `Constant`（内联）            | 21             |

内联会为每个不同的列表生成一条新计划，而补齐把二十种长度收敛到四条。这是 `EF.Constant` 只适合短小稳定集合的最强理由。

## 三种翻译模式怎么选

EF Core 10 把选择权完全交了出来。全局配置：

```csharp
optionsBuilder.UseSqlServer(connectionString, sql =>
    sql.UseParameterizedCollectionMode(ParameterTranslationMode.Parameter));
```

按查询覆盖：

```csharp
// 单个 JSON 数组参数，用 OPENJSON 展开。EF Core 8/9 的默认行为。
.Where(p => EF.Parameter(ids).Contains(p.Id))

// 值内联进 SQL 文本。EF Core 8 之前的默认行为。
.Where(p => EF.Constant(ids).Contains(p.Id))
```

这里要提醒一件事：`ParameterTranslationMode` 的枚举注释里提到了一个按查询写法 `EF.MultipleParameters(ids)`，但它在发布包里并不存在。我核对了 EF Core 10.0.12 的 `Microsoft.EntityFrameworkCore` 程序集，`EF` 类只提供 `EF.Constant` 和 `EF.Parameter` 两个集合翻译辅助方法；release/10.0 的源码树里也没有任何声明 `EF.MultipleParameters` 的文件。要用「每个值一个参数」这个默认模式，只能走全局配置。

`EF.Constant` 的正当场景是短且稳定的集合，比如几个角色名或状态码：内联让规划器看到真实值，从而挑出更好的计划，而集合几乎不变，所以不会搅动缓存。

一个会在调试器前让人困惑的细节：EF Core 10 默认把内联常量从日志里抹掉。数据库收到的是 `IN (N'Administrator', N'Manager')`，日志里显示 `IN (?, ?)`，除非打开 `EnableSensitiveDataLogging()`。这是有意的安全改进，但很容易被误读成 EF 发错了 SQL。

还有个测试陷阱：EF 按模型缓存编译后的查询。如果在一个进程里依次切换几种全局模式，后面每次拿到的都是第一种模式的 SQL，你会以为配置没生效。作者的做法是把每种全局模式放到独立子进程里跑。按查询的 `EF.Parameter` 和 `EF.Constant` 没有这个问题，因为它们改变了表达式树，会各自命中不同的缓存条目。

## 内置方案不够用时：把列表当成表

翻译模式只能解决「按一列标量列表过滤」。它表达不了三类需求：

- 复合键：`(TenantId, ProductId)` 这样的列表没有 `IN` 形式
- 对象列表：按内存实体的多个属性过滤
- 规模无法界定，更愿意在服务端 join 而不是把列表传过去

共同的答案是不再把列表当谓词，而是当一张表：先把值装载进去，再 `INNER JOIN`。手写版本是临时表加 `SqlBulkCopy`：

```csharp
await using var connection = new SqlConnection(connectionString);
await connection.OpenAsync();

await using (var create = connection.CreateCommand())
{
    create.CommandText = "CREATE TABLE #Ids ([Value] int NOT NULL PRIMARY KEY);";
    await create.ExecuteNonQueryAsync();
}

using var bulk = new SqlBulkCopy(connection) { DestinationTableName = "#Ids" };
bulk.ColumnMappings.Add("Value", "Value");
await bulk.WriteToServerAsync(idTable);

await using var select = connection.CreateCommand();
select.CommandText =
    "SELECT p.[Id] FROM [Products] p INNER JOIN #Ids i ON i.[Value] = p.[Id];";
```

它在 100,000 个 ID 那档赢了（187 ms），代价是离开 EF 的查询管线：不能再组合 LINQ、不能投影、不能用导航属性，连接也得自己管。

有几家库把同一套做法包成了 `IQueryable` 上的方法，例如 Entity Framework Extensions 的 `WhereBulkContains` 和 Entity Framework Plus 的 `WhereContains`。作者对前者的评价是「买的是能力不是速度」：在 100,000 个 ID 的测试里它和默认模式打平（270 ms 对 273 ms），小列表反而有额外开销（10 个 ID 时 5.4 ms，其他方案都在 2 ms 以内）。采用前需要核对的东西包括许可证与试用条款、只支持 SQL Server 和 PostgreSQL、不支持 `ExecuteUpdate`/`ExecuteDelete`、不支持 TPH/TPT/TPC 继承映射。免费那个还有一层细节：它会把商业版程序集一起还原到输出目录，而且超过 200 个值之后会转成内联常量，也就是继承 `EF.Constant` 的退化行为。第三方库的条款和默认值会变，落地前请以当时的文档为准。

## 复合键是另一回事

换成复合键列表，问题不再是「慢」，而是内置方案根本无法表达这个查询。三种直觉写法在 EF Core 10 上全部翻译失败：

```csharp
// 三种都不能翻译
.Where(i => keys.Contains(new ValueTuple<int, int>(i.TenantId, i.ProductId)))
.Where(i => keys.Contains(new { i.TenantId, i.ProductId }))
.Where(i => keys.Any(k => k.TenantId == i.TenantId && k.ProductId == i.ProductId))
```

抛的都是同一句：「LINQ 表达式无法翻译……」。这跟规模无关：两对键和两千对键的失败方式一样。SQL Server 没有接受两列的 `IN` 形式，EF 也没有可翻译的元组 `Contains`，查询根本到不了数据库。

常见的绕法是自己拼谓词，每对键一个 `AND` 子句再全部 `OR` 起来。100 对时它跑 2.1 ms，和其他方案持平；到 490 对时进程直接死掉。

退出码是 `0xC00000FD`，`STATUS_STACK_OVERFLOW`。.NET 里栈溢出无法被捕获，所以没有异常可记，没有 `catch` 能救，遥测里只留下一个消失的工作进程。作者做了二分：489 对正常，490 对进程消失。

原因是表达式树的形状，不是参数数量。在循环里不断 `OR` 到累加器上会构造出一棵 490 层深的左倾树，EF 翻译时递归遍历它。490 对只是 980 个参数，还不到预算的一半——参数上限根本没参与。

把同样的子句按平衡树合并，深度从 n 变成 log₂(n)，能撑到 1,049 对，然后抛出真正的参数错误：「传入的请求参数过多，服务器最多支持 2100 个参数。」每对键两个参数，所以上限落在 1,049 对上。

这是全文唯一能真正触发 2,100 错误的地方，原因也清楚：OR 链不是参数化集合，没有一个数组让 EF 注意到并改换翻译，只有 2,098 个碰巧排成树状的独立参数。悄悄救下标量 `Contains` 的那条 OPENJSON 回退路径，在这里没有钩子。

OR 链还有第二个意外，来得比两个上限都早：400 对时，参数化版本跑了 5.3 秒，把值内联进去的同样一条链只要 2.9 ms——同样的行，同样的谓词，差约 1,800 倍。原因是给了真实值，SQL Server 能把 OR 列表展开成一组索引查找；给它 800 个参数它就不这么做，退化成扫表并对每一行做 400 次比较。而内联正是「每个不同列表留一份计划」的做法，也就是 `EF.Constant` 在前面已经输掉的那个权衡。

还有一种绕法是把两列拼成一个字符串，回到普通的 `Contains`。它能翻译，这正是陷阱：

```sql
WHERE CAST([i].[TenantId] AS nvarchar(max)) + N'-' + CAST([i].[ProductId] AS nvarchar(max))
      IN (@keys1, @keys2, ...)
```

两列都先 `CAST` 再比较，主键索引完全用不上，SQL Server 要扫全部一百万行、逐行做拼接。100、400、1,000 对时它一次都没跑完，全都撞上默认的 30 秒命令超时；而 OR 链回答同一个问题只要 2.1 ms。

然后更奇怪的事出现了：5,000 对时它 1.3 秒跑完，100,000 对时 1.9 秒。因为字符串列表同样受那条规则约束，一旦跨过 2,098 个值，EF 就把它塞进单个 JSON 参数，`IN` 变成对 `OPENJSON` 的子查询。一次扫描配一次哈希匹配，胜过一次扫描加几千次逐行字符串比较。所以这个做法在它看起来最安全的小列表上表现最差，任何规模下都不是正确答案。

复合键的实测：

| 方案                    | 100    | 400      | 1,000    | 5,000    | 100,000  |
| ----------------------- | ------ | -------- | -------- | -------- | -------- |
| OR 链，参数化           | 2.1 ms | 5,316 ms | 进程崩溃 | 进程崩溃 | 进程崩溃 |
| OR 链，内联             | 2.0 ms | 2.9 ms   | 进程崩溃 | 进程崩溃 | 进程崩溃 |
| 字符串拼接 `Contains`   | 超时   | 超时     | 超时     | 1,308 ms | 1,857 ms |
| 手工临时表              | 2.1 ms | 2.3 ms   | 4.9 ms   | 9.3 ms   | 170 ms   |
| `WhereBulkContains`     | 4.9 ms | 5.3 ms   | 8.1 ms   | 20.7 ms  | 255 ms   |
| `WhereContains`（免费） | 2.2 ms | 3.7 ms   | 进程崩溃 | 进程崩溃 | 进程崩溃 |

「进程崩溃」指进程因栈溢出死掉，既没有异常也没有结果；「超时」指查询在 30 秒命令超时时仍在运行。两者都是运行这段代码的真实结果，不是测试工具的缺口。

两点值得记住：手工临时表从 400 对起就赢下每一列，比标量场景（内置方案一直赢到 100,000）早得多——这正是「复合键没有内置方案可赢」的意思。`WhereBulkContains` 是唯一在每个规模都返回正确结果的行，代价是手写装载的 1.5 到 2.4 倍。免费那个方法确实接受复合键，但它会解析成内联 OR 链，于是原封不动地继承了那套上限，在同样的几百对处因同样的栈溢出死掉。

最后提醒一句边界：489 这个数字是栈深度限制，会随栈大小、构建配置和运行时版本移动，你自己的数字不会完全一样。不要把它当文档化的边界，把它读成「几百对」，并当作不要在循环里拼谓词的理由。

## 监控与预防

三个习惯：

- 记录参数个数，不是列表长度。一个 `DbCommandInterceptor` 读 `command.Parameters.Count` 大概十行代码，它告诉你唯一重要的那个数字。
- 按列表规模给查询耗时打桶告警，而不是只看错误率。在这条代码路径上 EF 已经替你吞掉了错误，耗时是剩下的唯一信号。
- 在基准测试里锁定 EF Core 的补丁版本，并写进结果。这里描述的行为在 10.0.0 到 10.0.2 之间变了两次，以后还会变。

选型速查：

| 你的情况                   | 用什么                                               | 为什么                                                      |
| -------------------------- | ---------------------------------------------------- | ----------------------------------------------------------- |
| 1,000 个 ID 以内           | 默认 `Contains`                                      | 各方案实测都一样，别把事情搞复杂                            |
| 1,000–2,098 个 ID          | `EF.Parameter(ids)`                                  | 默认模式最差的区间，2,098 时快约 8 倍                       |
| 超过 2,098 个 ID           | 默认 `Contains`                                      | EF 已经替你切到 JSON 参数                                   |
| 短且稳定的值集合           | `EF.Constant(ids)`                                   | 真实值带来更好的计划，且很少变化                            |
| 热路径上列表长度花样很多   | `EF.Parameter(ids)`                                  | 缓存计划 2 条，而不是 4 条或 21 条                          |
| 100,000+ 个 ID，只要速度   | 手工临时表                                           | 实测最快，代价是离开 EF 管线                                |
| 复合键或对象列表           | staging 加 join（可用 `WhereBulkContains` 之类封装） | 内置方案翻译不了，手拼 OR 链几百对就崩                      |
| 几百对复合键，没有授权预算 | 平衡 OR 树加内联值                                   | 免费且能过两个上限；参数化形式在 400 对时是 5.3 s 对 2.9 ms |
| 用 PostgreSQL              | 先自己测                                             | 上限不同，但不是没有                                        |

最后一行值得展开。PostgreSQL 的上限远高于 SQL Server：协议文档里 `Bind` 消息的参数个数标的是 `Int16`，但服务端按无符号 16 位解析（`pq_getmsgint(..., 2)` 的返回值是 `uint16`），所以实际是 65,535。再叠加 Npgsql 自己的集合翻译方式，两个数据库的结论不能互相套用。

还有个更根本的问题值得在动手前问：这个列表为什么这么长。一个带着 50,000 个 ID 到达的请求，往往是一个伪装成过滤的分页问题——用分页、排序和搜索解决它，列表根本不会到达数据库。如果同一份列表确实要被反复查询，二级缓存省掉的是往返，而不是去优化这条查询。

这类问题的共同形状是「框架替你做了一个安静的决定」。Aide Hub 会继续整理 .NET 与数据库层里这类默认行为的实测和取舍。如果你在生产里见过查询因为参数变多而变快、或者因为栈溢出整进程消失，欢迎把当时的现象发来对照。

## 参考

- [Filtering EF Core by a Large List: The 2,100 Parameter Wall](https://codewithmukesh.com/blog/ef-core-contains-large-list/)（原文，Mukesh Murugan）
- [What's New in EF Core 10：Improved translation for parameterized collection](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/whatsnew#improved-translation-for-parameterized-collection)
- [EF Core issue #37151](https://github.com/dotnet/efcore/issues/37151) / [#37152](https://github.com/dotnet/efcore/issues/37152) / [#37336](https://github.com/dotnet/efcore/issues/37336)
- [ParameterTranslationMode 源码](https://github.com/dotnet/efcore/blob/release/10.0/src/EFCore/ParameterTranslationMode.cs)
- [Maximum capacity specifications for SQL Server](https://learn.microsoft.com/en-us/sql/sql-server/maximum-capacity-specifications-for-sql-server)
- [PostgreSQL 18：Message Formats（Bind）](https://www.postgresql.org/docs/18/protocol-message-formats.html)
- [PostgreSQL 18：pqformat.c](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/libpq/pqformat.c)
- [EF Core 10.0.12 on NuGet](https://www.nuget.org/packages/Microsoft.EntityFrameworkCore/10.0.12)
