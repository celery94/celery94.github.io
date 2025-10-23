---
pubDatetime: 2024-03-13
tags: [".NET", "C#"]
source: https://www.devleader.ca/2024/03/12/plugin-architecture-in-c-for-improved-software-design/
author: Nick Cosentino
title: 在 C# 中使用插件架构以改善软件设计
description: 了解 C# 中的插件架构以创建可扩展的应用程序！本文通过代码片段提供示例，解释如何开始使用 C# 插件。
---

# 在 C# 中使用插件架构以改善软件设计

> ## 摘要
>
> 了解 C# 中的插件架构以创建可扩展的应用程序！本文通过代码片段提供示例，解释如何开始使用 C# 插件。
>
> 原文 [Plugin Architecture in C# for Improved Software Design](https://www.devleader.ca/2024/03/12/plugin-architecture-in-c-for-improved-software-design/)

---

我对基于插件架构的应用程序的迷恋可能源自于我玩角色扮演游戏的历史。这些游戏通常需要能够通过插件扩展机制或通过插件添加新内容的系统。由于我学习 C# 并制作游戏的早期经历，C# 应用程序中的插件架构很自然地成为了我经常学习的内容。

在这篇文章中，我将向您介绍插件架构的概念，特别是看看 C# 中的插件架构以及我们如何可以探索加载插件信息。我们还将看一些插件在哪些情况下会很有价值的高层次示例 - 但实现这些示例的更多细节是你可以作为作业来做的活动！让我们深入了解吧！

---

## 理解插件架构

那么，关于软件构建，什么是插件架构呢？[插件架构是一种设计模式](https://www.devleader.ca/2023/09/07/plugin-architecture-design-pattern-a-beginners-guide-to-modularity/ "插件架构设计模式 - 初学者的模块化入门指南")，它允许你通过动态加载和执行外部模块或插件来扩展现有应用程序的功能。这些插件可以单独开发，并且可以在不修改核心代码库的情况下添加到应用程序中。这意味着我们可以添加新功能，甚至不需要重建原始核心应用程序的代码！

[在 C# 应用程序中使用插件架构](https://www.devleader.ca/2023/09/26/blazor-renderfragment-how-to-use-plugins-to-generate-html/ "Blazor RenderFragment - 如何使用插件生成 HTML")提供了几个好处，其中一些包括：

1.  模块化：使用插件架构，应用程序的不同组件可以作为插件单独开发。这种模块化允许你专注于特定功能而不影响应用程序的整体结构。它还使得维护和更新变得更容易，因为插件可以独立添加或替换。
2.  灵活性：通过使用插件架构，你可以轻松地向应用程序引入新的功能或特性而不需要修改核心代码。这种灵活性允许快速开发和迭代，因为创建和集成新插件的工作量要小于修改核心共享代码。
3.  代码可重用性：插件可以作为可在多个项目或应用程序中使用的可重用组件开发。这种可重用性不仅节省了开发时间，而且还促进了代码一致性，并减少了引入错误的机会。
4.  定制化：插件架构允许用户或客户根据他们的特定需求定制和扩展应用程序的功能。这种定制可以通过简单地添加或删除插件来实现，而不需要更改核心代码库。

总的来说，C# 中的插件架构是我在开发中大量使用的一种模块化和灵活的构建软件的方法。[查看这个视频了解我如何使用插件系统](https://youtu.be/5OKLiQM2y30)在基于垂直切片的[应用程序中](https://www.devleader.ca/2023/12/07/exploring-an-example-vertical-slice-architecture-in-asp-net-core-what-you-need-to-know/ "探索 ASP.NET Core 中的示例垂直切片架构 - 你需要了解的")：

---

## 在 C# 中加载插件

在 C# 中，有各种各样的方法和技术可以将插件加载到你的软件解决方案中。加载插件可以为你的应用程序提供增强的功能和灵活性。让我们用代码示例探索这些方法和技术。对于以下示例，假设我们有一个 IPlugin 接口，简单地映射到以下代码：

```csharp
public IPlugin
{
    void Execute();
}
```

### 用 CSharp 的反射进行动态程序集加载

在 C# 中加载插件的一种方法是通过动态加载程序集。这允许你在运行时加载包含插件所需代码的外部 DLL 文件。这里是一个实现这一目标的示例：

```csharp
// 获取插件 DLL 的路径
string pluginPath = "path/to/plugin.dll";

// 加载插件程序集
Assembly assembly = Assembly.LoadFrom(pluginPath);

// 实例化插件类型
IEnumerable<Type> pluginTypes = assembly
    .GetTypes()
    .Where(t => typeof(IPlugin).IsAssignableFrom(t) && !t.IsAbstract);

// 创建插件实例
List<IPlugin> plugins = new();
foreach (Type pluginType in pluginTypes)
{
    IPlugin plugin = (IPlugin)Activator.CreateInstance(pluginType);
    plugins.Add(plugin);
}

// 使用插件
foreach (IPlugin plugin in plugins)
{
    plugin.Execute();
}
```

在上面的代码中，我们首先使用 `Assembly.LoadFrom` 加载插件程序集。然后我们使用反射找到所有实现 `IPlugin` 接口且不是抽象的类型。我们[使用反射创建这些插件类型的实例](https://www.devleader.ca/2024/02/26/reflection-in-c-4-code-simple-but-powerful-code-examples/ "C# 中的反射：4 个简单但强大的代码示例")- [特别是，使用 `Activator.CreateInstance`](https://www.devleader.ca/2024/02/28/activator-createinstance-in-c-a-quick-rundown/ "C# 中的 Activator.CreateInstance - 快速概述") - 并将它们存储在一个列表中。最后，我们可以通过调用它们的 `Execute` 方法来使用插件。

### 使用 Autofac 动态加载 C# 插件

我最喜欢的一种 C# 依赖注入框架是 Autofac。我们可以使用 Autofac 扫描一个目录中包含实现 `IPlugin` 接口的类型的程序集并注册它们。下面是一个用 C# 为此目的设置 Autofac 的示例：

```csharp
using Autofac;
using System.Reflection;

public class PluginLoader
{
    public IContainer LoadPlugins(string pluginsPath)
    {
        var builder = new ContainerBuilder();

        // 扫描插件目录中的程序集
        // 并注册实现 IPlugin 的类型
        var types = Directory
            .GetFiles(pluginsPath, "*.dll")
            .Select(Assembly.LoadFrom)
            .ToArray();
        builder
            .RegisterAssemblyTypes(types)
            .AssignableTo<IPlugin>()
            .As<IPlugin>();

        return builder.Build();
    }
}
```

[上面的代码将使用反射从插件目录中的程序集获取类型](https://www.devleader.ca/2023/09/15/blazor-plugin-architecture-how-to-manage-dynamic-loading-lifecycle/ "Blazor 插件架构 - 如何管理动态加载&生命周期")。在这种情况下，它将尝试从该文件夹位置加载任何带有 DLL 扩展名的文件。从那里，我们可以让 Autofac 注册这些类型，但我们使用 `AssignableTo<T>()` 方法过滤类型，只留下 IPlugin。最后，我们使用 `As<T>()` 方法表明它们可以作为 IPlugin 实例解析。

以下代码示例构建容器，注册所有插件，然后模仿前一个代码示例中的行为，我们在每个插件上调用 `Execute()`：

```csharp
// 假设插件位于应用程序目录中的“plugins”文件夹
var pluginFolder = Path.Combine(
    Directory.GetCurrentDirectory(),
    "plugins");
var pluginLoader = new PluginLoader();
var container = pluginLoader.LoadPlugins(pluginFolder);

// 解析所有 IPlugin 的实现并执行它们
foreach (var plugin in container.Resolve<IEnumerable<IPlugin>>())
{
    plugin.Execute();
}

```

我还做了[视频教程，介绍如何利用 Autofac 加载插件](https://youtu.be/-pxwL_VD4Uo)：

---

## C# 应用程序中实际插件架构的示例

现在我们已经看到了如何去实现加载插件，是时候看一些可能的 C# 应用程序中插件架构的示例了。在这些示例中，我们不会构建一个完整的应用程序，但我们可以深入一些高层次的用例细节，一个示例插件 API 可能看起来像什么，以及为什么插件可能是有用的。

### 动态数据可视化插件

[C# 中插件架构的一个有趣用例是用于动态数据可视化](https://www.devleader.ca/2023/09/26/blazor-renderfragment-how-to-use-plugins-to-generate-html/ "Blazor RenderFragment - 如何使用插件生成 HTML")。在处理大型数据集或实时数据流时，这可能特别有用。通过创建一个插件系统，你可以开发独立的可视化模块，这些模块可以在运行时根据数据的类型和格式动态加载和卸载。而不是围绕一两个可视化构建应用程序的核心，我们可以将它们视为插件，以便在应用程序演进时可以添加更丰富的可视化。

下面是我们可以考虑的一些示例代码：

```csharp
// 可视化插件的接口
public interface IVisualizationPlugin : IDisposable
{
    void Initialize();

    void RenderData(
        DataSet data,
        IVisualizationContext context);
}

// 示例插件实现
public class BarChartPlugin : IVisualizationPlugin
{
    public void Initialize()
    {
        // 初始化条形图可视化
    }

    public void RenderData(
        DataSet data,
        IVisualizationContext context)
    {
        // 使用提供的数据渲染条形图
    }

    public void Dispose()
    {
        // 清理条形图使用的资源
    }
}
```

在此示例中，我们可能希望为插件设置一些可选的入口点，以便做一些准备工作。这将是我们的 `Initialize()` 方法。我们将每个插件标记为 IDisposable，这样我们就可以确保在准备卸载它们时，每个插件都有适当的清理资源机会。`RenderData` 方法是魔法发生的地方，每个插件将能够获取传入的数据集和可视化上下文对象。这个上下文对象是编造的，当然，这将在很大程度上取决于应用程序，但它可能是允许插件直接添加 UI 控件或作为插件可以直接绘制可视化的表面的东西。

### 基于扩展的文件处理插件

C# 中可能的另一个插件架构示例是用于扩展文件处理能力。设想你有一个文件处理应用程序，支持各种文件格式，如图像、文档和视频。通过实现一个插件系统，你可以允许用户动态开发和加载自定义文件格式处理程序。

在下面的代码中，我们将看到一个插件格式，它允许我们检查插件是否可以支持文件扩展名。你可以想象，[我们有像门面（facade）类这样的东西，它会遍历每个插件](https://www.devleader.ca/2024/03/08/the-facade-design-pattern-in-c-how-to-simplify-complex-subsystems/ "C# 中的门面设计模式：如何简化复杂的子系统")看哪个支持它，并调用相关插件来处理它：

```csharp
// 文件格式插件的接口
public interface IFileFormatPlugin
{
    bool CanHandleFile(string filePath);

    void ProcessFile(string filePath);
}

// 示例插件实现
public class PDFPlugin : IFileFormatPlugin
{
    public bool CanHandleFile(string filePath)
    {
        return filePath.EndsWith("pdf", StringComparison.OrdinalIgnoreCase);
    }

    public void ProcessFile(string filePath)
    {
        // 执行 PDF 特定的文件处理
    }
}
```

### 自定义规则引擎插件

当实现一个需要复杂验证或业务规则的应用程序的自定义规则引擎时，使用插件也是有益的。通过使用插件，你可以将规则引擎分解为独立的模块，并根据特定条件或触发器动态加载和执行它们。

在下面的代码示例中，我们使用 TryX 模式，它通常具有布尔返回类型和一个 out 参数来获取结果。在这种情况下，我们可以在规则评估不符合时输出一个 Exception 实例。一种替代方法可能是[使用一个自定义多类型来创建你自己的返回类型，这个类型可以是结果或错误](https://www.devleader.ca/2023/05/31/implicit-operators-in-c-and-how-to-create-a-multi-type/ "C# 中的隐式操作符以及如何创建多类型")，或者使用 OneOf NuGet 包。让我们看看：

```csharp
// 规则插件的接口
public interface IRulePlugin
{
    string RuleName { get; }

    bool TryEvaluateRule(
        object target,
        out Exception error);
}

// 示例插件实现
public class AgeValidationPlugin : IRulePlugin
{
    public string RuleName { get; } = "AgeValidation";

    public bool TryEvaluateRule(
        object target,
        out Exception error)
    {
        // 检查目标对象是否符合年龄验证标准
    }
}
```

### 基于插件的认证系统

[插件架构](https://www.devleader.ca/2023/09/14/plugin-architecture-in-blazor-a-how-to-guide/ "插件架构在Blazor中的实现 - 教程指南")同样可以应用于认证系统，它允许集成各种认证提供者，如OAuth、Active Directory或自定义认证机制。通过创建认证插件，您可以实现灵活性，并且可以在不同的认证方法间轻松切换，而不会将您的应用程序紧密绑定到特定的实现上。

这里有一个高度简化的插件API，用于演示目标，但任何有实际操作认证系统经验的人都会意识到这很简化：

```csharp
// 认证插件的接口
public interface IAuthenticationPlugin
{
    bool AuthenticateUser(string username, string password);
}

// 示例插件实现
public class OAuthPlugin : IAuthenticationPlugin
{
    public bool AuthenticateUser(string username, string password)
    {
        // 使用OAuth协议认证用户
    }
}
```

虽然这个示例可能有点简单，但关键点是指出了用例 —— 认证在应用程序中是一个很好的可插拔点。如果您正在开发可能需要不同认证集成的东西，利用插件与每个服务接口并为您的应用提供认证将是一个很好的机会。

一个非常相关的C#中插件架构的例子是用于跟踪社交媒体指标。[在我的新闻通讯中，我分享了关于这是如何构建的幕后细节](https://www.devleader.ca/2024/01/13/take-control-of-career-progression-dev-leader-weekly-26/ "构建Blazor Web应用！- Dev Leader周刊26") 并创建了一个视频系列，您可以在YouTube上观看，详细介绍了制作应用的整个逐步过程。您可以看到[这个视频中Blazor构建系列的开始](https://youtu.be/qndnxPzjrow)，它关注于C#中的插件架构：

---

## 常见问题解答：C#中的插件架构

### 什么是插件架构？

插件架构是一种设计模式，允许通过添加插件来扩展或定制软件解决方案。

### 为什么C#应用程序中的插件架构很重要？

插件架构使C#应用程序能够更加灵活、可扩展和可维护，通过将核心功能与可选特性分离。这不是C#特有的事情，但是因为C#可以用来创建多种类型的应用程序，这表明在很多情况下插件架构可能非常有价值。

### C#应用程序中如何加载插件？

C#应用程序中可以使用各种技术加载插件，例如反射或依赖注入框架如Autofac。无论技术实现如何，类型通常会在运行时从程序集（或一些其他编译代码的来源）中加载。

### 在C#中实现插件系统的一些常用方法是什么？

实现C#中插件系统的常用方法包括使用接口或属性以及反射来发现和初始化插件。这可以与依赖注入框架结合使用，使解析插件集合感觉更加流畅和自动。

### 使用C#中的插件架构的一些例子是什么？

插件架构可能不适合每个应用程序 — 尤其是当它们非常简单时。然而，如果你正在寻找在应用程序中有可扩展特性，一些例子包括C#应用程序中数据加密、认证、日志记录和用户界面自定义的插件。
