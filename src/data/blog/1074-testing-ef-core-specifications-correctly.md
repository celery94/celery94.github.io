---
pubDatetime: 2026-09-20T08:54:52+08:00
title: "别让 InMemory 冒充 EF Core 翻译证明"
description: "规范测试分成谓词含义、应用接线与数据库翻译三层证据。本文用 .NET 10 与 EF Core 10 的 xUnit 代码说明每层能证明什么，并补一份可跨提供程序复用的生产库契约测试。"
tags: ["EF Core", "xUnit", ".NET", "Specification Pattern", "测试策略"]
slug: "testing-ef-core-specifications-correctly"
ogImage: "../../assets/1074/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/18/how-to-test-c-and-ef-core-specifications-correctly"
---

一个用 `Compile()` 编出来的谓词，在内存里返回了正确的 `true`。这条测试绿了，然后你把同一份条件交给生产库，SQL 翻译失败、排序规则不同、字符串比较结果相反。测试从头到尾没撒过谎，是你把它的结论用错了地方。

Nick Cosentino 在 [How to Test C# and EF Core Specifications Correctly](https://www.devleader.ca/2026/09/18/how-to-test-c-and-ef-core-specifications-correctly) 里把这件事归结为一个判断：写 xUnit 测试不难，难的是说清一条通过的测试到底证明了什么。本文按「证明层级 → 纯谓词 → 应用接缝 → 关系型执行 → 生产库契约」重排他的论证，并补上原文没展开的两处落地细节：`StringComparison` 在 SQL 里其实不起作用，以及一份可以同时跑 SQLite 和 SQL Server 的共享契约测试。

## 先区分三种「规范」，再决定测什么

同一个词在代码库里往往指三样东西，混着用，测试断言的边界就说不清了：

- **纯领域规范**：对内存里的候选对象返回 `bool`，不碰数据库。
- **表达式规范**：暴露 `Expression<Func<T, bool>>`，交给 `IQueryable<T>` 的提供程序。
- **完整查询信封**：除了条件，还带排序、投影、`Include`、跟踪行为、分页。

前两种都叫规范，但证据要求不同。纯谓词压根没有「翻译」这个命题；表达式规范有；查询信封更多，因为排序、投影和加载策略都会改变结果。

原文明确定了一条实操规则：**在能证明该命题的最低层级上测试，只有当命题跨过边界时才加更高一层**。映射关系如下：

| 被测命题                                   | 最少需要的证明                      |
| ------------------------------------------ | ----------------------------------- |
| 领域规则按预期接受与拒绝                   | 纯单元测试                          |
| AND / OR / NOT 保持预期布尔含义            | 真值表与代数律单元测试              |
| 用例构造并传出了预期的规范                 | 应用层或仓储接缝测试                |
| 求值器在物化前应用了条件                   | 求值器测试                          |
| EF Core 能翻译该条件                       | 关系型提供程序执行测试              |
| 字符串、空值、日期、排序规则语义与生产一致 | 生产提供程序测试                    |
| 关键查询发出预期形状                       | 生成 SQL 或命令断言，外加关系型执行 |

微软的 [EF Core 测试策略指引](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy) 把这条限制写得很直白：针对测试替身通过的测试，不能保证对生产数据库系统也有相同行为。规范模式正好会放大这个错觉——抽象层让提供程序显得比实际更远。

## 纯谓词就老老实实测布尔语义

纯领域规范应该小、确定、不依赖 EF Core。正例、反例、边界、空值策略都放这里，布尔组合也放这里。

下面这段生产代码来自原文，目标框架 .NET 10，启用了可空引用类型：

```csharp
public interface IDomainSpecification<in T>
{
    bool IsSatisfiedBy(T candidate);
}

public sealed class MinimumPriceSpecification(decimal minimum)
    : IDomainSpecification<Product>
{
    public bool IsSatisfiedBy(Product candidate)
    {
        ArgumentNullException.ThrowIfNull(candidate);

        return candidate.Price >= minimum;
    }
}

public sealed class AndSpecification<T>(
    IDomainSpecification<T> left,
    IDomainSpecification<T> right) : IDomainSpecification<T>
{
    public bool IsSatisfiedBy(T candidate)
    {
        ArgumentNullException.ThrowIfNull(candidate);

        return left.IsSatisfiedBy(candidate) &&
            right.IsSatisfiedBy(candidate);
    }
}
```

`OrSpecification` 与 `NotSpecification` 结构相同，另外配一个委托适配器 `DelegateSpecification<T>` 方便在测试里构造任意真假值。

测试要描述规则，而不是描述测试框架：

```csharp
public sealed class DomainSpecificationTests
{
    [Theory]
    [InlineData(99, false)]
    [InlineData(100, true)]
    [InlineData(101, true)]
    public void IsSatisfiedBy_PriceAroundBoundary_ReturnsExpectedResult(
        int price,
        bool expected)
    {
        var product = new Product(Guid.NewGuid(), "HW-100", price, true);
        var specification = new MinimumPriceSpecification(100m);

        Assert.Equal(expected, specification.IsSatisfiedBy(product));
    }

    [Fact]
    public void IsSatisfiedBy_NullCandidate_ThrowsArgumentNullException()
    {
        var specification = new MinimumPriceSpecification(100m);

        Assert.Throws<ArgumentNullException>(
            () => specification.IsSatisfiedBy(null!));
    }

    [Theory]
    [InlineData(false, false)]
    [InlineData(false, true)]
    [InlineData(true, false)]
    [InlineData(true, true)]
    public void BooleanComposition_AllInputs_ObeysBooleanLaws(
        bool leftValue,
        bool rightValue)
    {
        var candidate = new object();
        var left = new DelegateSpecification<object>(_ => leftValue);
        var right = new DelegateSpecification<object>(_ => rightValue);
        var alwaysTrue = new DelegateSpecification<object>(_ => true);
        var alwaysFalse = new DelegateSpecification<object>(_ => false);

        Assert.Equal(
            leftValue && rightValue,
            new AndSpecification<object>(left, right)
                .IsSatisfiedBy(candidate));
        Assert.Equal(
            leftValue || rightValue,
            new OrSpecification<object>(left, right)
                .IsSatisfiedBy(candidate));
        Assert.Equal(
            leftValue,
            new AndSpecification<object>(left, alwaysTrue)
                .IsSatisfiedBy(candidate));
        Assert.Equal(
            leftValue,
            new OrSpecification<object>(left, alwaysFalse)
                .IsSatisfiedBy(candidate));
        Assert.Equal(
            leftValue,
            new NotSpecification<object>(new NotSpecification<object>(left))
                .IsSatisfiedBy(candidate));

        var notAnd = new NotSpecification<object>(
            new AndSpecification<object>(left, right));
        var deMorgan = new OrSpecification<object>(
            new NotSpecification<object>(left),
            new NotSpecification<object>(right));

        Assert.Equal(
            notAnd.IsSatisfiedBy(candidate),
            deMorgan.IsSatisfiedBy(candidate));
    }
}
```

这组测试确实有价值：它锁住了价格边界、写明了空值策略、跑完四种布尔组合，还验证了双重否定和一条德摩根律。但它没有碰过 `IQueryable<T>`、EF 提供程序、SQL、排序规则或数据库空值语义。把这段测试的绿灯当成「查询没问题」，就是层级错配。

## 应用接缝要返回具体结果，不要返回 IQueryable

用例测试只该回答一个问题：这段业务逻辑有没有构造出预期条件，并把它交给了数据访问边界。命题只涉及编排时，不需要真数据库。

接缝的返回类型值得较真。微软 [Testing without your production database system](https://learn.microsoft.com/en-us/ef/core/testing/testing-without-the-database) 里给了理由：如果仓储返回 `IQueryable<T>`，调用方仍然能在外面继续组合操作符，EF Core 就还得参与翻译，替身也就没有真正替换掉数据访问行为。

```csharp
public interface IQuerySpecification<T>
{
    Expression<Func<T, bool>> Criteria { get; }
}

public sealed record QuerySpecification<T>(
    Expression<Func<T, bool>> Criteria) : IQuerySpecification<T>;

public sealed record ProductSummary(Guid Id, string Sku);

public interface IProductReader
{
    Task<IReadOnlyList<ProductSummary>> ListAsync(
        IQuerySpecification<Product> specification,
        CancellationToken cancellationToken);
}

public sealed class FindActiveProducts(IProductReader productReader)
{
    public Task<IReadOnlyList<ProductSummary>> ExecuteAsync(
        decimal minimumPrice,
        CancellationToken cancellationToken)
    {
        var specification = new QuerySpecification<Product>(
            product => product.IsActive && product.Price >= minimumPrice);

        return productReader.ListAsync(specification, cancellationToken);
    }
}
```

测试里用 `InMemoryProductReader` 实现这个接口，把 `ListAsync` 的结果先物化成 `IReadOnlyList<ProductSummary>`；用例断言单条结果的 `Id`，并检查 `LastSpecification` 不为空，确认规范真的传了过去。

注意最后一句：即使条件以表达式树的形式存着，这个测试依然没有证明 EF 能翻译它。求值发生的地方是 LINQ to Objects。表达式树仅仅是被当参数传了一圈。

## 翻译命题只能在关系型提供程序上立项

只有当关系型提供程序真的接收并执行表达式时，才出现了「EF Core 能不能翻译」这个命题。`IQueryable<T>` 同时携带表达式和提供程序，枚举时执行交给提供程序；而 `Compile()` 会把表达式变成普通 .NET 委托，从此按 CLR 语义运行。编译过的谓词再正确，也不是 EF 证据。

原文用 EF Core 10.0.10 配 SQLite 内存库做关系型冒烟测试：检查生成的 SQL、执行命令、断言结果，并数一次 reader 命令。同一组测试里还放了一个必然失败的用例。

```csharp
public sealed class ReaderCommandCounter : DbCommandInterceptor
{
    private int _readerCommands;

    public int ReaderCommands => Volatile.Read(ref _readerCommands);

    public void Reset() => Interlocked.Exchange(ref _readerCommands, 0);

    public override ValueTask<InterceptionResult<DbDataReader>>
        ReaderExecutingAsync(
            DbCommand command,
            CommandEventData eventData,
            InterceptionResult<DbDataReader> result,
            CancellationToken cancellationToken = default)
    {
        Interlocked.Increment(ref _readerCommands);

        return ValueTask.FromResult(result);
    }
}

[Fact]
public async Task Query_TranslatableCriteria_ExecutesExpectedCommand()
{
    var counter = new ReaderCommandCounter();
    await using var connection = new SqliteConnection("Data Source=:memory:");
    await connection.OpenAsync(CancellationToken.None);

    var options = new DbContextOptionsBuilder<ProductDbContext>()
        .UseSqlite(connection)
        .AddInterceptors(counter)
        .Options;

    await using var db = new ProductDbContext(options);
    await db.Database.EnsureCreatedAsync(CancellationToken.None);
    db.Products.AddRange(
        new Product(Guid.NewGuid(), "HW-100", 150m, true),
        new Product(Guid.NewGuid(), "HW-200", 50m, true));
    await db.SaveChangesAsync(CancellationToken.None);

    var specification = new QuerySpecification<Product>(
        product => product.IsActive && product.Price >= 100m);
    var query = db.Products
        .Where(specification.Criteria)
        .OrderBy(product => product.Id);

    var sql = query.ToQueryString();
    counter.Reset();
    var rows = await query.ToListAsync(CancellationToken.None);

    Assert.Contains("WHERE", sql, StringComparison.OrdinalIgnoreCase);
    Assert.Contains("IsActive", sql, StringComparison.OrdinalIgnoreCase);
    Assert.Single(rows);
    Assert.Equal(1, counter.ReaderCommands);
}
```

两个细节值得单独说。

第一，`ToQueryString()` 的字符串检查是辅助证据，不是终点。[EF Core 10 的 API 文档](https://learn.microsoft.com/en-us/dotnet/api/microsoft.entityframeworkcore.entityframeworkqueryableextensions.toquerystring?view=efcore-10.0) 把它描述为调试用的文本，不一定能直接执行。所以断言里既看字符串，也真的跑一次查询。

第二，原作者刻意放了一个失败用例：把自定义 CLR 辅助方法放进 `Where`，断言执行时抛 `InvalidOperationException`。

```csharp
public static class ProductRules
{
    public static bool HasRequiredPrefix(string sku, string prefix)
    {
        return sku.StartsWith(prefix, StringComparison.OrdinalIgnoreCase);
    }
}

[Fact]
public async Task Query_CustomClrMethodInFilter_ThrowsOnExecution()
{
    // ... 与上例相同的链接与选项配置，不插入数据 ...

    var specification = new QuerySpecification<Product>(
        product => ProductRules.HasRequiredPrefix(product.Sku, "HW-"));
    var query = db.Products.Where(specification.Criteria);

    await Assert.ThrowsAsync<InvalidOperationException>(
        () => query.ToListAsync(CancellationToken.None));
}
```

这条测试证明的不是「查询没问题」，而是「测试套件抓得住翻译失败」。按 [客户端与服务器端求值行为](https://learn.microsoft.com/en-us/ef/core/querying/client-eval) 的说明，EF Core 允许在顶层投影里做客户端求值，但 `Where` 里出现无法翻译的表达式会在运行时抛异常。没有这条测试，一套全绿的套件无法区分「都翻译成功了」和「断言太弱，什么都测不出来」。

顺带一个原文提到、但值得展开的点：`StringComparison` 是 CLR 概念，SQL 里没有对应参数。SQL Server 提供程序把 `stringValue.StartsWith(value)` 翻译成 `@stringValue LIKE @value + N'%'`，大小写是否敏感取决于列上的排序规则，而不是 C# 枚举值。也就是说，`ProductRules.HasRequiredPrefix` 里写的 `OrdinalIgnoreCase` 在翻译路径上并不生效——真正的语义来自数据库配置。这正是下一节要讲的、必须由生产提供程序测试兜住的差异。

## InMemory 和 SQLite 各自证明不了什么

测试替身本身没问题，问题出在把替身的结果升格成更大的结论。

**EF Core InMemory**：[官方提供程序文档](https://learn.microsoft.com/en-us/ef/core/providers/in-memory/) 明确写着把它当数据库测试替身是 discouraged。它不关系型，不支持原始 SQL 和事务，查询类型支持更少，也不是性能替代品。好处是搭建成本低、状态容易隔离；代价是它证明不了关系型翻译、生成的 SQL、关系约束、提供程序函数、排序规则，也证明不了生产查询计划。对查询规范来说，这些代价恰好抹掉了大部分人以为自己拿到的那部分证据。

**SQLite 内存库**：它是关系型数据库，能发现不少翻译错误，也能看到生成的 SQL，比 InMemory 强得多。但它仍是另一个提供程序。[EF Core 测试策略](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy) 列举过大小写敏感性差异、不支持的提供程序专属方法、不同 SQL 方言，以及只在某一个提供程序上能跑的查询。SQLite 通过只证明 SQLite 在那条测试上的行为，不证明 SQL Server、PostgreSQL、MySQL 或 Oracle 表现相同。

平衡做法是分四步走：

1. 纯测试证明谓词含义。
2. 接缝测试证明应用编排。
3. SQLite 用作快速关系型冒烟测试。
4. 生产相关结论，跑生产数据库系统上的契约测试。

## 把生产提供程序测试当成一份明确的契约

生产提供程序测试应该无聊且可重复：只种语义边界需要的那些行；用与应用程序相同的提供程序大版本执行；用可丢弃的数据库、schema、事务策略或容器隔离数据；然后只断言在生产里真正有意义的结果。

版本这件事具体到当下：EF Core 目前稳定版是 10.0 系列，[官方发布页](https://learn.microsoft.com/en-us/ef/core/what-is-new/) 标注 EF Core 10.0 面向 .NET 10、支持到 2028 年 11 月，下一个稳定版 EF Core 11.0 计划在 2026 年 11 月。NuGet 上 `Microsoft.EntityFrameworkCore.Sqlite` 与 `Microsoft.EntityFrameworkCore.InMemory` 的最新补丁已经是 10.0.12，而原文写的是 10.0.10——提供程序包通常不跨大版本工作，测试项目要跟应用保持同一个大版本，并定期跟着补丁往上走。

值得进契约测试的场景：

- 大小写与排序规则敏感的条件。
- 可空比较与空值补偿。
- 日期、时间、JSON、空间或全文检索的提供程序函数。
- 全局查询过滤器与必需导航的连接。
- 投影的列形状。
- 唯一排序与分页行为。
- `Include`、拆分查询与预期的命令次数。
- 原始 SQL 或提供程序专属映射。

不要对每条 SQL 做逐字符快照。提供程序的补丁版本会带来无意义的格式和别名变化。断言契约里稳定的那部分：必需的谓词、连接、投影列、参数化、排序和命令次数。少数关键查询在团队愿意承担维护成本时，做一份经过评审的 SQL 快照仍然合理。

这里有个真实的取舍：生产提供程序测试要处理数据库生命周期和隔离，成本不低；换来的是任何替身都给不出的证据。微软 [Testing against your production database system](https://learn.microsoft.com/en-us/ef/core/testing/testing-with-the-database) 讨论了本地安装、容器、共享 fixture 和隔离策略。正确答案不是「把所有单元测试塞进容器」，而是「每条依赖提供程序的命题，都要有一条使用该提供程序的测试」。

### 一份共享契约，两种提供程序

不需要为每个提供程序重写一遍测试意图。需要的是一个共享契约，加上提供程序专属的设置和期望。xUnit 的抽象基类正好适合这个结构：契约断言放在基类里，子类只提供 fixture。

```csharp
public sealed class ProductDbContext(DbContextOptions<ProductDbContext> options)
    : DbContext(options)
{
    public DbSet<Product> Products => Set<Product>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Product>(entity =>
        {
            entity.HasKey(product => product.Id);
            entity.Property(product => product.Sku).HasMaxLength(64);
        });
    }
}

public abstract class SpecificationProviderContractTests
{
    protected abstract ProductDbContext CreateContext();

    protected virtual async Task SeedAsync(ProductDbContext db)
    {
        db.Products.AddRange(
            new Product(Guid.NewGuid(), "HW-100", 150m, true),
            new Product(Guid.NewGuid(), "HW-200", 50m, true));
        await db.SaveChangesAsync(CancellationToken.None);
    }

    [Fact]
    public async Task Criteria_TranslatesAndFilters_ThroughProvider()
    {
        await using var db = CreateContext();
        await db.Database.EnsureCreatedAsync(CancellationToken.None);
        await SeedAsync(db);

        var specification = new QuerySpecification<Product>(
            product => product.IsActive && product.Price >= 100m);

        var rows = await db.Products
            .Where(specification.Criteria)
            .OrderBy(product => product.Id)
            .ToListAsync(CancellationToken.None);

        var row = Assert.Single(rows);
        Assert.Equal("HW-100", row.Sku);
    }

    [Fact]
    public async Task CaseInsensitiveFilter_ReturnsExpectedRows()
    {
        await using var db = CreateContext();
        await db.Database.EnsureCreatedAsync(CancellationToken.None);
        await SeedAsync(db);

        var specification = new QuerySpecification<Product>(
            product => product.Sku.StartsWith("hw"));

        var rows = await db.Products
            .Where(specification.Criteria)
            .ToListAsync(CancellationToken.None);

        Assert.Single(rows);
    }
}
```

SQLite 实现只需要给出连接；`EnsureCreatedAsync` 负责建表，测试结束时释放连接，内存库随之消失。`Product` 的属性虽然是私有 setter，EF Core 按约定仍会映射它们，不需要额外配置：

```csharp
public sealed class SqliteSpecificationContractTests
    : SpecificationProviderContractTests, IAsyncLifetime
{
    private SqliteConnection _connection = null!;

    protected override ProductDbContext CreateContext()
    {
        var options = new DbContextOptionsBuilder<ProductDbContext>()
            .UseSqlite(_connection)
            .Options;

        return new ProductDbContext(options);
    }

    public async ValueTask InitializeAsync()
    {
        _connection = new SqliteConnection("Data Source=:memory:");
        await _connection.OpenAsync(CancellationToken.None);
    }

    public async ValueTask DisposeAsync() => await _connection.DisposeAsync();
}
```

SQL Server 实现把同样的契约指向真实数据库系统，只换 provider 和清理方式：

```csharp
public sealed class SqlServerSpecificationContractTests
    : SpecificationProviderContractTests, IAsyncLifetime
{
    private readonly string _databaseName =
        $"spec_contract_{Guid.NewGuid():N}";

    private string ConnectionString =>
        $"Server=localhost;Database={_databaseName};" +
        "Trusted_Connection=True;TrustServerCertificate=True";

    protected override ProductDbContext CreateContext()
    {
        var options = new DbContextOptionsBuilder<ProductDbContext>()
            .UseSqlServer(ConnectionString)
            .Options;

        return new ProductDbContext(options);
    }

    public Task InitializeAsync() => Task.CompletedTask;

    public async ValueTask DisposeAsync()
    {
        await using var db = CreateContext();
        await db.Database.EnsureDeletedAsync();
    }
}
```

这份契约里 `CaseInsensitiveFilter_ReturnsExpectedRows` 的期望值是故意偏心的：种子数据里的 Sku 是 `HW-100`，查询用小写 `hw` 前缀。SQLite 的默认排序规则是 `BINARY`，`LIKE` 对 ASCII 字符的大小写处理又和 SQL Server 的默认排序规则不同，所以这条断言在 SQLite 上通过与否都不该被当成生产结论，真正需要它表态的是生产库。类似的还有 PostgreSQL：EF Core 提供 `EF.Functions.ILike`，SQL Server 没有对应函数，写进共享契约就会被翻译挡住，只能放进提供程序专属测试类。

共享部分只保留两边都应该成立的行为：

- 查询确实经过提供程序执行。
- 返回了预期的行。
- 排序信封存在时，结果顺序确定。
- 投影包含预期值。
- 该查询模式下发出的命令次数符合预期。

排序规则、数据库函数、SQL 语法、索引和计划算子放进各自的提供程序测试类。SQL Server 可以断言自己的函数映射，PostgreSQL 断言自己的运算符，两边都不该塞进提供程序中立的共享契约。

这个设计同样有取舍：共享契约减少重复搭建、让缺失的提供程序覆盖一眼可见；提供程序专属测试保住语义诚实；代价是额外的 fixture 基础设施，以及决定哪些测试跑在本地编辑、哪些跑在 PR、哪些跑在慢速定时通道。原文建议分三组执行：纯规则与接缝测试随每次开发者测试运行；快速关系型冒烟测试放在能改善反馈的地方；生产提供程序契约测试作为面向数据库规范的必经交付门禁。具体分组看团队环境，但证明规则不变——如果发布声明依赖某个提供程序的行为，那个提供程序的契约必须在发布前跑过。

## 让失败用例有确定性，顺便给缺陷分类

可靠的翻译失败应该来自固定的不支持形状，而不是超时、网络抖动或本地服务没起。`Where` 里的自定义 CLR 辅助方法就是个好例子，因为 EF Core 无法把任意方法体翻译成等价 SQL。修好之后的条件应该直接在表达式树里写受支持的操作，或者改用有自己生产提供程序测试的映射函数。

失败用例还能帮忙归因。按测试层级，失败大致落在这些位置：

- 纯测试失败 → 规则逻辑或空值策略。
- 接缝测试失败 → 应用构造、委托或映射。
- SQLite 翻译失败 → 表达式本身或 SQLite 提供程序路径。
- 只在生产提供程序上失败 → 提供程序翻译或数据库语义。
- SQL 形状断言失败 → 查询构造变了。
- 命令次数失败 → 物化或加载行为变了。

这条分类之所以省时间，是因为每条测试都事先声明了自己的证明边界。一条又编译谓词、又调求值器、又开数据库、最后断言 DTO 的巨型测试并非毫无价值，只是它失败时你很难立刻说出哪一层保证破了。

## 常见问题

**编译过的谓词能证明 EF Core 翻译了吗？**
不能。`Compile()` 生成的是 .NET 委托，按 CLR 语义求值。EF Core 翻译要求表达式树留在 `IQueryable<T>` 上并被数据库提供程序处理。编译谓词测试对内存语义有价值，但不是 EF 证据。

**查询规范测试用 EF Core InMemory 够吗？**
对关系型命题不够。它可以支撑有限的编排测试，但证明不了 SQL 翻译、关系约束、事务、提供程序函数、排序规则或查询计划。

**查询执行成功就说明 SQLite 够用了吗？**
SQLite 执行成功只证明 SQLite 提供程序翻译并运行了那条查询，作为关系型冒烟测试很好。当 SQL 方言、函数、比较规则、数据类型或翻译存在差异时，它不证明生产提供程序的行为。

**每条规范测试都要断言生成的 SQL 吗？**
不用。查询形状属于契约、或回归代价高昂时才断言 SQL。纯领域测试大多不需要 SQL；关系型测试至少应该真的执行查询；关键查询可以额外检查 SQL 或命令日志。

**仓储或应用接缝测试该返回什么？**
优先返回物化结果、标量值或应用自己的结果类型。返回 `IQueryable<T>` 会让提供程序组合在接缝之外继续存活，替身也就无法可靠地替换数据访问行为。

**怎么测翻译失败又不让测试变脆？**
用一个所选提供程序确实不翻译的固定表达式形状，执行它，断言文档写明的异常类别。不要依赖超时、远端故障或数据竞争。旁边留一条修好之后可执行的查询，让提供程序安全的写法清楚可见。

## 下一步

按这几条检查现有的规范测试：

1. 每条测试写清它声明证明什么，说不出来就说明它在测别的东西。
2. 纯谓词测试里不要出现 `DbContext`；出现了就拆开。
3. 接缝接口检查返回类型，`IQueryable<T>` 换成物化结果或应用自有类型。
4. 至少为每条关键规范准备一条真的经过提供程序执行的测试，并保留一条确定性失败用例。
5. 把与生产库相关的命题抽成共享契约，在生产提供程序上跑一遍，并纳入发布门禁。

最后可以用原文的一句话自检：当一条测试通过时，你应该能不加含糊地补完「这证明了……」。如果答案里出现 EF 翻译、SQL 语义、排序规则、提供程序函数或查询计划，那这条测试必须跨过关系型提供程序边界。编译过的谓词永远跨不过去。

Aide Hub 会继续整理这类把测试断言和实际结论对齐的做法，覆盖 .NET、AI 助手和软件工程实践。如果你在项目里遇到过「测试全绿但生产查询翻车」的具体场景，欢迎把当时的表达式和提供程序差异发来交流。

## 参考

- [How to Test C# and EF Core Specifications Correctly](https://www.devleader.ca/2026/09/18/how-to-test-c-and-ef-core-specifications-correctly)（原文，Nick Cosentino）
- [Choosing a testing strategy - EF Core](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy)
- [Testing without your production database system - EF Core](https://learn.microsoft.com/en-us/ef/core/testing/testing-without-the-database)
- [Testing against your production database system - EF Core](https://learn.microsoft.com/en-us/ef/core/testing/testing-with-the-database)
- [EF Core In-Memory Database Provider](https://learn.microsoft.com/en-us/ef/core/providers/in-memory/)
- [Client vs. Server Evaluation - EF Core](https://learn.microsoft.com/en-us/ef/core/querying/client-eval)
- [EF Core releases and planning](https://learn.microsoft.com/en-us/ef/core/what-is-new/)
- [Function Mappings of the Microsoft SQL Server Provider](https://learn.microsoft.com/en-us/ef/core/providers/sql-server/functions)
- [EntityFrameworkQueryableExtensions.ToQueryString 方法](https://learn.microsoft.com/en-us/dotnet/api/microsoft.entityframeworkcore.entityframeworkqueryableextensions.toquerystring?view=efcore-10.0)
