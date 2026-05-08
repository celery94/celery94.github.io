---
pubDatetime: 2026-05-08T09:40:00+08:00
title: ".NET 10 中结合 API 版本控制与 OpenAPI 文档的实践指南"
description: "本文介绍如何在 .NET 10 应用中使用全新的 Asp.Versioning v10 实现 API 版本控制，涵盖 Controllers 和 Minimal APIs 两种方式，并与内置 OpenAPI 库无缝集成，生成各版本独立的文档，同时支持 SwaggerUI 和 Scalar 可视化工具。"
tags: [".NET", "ASP.NET Core", "API Versioning", "OpenAPI", "Minimal APIs"]
slug: "api-versioning-openapi-dotnet-10"
ogImage: "../../assets/784/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/api-versioning-in-dotnet-10-applications/"
---

> 本文译自 Sander ten Brinke（Microsoft MVP、Senior Software Engineer）发布在 .NET Blog 的原文，作者对构建可扩展、可维护的应用深有研究。

过去几年，ASP.NET Core 的 API 开发方式发生了不小的变化。Minimal APIs 的出现让入门门槛降低了很多，.NET 10 进一步加入了[内置请求验证](https://learn.microsoft.com/aspnet/core/release-notes/aspnetcore-10.0?view=aspnetcore-10.0#validation-support-in-minimal-apis)，让它与传统 Controllers 相比更具竞争力。

但有一件事始终绕不开：**API 版本控制**。正确的版本管理能让 API 在演进过程中不破坏现有客户端。[Asp.Versioning](https://github.com/dotnet/aspnet-api-versioning) 库长期以来承担着这个任务。而随着 .NET 9 引入 `Microsoft.AspNetCore.OpenApi` 作为官方 OpenAPI 库，版本控制的集成方式也随之改变。

本文介绍如何在 .NET 10 中使用全新的 **Asp.Versioning v10**——这是第一个同时官方支持 .NET 10 和新内置 OpenAPI 库的版本——为 Controllers 和 Minimal APIs 实现版本控制，并生成各版本独立的 OpenAPI 文档。

![三条版本数据流汇入统一管道的示意图](../../assets/784/01-cover.png)

## 为什么需要 API 版本控制

API 版本控制让你在引入新特性、修复缺陷、调整结构时，不会直接破坏正在使用旧版本的客户端。常见的版本策略有以下几种：

- **URL 路径版本**：`/api/v1/resource`
- **查询字符串版本**：`/api/resource?version=1.0`
- **请求头版本**：`X-API-Version: 1.0`
- **媒体类型版本**：`Accept: application/json; v=1.0`（GitHub 采用此方式）

版本号格式也有多种选择：`v1`、`v1.0`、日期格式（`2026-03-01`）、状态标识（`v1-beta`）等，具体取决于业务场景和客户端需求。

> **注意**：本文聚焦 `Asp.Versioning v10.0.0`，这是第一个**官方**同时支持 ASP.NET Core 10 和新内置 OpenAPI 库的版本。旧版 `v8.x.x` 通过隐式 roll-forward 仍可在 .NET 10 运行，但 v10 是专门为新 OpenAPI 集成而设计的，建议新项目直接使用。

> **关于代码示例**：所有完整示例均为[文件式应用](https://learn.microsoft.com/dotnet/core/sdk/file-based-apps)（file-based apps），这是 C# 14 / .NET 10 的新特性，可以直接用 `dotnet <filename>.cs` 运行，无需项目文件。文件顶部的 `#:sdk` 和 `#:package` 指令会自动配置所需 SDK 和 NuGet 包，确保安装了 [.NET 10 SDK](https://dotnet.microsoft.com/download/dotnet/10.0) 即可。

## .NET 9 / 10 中 OpenAPI 的变化

从 .NET 9 起，`Microsoft.AspNetCore.OpenApi` 成为 ASP.NET Core 应用生成 OpenAPI 文档的默认方式，取代了原来模板里内置的 `Swashbuckle.AspNetCore`。配置非常简洁，而且 URL 路径默认就带版本段（`/openapi/v1.json`），看起来天生就为版本化设计。

快速示例如下：

```csharp
#:property PublishAot=false
#:sdk Microsoft.NET.Sdk.Web
#:package Microsoft.AspNetCore.OpenApi@10.0.4

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddOpenApi();

var app = builder.Build();

// OpenAPI 文档默认在 /openapi/v1/openapi.json
app.MapOpenApi();

app.MapGet("/users", () => {
    var users = new List<UserDto> {
        new(1, "Ada Lovelace", "ada@example.com"),
        new(2, "Grace Hopper", "grace@example.com"),
    };
    return TypedResults.Ok<List<UserDto>>(users);
}).WithName("GetUsers");

app.Run();

record UserDto(int Id, string Name, string Email);
```

不过，`Microsoft.AspNetCore.OpenApi` 本身并不提供完整的版本控制能力，这就是 `Asp.Versioning` 库的用武之地。

## Asp.Versioning 简介

[Asp.Versioning](https://github.com/dotnet/aspnet-api-versioning) 是一套专为 ASP.NET Core 设计的版本控制库，所有包合计下载量超过 **8 亿次**，在 .NET 社区被广泛采用。

不同 API 类型需要的包略有不同：

| API 类型 | 所需包（.NET 10+） |
|---|---|
| Controllers | `Asp.Versioning.Mvc` / `Asp.Versioning.Mvc.ApiExplorer` |
| Minimal APIs | `Asp.Versioning.Http` / `Asp.Versioning.Mvc.ApiExplorer` |

> 完整代码示例可在[示例仓库](https://github.com/sander1095/openapi-versioning)查看，更多样例可参考 [Asp.Versioning 官方示例](https://github.com/dotnet/aspnet-api-versioning/tree/main/examples)。

## Controllers 的版本控制

`Asp.Versioning.Mvc` 包提供一组特性和约定来声明 API 版本。推荐的做法是每个版本对应一个独立的 Controller 类：

```csharp
#:property PublishAot=false
#:sdk Microsoft.NET.Sdk.Web
#:package Asp.Versioning.Mvc@10.0.0

using Asp.Versioning;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddApiVersioning()
    .AddMvc();

var app = builder.Build();
app.MapControllers();
app.Run();

// 对于文件式应用，Controller 类写在 app.Run() 之后

[ApiController]
[Route("api/users")]
[ApiVersion("1.0")]
public class UsersV1Controller : ControllerBase
{
    [HttpGet]
    public ActionResult<UserV1[]> Get()
    {
        return Ok(new[] {
            new UserV1(1, "John Doe"),
            new UserV1(2, "Alice Dewett"),
        });
    }
}

[ApiController]
[Route("api/users")]
[ApiVersion("2.0")]
public class UsersV2Controller : ControllerBase
{
    [HttpGet]
    public ActionResult<UserV2[]> Get()
    {
        return Ok(new[] {
            new UserV2(1, "John Doe", new DateOnly(1990, 1, 1)),
            new UserV2(2, "Alice Dewett", new DateOnly(1992, 2, 2)),
        });
    }
}

public record UserV1(int Id, string Name);
public record UserV2(int Id, string Name, DateOnly BirthDate);
```

通过 `api/users?api-version=1.0` 和 `api/users?api-version=2.0` 分别访问两个版本。

## Minimal APIs 的版本控制

Minimal APIs 使用 `Asp.Versioning.Http` 包，通过 `NewVersionedApi` 创建版本化路由组：

```csharp
#:property PublishAot=false
#:sdk Microsoft.NET.Sdk.Web
#:package Asp.Versioning.Http@10.0.0

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddApiVersioning();

var app = builder.Build();

var usersApi = app.NewVersionedApi("Users");
var usersv1 = usersApi.MapGroup("api/users").HasApiVersion("1.0");
var usersv2 = usersApi.MapGroup("api/users").HasApiVersion("2.0");

usersv1.MapGet("", () => TypedResults.Ok(new[] {
    new UserV1(1, "John Doe"),
    new UserV1(2, "Alice Dewett"),
}));

usersv2.MapGet("", () => TypedResults.Ok(new[] {
    new UserV2(1, "John Doe", new DateOnly(1990, 1, 1)),
    new UserV2(2, "Alice Dewett", new DateOnly(1992, 2, 2)),
}));

app.Run();

record UserV1(int Id, string Name);
record UserV2(int Id, string Name, DateOnly BirthDate);
```

> **如何组织多版本 API**：随着 API 规模增长，把所有版本定义塞进 `Program.cs` 会越来越难维护。一个常见的解法是用扩展方法拆分：
> ```csharp
> app.MapUsers().ToV1().ToV2().ToV3();
> app.MapScores().ToV1().ToV2().ToV3();
> ```
> 其中 `MapUsers()` 调用 `app.NewVersionedApi()`，而 `ToV1()`、`ToV2()` 等是各版本路由的扩展方法，保持 `Program.cs` 简洁易读。

## 切换版本策略

上面的示例使用查询字符串版本（默认行为），但切换到其他策略只需修改配置：

**URL 段版本**（`api/v1/users`）：

```csharp
builder.Services.AddApiVersioning(options => {
    options.ApiVersionReader = new UrlSegmentApiVersionReader();
});
```

**请求头版本**（`X-API-Version: 1.0`）：

```csharp
builder.Services.AddApiVersioning(options => {
    options.ApiVersionReader = new HeaderApiVersionReader("X-API-Version");
});
```

对于请求头和查询字符串版本，客户端可能忘记传版本号。可以设置默认版本来兜底：

```csharp
builder.Services.AddApiVersioning(options => {
    options.DefaultApiVersion = new ApiVersion(1, 0);
    // 未指定版本时使用默认版本（默认关闭，启用需权衡便利性和显式性）
    options.AssumeDefaultVersionWhenUnspecified = true;
});
```

也可以同时支持多种策略：

```csharp
builder.Services.AddApiVersioning(options => {
    options.ApiVersionReader = ApiVersionReader.Combine(
        new QueryStringApiVersionReader("api-version"),
        new HeaderApiVersionReader("X-API-Version")
    );
});
```

## 在 .NET 10 中集成 OpenAPI 与版本控制

> **注意**：`Asp.Versioning.OpenApi` v10.0.0-rc.1 目前处于 Release Candidate 阶段。

`Asp.Versioning v10.0.0` 新增了 `Asp.Versioning.OpenApi` 包，让 Controllers 和 Minimal APIs 都能以简洁的方式生成**各版本独立的** OpenAPI 文档，无需手动重复注册。

### Controllers + OpenAPI

只需在原有配置上做三处改动：

1. 在 `AddApiVersioning()` 之后调用 `.AddApiExplorer()`，让版本信息进入 OpenAPI 文档
2. 调用 `Asp.Versioning` 命名空间下的 `.AddOpenApi()`（而非 `Microsoft.AspNetCore` 的那个）
3. `app.MapOpenApi().WithDocumentPerVersion()` 自动为每个版本生成独立文档

```csharp
#:property PublishAot=false
#:sdk Microsoft.NET.Sdk.Web
#:package Asp.Versioning.Mvc@10.0.0
#:package Asp.Versioning.Mvc.ApiExplorer@10.0.0
#:package Asp.Versioning.OpenApi@10.0.0-rc.1

using Asp.Versioning;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddApiVersioning()
    .AddApiExplorer(options => {
        // GroupNameFormat 让版本号格式化为 v1、v2，与 /openapi/v1.json 默认行为一致
        options.GroupNameFormat = "'v'VVV";
    })
    .AddMvc()
    .AddOpenApi(); // 必须在 AddApiVersioning 链上调用

var app = builder.Build();

// WithDocumentPerVersion() 为每个 API 版本自动生成独立文档
app.MapOpenApi().WithDocumentPerVersion();
app.MapControllers();
app.Run();

// 把之前章节中的 Controller 类粘贴到 app.Run() 之后
```

现在可以分别访问 `/openapi/v1.json` 和 `/openapi/v2.json` 获取各版本的文档。

### Minimal APIs + OpenAPI

配置方式与 Controllers 完全相同，唯一区别是不需要调用 `.AddMvc()`：

```csharp
#:property PublishAot=false
#:sdk Microsoft.NET.Sdk.Web
#:package Asp.Versioning.Http@10.0.0
#:package Asp.Versioning.Mvc.ApiExplorer@10.0.0
#:package Asp.Versioning.OpenApi@10.0.0-rc.1

using Asp.Versioning;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddApiVersioning()
    .AddApiExplorer(options => {
        options.GroupNameFormat = "'v'VVV";
    })
    .AddOpenApi();

var app = builder.Build();

app.MapOpenApi().WithDocumentPerVersion();

// 在此处粘贴前面 Minimal APIs 章节中的 API 端点和 record 定义
app.Run();
```

## 接入 SwaggerUI 和 Scalar

版本化的 OpenAPI 文档生成好之后，可以接入可视化工具来浏览和测试接口。

### SwaggerUI

使用 `Swashbuckle.AspNetCore.SwaggerUI` 包（只含 UI 组件，不含文档生成），配置让其指向版本化文档：

```csharp
#:package Swashbuckle.AspNetCore.SwaggerUI@10.1.4

using Asp.Versioning.ApiExplorer;

// ... （省略 AddApiVersioning / AddOpenApi 等配置）

app.MapOpenApi().WithDocumentPerVersion();

// UseSwaggerUI 必须在 MapOpenApi() 和所有端点定义之后调用
app.UseSwaggerUI(options => {
    // 倒序排列，让最新版本显示在最前面
    foreach (var description in app.DescribeApiVersions().Reverse())
    {
        options.SwaggerEndpoint(
            $"/openapi/{description.GroupName}.json",
            description.GroupName.ToUpperInvariant());
    }
});

app.Run();
```

访问 `/swagger` 即可看到带版本下拉菜单的 SwaggerUI 界面。

### Scalar

`Scalar.AspNetCore` 提供更现代的界面，性能也优于 SwaggerUI：

```csharp
#:package Scalar.AspNetCore@2.13.0

using Asp.Versioning.ApiExplorer;
using Scalar.AspNetCore;

// ... （省略 AddApiVersioning / AddOpenApi 等配置）

app.MapOpenApi().WithDocumentPerVersion();

app.MapScalarApiReference(options => {
    var descriptions = app.DescribeApiVersions();
    for (var i = 0; i < descriptions.Count; i++)
    {
        var description = descriptions[i];
        var isDefault = i == descriptions.Count - 1;
        options.AddDocument(description.GroupName, description.GroupName, isDefault: isDefault);
    }
});

app.Run();
```

访问 `/scalar` 查看带版本切换的 Scalar 界面。右上角的 Configure 按钮可以调整主题和布局。

如果两者都想支持，没有问题——SwaggerUI 在 `/swagger`，Scalar 在 `/scalar`，可以共存。

## v8 升级到 v10 的关键变化

从 `Asp.Versioning v8.x.x` 升级到 v10，主要变化有：

- 新增 `Asp.Versioning.OpenApi` 包，Controllers 和 Minimal APIs 都需要引用
- `AddOpenApi()` 必须从 `Asp.Versioning` 命名空间调用，而不是 `Microsoft.AspNetCore`
- `WithDocumentPerVersion()` 替代了之前手动多次调用 `services.AddOpenApi("v1")` / `services.AddOpenApi("v2")` 的写法
- v8 中需要自定义 OpenAPI Transformer 才能让 SwaggerUI / Scalar 支持版本化，v10 中这些工作已内置

对比一下两个版本的配置量：

**v8.x.x（旧方式）**：

```csharp
builder.Services.AddOpenApi("v1");
builder.Services.AddOpenApi("v2");
builder.Services.AddApiVersioning()
    .AddApiExplorer(options => {
        options.GroupNameFormat = "'v'VVV";
    });

app.MapOpenApi();
// 还需要若干 OpenAPI Transformer 才能让 SwaggerUI/Scalar 正常工作
```

**v10.x.x（新方式）**：

```csharp
builder.Services.AddApiVersioning()
    .AddApiExplorer(options => {
        options.GroupNameFormat = "'v'VVV";
    })
    .AddOpenApi(); // 一次调用，自动感知所有版本

app.MapOpenApi().WithDocumentPerVersion();
```

减少了重复配置，也降低了加新版本时漏改某处的风险。

## 进一步：API 质量保障工具

版本化文档就绪之后，可以用 API linting 工具来保证接口质量：

- **[Spectral](https://github.com/stoplightio/spectral)**：定义自定义规则对 OpenAPI 文档做 linting，可以强制要求所有 API 必须添加版本控制、接口必须有描述等团队规范，集成进 CI/CD 流程后，缺少版本标记的 PR 会自动被拦截。
- **[oasdiff](https://github.com/oasdiff/oasdiff)**：对比两个 OpenAPI 文档，检测破坏性变更。把它接入流水线，当检测到有不兼容改动时自动提示开发者引入新版本，而不是直接修改已发布的 API。

## 小结

.NET 10 加上 `Asp.Versioning v10`，让 API 版本控制的配置比以往简洁了很多：一次 `AddOpenApi()` 调用加上 `WithDocumentPerVersion()`，就能为 Controllers 或 Minimal APIs 自动生成版本化的 OpenAPI 文档，SwaggerUI / Scalar 集成也不再需要手写 Transformer。

如果你的项目还在用 v8，[这个提交](https://github.com/sander1095/openapi-versioning/commit/0623dc7ae35eb5a2e253d1771c1d3c03addb24f3)记录了升级时需要调整的关键点，可以作为迁移参考。

## 参考

- [原文：Combining API versioning with OpenAPI in .NET 10 applications](https://devblogs.microsoft.com/dotnet/api-versioning-in-dotnet-10-applications/)
- [Asp.Versioning GitHub 仓库](https://github.com/dotnet/aspnet-api-versioning)
- [示例代码仓库](https://github.com/sander1095/openapi-versioning)
- [Microsoft.AspNetCore.OpenApi 官方文档](https://learn.microsoft.com/aspnet/core/fundamentals/openapi/overview)
- [ASP.NET Community Standup：Combining API Versioning with OpenAPI](https://www.youtube.com/watch?v=7m3r6slW68U)
