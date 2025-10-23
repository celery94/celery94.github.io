---
pubDatetime: 2024-05-16
tags: [".NET", "Architecture"]
source: https://www.milanjovanovic.tech/blog/functional-error-handling-in-dotnet-with-the-result-pattern?utm_source=Twitter&utm_medium=social&utm_campaign=13.05.2024
author: Milan Jovanović
title: 用Result Pattern在.NET中进行功能性错误处理
description: 你应该如何处理代码中的错误呢？这个问题引发了很多讨论，我想分享我的观点。
---

# 用Result Pattern在.NET中进行功能性错误处理

> ## 摘要
>
> 你应该如何处理代码中的错误呢？这个问题引发了很多讨论，我想分享我的观点。
> 有一种观点建议使用异常进行流控。但是，这并不是一个好的做法，因为它使得代码更难理解。调用者需要知道具体的实现细节以及需要处理哪些异常。
> 异常是为了处理异常情况。
> 今天，我想向你展示如何使用Result Pattern来实现错误处理。
> 这是一种功能性的错误处理方式，可以让你的代码变得更具表现力。
>
> 原文 [Functional Error Handling in .NET With the Result Pattern](https://www.milanjovanovic.tech/blog/functional-error-handling-in-dotnet-with-the-result-pattern?utm_source=Twitter&utm_medium=social&utm_campaign=13.05.2024) 由 [Milan Jovanović](https://www.milanjovanovic.tech/) 发表。

---

你应该如何处理你代码中的错误呢？

这个问题已经引起了很多讨论，我想分享我的观点。

有一种观点建议使用异常进行流控制。但这并不是一个好的方法，因为它使得你的代码更难以推导。调用者需要知道实现细节以及需要处理哪些异常。

异常应该用于处理异常情况。

今天，我想展示如何使用**Result Pattern**来实现错误处理。

这是一种功能性错误处理方式，可以让你的代码变得更具表现力。

## 使用异常进行流控制

使用异常进行流控制是一种实现**快速失败**原则的方法。

一旦你在代码中遇到错误，就会抛出异常 —— 这实际上终止了方法的执行，并让调用者负责处理异常。

问题在于调用者必须知道需要处理哪些异常。仅从方法签名是无法明确知道的。

另一种常见的用法是抛出验证错误的异常。

下面是在`FollowerService`中的一个例子：

```csharp
public sealed class FollowerService
{
    private readonly IFollowerRepository _followerRepository;

    public FollowerService(IFollowerRepository followerRepository)
    {
        _followerRepository = followerRepository;
    }

    public async Task StartFollowingAsync(
        User user,
        User followed,
        DateTime createdOnUtc,
        CancellationToken cancellationToken = default)
    {
        if (user.Id == followed.Id)
        {
            throw new DomainException("Can't follow yourself");
        }

        if (!followed.HasPublicProfile)
        {
            throw new DomainException("Can't follow non-public profile");
        }

        if (await _followerRepository.IsAlreadyFollowingAsync(
                user.Id,
                followed.Id,
                cancellationToken))
        {
            throw new DomainException("Already following");
        }

        var follower = Follower.Create(user.Id, followed.Id, createdOnUtc);

        _followerRepository.Insert(follower);
    }
}
```

## 对于异常情况使用异常

我遵循的一个经验法则是，在异常情况下使用异常。既然你已经预期可能会有错误，为什么不明确地表示出来呢？

你可以将所有应用程序错误分为两组：

- 你知道如何处理的错误
- 你不知道如何处理的错误

对于你不知道如何处理的错误，异常是个非常好的解决方案。你应在可能的最低层次上捕获并处理它们。

那么你知道如何处理的错误呢？

你可以用**Result Pattern**功能性地处理它们。这种方式明确且清晰地表明了方法可以失败的意图。缺点是调用者必须手动检查操作是否失败。

## 用Result Pattern表达错误

你首先需要的是一个`Error`类来表示应用程序错误。

- `Code` - 错误在应用中的唯一名称
- `Description` - 包含关于错误的开发者友好的详细信息

```csharp
public sealed record Error(string Code, string Description)
{
    public static readonly Error None = new(string.Empty, string.Empty);
}
```

然后，你可以使用`Error`来实现`Result`类以描述失败。这个实现非常基础，你可以添加更多的功能。在大多数情况下，你也需要一个泛型`Result<T>`类，它将一个值封装在内部。

下面是`Result`类的样子：

```csharp
public class Result
{
    private Result(bool isSuccess, Error error)
    {
        if (isSuccess && error != Error.None ||
            !isSuccess && error == Error.None)
        {
            throw new ArgumentException("Invalid error", nameof(error));
        }

        IsSuccess = isSuccess;
        Error = error;
    }

    public bool IsSuccess { get; }

    public bool IsFailure => !IsSuccess;

    public Error Error { get; }

    public static Result Success() => new(true, Error.None);

    public static Result Failure(Error error) => new(false, error);
}
```

创建`Result`实例的唯一方法是通过使用静态方法：

- `Success` - 创建一个成功的结果
- `Failure` - 创建一个带有指定`Error`的失败结果

如果你想避免构造你自己的`Result`类，可以看一下[FluentResults](https://github.com/altmann/FluentResults)这个库。

## 应用Result Pattern

现在我们有了`Result`类，让我们看看如何在实践中应用它。

这里是重构过的`FollowerService`版本。注意以下几点：

- 不再抛出异常
- `Result`返回类型是显式的
- 显式的返回方法可能会出现哪些错误

使用**Result Pattern**进行错误处理的另一个好处是，它更容易进行测试。

```csharp
public sealed class FollowerService
{
    private readonly IFollowerRepository _followerRepository;

    public FollowerService(IFollowerRepository followerRepository)
    {
        _followerRepository = followerRepository;
    }

    public async Task<Result> StartFollowingAsync(
        User user,
        User followed,
        DateTime utcNow,
        CancellationToken cancellationToken = default)
    {
        if (user.Id == followed.Id)
        {
            return Result.Failure(FollowerErrors.SameUser);
        }

        if (!followed.HasPublicProfile)
        {
            return Result.Failure(FollowerErrors.NonPublicProfile);
        }

        if (await _followerRepository.IsAlreadyFollowingAsync(
                user.Id,
                followed.Id,
                cancellationToken))
        {
            return Result.Failure(FollowerErrors.AlreadyFollowing);
        }

        var follower = Follower.Create(user.Id, followed.Id, utcNow);

        _followerRepository.Insert(follower);

        return Result.Success();
    }
}
```

## 文档化应用程序错误

你可以使用`Error`类来记录应用程序中可能出现的所有错误。

一种方法是创建一个名为`Errors`的静态类。它会包含具体错误的嵌套类。使用方式看起来像 `Errors.Followers.NonPublicProfile`。

然而，我喜欢的做法是创建一个包含错误的具体类。

下面是`FollowerErrors`类，它记录了`Follower`实体可能出现的错误：

```csharp
public static class FollowerErrors
{
    public static readonly Error SameUser = new Error(
        "Followers.SameUser", "Can't follow yourself");

    public static readonly Error NonPublicProfile = new Error(
        "Followers.NonPublicProfile", "Can't follow non-public profiles");

    public static readonly Error AlreadyFollowing = new Error(
        "Followers.AlreadyFollowing", "Already following");
}
```

除了静态字段，你也可以使用返回错误的静态方法。你会用具体的参数调用此方法以获取`Error`实例。

```csharp
public static class FollowerErrors
{
    public static Error NotFound(Guid id) => new Error(
        "Followers.NotFound", $"The follower with Id '{id}' was not found");
}
```

## 将结果转化为API响应

`Result`对象最终会到达ASP.NET Core的 简易API（或控制器）端点。简易API返回一个`IResult`响应，控制器返回一个`IActionResult`响应。无论如何，你都必须将`Result`实例转化为有效的API响应。

最直接的方法是检查`Result`的状态并返回HTTP响应。下面是一个检查`Result.IsFailure`标志的例子：

```csharp
app.MapPost(
    "users/{userId}/follow/{followedId}",
    (Guid userId, Guid followedId, FollowerService followerService) =>
    {
        var result = await followerService.StartFollowingAsync(
            userId,
            followedId,
            DateTime.UtcNow);

        if (result.IsFailure)
        {
            return Results.BadRequest(result.Error);
        }

        return Results.NoContent();
    });
```

但这是一个非常好的机会采用更加功能性的方法。你可以实现`Match`扩展方法，为每个`Result`状态提供回调。`Match`方法会执行相应的回调并返回结果。

下面是`Match`的实现：

```csharp
public static class ResultExtensions
{
    public static T Match(
        this Result result,
        Func<T> onSuccess,
        Func<Error, T> onFailure)
    {
        return result.IsSuccess ? onSuccess() : onFailure(result.Error);
    }
}
```

这是你如何在简易API端点中使用`Match`方法的例子：

```csharp
app.MapPost(
    "users/{userId}/follow/{followedId}",
    (Guid userId, Guid followedId, FollowerService followerService) =>
    {
        var result = await followerService.StartFollowingAsync(
            userId,
            followedId,
            DateTime.UtcNow);

        return result.Match(
            onSuccess: () => Results.NoContent(),
            onFailure: error => Results.BadRequest(error));
    });
```

看起来更简洁，不是吗？

## 总结

如果你从这篇文章中只带走一件事，那就应该是：异常是用于处理异常情况。而且，你只应该对你不知道如何处理的错误使用异常。在所有其他情况下，使用**Result Pattern**更明确地表达错误会更有价值。

使用`Result`类允许你：

- 表明一个方法可能会失败的意图
- 封装一个应用程序错误
- 提供一种处理错误的功能性方法

另外，你可以用`Error`类记录所有应用程序的错误。这对开发者了解需要处理哪些错误很有帮助。

你甚至可以将其转化为真正的*documentation*。比如，我写了一个简单的程序，扫描项目中所有的`Error`字段。然后将其转化为表格格式，并上传到一个Confluence页面。

因此，我鼓励你试一试**Result Pattern**，看看它能如何改进你的代码。
