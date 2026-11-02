---
pubDatetime: 2026-11-02T08:20:00+08:00
title: ".NET 10 HttpClient 容错与重试顺序"
description: "先用一次 500 个 socket 的实测说明连接复用，再讲 .NET 10 的键控客户端注册、标准容错处理器的五个默认策略、默认重试为何把同一个 POST 存了三次，以及处理器相对重试的位置该放哪边。"
tags: ["CSharp", ".NET", "HttpClient", "ASP.NET Core", "Resilience"]
slug: "httpclient-resilience-retry-order-dotnet-10"
ogImage: "../../assets/1124/01-cover.jpg"
source: "https://codewithmukesh.com/blog/httpclient-ihttpclientfactory-resilience-dotnet/"
---

下单接口返回了 `201 Created`，下游数据库里却躺着三条一模一样的订单。调用方只发了一次请求，响应码也正常，重复数据往往要等对账，或者用户自己发现。

这是 .NET 10 里 `AddStandardResilienceHandler()` 的默认行为：它给 POST 也配了重试。把客户端注册到 `IHttpClientFactory`、用键控客户端取实例、再挂上标准容错管道，这套组合能同时解决端口耗尽、DNS 过期和瞬时失败。要让它安全，还得单独确认两件事：哪些 HTTP 方法允许重试，哪些处理器放在重试环外面。

## 500 次请求，500 个端口还在等

`HttpClient` 对象本身很轻，贵的是它底下的 `HttpMessageHandler` 和连接池。每 `new` 一个客户端就自建一套连接池，释放时连接关闭，TCP 端口进入 `TIME_WAIT`，按 RFC 9293 的规定要等 2 倍报文段最大生存期（MSL）过去才回收。端口被占着，新的连接就分不到。

```csharp
using var client = new HttpClient();
using var response = await client.GetAsync(url);
```

`HttpClient` 实现了 `IDisposable`，所以这段代码看起来完全正常，问题恰恰出在这里。

原文作者在 Windows 11、.NET SDK 10.0.401（运行时 10.0.12）上写了一个控制台程序，向本地端点发 500 次 GET，前后各用 `IPGlobalProperties.GetActiveTcpConnections()` 数一次端口：

| 模式                 | 500 次请求耗时 | 新增 TIME_WAIT | 保持的连接 |
| -------------------- | -------------- | -------------- | ---------- |
| `new HttpClient()`   | 374 ms         | 500            | 0          |
| `IHttpClientFactory` | 105 ms         | 0              | 1          |

耗时是单次运行的结果，socket 数量每次一致。500 次请求换来 500 个等待回收的端口，在开发机上只是一行数字，在生产机上就是把端口用光。

静态客户端能省掉这笔开销，代价是 DNS。`HttpClient` 只在建立连接时解析一次地址，之后不再理会 DNS 服务器的 TTL。服务做故障转移、Kubernetes 滚动发布，或者只是换了 IP，长连接都会继续发往旧地址。没有依赖注入容器的地方，给 `SocketsHttpHandler` 设一个 `PooledConnectionLifetime` 就够用了：

```csharp
var handler = new SocketsHttpHandler
{
    PooledConnectionLifetime = TimeSpan.FromMinutes(2)
};
var sharedClient = new HttpClient(handler);
```

## 工厂真正复用和轮换的是 handler

`IHttpClientFactory` 每次 `CreateClient()` 都返回一个新的 `HttpClient`，这些对象创建成本很低；被池化的是底层 handler。默认每个 handler 活两分钟，到期后新建一个，重新做 DNS 解析，旧的在没有任何客户端使用后释放。连接被复用，端口不会堆积，DNS 也能定期刷新。

`SetHandlerLifetime()` 可以按客户端改这个时长。handler 归工厂所有，所以释放工厂给的客户端不会关闭连接，`using` 与否都不影响。

注册入口是 `builder.Services.AddHttpClient()`。它接出四种用法：无参 `CreateClient()`、命名客户端、类型化客户端、键控客户端。前三种出现得更早，键控客户端是 .NET 9 加的。

## 新代码用键控客户端注册

微软的键控 DI 文档现在明确推荐用键控 DI 替代类型化客户端，理由很实际：类型化客户端注册成 transient，一旦被单例捕获，就再也不受工厂管理。键控客户端把这些配置挂在命名客户端上，再把同一个名称暴露成键控服务。

