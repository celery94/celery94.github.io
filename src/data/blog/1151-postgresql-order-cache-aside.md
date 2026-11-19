---
pubDatetime: 2026-11-19T14:31:11+08:00
title: "数据库九课 06｜哪些查询值得加缓存？"
description: "给允许短暂延迟的订单销量榜加一层 Redis 缓存。通过缓存未命中、命中、主动失效和集中到期的实验，看清缓存省下了多少次查库、旧结果会留多久，以及请求同时回源时要付出什么代价。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-cache-aside"
ogImage: "../../assets/1151/01-cover.jpg"
source: "https://redis.io/docs/latest/develop/use-cases/cache-aside/"
---

后台首页的销量榜每次打开都要从已支付订单里汇总商品数量。短时间反复查询同一份榜单，数据库也会反复计算同一个结果。如果业务接受短暂延迟，可以先把汇总结果放进 Redis，并给它一个过期时间。衡量值不值得做，要同时看省下的查库次数和用户能接受多旧的数据。

下面用订单实验库做一次小实验。销量榜可以延迟几十秒。下单时校验库存仍直接访问数据库。

## 先查缓存，未命中再查库

这种由应用读写缓存的方式叫 **Cache-Aside**。应用先查 Redis。有结果就返回，没有结果才去 PostgreSQL 汇总，并把结果写入 Redis。写入时同时设置 TTL，即这份缓存还能存活多久。

准备 Python、可连接的 PostgreSQL 18 和独立的本地 Redis。数据库沿用前两篇，订单 100 已支付，订单 101 至少有一条明细。先用 `psql` 验证环境变量能连到实验库，例如设置 `PGHOST`、`PGPORT`、`PGUSER` 和 `PGDATABASE`。脚本默认连接本机 Redis 的 6379 端口，可以通过 `REDIS_URL` 改用其他实验端口。

```bash
python -m pip install "psycopg[binary]" redis
```

把下面的代码保存为 `sales_cache.py`，执行 `python sales_cache.py`。脚本会改变实验订单 101 的支付状态。每次运行使用独立的缓存键，避免复用前一次的结果。

```python
import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from uuid import uuid4

import psycopg
import redis

cache = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
    decode_responses=True,
)
key = f"lab:top-sales:{uuid4()}"
query_count = 0
count_lock = Lock()

sales_sql = """
    SELECT oi.product_id, SUM(oi.quantity) AS units_sold
    FROM order_items AS oi
    JOIN orders AS o ON o.id = oi.order_id
    WHERE o.status = 'paid'
    GROUP BY oi.product_id
    ORDER BY units_sold DESC, oi.product_id
    LIMIT 10
"""


def top_sales(miss_gate=None):
    global query_count

    cached = cache.get(key)
    if cached is not None:
        return json.loads(cached)

    if miss_gate is not None:
        miss_gate.wait(timeout=10)  # Force every test request to miss first.

    with psycopg.connect() as db:
        rows = [list(row) for row in db.execute(sales_sql)]

    with count_lock:
        query_count += 1
    cache.set(key, json.dumps(rows), ex=30)
    return rows


def update_demo_order(status):
    with psycopg.connect() as db:
        result = db.execute(
            "UPDATE orders SET status = %s WHERE id = 101",
            (status,),
        )
        if result.rowcount != 1:
            raise RuntimeError("Create demo order 101 from lesson 02 first.")


update_demo_order("pending")
print("cold:", top_sales(), "queries:", query_count)
print("warm:", top_sales(), "queries:", query_count)

update_demo_order("paid")
print("before invalidation:", top_sales(), "queries:", query_count)
cache.delete(key)
print("after invalidation:", top_sales(), "queries:", query_count)

cache.expire(key, 0)
gate = Barrier(8)
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(top_sales, gate) for _ in range(8)]
    for future in futures:
        future.result()
print("after concurrent misses:", query_count)
```

只用了前两篇的种子数据时，前两次输出都是 `[[1, 2]]`，也就是商品 1 卖了两件，查库计数停在 1。订单 101 改成已支付后，缓存还会返回旧数字。删除旧键再读，结果变成 `[[1, 3]]`，计数上升到 2。如果实验库里还有其他已支付订单，榜单数字会不同，查库计数的变化相同。

## 同一份缓存到期，八个请求都回源

最后一段让榜单立即过期，再让八个并发请求都读到空缓存后一起继续。查库次数从 2 增加到 10。这个同步点只用于稳定复现竞争。在真实系统里，只要榜单重算的时间足够长，新请求就可能赶在结果写回前集中回源。

热点榜单可以让同一个键的请求合并，由一个请求重算，其他请求等待或暂时使用旧值。给不同键的到期时间加入随机偏移，能减少大批不同键同时过期。它仍需要和单键的并发处理配合。

实际发布时，查库成功和重新填充之间也可能插进一次更新。比如请求 A 查完旧数据，B 提交新数据并删除旧缓存，A 随后又把旧数据写回。这个例子用 30 秒 TTL 给单份缓存设置过期时间，允许短暂陈旧。如果榜单需要更严格的及时性，要把重填竞态、失效失败和 Redis 故障时的回源量纳入设计。

在决定缓存另一个页面之前，先弄清数据允许陈旧多久。试运行时记录缓存命中率和数据库查询次数。如果重复请求很少，先改善 SQL 往往更简单。如果慢在查库之前，先看请求有没有在等连接。下一篇会把这段时间单独量出来。

## 参考

- [Redis · Cache-Aside 的适用条件和并发问题](https://redis.io/docs/latest/develop/use-cases/cache-aside/)
- [Redis · EXPIRE 的到期行为](https://redis.io/docs/latest/commands/expire/)
