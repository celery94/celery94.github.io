---
pubDatetime: 2026-06-12T11:55:01+08:00
title: "10 个 Async/Await 错误正在拖垮你的 ASP.NET Core API 性能"
description: "来自 Mattrx（110k MAU 的营销分析 SaaS）真实生产环境：10 个 async/await 错误如何造成线程池饥饿、死锁和延迟飙升。每个错误都包含可直接编译的错误代码、修复后的正确写法、dotnet-counters 诊断信号，以及修复后的量化指标——吞吐量从 1,200 RPS 提升到 4,500 RPS，p95 延迟从 8.2 秒降至 1.4 秒，两周工作零新基础设施。"
tags: ["ASP.NET Core", "C#", "async/await", "Performance", ".NET"]
slug: "async-await-mistakes-aspnet-core-performance"
ogImage: "../../assets/873/01-cover.png"
source: "https://prepstack.co.in/blog/async-await-mistakes-that-kill-aspnet-core-api-performance-guide"
---

async/await 看起来像语法糖，但它不是。它是编译器生成的状态机、Task 分配、在线程池上调度的延续，以及 ASP.NET Core 对同步上下文有"意见"的一套机制。用对了，你的 API 能在 22 个线程上承受 5,000 RPS。用错了，同一个 API 在 1,200 RPS 时就会线程池饥饿、随机死锁、泄漏 `TaskCanceledException`，并在负载下因状态机分配而 OOM。

这些错误**不会**作为编译错误出现。它们能编译、能过测试、能在开发环境单用户下正常运行。它们只会在线程池压力到达阈值时崩——通常是在凌晨三点。

这篇文章来自 **Mattrx** 的真实生产审计——一个多租户营销分析 SaaS（Angular 19 + .NET 9、6 个 Azure App Service 实例、110k MAU）。每个错误都包含修复前的代码、修复后的代码、Application Insights 中会看到的症状，以及暴露问题的 `dotnet-counters` 读数。

## 异步到底是什么

```
async 不会让任何东西并行运行。
async 不会"让它更快"。
async 在等待 I/O 时释放当前线程——这样同一个线程就能服务其他请求。
```

读两遍。几乎所有 async 错误都源于对这个概念的误解。

```
WITHOUT ASYNC (阻塞 I/O):
  Request 1 -> [线程 A 被持有]: 查询 DB — 等待 200ms — 格式化 — 响应
                    ↑  线程 A 被阻塞，不可用于他人
  Request 2 -> [等待线程]

WITH ASYNC (非阻塞 I/O):
  Request 1 -> [线程 A]: 启动 DB 查询 — 释放 — ...
                                          │
                                          ▼
                          [线程 B, 200ms 后]: 继续 — 格式化 — 响应
  Request 2 -> [线程 A] 几微秒后就空闲 — 服务请求 2
```

好处不是"每个请求少了几十毫秒"。好处是**线程保持可用**。ASP.NET Core 的线程池默认约 30 个工作线程；如果你阻塞了它们，第 31 个请求排队，第 32 个排队，到 200 个并发请求时你已经在饿死了。

本文每个错误都属于以下四类之一：

1. 阻塞线程而不是释放线程（`.Result`、`.Wait()`、跨 await 持有 `lock`）
2. 在并行 I/O 可行时做了串行 I/O
3. 分配了你不需要的状态机
4. 泄漏了超出其作用域的工作

## 诊断工具集

在深入错误之前，先认识这几个工具：

| 工具                                                            | 揭示什么                       | 何时使用                       |
| --------------------------------------------------------------- | ------------------------------ | ------------------------------ |
| `dotnet-counters monitor -p <pid> System.Runtime`               | 线程池队列长度、锁竞争、分配率 | 第一诊断手段；可在生产环境运行 |
| `dotnet-counters monitor System.Threading.Tasks.TplEventSource` | Task 计数、调度器队列深度      | Async 专项深入                 |
| Application Insights 端到端事务                                 | 请求线程在何处阻塞 vs await    | 生产追踪                       |
| PerfView "Async Causality" + "Lock Contention"                  | 每个异步链 + 锁等待的可视化    | 疑难杂症                       |
| `dotnet-stack report`                                           | 实时线程栈 → 看谁在阻塞谁      | 所有东西都卡住时               |

