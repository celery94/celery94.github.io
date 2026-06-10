---
pubDatetime: 2026-06-10T08:44:00+08:00
title: "ASP.NET Core API 部署指南"
description: "部署 ASP.NET Core Web API 时，先把 Docker 镜像做对，再补上 Compose 本地依赖、健康检查、环境配置、Azure App Service 或 Container Apps、Key Vault 密钥和启动性能优化。"
tags: ["ASP.NET Core", "Docker", "Azure", "Web API", "DevOps"]
slug: "aspnet-core-api-deployment-guide"
ogImage: "../../assets/867/01-cover.png"
source: "https://www.devleader.ca/2026/06/09/deploying-aspnet-core-web-api-to-azure-and-docker"
---

![ASP.NET Core Web API 从 Docker 镜像到 Azure 部署的生产检查路径](../../assets/867/01-cover.png)

ASP.NET Core Web API 部署到生产环境时，真正难的不是“能不能跑起来”，而是能不能用可重复、可观测、可回滚的方式稳定运行。

Dev Leader 这篇文章把路径拆得很实用：先用 Docker 做出正确的运行镜像，再用 Docker Compose 验证本地依赖，补上健康检查和环境配置，最后根据团队运维模型选择 Azure App Service 或 Azure Container Apps。密钥、迁移、日志和启动性能也要在上线前想清楚。

下面按一条生产部署清单重写。你可以把它当成 ASP.NET Core API 上线前的检查顺序。

## 先选基础镜像

Microsoft 在 `mcr.microsoft.com` 发布官方 .NET 容器镜像。部署 ASP.NET Core API 时，最常用的是两类：

- `mcr.microsoft.com/dotnet/sdk:10.0`：包含完整 SDK、编译器、CLI、NuGet，适合构建阶段。
- `mcr.microsoft.com/dotnet/aspnet:10.0`：只包含 ASP.NET Core runtime，适合生产运行阶段。

不要把 SDK 镜像直接发到生产。它大、攻击面更宽，也带着生产环境不需要的工具链。正确做法是多阶段构建：用 SDK 镜像 build/publish，再把发布产物复制到 runtime 镜像。

如果特别在意镜像大小，可以考虑 Alpine 变体，比如 `mcr.microsoft.com/dotnet/aspnet:10.0-alpine`。它通常更小，但 Alpine 使用 `musl libc`，不是默认 Debian 镜像里的 `glibc`。如果项目依赖 native library，先完整测试再决定是否用 Alpine。

## 写好多阶段 Dockerfile

多阶段 Dockerfile 是容器化 .NET API 的基本盘。原文给出的核心结构是：先复制 `.csproj` 并 restore，让 Docker layer cache 发挥作用；再复制完整源码并 publish；最后只把 `/app/publish` 复制到 runtime 镜像。

```dockerfile
# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY ["src/MyApi/MyApi.csproj", "src/MyApi/"]
RUN dotnet restore "src/MyApi/MyApi.csproj"

COPY . .

RUN dotnet publish "src/MyApi/MyApi.csproj" \
    -c Release \
    -o /app/publish \
    --no-restore

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app

RUN addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --ingroup appgroup appuser

COPY --from=build /app/publish .

USER appuser

EXPOSE 8080

ENTRYPOINT ["dotnet", "MyApi.dll"]
```

这里有三个上线前要确认的点：

- `.csproj` 先复制，是为了缓存 `dotnet restore`，加快增量构建。
- 生产镜像使用 `aspnet:10.0`，不是 `sdk:10.0`。
- 运行用户是非 root，降低容器被打穿后的权限风险。

还有一个容易漏的变化：.NET 8 以后 ASP.NET Core 默认监听 `8080`，这也更适合非 root 容器。你的 `EXPOSE`、Docker Compose、负载均衡和 Azure target port 都要对齐到 `8080`。

## 本地用 Compose 验证

Docker Compose 适合在本地把 API 和依赖一起拉起来，比如 SQL Server、Redis、消息队列等。原文示例里 API 依赖 SQL Server，并通过 `depends_on.condition: service_healthy` 等数据库 ready 后再启动 API。

```yaml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - ConnectionStrings__DefaultConnection=Server=db;Database=MyApiDb;User Id=sa;Password=YourStrong!Passw0rd;TrustServerCertificate=True;
    depends_on:
      db:
        condition: service_healthy
    networks:
      - api-network

  db:
    image: mcr.microsoft.com/mssql/server:2022-latest
    environment:
      - SA_PASSWORD=YourStrong!Passw0rd
      - ACCEPT_EULA=Y
    ports:
      - "1433:1433"
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P YourStrong!Passw0rd -Q 'SELECT 1' -No || exit 1",
        ]
      interval: 10s
      timeout: 5s
      retries: 10
    networks:
      - api-network

networks:
  api-network:
    driver: bridge
```

