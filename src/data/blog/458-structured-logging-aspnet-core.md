---
pubDatetime: 2025-09-11
tags: ["ASP.NET Core", "Serilog", "Logging", "Structured Logging", "C#", ".NET"]
slug: structured-logging-aspnet-core
source: https://codingsonata.com/structured-logging-in-asp-net-core/
title: ASP.NET Core 中的结构化日志记录：使用 Serilog 实现高效日志管理
description: 深入了解如何在 ASP.NET Core 中使用 Serilog 实现结构化日志记录，包括配置、最佳实践和多种输出目标的设置。
---

# ASP.NET Core 中的结构化日志记录：使用 Serilog 实现高效日志管理

在现代软件开发中，日志记录是最重要且关键的功能之一，它允许开发人员和产品负责人排查和分析应用程序错误。结构化日志记录是一种写入日志的方式，使日志不仅仅是纯文本消息，而是带有上下文的数据。与将日志条目视为字符串不同，结构化日志记录将关键信息捕获为字段（如 JSON），这使得日志更容易存储、搜索和使用现代日志管理工具进行分析。

使用 Serilog 或任何其他日志记录提供程序，当您的应用程序写入全面而广泛的日志时，您将能够追踪发生的任何错误或问题，这将极大地帮助找到问题的解决方案。

## 为什么选择结构化日志记录？

传统的日志记录方式往往产生难以解析和分析的纯文本消息。而结构化日志记录通过以下优势彻底改变了这一现状：

- **可查询性**：以键值对形式存储的数据使得日志搜索和过滤变得简单高效
- **可分析性**：便于与现代日志管理工具（如 ELK Stack、Seq、Grafana）集成
- **上下文丰富**：每条日志都包含相关的上下文信息，便于问题定位
- **标准化格式**：统一的日志格式使得跨服务日志分析成为可能

## 1. 安装 Serilog 相关 NuGet 包

首先，我们需要安装核心 Serilog 库以及相关的依赖库，这些库用于丰富结构化格式并通过不同的接收器将日志输出到不同的目标。

您可以使用 Visual Studio 2022 的 NuGet 包管理器 GUI，或者在 NuGet 包管理器控制台中运行以下命令：

```bash
dotnet add package Serilog.AspNetCore
dotnet add package Serilog.Settings.Configuration
dotnet add package Serilog.Sinks.File
dotnet add package Serilog.Sinks.MSSqlServer
dotnet add package Serilog.Enrichers.Environment
dotnet add package Serilog.Enrichers.Thread
```

这些包提供了：

- **Serilog.AspNetCore**：ASP.NET Core 集成的核心包
- **Serilog.Settings.Configuration**：从配置文件读取设置
- **Serilog.Sinks.File**：文件输出支持
- **Serilog.Sinks.MSSqlServer**：SQL Server 数据库输出支持
- **Serilog.Enrichers.Environment** 和 **Serilog.Enrichers.Thread**：日志增强功能

## 2. appsettings.json 配置

为了使日志记录更加动态，建议将日志配置保存在 appsettings.json 文件中，这样您可以在不重新部署整个 ASP.NET Core 项目的情况下更改设置。

这些设置可以包括常规日志级别、特定接收器的配置（如文件路径和参数）、日志模板结构、访问控制提供程序（如数据库或基于索引的提供程序）的凭据。

以下是包含文件和 SQL Server 接收器的 Serilog 配置的 appsettings.json 文件示例：

