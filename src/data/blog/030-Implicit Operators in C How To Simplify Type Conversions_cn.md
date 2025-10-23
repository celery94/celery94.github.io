---
pubDatetime: 2024-03-06
tags: [".NET", "C#"]
source: https://www.devleader.ca/2024/03/04/implicit-operators-in-c-how-to-simplify-type-conversions/
author: Nick Cosentino
title: C#中的隐式操作符，如何简化类型转换
description: 学习如何通过使用 C# 中的隐式操作符执行隐式转换。这是一个有用的特性，如果小心使用，可以增强可读性。
---

# C#中的隐式操作符：如何简化类型转换

> ## 摘录
>
> 学习如何通过使用 C# 中的隐式操作符执行隐式转换。这是一个有用的特性，如果小心使用，可以增强可读性。

---

C#中的隐式操作符允许我们定义在处理多种类型时发生的自定义类型转换——正如你所猜测到的那样——隐式进行。在这个场景中隐式意味着我们不必显式地进行类型转换，因为我们实现的隐式操作符会为我们处理这一切。

[C#中的隐式操作符在简化数据类型转换中起到作用](https://www.devleader.ca/2023/08/04/implicit-operators-clean-code-secrets-or-buggy-nightmare/ "隐式操作符 - 清晰代码的秘密还是错误的噩梦？")。它们允许你无缝转换一种类型到另一种类型，而无需显式地转换值。这个功能可以节省你的时间和精力，并提高代码的可读性，但就像我们查看的所有事物一样，也有需要考虑的缺点。

在本文中，我们将[探索 C# 中隐式操作符的使用案例](https://www.devleader.ca/2023/05/31/implicit-operators-in-c-and-how-to-create-a-multi-type/ "C#中的隐式操作符及如何创建多类型")并检查代码示例来说明它们的实际应用。让我们深入了解 C# 中的隐式操作符吧！

---

## 什么是C#中的隐式操作符？

C#中的隐式操作符是一种强大的特性，允许一种类型的对象自动转换为另一种类型，而无需显式转换。它们提供了一种无缝转换类型的方法，使代码更加简洁和可读。

隐式操作符被定义为类或结构体中的特殊方法，使用`implicit`关键字。这些方法指定了从一种类型到另一种类型的转换。当编译器遇到涉及兼容类型的赋值或表达式时，它将自动调用适当的隐式操作符来执行转换。

以下是一个说明这个概念的示例：

```csharp
public struct Celsius
{
    public Celsius(double value)
    {
        Value = value;
    }

    public double Value { get; }

    // 从 Celsius 到 Fahrenheit 定义一个隐式操作符
    public static implicit operator Fahrenheit(Celsius celsius)
    {
        double fahrenheit = celsius.Value * 9 / 5 + 32;
        return new Fahrenheit(fahrenheit);
    }
}

public struct Fahrenheit
{
    public Fahrenheit(double value)
    {
        Value = value;
    }

    public double Value { get; }
}

public class Program
{
    public static void Main()
    {
        // 隐式将一个 Celsius 温度转换为 Fahrenheit
        Celsius celsius = new Celsius(25);
        Fahrenheit fahrenheit = celsius;

        Console.WriteLine(fahrenheit.Value);  // 输出：77
    }
}
```

在这个例子中，我们有一个带有`Value`属性的`Celsius`类型。我们在`Celsius`类型中定义了一个隐式操作符，它将一个`Celsius`值转换为`Fahrenheit`。当我们将一个`Celsius`值赋给一个`Fahrenheit`变量时，编译器自动调用隐式操作符，将温度从摄氏度转换为华氏度。

C#中的隐式操作符可以通过允许对象在适当时自动转换来大大简化代码。这可以使代码更易于阅读，并减少显式类型转换的需要。然而，重要的是要谨慎使用隐式操作符，并确保转换是安全和逻辑上合理的。

---

## 隐式操作符在C#中的优缺点

就像我们看到的一切一样，总会有优点和缺点。我试图确保我们在我的网站和[我的 YouTube 频道](https://www.youtube.com/@devleader?sub_confirmation=1 "开发领袖 - YouTube")上共同讨论的每个话题都观察多个视角。在我看来，这是理解事物是更好还是更差配合的最佳方式。

### 隐式操作符在C#中的优点

C#中的隐式操作符在软件开发中提供了几个好处。它们可以通过允许自动类型转换而不需要显式转换或转换方法来简化代码和提高可读性。这消除了重复和可能错误的代码的需要，使代码库更加简洁易懂。

考虑以下示例，我们有一个自定义类型`Length`，表示我们正在处理的测量单位：

```csharp
public struct Length
{
    public double Value { get; set; }

    // 从 Length 到 double 的隐式转换
    public static implicit operator double(Length length)
    {
        return length.Value;
    }
}
```

通过定义隐式操作符，我们可以在计算中使用这个自定义类型，而不需要显式地将它们转换为其底层类型：

```
Length length = new Length { Value = 5.0 };
double finalResult = (length * 1.23) / 42d;
Console.WriteLine($"答案是 {finalResult}.");
```

需要注意的一点是，几乎任何具有这样值的数量都需要指示测量单位——这在这个示例中被省略了，因为你可以通过多种方式做到这一点，我不希望这成为焦点。因此，在这个示例中有一个假设，我们确实知道我们在处理哪个单位。

我们添加的操作符的隐式转换使代码更简单，通过减少显式转换的次数并通过更清晰地表达意图来提高可读性。如果我们需要在数学声明中到处添加(double)和其他转换，它开始分散对表达式本身的理解。

### 隐式操作符在C#中的缺点

隐式操作符的一个大缺点与我们之前看到的一个优点非常相关。我们可以隐式转换的事实可能会导致我们在不小心时进入非常奇怪的情形。

我们引入另一种也可以隐式转换为double的自定义类型。我们可以像之前一样假设我们知道这个表示数量的类型的单位。下面是代码，与前一个类型非常相似：

```csharp
public struct Temperature
{
    public double Value { get; set; }

    // 从 Temperature 到 double 的隐式转换
    public static implicit operator double(Temperature temperature)
    {
        return temperature.Value;
    }
}
```

由于两种类型都可以隐式转换为double，我们有能力写出这样的数学表达式而不需要转换——但我们应该这么做吗？

```csharp
Length length = new Length { Value = 5.0 };
Temperature temperature = new Temperature { Value = 25.0 };
double finalResult = ((length * temperature) + 42d) / 1.23;
Console.WriteLine($"答案是 {finalResult}.");
```

在这个示例中，隐式操作符允许直接执行`Length`和`Temperature`对象之间的乘法，而不需要显式转换。从隔离的角度来看，可能允许任一类型转换为double是有意义的，但当它们都可以转换时，结果可能是意外的。

举个例子，如果你的长度是米，将它们转换为一个称为lengthInMeters的double并不是太难。但是double本身是无单位的，当我们开始通过混合其他类型来累积这一点时，跟踪我们*实际上*在谈论什么单位的负担开始超过隐式转换的好处。在我看来，如果我们被迫显式转换并在必要时跟踪中间步骤中的转换，会更易于阅读。

这当然只是一个例子，但重点是，如果你在隐式转换中可能丢失数据分辨率（在这种情况下是单位），那么你就冒着这种风险。除了可能其他开发人员在pull请求和代码审查中阻止我们外，没有什么能阻止我们作为C#开发人员这么做！

---

## 隐式操作符的使用案例

在这一部分，我将展示三个C#中隐式操作符的实际使用案例。隐式操作符是一种强大的特性，允许不同类型之间的自动转换。理解和利用隐式操作符可以极大地简化你的代码并提高其可读性。让我们探索三个隐式操作符在C#中可以有用的使用案例。

### 转换自定义类型 - 心系金钱

隐式操作符的一个主要使用案例是转换自定义类型。假设我们有一个自定义类型`Money`，代表某种货币的金额。我们可能希望允许`Money`隐式转换为`double`，以简化计算并启用直接比较。以下是我们如何定义隐式操作符来实现这一点：

```csharp
public struct Money
{
    private readonly double _amount;

    public Money(double amount)
    {
        _amount = amount;
    }

    public double Amount => _amount;

    // 将 Money 隐式转换为 double
    public static implicit operator double(Money money)
    {
        return money._amount;
    }

    // 将 double 隐式转换为 Money
    public static implicit operator Money(double amount)
    {
        return new Money(amount);
    }
}

// 用法
class Program
{
    static void Main(string[] args)
    {
        Money moneyInWallet = new Money(100.50); // $100.50
        double cash = moneyInWallet; // 向 double 的隐式转换

        // 增加更多的钱
        moneyInWallet += 99.50; // 从 double 到 Money 的隐式转换，然后加法

        Console.WriteLine(cash); // 输出：100.5
        Console.WriteLine(moneyInWallet.Amount); // 输出：200
    }
}
```

通过定义从`Money`到`double`的隐式转换操作符，我们现在可以直接将一个`Money`对象赋值给一个`double`变量，而不需要显式类型转换。如果你想要拥有更具表现力的财务计算，通过拥有`Money`类型，这可能是有用的，而不是强制到处转换操作。

### 简化数学运算

隐式操作符还可以通过自动将操作数转换为兼容类型来简化数学运算。假设我们有一个代表复数的类型`ComplexNumber`，我们希望对它们执行算术运算。通过使用隐式操作符，我们可以在执行数学运算时无缝地将整数和double转换为`ComplexNumber`。在这种情况下，我们不仅需要隐式操作符进行转换，还需要操作符在两个`ComplexNumber`实例之间进行算术。

这是一个示例：

```csharp
public class ComplexNumber
{
    public double Real { get; set; }
    public double Imaginary { get; set; }

    public ComplexNumber(double real, double imaginary)
    {
        Real = real;
        Imaginary = imaginary;
    }

    // 将 int 隐式转换为 ComplexNumber
    public static implicit operator ComplexNumber(int number)
    {
        return new ComplexNumber(number, 0);
    }

    // 将 double 隐式转换为 ComplexNumber
    public static implicit operator ComplexNumber(double number)
    {
        return new ComplexNumber(number, 0);
    }

    // 添加两个 ComplexNumber 实例
    public static ComplexNumber operator +(ComplexNumber a, ComplexNumber b)
    {
        return new ComplexNumber(a.Real + b.Real, a.Imaginary + b.Imaginary);
    }
}

// 用法
ComplexNumber complexNumber = 2.5; // 从 double 的隐式转换
complexNumber += 3; // 从 int 的隐式转换
Console.WriteLine(complexNumber.Real); // 输出：5.5
```

有了隐式操作符，我们可以在不需要显式转换的情况下，在`ComplexNumber`对象上使用整数或双精度数执行数学运算。如果你正在创建一个应用程序，其中包含了很多与这些概念的算术运算，你可能会发现，不必经常转换可以提高代码的可读性。

### 与其他库的转换：一个几何示例

当与具有代表相似概念的不同类型的库或API一起工作时，隐式操作符可能特别有用。通过在这些类型之间创建隐式操作符，你可以无缝地在它们之间转换并简化与库的交互。

例如，考虑我们想要创建的一个库，该库提供了不同类型来表示二维空间中的点。该库可能定义了`Point2D`和`Vector2D`类型，每种类型都有自己的一套操作。通过在这些类型之间定义隐式操作符，你可以使用户能够根据代码的需要，使用不同的对象来表示不同的概念，从而轻松地在`Point2D`和`Vector2D`对象之间转换：

```csharp
public struct Point2D
{
    // 从 Point2D 到 Vector2D 的隐式转换
    public static implicit operator Vector2D(Point2D point)
    {
        return new Vector2D(point.X, point.Y);
    }
}

public struct Vector2D
{
    // 从 Vector2D 到 Point2D 的隐式转换
    public static implicit operator Point2D(Vector2D vector)
    {
        return new Point2D(vector.X, vector.Y);
    }
}
```

有了这些隐式操作符，用户可以无缝地在`Point2D`和`Vector2D`对象之间转换，根据其代码的需要使用它们：

```csharp
Point2D point = new Point2D(2, 3);
Vector2D vector = new Vector2D(4, 5);

// 从 Point2D 到 Vector2D 的隐式转换
Vector2D convertedVector = point;

// 从 Vector2D 到 Point2D 的隐式转换
Point2D convertedPoint = vector;
```

在这种场景下，隐式操作符通过允许用户使用不同的对象代表不同的概念来处理相同的底层数据，简化了代码并使其更具表达性。在我们想要将第三方库整合进我们的代码库，并希望在与之交互时提供一定级别的灵活性的类似情况下，可能会有好处。对于我们拥有的类型，我们可以为所涉及的库提供隐式转换，这可能会简化我们在与库交互时代码库中的逻辑。

---

## 频繁问到的问题：C#中的隐式操作符

### C#中的隐式操作符是什么？

C#中的隐式操作符是一种特殊方法，允许在两种类型之间自动转换，无需显式强制类型转换。它们使用`implicit`关键字定义，并启用隐式类型转换。

### 为什么在C#开发中隐式操作符很重要？

理解并使用C#中的隐式操作符可以帮助软件工程师通过简化类型转换编写更清晰、更可读的代码。它们提供了一种方便的方式来处理类型转换，而无需显式强制类型转换，导致代码更简洁、易于维护。

### C#中的隐式操作符如何工作？

在两种类型之间定义了隐式操作符时，编译器会在需要隐式类型转换时自动调用它。操作符无缝地将一个类型的实例转换为另一个类型，如果转换有效的话。编译器在赋值和方法参数中检测和应用隐式操作符，简化了代码并使其更直观。

### 使用C#中的隐式操作符有什么好处？

使用隐式操作符可以提升代码可读性，简化类型转换，并减少对显式强制类型转换的需求。它们可以通过消除不必要的类型转换代码使代码更加简洁，改善代码可维护性并减少强制类型转换错误的机会。当然，过度使用这个功能，创建在特定上下文之外可能没有意义的转换，或可能丢失数据精度，也是很容易发生的。

### C#中隐式操作符的一些用例是什么？

隐式操作符通常用于转换具有自然关系或可以逻辑地解释为彼此的类型。一些常见的用例包括自定义类之间的转换、具有安全范围约束的数字类型之间的转换，以及简化从一种数据结构到另一种数据结构的转换。
