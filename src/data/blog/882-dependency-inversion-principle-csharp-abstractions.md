---
pubDatetime: 2026-06-16T10:52:30+08:00
title: "C# 依赖倒置原则：让业务代码依赖抽象"
description: "依赖倒置原则提醒我们，业务逻辑不该直接绑在数据库、日志、外部 API 这类具体实现上。本文用 C# 和 .NET 10 示例说明如何引入接口、构造函数注入和 DI 容器，让代码更容易替换、测试和维护。"
tags: ["C#", "SOLID", "依赖注入", ".NET", "软件架构"]
slug: "dependency-inversion-principle-csharp-abstractions"
ogImage: "../../assets/882/01-cover.png"
source: "https://www.devleader.ca/2026/06/15/dependency-inversion-principle-c-abstractions-over-concretions"
---

依赖倒置原则（Dependency Inversion Principle，DIP）是 SOLID 的 D。它解决的问题很常见：业务代码一旦直接依赖数据库、文件系统、HTTP 客户端或具体日志实现，后面替换实现、写单元测试、调整架构都会变重。

原文用 C# 和 .NET 10 示例讲了一个清楚的路径：先识别高层模块和低层模块，再用接口建立抽象契约，接着用构造函数注入和 DI 容器完成对象组装。读完这篇，你应该能判断一段代码是在遵守 DIP，还是只用了依赖注入的外壳。

## DIP 在说什么

DIP 有两条核心规则：

- 高层模块不应该依赖低层模块，双方都应该依赖抽象。
- 抽象不应该依赖细节，细节应该依赖抽象。

在 C# 里，这通常意味着业务类依赖接口，例如 `IOrderRepository`、`IPaymentGateway`、`ILogger<T>`，具体实现由 SQL、文件、第三方服务或日志提供方承担。

这里的“高层模块”通常是业务逻辑：`OrderService`、`PaymentProcessor`、`NotificationManager`。它们描述软件要做什么。

“低层模块”通常是基础设施：`SqlOrderRepository`、`FileLogger`、`StripePaymentGateway`。它们描述事情怎么被完成。

如果 `OrderService` 直接引用 `SqlOrderRepository`，业务逻辑就知道了存储细节。换数据库时，你会改到业务服务。DIP 要把这个方向转过来：业务逻辑只声明自己需要一个订单仓储契约，SQL 仓储去实现这个契约。

## 典型坏味道

原文先给了一个典型 DIP 违规例子：

```csharp
public sealed class SqlOrderRepository
{
    public Order? GetById(int id)
    {
        Console.WriteLine($"Fetching order {id} from SQL Server...");
        return new Order(id, "Widget", 49.99m);
    }

    public void Save(Order order)
    {
        Console.WriteLine($"Saving order {order.Id} to SQL Server...");
    }
}

public sealed class OrderService
{
    private readonly SqlOrderRepository _repository = new();

    public Order? GetOrder(int id) => _repository.GetById(id);
    public void PlaceOrder(Order order) => _repository.Save(order);
}

public record Order(int Id, string ProductName, decimal Price);
```

这段代码的问题集中在一行：

```csharp
private readonly SqlOrderRepository _repository = new();
```

`OrderService` 直接创建了 `SqlOrderRepository`。这会带来三个后果：

- 单元测试很难隔离，测试业务逻辑时会被 SQL 实现拖进去。
- 换成 NoSQL、内存仓储或远程服务时，需要改 `OrderService`。
- `OrderService` 开始负责依赖对象的生命周期，这不该是它的职责。

根因很简单：业务服务知道了太多实现细节。

## 引入抽象

修法是把 `OrderService` 真正需要的能力抽出来：

```csharp
public interface IOrderRepository
{
    Order? GetById(int id);
    void Save(Order order);
}
```

低层模块实现这个契约：

```csharp
public sealed class SqlOrderRepository : IOrderRepository
{
    public Order? GetById(int id)
    {
        Console.WriteLine($"Fetching order {id} from SQL Server...");
        return new Order(id, "Widget", 49.99m);
    }

    public void Save(Order order)
    {
        Console.WriteLine($"Saving order {order.Id} to SQL Server...");
    }
}
```

高层模块依赖契约：

```csharp
public sealed class OrderService(IOrderRepository repository)
{
    public Order? GetOrder(int id) => repository.GetById(id);
    public void PlaceOrder(Order order) => repository.Save(order);
}

public record Order(int Id, string ProductName, decimal Price);
```

现在 `OrderService` 不关心数据来自 SQL Server、内存字典、NoSQL，还是测试替身。它只依赖 `IOrderRepository` 这个契约。

这就是 DIP 最关键的变化：业务逻辑看见的是能力，具体技术选择留在外部组装位置。

