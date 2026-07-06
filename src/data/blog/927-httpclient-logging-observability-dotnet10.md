---
pubDatetime: 2026-07-06T20:18:25+08:00
title: "HttpClient 日志与可观测性：ILogger、DelegatingHandler 和 OpenTelemetry"
description: "详解 .NET 10 中 HttpClient 的日志记录与可观测性方案：内置 ILogger 集成、DelegatingHandler 自定义日志、敏感头安全过滤、OpenTelemetry 分布式追踪与指标，附完整生产级代码示例。"
tags:
  [
    ".NET 10",
    "HttpClient",
    "ILogger",
    "DelegatingHandler",
    "OpenTelemetry",
    "Distributed Tracing",
    "Metrics",
    "Observability",
  ]
slug: "httpclient-logging-observability-dotnet10"
source: "https://www.devleader.ca/2026/07/03/httpclient-logging-and-observability-in-net-10-ilogger-delegatinghandler-and-opentelemetry"
ogImage: "../../assets/927/01-cover.png"
---

当微服务之间的 HTTP 调用开始出问题的时候，没有日志的开发体验是：用户报了故障，你打开日志平台，发现服务 A 调用服务 B 时没有任何记录——没有请求 URL、没有响应时间、没有 Trace ID。你只能猜测下游发生了什么。

.NET 10 默认带了足够好的 HttpClient 可观测能力：`IHttpClientFactory` 的内置日志、`DelegatingHandler` 的自定义请求日志、OpenTelemetry 的分布式追踪和 W3C TraceContext 自动传播，以及 `System.Net.Http` Meter 内置的指标。这些是独立的分层——你可以先从最简单的一层开始，再按需叠加。

## 内置日志：IHttpClientFactory 默认输出了什么

当你用 `IHttpClientFactory` 注册 HttpClient 时，框架会自动挂载两个日志分类：

- **`System.Net.Http.HttpClient.[ClientName].LogicalHandler`**：记录请求的逻辑生命周期开始和结束，包括 Polly 重试。
- **`System.Net.Http.HttpClient.[ClientName].ClientHandler`**：记录实际的网络层请求和响应。

默认情况下两个分类都在 `Information` 级别输出请求起止，失败时提升到 `Warning` 或 `Error`。典型日志长这样：

```
info: System.Net.Http.HttpClient.WeatherClient.LogicalHandler[100]
      Start processing HTTP request GET https://api.example.com/weather

info: System.Net.Http.HttpClient.WeatherClient.ClientHandler[100]
      Sending HTTP request GET https://api.example.com/weather

info: System.Net.Http.HttpClient.WeatherClient.ClientHandler[101]
      Received HTTP response headers after 184.3ms - 200

info: System.Net.Http.HttpClient.WeatherClient.LogicalHandler[101]
      End processing HTTP request after 185.1ms - 200
```

`LogicalHandler` 记录的耗时包含了自定义 `DelegatingHandler` 管线的开销，适合衡量从业务代码视角出发的真实调用成本。

## 按环境控制日志级别

默认 `Information` 在高吞吐量服务里会刷屏。通过 `appsettings.json` 按分类精确控制：

```json
{
  "Logging": {
    "LogLevel": {
      "System.Net.Http.HttpClient": "Warning",
      "System.Net.Http.HttpClient.WeatherClient": "Information"
    }
  }
}
```

全局把 HttpClient 日志压到 `Warning`，只对自己关心的命名客户端（`WeatherClient`）保留 `Information`。如果需要调试请求头，可以单独对 `ClientHandler` 打开 `Trace`：

```json
{
  "Logging": {
    "LogLevel": {
      "System.Net.Http.HttpClient.WeatherClient.ClientHandler": "Trace"
    }
  }
}
```

注意 `Trace` 会输出请求和响应头，不要在生产环境长期开启——里面通常包含 `Authorization` Token。

## DelegatingHandler：正确的自定义日志姿势

`DelegatingHandler` 是实现应用级 HttpClient 日志的推荐方式。它是类型安全的，挂载在 `IHttpClientFactory` 管线中，可以和重试策略自然组合。

一个完整的日志 Handler，捕获方法、URL、状态码和耗时：

