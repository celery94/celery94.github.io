---
pubDatetime: 2025-11-07
title: 90% 的 API 并非真正的 RESTful：你缺失了什么以及何时它真正重要
description: 深入探讨 REST 架构约束、HATEOAS 原则及其在现代 API 设计中的实际应用。了解 Richardson 成熟度模型，掌握在 ASP.NET Core 中实现超媒体控制的最佳实践，以及何时应该（或不应该）采用 HATEOAS。
tags: [".NET", "API Design", "REST", "HATEOAS", "ASP.NET Core", "Architecture"]
slug: 90-percent-apis-not-restful-what-missing-when-matters
source: https://antondevtips.com/blog/90-of-apis-are-not-restful-what-youre-missing-and-when-it-matters
---

## 引言

在日常开发中，你可能已经构建了数十个自称为"RESTful"的 API。你正确使用了 HTTP 方法，合理组织了 URL 结构，并返回了 JSON 响应。但真相是：如果你的 API 不包含超媒体链接（hypermedia links），它就不是真正的 RESTful。

**HATEOAS**（Hypermedia as the Engine of Application State，超媒体作为应用程序状态引擎）是 REST 中最容易被误解和最常被跳过的约束。没有它，前端客户端会与 API 结构紧密耦合，硬编码 URL，并重复实现业务逻辑来判断哪些操作可用。

本文将深入探讨为什么大多数 API 忽略 HATEOAS，它在实践中如何工作，以及何时应该投入精力来正确实现它。

我们将探讨以下内容：

- REST 的本质及其六大架构约束
- Richardson 成熟度模型的四个层级
- 为什么 90% 的 API 停留在第二层级
- 在 ASP.NET Core 中实现 HATEOAS 的完整示例
- 前端应用如何利用超媒体控制
- HATEOAS 何时有价值——以及何时不值得投入

## REST 的本质与六大架构约束

### REST 不是协议而是架构风格

REST（Representational State Transfer，表现层状态转移）不是协议或标准，而是 Roy Fielding 在其博士论文中提出的一种架构风格。REST 的设计目的是利用使万维网成功的架构原则。

Web 之所以有效，是因为它是解耦的、可扩展的，而且客户端（浏览器）不需要预先知道每个网站的完整结构。浏览器只需跟随链接即可。REST 将这一原则应用到 API 设计中。

当你构建一个 RESTful API 时，你不仅仅是在创建返回数据的端点，而是在构建一个系统，其中服务器引导客户端完成可用的操作，就像网站通过可点击的链接引导你一样。

### REST 的六大架构约束

要使 API 真正符合 REST 规范，它必须遵循以下六个架构约束：

#### 1. 客户端-服务器架构（Client-Server Architecture）

客户端和服务器是分离的。客户端处理用户界面和用户状态，而服务器管理数据存储和业务逻辑。这种分离允许双方独立演进。只要维持契约不变，你可以更新后端实现而不会破坏客户端。

这种架构模式带来了明确的关注点分离。前端团队可以专注于用户体验，后端团队可以优化性能和数据处理，双方不会相互干扰。

#### 2. 无状态（Stateless）

来自客户端的每个请求必须包含理解和处理该请求所需的所有信息。服务器不在请求之间存储客户端上下文。无状态性使 API 更具可扩展性，因为任何服务器实例都可以处理任何请求，而无需知道之前发生了什么。

无状态设计简化了水平扩展。你可以在负载均衡器后添加更多服务器实例，而无需担心会话亲和性或状态同步问题。每个请求都是自包含的，携带了认证令牌、过滤条件和其他必要的上下文信息。

#### 3. 可缓存（Cacheable）

响应必须明确指示它们是否可以被缓存。你可以使用 HTTP 头如 `Cache-Control`、`ETag` 和 `Last-Modified` 来告诉客户端和中间件（如 CDN）哪些内容可以缓存以及缓存多长时间。

适当的缓存策略可以显著减少服务器负载并改善用户体验。对于很少变化的资源，可以设置较长的缓存时间；对于频繁更新的数据，可以使用条件请求和 ETag 来验证缓存的新鲜度。

