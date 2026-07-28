---
pubDatetime: 2026-07-28T07:48:50+08:00
title: "ASP.NET Core 健康检查完全指南：从 Hello World 到生产环境"
description: "从零开始为 ASP.NET Core (.NET 10) 添加健康检查：数据库、Redis、自定义检查、liveness/readiness 探针拆分、探针成本预算、优雅排水，以及 Kubernetes 部署接线。附 Health Checks UI 的版本坑和 CVE 注意事项。"
tags: ["health-checks", "aspnet-core", "dotnet", "kubernetes", "observability", "ef-core", "redis", "tutorial"]
slug: "health-checks-aspnet-core-dotnet-10"
ogImage: "../../assets/972/01-cover.png"
source: "https://codewithmukesh.com/blog/health-checks-in-aspnet-core/"
---

ASP.NET Core 里的健康检查就是几行 HTTP 端点，告诉外部系统你的应用和它依赖的数据库、缓存、下游 API 是否真的能干活。用 `builder.Services.AddHealthChecks()` 注册，`app.MapHealthChecks("/health")` 暴露出来。在 .NET 10 里，核心 API 已经内置在 `Microsoft.AspNetCore.App` 共享框架里，不需要额外装任何 NuGet 包。

但一个只返回 `Healthy` 的端点——进程还在跑，数据库已经挂了——比没有健康检查更危险。它会让负载均衡器和 Kubernetes 继续往一个坏掉的 Pod 里灌流量。所以这篇文章不止于那两行代码：它会覆盖真实数据库和 Redis 检查、自定义 `IHealthCheck` 逻辑、结构化的 JSON 响应、实时仪表盘，以及大多数教程跳过但生产中一定会撞上的三件事——**liveness/readiness 拆分、探针的真实成本，还有 Pod 关闭前的优雅排水**。

原作者 Mukesh Murugan 在 .NET 10 上用 minimal API + PostgreSQL 搭了完整示例，过程中还发现 Health Checks UI 包传递依赖了一个中等严重度的 CVE。完整可运行源码在 GitHub 上。

## 健康检查是什么

健康检查是 ASP.NET Core 内置的诊断功能，把应用状态以一种简单、机器可读的格式暴露出来。每个检查返回三种状态之一：

- `Healthy`：一切正常
- `Degraded`：能工作，但某个组件变慢了或部分失败
- `Unhealthy`：挂了，不要再给我发流量

所有已注册检查的状态会被聚合为一个整体结果，然后通过 HTTP 端点（通常是 `/health`）暴露，让外部系统不需要知道内部细节就能轮询。三个消费者关心这个端点：

- **负载均衡器**：把不健康的实例从轮转中踢掉
- **容器编排器（Kubernetes）**：根据返回值重启或暂停 Pod
- **可用性监控**（Better Stack、UptimeRobot、Pingdom）：状态翻转时告警

核心契约很简单：`200 OK` 表示「可以给我派活」，`503 Service Unavailable` 表示「在我恢复之前别碰我」。这篇文章做的所有配置，都是为了让这个信号诚实。

## 前置条件

- .NET 10 SDK
- IDE：Visual Studio 2026、Rider，或 VS Code + C# Dev Kit
- Docker Desktop（PostgreSQL 和 Redis 示例需要）

本指南使用 minimal API 和 `Program.cs` 托管模型。如果你还在用 `Startup.cs`，注册调用完全一样，只是分散在 `ConfigureServices` 和 `Configure` 里。

## 最基础的健康检查

新建一个 Web API 项目，打开 `Program.cs`，加两行代码：

```bash
dotnet new webapi -n HealthChecks.Api
```

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHealthChecks();

var app = builder.Build();

app.MapHealthChecks("/health");

