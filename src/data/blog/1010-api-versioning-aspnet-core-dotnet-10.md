---
pubDatetime: 2026-08-20T14:03:00+08:00
title: "ASP.NET Core API 版本化实战（.NET 10）"
description: ".NET 10 下用 Asp.Versioning 10.2 给 API 做版本化：URL 段与请求头怎么选、控制器与 Minimal API 两种写法、每版本 OpenAPI 文档、字段级版本化与 Sunset 头，附完整代码与最佳实践。"
tags: [".NET", "ASP.NET Core", "API", "Versioning"]
slug: "api-versioning-aspnet-core-dotnet-10"
ogImage: "../../assets/1010/01-cover.jpg"
source: "https://codewithmukesh.com/blog/api-versioning-in-aspnet-core/"
---

Code with Mukesh（Mukesh Murugan，Microsoft MVP）在 2026 年 8 月发表了《API Versioning in ASP.NET Core - The .NET 10 Guide》，是它的「.NET Web API Zero to Hero」课程第 54 课。这篇教程把 .NET 10 上 API 版本化的正确做法讲得很完整，而且包含了 2026 年 8 月刚发布的新能力——这篇文章把它整理成一份可以照着做的中文指南。

要解决的问题：你的 API 上线后，客户端已经把接口写死了。当你要重命名字段、删掉属性、收紧校验规则时，一次破坏性变更就会静默打断所有线上集成。API 版本化让同一个端点的多个版本并行运行：v1 客户端继续用 v1，你发布形状不同的 v2，两者都正常工作。

读完这篇，你会得到：四种种版本策略的决策矩阵和默认选择、控制器与 Minimal API 两套完整写法、每版本一份 OpenAPI 文档的接入方式、10.2 新增的字段级版本化，以及正确的弃用流程（Sunset 头）。所有代码都基于 .NET 10.0.303 构建运行过，完整源码在 GitHub。

## 前置条件

- **.NET 10 SDK**，创建 Web API 项目
- NuGet 包 **Asp.Versioning** 10.2 系列（各包当前版本见下文）
- 内置 OpenAPI 文档（`Microsoft.AspNetCore.OpenApi`）+ Scalar 作为交互 UI

先说一个绝大多数教程（包括把您带到这篇文章的那篇）都讲错的地方：**不要装 `Microsoft.AspNetCore.Mvc.Versioning`**。这个包在 v6.0（2022 年末）改名了——去掉 `Microsoft.` 前缀变成 `Asp.Versioning.*`，因为项目不再是微软维护的包（现在是社区维护，仓库仍挂在 dotnet org 下）。v10 是第一个为 .NET 10 及其原生 OpenAPI 支持构建的版本。如果你的教程还在教在 `Startup.cs` 里调 `AddApiVersioning`，它教的是 2020 年。

另一个更新的信息差：**Asp.Versioning 10.2 于 2026 年 8 月 6 日发布**，带来一个根本性变化——可以只给单个字段做版本化，而不用创建新的端点版本。这包括下面要讲的 `[VisibleInApiVersion]`，以及默认开启的 31 个 Roslyn 分析器。

## 触发条件：什么是破坏性变更

版本化的触发条件永远是**破坏性变更**。新增一个可选字段是安全的，不需要新版本；删除字段、重命名字段、改变类型、收紧校验、改变错误契约——这些才是破坏性的，才是新版本存在的意义。团队应该把「什么算破坏性变更」写下来，因为一半的「要不要开新版本」争论，本质是「这算不算破坏性变更」的争论。

## 四种版本策略怎么选

Asp.Versioning 通过 `ApiVersionReader` 支持四种主流策略。这个选择比看起来重要，因为客户端会把方案写死，之后切换方案会搞坏所有人——这是一次性决策。

