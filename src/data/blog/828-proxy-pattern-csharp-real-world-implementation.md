---
pubDatetime: 2026-05-25T11:40:00+08:00
title: "C# 代理模式实战：用组合叠加缓存、限流和日志"
description: "当一个 HTTP 客户端同时要处理缓存、限流、日志，单类实现很快变成难以维护的混乱代码。代理模式让每个横切关注点拥有独立的类，它们共同实现同一接口，通过依赖注入组合成调用链。本文以天气 API 客户端为例，完整演示缓存代理、限流代理、日志代理和熔断器代理的 C# 实现与组合方式。"
tags: ["C#", "Design Patterns", "Dependency Injection", ".NET"]
slug: "proxy-pattern-csharp-real-world-implementation"
ogImage: "../../assets/828/01-cover.png"
source: "https://www.devleader.ca/2026/05/23/proxy-pattern-realworld-example-in-c-complete-implementation"
---

代理模式的教科书示例通常是懒加载图片或权限检查。这类示例够简单，但放到生产代码里很快就会遇到一个现实问题：你需要同时处理缓存、限流和日志，还得保持代码干净。这篇文章用一个天气 API 客户端，完整展示如何用 C# 实现代理模式，把每个横切关注点分离成独立的类，再通过依赖注入组合成调用链。

## 混乱单类的问题在哪里

假设你在调用一个第三方天气 API。起初只有 HTTP 请求，代码很干净。慢慢地，需求追加：加缓存避免重复请求，加限流遵守 API 配额，加结构化日志排查性能问题。最自然的做法是往同一个类里塞，最终变成这样：

```csharp
public sealed class WeatherService
{
    private readonly HttpClient _httpClient;
    private readonly IMemoryCache _cache;
    private readonly ILogger<WeatherService> _logger;
    private readonly SemaphoreSlim _rateLimiter;

    public async Task<WeatherForecast> GetForecastAsync(string city)
    {
        var cacheKey = $"forecast_{city}";
        if (_cache.TryGetValue(cacheKey, out WeatherForecast? cached))
        {
            _logger.LogInformation("Cache hit for {City}", city);
            return cached!;
        }

        await _rateLimiter.WaitAsync();
        try
        {
            _logger.LogInformation("Fetching forecast for {City}", city);
            var stopwatch = Stopwatch.StartNew();

            var response = await _httpClient
                .GetFromJsonAsync<WeatherForecast>($"/api/forecast/{city}");

            stopwatch.Stop();
            _logger.LogInformation(
                "Forecast retrieved in {Elapsed}ms",
                stopwatch.ElapsedMilliseconds);

            _cache.Set(cacheKey, response, TimeSpan.FromMinutes(10));
            return response!;
        }
        finally
        {
            _rateLimiter.Release();
        }
    }
}
```

看起来能用，但每个关注点都相互缠绕。测试缓存逻辑时必须同时处理限流器和日志器。调整限流策略就要进入同一个类修改。再加一个熔断器，这个类会继续朝四个方向生长。

代理模式解决这个问题的方式很直接：每个关注点实现同一个接口，包住下一层，链式传递。

## 定义接口和数据类型

整个代理链共用一个接口。调用方只依赖这个接口，不知道背后有多少层代理：

```csharp
public sealed record WeatherForecast(
    string City,
    double TemperatureCelsius,
    string Summary,
    DateTimeOffset RetrievedAt);

public sealed record HistoricalWeatherData(
    string City,
    DateTimeOffset Date,
    double HighCelsius,
    double LowCelsius,
    string Conditions);

public interface IWeatherService
{
    Task<WeatherForecast> GetForecastAsync(string city);

    Task<IReadOnlyList<HistoricalWeatherData>> GetHistoricalDataAsync(
        string city,
        DateTimeOffset from,
        DateTimeOffset to);
}
```

两个方法、两种数据类型，接口足够小。`WeatherForecast` 和 `HistoricalWeatherData` 是不可变的记录类型，只携带必要数据。接口是调用方唯一知道的东西，不论背后是真实 HTTP 客户端还是四层代理。这正是依赖倒置原则的用意：依赖抽象而非具体实现。

## 真实服务只做一件事

链条最里层是 `HttpWeatherService`，它只负责 HTTP 通信：

