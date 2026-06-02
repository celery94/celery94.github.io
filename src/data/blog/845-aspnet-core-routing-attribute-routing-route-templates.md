---
pubDatetime: 2026-06-02T07:45:14+08:00
title: "ASP.NET Core 路由：把 URL 稳定交给正确的端点"
description: "这篇文章梳理 ASP.NET Core 路由的关键概念：attribute routing、route templates、constraints、参数绑定和 URL 生成，帮助你减少 404、路由冲突和硬编码链接。"
tags: ["ASP.NET Core", "CSharp", "Web API"]
slug: "aspnet-core-routing-attribute-routing-route-templates"
ogImage: "../../assets/845/01-cover.png"
source: "https://www.devleader.ca/2026/05/31/aspnet-core-routing-attribute-routing-route-templates-and-constraints"
---

ASP.NET Core Routing 负责把一个 HTTP 请求交给正确的处理代码。你可以把它理解成一张请求地图：URL、HTTP 方法、route template、constraint 和 endpoint metadata 共同决定请求会进入哪个 controller action、minimal API handler 或 Razor Page。

这篇基于 Dev Leader 的路由文章，并补充 Microsoft Learn 的官方说明，重点看 Web API 最常遇到的几件事：attribute routing 怎么组织 URL，route template 怎么表达参数，constraint 为什么会导致 404，以及怎样用 `CreatedAtAction` 和 `LinkGenerator` 避免到处手写路径。

## 路由做了什么

现代 ASP.NET Core 的路由可以拆成两个阶段：

- route matching：根据 URL、HTTP 方法和已注册的 endpoint 找候选项。
- endpoint execution：执行匹配到的 handler。

这个拆分很有用。放在匹配与执行之间的 middleware，可以读取已经匹配到的 endpoint metadata，然后再决定是否继续。例如授权、限流、缓存都可以看 endpoint 上的元数据，在业务代码运行前做处理。

在较新的 minimal hosting 写法里，常见应用调用 `app.MapControllers()` 或 `app.MapGet(...)` 后，框架会接好常规的 endpoint routing。老项目里常见的 `UseRouting()` 与 `UseEndpoints()` 仍然存在，遇到复杂 middleware 顺序时也还能显式配置。

## 两种写法

ASP.NET Core 里常见两种路由组织方式。

Conventional routing 把模板集中写在 `Program.cs`，例如：

```csharp
app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");
```

这类写法适合 MVC 页面项目。框架会从 URL 片段推断 controller 与 action，比如 `/products/detail/5` 对应 `ProductsController.Detail(5)`。

Web API 更常用 attribute routing。路由直接写在 controller 和 action 上，读代码时就能看到 API 入口。

```csharp
[ApiController]
[Route("api/[controller]")]
public class OrdersController : ControllerBase
{
    [HttpGet]
    public IActionResult GetAll() => Ok(Array.Empty<object>());

    [HttpGet("{id:guid}")]
    public IActionResult GetById(Guid id) => Ok(new { Id = id });

    [HttpPost]
    public IActionResult Create([FromBody] CreateOrderRequest request)
        => CreatedAtAction(nameof(GetById), new { id = Guid.NewGuid() }, request);
}

public record CreateOrderRequest(string CustomerId, decimal Total);
```

这里的 `[controller]` 会被替换成 controller 名称去掉 `Controller` 后缀。`OrdersController` 对应的基础路径就是 `/api/orders`。方法上的 `[HttpGet("{id:guid}")]` 会追加到基础路径后面。

一个细节要记住：action 上的 route template 如果以 `/` 开头，它会变成绝对路径，不再拼接 controller 上的基础路径。

## 模板表达路径

Route template 是路由的形状。它可以包含固定片段、参数、可选参数、默认值和 catch-all 参数。

常见写法如下：

- `{id}`：从当前位置取一个 URL 片段并绑定到同名参数。
- `{id?}`：可选片段，缺失时使用类型默认值。
- `{version=1}`：片段缺失时使用默认值 `1`。
- `{**path}`：catch-all 参数，匹配零个或多个路径片段，包含 `/`。

例如一个 catalog API 可以这样表达版本号、分类路径和分页查询：

