---
pubDatetime: 2026-07-09T08:25:27+08:00
title: "单体还是微服务：给 .NET 开发者的 5 个判断问题"
description: "别再问'我们够不够大用微服务'。这篇用 5 个真正有用的问题帮你判断单体、微服务还是模块化单体更适合当前项目，并讲清分布式单体这个最坑的失败模式怎么避开。"
tags: ["架构设计", "微服务", "单体架构", "模块化单体", ".NET"]
slug: "monolith-vs-microservices-csharp-decision-framework"
source: "https://www.devleader.ca/2026/07/08/monolith-vs-microservices-in-c-a-decision-framework-for-net-developers"
ogImage: "../../assets/935/01-cover.png"
---

单体和微服务的争论，产生的热度远大于有用的结论。有几年行业默认微服务是"长大成人"该走的路，可现在越来越多团队在往回走——他们发现时机不对或做得不到位的微服务，会把交付速度拖到爬，运维负担翻倍，却没换来任何有意义的业务价值。

这篇不打算说"微服务不好"，也不是给单体唱赞歌。它给的是一套判断框架：5 个真正重要的问题，帮你为自己这个具体的 .NET 项目选对架构，而不是追去年会议上被讲得最多的那个模式。

## 先看清楚你在权衡什么

在问"该选哪个"之前，得先弄清你实际在换取什么。两种架构在影响日常工作的几个维度上是这样对比的：

| 维度                     | 单体                       | 微服务                                 |
| ------------------------ | -------------------------- | -------------------------------------- |
| **部署**                 | 单一制品，CI/CD 简单       | 独立可部署单元，编排复杂               |
| **扩展**                 | 要么整体扩，要么不扩       | 按需扩单个服务                         |
| **团队自治**             | 共享代码库，协调成本高     | 团队各自拥有服务                       |
| **调试**                 | 单进程，直接               | 需要跨服务分布式追踪                   |
| **运维复杂度**           | 低，一个运行时一个库       | 高，服务发现、负载均衡、重试、可观测性 |
| **开发速度（早期）**     | 快，没有网络调用和契约     | 慢，得先把服务基础设施搭起来           |
| **开发速度（规模化后）** | 缺纪律的话会随代码增长变慢 | 边界清晰时反而能加速                   |

这张表的核心结论是：微服务在规模化时才回本，但前期成本高出一大截。表里每一个写着"复杂"或"高"的格子，都代表你团队从第一天起就要背的实打实的工程量——不是将来某天，是第一天。

## 判断框架：5 个真正重要的问题

别再问"我们够不够大能上微服务"，改问下面这 5 个问题。

### 问题一：团队多大？

团队规模是判断微服务帮你还是害你的最好指标。少于 10-12 个工程师时，微服务的协调成本——独立仓库、独立 CI 流水线、带版本的 API 契约、服务网格配置——会把它承诺的生产力大部分吃掉。

到 50+ 工程师时，你常会遇到反过来的问题：单个单体造成部署瓶颈、合并冲突和共享 schema 的噩梦。独立服务让团队各自发布、互不踩脚。前提是你要有职责清晰的团队，而不只是更多人头。

12-50 这个区间，通常是模块化单体（下面会讲）赢的地方。它让团队在内部拥有所有权，又不用过早交那笔分布式系统的税。

### 问题二：领域边界有多清楚？

微服务的生死系于边界定义。如果你在还没完全理解领域之前就拆服务，一定会切错——而切错会在网络边界上造成紧耦合，这比单进程内部的紧耦合糟糕得多。

如果你在做一个全新的东西，那你几乎肯定还不知道自己的边界。先从单体开始，通过能运行的软件去发现你的领域，等接缝自己显现出来时再抽取。没有什么能替代真实使用模式告诉你东西自然该在哪里分开。

### 问题三：运维成熟度如何？

微服务需要你团队可能还不具备的基础设施能力。你需要分布式追踪——因为一条日志不会告诉你服务 A 调服务 B 时 B 为什么超时。你需要集中日志聚合、带自动重启的健康检查、熔断器、重试策略，以及一套优雅处理部分失败的清晰方案。

如果你团队还没有成型的 DevOps 文化——自动化部署、基础设施即代码、把监控当头等大事——微服务不会帮你建立这种文化，它只会大声暴露这种文化的缺失，通常是在凌晨两点。

### 问题四：系统不同部分需要独立扩展吗？

这常被当成微服务的杀手级论据，而且在它适用时确实是真优势。如果你的图像处理流水线需要用户资料服务 10 倍的算力，把这块算力密集的部分抽出来就有意义。

但要对"这是当下真实需求，还是理论上的未雨绸缪"诚实。多数早期应用的负载分布是均匀的。为了支持一个根本不会发生的扩展而过早拆服务，纯粹是额外开销。一个内部边界清晰的模块化单体，能让你以后单独抽出那个真正需要独立扩展的服务，而不用重建其余一切。

### 问题五：新建还是迁移？

新项目几乎总是从单体起步更好——具体说是结构良好的模块化单体。产品的第一个版本要找的是产品市场契合度，不是去优化那些你现在还用不上的分布式系统模式。

