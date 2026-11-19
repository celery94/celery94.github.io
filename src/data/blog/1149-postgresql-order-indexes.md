---
pubDatetime: 2026-11-19T14:25:31+08:00
title: "数据库九课 04｜订单索引应该怎么建？"
description: "同一张订单表有按状态看最新订单、按时间查询以及导出大批订单等几种访问方式。用 PostgreSQL 生成可复现的数据，比较两种 B-tree 复合索引的列顺序，并理解索引对查询和写入的成本。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-indexes"
ogImage: "../../assets/1149/01-cover.jpg"
source: "https://www.postgresql.org/docs/18/indexes-multicolumn.html"
---

后台经常查「最近 20 笔待处理订单」。如果 SQL 先按 `status` 选出待处理订单，再按 `created_at` 倒序取前 20 行，`(status, created_at DESC)` 是一个合适的 B-tree 复合索引。状态相同的条目在索引里相邻，数据库能沿着这段有序条目取数。

另一个页面如果要看所有状态的最新订单，时间排在第一列的索引更贴合它的排序。下面沿用第一篇的 `orders`，用相同的数据试两种列顺序。

## 先造出一张有偏向的订单表

在 PostgreSQL 18 的实验库里运行。保留第一篇的小编号订单，生成的 20 万行从编号 1001 开始。大部分订单已支付，待处理和取消各占约 1%。

```sql
INSERT INTO orders (id, status, created_at)
SELECT 1000 + g,
       CASE
           WHEN g % 100 = 0 THEN 'pending'
           WHEN g % 100 = 1 THEN 'cancelled'
           ELSE 'paid'
       END,
       timestamptz '2026-04-01 00:00:00+00' + g * interval '1 minute'
FROM generate_series(1, 200000) AS g;

ANALYZE orders;

SELECT status, count(*) FROM orders GROUP BY status ORDER BY status;
```

如果重复运行，请使用新的实验库或跳过已有的批量数据。这里让订单状态和时间具有规律，方便复现，真实系统还应使用有代表性的数据分布验证。

## 把状态放在时间前面

先用 `EXPLAIN` 看同一条 SQL 在创建索引前后的计划。它会展示数据库准备怎么取行。下面这段在索引建好后再执行一遍即可。

```sql
EXPLAIN
SELECT id, created_at
FROM orders
WHERE status = 'pending'
ORDER BY created_at DESC
LIMIT 20;
```

```sql
CREATE INDEX orders_status_created_at_idx
ON orders (status, created_at DESC);
```

预期在建索引后看到使用 `orders_status_created_at_idx` 的扫描，计划里通常省去单独的排序。B-tree 先定位到待处理订单，在这一段里，最近的条目已经排在前面。

## 把时间放在状态前面

换一个请求。运营要看全站最近的 20 笔订单，这次没有状态条件。先看原计划，再建时间优先的索引，然后复跑。

```sql
EXPLAIN
SELECT id, status, created_at
FROM orders
WHERE created_at >= timestamptz '2026-08-01 00:00:00+00'
ORDER BY created_at DESC
LIMIT 20;
```

```sql
CREATE INDEX orders_created_at_status_idx
ON orders (created_at DESC, status);
```

原来的索引先按状态分组。取全局最新记录时，就要考虑不同组里的时间。时间优先的索引能直接按全局时间顺序读取。反过来拿它查稀有状态时，扫描最近的记录可能要越过很多其他状态，才能凑齐 20 行。后面几篇只需要状态优先的索引，演示结束后可用 `DROP INDEX orders_created_at_status_idx;` 移除临时索引。

B-tree 前导列有等值条件时，数据库通常能缩小需要访问的范围。PostgreSQL 18 在合适的数据分布下也可能尝试跳跃扫描（skip scan），通过对少数前导值重复定位来利用后面的列。整体排序是否符合 SQL 的 `ORDER BY`，还要单独看。

## 查得多时，索引也会输给扫表

试试去掉 `LIMIT`，请求所有已支付订单。

```sql
EXPLAIN
SELECT id, created_at
FROM orders
WHERE status = 'paid';
```

这条查询命中接近全表的数据。索引里还缺查询需要的 `id`，走索引后通常还要访问很多表页。此时顺序扫描可能更便宜。每个额外的索引还占空间，插入订单和修改索引列时也有维护开销。

为一个页面选索引时，先拿出它实际发送的 SQL，写清筛选、排序和预期返回量，再用代表性数据看计划。下一篇继续用 `orders`，看看估算和实际相差多少，以及到底读了哪些页面。

## 参考

- [PostgreSQL 18 · 多列索引和跳跃扫描](https://www.postgresql.org/docs/18/indexes-multicolumn.html)
- [PostgreSQL 18 · 索引和排序](https://www.postgresql.org/docs/18/indexes-ordering.html)
