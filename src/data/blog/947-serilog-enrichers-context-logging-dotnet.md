---
pubDatetime: 2026-07-16T15:14:10+08:00
title: "Serilog Enrichers：给每条日志自动注入上下文"
description: "Serilog Enrichers 在日志管线中自动为每条日志附加机器名、线程 ID、关联 ID 等诊断属性，配置一次全局生效。本文覆盖标准 Enricher、LogContext 动态上下文、自定义 Enricher 和日志作用域，附带完整的 C# 代码示例。"
tags: ["Serilog", "Serilog Enrichers", "C#", ".NET", "结构化日志"]
slug: "serilog-enrichers-context-logging-dotnet"
ogImage: "../../assets/947/01-cover.png"
source: "https://www.devleader.ca/2026/07/11/serilog-enrichers-adding-context-to-every-log-entry"
---

Serilog Enrichers 解决的是日志里最烦人的一件事：保证每条日志都带着排查问题需要的上下文。没有 Enricher 的时候，你总是在事后问自己"这条日志是哪个服务器打的？""当时是哪个请求？""哪个用户触发了这段代码？"——然后发现写日志的时候根本没记这些信息。

Enricher 在 Serilog 的管线里自动给每条日志事件附加属性，在所有 sink 收到日志之前就处理完了。配置一次，之后就不用再管。不管你需要多服务器调试用的机器名、分布式追踪用的关联 ID，还是自定义的应用元数据，Enricher 都能透明地搞定。

## 什么是 Serilog Enricher

Enricher 是 Serilog 管线中的一个组件，在日志事件到达 sink 之前添加、删除或修改属性。Enricher 实现 `ILogEventEnricher` 接口，对每条经过管线的事件执行。

```
数据源 → [Enrichers] → Filters → Sinks
```

Enricher 本质上是装饰器模式的思路：它在源代码不知情的情况下给日志事件追加属性。代码里写的是 `_logger.LogInformation("订单 {OrderId} 已创建", orderId)`，Enricher 静默地给同一条事件加上 `MachineName=prod-01`、`ThreadId=15`、`CorrelationId=abc-123`。

## 标准 Serilog Enricher

### 环境 Enricher

```bash
dotnet add package Serilog.Enrichers.Environment
```

```csharp
.Enrich.WithMachineName()       // 添加 MachineName 属性
.Enrich.WithEnvironmentName()   // 添加 EnvironmentName
.Enrich.WithEnvironmentUserName() // 添加 EnvironmentUserName
```

`WithMachineName()` 在任何多服务器部署里都很值钱——你的服务跑了 10 个 pod，错误一出来第一反应就是"哪个 pod？"。每条日志自带 `MachineName`，当场回答这个问题。

### 线程 Enricher

```bash
dotnet add package Serilog.Enrichers.Thread
```

```csharp
.Enrich.WithThreadId()   // 添加 ThreadId（int）
.Enrich.WithThreadName() // 添加 ThreadName（如果命名了）
```

线程 ID 在并行处理的 Worker Service 里特别有用——你可以追踪某个工作项在线程生命周期里的所有日志。

### 进程 Enricher

```bash
dotnet add package Serilog.Enrichers.Process
```

```csharp
.Enrich.WithProcessId()
.Enrich.WithProcessName()
```

### 关联 ID Enricher

```bash
dotnet add package Serilog.Enrichers.CorrelationId
```

```csharp
.Enrich.WithCorrelationId() // 读取 X-Correlation-ID 头并添加 CorrelationId
```

加上中间件确保 header 被传播：

```csharp
builder.Services.AddHttpContextAccessor();

app.Use(async (context, next) =>
{
    if (!context.Request.Headers.ContainsKey("X-Correlation-ID"))
        context.Request.Headers["X-Correlation-ID"] =
            Guid.NewGuid().ToString();
    await next();
});
```

关联 ID 在分布式系统里是关键——前端发一个请求扇出到五个微服务，同一个关联 ID 能把所有服务上的日志串联起来。

## 通过 appsettings.json 配置 Enricher

