---
pubDatetime: 2026-07-16T15:08:18+08:00
title: "分布式单体：每个 C# 开发者都应该识别的反模式"
description: "分布式单体看起来像微服务，实则共享数据库、需要协同部署、靠同步 HTTP 链耦合。本文拆解 5 个识别症状和 3 步修复方案，帮你判断是该解耦还是合并回模块化单体。"
tags: ["分布式单体", "C#", ".NET", "微服务", "架构反模式"]
slug: "distributed-monolith-csharp-antipattern"
ogImage: "../../assets/946/01-cover.png"
source: "https://www.devleader.ca/2026/07/12/distributed-monolith-the-antipattern-every-c-developer-should-recognize"
---

你以为自己在做微服务。独立的 Git 仓库、独立部署的服务、各自归属的团队。但一个服务挂了，半个系统跟着崩。每次发布要对照清单，确认哪些服务按什么顺序部署。排查一个生产事故得从五个地方的日志拼线索。恭喜——你实际上建了一个**分布式单体**，而且它大概率比你最开始那个单体更难搞。

这篇文章拆解什么是分布式单体、怎么在 .NET 代码里识别它、以及三招能落地的修复方案。无论你已经陷在里面还是想提前避开，这个反模式都值得认清。

## 什么是分布式单体

分布式单体是一个以多个独立进程运行的、但耦合紧到无法独立运作的系统。你把服务拆到了网络两侧，但它们共享数据库、要求同步部署、靠同步调用链串联，把分布式架构每一个好处都抵消了。

核心问题：你承受了分布式系统所有的复杂度——网络延迟、分布式追踪、重试策略、容器编排——却没拿到任何好处。传统单体至少简单：一次部署、一个数据库、一个日志文件。分布式单体逼你管理微服务的运维开销，同时还得受紧耦合制约。两头不讨好。

这个模式通常在团队还没定义好领域边界就拆服务时出现，或者在服务拆分后允许共享基础设施（比如同一个数据库）继续存在时形成。

## 识别分布式单体的 5 个症状

分布式单体反模式有欺骗性——架构图上看不出问题，几个独立的方框，中间画着箭头。但以下几个症状会暴露真相。

### 1. 多个服务共享同一个数据库

最明显的信号：多个服务指向同一个数据库 schema——或者共用同一个暴露所有领域表的 `DbContext`。当 Inventory 服务可以直接查 Customers 表时，你没有服务边界。你只有一个穿了微服务戏服的 monomer。一次 schema 迁移能让三个服务同时挂掉。

### 2. 部署需要协调编排

"我不能单独部署 Orders，得先把 Inventory 部署了。"如果你说过这句话，或者发布说明里带着部署顺序表，你就有部署耦合。设计得当的微服务架构里，每个服务独立部署，不影响其他服务。需要协调本身就是坏味道。

### 3. 同步 HTTP 调用链

Service A 同步调 Service B，B 再同步调 Service C，这就是分布式调用图。任何一个环节变慢或挂了，整条请求就失败。这比进程内方法调用更糟——因为失败路径上还多了网络超时、序列化开销和 DNS 查询。

### 4. 没有服务可以独立扩缩

微服务的承诺是促销期间只扩 checkout 服务，不动 notification 服务。如果因为紧密的运行时依赖，扩一个就必须扩好几个，这个承诺就破产了。你在付微服务基础设施的成本，却拿不到弹性收益。

### 5. 每个需求改 3 个以上的仓库

一个产品需求需要跨多个仓库协同修改，而且必须一起合并、一起部署——这是代码层面的分布式单体信号。服务不是真正独立的，它们只是物理上分开的代码库，耦合是隐形的。

## 分布式单体的真实代价

传统单体有一个真正的负担：难以随时间扩展和演进。但它的运维简单。

分布式单体同时继承了两种成本。

你照常为服务发现、容器编排、分布式追踪、健康检查、重试逻辑买单——所有把系统分散到网络上的运维开销。但你还承受着单体的紧耦合。共享数据库的一次 schema 变更能同时炸掉多个服务。下游服务重启会级联成调用方的客户侧报错。

