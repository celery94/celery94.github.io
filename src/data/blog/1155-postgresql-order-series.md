---
pubDatetime: 2026-11-19T14:56:18+08:00
title: "数据库九课 00｜系列总览"
description: "会写基本 SQL 之后，怎样判断订单会不会写错、查询慢在哪里、误删后又能找回多少数据？这份总览把九篇教程串成一条阅读路线，用同一个 PostgreSQL 订单库完成从建表、并发下单到备份恢复的实验。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-series"
ogImage: "../../assets/1155/01-cover.jpg"
source: "https://celery94.github.io/tags/%E6%95%B0%E6%8D%AE%E5%BA%93%E4%B9%9D%E8%AF%BE/"
---

两个人同时买最后一件商品，两个订单都显示成功。后台查最近 20 笔订单，几秒后才返回。一次误删之后，备份里找得回旧订单，新订单却少了一批。这三个问题出现在同一个订单系统里，分别要靠并发实验、执行计划和恢复演练来查证。

《数据库九课》用 PostgreSQL 18 从头走一遍。先建四张表，确保订单、库存和流水能一起写对。再给订单查询加索引、读执行计划，判断销量榜是否值得缓存。后面把同一个实验库用来压测连接池、做结构迁移和恢复数据。

## 01–03 · 把数据写对

1. [01｜旧订单如何保留成交价？](https://celery94.github.io/posts/postgresql-order-data-model/) 商品改价后，为什么旧订单还能显示原来的 2400 分？从当前售价和历史成交价入手，理解规范化以及预存订单总额的维护成本。
2. [02｜下单失败，怎样整单回滚？](https://celery94.github.io/posts/postgresql-order-transactions/) 在库存流水写入时制造错误，核对库存和订单是否一起回滚，认识 ACID 的四项保证。
3. [03｜最后一件库存怎么卖？](https://celery94.github.io/posts/postgresql-order-isolation/) 用两个会话复现超卖，再把库存条件和扣减写进一条 SQL。观察第二个请求为什么拿到 `UPDATE 0`。

## 04–06 · 找出查询慢在哪里

4. [04｜订单索引应该怎么建？](https://celery94.github.io/posts/postgresql-order-indexes/) 对比「某个状态的最新 20 笔」和「全站最新 20 笔」，看两种复合索引怎样改变扫描范围和排序。
5. [05｜有索引，为什么还扫表？](https://celery94.github.io/posts/postgresql-order-query-plans/) 用 `EXPLAIN (ANALYZE, BUFFERS)` 比较估算行数和实际行数，观察更新统计后，数据库对同一条查询的判断怎样变化。
6. [06｜哪些查询值得加缓存？](https://celery94.github.io/posts/postgresql-order-cache-aside/) 为允许短暂延迟的销量榜加 Redis，数一数命中时省了几次查库，同一时间过期时又多了几次。

## 07–09 · 系统上线以后

7. [07｜连接池多大才合适？](https://celery94.github.io/posts/postgresql-order-connection-pooling/) 模拟应用扩容，分开量连接池等待和 SQL 执行，按实际副本数计算连接额度。
8. [08｜怎样给订单表加必填列？](https://celery94.github.io/posts/postgresql-order-schema-migration/) 让新旧版本先一起运行，分批补历史数据，再收紧非空约束。用两个会话亲眼看到改表等锁。
9. [09｜误删订单后能恢复到哪？](https://celery94.github.io/posts/postgresql-order-backup-recovery/) 把备份还原到独立实例，核对订单和流水。对比逻辑备份和按时间点恢复各能找回哪些订单。

## 跟着哪一篇开始？

准备一个空的 PostgreSQL 18 实验库和能执行 SQL 的客户端，从第 01 篇建表，后续保留实验数据。第 06、07 篇会用到 Python，第 06 篇还需要 Redis，第 09 篇需要单独的恢复实例。已经在排查慢查询，可以先读 04、05，动手时再用 01 建表、用 04 生成样本。

做完第 09 篇，保留最后一次恢复的核对结果。记录找回了哪笔订单、哪笔缺失、恢复用了多久。下次调整备份频率或迁移方案，可以用同样的检查重新做一遍。

## 参考

- [数据库九课 · 博客系列目录](https://celery94.github.io/tags/%E6%95%B0%E6%8D%AE%E5%BA%93%E4%B9%9D%E8%AF%BE/)