快速嗅探测试——打开 `dotnet-counters` 看这几个指标：

```
threadpool-queue-length:       > 0 持续出现          → 饥饿
threadpool-thread-count:       攀升超过 ~50            → 过度配置
monitor-lock-contention-count: > 1k/sec               → 跨 await 持有 lock
exception-count:               > 50/sec 在低 RPS 下   → TaskCanceled 泛滥
```

## 先看结果：Mattrx 的两周审计

Mattrx 峰值约 3,200 请求/秒，分布 6 个 ASP.NET Core 9 实例。热路径：`/api/dashboard/kpis`（80k req/day）、`/api/campaigns/{id}/archive`（写端点，触发 SignalR + 邮件 + 审计）、`/api/import`（CSV 批量导入）、`/api/webhook/replay`（回放合作伙伴 webhook）。

以下 10 个错误**大致按对我们造成的损失排序**。修好前三个就能拿下大部分收益。

最终汇总：

- 线程池饥饿事件：4/周 → **0**（90 天）
- 每实例吞吐量：1,200 RPS → **4,500 RPS**（3.75×）
- 峰值工作线程数：110 → **22**（-80%）
- 月度死锁报告：3 → **0**
- `TaskCanceledException` 孤儿请求/周：240 → **6**
- `/api/dashboard/kpis` 异步状态机分配：**-40%**
- 热端点 GC % 时间：9% → **3%**
- `/api/import` p95：8.2s → **1.4s**（-83%）
- `/api/webhook/replay` p95：9.4s → **720ms**（-92%）
- Sentry 幽灵失败报告：18/周 → **0**

两周工作。没有新基础设施。没有重写。错误就是上面那 10 个无聊的模式。

## 错误 #1：`.Result` / `.Wait()` (sync-over-async)

**症状**：对 `Task` 调用 `.Result`、`.Wait()` 或 `.GetAwaiter().GetResult()` 会阻塞当前线程直到 task 完成。在 ASP.NET Core 中，当前线程是线程池线程。阻塞足够多，池就耗尽。新请求排队。最终超时。

### 修复前

```csharp
// 在需要异步结果的同步方法里
public Campaign LoadCampaign(Guid id)
{
    return _db.Campaigns.FirstAsync(c => c.Id == id).Result;
}

// "我就在这里等"反模式
public IActionResult Get(Guid id)
{
    var task = _campaigns.LoadAsync(id);
    task.Wait();
    return Ok(task.Result);
}

// GetAwaiter().GetResult() — 同样的问题
public Campaign LoadSync(Guid id)
    => _campaigns.LoadAsync(id).GetAwaiter().GetResult();
```

### 这对线程池做了什么

```
100 个并发请求，全部调用 .Result：
  - 线程 1：阻塞在 DB 往返 (200ms)
  - 线程 2：阻塞在 DB 往返 (200ms)
  - ...
  - 线程 28：阻塞在 DB 往返 (200ms)
  - 线程 29：ThreadPool.SetMinThreads 尚未分配
  - 请求 30+ —— 排队。延迟从 200ms 攀升至 4 秒。
```

线程池缓慢注入新线程（默认约每 500ms 一个）。请求队列增长比线程池快。你是在通过分配线程来"扩展"，这会消耗内存和 CPU，而不是像 async 设计的那样释放线程。

**诊断**：

```
dotnet-counters monitor -p <pid> System.Runtime
  threadpool-queue-length: 24, 38, 67, 110, 240, ...   ← 饥饿信号
  threadpool-thread-count: 32, 44, 58, 72, 96, ...      ← 被动增长
```

在 Application Insights 中：即使 CPU < 30%，尾部延迟 p99 在负载下也会飙升到 p50 的 4–10 倍。

### 修复后

```csharp
// 整条链保持异步
public async Task<Campaign> LoadCampaignAsync(Guid id, CancellationToken ct)
{
    return await _db.Campaigns.FirstAsync(c => c.Id == id, ct);
}

// Controller 也保持异步
public async Task<IActionResult> Get(Guid id, CancellationToken ct)
{
    return Ok(await _campaigns.LoadAsync(id, ct));
}
```

规则：**async all the way**。如果方法调用了异步方法，它自己也应该是异步的。只有一个使用 `.Result` 的合理场景：在老版本 C# 中写 Console App 的 `Main`。ASP.NET Core 6+ 已支持 async `Main`，不再需要。

