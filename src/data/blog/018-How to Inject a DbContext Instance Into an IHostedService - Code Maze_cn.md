---
pubDatetime: 2024-02-26T16:33:52
tags: ["Productivity", "Tools"]
source: https://code-maze.com/efcore-inject-dbcontext-instance-into-ihostedservice/
author: Ivan Gechev
title: 如何将DbContext实例注入到IHostedService
description: 在这篇文章中，我们将探讨如何将DbContext实例注入到IHostedService，以及在这个过程中需要了解的一些重要概念。
---

# 如何将DbContext实例注入到IHostedService

> ## 摘要
>
> 在这篇文章中，我们将探讨如何将DbContext实例注入到IHostedService，以及在这个过程中需要了解的一些重要概念。
>
> 本文翻译自[How to Inject a DbContext Instance Into an IHostedService](https://code-maze.com/efcore-inject-dbcontext-instance-into-ihostedservice/)。

---

在这篇文章中，我们将看如何将DbContext实例注入到IHostedService。我们还会指出我们应注意的一些重要概念。

要下载这篇文章的源码，可以访问我们的[GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/dotnet-dependency-injection/InjectDbContextIntoIHostedService)。

让我们开始吧！

## 为什么不能直接将DbContext注入到IHostedService

我们不能直接将`DbContext`实例注入到`IHostedService`的主要原因是，`IHostedService`实例中可以注入的对象有限制。我们可以注入的两种[依赖注入生命周期](https://code-maze.com/dependency-injection-lifetimes-aspnet-core/)是*Singleton* 和 _Transient_。**这使得我们不能直接将一个`DbContext`注入，因为`AddDbContext<TContext>()`方法会将我们的上下文注册为*Scoped*服务。**

但是为什么`DbContext`实例有一个*Scoped*生命周期呢？这与工作单位模式紧密相连。根据该模式，有些情况下我们必须把一些数据库操作放在一起处理，否则就不处理。有了*Scoped*生命周期，我们确保在处理一个给定请求的操作时使用的是同一个`DbContext`实例。这也确保了来自不同请求的数据库操作在隔离中运行，而不会互相干扰。

此外，**`DbContext`实例不是线程安全的，应该永远不与线程共享。**Entity Framework通常能检测到试图并发使用`DbContext`实例的尝试，并会抛出一个类型为`InvalidOperationException`的异常。在某些情况下，它可能会遗漏并发使用尝试，这可能会导致意外行为和数据被破坏。

## 如何使用IServiceScopeFactory将DbContext实例注入到IHostedService

我们使用`IHostedService`接口运行不同的[后台任务](https://code-maze.com/aspnetcore-different-ways-to-run-background-tasks/)。在我们的例子中，我们将创建一个用一些随机猫填充我们数据库的服务：

```csharp
public class CatsSeedingService(IServiceScopeFactory scopeFactory)
    : IHostedService
{
    private static readonly int _maxAge = 15;
    private static readonly string[] _names =
        ["Whiskers", "Luna", "Simba", "Bella", "Oliver", "Shadow", "Gizmo", "Cleo", "Jasper", "Mocha"];
    public Task StopAsync(CancellationToken cancellationToken)
        => Task.CompletedTask;
}
```

首先，我们创建我们的`CatsSeedingService`类并实现`IHostedService`接口。然后，我们创建两个静态字段——一个表示猫的最大年龄，另一个是一组名字。然后，我们实现`StopAsync()`方法并返回一个已完成的任务。

**这里的关键是我们也有一个`IServiceScopeFactory`实例作为构造函数的参数。**

那么，让我们使用它并创建一个播种数据的方法：

```csharp
public async Task StartAsync(CancellationToken cancellationToken)
{
    using var scope = scopeFactory.CreateScope();
    using var context = scope.ServiceProvider.GetRequiredService<CatsDbContext>();
    await context.Database.EnsureCreatedAsync(cancellationToken);
    context.Cats.AddRange(Enumerable.Range(1, 50)
        .Select(_ => new Cat
        {
            Id = Guid.NewGuid(),
            Name = _names[Random.Shared.Next(_names.Length)],
            Age = Random.Shared.Next(1, _maxAge)
        }));
    await context.SaveChangesAsync(cancellationToken);
}
```

在`StartAsync()`方法中，我们首先在scope工厂上调用`CreateScope()`方法，获取一个`IServiceScope`实例。然后我们使用这个scope来访问它的`ServiceProvider`属性，然后调用它的`GetRequiredService<T>()`方法。在这种情况下，`T`是我们的`CatsDbContext`类。这整个过程将从DI容器中获取一个context实例。

**注意，我们也可以在我们的猫播种服务中注入一个`IServiceProvider`实例，代码将在没有任何额外变化的情况下工作。**

两个接口之间有一个微妙的区别 —— `IServiceScopeFactory`将始终有一个*Singleton*生命周期，而`IServiceProvider`的生命周期将反映它被注入的类的生命周期。在`IServiceProvider`上我们也有一个`CreateScope()`方法的版本，它会在我们调用它的`CreateScope()`方法时代我们解决`IServiceScopeFactory`。直接使用`IServiceScopeFactory`可以节省编译器的一步。

然后，我们用50只随机猫种子填充我们的数据库。

最后，我们可以注册我们的服务：

```csharp
builder.Services.AddHostedService<CatsSeedingService>();
```

## 如何使用IDbContextFactory将DbContext实例注入到IHostedService

在我们的`Program`类中，我们使用`AddDbContext<TContext>()`方法将我们的context注册到DI容器。但是还有一种我们可以注入一个`DbContext`实例的方法：

```csharp
builder.Services.AddDbContextFactory<CatsDbContext>(options => options.UseInMemoryDatabase("Cats"));
```

我们首先将 `AddDbContext<TContext>()`方法改为`AddDbContextFactory<TContext>()`方法。这将注册一个我们可以用来创建`DbContext`实例的工厂。

**我们可以在`DbContext`的范围与需要消耗它的服务的范围不对齐的情况下，使用`AddDbContextFactory<TContext>()`方法**。这样的情况是任何后台服务或Blazor应用程序。这将把一个`IDbContextFactory<TContext>`实例作为一个*Singleton*服务添加到DI容器中。为了我们的方便，编译器会在context工厂旁边以*Scoped*生命周期注册context本身。

现在我们可以继续更新我们的hosted service的构造函数：

```csharp
public class CatsSeedingService(IDbContextFactory<CatsDbContext> contextFactory)
    : IHostedService
{
    // The rest of the class is removed for brevity
}
```

在这里，我们把`IServiceScopeFactory`参数更改为`IDbContextFactory<TContext>`参数。依赖注入会成功，因为 `IDbContextFactory<TContext>`已注册为*Singleton*生命周期。

我们需要在`StartAsync()`方法中做最后一次变更：

```csharp
public async Task StartAsync(CancellationToken cancellationToken)
{
    using var context = await contextFactory.CreateDbContextAsync(cancellationToken);
    await context.Database.EnsureCreatedAsync(cancellationToken);
    for (int i = 0; i < 50; i++)
    {
        context.Cats.Add(new()
        {
            Id = Guid.NewGuid(),
            Name = _names[Random.Shared.Next(_names.Length)],
            Age = Random.Shared.Next(1, _maxAge)
        });
    }
    await context.SaveChangesAsync(cancellationToken);
}
```

要访问我们的context，我们在注入的context工厂上调用`CreateDbContextAsync()`方法。这将初始化我们的`CatsDbContext`类，然后我们可以用它来播种数据库。

## 总结

在这篇文章中，我们研究了两种将DbContext实例注入到实现IHostedService接口的类的方法。面临的挑战是由于数据库上下文的*Scoped*生命周期和在托管服务中的注入生命周期的限制。但我们可以通过使用IServiceScopeFactory或IDbContextFactory来轻易克服这些挑战。这两种不同的工厂提供了在将context的范围与后台服务的需求对齐时的灵活性，并帮助确保适当的数据隔离和线程安全。
