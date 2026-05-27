---
pubDatetime: 2026-05-28T07:12:26+08:00
title: "用 C# 实现责任链模式：5 步写出生产级审批链"
description: "以采购审批为例，分步演示 C# 责任链模式的接口 vs 抽象类选型、具体处理器编写、Builder 链构建、DI 容器集成和日志诊断，附常见踩坑点。"
tags: ["CSharp", "Design Patterns"]
slug: "csharp-chain-of-responsibility-pattern-guide"
ogImage: "../../assets/836/01-cover.png"
source: "https://www.devleader.ca/2026/05/27/how-to-implement-chain-of-responsibility-pattern-in-c-stepbystep-guide"
---

责任链模式的核心思路很简单：把一个请求沿着一条处理器链传下去，每个处理器自己判断能不能接手，不能就交给下一位。这篇文章用一个采购审批流程做例子，从定义处理器抽象一直走到 DI 注册和日志诊断，每一步都给出可编译的 C# 代码。

读完你会拿到一套能直接用于生产的责任链骨架：处理器只需关心"我能不能处理"和"怎么处理"，链的组装、传递、兜底、诊断全部由基类和构建器搞定。

## 定义处理器抽象

责任链的起点是一个处理器抽象。你有两条路：接口或抽象类。

### 接口方式

```csharp
public interface IHandler<TRequest>
{
    IHandler<TRequest>? NextHandler { get; }

    void SetNext(IHandler<TRequest> next);

    void Handle(TRequest request);
}
```

泛型 `TRequest` 让你不需要做类型转换就能处理任意请求类型。但问题是：每个处理器都要重复实现 `SetNext` 和"判断是否传递"的逻辑。如果有十个处理器，就是十份几乎一模一样的代码。

### 抽象类方式（推荐）

```csharp
public abstract class HandlerBase<TRequest>
{
    private HandlerBase<TRequest>? _nextHandler;

    public void SetNext(HandlerBase<TRequest> next)
    {
        _nextHandler = next;
    }

    public void Handle(TRequest request)
    {
        if (CanHandle(request))
        {
            Process(request);
            return;
        }

        if (_nextHandler is not null)
        {
            _nextHandler.Handle(request);
            return;
        }

        HandleUnprocessed(request);
    }

    protected abstract bool CanHandle(TRequest request);

    protected abstract void Process(TRequest request);

    protected virtual void HandleUnprocessed(
        TRequest request)
    {
        Console.WriteLine(
            "[Chain] Request reached end of chain " +
            "without being handled.");
    }
}
```

基类把链的串联和传递逻辑集中在一个地方，具体处理器只需回答两个问题：`CanHandle`——我能不能接手？`Process`——怎么处理？`HandleUnprocessed` 提供了链末尾的兜底行为，子类可以覆盖。

这种做法和模板方法模式（Template Method）如出一辙：基类定义算法骨架，子类填充细节。大多数场景下推荐用抽象类。

## 编写具体处理器

用一个采购审批场景来演示：不同级别的审批人可以批准不同金额上限的采购申请。

先定义请求对象：

```csharp
public sealed class PurchaseRequest
{
    public string Description { get; }
    public decimal Amount { get; }
    public string RequestedBy { get; }

    public PurchaseRequest(
        string description,
        decimal amount,
        string requestedBy)
    {
        Description = description;
        Amount = amount;
        RequestedBy = requestedBy;
    }

    public override string ToString()
    {
        return $"{Description} (${Amount:N2}) " +
            $"by {RequestedBy}";
    }
}
```

然后依次实现四个处理器，审批额度从低到高：

### ManagerHandler（≤ $1,000）

```csharp
public sealed class ManagerHandler
    : HandlerBase<PurchaseRequest>
{
    private const decimal ApprovalLimit = 1_000m;

    protected override bool CanHandle(
        PurchaseRequest request)
    {
        return request.Amount <= ApprovalLimit;
    }

    protected override void Process(
        PurchaseRequest request)
    {
        Console.WriteLine(
            $"[Manager] Approved: {request}");
    }
}
```

### DirectorHandler（≤ $10,000）

```csharp
public sealed class DirectorHandler
    : HandlerBase<PurchaseRequest>
{
    private const decimal ApprovalLimit = 10_000m;

    protected override bool CanHandle(
        PurchaseRequest request)
    {
        return request.Amount <= ApprovalLimit;
    }

    protected override void Process(
        PurchaseRequest request)
    {
        Console.WriteLine(
            $"[Director] Approved: {request}");
    }
}
```

### VPHandler（≤ $50,000）

```csharp
public sealed class VPHandler
    : HandlerBase<PurchaseRequest>
{
    private const decimal ApprovalLimit = 50_000m;

    protected override bool CanHandle(
        PurchaseRequest request)
    {
        return request.Amount <= ApprovalLimit;
    }

    protected override void Process(
        PurchaseRequest request)
    {
        Console.WriteLine(
            $"[VP] Approved: {request}");
    }
}
```

