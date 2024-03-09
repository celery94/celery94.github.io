---
pubDatetime: 2024-03-09
tags: ["C#", "Abstraction", "Encapsulation", "OOP"]
source: https://code-maze.com/csharp-difference-between-abstraction-and-encapsulation/
author: Almir Tihak
title: C#中抽象与封装的区别
description: 探索C#中抽象与封装的区别。了解它们对代码的影响并发现高效C#的本质。
---

# C#中抽象与封装的区别

> ## 摘要
>
> 探索C#中抽象与封装的区别。了解它们对代码的影响并发现高效C#的本质。
>
> 原文 [Difference Between Abstraction and Encapsulation in C#](https://code-maze.com/csharp-difference-between-abstraction-and-encapsulation/)

---

让我们探索C#中抽象与封装的区别。

抽象和封装是面向对象编程（OOP）中的基本概念，并且在C#中共存。它们各自在类和对象的设计与实现中发挥关键作用，尽管它们服务于不同的目的。

要下载本文的源代码，您可以访问我们的 [GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/csharp-intermediate-topics/AbstractionVsEncapsulationInCSharp)。

让我们从探索C#中的抽象开始。

## 探索C#中的抽象

面向对象编程依赖于抽象，C#提供了多种实现这一概念的方法。**抽象涉及隐藏复杂的实现细节，只公开对象的必要特性。**这一思想通常通过使用抽象类和接口来实践。

抽象类作为模板不能直接实例化。它们可以包含抽象方法，这些方法作为基本方法并要求继承它们的类进行实现。此外，接口可以为方法、属性、索引器和事件定义声明，这是实现类的责任。

从C#8开始，接口可能有默认实现，派生类可以使用而无需显式实现它们的版本，这促进了在设计有组织、可维护和可扩展代码时的灵活性和适应性。

让我们用一个例子更好地理解抽象：

```csharp
public abstract class Animal
{
    public string Name { get; set; }
    public int Age { get; set; }
    public abstract void MakeSound();
}
public class Dog : Animal
{
    public override void MakeSound()
    {
        Console.WriteLine("Bark bark!");
    }
}
public class Cat : Animal
{
    public override void MakeSound()
    {
        Console.WriteLine("Meow!");
    }
}
```

这里，我们定义了一个抽象类，`Animal`，它包含`Name`和`Age`属性，以及一个抽象方法`MakeSound()`。从这里，我们创建两个具体类，`Dog`和`Cat`，它们都继承自我们的抽象类并提供`MakeSound()`方法的实现，描述每个动物发出的声音。

现在我们在`Program`类中看到我们的类是如何使用的：

```csharp
Animal dog = new Dog();
dog.Name = "Buddy";
dog.Age = 3;
Console.WriteLine($"{dog.Name} says:");
dog.MakeSound();
Animal cat = new Cat();
cat.Name = "Whiskers";
cat.Age = 2;
Console.WriteLine($"{cat.Name} says:");
cat.MakeSound();
```

我们创建了一个`Animal`的实例，并将其分配给一个新的`Dog`类。然后我们将属性`Name`和`Age`分别设置为“Buddy”和3。我们用`Cat`类做同样的事情，将属性设置为“Whiskers”和2。最后，我们输出每个动物的名字和它发出的声音。

让我们检查控制台输出：

```bat
Buddy says:
Bark bark!
Whiskers says:
Meow!
```

我们看到我们的`Cat`和`Dog`类都使用了它们的`MakeSound()`方法覆写。

### **\*抽象的优点\***

**抽象大大提高了代码复用性，通过建立共享接口或基类，促进多个类从一个共同的抽象继承，并最小化冗余。**

这种方法培养了可适应的设计，使得在不需要修改现有代码的情况下扩展功能成为可能。编程到接口或抽象类使得加入新特性变得轻松，避免了对现有代码库的干扰。使用抽象简化了测试和调试过程。此外，定义良好的接口有助于创建模拟对象进行测试和隔离组件进行调试，最终提高了整体软件质量。

让我们继续深入探讨封装 - 深入其概念基础、实际用例和总体目标。

## 探索C#中的封装

封装是面向对象编程（OOP）的主要支柱之一。它代表了一个关键概念，包含了在一个类中一起工作的属性和方法。封装限制了对对象内部状态的外部访问，并且限制了在类外直接操纵对象数据的访问。**它隐藏了对象的内部状态，仅通过定义的接口（公共方法或属性）允许访问。**

C#中的访问修饰符，如`public`、`private`、`protected`和`internal`，强制实现封装。私有成员仅在类内部可访问，公共成员允许外部访问，受保护的修饰符在内部和派生类中可访问。内部修饰符用于程序集内，即通过编译一个或多个代码文件创建的DLL或EXE。

让我们创建一个类来演示封装：

```csharp
public class BankAccount
{
    public string AccountNumber { get; }
    public decimal Balance { get; private set; }
    public BankAccount(string accountNumber, decimal initialBalance = 0)
    {
        AccountNumber = accountNumber;
        Balance = initialBalance;
    }
    public void Deposit(decimal amount)
    {
        if (amount > 0)
        {
            Balance += amount;
            Console.WriteLine($"Deposit successful. New account balance: {Balance}");
        }
        else
        {
            Console.WriteLine("Invalid amount for deposit.");
        }
    }
    public void Withdraw(decimal amount)
    {
        if (amount > 0 && amount <= Balance)
        {
            Balance -= amount;
            Console.WriteLine($"Withdrawal successful. New account balance: {Balance}");
        }
        else
        {
            Console.WriteLine("Invalid amount for withdrawal or insufficient funds.");
        }
    }
}
```

这里，我们创建了一个`BankAccount`类来演示封装的原理。在这个类中，我们将`AccountNumber`作为只读属性公开，并且C#允许通过构造函数设置值。此外，`Balance`属性有一个getter，使得检索值成为可能，并有一个私有setter，防止外部修改。此外，我们的构造函数通过接受一个账号和可选的初始余额来促进账户的初始化。我们有存款和取款的方法，每个方法都集成了适当的验证并提供信息。最终，我们的`BankAccount`类遵循了封装的原则，通过限制直接修改余额并遵循面向对象设计的最佳实践。

现在，让我们在`Program`类中使用我们的`BankAccount`类：

```csharp
BankAccount account = new BankAccount("1234567890");
account.Deposit(500);
account.Withdraw(200);
Console.WriteLine($"Final Account Information - Account Number: {account.AccountNumber}, Balance: {account.Balance}");
```

这里，我们创建了一个`BankAccount`类的实例，在构造函数中设置账号。然后，我们使用`Deposit()`向账户添加500，并使用`Withdraw()`取出200。

让我们检查控制台输出：

```bat
Deposit successful. New account balance: 500
Withdrawal successful. New account balance: 300
Final Account Information - Account Number: 1234567890, Balance: 300
```

### **\*封装的优点\***

在C#中，将封装视为一种强大的防御机制，与抽象区分开来。C#中抽象与封装的区别凸显了每个在塑造代码结构和功能方面扮演的独特角色。例如，封装阻止外部实体直接干预对象的数据和功能。此外，封装在加强程序安全和减少意外干涉或未经授权访问关键信息的风险方面发挥关键作用。

现在，让我们深入技术魔法：封装不仅仅是安全增强；它是软件维护的游戏规则改变者。通过使用封装，类能够无缝地允许其内部进行修改，而不会导致其他代码部分发生级联变化。这增加了灵活性，并有助于构建可扩展和适应性强的应用结构。

此外，封装充当了调试向导。通过在特定类内精确定位潜在问题，它简化了调试过程并提高了识别和解决问题的效率。这种方法简化了开发和维护阶段，确保了更健壮和弹性的代码库。

因此，封装不仅仅是一种安全特性；它是为了打造安全、高度可维护、灵活和高效代码的战略举措。

现在我们已经理解了抽象和封装，让我们理解两者的区别。

**C#中的抽象涉及通过创建类来简化复杂系统，这些类利用适当级别的继承来解决给定问题。**这强调了定义对象的基本特性，同时隐藏了不必要的细节。这种做法提供了双重优势：首先，它降低了代码复杂性；其次，它促进了代码复用。此外，抽象容纳多种实现，同时遵循标准化的接口。

相反，**封装专注于将数据和在数据上操作的方法打包到一个单元（通常是一个类）中，并通过访问修饰符控制对内部状态的访问。**这种方法不仅确保了数据安全，而且促进了模块化，并通过在明确定义的边界内限制组件来简化维护。

抽象是关于建立清晰和概念性的结构，而封装是关于隐藏实现细节并为与类互动提供明确定义的外部接口。它们共同促进了有效管理复杂性，在软件设计中提高代码复用、增强组织和安全性。

## 结论

在本文中，我们首先获得了对C#中抽象和封装的理解，通过示例探索了这两者，并查看了一些优点。通过这种理解，我们进而探讨了这两个概念之间的区别。
