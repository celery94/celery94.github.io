---
pubDatetime: 2025-10-22
title: 为什么在 EF Core 中不需要仓储模式
description: 深入探讨在使用 Entity Framework Core 时为什么传统的仓储模式往往是不必要的，以及如何在不同架构风格中直接使用 DbContext 来构建更简洁、更高效的数据访问层。
tags: [".NET", "EF Core", "架构设计", "Clean Architecture", "最佳实践"]
slug: why-you-dont-need-repository-in-ef-core
source: https://antondevtips.com/blog/why-you-dont-need-a-repository-in-ef-core
---

# 为什么在 EF Core 中不需要仓储模式

大多数资深开发者会建议你将 Entity Framework Core (EF Core) 包装在自定义的仓储接口中。但你是否曾经思考过：为什么我们需要在一个已经是仓储的东西之上再创建一个仓储层？

在实际项目中，这种做法往往导致编写大量冗余的样板代码，并产生过度工程化的解决方案。每个功能的实现和维护都需要比应有的时间更长。其实，有更好的方法。

本文将深入探讨以下主题：

- 为什么在 EF Core 中不需要仓储模式
- 如何在没有仓储的情况下使用 EF Core
- 在不同架构风格中使用 EF Core 的最佳实践（N 层架构、整洁架构、垂直切片架构）
- 使用规约模式 (Specification Pattern) 实现查询复用
- 这种方法如何影响可测试性
- 什么时候你可能仍然需要仓储模式

## 为什么不需要仓储模式

### 仓储快速增长的问题

最常见的问题之一是，随着业务需求的演进，仓储类往往会快速膨胀。当应用程序规模较小时，使用仓储模式看起来很简单。但原本只有 4 个方法的简单 CRUD 操作，很快就会演变成一个包含所有可能场景的数据库读写查询的庞大类。

随着领域的增长，你面临一个关键决策：**应该为每个实体创建一个仓储吗？**

每个新的业务需求都意味着需要在仓储中添加另一个方法。随着时间的推移，你最终会得到充满相似方法的类：

```csharp
public class ShipmentRepository
{
    public Task<List<Shipment>> GetShipmentsByOrder(int userId) { ... }
    public Task<List<Shipment>> GetCancelledPosts() { ... }
    public Task<List<Shipment>> GetDeliveredShipmentsByCategory(string category) { ... }
    public Task<List<Shipment>> GetRecentShipments(int daysBack) { ... }
    // ...还有更多方法！
}
```

要找到正确的方法变得越来越困难，甚至很难记住每个仓储中已经有哪些方法。

### 多实体场景的复杂性

当处理 `Shipments`、`ShipmentItems` 和 `Orders` 时，遵循传统方法会导致：

```csharp
public interface IShipmentRepository
{
    Task<ShipmentDto> GetByIdAsync(int id);
    Task<IEnumerable<ShipmentDto>> GetAllAsync();
    // ...
}

public interface IShipmentItemRepository
{
    Task<ShipmentItemDto> GetByIdAsync(int id);
    Task<IEnumerable<ShipmentItemDto>> GetByShipmentIdAsync(int shipmentId);
    // ...
}

public interface IOrderRepository
{
    Task<OrderDto> GetByIdAsync(int id);
    Task<IEnumerable<OrderDto>> GetByUserIdAsync(int userId);
    // ...
}
```

但当你需要一起获取相关实体时会发生什么？例如：

- 获取包含所有项目的发货单
- 获取订单及其关联的发货单
- 获取需要加载多个实体的发货历史数据

**这些跨实体方法应该放在哪里？**

许多开发者最终得到大量功能不足的仓储。当你实现新功能时，你会开始思考应该在 N 个仓储中的哪一个添加新方法。

### 常见的仓储理由辨析

我经常听到这些使用仓储的理由：

#### 1. "我们以后可能会切换数据库"

这是最常见的论点。但在生产环境中，你真的会多久切换一次数据库？

在 99% 的情况下，你不需要切换数据库。即使你从一个 SQL 数据库切换到另一个（例如，PostgreSQL → SQL Server），95% 以上的 EF Core 代码也不会改变。

如果你使用存储过程和触发器，数据库本身的重写工作会大得多（希望你不要使用它们）。

