---
pubDatetime: 2026-04-10T08:34:23+08:00
title: ".NET 插件加载实战：AssemblyLoadContext 与依赖注入集成"
description: "Assembly.LoadFrom 在插件有不同依赖版本时会出现冲突，AssemblyLoadContext 提供了正确的隔离机制。本文讲解 PluginLoadContext 的实现原理、AssemblyDependencyResolver 的作用，以及如何将插件与 Microsoft.Extensions.DependencyInjection 干净地集成。"
tags: ["C#", ".NET", "插件架构", "依赖注入", "软件设计"]
slug: "dotnet-plugin-loading-assemblyloadcontext-dependency-injection"
ogImage: "../../assets/722/01-cover.jpg"
source: "https://www.devleader.ca/2026/04/09/plugin-loading-in-net-assemblyloadcontext-with-dependency-injection"
---

![.NET 插件加载：AssemblyLoadContext 与依赖注入](../../assets/722/01-cover.jpg)

如果你已经决定构建一个插件架构，概念层面的问题算是解决了——你有宿主应用、共享契约和外部程序集。真正的挑战在于：怎么实现插件加载，同时不让依赖冲突在生产环境炸掉？这正是 `AssemblyLoadContext` 插件加载要解决的问题。配合 `Microsoft.Extensions.DependencyInjection`，你可以得到一套完整的、现代化的扩展机制，而不需要依赖任何历史遗留框架。

本文覆盖 `AssemblyLoadContext` 的工作机制、`AssemblyDependencyResolver` 如何处理插件私有依赖，以及如何将整个流程接入 DI 容器。

## 插件加载为什么比看上去难

大多数开发者第一次尝试的方法是 `Assembly.LoadFrom(path)`。单个插件、没有私有依赖时，它能工作。一旦第二个插件也依赖同一个 NuGet 包但版本不同，运行时要么加载了错误的版本，要么抛出 `FileNotFoundException`——因为这个程序集已经在另一个无法访问的上下文里加载了。

核心问题在于，`Assembly.LoadFrom` 把程序集倒入共享的默认上下文。两个插件竞争同一个依赖名称时，谁先加载谁赢，另一个插件可能静默地跑在错误的版本上。这让朴素的插件加载方式在插件生态超出单个零依赖程序集时就变得脆弱。

程序集隔离的含义是：每个插件有自己的解析作用域。Plugin A 需要 `Serilog 3.1.0`，Plugin B 需要 `Serilog 4.0.0`，各自只应该找到自己的那份副本。

.NET Framework 时代，`AppDomain` 是隔离机制，但创建一个 AppDomain 开销很大，跨域通信需要序列化或 `MarshalByRefObject` 代理。.NET Core 移除了多 AppDomain 支持——`AppDomain.CreateDomain` 在 .NET 5+ 上直接抛 `PlatformNotSupportedException`。`AssemblyLoadContext` 就是现代的轻量替代：它在同一个进程和 CLR 实例里，给每个上下文提供独立的程序集名称解析作用域。

## AssemblyLoadContext 是什么

运行中的 .NET 进程里，每个程序集都在某个 `AssemblyLoadContext` 里。默认上下文是宿主所有启动依赖的落脚地——运行时本身、应用包、ASP.NET Core 管道。正常加载的程序集都在这里。

隔离上下文是你手动创建的具名实例。其中的程序集针对自己的路径解析依赖，而不是全局依赖集。关键点在于：从 `Load` 重写里返回 `null`，意味着告诉运行时回退到默认上下文——这正是共享类型（比如你的插件契约接口）能被宿主和插件同时访问而不重复加载的原因。

三种场景决定是否需要隔离：

- 插件没有私有依赖，且你完全控制它——加载到默认上下文就够了。
- 插件打包了自己的依赖，或可能与宿主依赖冲突——创建隔离上下文。
- 插件需要在运行时卸载（热重载场景）——创建可回收上下文（collectible context）。

下面是覆盖前两种场景的最小 `PluginLoadContext` 实现：