#### 4. 统一接口（Uniform Interface）

这是使 REST 区别于其他架构风格的基本约束。它包含四个子约束：

**资源标识（Resource Identification）**：资源通过 URI 标识。资源可以是任何可命名的概念——用户、订单、产品等。

**通过表示操作资源（Resource Manipulation Through Representations）**：当你收到资源表示（如 JSON）时，它包含足够的信息来修改或删除该资源。

**自描述消息（Self-Descriptive Messages）**：每条消息包含足够的信息来描述如何处理它。HTTP 方法（GET、POST、PUT、DELETE）告诉你操作类型，`Content-Type` 头告诉你格式。

**超媒体作为应用程序状态引擎（HATEOAS）**：响应应该包含指向相关操作和资源的链接，引导客户端了解接下来可以做什么。这是本文的核心主题。

#### 5. 分层系统（Layered System）

客户端不应该能够区分它是直接连接到终端服务器还是连接到中间件。你可以在不让客户端知道的情况下添加负载均衡器、缓存或 API 网关。这个约束通过允许你在多个服务器之间分布服务来实现可扩展性。

分层架构还增强了安全性和灵活性。你可以在应用层前添加 WAF（Web 应用防火墙），在数据库前添加缓存层，或者引入 API 网关来处理认证、限流和转换，而客户端完全无感知。

#### 6. 按需代码（Code on Demand）——可选

这是唯一的可选约束。服务器可以通过传输可执行代码（如 JavaScript）来扩展客户端功能。大多数 API 不使用这个约束，这完全可以接受。

这个约束在现代单页应用中其实无处不在——服务器提供 JavaScript bundle，客户端下载并执行。但在 API 设计中，这个约束很少被显式利用。

## Richardson 成熟度模型：衡量 REST 成熟度的四个层级

在实践中，我们需要一种方法来衡量 API 与真正 RESTful 的接近程度。Leonard Richardson 创建了一个成熟度模型，将 REST 采用分解为四个层级。

### Level 0：POX 沼泽（The Swamp of POX - Plain Old XML）

在这个层级，你只是将 HTTP 用作传输机制，仅此而已。你有一个单一的 URI 端点，通常只使用 POST 请求，请求体包含关于要执行什么操作的所有信息。这本质上是通过 HTTP 进行的 RPC（远程过程调用）。SOAP API 通常在这个层级运行。

端点示例：`/api/service`

所有操作通过请求体中的不同参数来区分。这种方法没有利用 HTTP 协议的任何语义，只是把它当作隧道。

### Level 1：资源（Resources）

在这个层级，你开始将单一端点分解为多个基于资源的 URI。不再是一个端点处理所有事情，而是为不同的资源使用不同的 URI。

端点示例：

- `/api/orders`
- `/api/customers`
- `/api/products`

这是向 RESTful 设计迈出的第一步。你开始以名词（资源）而非动词（操作）来思考 API 结构。每个资源都有自己的 URI 空间。

### Level 2：HTTP 动词（HTTP Verbs）

现在你正确使用 HTTP 方法了。GET 用于检索数据，POST 用于创建，PUT 用于更新，DELETE 用于删除。你还有意义地使用 HTTP 状态码。

端点示例：

- `GET /api/orders/123` - 检索订单
- `POST /api/orders` - 创建新订单
- `PUT /api/orders/123` - 更新订单
- `DELETE /api/orders/123` - 删除订单

正确的状态码：200 OK、201 Created、404 Not Found 等。

大多数自称 RESTful 的 API 都处于这个层级。你正确使用资源、HTTP 方法和状态码。你的 API 是可预测的，遵循 Web 标准。但你仍然缺少最后一块拼图。

### Level 3：超媒体控制（HATEOAS）

这才是真正的 REST。你的 API 响应包含指向相关资源和可用操作的链接。客户端不需要预先知道你的 URL 结构。服务器告诉客户端接下来可以做什么。

