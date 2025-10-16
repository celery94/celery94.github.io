---
pubDatetime: 2024-03-10
tags: [".NET", "C#"]
  [
    c#,
    code,
    coding,
    csharp,
    design patterns,
    dotnet,
    facade,
    facade design pattern,
    facade pattern,
    facades,
    programming,
    software engineering,
  ]
source: https://www.devleader.ca/2024/03/08/the-facade-design-pattern-in-c-how-to-simplify-complex-subsystems/#aioseo-section-1-what-is-the-facade-design-pattern
author: Nick Cosentino
title: C#中的外观设计模式：简化复杂子系统
description: 了解C#中的外观设计模式以及它是如何简化复杂子系统的。查看这4个代码示例，了解C#中的外观模式是如何工作的！
---

# C#中的外观设计模式：简化复杂子系统

> ## 摘要
>
> 了解C#中的外观设计模式以及它是如何简化复杂子系统的。查看这4个代码示例，了解C#中的外观模式是如何工作的！
>
> 原文 [The Facade Design Pattern in C#: How to Simplify Complex Subsystems](https://www.devleader.ca/2024/03/08/the-facade-design-pattern-in-c-how-to-simplify-complex-subsystems/#aioseo-section-1-what-is-the-facade-design-pattern)

---

外观设计模式是我最喜欢的设计模式之一。在[所有的设计模式中](https://www.devleader.ca/2023/12/31/the-big-list-of-design-patterns-everything-you-need-to-know/ "设计模式大全 - 你需要知道的一切")，我发现这是我在不同应用程序中反复使用的模式。在这篇文章中，我将探讨C#中的外观设计模式 —— 因为所有的代码示例都将使用C#！我们将查看C#中外观模式的4个不同示例，以及它们是如何简化我们API调用者事物的。

---

## C#中外观设计模式的通用示例：

这里是一个如何在C#中实现外观模式的示例：

```
// 复杂子系统类
class SubsystemA
{
    public void MethodA()
    {
        Console.WriteLine("子系统 A - 方法 A");
    }
}

class SubsystemB
{
    public void MethodB()
    {
        Console.WriteLine("子系统 B - 方法 B");
    }
}

class SubsystemC
{
    public void MethodC()
    {
        Console.WriteLine("子系统 C - 方法 C");
    }
}

// 外观类
class Facade
{
    private SubsystemA subsystemA;
    private SubsystemB subsystemB;
    private SubsystemC subsystemC;

    public Facade()
    {
        subsystemA = new SubsystemA();
        subsystemB = new SubsystemB();
        subsystemC = new SubsystemC();
    }

    public void Operation()
    {
        Console.WriteLine("外观 - 操作");
        subsystemA.MethodA();
        subsystemB.MethodB();
        subsystemC.MethodC();
    }
}

// 客户端代码
class Client
{
    static void Main(string[] args)
    {
        Facade facade = new Facade();
        facade.Operation();
    }
}
```

在这个代码示例中，我们有一个由三个类组成的复杂子系统：`SubsystemA`、`SubsystemB`和`SubsystemC`。这些类代表了子系统的不同功能或组件。`Facade`类作为一个简化的接口，封装了子系统的复杂性。`Facade`类中的`Operation`方法为客户端提供了一个统一的接口来与子系统进行交互。

通过在`Facade`对象上调用`Operation`方法，客户端代码可以执行所需的操作，而无需直接与复杂的子系统类进行交互。`Facade`类在内部与各个子系统类通信，隐藏了客户端的复杂细节。

---

## 使用外观模式的C#插件架构

[在插件风格的架构中](https://www.devleader.ca/2023/09/07/plugin-architecture-design-pattern-a-beginners-guide-to-modularity/ "插件架构设计模式 - 初学者的模块化入门指南")，外观设计模式特别有用，用于抽象动态选择和与基于运行时条件或配置的各种插件进行交互的复杂性。让我们考虑一个文档处理系统，该系统需要通过插件支持不同的格式（例如，PDF、DOCX、ODT）和操作（例如，解析、呈现）。每种格式都由不同的插件处理，但客户端与外观提供的统一接口进行交互。

### 复杂子系统 - 插件！

我们有用于处理各种文档格式的插件：

- `PdfPlugin`：处理PDF文档操作。
- `DocxPlugin`：处理DOCX文档操作。
- `OdtPlugin`：处理ODT文档操作。

每个插件都实现了一个公共接口，`IDocumentPlugin`，该接口定义了文档是否支持和呈现文档的方法。我们将使用一个假想的`IRenderContext`接口，该接口将支持与能够将文档内容呈现到某种虚拟画布的交互 - 本示例不包括此内容 🙂

### IDocumentPlugin接口

让我们看一下为我们需要支持的三个插件提供的插件接口示例代码：

```
public interface IDocumentPlugin
{
    bool SupportsFormat(string filePath);

    void RenderDocument(Stream stream, IRenderContext renderContext);
}
```

现在用一些虚拟类满足我们需要支持的三个插件：

```
public class PdfPlugin : IDocumentPlugin
{
    public bool SupportsFormat(string filePath) => filePath.EndsWith(
        "pdf",
        StringComparison.OrdinalIgnoreCase);

    public void RenderDocument(
        Stream stream,
        IRenderContext renderContext) => Console.WriteLine("呈现PDF文档...");
}

public class DocxPlugin : IDocumentPlugin
{
    public bool SupportsFormat(string filePath) => filePath.EndsWith(
        "docx",
        StringComparison.OrdinalIgnoreCase);

    public void RenderDocument(
        Stream stream,
        IRenderContext renderContext) => Console.WriteLine("呈现DOCX文档...");
}

public class OdtPlugin : IDocumentPlugin
{
    public bool SupportsFormat(string filePath) => filePath.EndsWith(
        "odt",
        StringComparison.OrdinalIgnoreCase);

    public void RenderDocument(
        Stream stream,
        IRenderContext renderContext) => Console.WriteLine("呈现ODT文档...");
}
```

### 文档处理外观类

`DocumentProcessorFacade`类提供了一个简化的接口，用于根据文档格式与适当的插件进行交互，隐藏了插件选择和操作执行的复杂性：

```
public class DocumentProcessorFacade
{
    private readonly List<IDocumentPlugin> _plugins;

    public DocumentProcessorFacade()
    {
        // 注意：我可能会使用依赖注入来
        // 传入可行的插件，但这只是为了
        // 演示示例
        _plugins = new List<IDocumentPlugin>
        {
            new PdfPlugin(),
            new DocxPlugin(),
            new OdtPlugin()
        };
    }

    public void ProcessDocument(
        string filePath,
        IRenderContext renderContext)
    {
        var plugin = GetSupportedPlugin(format);
        if (plugin == null)
        {

            throw new NotSupportedException(
                $"没有找到支持文件'{filePath}'格式的插件。");
        }

        using var fileStream = File.OpenRead(filePath);
        plugin.RenderDocument(stream, renderContext);
    }

    private IDocumentPlugin GetPluginForFormat(string filePath)
    {
        return _plugins.FirstOrDefault(p => p.SupportsFormat(filePath));
    }
 }
```

这个示例演示了外观模式如何通过提供一个统一的接口（`DocumentProcessorFacade`）来简化插件风格架构中的交互，这些插件用于各种文档处理。外观处理了基于文档格式选择适当插件并执行操作的复杂性，允许客户端代码保持简单和清洁。这种方法增强了软件系统的模块化、可伸缩性和可维护性。

---

## 使用外观设计模式简化API调用

在应用程序中管理多个API调用可能是一项复杂的任务。作为软件工程师，找到简化和规范这一过程的方法非常重要。一种有效的方法是使用外观设计模式，它为子系统中的一组接口提供了一个方便的接口。在这一部分中，我们将探讨如何使用外观模式来简化和集中管理C#中的API调用。

在处理多个API时，常见的挑战包括处理认证、管理请求/响应格式和处理速率限制。如果这些任务没有得到妥善管理，可能会变得耗时且容易出错。外观模式可以帮助缓解这些挑战，提供了一个统一和简化的接口来与APIs进行交云。让我们看一个例子，了解如何实现这一点：

```
public class ApiFacade
{
    private readonly ApiAuthenticationService _authenticationService;
    private readonly ApiRequestFormatter _requestFormatter;
    private readonly ApiRateLimiter _rateLimiter;

    public ApiFacade()
    {
        _authenticationService = new ApiAuthenticationService();
        _requestFormatter = new ApiRequestFormatter();
        _rateLimiter = new ApiRateLimiter();
    }

    public ApiResponse MakeApiCall(ApiRequest request)
    {
        _authenticationService.Authenticate();
        var formattedRequest = _requestFormatter.Format(request);
        _rateLimiter.WaitIfNeeded();

        // 执行实际的API调用并检索响应
        var response = ApiClient.MakeCall(formattedRequest);

        return response;
    }
}
```

在上面的代码示例中，我们创建了一个`ApiFacade`类，它封装了认证、请求格式化和速率限制的复杂性。它使用了三个不同的服务：`ApiAuthenticationService`、`ApiRequestFormatter`和`ApiRateLimiter`。通过使用外观模式，我们可以集中管理这些服务，并公开一个方法（`MakeApiCall`），该方法负责完成API调用的所有必要步骤。

要使用`ApiFacade`类，代码库的其他部分可以简单地创建一个实例并调用`MakeApiCall`方法，传入所需的`ApiRequest`。外观类将处理认证、请求格式化、限速以及实际的API调用，简化了整个过程，减少了管理多个API调用的复杂性。

---

## 使用C#中的外观设计模式增强UIs

用户界面交互经常变得复杂，涉及一系列复杂的步骤。外观模式为简化和优化这些交互提供了一个优雅的解决方案，使它们更易于管理和高效。让我们探索如何使用外观模式通过C#中的代码示例来增强用户界面交互。

考虑一个场景，其中用户需要在客户管理系统上执行各种操作，如创建新客户、更新其信息和检索客户详细信息。这些操作涉及与多个组件交互并执行一系列步骤。

通过使用外观设计模式，我们可以创建一个统一的接口，封装这些交互的复杂性。外观类充当了一个简化的入口点，屏蔽了客户端与底层系统的复杂性，并提供了一个更简洁的API来与用户界面进行交云。

```
public class CustomerManagementFacade
{
    private readonly CustomerService _customerService;
    private readonly CustomerValidationService _validationService;
    private readonly CustomerCacheService _cacheService;

    public CustomerManagementFacade()
    {
        _customerService = new CustomerService();
        _validationService = new CustomerValidationService();
        _cacheService = new CustomerCacheService();
    }

    public void CreateNewCustomer(string name, string email)
    {
        if (_validationService.ValidateCustomerData(name, email))
        {
            _customerService.CreateCustomer(name, email);
            _cacheService.CacheCustomer(name, email);
        }
    }

    public void UpdateCustomerInformation(string name, string email)
    {
        if (_validationService.ValidateCustomerData(name, email))
        {
            _customerService.UpdateCustomer(name, email);
            _cacheService.UpdateCachedCustomer(name, email);
        }
    }

    public Customer GetCustomerDetails(string name)
    {
        var customer = _cacheService.GetCachedCustomer(name);

        if (customer == null)
        {
            customer = _customerService.GetCustomer(name);
            _cacheService.CacheCustomer(customer.Name, customer.Email);
        }

        return customer;
    }
}
```

在上述代码示例中，我们有一个`CustomerManagementFacade`类，它充当管理客户互动的外观。它封装了创建、更新和检索客户信息的操作。外观协调了`CustomerService`、`CustomerValidationService`和`CustomerCacheService`之间的交互，为客户端提供了更简单的方法。

有了外观模式，客户端代码只需要与外观类交互，而不需要担心与每个单独组件的详细交互。这样简化了代码库，减少了复杂性，并允许更容易地进行维护和扩展。

---

## 总结C#中的外观设计模式

总之，我们探索了C#中的外观设计模式，并通过代码示例讨论了4个有趣的用例。外观模式提供了一个简化的接口来处理复杂的子系统，使其更易于理解和使用。希望这些示例有助于展示在不同情况下利用外观可以为调用代码带来更大简化的不同场景。

理解并使用设计模式，如外观模式，对于软件工程师来说是很重要的。这些模式提供了通用软件工程问题的经过验证的解决方案，并提供了一种结构化的方法来设计健壮和可扩展的应用程序。通过将设计模式纳入我们的开发实践中，我们可以创建更高效、更灵活、更易于维护的软件解决方案 — 但[理解哪些设计模式最适合哪里需要一些实践](https://www.devleader.ca/2023/12/31/the-big-list-of-design-patterns-everything-you-need-to-know/ "设计模式大全 - 你需要知道的一切")！

进一步尝试外观模式，并考虑在你的C#项目中实施它 — 这确实是我最喜欢使用的设计模式之一。如果你觉得这很有用，且你正在寻求更多学习机会，考虑[订阅我的免费每周软件工程时事通讯](https://subscribe.devleader.ca/ "订阅Dev Leader每周")，并查看我的[免费YouTube视频](https://www.youtube.com/@devleader?sub_confirmation=1 "Dev Leader - YouTube")！

---

## 常见问题解答：C#中的外观设计模式

### 什么是外观设计模式？

外观设计模式是一种软件设计模式，为复杂的系统或子系统提供了一个简化的接口。它允许客户端通过统一的接口与系统进行交互，隐藏了底层实现的复杂性。

### 为什么理解和实施设计模式在软件工程中很重要？

[理解和实施设计模式](https://www.devleader.ca/2023/12/31/the-big-list-of-design-patterns-everything-you-need-to-know/ "设计模式大全 - 你需要知道的一切")在软件工程中很重要，因为它促进了可重用和可维护的代码。设计模式提供了常见设计问题的经过验证的解决方案，有助于改善软件架构、可伸缩性和可维护性。

### Facade设计模式如何简化复杂的子系统？

Facade模式通过提供一个更高层次的接口，封装并隐藏底层组件的复杂性，从而简化复杂的子系统。它充当客户端的单一入口点，允许客户端与子系统交互，而无需了解其内部工作机制。

### Facade设计模式在管理API调用时面临哪些挑战？

Facade模式通过提供一个集中的接口来处理多个API调用，解决了管理API调用的挑战。它帮助抽象化调用的复杂性，管理认证，处理错误以及处理响应，使API集成更加流畅，更易于维护。

### Facade设计模式如何帮助插件架构？

Facade模式可以隐藏在不同情况下选择激活/使用哪个插件的复杂性。假设插件的用例是在不同情况下提供功能。这种情况下，调用者可以向Facade提供情境上下文，但完全隐藏行为。Facade处理复杂的工作，使之对调用者看起来简单。

### Facade模式如何增强用户界面交互？

Facade模式通过简化和优化用户界面与底层系统之间的交互来增强用户界面交互。它将复杂的UI操作，如表单验证，数据检索和展示逻辑，抽象成一个统一且用户友好的接口，提高了可用性和可维护性。