```csharp
public sealed class HttpWeatherService : IWeatherService
{
    private readonly HttpClient _httpClient;

    public HttpWeatherService(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<WeatherForecast> GetForecastAsync(string city)
    {
        var response = await _httpClient
            .GetFromJsonAsync<WeatherApiResponse>($"/api/forecast/{city}");

        if (response is null)
        {
            throw new InvalidOperationException(
                $"No forecast data returned for {city}");
        }

        return new WeatherForecast(
            City: city,
            TemperatureCelsius: response.Temperature,
            Summary: response.Description,
            RetrievedAt: DateTimeOffset.UtcNow);
    }

    public async Task<IReadOnlyList<HistoricalWeatherData>> GetHistoricalDataAsync(
        string city, DateTimeOffset from, DateTimeOffset to)
    {
        var url = $"/api/history/{city}"
            + $"?from={from:yyyy-MM-dd}"
            + $"&to={to:yyyy-MM-dd}";

        var response = await _httpClient
            .GetFromJsonAsync<List<HistoricalApiResponse>>(url);

        if (response is null)
        {
            return Array.Empty<HistoricalWeatherData>();
        }

        return response
            .Select(r => new HistoricalWeatherData(
                City: city,
                Date: r.Date,
                HighCelsius: r.High,
                LowCelsius: r.Low,
                Conditions: r.Conditions))
            .ToList()
            .AsReadOnly();
    }
}

public sealed record WeatherApiResponse
{
    public double Temperature { get; init; }
    public string Description { get; init; } = "";
}

public sealed record HistoricalApiResponse
{
    public DateTimeOffset Date { get; init; }
    public double High { get; init; }
    public double Low { get; init; }
    public string Conditions { get; init; } = "";
}
```

没有缓存，没有限流，没有日志。DTO 记录类型（`WeatherApiResponse`、`HistoricalApiResponse`）只在这个类内部使用，负责接收 JSON 反序列化结果。代理模式的起点就是这样一个干净的单职责类。

## 缓存代理

`CachingWeatherProxy` 在转发请求前检查缓存，命中就直接返回，不命中才调用 `_inner`。TTL 通过构造函数注入，不同操作可以设置不同的缓存时长：

```csharp
public sealed class CachingWeatherProxy : IWeatherService
{
    private readonly IWeatherService _inner;
    private readonly IMemoryCache _cache;
    private readonly TimeSpan _forecastTtl;
    private readonly TimeSpan _historicalTtl;

    public CachingWeatherProxy(
        IWeatherService inner,
        IMemoryCache cache,
        TimeSpan forecastTtl,
        TimeSpan historicalTtl)
    {
        _inner = inner;
        _cache = cache;
        _forecastTtl = forecastTtl;
        _historicalTtl = historicalTtl;
    }

    public async Task<WeatherForecast> GetForecastAsync(string city)
    {
        var cacheKey = $"forecast:{city.ToLowerInvariant()}";

        if (_cache.TryGetValue(cacheKey, out WeatherForecast? cached))
        {
            return cached!;
        }

        var result = await _inner.GetForecastAsync(city);
        _cache.Set(cacheKey, result, _forecastTtl);
        return result;
    }

    public async Task<IReadOnlyList<HistoricalWeatherData>> GetHistoricalDataAsync(
        string city, DateTimeOffset from, DateTimeOffset to)
    {
        var cacheKey =
            $"history:{city.ToLowerInvariant()}"
            + $":{from:yyyyMMdd}:{to:yyyyMMdd}";

        if (_cache.TryGetValue(
                cacheKey,
                out IReadOnlyList<HistoricalWeatherData>? cached))
        {
            return cached!;
        }

        var result = await _inner.GetHistoricalDataAsync(city, from, to);
        _cache.Set(cacheKey, result, _historicalTtl);
        return result;
    }
}
```

缓存键使用规范化的城市名（`ToLowerInvariant()`）和日期范围，保证确定性。`_inner` 存放的是链条里下一层的 `IWeatherService`。缓存代理不知道也不关心 `_inner` 是 HTTP 服务还是另一个代理。

## 限流代理

`RateLimitingWeatherProxy` 用 `SemaphoreSlim` 做并发控制，配合令牌桶做每秒请求数限制：

