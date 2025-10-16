---
pubDatetime: 2025-04-16 10:51:13
tags: [".NET", "ASP.NET Core"]
slug: extending-httpclient-delegating-handlers-aspnetcore
source: https://www.milanjovanovic.tech/blog/extending-httpclient-with-delegating-handlers-in-aspnetcore
title: ASP.NET Core进阶：通过Delegating Handlers扩展HttpClient，日志记录、弹性策略与身份验证一网打尽！
description: 探索如何在ASP.NET Core中通过Delegating Handlers扩展HttpClient行为，包括实现日志记录、重试机制和身份验证，助你打造更强大的应用程序。
---

# ASP.NET Core进阶：通过Delegating Handlers扩展HttpClient，日志记录、弹性策略与身份验证一网打尽！ 🚀

## 什么是Delegating Handlers？🤔

在ASP.NET Core开发中，[Delegating Handlers](https://learn.microsoft.com/en-us/dotnet/api/system.net.http.delegatinghandler?view=net-8.0)是一种非常强大的机制，它的作用类似于[ASP.NET Core中间件](https://www.milanjovanovic.tech/blog/3-ways-to-create-middleware-in-asp-net-core)。不同之处在于：

- **中间件**处理的是进入应用的HTTP请求。
- **Delegating Handlers**则用于处理发往外部的HTTP请求。

通过它，我们可以为`HttpClient`添加额外行为，例如日志记录、请求重试、身份验证等。这些功能在开发云原生应用和微服务架构时尤为重要。

今天，我们将深入探讨如何利用Delegating Handlers来优化HTTP请求处理，并通过丰富的代码示例实现以下功能：

- 日志记录
- 弹性处理（重试机制）
- 身份验证

---

## 配置HttpClient：第一步👨‍💻

我们从一个简单的应用开始，它使用`HttpClient`调用GitHub API，并通过`GitHubService`类实现一个类型化客户端（Typed Client）。如下是代码：

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

### 什么是类型化客户端？

类型化客户端封装了`HttpClient`的行为，让我们可以通过强类型的API发送请求，而无需直接操作`HttpClient`。它的优势包括：

- **简化代码**：隐藏复杂的HTTP配置。
- **自动注入**：通过ASP.NET Core依赖注入（DI）系统自动管理。
- **生命周期管理**：无需手动释放`HttpClient`，由底层的`IHttpClientFactory`完成管理。

示例代码：

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

---

## 日志记录：让HTTP请求透明化 📜

第一步是为HTTP请求添加日志记录功能。我们通过自定义Delegating Handler实现这一点。

### 创建LoggingDelegatingHandler

以下代码展示了如何创建一个自定义Delegating Handler，用于在发送HTTP请求前后记录日志：

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

### 注册Handler到DI容器

将Handler注册为**Transient**服务，并绑定到`GitHubService`：

```csharp
builder.Services.AddTransient<LoggingDelegatingHandler>();

builder.Services.AddHttpClient<GitHubService>(httpClient =>
{
    httpClient.BaseAddress = new Uri("https://api.github.com");
})
.AddHttpMessageHandler<LoggingDelegatingHandler>();
```

---

## 弹性策略：打造云端稳定应用 🌐

为了提高应用在网络波动或服务故障时的稳定性，我们可以通过[Polly库](https://github.com/App-vNext/Polly)为HTTP请求增加重试策略。

### 创建RetryDelegatingHandler

以下是一个实现重试机制的代码示例：

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

### 配置多层Handler

我们可以将多个Delegating Handlers链式绑定，实现叠加功能：

```csharp
builder.Services.AddTransient<RetryDelegatingHandler>();

builder.Services.AddHttpClient<GitHubService>(httpClient =>
{
    httpClient.BaseAddress = new Uri("https://api.github.com");
})
.AddHttpMessageHandler<LoggingDelegatingHandler>()
.AddHttpMessageHandler<RetryDelegatingHandler>();
```

---

## 身份验证：安全通信的必备 🔒

在与外部API交互时，身份验证是必不可少的。以下是两个示例实现：

1. 简单的Access Token认证。
2. 基于Keycloak的OAuth 2.0认证。

### 示例1：Access Token认证

通过在请求头中添加`Authorization`字段实现简单认证：

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

注册到服务：

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

### 示例2：Keycloak OAuth 2.0认证

以下是更复杂的实现，使用[Keycloak](https://www.keycloak.org/)进行授权，并获取Access Token：

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

---

## 总结与启发 ✨

通过Delegating Handlers，我们可以轻松扩展`HttpClient`，解决许多常见的开发问题，例如：

- 在发送请求前后记录日志。
- 增加弹性处理（重试、回退机制）。
- 集成身份验证逻辑。