迁移是另一回事。一个模块边界清晰的可运行单体，是一个你能增量抽取的单体。在旧代码还在跑的同时把流量路由到新服务，是最安全的迁移策略——它让你在完全押注每次抽取之前先验证它。

## 什么时候单体赢

这些场景下，结构良好的单体是正确的默认选择：

- **早期产品**——领域未知、团队小、需求快速变化。快速上线、快速学习。
- **内部工具和管理后台**——通常流量低、团队小、部署不频繁。微服务的运维开销在这里纯属浪费。
- **高数据一致性要求**——分布式事务是真的痛。如果几乎每个操作都涉及多个必须保持一致的实体，把它们放在一个进程一个数据库里会简单得多。
- **亚 10 毫秒延迟目标**——去掉服务间的网络跳数，能在一整类延迟问题出现之前就消除它们。

在这些场景里，保持干净的内部结构——清晰的模块目录、依赖注入边界、恰当使用策略、装饰器、观察者等设计模式——能让你拿到模块化的好处，又不付运维成本。

## 什么时候微服务赢

这些地方微服务确实值回票价：

- **规模大、稳定、领域边界清楚的产品**——你已经跑了好几年单体，清楚知道接缝在哪，不同团队拥有明显可分的能力。
- **扩展需求截然不同**——某个组件确实需要独立于其他部分扩展，抽取的成本被算力节省证明是划算的。
- **独立的发布节奏**——不同业务线或面向客户的界面需要按完全不同的时间线部署，不共享发布协调。
- **多语言需求**——某个服务硬性要求不同的运行时（Python 做 ML 推理、Go 做低延迟网关），而 .NET 确实满足不了。
- **强故障隔离**——如果你的通知服务宕机必须对支付服务零影响，硬进程隔离能以进程内代码做不到的方式强制这条边界。

诚实地说，这些都是真实的好处，但它们通常是后来才浮现的需求，不是新项目第一天就有的需求。

## 分布式单体这个陷阱

最扎心的失败模式是这个：团队把应用拆成了"服务"，却没真正解决耦合。结果是一个分布式单体——有微服务的全部运维复杂度，却没有任何独立性带来的好处。

```csharp
// 反例：OrderService 和 InventoryService 看着独立，
// 却共享同一个 DbContext——伪装的分布式单体
public class OrderService
{
    private readonly AppDbContext _db; // 共享数据库上下文

    public OrderService(AppDbContext db) => _db = db;

    public async Task PlaceOrderAsync(int productId, int quantity)
    {
        // 直接操作"另一个服务的"表里的库存数据
        var product = await _db.Products.FindAsync(productId);
        if (product == null || product.Stock < quantity)
            throw new InvalidOperationException("Insufficient stock.");

        product.Stock -= quantity;
        _db.Orders.Add(new Order { ProductId = productId, Quantity = quantity });
        await _db.SaveChangesAsync();
    }
}

// 作为独立进程部署——但在数据层依然耦合
public class InventoryService
{
    private readonly AppDbContext _db; // 同一个共享上下文——问题所在

    public InventoryService(AppDbContext db) => _db = db;

    public async Task<int> GetStockAsync(int productId)
    {
        var product = await _db.Products.FindAsync(productId);
        return product?.Stock ?? 0;
    }
}
```

两个"服务"共享一个数据库上下文，直接操作彼此的表。你没法独立部署它们——一个的 schema 迁移会弄坏另一个。你没法独立扩展它们——它们会在同一批行上竞争。你跑着两个进程去监控和维护，却拿不到任何让微服务值得投资的独立性。

分布式单体是一个警告信号：领域边界还没想清楚。解药不是加更多服务，而是回头先定义真正的边界。

## 模块化单体：两全其美

模块化单体已经成为务实的中间地带，适合那些想要干净边界、又不想要分布式系统复杂度的团队。思路很直接：把你的单体组织成每个领域各自拥有自己的代码、数据访问层和 DI 注册——但一切都在进程内运行。

```csharp
// MyApp.Orders/OrdersModule.cs
// 每个模块自注册——除非显式暴露，否则什么都不外泄
public static class OrdersModule
{
    public static IServiceCollection AddOrdersModule(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        services.AddScoped<IOrderService, OrderService>();
        services.AddScoped<IOrderRepository, SqlOrderRepository>();
        return services;
    }
}

// MyApp.Inventory/InventoryModule.cs
public static class InventoryModule
{
    public static IServiceCollection AddInventoryModule(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        services.AddScoped<IInventoryService, InventoryService>();
        return services;
    }
}

// MyApp.Host/Program.cs
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddOrdersModule(builder.Configuration);
builder.Services.AddInventoryModule(builder.Configuration);
// 每个模块自成一体——时机到了就能抽出去
var app = builder.Build();
app.Run();
```

这强制了一条结构规则：Orders 模块只能通过 `IInventoryService` 跟 Inventory 对话，绝不直接通过共享的 `DbContext`。每个模块可以有自己作用于自己表的 EF Core `DbContext`。跨模块通信走接口或内部事件——跟你为真正的服务边界会用的模式是一样的。

