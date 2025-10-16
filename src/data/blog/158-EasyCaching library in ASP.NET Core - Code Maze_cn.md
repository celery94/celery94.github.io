---
pubDatetime: 2024-06-01
tags: [".NET", "ASP.NET Core"]
source: https://code-maze.com/aspnetcore-easycaching/
author: Daniel Laurens
title: EasyCaching library in ASP.NET Core
description: 在本文中，我们展示了如何在 ASP.NET Core 中使用 EasyCaching 库设置缓存机制
---

# EasyCaching library in ASP.NET Core

> ## 摘要
>
> 在本文中，我们展示了如何在 ASP.NET Core 中使用 EasyCaching 库设置缓存机制

---

EasyCaching 是一个开源的缓存库，它帮助我们更简单、更灵活地管理缓存，并且是 ASP.NET Core 内置缓存库的替代方案。

缓存是一种常见且有用的技术，用于提高 Web 应用的性能。通过缓存频繁访问的数据，你可以减少 SQL 查询、API 调用或重复计算的频次。缓存的主要目标是通过消除从数据源（例如数据库）重复检索相同数据的需求来加速数据传输到客户端的速度。

要下载本文的源代码，可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/dotnet-client-libraries/EasyCaching)。

## 安装 EasyCaching

在本文中，我们将处理一个列出获奖葡萄酒的 API。

要安装的主要包是 `EasyCaching.Core`，它包含缓存的所有基础内容。此外，我们还需要安装一个或多个缓存提供程序，EasyCaching 会在这些提供程序上存储其缓存的数据（例如，内存缓存，Redis，SQLite，Memcached 等）。

我们将创建一个 ASP.NET Core Web API，并在同一个项目中使用两种不同的缓存提供程序（内存和 SQLite）。

首先，我们需要安装必要的 NuGet 包。除了允许我们实现缓存管理的 `EasyCaching.Core` 包之外，我们还要安装 `EasyCaching.InMemory` 和 `EasyCaching.SQLite`。这两个库将使我们能够分别使用应用服务器的内存（通常称为本地内存缓存）和 SQLite 数据库引擎用于持久化缓存项，以创建两种存储位置。

安装结束后，我们的项目文件将包含如下包引用：

```xml
<PackageReference Include="EasyCaching.Core" Version="1.9.2" />
<PackageReference Include="EasyCaching.InMemory" Version="1.9.2" />
<PackageReference Include="EasyCaching.SQLite" Version="1.9.2" />
```

## 配置项目以使用 EasyCaching

在我们的 `Program` 类中，我们现在必须使用 EasyCaching 和所需的提供程序来配置缓存。

我们可以通过两种方式配置缓存提供程序：通过代码或将配置存储在 `appsettings.json` 文件中：

```csharp
builder.Services.AddEasyCaching(options =>
{
    options.UseInMemory(configuration, "InMemoryCache", "EasyCaching:InMemoryCache");
    options.UseSQLite(config =>
    {
        config.DBConfig = new EasyCaching.SQLite.SQLiteDBOptions { FileName = "cache.db" };
    }, "SQLiteCache");
});
```

