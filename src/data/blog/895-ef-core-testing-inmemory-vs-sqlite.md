---
pubDatetime: 2026-06-25T11:54:57+08:00
title: "EF Core 单元测试：InMemory vs SQLite 怎么选"
description: "数据库代码是测试里最难搞的一类。EF Core 提供了 InMemory 和 SQLite 内存模式两种轻量方案，但选错一个会让你的测试形同虚设。本文对比两种方案的适用场景、代码示例和常见陷阱，并给出可落地的决策指南。"
tags: ["C#", "EF Core", "Testing", "xUnit", "SQLite", ".NET"]
slug: "ef-core-testing-inmemory-vs-sqlite"
ogImage: "../../assets/895/01-cover.png"
source: "https://www.devleader.ca/2026/06/24/testing-with-ef-core-in-c-inmemory-vs-sqlite-for-unit-tests"
---

## 数据库测试为什么难搞

真实数据库会让测试变慢、变脆，还会把测试套件绑到 CI 里不一定可用的基础设施上。

每次跑 SQL Server 测试都要建连接、执行 DDL、插入数据、跑查询、清理。对于集成测试来说这没问题，但几百个仓储测试每个都应该在毫秒级跑完才算合理。再加上并行测试互相踩数据，最终结果就是构建不稳定，团队信任被一点一点磨掉。

EF Core 团队知道这个问题。InMemory provider 是他们的第一版答案。SQLite 内存模式是更贴近生产的答案。理解两者的取舍，是搭建一个靠谱测试策略的关键。

## 方案一：UseInMemoryDatabase

`Microsoft.EntityFrameworkCore.InMemory` 包提供了一个用 .NET 字典存储实体的 provider。没有 SQL，没有文件 I/O，只有对象。

### 搭建

先准备好 `BlogDbContext` 和实体类：

```csharp
// Package: Microsoft.EntityFrameworkCore.InMemory (v10.x)
// Package: xunit (v2.x)

public class BlogDbContext(DbContextOptions<BlogDbContext> options)
    : DbContext(options)
{
    public DbSet<Post> Posts => Set<Post>();
    public DbSet<Tag> Tags => Set<Tag>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Post>()
            .HasMany(p => p.Tags)
            .WithMany();
    }
}

public record Post
{
    public int Id { get; init; }
    public required string Title { get; init; }
    public required string Slug { get; init; }
    public bool IsPublished { get; init; }
    public DateTimeOffset PublishedAt { get; init; }
    public List<Tag> Tags { get; init; } = [];
}

public record Tag
{
    public int Id { get; init; }
    public required string Name { get; init; }
}

// 测试中：
private static BlogDbContext CreateInMemoryContext(
    string dbName = "TestDb")
{
    var options = new DbContextOptionsBuilder<BlogDbContext>()
        .UseInMemoryDatabase(dbName)
        .Options;

    return new BlogDbContext(options);
}
```

每个测试传一个唯一的 `dbName`，就能拿到一个干净的独立存储。测试之间不会互相干扰。

### 优点

- **极快。** 没有 SQL 解析、没有磁盘 I/O、没有连接池。
- **零配置。** 不需要 SQLite 原生库、不需要连接串、不需要文件路径。
- **适合逻辑测试。** 如果你在测试一个用 EF Core 做查询和过滤的服务层，InMemory 完全够用。

### 缺点——这些是真坑

这是最容易出问题的地方。InMemory provider **不是**关系型数据库。它不强制：

- **外键约束。** 你可以插入一个引用不存在的 `Tag.Id` 的 `Post`，EF Core 会毫不犹豫地保存。
- **唯一约束。** 标了 `[Index(IsUnique = true)]` 的列上插重复值？不会报错。
- **事务。** `BeginTransaction()` 能编译通过，但是一个空操作。
- **原生 SQL。** `FromSqlRaw("SELECT ...")` 运行时报错。
- **数据库生成值。** 自增能跑，但行为和 SQL Server 的 identity 列有差异。

InMemory provider 适合测试**数据访问层之上的业务逻辑**。不适合测试**仓储或数据访问代码本身**，因为约束行为和 SQL 正确性才是你要验证的东西。

## 方案二：SQLite 内存模式

SQLite 是一个真正的 SQL 引擎。它解析 SQL、强制约束（启用之后）、运行事务。把它完全跑在内存里——不落盘——可以保持测试速度，同时给你接近生产环境的数据库行为。

### 搭建：保持连接不关闭

SQLite 内存模式最常见的错误是让连接关闭。SQLite 的内存数据库在最后一个连接关闭时就被销毁。EF Core 内部会自己开关连接，所以你必须自己创建连接并在整个测试生命周期里保持它不关闭。

