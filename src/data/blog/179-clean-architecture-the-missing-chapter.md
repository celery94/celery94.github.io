---
pubDatetime: 2024-11-02
tags: ["Architecture", "Productivity", "Tools"]
source: https://www.milanjovanovic.tech/blog/clean-architecture-the-missing-chapter?utm_source=newsletter&utm_medium=email&utm_campaign=tnw114
author: Milan Jovanović
title: Clean Architecture, 缺失的一章
description: Clean Architecture著名的图示常常被误解为项目结构，导致开发者创建了人为的技术层次，将业务逻辑散布在整个代码库中。了解这个图示真正的含义，以及如何使用组件和明确的边界正确地围绕业务能力组织代码。
---

我一次又一次地看到这个错误发生。

开发者发现Clean Architecture，对其原则感到兴奋，然后……他们将著名的Clean Architecture图示变成了项目结构。

但事实是：**Clean Architecture与文件夹无关**。它关乎依赖。

Simon Brown为Uncle Bob的Clean Architecture书写了一章“缺失的章”，专门解决这个问题。然而，这一关键信息在某种程度上被忽视了。

今天，我将向你展示Uncle Bob的Clean Architecture图示真正的意义，以及你应该如何实际组织代码。我们将看到可以立即应用于你项目的实际示例。

让我们彻底消除这一常见误解。

## 传统分层的问题

几乎每个.NET开发者都构建过类似这样的解决方案：

- `MyApp.Web`用于控制器和视图
- `MyApp.Business`用于服务和业务逻辑
- `MyApp.Data`用于仓储和数据访问

这是默认的方法。是我们在教程中看到的，是我们教初学者的。

而这是完全错误的。

### 为什么基于层的组织会失败

当你按技术层次组织代码时，你会将相关的组件分散在多个项目中。一个简单的功能，比如管理策略，结果是在整个代码库中分散：

- Web层的策略控制器
- 业务层的策略服务
- 数据层的策略仓储

当你查看文件夹结构时，你会看到：

```
📁 MyApp.Web
|__ 📁 Controllers
    |__ #️⃣ PoliciesController.cs
📁 MyApp.Business
|__ 📁 Services
    |__ #️⃣ PolicyService.cs
📁 MyApp.Data
|__ 📁 Repositories
    |__ #️⃣ PolicyRepository.cs
```

这是基于层的架构的视觉表示：