我们的 `Program` 类展示了两种方法。对于[内存缓存](https://code-maze.com/aspnetcore-in-memory-caching/)，我们提供一个指向 `appsettings.json` 文件部分的配置对象，同时为 SQLite 缓存编写指令。

在 `appsettings.json` 文件中，`EasyCaching` 部分带有子部分 `InMemoryCache` 包含一些基本参数：

```json
"EasyCaching": {
  "InMemoryCache": {
    "MaxRdSecond": 120, // 随机到缓存过期的最大秒数，默认值是120
    "EnableLogging": false, // 是否启用日志记录，默认是false
    "LockMs": 5000, // 互斥键的生存时间（毫秒），默认是5000
    "SleepMs": 300, // 互斥键存在时会暂停的时间，默认是300
    "DBConfig": {
      "SizeLimit": 100, // 缓存项的总数限制，默认值是10000
      "ExpirationScanFrequency": 60 // 扫描时间，默认值是60秒
    }
  }
}
```

现在配置就绪，我们可以调用两个提供程序来在控制器中处理缓存。

## 缓存实现

让我们创建一个控制器和一个端点来实际应用缓存，并比较有无缓存的性能。

### 在控制器类中实现缓存

我们将使用主构造函数并将提供程序作为类参数传递给它。

当使用单个提供程序时，我们注入一个实现 `IEasyCachingProvider` 的对象：

```csharp
public class ValuesController(IEasyCachingProvider _provider) : ControllerBase
{
}
```

在我们的示例应用程序中，我们决定使用两个不同的提供程序。在这种情况下，我们将使用一个实现 `IEasyCachingProviderFactory` 的工厂提供程序，并将其作为参数传递给主构造函数：

```csharp
public class ValuesWithTwoProvidersController(IEasyCachingProviderFactory _factory) : ControllerBase
{
}
```

在运行时，类将通过依赖注入容器注入必要的参数。

### 在端点函数中使用缓存

现在我们可以利用我们的工厂对象，并通过提供缓存提供程序的名称作为参数，调用 `GetCachingProvider()` 方法来选择我们想要使用的提供程序：

```csharp
public class ValuesWithTwoProvidersController(IEasyCachingProviderFactory _factory) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<ApiResponse>> GetValues()
    {
        var inMemoryProvider = _factory.GetCachingProvider("InMemoryCache");

        //内存缓存
        if (await inMemoryProvider.ExistsAsync("today"))
        {
            var cachedTodayDate = await inMemoryProvider.GetAsync<DateTime>("today");
            // ...
        }
        else
        {
            // ...
            var today = DateTime.Now.Date;
            await inMemoryProvider.SetAsync("today", today, TimeSpan.FromMinutes(1));
        }
        // ...
    }
}
```

在这里，我们检查要检索的数据是否存在于缓存中，以便首先提供它，使用 `ExistsAsync()` 方法。如果不存在，我们从原始数据源获取它。

如果请求的数据已被缓存，我们再调用提供程序的 `GetAsync()` 方法并将数据的键名作为参数传递，以检索它。否则，我们从其源中获取数据，然后使用提供程序的 `SetAsync()` 方法将其保存并缓存，提供三个参数：键名、值和过期时间。因此，下次请求相同的数据时，将首先检查缓存以获得更好的性能。

在示例中，目标数据是一个 `DateTime` 变量，但也可以假设它是频繁访问的数据并且最初存储在远程服务器上，比如说。

要注意的是，EasyCaching 提供了许多方法来管理和操作缓存数据。**除了本文中介绍的方法外，还可以通过 `FlushAsync()` 方法清除所有缓存项，或使用 `Remove()` 和 `RemoveAll()` 方法删除一个或一组指定的缓存键**。我们还可以使用 `GetExpirationAsync()` 方法处理缓存键的过期。EasyCaching 提供的 API 很大程度上满足了各种当前需求。

## 使用 EasyCaching 的缓存性能

现在让我们完成我们的 `GET` 端点，它将返回获奖葡萄酒的列表。我们将添加我们的第二个提供程序，这将使我们能够访问两个不同的缓存源：内存缓存和 SQLite 数据库。我们应用程序的完整代码可以在我们的 Git 仓库中访问。

**在某些情况下，拥有多个缓存提供程序可能是有用的**。确实，各种缓存提供程序有其各自的优缺点。

例如，可以将频繁访问的数据缓存到内存中以确保最佳速度，而需要持久存储但不太频繁访问的数据，可以使用分布式缓存如 Redis 或 SQLite：

```csharp
private ApiResponse _response = new();
[HttpGet]
public async Task<ActionResult<ApiResponse>> GetValues()
{
    var sqliteProvider = _factory.GetCachingProvider("SQLiteCache");
    var prizeDto = new PrizeDto();
    var stopwatch = Stopwatch.StartNew();

    //SQLite
    if (await sqliteProvider.ExistsAsync("prizes"))
    {
        var cachedPrizes = await sqliteProvider.GetAsync<List<WinePrize>>("prizes");
        prizeDto.Prizes = cachedPrizes.Value;
    }
    else
    {
        await Task.Delay(50);
        var prizes = Data.GetWinePrizes();
        prizeDto.Prizes = prizes;
        await sqliteProvider.SetAsync("prizes", prizes, TimeSpan.FromMinutes(1));
    }
    stopwatch.Stop();
    _response.Result = prizeDto;
    _response.Duration = stopwatch.ElapsedMilliseconds;
    _response.StatusCode = System.Net.HttpStatusCode.OK;
    return Ok(_response);
}
```

在我们的端点中，我们通过 `Task.Delay(50)` 语句模拟一个持续 50 毫秒的处理，以便缓存中还没有每一个数据时执行。

我们使用 `ApiResponse` 类来标准化 HTTP 响应。检索到的数据被映射到一个名为 `PrizeDto` 的 DTO 类中。

现在让我们多次连续调用我们的端点来测量无缓存和有缓存时的执行时间。在我们的测试中，首次运行持续了 710 毫秒。由于两次请求的数据都未被缓存，`Task.Delay(50)` 被执行了两次才返回响应。

后续执行时间少于 50 毫秒，且频繁接近 1 毫秒！在这些情况下，我们通过缓存来获取每次请求的数据。

这个简单的示例演示了缓存的有效性。

## 结论

EasyCaching 是一个免费可用的库，它简化了 .NET Core 应用程序中的缓存功能。它提供了一个统一的接口来与各种缓存提供程序一起工作，使你可以在不修改核心缓存逻辑的情况下轻松地在它们之间切换。在本文中，我们展示了如何使用 EasyCaching 库设置缓存机制。

请查阅 [官方文档](https://easycaching.readthedocs.io/en/latest/) 以了解该库提供的各种提供程序的更多信息。