## 迁移路径：什么时候从单体毕业

跑一个单体跑好几年，不丢人。但有些具体信号会告诉你，抽取开始值这个成本了：

**特定模块需要独立扩展。** 如果你的任务处理模块在扛 CPU 负载，而客户门户却闲着，独立扩展就开始回本了。这表现为集中在单个模块的资源竞争。

**同一代码库上团队增长到约 15 人以上。** 部署冲突、长合并队列、职责不清是早期指标。不是硬性界限，但值得认真对待。

**部署冲突正在卡团队。** 如果两个团队因为代码一起发布而在等同一个发布窗口，共享部署的成本就变得可见、可衡量了。

**某个模块有硬性技术要求。** ML 推理要 Python、高吞吐网关要 Go——有时确实是真实的技术错配，证明抽取合理。

真要抽取时，模块化单体里内建的基于接口的抽象给你一个干净的接缝。下面这个模式让抽取成为增量工作，而不是重写级别的工作：

```csharp
// 抽象保持稳定——抽取时只换实现
public interface IOrderProcessor
{
    Task<OrderResult> ProcessAsync(OrderRequest request, CancellationToken ct = default);
}

// 进程内：零网络开销——在有具体理由之前一直用这个
public class InProcessOrderProcessor : IOrderProcessor
{
    private readonly IInventoryService _inventory;
    private readonly IOrderRepository _orders;

    public InProcessOrderProcessor(
        IInventoryService inventory,
        IOrderRepository orders)
    {
        _inventory = inventory;
        _orders = orders;
    }

    public async Task<OrderResult> ProcessAsync(
        OrderRequest request,
        CancellationToken ct = default)
    {
        var available = await _inventory.IsAvailableAsync(
            request.ProductId, request.Quantity, ct);

        if (!available)
            return OrderResult.Failure("Insufficient stock");

        var order = await _orders.CreateAsync(request, ct);
        return OrderResult.Success(order.Id);
    }
}

// HTTP 实现：藏在同一个接口后面的抽取出的服务
// Order 服务独立部署后，通过 DI 换成这个
public class HttpOrderProcessor : IOrderProcessor
{
    private readonly HttpClient _client;

    public HttpOrderProcessor(HttpClient client)
    {
        _client = client;
    }

    public async Task<OrderResult> ProcessAsync(
        OrderRequest request,
        CancellationToken ct = default)
    {
        var response = await _client.PostAsJsonAsync("/orders", request, ct);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<OrderResult>(ct)
            ?? OrderResult.Failure("Empty response");
    }
}
```

今天你在生产里部署 `InProcessOrderProcessor`，等 Order 服务上线并验证后，改一处 DI 注册切到 `HttpOrderProcessor`。调用方代码一行都不用改。这就是从一开始就投资干净抽象的回报——抽取变成一次配置切换，而不是一次重写。

## 常见问题

**单体总是正确的起点吗？**
对多数新项目是。模块化单体给你干净架构的好处，运维复杂度却低得多。主要的例外：如果你高度确信某个组件从第一天起就需要独立扩展或部署，而且你有支撑它的运维成熟度，那么前期就画一条针对性的服务边界是合理的。但"我们以后可能需要"不足以构成理由。

**C# 单体能扛高流量吗？**
完全能。C# 和 .NET 是当今最快的服务端平台之一。一个调优良好的 ASP.NET Core 应用每实例每秒能处理数千请求。水平扩展——在负载均衡后加更多实例——能带你走很远，远到你根本不需要仅为容量而抽服务。

**怎么避开分布式单体陷阱？**
关键规则：如果两个"服务"共享一个数据库，它们就不是真正独立的服务。每个服务必须拥有自己的数据，只通过它的公开 API 暴露。用结构强制这一点——独立数据库或 schema 所有权、不共享 DbContext、没有 ORM 模型跨越服务边界。先定义模块契约（接口、事件、DTO），再在它们背后建实现。

**能从微服务迁回单体吗？**
能，而且发生的比团队公开承认的多。绞杀者模式（Strangler Fig）双向都管用。跑着没有真正独立性好处的分布式单体的团队，常会发现把服务收拢成结构良好的模块化单体能大幅简化运维、降低延迟、加快开发——而不丢失架构清晰度。

## 小结

单体与微服务的争论，不是哪个架构客观上更好的问题，而是对你的团队规模、领域清晰度、运维成熟度和实际扩展需求来说，此刻哪个更好的问题。微服务解决真实的问题，也引入真实的成本。这套五问框架给你的是一个诚实的筛子，而不是一个照搬的模式。

从结构良好的模块化单体起步，从第一天就用接口和 DI 模块注册强制模块边界。让真实的扩展需求和团队摩擦告诉你什么时候抽取值这个成本。对多数 .NET 团队来说，这个路子会比在任一方向上追最新架构潮流服务得更好。

## 参考

- [Monolith vs Microservices in C#: A Decision Framework for .NET Developers](https://www.devleader.ca/2026/07/08/monolith-vs-microservices-in-c-a-decision-framework-for-net-developers)
  </content>