标准 Enricher 可以完全通过 `appsettings.json` 配置：

```json
{
  "Serilog": {
    "Enrich": [
      "FromLogContext",
      "WithMachineName",
      "WithThreadId",
      "WithProcessId",
      "WithEnvironmentName"
    ]
  }
}
```

`Enrich` 数组里的字符串对应 `LoggerEnrichmentConfiguration` 的方法名。带参数的 Enricher（如 `WithProperty`）需要用代码配置。

## 用静态属性做 Enrich

给每条日志加一个固定值——适合应用名称、版本号、部署环境：

```csharp
.Enrich.WithProperty("Application", "OrderApi")
.Enrich.WithProperty("Version",
    Assembly.GetExecutingAssembly()
        .GetName().Version?.ToString() ?? "unknown")
.Enrich.WithProperty("DeploymentEnvironment",
    builder.Environment.EnvironmentName)
```

`appsettings.json` 写法：

```json
{
  "Serilog": {
    "Enrich": [
      {
        "Name": "WithProperty",
        "Args": {
          "name": "Application",
          "value": "OrderApi"
        }
      }
    ]
  }
}
```

当多个应用把日志发到同一个 Seq 实例或 Elasticsearch 集群时，这些静态属性让你可以马上过滤到 `Application = 'OrderApi'`。

## LogContext：动态的按作用域 Enrich

`Serilog.Context.LogContext` 允许你在当前逻辑线程上下文上压入属性，在一个作用域块内有效。块内发出的所有日志事件都带着这些属性：

```csharp
using Serilog.Context;

public async Task<IActionResult> ProcessPayment(
    PaymentRequest request)
{
    using (LogContext.PushProperty("PaymentId", request.PaymentId))
    using (LogContext.PushProperty("CustomerId", request.CustomerId))
    using (LogContext.PushProperty("Amount", request.Amount))
    {
        _logger.LogInformation("开始处理支付");

        var result = await _paymentGateway.ChargeAsync(request);

        if (result.Succeeded)
        {
            _logger.LogInformation(
                "支付成功，交易号 {TransactionId}",
                result.TransactionId);
        }
        else
        {
            _logger.LogWarning(
                "支付被拒绝: {DeclineReason}",
                result.DeclineReason);
        }
    }
    // 属性在此处从上下文中移除

    return Ok();
}
```

`using` 块内的每一条日志都带着 `PaymentId`、`CustomerId`、`Amount`——但这些值不需要出现在 `LogInformation` 的消息模板里。代码干净，上下文透明注入。

### 在中间件中用 LogContext

一个常见模式是在 ASP.NET Core 中间件里压入关联 ID 或用户 ID，让每个请求的日志自动带注释：

```csharp
public class LogContextMiddleware
{
    private readonly RequestDelegate _next;

    public LogContextMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var correlationId = context.Request.Headers["X-Correlation-ID"]
            .FirstOrDefault() ?? context.TraceIdentifier;

        using (LogContext.PushProperty("CorrelationId", correlationId))
        using (LogContext.PushProperty("RequestPath",
            context.Request.Path))
        using (LogContext.PushProperty("UserId",
            context.User.FindFirst("sub")?.Value ?? "anonymous"))
        {
            await _next(context);
        }
    }
}
```

在 `Program.cs` 中注册：

```csharp
app.UseMiddleware<LogContextMiddleware>();
app.UseSerilogRequestLogging(); // 放在 LogContext 中间件之后
```

请求生命周期内的每条日志现在都带着 `CorrelationId`、`RequestPath`、`UserId`——不管日志从哪个类、哪一层发出。

## 用 ILogger 的日志作用域

内置 `ILogger.BeginScope()` API 等价于 Serilog 的 `LogContext.PushProperty()`——配上 `FromLogContext()`，通过 `BeginScope()` 压入的作用域会被 Serilog 捕获并输出：

