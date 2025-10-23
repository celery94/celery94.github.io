---
pubDatetime: 2025-03-17
tags: [".NET", "AI", "DevOps", "Testing"]
slug: testcontainers-docker-dotnet-integration-testing
source: https://www.milanjovanovic.tech/blog/testcontainers-integration-testing-using-docker-in-dotnet
title: 🐳 利用 Testcontainers 和 Docker 提升 .NET 应用的集成测试质量
description: 探讨如何使用 Testcontainers 和 Docker 在 .NET 环境中进行集成测试，以提高系统稳定性和开发人员信心。
---

# 🐳 利用 Testcontainers 和 Docker 提升 .NET 应用的集成测试质量

现代软件应用几乎不会孤立运行，它们通常需要与数据库、消息系统、缓存提供者以及众多第三方服务进行交互。这就要求我们确保每个组件都能正常工作。测试的重要性不言而喻，而集成测试更是确保应用程序稳定性的关键。本文将向您介绍如何在 .NET 环境中使用 **Testcontainers** 和 **Docker** 进行集成测试。

## 为什么选择 Testcontainers？

[Testcontainers](https://dotnet.testcontainers.org/) 是一个用于编写测试的库，它通过临时 Docker 容器来实现。这种方式解决了传统集成测试的难题：维护测试基础设施。通常，我们需要确保数据库启动并运行，并且数据已被初始化。如果多个测试并行运行，可能会发生相互干扰。而 Testcontainers 利用 Docker 启动真实服务，从而避免这些问题。

```csharp
MsSqlContainer dbContainer = new MsSqlBuilder()
    .WithImage("mcr.microsoft.com/mssql/server:2022-latest")
    .WithPassword("Strong_password_123!")
    .Build();
```

这种方法让我们无需再使用模拟或内存数据库，而可以直接使用真实的数据库。

## 实现自定义 WebApplicationFactory

**ASP.NET Core** 提供了一个内存测试服务器，可用于集成测试。我们可以通过 `Microsoft.AspNetCore.Mvc.Testing` 包中的 `WebApplicationFactory` 类来实现这一点。

自定义 `IntegrationTestWebAppFactory` 的主要功能包括：

- 创建并配置 `MsSqlContainer` 实例
- 设置 EF Core，以便与容器数据库交互
- 使用 `IAsyncLifetime` 启动和停止容器实例

```csharp
public class IntegrationTestWebAppFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    private readonly MsSqlContainer _dbContainer = new MsSqlBuilder()
        .WithImage("mcr.microsoft.com/mssql/server:2022-latest")
        .WithPassword("Strong_password_123!")
        .Build();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureTestServices(services =>
        {
            var descriptorType = typeof(DbContextOptions<ApplicationDbContext>);
            var descriptor = services.SingleOrDefault(s => s.ServiceType == descriptorType);

            if (descriptor is not null)
            {
                services.Remove(descriptor);
            }

            services.AddDbContext<ApplicationDbContext>(options =>
                options.UseSqlServer(_dbContainer.GetConnectionString()));
        });
    }

    public Task InitializeAsync()
    {
        return _dbContainer.StartAsync();
    }

    public new Task DisposeAsync()
    {
        return _dbContainer.StopAsync();
    }
}
```

## 创建基础测试类

基础测试类实现了 `IClassFixture` 接口，用于在测试类内部共享对象实例。这里可以实例化大多数测试所需的服务，例如：

- `ISender` 用于发送命令和查询
- `ApplicationDbContext` 用于数据库设置或验证结果

```csharp
public abstract class BaseIntegrationTest : IClassFixture<IntegrationTestWebAppFactory>, IDisposable
{
    private readonly IServiceScope _scope;
    protected readonly ISender Sender;
    protected readonly ApplicationDbContext DbContext;

    protected BaseIntegrationTest(IntegrationTestWebAppFactory factory)
    {
        _scope = factory.Services.CreateScope();
        Sender = _scope.ServiceProvider.GetRequiredService<ISender>();
        DbContext = _scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
    }

    public void Dispose()
    {
        _scope?.Dispose();
        DbContext?.Dispose();
    }
}
```

## 编写集成测试

以下是一个 `ProductTests` 类示例，它包含一个集成测试：

```csharp
public class ProductTests : BaseIntegrationTest
{
    public ProductTests(IntegrationTestWebAppFactory factory) : base(factory)
    {
    }

    [Fact]
    public async Task Create_ShouldCreateProduct()
    {
        // Arrange
        var command = new CreateProduct.Command
        {
            Name = "AMD Ryzen 7 7700X",
            Category = "CPU",
            Price = 223.99m
        };

        // Act
        var productId = await Sender.Send(command);

        // Assert
        var product = DbContext.Products.FirstOrDefault(p => p.Id == productId);
        Assert.NotNull(product);
    }
}
```

这个测试使用了运行在 **Docker 容器**中的真实数据库实例。

## 在 CI/CD 管道中运行集成测试

你可以在支持 Docker 的 **CI/CD 管道**中运行 Testcontainers 的集成测试。例如，**GitHub Actions** 就支持 Docker。因此，如果你在 GitHub 托管项目，集成测试将开箱即用。

以下是一个可供使用的 GitHub Actions 工作流：

```yaml
name: Run Tests 🚀

on:
  workflow_dispatch:
  push:
    branches:
      - main

jobs:
  run-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup .NET
        uses: actions/setup-dotnet@v3
        with:
          dotnet-version: "7.0.x"

      - name: Restore
        run: dotnet restore ./Products.Api.sln

      - name: Build
        run: dotnet build ./Products.Api.sln --no-restore

      - name: Test
        run: dotnet test ./Products.Api.sln --no-build
```

## 总结

**Testcontainers** 是一个优秀的解决方案，用于使用 **Docker** 编写 **集成测试**。它允许您启动并配置任何 **Docker** 映像，并在应用程序中使用。这种方法比使用模拟或内存变体要好得多，因为后者缺乏许多功能。

如果您的 CI/CD 管道支持 Docker，那么 Testcontainers 可以直接使用。仅需少量集成测试即可显著提升您对系统的信心。

您可以从我的 GitHub 获取[**本新闻稿的源代码**](https://github.com/m-jovanovic/testcontainers-sample)。它完全免费，赶快行动吧！

如果您更喜欢视频教程，这里有一个关于[**使用 Testcontainers 进行集成测试的快速教程。**](https://youtu.be/tj5ZCtvgXKY)

希望这对您有所帮助。保持优秀！ 🎉