### CEOHandler（无上限）

```csharp
public sealed class CEOHandler
    : HandlerBase<PurchaseRequest>
{
    protected override bool CanHandle(
        PurchaseRequest request)
    {
        return true; // CEO 可以批准任意金额
    }

    protected override void Process(
        PurchaseRequest request)
    {
        Console.WriteLine(
            $"[CEO] Approved: {request}");
    }
}
```

几个值得注意的地方：

- 每个处理器的判断条件清晰单一，Manager 管 $1,000 以内，Director 管 $10,000 以内，依此类推。
- `CEOHandler` 充当终端处理器——`CanHandle` 永远返回 `true`，确保没有请求会从链尾漏掉。
- 这些处理器之间完全不知道彼此的存在。`ManagerHandler` 不知道有 `DirectorHandler`，这种解耦正是责任链模式的核心价值。

这种关注点分离和策略模式（Strategy Pattern）类似。区别在于：策略模式由调用方显式选择用哪个算法；责任链模式由处理器自己根据请求内容决定是否接手。

## 组装处理器链

### 手动串联

最直接的方式是逐个调用 `SetNext`：

```csharp
var manager = new ManagerHandler();
var director = new DirectorHandler();
var vp = new VPHandler();
var ceo = new CEOHandler();

manager.SetNext(director);
director.SetNext(vp);
vp.SetNext(ceo);

manager.Handle(new PurchaseRequest(
    "Office supplies", 500m, "Alice"));
// [Manager] Approved: Office supplies ($500.00) by Alice

manager.Handle(new PurchaseRequest(
    "Server hardware", 8_000m, "Bob"));
// [Director] Approved: Server hardware ($8,000.00) by Bob

manager.Handle(new PurchaseRequest(
    "Company retreat", 75_000m, "Carol"));
// [CEO] Approved: Company retreat ($75,000.00) by Carol
```

能跑，但容易出错——漏掉一个 `SetNext` 调用或者顺序接反，链就静默地断了。处理器少的时候还好，多了以后维护成本上升。

### 用 Builder 做流式构建（推荐）

用一个 Builder 封装链的组装逻辑：

```csharp
public sealed class ChainBuilder<TRequest>
{
    private readonly List<HandlerBase<TRequest>> _handlers
        = new();

    public ChainBuilder<TRequest> AddHandler(
        HandlerBase<TRequest> handler)
    {
        _handlers.Add(handler);
        return this;
    }

    public HandlerBase<TRequest> Build()
    {
        if (_handlers.Count == 0)
        {
            throw new InvalidOperationException(
                "Chain must contain at least one handler.");
        }

        for (int i = 0; i < _handlers.Count - 1; i++)
        {
            _handlers[i].SetNext(_handlers[i + 1]);
        }

        return _handlers[0];
    }
}
```

`Build()` 返回链的第一个处理器——请求入口。使用起来很清晰：

```csharp
var chain = new ChainBuilder<PurchaseRequest>()
    .AddHandler(new ManagerHandler())
    .AddHandler(new DirectorHandler())
    .AddHandler(new VPHandler())
    .AddHandler(new CEOHandler())
    .Build();

chain.Handle(new PurchaseRequest(
    "Team lunch", 250m, "Dave"));
// [Manager] Approved: Team lunch ($250.00) by Dave

chain.Handle(new PurchaseRequest(
    "Annual license", 25_000m, "Eve"));
// [VP] Approved: Annual license ($25,000.00) by Eve
```

Builder 内部处理所有串联工作，你不可能漏掉连接。生产代码里多花这点前置投入是值得的。

## 接入依赖注入

实际项目中你会希望通过 DI 容器管理处理器的生命周期。先注册各个处理器：

```csharp
using Microsoft.Extensions.DependencyInjection;

var services = new ServiceCollection();

services.AddSingleton<ManagerHandler>();
services.AddSingleton<DirectorHandler>();
services.AddSingleton<VPHandler>();
services.AddSingleton<CEOHandler>();
```

再注册一个工厂，从容器中解析处理器并用 Builder 组装链：

```csharp
services.AddSingleton<HandlerBase<PurchaseRequest>>(
    provider =>
    {
        var chain =
            new ChainBuilder<PurchaseRequest>()
            .AddHandler(
                provider.GetRequiredService<ManagerHandler>())
            .AddHandler(
                provider.GetRequiredService<DirectorHandler>())
            .AddHandler(
                provider.GetRequiredService<VPHandler>())
            .AddHandler(
                provider.GetRequiredService<CEOHandler>())
            .Build();

        return chain;
    });
```

消费方只需要注入一个 `HandlerBase<PurchaseRequest>`：

```csharp
var provider = services.BuildServiceProvider();

var approvalChain = provider
    .GetRequiredService<HandlerBase<PurchaseRequest>>();

approvalChain.Handle(new PurchaseRequest(
    "Cloud subscription", 3_500m, "Frank"));
// [Director] Approved: Cloud subscription ($3,500.00) by Frank
```

