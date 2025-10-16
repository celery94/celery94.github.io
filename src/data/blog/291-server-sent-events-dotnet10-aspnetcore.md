---
pubDatetime: 2025-04-27 08:59:51
tags: [".NET", "ASP.NET Core"]
slug: server-sent-events-dotnet10-aspnetcore
source: https://khalidabuhakmeh.com/server-sent-events-in-aspnet-core-and-dotnet-10
title: .NET 10 新特性：ASP.NET Core Minimal API 实现 Server-Sent Events（SSE）实时推送详解
description: 面向.NET开发者与技术爱好者，详解ASP.NET Core Minimal API在.NET 10中如何优雅实现Server-Sent Events（SSE）单向实时推送，并对比SignalR，配合完整代码与前端交互示例，助你打造轻量级实时应用。
---

# .NET 10 新特性：ASP.NET Core Minimal API 实现 Server-Sent Events（SSE）实时推送详解

## 引言：.NET 10，实时推送新姿势 👀

.NET 10 和 ASP.NET Core 的持续进化总能给开发者带来惊喜。在 C# 14 与最新 Minimal API 支持下，Server-Sent Events（SSE）成为实现后端到前端单向实时推送的全新选择。无论你是正为直播新闻、股票行情、还是其他需要“只读”实时流的系统头疼，这篇文章都将让你事半功倍！

那么，SSE 到底是什么？和 SignalR、WebSocket 有啥不同？如何用最简洁的方式在 ASP.NET Core Minimal API 中落地？接下来，一文解锁！👇

---

## 一、Server-Sent Events（SSE）到底是什么？

SSE（Server-Sent Events）是一种基于 HTTP 协议的单向实时通信方式，由服务器主动向客户端推送事件，客户端只需订阅即可持续收到数据。SSE 适合用在：

- 实时新闻推送
- 股票、体育比分等行情应用
- 系统监控仪表盘等场景

### SSE vs. SignalR vs. WebSocket，有啥不同？

| 特性     | SSE                   | SignalR/WebSocket       |
| -------- | --------------------- | ----------------------- |
| 通信方向 | 单向（服务器→客户端） | 双向（可互相发送消息）  |
| 协议     | 基于 HTTP             | 独立协议                |
| 资源消耗 | 更轻量                | 通常更重，功能更丰富    |
| 使用场景 | 只需服务器推送        | 需双向交互/高复杂度场景 |

> **总结**：如果只需服务器推送数据给客户端，SSE 就是理想选择；如果需要双向通信或更复杂的交互，则推荐使用 SignalR。

---

## 二、ASP.NET Core Minimal API 如何实现 SSE？代码演示来啦！

### 1. SSE Endpoint 核心实现

.NET 10 开始，Minimal API 支持 `TypedResults.ServerSentEvents`，只需返回 `IAsyncEnumerable<>` 即可持续推送数据。

```csharp
app.MapGet("/orders", (FoodService foods, CancellationToken token) =>
    TypedResults.ServerSentEvents(
        foods.GetCurrent(token),
        eventType: "order")
);
```

- `foods.GetCurrent(token)` 返回一个异步可枚举序列，用于源源不断地推送数据。
- `eventType` 指定事件类型，方便前端 JS 监听。

### 2. IAsyncEnumerable 服务端实现

如何让所有订阅者同步收到同一份数据？这就需要 `FoodService` 和后台定时更新的 `FoodServiceWorker`。

#### FoodService（状态管理+事件订阅）

```csharp
public class FoodService : INotifyPropertyChanged
{
    public FoodService() { /* 初始化当前菜品 */ }

    // 当前推送的“食物”emoji
    private string Current { get; set; }

    public async IAsyncEnumerable<string> GetCurrent([EnumeratorCancellation] CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            yield return Current;
            var tcs = new TaskCompletionSource();
            PropertyChanged += (_, _) => tcs.SetResult();
            try { await tcs.Task.WaitAsync(ct); } finally { PropertyChanged -= handler; }
        }
    }

    public void Set() { /* 随机切换下一个食物 */ }
}
```

#### FoodServiceWorker（定时更新）

```csharp
public class FoodServiceWorker(FoodService foodService) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            foodService.Set();
            await Task.Delay(1000, stoppingToken);
        }
    }
}
```

> **原理**：每秒随机更新一次食物 emoji，通过事件通知所有订阅者，即时推送新内容。

---

## 三、前端：JavaScript 轻松接收 SSE 推送

只需几行 JS，即可完成客户端订阅与渲染！

```html
<ul id="orders"></ul>
<script>
  const eventSource = new EventSource("/orders");
  const ordersList = document.getElementById("orders");

  eventSource.addEventListener("order", event => {
    const li = document.createElement("li");
    li.textContent = event.data;
    ordersList.appendChild(li);
  });

  eventSource.onerror = error => {
    console.error("EventSource failed:", error);
    eventSource.close();
  };
</script>
```

每次服务端变更，前端自动收到新 emoji。如果你同时打开多个页面，还能看到数据完全同步！

---

## 四、实战应用与优势总结

- **高效轻量**：利用 HTTP 长连接，无需额外协议或复杂依赖。
- **易于集成**：Minimal API + IAsyncEnumerable，自然融入 .NET 生态。
- **场景广泛**：适合各种“只需服务器推送”的信息流项目。

---

## 结语 & 互动 🌟

Server-Sent Events 在 .NET 10 中的原生支持让实时应用开发变得更加简单高效。你有哪些实时推送需求？会考虑用 SSE 替代 SignalR 吗？或者你在项目中遇到过哪些有趣的“只读流”场景？欢迎在评论区留言讨论，或转发给身边感兴趣的小伙伴！
