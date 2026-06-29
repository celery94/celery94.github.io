---
pubDatetime: 2026-06-29T12:51:27+08:00
title: "HttpClient DNS 问题：PooledConnectionLifetime 与 SocketsHttpHandler"
description: "深入理解 HttpClient DNS 过期的根因——TCP 连接池使 DNS 只解析一次。掌握 SocketsHttpHandler.PooledConnectionLifetime 和 IHttpClientFactory handler 轮换两种修复方式，以及在 Kubernetes 环境中的调优策略。"
tags: ["CSharp", ".NET", "HttpClient", "DNS", "Kubernetes"]
slug: "httpclient-dns-pooledconnectionlifetime"
ogImage: "../../assets/911/01-cover.png"
source: "https://www.devleader.ca/2026/06/28/httpclient-dns-issues-in-c-and-net-pooledconnectionlifetime-and-socketshttphandler"
---

有一个非常具体的 bug 会在生产环境中咬 .NET 开发者一口，往往发生在部署或 Kubernetes 滚动更新的几个小时之后。症状很微妙：流量不再到达新 pod、一切都看起来健康的服务返回错误、或者负载均衡悄悄失效。根因几乎总是同一个——**HttpClient DNS 过期**。一个长期存活的 `HttpClient` 解析过一次主机名，把结果缓存在打开的 TCP 连接里，然后再也不问 DNS 了。

修复听起来简单，但真正把它做对需要理解 .NET 怎么管理连接池、`SocketsHttpHandler` 在底层做了什么、以及 `IHttpClientFactory` 为什么存在。

## 复用 vs 新鲜度：HttpClient DNS 悖论

每个 .NET 开发者早期都听到过同样的警告：不要每个请求都创建新的 `HttpClient`。理由很对——`HttpClient` 背后是连接池，新建实例绕过池、破坏底层 TCP 连接并开新的。高负载下这会导致 **socket 耗尽**，操作系统端口用尽、连接失败、应用崩溃。

所以修复是复用 `HttpClient`：注册成单例，放在 DI 里，让它一直活着。

然后你撞上了另一个问题：**DNS 过期**。一个长期存活的 `HttpClient` 只解析一次 DNS 主机名——在它第一次向那个主机建立 TCP 连接的时候。它为了性能在池里保持这个连接打开。只要连接还活着，客户端就再也不问 DNS 了，只用它已经知道的 IP。在 TCP 层面这完全正确。问题在于现代云环境里 IP 地址经常变。

Kubernetes 重新调度 pod，负载均衡器轮换端点，蓝绿部署切换流量。DNS 记录更新了，但你的 `HttpClient` 还在跟旧 IP 说话，因为它有一个完美的、开放的 TCP 连接。从 .NET 的角度看没问题，从运维角度看，你的服务拒绝接纳新后端。

这就是悖论：不复用 `HttpClient` 导致 socket 耗尽，复用它导致 DNS 过期。解法在中间：带显式生命周期限制的连接池管理。

## TCP 连接和 DNS 怎么协作

`HttpClient` 第一次请求 `https://api.example.com` 时，以下序列发生：

1. OS 通过 DNS 把 `api.example.com` 解析成 IP。DNS 响应包含 TTL，告诉 OS 缓存这个 IP 多久。云环境中常见 TTL 是 5 到 30 秒。
2. 向解析出的 IP 的 443 端口建立 TCP 连接。
3. TLS 握手。
4. HTTP 请求发送、响应接收。
5. TCP 连接返回连接池供复用。

下一次请求时，第 5 步先触发。`HttpClient` 在池里找到现有的到那个 IP 的打开连接然后复用——完全跳过第 1 到 4 步。这是性能收益。但这也意味着只要连接还活着，DNS 再也不被咨询。

操作系统有自己的带 TTL 过期的 DNS 缓存。但这个缓存只在新建连接时才重要。如果池里总有一个健康的连接，OS DNS 缓存永远没机会交出新的 IP 地址。

这是有意为之的设计。TCP 连接不是 DNS 感知的，它们连接到一个 IP。如果 IP 变了，现有连接仍然有效——它仍然连着原始目的地。只有新连接才会拿到更新的 DNS 记录。