| 策略       | 示例                             | 可见性             | 缓存友好                           | 易测试                 | 结论                         |
| ---------- | -------------------------------- | ------------------ | ---------------------------------- | ---------------------- | ---------------------------- |
| URL 段     | `/api/v1/products`               | 最高，版本在路径里 | 是，URL 不同缓存干净               | 是，粘贴 URL 即可      | 公开 REST API 的默认         |
| 查询字符串 | `/api/products?api-version=1.0`  | 中                 | 基本可以，部分代理缓存键忽略 query | 是                     | 内部 API 可以，公开 API 难看 |
| HTTP 头    | `X-API-Version: 1.0`             | 低，URL 里看不到   | 否，所有版本同 URL                 | 否，需要工具而非浏览器 | URL 干净，但有测试税         |
| 媒体类型   | `Accept: application/json;v=2.0` | 低                 | 否                                 | 否                     | 最「RESTful」，摩擦最大      |

作者的结论：**公开 REST API 默认用 URL 段版本化**，除非你有具体理由。它最容易被发现、新开发者最容易理解、对 CDN 和 HTTP 缓存最友好，而且是唯一能直接粘贴到浏览器测试的方式。「URL 应该永久，所以版本应该放在 header 里」的论点理论上很纯粹，实践上是个支持负担——你会把省下的 URL 美感花在「为什么我的请求打到了错误的版本」的工单上。Header 和媒体类型版本化适合内部或超媒体驱动、客户端足够老练且有工具支撑的 API。

## 选包：按宿主模型挑

当前（2026 年 8 月）的包和版本：

| 包                             | 用途                                 | 版本   |
| ------------------------------ | ------------------------------------ | ------ |
| Asp.Versioning.Http            | Minimal APIs                         | 10.2.2 |
| Asp.Versioning.Mvc             | 控制器                               | 10.2.1 |
| Asp.Versioning.Mvc.ApiExplorer | OpenAPI 元数据（两种模型都用）       | 10.2.1 |
| Asp.Versioning.OpenApi         | 每版本一份文档 + OpenAPI 里的 Sunset | 10.2.2 |

```bash
# Minimal APIs
dotnet add package Asp.Versioning.Http --version 10.2.2
dotnet add package Asp.Versioning.Mvc.ApiExplorer --version 10.2.1
dotnet add package Asp.Versioning.OpenApi --version 10.2.2

# Controllers
dotnet add package Asp.Versioning.Mvc --version 10.2.1
dotnet add package Asp.Versioning.Mvc.ApiExplorer --version 10.2.1
dotnet add package Asp.Versioning.OpenApi --version 10.2.2
```

一个值得指出的修正：**Asp.Versioning.OpenApi 现在已经 GA 了**。它在 `10.0.0-rc.1` 上待了好几个月，这就是为什么官方 .NET 博客和所有第三方文章都还让你装预发布版。它在 10.2 系列转正，OpenAPI 集成不再需要 prerelease 标记。

## 在 .NET 10 里配置版本化

注册是一整条流式链，这是作者作为公开 API 基线的配置：默认版本、显式 reader、合理的 reporting、API Explorer 加 OpenAPI 全部接好。

```csharp
using Asp.Versioning;

var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddApiVersioning(options =>
    {
        // Treat 1.0 as the version when a client does not ask for one.
        options.DefaultApiVersion = new ApiVersion(1, 0);
        // Advertise supported + deprecated versions in response headers.
        options.ReportApiVersions = true;
        // Read the version from the URL segment only.
        options.ApiVersionReader = new UrlSegmentApiVersionReader();
    })
    .AddApiExplorer(options =>
    {
        // Formats groups as "v1", "v2" - matches the /openapi/v1.json convention.
        options.GroupNameFormat = "'v'VVV";
        options.SubstituteApiVersionInUrl = true;
    })
    .AddOpenApi();
```

几个决定真实流量下行为的选项值得理解而不是复制粘贴：