```csharp
using System.Diagnostics;
using Microsoft.Extensions.Logging;

public sealed class RequestLoggingHandler : DelegatingHandler
{
    private readonly ILogger<RequestLoggingHandler> _logger;

    public RequestLoggingHandler(ILogger<RequestLoggingHandler> logger)
    {
        _logger = logger;
    }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        _logger.LogInformation(
            "HTTP {Method} {Uri}",
            request.Method,
            request.RequestUri);

        var stopwatch = Stopwatch.StartNew();
        try
        {
            var response = await base.SendAsync(request, cancellationToken);
            _logger.LogInformation(
                "HTTP {Method} {Uri} responded {StatusCode} in {ElapsedMs}ms",
                request.Method,
                request.RequestUri,
                (int)response.StatusCode,
                stopwatch.ElapsedMilliseconds);
            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(
                ex, "HTTP {Method} {Uri} failed",
                request.Method, request.RequestUri);
            throw;
        }
    }
}
```

注册到管线：

```csharp
builder.Services.AddTransient<RequestLoggingHandler>();
builder.Services
    .AddHttpClient("MyClient")
    .AddHttpMessageHandler<RequestLoggingHandler>();
```

### 一个陷阱：不要直接用 DiagnosticListener

`DiagnosticListener` 是 .NET 运行时内部的诊断机制——内置 ILogger 和 OpenTelemetry 都在它之上构建，但它不是应用层日志 API。它触发 `System.Net.Http.HttpRequestOut.Start` 和 `System.Net.Http.HttpRequestOut.Stop` 事件时，载荷被包装在 `private internal struct` 中（`ActivityStartData`、`ActivityStopData`）。写成 `value.Value is HttpRequestMessage request` 这种类型检查在运行时永远返回 false——代码编译通过，但静默地什么都不做。日志用 `DelegatingHandler`，追踪用 OpenTelemetry。

## 敏感头过滤：Authorization 不要进日志

把 `Authorization` 头写进日志是 HttpClient 日志中最常见的安全事故。在 Seq 或 Application Insights 这类可查询的日志系统中，一旦日志查看权限被突破，攻击者就拿到了所有曾经用过的 Bearer Token。

安全模式是用**白名单**而不是黑名单来决定记录哪些头：

```csharp
public sealed class SafeHeaderLoggingHandler(
    ILogger<SafeHeaderLoggingHandler> logger)
    : DelegatingHandler
{
    private static readonly HashSet<string> AllowedRequestHeaders =
        new(StringComparer.OrdinalIgnoreCase)
        {
            "Content-Type", "Accept", "User-Agent",
            "X-Correlation-ID", "traceparent"
        };

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        if (logger.IsEnabled(LogLevel.Debug))
        {
            var safe = request.Headers
                .Where(h => AllowedRequestHeaders.Contains(h.Key))
                .Select(h => $"{h.Key}={string.Join(",", h.Value)}");
            logger.LogDebug(
                "Request to {Url}, allowed headers: {Headers}",
                request.RequestUri, string.Join("; ", safe));
        }
        return await base.SendAsync(request, cancellationToken);
    }
}
```

白名单策略意味着新引入的敏感头（比如 `X-User-Token`）自动被排除在日志之外——不需要记住更新黑名单。

还需要处理 URL 中的敏感查询参数。一个简单的 `SanitizeUri` 方法是直接去掉整个 query string：

```csharp
private static string? SanitizeUri(Uri? uri) =>
    uri is null ? null : $"{uri.Scheme}://{uri.Host}{uri.AbsolutePath}";
```

因为查询参数里经常夹带 API Key、Token 或 PII。宁可少记录，不要漏出去。

## OpenTelemetry 分布式追踪

当单条日志不够用，需要跨服务的调用链全貌时，OpenTelemetry 是标准答案。`OpenTelemetry.Instrumentation.Http` 包为每次出站 HttpClient 请求自动创建 Span：

```xml
<PackageReference Include="OpenTelemetry.Extensions.Hosting" Version="1.*" />
<PackageReference Include="OpenTelemetry.Instrumentation.Http" Version="1.*" />
<PackageReference Include="OpenTelemetry.Instrumentation.AspNetCore" Version="1.*" />
```

```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing => tracing
        .ConfigureResource(resource => resource
            .AddService("WeatherService", serviceVersion: "1.0.0"))
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation(options =>
        {
            options.FilterHttpRequestMessage = request =>
                request.RequestUri?.Host != "localhost" &&
                !(request.RequestUri?.AbsolutePath.StartsWith("/health") ?? false);
        }));
```

`AddHttpClientInstrumentation` 挂载到与内置 ILogger 相同的 `DiagnosticListener` 基础设施上，但把这些事件包装成标准的 OpenTelemetry `Activity`，每个出站 HTTP 调用自动成为当前 Trace 的子 Span。

## W3C TraceContext 自动传播

分布式追踪只有在 Trace 上下文跨服务边界传播时才真正有意义。在 .NET 10 中，当你调用 `AddHttpClientInstrumentation` 后，每个出站 HttpClient 请求都会自动注入 `traceparent` 头。如果下游服务也使用 OpenTelemetry，它会读取这个头，把自己的 Span 创建为同一个 Trace 的子节点——一条 Trace ID 贯穿从浏览器到你的 API 再到所有下游服务的完整链路。

