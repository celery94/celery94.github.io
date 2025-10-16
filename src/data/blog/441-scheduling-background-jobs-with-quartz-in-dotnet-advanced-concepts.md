---
pubDatetime: 2025-08-19
tags: [".NET", "Architecture"]
slug: scheduling-background-jobs-with-quartz-in-dotnet-advanced-concepts
source: https://www.milanjovanovic.tech/blog/scheduling-background-jobs-with-quartz-in-dotnet-advanced-concepts
title: 使用 Quartz.NET 在 .NET 中调度后台任务的高级概念
description: 深入探讨如何在 ASP.NET Core 应用程序中使用 Quartz.NET 实现强大的后台任务调度，包括持久化存储、监控和生产级配置。
---

# 使用 Quartz.NET 在 .NET 中调度后台任务的高级概念

在现代 ASP.NET Core 应用程序中，后台任务处理是一个不可或缺的组成部分。无论是发送提醒邮件、执行数据清理任务，还是处理定期报告生成，我们都需要一个可靠的后台任务调度器。虽然有多种实现后台任务的方式，但 Quartz.NET 凭借其强大的调度能力、持久化选项和生产就绪的特性脱颖而出。

## Quartz.NET 简介与优势

Quartz.NET 是一个功能丰富的开源作业调度库，它是 Java Quartz 调度器的 .NET 移植版本。与其他后台任务解决方案相比，Quartz.NET 提供了以下关键优势：

### 核心特性

**强大的调度能力**：支持简单的时间间隔调度和复杂的 Cron 表达式调度，能够满足从简单到复杂的各种调度需求。

**持久化存储**：支持多种数据库后端（SQL Server、PostgreSQL、MySQL、Oracle），确保任务在应用程序重启后不会丢失。

**集群支持**：在多实例环境中，Quartz.NET 可以确保同一个任务不会被重复执行，提供了良好的负载均衡和故障转移能力。

**监控与可观测性**：与 OpenTelemetry 集成，提供详细的任务执行追踪和性能监控。

**灵活的任务数据传递**：通过 JobDataMap 机制，可以向任务传递复杂的参数和配置信息。

## 在 ASP.NET Core 中设置 Quartz.NET

### 安装必要的 NuGet 包

首先，我们需要安装相关的 NuGet 包。以下是推荐的包列表：

```xml
<PackageReference Include="Quartz.Extensions.Hosting" Version="3.8.0" />
<PackageReference Include="Quartz.Serialization.Json" Version="3.8.0" />
<PackageReference Include="OpenTelemetry.Instrumentation.Quartz" Version="1.5.0-beta.1" />
```

注意：`OpenTelemetry.Instrumentation.Quartz` 可能处于预发布状态，请根据实际情况选择合适的版本。

### 基础配置

在 `Program.cs` 中配置 Quartz 服务和 OpenTelemetry 集成：

```csharp
var builder = WebApplication.CreateBuilder(args);

// 添加 Quartz.NET 服务
builder.Services.AddQuartz();

// 将 Quartz.NET 添加为托管服务
builder.Services.AddQuartzHostedService(options =>
{
    // 等待作业完成后再关闭应用程序
    options.WaitForJobsToComplete = true;
});

// 配置 OpenTelemetry 监控
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing =>
    {
        tracing
            .AddHttpClientInstrumentation()
            .AddAspNetCoreInstrumentation()
            .AddQuartzInstrumentation(); // 添加 Quartz 追踪
    })
    .UseOtlpExporter();

var app = builder.Build();
```

这个基础配置为我们提供了：

- Quartz 调度器的基本功能
- 应用程序关闭时等待任务完成的优雅关闭机制
- 完整的可观测性支持，便于监控和调试

## 定义和调度任务

### 创建任务类

要定义后台任务，需要实现 `IJob` 接口。所有任务实现都作为作用域服务运行，因此可以注入所需的依赖项：

