---
pubDatetime: 2026-04-11T14:40:00+08:00
title: "C# 插件生命周期管理：加载、激活与卸载"
description: "用 .NET 8/9 的 AssemblyLoadContext 构建稳健插件系统，完整覆盖发现、初始化、激活、热重载和优雅关闭五个阶段，附可直接落地的代码模式和常见坑点说明。"
tags: ["CSharp", "Plugin", "DotNet", "Architecture"]
slug: "plugin-lifecycle-management-csharp-loading-activation-unloading"
ogImage: "../../assets/724/01-cover.jpg"
source: "https://www.devleader.ca/2026/04/10/plugin-lifecycle-management-in-c-loading-activation-and-unloading"
---

![C# 插件生命周期管理封面](../../assets/724/01-cover.jpg)

在 C# 里构建插件系统，很多人最开始只想到一件事：调用 `Assembly.LoadFrom` 加载 DLL。但插件生命周期管理要处理的远不止这一步。你需要知道什么时候去发现插件、怎么把它们初始化好、何时激活、以及怎么在不重启宿主的情况下把旧版本换掉。每一个环节做错了，代价都不一样——内存泄漏、启动失败、宿主崩溃。

这篇文章会带你走完四个生命周期阶段，配合可以直接放进项目的 .NET 8/9 代码。如果你还没有接触过插件架构的基本概念，可以先看 [Plugin Architecture in C# for Improved Software Design](https://www.devleader.ca/2024/03/12/plugin-architecture-in-c-for-improved-software-design) 建立背景知识。

## 什么是插件生命周期管理

插件生命周期管理就是把一个插件从无到有、从运行到退出的全过程控制起来，分四个阶段：

- **发现（Discovery）**：从磁盘或配置里找到插件程序集
- **加载（Loading）**：通过 `AssemblyLoadContext` 把程序集加载进内存
- **激活（Activation）**：启动插件，让它开始工作
- **停用 / 卸载（Deactivation / Unloading）**：干净地停止插件并释放内存

作者用了一个简洁的比喻：插座一直在（发现），设备插上（加载），翻开关（激活），用完拔掉（卸载）。跳过任何一步，要么浪费资源，要么内存泄漏，要么在最不想崩的时候崩。

为什么要把这几件事做清楚？

- **资源清理**：插件会打开文件句柄、数据库连接、启定时器、起后台线程。没有正确的关闭路径，这些都会泄漏。
- **热重载**：要在不重启宿主的情况下换一个正在运行的插件，必须在加载新版本之前把旧 `AssemblyLoadContext` 有序卸掉。
- **错误隔离**：插件初始化里的 bug 不应该把宿主拖垮。生命周期管理给了你捕获和隔离这些失败的接缝。

## 插件发现：启动时找到可用插件

加载任何东西之前，你得先知道有哪些插件存在。常见三种方式：

- **文件夹扫描**：扫描 `plugins/` 目录里符合命名规范的 DLL。简单、零配置。
- **配置驱动**：在 `appsettings.json` 里显式列出程序集路径。给运维人员精细控制权。
- **命名约定**：只加载匹配 `*.Plugin.dll` 之类规则的文件，避免把同目录下的依赖 DLL 也加载进来。

下面的类把三种方式都包进去了，配置优先，没有配置则回落到文件夹扫描：

```csharp
public sealed class PluginDiscovery
{
    private readonly string _pluginDirectory;
    private readonly IReadOnlyList<string>? _explicitPaths;
    private readonly string _searchPattern;

    public PluginDiscovery(
        string pluginDirectory = "plugins",
        IReadOnlyList<string>? explicitPaths = null,
        string searchPattern = "*.Plugin.dll")
    {
        _pluginDirectory = pluginDirectory;
        _explicitPaths = explicitPaths;
        _searchPattern = searchPattern;
    }

    public IEnumerable<string> Discover()
    {
        // Config-based wins when explicit paths are provided
        if (_explicitPaths is { Count: > 0 })
            return _explicitPaths.Where(File.Exists);

        if (!Directory.Exists(_pluginDirectory))
            return Enumerable.Empty<string>();

        return Directory.GetFiles(_pluginDirectory, _searchPattern, SearchOption.AllDirectories);
    }
}
```

把发现和加载分开，两个步骤都可以独立测试。在容器环境里，还可以扩展发现逻辑来支持远程插件清单——从注册服务获取程序集位置，而不是扫本地文件系统。

## 用 IPluginLifecycle 定义初始化契约

每个插件需要一种方式告诉宿主「我准备好了」和「我结束了」。一个共享接口是最干净的契约：

```csharp
public interface IPluginLifecycle
{
    string PluginId { get; }
    string DisplayName { get; }

    Task InitializeAsync(IServiceProvider hostServices, CancellationToken cancellationToken = default);
    Task ShutdownAsync(CancellationToken cancellationToken = default);
}
```

`InitializeAsync` 接收宿主的 `IServiceProvider`，插件可以从中获取共享服务（日志、配置等），宿主不需要知道每个插件具体要什么。异步初始化很重要，因为真实插件在这里会做真实的工作——打开数据库连接、启动文件监听、注册后台定时器。

下面是一个邮件通知插件的样例，演示了异步初始化的写法：

```csharp
public sealed class EmailNotificationPlugin : IPluginLifecycle
{
    private ILogger<EmailNotificationPlugin>? _logger;
    private SmtpClient? _smtpClient;

    public string PluginId => "notifications.email";
    public string DisplayName => "Email Notification Channel";

    public async Task InitializeAsync(
        IServiceProvider hostServices,
        CancellationToken cancellationToken = default)
    {
        _logger = hostServices.GetRequiredService<ILogger<EmailNotificationPlugin>>();
        var config = hostServices.GetRequiredService<IConfiguration>();

        _smtpClient = new SmtpClient(config["Smtp:Host"])
        {
            Port = int.Parse(config["Smtp:Port"] ?? "587"),
            EnableSsl = true
        };

        // Verify connectivity before reporting ready
        await _smtpClient.SendMailAsync(
            new MailMessage("health@example.com", "health@example.com", "ping", "ping"),
            cancellationToken);

        _logger.LogInformation("Email plugin initialized");
    }

    public Task ShutdownAsync(CancellationToken cancellationToken = default)
    {
        _smtpClient?.Dispose();
        _logger?.LogInformation("Email plugin shut down");
        return Task.CompletedTask;
    }
}
```

注意插件自己管理自己的资源生命周期。宿主完全不需要知道 SMTP 的存在。

## 激活与 PluginHost：把加载和激活分开

把插件加载进内存和激活它是两回事。你可能会在启动时加载所有插件，但只根据配置或用户操作激活其中的一部分。

`PluginHost<TContract>` 把已加载的插件和激活的插件分开管理，支持在运行时启用或禁用单个插件，而不需要卸载程序集：

```csharp
public sealed class PluginHost<TContract> where TContract : IPluginLifecycle
{
    private readonly ILogger<PluginHost<TContract>> _logger;
    private readonly Dictionary<string, TContract> _loaded = new();
    private readonly HashSet<string> _active = new();

    public PluginHost(ILogger<PluginHost<TContract>> logger)
    {
        _logger = logger;
    }

    public void Register(TContract plugin)
    {
        _loaded[plugin.PluginId] = plugin;
        _logger.LogDebug("Registered plugin {PluginId}", plugin.PluginId);
    }

    public async Task ActivateAsync(
        string pluginId,
        IServiceProvider services,
        CancellationToken ct = default)
    {
        if (!_loaded.TryGetValue(pluginId, out var plugin))
            throw new KeyNotFoundException($"Plugin '{pluginId}' is not registered.");

        if (_active.Contains(pluginId))
        {
            _logger.LogWarning("Plugin {PluginId} is already active", pluginId);
            return;
        }

        await plugin.InitializeAsync(services, ct);
        _active.Add(pluginId);
        _logger.LogInformation("Activated plugin {PluginId}", pluginId);
    }

    public async Task DeactivateAsync(string pluginId, CancellationToken ct = default)
    {
        if (!_active.Remove(pluginId)) return;

        if (_loaded.TryGetValue(pluginId, out var plugin))
        {
            await plugin.ShutdownAsync(ct);
            _logger.LogInformation("Deactivated plugin {PluginId}", pluginId);
        }
    }

    public IEnumerable<TContract> ActivePlugins =>
        _active.Select(id => _loaded[id]);
}
```

这个设计让激活变成运行时的开关。可以通过管理 API 或配置 Flag 控制，不涉及任何程序集的加载和卸载。

## 错误隔离：防止插件故障拖垮宿主

插件代码在你的进程里运行。任何插件里的未处理异常都会向上传播到宿主，除非你显式拦截。最简单也最有效的模式是一个安全调用包装器：

```csharp
public static class PluginInvoker
{
    public static async Task InvokeSafelyAsync(
        IPluginLifecycle plugin,
        Func<Task> action,
        ILogger logger)
    {
        try
        {
            await action();
        }
        catch (OperationCanceledException)
        {
            // Propagate cancellation -- this is expected behavior
            throw;
        }
        catch (Exception ex)
        {
            logger.LogError(
                ex,
                "Plugin {PluginId} threw an unhandled exception and has been isolated",
                plugin.PluginId);
            // Do NOT rethrow -- isolate this plugin's failure from the host
        }
    }
}
```

任何从宿主调用插件方法的地方都要用这个。对于更严格的场景，可以在上面叠加熔断器：追踪每个插件的连续失败次数，超过阈值后自动停用。

在向所有活跃插件广播事件时，要给每次调用单独隔离：

```csharp
foreach (var plugin in host.ActivePlugins)
{
    await PluginInvoker.InvokeSafelyAsync(
        plugin,
        () => plugin.SendAsync(notification),
        logger);
}
```

这样一个坏掉的 SMS 插件不会阻止 Email 和 Slack 插件继续投递。

把插件生命周期想象成一个状态机有助于设计错误隔离：每个插件从 discovered → loaded → initialized → active → deactivating → unloaded 这几个状态转换。用一个枚举显式建模这些转换，既方便验证（比如不允许在初始化前激活），也方便测试。

## 热重载：不重启宿主换掉插件

热重载的意思是在运行时替换插件的代码，不停宿主应用。.NET 通过 `AssemblyLoadContext` 实现这个能力：为新 DLL 创建一个新 context，对旧 context 调用 `Unload()` 触发回收，然后重新注册新的插件实例。

要注意：`Unload()` 并不会立即释放内存，它只是发起回收请求，GC 必须能够回收这个 context。任何还持有插件类型强引用的东西（缓存的委托、静态字段、静态事件处理器）都会阻止卸载。

`PluginHotReloadManager` 监视插件目录，在 DLL 变化时触发重载：

```csharp
public sealed class PluginHotReloadManager : IAsyncDisposable
{
    private readonly string _pluginDirectory;
    private readonly IServiceProvider _services;
    private readonly ILogger<PluginHotReloadManager> _logger;
    private readonly FileSystemWatcher _watcher;
    private readonly Dictionary<string, (AssemblyLoadContext Context, IPluginLifecycle Plugin)> _contexts = new();

    public PluginHotReloadManager(
        string pluginDirectory,
        IServiceProvider services,
        ILogger<PluginHotReloadManager> logger)
    {
        _pluginDirectory = pluginDirectory;
        _services = services;
        _logger = logger;

        _watcher = new FileSystemWatcher(pluginDirectory, "*.Plugin.dll")
        {
            NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.FileName,
            EnableRaisingEvents = true
        };

        _watcher.Changed += OnPluginFileChanged;
        _watcher.Created += OnPluginFileChanged;
    }

    private void OnPluginFileChanged(object sender, FileSystemEventArgs e)
    {
        // Offload to thread pool -- FileSystemWatcher callbacks must not block
        _ = Task.Run(() => ReloadPluginAsync(e.FullPath));
    }

    private async Task ReloadPluginAsync(string dllPath)
    {
        // Small delay to let the file write complete
        await Task.Delay(500);

        _logger.LogInformation("Hot-reloading plugin from {Path}", dllPath);

        var pluginId = Path.GetFileNameWithoutExtension(dllPath);

        // Shutdown and unload the old context if it exists
        if (_contexts.TryGetValue(pluginId, out var existing))
        {
            await existing.Plugin.ShutdownAsync();
            existing.Context.Unload();
            _contexts.Remove(pluginId);
            _logger.LogInformation("Unloaded old context for {PluginId}", pluginId);
        }

        // Load the new assembly in a fresh, collectible context
        var context = new AssemblyLoadContext(pluginId, isCollectible: true);
        var assembly = context.LoadFromAssemblyPath(dllPath);

        var pluginType = assembly.GetTypes()
            .FirstOrDefault(t => typeof(IPluginLifecycle).IsAssignableFrom(t) && !t.IsAbstract);

        if (pluginType is null)
        {
            _logger.LogWarning("No IPluginLifecycle implementation found in {Path}", dllPath);
            context.Unload();
            return;
        }

        var plugin = (IPluginLifecycle)Activator.CreateInstance(pluginType)!;
        await plugin.InitializeAsync(_services);

        _contexts[pluginId] = (context, plugin);
        _logger.LogInformation("Hot-reloaded plugin {PluginId}", pluginId);
    }

    public async ValueTask DisposeAsync()
    {
        _watcher.EnableRaisingEvents = false;
        _watcher.Dispose();

        foreach (var (id, entry) in _contexts)
        {
            await entry.Plugin.ShutdownAsync();
            entry.Context.Unload();
            _logger.LogInformation("Unloaded plugin context {PluginId} on dispose", id);
        }

        _contexts.Clear();
    }
}
```

热重载有几个重要限制要了解：

- **卸载不保证立即发生**：`context.Unload()` 发起回收，GC 必须能实际回收。静态事件处理器、后台线程、定时器、缓存的 `Type` 引用、静态单例都会阻止卸载。开发阶段可以用 `WeakReference` 验证是否真正卸载了。
- **进行中的请求**：旧实例上已经开始的调用在卸载前需要完成。实践中要么设静默期，要么用引用计数包装器延迟卸载。
- **文件锁**：替换的 DLL 可能仍被上一次写入锁定，500ms 的延迟是个粗糙的经验值，生产环境应该加上带退避的重试逻辑。
- **状态迁移**：旧插件的内存状态（队列、缓存）在新版启动时是空的。设计插件时尽量做成无状态，或从外部数据源重新加载状态。
- **共享类型**：宿主契约（`IPluginLifecycle`）必须放在一个独立的 Contracts 程序集里，宿主和所有插件的 load context 都从同一处加载。

## 优雅关闭：用 IHostedService 管理插件生命周期

宿主应用的关闭也是一个生命周期事件，需要显式处理。在 ASP.NET Core 里最干净的做法是实现 `IHostedService`，这样你就能拿到正确的 `StopAsync` 回调：

```csharp
public sealed class PluginLifecycleService : IHostedService
{
    private readonly PluginHost<IPluginLifecycle> _host;
    private readonly IServiceProvider _services;
    private readonly ILogger<PluginLifecycleService> _logger;

    public PluginLifecycleService(
        PluginHost<IPluginLifecycle> host,
        IServiceProvider services,
        ILogger<PluginLifecycleService> logger)
    {
        _host = host;
        _services = services;
        _logger = logger;
    }

    public async Task StartAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Starting plugin lifecycle service");

        var discovery = new PluginDiscovery(pluginDirectory: "plugins");

        foreach (var dllPath in discovery.Discover())
        {
            var context = new AssemblyLoadContext(
                Path.GetFileNameWithoutExtension(dllPath), isCollectible: true);
            var assembly = context.LoadFromAssemblyPath(dllPath);

            foreach (var type in assembly.GetTypes()
                .Where(t => typeof(IPluginLifecycle).IsAssignableFrom(t) && !t.IsAbstract))
            {
                var plugin = (IPluginLifecycle)Activator.CreateInstance(type)!;
                _host.Register(plugin);
                await _host.ActivateAsync(plugin.PluginId, _services, cancellationToken);
            }
        }
    }

    public async Task StopAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Stopping all plugins");

        foreach (var plugin in _host.ActivePlugins.ToList())
        {
            await _host.DeactivateAsync(plugin.PluginId, cancellationToken);
        }
    }
}
```

在 `Program.cs` 里注册：

```csharp
builder.Services.AddSingleton<PluginHost<IPluginLifecycle>>();
builder.Services.AddHostedService<PluginLifecycleService>();
```

.NET 的 generic host 保证在进程退出前按注册的逆序调用所有 hosted service 的 `StopAsync`，这正是有序停用插件时想要的顺序。

## 完整示例：通知系统

把上面的模式组合到一个具体场景里：一个可插拔通知系统，支持 Email、Slack、SMS 三种投递渠道，每个渠道是一个插件。

```csharp
// 共享契约 -- 放在独立的 Contracts 项目里
public interface INotificationPlugin : IPluginLifecycle
{
    Task SendNotificationAsync(string recipient, string message, CancellationToken ct = default);
}

// 通知服务 -- 不知道任何具体渠道的细节
public sealed class NotificationService
{
    private readonly PluginHost<INotificationPlugin> _host;
    private readonly ILogger<NotificationService> _logger;

    public NotificationService(
        PluginHost<INotificationPlugin> host,
        ILogger<NotificationService> logger)
    {
        _host = host;
        _logger = logger;
    }

    public async Task BroadcastAsync(string recipient, string message, CancellationToken ct = default)
    {
        var tasks = _host.ActivePlugins.Select(plugin =>
            PluginInvoker.InvokeSafelyAsync(
                plugin,
                () => plugin.SendNotificationAsync(recipient, message, ct),
                _logger));

        await Task.WhenAll(tasks);
    }
}

// Slack 插件实现
public sealed class SlackNotificationPlugin : INotificationPlugin
{
    private ILogger<SlackNotificationPlugin>? _logger;
    private HttpClient? _httpClient;
    private string? _webhookUrl;

    public string PluginId => "notifications.slack";
    public string DisplayName => "Slack Notification Channel";

    public async Task InitializeAsync(IServiceProvider services, CancellationToken ct = default)
    {
        _logger = services.GetRequiredService<ILogger<SlackNotificationPlugin>>();
        var config = services.GetRequiredService<IConfiguration>();
        _webhookUrl = config["Slack:WebhookUrl"]
            ?? throw new InvalidOperationException("Slack:WebhookUrl is required");

        _httpClient = services.GetRequiredService<IHttpClientFactory>().CreateClient("slack");
        _logger.LogInformation("Slack plugin initialized");
        await Task.CompletedTask;
    }

    public Task ShutdownAsync(CancellationToken ct = default)
    {
        _httpClient?.Dispose();
        return Task.CompletedTask;
    }

    public async Task SendNotificationAsync(string recipient, string message, CancellationToken ct = default)
    {
        var payload = JsonSerializer.Serialize(new { text = $"@{recipient}: {message}" });
        using var content = new StringContent(payload, Encoding.UTF8, "application/json");
        var response = await _httpClient!.PostAsync(_webhookUrl, content, ct);
        response.EnsureSuccessStatusCode();
    }
}
```

`Program.cs` 里的注册：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHttpClient("slack");
builder.Services.AddSingleton<PluginHost<INotificationPlugin>>();
builder.Services.AddSingleton<NotificationService>();
builder.Services.AddHostedService<PluginLifecycleService<INotificationPlugin>>();

var app = builder.Build();

app.MapPost("/notify", async (NotificationService svc, NotificationRequest req) =>
{
    await svc.BroadcastAsync(req.Recipient, req.Message);
    return Results.Ok();
});

app.Run();
```

这个架构下，新增一个投递渠道只需要把一个新的 `.Plugin.dll` 丢进 plugins 文件夹重启（或者结合前面的热重载管理器，连重启都不用）。

## 常见问题

**ASP.NET Core 里应该用 IHostedService 管理插件生命周期吗？**

推荐这样做。`IHostedService` 给你 `StartAsync` 和 `StopAsync` 钩子，和 generic host 的启动/关闭序列干净地集成。不要把插件初始化直接放进 `Program.cs` 的启动代码，那样会失去优雅关闭的保证。

**插件之间怎么传递数据？**

最干净的方式是用宿主的 `IServiceProvider` 作为消息总线。在宿主的 DI 容器里注册一个共享服务（如 `IEventBus`），注入到每个插件的 `InitializeAsync` 里。插件之间不直接通信，通过共享服务发布和订阅。这样能避免插件 A 持有插件 B 程序集类型的引用。

**生产环境里怎样不停机更新插件？**

最安全的模式是版本化交换：把新版本加载进新的 `AssemblyLoadContext`，同时运行新旧两个版本，短暂静默期内把新请求路由到新版本，等旧版本跑完进行中的工作后再卸载旧 context。对大多数应用来说，一个简单的「停—换—启」加短暂维护窗口就够用了，也更好理解。

**插件慢到初始化超时怎么处理？**

把带超时的 `CancellationToken` 传进 `InitializeAsync`。可以用 `CancellationTokenSource.CancelAfter(TimeSpan.FromSeconds(30))` 给每个插件单独设超时。如果抛了 `OperationCanceledException`，记录失败、标记该插件为未激活，继续加载其他插件。把每个插件的超时放进 `appsettings.json`，这样运维人员可以调，不用改代码。

## 小结

插件生命周期管理在 C# 里看起来简单——「就是加载个 DLL 而已」——直到你遇到第一个内存泄漏、第一次热重载失败、第一次插件未处理异常把宿主带崩。这篇文章覆盖的模式给了你处理这些情况的基础构件：

- **发现**：`PluginDiscovery`，文件夹扫描加配置回落
- **初始化**：`IPluginLifecycle`，异步 init 和 shutdown
- **激活**：`PluginHost<TContract>`，已加载和已激活分开管理
- **错误隔离**：每个调用点都用 `PluginInvoker.InvokeSafelyAsync`
- **热重载**：`PluginHotReloadManager`，`AssemblyLoadContext` + `FileSystemWatcher`
- **关闭**：`IHostedService` 提供 `StopAsync` 保证

从 `IPluginLifecycle` 和 `PluginHost` 开始，按需累加其他层。

## 参考

- [原文：Plugin Lifecycle Management in C#: Loading, Activation, and Unloading](https://www.devleader.ca/2026/04/10/plugin-lifecycle-management-in-c-loading-activation-and-unloading)
- [Plugin Architecture in C# for Improved Software Design](https://www.devleader.ca/2024/03/12/plugin-architecture-in-c-for-improved-software-design)
- [Plugin Architecture Design Pattern — A Beginner's Guide to Modularity](https://www.devleader.ca/2023/09/07/plugin-architecture-design-pattern-a-beginners-guide-to-modularity)
- [Plugin Architecture in ASP.NET Core — How To Master It](https://www.devleader.ca/2023/07/31/plugin-architecture-in-aspnet-core-how-to-master-it)
