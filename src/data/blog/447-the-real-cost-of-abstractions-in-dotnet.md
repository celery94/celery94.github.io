---
pubDatetime: 2025-08-25
tags: [".NET", "Architecture", "Performance", "Productivity"]
slug: the-real-cost-of-abstractions-in-dotnet
source: https://www.milanjovanovic.tech/blog/the-real-cost-of-abstractions-in-dotnet
title: .NET中抽象的真实成本：何时抽象是财富，何时是技术债务
description: 深入探讨.NET开发中抽象的利弊，通过实际案例分析何时应该使用抽象，何时抽象会成为技术债务，以及如何做出明智的架构决策。
---

作为开发者，我们热爱抽象。Repository模式、Service层、Mapper、包装器——它们让我们的代码看起来"干净"，承诺可测试性，并给我们一种正在构建灵活系统的感觉。

但是，**每个抽象都是一笔贷款，从你编写它的那一刻起就要支付利息。**

一些抽象通过隔离真正的易变性和保护系统免受变化影响来赚取回报。而另一些则悄悄地累积复杂性，减慢新人入职速度，并在间接层后隐藏性能问题。

让我们探讨何时抽象能带来收益，何时它们会成为技术债务。

## 何时抽象能带来收益

最好的抽象隔离真正的易变性——系统中你真正期望会发生变化的部分。

### 示例：支付处理

你的核心业务逻辑不应该直接依赖Stripe的SDK。如果你曾经切换到Adyen或Braintree，你不希望这个决定波及到代码库的每个角落。在这里，抽象是有意义的：

```csharp
public interface IPaymentProcessor
{
    Task ProcessAsync(Order order, CancellationToken ct);
}

public class StripePaymentProcessor : IPaymentProcessor
{
    public async Task ProcessAsync(Order order, CancellationToken ct)
    {
        // Stripe特定的实现
        // 处理webhooks、错误代码等
    }
}

public class AdyenPaymentProcessor : IPaymentProcessor
{
    public async Task ProcessAsync(Order order, CancellationToken ct)
    {
        // Adyen特定的实现
        // 不同的API，相同的业务结果
    }
}
```

现在你的业务逻辑可以专注于领域：

```csharp
public class CheckoutService(IPaymentProcessor processor)
{
    public Task CheckoutAsync(Order order, CancellationToken cancellationToken) =>
        processor.ProcessAsync(order, cancellationToken);
}
```

这个抽象隔离了一个真正不稳定的依赖（支付提供商），同时保持结账逻辑的独立性。当Stripe更改他们的API或你切换提供商时，只有一个类需要更改。

这是一个好的抽象。它在你真正需要的地方为你购买了可选性。

## 何时抽象成为技术债务

当我们抽象那些实际上并不易变的东西时，问题就出现了。我们最终包装稳定的库或创建不增加真正价值的层。今天你添加的"干净"层成为明天的维护负担。

### 迷失方向的Repository

大多数团队从一些合理的东西开始：

```csharp
public interface IUserRepository
{
    Task<IEnumerable<User>> GetAllAsync();
}
```

但随着需求的演变，接口也在演变：

```csharp
public interface IUserRepository
{
    Task<IEnumerable<User>> GetAllAsync();
    Task<User?> GetByEmailAsync(string email);
    Task<IEnumerable<User>> GetActiveUsersAsync();
    Task<IEnumerable<User>> GetUsersByRoleAsync(string role);
    Task<IEnumerable<User>> SearchAsync(string keyword, int page, int pageSize);
    Task<IEnumerable<User>> GetUsersWithRecentActivityAsync(DateTime since);
    // ...并且它不断增长
}
```

突然间，repository将查询逻辑泄露到其接口中。每种获取用户的新方式都意味着另一个方法，你的"抽象"变成了每个可能查询的大杂烩。

与此同时，Entity Framework已经通过LINQ为你提供了所有这些：直接映射到SQL的强类型查询。你没有利用这种力量，而是引入了一个间接层，隐藏查询性能特征，并且通常表现更差。Repository模式在ORM不成熟时是有意义的。今天，它通常只是形式主义。