app.Run();
```

`AddHealthChecks()` 注册健康检查服务，返回一个 `IHealthChecksBuilder` 用来链式添加具体检查。`MapHealthChecks("/health")` 把端点接入路由管线。跑起来之后用 curl 测试：

```bash
curl https://localhost:7042/health
```

返回：

```
Healthy
```

端口号 `7042` 替换成你项目里 launchSettings 分配的 HTTPS 端口——.NET 10 会随机生成。

这个端点返回纯文本 `Healthy`，状态码 `200`。没有注册任何检查时，「健康」只代表进程还活着、能处理请求。对 liveness 信号来说够用了，但完全不知道依赖是否正常。先把响应改成结构化的 JSON，再逐步加真正的检查。

> **已经在用 .NET Aspire？** 生成的 `ServiceDefaults` 项目已经帮你做了这件事：`AddDefaultHealthChecks()` 注册了一个 tagged `live` 的简单自检，`MapDefaultEndpoints()` 映射了 `/health`（所有检查）和 `/alive`（只跑 `live` 标签）。Aspire 在非 Development 环境下默认禁用了这两个端点，所以你还是得自己决定怎么暴露到生产环境。下面的所有内容同样适用——你只是在 Aspire 已经建好的 builder 上继续加检查。

## 返回结构化 JSON

默认纯文本 `Healthy` 看不出哪个检查挂了。要返回结构化 JSON——每个组件的状态、描述和耗时——给 `MapHealthChecks` 传一个带自定义 `ResponseWriter` 的 `HealthCheckOptions`：

```csharp
using System.Text.Json;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.Extensions.Diagnostics.HealthChecks;

app.MapHealthChecks("/health", new HealthCheckOptions
{
    ResponseWriter = async (context, report) =>
    {
        context.Response.ContentType = "application/json";

        var response = new
        {
            status = report.Status.ToString(),
            totalDurationMs = Math.Round(report.TotalDuration.TotalMilliseconds, 2),
            checks = report.Entries.Select(entry => new
            {
                name = entry.Key,
                status = entry.Value.Status.ToString(),
                description = entry.Value.Description,
                durationMs = Math.Round(entry.Value.Duration.TotalMilliseconds, 2),
                error = entry.Value.Exception?.Message
            })
        };

        var json = JsonSerializer.Serialize(response,
            new JsonSerializerOptions { WriteIndented = true });

        await context.Response.WriteAsync(json);
    }
});
```

`report.Entries` 是一个字典，按名称键控了每个已注册的检查。每个条目携带自己的状态、描述、耗时和可能抛出的异常。注册了数据库检查之后，返回大概是这样的：

```json
{
  "status": "Healthy",
  "totalDurationMs": 42.18,
  "checks": [
    {
      "name": "postgres",
      "status": "Healthy",
      "description": "Database reachable",
      "durationMs": 41.02,
      "error": null
    }
  ]
}
```

凌晨三点收到告警时，「Redis 检查在 5002ms 超时」和「有东西挂了」的区别，就靠这段 JSON。

## 数据库健康检查（EF Core）

安装 Microsoft 官方包并链式调用 `AddDbContextCheck`：

```bash
dotnet add package Microsoft.Extensions.Diagnostics.HealthChecks.EntityFrameworkCore --version 10.0.0
```

```csharp
builder.Services.AddHealthChecks()
    .AddDbContextCheck<AppDbContext>(
        name: "postgres",
        tags: ["ready"]);
```

`AddDbContextCheck<T>` 调用 `DbContext` 的 `CanConnectAsync()`，这个方法是轻量级连接测试，不会真的拉数据行。`name` 会出现在 JSON 里，`tags` 对后续的 liveness/readiness 拆分很重要。

有一个细节要知道：`CanConnectAsync()` 只确认数据库接受连接，不验证 schema 是否迁移成功、某个表是否存在。如果你想要更严格的检查——执行一条真实 SQL——可以用社区 PostgreSQL 包：

```bash
dotnet add package AspNetCore.HealthChecks.NpgSql --version 9.0.0
```

```csharp
builder.Services.AddHealthChecks()
    .AddNpgSql(
        connectionString: builder.Configuration.GetConnectionString("Postgres")!,
        healthQuery: "SELECT 1;",
        name: "postgres",
        tags: ["ready"]);
```

`AddNpgSql` 打开原始连接执行你指定的 `healthQuery`，不依赖 EF Core。如果你想让健康检查验证的是迁移工具或后台 worker 用的连接串、而不是应用的 DbContext，这个方式更合适。

## Redis 健康检查

装社区 Redis 包并注册：

```bash
dotnet add package AspNetCore.HealthChecks.Redis --version 9.0.0
```

```csharp
builder.Services.AddHealthChecks()
    .AddNpgSql(/* ... */)
    .AddRedis(
        builder.Configuration.GetConnectionString("Redis")!,
        name: "redis",
        tags: ["ready"]);
