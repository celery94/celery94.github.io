---
pubDatetime: 2026-06-08T08:18:52+08:00
title: "C# Mediator 模式：把对象通信收回到一个中介"
description: "Mediator 模式适合处理多个对象之间越来越乱的通信关系。它把对象间的直接引用改成通过中介协调，降低耦合，但也可能把中介写成 God Object。这篇用 C# 示例、事件驱动变体和 MediatR 讲清楚取舍。"
tags: ["C#", "Design Patterns", "Mediator", "MediatR"]
slug: "csharp-mediator-design-pattern-guide"
ogImage: "../../assets/856/01-cover.png"
source: "https://www.devleader.ca/2026/06/06/mediator-design-pattern-in-c-complete-guide-with-examples"
---

当多个对象需要互相通信，而每个对象都开始持有其他对象的引用时，代码很快会变成一张难追踪的网。Mediator design pattern 的做法是：让对象不要直接找彼此，而是统一通过一个中介对象协调通信。

Dev Leader 这篇文章用 C# 示例讲了 Mediator 的经典结构、聊天系统、事件驱动变体，以及 .NET 生态里常见的 MediatR。它的核心价值不是“多加一层抽象”，而是在对象之间的通信复杂度已经失控时，把交互逻辑集中到一个可读、可测、可替换的位置。

## 它解决什么

Mediator 是 GoF 行为型设计模式之一。它定义一个对象，用来封装一组对象之间如何交互。参与者不再显式引用彼此，而是只知道 mediator。

原文用了空中交通管制塔的比喻：飞机之间不需要互相广播位置和意图，每架飞机只和塔台通信，塔台协调起飞、降落和避让。代码里也是同样的意思。

如果 N 个对象都需要互相通信，直接引用最多会产生 `N×(N-1)` 条关系。对象越多，依赖网越乱。Mediator 把这张网改成 N 个对象都引用同一个 mediator，从而降低耦合。

## 四个参与者

经典 Mediator 模式通常有四类角色：

- `Mediator`：定义通信契约，比如发送消息、发布通知。
- `ConcreteMediator`：实现协调逻辑，知道有哪些参与者，决定消息如何路由。
- `Colleague`：参与通信的对象基类或接口，只持有 mediator 引用。
- `ConcreteColleague`：具体参与者，通过 mediator 发送消息，也从 mediator 接收消息。

这个结构的关键是：参与者不认识其他参与者。你可以修改路由逻辑、增加新参与者、换一套 mediator 实现，而不必让每个对象都重新认识一遍彼此。

## 什么时候用

Mediator 适合这些情况：

一组对象之间有明确但复杂的通信规则。读代码时，你不想在十几个类之间来回跳，才能知道一次交互到底发生了什么。

你希望替换协调逻辑。比如同一组参与者在不同场景下有不同工作流规则、聊天策略、通知策略。

某个对象因为引用太多其他对象而难以复用。把直接依赖收回 mediator 后，这个对象只依赖通信契约，迁移到其他上下文会容易很多。

不适合的情况也很明确：两三个对象之间的交互很简单时，不要为了模式而加 mediator。它引入的是间接通信，只有当直接引用的复杂度更高时才值得。

## 经典 C# 结构

一个最小化的 mediator 接口可以只有一个发送方法：

```csharp
public interface IMediator
{
    void SendMessage(string message, Colleague sender);
}

public abstract class Colleague
{
    protected IMediator Mediator { get; }

    protected Colleague(IMediator mediator)
    {
        Mediator = mediator;
    }

    public abstract void ReceiveMessage(string message);
}
```

具体参与者只知道 mediator：

```csharp
public sealed class Developer : Colleague
{
    public string Name { get; }

    public Developer(IMediator mediator, string name)
        : base(mediator)
    {
        Name = name;
    }

    public void Send(string message)
    {
        Console.WriteLine($"[{Name}] sends: {message}");
        Mediator.SendMessage(message, this);
    }

    public override void ReceiveMessage(string message)
    {
        Console.WriteLine($"[{Name}] received: {message}");
    }
}
```

Concrete mediator 维护参与者列表，并决定如何投递消息：

```csharp
public sealed class TeamMediator : IMediator
{
    private readonly List<Colleague> _colleagues = new();

    public void Register(Colleague colleague)
    {
        if (!_colleagues.Contains(colleague))
        {
            _colleagues.Add(colleague);
        }
    }

    public void SendMessage(string message, Colleague sender)
    {
        foreach (var colleague in _colleagues)
        {
            if (colleague != sender)
            {
                colleague.ReceiveMessage(message);
            }
        }
    }
}
```

这个例子是广播式 mediator：发送者发出消息，mediator 转发给除发送者之外的所有参与者。它不复杂，但能说明模式的核心：`Developer` 不需要知道 `ProjectManager` 或另一个 `Developer` 的存在。

## 聊天室例子

聊天室天然适合 Mediator。用户之间看起来是在聊天，实际上每个用户只和 chat room 通信。

