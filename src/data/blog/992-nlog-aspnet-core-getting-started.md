---
pubDatetime: 2026-08-04T14:28:55+08:00
title: "ASP.NET Core 集成 NLog 完整入门"
description: "从安装 NLog.Web.AspNetCore 到两种配置方式、Program.cs 启动关闭模式、Worker Service 接入与 ILogger 注入验证，一文讲清生产可用的 NLog 配置。"
tags: ["NLog", "ASP.NET Core", ".NET", "Logging", "CSharp"]
slug: "nlog-aspnet-core-getting-started"
ogImage: "../../assets/992/01-cover.jpg"
source: "https://www.devleader.ca/2026/08/03/getting-started-with-nlog-in-aspnet-core"
---

在 ASP.NET Core 里配置 NLog 本身不难，但足够多的配置选项和启动模式细节，足以绊倒有经验的开发者：到底用 XML 配置文件还是把一切写进 `appsettings.json`？进程退出时怎么保证日志刷盘？官方文档推荐的 `try/catch/finally` 模式到底解决什么问题？

Nick Cosentino（Dev Leader）2026 年 8 月的这篇文章，从零完整走了一遍 NLog 在 ASP.NET Core 里的设置流程：两种配置风格、Web 与 Worker Service 各自的启动/关闭模式，以及最实用的一组基线配置。读完你就能得到一份可以直接放进 .NET 8 项目的生产级 NLog 配置。

本文按同样的顺序整理为中文教程，并核对了 NuGet 上的最新包版本（NLog 6.1.4 / NLog.Web.AspNetCore 6.1.4）。

## 前置条件

- .NET 8 SDK 或更高版本
- 一个 ASP.NET Core Web API、Blazor 或 Worker Service 项目
- NuGet 访问权限
- 本教程不需要第三方日志服务器——目标只有文件和控制台。系列后续文章会覆盖 Seq、Elasticsearch 和自定义 target

