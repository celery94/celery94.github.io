---
pubDatetime: 2026-04-29T12:17:41+08:00
title: ".NET 10 中结合 API 版本管理与 OpenAPI 的完整指南"
description: "Asp.Versioning v10 首次正式支持 .NET 10 和内置 OpenAPI，本文从零演示如何为 Controllers 和 Minimal APIs 配置多版本 API，并集成 SwaggerUI / Scalar 可视化文档，代码精简、维护友好。"
tags: ["ASP.NET Core", "API Versioning", "OpenAPI", ".NET 10"]
slug: "dotnet-10-api-versioning-openapi"
ogImage: "../../assets/766/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/api-versioning-in-dotnet-10-applications/"
---

> 本文由 Microsoft MVP、Senior Software Engineer Sander ten Brinke 撰写，原载于 .NET 官方博客。

过去几年，ASP.NET Core 构建 API 的方式经历了不小的变化：Minimal APIs 出现了，.NET 10 还内置了请求验证（request validation）。然而，无论形式怎么变，**API 版本管理**始终是让 API 稳健演进的核心能力。

问题在于——自从 .NET 9 引入 `Microsoft.AspNetCore.OpenApi` 取代 Swashbuckle 之后，怎么把版本管理和新的 OpenAPI 支持拼在一起，一直是很多人的困惑：重复配置多、样板代码多，官方也没有给出一条清晰的路线。

现在有了答案：**Asp.Versioning v10**，第一个同时官方支持 .NET 10 和内置 OpenAPI 的版本，把这两件事的整合变得干净利落。

## API 版本管理的几种策略

在动手之前，先确认几种常见的 API 版本化方式：

- **URL Path**（如 `/api/v1/resource`）：直观，但 URL 会随版本变化
- **Query String**（如 `/api/resource?version=1.0`）：简单，不改 URL 结构
- **Header**（如 `X-API-Version: 1.0`）：更 RESTful，URL 保持稳定
- **Media Type**（如 `Accept: application/json; v=1.0`）：完全 RESTful，但实现复杂，GitHub API 采用此方式

`Asp.Versioning` 支持以上全部策略，并且可以组合使用。本文示例默认用 Query String 版本化，切换到其他策略只需改一处配置。

## .NET 9/10 中 OpenAPI 的现状

自 .NET 9 起，`Microsoft.AspNetCore.OpenApi` 成为生成 OpenAPI 文档的默认方式。它的默认访问地址 `/openapi/v1.json` 看起来已经"预留了版本"，但 ASP.NET Core 本身并没有提供完整的版本管理能力。

