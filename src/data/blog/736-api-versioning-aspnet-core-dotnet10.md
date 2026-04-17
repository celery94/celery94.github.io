---
pubDatetime: 2026-04-15T09:16:00+08:00
title: "ASP.NET Core API 版本管理完全指南（.NET 10）"
description: "每个 API 迟早都会有破坏性变更。本文讲清楚为什么要做 API 版本管理，如何区分破坏性与非破坏性变更，并用 .NET 10 Minimal API 的完整代码演示从配置到废弃再到迁移的全流程。"
tags: [".NET", "ASP.NET Core", "API", "C#"]
slug: "api-versioning-aspnet-core-dotnet10"
ogImage: "../../assets/736/01-cover.png"
source: "https://thecodeman.net/posts/why-do-you-need-api-versioning"
---

![ASP.NET Core API 版本管理](../../assets/736/01-cover.png)

API 版本管理是那种你可以忽略的事——但只能忽略一次。

第一次遇到生产事故，因为一个"小小的响应字段改动"导致移动端应用崩溃、合作方集成凌晨三点报警，每个团队都会说同一句话："我们当初应该做版本管理。"

Stefan Đokić（微软 MVP）在这篇文章里把他在多个生产项目中用的那套方案完整写了出来：从概念到代码，从废弃策略到迁移 Playbook。本文基于 .NET 10 Minimal API。

## 什么是 API 版本管理

做版本管理之前，先搞清楚你在版本化什么。

一个 API 版本代表一份**契约**。这份契约包含：

- 端点路径和 HTTP 方法
- 请求体结构（字段名、类型、必填/可选）
- 响应体结构
- 查询参数名和行为
- 状态码及其含义
- 认证与授权规则

当这些内容有任何改动让现有客户端无法处理时，就是**破坏性变更**，就需要新版本。

版本管理让你可以发布新契约（v2）的同时保留旧契约（v1）继续运行，消费方按自己的节奏迁移，而不是被你强制同步升级。

## 为什么需要版本管理

几个实际理由：

- **向后兼容**：六个月前的移动端 App 在新版本发布时依然能正常工作
- **更安全的部署**：上线 v2 不需要逼所有客户端当天同步更新
- **并行开发**：前端团队继续用 v1，后端团队同时开发 v2
- **清晰的生命周期**：可以将 v1 标记为废弃、设置下线日期、等流量归零后再删除
- **合作方信任**：外部消费方需要知道他们的集成不会随时被打破

如果你的 API 不是完全由你控制的单个前端在消费，版本管理就不是可选项。

## 破坏性变更 vs. 非破坏性变更

这是最重要的判断：**这个改动需要新版本吗？**

### 破坏性变更（需要新版本）

- 从响应中删除一个字段
- 重命名字段
- 更改字段的数据类型（例如 `string` → `int`）
- 更改字段含义（例如 `price` 从分改为元）
- 将原本可选的请求字段改为必填
- 更改已有流程的状态码行为
- 删除或重命名端点
- 更改认证要求

### 非破坏性变更（保持同一版本）

- 在响应中添加新的可选字段
- 添加新端点
- 添加新的可选查询参数
- 在不改变契约的前提下优化性能
- 修复不影响文档行为的 Bug

一个简单的判断标准：**昨天还能正常工作的客户端，今天因为你的改动坏掉了，那就是破坏性变更。**

## 版本策略对比

有几种常见的 API 版本策略：

| 策略 | 示例 | 优点 | 缺点 |
|------|------|------|------|
| URL 段 | `/api/v1/products` | 易读，便于测试、缓存、文档 | URL 随版本变化 |
| 查询字符串 | `/api/products?api-version=1.0` | URL 基本稳定 | 容易遗漏，污染查询参数 |
| 请求头 | `X-Api-Version: 1.0` | URL 完全稳定 | 隐蔽，测试和发现困难 |
| 媒体类型 | `Accept: application/vnd.myapi.v1+json` | 符合 HTTP 规范 | 复杂，工具支持参差不齐 |

2026 年的建议：**用 URL 段版本管理，只做主版本**（v1、v2）。

原因：在日志、链路追踪、浏览器开发者工具里一眼可见；Swagger/OpenAPI 集成干净；curl、Postman 或任何 HTTP 客户端都很容易测；CDN 和缓存天然工作，因为不同版本 URL 不同；新来的团队成员能立刻看清他们在调哪个版本。

## 项目配置

安装三个 NuGet 包：

```bash
dotnet add package Asp.Versioning.Http
dotnet add package Asp.Versioning.Mvc.ApiExplorer
dotnet add package Swashbuckle.AspNetCore
```