```csharp
using System.Reflection;
using System.Runtime.Loader;

public class PluginLoadContext : AssemblyLoadContext
{
    private readonly AssemblyDependencyResolver _resolver;

    public PluginLoadContext(string pluginPath)
        : base(name: Path.GetFileNameWithoutExtension(pluginPath), isCollectible: false)
    {
        // Resolver 读取插件 DLL 旁边的 .deps.json 文件
        _resolver = new AssemblyDependencyResolver(pluginPath);
    }

    protected override Assembly? Load(AssemblyName assemblyName)
    {
        // 优先从插件自己的目录解析
        string? assemblyPath = _resolver.ResolveAssemblyToPath(assemblyName);
        if (assemblyPath is not null)
        {
            return LoadFromAssemblyPath(assemblyPath);
        }

        // 返回 null 回退到默认上下文，
        // 共享契约程序集就在那里
        return null;
    }

    protected override IntPtr LoadUnmanagedDll(string unmanagedDllName)
    {
        string? libraryPath = _resolver.ResolveUnmanagedDllToPath(unmanagedDllName);
        return libraryPath is not null
            ? LoadUnmanagedDllFromPath(libraryPath)
            : IntPtr.Zero;
    }
}
```

`Load` 里的 `null` 回退是让一切运转起来的关键设计决策。契约程序集——定义了你的 `IPlugin` 或 `IAnalyzer` 接口的那个——必须来自默认上下文，这样宿主和插件才共享同一个 `Type` 对象。如果两侧各自加载了一份，`IsAssignableFrom` 会返回 `false`，即便代码完全相同。

## AssemblyDependencyResolver：处理插件依赖

`AssemblyDependencyResolver` 读取编译每个 .NET 项目时生成的 `.deps.json` 文件。这个文件把程序集名称映射到物理路径，包括传递性 NuGet 依赖。当 Plugin B 需要 `Newtonsoft.Json 13.0.3` 时，resolver 知道去 Plugin B 自己的输出目录找，而不是去宿主的目录。

没有这个 resolver，你就得手动枚举插件目录、把 DLL 名称匹配到程序集名称——对复杂依赖图来说既脆弱又不完整。有了 `AssemblyDependencyResolver`，你只需把它指向插件的入口 DLL 路径，剩下的由生成的元数据文件处理。

上面的 `PluginLoadContext` 已经集成了它。运行时调用 `Load(assemblyName)` 时，先问 resolver 有没有本地路径。有就从那里加载，没有就返回 `null` 让默认上下文处理。这个两步解析模式是 `AssemblyLoadContext` 插件加载的核心套路。

一个实际约束：插件项目的输出必须包含 `.deps.json` 文件（发布时默认会生成）。如果你只把 DLL 复制到 plugins 文件夹，resolver 找不到依赖。始终部署插件的完整发布输出，包括 deps 文件和所有私有依赖 DLL。

## 逐步加载插件程序集

有了上下文类，下面是一个泛型加载器，覆盖完整的插件加载生命周期——路径验证、上下文创建、类型发现和实例化：

```csharp
using System.Reflection;

public static class PluginLoader<TContract>
{
    public static IReadOnlyList<TContract> LoadFromAssembly(string pluginPath)
    {
        if (!File.Exists(pluginPath))
        {
            throw new FileNotFoundException($"Plugin assembly not found: {pluginPath}");
        }

        var context = new PluginLoadContext(pluginPath);
        Assembly assembly;

        try
        {
            assembly = context.LoadFromAssemblyPath(pluginPath);
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException(
                $"Failed to load plugin assembly from '{pluginPath}'.", ex);
        }

        var contractType = typeof(TContract);

        var implementations = assembly.GetTypes()
            .Where(t => contractType.IsAssignableFrom(t)
                     && t is { IsClass: true, IsAbstract: false })
            .ToList();

        if (implementations.Count == 0)
        {
            throw new InvalidOperationException(
                $"No implementations of '{contractType.Name}' found in '{pluginPath}'.");
        }

        var instances = new List<TContract>();
        foreach (var type in implementations)
        {
            if (Activator.CreateInstance(type) is TContract instance)
            {
                instances.Add(instance);
            }
        }

        return instances;
    }
}
```

`IsAssignableFrom` 检查使用的是来自宿主上下文的 `typeof(TContract)`。这能正常工作，是因为契约程序集在默认上下文里，而插件的 `Load` 重写对它返回 `null`——让运行时复用宿主已加载的那份副本。如果你绕过这个逻辑，把契约 DLL 显式加载到隔离上下文，你会在运行时遇到类型不匹配的错误，即便两边的程序集完全相同。