当订单处于"待处理"状态时，响应可能包含"付款"和"取消"的链接。当订单已支付时，响应包含"发货"的链接。客户端只需检查链接是否存在，就知道哪些操作可用，而无需实现复杂的业务规则。

## 为什么 90% 的 API 停留在 Level 2

大多数 API 止步于 Level 2，而且效果不错。这些 API 是可预测的，遵循 HTTP 标准，开发者知道如何构建它们。

但达到 Level 3 需要：

1. **更多的实现工作**：为每个响应生成链接需要额外的代码、维护和测试。
2. **更大的响应负载**：每个响应都会变大，因为你要包含链接对象。当返回 100 个订单的列表时，现在为每个订单都包含链接。响应大小显著增长。对于慢速网络上的移动应用，这很重要。对于高流量 API，带宽成本会增加。
3. **没有标准格式**：与 HTTP 方法或状态码不同，超媒体没有单一标准。这种标准化的缺乏意味着每个团队都发明自己的方法，使客户端开发者更难学习和采用。
4. **客户端复杂性**：你的前端现在需要解析链接并使用它们，而不是硬编码的 URL。
5. **感觉像过度工程**：当你在交付功能时，HATEOAS 感觉像过度工程。为什么在硬编码 URL 效果良好时增加复杂性？HATEOAS 的好处稍后出现，在维护和演进期间。但截止日期就在眼前。
6. **内部 API 不需要它**：如果你控制前端和后端，同时部署它们，为什么要费心处理超媒体？你可以同时更新双方。

### 跳过 HATEOAS 的代价

跳过 HATEOAS 看起来很实用，直到你遇到这些问题：

#### 1. 紧耦合

你的前端硬编码 URL 如 `/orders/123/payment`。当你重构并将付款移动到 `/payments?orderId=123` 时，每个客户端都会中断。

你需要版本化 API，维护旧端点，或者协调所有客户端的同步更新。对于公共 API 或多个团队使用的内部 API，这变成了噩梦。

#### 2. 重复的业务逻辑

你的后端知道订单只有在尚未发货时才能被取消。但你的前端也实现了这个检查来适当地隐藏"取消"按钮。

现在你在两个地方有相同的业务规则。当规则改变时，你更新两者。当你忘记时，用户看到触发 403 Forbidden 错误的按钮。这不仅是糟糕的用户体验，还是维护负担。

#### 3. 可发现性差

加入项目的新开发者需要全面的文档来了解每个资源在每个状态下可能的操作。使用 HATEOAS，他们可以通过跟随链接来探索。API 告诉他们什么是可能的。

理论讲够了，让我们看看 HATEOAS 在实践中如何工作。

## 在 ASP.NET Core 中实现 HATEOAS

我们将在 ASP.NET Core 中构建一个实现 HATEOAS 的订单 API。

### 定义链接模型

首先，我们需要一种表示超媒体链接的方法。这是我们的 `LinkResponse` 模型：

```csharp
public record LinkResponse
{
    public required string Href { get; init; }
    public required string Rel { get; init; }
    public required string Method { get; init; }
}
```

每个链接告诉客户端：

- `Href`：发送请求的位置
- `Rel`：这个链接代表什么（关系类型，如"self"、"update"、"delete"）
- `Method`：使用哪个 HTTP 方法

### 创建链接生成服务

接下来，我们需要一种生成链接的方法。这是 `LinkService`：

```csharp
public sealed class LinkService(
    LinkGenerator linkGenerator,
    IHttpContextAccessor httpContextAccessor)
{
    public LinkResponse Create(
        string endpointName,
        string rel,
        string method,
        object? values = null,
        string? controller = null)
    {
        var href = linkGenerator.GetUriByAction(
            httpContextAccessor.HttpContext!,
            endpointName,
            controller,
            values);

        return new LinkResponse
        {
            Href = href ?? throw new InvalidOperationException("Invalid endpoint name provided"),
            Rel = rel,
            Method = method
        };
    }
}
```