```csharp
public sealed class RateLimitingWeatherProxy
    : IWeatherService, IDisposable
{
    private readonly IWeatherService _inner;
    private readonly SemaphoreSlim _concurrencyLimiter;
    private readonly SemaphoreSlim _tokenBucket;
    private readonly Timer _tokenRefillTimer;

    public RateLimitingWeatherProxy(
        IWeatherService inner,
        int maxConcurrentRequests,
        int maxRequestsPerSecond)
    {
        _inner = inner;
        _concurrencyLimiter = new SemaphoreSlim(
            maxConcurrentRequests, maxConcurrentRequests);
        _tokenBucket = new SemaphoreSlim(
            maxRequestsPerSecond, maxRequestsPerSecond);

        _tokenRefillTimer = new Timer(
            _ => RefillTokens(maxRequestsPerSecond),
            null,
            TimeSpan.FromSeconds(1),
            TimeSpan.FromSeconds(1));
    }

    public async Task<WeatherForecast> GetForecastAsync(string city)
    {
        await AcquirePermissionAsync();
        try
        {
            return await _inner.GetForecastAsync(city);
        }
        finally
        {
            _concurrencyLimiter.Release();
        }
    }

    public async Task<IReadOnlyList<HistoricalWeatherData>> GetHistoricalDataAsync(
        string city, DateTimeOffset from, DateTimeOffset to)
    {
        await AcquirePermissionAsync();
        try
        {
            return await _inner.GetHistoricalDataAsync(city, from, to);
        }
        finally
        {
            _concurrencyLimiter.Release();
        }
    }

    private async Task AcquirePermissionAsync()
    {
        await _tokenBucket.WaitAsync();
        await _concurrencyLimiter.WaitAsync();
    }

    private void RefillTokens(int maxTokens)
    {
        var tokensToAdd = maxTokens - _tokenBucket.CurrentCount;
        for (var i = 0; i < tokensToAdd; i++)
        {
            try
            {
                _tokenBucket.Release();
            }
            catch (SemaphoreFullException)
            {
                break;
            }
        }
    }

    public void Dispose()
    {
        _tokenRefillTimer.Dispose();
        _concurrencyLimiter.Dispose();
        _tokenBucket.Dispose();
    }
}
```

令牌桶每秒补满。有令牌才能进入并发控制，并发控制限制同时执行的请求数。`AcquirePermissionAsync` 把两个检查封装在一起。请求完成后在 `finally` 块里释放并发槽位。因为持有 `Timer`，这个代理实现了 `IDisposable`。

## 日志代理

`LoggingWeatherProxy` 给每次调用加上计时和结构化日志：

```csharp
public sealed class LoggingWeatherProxy : IWeatherService
{
    private readonly IWeatherService _inner;
    private readonly ILogger<LoggingWeatherProxy> _logger;

    public LoggingWeatherProxy(
        IWeatherService inner,
        ILogger<LoggingWeatherProxy> logger)
    {
        _inner = inner;
        _logger = logger;
    }

    public async Task<WeatherForecast> GetForecastAsync(string city)
    {
        _logger.LogInformation("Requesting forecast for {City}", city);
        var stopwatch = Stopwatch.StartNew();

        try
        {
            var result = await _inner.GetForecastAsync(city);
            stopwatch.Stop();
            _logger.LogInformation(
                "Forecast for {City} retrieved in {ElapsedMs}ms",
                city, stopwatch.ElapsedMilliseconds);
            return result;
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(
                ex,
                "Forecast request for {City} failed after {ElapsedMs}ms",
                city, stopwatch.ElapsedMilliseconds);
            throw;
        }
    }

    public async Task<IReadOnlyList<HistoricalWeatherData>> GetHistoricalDataAsync(
        string city, DateTimeOffset from, DateTimeOffset to)
    {
        _logger.LogInformation(
            "Requesting historical data for {City} from {From} to {To}",
            city, from, to);
        var stopwatch = Stopwatch.StartNew();

        try
        {
            var result = await _inner.GetHistoricalDataAsync(city, from, to);
            stopwatch.Stop();
            _logger.LogInformation(
                "Historical data for {City} retrieved ({Count} records) in {ElapsedMs}ms",
                city, result.Count, stopwatch.ElapsedMilliseconds);
            return result;
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(
                ex,
                "Historical data request for {City} failed after {ElapsedMs}ms",
                city, stopwatch.ElapsedMilliseconds);
            throw;
        }
    }
}
```

使用结构化日志的命名占位符（`{City}`、`{ElapsedMs}`），而不是字符串插值。这样日志聚合工具可以按城市名、耗时等字段检索。异常会被记录但不会被吞掉，日志代理不改变错误语义，只是在传播前留下记录。

## DI 注册：由内向外组装链条

