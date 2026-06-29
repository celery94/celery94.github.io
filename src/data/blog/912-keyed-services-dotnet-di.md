---
pubDatetime: 2026-06-30T07:23:12+08:00
title: ".NET Keyed Services：一个接口多实现时的依赖注入方案"
description: "用 .NET 8 的 Keyed Services 替代手写工厂 switch。覆盖 AddKeyedScoped、FromKeyedServices 属性、运行时动态解析和 KeyedService.AnyKey 广播模式，帮你去掉一整类样板代码。"
tags: ["CSharp", ".NET", "Dependency Injection", "Architecture"]
slug: "keyed-services-dotnet-di"
ogImage: "../../assets/912/01-cover.png"
source: "https://thecodeman.net/posts/keyed-services-in-dotnet-dependency-injection"
---

一个接口三个实现。`INotificationSender`，有邮件发送器、短信发送器、推送发送器。用户选择怎么被通知，你的代码要把选择变成正确的对象。

于是你写了个工厂。工厂里有个 `switch`：

```csharp
public class NotificationFactory
{
    private readonly IServiceProvider _provider;

    public NotificationFactory(IServiceProvider provider) => _provider = provider;

    public INotificationSender Create(string channel) => channel switch
    {
        "email" => _provider.GetRequiredService<EmailSender>(),
        "sms"   => _provider.GetRequiredService<SmsSender>(),
        "push"  => _provider.GetRequiredService<PushSender>(),
        _ => throw new ArgumentException($"Unknown channel: {channel}")
    };
}
```

这能工作，我也在线上跑过。但它有味道：每加一个渠道，你要改两个地方——注册和 switch。容器已经知道怎么构建所有三个；你只是在它上面又手写了一张查询表。而且你必须注册具体类型（`EmailSender` 而不是 `INotificationSender`），到处泄露实现细节。

从 .NET 8 起，你根本不需要工厂。DI 容器可以持有同一个接口的多个实现，每个打上 key，然后把对的那个递给你。这叫 **keyed services**，它删掉了一整类样板代码。

## Keyed Services 是什么

一个普通注册是按类型键控的：要 `INotificationSender`，拿到为它注册的那一个实现。注册两个，后一个覆盖前一个——前一个被静默遮蔽。

键控注册增加第二个维度：**类型加上 key**。你把 `INotificationSender` 注册三次，每次在不同 key 下，它们共存。解析时你同时要类型和 key。

key 可以是任何对象——string、enum、任何有合理等值判断的东西。string 读起来好，但 enum 给你编译期安全，所以 key 集合固定时我优先用 enum。

## 注册

你熟悉的方法都有键控版本：`AddKeyedSingleton`、`AddKeyedScoped`、`AddKeyedTransient`。第一个参数传 key：

```csharp
builder.Services.AddKeyedScoped<INotificationSender, EmailSender>("email");
builder.Services.AddKeyedScoped<INotificationSender, SmsSender>("sms");
builder.Services.AddKeyedScoped<INotificationSender, PushSender>("push");
```

这就是全部注册。没有工厂、没有 switch、不注册具体类型。每个实现是容器可以构建的真正的 `INotificationSender`，自己的依赖正常注入：

```csharp
public class SmsSender : INotificationSender
{
    private readonly ITwilioClient _twilio;
    private readonly ILogger<SmsSender> _logger;

    // 构造函数注入照常工作 —— 键控注册不改变这个类怎么拿到自己的依赖
    public SmsSender(ITwilioClient twilio, ILogger<SmsSender> logger)
    {
        _twilio = twilio;
        _logger = logger;
    }

    public Task SendAsync(string to, string message, CancellationToken ct) =>
        _twilio.SendSmsAsync(to, message, ct);
}
```

## 已知 Key 解析

当 key 在调用点是固定的——这个服务总是发邮件——用 `[FromKeyedServices]` 直接注入：

```csharp
public class WelcomeEmailService
{
    private readonly INotificationSender _sender;

    public WelcomeEmailService(
        [FromKeyedServices("email")] INotificationSender sender)
    {
        _sender = sender;
    }

    public Task SendWelcome(string address, CancellationToken ct) =>
        _sender.SendAsync(address, "Welcome aboard!", ct);
}
```

同样的属性在 Minimal API handler 里最清爽：

```csharp
app.MapPost("/welcome", (
    [FromKeyedServices("email")] INotificationSender sender,
    WelcomeRequest request,
    CancellationToken ct) =>
{
    return sender.SendAsync(request.Email, "Welcome aboard!", ct);
});
```