- **DefaultApiVersion**：请求没指定版本时用的版本。新 API 从 `1.0` 开始。
- **ReportApiVersions = true**：响应头加上 `api-supported-versions` 和 `api-deprecated-versions`。配合结构化日志可以看到客户端实际在调哪个版本，保持开启。
- **ApiVersionReader**：指定读取版本的唯一来源。显式设置比默认更快——默认每个请求都同时探测查询字符串和 URL 段。库自带的分析器也会提醒你，它是对的。
- **GroupNameFormat = "'v'VVV"**：控制版本在 OpenAPI 里的显示。`VVV` 把 `1.0` 折叠成 `v1`，`1.1` 保持 `v1.1`。
- **.AddOpenApi()**：Asp.Versioning.OpenApi 的挂载点，让下一节变成一行调用而不是手写循环。

一个 10.2 起的行为变化：`AddApiVersioning()` 现在会帮你注册 `IHttpContextAccessor`——字段级版本化需要它在序列化期间拿到请求的版本，这是它能工作的前提。

### 换 reader：Header 或多方案

想用 header，或同时接受几种，就替换 `ApiVersionReader`：

```csharp
// Header-only versioning
options.ApiVersionReader = new HeaderApiVersionReader("X-API-Version");

// Accept URL segment, query string, AND header (most forgiving)
options.ApiVersionReader = ApiVersionReader.Combine(
    new UrlSegmentApiVersionReader(),
    new QueryStringApiVersionReader("api-version"),
    new HeaderApiVersionReader("X-API-Version"));
```

`ApiVersionReader.Combine` 在迁移期间很方便，但别把「永久支持一切」当姿态发布出去。选定你希望客户端用的那一种、写进文档，并承担单个 reader 更小的每请求成本。

### AssumeDefaultVersionWhenUnspecified 该开吗

很多教程习惯性设置 `AssumeDefaultVersionWhenUnspecified = true`。它让未指定版本的请求回退到 `DefaultApiVersion`，听起来无害。

但它不是作者会默认使用的选项。它存在的意义是**给已有调用者、正在打未版本化 URL 的 API 做回填**。在新 API 上，它掩盖了 reader 配错的问题：客户端发了你根本没接的版本，reader 找不到，请求不返回明确的 404，而是悄悄落在 v1 上。几个月后你才发现「v2 集成返回的是 v1 的数据」。Asp.Versioning 10.2 用分析器 AV0016 专门标记这种情况。有遗留调用者要保护时再开，别凭反射开。

## 版本化控制器

控制器用特性声明版本，路由模板携带版本段。下面是同一个应用里 `ProductsController` 的两个版本：

```csharp
using Asp.Versioning;
using Microsoft.AspNetCore.Mvc;
using Versioning.Controllers.Models;

namespace Versioning.Controllers.Controllers;

[ApiController]
[ApiVersion("1.0", Deprecated = true)]
[ApiVersion("2.0")]
[Route("api/v{version:apiVersion}/[controller]")]
public class ProductsController : ControllerBase
{
    private static readonly Product[] Catalog =
    [
        new() { Id = 1, Name = "Keyboard", Price = 79.00m, Sku = "KB-001", LegacyCategory = "Peripherals" },
        new() { Id = 2, Name = "Mouse", Price = 39.00m, Sku = "MS-002", LegacyCategory = "Peripherals" }
    ];

    [HttpGet]
    [MapToApiVersion("1.0")]
    public ActionResult<Product[]> GetV1() => Ok(Catalog);

    [HttpGet]
    [MapToApiVersion("2.0")]
    public ActionResult<ProductListResponse> GetV2() =>
        Ok(new ProductListResponse(Catalog, Catalog.Length));
}
```

`[ApiVersion]` 声明这个控制器服务哪些版本；`{version:apiVersion}` 路由约束从 URL 里取出版本；`[MapToApiVersion]` 把每个方法路由到对应版本，于是 `GET /api/v1/products` 命中 `GetV1`，`GET /api/v2/products` 命中 `GetV2`。v2 把载荷包进带 count 的信封而不是返回裸数组——这种形状变化正是第二个版本存在的意义。