### "库只暴露同步 API"问题

有时你改不了调用方。这种情况下最不坏的选择是 `Task.Run`：

```csharp
// 可接受的桥接（不理想）：你控制了线程池冲击
public Campaign LoadCampaign(Guid id) =>
    Task.Run(async () => await LoadCampaignAsync(id, default)).GetAwaiter().GetResult();
```

这用调用线程的同步阻塞，换成了**另一个**阻塞的线程池线程。你没有解决问题——你只是把它转移了。仅在确实无法改变 API 边界时使用。

**Mattrx 指标**：通过 grep（`\.Result\b`、`.Wait()`、`.GetAwaiter().GetResult()`）找到 **11 个 sync-over-async 调用点**。全部修复。每实例吞吐量：**1,200 → 4,500 RPS**。线程池饥饿事件：**4/周 → 0**。

## 错误 #2：async void

**症状**：`async void` 方法不能被 await，**它们的异常不能被调用方捕获**。它们会崩溃进程。它们让事件处理器看起来正常，让测试看起来绿色。

### 修复前

```csharp
// async void 在一个托管服务里
public class TimedReportRefresher : BackgroundService
{
    protected override Task ExecuteAsync(CancellationToken ct)
    {
        var timer = new Timer(_ => RefreshReportsAsync(ct), null, 0, 30_000);
        return Task.Delay(Timeout.Infinite, ct);
    }

    // async void — 这里的异常会崩溃进程
    private async void RefreshReportsAsync(CancellationToken ct)
    {
        var reports = await _db.Reports.ToListAsync(ct);
        foreach (var r in reports) await RefreshAsync(r, ct);
    }
}
```

如果 `RefreshReportsAsync` 抛出异常，它会传播到同步上下文——在 Timer 回调中同步上下文为 `null`，从而崩溃进程。在 Sentry 中表现为 `AppDomain.UnhandledException → process restart`。Mattrx 每月有 3 次。

### 为什么 async void 存在

只为一个原因：**WinForms / WPF 事件处理器**。框架签名要求 `void` 返回，所以异步事件处理器必须是 `async void`。除此之外，**永远不要用**。

### 修复后

```csharp
// 返回 Task；调用方能观察到失败
public class TimedReportRefresher(IServiceScopeFactory scopeFactory,
    ILogger<TimedReportRefresher> log) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        using var periodic = new PeriodicTimer(TimeSpan.FromSeconds(30));

        while (await periodic.WaitForNextTickAsync(ct))
        {
            try
            {
                await RefreshReportsAsync(ct);
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { break; }
            catch (Exception ex)
            {
                log.LogError(ex, "RefreshReports failed; will retry next tick.");
            }
        }
    }

    private async Task RefreshReportsAsync(CancellationToken ct)
    {
        using var scope = scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var reports = await db.Reports.ToListAsync(ct);
        foreach (var r in reports) await RefreshAsync(r, ct);
    }
}
```

两个改进：返回 `Task` 而非 `void`（调用方能 await 并观察失败），使用 `PeriodicTimer` 而非 `System.Threading.Timer`（异步感知、尊重取消、顺序执行，不会在前一个回调还在运行时再触发新回调）。

### async lambda 陷阱

```csharp
// 能编译。这是伪装的 async void。
button.Click += async (s, e) =>
{
    await DoWorkAsync();
};

// 对需要 Task 返回的框架事件，用一个 helper
button.Click += (s, e) => _ = HandleAsync(s, e);
```

任何把 `async` lambda 传给 `Action` 的地方，你都创建了一个 `async void`。注意 `EventHandler`、`Action<T>`、LINQ 的 `Where`/`Select`，以及 `Parallel.ForEach`。

**Mattrx 指标**：找到 5 个 `async void`，全部在后台计时器/事件订阅中。未处理异常的进程崩溃：**3/月 → 0**。

## 错误 #3：在可以并行时串行 await

**症状**：两个 await 排成一排，各自做独立工作。第二个在等第一个完成，虽然它不需要。

### 修复前

