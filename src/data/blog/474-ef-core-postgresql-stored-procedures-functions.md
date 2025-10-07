---
pubDatetime: 2025-10-07
title: 在 EF Core 与 PostgreSQL 中使用存储过程和函数
description: 深入探讨如何在 Entity Framework Core 与 PostgreSQL 环境中高效使用存储过程和函数，包括标量函数、表值函数和复杂存储过程的实现，以及何时选择原生 SQL 而非 LINQ 查询的最佳实践。
tags: ["EF Core", ".NET", "PostgreSQL", "Database", "Performance"]
slug: ef-core-postgresql-stored-procedures-functions
source: https://www.milanjovanovic.tech/blog/using-stored-procedures-and-functions-with-ef-core-and-postgresql
---

在使用 Entity Framework Core 开发 .NET 应用时，大多数场景下 LINQ 查询都能满足需求。但当面对复杂的聚合查询、数据库特有功能或需要原子操作时，直接使用数据库的存储过程和函数往往是更明智的选择。本文将详细讲解如何在 EF Core 与 PostgreSQL 环境中有效使用这些数据库对象，并探讨其适用场景与最佳实践。

## 何时应该使用原生 SQL

虽然 LINQ 提供了类型安全和重构支持，但在某些场景下，直接编写 SQL 会是更好的选择：

**性能优化需求**：当面对包含多表连接、窗口函数或复杂聚合的报表查询时，手写 SQL 往往能获得更好的性能表现。你可以在数据库工具中直接测试和优化查询语句，然后再集成到代码中。

**数据库特定功能**：PostgreSQL 提供了许多强大的特性，如全文搜索、JSON 操作符和公共表表达式（CTE），这些功能在 LINQ 中并不总有对等的表达方式。此时直接使用 SQL 是最直接的路径。

**遗留系统集成**：如果数据库中已存在存储过程和函数（可能来自遗留系统），直接调用它们比用 C# 重写整个逻辑更加合理。

**原子操作与锁控制**：需要使用 `FOR UPDATE` 锁来协调多个更新操作时，在存储过程中实现比在应用层管理更简单也更安全。

**减少网络往返**：一个函数调用能从五个表中聚合数据，这比执行五次独立的 LINQ 查询要高效得多。

## PostgreSQL 函数与存储过程的区别

PostgreSQL 对函数（Function）和存储过程（Procedure）有明确的区分，理解这种区别对于合理设计数据库逻辑至关重要。

**函数**设计用于返回值。它们可以返回标量值、表或复杂的 JSON 对象。你使用 `SELECT` 语句调用函数，并且可以像使用其他表达式一样在查询中使用它们。函数在事务内运行，可以用在 `WHERE` 子句、连接和其他查询上下文中。

**存储过程**设计用于产生副作用。它们不直接返回值，但可以通过 `OUT` 参数修改数据。你使用 `CALL` 语句调用存储过程，它们特别适合需要显式管理事务或执行多个相关更新的复杂操作。

简单来说：需要查询数据时使用函数，需要修改数据或执行复杂逻辑时使用存储过程。

这种区分会影响你如何设计数据库逻辑以及如何在 C# 中调用这些数据库对象。

## 实战示例：标量函数

让我们从一个简单的标量函数开始。下面的函数返回指定票种的剩余数量：

```sql
CREATE OR REPLACE FUNCTION ticketing.tickets_left(p_ticket_type_id uuid)
RETURNS numeric
LANGUAGE sql
AS $$
  SELECT tt.available_quantity
  FROM ticketing.ticket_types tt
  WHERE tt.id = p_ticket_type_id
$$;
```

这个函数非常简单，只是将一个查询封装在函数中。

在 EF Core 中调用这个函数同样直接：

```csharp
app.MapGet("ticket-types/{ticketTypeId}/available-quantity",
async (Guid ticketTypeId, EventManagementContext dbContext) =>
{
    var result = await dbContext.Database.SqlQuery<int>(
            $"""
             SELECT ticketing.tickets_left({ticketTypeId}) AS "Value"
             """)
        .FirstAsync();

    return Results.Ok(result);
});
```