版本多了之后，把控制器拆到 `Controllers/V1` 和 `Controllers/V2` 文件夹更整洁。版本来自特性而不是命名空间，所以文件夹纯粹是给自己看的。

## 版本化 Minimal API

Minimal API 通过 `NewVersionedApi` 创建命名版本组，然后每个版本挂一个路由组，在组上声明版本：

```csharp
var productsApi = app.NewVersionedApi("Products");

var productsV1 = productsApi
    .MapGroup("api/v{version:apiVersion}/products")
    .HasDeprecatedApiVersion(1.0);

var productsV2 = productsApi
    .MapGroup("api/v{version:apiVersion}/products")
    .HasApiVersion(2.0);

productsV1.MapGet("/", () => TypedResults.Ok(catalog));

productsV2.MapGet("/", () =>
    TypedResults.Ok(new ProductListResponse(catalog, catalog.Length)));
```

`NewVersionedApi("Products")` 声明版本化 API 并给它一个会出现在 OpenAPI 文档里的名字。每个 `MapGroup` 用 `HasApiVersion` 声明自己的版本，快退出的版本用 `HasDeprecatedApiVersion`。组路由里的 `{version:apiVersion}` 段让它变成 URL 段版本化。

这比大多数旧文章里 `NewApiVersionSet()` + `WithApiVersionSet()` + `MapToApiVersion()` 的组合读起来好得多。那套 API 仍然能用，但在组上声明版本意味着每个版本的端点各自成块，而不是一个 handler 一个 handler 地消歧。

这里用 `TypedResults` 而不是 `Results` 不是装饰：类型化重载告诉 OpenAPI 响应 schema，否则生成的文档 `components.schemas` 是空的。

## 让 OpenAPI 和 Scalar 显示版本

这是其他教程跳过或搞砸的部分，也是让你的版本化 API 真正可用的关键。.NET 10 里 OpenAPI 文档由内置的 `Microsoft.AspNetCore.OpenApi` 生成，`Asp.Versioning.OpenApi` 把版本元数据桥接进去。

有了注册链里的 `.AddOpenApi()`，每版本一份文档只是一行调用：

```csharp
app.MapOpenApi().WithDocumentPerVersion();
```

`WithDocumentPerVersion()` 枚举应用实际暴露的版本，注册 `/openapi/v1.json`、`/openapi/v2.json` 等，文档之间没有交叉污染——v1 文档只含 v1 的路径。

如果你见过 `foreach` 循环遍历 `DescribeApiVersions()` 再逐版本调 `MapOpenApi()`，那是这个包转正之前的 workaround，现在不需要了。

把 Scalar 指向每个版本，文档 UI 就有版本切换器而不是一个合并的大 blob：

```csharp
app.MapScalarApiReference(options =>
{
    var descriptions = app.DescribeApiVersions();

    for (var i = 0; i < descriptions.Count; i++)
    {
        var description = descriptions[i];

        options.AddDocument(
            description.GroupName,
            description.GroupName,
            isDefault: i == descriptions.Count - 1);
    }
});
```

`DescribeApiVersions()` 在这里仍然有用：它枚举版本给 Scalar 的文档列表，`isDefault` 落在最后一项上让最新版本最先打开。Swashbuckle 在 .NET 9 就从模板里移除了，这个 OpenAPI + Scalar 组合是当前默认，不是旧的 Swagger UI。

## 字段级版本化：不用新版本改一个字段

这是 Asp.Versioning 10.2 改变建议的部分，新到其他文章都还没覆盖。以前规则很简单：加字段安全，删或重命名是破坏性的，破坏性意味着新版本。于是一个被删的属性就逼你立起整个第二端点、复制 DTO、永远维护两份。

`[VisibleInApiVersion]` 打破了这个关联：标注在**成员**上，库按请求版本过滤它：

