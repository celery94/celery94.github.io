---
pubDatetime: 2026-10-12T08:54:00+08:00
title: "SSE 鉴权：五种方案怎么选"
description: "EventSource 不能发自定义请求头，浏览器端 SSE 鉴权因此只剩三条路。本文把 Cookie、短期令牌、fetch-event-source 与 HttpClient 放回各自场景，并列出 CORS 凭证规则和令牌过期重连这些坑。"
tags: ["ASP.NET Core", ".NET", "SSE", "认证授权", "Blazor"]
slug: "sse-with-authentication"
ogImage: "../../assets/1091/01-cover.jpg"
source: "https://tiger4589.github.io/2026/10/02/sse-with-authentication.html"
---

给 SSE 端点加上 `.RequireAuthorization()` 之后，浏览器控制台开始刷 401，而同样的接口用 curl 带 Bearer 头访问却是正常的。问题不在服务端授权配置，在于浏览器原生的 `EventSource` 根本不支持自定义请求头——它没有任何地方可以放 `Authorization`。

Paul Karam 在[原文](https://tiger4589.github.io/2026/10/02/sse-with-authentication.html)里把这个问题拆成五条可行路径，并给了一个 Aspire 演示项目，每个方案对应一个页面。下面按「客户端是什么」重新组织这五种做法，重点放在各自的真正限制上。

## 先明确约束：SSE 没有绕开认证中间件

一个常见的误解是 SSE 是特殊协议、会跳过认证管道。实际上它就是一个普通的 HTTP 请求，只是响应是 `text/event-stream` 且不结束。ASP.NET Core 端照常使用认证中间件，最小 API 里写下 `.RequireAuthorization()` 就够了。

所以真正需要解决的是「客户端怎么把凭证带过去」，而可选手段只有三种：Cookie 自动带、放到 URL 查询串、换成能发请求头的客户端。五种方案都是这三种手段的组合。

## 方案一：同源 Cookie，最简单

如果前端和 API 同源，浏览器已有认证 Cookie，`EventSource` 会自动把它带上：

```javascript
const events = new EventSource("/api/events");
```

服务端不需要为 SSE 做任何额外配置：

```csharp
app.MapGet("/events", (CancellationToken ct) => Results.ServerSentEvents(StreamEvents(ct)))
   .RequireAuthorization();
```

`EventSource` 原生自带断线重连，这一条路径上重连也能正常带上 Cookie，因此它的重连行为是最省心的。限制也很直接：前提是你本来就使用 Cookie 认证。

## 方案二：跨域 Cookie，必须配 CORS 凭证

前端在 `https://app.example.com`、API 在 `https://api.example.com` 时，跨域请求默认不带 Cookie，需要显式打开：

```javascript
const events = new EventSource("https://api.example.com/api/events", {
  withCredentials: true,
});
```

服务端的 CORS 策略也必须允许凭证，并且**不能用 `AllowAnyOrigin()`**：

```csharp
builder.Services.AddCors(options =>
{
    options.AddPolicy("frontend", policy =>
    {
        policy
            .WithOrigins("https://app.example.com")
            .AllowCredentials()
            .AllowAnyHeader()
            .AllowAnyMethod();
    });
});
```

`AllowAnyOrigin()` 与 `AllowCredentials()` 同时使用会被框架拒绝，因为这等于把凭证发给任意站点。除了 CORS，这条路径还要面对两个浏览器侧的变量：Cookie 的 `SameSite` 设置，以及第三方 Cookie 拦截策略。API 域名如果被浏览器视为第三方，即使 `withCredentials: true` 也可能带不上 Cookie。这一条是排查跨域 SSE 401 时最该先看的地方。

## 方案三：短期令牌，原生 EventSource 的唯一出路

如果认证体系基于 Bearer Token、没有 Cookie，又不允许引入前端库，就只剩 URL 查询串这一条路。直接在查询串里放访问令牌不安全——URL 会进服务器日志、代理日志和浏览器历史。原文的做法是把风险窗口压到最小：签发一个 10 秒有效、且只能使用一次的短期令牌（SLT）。

令牌存储用一个并发字典加过期任务：

```csharp
public class ShortLivedTokenStore
{
    private readonly ConcurrentDictionary<string, string> _tokenStore = [];
    private readonly TimeSpan _lifeTime = TimeSpan.FromSeconds(10);

    public string GetToken(string userId)
    {
        var token = Guid.NewGuid().ToString();
        _tokenStore.TryAdd(token, userId);

        _ = Task.Run(async () =>
        {
            await Task.Delay(_lifeTime);
            _tokenStore.TryRemove(token, out _);
        });

        return token;
    }

    public bool TryConsume(string token, [NotNullWhen(true)] out string? userId)
        => _tokenStore.TryRemove(token, out userId);
}
```

`TryConsume` 用 `TryRemove` 而不是查询，这一步是「一次性」语义的来源：令牌在被校验的同时就被消费掉，重放拿不到第二次机会。

签发端点要求用户已认证：

```csharp
app.MapGet("/request-slt", (HttpContext context, ShortLivedTokenStore store) =>
    {
        string? userId = context.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

        if (string.IsNullOrWhiteSpace(userId))
        {
            return Results.Unauthorized();
        }

        return Results.Ok(store.GetToken(userId));
    })
    .WithName("RequestShortLivedToken")
    .RequireAuthorization();
```

SSE 端点则从查询串取令牌并消费：

```csharp
app.MapGet("/events-slt", (string shortLivedToken, ShortLivedTokenStore store, CancellationToken cancellationToken) =>
{
    if (!store.TryConsume(shortLivedToken, out _))
    {
        return Results.Unauthorized();
    }

    int count = 0;

    async IAsyncEnumerable<int> StreamEvents([EnumeratorCancellation] CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            yield return count++;

            try
            {
                await Task.Delay(1000, ct);
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested)
            {
                yield break;
            }
        }
    }

    return Results.ServerSentEvents(StreamEvents(cancellationToken));
})
.WithName("GetEventsWithShortLivedToken");
```

客户端把令牌拼进 URL：

```javascript
export function connect(
  id,
  url,
  dotNetObject,
  messageCallback,
  errorCallback,
  shortLivedToken
) {
  disconnect(id);

  const source = new EventSource(
    `${url}?shortLivedToken=${encodeURIComponent(shortLivedToken)}`
  );

  source.onmessage = event => {
    dotNetObject.invokeMethodAsync(messageCallback, id, event.data);
  };

  source.onerror = () => {
    dotNetObject.invokeMethodAsync(
      errorCallback,
      id,
      `Connection failed or was closed for ${url}.`
    );
    disconnect(id);
  };

  connections[id] = source;
}
```

这个方案有三个必须知道的边界。

第一，一次性令牌和自动重连天然冲突。按 HTML 规范，连接失败时 `EventSource` 会重连；但重连请求拿的是同一个已消费的令牌，服务端返回非 200 响应后，客户端会**永久关闭**这条连接，而不是继续重试。客户端必须把 `onerror` 当成「重新申请令牌并新建 `EventSource`」的信号，不能等它自己恢复。如果希望主动告诉客户端别再重连，规范也给了明确手段：服务端返回 `204 No Content`，客户端就会停止重连，这比让浏览器撞上一次 401 更干净。

第二，`Guid.NewGuid()` 不是安全随机数，只适合演示。生产环境换成 `RandomNumberGenerator.GetBytes(32)` 再做 Base64Url 编码。

第三，内存字典在单实例下能用，多实例部署时签发的令牌在另一台机器上不存在，重启还会全部丢失。这两点都要靠 `IDistributedCache` 或 Redis 解决。

## 方案四：fetch-event-source，用请求头发令牌

浏览器端如果可以用第三方库，`@microsoft/fetch-event-source` 通过 `fetch()` 实现 SSE，因此可以正常发送请求头，也不需要额外的服务端端点：

```javascript
import { fetchEventSource } from "https://cdn.jsdelivr.net/npm/@microsoft/fetch-event-source@2.0.1/+esm";

export async function connect(
  id,
  url,
  dotNetObject,
  messageCallback,
  errorCallback,
  token
) {
  disconnect(id);

  const controller = new AbortController();
  connections[id] = controller;

  try {
    await fetchEventSource(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      signal: controller.signal,
      onmessage(event) {
        dotNetObject.invokeMethodAsync(messageCallback, id, event.data);
      },
      onerror() {
        dotNetObject.invokeMethodAsync(
          errorCallback,
          id,
          `Connection failed or was closed for ${url}.`
        );
        controller.abort();
      },
    });
  } finally {
    if (connections[id] === controller) {
      delete connections[id];
    }
  }
}
```

代价是这几种方案里行为最需要自己兜住的一种。这个库在 `onerror` 不抛出异常时会持续重试，而且重试复用最初那次请求的令牌；页面被浏览器切到后台时连接默认也会关闭。也就是说，令牌过期后它不会自己去刷新，只会拿旧令牌反复撞墙。`onerror` 里主动 `abort()` 再触发一次取新令牌的重连，比让库自己重试更可控。

这个库目前停留在 2.0.1，已经很久没有更新。如果需要更长期的选择，可以看看 Azure SDK 的 `@azure/core-sse`：它提供 `createReconnectingSseStream`，支持 `maxRetries` 限制重试次数、通过非 200 响应（例如 204）主动停止重连，并且会把 `Last-Event-ID` 带到下一次请求上，重连后能接着上次的事件继续，而不是从零开始。

## 方案五：HttpClient，非浏览器客户端的正解

.NET 客户端（MAUI、桌面、控制台、后台服务）直接用 `HttpClient` 发请求头，没有前面所有限制。一个能跑的最小实现：

```csharp
public static class SimpleSse
{
    public static async IAsyncEnumerable<string> StreamAsync(
        HttpClient httpClient,
        string endpoint,
        string? bearerToken = null,
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, endpoint);
        request.Headers.TryAddWithoutValidation("Accept", "text/event-stream");

        if (!string.IsNullOrWhiteSpace(bearerToken))
        {
            request.Headers.Authorization =
                new AuthenticationHeaderValue("Bearer", bearerToken);
        }

        using var response = await httpClient.SendAsync(
            request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var reader = new StreamReader(stream);

        while (await reader.ReadLineAsync(cancellationToken) is { } line)
        {
            if (line.StartsWith("data:", StringComparison.Ordinal))
            {
                yield return line.Length > 5 && line[5] == ' ' ? line[6..] : line[5..];
            }
        }
    }
}
```

`HttpCompletionOption.ResponseHeadersRead` 是这里最关键的一个参数：不加它，`SendAsync` 会等到整个响应结束才返回，而 SSE 响应永远不会结束。剩下就是逐行读 `data:` 前缀。

这个解析只处理了 SSE 的最小子集，`id:`、`event:`、`retry:` 和跨多行的 `data` 都被丢掉了。原文作者为此提供了 `DotNetSseClient`（`dotnet add package DotNetSseClient`，当前 1.2.0，目标框架 `net10.0`），支持 keyed DI 注册、每次连接重新取令牌、401 时回调刷新令牌后重试一次、自动重连并带上 `Last-Event-ID`。如果只想自己处理解析，.NET 10 也内置了 `System.Net.ServerSentEvents.SseParser`，不必手写状态机。

另外值得注意的一点：SSE 的解析规则和你想的不完全一样。规范要求把连续的 `data:` 行用换行拼成一条消息，遇到空行才派发事件，`:` 开头的行是注释，服务端的 `retry:` 可以改写重连间隔。手写解析很容易在这些细节上出错，这也是优先用现成解析器的理由。

## 五种方案对照

| 方案               | 客户端                            | 自定义请求头       | 服务端改动                       | 重连行为                                     | 主要坑                                      |
| ------------------ | --------------------------------- | ------------------ | -------------------------------- | -------------------------------------------- | ------------------------------------------- |
| 同源 Cookie        | `EventSource`                     | 不需要             | 无                               | 原生自动重连正常                             | 依赖 Cookie 认证                            |
| 跨域 Cookie        | `EventSource` + `withCredentials` | 不需要             | CORS 允许凭证 + 明确来源         | 原生自动重连正常                             | `SameSite` 规则与第三方 Cookie 拦截         |
| 短期令牌           | `EventSource`                     | 不能，令牌走查询串 | 令牌端点、令牌存储、SSE 端点校验 | 一次性令牌下会中断，客户端须换新令牌重建连接 | 令牌可能进入 URL 与日志，必须短时效加一次性 |
| fetch-event-source | JS 库                             | 可以               | CORS 需允许 `Authorization` 头   | 由 `onerror` 控制，重试复用原令牌            | 不抛异常会无限重试；页面隐藏时默认断开      |
| HttpClient         | .NET 代码                         | 可以               | 无                               | 自己写重试逻辑                               | 手写解析只能覆盖最小子集                    |

选型的判断顺序可以简化成三个问题：

1. 客户端不是浏览器？用 `HttpClient`，解析交给 `DotNetSseClient` 或 `SseParser`。
2. 是浏览器，而且已经有 Cookie（或者走 BFF）？用 Cookie。同源最简单，跨域只要 CORS 配对正确也可以。
3. 是浏览器，用的是 Bearer Token 且没有 Cookie？能加库就用 `fetch-event-source`，令牌不进 URL；必须用原生 `EventSource` 才考虑短期令牌。

原文最后有一句值得保留的提醒：这不是一条必须遵守的规则，五种方案在 Blazor 里都能跑通，最终取决于你的技术栈和业务约束能不能接受对应的代价。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践方面的内容，包括 ASP.NET Core 实时通信的实践细节。

## 参考

- [How to Authenticate Server-Sent Events in ASP.NET Core — Paul Karam](https://tiger4589.github.io/2026/10/02/sse-with-authentication.html)
- [sse-with-auth 演示仓库](https://github.com/tiger4589/sse-with-auth)
- [dotnet-sse-client](https://github.com/tiger4589/dotnet-sse-client)
- [DotNetSseClient — NuGet](https://www.nuget.org/packages/DotNetSseClient/)
- [@microsoft/fetch-event-source — GitHub](https://github.com/Azure/fetch-event-source)
- [@azure/core-sse：可重连的 SSE 流](https://github.com/Azure/azure-sdk-for-js/blob/main/sdk/core/core-sse/README.md)
- [HTML 规范：Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [SseParser 类（System.Net.ServerSentEvents）— Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/api/system.net.serversentevents.sseparser)
- [ASP.NET Core 10 中的 ServerSentEvents 支持 — Microsoft Learn](https://learn.microsoft.com/en-us/aspnet/core/release-notes/aspnetcore-10.0)
