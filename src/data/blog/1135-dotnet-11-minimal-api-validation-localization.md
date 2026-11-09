---
pubDatetime: 2026-11-09T09:37:26+08:00
title: ".NET 11：让 Minimal API 验证消息支持多语言"
description: "使用 .NET 11 的内置验证本地化功能，为 Minimal API 配置请求语言、资源文件和字段显示名称，并通过实际请求检查错误消息、语言回退与常见资源查找问题。"
tags: ["DotNet", "ASP.NET Core", "CSharp"]
slug: "dotnet-11-minimal-api-validation-localization"
ogImage: "../../assets/1135/01-cover.jpg"
source: "https://khalidabuhakmeh.com/posts/minimal-api-validation-localization/"
---

同一个客户创建接口，中文用户提交空姓名时需要看到中文错误，英文用户则需要英文提示。.NET 11 的 `Microsoft.Extensions.Validation` 可以根据请求语言查找验证消息和字段名称：注册本地化与验证服务，配置请求语言，再为模型准备 `.resx` 资源文件即可。

下面用一个 Minimal API 展示完整配置，并检查资源键、语言回退和常见错误。原文作者的示例基于 .NET 11 RC1，文中报告了四种语言的集成测试结果；本文按同一功能编写中文示例，使用前请确认项目 SDK 支持该版本。

## 准备接口和模型

安装 .NET 11 SDK 后，新建空的 ASP.NET Core 项目，项目名使用 `ValidationDemo`。下面的资源路径依赖这个项目名和模型命名空间；如果改名，需要同步调整。

```bash
dotnet new web -n ValidationDemo --framework net11.0
cd ValidationDemo
```

将 `Program.cs` 改为：

```csharp
using ValidationDemo;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddLocalization(options => options.ResourcesPath = "Resources");
builder.Services.AddValidation();

var cultures = new[] { "zh-CN", "en-US" };
builder.Services.Configure<RequestLocalizationOptions>(options =>
{
    options.SetDefaultCulture("zh-CN");
    options.AddSupportedCultures(cultures);
    options.AddSupportedUICultures(cultures);
});

var app = builder.Build();

app.UseRequestLocalization();
app.MapPost("/customers", (Customer customer) => Results.Ok(customer));
app.Run();

public partial class Program;
```

`AddValidation()` 为支持的 Minimal API 参数启用自动验证；`AddLocalization()` 注册资源查找服务。`UseRequestLocalization()` 根据请求设置语言，需要放在处理请求的端点之前。验证失败时，处理函数不会执行，接口返回 HTTP 400 和验证错误。

在项目根目录新建 `Customer.cs`：

```csharp
using System.ComponentModel.DataAnnotations;
using Microsoft.Extensions.Validation;

namespace ValidationDemo;

[ValidatableType]
public class Customer
{
    [Display(Name = "CustomerName")]
    [Required(ErrorMessage = "NameRequired")]
    [StringLength(50, MinimumLength = 2, ErrorMessage = "NameLength")]
    public string? Name { get; set; }

    [Required]
    [EmailAddress]
    public string? Email { get; set; }

    [Range(18, 120)]
    public int Age { get; set; }
}
```

`[ValidatableType]` 将类型标记给验证源生成器。`Display` 指定字段显示名称的资源键；两个显式的 `ErrorMessage` 值也用作资源键。`Email` 和 `Age` 则使用约定的键。

## 添加中英文资源

在项目中创建 `Resources` 文件夹，分别新建 `Customer.zh-CN.resx` 和 `Customer.en-US.resx`。可以使用支持 `.resx` 的编辑器创建字符串资源，按下表填入名称和值；花括号里的数字是格式化占位符，需要原样保留。

| 名称                          | `Customer.zh-CN.resx`           | `Customer.en-US.resx`                           |
| ----------------------------- | ------------------------------- | ----------------------------------------------- |
| `CustomerName`                | 客户姓名                        | customer name                                   |
| `NameRequired`                | {0}为必填项。                   | The {0} field is required.                      |
| `NameLength`                  | {0}长度须为 {2} 到 {1} 个字符。 | The {0} must be between {2} and {1} characters. |
| `RequiredAttribute_Error`     | {0}为必填项。                   | The {0} field is required.                      |
| `EmailAddressAttribute_Error` | {0}须为有效的电子邮件地址。     | The {0} must be a valid email address.          |
| `RangeAttribute_Error`        | {0}须在 {1} 到 {2} 之间。       | The {0} must be between {1} and {2}.            |

