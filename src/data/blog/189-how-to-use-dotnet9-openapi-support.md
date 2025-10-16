---
pubDatetime: 2025-03-11
tags: [".NET", "ASP.NET Core"]
slug: how-to-use-dotnet9-openapi-support
source: https://www.telerik.com/blogs/how-use-net-9-openapi-support-document-web-api
title: 探索.NET 9：内置OpenAPI支持助力Web API文档生成
description: 了解.NET 9如何通过内置OpenAPI支持简化Web API文档生成，探索新工具的应用与自定义方法，提升开发效率。
---

# 探索.NET 9：内置OpenAPI支持助力Web API文档生成 🚀

## 引言

.NET 9 引入了全新的库，用于记录您的 .NET Web API。对于已经使用 .NET 构建 API 的开发者来说，您可能已经听说过 Swagger。多年来，Swagger 一直作为 .NET Web 应用项目模板的一部分，它使您能够通过自动生成的规范来记录您的 API。😃

![Swagger UI 示例](https://d585tldpucybw.cloudfront.net/sfimages/default-source/blogs/2025/2025-02/swaggerui.png?sfvrsn=2ad422d2_2)

## 从 Swagger 到 Microsoft.AspNetCore.OpenApi 🌐

“Swagger”已经成为“OpenAPI”的代名词，但这两个术语值得区分。**OpenAPI** 是指规范，而 **Swagger** 则是指来自 SmartBear 的一系列产品，这些产品可以与 OpenAPI 规范交互。

在 .NET 项目中（.NET 8 及更早版本），默认情况下使用 Swagger。到了 .NET 9，微软捆绑了自己的工具来生成 OpenAPI 规范。在新的 .NET 9 项目中，你会发现它已经在使用这个新工具。🤔

### 安装和配置 Microsoft OpenAPI 包 📦

首先，安装新的 Microsoft OpenAPI 包：

```bash
dotnet add package Microsoft.AspNetCore.OpenApi
```

然后，在您的 **Program.cs** 文件中添加以下行进行配置：

```csharp
// 添加这一行
builder.Services.AddOpenApi();

var app = builder.Build();

// 添加这一行
app.MapOpenApi();
```

运行应用程序后，导航到 `/openapi/v1.json`，您会看到 JSON 格式的 OpenAPI 规范。

## 使用 Swagger UI 🖥️

想要继续使用 Swagger 提供的界面？没问题！生成的规范符合 OpenAPI 标准，因此我们可以使用熟悉的工具来探索该规范。例如，您可以安装 Swagger UI 包：

```bash
dotnet add package Swashbuckle.AspNetCore.SwaggerUi
```

然后在 **Program.cs** 中进行配置：

```csharp
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.UseSwaggerUI(options =>
    {
        options.SwaggerEndpoint("/openapi/v1.json", "v1");
    });
}
```

导航到 `/swagger`，您将看到标准的 Swagger UI 界面。

## 自定义生成的输出 ✨

有时您可能需要调整 OpenAPI 规范的输出，例如通过调整端点的名称或数据模型的表示。以下是一个示例展示如何通过自定义类名来避免名称冲突：

```csharp
services.AddSwaggerGen(c =>
{
    c.CustomSchemaIds(type =>
    {
        if (type.IsNested)
        {
            // 将声明类型名称与嵌套类型名称结合
            return $"{type.DeclaringType.Name}{type.Name}";
        }

        return type.Name;
    });
});
```

## 使用 Microsoft.AspNetCore.OpenApi 进行更深入的自定义 🛠️

该库提供了一种低级机制来在生成时转换您的架构。通过定义架构转换器，可以修改由 MS 库生成的架构。

```csharp
Task Transformer(OpenApiSchema schema, OpenApiSchemaTransformerContext context, CancellationToken arg3)
{
    var type = context.JsonTypeInfo.Type;

    if (!type.IsNested)
        return Task.CompletedTask;

    const string schemaId = "x-schema-id";
    schema.Annotations[schemaId] = $"{type.DeclaringType?.Name}{type.Name}";

    return Task.CompletedTask;
}
```

## 总结 🎯

当您创建一个新的 .NET 9 Web 应用时，您会发现它正在使用 `Microsoft.AspNetCore.OpenApi` 来替代 Swagger 生成 OpenAPI 规范。这为开发者提供了更灵活的定制选项，同时也意味着需要熟悉新的配置方式，以便充分利用这一新功能。

通过掌握这些工具和技术，您可以显著提升开发效率，并更好地管理项目中的 API 文档生成。📈

准备好升级您的开发技能了吗？立即尝试 .NET 9 的新特性吧！🎉
