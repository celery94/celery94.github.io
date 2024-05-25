---
pubDatetime: 2024-05-25
tags: []
source: https://code-maze.com/dotnet-introduction-to-stronglytypedid-package/
author: Caleb Okechukwu
title: 介绍 .NET 中的 StronglyTypedId 包
description: 让我们来看看 StronglyTypedId 库，它如何帮助在 .NET 项目中增强类型安全性和代码可读性。
---

# 介绍 .NET 中的 StronglyTypedId 包

> ## 摘要
>
> 让我们来看看 StronglyTypedId 库，它如何帮助在 .NET 项目中增强类型安全性和代码可读性。
>
> 原文 [Introduction to the StronglyTypedId Package in .NET](https://code-maze.com/dotnet-introduction-to-stronglytypedid-package/)

---

在本文中，我们将了解 StronglyTypedId NuGet 包，它通过为实体生成强类型 ID 来帮助我们增强 .NET 项目中的类型安全性和代码可读性。

要下载本文的源代码，你可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/dotnet-client-libraries/StronglyTypedIDPackage)。

让我们开始吧。

## 使用 StronglyTypedId 的好处

在我们了解如何安装和使用 StronglyTypedId NuGet 包之前，先来考虑一下为什么我们需要它。

我们通常使用 `string`、`integer` 或 `GUID` 之类的数据类型来表示应用程序中的唯一标识符。**尽管这些解决方案通常是有效的，但它们可能导致 primitive obsession 并引发程序中的重大问题**。

**使用原始数据类型作为唯一标识符极易被误用，并且在代码中缺乏上下文**。想象一下错误地将一个 `UserId` 输入到需要 `CommentId` 的地方。这可能会导致运行时错误，这在开发过程中很难识别。此外，尽管 `GUIDs` 是唯一的，但它们在代码中没有内在意义。

相比之下，StronglyTypedId 是一个自定义类型，它作为实体的唯一标识符。**它通过为每种标识符类型定义单独的类来确保类型安全，防止无意的 ID 混淆，并减少运行时问题**。除了防止无意的 ID 混淆，它还清晰地指示了它们在代码中的作用。这使得代码更加自我文档化和易于理解。

## 安装 StronglyTypedId

要开始使用该包，我们首先需要安装它：

```bash
dotnet add package StronglyTypedId --version 1.0.0-beta08
```

或者，我们可以使用 Visual Studio 的 NuGet 包管理器来安装该包。截至本文写作时，最新的稳定版本是 `1.0.0-beta08`。

## 使用 StronglyTypedId

稍后我们将看到如何使用 StronglyTypedId 包。但首先，让我们看一个使用原始对象作为程序中唯一标识符的例子，这可能导致的问题：

```csharp
public class User
{
    public Guid Id { get; set; }
    public string? Name { get; set; }
    public List<Comment>? Comments { get; set; }
}
public class Comment
{
    public Guid Id { get; set; }
    public string? Text { get; set; }
    public Guid UserId { get; set; }
    public User? User { get; set; }
}
```

这里，我们使用 `Guid` 原语为基本的 `User` 和 `Comment` 实体指定标识符。这是一种常见的做法。

现在让我们创建一个基本方法来检索单个用户的评论：

```csharp
public class CommentService
{
    private static List<Comment> _comments =
    [
        new ()
        {
            Id = Guid.Parse("5c6a8f59-02c1-4f5b-bc85-bfea9ed3a6e4"),
            Text = "First comment made by user.",
            UserId = Guid.Parse("3b3b1a5d-6cd1-42f2-9331-fc6f716e9a2c")
        }
    ];
    public Comment GetSingleUserComment(Guid commentId, Guid userId)
    {
        var comment = _comments
            .FirstOrDefault(comment => comment.Id == userId
                            && comment.UserId == userId);
        return comment ?? throw new NullReferenceException();
    }
}
```

注意我们 `GetSingleUserComment()` 方法中的代码行，以及 `userId` 是如何被传递而不是 `commentId`。这是故意做的，以检查程序在编译期间是否会抛出错误。

不幸的是，这段代码成功编译，并且在运行时没有抛出任何错误，这不是我们希望在程序中看到的行为。

