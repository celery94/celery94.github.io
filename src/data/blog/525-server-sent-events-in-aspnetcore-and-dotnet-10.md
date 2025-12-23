---
pubDatetime: 2025-12-20
title: "Server-Sent Events in ASP.NET Core and .NET 10"
description: "探索 .NET 10 中新增的原生 Server-Sent Events (SSE) API，学习如何在 ASP.NET Core 中实现轻量级的单向实时数据推送，以及何时选择 SSE 而非 SignalR。"
tags: [".NET", "ASP.NET Core", "Real-time", "SSE", "WebSockets"]
slug: "server-sent-events-in-aspnetcore-and-dotnet-10"
source: "https://www.milanjovanovic.tech/blog/server-sent-events-in-aspnetcore-and-dotnet-10"
---

# Server-Sent Events in ASP.NET Core and .NET 10

## 背景

实时数据更新已经成为现代 Web 应用的标准需求。在 .NET 生态系统中，SignalR 长期以来一直是实现实时功能的首选方案。然而，对于简单的单向数据推送场景，SignalR 可能显得过于复杂。

随着 ASP.NET Core 10 的发布，.NET 终于提供了原生的 Server-Sent Events (SSE) API。SSE 在基本的 HTTP 轮询和 SignalR 的全双工 WebSockets 之间提供了一个理想的中间选择。

## 为什么选择 SSE 而不是 SignalR？

SignalR 是一个功能强大的框架，自动处理 WebSockets、长轮询和 SSE，提供全双工（双向）通信通道。但它也带来了额外的开销：

- 特定的协议（Hubs）
- 必需的客户端库
- 扩展时需要"粘性会话"或 Redis 等后端支撑

相比之下，SSE 具有以下优势：

- **单向通信**：专为从服务器到客户端的数据流设计
- **原生 HTTP**：只是标准的 HTTP 请求，内容类型为 `text/event-stream`
- **自动重连**：浏览器通过 EventSource API 原生支持重连
- **轻量级**：无需复杂的客户端库或握手逻辑

## 最简单的 SSE 端点

.NET 10 SSE API 的优雅之处在于其简洁性。你可以使用新的 `Results.ServerSentEvents` 从任何 `IAsyncEnumerable<T>` 返回事件流。

因为 `IAsyncEnumerable` 代表可以随时间到达的数据流，服务器知道要保持 HTTP 连接打开，而不是在第一个数据块之后就关闭它。

以下是一个流式传输实时订单的最小化 SSE 端点示例：

```csharp
app.MapGet("orders/realtime", (
    ChannelReader<OrderPlacement> channelReader,
    CancellationToken cancellationToken) =>
{
    // 1. ReadAllAsync 返回一个 IAsyncEnumerable
    // 2. Results.ServerSentEvents 告诉浏览器："保持此连接打开"
    // 3. 新数据一进入 Channel 就立即推送到客户端
    return Results.ServerSentEvents(
        channelReader.ReadAllAsync(cancellationToken),
        eventType: "orders");
});
```

当客户端访问此端点时：

1. 服务器发送 `Content-Type: text/event-stream` 头
2. 连接保持活动状态并在等待数据时处于空闲状态
3. 一旦你的应用将订单推入 `Channel`，`IAsyncEnumerable` 产出该项，.NET 立即通过打开的 HTTP 管道将其刷新到浏览器

这是一种极其高效的方式来处理"推送"通知，无需有状态协议的开销。

> **注意**：这里使用 `Channel` 只是达到目的的一种手段。在真实应用中，你可能会有一个后台服务监听消息队列（如 RabbitMQ 或 Azure Service Bus）或数据库变更馈送，然后将新事件推入 Channel 供连接的客户端消费。

## 处理丢失的事件

我们刚刚构建的简单端点很棒，但它有一个弱点：缺少弹性机制。

实时流的最大挑战之一是连接断开。当浏览器自动重连时，可能已经发送并丢失了几个事件。为了解决这个问题，SSE 有一个内置机制：`Last-Event-ID` **头**。当浏览器重连时，它会将此 ID 发回服务器。

