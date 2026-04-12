---
pubDatetime: 2026-04-12T14:38:06+08:00
title: "C# 插件架构测试策略：让可扩展系统经得起考验"
description: "插件架构让系统具备运行时扩展能力，但也让测试变得更复杂。本文介绍三层测试方法——契约测试、单元测试、集成测试——每层针对不同的失败模式，帮助你为动态加载的插件系统建立可靠的测试体系。"
tags: ["C#", ".NET", "单元测试", "插件架构", "软件架构"]
slug: "testing-plugin-architectures-csharp-strategies-extensible-systems"
ogImage: "../../assets/727/01-cover.jpg"
source: "https://www.devleader.ca/2026/04/11/testing-plugin-architectures-in-c-strategies-for-extensible-systems"
---

![C# 插件架构测试策略封面](../../assets/727/01-cover.jpg)

如果你构建过插件架构，就知道它的核心能力：插件在运行时被发现、动态加载，并针对宿主定义的契约接口执行。这套机制的开放性让它强大，也让测试变得棘手——你没法像普通测试那样实例化对象、注入假依赖、调用方法、断言结果。

问题在于，一旦插件边界出了问题，它几乎是"隐形"的，直到生产环境崩溃才会冒头。这恰恰说明认真测试插件架构比普通系统更重要。

本文拆解三层测试策略：验证插件实现、校验契约符合度，以及集成测试完整的宿主+插件加载流程。

## 为什么插件架构测试与众不同

常规单元测试的套路很简单：构造对象、注入 fake、调用方法、断言结果。插件架构在三个维度上打破了这个套路。

**第一，插件是运行时发现的。** 宿主从目录扫描 DLL、反射类型、激活实现契约接口的对象。你没法像普通 DI 那样预先把依赖连接好。

**第二，系统是故意开放的。** 今天的插件会在下个月和别人写的插件并存。你的测试套件枚举不完所有未来的插件——但它可以验证任何插件是否满足契约。

**第三，失败模式不同。** 初始化时抛异常的插件不应该让宿主崩溃，缺失目录不应该中止启动，编译时依赖旧契约版本的插件不应该悄悄出错。

这三个现实对应三层测试：

- **契约测试**：任何插件是否满足接口预期？
- **单元测试**：每个具体插件是否能正确完成它的任务？
- **集成测试**：宿主能否正确发现、加载并端到端执行插件？

层次分清楚之后，单元测试失败说明某个插件的逻辑有问题，契约测试失败说明插件不再满足接口预期，集成测试失败说明加载管道本身出了毛病。这种精确性让调试从"玄学"变成了"可追溯"。

## 单元测试插件实现

具体的插件类本质上还是一个普通类，用不着什么特殊手段——实例化、调用方法、断言结果就够了。

```csharp
// 插件契约（放在共享契约程序集中）
public interface IAnalyticsPlugin
{
    string Name { get; }
    Task<AnalyticsSummary> ComputeAsync(IReadOnlyList<DataPoint> data);
}

// 具体插件（放在单独的插件程序集中）
public class AverageAnalyticsPlugin : IAnalyticsPlugin
{
    public string Name => "Average";

    public Task<AnalyticsSummary> ComputeAsync(IReadOnlyList<DataPoint> data)
    {
        var avg = data.Average(d => d.Value);
        return Task.FromResult(new AnalyticsSummary(avg));
    }
}
```

用 xUnit 测试非常直接：

```csharp
public class AverageAnalyticsPluginTests
{
    [Fact]
    public async Task ComputeAsync_WithValidData_ReturnsCorrectAverage()
    {
        var plugin = new AverageAnalyticsPlugin();
        var data = new List<DataPoint>
        {
            new(10.0), new(20.0), new(30.0)
        };

        var result = await plugin.ComputeAsync(data);

        Assert.Equal(20.0, result.Value, precision: 5);
    }

    [Fact]
    public void Name_ReturnsExpectedIdentifier()
    {
        var plugin = new AverageAnalyticsPlugin();
        Assert.Equal("Average", plugin.Name);
    }
}
```

如果插件依赖 `IServiceProvider`，别急着用复杂的 mock 框架——直接构建一个最小化的内存 DI 容器，可读性更好，也更接近插件的真实运行方式：

```csharp
[Fact]
public async Task ComputeAsync_WithServiceProvider_ResolvesCorrectly()
{
    var services = new ServiceCollection();
    services.AddSingleton<IDataNormalizer, PassThroughNormalizer>();
    var provider = services.BuildServiceProvider();

    var plugin = new NormalizedAnalyticsPlugin(provider);
    var data = new List<DataPoint> { new(100.0) };

    var result = await plugin.ComputeAsync(data);

    Assert.NotNull(result);
}
```

这种做法避免了 mock 框架的开销，同时也迫使插件构造函数只接受它真正需要的东西。

## 契约测试：验证所有插件都满足接口

单元测试单个插件是必要的，但不够用。随着插件生态扩大，你需要一种机制来保证每一个插件——无论当前还是未来的——都满足完整契约。

**契约测试模式**解决这个问题：创建一个抽象 xUnit 基类，定义每个插件都必须通过的测试。具体的测试类继承基类，并提供待测插件的实例：

```csharp
// 抽象基类——所有插件都必须通过这些测试
public abstract class PluginContractTests<TPlugin>
    where TPlugin : IAnalyticsPlugin
{
    protected abstract TPlugin CreatePlugin();

    [Fact]
    public void Name_IsNotNullOrEmpty()
    {
        var plugin = CreatePlugin();
        Assert.False(string.IsNullOrWhiteSpace(plugin.Name));
    }

    [Fact]
    public async Task ComputeAsync_WithEmptyList_DoesNotThrow()
    {
        var plugin = CreatePlugin();
        // 行为良好的插件应该能优雅地处理空输入
        var result = await plugin.ComputeAsync(new List<DataPoint>());
        Assert.NotNull(result);
    }

    [Fact]
    public async Task ComputeAsync_WithSinglePoint_ReturnsResult()
    {
        var plugin = CreatePlugin();
        var data = new List<DataPoint> { new(42.0) };
        var result = await plugin.ComputeAsync(data);
        Assert.NotNull(result);
    }
}

// AverageAnalyticsPlugin 的具体测试类
public class AverageAnalyticsPluginContractTests
    : PluginContractTests<AverageAnalyticsPlugin>
{
    protected override AverageAnalyticsPlugin CreatePlugin()
        => new AverageAnalyticsPlugin();
}
```

xUnit 会自动通过每个具体子类运行基类中定义的所有测试。新增插件时，只需要新建一个继承基类的测试类，所有契约不变量就自动覆盖了，完全不需要重复测试逻辑。

这个模式随着插件数量增长能保持很好的扩展性——到了二十个插件，省下的是几百行重复测试代码，同时契约覆盖率丝毫不打折。

## 测试插件发现逻辑

插件发现是藏匿细微 bug 最多的地方。宿主扫描目录、加载程序集、反射类型、筛选实现契约的对象。如果直接面向真实文件系统测试，速度慢、脆、还得在测试旁边附带 DLL 文件。

更好的做法：用接口把文件系统操作抽象出来，然后注入测试替代。

```csharp
// 对文件系统操作的抽象
public interface IPluginDirectory
{
    IEnumerable<string> GetAssemblyPaths();
}

// 发现逻辑依赖接口，而不是直接依赖文件系统
public class PluginDiscovery
{
    private readonly IPluginDirectory _directory;

    public PluginDiscovery(IPluginDirectory directory)
    {
        _directory = directory;
    }

    public IReadOnlyList<Type> DiscoverPluginTypes()
    {
        var results = new List<Type>();

        foreach (var path in _directory.GetAssemblyPaths())
        {
            try
            {
                var assembly = Assembly.LoadFrom(path);
                var pluginTypes = assembly.GetExportedTypes()
                    .Where(t => typeof(IAnalyticsPlugin).IsAssignableFrom(t)
                             && t is { IsAbstract: false, IsInterface: false });
                results.AddRange(pluginTypes);
            }
            catch (Exception)
            {
                // 跳过有问题的 DLL，不让宿主崩溃
            }
        }

        return results;
    }
}
```

测试中直接提供 fake 目录，不需要任何真实 DLL：

```csharp
public class FakePluginDirectory : IPluginDirectory
{
    private readonly List<string> _paths;

    public FakePluginDirectory(params string[] paths)
        => _paths = new List<string>(paths);

    public IEnumerable<string> GetAssemblyPaths() => _paths;
}

public class PluginDiscoveryTests
{
    [Fact]
    public void DiscoverPluginTypes_WithEmptyDirectory_ReturnsEmpty()
    {
        var discovery = new PluginDiscovery(new FakePluginDirectory());
        var types = discovery.DiscoverPluginTypes();
        Assert.Empty(types);
    }

    [Fact]
    public void DiscoverPluginTypes_WithInvalidPath_DoesNotThrow()
    {
        // 不存在的路径应该被吞掉，而不是抛出异常
        var discovery = new PluginDiscovery(
            new FakePluginDirectory(@"C:\nonexistent\fake.dll"));

        var types = discovery.DiscoverPluginTypes();
        Assert.Empty(types);
    }
}
```

这种方式让发现测试快速且确定性强。真实的 `FileSystemPluginDirectory` 实现只需要一两个针对已知临时目录的集成测试——发现逻辑的主体靠 fake 就能廉价覆盖。

## 集成测试：宿主加载真实插件

有时候你确实需要测试完整管道：加载程序集、发现类型、激活、执行。这时候集成测试才真正有价值。

在 .NET 中效果最好的方式是：把一个已知良好的测试插件编译到独立项目，复制到测试输出目录，然后在集成测试中用 `AssemblyLoadContext` 加载它。

在测试项目的 `.csproj` 里添加一个 `ProjectReference` 指向测试插件项目，设置 `ReferenceOutputAssembly=false` 并添加自定义 target 把 DLL 复制到输出目录。然后在测试中加载：

```csharp
public class PluginLoadingIntegrationTests
{
    [Fact]
    public async Task LoadPlugin_FromAssembly_ExecutesCorrectly()
    {
        var pluginPath = Path.Combine(
            AppContext.BaseDirectory, "TestPlugin.dll");

        Assert.True(File.Exists(pluginPath),
            "Test plugin DLL not found in output directory.");

        // 可回收的 context 让我们能在测试完成后卸载
        var context = new AssemblyLoadContext(
            name: "TestPluginContext",
            isCollectible: true);

        try
        {
            var assembly = context.LoadFromAssemblyPath(pluginPath);
            var pluginType = assembly.GetExportedTypes()
                .Single(t => typeof(IAnalyticsPlugin).IsAssignableFrom(t));

            var plugin = (IAnalyticsPlugin)Activator.CreateInstance(pluginType)!;

            var data = new List<DataPoint> { new(10.0), new(20.0) };
            var result = await plugin.ComputeAsync(data);

            Assert.Equal(15.0, result.Value, precision: 5);
        }
        finally
        {
            context.Unload();
        }
    }
}
```

使用可回收的 `AssemblyLoadContext` 可以在测试完成后发起卸载，减少测试间的相互污染。注意 `Unload()` 不保证立即回收——如果测试隔离要求严格，可以用 `WeakReference` 来验证 context 是否真正被 GC 回收。

## 测试插件失败场景

健壮的插件宿主必须在插件行为异常时保持稳定。明确测试失败场景，是区分脆弱系统和生产级系统的关键。

值得明确测试的三类失败：执行时抛异常、返回 null、初始化时抛异常：

```csharp
// 专门用于失败测试的"坏"插件
public class ThrowingPlugin : IAnalyticsPlugin
{
    public string Name => "Throwing";

    public Task<AnalyticsSummary> ComputeAsync(IReadOnlyList<DataPoint> data)
        => throw new InvalidOperationException("Simulated plugin failure.");
}

public class NullReturningPlugin : IAnalyticsPlugin
{
    public string Name => "NullReturning";

    public Task<AnalyticsSummary> ComputeAsync(IReadOnlyList<DataPoint> data)
        => Task.FromResult<AnalyticsSummary>(null!);
}

public class PluginHostFailureTests
{
    [Fact]
    public async Task Host_WhenPluginThrows_ContinuesWithOtherPlugins()
    {
        var host = new PluginHost(new IAnalyticsPlugin[]
        {
            new ThrowingPlugin(),
            new AverageAnalyticsPlugin()
        });

        var data = new List<DataPoint> { new(10.0), new(20.0) };

        // 宿主应返回正常插件的结果，跳过出错的插件
        var results = await host.RunAllAsync(data);

        Assert.Single(results);
        Assert.Equal("Average", results[0].PluginName);
    }

    [Fact]
    public async Task Host_WhenPluginReturnsNull_HandlesGracefully()
    {
        var host = new PluginHost(new IAnalyticsPlugin[]
        {
            new NullReturningPlugin()
        });

        var data = new List<DataPoint> { new(5.0) };

        // null 结果应该被过滤掉，而不是导致异常
        var results = await host.RunAllAsync(data);
        Assert.Empty(results);
    }
}
```

这些测试定义了宿主的预期韧性行为。在实现错误处理之前先写它们最有价值——它们用可执行的形式指定了"韧性"的具体含义。

## 测试插件版本兼容性

版本兼容性是插件架构中最棘手的测试挑战之一。契约程序集发布了新版本，旧插件（编译时依赖 v1.0）需要在 v1.1 宿主上继续工作——或者以明确的错误失败，而不是在运行时神秘地抛出 `MissingMethodException`。

实践层面，按契约版本划分独立测试项目：

```
tests/
├── PluginHost.UnitTests/
├── PluginHost.IntegrationTests/
├── PluginContracts.V1.Tests/           # 针对 v1 契约的测试
└── PluginContracts.V2.CompatTests/     # v1 插件在 v2 宿主上运行
```

在兼容性测试项目中，插件引用 v1 契约程序集，宿主引用 v2，测试验证宿主在缺少新成员时能优雅降级：

```csharp
[Fact]
public async Task HostV2_LoadsV1Plugin_DoesNotThrowOnOptionalNewMethod()
{
    // 模拟基于 v1 编译的插件——它不实现新的可选方法
    IAnalyticsPlugin plugin = new LegacyV1AnalyticsPlugin();

    var host = new PluginHostV2(new[] { plugin });
    var data = new List<DataPoint> { new(5.0) };

    // v2 宿主应该在调用新方法前先检查能力，绝不能崩溃
    var result = await host.RunWithOptionalEnrichmentAsync(data);

    Assert.NotNull(result);
}
```

核心设计原则：宿主调用可选契约方法之前，必须先检查是否存在——通过增量接口版本或显式能力检查。这类边界测试是在演进契约时捕获回归的最快手段。

## 完整测试套件结构

把上面所有层次组合在一起，一个结构良好的 .NET 插件测试套件大致如下：

```
PluginSystem.sln
├── src/
│   ├── PluginContracts/               # IAnalyticsPlugin、数据类型
│   ├── PluginHost/                    # 发现、加载、执行
│   └── Plugins/
│       └── AveragePlugin/             # 具体插件（独立分发）
├── tests/
│   ├── PluginHost.UnitTests/          # 发现测试、失败场景测试
│   ├── PluginHost.IntegrationTests/   # 端到端加载+执行测试
│   └── PluginContracts.ContractTests/ # 抽象基类+每个插件一个具体类
└── testplugins/
    └── TestAveragePlugin/             # 编译到集成测试输出目录
```

每一层职责清晰明确：

- `PluginHost.UnitTests`：无文件系统访问、无 DLL 加载，毫秒级运行
- `PluginContracts.ContractTests`：跨所有具体插件验证契约不变量
- `PluginHost.IntegrationTests`：加载真实程序集，验证端到端行为

每次提交运行单元测试，集成测试放在 CI 中运行。这种拆分让本地开发循环保持轻快，同时不放弃对加载和激活 bug 的完整覆盖。

## 常见问题

**是否应该用 Moq 等 mock 框架测试插件架构？**

Moq 适合测试宿主的错误处理逻辑，这种场景需要受控的插件桩。对于插件本身，优先用具体的测试实现——更简单，也更接近真实运行时行为。不要在契约测试中 mock `IAnalyticsPlugin`，因为契约测试的全部意义就在于对真实实现运行。

**插件依赖文件系统或网络时怎么测？**

用和发现测试相同的接口提取模式，抽象出 `IFileReader` 或 `IHttpClient`，注入到插件构造函数，在测试中提供 fake。如果插件接受无类型的 `IServiceProvider`，在测试中构建一个最小化的真实 DI 容器，比 mock 更不脆、也更接近实际解析路径。

**不创建真实 DLL 能测试插件加载吗？**

对于发现逻辑的单元测试，可以——用上面示例的 `IPluginDirectory` 接口返回 fake 路径，完全不接触磁盘。对于验证 `AssemblyLoadContext` 行为的测试，你确实需要真实程序集，最干净的方式是一个专用的测试插件项目，通过 `.csproj` 的 `ProjectReference` 自动编译到测试输出目录。

## 总结

测试插件架构需要分层思考。插件实现只是普通类，照常测试。契约需要抽象测试基类，跨所有实现强制不变量、不重复代码。发现逻辑需要接口提取，让测试不触碰文件系统。完整的加载-发现-执行流程需要少量精心构造的集成测试，借助 `AssemblyLoadContext` 进行。

最关键的一步是尽早把快速单元测试和慢速集成测试分开。这种拆分让开发循环保持干净，也保证集成测试真正会被执行——在 CI、在每个 PR，在它们能捕获真实问题的地方。

投入到插件架构测试中的，不只是覆盖率：你得到的是系统行为的活文档。契约测试记录接口不变量，集成测试记录加载场景，失败测试记录韧性预期。

## 参考

- [Testing Plugin Architectures in C#: Strategies for Extensible Systems](https://www.devleader.ca/2026/04/11/testing-plugin-architectures-in-c-strategies-for-extensible-systems)
- [Plugin Architecture Design Pattern -- A Beginner's Guide to Modularity](https://www.devleader.ca/2023/09/07/plugin-architecture-design-pattern-a-beginners-guide-to-modularity)
- [Plugin Architecture in C# for Improved Software Design](https://www.devleader.ca/2024/03/12/plugin-architecture-in-c-for-improved-software-design)
- [Plugin Architecture in ASP.NET Core -- How To Master It](https://www.devleader.ca/2023/07/31/plugin-architecture-in-aspnet-core-how-to-master-it)
- [Plugin Architecture with Needlr in .NET: Building Modular Applications](https://www.devleader.ca/2026/02/15/plugin-architecture-with-needlr-in-net-building-modular-applications)
