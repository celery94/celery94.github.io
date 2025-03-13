---
pubDatetime: 2024-04-16
tags: []
source: https://code-maze.com/csharp-improvements-in-the-using-directive-for-additional-types/
author: Georgios Panagopoulos
title: 在 C# 中 `using` 指令的额外类型改进
description: 在 C# 中，`using` 指令帮助我们减少了样板代码。让我们看看 C# 12 是如何提升 `using` 指令以用于额外的类型的。
---

> ## 摘要
>
> 在 C# 中，`using` 指令帮助我们减少了样板代码。让我们看看 C# 12 是如何提升 `using` 指令以用于额外的类型的。
>
> 原文 [Improvements in the Using Directive for Additional Types in C#](https://code-maze.com/csharp-improvements-in-the-using-directive-for-additional-types/) 由 Georgios Panagopoulos 撰写，2024 年 4 月 16 日发布。

---

C# 中的 “using” 指令在引用位于我们类上下文之外的类型和成员时有助于我们减少样板代码。C# 12 进一步扩展了 `using` 指令的功能，允许它用于额外的类型。

在本文中，我们将首先回顾到目前为止在 .NET 中如何使用 “using”。然后我们将探讨如何在过去更多类型中使用 `using` 指令。

要下载本文的源代码，您可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/csharp-basic-topics/UsingDirectiveForAdditionalTypes)。

## `using` 指令的常见用途

`using` 指令已经存在了好几年，C# 团队在不同的语言版本中扩展了其能力。

让我们看看到目前为止我们如何能够使用它。

### 导入外部命名空间

`using` 的最常见用途是导入外部命名空间的类型。

让我们导入命名空间 `System.Collections.Generic` 到我们的代码中，这样我们就可以“使用”它所包含的类型和功能：

```csharp
using System.Collections.Generic;
```

现在我们可以像使用我们类的成员一样使用 `List<T>`：

```csharp
public static List<Article> GetArticles()
{
    return new List<Article>()
    {
        new("如何在 C# 中使用 `Using Static` 功能", 950),
        new("C# 中的全局 Using 指令", 1100),
        new("对额外类型的 Using 指令", 800)
    };
}
```

通过 `using` 指令导入命名空间是编写 C# 代码的一个基本部分，语言从其第一个版本开始就包含了它。

### 访问静态成员

C# 6 引入了 `using static` 指令，旨在**减少访问静态成员时的样板代码。** 它使我们能够导入一个 `static` 类的成员，然后像使用局部变量一样使用它们。

让我们导入 `System.Math` 以便我们使用其成员：

```csharp
using static System.Math;
```

结果，我们可以调用 `Min()` 方法而不必每次都包括完全限定的名字 `System.Math.Min()` 或 `Math.Min()`:

```csharp
public static int GetMinimumInteger(int num1, int num2, int num3, int num4)
{
    return Min(Min(Min(num1, num2), num3), num4);
}
```

`using static` 指令是 C# 语言的一个很好的补充，所以请确保查看我们的文章 [如何在 C# 中使用 “Using Static” 功能](https://code-maze.com/using-static-feature-csharp/) 以深入了解。

### 全局和隐式 ‘using’ 指令

C# 10 引入了 ‘global’ 和 ‘implicit’ `using` 指令的概念。

虽然 `using` 允许我们在需要时在一个类中导入命名空间，`global using` 指令允许我们**导入将在整个应用程序中使用的命名空间。**在全局声明命名空间后，我们可以在任何文件中使用它。

让我们看看我们如何使用 `global using` 声明一个全局命名空间。为此，我们创建一个名为 `GlobalUsings.cs` 的单独文件来存储所有全局 usings：

```csharp
global using UsingDirectiveForAdditionalTypes.Models;
```

这里，我们全局声明了命名空间 `UsingDirectiveForAdditionalTypes.Models`，以便我们可以在整个应用程序中使用它的成员。

`ImplicitUsings` 是一个密切相关的功能，也在 C# 10 中引入。它指示编译器自动生成一个包含我们应用程序所需的所有 `using` 指令的 `GlobalUsings.cs` 文件。这个设置可以在我们应用程序的 `.csproj` 文件中启用或禁用。

