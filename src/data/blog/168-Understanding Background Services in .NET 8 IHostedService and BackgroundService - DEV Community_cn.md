---
pubDatetime: 2024-07-18
tags: [".NET", "Architecture"]
source: https://dev.to/moh_moh701/understanding-background-services-in-net-8-ihostedservice-and-backgroundservice-2eoh
author: mohamed Tayel
title: Understanding Background Services in .NET 8 IHostedService and BackgroundService - DEV Community
description: .NET 8 introduces powerful features for managing background tasks with IHostedService and...
---

# 理解.NET 8中的后台服务：IHostedService和BackgroundService - DEV社区

> ## 摘要
>
> .NET 8引入了强大的功能，用于通过IHostedService和...

---

.NET 8引入了强大的功能，用于通过`IHostedService`和`BackgroundService`管理后台任务。这些服务使得长时间运行的操作（如定时任务、后台处理和周期性维护任务）能够无缝集成到你的应用程序中。本文探讨了这些新功能，并提供了实际示例帮助你快速入门。你可以在我的[GitHub 仓库](https://github.com/mohamedtayel1980/DotNet8NewFeature/tree/main/DotNet8NewFeature/BackgroundingService)找到这些示例的源代码。

#### 什么是后台服务？

.NET中的后台服务允许你在独立于主应用程序线程的情况下运行任务。这对于那些需要持续运行或定期运行但不阻塞主应用程序流程的任务非常重要。

#### `IHostedService`接口

`IHostedService`接口定义了两个方法：

- **`StartAsync(CancellationToken cancellationToken)`**：在应用程序主机启动时调用。
- **`StopAsync(CancellationToken cancellationToken)`**：在应用程序主机执行优雅关闭时调用。

**`IHostedService`实现示例**:

```csharp
using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

public class TimedHostedService : IHostedService, IDisposable
{
    private readonly ILogger<TimedHostedService> _logger;
    private Timer _timer;

    public TimedHostedService(ILogger<TimedHostedService> logger)
    {
        _logger = logger;
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Timed Hosted Service running.");

        _timer = new Timer(DoWork, null, TimeSpan.Zero, TimeSpan.FromSeconds(5));

        return Task.CompletedTask;
    }

    private void DoWork(object state)
    {
        _logger.LogInformation("Timed Hosted Service is working.");
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Timed Hosted Service is stopping.");

        _timer?.Change(Timeout.Infinite, 0);

        return Task.CompletedTask;
    }

    public void Dispose()
    {
        _timer?.Dispose();
    }
}
```

#### `BackgroundService`类

`BackgroundService`类是一个抽象基类，简化了后台任务的实现。它提供了单个方法供重写：

- **`ExecuteAsync(CancellationToken stoppingToken)`**：包含后台任务的逻辑，并在应用程序关闭前持续运行。

**`BackgroundService`实现示例**:

```csharp
using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

public class TimedBackgroundService : BackgroundService
{
    private readonly ILogger<TimedBackgroundService> _logger;

    public TimedBackgroundService(ILogger<TimedBackgroundService> logger)
    {
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Timed Background Service running.");

        while (!stoppingToken.IsCancellationRequested)
        {
            _logger.LogInformation("Timed Background Service is working.");
            await Task.Delay(TimeSpan.FromSeconds(5), stoppingToken);
        }

        _logger.LogInformation("Timed Background Service is stopping.");
    }
}
```

#### 实际应用

要在你的.NET应用程序中利用这些后台服务，你需要在依赖注入容器中注册它们。这可以在`Program.cs`文件中完成。

**注册托管服务**：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System.Threading.Tasks;

public class Program
{
    public static async Task Main(string[] args)
    {
        var host = Host.CreateDefaultBuilder(args)
            .ConfigureServices(services =>
            {
                services.AddHostedService<TimedHostedService>();
                services.AddHostedService<TimedBackgroundService>();
            })
            .Build();

        await host.RunAsync();
    }
}
```

### 主要区别

- **抽象级别**：

  - **`IHostedService`**：需要手动实现启动和停止逻辑。
  - **`BackgroundService`**：通过提供一个基类并重写单个方法简化了实现。

- **使用场景**：

  - **`IHostedService`**：适用于需要对服务生命周期进行细粒度控制的复杂场景。
  - **`BackgroundService`**：适用于较简单的长时间运行任务，减少了样板代码。

### 结论

.NET 8的后台服务通过`IHostedService`和`BackgroundService`提供了一种强大且灵活的管理后台任务的方法。通过根据需求选择合适的抽象层，你可以高效地在你的应用程序中实现和管理长时间运行的操作。这些新特性增强了创建响应性、可扩展和可维护的.NET应用程序的能力。