两个细节值得记住：

- `condition: service_healthy` 能避免 API 在 SQL Server 还没准备好时启动失败。
- 环境变量里的双下划线 `__` 会映射到 ASP.NET Core 配置层级里的冒号，比如 `ConnectionStrings__DefaultConnection` 对应 `ConnectionStrings:DefaultConnection`。

本地 Compose 不是生产部署本身，但它能提前暴露端口、连接字符串、依赖启动顺序和健康检查问题。

## 健康检查要分层

容器平台需要知道你的服务是不是活着、能不能接流量。ASP.NET Core 内置 health checks，部署到 Azure Container Apps、Kubernetes 或 App Service 容器场景时，不应该省略。

原文强调 liveness 和 readiness 的区别：

- Liveness：进程是否还活着、没有死锁。失败通常触发重启。
- Readiness：应用是否准备好处理请求，比如数据库和外部依赖是否可用。失败时通常停止转发流量，但不一定重启。

一个简化版配置可以这样写：

```csharp
using Microsoft.Extensions.Diagnostics.HealthChecks;

builder.Services
    .AddHealthChecks()
    .AddDbContextCheck<AppDbContext>("database")
    .AddCheck<ExternalApiHealthCheck>("external-api", tags: ["ready"]);

app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    Predicate = _ => false
});

app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready")
});
```

`/health/live` 不应该检查数据库，否则数据库短暂故障可能导致整批容器重启。`/health/ready` 才适合检查数据库、外部 API、消息队列等真实依赖。

## 配置放在环境里

ASP.NET Core 的配置系统本来就是分层的：

- `appsettings.json` 放共享默认值。
- `appsettings.{Environment}.json` 放环境差异。
- 环境变量在运行时覆盖前两者。

生产环境不要把配置写死进代码或 Dockerfile。`ASPNETCORE_ENVIRONMENT` 应该在 Azure App Service 的 Application Settings 或容器运行配置里设为 `Production`。

强类型配置建议用 `IOptions<T>`：

```csharp
builder.Services.Configure<ApiSettings>(
    builder.Configuration.GetSection("ApiSettings"));

public sealed record ApiSettings
{
    public int MaxPageSize { get; init; } = 100;
    public int DefaultPageSize { get; init; } = 20;
    public int CacheExpirationMinutes { get; init; } = 5;
}
```

这比到处写 magic string 更稳，也更容易测试。如果某些配置会运行时变化，可以再考虑 `IOptionsMonitor<T>`。

## App Service 适合快速上线

Azure App Service 是很多团队部署 ASP.NET Core API 的最短路径。你可以直接部署发布目录，也可以部署容器镜像。它负责 TLS、基础伸缩、平台维护，并且和 GitHub Actions 集成很顺。

原文给了一个 GitHub Actions 发布到 App Service 的基本形状：

```yaml
name: Deploy ASP.NET Core API to Azure App Service

on:
  push:
    branches: [main]

env:
  DOTNET_VERSION: "10.0.x"
  AZURE_WEBAPP_NAME: "my-api-app"
  AZURE_WEBAPP_PACKAGE_PATH: "./publish"

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: ${{ env.DOTNET_VERSION }}

      - name: Restore dependencies
        run: dotnet restore

      - name: Build
        run: dotnet build --configuration Release --no-restore

      - name: Test
        run: dotnet test --no-build --configuration Release

      - name: Publish
        run: dotnet publish src/MyApi/MyApi.csproj --configuration Release --output ${{ env.AZURE_WEBAPP_PACKAGE_PATH }} --no-build

      - name: Deploy to Azure App Service
        uses: azure/webapps-deploy@v3
        with:
          app-name: ${{ env.AZURE_WEBAPP_NAME }}
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
          package: ${{ env.AZURE_WEBAPP_PACKAGE_PATH }}
```

发布配置文件应放在 GitHub repository secret 里，比如 `AZURE_WEBAPP_PUBLISH_PROFILE`。不要把凭据写进仓库。

对单个 API 或希望快速上生产的团队，App Service 往往更省心。它不要求你先设计完整容器编排模型。

## Container Apps 适合容器优先

Azure Container Apps 更适合已经容器化、想要自动伸缩或 scale-to-zero 的场景。它比直接用 Kubernetes 简单，但比 App Service 更贴近容器运行模型。

基本部署命令类似：

```bash
az containerapp create \
  --name my-api \
  --resource-group my-rg \
  --environment my-env \
  --image myregistry.azurecr.io/my-api:latest \
  --target-port 8080 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 10 \
  --cpu 0.5 \
  --memory 1Gi
```

