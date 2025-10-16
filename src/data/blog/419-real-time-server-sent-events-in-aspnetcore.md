---
pubDatetime: 2025-08-07
tags: [".NET", "ASP.NET Core", "Architecture", "Frontend"]
slug: real-time-server-sent-events-in-aspnetcore
source: https://antondevtips.com/blog/real-time-server-sent-events-in-asp-net-core
title: ASP.NET Core 与 .NET 10 中的实时 Server-Sent Events 技术详解
description: 本文详细介绍了如何在 ASP.NET Core 和 .NET 10 中实现 Server-Sent Events（SSE）实时推送，包括核心原理、服务端与前端实现、与 SignalR 的对比及最佳实践，配合源码与实用图示，适合希望提升 .NET 实时能力的开发者。
---

# ASP.NET Core 与 .NET 10 中的实时 Server-Sent Events 技术详解

随着实时 Web 应用场景日益丰富，如何高效地将后端变动第一时间推送到前端，已成为现代 .NET 应用开发中绕不开的话题。ASP.NET Core 10 开始，官方正式引入了原生 Server-Sent Events（SSE）支持。本文将围绕 SSE 技术，从原理、ASP.NET Core 实现、重连机制、前端消费、与 SignalR 对比等多个维度，深入解析 SSE 在实时推送领域的价值与落地实践。

## 什么是 Server-Sent Events（SSE）？

Server-Sent Events（SSE）是一种基于 HTTP 协议的单向推送技术，允许服务器主动向浏览器等客户端连续推送实时数据，而无需客户端反复轮询。它使用 `text/event-stream` 作为响应类型，在浏览器端由原生 EventSource API 直接支持。SSE 适用于股票行情、系统通知、实时监控等一切需要“服务端到客户端单向流式数据”的场景。

**SSE 的核心特点包括：**

- **单向通信**：只支持服务器到客户端的推送。
- **基于 HTTP/1.1**：无需 WebSocket 复杂握手，天然兼容主流浏览器与网络基础设施。
- **内建重连机制**：连接意外断开后，浏览器可自动发起重连，并支持断点续传。
- **资源消耗低**：相比 WebSocket，更加轻量，适合简单实时需求。

SSE 现已在 Chrome、Firefox、Safari、Edge 等主流浏览器实现，并可通过 curl、Postman 等工具直接测试。

## 常见应用场景

SSE 适合但不限于以下场景：

- **实时数据流**：如股票、比分、新闻、舆情监控。
- **系统推送通知**：社交、业务变更、状态提醒。
- **进度反馈**：如大文件上传进度、长任务处理回调。
- **实时仪表盘**：各类监控面板、运营可视化。

其实现门槛远低于 WebSocket/SignalR，尤其适用于无需客户端反馈的实时可视化与播报类应用。

## ASP.NET Core 10 中的 SSE 实现

从 .NET 10 Preview 4 开始，ASP.NET Core 增加了对 SSE 的内置支持。开发者只需将接口的 Content-Type 设置为 `text/event-stream`，利用 Minimal API 方式即可实现高性能 SSE 推送。

### 1. 服务端异步流数据生成

例如，创建一个每隔两秒推送一次股票报价的 StockService：

```csharp
public record StockPriceEvent(string Id, string Symbol, decimal Price, DateTime Timestamp);

public class StockService
{
    public async IAsyncEnumerable<StockPriceEvent> GenerateStockPrices(
        [EnumeratorCancellation] CancellationToken cancellationToken)
    {
        var symbols = new[] { "MSFT", "AAPL", "GOOG", "AMZN" };

        while (!cancellationToken.IsCancellationRequested)
        {
            var symbol = symbols[Random.Shared.Next(symbols.Length)];
            var price = Math.Round((decimal)(100 + Random.Shared.NextDouble() * 50), 2);
            var id = DateTime.UtcNow.ToString("o");

            yield return new StockPriceEvent(id, symbol, price, DateTime.UtcNow);

            await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);
        }
    }
}
```

### 2. SSE Endpoint 配置

利用 Minimal API，可以快速实现 SSE 推送接口：

```csharp
builder.Services.AddSingleton<StockService>();

app.MapGet("/stocks", (StockService stockService, CancellationToken ct) =>
{
    return TypedResults.ServerSentEvents(
        stockService.GenerateStockPrices(ct),
        eventType: "stockUpdate"
    );
});
```

这样，前端每两秒即可收到一条最新的股票数据，且通道为持久长连，无需额外配置。

## SSE 的断线重连与 Last-Event-ID 机制

SSE 天然支持断线重连功能。浏览器会自动带上 `Last-Event-ID` 头，指明上次接收到的事件 ID，方便服务端判断断点续传。例如：

```
Last-Event-ID: 20250616T150430Z
```

在 ASP.NET Core 端，可以这样获取并处理重连逻辑：

```csharp
app.MapGet("/stocks2", (
    StockService stockService,
    HttpRequest httpRequest,
    CancellationToken ct) =>
{
    var lastEventId = httpRequest.Headers.TryGetValue("Last-Event-ID", out var id)
        ? id.ToString()
        : null;

    if (!string.IsNullOrEmpty(lastEventId))
    {
        app.Logger.LogInformation("Reconnected, client last saw ID {LastId}", lastEventId);
    }

    var stream = stockService.GenerateStockPricesSince(lastEventId, ct)
        .Select(evt =>
        {
            var sseItem = new SseItem<StockPriceEvent>(evt, "stockUpdate")
            {
                EventId = evt.Id
            };
            return sseItem;
        });

    return TypedResults.ServerSentEvents(
        stream,
        eventType: "stockUpdate"
    );
});
```

