---
pubDatetime: 2024-05-21
tags: ["Productivity", "Tools"]
source: https://www.devleader.ca/2024/05/20/dapper-and-strongly-typed-ids-how-to-dynamically-register-mappings/
author: Nick Cosentino
title: Dapper与强类型ID：动态注册映射
description: 如何结合使用Dapper和来自StronglyTypedId包的强类型ID？让我们看看是否可以推广原作者的指导意见！
---

# Dapper与强类型ID：动态注册映射

> ## 摘录
>
> 如何结合使用Dapper和来自StronglyTypedId包的强类型ID？让我们看看是否可以推广原作者的指导意见！
>
> 原文 [Dapper and Strongly Typed IDs: How to Dynamically Register Mappings](https://www.devleader.ca/2024/05/20/dapper-and-strongly-typed-ids-how-to-dynamically-register-mappings/)

---

Dapper和StronglyTypedId是我们在.NET开发中可以使用的两个棒棒的包——但如何结合使用Dapper和强类型ID呢？

在本文中，我将解释我正在构建的方法，该方法在包作者的推荐基础上进行了扩展。虽然现在还不是最优化的，但有两个有趣的方向可以考虑！

---

## 什么是Dapper？

Dapper是一个简单、轻量的ORM（对象关系映射器）供C#开发者使用。许多人熟悉Entity Framework Core (EF Core)，但Dapper是你可以用作ORM的绝佳选项。实际上，在多年不使用ORM并尝试EF Core之后，我感到失望……但最近尝试Dapper后，我意识到这正是我所寻求的。

Dapper旨在通过提供一种快速高效的方式与数据库进行交互来提高数据访问的性能。它不像在代码APIs中那样掩盖SQL的外貌，你编写原始SQL并让Dapper为你进行对象映射。然而，[Dapper也有SQL构建工具类](https://github.com/DapperLib/Dapper/tree/main/Dapper.SqlBuilder "Dapper.SqlBuilder - 一个简单的sql格式化工具")！

以下是在应用中考虑使用Dapper时的一些关键点：

1.  **性能**：Dapper以其速度而闻名。它使用原始SQL查询，但将结果直接映射到C#对象，使其比传统ORM（如Entity Framework）更快。
2.  **简单**：Dapper使用非常简单。开发者可以直接编写SQL查询并以最小的开销执行它们。
3.  **灵活性**：它适用于任何支持ADO.NET的数据库，包括SQL Server、MySQL、PostgreSQL、SQLite等。
4.  **微ORM**：Dapper被认为是微ORM，因为它没有提供完整ORM的所有功能，但专注于性能和简单性。它高效地处理基本的CRUD操作。
5.  **扩展方法**：它通过像Query和Execute这样的方法扩展了IDbConnection接口，允许轻松地检索和操作数据。
6.  **最少设置**：Dapper需要的配置和设置很少，使其快速集成到现有项目中。

你可以通过[访问项目的GitHub页面](https://github.com/DapperLib/Dapper/tree/main "Dapper - 一个简单的对象映射器")来了解更多关于Dapper的信息。

---

## 什么是强类型ID？

强类型ID是C#中提高类型安全的一种技术，通过使用像`int`、`Guid`或`string`这样的原始类型来代替表示特定实体ID的自定义类型。这有助于避免因混淆不同类型的ID而导致的错误，并增强代码的可读性和可维护性。

你可能会问这是如何帮助实现这些目标的，答案是解决了部分“[原始类型固执](https://lostechies.com/jimmybogard/2007/12/03/dealing-with-primitive-obsession/ "处理原始类型固执")”问题。当我们有代表特定含义的原始类型时，因为很容易将一个`string`替换为另一个`string`，或一个`int`替换为另一个`int`，就会遇到易犯的错误。但如果一个应该是`UserId`而另一个应该是`AccountType`，那么这些就不应该是可互换的！

[Andrew Lock的StronglyTypedId项目](https://github.com/andrewlock/StronglyTypedId "StronglyTypedId项目")提供了在C#中生成强类型ID类的方法。Andrew Lock是一个受欢迎的.NET博主，而且这个库绝对是棒棒的。

在考虑使用这个项目时，以下是一些要检查的关键点：

1.  **类型安全**：确保不同实体的ID（例如UserId, OrderId）不会意外交换，减少了错误。
2.  **代码生成**：Andrew Lock的StronglyTypedId项目使用源生成器自动生成强类型ID类，最小化了手动样板代码。
3.  **易用性**：你可以通过简单地将一个属性添加到实体上来定义一个强类型ID，项目会处理其余事项。
4.  **兼容性**：生成的ID与常见库和框架兼容，确保它们在现有代码库中无缝工作。很快我们会看到更多这方面的内容！
5.  **序列化**：强类型ID可以轻松序列化和反序列化，使得它们适用于API和数据存储中。
6.  **定制**：该项目允许对生成的ID类进行定制，例如选择底层类型（`int`、`Guid`等）。你不会被锁定在一个原始后备类型中。

如果你正在寻找一种获得更好的ID类型支持的简单方法，Andrew Lock的StronglyTypedId非常棒！下面是代码是多么简单：

```csharp
[StronglyTypedId(Template.Long)]
public readonly partial struct YourId { }
```

---

## Dapper与强类型ID的挑战

### 挑战：

Dapper的基本责任之一是能够映射数据到我们的对象，并将对象映射到数据。归根到底，我们处理的数据来源通常处理（大多数）常见的原始类型，如`strings`、`ints`、`floats`等...所以只要你试图读写的实体可以由原始类型表示，你就（大多数情况下）可以解决问题！

然而，来自Lock的StronglyTypedId包的强类型ID是一个结构体和值类型，但它*不是*一个原始类型。因此，一旦你将原始类型转换为使用强类型ID，当涉及到数据转换时，一切都会中断。

但别担心！Andrew Lock有一个可靠的解决方案。

### 提出的解决方案：

Andrew Lock提出的解决方案可以在他的博客中找到：  
[https://andrewlock.net/using-strongly-typed-entity-ids-to-avoid-primitive-obsession-part-3/#interfacing-with-external-system-using-strongly-typed-ids](https://andrewlock.net/using-strongly-typed-entity-ids-to-avoid-primitive-obsession-part-3/#interfacing-with-external-system-using-strongly-typed-ids "与EF Core使用强类型实体ID避免原始类型固执")

在文章中，你可以看到我们可以使用的一个简单代码片段，用来来回转换特定的StronglyTypedId：

```csharp
class OrderIdTypeHandler : SqlMapper.TypeHandler<OrderId>
{
    public override void SetValue(IDbDataParameter parameter, OrderId value)
    {
        parameter.Value = value.Value;
    }

    public override OrderId Parse(object value)
    {
        return new OrderId((Guid)value);
    }
}
```

从那里我们只需要连接它以供使用：

```csharp
SqlMapper.AddTypeHandler(new OrderIdTypeHandler());
```

处理程序实现有两个简单的方法，用于获取值和创建特定StronglyTypedId的实例。

## 我对Dapper和强类型ID的解决方案

### 我对原始解决方案的不满

虽然Andrew Lock的解决方案非常简单且有效，但有一点我不喜欢：每次我创建一个新的StronglyTypedId时，我现在都需要记得创建一个专用的处理程序类，并且设置这个处理程序类。

对于大多数人来说，这可能不是什么大问题，但这违背了我尝试拥有的一些设计理念。我不喜欢需要手动完成的额外工作。原因是它容易出错，即使是微不足道的，也需要一些额外的时间去完成。

我提出了一个扩展Andrew Lock所提议的解决方案。虽然我的理想解决方案现在还不支持（看起来我们需要.NET 9.0支持），但对我来说这仍然非常有效。

我们将采用通用处理程序：

```csharp
private sealed class LongStrongTypeHandler<TStrongType>(
    Func<long, object> _createCallback,
    Func<object, long> _getValueCallback) :
    SqlMapper.TypeHandler<TStrongType>
{
    public override TStrongType Parse(object value)
    {
        var castedValue = (long)value;
        var instance = _createCallback.Invoke(castedValue);
        return (TStrongType)instance;
    }

    public override void SetValue(
        IDbDataParameter parameter,
        TStrongType? value)
    {
        parameter.Value = value == null
            ? DBNull.Value
            : _getValueCallback.Invoke(value);
    }
}
```

如果你在阅读这篇文章，并且警钟正在响起，别急，因为我很快会详细介绍这个。但如你所见，这是一个由`longs`支持的StronglyTypedIds的处理程序。对于我的需求，我几乎只使用这种数据类型，但也可以轻松地添加另一种更泛型的此类变体，它使用另一个类型参数作为后备值类型。

为了使用这个，我们通过以下代码连接事物：

```csharp
var typePairs = assemblies
    .SelectMany(assembly => assembly.GetTypes())
    .Select(type =>
    {
        //{[System.CodeDom.Compiler.GeneratedCodeAttribute("StronglyTypedId", "1.0.0-beta08")]}
        var generatedCodeAttribute = type.GetCustomAttribute<System.CodeDom.Compiler.GeneratedCodeAttribute>();
        if (generatedCodeAttribute is null ||
            generatedCodeAttribute.Tool != "StronglyTypedId")
        {
            return (null, null, null);
        }

        var constructor = type.GetConstructors().Where(x => x.GetParameters().Length == 1).Single();
        var parameter = constructor.GetParameters()[0];

        return (StrongType: type, ValueType: parameter.ParameterType, Constructor: constructor);
    })
    .Where(x => x.ValueType != null && x.StrongType != null)
    .ToArray();

foreach (var type in typePairs)
{
    // 注意：到目前为止，我只支持我的代码中的long StrongTypes
    if (type.ValueType != typeof(long))
    {
        throw new NotSupportedException(
            "到目前为止，只支持long StrongTypes。添加你自己的支持！");
    }

    Type genericClass = typeof(LongStrongTypeHandler<>);
    Type constructedClass = genericClass.MakeGenericType(type.StrongType);

    var getValueMethod = type.StrongType.GetMethod("get_Value");

    var typeHandler = (SqlMapper.ITypeHandler)Activator.CreateInstance(
        constructedClass,
        new object[]
        {
            (long value) => type.Constructor.Invoke([value]),
            (object x) => (long)getValueMethod.Invoke(x, null)
        });

    SqlMapper.AddTypeHandler(type.StrongType, typeHandler);
}
```

代码的顶部部分通过程序集扫描找到感兴趣的类型。我们需要查找`GeneratedCodeAttribute`并匹配正确的工具。接着，我们使用一些反射的位来获取构造函数和getter属性，以便能够创建我们的通用处理程序的新实例。最后，我们将其添加到`SqlMapper`类中。

你只需要在启动时调用这段代码一次，它将按需注册所有你的处理程序。

### 明显的问题和希望修复

这种方法的一个巨大问题是潜在的性能影响。Lock的方法在类型方面非常简单。在这种情况下，我需要既通用又动态，因此使用反射来解决这个问题。

如果性能绝对关键，这将是一个不佳的选择：

- 处理程序使用反射创建StronglyTypedId实例
- 处理程序使用反射询问StronglyTypedId其值
- 处理程序设置中有装箱（值类型到对象）

对于我目前的用例，我对此并不担心。性能（还）不是关键，并且我有方法可以创建一个更高性能的变体。我想要从一开始就有但遇到了一些问题：

```csharp
    private sealed class StrongTypeHandler<TStrongType, TValueType> :
        SqlMapper.TypeHandler<TStrongType>
    {
        [UnsafeAccessor(UnsafeAccessorKind.Constructor)]
        private extern static TStrongType CreateTypeInstance(TValueType value);

        [UnsafeAccessor(UnsafeAccessorKind.Method, Name = "get_Value")]
        private extern static TValueType GetValue(TStrongType @this);

        public override TStrongType Parse(object value)
        {
            var castedValue = (TValueType)value;
            var instance = CreateTypeInstance(castedValue);
            return instance;
        }

        public override void SetValue(
            IDbDataParameter parameter,
            TStrongType? value)
        {
            parameter.Value = value == null
                ? DBNull.Value
                : GetValue(value);
        }
    }
```

这段代码使用了`UnsafeAccessor`属性，可以极其高性能。[这篇文章](https://startdebugging.net/2023/11/net-8-performance-unsafeaccessor-vs-reflection/)演示了它们有多高性能，但比较不安全访问与反射和直接访问的基准测试结果如下：

| 方法           |       均值 |      错误 |    标准差 |
| -------------- | ---------: | --------: | --------: |
| 反射           | 35.9979 ns | 0.1670 ns | 0.1562 ns |
| 带缓存的反射   | 21.2821 ns | 0.2283 ns | 0.2135 ns |
| UnsafeAccessor |  0.0035 ns | 0.0022 ns | 0.0018 ns |
| 直接访问       |  0.0028 ns | 0.0024 ns | 0.0023 ns |

这些数据清楚地显示我的方法速度比其他方法慢好几个数量级，但也显示我的理想方法在技术上可能与直接访问相当。看起来到.NET 9.0时代我们可能才能使用带有泛型的UnsafeAccessor。另一个选项是使用源生成器进行转换器，这样样板代码都是为我们准备好的。但无论如何，当我需要优化时有一些选项！

---

## 封装Dapper与强类型ID

Andrew Lock的StronglyTypedId项目很棒，并且结合使用Dapper和强类型ID只需要一点点工作。本文概述的方法展示了我们如何动态扫描处理程序类以创建。尽管目前的实现因反射而效率不佳，我们可以期待使用`UnsafeAccessor`属性和/或源生成器来优化这一点。
