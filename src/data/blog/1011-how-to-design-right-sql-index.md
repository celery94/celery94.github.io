---
pubDatetime: 2026-08-22T19:38:54+08:00
title: "从 17ms 到 0.04ms：如何设计正确的 SQL 索引"
description: "以 Postgres 18 和 100 万条评论为例，用 EXPLAIN ANALYZE 实测索引设计：为什么复合索引的列顺序决定一切、等值列在前排序列在后、为何有的索引用不上、以及每条索引的写入与磁盘成本。"
tags: ["SQL", "PostgreSQL", "Database", "Indexing"]
slug: "how-to-design-right-sql-index"
ogImage: "../../assets/1011/01-cover.jpg"
source: "https://milanjovanovic.tech/blog/how-to-design-the-right-sql-index"
---

Milan Jovanović 在 2026 年 8 月发表了《From 17ms to 0.04ms: How to Design the Right SQL Index》。他往 Docker 里的一个 Postgres 18 实例灌了数据：100 个用户、10000 个 issue、100 万条评论，然后用 `EXPLAIN ANALYZE` 把每一个索引决策都实测了一遍。这篇文章把它整理成一篇可以直接照着做、判断「这个索引到底该不该建、列该怎么排」的中文教程。

## 为什么要先看查询，而不是先看表结构

很多人建索引是盯着表结构来的：看到常查的列就顺手建一个。但正确的 SQL 索引来自**应用实际会跑的查询**，而不是来自表里有哪些列。

Milan 的 `comments` 表需要服务三种访问模式：

- 某个用户的全部评论
- 某个 issue 的全部评论
- 某个 issue 下、某个用户、最近一个月的评论，按时间倒序

第一种最简单，我们先从它入手。没有索引时，它是一条全表扫描：

```sql
EXPLAIN ANALYZE
SELECT COUNT(*)
FROM comments
WHERE user_id = 1;
```

```text
---
Finalize Aggregate
  ->  Gather
        ->  Partial Aggregate
              ->  Parallel Seq Scan on comments  (actual time=0.010..11.727 rows=3356.67 loops=3)
                    Filter: (user_id = 1)
                    Rows Removed by Filter: 329977
Execution Time: 17.066 ms
```

`EXPLAIN ANALYZE` 会真实执行这条查询，并把你用到的计划打出来。上面的 `Parallel Seq Scan` 读完了全部 100 万行，只为了数出 10070 行符合条件的记录——花掉 17ms。这值得吗？读 100 万行只服务一条查询，显然不划算。

建个单列索引，再跑一遍：

```sql
CREATE INDEX ix_comments_user_id
ON comments (user_id);
```

```text
Aggregate
  ->  Index Only Scan using ix_comments_user_id on comments  (actual time=0.024..0.348 rows=10070.00 loops=1)
        Index Cond: (user_id = 1)
        Heap Fetches: 0
Execution Time: 0.612 ms
```

17ms 降到了 0.6ms。这里出现的是 **Index Only Scan**——因为索引本身就能回答 `COUNT(*)`，Postgres 压根不会回头去读表。`Heap Fetches: 0` 就是证据。

## 什么是 SQL 索引

先把概念说清楚：索引把你选中的列按排序存起来，每个条目都指向它对应的完整行。

主流数据库默认的索引类型是 **B-tree**——一棵很浅的树，即使有上百万行，也只需要往下走几层就能定位到目标。顺序扫描要把 100 万条评论全读一遍；而索引扫描只要顺着这几层往下走，只取匹配的行。

## 复合索引的列顺序，决定一切

真正有看点的是第三种访问模式：

```sql
SELECT *
FROM comments
WHERE issue_id = 10
  AND user_id = 29
  AND created_at >= NOW() - INTERVAL '1 month'
ORDER BY created_at DESC;
```

没有索引时，又是一条全表扫描，16.6ms。如果只给 `issue_id` 和 `user_id` 各建一个单列索引，Postgres 会用一个 `BitmapAnd` 把两者结果求交集，再对剩余的行做一次排序，耗时 0.6ms，分三步才能完成。

而一个复合索引能一次把整条查询跑完：

```sql
CREATE INDEX ix_comments_issue_user_date
ON comments (issue_id, user_id, created_at DESC);
```

```text
Index Scan using ix_comments_issue_user_date on comments  (actual time=0.019..0.026 rows=2.00 loops=1)
  Index Cond: ((issue_id = 10) AND (user_id = 29) AND (created_at >= (now() - '1 mon'::interval)))
Execution Time: 0.039 ms
```

三个条件全部落进了 `Index Cond`，而且 `Sort` 消失了——因为索引本身已经按 `created_at DESC` 返回有序数据。运行时间：0.04ms，比原来的 16.6ms 快了 400 多倍。

关键在于理解复合索引的排序规则：它先按第一列排序，再在第一列相等时按第二列排序，再按第三列。所以 Postgres 能直接跳到 `issue_id = 10, user_id = 29` 这一小块，并且按顺序读出来。

**列顺序还决定了这个索引还能服务哪些查询**：`issue_id` 单独用可以，`issue_id + user_id` 可以，但 `user_id` 单独用不了——因为它的值分散在整棵树里。这就是**最左前缀规则**（leftmost prefix rule），也是为什么 `user_id` 的独立索引还得留着。

这条规则浓缩成一句话：**等值列放在最前面，然后才是你要排序或做范围查询的列。**

## 一个复合索引救不了的查询

每个 issue 跟踪系统都有一个仪表盘查询：取最新的 25 个未关闭 issue，每个 issue 带一条最新评论，用 `LATERAL` 子查询取：