```csharp
public class OrderProcessor
{
    private readonly ILogger<OrderProcessor> _logger;

    public OrderProcessor(ILogger<OrderProcessor> logger)
    {
        _logger = logger;
    }

    public async Task ProcessBatchAsync(IEnumerable<Order> orders)
    {
        using var batchScope = _logger.BeginScope(
            new Dictionary<string, object>
        {
            ["BatchId"] = Guid.NewGuid().ToString("N"),
            ["BatchSize"] = orders.Count()
        });

        _logger.LogInformation("开始批次处理");

        foreach (var order in orders)
        {
            using var orderScope = _logger.BeginScope(
                new Dictionary<string, object>
            {
                ["OrderId"] = order.Id,
                ["CustomerId"] = order.CustomerId
            });

            _logger.LogInformation("处理订单");
            await ProcessSingleOrderAsync(order);
            _logger.LogInformation("订单处理完毕");
        }

        _logger.LogInformation("批次处理完成");
    }
}
```

要让 `BeginScope()` 的属性出现在 Serilog 输出中，需要满足两个条件：

1. Serilog 配置里必须有 `Enrich.FromLogContext()`
2. 如果用 Console sink 配了文本模板，模板里必须包含 `{Properties}`（或者直接用 JSON 格式化器）

Console sink 可以用这个模板显示所有作用域属性：

```
"[{Timestamp:HH:mm:ss} {Level:u3}] {Message:lj} {Properties:j}{NewLine}{Exception}"
```

## 自定义 Enricher

标准 Enricher 不够用时，实现 `ILogEventEnricher`：

```csharp
using Serilog.Core;
using Serilog.Events;

public class TenantEnricher : ILogEventEnricher
{
    private readonly ITenantAccessor _tenantAccessor;

    public TenantEnricher(ITenantAccessor tenantAccessor)
    {
        _tenantAccessor = tenantAccessor;
    }

    public void Enrich(
        LogEvent logEvent,
        ILogEventPropertyFactory propertyFactory)
    {
        var tenantId = _tenantAccessor.GetCurrentTenantId();

        if (!string.IsNullOrEmpty(tenantId))
        {
            var property = propertyFactory
                .CreateProperty("TenantId", tenantId);
            logEvent.AddPropertyIfAbsent(property);
        }
    }
}
```

用 `ReadFrom.Services()` 注册，利用 DI 注入依赖：

```csharp
// 注册到 DI
builder.Services.AddSingleton<TenantEnricher>();
builder.Services.AddHttpContextAccessor();

// 通过 ReadFrom.Services() 注册到 Serilog
builder.Host.UseSerilog((ctx, services, config) =>
    config
        .ReadFrom.Configuration(ctx.Configuration)
        .ReadFrom.Services(services)
        .Enrich.FromLogContext());
```

`ReadFrom.Services(services)` 会扫描 DI 容器中所有 `ILogEventEnricher` 注册并自动加入——不需要手动 `Enrich.With<TenantEnricher>()`。

## Enricher 性能注意事项

Enricher 在每条日志事件上都执行，所以 `Enrich()` 方法里不要做昂贵的操作（数据库查询、HTTP 调用）。替代方案：

- 缓存静态值（机器名、进程 ID、应用版本永远不会变）
- 从中间件用请求作用域的 `LogContext.PushProperty()`（每个请求一次，不是每条日志一次）
- 把计算值存为带懒初始化的静态 Enricher

```csharp
public class CachedMachineEnricher : ILogEventEnricher
{
    private static readonly LogEventProperty MachineNameProperty =
        new("MachineName",
            new ScalarValue(Environment.MachineName));

    private static readonly LogEventProperty AppVersionProperty =
        new("AppVersion", new ScalarValue(
            Assembly.GetEntryAssembly()
                ?.GetName().Version?.ToString() ?? "unknown"));

    public void Enrich(
        LogEvent logEvent,
        ILogEventPropertyFactory propertyFactory)
    {
        logEvent.AddPropertyIfAbsent(MachineNameProperty);
        logEvent.AddPropertyIfAbsent(AppVersionProperty);
    }
}
```

## 参考

- [原文：Serilog Enrichers: Adding Context to Every Log Entry](https://www.devleader.ca/2026/07/11/serilog-enrichers-adding-context-to-every-log-entry)
