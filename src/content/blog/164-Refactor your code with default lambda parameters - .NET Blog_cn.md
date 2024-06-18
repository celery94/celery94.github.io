---
pubDatetime: 2024-06-18
tags: []
source: https://devblogs.microsoft.com/dotnet/refactor-your-code-with-default-lambda-parameters/
author: David Pine
title: 使用默认 lambda 参数重构你的代码 - .NET 博客
description: 探索使用 C# 12 新特性——默认 lambda 参数 ——重构 C# 代码的机会。
---

# 使用默认 lambda 参数重构你的代码 - .NET 博客

> ## 摘要
>
> 探索使用 C# 12 新特性——默认 lambda 参数——重构 C# 代码的机会。

---

2024年6月17日

这是探讨 C# 12 特性的四篇系列文章的最后一篇。在这篇文章中，我们将探索“默认 lambda 参数”特性，它使开发者能够在 lambdas 中表达默认参数值。这个系列文章涵盖了很多内容：

1. [使用主要构造函数重构你的 C# 代码](https://devblogs.microsoft.com/dotnet/csharp-primary-constructors-refactoring/)
2. [用集合表达式重构你的 C# 代码](https://devblogs.microsoft.com/dotnet/refactor-your-code-with-collection-expressions/)
3. [通过为任何类型起别名来重构你的 C# 代码](https://devblogs.microsoft.com/dotnet/refactor-your-code-using-alias-any-type/)
4. 使用默认 lambda 参数重构你的 C# 代码（本文）

这些特性是我们增强代码可读性和可维护性持续努力的一部分。让我们详细探讨它们！

## 默认 lambda 参数 🧮

默认 lambda 参数是 C# 12 的新特性，允许开发者在 lambdas 中表达默认参数值。此特性是现有 C# 方法中默认参数特性的一种自然扩展。

### C# 12 之前 🕰️

在 C# 12 之前，当你定义一个需要提供某种默认行为的 lambda 表达式时，你必须使用空合并运算符 (`??`) 或条件运算符 (`?:`)。考虑以下示例：

```csharp
var IncrementBy = static (int source, int? increment) =>
{
    // 等同于 source + (increment.HasValue ? increment.Value : 1)
    return source + (increment ?? 1);
};

Console.WriteLine(IncrementBy(5, null)); // 6
Console.WriteLine(IncrementBy(5, 2));    // 7
```

### C# 12 中 🤓

相反，现在通过默认 lambda 参数，你可以直接在 lambda 表达式中定义参数的默认值。默认 lambda 参数的语法类似于方法中的默认参数语法。默认值在参数名称后面通过等号 (`=`) 指定。请看下例：

```csharp
var IncrementBy = static (int source, int increment = 1) =>
{
    return source + increment;
};

Console.WriteLine(IncrementBy(10));     // 11
Console.WriteLine(IncrementBy(10, 20)); // 30
```

在默认参数方面，lambda 表达式遵循与方法相同的规则。默认值必须是编译时常量，并且必须与参数类型相同。默认值在 _编译时_ 进行计算，调用 lambda 表达式时该参数是可选的。

```csharp
delegate int (int arg1, int arg2 = 1);
```

这意味着技术上你可以用参数的名称来调用 lambda 表达式，但它必须是匿名函数生成的名称。例如，考虑以下扩展示例：

```csharp
var IncrementByWithOffset = static (int source, int increment = 1, int offset = 100) =>
{
    return source + increment + offset;
};

Console.WriteLine(IncrementByWithOffset(10));             // 111
Console.WriteLine(IncrementByWithOffset(10, 20));         // 130
Console.WriteLine(IncrementByWithOffset(10, 20, 0));      // 30
Console.WriteLine(IncrementByWithOffset(10, arg2: -100)); // 10
Console.WriteLine(IncrementByWithOffset(10, arg3: 0));    // 11
```

### ASP.NET Core Minimal API 示例 🌐

让我们考虑一个使用默认 lambda 参数的 ASP.NET Core Minimal API 示例。在 Visual Studio 2022 中使用 **File** > **New** > **Project** 对话框创建一个新的 **ASP.NET Core Web API** 项目。或者，可以使用以下 .NET CLI 命令创建新项目：

```bash
dotnet new webapi -n WebApi
```

此模板创建了一个包含单个 `/weatherforecast` 端点的 ASP.NET Core Web API 项目。此 `/weatherforecast` 端点返回包含五个随机天气预报的数组，请看 _Program.cs_ 文件中的模板代码：

```csharp
var builder = WebApplication.CreateBuilder(args);

// 向容器添加服务。
// 了解更多关于 Swagger/OpenAPI 配置的信息：https://aka.ms/aspnetcore/swashbuckle
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

// 配置 HTTP 请求管道。
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

var summaries = new[]
{
    "Freezing", "Bracing", "Chilly", "Cool", "Mild", "Warm", "Balmy", "Hot", "Sweltering", "Scorching"
};

app.MapGet("/weatherforecast", () =>
{
    var forecast = Enumerable.Range(1, 5).Select(index =>
        new WeatherForecast
        (
            DateOnly.FromDateTime(DateTime.Now.AddDays(index)),
            Random.Shared.Next(-20, 55),
            summaries[Random.Shared.Next(summaries.Length)]
        ))
        .ToArray();
    return forecast;
})
.WithName("GetWeatherForecast")
.WithOpenApi();

app.Run();

internal record WeatherForecast(DateOnly Date, int TemperatureC, string? Summary)
{
    public int TemperatureF => 32 + (int)(TemperatureC / 0.5556);
}
```

模板代码中有些许代码与本讨论无太大关联。我们专注于只有 `MapGet` 功能，因为它将我们的 lambda 功能映射到 HTTP GET 调用。

```csharp
app.MapGet("/weatherforecast", () =>
{
    var forecast = Enumerable.Range(1, 5).Select(index =>
        new WeatherForecast
        (
            DateOnly.FromDateTime(DateTime.Now.AddDays(index)),
            Random.Shared.Next(-20, 55),
            summaries[Random.Shared.Next(summaries.Length)]
        ))
        .ToArray();
    return forecast;
})
.WithName("GetWeatherForecast")
.WithOpenApi();
```

`/weatherforecast` 端点返回一个含有五个天气预报的数组。`Enumerable.Range(1, 5)` 方法调用中的硬编码 5 可以用默认的 lambda 参数替换，考虑以下更新的代码片段：

```csharp
app.MapGet("/weatherforecast", (int days = 5) =>
{
    // 安全检查，确保 days 参数至少为 1，且不超过 50。
    var count = days is > 0 and <= 50
        ? days
        : 5;

    var forecast = Enumerable.Range(1, count).Select(index =>
        new WeatherForecast
        (
            DateOnly.FromDateTime(DateTime.Now.AddDays(index)),
            Random.Shared.Next(-20, 55),
            summaries[Random.Shared.Next(summaries.Length)]
        ))
        .ToArray();

    return forecast;
})
```

通过上述修改，`MapGet` 方法现在接受一个默认值为 `5` 的可选 `days` 参数。尽管依旧存在相同的默认行为，但我们将此参数公开给用户。`days` 参数可以通过查询字符串传递给 API。例如，考虑以下请求一个 21 天天气预报的 HTTP 请求：

```http
GET /weatherforecast?days=21 HTTP/1.1
Host: localhost:7240
Scheme: https
```

当查询字符串未提供 `days` 参数时，默认值会被使用。`days` 参数用于指定要生成天气预报的天数。关于 ASP.NET Core Minimal APIs 的更多信息，请参阅 [optional parameters](https://learn.microsoft.com/aspnet/core/fundamentals/minimal-apis/parameter-binding#optional-parameters)。

## 下一步 🚀

四部分的 C# 12 特性系列文章到此结束！希望你喜欢这些新特性并了解它们如何帮助你重构代码。

在本篇文章中，你了解了 C# 12 中的默认 lambda 参数特性。此特性允许开发者在 lambdas 中表达默认参数值。请务必在自己的代码中尝试此特性！更多资源请参阅以下链接：

- [C# 语言参考：Lambda 表达式](https://learn.microsoft.com/dotnet/csharp/language-reference/operators/lambda-expressions)
- [C# 语言参考：Lambda 方法组默认](https://learn.microsoft.com/dotnet/csharp/language-reference/proposals/csharp-12.0/lambda-method-group-defaults)
