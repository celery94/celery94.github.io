---
pubDatetime: 2026-03-07
title: "你的 .NET 项目该补上的 5 类架构测试"
description: "架构图写在 Confluence 里，半年后多半会被人悄悄绕开。本文整理 5 类值得放进 .NET 项目的架构测试：层级依赖、命名约束、就近放置、可见性控制和依赖守卫，让架构规则真正变成会失败的测试。"
tags: [".NET", "Architecture", "Testing", "xUnit", "Clean Architecture"]
slug: "architecture-tests-dotnet-projects"
source: "https://www.milanjovanovic.tech/blog/5-architecture-tests-you-should-add-to-your-dotnet-projects"
---

项目刚开工的时候，大家都很讲规矩。`Domain` 不碰 `Infrastructure`，Handler 命名统一，内部实现尽量别往外漏，目录结构看起来也像那么回事。可代码库一长大，事情就变了。有人为了图省事把数据库相关类型带进 Application，有人顺手把 `public` 写满整片文件夹，还有人把 `CreateOrderCommand` 和对应 Handler 拆到两个毫不相干的命名空间里。

代码评审能拦住一部分问题，但拦不住全部。评审是人，规则一多就会漏。架构测试不一样，它不会累，也不会在周五下午心软。只要规则被踩，构建就该失败。这就是它最值钱的地方。

> 架构如果只存在于图纸和口头约定里，它迟早会被破坏。把规则写成测试，事情才算真的开始。

这篇文章整理 5 类我认为很值得放进 .NET 项目的架构测试。它们都不复杂，跑得也快，放在 CI 里几乎没有负担。

## 先把测试地基铺好

如果你打算在 .NET 里写这类测试，`ArchUnitNET` 是个很顺手的选择。它是 Java 世界 `ArchUnit` 的 C# 版本，可以把程序集加载进来，再用接近英文句子的 fluent API 写规则。

先安装与测试框架对应的包：

```bash
dotnet add package TngTech.ArchUnitNET.xUnit
```

然后准备一个测试基类，把要检查的几个程序集都加载进来。这里的“锚点类型”（anchor type）很实用，它能让你在编译期稳定拿到程序集引用。

```csharp
using System.Reflection;
using ArchUnitNET.Domain;
using ArchUnitNET.Loader;

public abstract class BaseArchitectureTest
{
    protected static readonly Assembly DomainAssembly = typeof(User).Assembly;
    protected static readonly Assembly ApplicationAssembly = typeof(ICommand).Assembly;
    protected static readonly Assembly InfrastructureAssembly = typeof(ApplicationDbContext).Assembly;
    protected static readonly Assembly PresentationAssembly = typeof(Program).Assembly;

    protected static readonly Architecture Architecture = new ArchLoader()
        .LoadAssemblies(
            DomainAssembly,
            ApplicationAssembly,
            InfrastructureAssembly,
            PresentationAssembly)
        .Build();
}
```

这段代码只写一次，后面的测试类都继承它。接下来就能开始给你的系统“立规矩”。

## 把层级边界锁死

这是最该先补上的一类测试。Clean Architecture 也好，分层架构也好，最容易出事的地方始终是依赖方向。内层应该稳定，外层应该依赖内层，而不是反过来。

很多人会说，项目引用不是已经帮我拦住了吗？有时能，有时不能。NuGet 的传递依赖、解决方案结构调整、模块化单体里多层共用同一个程序集，这些场景都可能绕开编译器的保护。等你发现边界漏了，通常已经有人在错误的层里写了不少代码。

```csharp
using ArchUnitNET.Domain;
using ArchUnitNET.Fluent;
using Xunit;
using static ArchUnitNET.Fluent.ArchRuleDefinition;

public class LayerDependencyTests : BaseArchitectureTest
{
    private static readonly IObjectProvider<IType> DomainLayer =
        Types().That().ResideInAssembly(DomainAssembly).As("Domain");

    private static readonly IObjectProvider<IType> ApplicationLayer =
        Types().That().ResideInAssembly(ApplicationAssembly).As("Application");

    private static readonly IObjectProvider<IType> InfrastructureLayer =
        Types().That().ResideInAssembly(InfrastructureAssembly).As("Infrastructure");

    private static readonly IObjectProvider<IType> PresentationLayer =
        Types().That().ResideInAssembly(PresentationAssembly).As("Presentation");

    [Fact]
    public void Domain_Should_Not_Depend_On_Outer_Layers()
    {
        Types().That().Are(DomainLayer).Should().NotDependOnAny(ApplicationLayer)
            .AndShould().NotDependOnAny(InfrastructureLayer)
            .AndShould().NotDependOnAny(PresentationLayer)
            .Check(Architecture);
    }

    [Fact]
    public void Application_Should_Not_Depend_On_Infrastructure_Or_Presentation()
    {
        Types().That().Are(ApplicationLayer).Should().NotDependOnAny(InfrastructureLayer)
            .AndShould().NotDependOnAny(PresentationLayer)
            .Check(Architecture);
    }

    [Fact]
    public void Infrastructure_Should_Not_Depend_On_Presentation()
    {
        Types().That().Are(InfrastructureLayer).Should().NotDependOnAny(PresentationLayer)
            .Check(Architecture);
    }
}
```

