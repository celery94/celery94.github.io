---
pubDatetime: 2026-11-19T14:27:52+08:00
title: "数据库九课 05｜有索引，为什么还扫表？"
description: "从同一张订单表的热门状态和稀有状态入手，用 PostgreSQL 的 EXPLAIN 对照顺序扫描、索引扫描、估算行数和实际行数。观察数据分布与统计信息怎样改变执行计划，再用缓冲区计数定位工作量。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-query-plans"
ogImage: "../../assets/1150/01-cover.jpg"
source: "https://www.postgresql.org/docs/18/using-explain.html"
---

同一个状态索引，查待处理订单时能省掉许多工作，查已支付订单时 PostgreSQL 却可能直接扫表。上一篇的测试数据里，已支付订单接近全表，数据库预计一页页顺序读取会更省事。要检验这个判断，可以用执行计划对照估算行数、实际行数和访问过的缓冲区。

在 PostgreSQL 18 的实验库中沿用上一篇的 20 万行订单和 `orders_status_created_at_idx`，保留普通查询的列。这里刻意取所有匹配行，省去 `LIMIT` 对计划的影响。

## 先看数据库准备用什么办法取行

```sql
EXPLAIN
SELECT id, created_at FROM orders WHERE status = 'pending';
```

`EXPLAIN` 显示计划。典型结果是先用 `Bitmap Index Scan` 找出匹配位置，然后由 `Bitmap Heap Scan` 按表页取出订单行。最内层告诉你数据库怎样找到候选记录，最外层反映它最终要交给调用方什么。计划中的 `cost` 是数据库比较方案用的成本单位，没法直接读成毫秒。

## 再用实际结果检查估算

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, created_at FROM orders WHERE status = 'pending';

EXPLAIN (ANALYZE, BUFFERS)
SELECT id, created_at FROM orders WHERE status = 'paid';
```

每个节点通常有两组 `rows`。第一组是计划时估算每次会返回的行数，`actual` 括号里的那组是执行时平均每次返回的行数。节点如果重复执行，记得同时看 `loops`。本例先关注顶层节点，待处理订单约 2000 行，已支付订单约 19.6 万行。

走顺序扫描时，`Rows Removed by Filter` 会告诉你多少行读到后被筛掉。接着看 `Buffers`。其中 `shared hit` 表示该块已在 PostgreSQL 共享缓冲区中，`shared read` 表示需要把块读入共享缓冲区，操作系统也可能用自己缓存的页面满足这次读取。比较两条查询时，可以看各自顶层的缓冲区统计。父节点的统计已经包括子节点，直接把整棵树上的读数相加会重复计算。

`EXPLAIN ANALYZE` 会真的执行语句。做这篇实验只运行 `SELECT`，把带写入或副作用的分析留在隔离环境。

## 人为制造一次行数估错

在一个事务中把前 3 万笔样本中的已支付订单改成待处理。数据立即变了，表的统计信息仍描述更新前的分布。先看一次计划，再执行 `ANALYZE orders` 更新统计，重复同样的查询。

```sql
BEGIN;

UPDATE orders
SET status = 'pending'
WHERE id BETWEEN 1001 AND 31000 AND status = 'paid';

EXPLAIN (ANALYZE, BUFFERS)
SELECT id, created_at FROM orders WHERE status = 'pending';

ANALYZE orders;

EXPLAIN (ANALYZE, BUFFERS)
SELECT id, created_at FROM orders WHERE status = 'pending';

ROLLBACK;
```

实验中，两次执行都返回 31,404 行。更新统计前只估算了 2,330 行，更新后变成 31,187 行。采样和种子订单会影响具体数字。即使节点类型没变化，两组 `rows` 也能说明统计信息改善了什么。两次查询的执行时间还会受缓存预热影响，单凭毫秒变化很难归因。

排查慢 SQL 时，可以先定位第一个估算严重偏离实际的节点。若全表状态分布刚有大变化，更新统计再测。若估算相当准，查询确实需要处理大量数据，就看看接口是否每次都需要这么多行。如果很多请求都在执行同一个汇总，还可以复用查询结果。下一篇用销量榜演示。

## 参考

- [PostgreSQL 18 · 阅读执行计划](https://www.postgresql.org/docs/18/using-explain.html)
- [PostgreSQL 18 · EXPLAIN 参数与执行行为](https://www.postgresql.org/docs/18/sql-explain.html)