```csharp
// Package: Microsoft.EntityFrameworkCore.Sqlite (v10.x)
// Package: Microsoft.Data.Sqlite (v10.x)

public sealed class SqliteInMemoryFixture : IDisposable
{
    private readonly SqliteConnection _connection;

    public SqliteInMemoryFixture()
    {
        _connection = new SqliteConnection("Data Source=:memory:");
        _connection.Open();

        var options = CreateOptions();
        using var context = new BlogDbContext(options);
        context.Database.EnsureCreated();
    }

    public DbContextOptions<BlogDbContext> CreateOptions() =>
        new DbContextOptionsBuilder<BlogDbContext>()
            .UseSqlite(_connection)
            .Options;

    public BlogDbContext CreateContext() =>
        new BlogDbContext(CreateOptions());

    public void Dispose() => _connection.Dispose();
}
```

几个要点：

- `_connection.Open()` 只调一次，连接在整个 fixture 生命周期里保持打开。
- `EnsureCreated()` 从模型构建 schema。**不要**在测试里调 `Migrate()`——那需要迁移历史表和真实的迁移文件。
- 每次调 `CreateContext()` 返回一个**新的** `DbContext` 实例，但它共享同一个打开的连接，所以 schema 和种子数据在测试期间一直存在。

### 优点

- **真正的 SQL。** `FromSqlRaw` 能跑（SQLite 兼容的 SQL）。
- **强制外键约束。** EF Core 的 SQLite provider 在打开连接时自动执行 `PRAGMA foreign_keys = ON`（自 EF Core 3.x 起）。
- **事务正常工作。**
- **比 InMemory 更接近生产环境。**

### 缺点

- **SQLite 语法和 SQL Server 不同。** 如果你的生产查询用了 `JSON_VALUE`、`OPENJSON`、`STRING_AGG`（SQL Server 版语法）或者其他 SQL Server 特有函数，这些查询在 SQLite 上会挂。测试通过，不代表生产 SQL 没问题。
- **SQLite 类型亲和性**比 SQL Server 的严格类型系统要松。decimal 精度、日期存储、计算列的边界行为可能不一样。
- **原生依赖。** `Microsoft.Data.Sqlite` 包为每个平台打包了 SQLite 原生二进制文件。实际很少出问题，但值得知道。

## 用 IDbContextFactory 保证测试隔离

在生产代码里用依赖注入时，仓储和服务通常依赖 `IDbContextFactory<T>` 而不是裸的 `DbContext`。这是 Blazor Server 和后台服务的正确模式——单个长生命周期的 `DbContext` 会导致并发问题。

在测试里，你需要精确控制 `IDbContextFactory<T>` 返回什么。这里是一个轻量实现：

```csharp
public sealed class TestDbContextFactory<TContext>(
    Func<TContext> factory) : IDbContextFactory<TContext>
    where TContext : DbContext
{
    public TContext CreateDbContext() => factory();
}
```

结合 SQLite fixture：

```csharp
public sealed class SqliteTestBase : IDisposable
{
    private readonly SqliteConnection _connection;
    protected readonly IDbContextFactory<BlogDbContext> DbContextFactory;

    protected SqliteTestBase()
    {
        _connection = new SqliteConnection("Data Source=:memory:");
        _connection.Open();

        var options = new DbContextOptionsBuilder<BlogDbContext>()
            .UseSqlite(_connection)
            .Options;

        using var context = new BlogDbContext(options);
        context.Database.EnsureCreated();

        DbContextFactory = new TestDbContextFactory<BlogDbContext>(
            () => new BlogDbContext(options));
    }

    public void Dispose() => _connection.Dispose();
}
```

继承 `SqliteTestBase` 的测试类就能直接拿到一个可用的 factory。干净、可复用、整个测试套件保持一致。

## 一个完整的 xUnit 测试类

下面是一个真实的仓储测试，用了上面的基类模式。这种风格的测试能抓到真正的 bug——约束违反、查询逻辑、LINQ 过滤——而不只是验证 EF Core 本身能跑。