此外，从关系数据库切换到文档数据库意味着改变数据模型、查询和访问模式。你不能简单地交换仓储实现。

实际情况是：

- 从 SQL Server 切换到 PostgreSQL？EF Core 支持两者
- 切换到 Cosmos DB 或 MongoDB？那是数据访问逻辑的完全重写，而不仅仅是仓储的更改
- 因此，除非你正在积极构建多数据库抽象层（大多数应用程序不需要），否则这个理由站不住脚

#### 2. "它使测试更容易"

有些人认为模拟仓储比模拟 DbContext 更容易。但这隐藏了一个更大的问题：**你正在测试一个抽象的抽象**。

模拟仓储通常会导致脆弱的测试，这些测试无法反映真实的查询行为。例如，如果你模拟一个返回发货单的仓储方法，你不会测试 EF Core 如何将 LINQ 转换为 SQL，或如何处理加载子实体。

相反，最好使用真实的 EF Core 配合内存数据库，或者更好的做法是编写集成测试。

#### 3. "它强制关注点分离"

仓储通常在 N 层架构和整洁架构中使用，以保持业务层与 EF Core 解耦。但在实践中，这种分离造成的混乱比清晰度更多。

你从每个实体一个仓储开始。但随着功能的增长，你需要涉及多个实体的数据。现在你被迫：

- 在服务中注入多个仓储
- 或者将跨实体逻辑移入臃肿的仓储

结果不是清晰的分离，而是更多的间接层、更多的样板代码和更难理解的代码。

## 如何在没有仓储的情况下使用 EF Core

### EF Core 已经是仓储和工作单元

EF Core 的 DbContext 已经实现了仓储模式和工作单元模式，这在官方 DbContext 的代码摘要中有明确说明。

当我们在 EF Core 之上创建仓储时，我们是在创建一个抽象之上的抽象，导致过度工程化的解决方案。

DbContext 中的每个 `DbSet<TEntity>` 代表一个实体集合，就像典型的仓储一样。它允许你：

- 使用 LINQ 查询数据
- 添加、更新和删除实体
- 将数据投影到其他类型

当你需要查找订单的所有发货单时，你可以这样编写代码：

```csharp
var shipments = await dbContext.Shipments
    .Include(s => s.Items)
    .Where(s => s.OrderId == orderId)
    .ToListAsync();
```

这非常简单直接。你不需要仓储来查询这些数据。

如果你需要从几个用例中获取订单发货单怎么办？只需在几个地方复制这个简单的查询，这不是什么大问题。

但如果你有更复杂的查询呢？你总是可以将其提取为 `DbSet<Shipment>` 的扩展方法，并更方便地重用它：

```csharp
var shipments = await dbContext.Shipments
    .GetActiveShipmentsForOrder(orderId)
    .ToListAsync();
```

### 在服务或用例中注入 DbContext

与其注入 `IShipmentRepository`、`IShipmentItemRepository` 和 `IOrderRepository`，不如直接注入 DbContext。

```csharp
internal sealed class CreateShipmentCommandHandler(
    ShipmentsDbContext context,
    ILogger<CreateShipmentCommandHandler> logger)
    : IRequestHandler<CreateShipmentCommand, ErrorOr<ShipmentResponse>>
{
    public async Task<ErrorOr<ShipmentResponse>> Handle(
        CreateShipmentCommand request,
        CancellationToken cancellationToken)
    {
        var shipmentExists = await context.Shipments
            .AnyAsync(x => x.OrderId == request.OrderId, cancellationToken);

        if (shipmentExists)
        {
            return Error.Conflict("Shipment already exists");
        }

        var shipment = request.MapToShipment();
        await context.Shipments.AddAsync(shipment, cancellationToken);
        await context.SaveChangesAsync(cancellationToken);

        return shipment.MapToResponse();
    }
}
```

这段代码专注、可测试且易于理解。

## 在不同架构风格中使用 EF Core

### N 层架构中的直接使用

N 层架构仍然在代码库中非常流行。它围绕将职责分离到逻辑层，最常见的是：

- **表示层**：控制器、API 端点或 UI 组件
- **业务逻辑层（服务）**：封装业务规则的应用服务
- **数据访问层（仓储）**：数据持久化的抽象

