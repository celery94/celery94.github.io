---
pubDatetime: 2026-06-26T08:09:49+08:00
title: "一位资深 .NET 开发者的 20+ 条实战建议：从 DI、Async 到 EF Core 优化"
description: "这些建议不来自教程或文档，而是来自凌晨两点的 debug、遗留代码的挣扎和踩过的坑。覆盖依赖注入、异步编程、EF Core 优化、CancellationToken、缓存策略、安全、异常处理等 20+ 个领域，每条都附 bad/good 代码对比和作者的真实生产判断。"
tags: [".NET", "Best Practices", "C#", "EF Core", "Dependency Injection"]
slug: "senior-dotnet-developer-tips-2026"
ogImage: "../../assets/904/01-cover.png"
source: "https://codewithmukesh.com/blog/20-tips-from-a-senior-dotnet-developer/"
---

这些年跟 .NET 打交道，真正学到的东西不是在教程里读到的，而是凌晨两点 debug 不可能的问题、跟混乱的遗留代码斗争、以及用惨痛代价换来的"千万别这么做"。有些错误很疼，但正是它们塑造了我今天构建软件的方式。

无论你刚入门还是用了 .NET 多年，这 20 多条建议能帮你写出更干净、更快、更可维护的应用。如果你想构建健壮、可扩展的 API 并且真正提升 .NET 水平，认真读下去——这会帮你省掉很多年的试错。

**Top 5 最高 ROI 建议：** (1) 搞对 DI——在代码库膨胀之前选对 Transient/Scoped/Singleton；(2) 正确写 `async/await`——绝不 `.Result` 或 `.Wait()`，绝不在事件处理器外用 `async void`；(3) 有意识地用 EF Core——读查询全加 `AsNoTracking()`（2-5 倍提速），留意 N+1，批量操作用 `ExecuteUpdate`；(4) 把 `CancellationToken` 传遍每个异步调用——这是最被低估的生产杠杆；(5) 用 `HybridCache`（.NET 10 新默认）做缓存，别再手拼 MemoryCache + Redis。

## 1. 把基础打牢

跳进复杂框架和设计模式之前，先把地基夯实。扎实的 C#、.NET Core 和 ASP.NET 基础，远比追新框架重要。关注这些领域：泛型、委托、async/await、LINQ、模式匹配；SOLID 原则、继承、多态、封装；.NET 10 的 DI、请求管道、中间件、配置管理、Minimal API；数据结构与算法基础；异常处理和调试工具。

技术怎么变，这些概念不变。

## 2. 写干净的代码

干净代码不是审美问题，它直接影响开发效率。两条原则最关键：**单一职责**——一个方法只做一件事；**有意义命名**——如果需要注释才能解释方法在干什么，名字就不够好。

```csharp
// 烂代码
public void ProcessData(string d)
{
    var x = d.Split(',');
    for (int i = 0; i < x.Length; i++)
        if (x[i].Contains("error"))
            Console.WriteLine("Found error!");
}

// 好代码
public void ProcessLogs(string logData)
{
    var logEntries = ParseLogEntries(logData);
    foreach (var entry in logEntries)
        if (IsError(entry))
            Console.WriteLine("Found error!");
}
```

## 3. 搞懂依赖注入

DI 是 .NET 里最强大的特性之一，但很多人要么不用要么用错。最大的错误是在类里直接 new 依赖——这让代码僵化且难测。

```csharp
// 烂：紧耦合
public class OrderService
{
    private readonly EmailService _emailService;
    public OrderService() => _emailService = new EmailService();
}

// 好：注入接口
public class OrderService
{
    private readonly IEmailService _emailService;
    public OrderService(IEmailService emailService) =>
        _emailService = emailService;
}
```

一定要搞懂 Transient、Scoped、Singleton 三种生命周期的区别——选错生命周期是我在生产代码里见过最多的 DI bug。

## 4. 正确使用异步编程

`async/await` 能提升响应性和可扩展性，但用错会导致死锁和性能瓶颈。三条硬规则：

**绝不阻塞异步代码。** `.Result` 和 `.Wait()` 在 UI 和 Web 应用中可能直接死锁。

```csharp
// 烂
public void ProcessData() { var result = GetData().Result; }
// 好
public async Task ProcessData() { var result = await GetData(); }
```

**CPU 密集操作不要套 async。** `Task.FromResult` 包一个纯计算没有任何意义，直接同步返回。

**库代码里用 `ConfigureAwait(false)`**，避免捕获调用上下文。

## 5. 记录该记录的，别记录不该记录的

日志是生产和 debug 的命脉，但什么都记和什么都不记一样有害。用对日志级别（Debug → Information → Warning → Error → Critical），带上上下文信息（UserId、CorrelationId），绝不记录敏感数据。