验证方式：在 `DelegatingHandler` 中检查 `traceparent` 头：

```csharp
if (request.Headers.TryGetValues("traceparent", out var values))
{
    _logger.LogDebug("traceparent: {TraceParent}", values.FirstOrDefault());
}
```

## HttpClient 指标：System.Net.Http Meter

.NET 8 引入并在 9/10 中延续的 `System.Net.Http` Meter 自动暴露五类指标，不需要写任何埋点代码：

| 指标                                | 类型          | 含义                    |
| ----------------------------------- | ------------- | ----------------------- |
| `http.client.request.duration`      | Histogram     | 请求耗时分布（秒）      |
| `http.client.active_requests`       | UpDownCounter | 当前活跃出站请求数      |
| `http.client.request.time_in_queue` | Histogram     | 连接池中排队等待时间    |
| `http.client.open_connections`      | UpDownCounter | 连接池中活跃 TCP 连接数 |
| `http.client.connection.duration`   | Histogram     | HTTP 连接生命周期       |

通过 OpenTelemetry 暴露这些指标：

```csharp
builder.Services.AddOpenTelemetry()
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddRuntimeInstrumentation()
        .AddPrometheusExporter());
```

`http.client.request.duration` Histogram 特别适合 SLO 仪表盘——按下游服务追踪 P99 延迟，超过阈值告警，再关联 Jaeger 里的 Trace 定位根因。

## 完整代码：ILogger + OTel + Metrics 全栈

下面是一个完整的 `Program.cs`，把内置日志过滤、自定义 `DelegatingHandler`、OpenTelemetry 追踪与 W3C 传播、OTLP 指标导出组合在一起：

```csharp
using OpenTelemetry.Resources;

var builder = WebApplication.CreateBuilder(args);

// ── Logging ──
builder.Logging.AddJsonConsole();
builder.Logging.AddFilter("System.Net.Http.HttpClient", LogLevel.Warning);

// ── DelegatingHandlers ──
builder.Services.AddTransient<SafeHeaderLoggingHandler>();
builder.Services.AddTransient<RequestDetailsDelegatingHandler>();

builder.Services.AddHttpClient<WeatherServiceClient>(client =>
{
    client.BaseAddress = new Uri(
        builder.Configuration["WeatherApi:BaseUrl"]
        ?? throw new InvalidOperationException("BaseUrl missing"));
    client.Timeout = TimeSpan.FromSeconds(30);
})
.AddHttpMessageHandler<SafeHeaderLoggingHandler>()
.AddHttpMessageHandler<RequestDetailsDelegatingHandler>();

// ── OpenTelemetry ──
var otlpEndpoint = builder.Configuration["Otlp:Endpoint"]
    ?? "http://localhost:4317";

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService("WeatherService"))
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation(o => o.RecordException = true)
        .AddHttpClientInstrumentation(o =>
            o.FilterHttpRequestMessage = req =>
                !(req.RequestUri?.AbsolutePath.StartsWith("/health") ?? false))
        .AddOtlpExporter(o => o.Endpoint = new Uri(otlpEndpoint)))
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddRuntimeInstrumentation()
        .AddOtlpExporter(o => o.Endpoint = new Uri(otlpEndpoint)));

builder.Services.AddControllers();
var app = builder.Build();
app.MapControllers();
app.Run();
```

这套配置给你结构化 JSON 日志、Jaeger/Grafana Tempo 中可见的分布式链路、以及请求耗时和连接池健康的指标。

如果你关注 .NET 开发、工具实践和可运维的软件工程，可以关注 Aide Hub。这里会继续分享能落地的教程、工具分析和工程观察。

## 参考

- [原文: HttpClient Logging and Observability in .NET 10](https://www.devleader.ca/2026/07/03/httpclient-logging-and-observability-in-net-10-ilogger-delegatinghandler-and-opentelemetry)
- [HttpClient in C#: The Complete Guide](https://www.devleader.ca/2026/06/26/httpclient-in-c-the-complete-guide-for-net-developers)
- [ASP.NET Core Web API in .NET: The Complete Guide](https://www.devleader.ca/2026/05/30/aspnet-core-web-api-in-net-the-complete-guide)
- [Authentication and Authorization in ASP.NET Core Web API](https://www.devleader.ca/2026/06/03/authentication-and-authorization-in-aspnet-core-web-api-jwt-and-policies)
- [OpenTelemetry .NET 官方文档](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/observability-with-otel)