这是这个模式最关键的地方。代理链从内到外构建，最外层是调用方拿到的那个实例：

```csharp
using System.Diagnostics;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddMemoryCache();

builder.Services.AddHttpClient<HttpWeatherService>(client =>
{
    client.BaseAddress = new Uri("https://api.weather-provider.example");
    client.Timeout = TimeSpan.FromSeconds(10);
});

builder.Services.AddSingleton<IWeatherService>(sp =>
{
    var httpService = sp.GetRequiredService<HttpWeatherService>();
    var logger = sp.GetRequiredService<ILogger<LoggingWeatherProxy>>();
    var cache = sp.GetRequiredService<IMemoryCache>();

    IWeatherService chain = httpService;

    chain = new LoggingWeatherProxy(chain, logger);

    chain = new RateLimitingWeatherProxy(
        chain,
        maxConcurrentRequests: 5,
        maxRequestsPerSecond: 10);

    chain = new CachingWeatherProxy(
        chain,
        cache,
        forecastTtl: TimeSpan.FromMinutes(10),
        historicalTtl: TimeSpan.FromHours(1));

    return chain;
});

var app = builder.Build();

app.MapGet("/forecast/{city}", async (
    string city,
    IWeatherService weatherService) =>
{
    var forecast = await weatherService.GetForecastAsync(city);
    return Results.Ok(forecast);
});

app.MapGet("/history/{city}", async (
    string city,
    DateTimeOffset from,
    DateTimeOffset to,
    IWeatherService weatherService) =>
{
    var data = await weatherService.GetHistoricalDataAsync(city, from, to);
    return Results.Ok(data);
});

app.Run();
```

调用链的顺序是有意义的：

- `HttpWeatherService`：最内层，实际发出 HTTP 请求
- `LoggingWeatherProxy`：包住 HTTP 服务，记录每次真实调用的耗时
- `RateLimitingWeatherProxy`：包住日志层，在请求到达日志层之前做节流
- `CachingWeatherProxy`：最外层，缓存命中就直接返回，整条链都不会被触发

当 API 端点解析 `IWeatherService` 时，拿到的是缓存代理。缓存代理委托给限流代理，限流代理委托给日志代理，日志代理委托给 HTTP 服务。每一层只做自己的事，不知道也不需要知道链条里其他层的存在。

## 添加新代理不需要改任何现有代码

假设需要一个熔断器：连续失败超过阈值后，暂时停止转发请求。只需要写一个新类：

```csharp
public sealed class CircuitBreakerWeatherProxy : IWeatherService
{
    private readonly IWeatherService _inner;
    private readonly int _failureThreshold;
    private readonly TimeSpan _openDuration;
    private int _consecutiveFailures;
    private DateTimeOffset _circuitOpenedAt;
    private bool _isOpen;
    private readonly object _lock = new();

    public CircuitBreakerWeatherProxy(
        IWeatherService inner,
        int failureThreshold,
        TimeSpan openDuration)
    {
        _inner = inner;
        _failureThreshold = failureThreshold;
        _openDuration = openDuration;
    }

    public async Task<WeatherForecast> GetForecastAsync(string city)
    {
        EnsureCircuitAllowsRequest();
        try
        {
            var result = await _inner.GetForecastAsync(city);
            RecordSuccess();
            return result;
        }
        catch
        {
            RecordFailure();
            throw;
        }
    }

    public async Task<IReadOnlyList<HistoricalWeatherData>> GetHistoricalDataAsync(
        string city, DateTimeOffset from, DateTimeOffset to)
    {
        EnsureCircuitAllowsRequest();
        try
        {
            var result = await _inner.GetHistoricalDataAsync(city, from, to);
            RecordSuccess();
            return result;
        }
        catch
        {
            RecordFailure();
            throw;
        }
    }

    private void EnsureCircuitAllowsRequest()
    {
        lock (_lock)
        {
            if (!_isOpen) return;

            if (DateTimeOffset.UtcNow - _circuitOpenedAt >= _openDuration)
            {
                _isOpen = false;
                _consecutiveFailures = 0;
                return;
            }

            throw new InvalidOperationException(
                "Circuit breaker is open. Requests are temporarily blocked.");
        }
    }

    private void RecordSuccess()
    {
        lock (_lock) { _consecutiveFailures = 0; }
    }

    private void RecordFailure()
    {
        lock (_lock)
        {
            _consecutiveFailures++;
            if (_consecutiveFailures >= _failureThreshold)
            {
                _isOpen = true;
                _circuitOpenedAt = DateTimeOffset.UtcNow;
            }
        }
    }
}
```

