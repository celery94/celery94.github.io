---
pubDatetime: 2024-05-17
tags: [".NET", "ASP.NET Core"]
source: https://code-maze.com/aspnetcore-using-source-generators-to-validate-ioptions/
author: Ivan Gechev
title: 在ASP.NET Core中使用Source Generators验证IOptions
description: 在本文中，我们将探讨如何使用Source Generators来验证IOptions，确保它们满足所需的配置期望。
---

# 在ASP.NET Core中使用Source Generators验证IOptions

> ## 摘要
>
> 在本文中，我们将探讨如何使用Source Generators来验证IOptions，确保它们满足所需的配置期望。
>
> 原文 [Using Source Generators to Validate IOptions in ASP.NET Core](https://code-maze.com/aspnetcore-using-source-generators-to-validate-ioptions/) 由 Ivan Gechev 撰写。

---

在本文中，我们将探讨如何使用Source Generators来验证IOptions并确保它们满足所需的配置期望。

要下载本文的源代码，您可以访问我们的 [GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/aspnetcore-webapi/ValidationForConfigurationData)。

## 为什么我们需要验证IOptions

在ASP.NET Core中，我们有许多配置提供程序的选择。这给了我们在设置配置数据时的自由度。但是如果配置数据设置不正确，不符合我们的需求会发生什么呢？这可能导致安全问题、运行时失败或意外行为。

**当我们在应用中验证配置数据时，我们可以预防错误配置。更重要的是，通过添加验证，我们强制执行约束，确保应用能够按预期运行。**

在本文中，我们将选择options模式：

```csharp
public class NotificationOptions
{
    [Required]
    public string Sender { get; init; }
    [Required]
    public bool EnableSms { get; init; }
    [Required]
    public bool EnableEmail { get; init; }
    [Required]
    [Range(1, 10)]
    public int MaxNumberOfRetries { get; init; }
}
```

我们创建`NotificationOptions`类并添加了一些我们需要进行正确处理通知的属性。我们还使用属性来装饰这些属性，指定它们必须遵循的不同条件。

接下来，我们添加我们的设置：

```json
"NotificationOptions": {
  "Sender": "Code-Maze",
  "EnableSms": false,
  "EnableEmail": true,
  "MaxNumberOfRetries": 3
}
```

在我们的`appsettings.json`文件中，我们添加了`NotificationOptions`部分及其对应的属性。

让我们看看如何利用Source Generators来执行验证！

## 如何使用Source Generators来验证IOptions

使用.NET 8，我们可以利用Source Generators创建验证器：

```csharp
[OptionsValidator]
public partial class ValidateNotificationOptions : IValidateOptions<NotificationOptions>
{
}
```

我们创建`ValidateNotificationOptions`类，然后实现`IValidateOptions<TOptions>`接口。下一步是使类成为`partial`类并用`OptionsValidator`属性进行装饰。通过在空的partial类上使用该属性，该类实现了`IValidateOptions<TOptions>`接口，我们指示编译器使用Source Generators为我们创建该接口的实现。

> 你不熟悉Source Generators？那么请查看我们的文章[Source Generators in C#](https://code-maze.com/csharp-source-generators/)。

接下来，我们注册我们的选项：

```csharp
builder.Services.AddOptions<NotificationOptions>()
    .BindConfiguration(nameof(NotificationOptions));
```

在我们的`Program`类中，我们使用`AddOptions()`和`BindConfiguration()`方法。前者，我们注册我们的`NotificationOptions`类，后者我们将它们绑定到`appsettings.json`文件的相应部分。

我们还有最后一步：

```csharp
builder.Services.AddSingleton<IValidateOptions<NotificationOptions>, ValidateNotificationOptions>()
```

在这里，我们以*Singleton*生命周期注册了我们的`IValidateOptions<TOptions>`接口实现。现在，每次我们请求一个`IOptions<NotificationOptions>`实例时，编译器将尝试构造它并根据我们使用的属性验证其属性。如果任何值不符合定义的约束，将在运行时抛出异常。

## 在使用Source Generators时，在启动时验证IOptions

运行时异常可能非常麻烦，导致不希望的问题。让我们看看如何解决它们：

```csharp
builder.Services.AddSingleton<IValidateOptions<NotificationOptions>, ValidateNotificationOptions>()
    .AddOptionsWithValidateOnStart<NotificationOptions>();
```

再次，在`Program`类中，我们添加了`AddOptionsWithValidateOnStart<TOptions>()`方法的调用。这将在应用启动时验证我们的`NotificationOptions`类，防止不希望的运行时错误。

如果您熟悉Options模式，但不知道在编写测试时如何模拟它，您应该查看我们的文章[How to Mock IOptions in ASP.NET Core](https://code-maze.com/csharp-mock-ioptions/)。

这仍然会在我们的配置数据存在问题时导致程序崩溃。虽然这可能不愉快，但它将确保我们不能在正确配置之前部署我们的应用程序。

## 结论

在本文中，我们探索了如何使用Source Generators验证IOptions对于维护应用完整性和安全性至关重要。通过在应用启动时采用验证，我们主动解决配置问题，确保我们只部署正确配置的应用。虽然这可能引入初期的运行时异常，但这是在部署前保证正确配置的必要步骤。总体而言，健壮的验证实践对于维持我们应用的完整性和有效性至关重要。