在 .NET 10 中，我们可以使用 `SseItem<T>` 类型为数据添加元数据，如 ID 和重试间隔。

通过结合简单的内存 `OrderEventBuffer` 和浏览器提供的 `Last-Event-ID`，我们可以在重连时"重放"丢失的消息：

```csharp
app.MapGet("orders/realtime/with-replays", (
    ChannelReader<OrderPlacement> channelReader,
    OrderEventBuffer eventBuffer,
    [FromHeader(Name = "Last-Event-ID")] string? lastEventId,
    CancellationToken cancellationToken) =>
{
    async IAsyncEnumerable<SseItem<OrderPlacement>> StreamEvents()
    {
        // 1. 从缓冲区重放丢失的事件
        if (!string.IsNullOrWhiteSpace(lastEventId))
        {
            var missedEvents = eventBuffer.GetEventsAfter(lastEventId);
            foreach (var missedEvent in missedEvents)
            {
                yield return missedEvent;
            }
        }

        // 2. 流式传输新到达的事件
        await foreach (var order in channelReader.ReadAllAsync(cancellationToken))
        {
            var sseItem = eventBuffer.Add(order);
            yield return sseItem;
        }
    }

    return TypedResults.ServerSentEvents(StreamEvents(), "orders");
});
```

## 按用户过滤事件

Server-Sent Events 构建在标准 HTTP 之上。因为它是标准的 `GET` 请求，你现有的基础设施"开箱即用"：

- **安全性**：可以在 `Authorization` 头中传递标准 JWT
- **用户上下文**：可以访问 `HttpContext.User` 提取用户 ID 并过滤流。你只向用户发送属于他们的数据

以下是只向认证用户流式传输其自己订单的 SSE 端点示例：

```csharp
app.MapGet("orders/realtime", (
    ChannelReader<OrderPlacement> channelReader,
    IUserContext userContext, // 注入的包含用户元数据的上下文
    CancellationToken cancellationToken) =>
{
    // UserId 从 JWT 访问令牌中通过 IUserContext 提取
    var currentUserId = userContext.UserId;

    async IAsyncEnumerable<OrderPlacement> GetUserOrders()
    {
        await foreach (var order in channelReader.ReadAllAsync(cancellationToken))
        {
            // 只产出属于认证用户的数据
            if (order.CustomerId == currentUserId)
            {
                yield return order;
            }
        }
    }

    return Results.ServerSentEvents(GetUserOrders(), "orders");
})
.RequireAuthorization(); // 标准的 ASP.NET Core 授权
```

> **注意**：当你向 `Channel` 写入消息时，它会广播到**所有**连接的客户端。这对于每用户流不太理想。对于生产环境，你可能需要使用更强大的方案。

## JavaScript 客户端实现

在客户端，你不需要安装任何 npm 包。浏览器原生的 `EventSource` API 处理所有重活，包括我们上面讨论的"重连并发送 Last-Event-ID"逻辑。

```javascript
const eventSource = new EventSource("/orders/realtime/with-replays");

// 监听我们在 C# 中定义的特定 'orders' 事件类型
eventSource.addEventListener("orders", event => {
  const payload = JSON.parse(event.data);
  console.log(`New Order ${event.lastEventId}:`, payload.data);
});

// 连接打开时的处理
eventSource.onopen = () => {
  console.log("Connection opened");
};

// 处理通用消息（如果有的话）
eventSource.onmessage = event => {
  console.log("Received message:", event);
};

// 错误处理和重连
eventSource.onerror = () => {
  if (eventSource.readyState === EventSource.CONNECTING) {
    console.log("Reconnecting...");
  }
};
```

## 总结

.NET 10 中的 SSE 是简单的单向更新的完美中间方案，如仪表板、通知提示和进度条。它轻量、基于 HTTP 原生协议，并且易于使用现有中间件保护。

然而，**SignalR** 仍然是复杂双向通信或需要后端支撑的大规模场景的强大、久经考验的选择。

目标不是取代 SignalR，而是为更简单的工作提供更简单的工具。选择能解决你问题的最轻量的工具。

这就是今天的全部内容。希望对你有所帮助。
