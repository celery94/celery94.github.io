---
pubDatetime: 2026-06-16T08:25:52+08:00
title: "C# 接口隔离原则：把胖接口拆成清晰角色"
description: "接口隔离原则提醒我们，调用方不该依赖自己用不到的方法。本文用 C# 示例说明胖接口的信号、IWorker 拆分成角色接口的过程，以及它在 .NET 依赖注入、Repository 设计和测试中的实际价值。"
tags: ["C#", "SOLID", "接口设计", ".NET", "软件架构"]
slug: "interface-segregation-principle-csharp-role-interfaces"
ogImage: "../../assets/881/01-cover.png"
source: "https://www.devleader.ca/2026/06/14/interface-segregation-principle-c-focused-interfaces-that-scale"
---

接口隔离原则（Interface Segregation Principle，ISP）是 SOLID 里的 I。它的意思很朴素：调用方不该被迫依赖自己用不到的方法。

这个原则听起来简单，代码里却很容易被破坏。一个接口一开始很小，后来新需求来了，大家顺手往里面加方法。几轮之后，它变成一个什么都管的胖接口。实现类为了满足契约，只能写空方法、返回无意义默认值，或者直接抛 `NotImplementedException`。

原文用 C# 示例讲清了 ISP 的几个关键点：怎么识别胖接口、怎么拆成角色接口、拆完以后如何配合 .NET 10 依赖注入，以及 Repository 这类常见抽象该怎么处理。

## ISP 在说什么

ISP 的核心规则是：一个类不应该被迫实现不属于它职责的方法。

接口最好表达一个清晰角色，也就是某个对象“能做什么”。比如：

- `IWorker`：能执行工作。
- `IManager`：能管理团队和调整薪资。
- `IReporter`：能生成报告。

一个类可以同时扮演多个角色，但每个角色本身要足够聚焦。`Manager` 可以实现 `IWorker` 和 `IManager`，`ReportingManager` 可以再多实现一个 `IReporter`。这样类型系统说出的就是事实。

这也和单一职责原则有联系。类要有清晰职责，接口也要有清晰职责。接口一旦混进多种互不相关的能力，后面每个实现者都会被牵连。

## 胖接口的信号

原文列了一组很好用的判断信号。你看到这些情况，就该怀疑接口过宽：

- 实现类为了满足契约抛 `NotImplementedException`。
- 测一个行为，却要 mock 六个无关方法。
- 两个实现类共享同一个接口，但共同点很少。
- 接口名字很含糊，比如 `IService`、`IHelper`，里面塞了多个方向的能力。

这些问题的共同点是：接口已经无法准确描述实现者能做什么。它要求太多，实现类只好假装自己有这些能力。

## 胖 IWorker 示例

原文的例子从一个典型 `IWorker` 开始。它想描述“员工”，于是把工作、管理、报表、薪资都塞进同一个接口：

```csharp
public interface IWorker
{
    void DoWork();
    void ManageTeam();
    void GenerateReport();
    void SetSalary(decimal amount);
}
```

问题很快出现。普通开发者能写代码，但不管理团队、不生成季度报告，也不设置薪资。为了实现接口，它只能这样写：

```csharp
public class Developer : IWorker
{
    public void DoWork() => Console.WriteLine("Writing code...");

    public void ManageTeam() =>
        throw new NotImplementedException("Developers don't manage teams.");

    public void GenerateReport() =>
        throw new NotImplementedException("Developers don't generate reports.");

    public void SetSalary(decimal amount) =>
        throw new NotImplementedException("Developers don't set salaries.");
}
```

这段代码的坏味道很明显：`Developer` 的接口声明说它能管理团队、生成报告、设置薪资，运行时却告诉你这些都做不了。契约已经不可信。

## 拆成角色接口

修法是把接口按能力拆开：

```csharp
public interface IWorker
{
    void DoWork();
}

public interface IManager
{
    void ManageTeam();
    void SetSalary(decimal amount);
}

public interface IReporter
{
    void GenerateReport();
}
```

实现类只声明自己真正支持的角色：

```csharp
public sealed class Developer : IWorker
{
    public void DoWork() => Console.WriteLine("Writing code...");
}

public sealed class Manager : IWorker, IManager
{
    public void DoWork() => Console.WriteLine("Reviewing pull requests...");
    public void ManageTeam() => Console.WriteLine("Running 1:1s...");
    public void SetSalary(decimal amount) =>
        Console.WriteLine($"Setting salary: {amount:C}");
}

public sealed class ReportingManager : IWorker, IManager, IReporter
{
    public void DoWork() => Console.WriteLine("Reviewing architecture...");
    public void ManageTeam() => Console.WriteLine("Leading the team...");
    public void SetSalary(decimal amount) =>
        Console.WriteLine($"Setting salary: {amount:C}");
    public void GenerateReport() =>
        Console.WriteLine("Generating quarterly report...");
}
```

拆完之后，每个方法都有真实含义。`Developer` 不再假装能设置薪资，`ReportingManager` 也能明确表达自己同时具备工作、管理和报表三个角色。

## 角色接口思维

设计接口时，别从“这个类有哪些方法”出发，应该从“这个对象在某个场景里扮演什么角色”出发。

`Developer` 扮演工作者角色，`Manager` 扮演工作者和管理者角色，某个 `AnalyticsReporter` 可能只扮演报表角色。接口名应该描述能力，别按某个具体类来命名。

这种写法扩展起来也更稳。后来需要通知能力时，你可以新增 `INotifiable`，只让需要通知能力的类实现它。既有类型不用被迫修改，调用方也不用依赖额外方法。

