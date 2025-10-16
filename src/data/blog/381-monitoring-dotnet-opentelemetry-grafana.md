---
pubDatetime: 2025-06-21
tags: [".NET", "Architecture"]
slug: monitoring-dotnet-opentelemetry-grafana
source: https://www.milanjovanovic.tech/blog/monitoring-dotnet-applications-with-opentelemetry-and-grafana
title: 利用 OpenTelemetry 和 Grafana 监控 .NET 应用实践详解
description: 本文详细介绍如何在 .NET 应用中集成 OpenTelemetry，实现分布式链路追踪与日志采集，并通过 Grafana Cloud 进行统一可观测性展示。内容涵盖原理、实现步骤、关键代码解析、实际效果与常见问题解决方案，助力开发者构建高效、可观测的生产系统。
---

# 利用 OpenTelemetry 和 Grafana 监控 .NET 应用实践详解

## 引言

在现代分布式系统中，仅依靠传统日志已无法满足对系统健康和性能的全面观测。当生产环境中发生故障时，开发者常常陷入翻查日志、猜测瓶颈与关联问题的泥潭。随着 OpenTelemetry 的普及和 Grafana Cloud 的易用性提升，实现端到端可观测性已经变得简单高效。

本文将带你完整体验如何通过 OpenTelemetry 为 .NET 应用植入分布式追踪与日志采集能力，并将数据无缝接入 Grafana Cloud，实现统一的指标、日志与链路可视化。

---

## 背景与技术原理

### OpenTelemetry 简介

OpenTelemetry 是一个开源的可观测性框架，支持多语言，标准化地采集**链路追踪（Tracing）**、**指标（Metrics）**和**日志（Logs）**数据。它具备自动化采集、上下文关联和供应商无关等特点，是现代应用监控的事实标准。

### Grafana 及其 Cloud 服务