```

`AddRedis` 连接后发一个 `PING` 命令。社区包（以前叫 Xabaril，现在在 `AspNetCore.HealthChecks.*` 家族下）覆盖了大量依赖：SQL Server、MySQL、MongoDB、RabbitMQ、Kafka、Azure Blob、AWS S3 等等，注册模式都是 `Add{依赖名}` + `name` + `tags`。

## 检查外部 URL / 下游服务

要检查你的应用依赖的下游 API 是否可达，用 URL 检查：

```bash
dotnet add package AspNetCore.HealthChecks.Uris --version 9.0.0
```

```csharp
builder.Services.AddHealthChecks()
    .AddUrlGroup(
        new Uri("https://payments.internal/health/live"),
        name: "payments-api",
        tags: ["ready"]);
```

指向对方实际发布出来的健康端点，而不是营销首页或会产生计费调用的 API 路由。

有一个陷阱：把第三方 URL 放进 readiness 探针，等于把你的可用性和对方的可用性绑定了。如果那个服务短暂抖动 30 秒、你的 readiness 标记 Pod 为不健康、编排器把它从轮转中摘掉——但实际上你自己的服务完全正常。把外部 URL 检查留给对业务来说必须保证可达的关键依赖，其他的尽量用重试和熔断来处理，不要放进探针。

## 自定义健康检查

内置检查覆盖了基础设施层面。对于业务逻辑——队列深度、feature flag 服务、磁盘空间、license 过期时间——实现 `IHealthCheck` 接口，方法只有一个。返回类型正是三状态模型发挥价值的地方。

下面是一个自定义检查，测量下游依赖延迟，慢了就报 `Degraded` 而不是直接报 `Unhealthy`：

```csharp
using System.Diagnostics;
using Microsoft.Extensions.Diagnostics.HealthChecks;

public sealed class PaymentGatewayHealthCheck(
    IHttpClientFactory httpClientFactory)
    : IHealthCheck
{
    private const int DegradedThresholdMs = 500;

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        var client = httpClientFactory.CreateClient("PaymentGateway");
        var sw = Stopwatch.StartNew();

        try
        {
            var response = await client.GetAsync(
                "/health/live", cancellationToken);
            sw.Stop();

            if (!response.IsSuccessStatusCode)
            {
                return HealthCheckResult.Unhealthy(
                    $"Gateway returned {response.StatusCode}",
                    data: new Dictionary<string, object>
                    {
                        ["latencyMs"] = sw.ElapsedMilliseconds
                    });
            }

            if (sw.ElapsedMilliseconds > DegradedThresholdMs)
            {
                return HealthCheckResult.Degraded(
                    $"Gateway responding slowly",
                    data: new Dictionary<string, object>
                    {
                        ["latencyMs"] = sw.ElapsedMilliseconds
                    });
            }

            return HealthCheckResult.Healthy(
                "Gateway reachable",
                data: new Dictionary<string, object>
                {
                    ["latencyMs"] = sw.ElapsedMilliseconds
                });
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            sw.Stop();
            return HealthCheckResult.Unhealthy(
                "Gateway unreachable", ex);
        }
    }
}
```

注册：

```csharp
builder.Services.AddHealthChecks()
    .AddCheck<PaymentGatewayHealthCheck>(
        name: "payment-gateway",
        tags: ["ready"]);
```

两个关键设计：第一，延迟高时返回 `Degraded` 而不是 `Unhealthy`，慢速网关会在仪表盘上显示出来，但不会把 Pod 踢出服务；第二，通过 `cancellationToken` 响应取消操作，防止一个挂起的依赖把整个健康端点冻住——`AddCheck<T>` 默认的超时可以在注册时配置。

## Liveness vs Readiness vs Startup：探针拆分

这一段是把「能跑的健康检查」和「生产可用的健康检查」区分开的关键。没有「单一正确」的健康端点，有三个，而且把检查放错探针是一个极其常见的错误。

三种探针回答三个不同问题：

- **Liveness**：「进程还活着吗，是否死锁需要重启？」不要检查任何外部依赖。失败时编排器杀掉并重建 Pod。
- **Readiness**：「这个实例现在能处理请求吗？」检查数据库、缓存、下游 API。失败时编排器暂停转发流量，但 Pod 继续运行。
- **Startup**：「启动慢的应用初始化完成了吗？」只在启动时运行一次，在它通过之前其他探针不会启动。

最常见的错误：把数据库检查放进 liveness 探针。表面逻辑看起来没错——数据库挂了应用就坏了，那就重启。但数据库短暂故障转移——几十秒就能自动恢复的那种——会让所有 Pod 同时报 liveness 失败，编排器把每个副本都杀掉重启。重启一个进程能修好死锁，但永远修不好下游故障。结果是把几十秒的数据库抖动放大成集群级的重启风暴。

**规则很简单**：liveness 只查自己的进程；readiness 查依赖。用 tags 实现拆分：

```csharp
using Microsoft.AspNetCore.Diagnostics.HealthChecks;

