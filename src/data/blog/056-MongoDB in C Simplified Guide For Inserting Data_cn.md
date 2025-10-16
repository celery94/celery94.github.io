---
pubDatetime: 2024-03-24
tags: [".NET", "C#", "Database"]
source: https://www.devleader.ca/2024/03/22/mongodb-in-c-simplified-guide-for-inserting-data/
author: Nick Cosentino
title: C#中使用MongoDB-简化数据插入指南
description: 本文解释了在C#中向MongoDB插入文档的基础知识。查看InsertOne、InsertMany及其异步等效方法的代码示例。
---

> ## 摘要
>
> 本文解释了在C#中向MongoDB插入文档的基础知识。查看InsertOne、InsertMany及其异步等效方法的代码示例。
>
> 原文 [MongoDB in C# - Simplified Guide For Inserting Data](https://www.devleader.ca/2024/03/22/mongodb-in-c-simplified-guide-for-inserting-data/)

---

大部分时间开发应用程序时，我默认使用某种形式的SQL。无论是使用SQlite的简单应用程序，还是计划使用MySQL进行扩展的更为健壮的应用程序，不可避免地，这些都是SQL的某种变体。然而，在过去几年开始新项目时，我一直试图确保我有使用文档数据库的经验，并花了更多时间在C#中使用MongoDB。

在本文中，我将指导你了解一些基础知识，以便能够使用C#中的MongoDB插入数据。我们将保持轻松和简洁，所以让我们深入MongoDB在C#中的简要概述，然后是一些C#的代码示例！

---

## C#中MongoDB的概述

MongoDB是一个广泛使用的NoSQL数据库，为数据存储提供了灵活和可扩展的解决方案。MongoDB的一个关键优势是它的文档导向特性，所以不像传统关系型数据库中使用具有固定架构的表，MongoDB在类似JSON的文档集合中存储数据。这可以允许更灵活和动态的数据模型，特别是在数据结构可能变化的场景中。

在C#中，你可以无缝地将MongoDB集成到你的应用程序中，因为MongoDB为C#提供了一个原生驱动程序。这简化了与数据库交互的过程，并为C#开发者提供了一个舒适的开发体验。

嗯，大部分是这样。如果你习惯使用SQL连接、SQL命令对象和`DataReader`类来访问你的数据，那么就会有点更复杂。但这是来自于一个更喜欢在数据访问层中编写原始SQL查询的人的角度。如果你没有这种偏见，那么使用他们的API，尤其是对过滤的操作，可能会感觉相当直观。

如果你来自关系型数据库背景，你会想要记住的一件大事是理解关系型和文档数据库之间的主要区别。在前者中，我们通常在表中对数据进行非规范化操作，而在后者中，我们将数据写成一个文档，我们希望在不需要连接的情况下读回。这些类型的数据库并不是设计来像我们在关系型数据库中那样连接数据的，所以这是你需要注意的事情！

### 与C#中的MongoDB相关内容一起跟随学习

我总是尽量确保我能提供多种形式的内容。下面你会找到一个[YouTube视频，通过例子讲解在C#中使用MongoDB插入记录](https://youtu.be/0fB9qg-oR04 "MongoDB in C# - Inserting Records"):

当然，如果你更愿意玩一些工作代码（除了确保你有自己的数据库外），你可以在我的[Dev Leader GitHub仓库这里找到示例代码](https://github.com/ncosentino/DevLeader/tree/master/MongoDBExamples/MongoDBExamples.InsertRecords "MongoDB in C# - Inserting Records on GitHub")。你应该能够克隆它，正确设置你的连接字符串，根据需要更改你的数据库和集合名称，然后开始！

---

## 向MongoDB中插入文档

在本节中，我将解释如何使用C#向MongoDB插入文档。我们将查看使用`InsertOne`和`InsertMany`方法的代码示例。我们将看到这些方法的同步和异步形式！记住，你需要确保你的项目中安装了“MongoDB.Driver”NuGet包，以下的代码示例才能工作。

### 使用InsertOne和InsertOneAsync方法

要同步将单个文档插入MongoDB集合，请使用`InsertOne`方法。这个方法很直接，并且会立即执行，阻塞当前线程直到操作完成。下面是一个基本示例：

```csharp
using MongoDB.Bson;
using MongoDB.Driver;

// 连接到MongoDB实例
var client = new MongoClient("mongodb://localhost:27017");

// 选择数据库
var database = client.GetDatabase("testDatabase");

// 选择集合（有点像SQL“表”）
var collection = database.GetCollection<BsonDocument>("myCollection");

var document = new BsonDocument
{
    { "name", "John" },
    { "age", 30 }
};

// 将文档插入集合
collection.InsertOne(document);
```

在本示例中：

- 我们首先建立与MongoDB实例的连接，并选择我们的数据库和集合。
- 然后，我们创建一个`BsonDocument`对象，表示我们想要插入的文档。
- 最后，我们在我们的集合对象上调用`InsertOne`，传入文档。这将文档插入到指定的集合中。

对于异步操作，你可以使用`InsertOneAsync`。这个方法在需要非阻塞操作的应用程序中特别有用，例如Web应用程序或服务，以保持响应性。这是如何使用它的方式：

```csharp
using MongoDB.Bson;
using MongoDB.Driver;
using System.Threading.Tasks;

// 和之前的示例一样
var client = new MongoClient("mongodb://localhost:27017");
var database = client.GetDatabase("testDatabase");
var collection = database.GetCollection<BsonDocument>("myCollection");

var document = new BsonDocument
{
    { "name", "Jane" },
    { "age", 28 }
};

// 异步插入文档
await collection.InsertOneAsync(document, cancellationToken: CancellationToken.None);
```

在这个异步示例中：

- 设置与同步版本相似，但我们使用`await`与`InsertOneAsync`一起。这告诉程序继续执行不依赖插入操作完成的其他工作。
- 注意，你可以在这里传入一个取消令牌，这是异步代码的一个最佳实践

注意，如果插入操作失败，`InsertOne`和`InsertOneAsync`方法会抛出异常，所以你应该使用try-catch块来优雅地处理潜在的错误。

### 使用InsertMany和InsertManyAsync方法

`InsertMany`方法同步地将一个文档对象列表插入指定的集合。当你有多个准备好存储的文档并希望在单个调用中执行操作时，这很有用。这是一个示例：

```csharp
using MongoDB.Bson;
using MongoDB.Driver;
using System.Threading.Tasks;

// 和之前的示例一样
var client = new MongoClient("mongodb://localhost:27017");
var database = client.GetDatabase("testDatabase");
var collection = database.GetCollection<BsonDocument>("myCollection");

var documents = new List<BsonDocument>
{
    new BsonDocument("name", "John").Add("age", 30),
    new BsonDocument("name", "Jane").Add("age", 25),
    new BsonDocument("name", "Doe").Add("age", 28)
};

collection.InsertMany(documents);
```

在这个示例中，我们首先获取到我们的集合的引用。然后，我们[创建一个列表](https://www.devleader.ca/2024/03/20/mudblazor-list-items-how-to-create-awesome-blazor-list-views/)的`BsonDocument`对象，每个都代表一个要插入的文档。最后，我们使用我们的文档列表调用`InsertMany`。这个方法将在一次操作中将列表中的所有文档插入到MongoDB集合中。

对于异步操作，特别是在响应性至关重要或处理I/O绑定任务时，你可以使用`InsertManyAsync`方法。这个方法的工作方式与`InsertMany`类似，但它以异步的方式执行操作。这是一个示例：

```csharp
using MongoDB.Bson;
using MongoDB.Driver;
using System.Threading.Tasks;

// 和之前的示例一样
var client = new MongoClient("mongodb://localhost:27017");
var database = client.GetDatabase("testDatabase");
var collection = database.GetCollection<BsonDocument>("myCollection");

var documents = new List<BsonDocument>
{
    new BsonDocument("name", "John").Add("age", 30),
    new BsonDocument("name", "Jane").Add("age", 25),
    new BsonDocument("name", "Doe").Add("age", 28)
};

await collection.InsertManyAsync(documents);
```

在这个异步版本中，我们在调用`InsertManyAsync`之前使用`await`，确保在继续执行下一行代码前操作完成。这在Web应用程序或服务中特别重要，其中阻塞主线程可能导致性能不佳或用户体验差。

---

## 有效插入数据的最佳实践

本文侧重于使用C#向MongoDB插入数据的API使用，但我想触及一些其他点。为了提高MongoDB数据插入的效率，你可以考虑以下最佳实践：

1. 批量插入：与每次插入一个文档相比，你可以将多个文档批量组合在一起，并使用InsertMany在单个操作中插入。这减少了多次往返数据库的开销。
2. 使用索引：索引可以显著提高插入性能，通过加快搜索插入新文档的正确位置。确保你在常用于插入的字段上定义了适当的索引。
3. 考虑分片：如果你有大量数据要插入，分片可以将数据分布在多个服务器上，提高插入性能。
4. 写入关注：MongoDB中的默认写入关注是Acknowledged，它等待服务器的确认。如果你正在进行批量插入且不需要立即确认，你可以设置较低的写入关注以提高性能。
5. 考虑异步操作：异步操作可以通过允许多个插入操作同时执行来提高应用程序的响应性。

除了前面提到的这些API的异步版本外，我在本文中不会更详细地讨论这些其他主题。请继续关注即将发布的文章，我将在其中涵盖这些主题以及更新MongoDB文档和删除记录等其他功能！

---

## 常见问题解答：C#中的MongoDB

### MongoDB是什么，我如何在C#中使用MongoDB？

MongoDB是一个NoSQL数据库，可以与C#一起使用来存储和管理数据。它提供了灵活的架构、可扩展的性能和高可用性。在C#中，可以使用一个驱动程序来访问MongoDB，该驱动程序提供了一个易于使用的API与数据库交互。

### 使用MongoDB进行数据存储有什么好处？

MongoDB为数据存储提供了几个好处，包括水平可扩展性、自动分片和灵活的文档结构。它允许更快的开发周期，因为数据可以以其自然形式存储，无需复杂的映射或迁移。此外，MongoDB提供了对索引、复制和负载平衡的支持，确保数据库的高可用性和性能。

### 我如何在C#中高效地向MongoDB插入文档？

要使用C#高效地向MongoDB插入文档，你可以使用像‘InsertOne’和‘InsertMany’这样的方法。这些方法允许你分别插入单个或多个文档。建议批量插入以减少网络开销。此外，在集合上创建适当的索引可以提高插入性能。根据你的应用程序的具体需求优化插入过程很重要。