错误处理在这里很重要。如果插件编译时用的契约接口版本不同（方法签名已经变了），`Activator.CreateInstance` 会成功，但调用契约方法时可能抛 `MissingMethodException`。仔细给契约程序集做版本管理，或者采用保持向后兼容的接口演化策略。

## 为什么 MEF 已经不是答案

MEF（`System.ComponentModel.Composition` 和后续的 `System.Composition`）曾是 .NET 的原生插件组合框架，用 `[Export]`、`[Import]` 属性声明扩展点，用反射在启动时连接各部分。简单场景下看起来很优雅。

但问题是根本性的。MEF 早于 `AssemblyLoadContext`，不能与隔离上下文干净地集成。它的属性耦合在以 DI 为中心的代码库里造成摩擦——你最终要维护两套组合系统。它不支持 `IServiceCollection` 注册，除非你写胶水代码。微软已经把 MEF 置于维护模式，只收安全修复，不加新特性，不推荐用于新开发。

现代的答案是：用 `AssemblyLoadContext` 做程序集隔离，用 `Microsoft.Extensions.DependencyInjection` 做组合。这就是你的 ASP.NET Core 或 Worker Service 应用已经在用的 DI 容器。注册插件实现和注册任何其他服务完全一样——没有属性耦合，没有第二套组合层，没有历史包袱。MEF 了解一下作为历史背景无妨，但它不是 .NET 8+ 新插件系统的可行选项。

## 与 DependencyInjection 集成

集成的挑战是微妙的。正确的插件加载要求按契约接口注册，而不是按具体类型。当一个插件类型在隔离的 `AssemblyLoadContext` 里时，它的 `Type` 对象是上下文特有的。可靠的模式是按契约接口注册（来自共享默认上下文的类型），并直接提供具体实现的 `Type` 对象。`Microsoft.Extensions.DependencyInjection` 接受带有具体 `Type` 实例的 `ServiceDescriptor`，绕过任何名称查找，直接使用你已有的类型对象。

下面是一个扫描插件目录、注册所有给定契约实现的 `IServiceCollection` 扩展方法：

```csharp
using System.Reflection;
using Microsoft.Extensions.DependencyInjection;

public static class PluginServiceCollectionExtensions
{
    public static IServiceCollection AddPluginsFromDirectory<TContract>(
        this IServiceCollection services,
        string pluginDirectory,
        ServiceLifetime lifetime = ServiceLifetime.Singleton)
        where TContract : class
    {
        if (!Directory.Exists(pluginDirectory))
        {
            throw new DirectoryNotFoundException(
                $"Plugin directory not found: {pluginDirectory}");
        }

        // 用命名约定（如 "*.Plugin.dll"）而不是扫描所有 DLL——
        // 盲目扫描 "*.dll" 会把依赖程序集也扫进来，造成误报。
        var pluginFiles = Directory.EnumerateFiles(
            pluginDirectory, "*.Plugin.dll", SearchOption.TopDirectoryOnly);

        var contractType = typeof(TContract);

        foreach (var pluginPath in pluginFiles)
        {
            var context = new PluginLoadContext(pluginPath);
            Assembly assembly;

            try
            {
                assembly = context.LoadFromAssemblyPath(pluginPath);
            }
            catch
            {
                // 跳过无法加载的程序集（如原生 DLL）
                continue;
            }

            var implementations = assembly.GetTypes()
                .Where(t => contractType.IsAssignableFrom(t)
                         && t is { IsClass: true, IsAbstract: false });

            foreach (var implType in implementations)
            {
                // 按契约接口注册，而不是按具体类型
                services.Add(new ServiceDescriptor(contractType, implType, lifetime));
            }
        }

        return services;
    }
}
```

在 `Program.cs` 里注册只需一行：

```csharp
builder.Services.AddPluginsFromDirectory<IAnalyzer>(
    Path.Combine(AppContext.BaseDirectory, "plugins"));
```

如果团队用 Autofac 而不是内置容器，这个模式可以直接平移——注册机制等价，只是语法不同。

## 卸载插件与内存管理

如果插件在启动时加载并存活整个进程生命周期，卸载不是问题。上下文和程序集留在内存里直到进程退出，这对大多数生产场景是正确行为。

热重载改变了这个逻辑。如果你想在不重启宿主的情况下更新插件，需要卸载旧版本并加载新版本。这要求可回收上下文——用 `isCollectible: true` 创建的那种：

