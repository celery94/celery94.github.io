---
pubDatetime: 2024-06-20
tags: ["Productivity", "Tools"]
source: https://code-maze.com/csharp-null-statement/
author: Januarius Njoku
title: What Does the null! Statement Do? - Code Maze
description: In this article, we discuss and clearly explain the purpose of the null! statement in C# and when to use it in our applications
---

# What Does the null! Statement Do? - Code Maze

> ## Excerpt
>
> In this article, we discuss and clearly explain the purpose of the null! statement in C# and when to use it in our applications

---

在本文中，我们将讨论C#中的null!语句。首先，我们将探索它的结构和在程序中的功能。然后，我们将考察在应用中可以使用此语句的各种情况。

要下载本文的源代码，可以访问我们的[GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/csharp-intermediate-topics/TheNullBangStatementInCSharp)。

让我们开始吧。

## 一点历史 – C#中不同类型的对象

为了正确地审视`null!`语句，我们首先需要了解C#中不同类型的对象及其与null的关系。

一般来说，C#中的对象可以是值类型或引用类型。让我们简要地看看这些对象类型是什么。

### 值类型

[值类型](https://code-maze.com/csharp-value-vs-reference-types/)是直接在栈内存中保存其值的变量。这些类型继承自`System.ValueType`类，并且我们使用`struct`关键字创建它们。

**默认情况下，值类型不能为null**。然而，如果我们将它们声明为[可空值类型](https://code-maze.com/csharp-nullable-types/)，它们可以变成null。因此，每当我们创建一个非可空值类型而没有赋值给它时，它会自动默认为非null值。

C#中的值类型包括`int`、`float`、`bool`和`DateTime`。

### 引用类型

另一方面，[引用类型](https://code-maze.com/csharp-value-vs-reference-types/)是保存实际数据的引用的变量。这些引用存储在栈中，而实际数据驻留在堆中。C#中的引用类型包括字符串和类。

现在，**与不可为null的值类型不同，引用类型变量可以为null**。每当我们声明一个引用类型而没有为其赋值时，它会默认为null。

因此，访问引用类型需要谨慎以避免在应用中引发[`NullReferenceException`](https://code-maze.com/csharp-nullreferenceexception/)。

为了解决这个问题并减少由于访问null引用类型可能引发的潜在问题的数量，在C# 8中引入了可空引用类型。

## 可空引用类型

**[可空引用类型](https://code-maze.com/csharp-nullable-types/)是一组静态分析程序并跟踪我们如何在程序中使用null的特性**。这些特性帮助我们减少应用中`NullReferenceException`的发生。它们在编译时识别和警告潜在的null错误。

为了更清楚地理解可空引用类型为我们做了什么，让我们通过一些代码示例来说明。

为此，我们先看看在引入可空引用类型之前我们如何定义属性：

```csharp
public class Student
{
    public int Id { get; set; }
    public string Name { get; set; }
}
```

在这个`Student`类中，我们首先定义了一个值类型的整数属性`Id`。然后，我们声明了一个引用类型的`string`属性`Name`，编译器不会发出任何警告。

我们可以这样做是因为我们的代码是可空忽略的。这意味着我们可以自由地将null或潜在的null表达式赋给变量而不会触发编译器警告。例如，将我们的字符串属性未初始化，使其默认为null，这对于编译器来说完全可以接受。

然而，随着可空引用类型的出现，以这种方式定义类不会没有一些编译器警告。

**随着可空引用类型的引入，编译器现在将所有引用类型变量视为非可空类型**。在这种情况下，它将我们的`string`属性`Name`视为非可空类型。

要使编译器再次将它们视为可空类型，我们现在必须使用可空（？）运算符：

```csharp
public string? Name { get; set; }
```

然而，如果我们决定保持它们为非可空类型，在这种情况下，将我们的`Name`属性保留为`string`，那么编译器将要求我们为其赋值初始值。

**不赋值初始值意味着我们希望允许非可空属性具有null值，因为它会自动默认为null。这种行为将触发编译器的[`CS8618`](https://code-maze.com/csharp-resolve-non-nullable-property-must-contain-a-non-null-value-warning/) null警告。**

`CS8618`警告告诉我们我们的引用类型属性在运行时可能变为null，并且可能最终导致`NullReferenceException`被抛出，这可能会导致我们应用的行为异常。

为了解决这个问题并抑制警告，一个有效的方法是利用`null!`语句。

让我们深入探讨如何使用`null!`语句来执行这个任务。

## 使用null!语句抑制**CS8618**警告

要用`null!`语句抑制这个警告，我们只需将其赋给属性：

```csharp
public class Student
{
    public int Id { get; set; }
    public string Name { get; set; } = null!;
}
```

在我们这样做之后，来自编译器的`CS8618` null警告消失了。

很酷！但这是如何工作的呢？

### null原谅运算符

要理解`null!`语句如何执行这种抑制，首先看看它的语法。

要得到`null!`语句，我们将一元后缀运算符`!`附加到null关键字的末尾。这个`!`运算符是null原谅运算符，**它通过将可空类型标记为非可空类型来抑制编译器的null警告**。

在这种情况下，通过**将其附加到null字面值以得到`null!`，我们告诉编译器我们希望将null字面值标记为非可空值，尽管我们知道它默认是可空的**。

好的。那么将这个`null!`语句赋给属性会做什么呢？

### null!语句

**当我们将非可空引用类型属性初始化为这个非可空的null，`null!`时，我们防止引用类型默认为`null`，一个可空值**。

这样，我们遵守了编译器的规则，确保我们的非可空属性在退出构造函数之前包含非null值。通过这个赋值，我们告诉编译器我们的属性不会为null。

很棒！正如我们所见，这种技术非常有效，使用它，我们成功地抑制了`CS8618`警告。

然而，我们应该时刻记住，由于引用类型总是默认值为null，这种抑制只发生在编译时。**它在运行时没有任何影响**。因此，即使在用`null!`语句抑制了编译器的警告之后，**如果我们的引用类型属性变为null，我们仍会在运行时遇到`NullReferenceException`**。

因此，我们应该限制使用此语句，以防我们的应用在运行时发生意外异常。

牢记这一点，让我们通过概述一些可能需要我们使用`null!`语句的情况来总结。

## 可能需要我们利用null!语句的情况

首先，正如我们在示例中所看到的，**我们可以使用`null!`来抑制来自编译器的null警告**。这在我们有一个非可空引用类型且希望其保持非可空，但在构造函数中没有赋值，而是在应用运行时稍后初始化它的情况下非常有用。

此外，当我们希望在使用[EF Core](https://code-maze.com/entity-framework-core-series/)时为模型定义必须的（非null）属性时，我们也可以使用此语句。然而，我们应注意，将属性标记为[必需成员](https://code-maze.com/csharp-required-members/)是处理此任务的更优方法。

## 结论

在本文中，我们详细探讨了C#中的null!语句。

我们讨论了如何使用它，它是如何工作的，以及在应用中何时使用它。
