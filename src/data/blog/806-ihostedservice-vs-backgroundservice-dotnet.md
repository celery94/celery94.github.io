---
pubDatetime: 2026-05-19T07:21:16+08:00
title: "IHostedService vs BackgroundService：.NET 10 后台任务选哪个"
description: "BackgroundService 覆盖 .NET 后台任务 99% 的场景，但有 5 个生产坑会让你在凌晨 3 点接到警报。本文对比两种抽象的核心差异，逐一拆解常见陷阱，并附决策矩阵帮你判断何时该升级到 Hangfire 或 Quartz.NET。"
tags: ["dotnet", "BackgroundService", "IHostedService", "ASP.NET Core"]
slug: "ihostedservice-vs-backgroundservice-dotnet"
ogImage: "../../assets/806/01-cover.png"
source: "https://codewithmukesh.com/blog/ihostedservice-vs-backgroundservice-dotnet/"
---

![IHostedService vs BackgroundService 决策封面](../../assets/806/01-cover.png)

**短结论**：99% 的后台循环任务用 `BackgroundService`；只有一次性启动或关闭任务才直接实现 `IHostedService`；需要持久化、重试、调度或仪表盘时，跳过两者，直接用 Hangfire 或 Quartz.NET。

原文作者在 50+ 个 .NET API 项目中积累了这套判断。这篇文章跟着他走一遍两种抽象的差异、同一任务的对比写法、以及 5 个在 .NET 6 到 .NET 10 真实踩过的生产坑，最后给出一张决策矩阵。

## IHostedService 是什么

`IHostedService` 是 .NET 的底层接口，定义了两个方法：

```csharp
namespace Microsoft.Extensions.Hosting;

public interface IHostedService
{
    Task StartAsync(CancellationToken cancellationToken);
    Task StopAsync(CancellationToken cancellationToken);
}
```

就这两个方法，从 .NET Core 2.0 发布至今接口契约没变过。凡是通过 `services.AddHostedService<T>()` 注册的类型，Host 都会在启动时调用 `StartAsync`，在关闭时调用 `StopAsync`。

**Host 会等 `StartAsync` 完成后才开始接受请求**，等 `StopAsync` 完成后才退出进程（默认超时 5 秒，可通过 `HostOptions.ShutdownTimeout` 调整）。这让 `IHostedService` 非常适合做真正的启动任务：迁移数据库 schema、向服务注册中心注册、预热 HTTP 客户端连接池。但它不适合开一个后台循环，因为 Host 会真的等着你。

## BackgroundService 是什么

`BackgroundService` 是 .NET Core 2.1 引入的抽象基类，它实现了 `IHostedService`，封装了持续运行的后台任务所需的全部生命周期逻辑。你只需要继承它并重写一个方法：

```csharp
public sealed class HeartbeatService(ILogger<HeartbeatService> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            logger.LogInformation("Heartbeat at {Time}", DateTimeOffset.UtcNow);
            await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
        }
    }
}
```

`BackgroundService` 的 `StartAsync` 会把 `ExecuteAsync` 作为一个后台 Task 启动后立刻返回，不会阻塞 Host 继续接请求。`StopAsync` 则取消 `stoppingToken` 并等待你的任务结束。你不用写任何生命周期管理代码，6 行业务逻辑就够了。

整个 `BackgroundService` 实现大约 80 行，可以直接在 GitHub 上看源码，没有什么魔法。

## 同一任务，两种写法

用"每 30 秒记录一次心跳"来对比，差异一目了然。

**用 IHostedService 原始实现（约 30 行）**：

```csharp
public sealed class HeartbeatHostedService(ILogger<HeartbeatHostedService> logger) : IHostedService
{
    private Task? _backgroundTask;
    private CancellationTokenSource? _stoppingCts;

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _stoppingCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        _backgroundTask = RunAsync(_stoppingCts.Token);
        return Task.CompletedTask;
    }

    public async Task StopAsync(CancellationToken cancellationToken)
    {
        if (_backgroundTask is null) return;
        try
        {
            _stoppingCts!.Cancel();
        }
        finally
        {
            await Task.WhenAny(_backgroundTask, Task.Delay(Timeout.Infinite, cancellationToken));
        }
    }

    private async Task RunAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            logger.LogInformation("Heartbeat at {Time}", DateTimeOffset.UtcNow);
            await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
        }
    }
}
```