## 构造函数注入

DIP 要求依赖从外部传入，而不是在类内部创建。C# 里最常用的方式是构造函数注入。

原文把构造函数注入作为 .NET 10 的主要写法，原因很实际：

- 依赖一眼可见，构造函数签名就是依赖清单。
- 必需依赖在创建对象时就被提供，缺少注册会更早暴露。
- 依赖可以保持不可变，尤其是 C# 主构造函数写法很简洁。
- 测试时可以直接传 mock、stub 或 fake。

C# 12 之后，主构造函数让这段代码更短：

```csharp
public sealed class OrderService(
    IOrderRepository repository,
    ILogger<OrderService> logger)
{
    public Order? GetOrder(int id)
    {
        logger.LogInformation("Getting order {OrderId}", id);
        return repository.GetById(id);
    }

    public void PlaceOrder(Order order)
    {
        logger.LogInformation("Placing order {OrderId}", order.Id);
        repository.Save(order);
    }
}
```

`repository` 和 `logger` 都从外部进入 `OrderService`。类本身只处理订单相关业务。

## 注册到 DI 容器

.NET 的内置容器来自 `Microsoft.Extensions.DependencyInjection`。它负责把接口映射到实现，并在运行时创建对象。

原文中的注册方式如下：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddScoped<IOrderRepository, SqlOrderRepository>();
builder.Services.AddScoped<OrderService>();

builder.Logging.AddConsole();

var host = builder.Build();

using var scope = host.Services.CreateScope();
var orderService = scope.ServiceProvider.GetRequiredService<OrderService>();
var order = orderService.GetOrder(42);
Console.WriteLine($"Retrieved: {order?.ProductName}");

await host.RunAsync();
```

这里有两个关键点。

`AddScoped<IOrderRepository, SqlOrderRepository>()` 表示：当有人需要 `IOrderRepository` 时，容器提供 `SqlOrderRepository`。

`OrderService` 自己不用知道这个映射。容器解析 `OrderService` 时，会读取构造函数，发现它需要 `IOrderRepository` 和 `ILogger<OrderService>`，再把已注册的对象传进去。

## 生命周期要选对

原文也提醒，DI 注册不能只看“能跑起来”。服务生命周期选错，会制造很隐蔽的问题。

常见生命周期有三个：

- `AddSingleton`：整个应用共享一个实例，适合无状态服务、配置对象或创建成本高的基础设施对象。
- `AddScoped`：每个请求或每个 scope 一个实例，Web 应用里的数据库仓储常用这个。
- `AddTransient`：每次解析都创建新实例，适合轻量、无状态、无需共享状态的服务。

比如数据库仓储常用 `AddScoped`，让每个请求拿到自己的仓储实例。后台服务、桌面应用或手动管理 scope 的场景，还要结合实际生命周期重新判断。

## DIP 和 DI 的区别

这两个词经常混在一起，但它们解决的问题不同。

DIP 是设计原则。它说业务逻辑和基础设施都依赖抽象。

DI 是实现模式。它把依赖从外部传进对象，常见方式包括构造函数注入、方法注入、属性注入，以及手动组装。

你可以遵守 DIP，但不用 DI 容器：

```csharp
var repository = new SqlOrderRepository();
var logger = LoggerFactory.Create(b => b.AddConsole())
                          .CreateLogger<OrderService>();
var service = new OrderService(repository, logger);
```

这段手动组装依然遵守 DIP，因为 `OrderService` 依赖的是 `IOrderRepository`。

反过来，你也可能用了 DI 容器，却没有遵守 DIP。比如直接注入 `SqlOrderRepository` 这个具体类型，容器确实帮你创建了对象，但业务服务仍然绑在具体实现上。

判断时别只看有没有容器。要看业务类依赖的是抽象，还是具体实现。

## 容器如何解析

当你写下：

```csharp
builder.Services.AddScoped<IOrderRepository, SqlOrderRepository>();
```

容器会记录一条映射。后面解析 `OrderService` 时，它会检查构造函数，发现需要 `IOrderRepository`，再根据映射创建 `SqlOrderRepository` 并传入。

原文说这是一个简化理解模型。真实容器会缓存解析路径，也会做各种优化。对日常开发来说，理解这个过程已经足够解释很多现象：

- 构造函数注入可以在启动阶段检查依赖图。
- 注册缺失会尽早报错。
- 属性注入更难在启动阶段完整验证。
- 依赖链越清楚，排查容器错误越快。

所以构造函数注入通常是必需依赖的默认选择。可选依赖或运行时选择依赖时，再考虑工厂、方法参数或其他模式。

## 日志是好例子

.NET 里的 `ILogger<T>` 很适合说明 DIP。

业务类依赖的是 `ILogger<PaymentProcessor>`。日志写到控制台、文件、Application Insights，还是 Serilog，是外部注册决定的细节。

```csharp
public sealed class PaymentProcessor(
    IOrderRepository repository,
    ILogger<PaymentProcessor> logger)
{
    public bool ProcessPayment(int orderId, decimal amount)
    {
        var order = repository.GetById(orderId);

        if (order is null)
        {
            logger.LogWarning(
                "Order {OrderId} not found during payment processing",
                orderId);
            return false;
        }

        logger.LogInformation(
            "Processing payment of {Amount:C} for order {OrderId}",
            amount,
            orderId);

        return true;
    }
}
```

如果要把内置控制台日志换成 Serilog，通常改的是启动注册代码。`PaymentProcessor` 不需要变。

这个例子很有代表性：业务代码只依赖稳定抽象，输出目标由基础设施配置决定。

## 测试会变轻

DIP 带来的直接收益是单元测试更轻。

原文用 NSubstitute 写了一个测试例子：

```csharp
using NSubstitute;
using Xunit;