// Readiness：只跑 tagged "ready" 的检查（数据库、Redis、外部 API）
app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready")
});

// Liveness：不跑任何检查。返回 200 只代表进程能处理请求
app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    Predicate = _ => false
});
```

`Predicate = _ => false` 是关键——零检查，所以 liveness 端点只要进程能响应就返回 `200`，这正是 liveness 探针应该测的东西。readiness 端点只跑你打了 `ready` 标签的检查。两个端点，一组注册，没有额外维护成本。

**实践建议**：默认把所有依赖检查放在 readiness，liveness 保持空的，除非你真的在检测某个具体死锁。那种「数据库挂了就让 liveness 也挂」的直觉看起来很保护应用，但在任何多副本系统中是主动制造危险。liveness 里唯一该出现的检查是检测进程本身是否进入不可恢复状态的逻辑——比如线程池饥饿、死锁检测器信号等。

## Health Checks UI 仪表盘

JSON 端点是给机器读的。给人类一个能轮询端点、显示历史的仪表盘，装三个包：

```bash
dotnet add package AspNetCore.HealthChecks.UI --version 9.0.0
dotnet add package AspNetCore.HealthChecks.UI.Client --version 9.0.0
dotnet add package AspNetCore.HealthChecks.UI.InMemory.Storage --version 9.0.0
```

先把 readiness 端点改成 UI 兼容的 JSON 格式：

```csharp
using HealthChecks.UI.Client;

app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready"),
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse
});
```

再注册并映射 UI：

```csharp
builder.Services
    .AddHealthChecksUI(options =>
    {
        options.AddHealthCheckEndpoint("API", "/health/ready");
        options.SetEvaluationTimeInSeconds(15);
    })
    .AddInMemoryStorage();

// build 之后
app.MapHealthChecksUI(options => options.UIPath = "/health-ui");
```

访问 `/health-ui` 就能看到一个每 15 秒轮询并颜色编码各组件的仪表盘。`AddInMemoryStorage` 把历史留在内存里，单实例或本地开发足够用。多实例持久化可以换成 SQL Server 或 PostgreSQL 存储提供程序。

### 两个必须知道的坑

原作者跑漏洞扫描时发现了意料之外的问题：

```bash
dotnet list package --vulnerable --include-transitive
```

```
Project `HealthChecks.Api` has the following vulnerable packages
   [net10.0]:
   Transitive Package    Resolved   Severity   Advisory URL
   > KubernetesClient    15.0.1     Moderate   https://github.com/advisories/GHSA-w7r3-mgwf-4mqq
```

`AspNetCore.HealthChecks.UI` 9.0.0 依赖了 `KubernetesClient` 15.0.1——它内置了一个大多数人都不会启用的 Kubernetes 服务发现功能——而这个版本有一个中等严重度的安全公告。整个健康检查链路里没有任何其他包拖进这个依赖。

更隐蔽的问题是版本冲突。把 UI 加到一个用 EF Core 10 的应用里，编译通过，启动直接崩：

```
System.MissingMethodException: Method not found:
'System.String Microsoft.EntityFrameworkCore.Diagnostics
.AbstractionsStrings.ArgumentIsEmpty(System.Object)'.
```

原因：`AspNetCore.HealthChecks.UI.InMemory.Storage` 9.0.0 锁定了 `Microsoft.EntityFrameworkCore.InMemory` 8.0.11，而 Npgsql 和 Microsoft 健康检查包已经拖进了 EF Core 10。编译器发现不了——这是运行时绑定失败，所以构建和 CI 全绿，直到容器起不来。

修复方案是对 InMemory 提供程序加一个显式引用，把它拉到和核心库同一个主版本：

```xml
<PackageReference Include="Microsoft.EntityFrameworkCore.InMemory" Version="10.0.0" />
```

整个 `AspNetCore.HealthChecks.*` 社区包家族还有一个通用注意事项：目前最新稳定版还是 9.0.0，目标框架是 `net8.0` 而不是 `net10.0`。它会把 `Microsoft.Extensions.Diagnostics.HealthChecks` 8.0.11 拖进来，和你共享框架里已有的 10.x 程序集并存。

**实践建议**：有 Microsoft 官方包的地方尽量用官方的；把 UI 看作开发便利工具而不是一定要部署到生产镜像里的东西。一个需要手动 pin 版本才能启动、还带着有 CVE 的 Kubernetes 客户端的仪表盘，不太适合出现在生产镜像里。生产环境用外部监控系统消费 JSON 端点更安全。

## 接入 Kubernetes

有了 `/health/live` 和 `/health/ready` 之后，Kubernetes 直接通过它的 liveness、readiness、startup 探针来消费：

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  periodSeconds: 10
  failureThreshold: 3

startupProbe:
  httpGet:
    path: /health/live
    port: 8080
  failureThreshold: 30
  periodSeconds: 10
```