```csharp
public class EmailReminderJob(
    ILogger<EmailReminderJob> logger,
    IEmailService emailService) : IJob
{
    public const string Name = nameof(EmailReminderJob);

    public async Task Execute(IJobExecutionContext context)
    {
        // 最佳实践：优先使用 MergedJobDataMap
        var data = context.MergedJobDataMap;

        // 获取任务数据 - 注意这不是强类型的
        string? userId = data.GetString("userId");
        string? message = data.GetString("message");

        // 数据验证
        if (string.IsNullOrEmpty(userId) || string.IsNullOrEmpty(message))
        {
            logger.LogError("缺少必需的任务数据：userId 或 message");
            throw new InvalidOperationException("任务数据不完整");
        }

        try
        {
            await emailService.SendReminderAsync(userId, message);

            logger.LogInformation("成功发送提醒给用户 {UserId}: {Message}", userId, message);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "发送提醒失败，用户 {UserId}", userId);

            // 重新抛出异常让 Quartz 处理重试逻辑
            throw;
        }
    }
}
```

### 任务数据管理

Quartz 允许通过 `JobDataMap` 字典向任务传递数据。有几种获取任务数据的方式：

1. **JobDataMap** - 键值对字典

   - `JobExecutionContext.JobDetail.JobDataMap` - 任务特定数据
   - `JobExecutionContext.Trigger.TriggerDataMap` - 触发器特定数据

2. **MergedJobDataMap** - 合并任务数据和触发器数据

**最佳实践建议**：

- 使用 `MergedJobDataMap` 获取任务数据
- 仅使用基本类型避免序列化问题
- 使用常量定义键名以避免拼写错误
- 在 `Execute` 方法开始时验证数据

### 调度一次性任务

以下是如何调度一次性提醒任务的实现：

```csharp
public record ScheduleReminderRequest(
    string UserId,
    string Message,
    DateTime ScheduleTime
);

// 调度一次性提醒
app.MapPost("/api/reminders/schedule", async (
    ISchedulerFactory schedulerFactory,
    ScheduleReminderRequest request) =>
{
    var scheduler = await schedulerFactory.GetScheduler();

    // 创建任务数据
    var jobData = new JobDataMap
    {
        { "userId", request.UserId },
        { "message", request.Message }
    };

    // 创建任务
    var job = JobBuilder.Create<EmailReminderJob>()
        .WithIdentity($"reminder-{Guid.NewGuid()}", "email-reminders")
        .SetJobData(jobData)
        .Build();

    // 创建触发器
    var trigger = TriggerBuilder.Create()
        .WithIdentity($"trigger-{Guid.NewGuid()}", "email-reminders")
        .StartAt(request.ScheduleTime)
        .Build();

    // 调度任务
    await scheduler.ScheduleJob(job, trigger);

    return Results.Ok(new {
        scheduled = true,
        scheduledTime = request.ScheduleTime,
        jobId = job.Key.ToString()
    });
})
.WithName("ScheduleReminder")
.WithOpenApi();
```

**示例请求**：

```json
{
  "userId": "user123",
  "message": "重要会议提醒！",
  "scheduleTime": "2025-08-20T15:00:00"
}
```

## 调度重复任务

对于重复执行的后台任务，可以使用 Cron 调度表达式：

```csharp
public record RecurringReminderRequest(
    string UserId,
    string Message,
    string CronExpression
);

// 调度重复提醒
app.MapPost("/api/reminders/schedule/recurring", async (
    ISchedulerFactory schedulerFactory,
    RecurringReminderRequest request) =>
{
    var scheduler = await schedulerFactory.GetScheduler();

    var jobData = new JobDataMap
    {
        { "userId", request.UserId },
        { "message", request.Message }
    };

    var job = JobBuilder.Create<EmailReminderJob>()
        .WithIdentity($"recurring-{Guid.NewGuid()}", "recurring-reminders")
        .SetJobData(jobData)
        .Build();

    var trigger = TriggerBuilder.Create()
        .WithIdentity($"recurring-trigger-{Guid.NewGuid()}", "recurring-reminders")
        .WithCronSchedule(request.CronExpression)
        .StartNow() // 可选：立即开始
        .Build();

    await scheduler.ScheduleJob(job, trigger);

    return Results.Ok(new {
        scheduled = true,
        cronExpression = request.CronExpression,
        nextFireTime = trigger.GetNextFireTimeUtc()
    });
})
.WithName("ScheduleRecurringReminder")
.WithOpenApi();
```

