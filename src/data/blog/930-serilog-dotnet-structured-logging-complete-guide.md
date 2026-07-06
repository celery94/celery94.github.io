---
pubDatetime: 2026-07-06T20:29:25+08:00
title: "Serilog 在 .NET 中的完整指南：从安装到生产级结构化日志"
description: "覆盖 Serilog 在 ASP.NET Core 中的完整接入流程：两阶段引导初始化、appsettings.json 配置、Sink 和 Enricher 的使用方式、请求日志中间件，以及输出模板与 JSON 格式化的最佳实践。"
tags:
  [
    "Serilog",
    "Structured Logging",
    "ASP.NET Core",
    ".NET 10",
    "ILogger",
    "Logging",
    "Sink",
    "Enricher",
  ]
slug: "serilog-dotnet-structured-logging-complete-guide"
source: "https://www.devleader.ca/2026/07/05/serilog-in-net-complete-guide-to-structured-logging"
ogImage: "../../assets/930/01-cover.png"
---

`Microsoft.Extensions.Logging` 给 .NET 提供了一层日志抽象，但它的内置 Provider 只有 Console 和 Debug——不够生产环境用。Serilog 是目前 .NET 生态中使用最广的结构化日志库：100+ 个 Sink、丰富的 Enrichment API、`appsettings.json` 完整配置支持、以及通过 `ILogger<T>` 桥接后对应用代码完全透明。

本文覆盖 Serilog 4.x + `Serilog.AspNetCore 10.0.0` 在 .NET 10 下的完整接入方式。

如果你还不熟悉 `ILogger`、结构化日志和日志级别等基础概念，建议先看 [.NET 日志记录的完整指南](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)。

## Serilog 和 MEL 是什么关系

一个关键区分：**Serilog 是 `Microsoft.Extensions.Logging` 的 Provider，不是它的替代品**。你的应用代码始终面对 `ILogger<T>`（框架抽象），Serilog 负责实际的日志输出。这意味着：

- 业务代码零供应商锁定
- 完全兼容使用 `ILogger<T>` 的框架（EF Core、ASP.NET Core、gRPC 等）
- 更换 Provider 不需要改任何业务逻辑

## 在 ASP.NET Core 中接入 Serilog

推荐使用 `Serilog.AspNetCore` 包做两阶段引导初始化：先在 Host 构建完成前用最小 Logger 捕获启动异常，再在 Host 构建后加载完整配置。

### 安装 NuGet 包

```bash
dotnet add package Serilog.AspNetCore
dotnet add package Serilog.Settings.Configuration
dotnet add package Serilog.Sinks.Console
dotnet add package Serilog.Sinks.File
```

### Program.cs 中的两阶段初始化

```csharp
using Serilog;

// 阶段 1：引导 Logger —— 在 Host 构建之前捕获启动异常
Log.Logger = new LoggerConfiguration()
    .WriteTo.Console()
    .CreateBootstrapLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);

    // 阶段 2：Host 构建后加载 appsettings.json 中的完整配置
    builder.Host.UseSerilog((context, services, config) =>
        config
            .ReadFrom.Configuration(context.Configuration)
            .ReadFrom.Services(services)
            .Enrich.FromLogContext());

    builder.Services.AddControllers();

    var app = builder.Build();

    app.UseSerilogRequestLogging(); // 结构化 HTTP 请求日志
    app.MapControllers();
    app.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Application startup failed");
}
finally
{
    Log.CloseAndFlush(); // 确保缓冲日志在退出前全部写入
}
```

### appsettings.json 配置

```json
{
  "Serilog": {
    "Using": ["Serilog.Sinks.Console", "Serilog.Sinks.File"],
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft": "Warning",
        "Microsoft.AspNetCore": "Warning",
        "System": "Warning"
      }
    },
    "WriteTo": [
      {
        "Name": "Console",
        "Args": {
          "outputTemplate": "[{Timestamp:HH:mm:ss} {Level:u3}] {Message:lj}{NewLine}{Exception}"
        }
      },
      {
        "Name": "File",
        "Args": {
          "path": "logs/app-.log",
          "rollingInterval": "Day",
          "retainedFileCountLimit": 7
        }
      }
    ],
    "Enrich": ["FromLogContext", "WithMachineName", "WithThreadId"]
  }
}
```

