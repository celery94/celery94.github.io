---
pubDatetime: 2026-04-29T08:11:00+08:00
title: ".NET + Postgres 实现高性能分布式缓存：HybridCache 实战"
description: "本文逐步演示如何在 .NET 10 控制台应用中集成 Azure Database for PostgreSQL 分布式缓存与 HybridCache，从零构建一套内存层 + 持久层协同的高性能缓存方案，附完整代码和性能对比数据。"
tags: [".NET", "Caching", "PostgreSQL", "Azure", "HybridCache", "C#", "Performance"]
slug: "dotnet-distributed-caching-postgres-azure-hybridcache"
ogImage: "../../assets/762/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/high-performance-distributed-caching-dotnet-postgres-azure"
---

现代 .NET 应用需要应对越来越复杂的数据源、端点和微服务，保持高吞吐、快响应的压力随之增大。缓存是解决这个问题最直接的手段之一——但"用什么缓存"和"怎么用"之间，仍然有很大的设计空间。

这篇文章来自 .NET 官方博客，作者 Jared Meade 用一个可运行的 .NET 10 控制台示例，演示了如何把 Azure Database for PostgreSQL 作为分布式缓存后端，再叠加 `HybridCache` 的内存层，最终让应用同时享有"速度"和"可靠性"。文章的每个步骤都有完整代码，可以直接照着做。

![分布式缓存架构示意：内存层 + PostgreSQL 分布式层](../../assets/762/01-cover.png)

## 目标：做一个能照着跑的参考应用

按这篇文章构建完成后，你的应用会具备：

- 使用 .NET Generic Host，统一管理配置、DI、日志和后台服务
- 从 `appsettings.json` 加载缓存配置
- 用 `dotnet user-secrets` 安全存储数据库连接字符串
- 用结构化日志输出带时间戳的运行信息
- 模拟耗时的外部数据请求
- 用 Azure PostgreSQL 存储分布式缓存条目
- 用 `HybridCache` 把内存缓存和分布式缓存合并成一个接口
- 打印每次请求耗时，直观对比缓存命中前后的性能差异

整个示例在 Windows 和 Linux 上都能运行。

## 前置条件

- .NET 10 SDK
- 一个可连接的 Azure Database for PostgreSQL 实例（或本地 Postgres）
- 了解 .NET Generic Host 的基本概念

## 第一步：创建项目并启用 Host

```bash
mkdir dcache-demo
cd dcache-demo
dotnet new console
dotnet add package Microsoft.Extensions.Hosting
```

`Microsoft.Extensions.Hosting` 带来了完整的 DI、配置、日志和托管服务支持。安装后 `.csproj` 中会多出类似这样的依赖项：

```xml
<ItemGroup>
  <PackageReference Include="Microsoft.Extensions.Hosting" Version="10.0.5" />
</ItemGroup>
```

把 `Program.cs` 替换成 Host 架构的初始骨架：

```csharp
using Microsoft.Extensions.Hosting;

var builder = Host.CreateDefaultBuilder(args);

builder.ConfigureAppConfiguration((hostingContext, config) => {
    // 后续添加配置源
});

builder.ConfigureServices((hostingContext, services) => {
    // 后续注册服务
});

builder.ConfigureLogging(logging => {
    // 后续配置日志
});

var app = builder.Build();
await app.RunAsync();
```

`Host.CreateDefaultBuilder` 已经自动接入了标准配置源、DI 容器和默认日志设置。

## 第二步：配置结构化日志

添加命名空间：

```csharp
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.DependencyInjection;
```

把 `ConfigureLogging` 替换成带时间戳的简洁控制台日志：

```csharp
builder.ConfigureLogging(logging => {
    logging.ClearProviders();
    logging.SetMinimumLevel(LogLevel.Information);
    logging.AddSimpleConsole(options => {
        options.TimestampFormat = "[yyyy-MM-dd HH:mm:ss.ffffff] ";
        options.SingleLine = true;
    });
});
```

在 `RunAsync` 前写入启动日志：

```csharp
var app = builder.Build();
var logger = app.Services.GetRequiredService<ILogger<Program>>();
logger.LogInformation("Console logging is now enabled!");
await app.RunAsync();
```

运行后输出类似：

```
[2026-03-20 17:01:11.358539] info: Program[0] Console logging is now enabled!
[2026-03-20 17:01:11.377219] info: Microsoft.Hosting.Lifetime[0] Application started. Press Ctrl+C to shut down.
```

## 第三步：添加模拟耗时任务

接下来让 Host 做点有用的事情。在 `await app.RunAsync()` 之后，添加 `WeatherForecast` 数据模型和 `ConsoleService` 后台服务：