## 轮询 DNS：为什么你的 HttpClient 绕过了负载均衡

`HttpClient` 的 DNS 问题在轮询 DNS 下最明显。很多负载均衡器和服务网格为单个主机名广告多个 IP，每次 DNS 查询返回不同地址，把流量分散到多个后端。

`HttpClient` 的池化连接完全绕过了这个机制。第一次查询返回一个 IP，到那个 IP 的连接进入了池。之后每次请求复用这个连接。从 DNS 服务器视角它准备给出不同 IP 分散负载，从客户端视角所有流量永远流向第一个后端。

在 Kubernetes 集群里这特别突出。像 `payment-service.default.svc.cluster.local` 这样的服务主机名在 pod 扩缩或被替换时可能解析到不同 pod IP。集群期望客户端定期重新解析，这样流量才会被分发。一个从不重新解析的 `HttpClient` 把所有连接固定在了启动时活着的那些 IP 上。

如果那些旧 pod 还在跑，服务能工作但负载严重不均衡。如果那些 pod 已经被替换，服务开始失败——因为客户端试图跟已经没有东西在监听的 IP 通信。

## Socket 耗尽：连接太多的后果

再看悖论的另一面。如果试图通过每个请求创建新 `HttpClient` 来解决 DNS 过期呢？

每个 `HttpClient` 实例创建新的 TCP 连接，OS 从临时端口范围分配源端口——Linux 上通常是 49152 到 65535，大约 16,000 个端口。负载下，大量外部 HTTP 调用的服务可能几秒内耗尽这个范围。

端口耗尽后，新连接尝试以 `SocketException: address already in use` 失败。应用在每个出站 HTTP 调用上开始抛异常。唯一恢复方式是等待现有连接超时释放端口——根据 OS 的 TCP_WAIT 配置可能需要几分钟。

"每次请求后 Dispose `HttpClient`"的天真修复在这里没用。底层 TCP 连接关闭后进入 TIME_WAIT 状态，OS 默认最长持有端口 240 秒。Dispose `HttpClient` 对象不会立即释放端口。

复用 `HttpClient` 通过保持一个小的持久连接池解决了 socket 耗尽。但持久连接导致 DNS 过期。两个问题都由同一个方案解决：**有界的连接生命周期**。

## SocketsHttpHandler.PooledConnectionLifetime：修复方案

对长期存活的 `HttpClient` 实例，DNS 过期的直接解决方法是 `SocketsHttpHandler.PooledConnectionLifetime`。这个属性告诉 handler 关闭任何存活超过指定时长的池化连接。连接关闭后，下一次请求建立新连接——意味着新的 DNS 查询。

```csharp
var handler = new SocketsHttpHandler
{
    // 2 分钟后退役连接 —— 强制 DNS 重新解析
    PooledConnectionLifetime = TimeSpan.FromMinutes(2),

    // 可选：调优空闲连接在池里的存活时间
    PooledConnectionIdleTimeout = TimeSpan.FromMinutes(1),

    // 可选：控制每端点的连接数
    MaxConnectionsPerServer = 10
};

// 这个 HttpClient 可以安全地作为单例使用
// DNS 大约每 2 分钟刷新一次
var client = new HttpClient(handler);
```

关键点是 `PooledConnectionLifetime` **不会中断在途请求**。它标记连接在指定时间后退役。当一个超过生命周期的连接完成服务当前请求后，它被关闭而不是返回池。下次请求建立新连接。

默认值是 `Timeout.InfiniteTimeSpan`（除非你配置，否则连接永不过期）——这正是 DNS 过期问题。大多数云环境的推荐值是 1 到 5 分钟，取决于 DNS TTL 和集群里 pod IP 的变更频率。

## IHttpClientFactory 的 Handler 轮换

`IHttpClientFactory` 用更高层的方式解决 DNS 过期问题。它不直接配置 `PooledConnectionLifetime`，而是管理一个按定时器轮换的 `HttpMessageHandler` 实例池。

