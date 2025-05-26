---
pubDatetime: 2025-05-26
tags: [C#, .NET, DDD, Clean Architecture, 微服务, 架构, 领域事件, 实践]
slug: domain-events-dispatcher-dotnet-guide
source: https://www.milanjovanovic.tech/blog/building-a-custom-domain-events-dispatcher-in-dotnet
title: .NET领域事件解耦实战：手把手教你构建自定义事件分发器
description: 深度解析如何在.NET项目中实现轻量级领域事件分发器，助力DDD、微服务与Clean Architecture实践，让系统更灵活、更易扩展。
---

# .NET领域事件解耦实战：手把手教你构建自定义事件分发器

对于追求高内聚、低耦合架构的C#/.NET开发者而言，领域事件无疑是解耦业务逻辑、提升系统可维护性的关键利器。本文将结合实际案例，深入剖析如何在.NET中实现一个轻量级的领域事件分发器，无需引入第三方库，帮助你迈出DDD与Clean Architecture落地的关键一步。

> 目标读者：有一定C#/.NET开发经验的软件工程师、架构师，以及关注DDD、微服务或Clean Architecture实践的中高级开发者。

---

## 引言：为什么要用领域事件？

在企业级应用开发中，业务需求的演进往往会让“核心服务”变得越来越臃肿。以用户注册为例，刚开始也许只需保存用户信息，但不久后就会接连添加“发送欢迎邮件”“埋点统计”“发放新人礼包”等功能。每加一个新功能，核心服务的代码就多耦合一个依赖，最终变得难以维护。

✨ **领域事件的好处：**

- 解耦业务主流程与各类扩展逻辑
- 易于测试与演化
- 支持多种架构风格（如DDD、微服务等）

---

## 正文

### 1️⃣ 传统做法的隐患

来看一段典型的“紧耦合”代码：

```csharp
public class UserService
{
    public async Task RegisterUser(string email, string password)
    {
        var user = new User(email, password);
        await _userRepository.SaveAsync(user);

        // 直接调用邮件服务
        await _emailService.SendWelcomeEmail(user.Email);

        // 直接调用分析服务
        await _analyticsService.TrackUserRegistration(user.Id);

        // 新需求不断加入，方法越来越臃肿...
    }
}
```

这种写法让UserService既要关注业务核心，又要知晓所有扩展需求，一旦业务扩展，维护成本剧增。

### 2️⃣ 用领域事件解耦业务逻辑

借助领域事件，我们可以让UserService只负责用户注册，其他逻辑通过“发布事件”来通知感兴趣的模块：

```csharp
public class UserService
{
    public async Task RegisterUser(string email, string password)
    {
        var user = new User(email, password);
        await _userRepository.SaveAsync(user);

        // 发布领域事件，其他模块订阅处理
        await _domainEventsDispatcher.DispatchAsync(
            [new UserRegisteredDomainEvent(user.Id, user.Email)]
        );
    }
}
```

**优势一目了然：**

- 注册流程清晰专一
- 扩展功能可插拔，互不干扰

### 3️⃣ 设计领域事件基础抽象

实现解耦的关键，是合理设计事件与处理器接口：

```csharp
// 领域事件标记接口
public interface IDomainEvent { }

// 泛型领域事件处理器接口
public interface IDomainEventHandler<in T> where T : IDomainEvent
{
    Task Handle(T domainEvent, CancellationToken cancellationToken = default);
}
```

### 4️⃣ 实现具体的事件处理器

比如，我们需要两个不同的处理器响应“用户注册”这一事件：

```csharp
// 发送欢迎邮件
internal sealed class SendWelcomeEmailHandler(IEmailService emailService)
    : IDomainEventHandler<UserRegisteredDomainEvent>
{
    public async Task Handle(UserRegisteredDomainEvent domainEvent, CancellationToken cancellationToken = default)
    {
        var welcomeEmail = new WelcomeEmail(domainEvent.Email, domainEvent.UserId);
        await emailService.SendAsync(welcomeEmail, cancellationToken);
    }
}

// 埋点分析处理器
internal sealed class TrackUserRegistrationHandler(IAnalyticsService analyticsService)
    : IDomainEventHandler<UserRegisteredDomainEvent>
{
    public async Task Handle(UserRegisteredDomainEvent domainEvent, CancellationToken cancellationToken = default)
    {
        await analyticsService.TrackEvent(
            "user_registered",
            new { user_id = domainEvent.UserId, registration_date = domainEvent.RegisteredAt },
            cancellationToken);
    }
}
```

### 5️⃣ 自动注册事件处理器

手动注册每个处理器太繁琐？可以用[Scrutor自动扫描注册](https://www.milanjovanovic.tech/blog/improving-aspnetcore-dependency-injection-with-scrutor)：

```csharp
services.Scan(scan => scan.FromAssembliesOf(typeof(DependencyInjection))
    .AddClasses(classes => classes.AssignableTo(typeof(IDomainEventHandler<>)), publicOnly: false)
    .AsImplementedInterfaces()
    .WithScopedLifetime());
```

### 6️⃣ 构建自定义事件分发器

**核心调度器代码如下：**

```csharp
public interface IDomainEventsDispatcher
{
    Task DispatchAsync(IEnumerable<IDomainEvent> domainEvents, CancellationToken cancellationToken = default);
}

internal sealed class DomainEventsDispatcher(IServiceProvider serviceProvider)
    : IDomainEventsDispatcher
{
    // ... 省略字典缓存和Wrapper实现 ...

    public async Task DispatchAsync(IEnumerable<IDomainEvent> domainEvents, CancellationToken cancellationToken = default)
    {
        foreach (IDomainEvent domainEvent in domainEvents)
        {
            using IServiceScope scope = serviceProvider.CreateScope();
            Type handlerType = typeof(IDomainEventHandler<>).MakeGenericType(domainEvent.GetType());
            IEnumerable<object?> handlers = scope.ServiceProvider.GetServices(handlerType);

            foreach (object? handler in handlers)
            {
                // 利用泛型wrapper避免反射损耗，强类型调用
                var handlerWrapper = HandlerWrapper.Create(handler, domainEvent.GetType());
                await handlerWrapper.Handle(domainEvent, cancellationToken);
            }
        }
    }
}
```

### 7️⃣ 实际调用场景

在Controller中使用自定义分发器，只需：

```csharp
public class UserController(
    IUserService userService,
    IDomainEventsDispatcher domainEventsDispatcher) : ControllerBase
{
    [HttpPost("register")]
    public async Task<IActionResult> Register([FromBody] RegisterUserRequest request)
    {
        var user = await userService.CreateUserAsync(request.Email, request.Password);
        var userRegisteredEvent = new UserRegisteredDomainEvent(user.Id, user.Email);

        await domainEventsDispatcher.DispatchAsync([userRegisteredEvent]);

        return Ok(new { UserId = user.Id, Message = "User registered successfully" });
    }
}
```

> ✅ 保证注册流程专注于主线，所有副作用都交由事件分发器处理。

---

## 结论与最佳实践建议

### ⚠️ 注意边界与权衡

- 本方案为**进程内同步执行**，适合单体或边界明确的微服务。
- 若某些副作用不能丢失（如发送订单短信），建议采用[Outbox Pattern](https://www.milanjovanovic.tech/blog/implementing-the-outbox-pattern)做持久化保障。
- 对于跨服务通信或最终一致性需求，建议引入消息总线等机制。

**领域事件不是银弹，但它是清晰分离关注点和提升系统可演化性的有力工具。**

---

## 总结&互动

本文带你从零实现了一个.NET自定义领域事件分发器，并结合实际场景解析了其设计理念、使用方式及适用边界。希望你能把这个模式灵活地应用到自己的DDD或Clean Architecture项目中。

> 🤔 你在实际开发中遇到过哪些“业务膨胀”或“难以扩展”的痛点？  
> 💬 欢迎在评论区留言分享你的经验，或提出关于领域事件实现与架构演进的问题！  
> 🚀 如果觉得本文有启发，不妨分享给你的同事或团队，一起打造更优雅的.NET系统！

---

**更多精彩内容：**

- [Pragmatic REST APIs NEW](https://www.milanjovanovic.tech/pragmatic-rest-apis?utm_source=article_page)
- [Pragmatic Clean Architecture](https://www.milanjovanovic.tech/pragmatic-clean-architecture?utm_source=article_page)
- [Modular Monolith Architecture](https://www.milanjovanovic.tech/modular-monolith-architecture?utm_source=article_page)
