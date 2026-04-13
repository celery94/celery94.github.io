---
pubDatetime: 2026-04-13T07:59:00+08:00
title: "在 C# 中构建 VS Code 风格的扩展系统"
description: "VS Code 的扩展平台不只是简单的加载 DLL 调接口，它有一套完整的生命周期设计：Manifest 声明、贡献点注册、懒激活机制和作用域 API 隔离。本文从零开始，带你用 C#/.NET 8 实现这套结构，涵盖完整代码和关键设计决策。"
tags:
  [
    "C#",
    ".NET",
    "Plugin Architecture",
    "Extension System",
    "Software Architecture",
  ]
slug: "building-vscode-style-extension-system-csharp"
ogImage: "../../assets/729/01-cover.png"
source: "https://www.devleader.ca/2026/04/12/building-a-vs-codestyle-extension-system-in-c"
---

如果你曾经想给应用加插件能力，又觉得"把 DLL 加载进来调接口"不够用，那你想的其实就是 VS Code 解决的问题。VS Code 的扩展系统是现代工具链里设计得最完整的可扩展平台之一，它的核心结构可以直接移植到 C# 应用里。

先说一个重要区别：VS Code 的扩展是跑在独立 Node.js 进程里的，有真实的进程隔离边界。我们在 .NET 里实现的是进程内加载，插件和宿主共享同一个地址空间——行为不好的插件理论上可以影响宿主。这个权衡在后面会显式处理，但在开始之前值得先理解清楚。

这篇文章会从零开始，逐层搭建一个 VS Code 风格的扩展系统：Manifest 声明、贡献点、懒激活、作用域 API 隔离，以及把它们串联起来的 `ExtensionHost`。代码基于 .NET 8/9，大量使用 record、模式匹配和泛型约束。