- `Asp.Versioning.Http`：Minimal API 版本管理的核心包
- `Asp.Versioning.Mvc.ApiExplorer`：启用 Swagger 集成
- `Swashbuckle.AspNetCore`：生成 OpenAPI 文档和 Swagger UI

## Minimal API 版本管理：完整实现

### 第一步：配置版本管理服务

```csharp
using Asp.Versioning;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddApiVersioning(options =>
{
    options.DefaultApiVersion = new ApiVersion(1, 0);
    options.AssumeDefaultVersionWhenUnspecified = true;
    options.ReportApiVersions = true;
    options.ApiVersionReader = new UrlSegmentApiVersionReader();
})
.AddApiExplorer(options =>
{
    options.GroupNameFormat = "'v'VVV";
    options.SubstituteApiVersionInUrl = true;
});

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();
```

每个配置项的作用：

- `DefaultApiVersion`：请求未指定版本时默认使用 v1.0
- `AssumeDefaultVersionWhenUnspecified`：无版本请求自动匹配默认版本
- `ReportApiVersions`：自动在响应头中加入 `api-supported-versions` 和 `api-deprecated-versions`
- `UrlSegmentApiVersionReader`：从 URL 路径段读取版本（`/api/v1/...`）
- `GroupNameFormat`：在 API Explorer 中将版本格式化为 `v1`、`v2`
- `SubstituteApiVersionInUrl`：在 Swagger 中把路由模板里的 `{version:apiVersion}` 替换为实际版本号

### 第二步：创建版本集合

版本集合定义你的 API 支持哪些版本，创建一个后在各端点组中共享：

```csharp
var apiVersionSet = app.NewApiVersionSet()
    .HasApiVersion(new ApiVersion(1, 0))
    .HasApiVersion(new ApiVersion(2, 0))
    .ReportApiVersions()
    .Build();
```

这告诉框架：我的 API 有 v1 和 v2，两者都在响应头中报告。

### 第三步：定义 v1 端点

```csharp
var productsV1 = app.MapGroup("/api/v{version:apiVersion}/products")
    .WithApiVersionSet(apiVersionSet)
    .MapToApiVersion(1, 0);

productsV1.MapGet("", async (AppDbContext db) =>
{
    var products = await db.Products
        .Select(p => new ProductResponseV1(p.Id, p.Name, p.Price))
        .ToListAsync();
    return Results.Ok(products);
})
.WithName("GetProductsV1")
.WithSummary("Get all products")
.WithDescription("Returns all products with basic details.");

productsV1.MapGet("/{id:int}", async (int id, AppDbContext db) =>
{
    var product = await db.Products.FindAsync(id);
    if (product is null) return Results.NotFound();
    return Results.Ok(new ProductResponseV1(product.Id, product.Name, product.Price));
})
.WithName("GetProductByIdV1")
.WithSummary("Get product by ID");

public record ProductResponseV1(int Id, string Name, decimal Price);
```

v1 返回简单响应：ID、名称、价格。

### 第四步：定义 v2 端点（不同的契约）

假设 v2 需要包含货币、分类和可用性信息：

```csharp
var productsV2 = app.MapGroup("/api/v{version:apiVersion}/products")
    .WithApiVersionSet(apiVersionSet)
    .MapToApiVersion(2, 0);

productsV2.MapGet("", async (AppDbContext db) =>
{
    var products = await db.Products
        .Select(p => new ProductResponseV2(
            p.Id, p.Name, p.Price, p.Currency, p.Category, p.IsAvailable))
        .ToListAsync();
    return Results.Ok(products);
})
.WithName("GetProductsV2")
.WithSummary("Get all products (v2)")
.WithDescription("Returns all products with extended details including currency and availability.");

public record ProductResponseV2(
    int Id,
    string Name,
    decimal Price,
    string Currency,
    string Category,
    bool IsAvailable);
```

相同的端点路径，不同的响应契约，两者同时运行——这就是版本管理。

### 第五步：启动应用

```csharp
app.UseSwagger();
app.UseSwaggerUI();

app.Run();
```

调用 `GET /api/v1/products` 得到 v1 响应，调用 `GET /api/v2/products` 得到 v2 响应。响应头会包含：

```
api-supported-versions: 1.0, 2.0
```

## 大规模项目的端点组织方式

真实项目里，你不会想把 200 行端点映射全堆在 `Program.cs`。把版本化的端点提取成扩展方法：