### Cron 表达式详解

Cron 触发器比简单触发器更强大，允许定义复杂的调度，如"每个工作日上午 10 点"或"每 15 分钟"。Quartz 支持包含秒、分、时、日、月、年的 Cron 表达式。

**常用 Cron 表达式示例**：

```csharp
// 每分钟执行
"0 * * ? * *"

// 每小时的第 30 分钟执行
"0 30 * ? * *"

// 每天上午 10 点执行
"0 0 10 ? * *"

// 每个工作日上午 10 点执行
"0 0 10 ? * MON-FRI"

// 每月第一天上午 9 点执行
"0 0 9 1 * ?"

// 每 15 分钟执行
"0 0/15 * ? * *"
```

**示例请求**：

```json
{
  "userId": "user123",
  "message": "每日站会提醒",
  "cronExpression": "0 0 10 ? * MON-FRI"
}
```

## 任务持久化配置

默认情况下，Quartz 使用内存存储，这意味着应用程序重启时任务会丢失。对于生产环境，需要使用持久化存储。

### PostgreSQL 持久化配置

```csharp
builder.Services.AddQuartz(options =>
{
    // 注册持久化任务
    options.AddJob<EmailReminderJob>(c => c
        .StoreDurably() // 标记为持久化任务
        .WithIdentity(EmailReminderJob.Name));

    // 配置持久化存储
    options.UsePersistentStore(persistenceOptions =>
    {
        persistenceOptions.UsePostgres(cfg =>
        {
            cfg.ConnectionString = connectionString;
            cfg.TablePrefix = "scheduler.qrtz_"; // 使用专用模式
        },
        dataSourceName: "reminders"); // 数据源名称

        // 使用 JSON 序列化器
        persistenceOptions.UseNewtonsoftJsonSerializer();
        persistenceOptions.UseProperties = true;
    });
});
```

### 数据库架构设置

**重要配置说明**：

1. **TablePrefix 设置**：`scheduler.qrtz_` 前缀将 Quartz 表放在专用的 `scheduler` 模式中，有助于组织数据库表结构。

2. **数据库脚本**：需要运行适当的数据库脚本来创建这些表。每个数据库提供商都有自己的设置脚本。

3. **模式隔离**：使用专用模式可以更好地管理 Quartz 相关表，避免与应用程序表混淆。

**PostgreSQL 模式创建示例**：

```sql
-- 创建专用模式
CREATE SCHEMA IF NOT EXISTS scheduler;

-- 设置搜索路径
SET search_path TO scheduler, public;

-- 运行 Quartz PostgreSQL 表创建脚本
-- (从 Quartz.NET 仓库获取相应的 SQL 脚本)
```

### 持久化任务模式

使用 `StoreDurably()` 配置的持久化任务是一种强大的模式，允许一次定义任务并通过不同的触发器重用：

```csharp
public class JobSchedulingService
{
    private readonly ISchedulerFactory _schedulerFactory;

    public JobSchedulingService(ISchedulerFactory schedulerFactory)
    {
        _schedulerFactory = schedulerFactory;
    }

    public async Task ScheduleReminder(string userId, string message, DateTime scheduledTime)
    {
        var scheduler = await _schedulerFactory.GetScheduler();

        // 引用存储的任务
        var jobKey = new JobKey(EmailReminderJob.Name);

        var trigger = TriggerBuilder.Create()
            .ForJob(jobKey)  // 引用持久化任务
            .WithIdentity($"trigger-{Guid.NewGuid()}")
            .UsingJobData("userId", userId)
            .UsingJobData("message", message)
            .StartAt(scheduledTime)
            .Build();

        // 注意：只传递触发器
        await scheduler.ScheduleJob(trigger);
    }

    public async Task ScheduleRecurringReminder(
        string userId,
        string message,
        string cronExpression)
    {
        var scheduler = await _schedulerFactory.GetScheduler();
        var jobKey = new JobKey(EmailReminderJob.Name);

        var trigger = TriggerBuilder.Create()
            .ForJob(jobKey)
            .WithIdentity($"recurring-trigger-{Guid.NewGuid()}")
            .UsingJobData("userId", userId)
            .UsingJobData("message", message)
            .WithCronSchedule(cronExpression)
            .Build();

        await scheduler.ScheduleJob(trigger);
    }
}
```