```csharp
// 六个 await，串行 —— 耗时是六个的总和
public async Task<ImportPreview> PreviewAsync(Guid jobId, CancellationToken ct)
{
    var job        = await _db.ImportJobs.FindAsync([jobId], ct);       // ~80 ms
    var settings   = await _settings.GetAsync(job.TenantId, ct);         // ~40 ms
    var csv        = await _blob.DownloadAsync(job.BlobUri, ct);         // ~600 ms
    var validators = await _validators.GetForKindAsync(job.Kind, ct);    // ~30 ms
    var fxRates    = await _fx.GetCurrentRatesAsync(job.Currency, ct);   // ~80 ms
    var preview    = await _parser.ParseAsync(csv, settings, validators, ct); // ~200 ms

    return new ImportPreview(job, preview, fxRates);
}
// 总耗时：~1,030 ms（冷缓存时最坏 8,200ms）
```

前 5 行互相独立——它们不读取彼此的结果。只有第 6 行才使用前面的结果。单个 MiniProfiler 瀑布图就能立刻暴露问题。

### 修复后

```csharp
// 五个独立操作并行启动；只 await 一次
public async Task<ImportPreview> PreviewAsync(Guid jobId, CancellationToken ct)
{
    var job = await _db.ImportJobs.FindAsync([jobId], ct);

    // 这 5 个互相独立
    var settingsTask   = _settings.GetAsync(job.TenantId, ct);
    var csvTask        = _blob.DownloadAsync(job.BlobUri, ct);
    var validatorsTask = _validators.GetForKindAsync(job.Kind, ct);
    var fxRatesTask    = _fx.GetCurrentRatesAsync(job.Currency, ct);

    await Task.WhenAll(settingsTask, csvTask, validatorsTask, fxRatesTask);

    var preview = await _parser.ParseAsync(csvTask.Result, settingsTask.Result,
                                           validatorsTask.Result, ct);

    return new ImportPreview(job, preview, fxRatesTask.Result);
}
// 总耗时：~max(40, 600, 30, 80) + 80 + 200 = ~880ms 开发环境，
// 但重型场景（blob 6s, fx 冷 800ms）从 8.2s → 1.4s。
```

```
SEQUENTIAL（修复前）:
  0────80────120───720────────────750─────830─────────────1030 ms
  [Job][Set ][Blob ────────────────][Val ][Fx ][Parse ────────]

PARALLEL（修复后）:
  0────80───────────────────────────680──────────────────────880 ms
  [Job]
       [Set ──────]
       [Blob ─────────────────────]
       [Val ─────]
       [Fx ──────────]
                                    [Parse ────────────────]
                          ▲
                    Task.WhenAll 完成
```

### 什么时候不该并行

- **B 依赖 A 的结果时**：`var u = await GetUser(); var orders = await GetOrders(u.Id);` 是正确的串行。
- **操作共享非线程安全的状态时**：EF Core `DbContext` 不是线程安全的——永远不要在同一上下文上并发运行两个查询。
- **需要副作用顺序保证时**。

EF Core 特别注意：

```csharp
// 同一个 DbContext，两个并发查询 —— 抛出 InvalidOperationException
var t1 = _db.Campaigns.ToListAsync(ct);
var t2 = _db.Events.ToListAsync(ct);
await Task.WhenAll(t1, t2);   // BOOM

// 要么用作用域工厂，要么串行 await
await using var db1 = _factory.CreateDbContext();
await using var db2 = _factory.CreateDbContext();
var t1 = db1.Campaigns.ToListAsync(ct);
var t2 = db2.Events.ToListAsync(ct);
await Task.WhenAll(t1, t2);
```

**Mattrx 指标**：`/api/import` 预览 p95 **8.2s → 1.4s**（-83%）。审计中最大的单次异步修复。

## 错误 #4：在请求线程上用 Task.Run

**症状**：有人用 `Task.Run` 包裹一个异步调用"让它非阻塞"。这错了两次：

1. 异步调用本来就已经是非阻塞的。`Task.Run` 什么都没增加。
2. `Task.Run` 把工作移到另一个线程池线程，然后 await 它——意味着**用了两个线程池槽位**而非一个。

### 修复前

```csharp
// "让它非阻塞" —— 但它本来就已经是了
public async Task<IActionResult> GetReports(Guid tenantId, CancellationToken ct)
{
    var reports = await Task.Run(async () =>
        await _db.Reports.Where(r => r.TenantId == tenantId).ToListAsync(ct), ct);

    return Ok(reports);
}
```

