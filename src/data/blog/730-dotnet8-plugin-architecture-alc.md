---
pubDatetime: 2026-04-13T10:29:00+08:00
title: ".NET 8+ 插件架构设计：基于 AssemblyLoadContext 的完整方案"
description: "本文从官方文档、官方样例和 McMaster.NETCore.Plugins 出发，系统梳理 .NET 8+ 环境下插件系统的核心机制、设计约束和工程落地方法。包括 ALC 隔离模型、共享契约边界、依赖解析、卸载规则、Native AOT 限制，以及从"可信 in-proc"到"不可信 sidecar"的双模式选型建议。"
tags: ["dotnet", "plugin", "architecture", "csharp"]
slug: "dotnet8-plugin-architecture-alc"
ogImage: "../../assets/730/01-cover.png"
source: "https://github.com/dotnet/docs/blob/main/docs/core/tutorials/creating-app-with-plugin-support.md"
---

如果你曾经尝试在 .NET 项目里做插件系统，早期大概率踩过 `Assembly.LoadFrom` 带来的版本冲突、依赖污染、卸载无法完成这些坑。.NET Core / .NET 5+ 之后，官方提供了 `AssemblyLoadContext`（ALC），这是现在做 .NET 插件系统的基础设施。

这篇文章整理的是 .NET 8+ 环境下插件系统的完整设计方案，覆盖从核心机制到工程落地的主要决策点，包括卸载、热更新、安全隔离和 Native AOT 限制。所有结论优先来自官方文档和官方样例，第三方库作为补充参考。

## 为什么 ALC 才是正确起点

.NET 8+ 里，每个 `AssemblyLoadContext` 是一个独立的程序集加载边界。同一进程里可以有多个 ALC，同一个程序集名称可以在不同 ALC 里各自加载一个版本，互不干扰。

这直接解决了旧式 `Assembly.LoadFrom` 的三个核心问题：

1. **版本隔离**：插件 A 依赖 `Newtonsoft.Json 12.0`，插件 B 依赖 `Newtonsoft.Json 13.0`，两者可以共存。
2. **依赖不污染宿主**：插件的私有依赖不会意外覆盖宿主里已有的程序集。
3. **可卸载**：把 ALC 标记为 collectible 后，能在运行时卸载插件并释放内存（有约束，后面说）。

官方文档的表述是：ALC 负责隔离、分组和版本控制，是运行时程序集加载的基础组件。

## 架构全景

下面这个图描述了一个典型的双层插件架构：

```
┌─────────────────────────────────────────────┐
│                宿主进程                       │
│  ┌──────────────────────────────────────┐    │
│  │      Plugin.Abstractions (Default ALC)│    │  ← 共享契约，唯一来源
│  └──────────────────────────────────────┘    │
│           │ 类型共享                           │
│  ┌────────┴──────────────────────────────┐   │
│  │         PluginManager / DI             │   │  ← 发现、加载、生命周期
│  └────────────────────────────────────────┘  │
│       │            │            │             │
│  ┌────▼────┐  ┌────▼────┐  ┌───▼─────┐      │
│  │Plugin A │  │Plugin B │  │Plugin C │      │  ← 每个插件一个 collectible ALC
│  │ ALC     │  │ ALC     │  │ ALC     │      │
│  └─────────┘  └─────────┘  └─────────┘      │
└─────────────────────────────────────────────┘
```

关键约束只有一条：**共享契约（接口 + DTO）只能存在于 Default ALC**。插件引用契约程序集，但不能把它复制到自己的输出目录。

## 共享类型边界：这是最容易出错的地方

官方文档描述了一个非常反直觉的行为：即使两个程序集名称、版本、内容完全一致，从不同 ALC 加载的结果是两个不同的 `Type` 对象。代码层面的表现是 `(IPlugin)pluginInstance` 的类型转换会失败，抛 `InvalidCastException`。

正确做法：契约接口和 DTO 必须从 **Default ALC**（宿主那侧）统一加载。插件项目引用契约 ProjectReference 时，必须加 `<Private>false</Private>`，阻止契约 DLL 被复制到插件输出目录：

