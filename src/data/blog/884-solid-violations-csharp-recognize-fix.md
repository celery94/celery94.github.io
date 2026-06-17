---
pubDatetime: 2026-06-17T07:52:42+08:00
title: "SOLID 违规识别与修复：C# 代码审查的五类典型问题"
description: "用五个贴近生产的 C# 代码示例，逐条讲解 SRP、OCP、LSP、ISP、DIP 的典型违规信号与修复方案。附代码审查清单，帮助在 PR 阶段识别结构问题，避免腐化积累。"
tags: ["Csharp", "Design Patterns", "SOLID"]
slug: "solid-violations-csharp-recognize-fix"
source: "https://www.devleader.ca/2026/06/16/solid-violations-c-how-to-recognize-and-fix-each-one"
ogImage: "../../assets/884/01-cover.png"
---

SOLID 违规不会以编译错误或直接崩溃的形式出现。它们表现为摩擦——一个类要读二十分钟才看懂、一次功能改动牵动八个文件、一个 bug "修好"三周后又冒出来。

知道 SOLID 原则的理论和在生产代码中识别违规是两回事。
这篇文章聚焦在**识别和修复**。
每个原则展示一段你会遇到的真实违规代码，然后是重构后的版本。
读完你会有一个在代码审查中捕捉这些信号的心理模型——在它们复合恶化之前。

## SRP 违规：上帝类

单一职责原则说一个类应该只有一条修改理由。
最常见的违规就是上帝类——同时做验证、持久化、邮件通知、日志记录和业务规则。

```csharp
// ❌ SRP 违规——OrderProcessor 做的事太多

public sealed class OrderProcessor
{
    private readonly string _connectionString;

    public OrderProcessor(string connectionString)
    {
        _connectionString = connectionString;
    }

    public void ProcessOrder(Order order)
    {
        // 验证
        if (order.Items.Count == 0)
            throw new InvalidOperationException("Order must have items.");
        if (order.CustomerId == Guid.Empty)
            throw new InvalidOperationException("Customer ID is required.");

        // 业务规则
        decimal total = order.Items.Sum(i => i.Price * i.Quantity);
        if (total > 10_000)
            order.RequiresApproval = true;

        // 持久化——直接写 SQL
        using var connection = new SqlConnection(_connectionString);
        connection.Open();
        using var cmd = connection.CreateCommand();
        cmd.CommandText =
            "INSERT INTO Orders (Id, CustomerId, Total) " +
            "VALUES (@id, @cid, @total)";
        cmd.Parameters.AddWithValue("@id", order.Id);
        cmd.Parameters.AddWithValue("@cid", order.CustomerId);
        cmd.Parameters.AddWithValue("@total", total);
        cmd.ExecuteNonQuery();

        // 邮件通知
        var smtp = new SmtpClient("smtp.company.com");
        smtp.Send("orders@company.com", "warehouse@company.com",
            $"New Order {order.Id}", $"Total: {total:C}");

        // 日志
        File.AppendAllText("orders.log",
            $"[{DateTime.UtcNow:O}] Order {order.Id} processed.\n");
    }
}
```

每次邮件模板变更、表结构变更、验证规则变更、日志格式变更——这个类都要动。
五条独立的修改理由，五个不同的团队可能在同一天编辑同一个文件。

修复方案：把每个关注点抽成独立的类。

```csharp
// ✅ SRP 合规——每个类只管一件事

public interface IOrderValidator
{
    void Validate(Order order);
}

public interface IOrderRepository
{
    Task SaveAsync(Order order, decimal total,
        CancellationToken ct = default);
}

public interface IOrderNotifier
{
    Task NotifyAsync(Order order, decimal total,
        CancellationToken ct = default);
}

public sealed class OrderBusinessRules
{
    public decimal CalculateTotal(Order order) =>
        order.Items.Sum(i => i.Price * i.Quantity);

    public void ApplyApprovalPolicy(
        Order order, decimal total)
    {
        if (total > 10_000)
            order.RequiresApproval = true;
    }
}

public sealed class OrderProcessor(
    IOrderValidator validator,
    IOrderRepository repository,
    IOrderNotifier notifier,
    OrderBusinessRules rules,
    ILogger<OrderProcessor> logger)
{
    public async Task ProcessOrderAsync(
        Order order, CancellationToken ct = default)
    {
        validator.Validate(order);

        decimal total = rules.CalculateTotal(order);
        rules.ApplyApprovalPolicy(order, total);

        await repository.SaveAsync(order, total, ct);
        await notifier.NotifyAsync(order, total, ct);

        logger.LogInformation(
            "Order {OrderId} processed successfully.",
            order.Id);
    }
}
```

