---
pubDatetime: 2025-09-29
title: ".NET 分布式锁定：多实例协调工作的实用指南"
description: "深入探讨 .NET 环境下的分布式锁定机制，包括 PostgreSQL Advisory Locks 和 DistributedLock 库的实现方案，帮助解决多实例环境中的并发访问问题。"
tags: [".NET", "分布式系统", "并发控制", "PostgreSQL", "Redis"]
slug: distributed-locking-dotnet-coordination
source: https://www.milanjovanovic.tech/blog/distributed-locking-in-dotnet-coordinating-work-across-multiple-instances
---

在构建需要横跨多个服务器或进程运行的应用程序时，我们经常会遇到并发访问的问题。多个工作进程同时尝试更新同一资源，最终导致竞态条件、重复工作或数据损坏。

.NET 为单进程场景提供了优秀的并发控制原语，如 `lock`、`SemaphoreSlim` 和 `Mutex`。但当应用程序扩展到多个实例时，这些原语就不再适用了。

这就是分布式锁定发挥作用的地方。分布式锁定通过确保一次只有一个节点（应用程序实例）可以访问关键部分，来防止竞态条件并维护分布式系统中的数据一致性。

## 何时需要分布式锁定

在单进程应用中，你可以直接使用 `lock` 或 .NET 10 中新的 Lock 类。但一旦你向外扩展，这就不够了，因为每个进程都有自己的内存空间。

以下是分布式锁定发挥价值的几种常见情况：

**后台作业处理**：确保一次只有一个工作进程处理特定的作业或资源。当你有多个实例运行相同的后台服务时，分布式锁可以防止多个实例同时处理同一个任务。

**领导者选举**：选择单个进程执行周期性工作，比如应用异步数据库投影或执行定期维护任务。这在微服务架构中特别有用，可以避免多个服务实例执行相同的管理任务。

**避免重复执行**：确保在部署到多个实例时，计划任务不会多次运行。例如，每日报告生成或数据同步任务应该只执行一次，而不是在每个实例上都执行。

**协调共享资源**：确保一次只有一个服务实例执行迁移或清理操作。数据库架构迁移是一个典型例子，多个实例同时执行迁移可能导致严重的数据问题。

**缓存雪崩预防**：确保当给定缓存键过期时，只有一个实例刷新缓存。这避免了多个实例同时重建缓存而造成的系统负载峰值。

核心价值在于：在分布式环境中保证一致性和安全性。没有这些保障，你会面临重复操作、状态损坏或不必要的负载风险。

## 使用 PostgreSQL Advisory Locks 实现分布式锁定

让我们从简单的开始。PostgreSQL 有一个名为 Advisory Locks 的特性，非常适合分布式锁定。与表锁不同，这些锁不会干扰你的数据——它们纯粹用于协调。

```csharp
public class NightlyReportService(NpgsqlDataSource dataSource)
{
    public async Task ProcessNightlyReport()
    {
        await using var connection = dataSource.OpenConnection();

        var key = HashKey("nightly-report");

        var acquired = await connection.ExecuteScalarAsync<bool>(
            "SELECT pg_try_advisory_lock(@key)",
            new { key });

        if (!acquired)
        {
            throw new ConflictException("另一个实例正在处理夜间报告");
        }

        try
        {
            await DoWork();
        }
        finally
        {
            await connection.ExecuteAsync(
                "SELECT pg_advisory_unlock(@key)",
                new { key });
        }
    }

    private static long HashKey(string key) =>
        BitConverter.ToInt64(SHA256.HashData(Encoding.UTF8.GetBytes(key)), 0);

    private static Task DoWork() => Task.Delay(5000); // 你的实际工作逻辑
}
```

让我们分析一下底层的工作原理：

**键值转换**：我们将锁名称转换为数字。PostgreSQL Advisory Locks 需要数字键，所以我们将 `"nightly-report"` 哈希为 64 位整数。每个节点（应用程序实例）必须为相同字符串生成相同的数字，否则锁定机制将无法工作。

**尝试获取锁**：`pg_try_advisory_lock()` 尝试在该数字上获取排他锁。如果成功则返回 `true`，如果另一个连接已经持有则返回 `false`。这个调用不会阻塞——它立即告诉你是否获得了锁。

**执行工作**：如果我们获得锁，就执行我们的工作。如果没有，我们返回冲突响应，让其他实例处理。

**释放锁**：`finally` 块确保我们总是释放锁，即使出现问题。PostgreSQL 还会在连接关闭时自动释放 Advisory Locks，这是一个很好的安全网。

SQL Server 也有类似的特性，即 `sp_getapplock` 存储过程，提供了相似的功能。

## 探索 DistributedLock 库

虽然 DIY 方法可以工作，但生产应用程序需要更复杂的功能。DistributedLock 库处理边缘情况并提供多个后端选项（Postgres、Redis、SqlServer 等）。我是不重新发明轮子的拥护者，所以这是一个很好的选择。

