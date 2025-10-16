---
pubDatetime: 2024-04-28
tags: [".NET", "ASP.NET Core", "Architecture"]
source: https://code-maze.com/aspnetcore-using-server-sent-events-for-realtime-updates/
author: Thages Wilson de Almeida
title: 在 ASP.NET Core 中使用Server-Sent Events进行实时更新
description: 在 ASP.NET Core 中发现Server-Sent Events，学习它们的特性、优势，以及如何实现它们进行实时的、基于事件的更新。
---

> ## 摘要
>
> 在 ASP.NET Core 中使用Server-Sent Events：学习它们的特性、优势，以及如何实现它们进行实时的、基于事件的更新。
>
> 原文 [Using Server-Sent Events for Realtime Updates in ASP.NET Core](https://code-maze.com/aspnetcore-using-server-sent-events-for-realtime-updates/)

---

在本文中，我们将讨论 ASP.NET Core 中的Server-Sent Events。我们将看到它们是什么，它们有哪些特性、优势以及如何实施它们。

要下载此文章的源代码，您可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/aspnetcore-features/ServerSentEventsForRealtimeUpdates)。

那么，让我们开始吧。

## 什么是Server-Sent Events

**Server-Sent Events（SSE）协议允许服务器通过 HTTP 连接向客户端发送实时的、事件驱动的更新，而无需客户端请求这些更新。**它使用 HTTP 作为服务器和客户端之间的通信协议。SSE 消除了手动查询服务器或建立多个连接以向客户端交付更改的需求。

## Server-Sent Events的关键特性

在服务器和客户端之间建立的连接中，服务器可以向客户端提供**实时的、事件驱动的更新**。客户端界面监听服务器事件，这些事件可以包含特定的身份。

使用 SSE，只有服务器可以向连接的客户端发送数据。这就是为什么我们称它为**单向通信**渠道。客户端不能向服务器发送数据回去。

SSE 客户端-服务器连接是在整个客户端生命周期中维持的**持久 HTTP 连接**。

SSE 消息通过 HTTP 以纯文本形式发送。因为 SSE 是一个**基于文本的协议**，其字段作为文本字符串作为事件字段发送。

客户端界面将尝试保持连接打开。一旦断开连接，它将尝试重新连接到服务器以保持更新。SSE 通过自动重新建立连接提供了**弹性连接**。这允许事件继续。

使用 SSE，可以从与客户端不同的来源或域接收更新。我们可以配置服务器的**跨域资源共享（CORS）**规则以允许特定的来源和域。

## Server-Sent Events是如何工作的？

