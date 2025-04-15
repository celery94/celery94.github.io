---
pubDatetime: 2025-04-15 22:07:24
tags: [.NET, C#, 编程, 软件开发, 技术文章]
slug: dotnet10-extension-keyword
source: https://thecodeman.net/posts/dotnet10-extension
title: 🚀揭开.NET 10的新篇章：`extension`关键字让扩展方法更强大！
description: .NET 10 引入了新的 `extension` 关键字，助力开发者更高效地组织逻辑、扩展类型，并提升代码的清晰度与缓存友好性。本文将通过代码示例与实际场景，带你深入了解这一新功能的潜力。
---

# 🚀揭开.NET 10的新篇章：`extension`关键字让扩展方法更强大！

2025 年，微软发布了 .NET 10 以及 C# 14（Preview 3），其中一个令人兴奋的新特性是 `extension` 关键字的引入。这个特性彻底改变了我们处理扩展方法的方式，让代码组织更加清晰、逻辑分组更加自然。🌟

在这篇文章中，我们将探讨：

- 新扩展特性的核心功能
- 它为何重要
- 实际应用场景中的优雅解决方案
- 如何通过它优化代码组织和逻辑

让我们一起来深挖这个技术宝藏吧！

---

## 🔍什么是`extension`关键字？

在 .NET 10 中，`extension` 关键字允许开发者为任何类型定义 **扩展块**，支持以下功能：

1. **扩展属性**：不仅限于方法，还可以定义属性。
2. **私有后备字段**：可以在扩展块内进行缓存，提升性能。
3. **分组逻辑**：将相关逻辑集中到一个局部范围内。
4. **静态扩展方法**：定义与类型无关的工具方法。

### 📖基础语法

以下是新的扩展块语法的基本示例：

```csharp
public static class MyExtensions
{
    extension(TargetType instance)
    {
        public ReturnType PropertyOrMethod => ...;
    }

    extension static
    {
        public static ReturnType StaticHelper() => ...;
    }
}
```

是不是看起来很简洁？它不仅让代码更清晰，还提升了可维护性。

---

## ⚙️实际应用场景：多租户 SaaS 和 HttpContext

假设你正在开发一个多租户 SaaS 应用。你需要解析用户 ID、检查用户是否为租户管理员，并提供默认值和验证逻辑。传统方式可能会让这些逻辑散布在多个静态方法中，难以维护。而新的扩展块则将所有相关逻辑优雅地聚合在一起：

### 💡代码示例：

```csharp
public static class MultiTenantHttpContextExtensions
{
    extension(HttpContext ctx)
    {
        private string? _tenantId;
        private Guid? _userId;

        public string TenantId =>
            _tenantId ??=
                ctx.User.Claims.FirstOrDefault(c => c.Type == "tenant_id")?.Value
                ?? throw new UnauthorizedAccessException("Tenant ID missing");

        public Guid UserId =>
            _userId ??=
                Guid.TryParse(
                    ctx.User.Claims.FirstOrDefault(c => c.Type == "user_id")?.Value, out var id)
                ? id
                : throw new UnauthorizedAccessException("User ID invalid");

        public bool IsTenantAdmin =>
            ctx.User.IsInRole("Admin") || ctx.Request.Headers["X-Tenant-Admin"] == "true";

        public string? GetHeader(string name) =>
            ctx.Request.Headers.TryGetValue(name, out var value)
                ? value.ToString()
                : null;
    }

    extension static
    {
        public static string DefaultTenantId => "public";

        public static bool IsValidTenantId(string? id) =>
            !string.IsNullOrWhiteSpace(id) && id.All(char.IsLetterOrDigit);
    }
}
```

### 🎯优势：

1. **逻辑清晰**：所有与 HttpContext 的逻辑集中在一个地方。
2. **缓存友好**：使用私有字段 (`_tenantId`, `_userId`) 实现懒加载。
3. **领域逻辑增强**：更易读、更易维护。

---

## 📦外部模型扩展的妙用

当需要扩展第三方模型时，新功能也能派上用场。例如，我们有一个简单的 `OrderDto`：

```csharp
public class OrderDto
{
    public List<OrderItemDto> Items { get; set; }
    public string Status { get; set; }
}
```

使用扩展块，可以轻松添加领域逻辑，而无需修改原始类：

### 💡代码示例：

```csharp
public static class OrderExtensions
{
    extension(OrderDto order)
    {
        public decimal TotalAmount =>
            order.Items.Sum(i => i.Quantity * i.PricePerUnit);

        public bool IsComplete =>
            order.Status == "Completed";

        public int TotalItems =>
            order.Items.Sum(i => i.Quantity);
    }
}
```

### 🌟使用示例：

```csharp
if (order.TotalAmount > 1000 && order.IsComplete)
{
    // Do something
}
```

这样不仅提高了代码表达力，也避免了对原始类的侵入性修改。

---

## 📊为什么不直接用传统扩展方法？

来看看传统扩展方法与新扩展块的对比吧：

![Image 1: Comparing with Extension Methods](https://thecodeman.net/images/blog/posts/dotnet10-extension/comparing-with-extension-methods.png)

新的方式不仅简化了逻辑分组，还允许使用私有字段进行状态缓存。这是一种从根本上改进代码组织的范式变化。

---

## 📝注意事项与建议

### ⚠️注意：

1. 当前该功能仅在 **.NET 10 Preview 3** 和 **C# 14** 中提供。
2. 语法和工具支持可能仍在不断完善中。
3. 此特性是完全向后兼容的，对现有扩展方法没有影响。

### 📌建议：

当需要为某个类型添加 **多种行为** 且这些行为紧密相关时，使用扩展块会是最佳选择。例如：

- DTO 转换
- HTTP 上下文处理逻辑
- 外部模型的计算值和领域增强
- 特定领域逻辑（如 `IsActive`, `TotalAmount`, `NeedsSync` 等）

这种方式能够显著提升代码的清晰度、组织性和可维护性。

---

## ✨总结与展望

.NET 10 中引入的 `extension` 关键字可能不会立刻吸引所有人的注意，但它解决了开发者在组织代码时的一些痛点，尤其是对于那些注重架构设计、领域建模和代码可维护性的开发者来说，这是一个强大的工具。

💬如果你想了解如何将这一特性应用于：

- CQRS 助手
- ViewModel 构建器
- ASP.NET Core 服务管道

请留言告诉我！我已经开始计划重构一些旧项目，以充分利用这一新特性。🎉
