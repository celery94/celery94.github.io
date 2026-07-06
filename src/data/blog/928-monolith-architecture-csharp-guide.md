---
pubDatetime: 2026-07-06T20:21:14+08:00
title: "单体架构在 C# 中的完整指南：从传统分层到模块化单体"
description: "区分传统分层单体、模块化单体和分布式单体反模式，用代码演示 C# 中如何通过依赖注入和 internal 关键字保护模块边界，并给出何时用单体、何时拆微服务的判断框架。"
tags:
  [
    "C#",
    "Architecture",
    "Monolith",
    "Modular Monolith",
    "Design Patterns",
    ".NET",
  ]
slug: "monolith-architecture-csharp-guide"
source: "https://www.devleader.ca/2026/07/04/monolith-architecture-in-c-the-complete-guide"
ogImage: "../../assets/928/01-cover.png"
---

在微服务、事件驱动、分布式架构成为讨论焦点的这些年里，单体被贴上了“遗留系统”的标签。但一个干净、边界清晰的单体项目——尤其是在 C# 里——仍然是很多团队最合理的起步选择。

这篇文章把单体架构分成三种形态，讲清楚它们的代码特征、适用场景和常见陷阱，并给出 C# 中从传统分层单体演进到模块化单体的完整路径。

## 三种单体，不要混为一谈

单体不是只有一种。团队讨论“要不要拆服务”的时候，通常没有先分辨自己面对的是哪一种单体，导致决策方向错了。

### 传统分层单体

这是教科书教的标准结构：表现层 → 业务逻辑层 → 数据访问层。每层只依赖下一层。理想很清晰，但实践里这层约束最容易崩塌——业务层直接 `new OrderRepository()`，不做依赖注入：

```csharp
public class OrderService
{
    private readonly OrderRepository _repository = new OrderRepository();

    public void PlaceOrder(Order order)
    {
        if (order.Items.Count == 0)
            throw new InvalidOperationException("Cannot place an empty order.");
        order.Status = OrderStatus.Pending;
        order.PlacedAt = DateTime.UtcNow;
        _repository.Save(order);
    }
}
```

`OrderService` 被直接焊死在 `OrderRepository` 上——无法单元测试、无法替换实现。这不是单体架构本身的问题，而是耦合控制的问题。

### 模块化单体

模块化单体保持一个部署单元，但用**垂直边界**代替水平分层。每个模块（订单、商品、用户）是独立的类库项目，只通过 `public` 接口暴露能力，内部实现全是 `internal`：

```
MyStore.sln
├── MyStore.Api/          # 宿主项目，入口
├── MyStore.Orders/        # 订单模块
│   ├── IOrderService.cs   # public - 模块公共契约
│   ├── OrderService.cs    # internal - 其他模块不可见
│   └── OrderRepository.cs # internal - 其他模块不可见
├── MyStore.Catalog/       # 商品模块
└── MyStore.Shared/        # 共享内核，保持小而稳定
```

模块之间不直接引用对方的内部类——这是 C# 编译器帮你强制执行的纪律。

### 分布式单体

分布式单体是一种反模式：团队把应用拆成了多个服务，但这些服务仍然共享数据库、共享领域模型、每个请求都是同步 HTTP 链式调用。结果你拥有了分布式系统的全部运维成本（网络故障、部署协调、延迟），却没有任何微服务的真正收益（独立扩缩、独立发布、技术自治）。如果服务 A 和服务 B 共享一张表导致必须一起发布，你手里就是一个分布式单体。

没准备好分离数据库、异步通信和独立 API 契约之前，一个结构良好的模块化单体几乎总是更好的选择。

## 单体的真正优势

在微服务叙事占主流的环境里，单体有几个容易被忽略的实际好处：

**部署简单。** 一次 `dotnet publish`，复制文件或推送一个容器镜像，结束。不需要编排、服务网格、分布式追踪基础设施。

**调试零摩擦。** 所有代码在一个进程里，断点随便打，堆栈完整。不需要跨五个服务追一条请求。

**运维开销低。** 没有 API 网关、没有每服务负载均衡、不需要 Kubernetes。小团队可以把精力花在产品而不是基础设施上。

**进程内调用零网络延迟。** 业务逻辑中的多次依赖操作如果走 HTTP 跨服务调用会累积显著延迟，留在进程内是纳秒级的。

**集成测试简单。** 启一个进程、挂一个测试数据库，就能端到端跑完整个应用。不需要 mock 远程服务。

## 单体的真正痛点

知道这些痛点，你可以提前规划而不是被动应对：

**扩展瓶颈。** 单体作为整体扩缩。只要一个功能 CPU 密集型，就得扩整个应用——而不只是那一个模块。

**构建变慢。** 代码量增长后，改一行代码也触发全量构建。CI 流水线越来越慢，迭代节奏被拖住。

**共享数据库耦合。** 传统分层单体中所有功能共享一张 schema。改一张表影响所有模块，schema 迁移风险高。

**大团队协调成本。** 多人共享同一个代码库时，合并冲突和意外耦合随人数增长。

**依赖升级牵连全局。** 一个 `csproj` 管所有 NuGet 包，升级一个共享库影响所有模块。

## 什么时候用单体是正确答案

**团队人数在 10-12 人以内。** 小团队管理多服务的开销会显著拖慢开发。一个代码库意味着共享上下文、更快的 Code Review 和更高的迭代速度。

**新项目或绿地项目。** 领域边界在项目初期几乎总是不清晰的。模块化单体让你在进程中摸索和调整边界，不需要付出跨服务迁移的成本。