**持久化任务的优势**：

1. **集中管理**：任务定义在启动配置中集中管理
2. **配置一致性**：确保所有调度的任务配置一致
3. **防止错误**：无法意外调度未正确配置的任务
4. **代码复用**：一个任务定义可以被多个触发器使用

## 高级任务管理功能

### 任务监控和管理 API

创建一组 API 端点来监控和管理调度的任务：

```csharp
// 获取所有任务状态
app.MapGet("/api/jobs", async (ISchedulerFactory schedulerFactory) =>
{
    var scheduler = await schedulerFactory.GetScheduler();
    var jobKeys = await scheduler.GetJobKeys(GroupMatcher<JobKey>.AnyGroup());

    var jobs = new List<object>();
    foreach (var jobKey in jobKeys)
    {
        var jobDetail = await scheduler.GetJobDetail(jobKey);
        var triggers = await scheduler.GetTriggersOfJob(jobKey);

        var triggerStates = new List<object>();
        foreach (var trigger in triggers)
        {
            var state = await scheduler.GetTriggerState(trigger.Key);
            triggerStates.Add(new
            {
                triggerId = trigger.Key.ToString(),
                state = state.ToString(),
                nextFireTime = trigger.GetNextFireTimeUtc(),
                previousFireTime = trigger.GetPreviousFireTimeUtc()
            });
        }

        jobs.Add(new
        {
            jobId = jobKey.ToString(),
            jobType = jobDetail?.JobType.Name,
            triggers = triggerStates
        });
    }

    return Results.Ok(jobs);
});

// 暂停任务
app.MapPost("/api/jobs/{jobId}/pause", async (
    string jobId,
    ISchedulerFactory schedulerFactory) =>
{
    var scheduler = await schedulerFactory.GetScheduler();
    var jobKey = JobKey.Create(jobId);

    await scheduler.PauseJob(jobKey);
    return Results.Ok(new { paused = true });
});

// 恢复任务
app.MapPost("/api/jobs/{jobId}/resume", async (
    string jobId,
    ISchedulerFactory schedulerFactory) =>
{
    var scheduler = await schedulerFactory.GetScheduler();
    var jobKey = JobKey.Create(jobId);

    await scheduler.ResumeJob(jobKey);
    return Results.Ok(new { resumed = true });
});

// 删除任务
app.MapDelete("/api/jobs/{jobId}", async (
    string jobId,
    ISchedulerFactory schedulerFactory) =>
{
    var scheduler = await schedulerFactory.GetScheduler();
    var jobKey = JobKey.Create(jobId);

    var deleted = await scheduler.DeleteJob(jobKey);
    return Results.Ok(new { deleted });
});
```

### 任务执行历史记录

实现一个任务执行监听器来记录任务执行历史：