SSE 通过启用服务器和客户端之间的实时、单向通信，消除了手动服务器查询和多个连接的需求。一旦建立，服务器将事件驱动的更改通过单个 HTTP 连接发送给客户端。服务器可以单独提交新事件，同时保持 HTTP 响应打开。[EventSource API](https://developer.mozilla.org/en-US/docs/Web/API/EventSource) 是一个标准的客户端接口，它打开到 HTTP 服务器的持久连接，并且连接保持打开状态直到通过调用 `EventSource.close()` 关闭。

## WebSockets 与Server-Sent Events的比较

WebSockets 和Server-Sent Events之间的主要区别是通信的方向。**WebSockets 是双向的**，允许客户端和服务器之间的通信，而 **SSE 是单向的**，只允许客户端从服务器接收数据。另一个区别是，虽然 SSE 具有自动重连、事件 ID 和任意发送事件的特性，但 WebSockets 可以检测到客户端失去连接。另外，WebSockets 可以发送二进制和 UTF-8 数据，而 SSE 仅限于 UTF-8 数据。SSE 的一个缺点是每个浏览器最多允许六个开放连接。

## 使用Server-Sent Events构建应用程序

我们可以在各种场景和应用程序中使用Server-Sent Events，如新闻推送、通知或实时监控仪表板。让我们使用 ASP.NET Core Web API 实现一个简单的 SSE 应用程序。**我们的应用程序将是一个倒计时计时器，从 30 倒计时到 0。**

服务器每秒发送数据，并将其递减，直到达到 0。这个循环在服务器客户端连接存活时继续进行。

### 创建一个 ASP.NET Core 项目

首先，让我们使用 dotnet CLI 创建我们的项目：

```bash
dotnet new webapi -n ServerSentEventsForRealtimeUpdates.Server
```

我们使用 `new` 命令创建一个新项目，`webapi` 指定模板，使用 `-n` 选项为我们的项目设置一个名称。

### 创建 Timer 服务

让我们创建一个从 `ICounterService` 继承的 `CounterService` 类，并实现几个方法：

```csharp
public class CounterService : ICounterService
{
    private const int StartValueCounter = 30;
    private const int MillisecondsDelay = 1000;
    public async Task CountdownDelay(CancellationToken cancellationToken)
    {
        await Task.Delay(MillisecondsDelay, cancellationToken);
    }
    public int StartValue
    {
        get => StartValueCounter;
    }
}
```

首先，我们声明了两个常量：`StartValueCounter` 和 `MillisecondsDelay`。

现在，我们实现了 `CountdownDelay()` 方法，它只是调用 `Task.Delay()` 方法并传递我们声明的 `MillisecondsDelay` 常量。

然后，我们声明 `StartValue` 作为 `StartValueCounter` 常量的 getter。

## 实现Server-Sent Events端点

现在，让我们修改我们的 `Program` 类，这样我们就可以有我们将用于建立服务器-客户端连接的 SSE 端点了。

#### 启用跨域请求 (CORS)

首先，让我们启用跨域请求 (CORS)，这样客户端才能连接到我们的服务器：

```csharp
const string myCors = "client";
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddCors(options =>
{
    options.AddPolicy(myCors,
        policy =>
        {
            policy.AllowAnyOrigin()
                .AllowAnyHeader()
                .AllowAnyMethod();
        });
});
```

在这里，我们声明了 `myCors` 常量，为 CORS 策略命名，并使用 `AddPolicy()` 方法将策略添加到 CORS 选项中。

现在，我们可以将策略设置到 `WebApplication` 中：

```csharp
app.UseCors(myCors);
```

我们调用 `IApplicationBuilder.UseCors()` 方法，传递我们之前创建的相同常量。

为了能够使用服务方法，让我们注册 `CounterService`：

```csharp
builder.Services.AddScoped<ICounterService, CounterService>();
```

我们使用 `AddScoped()` 方法将 `CounterService` 服务作为 `ICounterService` 实现添加到服务集合中。

#### 创建路由处理程序

现在，让我们使用 `app.MapGet()` 添加一个路由端点：

```csharp
app.MapGet("/sse", async Task (HttpContext ctx, ICounterService service, CancellationToken token) =>
{
    ctx.Response.Headers.Append(HeaderNames.ContentType, "text/event-stream");
    var count = service.StartValue;
    while (count >= 0)
    {
        token.ThrowIfCancellationRequested();

        await service.CountdownDelay(token);
        await ctx.Response.WriteAsync($"data: {count}\n\n", cancellationToken: token);
        await ctx.Response.Body.FlushAsync(cancellationToken: token);
        count--;
    }
    await ctx.Response.CompleteAsync();
});
```

我们将端点设置为 `/sse` 并注入 `HttpContext`、`ICounterService` 和 `CancellationToken`。正如我们所说，Server-Sent Events是基于文本的协议，所以我们在头部中将 `ContentType` 设置为 `text/event-stream`。

我们创建一个 `while` 循环来检查计数器何时完成，并添加更新客户端的逻辑。

然后，我们通过使用 `service.CountdownDelay()` 等待一秒钟才继续。

我们必须以 `$"data: {<DataToSend>}\n\n"` 格式定义响应，否则它将不起作用。在我们的示例中，我们使用了 `count` 变量作为数据。

最后，我们使用 `HttpResponse.FlushAsync()` 方法将其发送给客户端。

### 实施客户端

现在我们已经实现了服务器发送的事件，让我们实现我们的客户端：

```html
<div id="counter" />
```

我们在 HTML 文件中创建一个简单的 `div` 容器，ID 为 `counter`，这将是计数器值的占位符。

现在，让我们实现我们将用来连接到服务器的脚本：

```html
<script>
  async function ServerConnection() {
    const eventSource = new EventSource("https://localhost:7095/sse");
    eventSource.onmessage = event => {
      document.getElementById("counter").innerText = event.data.replace(
        /(\r\n|\n|\r)/gm,
        ""
      );
    };
  }
  ServerConnection();
</script>
```

我们在 `</body>` 标签前添加一个新的 `<script>` 标签，并创建一个新的 JavaScript 异步函数 `ServerConnection()`。

我们现在可以创建服务器发送的事件连接了。所以，我们创建了 `EventSource` 的一个新实例，传递服务器 `URL`。然后，我们调用 `EventSource.onmessage` 方法来接收服务器数据。我们使用 `document.getElementById()` 方法获取设置了 `id` 属性为 _counter_ 的元素，并将此元素的内部文本设置为 `event.data` 的值。最后，我们将数据末尾的换行符 `\r` 和 `\n` 字符替换掉。

## 结论

在这篇文章中，我们学习了Server-Sent Events如何用于实时更新。我们看到了一些应用场景以及它与 WebSocket 的区别。然后，我们在一个简单的 ASP.NET Core Web API 中实现了它。使用Server-Sent Events有一些优点，但也有一些缺点。我们必须评估整个上下文以选择最佳技术以适用于我们的应用程序。