public sealed class OrderServiceTests
{
    [Fact]
    public void GetOrder_WhenOrderExists_ReturnsOrder()
    {
        var repository = Substitute.For<IOrderRepository>();
        var logger = Substitute.For<ILogger<OrderService>>();

        var expectedOrder = new Order(42, "Widget", 49.99m);
        repository.GetById(42).Returns(expectedOrder);

        var service = new OrderService(repository, logger);

        var result = service.GetOrder(42);

        Assert.NotNull(result);
        Assert.Equal("Widget", result.ProductName);
        repository.Received(1).GetById(42);
    }
}
```

测试只关心 `OrderService` 的行为，不需要真实 SQL Server、HTTP 服务或文件系统。仓储用测试替身代替，日志也可以用替身代替。

如果没有 DIP，`OrderService` 内部直接 new 了 `SqlOrderRepository`，这个测试就会被迫靠近集成测试。每次测业务分支，都可能要准备数据库或其他外部资源。

## 架构里的 DIP

DIP 不只适用于一个类。原文把它放进几个常见架构模式里看：

- Facade：外观可以给调用方一个简化入口，内部依然通过抽象隔离复杂子系统。
- Proxy：缓存代理、日志代理、鉴权代理都可以包住同一个接口。
- Mediator：发送方依赖 `IMediator`，不用直接知道每个处理器。
- 模块化单体：模块边界可以用接口表达，模块之间通过抽象通信。

把范围放大后，原则仍然一样：稳定的业务规则和模块边界不该直接依赖具体基础设施类。

## 什么时候别过度抽象

DIP 不等于每个类都要配一个接口。抽象应该服务于变化点、测试需求和边界隔离。

比较适合引入抽象的场景：

- 业务逻辑依赖数据库、消息队列、文件、外部 API 等基础设施。
- 需要在测试里替换真实实现。
- 同一能力已经有多个实现，或未来很可能出现多个实现。
- 你希望把模块边界表达清楚，减少跨层直接引用。

可以暂缓抽象的场景：

- 类型很小，且没有替换需求。
- 代码只在一个地方使用，抽象会让阅读路径变长。
- 接口只是在机械复制实现类的方法，没有表达稳定契约。

好的接口应该描述能力。为了“看起来符合设计原则”硬加接口，通常只会让代码更绕。

## 实践检查清单

你可以用这几个问题检查一段 C# 代码：

- 业务类内部有没有直接 `new` 数据库仓储、HTTP 客户端封装、日志实现或文件访问对象？
- 构造函数参数里有没有具体基础设施类型，例如 `SqlOrderRepository`？
- 单元测试是否必须启动真实数据库、真实文件系统或真实网络服务？
- 换日志提供方、存储实现或支付网关时，是否需要改业务逻辑？
- 接口是否表达了稳定能力，还是只复制了某个实现类的公开方法？

如果这些问题频繁出现，DIP 很可能能帮你减轻耦合。

## 结语

DIP 的重点不是容器，也不是接口数量。重点是让业务代码依赖稳定契约，把具体技术选择留给外部组装。

在 C# 和 .NET 里，最常见的组合是接口、构造函数注入和 DI 容器注册。`OrderService` 依赖 `IOrderRepository`，`SqlOrderRepository` 实现这个接口，测试替身也实现同一个接口。业务逻辑因此更容易测试，也更能承受基础设施变化。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享可操作的工具教程、技术观察和项目经验。

## 参考

- [Dependency Inversion Principle C#: Abstractions Over Concretions](https://www.devleader.ca/2026/06/15/dependency-inversion-principle-c-abstractions-over-concretions)