```csharp
public class JobExecutionHistoryListener : IJobListener
{
    private readonly ILogger<JobExecutionHistoryListener> _logger;
    private readonly IServiceProvider _serviceProvider;

    public string Name => nameof(JobExecutionHistoryListener);

    public JobExecutionHistoryListener(
        ILogger<JobExecutionHistoryListener> logger,
        IServiceProvider serviceProvider)
    {
        _logger = logger;
        _serviceProvider = serviceProvider;
    }

    public Task JobToBeExecuted(IJobExecutionContext context,
        CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("任务即将执行: {JobKey}", context.JobDetail.Key);
        return Task.CompletedTask;
    }

    public Task JobExecutionVetoed(IJobExecutionContext context,
        CancellationToken cancellationToken = default)
    {
        _logger.LogWarning("任务执行被否决: {JobKey}", context.JobDetail.Key);
        return Task.CompletedTask;
    }

    public async Task JobWasExecuted(IJobExecutionContext context,
        JobExecutionException? jobException,
        CancellationToken cancellationToken = default)
    {
        using var scope = _serviceProvider.CreateScope();
        // 假设有一个服务来记录执行历史
        // var historyService = scope.ServiceProvider.GetRequiredService<IJobHistoryService>();

        var executionInfo = new
        {
            JobKey = context.JobDetail.Key.ToString(),
            FireTime = context.FireTimeUtc,
            RunTime = context.JobRunTime,
            Success = jobException == null,
            Error = jobException?.Message
        };

        if (jobException != null)
        {
            _logger.LogError(jobException, "任务执行失败: {JobKey}", context.JobDetail.Key);
        }
        else
        {
            _logger.LogInformation("任务执行成功: {JobKey}, 耗时: {RunTime}ms",
                context.JobDetail.Key, context.JobRunTime.TotalMilliseconds);
        }

        // await historyService.RecordExecutionAsync(executionInfo, cancellationToken);
    }
}

// 在 Program.cs 中注册监听器
builder.Services.AddQuartz(options =>
{
    // ... 其他配置

    options.AddJobListener<JobExecutionHistoryListener>();
});
```

## 错误处理和重试策略

### 实现重试逻辑

```csharp
public class ResilientEmailReminderJob : IJob
{
    private readonly ILogger<ResilientEmailReminderJob> _logger;
    private readonly IEmailService _emailService;
    private const int MaxRetries = 3;

    public ResilientEmailReminderJob(
        ILogger<ResilientEmailReminderJob> logger,
        IEmailService emailService)
    {
        _logger = logger;
        _emailService = emailService;
    }

    public async Task Execute(IJobExecutionContext context)
    {
        var data = context.MergedJobDataMap;
        string? userId = data.GetString("userId");
        string? message = data.GetString("message");
        int retryCount = data.GetInt("retryCount");

        try
        {
            await _emailService.SendReminderAsync(userId, message);
            _logger.LogInformation("邮件发送成功，用户: {UserId}", userId);
        }
        catch (Exception ex) when (retryCount < MaxRetries)
        {
            _logger.LogWarning(ex, "邮件发送失败，第 {RetryCount} 次重试，用户: {UserId}",
                retryCount + 1, userId);

            // 更新重试计数并重新调度
            var scheduler = context.Scheduler;
            var newJobData = new JobDataMap(data) { ["retryCount"] = retryCount + 1 };

            var retryJob = JobBuilder.Create<ResilientEmailReminderJob>()
                .WithIdentity($"retry-{context.JobDetail.Key.Name}-{retryCount + 1}")
                .SetJobData(newJobData)
                .Build();

            var retryTrigger = TriggerBuilder.Create()
                .WithIdentity($"retry-trigger-{Guid.NewGuid()}")
                .StartAt(DateTimeOffset.UtcNow.AddMinutes(Math.Pow(2, retryCount))) // 指数退避
                .Build();

            await scheduler.ScheduleJob(retryJob, retryTrigger);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "邮件发送最终失败，已达到最大重试次数，用户: {UserId}", userId);
            throw; // 最终失败，抛出异常
        }
    }
}
```

## 性能优化和最佳实践

### 连接池配置

```csharp
builder.Services.AddQuartz(options =>
{
    options.UsePersistentStore(persistenceOptions =>
    {
        persistenceOptions.UsePostgres(cfg =>
        {
            cfg.ConnectionString = connectionString;
            cfg.TablePrefix = "scheduler.qrtz_";
        });

        // 配置连接池
        persistenceOptions.UseProperties = true;
    });

    // 配置线程池
    options.UseDefaultThreadPool(tp =>
    {
        tp.MaxConcurrency = 10; // 根据需要调整
    });
});
```

### 任务设计最佳实践

1. **保持任务轻量级**：将复杂逻辑分解为多个简单任务
2. **使用依赖注入**：充分利用 ASP.NET Core 的依赖注入容器
3. **实现幂等性**：确保任务可以安全地重复执行
4. **适当的日志记录**：记录任务开始、完成和错误信息
5. **资源清理**：确保任务正确释放资源

