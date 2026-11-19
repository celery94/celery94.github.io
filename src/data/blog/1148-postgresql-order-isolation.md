---
pubDatetime: 2026-11-19T14:23:48+08:00
title: "数据库九课 03｜最后一件库存怎么卖？"
description: "用两个 PostgreSQL 会话同时购买最后一件商品，复现读到同一份库存后覆盖写入的问题。比较提交读、可重复读和可串行化，再用带条件的原子更新保护单行库存，理解跨行规则与事务重试。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-isolation"
ogImage: "../../assets/1148/01-cover.jpg"
source: "https://www.postgresql.org/docs/18/transaction-iso.html"
---

库存表里只剩一件笔记本。两个请求都先读到 1，再各自在应用里算出 0，最后都把 0 写回数据库。库存字段看起来正常，但订单已经收下了两笔。对于这种「改一行库存」的操作，可以把计算和库存检查写进同一条 SQL，并把更新是否返回一行作为下单的条件。

用两个 PostgreSQL 18 的 `psql` 会话就能看出差别。连到同一个实验库，沿用第一篇的四张表。这里新增商品 3，专门用来做并发练习。

```sql
INSERT INTO products VALUES (3, '限量笔记本', 1500, 1);
```

## 两个人都根据旧库存下单

下面按行操作，先让两个窗口都完成读取。为突出竞态，只保留订单头和明细。

| 顺序 | 会话 A                                             | 会话 B                                        |
| ---- | -------------------------------------------------- | --------------------------------------------- |
| 1    | `BEGIN ISOLATION LEVEL READ COMMITTED;`            | `BEGIN ISOLATION LEVEL READ COMMITTED;`       |
| 2    | `SELECT stock FROM products WHERE id = 3;`，读到 1 | 同样执行查询，读到 1                          |
| 3    | `UPDATE products SET stock = 0 WHERE id = 3;`      | 等 A 提交后再执行下一步                       |
| 4    | 写入订单 201 和明细，执行 `COMMIT;`                |                                               |
| 5    |                                                    | `UPDATE products SET stock = 0 WHERE id = 3;` |
| 6    |                                                    | 写入订单 202 和明细，执行 `COMMIT;`           |

写订单时把下面的 `201` 换成各自的订单号。

```sql
INSERT INTO orders (id, status) VALUES (201, 'pending');
INSERT INTO order_items VALUES (201, 3, 1, 1500);
```

两个 `UPDATE` 都返回 `UPDATE 1`。查一下明细，商品 3 卖了两件，库存仍是 0。非负约束只检查最终存入的库存值，它在这个实验中看不到应用使用了旧数据。

```sql
SELECT p.stock, SUM(oi.quantity) AS quantity_sold
FROM products AS p
JOIN order_items AS oi ON oi.product_id = p.id
WHERE p.id = 3
GROUP BY p.id;
```

## 让库存条件和扣减一起执行

在实验库中把商品 3 的库存重设为 1。接下来演示并发扣减，两个窗口分别开启一个 `READ COMMITTED` 事务，然后执行同一条更新。

```sql
UPDATE products
SET stock = stock - 1
WHERE id = 3 AND stock >= 1
RETURNING stock;
```

A 先执行，看到返回库存 0。A 暂时保持事务打开，让 B 执行同一条语句。B 会等 A 释放这行的锁。A 用新订单号 203 写入订单、明细和扣减流水，再提交。PostgreSQL 随后会让 B 根据已经更新的行重新检查库存条件，这次结果是 `UPDATE 0`。B 应回滚，并告诉调用方库存不足。

在实际代码里，把购买量放进参数，先确保它大于 0。数据库更新成功，再在同一事务中完成剩余写入。事务失败后应让整次下单回滚，避免库存扣减脱离订单。

## 隔离级别影响你能看见什么

| PostgreSQL 隔离级别              | 用在订单系统时的具体区别                                                                                                         |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `Read Committed`（提交读，默认） | 普通查询每条语句开始时取一份已提交数据。同一事务连续读两次，两次结果可能不同。                                                   |
| `Repeatable Read`（可重复读）    | 第一次业务语句确定视图，后续查询沿用它，并能看见自己的更改。遇到已经被并发事务修改的目标行，更新可能失败，应用需要重试整个事务。 |
| `Serializable`（可串行化）       | 数据库保证成功提交的事务可以解释为某种先后执行顺序。检测到无法排成这种顺序的并发操作时，事务可能以 `40001` 失败。                |

SQL 标准还定义了 `Read Uncommitted`（未提交读）。PostgreSQL 把它按 `Read Committed` 处理。

单行扣减可以靠刚才的条件更新。若规则变成「两个仓库合计必须至少留一件」，两个请求可能各更新不同的库存行，单行条件就涵盖不了整条规则。可以通过固定顺序锁住所有相关行，也可以让参与该规则的事务用 `Serializable`，并为失败设计有界重试。重试从第一次读取开始，事务外的副作用也需要考虑重复执行。

## 参考

- [PostgreSQL 18 · 事务隔离、并发更新和序列化失败](https://www.postgresql.org/docs/18/transaction-iso.html)
