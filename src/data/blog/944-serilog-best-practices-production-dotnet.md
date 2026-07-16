---
pubDatetime: 2026-07-16T07:32:55+08:00
title: "Serilog 生产环境最佳实践：从开发默认值到线上日志的十二条铁律"
description: "Serilog 在开发环境跑得好好的，上线就拖慢请求、写爆磁盘、把用户手机号打得到处都是。这篇文章整理了十二条经过线上验证的最佳实践——异步 Sink、等级调优、PII 脱敏、关联 ID、日志轮转、循环内日志优化——每条都附带可复制的配置和代码。"
tags: [".NET", "Serilog", "日志", "最佳实践", "ASP.NET Core", "Observability"]
slug: "serilog-best-practices-production-dotnet"
ogImage: "../../assets/944/01-cover.png"
source: "https://www.devleader.ca/2026/07/15/serilog-best-practices-for-production-net-applications/"
---

Serilog 是 .NET 生态里用得最广的结构化日志库，但多数人照着入门教程配好之后就推上线了。开发环境的默认配置在生产环境就是反模式：同步 Sink 堵线程、Debug 级别写爆磁盘、字符串插值吃掉分配、完整对象序列化把密码也打进去。

这篇文章整理的是我在生产环境跑了几年 Serilog 之后沉淀下来的十二条规则。每条都有代码,每条都能直接抄进 `Program.cs`。核心原则只有一条：**日志是生产环境的基础设施，不是调试工具。**

## 异步 Sink：别让日志阻塞请求

Serilog 的 `File` 和 `Seq` Sink 默认是同步的——`Log.Information()` 调用完成之前，磁盘写入或网络请求没返回，当前线程就一直等着。高并发下这直接拖垮吞吐。

原则很简单：**线上环境里，除了 Console，所有 Sink 都包一层 `Async`。**

```bash
dotnet add package Serilog.Sinks.Async
```

```csharp
.WriteTo.Async(a =>
{
    a.File("logs/app.log", rollingInterval: RollingInterval.Day);
    a.Seq("http://your-seq-server:5341");
})
```

`Async` Sink 内部有一个环形缓冲区（默认 10000 条），后台线程批量写出。队列满时的行为由 `blockWhenFull` 控制：默认 `false` 会丢弃事件，适合普通业务日志；审计日志之类丢不得的场景才开 `true`。

```csharp
.WriteTo.Async(a => a.File("logs/app.log"),
    bufferSize: 10000,
    blockWhenFull: false)  // 默认行为，一般不需要显式声明
```

## 生产环境日志等级调优

开发时为了排查方便，`Debug` 甚至 `Verbose` 开满很合理。上线之后还用这套，存储成本和查询噪音都扛不住。

生产环境默认等级调到 `Information`，然后把 `Microsoft` 和 `System` 命名空间的噪音压到 `Warning`：

```json
{
  "Serilog": {
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft": "Warning",
        "Microsoft.AspNetCore": "Warning",
        "Microsoft.EntityFrameworkCore": "Warning",
        "Microsoft.EntityFrameworkCore.Database.Command": "Warning",
        "Microsoft.Hosting.Lifetime": "Information",
        "System.Net.Http.HttpClient": "Warning"
      }
    }
  }
}
```

开发环境在 `appsettings.Development.json` 里单独放宽：

```json
{
  "Serilog": {
    "MinimumLevel": {
      "Default": "Debug",
      "Override": {
        "Microsoft.AspNetCore": "Information",
        "Microsoft.EntityFrameworkCore.Database.Command": "Information"
      }
    }
  }
}
```

> 这里保留 `Microsoft.Hosting.Lifetime` 为 `Information` 是有原因的：启动和关闭日志对于诊断容器重启、健康检查失败非常关键，压到 `Warning` 反而会丢掉线索。

## 永远别在日志里用字符串插值

这是 Serilog 最常见的反模式，也是代价最高的那种。问题不在写法丑不丑，在于两件事同时发生：**字符串在日志等级判断之前就已经分配了，而且插值之后的结构化属性彻底丢掉了。**

