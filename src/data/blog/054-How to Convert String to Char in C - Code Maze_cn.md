---
pubDatetime: 2024-03-21
tags: [".NET", "C#", "Performance"]
source: https://code-maze.com/csharp-how-to-convert-string-to-char/
author: Samuel Lawal
title: 如何在C#中将String转换为Char
description: 在C#开发中，处理字符串和字符是基本工作。本文探讨了如何将字符串转换为char数组。
---

> ## 摘要
>
> 在C#开发中，处理字符串和字符是基本工作。本文探讨了如何将字符串转换为char数组。
>
> 原文链接：[How to Convert String to Char in C#](https://code-maze.com/csharp-how-to-convert-string-to-char/)

---

在C#开发中，处理字符串和字符是基本工作。本文探讨了如何将字符串转换为char数组。文章还扩展到将字符串数组转换为字符数组的方法。

下载本文的源代码，您可以访问我们的[GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/strings-csharp/ConvertingStringToCharArrayInCSharp)。

让我们开始。

## 将单字符字符串转换为Char

如果我们有一个单字符字符串，我们可以将字符串转换为char：

```csharp
public static char ConvertSingleCharacterStringToChar(string inputString)
{
    return char.Parse(inputString);
}
```

这里，我们的方法利用了`char.Parse()`。它接受一个字符串作为输入并返回其第一个字符，如果字符串确切地有一个字符。注意，如果输入字符串的长度大于1，`char.Parse()`会抛出异常。

## 将字符串转换为Char数组

让我们看一个示例，展示如何使用一个简单的方法将包含多个字符的字符串转换为char数组：

```csharp
public static char[] ConvertStringToCharArray(string inputString)
{
    return inputString.ToCharArray();
}
```

`ConvertStringToCharArray()`方法接受一个字符串输入，然后利用`ToCharArray()`方法将输入字符串转换为一个字符数组。`ToCharArray()`方法返回一个新数组，包含字符串的字符。

让我们测试一下：

```csharp
string myString = "Hello World!";
char[] charArray = StringHelper.ConvertStringToCharArray(myString);
```

我们调用该方法，向其传递一个字符串，它返回一个字符数组，包含字符串的单个字符。然后，`charArray`结果可以用于进一步处理或操作。

这种方法是将字符串转换为字符数组的便利方式，它利用了C#的字符串类提供的内置功能。

## 使用ReadOnlySpan作为Char的替代方案

`ReadOnlySpan<T>`是C#中的一个类型，它提供对一块内存的只读视图，无需创建新数组或复制数据。**它在处理性能关键场景或希望在不生成数组开销的情况下处理数据时特别有用。**

要了解更多关于`ReadOnlySpan`类型的信息，请查看我们的文章[此处](https://code-maze.com/csharp-span-to-improve-application-performance/)。

在处理字符数据的上下文中，当我们需要处理字符序列而不修改底层数据时，可以将`ReadOnlySpan<char>`视为`char[]`的替代方案。

让我们看看如何实现这一点：

```csharp
public static ReadOnlySpan<char> ConvertStringToCharArrayUsingReadOnlySpan(string inputString)
{
    return inputString.AsSpan();
}
```

`ConvertStringToCharArrayUsingReadOnlySpan()`方法将字符串转换为字符的只读范围。它利用`AsSpan()`方法创建输入字符串字符的只读视图。生成的`ReadOnlySpan<char>`允许对字符串的底层字符数据进行有效且只读的访问，无需分配新数组。

现在，我们调用该方法：

```csharp
ReadOnlySpan<char> charArrayReadOnlySpan = StringHelper.ConvertStringToCharArrayUsingReadOnlySpan(myString);
```

### ToCharArray与AsSpan的比较

- `ToCharArray()`在堆上创建一个新的`char[]`，而`AsSpan()`仅创建现有数据上的`ReadOnlySpan<char>`视图
- 结果`char[]`是可变的，意味着我们可以修改数组的内容，而`ReadOnlySpan<char>`是只读的，因此我们不能
- `ToCharArray()`涉及内存分配和复制，而`AsSpan()`通常更具性能优势，因为它不需要分配或复制

## 使用循环将字符串数组转换为Char数组

现在，让我们更进一步，探讨将字符串数组转换为字符数组的方法。

让我们看看如何借助[StringBuilder](https://code-maze.com/stringbuilder-csharp/)来实现：

```csharp
public static char[] ConvertStringArrayToCharArrayUsingLoop(string[] stringArray)
{
    var combinedString = new StringBuilder();
    foreach (var str in stringArray)
    {
        combinedString.Append(str);
    }
    var result = new char[combinedString.Length];
    combinedString.CopyTo(0, result, 0, result.Length);
    return result;
}
```

这里，我们首先创建一个`StringBuilder`并使用`Append()`方法将字符串连在一起。接下来，我们根据合并字符串的长度分配`result` char数组。最后，我们将`combinedString`的内容复制到`result`数组中并返回它。**注意** **在连接`stringArray`的元素时我们没有添加分隔符**。

## 使用LINQ将字符串数组转换为Char数组

我们也可以使用LINQ而非循环来达到相同的结果：

```csharp
public static char[] ConvertStringArrayToCharArrayUsingLinq(string[] stringArray)
{
    return stringArray.SelectMany(s => s.ToCharArray()).ToArray();
}
```

这个`ConvertStringArrayToCharArrayUsingLinq()`方法使用LINQ（语言集成查询）将字符串数组`stringArray`转换为单个字符数组`char[]`。

> 有关LINQ的更多详细信息，请查看我们的文章[LINQ](https://code-maze.com/linq-csharp-basic-concepts/)。

这里我们使用LINQ的`SelectMany()`将数组中的每个字符串转换为一系列字符。`ToCharArray()`方法应用于每个字符串，结果是一个字符序列。最后，`ToArray()`将序列转换为单个`char[]`。

这种方法通过将集合中所有字符串的字符连接成一个单一的`char[]`来执行，它是使用LINQ的表达性语法达到预期结果的简洁且可读的方式。

## 结论

在这篇文章中，我们学习了如何将一个字符串转换为char数组。我们还更进一步，将字符串数组转换成char数组。理解如何将字符串转换为字符数组并将其扩展到处理字符串数组，在C#编程中提供了有价值的灵活性。无论是处理单个字符串还是字符串集合，这些转换在我们的开发工具箱中都是强大的工具。

通过利用这些技术，我们可以在处理字符串和字符操作时，提高C#应用程序的效率和多样性。
