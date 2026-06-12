---
pubDatetime: 2026-06-12T08:14:52+08:00
title: "迭代器模式 C# 实战：分页数据访问的完整实现"
description: "大部分迭代器模式教程只演示玩具级别的集合遍历。本文从一个真实生产场景出发——遍历数千条数据库记录而不一次性加载到内存——带你从零构建同步与异步两个版本的分页迭代器，集成仓储模式与依赖注入，并配有完整的 xUnit 测试。看完可以直接用在自己的数据访问层里。"
tags: ["设计模式", "CSharp", "编程"]
slug: "iterator-pattern-realworld-example-csharp"
source: "https://www.devleader.ca/2026/06/11/iterator-pattern-realworld-example-in-c-complete-implementation"
ogImage: "../../assets/872/01-cover.png"
---

大部分迭代器模式教程的做法是：写一个自定义集合，实现 `MoveNext()` 和 `Current`，遍历几个字符串，收工。这能帮人理解机制，但解决不了生产代码里真正要面对的问题——比如遍历成千上万条数据库记录，又不能一股脑全加载到内存里。

这篇文章从零构建一个**真实的迭代器模式 C# 实现**：一个分页数据访问层，业务代码用普通的 `foreach` 就能遍历，而迭代器在背后默默处理分页抓取、惰性求值和数据结束检测。读完你会拿到一套完整的、可直接编译的类——包括同步迭代器、基于 `IAsyncEnumerable<T>` 的异步版本、仓储模式集成、依赖注入注册，以及验证整套实现的 xUnit 测试。

## 问题：分页数据访问的困局

假设一个应用需要处理来自数据库或外部 API 的数千条客户记录。把所有记录一次性加载到一个列表里会吃掉大量内存——数据集大的时候几百兆也不稀奇。数据源按每页 100 条返回结果，你的应用要对每条记录逐一处理。

不用迭代器模式的话，每一处消费这些数据的代码都得自己管分页。大概长这样：

```csharp
public class OrderReportGenerator
{
    private readonly ICustomerDataSource _dataSource;

    public OrderReportGenerator(
        ICustomerDataSource dataSource)
    {
        _dataSource = dataSource;
    }

    public void GenerateReport()
    {
        int pageNumber = 0;
        const int pageSize = 100;

        while (true)
        {
            var page = _dataSource.FetchPage(
                pageNumber, pageSize);

            if (page.Count == 0)
            {
                break;
            }

            foreach (var customer in page)
            {
                ProcessCustomer(customer);
            }

            pageNumber++;
        }
    }

    private void ProcessCustomer(Customer customer)
    {
        // 报表生成逻辑
    }
}
```

这段代码的问题会随着项目规模增长而放大。分页循环和业务逻辑搅在一起，既不好读也不好测。每一个需要分页数据的地方——报表生成器、数据导出器、批量处理器——都在重复相同的 `while-true-fetch-break` 模式。

真正的痛苦在需求变更时才显现。如果每页大小要变成可配置的，你得改每一个消费者。如果数据源从基于偏移量的分页切换到基于游标的分页，每一个消费者都要重写。至于 LINQ 查询？想都别想——你没法在手动分页循环上链式调用 `.Where()` 或 `.Select()`。

迭代器模式解决这一切的办法是：把分页机制封装进一个实现了 `IEnumerable<T>` 的类里。业务代码写一个普通的 `foreach` 循环，完全不知道背后在惰性抓取分页数据。

## 设计迭代器：PaginatedEnumerable

核心思路很直接。我们需要一个实现 `IEnumerable<T>` 的类，它接受一个知道如何抓取单页数据的函数。这个类本身对数据库、API、页大小一无所知——它只管调用那个函数、产出结果，直到函数返回空页为止。

```csharp
using System.Collections;

public sealed class PaginatedEnumerable<T>
    : IEnumerable<T>
{
    private readonly Func<int, IReadOnlyList<T>> _pageFetcher;

    public PaginatedEnumerable(
        Func<int, IReadOnlyList<T>> pageFetcher)
    {
        _pageFetcher = pageFetcher
            ?? throw new ArgumentNullException(
                nameof(pageFetcher));
    }

    public IEnumerator<T> GetEnumerator()
    {
        return new PaginatedEnumerator<T>(
            _pageFetcher);
    }

    IEnumerator IEnumerable.GetEnumerator()
    {
        return GetEnumerator();
    }
}
```

