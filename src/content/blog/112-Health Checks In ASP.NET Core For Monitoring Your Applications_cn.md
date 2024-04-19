---
pubDatetime: 2024-04-19
tags: []
source: https://www.milanjovanovic.tech/blog/health-checks-in-asp-net-core?utm_source=Twitter&utm_medium=social&utm_campaign=15.04.2024
author: Milan Jovanović
title: 在ASP.NET Core中使用健康检查监控您的应用程序
description: 我们都希望构建能够无限扩展并处理任意数量请求的健壮且可靠的应用程序。但随着分布式系统和微服务架构日益增长的复杂性，监控我们应用程序的健康变得越来越困难。
---

# 在ASP.NET Core中使用健康检查监控您的应用程序

> ## 摘要

---

我们都希望构建**健壮**且**可靠**的应用程序，这些应用程序能无限扩展并处理任意数量的请求。

但随着**分布式系统**和**微服务架构**增长的复杂性，监控我们应用程序的**健康**变得越来越困难。

拥有一个系统来快速反馈应用程序**健康**状态是至关重要的。

这就是**健康检查**的用武之地。

**健康检查**提供了一种监控和验证应用程序各个组件健康情况的方法，包括：

- 数据库
- API接口
- 缓存
- 外部服务

让我们看看如何在**ASP.NET Core**中实现**健康检查**。

## 什么是健康检查？

**健康检查**是一种主动机制，用于监控和验证**ASP.NET Core**中应用程序的**健康状态**和**可用性**。

ASP.NET Core具有**内置支持**来实现**健康检查**。

这是基本配置，它注册健康检查服务，并添加`HealthCheckMiddleware`以在指定的URL响应。

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHealthChecks();

var app = builder.Build();

app.MapHealthChecks("/health");

app.Run();
```

健康检查返回一个`HealthStatus`值，指示服务的健康状态。

有三种不同的`HealthStatus`值：

- `HealthStatus.Healthy`
- `HealthStatus.Degraded`
- `HealthStatus.Unhealthy`

您可以使用`HealthStatus`来指示应用程序的不同状态。

例如，如果应用程序的运行速度比预期慢，你可以返回`HealthStatus.Degraded`。

## 添加自定义健康检查

您可以通过实现`IHealthCheck`接口来创建**自定义健康检查**。

例如，您可以实现一个检查，看看您的**SQL**数据库是否可用。

在数据库中使用一个能快速完成的查询是很重要的，比如`SELECT 1`。

这是在`SqlHealthCheck`类中的一个**自定义健康检查**实现示例：

```csharp
public class SqlHealthCheck : IHealthCheck
{
    private readonly string _connectionString;

    public SqlHealthCheck(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("Database");
    }

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        try
        {
            using var sqlConnection = new SqlConnection(_connectionString);

            await sqlConnection.OpenAsync(cancellationToken);

            using var command = sqlConnection.CreateCommand();
            command.CommandText = "SELECT 1";

            await command.ExecuteScalarAsync(cancellationToken);

            return HealthCheckResult.Healthy();
        }
        catch(Exception ex)
        {
            return HealthCheckResult.Unhealthy(
                context.Registration.FailureStatus,
                exception: ex);
        }
    }
}
```

实现**自定义健康检查**后，您需要进行注册。

之前对`AddHealthChecks`的调用现在变为：

```csharp
builder.Services.AddHealthChecks()
    .AddCheck<SqlHealthCheck>("custom-sql", HealthStatus.Unhealthy);
```

我们给它一个自定义名称，并设置在`HealthCheckContext.Registration.FailureStatus`中使用哪种状态作为失败结果。

但是，请稍停一下思考。

对于你拥有的**每一个外部服务**，你都想自己实现一个**自定义健康检查**吗？

当然不是！有一个更好的解决方案。

## 使用现有健康检查库

在你开始为每件事实现自定义**健康检查**之前，你应该首先看看是否已经有了一个**现有的库**。

在[`AspNetCore.Diagnostics.HealthChecks`](https://github.com/Xabaril/AspNetCore.Diagnostics.HealthChecks)仓库中，你可以找到用于常用服务和库的广泛集合**健康检查**包。

这里有一些示例：

- SQL Server - `AspNetCore.HealthChecks.SqlServer`
- Postgres - `AspNetCore.HealthChecks.Npgsql`
- Redis - `AspNetCore.HealthChecks.Redis`
- RabbitMQ - `AspNetCore.HealthChecks.RabbitMQ`
- AWS S3 - `AspNetCore.HealthChecks.Aws.S3`
- SignalR - `AspNetCore.HealthChecks.SignalR`

以下是如何为**PostgreSQL**和**RabbitMQ**添加健康检查：

```csharp
builder.Services.AddHealthChecks()
    .AddCheck<SqlHealthCheck>("custom-sql", HealthStatus.Unhealthy);
    .AddNpgSql(pgConnectionString)
    .AddRabbitMQ(rabbitConnectionString)
```

## 格式化健康检查响应

默认情况下，返回你的**健康检查**状态的端点将返回一个代表`HealthStatus`的字符串值。

如果你配置了**多个健康检查**，这不实用，因为你希望单独查看每项服务的健康状态。

更糟糕的是，如果其中一项服务失败，整个响应将返回`Unhealthy`，你不知道问题的原因。

你可以通过提供一个`ResponsWriter`来解决这个问题，而在`AspNetCore.HealthChecks.UI.Client`库中就存在这样一个。

让我们安装**NuGet**包：

```powershell
Install-Package AspNetCore.HealthChecks.UI.Client
```

你需要稍微更新对`MapHealthChecks`的调用，以使用来自此库的`ResponseWriter`：

```csharp
app.MapHealthChecks( "/health", new HealthCheckOptions { ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse });
```

做了这些改变之后，健康检查端点的响应看起来是这样的：

```json
{
  "status": "Unhealthy",
  "totalDuration": "00:00:00.3285211",
  "entries": {
    "npgsql": {
      "data": {},
      "duration": "00:00:00.1183517",
      "status": "Healthy",
      "tags": []
    },
    "rabbitmq": {
      "data": {},
      "duration": "00:00:00.1189561",
      "status": "Healthy",
      "tags": []
    },
    "custom-sql": {
      "data": {},
      "description": "无法连接到数据库。",
      "duration": "00:00:00.2431813",
      "exception": "无法连接到数据库。",
      "status": "Unhealthy",
      "tags": []
    }
  }
}
```

## 要点

应用程序监控对于跟踪应用程序的可用性、资源使用情况和性能变化很重要。

我之前在**云部署**中使用了**健康检查**来实现**故障转移情景**。当一个应用实例停止回应健康结果时，会创建一个新的实例继续处理请求。

通过**暴露健康检查**，可以轻松监控ASP.NET Core应用程序的健康状况。

你可以选择实现**自定义健康检查**，但首先考虑是否有**现成的解决方案**。
