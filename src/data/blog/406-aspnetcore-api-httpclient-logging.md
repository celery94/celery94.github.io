---
pubDatetime: 2025-07-16
tags: [".NET", "ASP.NET Core", "Security", "DevOps"]
slug: aspnetcore-api-httpclient-logging
source: https://antondevtips.com/blog/logging-requests-and-responses-for-api-requests-and-httpclient-in-aspnetcore
title: 深入 ASP.NET Core：高效实现 API 请求与 HttpClient 的请求响应日志记录
description: 本文全面介绍如何在 ASP.NET Core 项目中高效记录 HTTP 请求与响应日志，包括 HttpLogging 中间件配置、日志自定义、敏感数据脱敏与 HttpClient 日志方案，兼顾实用性与安全性，适合追求高可维护性和可观测性的 .NET 团队。
---

# 深入 ASP.NET Core：高效实现 API 请求与 HttpClient 的请求响应日志记录

## 前言

日志是保障现代应用稳定、高可维护与安全合规的核心。特别是在微服务和 API 日益普及的背景下，如何规范记录每一次 HTTP 请求与响应，成为开发者和架构师关注的重点。ASP.NET Core 自带强大的 HttpLogging 支持，既能便捷开启、细粒度控制，也能自定义扩展和安全脱敏。与此同时，外部 API 通信（如通过 HttpClient）也需要有体系化的日志方案，便于诊断问题与审计接口调用。

本文将结合原文实践和更广泛的业界经验，深入讲解：

- 如何开启与配置 ASP.NET Core 的 HTTP 请求/响应日志
- 日志内容与级别管理
- 如何自定义日志、实现敏感数据脱敏
- 针对 HttpClient 的外部请求日志采集
- 实用安全建议与常见误区分析

## 一、快速上手 HttpLogging：两步搞定 API 日志

ASP.NET Core 通过 `HttpLogging` 中间件即可记录所有进入 Web API 的请求与响应。只需两步即可启用：

**第一步：在 Program.cs 注册中间件**

```csharp
var builder = WebApplication.CreateBuilder(args);

// 注册 HttpLogging 服务
builder.Services.AddHttpLogging(options =>
{
    options.LoggingFields = HttpLoggingFields.Request | HttpLoggingFields.Response;
});

var app = builder.Build();

// 加入请求管道
app.UseHttpLogging();

app.Run();
```

**第二步：配置日志输出级别**

在 `appsettings.json` 设定合适的日志级别，通常“Information”已足够：

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning",
      "Microsoft.AspNetCore.HttpLogging.HttpLoggingMiddleware": "Information"
    }
  }
}
```

配置完成后，所有 HTTP 请求和响应内容会自动写入日志，如下示例：

```
info: Microsoft.AspNetCore.HttpLogging.HttpLoggingMiddleware[1]
      Request:
      Protocol: HTTP/1.1
      Method: GET
      Path: /
      Headers: ...
      Response:
      StatusCode: 200
      Headers: Content-Type: text/plain; charset=utf-8
```

这种方案默认集成 `Microsoft.Extensions.Logging`，当然也可配合如 Serilog 等第三方日志库，将日志灵活输出到文件、数据库、监控系统等。

## 二、细粒度日志配置与性能优化

HttpLogging 支持丰富的字段选项，开发者可通过 `HttpLoggingOptions` 按需调整：

```csharp
builder.Services.AddHttpLogging(options =>
{
    options.LoggingFields =
        HttpLoggingFields.RequestMethod |
        HttpLoggingFields.RequestPath |
        HttpLoggingFields.RequestQuery |
        HttpLoggingFields.RequestHeaders |
        HttpLoggingFields.ResponseStatusCode |
        HttpLoggingFields.Duration;
    // 只记录指定头部
    options.RequestHeaders.Add("User-Agent");
    options.ResponseHeaders.Add("Content-Type");
    // 限制日志体大小（防止日志膨胀）
    options.RequestBodyLogLimit = 4096;
    options.ResponseBodyLogLimit = 4096;
});
```

**注意事项**：

- **性能影响**：记录请求/响应体内容会影响吞吐，建议只在开发/调试环境开启，线上环境慎用。
- **安全与合规**：日志中可能包含敏感数据，必须严格控制记录范围和字段，并配合脱敏处理。

## 三、自定义日志与敏感数据脱敏

实际开发中，不同接口可能需要不同的日志策略，比如支付接口完全禁止记录 body，用户登录接口屏蔽 Authorization 等敏感字段。这时可以实现 `IHttpLoggingInterceptor`，实现灵活的日志处理。

**自定义日志拦截器示例**：

```csharp
public class CustomLoggingInterceptor : IHttpLoggingInterceptor
{
    public ValueTask OnRequestAsync(HttpLoggingInterceptorContext context)
    {
        // 动态移除敏感请求头
        context.HttpContext.Request.Headers.Remove("X-API-Key");
        // 增加追踪字段
        context.AddParameter("RequestId", Guid.NewGuid().ToString());
        return ValueTask.CompletedTask;
    }