注意这里的 `AS "Value"` 别名。当 EF Core 映射到基元类型时，它期望有一个名为 `Value` 的属性。引号保留了精确的大小写（PostgreSQL 默认会将未加引号的标识符转换为小写）。

插值字符串语法（`$"{ticketTypeId}"`）看起来可能有安全风险，但实际上 EF Core 会自动将其转换为参数化查询。你并不是在拼接 SQL 字符串，而是使用 C# 插值作为参数的便捷语法。

## 实战示例：表值函数

函数可以返回完整的结果集，这正是它们真正强大的地方。下面的函数返回客户的订单汇总信息：

```sql
CREATE OR REPLACE FUNCTION ticketing.customer_order_summary(p_customer_id uuid)
RETURNS TABLE (
    order_id uuid,
    created_at_utc timestamptz,
    total_price numeric,
    currency text,
    item_count numeric
)
LANGUAGE sql
AS $$
SELECT
    o.id,
    o.created_at_utc,
    o.total_price,
    o.currency,
    COALESCE(SUM(oi.quantity), 0) AS item_count
FROM ticketing.orders o
LEFT JOIN ticketing.order_items oi ON oi.order_id = o.id
WHERE o.customer_id = p_customer_id
GROUP BY o.id, o.created_at_utc, o.total_price, o.currency
ORDER BY o.created_at_utc DESC
$$;
```

这个函数连接订单和订单项，聚合数量，并返回多行结果。虽然可以用 LINQ 编写，但 SQL 版本更清晰，而且可以直接在数据库工具中测试。

要在 C# 中使用它，首先创建一个与函数输出匹配的 DTO：

```csharp
public class OrderSummaryDto
{
    public Guid OrderId { get; set; }
    public DateTime CreatedAtUtc { get; set; }
    public decimal TotalPrice { get; set; }
    public string Currency { get; set; }
    public int ItemCount { get; set; }
}
```

然后像查询普通表一样查询该函数：

```csharp
app.MapGet("customers/{customerId}/order-summary",
async (Guid customerId, EventManagementContext dbContext) =>
{
    var orders = await dbContext.Database
        .SqlQuery<OrderSummaryDto>(
            $"""
             SELECT
                order_id AS OrderId,
                created_at_utc AS CreatedAtUtc,
                total_price AS TotalPrice,
                currency AS Currency,
                item_count AS ItemCount
             FROM ticketing.customer_order_summary({customerId})
             """)
        .ToListAsync();

    return Results.Ok(orders);
});
```

关键在于使用别名将列名映射到 DTO 属性。EF Core 会自动处理其余部分。

这是一个简单的无连接情况，但你也可以在更复杂的查询中使用这种模式。不过，你需要手动映射到 DTO，因为 EF Core 无法将原生 SQL 中的连接转换为实体图。通常情况下，函数会返回扁平结构，如有需要可以在 C# 中映射到更丰富的模型。

## 实战示例：带验证的存储过程

存储过程在处理复杂业务逻辑时真正展现其价值。假设需要调整票务库存，同时要防止竞态条件并验证操作：

```sql
CREATE OR REPLACE PROCEDURE ticketing.adjust_available_quantity(
    p_ticket_type_id uuid,
    p_delta numeric,
    p_reason text DEFAULT 'manual-adjust'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_qty numeric;
    v_avail numeric;
    v_new_avail numeric;
BEGIN
    SELECT quantity, available_quantity
    INTO v_qty, v_avail
    FROM ticketing.ticket_types
    WHERE id = p_ticket_type_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket_type % not found', p_ticket_type_id;
    END IF;

    v_new_avail := v_avail + p_delta;

    IF v_new_avail < 0 THEN
        RAISE EXCEPTION 'Cannot reduce below zero';
    END IF;

    IF v_new_avail > v_qty THEN
        RAISE EXCEPTION 'Cannot exceed quantity';
    END IF;

    UPDATE ticketing.ticket_types
    SET available_quantity = v_new_avail
    WHERE id = p_ticket_type_id;
END;
$$;
```

