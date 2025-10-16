---
pubDatetime: 2025-10-06
title: .NET 中抽象的真实代价：何时使用，何时避免
description: 深入探讨在 .NET 开发中使用抽象的利弊权衡。通过实际案例分析接口、仓储模式和服务包装器等抽象手段的适用场景，帮助开发者做出更明智的架构决策，避免过度设计带来的技术债务。
tags: [".NET", "Architecture", "Performance"]
slug: real-cost-of-abstractions-in-dotnet
source: https://www.milanjovanovic.tech/blog/the-real-cost-of-abstractions-in-dotnet
---

作为开发者，我们对抽象有着天然的热爱。仓储（Repository）、服务（Service）、映射器（Mapper）、包装器（Wrapper）——这些抽象让我们的代码看起来"整洁"，承诺提供可测试性，并给我们一种正在构建灵活系统的安全感。

然而，有一个关键认知需要建立：**每个抽象都是一笔贷款，你从编写它的那一刻起就要支付利息**。

一些抽象通过隔离真正的易变性（volatility）和保护系统免受变化影响而获得回报；另一些则悄然堆积复杂性，拖慢团队入职速度，并在层层间接调用背后隐藏性能问题。本文将深入探讨何时抽象能带来红利，何时它们会变成技术债务。

## 抽象的本质：权衡与代价

在软件架构中，抽象是一种强大的工具，但它并非没有成本。每增加一层抽象，你就在代码库中引入了以下开销：

### 认知负担

开发者需要理解接口背后的实现逻辑。当你看到 `IUserRepository` 时，你必须跳转到具体实现才能了解实际的数据访问模式。这种间接性在小型项目中可能微不足道，但在大型系统中会显著增加理解成本。

### 性能影响

虽然现代 JIT 编译器能够内联（inline）许多虚方法调用，但抽象层仍然会引入开销。接口调用无法像具体类型调用那样被优化，特别是在热路径（hot path）中，这种影响会被放大。

### 维护成本

每个接口都需要与其实现保持同步。当业务需求变化时，你不仅要修改实现，还要更新接口定义、所有模拟对象（mock）以及相关测试代码。

## 何时抽象能带来价值

最佳的抽象是那些能够隔离真正易变性的抽象——即你真正预期会发生变化的系统部分。

### 案例：支付处理系统

考虑一个电商系统的支付处理模块。你的核心业务逻辑不应该直接依赖 Stripe SDK。如果将来切换到 Adyen 或 Braintree，你不希望这个决策在代码库的每个角落产生连锁反应。这里，抽象就非常有意义：

```csharp
public interface IPaymentProcessor
{
    Task ProcessAsync(Order order, CancellationToken ct);
}

public class StripePaymentProcessor : IPaymentProcessor
{
    public async Task ProcessAsync(Order order, CancellationToken ct)
    {
        // Stripe 特定实现
        // 处理 webhook、错误码等
    }
}

public class AdyenPaymentProcessor : IPaymentProcessor
{
    public async Task ProcessAsync(Order order, CancellationToken ct)
    {
        // Adyen 特定实现
        // 不同的 API，相同的业务结果
    }
}
```

现在你的业务逻辑可以专注于领域本身：

```csharp
public class CheckoutService(IPaymentProcessor processor)
{
    public Task CheckoutAsync(Order order, CancellationToken cancellationToken) =>
        processor.ProcessAsync(order, cancellationToken);
}
```

这个抽象隔离了一个真正不稳定的依赖（支付提供商），同时保持结账逻辑的独立性。当 Stripe 更改其 API 或你切换提供商时，只有一个类需要修改。

**这就是一个好的抽象**。它在你真正需要的地方为你提供了可选择性。

### 外部 API 集成包装器

当与外部 API 集成时，包装器能够提供真正的价值，通过集中关注点：

