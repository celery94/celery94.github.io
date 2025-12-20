---
pubDatetime: 2025-12-20
title: "Server-Sent Events in ASP.NET Core and .NET 10"
description: "探索 .NET 10 中新增的原生 Server-Sent Events (SSE) API，学习如何在 ASP.NET Core 中实现轻量级的单向实时数据推送，以及何时选择 SSE 而非 SignalR。"
tags: [".NET", "ASP.NET Core", "Real-time", "SSE"]
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

.NET 10 SSE API 的优雅之处在于其简洁性。你可以使用新的 `Results.ServerSentEvents` 从任何 `IAsyncEnumerable<T>` 返回事件流：

```csharp
app.MapGet("orders/realtime", (
    ChannelReader<OrderPlacement> channelReader,
    CancellationToken cancellationToken) =>
{
    // IAsyncEnumerable 代表随时间到达的数据流
    return Results.ServerSentEvents(
        channelReader.ReadAllAsync(cancellationToken),
        eventType: "orders");
});
```

当客户端访问此端点时：

1. 服务器发送 `Content-Type: text/event-stream` 头
2. 连接保持活动并等待数据
3. 一旦有新订单进入 Channel，`IAsyncEnumerable` 产出该项，.NET 立即通过 HTTP 管道将其推送到浏览器

## 处理丢失的事件

简单的端点虽然有效，但缺少弹性机制。当连接断开并重连时，可能会丢失一些事件。SSE 内置了解决方案：`Last-Event-ID` 头。浏览器重连时会将此 ID 发回服务器。

在 .NET 10 中，我们可以使用 `SseItem<T>` 类型为数据添加元数据（如 ID 和重试间隔）：

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

SSE 构建在标准 HTTP 之上，因此你现有的基础设施"开箱即用"：

- **安全性**：可以在 `Authorization` 头中传递标准 JWT
- **用户上下文**：可以访问 `HttpContext.User` 提取用户 ID 并过滤流

以下是只向认证用户推送其自己订单的示例：

```csharp
app.MapGet("orders/realtime", (
    ChannelReader<OrderPlacement> channelReader,
    IUserContext userContext,
    CancellationToken cancellationToken) =>
{
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
.RequireAuthorization();
```

## JavaScript 客户端实现

客户端无需安装任何 npm 包。浏览器原生的 `EventSource` API 处理所有重连和 Last-Event-ID 逻辑：

```javascript
const eventSource = new EventSource("/orders/realtime/with-replays");

// 监听特定的 'orders' 事件类型
eventSource.addEventListener("orders", event => {
  const payload = JSON.parse(event.data);
  console.log(`New Order ${event.lastEventId}:`, payload.data);
});

// 连接打开时的处理
eventSource.onopen = () => {
  console.log("Connection opened");
};

// 错误处理和重连
eventSource.onerror = () => {
  if (eventSource.readyState === EventSource.CONNECTING) {
    console.log("Reconnecting...");
  }
};
```

## 实践建议

**何时使用 SSE：**

- 仪表板实时更新
- 通知推送
- 进度条更新
- 简单的单向数据流

**何时使用 SignalR：**

- 需要双向通信
- 复杂的实时应用
- 需要大规模扩展和后端支撑

**最佳实践：**

1. 对于生产环境，使用更强大的消息分发机制而不是简单的 Channel 广播
2. 实现事件缓冲来处理重连场景
3. 使用标准的 ASP.NET Core 授权来保护端点
4. 充分利用 `IAsyncEnumerable` 的流式特性

.NET 10 中的 SSE 为简单的单向更新提供了完美的中间方案。它轻量、基于 HTTP 原生协议，并且易于使用现有中间件保护。选择最轻量的工具来解决你的问题——这正是优秀架构的体现。