这个服务使用 ASP.NET Core 的 `LinkGenerator` 基于操作名称创建 URL。当你重命名路由时，链接会自动更新。这是一个关键优势——你不必在代码中散布字符串常量。

### 在响应模型中包含链接

我们的响应模型需要携带链接。这是 `OrderResponse`：

```csharp
public record OrderResponse
{
    public required Guid Id { get; init; }
    public required string OrderNumber { get; init; }
    public Guid? CustomerId { get; init; }
    public required DateTime OrderDate { get; init; }
    public required decimal TotalAmount { get; init; }
    public required OrderStatus Status { get; init; }
    public DateTime? ShippedDate { get; init; }
    public string? ShippingAddress { get; init; }
    public required List<OrderItemResponse> Items { get; init; }
    public List<LinkResponse> Links { get; set; } = [];
}
```

`Links` 属性保存此订单的所有可用操作。它开始时是空的，我们根据订单的当前状态填充它。

### 在控制器中生成链接

现在来到有趣的部分。让我们看看 `OrdersController` 如何包含链接：

```csharp
[HttpGet(OrdersRouteConsts.GetOrderById)]
public async Task<IActionResult> GetOrderById(
    Guid id,
    GetOrderByIdHandler handler,
    LinkService linkService,
    CancellationToken cancellationToken)
{
    var response = await handler.HandleAsync(id, cancellationToken);
    
    if (response is null)
    {
        return NotFound();
    }

    response.Links = [
        linkService.Create(nameof(GetOrderById), "self", HttpMethods.Get, new { id }),
        linkService.Create(nameof(CreateOrder), "create", HttpMethods.Post),
        linkService.Create(nameof(UpdateOrder), "update", HttpMethods.Put, new { id }),
        linkService.Create(nameof(DeleteOrder), "delete", HttpMethods.Delete, new { id }),
        linkService.Create(nameof(OrderItemsController.AddItemToOrder), "add-item", 
            HttpMethods.Post, new { orderId = id }, 
            nameof(OrderItemsController).Replace("Controller", ""))
    ];

    return Ok(response);
}
```

每次返回订单时，我们都包含以下链接：

- `self`：再次获取此订单
- `create`：创建新订单
- `update`：更新此订单
- `delete`：删除此订单
- `add-item`：向此订单添加项目

我们引用操作名称如 `nameof(UpdateOrder)`。如果我们重构路由结构，链接保持正确。

### 处理订单项

这是我们如何处理订单项的：

```csharp
[HttpGet(OrderItemsRouteConsts.GetOrderItemById)]
public async Task<IActionResult> GetOrderItemById(
    Guid orderId,
    Guid itemId,
    GetOrderItemByIdHandler handler,
    LinkService linkService,
    CancellationToken cancellationToken)
{
    var response = await handler.HandleAsync(orderId, itemId, cancellationToken);
    
    if (response is null)
    {
        return NotFound();
    }

    response.Links = [
        linkService.Create(nameof(GetOrderItemById), "self", 
            HttpMethods.Get, new { orderId, itemId }),
        linkService.Create(nameof(UpdateOrderItem), "update", 
            HttpMethods.Put, new { orderId, itemId }),
        linkService.Create(nameof(DeleteOrderItem), "delete", 
            HttpMethods.Delete, new { orderId, itemId })
    ];

    return Ok(response);
}
```

每个订单项都获得查看、更新或删除自身的链接。

### 示例响应

当客户端调用 `GET /orders/123` 时，他们会收到如下 JSON：

