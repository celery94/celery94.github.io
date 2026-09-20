---
pubDatetime: 2026-09-20T09:00:00+08:00
title: "Postgres 更爱走新索引，但它扫错了方向"
description: "新增索引会给规划器多一条看似更便宜的路径。本文用 PostgreSQL 18.6 上的百万行实验说明这个查询如何从 16.5ms 涨到 241ms，并给出索引改法、计划读法与验证步骤。"
tags: ["PostgreSQL", "索引", "查询优化", "EXPLAIN", "数据库"]
slug: "postgres-picks-the-wrong-index"
ogImage: "../../assets/1075/01-cover.jpg"
source: "https://milanjovanovic.tech/blog/when-postgres-picks-the-wrong-index"
---

先看这组数字。同一个查询，同一张表，什么都没改，只多建了一个索引：执行时间从 16.537ms 变成 241.354ms，慢了将近 15 倍。再建第二个索引，它掉到 0.067ms。

Milan Jovanović 在 [When Postgres Picks the Wrong Index](https://milanjovanovic.tech/blog/when-postgres-picks-the-wrong-index) 里用一百万行评论数据把这个反直觉现象完整复现了一遍，并给出了[可直接运行的实验脚本](https://milanjovanovic.tech/labs/postgres-index-regression)。原文的价值不在于「索引要谨慎」这句结论，而在于它展示了一个能自己复现、也能套用到其它查询上的判断方法：**看成本估算和实际走过多远的差距**。本文按「实验 → 三份计划 → 估算为什么错 → 怎么改 → 怎么验证」重排，并补上原文没展开的部分：`shared hit` 这个计数的含义，以及回到生产环境后该怎么确认自己遇到的是同一类问题。

## 一个可复现的百万行实验

表结构很简单，`comments` 有 `id`、`user_id`、`body`、`created_at` 四列，一共一百万行。数据分布是设计过的关键：100 个用户里，用户 42 拥有 10,000 条评论，全部落在 12 到 14 个月前；其他人的评论散布在最近两年里。

```sql
CREATE TABLE comments (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

SELECT setseed(0.212);
INSERT INTO comments (user_id, body, created_at)
SELECT 1 + (g % 100),
       'Comment body ' || g,
       CASE WHEN 1 + (g % 100) = 42
            THEN TIMESTAMPTZ '2026-09-01' - INTERVAL '14 months'
                 + random() * INTERVAL '2 months'
            ELSE TIMESTAMPTZ '2026-09-01' - random() * INTERVAL '2 years'
       END
FROM generate_series(1, 1000000) AS g;

CREATE INDEX ix_comments_user_id ON comments (user_id);
VACUUM ANALYZE comments;
```

`setseed(0.212)` 固定了随机序列，日期锚点也写死，所以任何人跑出来的行数分布都一样，只有耗时会有差异。

要模拟的场景是一个「一年前就停更的用户」：个人主页仍要展示他最近的十条评论。

```sql
SELECT *
FROM comments
WHERE user_id = 42
ORDER BY created_at DESC
LIMIT 10;
```

原始测量环境是 PostgreSQL 18.6，每次查询跑两遍并引用第二遍的耗时，以避开首次执行带来的额外开销。

## 三份计划，三次换路

**只有 `user_id` 索引时**，Postgres 先用位图索引扫描找到这个用户的全部 10,000 条评论，搬出来做 top-N 排序，只留十条。

```text
Limit
  -> Sort
       -> Bitmap Heap Scan on comments (rows=10000.00 loops=1)
            -> Bitmap Index Scan on ix_comments_user_id
Execution Time: 16.537 ms
```

**再加一个按日期排序的索引**——比如另一个页面要展示全站最新评论：

```sql
CREATE INDEX ix_comments_created_at
ON comments (created_at DESC);
```

同一个个人主页查询立刻换了路。

```text
Limit
  -> Index Scan using ix_comments_created_at on comments
       Filter: (user_id = 42)
       Rows Removed by Filter: 495944
Execution Time: 241.354 ms
```

它现在沿着日期索引从最新往旧走，一边走一边用 `user_id = 42` 过滤，在找到十条之前丢弃了 495,944 行。用户 42 的评论全是一年前的，而索引从最近的时间开始扫，所以几乎要走遍整个索引才碰到目标。

**把过滤键和排序列放进同一个索引**：

```sql
CREATE INDEX ix_comments_user_date
ON comments (user_id, created_at DESC);
```

```text
Limit
  -> Index Scan using ix_comments_user_date on comments
       Index Cond: (user_id = 42)
Execution Time: 0.067 ms
```

这个索引能直接跳到用户 42 的那一段，而这一段本身已经按时间倒序排好，读十条就停。

## 规划器为什么会选那条远路

规划器要给每条可行路径估一个成本，再挑最低的。一个和 `ORDER BY` 顺序一致、又配着 `LIMIT` 的索引看起来特别划算，因为理论上找到足够多的匹配行就能提前停。

用户 42 大约占全表的 1%。如果他的评论均匀散布在时间轴上，走十条大概只需要检查一千个索引条目——这比取出 10,000 行再排序便宜得多。

问题出在这句话的前提上：**这个用户的评论并不均匀分布，而是全部集中在时间轴的一端**。规划器的估算里没有「匹配项在排序中的位置」这条信息。

这个赌注在计划里留下了痕迹。两个方案顶层 `Limit` 节点的估算总成本分别是 9194.00 和 63.93。注意这是成本单位，不是毫秒，不能直接当成耗时读。前一个方案要先把 10,000 行搬出来排序，所以估算成本高；后一个方案被认为能很快停下，所以估算成本低。

估算的匹配行数是 9,733，实际是 10,000，误差只有 2.7%。**规划器算对了「有多少条」，算错的是「要扫多远才能碰到它们」。**

这也解释了一个常见误判：这里不是统计信息过期。数据导入后立刻跑过 `VACUUM ANALYZE`，统计信息是新鲜的，再跑一次 `ANALYZE` 也教不会单列统计去描述「某个用户的评论在时间轴上集中在哪个区间」。普通单列统计只知道 `user_id` 的分布和 `created_at` 的分布，不知道两者的相关性。

## 索引要同时接住过滤和排序

把等值条件放前面、排序列放后面，是这个查询最直接的解法：

```sql
CREATE INDEX ix_comments_user_date
ON comments (user_id, created_at DESC);
```

复合 B-tree 索引先按第一列排序，第一列相同再按第二列排。所以 `user_id = 42` 那一段内部已经满足 `created_at DESC`，`LIMIT 10` 读完十条就能停，`Index Cond` 同时覆盖了过滤和排序，`Sort` 节点也消失了。

代价是实在的：多一个索引要占空间、要在写入时维护。而且新的复合索引可能让原来的 `ix_comments_user_id` 变得多余——`user_id` 的等值条件已经由复合索引的前缀承担。不过 `user_id` 单列索引上还可能挂着别的查询和依赖，删之前先查清楚。

顺带一个容易踩的判断：**加了索引之后变慢，不等于索引本身写错了**。`ix_comments_created_at` 对「展示全站最新评论」那个页面完全合理，它只是恰好也给这个个人主页查询提供了一条看起来更便宜的路径。两个需求对索引的要求不同，冲突发生在规划器的选择上，而不是索引的定义上。

## 用 shared buffer 看清真实工作量

耗时容易被缓存和机器状态干扰，原文引用了另一个更稳定的证据：缓冲区计数。

在实验脚本里，`EXPLAIN (ANALYZE, BUFFERS)` 输出显示，日期索引方案在找到十条之前产生了 497,260 次 shared buffer hit，而原始方案是 8,344 次。二者相差近 60 倍，方向和耗时一致。

这里要分清两个概念：

- `shared hit` 是**缓冲区访问次数**，同一页被反复访问会重复计数，它不是「访问了多少个不同的页」。
- 正因为它会重复计数，所以它能反映扫描的路径长度和重复程度。缓存再热，也改变不了这条路径要走多远。

在原文提供的[完整实验输出](https://milanjovanovic.tech/labs/postgres-index-regression) 里，还有一个容易被忽略的细节：同一个计划连跑两次的耗时会波动。基线计划第一遍 10.084ms、第二遍 16.537ms，两者计划完全相同，差异来自缓存预热和机器噪声。所以判断回归时不要只盯着单次毫秒数，而要同时看**计划形状**（换没换索引、有没有多出 `Rows Removed by Filter`）和**缓冲区计数**。这两项稳定得多，也更能说明问题。

## 在生产里怎么查同一类问题

先复现实验，再谈生产。原文给了完整的 Docker 流程：

```bash
docker run -d --name mnw212-lab -e POSTGRES_PASSWORD=postgres postgres:18.6-alpine
docker exec mnw212-lab pg_isready -U postgres
docker cp lab.sql mnw212-lab:/tmp/lab.sql
docker exec mnw212-lab psql -X -U postgres -f /tmp/lab.sql
```

等 `pg_isready` 报接受连接后再执行 `psql`。脚本会自己建 `index_lab` schema 并在每次运行时重建，数据集用固定随机种子生成，所以可以反复跑，行数和计划形状应当与 `output.txt` 一致，只有耗时会不同。

跑通之后，建议做两次对照实验，它们比原始复现更能说明问题：

1. **换一个活跃用户**（实验里是 `user_id = 7`，评论散布在两年里）。规划器同样会选日期索引，但这次最新匹配就在索引前端，`Rows Removed by Filter` 会接近原文估算的「一千个条目」，而不是五十万。这条对照证明了根因是数据分布，不是索引本身。
2. **先别删旧索引**。在原实验里，复合索引建好之后即使删掉 `ix_comments_user_id`，用户 42 的查询计划也不变，因为等值条件已经由复合索引前缀承担。但这只是这个查询的情况，不能当成通用结论。

回到自己的库，按这个顺序查：

1. 找到可疑查询，用 `EXPLAIN (ANALYZE, BUFFERS)` 看 `Limit` 下面第一个真正干活的节点。
2. 看 `Rows Removed by Filter`。这个数字很大，说明扫描路径和过滤条件不匹配。
3. 同时看 `shared hit`。它比耗时稳定，能确认工作量确实增加了。
4. 比对建索引前后的计划，而不是只比对耗时。**参数必须一致**，还要覆盖不同类型的参数值——只测最活跃的账号，正好会漏掉这类回归。
5. 候选索引按「等值列在前、排序列或范围列在后」构造，然后重新测量。

还要提醒一句：原文的实验规模是百万行、单表、纯读。真实系统里还牵扯并发写入、索引膨胀、autovacuum 时机和其它查询的计划变化。上面的步骤给的是定位方法，不是可以直接照抄的参数。

## 结论

1. **新增索引会改变已有查询的计划。** 只要新索引给规划器多提供了一条路径，它就可能被选中。
2. **规划器的成本不是距离。** 在这个例子里它估对了匹配行数，却不知道要扫多远才能碰到它们。
3. **`Rows Removed by Filter` 很大时，先怀疑索引和查询不匹配**，而不是先去调规划器参数。
4. **索引要同时服务过滤与排序。** `(user_id, created_at DESC)` 之所以有效，是因为它把等值条件和排序列放在了同一段有序结构里。
5. **`ANALYZE` 不是万能解。** 统计信息新鲜时也可能选错，因为单列统计描述不了列之间的相关性。
6. **验证要看计划和缓冲区**，不要只看单次耗时。

如果你手上正好有「加索引之后某个接口变慢」的案例，可以先做两件事：把该查询的 `EXPLAIN (ANALYZE, BUFFERS)` 在加索引前后各存一份，然后确认这两份计划里 `Rows Removed by Filter` 和 `shared hit` 的变化方向是否一致。这两份输出通常比耗时曲线更能说明发生了什么。

Aide Hub 会继续整理这类可复现的性能分析，覆盖数据库、.NET 和软件工程实践。

## 参考

- [When Postgres Picks the Wrong Index (And How to Fix It)](https://milanjovanovic.tech/blog/when-postgres-picks-the-wrong-index)（原文，Milan Jovanović）
- [Postgres index regression lab（含 lab.sql、output.txt 与 Docker 步骤）](https://milanjovanovic.tech/labs/postgres-index-regression)
- [PostgreSQL 18.6 Release Notes](https://www.postgresql.org/docs/release/18.6/)
- [PostgreSQL: Using EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html)
- [PostgreSQL: Indexes and ORDER BY](https://www.postgresql.org/docs/18/indexes-ordering.html)
- [SQL Indexing Explained: Composite Indexes and Column Order](https://milanjovanovic.tech/blog/how-to-design-the-right-sql-index)
