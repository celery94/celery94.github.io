---
pubDatetime: 2024-04-01
tags: [".NET", "C#", "NewId", "Unique ID", "Sortable Unique ID"]
source: https://code-maze.com/dotnet-generate-sortable-unique-ids-with-the-newid-library/
author: Ivan Gechev
title: 使用 NewId 库在 .NET 中生成可排序的唯一ID
description: 在本文中，我们将探讨为什么我们在 .NET 中可能需要可排序的唯一ID，以及如何使用 NewId NuGet 包来创建它们。
---

> ## 摘要
>
> 在本文中，我们将探讨为什么我们在 .NET 中可能需要可排序的唯一ID，以及如何使用 NewId NuGet 包来创建它们。
>
> 原文 [Generate Sortable Unique IDs With the NewId Library in .NET](https://code-maze.com/dotnet-generate-sortable-unique-ids-with-the-newid-library/) 由 Ivan Gechev 撰写。

---

在本文中，我们将探讨为什么我们在 .NET 中可能需要可排序的唯一ID，以及如何使用 NewId NuGet 包来创建它们。

要下载本文的源代码，您可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/dotnet-client-libraries/GenerateUniqueIDsWithNewId)。

## 为什么我们在 .NET 中需要可排序的唯一ID

我们都知道，生成项目中实体的ID有两种主要方法：要么是 `int`，要么是 `Guid`（全局唯一标识符）值。但这两种方法都有它们的问题。让我们在一个处理客户订单的 API 中探讨一下。

### 整数作为主键

首先，让我们看看整数作为主键：

```csharp
public class Order
{
    public int Id { get; set; }
    public required string CustomerName { get; set; }
    public required IEnumerable<string> Products { get; set; }
    public required decimal TotalAmount { get; set; }
}
```

我们创建了一个 `Order` 类并使用 `int` 作为ID。

采用这种方法，我们将ID生成工作交给数据库提供商。好处是我们得到了短小、美观、连续的ID。但，使用数据库生成的主键，我们遇到一个主要缺点 —— 我们的应用程序变得更难扩展。**处理大量的插入语句迫使我们的数据库不断使用锁来处理生成新的主键。**

在几个不同的数据库中存储实体并维护唯一的 `int` ID也几乎是不可能的。另外，我们可能会向我们的竞争对手泄露敏感信息 - 我们是否希望拥有连续的ID并让别人确切知道我们有多少订单？

### 全局唯一标识符作为主键

另一种流行的方法是使用 `Guid` 值：

```csharp
public class OrderService(IUnitOfWork unitOfWork) : IOrderService
{
    public async Task<OrderDto> CreateAsync(
        OrderForCreationDto orderForCreationDto,
        CancellationToken cancellationToken = default)
    {
        var order = new Order
        {
            Id = Guid.NewGuid(),
            CustomerName = orderForCreationDto.CustomerName,
            Products = orderForCreationDto.Products,
            TotalAmount = orderForCreationDto.TotalAmount,
        };
        unitOfWork.OrderRepository.Insert(order);
        await unitOfWork.SaveChangesAsync(cancellationToken);
        return new OrderDto
        {
            Id = order.Id,
            CustomerName = order.CustomerName,
            Products = order.Products,
            TotalAmount = order.TotalAmount,
        };
    }
    // 省略以简洁
}
```