`pageFetcher` 委托接收一个从零开始的页码，返回该页数据的只读列表。当列表为空时，迭代结束。这套基于委托的方案让迭代器和数据源彻底解耦——你可以传入一个查数据库的函数、调 HTTP API 的函数，或者读文件的函数。同一个 `PaginatedEnumerable<T>` 适用于任何分页数据源，一行代码都不用改。

注意这里用的是 `Func<int, IReadOnlyList<T>>`，而不是要求调用方实现某个特定接口。这让 API 极其灵活——你可以传 lambda、方法组，或者一个捕获了连接字符串、HTTP 客户端等上下文信息的闭包。

## 实现枚举器：PaginatedEnumerator

真正干活的在枚举器里。它跟踪当前页码、页内当前位置，并透明地处理跨页切换：

```csharp
using System.Collections;

public sealed class PaginatedEnumerator<T>
    : IEnumerator<T>
{
    private readonly Func<int, IReadOnlyList<T>> _pageFetcher;
    private IReadOnlyList<T> _currentPage;
    private int _pageNumber;
    private int _indexInPage;
    private bool _finished;

    public PaginatedEnumerator(
        Func<int, IReadOnlyList<T>> pageFetcher)
    {
        _pageFetcher = pageFetcher;
        _currentPage = Array.Empty<T>();
        _pageNumber = 0;
        _indexInPage = -1;
        _finished = false;
    }

    public T Current
    {
        get
        {
            if (_indexInPage < 0
                || _indexInPage >= _currentPage.Count)
            {
                throw new InvalidOperationException(
                    "Enumerator is not positioned " +
                    "on a valid element.");
            }

            return _currentPage[_indexInPage];
        }
    }

    object? IEnumerator.Current => Current;

    public bool MoveNext()
    {
        if (_finished)
        {
            return false;
        }

        _indexInPage++;

        if (_indexInPage < _currentPage.Count)
        {
            return true;
        }

        _currentPage = _pageFetcher(_pageNumber);
        _pageNumber++;
        _indexInPage = 0;

        if (_currentPage.Count == 0)
        {
            _finished = true;
            return false;
        }

        return true;
    }

    public void Reset()
    {
        _currentPage = Array.Empty<T>();
        _pageNumber = 0;
        _indexInPage = -1;
        _finished = false;
    }

    public void Dispose()
    {
        _currentPage = Array.Empty<T>();
    }
}
```

`MoveNext()` 的设计有几个关键决策。它先递增当前页内的索引，如果本页还有数据就直接返回 `true`——不需要触发新的分页请求。只有当当前页耗尽时，才调用 `_pageFetcher` 加载下一批数据。这就是惰性求值：只有消费者准备好接收更多数据时，才会真的去抓下一页。

数据结束检测依赖一个简单约定：空页表示没有更多记录。这在分页 API 和数据库查询里是常见模式。`_finished` 标志位防止在数据源耗尽后重复抓取。

`Dispose()` 方法清除对当前页的引用，让 GC 可以回收那块内存。在更复杂的场景里——比如 page fetcher 打开了数据库连接或 HTTP 流——可以扩展这里来清理那些资源。`foreach` 语句内部使用了 `try/finally`，循环结束或中途 `break` 时都会自动调用 `Dispose()`，所以这个实现很关键。

`Reset()` 方法把枚举器倒回起点。虽然大多数现代 .NET 代码不直接调用 `Reset()`，但正确实现它可以确保需要重新枚举时的行为是可预测的。

## 异步支持：IAsyncEnumerable 版本

同步版本对内存数据源和本地数据库够用，但真实世界的数据访问几乎总是异步的。当 page fetcher 需要调 HTTP API 或执行异步数据库查询时，你需要异步迭代器。C# 通过 `IAsyncEnumerable<T>` 和 `await foreach` 让这件事变得很直接。

```csharp
using System.Runtime.CompilerServices;

public sealed class AsyncPaginatedEnumerable<T>
    : IAsyncEnumerable<T>
{
    private readonly Func<int, CancellationToken,
        Task<IReadOnlyList<T>>> _pageFetcher;

    public AsyncPaginatedEnumerable(
        Func<int, CancellationToken,
            Task<IReadOnlyList<T>>> pageFetcher)
    {
        _pageFetcher = pageFetcher
            ?? throw new ArgumentNullException(
                nameof(pageFetcher));
    }

    public async IAsyncEnumerator<T> GetAsyncEnumerator(
        [EnumeratorCancellation]
        CancellationToken cancellationToken = default)
    {
        int pageNumber = 0;

        while (!cancellationToken.IsCancellationRequested)
        {
            var page = await _pageFetcher(
                pageNumber,
                cancellationToken)
                .ConfigureAwait(false);

            if (page.Count == 0)
            {
                yield break;
            }

            foreach (var item in page)
            {
                yield return item;
            }

            pageNumber++;
        }

        cancellationToken.ThrowIfCancellationRequested();
    }
}
```