```csharp
public static class ProductEndpoints
{
    public static void MapProductEndpointsV1(
        this IEndpointRouteBuilder app,
        ApiVersionSet apiVersionSet)
    {
        var group = app.MapGroup("/api/v{version:apiVersion}/products")
            .WithApiVersionSet(apiVersionSet)
            .MapToApiVersion(1, 0)
            .WithTags("Products");

        group.MapGet("", GetAllV1).WithName("GetProductsV1");
        group.MapGet("/{id:int}", GetByIdV1).WithName("GetProductByIdV1");
        group.MapPost("", CreateV1).WithName("CreateProductV1");
    }

    public static void MapProductEndpointsV2(
        this IEndpointRouteBuilder app,
        ApiVersionSet apiVersionSet)
    {
        var group = app.MapGroup("/api/v{version:apiVersion}/products")
            .WithApiVersionSet(apiVersionSet)
            .MapToApiVersion(2, 0)
            .WithTags("Products");

        group.MapGet("", GetAllV2).WithName("GetProductsV2");
        group.MapGet("/{id:int}", GetByIdV2).WithName("GetProductByIdV2");
        group.MapPost("", CreateV2).WithName("CreateProductV2");
    }

    // 处理方法...
    private static async Task<IResult> GetAllV1(AppDbContext db) { /* ... */ }
    private static async Task<IResult> GetAllV2(AppDbContext db) { /* ... */ }
    // ...
}
```

然后在 `Program.cs` 中：

```csharp
app.MapProductEndpointsV1(apiVersionSet);
app.MapProductEndpointsV2(apiVersionSet);

app.Run();
```

两行代码，`Program.cs` 保持整洁。每个版本的端点在各自的方法里，易查找、易测试、废弃时也好删。

## 废弃一个版本

准备废弃 v1 时，在版本集合中将其标记为已废弃：

```csharp
var apiVersionSet = app.NewApiVersionSet()
    .HasDeprecatedApiVersion(new ApiVersion(1, 0))
    .HasApiVersion(new ApiVersion(2, 0))
    .ReportApiVersions()
    .Build();
```

注意：`HasApiVersion` 改成了 `HasDeprecatedApiVersion`。

现在每个 v1 响应都会包含：

```
api-deprecated-versions: 1.0
api-supported-versions: 2.0
```

检查响应头的客户端（优秀的 API 消费方都会这样做）能自动收到废弃信号。

### 添加 Sunset 头

为了传达更明确的下线时间，用中间件添加 Sunset 日期头：

```csharp
app.Use(async (context, next) =>
{
    await next();

    var apiVersion = context.GetRequestedApiVersion();
    if (apiVersion?.MajorVersion == 1)
    {
        context.Response.Headers["Sunset"] = "Sat, 01 Nov 2026 00:00:00 GMT";
        context.Response.Headers["Deprecation"] = "true";
        context.Response.Headers["Link"] =
            "</api/v2/products>; rel=\"successor-version\"";
    }
});
```

这告诉每个 v1 消费方："这个版本将在 2026 年 11 月 1 日下线，替代版本在这里。"明确、机器可读、不容错过。

## 每个版本独立的 Swagger 文档

把所有版本混在同一个 Swagger 页面很混乱。配置独立的 Swagger 文档：

```csharp
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "Products API",
        Version = "v1",
        Description = "Legacy product endpoints. Deprecated - migrate to v2."
    });

    options.SwaggerDoc("v2", new OpenApiInfo
    {
        Title = "Products API",
        Version = "v2",
        Description = "Current product endpoints with extended product details."
    });
});
```

以及中间件配置：

```csharp
app.UseSwagger();
app.UseSwaggerUI(options =>
{
    options.SwaggerEndpoint("/swagger/v1/swagger.json", "Products API v1 (Deprecated)");
    options.SwaggerEndpoint("/swagger/v2/swagger.json", "Products API v2");
});
```

现在访问 Swagger UI 的开发者能看到清晰的下拉列表：v1（已废弃）和 v2（当前）。

## Header 版本管理备选方案