现在让我们看看如何解决这个问题，使用 StronglyTypedId 包来修改我们的 `User` 和 `Comment` 类：

```csharp
[StronglyTypedId]
public partial struct UserId { }
public class User
{
    public UserId Id { get; set; }
    public string? Name { get; set; }
    public List<Comment>? Comments { get; set; }
}
[StronglyTypedId]
public partial struct CommentId { }
public class Comment
{
    public CommentId Id { get; set; }
    public string? Text { get; set; }
    public UserId UserId { get; set; }
    public User? User { get; set; }
}
```

在这里，我们为 `User` 和 `Comment` 实体的 `Id` 属性创建了一个 `struct`，并使用 `[StronglyTypedId]` 属性装饰它们，以确保我们的 ID 是唯一的。

使用我们的强类型 ID，现在让我们修改 `GetSingleUserComment()` 方法：

```csharp
public class CommentService
{
    private static List<Comment> _comments =
    [
        new ()
        {
            Id = new CommentId(),
            Text = "First comment made by user.",
            UserId = new UserId()
        }
    ];
    public Comment GetSingleUserComment(CommentId commentId, UserId userId)
    {
        var comment = _comments
            .FirstOrDefault(comment => comment.Id == userId
                            && comment.UserId == userId);
        return comment ?? throw new NullReferenceException();
    }
}
```

通过将我们的唯一 ID 作为类型分配给 `commentId` 和 `userId` 参数，如果我们混淆了 ID，编辑器现在会抛出一个错误，导致编译错误：

> 操作符`==`不能应用于 `Commentld` 和 `Userld` 类型的操作数

这是因为**package 源代码生成器生成了一个方法，该方法比较 ID 的值而不是引用**。这有助于提供类型安全性，并增加代码可读性，而不是仅使用原始数据类型。

## StronglyTypedId 的高级功能

虽然基本用法展示了核心功能，但 StronglyTypedId 包提供了额外的功能，增强了 ID 的灵活性和定制性。让我们看看其中的一些功能。

### 使用不同类型作为 ID 的后备字段

该包的主要功能之一是能够使用不同的数据类型作为 ID 的后备字段。默认情况下，**该包使用 `Guid` 类型作为底层标识符，但也允许我们选择最合适的数据类型来存储 ID 值**。我们可以使用 `string`、`long` 和 `int` 类型来指定后备字段。

以下是如何修改之前的 `User` 实体以使用 `string` 作为后备字段：

```csharp
[StronglyTypedId(Template.String)]
public partial struct UserId { }
```

通过在构造函数中给出 `Template` 枚举中的一个值，我们指定 `UserId` 的类型应该是 `string`，而不是默认的 `Guid` 类型。这允许我们完全自主地表示我们的 ID。

内置的后备字段支持包括 `int`、`long`、`Guid` 和我们刚刚看到的 `string` 类型。我们还可以通过安装 StronglyTypedId 模板包，从[其他人构建的模板](https://github.com/andrewlock/StronglyTypedId/tree/master/src/StronglyTypedIds.Templates)中受益：

```bash
dotnet add package StronglyTypedId.Templates --version 1.0.0-beta08
```

安装此包将允许我们引用随附的所有模板。

### 全局更改默认后备字段

如果我们决定项目中使用 `[StronglyTypedId]` 属性的每个 ID 的后备字段类型相同，可以配置项目：

```csharp
[assembly: StronglyTypedIdDefaults(Template.String)]
[StronglyTypedId]
public partial struct UserId { }
[StronglyTypedId]
public partial struct CommentId { }
```

在这里，我们一次性使用 `StronglyTypedIdDefaults` 汇编属性，将每个 ID 的默认后备字段更改为 `string` 类型。

我们可以通过为任何 `StronglyTypedId` 属性提供后备字段类型来覆盖全局默认值，正如我们之前所做的那样。

## 结论

这篇文章概述了 StronglyTypedId NuGet 包。我们首先讨论了使用原始数据类型作为实体标识符的一些困难。然后介绍了如何使用该包，并为单个 ID 和全局定义后备字段类型。

要了解更多关于该包的功能，请访问 [StronglyTypedId GitHub 仓库](https://github.com/andrewlock/StronglyTypedId#installing)。