```json
{
  "id": "7c533935-ee09-4435-9c00-2a68df13fbca",
  "orderNumber": "ORD-2025-001-UPDATED",
  "customerId": "f09f4e75-8a6d-4640-9893-c96050883b2b",
  "orderDate": "2025-10-14T17:41:11.868504Z",
  "totalAmount": 349.97,
  "status": 1,
  "shippedDate": "2025-01-15T10:30:00Z",
  "shippingAddress": "456 Oak Ave, Los Angeles, CA 90001",
  "items": [],
  "links": [
    {
      "href": "https://localhost:7023/orders/7c533935-ee09-4435-9c00-2a68df13fbca",
      "rel": "self",
      "method": "GET"
    },
    {
      "href": "https://localhost:7023/orders",
      "rel": "create",
      "method": "POST"
    },
    {
      "href": "https://localhost:7023/orders/7c533935-ee09-4435-9c00-2a68df13fbca",
      "rel": "update",
      "method": "PUT"
    },
    {
      "href": "https://localhost:7023/orders/7c533935-ee09-4435-9c00-2a68df13fbca",
      "rel": "delete",
      "method": "DELETE"
    },
    {
      "href": "https://localhost:7023/orders/7c533935-ee09-4435-9c00-2a68df13fbca/items",
      "rel": "add-item",
      "method": "POST"
    }
  ]
}
```

客户端不需要知道你的 URL 结构。他们需要的一切都在响应中。

### 基于状态的链接生成

目前，我们无论订单状态如何都包含所有可能的操作。但这就是 HATEOAS 变得有用的地方：你根据资源的当前状态有条件地包含链接。

这是如何增强 `GetOrderById` 方法以考虑订单状态：

```csharp
response.Links = [
    linkService.Create(nameof(GetOrderById), "self", HttpMethods.Get, new { id })
];

// 只有订单处于待处理状态时才允许更新
if (response.Status == OrderStatus.Pending)
{
    response.Links.Add(linkService.Create(nameof(UpdateOrder), "update", 
        HttpMethods.Put, new { id }));
    response.Links.Add(linkService.Create(nameof(DeleteOrder), "cancel", 
        HttpMethods.Delete, new { id }));
}

// 只有订单已支付时才允许发货
if (response.Status == OrderStatus.Paid)
{
    response.Links.Add(linkService.Create(nameof(ShipOrder), "ship", 
        HttpMethods.Post, new { id }));
}

// 除非已发货或已取消，否则始终允许添加项目
if (response.Status != OrderStatus.Shipped && response.Status != OrderStatus.Cancelled)
{
    response.Links.Add(linkService.Create(nameof(OrderItemsController.AddItemToOrder), 
        "add-item", HttpMethods.Post, new { orderId = id }, 
        nameof(OrderItemsController).Replace("Controller", "")));
}
```

现在你的 API 充当应用程序状态的引擎。后端编码关于什么是可能的业务规则，前端只需渲染它收到的内容。

## 前端应用使用 HATEOAS

### 传统方式 vs HATEOAS 方式

没有 HATEOAS，你的前端代码看起来像这样：

```javascript
// 前端重复业务逻辑
if (order.status === 'Pending') {
    showUpdateButton();
    showCancelButton();
} else if (order.status === 'Paid') {
    showShipButton();
}
```

使用 HATEOAS，你的前端变成这样：

```javascript
// 前端只检查链接
if (order.links.find(l => l.rel === 'update')) {
    showUpdateButton();
}

if (order.links.find(l => l.rel === 'ship')) {
    showShipButton();
}
```

当业务规则改变时（例如，你决定已支付的订单仍然可以在 24 小时内更新），你只需更改后端。前端继续工作而无需任何代码更改。

关键原则：你的前端不硬编码 URL 或重复业务逻辑。它查找链接并根据可用的内容渲染 UI。

### React 中的实现示例

让我们探讨如何在 React 前端应用中渲染 `OrderItemRow`：