这消耗线程 A 来触发 `Task.Run`，它调度工作到线程 B，线程 B await DB。在线程 B 等待期间，线程 A 也被持有。**你把请求的线程池成本翻倍了。**

### 何时 Task.Run 是正确的

仅当你真的有**同步、CPU 密集型**工作，否则会阻塞请求线程时：

```csharp
// 图片压缩是 CPU 密集的；卸载以保持请求线程空闲
public async Task<IActionResult> ProcessImage(byte[] data, CancellationToken ct)
{
    var thumbnail = await Task.Run(() => GenerateThumbnail(data), ct);
    return Ok(thumbnail);
}
```

| 工作形态                                | 应该 Task.Run 吗        |
| --------------------------------------- | ----------------------- |
| 异步 I/O（DB、HTTP、带异步 API 的文件） | **否**——它已经非阻塞了  |
| 同步 CPU 工作（压缩、解析、哈希）       | **是**，如果 > ~50ms    |
| 同步 I/O（无异步 API 的旧库）           | **最后手段**——见错误 #1 |
| 微小工作（< 1ms）                       | **否**——开销占主导      |

**Mattrx 指标**：在异步处理器中找到 **8 处误用的 `Task.Run`**。移除后：峰值 CPU **12% → 4%** + 线程池工作线程数峰值 **110 → 22**。

## 错误 #5：缺少 CancellationToken

**症状**：长时间运行的工作**无法被取消**，在客户端断开后仍持续运行。浪费的 CPU、浪费的 DB 周期、浪费的内存持有部分结果。在规模下：你的吞吐量有 10%+ 是在做没人等待的工作。

### 修复前

```csharp
// 没有 CancellationToken；客户端断开后服务器仍在工作
public async Task<IActionResult> ListCampaigns()
{
    var campaigns = await _db.Campaigns.ToListAsync();        // 没有 ct
    var enriched = await _enricher.EnrichAsync(campaigns);    // 没有 ct
    return Ok(enriched);
}
```

用户在 4 秒响应期间关闭标签。服务器毫不知情。两个查询都运行完成。构建响应，序列化 JSON，响应写入器失败并抛出 `IOException: response stream closed`。用户的 CPU 花在了无用功上。

### 修复后

```csharp
// 从 Controller 签名一路向下传播 ct
public async Task<IActionResult> ListCampaigns(CancellationToken ct)
{
    var campaigns = await _db.Campaigns.ToListAsync(ct);
    var enriched = await _enricher.EnrichAsync(campaigns, ct);
    return Ok(enriched);
}
```

ASP.NET Core **注入** `CancellationToken ct` 到 Controller Action 中，当请求被取消（客户端断开、超时）时触发。EF Core、`HttpClient`、`MediatR`、`StreamReader.ReadLineAsync`，几乎所有现代异步 API 都接受 `CancellationToken`。**传进去。**

### 双重取消模式

当你还需要因为自己的原因取消时：

```csharp
// 把请求的 CT 和你自己的合并
public async Task<List<Result>> SearchAsync(string q, CancellationToken ct)
{
    using var timeoutCts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
    using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(
        ct, timeoutCts.Token);

    return await _api.SearchAsync(q, linkedCts.Token);
}
```

无论是请求被取消**还是** 5 秒超时触发，都会取消。

**Mattrx 指标**：10 个端点 + 18 个服务方法更新，传播 `CancellationToken`。孤儿请求的 `TaskCanceledException` 频率：**240/周 → 6**。峰值 CPU：-4%。更大的质量收益：关于"仪表盘卡住了"的支持工单变少了。

## 错误 #6：在不需要异步的方法上标 async

**症状**：给方法标 `async` 总是分配一个状态机，即使方法里没有任何 `await`。对于一个每秒调用 10 万次的方法，就是 10 万次不必要的分配。

### 修复前

```csharp
// 无故标 async —— 分配状态机
public async Task<Campaign> WrapCachedAsync(Guid id)
{
    if (_cache.TryGetValue(id, out Campaign c))
        return c;
    return await LoadAsync(id);
}

// 有 async 但没有 await —— 纯粹浪费
public async Task<int> AddAsync(int a, int b)
{
    return a + b;
}
```

编译器发出一个状态机结构体（`<WrapCachedAsync>d__0`），在第一次 `await` 时装箱（如果有的话），并付出捕获同步上下文的成本。对于缓存命中的情况（未走 await 分支）这是浪费。

