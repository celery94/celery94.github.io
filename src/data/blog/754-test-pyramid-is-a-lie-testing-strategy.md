---
pubDatetime: 2026-04-25T09:40:00+08:00
title: "测试金字塔是个谎言——我实际用的测试分层策略"
description: "测试金字塔建议以大量单元测试为基础，但这条建议诞生于 2009 年的基础设施条件。Testcontainers 和 Aspire 改变了集成测试的成本，集成测试才应该是现代测试套件的骨干，本文详述作者亲历的 Bug 案例与他实际采用的四层测试结构。"
tags: ["Testing", ".NET", "Integration Testing", "Unit Testing", "Software Engineering"]
slug: "test-pyramid-is-a-lie-testing-strategy"
ogImage: "../../assets/754/01-cover.png"
source: "https://www.milanjovanovic.tech/blog/the-test-pyramid-is-a-lie-and-what-i-do-instead"
---

![崩裂的测试金字塔，金色奖杯从裂缝中透出光芒](../../assets/754/01-cover.png)

多年来，我的项目从来不像测试金字塔描述的那样。

金字塔说：底层放大量单元测试，中间放少量集成测试，顶端放极少的端到端测试。每次在大会上听到这个模型，我都点头称是，然后回到自己的代码里做了截然不同的事情：少量单元测试只覆盖值得单独测的纯逻辑，大块集成测试跑在真实的 PostgreSQL、RabbitMQ、真实 HTTP 上，最后加几个端到端测试兜住那些一旦挂掉就会让人被炒的关键流程。

这样做之后，我的发布信心反而更强了，不是更弱。

## 金字塔的来历

测试金字塔由 Mike Cohn 在 2009 年普及开来。彼时"集成测试"意味着一台共享数据库服务器、不稳定的 CI 环境，以及动辄 20 分钟的构建时长。用 Mock 写单元测试是当时最务实的妥协方案。

那个时代已经过去了。

