---
pubDatetime: 2026-04-01T16:40:00+08:00
title: "10 个正在拖垮你 ASP.NET Core 应用的 Async 错误"
description: "本文梳理了 .NET Core 后端中最常见的 10 个异步编程错误，包括滥用 Task.Run、忘记 CancellationToken、async void 陷阱等，并给出每种错误的具体修复方法，帮助你写出更健壮的异步代码。"
tags: ["ASP.NET Core", "Async", "C#", ".NET", "性能优化"]
slug: "ten-async-mistakes-dotnet-aspnet-core"
ogImage: "../../assets/703/01-cover.png"
source: "https://x.com/AntonMartyniuk/status/2039228565015662851"
---

![ASP.NET Core 异步错误导致调用链断裂](../../assets/703/01-cover.png)

异步代码写错了，应用不会立刻崩溃，也不会抛出明显的异常。它只是变慢、内存上涨、偶尔超时——然后你花几天时间排查，发现根源是几行看起来"没问题"的 async/await。

Anton Martyniuk 在对大量 .NET Core 后端代码做过审查后，总结出了 10 个反复出现的 async 错误。这些问题不难理解，但修起来需要先把坑的位置认清楚。

## 1. 没有传递 CancellationToken

**问题**：客户端断开连接后，服务端的请求仍然在跑。CPU 白白消耗，内存占用不释放。

很多项目里，控制器方法签名已经接收了 `CancellationToken`，但调用下层服务、数据库查询时并没有传进去，token 就成了摆设。

```csharp
// 错误写法
public async Task<IActionResult> GetData(CancellationToken cancellationToken)
{
    var result = await _repository.GetItemsAsync(); // 没有传 token
    return Ok(result);
}

// 正确写法
public async Task<IActionResult> GetData(CancellationToken cancellationToken)
{
    var result = await _repository.GetItemsAsync(cancellationToken);
    return Ok(result);
}
```

**修复原则**：把 `CancellationToken` 一路贯穿整条调用链，从控制器到 Service 再到 Repository，每一层都传下去。

## 2. 在异步代码上同步阻塞

**问题**：用 `.Result`、`.Wait()` 或 `.GetAwaiter().GetResult()` 强等 Task 完成，会导致线程池耗尽，整个应用卡死。

这是最容易造成死锁的写法，在 ASP.NET Core 的默认同步上下文里尤为危险：

```csharp
// 错误写法——可能死锁
var user = _userService.GetByIdAsync(id).Result;

// 正确写法
var user = await _userService.GetByIdAsync(id);
```

只要调用栈顶端有 `async`，整条链就该用 `await`，没有折中方案。

## 3. 出站请求没有设置超时

**问题**：`HttpClient` 默认超时是 100 秒。如果下游服务卡住，你的线程就挂在那里，最终把整个服务拖垮。

```csharp
// 错误写法——依赖默认超时
var response = await _httpClient.GetAsync(url);

// 正确写法——设置超时
var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
var response = await _httpClient.GetAsync(url, cts.Token);
```

推荐在注册 `HttpClient` 时直接设 `Timeout`，同时在每次调用时再叠加一个 `CancellationTokenSource`，两道保险应对不同的超时场景。

## 4. 整条调用链没有彻底异步化

**问题**：控制器是 async，但调用了一个同步 Service 或者同步的 Repository 方法，效果等于没有异步。在高并发下会出现线程竞争和死锁。

```csharp
// 错误写法——Service 里混入了同步 I/O
public class OrderService
{
    public async Task<Order> GetOrderAsync(int id)
    {
        return _dbContext.Orders.Find(id); // 同步查询！
    }
}

// 正确写法——全链异步
public async Task<Order> GetOrderAsync(int id)
{
    return await _dbContext.Orders.FindAsync(id);
}
```

**原则**：Controller → Service → Repository，每一层都用 async/await，不要在中间混入任何同步 I/O 操作。

## 5. 在控制器或 Service 里滥用 Task.Run

**问题**：`Task.Run` 是把工作扔到线程池，适合 CPU 密集型任务。在控制器或 Service 里用它来包装 I/O 操作，不仅毫无收益，还增加了上下文切换开销。

```csharp
// 错误写法——不必要的 Task.Run
public async Task<IActionResult> Process()
{
    var result = await Task.Run(() => _dbContext.Items.ToList());
    return Ok(result);
}

// 正确写法——直接 await I/O
public async Task<IActionResult> Process()
{
    var result = await _dbContext.Items.ToListAsync();
    return Ok(result);
}
```

