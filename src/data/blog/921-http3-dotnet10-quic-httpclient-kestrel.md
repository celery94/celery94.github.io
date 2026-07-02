---
pubDatetime: 2026-07-02T11:30:44+08:00
title: "HTTP/3 在 .NET 10：用 HttpClient 和 Kestrel 启用 QUIC"
description: "介绍 .NET 10 中 HTTP/3 的生产级支持，覆盖 QUIC 协议的核心优势（无队头阻塞、0-RTT、连接迁移）、HttpVersionPolicy 三种策略的适用场景、Kestrel 服务端配置、Alt-Svc 协商机制、本地测试方法以及容器与反向代理部署中的 UDP 注意事项。"
tags: ["HTTP/3", ".NET 10", "ASP.NET Core", "C#"]
slug: "http3-dotnet10-quic-httpclient-kestrel"
ogImage: "../../assets/921/01-cover.png"
source: "https://www.devleader.ca/2026/07/01/http3-in-net-10-enabling-quic-with-httpclient-and-aspnet-core"
---

HTTP 协议在过去几年里迭代速度很快。HTTP/2 带来了多路复用，HTTP/3 则直接换掉了底层的传输协议——从 TCP 切换到基于 UDP 的 QUIC。到 .NET 10，HTTP/3 已经是生产就绪的一等公民，不需要任何 feature flag 就能在客户端和服务端同时启用。

这篇文章覆盖从 QUIC 的基本原理到 HttpClient 和 Kestrel 的完整配置，最后给出一个能直接跑通的端到端示例。

## QUIC 解决了什么

HTTP/3 与 HTTP/2 最大的区别不在应用层，而在传输层：HTTP/2 跑在 TCP 上，HTTP/3 跑在 QUIC（基于 UDP）上。这一个架构层面的改动，解决了三个 TCP 层面无解的问题。

### 队头阻塞

HTTP/2 的多路复用让多个请求共享一条 TCP 连接。问题是 TCP 自身——如果有一个包丢了，整条连接都会停等重传。所有流，包括完全不相关的请求，全被堵住。这是 TCP 层面的队头阻塞，是协议的根本局限。

QUIC 在传输层解决这个问题：每个 QUIC 流都是独立的。A 流丢包不会影响 B 流。多路复用的好处保住了，队头阻塞的代价去掉了。

### 0-RTT 连接建立

标准 TLS 1.3 over TCP 在建连阶段至少需要一个 round-trip 才能开始传数据。QUIC 把传输握手和加密握手合并到一起，首次连接只需 1-RTT。如果客户端之前连过同一个服务器，还能用 0-RTT 恢复——在第一个包里就开始发数据。

对移动端、跨地域服务这类延迟敏感的场景，减少一个 round-trip 是实打实的收益。

### 连接迁移

TCP 连接由四元组标识：源 IP、源端口、目标 IP、目标端口。任何一个变了，连接就断了。手机在 Wi-Fi 和蜂窝网络之间切换时这个情况非常常见。

QUIC 用 Connection ID 来标识连接，不绑定网络地址。IP 在中途变了，QUIC 可以无缝迁移，不断开、不重建连接。HTTP/3 直接继承了这个能力。

## .NET 中 HTTP/3 的支持时间线

往回倒一下各版本的进展：

- **.NET 6**：HTTP/3 作为 preview 功能，需要 `AppContext` 开关才能用，明确不是生产就绪。
- **.NET 7**：客户端（HttpClient）和服务端（Kestrel）都达到生产级别。
- **.NET 8 / .NET 9**：渐进优化——TLS 集成更好、QUIC 流处理更稳、性能调优。
- **.NET 10**：HTTP/3 是一等公民。不需要 feature flag。`HttpVersionPolicy` 行为稳定且定义清晰。QUIC 性能有显著提升。

平台层面要注意：HTTP/3 底层依赖 MsQuic。从 .NET 8 起，Windows x64 和 Linux x64 的运行时已经内置了 MsQuic，大多数部署场景不需要额外安装。在 Windows 11 / Windows Server 2022 及以上版本里 MsQuic 是系统组件。Linux 上如果没有内置版本，需要单独装 `libmsquic` 包。

## 客户端：用 HttpVersionPolicy 启用 HTTP/3

