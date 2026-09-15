---
pubDatetime: 2026-09-15T14:20:00+08:00
title: "EF Core 动态筛选排序分页：用白名单收口"
description: "列表接口一旦接受任意属性名或表达式，翻页就可能丢行、重复甚至翻译失败。本文把动态查询收成一个有界信封：白名单排序、完全唯一的排序键、页大小上限和可见的终止操作，并附在 net10.0 上跑通的完整代码与测试。"
tags: ["EF Core", ".NET 10", "C#", "LINQ", "架构"]
slug: "ef-core-dynamic-query-specification-pagination"
ogImage: "../../assets/1069/01-cover.jpg"
source: "https://www.devleader.ca/2026/09/14/dynamic-filtering-sorting-and-pagination-with-specifications"
---

一个商品列表接口如果支持 `sort=任意属性名`、并且允许调用方传一段序列化的表达式树，看起来只是「更灵活」。真正的问题会出现在三个地方：排序键由调用方决定，表达式并不会因为被接受就变得可翻译，以及在只按一个字段排序时，翻页会在并列值上跳行或重复。

Dev Leader 的 Nick Cosentino 在 [Dynamic Filtering, Sorting, and Pagination With Specifications](https://www.devleader.ca/2026/09/14/dynamic-filtering-sorting-and-pagination-with-specifications) 里给出的收口方式叫查询信封（query envelope）：调用方只能提供值，查询结构由应用自己拥有一份有限的集合来决定。

下面把这套信封完整实现一遍，并补上原文只写了结论、没有贴出来的部分——`Skip`/`Take` 和 keyset 分页各自生成的 SQL。示例面向 `net10.0`、C# 14 和 EF Core 10；我把原文的代码抄成一个测试项目在本机跑过：`Microsoft.EntityFrameworkCore.Sqlite` 还原到 10.0.12（原文标注的是 10.0.10，也就是 10.0 线的补丁差异），原文的 9 个测试用例加上我补的 3 个共 12 个全部通过，后面会贴出运行结果和实际 SQL。

## 动态查询失控的三个具体位置

把「任意」拆开看，风险并不抽象。

**任意属性名。** 反射确实能拼出 `OrderBy(x => x.某属性)`，但每公开一个属性，就多一个没有约定方向、索引和并列值处理方式的排序入口。这类接口的排序行为通常没人逐一审过。

**任意表达式。** [EF Core 的客户端求值说明](https://learn.microsoft.com/en-us/ef/core/querying/client-eval)指出，最终投影之外无法翻译的表达式会在运行时抛异常。接受任意表达式不会让它变得可翻译，只是把失败从启动时推迟到了执行时。

**只按一个字段排序。** [官方分页文档](https://learn.microsoft.com/en-us/ef/core/querying/pagination)的警告很直接：无论用哪种分页方式，排序都必须完全唯一；如果只按日期排序而多条记录日期相同，两次分页查询之间的顺序可能不一致，导致结果被跳过。文档还补了一句容易被忽略的话——关系数据库不会默认按主键排序。

这三件事的根因是同一个：调用方决定了查询结构。所以收口点在信封的边界上，而不是在表达式内部写得更小心。

## 第一步：把请求收成受校验的信封

先看请求和排序白名单。调用方只能请求 `newest`、`name`、`name-desc`、`price`、`price-desc` 这五种排序，别的字符串进不来。

```csharp
public sealed record ProductSearchRequest(
    string? Term,
    decimal? MinimumPrice,
    decimal? MaximumPrice,
    bool? IsActive,
    string? Sort,
    int PageNumber,
    int PageSize,
    bool IncludeTotalCount);

public enum ProductSort
{
    Newest,
    NameAscending,
    NameDescending,
    PriceAscending,
    PriceDescending,
}
```

规格类用私有构造函数封住，唯一的构造入口是 `Create`，它会一次性校验页码、页大小、价格区间、搜索词长度和排序标签。

```csharp
public sealed class ProductSearchSpecification
{
    public const int MaximumPageSize = 100;

    private ProductSearchSpecification(
        string? term,
        decimal? minimumPrice,
        decimal? maximumPrice,
        bool? isActive,
        ProductSort sort,
        int pageNumber,
        int pageSize,
        bool includeTotalCount)
    {
        Term = term;
        MinimumPrice = minimumPrice;
        MaximumPrice = maximumPrice;
        IsActive = isActive;
        Sort = sort;
        PageNumber = pageNumber;
        PageSize = pageSize;
        IncludeTotalCount = includeTotalCount;
    }

    public string? Term { get; }
    public decimal? MinimumPrice { get; }
    public decimal? MaximumPrice { get; }
    public bool? IsActive { get; }
    public ProductSort Sort { get; }
    public int PageNumber { get; }
    public int PageSize { get; }
    public bool IncludeTotalCount { get; }

    public static ProductSearchSpecification Create(
        ProductSearchRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);

        ValidatePageNumber(request.PageNumber, nameof(request.PageNumber));
        ValidatePageSize(request.PageSize, nameof(request.PageSize));

        if (request.MinimumPrice is < 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(request.MinimumPrice));
        }

        if (request.MaximumPrice is < 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(request.MaximumPrice));
        }

        if (request.MinimumPrice > request.MaximumPrice)
        {
            throw new ArgumentException(
                "MinimumPrice cannot exceed MaximumPrice.",
                nameof(request));
        }

        var term = string.IsNullOrWhiteSpace(request.Term)
            ? null
            : request.Term.Trim();

        if (term?.Length > 100)
        {
            throw new ArgumentException(
                "Term cannot exceed 100 characters.",
                nameof(request));
        }

        var sort = request.Sort?.Trim().ToLowerInvariant() switch
        {
            null or "" or "newest" => ProductSort.Newest,
            "name" => ProductSort.NameAscending,
            "name-desc" => ProductSort.NameDescending,
            "price" => ProductSort.PriceAscending,
            "price-desc" => ProductSort.PriceDescending,
            _ => throw new ArgumentException(
                "The requested sort field is not supported.",
                nameof(request)),
        };

        return new ProductSearchSpecification(
            term,
            request.MinimumPrice,
            request.MaximumPrice,
            request.IsActive,
            sort,
            request.PageNumber,
            request.PageSize,
            request.IncludeTotalCount);
    }

    private static void ValidatePageNumber(
        int pageNumber,
        string parameterName)
    {
        if (pageNumber < 1)
        {
            throw new ArgumentOutOfRangeException(parameterName);
        }
    }

    private static void ValidatePageSize(
        int pageSize,
        string parameterName)
    {
        if (pageSize is < 1 or > MaximumPageSize)
        {
            throw new ArgumentOutOfRangeException(parameterName);
        }
    }
}
```

排序用有限 `switch` 落到有限数量的查询形状上：

```csharp
    public IOrderedQueryable<Product> ApplyOrdering(
        IQueryable<Product> products)
    {
        return Sort switch
        {
            ProductSort.Newest => products
                .OrderByDescending(product => product.CreatedSequence)
                .ThenByDescending(product => product.Id),
            ProductSort.NameAscending => products
                .OrderBy(product => product.Name)
                .ThenBy(product => product.Id),
            ProductSort.NameDescending => products
                .OrderByDescending(product => product.Name)
                .ThenByDescending(product => product.Id),
            ProductSort.PriceAscending => products
                .OrderBy(product => product.Price)
                .ThenBy(product => product.Id),
            ProductSort.PriceDescending => products
                .OrderByDescending(product => product.Price)
                .ThenByDescending(product => product.Id),
            _ => throw new ArgumentOutOfRangeException(
                nameof(Sort),
                Sort,
                "Unsupported sort mode."),
        };
    }
```

这段代码里有三个决定值得单独说明，因为它们决定了后面能不能被 EF Core 正确翻译和缓存。

**筛选条件返回 `Expression<Func<Product, bool>>`，不是 `Func<Product, bool>`。** [`Queryable.Where`](https://learn.microsoft.com/en-us/dotnet/api/system.linq.queryable.where?view=net-10.0) 接受的是表达式树。一旦在规格里调用 `Compile()`，拿到的是内存委托，provider 需要的那棵树就没了。

**捕获标量，不手工拼 `Expression.Constant`。** [EF Core 高级性能主题](https://learn.microsoft.com/en-us/ef/core/performance/advanced-performance-topics)说明，动态构造、且常量节点会变化的表达式树会破坏查询形状缓存，并污染数据库的计划缓存。把值捕获进闭包是正常且被参数化的路径。

**五种排序就是五种形状。** 这比接受一个属性字符串要写得更多，但每种排序都有已知语义、已知方向和确定的并列值处理方式。

## 第二步：先定语义，再写表达式

可选筛选在变成表达式树节点之前，必须先有明确含义，否则不同接口会各自做出一套略有差异的假设。示例采用的语义是：

- 搜索词为 null、空字符串或纯空白，等于不做文本筛选；
- 非空搜索词先 trim，再限制在 100 个字符以内；
- 价格下限或上限为 null，表示该侧不设限；
- 下限大于上限属于非法请求；
- 上架状态为 null，表示上架和下架都要；
- 无法识别的排序标签直接拒绝，不回退到某个无关排序。

这些都是应用侧的决定。另一个产品完全可以把空搜索词视为非法、把负价格夹到 0、或让未知排序默认落到 `newest`。重要的是这个决定发生在信封创建阶段，而不是埋在 LINQ 链里。

筛选条件本身保持简单，只捕获标量再比较：

```csharp
    public Expression<Func<Product, bool>> BuildCriteria()
    {
        var term = Term;
        var minimumPrice = MinimumPrice;
        var maximumPrice = MaximumPrice;
        var isActive = IsActive;

        return product =>
            (term == null || product.Name.Contains(term)) &&
            (!minimumPrice.HasValue ||
                product.Price >= minimumPrice.Value) &&
            (!maximumPrice.HasValue ||
                product.Price <= maximumPrice.Value) &&
            (!isActive.HasValue ||
                product.IsActive == isActive.Value);
    }
```

文本搜索要额外小心。`string.Contains` 好读，但大小写敏感性、排序规则（collation）、可用函数和索引使用都是数据库的事。除非生产 provider、列排序规则和生成的 SQL 能证明，否则不要在规格里承诺「不区分大小写搜索」。如果确实需要语言级检索、重音处理、相关性排序或分词，应该单独定义一个应用自有的搜索模式，而不是让客户端传任意字符串方法进来。

把校验留在 `Create` 里还有一个直接收益：只针对请求的单元测试可以证明接受范围和排序白名单，完全不需要启动数据库；关系型测试则只需要回答一个小得多的问题——每种被接受的查询形状，在目标 provider 上能不能翻译、能不能返回预期的行。

## 第三步：让非法的分页状态无法构造

规格要求页码从 1 开始、页大小在 1 到 100 之间，偏移量计算用 `checked`：

```csharp
        var offset = checked(
            (specification.PageNumber - 1) * specification.PageSize);
```

页码足够大时，乘法会抛溢出异常，而不是回绕成一个莫名其妙的偏移量。

```csharp
    public ProductSearchSpecification WithPageNumber(int pageNumber)
    {
        ValidatePageNumber(pageNumber, nameof(pageNumber));

        return new ProductSearchSpecification(
            Term,
            MinimumPrice,
            MaximumPrice,
            IsActive,
            Sort,
            pageNumber,
            PageSize,
            IncludeTotalCount);
    }
```

因为是密封类加私有构造函数，`Create` 是唯一的初始入口，`WithPageNumber` 只在复用同一套校验之后才产出不可变副本。更严格的设计还可以把两个 `int` 换成 `PageNumber`、`PageSize` 值对象。核心是同一个：`Skip` 和 `Take` 永远不应该拿到未经审查的请求值。

## 排序必须完全唯一

每个白名单排序都以 `Id` 收尾，方向跟随主排序：

- `Name`，然后 `Id`；
- `Price`，然后 `Id`；
- `CreatedSequence`，然后 `Id`。

只按 `Name` 排序不够，因为可能有多条同名商品；只按 `Price` 排序不够，因为可能有多条同价商品；只按创建顺序也不够，因为两条记录可能拿到同一个值。示例里的 `CreatedSequence` 代表一个由应用持有的单调创建值，这样关系型样例就与 provider 特有的日期映射解耦——生产模型可以换成 `DateTimeOffset` 加唯一 ID，前提是映射和索引都验证过。

方向为什么重要：keyset 的游标谓词必须和排序用同一组字段、同一个方向，否则下一页会从错误的位置继续。

## 两种翻页：先看它们生成的 SQL

偏移分页用 `Skip` 和 `Take`：

```csharp
    public static IQueryable<ProductListItem> BuildOffsetQuery(
        IQueryable<Product> products,
        ProductSearchSpecification specification)
    {
        var filtered = products.Where(specification.BuildCriteria());
        var ordered = specification.ApplyOrdering(filtered);
        var offset = checked(
            (specification.PageNumber - 1) * specification.PageSize);

        return ordered
            .Skip(offset)
            .Take(specification.PageSize)
            .Select(product => new ProductListItem(
                product.Id,
                product.Name,
                product.Price,
                product.CreatedSequence));
    }
```

第 3 页、每页 2 条，`ToQueryString()` 在 SQLite 上给出的形状是：

```text
.param set @p1 2
.param set @p 4

SELECT "p"."Id", "p"."Name", "p"."Price", "p"."CreatedSequence"
FROM "Products" AS "p"
ORDER BY "p"."CreatedSequence" DESC, "p"."Id" DESC
LIMIT @p1 OFFSET @p
```

偏移量 4 是参数，不在 LINQ 里拼字符串——但这不影响一件事实：数据库仍然要处理被跳过的那些行，跳过越多，代价越大。页码继续放大时 SQL 形状完全一样，只是 `OFFSET` 的值更大。

keyset 分页（也叫 seek 分页）换一个思路：不再记住偏移量，而是记住上一页最后一行的那组排序值。

```csharp
public sealed record ProductListItem(
    long Id,
    string Name,
    decimal Price,
    long CreatedSequence);

public sealed record OffsetPage<T>(
    IReadOnlyList<T> Items,
    int PageNumber,
    int PageSize,
    int? TotalCount);

public sealed record ProductCursor(
    long CreatedSequence,
    long Id);

public sealed record KeysetPage<T>(
    IReadOnlyList<T> Items,
    ProductCursor? NextCursor,
    bool HasMore);

public static class ProductSearchQueries
{
    public static async Task<KeysetPage<ProductListItem>> SearchNextAsync(
        CatalogDbContext dbContext,
        ProductSearchSpecification specification,
        ProductCursor? after,
        CancellationToken cancellationToken)
    {
        if (specification.Sort != ProductSort.Newest)
        {
            throw new ArgumentException(
                "This cursor format is defined only for newest sorting.",
                nameof(specification));
        }

        IQueryable<Product> query = dbContext.Products
            .Where(specification.BuildCriteria());

        if (after is not null)
        {
            var cursorSequence = after.CreatedSequence;
            var cursorId = after.Id;

            query = query.Where(product =>
                product.CreatedSequence < cursorSequence ||
                (product.CreatedSequence == cursorSequence &&
                    product.Id < cursorId));
        }

        var candidates = await query
            .OrderByDescending(product => product.CreatedSequence)
            .ThenByDescending(product => product.Id)
            .Select(product => new ProductListItem(
                product.Id,
                product.Name,
                product.Price,
                product.CreatedSequence))
            .Take(specification.PageSize + 1)
            .ToListAsync(cancellationToken);

        var hasMore = candidates.Count > specification.PageSize;
        var items = candidates
            .Take(specification.PageSize)
            .ToArray();

        ProductCursor? nextCursor = null;
        if (hasMore && items.Length > 0)
        {
            var last = items[^1];
            nextCursor = new ProductCursor(
                last.CreatedSequence,
                last.Id);
        }

        return new KeysetPage<ProductListItem>(
            items,
            nextCursor,
            hasMore);
    }
}
```

带游标 `(CreatedSequence = 100, Id = 2)` 请求下一页时，生成的 SQL 里没有 `OFFSET`：

```text
.param set @cursorSequence 100
.param set @cursorId 2
.param set @p 3

SELECT "p"."Id", "p"."Name", "p"."Price", "p"."CreatedSequence"
FROM "Products" AS "p"
WHERE "p"."CreatedSequence" < @cursorSequence OR ("p"."CreatedSequence" = @cursorSequence AND "p"."Id" < @cursorId)
ORDER BY "p"."CreatedSequence" DESC, "p"."Id" DESC
LIMIT @p
```

`LIMIT` 的参数是 3，也就是 `PageSize + 1`：多取一行用来判断还有没有下一页。两个值得注意的细节：

- 谓词里的 `<` 和排序里的 `DESC` 必须成对出现，方向反了就会原地打转或跳过数据；
- 游标不是「页码的替代品」。不要把它跨筛选条件或排序模式复用。生产 API 应该把筛选版本和排序模式编进游标（必要时签名），返回时再校验。

两种方式的取舍很明确：

| 场景                   | 选择                     |
| ---------------------- | ------------------------ |
| 后台表格要跳到第 12 页 | 偏移分页                 |
| 列表做上一页/下一页    | keyset 分页              |
| 产品确实两种都要       | 两种都实现，各用各的契约 |

微软文档还提到一种 SQL 里更简洁的行值比较写法 `WHERE (Date, Id) > (@lastDate, @lastId)`，并说明目前还无法在 LINQ 中表达，跟踪项是 [dotnet/efcore#26822](https://github.com/dotnet/efcore/issues/26822)。

## 精确总数是另一条查询

要显示「共 2431 条」或者算出最后一页页码时，精确总数是有用的；它不是挂在列表查询上的免费元数据。`CountAsync` 会在过滤后的查询上多执行一次数据库往返。

```csharp
        var filtered = dbContext.Products
            .Where(specification.BuildCriteria());

        int? totalCount = null;
        if (specification.IncludeTotalCount)
        {
            totalCount = await filtered.CountAsync(cancellationToken);
        }

        var items = await BuildOffsetQuery(
                dbContext.Products,
                specification)
            .ToListAsync(cancellationToken);
```

这里两个 `await` 是顺序的，因为同一个 `DbContext` 不支持并行操作。顺序执行避免了并行使用上下文，但**不构成快照一致性**：count 和取页之间发生并发写入，两个数字就可能互相矛盾。真的要快照一致性，就按 [EF Core 事务指南](https://learn.microsoft.com/en-us/ef/core/saving/transactions)显式选择事务和隔离级别，并接受它带来的锁、版本存储、重试或吞吐成本。

四种常见做法：

- 界面需要精确数字，就返回精确总数；
- 无限滚动或简单下一页导航，可以不返回总数；
- 用多取一行的 `HasMore` 代替；
- 只有在新鲜度语义明确时，才用应用自有的近似值或缓存值。

「count 很便宜」或「count 很贵」都不是可以通用成立的结论。成本取决于筛选条件、索引、数据分布、provider 和数据库计划；在意的时候就到生产环境上量。

另外注意 `SearchOffsetAsync` 里 `BuildCriteria()` 被调用了两次：一次给 count，一次在 `BuildOffsetQuery` 里。两次生成的是两棵结构相同的表达式树；能这样做的原因是它捕获标量、由 provider 参数化——如果改成手工插入常量节点，值一变就是新的查询形状，缓存就失效了。

## 让 IQueryable 边界保持可见

整个链路上，筛选、排序、投影和取页范围都留在 `IQueryable<T>` 上，直到 `CountAsync` 或 `ToListAsync`。规格里不要做这些事：

- 对筛选条件调用 `Compile()`；
- 在筛选前调用 `AsEnumerable()`；
- 在排序或分页前调用 `ToList()`；
- 调用调用方提供的本地方法。

这就是查询能交给 EF Core provider 翻译的前提。反过来，`string.Contains` 的翻译和比较语义会随 provider 和排序规则变化：一个在 SQLite 上通过的测试，证明的是 SQLite 上的执行，不能证明 SQL Server、PostgreSQL 或 MySQL 上的大小写行为、索引使用和 SQL 形状。

## 关系型测试证明的是翻译和排序

纯请求测试覆盖不了排序和翻译。原文用 SQLite 内存库做关系型冒烟测试，配一个 `DbCommandInterceptor` 统计执行的 reader 命令数：

```csharp
public sealed class ReaderCommandCounter : DbCommandInterceptor
{
    public int Count { get; private set; }

    public void Reset()
    {
        Count = 0;
    }

    public override ValueTask<InterceptionResult<DbDataReader>>
        ReaderExecutingAsync(
            DbCommand command,
            CommandEventData eventData,
            InterceptionResult<DbDataReader> result,
            CancellationToken cancellationToken = default)
    {
        Count++;
        return ValueTask.FromResult(result);
    }
}
```

种子数据故意制造并列值——两条同名同创建序号的商品：

```csharp
        context.Products.AddRange(
            new Product(1, "Alpha", 10m, true, 100),
            new Product(2, "Alpha", 11m, true, 100),
            new Product(3, "Beta", 12m, true, 99),
            new Product(4, "Gamma", 13m, true, 98),
            new Product(5, "Delta", 14m, false, 97));
```

于是四个断言各自有明确目标：按名字排序时两页结果不重叠且顺序确定；按 keyset 翻页时并列的 `CreatedSequence` 不会导致重复；打开精确总数时确实产生两条 reader 命令。

```csharp
        Assert.Equal([1L, 2L], firstPage.Select(item => item.Id));
        Assert.Equal([3L, 5L], secondPage.Select(item => item.Id));
        Assert.Empty(firstPage.Select(item => item.Id)
            .Intersect(secondPage.Select(item => item.Id)));
```

我把原文这份测试代码原样抄进一个 net10.0 测试项目，另外补了三个断言（keyset 第二页的 SQL 不含 `OFFSET`、深页码仍然走 `OFFSET`、下限大于上限被拒绝），`dotnet test` 的结果是 **12 个用例全部通过**，耗时 695 毫秒（`Microsoft.EntityFrameworkCore.Sqlite` 10.0.12）。但这件事的边界要说清楚：SQLite 不是大多数应用的生产 provider。微软的[测试策略指南](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy)明确提醒 provider 之间在翻译和数据库行为上会有差异。要在生产中依赖文本搜索、排序、游标比较、count 和索引使用，就得用生产 provider 跑等价测试。

## 代价与常见取舍

这套信封的收益是可以审核的：接受的筛选和排序有清单，查询值始终是参数而不是可执行输入，每个分页查询都有完全唯一的排序，页大小在构造查询前就有上限，两种翻页方式各有明确契约，count 是否执行是显式的，取消令牌能到达终止操作。

代价同样是真实的：每加一个筛选或排序都要写代码和测试；某些产品两种分页模型都需要；游标版本化会成为 API 契约的一部分；生产 provider 的测试需要数据库基础设施；provider 特有的文本行为可能迫使你单独设计搜索。

几个常见问题：

**为什么不用反射拼 OrderBy？** 白名单 `switch` 让每种排序都有已知的类型语义、方向、并列值、索引和测试。反射可以被约束，但接受任意属性会扩大公开查询面，让翻译和确定性排序更难推理。

**页大小应该夹取还是拒绝？** 两种策略只要写清楚都能用。拒绝让非法请求暴露出来，测试也不含糊；夹取对公开客户端更友好，但可能掩盖调用方的 bug。底线是实际执行的查询必须有界。

**keyset 一定比偏移分页好吗？** 不是。keyset 适合顺序导航，但难以支持随机跳页；界面真的需要页码导航时，偏移分页依然是合适的选择。

**编译后的谓词能让 EF Core 筛选更快吗？** 编译表达式得到的是内存执行的委托，同时丢掉了 EF Core 翻译所需的表达式树。把表达式留在 `IQueryable<T>` 上，编译委托留给孤立的内存测试。

## 结论

安全的动态查询不是「接受任意查询代码」，而是接受已知的值、映射到已知的筛选和排序模式、补上唯一并列键、给页大小设上限，并让执行保持可见。

偏移分页和 keyset 分页解决的是两种不同的导航问题，精确总数解决的是第三种（显示）问题，取消令牌属于终止操作。关系型测试证明被测 provider 上的翻译行为，生产 provider 的验证才证明生产真正依赖的行为。

落地时最小的一步是：把列表接口的 `sort` 参数从自由字符串改成枚举或白名单，然后给每个排序补上唯一并列键。这两处改动不需要重构整个查询层，就能消掉最容易被用户看见的一类分页 bug。

如果你也在做 AI 助手、开发工具或 .NET 工程实践，Aide Hub 会继续分享这类「先定边界、再写实现」的落地经验。

## 参考

- [Dynamic Filtering, Sorting, and Pagination With Specifications — Nick Cosentino, Dev Leader](https://www.devleader.ca/2026/09/14/dynamic-filtering-sorting-and-pagination-with-specifications)
- [Pagination — EF Core 官方文档](https://learn.microsoft.com/en-us/ef/core/querying/pagination)
- [Client vs. Server Evaluation — EF Core 官方文档](https://learn.microsoft.com/en-us/ef/core/querying/client-eval)
- [Advanced Performance Topics — EF Core 官方文档](https://learn.microsoft.com/en-us/ef/core/performance/advanced-performance-topics)
- [Choosing a Testing Strategy — EF Core 官方文档](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy)
- [Transactions — EF Core 官方文档](https://learn.microsoft.com/en-us/ef/core/saving/transactions)
- [Queryable.Where 方法 — .NET 10 API](https://learn.microsoft.com/en-us/dotnet/api/system.linq.queryable.where?view=net-10.0)
- [Allow users to express SQL row value comparison syntax — dotnet/efcore#26822](https://github.com/dotnet/efcore/issues/26822)
