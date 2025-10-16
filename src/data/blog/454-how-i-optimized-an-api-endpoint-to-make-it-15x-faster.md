---
pubDatetime: 2025-09-03
tags: [".NET", "ASP.NET Core", "C#", "Performance"]
slug: how-i-optimized-an-api-endpoint-to-make-it-15x-faster
source: https://www.milanjovanovic.tech/blog/how-i-optimized-an-api-endpoint-to-make-it-15x-faster
title: 如何将 API 端点性能优化 15 倍
description: 深入探讨 API 性能优化的实战案例，通过聚焦瓶颈、减少往返次数、并行化外部调用和缓存策略，将端点性能提升 15 倍的完整方法。
---

性能优化是软件工程中最令我着迷的部分。在过去的 5 年中，我遇到了各种性能问题，这些问题教会了我不同的解决方法。

大约一个月前，我遇到了一个 API 端点的扩展问题。这个端点用于为电子商务 Web 应用程序计算报告。它需要与多个模块（服务）通信以收集所有必要的数据，将其组合并执行计算。

最终，我实现了 15 倍的性能提升。在这篇文章中，我将详细介绍实现这一显著改进的具体方法。

## 首先聚焦瓶颈

当我解决性能问题时，首先要做的是确定代码中最慢的部分。修复这部分代码通常会带来最显著的改进。

解决一个瓶颈也可以揭示下一个瓶颈在哪里。这是一个持续的过程。

在我的情况下，有几个瓶颈：

- 在循环中调用数据库
- 多次调用外部服务
- 使用相同参数多次执行复杂计算

### 如何测量性能？

一个简单的方法是使用 `System.Timers.Timer`，在方法调用之间手动记录执行时间。或者你可以使用性能分析器。

更高级的方法包括：

- 使用 Application Insights 或其他 APM 工具
- 实现自定义性能计数器
- 使用 BenchmarkDotNet 进行微基准测试

## 减少往返次数

应用程序与数据库（或其他服务）之间的往返可能需要 5-10 毫秒或更多时间。如果你的流程中有很多往返，这会快速累积。

以下是减少往返次数的几种方法：

### 1. 避免在循环中调用数据库

这通常可以通过简单的查询来解决：

```sql
SELECT * FROM [TableName] WHERE Id IN (list_of_ids)
```

这种方法将多个单独的查询合并为一个批量查询，显著减少了数据库往返次数。

### 2. 使用返回多个结果集的查询

