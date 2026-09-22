---
pubDatetime: 2026-09-22T12:06:10+08:00
title: "PG 转 SQL Server：日期时间类型映射与陷阱"
description: "PostgreSQL 的 timestamp、timestamptz 和 SQL Server 的 datetime2、datetimeoffset 语义并不一一对应。这份迁移笔记给出映射表、存储账，以及官方文档里六个容易踩的转换陷阱。"
tags: ["PostgreSQL", "SQL Server", "数据库迁移", "日期时间", "Azure SQL"]
slug: "pg-to-sql-server-date-time"
ogImage: "../../assets/1083/01-cover.jpg"
source: "https://devblogs.microsoft.com/azure-sql/pg-to-sql-date-time"
---

把 PostgreSQL 的 `timestamptz` 列迁到 SQL Server，最容易做错的一步是选目标类型。如果目标列写成 `datetime2`，时区偏移会在转换时被静默丢掉——而留下的还是本地时间，不是 UTC 瞬间。换句话说，原始偏移没保住，那个时间点也没保住，而且不会报任何错。

[原文](https://devblogs.microsoft.com/azure-sql/pg-to-sql-date-time)是 Azure SQL 团队 Jerry Nixon 写的《PostgreSQL to SQL Field Notes: Date & Time》，属于「PG 开发者迁到 SQL」系列，专门讲日期时间。它把两边的类型语义讲清楚了，下面在它的基础上补出映射表和几个官方文档里有、原文没提的转换陷阱。

先说结论：**PG 的两个时间类型回答的是「有没有时区」，SQL Server 的两个时间类型回答的是「要不要保留偏移」。** `timestamptz` 和 `datetimeoffset` 名字像、都能跨时区，但存的东西不一样——前者只存一个瞬间，后者存本地时间加偏移。

## PostgreSQL：一个丢偏移，一个丢原始时区

原文先梳理了 PG 的历史：`timestamp` 这个名字存在得比 PostgreSQL 7.0 还早，但含义变过。7.0 用 SQL92 定义的 `timestamp` 取代了旧的 `datetime`，7.2 才引入今天 `timestamp without time zone` 和 `timestamp with time zone` 的区分。所以现在写一个光秃秃的 `timestamp`，等价于 `timestamp without time zone`。

### timestamp 会静默丢弃偏移

```sql
SELECT TIMESTAMP '2026-09-21 10:30:00';
```

没有时区信息，也不会存时区信息，值原样存下。麻烦的是带偏移的写法：

```sql
SELECT TIMESTAMP '2026-09-21 10:30:00-06:00';
```

偏移被直接忽略。你明确写了 `-06:00`，它照样丢掉。想在库里保住原始时区，只能自己加字段：

```sql
CREATE TABLE events (
    event_id SERIAL PRIMARY KEY,
    event_name TEXT NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    event_timezone TEXT NOT NULL
);
```

能用，但从这一刻起，一个事件由两个值描述，应用要负责让它们始终一致、并且解释正确。任何一处漏更新，数据就不自洽了。

### timestamptz 存的是瞬间，不是原始时区

```sql
SELECT TIMESTAMPTZ '2026-09-21 10:30:00-06:00';
```

这次偏移起作用了：PG 用它算出真实的时间点，内部按 UTC 存下来。但取出来的时候，PG 会把它转换成当前会话的 `TimeZone`。所以同一个存储值，换个会话就换个样子：

```sql
SET TIME ZONE 'America/Denver';

SELECT TIMESTAMPTZ '2026-09-21 10:30:00-06:00';
-- 2026-09-21 10:30:00-06

SET TIME ZONE 'America/New_York';

SELECT TIMESTAMPTZ '2026-09-21 10:30:00-06:00';
-- 2026-09-21 12:30:00-04
```

两个结果是同一个瞬间，这是 PG 有意为之。代价是：**原始偏移在插入时就丢了**，`timestamptz` 回答不了「应用当初传的是哪个偏移」。需要这个信息，只能在应用侧记，或者另外存一个字段。

## SQL Server：datetime2 对应 timestamp，datetimeoffset 要你明确选

原文把 SQL Server 的两个类型定义成「PG timestamp 的对应物」和「带时区的升级选项」，这个定位是准的。

`datetime2` 是 SQL Server 传统 `datetime` 类型的现代替代，新开发应该用它。它最接近 PG 的 `timestamp`：不带时区、存本地日期时间。精度上有个真实差异——`datetime2` 的小数秒精度可以从 0 调到 7 位，默认 `datetime2(7)`，也就是 100 纳秒；PG 的 `timestamp` 是 6 位，1 微秒。**SQL Server 的表示精度高 10 倍。**

`datetimeoffset` 从 SQL Server 2008 起就有，本地日期时间和 UTC 偏移一起存：

```sql
DECLARE @dt DATETIMEOFFSET = '2026-09-21 10:30:00-06:00';
```

这个 `-06:00` 会真的留下来。要按 UTC 展示，两种写法都对：

```sql
SELECT @dt AT TIME ZONE 'UTC';

SELECT SWITCHOFFSET(@dt, '+00:00');
```

两者返回同一个瞬间，但适用场景不同。`AT TIME ZONE` 走命名时区和它的夏令时规则，适合「把它换算到某个地区」；`SWITCHOFFSET` 只对现成的偏移做算术，适合「我已经有 datetimeoffset，只想换个偏移显示」。

这里补一个原文没标的前置条件：**`AT TIME ZONE` 需要 SQL Server 2016 及以上**。目标实例更老，就只有 `SWITCHOFFSET` 和 `TODATETIMEOFFSET` 可用。

## 类型映射表

| PostgreSQL                                  | 语义                         | 推荐目标                             | 迁移时要确认                       |
| ------------------------------------------- | ---------------------------- | ------------------------------------ | ---------------------------------- |
| `timestamp` / `timestamp without time zone` | 不带时区的本地时间           | `datetime2`                          | 精度 6 位提到 7 位不丢，反向会截断 |
| `timestamptz` / `timestamp with time zone`  | UTC 瞬间，读时按会话时区渲染 | `datetimeoffset` 或 `datetime2`      | 偏移从哪来（见下面第 6 条）        |
| `time with time zone`                       | 带偏移的时间                 | 没有直接对应，拆成 `time` 加偏移字段 | 需要应用层拼装                     |
| `interval`                                  | 时间间隔                     | 没有对应类型，用秒数或两个时间点     | 依赖 `DATEDIFF` / `DATEADD` 改写   |

后两行是补充，原文没有展开。SQL Server 既没有 `interval` 类型，也没有带偏移的 `time` 类型，这两类列在迁移里通常要改结构，而不是改类型名。

`timestamptz` 那一行是整张表里唯一需要动脑子的地方。它没有唯一正确答案，取决于你要什么：要保留「当时那个地区的时间」就选 `datetimeoffset`，只要一个确定的时间点就选 `datetime2`。选之前先回答一个问题：**以后有没有代码会问「这条记录当初记的是几点几分、在哪个时区」？** 会问，就必须用 `datetimeoffset`；问了也没用，用 `datetime2` 更省。

## 存储账：多存 2 字节，还是每十亿行多 2 GB

精度是可调的，所以存储也是可调的。原文给的两张表值得记住，这里补上官方文档的分档：

| 类型                      | 存储    | 说明                     |
| ------------------------- | ------- | ------------------------ |
| `datetime2(0)`–`(2)`      | 6 字节  |                          |
| `datetime2(3)`–`(4)`      | 7 字节  |                          |
| `datetime2(5)`–`(7)`      | 8 字节  | 默认 `datetime2(7)`      |
| `datetimeoffset(0)`–`(2)` | 8 字节  |                          |
| `datetimeoffset(3)`–`(4)` | 9 字节  |                          |
| `datetimeoffset(5)`–`(7)` | 10 字节 | 默认 `datetimeoffset(7)` |

同样的精度下，`datetimeoffset` 比 `datetime2` 多 2 字节，那 2 字节存的就是时区偏移。放到十亿行的量级上：

| 行数  | `datetimeoffset` | `datetime2` |
| ----- | ---------------- | ----------- |
| 10 亿 | 8–10 GB          | 6–8 GB      |

| 行数  | `datetimeoffset(0)` | `datetimeoffset(7)` |
| ----- | ------------------- | ------------------- |
| 10 亿 | 8 GB                | 10 GB               |

十亿行差 2 GB。日期时间字段在很多应用里无处不在，这个差值会影响磁盘、I/O、内存压力和索引大小。

所以原文那句「默认不应该是 datetimeoffset」是对的：应用不关心时区时，`datetime2` 仍然是更好的选择。同时因为精度可调，你还能在「要不要时区」和「要多少存储」之间分开做决定——需要时区支持，但只精确到秒，`datetimeoffset(0)` 比默认的 `(7)` 省下五分之一的存储。

## 六个官方文档里有、原文没提的陷阱

1. **`datetimeoffset` 转 `datetime2` 会静默丢掉偏移，而且留下的是本地时间，不是 UTC 瞬间。** 官方文档写得很明确：转成 `datetime2` 时「the time zone is truncated」。`2026-09-21 10:30:00-06:00` 转过去是 `2026-09-21 10:30:00`，不是 `16:30:00`。别指望先落成 `datetime2` 以后再补会时区，那一步补不回来。

2. **`AT TIME ZONE` 是非确定性函数**，因此不能用在索引视图上，也不能用在带索引的计算列上。而且它依赖的时区规则保存在 Windows 注册表里，会随系统更新变化——这是它被归为非确定性的原因。要把时区换算做成持久化计算列，这条路走不通。

3. **`AT TIME ZONE` 是 SQL Server 2016 才有的语法。** 原文用它举例，但没写版本要求。迁移目标如果是更老的实例，或者你用 `datetime2` 存 UTC 又想换算，方案要提前定。

4. **`datetimeoffset` 的比较、排序、索引都在 UTC 上做**，偏移只是取出来给你看的。官方文档的原话是数据「stored in the database and processed, compared, sorted, and indexed in the server as in UTC」。所以按本地日期做范围过滤时，边界值要先换算成对应的 UTC 瞬间，否则边界会偏。

5. **`datetimeoffset` 保留的是偏移量，不是时区名。** 官方文档里这个类型的「Daylight saving aware」是 No——它不知道自己是哪个地区，也就不知道夏令时规则。需要按地区规则换算，必须走 `AT TIME ZONE` 加命名时区。

6. **`timestamptz` 迁到 `datetimeoffset` 时，那个偏移来自导出会话，不是原始业务时区。** 这是我这边的推论，但依据很直接：PG 在插入时就把原始偏移丢了，所以你在导出时看到的偏移，只由导出会话的 `TimeZone` 决定。迁移脚本里先 `SET TIME ZONE 'UTC'`（或其他你明确选定的值），否则每一行带上的偏移是导出机的时区，而不是应用当初的时区——这时候 `datetimeoffset` 的「保留原始上下文」就是假的。

还有一条只影响特定目标：**Microsoft Fabric 目前不能建 `datetimeoffset` 列。** 在 Fabric SQL database 里，镜像到 OneLake 的数据会截掉时区和第 7 位小数，而且这个类型不能做主键。如果迁移终点是 Fabric，第 1 条之后就要先看这一条。

## 怎么选：三个问题加一个收尾

1. **需要保留「当时当地的时间 + 偏移」吗？** 比如机票起降时间、合同签署地时间、跨时区的营业时间——需要就用 `datetimeoffset`。
2. **只需要一个确定的时间点吗？** 日志、审计、创建时间、更新时间都属于这类——用 `datetime2`，并约定全库统一用 UTC 存。
3. **只是一个不带时区的本地时间吗？** 营业日、排班、账期——用 `datetime2`，并且不要在它上面做跨时区换算。

收尾一步是精度：不需要小数秒就用 `(0)`，十亿行能省下五分之一的存储。

选完之后还有一件必做的事：把现有数据量出来。哪几列是 `timestamptz`、哪几列是 `timestamp`、各有多少行，决定了这次迁移是改类型名还是改结构。数量最多的那几列如果选了 `datetimeoffset(7)`，存储账单会在迁移完成后才显形。

如果你也在做数据库迁移，Aide Hub 会继续写这类「官方文档里有、但踩过才知道」的工程细节，尽量把每条结论的依据和适用版本标清楚。

## 参考

- [PostgreSQL to SQL Field Notes: Date & Time（原文）](https://devblogs.microsoft.com/azure-sql/pg-to-sql-date-time)
- [PostgreSQL 7.0 Release Notes](https://www.postgresql.org/docs/9.0/release-7-0.html)
- [PostgreSQL 7.2 Release Notes](https://www.postgresql.org/docs/9.0/release-7-2.html)
- [SQL Server：datetimeoffset (Transact-SQL)](https://learn.microsoft.com/en-us/sql/t-sql/data-types/datetimeoffset-transact-sql)
- [SQL Server：datetime2 (Transact-SQL)](https://learn.microsoft.com/en-us/sql/t-sql/data-types/datetime2-transact-sql)
- [SQL Server：AT TIME ZONE (Transact-SQL)](https://learn.microsoft.com/en-us/sql/t-sql/queries/at-time-zone-transact-sql)
- [SQL Server：SWITCHOFFSET (Transact-SQL)](https://learn.microsoft.com/en-us/sql/t-sql/functions/switchoffset-transact-sql)
- [SQL Server：Deterministic and nondeterministic functions](https://learn.microsoft.com/en-us/sql/relational-databases/user-defined-functions/deterministic-and-nondeterministic-functions)
