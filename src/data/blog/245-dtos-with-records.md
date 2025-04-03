---
pubDatetime: 2025-04-03 12:29:15
tags: [C#, DTOs, Records, .NET, Software Development]
slug: dtos-with-records
source: none
author: Celery Liu
title: 使用 C# Records 优化 DTOs：为什么推荐？
description: 探讨在 C# 中使用 Records 代替 Classes 定义数据传输对象 (DTO)，以及它们的技术优势。
---

# 使用 C# Records 优化 DTOs 🚀

在现代软件开发中，数据传输对象 (DTO, Data Transfer Object) 是一种常见的设计模式，用于在系统的不同部分之间传递数据。通常，DTO 是通过类定义的，但在 C# 的最新版本中，引入了 **Records** 类型，这是一个更加简洁且功能强大的替代方案。本篇文章将探讨为什么在定义 DTO 时推荐使用 C# Records，以及它们的技术优势。

---

## 什么是 DTO？📦

### 定义

DTO 是一种仅用于传递数据的对象。它通常不包含业务逻辑，只存储字段或属性以便在不同系统组件之间交换信息。DTO 的主要特点包括：

- 简单且轻量级。
- 不依赖复杂的逻辑，仅作为数据载体。

### 传统实现方式

在传统的 C# 开发中，DTO 通常通过 `class` 定义。例如：

```csharp
public class GetTodoResponse
{
    public Guid? Id { get; set; }
    public string Title { get; set; }
    public string Notes { get; set; }
}
```

这种实现虽然有效，但存在一定的冗余，例如手动定义 `get; set;` 属性，以及潜在的可变性问题。

---

## 为什么使用 C# Records？🎯

C# 在 9.0 版本中引入了 **Records** 类型，这是一种特殊的引用类型，专门用于不可变数据建模，非常适合 DTO 的场景。

### Records 的特点

1. **不可变性 (Immutable)**
   - Records 默认是不可变的，这意味着一旦创建，数据就无法修改。这非常适合 DTO，因为 DTO 通常只用来传递数据，而不是修改数据。
2. **简化代码**
   - 使用 Records 可以省去大量的模板代码。例如，自动实现 `get; set;` 属性以及构造函数等。
3. **内置值比较**

   - Records 内置了基于值的比较功能，即两个 Record 实例被认为相等，如果它们的所有字段值都相等。这在处理数据传输时非常方便。

4. **更符合 DTO 的用途**
   - Records 完美契合 DTO 的单向数据流模式，仅用于传递状态，不附加任何逻辑。

---

## 对比：Class vs Record 📋

以下是使用 `class` 和 `record` 定义 DTO 的对比：

### 使用 Class 定义 DTO

```csharp
public class GetTodoResponse
{
    public Guid? Id { get; set; }
    public string Title { get; set; }
    public string Notes { get; set; }
}
```

缺点：

- 可变性：`get; set;` 使得属性可以被修改，不符合 DTO 的设计初衷。
- 冗长：需要手动定义每个属性。
- 无内置值比较：需要额外编写代码才能进行深度比较。

### 使用 Record 定义 DTO

```csharp
public record GetTodoResponse(Guid? Id, string Title, string Notes);
```

优点：

- 默认不可变：更安全，防止意外修改。
- 简洁：构造函数和属性声明合二为一。
- 内置值比较：无需额外代码即可比较两个实例是否相等。

---

## 技术实现解析 🛠️

### Immutable 数据模型

使用 Records 定义的 DTO 是不可变的，这意味着所有属性只能在对象初始化时赋值。以下代码展示了如何创建和使用不可变 Record：

```csharp
var todoResponse = new GetTodoResponse(Guid.NewGuid(), "Learn C#", "Use Records for DTO");
Console.WriteLine(todoResponse.Title); // 输出: Learn C#
```

### 值比较示例

Records 的值比较功能可以减少代码量，提高代码可读性：

```csharp
var todo1 = new GetTodoResponse(Guid.NewGuid(), "Learn C#", "Use Records for DTO");
var todo2 = new GetTodoResponse(todo1.Id, "Learn C#", "Use Records for DTO");

Console.WriteLine(todo1 == todo2); // 输出: True，因为所有字段值相等。
```

### 与类的继承对比

虽然 Records 可以继承，但它们更加专注于数据建模，而不是行为建模。例如：

```csharp
public record ExtendedTodoResponse(Guid? Id, string Title, string Notes, DateTime CreatedAt)
    : GetTodoResponse(Id, Title, Notes);
```

这种继承方式让你能够扩展字段，而无需修改原始记录。

---

## 总结 📌

使用 C# Records 定义 DTO 是一种现代化、高效且简洁的方法。与传统的类定义相比，Records 在不可变性、代码简化以及内置值比较方面具有显著优势，非常适合用于数据传输场景。

### 推荐场景

1. **数据传输**：需要轻量级对象来传递数据。
2. **不可变性要求**：需要确保对象状态不被修改。
3. **高频比较操作**：需要频繁比较对象值。

通过采用 Records，开发者可以大幅减少模板代码，同时提高代码质量与维护性。如果你正在使用 C# 开发项目，不妨尝试用 Records 替代传统类定义 DTO，让你的代码更加现代化！