```csharp
public class OptimizedDataProcessingJob : IJob
{
    private readonly ILogger<OptimizedDataProcessingJob> _logger;
    private readonly IDataProcessor _dataProcessor;
    private readonly IServiceScopeFactory _scopeFactory;

    public OptimizedDataProcessingJob(
        ILogger<OptimizedDataProcessingJob> logger,
        IDataProcessor dataProcessor,
        IServiceScopeFactory scopeFactory)
    {
        _logger = logger;
        _dataProcessor = dataProcessor;
        _scopeFactory = scopeFactory;
    }

    public async Task Execute(IJobExecutionContext context)
    {
        using var scope = _scopeFactory.CreateScope();
        var cancellationToken = context.CancellationToken;

        try
        {
            _logger.LogInformation("开始数据处理任务");

            // 使用作用域服务处理数据
            var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

            await _dataProcessor.ProcessDataAsync(dbContext, cancellationToken);

            _logger.LogInformation("数据处理任务完成");
        }
        catch (OperationCanceledException)
        {
            _logger.LogInformation("数据处理任务被取消");
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "数据处理任务失败");
            throw;
        }
    }
}
```

## 监控和可观测性

### OpenTelemetry 集成

配置详细的 OpenTelemetry 监控：

```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing =>
    {
        tracing
            .AddHttpClientInstrumentation()
            .AddAspNetCoreInstrumentation()
            .AddQuartzInstrumentation(options =>
            {
                // 配置 Quartz 追踪选项
                options.RecordException = true;
                options.SetDbStatementForText = true;
            })
            .AddEntityFrameworkCoreInstrumentation();
    })
    .WithMetrics(metrics =>
    {
        metrics
            .AddHttpClientInstrumentation()
            .AddAspNetCoreInstrumentation();
    })
    .UseOtlpExporter();
```

### 健康检查

添加 Quartz 健康检查：

```csharp
builder.Services.AddHealthChecks()
    .AddQuartz(options =>
    {
        options.CheckScheduler = true;
        options.CheckJobs = true;
    });

app.MapHealthChecks("/health");
```

## 集群部署考虑

在多实例环境中部署 Quartz.NET 时，需要考虑以下因素：

### 集群配置

```csharp
builder.Services.AddQuartz(options =>
{
    options.UsePersistentStore(persistenceOptions =>
    {
        persistenceOptions.UsePostgres(cfg =>
        {
            cfg.ConnectionString = connectionString;
            cfg.TablePrefix = "scheduler.qrtz_";
        });

        // 启用集群模式
        persistenceOptions.UseClustering(clusterOptions =>
        {
            clusterOptions.CheckinInterval = TimeSpan.FromSeconds(10);
            clusterOptions.CheckinMisfireThreshold = TimeSpan.FromSeconds(20);
        });
    });

    // 配置实例名称和 ID
    options.SchedulerName = "MyAppScheduler";
    options.SchedulerId = Environment.MachineName;
});
```

### 注意事项

1. **时钟同步**：确保所有实例的系统时钟同步
2. **数据库连接**：配置适当的连接池大小
3. **故障转移**：了解集群中节点故障时的行为
4. **负载分配**：Quartz 会自动在可用节点间分配任务

## 总结

在 .NET 应用程序中正确设置 Quartz.NET 需要考虑多个方面：

1. **任务定义和数据处理**：使用 `JobDataMap` 正确处理任务数据，实现幂等性和错误处理
2. **调度策略**：掌握一次性和重复任务的调度方法，灵活运用 Cron 表达式
3. **持久化配置**：配置适当的数据库存储和模式隔离
4. **监控和可观测性**：集成 OpenTelemetry 和健康检查
5. **生产就绪**：考虑集群部署、错误处理和性能优化

Quartz.NET 为构建可靠的后台处理系统提供了坚实的基础，这些元素共同构成了一个能够随应用程序需求增长的可靠后台处理系统。无论是简单的提醒任务还是复杂的数据处理工作流，掌握这些高级概念都将帮助你构建出生产就绪的解决方案。

通过合理的架构设计和配置，Quartz.NET 可以成为你 .NET 应用程序中可靠的后台任务处理引擎，为用户提供及时、准确的服务体验。