HttpClient 上控制 HTTP/3 的核心属性是两个：`DefaultRequestVersion` 和 `DefaultVersionPolicy`。

```csharp
using System.Net;
using System.Net.Http;

var client = new HttpClient
{
    DefaultRequestVersion = HttpVersion.Version30,
    DefaultVersionPolicy = HttpVersionPolicy.RequestVersionOrLower
};

var response = await client.GetAsync("https://example.com/api/data");
Console.WriteLine($"Response version: {response.Version}");
```

如果用的是 `IHttpClientFactory`（ASP.NET Core 的推荐方式），在注册时配置：

```csharp
using Microsoft.Extensions.DependencyInjection;
using System.Net;
using System.Net.Http;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHttpClient("http3-client", client =>
{
    client.DefaultRequestVersion = HttpVersion.Version30;
    client.DefaultVersionPolicy = HttpVersionPolicy.RequestVersionOrLower;
});

var app = builder.Build();
app.Run();
```

### 三种 VersionPolicy 的区别

`HttpVersionPolicy` 有三个值，理解它们的差异对生产环境的正确性很重要。

**RequestVersionOrLower**：最安全的选项。请求指定版本，服务器不支持时自动降级到下一个更低版本（HTTP/2 -> HTTP/1.1）。适合"能用 HTTP/3 最好，不行也没关系"的场景。

```csharp
var request = new HttpRequestMessage(HttpMethod.Get, "https://api.example.com/data")
{
    Version = HttpVersion.Version30,
    VersionPolicy = HttpVersionPolicy.RequestVersionOrLower
};
```

**RequestVersionOrHigher**：请求至少某个版本。服务器支持更高版本时可以协商升级。适合有最低版本要求、同时想享受更高版本好处的场景。注意这个选项没有降级逻辑——如果服务器连最低版本都不支持，会抛 `HttpRequestException`。

```csharp
var request = new HttpRequestMessage(HttpMethod.Get, "https://api.example.com/data")
{
    Version = HttpVersion.Version20,
    VersionPolicy = HttpVersionPolicy.RequestVersionOrHigher
};
```

**RequestVersionExact**：最严格。必须精确匹配指定版本。不匹配就抛 `HttpRequestException`。适合测试场景（验证某个端点是否真的在提供 HTTP/3），不适合面向公用 API 的生产客户端。

```csharp
var request = new HttpRequestMessage(HttpMethod.Get, "https://api.example.com/data")
{
    Version = HttpVersion.Version30,
    VersionPolicy = HttpVersionPolicy.RequestVersionExact
};

try
{
    var response = await client.SendAsync(request);
}
catch (HttpRequestException ex)
{
    Console.WriteLine($"HTTP/3 not available: {ex.Message}");
}
```

### TLS 要求

HTTP/3 必须走 HTTPS，更准确地说需要 TLS 1.3 及以上。不存在明文 HTTP/3。这是设计使然——QUIC 在设计之初就把安全作为核心要求而非附加层。这意味着：

- 服务器必须有有效的 TLS 证书（本地开发可以用自签名证书）。
- 客户端必须通过 `https://` 连接，用 `http://` 尝试 HTTP/3 会失败——运行时根据 VersionPolicy 要么降级到 HTTP/1.1 要么抛异常。
- 证书必须支持 TLS 1.3。Let's Encrypt 和主流 CA 签发的现代证书都支持。

## 服务端：Kestrel 启用 HTTP/3

Kestrel 通过 `Protocols` 配置按端点启用 HTTP/3。

```csharp
using Microsoft.AspNetCore.Server.Kestrel.Core;

var builder = WebApplication.CreateBuilder(args);

builder.WebHost.ConfigureKestrel(options =>
{
    options.ListenAnyIP(443, listenOptions =>
    {
        listenOptions.UseHttps();
        listenOptions.Protocols = HttpProtocols.Http1AndHttp2AndHttp3;
    });
});

var app = builder.Build();

app.MapGet("/", () => "Hello from HTTP/3!");

app.Run();
```

`appsettings.json` 方式更适合按环境切换配置：

```json
{
  "Kestrel": {
    "Endpoints": {
      "Https": {
        "Url": "https://*:443",
        "Protocols": "Http1AndHttp2AndHttp3"
      }
    }
  }
}
```

两种方式等价。容器化部署时还可以用环境变量 `Kestrel__Endpoints__Https__Protocols` 覆盖。