一个基础的 OpenAPI 配置如下（使用 .NET 10 的 [file-based apps](https://learn.microsoft.com/dotnet/core/sdk/file-based-apps) 格式，单个 `.cs` 文件即可运行）：

```csharp
#:property PublishAot=false
#:sdk Microsoft.NET.Sdk.Web
#:package Microsoft.AspNetCore.OpenApi@10.0.4

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenApi();

var app = builder.Build();

// 默认 OpenAPI 端点：/openapi/v1/openapi.json
app.MapOpenApi();

app.MapGet("/users", () =>
{
    var users = new List<UserDto>
    {
        new(1, "Ada Lovelace", "ada@example.com"),
        new(2, "Grace Hopper", "grace@example.com"),
    };
    return TypedResults.Ok<List<UserDto>>(users);
})
.WithName("GetUsers");

app.Run();

record UserDto(int Id, string Name, string Email);
```

这解决了"有 OpenAPI 文档"的问题，但还没有真正的版本管理。

## Controllers 版本化

Controllers 使用 `Asp.Versioning.Mvc` 包。通过 `[ApiVersion]` 属性标注每个控制器所属的版本，并在 DI 中调用 `AddApiVersioning().AddMvc()`：

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
```

对应的控制器（推荐每个版本一个控制器类）：

```csharp
[ApiController]
[Route("api/users")]
[ApiVersion("1.0")]
public class UsersV1Controller : ControllerBase
{
    [HttpGet]
    public ActionResult<UserV1[]> Get()
    {
        return Ok(new[]
        {
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
        return Ok(new[]
        {
            new UserV2(1, "John Doe", new DateOnly(1990, 1, 1)),
            new UserV2(2, "Alice Dewett", new DateOnly(1992, 2, 2)),
        });
    }
}

public record UserV1(int Id, string Name);
public record UserV2(int Id, string Name, DateOnly BirthDate);
```

配置完成后，通过 `api/users?api-version=1.0` 和 `api/users?api-version=2.0` 分别访问两个版本。

## Minimal APIs 版本化

Minimal APIs 使用 `Asp.Versioning.Http` 包，通过 `NewVersionedApi` 创建版本化路由组：

```csharp
#:property PublishAot=false
#:sdk Microsoft.NET.Sdk.Web
#:package Asp.Versioning.Http@10.0.0

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddApiVersioning();

var app = builder.Build();

var usersApi = app.NewVersionedApi("Users");

var usersV1 = usersApi.MapGroup("api/users").HasApiVersion("1.0");
var usersV2 = usersApi.MapGroup("api/users").HasApiVersion("2.0");

usersV1.MapGet("", () => TypedResults.Ok(new[]
{
    new UserV1(1, "John Doe"),
    new UserV1(2, "Alice Dewett"),
}));

usersV2.MapGet("", () => TypedResults.Ok(new[]
{
    new UserV2(1, "John Doe", new DateOnly(1990, 1, 1)),
    new UserV2(2, "Alice Dewett", new DateOnly(1992, 2, 2)),
}));

app.Run();

record UserV1(int Id, string Name);
record UserV2(int Id, string Name, DateOnly BirthDate);
```

当端点越来越多时，推荐把版本注册封装为扩展方法，`Program.cs` 里只留：

```csharp
app.MapUsers().ToV1().ToV2().ToV3();
app.MapScores().ToV1().ToV2().ToV3();
```

这样新版本的添加只改一处，`Program.cs` 保持可读。

## 切换版本化策略

默认是 Query String 版本化，改为 URL 段（`/api/v1/users`）只需：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.ApiVersionReader = new UrlSegmentApiVersionReader();
});
```

改为 Header 版本化：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.ApiVersionReader = new HeaderApiVersionReader("X-API-Version");
});
```

如果不想让客户端漏传版本号时报错，可以启用默认版本：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.DefaultApiVersion = new ApiVersion(1, 0);
    options.AssumeDefaultVersionWhenUnspecified = true;
});
```

也可以同时支持多种策略：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.ApiVersionReader = ApiVersionReader.Combine(
        new QueryStringApiVersionReader("api-version"),
        new HeaderApiVersionReader("X-API-Version")
    );
});
```

## 结合 OpenAPI 生成分版本文档

这是 Asp.Versioning v10 最关键的改进。新增了 `Asp.Versioning.OpenApi` 包，把原来需要多次调用 `AddOpenApi("v1")`、`AddOpenApi("v2")` 的繁琐配置压缩成了两步。

### Controllers 的配置

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
    .AddApiExplorer(options =>
    {
        // 格式化版本号为 v1、v2，与默认的 /openapi/v1.json 保持兼容
        options.GroupNameFormat = "'v'VVV";
    })
    .AddMvc()
    // 必须在 AddApiVersioning 链式调用之后再调用 AddOpenApi
    .AddOpenApi();

var app = builder.Build();

// WithDocumentPerVersion() 为每个 API 版本自动生成独立的 OpenAPI 文档
app.MapOpenApi().WithDocumentPerVersion();

app.MapControllers();
app.Run();
```

关键点有三：
1. `AddApiExplorer` 让 API Explorer 知道版本信息，是生成版本化文档的前提
2. `AddOpenApi` 必须来自 `Asp.Versioning` 命名空间（而不是 `Microsoft.AspNetCore`），调用位置在 `AddApiVersioning` 链式之后
3. `WithDocumentPerVersion()` 自动按版本生成文档，省掉了逐个调用 `AddOpenApi("v1")` 的维护负担

配置完成后，`/openapi/v1.json` 和 `/openapi/v2.json` 分别返回对应版本的文档。

### Minimal APIs 的配置

与 Controllers 几乎相同，只是不需要 `AddMvc()`：

```csharp
#:property PublishAot=false
#:sdk Microsoft.NET.Sdk.Web
#:package Asp.Versioning.Http@10.0.0
#:package Asp.Versioning.Mvc.ApiExplorer@10.0.0
#:package Asp.Versioning.OpenApi@10.0.0-rc.1

using Asp.Versioning;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddApiVersioning()
    .AddApiExplorer(options =>
    {
        options.GroupNameFormat = "'v'VVV";
    })
    .AddOpenApi();

var app = builder.Build();

app.MapOpenApi().WithDocumentPerVersion();

// 在此处粘贴前面"Minimal APIs 版本化"章节的端点代码
// 最后加上 app.Run();
```

