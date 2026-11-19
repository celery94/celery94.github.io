---
pubDatetime: 2026-11-19T14:35:05+08:00
title: "数据库九课 08｜怎样给订单表加必填列？"
description: "订单表还在接收写入，应用的新旧版本可能同时运行。用 PostgreSQL 将新增来源字段拆成加列、新写入、分批回填和约束验证，观察表锁会怎样影响发布，并保留历史来源未知的真实含义。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-schema-migration"
ogImage: "../../assets/1153/01-cover.jpg"
source: "https://www.postgresql.org/docs/18/sql-altertable.html"
---

订单表已经有 20 万行，应用还在写入。新版本现在要给每条订单记一个来源。可以先加允许为空的列，让新版本开始写，再等旧版本退出、分批补齐历史数据，最后启用非空约束。发布期间，每一步都要能与当时正在运行的应用版本一起工作。

下面用 PostgreSQL 18 和前几篇的 `orders` 表演示。历史订单无法可靠推断来源时，用 `unknown` 表示这个事实。新订单的来源由入口决定，例如 `web` 或 `app`。

## 先加列，让新旧版本都能写

```sql
BEGIN;
SET LOCAL lock_timeout = '2s';

ALTER TABLE orders ADD COLUMN order_source text;

COMMIT;
```

只加一个可空列的操作通常很快，不过仍需拿到排他的表锁。即使另一条长查询只在读表，也可能让它等待。这里用 `lock_timeout` 限定获取锁的等待时间。如果收到锁超时错误，先回滚，检查持锁事务，换合适的时间重试。

发布新代码前，先确认所有旧写入都显式列出了要写入的字段。旧代码可以继续省略新列，新代码开始显式写 `order_source`。读端暂时用 `COALESCE(order_source, 'unknown')` 显示历史数据。

在实验库里分别运行两代写法，观察它们能否共存。下列两个编号应当尚未使用。这里用负数，避开前几篇的数据。

```sql
INSERT INTO orders (id, status) VALUES (-1, 'pending');
INSERT INTO orders (id, status, order_source)
VALUES (-2, 'pending', 'web');

SELECT id, order_source FROM orders WHERE id IN (-1, -2) ORDER BY id;
```

旧写法插入的订单来源为空，新写法已经有 `web`。线上尤其需要检查后台任务、导入脚本和重试队列。它们也可能继续用旧写法。

## 一批一批补历史订单

等所有写入方都已经带上来源，再补旧数据。下面每次处理 4000 行，用客户端自动提交模式执行。重复执行，直到客户端显示 `UPDATE 0`，再查还有多少行为空。每批独立提交，发布暂停后可以从仍为空的行继续。

```sql
WITH batch AS (
    SELECT id
    FROM orders
    WHERE order_source IS NULL
    ORDER BY id
    LIMIT 4000
)
UPDATE orders AS o
SET order_source = 'unknown'
FROM batch
WHERE o.id = batch.id AND o.order_source IS NULL;
```

最后一个条件用于再次确认目标仍为空。若其他写入已经给这条订单填了真实来源，这批回填应保留它。

```sql
SELECT count(*) AS missing_source
FROM orders
WHERE order_source IS NULL;
```

本地可以快速跑完，线上批大小和间隔要看单批耗时、行锁等待及复制延迟。每批处理多少行，可以在第一批拿到真实数据后调整。

## 验证历史数据，再收紧写入

以下三步分别执行，避免把排他锁带入整个扫描过程。第一步加一个检查约束，`NOT VALID` 会跳过旧数据扫描，之后的插入和更新仍受约束限制。第二步验证旧数据，允许普通读写继续。第三步将列标为 `NOT NULL`，PostgreSQL 能利用已验证的检查约束跳过再次扫描，但仍需要短暂的排他锁。

```sql
BEGIN;
SET LOCAL lock_timeout = '2s';
ALTER TABLE orders
    ADD CONSTRAINT orders_source_present
    CHECK (order_source IS NOT NULL) NOT VALID;
COMMIT;

ALTER TABLE orders VALIDATE CONSTRAINT orders_source_present;

BEGIN;
SET LOCAL lock_timeout = '2s';
ALTER TABLE orders ALTER COLUMN order_source SET NOT NULL;
COMMIT;
```

试一下旧写入。这里用尚未使用的 `-3`，预期数据库以非空约束拒绝插入。

```sql
INSERT INTO orders (id, status) VALUES (-3, 'pending');
```

如果想亲眼看到锁等待，可以在实验库第一个窗口加列前先执行 `BEGIN;` 和 `SELECT id FROM orders WHERE id = 100;`，保持事务不提交。在第二个窗口运行加列步骤，预期触发两秒的锁超时。然后两个窗口分别回滚，重新执行加列。即使改表无需重写数据，现场是否有长事务也会影响发布。

从约束生效开始，省略该字段的旧版本已经无法写入。把这个时间点写入发布计划，并在收紧前核对回退版本也会填来源。回填脚本能重跑，旧版本能否恢复服务还取决于数据库接受哪些写法。

## 参考

- [PostgreSQL 18 · 添加约束、延迟验证和 SET NOT NULL](https://www.postgresql.org/docs/18/sql-altertable.html)
- [PostgreSQL 18 · 表锁与锁冲突](https://www.postgresql.org/docs/18/explicit-locking.html)
