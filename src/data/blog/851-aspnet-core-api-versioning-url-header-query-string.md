---
pubDatetime: 2026-06-05T07:51:20+08:00
title: "ASP.NET Core API 版本管理：URL、Header 和 Query String 怎么选"
description: "ASP.NET Core 没有内置完整 API versioning，常见做法是用 Asp.Versioning.Mvc。本文用原文示例梳理 URL segment、query string、header、组合读取器、版本废弃和 OpenAPI 分版本文档的配置方法。"
tags: ["ASP.NET Core", ".NET", "Web API", "API Versioning", "OpenAPI"]
slug: "aspnet-core-api-versioning-url-header-query-string"
ogImage: "../../assets/851/01-cover.png"
source: "https://www.devleader.ca/2026/06/04/api-versioning-in-aspnet-core-url-header-and-query-string-strategies"
---

API 一旦被外部客户端使用，版本管理就不再是“以后再说”的装饰。移动端、第三方集成、合作方系统都可能依赖某个响应字段、某个状态码，或者某个 URL 形态。后端要演进，又不能把旧客户端一次性打断，这就是 API versioning 的价值。

Dev Leader 这篇文章讲的是在 .NET 10 的 ASP.NET Core 项目里，用 `Asp.Versioning.Mvc` 做控制器 API 的版本管理。它把常见策略讲得很完整：URL segment、query string、header、多个 reader 组合、`[MapToApiVersion]`、版本废弃，以及 Swagger/OpenAPI 的多版本文档。

## 先装包

ASP.NET Core 本身不直接提供这套完整的 controller API versioning 能力。原文使用的是第三方包 `Asp.Versioning.Mvc`，它是早期 `Microsoft.AspNetCore.Mvc.Versioning` 迁移到独立项目后的延续。

如果还要让 Swagger/OpenAPI 按版本生成文档，需要同时安装 `Asp.Versioning.Mvc.ApiExplorer`：

```bash
dotnet add package Asp.Versioning.Mvc
dotnet add package Asp.Versioning.Mvc.ApiExplorer
```

基础配置通常放在 `Program.cs`：

```csharp
using Asp.Versioning;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

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

var app = builder.Build();

app.UseRouting();
app.UseAuthorization();
app.MapControllers();

app.Run();
```

这里有三个配置尤其常用。

- `DefaultApiVersion`：没有明确版本时，系统退回哪个版本。
- `AssumeDefaultVersionWhenUnspecified = true`：旧客户端没传版本时，不直接返回错误，而是按默认版本处理。
- `ReportApiVersions = true`：响应里带上 `api-supported-versions` 和 `api-deprecated-versions`，方便客户端知道支持和废弃情况。

## URL 路径版本

URL segment versioning 是最直观的一种方式。版本直接出现在路径里，例如：

```text
/api/v1/products
/api/v2/products
```

它的优点是可见、好测试、日志里也清楚。看到 `/api/v2/orders`，基本不用再查 header 或 query string，就知道请求落在哪个版本上。缺点是 URL 会随版本变化，对非常强调稳定资源标识的团队来说可能不够优雅。

控制器写法通常是把版本放到 route template 里：

```csharp
[ApiController]
[ApiVersion("1.0")]
[Route("api/v{version:apiVersion}/products")]
public sealed class ProductsV1Controller : ControllerBase
{
    [HttpGet]
    public IActionResult GetAll()
    {
        // v1 返回较扁平的字段
        return Ok(new[]
        {
            new { Id = 1, Name = "Keyboard", Price = 99 }
        });
    }
}

[ApiController]
[ApiVersion("2.0")]
[Route("api/v{version:apiVersion}/products")]
public sealed class ProductsV2Controller : ControllerBase
{
    [HttpGet]
    public IActionResult GetAll()
    {
        // v2 可以加入类别、库存、可售状态等新字段
        return Ok(new[]
        {
            new
            {
                Id = 1,
                Name = "Keyboard",
                Price = 99,
                CategoryId = 10,
                StockQuantity = 42,
                IsAvailable = true
            }
        });
    }
}
```

原文推荐把 v1 和 v2 做成独立 controller，这是最干净的方式。版本之间差异变大时，各自维护自己的行为，比在一个方法里塞很多兼容判断更容易读。