```json
{
  "Serilog": {
    "Using": ["Serilog.Sinks.File", "Serilog.Sinks.MSSqlServer"],
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft": "Warning",
        "System": "Warning"
      }
    },
    "Enrich": ["FromLogContext", "WithMachineName", "WithThreadId"],
    "WriteTo": [
      {
        "Name": "File",
        "Args": {
          "path": "logs/app-.log",
          "rollingInterval": "Day",
          "retainedFileCountLimit": 7,
          "outputTemplate": "[{Timestamp:yyyy-MM-dd HH:mm:ss} {Level:u3}] {Message:lj}{Properties:j}{NewLine}{Exception}"
        }
      },
      {
        "Name": "MSSqlServer",
        "Args": {
          "connectionString": "Server=Home\\SQLEXPRESS;Database=TasksDb;Trusted_Connection=True;MultipleActiveResultSets=true",
          "tableName": "Logs",
          "autoCreateSqlTable": true,
          "columnOptionsSection": {
            "addStandardColumns": ["LogEvent", "Properties"]
          }
        }
      }
    ]
  }
}
```

### 配置详解

- **MinimumLevel**：设置最小日志级别，默认为 Information
- **Override**：为特定命名空间设置不同的日志级别
- **Enrich**：添加额外的上下文信息，如机器名、线程ID等
- **WriteTo**：定义日志输出目标（接收器）

## 3. Program.cs 设置

在这一步中，我们将在 ASP.NET Core 项目中指定 Serilog 作为日志记录提供程序，并配置 Serilog 从 appsettings.json 文件中读取配置（根据 launch.json 文件中指定的当前环境）。

以下是需要在 Program.cs 文件中包含的代码：

```csharp
using Serilog;

var builder = WebApplication.CreateBuilder(args);

// 从 appsettings.json 加载 Serilog 配置
Log.Logger = new LoggerConfiguration()
    .ReadFrom.Configuration(builder.Configuration)
    .CreateLogger();

builder.Host.UseSerilog();

builder.Services.AddControllers();

var app = builder.Build();

app.MapControllers();

app.Run();
```

这个配置：

1. 创建全局静态 Logger 实例
2. 从配置文件读取 Serilog 设置
3. 将 Serilog 注册为 ASP.NET Core 的日志提供程序

## 4. 使用抽象的 ILogger<T>

Serilog（以及许多其他日志记录库）的优点在于它们可以利用抽象的泛型 `ILogger<T>` 接口，基于 `ILogger<T>` 中可用的功能提供日志记录功能。

这是抽象如何提供强大方式通过不同提供程序扩展功能而无需更改代码实现的绝佳示例。

以下是在控制器中使用 `ILogger<T>` 的示例：

```csharp
using Microsoft.AspNetCore.Mvc;

namespace StructuredLogging.Controllers
{
    public record Task(int UserId, string Title, string Description);

    [ApiController]
    [Route("api/[controller]")]
    public class TasksController(ILogger<TasksController> logger) : ControllerBase
    {
        [HttpPost]
        public IActionResult CreateTask(Task task)
        {
            logger.LogInformation("User {UserId} created task {Title} with description {Description}",
                task.UserId, task.Title, task.Description);

            try
            {
                if (string.IsNullOrWhiteSpace(task.Title))
                    throw new ArgumentException("Task title cannot be empty");

                return Ok(new { Status = "Task created" });
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Failed to create task for {UserId} with title {Title}", task.UserId, task.Title);
                return BadRequest("Task creation failed");
            }
        }
    }
}
```

### 结构化日志记录的关键特点

注意在上述代码中，我们使用了占位符语法 `{UserId}`、`{Title}` 等，而不是字符串连接。这是结构化日志记录的核心：

- 使用占位符而非字符串插值
- 每个占位符都会成为日志事件中的一个属性
- 便于后续查询和分析

## 5. 测试 API

使用 Postman 模拟调用 CreateTask 端点来触发根据定义的日志级别插入日志，并将其转储到定义的接收器中。

### SQL Server 接收器 (MSSqlServer)

应用程序首次运行后，它将使用提供的设置在 SQL Server 中创建表。在表中快速搜索，将显示添加的完整详细信息日志。

### 文件接收器

您还会发现日志根据配置设置写入文件中。打开文件，将显示转储在其中的结构化日志。

## ASP.NET Core 结构化日志记录的 12 条规则

以下是在 ASP.NET Core 中实现结构化日志记录时要遵循的规则和最佳实践列表：

