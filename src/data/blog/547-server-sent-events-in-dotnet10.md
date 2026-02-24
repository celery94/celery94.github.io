---
pubDatetime: 2026-02-24
title: ".NET 10 中的 Server-Sent Events：实时流式传输的简洁方案"
description: "本文介绍 .NET 10 中新增的 Results.ServerSentEvents 功能，通过订单实时追踪案例，展示如何用 SSE 替代 WebSocket 实现更简洁的服务端推送，并探讨 Channel、生产环境注意事项及适用场景。"
tags: [".NET", "ASP.NET Core", "SSE", "Real-Time", "Server-Sent Events"]
source: "https://thecodeman.net/posts/server-sent-event-in-dotnet"
---

## 引言：现代 ASP.NET Core 应用中的实时功能

实时功能已经是现代 Web 应用的标配。用户下单后期待看到即时状态变化，监控后台任务期待进度实时刷新。作为 .NET 开发者，一提到"实时"，我们往往首先想到 WebSocket 或 SignalR。

但从架构角度重新审视：如果你的系统只需要**从服务端向客户端推送数据**，WebSocket 带来的复杂度可能是多余的。

.NET 10 中，ASP.NET Core 提供了对 **Server-Sent Events（SSE）** 的原生支持：`Results.ServerSentEvents`。它让实时流式传输变得更简单、更干净，也更符合 HTTP 语义。

## 什么是 Server-Sent Events（SSE）？

Server-Sent Events 是一种 Web 标准，允许服务端通过一条长连接的 HTTP 连接向浏览器推送更新。响应的 Content-Type 为 `text/event-stream`，服务端在事件发生时持续发送消息。

和 WebSocket 不同，SSE 是**单向**的，数据只从服务端流向客户端，没有全双工通道。这个限制在很多场景下反而是优势，因为它降低了架构复杂度。

在 ASP.NET Core 中，SSE 允许你把 `IAsyncEnumerable<T>` 直接流式传输给浏览器，使用的是原生 HTTP 基础设施。.NET 10 的 `Results.ServerSentEvents` 封装了手动配置 Header、格式化和 Flush 的逻辑。

如果你的场景涉及订单状态推送、任务进度、监控指标、日志或通知，SSE 可能是最务实的选择。

## 为什么用 SSE 而不用 WebSocket？

在企业系统中，复杂度是有代价的。WebSocket 引入了连接升级、双向状态管理、额外的基础设施考量，以及对 SignalR 等外部库的依赖。

如果你的系统不需要双向通信，引入 WebSocket 可能是过度设计。

SSE 完全运行在标准 HTTP 之上，没有升级握手。浏览器通过 EventSource API 原生支持 SSE，并且在连接断开时自动重连。这让 SSE 在云环境和反向代理配置中特别有吸引力。

对于订单追踪、后台处理更新、部署状态推送等场景，SSE 提供了更简洁、更易维护的方案。

## 实战案例：实时订单追踪

假设一个客户下了订单，后台需要依次完成支付验证、打包、发货、配送确认等异步操作。与其让前端每隔几秒轮询一次，不如让前端订阅一个流式端点，即时接收状态更新。

首先定义一个简单的领域模型来表示订单状态变更：

```csharp
public enum OrderStatus
{
    Created,
    PaymentConfirmed,
    Packed,
    Shipped,
    OutForDelivery,
    Delivered
}

public sealed record OrderStatusUpdate(
    Guid OrderId,
    OrderStatus Status,
    DateTime Timestamp);
```

使用 record 确保不可变性和清晰的序列化。在生产环境中，这些状态更新可能来自后台服务、消息队列或领域事件。

## 用 Channel 构建流式基础设施

要支持 .NET 10 中的实时流式传输，我们需要一种将事件生产者和订阅者解耦的机制。`System.Threading.Channels` 非常适合这个场景。

Channel 提供高性能的异步管道，能与 `IAsyncEnumerable<T>` 无缝集成，这正是 `Results.ServerSentEvents` 所需要的。

下面是一个简单的流式服务：

```csharp
public sealed class OrderStreamService
{
    private readonly ConcurrentDictionary<Guid, Channel<OrderStatusUpdate>> _streams = new();

    public ChannelReader<OrderStatusUpdate> Subscribe(Guid orderId)
    {
        var channel = Channel.CreateUnbounded<OrderStatusUpdate>();
        _streams[orderId] = channel;
        return channel.Reader;
    }

    public async Task PublishAsync(OrderStatusUpdate update)
    {
        if (_streams.TryGetValue(update.OrderId, out var channel))
        {
            await channel.Writer.WriteAsync(update);
        }
    }

    public void Unsubscribe(Guid orderId)
    {
        if (_streams.TryRemove(orderId, out var channel))
        {
            channel.Writer.TryComplete();
        }
    }
}
```