### 修复后

```csharp
// 缓存命中路径是同步的；仅在穿透时才分配状态机
public Task<Campaign> WrapCachedAsync(Guid id)
{
    if (_cache.TryGetValue(id, out Campaign c))
        return Task.FromResult(c);
    return LoadAsync(id);
}

// 纯同步方法不需要 async
public Task<int> AddAsync(int a, int b)
    => Task.FromResult(a + b);
```

对超热路径，优先使用 `ValueTask`（见错误 #10）以避免连 `Task.FromResult` 的分配都省掉。

### 什么时候保留 async

- 带异常处理的多个 await：`try { await A(); await B(); } catch (...) { ... }`——async 机制能干净地展开异常。直接返回 Task 则需手动 `.ContinueWith` 处理错误。
- `using` / `await using` 块：需要 `async` 才能正确 dispose。
- 任何可读性收益超过分配成本的场景。

**嗅探测试**：如果你的方法体是 `return SomeOtherAsync(x);` 或 `return Task.FromResult(x);`——**去掉 async**。如果方法体只有一个尾部的 `await`，后面没有其他逻辑——**去掉 async**，直接返回 Task。

```csharp
// 模式 1：单尾部 await —— 直接返回
public Task<Foo> GetAsync(Guid id) => _db.Foos.FindAsync(id).AsTask();

// 模式 2：分支中有一个分支 await —— 两个分支都返回 Task
public Task<Foo> GetCachedAsync(Guid id) =>
    _cache.TryGetValue(id, out Foo f) ? Task.FromResult(f) : GetAsync(id);
```

**Mattrx 指标**：约 40 个方法重构。`/api/dashboard/kpis` 上异步状态机分配：**-40%**。热端点 GC % 时间：**9% → 3%**。不是头条收益，但和其他修复叠加起来效果显著。

## 错误 #7：Fire-and-forget 但没有错误捕获

**症状**：`_ = SomeAsync()` 或 `Task.Run(...)` 不加 `await`。异常消失。你发现有问题，是在六小时后数据静默不一致时。

### 修复前

```csharp
// Fire-and-forget —— 异常被静默吞噬
public IActionResult Archive(Guid id, [FromServices] AppDbContext db)
{
    _ = SendAuditEmailAsync(id);      // 异常？没人知道。
    _ = _hub.NotifyAllAsync(id);      // 异常？崩溃信号丢失。
    return Accepted();
}
```

当 `SendAuditEmailAsync` 抛出异常时，Task 的 faulted 状态被 GC 终结器线程观察（如果它真的被观察的话）——在 Modern .NET 中这不再崩溃进程——但错误从日志中消失。**你不会知道。**

### 隐藏 bug 模式：空的 try/catch

```csharp
// "捕获并忽略" —— 仍然隐藏 bug
_ = Task.Run(async () =>
{
    try { await SendAuditEmailAsync(id); }
    catch { /* 别崩溃进程 */ }
});
```

如果你不**记录**失败，你是在用数据损坏换堆栈追踪。

### 修复后

最佳实践：使用适当的后台工作模式：

```csharp
// 入队工作；消费者托管服务以重试 + 日志方式运行它
public IActionResult Archive(Guid id, [FromServices] IBackgroundWorkQueue queue)
{
    queue.Enqueue(new SendAuditEmail(id));
    queue.Enqueue(new NotifySubscribers(id));
    return Accepted();
}
```

如果你**必须**在请求线程上 fire-and-forget，显式观察 Task：

```csharp
// 最低可接受的方案 —— 记录每一次失败
public IActionResult Archive(Guid id)
{
    _ = SafeFireAndForget(SendAuditEmailAsync(id), "SendAuditEmail");
    _ = SafeFireAndForget(_hub.NotifyAllAsync(id),  "HubNotifyAll");
    return Accepted();
}

private async Task SafeFireAndForget(Task task, string operation)
{
    try { await task; }
    catch (Exception ex) { _logger.LogError(ex, "Fire-and-forget failed: {Op}", operation); }
}
```

这个模式仍有作用域捕获问题，所以优先使用队列模式。但如果**必须**，至少要记录。

