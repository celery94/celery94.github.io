---
pubDatetime: 2026-05-27T08:23:00+08:00
title: "DI 容器内部怎么用反射：从 55 行手写容器到 IServiceCollection"
description: "DI 容器的魔法就是反射。本文从 GetConstructors → GetParameters → Resolve → Invoke 的递归循环讲起，用 55 行 C# 实现一个最小容器，再拆解 IServiceCollection 和 Scrutor 的内部机制，最后介绍源生成器如何在编译期消除反射。"
tags: ["CSharp", "DotNet", "依赖注入", "反射"]
slug: "di-container-reflection-internals-csharp"
ogImage: "../../assets/834/01-cover.png"
source: "https://www.devleader.ca/2026/05/26/how-dependency-injection-containers-use-reflection-internally-in-c"
---

![DI 容器内部怎么用反射：从 55 行手写容器到 IServiceCollection](../../assets/834/01-cover.png)

你写过几百次 `services.AddSingleton<IMyService, MyService>()`，容器就能在运行时拿到一个完整的对象图，所有构造函数参数都填好了。没有 `new`，没有手动接线。它就是能跑。

能跑是因为反射。容器在运行时检查你的类型，读构造函数签名，递归解析每个参数的类型，按正确顺序创建实例。理解这条管线之后，DI 就不再是魔法，而是一个你自己也能搭出来的算法——这篇文章就带你搭一个。

## DI 容器到底做了什么

核心问题就一个：给定类型 `T`，产出一个有效实例，所有依赖都已满足。步骤分六步：

1. **注册** — 用户告诉容器哪个接口映射到哪个实现。
2. **解析** — 有人请求一个服务时，容器查找实现类型。
3. **构造分析** — 容器通过反射检查实现类型的构造函数，发现它需要什么。
4. **递归解析** — 每个构造函数参数本身也是一个类型，容器用同样的方式解析。
5. **实例化** — 容器用解析好的参数值创建对象。
6. **生命周期管理** — 容器决定是创建新实例还是返回缓存的。

**反射是第 3 步和第 4 步的引擎**，其余都是记账。

一个重要的细微差别：反射只在启动时（或每个类型首次解析时）用一次，用来分析构造函数签名并构建工厂。在稳态请求处理期间，容器调用的是编译好的委托或缓存的构造器——不是每次调用都跑原始反射。DI 解析的单次调用成本可以忽略不计，正是因为反射的工作被前置了。

## 55 行手写最小容器

直接写一个。这个容器支持 Singleton 和 Transient 生命周期，处理构造函数注入，递归解析依赖。大约 55 行代码，故意保持简单，让算法清晰可见。

> ⚠️ 以下实现仅用于教学目的，不适合生产环境。生产环境请用 `Microsoft.Extensions.DependencyInjection` 或其他成熟的 DI 容器。

```csharp
using System.Collections.Concurrent;

public enum Lifetime { Singleton, Transient }

public sealed class MinimalContainer
{
    private readonly Dictionary<Type, (Type ImplementationType, Lifetime Lifetime)>
        _registrations = new();
    private readonly ConcurrentDictionary<Type, object> _singletons = new();

    public MinimalContainer Register<TService, TImplementation>(
        Lifetime lifetime = Lifetime.Transient)
        where TImplementation : TService
    {
        _registrations[typeof(TService)] =
            (typeof(TImplementation), lifetime);
        return this;
    }

    public MinimalContainer RegisterSelf<TImplementation>(
        Lifetime lifetime = Lifetime.Transient)
    {
        _registrations[typeof(TImplementation)] =
            (typeof(TImplementation), lifetime);
        return this;
    }

    public TService Resolve<TService>() =>
        (TService)Resolve(typeof(TService));

    private object Resolve(Type serviceType)
    {
        if (!_registrations.TryGetValue(serviceType, out var registration))
            throw new InvalidOperationException(
                $"No registration found for {serviceType.Name}.");

        if (registration.Lifetime == Lifetime.Singleton)
            return _singletons.GetOrAdd(serviceType,
                _ => CreateInstance(registration.ImplementationType));

        return CreateInstance(registration.ImplementationType);
    }

    private object CreateInstance(Type implementationType)
    {
        // 容器的反射核心
        var constructor = implementationType.GetConstructors()
            .OrderByDescending(c => c.GetParameters().Length)
            .FirstOrDefault()
            ?? throw new InvalidOperationException(
                $"No public constructor found on {implementationType.Name}.");

        var parameters = constructor.GetParameters();

        // 递归解析每个参数
        var resolvedArgs = parameters
            .Select(p => Resolve(p.ParameterType))
            .ToArray();

        return constructor.Invoke(resolvedArgs);
    }
}
```

用起来：

