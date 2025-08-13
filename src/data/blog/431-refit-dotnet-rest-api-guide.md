---
pubDatetime: 2025-08-13
tags: ["dotnet", "refit", "rest-api", "csharp"]
slug: refit-dotnet-rest-api-guide
source: https://thecodeman.net/posts/refit-the-dotnet-rest-api-you-should-know-about
title: Refit：让 .NET REST API 调用更简单高效的利器
description: 介绍 Refit 这个 .NET REST API 客户端库的功能与用法，结合 GitHub API 示例讲解其在减少样板代码、提升可维护性和测试性方面的优势，并分析在 .NET 8 环境中的集成实践。
---

---

# Refit：让 .NET REST API 调用更简单高效的利器

在 .NET 开发中，如果提到调用 REST API，大多数人第一反应是 `HttpClient`。它功能强大，几乎无处不在，但你可能并不知道，有一个更优雅、实现成本更低的选择——**Refit**。

## 什么是 Refit？

[Refit](https://github.com/reactiveui/refit) 是一个适用于 .NET 的 REST API 客户端库，它允许你通过**接口定义 API**，并用特性（Attributes）描述 HTTP 请求细节。
它构建在 `System.Net.Http.HttpClient` 之上，自动处理 JSON 的序列化与反序列化，让你只需关注业务逻辑本身。

在传统方式下，你需要创建类、手动构建 URL、处理 HTTP 请求和响应。而在 Refit 中，你只需定义接口，剩下的由它自动生成，开发体验大大简化。

## GitHub API 示例

以 GitHub 公共 API 为例，下面展示如何快速构建一个获取用户信息的客户端。

### 步骤 1：安装 NuGet 包

```bash
dotnet add package Refit.HttpClientFactory
```

### 步骤 2：定义 API 接口

创建 `IGitHubApi.cs`：

```csharp
using Refit;
using System.Threading.Tasks;

public interface IGitHubApi
{
    [Get("/users/{username}")]
    Task<GitHubUser> GetUserAsync(string username);
}
```

这里 `[Get]` 表明这是一个 HTTP GET 请求，`{username}` 会被动态替换为方法参数。

### 步骤 3：定义数据模型

创建 `GitHubUser.cs`：

```csharp
public class GitHubUser
{
    public string Login { get; set; }
    public string Name { get; set; }
    public string Company { get; set; }
    public int Followers { get; set; }
    public int Following { get; set; }
    public string AvatarUrl { get; set; }
}
```

该类映射了 GitHub API 返回的 JSON 字段。

### 步骤 4：配置依赖注入

在 `Program.cs` 中：

```csharp
builder.Services.AddRefitClient<IGitHubApi>()
    .ConfigureHttpClient((sp, client) =>
    {
        var settings = sp.GetRequiredService<IOptions<GitHubSettings>>().Value;
        client.BaseAddress = new Uri(settings.BaseAddress);
        client.DefaultRequestHeaders.Add("Authorization", settings.AccessToken);
        client.DefaultRequestHeaders.Add("User-Agent", settings.UserAgent);
    });
```

这样 `IGitHubApi` 会作为一个 **Typed Client** 被注册，并由 Refit 自动生成实现。

调用方式也很简洁：

```csharp
var user = await gitHubService.GetUserAsync("StefanTheCode");
```

## 与传统 HttpClient 对比

如果使用 `HttpClient`，你需要写类似这样的实现：

```csharp
public class GitHubApiClient : IGitHubApi
{
    private readonly HttpClient _httpClient;
    public GitHubApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
        _httpClient.BaseAddress = new Uri("https://api.github.com");
    }
    public async Task<GitHubUser> GetUserAsync(string username)
    {
        var response = await _httpClient.GetAsync($"/users/{username}");
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<GitHubUser>();
    }
}
```

相比之下，Refit 只需接口定义即可完成同样的工作，省去了冗余的样板代码。

## 在 .NET 8 中的优势

在 .NET 8 中，Refit 的优势更加明显：

- **代码可读性高**：接口定义与业务逻辑分离，清晰直观。
- **易于测试**：接口天然适合 Mock，便于单元测试。
- **无缝集成**：支持依赖注入、`HttpClientFactory`、多种序列化选项。

得益于 .NET 8 在性能与语言特性上的提升，Refit 与其结合能够实现更高效、可维护的 API 调用方案。

## 总结

Refit 让 .NET 开发者以最小的样板代码构建功能齐全的 REST API 客户端。在几行代码内，就能实现调用 GitHub API 并获取用户数据的功能。对于追求开发效率与代码整洁度的团队而言，它绝对值得一试。

如果你还没用过，不妨泡杯咖啡，动手试一下 Refit 的简洁之美。
