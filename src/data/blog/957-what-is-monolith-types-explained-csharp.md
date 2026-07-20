---
pubDatetime: 2026-07-21T08:46:50+08:00
title: "什么是单体架构？三种类型用 C# 讲清楚"
description: "单体架构不是一种模糊的坏东西，而是三种截然不同的形态：单进程单体、模块化单体和分布式单体（反模式）。本文用 C# 代码讲清每种类型长什么样、各自适用什么场景、以及为什么模块化单体才是大多数团队的正确默认选择。"
tags: ["单体架构", "模块化单体", "C#", ".NET", "架构模式"]
slug: "what-is-monolith-types-explained-csharp"
ogImage: "../../assets/957/01-cover.png"
source: "https://www.devleader.ca/2026/07/10/what-is-a-monolith-monolithic-architecture-types-explained-for-c-developers"
---

"单体"这个词在架构讨论里经常出现，但用法常常互相矛盾且模糊。先把定义说清楚：**单体是一个可部署单元，包含所有应用逻辑**——一份代码库、一个部署产物、一个运行进程。其他一切——好的、坏的、微妙的——都由此派生。

## 单体的精确定义

拆开来看，单体有三个核心特征：

- **一份代码库**：所有功能、领域和层在同一个源码仓库里，一起编译。
- **一个部署单元**：整个应用作为一个产物发布——一个 DLL、一个可执行文件、一个容器镜像——不是独立分片。
- **一个运行时进程**：应用作为单个 OS 进程运行。
- **共享内存空间**：组件之间通过直接方法调用、共享对象和进程内事件通信，而非通过网络。

最后一点是区分单体和分布式系统的决定性特征。当你的 `OrderService` 通过方法调用而非 HTTP 请求调用 `InventoryService` 时，你在单体领域。调用是同步的、快速的、发生在同一内存空间内。没有序列化、没有网络延迟、没有部分失败场景。

单体的定义本身不涉及质量。单体可以结构优雅，也可以是一团乱麻——架构类型不决定这个，你的设计决定决定它。

## 三种单体类型

### 类型一：单进程单体

这是大多数开发者听到"单体"时脑子里浮现的画面。经典分层架构：Controller 调 Service，Service 调 Repository，Repository 调数据库。一切在一个进程里，层之间直接调用。

```csharp
// Controller 层
[ApiController]
[Route("api/customers")]
public sealed class CustomerController : ControllerBase
{
    private readonly ICustomerService _customerService;

    public CustomerController(ICustomerService customerService)
    {
        _customerService = customerService;
    }

    [HttpGet("{id}")]
    public async Task<IActionResult> GetById(int id)
    {
        var customer = await _customerService.GetByIdAsync(id);
        return customer is null ? NotFound() : Ok(customer);
    }
}

// Service 层
public sealed class CustomerService : ICustomerService
{
    private readonly ICustomerRepository _repository;

    public CustomerService(ICustomerRepository repository)
    {
        _repository = repository;
    }

    public async Task<Customer?> GetByIdAsync(int id) =>
        await _repository.GetByIdAsync(id);
}

// Repository 层
public sealed class CustomerRepository : ICustomerRepository
{
    private readonly AppDbContext _dbContext;

    public CustomerRepository(AppDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public async Task<Customer?> GetByIdAsync(int id) =>
        await _dbContext.Customers.FindAsync(id);
}
```

这种模式在中小规模下工作良好。层是逻辑分离的、接口可测试、代码易导航。问题是随着应用增长，Service 之间开始互相依赖、共享工具类被到处引用、分层模型变成横切关注点的迷宫。

### 类型二：模块化单体

模块化单体仍然是单体——一个进程、一次部署——但它在功能模块之间强制执行硬边界。每个模块是一个自包含单元，有自己的公开 API 和内部实现。其他模块只通过公开 API 交互，绝不触碰内部实现。

在 .NET 中通常实现为每个模块一个类库项目，全部被 Web 宿主消费。关键执行机制是项目引用：宿主引用模块程序集，但模块之间不直接引用。

```csharp
// Customers 模块——唯一公开入口
public static class CustomerModule
{
    public static IServiceCollection AddCustomersModule(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        services.AddScoped<ICustomerService, CustomerService>();
        services.AddScoped<ICustomerRepository, CustomerRepository>();
        services.AddDbContext<CustomerDbContext>(options =>
            options.UseSqlServer(
                configuration.GetConnectionString("Customers")));
        return services;
    }
}

// Orders 模块
public static class OrderModule
{
    public static IServiceCollection AddOrdersModule(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        services.AddScoped<IOrderService, OrderService>();
        services.AddScoped<IOrderRepository, OrderRepository>();
        services.AddDbContext<OrderDbContext>(options =>
            options.UseSqlServer(
                configuration.GetConnectionString("Orders")));
        return services;
    }
}

// Program.cs——宿主组合模块
var builder = WebApplication.CreateBuilder(args);
builder.Services
    .AddCustomersModule(builder.Configuration)
    .AddOrdersModule(builder.Configuration);
var app = builder.Build();
app.Run();
```