现在每个类各自只有一条修改理由。
`OrderProcessor` 变成了一个薄协调器。

## OCP 违规：脆弱的 Switch

开闭原则说代码应该对扩展开放、对修改关闭。
最典型的违规是每次新增类型就要编辑的 `switch` 语句。

```csharp
// ❌ OCP 违规——每次新增支付方式都要改这个类

public sealed class PaymentService
{
    public decimal ProcessPayment(
        string paymentType, decimal amount)
    {
        return paymentType switch
        {
            "CreditCard" => amount * 1.02m,   // 2% 手续费
            "PayPal"     => amount * 1.035m,  // 3.5% 手续费
            "BankWire"   => amount + 15m,     // 固定费用
            _ => throw new NotSupportedException(
                $"Unknown payment type: {paymentType}")
        };
    }
}
```

每新增一种支付方式，就要打开 `PaymentService` 编辑——修改已经能跑通的代码，正是引入 bug 的方式。

修复方案：使用多态 + 注册模式。

```csharp
// ✅ OCP 合规——新增支付类型不必改现有代码

public interface IPaymentProcessor
{
    string PaymentType { get; }
    decimal CalculateFee(decimal amount);
}

public sealed class CreditCardProcessor : IPaymentProcessor
{
    public string PaymentType => "CreditCard";
    public decimal CalculateFee(decimal amount)
        => amount * 1.02m;
}

public sealed class PayPalProcessor : IPaymentProcessor
{
    public string PaymentType => "PayPal";
    public decimal CalculateFee(decimal amount)
        => amount * 1.035m;
}

public sealed class BankWireProcessor : IPaymentProcessor
{
    public string PaymentType => "BankWire";
    public decimal CalculateFee(decimal amount)
        => amount + 15m;
}

public sealed class PaymentService(
    IEnumerable<IPaymentProcessor> processors)
{
    private readonly Dictionary<string, IPaymentProcessor>
        _processors = processors.ToDictionary(
            p => p.PaymentType);

    public decimal ProcessPayment(
        string paymentType, decimal amount)
    {
        if (!_processors.TryGetValue(
            paymentType, out var processor))
            throw new NotSupportedException(
                $"Unknown payment type: {paymentType}");

        return processor.CalculateFee(amount);
    }
}
```

加 "Crypto" 就是写一个新类，什么都不用改。

## LSP 违规：带漏洞的 Override

里氏替换原则说：在任何使用基类的地方，你应该都能替换成子类而不破坏程序。
违规表现为抛出异常、静默忽略行为、或返回哨兵值表示"不支持"。

著名的 `Bird` / `Penguin` 例子：

```csharp
// ❌ LSP 违规——Penguin 是 Bird，但不能飞

public class Bird
{
    public virtual void Fly()
        => Console.WriteLine("Flap flap!");
}

public class Penguin : Bird
{
    public override void Fly() =>
        throw new NotSupportedException(
            "Penguins cannot fly.");
}

// 运行时炸，不是编译时
public static void MakeBirdFly(Bird bird)
    => bird.Fly();

var penguin = new Penguin();
MakeBirdFly(penguin); // 💥 NotSupportedException
```

修复方案：按行为契约而不是现实世界分类来设计继承。

```csharp
// ✅ LSP 合规——按能力拆分抽象

public abstract class Bird
{
    public abstract string Name { get; }
    public abstract void Move();
}

public interface IFlyingBird
{
    void Fly();
}

public sealed class Sparrow : Bird, IFlyingBird
{
    public override string Name => "Sparrow";
    public override void Move() => Fly();
    public void Fly()
        => Console.WriteLine("Sparrow soars.");
}

public sealed class Penguin : Bird
{
    public override string Name => "Penguin";
    public override void Move()
        => Console.WriteLine("Penguin waddles.");
}

// 需要飞行的代码显式要求 IFlyingBird
public static void MakeBirdFly(IFlyingBird bird)
    => bird.Fly();
```

现在编译器会强制执行契约——你不可能不小心把 `Penguin` 传进要求飞行的上下文。
LSP 违规尤其隐蔽，因为它们产生运行时而非编译时失败，往往藏在你很少跑到的代码路径深处。

## ISP 违规：臃肿的接口

接口隔离原则说：客户端不应被迫依赖它不使用的方法。
违规表现为一个臃肿的接口，大多数实现用 `NotImplementedException` 填充半数方法。