**Mattrx 指标**：23 个 fire-and-forget 调用点。18 个迁移到后台工作队列，5 个包裹在 `SafeFireAndForget` 中。Sentry 幽灵失败报告：**18/周 → 0**。更大质量收益：当什么东西确实坏了的时候，我们**现在能看见了**。

## 错误 #8：在循环里 await 而不是批量处理

**症状**：`foreach (var x in xs) await ProcessAsync(x)`——N 次串行往返，而一次批量调用或 `Task.WhenAll` 就能做到。

### 修复前

```csharp
// 200 个 webhook × 50ms 每个 = 10 秒
public async Task ReplayAsync(IReadOnlyList<WebhookEvent> events, CancellationToken ct)
{
    foreach (var e in events)
    {
        await _partner.SendAsync(e, ct);   // 每个：~50ms HTTP 往返
    }
}
```

### 修复后

```csharp
// 有界并行 —— 一次启动 10 个，await 全部
public async Task ReplayAsync(IReadOnlyList<WebhookEvent> events, CancellationToken ct)
{
    using var sem = new SemaphoreSlim(initialCount: 10, maxCount: 10);

    var tasks = events.Select(async e =>
    {
        await sem.WaitAsync(ct);
        try { await _partner.SendAsync(e, ct); }
        finally { sem.Release(); }
    });

    await Task.WhenAll(tasks);
}
```

为什么要限制并发：纯粹的 `Task.WhenAll(events.Select(SendAsync))` 对 10,000 个事件会同时触发 10,000 个 HTTP 请求，耗尽连接池并触发限流。`SemaphoreSlim(10)` 将并发上限限制为 10 个在途请求，平衡吞吐量和下游系统的负载。

### 更好的方案：Parallel.ForEachAsync（.NET 6+）

```csharp
public Task ReplayAsync(IReadOnlyList<WebhookEvent> events, CancellationToken ct) =>
    Parallel.ForEachAsync(events,
        new ParallelOptions { MaxDegreeOfParallelism = 10, CancellationToken = ct },
        async (e, token) => await _partner.SendAsync(e, token));
```

### 什么时候应该串行

- 下游系统要求每次只一个请求（速率限制 = 1，或无队列）
- 每个操作的副作用必须严格有序
- 操作共享非线程安全的状态

**Mattrx 指标**：`/api/webhook/replay` p95 **9.4s → 720ms**（-92%）。

## 错误 #9：跨 await 持有 lock

**症状**：C# 的 `lock` 语句不跨 `await` 边界。如果你在 `lock` 块内 await，线程可以在 await 之后切换——然后**另一个线程**进入你以为是锁定的代码。

### 修复前 —— 危险的变通方案

```csharp
// lock 不跨 await！
lock (_syncRoot)
{
    await DoSomethingAsync();  // lock 在此之后就被丢掉了
}
```

这根本不能编译——编译器阻止你。但人们会做这个：

### "假 lock"——用一个标志位

```csharp
// 不是真正的互斥 —— 是竞态条件
private bool _busy;

public async Task ProcessAsync()
{
    if (_busy) return;
    _busy = true;
    await DoSomethingAsync();   // 另一个请求可能已经设了 _busy = true
    _busy = false;
}
```

两个并发请求都能通过 `if (_busy)` 检查，因为没有任何东西阻止它们同时读取。

### 修复后

```csharp
// SemaphoreSlim 是异步感知的
private readonly SemaphoreSlim _gate = new(1, 1);

public async Task ProcessAsync(CancellationToken ct)
{
    await _gate.WaitAsync(ct);
    try
    {
        await DoSomethingAsync(ct);
    }
    finally
    {
        _gate.Release();
    }
}
```

### 更好的方案：用数据库级并发

如果能用数据库乐观并发控制或 `SELECT ... FOR UPDATE` 解决，就不要在应用层锁：

```csharp
// 用 EF Core 并发令牌
var saved = await _db.SaveChangesAsync(ct);
// 如果别人先改了，ConcurrencyException 会在这行触发
```

**Mattrx 指标**：**4 次生产事件 → 0**。把自定义标志位锁替换为 `SemaphoreSlim` 后，不再有关于重复写入的奇怪竞态条件 bug。

## 错误 #10：ValueTask\<T\> 的误用（或热路径中缺失）

**症状**：要么 await 了 `ValueTask<T>` 两次（未定义行为），要么在热路径上错过了免费的分配节省。