```csharp
[ApiController]
[Route("api/v{version:int}/[controller]")]
public class CatalogController : ControllerBase
{
    [HttpGet("categories/{**categoryPath}")]
    public IActionResult BrowseCategory(int version, string categoryPath)
        => Ok(new { Version = version, Path = categoryPath });

    [HttpGet("items")]
    public IActionResult ListItems(
        int version,
        [FromQuery] int page = 1,
        [FromQuery] int size = 20)
        => Ok(new { Version = version, Page = page, Size = size });
}
```

路径参数适合表达资源本身，例如订单 ID、文章 ID、分类路径。查询参数适合表达筛选、排序和分页。这个区分能让 URL 更容易理解，也方便客户端长期使用。

## 约束只管匹配

Route constraint 的作用是限制某个 route parameter 能匹配什么值。比如：

- `{id:int}` 只匹配整数。
- `{id:guid}` 只匹配 GUID。
- `{id:int:min(1)}` 要求先是整数，再要求不小于 1。
- `{slug:regex(^[a-z0-9-]+$)}` 用正则限制 slug 形状。

最容易踩坑的点是：constraint 参与的是路由匹配。它失败时，这条路由会被当作不匹配，常见结果是 `404 Not Found`。如果你希望客户端传错值时返回 `400 Bad Request`，应该使用 model validation，例如 Data Annotations 或 FluentValidation。

这个区别会直接影响 API 设计。constraint 适合做结构判断，例如区分 `{id:int}` 和 `{slug}`，也适合让路由选择更明确。业务规则应放在 action 或 service 里，例如“这个 product ID 是否存在”“用户是否能访问这个订单”。

```csharp
[ApiController]
[Route("api/products")]
public class ProductsController : ControllerBase
{
    [HttpGet("{id:int:min(1)}")]
    public IActionResult GetByIntId(int id)
        => Ok(new { Id = id, Source = "integer lookup" });

    [HttpGet("by-slug/{slug:regex(^[[a-z0-9-]]+$)}")]
    public IActionResult GetBySlug(string slug)
        => Ok(new { Slug = slug });

    [HttpGet("{id:guid}")]
    public IActionResult GetByGuid(Guid id)
        => Ok(new { Id = id, Source = "guid lookup" });
}
```

上面正则里的 `[[a-z0-9-]]` 是 C# attribute 字符串里的写法，用来转义 route template 中的方括号。最终正则表达的含义仍是 `[a-z0-9-]`。

## 自定义约束要克制

内置 constraint 不够用时，可以实现 `IRouteConstraint`。原文给了一个 version constraint 的例子，用 `v1`、`v2`、`v3` 限制版本片段：

```csharp
public sealed class VersionConstraint : IRouteConstraint
{
    private static readonly string[] SupportedVersions = ["v1", "v2", "v3"];

    public bool Match(
        HttpContext? httpContext,
        IRouter? route,
        string routeKey,
        RouteValueDictionary values,
        RouteDirection routeDirection)
    {
        if (!values.TryGetValue(routeKey, out var value))
        {
            return false;
        }

        var version = value?.ToString()?.ToLowerInvariant();
        return SupportedVersions.Contains(version);
    }
}
```

注册时把名称加入 `RouteOptions.ConstraintMap`：

```csharp
builder.Services.Configure<RouteOptions>(options =>
{
    options.ConstraintMap.Add("supportedVersion", typeof(VersionConstraint));
});
```

然后就能在模板里使用：

```csharp
[Route("api/{version:supportedVersion}/[controller]")]
```

这里要保持克制。constraint 会在路由匹配阶段执行，应该快速、无副作用，避免数据库访问、网络请求或复杂业务判断。Microsoft Learn 也提醒，自定义 constraint 并不常见，写之前应先考虑 model binding 或 validation 是否更合适。

## 参数从哪里来

在 `[ApiController]` 下，ASP.NET Core 会推断大部分参数来源：

- route template 里出现的简单类型参数，通常来自 `[FromRoute]`。
- 没出现在 route template 里的简单类型参数，通常来自 `[FromQuery]`。
- 复杂类型通常来自 `[FromBody]`。

必要时可以显式写出来，减少误解：

