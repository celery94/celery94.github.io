---
pubDatetime: 2026-02-12
title: "生产环境中监控 .NET 应用程序的完整指南"
description: "学习如何使用健康检查、Prometheus 和 Grafana 构建完整的 .NET 应用监控系统，包括活性检查、就绪检查、指标收集和可视化仪表板。"
tags: [".NET", "Monitoring", "Prometheus", "Grafana", "Docker"]
slug: "monitor-dotnet-applications-production"
source: "https://thecodeman.net/posts/how-to-monitor-dotnet-applications-in-production"
---

# 生产环境中监控 .NET 应用程序的完整指南

在生产环境中，应用程序很少会完全"崩溃"。更常见的情况是：API 依然运行但无法连接数据库、请求开始超时、后台任务静默停止但进程仍然存活、部署后延迟增加但几小时后才注意到。这就是为什么生产监控需要两个层次：健康检查和指标收集。

## 核心概念

### 健康检查与指标的区别

健康检查回答二元问题：
- 服务是否存活？
- 是否准备好接收流量？

指标回答行为问题：
- 每秒处理多少请求？
- 请求耗时多久？
- 处理了多少任务？
- 失败频率如何？

两者都不可或缺。

### Prometheus 和 Grafana 的角色

**Prometheus** 是时间序列指标系统，负责：
- 从应用程序拉取指标（pull 模式）
- 存储时间序列数据
- 提供 PromQL 查询语言

**Grafana** 是可视化层，负责：
- 连接 Prometheus 作为数据源
- 将指标转换为仪表板
- 触发告警

简单来说：Prometheus 存储数据，Grafana 让数据可见。

## 理解活性检查和就绪检查

生产环境中最常见的错误之一是只暴露单个健康端点，这会导致部署失败和不必要的重启。

### 活性检查（Liveness）

回答一个问题：进程是否运行？

**不应该**检查数据库、HTTP 调用或外部依赖。如果此检查失败，服务会被视为死亡。

### 就绪检查（Readiness）

回答不同的问题：服务是否准备好处理流量？

**必须**检查：
- 数据库
- 外部 API
- 消息队列

如果就绪检查失败，应停止流量，但不应杀死服务。

实现时需要暴露两个端点：
- `/health/live`
- `/health/ready`

## 实践示例：订单 API 的监控实现

### 安装必要的 NuGet 包

```bash
dotnet add package AspNetCore.HealthChecks.NpgSql
dotnet add package prometheus-net.AspNetCore
```

### 配置健康检查

在 `Program.cs` 中：

```csharp
var postgres = builder.Configuration.GetConnectionString("Postgres")
    ?? "Host=localhost;Port=5432;Database=orders;Username=postgres;Password=postgres";

builder.Services.AddHealthChecks()
    .AddCheck("self", () => HealthCheckResult.Healthy(), tags: new[] { "live" })
    .AddNpgSql(postgres, name: "postgres", tags: new[] { "ready" });
```

### 配置端点

```csharp
var app = builder.Build();

app.UseHttpMetrics();
app.MapMetrics("/metrics");

app.MapHealthChecks("/health/live", new HealthCheckOptions {
    Predicate = r => r.Tags.Contains("live")
});

app.MapHealthChecks("/health/ready", new HealthCheckOptions {
    Predicate = r => r.Tags.Contains("ready")
});
```

说明：
- `/health/live` 只检查应用本身
- `/health/ready` 检查 PostgreSQL 连接性
- `/metrics` 暴露 Prometheus 格式的指标
- `UseHttpMetrics()` 自动收集请求指标

## Worker 服务的自定义指标

对于后台服务，需要暴露 HTTP 端点来提供健康检查和指标。以下是完整配置：

```csharp
var builder = WebApplication.CreateBuilder(args);

var postgres = builder.Configuration.GetConnectionString("Postgres")
    ?? "Host=localhost;Port=5432;Database=appdb;Username=app;Password=app";

builder.Services.AddHealthChecks()
    .AddCheck("self", () => HealthCheckResult.Healthy(), tags: new[] { "live" })
    .AddNpgSql(postgres, name: "postgres", tags: ["ready"]);

builder.Services.AddHostedService<BillingJobRunner>();

var app = builder.Build();

app.UseHttpMetrics();
app.MapMetrics("/metrics");

app.MapHealthChecks("/health/live", new HealthCheckOptions {
    Predicate = r => r.Tags.Contains("live")
});

app.MapHealthChecks("/health/ready", new HealthCheckOptions {
    Predicate = r => r.Tags.Contains("ready")
});

app.Run();
```