有了 [Testcontainers](https://www.milanjovanovic.tech/blog/testcontainers-integration-testing-using-docker-in-dotnet)，我可以为每个测试在几秒内启动一个全新的 PostgreSQL、Redis 或 RabbitMQ 容器。[Aspire 测试宿主](https://learn.microsoft.com/en-us/dotnet/aspire/testing/overview)更进一步，直接把整个应用图连线完成。"真实依赖太贵"这个理由，对于大多数项目来说已经不成立。

但建议没有跟着更新。

## 那个让我彻底改变主意的 Bug

几年前，我有一个服务的单元测试覆盖率达到 94%，全部绿色。

随后用户反映：删除账户之后，他们的数据并没有真正被删掉。

Bug 只有三行：

```csharp
public async Task Handle(DeleteAccountCommand command, CancellationToken ct)
{
    var account = await _repository.GetByIdAsync(command.AccountId, ct);
    account.MarkAsDeleted();
    // 遗漏了：await _unitOfWork.SaveChangesAsync(ct);
}
```

说实话，这个测试用例从来没有被写出来。你当然可以用 Mock 验证 `SaveChangesAsync` 是否被调用，但在一个有几百个 Handler 测试的代码库里，每个测试都有自己的 Mock 设置和验证清单，这种断言很容易被遗漏。我就遗漏了。

一个针对真实数据库的集成测试，不需要任何人去记住这条断言就能把这个 Bug 抓住。这就是核心：**测试风格要求你主动记住的约束越少，漏掉的 Bug 就越少。**

那是我最后一次认真对待测试金字塔的那周。

## 单元测试真正适合什么

我还是会写单元测试，只是数量很少。

单元测试在以下场景才有充分的价值：逻辑非平凡、纯粹（无 I/O、无时间、无随机性）、且难以通过端到端方式验证。符合这个描述的代码有一个明确的范围：[值对象](https://www.milanjovanovic.tech/blog/value-objects-in-dotnet-ddd-fundamentals)和[富领域模型](https://www.milanjovanovic.tech/blog/refactoring-from-an-anemic-domain-model-to-a-rich-domain-model)、定价与税务计算、解析器、映射器、序列化逻辑。

注意不在这个列表里的：应用服务、Handler、Controller、Repository、基础设施层。这些代码活在"接缝"处，而接缝恰恰是真实 Bug 最容易藏身的地方。

## 我实际采用的四层结构

下面是我在典型 .NET 服务或[模块化单体](https://www.milanjovanovic.tech/blog/what-is-a-modular-monolith)中稳定下来的测试形状。它更接近 Kent C. Dodds 的"测试奖杯"，而不是金字塔。

### Layer 1：薄薄的单元测试基础

占测试总数的约 15–25%，全部覆盖领域逻辑，不 Mock 协作对象。如果一个单元测试需要 Mock，我通常会把它提升到集成层。

```csharp
[Fact]
public void Confirm_WhenPending_TransitionsToConfirmed()
{
    var order = Order.Create(CustomerId.New(), Money.Usd(100));

    order.Confirm();

    order.Status.Should().Be(OrderStatus.Confirmed);
    order.DomainEvents.Should().ContainSingle(e => e is OrderConfirmedEvent);
}
```

不需要容器，不需要 Mock，每个测试耗时微秒级。这才是单元测试该做的事。

### Layer 2：厚重的集成测试中层

占主体，约 60–70%。每一个 [Command 和 Query Handler](https://www.milanjovanovic.tech/blog/cqrs-pattern-with-mediatr)、每一个 HTTP 端点、每一个消息消费者，都要有一个跑在 Testcontainers 里真实基础设施上的测试。在[模块化单体](https://www.milanjovanovic.tech/blog/testing-modular-monoliths-system-integration-testing)场景下，这一层还能验证各模块通过公开 API 互相通信的正确性。

```csharp
public class DeleteAccountTests(IntegrationTestWebAppFactory factory)
    : BaseIntegrationTest(factory)
{
    [Fact]
    public async Task DeleteAccount_WhenAccountExists_MarksAccountAsDeleted()
    {
        var account = await CreateAccountAsync();

        var response = await HttpClient.DeleteAsync($"/accounts/{account.Id}");

        response.StatusCode.Should().Be(HttpStatusCode.NoContent);

        var stored = await DbContext.Accounts
            .IgnoreQueryFilters()
            .SingleAsync(a => a.Id == account.Id);

        stored.IsDeleted.Should().BeTrue();
    }
}
```

这个测试一次性覆盖了 HTTP 层、路由、模型绑定、鉴权、Handler、工作单元、EF Core 以及 PostgreSQL。它证明了你真正关心的事：调用这个端点，数据库里的行会变化。而且不需要任何人记住要断言 `SaveChangesAsync` 有没有被调用。

### Layer 3：极少的端到端测试封顶

不超过 10%。只覆盖那些一旦悄悄失效就会带来商业或合规问题的流程：注册、支付、退款、密码重置、[双因素认证](https://www.milanjovanovic.tech/blog/how-to-implement-two-factor-authentication-in-aspnetcore)。它们慢，偶尔有抖动，但它们能捕捉其他层都会漏掉的那一类失败：整个系统作为一个整体是否还能正常工作。

### Layer 0：架构与契约测试

经常被遗忘，但同属于测试套件。[架构测试](https://www.milanjovanovic.tech/blog/5-architecture-tests-you-should-add-to-your-dotnet-projects)强制执行分层规则和模块边界。契约测试验证消息 Schema 和 API 形态不会悄悄漂移。它们在毫秒级运行完成，捕捉的是"六个月后某人会在不自知的情况下破坏这个约定"一类的问题。

这个形状的胖中间是刻意为之的。我的信心就来自那里。

## 常见反驳

**"集成测试很慢。"**

我的典型集成套件，在开启了 Testcontainers 容器复用和测试类并行化之后，在 CI 里跑完需要 2–4 分钟。确实比单元测试慢，但比在生产上发现 Bug 要快得多。

**"只要足够自律，Mock 也没问题。"**

也许吧。但我审计过的每一个重度依赖 Mock 的大型代码库，都有同样的病理特征：重构之后测试仍然是绿色的，但重构已经把生产代码搞挂了。这不是纪律出了问题，而是工具的方向用错了。

## 总结

测试金字塔在 2009 年的基础设施下是好建议，在 2026 年的基础设施下是差建议。Testcontainers 和 Aspire 改变了经济账——现在仍然能告诉你真相的最快反馈回路，是一个跑在真实依赖上的集成测试。单元测试依然属于纯领域逻辑。接缝处的代码，属于集成层。

## 参考

- [原文：The Test Pyramid Is a Lie (and What I Do Instead)](https://www.milanjovanovic.tech/blog/the-test-pyramid-is-a-lie-and-what-i-do-instead)
- [Testcontainers Integration Testing in .NET](https://www.milanjovanovic.tech/blog/testcontainers-integration-testing-using-docker-in-dotnet)
- [Testing Modular Monoliths](https://www.milanjovanovic.tech/blog/testing-modular-monoliths-system-integration-testing)
- [5 Architecture Tests You Should Add to Your .NET Projects](https://www.milanjovanovic.tech/blog/5-architecture-tests-you-should-add-to-your-dotnet-projects)
