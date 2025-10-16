---
pubDatetime: 2025-04-01 12:00:04
tags: [".NET", "ASP.NET Core"]
slug: dependency-injection-aspnet-core-guide
source: https://codewithmukesh.com/blog/dependency-injection-in-aspnet-core-explained/
title: 深入浅出ASP.NET Core依赖注入：构建高效、可扩展的应用
description: 探索依赖注入在ASP.NET Core中的应用，从基础概念到高级实践，全方位助力开发者构建松耦合、可测试和可扩展的应用架构。
---

# 🌟 深入浅出ASP.NET Core依赖注入：构建高效、可扩展的应用

依赖注入（Dependency Injection, DI）是ASP.NET Core框架的核心功能之一，它不仅是一种设计模式，更是构建现代化、高效软件应用的关键。本文将带你全面了解DI的概念、优势及其在ASP.NET Core中的应用，并通过大量示例和实践指导帮助你快速掌握这项技术。

---

## 🚀 什么是依赖注入（Dependency Injection）？

依赖注入是一种设计模式，它的核心思想是**让类获取它需要的依赖，而不是让类自己创建这些依赖**。这种方法不仅能减少代码的耦合，还能提升测试性和可维护性。

举个例子，如果一个类需要发送邮件，它不应该负责创建邮件服务，而是直接声明“我需要一个能发送邮件的服务”。DI容器会根据需求为它提供适当的服务实现。

### 🌟 优势：

1. **松耦合**：模块之间相互独立，修改或替换某个模块不会影响其他模块。
2. **易于测试**：通过注入模拟对象（Mock），可以轻松进行单元测试。
3. **架构灵活性**：支持动态替换实现，便于扩展和维护。

---

## 🔧 ASP.NET Core中的内置DI支持

ASP.NET Core自带一个轻量级、高效的DI容器，它与框架深度集成，使得服务注册和注入变得简单易用。

### ✨ 示例：服务注册与使用

在`Program.cs`中注册服务：

```csharp
builder.Services.AddScoped<IEmailService, EmailService>();
```

在控制器中使用：

```csharp
public class NotificationController(IEmailService emailService) : ControllerBase {
    public IActionResult SendNotification() {
        emailService.SendEmail();
        return Ok("通知已发送！");
    }
}
```

无论是控制器、最小API（Minimal API）还是中间件，都可以使用这种方式实现依赖注入。

---

## 🛠 DI的三种主要形式

### 1️⃣ **构造函数注入**（最常见且推荐）

通过类的构造函数显式声明依赖，使得类的职责更加清晰。

```csharp
public class ReportService(IEmailService emailService) {
    public void GenerateReport() => emailService.Send();
}
```

### 2️⃣ **方法注入**（Minimal API常用）

在路由处理方法中直接声明依赖，简化代码。

```csharp
app.MapGet("/reports", (IReportService reportService) => {
    var report = reportService.Generate();
    return Results.Ok(report);
});
```

### 3️⃣ **属性注入**（不推荐）

通过公共属性设置依赖，容易隐藏类实际需求，降低可测试性。

```csharp
public class ReportService {
    public ILogger<ReportService> Logger { get; set; }
    public void Generate() => Logger?.LogInformation("报告已生成");
}
```

---

## 🏗 在`Program.cs`中注册服务

服务注册是DI的基础操作，你可以选择以下方法来注册服务：

### 🔑 常规注册

根据服务生命周期选择适当的方法：

```csharp
builder.Services.AddScoped<IOrderService, OrderService>();
builder.Services.AddSingleton<INotificationService, EmailNotificationService>();
builder.Services.AddTransient<IPaymentService, StripePaymentService>();
```

### ⚡ 使用Lambda表达式注册

适用于需要动态配置的场景：

```csharp
builder.Services.AddScoped<IInvoiceService>(sp => {
    var logger = sp.GetRequiredService<ILogger<InvoiceService>>();
    return new InvoiceService(logger, "INVOICE_PREFIX");
});
```