异步版本走了一条和同步版本不同的路。它没有用独立枚举器类手动追踪状态，而是在 async 方法里用 C# 的 `yield return`。编译器帮我们生成状态机，省掉了手动跟踪页码和索引的模板代码。

`CancellationToken` 参数从 `await foreach` 一路透传到 page fetcher，让消费者可以随时取消迭代。`[EnumeratorCancellation]` 特性告诉编译器自动接入 `WithCancellation()` 调用传来的取消令牌。这对长时间运行的数据处理任务至关重要——你需要在应用关闭时能够优雅地停下来。

注意 page fetch 上的 `ConfigureAwait(false)` 调用。它阻止异步续延捕获同步上下文，既避免了 UI 应用中的潜在死锁，也提升了服务端代码的吞吐量。

消费异步迭代器非常干净：

```csharp
var customers = new AsyncPaginatedEnumerable<Customer>(
    async (page, token) =>
        await api.GetCustomersAsync(page, 100, token));

await foreach (var customer in customers)
{
    await ProcessCustomerAsync(customer);
}
```

调用方只需要写一个普通的 `await foreach` 循环。没有页码跟踪，没有手动异步状态管理。遍历就完事了。

## 与仓储模式集成

迭代器模式在整合进数据访问层后才真正显露威力。一个仓储可以直接返回 `IEnumerable<T>` 或 `IAsyncEnumerable<T>`，服务层消费数据时完全不知道背后在分页。

```csharp
public interface ICustomerRepository
{
    IEnumerable<Customer> GetAll();

    IAsyncEnumerable<Customer> GetAllAsync(
        CancellationToken cancellationToken = default);

    IAsyncEnumerable<Customer> GetByRegionAsync(
        string region,
        CancellationToken cancellationToken = default);
}

public sealed class CustomerRepository
    : ICustomerRepository
{
    private readonly ICustomerDataSource _dataSource;
    private const int PageSize = 100;

    public CustomerRepository(
        ICustomerDataSource dataSource)
    {
        _dataSource = dataSource;
    }

    public IEnumerable<Customer> GetAll()
    {
        return new PaginatedEnumerable<Customer>(
            pageNumber => _dataSource.FetchPage(
                pageNumber, PageSize));
    }

    public IAsyncEnumerable<Customer> GetAllAsync(
        CancellationToken cancellationToken = default)
    {
        return new AsyncPaginatedEnumerable<Customer>(
            (pageNumber, token) =>
                _dataSource.FetchPageAsync(
                    pageNumber, PageSize, token));
    }

    public IAsyncEnumerable<Customer> GetByRegionAsync(
        string region,
        CancellationToken cancellationToken = default)
    {
        return new AsyncPaginatedEnumerable<Customer>(
            (pageNumber, token) =>
                _dataSource.FetchByRegionAsync(
                    region, pageNumber, PageSize, token));
    }
}
```

仓储方法极其简洁。每个方法创建带对应分页委托的分页枚举，然后直接返回。调用方拿到的是 `IEnumerable<Customer>` 或 `IAsyncEnumerable<Customer>`——标准的 .NET 接口，可以和 `foreach`、LINQ 以及框架里任何枚举机制无缝协作。

下面是消费仓储的服务：

```csharp
public sealed class CustomerReportService
{
    private readonly ICustomerRepository _repository;

    public CustomerReportService(
        ICustomerRepository repository)
    {
        _repository = repository;
    }

    public async Task<ReportSummary> GenerateRegionReportAsync(
        string region,
        CancellationToken cancellationToken = default)
    {
        int count = 0;
        decimal totalRevenue = 0m;

        await foreach (var customer in _repository
            .GetByRegionAsync(region, cancellationToken))
        {
            count++;
            totalRevenue += customer.TotalRevenue;
        }

        return new ReportSummary(region, count, totalRevenue);
    }

    public IEnumerable<Customer> GetHighValueCustomers()
    {
        return _repository.GetAll()
            .Where(c => c.TotalRevenue > 10_000m)
            .OrderByDescending(c => c.TotalRevenue);
    }
}

public record ReportSummary(
    string Region,
    int CustomerCount,
    decimal TotalRevenue);

public record Customer(
    string Id,
    string Name,
    string Region,
    decimal TotalRevenue);
```

