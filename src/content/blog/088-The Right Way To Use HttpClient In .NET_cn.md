---
pubDatetime: 2024-04-08
tags: [C#]
source: https://www.milanjovanovic.tech/blog/the-right-way-to-use-httpclient-in-dotnet?utm_source=Twitter&utm_medium=social&utm_campaign=01.04.2024
author: Milan Jovanović
title: 在 .NET 中正确使用 HttpClient 的方式
description: 了解如何在 .NET 中正确使用 HttpClient
---

> ## 摘要
>
> 原文 [The Right Way To Use HttpClient In .NET](https://www.milanjovanovic.tech/blog/the-right-way-to-use-httpclient-in-dotnet?utm_source=Twitter&utm_medium=social&utm_campaign=01.04.2024)

---

如果您正在构建一个 **.NET** 应用程序，那么您很可能需要通过 **HTTP** 调用一个 **外部 API**。

在 .NET 中发送 HTTP 请求的简便方法是使用 `HttpClient`。它是一个很棒的抽象工具，尤其是支持 **JSON** 载荷和响应的方法。

不幸的是，很容易误用 `HttpClient`。

**端口耗尽** 和 **DNS 行为** 是一些最常见的问题。

因此，这里有一些关于使用 `HttpClient` 需要知道的事情：

- 如何不使用 `HttpClient`
- 如何使用 `IHttpClientFactory` 简化配置
- 如何配置 **类型化客户端**
- 为什么在单例服务中避免使用 **类型化客户端**
- 何时使用哪个选项

让我们深入了解！

## 使用 HttpClient 的初学者方式

使用 `HttpClient` 的最简单方法就是创建一个新实例，设置所需的属性，并使用它来发送请求。

可能会出现什么问题呢？

`HttpClient` 实例应该是 **长期存活的**，并且在应用程序的生命周期内重复使用。

每个实例都使用自己的 **连接池** 出于隔离目的，但也是为了防止 **端口耗尽**。如果服务器负载很高，而您的应用程序不断地创建新连接，可能会导致可用端口耗尽。在尝试发送请求时，这将在运行时导致异常。

那么，如何避免这个问题呢？

```csharp
public class GitHubService
{
    private readonly GitHubSettings _settings;

    public GitHubService(IOptions<GitHubSettings> settings)
    {
        _settings = settings.Value;
    }

    public async Task<GitHubUser?> GetUserAsync(string username)
    {
        var client = new HttpClient();

        client.DefaultRequestHeaders.Add("Authorization", _settings.GitHubToken);
        client.DefaultRequestHeaders.Add("User-Agent", _settings.UserAgent);
        client.BaseAddress = new Uri("https://api.github.com");

        GitHubUser? user = await client
            .GetFromJsonAsync<GitHubUser>($"users/{username}");

        return user;
    }
}
```

## 使用 IHttpClientFactory 智能创建 HttpClient

您可以使用 `IHttpClientFactory` 来创建 `HttpClient` 实例，而不用自己管理 `HttpClient` 的生命周期。

只需调用 `CreateClient` 方法，并使用返回的 `HttpClient` 实例来发送您的 HTTP 请求。

为什么这是一个更好的方法呢？

`HttpClient` 的开销大的部分是实际的消息处理器 - `HttpMessageHandler`。每个 `HttpMessageHandler` 都有一个内部的 HTTP **连接池**，可以重用。

`IHttpClientFactory` 将 **缓存** `HttpMessageHandler` 并在创建新的 `HttpClient` 实例时重用它。

这里的一个重要说明是通过 `IHttpClientFactory` 创建的 `HttpClient` 实例是意味着 **短暂存活** 的。

```csharp
public class GitHubService
{
    private readonly GitHubSettings _settings;
    private readonly IHttpClientFactory _factory;

    public GitHubService(
        IOptions<GitHubSettings> settings,
        IHttpClientFactory factory)
    {
        _settings = settings.Value;
        _factory = factory;
    }

    public async Task<GitHubUser?> GetUserAsync(string username)
    {
        var client = _factory.CreateClient();

        client.DefaultRequestHeaders.Add("Authorization", _settings.GitHubToken);
        client.DefaultRequestHeaders.Add("User-Agent", _settings.UserAgent);
        client.BaseAddress = new Uri("https://api.github.com");

        GitHubUser? user = await client
            .GetFromJsonAsync<GitHubUser>($"users/{username}");

        return user;
    }
}
```

## 通过命名客户端减少代码重复

使用 `IHttpClientFactory` 可以解决手动创建 `HttpClient` 的大部分问题。然而，我们仍然需要在每次从 `CreateClient` 方法获取新的 `HttpClient` 时配置默认的请求参数。

你可以通过调用 `AddHttpClient` 方法，并传递所需名称来配置一个 **命名客户端**。`AddHttpClient` 接受一个委托，您可以使用它来配置 `HttpClient` 实例上的默认参数。

```csharp
services.AddHttpClient("github", (serviceProvider, client) =>
{
    var settings = serviceProvider
        .GetRequiredService<IOptions<GitHubSettings>>().Value;

    client.DefaultRequestHeaders.Add("Authorization", settings.GitHubToken);
    client.DefaultRequestHeaders.Add("User-Agent", settings.UserAgent);

    client.BaseAddress = new Uri("https://api.github.com");
});
```

主要区别在于，您现在需要通过传递客户端的名称来获取客户端。

但使用 `HttpClient` 看起来简单多了：

```csharp
public class GitHubService
{
    private readonly IHttpClientFactory _factory;

    public GitHubService(IHttpClientFactory factory)
    {
        _factory = factory;
    }

    public async Task<GitHubUser?> GetUserAsync(string username)
    {
        var client = _factory.CreateClient("github");

        GitHubUser? user = await client
            .GetFromJsonAsync<GitHubUser>($"users/{username}");

        return user;
    }
}
```

## 用类型化客户端取代命名客户端

使用 **命名客户端** 的缺点是每次都需要通过传递名称来解析一个 `HttpClient`。

有一个更好的方法可以通过配置一个 **类型化客户端** 来实现相同的行为。你可以通过调用 `AddClient<TClient>` 方法，并配置将使用 `HttpClient` 的服务来做到这一点。

在底层，这仍然是使用一个 **命名客户端**，其中名称与类型名称相同。

这也会注册 `GitHubService` 为 **瞬态生命周期**。

```csharp
services.AddHttpClient<GitHubService>((serviceProvider, client) =>
{
    var settings = serviceProvider
        .GetRequiredService<IOptions<GitHubSettings>>().Value;

    client.DefaultRequestHeaders.Add("Authorization", settings.GitHubToken);
    client.DefaultRequestHeaders.Add("User-Agent", settings.UserAgent);

    client.BaseAddress = new Uri("https://api.github.com");
});
```

在 `GitHubService` 内，您注入并使用已应用所有配置的类型化 `HttpClient` 实例。

不再需要处理 `IHttpClientFactory` 和手动创建 `HttpClient` 实例。

```csharp
public class GitHubService
{
    private readonly HttpClient client;

    public GitHubService(HttpClient client)
    {
        _client = client;
    }

    public async Task<GitHubUser?> GetUserAsync(string username)
    {
        GitHubUser? user = await client
            .GetFromJsonAsync<GitHubUser>($"users/{username}");

        return user;
    }
}
```

## 为什么应该避免在单例服务中使用类型化客户端

如果您将 **类型化客户端** 注入到一个 **单例服务** 中，可能会遇到一个 **问题**。由于 **类型化客户端** 是 **瞬态的**，将其注入 **单例服务** 会导致它在 **单例服务** 的生命周期内被缓存。

这将阻止 **类型化客户端** 响应 DNS 变化。

如果您想在 **单例服务** 中使用 **类型化客户端**，推荐的方法是使用 `SocketsHttpHandler` 作为主处理器，并配置 `PooledConnectionLifetime`。

由于 `SocketsHttpHandler` 将处理连接池，您可以通过将 `HandlerLifetime` 设置为 `Timeout.InfiniteTimeSpan` 来禁用在 `IHttpClientFactory` 级别的循环。

```csharp
services.AddHttpClient<GitHubService>((serviceProvider, client) =>
{
    var settings = serviceProvider
        .GetRequiredService<IOptions<GitHubSettings>>().Value;

    client.DefaultRequestHeaders.Add("Authorization", settings.GitHubToken);
    client.DefaultRequestHeaders.Add("User-Agent", settings.UserAgent);

    client.BaseAddress = new Uri("https://api.github.com");
})
.ConfigurePrimaryHttpMessageHandler(() =>
{
    return new SocketsHttpHandler()
    {
        PooledConnectionLifetime = TimeSpan.FromMinutes(15)
    };
})
.SetHandlerLifetime(Timeout.InfiniteTimeSpan);
```

## 应该在什么时候使用哪个选项？

我向您展示了使用 `HttpClient` 的几个可能的选项。

但您应该在什么时候使用哪个呢？

微软很好地为我们提供了一套最佳实践和 [`HttpClient` 的推荐使用](https://learn.microsoft.com/zh-cn/dotnet/fundamentals/networking/http/httpclient-guidelines#recommended-use)指南。

- 使用配置了 `PooledConnectionLifetime` 的 `static` 或 **单例** `HttpClient` 实例，因为这解决了端口耗尽和跟踪 DNS 变化的问题
- 如果您想将配置移动到一个地方，但记住客户端应该是 **短暂存活** 的，可以使用 `IHttpClientFactory`
- 如果您希望 `IHttpClientFactory` 的可配置性，可以使用 **类型化客户端**

我更喜欢使用 **类型化客户端**，并且我知道它被配置为 **瞬态服务**。

---
