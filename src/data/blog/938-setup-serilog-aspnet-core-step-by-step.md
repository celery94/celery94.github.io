---
pubDatetime: 2026-07-09T11:30:14+08:00
title: "在 ASP.NET Core 里配好 Serilog：一步步做下来"
description: "Serilog 接入 ASP.NET Core 的推荐做法就那几步，但第一次做容易踩坑：漏掉启动异常、bootstrap logger 用太久、没走 appsettings.json 配置。这篇按 .NET 9/10 把两阶段初始化、分环境配置、请求日志中间件和验证完整走一遍。"
tags: ["Serilog", "ASP.NET Core", "结构化日志", ".NET", "日志"]
slug: "setup-serilog-aspnet-core-step-by-step"
source: "https://www.devleader.ca/2026/07/07/how-to-set-up-serilog-in-aspnet-core-stepbystep-guide"
ogImage: "../../assets/938/01-cover.png"
---

在 ASP.NET Core 里配 Serilog，理解了推荐模式之后其实很直接，但第一次做的人常被几个坑绊住。最常见的错误是接线方式漏掉了启动阶段的异常、让 bootstrap logger 跑得太久，或者没用上 `appsettings.json` 驱动的配置。

这篇按 .NET 9 和 .NET 10，把生产可用的 Serilog 接入完整走一遍：装包、两阶段初始化、`appsettings.json` 分环境配置、结构化请求日志中间件，以及最后怎么验证一切正常。如果你对 Serilog 和 .NET 日志的基础还不熟，建议先补一下再往下看。

## 第一步：装必要的包

先装 ASP.NET Core 的核心 Serilog 包：

```bash
dotnet add package Serilog.AspNetCore
dotnet add package Serilog.Settings.Configuration
```

`Serilog.AspNetCore` 提供 `UseSerilog()` 和请求日志中间件，`Serilog.Settings.Configuration` 让你能用 `appsettings.json` 配置。然后按需要装 sink（输出目标）：

```bash
dotnet add package Serilog.Sinks.Console
dotnet add package Serilog.Sinks.File
```

开发时想配合 Seq 看日志：

```bash
dotnet add package Serilog.Sinks.Seq
```

需要 enricher（给日志附加机器名、线程等信息）：

```bash
dotnet add package Serilog.Enrichers.Environment
dotnet add package Serilog.Enrichers.Thread
```

## 第二步：配置两阶段初始化

ASP.NET Core 里 Serilog 接入的推荐模式用的是两阶段初始化。它解决一个关键问题：如果你的应用启动失败（配置错误、缺依赖、数据库连不上），你需要一个在**主机构建之前**就已经在跑的 logger。

```csharp
// Program.cs
using Serilog;

// 阶段一：bootstrap logger——在主机构建前就能捕获错误
Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Override("Microsoft", LogEventLevel.Warning)
    .Enrich.FromLogContext()
    .WriteTo.Console()
    .CreateBootstrapLogger();

try
{
    Log.Information("Starting application");

    var builder = WebApplication.CreateBuilder(args);

    // 阶段二：完整 logger——从 appsettings.json 和 DI 服务读取配置
    builder.Host.UseSerilog((context, services, configuration) =>
        configuration
            .ReadFrom.Configuration(context.Configuration)
            .ReadFrom.Services(services)
            .Enrich.FromLogContext());

    builder.Services.AddControllers();
    // 其他服务注册...

    var app = builder.Build();

    app.UseSerilogRequestLogging(); // 放在 UseRouting/UseEndpoints 之前

    app.UseRouting();
    app.UseAuthorization();
    app.MapControllers();

    app.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Application terminated unexpectedly");
    return 1;
}
finally
{
    // 重要：进程退出前把所有缓冲的日志事件刷出去
    await Log.CloseAndFlushAsync();
}

return 0;
```

### 为什么要两阶段

| 关注点                    | Bootstrap Logger       | 完整 Logger                      |
| ------------------------- | ---------------------- | -------------------------------- |
| 捕获启动失败              | ✅ 能                  | ❌ 太晚了                        |
| appsettings.json 配置     | ❌ 还读不到            | ✅ 完整访问                      |
| 注入的服务（如 enricher） | ❌ 还没注册            | ✅ 通过 `ReadFrom.Services()`    |
| 运行时机                  | `builder.Build()` 之前 | `builder.Host.UseSerilog()` 之后 |

`try/catch/finally` 块保证启动异常被记进 bootstrap logger，`finally` 里的 `Log.CloseAndFlushAsync()` 保证进程退出前所有缓冲日志都被写出——这对异步 sink（文件、Seq、云服务）尤其关键。

## 第三步：配置 appsettings.json

把 Serilog 配置从代码搬进 `appsettings.json`，换取分环境的灵活性。完整 logger 通过 `.ReadFrom.Configuration(context.Configuration)` 读取它。