工厂消失了。属性本身就是查找。

## 运行时 Key 解析

更有趣的场景是 key 直到请求进来才知道——用户在设置里选了 `"sms"`。你不能用属性做这个，需要动态解析。注入 `IServiceProvider` 并调用 `GetRequiredKeyedService`：

```csharp
public class NotificationDispatcher
{
    private readonly IServiceProvider _provider;

    public NotificationDispatcher(IServiceProvider provider) => _provider = provider;

    public Task Dispatch(string channel, string to, string message, CancellationToken ct)
    {
        // channel 在运行时来自用户偏好："email" | "sms" | "push"
        var sender = _provider.GetRequiredKeyedService<INotificationSender>(channel);
        return sender.SendAsync(to, message, ct);
    }
}
```

这是对工厂 switch 的诚实替代。容器现在是查询表，加第四个渠道只加一行注册——别的什么都不动。如果未知 key 应该返回 `null` 而不是抛异常，用 `GetKeyedService`（可空）代替 `GetRequiredKeyedService`。

值得说明的一点：注入 `IServiceProvider` 并从中解析是服务定位器模式，人们有理由对它保持警惕。这里的区别在于范围。你不是在代码库各处为任意类型伸手进容器——你在一个地方、为一个接口、做一次键控查找，key 确实直到运行时才知道。这是合理的用法。如果 key 在编译期就已知，用属性。

## 同时获取全部实现

有时候你要全部实现而不是某一个——把消息扇出到用户启用的每个渠道。注入键控可枚举：

```csharp
// 注入所有键控的 INotificationSender 注册
public class BroadcastService
{
    private readonly IEnumerable<INotificationSender> _all;

    public BroadcastService(
        [FromKeyedServices(KeyedService.AnyKey)] IEnumerable<INotificationSender> all)
    {
        _all = all;
    }

    public Task BroadcastAll(string to, string message, CancellationToken ct) =>
        Task.WhenAll(_all.Select(s => s.SendAsync(to, message, ct)));
}
```

`KeyedService.AnyKey` 相当于"匹配任意 key"，拿到的就是所有键控注册的实现集合。

## 什么时候真该用

不是每个"多实现"问题都需要键控 DI。值得用的场景：

- **一个接口背后多个提供者**：支付网关、通知渠道、存储后端、按功能区分的定价规则。经典的策略模式形态，但不用手写工厂。
- **每租户或每环境变体**：按租户级别键控的 `IReportGenerator`，或者按 `"local"` vs `"distributed"` 键控的 `ICacheStore`。
- **装饰器和管道**：在一个 key 下注册裸服务、在另一个 key 下注册装饰后的版本，然后选择注入哪个。

不值得的场景：如果你永远只有一个实现，键控服务是在无理由增加仪式。如果选择逻辑复杂——不止是按 key 选，比如有权重或回退——把逻辑放在一个真正的策略类里比让 key 过载更清楚。键控 DI 替代的是**查找**，不是你的**业务规则**。

## 几点注意

- **没有属性不能注入键控服务。** 普通 `INotificationSender` 参数不会解析键控注册——除非还有一个非键控注册否则会失败。键控和非键控在容器内部存在不同的命名空间。
- **容器不会枚举 key。** 没有内置的"给我所有 key"的 API。如果你需要校验传入的渠道字符串是否在已注册的集合中，自己维护有效 key 列表（enum 对这个是完美的），不要指望容器告诉你。
- **`GetRequiredKeyedService` 在未知 key 上抛异常。** 在解析前先校验用户提供的 key，或者用可空的 `GetKeyedService` 并显式处理 `null`，别让一个坏的 query string 值变成一个 500。
- **生命周期照常工作。** 键控 scoped 仍然是每个 scope 一个实例；键控 singleton 仍然是整个应用一个。key 不改变生命周期语义。

## 总结

Keyed Services 是一个小特性，悄悄去掉了大多数 .NET 代码库都带着的一种模式：那个你每加一个实现就得编辑一次的带 `switch` 的工厂。把每个实现注册在一个 key 下，key 固定时通过属性注入，运行时选择时从 provider 解析，让容器去做它本来就能做的查询表。

我的使用经验法则：如果你在写一个唯一职责是把值映射到注册类型的工厂，keyed services 替你做。如果工厂包含真正的决策逻辑，保留它——但它仍然可以通过 key 而不是具体类型来解析选项。

## 参考

- [Keyed Services in .NET — TheCodeMan](https://thecodeman.net/posts/keyed-services-in-dotnet-dependency-injection)