```csharp
public class WeatherForecast {
    public DateOnly Date { get; set; }
    public int TemperatureC { get; set; }
    public int TemperatureF => 32 + (int)(TemperatureC / 0.5556);
    public string? Summary { get; set; }
    public static readonly string[] Summaries = new[] {
        "Freezing", "Bracing", "Chilly", "Cool", "Mild",
        "Warm", "Balmy", "Hot", "Sweltering", "Scorching"
    };
}

public class ConsoleService : BackgroundService {
    private readonly ILogger<ConsoleService> _logger;

    public ConsoleService(ILogger<ConsoleService> logger) {
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken) {
        _logger.LogInformation("Console Service Started.");

        while (!stoppingToken.IsCancellationRequested) {
            var response = await GetDataFromTheSource(stoppingToken);
            _logger.LogInformation("Returned {Count} forecast item(s)", response.Count());
            await Task.Delay(500, stoppingToken);
        }
    }

    async Task<IEnumerable<WeatherForecast>> GetDataFromTheSource(CancellationToken cancellationToken) {
        await Task.Delay(2000, cancellationToken); // 模拟 2 秒的外部延迟
        _logger.LogInformation("Fetching Weather");

        return Enumerable.Range(1, 1).Select(index => new WeatherForecast {
            Date = DateOnly.FromDateTime(DateTime.Now.AddDays(index)),
            TemperatureC = Random.Shared.Next(-20, 55),
            Summary = WeatherForecast.Summaries[Random.Shared.Next(WeatherForecast.Summaries.Length)]
        }).ToArray();
    }
}
```

注册后台服务：

```csharp
builder.ConfigureServices((hostingContext, services) => {
    services.AddHostedService<ConsoleService>();
});
```

运行后能看到每次请求都要等待约 2 秒——这就是需要缓存解决的问题。

## 第四步：安装缓存包

```bash
dotnet add package Microsoft.Extensions.Caching.Postgres
dotnet add package Microsoft.Extensions.Caching.Hybrid
```

- `Microsoft.Extensions.Caching.Postgres`：把缓存条目持久化到 Postgres 数据库
- `Microsoft.Extensions.Caching.Hybrid`：把内存缓存和分布式缓存组合成一层

## 第五步：配置连接字符串和缓存参数

安全存储数据库连接字符串（不要提交到源码！）：

```bash
dotnet user-secrets init
dotnet user-secrets set "ConnectionStrings:PostgresCache" \
  "Host=your-server.postgres.database.azure.com;Port=5432;Username=your-user;Password=your-password;Database=your-database;Pooling=true;MinPoolSize=0;MaxPoolSize=100;Timeout=15;"
```

创建 `appsettings.json`，设置缓存行为参数：

```json
{
  "PostgresCache": {
    "SchemaName": "public",
    "TableName": "cache",
    "CreateIfNotExists": true,
    "UseWAL": false,
    "ExpiredItemsDeletionInterval": "00:30:00",
    "DefaultSlidingExpiration": "00:20:00"
  }
}
```

在 `.csproj` 中确保该文件被复制到输出目录：

```xml
<ItemGroup>
  <None Update="appsettings.json">
    <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
    <CopyToPublishDirectory>PreserveNewest</CopyToPublishDirectory>
  </None>
</ItemGroup>
```

更新 `ConfigureAppConfiguration`，加载 User Secrets 和 JSON 配置：

```csharp
using Microsoft.Extensions.Configuration;

builder.ConfigureAppConfiguration((hostingContext, config) => {
    config.AddUserSecrets<Program>();
    config.AddJsonFile("appsettings.json", optional: false, reloadOnChange: true);

    if (hostingContext.HostingEnvironment.IsProduction()) {
        config.AddEnvironmentVariables();
    }
});
```

## 第六步：注册 Postgres 分布式缓存和 HybridCache

添加命名空间：

```csharp
using Microsoft.Extensions.Caching.Hybrid;
```

在 `ConfigureServices` 中注册分布式缓存和 HybridCache：

```csharp
builder.ConfigureServices((hostingContext, services) => {
    services.AddHostedService<ConsoleService>();

    services.AddDistributedPostgresCache(options => {
        options.ConnectionString = hostingContext.Configuration.GetConnectionString("PostgresCache");
        options.SchemaName = hostingContext.Configuration.GetValue<string>("PostgresCache:SchemaName", "public");
        options.TableName = hostingContext.Configuration.GetValue<string>("PostgresCache:TableName", "cache");
        options.CreateIfNotExists = hostingContext.Configuration.GetValue<bool>("PostgresCache:CreateIfNotExists", true);
        options.UseWAL = hostingContext.Configuration.GetValue<bool>("PostgresCache:UseWAL", false);

        var expirationInterval = hostingContext.Configuration.GetValue<string>("PostgresCache:ExpiredItemsDeletionInterval");
        if (!string.IsNullOrEmpty(expirationInterval) && TimeSpan.TryParse(expirationInterval, out var interval)) {
            options.ExpiredItemsDeletionInterval = interval;
        }

        var slidingExpiration = hostingContext.Configuration.GetValue<string>("PostgresCache:DefaultSlidingExpiration");
        if (!string.IsNullOrEmpty(slidingExpiration) && TimeSpan.TryParse(slidingExpiration, out var sliding)) {
            options.DefaultSlidingExpiration = sliding;
        }
    });

    services.AddHybridCache();
});
```

