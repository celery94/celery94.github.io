---
pubDatetime: 2024-04-08
tags: [C#, HttpClient]
source: https://www.milanjovanovic.tech/blog/extending-httpclient-with-delegating-handlers-in-aspnetcore?utm_source=Twitter&utm_medium=social&utm_campaign=01.04.2024
author: Milan Jovanović
title: 在 ASP.NET Core 中通过 Delegating Handlers 扩展 HttpClient
description: Delegating handlers 很像 ASP.NET Core 的中间件。不同的是，它们与 HttpClient 一起工作。我将向你展示如何使用 delegating handlers
---

> ## 摘要
>
> Delegating handlers 很像 ASP.NET Core 的中间件。不同的是，它们与 HttpClient 一起工作。我将向你展示如何使用 delegating handlers

[Delegating handlers](https://learn.microsoft.com/en-us/dotnet/api/system.net.http.delegatinghandler?view=net-8.0) 很像 [ASP.NET Core 中间件](https://www.milanjovanovic.tech/blog/3-ways-to-create-middleware-in-asp-net-core)。不同的是，它们与 [`HttpClient`](https://www.milanjovanovic.tech/blog/the-right-way-to-use-httpclient-in-dotnet) 一起工作。ASP.NET Core 请求管道允许你通过使用 [中间件](https://www.milanjovanovic.tech/blog/3-ways-to-create-middleware-in-asp-net-core) 引入自定义行为。你可以使用中间件解决许多横切关注点 — 日志记录、跟踪、验证、认证、授权等。

但是，一个重要的方面是，中间件与进入你的 API 的 HTTP 请求一起工作。Delegating handlers 与发出的请求一起工作。

[`HttpClient`](https://learn.microsoft.com/en-us/dotnet/api/system.net.http.httpclient?view=net-8.0) 是我首选的在 ASP.NET Core 中发送 HTTP 请求的方法。它使用起来非常简单，并解决了我的大多数用例。你可以使用 delegating handlers 在发送 HTTP 请求前或后扩展 `HttpClient` 的行为。

今天，我想向你展示如何使用 [`DelegatingHandler`](https://learn.microsoft.com/en-us/dotnet/api/system.net.http.delegatinghandler?view=net-8.0) 引入：

- 日志记录
- 弹性
- 认证

## 配置 HttpClient

这是一个非常简单的应用，它：

- 将 `GitHubService` 类配置为一个类型化的 HTTP 客户端
- 设置 `HttpClient.BaseAddress` 指向 GitHub API
- 暴露一个通过用户名检索 GitHub 用户的端点

我们将使用 delegating handlers 扩展 `GitHubService` 的行为。

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHttpClient<GitHubService>(httpClient =>
{
    httpClient.BaseAddress = new Uri("https://api.github.com");
});

var app = builder.Build();

app.MapGet("api/users/{username}", async (
    string username,
    GitHubService gitHubService) =>
{
    var content = await gitHubService.GetByUsernameAsync(username);

    return Results.Ok(content);
});

app.Run();
```

`GitHubService` 类是一个 [类型化客户端](https://www.milanjovanovic.tech/blog/the-right-way-to-use-httpclient-in-dotnet#replacing-named-clients-with-typed-clients) 的实现。类型化客户端允许你暴露一个强类型的 API 并隐藏 `HttpClient`。运行时通过依赖注入提供一个配置过的 `HttpClient` 实例。你也不必考虑释放 `HttpClient`。它从一个管理 `HttpClient` 生命周期的底层 `IHttpClientFactory` 解析出来。

```csharp
public class GitHubService(HttpClient client)
{
    public async Task<GitHubUser?> GetByUsernameAsync(string username)
    {
        var url = $"users/{username}";

        return await client.GetFromJsonAsync<GitHubUser>(url);
    }
}
```

## 使用 Delegating Handlers 记录 HTTP 请求

让我们从一个简单的例子开始。我们将在发送 HTTP 请求之前和之后添加日志记录。为此，我们将创建一个自定义的 delegating handler - `LoggingDelegatingHandler`。

自定义的 delegating handler 实现了 `DelegatingHandler` 基类。然后，你可以覆盖 `SendAsync` 方法以引入额外的行为。

```csharp
public class LoggingDelegatingHandler(ILogger<LoggingDelegatingHandler> logger)
    : DelegatingHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        try
        {
            logger.LogInformation("Before HTTP request");

            var result = await base.SendAsync(request, cancellationToken);

            result.EnsureSuccessStatusCode();

            logger.LogInformation("After HTTP request");

            return result;
        }
        catch (Exception e)
        {
            logger.LogError(e, "HTTP request failed");

            throw;
        }
    }
}
```

你还需要通过依赖注入注册 `LoggingDelegatingHandler`。Delegating handlers 必须以 **短暂** 的服务注册。

`AddHttpMessageHandler` 方法为 `GitHubService` 添加了 `LoggingDelegatingHandler` 作为一个 delegating handler。任何使用 `GitHubService` 发出的 HTTP 请求都将首先通过 `LoggingDelegatingHandler`。

```csharp
builder.Services.AddTransient<LoggingDelegatingHandler>();

builder.Services.AddHttpClient<GitHubService>(httpClient =>
{
    httpClient.BaseAddress = new Uri("https://api.github.com");
})
.AddHttpMessageHandler<LoggingDelegatingHandler>();
```

让我们看看还可以做些什么。

## 通过 Delegating Handlers 增加弹性

构建[弹性](https://learn.microsoft.com/en-us/dotnet/core/resilience/?tabs=dotnet-cli)应用是云开发的重要需求。

`RetryDelegatingHandler` 类使用 [Polly](https://github.com/App-vNext/Polly) 创建一个 `AsyncRetryPolicy`。重试策略封装了 HTTP 请求，并在遇到瞬态故障时重试它。

```csharp
public class RetryDelegatingHandler : DelegatingHandler
{
    private readonly AsyncRetryPolicy<HttpResponseMessage> _retryPolicy =
        Policy<HttpResponseMessage>
            .Handle<HttpRequestException>()
            .RetryAsync(2);

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        var policyResult = await _retryPolicy.ExecuteAndCaptureAsync(
            () => base.SendAsync(request, cancellationToken));

        if (policyResult.Outcome == OutcomeType.Failure)
        {
            throw new HttpRequestException(
                "Something went wrong",
                policyResult.FinalException);
        }

        return policyResult.Result;
    }
}
```

你还需要通过依赖注入注册 `RetryDelegatingHandler`。同时，记得将其配置为消息处理器。在这个例子中，我将两个 delegating handlers 链接在一起，它们将依次运行。

```csharp
builder.Services.AddTransient<RetryDelegatingHandler>();

builder.Services.AddHttpClient<GitHubService>(httpClient =>
{
    httpClient.BaseAddress = new Uri("https://api.github.com");
})
.AddHttpMessageHandler<LoggingDelegatingHandler>()
.AddHttpMessageHandler<RetryDelegatingHandler>();
```

## 通过 Delegating Handlers 解决认证问题

在任何微服务应用中，你都将不得不解决认证这一横切关注点。delegating handlers 的一个常见用途是在发送 HTTP 请求之前添加 `Authorization` 头。

例如，GitHub API 要求在认证传入请求时存在访问令牌。`AuthenticationDelegatingHandler` 类从 `GitHubOptions` 添加了 `Authorization` 头的值。另一个要求是指定 `User-Agent` 头，这是从应用配置中设置的。

```csharp
public class AuthenticationDelegatingHandler(IOptions<GitHubOptions> options)
    : DelegatingHandler
{
    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        request.Headers.Add("Authorization", options.Value.AccessToken);
        request.Headers.Add("User-Agent", options.Value.UserAgent);

        return base.SendAsync(request, cancellationToken);
    }
}
```

不要忘记将 `AuthenticationDelegatingHandler` 与 `GitHubService` 配置在一起：

```csharp
builder.Services.AddTransient<AuthenticationDelegatingHandler>();