`GetHighValueCustomers()` 方法展示了 LINQ 如何透明地作用在分页数据上。`.Where()` 和 `.OrderByDescending()` 操作的是流经迭代器的每一条数据——不会在内存中先构建一份全部客户的中间列表。这才是迭代器模式真正的收获：消费者代码干净、可组合、内存高效，同时对底层的分页机制一无所知。

### 接入依赖注入

用 `IServiceCollection` 注册这些组件，完成集成：

```csharp
using Microsoft.Extensions.DependencyInjection;

public static class CustomerServiceRegistration
{
    public static IServiceCollection AddCustomerServices(
        this IServiceCollection services)
    {
        services.AddSingleton<
            ICustomerDataSource, DatabaseCustomerDataSource>();

        services.AddScoped<
            ICustomerRepository, CustomerRepository>();

        services.AddTransient<CustomerReportService>();

        return services;
    }
}
```

在 `Program.cs` 中：

```csharp
builder.Services.AddCustomerServices();
```

DI 容器把 `ICustomerDataSource` 解析注入到 `CustomerRepository`，再把 `CustomerRepository` 注入到 `CustomerReportService`。如果你要从数据库数据源切换到 API 数据源，只需要改一行注册代码。仓储、服务和迭代器代码完全不动。

## 测试迭代器实现

测试分页迭代器很直接，因为 `Func<int, IReadOnlyList<T>>` 委托很容易 stub。下面是 xUnit 测试覆盖关键场景：

```csharp
using Xunit;

public sealed class PaginatedEnumerableTests
{
    [Fact]
    public void Enumerate_MultiplePages_ReturnsAllItems()
    {
        var pages = new Dictionary<int, IReadOnlyList<int>>
        {
            [0] = new[] { 1, 2, 3 },
            [1] = new[] { 4, 5, 6 },
            [2] = Array.Empty<int>()
        };

        var enumerable = new PaginatedEnumerable<int>(
            page => pages.GetValueOrDefault(
                page, Array.Empty<int>()));

        var result = enumerable.ToList();

        Assert.Equal(
            new[] { 1, 2, 3, 4, 5, 6 },
            result);
    }

    [Fact]
    public void Enumerate_EmptyFirstPage_ReturnsEmpty()
    {
        var enumerable = new PaginatedEnumerable<int>(
            _ => Array.Empty<int>());

        var result = enumerable.ToList();

        Assert.Empty(result);
    }

    [Fact]
    public void Enumerate_SinglePage_ReturnsPageItems()
    {
        var pages = new Dictionary<int, IReadOnlyList<int>>
        {
            [0] = new[] { 10, 20, 30 },
            [1] = Array.Empty<int>()
        };

        var enumerable = new PaginatedEnumerable<int>(
            page => pages.GetValueOrDefault(
                page, Array.Empty<int>()));

        var result = enumerable.ToList();

        Assert.Equal(new[] { 10, 20, 30 }, result);
    }

    [Fact]
    public void Enumerate_EarlyBreak_StopsFetching()
    {
        int maxPageFetched = -1;

        var enumerable = new PaginatedEnumerable<int>(
            page =>
            {
                maxPageFetched = page;
                return new[] { page * 10 };
            });

        var result = new List<int>();

        foreach (var item in enumerable)
        {
            result.Add(item);

            if (result.Count >= 2)
            {
                break;
            }
        }

        Assert.Equal(new[] { 0, 10 }, result);
        Assert.True(maxPageFetched <= 2);
    }

    [Fact]
    public void Enumerate_WithLinq_FiltersCorrectly()
    {
        var pages = new Dictionary<int, IReadOnlyList<int>>
        {
            [0] = new[] { 1, 2, 3, 4 },
            [1] = new[] { 5, 6, 7, 8 },
            [2] = Array.Empty<int>()
        };

        var enumerable = new PaginatedEnumerable<int>(
            page => pages.GetValueOrDefault(
                page, Array.Empty<int>()));

        var evens = enumerable
            .Where(x => x % 2 == 0)
            .ToList();

        Assert.Equal(new[] { 2, 4, 6, 8 }, evens);
    }
}
```

异步版本测试：

