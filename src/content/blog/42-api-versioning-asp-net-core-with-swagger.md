---
pubDatetime: 2024-03-14
tags: [".NET", "ASP.NET Core", "API", "Versioning", "swagger"]
author: Celery Liu
title: ASP.NET Core Web API with swagger中基于URL的API版本控制
description: 在这篇文章中，我们将讨论如何在 ASP.NET Core Web API 中实现基于 URL 的 API 版本控制。我们将使用 `Asp.Versioning.Mvc` NuGet 包来实现版本控制。我们还将使用 `Asp.Versioning.Mvc.ApiExplorer` NuGet 包来集成 swagger。
---

# ASP.NET Core Web API with swagger 中的 API 版本控制

> ## 摘要
>
> 在这篇文章中，我们将讨论如何在 ASP.NET Core Web API 中实现基于 URL 的 API 版本控制。我们将使用 `Asp.Versioning.Mvc` NuGet 包来实现版本控制。我们还将使用 `Asp.Versioning.Mvc.ApiExplorer` NuGet 包来集成 swagger。

## 如何在 ASP.NET Core Web API 中实现基于 URL 的 API 版本控制

URI版本控制是最常见的版本控制方案，因为版本信息从URI中很容易读取。

使用`Asp.Versioning.Mvc`实现基于 URL 的 API 版本控制，第一步是安装`Asp.Versioning.Mvc`NuGet 包。

> 在dotnet 5之前使用的`Microsoft.AspNetCore.Mvc.Versioning`已经被弃用

```bash
dotnet add package Asp.Versioning.Mvc --version 8.0.0
```

然后在`Program.cs`中配置版本控制：

```csharp
builder.Services.AddApiVersioning(options =>
{
    options.ReportApiVersions = true;
});
```

在需要版本控制的ApiController添加对应的版本信息：

```csharp
[ApiVersion("1.0")]
[Route("api/v{version:apiVersion}/[controller]")]
[ApiController]
public class ValuesController : ControllerBase
{
    // ...
}
```

这样，我们就可以通过`api/v1/values`访问`ValuesController`的API。 这已经完成了最基本的配置。

## 集成版本控制到swagger中

我们可以使用`Asp.Versioning.Mvc.ApiExplorer`来集成版本控制到swagger中。

```bash
dotnet add package Asp.Versioning.Mvc.ApiExplorer --version 8.0.0
```

然后在`Program.cs`中配置：

```csharp
builder.Services.AddApiVersioning(
        options =>
        {
            // reporting api versions will return the headers
            // "api-supported-versions" and "api-deprecated-versions"
            options.ReportApiVersions = true;
        })
    .AddApiExplorer(
        options =>
        {
            // add the versioned api explorer, which also adds IApiVersionDescriptionProvider service
            // note: the specified format code will format the version as "'v'major[.minor][-status]"
            options.GroupNameFormat = "'v'VVV";

            // note: this option is only necessary when versioning by url segment. the SubstitutionFormat
            // can also be used to control the format of the API version in route templates
            options.SubstituteApiVersionInUrl = true;
        });
```

这个时候使用`IApiVersionDescriptionProvider`可以获取所有版本的信息。为了在swagger中显示版本信息，需要提前配置`SwaggerGenOptions`

```csharp
/// <summary>
/// Configures the Swagger generation options.
/// </summary>
/// <remarks>This allows API versioning to define a Swagger document per API version after the
/// <see cref="IApiVersionDescriptionProvider"/> service has been resolved from the service container.</remarks>
public class ConfigureSwaggerOptions : IConfigureOptions<SwaggerGenOptions>
{
    private readonly IApiVersionDescriptionProvider _provider;

    /// <summary>
    /// Initializes a new instance of the <see cref="ConfigureSwaggerOptions"/> class.
    /// </summary>
    /// <param name="provider">The <see cref="IApiVersionDescriptionProvider">provider</see> used to generate Swagger documents.</param>
    public ConfigureSwaggerOptions(IApiVersionDescriptionProvider provider)
    {
        _provider = provider;
    }

    /// <inheritdoc />
    public void Configure(SwaggerGenOptions options)
    {
        // add a swagger document for each discovered API version
        // note: you might choose to skip or document deprecated API versions differently
        foreach (var description in _provider.ApiVersionDescriptions)
        {
            options.SwaggerDoc(description.GroupName, CreateInfoForApiVersion(description));
        }
    }

    private OpenApiInfo CreateInfoForApiVersion(ApiVersionDescription description)
    {
        var text = new StringBuilder("Example Description.");
        var info = new OpenApiInfo
        {
            Title = "Example Title",
            Version = description.ApiVersion.ToString()
        };

        if (description.IsDeprecated) text.Append(" This API version has been deprecated.");

        info.Description = text.ToString();

        return info;
    }
}

builder.Services.AddTransient<IConfigureOptions<SwaggerGenOptions>, ConfigureSwaggerOptions>();

```

最后在`Startup.cs`中启用swagger便可：

```csharp
app.UseSwagger();
app.UseSwaggerUI(
    options =>
    {
        var descriptions = app.DescribeApiVersions();

        // build a swagger endpoint for each discovered API version
        foreach (var description in descriptions)
        {
            var url = $"/swagger/{description.GroupName}/swagger.json";
            var name = description.GroupName.ToUpperInvariant();
            options.SwaggerEndpoint(url, name);
        }
    });
```
