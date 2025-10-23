---
pubDatetime: 2024-05-30
tags: [".NET", "C#"]
source: https://code-maze.com/csharp-lookup/
author: Januarius Njoku
title: Lookup in C#
description: In C#, the Lookup class is a dictionary-like data structure that maps keys to a value or collection of values.
---

# Lookup in C#

> ## Excerpt
>
> In C#, the Lookup class is a dictionary-like data structure that maps keys to a value or collection of values.

---

当我们构建.NET应用程序时，通常会使用字典来存储键值对形式的数据。然而，字典不允许我们将多个值映射到一个键。在本文中，让我们探讨一下C#中的Lookup类，并讨论如何使用它来处理这一挑战。

要下载本文的源代码，可以访问我们的[GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/csharp-linq/LookupInCSharp)。

事不宜迟，让我们深入研究。

## 什么是C#中的Lookup？

在C#中，**`Lookup<TKey, TElement>`类是一种类字典数据结构，它将键映射到一个值或一组值**。此类实现了`ILookup<TKey, TElement>`接口，我们可以在[LINQ](https://code-maze.com/linq-csharp-basic-concepts/)命名空间中找到它。

`Lookup`类的实例维护一个内部的[`Grouping<TKey, TElement>`](https://learn.microsoft.com/en-us/dotnet/api/microsoft.visualstudio.workspace.grouping-2?view=visualstudiosdk-2022)对象数组，每个组映射到一个独特的键。所以，每当我们向lookup中添加与某个键对应的值时，它会将该值添加到键的组中。

`Lookup<TKey, TElement>`类与[`Dictionary<TKey, TValue>`](https://code-maze.com/dictionary-csharp/)类相似，我们可以使用它们将键映射到值。然而，这些类型之间存在一些差异。

在下一节中，让我们讨论这些差异并看看它们如何影响我们的应用程序。

## Lookup和Dictionary在C#中的差异

首先，**`Lookup<TKey, TElement>`实例是一个不可变的数据结构**。这意味着一旦我们创建了一个`Lookup`，我们就不能向其中添加或删除任何项目。相比之下，字典允许我们在创建后添加、删除或修改其内容。

C#中有多种不可变的集合类型，如果你想了解更多，可以查看我们的文章[不可变集合在C#中的应用](https://code-maze.com/csharp-immutable-collections/)。

其次，`Lookup<TKey, TElement>`对象允许我们将一个键映射到一个单一值或一组值。但是字典只允许我们将每个键映射到一个单一的值。

最后，**lookups没有公共构造函数**。**我们只能通过在实现[`IEnumerable<T>`](https://code-maze.com/csharp-ienumerable/)接口的集合上调用`ToLookup()`方法来创建lookup**。另一方面，当我们使用字典时，可以访问多种公共构造函数重载。

让我们继续谈一些更实际的内容，讨论如何创建`Lookup`对象。

## 如何在C#中创建Lookup

如前所述，我们只能通过调用`ToLookup()`方法来创建lookups。当我们在一个可枚举对象上调用此方法时，它会执行两个动作。

首先，它创建一个包含`Grouping<TKey, TElement>`数组字段的新`Lookup`实例。

之后，它会遍历输入可枚举对象中的所有项目。**在每次迭代中，它会为当前项目生成一个新的`Grouping<TKey, TElement>`实例，将该组映射到我们指定的键，然后将选定的值添加到该组中**。

这个材料对你有用吗？考虑订阅并获取免费的**ASP.NET Core Web API最佳实践**电子书![免费获取！](https://code-maze.com/free-ebook-aspnetcore-webapi-best-practices/)

在这个过程中，**如果遇到重复的键，则表示我们已经创建并映射了一个组。因此，我们会检索该组并将我们的值添加到其中**。

请注意，`ToLookup()`方法返回`ILookup`接口的实例。这是因为在设计API时，返回抽象类型总是比返回具体类型更好。

现在，我们的lookup输入会是一组学生列表。让我们定义一个`Student`记录：

```csharp
public record Student(string Name, string Course);
```

此记录将作为我们输入列表的类型，我们会定义字符串属性`Name`和`Course`。

很好！现在让我们继续定义我们的`Lookup<TKey, TElement>`对象。

### 从包含重复的列表中创建Lookup

首先，让我们创建我们的学生列表：

```csharp
private static readonly List<Student> _students
    = [
        new("Dan Sorla", "Accounting"),
        new("Dan Sorla", "Economics"),
        new("Luna Delgrino", "Finance"),
        new("Kate Green", "Investment Management")
      ];
```

在这里，我们定义了一组学生，其中第一个学生被输入了两次但课程不同。

这个材料对你有用吗？考虑订阅并获取免费的**ASP.NET Core Web API最佳实践**电子书![免费获取！](https://code-maze.com/free-ebook-aspnetcore-webapi-best-practices/)

接下来，让我们创建我们的lookup：

```csharp
public static ILookup<string, string> CreateLookup()
    => _students.ToLookup(s => s.Name, s => s.Course);
```

我们传递两个参数到`ToLookup()`方法并在`_students`列表上调用它。

第一个参数`s => s.Name`是一个`keySelector`函数。我们用它来指定`ToLookup()`方法应如何从输入列表中的每个项目中提取键。在这种情况下，我们指定学生的名字作为lookup中的键。然后，第二个参数`s => s.Course`是一个`elementSelector`函数。我们使用这个选择器来指定课程作为lookup中的值。

正如我们所见，通过这些选择，名字`"Dan Sorla"`的第二次出现将在我们的lookup中是一个重复的键。然而，当我们尝试将该名字添加到lookup时（这在字典中会引发异常）——`ToLookup()`方法会检索初始组并将新的`Course`字符串添加到该组。

所有操作完成后，我们会得到一个`Lookup`，其中一个键映射到多个值。

## Lookup类的操作

让我们讨论可以在lookup上执行的各种操作。这些操作包括从lookup中检索项目、在lookup中搜索键以及检索lookup中的项目数量。

如前所述，**lookups是不可变的**。因此，我们不能在lookup实例上进行添加、更新和删除操作。

基于以上内容，我们定义一个用于这些操作的输入`Lookup`实例：

```csharp
private static readonly ILookup<string, string> _lookup
    = CreateLookup();
```

这个材料对你有用吗？考虑订阅并获取免费的**ASP.NET Core Web API最佳实践**电子书![免费获取！](https://code-maze.com/free-ebook-aspnetcore-webapi-best-practices/)

在这里，我们调用上一节中定义的`CreateLookup()`方法来创建输入lookup，将学生的名字作为键，课程作为元素。

让我们将这些操作划分为不同的部分并深入讨论它们。

### 从Lookup中检索项目

让我们从从lookup中检索项目开始。

首先，让我们探索如何通过指定键从lookup中获取值：

```csharp
public static IEnumerable<string> RetrieveValuesOfAKeyFromLookup(string key)
    => _lookup[key];
```

为此，我们使用要检索的值的键作为索引器。我们会得到映射到该键的所有值作为一个集合。然而，如果没有值映射到该键，我们会得到一个空的`IEnumerable<string>`实例。

想了解更多关于索引器的信息？查看我们的文章[索引器在C#中的应用](https://code-maze.com/csharp-indexers/)。

接下来，我们讨论如何检索lookup中的所有键：

```csharp
public static List<string> RetrieveAllKeysFromLookup()
    => _lookup.Select(studentGroup => studentGroup.Key).ToList();
```

我们调用`Select()`方法并获取`Lookup`元素的`Key`。

接下来，让我们演示如何检索lookup中的所有值：

```csharp
public static IEnumerable<string> RetrieveAllValuesFromLookup()
    => _lookup.SelectMany(studentGroup => studentGroup);
```

为了检索lookup中的值，我们调用[`SelectMany()`](https://code-maze.com/csharp-difference-between-select-and-selectmany-methods-in-linq/)方法将所有`Grouping<TKey, TElement>`对象拍平并yield return加入所有元素（学生课程）。

### 在Lookup中搜索键

下一步，让我们探索如何在lookup中搜索键：

```csharp
public static bool SearchForKeyInLookup(string key)
    => _lookup.Contains(key);
```

在这里，我们将要查找的键传递给`Contains()`方法并调用它。如果指定的键存在于lookup中，该方法返回`true`。否则，它返回`false`。

### 获取Lookup的计数

最后一个操作，让我们检索lookup中的项目数量：

```csharp
public static int GetLookupCount()
    => _lookup.Count;
```

通过`Count`属性，我们可以获得lookup中键值对的总数。

好的！我们已经成功地研究了在C#中可以在lookups上执行的各种操作。现在让我们继续讨论一些适合在应用程序中使用lookups的情况。

## 在C#中应该什么时候使用Lookup？

一般而言，只要**我们想要以键值对的形式存储数据**，我们都可以使用lookups。然而对于简单的情况，建议使用字典。这是因为字典在性能上更高效，因为我们不需要为它们的键定义`Grouping<TKey, TElement>`对象。

此外，正如我们在示例中看到的，lookups在**我们想要将多个值映射到特定键时**特别有用。

这个材料对你有用吗？考虑订阅并获取免费的**ASP.NET Core Web API最佳实践**电子书![免费获取！](https://code-maze.com/free-ebook-aspnetcore-webapi-best-practices/)

此外，lookups在**我们想要根据特定属性或属性集合轻松地对可枚举对象进行分组时**将非常有用。

最后，**当我们想要以键值对的形式存储数据，并且不确定所有键是否都是唯一的时**，建议使用lookup。

## 结论

在本文中，我们探讨了C#中的Lookup类。

首先，我们解释了什么是Lookup。然后，我们讨论了如何创建Lookup实例。接下来，我们研究了从lookup中检索项目的不同方法。随后，我们探讨了如何在lookup中搜索键以及如何获取lookup中的项目数量。

最后，我们看到四种在实际应用中适合使用lookup的场景。
