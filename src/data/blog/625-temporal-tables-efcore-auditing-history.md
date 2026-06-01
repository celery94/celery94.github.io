---
pubDatetime: 2026-06-02T09:40:00+08:00
title: "SQL Server 时态表 + EF Core：零侵入式数据变更审计"
description: "介绍如何借助 SQL Server 系统版本时态表与 EF Core 6+ 的 IsTemporal() API，为业务实体建立完整的行级别历史追踪，覆盖配置、迁移、5 种历史查询运算符、生产环境注意事项与常见坑点。"
tags: ["EF Core", ".NET", "SQL Server", "数据审计", "Entity Framework"]
slug: "temporal-tables-efcore-auditing-history"
ogImage: "../../assets/625/01-cover.png"
source: "https://thecodeman.net/posts/temporal-tables-efcore-auditing-history"
---

审计需求几乎在每个业务系统里都会出现：订单地址是什么时候改的？合同金额被谁修改过？用户资料在某次投诉前是什么状态？

常见的做法是在表里加 `CreatedAt`、`UpdatedAt`、`ModifiedBy` 三列，或者自己维护一张审计日志表。前者只记录最后一次变更，历史全丢；后者需要所有写操作都记得往日志表写一笔，一旦漏掉就是不完整的审计链。

SQL Server 的时态表（Temporal Tables）把这件事交给数据库引擎处理。EF Core 6+ 通过 `IsTemporal()` 暴露了完整的配置和查询 API。本文用一个电商订单场景，从头走完配置、迁移、查询和注意事项。

## 时态表的工作原理

SQL Server 2016 引入了**系统版本时态表**（System-Versioned Temporal Tables），这是 SQL:2011 标准的实现。它的核心机制是：

- 主表保存每行的**当前状态**
- 历史表保存每行的**全部历史版本**，每个版本附带两个 `datetime2` 字段 `ValidFrom` / `ValidTo`，记录该版本生效的 UTC 时间范围
- 这两个字段完全由 SQL Server 写入，应用代码无法覆盖

```text
┌──────────────────────────────────────────────────────────┐
│                      Orders（主表）                        │
│  Id │ CustomerId │ ShippingAddress   │ ValidFrom │ ValidTo│
│─────┼────────────┼───────────────────┼───────────┼────────│
│  1  │    42      │ "123 Main St"     │ 2026-05-25│ 9999.. │  ← 当前
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                   OrdersHistory（历史表）                  │
│  Id │ CustomerId │ ShippingAddress   │ ValidFrom │ ValidTo│
│─────┼────────────┼───────────────────┼───────────┼────────│
│  1  │    42      │ "456 Oak Ave"     │ 2026-05-20│ 2026-05-25│ ← 旧版本
│  1  │    42      │ "789 Pine Rd"     │ 2026-05-15│ 2026-05-20│ ← 更旧
└──────────────────────────────────────────────────────────┘
```

三个操作的内部行为：

- **INSERT**：新行写入主表，`ValidFrom` = 当前事务时间，`ValidTo` = `9999-12-31 23:59:59`
- **UPDATE**：旧版本原子移入历史表（`ValidTo` = 当前时间），主表更新（`ValidFrom` = 当前时间）
- **DELETE**：当前行原子移入历史表，主表删除

时间戳强制使用 UTC，不受应用层控制，这也让审计记录具备一定的防篡改性。

## 前置条件

- .NET 6 或更高版本
- EF Core 6 或更高版本（`Microsoft.EntityFrameworkCore.SqlServer`）
- SQL Server 2016+ 或 Azure SQL Database

## 第一步：定义实体

实体本身**不需要**加任何审计字段，这是时态表相比手写审计的最大优势之一：

