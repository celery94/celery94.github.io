---
pubDatetime: 2024-03-01
tags:
  [
    asp,
    asp.net,
    asp.net core,
    autofac,
    c#,
    csharp,
    dependency injection,
    di,
    di frameworks,
    dotnet,
    dotnet core,
    inversion of control,
    iservicecollection,
    simple injector,
    c# / .net / dotnet,
    programming,
    software engineering,
  ]
source: https://www.devleader.ca/2024/02/21/iservicecollection-in-c-simplified-beginners-guide-for-dependency-injection/
author: Nick Cosentino
title: C# 中的 IServiceCollection - 简化版初学者指南
description: 了解C#中的IServiceCollection和依赖注入。看看依赖反转、单一责任和开放/封闭原则是如何结合在一起的！
---

# C# 中的 IServiceCollection - 简化版初学者指南

> ## 摘录
>
> 了解C#中的IServiceCollection和依赖注入。看看依赖反转、单一责任和开放/封闭原则是如何结合在一起的！
>
> 原文[IServiceCollection In C# – Simplified Beginner’s Guide For Dependency Injection](https://www.devleader.ca/2024/02/21/iservicecollection-in-c-simplified-beginners-guide-for-dependency-injection/)

---

依赖注入是一种用于构建可测试、可维护和可扩展代码的有用技术。它涉及将对象的实例（或“依赖”）作为参数传递给需要它们的其他对象，从上至下地提供它们。我们将在C#中查看作为内置解决方案的`IServiceCollection`，它提供了一种方便的方式来注册和解析依赖。虽然我[以前更喜欢Autofac](https://www.devleader.ca/2023/09/12/how-to-implement-the-decorator-pattern-with-autofac/ "如何使用Autofac实现装饰器模式")，但我认为有必要回过头来重新审视我们可以访问的内置机制。

使用依赖注入框架有几个好处，比如最小化对象之间的紧密耦合、简化单元测试并促进单一责任原则。通过使用C#代码中的`IServiceCollection`来管理依赖，您可以朝着更模块化的代码方向努力，这些代码更易于长期维护和测试。

在本文中，我将解释C#中的依赖注入与`IServiceCollection`。我们将涵盖`IServiceCollection`的基础知识，深入研究依赖注入的核心原则，探索一些额外的技巧等等。通过阅读本文，您应该对利用依赖注入创建可扩展且可维护的软件感到自信——那么让我们开始吧！

---

## C# 中 IServiceCollection 的基础知识

在dotnet中，`IServiceCollection`接口用于在.NET Core应用程序中注册依赖。它是我们在特别是搭建ASP.NET Core应用程序时看到的一个基本部分。如果你已经构建了一个ASP.NET Core网络应用程序——惊喜，即使你不知道，你也在使用它！

`IServiceCollection` API易于使用，并[简化了.NET Core应用程序中的依赖注册](https://www.devleader.ca/2023/09/17/automatic-module-discovery-with-autofac-simplified-registration/)。当创建一个服务集合时，它将使用如下方法来注册依赖:

- AddSingleton: 用于在应用程序的生命周期内创建依赖的单个实例
- AddTransient: 每次请求时都创建一个新的实例
- AddScoped: 在作用域内每个请求都创建一个新的实例。

### 使用 IServiceCollection 管理依赖关系

使用`IServiceCollection`的好处之一是依赖项的管理性得到了改善。它允许在注册服务时清晰地分离关注点，并且比硬编码依赖项更容易维护。C#中的`IServiceCollection`还促进了代码重用并有助于测试，使测试过程更有效率。当`IServiceCollection`与其他依赖注入库一起使用时，注册过程可能变得更简单。

下面是一个如何使用IServiceCollection的简单代码示例：

```
public void ConfigureServices(IServiceCollection services)
{
    services.AddMvc();
    services.AddSingleton<IMyService, MyService>();
    services.AddTransient<BookService>();
}
```

这个例子注册了作为单例依赖的`IMyservice`，这意味着在应用程序的整个生命周期内创建了服务的单个实例。`BookService`被注册为瞬态依赖项，这意味着每次请求时都会创建一个新的实例。最后，`AddMvc()`方法用于注册MVC框架——你可能以前见过！

---

## 依赖注入的核心原则

依赖注入是遵循两个基本概念的设计原则，即控制反转（IoC）和依赖反转原则（DIP）。IoC描述了[程序中类之间的控制如何传递](https://www.devleader.ca/2023/10/06/strong-coding-foundations-what-are-the-principles-of-programming-languages/)，DIP描述了通过引入抽象减少类依赖的设计原则。

### 依赖注入中的单一责任原则

单一责任原则（SRP）是面向对象编程中的一个核心[原则](https://www.devleader.ca/2023/10/06/strong-coding-foundations-what-are-the-principles-of-programming-languages/)，它描述了一个类应该拥有单一责任的需求。在依赖注入中应用SRP是有用的，因为它有助于确保每个类只有一个变更的理由，这加快了开发速度并减少了错误的可能性。

通过隔离每个类的责任，我们可以使用依赖注入来解耦它们的依赖关系，使代码易于维护和测试。但是，如果依赖注入如何立即带来好处不是很明显，想一下分解一个类的过程。即使您的方法是解耦的，您仍然需要将东西移动到新的类中，将它们正确地实例化在正确的地方，通过构造函数在正确的地方传递它们等等……

依赖注入可以几乎微不足道地将依赖关系传递到您的类中。通过在依赖注入容器中将事物连接起来（本文的范围内为C#中的`IServiceCollection`），DI框架本身为您自动解析这些问题。再见手动努力！

### 依赖注入中的开放/关闭原则

开放/封闭原则（OCP）指出，类应该对扩展开放，但对修改封闭。设计代码的理念是可以轻松地扩展而不修改原始代码的行为。应用开放/封闭原则，我们可以使用依赖注入创建更加灵活、可维护和可测试的代码。通过创建符合OCP的代码，依赖注入可以使开发人员在不修改现有代码的情况下替换实现——而变化越少，爆炸的表面积就越小。

### 将这些结合在一起

在使用依赖注入时，单一责任原则和开放/封闭原则都很有帮助。通过隔离类的责任和设计不修改现有行为即可扩展代码的代码，依赖注入简化了开发。这是因为我们同时在促进模块化、可扩展性和可测试性，提高了代码质量和可维护性。对于所有这些，不爱它吗？

与依赖注入配合使用这些原则的一个例子是创建一个取决于接口而不是具体实现的类。这样，当实施该类时，我们可以轻松地用一个符合同一接口的新实现替换原来的实现，而不需要更新原始类。如果你是立即觉得这太过分的阵营（当然，不是每个类都需要一个接口），至少在你需要在测试中模拟外部依赖的情况下考虑一下。

---

## C# 中 IServiceCollection 与其他 DI 容器的比较

当涉及到依赖注入（DI）时，有很多工具和库可供选择，每个工具和库都有其优势和劣势。对于.NET Core，最受欢迎的DI容器之一是IServiceCollection，但与其他容器相比，它如何呢？

### IServiceCollection 以外的替代 DI 容器

一个[流行的DI容器是Autofac，我个人最喜欢](https://www.devleader.ca/2023/08/22/dependency-injection-how-to-start-with-autofac-the-easy-way/ "依赖注入：如何用Autofac轻松入门")，它提供了广泛的功能，包括实例和程序集扫描，这些功能是`IServiceCollection`默认不提供的。与`IServiceCollection`相比，Autofac能够处理更复杂和定制的场景，后者有一个更简单的API。然而，Autofac对于小到中等规模的项目可能过于复杂，需要更多的样板代码。同样重要的是要注意，`IServiceCollection`这些年已经有了很大的发展，虽然我喜欢Autofac，但我相信功能之间的差距正在迅速缩小。

另一个流行的DI容器是Simple Injector，它专注于性能和编译时验证。它的API类似于`IServiceCollection`，但是它对注册和验证有一个更严格的模型。Simple Injector适合中大型应用程序，并可以实现高性能基准，但在处理多个依赖时可能会出现问题。我没有使用过这个的专业经验，但我想提一下。

[也要考虑Scrutor这类东西](https://www.devleader.ca/2024/02/23/scrutor-vs-autofac-in-c-what-you-need-to-know/ "Scrutor vs Autofac在C#中：您需要知道的事情")，所以请保持关注！

### 使用 C# 中的 IServiceCollection 而不是其他 DI 容器的优势

尽管Autofac和Simple Injector很受欢迎，但IServiceCollection仍然是大多数.NET Core开发人员的首选。使用`IServiceCollection`的主要优势之一是它与.NET Core的集成，这允许在Startup.cs中进行DI注册。此外，`IServiceCollection`可以很容易地与其他依赖注入库（如Autofac或Simple Injector）集成，以便在出现更复杂的场景时使用。它立即在ASP.NET Core中可用，无需引入额外的依赖，这是一个巨大的胜利。下面是一个快速片段，向您显示是的，Autofac可以直接与`IServiceCollection`结合使用：

```
builder.Services.AddAutofac(); // 允许在容器中注册autofac！
builder.Services.AddRazorPages();
builder.Services.AddServerSideBlazor();
builder.Services.AddBlazorBootstrap();
```

`IServiceCollection`的另一个重要优势是其简单性和灵活性。其API简单易懂，非常适合小到中等规模的项目以及一般的DI入门。它的灵活性允许您根据需要添加高级功能，比其他DI容器更平滑的学习曲线。

总的来说，在IServiceCollection和其他DI容器之间的选择主要取决于项目的规模、具体要求和您在每个方面的经验水平。然而，在大多数情况下，`IServiceCollection`提供所需项目的灵活性，而不牺牲基本功能——这是来自一个Autofac粉丝的说法！

---

## 与 DI 和 C# 中的 IServiceCollection 相关的进一步概念

依赖注入（DI）使我们作为.NET开发人员可以轻松地添加新功能，提高代码的灵活性。在本节中，我将介绍一些稍微高级一点的DI概念，可以通过使用C#中的`IServiceCollection`来应用这些概念。

### 如何将依赖注入与接口一起使用

与依赖注入相关的最佳实践建议应使用接口来减少类依赖并抽象代码的功能。通过定义一个接口，您可以在应用程序组件之间创建明确的关注点分离，使DI能够更强大、更高效地工作。

当然，也有越来越多的人讨厌接口，因为他们认为接口是臃肿的。争论是，它只是一个额外的文件，而且在大多数情况下实际上将一个实现换成另一个的可能性几乎为零。对于我来说，我发现添加接口几乎没有开销，并且如果我需要交换实现，我会觉得额外的安全感觉得很好……这对我来说，几乎每次我想去写一个类的编码测试而不使用真正的依赖时都会这样。

### 创建带有依赖注入的服务的最佳实践

创建带有DI的服务的最佳实践是[设计代码以使其模块化](https://www.devleader.ca/2023/09/07/plugin-architecture-design-pattern-a-beginners-guide-to-modularity/)、可扩展和易于理解。应该在可能的情况下利用抽象来使代码更加[灵活，减少对特定实现的依赖](https://www.devleader.ca/2023/11/22/how-to-implement-the-strategy-pattern-in-c-for-improved-code-flexibility/)。但是，基于上一节中的观点，过度抽象化显然是荒谬的……所以请记住这一点。

服务生命周期管理也很重要，以确保您的服务[高效运行并最大限度地减少](https://www.devleader.ca/2023/11/24/when-to-refactor-code-how-to-maximize-efficiency-and-minimizing-tech-debt/)内存使用。所以要考虑谁需要拥有和引用什么，以及什么生命周期。我发现在许多情况下，事情有依赖性是应用程序的整个生命周期——所以我因此默认使用了一些模式。然而，当事情不需要那种需求时，我需要更仔细地考虑如何根据需要维护那些生命周期。

### 使用依赖注入的高级技术实用示例

这是一个简单的依赖注入代码示例，遵循了上述的最佳实践。设想我们有一个需要用DI注册的`UserService`类。我们可以定义一个接口 - `IUserService` - 并在`UserService`类中创建这个接口的新实现。

我们的项目可以轻松地通过这个接口访问`UserService`的功能。我们还了解到生命周期管理的重要性，所以我们将使用`AddTransient`将我们的`IUserService`实现添加到`IServiceCollection`中。在这种情况下，我们的（人为的）要求是我们不希望服务引用被重复使用。

```
public interface IUserService
{
    void GetUserById(int id);
    void SaveUser(User user);
}

public class UserService : IUserService
{
    public void GetUserById(int id)
    {
        // ...
    }

    public void SaveUser(User user)
    {
        // ...
    }
}

public void ConfigureServices(IServiceCollection services)
{
    services.AddTransient<IUserService, UserService>();
}
```

这个例子遵循了为服务定义创建接口的最佳实践。我们还考虑了使用`AddTransient`进行生命周期管理，因为我们不想重用实例。

---

## 总结 C# 中的 IServiceCollection

在C#中，使用`IServiceCollection`进行依赖注入是一个有用的工具，你可以在你的dotnet应用程序中利用它。通过在C#应用中使用`IServiceCollection`，你可以快速高效地创建松散耦合的代码，这些代码易于维护和扩展。

我们探讨了`IServiceCollection`的基础知识和依赖注入的核心原则，如控制反转和依赖倒置原则。我还讨论了松散耦合代码的好处，特别是关于可测试性和可维护性的软件。我们还讨论了如何在C#中使用`IServiceCollection`来创建接口和创建服务的最佳实践。

重要的是要记住，虽然`IServiceCollection`是一个出色的DI容器，但它并不是唯一的选项。你应该花时间评估你的需要，并[探索其他的DI容器（比如Autofac！）](https://www.devleader.ca/2023/09/17/automatic-module-discovery-with-autofac-simplified-registration/ "自动模块发现与Autofac - 简化注册")，然后再做最终决定。如果你觉得这个有用，并且你正在寻找更多的学习机会，考虑[订阅我的免费每周软件工程新闻](https://subscribe.devleader.ca/ "订阅Dev Leader周刊")并查看我的[免费YouTube视频](https://www.youtube.com/@devleader "Dev Leader - YouTube")！

---

## 常见问题解答：C# 中的 IServiceCollection

### C# 中的 IServiceCollection 是什么？

IServiceCollection是C#中内置的一个容器，用于注册和解决依赖注入中的依赖关系。这通常是.NET中构建的ASP.NET Core应用程序默认使用的。

### 使用C#中的IServiceCollection有什么好处？

使用IServiceCollection可以更容易地管理和组织依赖关系，以及更好地控制对象的生命周期和作用域。它易于使用且无需外部依赖即可获取。

### 控制反转的概念是什么？

控制反转是一种设计方法，可以将依赖关系与使用这些依赖关系的代码分离，并依赖于容器来管理和解决这些依赖关系。

### 松散耦合代码有什么好处？

松散耦合代码允许在代码库中更容易进行测试、维护和灵活性。当代码松散耦合时，在一个地方进行更改应该对其他地方影响很小或没有影响，从而减少需要测试/更新的范围。

### 单一职责原则如何与依赖注入相关？

单一职责原则指出一个类应该只有一个并且只有一个职责。通过使用依赖注入，管理依赖关系的责任从类中提取出来，并放在一个单独的容器中，允许类仅专注于其预期的职责。

### 开闭原则的好处是什么？

开闭原则指出，一个类应该对扩展开放，对修改关闭。遵循这一原则，可以在不修改现有代码库的情况下轻松扩展代码，从而易于维护、测试和灵活性。

### C#中的IServiceCollection与其他DI容器相比如何？

IServiceCollection在C#中是一个内置容器，而其他DI容器如Autofac和Ninject是第三方库。然而，IServiceCollection提供了依赖注入的简便且轻量级的方法，而不牺牲功能。IServiceCollection在C#中允许与.NET Core应用程序更容易集成，并减少项目中所需的第三方依赖量。