```csharp
public class UnloadablePluginLoadContext : AssemblyLoadContext
{
    private readonly AssemblyDependencyResolver _resolver;

    public UnloadablePluginLoadContext(string pluginPath)
        : base(
            name: Path.GetFileNameWithoutExtension(pluginPath),
            isCollectible: true) // 卸载所必需
    {
        _resolver = new AssemblyDependencyResolver(pluginPath);
    }

    protected override Assembly? Load(AssemblyName assemblyName)
    {
        string? path = _resolver.ResolveAssemblyToPath(assemblyName);
        return path is not null ? LoadFromAssemblyPath(path) : null;
    }
}

// 触发卸载并用 WeakReference 验证
public static void UnloadPlugin(ref UnloadablePluginLoadContext? context)
{
    if (context is null) return;

    var weakRef = new WeakReference(context);
    context.Unload();
    context = null; // GC 运行前先解除强引用

    // 强制 GC 回收上下文
    for (int i = 0; i < 10 && weakRef.IsAlive; i++)
    {
        GC.Collect();
        GC.WaitForPendingFinalizers();
    }

    if (weakRef.IsAlive)
    {
        // 仍有强引用持有着上下文
        throw new InvalidOperationException(
            "Plugin context could not be unloaded. Check for lingering references.");
    }
}
```

弱引用模式是 Microsoft 推荐的验证方式。如果经过多次 GC 后 `weakRef.IsAlive` 仍为 `true`，说明某个地方还有强引用——常见于持有插件类型的静态字段、捕获了插件实例的委托、或缓存的反射结果。卸载是全或无的：必须解除所有强引用，GC 才能回收上下文。

对于启动时加载、伴随进程生命周期的插件，用不可回收上下文。安全卸载的复杂度是真实的，遗漏的一个引用就能造成内存泄漏，比直接保留程序集在内存里更糟。可回收上下文留给开发期工具或明确设计了热重载功能的场景。

## 完整示例

把所有部分结合在一起。契约定义在一个被宿主和插件共同引用的共享项目里：

```csharp
// DevLeader.Analyzers.Contracts — 在默认上下文里的共享程序集

namespace DevLeader.Analyzers.Contracts;

public interface IAnalyzer
{
    string Name { get; }
    AnalysisResult Analyze(string input);
}

public record AnalysisResult(bool Passed, string Message);
```

宿主扫描 `plugins/` 目录，注册所有 `IAnalyzer` 实现，然后运行它们：

```csharp
// Program.cs
using DevLeader.Analyzers.Contracts;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = Host.CreateApplicationBuilder(args);

// 扫描 plugins/ 目录，注册所有 IAnalyzer 实现
builder.Services.AddPluginsFromDirectory<IAnalyzer>(
    Path.Combine(AppContext.BaseDirectory, "plugins"));

var host = builder.Build();

// 通过 IEnumerable<IAnalyzer> 解析所有已注册的分析器
var analyzers = host.Services.GetServices<IAnalyzer>();
foreach (var analyzer in analyzers)
{
    var result = analyzer.Analyze("sample input");
    Console.WriteLine($"[{analyzer.Name}] {(result.Passed ? "PASS" : "FAIL")}: {result.Message}");
}
```

每个插件项目只引用契约程序集，把完整发布输出（DLL、`.deps.json`、所有私有依赖）放到 `plugins/` 子目录。`AssemblyLoadContext` 透明地处理隔离和解析，不需要修改宿主或契约，添加新插件就是往目录里放文件。

## 常见问题

**AssemblyLoadContext 和 AppDomain 有什么区别？**

`AppDomain` 是 .NET Framework 的隔离原语，创建开销大，跨域通信需要序列化或 `MarshalByRefObject` 代理。.NET 5+ 已完全移除多 AppDomain 支持。`AssemblyLoadContext` 是现代替代品，提供程序集级隔离，没有进程开销，跨上下文通信直接（两个上下文共享同一 CLR 和内存空间）。需要注意的是，`AssemblyLoadContext` 只提供程序集隔离，不提供内存隔离——行为不当的插件仍然可以影响宿主内存。

**能不能加载两个依赖同一 NuGet 包不同版本的插件？**

