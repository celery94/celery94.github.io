---
pubDatetime: 2025-10-13
title: 在 AWS Lambda 上使用 Minimal APIs 构建高性能无服务器 API
description: 深入探讨如何将 ASP.NET Core Minimal APIs 部署到 AWS Lambda，包括配置步骤、性能测试、冷启动优化和实际应用场景分析，帮助开发者理解无服务器架构的优势与权衡。
tags: [".NET", "ASP.NET Core", "Architecture", "DevOps"]
slug: building-fast-serverless-apis-minimal-apis-aws-lambda
source: https://www.milanjovanovic.tech/blog/building-fast-serverless-apis-with-minimal-apis-on-aws-lambda
---

# 在 AWS Lambda 上使用 Minimal APIs 构建高性能无服务器 API

无服务器架构（Serverless）已经成为现代云原生应用开发的重要选择。对于 .NET 开发者而言，AWS Lambda 提供了一个强大的平台，可以按需运行代码而无需维护服务器基础设施。通过结合 ASP.NET Core Minimal APIs 和 AWS Lambda，我们能够构建轻量级、高效且成本可控的 API 服务。

本文将深入探讨如何将 Minimal APIs 部署到 AWS Lambda，分析其性能表现，并讨论这种架构模式适用的场景及需要注意的权衡因素。

## 无服务器架构的核心优势

在深入技术细节之前，我们先理解为什么要考虑将 API 部署到 Lambda。无服务器架构的核心价值在于将基础设施管理的负担转移给云服务提供商，让开发团队能够专注于业务逻辑的实现。

传统的服务器托管模式需要开发者管理虚拟机、负载均衡器、自动扩缩容策略等基础设施。即使在低流量时期，服务器也需要持续运行并产生费用。而 Lambda 采用按需计费模式，仅在函数实际执行时收费，并且提供每月一百万次免费请求额度，这对于测试环境和轻量级应用极具吸引力。

此外，Lambda 的自动扩展能力能够无缝应对流量波动。当请求量激增时，AWS 会自动创建更多函数实例来处理并发请求；当流量下降时，实例会自动缩减。这种弹性机制无需人工干预，极大降低了运维复杂度。

## 配置 Minimal APIs 以支持 Lambda

将 ASP.NET Core Minimal APIs 迁移到 Lambda 的过程出乎意料地简单。整个配置只需要三个关键步骤，即可让你的 API 同时支持本地开发和 Lambda 部署。

首先创建一个标准的 Minimal API 项目：

```bash
dotnet new webapi -n MyLambdaApi
cd MyLambdaApi
```

接下来安装 Amazon 提供的托管包，这个包封装了 Lambda 与 ASP.NET Core 之间的集成逻辑：

```bash
dotnet add package Amazon.Lambda.AspNetCoreServer.Hosting
```

最后在 `Program.cs` 中添加一行关键代码来启用 Lambda 托管支持：

```csharp
var builder = WebApplication.CreateBuilder(args);

// 添加 Lambda 托管支持，指定事件源类型为 HTTP API
builder.Services.AddAWSLambdaHosting(LambdaEventSource.HttpApi);

var app = builder.Build();

// 定义一个简单的端点
app.MapGet("/", () => "Hello from Lambda!");

app.Run();
```

这个配置的巧妙之处在于它的双重特性。当你在本地运行 `dotnet run` 时，应用会使用 Kestrel 服务器正常启动，方便开发和调试。而当部署到 AWS 后，`AddAWSLambdaHosting` 方法会自动激活 Lambda 运行时环境，将 HTTP 请求转换为 Lambda 事件并路由到相应的端点。

这种设计让开发者无需维护两套不同的代码或配置，极大提升了开发效率。你可以在本地完成所有开发和测试工作，部署时只需简单地将代码推送到 AWS，应用会自动适应 Lambda 环境。

## 部署到 AWS Lambda

部署过程同样简洁明了。AWS 提供了专门的 .NET CLI 工具来简化 Lambda 函数的发布流程。

首先全局安装 Lambda 工具：

```bash
dotnet tool install -g Amazon.Lambda.Tools
```

然后使用一条命令完成部署：

```bash
dotnet lambda deploy-function
```

这个工具会启动一个交互式向导，询问你几个关键问题：函数名称、使用的 IAM 角色、内存配置等。如果你只是进行测试，选择默认值即可快速完成部署。整个过程通常在一到两分钟内完成，之后你会获得一个类似这样的 Lambda 函数 URL：

```
https://abc123xyz.lambda-url.us-east-1.on.aws/
```