```csharp
public sealed class PostRepositoryTests : SqliteTestBase
{
    private readonly PostRepository _sut;

    public PostRepositoryTests()
    {
        _sut = new PostRepository(DbContextFactory);
    }

    [Fact]
    public async Task GetPublishedPostsAsync_WhenPostsExist_ReturnsOnlyPublished()
    {
        // Arrange
        await using var context = DbContextFactory.CreateDbContext();
        context.Posts.AddRange(
            new Post { Id = 1, Title = "Draft Post", Slug = "draft-post",
                IsPublished = false, PublishedAt = DateTimeOffset.UtcNow },
            new Post { Id = 2, Title = "Live Post", Slug = "live-post",
                IsPublished = true, PublishedAt = DateTimeOffset.UtcNow.AddDays(-1) },
            new Post { Id = 3, Title = "Another Live Post", Slug = "another-live-post",
                IsPublished = true, PublishedAt = DateTimeOffset.UtcNow.AddDays(-7) }
        );
        await context.SaveChangesAsync();

        // Act
        var results = await _sut.GetPublishedPostsAsync();

        // Assert
        Assert.Equal(2, results.Count);
        Assert.All(results, p => Assert.True(p.IsPublished));
    }

    [Fact]
    public async Task AddPostAsync_WithDuplicateSlug_ThrowsUniqueConstraintException()
    {
        // Arrange
        await using var context = DbContextFactory.CreateDbContext();
        context.Posts.Add(new Post { Id = 10, Title = "Existing",
            Slug = "my-slug", IsPublished = false,
            PublishedAt = DateTimeOffset.UtcNow });
        await context.SaveChangesAsync();

        // Act & Assert —— SQLite 会强制唯一索引，InMemory 不会
        await Assert.ThrowsAnyAsync<DbUpdateException>(
            () => _sut.AddPostAsync(new Post { Id = 11, Title = "Duplicate",
                Slug = "my-slug", IsPublished = false,
                PublishedAt = DateTimeOffset.UtcNow }));
    }
}
```

注意第二个测试 `AddPostAsync_WithDuplicateSlug_ThrowsUniqueConstraintException`。这个测试**在 SQLite 上通过**，但如果你用 InMemory provider，它会**静默通过而不抛异常**。这就是两者区别的一个具体案例。

## 正确播种测试数据

数据访问测试的 Arrange 步骤就是播种。用一个**独立的 context** 来播种——和被测系统用的 context 分开——避免变更追踪器污染。

```csharp
// Arrange: 用 context A 播种
await using (var seedContext = DbContextFactory.CreateDbContext())
{
    seedContext.Tags.AddRange(
        new Tag { Id = 1, Name = "csharp" },
        new Tag { Id = 2, Name = "dotnet" }
    );
    await seedContext.SaveChangesAsync();
}

// Act: 用 context B 执行（没有共享的变更追踪器）
await using var actContext = DbContextFactory.CreateDbContext();
var tags = await actContext.Tags
    .Where(t => t.Name.StartsWith("dot"))
    .ToListAsync();
```

每次操作使用独立的 context，和仓储模式在生产代码里执行的规范一致。测试里保持一致，可以防止变更追踪器返回过期的被追踪实体、掩盖真实的查询 bug。

> **注意：** 在种子数据里用显式 ID 可行但需要小心：如果后续操作用了自增，而数据库序列还没越过你设的显式 ID，就会触发重复键冲突。要么测试里统一用显式 ID，要么统一依赖自增——不要混用两种方式。

## xUnit 测试结构：Class Fixture vs IDisposable

在 xUnit 里共享 setup，有两个主要选项。

**IDisposable 在测试类上**——简单，每个测试类管理自己的 setup 和 teardown。当你需要测试类之间完全隔离时（每个类独立的 SQLite 数据库）用这个。

**IClassFixture\<T\>**——fixture 创建一次，被同一测试类的所有测试共享。当 schema 创建成本高、且测试之间不会冲突地修改共享状态时用这个。对于 SQLite 内存模式，fixture 持有打开的连接，所以 schema 在 fixture 生命周期内跨测试保持。

```csharp
public sealed class PostRepositoryTests : IClassFixture<SqliteInMemoryFixture>
{
    private readonly SqliteInMemoryFixture _fixture;

    public PostRepositoryTests(SqliteInMemoryFixture fixture)
    {
        _fixture = fixture;
    }

    [Fact]
    public async Task SomeTest()
    {
        await using var context = _fixture.CreateContext();
        // ...
    }
}
```

对于大多数仓储测试套件，class fixture + 每次操作创建新 context 的模式是最佳平衡。Schema 建一次，每个测试自己播种数据、查询独立行。

## 在测试中记录日志

测试挂了又看不出原因的时候，EF Core 的查询日志是你最好的朋友。通过 options builder 挂上：

```csharp
var options = new DbContextOptionsBuilder<BlogDbContext>()
    .UseSqlite(_connection)
    .LogTo(Console.WriteLine, LogLevel.Information)
    .EnableSensitiveDataLogging()
    .Options;
```

`LogTo` 把生成的 SQL 写到 `Console.WriteLine`，xUnit 会自动捕获并放入测试输出。你会看到 EF Core 实际生成了什么 SQL，以及在哪一步出了问题。

## 集成测试：什么时候需要真数据库

InMemory 和 SQLite 的测试覆盖了大部分场景，但它们不能替代对真实数据库引擎的集成测试。

在 CI 里对真实 SQL Server 或 PostgreSQL 跑集成测试，用来验证：