在 N 层架构中，应用层应包含业务逻辑和用例。它应该协调工作流、执行策略并调用领域模型或基础设施。

以下是经典的 `ShipmentService` 实现示例：

```csharp
public sealed class ShipmentService(
    IShipmentRepository repository,
    ILogger<ShipmentServiceWithRepo> logger)
{
    public async Task<ErrorOr<ShipmentResponse>> CreateAsync(
        CreateShipmentCommand request,
        CancellationToken token = default)
    {
        var alreadyExists = await repository.ExistsForOrderAsync(request.OrderId, token);

        if (alreadyExists)
        {
            logger.LogInformation("Shipment for order '{OrderId}' already exists", request.OrderId);
            return Error.Conflict($"Shipment for order '{request.OrderId}' is already created");
        }

        var shipmentNumber = new Faker().Commerce.Ean8();
        var shipment = request.MapToShipment(shipmentNumber);

        await repository.AddAsync(shipment, token);
        await repository.SaveChangesAsync(token);

        logger.LogInformation("Created shipment: {@Shipment}", shipment);
        return shipment.MapToResponse();
    }
}
```

调用基础设施服务并不意味着你需要在仓储后面隐藏 EF Core。相反，你可以直接将 DbContext 注入应用服务或处理程序：

```csharp
public sealed class ShipmentService(
    ShipmentsDbContext context,
    ILogger<ShipmentService> logger)
{
    public async Task<ErrorOr<ShipmentResponse>> CreateAsync(
        CreateShipmentCommand request,
        CancellationToken token = default)
    {
        var shipmentAlreadyExists = await context.Shipments
            .AnyAsync(x => x.OrderId == request.OrderId, token);

        if (shipmentAlreadyExists)
        {
            logger.LogInformation("Shipment for order '{OrderId}' is already created", request.OrderId);
            return Error.Conflict($"Shipment for order '{request.OrderId}' is already created");
        }

        var shipmentNumber = new Faker().Commerce.Ean8();
        var shipment = request.MapToShipment(shipmentNumber);

        await context.Shipments.AddAsync(shipment, token);
        await context.SaveChangesAsync(token);

        logger.LogInformation("Created shipment: {@Shipment}", shipment);
        return shipment.MapToResponse();
    }
}
```

代码变得更难了吗？绝对不会。相反，这种方法会节省你的时间：

- 不需要每次都创建新的仓储方法
- 不需要在服务和仓储之间来回导航以查看完整实现

当你发现查询在多个地方重复使用时：

- 将查询提取到共享类或方法中
- 使用扩展方法、表达式扩展或规约模式（稍后会介绍）

### 整洁架构中的直接使用

整洁架构旨在将应用程序的关注点分离到不同的层，促进高内聚和低耦合。它包括以下层：

- **领域层**：包含核心业务对象，如实体
- **应用层**：业务用例的实现（类似于 N 层中的服务层）
- **基础设施层**：外部依赖项的实现，如数据库、缓存、消息队列、身份验证提供程序等
- **表示层**：与外部世界的接口实现，如 WebAPI、gRPC、GraphQL、MVC 等

但随着时间的推移，整洁架构已经演变成更加务实的方法：开发者同意他们可以在应用用例中直接使用 EF Core。

以下是当我们摆脱仓储时 `CreateShipmentCommandHandler` 的变化：

```csharp
internal sealed class CreateShipmentCommandHandler(
    ShipmentsDbContext context,
    ILogger<CreateShipmentCommandHandler> logger)
    : IRequestHandler<CreateShipmentCommand, ErrorOr<ShipmentResponse>>
{
    public async Task<ErrorOr<ShipmentResponse>> Handle(
        CreateShipmentCommand request,
        CancellationToken cancellationToken)
    {
        var shipmentAlreadyExists = await context.Shipments
            .AnyAsync(x => x.OrderId == request.OrderId, cancellationToken);

        if (shipmentAlreadyExists)
        {
            logger.LogInformation("Shipment for order '{OrderId}' is already created", request.OrderId);
            return Error.Conflict($"Shipment for order '{request.OrderId}' is already created");
        }

        var shipmentNumber = new Faker().Commerce.Ean8();
        var shipment = request.MapToShipment(shipmentNumber);

        await context.Shipments.AddAsync(shipment, cancellationToken);
        await context.SaveChangesAsync(cancellationToken);

        logger.LogInformation("Created shipment: {@Shipment}", shipment);
        var response = shipment.MapToResponse();

        return response;
    }
}
```