可以——这正是 `AssemblyLoadContext` 隔离要解决的问题。每个插件有自己的 `PluginLoadContext` 实例，有自己指向自己目录的 `AssemblyDependencyResolver`。Plugin A 可以加载 `Newtonsoft.Json 12.0.3`，Plugin B 同时加载 `Newtonsoft.Json 13.0.3`，不冲突，因为每个版本在各自独立的上下文里。关键约束是：在插件和宿主之间流动的类型——契约类型——必须来自共享的默认上下文。如果 Plugin A 把它本地 `Newtonsoft.Json` 里的 `JObject` 传给宿主，宿主的类型系统不认识它。契约类型应当始终是在共享契约程序集里定义的简单类型，不应是插件可能独立版本化的第三方包里的类型。

**怎么给通过 AssemblyLoadContext 加载的插件传递配置？**

最干净的方式是在契约接口里定义配置访问——加一个 `Initialize(IConfiguration config)` 方法，或者接受契约程序集里定义的配置 POCO。因为 `Microsoft.Extensions.Configuration.IConfiguration` 是在默认上下文加载的共享程序集，宿主可以直接把配置实例传给插件，不需要序列化。另一种方式是在契约程序集里定义一个简单的设置 POCO，填好后传给插件。避免直接把 `IServiceProvider` 传进插件——这会把插件和宿主整个服务图紧密耦合，也让插件难以独立测试。

**AssemblyLoadContext 在 .NET Framework 上可用吗？**

不可用。`AssemblyLoadContext` 是 .NET Core / .NET 5+ 的 API，在 .NET Framework 4.x 上不存在。如果你在维护用 `AppDomain` 做隔离的 .NET Framework 插件系统，迁移路径是升级到 .NET 8 或更高，届时 `AssemblyLoadContext` 就可用了。没有把 `AssemblyLoadContext` 向后移植到 .NET Framework 的方案——这个 API 依赖 .NET Core 引入的统一运行时。如果一步迁移不现实，可以让契约程序集面向 `netstandard2.0`，宿主保持在 .NET 8+，这是最常见的分阶段过渡方式。

**怎么调试加载在独立 AssemblyLoadContext 里的插件？**

Visual Studio 和 JetBrains Rider 都支持调试非默认加载上下文里的程序集，前提是插件的 PDB 文件和 DLL 放在同一个 plugins 目录里。调试会话期间把上下文设为 `isCollectible: false`，避免卸载干扰调试器的符号状态。你也可以在插件初始化代码里嵌入 `Debugger.Launch()` 或 `Debugger.Break()`，在已知位置强制触发调试器接入。对于不需要交互式调试器的追踪和诊断，通过契约接口传入 `ILogger` 实例，把所有插件输出路由到宿主的日志管道——无论哪个插件产生的日志，都统一进入宿主配置的接收器。

## 小结

`AssemblyLoadContext` 配合 `AssemblyDependencyResolver` 是 .NET 插件加载的正确机制。它解决了 `Assembly.LoadFrom` 脆弱的依赖冲突问题，通过契约注册与 `Microsoft.Extensions.DependencyInjection` 干净集成，在需要时也支持热重载卸载。

几个关键决策值得提前想清楚：插件是否需要隔离上下文（真实插件系统几乎总是要）、是否需要可回收上下文（只用于热重载）、契约程序集住在哪里（始终在默认上下文，绝不重复加载进插件上下文）。

从这里展示的 `PluginLoadContext` 和 `AddPluginsFromDirectory` 模式出发，针对你的依赖图验证它们，然后从这个基础上扩展。不需要历史遗留框架，不需要属性耦合，只需要你的应用已经在用的工具。

## 参考

- [Plugin Loading in .NET: AssemblyLoadContext with Dependency Injection](https://www.devleader.ca/2026/04/09/plugin-loading-in-net-assemblyloadcontext-with-dependency-injection)
- [Plugin Architecture in C# for Improved Software Design](https://www.devleader.ca/2024/03/12/plugin-architecture-in-c-for-improved-software-design)
- [Plugin Architecture in ASP.NET Core: How to Master It](https://www.devleader.ca/2023/07/31/plugin-architecture-in-aspnet-core-how-to-master-it)
- [Plugin Architecture Design Pattern: A Beginner's Guide to Modularity](https://www.devleader.ca/2023/09/07/plugin-architecture-design-pattern-a-beginners-guide-to-modularity)
- [Plugin Architecture with Needlr in .NET](https://www.devleader.ca/2026/02/15/plugin-architecture-with-needlr-in-net-building-modular-applications)