## Alt-Svc：版本协商是怎样发生的

HTTP/3 用的是升级发现机制，不是直接协商。客户端第一次请求服务器时走的是 HTTP/1.1 或 HTTP/2（通过 TCP）。服务器在响应头里加一个 `Alt-Svc`，相当于通知客户端："我也在端口 443 上支持 HTTP/3"：

```
Alt-Svc: h3=":443"; ma=86400
```

这告诉客户端：QUIC（HTTP/3）在端口 443 可用，这个声明的有效期是 86400 秒。客户端缓存这个信息，后续到同一个源的请求就走 HTTP/3 了。

Kestrel 从 .NET 7 起在配置了包含 HTTP/3 的协议组合后会自动添加这个响应头，不需要手动处理。

这也是为什么你有时会看到第一次请求走 HTTP/2、后续请求走 HTTP/3——这不是 bug，是协议按设计工作的表现。

## 连接迁移的实际意义

连接迁移是 QUIC 对现实场景最有用的特性之一。当一个移动设备从 Wi-Fi 切到蜂窝网络，IP 地址变了。在 TCP 下这直接断连——操作系统得新建 TCP 连接、重新做 TLS 握手、重新发所有在途请求。用户感受到的是延迟、请求失败或报错。

QUIC 下，客户端在新网络路径上给服务器发 `PATH_CHALLENGE`。服务器验证新路径后更新路由。原有 Connection ID 被保留。在途的流不受影响地继续。

在 .NET 10 里这由 MsQuic 层透明处理，应用代码不需要任何配置。

实际限制是：很多企业防火墙和负载均衡器是按源 IP 做会话亲和的。如果你的负载均衡器用源 IP 绑定连接，连接迁移会导致路由错乱。这是部署层面的问题而非 .NET 层面的问题。

## 本地测试 HTTP/3

先信任 .NET 开发证书：

```bash
dotnet dev-certs https --trust
```

服务端最小示例：

```csharp
using Microsoft.AspNetCore.Server.Kestrel.Core;

var builder = WebApplication.CreateBuilder(args);

builder.WebHost.ConfigureKestrel(options =>
{
    options.ListenLocalhost(5001, listenOptions =>
    {
        listenOptions.UseHttps();
        listenOptions.Protocols = HttpProtocols.Http1AndHttp2AndHttp3;
    });
});

var app = builder.Build();

app.MapGet("/version-check", (HttpContext ctx) =>
    $"Protocol: {ctx.Request.Protocol}");

app.Run();
```

客户端测试代码（仅开发环境使用，生产环境不要跳过证书验证）：

```csharp
using System.Net;
using System.Net.Http;

var handler = new SocketsHttpHandler
{
    SslOptions = new System.Net.Security.SslClientAuthenticationOptions
    {
        RemoteCertificateValidationCallback = (_, _, _, _) => true
    }
};

var client = new HttpClient(handler)
{
    DefaultRequestVersion = HttpVersion.Version30,
    DefaultVersionPolicy = HttpVersionPolicy.RequestVersionOrLower
};

var response = await client.GetStringAsync(
    "https://localhost:5001/version-check");
Console.WriteLine(response); // 应该输出 "Protocol: HTTP/3"
```

同时启动服务端和客户端。第一次请求可能协商到 HTTP/1.1 或 HTTP/2（Alt-Svc 发现周期），后续请求应该走 HTTP/3。检查服务端 `ctx.Request.Protocol` 或客户端 `response.Version` 进行确认。

Linux 用户注意：确保安装了 `libmsquic`。Ubuntu/Debian 上运行 `sudo apt-get install -y libmsquic`。没有它的话 HTTP/3 会静默降级到 HTTP/2。

## 容器与反向代理中的 HTTP/3

### UDP 防火墙问题

QUIC 跑在 UDP 上，而很多云环境和公司网络默认屏蔽或限制 UDP。如果容器或虚拟机的 UDP 443 端口在网络上被禁，Kestrel 怎么配置都没用。

Docker Compose 里要同时映射 TCP 和 UDP：

```yaml
services:
  api:
    image: myapp:latest
    ports:
      - "443:443/tcp"
      - "443:443/udp" # HTTP/3 / QUIC 必需
```