我们首先将 `Order` 的标识从 `int` 变更为 `Guid`，然后我们创建了 `OrderService` 类。我们的项目基于 [Onion 架构](https://code-maze.com/onion-architecture-in-aspnetcore/)，所以我们的服务使用一个 Dto 对象，处理它，并使用仓库将实体插入数据库。

采用这种方法，`OrderService` 类负责生成主键值。最大的好处在于我们可以使用 `Guid.NewGuid()` 轻松获得唯一ID。拥有唯一但随机的ID使我们的应用扩展到几个数据库变得非常容易。但这也是它们最大的问题：它使我们的数据基于主键单独排序变得不可能，并可能导致潜在的索引问题。**这种类型的主键在数据库中存储时也会占用四倍于常规整数的空间。**

**这就是 [NewId](https://github.com/phatboyg/NewId) 库发挥作用的地方。**通过使用它，我们结合了 `int` 和 `Guid` 主键的优点，同时消除了一些缺点。

## NewId 库是什么

**NewId 库是一个 NuGet 包，我们可以用它来生成唯一但可排序的ID。** 它基于现已退役的 Snowflake：X（前 Twitter）内部服务，用于生成可排序的唯一主键。NewId 是分布式应用框架 **MassTransit** 的一部分，旨在解决 `int` 和 `Guid` 标识符存在的问题。其目的是提供一种在大规模下生成唯一且可排序ID的方法。

**该包基于三个事物生成ID - 时间戳、工作ID和进程ID。**这样我们最终得到的是虽然唯一但仍可排序的ID，并且当我们的应用和数据库有多个实例时不会发生冲突。

这个材料对你有用吗？考虑订阅并免费获取 **ASP.NET Core Web API 最佳实践** 电子书！

在我们开始生成ID之前，我们需要安装 `NewId` 包：

```bash
dotnet add package NewId
```

使用 `dotnet add package` 命令，我们安装了这个库。

现在我们已经准备好了，让我们开始使用这个包来生成ID。

要生成我们的可排序唯一ID，我们需要使用 `NewId` 类。它位于 `MassTransit` 命名空间中，有三个方法。

首先是 `Next()` 方法 - 生成一个新的 `NewId` 类实例：

```plaintext
00070000-ac11-0242-3d9b-08dc45bed613
00070000-ac11-0242-c9d3-08dc45bed614
00070000-ac11-0242-cafd-08dc45bed614
00070000-ac11-0242-cb2e-08dc45bed614
00070000-ac11-0242-cb69-08dc45bed614
```

接下来，`NextGuid()` 方法 - 生成一个新的 `Guid` 值：

```plaintext
00070000-ac11-0242-df20-08dc45bed614
00070000-ac11-0242-0c11-08dc45bed615
00070000-ac11-0242-0d30-08dc45bed615
00070000-ac11-0242-0d46-08dc45bed615
00070000-ac11-0242-0d58-08dc45bed615
```

最后，`NextSequentialGuid()` 方法 - 生成一个新的顺序 `Guid` 值：

```plaintext
08dc45be-d615-19b5-0242-ac1100070000
08dc45be-d615-1b01-0242-ac1100070000
08dc45be-d615-1b46-0242-ac1100070000
08dc45be-d615-1b66-0242-ac1100070000
08dc45be-d615-1ba4-0242-ac1100070000
```

我们可以看到，使用 `Next()` 和 `NextGuid()` 方法，我们得到相同的模式，其中 `NextSequentialGuid()` 方法有稍微不同的模式。后两种方法返回一个 `Guid` 值，我们的类不需要修改，但如果我们选择 `Next()` 方法，我们将需要更改我们 `Order` 类的ID类型。

让我们使用其中一个：

```csharp
public class OrderService(IUnitOfWork unitOfWork) : IOrderService
{
    public async Task<OrderDto> CreateAsync(
        OrderForCreationDto orderForCreationDto,
        CancellationToken cancellationToken = default)
    {
        var order = new Order
        {
            Id = NewId.NextSequentialGuid(),
            CustomerName = orderForCreationDto.CustomerName,
            Products = orderForCreationDto.Products,
            TotalAmount = orderForCreationDto.TotalAmount,
        };
        unitOfWork.OrderRepository.Insert(order);
        await unitOfWork.SaveChangesAsync(cancellationToken);
        return new OrderDto
        {
            Id = order.Id,
            CustomerName = order.CustomerName,
            Products = order.Products,
            TotalAmount = order.TotalAmount,
        };
    }
    // 省略以简洁
}
```

在我们的 `OrderService` 类中，我们生成ID的地方，我们用 `NewId.NextSequentialGuid()` 方法替换了 `Guid.NewGuid()` 方法。这是我们唯一需要做的改变。

让我们运行我们的 API 并添加一些订单：

```json
[
  {
    "id": "08dc45c0-b5b5-0d5d-5811-22b038790000",
    "customerName": "Marcel Waters",
    "products": ["Piano"],
    "totalAmount": 599.99
  },
  {
    "id": "08dc45c0-d6f4-fbed-5811-22b038790000",
    "customerName": "Elizabeth Doyle",
    "products": ["Vase", "Mirror", "Blanket"],
    "totalAmount": 49.39
  },
  {
    "id": "08dc45c0-f143-a9f9-5811-22b038790000",
    "customerName": "Rayford Lopez",
    "products": ["Headphones", "Microphone"],
    "totalAmount": 86.06
  }
]
```

我们可以看到，我们的实体现在拥有唯一但不完全随机的标识符，这些标识符可以排序。

## 何时不应使用 NewId 库生成可排序的唯一ID

虽然 NewId 库为我们提供了生成可排序唯一ID的便利，但在一些场景下我们应该避免使用它们。**至关重要的是要记住，我们生成的ID具有一定程度的可预测性**。当你知道它们的创建算法时，它们可以被猜测。

因此，当不可预测性和安全性至关重要时，最好不要使用 NewId 生成的ID。**我们不应该在需要高度保密性的敏感信息如密码、安全令牌或任何其他数据上使用这样的ID**。如果我们在这样的场景下依赖 NewId 库，我们可能会危及我们应用程序的安全。这可能会使它们暴露于漏洞和未经授权的访问中。因此，当我们的应用程序在安全上有重要需求时，需要格外小心。

## 结论

在本文中，我们探讨了在作为主键时，整数和全局唯一标识符的限制，以及需要一种新方法的原因。NewId NuGet 包为我们提供了一个解决方案，提供了基于时间戳、工作ID和进程ID组合的唯一、可排序的ID。通过使用 NewId 库，我们获得了 int 和 Guid 主键的好处，同时减少了它们的缺点。这使我们能够轻松实现可扩展性、有效的索引，并提高我们的数据组织。所有这些最终增强了我们的应用程序的健壮性和功能。
