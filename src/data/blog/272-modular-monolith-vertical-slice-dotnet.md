---
pubDatetime: 2025-04-17 12:08:46
tags: [".NET", "Architecture"]
slug: modular-monolith-vertical-slice-dotnet
source: https://dev.to/antonmartyniuk/building-a-modular-monolith-with-vertical-slice-architecture-in-net-2jj7
title: 从零搭建.NET模块化单体：垂直切片架构的最佳实践
description: 结合Clean Architecture与Vertical Slice，在.NET中构建可扩展、易维护的模块化单体架构，助你轻松实现微服务演进。
---

# 从零搭建.NET模块化单体：垂直切片架构的最佳实践

## 引言：为什么不要一上来就选微服务？

> “你不应该用微服务开启新项目，即使你确信应用会变得足够大。”——Martin Fowler

这句话你一定不陌生。很多.NET开发者、架构师在新项目时都面临着“单体 or 微服务”的抉择。  
微服务看起来很酷，但上手成本高、复杂度爆表，远远超出许多团队的实际需求。那是不是还得回头用“传统大单体”？其实还有更优解——**模块化单体（Modular Monolith）**。

本文结合 Clean Architecture 和 Vertical Slice，带你深入了解 .NET 下的模块化单体架构，如何在易于开发和部署的同时，保持模块独立、易于未来迁移到微服务。  
（适合有一定架构经验、关注企业级应用设计的.NET开发者阅读）

---

## 什么是模块化单体？🧩

模块化单体是一种融合了单体和微服务优势的架构：

- **统一代码库**，开发效率高
- **一次部署**，运维简单
- **模块边界清晰**，每个业务模块互不干扰
- **模块可独立开发、集成测试**
- **未来可平滑迁移到微服务**

### 模块间如何通信？

- 只允许通过**公共接口（Public API）**通信，不能直接操作对方数据库。
- 推荐用方法调用，如果考虑未来迁移微服务，可提前采用事件驱动架构。

---

## 项目结构一览

我们以实际业务为例：  
三个核心业务模块 —— Shipments（发货）、Carriers（承运商）、Stocks（库存）。

**在微服务里，它们通常是三个服务，各自独立数据库和接口。  
在模块化单体里，它们则是同一个解决方案下的不同模块。**

![项目结构总览](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fqfgifb74qn0v24o7kjzc.png)

每个模块都遵循统一分层：

- Domain：领域实体与业务逻辑
- Features：基于垂直切片的业务用例实现
- Infrastructure：技术实现，如数据库
- PublicApi：对外暴露的合约（接口）

---

## 深入拆解：Shipments 模块

来看下 Shipments 模块的详细结构👇

![Shipments模块结构](https://media2.dev.to/dynamic/image/width=800%2Cheight=%2Cfit=scale-down%2Cgravity=auto%2Cformat=auto/https%3A%2F%2Fdev-to-uploads.s3.amazonaws.com%2Fuploads%2Farticles%2Fx04yy11ynnl9xi6kch1x.png)

### 领域实体举例

```csharp
public class Shipment
{
    public Guid Id { get; set; }
    public string Number { get; set; }
    public string OrderId { get; set; }
    public Address Address { get; set; }
    public string Carrier { get; set; }
    public string ReceiverEmail { get; set; }
    public ShipmentStatus Status { get; set; }
    public List<ShipmentItem> Items { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
}
```

### 独立的数据访问

每个模块有自己独立的 DbContext 及数据库 schema：

```csharp
public class ShipmentsDbContext : DbContext
{
    public DbSet<Shipment> Shipments { get; set; }
    // ...
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasDefaultSchema("Shipments");
    }
}
```

### 垂直切片 + Clean Architecture

每个功能就是一个“垂直切片”，比如“创建发货”用例：

- 校验请求参数
- 调用 Stocks 模块检查库存
- 创建 Shipment 记录
- 通知 Carriers 模块登记发货信息
- 再次调用 Stocks 模块扣减库存

简化后的 Minimal API Endpoint：

```csharp
public class CreateShipmentEndpoint : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        app.MapPost("/api/shipments", Handle);
    }

    private static async Task<IResult> Handle(
        [FromBody] CreateShipmentRequest request,
        IValidator<CreateShipmentRequest> validator,
        IMediator mediator,
        CancellationToken cancellationToken)
    {
        // ...校验及业务逻辑处理...
        return Results.Ok(response.Value);
    }
}
```

业务逻辑通过 MediatR 处理：

```csharp
public async Task<ErrorOr<ShipmentResponse>> Handle(
    CreateShipmentCommand request, CancellationToken cancellationToken)
{
    // 1. 校验订单是否已存在发货
    // 2. 检查库存
    // 3. 保存发货信息
    // 4. 通知承运商
    // 5. 更新库存
}
```

---

## Carriers 与 Stocks 模块接口示例

**Carriers模块暴露API：**

```csharp
public interface ICarrierModuleApi
{
    Task CreateShipmentAsync(CreateCarrierShipmentRequest request, CancellationToken cancellationToken = default);
}
```

**Stocks模块暴露API：**

```csharp
public interface IStockModuleApi
{
    Task<CheckStockResponse> CheckStockAsync(CheckStockRequest request, CancellationToken cancellationToken = default);
    Task<UpdateStockResponse> UpdateStockAsync(UpdateStockRequest request, CancellationToken cancellationToken = default);
}
```

实现均为 `internal`，细节不对外暴露，保证模块封装性。

---

## 为什么选择垂直切片架构？🎯

将 Clean Architecture 与 Vertical Slice 结合，有如下好处：

- 关注特性开发，避免无关代码污染
- 多团队协作更高效，分工明确
- 灵活支持不同技术选型和实现方式
- 易于维护与理解，代码结构清晰
- 降低各功能间耦合度

对.NET的大型项目来说，这样的架构极大提升了可扩展性和可维护性。

---

## 总结与行动建议

1. **不要盲目上微服务**——除非你已经遇到明显的组织与技术瓶颈。
2. **优先选择模块化单体**，用清晰边界管理复杂业务。
3. **用好垂直切片架构**，关注业务特性本身，让你的代码更加易读、易扩展。
4. **为未来演进做好准备**——公共接口通信、事件驱动，为后续拆分打好基础。

---

> 🎁 源码下载&更多实践分享：[antondevtips.com](https://antondevtips.com/blog/building-a-modular-monolith-with-vertical-slice-architecture-in-dotnet?utm_source=devto&utm_medium=social&utm_campaign=april-2025)

---

## 互动时间

你现在的企业应用是怎样划分模块和团队协作的？  
你在使用.NET过程中，有哪些架构难题想要深入探讨？  
欢迎留言分享你的观点！如果觉得本文有帮助，也请点个赞或分享给同事吧 🚀
