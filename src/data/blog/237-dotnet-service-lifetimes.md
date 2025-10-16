---
pubDatetime: 2025-04-01 12:03:40
tags: [".NET", "Architecture", "Productivity"]
slug: dotnet-service-lifetimes
source: https://codewithmukesh.com/blog/when-to-use-transient-scoped-singleton-dotnet/
title: 探索.NET服务生命周期：如何正确使用Transient、Scoped和Singleton
description: 本文深入解析.NET应用中的服务生命周期管理，详细介绍Transient、Scoped和Singleton三种生命周期的特点及最佳实践，同时帮助开发者避免常见错误，构建高性能稳定的应用架构。
---

# 探索.NET服务生命周期：如何正确使用Transient、Scoped和Singleton 🚀

在现代.NET应用开发中，**服务生命周期（Service Lifetimes）**是依赖注入（Dependency Injection）核心概念之一。选择正确的生命周期不仅能优化性能，还能避免意外的bug和资源泄漏。今天，让我们深入探讨.NET中的三种服务生命周期：**Transient**、**Scoped** 和 **Singleton**，并分享实用的最佳实践和避坑指南。

---

## 什么是服务生命周期？🤔

服务生命周期定义了一个服务实例在应用中存活的时间。每当我们在.NET中注册服务时，都会指定其生命周期，这决定了：

- 是否每次请求都创建新的实例？
- 是否可以在同一请求中复用实例？
- 实例是否贯穿整个应用生命周期？

### 三种主要生命周期：

1. **Transient**（瞬态）：每次请求都生成新实例。
2. **Scoped**（范围）：一个请求内共享一个实例。
3. **Singleton**（单例）：整个应用共享一个实例。

不同的服务有不同的职责，选择合适的生命周期至关重要。如果选错，可能导致性能问题、线程安全隐患，甚至难以调试的Bug。

---

## 为什么服务生命周期如此重要？💡

正确选择生命周期可以确保：

- **内存使用优化**：避免不必要的对象创建和销毁。
- **线程安全**：防止共享状态引发竞争条件。
- **数据一致性**：确保服务仅在合适的范围内共享数据。
- **请求隔离**：在多用户请求场景中避免数据混乱。

错误配置可能导致：

- Scoped服务注入到Singleton中，抛出运行时异常。
- Singleton服务存储用户数据导致竞态条件。
- 频繁创建Transient对象损耗性能。

总之，选择合适的生命周期是保证应用高效、稳定运行的关键！

---

## 深入理解三种生命周期 🔍

### 1. Transient：每次都是全新开始 ✨

Transient服务每次被请求时都会生成一个新的实例，非常适合以下场景：

- **无状态服务**：如格式化器、映射器或构建器。
- **轻量级操作**：不需要保存任何共享数据。

📌 **代码示例：**

```csharp
builder.Services.AddTransient<IEmailSender, SmtpEmailSender>();
```

✅ **适用场景：**

- 无状态操作（如验证器、映射器）。
- 短期任务，不需要跟踪生命周期。

⚠️ **注意事项：**

- 避免为昂贵的构造服务使用Transient。
- 如果服务包含非托管资源，记得手动释放。

### 2. Scoped：为每个请求保驾护航 🚧

Scoped服务在每个请求中仅创建一次，非常适合需要共享上下文或状态的数据处理任务。例如：

- 当前用户信息（如用户ID）。
- 数据库上下文（如Entity Framework Core中的DbContext）。

📌 **代码示例：**

```csharp
builder.Services.AddScoped<IUserContext, HttpUserContext>();
```

✅ **适用场景：**

- 跟踪HTTP请求或特定范围内的数据。
- 使用EF Core进行数据库操作。

⚠️ **注意事项：**

- 切勿将Scoped服务注入到Singleton中。
- 在非HTTP请求场景中需要手动创建Scope。

### 3. Singleton：整个应用的守护者 🏛️

Singleton服务贯穿整个应用生命周期，是跨线程共享的最佳选择。适合以下场景：

- 配置提供者。
- 日志记录器或时间服务。
- 应用级缓存。

📌 **代码示例：**

```csharp
builder.Services.AddSingleton<IClock, SystemClock>();
```

✅ **适用场景：**

- 全局无状态逻辑，如日志记录。
- 不依赖用户或请求上下文。

⚠️ **注意事项：**

- 避免存储可变状态，否则需确保线程安全。
- 如果依赖Scoped服务，需要使用`IServiceScopeFactory`手动创建Scope。

---

## 实际案例：如何选择正确的生命周期 🛠️

以下是一些典型开发场景及对应生命周期选择：

### 🌟 Transient – 无状态轻量级服务

例如：

```csharp
builder.Services.AddTransient<IEmailBuilder, DefaultEmailBuilder>();
```

适合无状态、短期使用的服务，如密码哈希器或电子邮件构建器。

---

### 🌟 Scoped – 请求上下文相关的服务

例如：

```csharp
builder.Services.AddScoped<ICurrentUserService, HttpContextUserService>();
builder.Services.AddScoped<ApplicationDbContext>();
```

适合跟踪用户信息或数据库操作的场景，确保每个请求之间数据隔离。

---

### 🌟 Singleton – 应用级无状态基础设施

例如：

```csharp
builder.Services.AddSingleton<IClock, SystemClock>();
```

适合全局共享的逻辑，如日志记录或缓存管理。

⚠️ 注意事项：
如果需要Scoped数据，例如用户信息，请通过`IServiceScopeFactory`动态获取，而不是直接注入！

---

## 避免常见错误 ⛔

1️⃣ **Scoped服务注入到Singleton中**

- 修复方法：使用`IServiceScopeFactory`动态解析Scoped服务。

2️⃣ **Singleton存储可变状态**

- 修复方法：使用线程安全机制，如`lock`或`ConcurrentDictionary`。

3️⃣ **Transient服务频繁创建**

- 修复方法：对于昂贵构造资源，考虑使用Scoped或Singleton。

4️⃣ **未释放手动解析的Transient服务**

- 修复方法：使用`using`语句或显式调用`Dispose()`。

5️⃣ **假设Scoped自动适用于非HTTP请求**

- 修复方法：通过`IServiceScopeFactory.CreateScope()`手动创建Scope。

---

## .NET内部如何管理服务生命周期 🛠️

.NET框架通过以下机制管理服务：

1. 服务注册时保存到`ServiceDescriptor`中，包括类型、实现和生命周期。
2. 服务提供者根据生命周期规则创建实例：
   - Singleton实例存储在根级别字典中。
   - Scoped实例缓存于当前Scope。
   - Transient始终创建新实例。
3. 容器会自动释放实现`IDisposable`接口的服务。

了解这些机制，有助于我们更好地调试和设计高效系统！

---

## 最佳实践 💎

1️⃣ 让Singleton保持无状态并确保线程安全。  
2️⃣ 为应用级逻辑优先使用Scoped。  
3️⃣ 对无状态轻量级任务使用Transient。  
4️⃣ 明确托管与非托管资源的责任分工。  
5️⃣ 匹配生命周期与具体业务需求，而非仅考虑性能优化。

🎯 小贴士：根据实际需求设计不同接口，将生命周期与逻辑职责分离。例如，为后台任务设计专用接口以处理Scoped依赖。

---

## 总结 🎉

正确选择Transient、Scoped和Singleton，不仅能构建高效稳定的应用，还能显著提升代码质量和可维护性：

✔️ 使用**Transient**处理短期无状态任务。  
✔️ 使用**Scoped**隔离请求上下文数据。  
✔️ 使用**Singleton**管理全局无状态逻辑。
