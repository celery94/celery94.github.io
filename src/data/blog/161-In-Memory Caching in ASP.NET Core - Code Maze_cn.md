---
pubDatetime: 2024-06-09
tags: [".NET", "ASP.NET Core"]
source: https://code-maze.com/aspnetcore-in-memory-caching/
author: Muhammed Saleem
title: In-Memory Caching in ASP.NET Core
description: In this article, we will talk about caching basics and how to implement In-Memory Caching in ASP.NET Core Applications
---

# In-Memory Caching in ASP.NET Core

> ## Excerpt
>
> In this article, we will talk about caching basics and how to implement In-Memory Caching in ASP.NET Core Applications

---

本文将介绍缓存的一些基础知识以及如何在ASP.NET Core应用程序中实现内存缓存。

---

## 什么是缓存？

缓存是一种将经常访问的数据存储在临时位置以便将来更快访问的技术。这可以显著提高应用程序的性能，因为它减少了与数据源频繁连接和通过网络发送数据所需的时间。这对于那些数据不经常更改但需要时间填充的数据效果最佳。一旦缓存，我们可以非常快地获取这些数据。也就是说，我们不应该盲目地依赖缓存数据，始终应该有一个回退机制。此外，我们应该定期刷新缓存中的数据，以避免数据变得过时。

ASP.NET Core原生支持两种类型的缓存：

- **In-Memory Caching** – 将数据存储在应用程序服务器的内存中。
- **Distributed Caching** – 将数据存储在多个应用程序服务器可以共享的外部服务中。

**在ASP.NET Core中，内存缓存是最简单的缓存形式，应用程序将数据存储在Web服务器的内存中。** 这基于`IMemoryCache`接口，该接口表示存储在应用程序内存中的缓存对象。由于应用程序在服务器内存中维护了一个内存缓存，如果我们想在多个服务器上运行应用程序，应该确保会话是粘性的。**粘性会话是一种机制，通过该机制我们可以使来自客户端的所有请求都转到同一个服务器**。

## 实现内存缓存