### 何时使用 ValueTask\<T\>

`ValueTask<T>` 是一个结构体，能在结果立即可用时避免堆分配。当你预期以下情况时可考虑：

- 高比例同步完成（例如缓存命中）
- 极高频率调用（每秒数十万次）
- 方法返回 `Task<T>` 是 GC 热点

```csharp
// 热路径上：缓存命中率 95% —— ValueTask 是双赢
public ValueTask<Campaign?> GetCampaignAsync(Guid id, CancellationToken ct)
{
    if (_cache.TryGetValue(id, out var c))
        return new ValueTask<Campaign?>(c);        // 无分配
    return new ValueTask<Campaign?>(LoadFromDbAsync(id, ct));
}
```

对比基准：

| 场景                  | Task\<T\>          | ValueTask\<T\>                 |
| --------------------- | ------------------ | ------------------------------ |
| 缓存命中（95%）       | ~72 bytes 每次调用 | **~0 bytes**                   |
| 缓存未命中 + DB（5%） | ~72 bytes          | ~56 bytes (struct) + Task 包装 |

### 何时不要用

- **绝不要** await 同一个 `ValueTask<T>` 两次——它是结构体，第二次 await 是未定义行为。
- 不要作为 `Task.WhenAll` 的参数使用（除非你先 `.AsTask()`）。
- 不要存储为字段——它是为局部使用设计的。
- 当同步完成率 < 50% 时——`Task<T>` 更简单，开销差距可忽略。

**Mattrx 指标**：在热序列化器中引入 `ValueTask<T>`：**-28% 分配**。影响最集中在 `/api/dashboard/kpis`——每天 8 万请求，每个请求做 6 次缓存读取。

## 排查手册

当你怀疑有异步问题时，按这个顺序跑：

```
1. dotnet-counters 快速扫描
   dotnet-counters monitor -p <pid> System.Runtime
   → 看 threadpool-queue-length、threadpool-thread-count

2. grep 找已知坏模式
   grep -rn "\.Result\b" --include="*.cs"
   grep -rn "async void" --include="*.cs"
   grep -rn "_ = " --include="*.cs" | grep "Async"

3. Application Insights 端到端追踪
   → 找"阻塞"与"await"时长之间的间隙

4. PerfView "Async Causality"
   → 可视化每个异步链和锁等待

5. dotnet-stack report
   → 当所有东西都卡住时：看实时线程栈
```

## 合并前的心智检查清单

在合并任何非平凡的异步代码之前，逐项确认：

- [ ] 没有 `.Result`、`.Wait()`、`.GetAwaiter().GetResult()`——除非你明确在 async `Main` 中，并且有理由
- [ ] 没有 `async void`，只有 `async Task` 或 `async Task<T>`
- [ ] 独立的 I/O 操作使用 `Task.WhenAll` 并行化
- [ ] `Task.Run` 仅用于 CPU 密集工作，且 > ~50ms
- [ ] 每个长时间运行的异步方法都传播 `CancellationToken`
- [ ] 只在方法体确实需要 `await` 时才写 `async` 关键字
- [ ] Fire-and-forget 有错误日志，或使用后台工作队列
- [ ] 循环中不串行 await；使用 `Task.WhenAll` 或 `Parallel.ForEachAsync` 并进行限流
- [ ] 没有 `lock` / `Monitor` 跨 `await`；用 `SemaphoreSlim` 代替
- [ ] 热路径考虑 `ValueTask<T>`；绝不在同一 `ValueTask<T>` 上 await 两次

## 结语

这些错误都不是 ASP.NET Core 独有的。async/await 的所有误用本质上都是对同一个事实的误解：**async 释放线程**。阻塞线程、串行化独立的 I/O、分配无用状态机、泄漏不可观测的工作——这些只是那条核心理解的失败变体。

Mattrx 的经验说明了两点：第一，这些错误非常普遍，即使在有经验的团队中也不例外。第二，**修复它们不需要重写**。两周，零新基础设施，效果：3.75 倍吞吐量，零死锁，延迟降低 83-92%。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 **Aide Hub**。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [10 Async/Await Mistakes That Kill ASP.NET Core API Performance — PrepStack](https://prepstack.co.in/blog/async-await-mistakes-that-kill-aspnet-core-api-performance-guide)