我自己也犯过这样的错误。但作为开发者成熟的一部分是认识到何时模式变成反模式。当Repository封装复杂的查询逻辑或在多个数据源上提供统一API时，它们是有意义的。但你应该努力让它们专注于领域逻辑。一旦它们爆炸成无数个方法来处理每个可能的查询，这就是抽象失败的标志。

## Service包装器：好与坏

不是所有的service包装器都有问题。上下文很重要。

### ✅ 好例子：外部API集成

当与外部API集成时，包装器通过集中关注点提供真正的价值：

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

这个包装器隔离了GitHub的API细节。当认证更改或端点演变时，你只需更新一个地方。你的业务逻辑永远不需要知道HTTP头、基础URL或JSON序列化。

### ❌ 坏例子：透传服务

当我们包装自己的稳定服务而不添加业务价值时，麻烦就开始了：

```csharp
public class UserService(IUserRepository userRepository)
{
    // 只是转发调用而没有添加价值
    public Task<User?> GetByIdAsync(Guid id) => userRepository.GetByIdAsync(id);
    public Task<IEnumerable<User>> GetAllAsync() => userRepository.GetAllAsync();
    public Task SaveAsync(User user) => userRepository.SaveAsync(user);
}
```

这个`UserService`是纯粹的间接。它所做的就是将调用转发给`IUserRepository`。它不强制业务规则，不添加验证，不实现缓存，也不提供任何真正的功能。它是一个存在的层，仅仅因为"服务是好架构"。

随着这些贫血包装器的增多，你的代码库变成了迷宫。开发者浪费时间导航层次，而不是专注于业务逻辑实际存在的地方。

## 做出更好的决策

以下是如何思考抽象何时值得投资：

### 抽象策略，而非机制

- **策略**是可能改变的决策：使用哪个支付提供商，如何处理缓存，外部调用的重试策略
- **机制**是稳定的实现细节：EF Core的LINQ语法，`HttpClient`配置，JSON序列化

抽象策略，因为它们给你灵活性。不要抽象机制，它们已经是稳定的API，很少以破坏性方式改变。

### 等待第二个实现

如果你只有一个实现，请抵制接口的冲动。单个实现不能证明抽象的合理性，这是过早的泛化，增加了复杂性而没有好处。

考虑这种演变：

```csharp
// 步骤1：从具体开始
public class EmailNotifier
{
    public async Task SendAsync(string to, string subject, string body)
    {
        // SMTP实现
    }
}

// 步骤2：需要SMS？现在抽象
public interface INotifier
{
    Task SendAsync(string to, string subject, string body);
}

public class EmailNotifier : INotifier { /* ... */ }
public class SmsNotifier : INotifier { /* ... */ }
```

当你真正需要时，抽象自然出现。接口通过真实需求揭示自己，而不是想象的需求。

### 保持实现在内部，抽象在边界

在你的应用程序内部，偏好具体类型。直接使用Entity Framework，将`HttpClient`配置为类型化客户端，使用领域实体工作。只在你的系统遇到外部世界的地方引入抽象：外部API、第三方SDK、基础设施服务。

那是最可能发生变化的地方，也是抽象赚取回报的地方。

## 重构坏抽象

定期用这个问题审查你的抽象：如果我移除这个抽象，代码会变得更简单还是更复杂？

如果移除一个接口或服务层会让代码更清晰、更直接，那个抽象可能成本超过价值。不要害怕删除不必要的层。更简单的代码通常是更好的代码。

当你识别出有问题的抽象时，以下是安全移除它们的方法：

1. 识别真正的消费者。谁真正需要抽象？
2. 内联接口。用具体实现替换抽象调用。
3. 删除包装器。移除不必要的间接。
4. 简化调用代码。利用具体API的特性。

例如，用直接的EF Core使用替换repository：

```csharp
// 之前：隐藏在repository后面
var users = await _userRepo.GetActiveUsersWithRecentOrders();

// 之后：直接、优化的查询
var users = await _context.Users
    .Where(u => u.IsActive)
    .Where(u => u.Orders.Any(o => o.CreatedAt > DateTime.Now.AddDays(-30)))
    .Include(u => u.Orders.Take(5))
    .ToListAsync();
```