工厂创建 handler，按请求分发给 `HttpClient` 实例，并追踪每个 handler 的创建时间。在可配置的生命周期后（默认 2 分钟），工厂停止分发旧 handler 并创建新的。旧 handler 被允许排干——正在用它的客户端可以完成请求——然后被 Dispose。

新 handler 创建时有一个空的连接池。通过新 handler 的第一个请求建立全新的 TCP 连接进行全新的 DNS 查询。这就是保持 DNS 最新而无需直接配置 `SocketsHttpHandler` 的机制。

```csharp
builder.Services.AddHttpClient("PaymentService", client =>
{
    client.BaseAddress = new Uri("https://payment-service.default.svc.cluster.local");
    client.Timeout = TimeSpan.FromSeconds(30);
});
```

用 `IHttpClientFactory` 并调用 `CreateClient("PaymentService")` 的任何服务拿到一个包装了最多 2 分钟老的 handler 的新 `HttpClient`。DNS 大约每 2 分钟刷新一次，不需要额外配置。

## 用 SetHandlerLifetime 自定义轮换

2 分钟默认对很多环境是合理的，但 pod 扩缩激进的 Kubernetes 集群可能需要更短的值：

```csharp
// Kubernetes 环境：每 30 秒轮换 handler
builder.Services.AddHttpClient("KubernetesService", client =>
{
    client.BaseAddress = new Uri("https://my-service.default.svc.cluster.local");
})
.SetHandlerLifetime(TimeSpan.FromSeconds(30));

// 稳定的外部 API：每 10 分钟轮换
builder.Services.AddHttpClient("StableExternalApi", client =>
{
    client.BaseAddress = new Uri("https://stable.external.api.com");
})
.SetHandlerLifetime(TimeSpan.FromMinutes(10));
```

两者结合使用时——同时设 `PooledConnectionLifetime` 和 `SetHandlerLifetime`——较短的哪个实际控制 DNS 刷新频率。

## Kubernetes 服务发现与短 TTL DNS

Kubernetes 让 DNS 过期问题远比传统部署严重。对 ClusterIP 服务，ClusterIP 本身是稳定的——pod 重启时不会变，所以 DNS 过期不是问题。

问题出现在 **headless 服务**（`clusterIP: None`）。headless 服务在 DNS 响应中直接返回各 pod 的 IP。pod 被替换时旧 IP 消失、新 pod IP 出现。有旧连接的客户端仍然指着已经消失的旧 pod。

它同样出现在外部服务端点、Istio 服务网格配置以及任何涉及 IP 轮换的负载均衡主机名场景中。Kubernetes 服务条目的 DNS TTL 通常是 5 到 30 秒。你的 `PooledConnectionLifetime` 或 handler 轮换间隔应该设置成能合理及时捕捉 DNS 变更的值——但又不能激进到不断拆除健康连接。

大多数生产 Kubernetes 负载，**30 到 90 秒**的 handler 生命周期能平衡这些关切。有快速轮换 pod 的 headless 服务，**15 到 30 秒**更合适。

## 完整 .NET 10 示例

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System.Net.Http;

// ====================
// 方案 A：带 SocketsHttpHandler 的单例 HttpClient
// 在 DI 容器外使用
// ====================

var handler = new SocketsHttpHandler
{
    PooledConnectionLifetime = TimeSpan.FromMinutes(2),
    PooledConnectionIdleTimeout = TimeSpan.FromMinutes(1),
    MaxConnectionsPerServer = 20,
    EnableMultipleHttp2Connections = true,
};

HttpClient sharedClient = new(handler)
{
    Timeout = TimeSpan.FromSeconds(30),
    DefaultRequestVersion = new Version(2, 0),
    DefaultVersionPolicy = HttpVersionPolicy.RequestVersionOrHigher,
};

// ====================
// 方案 B：IHttpClientFactory + 命名客户端（推荐）
// 用于有 DI 容器的 ASP.NET Core 应用
// ====================

var builder = Host.CreateApplicationBuilder();