```csharp
public class Product
{
    public int Id { get; set; }
    public required string Name { get; set; }
    public decimal Price { get; set; }

    // Introduced in v2. Invisible to v1 clients.
    [VisibleInApiVersion("2.0")]
    public string? Sku { get; set; }

    // Served to v1 only. Dropped from v2.
    [VisibleInApiVersion("[1.0,2.0)")]
    public string? LegacyCategory { get; set; }
}
```

一个类，两种形状，handler 里零分支。运行结果：

```bash
$ curl http://localhost:5215/api/v1/products
[{"id":1,"name":"Keyboard","price":79.00,"legacyCategory":"Peripherals"}]

$ curl http://localhost:5215/api/v2/products
{"data":[{"id":1,"name":"Keyboard","price":79.00,"sku":"KB-001"}],"count":2}
```

参数用的是和 NuGet 包版本一样的**区间记法**，对应新的 `ApiVersionRange` 类型：`"2.0"` 表示 2.0 及以后，`"[1.0]"` 表示恰好 1.0，`"[1.0,2.0)"` 表示 1.0 到不含 2.0，`"(,1.0]"` 表示 1.0 及以前。区间**匹配**版本，不**声明**版本——版本仍然在端点上声明。

生成的 OpenAPI 文档也遵循同样的过滤，这是让它真正可用的细节：`/openapi/v1.json` 里 `Product` schema 列出 `id/name/price/legacyCategory`，`/openapi/v2.json` 里列出 `id/name/price/sku`。你的文档不再撒谎。

### 还没人写下来的坑

过滤也作用于**入站**请求，这是大规模采用前要慢下来的地方。发布说明把它描述为补上 over-posting 的漏洞——确实如此。但它不是静默丢弃隐藏成员，而是**用 400 拒绝请求**：

```bash
$ curl -X POST http://localhost:5215/api/v1/products \
    -H "Content-Type: application/json" \
    -d '{"id":9,"name":"Webcam","price":120.00,"sku":"WC-009"}'
400 Bad Request
The JSON property 'sku' could not be found on type 'Product'.
```

对 over-posting 来说这是对的——v1 客户端不应该能设置 v2 专属字段，大声失败好过悄悄失败。但想想另一种情况：很多客户端读一个对象再整个回传。如果客户端从 v2 文档里拿走一个字段、回显到 v1 端点，得到的是硬 400 而不是被容忍的多余属性。这是对通常宽松的 JSON 绑定的行为改变，会让人意外。

作者的判断：`[VisibleInApiVersion]` 用在**读为主的响应模型**上，请求模型上要慎重。它是为「一个字段出现、一个字段消失，而你不想为此复制 DTO 和端点」这个场景准备的，不是跳过端点版本化的通行证。信封、状态码、错误契约或字段含义变了，那仍然是真版本。如果你发现自己往十几个属性上撒区间，说明契约翻动太快，字段级版本化在掩盖而不是修复问题。

两个限制：过滤目前**仅限 JSON**；特性位于核心抽象里，所以可以在共享库标注模型而不用依赖 ASP.NET Core。

## 分析器会给你的配置打分

10.2 还带了 **31 个 Roslyn 分析器**，没有单独的包要装。核心规则打包在 `Asp.Versioning.Abstractions`，API 规则在 `Asp.Versioning.Http`，任何引用版本化的项目一升级就会传递性地拿到它们。

升级后第一个惊喜：**AV0012、AV0018、AV0019 默认是 error，会直接让构建失败**：

| 规则   | 捕获什么                                                 |
| ------ | -------------------------------------------------------- |
| AV0012 | 默认 API 版本无效                                        |
| AV0018 | 每个端点都是版本中立                                     |
| AV0019 | 版本化和版本中立端点混用不一致                           |
| AV0015 | 没有显式设置 reader，每个请求探测多个来源                |
| AV0016 | 不需要的地方设置了 `AssumeDefaultVersionWhenUnspecified` |
| AV0031 | 没配置 API explorer，OpenAPI 文档没有版本                |