builder.Services.AddHttpClient<GitHubService>(httpClient =>
{
    httpClient.BaseAddress = new Uri("https://api.github.com");
})
.AddHttpMessageHandler<LoggingDelegatingHandler>()
.AddHttpMessageHandler<RetryDelegatingHandler>()
.AddHttpMessageHandler<AuthenticationDelegatingHandler>();
```

以下是使用 `KeyCloakAuthorizationDelegatingHandler` 的更复杂的认证示例。这是一个从 [Keycloak](https://www.keycloak.org/) 获取访问令牌的 delegating handler。Keycloak 是一个开源身份和访问管理服务。

我在我的[实用洁净架构](https://www.milanjovanovic.tech/pragmatic-clean-architecture)课程中使用了 Keycloak 作为身份提供者。

这个例子中的 delegating handler 使用了 [OAuth 2.0](https://oauth.net/2/) [客户端凭据](https://www.oauth.com/oauth2-servers/access-tokens/client-credentials/)授权流程来获取访问令牌。当应用请求访问令牌以访问它们自己的资源，而不是代表一个用户时，就会使用这种授权。

```csharp
public class KeyCloakAuthorizationDelegatingHandler(
    IOptions<KeycloakOptions> keycloakOptions)
    : DelegatingHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        var authToken = await GetAccessTokenAsync();

        request.Headers.Authorization = new AuthenticationHeaderValue(
            JwtBearerDefaults.AuthenticationScheme,
            authToken.AccessToken);

        var httpResponseMessage = await base.SendAsync(
            request,
            cancellationToken);

        httpResponseMessage.EnsureSuccessStatusCode();

        return httpResponseMessage;
    }

    private async Task<AuthToken> GetAccessTokenAsync()
    {
        var params = new KeyValuePair<string, string>[]
        {
            new("client_id", _keycloakOptions.Value.AdminClientId),
            new("client_secret", _keycloakOptions.Value.AdminClientSecret),
            new("scope", "openid email"),
            new("grant_type", "client_credentials")
        };

        var content = new FormUrlEncodedContent(params);

        var authRequest = new HttpRequestMessage(
            HttpMethod.Post,
            new Uri(_keycloakOptions.TokenUrl))
        {
            Content = content
        };

        var response = await base.SendAsync(authRequest, cancellationToken);

        response.EnsureSuccessStatusCode();

        return await response.Content.ReadFromJsonAsync<AuthToken>() ??
               throw new ApplicationException();
    }
}
```

## 总结

Delegating handlers 为你提供了一个强大的机制，以扩展使用 `HttpClient` 发送请求时的行为。你可以使用 delegating handlers 解决横切关注点，就像你会使用中间件一样。

以下是一些你可能会使用 delegating handlers 的想法：

- 在发送 HTTP 请求前后记录日志
- 引入弹性策略（重试、回退）
- 验证 HTTP 请求内容
- 与外部 API 进行认证

我相信你自己也能想出一些用例。

我制作了一个展示如何[实现 delegating handlers](https://youtu.be/_u6v4D6qgDI)的视频，你可以[在这里观看。](https://youtu.be/_u6v4D6qgDI)

---