大约 30 行，绝大部分是生命周期管道：链接 CancellationToken、持有 Task 引用、在 `StopAsync` 里和关闭 token 赛跑避免挂死。每一行都是过去踩过 bug 的地方。

**用 BackgroundService（6 行）**：

```csharp
public sealed class HeartbeatBackgroundService(ILogger<HeartbeatBackgroundService> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            logger.LogInformation("Heartbeat at {Time}", DateTimeOffset.UtcNow);
            await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
        }
    }
}
```

行为完全一致，但生命周期管道由框架负责。除非你的后台任务不是循环形态，否则没有理由手写那 30 行。

## 注册和生命周期

注册只要一行：

```csharp
builder.Services.AddHostedService<HeartbeatBackgroundService>();
```

`AddHostedService<T>()` 把服务注册为 `IHostedService` 的单例实现。Host 启动时按注册顺序调用每个 `StartAsync`，关闭时**按逆序**调用 `StopAsync`。

逆序关闭意味着：如果 ServiceA 依赖 ServiceB，先注册 B 再注册 A，关闭时 A 先停（此时 B 还在运行），再停 B。顺序调整一下就会悄悄破坏这个保证，这是一个经常被忽视的细节。

## 5 个生产级坑

这是原文最有价值的部分，每个坑都对应过一次真实的线上事故。

### 坑 1：未处理异常会把整个 Host 进程杀掉

这是最贵的坑。

.NET 6 之前，`ExecuteAsync` 抛出未处理异常会被记录日志，然后 BackgroundService 悄悄停止运行，API 进程还在。

**.NET 6 及之后，默认行为变了**：`ExecuteAsync` 抛出异常，整个 Host 进程终止。这个行为由 `BackgroundServiceExceptionBehavior` 控制，.NET 6+ 的默认值是 `StopHost`。

凌晨 3 点，一个发邮件的 BackgroundService 因为一个瞬时 SMTP 错误，把整个订单 API 拉下来了——这就是这个默认值的代价。

修复分两层。全局配置：

```csharp
builder.Services.Configure<HostOptions>(opts =>
{
    opts.BackgroundServiceExceptionBehavior = BackgroundServiceExceptionBehavior.Ignore;
});
```

但光改全局还不够。正确模式是在循环体里加 try/catch，让瞬时错误不要打断循环：

```csharp
protected override async Task ExecuteAsync(CancellationToken stoppingToken)
{
    while (!stoppingToken.IsCancellationRequested)
    {
        try
        {
            await SendQueuedEmailsAsync(stoppingToken);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            logger.LogError(ex, "Email loop iteration failed. Continuing.");
        }

        await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
    }
}
```

**实践建议**：对大多数生产 API，把 `BackgroundServiceExceptionBehavior` 设为 `Ignore`，**同时**在循环体里加 try/catch。几乎不会有场景想让一个后台瞬时错误把整个 Host 拉下来。

### 坑 2：向 BackgroundService 注入 Scoped 服务（Captive Dependency）

`BackgroundService` 是单例。如果直接在构造函数里注入 `DbContext`（Scoped 生命周期），这个 `DbContext` 实例会活到 Host 结束，而不是每次迭代刷新。

**错误写法**：

```csharp
public sealed class OrderProcessor(MyDbContext db, ILogger<OrderProcessor> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            // db 是同一个实例，永远不会被 dispose
            // 变更追踪无限增长，第一次 SQL 异常会让它永久损坏
            var orders = await db.Orders.Where(o => !o.Processed).ToListAsync(stoppingToken);
            await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken);
        }
    }
}
```

开发环境跑得好好的，到了生产环境 DbContext 会逐渐积累追踪的实体，内存增长，第一次瞬时 SQL 异常之后 context 就坏了，再也查不出正确结果。

**正确写法**：注入 `IServiceScopeFactory`，每次迭代创建一个新的 scope：

```csharp
public sealed class OrderProcessor(IServiceScopeFactory scopeFactory, ILogger<OrderProcessor> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            using var scope = scopeFactory.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<MyDbContext>();

            var orders = await db.Orders
                .Where(o => !o.Processed)
                .ToListAsync(stoppingToken);
            // db 在 using 块结束时被 dispose，下次循环拿到全新的实例

            await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken);
        }
    }
}
```