```csharp
// ❌ ISP 违规——不是每个仓储都需要 8 个方法

public interface IRepository<T>
{
    T? GetById(Guid id);
    IEnumerable<T> GetAll();
    IEnumerable<T> Search(string query);
    void Add(T entity);
    void Update(T entity);
    void Delete(Guid id);
    void BulkInsert(IEnumerable<T> entities);
    void Archive(Guid id);
}

// 只读缓存实现——一半方法毫无意义
public sealed class CachedProductRepository
    : IRepository<Product>
{
    public Product? GetById(Guid id) => null;
    public IEnumerable<Product> GetAll() => [];
    public IEnumerable<Product> Search(string query) => [];

    public void Add(Product entity) =>
        throw new NotImplementedException("只读缓存");
    public void Update(Product entity) =>
        throw new NotImplementedException("只读缓存");
    public void Delete(Guid id) =>
        throw new NotImplementedException("只读缓存");
    public void BulkInsert(IEnumerable<Product> _) =>
        throw new NotImplementedException("只读缓存");
    public void Archive(Guid id) =>
        throw new NotImplementedException("只读缓存");
}
```

修复：拆成内聚的、聚焦的小接口。

```csharp
// ✅ ISP 合规——按能力拆分接口

public interface IReadRepository<T>
{
    T? GetById(Guid id);
    IEnumerable<T> GetAll();
    IEnumerable<T> Search(string query);
}

public interface IWriteRepository<T>
{
    void Add(T entity);
    void Update(T entity);
    void Delete(Guid id);
}

public interface IBulkRepository<T>
{
    void BulkInsert(IEnumerable<T> entities);
    void Archive(Guid id);
}

// 只读缓存只实现它真正支持的方法
public sealed class CachedProductRepository
    : IReadRepository<Product>
{
    public Product? GetById(Guid id) => null;
    public IEnumerable<Product> GetAll() => [];
    public IEnumerable<Product> Search(string query) => [];
}

// 完整的 SQL 仓储实现所有接口
public sealed class SqlProductRepository :
    IReadRepository<Product>,
    IWriteRepository<Product>,
    IBulkRepository<Product>
{
    public Product? GetById(Guid id) => /* SQL */ null;
    public IEnumerable<Product> GetAll() => /* SQL */ [];
    public IEnumerable<Product> Search(string q) => /* SQL */ [];
    public void Add(Product e) { /* insert */ }
    public void Update(Product e) { /* update */ }
    public void Delete(Guid id) { /* delete */ }
    public void BulkInsert(IEnumerable<Product> e) { }
    public void Archive(Guid id) { /* soft delete */ }
}
```

小接口也让测试大幅简化——依赖 `IReadRepository<T>` 时只需 mock 三个方法而不是八个。

## DIP 违规：硬编码依赖

依赖倒置原则说高层模块不应依赖低层模块，两者都应依赖抽象。
违规信号很明确：业务逻辑类里出现 `new SqlConnection(...)` 或 `new SmtpClient(...)`。

```csharp
// ❌ DIP 违规——业务逻辑直接创建基础设施

public sealed class ReportingService
{
    public IEnumerable<string> GetActiveUserReports()
    {
        using var connection = new SqlConnection(
            "Server=prod-sql;Database=AppDb;...");
        connection.Open();
        using var cmd = connection.CreateCommand();
        cmd.CommandText =
            "SELECT Name FROM Users WHERE IsActive = 1";
        using var reader = cmd.ExecuteReader();

        var results = new List<string>();
        while (reader.Read())
            results.Add(reader.GetString(0));

        return results;
    }
}
```

这段代码无法单元测试、无法切换数据库、无法用内存存储跑测试——不改生产代码的话。
业务逻辑和基础设施焊在一起了。

修复：通过构造函数注入抽象。

```csharp
// ✅ DIP 合规——依赖抽象，通过构造函数注入

public interface IUserRepository
{
    IEnumerable<string> GetActiveUserNames();
}

public sealed class SqlUserRepository(
    IDbConnection connection) : IUserRepository
{
    public IEnumerable<string> GetActiveUserNames()
    {
        if (connection.State != ConnectionState.Open)
            connection.Open();

        using var cmd = connection.CreateCommand();
        cmd.CommandText =
            "SELECT Name FROM Users WHERE IsActive = 1";
        using var reader = cmd.ExecuteReader();

        var results = new List<string>();
        while (reader.Read())
            results.Add(reader.GetString(0));

        return results;
    }
}

public sealed class ReportingService(
    IUserRepository userRepository)
{
    public IEnumerable<string> GetActiveUserReports() =>
        userRepository.GetActiveUserNames();
}
```

