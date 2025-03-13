---
pubDatetime: 2024-03-27
tags:
  [
    .net,
    c#,
    code,
    coding,
    csharp,
    数据库,
    dotnet,
    dotnet core,
    mongodb,
    编程,
    软件工程,
  ]
source: https://www.devleader.ca/2024/03/26/how-to-delete-documents-from-mongodb-in-c-what-you-need-to-know/
author: Nick Cosentino
title: 如何在C#中从MongoDB删除文档
description: 本文通过代码示例展示如何在C#中从MongoDB删除文档。文章涵盖了你可以用来从Mongo删除记录的不同方法的基础知识！
---

> ## 摘要
>
> 通过代码示例看看如何在C#中从MongoDB删除文档。本文涵盖了你可以用来从Mongo删除记录的不同方法的基础知识！
>
> 原文 [How To Delete Documents From MongoDB In C# – What You Need To Know](https://www.devleader.ca/2024/03/26/how-to-delete-documents-from-mongodb-in-c-what-you-need-to-know/ "How To Delete Documents From MongoDB In C# – What You Need To Know") 由 Nick Cosentino 撰写。

---

在我最近的博客中，我已经介绍了很多用C#操作MongoDB的基础知识。我强烈建议你查看[如何在C#中执行MongoDB文档的过滤](https://www.devleader.ca/2024/03/24/mongodb-filtering-in-c-beginners-guide-for-easy-filters/ "MongoDB Filtering in C# – Beginner’s Guide For Easy Filters")，因为这将是我们深入删除操作之前的垫脚石。在本文中，我将介绍如何在C#中删除MongoDB文档，代码示例将假设你已经拥有一些基本的MongoDB过滤知识。

如果你想将MongoDB集成到你的C#应用程序中，并想了解如何删除文档，请继续阅读！

---

## C#中的MongoDB基础知识

要开始使用C#中的MongoDB，你需要安装C#的MongoDB驱动程序。这个驱动程序为你的C#代码与MongoDB交互提供了高级API，安装它[就像获取NuGet包那样简单](https://www.nuget.org/packages/MongoDB.Driver "MongoDB.Driver - NuGet")。一旦你安装了驱动程序，你就可以建立与MongoDB数据库的连接，并开始操作文档。

如果你正在使用MongoDB Atlas和桌面工具Compass，它们应该会指导你如何获取你的连接字符串。然而，如果你正在使用其他托管提供商或在本地托管，你将需要按照相关说明来设置你的连接字符串，以便能够正确连接。不幸的是，我不能为每一个可能性记录这个过程🙂

在MongoDB中，数据存储在集合中，这与关系型数据库中的表类似。也许在结构上或实现方式上不同，但从概念上来看，这是最简单的理解方式。集合内的每个文档都是类似于JSON的对象，可以有不同的字段和值。在SQL数据库中，我们习惯了将数据想象为行，一行数据跨越多个列。然而，在像MongoDB这样的文档数据库中，“行”是整个文档，可以是层级数据。要从MongoDB删除文档，你需要指定集合和你想要删除的文档。

---

## 在C#中从MongoDB删除文档之前……

在这里过于急切地删除文档之前，确保我们了解过滤如何工作是很重要的。这是因为要删除正确的文档，我们需要确保我们能识别出需要删除的文档！在生产环境中，你真的需要做到这一点。如果你没有正确过滤，你可能会冒险从数据库中删除各种不正确的文档……我甚至不想想象恢复数据的乐趣。

如果你需要关于如何过滤的初学者指南，你可以阅读[这篇关于从C#过滤MongoDB记录的文章](https://www.devleader.ca/2024/03/24/mongodb-filtering-in-c-beginners-guide-for-easy-filters/ "MongoDB Filtering in C# – Beginner’s Guide For Easy Filters")。如果这对你来说不够直接或不符合你的学习风格，你可能会发现[这个关于使用C#过滤MongoDB记录的视频](https://youtu.be/2zXvDW2YFcg "Beginner's Guide to Filtering MongoDB Records in C# - YouTube")更有价值：

![YouTube播放器](../../assets/65/maxresdefault.jpg)

---

## MongoDB中的DeleteOne和DeleteOneAsync

`DeleteOne`方法删除与指定过滤条件匹配的单个文档。重要的是要注意，没有什么强制你编写一个只能匹配单个文档的过滤条件，如果你确实打算匹配多个文档，我们将在下一节中看到更多相关内容。

MongoDB C#驱动程序允许你编写一个空的过滤条件来匹配EVERY个文档，并调用`DeleteOne`。但在这种情况下，你会期望发生什么？你会用过滤条件匹配到每个文档，但方法调用仍然只会删除一个文档。它是你期望的文档吗？如果你编写了一个匹配多个的过滤条件，那么从定义上来说，可能不是。尝试特别注意这一点！

这是调用`DeleteOne`方法的一个简单示例，以及一个重要提示，即还有一个异步版本：

```csharp
var filter = Builders<MyDocument>.Filter.Eq("fieldName", "fieldValue");
var result = collection.DeleteOne(filter);

// 异步版本
// var result = await collection.DeleteOneAsync(filter);
```

返回的结果有一个匹配和删除的计数，我们可以调查。值得注意的是，在我迄今为止的所有经验中，即使你的过滤条件匹配了MANY项，如果你调用`DeleteOne`，它最多还是会显示一个最多的匹配计数。因此，这似乎不是一个可靠的方式来告诉你你的过滤条件是否会（或确实）匹配了多个项而仍然只删除了一个。

---

## MongoDB中的DeleteMany和DeleteManyAsync

很像上一个示例，`DeleteMany`和`DeleteManyAsync`的行为相似，除了它们旨在用于并支持处理多个文档的删除。`DeleteOne`不会在过滤条件匹配多个文档时抛出异常，但如果你的意图真的是要能够支持多个文档删除，这些是要使用的方法。

下面的代码示例显示了同步和异步的变体：

```csharp
var filter = Builders<MyDocument>.Filter.Gte("fieldValue", minValue);
var result = collection.DeleteOne(filter);

// 异步版本
//var result = await collection.DeleteOneAsync(filter);
```

像`DeleteOne`一样，我们必须处理的结果有匹配和删除的计数。然而，与`DeleteOne`不同的是，匹配计数将指示有多少项真正匹配了过滤条件，并且不会仅限于最多一个。再次强调，如果你需要支持过滤条件匹配多个文档，使用这些方法变体。

---

## FindOneAndDelete和FindOneAndDeleteAsync方法

`FindOneAndDelete`和异步变体与`DeleteOne`方法变体非常相似。这些方法将执行最多一个匹配过滤条件的文档的删除，但有趣的区别是返回值。返回类型为我们提供了访问与过滤条件匹配并从MongoDB中删除的文档。

这是`FindOneAndDelete`的代码示例：

```csharp
var filter = Builders<MyDocument>.Filter.Gte("fieldValue", minValue);
var result = collection.FindOneAndDelete(filter);

// 异步版本
//var result = await collection.FindOneAndDeleteAsync(filter);
```

从这个方法调用返回的结果是与过滤条件匹配并被删除的文档。如果你需要使用记录信息并希望为自己节省额外的查询和验证响应的逻辑，这可能特别有用。

---

## 常见问题解答：如何在C#中从MongoDB删除文档

### MongoDB是什么？

MongoDB是一个流行的NoSQL数据库，为管理非结构化数据提供了高性能、可扩展性和灵活性。

### 为什么在MongoDB中删除文档很重要？

删除文档允许你从MongoDB中移除不再需要的记录。这确保了你可以保持数据的最新状态，只保留持久存储中相关的数据。

### 使用C#从MongoDB删除文档有哪些不同的方法？

在C#中，你可以使用DeleteOne、DeleteMany和FindOneAndDelete等方法从MongoDB删除文档。这些方法提供了删除单个或多个文档的不同方法，并具有异步变体。

### C#中的DeleteOne方法如何工作，以从MongoDB删除文档？

DeleteOne方法允许你删除与指定过滤条件匹配的单个文档。如果有多个文档匹配过滤条件，它仍然只会删除其中一个。

### C#中的DeleteMany方法如何用于MongoDB？

DeleteMany方法用于删除与给定过滤条件匹配的多个文档。这个方法适合一次删除一批文档，如果提供的过滤条件旨在匹配多个文档，这特别有价值。