排查尤其痛苦。追踪一个失败请求，你要跨多个服务关联日志、匹配 correlation ID、搞清楚每个服务当时跑的是哪个版本。在单体里这只是一个堆栈跟踪的事。

## 在代码里看分布式单体

以下例子来自一个故意同时展示反模式和修正方案的示例项目。

### 共享 DbContext 反模式

这是 `Shared.DataAccess` 项目中的 `AppDbContext`。Orders、Inventory、Customers 每个服务都依赖这同一个类：

```csharp
using Microsoft.EntityFrameworkCore;
using Shared.DataAccess.Entities;

namespace Shared.DataAccess;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options)
        : base(options) { }

    // 反模式：单一 DbContext 暴露所有领域的实体
    // 每个服务都能直接访问任何表，边界不存在
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<InventoryItem> Inventory => Set<InventoryItem>();
    public DbSet<Customer> Customers => Set<Customer>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Order>(entity =>
        {
            entity.HasKey(e => e.OrderId);
            entity.Property(e => e.CreatedAt)
                .HasDefaultValueSql("datetime('now')");
        });

        modelBuilder.Entity<InventoryItem>(entity =>
        {
            entity.HasKey(e => e.ProductId);
            entity.Property(e => e.ProductName)
                .IsRequired().HasMaxLength(200);
        });

        modelBuilder.Entity<Customer>(entity =>
        {
            entity.HasKey(e => e.CustomerId);
            entity.Property(e => e.Name)
                .IsRequired().HasMaxLength(100);
            entity.Property(e => e.Email)
                .IsRequired().HasMaxLength(200);
        });
    }
}
```

引用 `Shared.DataAccess` 的每个服务都能读写每一张表。Orders 服务能查 Customers，Inventory 服务能改 Orders。数据层没有领域边界的约束。这是分布式单体最赤裸的形态——一个碰巧跑在不同进程里的单体。

### 同步 HTTP 调用反模式

看 `Orders.API` 怎么处理一个下单请求。注意它依赖了多少东西：

```csharp
app.MapPost("/orders", async (
    CreateOrderRequest request,
    AppDbContext db,
    IHttpClientFactory httpClientFactory) =>
{
    // 反模式：Orders 通过共享 DbContext 直接查 Inventory 表
    var inventoryItem = await db.Inventory
        .FindAsync(request.ProductId);

    if (inventoryItem == null)
        return Results.BadRequest(
            new { message = "产品在库存中不存在" });

    if (inventoryItem.Stock < request.Quantity)
        return Results.BadRequest(
            new { message = "库存不足" });

    // 反模式：同步 HTTP 调用 Inventory.API
    // 如果 Inventory.API 不可用，所有下单请求立即失败
    var httpClient = httpClientFactory
        .CreateClient("InventoryAPI");
    var response = await httpClient.PostAsJsonAsync(
        $"/inventory/reserve?productId={request.ProductId}" +
        $"&quantity={request.Quantity}", new { });

    if (!response.IsSuccessStatusCode)
        return Results.BadRequest(
            new { message = "库存预留失败" });

    var order = new Order
    {
        ProductId = request.ProductId,
        Quantity = request.Quantity,
        CustomerId = request.CustomerId,
        CreatedAt = DateTime.UtcNow
    };

    db.Orders.Add(order);
    await db.SaveChangesAsync();

    return Results.Created(
        $"/orders/{order.OrderId}", new
    {
        orderId = order.OrderId,
        message = "订单创建成功"
    });
});
```

这里叠了三个反模式。第一，Orders 服务通过共享 `AppDbContext` 直接查 Inventory 表——跨领域数据访问，没有任何抽象。第二，同步 HTTP 调用 `Inventory.API` 预留库存。如果服务重启、网络抖动、滚动部署，所有在途请求一起失败。第三，所有变更落回同一个共享数据库，一次迁移就能级联炸掉所有服务。

## 修复 1：每个服务拥有自己的数据