```csharp
// Models/Order.cs
public class Order
{
    public int Id { get; set; }
    public int CustomerId { get; set; }
    public string ShippingAddress { get; set; } = string.Empty;
    public string Status { get; set; } = "Pending";
    public decimal TotalAmount { get; set; }
    public DateTime CreatedAt { get; set; }

    public Customer Customer { get; set; } = null!;
    public ICollection<OrderItem> Items { get; set; } = new List<OrderItem>();
}

// Models/OrderItem.cs
public class OrderItem
{
    public int Id { get; set; }
    public int OrderId { get; set; }
    public string ProductName { get; set; } = string.Empty;
    public int Quantity { get; set; }
    public decimal UnitPrice { get; set; }

    public Order Order { get; set; } = null!;
}
```

没有 `ValidFrom`、`ValidTo`，也没有 `ModifiedBy`——时态基础设施是数据层的事，不需要泄漏到领域模型里。

## 第二步：在 DbContext 里配置时态表

```csharp
// Data/AppDbContext.cs
public class AppDbContext : DbContext
{
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<OrderItem> OrderItems => Set<OrderItem>();
    public DbSet<Customer> Customers => Set<Customer>();

    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Order>(entity =>
        {
            entity.ToTable("Orders", t => t.IsTemporal(temporal =>
            {
                temporal.HasPeriodStart("ValidFrom");
                temporal.HasPeriodEnd("ValidTo");
                temporal.UseHistoryTable("OrdersHistory", "audit");
            }));

            entity.Property(o => o.TotalAmount).HasColumnType("decimal(18,2)");
            entity.Property(o => o.Status).HasMaxLength(50);
        });

        modelBuilder.Entity<OrderItem>(entity =>
        {
            entity.ToTable("OrderItems", t => t.IsTemporal(temporal =>
            {
                temporal.HasPeriodStart("ValidFrom");
                temporal.HasPeriodEnd("ValidTo");
                temporal.UseHistoryTable("OrderItemsHistory", "audit");
            }));

            entity.Property(i => i.UnitPrice).HasColumnType("decimal(18,2)");
        });
    }
}
```

几个有意的选择：

- 历史表放在独立的 `audit` schema，方便权限管理（比如只允许 DBA 读取 `audit.*`）
- 显式命名 `ValidFrom` / `ValidTo`，如果团队更喜欢 `PeriodStart` / `PeriodEnd` 也可以
- `Order` 和 `OrderItem` 都启用时态，这样做点时间恢复时才能拿到完整快照

## 第三步：创建并应用迁移

```bash
dotnet ef migrations add AddTemporalTables --output-dir Data/Migrations
dotnet ef database update
```

生成的迁移里，EF Core 会给表加 `SqlServer:IsTemporal`、`SqlServer:TemporalHistoryTableName` 等注解。对应的 SQL 大致是：

```sql
CREATE TABLE [Orders] (
    [Id]              INT           NOT NULL IDENTITY,
    [CustomerId]      INT           NOT NULL,
    [ShippingAddress] NVARCHAR(MAX) NOT NULL,
    [Status]          NVARCHAR(50)  NOT NULL,
    [TotalAmount]     DECIMAL(18,2) NOT NULL,
    [CreatedAt]       DATETIME2     NOT NULL,
    [ValidFrom]       DATETIME2 GENERATED ALWAYS AS ROW START NOT NULL,
    [ValidTo]         DATETIME2 GENERATED ALWAYS AS ROW END   NOT NULL,
    PERIOD FOR SYSTEM_TIME ([ValidFrom], [ValidTo]),
    CONSTRAINT [PK_Orders] PRIMARY KEY ([Id])
)
WITH (SYSTEM_VERSIONING = ON (
    HISTORY_TABLE = [audit].[OrdersHistory]
));
```

## 写操作无需任何改动

标准的 EF Core 写操作会自动触发历史追踪：