```csharp
using Xunit;

public sealed class AsyncPaginatedEnumerableTests
{
    [Fact]
    public async Task EnumerateAsync_MultiplePages_ReturnsAllItems()
    {
        var pages = new Dictionary<int, IReadOnlyList<int>>
        {
            [0] = new[] { 1, 2, 3 },
            [1] = new[] { 4, 5 },
            [2] = Array.Empty<int>()
        };

        var enumerable = new AsyncPaginatedEnumerable<int>(
            (page, _) => Task.FromResult(
                pages.GetValueOrDefault(
                    page,
                    (IReadOnlyList<int>)Array.Empty<int>())));

        var result = new List<int>();

        await foreach (var item in enumerable)
        {
            result.Add(item);
        }

        Assert.Equal(
            new[] { 1, 2, 3, 4, 5 },
            result);
    }

    [Fact]
    public async Task EnumerateAsync_EmptySource_ReturnsEmpty()
    {
        var enumerable = new AsyncPaginatedEnumerable<int>(
            (_, _) => Task.FromResult(
                (IReadOnlyList<int>)Array.Empty<int>()));

        var result = new List<int>();

        await foreach (var item in enumerable)
        {
            result.Add(item);
        }

        Assert.Empty(result);
    }

    [Fact]
    public async Task EnumerateAsync_Cancellation_StopsIteration()
    {
        var cts = new CancellationTokenSource();
        int pagesRequested = 0;

        var enumerable = new AsyncPaginatedEnumerable<int>(
            (page, token) =>
            {
                pagesRequested++;
                token.ThrowIfCancellationRequested();
                return Task.FromResult(
                    (IReadOnlyList<int>)new[] { page });
            });

        var result = new List<int>();

        await Assert.ThrowsAsync<OperationCanceledException>(
            async () =>
            {
                await foreach (var item in enumerable
                    .WithCancellation(cts.Token))
                {
                    result.Add(item);

                    if (result.Count >= 2)
                    {
                        cts.Cancel();
                    }
                }
            });

        Assert.True(result.Count >= 2);
    }

    [Fact]
    public async Task EnumerateAsync_SinglePage_ReturnsItems()
    {
        var pages = new Dictionary<int, IReadOnlyList<string>>
        {
            [0] = new[] { "alpha", "beta" },
            [1] = Array.Empty<string>()
        };

        var enumerable = new AsyncPaginatedEnumerable<string>(
            (page, _) => Task.FromResult(
                pages.GetValueOrDefault(
                    page,
                    (IReadOnlyList<string>)
                        Array.Empty<string>())));

        var result = new List<string>();

        await foreach (var item in enumerable)
        {
            result.Add(item);
        }

        Assert.Equal(
            new[] { "alpha", "beta" },
            result);
    }
}
```

这些测试覆盖了分页迭代器最重要的场景。多页测试验证不同页的数据被无缝拼接在一起。空数据源测试确认迭代器能优雅处理零条记录。提前终止测试证明惰性求值确实生效——消费者不需要的页根本不会被抓取。LINQ 测试确认标准查询操作符能在分页枚举上正确组合。

取消测试对异步版本尤其重要。它验证 `CancellationToken` 确实透传到了 page fetcher，并且在请求取消时迭代会立即停止。在生产环境里，这正是让批处理作业在应用关闭时能够干净退出所需要的。

## 什么时候用迭代器做数据访问

分页迭代器方式最适用的是：数据集大到不适合一次性加载，但处理逻辑需要逐条对待每项数据。数据库记录导出、API 数据同步、日志文件处理、ETL 管道都是很好的候选场景。

当你需要通过索引随机访问数据项，或者整个集合必须驻留在内存来进行排序或分组操作时，这个模式就不太合适了。那种情况下，不如直接把数据加载到列表里操作。关键问题是：你的消费者是否按顺序处理数据——如果是，迭代器模式可以几乎零成本地带来内存效率和干净的抽象。

要注意的一个点是**多次枚举**。因为 `PaginatedEnumerable<T>` 惰性抓取数据，遍历它两次意味着抓取所有页两次。如果需要多次迭代，先调 `.ToList()` 把结果物化。这和 LINQ-to-Objects 的延迟执行是一样的取舍——解决方案也一样。

迭代器模式和其他设计模式也能很好地组合。你可以用适配器模式把不同的分页 API 规范化为统一的分页抓取委托，用代理模式在 page fetcher 周围加上缓存、日志或重试逻辑而不改动迭代器本身，或者用桥接模式在需要支持多种后端时把迭代抽象和数据源实现分开。

## 常见问题

### yield return 和手动实现 IEnumerator 有什么区别？