这个服务允许系统的任何部分发布订单更新，无需知道谁在监听。SSE 端点只需订阅并流式转发事件即可。这种模式天然适合 Clean Architecture、Vertical Slice Architecture 或模块化单体架构。

## 在 .NET 10 中使用 Results.ServerSentEvents

现在使用 .NET 10 的方式实现流式端点：

```csharp
app.MapGet("/orders/{orderId:guid}/stream", (
    Guid orderId,
    OrderStreamService streamService,
    CancellationToken cancellationToken) =>
{
    var reader = streamService.Subscribe(orderId);

    return Results.ServerSentEvents(
        reader.ReadAllAsync(cancellationToken),
        eventType: "order-update");
});
```

这就是 .NET 10 的关键改进。`Results.ServerSentEvents` 自动完成以下工作：

- 设置 `Content-Type` 为 `text/event-stream`
- 将每个对象序列化为 JSON
- 正确格式化 SSE 消息
- 适时 Flush 响应
- 处理取消令牌
- 管理 HTTP 流式生命周期

在早期版本的 ASP.NET Core 中，开发者需要手动写入 Header、用 `data:` 前缀格式化字符串、调用 `FlushAsync`。在 .NET 10 中，这些都由框架内置处理了，让实时流式传输更加简洁、不易出错。

## 模拟后端订单处理

为了演示实时更新，我们可以模拟异步订单处理过程：

```csharp
app.MapPost("/orders/{orderId:guid}/simulate", async (
    Guid orderId,
    OrderStreamService streamService) =>
{
    var statuses = Enum.GetValues<OrderStatus>();

    foreach (var status in statuses)
    {
        await Task.Delay(2000);

        await streamService.PublishAsync(new OrderStatusUpdate(
            orderId,
            status,
            DateTime.UtcNow));
    }

    return Results.Ok("Order simulation completed.");
});
```

每次状态更新都发布到 Channel 中，SSE 端点会立即将更新流式推送给已连接的客户端。不需要轮询，也不需要额外的消息基础设施。

## 用 Postman 测试 SSE

SSE 端点的测试方式和普通 REST 端点略有不同。SSE 端点会保持 HTTP 连接打开、持续推送数据，不会立即完成。Postman 支持这种测试，只要配置正确即可。

**测试 POST 模拟端点：**

1. 创建一个新请求，Method 选 POST
2. URL 填写 `https://localhost:7060/orders/{orderId}/simulate`（替换为真实 GUID）
3. 点击 Send，应收到 "Order simulation completed."

在后台，端点开始发布事件，每 2 秒发出一个 `OrderStatusUpdate`。

**测试 GET SSE 端点：**

1. 创建一个新的 GET 请求
2. URL 填写 `https://localhost:7060/orders/{orderId}/stream`
3. 点击 Send，请求不会立即完成，你会看到流式数据持续输出

## 生产环境注意事项

在生产环境中使用 SSE 需要注意以下几点：

- **反向代理配置**：Nginx、Traefik 或 Azure Application Gateway 等反向代理如果未正确配置，可能会关闭空闲连接。确保设置适当的超时参数。
- **多实例部署**：在多实例部署中，每个应用实例都必须接收到相同的事件。此时需要使用 Redis pub/sub 或消息队列等分布式事件总线将更新广播到所有节点。
- **连接数监控**：每个 SSE 客户端维持一条持久 HTTP 连接。虽然比 WebSocket 更轻量，但在高流量环境下仍需监控并发连接数。

## SSE 不适合的场景

当需要**双向通信**时，SSE 并不合适。实时聊天、多人游戏、协同编辑工具或 IoT 命令系统都需要双向通信，应该使用 WebSocket 或 SignalR。

SSE 的优势场景是服务端作为唯一的数据源，单向推送更新给客户端。

## 总结

随着 `Results.ServerSentEvents` 的引入，SSE 在 .NET 10 中成为了 ASP.NET Core 的一等公民。它提供了一种简洁的、基于 HTTP 原生协议的实时流式方案，避免了 WebSocket 带来的复杂度。

对于需要实时更新的系统，无论是订单追踪、任务进度推送还是监控面板，SSE 都是务实且可投产的方案。

在为下一个项目引入 WebSocket 基础设施之前，先问问自己是否真的需要双向通信。如果不需要，SSE 可能是最优雅、最易维护的选择。实时通信不一定意味着复杂，有时候最简单的协议反而最强大。
