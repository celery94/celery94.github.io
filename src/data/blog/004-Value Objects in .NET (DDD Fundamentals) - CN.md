---
pubDatetime: 2024-02-01T20:33:54
tags: [.NET, DDD]
source: https://www.milanjovanovic.tech/blog/value-objects-in-dotnet-ddd-fundamentals
author: Milan Jovanović
title: .NET 中的值对象（领域驱动设计基础）
description: 值对象是领域驱动设计的基础构件之一。DDD 是一种针对复杂领域问题解决方案的软件开发方法。值对象封装了一组原始值和相关的不变性。一些值对象的例子包括金钱和日期范围对象。金钱由金额和货币构成。日期范围由开始日期和结束日期构成。
---

> 本文翻译自 [Milan Jovanović](https://www.milanjovanovic.tech/blog/value-objects-in-dotnet-ddd-fundamentals) 的博客文章。原文标题为 [Value Objects in .NET (DDD Fundamentals)](https://www.milanjovanovic.tech/blog/value-objects-in-dotnet-ddd-fundamentals)。

---

**值对象**是领域驱动设计的基础构件之一。DDD 是一种针对复杂领域问题解决方案的软件开发方法。

值对象封装了一组原始值和相关的不变性。一些值对象的例子包括金钱和日期范围对象。金钱由金额和货币构成。日期范围由开始日期和结束日期构成。

今天，我将向你展示一些实现值对象的最佳实践。

## 什么是值对象？

让我们从《领域驱动设计》书中的定义开始：

> 一个代表领域中的描述性方面且没有概念身份的对象被称为值对象。值对象被实例化以表示我们只关心它们是什么，而不是它们是谁或哪一个的设计元素。

_— [埃里克·埃文斯](http://www.amazon.com/Domain-Driven-Design-Tackling-Complexity-Software/dp/0321125215)_

值对象与实体不同——它们没有身份概念。它们封装了领域中的原始类型，并解决了[原始类型固执](https://refactoring.guru/smells/primitive-obsession)。

值对象有两个主要特质：

- 它们是不可变的
- 它们没有身份

值对象的另一个特质是结构相等。如果两个值对象的值相同，则它们相等。这个特质在实践中是最不重要的。然而，在某些情况下，你可能希望只有一些值决定相等性。

## 实现值对象

值对象最重要的特质是不可变性。一旦创建了值对象，其值就不能改变。如果你想改变某个值，你需要替换整个值对象。

以下是一个`Booking`实体，它使用原始值来表示地址以及预订的开始和结束日期。

```csharp
public class Booking
{
    public string Street { get; init; }
    public string City { get; init; }
    public string State { get; init; }
    public string Country { get; init; }
    public string ZipCode { get; init; }

    public DateOnly StartDate { get; init; }
    public DateOnly EndDate { get; init; }
}
```

你可以用`Address`和`DateRange`值对象替换这些原始值。

```csharp
public class Booking
{
    public Address Address { get; init; }

    public DateRange Period { get; init; }
}
```

但你如何实现值对象呢？

### C# 记录（Records）

你可以使用 C# 记录（records）来表示值对象。记录（Records）在设计上是不可变的，并且它们具有结构相等性。我们希望我们的值对象具有这两个特质。

例如，你可以使用带有主构造器的`record`来表示一个`Address`值对象。这种方法的优势在于简洁性。

```csharp
public record Address(
    string Street,
    string City,
    string State,
    string Country,
    string ZipCode);
```

然而，当定义一个私有构造函数时，你会失去这个优势。当你想在创建值对象时强制执行不变性时，就会发生这种情况。使用记录（records）的另一个问题是，使用`with`表达式时避免值对象不变性。

```csharp
public record Address
{
    private Address(
        string street,
        string city,
        string state,
        string country,
        string zipCode)
    {
        Street = street;
        City = city;
        State = state;
        Country = country;
        ZipCode = zipCode;
    }

    public string Street { get; init; }
    public string City { get; init; }
    public string State { get; init; }
    public string Country { get; init; }
    public string ZipCode { get; init; }

    public static Result<Address> Create(
        string street,
        string city,
        string state,
        string country,
        string zipCode)
    {
        // Check if the address is valid

        return new Address(street, city, state, country, zipCode);
    }
}
```

### 基类

实现值对象的另一种方式是使用`ValueObject`基类。基类通过`GetAtomicValues`抽象方法处理结构相等性。`ValueObject`的实现必须实现这个方法并定义相等组件。

使用`ValueObject`基类的优势是它的明确性。在你的领域中，哪些类代表值对象是清晰的。另一个优势是能够控制相等组件。

这是我在我的项目中使用的`ValueObject`基类：

```csharp
public abstract class ValueObject : IEquatable<ValueObject>
{
    public static bool operator ==(ValueObject? a, ValueObject? b)
    {
        if (a is null && b is null)
        {
            return true;
        }

        if (a is null || b is null)
        {
            return false;
        }

        return a.Equals(b);
    }

    public static bool operator !=(ValueObject? a, ValueObject? b) =>
        !(a == b);

    public virtual bool Equals(ValueObject? other) =>
        other is not null && ValuesAreEqual(other);

    public override bool Equals(object? obj) =>
        obj is ValueObject valueObject && ValuesAreEqual(valueObject);

    public override int GetHashCode() =>
        GetAtomicValues().Aggregate(
            default(int),
            (hashcode, value) =>
                HashCode.Combine(hashcode, value.GetHashCode()));

    protected abstract IEnumerable<object> GetAtomicValues();

    private bool ValuesAreEqual(ValueObject valueObject) =>
        GetAtomicValues().SequenceEqual(valueObject.GetAtomicValues());
}
```

`Address`值对象的实现看起来会是这样：

```csharp
public sealed class Address : ValueObject
{
    public string Street { get; init; }
    public string City { get; init; }
    public string State { get; init; }
    public string Country { get; init; }
    public string ZipCode { get; init; }

    protected override IEnumerable<object> GetAtomicValues()
    {
        yield return Street;
        yield return City;
        yield return State;
        yield return Country;
        yield return ZipCode;
    }
}
```

## 何时使用值对象？

我使用值对象来解决原始类型固执问题并封装领域不变性。封装是任何领域模型的重要方面。你不应该能够在无效状态下创建值对象。

值对象还为你提供了类型安全。看看这个方法签名：

```csharp
public interface IPricingService
{
    decimal Calculate(Apartment apartment, DateOnly start, DateOnly end);
}
```

然后，将其与我们添加了值对象的这个方法签名进行比较。你可以看到，使用值对象的`IPricingService`要明确得多。你还获得了类型安全的好处。在编译代码时，值对象减少了错误潜入的机会。

```csharp
public interface IPricingService
{
    PricingDetails Calculate(Apartment apartment, DateRange period);
}
```

你应该考虑以下几点以决定是否需要值对象：

- **不变性的复杂性** - 如果要强制执行复杂的不变性，请考虑使用值对象
- **原始值的数量** - 当封装许多原始值时，使用值对象是有意义的
- **重复的数量** - 如果你只需要在代码中几个地方强制执行不变性，你可以不使用值对象

## 使用 EF Core 持久化值对象

值对象是领域实体的一部分，你需要将它们保存在数据库中。

我将向你展示如何使用 EF [拥有类型](https://learn.microsoft.com/en-us/ef/core/modeling/owned-entities)和[复杂类型](https://devblogs.microsoft.com/dotnet/announcing-ef8-rc1/#complex-types-as-value-objects)来持久化值对象。

### 拥有类型

[拥有类型](https://learn.microsoft.com/en-us/ef/core/modeling/owned-entities)可以通过在配置实体时调用`OwnsOne`方法来配置。这告诉 EF 将`Address`和`Price`值对象持久化到与`Apartment`实体相同的表中。值对象以`apartments`表中的额外列表示。

```csharp
public void Configure(EntityTypeBuilder<Apartment> builder)
{
    builder.ToTable("apartments");

    builder.OwnsOne(property => property.Address);

    builder.OwnsOne(property => property.Price, priceBuilder =>
    {
        priceBuilder.Property(money => money.Currency)
            .HasConversion(
                currency => currency.Code,
                code => Currency.FromCode(code));
    });
}
```

关于拥有类型的更多说明：

- 拥有类型有一个隐藏的键值
- 不支持可选（可空）拥有类型
- 支持使用`OwnsMany`的拥有集合
- 表拆分允许你分开持久化拥有类型

### 复杂类型

[复杂类型](https://devblogs.microsoft.com/dotnet/announcing-ef8-rc1/#complex-types-as-value-objects)是 .NET 8 中可用的一项新 EF 功能。它们不通过键值被识别或跟踪。复杂类型必须是实体类型的一部分。

对于使用 EF 表示值对象，复杂类型更为合适。

以下是如何将`Address`值对象配置为复杂类型：

```csharp
public void Configure(EntityTypeBuilder<Apartment> builder)
{
    builder.ToTable("apartments");

    builder.ComplexProperty(property => property.Address);
}
```

复杂类型的一些限制：

- 不支持集合
- 不支持可空值

## 要点

值对象有助于设计丰富的领域模型。你可以使用它们来解决原始类型固执问题并封装领域不变性。值对象通过防止无效领域对象的实例化来减少错误。

你可以使用`record`或`ValueObject`基类来表示值对象。这应该取决于你的具体要求和领域的复杂性。默认情况下我使用记录（records），除非我需要`ValueObject`基类的一些特性。例如，当你想控制相等组件时，基类是实用的。