### 添加自定义业务指标

```csharp
public static readonly Counter JobsProcessed = Metrics.CreateCounter(
    "billing_jobs_processed_total",
    "Total number of billing jobs processed.");

internal sealed class BillingJobRunner : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            JobsProcessed.Inc();
            await Task.Delay(TimeSpan.FromSeconds(2), stoppingToken);
        }
    }
}
```

这是监控生产环境后台处理的标准方式。

## Docker Compose 完整配置

创建 `docker-compose.yml`：

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: orders
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5433:5433"

  orders-api:
    build:
      context: .
      dockerfile: OrderManagement.Api/Dockerfile
    environment:
      ConnectionStrings__Postgres: Host=postgres;Port=5433;Database=orders;Username=postgres;Password=postgres
    ports:
      - "8082:8080"
    depends_on:
      - postgres

  billing-worker:
    build:
      context: .
      dockerfile: OrderManagement.Billing.Worker/Dockerfile
    environment:
      ConnectionStrings__Postgres: Host=postgres;Port=5433;Database=orders;Username=postgres;Password=postgres
    ports:
      - "8081:8080"
    depends_on:
      - postgres

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    depends_on:
      - orders-api
      - billing-worker

  grafana:
    image: grafana/grafana:latest
    volumes:
      - ./ops/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./ops/grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3003:3000"
    depends_on:
      - prometheus
```

启动顺序很重要：
1. Postgres 必须在就绪检查之前存在
2. 两个 .NET 应用在 Postgres 之后启动
3. Prometheus 在应用之后启动，因为需要抓取目标
4. Grafana 在 Prometheus 之后启动，因为需要数据源

## Prometheus 抓取配置

创建 `prometheus.yml`：

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: "orders-api"
    metrics_path: /metrics
    static_configs:
      - targets:
          - "orders-api:8080"

  - job_name: "billing-worker"
    metrics_path: /metrics
    static_configs:
      - targets:
          - "billing-worker:8080"
```

Prometheus 每 5 秒抓取一次，每个 .NET 服务成为独立的作业，目标使用 Docker 服务名（Docker Compose 提供 DNS）。

## Grafana 数据源自动配置

创建 `ops/grafana/provisioning/datasources/datasource.yml`：

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

这样 Grafana 启动时就已经连接好 Prometheus，避免"在我机器上能运行"的仪表板配置问题。

## 验证监控栈

启动完整系统：

```bash
docker compose up --build
```

### 检查健康端点

- Orders API 活性：`http://localhost:8082/health/live`
- Orders API 就绪：`http://localhost:8082/health/ready`
- Worker 就绪：`http://localhost:8081/health/ready`

### 检查指标端点

- Orders API: `http://localhost:8082/metrics`
- Worker: `http://localhost:8081/metrics`

查找以下指标：
- `http_requests_received_total`
- `billing_jobs_processed_total`

### 检查 Prometheus 目标

访问 `http://localhost:9090`，进入 Status → Targets，两个目标应显示为 UP。

## 创建 Grafana 仪表板

访问 `http://localhost:3000`（默认登录 `admin`/`admin`）。

### 配置数据源

1. 点击 Connections → Data sources
2. 选择 Prometheus
3. 验证 URL：`http://prometheus:9090`
4. 点击 Save & Test

### 创建第一个面板：HTTP 请求速率

1. 点击 Dashboards → New → New dashboard
2. 点击 Add visualization
3. 选择 Prometheus

在查询部分输入：

```promql
rate(http_requests_received_total{job="orders-api"}[1m])
```

这显示每秒的 HTTP 请求数。

### 添加自定义业务指标

对于自定义的 `billing_jobs_processed_total` 指标，使用：

```promql
rate(billing_jobs_processed_total[1m]) * 60
```

这显示每分钟处理的任务数，更易于非技术人员理解。

## 总结

监控不是事后添加的功能，而是一项技能。通过理解概念、端到端连接系统、了解生产环境中真正重要的内容来建立。

本文展示了：
- 活性和就绪健康检查的正确使用方式
- 如何从 .NET 暴露有意义的 `/metrics`
- Prometheus 如何抓取这些指标
- Grafana 如何将指标转换为答案
- 如何监控后台工作，不仅限于 HTTP 请求

这是真实 .NET 系统中的基准配置，既不是高级设置，也不是过度设计，只是正确的做法。

---

**参考资料：** 本文基于 [How to Monitor .NET Applications in Production with Health Checks, Prometheus, and Grafana](https://thecodeman.net/posts/how-to-monitor-dotnet-applications-in-production) 整理编写。
