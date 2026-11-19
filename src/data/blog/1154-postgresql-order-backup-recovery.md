---
pubDatetime: 2026-11-19T14:37:04+08:00
title: "数据库九课 09｜误删订单后能恢复到哪？"
description: "在 PostgreSQL 实验环境中导出备份、模拟误删，再把订单和流水恢复到独立实例。用数据核对和计时检验恢复能力，比较逻辑备份与基础备份加 WAL 的时间点恢复，并理解 RPO 与 RTO。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-backup-recovery"
ogImage: "../../assets/1154/01-cover.jpg"
source: "https://www.postgresql.org/docs/18/backup.html"
---

订单 100 连同明细和库存流水被误删了。手里有一个备份文件，能不能把这笔订单找回来？备份之后新写入的订单又会缺多少？把备份恢复到独立实例，拿订单号和流水逐项核对，才能回答这两个问题。

这次用 `pg_dump` 导出实验库，再用 `pg_restore` 恢复。逻辑备份能还原导出时看到的数据。要恢复到备份之后、误删之前的某个时间点，需要事先准备基础备份和持续归档的 WAL。WAL 是 PostgreSQL 按顺序记录数据变更、可在恢复时重放的日志。

## 备份前记下恢复基准

准备两个独立的 PostgreSQL 18 实例。这里让源实验库 `orders_lab` 监听本机 55432 端口，恢复实例监听 55433，两个实例都用具备相应权限的实验角色。使用与服务器同一大版本的 `psql`、`pg_dump`、`pg_restore` 和 `createdb`。下面的命令假定连接用户已通过 `PGUSER` 等环境变量设置，认证信息由客户端正常读取。

源库沿用第一篇的数据和第八篇的 `order_source` 字段。先在源库查询，保存结果，之后在恢复库执行同样的 SQL。

```sql
SELECT o.id, o.status,
       (SELECT sum(quantity) FROM order_items WHERE order_id = o.id) AS units,
       (SELECT sum(quantity_delta) FROM inventory_movements
        WHERE order_id = o.id) AS stock_change
FROM orders AS o
WHERE o.id IN (100, 900)
ORDER BY o.id;
```

基准应只有订单 100，一共两件，库存变化为 -2。把库名、时间和这份结果一起记下来。导出到一个新的工作目录。

```bash
pg_dump -h 127.0.0.1 -p 55432 -d orders_lab -Fc -f orders-before.dump
pg_restore --list orders-before.dump
```

`-Fc` 生成可由 `pg_restore` 读取的自定义格式。`--list` 让你先检查备份目录里有没有表和数据项，真正的恢复验证还在后面。

## 模拟备份之后的新写入和误删

**以下写入仅用于第一篇搭建的实验库。** 在源实例先插入订单 900，模拟备份之后写入的订单，再在一个事务里删除订单 100 的三组记录。

```sql
INSERT INTO orders (id, status, order_source)
VALUES (900, 'pending', 'web');

BEGIN;
DELETE FROM inventory_movements WHERE order_id = 100;
DELETE FROM order_items WHERE order_id = 100;
DELETE FROM orders WHERE id = 100;
COMMIT;
```

现在源库跑基准查询只会看到订单 900。这次演练用数据库编号判断数据是否存在，避开了只看总行数可能碰到的巧合。

## 在独立实例恢复，再核对订单与流水

先创建空的恢复库，开始计时，然后执行恢复。两个端口不同，恢复操作不会覆盖源库。恢复库需要能创建相应的表、索引和约束。

```bash
createdb -h 127.0.0.1 -p 55433 orders_restored
pg_restore -h 127.0.0.1 -p 55433 -d orders_restored \
  --no-owner --no-privileges --single-transaction --exit-on-error orders-before.dump
psql -h 127.0.0.1 -p 55433 -d orders_restored
```

在恢复库重新运行基准 SQL。订单 100 应该重新出现，两件明细数量对应 -2 的库存流水。订单 900 应该查不到，因为它在导出之后才写入。实际服务恢复还要验证权限、应用连通性及关键用例。这个实验跳过了原所有者和授权的恢复，因此不能拿权限直接做生产验收。

本地实验里，从创建空库、导入备份到查出订单和流水用了约 1.8 秒。备份文件当时已经在本地，这个数字只覆盖这三个步骤。

如果操作目的是把少数被误删的订单补回仍在运行的库，可以先在独立实例找回，再经业务校验后回填所需记录。整库切回旧恢复点会把缺口带到其他订单，本例的 900 就会一起消失。

## 把恢复点和恢复用时写下来

**RPO（恢复点目标）**回答最多能接受丢多长时间的数据。**RTO（恢复时间目标）**回答最多允许服务中断多久。它们是目标，演练另外记录实际结果。从恢复出的数据判断缺口，从取出备份、启动恢复到应用通过验证计量用时。实际事故还要计入发现故障、决定切换和处理期间新写入的时间。

若每天只导出一次，误删前一天内成功写入的数据可能不在最新备份里。按时间点恢复（PITR）会把基础备份还原，再重放连续归档的 WAL，停在选定的恢复目标。

同一次实验也做了 PITR。在写入订单 900 之前用 `pg_basebackup` 做基础备份，等订单 900 提交后、删除订单 100 之前，用 `pg_create_restore_point('before_order_100_delete')` 记录恢复点。误删后确认对应 WAL 已归档，再在第三个实例上以 `recovery_target_name` 指定这个点。重放完成后，订单 100 的明细和流水都在，订单 900 也在。练习时可以用一个明确的命名恢复点验证流程。实际误删通常没有提前打标记，需要从日志定位事故时间，再选择一个可验证的恢复目标。

GitLab 在 2017 年的数据库事故后公开了恢复过程。事故复盘可以和实验一起读，然后回到自己的备份挑一张具体订单。记录它的订单状态、明细和流水，恢复后逐项核对。这样可以把「备份任务跑完了」变成一条可验证的恢复记录。

## 参考

- [PostgreSQL 18 · 备份与恢复方法](https://www.postgresql.org/docs/18/backup.html)
- [PostgreSQL 18 · 持续归档与时间点恢复](https://www.postgresql.org/docs/18/continuous-archiving.html)
- [PostgreSQL 18 · pg_basebackup](https://www.postgresql.org/docs/18/app-pgbasebackup.html)
- [PostgreSQL 18 · pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html)
- [GitLab · 2017 年数据库事故复盘](https://about.gitlab.com/blog/gitlab-dot-com-database-incident/)