```xml
<ProjectReference Include="..\..\Plugin.Abstractions\Plugin.Abstractions.csproj">
  <Private>false</Private>
  <ExcludeAssets>runtime</ExcludeAssets>
</ProjectReference>
```

NuGet 包形式的契约同理，用 `<ExcludeAssets>runtime</ExcludeAssets>` 阻止它被放进插件的私有依赖目录。

## PluginLoadContext：官方推荐实现

官方样例（[dotnet/samples AppWithPlugin](https://github.com/dotnet/samples/tree/main/core/extensions/AppWithPlugin)）给出了一个标准的 `PluginLoadContext`：

```csharp
internal class PluginLoadContext : AssemblyLoadContext
{
    private readonly AssemblyDependencyResolver _resolver;

    public PluginLoadContext(string pluginPath) : base(isCollectible: true)
    {
        _resolver = new AssemblyDependencyResolver(pluginPath);
    }

    protected override Assembly? Load(AssemblyName assemblyName)
    {
        // 先用插件自己的依赖解析器找
        string? assemblyPath = _resolver.ResolveAssemblyToPath(assemblyName);
        if (assemblyPath != null)
            return LoadFromAssemblyPath(assemblyPath);

        // 找不到则回退到默认上下文（宿主/框架程序集）
        return null;
    }

    protected override IntPtr LoadUnmanagedDll(string unmanagedDllName)
    {
        string? libraryPath = _resolver.ResolveUnmanagedDllToPath(unmanagedDllName);
        if (libraryPath != null)
            return LoadUnmanagedDllFromPath(libraryPath);

        return IntPtr.Zero;
    }
}
```

`AssemblyDependencyResolver` 读取插件目录下的 `.deps.json`，按正确顺序查找 NuGet 包和本机库，不需要手动拼路径。`Load` 返回 `null` 时，运行时自动回退到 Default ALC，这样契约和框架程序集就能共享。

## 插件契约设计

契约层保持最小化，只放接口和 DTO：

```csharp
// Plugin.Abstractions 项目
public interface IPlugin
{
    string Name { get; }
    string Description { get; }
    IEnumerable<ICommand> GetCommands();
}

public interface ICommand
{
    string Name { get; }
    string Description { get; }
    Task ExecuteAsync(string[] args);
}
```

如果需要 DI 支持，加一个模块接口：

```csharp
public interface IPluginModule
{
    void ConfigureServices(IServiceCollection services, IConfiguration configuration);
    Task StartAsync(CancellationToken cancellationToken);
    Task StopAsync(CancellationToken cancellationToken);
}
```

不要在契约里放任何会引入大量框架依赖的类型。

## plugin.json manifest

每个插件目录放一个 `plugin.json`，记录元数据和兼容性信息：

```json
{
  "id": "my-plugin",
  "version": "2.0.0",
  "entryPoint": "MyPlugin.dll",
  "hostApiVersion": ">=1.0.0 <2.0.0",
  "requiredFrameworks": ["Microsoft.NETCore.App"],
  "signature": "sha256:abc123..."
}
```

`PluginManager` 在装载前先读这个文件，做版本兼容检查和签名校验，不符合的直接拒绝，不进入 ALC 加载流程。

## 插件项目的 MSBuild 要求

插件项目必须加 `<EnableDynamicLoading>true</EnableDynamicLoading>`：

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <EnableDynamicLoading>true</EnableDynamicLoading>
  </PropertyGroup>

  <ItemGroup>
    <!-- 阻止契约 DLL 被复制到插件输出目录 -->
    <ProjectReference Include="..\..\Plugin.Abstractions\Plugin.Abstractions.csproj">
      <Private>false</Private>
      <ExcludeAssets>runtime</ExcludeAssets>
    </ProjectReference>
  </ItemGroup>
</Project>
```

`EnableDynamicLoading` 让 SDK 生成 `runtimeconfig.json` 并把 NuGet 依赖复制到本地，这是 `AssemblyDependencyResolver` 能正确工作的前提。

插件**必须**用运行时 TFM（`net8.0`），不要用 `netstandard2.0`——后者生成的 `runtimeconfig.json` 格式有差异，`AssemblyDependencyResolver` 解析会失败。

每个插件必须发布到独立的子目录，不能和其他插件共用一个目录。共用目录会导致 `.deps.json` 依赖解析互相干扰。

## 宿主加载流程

```csharp
public class PluginManager
{
    private readonly List<PluginHandle> _loaded = new();

    public async Task<IPlugin> LoadAsync(string pluginDirectory)
    {
        // 1. 读 manifest，做兼容性和签名检查
        var manifest = await PluginManifest.ReadAsync(pluginDirectory);
        PluginCompatibilityChecker.Verify(manifest);

        // 2. 找入口 DLL
        var entryDll = Path.Combine(pluginDirectory, manifest.EntryPoint);

        // 3. 创建 collectible ALC
        var alc = new PluginLoadContext(entryDll);

        // 4. 加载程序集，找实现了 IPlugin 的类型
        var assembly = alc.LoadFromAssemblyPath(entryDll);
        var pluginType = assembly.GetTypes()
            .Single(t => typeof(IPlugin).IsAssignableFrom(t) && !t.IsAbstract);

        // 5. 实例化
        var plugin = (IPlugin)Activator.CreateInstance(pluginType)!;

        _loaded.Add(new PluginHandle(alc, plugin));
        return plugin;
    }
}
```

## 卸载：cooperative，不是强制

`AssemblyLoadContext.Unload()` 发起卸载请求，但不保证立刻完成。真正卸载发生的条件：

- 没有线程在执行插件代码
- 没有类型、实例或程序集被强引用
- 没有强 GC handle 持有插件对象

官方文档建议用弱引用轮询来确认卸载完成：

```csharp
public void Unload(PluginHandle handle)
{
    var weakRef = new WeakReference(handle.Context);
    handle.Context.Unload();

    // 等待 GC 回收
    for (int i = 0; weakRef.IsAlive && i < 10; i++)
    {
        GC.Collect();
        GC.WaitForPendingFinalizers();
    }

    if (weakRef.IsAlive)
    {
        // 卸载失败，记录审计日志，排查哪里还有强引用
        _logger.LogWarning("Plugin {Name} ALC not collected after 10 GC cycles", handle.Plugin.Name);
    }
}
```

插件自身必须在 `StopAsync` 里主动停止后台线程、释放 Timer、清空静态缓存。只要还有一个线程在执行插件代码，ALC 就无法被回收。

另外两个限制：collectible ALC 下，C++/CLI 代码不被支持；ReadyToRun 代码会被忽略、以 IL 重新 JIT。如果插件里有 C++/CLI 组件，就不能用 collectible 模式，要么放弃卸载能力，要么改用 sidecar 方案。

## 热更新：先不要做，有需要再加

热更新本质是：

1. 检测插件目录文件变化
2. 卸载旧 ALC
3. 加载新版本到新 ALC

McMaster.NETCore.Plugins 提供了 `EnableHotReload`、`ReloadDelay`、`LoadInMemory` 和 `Reloaded` 事件来简化这个流程。但热更新需要插件严格遵守卸载规则（没有后台线程、没有静态引用泄漏），否则旧 ALC 永远无法被回收，内存会持续增长。

建议是：第一版先做 **restart-safe**（重启宿主后加载新插件版本），不做 hot reload。hot reload 留到团队对插件的卸载规范建立信心之后再加。

## 安全边界：ALC 不是安全隔离

官方文档明确说明：不可信代码不能安全加载到可信 .NET 进程里。ALC 提供的是版本隔离，不是进程间安全隔离。

如果插件来自第三方、用户提交或外部脚本，应该用 **sidecar 进程**方案：

```
宿主进程  ←── gRPC / named pipes / JSON-RPC ──→  插件进程（独立进程）
```

sidecar 进程有独立的身份、工作目录和资源限制，插件崩溃不影响宿主，升级和回滚也更干净。

可信内部插件（自己团队维护的功能模块）适合 in-proc ALC 方案，并加上签名校验、白名单 capability 和加载超时。

## Native AOT 和 Trimming 的硬限制

两个不可绕过的边界：

**Native AOT**：Native AOT 明确不支持动态加载（`Assembly.LoadFile`、`Assembly.LoadFrom`）。插件宿主如果要运行时动态加载插件，就不能发布为 Native AOT。

**Trimming**：Trimmer 在构建时分析代码，动态加载的程序集在构建时不可见，trimmer 无法知道要保留哪些方法。开启激进 trimming 的宿主加载插件时，插件依赖的反射目标可能已经被裁剪掉。

实践规则：
- 宿主默认不开激进 trimming，不发布为 Native AOT
- 插件如果有 trim 需要，只能在代码路径完全已知、反射点可声明的前提下谨慎使用
- 插件发布为**外部独立目录**（含 `.deps.json` + 私有依赖），不要做单文件插件

## 是否引入 McMaster.NETCore.Plugins

[McMaster.NETCore.Plugins](https://github.com/natemcmaster/DotNetCorePlugins) 封装了大量 ALC 细节，提供：

- `sharedTypes` 配置：显式指定哪些类型跨 ALC 共享
- `PreferSharedTypes`：优先使用宿主加载的版本
- `EnableHotReload`：文件变化时自动触发 reload
- `LoadInMemory`：内存加载，避免文件锁
- MVC/Razor 插件支持（`McMaster.NETCore.Plugins.Mvc`）

如果插件模型简单，裸 ALC 完全够用，不用引入外部库。如果需要 MVC 插件、热更新或精细的类型共享控制，McMaster.NETCore.Plugins 能省不少底层代码。v2.0+ 支持 .NET 8。

注意：用 McMaster.NETCore.Plugins 时，插件 TFM 同样不要用 `netstandard2.0`，原因和裸 ALC 一样。

## 分阶段落地

**第一阶段：把稳定边界做对**

- 建立 `Plugin.Abstractions` 包，只放接口和 DTO
- 实现 `PluginCatalog`、`PluginCompatibilityChecker`、`PluginManager`
- 每插件一目录、每插件一 collectible ALC
- 先支持 restart-safe 发布，不做 hot reload

**第二阶段：补足工程化**

- 加 `plugin.json` manifest 与签名校验
- 加 DI 模块接口和白名单共享服务
- 加审计日志、健康检查、加载指标、失败分类

**第三阶段：按需增强**

- 若需要高级装载能力，引入 McMaster.NETCore.Plugins
- 若需要热更新，引入 collectible 卸载观测和弱引用回收检查
- 若插件来源不可信，落地 sidecar 方案，废弃 in-proc 装载

## 总结

.NET 8+ 插件系统的最佳默认方案：**Host + Abstractions + 每插件独立 publish 目录 + 每插件 collectible ALC + AssemblyDependencyResolver + 受控 DI 边界**。对不可信插件，向外升级为 sidecar 进程。

这个方案和官方文档、官方样例、McMaster.NETCore.Plugins 的设计共识最一致，也是最适合长期维护的选择。

## 参考

- [Creating a .NET application with plugins (官方教程)](https://learn.microsoft.com/dotnet/core/tutorials/creating-app-with-plugin-support)
- [Understanding AssemblyLoadContext (官方文档)](https://learn.microsoft.com/dotnet/core/dependency-loading/understanding-assemblyloadcontext)
- [How to use and debug assembly unloadability (官方文档)](https://learn.microsoft.com/dotnet/standard/assembly/unloadability)
- [Native AOT deployment overview](https://learn.microsoft.com/dotnet/core/deploying/native-aot/)
- [Trimming incompatibilities](https://learn.microsoft.com/dotnet/core/deploying/trimming/incompatibilities)
- [dotnet/samples AppWithPlugin 示例](https://github.com/dotnet/samples/tree/main/core/extensions/AppWithPlugin)
- [McMaster.NETCore.Plugins (natemcmaster)](https://github.com/natemcmaster/DotNetCorePlugins)