### 📋 服务注册的组织方式

为了保持项目结构清晰，可将服务注册提取到扩展方法中：

```csharp
public static class ServiceCollectionExtensions {
    public static IServiceCollection AddApplicationServices(this IServiceCollection services) {
        services.AddScoped<IOrderService, OrderService>();
        services.AddScoped<ICustomerService, CustomerService>();
        return services;
    }
}
```

然后在`Program.cs`中调用：

```csharp
builder.Services.AddApplicationServices();
```

---

## 💡 DI与接口驱动设计：从理论到实践

在DI中使用接口是一种最佳实践，它能进一步解耦代码，并增强扩展性。

### 🛠 示例：

定义接口：

```csharp
public interface IEmailService {
    void SendEmail();
}
```

实现接口：

```csharp
public class EmailService : IEmailService {
    public void SendEmail() => Console.WriteLine("发送邮件...");
}
```

在业务类中使用：

```csharp
public class NotificationService(IEmailService emailService) {
    public void Notify() => emailService.SendEmail();
}
```

通过这种设计，你可以轻松替换`EmailService`的具体实现，而无需修改核心逻辑。

---

## 🌀 高级场景：条件注册与工厂委托

在某些情况下，你需要根据运行时条件动态选择服务实现。这时可以使用条件注册或工厂委托。

### 🎯 条件注册示例：

```csharp
builder.Services.AddScoped<StripePaymentService>();
builder.Services.AddScoped<RazorpayPaymentService>();
builder.Services.AddScoped<IPaymentService>(provider => {
    var useStripe = provider.GetRequiredService<IConfiguration>().GetValue<bool>("UseStripe");
    return useStripe ? provider.GetRequiredService<StripePaymentService>() : provider.GetRequiredService<RazorpayPaymentService>();
});
```

### ⚙ 工厂委托示例：

定义工厂委托：

```csharp
public delegate IEmailService EmailServiceFactory(string region);
```

注册服务：

```csharp
builder.Services.AddScoped<EmailServiceFactory>(sp => region => {
    var config = sp.GetRequiredService<IConfiguration>();
    var settings = config.GetSection($"Email:{region}").Get<EmailSettings>();
    return new EmailService(settings);
});
```

使用工厂创建服务：

```csharp
public class NotificationSender(EmailServiceFactory emailFactory) {
    public void Send(string region) {
        var service = emailFactory(region);
        service.SendEmail();
    }
}
```

---

## ❌ 常见错误及如何避免

1. 🚫 **服务定位器反模式**
   避免直接通过`IServiceProvider`解析服务。推荐使用构造函数注入。

   ```csharp
   public class BadService(IServiceProvider provider) {
       public void DoWork() => provider.GetRequiredService<IRepository>().DoWork();
   }
   ```

2. ⚠️ **过多的依赖**
   如果类需要超过5个依赖，说明该类职责可能过重，需要拆分。

3. 🔍 **未正确注册服务**
   忘记在`Program.cs`中注册服务会导致运行时错误。

4. 🕒 **服务生命周期混乱**
   避免将作用域服务注入到单例服务中，否则可能导致意外行为。

---

## 🌈 总结：拥抱DI，提升代码质量

通过依赖注入，你可以构建更干净、更模块化的ASP.NET Core应用。它不仅简化了代码逻辑，还为你的项目提供了更高的灵活性和可维护性。

如果你正在学习或使用ASP.NET Core，那么掌握DI是必不可少的一步。希望本文能帮助你深入理解DI，并在实践中灵活运用。

📖 **下一步学习：**

- 服务生命周期（Scoped、Singleton、Transient）
- Keyed Services（ASP.NET Core 8新特性）

👉 如果你觉得这篇文章对你有帮助，别忘了分享给你的开发者朋友！😊