`Task.Run` 的正确用途：把阻塞 CPU 的计算（如图像处理、加解密、复杂算法）移出主线程。I/O 操作本身就是异步的，不需要它。

## 6. 把大响应整个读进内存而不是流式处理

**问题**：读取 500MB 的文件或大型 API 响应时，一次性 `ReadAsStringAsync()` 会把整个内容加载进内存，轻则内存飙高，重则 `OutOfMemoryException`。

```csharp
// 错误写法——整个响应加载进内存
var content = await response.Content.ReadAsStringAsync();

// 正确写法——流式读取
await using var stream = await response.Content.ReadAsStreamAsync();
await stream.CopyToAsync(outputStream);
```

对于数据库查询返回大量数据的场景，优先使用 `IAsyncEnumerable<T>` 配合 EF Core 的 `AsAsyncEnumerable()`，按需拉取数据而不是全量加载。

## 7. Task.WhenAll 不加并发限制

**问题**：对 1000 个 URL 同时发请求，或者一次并发 500 个数据库查询，很容易触发下游的限流，甚至把外部服务打垮引发雪崩。

```csharp
// 危险写法——无限并发
await Task.WhenAll(urls.Select(url => _httpClient.GetAsync(url)));

// 安全写法——限制并发数
await Parallel.ForEachAsync(urls,
    new ParallelOptions { MaxDegreeOfParallelism = 10 },
    async (url, ct) => await _httpClient.GetAsync(url, ct));
```

或者用 `SemaphoreSlim` 手动控制并发槽位，根据下游服务的承受能力设定上限。

## 8. async void 陷阱

**问题**：除了事件处理器（如按钮点击），其他地方用 `async void` 是危险的。方法内抛出的异常无法被 `try-catch` 捕获，会直接撞崩整个进程。

```csharp
// 危险写法
public async void SendEmail(string to) // 异常无处可去
{
    await _emailService.SendAsync(to);
}

// 正确写法
public async Task SendEmailAsync(string to)
{
    await _emailService.SendAsync(to);
}
```

无论什么场景，只要是自定义的 async 方法，返回类型都应该是 `Task` 或 `Task<T>`，绝不要用 `void`。

## 9. Fire-and-forget 的失控

**问题**：用 `_ = DoSomethingAsync()` 启动一个后台任务，完全不关注它是否成功完成，是否抛异常。这种模式在生产环境里几乎必然导致静默失败和资源泄漏。

```csharp
// 危险写法
_ = ProcessOrderAsync(order); // 不追踪，不等待，不管结果

// 更安全的做法——使用 BackgroundService
public class OrderProcessor : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await foreach (var order in _channel.Reader.ReadAllAsync(stoppingToken))
        {
            await ProcessOrderAsync(order);
        }
    }
}
```

需要后台处理时，推荐用 `BackgroundService` + Channel 形成有界队列，或采用 OutBox 模式保证消息不丢。

## 10. 库代码里忘记 ConfigureAwait(false)

**问题**：在库或基础设施层里 `await` 时，默认会捕获当前的同步上下文（在 ASP.NET Framework 里是 HttpContext 上下文）。切回这个上下文是一次不必要的开销，有时还会造成死锁。

```csharp
// 库代码里应该加 ConfigureAwait(false)
public async Task<string> FetchDataAsync(string url)
{
    var response = await _httpClient.GetAsync(url).ConfigureAwait(false);
    return await response.Content.ReadAsStringAsync().ConfigureAwait(false);
}
```

ASP.NET Core 本身没有 `SynchronizationContext`，所以这条规则在纯 Core 项目里影响相对较小，但在编写通用库或兼容旧版 ASP.NET 的代码时仍然重要。

## 小结

这 10 个问题有个共同特征：没有即时报错，症状在压力下才暴露。可以按以下优先级逐步排查：

1. **先看有没有同步阻塞**（`.Result`、`.Wait()`）——最容易造成死锁
2. **检查 CancellationToken 是否传透了**——避免无效请求占用资源
3. **确认所有出站请求都有超时**——防止级联挂起
4. **排查 async void 和 fire-and-forget**——防止不可见的崩溃和泄漏

把这些模式变成 Code Review 的固定检查项，比等线上出问题再回来排查要省心得多。

## 参考

- [原文 X（Twitter）帖子 by Anton Martyniuk](https://x.com/AntonMartyniuk/status/2039228565015662851)
- [antondevtips.com — .NET 开发者周刊](https://antondevtips.com/)