## Query String 版本

Query string versioning 把版本放到 URL 参数里：

```text
/api/products?api-version=1.0
```

这种方式保留了基础路径 `/api/products`，对已有 API 改造更温和。配置时把 reader 换成 `QueryStringApiVersionReader`：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.DefaultApiVersion = new ApiVersion(1, 0);
    options.AssumeDefaultVersionWhenUnspecified = true;
    options.ReportApiVersions = true;
    options.ApiVersionReader =
        new QueryStringApiVersionReader("api-version");
});

[ApiController]
[ApiVersion("1.0")]
[Route("api/products")]
public sealed class ProductsController : ControllerBase
{
    // ...
}
```

默认参数名常用 `api-version`。如果团队已有约定，也可以改成别的名字。需要注意的是，v1 和 v2 的 route 可能相同，框架会根据 `[ApiVersion]` 和 query string 的值来区分最终 action。

## Header 版本

Header versioning 把版本放到 HTTP header 里，常见名字是 `X-Api-Version`：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.DefaultApiVersion = new ApiVersion(1, 0);
    options.AssumeDefaultVersionWhenUnspecified = true;
    options.ReportApiVersions = true;
    options.ApiVersionReader =
        new HeaderApiVersionReader("X-Api-Version");
});
```

它的好处是 URL 保持干净，版本更像协议层面的协商信息。它也很适合 API gateway 场景：网关可以根据规则注入、改写或转发版本 header。

缺点也明显。浏览器里直接访问不方便，Postman、curl 或 SDK 都要额外设置 header。对公开 API 来说，header 版本通常不如 URL 路径版本容易被新用户发现。

## 同时支持多种入口

迁移期经常会遇到多个客户端习惯不同。有的已经用了 `/api/v1`，有的更容易加 query string，有的流量经过网关适合 header。这时可以用 `ApiVersionReader.Combine()`：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.DefaultApiVersion = new ApiVersion(1, 0);
    options.AssumeDefaultVersionWhenUnspecified = true;
    options.ReportApiVersions = true;
    options.ApiVersionReader = ApiVersionReader.Combine(
        new UrlSegmentApiVersionReader(),
        new QueryStringApiVersionReader("api-version"),
        new HeaderApiVersionReader("X-Api-Version")
    );
});
```

原文提到，如果多个 reader 都读到了版本，框架会按配置顺序处理。实际项目里要把这个顺序写进团队约定，否则排查问题时会出现“明明 header 是 v2，为什么走了 URL 里的 v1”这类困惑。

## 一个控制器多版本

如果两个版本差异很小，可以把多个版本放在一个 controller 里，用 `[MapToApiVersion]` 区分不同 action：

```csharp
[ApiController]
[ApiVersion("1.0")]
[ApiVersion("2.0")]
[Route("api/v{version:apiVersion}/orders")]
public sealed class OrdersController : ControllerBase
{
    [HttpGet]
    public IActionResult GetAll()
    {
        // v1 和 v2 共享行为
        return Ok();
    }

    [HttpGet("{id:int}")]
    [MapToApiVersion("1.0")]
    public IActionResult GetByIdV1(int id)
    {
        return Ok(new { Id = id, Status = "Paid", Total = 199 });
    }