具体版本更明确地说明它获取什么数据以及如何获取，使性能特征可见并可能优化。如果你在多个地方需要相同的查询，你可以将其移动到扩展方法中以使其可共享。

## 关键要点

抽象是管理复杂性和变化的强大工具，但它们不是免费的。每一个都增加间接性、认知开销和维护负担。

最干净的架构不是拥有最多层的架构。它是每一层都有明确、合理目的的架构。

在添加下一个抽象之前，问问自己：

- 我是在抽象策略还是仅仅机制？
- 我有两个实现，还是我在推测未来需求？
- 这会让我的系统更适应，还是只是更难跟随？
- 如果我移除这一层，代码会变得更简单吗？

记住：抽象是随时间产生利息的贷款。确保你借钱是出于正确的原因，而不仅仅是出于习惯。

目标是有意地使用抽象，在它们解决真实问题并防范真正易变性的地方。构建能赚取回报的抽象。删除不能的。

## 深入理解抽象的成本分析

### 性能影响

抽象层往往隐藏性能特征。当你通过多层间接调用数据库查询时，很难看到实际发生了什么：

```csharp
// 隐藏的N+1问题
public async Task<IEnumerable<UserDto>> GetUsersWithOrdersAsync()
{
    var users = await _userService.GetAllUsersAsync();
    var result = new List<UserDto>();

    foreach (var user in users)
    {
        var orders = await _orderService.GetOrdersByUserIdAsync(user.Id); // N+1!
        result.Add(new UserDto(user, orders));
    }

    return result;
}

// 直接、优化的版本
public async Task<IEnumerable<UserDto>> GetUsersWithOrdersAsync()
{
    return await _context.Users
        .Include(u => u.Orders)
        .Select(u => new UserDto(u, u.Orders))
        .ToListAsync();
}
```

直接版本让性能问题立即可见，而抽象版本将其隐藏在看似无害的方法调用后面。

### 测试复杂性

过度抽象实际上会使测试变得更加困难：

```csharp
// 过度抽象的测试噩梦
[Test]
public async Task CheckoutAsync_ShouldProcessPayment()
{
    // 需要模拟5个不同的接口
    var mockUserRepo = new Mock<IUserRepository>();
    var mockOrderRepo = new Mock<IOrderRepository>();
    var mockPaymentProcessor = new Mock<IPaymentProcessor>();
    var mockEmailService = new Mock<IEmailService>();
    var mockLogger = new Mock<ILogger>();

    // 100行设置代码...

    var service = new CheckoutService(
        mockUserRepo.Object,
        mockOrderRepo.Object,
        mockPaymentProcessor.Object,
        mockEmailService.Object,
        mockLogger.Object
    );

    await service.CheckoutAsync(order);

    // 验证所有模拟调用...
}

// 更简单的集成测试
[Test]
public async Task CheckoutAsync_ShouldProcessPayment()
{
    // 使用内存数据库和真实的业务逻辑
    using var context = CreateInMemoryContext();
    var paymentProcessor = new TestPaymentProcessor();

    var service = new CheckoutService(context, paymentProcessor);

    var result = await service.CheckoutAsync(order);

    Assert.That(result.IsSuccess, Is.True);
    Assert.That(paymentProcessor.ProcessedPayments.Count, Is.EqualTo(1));
}
```

### 认知负荷

每个抽象层都增加了开发者需要理解的心理模型：

```csharp
// 6层深的调用链
Controller -> Service -> Manager -> Handler -> Repository -> ORM -> Database

// 更直接的方法
Controller -> Business Logic -> Database
```

新团队成员需要理解的概念越少，他们就能越快地开始贡献有意义的代码。

## 实际重构策略

### 识别重构候选

寻找这些抽象债务的警告信号：

1. **一对一映射**：接口只有一个实现，没有计划的第二个
2. **透传方法**：方法只是转发到另一个服务
3. **爆炸式接口**：接口随时间不断增长新方法
4. **测试困难**：需要大量模拟设置的测试
5. **性能谜团**：难以理解查询如何执行

### 安全重构步骤