在 AWS 管理控制台中，你可以查看函数的详细信息，包括配置参数、日志输出、监控指标等。Lambda 会自动配置 CloudWatch 日志记录，让你能够轻松追踪函数执行情况和排查问题。

值得注意的是，初次部署时需要确保你的 AWS CLI 已经正确配置了访问凭证和默认区域。你可以通过 `aws configure` 命令来设置这些信息，或者使用环境变量和 IAM 角色进行身份验证。

## 冷启动问题的深入分析

Lambda 的核心特性之一是按需执行，但这也带来了一个不可回避的问题：冷启动（Cold Start）。理解冷启动的原理和影响对于评估 Lambda 是否适合你的场景至关重要。

当 Lambda 函数一段时间未被调用时，AWS 会回收其运行实例以节省资源。当下次请求到来时，Lambda 需要重新初始化运行环境，包括加载 .NET 运行时、应用程序代码、依赖库，以及执行应用启动逻辑。这个过程会显著增加首次请求的延迟。

通过实际测试一个基础的 Minimal API，我们可以清楚地看到冷启动的影响：

- **首次请求（冷启动）**：2,153 毫秒
- **第二次请求（预热状态）**：154 毫秒
- **第三次请求（预热状态）**：143 毫秒
- **闲置 10 分钟后（再次冷启动）**：2,074 毫秒

从数据中可以看出，冷启动会导致超过 2 秒的延迟，而预热状态下的响应时间稳定在 150 毫秒左右。Lambda 的空闲回收策略通常在 10 到 15 分钟的不活动期后触发，这意味着低流量 API 会频繁遭遇冷启动问题。

需要注意的是，这些测试数据是在跨大西洋的网络条件下获得的（客户端位于欧洲，Lambda 函数部署在美国东部）。网络延迟会进一步影响总体响应时间。如果你的应用服务于全球用户，建议在多个区域部署函数，并使用 CloudFront 等 CDN 服务来优化路由。

AWS 提供了一个名为 SnapStart 的优化功能来缓解冷启动问题。SnapStart 的工作原理是在函数初始化完成后创建内存快照，后续冷启动时直接恢复快照而非重新初始化。这能将冷启动时间减少 90% 以上。但需要注意的是，SnapStart 仅支持 Java 运行时，.NET 运行时目前还无法使用此功能。

对于 .NET 应用，可以考虑以下策略来减轻冷启动影响：

1. **Provisioned Concurrency（预配置并发）**：保持一定数量的实例始终处于预热状态，消除冷启动但会增加成本。
2. **定期预热**：使用 CloudWatch Events 定期调用函数，确保至少有一个实例保持活跃。
3. **优化应用启动时间**：减少依赖注入容器中的服务数量，延迟加载非关键组件。
4. **使用 ReadyToRun 编译**：通过 AOT 编译减少 JIT 编译开销。

## 实战性能测试：CRUD 操作基准

为了更真实地评估 Lambda 的性能表现，我构建了一个包含完整 CRUD 操作的产品管理 API。这个 API 使用 Npgsql 和 Dapper 与运行在 Amazon RDS 上的 PostgreSQL 数据库交互。

以下是创建产品端点的实现代码：

```csharp
// POST /products - 创建新产品
app.MapPost("/products", async (CreateProductRequest request, NpgsqlDataSource dataSource) =>
{
    const string sql =
        """
        INSERT INTO Products (Name, Description, Price, CreatedAt)
        VALUES (@Name, @Description, @Price, @CreatedAt)
        RETURNING Id, Name, Description, Price, CreatedAt
        """;

    await using var connection = await dataSource.OpenConnectionAsync();
    var product = await connection.QueryFirstAsync<Product>(sql, new
    {
        request.Name,
        request.Description,
        request.Price,
        CreatedAt = DateTime.UtcNow
    });

    return Results.Created(
        $"/products/{product.Id}",
        new ProductResponse(
            product.Id,
            product.Name,
            product.Description,
            product.Price,
            product.CreatedAt));
});

// GET /products/{id} - 根据 ID 获取产品
app.MapGet("/products/{id}", async (int id, NpgsqlDataSource dataSource) =>
{
    const string sql = "SELECT * FROM Products WHERE Id = @Id";

    await using var connection = await dataSource.OpenConnectionAsync();
    var product = await connection.QueryFirstOrDefaultAsync<Product>(sql, new { Id = id });

    return product is not null
        ? Results.Ok(new ProductResponse(product.Id, product.Name, product.Description, product.Price, product.CreatedAt))
        : Results.NotFound();
});

// PUT /products/{id} - 更新产品
app.MapPut("/products/{id}", async (int id, UpdateProductRequest request, NpgsqlDataSource dataSource) =>
{
    const string sql =
        """
        UPDATE Products
        SET Name = @Name, Description = @Description, Price = @Price
        WHERE Id = @Id
        RETURNING Id, Name, Description, Price, CreatedAt
        """;

    await using var connection = await dataSource.OpenConnectionAsync();
    var product = await connection.QueryFirstOrDefaultAsync<Product>(sql, new
    {
        Id = id,
        request.Name,
        request.Description,
        request.Price
    });

    return product is not null
        ? Results.Ok(new ProductResponse(product.Id, product.Name, product.Description, product.Price, product.CreatedAt))
        : Results.NotFound();
});

// DELETE /products/{id} - 删除产品
app.MapDelete("/products/{id}", async (int id, NpgsqlDataSource dataSource) =>
{
    const string sql = "DELETE FROM Products WHERE Id = @Id RETURNING Id";

    await using var connection = await dataSource.OpenConnectionAsync();
    var deletedId = await connection.QueryFirstOrDefaultAsync<int?>(sql, new { Id = id });

    return deletedId.HasValue ? Results.NoContent() : Results.NotFound();
});
```