首先安装包：

```powershell
Install-Package DistributedLock
```

我会使用 `IDistributedLockProvider` 的方法，它与 DI 配合得很好。你可以获取锁而无需了解底层基础设施的任何信息。你所要做的就是在 DI 容器中注册锁提供程序实现。

使用 Postgres 的例子：

```csharp
// 注册分布式锁提供程序
builder.Services.AddSingleton<IDistributedLockProvider>(
    (_) =>
    {
        return new PostgresDistributedSynchronizationProvider(
            builder.Configuration.GetConnectionString("distributed-locking")!);
    });
```

或者，如果你想使用 Redis 和 Redlock 算法：

```csharp
// 需要 StackExchange.Redis
builder.Services.AddSingleton<IConnectionMultiplexer>(
    (_) =>
    {
        return ConnectionMultiplexer.Connect(
            builder.Configuration.GetConnectionString("redis")!);
    });

// 注册分布式锁提供程序
builder.Services.AddSingleton<IDistributedLockProvider>(
    (sp) =>
    {
        var connectionMultiplexer = sp.GetRequiredService<IConnectionMultiplexer>();

        return new RedisDistributedSynchronizationProvider(
            connectionMultiplexer.GetDatabase());
    });
```

使用方法很直接：

```csharp
// 你也可以传入超时时间，提供程序会持续重试获取锁直到达到超时
IDistributedSynchronizationHandle? distributedLock = distributedLockProvider
    .TryAcquireLock("nightly-report");

// 如果我们没有获得锁，对象将为 null
if (distributedLock is null)
{
    return Results.Conflict();
}

// 重要的是将锁包装在 using 语句中，确保正确释放
using (distributedLock)
{
    await DoWork();
}
```

该库处理所有棘手的部分：超时、重试，以及确保即使在失败场景下也能释放锁。

它还支持许多后端（SQL Server、Azure、ZooKeeper 等），使其成为生产工作负载的可靠选择。

## 最佳实践与注意事项

在实际应用中使用分布式锁时，有几个重要的最佳实践需要遵循：

**设置合理的超时时间**：始终为锁设置超时时间，避免死锁情况。如果持有锁的进程崩溃，超时机制确保锁最终会被释放。

```csharp
// 设置 30 秒超时
var distributedLock = await distributedLockProvider
    .TryAcquireLockAsync("my-lock", TimeSpan.FromSeconds(30));
```

**实现幂等性**：即使有分布式锁，也要确保你的操作是幂等的。这提供了额外的安全保障，以防锁机制出现问题。

**监控锁的性能**：记录锁的获取时间和持有时间，这有助于识别性能瓶颈和潜在的死锁情况。

**选择合适的后端**：

- PostgreSQL Advisory Locks：如果你已经在使用 PostgreSQL，这是最简单的选择
- Redis：适合需要高性能和低延迟的场景
- SQL Server：如果你的基础设施主要基于 Microsoft 技术栈

**错误处理策略**：决定当无法获取锁时该如何处理。你可以选择抛出异常、返回错误状态码，或者实现重试逻辑。

## 性能考虑

分布式锁定会引入网络延迟和额外的基础设施依赖。在设计系统时需要考虑这些因素：

**网络延迟影响**：每次锁操作都涉及网络调用，这会增加操作的总延迟。对于频繁的锁操作，这可能成为性能瓶颈。

**故障转移机制**：确保你的锁后端具有高可用性。如果锁服务不可用，你的整个应用可能会受到影响。

**锁的粒度**：选择合适的锁粒度。过细的锁可能导致过多的竞争，过粗的锁可能降低并发性。

## 总结

分布式锁定不是你每天都需要的东西。但当你需要时，它能让你免受只在负载下或生产环境中才出现的微妙而痛苦的错误。

从简单开始：如果你已经在使用 Postgres，Advisory Locks 是一个强大的工具。

为了更清洁的开发者体验，可以选择 DistributedLock 库。

选择适合你基础设施的后端（Postgres、Redis、SQL Server 等）。

在正确的时间使用正确的锁，确保你的系统保持一致、可靠和弹性，即使跨越多个进程和服务器。

分布式锁定是构建可扩展、可靠的分布式系统的重要工具。虽然它增加了一些复杂性，但它提供的一致性保证对于许多实际应用场景来说是必不可少的。选择合适的实现方案，遵循最佳实践，你就能构建出既高效又可靠的分布式应用程序。

## 参考资料

- [PostgreSQL Advisory Locks 官方文档](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
- [DistributedLock 库 GitHub 仓库](https://github.com/madelson/DistributedLock)
- [Redis 分布式锁文档](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)
- [原文链接 - Milan Jovanovic Tech](https://www.milanjovanovic.tech/blog/distributed-locking-in-dotnet-coordinating-work-across-multiple-instances)