- **迁移正确性。** `EnsureCreated()` 和真正的 `Migrate()` 产出的 schema 不同。迁移必须在真实引擎上测试。
- **SQL Server 特有查询。** `FromSqlRaw` 配合 T-SQL、`JSON_VALUE`、窗口函数、全文搜索。
- **性能特征。** 查询计划、索引使用、执行时间——只有真实引擎、真实数据量下才有意义。
- **并发和隔离级别。** Serializable vs read committed 的行为是引擎层面的。

大多数 .NET 项目的实践分层：

| 测试类型                   | Provider        | 速度          | 跑在什么时候     |
| -------------------------- | --------------- | ------------- | ---------------- |
| 逻辑 / 服务测试            | InMemory        | < 1ms/test    | 每次构建         |
| 仓储 / 数据访问测试        | SQLite 内存     | 5-50ms/test   | 每次构建         |
| 迁移 / SQL Server 特有测试 | 真实 SQL Server | 500ms-5s/test | PR CI 或 nightly |

## 常见坑

### 测试间共用 DbContext

永远不要在测试间复用同一个 `DbContext` 实例。变更追踪器持有它见过所有实体的引用。第二个测试会带着过期的被追踪实体、断裂的导航属性、以及反映内存缓存而非真实数据库状态的查询结果开始。

始终在每个逻辑操作开头调 `CreateDbContext()`。

### 忘记 EnsureDeleted

如果你用的是命名 InMemory 数据库（不是 SQLite），且测试在同一个进程里跑，InMemory 数据库会在同进程的测试运行间持续存在。在 teardown 里加 `EnsureDeleted()`，或者每个测试用唯一名称：

```csharp
var dbName = $"TestDb_{Guid.NewGuid()}";
var options = new DbContextOptionsBuilder<BlogDbContext>()
    .UseInMemoryDatabase(dbName)
    .Options;
```

用唯一名称，不需要 teardown 逻辑就能防止测试间渗透。GC 会处理清理。

### 在测试中使用 EF Core Migrations

`context.Database.Migrate()` 会跑迁移历史检查，依赖 `__EFMigrationsHistory` 表。这个表在全新的 InMemory 或 SQLite 数据库里不存在，除非你手动创建了它。在测试里用 `EnsureCreated()`，它从当前模型快照直接创建完整 schema，没有迁移追踪开销。

### 异步测试忘了 await

EF Core 的异步方法（`SaveChangesAsync`、`ToListAsync`、`FirstOrDefaultAsync`）返回 `Task` 或 `ValueTask`。在 xUnit 异步测试里忘了 `await` 会导致测试总是通过——因为它们根本没执行。把测试方法标记为 `async Task`，然后 await 所有异步调用。

## 决策指南

回到实际选择上，这里有一条决策路径：

- **测试业务逻辑或服务类**（恰好用到 EF Core）？用 `UseInMemoryDatabase`。它快、简单，不强制 SQL 约束不影响数据层之上的逻辑测试。
- **测试仓储方法、查询正确性或约束行为**？用 SQLite 内存模式。你得到一个真正的 SQL 引擎，而且配置成本几乎为零。
- **测试迁移、SQL Server 特有查询或生产级数据量**？在 CI 里打真实数据库。没有替代方案。

## 小结

EF Core 单元测试不一定要连真实数据库，也不一定要在 CI 里维护完整的 SQL Server 实例。InMemory provider 和 SQLite 内存模式组合起来，能覆盖绝大多数测试场景——快速、确定性、没有基础设施依赖。

在数据层之上用 InMemory 测逻辑。在仓储和数据访问层用 SQLite 内存模式测约束行为和 SQL 正确性。让 `IDbContextFactory<T>` 模式在测试和生产代码之间保持一致。把真实数据库的集成测试留给迁移、SQL Server 特有查询和性能验证。

把这几层搞对，你的测试套件才会变成一个你真正信得过的安全网。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Testing with EF Core in C#: In-Memory vs SQLite for Unit Tests — Dev Leader](https://www.devleader.ca/2026/06/24/testing-with-ef-core-in-c-inmemory-vs-sqlite-for-unit-tests)
- [How Dependency Injection Containers Use Reflection Internally in C#](https://www.devleader.ca/2026/05/26/how-dependency-injection-containers-use-reflection-internally-in-c)
- [LINQ Filtering in C# — Where, Any, All, Contains and OfType](https://www.devleader.ca/2026/05/08/linq-filtering-in-c-where-any-all-contains-and-oftype)
- [LINQ in C#: Complete Guide to Language Integrated Query (.NET 6-9)](https://www.devleader.ca/2026/05/07/linq-in-c-complete-guide-to-language-integrated-query-net-6-9)
- [When to Use Facade Pattern in C# — Decision Guide With Examples](https://www.devleader.ca/2026/04/30/when-to-use-facade-pattern-in-c-decision-guide-with-examples)
- [Logging in .NET: The Complete Developer's Guide](https://www.devleader.ca/2026/07/03/logging-in-net-the-complete-developers-guide)