这个实现展示了典型的数据库交互模式。每个端点都使用依赖注入获取 `NpgsqlDataSource`，然后通过 Dapper 执行 SQL 查询。PostgreSQL 的 `RETURNING` 子句允许在插入或更新后直接返回受影响的行，减少数据库往返次数。

### 单次调用延迟测试

首先测试每个操作的独立延迟：

| 操作 | 延迟（毫秒） | 说明                         |
| ---- | ------------ | ---------------------------- |
| 创建 | 537          | 包含冷启动和数据库连接初始化 |
| 读取 | 134          | 简单的 SELECT 查询           |
| 更新 | 140          | 单个字段的 UPDATE 操作       |
| 删除 | 167          | DELETE 操作并验证结果        |

创建操作耗时最长，因为它包含了冷启动开销。一旦函数进入预热状态，后续操作的响应时间都保持在 200 毫秒以下。考虑到每次操作都涉及到网络往返和数据库查询，这个性能水平是相当合理的。

### 负载测试：100 并发用户

为了评估 Lambda 的并发处理能力，我使用负载测试工具模拟 100 个虚拟用户同时访问 API。AWS Lambda 会自动扩展实例数量来处理并发请求，理论上每个请求都会得到一个预热的函数实例。

测试结果显示出色的性能表现：

- **创建操作平均延迟**：129 毫秒
- **读取操作平均延迟**：132 毫秒
- **更新操作平均延迟**：152 毫秒
- **删除操作平均延迟**：144 毫秒

在高并发场景下，平均延迟反而有所下降，这是因为大部分请求都命中了预热实例，避免了冷启动开销。Lambda 的自动扩展机制能够在几秒内创建数十个并发实例，有效应对流量峰值。

需要注意的是，并发扩展也有限制。默认情况下，AWS 账户在每个区域有 1000 个并发执行的配额限制。对于超高流量应用，可能需要申请提升配额或采用多区域部署策略。

此外，数据库连接池也是需要考虑的因素。由于每个 Lambda 实例都会建立自己的数据库连接，高并发时可能快速耗尽数据库的连接限制。AWS 提供 RDS Proxy 服务来管理连接池和复用连接，有效缓解这个问题。

## Lambda 适用场景与架构权衡

通过上述测试和分析，我们可以总结 Lambda 适合的场景以及需要权衡的因素。

### Lambda 的理想应用场景

1. **间歇性工作负载**：如果你的 API 流量不是持续的，而是有明显的高峰和低谷，Lambda 能够在低流量时期节省大量成本。例如内部管理工具、定期数据处理任务、webhook 接收端点等。

2. **事件驱动架构**：Lambda 天然适合处理来自其他 AWS 服务的事件，如 S3 文件上传、DynamoDB 流变更、SNS 消息等。你可以构建完全无服务器的事件处理管道。

3. **微服务拆分**：将单体应用中的特定功能模块独立部署为 Lambda 函数，实现逐步迁移和模块化。每个函数可以独立扩展和更新，降低系统耦合度。

4. **原型验证和 MVP**：Lambda 的免费额度和快速部署特性使其成为快速验证想法的理想平台。你可以在不投入大量基础设施成本的情况下测试市场反应。

5. **后台处理任务**：图像处理、报表生成、数据导出等不需要实时响应的任务非常适合 Lambda。可以通过 SQS 队列触发异步处理。

### 需要谨慎考虑的场景

