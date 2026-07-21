---
pubDatetime: 2026-07-21T15:16:21+08:00
title: "System.Threading.Channels：.NET 内置的生产者-消费者管道，不需要 RabbitMQ"
description: "一个上传接口在并发上来后把 CPU 打满、把其他请求拖死。问题不在异步写得不对，而在没有一条带背压的工作管道。这篇文章用 System.Threading.Channels 从零搭出生产者-消费者模式，把并发控制、背压和平滑关停一起讲清楚。"
tags: [".NET", "Channels", "Async", "BackgroundService", "Architecture"]
slug: "system-threading-channels-producer-consumer-dotnet"
ogImage: "../../assets/961/01-cover.png"
source: "https://thecodeman.net/posts/producer-consumer-with-channels-in-dotnet"
---

有个上传接口是这样的：用户传一批图片，后端挨个压缩尺寸，返回结果。单次请求跑得挺快，demo 演示一切正常。然后客户写了脚本一口气怼了几百个请求 —— CPU 直接顶到 100%，登录、搜索、健康检查全部开始超时，因为线程池被压缩任务淹没了。

问题很清楚：这些压缩任务不需要在响应返回之前做完，只需要**被接受下来**，再按自己的能力慢慢处理。这就是生产者-消费者问题：一端把工作交出去，另一端以自己能承受的节奏来消费。而且你不需要 RabbitMQ，也不需要额外引入后台任务库 —— .NET 内置的 `System.Threading.Channels` 就够了。

`System.Threading.Channels` 在 `System.Threading.Channels` NuGet 包里（.NET Core 3.0+ 内置），用来在同一进程内做生产者和消费者之间的数据传递。生产者往 `ChannelWriter<T>` 写，消费者从 `ChannelReader<T>` 读，线程安全和异步交接都由 Channel 自己搞定。关键的一点是：**有界 Channel 自带背压**，这才是大多数人容易忽略但最重要的部分。

## 别用 Task.Run 敷衍了事

直觉反应通常是"改成异步就好了" —— 把工作扔给 `Task.Run`，然后立刻返回：

```csharp
[HttpPost("process")]
public IActionResult Process(UploadRequest request)
{
    // Fire-and-forget。看着像异步，实际上是个坑。
    _ = Task.Run(() => _imageService.Resize(request));
    return Accepted();
}
```

请求回来很快，看起来没问题。实际上有三个坑：

1. **没有并发上限**：同一个 burst 过来照样把 CPU 打满，只不过这次返回了 202
2. **进程重启丢数据**：进程回收时没处理完的任务直接被干掉，消失得无影无踪
3. **异常被吞**：`_ =` 放弃了 task，内部抛异常你根本看不到

你用一组可见的慢请求换来了一堆不可见的丢任务。真正的修法是在两端之间放一个**有上限的队列**。队列满了，生产者就得等着 —— 这个等待就是信号：你收活的速度超过了处理速度。

## Channel 基础：Writer、Reader 和上限

`Channel<T>` 有两个端口，创建一次，分发给两端：

```csharp
using System.Threading.Channels;

var channel = Channel.CreateBounded<WorkItem>(new BoundedChannelOptions(100)
{
    FullMode = BoundedChannelFullMode.Wait,
    SingleReader = false,
    SingleWriter = false
});

ChannelWriter<WorkItem> writer = channel.Writer;
ChannelReader<WorkItem> reader = channel.Reader;
```

上面这个 Channel 容量是 100。当 100 个坑被占满时，`WriteAsync` 会等着，直到消费者腾出位置 —— 这就是背压。

`FullMode` 是整个设计的核心，四种模式：

```csharp
// Wait        - WriteAsync 等到有空位为止。这是背压，默认选择。
// DropWrite   - 满了就悄悄丢弃当前写入的项。
// DropOldest  - 踢掉最旧的一项，给新的腾地方。
// DropNewest  - 踢掉最新入队的一项，把刚来的留下。
```

`Wait` 适合"每一条都不能丢"的场景，宁可拖慢生产者也不能掉数据。`Drop*` 适合遥测、实时推送这种"新鲜度比完整性重要"的场景。

`SingleReader` 和 `SingleWriter` 是性能优化。只有**真的**只有一个读者或一个写者时才设为 `true`，Channel 内部会走更快的路径。不确定就留着 `false`：写错了 `true` 是偶发的竞态 bug，写错了 `false` 只是稍微慢一点。

## 生产者：一个负责接活的 Endpoint

生产者只负责写。唯一的判断是：满了怎么办？

```csharp
[ApiController]
[Route("api/[controller]")]
public class ProcessingController : ControllerBase
{
    private readonly ChannelWriter<WorkItem> _writer;

    public ProcessingController(Channel<WorkItem> channel)
        => _writer = channel.Writer;

    [HttpPost]
    public async Task<IActionResult> Enqueue(
        WorkItem item, CancellationToken ct)
    {
        await _writer.WriteAsync(item, ct);
        return Accepted();
    }
}
```

`WriteAsync` 在有空位时立即完成，满了就等。如果你的 API 是面向外部调用方的，可能更倾向于拒绝而不是让对方干等，那就用 `TryWrite` 返回 429：

```csharp
if (!_writer.TryWrite(item))
    return StatusCode(StatusCodes.Status429TooManyRequests,
        "服务繁忙，请稍后重试。");

return Accepted();
```

`TryWrite` 永远不会阻塞，满了直接返回 `false`。内部批处理任务让它等，公开 API 快速拒绝 —— 两种策略取决于谁在调用。