## 集成 SwaggerUI 和 Scalar

有了版本化的 OpenAPI 文档，可以接入可视化工具。这部分配置对 Controllers 和 Minimal APIs 完全相同。

### SwaggerUI

使用 `Swashbuckle.AspNetCore.SwaggerUI`（只有 UI 组件，不含文档生成）：

```csharp
#:package Swashbuckle.AspNetCore.SwaggerUI@10.1.4

using Asp.Versioning.ApiExplorer;

// ... 其他配置 ...

app.MapOpenApi().WithDocumentPerVersion();

// UseSwaggerUI 必须在 MapOpenApi() 之后调用
app.UseSwaggerUI(options =>
{
    // 倒序，使最新版本排在下拉列表首位
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

使用 `Scalar.AspNetCore`，配置方式类似：

```csharp
#:package Scalar.AspNetCore@2.13.0

using Asp.Versioning.ApiExplorer;
using Scalar.AspNetCore;

// ... 其他配置 ...

app.MapOpenApi().WithDocumentPerVersion();

app.MapScalarApiReference(options =>
{
    var descriptions = app.DescribeApiVersions();
    for (var i = 0; i < descriptions.Count; i++)
    {
        var description = descriptions[i];
        // 最后一个版本设为默认选中
        var isDefault = i == descriptions.Count - 1;
        options.AddDocument(description.GroupName, description.GroupName, isDefault: isDefault);
    }
});

app.Run();
```

访问 `/scalar`，右上角的 Configure 还可以调整主题、布局等。

两个工具可以并存，都指向同一套 OpenAPI 文档，让团队按偏好选择。

## v8 到 v10 的主要变化

如果你的项目还在用 `Asp.Versioning v8.x.x`，升级到 v10 需要关注以下改变：

**v8 的写法（需要为每个版本单独注册）：**

```csharp
builder.Services.AddOpenApi("v1");
builder.Services.AddOpenApi("v2");

builder.Services.AddApiVersioning()
    .AddApiExplorer(options =>
    {
        options.GroupNameFormat = "'v'VVV";
    });

app.MapOpenApi();
```

**v10 的写法（一次配置搞定所有版本）：**

```csharp
builder.Services.AddApiVersioning()
    .AddApiExplorer(options =>
    {
        options.GroupNameFormat = "'v'VVV";
    })
    .AddOpenApi();

app.MapOpenApi().WithDocumentPerVersion();
```

最显著的变化是：`AddOpenApi` 只需调用一次，且必须链在 `AddApiVersioning` 之后；`WithDocumentPerVersion()` 替代了手动的多次 `AddOpenApi("vX")` 调用。v8 中要让 SwaggerUI/Scalar 支持版本化还需要额外的 OpenAPI transformer，v10 把这部分也内置了。

> **注意**：`Asp.Versioning.OpenApi` v10.0.0-rc.1 目前处于 Release Candidate 阶段，请关注[发布说明](https://github.com/dotnet/aspnet-api-versioning/releases/tag/v10.0.0)。

## 延伸：为 OpenAPI 文档加入 Lint 检查

API 稳定之后，还可以用以下工具进一步保障质量：

- **[Spectral](https://github.com/stoplightio/spectral)**：为 OpenAPI 文档定义自定义 lint 规则，在 PR 阶段发现不规范的 API 设计（例如漏掉版本标注）
- **[oasdiff](https://github.com/oasdiff/oasdiff)**：对比两个版本的 OpenAPI 文档，检测 breaking change；可集成进 CI/CD，一旦发现破坏性变更就让流水线失败，强制开发者引入新版本而不是悄悄修改旧版本

这两个工具结合使用，可以把"API 版本管理规范"从文档要求变成可执行的工程约束。

## 参考

- [原文：Combining API versioning with OpenAPI in .NET 10 applications](https://devblogs.microsoft.com/dotnet/api-versioning-in-dotnet-10-applications/)
- [Asp.Versioning GitHub 仓库](https://github.com/dotnet/aspnet-api-versioning)
- [作者示例代码仓库](https://github.com/sander1095/openapi-versioning)
- [Microsoft.AspNetCore.OpenApi 官方文档](https://learn.microsoft.com/aspnet/core/fundamentals/openapi/overview)
- [Asp.Versioning 官方文档](https://github.com/dotnet/aspnet-api-versioning/wiki)