`AddAsKeyed()` 把命名客户端注册成键控服务，键就是客户端名，生命周期是 scoped。包装类可以保留，只是换一种方式拿 `HttpClient`：

```csharp
builder.Services.AddOptions<CatalogApiOptions>()
    .BindConfiguration(CatalogApiOptions.SectionName)
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddHttpClient("catalog", (sp, client) =>
    {
        var options = sp.GetRequiredService<IOptions<CatalogApiOptions>>().Value;
        client.BaseAddress = new Uri(options.BaseAddress);
    })
    .AddAsKeyed()
    .AddHttpMessageHandler<ApiKeyHandler>()
    .AddStandardResilienceHandler();

builder.Services.AddTransient<CatalogClient>();

public sealed class CatalogClient([FromKeyedServices("catalog")] HttpClient httpClient)
{
    // 业务方法不变
}
```

基地址从配置读，没有硬编码；因为 `"catalog"` 同时是一个命名客户端，`factory.CreateClient("catalog")` 拿到的配置和键控注入完全一样，后台服务不用再写第二份。

scoped 带来一个额外好处：开发环境默认开启 scope 校验，单例里误用这个客户端会在启动时直接报错，而不是等到上线后 DNS 不更新才发现。

## 类型化客户端被单例捕获以后

最常见的情况是 `BackgroundService`，它本身就是单例。把 `HttpClient` 存进它的字段，客户端和 handler 就活到进程结束，工厂失去了轮换 handler 的机会。

改法是注入工厂，每轮工作开始时再取客户端：

```csharp
public sealed class ProductSyncService(
    IHttpClientFactory httpClientFactory,
    ILogger<ProductSyncService> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromMinutes(5));
        do
        {
            var client = httpClientFactory.CreateClient("catalog");
            var products = await client.GetFromJsonAsync<List<ProductDto>>(
                "products", stoppingToken);
            logger.LogInformation("Synced {Count} products", products?.Count ?? 0);
        }
        while (await timer.WaitForNextTickAsync(stoppingToken));
    }
}
```

这里拿到的是同一个命名客户端的配置，基地址、`ApiKeyHandler`、容错管道都在，等于什么都没少。原文示例仓库里的完整版本还接住了 `HttpRequestException`、`TimeoutRejectedException` 和 `BrokenCircuitException`——`BackgroundService` 里未处理的异常默认会把整个 host 停掉。

确实需要长生命周期客户端的，可以组合 `UseSocketsHttpHandler` 配 `PooledConnectionLifetime`，再用 `SetHandlerLifetime(Timeout.InfiniteTimeSpan)` 关掉 handler 轮换，把控制权拿回来。

## 一行加进五个策略

```bash
dotnet add package Microsoft.Extensions.Http.Resilience --version 10.11.0
```

原文的三组测试跑在 10.10.0 上，当前稳定版是 10.11.0，默认值没变。装好之后，`AddStandardResilienceHandler()` 一次挂上五层策略，顺序从外到内：

| 顺序 | 策略         | 作用                           | 默认值                                                |
| ---- | ------------ | ------------------------------ | ----------------------------------------------------- |
| 1    | 限流         | 限制对同一依赖的并发请求       | 1,000 个许可，队列 0                                  |
| 2    | 整体超时     | 限制整次调用，重试时间也算在内 | 30 秒                                                 |
| 3    | 重试         | 对瞬时失败重发                 | 3 次，指数退避加抖动，基础延迟 2 秒                   |
| 4    | 熔断         | 依赖连续失败时停止调用         | 失败率 10%，30 秒窗口内最少 100 次请求，熔断持续 5 秒 |
| 5    | 单次尝试超时 | 只管一次尝试                   | 10 秒                                                 |

重试和熔断把 HTTP 500 以上、408、429 当作瞬时失败，另外还有 `HttpRequestException` 和 Polly 的 `TimeoutRejectedException`；400、404 这类直接返回。每次重试都会以 Polly 分类记一条日志。

要改默认值就传一个委托，比如给内网快服务放宽次数、缩短间隔：

```csharp
.AddStandardResilienceHandler(options =>
{
    options.Retry.MaxRetryAttempts = 5;
    options.Retry.Delay = TimeSpan.FromMilliseconds(500);
    options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(5);
});
```