对 .NET 日志的整体背景还不熟悉的读者，建议先读作者的 [Logging in .NET: The Complete Developer's Guide](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)。

## 安装 NLog

ASP.NET Core 项目一个包就够：

```bash
dotnet add package NLog.Web.AspNetCore
```

它会自动拉入基础 `NLog` 包作为依赖，并额外提供：

- `UseNLog()` 主机构建扩展
- ASP.NET Core 感知的 layout renderers（`${aspnet-request-url}`、`${aspnet-mvc-action}`、`${aspnet-TraceIdentifier}` 等）
- 与 `Microsoft.Extensions.Logging` 的集成

Worker Service 或不需要 HTTP 感知 renderers 的控制台应用，则安装：

```bash
dotnet add package NLog
dotnet add package NLog.Extensions.Logging
```

## 两种配置方式

NLog 支持两种配置风格，可以在任何时候切换（或组合），无需改动应用程序代码。

### 方式一：nlog.config（XML）

在项目根目录创建 `nlog.config`：

```xml
<?xml version="1.0" encoding="utf-8" ?>
<nlog xmlns="http://www.nlog-project.org/schemas/NLog.xsd"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      autoReload="true"
      throwConfigExceptions="true"
      internalLogLevel="Warn"
      internalLogFile="${basedir}/internal-nlog.txt">

  <targets>
    <!-- Async wrapper prevents logging from blocking request threads -->
    <target xsi:type="AsyncWrapper" name="asyncFile" queueLimit="5000" overflowAction="Discard">
      <target xsi:type="File"
              name="logfile"
              fileName="${basedir}/logs/app-${shortdate}.log"
              archiveFileName="${basedir}/logs/archives/app-{#}.log"
              archiveEvery="Day"
              archiveNumbering="Rolling"
              maxArchiveFiles="14"
              layout="${longdate}|${uppercase:${level}}|${logger}|${message} ${exception:format=tostring}" />
    </target>

    <target xsi:type="Console"
            name="console"
            layout="${level:truncate=4:uppercase=true}|${logger:shortName=true}|${message} ${exception:format=message}" />
  </targets>

  <rules>
    <!-- Silence noisy framework loggers at Info and below; final stops further evaluation -->
    <logger name="Microsoft.*" maxlevel="Info" final="true" />
    <logger name="System.Net.Http.*" maxlevel="Info" final="true" />
    <!-- All other loggers: Debug and above -->
    <logger name="*" minlevel="Debug" writeTo="asyncFile,console" />
  </rules>
</nlog>
```

然后在 `.csproj` 里注册文件复制到输出目录：

```xml
<ItemGroup>
  <Content Include="nlog.config">
    <CopyToOutputDirectory>Always</CopyToOutputDirectory>
  </Content>
</ItemGroup>
```

根元素 `<nlog>` 上的关键属性：

| 属性                           | 作用                                      |
| ------------------------------ | ----------------------------------------- |
| `autoReload="true"`            | 热重载配置变更，无需重启应用              |
| `throwConfigExceptions="true"` | 配置出错时直接抛异常，而不是静默失败      |
| `internalLogLevel="Warn"`      | NLog 自身诊断日志的级别                   |
| `internalLogFile`              | NLog 记录自身消息的位置（与应用日志分开） |

开发期间**务必设置 `throwConfigExceptions="true"`**。静默的配置失败极难排查——你只会奇怪为什么没有任何日志出现。

### 方式二：appsettings.json

如果团队倾向于把所有配置集中到 `appsettings.json`：

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  },
  "NLog": {
    "autoReload": true,
    "throwConfigExceptions": true,
    "internalLogLevel": "Warn",
    "extensions": [{ "assembly": "NLog.Web.AspNetCore" }],
    "targets": {
      "async": true,
      "logfile": {
        "type": "File",
        "fileName": "${basedir}/logs/app-${shortdate}.log",
        "archiveFileName": "${basedir}/logs/archives/app-{#}.log",
        "archiveEvery": "Day",
        "archiveNumbering": "Rolling",
        "maxArchiveFiles": 14,
        "layout": "${longdate}|${uppercase:${level}}|${logger}|${message} ${exception:format=tostring}"
      },
      "console": {
        "type": "Console",
        "layout": "${level:truncate=4:uppercase=true}|${logger:shortName=true}|${message}"
      }
    },
    "rules": [
      { "logger": "Microsoft.*", "maxLevel": "Info", "final": true },
      { "logger": "System.Net.Http.*", "maxLevel": "Info", "final": true },
      { "logger": "*", "minLevel": "Debug", "writeTo": "logfile,console" }
    ]
  }
}
```

注意 `targets` 块里的 `"async": true`——这是 `appsettings.json` 中等价于把所有 target 包进 `AsyncWrapper` 的写法，一个设置即可让配置中的每个 target 异步写入。

还可以创建一个 `appsettings.Development.json`，只在本地把最小日志级别覆盖为 `Trace`，不动生产配置：

```json
{
  "NLog": {
    "rules": [
      { "logger": "Microsoft.*", "maxLevel": "Info", "final": true },
      { "logger": "*", "minLevel": "Trace", "writeTo": "logfile,console" }
    ]
  }
}
```

## Program.cs 启动设置：ASP.NET Core（.NET 8）

### 使用 XML 配置文件

```csharp
using NLog.Web;

// Get a logger for startup errors before DI is initialized
var logger = NLogBuilder
    .ConfigureNLog("nlog.config")
    .GetCurrentClassLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);

    // Replace the default logging providers with NLog
    builder.Logging.ClearProviders();
    builder.Host.UseNLog();

    builder.Services.AddControllers();
    builder.Services.AddEndpointsApiExplorer();

    var app = builder.Build();

    app.UseHttpsRedirection();
    app.MapControllers();
    app.Run();
}
catch (Exception ex)
{
    // Log startup failures before the host starts
    logger.Fatal(ex, "Application startup failed");
    throw;
}
finally
{
    // Flush and close all targets. Closing a target flushes its internal buffer.
    NLog.LogManager.Shutdown();
}
```

### 使用 appsettings.json 配置

采用 JSON 配置时，NLog 会从 `IConfiguration` 自动发现配置，**不需要显式调用 `ConfigureNLog`**：

```csharp
using NLog.Web;