[Grafana](https://grafana.com/) 是业界领先的可观测性平台，支持多数据源聚合、灵活仪表盘、告警和日志分析等功能。[Grafana Cloud](https://grafana.com/products/cloud/) 则提供免运维的云端服务，开箱即用，支持与 OpenTelemetry 的原生集成。

---

## 实现步骤

### 1. 安装并集成 OpenTelemetry

在你的 .NET 项目中，通过 NuGet 安装核心包和所需的自动化探针：

```shell
Install-Package OpenTelemetry.Extensions.Hosting
Install-Package OpenTelemetry.Exporter.OpenTelemetryProtocol
Install-Package OpenTelemetry.Instrumentation.AspNetCore
Install-Package OpenTelemetry.Instrumentation.Http
```

可选扩展（根据实际使用的组件选择）：

```shell
Install-Package OpenTelemetry.Instrumentation.EntityFrameworkCore
Install-Package OpenTelemetry.Instrumentation.StackExchangeRedis
Install-Package Npgsql.OpenTelemetry
```

### 2. 配置 OpenTelemetry 采集与导出

在 `Program.cs` 中进行如下配置，实现 ASP.NET Core、EF Core、Redis、PostgreSQL 的自动追踪，并通过 OTLP 协议导出数据：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddOpenTelemetry()
    .ConfigureResource(resource => resource.AddService(serviceName))
    .WithTracing(tracing =>
    {
        tracing
            .AddAspNetCoreInstrumentation()
            .AddHttpClientInstrumentation()
            .AddEntityFrameworkCoreInstrumentation()
            .AddRedisInstrumentation()
            .AddNpgsql();

        tracing.AddOtlpExporter();
    });

builder.Logging.AddOpenTelemetry(logging =>
{
    logging.IncludeScopes = true;
    logging.IncludeFormattedMessage = true;

    logging.AddOtlpExporter();
});

var app = builder.Build();
app.Run();
```

**代码要点解析：**

- `AddOpenTelemetry()`：引导核心 SDK。
- `.AddAspNetCoreInstrumentation()` 等：自动采集请求/数据库操作等追踪。
- `AddOtlpExporter()`：通过 OTLP 协议导出数据，便于与 Grafana Cloud 对接。

### 3. 获取并配置 Grafana Cloud 接入信息

#### a. 获取 Stack Details 和接入参数

1. 注册并登录 [Grafana Cloud](https://grafana.com/auth/sign-up/create-user)。
2. 进入 **My Account → Stack Details** 页面，查找你的 OTLP Endpoint 和建议配置。

![Stack Details 示例](https://www.milanjovanovic.tech/blogs/mnw_147/grafana_setup.png?imwidth=3840)

3. 生成具有写权限的 API Token。

![Token 生成页面](https://www.milanjovanovic.tech/blogs/mnw_147/grafana_setup_token.png?imwidth=3840)

4. 获取官方推荐的环境变量配置：

![环境变量配置示例](https://www.milanjovanovic.tech/blogs/mnw_147/grafana_setup_env_vars.png?imwidth=3840)

#### b. 配置 OTLP 导出参数

建议将以下配置写入 `appsettings.json` 或作为环境变量设置：

```json
{
  "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otlp-gateway-prod-eu-west-2.grafana.net/otlp",
  "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
  "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Basic <your-base64-encoded-token>"
}
```

> **说明**：`<your-base64-encoded-token>` 为你实际生成并 base64 编码后的 API Token。

---

## 数据采集效果与实际应用案例

### 1. 链路追踪可视化

启动应用并产生一些流量后，在 Grafana Cloud 控制台的 **Traces** 区域即可看到完整的请求链路：

![Grafana Trace 示例 - 注册请求](https://www.milanjovanovic.tech/blogs/mnw_147/grafana_trace_1.png?imwidth=3840)

如上图所示，一个 `POST users/register` 请求包含多个 Span，清晰展示了各环节耗时、依赖调用等。

如果你的系统涉及消息队列，还能看到跨服务的链路追踪：

![Grafana Trace 示例 - 消息队列场景](https://www.milanjovanovic.tech/blogs/mnw_147/grafana_trace_2.png?imwidth=3840)

### 2. 日志与链路关联分析

Grafana Cloud 支持按 Trace/Span ID 自动关联日志，实现“日志与链路无缝切换”：

![日志视图示例1](https://www.milanjovanovic.tech/blogs/mnw_147/grafana_logs_1.png?imwidth=3840)
![日志视图示例2](https://www.milanjovanovic.tech/blogs/mnw_147/grafana_logs_2.png?imwidth=3840)

你可以按严重级别筛选、全文检索，定位单次请求的详细日志。点击 Trace 可切换至相关链路，极大提升排查效率。

---

## 常见问题与解决方案

### Q1. 日志或链路数据未采集到 Grafana？

- 检查网络连通性，确保服务器可访问 OTLP Endpoint。
- 确认 API Token 权限及 base64 编码是否正确。
- 查看应用启动日志，确认没有 OTLP 导出异常。

### Q2. 如何安全管理 Token？

- 使用环境变量或安全配置管理密钥，避免硬编码在源码或公开仓库。
- 设置 Token 最小权限原则，仅授予必要的写入权限。

### Q3. 性能影响大吗？

- OpenTelemetry 默认对性能影响较小，可根据实际情况调整采样率或仅启用核心模块。
- 如需采集高流量场景建议开启批量导出并合理配置资源限制。

---

## 总结与展望

通过本文介绍的方法，你可以轻松为 .NET 应用构建全链路追踪、统一日志与指标监控体系，实现从单体到微服务的可观测性升级：

- **OpenTelemetry** 提供无供应商锁定的标准化数据采集能力；
- **Grafana Cloud** 提供统一的数据存储、分析和可视化平台；
- 两者结合，大幅提升故障排查和系统优化效率。

---

**相关链接推荐：**

- [OpenTelemetry 官网](https://opentelemetry.io/)
- [Grafana Cloud 免费注册](https://grafana.com/auth/sign-up/create-user)
- [分布式追踪实战 in .NET](https://www.milanjovanovic.tech/blog/introduction-to-distributed-tracing-with-opentelemetry-in-dotnet)
- [Pragmatic Clean Architecture](https://www.milanjovanovic.tech/pragmatic-clean-architecture)

---

🎯 **拥抱可观测性，让你的 .NET 服务从此不再“盲飞”！**