```csharp
// 创建订单——SQL Server 自动设置 ValidFrom = UTC_NOW, ValidTo = 9999-12-31
public async Task<Order> PlaceOrderAsync(int customerId, CreateOrderDto dto)
{
    var order = new Order
    {
        CustomerId = customerId,
        ShippingAddress = dto.ShippingAddress,
        Status = "Pending",
        TotalAmount = dto.Items.Sum(i => i.Quantity * i.UnitPrice),
        CreatedAt = DateTime.UtcNow,
        Items = dto.Items.Select(i => new OrderItem
        {
            ProductName = i.ProductName,
            Quantity = i.Quantity,
            UnitPrice = i.UnitPrice
        }).ToList()
    };

    _db.Orders.Add(order);
    await _db.SaveChangesAsync();
    return order;
}

// 更新地址——SQL Server 自动把旧行移入历史表，ValidTo = 变更时间
public async Task UpdateShippingAddressAsync(int orderId, string newAddress)
{
    var order = await _db.Orders.FindAsync(orderId)
        ?? throw new OrderNotFoundException(orderId);

    order.ShippingAddress = newAddress;
    await _db.SaveChangesAsync();
    // 不需要任何额外代码，历史记录已经写入
}
```

## 5 种历史查询运算符

这里是时态表真正发挥价值的地方。EF Core 7+ 提供了 5 个时态查询运算符：

### TemporalAll() — 完整变更历史

查看某张订单的所有历史版本，构建审计时间线：

```csharp
public async Task<IEnumerable<OrderAuditEntry>> GetOrderHistoryAsync(int orderId)
{
    return await _db.Orders
        .TemporalAll()
        .Where(o => o.Id == orderId)
        .OrderBy(o => EF.Property<DateTime>(o, "ValidFrom"))
        .Select(o => new OrderAuditEntry
        {
            ShippingAddress = o.ShippingAddress,
            Status = o.Status,
            TotalAmount = o.TotalAmount,
            ValidFrom = EF.Property<DateTime>(o, "ValidFrom"),
            ValidTo = EF.Property<DateTime>(o, "ValidTo")
        })
        .ToListAsync();
}
```

查询结果示例：

```text
ValidFrom            ValidTo              Status     ShippingAddress
───────────────────────────────────────────────────────────────────
2026-05-15 09:00:00  2026-05-20 14:32:11  Pending    "789 Pine Rd"
2026-05-20 14:32:11  2026-05-25 08:17:44  Processing "456 Oak Ave"
2026-05-25 08:17:44  9999-12-31 23:59:59  Shipped    "123 Main St"  ← 当前
```

地址是什么时候改的、改成什么——一目了然。

### TemporalAsOf() — 时间点快照

重建订单在某个时刻的完整状态，包括关联的订单项：

```csharp
public async Task<OrderSnapshot?> GetOrderSnapshotAsync(int orderId, DateTime asOf)
{
    // 注意：asOf 必须是 UTC
    var order = await _db.Orders
        .TemporalAsOf(asOf)
        .Include(o => o.Items)  // EF Core 会把时态过滤同步应用到 Include
        .FirstOrDefaultAsync(o => o.Id == orderId);

    if (order is null) return null;

    return new OrderSnapshot
    {
        OrderId = orderId,
        AsOf = asOf,
        ShippingAddress = order.ShippingAddress,
        Status = order.Status,
        Items = order.Items.Select(i => new OrderItemSnapshot
        {
            ProductName = i.ProductName,
            Quantity = i.Quantity,
            UnitPrice = i.UnitPrice
        }).ToList()
    };
}
```

关键点：使用 `TemporalAsOf()` 配合 `Include()` 时，EF Core 会把时间过滤同时应用到关联实体，拿到的 `OrderItems` 是那个时间点实际存在的版本，不是当前版本。

### TemporalBetween() — 时间窗口内的变更

查找在某个时间窗口内被修改的订单（例如排查某个批处理任务在凌晨 3 点的异常操作）：