C# 的 `yield return` 关键字是编译器对迭代器模式的内建支持。当你写一个带 `yield return` 的方法时，编译器会生成一个实现了 `IEnumerator<T>` 的状态机。本文中手写的 `PaginatedEnumerator<T>` 给了你对状态的显式控制——页码跟踪、资源清理、重置行为——这些事 `yield return` 是隐式处理的。异步版本我们用了 `yield return`，因为编译器生成的状态机能干净地处理异步复杂度。

### 能在分页迭代器上用 LINQ 吗？

可以。因为 `PaginatedEnumerable<T>` 实现了 `IEnumerable<T>`，所有 LINQ 扩展方法都能直接用。`.Where()`、`.Select()`、`.Take()`、`.Skip()`、`.Aggregate()` 都能在惰性迭代器上组合，不会物化整个数据集。但要小心 `.OrderBy()` 和 `.GroupBy()`——它们需要消费整个序列才能产出结果，这会抵消惰性求值的优势。

### page fetcher 抛出异常会怎样？

异常会从 `MoveNext()`（异步版本从 `await foreach` 循环）传播到消费者的 `foreach` 代码块。因为 `foreach` 内部使用 `try/finally`，枚举器的 `Dispose()` 方法仍然会被调用。如果你需要重试逻辑，应该在 page-fetching 委托那一层包装，而不是在枚举器里加重试——这样能让迭代器保持干净，重试策略也可配置。

### 怎么处理基于游标的分页而不是页码分页？

把 `Func<int, IReadOnlyList<T>>` 委托替换成同时返回数据和续传令牌的版本。比如用 `Func<string?, (IReadOnlyList<T> Items, string? NextCursor)>`，其中 `null` 游标表示没有更多页。枚举器跟踪游标而不是页码。消费者那侧 API 完全不变——不管底层分页怎么实现，`foreach` 都一样用。

### 迭代器模式线程安全吗？

单个枚举器实例不是线程安全的，不应该跨线程共享。每次 `foreach` 循环都会通过 `GetEnumerator()` 拿到自己的枚举器实例，所以同一个 `PaginatedEnumerable<T>` 上的并发 `foreach` 循环没问题——它们各自维护独立的状态。如果 page-fetching 委托访问了共享资源，那个委托需要自己做同步。

### 数据库访问该用 IEnumerable 还是 IAsyncEnumerable？

对任何 I/O 绑定的数据源都应该用 `IAsyncEnumerable<T>`。数据库查询、HTTP API 调用、文件读取都应该用异步版本，避免阻塞线程。把同步的 `IEnumerable<T>` 留到内存数据源、CPU 绑定的转换、或者分页数据已经缓存好了的场景。在 Web 应用中，用同步 I/O 阻塞线程池线程会降低服务器处理并发请求的能力。

### 和 EF Core 的流式查询相比怎么样？

Entity Framework Core 可以通过 `AsAsyncEnumerable()` 流式传输查询结果，内部使用了类似的惰性抓取策略。本文中的自定义 `AsyncPaginatedEnumerable<T>` 适用于 EF Core 管不到的数据源——REST API、带自定义分页的老数据库、或者第三方服务。当你需要主动控制分页边界来做日志、指标或进度报告时，它也很有用。

## 总结

这套实现展示了迭代器模式解决一个真实生产问题——消费者完全透明的分页数据访问。我们从一段分页循环和业务逻辑纠缠的代码出发，最终实现了清晰的职责分离：`PaginatedEnumerable<T>` 处理分页抓取，`CustomerRepository` 提供数据访问 API，`CustomerReportService` 用一个简单的 `foreach` 循环消费记录。

同步和异步两个版本覆盖了最常见的数据访问场景。因为实现了标准的 .NET 接口，LINQ 集成是免费的。xUnit 测试验证了多页遍历、空数据集、提前终止和取消操作都正确工作。

把 `PaginatedEnumerable<T>` 和 `AsyncPaginatedEnumerable<T>` 这两个类拿走，把模拟数据源换成你实际的数据库或 API 客户端，你就有了一个可复用、可测试的数据访问层——它可以扩展到百万级记录，而内存消耗不会跟着线性增长。迭代器模式让你的分页逻辑集中管理、消费者代码保持干净、应用保持响应。

如果你关注设计模式、C# 工程实践和开发工具，可以关注 Aide Hub。这里会继续分享能直接落地的技术教程和项目经验。

## 参考

- [Iterator Pattern Real-World Example in C#: Complete Implementation — Dev Leader](https://www.devleader.ca/2026/06/11/iterator-pattern-realworld-example-in-c-complete-implementation)