`ReportingService` 现在对 SQL、连接字符串或任何基础设施一无所知。
测试中注入 mock `IUserRepository`，生产环境由 DI 容器自动装配 `SqlUserRepository`。

## 违规如何复合恶化

SOLID 违规很少单独出现，它们会连锁反应。

SRP 先出问题——某个类变得太大、职责太多。
改它容易引入 bug，于是开发者开始绕过它而非重构它。
他们加 `if/else` 分支处理新情况——OCP 被突破。

随着类膨胀，继承体系被拉伸来适配变体。
有人写了一个 `LiteOrderProcessor` 继承 `OrderProcessor` 但对支付方法抛异常——LSP 破了。
接口随之膨胀来容纳所有变体——ISP 破了。
最终整坨代码开始直接实例化依赖，因为重构 DI 配置感觉太麻烦——DIP 破了。

一个上帝类经常同时展示多种 SOLID 张力，这体现了违规如何层层复合。
正因如此，在第一个违规信号出现时就重构最划算——而不是等五条全嵌入了再动手。

## 代码审查清单

逐条对照作为 PR 审查提示——不是违规的确凿证据，而是值得调查的信号。

**单一职责**——最常出现，传染性最强

- 这个类是否有多条修改理由？
- 两个不同团队是否可能独立编辑这个类？
- 类名以 "Manager"、"Helper"、"Processor" 结尾，同时做了四五件不相关的事？

**开闭原则**

- 加一个新类型是否需要修改现有的 `switch` 或 `if/else` 链？
- 是否有按类型名映射到行为的 `switch` 或 `if/else if` 链？

**里氏替换**

- 是否有 override 抛出 `NotImplementedException` 或 `NotSupportedException`？
- 子类型是否静默忽略基类契约的一部分？
- 以基类类型编写的代码在拿到这个子类时是否会异常？

**接口隔离**

- 是否有类实现了接口，但半数方法以 `throw new NotImplementedException()` 填充？
- 是否有消费者只用了六方法接口里的两三个方法？
- 接口名字是描述了角色，还是以它唯一的实现类命名？

**依赖倒置**

- 业务逻辑类里是否出现 `new SomeConcreteInfrastructureClass()`？
- 是否有类直接依赖特定数据库库、HTTP 客户端或文件路径？
- 依赖是通过构造函数注入的，还是在方法内部直接创建的？

## 常见问题

**最常碰到的 SOLID 违规是哪条？**

SRP——上帝类。它们随功能迭代自然积累，每次加一小块都显得合理，直到重构变成一个持续数天的大工程。触发信号通常是类名以 "Manager" 或 "Service" 结尾、文件超过 400 行。

**拆分过度也是问题吗？**

是的。如果你把一个类拆成 15 个各含一行逻辑的微类，就从一个问题换成了另一个问题——理解系统的心智模型需要横跨 15 个文件。原则是"一条修改理由"，不是"一个类一个方法"。

**SOLID 违规总是值得修吗？**

不总值得。原型、一次性脚本或截止日下的紧急修复中，结构纯度优先级低于交付。问题在于这段代码会不会被长期维护。如果会——在违规复合之前修掉，每次叠加一层新代码，重构成本就翻倍。

**DI 容器不等于 DIP 合规？**

对。你可以注入具体类——那仍然是 DIP 违规。DIP 的核心是依赖抽象（接口或抽象类），不只是"用了 DI 容器"。核心问题：不改被测类的情况下，你能换掉这个依赖的实现吗？

## 小结

SOLID 违规藏在你天天看的代码里。不是语法错误，不是运行恐慌，而是那些当时觉得合理的结构选择，慢慢让代码库难以扩展、难以测试、难以理解。

识别信号跨所有代码库一致：修改理由过多的类、一直生长的 `switch` 语句、抛异常的 override、充满 `NotImplementedException` 的臃肿接口、以及在自己的方法里 new 基础设施的业务逻辑。看到这些信号，你现在知道在看什么，也知道怎么修。

把那份代码审查清单放在手边，持续使用。你六个月前在审查时拦住的违规，比它们复合半年的修复成本低一个数量级。

---

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [SOLID Violations C#: How to Recognize and Fix Each One — devleader.ca](https://www.devleader.ca/2026/06/16/solid-violations-c-how-to-recognize-and-fix-each-one)