```csharp
[HttpGet("{id:int}")]
public IActionResult Get(
    [FromRoute] int id,
    [FromQuery] bool includeItems = false,
    [FromHeader(Name = "X-Correlation-Id")] string? correlationId = null)
{
    return Ok(new { id, includeItems, correlationId });
}
```

显式标注在几种场景里很有帮助：参数名和 route token 不一致，需要读取 header，或者团队希望 API 签名更清楚。

## 少手写 URL

创建资源时，API 通常需要返回 `201 Created`，并在 `Location` header 里放新资源地址。ASP.NET Core 里常用 `CreatedAtAction`：

```csharp
[HttpPost]
public IActionResult Create([FromBody] CreateArticleRequest request)
{
    var newId = 42;

    return CreatedAtAction(
        nameof(GetById),
        new { id = newId },
        new { Id = newId, request.Title });
}
```

如果你在 middleware、后台服务、事件处理器里生成 URL，可以注入 `LinkGenerator`。它不依赖 controller context，适合在 controller 外部使用。

```csharp
public sealed class ArticleLinkBuilder(LinkGenerator links)
{
    public string? GetArticlePath(HttpContext context, int id)
    {
        return links.GetPathByAction(
            httpContext: context,
            action: "GetById",
            controller: "Articles",
            values: new { id });
    }
}
```

这样做的好处很直接：URL 跟着路由定义走。以后调整 template，生成链接的代码不需要散落修改。

## 冲突怎么处理

多个路由都可能匹配时，ASP.NET Core 会按更具体的规则排序。一般来说：

- 固定片段比参数片段更具体。
- 带 constraint 的参数比不带 constraint 的参数更具体。
- HTTP method constraint 会参与匹配，例如 `GET /api/products` 和 `POST /api/products` 是两个不同入口。

如果两条路由对框架来说无法区分，就可能在运行时遇到 `AmbiguousMatchException`。常见修法有三种：给参数加类型约束，增加固定片段，或者重新整理路由层级。

```csharp
[HttpGet("{id:int}")]
public IActionResult GetById(int id) => Ok();

[HttpGet("by-slug/{slug}")]
public IActionResult GetBySlug(string slug) => Ok();
```

这类写法比同时使用 `[HttpGet("{value}")]` 更清楚，调用方和框架都少猜一次。

## .NET 10 相关变化

原文提到 .NET 10 对 ASP.NET Core 路由层有一些渐进改进。结合 Microsoft Learn 当前文档，可以重点关注两点：

- `Microsoft.AspNetCore.OpenApi` 会读取 routing metadata 来生成 OpenAPI 文档，.NET 10 还加入了 OpenAPI 3.1 文档支持。
- `RouteGroupBuilder` 在 minimal APIs 中用于共享 route prefix、认证策略和 metadata，适合把相关 endpoint 放到同一组里。

如果你主要写 controller-based Web API，attribute routing 仍然是日常主线。minimal API 项目则可以用 route groups 把一组 endpoint 的共同规则集中起来。

## 实践建议

写 ASP.NET Core Web API 路由时，可以按这几个判断检查：

- controller 上放稳定的资源前缀，例如 `api/orders`。
- action 上只补动作所需的路径片段，例如 `{id:guid}`、`{id:guid}/items`。
- route parameter 表达资源身份，query string 表达筛选、排序和分页。
- constraint 用来区分路由形状，输入错误用 validation 返回 400。
- 创建资源时使用 `CreatedAtAction` 或 `CreatedAtRoute` 返回 `Location`。
- controller 外生成链接时优先看 `LinkGenerator`。

这些点不复杂，但能减少大量难查的 404、路径冲突和硬编码 URL。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享清楚、可复用的工具教程、技术观察和项目经验。

## 参考

- [ASP.NET Core Routing: Attribute Routing, Route Templates, and Constraints](https://www.devleader.ca/2026/05/31/aspnet-core-routing-attribute-routing-route-templates-and-constraints)
- [Routing in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/routing)
- [Routing to controller actions in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/mvc/controllers/routing)
- [Overview of OpenAPI support in ASP.NET Core API apps](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/openapi/overview)
- [What's new in ASP.NET Core in .NET 10](https://learn.microsoft.com/en-us/aspnet/core/whats-new/)
