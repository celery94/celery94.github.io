---
pubDatetime: 2026-11-19T14:33:13+08:00
title: "数据库九课 07｜连接池多大才合适？"
description: "应用副本增多后，每个实例的连接池都会占用 PostgreSQL 的连接额度。用本地压测区分池内等待和 SQL 执行时间，按实例数核算连接预算，并理解 PgBouncer 事务池对会话状态的影响。"
tags: ["PostgreSQL", "数据库九课"]
slug: "postgresql-order-connection-pooling"
ogImage: "../../assets/1152/01-cover.jpg"
source: "https://www.postgresql.org/docs/18/runtime-config-connection.html"
---

每个应用实例的连接池上限是 20，单个实例跑得好好的，扩到五个实例后却开始报数据库连接不足。连接额度要按**所有实例的池上限之和**计算。排查延迟时，分别记录借连接耗时和执行 SQL 耗时。

连接池保存一批可复用的数据库连接。请求短时间借用其中一条，用完归还。PostgreSQL 直接接入的每条客户端连接都有对应的服务器进程，数据库还要为这些连接和正在执行的查询消耗资源。提高池上限会减少一部分等连接的时间，也可能把更多并发工作同时推给数据库。

## 先算连接额度，再算应用副本

假设数据库允许 100 条连接，你计划为监控、迁移、其他服务及管理登录腾出 20 条，订单应用的总额度就是 80。4 个实例每池 20，已经用完这份额度。部署期间如果短暂跑到 5 个实例，应用最多会尝试使用 100 条。实际预算要计算可能同时存在的副本，并查看数据库给特定角色预留了多少连接。

在实验库里可以先读几个参数，再按应用名统计客户端连接。

```sql
SHOW max_connections;
SHOW reserved_connections;
SHOW superuser_reserved_connections;

SELECT application_name, state, count(*) AS connections
FROM pg_stat_activity
WHERE backend_type = 'client backend'
GROUP BY application_name, state
ORDER BY application_name, state;
```

`idle` 表示连接当前空闲，依然占用一个连接槽。`idle in transaction` 则表示有事务尚未结束，可能继续持有锁或让旧版本数据迟迟无法清理。调查连接池时，这两种状态应分开看。

## 把等连接和执行 SQL 分开计时

准备 Python 和可连接的 PostgreSQL 18 实验库。沿用上一篇的 `PGHOST`、`PGPORT`、`PGUSER` 和 `PGDATABASE`。数据库只需能运行 SQL，实验用 `pg_sleep(0.12)` 模拟一条服务端耗时稳定的查询。

```bash
python -m pip install "psycopg[binary,pool]"
```

保存为 `pool_demo.py`。第一个参数模拟应用实例数，第二个参数是每个池的连接数。每个实例同时接到 8 个请求，先把池预热，避免把首次建连的时间算进去。

```python
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from statistics import median
from time import perf_counter

import psycopg
from psycopg_pool import ConnectionPool

instances, pool_size = map(int, sys.argv[1:] or ["1", "2"])
requests_per_instance = 8


def run_request(pool):
    start = perf_counter()
    with pool.connection(timeout=5) as conn:
        borrowed = perf_counter()
        conn.execute("SELECT pg_sleep(0.12)").fetchone()
        finished = perf_counter()
    return (borrowed - start) * 1000, (finished - borrowed) * 1000


with ExitStack() as stack:
    pools = []
    for instance in range(instances):
        pool = stack.enter_context(
            ConnectionPool(
                min_size=pool_size,
                max_size=pool_size,
                kwargs={"application_name": f"lesson07-{instance}"},
                open=False,
            )
        )
        pool.wait(timeout=10)
        pools.append(pool)

    with ThreadPoolExecutor(
        max_workers=instances * requests_per_instance,
    ) as executor:
        futures = [
            executor.submit(run_request, pool)
            for pool in pools
            for _ in range(requests_per_instance)
        ]
        wait_ms, sql_ms = zip(*(task.result() for task in futures))

    with psycopg.connect() as db:
        connections = db.execute(
            """
            SELECT count(*) FROM pg_stat_activity
            WHERE application_name LIKE 'lesson07-%'
            """
        ).fetchone()[0]

    print(f"connections={connections}")
    print(f"pool wait median={median(wait_ms):.1f} ms")
    print(f"sql time median={median(sql_ms):.1f} ms")
```

```bash
python pool_demo.py 1 2
python pool_demo.py 1 4
python pool_demo.py 4 2
```

第一组只有 2 条连接，8 个请求需要分批执行。第二组把单实例的池放大到 4，等连接时间会下降，单条 SQL 耗时仍接近 120 毫秒。第三组模拟 4 个实例，每个池仍是 2 条，数据库连接数会增至 8，单实例内部还要分批处理。本地一次实测中，单实例从 2 条连接增至 4 条后，借连接的中位数从约 202 毫秒降至约 63 毫秒，SQL 耗时的中位数都在 128 毫秒左右。这个实验刻意固定了查询耗时，线上还要测数据库在额外并发下的吞吐和尾部延迟。

## 加一层 PgBouncer 时，先检查会话依赖

应用池和 PgBouncer 可以一起使用。PgBouncer 的事务池模式在一个事务结束后会归还服务器连接，下一次事务可能换一条。靠会话一直保留的临时表、跨事务的 `SET` 或会话级锁，都需要逐项检查。事务内的临时设置可以考虑 `SET LOCAL`。

上线后把池等待、SQL 耗时和数据库连接数放在一起看。池等待长且数据库还有余量，可以小幅调高池上限后重测。若 SQL 本身已经在高并发下变慢，提高池上限可能延长整体响应时间。后面做表结构迁移时，同样要分清请求是在等连接，还是已经拿到连接、卡在表锁上。

## 参考

- [PostgreSQL 18 · 连接上限和预留连接](https://www.postgresql.org/docs/18/runtime-config-connection.html)
- [PostgreSQL 18 · pg_stat_activity](https://www.postgresql.org/docs/18/monitoring-stats.html)
- [Psycopg 3 · 连接池](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
- [PgBouncer · 不同池模式的能力](https://www.pgbouncer.org/features.html)
