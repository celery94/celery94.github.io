---
pubDatetime: 2026-04-22T20:28:00+08:00
title: "C# Feature Slice 测试策略：单元测试、集成测试与边界划分"
description: "Feature-sliced 架构的核心优势之一是让测试变得清晰：Handler 是天然的单元测试边界，WebApplicationFactory 覆盖 HTTP 管道。本文介绍针对 .NET Feature Slice 应用的完整测试策略，包括 Handler 单元测试、集成测试搭建、验证逻辑测试和 Testcontainers 使用方式。"
tags: ["CSharp", "Testing", "Feature Slice", "ASP.NET Core", "Architecture"]
slug: "csharp-feature-slice-testing-strategy"
ogImage: "../../assets/749/01-cover.png"
source: "https://www.devleader.ca/2026/04/21/testing-feature-slices-in-c-unit-tests-integration-tests-and-what-to-test"
---

![C# Feature Slice 测试策略：单元测试与集成测试](../../assets/749/01-cover.png)

Feature-sliced 架构（垂直切片架构，VSA）有个常被忽视的好处：架构本身就在告诉你该测什么、怎么测。分层架构要求你分别测 Controller、Service、Repository，三层之间的集成测试还容易产生大量重叠。Feature Slice 把一个 Use Case 打包成一个 Handler，Handler 就是天然的测试边界。

这篇文章介绍一套针对 .NET Feature-Sliced 应用的实际测试策略：单元测试覆盖 Handler 业务逻辑，集成测试覆盖完整 HTTP 管道，以及如何判断该用哪种。

## 为什么 Feature Slice 更好测

Feature Handler 只接收一个请求，返回一个结果，没有 HTTP context，没有路由，没有序列化。依赖项全部体现在构造函数里。这是单元测试最理想的形态。

对比传统分层 Service 的测试面：

```csharp
// 分层架构：测试 TaskService.CompleteTaskAsync 意味着
// - 方法会碰 _repository（需要 mock 的接口）
// - _repository 依赖 _db（另一个依赖）
// - 可能还有 _logger、_eventPublisher 等
// - 方法内部可能调用其他 Service 方法
```

Feature Handler 的测试面：

```csharp
// Feature Slice：测试 CompleteTaskHandler.HandleAsync 意味着
// - Handler 接受 AppDbContext（可用 EF 内存测试）
// - 接受 TimeProvider（可用 FakeTimeProvider）
// - 就这两个
```

构造函数就是 Test Fixture 的定义。每个依赖都是可见的、可控的。

## 单元测试：Command Handler

Handler 的单元测试使用 EF Core 内存数据库，而不是 mock `DbContext`。EF 内存提供器适合基础逻辑测试，但它是非关系型的，某些查询和约束会被静默放行。SQLite 内存模式的保真度更高，在涉及查询或约束时推荐使用。如果需要与生产环境等价的行为，可以用 Testcontainers（见后文）。

下面是 `CompleteTaskHandler` 的完整单元测试：

```csharp
// Tests/Features/Tasks/CompleteTask/CompleteTaskHandlerTests.cs
namespace TaskTracker.Tests.Features.Tasks.CompleteTask;

public sealed class CompleteTaskHandlerTests : IDisposable
{
    private readonly AppDbContext _db;
    private readonly FakeTimeProvider _time;
    private readonly CompleteTaskHandler _handler;

    public CompleteTaskHandlerTests()
    {
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        _db = new AppDbContext(options);
        _time = new FakeTimeProvider();
        _handler = new CompleteTaskHandler(_db, _time);
    }

    public void Dispose() => _db.Dispose();

    [Fact]
    public async Task HandleAsync_ExistingIncompleteTask_CompletesTask()
    {
        // Arrange
        var task = new TaskEntity
        {
            Id = Guid.NewGuid(),
            Title = "Test task",
            ProjectId = Guid.NewGuid(),
            CreatedAt = _time.GetUtcNow(),
            IsCompleted = false
        };

        _db.Tasks.Add(task);
        await _db.SaveChangesAsync();

        var expectedCompletedAt = _time.GetUtcNow().AddHours(1);
        _time.Advance(TimeSpan.FromHours(1));

        // Act
        var result = await _handler.HandleAsync(task.Id);

        // Assert
        result.Found.ShouldBeTrue();
        result.AlreadyCompleted.ShouldBeFalse();

        var updated = await _db.Tasks.FindAsync(task.Id);
        updated!.IsCompleted.ShouldBeTrue();
        updated.CompletedAt.ShouldBe(expectedCompletedAt);
    }

    [Fact]
    public async Task HandleAsync_TaskNotFound_ReturnsFalse()
    {
        var nonExistentId = Guid.NewGuid();
        var result = await _handler.HandleAsync(nonExistentId);
        result.Found.ShouldBeFalse();
    }

    [Fact]
    public async Task HandleAsync_AlreadyCompletedTask_ReturnsAlreadyCompleted()
    {
        // Arrange
        var task = new TaskEntity
        {
            Id = Guid.NewGuid(),
            Title = "Already done",
            ProjectId = Guid.NewGuid(),
            CreatedAt = _time.GetUtcNow(),
            IsCompleted = true,
            CompletedAt = _time.GetUtcNow()
        };

        _db.Tasks.Add(task);
        await _db.SaveChangesAsync();

        // Act
        var result = await _handler.HandleAsync(task.Id);

        // Assert
        result.Found.ShouldBeTrue();
        result.AlreadyCompleted.ShouldBeTrue();
    }
}
```

几点说明：

- 每个测试用 `Guid.NewGuid().ToString()` 作数据库名，保证测试之间没有共享状态
- `FakeTimeProvider` 来自 `Microsoft.Extensions.TimeProvider.Testing`，用于控制时间；若目标框架不支持，可以实现一个返回固定 `DateTimeOffset` 的最小 `TimeProvider` 子类
- 测试同时断言返回值和持久化状态，两者都验
- 命名规范：`MethodUnderTest_Condition_ExpectedResult`

## 单元测试：Query Handler

Query Handler 往往更简单，直接插入种子数据，运行查询，断言结果：

```csharp
// Tests/Features/Tasks/GetTasks/GetTasksHandlerTests.cs
namespace TaskTracker.Tests.Features.Tasks.GetTasks;

public sealed class GetTasksHandlerTests : IDisposable
{
    private readonly AppDbContext _db;
    private readonly GetTasksHandler _handler;
    private readonly Guid _projectId = Guid.NewGuid();

    public GetTasksHandlerTests()
    {
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        _db = new AppDbContext(options);
        _handler = new GetTasksHandler(_db);
    }

    public void Dispose() => _db.Dispose();

    [Fact]
    public async Task HandleAsync_WithTasks_ReturnsTasksForProject()
    {
        // Arrange
        await SeedTasksAsync(
            ("Task 1", _projectId, false),
            ("Task 2", _projectId, true),
            ("Other project task", Guid.NewGuid(), false));

        // Act
        var results = await _handler.HandleAsync(new GetTasksQuery(_projectId));

        // Assert
        results.Count.ShouldBe(2);
        results.Select(t => t.Title).ShouldContain("Task 1");
        results.Select(t => t.Title).ShouldContain("Task 2");
    }

    [Fact]
    public async Task HandleAsync_FilterByCompleted_ReturnsOnlyCompletedTasks()
    {
        await SeedTasksAsync(
            ("Incomplete", _projectId, false),
            ("Complete", _projectId, true));

        var query = new GetTasksQuery(_projectId, IsCompleted: true);
        var results = await _handler.HandleAsync(query);

        results.ShouldHaveSingleItem();
        results[0].Title.ShouldBe("Complete");
    }

    private async Task SeedTasksAsync(
        params (string Title, Guid ProjectId, bool IsCompleted)[] tasks)
    {
        foreach (var (title, projectId, isCompleted) in tasks)
        {
            _db.Tasks.Add(new TaskEntity
            {
                Id = Guid.NewGuid(),
                Title = title,
                ProjectId = projectId,
                IsCompleted = isCompleted,
                CreatedAt = DateTimeOffset.UtcNow
            });
        }
        await _db.SaveChangesAsync();
    }
}
```

## 集成测试：覆盖 HTTP 管道

单元测试覆盖 Handler 逻辑，集成测试验证 HTTP 管道全链路是否通畅：路由、模型绑定、验证、认证、响应格式。

ASP.NET Core 的 `WebApplicationFactory<T>` 提供了一个进程内测试 HTTP 服务器，能运行完整的应用程序栈：

```csharp
// Tests/Integration/Tasks/CreateTaskIntegrationTests.cs
namespace TaskTracker.Tests.Integration.Tasks;

public sealed class CreateTaskIntegrationTests
    : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;

    public CreateTaskIntegrationTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task Post_CreateTask_Returns201WithTaskId()
    {
        // Arrange
        var client = _factory
            .WithWebHostBuilder(builder =>
            {
                builder.ConfigureTestServices(services =>
                {
                    // 替换成内存数据库
                    services.RemoveAll<DbContextOptions<AppDbContext>>();
                    services.AddDbContext<AppDbContext>(options =>
                        options.UseInMemoryDatabase($"test-{Guid.NewGuid()}"));
                });
            })
            .CreateClient();

        var projectId = await CreateProjectAsync(client);
        var request = new
        {
            Title = "Write tests",
            Description = "Test the feature slice",
            ProjectId = projectId
        };

        // Act
        var response = await client.PostAsJsonAsync("/tasks", request);

        // Assert
        response.StatusCode.ShouldBe(HttpStatusCode.Created);

        var body = await response.Content.ReadFromJsonAsync<CreateTaskResponseDto>();
        body.ShouldNotBeNull();
        body.TaskId.ShouldNotBe(Guid.Empty);
        body.Title.ShouldBe("Write tests");
        response.Headers.Location!.ToString()
            .ShouldBe($"/tasks/{body.TaskId}");
    }

    [Fact]
    public async Task Post_CreateTask_WithEmptyTitle_Returns400()
    {
        var client = CreateTestClient();
        var request = new { Title = "", ProjectId = Guid.NewGuid() };

        var response = await client.PostAsJsonAsync("/tasks", request);

        response.StatusCode.ShouldBe(HttpStatusCode.BadRequest);
    }

    private HttpClient CreateTestClient()
    {
        return _factory
            .WithWebHostBuilder(builder =>
            {
                builder.ConfigureTestServices(services =>
                {
                    services.RemoveAll<DbContextOptions<AppDbContext>>();
                    services.AddDbContext<AppDbContext>(options =>
                        options.UseInMemoryDatabase($"test-{Guid.NewGuid()}"));
                });
            })
            .CreateClient();
    }

    private static async Task<Guid> CreateProjectAsync(HttpClient client)
    {
        var response = await client.PostAsJsonAsync("/projects",
            new { Name = "Test Project" });

        response.EnsureSuccessStatusCode();
        var project = await response.Content
            .ReadFromJsonAsync<CreateProjectResponseDto>();
        return project!.ProjectId;
    }

    // 本地 DTO，避免测试与生产类型耦合
    private sealed record CreateTaskResponseDto(
        Guid TaskId, string Title, DateTimeOffset CreatedAt);
    private sealed record CreateProjectResponseDto(Guid ProjectId, string Name);
}
```

### 共享测试基础设施

多个 Feature 的集成测试通常需要同一套配置，可以提取为公共 Fixture：

```csharp
// Tests/Integration/TestWebAppFactory.cs
namespace TaskTracker.Tests.Integration;

public sealed class TestWebAppFactory : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureTestServices(services =>
        {
            services.RemoveAll<DbContextOptions<AppDbContext>>();
            services.AddDbContext<AppDbContext>(options =>
                options.UseInMemoryDatabase($"test-{Guid.NewGuid()}"));
        });
    }
}
```

各测试类通过构造函数注入这个 Fixture：

```csharp
public sealed class CompleteTaskIntegrationTests
    : IClassFixture<TestWebAppFactory>
{
    private readonly TestWebAppFactory _factory;
    private readonly HttpClient _client;

    public CompleteTaskIntegrationTests(TestWebAppFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    // ...
}
```

## 测试目录结构

测试项目的目录结构镜像主项目的 `Features/` 结构：

```
TaskTracker.Tests/
  Features/
    Tasks/
      CreateTask/
        CreateTaskHandlerTests.cs
      CompleteTask/
        CompleteTaskHandlerTests.cs
      GetTasks/
        GetTasksHandlerTests.cs
    Projects/
      CreateProject/
        CreateProjectHandlerTests.cs
  Integration/
    Tasks/
      CreateTaskIntegrationTests.cs
      CompleteTaskIntegrationTests.cs
    Projects/
      CreateProjectIntegrationTests.cs
  TestWebAppFactory.cs
```

这个结构保证了"找 Feature 代码"和"找 Feature 测试"的路径同等可预期。当 `CreateTask` 发生变化，你知道该去哪里更新测试。

## 单元测试还是集成测试？

两种测试解决的是不同层面的问题：

| 场景 | 单元测试 | 集成测试 |
|---|---|---|
| Handler 业务逻辑 | ✅ | 可选 |
| 路由（URL 映射正确） | ❌ | ✅ |
| 模型绑定（JSON 正确反序列化） | ❌ | ✅ |
| 验证（无效输入返回 400） | 可单独测 Validator | ✅ |
| 响应格式（正确 JSON 结构） | ❌ | ✅ |
| 认证（未认证返回 401） | ❌ | ✅ |
| 复杂业务逻辑，多分支 | ✅ | 可选 |
| 数据库查询返回正确数据 | ✅（内存） | 可选 |

原则：**单元测试测逻辑，集成测试测连接**。为了测一条业务规则而启动整个 HTTP 服务器是过度的；为了验证 POST 返回 201 而 mock `AppDbContext` 则是不够的。

## 测试验证逻辑

验证逻辑值得单独写单元测试，完全不涉及 HTTP 或 Handler：

```csharp
// Tests/Features/Tasks/CreateTask/CreateTaskValidatorTests.cs
namespace TaskTracker.Tests.Features.Tasks.CreateTask;

public sealed class CreateTaskValidatorTests
{
    private readonly CreateTaskValidator _validator = new();

    [Fact]
    public void Validate_ValidRequest_ReturnsSuccess()
    {
        var request = new CreateTaskRequest(
            Title: "Implement feature",
            Description: "Test it too",
            ProjectId: Guid.NewGuid());

        var result = _validator.Validate(request);

        result.IsValid.ShouldBeTrue();
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData(null)]
    public void Validate_EmptyTitle_ReturnsFailure(string? title)
    {
        var request = new CreateTaskRequest(
            Title: title!,
            Description: null,
            ProjectId: Guid.NewGuid());

        var result = _validator.Validate(request);

        result.IsValid.ShouldBeFalse();
        result.Errors.ShouldContain(
            e => e.PropertyName == nameof(CreateTaskRequest.Title));
    }
}
```

这类测试执行快，不需要数据库，同时把验证规则清晰地记录在测试名称里。

## 使用 Testcontainers 做生产级测试

EF Core 内存提供器会跳过一些 SQL 行为（约束、特定查询翻译）。如果需要生产等价的测试行为，[Testcontainers for .NET](https://dotnet.testcontainers.org/) 可以在 Docker 里跑一个真实的 SQL Server 或 PostgreSQL：

```csharp
// Tests/Integration/DatabaseFixture.cs
namespace TaskTracker.Tests.Integration;

public sealed class DatabaseFixture : IAsyncLifetime
{
    private readonly MsSqlContainer _container = new MsSqlBuilder()
        .WithImage("mcr.microsoft.com/mssql/server:2022-latest")
        .Build();

    public string ConnectionString => _container.GetConnectionString();

    public async ValueTask InitializeAsync() => await _container.StartAsync();
    public async ValueTask DisposeAsync() => await _container.DisposeAsync();
}
```

把 `WebApplicationFactory` 里的内存数据库替换成 `DatabaseFixture.ConnectionString` 即可。测试结构不变，只是数据库后端换成了真实实例。Feature Slice Handler 的构造函数显式依赖让这次切换直接而无痛。

## 常见问题

**为什么不 mock DbContext？**

Mock `DbContext` 需要配置 `DbSet<T>` 的 mock，设置复杂且脆弱。EF Core 内存提供器或 SQLite 内存模式给你一个有真实查询行为的 `DbContext`，在测试构造函数里几行就能设置好。

**如何保证测试间数据隔离？**

每个测试或测试类使用唯一数据库名（如 `Guid.NewGuid().ToString()`）。这样就不需要数据库清理代码，测试之间也不存在共享状态。

**测端点还是测 Handler？**

两者都测，但测不同的点。Handler 测试验证业务逻辑：Handler 是否正确更新了状态，是否返回了正确结果，是否处理了边界情况？集成测试验证连接：HTTP 路由是否存在，请求模型是否正确绑定，是否返回了预期的状态码？

**Feature Slice Handler 比 MediatR Handler 更好测吗？**

是的。直接实例化 Handler 类，调用 `HandleAsync`，完成。用 MediatR 时，要么 mock `IMediator`（测试意义几乎为零），要么在测试里配置真正的 mediator（增加了复杂性）。直接 Handler 是更简单的测试目标。

**测试方法怎么命名？**

非参数化测试使用 `MethodUnderTest_Condition_ExpectedResult`，例如 `HandleAsync_TaskNotFound_ReturnsFalse`。参数化测试（Theory）使用 `MethodUnderTest_ScenarioBeingExercised`，例如 `Validate_EmptyTitle_ReturnsFailure`。这样命名在 CI 里测试失败时输出可读性高。

## 参考

- [Testing Feature Slices in C#: Unit Tests, Integration Tests, and What to Test](https://www.devleader.ca/2026/04/21/testing-feature-slices-in-c-unit-tests-integration-tests-and-what-to-test)
- [Vertical Slice Development for Modern Teams](https://www.devleader.ca/2023/10/10/vertical-slice-development-a-comprehensive-how-to-for-modern-teams)
- [Testcontainers for .NET](https://dotnet.testcontainers.org/)
- [Testing Plugin Architectures in C#](https://www.devleader.ca/2026/04/11/testing-plugin-architectures-in-c-strategies-for-extensible-systems)