这种测试的价值不只是“防破坏”。它还把你的架构边界写成了活文档。新同事进来，不用先翻 Confluence，他看测试名就知道什么是允许的，什么不是。

如果你在做垂直切片（Vertical Slice Architecture）或者模块化单体，这类测试还能继续往里压。比如 `Application.Orders` 不准依赖 `Application.Users`，模块之间只能通过事件或公共契约通信。规则越明确，后面越省心。

## 命名别靠默契，靠测试

命名规范这种事，平时最容易被低估。可当项目里出现 `CreateOrderService`、`ProcessPaymentUseCase`、`CreateOrderHandler` 三套命名并存的时候，搜索、维护和约定注册都会开始变得别扭。

命名一乱，代码库就开始失去可预测性。开发者脑子里原本那张地图，也会越来越不准。

```csharp
using Xunit;
using static ArchUnitNET.Fluent.ArchRuleDefinition;

public class NamingConventionTests : BaseArchitectureTest
{
    [Fact]
    public void Command_Handlers_Should_End_With_CommandHandler()
    {
        Classes().That()
            .ImplementInterface(typeof(ICommandHandler<>))
            .Or()
            .ImplementInterface(typeof(ICommandHandler<,>))
            .And().DoNotResideInNamespace("Application.Abstractions.Behaviors")
            .Should().HaveNameEndingWith("CommandHandler")
            .Check(Architecture);
    }

    [Fact]
    public void Query_Handlers_Should_End_With_QueryHandler()
    {
        Classes().That()
            .ImplementInterface(typeof(IQueryHandler<,>))
            .And().DoNotResideInNamespace("Application.Abstractions.Behaviors")
            .Should().HaveNameEndingWith("QueryHandler")
            .Check(Architecture);
    }

    [Fact]
    public void Validators_Should_Stay_In_Application()
    {
        Classes().That()
            .HaveNameEndingWith("Validator")
            .Should().ResideInAssembly(ApplicationAssembly)
            .Check(Architecture);
    }
}
```

这里有个细节很容易踩坑。像 `ValidationBehavior` 这种管道装饰器，同样可能实现了 Handler 接口，但它不是你真正的业务 Handler。把它排除掉，测试结果才干净。

我很喜欢这种测试，因为它几乎没有争议。你写了命名约定，就应该让机器去执行，不要靠团队成员“记得”。人脑很贵，别浪费在这种重复劳动上。

## 一个用例的代码，最好住在一起

如果你在用 CQRS，命令、查询、Handler、Validator 往往天然是一组。它们表达的是同一个业务动作，读写的上下文也一致。可现实里经常有人把 `CreateInvoiceCommand` 放在一个目录，把 `CreateInvoiceCommandHandler` 放到另一个目录，理由通常是“以前就是这么放的”。

这会直接抬高理解成本。你想读一个用例，不得不在好几个命名空间之间来回跳。代码当然还能跑，只是人开始跑不动了。

这一类规则，`ArchUnitNET` 不太擅长直接表达，因为它涉及“泛型接口第一个参数的命名空间必须与实现类一致”这种关联。这里用反射写测试反而更直接。

```csharp
using Xunit;

public class ColocationTests : BaseArchitectureTest
{
    [Theory]
    [MemberData(nameof(GetHandlerPairs))]
    public void Handler_Should_Reside_In_Same_Namespace_As_Request(
        Type handlerType,
        Type requestType)
    {
        Assert.Equal(requestType.Namespace, handlerType.Namespace);
    }

    public static TheoryData<Type, Type> GetHandlerPairs()
    {
        Type[] handlerInterfaces =
        [
            typeof(ICommandHandler<>),
            typeof(ICommandHandler<,>),
            typeof(IQueryHandler<,>)
        ];

        var pairs = new TheoryData<Type, Type>();

        var handlers = ApplicationAssembly
            .GetTypes()
            .Where(type => type is { IsClass: true, IsAbstract: false })
            .Where(type => type.DeclaringType is null);

        foreach (var handler in handlers)
        {
            foreach (var implementedInterface in handler.GetInterfaces())
            {
                if (!implementedInterface.IsGenericType)
                {
                    continue;
                }

                var genericType = implementedInterface.GetGenericTypeDefinition();
                if (!handlerInterfaces.Contains(genericType))
                {
                    continue;
                }

                var requestType = implementedInterface.GetGenericArguments()[0];
                pairs.Add(handler, requestType);
            }
        }

        return pairs;
    }
}
```

这类测试对垂直切片非常有帮助。一个功能的入口、验证和处理逻辑都在附近，新人更容易读懂，重构时也更不容易把东西搬散。代码组织方式看起来像小事，长期看不是。

## 实现细节别默认公开

很多 Handler、配置类、内部服务，其实不该是 `public`。它们只在程序集内部被 DI 或框架扫描发现，对外没有公开语义。可惜 `public class` 写起来太顺手了，很多人连想都不会想，直接敲下去。