```tsx
// components/OrderItemRow.tsx
import React from 'react';
import { OrderItem } from '../types/api';
import { hasLink, findLink } from '../utils/linkHelper';
import { apiClient } from '../services/apiClient';

interface OrderItemRowProps {
    item: OrderItem;
    onUpdate: () => void;
}

export const OrderItemRow: React.FC<OrderItemRowProps> = ({ item, onUpdate }) => {
    const handleUpdateQuantity = async () => {
        const updateLink = findLink(item.links, 'update');
        if (!updateLink) return;

        const newQuantity = prompt('Enter new quantity:', item.quantity.toString());
        if (!newQuantity) return;

        try {
            await apiClient.followLink(updateLink, {
                quantity: parseInt(newQuantity),
            });
            onUpdate();
        } catch (err) {
            alert('Failed to update item');
        }
    };

    const handleDelete = async () => {
        const deleteLink = findLink(item.links, 'delete');
        if (!deleteLink) return;

        if (!confirm('Remove this item?')) return;

        try {
            await apiClient.followLink(deleteLink);
            onUpdate();
        } catch (err) {
            alert('Failed to remove item');
        }
    };

    return (
        <div className="order-item-row">
            <div className="item-info">
                <span className="product-name">{item.productName}</span>
                <span className="quantity">Qty: {item.quantity}</span>
                <span className="price">${item.unitPrice.toFixed(2)}</span>
                <span className="total">${item.lineTotal.toFixed(2)}</span>
            </div>
            <div className="item-actions">
                {hasLink(item.links, 'update') && (
                    <button onClick={handleUpdateQuantity}>Update</button>
                )}
                {hasLink(item.links, 'delete') && (
                    <button onClick={handleDelete}>Remove</button>
                )}
            </div>
        </div>
    );
};
```

### 使用自定义 Hook 简化代码

你可以使用自定义 Hook 使代码更简洁：

```tsx
// hooks/useHateoas.ts
import { Link } from '../types/api';
import { useMemo } from 'react';

export const useHateoas = (links: Link[]) => {
    const linkMap = useMemo(() => {
        return links.reduce((acc, link) => {
            acc[link.rel] = link;
            return acc;
        }, {} as Record<string, Link>);
    }, [links]);

    const hasAction = (rel: string): boolean => {
        return rel in linkMap;
    };

    const getLink = (rel: string): Link | undefined => {
        return linkMap[rel];
    };

    return { hasAction, getLink, links };
};
```

现在你的组件变得更简单：

```tsx
export const OrderDetail: React.FC<OrderDetailProps> = ({ orderId }) => {
    const [order, setOrder] = useState<Order | null>(null);
    const { hasAction, getLink } = useHateoas(order?.links || []);

    // ... 其他代码 ...

    return (
        <div className="order-actions">
            {hasAction('update') && (
                <button onClick={handleUpdate}>Update Order</button>
            )}
            {hasAction('delete') && (
                <button onClick={handleDelete}>Cancel Order</button>
            )}
            {hasAction('ship') && (
                <button onClick={handleShip}>Ship Order</button>
            )}
        </div>
    );
};
```

你的前端变得更简单。它说"如果有更新链接，显示更新按钮"，而不是"如果状态是 X 或 Y，显示更新按钮"。业务逻辑存在于它应该在的地方：在后端。前端专注于呈现和用户交互。

当你添加新操作时，你在后端添加新链接，在前端添加新按钮检查。你不需要跨多个代码库同步复杂的状态机。

这就是"超媒体作为应用程序状态引擎"在实践中的实际含义。API 驱动什么是可能的。UI 相应地响应。

## HATEOAS 何时有价值——以及何时没有

我们已经看到了 HATEOAS 如何工作以及如何实现它。现在让我们诚实地谈谈它何时值得投入，何时最好跳过它。

HATEOAS 不是灵丹妙药。像任何架构决策一样，它伴随着权衡。让我们探讨两面。

### HATEOAS 有价值的场景

#### 1. 具有多种客户端类型的公共 API

如果你正在构建一个被 Web 应用、移动应用和第三方集成消费的公共 API，HATEOAS 表现出色。不同的客户端可以跟随不同的链接。链接让你可以在不破坏客户端的情况下演进 API。移动应用可能会运行旧版本数月之久。

使用 HATEOAS，你可以逐步引入新端点，弃用旧端点，而不会强制所有客户端立即更新。客户端可以在可用时跟随新链接，在不可用时优雅降级。

#### 2. 复杂的工作流系统

当你的领域涉及具有许多可能转换的复杂状态机时，HATEOAS 保持逻辑集中。关于状态转换的业务规则存在于后端。前端不重复复杂的条件逻辑。规则可以在不更新前端的情况下改变。