    [HttpGet("{id:int}")]
    [MapToApiVersion("2.0")]
    public IActionResult GetByIdV2(int id)
    {
        return Ok(new
        {
            Id = id,
            Status = "Paid",
            Total = 199,
            LineItems = Array.Empty<object>(),
            Shipping = new { Method = "Standard" }
        });
    }
}
```

这个模式适合差异很小的版本。如果 v2 的业务逻辑、依赖服务、DTO、权限规则都开始明显不同，把 controller 拆开会更稳。

## 标记废弃版本

版本管理不只是“加一个 v2”。还要告诉客户端：v1 还在，但它已经进入迁移期。

`[ApiVersion]` 可以用 `Deprecated = true` 标记废弃版本：

```csharp
[ApiVersion("1.0", Deprecated = true)]
[ApiVersion("2.0")]
[Route("api/v{version:apiVersion}/customers")]
public sealed class CustomersController : ControllerBase
{
    // ...
}
```

配合 `ReportApiVersions = true`，响应会包含支持版本和废弃版本的信息。技术上这只是一个信号，真正让迁移顺利的仍然是文档、changelog、迁移窗口和对重要客户的通知。原文 FAQ 里也提到，常见 sunset window 可以是六到十二个月，具体还要看你的客户端类型和业务约束。

## OpenAPI 分版本

多个 API 版本如果还挤在一份 Swagger 文档里，读者会很难判断哪个 endpoint 属于哪个版本。原文把这里拆成三块：

- `Microsoft.AspNetCore.OpenApi`：ASP.NET Core 的 OpenAPI metadata。
- Swashbuckle：第三方 Swagger UI 和 `SwaggerGen`。
- `Asp.Versioning.Mvc.ApiExplorer`：让 API explorer 理解版本分组。

典型做法是为每个版本生成一份 Swagger doc，并在 Swagger UI 里提供版本切换：

```csharp
using Asp.Versioning.ApiExplorer;
using Microsoft.Extensions.Options;
using Microsoft.OpenApi.Models;
using Swashbuckle.AspNetCore.SwaggerGen;

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.ConfigureOptions<ConfigureSwaggerOptions>();

var app = builder.Build();

app.UseSwagger();
app.UseSwaggerUI(options =>
{
    var provider =
        app.Services.GetRequiredService<IApiVersionDescriptionProvider>();

    foreach (var description in provider.ApiVersionDescriptions)
    {
        options.SwaggerEndpoint(
            $"/swagger/{description.GroupName}/swagger.json",
            $"My API {description.GroupName.ToUpperInvariant()}");
    }
});

public sealed class ConfigureSwaggerOptions
    : IConfigureNamedOptions<SwaggerGenOptions>
{
    private readonly IApiVersionDescriptionProvider _provider;

    public ConfigureSwaggerOptions(
        IApiVersionDescriptionProvider provider)
    {
        _provider = provider;
    }

    public void Configure(SwaggerGenOptions options)
    {
        foreach (var description in _provider.ApiVersionDescriptions)
        {
            options.SwaggerDoc(
                description.GroupName,
                new OpenApiInfo
                {
                    Title = "My API",
                    Version = description.ApiVersion.ToString(),
                    Description = description.IsDeprecated
                        ? "This API version is deprecated."
                        : "Current stable version."
                });
        }
    }

    public void Configure(string? name, SwaggerGenOptions options) =>
        Configure(options);
}
```

这样 Swagger UI 会按版本展示 endpoint。v1 看 v1 的接口，v2 看 v2 的接口，废弃版本也可以在 `OpenApiInfo.Description` 里明确提醒。

## 迁移旧 API

给已有 API 加 versioning 时，最怕的是旧客户端突然全挂。原文的建议很实用：把默认版本设成当前已有行为对应的版本，比如 v1，并打开 `AssumeDefaultVersionWhenUnspecified`。

这样没有传版本的旧请求仍然按 v1 处理。之后你可以逐步加 v2、新文档和迁移说明，而不是强迫所有客户端同一天改 URL 或 header。

一个比较稳的落地顺序是：

1. 给现有 controller 标上 `[ApiVersion("1.0")]`。
2. 设置 `DefaultApiVersion = new ApiVersion(1, 0)`。
3. 开启 `AssumeDefaultVersionWhenUnspecified = true`。
4. 开启 `ReportApiVersions = true`。
5. 新增 v2 controller 或 `[MapToApiVersion("2.0")]`。
6. 给 OpenAPI 加版本分组。
7. 等客户端迁移后，再把 v1 标记为 deprecated。

## 怎么选

如果没有特殊约束，URL segment 是最容易起步的默认选择。它清楚、好调试、文档里也醒目。

Query string 更适合不想改基础路径、或者对已有客户端做温和迁移的场景。Header 更适合 API gateway、内部服务或更重视 URL 稳定性的系统。组合 reader 适合迁移期，但要明确优先级，避免多个版本来源打架。

版本管理的目的不是制造更多路由，而是让 breaking change 有地方落地，让旧客户端有迁移时间，让文档能清楚告诉调用方“你现在用的是哪一版”。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [API Versioning in ASP.NET Core: URL, Header, and Query String Strategies](https://www.devleader.ca/2026/06/04/api-versioning-in-aspnet-core-url-header-and-query-string-strategies)