**领域边界不明朗。** 如果你还说不清自然的切分线在哪，过早拆服务只会把耦合从代码层面搬到网络层面——耦合还在，延迟更大了。

**运维简洁是刚需。** 如果你的团队没有专职平台或基础设施工程师，负责任地运行一个分布式系统的负担很重。单体部署到一台 App Service、一台 VM 或一个小容器容易得多。

**启动速度重要。** 花在搭建 Kubernetes、服务网格和分布式追踪上的每一周，都是没有花在构建产品上的时间。单体能让你把这些复杂性推迟到真正需要为止。

## 用依赖注入改造传统分层单体

传统分层单体的核心问题是 `new OrderRepository()` 这种硬耦合。用接口抽象替换它，代码不动结构、只改依赖关系：

```csharp
// 领域层 —— 纯实体
public class Order
{
    public int Id { get; set; }
    public List<OrderItem> Items { get; set; } = new();
    public OrderStatus Status { get; set; }
    public DateTime PlacedAt { get; set; }
}

// 应用层 —— 接口和实现分离
public interface IOrderRepository
{
    void Save(Order order);
    Order? GetById(int orderId);
}

public class OrderService : IOrderService
{
    private readonly IOrderRepository _repository;

    // 构造函数注入 —— 可测试，松耦合
    public OrderService(IOrderRepository repository)
    {
        _repository = repository
            ?? throw new ArgumentNullException(nameof(repository));
    }

    public void PlaceOrder(Order order)
    {
        if (order.Items.Count == 0)
            throw new InvalidOperationException("订单不能为空。");
        order.Status = OrderStatus.Pending;
        order.PlacedAt = DateTime.UtcNow;
        _repository.Save(order);
    }
}
```

`OrderService` 依赖 `IOrderRepository` 而不是具体类。测试时注入内存实现，生产环境注入 SQL 实现——`OrderService` 不需要任何修改。

## internal 关键字：模块化单体的编译器防线

C# 的 `internal` 访问修饰符是把模块化边界从“团队约定”升级为“编译器强制”的关键工具。每个模块作为独立的类库项目，只有显式标记 `public` 的类型才会暴露给其他模块：

```csharp
// MyStore.Orders 项目 —— 模块边界示例

// 这是模块的公共契约 —— 所有其他模块可见
public interface IOrderService
{
    void PlaceOrder(Order order);
    Order? GetOrder(int orderId);
}

// 实现细节 —— 其他模块完全不可见
internal class OrderService : IOrderService
{
    private readonly IOrderRepository _repository;

    internal OrderService(IOrderRepository repository)
    {
        _repository = repository;
    }

    public void PlaceOrder(Order order) { /* ... */ }
    public Order? GetOrder(int orderId) => _repository.GetById(orderId);
}

internal class OrderRepository : IOrderRepository { /* ... */ }

// 模块唯一的公共入口 —— 装配 DI 容器
public static class OrdersModule
{
    public static IServiceCollection AddOrdersModule(
        this IServiceCollection services)
    {
        services.AddScoped<IOrderService, OrderService>();
        services.AddScoped<IOrderRepository, OrderRepository>();
        return services;
    }
}
```

`CatalogModule` 无法直接 `new OrderRepository()`——编译器直接拒绝。每个模块只暴露它必须暴露的接口，所有实现细节隐藏。这就是模块化单体区别于“大泥球”的核心纪律。

## 从传统单体到模块化单体的演进路径

大多数团队不是从零搭建一个完美的模块化单体，而是手里已经有一个大而混乱的传统分层单体。好消息是这个演进是渐进的——不需要停止功能开发。

典型路径：先在现有代码中识别自然的领域边界（订单、商品、用户、支付、通知），画出概念模块线。然后逐步把类移动到对应模块项目中，把直接类引用替换为接口依赖。`internal` 成为你的“lint 规则”——如果模块 A 的代码需要访问模块 B 的 `internal` 类型，这是一个需要重新设计的耦合问题，而不是该绕过去。

当模块边界稳定并通过测试后，未来某天把一个模块提取为独立服务就变成了一个小得多的操作——接口契约、领域模型和基础设施层都已经定义好了。提取主要是一个运维动作，而不是一次架构重写。

## 总结

单体不是敌人。不设边界、不控制耦合的单体才是。用依赖注入打破硬耦合、用 `internal` 保护模块边界、用独立类库项目组织领域——这三点已经能让一个 C# 单体在相当长的时间内保持可维护。

关键判断不应该是“单体还是微服务”，而是“我现在能控制住模块边界吗”。能，就用模块化单体继续跑；不能但需要控制，先修结构再讨论拆。

如果你关注 .NET 架构、设计模式和工程实践，可以关注 Aide Hub。这里会继续分享能落地的架构分析和代码重构经验。

## 参考

- [原文: Monolith Architecture in C#: The Complete Guide](https://www.devleader.ca/2026/07/04/monolith-architecture-in-c-the-complete-guide)
- [Strategy 设计模式 in C#](https://www.devleader.ca/2026/03/02/strategy-design-pattern-in-c-complete-guide-with-examples)
- [Observer 设计模式 in C#](https://www.devleader.ca/2026/03/26/observer-design-pattern-in-c-complete-guide-with-examples)
- [Decorator 设计模式 in C#](https://www.devleader.ca/2026/03/14/decorator-design-pattern-in-c-complete-guide-with-examples)
- [Builder 设计模式 in C#](https://www.devleader.ca/2026/02/18/builder-design-pattern-in-c-complete-guide-with-examples)
