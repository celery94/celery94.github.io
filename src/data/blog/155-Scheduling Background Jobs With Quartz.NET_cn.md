---
pubDatetime: 2024-05-27
tags: [".NET", "Architecture"]
source: https://www.milanjovanovic.tech/blog/scheduling-background-jobs-with-quartz-net?utm_source=Twitter&utm_medium=social&utm_campaign=27.05.2024
author: Milan Jovanović
title: 使用 Quartz.NET 调度后台作业
description: 如果你正在构建一个可扩展的应用程序，通常要求将应用程序中的一些工作卸载到后台作业中。
---

# 使用 Quartz.NET 调度后台作业

> 原文 [Scheduling Background Jobs With Quartz.NET](https://www.milanjovanovic.tech/blog/scheduling-background-jobs-with-quartz-net?utm_source=Twitter&utm_medium=social&utm_campaign=27.05.2024) 由 [Milan Jovanović](https://www.milanjovanovic.tech/) 发表。

---

如果你正在构建一个可扩展的应用程序，通常要求将应用程序中的一些工作卸载到**后台作业**中。

以下是一些示例：

- 发送电子邮件通知
- 生成报告
- 更新缓存
- 图像处理

如何在 .NET 中创建一个重复的**后台作业**？

[**Quartz.NET**](https://www.quartz-scheduler.net/) 是一个全功能的开源作业调度系统，可用于从最小的应用到大规模企业系统。

在**Quartz.NET**中有三个概念需要理解：

- **Job** - 你要运行的实际后台任务
- **Trigger** - 控制作业运行时间的触发器
- **Scheduler** - 负责协调作业和触发器

让我们看看如何使用 **Quartz.NET** 创建和调度**后台作业**。

## 添加 Quartz.NET 托管服务

我们首先需要安装 **Quartz.NET** NuGet 包。有几个可以选择，但我们要安装 `Quartz.Extensions.Hosting` 库：

```powershell
Install-Package Quartz.Extensions.Hosting
```

我们使用这个库的原因是它很好地与 .NET 集成，使用 `IHostedService` 实例。

要使 **Quartz.NET** 托管服务运行，我们需要两件事：

- 使用 DI 容器添加所需的服务
- 添加托管服务

```csharp
services.AddQuartz(configure =>
{
    configure.UseMicrosoftDependencyInjectionJobFactory();
});

services.AddQuartzHostedService(options =>
{
    options.WaitForJobsToComplete = true;
});
```

**Quartz.NET** 将通过从 DI 容器中获取来创建作业。这也意味着你可以在作业中使用 scoped 服务，而不仅仅是 singleton 或 transient 服务。

将 `WaitForJobsToComplete` 选项设置为 `true` 将确保 **Quartz.NET** 在退出前优雅地等待作业完成。

## 使用 `IJob` 创建后台作业

要使用 **Quartz.NET** 创建后台作业，你需要实现 `IJob` 接口。

它只公开一个方法 - `Execute` - 你可以在这里放置后台作业的代码。

这里有几点值得注意：

- 我们使用 DI 注入 `ApplicationDbContext` 和 `IPublisher` 服务
- 作业使用 `DisallowConcurrentExecution` 特性装饰，以防止同时运行相同的作业

```csharp
[DisallowConcurrentExecution]
public class ProcessOutboxMessagesJob : IJob
{
    private readonly ApplicationDbContext _dbContext;
    private readonly IPublisher _publisher;

    public ProcessOutboxMessagesJob(
        ApplicationDbContext dbContext,
        IPublisher publisher)
    {
        _dbContext = dbContext;
        _publisher = publisher;
    }

    public async Task Execute(IJobExecutionContext context)
    {
        List<OutboxMessage> messages = await _dbContext
            .Set<OutboxMessage>()
            .Where(m => m.ProcessedOnUtc == null)
            .Take(20)
            .ToListAsync(context.CancellationToken);

        foreach (OutboxMessage outboxMessage in messages)
        {
            IDomainEvent? domainEvent = JsonConvert
                .DeserializeObject<IDomainEvent>(
                    outboxMessage.Content,
                    new JsonSerializerSettings
                    {
                        TypeNameHandling = TypeNameHandling.All
                    });

            if (domainEvent is null)
            {
                continue;
            }

            await _publisher.Publish(domainEvent, context.CancellationToken);

            outboxMessage.ProcessedOnUtc = DateTime.UtcNow;

            await _dbContext.SaveChangesAsync();
        }
    }
}
```

现在 **后台作业** 已经准备好了，我们需要将其注册到 **DI** 容器中并添加一个触发器来运行该作业。

## 配置作业

我在开始时提到，在 **Quartz.NET** 中有三个关键概念：

- 作业
- 触发器
- 调度器

在前一部分中，我们已经实现了 `ProcessOutboxMessagesJob` 后台作业。

**Quartz.NET** 库将负责调度器。

接下来我们仍需为 `ProcessOutboxMessagesJob` 配置一个**触发器**。

```csharp
services.AddQuartz(configure =>
{
    var jobKey = new JobKey(nameof(ProcessOutboxMessagesJob));

    configure
        .AddJob<ProcessOutboxMessagesJob>(jobKey)
        .AddTrigger(
            trigger => trigger.ForJob(jobKey).WithSimpleSchedule(
                schedule => schedule.WithIntervalInSeconds(10).RepeatForever()));

    configure.UseMicrosoftDependencyInjectionJobFactory();
});
```

我们需要使用 `JobKey` 唯一标识我们的**后台作业**。我喜欢保持简单，使用作业名称。

调用 `AddJob` 将在 DI 中注册 `ProcessOutboxMessagesJob`，并同时在 Quartz 中注册。

之后，我们通过调用 `AddTrigger` 为该作业配置一个触发器。你需要通过调用 `ForJob` 将作业与触发器关联，然后为后台作业配置时间表。在这个例子中，我将作业设置为每十秒运行一次，并在托管服务运行时无限重复。

**Quartz** 还支持使用 [cron 表达式](https://www.quartz-scheduler.net/documentation/quartz-3.x/tutorial/crontriggers.html) 配置触发器。

## 作业持久性

默认情况下，Quartz 使用 `RAMJobStore` 配置所有作业，这是最具性能的，因为它将所有数据保存在 RAM 中。然而，这也意味着它是易失的，当你的应用程序停止或崩溃时，你可能会丢失所有调度信息。

在某些情况下，拥有一个持久的作业存储是有用的，内置的 `AdoJobStore` 可以与 SQL 数据库一起工作。你需要为 Quartz.NET 创建一组数据库表。

你可以在 [作业存储文档](https://www.quartz-scheduler.net/documentation/quartz-3.x/tutorial/job-stores.html) 中了解更多信息。

## 总结

**Quartz.NET** 使在 .NET 中运行**后台作业**变得容易，你可以在**后台作业**中使用 DI 的所有功能。它还灵活地支持使用代码配置或 cron 表达式的各种调度需求。

有一些改进的空间可以使作业调度更容易并减少样板代码：

- 添加扩展方法以简化使用简单时间表配置作业
- 添加扩展方法以简化从应用程序设置中使用 cron 时间表配置作业

如果你想查看有关使用 **Quartz.NET** 的教程，我制作了一个有关[**使用 Quartz 处理 Outbox 消息**](https://youtu.be/XALvnX7MPeo) 的详细视频。
