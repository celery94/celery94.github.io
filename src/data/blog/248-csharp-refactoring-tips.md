---
pubDatetime: 2025-04-05 17:39:29
tags: [".NET", "C#"]
slug: csharp-refactoring-tips
source: https://www.milanjovanovic.tech/blog/5-awesome-csharp-refactoring-tips
title: 💡 5种C#代码重构技巧，带你解锁更优雅的编程方式！
description: 探索五种实用的C#代码重构技术，通过实际案例改善代码的可读性、测试性和可维护性。让你的代码更简洁、更高效、更可扩展！
---

# 💡 5种C#代码重构技巧，带你解锁更优雅的编程方式！

> 🎯 **目标读者**：中高级C#开发者及热爱编程优化的技术人员  
> 📖 **文章亮点**：方法提取、接口提取、类提取、函数式编程、逻辑下推五大技术，结合实际案例全面提升代码质量！

## 什么是代码重构？

代码重构是一种在不改变软件行为的情况下，改进代码结构的技术。它通过一系列小的代码转换，使代码变得更简洁、更易读、更易维护。🌟

今天，我们将通过一个真实案例，学习如何应用五种高效的代码重构技巧：

- ✂️ 方法提取（Extract Method）
- 🛠 接口提取（Extract Interface）
- 🏗 类提取（Extract Class）
- 🧮 函数式代码（Functional Code）
- 📦 逻辑下推（Pushing Logic Down）

## 🛠 初始代码 —— 改进的起点

下面是我们要优化的 `CustomerService` 类，它包含多个功能：验证输入参数、创建 `Customer`、计算信用额度，以及保存 `Customer` 到数据库。初始代码如下👇：

```csharp
public class CustomerService
{
    public bool AddCustomer(
        string firstName,
        string lastName,
        string email,
        DateTime dateOfBirth,
        int companyId)
    {
        if (string.IsNullOrEmpty(firstName) || string.IsNullOrEmpty(lastName))
        {
            return false;
        }

        if (!email.Contains('@') && !email.Contains('.'))
        {
            return false;
        }

        var now = DateTime.Now;
        var age = now.Year - dateOfBirth.Year;
        if (dateOfBirth.Date > now.AddYears(-age))
        {
            age -= 1;
        }

        if (age < 21)
        {
            return false;
        }

        var companyRepository = new CompanyRepository();
        var company = companyRepository.GetById(companyId);

        var customer = new Customer
        {
            Company = company,
            DateOfBirth = dateOfBirth,
            EmailAddress = email,
            Firstname = firstName,
            Surname = lastName
        };

        if (company.Type == "VeryImportantClient")
        {
            customer.HasCreditLimit = false;
        }
        else if (company.Type == "ImportantClient")
        {
            customer.HasCreditLimit = true;
            using var creditService = new CustomerCreditServiceClient();

            var creditLimit = creditService.GetCreditLimit(
                customer.Firstname,
                customer.Surname,
                customer.DateOfBirth);

            creditLimit *= 2;
            customer.CreditLimit = creditLimit;
        }
        else
        {
            customer.HasCreditLimit = true;
            using var creditService = new CustomerCreditServiceClient();

            var creditLimit = creditService.GetCreditLimit(
                customer.Firstname,
                customer.Surname,
                customer.DateOfBirth);

            customer.CreditLimit = creditLimit;
        }

        if (customer.HasCreditLimit && customer.CreditLimit < 500)
        {
            return false;
        }

        var customerRepository = new CustomerRepository();
        customerRepository.AddCustomer(customer);

        return true;
    }
}
```

这段代码虽然能正常运行，但存在以下问题：

- 📄 **可读性差**：方法接近100行，逻辑复杂。
- 🔍 **难以测试**：无法控制外部依赖。
- 🔧 **扩展性不足**：添加新功能需要修改现有代码。

让我们逐步优化这些问题！🚀

---

## ✂️ 技巧一：方法提取（Extract Method）

首先，我们优化输入参数验证逻辑。将验证和年龄计算提取到独立方法中，提升可读性和复用性：

### 提取年龄计算方法

```csharp
int CalculateAge(DateTime dateOfBirth, DateTime now)
{
    var age = now.Year - dateOfBirth.Year;
    if (dateOfBirth.Date > now.AddYears(-age))
    {
        age -= 1;
    }
    return age;
}
```