如果没有 mediator，每个用户都要知道其他用户，加入新用户还要更新多处引用。用了 `ChatRoomMediator` 后，用户只需要注册进聊天室；发消息时，聊天室负责决定谁能收到、消息如何展示、是否需要过滤或记录。

这类例子也说明了一个边界：mediator 负责协调交互，不应该把聊天业务全部吃进去。比如“用户是否被禁言”“消息是否违反规则”“是否触发审核流程”这些逻辑，最好拆成策略、服务或 handler，而不是全部塞进一个越来越大的 chat room 类。

## 事件驱动变体

原文还讲了一个事件驱动版本：mediator 按频道维护订阅者，发布者向频道发布消息，订阅者只接收自己订阅的频道。

这个形式和 Observer pattern 有点像，但差别在于：Observer 里 subject 通常持有 observers；Mediator 里 publisher 和 subscriber 互相不知道，二者都只依赖 mediator。

这适合“多个来源发布，多类处理者订阅”的场景，比如：

- bug 报告进入 `bugs` 频道。
- feature request 进入 `features` 频道。
- 日志处理器订阅所有频道。
- 专门处理器只订阅自己关心的频道。

此时 mediator 不只是转发消息，还承担了频道路由规则。

## MediatR 怎么映射

在 .NET 里，MediatR 是最常见的 in-process mediator library。它支持两类通信：

- request/response：一个 request 对应一个 handler。
- notification：一个 notification 可以有多个 handler。

一个查询可以写成 request：

```csharp
public sealed record GetUserQuery(int UserId)
    : IRequest<UserDto>;

public sealed record UserDto(
    int Id,
    string Name,
    string Email);

public sealed class GetUserQueryHandler
    : IRequestHandler<GetUserQuery, UserDto>
{
    public Task<UserDto> Handle(
        GetUserQuery request,
        CancellationToken cancellationToken)
    {
        var user = new UserDto(
            request.UserId,
            "Alice",
            "alice@example.com");

        return Task.FromResult(user);
    }
}
```

调用方只发送 request，不直接引用 handler：

```csharp
var user = await mediator.Send(new GetUserQuery(42));
```

这就是 Mediator 的思想：sender 不知道 handler，handler 不知道 sender，运行时由 mediator 和 DI 容器完成路由。

MediatR 还支持 pipeline behaviors，可以把 logging、validation、performance monitoring 等横切逻辑插入请求管道。这一点和 Chain of Responsibility 有相似之处：每个 behavior 都有机会处理请求，再传给下一个环节。

## 代价是什么

Mediator 最大的代价是可发现性。直接调用 `userService.GetUser(42)` 时，IDE 的“Go to Definition”很清楚。调用 `mediator.Send(new GetUserQuery(42))` 时，你需要通过命名、搜索、约定或插件找到对应 handler。

换来的好处是 handler 小而聚焦，发送方和处理方解耦，测试时可以直接测试 handler 或替换 mediator。这个取舍是否值得，取决于系统复杂度。小项目里滥用 MediatR，会显得绕；复杂应用里，它能把 request handling 组织得很整齐。

## 别写成 God Object

Mediator 模式最常见的坑，是把 mediator 写成一个什么都管的中心类。它开始只是路由消息，后来加了数据库访问、业务规则、状态计算、权限判断、日志拼装，最后变成一个比原来的依赖网更难维护的巨型对象。

可以用几条原则约束它：

- mediator 只负责协调交互，不实现业务规则。
- 不相关的通信域拆成多个 mediator。
- 面向 `IMediator` 这类接口编程，方便替换和测试。
- 广播场景里提前决定异常策略：一个接收者失败，是否影响其他接收者。
- 并发场景下保护参与者列表和路由状态。
- 给 mediator 层加必要日志，帮助追踪间接通信。

好 mediator 像交通控制塔：负责协调路径和顺序。它不应该顺手修飞机、卖机票、算燃油。

## 和其他模式的区别

Observer 是一对多通知：一个 subject 通知多个 observer。Mediator 是多对多协调：多个对象通过中介通信，彼此不认识。

Facade 是给子系统提供简化入口。子系统类不一定知道 facade。Mediator 则是参与者主动依赖 mediator，通过它发送消息。

Command 把请求封装成对象，但不规定请求如何路由。Mediator 负责路由。MediatR 实际上常把两者结合起来：command/query 是请求对象，mediator 把它交给对应 handler。

## 实践判断

如果你在代码里看到一组对象互相持有引用、互相调用、改一个类要跟着改一串类，Mediator 值得考虑。

如果只是两个对象之间很简单的调用，保持直接调用就好。模式不是奖励贴纸，没必要每个交互都绕一圈。

如果已经在用 MediatR，重点不在“用了 mediator 就自动架构好”，而在是否把 request、handler、pipeline behavior 的职责拆清楚。Mediator 只是路由和协调工具，真正的可维护性来自边界感。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [Mediator Design Pattern in C#: Complete Guide with Examples](https://www.devleader.ca/2026/06/06/mediator-design-pattern-in-c-complete-guide-with-examples)
- [MediatR GitHub Repository](https://github.com/jbogard/MediatR)