这些选项在启动时校验。想给全部客户端统一加，用 `ConfigureHttpClientDefaults`；某个客户端要例外，先 `RemoveAllResilienceHandlers()` 清掉继承来的配置再加。.NET Aspire 的 ServiceDefaults 就是这么默认挂上的。

```csharp
builder.Services.ConfigureHttpClientDefaults(http =>
    http.AddStandardResilienceHandler());

builder.Services.AddHttpClient("payments")
    .RemoveAllResilienceHandlers()
    .AddStandardResilienceHandler(options =>
        options.Retry.DisableForUnsafeHttpMethods());
```

## 默认重试会把 POST 存三次

标准处理器默认对所有 HTTP 方法重试，POST、PUT、PATCH、DELETE 都在里面。GET 重试只是多一次读取，POST 重试可能多一条数据，而配置里没有任何地方提到方法。

原作者造了一个对照组：下游 `/orders` 端点先把订单写库，然后对前两次调用返回 503，模拟「下游已经提交、但响应超时」的场景。同一个下单请求，一次走默认配置，一次走关掉不安全方法重试的客户端，结果如下：

```json
{"client":"orders-default","finalStatusCode":201,"ordersPlacedByUser":1,"ordersSavedDownstream":3}
{"client":"orders-safe","finalStatusCode":503,"ordersPlacedByUser":1,"ordersSavedDownstream":1}
```

默认配置下，用户下了一单，调用方在约 4.7 秒后收到正常的 `201`，下游存了三条。响应里没有任何异常信号，重复数据只能等对账或用户投诉才暴露。关掉以后再试，订单只存一条，503 立刻返回，应用可以先去查订单状态再决定要不要补发。

改法是一行：

```csharp
.AddStandardResilienceHandler(options =>
{
    options.Retry.DisableForUnsafeHttpMethods();
});
```

`DisableForUnsafeHttpMethods()` 覆盖 POST、PUT、PATCH、DELETE 和 CONNECT，只想排掉个别方法就用 `options.Retry.DisableFor(HttpMethod.Post)`。对端支持幂等键的话（支付类接口基本都支持），重试可以留着，只要每次带同一个键。

## 处理器放在重试里还是重试外

容错处理器自己也是 `DelegatingHandler`，处理器按注册顺序执行。注册在 `AddStandardResilienceHandler()` 之前的，位于重试环外面，一次调用只跑一遍；注册在之后的，每次尝试都跑一遍。

原作者用两个打点 handler 夹住一个先连续返回 503 两次、再返回 200 的端点：

```text
04:29:15.373 outer handler: request started
04:29:15.373 inner handler: attempt returned 503
04:29:16.647 inner handler: attempt returned 503
04:29:20.655 inner handler: attempt returned 200
04:29:20.655 outer handler: final response 200
```

外层只跑一次，看到的是最终的 200；内层跑了三次，间隔约 1.3 秒和 4 秒，对应带抖动的指数退避。

所以生成幂等键、写请求级日志、计数这类一次调用只该发生一次的事情，放容错处理器前面；取 token、签名、加时间戳这类每次尝试都必须重新做的事情，放它后面。加请求头的 handler 尤其要注意：它注册在重试环里，`Headers.Add` 会在每次重试时再追加一个值，所以原文的 `ApiKeyHandler` 先 `Remove` 再 `Add`。

```csharp
var flakyClient = builder.Services
    .AddHttpClient("flaky", client =>
        client.BaseAddress = new Uri("http://localhost:5100/"))
    .AddAsKeyed();

flakyClient.AddHttpMessageHandler<OuterTraceHandler>();
flakyClient.AddStandardResilienceHandler();
flakyClient.AddHttpMessageHandler<InnerTraceHandler>();
```

`AddStandardResilienceHandler()` 返回的 builder 类型变了，所以要先把客户端 builder 存成变量，才能在它之后继续加 handler。

## Polly 还在依赖树里

用 `Microsoft.Extensions.Http.Resilience` 不需要直接引用 Polly，策略都在这个包里。老的 `Microsoft.Extensions.Http.Polly` 和 `AddPolicyHandler()` 仍然可用，新代码没有理由再用。

Polly 本身没有离开依赖树：`Microsoft.Extensions.Http.Resilience` 依赖 `Microsoft.Extensions.Resilience`，后者再依赖 `Polly.Extensions` 和 `Polly.RateLimiting`。这件事在 Polly 采用开源维护费（OSMF）之后一度值得留意：从 2026 年 11 月 16 日起，从使用 Polly 的产品里年收入达到两万美元的组织会被请求按组织每月支付 20 美元，许可证维持 BSD-3-Clause。