```csharp
public interface IMessageService
{
    void Send(string message);
}

public sealed class EmailService : IMessageService
{
    public void Send(string message) =>
        Console.WriteLine($"Email: {message}");
}

public sealed class NotificationHandler
{
    private readonly IMessageService _messageService;

    public NotificationHandler(IMessageService messageService)
    {
        _messageService = messageService;
    }

    public void Notify(string text) => _messageService.Send(text);
}

// 注册
var container = new MinimalContainer()
    .Register<IMessageService, EmailService>(Lifetime.Singleton)
    .RegisterSelf<NotificationHandler>(Lifetime.Transient);

// 解析——反射在这里发生
var handler = container.Resolve<NotificationHandler>();
handler.Notify("Hello, DI!"); // Email: Hello, DI!
```

`Resolve<NotificationHandler>()` 运行时的完整过程：

1. 查找 `NotificationHandler` → 实现类型是 `NotificationHandler` 本身。
2. `GetConstructors()` 返回唯一的公开构造函数。
3. `GetParameters()` 返回一个参数：`IMessageService`。
4. 容器递归调用 `Resolve(typeof(IMessageService))`。
5. `IMessageService` 映射到 `EmailService`，Singleton 生命周期。
6. `EmailService` 有无参构造函数，直接创建。
7. 缓存的 `EmailService` 通过 `constructor.Invoke(resolvedArgs)` 传给 `NotificationHandler` 的构造函数。

每一个 `GetConstructors()`、`GetParameters()` 和 `constructor.Invoke()` 调用都是反射。

## IServiceCollection 内部怎么做

微软内置的 DI 容器（`Microsoft.Extensions.DependencyInjection`）遵循同样的概念算法，但在上面加了大量生产级机制。

当你调用 `services.AddTransient<IMyService, MyService>()` 时，你只是往 `IServiceCollection` 里添加了一个 `ServiceDescriptor`——一个普通数据对象。集合本身就是一个 `List<ServiceDescriptor>`。

魔法发生在你调用 `services.BuildServiceProvider()` 的时候：

1. 从集合构造 `ServiceProvider`。
2. 内部构建一个 `CallSiteFactory`——缓存"如何创建每个注册类型"的信息。
3. 每个 call site 通过反射检查实现类型的构造函数，找到最佳匹配（参数最多且都能被容器满足的构造函数），记录依赖图。
4. 首次解析时用 call site 创建对象。后续解析（Singleton 和 Scoped）返回缓存实例。

关键优化：DI 容器用反射做服务注册分析，然后构建优化的工厂委托用于稳态解析。首次解析之后，后续调用走缓存工厂，不再有反射开销。"启动时反射一次，运行时调委托"这个模式在各个 .NET 版本里是一致的。

## Scrutor 怎么用反射扩展注册

Scrutor 在 `IServiceCollection` 之上加了程序集扫描。不用手动注册每个服务，你告诉 Scrutor："扫描这个程序集，找到所有实现 `IMyInterface` 的类型，注册它们。"

底层用的反射 API：

- `Assembly.GetTypes()` — 枚举目标程序集里的所有类型
- `type.GetInterfaces()` — 检查每个类型实现了哪些接口
- `type.IsAbstract`、`type.IsGenericTypeDefinition` — 过滤掉不可实例化的类型
- `IServiceCollection.Add()` — 注册找到的类型

全是反射。它在启动时运行，所以反射成本可以接受——启动是一次性事件，不是热路径。

## 反射在 DI 里的性能问题

精确地说清楚反射在哪里影响性能：

**启动时间**是大多数 DI 反射发生的地方。扫描程序集、读构造函数元数据、构建服务描述符——这些都在 `BuildServiceProvider()` 调用时跑一次。对于注册了几百个服务的大型应用，这会增加可感知的启动延迟。

**首次解析**是基于构造函数反射的实例化发生的地方（如果容器还没有编译 call site）。第二次及后续解析走的是缓存委托。

**Scoped 服务**在 ASP.NET Core 里是个更微妙的情况。Scoped 服务每个 HTTP 请求创建一次。编译好的 call site 意味着大部分成本已经摊销了，但每请求的分配仍然会发生。

生产级 DI 容器用的模式——你在自己的容器里也可以用——是：**启动时反射，编译成委托，运行时调用委托**。加到我们的最小容器里：

```csharp
// 添加到 MinimalContainer：编译工厂缓存
private readonly ConcurrentDictionary<Type, Func<object>>
    _compiledFactories = new();

private object CreateInstanceFast(Type implementationType)
{
    var factory = _compiledFactories.GetOrAdd(
        implementationType, BuildCompiledFactory);
    return factory();
}

private Func<object> BuildCompiledFactory(Type type)
{
    // 每个类型只跑一次——表达式树编译
    var ctor = type.GetConstructors()
        .OrderByDescending(c => c.GetParameters().Length)
        .First();

    var parameterTypes = ctor.GetParameters()
        .Select(p => p.ParameterType)
        .ToArray();

    var newExpr = Expression.New(ctor,
        parameterTypes.Select(t =>
            Expression.Convert(
                Expression.Call(
                    Expression.Constant(this),
                    typeof(MinimalContainer)
                        .GetMethod("Resolve",
                            new[] { typeof(Type) })!,
                    Expression.Constant(t)),
                t)));

    var lambda = Expression.Lambda<Func<object>>(
        Expression.Convert(newExpr, typeof(object)));
    return lambda.Compile();
}
```