问题在于，一旦实现细节暴露出来，别的层就可能直接引用它，绕过本来设计好的抽象边界。短期看很方便，长期看就是架构漏风。

```csharp
using Xunit;
using static ArchUnitNET.Fluent.ArchRuleDefinition;

public class VisibilityTests : BaseArchitectureTest
{
    [Fact]
    public void Command_Handlers_Should_Be_Internal()
    {
        Classes().That()
            .ImplementInterface(typeof(ICommandHandler<>))
            .Or()
            .ImplementInterface(typeof(ICommandHandler<,>))
            .Should().BeInternal()
            .Check(Architecture);
    }

    [Fact]
    public void Query_Handlers_Should_Be_Internal()
    {
        Classes().That()
            .ImplementInterface(typeof(IQueryHandler<,>))
            .Should().BeInternal()
            .Check(Architecture);
    }
}
```

不少人担心改成 `internal` 以后依赖注入扫描不到。大多数情况下，这个担心是多余的。常见的程序集扫描方式完全可以发现 `internal` 类型。真正该担心的，是你把不该暴露的实现暴露给了整个解决方案。

这条规则还可以继续扩展。比如 EF Core 的实体配置类、只给内部流程用的 Mapper、某些策略实现类，都很适合限制为 `internal`。

## 守住第三方依赖的漏口

层级依赖测试能拦住你自己的程序集之间乱连，但它拦不住所有外部库泄漏。最典型的例子，就是 Entity Framework、数据库驱动、消息中间件 SDK 这些基础设施依赖，通过传递引用一路飘进了 Domain 或 Application。

编译器通常不会提醒你。因为从技术上讲，类型就是可见的；从架构上讲，它却根本不该出现。

```csharp
using Xunit;
using static ArchUnitNET.Fluent.ArchRuleDefinition;

public class DependencyGuardTests : BaseArchitectureTest
{
    [Fact]
    public void Domain_Should_Not_Depend_On_EntityFrameworkCore()
    {
        Types().That().ResideInAssembly(DomainAssembly).Should()
            .NotDependOnAnyTypesThat()
            .ResideInNamespace("Microsoft.EntityFrameworkCore")
            .Check(Architecture);
    }

    [Fact]
    public void Application_Should_Not_Depend_On_EntityFrameworkCore()
    {
        Types().That().ResideInAssembly(ApplicationAssembly).Should()
            .NotDependOnAnyTypesThat()
            .ResideInNamespace("Microsoft.EntityFrameworkCore")
            .Check(Architecture);
    }

    [Fact]
    public void Application_Should_Not_Depend_On_Npgsql()
    {
        Types().That().ResideInAssembly(ApplicationAssembly).Should()
            .NotDependOnAnyTypesThat()
            .ResideInNamespace("Npgsql")
            .Check(Architecture);
    }
}
```

这一类测试特别适合防“手滑”。开发者也许只是图快，在 Application 里直接用了某个数据库异常类型，或者在 Domain 里顺手引用了 EF Core 的特性。小口子一开，后面就会越来越宽。

该拦哪些库，没有标准答案。你用什么基础设施，就把最不该泄漏进去的那些命名空间列出来。先从数据库和 ORM 开始，通常就很值。

## 这 5 类测试，分别在拦什么

| 测试类型     | 要拦住的问题               | 典型信号                            |
| ------------ | -------------------------- | ----------------------------------- |
| 层级依赖测试 | 内层依赖外层、模块乱连     | `Application` 引用 `Infrastructure` |
| 命名约定测试 | 命名风格失控、搜索失真     | Handler 名称五花八门                |
| 就近放置测试 | 一个用例散落多个目录       | Command 和 Handler 不在同一命名空间 |
| 可见性测试   | 实现细节被外部直接引用     | Handler、配置类默认 `public`        |
| 依赖守卫测试 | 第三方基础设施库向内层渗透 | Domain 直接引用 EF Core、Npgsql     |

如果你现在还没有任何架构测试，我建议先从层级依赖开始。它投入小，回报大，而且几分钟就能搭出来。等团队开始习惯这种护栏，再慢慢把命名、可见性和依赖守卫补上。等你把这些规则都放进测试，代码库会稳定很多。

还有一件事也很现实：这些测试不是为了证明团队不犯错，而是承认团队一定会犯错。承认这一点，工程质量反而会上一个台阶。

## 参考

- [原文：5 Architecture Tests You Should Add to Your .NET Projects](https://www.milanjovanovic.tech/blog/5-architecture-tests-you-should-add-to-your-dotnet-projects) — Milan Jovanović
- [ArchUnitNET](https://github.com/TNG/ArchUnitNET) — C# 架构测试库
- [Enforcing Software Architecture With Architecture Tests](https://www.milanjovanovic.tech/blog/enforcing-software-architecture-with-architecture-tests) — Milan Jovanović 更早一篇关于架构测试的文章
- [Vertical Slice Architecture: Structuring Vertical Slices](https://www.milanjovanovic.tech/blog/vertical-slice-architecture-structuring-vertical-slices) — 理解“就近放置”这类规则为什么有意义