## 消费者：一个 BackgroundService 负责干活

消费者放在 `BackgroundService` 里，应用启动时就开始跑，停止时跟着收尾。核心循环就一条 `ReadAllAsync`：

```csharp
public class WorkConsumer : BackgroundService
{
    private readonly ChannelReader<WorkItem> _reader;
    private readonly ILogger<WorkConsumer> _logger;

    public WorkConsumer(
        Channel<WorkItem> channel, ILogger<WorkConsumer> logger)
    {
        _reader = channel.Reader;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(
        CancellationToken stoppingToken)
    {
        await foreach (var item in _reader.ReadAllAsync(stoppingToken))
        {
            try
            {
                await ProcessAsync(item, stoppingToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "处理 {Id} 失败", item.Id);
            }
        }
    }

    private async Task ProcessAsync(
        WorkItem item, CancellationToken ct)
    {
        // 这里放真实的压缩 / 发送 / 写入逻辑
        await Task.Delay(50, ct);
    }
}
```

两个容易踩坑的地方：

1. **try/catch 要包在循环里面、单条处理外面**。如果包在整个 `await foreach` 外面，第一条出错就结束循环，消费者悄悄死掉，而应用还在继续收活。
2. `ReadAllAsync` 在 Channel 被标记完成时自然退出，这是平滑关停的基础。

## 注册到 DI，跑多个消费者

Channel 注册为 Singleton，生产者和消费者共享同一个实例：

```csharp
builder.Services.AddSingleton(_ =>
    Channel.CreateBounded<WorkItem>(new BoundedChannelOptions(100)
    {
        FullMode = BoundedChannelFullMode.Wait
    }));

// 三个消费者从同一个 Channel 里读 —— 并发度你来控制
builder.Services.AddHostedService<WorkConsumer>();
builder.Services.AddHostedService<WorkConsumer>();
builder.Services.AddHostedService<WorkConsumer>();
```

消费者的数量就是你的并发旋钮。一个消费者严格保序处理；三个消费者同时最多处理三条。把这个数字设成下游能承受的值 —— 如果 `ProcessAsync` 最终要写数据库，而数据库只抗得住 10 个并发写，就注册 10 个消费者，别注册 50 个。这是 `Task.Run` 版本永远给不了你的东西：一个固定的、已知的工作并发上限。

## 平滑关停：部署时别把缓冲区的东西丢掉

应用关停时，Channel 里可能还有没消费完的项。如果直接让进程死掉，缓冲区的数据就丢了。修法是在关停时标记 Writer 完成，让消费者把剩余的排空。用一个轻量的 `IHostedService` 发这个信号：

```csharp
public class ChannelCompleter : IHostedService
{
    private readonly ChannelWriter<WorkItem> _writer;

    public ChannelCompleter(Channel<WorkItem> channel)
        => _writer = channel.Writer;

    public Task StartAsync(CancellationToken ct)
        => Task.CompletedTask;

    public Task StopAsync(CancellationToken ct)
    {
        _writer.Complete();
        return Task.CompletedTask;
    }
}
```

`Complete()` 被调用后，`WriteAsync` 对任何新生产者都会抛异常，而每个消费者的 `ReadAllAsync` 会继续把缓冲区读完才退出循环。给 Host 一个足够的关停时间：

```csharp
builder.Services.Configure<HostOptions>(o =>
    o.ShutdownTimeout = TimeSpan.FromSeconds(30));
```

部署时缓冲排空再结束，而不是把进行中的工作扔掉。这一步是把 demo 变成线上能用代码的关键。

## 什么情况下不应该用 Channels

Channels 跟进程同生共死。进程重启了，缓冲区的项就没了 —— 没有持久化、没有重放、没有确认机制。这对**丢了也无所谓或能重新生成**的工作完全没问题：缩略图、缓存预热、非关键通知。但如果是不能丢的付款，或者法律要求必须发出的邮件，Channels 就不够用了。

一旦你需要跨重启持久化、带死信路径的重试、或者跨独立服务共享工作，Channels 就到头了，你需要的是一个真正的消息队列或者数据库支撑的 [Outbox 模式](https://thecodeman.net/posts/message-queues-dotnet-backpressure-idempotency-outbox)。Channels 是进程内工具 —— 当生产者和消费者住在同一个应用里、缓冲区丢了也能接受时，就用它。上线之前想清楚自己属于哪种情况，别等到第一次重启吃掉队列之后才明白。

## 和 BlockingCollection 的区别

很多同学知道 `BlockingCollection<T>`，会问这俩有什么区别。`BlockingCollection` 在队列满或空的时候阻塞调用线程，白白占着一个线程池线程等着。Channels 是异步优先的 —— `WriteAsync` 和 `ReadAsync` 把线程让出来而不是阻塞它，所以一个等待中的生产者或消费者几乎不消耗资源。在现代异步 .NET 上，原来用 `BlockingCollection` 的地方几乎都可以换成 Channels。

## 参考

- [Producer-Consumer in .NET with System.Threading.Channels](https://thecodeman.net/posts/producer-consumer-with-channels-in-dotnet) - Stefan Đokić
- [System.Threading.Channels 官方文档](https://learn.microsoft.com/en-us/dotnet/core/extensions/channels)
- [Message Queues, Backpressure, Idempotency & Outbox Pattern](https://thecodeman.net/posts/message-queues-dotnet-backpressure-idempotency-outbox)