作者在写这篇文章的示例时亲身踩过：第一次构建就报了 AV0015 和 AV0016，配置是从本指南旧版复制的。两条都合理：reader 留了隐式，`AssumeDefaultVersionWhenUnspecified` 无缘无故开着。修完上面配置节的写法，构建就干净了。

每条规则都有指向文档页的 `helpLinkUri`，单条规则按惯例通过 `.editorconfig` 配置。整体关掉用 MSBuild 属性：

```xml
<PropertyGroup>
  <EnableApiVersioningAnalyzers>false</EnableApiVersioningAnalyzers>
</PropertyGroup>
```

注意 `ExcludeAssets="analyzers"` 在这里**不生效**——分析器从多条依赖路径进来，NuGet 会合并所有路径的资产，MSBuild 属性是唯一可靠的开关。

## 正确弃用一个版本：Sunset 头

加版本容易，不破坏信任地退休版本才是专业 API 和玩具项目的分水岭。错误做法是周五直接删 v1。正确做法三步：**标记弃用、公告移除日期、然后移除**。

标记弃用是控制器上的一个标志（`[ApiVersion("1.0", Deprecated = true)]`）或 Minimal API 组上的 `HasDeprecatedApiVersion(1.0)`。配合 `ReportApiVersions = true`，v1 的调用现在返回 `api-deprecated-versions: 1.0`，细心的客户端不用读 changelog 就知道它快走了。