编译器不会阻止你把 `DbContext` 直接注入单例，所以这个 bug 能编译通过，只在高负载下才暴露。

### 坑 3：ExecuteAsync 提前返回会让服务永久死亡

BackgroundService 只有在 `ExecuteAsync` 的 Task 存活时才算"运行中"。一旦 `ExecuteAsync` 返回，框架就把服务标记为已完成，不会重试，不会重启，除非整个 Host 重启。

常见的三种意外退出：

- 异常逃脱了循环体里的 catch，直接传出 `ExecuteAsync`
- 循环因为某个测试用的计数器或布尔标志意外退出
- 一个 await 的 Task 返回了 faulted 状态并在外层 try 之外重新抛出

防御方式：在 `ExecuteAsync` 入口和出口都打日志，用 finally 块兜底：

```csharp
protected override async Task ExecuteAsync(CancellationToken stoppingToken)
{
    logger.LogInformation("{Service} ExecuteAsync starting", nameof(OrderProcessor));
    try
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await ProcessOneBatchAsync(stoppingToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                logger.LogError(ex, "Iteration failed. Continuing the loop.");
            }

            await Task.Delay(TimeSpan.FromSeconds(15), stoppingToken);
        }
    }
    catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
    {
        // 正常优雅关闭，不记录为错误
    }
    finally
    {
        logger.LogInformation("{Service} ExecuteAsync exiting", nameof(OrderProcessor));
    }
}
```

finally 里的退出日志就是告警。如果在非发布窗口期看到 `ExecuteAsync exiting`，说明服务已经悄悄死了。曾经有 BackgroundService 静默停止了好几天，唯一的症状是"outbox 不再排空"，就是因为没有退出日志。

### 坑 4：忽略 stoppingToken 会拖慢关闭并丢失进行中的工作

`HostOptions.ShutdownTimeout` 默认 5 秒。如果 `ExecuteAsync` 忽略 `stoppingToken`，`StopAsync` 等满 5 秒后放弃，Host 继续关闭。此时你的循环可能正在写数据库的一半——那次写丢了。

**正确**：每个 await 和每个循环条件都传入 `stoppingToken`：

```csharp
while (!stoppingToken.IsCancellationRequested)
{
    await DoWorkAsync(stoppingToken);
    await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken);
}
```

**错误**：

```csharp
while (true)
{
    DoWork();            // 没有 token，没有 async，没有取消
    Thread.Sleep(10_000); // 阻塞线程，忽略 stoppingToken
}
```

`Thread.Sleep(10_000)` 在收到关闭信号时不会被唤醒，导致 Host 白等 5 秒然后强制放弃。

如果每次迭代确实需要超过 5 秒才能干净结束（比如排空一批队列消息），可以显式延长超时：

```csharp
builder.Services.Configure<HostOptions>(opts =>
{
    opts.ShutdownTimeout = TimeSpan.FromSeconds(30);
});
```

但延长超时几乎都是错的方向。正确做法是让每次迭代足够短，并且始终响应 `stoppingToken`。

### 坑 5：CPU 密集型工作会饿死线程池

`ExecuteAsync` 运行在 ThreadPool 线程上。如果你做大量不 await 的 CPU 密集计算，那个线程就被你占着，背后其他请求开始排队超时。

两个处理方向：

- 对真正重的计算，用 `Task.Factory.StartNew(..., TaskCreationOptions.LongRunning)` 开专属线程，不占 ThreadPool
- 对可分批的工作，在批次之间插入 `await Task.Yield()` 或 `await Task.Delay(1, stoppingToken)` 让出线程

但说实话，如果计算要持续好几分钟，把这个工作放在 API 进程里的 BackgroundService 本来就是错误的选择。正确方式是把任务推到队列（SQS、Service Bus、Kafka），用独立 worker 进程处理。API 进程里的 BackgroundService 应该保持轻量：轮询、分发、出队。真正的重活放到别处去。

## 什么时候不该用 Hosted Services

Hosted Services 适合进程内、与应用同生命周期的后台任务。以下场景应该选专用工具：