Azure 上要确保网络安全组的规则同时允许 UDP 443 和 TCP 443。

### nginx

nginx 1.25+ 支持 HTTP/3，但需要编译时带 QUIC 实现（quiche 或 BoringSSL）。标准包管理器的 nginx 构建通常不包括。如果你用 nginx 做反向代理，先确认具体构建的能力。

### Azure Front Door 和 Cloudflare

这两类服务在边缘终止 HTTP/3，然后通过 HTTP/1.1 或 HTTP/2 代理请求到你的源站。这意味着：

- 客户端连到 CDN 边缘时享受到 HTTP/3 的好处（更快握手、连接迁移）。
- 边缘到源站的请求走 HTTP/2 或 HTTP/1.1，对内部通信完全够用。
- 使用这些服务时，不需要在源站启用 HTTP/3——边缘替你处理了。

## 什么时候用 HTTP/3

| 场景                       | 推荐版本                                  |
| -------------------------- | ----------------------------------------- |
| 现代浏览器客户端、公用 API | HTTP/3 优先（`RequestVersionOrLower`）    |
| gRPC 服务                  | HTTP/2（gRPC 基于 HTTP/2 帧）             |
| 数据中心内部服务间调用     | HTTP/2（低延迟、稳定网络下 TCP 完全够用） |
| 兼容旧版服务器             | HTTP/1.1                                  |
| 移动端为主的场景           | HTTP/3（连接迁移收益明显）                |
| 高丢包网络环境             | HTTP/3（QUIC 按流处理丢包）               |
| 反向代理不支持 HTTP/3      | HTTP/2 或 HTTP/1.1                        |

实用的建议：对大多数新的 .NET 10 API，服务端用 `HttpProtocols.Http1AndHttp2AndHttp3` 同时启用三个版本，让 Alt-Svc 协商自己决定。能走 HTTP/3 的客户端自然会走，不能走的平滑降级。客户端用 `RequestVersionOrLower` + `Version30` 作为安全默认值。

## 完整端到端示例

服务端（Program.cs）：

```csharp
using Microsoft.AspNetCore.Server.Kestrel.Core;

var builder = WebApplication.CreateBuilder(args);

builder.WebHost.ConfigureKestrel(options =>
{
    options.ListenLocalhost(7443, listenOptions =>
    {
        listenOptions.UseHttps();
        listenOptions.Protocols = HttpProtocols.Http1AndHttp2AndHttp3;
    });
});

var app = builder.Build();

app.MapGet("/ping", (HttpContext ctx) => new
{
    Protocol = ctx.Request.Protocol,
    Timestamp = DateTimeOffset.UtcNow
});

app.Run();
```

客户端：

```csharp
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json.Serialization;

var handler = new SocketsHttpHandler
{
    SslOptions = new System.Net.Security.SslClientAuthenticationOptions
    {
        RemoteCertificateValidationCallback = (_, _, _, _) => true
    }
};

var client = new HttpClient(handler)
{
    BaseAddress = new Uri("https://localhost:7443"),
    DefaultRequestVersion = HttpVersion.Version30,
    DefaultVersionPolicy = HttpVersionPolicy.RequestVersionOrLower
};

// 第一次请求可能走 HTTP/1.1 或 HTTP/2（Alt-Svc 发现中）
var first = await client.GetFromJsonAsync<PingResponse>("/ping");
Console.WriteLine($"First request -- Protocol: {first?.Protocol}");

// 稍等让 Alt-Svc 缓存生效
await Task.Delay(100);

// 后续请求应该协商到 HTTP/3
for (var i = 0; i < 3; i++)
{
    var result = await client.GetFromJsonAsync<PingResponse>("/ping");
    Console.WriteLine($"Request {i + 2} -- Protocol: {result?.Protocol}");
}

record PingResponse(
    [property: JsonPropertyName("protocol")] string Protocol,
    [property: JsonPropertyName("timestamp")] DateTimeOffset Timestamp
);
```

两端一起跑起来后你会看到协议版本从 HTTP/1.1 或 HTTP/2 过渡到 HTTP/3——这正是 Alt-Svc 协商按设计工作的表现。

## 常见问题

**HTTP/3 在 .NET 10 里需要额外安装 NuGet 包吗？**