```csharp
public interface IGitHubClient
{
    Task<UserDto?> GetUserAsync(string username);
    Task<IReadOnlyList<RepoDto>> GetRepositoriesAsync(string username);
}

public class GitHubClient(HttpClient httpClient) : IGitHubClient
{
    public Task<UserDto?> GetUserAsync(string username) =>
        httpClient.GetFromJsonAsync<UserDto>($"/users/{username}");

    public Task<IReadOnlyList<RepoDto>> GetRepositoriesAsync(string username) =>
        httpClient.GetFromJsonAsync<IReadOnlyList<RepoDto>>($"/users/{username}/repos");
}
```

这个包装器隔离了 GitHub API 的细节。当身份验证方式改变或端点演进时，你只需更新一个地方。你的业务逻辑永远不需要知道 HTTP 头、基础 URL 或 JSON 序列化的事情。

## 何时抽象成为技术债务

问题出现在我们抽象那些实际上并不易变的事物时。我们最终包装了稳定的库或创建了不增加实际价值的层。今天添加的"整洁"层成为明天的维护负担。

### 迷失方向的仓储模式

大多数团队从一些合理的东西开始：

```csharp
public interface IUserRepository
{
    Task<IEnumerable<User>> GetAllAsync();
}
```

但随着需求的演变，接口也在膨胀：

```csharp
public interface IUserRepository
{
    Task<IEnumerable<User>> GetAllAsync();
    Task<User?> GetByEmailAsync(string email);
    Task<IEnumerable<User>> GetActiveUsersAsync();
    Task<IEnumerable<User>> GetUsersByRoleAsync(string role);
    Task<IEnumerable<User>> SearchAsync(string keyword, int page, int pageSize);
    Task<IEnumerable<User>> GetUsersWithRecentActivityAsync(DateTime since);
    // ...并且持续增长
}
```

突然之间，仓储将查询逻辑泄漏到了它的接口中。每种新的用户获取方式都意味着又一个方法，你的"抽象"变成了一个包罗万象的查询大杂烩。

与此同时，Entity Framework 已经通过 LINQ 为你提供了所有这些功能：强类型查询，直接映射到 SQL。你没有利用这种能力，反而引入了一个间接层，隐藏了查询的性能特征，并且往往表现更差。

**仓储模式在 ORM 不成熟时很有意义。今天，它通常只是仪式性的代码。**

我自己也曾犯过这个错误。但作为开发者成熟的一部分，就是要认识到何时模式变成了反模式。当仓储为封装复杂查询逻辑或提供跨多个数据源的统一 API 时，它们是有意义的。但你应该努力让它们专注于领域逻辑。一旦它们为每个可能的查询爆炸成无数方法，这就是抽象失败的信号。

### 传递型服务：毫无价值的间接层

问题在我们包装自己的稳定服务而不增加业务价值时开始：

```csharp
public class UserService(IUserRepository userRepository)
{
    // 只是转发调用，没有增加任何价值
    public Task<User?> GetByIdAsync(Guid id) => 
        userRepository.GetByIdAsync(id);
    
    public Task<IEnumerable<User>> GetAllAsync() => 
        userRepository.GetAllAsync();
    
    public Task SaveAsync(User user) => 
        userRepository.SaveAsync(user);
}
```

这个 `UserService` 是纯粹的间接调用。它所做的只是将调用转发给 `IUserRepository`。它不强制执行业务规则、不添加验证、不实现缓存，也不提供任何实际功能。这一层的存在仅仅因为"服务是好的架构"。

随着这些贫血包装器（anemic wrapper）的增加，你的代码库变成了一个迷宫。开发者浪费时间导航层次，而不是专注于业务逻辑实际存在的地方。

## 做出更明智的决策

那么，如何判断何时值得投资于抽象呢？以下是一些实用的指导原则：

### 1. 抽象策略（Policy），而非机制（Mechanics）

- **策略**是可能改变的决策：使用哪个支付提供商、如何处理缓存、外部调用的重试策略
- **机制**是稳定的实现细节：EF Core 的 LINQ 语法、`HttpClient` 配置、JSON 序列化

抽象策略，因为它们给你灵活性。不要抽象机制——它们已经是稳定的 API，很少以破坏性方式改变。