注意这个配置强制执行的契约：liveness 探针指向 `/health/live`——不跑任何依赖检查，所以数据库挂掉永远不会触发重启风暴。readiness 探针指向 `/health/ready`——只跑依赖检查，所以依赖故障只会从 Service 负载均衡器里暂时摘掉 Pod。startup 探针也用 `/health/live`，因为启动阶段我们只关心进程是否已经能响应 HTTP。

如果你用的是 Docker Compose 或 App Runner 而不是 Kubernetes，同样的端点直接填进它们的 healthcheck 指令——ASP.NET Core 这边不需要任何修改。

## Pod 关闭前的优雅排水

几乎每个健康检查教程都留白的部分：Kubernetes 终止 Pod 时，两件事是**并行**发生的，不是串行——kubelet 给进程发 `SIGTERM`，同时控制面把 Pod 从 Service 端点列表里删掉。这个删除需要传播到每个 kube-proxy，有一到两秒的延迟。在这段间隙里，负载均衡器还在往一个正在关闭的 Pod 发请求——这就是每次部署都出 `502` 的根源。

修复方法：让 readiness 在进程开始拆资源**之前**就报失败，这样负载均衡器先停止路由，应用仍然能处理正在飞行中的请求。Microsoft 有一个专门为此设计的检查：

```bash
dotnet add package Microsoft.Extensions.Diagnostics.HealthChecks.Common --version 10.8.0
```

```csharp
builder.Services.AddHealthChecks()
    .AddApplicationLifecycleHealthCheck(tags: ["ready"]);
```

`AddApplicationLifecycleHealthCheck` 挂载 `IHostApplicationLifetime`：在 `ApplicationStarted` 触发之前报 `Unhealthy`，`ApplicationStopping` 触发的那一刻立刻翻回 `Unhealthy`。打了 `ready` 标签后，readiness 端点会在 shutdown 开始的第一时间返回 `503`。

配合 `preStop` hook，让 Pod 多活几秒等负载均衡器感知到变化：

```yaml
lifecycle:
  preStop:
    exec:
      command: ["sleep", "10"]

terminationGracePeriodSeconds: 30
```

完整序列变成：preStop 触发 → readiness 返回 503 → 端点控制器把 Pod 从轮转摘掉 → 飞行中的请求完成 → `SIGTERM` 到达。10 秒的 sleep，就是干净滚动发布和一墙 502 之间的全部距离。

## 健康检查的实际成本

健康检查结果从不缓存。每次请求到健康端点都从零开始同步执行所有匹配的检查。这是关于健康检查最贵的事实，但几乎没人算过这笔账。

按正常部署算笔账：`periodSeconds: 10` 的 readiness 探针，每 Pod 每分钟 6 次探测。4 个副本就是每分钟 24 次。每个 Pod 跑 4 个依赖检查——Postgres、Redis、支付网关、生命周期——就是每分钟 96 次依赖往返，每天约 **138,000 次**，在完全空闲没人用的情况下。你的数据库在为一个空应用扛每秒 1.6 次的查询。

三个优化杠杆，按优先级排序：

### 1. ShortCircuit：短路中间件管线

`MapHealthChecks` 返回 endpoint builder，可以链式调用 `.ShortCircuit()`。请求跳过管线其余部分——认证、日志、限流等——直奔健康检查：

