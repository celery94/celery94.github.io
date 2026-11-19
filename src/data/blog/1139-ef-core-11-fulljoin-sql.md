---
pubDatetime: 2026-11-19T09:30:03+08:00
title: "04｜EF Core 11：选课对账的 LINQ 与 SQL"
description: "用同一批选课对账数据对比 EF Core 10 与 11 的生成 SQL 和 SQLite 执行计划，检查全连接、分组、拆分查询和两侧缺失记录，并说明 PostgreSQL provider 的验证边界。"
tags: ["DotNet", "EF Core", "LINQ", "SQL"]
slug: "ef-core-11-fulljoin-sql"
ogImage: "../../assets/1139/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-11.0/whatsnew"
---

报表要找出漏缴和多缴，必须看见两张表里只出现一次的课程。用内连接会把它们直接过滤掉。我在同一批模拟数据上对照了 EF Core 10 的 `LEFT JOIN + UNION ALL` 写法和 EF Core 11 的 `FullJoin`。两边的结果一致，生成 SQL 和 SQLite 的执行计划有明确差异。

这篇的 SQL 来自 Microsoft 的 SQLite provider。系列 Web 服务使用 PostgreSQL，EF Core 的 LINQ 翻译仍取决于 Npgsql 对应版本；要在实际 provider 上重新核验 SQL 和结果。

## 先按课程聚合，再把两份账对上

样本中登记表为 C101 → 2、C102 → 1。缴费表为 C101 → 1、C101 → 2、C103 → 1。缴费表在 C101 有两笔，如果直接连接原始行，就可能在随后汇总时重复计算登记金额。先分别 `GroupBy`，把每一侧缩成每门课一行，再连接。

```csharp
var expected = db.Expected.GroupBy(x => x.Code)
    .Select(g => new { Code = g.Key, Amount = g.Sum(x => x.Amount) });
var paid = db.Paid.GroupBy(x => x.Code)
    .Select(g => new { Code = g.Key, Amount = g.Sum(x => x.Amount) });
var report = expected.FullJoin(paid, e => e.Code, p => p.Code,
    (e, p) => new
    {
        Code = e!.Code ?? p!.Code,
        Expected = (int?)e!.Amount ?? 0,
        Paid = (int?)p!.Amount ?? 0
    }).OrderBy(row => row.Code);
```

这个表达式在 EF Core 11 中由数据库执行。可空转换让缺失的一侧得到 SQL 的 `NULL`，再用 0 填充金额。直接把表达式挪到已物化的内存集合时，要显式处理空对象。正式对账如果要区分「没有账目」和「金额正好是零」，保留存在标志或 nullable 金额。

| 课程 | 应计 | 实缴 | 含义         |
| ---- | ---: | ---: | ------------ |
| C101 |    2 |    3 | 两侧都有记录 |
| C102 |    1 |    0 | 只在登记表   |
| C103 |    0 |    1 | 只在缴费表   |

## 从 SQL 和计划里看两边做了什么

EF Core 10.0.13 / SQLite 3.53.3 的对照写法先拿左表和匹配项，再用 `NOT EXISTS` 找只在右边的项，最后 `UNION ALL`。EF Core 11.0.0 / SQLite 3.53.4 直接生成 `FULL JOIN`。这是从 11 版日志保留的连接部分，省略了开头投影。

```sql
FROM (
    SELECT "e"."Code", COALESCE(SUM("e"."Amount"), 0) AS "Amount"
    FROM "Expected" AS "e"
    GROUP BY "e"."Code"
) AS "e0"
FULL JOIN (
    SELECT "p"."Code", COALESCE(SUM("p"."Amount"), 0) AS "Amount"
    FROM "Paid" AS "p"
    GROUP BY "p"."Code"
) AS "p0" ON "e0"."Code" = "p0"."Code"
ORDER BY COALESCE("e0"."Code", "p0"."Code")
```

这份数据上，11 版计划把两侧聚合结果各物化一次，出现 `RIGHT-JOIN p0` 和排序用的临时 B-tree。旧写法的计划有两个合并分支，右侧孤立项分支还要判断对应左行是否存在。这个对照说明查询结构变了。数据太小，不能从这份计划直接得出性能收益。

单独运行缴费 `GroupBy` 时，两版都生成按课程分组求和，计划都扫描缴费表并为 `GROUP BY` 建临时 B-tree。另一个对照用 `Include` 加 `AsSplitQuery()` 读取两门课程及报名集合。用 `ToQueryString()` 只能看到第一条，日志才记录后续读取关联行的 SQL。验证时把总语句数、各条参数和返回行数都保留下来，避免只看第一条就判断拆分查询变快了。

## 复现并验证生产 provider

下载源码和 SQL 日志，在解压目录分别运行 `dotnet run -f net10.0` 与 `dotnet run -f net11.0`。程序会输出 SQLite 版本、结果行、生成 SQL 与 `EXPLAIN QUERY PLAN`。两个目标都以 SDK 11.0.100 构建。[下载 EF Core 对账示例](https://celery94.github.io/assets/1139/enrollment-ef-demo.zip)

把相同样本移到 PostgreSQL 时，先核对 Npgsql 的 EF Core provider 发布线，再用 `ToQueryString()` 核对翻译，使用 PostgreSQL 的 `EXPLAIN` 观察计划。在测试库用有代表性的记录量测耗时和缓存表现。可能改变写入的语句做 `EXPLAIN ANALYZE` 前，确认它会真正执行。

其他 provider 的迁移也有自己的检查项。SQL Server 要核对默认兼容级别 160 和 SqlClient 7，向量索引仍属实验范围。Cosmos 要检查同步 I/O 移除和未映射字段行为。实际项目若尚未验证目标 provider，先保留基线 LINQ，让应用升级和查询改写可以分别回退。

## 参考

- [EF Core 11 功能说明与 FullJoin](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-11.0/whatsnew)
- [EF Core 11 破坏性变更](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-11.0/breaking-changes)
- [EF Core 单查询与拆分查询](https://learn.microsoft.com/en-us/ef/core/querying/single-split-queries)
- [Npgsql EF Core provider 发布说明](https://www.npgsql.org/efcore/release-notes/11.0.html)
- [SQLite EXPLAIN QUERY PLAN](https://www.sqlite.org/eqp.html)