现在让我们看看如何在ASP.NET Core应用程序中实现内存缓存。让我们从创建一个使用[EF Core Code-First](https://code-maze.com/net-core-web-api-ef-core-code-first/)方法的ASP.NET Core Web API开始。

API准备好后，我们将修改员工列表的端点并添加缓存支持：

```csharp
[Route("api/[controller]")]
[ApiController]
public class EmployeeController : ControllerBase
{
    private const string employeeListCacheKey = "employeeList";
    private readonly IDataRepository<Employee> _dataRepository;
    private IMemoryCache _cache;
    private ILogger<EmployeeController> _logger;
    public EmployeeController(IDataRepository<Employee> dataRepository,
        IMemoryCache cache,
        ILogger<EmployeeController> logger)
    {
        _dataRepository = dataRepository ?? throw new ArgumentNullException(nameof(dataRepository));
        _cache = cache ?? throw new ArgumentNullException(nameof(cache));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }
    [HttpGet]
    public async Task<IActionResult> GetAsync()
    {
        _logger.Log(LogLevel.Information, "Trying to fetch the list of employees from cache.");
        if (_cache.TryGetValue(employeeListCacheKey, out IEnumerable<Employee> employees))
        {
            _logger.Log(LogLevel.Information, "Employee list found in cache.");
        }
        else
        {
            _logger.Log(LogLevel.Information, "Employee list not found in cache. Fetching from database.");
            employees = _dataRepository.GetAll();
            var cacheEntryOptions = new MemoryCacheEntryOptions()
                    .SetSlidingExpiration(TimeSpan.FromSeconds(60))
                    .SetAbsoluteExpiration(TimeSpan.FromSeconds(3600))
                    .SetPriority(CacheItemPriority.Normal)
                    .SetSize(1024);
            _cache.Set(employeeListCacheKey, employees, cacheEntryOptions);
        }
        return Ok(employees);
    }
}
```

首先，我们将`IMemoryCache`和`ILogger`注入到`EmployeeController`中。然后，在列表操作方法中，我们检查`employeeList`数据是否存在于缓存中。如果数据存在于缓存中，我们就取出该数据。如果数据不存在于缓存中，我们从数据库中获取数据并同时将其填充到缓存中。此外，我们使用`MemoryCacheEntryOptions`设置滑动过期时间为1分钟。在下一节中，我们将详细了解`MemoryCacheEntryOptions`。

对于大多数类型的应用程序，`IMemoryCache`是默认启用的。例如，如果我们调用`AddMvc()`、`AddControllersWithViews()`、`AddRazorPages()`、`AddMvcCore().AddRazorViewEngine()`等，它会启用`IMemoryCache`。然而，对于那些不调用这些方法的应用程序，可能需要在`Program`类中调用`AddMemoryCache()`。当然，如果我们使用旧版本的.NET，并带有`Startup`类，我们需要在`Startup`类中调用`AddMemoryCache()`。

## 配置缓存选项

我们可以使用`MemoryCacheEntryOptions`对象配置内存缓存的行为。`MemoryCacheEntryOptions`提供了多个方法来设置不同的缓存属性：

```csharp
var cacheEntryOptions = new MemoryCacheEntryOptions()
        .SetSlidingExpiration(TimeSpan.FromSeconds(60))
        .SetAbsoluteExpiration(TimeSpan.FromSeconds(3600))
        .SetPriority(CacheItemPriority.Normal);
```

**SlidingExpiration** – 这决定了缓存条目在被移除之前可以保持不活动状态的时间长度。最好将其设置为较低的值，如1分钟。我们可以使用`SetSlidingExpiration()`方法来设置该值。

**AbsoluteExpiration** – 滑动过期的问题在于，如果我们继续访问缓存条目，它将永不过期。绝对过期通过确保缓存条目在绝对时间内过期来解决这个问题，不管它是否仍然活跃。最好将其设置为较高的值，如1小时。我们可以使用`SetAbsoluteExpiration()`方法来设置该值。**一个好的缓存策略是结合滑动和绝对过期来使用**。

**Priority** – 这设置了缓存对象的优先级。默认情况下，优先级将是**Normal**，但我们可以根据需要将其设置为**Low**、**High**、**Never Remove**等。我们可以使用`SetPriority()`方法来设置该值。随着服务器尝试释放内存，我们为缓存项目设置的优先级将决定它是否会从缓存中移除。

## 设置内存缓存的大小限制

使用`MemoryCache`实例时，可以选择指定大小限制。缓存大小限制没有定义的单位，但它代表缓存可以容纳的条目数量。尽管指定`MemoryCache`的大小限制是完全可选的，但一旦设置了缓存的大小限制，我们应该为所有缓存条目指定一个大小。同样，如果没有设置缓存大小限制，单个缓存条目上设置的大小将被忽略。

要设置缓存的大小限制，我们需要创建一个自定义`MemoryCache`实例：

```csharp
var cache = new MemoryCache(new MemoryCacheOptions
{
    SizeLimit = 1024,
});
```

在这个示例中，我们通过指定大小限制为1024来创建一个自定义`MemoryCache`实例。现在在创建单个缓存条目时，必须指定一个大小，否则会抛出异常：

```csharp
var options = new MemoryCacheEntryOptions().SetSize(2);
cache.Set("myKey1", "123", options);
cache.Set("myKey2", "456", options);
```

我们可以创建不同大小的缓存条目，但一旦所有条目的总和达到`SizeLimit`，就不能再插入任何条目。例如，在这个示例中，我们可以创建1024个大小为1的条目，512个大小为2的条目，或者256个大小为4的条目等。核心思想是我们可以根据应用程序的需求设计不同大小的缓存条目。

**这里有一个有趣的事情需要注意：一旦缓存达到上限，它不会删除最旧的条目以腾出空间给新条目**。相反，它会忽略新条目，缓存插入操作也不会抛出错误。因此，在设计带有大小限制的缓存时需要小心，否则以后调试与缓存相关的问题将变得不容易。

## 测试内存缓存

现在是时候测试我们的应用程序，以查看内存缓存的实际效果。让我们运行应用程序并导航到`/api/Employee`端点。当我们第一次访问它时，可能需要几秒钟的时间来从数据库中提取记录，这取决于我们在哪里托管数据库、结果集的数据量、网络速度等：

```bash
Status: 200 OK Time 3.67 s Size 451 B
```

从日志中可以看出，应用程序连接了数据库并获取了数据：

```bash
info: InMemoryCacheExample.Controllers.EmployeeController[0]
      Trying to fetch the list of employees from cache.
info: InMemoryCacheExample.Controllers.EmployeeController[0]
      Employee list not found in cache. Fetching from database.
info: Microsoft.EntityFrameworkCore.Database.Command[20101]
      Executed DbCommand (355ms) [Parameters=[], CommandType='Text', CommandTimeout='30']
      SELECT [e].[EmployeeId], [e].[DateOfBirth], [e].[Email], [e].[FirstName], [e].[LastName], [e].[PhoneNumber]
      FROM [Employees] AS [e]
```

请记住，在这样做的同时，这也会将结果放入缓存中。为了验证这一点，让我们再次执行相同的端点：

```bash
Status: 200 OK Time 22 ms Size 451 B
```

这次我们可以看到我们非常快速地获得了结果。在检查日志时，我们可以验证这次它是从缓存中提取员工列表的：

```bash
info: InMemoryCacheExample.Controllers.EmployeeController[0]
      Trying to fetch the list of employees from cache.
info: InMemoryCacheExample.Controllers.EmployeeController[0]
      Employee list found in cache.
```

在这个例子中，通过实现内存缓存，我们获得的结果比之前快了150多倍。这是一个巨大的性能提升！

然而，在现实世界的项目中，性能提升将取决于许多外部因素，例如我们在哪里托管数据库、网络速度如何、数据量有多大等，并且可能会有细微的变化。不过，毫无疑问，通过在内存中缓存这些类型的经常访问的数据，我们可以显著提高应用程序的性能。

## 从内存缓存中移除数据

在某些情况下，.NET Core运行时会自动移除内存缓存项：

- 当应用程序服务器内存不足时，.NET Core运行时将启动内存缓存项的清理过程，除了那些设置了**NeverRemove**优先级的项。
- 当我们设置了滑动过期时间时，不活动的条目将在该时间过期。同样，一旦我们设置了绝对过期时间，所有条目将在该时间过期。

除此之外，如果我们愿意，还有一个选项可以手动从内存缓存中移除某个项。例如，在我们的示例中，当一个新的员工记录插入到数据库中时，我们可能希望手动使缓存失效。我们可以在**POST**方法中使用`IMemoryCache`的`Remove()`方法来进行操作：

```csharp
[HttpPost]
public IActionResult Post([FromBody] Employee employee)
{
    if (employee == null)
    {
        return BadRequest("Employee is null.");
    }
    _dataRepository.Add(employee);
    _cache.Remove(employeeListCacheItem);
    return new ObjectResult(employee) { StatusCode = (int)HttpStatusCode.Created };
}
```

当新的员工记录插入到数据库中时，这将移除员工列表缓存。

## 管理并发访问内存缓存

现在假设多个用户同时尝试从内存缓存中访问数据。**即使`IMemoryCache`是线程安全的，它也容易出现竞争条件。** 例如，如果缓存为空，并且有两个用户同时尝试访问数据，则可能会出现两位用户都从数据库中获取数据并将其填充到缓存中的情况。这是不可取的。为了解决这些问题，我们需要为缓存实现锁定机制。

为了实现缓存的锁定，我们可以使用`SemaphoreSlim`类，这是`Semaphore`类的轻量级版本。这将帮助我们控制可以同时访问资源的线程数量。让我们在控制器中声明一个`SemaphoreSlim`对象以实现缓存锁定：

```csharp
private static readonly SemaphoreSlim semaphore = new SemaphoreSlim(1, 1);
```

现在让我们修改列表端点以实现缓存锁定：

```csharp
[HttpGet]
public async Task<IActionResult> GetAsync()
{
    _logger.Log(LogLevel.Information, "Trying to fetch the list of employees from cache.");
    if (_cache.TryGetValue("employeeList", out IEnumerable<Employee> employees))
    {
        _logger.Log(LogLevel.Information, "Employee list found in cache.");
    }
    else
    {
        try
        {
            await semaphore.WaitAsync();
            if (_cache.TryGetValue("employeeList", out employees))
            {
                _logger.Log(LogLevel.Information, "Employee list found in cache.");
            }
            else
            {
                _logger.Log(LogLevel.Information, "Employee list not found in cache. Fetching from database.");
                employees = _dataRepository.GetAll();
                var cacheEntryOptions = new MemoryCacheEntryOptions()
                        .SetSlidingExpiration(TimeSpan.FromSeconds(60))
                        .SetAbsoluteExpiration(TimeSpan.FromSeconds(3600))
                        .SetPriority(CacheItemPriority.Normal)
                        .SetSize(1024);
                _cache.Set(employeeListCacheItem, employees, cacheEntryOptions);
            }
        }
        finally
        {
            semaphore.Release();
        }
    }
    return Ok(employees);
}
```

在这里，如果缓存中没有找到条目，线程将等待，直到进入信号量。一旦进入信号量，线程将检查缓存条目是否已经被其他线程填充。如果条目仍然不可用，则继续从数据库中获取数据并将其填充到缓存中。最后，确保我们释放信号量非常重要，以便其他线程可以继续。

## 内存缓存的优缺点

我们已经看到内存缓存如何提高数据访问的性能。然而，它也有一些需要注意的限制。让我们看一下内存缓存的一些优缺点。

优点：

- **数据访问更快** – 当我们从缓存中访问数据时，因为没有涉及到应用程序外的额外网络通信，因此会非常快。
- **高度可靠** – 内存缓存被认为是高度可靠的，因为它驻留在应用服务器的内存中。只要应用程序运行，缓存就会工作正常。
- **易于实现** – 实现内存缓存非常简单，只需几个简单的步骤，无需额外的基础设施或第三方组件，因此它是小型到中型应用程序的好选择。

缺点：

- **粘性会话开销** – 对于在多个应用服务器上运行的大型应用程序，维护粘性会话将会有一定的开销。
- **服务器资源消耗** – 如果配置不当，可能会消耗应用服务器的大量资源，尤其是内存。

## 内存缓存指南

在实现内存缓存时，请考虑以下重要指南：

**我们应该编写和测试应用程序，使其永远不依赖于缓存数据。** 应该始终有一个回退机制，以便在缓存项不可用或过期的情况下从实际数据源获取数据。

**建议始终限制缓存的大小，以限制服务器内存的消耗。** ASP.NET Core运行时不会根据内存限制来限制缓存大小，因此开发人员需要自己设置缓存大小限制。

**我们应该使用过期时间来限制缓存的持续时间。** 设计缓存策略时，最好根据应用程序的具体情况结合使用绝对过期和滑动过期。

## 结论

在本文中，我们了解了缓存基础知识以及在ASP.NET Core中内存缓存的工作原理。此外，我们还了解了如何在ASP.NET Core应用程序中实现内存缓存，其优缺点及使用指南。