```csharp
app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    Predicate = _ => false
}).ShortCircuit();
```

### 2. 输出缓存：减少依赖往返

默认情况下健康检查中间件写入的 `Cache-Control`、`Expires`、`Pragma` 头禁止缓存。设 `AllowCachingResponses = true` 叠加输出缓存后，5 秒内的一波探测只花一次真实数据库往返：

```csharp
builder.Services.AddOutputCache();

app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready"),
    AllowCachingResponses = true
}).CacheOutput(policy => policy.Expire(TimeSpan.FromSeconds(5)));
```

缓存窗口必须远小于 `periodSeconds × failureThreshold`，否则会延迟对真实故障的感知。5 秒缓存配 10 秒探测间隔是安全的；60 秒就不行。

### 3. Push 代替 Poll

监控场景（相对于编排）可以实现 `IHealthCheckPublisher`。运行时在定时器上执行检查，推送报告给你，不需要任何人打 HTTP 端点：

```csharp
builder.Services.Configure<HealthCheckPublisherOptions>(options =>
{
    options.Delay = TimeSpan.FromSeconds(5);
    options.Period = TimeSpan.FromSeconds(30);
    options.Predicate = check => check.Tags.Contains("ready");
});

builder.Services.AddSingleton<IHealthCheckPublisher, SlackHealthCheckPublisher>();
```

默认 5 秒延迟、30 秒周期。整个应用只有一个定时器，不管有多少系统想知道状态。

**实践建议**：第一天就给所有健康端点加 `.ShortCircuit()`——免费、且能防止探针噪音灌满日志。一旦依赖检查碰了按量计费或慢速服务，就加输出缓存。Publisher 只在需要把状态推到编排器看不了的地方时才用——比如 Slack、PagerDuty 或你自己的告警管线。

## 安全与调优

四个生产环境里经常咬人的细节：

- **不要把详细 JSON 暴露到公网**。组件列表会泄露你的基础设施结构（你在用 Redis、Postgres、Stripe）。`/health/live` 保持公开给探针用，详细端点和 UI 加 `RequireAuthorization` 或绑定到内网。
- **给每个检查设超时**。没有超时的检查可能挂起并阻塞整个报告。自定义检查模式通过 `cancellationToken` 响应取消；内置检查接受 `timeout` 参数。
- **决定 `Degraded` 对你的编排器意味着什么**。默认 `Degraded` 返回 `200`，所以降级的 Pod 继续接流量——通常是你要的效果。如果想把降级 Pod 也摘掉，用 `ResultStatusCodes` 重映射。
- **连接串走配置，不要硬编码**。上面所有检查都从 `IConfiguration` 读取，所以同一套端点在不同环境里自动验证对应的依赖。

## 关键要点

- .NET 10 上基础健康检查不需要 NuGet 包：`AddHealthChecks()` + `MapHealthChecks("/health")` 即可开始
- 用自定义 `ResponseWriter` 返回 JSON，让失败的检查自报名字而不是隐藏在一个泛化的 `Unhealthy` 后面
- 用 tags 拆分 liveness 和 readiness：liveness 只查自己的进程，readiness 查依赖。重启修得了死锁，修不了下游故障
- 把数据库检查放 liveness 探针会把短暂故障放大成跨越所有副本的级联重启——它属于 readiness
- 健康检查结果不缓存。4 副本 × 10 秒间隔 × 4 检查 = 每天约 138,000 次依赖往返——用 `ShortCircuit()`、短窗口输出缓存和 publisher 来削减
- 把 `AddApplicationLifecycleHealthCheck` 标成 `ready`，让 shutdown 开始瞬间 readiness 就报失败；配合 `preStop` sleep 消灭每次部署的 502
- 社区 `AspNetCore.HealthChecks.*` 包仍是 9.0.0、目标 `net8.0`，UI 包拖进了一个含中等严重度 CVE 的 KubernetesClient 版本
- 在 EF Core 10 上 Health Checks UI 编译通过但启动时 `MissingMethodException` 崩溃：需要手动 pin `Microsoft.EntityFrameworkCore.InMemory` 到 10.0.0

## FAQ

**健康检查会缓存吗？**
不会。每次请求都重新执行所有匹配的检查，裸打真实数据库和缓存。用 `ShortCircuit()` 和输出缓存来削减成本。