这里 `{0}` 是显示名称。`StringLength` 的 `{1}` 是最大长度，`{2}` 是最小长度；`Range` 的 `{1}` 和 `{2}` 分别是最小值和最大值。本例只给 `Name` 配置了 `Display`，因此其他字段仍显示 `Email` 和 `Age`。需要翻译它们时，可分别添加 `Display` 和对应资源键。

默认资源按声明成员的类型查找。示例的根命名空间为 `ValidationDemo`，模型为 `ValidationDemo.Customer`，因此路径是 `Resources/Customer.zh-CN.resx`。如果模型改为 `ValidationDemo.Models.Customer`，路径应改为 `Resources/Models/Customer.zh-CN.resx`，也可使用 `Resources/Models.Customer.zh-CN.resx`。资源文件应放在声明模型的项目中。

## 资源键怎样匹配

显式设置了 `ErrorMessage` 时，验证器先用该值查找。例如 `NameRequired` 找到的模板会用本地化后的 `CustomerName` 填充。如果没有找到对应资源，显式设置的值会作为文本使用；看到 `NameRequired` 出现在响应中时，应检查键名和资源路径。

未设置 `ErrorMessage` 时，验证器按从具体到通用的顺序尝试约定键。例如 `Customer.Age` 的 `[Range]` 依次查找：

1. `Customer_Age_RangeAttribute_Error`
2. `Customer_RangeAttribute_Error`
3. `RangeAttribute_Error`

资源都不存在时，验证器使用特性自带的默认消息。通用键可以减少同一模型内的重复翻译；默认查找仍按类型进行，多个模型需要共用同一资源文件时，可以通过 `ValidationOptions.LocalizerProvider` 指定共享资源。

## 发送请求检查结果

启动项目后，按终端显示的地址替换下面的 `http://localhost:5000`。执行以下命令，发送无效数据并请求中文消息：

```bash
curl -i -X POST http://localhost:5000/customers \
  -H "Content-Type: application/json" \
  -H "Accept-Language: zh-CN" \
  -d '{"name":"","email":"invalid","age":5}'
```

在 PowerShell 中可以使用 `curl.exe`；不同 shell 对 JSON 引号的处理可能不同。成功时响应状态为 `400`，响应体的 `errors` 中应包含 `Name`、`Email` 和 `Age`，例如 `Name` 包含「客户姓名为必填项。」。将请求头改为 `Accept-Language: en-US`，应看到英文消息，例如 `The customer name field is required.`。

请求语言默认依次从查询字符串、Cookie 和 `Accept-Language` 请求头中选择，因此已有查询参数或 Cookie 可能覆盖请求头。也可以用 `/customers?culture=en-US` 测试查询参数。应用只支持 `zh-CN` 和 `en-US`；当请求语言无法匹配支持列表时，本例回退到默认的 `zh-CN`。

## 没有得到预期语言时检查什么

- **消息显示资源键**：检查 `ErrorMessage` 和 `.resx` 中的键是否一致，以及文件路径是否匹配模型的完整命名空间。
- **显示默认消息**：检查约定键是否包含完整特性名，例如 `RangeAttribute_Error`；同时确认 `.resx` 已包含在声明模型的项目中。
- **始终返回同一种语言**：检查是否调用了 `UseRequestLocalization()`、目标语言是否在支持列表中，以及查询参数或 Cookie 是否覆盖了请求头。资源查找使用 `CurrentUICulture`。
- **模型位于类库时没有按预期验证**：源生成器的处理范围受程序集影响。原文建议在模型所在类库引用 `Microsoft.Extensions.Validation`，并在该程序集提供由宿主调用的 `AddValidation` 扩展方法。

上线前，建议针对每种支持语言测试一次无效输入，再测试不支持的语言和缺失资源键。已有 MVC 或 Razor Pages 的项目应继续按其自身的数据注解本地化方式配置；迁移 Minimal API 时也要确认自定义验证和现有错误响应契约是否仍符合客户端预期。

## 参考

- [Localize Minimal API Validation Messages in .NET 11](https://khalidabuhakmeh.com/posts/minimal-api-validation-localization/)
- [What's new in ASP.NET Core in .NET 11](https://learn.microsoft.com/en-us/aspnet/core/release-notes/aspnetcore-11)
- [Validation in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/validation/overview?view=aspnetcore-11.0)
- [Select language and culture in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/localization/select-language-culture?view=aspnetcore-11.0)
