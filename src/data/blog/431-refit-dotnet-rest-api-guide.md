---
pubDatetime: 2025-08-13
tags: [".NET", "ASP.NET Core", "C#"]
slug: refit-dotnet-rest-api-guide
source: https://thecodeman.net/posts/refit-the-dotnet-rest-api-you-should-know-about
title: Refit：让 .NET REST API 调用更简单高效的利器
description: 介绍 Refit 这个 .NET REST API 客户端库的功能与用法，结合 GitHub API 示例讲解其在减少样板代码、提升可维护性和测试性方面的优势，并分析在 .NET 8 环境中的集成实践。
---

---

# Refit：让 .NET REST API 调用更简单高效的利器

在 .NET 开发中，调用 REST API 是常见需求，通常开发者会直接使用功能强大的 `HttpClient`。它虽然灵活但涉及大量样板代码，如手动拼接 URL、序列化请求体、解析响应等。

而 [Refit](https://github.com/reactiveui/refit) 提供了更优雅且低成本的解决方案，它让你通过定义接口并使用特性（Attributes）声明 HTTP 请求而自动生成客户端代码，极大简化了调用流程。

## 什么是 Refit？

Refit 是基于 `System.Net.Http.HttpClient` 的一个 REST API 客户端库。
它自动承担 JSON 序列化与反序列化任务，你只关心接口定义和业务逻辑。

传统调用 REST API 需要你编写具体实现、构造请求、解析响应，而 Refit 仅需声明接口定义，自动生成实现，显著减少重复代码并提升开发效率。它同时兼容同步调用、异步调用、以及支持 CancellationToken。

此设计提高了代码的可读性和可测试性，方便替换 Mock，且完美结合依赖注入与 .NET HttpClientFactory 机制，利于构建现代化的网络调用架构。

适用场景包括微服务调用、第三方 API 整合、跨平台客户端与服务端接口封装。特别适合团队中注重开发效率和代码质量的项目。

此外，Refit 也支持多种序列化库插件（如 System.Text.Json、Newtonsoft.Json），灵活满足不同项目需求。

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

在 `Program.cs` 或者 .NET 8 `Startup` 配置中集成 Refit：

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

这里将 `IGitHubApi` 注册为 **Typed Client**，由 Refit 自动实现接口。结合依赖注入后，调用接口代理简洁方便：

```csharp
var user = await gitHubService.GetUserAsync("StefanTheCode");
```

### 传统 HttpClient 调用示例对比

使用常规 `HttpClient`，你需要手动管理 HTTP 请求和响应，写大量样板代码：

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

相比之下，使用 Refit 只需声明接口即可完成相同的功能，极大减少了样板代码，维护成本更低。

## 在 .NET 8 中的优势

在 .NET 8 中，Refit 的优势更为突出，结合新语言特性与性能提升，带来：

- **更简洁直观的接口定义**：利用 C# 11 及以上版本的增强特性，接口定义更清晰。
- **高效的 HttpClientFactory 集成**：可通过依赖注入灵活配置，支持多种生命周期管理。
- **增强的测试友好性**：接口天然支持 Mock 优化，无需复杂手工编写测试桩。
- **支持最新序列化机制**：完美兼容 System.Text.Json、Newtonsoft.Json 等不同序列化方案。
- **性能优化**：借助 .NET 8 的性能改进，减少调用开销，响应更快。

### 集成示例

```csharp
builder.Services.AddRefitClient<IGitHubApi>()
    .ConfigureHttpClient(client =>
    {
        client.BaseAddress = new Uri("https://api.github.com");
        client.DefaultRequestHeaders.Add("User-Agent", "MyApp");
    });
```

通过上述方式，借助 .NET 8 框架，Refit 能带来更流畅与易维护的 REST API 调用体验。

## 高级特性及示例

Refit 的高级功能使其适合复杂的 REST API 调用场景，下面配合示例介绍常用特性：

- **自定义请求配置**

  支持在接口方法中使用 `[Headers]` 添加统一请求头，方法参数中用 `[Header]` 动态设置请求头。

  ```csharp
  public interface IApi
  {
      [Get("/items")]
      [Headers("Cache-Control: no-cache")]
      Task<List<Item>> GetItemsAsync([Header("Authorization")] string authToken);
  }
  ```

- **多种 HTTP 动词支持**

  除 `[Get]` 外，支持 `[Post]`、`[Put]`、`[Delete]`、`[Patch]`。

  ```csharp
  public interface IApi
  {
      [Post("/items")]
      Task<Item> CreateItemAsync([Body] Item newItem);

      [Patch("/items/{id}")]
      Task<Item> UpdateItemAsync(int id, [Body] JsonPatchDocument<Item> patchDoc);

      [Delete("/items/{id}")]
      Task DeleteItemAsync(int id);
  }
  ```

- **强大的路由参数**

  支持复杂的路径参数，多参数自动替换。

  ```csharp
  [Get("/users/{userId}/orders/{orderId}")]
  Task<Order> GetOrderAsync(int userId, int orderId);
  ```

- **请求取消支持**

  支持方法中传入 `CancellationToken`，优雅取消长时间运行请求。

  ```csharp
  Task<List<Item>> GetItemsAsync(CancellationToken cancellationToken);
  ```

- **请求拦截器**

  通过自定义 DelegatingHandler，可拦截请求和响应，进行日志、身份验证等处理。

  ```csharp
  public class LoggingHandler : DelegatingHandler
  {
      protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
      {
          Console.WriteLine($"Request: {request}");
          var response = await base.SendAsync(request, cancellationToken);
          Console.WriteLine($"Response: {response}");
          return response;
      }
  }

  // 注册
  builder.Services.AddRefitClient<IApi>()
      .AddHttpMessageHandler<LoggingHandler>();
  ```

- **序列化器切换**

  支持替换默认的 JSON 解析器为 Newtonsoft.Json 等。

  ```csharp
  builder.Services.AddRefitClient<IApi>()
      .ConfigureHttpClient(c => c.BaseAddress = new Uri("https://example.com"))
      .AddHttpMessageHandler(() => new NewtonsoftJsonContentSerializer());
  ```

- **高级重试与超时**

  可结合 Polly 实现智能重试和超时保护。

  ```csharp
  builder.Services.AddRefitClient<IApi>()
      .AddPolicyHandler(Policy.TimeoutAsync<HttpResponseMessage>(TimeSpan.FromSeconds(10)))
      .AddTransientHttpErrorPolicy(p => p.WaitAndRetryAsync(3, _ => TimeSpan.FromSeconds(2)));
  ```

- **多样体上传下载**

  支持 Multipart 文件上传、表单数据等。

  ```csharp
  [Multipart]
  [Post("/upload")]
  Task<Response> UploadFileAsync([AliasAs("file")] StreamPart file);

  [Post("/submit-form")]
  Task SubmitFormAsync([Body(BodySerializationMethod.UrlEncoded)] Dictionary<string, string> form);
  ```

- **接口继承与泛型支持**

  允许接口继承，支持泛型接口定义，便于复用通用接口。

  ```csharp
  public interface IBaseApi<T>
  {
      [Get("/items")] Task<List<T>> GetAllAsync();
  }
  public interface IProductApi : IBaseApi<Product> { }
  ```

- **扩展能力强**

  虽然 Refit 主要面向 HTTP/1.1 REST，支持通过自定义扩展适配 HTTP2、WebSocket 以及其他协议实现。

## 从 OpenAPI JSON 生成接口

对于大型 API 或频繁更新的服务，手动维护接口很费力。可以通过 OpenAPI JSON 规范自动生成 Refit 接口代码。

### 使用 NSwag 或 OpenAPI Generator

- [NSwag](https://github.com/RicoSuter/NSwag) 和 [OpenAPI Generator](https://openapi-generator.tech/) 是常用的工具，可以根据 OpenAPI 规范生成 C# 客户端，部分生成的代码可配合 Refit 使用。

### 示例

假设有 OpenAPI JSON 描述的 GitHub API，可以通过 NSwag CLI 生成客户端：

```bash
nswag openapi2csclient /input:https://api.github.com/swagger.json /classname:GitHubApiClient /namespace:YourNamespace /generateDtoTypes:true /useRefit:true /output:GitHubApiClient.cs
```

### 生成接口用法

- 生成的代码内包含接口定义（带 Refit 特性）和 DTO 类。
- 直接将接口注册为 Refit Client，并注入使用。

```csharp
builder.Services.AddRefitClient<IGitHubApi>()
    .ConfigureHttpClient(c => c.BaseAddress = new Uri("https://api.github.com"));

var api = sp.GetRequiredService<IGitHubApi>();
var user = await api.GetUserAsync("username");
```

### 注意事项

- 生成代码需根据项目需求调整命名空间和类名。
- 可结合现有测试和构建流程自动生成，保证接口定义实时同步。
- OpenAPI 规范支持丰富，需关注生成的请求和响应模型是否满足当前 API 版本。

通过这种方式，极大降低手工维护接口代码成本，提升开发效率和准确性。

## 总结

以上示例展示了 Refit 的高级灵活使用方式，帮助你在实际项目中更高效地管理复杂 API 调用需求。
