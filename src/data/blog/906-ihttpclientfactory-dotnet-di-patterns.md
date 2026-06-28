---
pubDatetime: 2026-06-29T07:07:40+08:00
title: "IHttpClientFactory 在 .NET 中的使用：命名客户端、类型化客户端与依赖注入模式"
description: "了解 IHttpClientFactory 如何解决 HttpClient 的 socket 耗尽和 DNS 过期两个生产环境问题。本文覆盖基础工厂、命名客户端、类型化客户端三种模式，以及 DelegatingHandler 管道和注册陷阱，帮你在实际项目中选对方法。"
tags: ["CSharp", ".NET", "HttpClient", "Dependency Injection"]
slug: "ihttpclientfactory-dotnet-di-patterns"
ogImage: "../../assets/906/01-cover.png"
source: "https://www.devleader.ca/2026/06/27/ihttpclientfactory-in-net-named-clients-typed-clients-and-di-patterns"
---

如果你写过调用外部 API 的 .NET 代码，就一定用过 `HttpClient`。如果你还在用 `new HttpClient()` 做这件事——尤其是放到 `using` 里用完就扔——在高负载下迟早会撞上 socket 耗尽。换成一个 static 单例倒是能避免耗尽，但又会埋下 DNS 不更新的坑。

`IHttpClientFactory` 就是为解决这两个问题设计的。这篇文章从它的内部机制开始，逐步覆盖基础工厂、命名客户端、类型化客户端三种使用方式，以及 DelegatingHandler 管道和常见的单例陷阱。