`Refactored/Orders.Standalone` 项目展示了数据自治长什么样。Orders 服务不再依赖 `Shared.DataAccess`，而是定义自己的 `OrdersDbContext`，只暴露自己拥有的实体：

```csharp
using Microsoft.EntityFrameworkCore;

namespace Orders.Standalone.Data;

public class OrdersDbContext : DbContext
{
    public OrdersDbContext(
        DbContextOptions<OrdersDbContext> options) : base(options) { }

    public DbSet<Order> Orders => Set<Order>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Order>(entity =>
        {
            entity.HasKey(e => e.OrderId);
            entity.Property(e => e.CreatedAt)
                .HasDefaultValueSql("datetime('now')");
        });
    }
}
```

Orders 服务再也看不到 Inventory 或 Customers 表。如果开发者试图从 Orders 查库存数据，编译就过不了。边界由类型系统强制执行，不靠约定或团队默契。

在生产系统中，每个服务还有自己的连接串指向独立 schema 或独立数据库实例。Orders 数据库的迁移不可能搞崩 Inventory 或 Customers。

## 修复 2：异步通信

去掉共享数据库后，服务之间需要另一种对话方式。答案是事件，不是同步 HTTP 调用。重构后的项目为 Inventory 领域定义了显式的事件合约：

```csharp
namespace Orders.Standalone.Events;

public interface IInventoryService
{
    Task<bool> CheckStockAvailabilityAsync(
        int productId, int quantity);
    Task PublishStockReservationRequestAsync(
        int productId, int quantity);
}

public record StockReservationRequested(
    int ProductId, int Quantity, int OrderId);

public record StockReserved(
    int ProductId, int Quantity, int OrderId);

public record StockReservationFailed(
    int ProductId, int Quantity, int OrderId, string Reason);
```

Orders 不再调用 `Inventory.API` 阻塞等待响应，而是发布 `StockReservationRequested` 事件。Inventory 服务处理它，然后发布 `StockReserved` 或 `StockReservationFailed`。Orders 响应这些事件来决定完成还是取消订单。

这是根本不同的模型。Orders 不再依赖 Inventory 在下单那一刻刚好可用。如果 Inventory 暂时下线，事件排队，恢复后处理。服务在时间上解耦了——这才是独立部署真正成立的理由。

## 修复 3：独立部署纪律

独立数据库和事件驱动是独立性的技术基础，但保持解耦还需要持续约束服务 API 的演进方式。

每个服务的公开接口——事件 schema 和 HTTP 合约——必须带版本且向后兼容。你应该能做到部署新版本 Orders 而不要求 Inventory 同时部署。做不到就说明耦合还在，只是不在代码里明显了。

消费者驱动的契约测试可以自动执行这个边界。Inventory 团队定义它产生什么事件，Orders 团队写测试验证这些合约是否符合自己的期望。如果 Inventory 破坏了合约，Orders 的测试在进生产前就抓到。

另外留意你的依赖注入配置如何反映服务边界。如果把服务注册按领域模块组织，跨模块的注册依赖会在编译期就暴露边界被侵犯。

## 该不该合并回单体

有时候正确答案是把分布式单体合并回一个可部署单元。这就是模块化单体，对很多团队来说它既合理，往往也更优。

如果你的服务总是一起部署、一直同步通信、从来没有独立扩缩的需求——那你就在全额支付微服务的运维成本，却没拿到任何好处。一个结构良好的模块化单体——独立模块、独立数据访问层、模块间定义清晰的接口——用很小的运维复杂度就能提供大部分架构收益。

判断是否真正需要分布式部署的几条标准：

- **独立扩缩需求**——系统不同部分确实有不同的负载特征，需要独立的基础设施
- **独立部署节奏**——不同团队需要发布而不跟别的团队协调
- **故障隔离要求**——一个部分的故障不能拖垮其余部分
- **组织边界**——康威定律早就预言架构会镜像团队结构

这些条件不满足的话，合并回去不是失败，是好的工程判断。

## 参考

- [原文：Distributed Monolith Anti-Pattern](https://www.devleader.ca/2026/07/12/distributed-monolith-the-antipattern-every-c-developer-should-recognize)