### 2. 等待第二个实现

如果你只有一个实现，请抵制接口的冲动。单一实现不能证明抽象的合理性——这是过早的泛化，只会增加复杂性而没有好处。

考虑这个演变过程：

```csharp
// 步骤 1：从具体开始
public class EmailNotifier
{
    public async Task SendAsync(string to, string subject, string body)
    {
        // SMTP 实现
    }
}

// 步骤 2：需要 SMS？现在抽象
public interface INotifier
{
    Task SendAsync(string to, string subject, string body);
}

public class EmailNotifier : INotifier { /* ... */ }
public class SmsNotifier : INotifier { /* ... */ }
```

抽象在你实际需要时自然浮现。接口通过真实需求展示自己，而非想象的需求。

### 3. 保持实现在内部，抽象在边界

在应用程序内部，优先使用具体类型。直接使用 Entity Framework，将 `HttpClient` 配置为类型化客户端，直接操作领域实体。只在系统与外部世界交汇的地方引入抽象：外部 API、第三方 SDK、基础设施服务。

那里是最可能发生变化的地方，也是抽象赚取回报的地方。

### 4. 问自己关键问题

在添加下一个抽象之前，问自己：

- 我是在抽象策略还是仅仅抽象机制？
- 我有两个实现，还是在推测未来需求？
- 这会让我的系统更适应变化，还是只是更难理解？
- 如果我移除这一层，代码会变得更简单吗？

## 重构掉不良抽象

定期用这个问题审视你的抽象：**如果我移除这个抽象，代码会变得更简单还是更复杂？**

如果移除一个接口或服务层会让代码更清晰、更直接，那么这个抽象的成本可能超过了它的价值。不要害怕删除不必要的层。更简单的代码往往是更好的代码。

当你识别出有问题的抽象时，以下是安全移除它们的方法：

1. **识别真正的消费者**：谁真正需要这个抽象？
2. **内联接口**：用具体实现替换抽象调用
3. **删除包装器**：移除不必要的间接层
4. **简化调用代码**：利用具体 API 的特性

例如，用直接的 EF Core 使用替换仓储：

```csharp
// 之前：隐藏在仓储后面
var users = await _userRepo.GetActiveUsersWithRecentOrders();

// 之后：直接、优化的查询
var users = await _context.Users
    .Where(u => u.IsActive)
    .Where(u => u.Orders.Any(o => o.CreatedAt > DateTime.Now.AddDays(-30)))
    .Include(u => u.Orders.Take(5))
    .ToListAsync();
```

具体版本更明确地说明了它获取什么数据以及如何获取，使性能特征可见并且优化成为可能。如果你需要在多个地方使用相同的查询，可以将其移动到扩展方法中以使其可共享。

## 核心原则

抽象是管理复杂性和变化的强大工具，但它们并非免费的。每一个都会增加间接性、认知开销和维护负担。

**最整洁的架构不是拥有最多层的架构，而是每一层都有明确、合理目的的架构。**

记住：抽象是会随时间累积利息的贷款。确保你借贷的理由是正确的，而不仅仅是出于习惯。目标是有意识地使用抽象，在它们解决实际问题并防范真正的易变性时。构建能够赚取回报的抽象，删除那些不能的。

在 .NET 开发中，Entity Framework Core、ASP.NET Core、`HttpClient` 等框架已经提供了高度优化和稳定的 API。在大多数情况下，直接使用这些工具比创建额外的抽象层更有效。只有在面对真正的易变性——如第三方服务、业务策略、外部依赖——时，抽象才能体现其真正价值。

通过遵循"抽象策略而非机制"、"等待第二个实现"、"保持实现在内部"等原则，你可以构建既灵活又可维护的系统，避免过度设计带来的技术债务。

## 参考资料

- [The Real Cost of Abstractions in .NET - Milan Jovanovic](https://www.milanjovanovic.tech/blog/the-real-cost-of-abstractions-in-dotnet)
- [Pragmatic Clean Architecture](https://www.milanjovanovic.tech/pragmatic-clean-architecture)
