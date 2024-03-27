---
pubDatetime: 2024-03-27
tags:
  [
    .net,
    c#,
    code,
    coding,
    csharp,
    databases,
    dotnet,
    dotnet core,
    mongodb,
    programming,
  ]
source: https://www.devleader.ca/2024/03/25/how-to-update-mongodb-documents-in-c-what-you-need-to-know/
author: Nick Cosentino
title: 如何在C#中更新MongoDB文档 你需要知道的
description: 查看如何在C#中更新MongoDB文档的代码示例。本文介绍了你可以用来更新记录的不同方法的基础知识。
---

> ## 摘要
>
> 查看如何在C#中更新MongoDB文档的代码示例。本文介绍了你可以用来更新记录的不同方法的基础知识。
>
> 原文 [How To Update MongoDB Documents in C# – What You Need To Know](https://www.devleader.ca/2024/03/25/how-to-update-mongodb-documents-in-c-what-you-need-to-know/ "How To Update MongoDB Documents in C# – What You Need To Know") 由 Nick Cosentino 撰写。

---

最近我一直在发布有关如何从C#操作MongoDB的内容，而这篇文章将继续沿着那个方向。如果你还没有掌握[如何在C#中对MongoDB文档进行筛选](https://www.devleader.ca/2024/03/24/mongodb-filtering-in-c-beginners-guide-for-easy-filters/ "MongoDB Filtering in C# – Beginner’s Guide For Easy Filters")，我强烈建议你在继续前先获得基本了解。在这篇文章中，我会介绍如何在C#中更新MongoDB文档，但代码示例将假设你知道如何筛选你感兴趣的内容！

如果你希望将MongoDB集成到你的C#应用程序中，并想了解如何更新文档，请继续阅读！

---

## MongoDB在C#中的基础

要开始在C#中使用MongoDB，你需要安装MongoDB的C#驱动程序。这个驱动程序为你提供了与MongoDB进行互动的高级API，而[安装NuGet包就像是获取它一样简单](https://www.nuget.org/packages/MongoDB.Driver "MongoDB.Driver - NuGet")。安装驱动程序后，你可以建立与你的MongoDB数据库的连接，并开始处理文档。

如果你正在使用像MongoDB Atlas这样的东西以及桌面工具Compass，它们应该会引导你如何获取你的连接字符串。然而，如果你使用其他托管服务提供商或本地托管，你需要遵循相关说明来设置你的连接字符串，以便你能正确连接。不幸的是，我不能为每一种可能性记录这一切 🙂

在MongoDB中，数据存储在集合中，这些集合在概念上类似于在关系数据库中的表。也许在结构或实现方式上不同，但从概念上来说，这是考虑它们的最简单方式。集合内的每个文档都是一个类似JSON的对象，可以具有不同的字段和值。在SQL数据库中，我们习惯于考虑要更新的行，并且单个行跨越表中的多个列。然而，在像MongoDB这样的文档数据库中，“行”是整个文档，可以是层次化数据。要在MongoDB中更新一个文档，你需要指定集合和你要更新的文档。

---

## 使用C#在MongoDB中更新文档

在进入更新之前，这里有一件非常重要的事情需要确保我们理解，那就是如何进行筛选。这是因为要正确更新文档，我们需要确保我们能识别出需要更新的文档是哪些！如果你的筛选条件错误，你将面临一个世界的痛苦 - 或者可能不是痛苦但在调试数据库问题时会感到非常不舒服。

如果你需要初学者指南来了解如何进行筛选，你可以阅读[这篇有关从C#筛选MongoDB记录的文章](https://www.devleader.ca/2024/03/24/mongodb-filtering-in-c-beginners-guide-for-easy-filters/ "MongoDB Filtering in C# – Beginner’s Guide For Easy Filters")。如果这不直观或不符合你的学习风格，你可能会发现[这个使用C#筛选MongoDB记录的视频](https://youtu.be/2zXvDW2YFcg "Beginner's Guide to Filtering MongoDB Records in C# - YouTube")更有价值：

![YouTube播放器](../../assets/64/maxresdefault.jpg)

---

## 在MongoDB中使用UpdateOne和UpdateOneAsync

`UpdateOne`方法更新符合指定筛选条件的单个文档。你可以使用$set操作符来更新文档内的特定字段，或者在C#中，通过在更新构建器上调用Set()方法。

这里需要特别注意的是，没有什么能强制你编写一个仅匹配单个文档的筛选条件。实际上，你可以编写一个空的筛选条件来匹配每个文档并调用`UpdateOne`。通过这样做，你会匹配每个文档，但方法调用仍然只会更新一个文档。它是你期望的文档吗？如果你编写了一个匹配多个的筛选条件，那么根据定义，可能不是。尝试特别注意这一点！

这是调用`UpdateOne`方法的一个简单示例，以及一个重要的提示，即存在异步版本：

```csharp
var filter = Builders<MyDocument>.Filter.Eq("fieldName", "fieldValue");
var update = Builders<MyDocument>.Update.Set("fieldName", "newValue");

var result = collection.UpdateOne(filter, update);

// 异步版本
// var result = await collection.UpdateOneAsync(filter, update);
```

返回的结果有一个匹配和修改的计数，我们可以调查。值得注意的是，根据我到目前为止的经验，即使你的筛选条件匹配了许多项目，如果你调用`UpdateOne`，它最多仍然只会显示一个匹配计数。因此，这似乎不是一个可靠的方法来判断你的筛选条件是否会（或确实）匹配多个项目并且仍然只更新了一个。

---

## 在MongoDB中使用UpdateMany和UpdateManyAsync

与前面的例子非常相似，`UpdateMany`和`UpdateManyAsync`几乎有\*相同的\*行为 - 除了一个你可能已经想到的微小细节之外。即许多部分。

`UpdateMany`允许你采取相同的筛选条件方法，并以你定义的更新定义方式更新所有匹配筛选条件的记录。如果你真的期望你的筛选条件能够匹配多个，我会建议使用这个 - 否则，`UpdateOne`更有意义。

下面的代码示例展示了同步和异步变体：

```csharp
var filter = Builders<MyDocument>.Filter.Gte("fieldValue", minValue);
var update = Builders<MyDocument>.Update.Set("fieldName", "newValue");

var result = collection.UpdateMany(filter, update);

// 异步版本
//var result = await collection.UpdateManyAsync(filter, update);
```

像`UpdateOne`一样，我们必须处理的结果有匹配和更新的计数。然而，与`UpdateOne`不同的是，匹配计数将指示确实有多少项目匹配了筛选条件，而不是最多限制于一个。

---

## FindOneAndUpdate和FindOneAndUpdateAsync方法

`FindOneAndUpdate`和异步变体非常类似于`UpdateOne`方法的变体。这些方法将对最多一个匹配筛选条件的文档进行更新，但有趣的区别是返回值。返回类型为我们提供了匹配筛选条件的文档在更新之前的快照。

这是`FindOneAndUpdate`的代码示例：

```csharp
var filter = Builders<MyDocument>.Filter.Gte("fieldValue", minValue);
var update = Builders<MyDocument>.Update.Set("fieldName", "newValue");

var result = collection.FindOneAndUpdate(filter, update);

// 异步版本
//var result = await collection.FindOneAndUpdateAsync(filter, update);
```

从这个方法调用返回的结果将提供匹配的文档，在被设置为“newValue”之前，`fieldName`仍将是存在的任何值。如果你想提前知道哪个文档将被更新，这在消除一次完整的数据库往返中可能会有用。

---

## 常见问题：如何在C#中更新MongoDB文档

### MongoDB是什么？

MongoDB是一种流行的NoSQL数据库，为管理非结构化数据提供高性能、可扩展性和灵活性。

### 为什么在MongoDB中更新文档很重要？

更新文档允许你修改和发展你在MongoDB中的数据，使你能够保持数据的最新状态并适应不断变化的需求。

### 使用C#在MongoDB中更新文档有哪些不同的方式？

在C#中，你可以使用如UpdateOne、UpdateMany和FindOneAndUpdate等方法来更新MongoDB中的文档。这些方法为使用不同的方法高效地更新单个或多个文档提供了不同的方法，并且有异步变体。

### C#中的UpdateOne方法是如何工作的，用于更新MongoDB文档？

UpdateOne方法允许你更新符合指定筛选条件的单个文档。你可以为文档设置新值、修改现有字段或添加新字段。

### C#中UpdateMany方法如何用于MongoDB？

UpdateMany方法用于更新匹配给定筛选条件的多个文档。此方法适用于一次性更新一批文档，同时应用一致的更改。
