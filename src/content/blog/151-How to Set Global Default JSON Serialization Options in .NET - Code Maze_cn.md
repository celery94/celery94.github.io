---
pubDatetime: 2024-05-22
tags: []
source: https://code-maze.com/aspnetcore-set-global-default-json-serialization-options/
author: Karthikeyan N S
title: .NET中如何设置全局默认的JSON序列化选项 - Code Maze
description: 在这篇文章中，我们将探讨在ASP.NET Core Web API中设置全局默认JSON序列化选项的各种方法。
---

# .NET中如何设置全局默认的JSON序列化选项 - Code Maze

> ## 摘要
>
> 在这篇文章中，我们将探讨在ASP.NET Core Web API中设置全局默认JSON序列化选项的各种方法。
>
> 原文 [How to Set Global Default JSON Serialization Options in .NET - Code Maze](https://code-maze.com/aspnetcore-set-global-default-json-serialization-options/)

---

JSON序列化是将.NET对象转换为JSON格式的过程，这确保了应用程序内的数据交换。在ASP.NET Core Web API中实现全局默认的JSON序列化设置，保持了应用程序间的一致性。在这篇文章中，我们将探讨在ASP.NET Core Web API中设置全局默认JSON序列化选项的各种方法。

要下载本文的源代码，您可以访问我们的[GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/json-csharp/GlobalDefaultJsonSerializationoptions)。

在我们深入这个主题之前，我们建议您阅读我们的文章[在C#中的序列化和反序列化](https://code-maze.com/serialization-deserialization-csharp/)。

## JsonSerializerOptions概述

`JsonSerializerOptions`类是`System.Text.Json`命名空间的一部分，提供了JSON序列化行为的自定义。它提供了各种设置，这些设置可以显著改变JSON序列化过程以满足特定需求。

现在，让我们看一些`JsonSerializerOptions`类的基本属性。

首先，我们有`PropertyNamingPolicy`属性，我们用它来控制JSON输出中的**属性名称大小写**，如使用`JsonNamingPolicy.CamelCase`启动属性名称的首字母为小写。

接下来，我们使用`DefaultIgnoreCondition`属性。将其设置为`JsonIgnoreCondition.WhenWritingNull`确保null值的属性从JSON输出中省略，**减小负载大小**并潜在地提高性能。

接下来是`Encoder`属性。这个属性通过正确编码JSON数据来帮助防止**XSS攻击**，通常使用`JavaScriptEncoder.Default`。

然后，我们有`Converters`属性，这是`JsonConverter`实例的列表，我们用它来自定义某些类型的序列化，这些类型默认情况下不会按预期序列化。这对于像`DateTime`或自定义业务对象等类型是有用的。

最后，我们有`WriteIndented`属性，我们用它来**用缩进和换行格式化JSON输出**，使其更易读。虽然这个属性在开发期间有助于可读性，但我们通常在生产中禁用它以减小负载大小。

## 使用GlobalJsonOptions属性设置全局默认的JSON序列化选项

ASP.NET Core中的`GlobalJsonOptions`属性决定了我们如何在整个应用程序中管理JSON数据。通过全局设置这些选项，我们保证**在应用程序的所有部分中统一处理JSON数据**。

首先，让我们在Web API项目中创建一个`Product`类：

```csharp
public class Product
{
    public int Id { get; set; }
    public string? Name { get; set; }
    public decimal Price { get; set; }
    public int Quantity { get; set; }
    public DateTime ReleaseDate { get; set; }
    public Manufacturer Manufacturer { get; set; } = new Manufacturer();
}
```

另外，让我们创建一个`Manufacturer`类：

```csharp
public class Manufacturer
{
    public string? Name { get; set; }
    public string? Location { get; set; }
}
```

这里，我们定义了两个模型类来保存产品的属性。

现在，让我们在`Program`类中配置JSON序列化选项：

```csharp
builder.Services.Configure<JsonOptions>(options =>
{
    options.JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
    options.JsonSerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    options.JsonSerializerOptions.WriteIndented = false;
    options.JsonSerializerOptions.Encoder = JavaScriptEncoder.Default;
    options.JsonSerializerOptions.AllowTrailingCommas = true;
    options.JsonSerializerOptions.MaxDepth = 3;
    options.JsonSerializerOptions.NumberHandling = JsonNumberHandling.AllowReadingFromString;
});
```

这里，我们使用`JsonOptions`类配置全局JSON序列化设置。

首先，我们设置所有基本属性。此外，我们设置`AllowTrailingCommas`来增强解析器的灵活性，设置`MaxDepth`为3，以限制序列化期间对象遍历到三个嵌套级别。这个属性对于限制嵌套对象的深度以增加性能和安全性可能是有用的。

接下来，我们启用`NumberHandling`，使用`JsonNumberHandling.AllowReadingFromString`允许从JSON字符串解析为适当的数字类型。

现在，让我们创建一个`ProductController`类并定义一个`POST`方法：

```csharp
[ApiController]
[Route("api/[controller]")]
public class ProductController : ControllerBase
{
    [HttpPost]
    public ActionResult CreateProduct(Product product)
    {
        return Ok(product);
    }
}
```

这里，我们创建了一个简单的`POST`方法，它接受`Product`对象作为输入参数并原封不动地返回它。

让我们看看我们在请求体中发送给API的产品JSON数据：

```json
{
  "Id": 1,
  "Name": null,
  "Price": 0,
  "Quantity": "5",
  "ReleaseDate": "2024-04-14T10:49:31.813Z",
  "Manufacturer": {
    "Name": "Apple",
    "Location": "California"
  }
}
```

我们使用Pascal case定义JSON属性。同时，我们将`Name`属性设置为`null`，并将`Quantity`属性设置为字符串格式。

现在，让我们检查响应：

```json
{
  "id": 1,
  "price": 0,
  "quantity": 5,
  "releaseDate": "2024-04-14T10:49:31.813Z",
  "manufacturer": {
    "name": "Apple",
    "location": "California"
  }
}
```

JSON序列化器将PascalCase名称更改为camelCase，并由于我们的`JsonIgnoreCondition.WhenWritingNull`设置，排除了`Name`属性。

`NumberHandling`属性将`Quantity`解释为数字，尽管其字符串格式。此外，启用`AllowTrailingCommas`和设置`MaxDepth`属性有助于成功响应。

## 使用**ConfigureHttpJsonOptions**设置全局默认的JSON序列化选项

当我们创建[最小API](https://code-maze.com/dotnet-minimal-api/)时，对HTTP响应专门的JSON序列化设置进行细粒度控制是必要的，这意味着将特定的JSON序列化设置专门应用于在HTTP响应中发送回客户端的数据。

`ConfigureHttpJsonOptions()`扩展方法允许我们自定义专门应用于HTTP管道的JSON选项，确保这些设置与应用程序的其他部分隔离。

接下来，让我们在`Program`类中设置`ConfigureHttpJsonOptions()`方法：

```csharp
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseUpper;
    options.SerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    options.SerializerOptions.WriteIndented = false;
    options.SerializerOptions.Encoder = JavaScriptEncoder.Default;
    options.SerializerOptions.AllowTrailingCommas = true;
    options.SerializerOptions.MaxDepth = 3;
    options.SerializerOptions.NumberHandling = JsonNumberHandling.AllowReadingFromString;
});
```

这里，我们向`IServiceCollection`添加`ConfigureHttpJsonOptions()`方法。同样地，我们设置了JSON序列化属性，就像之前一样。

接下来，让我们在`Program`类中定义一个最小API：

```csharp
app.MapPost("api/Product/create", (Product product) =>
{
    return product;
});
```

我们定义的序列化设置将应用于此响应。

[Newtonsoft.Json](https://www.newtonsoft.com/json)也称为`Json.NET`，为我们提供了各种自定义选项，这对特定应用来说是必要的。这些选项使我们能够调整如何将数据转换为JSON并从JSON转换回来以满足特定需求，这可能在`.NET Core 3.0`及之后的版本中使用较新的`System.Text.Json`库时更具挑战性。这一特性使`Newtonsoft.Json`在我们需要更多控制时特别有用。

`Newtonsoft.Json`包为我们提供了更多格式化日期和处理null值的选项。例如，它可以将日期序列化为使用各种格式的字符串，并以多种方式处理null值（忽略、包含或转换为默认值）。

首先，让我们安装`Newtonsoft.Json`包：

```bash
dotnet add package Newtonsoft.Json --version 13.0.3
```

有了这个，让我们在`Program`类中配置JSON序列化的默认设置：

```csharp
JsonConvert.DefaultSettings = () => new JsonSerializerSettings
{
    ContractResolver = new CamelCasePropertyNamesContractResolver(),
    Formatting = Formatting.Indented,
    NullValueHandling = NullValueHandling.Ignore,
    DateFormatString = "dd-MM-yyyy",
    DefaultValueHandling = DefaultValueHandling.Ignore,
    MaxDepth = 3
};
```

这里，我们使用`DefaultSettings`静态属性为我们应用程序中使用`JsonConvert()`方法的所有JSON序列化操作设置默认的`JsonSerializerSettings`。

然后，我们使用`CamelCasePropertyNamesContractResolver()`设置JSON键的默认命名策略为camel case。我们还格式化输出JSON以增强可读性。接下来，我们在结果JSON中省略了对象中的任何`null`属性，并将日期序列化为字符串，格式为“日-月-年”。

最后，我们通过设置`DefaultValueHandling.Ignore`处理属性的默认值，这会导致具有默认值的属性（如整数的0、布尔值的`false`等）在序列化时被排除。

让我们在`ProductController`类中定义一个`POST`端点：

```csharp
[HttpPost("save")]
public ActionResult SaveProduct(Product product)
{
    return Ok(JsonConvert.SerializeObject(product));
}
```

在这个动作中，我们使用`JsonConvert.Serialize()`方法序列化`product`对象。

那么，让我们看看请求体：

```json
{
  "Id": 1,
  "Name": null,
  "Price": 0,
  "Quantity": "5",
  "ReleaseDate": "2024-04-14T10:49:31.813Z",
  "Manufacturer": {
    "Name": "Apple",
    "Location": "California"
  }
}
```

我们使用Pascal case名称包括了`Name`和`Price`属性的默认值。

让我们检查响应：

```json
{
  "id": 1,
  "quantity": 5,
  "releaseDate": "14-04-2024",
  "manufacturer": {
    "name": "Apple",
    "location": "California"
  }
}
```

由于包含`null`值，`Name`属性从响应中省略。序列化将`ReleaseDate`属性格式化为“dd-MM-yyyy”样式，并且因为我们将其设置为默认值0，所以`Price`属性被忽略。

## 最佳实践和考虑因素

当我们全局更新JSON序列化设置时，仔细评估潜在影响我们**现有代码库以避免意外后果**是至关重要的。它可以改变客户端已经消费的API端点的行为，如果客户端依赖于现有的序列化格式，可能会破坏契约。我们应该逐渐实施，通过全面测试和功能开关，这可以帮助防范系统行为中的中断。

在应用程序中**一致**的JSON序列化实践是关键。它促进了可理解性并有助于预防bug。我们必须**集中和记录**序列化设置以期望整个应用程序的统一行为。

当序列化数据构成与外部系统的合同的一部分或需要长期存储时，确保**兼容性和谨慎的版本管理**至关重要。我们应该通过版本化的API引入变化，并考虑对数据存储、处理和外部消费者的影响。这种战略方法将保持数据完整性，并支持在新最佳实践出现时代码库的平稳演进。

考虑到.NET的未来，我们必须考虑这些额外的因素。Microsoft的`System.Text.Json`是新.NET应用程序的默认序列化器。即使我们选择使用`Newtonsoft.Json`，我们也应该注意到最佳实践的潜在变化，并准备根据生态系统的演变适应我们的策略。

## 结论

在这篇文章中，我们探讨了在ASP.NET Core中设置JSON序列化设置的不同方式，包括利用由System.Text.Json提供的原生选项以及由Newtonsoft.Json提供的更全面的功能。