![基于层的架构中功能的分散。](https://www.milanjovanovic.tech/blogs/mnw_114/layered_architecture.png?imwidth=640)

这种分散带来了几个问题：

1.  **违反共同封闭原则** - 应该一起改变的类应该呆在一起。当你的“策略”功能发生变化时，你需要修改三个不同的项目。
2.  **隐藏的依赖** - 公共接口无处不在，使得可以绕过层次。没有什么可以阻止控制器直接访问仓储。
3.  **没有业务意图** - 打开你的解决方案，并不能告诉你应用程序在做什么。它仅显示技术实现细节。
4.  **更难维护** - 做出改变需要在多个项目之间跳转。

最糟糕的是？这种方法甚至没有实现它所承诺的。尽管项目是分开的，但由于公共访问修饰符允许任何类引用任何其他类，你往往最终得到了一个“混乱一团”的结果。

### 层的真正意图

Clean Architecture的圆圈从来就不是为了代表项目或文件夹。它们代表不同级别的策略，依赖指向业务规则的内部。

你可以不将代码拆分为人为的技术层次来实现这一点。

让我向你展示一个更好的方法。

## 更好的代码组织方法

与其按技术层次划分代码，你有两种更好的选择：**按功能打包**或**按组件打包**。

让我们看看这两者。

### 按功能打包

按功能组织是一个很好的选择。每个功能都有自己的命名空间，并包含实现该功能所需的所有内容。

```
📁 MyApp.Policies
|__ 📁 RenewPolicy
    |__ #️⃣ RenewPolicyCommand.cs
    |__ #️⃣ RenewPolicyHandler.cs
    |__ #️⃣ PolicyValidator.cs
    |__ #️⃣ PolicyRepository.cs
|__ 📁 ViewPolicyHistory
    |__ #️⃣ PolicyHistoryQuery.cs
    |__ #️⃣ PolicyHistoryHandler.cs
    |__ #️⃣ PolicyHistoryViewModel.cs
```

这是这种结构的示意图：

![按功能组织的垂直切片架构。](https://www.milanjovanovic.tech/blogs/mnw_114/feature_folder_architecture.png?imwidth=640)

这种方法：

- 使功能明确
- 将相关代码保持在一起
- 简化导航
- 使得更容易维护和修改功能

如果你想了解更多，请查看我的关于[**垂直切片架构**](https://www.milanjovanovic.tech/blog/vertical-slice-architecture)的文章。

### 按组件打包

组件是一个具有明确接口的相关功能的内聚组。基于组件的组织比功能文件夹更加粗粒度。可以把它看作一个处理特定业务能力的小型应用程序。

这非常类似于我在[**模块化单体**](https://www.milanjovanovic.tech/blog/what-is-a-modular-monolith)中定义模块的方式。

这是基于组件的组织结构：

```
📁 MyApp.Web
|__ 📁 Controllers
    |__ #️⃣ PoliciesController.cs
📁 MyApp.Policies
|__ #️⃣ PoliciesComponent.cs     // 公共接口
|__ #️⃣ PolicyService.cs         // 实现细节
|__ #️⃣ PolicyRepository.cs      // 实现细节
```

关键区别在于？只有`PoliciesComponent`是公共的。其他一切都在组件内部。

![基于层的架构中功能的分散。](https://www.milanjovanovic.tech/blogs/mnw_114/component_architecture.png?imwidth=640)

这意味着：

- 无法绕过层次
- 清晰的依赖关系
- 真正的封装
- 结构中可见的业务意图

### 你应该选择哪一个？

选择**按功能打包**当：

- 你有许多小而独立的功能
- 你的功能共享的代码不多
- 你想要最大的灵活性

选择**按组件打包**当：

- 你有明确的业务能力
- 你想要强封装
- 你可能会在之后拆分成微服务

这两种方法都实现了Clean Architecture真正想要的：适当的依赖管理和业务聚焦。

这是这些架构方法的并排比较：

![分层、垂直切片和组件架构方法的比较。](https://www.milanjovanovic.tech/blogs/mnw_114/architecture_comparison.png?imwidth=3840)

灰色类型是定义程序集的内部。

在Clean Architecture的缺失章节中，Simon Brown 强烈主张按组件打包。关键见解是，组件是划分系统的自然方式。它们代表完整的业务能力，而不仅仅是技术特性。

我的建议？从按组件打包开始。在组件内部，围绕功能组织。

## 实际示例

让我们将一个典型的分层应用程序转变为一个清晰的、基于组件的结构。我们将以保险政策系统为例。

### 传统方式

以下是大多数开发者组织他们的解决方案的方式：

```
// MyApp.Data
public interface IPolicyRepository
{
    Task<Policy> GetByIdAsync(string policyNumber);
    Task SaveAsync(Policy policy);
}

// MyApp.Business
public class PolicyService : IPolicyService
{
    private readonly IPolicyRepository _repository;

    public PolicyService(IPolicyRepository repository)
    {
        _repository = repository;
    }

    public async Task RenewPolicyAsync(string policyNumber)
    {
        var policy = await _repository.GetByIdAsync(policyNumber);
        // 业务逻辑在这里
        await _repository.SaveAsync(policy);
    }
}

// MyApp.Web
public class PoliciesController : ControllerBase
{
    private readonly IPolicyService _policyService;

    public PoliciesController(IPolicyService policyService)
    {
        _policyService = policyService;
    }

    [HttpPost("renew/{policyNumber}")]
    public async Task<IActionResult> RenewPolicy(string policyNumber)
    {
        await _policyService.RenewPolicyAsync(policyNumber);
        return Ok();
    }
}
```

问题在哪儿？一切都是公共的。任何类都可以绕过服务直接访问仓储。

### 清洁方式

以下是相同功能作为一个合适组件的组织方式：

```
// 唯一的公共契约
public interface IPoliciesComponent
{
    Task RenewPolicyAsync(string policyNumber);
}

// 以下一切都是组件内部的
internal class PoliciesComponent : IPoliciesComponent
{
    private readonly IRenewPolicyHandler _renewPolicyHandler;

    // 依赖注入的公共构造函数
    public PoliciesComponent(IRenewPolicyHandler renewPolicyHandler)
    {
        _renewPolicyHandler = renewPolicyHandler;
    }

    public async Task RenewPolicyAsync(string policyNumber)
    {
        await _renewPolicyHandler.HandleAsync(policyNumber);
    }
}

internal interface IRenewPolicyHandler
{
    Task HandleAsync(string policyNumber);
}

internal class RenewPolicyHandler : IRenewPolicyHandler
{
    private readonly IPolicyRepository _repository;

    internal RenewPolicyHandler(IPolicyRepository repository)
    {
        _repository = repository;
    }

    public async Task HandleAsync(string policyNumber)
    {
        var policy = await _repository.GetByIdAsync(policyNumber);
        // 这里是策略续订的业务逻辑
        await _repository.SaveAsync(policy);
    }
}

internal interface IPolicyRepository
{
    Task<Policy> GetByIdAsync(string policyNumber);
    Task SaveAsync(Policy policy);
}
```

关键改进是：

1.  **单一公共接口** - 只有`IPoliciesComponent`是公共的。其他一切都是内部的。
2.  **保护的依赖** - 没有办法绕过组件直接访问仓储。
3.  **清晰的依赖关系** - 所有依赖通过组件向内流动。
4.  **适当的封装** - 实现细节是真正隐藏的。

这是使用依赖注入注册服务的方式：

```
services.AddScoped<IPoliciesComponent, PoliciesComponent>();
services.AddScoped<IRenewPolicyHandler, RenewPolicyHandler>();
services.AddScoped<IPolicyRepository, SqlPolicyRepository>();
```

这种结构通过编译器检查的边界而非仅仅依靠惯例来强制执行Clean Architecture原则。

编译器不会让你绕过组件的公共接口。这比希望开发者遵循规则要强得多。

## 最佳实践和限制

让我们讨论一些经常被忽视的东西：在.NET中实施Clean Architecture的实际限制。

### 封装的限制

.NET中的`internal`关键字在单个程序集中提供保护。以下是这在实践中的含义：

```
// 在一个项目中：
public interface IPoliciesComponent { } // 公共契约
internal class PoliciesComponent : IPoliciesComponent { }
internal class PolicyRepository { }

// 仍然可以这样做：
public class BadPoliciesComponent : IPoliciesComponent
{
    public BadPoliciesComponent()
    {
        // 没有什么能阻止他们创建一个糟糕的实现
    }
}
```

虽然`internal`有帮助，但它不能防止所有的架构违规。

### 权衡

一些团队将他们的代码分成多个程序集以实现更强的封装：

```
MyCompany.Policies.Core.dll
MyCompany.Policies.Infrastructure.dll
MyCompany.Policies.Api.dll
```

这带来了权衡：

1.  **更复杂的构建过程** - 需要编译和引用多个项目。
2.  **更难的导航** - 在IDE中在程序集之间跳转较慢。
3.  **部署复杂性** - 更多的DLL需要管理和部署。

### 实用的方法

这是我的建议：

1.  **使用单个程序集**
    - 将相关代码放在一起
    - 使用`internal`来表示实现细节
    - 仅公开组件接口
    - 尽可能添加`sealed`以防止继承
2.  **通过架构测试强制执行**
    - 添加架构测试以验证依赖
    - 自动化... **架构测试**

- 添加架构测试以验证依赖关系
- 自动检查架构违规
- 如果有人绕过规则则使构建失败

```csharp
[Fact]
public void Controllers_Should_Only_Depend_On_Component_Interfaces()
{
    var result = Types.InAssembly(Assembly.GetExecutingAssembly())
        .That()
        .ResideInNamespace("MyApp.Controllers")
        .Should()
        .OnlyDependOn(type =>
            type.Name.EndsWith("Component") ||
            type.Name.StartsWith("IPolicy"))
        .GetResult();

    result.IsSuccessful.Should().BeTrue();
}
```

想了解更多关于通过测试来执行架构的方法吗？请查看我的关于[**架构测试**](https://www.milanjovanovic.tech/blog/enforcing-software-architecture-with-architecture-tests)的文章。

记住：清晰架构是关于管理依赖关系，而不是实现完美封装。利用编程语言提供的工具，但不要为了追求不可能的理想而让事情过于复杂。

## 结论

清晰架构不是关于项目、文件夹或完美封装。

它是关于：

- 围绕业务能力组织代码
- 有效管理依赖关系
- 将相关代码放在一起
- 明确边界

从一个项目开始。使用组件。将接口公开，内部实现。添加架构测试以获得更多控制。

记住：**实用主义胜过纯净主义**。你的架构应该帮助你更快地发布功能，而不是因人为限制而拖慢进度。

想了解更多？请查看我的[**实用清晰架构**](https://www.milanjovanovic.tech/pragmatic-clean-architecture)课程，在课程中我将向你展示如何通过适当的边界、清晰的依赖关系和以业务为中心的组件构建可维护的应用程序。
