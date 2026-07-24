---
pubDatetime: 2026-07-24T00:12:39+08:00
title: "ASP.NET Core + SSE：构建流式 AI 聊天应用"
description: "用 Server-Sent Events 在 ASP.NET Core 中实现 AI 聊天响应的逐字流式输出，让用户不用等待完整生成就能看到结果。从 SSE 原理到完整端点实现，一篇就能跑通。"
tags: ["ASP.NET Core", "Server-Sent Events", "AI", "SSE", "Minimal API"]
slug: "building-ai-chat-aspnetcore-sse"
source: "https://www.c-sharpcorner.com/article/building-ai-chat-applications-with-asp-net-core-and-server-sent-events/"
ogImage: "../../assets/967/01-cover.png"
---

AI 聊天应用已经成为现代软件的标配功能。不管是客服机器人、内部知识助手，还是 AI 编程工具，用户的期待都一样：问题发出去，答案马上开始往外蹦，而不是盯着空白页面等十几秒。

这正是 Server-Sent Events（SSE）派上用场的地方。相比等 AI 把完整回复生成好再一次性返回，服务器可以生成一段就推送一段，用户在浏览器里看到的是逐字逐句流出来的效果——和 ChatGPT、Copilot 那种体验一样。

这篇文章会讲清楚 SSE 是什么、怎么在 ASP.NET Core 里实现，以及如何用它构建一个能实时流式输出 AI 回复的聊天应用。

## SSE 是什么

Server-Sent Events 是一种让服务器通过单条 HTTP 连接持续向客户端推送数据的技术。

和传统的 HTTP 请求不同——传统模式下客户端发请求、等服务端准备好完整响应再返回——SSE 把连接一直保持打开，有新数据就立即推送。连接建立后，数据只从服务端流向客户端，方向单一。

对 AI 聊天来说，这意味着用户可以看着回复一个字一个字地生成，不用等完整答案。

SSE 常见的使用场景：

- AI 聊天应用
- 实时通知
- 股票行情更新
- 体育比分推送
- 系统监控面板
- 长时间任务的进度更新

## 为什么不用轮询

很多应用用轮询来模拟"实时"效果——客户端每隔几秒发一次请求，问服务器有没有新数据。

轮询能跑，但问题也很明显：

- 大量无意义的网络请求
- 服务器负载偏高
- 更新延迟不可控
- 用户体验割裂

而 SSE 的做法是建立一次连接，之后服务器有新内容就主动推送。两者的差别一目了然：

| 轮询           | Server-Sent Events |
| -------------- | ------------------ |
| 多次 HTTP 请求 | 单条长连接         |
| 网络开销大     | 开销更低           |
| 更新有延迟     | 接近实时           |
| 服务器处理量大 | 流式传输更高效     |

如果数据流向主要是「服务端 → 客户端」，SSE 通常比轮询更简单也更好用。如果需要双向通信，那才考虑 WebSocket。

## 在 ASP.NET Core 中创建 SSE 端点

ASP.NET Core 内置了对 SSE 的支持，不需要额外安装包。核心思路很简单：设置响应头、写入数据、立即刷新。

下面是一个 Minimal API 的示例，向客户端依次推送 5 条消息：

```csharp
app.MapGet("/chat/stream", async (HttpContext context) =>
{
    context.Response.Headers.Append("Content-Type", "text/event-stream");

    for (int i = 1; i <= 5; i++)
    {
        await context.Response.WriteAsync($"data: Message {i}\n\n");
        await context.Response.Body.FlushAsync();
        await Task.Delay(1000);
    }
});
```

三个关键点：

1. **响应头设为 `text/event-stream`**：浏览器靠这个头识别 SSE 连接。
2. **每条消息以 `data:` 开头**：这是 SSE 协议规定的格式，消息以 `\n\n` 结尾。
3. **每次写入后立即 `FlushAsync`**：不刷新的话，数据可能被缓冲在服务端，客户端收不到实时更新。

保持连接打开直到流式传输结束即可。

## 浏览器端接收流式消息

客户端用 JavaScript 内置的 `EventSource` API 来接收 SSE，不需要任何第三方库：

```javascript
const source = new EventSource("/chat/stream");

source.onmessage = function (event) {
  console.log(event.data);
};
```

服务器每推送一条新消息，浏览器立马收到，不需要刷新页面。这就是「实时」体验的基础。

如果是聊天界面，把 `event.data` 追加到对话区域就行，用户看到的效果就是逐条、逐段地出字。

## 流式传输 AI 响应

上面的例子只是推送固定消息。换成 AI 模型，思路完全一样，只是数据源变成了模型逐块生成的文本：

```csharp
foreach (var chunk in aiResponseChunks)
{
    await context.Response.WriteAsync($"data: {chunk}\n\n");
    await context.Response.Body.FlushAsync();
}
```

`aiResponseChunks` 可以来自任何 AI 服务——Azure OpenAI、OpenAI、本地 Ollama 模型都可以。关键是上游的 AI 调用也要开启流式模式，让模型边生成边返回 token，服务端拿到一个 chunk 就立即推送给前端。

这种做法让应用「感觉更快」，因为用户不用等完整回答，第一秒就能开始阅读。

## 完整聊天流程

把上面的片段串起来，一个典型的 AI 聊天应用流程是这样的：

1. 用户在浏览器输入问题。
2. 浏览器把问题发送到 ASP.NET Core 服务端。
3. 服务端将请求转发给 AI 模型（开启流式模式）。
4. AI 模型逐块生成回复文本。
5. ASP.NET Core 通过 SSE 连接把每个 chunk 推给客户端。
6. 浏览器实时更新聊天窗口。

整个过程只需要一个 `EventSource` 连接和一个流式 SSE 端点。不需要引入 SignalR、WebSocket 或其他复杂组件。

## 最佳实践

在实际项目中落地时，有几点值得特别留意：

- **每次写入后刷新响应流**。不刷新等于没推送，用户看到的还是空白。
- **妥善处理客户端断连**。用户关掉页面或网络断开时，服务端要及时释放资源，避免空转消耗。
- **流式输出小块文本**，不要攒成大段再发。块越小，用户的即时感越强。
- **全程使用异步编程**，保证服务端在等待 AI 生成时还能处理其他请求。
- **校验和清理用户输入**，之后再发送给 AI 模型，防止注入或越权。
- **如果聊天服务不公开，加上身份认证**。
- **记录错误日志并监控流式传输性能**。SSE 连接是长连接，出问题不容易马上发现。
- **考虑限流策略**，保护应用不被滥用。

对于只需要服务端到客户端单向推送的场景，SSE 的实现复杂度远低于 WebSocket，和 ASP.NET Core 的集成也非常自然。

## 结语

Server-Sent Events 为 ASP.NET Core 应用提供了一种轻量、高效的实时通信方式，尤其适合 AI 聊天这种「服务端生成、客户端消费」的模式。通过流式输出 AI 回复，你能让用户在第一秒就看到内容开始生成，而不是干等完整答案。

如果你的应用不需要双向通信（客户端不会频繁发数据给服务端），SSE 通常比 WebSocket 更合适——实现更简单、调试更容易、和 HTTP 基础设施的兼容性也更好。

如果你平时用 ASP.NET Core 做后端，不妨在下一个 AI 功能里试试 SSE，整套体验比「请求-等待-返回」流畅不少。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Building AI Chat Applications with ASP.NET Core and Server-Sent Events - C# Corner](https://www.c-sharpcorner.com/article/building-ai-chat-applications-with-asp-net-core-and-server-sent-events/)
- [MDN: Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [ASP.NET Core Minimal APIs](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis)