### 1. 使用 ILogger<T> 保持代码与提供程序解耦

始终使用依赖注入的 `ILogger<T>` 接口，避免直接依赖具体的日志库。

### 2. 选择合适的日志级别

正确使用 Debug、Information、Warning、Error、Critical 等日志级别。

### 3. 正确记录异常

始终包含异常对象和堆栈跟踪信息。

### 4. 保持日志结构化

使用 Serilog 等知名日志库，使用 `{}` 占位符，避免字符串连接。

### 5. 永远不要记录敏感数据

屏蔽密码和个人信息。

### 6. 添加上下文和关联 ID

跨服务跟踪请求、用户和操作。

### 7. 在 appsettings.json 中配置日志级别

根据环境调整（开发环境使用 Debug，生产环境使用 Warning）。

### 8. 集中化日志

使用 Seq、ELK、Grafana、Azure Monitor 或 CloudWatch。

### 9. 设置保留和轮换策略

防止日志文件无限制增长。

### 10. 通过警报和监控丰富日志

对重复出现的警告和关键故障采取行动。

### 11. 利用 OpenTelemetry 和异步日志记录

统一日志、跟踪、指标，并提升性能。

### 12. 安全的日志存储

对日志文件和仪表板进行访问控制。

## 高级配置示例

### 环境特定配置

```json
{
  "Serilog": {
    "MinimumLevel": {
      "Default": "Debug",
      "Override": {
        "Microsoft": "Information",
        "Microsoft.Hosting.Lifetime": "Information"
      }
    },
    "WriteTo": [
      {
        "Name": "Console",
        "Args": {
          "theme": "Serilog.Sinks.SystemConsole.Themes.AnsiConsoleTheme::Code, Serilog.Sinks.Console",
          "outputTemplate": "[{Timestamp:HH:mm:ss} {Level:u3}] {Message:lj} <s:{SourceContext}>{NewLine}{Exception}"
        }
      }
    ]
  }
}
```

### 自定义增强器

```csharp
public class RequestIdEnricher : ILogEventEnricher
{
    public void Enrich(LogEvent logEvent, ILogEventPropertyFactory propertyFactory)
    {
        var requestId = Activity.Current?.Id ?? "N/A";
        logEvent.AddPropertyIfAbsent(propertyFactory.CreateProperty("RequestId", requestId));
    }
}
```

## 性能考虑

### 异步日志记录

```csharp
Log.Logger = new LoggerConfiguration()
    .WriteTo.Async(a => a.File("logs/app.log"))
    .CreateLogger();
```

### 条件日志记录

```csharp
// 避免不必要的字符串构建
if (logger.IsEnabled(LogLevel.Debug))
{
    logger.LogDebug("Complex operation result: {@Result}", expensiveOperation());
}
```

## 结论

使用 Serilog 在 ASP.NET Core 中实现结构化日志记录使日志比纯文本更有用。通过将数据捕获为键值对，您可以精确地查询、过滤和分析日志。

使用抽象的泛型 `ILogger<T>`，您可以保持标准的 .NET 实践，同时获得 Serilog 的强大功能：多个接收器、增强器以及通过 appsettings.json 进行配置。

这种方法确保了跨控制台、文件和 SQL Server 的一致、可搜索和可操作的日志，帮助您有效地监控和排查应用程序问题。

## 参考资源

- [Serilog 官方文档](https://serilog.net/)
- [.NET 和 ASP.NET Core 中的日志记录](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/logging/?view=aspnetcore-9.0)
- [Microsoft.Extensions.Logging 文档](https://docs.microsoft.com/en-us/dotnet/core/extensions/logging)

通过遵循这些最佳实践和配置示例，您将能够在 ASP.NET Core 应用程序中建立强大、可扩展和易于维护的日志记录系统。结构化日志记录不仅提高了应用程序的可观测性，还为问题诊断和性能优化提供了坚实的基础。
