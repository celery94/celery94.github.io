---
pubDatetime: 2026-03-26T14:20:00+08:00
title: "业务规则不该写在 Controller 里：ASP.NET Core 分层设计实践"
description: "胖 Controller 是 ASP.NET Core 项目里最常见的坏味道之一。本文通过电商订单的完整示例，演示如何把业务规则从 Controller 中剥离，分别用 Domain Service 模式和领域驱动设计两种方式重构，让 Controller 真正回归职责单一。"
tags: ["ASP.NET Core", "C#", "Architecture", "Clean Code", "DDD"]
slug: "designing-business-rules-clean-controllers"
ogImage: "../../assets/675/01-cover.png"
source: "https://blog.elmah.io/designing-business-rules-that-dont-leak-into-controllers/"
---

![业务规则分层架构示意图](../../assets/675/01-cover.png)

Controller 是 API 的入口，理论上应该只做三件事：接收请求、调用下层、返回响应。但在实际项目中，不少开发者会把用户校验、金额判断、业务限制条件直接写进 Controller Action，久而久之就成了所谓的"胖 Controller"。

这不只是代码整洁的问题。业务规则一旦耦合进 Controller，测试就得通过 HTTP 请求来驱动，需求变更时要在 Controller 里翻来覆去地找条件分支，多个接口复用同一段逻辑也变得困难。本文展示如何识别问题并系统地解决它。

## 胖 Controller 长什么样

以一个电商下单场景为例，来看一段典型的"胖"实现：

```csharp
using System;
using Microsoft.AspNetCore.Mvc;

namespace EcCommerce.Controllers;

[ApiController]
[Route("api/[controller]")]
public class OrdersController : ControllerBase
{
    private readonly ApplicationDbContext _context;

    public OrdersController(ApplicationDbContext context)
    {
        _context = context;
    }

    [HttpPost]
    public async Task<IActionResult> CreateOrder(CreateOrderRequest request)
    {
        var user = await _context.Users
            .Include(u => u.Orders)
            .FirstOrDefaultAsync(u => u.Id == request.UserId);

        if (user == null)
            return NotFound("User not found");

        if (!user.IsActive)
            return BadRequest("User is not active");

        if (request.TotalAmount <= 0)
            return BadRequest("Invalid order amount");

        var todayOrdersCount = user.Orders
            .Count(o => o.CreatedAt.Date == DateTime.UtcNow.Date);

        if (todayOrdersCount >= 5)
            return BadRequest("Daily order limit exceeded");

        var order = new Order
        {
            UserId = user.Id,
            TotalAmount = request.TotalAmount,
            CreatedAt = DateTime.UtcNow
        };

        _context.Orders.Add(order);
        await _context.SaveChangesAsync();

        return Ok(order);
    }
}
```

这段代码的问题一眼可见：Controller 知道的事情太多了。用户是否激活、订单金额是否合法、今天下单次数是否超限——这些都是业务规则，不是请求处理逻辑。如果日限从 5 改成 50，必须来 Controller 里找这一行；如果其他接口也要下单，整段逻辑得再复制一遍。单一职责原则（SRP）和 DRY 原则都被同时违反了。

## 方案一：抽出 Domain Service

最直接的修法是引入一个服务层，把业务规则收进去。

**第一步：定义接口**

```csharp
public interface IOrderService
{
    Task<Order> CreateOrderAsync(int userId, decimal totalAmount);
}
```

接口让 Controller 只依赖抽象，后续测试时也方便 Mock。

**第二步：实现服务**

```csharp
public class OrderService : IOrderService
{
    private readonly ApplicationDbContext _context;

    public OrderService(ApplicationDbContext context)
    {
        _context = context;
    }

    public async Task<Order> CreateOrderAsync(int userId, decimal totalAmount)
    {
        var user = await _context.Users
            .Include(u => u.Orders)
            .FirstOrDefaultAsync(u => u.Id == userId);

        if (user == null)
            throw new Exception("User not found");

        if (!user.IsActive)
            throw new Exception("User is not active");

        if (totalAmount <= 0)
            throw new Exception("Invalid order amount");

        var todayOrdersCount = user.Orders
            .Count(o => o.CreatedAt.Date == DateTime.UtcNow.Date);

        if (todayOrdersCount >= 5)
            throw new Exception("Daily order limit exceeded");

        var order = new Order
        {
            UserId = user.Id,
            TotalAmount = totalAmount,
            CreatedAt = DateTime.UtcNow
        };

        _context.Orders.Add(order);
        await _context.SaveChangesAsync();

        return order;
    }
}
```