### 提取输入验证方法

```csharp
bool IsValid(
    string firstName,
    string lastName,
    string email,
    DateTime dateOfBirth)
{
    const int minimumAge = 21;

    return !string.IsNullOrEmpty(firstName) &&
           !string.IsNullOrEmpty(lastName) &&
           (email.Contains('@') || email.Contains('.')) &&
           CalculateAge(dateOfBirth, DateTime.Now) >= minimumAge;
}
```

优化后的主方法调用更加简洁：

```csharp
if (!IsValid(firstName, lastName, email, dateOfBirth))
{
    return false;
}
```

---

## 🛠 技巧二：接口提取（Extract Interface）

为了提升模块化和测试性，我们将数据仓库和服务类改为接口形式，并通过依赖注入实现解耦。🎯

### 使用依赖注入

我们不再直接实例化 `CompanyRepository` 和 `CustomerCreditServiceClient`，而是将它们作为构造函数参数传入：

```csharp
public class CustomerService(
    ICompanyRepository companyRepository,
    ICustomerRepository customerRepository,
    ICustomerCreditService creditService)
{
    // ...
}
```

这不仅提升了灵活性，还使得测试时可以轻松模拟依赖。

---

## 🏗 技巧三：类提取（Extract Class）

信用额度的计算逻辑复杂且容易出错，我们将其抽离到一个专用类中，以遵循单一职责原则（SRP）。

### 信用额度计算类

使用 `switch` 表达式替代冗长的 `if-else` 结构，同时支持枚举类型，更加清晰直观：

```csharp
public class CreditLimitCalculator(ICustomerCreditService creditService)
{
    public (bool HasCreditLimit, decimal? CreditLimit) Calculate(
        Customer customer, Company company)
    {
        return company.Type switch
        {
            CompanyType.VeryImportantClient => (false, null),
            CompanyType.ImportantClient => (true, GetCreditLimit(customer) * 2),
            _ => (true, GetCreditLimit(customer))
        };
    }

    private decimal GetCreditLimit(Customer customer)
    {
        return creditService.GetCreditLimit(
            customer.FirstName, customer.LastName, customer.DateOfBirth);
    }
}
```

---

## 🧮 技巧四：函数式代码（Functional Code）

通过使用枚举和表达式简化信用额度逻辑，减少重复代码，并提高扩展性。

### 定义公司类型枚举

```csharp
public enum CompanyType
{
    Regular = 0,
    ImportantClient = 1,
    VeryImportantClient = 2
}
```

---

## 📦 技巧五：逻辑下推（Pushing Logic Down）

将创建 `Customer` 的逻辑移至领域模型中，进一步简化 `CustomerService` 的职责。

### 静态工厂模式创建客户

```csharp
public class Customer
{
    public static Customer Create(
        Company company,
        string firstName,
        string lastName,
        string email,
        DateTime dateOfBirth,
        CreditLimitCalculator creditCalculator)
    {
        var customer = new Customer
        {
            Company = company,
            FirstName = firstName,
            LastName = lastName,
            EmailAddress = email,
            DateOfBirth = dateOfBirth
        };

        (customer.HasCreditLimit, customer.CreditLimit) =
            creditCalculator.Calculate(customer, company);

        return customer;
    }
}
```

---

## 🚀 优化后的代码结构

最终的 `CustomerService` 简洁、清晰，同时更易于测试和扩展：

```csharp
public class CustomerService(
    ICompanyRepository companyRepository,
    ICustomerRepository customerRepository,
    CreditLimitCalculator creditCalculator)
{
    public bool AddCustomer(
        string firstName,
        string lastName,
        string email,
        DateTime dateOfBirth,
        int companyId)
    {
        if (!IsValid(firstName, lastName, email, dateOfBirth))
        {
            return false;
        }

        var company = companyRepository.GetById(companyId);

        var customer = Customer.Create(
            company,
            firstName,
            lastName,
            email,
            dateOfBirth,
            creditCalculator);

        if (customer.IsUnderCreditLimit())
        {
            return false;
        }

        customerRepository.AddCustomer(customer);

        return true;
    }
}
```

---

## 🔍 总结与下一步

通过本次优化，我们改善了代码的：

- ✅ 可读性
- ✅ 可测试性
- ✅ 可维护性