```csharp
// 错的——内存先分配，属性全丢失
_logger.LogInformation($"订单 {order.Id} 处理完成，耗时 {elapsed}ms");

// 对的——延迟格式化，保留结构化属性
_logger.LogInformation("订单 {OrderId} 处理完成，耗时 {ElapsedMs}ms",
    order.Id, elapsed);
```

热路径上如果每条日志都在分配字符串，GC 压力会很明显。可以用 `[LoggerMessage]` 源生成器把分配压到零：

```csharp
public static partial class AppLoggers
{
    [LoggerMessage(EventId = 200, Level = LogLevel.Information,
        Message = "订单 {OrderId} 处理完成，耗时 {ElapsedMs}ms")]
    public static partial void OrderProcessed(
        this ILogger logger, string orderId, long elapsedMs);
}

// 调用
_logger.OrderProcessed(order.Id, stopwatch.ElapsedMilliseconds);
```

**判断标准很简单：日志调用那行里看见 `$`，大概率就得改。**

## 谨慎解构对象

Serilog 的 `@` 操作符会把整个对象的所有属性展开成结构化字段，非常方便，也非常危险。一个带导航属性的 EF Core 实体传进去，可能递归序列化几百个字段，甚至触发懒加载额外查询。

全局加限制是成本最低的防御：

```csharp
.Destructure.ToMaximumDepth(3)
.Destructure.ToMaximumStringLength(500)
.Destructure.ToMaximumCollectionCount(10)
```

更好的做法是用专门的日志 DTO（record 完美适合）：

```csharp
public record OrderLogEntry(
    string Id, string CustomerId, decimal Amount, int ItemCount);

_logger.LogInformation("订单已创建 {@OrderSummary}",
    new OrderLogEntry(order.Id, order.CustomerId, order.Total, order.Items.Count));
```

DTO 的本质是**日志契约**：你只暴露需要被查询的字段，不会因为哪天实体加了导航属性就意外泄露数据。

## 保护 PII 和敏感数据

**把日志当成数据泄漏向量来对待。** 手机号、身份证号、银行卡号、Token、密码——这些东西一旦写进日志文件，日志文件本身的访问权限就变成了合规问题。

两种主流方案：

**方案一：自定义 Enricher 按属性名暴力脱敏**

```csharp
public class SensitivePropertyEnricher : ILogEventEnricher
{
    public void Enrich(LogEvent logEvent, ILogEventPropertyFactory propertyFactory)
    {
        foreach (var property in logEvent.Properties.ToList())
        {
            if (IsSensitiveKey(property.Key))
            {
                logEvent.RemovePropertyIfPresent(property.Key);
                logEvent.AddPropertyIfAbsent(
                    propertyFactory.CreateProperty(property.Key, "***REDACTED***"));
            }
        }
    }

    private static bool IsSensitiveKey(string key) =>
        key.Contains("password", StringComparison.OrdinalIgnoreCase) ||
        key.Contains("token", StringComparison.OrdinalIgnoreCase) ||
        key.Contains("secret", StringComparison.OrdinalIgnoreCase) ||
        key.Contains("email", StringComparison.OrdinalIgnoreCase);
}

// 注册
.Enrich.With<SensitivePropertyEnricher>()
```

**方案二：用 Destructurama.Attributed 在类型上打标记**

```bash
dotnet add package Destructurama.Attributed
```

```csharp
public class PaymentRequest
{
    public string OrderId { get; set; } = "";

    [NotLogged]
    public string CardNumber { get; set; } = "";

    [LogMasked(ShowFirst = 4)]
    public string CardHolder { get; set; } = "";  // 输出 "4111***"
}

// 启用
.Destructure.UsingAttributes()
```

方案一覆盖面宽但粗糙，方案二更精细但需要逐个类型加特性。线上用方案一兜底 + 方案二精确控制，两层的组合最稳。

## 加上关联 ID 做分布式追踪

微服务或分布式系统里，一个请求跨两三个服务是常态。不出事的时候各查各的就够了，出了事没有关联 ID，你只能凭时间戳猜。