消费方完全不知道链里有几个处理器、顺序是什么——它只看到一个入口。这是控制反转（Inversion of Control）的直接体现：容器拥有组合权，消费方依赖抽象。

这种方式也让测试变简单。单元测试里你可以只用需要验证的处理器构建一条短链，比如只放 `DirectorHandler` 和 `VPHandler`，检查超过 $10,000 的请求是否绕过了 Director。

## 加入日志诊断

生产环境里你迟早需要排查某个请求到底是被谁处理的、经过了哪些处理器。把日志嵌入基类，所有处理器自动获得诊断能力：

```csharp
public abstract class LoggingHandlerBase<TRequest>
{
    private LoggingHandlerBase<TRequest>? _nextHandler;

    public abstract string HandlerName { get; }

    public void SetNext(
        LoggingHandlerBase<TRequest> next)
    {
        _nextHandler = next;
    }

    public void Handle(TRequest request)
    {
        Console.WriteLine(
            $"[Chain] {HandlerName} evaluating " +
            $"request: {request}");

        if (CanHandle(request))
        {
            Console.WriteLine(
                $"[Chain] {HandlerName} HANDLING " +
                $"request.");
            Process(request);
            return;
        }

        Console.WriteLine(
            $"[Chain] {HandlerName} PASSING to " +
            $"next handler.");

        if (_nextHandler is not null)
        {
            _nextHandler.Handle(request);
            return;
        }

        Console.WriteLine(
            $"[Chain] End of chain reached. " +
            $"No handler processed the request.");
        HandleUnprocessed(request);
    }

    protected abstract bool CanHandle(TRequest request);
    protected abstract void Process(TRequest request);
    protected virtual void HandleUnprocessed(
        TRequest request) { }
}
```

一个 $25,000 的请求经过完整链时，输出大概是：

```text
[Chain] Manager evaluating request: Annual license ($25,000.00) by Eve
[Chain] Manager PASSING to next handler.
[Chain] Director evaluating request: Annual license ($25,000.00) by Eve
[Chain] Director PASSING to next handler.
[Chain] VP HANDLING request.
[VP] Approved: Annual license ($25,000.00) by Eve
```

生产系统里你会把 `Console.WriteLine` 换成 `ILogger<T>`，但结构完全一样——基类在每个处理器的评估前后自动写入日志，具体处理器不需要感知诊断层的存在。

这种"在核心操作外围包裹行为"的思路和装饰器模式（Decorator Pattern）类似。区别在于这里日志逻辑直接住在基类里，而不是一个独立的包装层。如果你需要更细粒度的控制——比如给特定处理器加上耗时统计或重试逻辑——在链上叠一层装饰器是更灵活的方案。

## 常见踩坑点

**忘记判空 `_nextHandler`**：如果链尾的处理器直接调用 `_nextHandler.Handle(request)` 而没有检查 null，运行时就会抛 `NullReferenceException`。用抽象类方式可以把判空集中到一处；如果用接口方式，每个处理器都必须自己做这个守卫。

**循环引用**：处理器 A 指向 B，B 又指回 A，就形成了无限循环，直到 `StackOverflowException`。Builder 模式天然避免这个问题，因为它按线性顺序串联；手动调用 `SetNext` 时要格外注意不要形成环。

**链条太长**：一条链里 20 个处理器，排查问题会很痛苦，即使有日志也一样。考虑合并一些处理器，或者评估是否换成命令模式（Command Pattern）+ 分发表更合适。

**处理器的副作用泄漏**：如果一个处理器在判断自己不能接手之前修改了请求对象或共享状态，下游处理器收到的就是被污染的数据。处理器在"放弃处理"的路径上必须保持请求不变。只有在真正处理请求时才允许修改。

## 和 ASP.NET Core 中间件的关系

ASP.NET Core 的中间件管线本质上就是一个责任链实现：每个中间件收到请求，可以处理或者调用 `next()` 传递给下一个。区别在于 ASP.NET Core 用委托和 Builder API，而不是显式的处理器类。底层概念完全一样：一组按顺序排列的处理器，每个自行决定是接手还是传递。用类的方式实现时，你对处理器的组合和生命周期管理有更显式的控制。

## 参考

- [How to Implement Chain of Responsibility Pattern in C#: Step-by-Step Guide - Dev Leader](https://www.devleader.ca/2026/05/27/how-to-implement-chain-of-responsibility-pattern-in-c-stepbystep-guide)
- [Template Method Design Pattern in C# - Dev Leader](https://www.devleader.ca/2026/05/20/template-method-design-pattern-in-c-complete-guide-with-examples)
- [Strategy Design Pattern in C# - Dev Leader](https://www.devleader.ca/2026/03/02/strategy-design-pattern-in-c-complete-guide-with-examples)
- [Decorator Design Pattern in C# - Dev Leader](https://www.devleader.ca/2026/03/14/decorator-design-pattern-in-c-complete-guide-with-examples)