**liveness 和 readiness 的本质区别是什么？**
Liveness 回答「进程是否活着」，失败应触发重启，不应检查外部依赖。Readiness 回答「现在能不能接流量」，应检查数据库、缓存等依赖。readiness 失败时编排器暂停流量但保持 Pod 运行。

**数据库检查放 liveness 有什么问题？**
重启 Pod 永远修不好下游数据库。短期数据库故障会同时让所有 Pod 报 liveness 失败，触发级联重启。依赖检查放 readiness：失败只暂停流量，等依赖恢复即可。

**Kubernetes 的 502 错误怎么来的？**
Kubernetes 发 `SIGTERM` 给 Pod 和从 Service 端点删 Pod 是并行的，负载均衡器有一两秒还在往关停中的 Pod 发请求。注册 `AddApplicationLifecycleHealthCheck` 标 `ready`，加 `preStop` sleep 消化掉这个延迟。

**`Healthy`、`Degraded`、`Unhealthy` 的区别？**
`Healthy` 表示检查完全通过；`Degraded` 表示能工作但有点慢或部分失败；`Unhealthy` 表示检查失败、组件坏了。默认 `Healthy` 和 `Degraded` 都返回 `200 OK`，`Unhealthy` 返回 `503`，可以改映射。

**怎么写自定义健康检查？**
实现 `IHealthCheck` 接口的 `CheckHealthAsync` 方法，返回 `HealthCheckResult.Healthy` / `Degraded` / `Unhealthy`。用 `AddCheck<T>` 注册，给 name 和 tags。务必尊重 `cancellationToken`，防止挂起的依赖冻住端点。

**`AddDbContextCheck` 会跑真实 SQL 吗？**
不会。它调用 `CanConnectAsync()`，只确认数据库接受连接，不验证迁移状态或表是否存在。要跑真实 SQL 用 `AspNetCore.HealthChecks.NpgSql` 等社区包并自定义 `healthQuery`。

**健康端点应该公开吗？**
`/health/live` 保持公开（不泄露信息），详细 JSON 和 UI 加 `RequireAuthorization` 或绑定内网。

## 常见问题排查

- **端点返回 404**：`AddHealthChecks()` 调了但忘了 `MapHealthChecks("/health")`，或者映射放在了终止性中间件后面。确保映射在 endpoint routing 阶段执行。
- **详细 JSON 是空的**：`Predicate` 把所有检查都过滤掉了。`Predicate = _ => false` 是给 liveness 用的（故意不跑检查），详细端点要么不设 predicate，要么用匹配 tags 的条件。
- **Readiness 端点卡住**：某个检查没有超时、阻塞了。给内置检查传 timeout 参数，自定义检查里尊重 `CancellationToken`。
- **加了 Health Checks UI 后启动 `MissingMethodException`**：UI 存储包锁定了 EF Core InMemory 8.0.11，和应用的 EF Core 10 冲突。加显式 `PackageReference` 到 `Microsoft.EntityFrameworkCore.InMemory` 10.0.0。
- **Health Checks UI 显示「Discovered」但没有数据**：UI 端点和被检查端点必须使用同一套 UI 响应格式。给 UI 轮询的端点设 `ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse`。
- **Kubernetes 反复重启健康的 Pod**：liveness 探针指向了一个跑依赖检查的端点。把 liveness 指向 `/health/live`（零检查），依赖检查放 readiness。
- **探测请求灌满日志和数据库**：同一个根因——每次请求都跑检查而且经过完整的中间件管线。给健康端点加 `ShortCircuit()` 跳过日志和认证中间件；给 readiness 端点加短窗口输出缓存。
- **每次部署出一波 502**：readiness 在 Pod 关停时还在返回 200。注册 `AddApplicationLifecycleHealthCheck` 标 `ready`，加 `preStop` sleep 让负载均衡器先感知到故障。

## 参考

- [Health Checks in ASP.NET Core: A Complete Guide (.NET 10)](https://codewithmukesh.com/blog/health-checks-in-aspnet-core/) — 原文
- [ASP.NET Core 官方健康检查文档](https://learn.microsoft.com/aspnet/core/host-and-deploy/health-checks)
- [AspNetCore.HealthChecks 社区包](https://github.com/Xabaril/AspNetCore.Diagnostics.HealthChecks)
- [Kubernetes 探针文档](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