```sql
SELECT i.id, c.body, c.created_at
FROM issues i
CROSS JOIN LATERAL (
  SELECT body, created_at
  FROM comments
  WHERE issue_id = i.id
  ORDER BY created_at DESC
  LIMIT 1
) c
WHERE i.status = 'open'
ORDER BY i.created_at DESC
LIMIT 25;
```

```text
Nested Loop  (actual time=0.790..352.076 rows=6537.00 loops=1)
  ->  Seq Scan on issues i  (rows=6537.00 loops=1)
  ->  Limit  (rows=1.00 loops=6537)
        ->  Sort  (actual time=0.053..0.053 rows=1.00 loops=6537)
              ->  Bitmap Index Scan on ix_comments_issue_user_date  (loops=6537)
Execution Time: 435.794 ms
```

这条查询会用上之前的 `ix_comments_issue_user_date`，但它的条目是按 `user_id` 排在 `created_at` 前面的，所以 Postgres 对每个未关闭的 issue 都要跑一次排序——一共跑了 6537 次，总共 436ms。

**列顺序又在这里咬了人。** 对这个访问路径来说，`created_at` 必须紧跟在 `issue_id` 后面：

```sql
CREATE INDEX ix_comments_issue_date
ON comments (issue_id, created_at DESC);
```

每次探测变成了一次单行索引扫描，只花 25ms。但 `LIMIT` 还是没法提前终止循环，因为 `issues` 表本身是乱序到达的。再建一个索引流式地把 issue 按时间倒序送进来：

```sql
CREATE INDEX ix_issues_status_date
ON issues (status, created_at DESC);
```

```text
Limit  (actual time=0.086..0.465 rows=25.00 loops=1)
  ->  Nested Loop  (actual time=0.085..0.463 rows=25.00 loops=1)
        ->  Index Scan using ix_issues_status_date on issues i  (rows=25.00 loops=1)
        ->  Limit  (rows=1.00 loops=25)
              ->  Index Scan using ix_comments_issue_date on comments  (rows=1.00 loops=25)
Execution Time: 0.489 ms
```

现在每个节点只读自己需要返回的东西：25 个 issue、25 次探测、每次一条评论。0.5ms，比之前快了将近 900 倍。

## 索引不是免费的

每一条 `INSERT`、`UPDATE`、`DELETE` 都要维护表上的每一个索引，所以你每多加一个索引，写入就会变慢一点点。它们还占磁盘空间，可以用这条查询看：

```sql
SELECT indexrelname AS index_name,
       pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE relname = 'comments';
```

在这个例子中，100 万条评论下，每个复合索引约 30 MB，而单列索引只有约 7 MB。另外要注意：`(issue_id, created_at DESC)` 建好之后，原来那个只含 `issue_id` 的索引就变得多余了，可以删掉。

**请为你真正会跑的查询建索引，而不是为你「未来某天可能会跑」的查询建索引。** 索引只有在查询能用到它时才有价值：如果你把被索引的列包进一个函数里，Postgres 就会忽略这个索引——这是一个很常见的失败模式，我在这篇文章里专门讲过 [为什么 Postgres 会忽略你的索引](https://milanjovanovic.tech/blog/sql-index-not-used-sargability)。

## 小结

- 从查询设计索引，而不是从表设计。
- 复合索引需要正确的列顺序：等值列在前，排序列在后。
- `LIMIT` 只有在索引能按顺序把数据喂给它时才真正有用。
- `EXPLAIN ANALYZE` 是证据。请读计划本身，而不是只看耗时数字。
- 每条索引都带来写入和空间的成本。

一旦索引调对了，**游标分页**就是水到渠成的下一步——它正好建立在这些复合索引之上。

## 常见问题

**什么是复合索引？**
复合索引把几个列一起存，先按第一列排序，再在第一列相等时按第二列排序，再按第三列。Postgres 可以跳到匹配前导列的位置并按顺序读取。

**复合索引的列应该怎么排？**
等值列在前，然后是你要排序或做范围查询的列。在这个例子里，`(issue_id, user_id, created_at DESC)` 把三个条件全部移进了索引条件，并去掉了排序，从 16.6ms 降到 0.04ms。

**为什么只用 user_id 查，用不上复合索引？**
复合索引只能服务使用它前导列的查询。用 `(issue_id, user_id, created_at DESC)` 时，按 `issue_id` 过滤可以，按 `issue_id + user_id` 也可以，但按 `user_id` 单独过滤不行，因为它的值散布在整棵树里。

**为什么建了索引，查询反而更慢了？**
索引进数返回了错误的顺序。仪表盘查询命中了 `(issue_id, user_id, created_at DESC)`，它按 `user_id` 排在了 `created_at` 前面，所以 Postgres 对每个未关闭的 issue 都跑一次排序，一共 6537 次，查询花了 436ms。

**什么是 Index Only Scan？**
指索引本身就能回答问题，Postgres 完全不用读表。数某个用户的评论时，它就是一个零次堆读取的 Index Only Scan，0.6ms，而不是 17ms 的全表扫描。

**索引对写入有没有影响？**
有。每条 `INSERT`、`UPDATE`、`DELETE` 都要维护表上的每个索引，所以每加一个索引写入就慢一点。它还占空间：这里的复合索引每个约 30 MB（100 万条评论），而单列索引只有约 7 MB。

---

Aide Hub 会持续分享 AI 助手、开发工具与软件工程实践，欢迎关注，一起把数据库和系统设计做到位。

## 参考

- 原文：[From 17ms to 0.04ms: How to Design the Right SQL Index (Milan Jovanović)](https://milanjovanovic.tech/blog/how-to-design-the-right-sql-index)
- 为什么 Postgres 会忽略你的索引：[Why Postgres Ignores Your Index (Milan Jovanović)](https://milanjovanovic.tech/blog/sql-index-not-used-sargability)
- [PostgreSQL 官方文档](https://www.postgresql.org)