不需要。HTTP/3 支持内置于 .NET 10 自带的 `System.Net.Http` 和 `Microsoft.AspNetCore.Server.Kestrel` 包里。Linux 可能需要安装系统级的 `libmsquic`，但那不是 .NET 包。

**为什么设了 Version30 之后 HttpClient 还显示 HTTP/2？**

最常见的原因是 Alt-Svc 发现。第一次请求服务器时用的是基于 TCP 的 HTTP，因为客户端还不知道服务器支持 QUIC。收到 `Alt-Svc` 响应头后，后续到同一个源的请求才会走 HTTP/3。试着发第二个请求再看 `response.Version`。

**能和 gRPC 一起用吗？**

gRPC 基于 HTTP/2 帧（`h2c` 或 `h2`）。截至 .NET 10，标准的 `Grpc.AspNetCore` 和 `Grpc.Net.Client` 包用的是 HTTP/2。如果需要 gRPC，在 Kestrel 端点上用 `HttpProtocols.Http1AndHttp2`。可以给 HTTP/3 REST 和 HTTP/2 gRPC 分别配不同端口。

**QUIC 握手在系统层面失败了会怎样？**

只要 VersionPolicy 是 `RequestVersionOrLower`，HttpClient 会优雅降级。运行时内部记录一条警告但不会抛异常。如果用 `RequestVersionExact` 且 QUIC 失败，会收到 `HttpRequestException`。排查之前先检查 VersionPolicy 的配置——答案往往是"它按配置正确工作了，只是选择降级了"。

**HTTP/3 对所有请求类型都能提升性能吗？**

不是一刀切。HTTP/3 在高延迟、高丢包的网络条件下收益最大（移动端、跨洲调用）。对数据中心内部低延迟、低丢包的通信，HTTP/2 和 HTTP/3 之间的差异很小——有时候 HTTP/2 反而因为更低的单连接开销更快。先用自己的实际负载做基准测试再下结论。

**怎么验证生产环境实际用的是哪个 HTTP 版本？**

服务端在中间件里记录 `HttpContext.Request.Protocol`。客户端每次调用后检查 `HttpResponseMessage.Version`。基础设施层面，APM 工具（Azure Monitor、Datadog、OpenTelemetry）会把 HTTP 版本作为一个维度呈现在请求指标上——查 OpenTelemetry 语义约定里的 `http.version`。

## 收尾

HTTP/3 在 .NET 10 里不是实验性功能——它是完整集成、生产就绪的特性，可以渐进式启用。`HttpVersionPolicy` 枚举给了版本协商的精细控制，Kestrel 的 `HttpProtocols` 一行配置就能在单个端口上同时启用三个版本。Alt-Svc 升级机制保证了与尚不支持 QUIC 的客户端的向后兼容。

大多数应用的前进路径很清楚：在 Kestrel 协议列表里加上 `Http3`，客户端设好 `DefaultVersionPolicy` 为 `RequestVersionOrLower`，剩下的交给协议自己去处理。网络和基础设施支持 HTTP/3 的地方享受性能红利，不支持的场景自动平滑降级。

如果你关注 .NET 开发、性能优化和工程实践，可以关注 Aide Hub。这里会继续分享能落地的技术教程和开发经验。

## 参考

- [HTTP/3 in .NET 10: Enabling QUIC with HttpClient and ASP.NET Core — Dev Leader](https://www.devleader.ca/2026/07/01/http3-in-net-10-enabling-quic-with-httpclient-and-aspnet-core)
- [HttpClient in C#: The Complete Guide](https://www.devleader.ca/2026/06/26/httpclient-in-c-the-complete-guide-for-net-developers)
- [ASP.NET Core Web API in .NET: The Complete Guide](https://www.devleader.ca/2026/05/30/aspnet-core-web-api-in-net-the-complete-guide)
- [ASP.NET Core Middleware: Building and Using the Request Pipeline](https://www.devleader.ca/2026/06/07/aspnet-core-middleware-building-and-using-the-request-pipeline)
- [ASP.NET Core Routing: Attribute Routing, Route Templates, and Constraints](https://www.devleader.ca/2026/05/31/aspnet-core-routing-attribute-routing-route-templates-and-constraints)
- [Deploying ASP.NET Core Web API to Azure and Docker](https://www.devleader.ca/2026/06/09/deploying-aspnet-core-web-api-to-azure-and-docker)