然后把它插入 DI 注册里，放在日志层和限流层之间：

```csharp
chain = new LoggingWeatherProxy(chain, logger);

chain = new CircuitBreakerWeatherProxy(
    chain,
    failureThreshold: 3,
    openDuration: TimeSpan.FromSeconds(30));

chain = new RateLimitingWeatherProxy(
    chain,
    maxConcurrentRequests: 5,
    maxRequestsPerSecond: 10);

chain = new CachingWeatherProxy(
    chain, cache,
    forecastTtl: TimeSpan.FromMinutes(10),
    historicalTtl: TimeSpan.FromHours(1));
```

`IWeatherService` 接口没变，`HttpWeatherService` 没变，三个已有的代理没变。这是开闭原则的直接体现：对扩展开放，对修改关闭。

## 缓存兜底降级

缓存代理还可以做一件有用的事：当内层服务抛出异常时，返回过期的缓存数据而不是直接报错：

```csharp
public async Task<WeatherForecast> GetForecastAsync(string city)
{
    var cacheKey = $"forecast:{city.ToLowerInvariant()}";

    try
    {
        if (_cache.TryGetValue(cacheKey, out WeatherForecast? cached))
        {
            return cached!;
        }

        var result = await _inner.GetForecastAsync(city);
        _cache.Set(cacheKey, result, _forecastTtl);
        return result;
    }
    catch (Exception) when (
        _cache.TryGetValue(cacheKey, out WeatherForecast? stale))
    {
        return stale!;
    }
}
```

`when` 过滤器只在确实存在过期数据时才拦截异常。没有过期数据，异常正常向上传播。这给调用方提供了优雅降级：天气 API 暂时不可用时，返回几分钟前的数据，而不是直接显示错误页面。

## 几个常见问题

**代理模式和装饰器模式的区别**：两者的结构几乎相同，都是包装实现同一接口的对象。区别在于意图：代理模式控制对真实主体的访问（缓存、限流、延迟加载、访问控制），装饰器模式增加新行为。实际上区别很模糊，这篇文章里的缓存代理叫装饰器也完全说得通。与其纠结名称，不如关注你要解决的问题。

**代理链的顺序怎么决定**：让短路最频繁的代理放最外层。缓存命中率高，放外层可以跳过整条链。限流放在缓存内层，这样缓存命中时不会占用限流名额。日志放在最靠近真实服务的位置，记录的是真实 HTTP 调用的耗时，而不是包括缓存检查在内的总耗时。

**怎么测试单个代理**：每个代理都只依赖 `IWeatherService` 和自身特定的依赖项，所以很容易隔离测试。给缓存代理传入一个 mock 的 `_inner`，验证第二次调用不触发 `_inner`。给限流代理验证超过令牌桶上限时请求被阻塞。每个代理的行为可以完全独立验证。

**会影响性能吗**：每层代理增加一次方法调用，开销相对于 HTTP 调用本身可以忽略不计。缓存代理实际上大幅提升了性能，因为它消除了网络往返。限流代理引入的延迟是保护下游服务的主动设计，不是性能损耗。

## 结语

这个天气 API 的例子展示了代理模式解决的真实工程问题：把缓存、限流、日志和熔断器叠加到一个 HTTP 客户端上，同时保持每个类的职责单一、可测试、可替换。

做法的核心就是：每个横切关注点一个类，每个类实现同一接口，DI 把它们组合起来。需要新增关注点时，写一个新类，修改一行 DI 注册，其他代码不动。

这个结构可以直接迁移到你的实际项目。把 `IWeatherService` 换成你的 API 客户端接口，调整每层代理的参数，组合出你需要的链条。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会持续分享能落地的工具教程、C# 设计模式实践和项目经验。

## 参考

- [Proxy Pattern Real-World Example in C#: Complete Implementation](https://www.devleader.ca/2026/05/23/proxy-pattern-realworld-example-in-c-complete-implementation)
- [Decorator Design Pattern in C#: Complete Guide with Examples](https://www.devleader.ca/2026/03/14/decorator-design-pattern-in-c-complete-guide-with-examples)
- [IServiceCollection in C# Simplified: Beginner's Guide for Dependency Injection](https://www.devleader.ca/2024/02/21/iservicecollection-in-c-simplified-beginners-guide-for-dependency-injection)
