---
pubDatetime: 2024-04-18
tags: ["Productivity", "Tools"]
source: https://www.milanjovanovic.tech/blog/refactoring-from-an-anemic-domain-model-to-a-rich-domain-model?utm_source=Twitter&utm_medium=social&utm_campaign=15.04.2024
author: Milan Jovanović
title: 从贫血模型到富模型的重构
description: 贫血域模型是一种反模式吗？它是一个没有任何行为，只有数据属性的域模型。
---

> ## 摘录
>
> 贫血域模型是一种反模式吗？它是一个没有任何行为，只有数据属性的域模型。
>
> 原文 [Refactoring From an Anemic Domain Model To a Rich Domain Model](https://www.milanjovanovic.tech/blog/refactoring-from-an-anemic-domain-model-to-a-rich-domain-model?utm_source=Twitter&utm_medium=social&utm_campaign=15.04.2024)

---

贫血域模型（**anemic domain model**）是一种**反模式**吗？

它是一个没有任何行为，只有数据属性的域模型。

贫血域模型在简单的应用中表现良好，但如果你拥有丰富的业务逻辑，它就很难维护和演进。

你的业务逻辑和规则的重要部分最终会分散在整个应用中。这降低了内聚性和可重用性，并使添加新特性变得更加困难。

**富域模型**试图通过尽可能地封装业务逻辑来解决这个问题。

但你应该如何设计一个**富域模型**？

这是一个将业务逻辑移入域并不断完善域模型的永无止境的过程。

让我们看看如何从**贫血域模型**重构到**富域模型**。

## 使用贫血域模型工作

为了理解使用**贫血域模型**的工作情况，我将使用处理 `SendInvitationCommand`的示例。

我省略了类及其依赖关系，这样我们可以专注于`Handle`方法。它从数据库加载一些实体，执行验证，执行业务逻辑，最后持久化数据库的更改并发送电子邮件。

它已经实现了一些好的实践，比如使用仓库（repositories）和返回结果对象。

然而，它是使用**贫血域模型**。

以下几点表明了这一点：

- 无参构造函数
- 公开的属性设置器
- 暴露的集合

换句话说 - 表示域实体的类只包含数据属性而没有行为。

**贫血域模型**的**问题**有：

- 操作的可发现性
- 可能的代码复制
- 缺乏封装

我们将应用一些技巧将逻辑下推到域中，并尝试使模型更加领域驱动。我希望你能看到这将带来的价值和好处。

```csharp
public async Task<Result> Handle(SendInvitationCommand command)
{
    var member = await _memberRepository.GetByIdAsync(command.MemberId);

    var gathering = await _gatheringRepository.GetByIdAsync(command.GatheringId);

    if (member is null || gathering is null)
    {
        return Result.Failure(Error.NullValue);
    }

    if (gathering.Creator.Id == member.Id)
    {
        throw new Exception("Can't send invitation to the creator.");
    }

    if (gathering.ScheduledAtUtc < DateTime.UtcNow)
    {
        throw new Exception("Can't send invitation for the past.");
    }

    var invitation = new Invitation
    {
        Id = Guid.NewGuid(),
        Member = member,
        Gathering = gathering,
        Status = InvitationStatus.Pending,
        CreatedOnUtc = DateTime.UtcNow
    };

    gathering.Invitations.Add(invitation);

    _invitationRepository.Add(invitation);

    await _unitOfWork.SaveChangesAsync();

    await _emailService.SendInvitationSentEmailAsync(member, gathering);

    return Result.Success();
}
```

## 将业务逻辑移入域

目标是将尽可能多的业务逻辑移入域。

让我们从`Invitation`实体开始，并为其定义一个构造函数。我可以简化设计，将`Status`和`CreatedOnUtc`属性在构造函数内设置。我还打算将其标记为`internal`，以便只能在域内创建`Invitation`实例。

```csharp
public sealed class Invitation
{
    internal Invitation(Guid id, Gathering gathering, Member member)
    {
        Id = id;
        Member = member;
        Gathering = gathering;
        Status = InvitationStatus.Pending;
        CreatedOnUtc = DateTime.Now;
    }

    // 为简洁起见，省略了数据属性。
}
```

我将`Invitation`构造函数标记为`internal`的原因是，这样我就可以在`Gathering`实体上引入一个新方法。我们称之为`SendInvitation`，它将负责实例化一个新的`Invitation`实例并将其添加到内部集合中。

当前，`Gathering.Invitations`集合是`public`的，这意味着任何人都可以获得引用并修改集合。

我们不想允许这样做，所以我们可以做的是将这个集合封装在一个`private`字段后面。这将`_invitations`集合的管理责任移交给了`Gathering`类。

现在这是`Gathering`类的样子：

```csharp
public sealed class Gathering
{
    private readonly List<Invitation> _invitations;

    // 为简洁起见，省略了其他成员。

    public void SendInvitation(Member member)
    {
        var invitation = new Invitation(Guid.NewGuid(), gathering, member);

        _invitations.Add(invitation);
    }
}
```

## 将验证规则移入域

我们接下来可以做的是将验证规则移入`SendInvitation`方法，进一步丰富域模型。

不幸的是，当验证失败时抛出“预期”异常仍然是一个不好的实践。如果你想使用异常来强制执行验证规则，至少你应该做得正确，使用特定的异常而不是泛型异常。

但使用**结果对象**来表达验证错误会更好。

```csharp
public sealed class Gathering
{
    // 为简洁起见，省略了其他成员。

    public void SendInvitation(Member member)
    {
        if (gathering.Creator.Id == member.Id)
        {
            throw new Exception("Can't send invitation to the creator.");
        }

        if (gathering.ScheduledAtUtc < DateTime.UtcNow)
        {
            throw new Exception("Can't send invitation for the past.");
        }

        var invitation = new Invitation(Guid.NewGuid(), gathering, member);

        _invitations.Add(invitation);
    }
}
```

这是使用**结果对象**的样子：

```csharp
public sealed class Gathering
{
    // 为简洁起见，省略了其他成员。

    public Result SendInvitation(Member member)
    {
        if (gathering.Creator.Id == member.Id)
        {
            return Result.Failure(DomainErrors.Gathering.InvitingCreator);
        }

        if (gathering.ScheduledAtUtc < DateTime.UtcNow)
        {
            return Result.Failure(DomainErrors.Gathering.AlreadyPassed);
        }

        var invitation = new Invitation(Guid.NewGuid(), gathering, member);

        _invitations.Add(invitation);

        return Result.Success();
    }
}
```

这种方法的好处是我们可以引入可能域错误的常量。域错误目录将作为您域的**文档**，并使其更富有表现力。

最后，这是到目前为止所有更改后的`Handle`方法的样子：

```csharp
public async Task<Result> Handle(SendInvitationCommand command)
{
    var member = await _memberRepository.GetByIdAsync(command.MemberId);

    var gathering = await _gatheringRepository.GetByIdAsync(command.GatheringId);

    if (member is null || gathering is null)
    {
        return Result.Failure(Error.NullValue);
    }

    var result = gathering.SendInvitation(member);

    if (result.IsFailure)
    {
        return Result.Failure(result.Errors);
    }

    await _unitOfWork.SaveChangesAsync();

    await _emailService.SendInvitationSentEmailAsync(member, gathering);

    return Result.Success();
}
```

如果你仔细观察`Handle`方法，你会注意到它正在做两件事：

- 持久化数据库的更改
- 发送电子邮件

这意味着它**不是原子的**。

有可能数据库事务完成，但发送电子邮件失败。此外，发送电子邮件将减慢方法的速度，这可能会影响性能。

我们如何使这个方法原子化？

通过在后台发送电子邮件。它对我们的业务逻辑不重要，所以这样做是安全的。

## 用域事件表示副作用

你可以使用**域事件**来表达域中发生了可能对系统中其他组件感兴趣的事情。

我经常使用**域事件**来在后台触发动作，比如发送通知或电子邮件。

让我们引入一个`InvitationSentDomainEvent`：

```csharp
public record InvitationSentDomainEvent(Invitation Invitation) : IDomainEvent;
```

我们将在`SendInvitation`方法内部引发这个**域事件**：

```csharp
public sealed class Gathering
{
    private readonly List<Invitation> _invitations;

    // 为简洁起见，省略了其他成员。

    public Result SendInvitation(Member member)
    {
        if (gathering.Creator.Id == member.Id)
        {
            return Result.Failure(DomainErrors.Gathering.InvitingCreator);
        }

        if (gathering.ScheduledAtUtc < DateTime.UtcNow)
        {
            return Result.Failure(DomainErrors.Gathering.AlreadyPassed);
        }

        var invitation = new Invitation(Guid.NewGuid(), gathering, member);

        _invitations.Add(invitation);

        Raise(new InvitationSentDomainEvent(invitation));

        return Result.Success();
    }
}
```

目标是从`Handle`方法中移除负责发送电子邮件的代码：

```csharp
public async Task<Result> Handle(SendInvitationCommand command)
{
    var member = await _memberRepository.GetByIdAsync(command.MemberId);

    var gathering = await _gatheringRepository.GetByIdAsync(command.GatheringId);

    if (member is null || gathering is null)
    {
        return Result.Failure(Error.NullValue);
    }

    var result = gathering.SendInvitation(member);

    if (result.IsFailure)
    {
        return Result.Failure(result.Errors);
    }

    await _unitOfWork.SaveChangesAsync();

    return Result.Success();
}
```

我们只关心执行业务逻辑和持久化数据库的任何更改。这些更改的一部分也将是**域事件**，系统将在后台发布它。

当然，我们需要一个相应的**域事件**处理程序：

```csharp
public sealed class InvitationSentDomainEventHandler
    : IDomainEventHandler<InvitationSentDomainEvent>
{
    private readonly IEmailService _emailService;

    public InvitationSentDomainEventHandler(IEmailService emailService)
    {
        _emailService = emailService;
    }

    public async Task Handle(InvitationSentDomainEvent domainEvent)
    {
        await _emailService.SendInvitationSentEmailAsync(
            domainEvent.Invitation.Member,
            domainEvent.Invitation.Gathering);
    }
}
```

我们实现了两件事情：

- 处理`SendInvitationCommand`现在是原子的
- 电子邮件在后台发送，如果出错可以安全地重试

## 总结

设计一个**富域模型**是一个逐步的过程，你可以随着时间的推移慢慢演进域模型。

第一步可以是使你的域模型更具防御性：

- 使用`internal`关键字隐藏构造函数
- 封装集合访问

这样做的好处是你的域模型将拥有细粒度的公共API（方法），这些方法充当执行业务逻辑的入口点。

当行为在一个类中封装而不必模拟外部依赖时，测试是容易的。

你可以引发**域事件**以通知系统发生了某些重要的事情，任何感兴趣的组件都可以订阅该域事件。域事件允许你开发一个**解耦**的系统，你可以专注于核心域逻辑，并不必担心副作用。

然而，这并不意味着每个系统都需要一个**富域模型**。

你应当务实地决定何时复杂性是值得的。