![Building a VS Code-Style Extension System in C#](../../assets/729/02-vscode-extension-system.webp)

## VS Code 扩展模型的四个核心

大多数"插件系统"本质上是：加载这个 DLL，调用某个接口。简单场景够用，但 VS Code 解决的是更复杂的问题——管理生命周期、懒激活、作用域 API 访问和结构化贡献点。这四点是插件系统和真正扩展平台的分界线：

1. **Extension Manifest**：扩展提供什么、什么时候激活的结构化声明（VS Code 用 `package.json`，我们用 C# record 加 `extension.json`）
2. **贡献点（Contribution Points）**：宿主提供的命名钩子，扩展把能力注册进去
3. **激活事件（Activation Events）**：懒激活触发器，推迟加载直到真正需要
4. **Extension API 隔离**：给每个扩展一个作用域上下文，控制它能访问宿主的哪些服务

## Extension Manifest：先描述自己，再谈加载

VS Code 里每个扩展都有一个 `package.json`，声明自己的身份、能力和激活触发器。我们用强类型的 `ExtensionManifest` record 加 `extension.json` 文件实现同样的效果。

```csharp
// ExtensionManifest.cs
public sealed record ExtensionManifest
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required string Version { get; init; }
    public string Description { get; init; } = string.Empty;

    // 触发激活的事件，如 "onStartup"、"onCommand:myCmd"
    public string[] ActivationEvents { get; init; } = [];

    // 扩展注册的贡献点，值是灵活的 JSON 结构
    public Dictionary<string, JsonElement> Contributes { get; init; } = [];
}
```

加载 Manifest 的类很简单：

```csharp
// ExtensionLoader.cs
public static class ExtensionLoader
{
    private static readonly JsonSerializerOptions _options = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static ExtensionManifest? LoadManifest(string extensionDirectory)
    {
        var manifestPath = Path.Combine(extensionDirectory, "extension.json");
        if (!File.Exists(manifestPath))
            return null;

        var json = File.ReadAllText(manifestPath);
        return JsonSerializer.Deserialize<ExtensionManifest>(json, _options);
    }
}
```

**为什么要先加载 Manifest？** 这个设计决策很关键——在碰触任何程序集之前先读 Manifest。如果 Manifest 缺失或格式错误，扩展直接排除在外。这意味着你可以在不加载任何 DLL 的情况下枚举所有已安装扩展及其贡献点——发现成本低，激活推迟。

## 贡献点：扩展注册能力，宿主决定调用

VS Code 扩展模型最强的地方就是贡献点。扩展不直接调用宿主内部逻辑，而是把能力注册到命名钩子里，宿主决定何时如何使用它们。

核心抽象是一个泛型接口：

```csharp
// IExtensionPoint.cs
public interface IExtensionPoint<T>
{
    string Name { get; }
    void Register(string extensionId, T contribution);
    IReadOnlyList<(string ExtensionId, T Contribution)> GetAll();
}

// ExtensionPointRegistry.cs
public sealed class ExtensionPointRegistry
{
    private readonly Dictionary<string, object> _points = new();

    public void Register<T>(IExtensionPoint<T> point)
        => _points[point.Name] = point;

    public IExtensionPoint<T> Resolve<T>(string name)
    {
        if (_points.TryGetValue(name, out var point) && point is IExtensionPoint<T> typed)
            return typed;

        throw new InvalidOperationException(
            $"No extension point '{name}' registered for type '{typeof(T).Name}'.");
    }

    public bool TryResolve<T>(string name, out IExtensionPoint<T>? point)
    {
        if (_points.TryGetValue(name, out var raw) && raw is IExtensionPoint<T> typed)
        {
            point = typed;
            return true;
        }
        point = null;
        return false;
    }
}
```

一个具体的命令贡献点长这样：

```csharp
// CommandExtensionPoint.cs
public sealed class CommandExtensionPoint : IExtensionPoint<Func<string[], Task>>
{
    private readonly List<(string ExtensionId, Func<string[], Task> Handler)> _registrations = [];

    public string Name => "commands";

    public void Register(string extensionId, Func<string[], Task> contribution)
        => _registrations.Add((extensionId, contribution));

    public IReadOnlyList<(string ExtensionId, Func<string[], Task> Contribution)> GetAll()
        => _registrations.AsReadOnly();
}
```

宿主调用 `Resolve<Func<string[], Task>>("commands")` 就能拿到所有已注册的命令处理器，完全不关心是哪个扩展贡献的。你可以为任何贡献类型创建扩展点：`IDataSource`、`IMenuContribution`、`IStatusBarItem`、`IAnalyzer`。每个都是一个有名字的类型化注册桶。

## 懒激活：推迟加载，保持启动速度

VS Code 快的一个原因就是扩展不全在启动时加载，而是根据激活事件按需加载。扩展在 Manifest 里声明 `onCommand:myCommand`、`onStartup`、`onFileOpen` 等事件，宿主触发对应事件时才加载并初始化。

```csharp
// IActivationCondition.cs
public interface IActivationCondition
{
    bool ShouldActivate(string activationEvent);
}

// ManifestActivationCondition.cs
public sealed class ManifestActivationCondition : IActivationCondition
{
    private readonly ExtensionManifest _manifest;

    public ManifestActivationCondition(ExtensionManifest manifest)
        => _manifest = manifest;

    public bool ShouldActivate(string activationEvent)
        => _manifest.ActivationEvents.Contains("*") ||
           _manifest.ActivationEvents.Contains(activationEvent);
}

// IExtension.cs — 所有扩展的入口契约
public interface IExtension
{
    Task ActivateAsync(IExtensionContext context);
    Task DeactivateAsync();
}

// ExtensionActivator.cs
public sealed class ExtensionActivator
{
    private readonly ExtensionPointRegistry _registry;
    private readonly Dictionary<string, bool> _activated = new();

    public ExtensionActivator(ExtensionPointRegistry registry)
        => _registry = registry;

    public async Task ActivateAsync(
        string extensionId,
        IExtension extension,
        IActivationCondition condition,
        string activationEvent,
        IExtensionContext context)
    {
        if (_activated.GetValueOrDefault(extensionId))
            return;

        if (!condition.ShouldActivate(activationEvent))
            return;

        await extension.ActivateAsync(context);
        _activated[extensionId] = true;
    }
}
```

`ActivationEvents` 里的 `"*"` 通配符对应 VS Code 的 `"*"` 激活——意思是"启动时立即激活"。**谨慎使用**。只有真正需要从第一时刻就能用的扩展才应该声明它，其他的一律懒加载。

## 宿主 API 隔离：作用域上下文

这是大多数扩展系统做错的地方。如果你把 `IServiceProvider` 直接给扩展，它就能解析容器里的任何东西——安全问题和耦合噩梦。

VS Code 的做法是给每个扩展一个作用域上下文，只暴露宿主明确决定共享的内容：

```csharp
// IExtensionContext.cs — 扩展能看到的宿主表面
public interface IExtensionContext
{
    string ExtensionId { get; }
    IExtensionLogger Logger { get; }
    IExtensionConfiguration Configuration { get; }
    ICommandRegistry Commands { get; }
    IExtensionStorage Storage { get; }
}

// ExtensionContext.cs — 由宿主构建的作用域实现
public sealed class ExtensionContext : IExtensionContext
{
    public ExtensionContext(
        string extensionId,
        ILogger hostLogger,
        IConfiguration hostConfiguration,
        ICommandRegistry commands,
        IExtensionStorage storage)
    {
        ExtensionId = extensionId;
        Commands = commands;
        Storage = storage;

        // 按扩展 ID 作用域化 logger 和 configuration
        Logger = new ScopedExtensionLogger(extensionId, hostLogger);
        Configuration = new ScopedExtensionConfiguration(extensionId, hostConfiguration);
    }

    public string ExtensionId { get; }
    public IExtensionLogger Logger { get; }
    public IExtensionConfiguration Configuration { get; }
    public ICommandRegistry Commands { get; }
    public IExtensionStorage Storage { get; }
}
```

扩展调用 `context.Commands.Register(...)`、`context.Logger.LogInformation(...)` 和 `context.Storage.Get(...)`，永远看不到宿主的服务容器、数据库连接或其他内部状态。宿主拥有这个表面，扩展在其中工作。

## 扩展注册表：发现和版本冲突处理

一个完整的扩展系统需要发现层。注册表扫描目录里已安装的扩展，加载 Manifest，处理版本冲突，准备待激活的条目：

```csharp
// ExtensionRegistry.cs
public sealed class ExtensionRegistry
{
    private readonly string _extensionsRoot;
    private readonly Dictionary<string, (ExtensionManifest Manifest, string Directory)> _entries = new();

    public ExtensionRegistry(string extensionsRoot)
        => _extensionsRoot = extensionsRoot;

    public void Discover()
    {
        if (!Directory.Exists(_extensionsRoot))
            return;

        foreach (var dir in Directory.GetDirectories(_extensionsRoot))
        {
            var manifest = ExtensionLoader.LoadManifest(dir);
            if (manifest is null)
                continue;

            // 版本冲突：保留版本号更高的
            if (_entries.TryGetValue(manifest.Id, out var existing))
            {
                var existingVersion = Version.Parse(existing.Manifest.Version);
                var incomingVersion = Version.Parse(manifest.Version);
                if (incomingVersion <= existingVersion)
                    continue;
            }

            _entries[manifest.Id] = (manifest, dir);
        }
    }

    public IReadOnlyDictionary<string, (ExtensionManifest Manifest, string Directory)> GetAll()
        => _entries.AsReadOnly();
}
```

注意：这里的版本冲突解决很简单——高版本优先。`System.Version`（`Version.Parse`）只处理四段数字版本号，**不支持** SemVer 预发布标签（如 `1.2.0-beta.1`）。如果你的扩展版本用完整 SemVer，需要引入专门的 SemVer 解析库。

## 串联所有部件：ExtensionHost

`ExtensionHost` 是整个扩展系统运行时的核心协调者：

```csharp
// ExtensionHost.cs
public sealed class ExtensionHost
{
    private readonly ExtensionRegistry _registry;
    private readonly ExtensionPointRegistry _pointRegistry;
    private readonly ExtensionActivator _activator;
    private readonly IServiceProvider _services;
    private readonly Dictionary<string, IExtension> _loaded = new();

    public ExtensionHost(
        ExtensionRegistry registry,
        ExtensionPointRegistry pointRegistry,
        IServiceProvider services)
    {
        _registry = registry;
        _pointRegistry = pointRegistry;
        _activator = new ExtensionActivator(pointRegistry);
        _services = services;
    }

    public async Task StartupAsync()
    {
        _registry.Discover();

        foreach (var (id, (manifest, directory)) in _registry.GetAll())
        {
            var extension = LoadExtension(id, directory);
            if (extension is null)
                continue;

            var context = BuildContext(id);
            var condition = new ManifestActivationCondition(manifest);

            // 只激活声明了 onStartup 的扩展
            await _activator.ActivateAsync(id, extension, condition, "onStartup", context);
        }
    }

    public async Task FireEventAsync(string activationEvent)
    {
        foreach (var (id, (manifest, directory)) in _registry.GetAll())
        {
            var extension = LoadExtension(id, directory);
            if (extension is null)
                continue;

            var context = BuildContext(id);
            var condition = new ManifestActivationCondition(manifest);

            await _activator.ActivateAsync(id, extension, condition, activationEvent, context);
        }
    }

    private IExtension? LoadExtension(string id, string directory)
    {
        if (_loaded.TryGetValue(id, out var cached))
            return cached;

        var assemblyPath = Path.Combine(directory, $"{id}.dll");
        if (!File.Exists(assemblyPath))
            return null;

        // 这里用 Assembly.LoadFrom 简化演示。
        // 生产环境请替换为 AssemblyLoadContext (isCollectible: true)
        // 以便扩展隔离并可独立卸载。
        var assembly = Assembly.LoadFrom(assemblyPath);
        var extensionType = assembly
            .GetExportedTypes()
            .FirstOrDefault(t => typeof(IExtension).IsAssignableFrom(t) && !t.IsAbstract);

        if (extensionType is null || Activator.CreateInstance(extensionType) is not IExtension ext)
            return null;

        _loaded[id] = ext;
        return ext;
    }

    private IExtensionContext BuildContext(string extensionId)
    {
        var logger = _services.GetRequiredService<ILogger<ExtensionHost>>();
        var config = _services.GetRequiredService<IConfiguration>();
        var commands = _services.GetRequiredService<ICommandRegistry>();
        var storage = _services.GetRequiredService<IExtensionStorage>();
        return new ExtensionContext(extensionId, logger, config, commands, storage);
    }
}
```

端到端流程和 VS Code 一致：启动时发现所有 Manifest 并激活声明了 `onStartup` 的扩展，其他扩展保持休眠。当用户触发命令时，`FireEventAsync("onCommand:myCommand")` 激活匹配的扩展，它的贡献立即通过注册的贡献点可用。

## 和 VS Code 真实 API 的对比

VS Code 的实际实现走得更远：

- 扩展跑在独立的 Node.js Worker 进程里，通过 IPC 通信
- VSIX 打包格式包含转译、打包和签名验证
- Language Server Protocol 是一等扩展接口
- 渲染进程和扩展宿主进程分开沙箱化

我们构建的版本抓住了结构精髓——Manifest、贡献点、懒激活、作用域 API——但没有进程隔离开销。对大多数 .NET 应用来说，这是合适的权衡。

**这个模式什么时候是过度设计：**

- 小型内部应用，`List<IPlugin>` 够用
- 所有扩展都是自有第一方、随产品一起发布
- 不需要版本化、独立部署的扩展

**这个模式什么时候值得投入：**

- IDE 和开发者工具（VS Code 的原始使用场景）
- CMS 平台，第三方扩展内容模型
- CI/CD 流水线执行器，流水线步骤由插件贡献
- 数据处理平台，数据源、转换器和目标都是扩展点

当你有独立团队或第三方来贡献你不完全控制的扩展时，Manifest + 贡献点 + 激活事件这套投入就值得了。

## 常见问题

**扩展系统和基础插件架构有什么区别？**

基础插件架构是：加载程序集，实现接口，调用它。扩展系统在上面加了一层生命周期：Manifest 描述插件贡献什么和何时激活，贡献点结构化地定义插件在哪里挂入宿主，激活事件控制延迟加载，作用域 API 限定插件能访问什么。区别在于"实现这个接口"和"参与这个平台"之间的差距。

**需要额外的 NuGet 包吗？**

不需要。核心模式只用 BCL（`System.Text.Json`、`System.Reflection`、`System.IO`）。如果想给每个扩展独立的 DI 容器，`Microsoft.Extensions.DependencyInjection` 是自然选择。更复杂的程序集隔离，用 BCL 里的 `System.Runtime.Loader.AssemblyLoadContext`。

**能沙箱化扩展防止访问敏感宿主 API 吗？**

同一个 CLR 进程内无法完全沙箱化托管代码——那个层面没有安全边界。实际的缓解措施：作用域化的 `IExtensionContext` 模式限制了扩展能通过公开 API 表面访问的内容，无法解析宿主内部服务。要真正隔离，需要把扩展跑在独立进程里，通过命名管道或 gRPC 通信——延迟增加，但有真实的进程边界。

## 总结

把这套结构拆开来看，每个部件都在解决朴素插件加载的某个具体问题：

- **ExtensionManifest**：在加载程序集之前，给你一个版本化的、结构化的"这个扩展能做什么"的描述
- **ExtensionPointRegistry**：命名贡献钩子，扩展注册进去，宿主不关心贡献来自哪里
- **ExtensionActivator**：懒加载，扩展生态扩大时启动速度不受影响
- **IExtensionContext**：宿主和扩展之间的明确边界

从 Manifest 和贡献点开始——剩下的系统可以随着你的可扩展性需求增量演化。

## 参考

- [Building a VS Code-Style Extension System in C#](https://www.devleader.ca/2026/04/12/building-a-vs-codestyle-extension-system-in-c)
- [Plugin Architecture Design Pattern — A Beginner's Guide to Modularity](https://www.devleader.ca/plugin-architecture-design-pattern-beginners-guide-to-modularity/)