```csharp
// TemporalBetween：ValidFrom >= start AND ValidFrom < end
var changedDuringWindow = await _db.Orders
    .TemporalBetween(
        new DateTime(2026, 5, 20, 3, 0, 0, DateTimeKind.Utc),
        new DateTime(2026, 5, 20, 4, 0, 0, DateTimeKind.Utc))
    .Select(o => new
    {
        o.Id,
        o.Status,
        ValidFrom = EF.Property<DateTime>(o, "ValidFrom")
    })
    .ToListAsync();
```

### TemporalFromTo() — 某时段内活跃的版本

与 `TemporalBetween` 的区别：`TemporalFromTo` 返回在指定范围内**存在过**（活跃过）的行，包括在范围开始前就已存在的版本：

```csharp
// TemporalFromTo：ValidFrom < end AND ValidTo > start
// 即"在这个窗口内任意时刻有效的行"
var ordersActiveLastWeek = await _db.Orders
    .TemporalFromTo(DateTime.UtcNow.AddDays(-7), DateTime.UtcNow)
    .Where(o => o.Status == "Processing")
    .ToListAsync();
```

### TemporalContainedIn() — 完全在范围内的短暂版本

只返回在指定范围内**创建且删除**的行，适合找生命周期极短的记录：

```csharp
// TemporalContainedIn：ValidFrom >= start AND ValidTo <= end
var shortLivedStatuses = await _db.Orders
    .TemporalContainedIn(
        DateTime.UtcNow.AddHours(-1),
        DateTime.UtcNow)
    .ToListAsync();
```

### 5 种运算符对比

| 运算符 | 返回条件 | 典型用途 |
|---|---|---|
| `TemporalAll()` | 所有版本 | 完整审计日志 |
| `TemporalAsOf(t)` | `ValidFrom <= t < ValidTo` | 时间点状态恢复 |
| `TemporalBetween(s, e)` | `ValidFrom >= s AND ValidFrom < e` | 查哪些行在窗口内发生了变更 |
| `TemporalFromTo(s, e)` | `ValidFrom < e AND ValidTo > s` | 查哪些行在窗口内活跃过 |
| `TemporalContainedIn(s, e)` | `ValidFrom >= s AND ValidTo <= e` | 查在窗口内创建又消失的行 |

## 生产环境迁移注意事项

对**已有生产表**启用时态比新建表要复杂一些。

**方案 A：让 EF Core 生成迁移（适合小表）**

```bash
dotnet ef migrations add EnableTemporalOnOrders
```

生成的迁移是 `AlterTable`，对大表可能导致锁表和长时间等待。

**方案 B：手写原始 SQL（适合大表）**

```csharp
public partial class EnableTemporalOnOrders : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        // 先加 period 列（已有数据的表不能直接加 NOT NULL 列，加 DEFAULT 解决）
        migrationBuilder.Sql(@"
            ALTER TABLE [Orders]
            ADD [ValidFrom] DATETIME2 GENERATED ALWAYS AS ROW START HIDDEN
                CONSTRAINT DF_Orders_ValidFrom DEFAULT '2000-01-01 00:00:00.0000000',
                [ValidTo] DATETIME2 GENERATED ALWAYS AS ROW END HIDDEN
                CONSTRAINT DF_Orders_ValidTo DEFAULT '9999-12-31 23:59:59.9999999',
                PERIOD FOR SYSTEM_TIME ([ValidFrom], [ValidTo]);
        ");

        // 再开启系统版本
        migrationBuilder.Sql(@"
            ALTER TABLE [Orders]
            SET (SYSTEM_VERSIONING = ON (
                HISTORY_TABLE = [audit].[OrdersHistory],
                DATA_CONSISTENCY_CHECK = ON
            ));
        ");
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.Sql(@"
            ALTER TABLE [Orders] SET (SYSTEM_VERSIONING = OFF);
            ALTER TABLE [Orders] DROP PERIOD FOR SYSTEM_TIME;
            ALTER TABLE [Orders] DROP COLUMN [ValidFrom];
            ALTER TABLE [Orders] DROP COLUMN [ValidTo];
            DROP TABLE IF EXISTS [audit].[OrdersHistory];
        ");
    }
}
```