// 内部 Kubernetes 服务——短生命周期
builder.Services.AddHttpClient("InternalService", client =>
{
    client.BaseAddress = new Uri("https://order-service.orders.svc.cluster.local");
    client.Timeout = TimeSpan.FromSeconds(10);
})
.ConfigurePrimaryHttpMessageHandler(() => new SocketsHttpHandler
{
    PooledConnectionLifetime = TimeSpan.FromSeconds(30),
    PooledConnectionIdleTimeout = TimeSpan.FromSeconds(20),
})
.SetHandlerLifetime(TimeSpan.FromSeconds(30));

// 稳定的外部 API——长生命周期
builder.Services.AddHttpClient("ExternalPaymentApi", client =>
{
    client.BaseAddress = new Uri("https://api.payment-provider.com");
    client.Timeout = TimeSpan.FromSeconds(30);
})
.ConfigurePrimaryHttpMessageHandler(() => new SocketsHttpHandler
{
    PooledConnectionLifetime = TimeSpan.FromMinutes(5),
    PooledConnectionIdleTimeout = TimeSpan.FromMinutes(2),
})
.SetHandlerLifetime(TimeSpan.FromMinutes(5));
```

## 运行时验证 DNS 刷新

用 `SocketsHttpHandler.ConnectCallback`（.NET 5+）可以在测试中观察新连接何时建立：

```csharp
var connectionAttempts = 0;

var handler = new SocketsHttpHandler
{
    PooledConnectionLifetime = TimeSpan.FromSeconds(10),
    ConnectCallback = async (context, cancellationToken) =>
    {
        Interlocked.Increment(ref connectionAttempts);
        Console.WriteLine(
            $"[{DateTime.UtcNow:HH:mm:ss}] New TCP connection to {context.DnsEndPoint.Host}");

        var socket = new Socket(SocketType.Stream, ProtocolType.Tcp) { NoDelay = true };
        await socket.ConnectAsync(context.DnsEndPoint, cancellationToken);
        return new NetworkStream(socket, ownsSocket: true);
    }
};

var client = new HttpClient(handler);

for (int i = 0; i < 10; i++)
{
    var response = await client.GetAsync("https://httpbin.org/get");
    Console.WriteLine($"Request {i + 1}: {response.StatusCode}");
    await Task.Delay(TimeSpan.FromSeconds(3));
}
```

在 Linux 上也可以用 `watch -n 1 'ss -tn state established | grep :443'` 观察活跃的 TCP 连接。你应该能看到连接数保持稳定（在 `MaxConnectionsPerServer` 限制内），在 handler 轮换时偶尔降到零再重建。

## 总结

HttpClient DNS 过期问题是那种在开发环境容易被忽略、但在云原生生产环境变得痛苦可见的问题。核心认知是：**TCP 连接不是 DNS 感知的**——一旦建立到某个 IP 的连接，只要连接不关闭就一直用那个 IP。长期存活的连接池让基于 DNS 的负载均衡失效，并且捕捉不到 Kubernetes 中的 pod 变更。

- **`SocketsHttpHandler.PooledConnectionLifetime`** 是单例 `HttpClient` 的正确修复，让你显式控制连接在退役和用新 DNS 查询重建之前在池里待多久。
- **`IHttpClientFactory`** 在 handler 层面提供同样的保证，默认 2 分钟轮换覆盖最常见场景，`SetHandlerLifetime()` 可用于调优。
- **ASP.NET Core 应用**推荐用 `IHttpClientFactory`，控制台应用或 DI 容器外服务用单例 `HttpClient` + `SocketsHttpHandler.PooledConnectionLifetime`。

## 参考

- [HttpClient DNS Issues in C# — Dev Leader](https://www.devleader.ca/2026/06/28/httpclient-dns-issues-in-c-and-net-pooledconnectionlifetime-and-socketshttphandler)
- [HttpClient in C#: The Complete Guide](https://www.devleader.ca/2026/06/26/httpclient-in-c-the-complete-guide-for-net-developers)
- [IHttpClientFactory docs — Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/core/extensions/httpclient-factory)
- [HttpClient guidelines — Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/fundamentals/networking/http/httpclient-guidelines)