    public ValueTask OnResponseAsync(HttpLoggingInterceptorContext context)
    {
        // 移除响应中的 Set-Cookie 等敏感头
        context.HttpContext.Response.Headers.Remove("Set-Cookie");
        return ValueTask.CompletedTask;
    }
}
```

注册方式如下：

```csharp
builder.Services.AddSingleton<IHttpLoggingInterceptor, CustomLoggingInterceptor>();
```

### 脱敏最佳实践

- **严格选择要记录的头/体字段**
- **开发环境与生产环境采用不同日志策略**
- **实现自动脱敏，如对手机号、邮箱、Token 进行正则替换或置为 \[REDACTED]**

## 四、按接口/端点细分日志规则

ASP.NET Core 支持对特定接口设置独立日志策略。例如健康检查、静态资源等无需日志，而业务接口可自定义更细粒度的日志内容。

```csharp
app.MapGet("/health", () => Results.Ok())
   .DisableHttpLogging();

app.MapPost("/api/orders", (OrderRequest request) => Results.Created())
   .WithHttpLogging(logging =>
   {
       logging.LoggingFields = HttpLoggingFields.RequestBody | HttpLoggingFields.ResponseStatusCode;
   });
```

## 五、HttpClient 外部请求日志采集方案

现代系统中，服务间或第三方 API 通信普遍依赖 HttpClient。要高质量采集所有外部 HTTP 请求日志，可借助自定义 DelegatingHandler 拦截和记录流量。

**自定义 HttpLoggingHandler 示例**：

```csharp
public class HttpLoggingHandler : DelegatingHandler
{
    private readonly ILogger _logger;

    public HttpLoggingHandler(ILogger logger) => _logger = logger;

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        var traceId = Guid.NewGuid().ToString();
        _logger.LogDebug("[REQUEST] {traceId} {method} {url}", traceId, request.Method, request.RequestUri);

        // 过滤/脱敏敏感头部
        var headers = request.Headers.Where(h => !h.Key.Contains("Authorization")).ToList();

        if (request.Content != null)
        {
            var body = await request.Content.ReadAsStringAsync();
            // 可按接口、内容类型灵活控制是否记录
            _logger.LogDebug("[REQUEST BODY] {body}", body);
        }

        var response = await base.SendAsync(request, cancellationToken);
        _logger.LogDebug("[RESPONSE] {traceId} {status}", traceId, response.StatusCode);

        if (response.Content != null)
        {
            var respBody = await response.Content.ReadAsStringAsync();
            _logger.LogDebug("[RESPONSE BODY] {body}", respBody);
        }

        return response;
    }
}
```

注册方式：

```csharp
builder.Services.AddHttpClient("MyApi")
    .AddHttpMessageHandler<HttpLoggingHandler>();
```

如此一来，系统内所有通过该 HttpClient 的外部请求都能标准化记录，方便追踪问题和链路分析。

## 六、安全建议与常见误区

1. **默认排除法**：日志只记录明确安全的内容，敏感信息全部排除。
2. **分环境配置**：开发、测试环境可开启详细日志，生产环境严格收敛内容。
3. **自动化测试验证**：引入自动化测试，确保日志不会泄漏敏感字段。
4. **合规性检查**：遵循如 GDPR、PCI DSS 等法规对日志安全的要求。

## 结语

日志不仅是开发者排查 bug 的利器，更是系统安全与合规的基石。ASP.NET Core 提供的 HttpLogging 和扩展机制，既易用又强大，配合自定义中间件、日志库与安全实践，能满足企业级项目对观测性、审计和风险防控的高标准需求。