var builder = WebApplication.CreateBuilder(args);

builder.Logging.ClearProviders();
builder.Host.UseNLog();

builder.Services.AddControllers();

var app = builder.Build();
app.MapControllers();
app.Run();
```

如果想捕获启动前的错误，同样可以加上外层 `try/catch/finally`，手动创建的 logger 用 `NLog.LogManager.Setup().LoadConfigurationFromAppSettings()` 加载配置。

## Worker Service 的接入方式

Worker Service 使用不同的主机构建器，NLog 的设置思路相同：

```csharp
using NLog.Web;

var builder = Host.CreateApplicationBuilder(args);

builder.Logging.ClearProviders();
builder.Logging.AddNLog();  // Use AddNLog() for non-web hosts

builder.Services.AddHostedService<OrderProcessingWorker>();

var host = builder.Build();

try
{
    host.Run();
}
finally
{
    NLog.LogManager.Shutdown();
}
```

关键区别：Worker Service 需要安装 `NLog.Extensions.Logging`，并在 logging builder 上调用 **`AddNLog()`** 而不是 host 上的 `UseNLog()`——`UseNLog()` 是 `IHostBuilder` Web 变体专用的。

## 注入和使用 ILogger

注册完成后，像使用任何其他 provider 一样注入 `ILogger<T>` 即可：

```csharp
public sealed class OrderController : ControllerBase
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

    [HttpPost("{orderId}/process")]
    public async Task<IActionResult> ProcessOrder(int orderId)
    {
        _logger.LogInformation("Received request to process order {OrderId}", orderId);

        try
        {
            await _orderService.ProcessAsync(orderId);
            _logger.LogInformation("Order {OrderId} processed successfully", orderId);
            return Ok();
        }
        catch (OrderNotFoundException ex)
        {
            _logger.LogWarning(ex, "Order {OrderId} not found", orderId);
            return NotFound();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unexpected error processing order {OrderId}", orderId);
            return StatusCode(500);
        }
    }
}
```

务必使用**消息模板语法**——`{OrderId}` 而不是 `$"Order {orderId}"`。字符串插值会把结构化属性折叠进消息字符串；模板语法则把 `OrderId` 保留为独立的命名值，Seq、Elasticsearch 等结构化日志 target 可以单独索引和过滤。

## 验证设置是否生效

运行应用后检查四项：

1. **日志文件出现**——查看 `${basedir}/logs/`（默认是项目输出目录）
2. **控制台输出**——应看到 NLog 格式的输出，而不是 ASP.NET Core 默认格式
3. **框架日志被静音**——`Microsoft.*` 和 `System.Net.Http.*` 规则应显著减少噪音
4. **内部日志干净**——检查 `internal-nlog.txt` 里 NLog 自身的诊断消息，任何错误都说明配置有问题

如果没有任何日志出现，**先查 `internal-nlog.txt`**。`throwConfigExceptions="true"` 会在启动时暴露错误，但内部日志会捕获 NLog 初始化后记录的一切。

## 配置最佳实践

- **开发环境始终设置 `throwConfigExceptions="true"`**。NLog 配置静默失败意味着应用正常启动但什么都不记，开发期要让失败大声一点。
- **所有环境都开 `autoReload="true"`**。运行时调整日志级别和 target 的能力在生产环境极有价值——排查问题时临时提高详细程度，不用重启。
- **在 `finally` 里总是调用 `NLog.LogManager.Shutdown()`**。NLog 内部使用 `AsyncWrapper`，没有 `Shutdown()`，进程退出时缓冲中的日志条目可能永远到不了 target。
- **显式静音 Microsoft 框架日志**。带 `final="true"` 的 `Microsoft.*` 和 `System.Net.Http.*` 规则，防止 EF Core 查询日志和 HTTP 客户端追踪以 MB 为单位淹没你的应用日志。
- **开发专属覆盖放 `appsettings.Development.json`**。不要在生成配置里降低最小日志级别，只为本机开发覆盖。

## 与 Serilog 设置对比

如果之前配过 Serilog，两者的结构差异如下：

|                   | NLog                                  | Serilog                         |
| ----------------- | ------------------------------------- | ------------------------------- |
| 配置风格          | XML 文件或 JSON 节                    | `Program.cs` 里的 C# fluent API |
| ASP.NET Core 集成 | `builder.Host.UseNLog()`              | `builder.Host.UseSerilog()`     |
| 关闭刷盘          | `LogManager.Shutdown()`               | `Log.CloseAndFlush()`           |
| 异步日志          | `AsyncWrapper` target 或 `async=true` | 异步 sink 因包而异              |

从应用代码的视角看，两者对 `ILogger<T>` 的集成方式完全一致。想直接对比 Serilog 的等价设置，可参考作者的 [How to Set Up Serilog in ASP.NET Core: Step-by-Step Guide](https://www.devleader.ca/2026/07/07/how-to-set-up-serilog-in-aspnet-core-step-by-step-guide)。

## 常见问题

**ASP.NET Core 里用 NLog 需要哪个包？**
`NLog.Web.AspNetCore`。这一个包提供 `UseNLog()` 主机扩展、`${aspnet-*}` HTTP 请求上下文 renderers 和 `Microsoft.Extensions.Logging` 集成，基础 `NLog` 包作为依赖自动引入。

**应该用 nlog.config 还是 appsettings.json？**
两者效果相同。想要与应用设置完全分离、可热重载的配置，或团队已熟悉 XML 风格，用 `nlog.config`；想集中所有配置并利用 `appsettings.Development.json` 或环境变量做环境覆盖，用 `appsettings.json`。

**为什么需要 Program.cs 里的 try/catch/finally 模式？**
双重目的：`catch` 块记录 DI 容器初始化之前发生的致命启动错误（否则这些异常可能无人记录）；`finally` 里的 `NLog.LogManager.Shutdown()` 确保 `AsyncWrapper` 等缓冲 target 中的日志在进程退出前刷盘。

**怎么阻止 NLog 记录嘈杂的 Microsoft 框架消息？**
在规则列表顶部为 `Microsoft.*` 和 `System.Net.Http.*` 添加 `final="true"` 的规则。`final="true"` 会在匹配后停止后续规则求值，静音 EF Core SQL 查询日志、HTTP 客户端请求细节等冗长框架输出，不影响应用日志。想保留 Warning 及以上消息就把 `maxlevel` 调到 `Warn`。

**NLog 支持 .NET 8 minimal API 吗？**
支持。`builder.Logging.ClearProviders()` 和 `builder.Host.UseNLog()` 在 controller 和 minimal API 路由下工作方式完全一样，注入到端点处理器或服务里的 `ILogger<T>` 由 NLog 提供。

**internal-nlog.txt 是干什么的？**
NLog 的自诊断日志，记录配置解析错误、target 写入失败等 NLog 内部事件。应用日志不符合预期时，这是第一个该看的地方。生产环境把 `internalLogLevel` 设为 `Warn` 保持安静。

**如何区分 Development 和 Production 的 NLog 配置？**
用 `appsettings.Development.json` 覆盖 `NLog` 节：比如本地把最小日志级别从 `Info` 降到 `Trace`，或加上生产环境没有的 console target。`autoReload="true"` 也允许在任何环境运行时编辑 `nlog.config` 而无需重启。

---

如果你也在搭建 .NET 应用的可观测性体系，欢迎关注 Aide Hub。我们会继续分享 ASP.NET Core、日志、监控和软件工程实践的一手教程。

## 参考

- [Getting Started with NLog in ASP.NET Core（原文，Nick Cosentino）](https://www.devleader.ca/2026/08/03/getting-started-with-nlog-in-aspnet-core)
- [NLog.Web.AspNetCore | NuGet](https://www.nuget.org/packages/NLog.Web.AspNetCore)
- [NLog 官方文档](https://nlog-project.org/)
- [Logging in .NET: The Complete Developer's Guide（作者前作）](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
- [How to Set Up Serilog in ASP.NET Core: Step-by-Step Guide（作者前作）](https://www.devleader.ca/2026/07/07/how-to-set-up-serilog-in-aspnet-core-step-by-step-guide)