.NET 标准库里也有类似例子：`IEnumerable<T>` 只表达遍历能力。它不负责排序、搜索、修改集合，只提供遍历所需的最小契约。

## 配合依赖注入

小接口和依赖注入很搭。消费者通过构造函数声明自己需要的能力，依赖关系会更诚实。

注册时可以按角色分别注册：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddScoped<IWorker, Developer>();
builder.Services.AddScoped<IManager, Manager>();
builder.Services.AddScoped<IReporter, ReportingManager>();

var app = builder.Build();
await app.RunAsync();
```

消费方只拿自己需要的接口：

```csharp
public sealed class WorkScheduler(IWorker worker)
{
    public void Schedule() => worker.DoWork();
}

public sealed class HRService(IManager manager)
{
    public void UpdateSalary(decimal newSalary) =>
        manager.SetSalary(newSalary);

    public void RunTeamMeeting() => manager.ManageTeam();
}

public sealed class AnalyticsService(
    IReporter reporter,
    ILogger<AnalyticsService> logger)
{
    public void RunReport()
    {
        logger.LogInformation("Starting report generation...");
        reporter.GenerateReport();
        logger.LogInformation("Report generation complete.");
    }
}
```

`WorkScheduler` 只知道 `IWorker`，它不需要知道管理者和报表对象存在。测试时也更轻，只 mock 一个 `DoWork` 就够了。

如果一个构造函数注入了一个胖接口，但类里只用其中两个方法，问题就被藏起来了。拆成小接口后，这种依赖膨胀会更容易被看见。

## Facade 不冲突

ISP 说内部接口要小，Facade Pattern（外观模式）说可以给外部调用方一个统一入口。它们解决的是不同层面的问题。

内部实现可以依赖多个小接口，比如 `IWorker`、`IManager`、`IReporter`。外部系统如果需要一个更简单的入口，可以由 Facade 把这些小接口组合起来。Facade 面向外部提供一个完整操作，内部仍然调用聚焦接口。

Proxy Pattern 也类似。缓存代理、日志代理、鉴权代理可以包住一个小接口，增加行为，但不应该把接口本身越包越大。

## Repository 里的 ISP

Repository 是最容易长胖的地方之一。一个“全功能”仓储接口通常会写成这样：

```csharp
public interface IRepository<T>
{
    T? GetById(int id);
    IEnumerable<T> GetAll();
    void Add(T entity);
    void Update(T entity);
    void Delete(int id);
    IEnumerable<T> Search(string query);
    void BulkInsert(IEnumerable<T> entities);
}
```

读服务可能只需要 `GetById` 和 `GetAll`，搜索功能只需要 `Search`，后台批处理只需要 `BulkInsert`。如果所有消费者都依赖完整 `IRepository<T>`，测试和实现都会背上多余方法。

可以按能力拆开：

```csharp
public interface IReadRepository<T>
{
    T? GetById(int id);
    IEnumerable<T> GetAll();
}

public interface IWriteRepository<T>
{
    void Add(T entity);
    void Update(T entity);
    void Delete(int id);
}

public interface ISearchRepository<T>
{
    IEnumerable<T> Search(string query);
}

public interface IBulkRepository<T>
{
    void BulkInsert(IEnumerable<T> entities);
}
```

这样读模型注入 `IReadRepository<T>`，搜索模块注入 `ISearchRepository<T>`，批处理模块注入 `IBulkRepository<T>`。每个类只声明自己要用的能力。

原文也提醒，这个例子用来说明 ISP，并没有要求所有团队都写通用 Repository。很多使用 EF Core 的团队会直接避开泛型仓储。这里关注的是接口边界，仓储模式本身可以按项目情况选择。

## 什么时候拆

ISP 不要求一个方法一个接口。拆太碎同样会制造噪音。

适合拆分的情况：

- 两个或更多实现类需要的方法子集不同。
- 消费者只调用接口里的一小部分方法。
- 方法代表不同能力，比如读写、管理、报表。
- 测试时需要为无关方法写很多 stub。
- 某个实现类为了满足契约抛 `NotImplementedException`。

适合保持统一的情况：

- 所有方法总是一起使用，并且属于同一个能力。
- 接口只有两三个方法，语义很完整。
- 只有一个实现者，拆分不会让设计更清楚。
- 拆完只剩大量单方法接口，阅读成本变高。

判断标准很实在：拆分要减少强迫依赖。只要没有实现类或调用方被无关方法拖住，接口稍微大一点也可以接受。

## 对测试的影响

小接口能直接改善单元测试。

假设业务类只调用 `IReporter.GenerateReport()`。如果它依赖完整 `IRepository<T>` 或胖 `IWorker`，测试时可能要配置一堆根本不会被调用的方法。接口越胖，mock 越吵，测试失败也更难看出原因。

换成角色接口后，测试替身只需要覆盖当前行为。依赖少了，测试阅读起来也更像业务意图。

## 结语

接口隔离原则的重点是诚实：类型真实表达自己能做什么，调用方真实表达自己需要什么。

当你看到 `NotImplementedException`、空实现、构造函数注入一个只用到两三个方法的大接口，基本就该检查 ISP 了。把接口按角色拆开，配合依赖注入使用，通常能让代码更好改，也让测试少一些无意义设置。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享可操作的工具教程、技术观察和项目经验。

## 参考

- [Interface Segregation Principle C#: Focused Interfaces That Scale](https://www.devleader.ca/2026/06/14/interface-segregation-principle-c-focused-interfaces-that-scale)