首次解析之后，每次调用走的都是 `Func<object>`——热路径上没有反射。

## 源生成器：把反射移到编译期

Needlr 采用了根本不同的方式：用 Roslyn 源生成器把类型发现的工作移到编译期。

不是在运行时用 `Assembly.GetTypes()` 扫描程序集，而是 Needlr 的源生成器在构建时运行，直接把 C# 注册代码生成到你的项目里——不需要运行时反射。

结果就是你在启动时的 DI 注册只是调用生成的方法，里面是显式的 `services.AddTransient<IMyService, MyService>()` 调用。没有程序集扫描，没有构造函数反射，没有表达式树编译。所有动态发现的东西都被硬编码成了生成的源代码。

两个主要优势：

1. **AOT 兼容** — NativeAOT 在裁剪时能看到所有类型引用，因为它们在真实的 C# 代码里，不是藏在 `Type.GetType()` 字符串后面。
2. **启动性能** — 零反射意味着更快的冷启动，这在 serverless 和容器按请求部署的模型里很重要。

## 三阶段 DI 生命周期

把以上所有内容综合起来，就是一个三阶段的 DI 生命周期：

**阶段 1 — 注册**（Needlr 在构建时，其他在启动时）。类型被注册。Needlr 不需要反射；Scrutor 和运行时扫描器需要完整的反射扫描。

**阶段 2 — 构建/预热**（启动时）。容器分析注册。通过反射读取构造函数元数据。构建 call site。使用表达式树的容器在这里编译并缓存委托。

**阶段 3 — 运行时解析**（热路径）。每个请求走的是编译好的委托或直接构造函数调用。没有反射。成本是一次字典查找和一次委托调用。

这个模式解释了为什么看起来开销很大的 DI 容器在生产中实际表现很好：反射成本被前置到启动阶段，启动只发生一次。运行时是快的。

如果你在构建自己的类 DI 基础设施（插件加载器、工厂注册表等），采用同样的三阶段结构能同时给你灵活性和性能。

## .NET 10 的相关进展

- **NativeAOT 改进** — .NET 10 的裁剪器在分析使用源生成器的 DI 注册时更好了，配合正确的工具链，AOT 兼容的 DI 注册变得直接。
- **Keyed services**（.NET 8 引入，.NET 9/10 成熟） — `IKeyedServiceCollection` API 让你可以用不同的 key 注册同一个接口的多个实现，源生成器能干净地处理。
- **`FrozenDictionary` 做服务缓存** — 不可变、读优化的字典非常适合 DI 容器"启动时构建一次、运行时持续读取"的模式。

## 多构造函数怎么选

`Microsoft.Extensions.DependencyInjection` 选择参数最多且所有参数都能从容器满足的构造函数。如果两个构造函数的可满足参数数量相同，抛 `InvalidOperationException`。你可以用 `[ActivatorUtilitiesConstructor]` 标记特定构造函数来覆盖这个选择逻辑。

## 为什么要理解这些

原文作者总结了三个理由：

1. **去魔法化** — 当 DI 解析出问题时，你能推理容器到底在做什么。
2. **知道性能开销在哪** — 启动，不是运行时热路径。
3. **知道何时优化** — 当启动成本确实重要时（serverless、冷启动），指向正确的优化方向——源生成器，把类型发现移到编译期。

我们手写的最小容器证明了核心算法是简单的。生产级容器加的是生命周期管理、作用域追踪、编译委托和诊断——但核心是同一个递归反射循环。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [How Dependency Injection Containers Use Reflection Internally in C# (Dev Leader)](https://www.devleader.ca/2026/05/26/how-dependency-injection-containers-use-reflection-internally-in-c)
- [IServiceCollection in C# — Complete Guide (Dev Leader)](https://www.devleader.ca/2024/02/21/iservicecollection-in-c-complete-guide-with-addsingleton-addscoped-&-addtransient)
- [ConstructorInfo — How To Make Reflection Faster for Instantiation (Dev Leader)](https://www.devleader.ca/2024/03/17/constructorinfo-how-to-make-reflection-in-dotnet-faster-for-instantiation)
- [Automatic Dependency Injection in C#: The Complete Guide to Needlr (Dev Leader)](https://www.devleader.ca/2026/02/03/automatic-dependency-injection-in-c-the-complete-guide-to-needlr)
