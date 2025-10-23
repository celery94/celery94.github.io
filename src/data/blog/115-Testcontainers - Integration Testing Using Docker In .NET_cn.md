---
pubDatetime: 2024-04-22
tags: [".NET", "AI", "DevOps", "Testing"]
source: https://www.milanjovanovic.tech/blog/testcontainers-integration-testing-using-docker-in-dotnet?utm_source=Twitter&utm_medium=social&utm_campaign=15.04.2024
author: Milan Jovanović
title: Testcontainers - 使用 Docker 在 .NET 中进行集成测试
description: 现代软件应用很少是孤立工作的。相反，一个典型的应用程序将与多个外部系统通信，例如数据库、消息系统、缓存提供商，以及许多第三方服务。确保一切正常运行是你的责任。
---

# Testcontainers - 使用 Docker 在 .NET 中进行集成测试

> ## 摘要
>
> Testcontainers 用于支持使用 Docker 容器进行集成测试。它可以通过编程方式创建、管理和销毁容器，从而为各种外部依赖提供轻松的模拟和隔离环境，如数据库、Web 服务器或任何其他可以在 Docker 容器中运行的服务。
>
> 这种方法使得开发者可以在本地或持续集成环境中以一致和可重复的方式进行测试，无需担心环境配置问题。Testcontainers 提供了多种模块支持不同的场景，例如专门的数据库模块、Selenium 模块用于自动化浏览器测试，以及一般的 Docker 模块用于启动任何容器。
>
> 使用 Testcontainers，开发者可以编写更健壮、更真实环境的集成测试，确保他们的应用能够在生产环境中正确运行。
>
> 原文 [Testcontainers - 使用 Docker 在 .NET 中进行集成测试](https://www.milanjovanovic.tech/blog/testcontainers-integration-testing-using-docker-in-dotnet?utm_source=Twitter&utm_medium=social&utm_campaign=15.04.2024)

---

现代软件应用很少是孤立工作的。相反，一个典型的应用程序将与多个外部系统通信，例如数据库、消息系统、缓存提供商，以及许多第三方服务。确保一切正常运行是你的责任。

希望我不需要说服你编写测试的价值。

你应该编写测试。就这些。

然而，我确实想讨论**集成测试**的*价值*。

**单元测试**有助于在没有任何外部服务的情况下，独立测试业务逻辑。它们易于编写，并提供几乎即时的反馈。

但是如果没有**集成测试**，你无法对你的应用程序完全有信心。

所以，在本周的新闻稿中，我将向你展示如何使用**Docker**进行集成测试。

这里是我们用于编写**集成测试**的工具：

- **Testcontainers**
- Docker
- [**xUnit**](https://www.milanjovanovic.tech/blog/creating-data-driven-tests-with-xunit)

让我们开始吧！

## 什么是 Testcontainers？

[Testcontainers](https://dotnet.testcontainers.org/) 是一个用于使用临时 Docker 容器编写测试的库。

为什么你应该使用它？

集成测试被认为是“困难”的，因为你必须维护测试基础设施。在运行测试之前，你需要确保数据库已启动并运行。你还必须为测试所需的任何数据进行预置。如果你在相同的数据库上并行运行测试，它们可能会相互干扰。

一个可能的解决方案是使用所需服务的内存中变体。但这与使用模拟没有太大区别。内存中的服务可能不具备生产服务的所有功能。

Testcontainers 通过使用 Docker 来启动真实服务进行集成测试，从而解决了这个问题。

这是创建一个**SQL Server**容器的示例：

```csharp
MsSqlContainer dbContainer = new MsSqlBuilder()
    .WithImage("mcr.microsoft.com/mssql/server:2022-latest")
    .WithPassword("Strong_password_123!")
    .Build();
```

然后，你可以使用`MsSqlContainer`实例获取在容器内运行的数据库的连接字符串。

你看出这对编写集成测试的价值了吗？

不再需要模拟或假内存数据库。相反，你可以使用真正的东西。

我在这里不会深入研究这个库，所以请参考文档了解更多信息。

## 实现自定义 WebApplicationFactory

**ASP.NET Core**提供了一个内存中的测试服务器，我们可以使用它来启动应用程序实例以运行测试。`Microsoft.AspNetCore.Mvc.Testing`包提供了我们将用作基础的`WebApplicationFactory`类。

`WebApplicationFactory<TEntryPoint>`用于为集成测试创建`TestServer`。

自定义的`IntegrationTestWebAppFactory`将做几件事情：

- 创建并配置一个`MsSqlContainer`实例
- 调用`ConfigureTestServices`来使用容器数据库设置 EF Core
- 在`IAsyncLifetime`中启动和停止容器实例

`MsSqlContainer`有一个`GetConnectionString`方法，用于抓取当前容器的连接字符串。请注意，这可能在测试之间发生变化，因为每个测试类将创建一个单独的容器实例。同一个测试类中的测试用例将使用相同的容器实例。因此，如果你需要在测试之间进行清理，请记住这一点。

另一个需要注意的是**数据库迁移**。你将不得不在每次测试之前手动运行它们，以创建所需的数据库结构。

使用`IAsyncLifetime`异步启动容器实例。容器是在`StartAsync`中启动的，任何测试运行之前。并且它是在`StopAsync`内部停止的。

这是`IntegrationTestWebAppFactory`的完整代码：

```csharp
public class IntegrationTestWebAppFactory
    : WebApplicationFactory<Program>,
      IAsyncLifetime
{
    private readonly MsSqlContainer _dbContainer = new MsSqlBuilder()
        .WithImage("mcr.microsoft.com/mssql/server:2022-latest")
        .WithPassword("Strong_password_123!")
        .Build();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureTestServices(services =>
        {
            var descriptorType =
                typeof(DbContextOptions<ApplicationDbContext>);

            var descriptor = services
                .SingleOrDefault(s => s.ServiceType == descriptorType);

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

基础测试类将实现类夹具接口`IClassFixture`。它表明类包含测试，并在内部的测试用例中提供共享的对象实例。这是实例化测试所需的大多数服务的好地方。

例如，我正在创建一个`IServiceScope`来解析测试中的作用域服务。

- `ISender` 用于发送命令和查询
- `ApplicationDbContext` 用于数据库设置或验证结果

```csharp
public abstract class BaseIntegrationTest
    : IClassFixture<IntegrationTestWebAppFactory>,
      IDisposable
{
    private readonly IServiceScope _scope;
    protected readonly ISender Sender;
    protected readonly ApplicationDbContext DbContext;

    protected BaseIntegrationTest(IntegrationTestWebAppFactory factory)
    {
        _scope = factory.Services.CreateScope();

        Sender = _scope.ServiceProvider.GetRequiredService<ISender>();

        DbContext = _scope.ServiceProvider
            .GetRequiredService<ApplicationDbContext>();
    }

    public void Dispose()
    {
        _scope?.Dispose();
        DbContext?.Dispose();
    }
}
```

有了所有的基础架构，我们终于可以编写测试了。

## 整合所有内容 - 编写集成测试

这是一个带有集成测试的`ProductTests`类。

我使用*安排-行动-断言*模式来构建测试：

- _安排_ - 创建`CreateProduct.Command`实例
- _行动_ - 使用`ISender`发送命令并存储结果
- _断言_ - 使用*行动*步骤中的结果来验证数据库状态

这样编写集成测试的价值在于你可以使用完整的**MediatR**请求管道。如果你有任何包装请求的`IPipelineBehavior`，它也将被执行。

如果你在服务类内部编写业务逻辑也一样。代替解析`ISender`，你将解析你想要测试的特定服务。

最重要的是，此测试使用运行在**Docker 容器**内的真实数据库实例。

```csharp
public class ProductTests : BaseIntegrationTest
{
    public ProductTests(IntegrationTestWebAppFactory factory)
        : base(factory)
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
        var product = DbContext
            .Products
            .FirstOrDefault(p => p.Id == productId);

        Assert.NotNull(product);
    }
}
```

## 在 CI/CD 管道中运行集成测试

你也可以在支持 Docker 的 **CI/CD 管道**中使用**Testcontainers** 运行集成测试。

**GitHub Actions** 支持 Docker。如果你在那里托管你的项目，集成测试将开箱即用。

你可以在这里了解更多关于[**使用 GitHub Actions 构建 CI/CD 管道**](https://www.milanjovanovic.tech/blog/how-to-build-ci-cd-pipeline-with-github-actions-and-dotnet)。

如果你想要一个插件解决方案，这里有一个你可以使用的 GitHub Actions 工作流程：

```yaml
name: 运行测试 🚀

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

      - name: 设置 .NET
        uses: actions/setup-dotnet@v3
        with:
          dotnet-version: "7.0.x"

      - name: 恢复
        run: dotnet restore ./Products.Api.sln

      - name: 构建
        run: dotnet build ./Products.Api.sln --no-restore

      - name: 测试
        run: dotnet test ./Products.Api.sln --no-build
```

## 结论

**Testcontainers** 是使用 Docker 编写**集成测试**的出色解决方案。你可以启动和配置任何**Docker**图像并从你的应用程序中使用它。这比使用缺少许多功能的模拟或内存中变体要好得多。

如果你有一个支持 Docker 的 CI/CD 管道，Testcontainers 将开箱即用。

即使是少量的集成测试也会大大提高你对系统的信心。

你可以在我的 GitHub 上抓取这个[**新闻稿的源代码**](https://github.com/m-jovanovic/testcontainers-sample)。
它完全免费，所以你还在等什么？

如果你喜欢视频，这里有一个关于[**使用 Testcontainers 进行集成测试**](https://youtu.be/tj5ZCtvgXKY)的快速教程。

希望这对你有价值。
