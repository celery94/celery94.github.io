---
pubDatetime: 2024-03-14
tags: [".NET", "ASP.NET Core", "API", "Versioning", "swagger"]
author: Celery Liu
title: ASP.NET Core Web API with swagger中基于URL的API版本控制
description: 在这篇文章中，我们将讨论如何在 ASP.NET Core Web API 中实现基于 URL 的 API 版本控制。我们将使用 `Asp.Versioning.Mvc` NuGet 包来实现版本控制。我们还将使用 `Asp.Versioning.Mvc.ApiExplorer` NuGet 包来集成 swagger。
---

# ASP.NET Core Web API with Swagger 中的 API 版本控制

> ## 摘要
>
> 在这篇文章中，我们将探讨如何在 ASP.NET Core Web API 中实现基于 URL 的 API 版本控制，并通过 `Asp.Versioning.Mvc` 和 `Asp.Versioning.Mvc.ApiExplorer` NuGet 包实现版本控制的集成到 Swagger。这样的版本控制机制不仅有助于维护老版本的 API 同时引入新版本的变化，而且还能通过 Swagger UI 为不同版本的 API 提供清晰的文档和测试界面。

## 引言

随着Web应用程序的不断发展和变化，API版本控制成为了一个重要的考虑因素。它允许开发人员引入不兼容的API改变而不会破坏现有的客户端实现。在ASP.NET Core Web API中实现版本控制，能够让你的应用保持灵活性和可扩展性。

## 如何在 ASP.NET Core Web API 中实现基于 URL 的 API 版本控制

URI版本控制是通过将版本信息直接嵌入到URL中来实现的，这种方法的直观性和易于理解使其成为众多API设计中的常用方案。

### 步骤 1: 安装必要的 NuGet 包

为了实现基于 URL 的 API 版本控制，首先需要安装 `Asp.Versioning.Mvc` NuGet 包。请注意，在 dotnet 5 之前，官方使用的是 `Microsoft.AspNetCore.Mvc.Versioning` 包，但它现在已经被废弃。

```bash
dotnet add package Asp.Versioning.Mvc --version 8.0.0
```

### 步骤 2: 配置版本控制

在 `Program.cs` 或 `Startup.cs` 中配置版本控制，以启用API版本报告功能。这样做可以让客户端知道服务器支持哪些版本的API。

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.ReportApiVersions = true;
});
```

### 步骤 3: 添加版本信息到控制器

在控制器上指定 API 版本信息，确保API的访问路径包含版本号。

```csharp
[ApiVersion("1.0")]
[Route("api/v{version:apiVersion}/[controller]")]
[ApiController]
public class ValuesController : ControllerBase
{
    // ...
}
```

通过这种方式，客户端可以通过如 `api/v1/values` 的 URL 访问特定版本的 API。

## 集成版本控制到 Swagger 中

集成 API 版本控制到 Swagger 不仅可以提供接口文档，还能通过 Swagger UI 测试不同版本的 API。

### 步骤 1: 安装 Swagger 集成包

首先，安装与 API 版本控制集成的 Swagger 包。

```bash
dotnet add package Asp.Versioning.Mvc.ApiExplorer --version 8.0.0
```

### 步骤 2: 配置 Swagger 以支持 API 版本控制

在 `Program.cs` 中配置 API 版本控制和 Swagger 集成，确保每个版本的 API 都有对应的 Swagger 文档。

```csharp
builder.Services.AddApiVersioning(
    options =>
    {
        options.ReportApiVersions = true;
    })
.AddApiExplorer(
    options =>
    {
        options.GroupNameFormat = "'v'VVV";
        options.SubstituteApiVersionInUrl = true;
    });
```

### 步骤 3: 配置 Swagger UI 以显示不同版本的 API

通过 `ConfigureSwaggerOptions` 类和 `SwaggerGenOptions`，为每

个发现的 API 版本添加一个 Swagger 文档，并在 Swagger UI 中显示这些版本。

```csharp
public class ConfigureSwaggerOptions : IConfigureOptions<SwaggerGenOptions>
{
    private readonly IApiVersionDescriptionProvider _provider;

    public ConfigureSwaggerOptions(IApiVersionDescriptionProvider provider)
    {
        _provider = provider;
    }

    public void Configure(SwaggerGenOptions options)
    {
        foreach (var description in _provider.ApiVersionDescriptions)
        {
            options.SwaggerDoc(description.GroupName, CreateInfoForApiVersion(description));
        }
    }

    private OpenApiInfo CreateInfoForApiVersion(ApiVersionDescription description)
    {
        var info = new OpenApiInfo
        {
            Title = "API Title",
            Version = description.ApiVersion.ToString(),
            Description = "API Description. "
        };

        return info;
    }
}

builder.Services.AddTransient<IConfigureOptions<SwaggerGenOptions>, ConfigureSwaggerOptions>();
```

最后，在 `Startup.cs` 中启用 Swagger，配置 Swagger UI 以显示不同版本的 API 端点。

```csharp
app.UseSwagger();
app.UseSwaggerUI(
    options =>
    {
        var descriptions = app.DescribeApiVersions();

        foreach (var description in descriptions)
        {
            options.SwaggerEndpoint($"/swagger/{description.GroupName}/swagger.json", description.GroupName.ToUpperInvariant());
        }
    });
```

## 总结

通过以上步骤，我们不仅实现了基于 URL 的 API 版本控制，还成功地将其集成到 Swagger 中，从而为不同版本的 API 提供了清晰、易于访问的文档和测试界面。这种方法确保了 API 的长期可维护性和向后兼容性，同时也提升了开发者和最终用户的体验。