```csharp
// 烂：暴露敏感信息
_logger.LogInformation($"User: {user.Email}");

// 好：带上下文但不暴露隐私
_logger.LogInformation("Processing request for user {UserId}", user.Id);
```

推荐用 Serilog 做结构化日志，输出 JSON 并送到 CloudWatch、Elastic 或 Application Insights。

## 6. 用 EF Core，但要聪明地用它

EF Core 简化了数据库访问，但盲目依赖会导致严重性能问题。

**永远过滤后再取数据。** `.ToList()` 不加 `Where` 会把整张表拉进内存。

**用 `Include` 避免 N+1 查询。** 懒加载在循环里触发的独立查询是性能杀手。

```csharp
// 烂：N+1
var users = await _context.Users.ToListAsync();
foreach (var user in users)
    Console.WriteLine(user.Orders.Count); // 每次循环一次查询

// 好：Eager loading
var users = await _context.Users.Include(u => u.Orders).ToListAsync();
```

**只读查询加 `AsNoTracking()`。** 作者在 EF Core 10 上对 10,000 行表的 BenchmarkDotNet 实测：tracked 查询 4.2ms / 3.8MB，加 `AsNoTracking()` 后 2.1ms / 1.9MB——**2 倍提速，内存减半**。在 100K 行表上更夸张：244ms → 84ms（2.9 倍）。

**大数据集做分页。** `Skip()` + `Take()` 分批拿，别一次全拉。

**常用查询列建索引：**

```csharp
modelBuilder.Entity<User>()
    .HasIndex(u => u.Email)
    .HasDatabaseName("IX_Users_Email");
```

**作者判断：EF Core vs Dapper。** 大部分应用用 EF Core 起步，只在性能敏感的读路径引入 Dapper。EF Core 管 90% 的工作，Dapper 管那些毫秒必争的热路径。别二选一，各用所长。

## 7. CancellationToken 极其重要

这是整份清单里最被低估的一条。它实现简单，却能在大流量下防止资源浪费。

```csharp
// 烂：忽略取消
[HttpGet("long-task")]
public async Task<IActionResult> LongRunningTask()
{
    await Task.Delay(5000); // 客户端断开后仍在浪费资源
    return Ok("Task Completed");
}

// 好：响应取消
[HttpGet("long-task")]
public async Task<IActionResult> LongRunningTask(
    CancellationToken cancellationToken)
{
    await Task.Delay(5000, cancellationToken);
    return Ok("Task Completed");
}
```

每个 async 方法都应该接收并向下传递 CancellationToken——包括 EF Core 查询：

```csharp
var users = await _context.Users
    .Where(u => u.IsActive)
    .ToListAsync(cancellationToken);
```

## 8. 数据库性能不只是 ORM 的事

即使用了 Dapper，索引设计、查询结构和缓存策略仍然决定性能上限。常用筛选列建索引，但别过度索引——每个索引都会拖慢 INSERT、UPDATE 和 DELETE。如果数据很少变化，先查缓存再查库。

## 9. 学 RESTful API 最佳实践

API 不只是"能跑就行"——要可扩展、安全、好用。核心实践：用缓存、压缩和分页优化性能；实施速率限制防滥用；用 HTTPS 并校验所有输入；用 `ProblemDetails` 返回结构化错误响应；监控 API 调用指标和失败率。

## 10. 优雅地处理异常

别吞异常，也别把原始异常直接丢给客户端。

```csharp
// 烂：吞掉异常
try { var result = await _repository.GetDataAsync(); }
catch (Exception ex) { /* silent failure */ }

// 好：记录并返回安全信息
try { var result = await _repository.GetDataAsync(); }
catch (Exception ex)
{
    _logger.LogError(ex, "Error while fetching data");
    throw new ApplicationException(
        "An unexpected error occurred, please try again later.");
}
```

用全局异常处理中间件统一管理，用 `ProblemDetails` 返回结构化错误信息。

## 11. 写测试

单元测试聚焦单个组件，用**手写 fake/stub** 而不是 mock 框架；集成测试验证组件间协作，用 `WebApplicationFactory` 测试 API 端点。把测试放进 CI/CD 自动跑。

## 12. 后台任务：从简单开始

对于周期性任务，先用 `BackgroundService`。需要任务持久化（重启后不丢）、重试机制或运维面板时，升级到 Hangfire。Quartz.NET 只在需要复杂任务依赖链时才用。别从第一天就过度设计。

```csharp
public class DataSyncService : BackgroundService
{
    protected override async Task ExecuteAsync(
        CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await SyncDataAsync();
            await Task.Delay(
                TimeSpan.FromMinutes(5), stoppingToken);
        }
    }
}
```

## 13. 把安全当一等公民