### appsettings.json（基础配置）

```json
{
  "Serilog": {
    "Using": ["Serilog.Sinks.Console", "Serilog.Sinks.File"],
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft": "Warning",
        "Microsoft.AspNetCore": "Warning",
        "Microsoft.EntityFrameworkCore": "Warning",
        "System": "Warning"
      }
    },
    "WriteTo": [
      {
        "Name": "Console",
        "Args": {
          "outputTemplate": "[{Timestamp:HH:mm:ss} {Level:u3}] {SourceContext}{NewLine}  {Message:lj}{NewLine}{Exception}"
        }
      },
      {
        "Name": "File",
        "Args": {
          "path": "logs/app-.log",
          "rollingInterval": "Day",
          "retainedFileCountLimit": 7,
          "outputTemplate": "{Timestamp:yyyy-MM-dd HH:mm:ss.fff zzz} [{Level:u3}] {SourceContext} {Message:lj}{NewLine}{Exception}"
        }
      }
    ],
    "Enrich": ["FromLogContext", "WithMachineName", "WithThreadId"]
  }
}
```

### appsettings.Development.json（本地开发覆盖）

```json
{
  "Serilog": {
    "MinimumLevel": {
      "Default": "Debug",
      "Override": {
        "Microsoft": "Information",
        "System": "Information"
      }
    },
    "WriteTo": [
      { "Name": "Console" },
      {
        "Name": "Seq",
        "Args": { "serverUrl": "http://localhost:5341" }
      }
    ]
  }
}
```

### appsettings.Production.json（云/容器配置）

```json
{
  "Serilog": {
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft": "Warning",
        "System": "Warning"
      }
    },
    "WriteTo": [
      {
        "Name": "Console",
        "Args": {
          "formatter": "Serilog.Formatting.Compact.CompactJsonFormatter, Serilog.Formatting.Compact"
        }
      }
    ]
  }
}
```

生产容器里把 JSON 写到 stdout，让你的日志聚合器（Fluent Bit、Logstash、Vector、Azure Monitor）不用正则提取就能解析结构化属性。

## 第四步：加上 Serilog 请求日志

ASP.NET Core 默认的请求日志每个请求会发多条——路由一条、控制器一条、响应一条。用一条结构化的单行记录替换它们：

```csharp
// Program.cs 里，放在 UseRouting 之前
app.UseSerilogRequestLogging(options =>
{
    // 自定义消息模板
    options.MessageTemplate =
        "HTTP {RequestMethod} {RequestPath} responded {StatusCode} in {Elapsed:0.0000} ms";

    // 根据响应控制日志级别
    options.GetLevel = (httpContext, elapsed, ex) =>
    {
        if (ex != null || httpContext.Response.StatusCode >= 500)
            return LogEventLevel.Error;
        if (httpContext.Response.StatusCode >= 400 || elapsed > 2000)
            return LogEventLevel.Warning;
        return LogEventLevel.Information;
    };

    // 给每个请求加额外属性
    options.EnrichDiagnosticContext = (diagnosticContext, httpContext) =>
    {
        diagnosticContext.Set("RequestHost", httpContext.Request.Host.Value);
        diagnosticContext.Set("RequestScheme", httpContext.Request.Scheme);
        diagnosticContext.Set("UserAgent", httpContext.Request.Headers.UserAgent.ToString());
        if (httpContext.User.Identity?.IsAuthenticated == true)
        {
            diagnosticContext.Set("UserId", httpContext.User.FindFirst("sub")?.Value ?? "unknown");
        }
    };
});
```

每个请求会产出这样一行：

```
[14:23:01 INF] HTTP GET /api/orders responded 200 in 12.4 ms
```

并带上结构化属性：`RequestMethod=GET`、`RequestPath=/api/orders`、`StatusCode=200`、`Elapsed=12.4`、`RequestHost=localhost`、`UserId=user-123`。这里有个中间件顺序的坑：`UseSerilogRequestLogging()` 要放在 `UseRouting()`、`UseAuthorization()` 和端点映射之前，这样它才能把认证和路由的开销一起算进整条管线的耗时。

## 第五步：在应用里用 ILogger

Serilog 配好后，像平常一样注入 `ILogger<T>`。所有走 `ILogger` 桥接的日志事件都会被 Serilog 透明接收：