本文是 [HttpClient in C#: The Complete Guide](https://www.devleader.ca/2026/06/26/httpclient-in-c-the-complete-guide-for-net-developers) 系列的一部分。

## 为什么不能用 new HttpClient()

看起来最直观的写法是创建、使用、销毁：

```csharp
// 这种写法看起来没问题，但在生产环境会导致 socket 耗尽
public class ProductService
{
    public async Task<Product?> GetProductAsync(int id)
    {
        // 每次请求新建一个 HttpClient —— 这是错的
        using var client = new HttpClient();
        client.BaseAddress = new Uri("https://api.example.com/");

        return await client.GetFromJsonAsync<Product>($"products/{id}");
    }
}
```

问题是 `Dispose()` 并不会立刻释放底层 TCP socket。socket 会进入 `TIME_WAIT` 状态，在操作系统层面最长停留 4 分钟。只要每秒几十个请求，可用 socket 就会被耗尽，然后你就能看到 `SocketException: Only one usage of each socket address is normally permitted`。

直觉上你会改成静态单例：

```csharp
// 解决了 socket 耗尽，但引入了另一个 bug
public class ProductService
{
    // 全局共享一个实例
    private static readonly HttpClient _client = new()
    {
        BaseAddress = new Uri("https://api.example.com/")
    };

    public async Task<Product?> GetProductAsync(int id)
    {
        return await _client.GetFromJsonAsync<Product>($"products/{id}");
    }
}
```

socket 不会耗尽了，但 DNS 变更永远不会被感知。在云环境和微服务架构里，主机名解析到的 IP 是频繁变动的。单例 `HttpClient` 在启动时缓存了 DNS 结果，之后就一直用这个 IP，直到进程重启。

你夹在两种坏方案之间。这就是 `IHttpClientFactory` 要填的坑。

## IHttpClientFactory 的内部机制

`IHttpClientFactory` 的解法是把 `HttpClient` 本来绑在一起的两个生命周期拆开：客户端对象本身，和真正管理 socket 池的底层 `HttpMessageHandler`。

当你从工厂获取一个客户端时，后台发生的事情是这样的：

- **每次调用都创建一个新的 `HttpClient` 包装对象**——没有共享状态，不会累积配置漂移
- **`HttpMessageHandler` 被池化复用**，同一个逻辑名称的客户端共享同一个 handler
- **每个池化 handler 有可配置的过期时间**（默认 2 分钟）
- **过期后 handler 被标记驱逐**，但在途请求会自然完成，不会中断
- **替换 handler 新创建时触发一次新的 DNS 解析**

可以把它理解成租车：每次拿到的是干净的车，没有上一位留下的东西；但底层车队是共享和维护的，不需要每次从炼钢开始造一辆新车。"换油"按时间表执行，不管上一个司机是谁。

这套设计让你同时拿到干净 `HttpClient` 实例（没有请求间共享可变状态）、高效的 handler 复用（不会耗尽 socket）、以及 handler 轮换周期内的自动 DNS 刷新。

## 用 AddHttpClient() 注册工厂

在 .NET 中使用 `AddHttpClient()` 一个调用就能注册完成：

```csharp
// Program.cs
var builder = WebApplication.CreateBuilder(args);

// 注册 IHttpClientFactory 以及所有支撑设施
builder.Services.AddHttpClient();

var app = builder.Build();
app.Run();
```

`AddHttpClient()` 把 `IHttpClientFactory` 注册为单例，同时配置好 handler 池、默认的 handler 轮换策略和支撑的 `IHttpMessageHandlerFactory`。后续一切的命名客户端、类型化客户端、DelegatingHandler 都建立在它之上。

`IHttpClientFactory` 从 .NET Core 2.1 开始就可以用了，本文的模式在所有现代 .NET 版本上都有效，示例代码用 .NET 10 的语法。

## 模式一：基础工厂

最简单的用法是直接注入 `IHttpClientFactory`，在调用处用 `CreateClient()` 获取客户端。没有命名配置，没有包装类：

```csharp
public class WeatherService
{
    private readonly IHttpClientFactory _httpClientFactory;

    public WeatherService(IHttpClientFactory httpClientFactory)
    {
        _httpClientFactory = httpClientFactory;
    }

    public async Task<WeatherForecast?> GetForecastAsync(
        string city, CancellationToken ct = default)
    {
        // 每次拿到新客户端 —— handler 在底层被池化复用
        var client = _httpClientFactory.CreateClient();
        client.BaseAddress = new Uri("https://api.weather.example.com/");

        return await client.GetFromJsonAsync<WeatherForecast>(
            $"forecast/{city}", ct);
    }
}
```

当你只有一个简单的、临时性的调用，还不确定客户端配置会不会在其他地方复用时，这是正确的起点。你仍然拿到了 `IHttpClientFactory` 的全部好处——handler 池化、DNS 刷新——没有命名或类型化客户端的额外开销。

局限也很明显：配置散落在各个调用点。如果 BaseAddress 变了，你得去每个 `CreateClient()` 的地方改。这是命名客户端存在的理由。

## 模式二：命名客户端

命名客户端让你在启动时按名称注册并配置一个 `HttpClient`，之后在代码任意位置通过名称获取。配置集中在同一个地方，调用点保持整洁：

```csharp
// Program.cs —— 只定义一次 "weather" 客户端
builder.Services.AddHttpClient("weather", client =>
{
    client.BaseAddress = new Uri("https://api.weather.example.com/");
    client.DefaultRequestHeaders.Add("Accept", "application/json");
    client.DefaultRequestHeaders.Add("User-Agent", "MyApp/1.0");
    client.Timeout = TimeSpan.FromSeconds(30);
});
```

需要调用天气 API 的服务只要按名称获取：

```csharp
public class WeatherService
{
    private readonly IHttpClientFactory _httpClientFactory;

    public WeatherService(IHttpClientFactory httpClientFactory)
    {
        _httpClientFactory = httpClientFactory;
    }

    public async Task<WeatherForecast?> GetForecastAsync(
        string city, CancellationToken ct = default)
    {
        // 拿到预配置好的客户端 —— 不需要本地再做设置
        var client = _httpClientFactory.CreateClient("weather");

        return await client.GetFromJsonAsync<WeatherForecast>(
            $"forecast/{city}", ct);
    }
}
```

多个服务消费同一个预配置端点时，或者你想把客户端配置和业务逻辑分离时，命名客户端是不错的选择。从静态 `HttpClient` 字段迁移重构时也很自然——把现有配置集中为一个命名客户端，调用点改动量很小。

字符串键是主要的缺点。`"weather"` 是个魔法字符串，写错了不会报编译错误，只是默默返回一个未配置的 `HttpClient`。对稍微复杂的场景，类型化客户端消除了这个风险。

## 模式三：类型化客户端

类型化客户端是 .NET 中对外部服务集成的推荐模式。不再注入 `IHttpClientFactory` 然后用字符串取客户端，而是封装一个专门的服务类，只暴露应用需要的操作。

以 GitHub API 为例：

```csharp
// 你的服务依赖的接口 —— 不直接依赖 HttpClient
public interface IGitHubClient
{
    Task<GitHubUser?> GetUserAsync(
        string username, CancellationToken ct = default);
    Task<IReadOnlyList<GitHubRepo>> GetUserReposAsync(
        string username, CancellationToken ct = default);
}

// 类型化客户端 —— HttpClient 由工厂注入，不需要你手动管理
public sealed class GitHubClient : IGitHubClient
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
    };

    private readonly HttpClient _httpClient;

    public GitHubClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<GitHubUser?> GetUserAsync(
        string username, CancellationToken ct = default)
    {
        return await _httpClient.GetFromJsonAsync<GitHubUser>(
            $"users/{username}", JsonOptions, ct);
    }

    public async Task<IReadOnlyList<GitHubRepo>> GetUserReposAsync(
        string username, CancellationToken ct = default)
    {
        var repos = await _httpClient.GetFromJsonAsync<List<GitHubRepo>>(
            $"users/{username}/repos?per_page=100", JsonOptions, ct);

        return repos ?? [];
    }
}
```

在 `Program.cs` 中注册：

```csharp
builder.Services.AddHttpClient<IGitHubClient, GitHubClient>(client =>
{
    client.BaseAddress = new Uri("https://api.github.com/");
    client.DefaultRequestHeaders.Add("Accept", "application/vnd.github+json");
    client.DefaultRequestHeaders.Add("User-Agent", "MyApp/1.0");
    client.DefaultRequestHeaders.Add("X-GitHub-Api-Version", "2022-11-28");
    client.Timeout = TimeSpan.FromSeconds(30);
});
```

现在任何需要 GitHub 访问的服务只依赖 `IGitHubClient`——不依赖 `HttpClient`，不依赖 `IHttpClientFactory`，也没有字符串键：

```csharp
public class UserProfileService
{
    private readonly IGitHubClient _gitHubClient;

    public UserProfileService(IGitHubClient gitHubClient)
    {
        _gitHubClient = gitHubClient;
    }

    public async Task<UserProfile> BuildProfileAsync(
        string username, CancellationToken ct)
    {
        var user = await _gitHubClient.GetUserAsync(username, ct);
        var repos = await _gitHubClient.GetUserReposAsync(username, ct);

        return new UserProfile(user, repos);
    }
}
```

这直接跟[依赖倒置原则](https://www.devleader.ca/2026/06/15/dependency-inversion-principle-c-abstractions-over-concretions)对齐——高层模块依赖抽象，不依赖具体的 HTTP 基础设施。测试 `UserProfileService` 只需要 mock `IGitHubClient`，不需要 mock `HttpClient` 或 `IHttpClientFactory`。

## 类型化客户端的单例陷阱

这是开发者最容易踩的坑：**类型化客户端不能注册为单例，也不能被单例服务捕获**。

调用 `AddHttpClient<IGitHubClient, GitHubClient>()` 时，类型化客户端默认注册为 **transient**。每次注入都会创建一个新的 `GitHubClient` 实例，连带一个由工厂管理的新 `HttpClient`。这是有意为之的——确保 handler 池被正确使用，没有单独的客户端实例在请求间累积状态。

如果你覆盖了这个行为，把类型化客户端注册为单例：

```csharp
// ⚠️ 错了 —— 这会破坏 IHttpClientFactory 的生命周期管理
builder.Services.AddSingleton<IGitHubClient, GitHubClient>();
// 这个单例里的 HttpClient 永远不会被回收
```

你重新引入了 DNS 过期问题。这个单例在启动时捕获了一个 `HttpClient`，而这个 `HttpClient` 持有一个永远不会被轮换出池的 `HttpMessageHandler`——因为 `IHttpClientFactory` 无法伸进一个单例里去替换它。

单例服务注入 transient 类型化客户端也会出现同样的问题。DI 容器在某些配置下会警告"captive dependency"，但真正的伤害是悄无声息的连接过期。

如果单例确实需要发 HTTP 请求，正确的做法是注入 `IHttpClientFactory` 本身，在每次使用时创建客户端：

```csharp
// ✅ 正确 —— 注入工厂而不是类型化客户端
public sealed class BackgroundSyncService
{
    private readonly IHttpClientFactory _httpClientFactory;

    public BackgroundSyncService(IHttpClientFactory httpClientFactory)
    {
        _httpClientFactory = httpClientFactory;
    }

    public async Task SyncAsync(CancellationToken ct)
    {
        // 每次同步获取新客户端 —— handler 仍然被高效池化
        var client = _httpClientFactory.CreateClient("sync-api");
        var result = await client.GetFromJsonAsync<SyncResponse>(
            "sync/latest", ct);
        // 处理结果...
    }
}
```

`IHttpClientFactory` 本身是单例，所以注入到单例是安全的。它创建的客户端仍然受 handler 池管理。你拿到了高效的连接复用，没有违反任何生命周期约束。

## 同一接口的多命名客户端

如果需要同一个类型化客户端的两种变体——比如同一个 API 的认证版和匿名版——正确的做法是注册命名客户端，然后在包装类构造函数里通过 `IHttpClientFactory.CreateClient(name)` 分别获取：

```csharp
// Program.cs —— 两个命名客户端注册
builder.Services.AddHttpClient("github-auth", client =>
{
    client.BaseAddress = new Uri("https://api.github.com/");
    client.DefaultRequestHeaders.Add("Accept", "application/vnd.github+json");
    client.DefaultRequestHeaders.Add("User-Agent", "MyApp/1.0");
    // Token 注入由 DelegatingHandler 处理
});

builder.Services.AddHttpClient("github-anon", client =>
{
    client.BaseAddress = new Uri("https://api.github.com/");
    client.DefaultRequestHeaders.Add("Accept", "application/vnd.github+json");
    client.DefaultRequestHeaders.Add("User-Agent", "MyApp/1.0");
});
```

在构造函数中通过工厂分别获取：

```csharp
// 必须注册为 scoped 或 transient —— 不能是 singleton
public sealed class GitHubOrchestrator
{
    private readonly IGitHubClient _authenticated;
    private readonly IGitHubClient _anonymous;

    public GitHubOrchestrator(IHttpClientFactory factory)
    {
        _authenticated = new GitHubClient(
            factory.CreateClient("github-auth"));
        _anonymous = new GitHubClient(
            factory.CreateClient("github-anon"));
    }
}
```

这比为区分注入点而单独创建 `IAuthenticatedGitHubClient` 和 `IAnonymousGitHubClient` 接口更干净。名字携带了区分信息，接口保持聚焦——跟[接口隔离原则](https://www.devleader.ca/2026/06/14/interface-segregation-principle-c-focused-interfaces-that-scale)的精神一致。

注意：`GitHubOrchestrator` 必须注册为 scoped 或 transient。如果注册为 singleton，构造函数里捕获的 `HttpClient` 永远不会被轮换，DNS 过期问题又回来了。

## BaseAddress、DefaultHeaders 和 Timeout 的配置细节

`AddHttpClient` 中的配置委托是你集中设置所有客户端属性的地方：

```csharp
builder.Services.AddHttpClient<IPaymentClient, PaymentClient>(client =>
{
    // 末尾斜杠至关重要 —— 影响相对路径的解析
    // "charges" 在有斜杠时解析为 https://api.payments.example.com/v2/charges
    // 没有末尾斜杠时 "v2" 会被丢掉，直接 404
    client.BaseAddress = new Uri("https://api.payments.example.com/v2/");

    // 每次请求都会带上的默认头
    client.DefaultRequestHeaders.Accept.Add(
        new MediaTypeWithQualityHeaderValue("application/json"));
    client.DefaultRequestHeaders.Add("User-Agent", "MyApp/1.0");
    client.DefaultRequestHeaders.Add("Idempotency-Key-Prefix", "myapp");

    // Timeout 覆盖整个请求生命周期：连接 + 发送 + 接收
    client.Timeout = TimeSpan.FromSeconds(45);
});
```

几点值得强调：

- `BaseAddress` 的末尾斜杠不是装饰。`new Uri("https://host/v2/")` 加上相对路径 `charges` 解析为 `https://host/v2/charges`。没有末尾斜杠时，Uri 解析会丢弃最后一段路径，你会悄悄请求到错误的端点。这是 404 的常见来源。
- `client.Timeout` 是整个请求的硬上限，不是分阶段超时。需要精细控制（分别设置连接超时、发送超时、接收超时）时，要直接配置底层的 `SocketsHttpHandler`，或者在调用处使用 `CancellationToken`。
- 不要把凭证和 token 放在配置委托里。token 会过期，把它们写进配置意味着你需要重新创建工厂（运行时做不到）。应该用 `DelegatingHandler`。

## 处理器管道：DelegatingHandler

`DelegatingHandler` 让 `IHttpClientFactory` 真正强大起来。你可以围绕特定客户端的每个 HTTP 调用组合一个可复用的关注点管道——完全不动业务逻辑。

一个结构化的日志处理器：

```csharp
public sealed class LoggingHandler : DelegatingHandler
{
    private readonly ILogger<LoggingHandler> _logger;

    public LoggingHandler(ILogger<LoggingHandler> logger)
    {
        _logger = logger;
    }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        _logger.LogInformation(
            "[HTTP OUT] {Method} {Uri}", request.Method, request.RequestUri);

        var stopwatch = Stopwatch.StartNew();

        var response = await base.SendAsync(request, cancellationToken);

        stopwatch.Stop();

        _logger.LogInformation(
            "[HTTP IN] {Status} in {ElapsedMs}ms",
            (int)response.StatusCode,
            stopwatch.ElapsedMilliseconds);

        return response;
    }
}
```

一个自动注入 Bearer token 的认证处理器，token 从 token provider 获取，在长期运行的应用中保持 token 新鲜：

```csharp
public sealed class BearerTokenHandler : DelegatingHandler
{
    private readonly ITokenProvider _tokenProvider;

    public BearerTokenHandler(ITokenProvider tokenProvider)
    {
        _tokenProvider = tokenProvider;
    }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        // 每次请求前获取新鲜（或缓存的）token
        var token = await _tokenProvider.GetTokenAsync(cancellationToken);
        request.Headers.Authorization =
            new AuthenticationHeaderValue("Bearer", token);

        return await base.SendAsync(request, cancellationToken);
    }
}
```

注册时先把 handler 注册为 transient，再链到客户端上：

```csharp
// 先注册 handler
builder.Services.AddTransient<LoggingHandler>();
builder.Services.AddTransient<BearerTokenHandler>();

// 链到类型化客户端 —— handler 按注册顺序执行
builder.Services.AddHttpClient<IGitHubClient, GitHubClient>(client =>
{
    client.BaseAddress = new Uri("https://api.github.com/");
    client.DefaultRequestHeaders.Add("User-Agent", "MyApp/1.0");
})
.AddHttpMessageHandler<LoggingHandler>()       // 最外层
.AddHttpMessageHandler<BearerTokenHandler>();  // 传输前的最内层
```

管道按注册顺序执行出站路径，按逆序执行入站路径。`LoggingHandler` 包在最外层——它在 token 添加之前看到请求、在 token 处理之后看到响应。`BearerTokenHandler` 更靠近网络层，看到最终请求，能在最后时刻注入认证头。

## 完整示例

下面是组装所有概念的 .NET 10 完整代码：

```csharp
// 模型
public sealed record GitHubUser(
    string Login, string? Name, int PublicRepos, int Followers);
public sealed record GitHubRepo(
    string Name, string? Description, bool Fork, int StargazersCount);

// 接口 —— 聚焦、遵循接口隔离原则
public interface IGitHubClient
{
    Task<GitHubUser?> GetUserAsync(
        string username, CancellationToken ct = default);
    Task<IReadOnlyList<GitHubRepo>> GetUserReposAsync(
        string username, CancellationToken ct = default);
}

// 类型化客户端
public sealed class GitHubClient : IGitHubClient
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
    };

    private readonly HttpClient _httpClient;

    public GitHubClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<GitHubUser?> GetUserAsync(
        string username, CancellationToken ct = default) =>
        await _httpClient.GetFromJsonAsync<GitHubUser>(
            $"users/{username}", JsonOptions, ct);

    public async Task<IReadOnlyList<GitHubRepo>> GetUserReposAsync(
        string username, CancellationToken ct = default)
    {
        var repos = await _httpClient.GetFromJsonAsync<List<GitHubRepo>>(
            $"users/{username}/repos?per_page=100&sort=stars",
            JsonOptions, ct);

        return repos ?? [];
    }
}

// 日志 handler（C# 12 主构造函数语法）
public sealed class LoggingHandler(ILogger<LoggingHandler> logger)
    : DelegatingHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, CancellationToken cancellationToken)
    {
        logger.LogInformation(
            "[HTTP] --> {Method} {Uri}", request.Method, request.RequestUri);
        var response = await base.SendAsync(request, cancellationToken);
        logger.LogInformation("[HTTP] <-- {Status}", response.StatusCode);
        return response;
    }
}

// Program.cs
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddTransient<LoggingHandler>();

builder.Services.AddHttpClient<IGitHubClient, GitHubClient>(client =>
{
    client.BaseAddress = new Uri("https://api.github.com/");
    client.DefaultRequestHeaders.Add("Accept", "application/vnd.github+json");
    client.DefaultRequestHeaders.Add("User-Agent", "MyApp/1.0");
    client.DefaultRequestHeaders.Add("X-GitHub-Api-Version", "2022-11-28");
    client.Timeout = TimeSpan.FromSeconds(30);
})
.AddHttpMessageHandler<LoggingHandler>();

builder.Services.AddControllers();

var app = builder.Build();
app.MapControllers();
app.Run();

// Controller —— 只依赖抽象
[ApiController]
[Route("api/github")]
public sealed class GitHubController(IGitHubClient gitHubClient)
    : ControllerBase
{
    [HttpGet("users/{username}")]
    public async Task<IActionResult> GetUser(
        string username, CancellationToken ct)
    {
        var user = await gitHubClient.GetUserAsync(username, ct);
        return user is null ? NotFound() : Ok(user);
    }

    [HttpGet("users/{username}/repos")]
    public async Task<IActionResult> GetRepos(
        string username, CancellationToken ct)
    {
        var repos = await gitHubClient.GetUserReposAsync(username, ct);
        return Ok(repos);
    }
}
```

Controller 完全不知道 `HttpClient`、BaseAddress、认证和日志的存在。它只依赖 `IGitHubClient`。所有的 HTTP 基础设施都在 `Program.cs` 和 handler 类里。

## 如何选择

三种模式有清楚的递进关系：

- **基础工厂**：临时调用、快速原型、还不确定配置会不会共享时用。既拿到所有好处也没有多余开销。
- **命名客户端**：多个地方消费同一个配置好的端点时用。最合适从静态 `HttpClient` 字段迁移的场景。
- **类型化客户端**：正式的 API 集成、需要可测试封装、或者已经有多个业务服务调用同一个外部 API 时用。`HttpClient` 完全藏在接口后面，测试只 mock 接口。

另外记住：**类型化客户端默认是 transient 的**，这个设计是刻意的。如果你的单例服务需要发 HTTP 请求，注入 `IHttpClientFactory`，别注入类型化客户端。

`IHttpClientFactory` 不是一个锦上添花的抽象，它的 handler 池化设计解决了两个真正的生产问题——socket 耗尽和 DNS 过期。理解了这个机理，transient 类型化客户端和 2 分钟 handler 过期这些默认行为就不再是死记硬背，而是设计意图的自然结果。

## 常见问题

**Q: IHttpClientFactory 是什么，为什么要用它？**

`IHttpClientFactory` 是 .NET 中安全创建和管理 `HttpClient` 实例的工厂抽象。`new HttpClient()` 每次请求创建会导致 socket 耗尽，静态单例会导致 DNS 不更新，`IHttpClientFactory` 通过 `HttpMessageHandler` 池化和可配置的过期轮换同时解决了这两个问题。

**Q: 命名客户端和类型化客户端有什么区别？**

命名客户端按字符串键检索，集中了配置但消费者仍暴露在 `IHttpClientFactory` 和魔法字符串中。类型化客户端把 `HttpClient` 包装成业务接口，编译期安全、封装了 API 特定逻辑、测试时只需 mock 接口。非临时调用优先用类型化客户端。

**Q: 为什么类型化客户端不能用在单例服务里？**

transient 类型化客户端被单例捕获后，单例持有的 `HttpClient` 和底层 `HttpMessageHandler` 不会过期轮换，DNS 变更永远不被感知。单例需要发 HTTP 时应该注入 `IHttpClientFactory`，每次调用时创建客户端。

**Q: IHttpClientFactory 如何处理 DNS 变更？**

池化的 `HttpMessageHandler` 有可配置的过期时间（默认 2 分钟），过期后从池中移除，下次请求创建新连接时触发新的 DNS 解析。这个自动轮换窗口让应用不需要重启就能适应 IP 变更。

**Q: 什么是 DelegatingHandler，什么时候用它？**

`DelegatingHandler` 是 HTTP 请求管道中的中间件层。当你需要统一应用的横切关注点时用它——结构化日志、token 注入、重试逻辑、关联 ID 传播、响应缓存。handler 把这些关注点从类型化客户端业务逻辑中分离出来，可以在多个客户端间复用。

**Q: 怎么写用了类型化客户端的单元测试？**

类型化客户端背后有接口（如 `IGitHubClient`），测试时用 NSubstitute 或 Moq 创建 mock 实现，设置预期返回值，注入到被测试的类中即可。不需要 mock `HttpClient`、`HttpMessageHandler` 或 `IHttpClientFactory`。

## 参考

- [IHttpClientFactory in .NET: Named Clients, Typed Clients, and DI Patterns — Dev Leader](https://www.devleader.ca/2026/06/27/ihttpclientfactory-in-net-named-clients-typed-clients-and-di-patterns)
- [HttpClient in C#: The Complete Guide](https://www.devleader.ca/2026/06/26/httpclient-in-c-the-complete-guide-for-net-developers)
- [Dependency Inversion Principle in C#](https://www.devleader.ca/2026/06/15/dependency-inversion-principle-c-abstractions-over-concretions)
- [Interface Segregation Principle in C#](https://www.devleader.ca/2026/06/14/interface-segregation-principle-c-focused-interfaces-that-scale)
