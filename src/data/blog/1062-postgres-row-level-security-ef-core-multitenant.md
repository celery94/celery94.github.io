---
pubDatetime: 2026-09-14T07:32:00+08:00
title: "Postgres RLS：EF Core 多租户的第二道防线"
description: "EF Core 查询过滤器管不到原生 SQL、附加实体和 IgnoreQueryFilters。用 Postgres 行级安全策略在数据库层补上第二道防线：角色拆分、每次连接设置租户、绕过验证、计划代价与运维边界。"
tags: ["PostgreSQL", "EF Core", "多租户", ".NET 10", "数据库安全"]
slug: "postgres-row-level-security-ef-core-multitenant"
ogImage: "../../assets/1062/01-cover.jpg"
source: "https://milanjovanovic.tech/blog/postgres-row-level-security-with-ef-core"
---

EF Core 的全局查询过滤器（global query filter）会给它生成的每条 SQL 加上 `WHERE tenant_id = @tenant`，但只加在它生成的那些语句上。有人在管理报表里顺手写了 `IgnoreQueryFilters()`，有人发了一段原生 SQL，有人把一个只填了主键的实体 `Attach` 上去改状态——这几条路径里都没有过滤器。

Milan Jovanović 在 [Let Postgres Enforce Tenant Isolation](https://milanjovanovic.tech/blog/postgres-row-level-security-with-ef-core) 里给这类应用补了第二层：把租户规则写成 Postgres 的行级安全（row-level security，RLS）策略，让数据库自己拒绝越界读写。配套的 [lab](https://milanjovanovic.tech/labs/postgres-row-level-security) 用 PostgreSQL 18 建了 50 个租户、共 100 万行 `invoices`，逐个验证哪些绕过方式会被挡住、哪些挡不住、代价是多少。本文按「建策略 → 每连接设置租户 → 试着绕过 → 看执行计划 → 给运维留出口」的顺序整理，并用 PostgreSQL 18 官方文档核对了几处容易踩的边界。

## 过滤器漏掉的是哪几类语句

全局查询过滤器生效的前提是「查询由 EF Core 生成」。只要语句不是这么来的，过滤器就不存在：

- `Database.ExecuteSqlRaw` / `ExecuteSql` 发出去的原生 SQL
- 手动 `Attach` 或 `Update` 一个只填了主键的实体，EF 只按主键拼 `WHERE id = @p0`
- 任何被 `IgnoreQueryFilters()` 关掉过滤器的查询，包括为了做管理端报表临时加上的那种
- `ExecuteUpdateAsync` / `ExecuteDeleteAsync` 直接下发的语句

这些恰好是数据修复、后台任务和紧急脚本最常用的写法。第二层的目标不是让开发者记得写谓词，而是让「忘记」这件事不再造成越权——策略由数据库在每次执行时附加，应用看不到它，也就绕不过它。

## 建策略：USING 管读，WITH CHECK 管写

策略本身只有几行。下面是 lab 里 `invoices` 表用的那条：

```sql
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON invoices
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

三个细节决定了它的强度。

`USING` 决定一次读、更新或删除能碰到哪些行，`WITH CHECK` 决定新写入的行是否被接受。只写 `USING` 时 Postgres 会隐式补上一条与它完全相同的 `WITH CHECK`，所以两者都显式写出来不是为了补一个漏洞，而是让「能看见哪些行」和「能写哪些行」这两条规则在 SQL 里直接可读，将来需要分别调整时也有明确的落点。

`NULLIF(..., '')` 把「没有设置租户」变成 `NULL`，而 `NULL` 与任何值的比较都不是 `true`。lab 的场景 5 验证了这一点：没有解析出租户时，`current_setting` 返回空字符串，带过滤器和 `IgnoreQueryFilters()` 的查询都返回 0 行。这是 fail closed——宁可什么都查不到，也不要因为设置缺失而放行全表。

`FORCE` 让表的所有者也受策略约束。默认情况下超级用户、带 `BYPASSRLS` 的角色和表的 owner 都跳过策略，而很多应用里「跑迁移的账号」和「服务请求的账号」是同一个。lab 的场景 2 把差别打了出来：

| 连接角色               | 表上的设置         | `IgnoreQueryFilters()` 看到的行数 |
| ---------------------- | ------------------ | --------------------------------- |
| `app_owner`            | 仅 `ENABLE`        | 1,000,000                         |
| `app_owner`            | `ENABLE` + `FORCE` | 20,000                            |
| `postgres`（超级用户） | `ENABLE` + `FORCE` | 1,000,000                         |

所以角色要拆开：`app_owner` 拥有表、只用来跑迁移，`app_user` 什么也不拥有、只拿它需要的 DML 权限。应用连 `app_user`。这样 `DROP POLICY`、`ALTER TABLE ... NO FORCE` 这些语句不在应用进程的权限范围里，即使应用被注入也改不掉策略。

## 租户要在每次连接打开时设置

策略读的是一个会话变量，所以应用得把它设上。直觉上会在请求开始时 `SET app.tenant_id = ...`，但这条路走不通。

EF Core 为一条命令打开连接、执行完就关掉，而 [Npgsql 在连接归还池子时会安排重置状态](https://www.npgsql.org/doc/performance.html#pooled-connection-reset)——重置通过 `DISCARD ALL` 完成。于是紧跟在 `SET` 之后的那次查询，可能跑在一个刚从池子里取出来的、从没听说过租户的连接上。lab 的场景 6 就是这个结果：`SET` 之后查询 0 行，只有当 EF 保持连接打开时才看得到 20,000 行。

把重置关掉更糟。连接串加上 `No Reset On Close=true` 之后，lab 场景 7 显示下一个没设任何租户的请求继承了上一个请求的租户：

```text
default (reset on close)   next request, no SET: setting = '',                                       0 rows visible
No Reset On Close=true     next request, no SET: setting = '00000000-0000-0000-0000-000000000001',  20,000 rows visible
```

这不是性能调优的副作用，这是一次真实的跨租户数据泄漏：下一个请求什么都没做，就看到了上一个请求的租户的全部数据。场景 7 的最后一行显示，启用拦截器之后，同一个物理连接上以租户 2 身份发起的请求会把自己的租户写回去，读到的是 20,000 行租户 2 的数据。

正确的做法是：每次连接打开时设置，不管池子把它交给谁。EF Core 的连接拦截器正好有这个钩子：

```csharp
// One instance per request scope. Null means nothing resolved a tenant.
public sealed class TenantContext
{
    public Guid? TenantId { get; set; }
}

public sealed class TenantConnectionInterceptor(TenantContext tenant) : DbConnectionInterceptor
{
    private const string Sql = "SELECT set_config('app.tenant_id', @tenant, false)";

    public override void ConnectionOpened(DbConnection connection, ConnectionEndEventData eventData)
    {
        using var command = Build(connection);
        command.ExecuteNonQuery();
    }

    public override async Task ConnectionOpenedAsync(
        DbConnection connection, ConnectionEndEventData eventData, CancellationToken cancellationToken = default)
    {
        await using var command = Build(connection);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    private DbCommand Build(DbConnection connection)
    {
        var command = connection.CreateCommand();
        command.CommandText = Sql;
        var parameter = command.CreateParameter();
        parameter.ParameterName = "tenant";
        parameter.Value = tenant.TenantId?.ToString() ?? "";
        command.Parameters.Add(parameter);
        return command;
    }
}
```

几个刻意的选择：用 `set_config` 而不是字符串拼 `SET`，租户值走绑定参数；第三个参数 `false` 表示会话级，`true` 只作用于当前事务（[官方文档](https://www.postgresql.org/docs/18/functions-admin.html)）；没有租户时传空字符串，交给策略里的 `NULLIF` 变成「查不到任何行」，而不是拼出一个语法错误的 `SET`。

注册时把两个服务都放成 scoped：

```csharp
builder.Services.AddScoped<TenantContext>();
builder.Services.AddScoped<TenantConnectionInterceptor>();
builder.Services.AddDbContext<AppDbContext>((sp, options) => options
    .UseNpgsql(connectionString)
    .AddInterceptors(sp.GetRequiredService<TenantConnectionInterceptor>()));
```

这里必须用 `AddDbContext` 而不是 `AddDbContextPool`：池化的 `DbContext` 会保留第一个请求的 `TenantContext`，租户就固化了。相应地，`TenantContext` 由 scoped 生命周期决定它属于当前请求，拦截器每次打开连接时读的就是这个值。

代价是每次连接打开多一次往返。lab 的场景 12 跑了 500 次请求：开启拦截器 1.293 ms / 1.214 ms 每请求，关闭 0.844 ms / 0.817 ms，差值约 0.4–0.45 ms。原文作者在自己的测试里给的也是约 0.4 ms。这个量级对绝大多数请求可以接受，但如果你的接口本身只有 1 ms，它就不是免费的。

如果前面挂着 PgBouncer 的事务池模式，会话级设置在事务之间不保证落在同一个物理连接上，这时要把租户改成在显式事务里用 `set_config(..., true)` 设置。

## 试着绕过它，看会发生什么

策略建好之后，把文章开头列的绕过方式逐个试一遍，验证方式不是「读代码觉得没问题」，而是看返回值和 SQLSTATE。

关掉过滤器按主键更新：

```csharp
var affected = await db.Invoices
    .IgnoreQueryFilters()
    .Where(i => i.Id == otherTenantInvoiceId)
    .ExecuteUpdateAsync(
        setters => setters.SetProperty(i => i.Status, "Cancelled"),
        cancellationToken);
// affected == 0
```

过滤条件确实没了，语句也确实发出去了，但那行属于别的租户，策略把可更新的行集合收窄到空，`affected` 为 0。

手动附加一个跨租户的实体同样失败。EF Core 按主键拼出 `UPDATE invoices SET ... WHERE id = @p0`，策略再叠上自己的谓词，匹配到 0 行。EF 把「预期影响 1 行、实际 0 行」报成 `DbUpdateConcurrencyException`。这个异常很容易被误读成乐观并发的正常竞争，实际含义是这行数据对本会话根本不存在。

跨租户插入则由 `WITH CHECK` 在数据库层拒绝，lab 里拿到的是：

```text
INSERT: 42501 new row violates row-level security policy for table "invoices"
```

42501 是 `insufficient_privilege`，对应行级安全策略违规。它在事务里抛出，EF 包装成 `DbUpdateException`，内层是 `PostgresException`。

必须说清楚策略做不到的事：它不判断哪个租户是对的。如果应用解析错了租户（比如从可伪造的请求头里取，或者缓存串了请求），策略会一丝不苟地按错误的租户执行。RLS 是防「忘记加条件」的，不是防「条件算错」的。

## 策略对执行计划做了什么

策略表达式会被加进每条语句，所以值得确认它不是白拿的。场景 8 里，一条不带显式租户条件的查询和一条手写 `WHERE tenant_id = '...'` 的查询拿到了同样的索引和同样的缓冲区：

| 查询（100 万行表，租户 1）             | 计划要点                                 | 共享缓冲区 | 执行时间 |
| -------------------------------------- | ---------------------------------------- | ---------- | -------- |
| `ORDER BY created_at DESC LIMIT 20`    | 走 `(tenant_id, created_at DESC)` 索引   | 23         | 0.029 ms |
| 同上，另加显式 `WHERE tenant_id = ...` | 同一个索引                               | 23         | 0.024 ms |
| `WHERE number LIKE 'INV-00000%'`       | 按 `tenant_id` 位图扫描 2 万行后逐行过滤 | 11,748     | 5.768 ms |
| 同上，关掉 RLS 并显式带 `tenant_id`    | 两个索引 `BitmapAnd`                     | 109        | 0.657 ms |

等值条件上策略几乎零成本：它就是一个普通谓词，能进 `Index Cond`。真正的坑在第三行。`LIKE` 在这里退化成了「先按租户取出 2 万行，再逐行比对前缀」，扫掉 19,991 行才留下 9 行。

原因在 [CREATE POLICY 文档](https://www.postgresql.org/docs/18/sql-createpolicy.html)里：系统一般会让策略条件先于用户查询里的条件求值，以免把受保护的数据暴露给不可信的函数；只有被标记为 `LEAKPROOF` 的函数和操作符可以提前求值。lab 把两个函数的标记打了出来：

```text
starts_with leakproof=true, textlike leakproof=false
```

`LIKE` 背后的 `textlike` 不是 leakproof，所以它不能下推到策略条件之前，两个索引也就没法用 `BitmapAnd` 合并。加一个 `(tenant_id, number text_pattern_ops)` 复合索引救不了——场景 10 里计划完全没变，还是 11,748 个缓冲区、5.502 ms。换成前缀操作符 `^@`（背后是 leakproof 的 `starts_with`）之后，两个条件都进了 `Index Cond`，缓冲区降到 8，执行时间 0.021 ms。

麻烦的是 EF Core 会把 `StartsWith` 翻译成 `LIKE`：

```sql
WHERE i.tenant_id = @ef_filter__TenantId AND i.number LIKE 'INV-00000%'
```

也就是说，这类前缀查询不会自动吃到 leakproof 带来的优化。如果租户表上确实有高频的前缀搜索，要么在仓储里用原生 SQL 写 `^@`，要么接受「先扫本租户再过滤」的代价——后者在有 `tenant_id` 索引的前提下，成本随单租户数据量增长，而不是随全表增长。

## FORCE 之后要给运维留出口

`FORCE` 让 owner 也受策略约束，这保护了数据，也意味着所有「本该看到全部数据」的任务都需要显式的出口。lab 的场景 11 把这几件事全试了一遍：

| 操作                                                    | 结果                                                         |
| ------------------------------------------------------- | ------------------------------------------------------------ |
| `SET row_security = off` 后查询（`pg_dump` 的默认行为） | `42501 query would be affected by row-level security policy` |
| 迁移脚本里的回填，没有设置租户                          | 0 行受影响                                                   |
| `COPY FROM`（Npgsql 二进制导入）                        | `0A000 COPY FROM not supported with row-level security`      |
| `COPY TO` 在策略生效时导出                              | 100 万行里导出 0 行                                          |

第一行是设计如此，不是缺陷。[`row_security` 配置项](https://www.postgresql.org/docs/18/runtime-config-client.html)设为 `off` 时，会被策略过滤的查询直接报错；[`pg_dump` 默认就这么设](https://www.postgresql.org/docs/18/app-pgdump.html)，目的是宁可失败也不要静默导出残缺的数据。

第二行才是真正危险的：回填脚本连上库、执行 `UPDATE`、报告成功，实际改了 0 行，因为它没有设置租户，策略让它什么都看不到。这类错误不会抛异常，只会安静地不做任何事。

第三行是硬限制：官方文档明确写着 `COPY FROM` 目前不支持带行级安全的表，要改用等价的 `INSERT`。同一个页面上还有一条相关的：`COPY TO` 会应用 `SELECT` 策略，所以用受策略约束的角色做逻辑备份，导出的是空表。

结论是备份、跨租户报表和数据修复任务需要一个带 `BYPASSRLS` 的专用角色，只在这些任务里使用，并且这个角色的凭据不进应用进程。原文也把这一点列为策略的固有代价。

## 落地清单

- 应用连接用非 owner、非超级用户、无 `BYPASSRLS` 的角色，只授予它需要的 DML 权限。
- 表归 `app_owner` 所有，迁移用这个角色跑，`DROP POLICY` 和 `ALTER TABLE ... NO FORCE` 不留给应用。
- 表上同时 `ENABLE` 和 `FORCE ROW LEVEL SECURITY`。
- 策略的 `USING` 与 `WITH CHECK` 都写，并用 `NULLIF(..., '')` 让「没有租户」匹配不到任何行。
- 租户在每次连接打开时通过 `DbConnectionInterceptor` 用 `set_config` 设置，值走参数绑定。
- 用 `AddDbContext`，不用 `AddDbContextPool`；`TenantContext` 保持 scoped。
- 不要用 `No Reset On Close=true` 去省那次往返。
- 保留 EF 的全局查询过滤器：它把租户写进 SQL，意图在代码里可见，执行计划更简单，运行时零成本。RLS 是可绕过的代码路径下面的兜底，不是替代品。
- 给备份、跨租户任务留一个 `BYPASSRLS` 角色，并限制它的使用范围。
- 加两条集成测试：没有租户时任何查询返回 0 行；带 A 租户写 B 租户的行返回 `42501` 或 `DbUpdateConcurrencyException`。
- 如果链路上有 PgBouncer 事务池，把租户改成在显式事务内 `set_config(..., true)`。
- 有前缀搜索的表，评估 `LIKE` 在策略下的计划退化，必要时改用 `^@`。

要不要上这套取决于两个前提：租户隔离目前只靠「代码里记得写谓词」，以及你已经有独立的迁移角色，能把表所有权和应用连接分开。两条都成立时，一条策略的收益远大于成本——它把「有人忘了」从一次跨租户泄漏变成一次返回 0 行的查询。两条都不成立时，先把角色拆开再谈策略，否则 `FORCE` 只会先给你带来一个会失败的 `pg_dump`。

多租户隔离只是「把规则下沉到更稳的一层」的一个例子。Aide Hub 会继续整理这类约束落在数据库、工具链和 CI 里的做法，以及 .NET 与软件工程实践中更细的取舍。如果你在自己的项目里遇到过租户设置在连接池里丢失，或者备份导出空表的情况，欢迎把当时的排查过程发来交流。

## 参考

- [Let Postgres Enforce Tenant Isolation](https://milanjovanovic.tech/blog/postgres-row-level-security-with-ef-core)（原文，Milan Jovanović）
- [Postgres row-level security lab](https://milanjovanovic.tech/labs/postgres-row-level-security)（原文配套 lab，含 12 个场景与实测输出）
- [PostgreSQL 18：Row Security Policies](https://www.postgresql.org/docs/18/ddl-rowsecurity.html)
- [PostgreSQL 18：CREATE POLICY](https://www.postgresql.org/docs/18/sql-createpolicy.html)
- [PostgreSQL 18：COPY](https://www.postgresql.org/docs/18/sql-copy.html)
- [PostgreSQL 18：System Administration Functions（set_config）](https://www.postgresql.org/docs/18/functions-admin.html)
- [PostgreSQL 18：pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)
- [Npgsql：Pooled Connection Reset](https://www.npgsql.org/doc/performance.html#pooled-connection-reset)
- [EF Core：Interceptors](https://learn.microsoft.com/en-us/ef/core/logging-events-diagnostics/interceptors)
- [PgBouncer：Features](https://www.pgbouncer.org/features.html)