这不仅提升了用户体验，也保证了消息传递的完整性与连续性。

## 开发环境下的 CORS 支持

前端跨域访问 SSE 接口时，需在开发环境中允许 CORS：

```csharp
if (builder.Environment.IsDevelopment())
{
    builder.Services.AddCors(options =>
    {
        options.AddPolicy("AllowFrontend", policy =>
        {
            policy.WithOrigins("*")
                .AllowAnyHeader()
                .AllowAnyMethod();
        });
    });
}

if (app.Environment.IsDevelopment())
{
    app.UseCors("AllowFrontend");
}
```

## 前端消费 SSE：EventSource 实践

前端使用原生的 `EventSource` API 即可轻松对接后端 SSE 服务：

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Live Stock Ticker</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="min-h-screen bg-gray-50 p-8">
    <div class="mx-auto max-w-4xl">
      <h1 class="mb-6 flex items-center text-3xl font-bold text-gray-800">
        📈<span class="ml-2">Live Stock Market Updates</span>
      </h1>
      <div class="rounded-lg bg-white p-6 shadow-md">
        <ul id="updates" class="divide-y divide-gray-200"></ul>
      </div>
    </div>
    <script>
      const source = new EventSource("http://localhost:5000/stocks");

      source.addEventListener("stockUpdate", e => {
        const { symbol, price, timestamp } = JSON.parse(e.data);

        const li = document.createElement("li");
        li.classList.add("new", "flex", "justify-between", "items-center");

        const timeSpan = document.createElement("span");
        timeSpan.classList.add("text-gray-500", "text-sm");
        timeSpan.textContent = new Date(timestamp).toLocaleTimeString();

        const symbolSpan = document.createElement("span");
        symbolSpan.classList.add("font-medium", "text-gray-800");
        symbolSpan.textContent = symbol;

        const priceSpan = document.createElement("span");
        priceSpan.classList.add("font-bold", "text-green-600");
        priceSpan.textContent = `$${price}`;

        li.appendChild(timeSpan);
        li.appendChild(symbolSpan);
        li.appendChild(priceSpan);

        const list = document.getElementById("updates");
        list.prepend(li);

        setTimeout(() => li.classList.remove("new"), 2000);
      });

      source.onerror = err => {
        console.error("SSE connection error:", err);
      };
    </script>
  </body>
</html>
```

每当服务端有新推送，页面便会实时更新行情列表，完全免除轮询和手动刷新。

![实时股票行情效果图](https://antondevtips.com/media/code_screenshots/aspnetcore/server-sent-events/img_1.png)

## 测试 SSE 接口：IDE HTTP 文件与网络调试

现代 IDE（如 Visual Studio Code、JetBrains Rider）均支持 HTTP Request 文件，直接编写如下内容即可调试 SSE 接口：

```
@ServerSentEvents_HostAddress = http://localhost:5000

GET {{ServerSentEvents_HostAddress}}/stocks
Accept: text/event-stream
```

在浏览器 DevTools 的 Network 面板中，也可直观查看事件流数据：

![浏览器网络面板调试 SSE](https://antondevtips.com/media/code_screenshots/aspnetcore/server-sent-events/img_2.png)

## SSE 与 SignalR（WebSocket）的核心区别

SSE 与 SignalR 虽同为实时通信技术，但设计理念与应用场景存在明显差异。对比如下：

| 维度       | SSE                           | SignalR (WebSocket)                |
| ---------- | ----------------------------- | ---------------------------------- |
| 协议       | HTTP/1.1（text/event-stream） | WebSocket/HTTP（多种回退）         |
| 通信方向   | 单向（服务器→客户端）         | 双向全双工                         |
| 浏览器支持 | 原生支持，兼容广泛            | 需 WebSocket 支持，部分回退        |
| 资源消耗   | 低，仅单一长连接              | 高，需专门帧管理                   |
| 消息类型   | 仅文本                        | 文本/二进制                        |
| API 丰富度 | 简单 API，易上手              | 丰富，支持分组、身份、广播等       |
| 适用场景   | 通知推送、状态流、日志        | 聊天、协作、需要客户端上传数据等   |
| 扩展与弹性 | 按普通 HTTP 扩展              | 支持分布式扩展，如 Redis Backplane |

综上，SSE 更适用于“单向消息推送”与流式广播；而 SignalR 则主打“实时互动”与高阶分布式场景。实际选择应结合业务需求与技术栈定制。

## 总结与最佳实践

ASP.NET Core 10 的 SSE 支持，让 .NET 开发者能更低门槛地构建实时推送应用。其简洁、易用、资源友好的特性，在各类数据流、仪表盘、实时监控等场景表现优异。当只需服务端到客户端单向推送时，推荐优先考虑 SSE；如需双向通信或复杂分组、分布式广播，则 SignalR 更合适。

感兴趣的开发者可[下载完整源码](https://antondevtips.com/source-code/real-time-server-sent-events-in-asp-net-core)进行实践，结合自身业务落地实时能力，提升应用交互体验与实时性。

---

> 原文作者：[Anton Martyniuk](https://antondevtips.com/)
>
> 原文链接：[https://antondevtips.com/blog/real-time-server-sent-events-in-asp-net-core](https://antondevtips.com/blog/real-time-server-sent-events-in-asp-net-core)