`MinimumLevel.Override` 是 Serilog 最有用的特性之一——按命名空间设置最低日志级别，把框架噪音压到 Warning，只对业务代码保留 Information 甚至 Debug。

## Serilog 管线：三条流水线

每条日志事件按顺序经过三个阶段：

```
ILogger<T> → Enrichers → Filters → Sinks
```

1. **Enrichers**：给事件附加属性（机器名、线程 ID、进程 ID、HTTP 请求属性、`LogContext` 中的自定义值）。
2. **Filters**：可选的过滤规则，在事件到达 Sink 之前排除不需要的。
3. **Sinks**：格式化事件并写入目标（Console、File、Seq、Elasticsearch 等）。

## Sink：把日志写到该去的地方

Sink 是 Serilog 的输出目标。可以同时激活多个 Sink，每个独立配置最低日志级别和输出格式。

### Console Sink

容器化和云环境的首选——Docker 日志驱动、Kubernetes 日志收集器、Azure Monitor 和 CloudWatch 会自动收集 stdout：

```csharp
.WriteTo.Console(outputTemplate:
    "[{Timestamp:HH:mm:ss} {Level:u3}] {SourceContext} {Message:lj}{NewLine}{Exception}")
```

生产环境输出 JSON 更适合日志聚合器：

```csharp
.WriteTo.Console(new CompactJsonFormatter())
```

### 滚动文件 Sink

```csharp
.WriteTo.File(
    path: "logs/app-.log",
    rollingInterval: RollingInterval.Day,
    retainedFileCountLimit: 30,
    outputTemplate: "{Timestamp:yyyy-MM-dd HH:mm:ss.fff} [{Level:u3}] {Message:lj}{NewLine}{Exception}")
```

生产环境一定要配 `rollingInterval` 和 `retainedFileCountLimit`，避免日志填满磁盘。

### Seq：本地开发日志仪表盘

Seq 是 Serilog 作者团队开发的日志查看器，本地开发时用 Docker 启动：

```bash
docker run -d --name seq -e ACCEPT_EULA=Y -p 5341:80 datalust/seq
```

```csharp
.WriteTo.Seq("http://localhost:5341")
```

访问 `http://localhost:5341`，用 `OrderId = 5678` 或 `@Level = 'Error'` 做结构化查询——比用 `grep` 翻文本日志快得多。

### 异步 Sink 包装

文件或网络 Sink 的 I/O 可能阻塞请求线程。用 `Serilog.Sinks.Async` 把任意 Sink 包装在后台线程中：

```csharp
.WriteTo.Async(a => a.File("logs/app-.log"))
.WriteTo.Async(a => a.Seq("https://logs.example.com"))
```

事件先入内存队列，后台线程异步写，请求线程立即返回。

## Enricher：一次配置，全局追加

Enricher 自动给每条日志事件附加属性，不需要每次手动传参。配置一次，全局生效。

### 内置 Enricher

```bash
dotnet add package Serilog.Enrichers.Environment
dotnet add package Serilog.Enrichers.Thread
dotnet add package Serilog.Enrichers.Process
```

```csharp
.Enrich.FromLogContext()      // 拾取 LogContext.PushProperty() 的值
.Enrich.WithMachineName()     // 添加 MachineName
.Enrich.WithThreadId()        // 添加 ThreadId
.Enrich.WithProcessId()       // 添加 ProcessId
.Enrich.WithEnvironmentName() // 添加 EnvironmentName（Development/Production）
```

### LogContext：每请求动态上下文

`LogContext.PushProperty()` 在作用域内给所有日志事件追加指定属性，作用域结束时自动移除：