这个存储过程完成了几项重要工作：

- 使用 `FOR UPDATE` 锁定行，确保其他事务在操作完成前无法修改该行
- 在做出更改前验证业务规则
- 在出错时提供清晰的错误消息
- 将所有操作保持在单次数据库往返中

虽然可以在 C# 中通过手动管理事务和显式锁定来实现这些功能，但这样会更复杂且容易出错。让数据库处理它擅长的事情。

在 EF Core 中调用存储过程的方式如下：

```csharp
app.MapPut("ticket-types/{ticketTypeId}/available-quantity", async (
    Guid ticketTypeId,
    int quantity,
    EventManagementContext dbContext) =>
{
    try
    {
        await dbContext.Database.ExecuteSqlAsync(
            $"""
             CALL ticketing.adjust_available_quantity({ticketTypeId},{quantity})
             """);

        return Results.Ok();
    }
    catch (Exception e)
    {
        return Results.BadRequest(e.Message);
    }
});
```

存储过程本身不返回值，但如果它抛出异常（使用 `RAISE EXCEPTION`），PostgreSQL 会将异常传播到 C# 代码。你可以捕获异常并返回适当的错误响应。

## SQL 注入问题（无需恐慌）

看到这些插值字符串，你可能会想："这不是在等待 SQL 注入攻击吗？"

实际上不是。

当你编写以下代码时：

```csharp
$"SELECT * FROM users WHERE id = {userId}"
```

EF Core 并不会拼接字符串。它会将其转换为：

```sql
SELECT * FROM users WHERE id = @p0
```

实际值作为参数单独发送，完全独立于 SQL 文本。这适用于本文中的所有示例。

插值语法只是编写参数化查询的便捷方式。

原因在于我们传递给 `SqlQuery` 方法的不是 `string` 类型，而是 `FormattableString` 类型。这是一个特殊类型，它分别捕获格式和参数，允许 EF Core 处理参数化。

本文中的所有内容都适用于 SQL Server、MySQL、SQLite 和其他 EF Core 支持的数据库。主要区别在于语法差异。

## 数据库视图简介

数据库视图类似于不带参数的函数。它们是保存的查询，可以通过名称引用。

你可以像查询函数一样使用 `SqlQuery<T>` 查询视图：

```csharp
var results = await dbContext.Database
    .SqlQuery<ActiveCustomerDto>(
        $"SELECT * FROM ticketing.active_customers")
    .ToListAsync();
```

或者，你可以在 `DbContext` 中将视图映射到实体类型，以获得完整的 LINQ 支持。

视图适合频繁使用且不需要参数的查询。函数则提供了参数化的灵活性。

## 最佳实践总结

我们介绍了如何在 EF Core 中使用 PostgreSQL 函数和存储过程，从简单的标量函数到带验证和锁定的复杂存储过程。

你了解了何时使用函数（需要返回数据时）与何时使用存储过程（需要修改数据时）。你看到了 EF Core 的 `SqlQuery<T>` 和 `ExecuteSqlAsync` 如何在提供类型安全的同时让你编写所需的 SQL。你还学到了何时使用原生 SQL 更合理：复杂聚合、数据库特定功能、带锁定的原子操作以及减少网络往返。

EF Core 不会强迫你在 LINQ 和原生 SQL 之间做出选择。你可以同时使用两者。

当需要返回数据时使用函数，当需要用复杂逻辑修改数据时使用存储过程，当 LINQ 无法高效满足需求时使用原生 SQL 查询。结合 EF Core 的便利性和数据库的强大功能，你可以灵活地为每个场景选择合适的工具。

## 参考资料

- [Using Stored Procedures and Functions With EF Core and PostgreSQL - Milan Jovanović](https://www.milanjovanovic.tech/blog/using-stored-procedures-and-functions-with-ef-core-and-postgresql)
- [PostgreSQL Window Functions Documentation](https://www.postgresql.org/docs/current/tutorial-window.html)
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [Entity Framework Core Raw SQL Queries](https://learn.microsoft.com/en-us/ef/core/querying/sql-queries)