每个模块声明它暴露了什么，宿主不知道模块的内部类型——只知道公开服务接口。模块化单体的最大实际好处是：如果需要迁移到微服务，每个模块已经是候选服务——有自己的数据上下文、服务边界和公开 API。提取模块只需要单独部署，不需要解依赖关系。

### 类型三：分布式单体（反模式）

分布式单体是两头不靠的反模式：分布式系统的运维复杂度 + 单体的紧耦合。有网络延迟、部署协调头疼、部分失败场景——但仍然不能独立部署组件，因为它们通过共享数据或代码耦合在一起。

```csharp
// Shared.Infrastructure——两个服务都依赖这个共享 DbContext
public class SharedAppDbContext : DbContext
{
    public DbSet<Customer> Customers { get; set; } = null!;
    public DbSet<Order> Orders { get; set; } = null!;
    public DbSet<OrderLine> OrderLines { get; set; } = null!;
}

// "独立服务" #1：OrderService——部署为独立容器
public sealed class OrderService
{
    private readonly SharedAppDbContext _dbContext;

    public OrderService(SharedAppDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    public async Task<Order?> GetOrderWithCustomerAsync(int orderId)
    {
        return await _dbContext.Orders
            .Include(o => o.Customer)
            .FirstOrDefaultAsync(o => o.Id == orderId);
    }
}
```

问题明显：两个"独立服务"共享 `SharedAppDbContext`，后者同时拥有 `Customers` 和 `Orders` 表。改一个服务的 schema 需要更新共享库并同时重新部署两个服务。你在服务之间加了网络跳转，却没有消除使独立部署成为不可能的那个耦合。

分布式单体的明显信号：服务共享数据库 schema、共享库包含实体类型和 DTO、部署一个服务要求同时部署另一个、集成测试需要同时启动多个服务才能测一个功能。

## 三种类型对比

| 维度 | 单进程单体 | 模块化单体 | 分布式单体 |
|---|---|---|---|
| 部署 | 单个产物，简单 | 单个产物，简单 | 多个产物，复杂协调 |
| 耦合 | 中等——层之间自由调用 | 低——强制模块边界 | 高——跨网络共享数据和代码 |
| 团队规模 | 受限——共享代码冲突 | 良好——团队拥有模块 | 差——每次变更都要协调 |
| 调试 | 简单——单进程单日志 | 简单——单进程结构化模块 | 困难——需要分布式追踪 |
| 迁移路径 | 提取前需要解耦工作 | 模块已准备好提取 | 迁移前必须先修耦合 |
| 运维复杂度 | 低 | 低 | 高 |

关键结论：模块化单体几乎总是比单进程单体更好的中间形态，而分布式单体必须避免。如果你要背负分布式服务的运维成本，你需要真正的服务独立性来证明它值得。

## 现代 .NET 中的单体

ASP.NET Core 是良好结构化单体的坚实基础。框架不推你向单体或微服务——它给你工具来正确组织任何一种。

对模块化单体，`IServiceCollection` 扩展方法模式是地道的 .NET 写法，随模块增加而良好扩展。Minimal API 也让每个模块拥有自己的端点注册变得特别容易：

```csharp
public static class CustomerEndpoints
{
    public static IEndpointRouteBuilder MapCustomerEndpoints(
        this IEndpointRouteBuilder app)
    {
        app.MapGet("/api/customers/{id}",
            async (int id, ICustomerService svc) =>
        {
            var customer = await svc.GetByIdAsync(id);
            return customer is null
                ? Results.NotFound()
                : Results.Ok(customer);
        });
        return app;
    }
}
```

每个模块拥有自己的端点注册、服务注册和数据访问，宿主项目只负责组合。这让宿主保持薄，模块保持自包含。

## 单体什么时候是正确的选择

单体不是妥协，不是通向微服务的半步。它经常是系统的正确最终架构。

**团队规模**：2 到 10 人的团队用良好结构化的单体比用分布式系统行动更快。管理多个服务的协调开销，要等到有足够多的人、独立部署真的减少集成冲突时才划算。

**领域清晰度**：微服务要求你在构建之前就清楚服务边界。边界划错代价高昂——你会掉进分布式单体反模式。模块化单体让你通过先构建系统再内部重构来发现正确边界。单体里移动一个模块边界是一个下午的重构量。合并两个配置错误的微服务是数周的基础设施工作量。

**项目阶段**：早期产品方向不断变化。单体更优雅地吸收变化。微服务放大每次领域变更的成本。

多数应用诚实的默认选择是模块化单体。它不是垫脚石——它是合法的目标架构，正确构建时能处理显著规模。

## 结语

理解什么是单体——并区分三种类型——是任何做系统架构的 C# 开发者的基础知识。单进程单体是经典起点；模块化单体在保持单次部署的同时强制执行真正的内部边界；分布式单体是需要主动避免的反模式。

问题不是"单体还是微服务"，而是"什么结构适合我的团队规模、领域清晰度和产品阶段"。对大多数 .NET 应用，答案是一个构建良好的模块化单体。

## 参考

- [原文：What Is a Monolith? Monolithic Architecture Types Explained for C# Developers](https://www.devleader.ca/2026/07/10/what-is-a-monolith-monolithic-architecture-types-explained-for-c-developers)
