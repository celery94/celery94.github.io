---
pubDatetime: 2026-07-03T08:38:49+08:00
title: "Mock HttpClient C#：DelegatingHandler、Mock 处理器与集成测试"
description: "从零学会在 .NET 10 中 Mock HttpClient：自定义 HttpMessageHandler 桩、DelegatingHandler 拦截器、IHttpClientFactory 注入、WebApplicationFactory 集成测试，以及韧性管线验证。每一步都能照着做出来。"
tags:
  ["C#", ".NET", "HttpClient", "测试", "Mock", "DelegatingHandler", "集成测试"]
slug: "mock-httpclient-csharp-delegatinghandler-testing"
source: "https://www.devleader.ca/2026/07/02/mock-httpclient-c-delegatinghandler-mock-handlers-and-integration-testing"
ogImage: "../../assets/922/01-cover.png"
---

写过调用外部 HTTP API 的代码，就一定碰过这个问题：生产环境跑得好好的，一到测试就头疼。要么让测试真的去打网络——慢、不稳定、依赖外部服务；要么干脆不测。两个答案都不行。

Mock HttpClient 就是解决这件事的办法。一旦理解了背后的机制，整个方案干净得出奇。

本文覆盖 .NET 10 下 HttpClient 测试的完整工具箱：从零写 `MockHttpMessageHandler`、搭建响应桩、捕获并断言请求、通过 `IHttpClientFactory` 注入 Mock 处理器、测试韧性管线，到用 `WebApplicationFactory` 跑完整集成测试。测试框架用 xUnit，语言用 C# 12+。