```csharp
public async Task<IActionResult> ProcessOrder(int orderId)
{
    using (LogContext.PushProperty("OrderId", orderId))
    using (LogContext.PushProperty("UserId", User.Identity!.Name))
    {
        _logger.LogInformation("开始处理订单");
        await _orderService.ProcessAsync(orderId);
        _logger.LogInformation("订单处理完成");
    }
    return Ok();
}
```

这等价于 `ILogger.BeginScope()`，但 Serilog 的属性语义更丰富。

## 结构化请求日志中间件

`UseSerilogRequestLogging()` 会替换 ASP.NET Core 默认的 HTTP 请求日志，为每个请求输出一条结构化日志条目，包含方法、路径、状态码和耗时：

```csharp
app.UseSerilogRequestLogging(options =>
{
    options.MessageTemplate =
        "HTTP {RequestMethod} {RequestPath} responded {StatusCode} in {Elapsed:0.0000} ms";

    options.GetLevel = (httpContext, elapsed, ex) =>
        ex != null || httpContext.Response.StatusCode > 499
            ? LogEventLevel.Error
            : elapsed > 1000
                ? LogEventLevel.Warning
                : LogEventLevel.Information;

    options.EnrichDiagnosticContext = (diagnosticContext, httpContext) =>
    {
        diagnosticContext.Set("RequestHost", httpContext.Request.Host.Value);
        diagnosticContext.Set("UserAgent", httpContext.Request.Headers.UserAgent);
    };
});
```

一条结构化日志比 ASP.NET Core 默认的多条逐行输出干净得多。你还能根据状态码和耗时自动分等级——5xx 或异常记 Error，超过 1 秒记 Warning，其余记 Information。

## 输出模板和 JSON 格式化

### 文本模板

开发期用人类可读的文本模板：

```
[{Timestamp:HH:mm:ss} {Level:u3}] {SourceContext} {Message:lj}{NewLine}{Exception}
```

- `{Level:u3}`：三字母大写级别（INF、WRN、ERR）
- `{Message:lj}`：文字格式，不转义 JSON
- `{SourceContext}`：`ILogger<T>` 的分类名

### JSON 格式化器

生产环境用 JSON 输出，日志聚合器（Fluent Bit、Logstash、Vector）能做结构化查询：

```csharp
.WriteTo.Console(new CompactJsonFormatter()) // 一行 JSON
.WriteTo.File(new JsonFormatter(), "logs/app-.json") // 缩进 JSON
```

`CompactJsonFormatter` 适合日志聚合管道，`JsonFormatter` 适合人工调试。

## 常见问题

**Serilog 和 MEL 是什么关系？** Serilog 是 MEL 的 Provider。代码写 `ILogger<T>`，Serilog 负责输出。100+ 个 Sink 和丰富的 Enrichment API 是 MEL 内置 Provider 的扩展，不是替代。

**部署到 Azure 还需要 Serilog 吗？** Application Insights 原生集成 MEL。但如果需要多 Sink 输出（开发环境 File + Seq，生产环境 Application Insights），Serilog 的灵活配置很有价值。

**Serilog 4.x 和 .NET 10 兼容吗？** `Serilog.AspNetCore 10.0.0` 完整支持 .NET 9/10，包括 AOT 编译和剪裁。

如果你关注 .NET 开发、工具实践和可运维的软件工程，可以关注 Aide Hub。这里会继续分享能落地的教程和工程观察。

## 参考

- [原文: Serilog in .NET: Complete Guide to Structured Logging](https://www.devleader.ca/2026/07/05/serilog-in-net-complete-guide-to-structured-logging)
- [.NET 日志记录完整指南](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
- [Serilog NuGet Profile](https://www.nuget.org/profiles/serilog)
- [Serilog.AspNetCore NuGet](https://www.nuget.org/packages/Serilog.AspNetCore)
- [Seq 官网](https://datalust.co/seq)
