---
pubDatetime: 2026-03-23T10:00:00+08:00
title: "用 Redis Backplane 解决 SignalR 多实例消息丢失问题"
description: "SignalR 单实例没问题，一水平扩展消息就开始消失——这是几乎所有人都会踩的坑。本文介绍 Redis Backplane 模式：原理、接入方式、粘性会话要求，以及 Redis 宕机时的行为。配置只需一行代码，但有两件事必须提前搞清楚。"
tags: ["SignalR", "Redis", "ASP.NET Core", "Real-time", "Distributed Systems"]
slug: "scaling-signalr-with-redis-backplane"
ogImage: "../../assets/656/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/scaling-signalr-with-redis-backplane"
---

![用 Redis Backplane 解决 SignalR 水平扩展消息丢失](../../assets/656/01-cover.png)

在本地测试时，SignalR 的实时通知运行得非常流畅。但一旦在负载均衡器后面扩展到两个实例，消息就开始对部分用户无声无息地消失——代码本身没有问题，问题出在 SignalR 的连接模型上。

## 问题根源

SignalR 的连接是绑定在接受它的那个服务器进程上的。每个实例只知道自己管理的连接。

单实例时，服务器持有所有客户端的完整连接映射，发消息给某个用户、某个 Group、或所有客户端都没问题。

但扩展到两个或更多实例时，这张映射就碎片化了：

- Server 1 完全不知道 Client 3 和 Client 4 的存在
- 当一个订单状态变更事件发生在 Server 1，需要通知 Client 3，Server 1 查自己的连接映射，什么都找不到，消息就被静默丢弃

## Backplane 模式

解决方法是引入一个 **Backplane**——一个坐在所有服务器实例之间的共享消息层。

每个服务器把出站消息发布到中央频道，同时每个服务器也订阅同一个频道。收到消息后，各服务器检查自己管理的本地连接里是否有目标接收方。

当 Server 1 需要通知 Client 3：

1. Server 1 把消息发布到 Backplane
2. 所有服务器都收到这条消息
3. Server 2 识别出 Client 3 是自己的连接，完成投递

从应用代码的角度来看，就像每台服务器都能看见所有连接一样。

Redis 在这个场景里非常契合，因为它的 Pub/Sub 能近乎实时地把消息推送给所有订阅者。如果你已经在用 Redis 做分布式缓存，甚至不需要额外搭建任何东西。

## 接入步骤

### 1. 安装 NuGet 包

```bash
dotnet add package Microsoft.AspNetCore.SignalR.StackExchangeRedis
```

### 2. 注册 Backplane

在 `AddSignalR()` 链式调用上增加 `.AddStackExchangeRedis()`：

```csharp
builder.Services.AddSignalR()
    .AddStackExchangeRedis(builder.Configuration.GetConnectionString("cache")!);
```

如果你用的是 .NET Aspire，Redis 连接字符串已经通过环境变量注入，直接从配置里取同名连接即可：

```csharp
builder.AddRedisDistributedCache("cache");

builder.Services.AddSignalR()
    .AddStackExchangeRedis(builder.Configuration.GetConnectionString("cache")!);
```

### 3. 多应用共用同一个 Redis 实例时设置频道前缀

如果多个 SignalR 应用共享同一个 Redis 实例，必须加频道前缀，否则一个应用发出的消息会被其他所有应用的订阅者收到：

```csharp
builder.Services.AddSignalR()
    .AddStackExchangeRedis(connectionString, options =>
    {
        options.Configuration.ChannelPrefix = RedisChannel.Literal("OrderNotifications");
    });
```

**调用侧代码完全不需要改动。** `IHubContext<>` 的 `Clients.User(...)` 写法不变，无论是一个实例还是十个实例，Backplane 在背后处理路由。

用 .NET Aspire 启动两个副本验证时，每条通知都带上了发送方的实例 ID。连接在副本 1 的客户端收到了副本 2 打标的通知，证实消息确实经过了 Redis 在实例之间流转。

## 粘性会话：不能省的前提条件

这是在配置 Backplane 之前必须清楚的一件事：**Redis Backplane 只解决了消息路由问题，粘性会话（Sticky Sessions）的需求并没有消失。**

SignalR 建立连接是两步走：

1. 客户端向 `/hub/negotiate` 发送 `POST` 请求，获取一个连接 Token
2. 客户端用这个 Token 建立 WebSocket 连接

这两个请求必须落在同一台服务器上。如果负载均衡器把 negotiate 请求路由到 Server 1，而 WebSocket 升级请求路由到 Server 2，连接会直接失败。

在你的负载均衡器上开启粘性会话——大多数负载均衡器支持 IP Hash 或 Cookie Affinity，具体看各自的文档。

## Redis 宕机时会发生什么

SignalR **不会**对消息做缓冲。Redis 不可用期间发出的消息会直接丢失。

SignalR 可能会抛出异常，但已有的 WebSocket 连接不会断开——客户端不会掉线。Redis 恢复后，SignalR 会自动重连。

对于大多数实时场景（订单更新、实时仪表盘），这是可以接受的：下次状态变更触发新的通知，或者用户刷新一下页面就好。如果你处理的是金融数据、运营告警这类对数据完整性要求更高的场景，需要在重连时加协调策略，或者并行跑一个持久化消息队列。

## 与 Azure SignalR Service 对比

如果你的服务跑在 Azure 上，托管的 Azure SignalR Service 值得考虑。它把所有客户端连接都代理到托管服务，从而消除了粘性会话的需求，你的服务器只需要和服务保持少量固定连接。

Redis Backplane 更适合自托管、对延迟敏感、或者已经在跑 Redis 的场景。其他情况下，Azure SignalR Service 是更干净的选择。

## 小结

Redis Backplane 的接入门槛出奇地低——在 `AddSignalR()` 上加一个方法调用，应用就从静默丢失消息变成了跨实例路由。Hub 代码、客户端代码、应用逻辑，一行都不用改。

只需要记住两件事：

- 粘性会话还是需要的
- Redis 临时宕机期间消息不会缓冲

把这两点处理好，SignalR 的水平扩展和你技术栈里其他部分一样顺畅。

## 参考

- [原文：Scaling SignalR With a Redis Backplane](https://www.milanjovanovic.tech/blog/scaling-signalr-with-redis-backplane)
- [Adding Real-Time Functionality to .NET Applications with SignalR](https://www.milanjovanovic.tech/blog/adding-real-time-functionality-to-dotnet-applications-with-signalr)
- [Simple Messaging in .NET with Redis Pub/Sub](https://www.milanjovanovic.tech/blog/simple-messaging-in-dotnet-with-redis-pubsub)
- [Azure SignalR Service 文档](https://learn.microsoft.com/en-us/azure/azure-signalr/signalr-overview)