| 需求                               | 推荐工具               |
| ---------------------------------- | ---------------------- |
| 任务在重启后能继续（持久化）       | Hangfire、Quartz.NET   |
| Cron 调度（"每周一上午 9 点"）     | Quartz.NET             |
| 可视化仪表盘                       | Hangfire               |
| 多实例协调（不重复执行同一个任务） | Hangfire、Quartz.NET   |
| 长时间运行（超过关闭宽限期）       | Hangfire               |
| 事件驱动的后台任务                 | Wolverine、MassTransit |

**Hangfire**：带持久化（SQL 或 Redis）、重试、仪表盘、定期任务的作业队列。80% 的场景下，当 BackgroundService 不够用时，就是 Hangfire。

**Quartz.NET**：重量级调度，支持 Cron 表达式、时区、复杂日历。简单轮询用不到，复杂调度场景是首选。

**Wolverine / MassTransit**：消息总线驱动的后台任务。触发器是"有事件发生"而不是"每隔 N 秒"时选这个形状。

原文作者的判断：如果你发现自己在 BackgroundService 上面堆持久化、重试逻辑和仪表盘，说明你在把 Hangfire 重发明一遍，而且发明得很差。直接用 Hangfire。

## 决策矩阵

| 使用场景                              | IHostedService | BackgroundService | Hangfire  | Quartz.NET | Wolverine  |
| ------------------------------------- | -------------- | ----------------- | --------- | ---------- | ---------- |
| 持续循环（轮询 / 心跳 / outbox 处理） | ❌             | ✅                | 过重      | ❌         | 仅事件驱动 |
| 一次性启动任务（迁移、注册、预热）    | ✅             | ❌                | ❌        | ❌         | ❌         |
| 一次性关闭任务（排空、注销）          | ✅             | ❌                | ❌        | ❌         | ❌         |
| Cron 调度                             | ❌             | 手写很难看        | 基础 cron | ✅         | 基础 cron  |
| 带持久化 + 重试的作业队列             | ❌             | ❌                | ✅        | ❌         | ✅         |
| 需要运维仪表盘                        | ❌             | ❌                | ✅        | ❌         | ✅         |
| 多实例协调（不重复运行）              | ❌             | ❌                | ✅        | ✅         | ✅         |
| 事件驱动的后台任务                    | ❌             | 需要手动接线      | ❌        | ❌         | ✅         |
| 轻量进程内后台任务                    | ✅             | ✅                | 过重      | 过重       | 过重       |
| 应用重启后能恢复                      | ❌             | ❌                | ✅        | ✅         | ✅         |
| CPU 密集型、分钟级运行                | ❌             | ❌（推到 worker） | ✅        | ✅         | ✅         |

行里两列都是 ❌ 就是升级到 Hangfire、Quartz 或消息总线的信号。不要在 BackgroundService 上面发明持久化。

## 关键结论

- `IHostedService` 是 2 个方法的原始接口；`BackgroundService` 是为持续循环任务实现了 `IHostedService` 的抽象基类
- **对 .NET 10 里 99% 的后台任务，用 `BackgroundService`**。只有一次性启动或关闭任务才直接实现 `IHostedService`。需要持久化、调度或分布式协调时用 Hangfire / Quartz / Wolverine
- .NET 6 及之后，`ExecuteAsync` 未处理异常默认会终止整个 Host 进程，把 `BackgroundServiceExceptionBehavior` 设为 `Ignore` 并在循环体里加 try/catch
- 不要把 `DbContext` 或其他 Scoped 服务直接注入 `BackgroundService` 构造函数，使用 `IServiceScopeFactory` 并每次迭代创建新的 scope
- 在 `ExecuteAsync` 的入口和出口都打日志，finally 块里的退出日志是发现服务静默死亡的最快方式
- 每个 await 和每个循环条件都传入 `stoppingToken`，永远不要 `Thread.Sleep`

## 参考

- [Understanding IHostedService & BackgroundService in .NET 10 - codewithmukesh](https://codewithmukesh.com/blog/ihostedservice-vs-backgroundservice-dotnet/)
- [Background tasks with hosted services in ASP.NET Core - Microsoft Docs](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/host/hosted-services)
- [BackgroundService 源码 - GitHub dotnet/runtime](https://github.com/dotnet/runtime/blob/main/src/libraries/Microsoft.Extensions.Hosting.Abstractions/src/BackgroundService.cs)
