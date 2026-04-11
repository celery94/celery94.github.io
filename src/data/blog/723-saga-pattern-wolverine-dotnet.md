---
pubDatetime: 2026-04-11T09:40:00+08:00
title: "用 Wolverine 实现 Saga 模式"
description: "长流程业务（如用户注册验证流程）天然需要 Saga 模式来协调多步骤操作。本文介绍如何用 Wolverine 构建一个带有超时补偿的 Saga，包括配置 RabbitMQ、PostgreSQL、定义消息类型、编写完整 Saga 类，以及处理超时和遗失消息的 NotFound 模式。"
tags: [".NET", "Wolverine", "Saga", "分布式系统", "消息驱动"]
slug: "saga-pattern-wolverine-dotnet"
ogImage: "../../assets/723/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/implementing-the-saga-pattern-with-wolverine"
---

长流程业务操作不适合放在单次请求里处理。

用户注册是个典型例子：注册账号、发验证邮件、等用户确认、再发欢迎邮件，每一步都依赖上一步的结果。如果用户一直没有点击确认链接，系统应该怎么办？

Saga 模式把这类流程拆成一组消息和处理器，每步完成后触发下一步，任何步骤超时或失败都有对应的补偿逻辑，系统不会停在一个中间状态里。

以前写 Saga 通常要对付 MassTransit 或 Rebus 的状态机 DSL，需要配置不少样板代码。[MassTransit 转向商业授权](https://www.milanjovanovic.tech/blog/mediatr-and-masstransit-going-commercial-what-this-means-for-you)之后，越来越多团队开始看 Wolverine。Wolverine 的思路是：写一个继承自 `Saga` 的类，用 `Handle` 方法处理各类消息，用返回值触发下一步操作，路由、持久化、关联全部由框架接管。

## 配置 Wolverine

需要三个 NuGet 包：

```xml
<PackageReference Include="WolverineFx" Version="5.16.2" />
<PackageReference Include="WolverineFx.Postgresql" Version="5.16.2" />
<PackageReference Include="WolverineFx.RabbitMQ" Version="5.16.2" />
```

消息传递用 RabbitMQ，Saga 状态持久化用 PostgreSQL。在 `Program.cs` 里配置：

```csharp
var connectionString = builder.Configuration.GetConnectionString("user-mgmt");

builder.Host.UseWolverine(options =>
{
    options.UseRabbitMqUsingNamedConnection("rmq")
        .AutoProvision()
        .UseConventionalRouting();

    options.Policies.DisableConventionalLocalRouting();

    options.PersistMessagesWithPostgresql(connectionString!);
});
```

几个配置项说明：

- `AutoProvision`：自动创建 RabbitMQ 中的 exchange 和 queue，不需要手动配置
- `UseConventionalRouting`：根据消息类型名称自动路由到对应 queue
- `DisableConventionalLocalRouting`：所有消息走 RabbitMQ，不走进程内处理
- `PersistMessagesWithPostgresql`：Saga 状态和消息都持久化到 PostgreSQL，进程宕机也不会丢失

Wolverine 提供三种 Saga 持久化方式：

- **Lightweight storage**（本文用的）：将 Saga 状态序列化为 JSON，每个 Saga 类型一张表，零 ORM 配置
- **Marten**：把 Saga 存为 Marten 文档，支持乐观并发和强类型 ID
- **EF Core**：映射到关系表，可以在同一个事务里提交 Saga 状态和业务数据

如果只需要管理 Saga 状态，Lightweight storage 是最简单的选择。

## 定义消息类型

先把这个 Saga 会用到的所有消息都定义出来：

```csharp
public record SendVerificationEmail(Guid UserId, string Email);
public record VerificationEmailSent(Guid Id);

public record VerifyUserEmail(Guid Id);

public record SendWelcomeEmail(Guid UserId, string Email, string FirstName);
public record WelcomeEmailSent(Guid Id);

public record OnboardingTimedOut(Guid Id) : TimeoutMessage(5.Minutes());
```

`OnboardingTimedOut` 继承了 Wolverine 的 `TimeoutMessage`，在 Saga 启动时会自动安排一个延迟投递，5 分钟后触发。这就是 Wolverine 内置的超时机制，不需要外部调度器。

## 构建 Saga 类

下面是完整的 `UserOnboardingSaga`：

```csharp
public class UserOnboardingSaga : Saga
{
    public Guid Id { get; set; }
    public string Email { get; set; } = string.Empty;
    public string FirstName { get; set; } = string.Empty;
    public string LastName { get; set; } = string.Empty;
    public bool IsVerificationEmailSent { get; set; }
    public bool IsEmailVerified { get; set; }
    public bool IsWelcomeEmailSent { get; set; }
    public DateTime StartedAt { get; set; }

    // 第 1 步：UserRegistered 触发 Saga 启动
    public static (
        UserOnboardingSaga,
        SendVerificationEmail,
        OnboardingTimedOut) Start(
            UserRegistered @event,
            ILogger<UserOnboardingSaga> logger)
    {
        logger.LogInformation(
            "Starting onboarding for user {UserId}", @event.Id);

        var saga = new UserOnboardingSaga
        {
            Id = @event.Id,
            Email = @event.Email,
            FirstName = @event.FirstName,
            LastName = @event.LastName,
        };

        return (
            saga,
            new SendVerificationEmail(saga.Id, saga.Email),
            new OnboardingTimedOut(saga.Id));
    }

    // 第 2 步：验证邮件已发出
    public void Handle(
        VerificationEmailSent @event,
        ILogger<UserOnboardingSaga> logger)
    {
        logger.LogInformation(
            "Verification email sent for user {UserId}", Id);

        IsVerificationEmailSent = true;
    }

    // 第 3 步：用户完成邮件验证
    public SendWelcomeEmail Handle(
        VerifyUserEmail command,
        ILogger<UserOnboardingSaga> logger)
    {
        logger.LogInformation("Email verified for user {UserId}", Id);

        IsEmailVerified = true;

        return new SendWelcomeEmail(Id, Email, FirstName);
    }

    // 第 4 步：欢迎邮件已发出，流程完成
    public void Handle(
        WelcomeEmailSent @event,
        ILogger<UserOnboardingSaga> logger)
    {
        logger.LogInformation("Onboarding complete for user {UserId}", Id);

        IsWelcomeEmailSent = true;

        MarkCompleted();
    }

    // 补偿：超时处理
    public void Handle(
        OnboardingTimedOut timeout,
        ILogger<UserOnboardingSaga> logger)
    {
        if (IsEmailVerified)
        {
            logger.LogInformation(
                "Timeout ignored - email already verified for user {UserId}",
                Id);
            return;
        }

        logger.LogWarning(
            "Onboarding timed out for user {UserId} - email not verified",
            Id);

        MarkCompleted();
    }

    // NotFound：消息抵达时 Saga 已不存在
    public static void NotFound(
        VerifyUserEmail command,
        ILogger<UserOnboardingSaga> logger)
    {
        logger.LogWarning(
            "Verify email received but saga {Id} no longer exists",
            command.Id);
    }

    public static void NotFound(
        OnboardingTimedOut timeout,
        ILogger<UserOnboardingSaga> logger)
    {
        logger.LogInformation(
            "Timeout received for already-completed saga {Id}",
            timeout.Id);
    }
}
```

## 几个关键设计细节

**启动 Saga**：`Start` 是一个静态工厂方法，返回一个元组。Wolverine 从元组里识别出 Saga 实例、需要发送的命令，以及延迟消息，然后一起持久化和投递。你不需要显式管理状态保存。

**消息关联**：Wolverine 需要把收到的消息路由到正确的 Saga 实例。它的查找顺序是：先找 `[SagaIdentity]` 特性标注的属性，再找 `{SagaTypeName}Id` 命名的属性，最后找 `Id`。本例中的消息都带 `Guid Id` 字段，正好匹配。

**级联命令**：`Handle` 方法可以返回一个消息，Wolverine 会自动将它发出去。第 3 步 `Handle(VerifyUserEmail)` 返回 `SendWelcomeEmail`，就是这种用法。返回 `void` 表示只更新状态，不触发新步骤。

**注意**：不要在 Saga 的 `Handle` 方法里调用 `IMessageBus.InvokeAsync()` 来处理同一个 Saga 的后续命令，那样会读到过时或空的状态。后续操作必须通过返回值（级联消息）来触发。

**完成 Saga**：调用 `MarkCompleted()` 后，Wolverine 会删除 PostgreSQL 中对应的 Saga 状态记录。

**并发控制**：Wolverine 默认对 Saga 状态使用乐观并发。如果同一个 Saga 的两条消息同时到达，一条成功处理，另一条自动重试，不会产生竞态。

## 超时与补偿

`OnboardingTimedOut` 在 Saga 启动时就被安排，5 分钟后投递。

处理逻辑很简单：如果用户已经验证，忽略这条超时消息；如果没有，记录日志并调用 `MarkCompleted()` 关闭 Saga。这比用外部定时任务轮询状态更干净，Saga 自己掌握自己的生命周期。

## NotFound 处理器

静态的 `NotFound` 方法用于处理"消息到了但 Saga 已经不存在"的情况。

最容易触发这个场景的是超时消息：在正常路径里，Saga 在超时触发前就已经完成并被删除，此时 `OnboardingTimedOut` 抵达时找不到对应的 Saga，就会走 `NotFound`。任何可能在 Saga 删除后才到的消息类型，都要有对应的 `NotFound` 方法，否则会报错。

## 小结

Wolverine 的 Saga 实现非常轻量：

- `Start` 方法创建 Saga 并返回初始 messages
- `Handle` 方法处理消息，通过返回值触发下一步
- `TimeoutMessage` 内置延迟投递，不需要外部调度器
- `MarkCompleted()` 删除状态，结束 Saga 生命周期
- `NotFound` 处理 Saga 已删除后到来的消息

与 MassTransit 的状态机 DSL 相比，Wolverine 的做法更接近普通 C# 代码。没有显式的状态枚举，没有转换配置，消息关联和路由也由框架按约定自动处理。

如果你有需要协调多步骤、带超时和补偿的业务流程，Wolverine 的 Saga 是一个值得认真看的选项。

## 参考

- [Implementing the Saga Pattern With Wolverine](https://www.milanjovanovic.tech/blog/implementing-the-saga-pattern-with-wolverine)
- [Wolverine Saga 文档](https://wolverinefx.net/guide/durability/sagas)
- [Wolverine TimeoutMessage](https://wolverinefx.net/guide/durability/sagas#timeout-messages)
- [Wolverine 持久化存储](https://wolverinefx.net/guide/durability/postgresql)