最简单的方式是在中间件里读取 `X-Correlation-ID` 请求头，推入 `LogContext`，并回传到响应头：

```csharp
public class CorrelationMiddleware
{
    private readonly RequestDelegate _next;

    public CorrelationMiddleware(RequestDelegate next) => _next = next;

    public async Task InvokeAsync(HttpContext context)
    {
        var correlationId = context.Request.Headers["X-Correlation-ID"].FirstOrDefault()
            ?? context.TraceIdentifier;

        context.Response.Headers["X-Correlation-ID"] = correlationId;

        using (Serilog.Context.LogContext.PushProperty("CorrelationId", correlationId))
        {
            await _next(context);
        }
    }
}
```

如果你已经在用 OpenTelemetry，加一个包就能直接把 `Activity.Current` 的 `TraceId` 和 `SpanId` 挂到每条日志上：

```bash
dotnet add package Serilog.Enrichers.Span
```

```csharp
.Enrich.WithSpan()
```

## 配置日志保留和滚动策略

不设 `retainedFileCountLimit` 的后果是磁盘被塞满，而且通常发生在凌晨三点。四个参数必须一起配：

```csharp
.WriteTo.Async(a => a.File(
    path: "logs/app-.log",
    rollingInterval: RollingInterval.Day,
    retainedFileCountLimit: 14,      // 保留 14 天
    fileSizeLimitBytes: 100_000_000, // 单文件 100MB
    rollOnFileSizeLimit: true        // 达到大小限制也滚动
))
```

14 天、单文件 100MB 是一个比较通用的起点，按你的日志量和合规要求调整就好。关键是**四个参数一个都别漏。**

## 别在循环里打日志

遍历十万条记录的时候每行一条 `Log.Information`，等于是拿日志框架做进度条。异步队列会被瞬间打满，真正需要排查的日志反而被挤掉。

把这个习惯改成：循环内只记录异常项，循环结束后输出一份汇总：

```csharp
var processed = 0;
var errors = new List<string>();

foreach (var item in largeCollection)
{
    try
    {
        Process(item);
        processed++;
    }
    catch (Exception ex)
    {
        errors.Add(item.Id);
        _logger.LogWarning(ex, "处理条目 {ItemId} 失败", item.Id);
    }
}

_logger.LogInformation("批次处理完成：成功 {Processed} 条，失败 {ErrorCount} 条",
    processed, errors.Count);
```

如果确实需要进度（比如长时间批处理），可以每 N 条或每隔 N 秒输出一次进度摘要，而不是逐条打。

## 给有意义的事件打日志，别记录实现细节

不是所有代码执行都值得变成一条日志。Serilog 给了你结构化能力，不代表每个方法出入口、每个内部变量赋值都值得一条 `Log.Debug`。

该记的：请求和响应、外部服务调用、业务事件（订单创建、支付完成）、配置变更、异常、性能阈值告警。

不该记的：方法进入和退出、内部变量中间值、逐行执行痕迹。

```csharp
// 有用
_logger.LogInformation("订单 {OrderId} 总额计算完成：{Total}（{ItemCount} 件商品，税率 {TaxRate}%）",
    orderId, total, itemCount, taxRate);

// 没用
_logger.LogDebug("进入 CalculateTotal 方法");
_logger.LogDebug("total 变量当前值为 {Total}", total);
```

换一个角度来看：**一条日志值得写，当且仅当它能在你凌晨被叫醒时帮你定位问题，或者在日常运营中帮你理解系统行为。** 过不了这个标准，就别记。

## 用健康检查配合日志告警

ASP.NET Core 的健康检查端点不仅能返回 JSON，还能把检查结果以结构化事件的形式打进 Serilog。这样你就可以在 Seq 或其他日志后端上对健康检查失败设置告警：

```csharp
app.MapHealthChecks("/health", new HealthCheckOptions
{
    ResponseWriter = async (ctx, report) =>
    {
        var result = new
        {
            Status = report.Status.ToString(),
            Checks = report.Entries.Select(e => new
            {
                e.Key,
                Status = e.Value.Status.ToString(),
                e.Value.Description,
                e.Value.Duration
            })
        };

        _logger.LogInformation("健康检查完成 {@HealthCheckResult}", result);
        await ctx.Response.WriteAsJsonAsync(result);
    }
});
```