```csharp
public class OrderController : ControllerBase
{
    private readonly ILogger<OrderController> _logger;
    private readonly IOrderService _orderService;

    public OrderController(
        ILogger<OrderController> logger,
        IOrderService orderService)
    {
        _logger = logger;
        _orderService = orderService;
    }

    [HttpPost]
    public async Task<IActionResult> CreateOrder(CreateOrderRequest request)
    {
        _logger.LogInformation(
            "Creating order for customer {CustomerId} with {ItemCount} items",
            request.CustomerId,
            request.Items.Count);

        try
        {
            var order = await _orderService.CreateAsync(request);

            _logger.LogInformation(
                "Order {OrderId} created successfully for customer {CustomerId}",
                order.Id,
                request.CustomerId);

            return Created($"/api/orders/{order.Id}", order);
        }
        catch (ValidationException ex)
        {
            _logger.LogWarning(ex,
                "Order validation failed for customer {CustomerId}: {ValidationErrors}",
                request.CustomerId,
                string.Join(", ", ex.Errors));

            return BadRequest(ex.Errors);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex,
                "Unexpected error creating order for customer {CustomerId}",
                request.CustomerId);

            return StatusCode(500);
        }
    }
}
```

注意消息模板里的 `{CustomerId}`、`{ItemCount}`、`{OrderId}` 会变成结构化属性，Seq 等日志聚合器可以按它们过滤和查询。

## 第六步：验证配置

跑起来看 Serilog 是否工作：

```bash
dotnet run
```

你应该看到类似这样的输出：

```
[14:23:00 INF] Starting application
[14:23:00 INF] Now listening on: https://localhost:7001
[14:23:01 INF] HTTP GET /api/health responded 200 in 5.2 ms
[14:23:01 INF] Creating order for customer cust-456 with 3 items
[14:23:01 INF] Order ord-789 created successfully for customer cust-456
```

本地用 Seq 的话，先起一个容器：

```bash
docker run -d --name seq -e ACCEPT_EULA=Y -p 5341:80 datalust/seq
```

然后打开 `http://localhost:5341` 去查询你的结构化日志属性。

## 几个常见坑

**Serilog 什么都不打。** 最常见的原因是漏了 `Log.CloseAndFlushAsync()`——进程退出前缓冲 sink 没刷出（短命的测试运行里尤其明显）。测试里显式调 `Log.CloseAndFlush()`。

**启动异常不出现。** 如果应用在 `builder.Host.UseSerilog()` 跑之前就崩了，靠的是 bootstrap logger。确认 `try/catch/finally` 包住了整个 `Program.cs`，而不只是 `app.Run()`。

**appsettings.json 的覆盖不生效。** `appsettings.json` 里的 `Serilog:Using` 数组必须列出你要配置的 sink 的**程序集名**（不是 NuGet 包名）。例如 `Using` 里的 `Serilog.Sinks.Seq` 对应 `Serilog.Sinks.Seq` 这个 NuGet 包。

**开发时日志量太大。** 在 `appsettings.Development.json` 里把你自己命名空间的最低级别设成 `Debug`，但把 `Microsoft.*` 和 `System.*` 保持在 `Warning`，避免框架内部的噪音。

## 常见问题

**Serilog 请求日志的中间件顺序？**
把 `app.UseSerilogRequestLogging()` 放在 `UseRouting()`、`UseAuthorization()` 和端点映射之前，这样中间件能捕获包含认证和路由开销在内的整条管线耗时。

**该用 `Log.CloseAndFlush()` 还是 `Log.CloseAndFlushAsync()`？**
在顶层 `Program.cs` 里优先用 `await Log.CloseAndFlushAsync()`（.NET 6+ 的顶层 await 语句）。在不能用 async 的场景（老式 Main 方法、测试拆解）用 `Log.CloseAndFlush()`。

**不用 appsettings.json 能用 Serilog 吗？**
能。完全用代码配置 `.WriteTo.Console()`、`.WriteTo.File()` 等没问题。但 ASP.NET Core 推荐用 `appsettings.json`，因为它支持不重新编译就分环境覆盖。

**怎么压掉特定框架的日志？**
在配置里用 `MinimumLevel.Override()`。例如 `"Microsoft.EntityFrameworkCore.Database.Command": "Warning"` 压掉 EF Core 的 SQL 查询日志。`Override` 段接受任何命名空间前缀，作用于该命名空间下所有 logger。

**Worker Service 怎么加 Serilog？**
同样的模式。`builder.Host.UseSerilog(...)` 把 Serilog 配成日志提供方。Worker service 没有 HTTP 请求日志，所以跳过 `UseSerilogRequestLogging()`。

## 小结

在 ASP.NET Core 配 Serilog 归结为五步：装包、在 `Program.cs` 配两阶段初始化、用带分环境覆盖的 `appsettings.json`、加 `UseSerilogRequestLogging()` 中间件、像平常一样注入 `ILogger<T>`。

把这个基础铺好后，你的应用就能产出结构化日志数据，可以在 Seq 里查询、导出到云日志服务，也能用它精确定位问题。

## 参考

- [How to Set Up Serilog in ASP.NET Core: Step-by-Step Guide](https://www.devleader.ca/2026/07/07/how-to-set-up-serilog-in-aspnet-core-stepbystep-guide)
- [Seq 官网](https://datalust.co/seq)
  </content>