一些开发者会争辩："但整洁架构意味着我的应用层不应该依赖 EF Core！"

只有在你以最严格的方式解释时才是如此。在务实的整洁架构中，EF Core 不仅仅是"另一个 ORM"——它是你选择的持久化技术。

是的，你不需要仓储抽象来保持整洁架构的边界。通过直接使用 DbContext，你减少了样板代码，同时保持核心领域不受 EF 依赖的影响。

如果有一天你替换 EF Core，不仅仅是仓储需要重写——而是你的整个持久化逻辑。这就是为什么在应用用例中直接使用 EF Core 是一个权衡，它带来的优势大于劣势。

### 垂直切片架构中的直接使用

垂直切片架构专注于特性，而不是层。我相信整洁架构的自然演进，加上其特性文件夹，已经导致它转变为垂直切片架构。原始的整洁架构并不总是关于将解决方案分离到项目中，而是关于你的类及其关系。

要点是内层的类不能调用外层的类。使用垂直切片架构，你可以实现相同的目标，但项目更少。

我发现将整洁架构与垂直切片相结合是复杂应用程序的出色架构设计。在小型应用程序或没有复杂业务逻辑的应用程序中，你可以使用没有整洁架构的垂直切片。

作为核心，我使用整洁架构层并将它们与垂直切片相结合。层的修改如下：

- **领域层**：包含核心业务对象，如实体（保持不变）
- **基础设施层**：外部依赖项的实现，如数据库、缓存、消息队列、身份验证提供程序等（保持不变）
- **应用层和表示层**与垂直切片相结合

如果我们在整洁架构的应用用例中直接使用 EF Core，那么在垂直切片架构中本质上是相同的。

## 使用规约模式实现查询复用

上面提到的避免代码重复的选项之一是使用规约模式 (Specification Pattern)。

规约模式是一种使用小型、可重用的类（称为"规约"）来描述你想从数据库中获取什么数据的方法。每个规约代表一个可以应用于查询的过滤器或规则。这让你可以通过组合简单、易于理解的类来构建复杂的查询。

**规约模式带来以下好处：**

- **可重用性**：你可以编写一次规约，并在项目的任何地方使用它
- **组合性**：你可以组合两个或多个规约来创建更高级的查询
- **可测试性**：规约是 EF Core（或任何其他 ORM）之上的类，因此你可以用单元测试覆盖它们，或者更好的是，用集成测试
- **关注点分离**：你的查询逻辑与数据访问代码分离，这使事情保持整洁

与其在仓储中编写数十个方法，你可以随着需求的增长创建新的规约。然后你可以将这些规约传递给你的 DbContext（或者如果你仍然想使用仓储，也可以传递给仓储）。

以下是一个规约示例，它返回社交媒体应用程序中至少有 150 个点赞的病毒式帖子：

```csharp
public class ViralPostSpecification : Specification<Post>
{
    public ViralPostSpecification(int minLikesCount = 150)
    {
        AddFilteringQuery(post => post.Likes.Count >= minLikesCount);
        AddOrderByDescendingQuery(post => post.Likes.Count);
    }
}
```

你可以在代码的任何地方重用此规约来获取"病毒式"帖子。

你可能会想——创建规约有什么意义？这不是另一个额外的抽象层吗？

是的，但以下是规约可能有用的几种情况：

- 将常见的复杂查询提取到可重用的类中
- 将多个查询组合成单个查询

真正的力量在于允许根据输入数据动态组合多个规约。想象一下用户选择了几个预定义的过滤器，你可以使用 AND 或 OR 操作动态组合它们。

## 可测试性考虑

开发者为创建仓储提供的一个常见理由是可测试性。论点是："如果我将 EF Core 包装在仓储中，我可以在单元测试中模拟仓储。"

但现实是：

- 模拟仓储通常会导致与 EF Core 不匹配的虚假行为
- 你的测试变得脆弱且价值较低
- 你实际上没有测试查询，而这通常是最重要的部分