注意：`Down` 迁移里删除了所有历史数据。生产环境通常应该只关闭系统版本，保留历史表数据。

## 性能影响

时态表不是零成本，开启前需要评估：

**写入开销**：每次 `UPDATE` 或 `DELETE` 都需要额外写一行到历史表。在典型 OLTP 场景下，开销约为 **5–15%**。对写入吞吐量极高的表（实时遥测、会话状态、事件日志）影响可能更大，需要实测。

**历史表增长**：随着时间推移，历史表会持续增长。管理策略：
- 对旧数据归档（INSERT 旧行到归档表，然后关闭系统版本、删除历史、重新开启）
- 给历史表加非聚集索引加速点时间查询：

```sql
CREATE NONCLUSTERED INDEX IX_OrdersHistory_IdValidFrom
ON [audit].[OrdersHistory] ([Id], [ValidFrom] DESC);
```

**读取性能**：`TemporalAll()` 和 `TemporalBetween()` 会扫描历史表，对大历史表要配合合适的过滤条件和索引使用。

## 5 个常见坑点

**坑 1：反向工程（Scaffold）可能不识别时态配置**

`dotnet ef dbcontext scaffold` 对已有时态表可能无法自动推断 `IsTemporal()` 配置，需要手动补充。

**坑 2：软删除与时态表叠加**

如果实体有软删除（`IsDeleted` 标志），时态表会忠实记录每次 `IsDeleted` 从 `false` 改为 `true` 的变化。两种机制叠加后查询历史时需要额外处理，考虑是否真的需要同时用两者。

**坑 3：批量操作仍然被时态追踪**

直接调用 `ExecuteSqlRawAsync` 的原生 SQL 操作会绕过 EF Core 变更追踪，但**不会**绕过时态表——时态追踪是引擎级别的，不经过 EF Core。

**坑 4：不能直接修改历史表结构**

给时态表加新列时，EF Core 会同步给历史表加列。如果你曾经手动修改过历史表，迁移会失败。规则很简单：**永远不要直接修改历史表**。

**坑 5：时间必须用 UTC**

时态表的时间戳全部是 UTC。如果查询时传入了本地时间，会得到错误的历史版本：

```csharp
// ❌ 错误：本地时间
var asOf = DateTime.Now.AddDays(-1);

// ✅ 正确：UTC
var asOf = DateTime.UtcNow.AddDays(-1);
```

## 不适合用时态表的场景

- **高频写入表**（实时遥测、事件日志）：写入开销和历史表膨胀会成问题，考虑时序数据库或事件存储
- **包含 PII / GDPR 数据**：时态表让"被遗忘权"实现起来更复杂，每次都需要关闭系统版本、清除历史、再重新开启
- **包含大型 BLOB 或 NVARCHAR(MAX) 列**：每次更新都会复制整行到历史表，大字段会让历史表快速膨胀
- **跨库事务一致性要求**：时态时间戳是每个数据库独立的，跨库时间点重建不可靠

---

时态表解决的是一个很具体的问题：用最少的代码，得到最完整、最难被绕过的数据历史。它不是万能的——上面的"不适用场景"列表值得认真对待——但对于订单、合同、用户资料这类读多写少、合规要求高的业务实体，`IsTemporal()` 是目前在 SQL Server 生态里成本最低的审计方案。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [原文：Temporal Tables with Entity Framework Core: Complete Guide to Auditing Data Changes](https://thecodeman.net/posts/temporal-tables-efcore-auditing-history)
- [EF Core 文档：时态表](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-6.0/whatsnew#sql-server-temporal-tables)
- [SQL Server 文档：时态表](https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal-tables)