让我们看看我们在哪里可以编辑 `ImplicitUsings` 设置的值：

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>disable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>
```

正如我们在这里看到的，我们已经禁用了 `ImplicitUsings` 设置。

请确保查看我们的文章 [C# 中的全局 Using 指令](https://code-maze.com/csharp-global-using-directives/)，了解这个伟大功能的全局和隐式更深入的学习。

### 类型别名

`using` 指令还可以用于类型别名。C# 早些时候引入了这个功能，允许我们导入一个类型并为其设置别名，以便我们可以用一个简短的名称来引用它。

让我们看看类型别名如何工作：

```csharp
using CodeMazeArticle = UsingDirectiveForAdditionalTypes.Models.Article;
```

这里，我们定义了别名 `CodeMazeArticle` 并将其设置为代表类型 `UsingDirectiveForAdditionalTypes.Models.Article`。这样，我们就可以在代码中使用 `CodeMazeArticle` 来代替完全限定的类型：

```csharp
public static List<CodeMazeArticle> GetCodeMazeArticles()
{
    return new List<CodeMazeArticle>()
    {
        new("如何在 C# 中使用 `Using Static` 功能", 950),
        new("C# 中的全局 Using 指令", 1100),
        new("对额外类型的 Using 指令", 800)
    };
}
```

到目前为止，这适用于有限的一组内置类型、自定义类型和命名空间。

现在让我们看看新支持的类型。

C# 12 进一步扩展了类型别名功能，现在我们可以使用 `using` 指令为几乎任何类型设置别名。

### 可空类型

一个新支持别名的类型是可空值类型：

```csharp
using NullableInt = int?;
```

这里我们使用 `using` 指令将 `int?` 别名为 `NullableInt`。然后我们可以在我们的代码中使用 `NullableInt`：

### 数组类型

`Array` 是另一种可以使用 `using` 指令创建别名的类型。我们可以用它为内置类型的数组和我们自定义类型的数组设置别名：

```csharp
using Titles = string[];
```

这里，我们为 `string[]` 定义一个别名 `Titles`。在我们下面的代码中，当提到字符串数组时，我们正在使用 `Titles`：

```csharp
public static Titles GetArticleTitles()
{
    return AliasExamples.GetArticles()
                        .Select(a => a.Title)
                        .ToArray();
}
```

### 元组

[元组](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/builtin-types/value-tuples) 是一种轻量级的数据结构，用于分组可能按类型不同的元素。它是一种在不需要定义自定义类型的情况下存储多个值的便捷方式。例如，以下元组将一个 `string` 和一个 `int` 值组合在一起：`(string, int)`

元组灵活而强大，但社区在某些情况下，理所当然地批评它们使代码变得难以推理。这就是为什么 C# 后来引入了元组别名。

我们可以使用 `using` 指令为元组创建别名，使我们的代码更具可读性：

```csharp
using Location = (int X, int Y);
```

这里我们定义了一个新的 `Tuple(int X, int Y)` 并将其命名为 `Location`。现在让我们使用 `Location` 元组：

```csharp
public static List<Location> GetLocationsOfInterest()
{
    return [new Location(25, 3), new Location(12, 8), new Location(-2, 0)];
}
```

注意它就好像是一个普通的 C# 约定提供了上下文信息。您可以在我们的文章 [C# 中的元组别名](https://code-maze.com/csharp-tuple-aliases/) 中阅读更多关于元组和别名的信息。

### 针对额外类型的全局 ‘using’ 指令

`using` 指令的最强大特性之一是**我们可以全局定义别名类型**。这意味着与我们全局导入命名空间的方式相同，我们也可以全局别名一个类型，并在整个应用程序中使用相同的别名引用这个类型！

让我们看看为元组定义 `global using` 指令的语法：

```csharp
global using Destination = (string Location, double Distance);
```

这里，我们定义了 `Destination` 元组，然后我们可以在整个应用程序中使用它。

在我们下面的代码中，我们正在初始化一个新的别名为 `Destination` 的元组，并像使用任何其他 C# 对象一样使用它。更重要的是，我们在不需要在我们的代码上下文中导入任何额外命名空间的情况下实现了这一点：

```csharp
var (Location, Distance) = new Destination("London", 2500.00);
Console.WriteLine($"我的目的地是 {Location}，距离是 {Distance}");
```

## `using` 指令用于类型别名的限制

`using` 指令一直是增加我们代码可读性的有用工具，现在新支持额外类型的能力只会增强。

虽然现在支持大多数类型，但还不支持可空引用类型：

```csharp
using NullableArticle = UsingDirectiveForAdditionalTypes.Models.Article?;
```

这里我们为可空的 `Article` 类型定义了一个别名，但编译器会显示一个错误，说明 “using 别名不能是可空引用类型”。

我们还应该记住，过度使用 `using` 指令，或者用已经作为 .NET 类型存在的名称定义别名，可能会混淆并误导其他开发人员，尤其是那些经验较少的开发人员。想象一下，如果我们为一个 3D 数组 `(int X, int Y, int Z)` 定义了一个别名 `Point`。[Point](https://learn.microsoft.com/en-us/dotnet/api/system.windows.point?view=windowsdesktop-8.0) 在 .NET 中已经作为 `struct` 存在，我们的别名会使开发人员困惑我们应该使用哪种类型。

因为这些原因，当我们引入 `using` 指令到我们的代码中时，我们应该小心谨慎。

## 结论

在本文中，我们学习了如何使用增强的 “using” 指令来处理额外的类型。

我们展示了到目前为止在 .NET 中我们如何使用 `using` 指令来导入命名空间以及引用和别名类型。然后我们继续展示了在 C# 12 中，通过 `using` 指令支持别名是如何扩展到更多 .NET 类型的。