```csharp
// 步骤1：识别使用模式
// 找到IUserService的所有用法
public interface IUserService
{
    Task<User> GetByIdAsync(int id);
    Task SaveAsync(User user);
}

// 步骤2：创建具体实现
public class UserOperations
{
    private readonly AppDbContext _context;

    public UserOperations(AppDbContext context)
    {
        _context = context;
    }

    public async Task<User> GetByIdAsync(int id)
    {
        return await _context.Users
            .FirstOrDefaultAsync(u => u.Id == id);
    }

    public async Task SaveAsync(User user)
    {
        _context.Users.Update(user);
        await _context.SaveChangesAsync();
    }
}

// 步骤3：逐步替换使用
// 替换依赖注入
services.AddScoped<UserOperations>();
// services.AddScoped<IUserService, UserService>(); // 注释掉旧的

// 步骤4：更新消费者
public class SomeController
{
    private readonly UserOperations _userOps; // 改变类型

    public SomeController(UserOperations userOps) // 更新构造函数
    {
        _userOps = userOps;
    }
}

// 步骤5：清理
// 删除接口和旧实现
```

## 架构决策指南

### 何时添加抽象：决策树

```text
需要新功能？
├─ 是否涉及外部系统？
│  ├─ 是 → 考虑抽象（API、第三方服务）
│  └─ 否 → 继续...
├─ 是否有多个实现？
│  ├─ 是 → 抽象可能有用
│  └─ 否 → 继续...
├─ 实现是否可能改变？
│  ├─ 很可能 → 考虑轻量级抽象
│  ├─ 可能 → 先实现，后抽象
│  └─ 不太可能 → 使用具体实现
```

### 抽象质量检查清单

在引入抽象之前，问这些问题：

- [ ] 这个抽象解决了具体的变更场景吗？
- [ ] 抽象的边界是否明确定义？
- [ ] 是否有至少两个合理的实现？
- [ ] 抽象是否增加了显著的认知负荷？
- [ ] 性能特征是否仍然可见？
- [ ] 测试是否变得更简单或更复杂？

## 现代.NET中的抽象最佳实践

### 利用.NET的内置抽象

.NET已经提供了许多优秀的抽象。不要重新发明：

```csharp
// 使用IHostedService而不是自定义服务抽象
public class PaymentProcessingService : IHostedService
{
    // 利用框架的生命周期管理
}

// 使用IOptions<T>而不是自定义配置抽象
public class EmailService
{
    private readonly EmailSettings _settings;

    public EmailService(IOptions<EmailSettings> settings)
    {
        _settings = settings.Value;
    }
}

// 使用HttpClient而不是自定义HTTP抽象
public class GitHubService
{
    private readonly HttpClient _httpClient;

    public GitHubService(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }
}
```

### 函数式方法

考虑函数式方法而不是重接口：

```csharp
// 而不是接口...
public interface IValidator<T>
{
    ValidationResult Validate(T item);
}

// 使用委托
public delegate ValidationResult Validator<T>(T item);

// 或者函数式方法
public static class Validators
{
    public static ValidationResult ValidateEmail(string email) =>
        IsValidEmail(email) ? ValidationResult.Success : ValidationResult.Failure("Invalid email");

    public static ValidationResult ValidateAge(int age) =>
        age >= 18 ? ValidationResult.Success : ValidationResult.Failure("Must be 18+");
}

// 使用
var emailResult = Validators.ValidateEmail(user.Email);
var ageResult = Validators.ValidateAge(user.Age);
```

## 总结

抽象是软件设计中强大的工具，但像所有强大的工具一样，它们需要谨慎使用。关键是要认识到抽象不是目标，而是达到目标的手段——管理复杂性，应对变化，提高代码的可维护性。

好的抽象：

- 解决真实的变更场景
- 有明确的边界和职责
- 简化而不是复杂化代码
- 使性能特征可见
- 随时间赚取回报

坏的抽象：

- 基于假设的未来需求
- 仅有一个实现
- 增加不必要的间接层
- 隐藏重要的实现细节
- 累积技术债务

记住，最好的代码往往是最简单的代码。在添加抽象之前，问问自己：这真的让事情变得更好了吗？