关键点在于 `services.AddHybridCache()` 这一行——它会自动把内存缓存和已注册的分布式缓存组合起来，两层缓存自动保持同步。

如果应用进程重启导致内存缓存丢失，Postgres 里的缓存条目依然有效，服务不会中断。

## 第七步：在服务中使用 HybridCache

更新 `ConsoleService`，注入 `HybridCache` 并设置分层过期策略：

```csharp
public class ConsoleService : BackgroundService {
    private readonly ILogger<ConsoleService> _logger;
    private readonly HybridCache _cache;

    // 内存层 3 秒过期，分布式层 6 秒过期
    private readonly HybridCacheEntryOptions _entryOptions = new HybridCacheEntryOptions {
        LocalCacheExpiration = TimeSpan.FromSeconds(3),
        Expiration = TimeSpan.FromSeconds(6),
    };

    public ConsoleService(ILogger<ConsoleService> logger, HybridCache cache) {
        _logger = logger;
        _cache = cache;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken) {
        _logger.LogInformation("Console Service Started.");

        while (!stoppingToken.IsCancellationRequested) {
            var timer = System.Diagnostics.Stopwatch.StartNew();

            var response = await _cache.GetOrCreateAsync(
                "weather:forecast:next-day",
                async cancel => {
                    _logger.LogInformation("Cache miss for weather request. Fetching from source.");
                    var result = await GetDataFromTheSource(cancel);
                    return result;
                },
                cancellationToken: stoppingToken,
                options: _entryOptions
            );

            timer.Stop();

            _logger.LogInformation("Returned {Count} forecast item(s) from HybridCache in {ElapsedMs} ms",
                response.Count(),
                timer.Elapsed.TotalMilliseconds
            );

            await Task.Delay(500, stoppingToken);
        }
    }

    // GetDataFromTheSource 不变
}
```

`GetOrCreateAsync` 的逻辑是：
1. 如果内存层有有效缓存 → 直接返回，亚毫秒级
2. 如果内存层过期，但 Postgres 层有效 → 从数据库取回，几十毫秒级
3. 两层都过期 → 调用真实数据源，将结果写入两层缓存

## 性能对比

加入 HybridCache 后，日志输出清晰反映了三种命中场景的耗时差距：

```
[17:22:46.408653] info: ConsoleService[0] Returned 1 forecast item(s) from HybridCache in 2061.0478 ms  ← 首次从源获取
[17:22:46.911366] info: ConsoleService[0] Returned 1 forecast item(s) from HybridCache in 0.6072 ms    ← 内存命中
[17:22:47.415489] info: ConsoleService[0] Returned 1 forecast item(s) from HybridCache in 0.3266 ms    ← 内存命中
[17:22:49.446790] info: ConsoleService[0] Returned 1 forecast item(s) from HybridCache in 38.9606 ms   ← Postgres 命中
[17:22:49.958174] info: ConsoleService[0] Returned 1 forecast item(s) from HybridCache in 0.2307 ms    ← 内存命中
[17:22:50.463451] info: ConsoleService[0] Cache miss for weather request. Fetching from source.         ← 两层都过期
```

- 内存命中：< 1 ms
- Postgres 分布式命中：~39 ms
- 无缓存/源请求：~2000 ms

## 适用边界和延伸

这套方案在以下场景效果尤为明显：
- 应用已在使用 Postgres，不想再单独维护 Redis
- 多实例部署，需要跨节点共享缓存状态
- 对进程重启后的缓存连续性有要求

如果需要更多示例，包括 Entra 认证方式注册缓存、复用现有数据源对象等进阶用法，可以参考官方 GitHub 仓库：[Azure/Microsoft.Extensions.Caching.Postgres](https://github.com/Azure/Microsoft.Extensions.Caching.Postgres)

## 参考

- [High-Performance Distributed Caching with .NET and Postgres on Azure](https://devblogs.microsoft.com/dotnet/high-performance-distributed-caching-dotnet-postgres-azure)
- [Azure/Microsoft.Extensions.Caching.Postgres on GitHub](https://github.com/Azure/Microsoft.Extensions.Caching.Postgres)
- [Hello HybridCache! - .NET Blog](https://devblogs.microsoft.com/dotnet/hybrid-cache-is-now-ga/)
- [Postgres as a Distributed Cache Unlocks Speed and Simplicity](https://aka.ms/dist-pg-cache)
- [Safe storage of app secrets in ASP.NET Core](https://learn.microsoft.com/aspnet/core/security/app-secrets)