`--min-replicas 0` 可以 scale-to-zero，适合开发、测试或低频服务。代价是冷启动，.NET 应用通常会有几秒延迟。生产 API 如果有明确延迟要求，通常把 `--min-replicas` 设为 `1` 更稳。

简单判断：

| 场景                                   | 更合适                          |
| -------------------------------------- | ------------------------------- |
| 单个 API，想少管容器编排               | Azure App Service               |
| 已经容器化，需要 scale-to-zero 或 Dapr | Azure Container Apps            |
| 多服务系统，未来可能走 AKS             | Azure Container Apps 起步更自然 |

## 密钥不要进镜像

不要把 secrets 放进源代码、`appsettings.json`、Dockerfile 或 Docker image layer。即使仓库不是公开的，密钥也可能出现在构建日志、镜像历史、崩溃报告和开发者机器里。

本地开发用 User Secrets：

```bash
dotnet user-secrets init
dotnet user-secrets set "ConnectionStrings:DefaultConnection" "Server=localhost;..."
dotnet user-secrets set "ApiKeys:Stripe" "sk_test_..."
```

Azure 生产环境用 Key Vault + managed identity。应用用 `DefaultAzureCredential` 读取 Key Vault，不需要自己管理账号密码：

```csharp
var keyVaultUrl = builder.Configuration["KeyVaultUrl"];

if (!string.IsNullOrEmpty(keyVaultUrl))
{
    builder.Configuration.AddAzureKeyVault(
        new Uri(keyVaultUrl),
        new DefaultAzureCredential());
}
```

Key Vault secret 名称里用双短横线 `--` 表示配置层级，比如 `ConnectionStrings--DefaultConnection` 会映射成 `ConnectionStrings:DefaultConnection`。

## 迁移单独跑

不要轻易在应用启动时直接跑 `dotnet ef database update` 或 `context.Database.MigrateAsync()`。多实例部署时，两个实例同时启动、同时迁移，可能产生锁冲突或失败。

更稳的做法是把数据库迁移作为 pre-deploy step：

1. 构建和测试通过。
2. 单独运行 EF Core migration bundle 或迁移命令。
3. 迁移成功后再部署新版本。

如果环境限制必须在启动时迁移，至少要加 distributed lock。否则它只是本地方便，生产不稳。

## 选择发布模式

部署方式会影响启动时间、镜像大小、内存和吞吐。原文提到几个选项：

- Framework-dependent deployment：默认方式，依赖宿主机或 runtime 镜像里的 .NET runtime。Docker 使用 `aspnet:10.0` 时就是这个模型。
- Self-contained deployment：把 runtime 一起打进去，更大，但更可移植。命令加 `--self-contained true -r linux-x64`。
- ReadyToRun：发布时预编译部分 IL，减少冷启动时 JIT 工作。可用 `-p:PublishReadyToRun=true`。
- Native AOT：启动快、内存低，但反射、动态加载、部分 middleware 和库兼容性要仔细确认。

如果你的 API 跑在 Container Apps 且启用了 scale-to-zero，ReadyToRun 值得测试。小 API 收益可能有限，大 API 或冷启动敏感场景可能有明显改善。

示例命令：

```bash
dotnet publish -c Release -r linux-x64 --self-contained true -p:PublishReadyToRun=true
```

不要只看理论。上线前测一次镜像大小、启动时间、内存和首个请求延迟，再决定是否启用。

## 上线前清单

把原文内容压缩成上线检查，可以是这样：

- Dockerfile 使用多阶段构建，生产镜像只用 ASP.NET Core runtime。
- 容器非 root 运行，端口统一到 `8080`。
- Compose 能启动 API 和依赖，数据库有 healthcheck。
- `/health/live` 和 `/health/ready` 分开。
- `ASPNETCORE_ENVIRONMENT=Production` 放在平台配置里。
- secrets 通过 User Secrets、环境变量或 Key Vault 注入，不进入镜像。
- GitHub Actions 先 restore/build/test/publish，再部署。
- 数据库迁移作为单独步骤处理。
- App Service 和 Container Apps 的选择符合团队运维模型。
- 需要冷启动优化时，再评估 ReadyToRun 或 Native AOT。

部署不是最后一步的“发布按钮”，而是一组贯穿代码、配置、容器、云平台和运维的工程约定。先把这些约定做清楚，ASP.NET Core API 才更像一个能长期运行的生产服务。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Deploying ASP.NET Core Web API to Azure and Docker](https://www.devleader.ca/2026/06/09/deploying-aspnet-core-web-api-to-azure-and-docker)