三条底线：**绝不硬编码密钥**——用环境变量、Azure Key Vault 或 AWS Secrets Manager；**用 OAuth 2.0 / JWT + RBAC** 做认证授权；**正确配置 CORS**，别用 `AllowAnyOrigin()`，显式列出受信域名。

## 14. 搞懂缓存策略

缓存是提升性能最直接的手段之一。**.NET 10 引入了 `HybridCache`**，把 MemoryCache 和分布式缓存统一进一个 API，内置防缓存击穿。作者的负载测试：在频繁查询的 endpoint 前加一层 MemoryCache，500 并发下平均响应从 45ms 降到 2ms，数据库查询减少 95%。

**作者判断：** 单实例应用从 MemoryCache 开始，.NET 10 多实例场景升级到 HybridCache，只有需要跨多个服务共享状态时才上独立 Redis 集群。最好的缓存是离应用最近的缓存——别加不必要的网络跳。

## 15. 别滥用反射

反射比直接调用慢很多，而且绕过编译期类型检查。在 .NET 10 里，source generator 已经消除了大多数以前需要反射的场景——JSON 序列化、依赖注册、对象映射都可以在编译期完成。如果你在应用代码里写 `typeof()` 或 `GetType()`，先问自己能不能用泛型或接口代替。

## 16. 用 Polly 做韧性策略

调用外部服务需要重试、熔断和超时保护。.NET 10 推荐用 `Microsoft.Extensions.Resilience` + `Microsoft.Extensions.Http.Resilience`（基于 Polly），它们集成 DI 容器并提供标准化遥测。

**作者判断：** 对跨网络边界的调用（第三方支付网关、外部 API、云存储）上全套 Polly（重试 + 熔断 + 超时）。内部服务间调用通常一个超时就够了——别过度工程化。

## 17. 用 CI/CD 自动化部署

手动部署低效且易出错。用 GitHub Actions 把构建、测试和发布全自动化。CI 确保每次代码变更都经过构建和测试，CD 让发布不需要人工干预。

## 18. 跟上 .NET 版本更新

.NET 10 GA 带来了 HybridCache、EF Core 命名查询过滤器、更好的 Minimal API 工具和 AOT 编译。.NET 11 预览版已经在路上了，而还有很多团队在用 .NET 6（已停止支持）甚至更老的版本。拖延越久，技术债越重。至少维持在受支持的 LTS 版本（目前是 .NET 8），定期关注 Microsoft .NET 博客和发布说明，用 `dotnet-outdated` 和 .NET Upgrade Assistant 辅助迁移。

## 19. 用 Feature Flags 做安全发布

Feature flags 让你不重新部署就能开启、关闭或灰度新功能。适合渐进式发布、即时回滚和 A/B 测试。.NET 里用 `Microsoft.FeatureManagement` 集成。

**作者判断：** 每个 flag 都要配一个 30 天清理 ticket。见过太多代码库积压 50+ 个没人敢删的 flag。功能稳定就删掉 flag。

## 20. 用 AI 编程助手提效

两年前作者不会写这条建议，但现在它排在前列。作者每天用 Claude Code——它读整个 solution、遵守项目约定、搭 endpoint、写测试、解释不熟悉的代码。最大的错误是把它当"帮我写整个应用"的魔法按钮。它放大你已经会的知识——如果你不懂 DI、async 正确性或 EF Core 查询行为，你就看不出来 AI 静默产出了一些微妙错误。前面 19 条建议，正是让你能批判性 review AI 产出、而不是盲目粘贴的基础。

## 21. 持续学习

.NET 在持续演进。读博客、看会议演讲、试验新特性。参与开源项目，在 GitHub、Stack Overflow 和 LinkedIn 上参与讨论。最好的开发者是那些从不停下学习的人。

## 要点

- **DI 和 async/await 是影响力最高的两项技能**——它们塑造整个架构和可扩展性故事。先把这两项搞对。
- **EF Core 强大但需要护栏**——读查询加 `AsNoTracking()`（实测 2 倍提速、内存减半），用 `.Include()` 防 N+1，大数据集分页。性能热路径用 Dapper。
- **CancellationToken 是最被低估的建议**——实现简单、防资源浪费，大多数代码库仍然忽略它。
- **.NET 10 里 HybridCache 是推荐缓存策略**——统一内存和分布式缓存，内置防击穿。
- **韧性策略放外部边界，别过度工程化内部调用。**
- **Feature flags 和 CI/CD 把高风险部署变成安全发布**——但 30 天内清理过期 flag。
- **别停下升级。**.NET 10 已是 GA，.NET 6 已停止支持。拖得越久，迁移越难。

> 如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [原文：20+ .NET 10 Best Practices & Tips from a Senior Developer](https://codewithmukesh.com/blog/20-tips-from-a-senior-dotnet-developer/)
