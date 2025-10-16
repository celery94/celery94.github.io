---
pubDatetime: 2024-03-26
tags: [".NET", "C#"]
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
source: https://www.devleader.ca/2024/03/24/mongodb-filtering-in-c-beginners-guide-for-easy-filters/
author: Nick Cosentino
title: MongoDB在C#中的过滤 – 初学者易用过滤指南
description: 学习C#中MongoDB过滤的基础知识，用简单的代码示例！了解如何使用MongoDB FilterDefinitionBuilder以支持MongoDB中的过滤。
---

> ## 摘要
>
> 学习C#中MongoDB过滤的基础知识，用简单的代码示例！了解如何使用MongoDB FilterDefinitionBuilder以支持MongoDB中的过滤。
>
> 原文 [MongoDB Filtering in C# – Beginner’s Guide For Easy Filters](https://www.devleader.ca/2024/03/24/mongodb-filtering-in-c-beginners-guide-for-easy-filters/)

---

我正在更多地努力使自己熟悉文档型数据库在我的副项目中的使用，目前我的首选是MongoDB。实际上，我最近[写了关于如何在C#中向MongoDB插入数据的文章](https://www.devleader.ca/2024/03/22/mongodb-in-c-simplified-guide-for-inserting-data/ "MongoDB in C#: Simplified Guide For Inserting Data")，并想以这篇文章的主题继续深入：C#中的MongoDB过滤。当涉及到MongoDB时，过滤是非常重要的，不仅仅是为了能够查询记录……还因为当你想运行删除或更新时，你也需要正确地过滤！

本文关注的是使用MongoDB过滤时的初学者概念。你将看到简化的代码示例，展示如何构建过滤器，这样当查询、删除或更新时，你将完全准备好。

---

## 使用FilterDefinitionBuilders在C#中进行MongoDB过滤

在C#中使用MongoDB时，用于过滤文档的一个强大工具是MongoDB `FilterDefinitionBuilder`。`FilterDefinitionBuilder`允许我们轻松高效地构建过滤表达式，使得查询MongoDB的过程更加简单。

我个人喜欢首先获取FilterDefinitionBuilder的实例，然后直接从那里创建`FilterDefinition`。然而，如果我计划构建更复杂的过滤规则，我通常会先获取FilterDefinitionBuilder实例和一个空的`FilterDefinition`实例。

这里有一个使用MongoDB `FilterDefinitionBuilder`在MongoDB中过滤文档的示例：

```csharp
var filterBuilder = Builders<BsonDocument>.Filter;
var filter = filterBuilder.Eq("field", "value");
var results = collection.Find(filter).ToList();
```

在上面的代码中，我们获取`FilterDefinitionBuilder`实例并赋值给一个变量以供使用。从技术上讲，这次赋值是不必要的，但我发现如果我需要多次请求`FilterDefinitionBuilder`实例，这有助于清理代码。从那里，我们使用“eq”过滤器来对名为“field”的字段和一个字符串值“value”进行等值过滤。不是很有创意，但完成了任务！

如果你想跟随本文的内容，你可以[查看这个关于使用C#过滤MongoDB数据的视频](https://youtu.be/2zXvDW2YFcg "Beginner's Guide to MongoDB Filtering in C#")：

![YouTube 播放器](../../assets/60/maxresdefault.jpg)

---

## MongoDB的比较操作符

为了快速了解MongoDB中的过滤，我们需要理解比较操作符。这些操作符允许你将特定字段值与其他值或表达式进行比较。一些常用的比较操作符包括：

- $eq：匹配等于指定值的值。
- $ne：匹配不等于指定值的值。
- $gt：匹配大于指定值的值。
- $lt：匹配小于指定值的值。

`FilterDefinitionBuilder`可以访问映射到这些操作符的方法。考虑以下示例，我们想从MongoDB集合中检索年龄大于或等于18岁的所有文档：

```csharp
var ageFilter = Builders<Person>.Filter.Gte(x => x.Age, 18);
var filteredDocuments = collection.Find(ageFilter).ToList();
```

在这个示例中，我们使用`$gte`比较操作符（表示“大于或等于”）来过滤年龄字段大于或等于18岁的文档。我们使用`Builders<Person>`静态类，带有我们实体类型的类型参数，这样在构建过滤表达式时我们可以看到属性。如果我们使用`BsonDocument`作为类型，我们需要以字符串形式提供属性名称：

```csharp
var ageFilter = Builders<BsonDocument>.Filter.Gte("Age", 18);
var filteredDocuments = collection.Find(ageFilter).ToList();
```

---

## MongoDB中的范围查询和模式匹配

MongoDB还提供了允许你执行范围查询和模式匹配的操作符。两个常用的这类操作符是：

- $in: 匹配数组中的任何指定值。
- $regex: 基于指定模式使用正则表达式匹配文档。

当你想根据一系列值过滤文档或应用基于模式的过滤时，这些操作符特别有用。现在我们来看一个使用`$in`操作符执行范围查询的示例：

```csharp
var rangeFilter = Builders<Person>.Filter.In(x => x.Age, new[] { 18, 19, 20 });
var filteredDocuments = collection.Find(rangeFilter).ToList();
```

像之前一样，我们使用`Builders<Person>`静态类。在这里，我们利用`$in`操作符过滤年龄字段匹配给定数组中的任何指定值的文档。

---

## 在C#中组合MongoDB过滤器

现在我们已经看到了如何创建一些基于MongoDB提供的比较操作符的基本MongoDB过滤器，是时候考虑构建更高级的过滤器了。为此，我们可以使用AND和OR操作符……但我们有几种不同的味道：

```csharp
var filterBuilder = Builders<BsonDocument>.Filter;
var filter = filterBuilder.Empty;

filter = filterBuilder.And(
    filter,
    filterBuilder.Eq("Name", "Nick Cosentino"));
filter = filterBuilder.And(
    filter,
    filterBuilder.Gte("Age", 30));
```

在上面的代码示例中，我们从一个空过滤器开始，将其赋值给一个过滤器变量。从那里，我们使用`FilterDefinitionBuilder`上的`And()`方法组合进一个`Eq()`过滤器，然后是一个`Gte()`过滤器。请记住，这个示例展示了通过AND组合过滤器，但我们也可以将过滤器合并成OR。

另一个示例放弃了方法调用，分别使用&=和|=表示AND和OR。在我看来，这是一种更易于阅读的编写过滤器的方式：

```csharp
var filterBuilder = Builders<BsonDocument>.Filter;
var filter = filterBuilder.Empty;
filter &= filterBuilder.Eq("Name", "Nick Cosentino");
filter &= filterBuilder.Gte("Age", 30);
```

请记住，一旦你开始引入OR操作符用于你的过滤器，你将想要考虑操作顺序！

---

## 常见问题解答：C#中的MongoDB过滤

### 什么是C#中的MongoDB过滤，为什么它很重要？

C#中的MongoDB过滤指的是基于某些标准缩小MongoDB集合中的文档的过程。如果您正在开发使用MongoDB的C#应用程序，了解这一领域是有用的，以便仅检索您需要的数据，从而提高性能并减少网络带宽使用。

### MongoDB FilterDefinitionBuilder如何用于C#中的过滤？

MongoDB `FilterDefinitionBuilder`在C#中提供了一种方便的方式来构建过滤表达式。开发人员可以将多个方法串联在一起来构建复杂的过滤条件，使得定义过滤标准变得更容易。

### 使用FilterDefinitionBuilder进行MongoDB过滤有哪些优势？

MongoDB FilterDefinitionBuilder在MongoDB过滤中提供了若干好处。它提供了更直观、可读的语法，启用了类型安全的过滤表达式，并自动处理参数绑定，确保过滤操作安全高效。

### MongoDB中有哪些可用的过滤技术和操作符？

MongoDB提供了多种过滤技术和操作符。一些突出的包括比较操作符如$eq、$ne、$gt和$lt，使用$in操作符进行范围查询，以及使用$regex操作符进行模式匹配。这些操作符允许精确和灵活的文档过滤。可以构建更复杂的查询。

### 如何使用C#应用MongoDB中的过滤技术和操作符？

在C#中，开发人员可以使用MongoDB的`FilterDefinitionBuilder`来应用过滤技术。通过使用可用的操作符和方法构建过滤表达式，您可以根据具体要求有效地从MongoDB集合中过滤数据。所有这些都得到了C#的MongoDB驱动支持。