有些团队倾向于 Header 版本管理，因为 URL 在版本间保持稳定。切换方式：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.DefaultApiVersion = new ApiVersion(1, 0);
    options.AssumeDefaultVersionWhenUnspecified = true;
    options.ReportApiVersions = true;
    options.ApiVersionReader = new HeaderApiVersionReader("X-Api-Version");
});
```

此时两个版本的 URL 都是 `/api/products`，客户端通过请求头指定版本：

```
GET /api/products
X-Api-Version: 2.0
```

**适合使用 Header 版本管理的场景：**
- CDN 或反向代理无法处理基于 URL 的路由
- 与合作方的 API 契约要求基于 Header 的版本管理
- 需要跨版本保持 URL 可缓存性

**应该避免的场景：**
- 消费方包含浏览器端应用（Header 更难设置）
- 团队经常通过浏览器地址栏或 curl 测试
- 需要最大化文档可发现性

### 同时支持多种读取方式

也可以同时支持 URL 段和 Header 两种方式：

```csharp
options.ApiVersionReader = ApiVersionReader.Combine(
    new UrlSegmentApiVersionReader(),
    new HeaderApiVersionReader("X-Api-Version")
);
```

客户端可以选择任意一种方式，URL 段优先级更高。

## 测试版本化端点

在集成测试中测试版本化 API 非常直接，调用版本特定的 URL，断言响应契约：

```csharp
public class ProductsApiTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public ProductsApiTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task GetProducts_V1_ReturnsBasicFields()
    {
        var response = await _client.GetAsync("/api/v1/products");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var products = await response.Content
            .ReadFromJsonAsync<List<ProductResponseV1>>();

        products.Should().NotBeEmpty();
        products![0].Id.Should().BeGreaterThan(0);
        products[0].Name.Should().NotBeNullOrEmpty();
    }

    [Fact]
    public async Task GetProducts_V2_ReturnsExtendedFields()
    {
        var response = await _client.GetAsync("/api/v2/products");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var products = await response.Content
            .ReadFromJsonAsync<List<ProductResponseV2>>();

        products.Should().NotBeEmpty();
        products![0].Currency.Should().NotBeNullOrEmpty();
        products[0].Category.Should().NotBeNullOrEmpty();
    }

    [Fact]
    public async Task V1_Response_Headers_Show_Deprecation()
    {
        var response = await _client.GetAsync("/api/v1/products");

        response.Headers.Should().ContainKey("api-deprecated-versions");
    }
}
```

关键测试策略：
- 用各自的响应契约独立测试每个版本
- 断言废弃版本的响应头存在
- 测试不支持的版本返回 4xx 错误
- 测试未指定版本时的默认版本行为

## 迁移 Playbook：v1 到 v2

在多个项目中运行版本化 API 之后，固定的迁移流程如下：

**第一阶段：构建并发布 v2**
- 用新契约构建 v2 端点
- v1 和 v2 并行部署
- 更新 Swagger 文档展示两个版本
- 编写迁移文档，说明变更内容和原因

**第二阶段：宣告废弃**
- 在版本集合中将 v1 标记为废弃（`HasDeprecatedApiVersion`）
- 添加 Sunset 头，设置具体日期（至少 3-6 个月后）
- 通过邮件、变更日志或 API 门户通知消费方
- 在 Swagger UI 描述中添加废弃提示

**第三阶段：监控与支持**
- 按客户端/API Key 记录 v1 使用量
- 主动联系高流量 v1 消费方
- 提供迁移支持
- 冻结 v1——只修安全补丁，不加新功能

**第四阶段：退役 v1**
- 当 v1 流量接近零（或到达下线日期），删除 v1 端点
- 在过渡期内对剩余 v1 请求返回 `410 Gone`
- 清理 v1 响应模型、处理方法和测试

最常见的错误：团队构建了 v2，宣告了废弃，然后就再也没有真正删除 v1。几年后维护着 4 个版本，毫无退役计划。**定好日期，执行到底。**

## 常见错误

**版本管理太晚**：等到有 20 个客户端依赖未版本化 API 时才开始，意味着所有人都要经历痛苦的迁移。

**破坏性变更不创建新版本**：在 v1 里悄悄重命名字段，寄希望于没人注意，这是一次有保障的生产事故。

**每次变更都创建新版本**：添加一个可选字段不需要 v3，版本只用于真正的破坏性变更。

**没有下线策略**：如果从不退役旧版本，你就是在永远维护多条代码路径。

**没有使用量追踪**：不知道谁还在调用 v1，就没办法安全地下线它。

**资源间版本不一致**：如果 `/products` 已经是 v2 但 `/orders` 还在 v1，消费方很快就会困惑。整个 API 应该一起版本化。

**不记录变更差异**：v1 到 v2 之间的变更日志是必要的，消费方需要知道究竟改了什么。

## 小结

API 版本管理是你可以忽略的事——但只能忽略一次。

第一次生产事故之后，每个团队都会希望从第一天就搭好这套基础设施。

好消息是：用 `Asp.Versioning.Http` 和 .NET 10 Minimal API，搭建过程并不复杂。你能得到基于 URL 的版本管理、自动废弃响应头、每版本独立的 Swagger 文档，以及保持 `Program.cs` 整洁的扩展方法模式。

建议：**从第一天就设置版本管理**，哪怕只有 v1。基础设施成本极低，等到已经有客户端依赖未版本化 API 之后再补，代价极高。

从 URL 段版本管理开始，只做主版本，用 Header 和日期废弃，积极执行下线计划。

## 参考

- [原文：Why You Need API Versioning in ASP.NET Core (.NET 10)](https://thecodeman.net/posts/why-do-you-need-api-versioning)
- [Asp.Versioning NuGet 包](https://www.nuget.org/packages/Asp.Versioning.Http)
