---
pubDatetime: 2025-07-07
tags: [".NET", "Domain Events", "DDD", "事件驱动", "架构设计"]
slug: custom-domain-events-dispatcher-dotnet
source: https://www.milanjovanovic.tech/blog/building-a-custom-domain-events-dispatcher-in-dotnet
title: 在 .NET 中构建自定义领域事件分发器
description: 本文深入解析如何在 .NET 应用中实现一个无第三方依赖的高效领域事件分发器。涵盖基础架构设计、事件处理、DI注入、性能优化和可靠性权衡，适用于 DDD 与 Clean Architecture 场景。
---

# 在 .NET 中构建自定义领域事件分发器

## 为什么要用领域事件？

在大型企业级应用或微服务架构中，业务模块间的解耦是提升系统可维护性、灵活性的重要手段。领域事件（Domain Event）就是实现这一解耦的核心技术之一。通过发布/订阅模式，业务主流程只需“发布事件”，无需感知或耦合下游的功能扩展（如邮件通知、审计日志、统计等）。

举个例子，传统的注册业务通常像下面这样写：

```csharp
public class UserService
{
    public async Task RegisterUser(string email, string password)
    {
        var user = new User(email, password);
        await _userRepository.SaveAsync(user);
        // 直接调用邮件和统计服务，强耦合
        await _emailService.SendWelcomeEmail(user.Email);
        await _analyticsService.TrackUserRegistration(user.Id);
    }
}
```

如果用领域事件，代码更专注于核心流程，扩展点以事件形式开放：

```csharp
public class UserService
{
    public async Task RegisterUser(string email, string password)
    {
        var user = new User(email, password);
        await _userRepository.SaveAsync(user);
        // 发布事件，其它逻辑由订阅者响应
        await _domainEventsDispatcher.DispatchAsync(
            [new UserRegisteredDomainEvent(user.Id, user.Email)]);
    }
}
```

这样，发送欢迎邮件、埋点统计等行为都通过事件订阅方式自动实现，主流程清晰易维护。

## 事件系统基础抽象

领域事件分发系统通常有两个核心接口：

```csharp
// 领域事件标记接口
public interface IDomainEvent
{
    // 可以加入 OccurredAt、EventId 等通用属性
}

// 泛型事件处理器
public interface IDomainEventHandler<in T> where T : IDomainEvent
{
    Task Handle(T domainEvent, CancellationToken cancellationToken = default);
}
```

这种泛型约束不仅类型安全，还能让事件和处理器完全解耦，便于测试和扩展。

## 实现事件处理器：不同业务对同一事件响应

比如，用户注册事件触发欢迎邮件和埋点统计：

```csharp
// 欢迎邮件
internal sealed class SendWelcomeEmailHandler(IEmailService emailService)
    : IDomainEventHandler<UserRegisteredDomainEvent>
{
    public async Task Handle(
        UserRegisteredDomainEvent domainEvent,
        CancellationToken cancellationToken = default)
    {
        var welcomeEmail = new WelcomeEmail(domainEvent.Email, domainEvent.UserId);
        await emailService.SendAsync(welcomeEmail, cancellationToken);
    }
}

// 用户注册埋点
internal sealed class TrackUserRegistrationHandler(IAnalyticsService analyticsService)
    : IDomainEventHandler<UserRegisteredDomainEvent>
{
    public async Task Handle(
        UserRegisteredDomainEvent domainEvent,
        CancellationToken cancellationToken = default)
    {
        await analyticsService.TrackEvent(
            "user_registered",
            new { user_id = domainEvent.UserId, registration_date = domainEvent.RegisteredAt },
            cancellationToken);
    }
}
```

注册时，只需在依赖注入（DI）系统注册相关 Handler。推荐用 Scrutor 等库做自动扫描，也可手动添加：

```csharp
services.AddScoped<IDomainEventHandler<UserRegisteredDomainEvent>, SendWelcomeEmailHandler>();
services.AddScoped<IDomainEventHandler<UserRegisteredDomainEvent>, TrackUserRegistrationHandler>();
```

## 强类型领域事件分发器实现原理

核心分发器负责将事件分发给所有注册的处理器：

```csharp
public interface IDomainEventsDispatcher
{
    Task DispatchAsync(IEnumerable<IDomainEvent> domainEvents, CancellationToken cancellationToken = default);
}
```

实现思路为：

- 通过泛型反射或字典缓存，动态找到每种事件对应的所有处理器类型。
- 每次分发事件时，自动 DI 获取当前事件类型的所有处理器，逐个调用 `Handle`。
- 用 HandlerWrapper 技术消除热路径反射开销，提高分发性能（仅在首次遇到新事件类型时构造 Wrapper）。

```csharp
internal sealed class DomainEventsDispatcher(IServiceProvider serviceProvider)
    : IDomainEventsDispatcher
{
    // ...省略静态缓存及类型映射
    public async Task DispatchAsync(IEnumerable<IDomainEvent> domainEvents, CancellationToken cancellationToken = default)
    {
        foreach (IDomainEvent domainEvent in domainEvents)
        {
            using IServiceScope scope = serviceProvider.CreateScope();
            // 查找所有处理器，构建并调用 Wrapper
            // ... 省略具体实现
        }
    }
}
```

这种实现兼顾了**类型安全**与**运行时性能**，能在无需三方依赖下胜任高并发领域事件分发场景。

## 事件分发器实用用法举例

实际业务开发中，可在 Controller 或 Application Service 中直接使用分发器：

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

也可以参考更深度集成方式，将领域事件直接绑定到实体生命周期，实现事件自动聚合和分发。

## 可靠性、事务与Outbox模式

上文实现方案是**进程内分发**，即所有 Handler 都在同一请求、同一事务范围内同步执行。这种设计的优点在于：

- 失败立即反馈：任一处理器异常，调用方可立刻获知，便于回滚或补偿。
- 逻辑完全在应用层掌控，无“幂等/最终一致”副作用。

但它也有局限：

- 若部分 Handler 执行后服务崩溃，未完成的事件不会自动补偿/重试。
- 事件未持久化，易丢失。

对于可靠性要求极高的场景，建议结合**Outbox模式**：事件与业务数据同库写入，再由后台服务异步分发/重试。这样可以在不牺牲主流程性能的前提下，实现事件的强一致与可靠交付。

## 总结与工程化建议

领域事件是 DDD、Clean Architecture 等现代架构体系中强烈推荐的解耦模式。自定义实现分发器不仅能完全掌控行为和性能，还能根据实际需求灵活扩展和调优。

对于大多数企业应用，进程内领域事件足够高效。如果业务复杂到需要跨进程/跨服务事件流转，再引入 Kafka、RabbitMQ、CAP 等消息中间件即可。

最重要的是：**理解自己的系统需求和演化方向，技术选型与落地方案应量体裁衣。**