例如，电子商务订单工作流、审批流程或文档管理系统都可以从 HATEOAS 中获益。在每个状态下可用的操作可能会根据用户角色、时间约束和业务规则而有很大不同。

#### 3. 长期存在的 API

如果你的 API 将存在 5 年以上并会显著演进，HATEOAS 提供了灵活性。你可以在不破坏客户端的情况下重构 URL 结构。新操作可以逐步添加。弃用的操作可以优雅地移除。API 对新开发者更具可发现性。

### HATEOAS 不值得的场景

#### 1. 简单的 CRUD API

如果你的 API 很简单，涉及创建、读取、更新和删除操作而没有复杂的工作流，HATEOAS 就是过度设计。在这样的 API 中，业务规则很简单，没有复杂的状态转换需要管理。

对于内容管理系统的基本 CRUD 操作、简单的目录 API 或直接的数据访问层，Level 2 REST 就足够了。

#### 2. 具有同步部署的内部 API

如果你同时控制前端和后端，一起部署它们，HATEOAS 增加了复杂性而没有太多好处。你可以同时更新双方。你可以用硬编码的 URL 获得更快的开发速度。

在微服务架构中，如果服务由同一团队拥有并一起部署，Level 2 REST 通常更实用。

#### 3. 性能关键的移动 API

慢速网络上的移动应用需要小负载。链接会显著增加集合的负载大小。如果你正在优化每一千字节，HATEOAS 可能不值得。

对于面向消费者的移动应用，尤其是在新兴市场，有限的带宽和数据成本意味着每个字节都很重要。在这些情况下，GraphQL 或优化的 Level 2 REST 可能更合适。

#### 4. GraphQL 或 gRPC 系统

如果你正在使用 GraphQL 或 gRPC，你已经以不同的方式解决了 HATEOAS 解决的问题。GraphQL 提供了强类型模式，让客户端准确查询他们需要的内容。gRPC 也使用强类型模式。

混合范式会造成混乱。例如：你构建了一个 GraphQL API，客户端在其中组合查询。向 GraphQL 响应添加 HATEOAS 链接与 GraphQL 的设计相悖。客户端已经指定他们想要什么；他们不需要服务器建议操作。

### 务实的混合方法：选择性 HATEOAS

你也可以采用务实的混合方法：**选择性 HATEOAS**。

只对具有复杂工作流的资源使用 HATEOAS：

- 具有状态转换的订单：包含链接
- 简单的产品列表：不包含链接
- 用户配置文件：不包含链接

通过查询参数使链接可选：

```bash
GET /orders/123 - 不包含链接
GET /orders/123?expand=links - 包含链接
```

这让性能关键的客户端跳过链接。Web 应用可以请求链接以获得更好的用户体验。移动应用可以选择退出以节省带宽。

在决定是停留在 Level 2 还是采用 HATEOAS 之前，问自己："HATEOAS 解决了我们实际存在的问题吗？"

如果你正在构建一个具有同步部署的内部 CRUD API，你没有 HATEOAS 解决的问题。这只是额外的工作。

如果你正在构建一个具有复杂工作流的公共 API，由你无法控制的许多客户端消费，HATEOAS 可能会为你节省数月的协调和版本控制头痛。

## 总结

架构是关于权衡的。HATEOAS 用实现复杂性和负载大小换取灵活性和松耦合。这种权衡是否有意义完全取决于你的具体情况。

大多数 API 停留在 Richardson Level 2，这完全可以。但了解 Level 3 提供了什么，以及它何时真正重要，这对于做出明智的架构决策至关重要。

当你的业务逻辑复杂、客户端多样化、API 生命周期长时，HATEOAS 的投资会得到回报。当你的场景简单、控制权集中、性能至关重要时，Level 2 REST 可能就足够了。

关键是要有意识地做出选择，而不是盲目遵循"最佳实践"或因为感觉像过度工程而跳过它。理解权衡，评估你的具体需求，然后做出明智的决定。

希望这篇文章对你有所帮助。下次见！
