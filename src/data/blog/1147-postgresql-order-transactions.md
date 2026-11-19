---
pubDatetime: 2026-11-19T14:21:32+08:00
title: "数据库九课 02｜扣库存失败，怎样整单回滚？"
description: "一次下单同时修改库存、订单明细和库存流水，任何一步失败都可能留下残缺数据。用 PostgreSQL 的事务复现流水写入错误，检查回滚和提交后的状态，并理解 ACID 的四项保证及其边界。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-transactions"
ogImage: "../../assets/1147/01-cover.jpg"
source: "https://www.postgresql.org/docs/18/tutorial-transactions.html"
---

扣库存的 `UPDATE` 执行完了，订单也有编号，最后一条库存流水却因为数量为零被数据库拒绝。把这次下单的全部写入放在一个 PostgreSQL 事务里，遇到错误就回滚，库存、订单和流水会一起回到操作前的状态。

事务的边界应当覆盖一次完整的业务写入。这个例子只操作一个数据库，客户端需要使用同一条连接，并在确认四步都成功后才提交。遇到库存不足或者 SQL 出错时，这条连接应先回滚，再交还连接池。

## 在写库存流水时制造一次失败

使用第一篇建立的四张表。以下是一张新订单，购买一件笔记本。打开交互式 `psql`，先查 `products` 中商品 1 的库存和价格。沿用上篇的数据时，两者分别是 10 和 1500。

```sql
SELECT stock, price_cents FROM products WHERE id = 1;
```

逐条运行下列语句。第一条 `UPDATE` 需要返回一行才继续。实际应用应检查受影响行数，并将返回的价格传给插入明细的 SQL，避免把演示里的固定价格写进业务代码。

```sql
BEGIN;

UPDATE products
SET stock = stock - 1
WHERE id = 1 AND stock >= 1
RETURNING stock, price_cents;

INSERT INTO orders (id, status) VALUES (101, 'pending');
INSERT INTO order_items VALUES (101, 1, 1, 1500);

INSERT INTO inventory_movements (order_id, product_id, quantity_delta)
VALUES (101, 1, 0);
```

最后一步触发 `CHECK (quantity_delta <> 0)`。该错误会使 PostgreSQL 当前事务进入失败状态。此时尝试再执行查询，通常会见到 `current transaction is aborted`。清理这次失败需要先执行 `ROLLBACK`。

```sql
ROLLBACK;

SELECT stock FROM products WHERE id = 1;
SELECT count(*) FROM orders WHERE id = 101;
SELECT count(*) FROM order_items WHERE order_id = 101;
SELECT count(*) FROM inventory_movements WHERE order_id = 101;
```

库存回到 10，后三个计数都是 0。回滚后可以用原订单编号再试一遍，把流水中的 0 改成 `-1`，用 `COMMIT` 结束事务。此时库存应为 9，后三个计数都为 1。如果同一编号已经在之前的练习里提交过，请换一个未使用的编号。

## ACID 分别保证什么？

| 属性                  | 在这次下单里意味着什么                                                                   |
| --------------------- | ---------------------------------------------------------------------------------------- |
| 原子性（Atomicity）   | 提交后四步生效。最后一步出错时，回滚也会撤回前面已经执行的扣库存和插入。                 |
| 一致性（Consistency） | `CHECK` 和外键阻止非法数量及无主流水。流水变化量是否等于实际扣减量，需要写入逻辑保证。   |
| 隔离性（Isolation）   | 另一个会话看不到未提交的新订单。两条并发写入最终怎样交错，取决于隔离级别、锁和具体 SQL。 |
| 持久性（Durability）  | 在默认的持久化配置和可靠存储下，成功提交的更改能在数据库崩溃重启后恢复。                 |

你可以打开第二个 `psql`，在第一个窗口提交前查询订单 101。第二个窗口正常查询时看不到这份订单。提交后再发起一个新查询，才会读到它。这个步骤假定第二个窗口处于默认的 `Read Committed` 隔离级别。

还有一种常见故障发生在提交之后：应用发送了 `COMMIT`，连接却在收到响应前断开。此时客户端无法单凭异常判断订单有没有落库，重试需要先用独立、唯一的请求编号查证，或者让重复请求返回同一订单。支付 API 这类外部操作也有自己的提交结果，要另外处理重试和对账。

下一篇让两个会话都看到「还有一件」，再让它们分别下单。事务能保证每个请求里的写入一起成功或回滚，库存仍要靠正确的并发写法来保护。

## 参考

- [PostgreSQL 18 · 事务、提交和回滚](https://www.postgresql.org/docs/18/tutorial-transactions.html)
- [PostgreSQL 18 · 约束](https://www.postgresql.org/docs/18/ddl-constraints.html)