公告在 10 月 12 日补了一段说明，结论比传闻宽松：只有直接引用 Polly 才适用这笔费用，通过 `Microsoft.Extensions.Resilience` 或 `Microsoft.Extensions.Http.Resilience` 间接引入的不在其中；费用也只针对 11 月 16 日之后发布的 Polly 下一个主版本。只靠这个包用容错的团队不用做任何处理，项目里直接写了 `PackageReference` 引用 Polly 的才需要在采购上确认。

## 原文作者的生产默认配置

把这套结论压成可以直接抄的配置：

- 每个外部 API 一个键控客户端，外面包一个小类，端点和后台服务共用同一份命名配置
- 所有走网络的客户端都挂 `AddStandardResilienceHandler()`，没有具体理由不改默认值
- 会写数据的客户端一律 `DisableForUnsafeHttpMethods()`，除非对端支持幂等键
- 没有 DI 容器的控制台工具和类库，用静态客户端加 `PooledConnectionLifetime`

他对全局配置同样保守：在一个会往多个服务写数据的 API 里，他不会打开带重试的 `ConfigureHttpClientDefaults`，除非确认每一个客户端都能安全重试。只要漏掉一个写操作客户端，重复数据就会开始出现。

## 默认配置下的四类故障

**Cookie 串号**：池化的 handler 共用一个 `CookieContainer`。需要按用户隔离 cookie 的应用，微软建议不要用 `IHttpClientFactory`，或者在主 handler 上设 `UseCookies = false`。

**改超时后抛 `OptionsValidationException`**：校验器要求熔断的采样窗口至少是单次尝试超时的两倍，报错原文是“The sampling duration of circuit breaker strategy needs to be at least double of an attempt timeout strategy’s timeout interval, in order to be effective.”。把单次尝试超时提到 20 秒、采样窗口还是 30 秒就会触发，两个值要一起改。同一处校验还要求单次尝试超时不能大于整体请求超时。

**请求打到错误路径**：`BaseAddress` 写成 `https://api.example.com/v1` 少了结尾斜杠，和相对路径拼接时 `v1` 会被丢掉，补上斜杠即可。

**抛 `BrokenCircuitException`**：依赖失败太多次，熔断打开了。在全局异常处理里接住，返回 503 加 ProblemDetails，同时用健康检查盯住这个依赖。

要真正收住这套默认值，可以先做两件具体的事：在仓库里搜一遍 `AddStandardResilienceHandler` 和 `AddPolicyHandler`，确认每个会写数据的客户端都排除了重试；再看一眼 handler 的注册顺序，把生成幂等键的那一个挪到容错处理器前面。两处改完，再谈要不要调重试次数。

还有一个问题在正常流量下不会报错，只在服务换 IP 之后慢慢显现：后台服务和单例里有没有存着长生命周期的 `HttpClient`。把它们的构造函数拿出来看一眼，注入的是 `IHttpClientFactory` 还是客户端实例，答案就在那里。

## 参考

- [HttpClient in .NET 10 - IHttpClientFactory and Resilience](https://codewithmukesh.com/blog/httpclient-ihttpclientfactory-resilience-dotnet/)
- [IHttpClientFactory 与键控 DI 文档](https://learn.microsoft.com/en-us/dotnet/core/extensions/httpclient-factory-keyed-di)
- [HTTP resilience in .NET](https://learn.microsoft.com/en-us/dotnet/core/resilience/http-resilience)
- [Microsoft.Extensions.Http.Resilience（NuGet）](https://www.nuget.org/packages/Microsoft.Extensions.Http.Resilience)
- [标准容错选项校验器源码](https://raw.githubusercontent.com/dotnet/extensions/main/src/Libraries/Microsoft.Extensions.Http.Resilience/Resilience/Internal/Validators/HttpStandardResilienceOptionsCustomValidator.cs)
- [HttpClient guidelines](https://learn.microsoft.com/en-us/dotnet/fundamentals/networking/http/httpclient-guidelines)
- [RFC 9293: Transmission Control Protocol](https://www.rfc-editor.org/rfc/rfc9293.html)
- [Polly Open Source Maintenance Fee 公告](https://thepollyproject.org/2026/07/14/polly-osmf-announcement.html)