1. **延迟敏感型应用**：如果你的 API 需要始终保持在 100 毫秒以下的响应时间，Lambda 的冷启动和网络开销可能无法满足要求。实时交易系统、游戏服务器、高频交易平台等应考虑传统托管方式。

2. **持续高流量服务**：当 API 的流量持续稳定且较高时，Lambda 的成本优势会逐渐消失。此时使用 EC2、ECS 或 EKS 运行容器可能更经济。

3. **长时间运行的操作**：Lambda 有 15 分钟的最大执行时间限制。如果你的任务需要更长时间，应该考虑 ECS Fargate 或 Step Functions 来协调多个短任务。

4. **状态管理需求**：Lambda 函数是无状态的，每次调用都可能运行在不同的实例上。如果你需要在内存中维护状态或缓存，需要借助外部服务如 ElastiCache 或 DynamoDB。

5. **复杂的网络配置**：如果你的应用需要固定 IP 地址、复杂的 VPC 配置或直接访问本地资源，Lambda 的网络配置会变得复杂且可能影响性能。

### 混合架构策略

在实际项目中，最佳方案往往是混合架构。你可以将低频、不敏感的端点部署到 Lambda，而将核心、高频的 API 部署到容器或虚拟机上。通过 API Gateway 或 Application Load Balancer 进行路由，实现成本和性能的平衡。

例如，一个电商平台可能将商品浏览、搜索等高频接口部署在 ECS 上，而将订单导出、数据分析、通知发送等功能实现为 Lambda 函数。这样既保证了用户体验，又优化了运营成本。

## 优化建议与最佳实践

为了最大化 Lambda 上 Minimal APIs 的性能，以下是一些实用的优化建议：

### 减少冷启动影响

1. **最小化依赖**：只引入必要的 NuGet 包，避免臃肿的依赖链。
2. **使用 ReadyToRun 编译**：在项目文件中启用 `<PublishReadyToRun>true</PublishReadyToRun>`，预编译部分代码减少 JIT 开销。
3. **优化依赖注入**：只注册真正需要的服务，避免在启动时执行昂贵的初始化操作。
4. **合理配置内存**：Lambda 的 CPU 性能与分配的内存成正比。适当增加内存配置可以显著缩短冷启动时间。

### 数据库连接优化

1. **使用连接池**：配置合理的最小和最大连接数，复用数据库连接。
2. **考虑 RDS Proxy**：对于高并发场景，RDS Proxy 能够有效管理连接并减少数据库负载。
3. **缓存查询结果**：使用 ElastiCache 或 DynamoDB 缓存频繁访问的数据，减少数据库压力。

### 监控和日志

1. **启用 X-Ray 追踪**：通过 AWS X-Ray 可以可视化请求流程，识别性能瓶颈。
2. **结构化日志**：使用 Serilog 等库输出结构化日志，便于在 CloudWatch Insights 中查询分析。
3. **设置告警**：为冷启动率、错误率、延迟等关键指标设置 CloudWatch 告警。

### 成本控制

1. **合理设置超时时间**：避免过长的超时配置导致失败请求持续消耗资源。
2. **使用预留并发**：对于关键端点，考虑购买预留容量以获得成本折扣。
3. **定期审查使用情况**：使用 AWS Cost Explorer 分析 Lambda 使用模式，识别优化机会。

## 总结

将 ASP.NET Core Minimal APIs 部署到 AWS Lambda 是一个简单而强大的选择。通过 `Amazon.Lambda.AspNetCoreServer.Hosting` 库，只需几行代码即可实现本地开发和无服务器部署的无缝切换。Lambda 的按需付费模式和自动扩展能力为开发者提供了极大的灵活性和成本优势。

然而，无服务器架构并非万能解决方案。冷启动延迟是不可忽视的挑战，特别是对于延迟敏感型应用。在决定是否采用 Lambda 时，需要综合考虑应用的流量特征、性能要求、成本预算和运维能力。

对于间歇性工作负载、事件驱动场景和微服务架构，Lambda 提供了一个成本效益极高的部署选项。而对于持续高流量、超低延迟需求的应用，传统的容器化部署可能是更好的选择。

最终，成功的架构往往是混合的——在正确的场景使用正确的工具。Lambda 为 .NET 开发者的工具箱增添了一个强大的选项，让我们能够更灵活地应对不同的业务需求。

通过本文的实践和分析，希望你能够对 Lambda 上的 Minimal APIs 有更深入的理解，并在自己的项目中做出明智的架构决策。无论选择哪种部署方式，保持对性能的持续监控和优化都是确保应用成功的关键。