一个支持此功能的库是 [Dapper](https://github.com/DapperLib/Dapper)，使用 `QueryMultiple` 方法：

```csharp
using (var connection = new SqlConnection(connectionString))
{
    var sql = @"
        SELECT * FROM Users WHERE Id = @UserId;
        SELECT * FROM Orders WHERE UserId = @UserId;
        SELECT * FROM OrderItems WHERE OrderId IN 
            (SELECT Id FROM Orders WHERE UserId = @UserId);";
    
    using (var multi = connection.QueryMultiple(sql, new { UserId = userId }))
    {
        var user = multi.Read<User>().Single();
        var orders = multi.Read<Order>().ToList();
        var orderItems = multi.Read<OrderItem>().ToList();
    }
}
```

### 3. 聚合服务调用

如果你需要对另一个服务进行多次调用，尝试将其转换为一次调用。在服务中聚合所需的数据并一次性返回所有内容。

```csharp
// 替代多次调用
var user = await userService.GetUserAsync(userId);
var preferences = await userService.GetUserPreferencesAsync(userId);
var permissions = await userService.GetUserPermissionsAsync(userId);

// 使用单次聚合调用
var userDetails = await userService.GetUserDetailsAsync(userId);
```

## 并行化外部调用

我遇到了需要等待来自多个服务的多个异步调用的情况。这些调用彼此没有依赖关系，所以我使用了一个简单的技术来获得显著的性能改进。

假设你正在等待两个任务：

```csharp
var task1Result = await CallService1Async();
var task2Result = await CallService2Async();
// 使用结果
```

### 使用 Task.WhenAll 并行化调用

一种简单的并行化这些调用的方法是使用 `Task.WhenAll` 方法：

```csharp
var task1 = CallService1Async();
var task2 = CallService2Async();

await Task.WhenAll(task1, task2);

// 使用结果
var result1 = task1.Result;
var result2 = task2.Result;
```

注意，我直接访问任务的 `Result` 属性。如果你使用它来阻塞异步调用，这可能是有害的，甚至可能导致死锁。

然而，在这种情况下这样做是完全安全的，因为在调用 `Task.WhenAll` 完成后，两个任务都将完成。

### 更复杂的并行化场景

对于更复杂的场景，你可以使用：

```csharp
var tasks = new List<Task>
{
    ProcessDataAsync(data1),
    ProcessDataAsync(data2),
    ProcessDataAsync(data3)
};

await Task.WhenAll(tasks);
```

或者使用 `Task.Run` 进行 CPU 密集型操作：

```csharp
var tasks = data.Select(item => Task.Run(() => ProcessItem(item)));
await Task.WhenAll(tasks);
```

## 缓存作为最后手段

我尝试将缓存留到最后，在我已经用尽所有其他提高性能的可能性之后。虽然我通常喜欢使用缓存，但我意识到当数据过时时，它可能会引入一些不需要的行为。

你必须考虑可以安全缓存数据多长时间，以及如果底层数据发生变化，你将如何清除缓存。

### 内存缓存

在简单的应用程序中，我使用 ASP.NET Core 开箱即用的 `IMemoryCache`：

```csharp
public class UserService
{
    private readonly IMemoryCache _cache;
    private readonly IUserRepository _userRepository;
    
    public UserService(IMemoryCache cache, IUserRepository userRepository)
    {
        _cache = cache;
        _userRepository = userRepository;
    }
    
    public async Task<User> GetUserAsync(int userId)
    {
        var cacheKey = $"user_{userId}";
        
        if (_cache.TryGetValue(cacheKey, out User cachedUser))
        {
            return cachedUser;
        }
        
        var user = await _userRepository.GetByIdAsync(userId);
        
        _cache.Set(cacheKey, user, TimeSpan.FromMinutes(15));
        
        return user;
    }
}
```

### 分布式缓存

对于更大规模的应用程序，你可以使用外部缓存如 [Redis](https://redis.io/)：

```csharp
public class UserService
{
    private readonly IDistributedCache _cache;
    private readonly IUserRepository _userRepository;
    
    public async Task<User> GetUserAsync(int userId)
    {
        var cacheKey = $"user_{userId}";
        var cachedUser = await _cache.GetStringAsync(cacheKey);
        
        if (cachedUser != null)
        {
            return JsonSerializer.Deserialize<User>(cachedUser);
        }
        
        var user = await _userRepository.GetByIdAsync(userId);
        
        await _cache.SetStringAsync(cacheKey, JsonSerializer.Serialize(user),
            new DistributedCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(15)
            });
        
        return user;
    }
}
```

### 缓存的最佳候选者

缓存的一个好候选者是经常访问但很少修改的数据，例如：

- 用户配置文件信息
- 产品目录数据
- 配置设置
- 查找表数据

## 总结

我认为对于大多数 Web 应用程序，性能优化可以归结为以下方法：

1. **首先聚焦瓶颈** - 识别和修复最慢的部分
2. **减少往返次数** - 批量查询和聚合调用
3. **并行化外部调用** - 同时执行独立的操作
4. **缓存** - 作为最后的优化手段

我在这里没有谈论数据库优化和索引，但如果数据库是你的瓶颈，这也应该在你的考虑范围内。

### 额外的性能优化技巧

- **使用连接池** - 重用数据库连接以减少创建开销
- **实现分页** - 避免一次性加载大量数据
- **优化序列化** - 使用高效的序列化库如 System.Text.Json
- **启用压缩** - 减少网络传输的数据量
- **使用 CDN** - 为静态资源提供更快的访问速度

通过系统地应用这些技术，你可以显著提高 API 的性能，就像我实现的 15 倍改进一样。关键是要有条理地进行，首先解决最大的瓶颈，然后逐步优化其他方面。
