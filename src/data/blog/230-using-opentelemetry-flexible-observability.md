---
pubDatetime: 2025-03-28 22:38:08
tags: ["Productivity", "Tools"]
slug: using-opentelemetry-flexible-observability
source: https://devblogs.microsoft.com/ise/using-opentelemetry-for-flexible-observability
title: 使用OpenTelemetry实现灵活可观测性：连接与断网环境中的系统监控
description: 探讨如何利用OpenTelemetry框架结合Azure Monitor和Grafana，创建适用于云端和边缘设备的灵活系统监控解决方案。
---

# 使用OpenTelemetry实现灵活可观测性：连接与断网环境中的系统监控 🌐

## 引言 🚀

在当今复杂的分布式系统中，可观测性是保持和提升系统性能与可靠性的关键。通过收集和分析指标、日志及跟踪数据，我们可以深入了解应用程序的内部状态。本篇文章将探讨如何结合 [OpenTelemetry](https://opentelemetry.io/) 与 [Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/overview) 和 [Grafana](https://grafana.com/oss/grafana/) 创建灵活的可观测性解决方案，适用于连接与断网环境。

---

## 背景：云端与边缘设备的挑战 🌩️

我们的团队最近开发了一套既运行于Azure云端，又部署在边缘设备（如[Azure Stack Edge](https://azure.microsoft.com/en-us/products/azure-stack/edge/)和[Intel NUC](https://en.wikipedia.org/wiki/Next_Unit_of_Computing)）上的系统。由于部分设备可能面临有限或无网络连接的情况（DDIL环境：拒绝、降级、间歇性和延迟），我们需要一个既能在云端运行，又能在断网情况下保持监控能力的混合解决方案。

此外，系统部署在Kubernetes集群中，因此任何可观测性工具也需适配这一环境。

---

## OpenTelemetry是什么？📊

[OpenTelemetry](https://opentelemetry.io/) 是一个开源可观测性框架，为收集指标、日志和跟踪数据提供标准化方法。它支持多种后端，包括 Azure Monitor，以及众多开源工具如 [Prometheus](https://grafana.com/oss/prometheus/)、[Loki](https://grafana.com/oss/loki/) 和 [Tempo](https://grafana.com/oss/tempo/)。

通过结合不同的可观测性工具与OpenTelemetry，我们能够创建一个灵活的混合解决方案，充分利用各个平台的优势。

---

## Azure Monitor与Grafana Stack对比 ⚖️

### Azure Monitor（Application Insights）

Azure Monitor 提供全面的监控解决方案，包括实时应用性能监控、遥测数据收集和分布式追踪等功能。它在云原生场景中表现优异，易于部署和扩展，非常适合集中化监控的连接系统。

**优点**：

- 集成便捷，适用于Azure云环境。
- 提供实时性能诊断和分布式追踪能力。

**缺点**：

- 对断网场景支持有限。
- 可视化选项较为基础。

### Grafana Stack

Grafana Stack 包括 Prometheus（指标收集）、Loki（日志管理）和 Tempo（分布式追踪），通过模块化设计提供高灵活性。在断网或间歇性连接场景下尤为出色，能够提供本地用户所需的可观测性能力。

**优点**：

- 高度灵活，支持本地化仪表板定制。
- 丰富的开源插件生态。

**缺点**：

- 需要更多运维管理工作。
- 架构复杂度较高。

---

## 两者结合：打造最佳解决方案 🛠️

为了兼顾两者优势，我们设计了一个混合可观测性架构。在系统联网时使用 Azure Application Insights 进行集中监控；在断网时使用 Grafana Stack 提供本地化监控能力。

这样既确保了云端系统的实时性能监控，也保证了边缘设备即使在网络不稳定时仍能持续可观测性。以下是架构配置示例：

---

## 配置示例 🔧

下图展示了如何配置数据源与OpenTelemetry Collector，并将数据导出到相关工具：

![OpenTelemetry Collector配置图](https://devblogs.microsoft.com/ise/wp-content/uploads/sites/55/2025/03/opentelemetry-configuration.png)

我们通过Helm模板部署Kubernetes清单，并使用[OpenTelemetry Helm Chart](https://opentelemetry.io/docs/kubernetes/helm)配置如下：

```yaml
exporters:
  otlp:
    endpoint: 0.0.0.0:4317
  azuremonitor:
    connection_string: YOUR_APP_INSIGHTS_CONNECTION_STRING
  prometheus/metrics:
    endpoint: "0.0.0.0:8889"
  loki:
    endpoint: YOUR_LOKI_ENDPOINT
    default_labels_enabled:
      exporter: true
      job: true
```

在代码层面，我们仅需使用OpenTelemetry SDK即可轻松生成遥测数据：

```csharp
using OpenTelemetry;
using OpenTelemetry.Trace;
using OpenTelemetry.Metrics;
using OpenTelemetry.Logs;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource.AddService("MyApp"))
    .WithTracing(tracing => tracing.AddOtlpExporter(options => options.Endpoint = new Uri("https://otel-endpoint")))
    .WithMetrics(metrics => metrics.AddOtlpExporter(options => options.Endpoint = new Uri("https://otel-endpoint")))
    .WithLogging(logging => logging.AddOpenTelemetry(options => options.AddOtlpExporter(exporterOptions => exporterOptions.Endpoint = new Uri("https://otel-endpoint"))));

var app = builder.Build();
app.Run();
```

---

## 可视化仪表板 📈

### Azure Monitor Workbooks

![Azure Workbook示例](https://devblogs.microsoft.com/ise/wp-content/uploads/sites/55/2025/03/azure-workbook.png)

**特点**：

- 可扩展性强，可处理大规模数据查询。
- 基于KQL语言，可实现复杂查询。
- 自定义选项较少，视觉效果偏基础。

---

### Grafana Dashboards

![Grafana Kubernetes监控仪表板](https://devblogs.microsoft.com/ise/wp-content/uploads/sites/55/2025/03/grafana-dashboard.png)

**特点**：

- 丰富的开源仪表板资源，易于复用。
- 灵活直观，支持复杂可视化。
- 支持JSON配置文件进行版本控制。

---

## 总结 🎯

通过整合 OpenTelemetry，我们成功解耦了代码与可观测性工具，为混合系统提供了灵活解决方案。在边缘场景中，Grafana Stack的强大灵活性为本地监控提供了保障；而在云端场景中，Azure Application Insights则凭借其便捷部署与扩展能力表现出色。

最终，这种结合实现了全面而强大的可观测性，使系统能够适应多种网络环境，同时保持性能与可靠性。

✨ 技术驱动创新，让监控无处不在！