## 完整生产配置

把所有规则拼在一起，一个可直接上线的 `Program.cs` 大概长这样：

```csharp
Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Information()
    .MinimumLevel.Override("Microsoft", LogEventLevel.Warning)
    .MinimumLevel.Override("Microsoft.AspNetCore", LogEventLevel.Warning)
    .MinimumLevel.Override("Microsoft.EntityFrameworkCore", LogEventLevel.Warning)
    .Enrich.FromLogContext()
    .Enrich.WithMachineName()
    .Enrich.WithSpan()
    .Enrich.With<SensitivePropertyEnricher>()
    .Destructure.ToMaximumDepth(3)
    .Destructure.ToMaximumStringLength(500)
    .Destructure.ToMaximumCollectionCount(10)
    .Destructure.UsingAttributes()
    .WriteTo.Console()
    .WriteTo.Async(a => a.File(
        path: "logs/app-.log",
        rollingInterval: RollingInterval.Day,
        retainedFileCountLimit: 14,
        fileSizeLimitBytes: 100_000_000,
        rollOnFileSizeLimit: true))
    .WriteTo.Async(a => a.Seq("http://your-seq-server:5341"))
    .CreateBootstrapLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);

    builder.Host.UseSerilog((ctx, lc) =>
        lc.ReadFrom.Configuration(ctx.Configuration));

    builder.Services.AddHttpContextAccessor();

    var app = builder.Build();

    app.UseMiddleware<CorrelationMiddleware>();
    app.UseSerilogRequestLogging();

    app.MapHealthChecks("/health", new HealthCheckOptions
    {
        ResponseWriter = async (ctx, report) =>
        {
            // ... 健康检查结构化日志
            await ctx.Response.WriteAsJsonAsync(new
            {
                Status = report.Status.ToString(),
                Checks = report.Entries.Select(e => new
                {
                    e.Key,
                    Status = e.Value.Status.ToString(),
                    e.Value.Description
                })
            });
        }
    });

    app.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "应用启动失败");
}
finally
{
    Log.CloseAndFlush();
}
```

## 小结

这十二条规则按重要程度排序，前面六条上线之前必须配好，后面六条根据流量和系统复杂度逐步加上。

整理一下速查清单：

| #   | 规则                                                          |
| --- | ------------------------------------------------------------- |
| 1   | 文件 / 网络 Sink 包在 `Async()` 里                            |
| 2   | 生产默认等级 `Information`，`Microsoft.*` 压到 `Warning`      |
| 3   | 日志调用里禁掉 `$` 字符串插值                                 |
| 4   | 解构加深度 / 长度 / 集合上限，用 DTO 代替实体                 |
| 5   | PII 字段必须脱敏（Enricher 兜底 + Attribute 精确控制）        |
| 6   | 传播 `X-Correlation-ID`，对接 OpenTelemetry                   |
| 7   | 文件日志配置 `retainedFileCountLimit` 和 `fileSizeLimitBytes` |
| 8   | 循环内只记异常，循环外记汇总                                  |
| 9   | 只记业务边界和异常，不记实现细节                              |
| 10  | 异常对象传给第一个参数，不调 `ex.ToString()`                  |
| 11  | 健康检查结果写进结构化日志，对接告警                          |
| 12  | 启动时用 Bootstrap Logger 兜底，避免配置加载阶段的日志丢失    |

## 参考

- [Serilog Best Practices for Production .NET Applications — Dev Leader](https://www.devleader.ca/2026/07/15/serilog-best-practices-for-production-net-applications/)
- [Serilog.Sinks.Async](https://github.com/serilog/serilog-sinks-async)
- [Destructurama.Attributed](https://github.com/destructurama/attributed)
- [Serilog.Enrichers.Span](https://github.com/serilog/serilog-enrichers-span)
- [[LoggerMessage] Source Generator — Microsoft Docs](https://learn.microsoft.com/en-us/dotnet/core/extensions/logging/source-generation)