与其模拟，你应该编写真实的 EF Core 测试。

### 选项 1：使用 EF Core InMemory 提供程序

EF Core 有一个内存数据库提供程序，允许你在没有物理数据库的情况下运行测试。

```csharp
var options = new DbContextOptionsBuilder<ShipmentsDbContext>()
    .UseInMemoryDatabase("ShipmentsTestDb")
    .Options;

using var context = new ShipmentsDbContext(options);

// Arrange
context.Shipments.Add(new Shipment
{
    OrderId = Guid.NewGuid(),
    Address = "Berlin"
});
await context.SaveChangesAsync();

// Act
var shipment = await context.Shipments.FirstOrDefaultAsync();

// Assert
Assert.NotNull(shipment);
```

这很快，适用于许多类似单元测试的场景。但请记住，InMemory 提供程序的行为并不完全像关系数据库（例如，它不强制执行外键）。仅在简单场景中使用它。

### 选项 2：编写集成测试

这是我最喜欢的选项。编写与真实数据库交互的测试是确保应用程序按预期工作的最佳方法。

编写集成测试有两种主要方法：

- 测试应用程序的 WebAPI 调用
- 测试使用 EF Core DbContext 的类

在大多数情况下，第一个选项已经足够了。但你也可以直接使用 EF Core 测试复杂场景。

**为什么这比模拟仓储更好：**

- **模拟会撒谎**：它们不会复制 EF Core 的 LINQ 到 SQL 转换、急切加载或跟踪行为
- **真实的 EF Core 测试捕获真实问题**：如不正确的连接、错误的投影或缺失的 Include
- **集成测试覆盖更多**：确保不仅你的代码有效，而且你的数据库架构也是正确的

通过直接使用 EF Core 进行测试，你不会失去可测试性——你实际上**获得了可靠性**。

## 什么时候仍然需要自定义仓储

到目前为止，我们认为大多数时候你不需要 EF Core 的仓储。但像每个规则一样，也有例外。

以下是自定义仓储可能有意义的情况：

### 1. 在多个地方使用的非常复杂的查询

如果你有一个跨多个聚合的查询，涉及大量过滤、排序或连接——并且在许多特性中使用——将其包装到仓储方法中可以减少重复并集中逻辑。

### 2. 团队约定或项目约束

在某些组织中，架构指南严格要求仓储以保持一致性。即使可以直接使用 EF Core，遵循团队商定的约定可能是务实的选择。

### 3. 横切基础设施关注点

有时，你希望用额外的行为装饰仓储，例如缓存、日志记录或审计。虽然这些也可以通过拦截器或中间件解决，但在你的上下文中，仓储包装器可能是最简单的方法。

### 4. 外部集成

如果你的项目查询多个数据源（例如，EF Core、外部 API 和遗留数据库），仓储可以充当门面，将这些源统一在单个抽象后面。

### 5. 使用 Dapper 时

使用 Dapper 时，仓储是必不可少的，因为它们从应用程序的其余部分抽象了 SQL。

在这些情况下，仓储服务于特定目的。但为每个实体创建仓储——仅仅因为"我们一直这样做"——只会导致臃肿和样板代码。

## 总结

让我们回顾关键要点：

- **EF Core 已经实现了仓储和工作单元**：`DbSet<TEntity>` 是你的仓储，`DbContext.SaveChangesAsync()` 是你的工作单元
- **仓储通常会增加不必要的复杂性**：它们导致臃肿的仓储、太多小仓储或跨服务的重复查询
- **在应用服务、处理程序或垂直切片中直接使用 EF Core**：这使你的代码更简单、更专注、更易于维护
- **使用规约模式实现查询复用**：它避免了重复并保持复杂查询的可组合性
- **没有仓储的测试效果很好**：使用 EF Core InMemory 或集成测试——而不是模拟仓储
- **仓储仍有小众用途**：对于共享的复杂查询、横切关注点或多源数据访问，仓储可能很有用

在现代 .NET 应用程序中，在应用层或垂直切片中直接使用 EF Core 通常是最干净、最简单、最务实的选择。

仓储并没有死——但它们不再是默认选择。只有在它们真正增加价值时才使用它们。

没有一种正确的软件编写方式；你需要选择在每个特定项目和情况下最有效的方法。