专业手笔是 **Sunset 头（RFC 8594）**，告诉客户端版本具体何时消失并链接迁移指南。Asp.Versioning 通过版本策略暴露：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.ReportApiVersions = true;

    options.Policies.Sunset(1.0)
        .Effective(new DateTimeOffset(2026, 12, 31, 0, 0, 0, TimeSpan.Zero))
        .Link("https://api.example.com/docs/migrating-to-v2")
            .Title("Migration Guide")
            .Type("text/html");
});
```

现在每个 v1 响应都带这两个头：

```text
Sunset: Thu, 31 Dec 2026 00:00:00 GMT
Link: <https://api.example.com/docs/migrating-to-v2>; rel="sunset"; title="Migration Guide"; type="text/html"
```

客户端和监控可以按日期行动，而不是等集成 404 才发现版本没了。用带显式偏移的 `DateTimeOffset` 而不是裸 `DateTime`，否则头会按服务器本地时间渲染，对半个地球的人来说日期差一天。

## 常见问题排查

按作者见到的频率排序的六个实际问题：

1. **升级到 10.2 后构建失败（AV0012/AV0018/AV0019）。** 这三条分析器默认是 error 且随包传递进来。读诊断上的 `helpLinkUri` 修底层配置——它们通常指着真问题。急着上线就先设 `<EnableApiVersioningAnalyzers>false</...>`，别用 `ExcludeAssets="analyzers"`。
2. **加了版本段后所有请求 404。** `{version:apiVersion}` 路由约束需要端点上声明了版本。路由模板有段但 `[ApiVersion]`/`HasApiVersion` 没声明那个版本，就匹配不上。请求你从未声明的版本返回 404 是设计行为，`GET /api/v999/products` 返回 404 不是 bug。
3. **Scalar 显示一份合并文档、没有版本切换器。** 缺 `AddApiExplorer`，或 `GroupNameFormat` 与注册给 Scalar 的文档名不匹配。分析器 AV0031 捕获第一种。直接查 `/openapi/v1.json`——返回文档说明问题在 Scalar 接线；404 说明问题在 `MapOpenApi().WithDocumentPerVersion()`。
4. **OpenAPI 文档 `components.schemas` 是空的。** handler 返回了未类型化结果。Minimal API 把 `Results.Ok(...)` 换成 `TypedResults.Ok(...)`，控制器给 action 加 `ActionResult<T>` 返回类型。没有声明类型，OpenAPI 没东西可描述，按版本过滤 schema 也没东西可过滤。
5. **加 `[VisibleInApiVersion]` 后 v1 客户端突然收到 400。** 成员过滤器对输入拒绝隐藏属性而不是忽略。如果客户端会整体回传对象，要么停止在请求模型上隐藏该成员，要么给旧版本准备单独的请求 DTO。
6. **请求打到了错误版本而不是失败。** 几乎总是 `AssumeDefaultVersionWhenUnspecified = true` 加上一个看不到客户端所发版本的 reader。关掉开关，配置错误就会变成明显的 404 而不是悄悄返回错误数据。

## 最佳实践

作者接线过不少 API 后不会打破的规则：

1. **第一天就版本化。** 哪怕只有一个版本也发 v1。给已上线、没版本化的 API 回填版本化是最痛的路——每个现有客户端都假设未版本化的 URL。
2. **公开 API 默认 URL 段版本化。** 可见、可缓存、可测试。有具体理由再考虑 header。
3. **选一个方案并坚持。** reader 是单向门。`ApiVersionReader.Combine` 是给迁移用的，不是「什么都支持」的长期姿态。
4. **只有破坏性变更才升主版本。** 向后兼容的新增改动进当前版本。别因为加了个可选字段就发 v2。
5. **`[VisibleInApiVersion]` 用于字段级改动，不是替代版本。** 属性出现或消失是它的好用法；信封、状态码、错误契约变了还是真版本。
6. **开 `ReportApiVersions`。** 免费的、基于标准的能力宣告。
7. **永远不要静默删版本。** 弃用、定 Sunset 日期、链接迁移指南、再移除——按这个顺序。
8. **别过度版本化。** 两到三个存活版本是健康上限。如果你扛着 v5，真正的问题是不稳定的契约，版本化在掩盖它而不是修复它。

版本化只是生产 API 的一层。公开的版本化 API 仍然需要认证和限流在前面挡着——它们位于你发布的每个版本之前。如果你在版本化 gRPC 服务而不是 HTTP，10.2 加了预览版的 `Asp.Versioning.Grpc`，把同一套模型带到版本化服务和消息字段上。

## 小结

API 版本化看起来像可选项，直到第一次破坏性变更——那时它是你和一整群坏掉的集成之间唯一的防线。.NET 10 上的路径很清晰：装 `Asp.Versioning` 10.2，默认 URL 段版本化并显式设置 reader，用同一套心智模型支持控制器和 Minimal API，用一行 `WithDocumentPerVersion()` 把版本接进 OpenAPI，用 Scalar 渲染，用 Sunset 头退休旧版本而不是静默删除。

10.2 单独就值得升级：`[VisibleInApiVersion]` 意味着单个字段出现或消失不再让你赔上一个完整端点版本，分析器会在客户端发现之前告诉你配置不干净。只是要记住：隐藏成员在输入时是被拒绝的，不是被忽略的。

把方案早期定对，因为它是客户端写死、你无法悄悄改掉的决策。今天发 v1，v2 就会是你添加的功能，而不是你要扑灭的火。

Aide Hub 持续分享 AI 助手、开发工具与软件工程实践。如果你也在调 ASP.NET Core 的版本化方案，欢迎分享你的 reader 选择和 Sunset 流程。

## 参考

- [API Versioning in ASP.NET Core - The .NET 10 Guide（原文，Mukesh Murugan）](https://codewithmukesh.com/blog/api-versioning-in-aspnet-core/)
- [dotnet/aspnet-api-versioning（Asp.Versioning 源码仓库）| GitHub](https://github.com/dotnet/aspnet-api-versioning)
- [API Versioning in .NET 10 Applications（官方 .NET 博客）](https://devblogs.microsoft.com/dotnet/api-versioning-in-dotnet-10-applications/)
- [RFC 8594（Sunset header）| IETF](https://www.rfc-editor.org/rfc/rfc8594)
- [Asp.Versioning 诊断规则文档](https://dotnet.github.io/aspnet-api-versioning/diagnostic/overview.html)
- [示例源码（api-versioning-in-aspnet-core）| GitHub](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/master/modules/03-advanced-api-patterns/api-versioning-in-aspnet-core)