原来 Controller 里的业务判断，原封不动地搬进了 `OrderService`，抛出异常而不是直接返回 HTTP 状态码。如果想做更精细的异常处理，可以在上层加全局异常中间件统一转换。

**第三步：瘦身后的 Controller**

```csharp
[ApiController]
[Route("api/[controller]")]
public class OrdersController : ControllerBase
{
    private readonly IOrderService _orderService;

    public OrdersController(IOrderService orderService)
    {
        _orderService = orderService;
    }

    [HttpPost]
    public async Task<IActionResult> CreateOrder(CreateOrderRequest request)
    {
        var order = await _orderService
            .CreateOrderAsync(request.UserId, request.TotalAmount);

        return Ok(order);
    }
}
```

三行。Controller 完全不关心业务规则，只负责把请求参数传给服务，把结果包进 HTTP 响应返回。

**注册依赖注入**（`Program.cs`）：

```csharp
var builder = WebApplication.CreateBuilder(args);

// Other injections
builder.Services.AddScoped<IOrderService, OrderService>();
```

如果项目里有多个层次，也可以在服务层内部再注入 Repository 层，进一步把数据访问和业务逻辑分开。

## 方案二：领域驱动设计风格

更进一步的做法是把业务规则直接放到领域模型里，让模型自己知道它的约束是什么。

**User 领域模型**

```csharp
public class User
{
    public bool IsActive { get; private set; }
    public List<Order> Orders { get; private set; } = new();

    public void CanPlaceOrder(decimal totalAmount)
    {
        if (!IsActive)
            throw new Exception("User is not active");

        if (totalAmount <= 0)
            throw new Exception("Invalid order amount");

        var todayOrders = Orders
            .Count(o => o.CreatedAt.Date == DateTime.UtcNow.Date);

        if (todayOrders >= 5)
            throw new Exception("Daily limit exceeded");
    }
}
```

`CanPlaceOrder` 是 `User` 自身的行为，放在这里有充分的理由：这些约束本来就描述了用户下单能力的边界，属于用户的领域知识，而不是外部业务流程强加的规则。

**相应的 OrderService**

```csharp
public class OrderService : IOrderService
{
    private readonly ApplicationDbContext _context;

    public OrderService(ApplicationDbContext context)
    {
        _context = context;
    }

    public async Task<Order> CreateOrderAsync(int userId, decimal totalAmount)
    {
        var user = await _context.Users
            .Include(u => u.Orders)
            .FirstOrDefaultAsync(u => u.Id == userId);

        if (user == null)
            throw new Exception("User not found");

        user.CanPlaceOrder(totalAmount);

        var order = new Order(userId, totalAmount);

        _context.Orders.Add(order);
        await _context.SaveChangesAsync();

        return order;
    }
}
```

服务的主要职责收窄为：加载实体、调用领域行为、持久化结果。纯粹的业务细节被隐藏在 `User.CanPlaceOrder()` 里，服务不需要关心具体是哪几条规则，只需要知道"可不可以下单"这一个问题的答案。

## 两种方案的适用场景

Domain Service 模式更接地气，对大多数 CRUD 型项目来说够用，迁移成本低，团队接受度也更好。

DDD 风格的领域模型在业务规则密集、变化频繁的核心域效果更突出，因为规则和实体本身的状态强相关，改规则时不需要翻服务层代码。代价是领域模型需要更精心的设计，不适合无脑套用。

两者的共同点是：**Controller 最终只关心 HTTP，不关心业务**。一旦日限从 5 改为 50，Controller 不需要动；一旦需要在其他接口复用下单逻辑，直接调 `_orderService.CreateOrderAsync` 即可。单元测试也可以直接针对 `OrderService` 或 `User.CanPlaceOrder` 编写，不需要启动 HTTP 管道。

## 什么应该留在 Controller

Controller 的职责并不是"什么都不做"，而是聚焦在 HTTP 层面：

- 从请求中提取参数并做基础格式校验（比如必填字段、类型检查）
- 调用服务层，传入业务所需的参数
- 将服务层的结果映射成合适的 HTTP 响应（200、201、404、400 等）
- 处理认证 / 授权标注

这条分界线划清楚了，Controller 的代码量自然就很少，测试也容易写。

## 参考

- [Designing business rules that don't leak into controllers](https://blog.elmah.io/designing-business-rules-that-dont-leak-into-controllers/)
