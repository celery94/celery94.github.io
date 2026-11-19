---
pubDatetime: 2026-11-19T14:19:51+08:00
title: "数据库九课 01｜旧订单如何保留成交价？"
description: "商品改价后，历史订单应该继续显示成交时的价格。用 PostgreSQL 搭建订单、订单明细、商品和库存流水四张表，理解规范化，并动手比较实时汇总与预存总额带来的读写与一致性成本。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-data-model"
ogImage: "../../assets/1146/01-cover.jpg"
source: "https://www.postgresql.org/docs/18/ddl-constraints.html"
---

商品单价从 1200 分改到 1500 分后，一张买了两件的旧订单仍应显示 2400 分。订单明细需要在下单时保存成交单价，查历史订单时就能直接用这份数据。商品表的当前售价继续供商品页使用，两列可以随各自的业务事件变化。

这也是订单系统做表设计时很实用的一条判断：**先弄清每个字段记录的是哪件事、由哪次写入更新。** 同一件事有了两个可写的副本，就要安排同步。两件不同的事即使起初恰好相等，也可以各自保存。

[数据库九课](https://celery94.github.io/tags/%E6%95%B0%E6%8D%AE%E5%BA%93%E4%B9%9D%E8%AF%BE/) 用这套订单数据贯穿全系列。前三篇从表设计讲到事务和并发，接着用索引、执行计划和缓存处理查询，最后做连接池压测、表结构迁移和备份恢复。

## 商品、订单和流水各管什么

| 表                    | 保存的事实                             | 典型变化                       |
| --------------------- | -------------------------------------- | ------------------------------ |
| `products`            | 商品名称、当前售价和可用库存           | 店员改价，库存发生变动         |
| `orders`              | 订单头部信息，包括状态和创建时间       | 订单确认、取消                 |
| `order_items`         | 买了哪件商品、买了几件、按什么价格成交 | 下单时记录，后续按业务规则更正 |
| `inventory_movements` | 每次库存变化及对应订单                 | 一次扣减生成一条流水           |

把只与商品有关的字段放在商品表，把与本次购买有关的字段放在订单明细，是**规范化**的一个常见做法。如果把当前商品名写到每条订单明细，改一次名就得更新许多行，还可能漏掉一部分。如果业务要求重现开票时的商品名称，就另存一个有明确含义的「开票时名称」，由开票动作写入。

## 搭出四张表

准备一个空白的 PostgreSQL 18 实验库，用 `psql` 或任意 SQL 客户端连接。金额统一用分，省去浮点数舍入问题。实验里的订单编号由 SQL 显式指定，后面几篇继续使用这套表结构。

```sql
CREATE TABLE products (
    id bigint PRIMARY KEY,
    name text NOT NULL,
    price_cents integer NOT NULL CHECK (price_cents >= 0),
    stock integer NOT NULL CHECK (stock >= 0)
);

CREATE TABLE orders (
    id bigint PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('pending', 'paid', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    order_id bigint REFERENCES orders (id),
    product_id bigint REFERENCES products (id),
    quantity integer NOT NULL CHECK (quantity > 0),
    unit_price_cents integer NOT NULL CHECK (unit_price_cents >= 0),
    PRIMARY KEY (order_id, product_id)
);

CREATE TABLE inventory_movements (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders (id),
    product_id bigint NOT NULL REFERENCES products (id),
    quantity_delta integer NOT NULL CHECK (quantity_delta <> 0)
);
```

主键用于唯一标识一行，外键要求明细和流水引用的订单、商品确实存在。这个实验中，同一订单里的同一商品合并成一条明细，所以用 `(order_id, product_id)` 作主键。有了这两个字段后，数量和成交单价才有明确归属。

## 改价后重新查历史订单

先放入一张已经成交的演示订单。这里用固定值表示下单后的库存和流水，第二篇再把整个下单过程写成事务。

```sql
INSERT INTO products VALUES (1, '笔记本', 1200, 10);
INSERT INTO orders (id, status) VALUES (100, 'paid');
INSERT INTO order_items VALUES (100, 1, 2, 1200);
INSERT INTO inventory_movements (order_id, product_id, quantity_delta)
VALUES (100, 1, -2);

UPDATE products SET price_cents = 1500 WHERE id = 1;

SELECT oi.order_id,
       oi.unit_price_cents AS sold_price,
       p.price_cents AS current_price,
       oi.quantity::bigint * oi.unit_price_cents AS line_total
FROM order_items AS oi
JOIN products AS p ON p.id = oi.product_id
WHERE oi.order_id = 100;
```

查询返回成交单价 1200、当前售价 1500、小计 2400。删掉查询中的商品表连接，仍然可以得到历史小计。商品表在这里负责提供当前售价，方便当场核对。

## 订单总额什么时候值得另存？

在这个实验里，订单总额就是各行小计相加。先用这条查询得到订单列表需要的数字。

```sql
SELECT order_id, SUM(quantity::bigint * unit_price_cents) AS total_cents
FROM order_items
WHERE order_id = 100
GROUP BY order_id;
```

如果订单列表频繁展示许多订单的总额，实时汇总经实测成了瓶颈，可以在 `orders` 里预存 `total_cents`。这是一种**反规范化**，目的是让常见查询少读明细。下面用一个临时事务展示它多出来的维护步骤。

```sql
BEGIN;
ALTER TABLE orders ADD COLUMN total_cents bigint;
UPDATE orders SET total_cents = 2400 WHERE id = 100;

INSERT INTO products VALUES (2, '书签', 500, 10);
INSERT INTO order_items VALUES (100, 2, 1, 500);

SELECT o.total_cents AS stored_total,
       SUM(oi.quantity::bigint * oi.unit_price_cents) AS calculated_total
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.id
WHERE o.id = 100
GROUP BY o.id;

ROLLBACK;
```

同一张订单查出两个数字。实时汇总得到 2900 分，预存总额还停在 2400 分。选择预存后，新增、删除或更正明细时，都得在同一个事务里维护总额，并用原始明细定期核对。`ROLLBACK` 会撤销这次演示里的加列和插入。

实际订单如果另存「支付渠道确认的实付金额」，那是支付发生时留下的事实，可能包含折扣、运费或退款。字段叫什么、什么时候更新，要由业务含义决定。

保留四张表和订单 100。下一篇会增加一张订单，并在写库存流水时故意触发约束错误，观察前面已经执行的扣库存和订单写入会怎样。

## 参考

- [PostgreSQL 18 · 主键、外键和检查约束](https://www.postgresql.org/docs/18/ddl-constraints.html)