如果你对 `HttpClient` 本身还不熟，可以先看 [HttpClient in C# 完全指南](https://www.devleader.ca/2026/06/26/httpclient-in-c-the-complete-guide-for-net-developers)。如果已经在生产环境用过 `HttpClient`，就是来学怎么 Mock 的，那直接往下看就行。

## 为什么 HttpClient 难测

`HttpClient` 看起来直接：注入它，调 `GetAsync` 或 `PostAsJsonAsync`，处理响应。等你真要写测试时才会发现问题——没有 `IHttpClient` 接口可以替换，类也不是抽象或 sealed 到能让你覆盖行为，没法轻松换成假的。

更核心的问题是测试运行时到底发生了什么。没有拦截的话，`HttpClient` 会打开一条真实 TCP 连接到 `BaseAddress` 或你配的 URL。这意味你的测试：

- 依赖目标服务器活着且可达
- 可能因为 DNS 解析、TLS 握手、网络延迟变慢
- 不确定性——服务器每次返回的数据可能不一样
- 离线或在隔离 CI 环境中根本跑不了

除此之外，你控制不了服务器返回什么。你没法模拟 503 来测重试逻辑，没法测 API 返回畸形 JSON 时你的代码会怎样，也没法验证你的代码发出去的 Header 和 Body 到底对不对。真实网络调用把你锁在了 happy path 上，还得看服务器配不配合。

有更好的办法。而且不用什么特殊测试基础设施——这个切入点就内建在框架里。

## HttpMessageHandler：天然的测试接缝

核心结论：`HttpClient` 本身不做网络调用。它把每个请求都委托给 `HttpMessageHandler`。默认情况下这个 handler 是 `HttpClientHandler`，它负责开 socket、做真实的 I/O。但这只是默认行为。

`HttpClient` 的构造函数可以接受一个 `HttpMessageHandler` 参数：

```csharp
var client = new HttpClient(myCustomHandler);
```

这就是你的测试接缝。塞一个假的 handler，一切尽在掌控。Handler 之上的 `HttpClient` 代码完全不变，照样调 `SendAsync`，只是你的 handler 返回你想要的响应。

这条思路其实是对[依赖反转原则](https://www.devleader.ca/2026/06/15/dependency-inversion-principle-c-abstractions-over-concretions)的直接应用：框架依赖的是 `HttpMessageHandler` 抽象，不是具体的网络层。测试就利用这个接缝。

`HttpMessageHandler` 基类只有一个 protected virtual 方法：

```csharp
protected override Task<HttpResponseMessage> SendAsync(
    HttpRequestMessage request,
    CancellationToken cancellationToken);
```

所有请求都经过这一个方法。拦截了它，就拦截了客户端发出的每个 HTTP 调用。

## 从零构建 MockHttpMessageHandler

不需要外部库。一个最精简的自定义 handler 就能把事情做清楚：

```csharp
public sealed class MockHttpMessageHandler : HttpMessageHandler
{
    private readonly Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> _sendAsync;

    public MockHttpMessageHandler(
        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> sendAsync)
    {
        _sendAsync = sendAsync;
    }

    // 简单同步桩的便捷构造
    public MockHttpMessageHandler(Func<HttpResponseMessage> responseFactory)
        : this((_, _) => Task.FromResult(responseFactory()))
    {
    }

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
        => _sendAsync(request, cancellationToken);
}
```

就这些。一个 `Func<>` 接收请求，返回响应。调用方决定返回什么，handler 只管执行。

这个设计让 handler 本身没有逻辑——没有分支、没有状态。所有测试行为都在传入的 lambda 里。Handler 可以在多个测试间复用，每个测试的意图在调用点一目了然。

## 编写响应桩：状态码、请求头、JSON Body

有了 `MockHttpMessageHandler`，还需要构造可信响应的办法。标准库已经满足所有需求。下面是一组最常见场景的辅助工厂：

```csharp
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;

public static class HttpStubs
{
    // 返回 200 OK 并带 JSON 序列化的 body
    public static MockHttpMessageHandler ReturnsJson<T>(
        T value,
        HttpStatusCode status = HttpStatusCode.OK)
    {
        var json = JsonSerializer.Serialize(value);
        return new MockHttpMessageHandler((_, _) =>
            Task.FromResult(new HttpResponseMessage(status)
            {
                Content = new StringContent(json, Encoding.UTF8, "application/json")
            }));
    }

    // 返回指定状态码，无 body
    public static MockHttpMessageHandler ReturnsStatus(HttpStatusCode status) =>
        new MockHttpMessageHandler((_, _) =>
            Task.FromResult(new HttpResponseMessage(status)));

    // 返回 JSON 加自定义请求头——适合分页或限流测试
    public static MockHttpMessageHandler ReturnsJsonWithHeaders<T>(
        T value,
        IDictionary<string, string> headers,
        HttpStatusCode status = HttpStatusCode.OK)
    {
        var json = JsonSerializer.Serialize(value);
        return new MockHttpMessageHandler((_, _) =>
        {
            var response = new HttpResponseMessage(status)
            {
                Content = new StringContent(json, Encoding.UTF8, "application/json")
            };
            foreach (var (key, val) in headers)
                response.Headers.TryAddWithoutValidation(key, val);
            return Task.FromResult(response);
        });
    }
}
```

这几个桩覆盖 Mock HttpClient 的绝大多数场景：带类型的 JSON 响应、纯状态码响应用于错误场景、带自定义请求头的响应用于分页游标或限流元数据。`HttpStubs` 工厂让每个测试方法专注于被测行为，而不是样板化的响应构造。

## 验证请求行为：方法、URL、请求头、请求体

桩响应只是问题的一半。另一半是验证你的代码发出的请求对不对。这里的模式是在 handler 内部捕获请求，调用完成后断言：

```csharp
[Fact]
public async Task CreateUser_SendsCorrectRequestToApi()
{
    // Arrange——捕获变量用于调用后断言
    HttpRequestMessage? capturedRequest = null;
    string? capturedBody = null;

    var handler = new MockHttpMessageHandler(async (req, ct) =>
    {
        capturedRequest = req;

        // 必须在 handler 内部读取 body——调用完成后流不可回退
        capturedBody = await req.Content!.ReadAsStringAsync(ct);

        return new HttpResponseMessage(HttpStatusCode.Created)
        {
            Content = new StringContent(
                """{"id":1,"name":"Alice","email":"alice@example.com"}""",
                Encoding.UTF8,
                "application/json")
        };
    });

    var httpClient = new HttpClient(handler) { BaseAddress = new Uri("https://api.example.com") };
    var apiClient = new UserApiClient(httpClient);

    // Act
    await apiClient.CreateUserAsync(new User(0, "Alice", "alice@example.com"));

    // Assert——验证实际发送了什么
    Assert.NotNull(capturedRequest);
    Assert.Equal(HttpMethod.Post, capturedRequest.Method);
    Assert.Equal("/users", capturedRequest.RequestUri?.PathAndQuery);
    Assert.Equal("application/json", capturedRequest.Content?.Headers.ContentType?.MediaType);
    Assert.NotNull(capturedBody);
    Assert.Contains("Alice", capturedBody);
}
```

一个关键细节：在 handler 的委托内部读取 `req.Content`，不要在 `SendAsync` 返回后再读。请求体流在 handler 完成后就被消耗了——之后再读只能拿到空字符串或 `ObjectDisposedException`。趁还有访问权时把需要的都取出来。

## DelegatingHandler：测试拦截器（Spy/Capture 模式）

`DelegatingHandler` 和 `HttpMessageHandler` 不一样。`HttpMessageHandler` 处在管线末端，负责生成响应；`DelegatingHandler` 则处于中间——它观察甚至改变请求和响应，然后传给下一个 handler。

这使得 `DelegatingHandler` 非常适合 spy 模式。你要记录发生了什么，但不替换生成响应的 handler。这在测试认证头注入、请求关联 ID、日志等中间件行为时特别有用——你关心的是穿过来的东西，而不是捏造响应：

```csharp
public sealed class SpyDelegatingHandler : DelegatingHandler
{
    private readonly List<HttpRequestMessage> _requests = [];
    private readonly List<HttpResponseMessage> _responses = [];

    public IReadOnlyList<HttpRequestMessage> Requests => _requests;
    public IReadOnlyList<HttpResponseMessage> Responses => _responses;
    public int CallCount => _requests.Count;

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        _requests.Add(request);
        var response = await base.SendAsync(request, cancellationToken);
        _responses.Add(response);
        return response;
    }
}
```

用 spy 和 mock inner handler 组合成一个完整测试管线：

```csharp
[Fact]
public async Task AuthorizationHeader_IsSentWithEveryRequest()
{
    // Arrange——spy 在前，mock 在后
    var innerHandler = HttpStubs.ReturnsJson(new User(1, "Alice", "alice@example.com"));
    var spy = new SpyDelegatingHandler { InnerHandler = innerHandler };

    var client = new HttpClient(spy) { BaseAddress = new Uri("https://api.example.com") };
    var apiClient = new UserApiClient(client);

    // Act
    await apiClient.GetUserAsync(1);
    await apiClient.GetUsersAsync();

    // Assert——验证两个调用的横切行为
    Assert.Equal(2, spy.CallCount);
    Assert.All(spy.Requests, req =>
        Assert.True(
            req.Headers.Contains("Authorization"),
            "每次发出的请求都必须携带 Authorization 头。"));
}
```

Spy 让你完整观察管线，又不替换生成响应的 handler。这是验证横切关注点的一条干净路径。

## 通过 IHttpClientFactory 注入 Mock 处理器

直接构造 `HttpClient` 对单元测试 typed client 类很好用。但生产代码通常通过 `AddHttpClient` 使用 `IHttpClientFactory`。问题在于工厂在内部构建 `HttpClient` 实例——没法像直接构造那样传入 handler。

答案在 `ConfigurePrimaryHttpMessageHandler`。它钩入工厂的 builder 管线，在 handler 的最外层配置点注入：

```csharp
using Microsoft.Extensions.DependencyInjection;

[Fact]
public async Task UserApiClient_ViaFactory_ReturnsMockedUser()
{
    // Arrange——通过工厂注入 mock handler
    var expected = new User(7, "Bob", "bob@example.com");
    var mockHandler = HttpStubs.ReturnsJson(expected);

    var services = new ServiceCollection();
    services
        .AddHttpClient<IUserApiClient, UserApiClient>(client =>
        {
            client.BaseAddress = new Uri("https://api.example.com");
        })
        .ConfigurePrimaryHttpMessageHandler(() => mockHandler);

    await using var provider = services.BuildServiceProvider();
    var apiClient = provider.GetRequiredService<IUserApiClient>();

    // Act
    var user = await apiClient.GetUserAsync(7);

    // Assert
    Assert.NotNull(user);
    Assert.Equal("Bob", user.Name);
    Assert.Equal(7, user.Id);
}
```

这个测试覆盖了完整的 `IHttpClientFactory` 集成。客户端从 DI 容器解析出来，完全和产线一样。唯一替换的是管线底部的 HTTP handler。加在上面的任何 `DelegatingHandler` 层——比如重试或日志——仍然在跑。

## WebApplicationFactory 集成测试：进程内跑真实 HTTP

当你需要端到端测试完整请求路径——路由、中间件、控制器，以及这些控制器调用的服务和对外 HTTP 调用——`WebApplicationFactory` 是合适的工具。它在进程内启动你的应用，让你替换任何已注册的服务。

如果你还不熟悉 `WebApplicationFactory`，可以先看 [Testing ASP.NET Core Web API 基础](https://www.devleader.ca/2026/06/08/testing-aspnet-core-web-api-webapplicationfactory-and-integration-tests)。这里的方法是在那之上叠加。

```csharp
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;

public sealed class WeatherForecastIntegrationTests
    : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;

    public WeatherForecastIntegrationTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task GetForecast_ReturnsOk_WhenWeatherApiIsAvailable()
    {
        // Arrange——只替换该测试的外部天气 API handler
        var fakeForecast = new[] { new Forecast("Sunny", 24), new Forecast("Cloudy", 18) };
        var mockHandler = HttpStubs.ReturnsJson(fakeForecast);

        var testClient = _factory
            .WithWebHostBuilder(builder =>
            {
                builder.ConfigureServices(services =>
                {
                    services
                        .AddHttpClient<IWeatherService, WeatherService>()
                        .ConfigurePrimaryHttpMessageHandler(() => mockHandler);
                });
            })
            .CreateClient();

        // Act——走完整的 ASP.NET Core 管线
        var response = await testClient.GetAsync("/api/forecast");

        // Assert
        response.EnsureSuccessStatusCode();
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("Sunny", body);
    }
}
```

`WithWebHostBuilder` 模式创建的作用域覆盖只影响这个测试的客户端，不干扰其他共享 `IClassFixture` 的测试。真实 ASP.NET Core 请求管线端到端运行——路由、中间件、模型绑定全在。唯一被 Mock 截住的是打到外部天气 API 的调用。

## 测试韧性行为：模拟瞬时故障并验证重试

.NET 8 引入了 `AddStandardResilienceHandler()`（来自 `Microsoft.Extensions.Http.Resilience`），用基于 Polly 的管线包裹 `HttpClient` 调用，涵盖重试、断路、超时。要验证韧性配置确实触发，需要模拟失败。调用计数模式让这件事很直接：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Http.Resilience;

[Fact]
public async Task GetUser_RetriesOnTransientFailure_AndSucceedsOnThirdAttempt()
{
    // Arrange——前两次返回 503，第三次返回 200
    var callCount = 0;
    var handler = new MockHttpMessageHandler((_, _) =>
    {
        callCount++;
        var statusCode = callCount < 3
            ? HttpStatusCode.ServiceUnavailable   // 503 触发重试
            : HttpStatusCode.OK;

        var response = new HttpResponseMessage(statusCode);
        if (statusCode == HttpStatusCode.OK)
        {
            response.Content = new StringContent(
                """{"id":1,"name":"Alice","email":"alice@example.com"}""",
                Encoding.UTF8, "application/json");
        }
        return Task.FromResult(response);
    });

    var services = new ServiceCollection();
    services
        .AddHttpClient<IUserApiClient, UserApiClient>(c =>
            c.BaseAddress = new Uri("https://api.example.com"))
        .ConfigurePrimaryHttpMessageHandler(() => handler)
        .AddStandardResilienceHandler();

    await using var provider = services.BuildServiceProvider();
    var apiClient = provider.GetRequiredService<IUserApiClient>();

    // Act
    var user = await apiClient.GetUserAsync(1);

    // Assert——确实重试了，最终结果正确
    Assert.Equal(3, callCount);
    Assert.NotNull(user);
    Assert.Equal("Alice", user.Name);
}
```

这个测试证明了重试管线挂上并实际为你的客户端配置触发。没有它，你只是在信任 `AddStandardResilienceHandler` 能工作，但不验证它接对了客户端。一个实用提示：标准韧性 handler 的重试策略默认带真实回退延迟（指数级，大契约 2 秒基础）。如果测试要快跑，用 `AddStandardResilienceHandler(o => o.Retry.Delay = TimeSpan.Zero)` 缩短延迟，或注入 `FakeTimeProvider`。

## NSubstitute 替代方案

如果项目全局用 NSubstitute，也可以配合 Mock HttpClient。挑战在于 `HttpMessageHandler.SendAsync` 是 protected 方法——NSubstitute 不能直接配置具体类型的 protected 成员。

解决方案是一个薄抽象适配器，暴露 public 方法并桥接到 `SendAsync`：

```csharp
// 公开可替换 public 方法的适配器
public abstract class TestableHttpMessageHandler : HttpMessageHandler
{
    public abstract Task<HttpResponseMessage> HandleRequestAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken);

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
        => HandleRequestAsync(request, cancellationToken);
}
```

有了这个基类，NSubstitute 照常工作：

```csharp
using NSubstitute;

[Fact]
public async Task GetUser_UsesNSubstitute_ToReturnStubResponse()
{
    // Arrange
    var handler = Substitute.For<TestableHttpMessageHandler>();
    handler
        .HandleRequestAsync(Arg.Any<HttpRequestMessage>(), Arg.Any<CancellationToken>())
        .Returns(new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(
                """{"id":5,"name":"Carol","email":"carol@example.com"}""",
                Encoding.UTF8, "application/json")
        });

    var httpClient = new HttpClient(handler) { BaseAddress = new Uri("https://api.example.com") };
    var apiClient = new UserApiClient(httpClient);

    // Act
    var user = await apiClient.GetUserAsync(5);

    // Assert
    Assert.NotNull(user);
    Assert.Equal("Carol", user.Name);

    // 用 NSubstitute 的 Received 验证
    await handler.Received(1)
        .HandleRequestAsync(
            Arg.Is<HttpRequestMessage>(r => r.Method == HttpMethod.Get),
            Arg.Any<CancellationToken>());
}
```

NSubstitute 方案在需要更丰富的参数匹配和 received-call 验证时有用。但大多数场景下用 lambda 的 `MockHttpMessageHandler` 更轻量。两者可以共存。

## 常见坑

即便用对方法，有几处错误会在代码库里反复出现：

**提前 dispose 了 `HttpResponseMessage`。** 在 mock 委托内部构造 `new HttpResponseMessage(...)` 没问题；如果在外层创建然后跨多次调用共享，第一次成功读取会消耗掉内容流，后续调用静默返回空 body。

**忘了设 `BaseAddress`。** 用 handler 直接构造 `HttpClient` 时（不走工厂），没有 `BaseAddress` 除非你自己设。如果你的 typed client 用了相对 URL 如 `GetAsync("users/1")`，调用会直接抛 `InvalidOperationException`。测试 setup 时别忘了给 `HttpClient` 加上 `BaseAddress`。

**不在 handler 内部读请求体。** 想断言请求 payload 的话，要在 mock 委托内部 `await req.Content!.ReadAsStringAsync()`。`SendAsync` 一返回，内容流就被消耗了。事后读取拿到的是空串或异常。

**没有 handler 计数器就测韧性管线。** 一个永远返回 200 的 mock 没法证明你的重试策略有效。记录 handler 被调次数——重试应该增加计数——然后同时断言调用次数和最终结果。

## 完整示例

把以上拼在一起。下面是真实的 typed REST 客户端加完整测试套件，覆盖 happy path、404 处理、错误传播和请求校验。

首先是待测客户端：

```csharp
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;

namespace MyApp.ApiClients;

public sealed record User(int Id, string Name, string Email);

public interface IUserApiClient
{
    Task<User?> GetUserAsync(int id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<User>> GetUsersAsync(CancellationToken cancellationToken = default);
    Task<User> CreateUserAsync(User user, CancellationToken cancellationToken = default);
}

// C# 12+ 主构造函数语法
public sealed class UserApiClient(HttpClient client) : IUserApiClient
{
    public async Task<User?> GetUserAsync(int id, CancellationToken cancellationToken = default)
    {
        var response = await client.GetAsync($"/users/{id}", cancellationToken);
        if (response.StatusCode == HttpStatusCode.NotFound)
            return null;
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<User>(cancellationToken: cancellationToken);
    }

    public async Task<IReadOnlyList<User>> GetUsersAsync(CancellationToken cancellationToken = default)
    {
        var response = await client.GetAsync("/users", cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<List<User>>(cancellationToken: cancellationToken) ?? [];
    }

    public async Task<User> CreateUserAsync(User user, CancellationToken cancellationToken = default)
    {
        var response = await client.PostAsJsonAsync("/users", user, cancellationToken);
        response.EnsureSuccessStatusCode();
        return (await response.Content.ReadFromJsonAsync<User>(cancellationToken: cancellationToken))!;
    }
}
```

然后是完整测试套件：

```csharp
using System.Net;
using System.Net.Http;
using System.Text;
using Xunit;

namespace MyApp.Tests.ApiClients;

public sealed class UserApiClientTests
{
    private static UserApiClient CreateClient(MockHttpMessageHandler handler)
    {
        var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://api.example.com")
        };
        return new UserApiClient(httpClient);
    }

    [Fact]
    public async Task GetUserAsync_ReturnsUser_WhenApiReturns200()
    {
        var expected = new User(42, "Alice", "alice@example.com");
        var client = CreateClient(HttpStubs.ReturnsJson(expected));

        var user = await client.GetUserAsync(42);

        Assert.NotNull(user);
        Assert.Equal(42, user.Id);
        Assert.Equal("Alice", user.Name);
    }

    [Fact]
    public async Task GetUserAsync_ReturnsNull_WhenApiReturns404()
    {
        var client = CreateClient(HttpStubs.ReturnsStatus(HttpStatusCode.NotFound));

        var user = await client.GetUserAsync(999);

        Assert.Null(user);
    }

    [Fact]
    public async Task GetUserAsync_ThrowsHttpRequestException_OnServerError()
    {
        var client = CreateClient(HttpStubs.ReturnsStatus(HttpStatusCode.InternalServerError));

        await Assert.ThrowsAsync<HttpRequestException>(() => client.GetUserAsync(1));
    }

    [Fact]
    public async Task GetUsersAsync_ReturnsAllUsers_WhenApiResponds()
    {
        var expected = new List<User>
        {
            new(1, "Alice", "alice@example.com"),
            new(2, "Bob", "bob@example.com")
        };
        var client = CreateClient(HttpStubs.ReturnsJson(expected));

        var users = await client.GetUsersAsync();

        Assert.Equal(2, users.Count);
        Assert.Equal("Alice", users[0].Name);
    }

    [Fact]
    public async Task GetUsersAsync_ReturnsEmptyList_WhenNoUsersExist()
    {
        var client = CreateClient(HttpStubs.ReturnsJson(Array.Empty<User>()));

        var users = await client.GetUsersAsync();

        Assert.Empty(users);
    }

    [Fact]
    public async Task CreateUserAsync_SendsJsonBody_WithPostMethodAndCorrectPath()
    {
        HttpRequestMessage? captured = null;
        string? capturedBody = null;

        var handler = new MockHttpMessageHandler(async (req, ct) =>
        {
            captured = req;
            capturedBody = await req.Content!.ReadAsStringAsync(ct);
            return new HttpResponseMessage(HttpStatusCode.Created)
            {
                Content = new StringContent(
                    """{"id":99,"name":"Dave","email":"dave@example.com"}""",
                    Encoding.UTF8, "application/json")
            };
        });

        var client = CreateClient(handler);
        var created = await client.CreateUserAsync(new User(0, "Dave", "dave@example.com"));

        Assert.Equal(HttpMethod.Post, captured?.Method);
        Assert.Equal("/users", captured?.RequestUri?.PathAndQuery);
        Assert.NotNull(capturedBody);
        Assert.Contains("Dave", capturedBody);
        Assert.Equal(99, created.Id);
        Assert.Equal("Dave", created.Name);
    }

    [Fact]
    public async Task CreateUserAsync_ThrowsHttpRequestException_OnConflict()
    {
        var client = CreateClient(HttpStubs.ReturnsStatus(HttpStatusCode.Conflict));

        await Assert.ThrowsAsync<HttpRequestException>(() =>
            client.CreateUserAsync(new User(0, "Alice", "alice@example.com")));
    }
}
```

这就是一个完整 typed client 的测试套件。每个有意义的行为都有覆盖：成功场景、未找到处理、错误传播、请求结构校验。没有外部服务器，没有不稳定因素，没有网络依赖。每个测试确定、快速、意图明确。

## 小结

测试使用 `HttpClient` 的 C# 代码归结为一个核心洞察：拦截 `HttpMessageHandler.SendAsync`。Mock HttpClient 的能力完全取决于这个接缝，而框架免费把它给了你。其他一切——响应桩、请求捕获、工厂注入、韧性验证、集成测试覆盖——都建立在这个单一切入点上。有了 `MockHttpMessageHandler`，后续都自然、可组合地跟进。

本文的模式适用于 .NET 10 中任何基于 `HttpClient` 的代码：typed client、`IHttpClientFactory` 的 named client、或者直接注入的 client——基于 handler 的方案全都能用。加 `SpyDelegatingHandler` 处理横切关注点，用 `WebApplicationFactory` 覆盖跑端到端集成测试，用 handler 计数验证韧性行为。

如果你关注 .NET 开发、测试实践和软件工程，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Mock HttpClient C#: DelegatingHandler, Mock Handlers, and Integration Testing — Dev Leader](https://www.devleader.ca/2026/07/02/mock-httpclient-c-delegatinghandler-mock-handlers-and-integration-testing)
- [HttpClient in C#: The Complete Guide](https://www.devleader.ca/2026/06/26/httpclient-in-c-the-complete-guide-for-net-developers)
- [Dependency Inversion Principle in C#](https://www.devleader.ca/2026/06/15/dependency-inversion-principle-c-abstractions-over-concretions)
- [Testing ASP.NET Core Web API: WebApplicationFactory and Integration Tests](https://www.devleader.ca/2026/06/08/testing-aspnet-core-web-api-webapplicationfactory-and-integration-tests)
