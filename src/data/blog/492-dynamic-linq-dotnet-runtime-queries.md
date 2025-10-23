---
pubDatetime: 2025-10-20
title: .NET 中的动态 LINQ：运行时构建查询的优雅解决方案
description: 深入探讨如何使用动态 LINQ 在 .NET 中构建运行时查询，避免条件分支爆炸，同时保持 EF Core 的 SQL 转换能力和性能优势，适用于管理后台、报表系统和多租户场景。
tags: [".NET", "LINQ", "EF Core", "Performance"]
slug: dynamic-linq-dotnet-runtime-queries
source: https://thecodeman.net/posts/dynamic-linq-in-dotnet
---

# .NET 中的动态 LINQ：运行时构建查询的优雅解决方案

## 引言

在实际的 .NET 项目开发中，我们经常会遇到这样的场景：最初设计了一个简单的搜索端点，但随着业务发展，产品经理或用户不断提出新的筛选需求——"能否按状态筛选？""能按最后登录时间排序吗？""市场部想保存客户细分规则"——你精心编写的 LINQ 查询逐渐演变成充满条件分支的代码森林，每次调整都需要重新部署。

动态 LINQ 为这类问题提供了优雅的解决方案。它允许我们在运行时构建查询条件，同时保持真正的 LINQ 执行语义，确保 Entity Framework Core 能够将查询转换为高效的 SQL 语句。本文将深入探讨动态 LINQ 的应用场景、工作原理、核心方法以及安全防护措施。

## 为什么需要动态谓词

### 传统静态 LINQ 的困境

当我们使用静态 LINQ 处理可选筛选条件时，代码往往会变成这样：

```csharp
var query = context.Customers.AsQueryable();

if (onlyActive)
    query = query.Where(x => x.Status == CustomerStatus.IsActive);

if (since is not null)
    query = query.Where(x => x.LastLogon >= since);

if (!string.IsNullOrWhiteSpace(search))
    query = query.Where(x => x.Name.Contains(search));

var list = await query.OrderBy(x => x.Name).ToListAsync();
```

这种实现方式存在几个明显的问题：

**条件分支爆炸**：随着筛选条件的增加，代码中的 `if` 语句数量呈线性增长，可读性和维护性急剧下降。每个新的筛选需求都需要添加新的条件分支，导致代码结构越来越复杂。

**查询形状不一致**：不同的条件组合会产生不同的查询管道，这不仅增加了代码复杂度，还可能导致性能分析和优化变得困难。

**频繁部署**：每次添加或修改筛选条件都需要修改代码并重新部署应用程序，这在快速迭代的业务场景中显得尤为繁琐。

### 动态 LINQ 的适用场景

动态 LINQ 特别适合以下三类场景：

**无界限筛选**：管理后台、报表构建器、保存的搜索条件等场景，用户可以混合使用各种字段和操作符，这些组合在编译时无法预测。例如，用户可能今天想按"状态 + 地区"筛选，明天又想加上"最近活跃时间"的条件。

**租户可变性**：在白标签应用（White-label Applications）中，每个客户或租户可能需要略微不同的业务规则。与其为每个租户维护独立的代码分支，不如将这些规则配置化，通过动态 LINQ 在运行时应用。

**保持 EF Core 性能**：动态 LINQ 库会将字符串表达式解析为表达式树（Expression Tree），然后调用真正的 LINQ 方法（如 `Where`、`OrderBy` 等）作用于 `IQueryable`。这意味着 Entity Framework Core 仍然能够将查询转换为 SQL，在数据库层面执行筛选和排序，而不是在内存中处理。

如果你的筛选条件是用户定义的、租户定义的或频繁变化的，动态 LINQ 能够将持续的代码改动转变为简单的规则更新。

## 动态 LINQ 的工作原理

### 核心机制

动态 LINQ 的实现依赖于 C# 的表达式树（Expression Trees）机制。使用诸如 `Z.Expressions`（C# Eval Expression）这样的库，你可以提供一个字符串形式的表达式，并调用动态扩展方法，如 `WhereDynamic`、`OrderByDynamic`、`SelectDynamic` 和 `FirstOrDefaultDynamic`。

在底层，库会将字符串解析为表达式树，然后调用实际的 LINQ 操作符。这个机制同时适用于 `IEnumerable` 和 `IQueryable`（包括 EF Core）。

### 表达式书写形式

你可以使用两种形式来编写动态表达式：

**仅主体形式（Body-only）**：

```csharp
"x.Status == 0 && x.LastLogon >= DateTime.Now.AddMonths(-1)"
```

**完整 Lambda 形式**：

```csharp
"x => x.Status == 0 && x.LastLogon >= DateTime.Now.AddMonths(-1)"
```

这两种形式在功能上是等价的，可以根据个人偏好和代码风格选择使用。完整 Lambda 形式更接近我们熟悉的 C# Lambda 表达式语法，而仅主体形式更简洁。

## 核心方法详解

在日常开发中，我们主要会用到以下几个核心方法。这些方法覆盖了 80% 的实际应用场景。

### WhereDynamic：动态筛选的主力

`WhereDynamic` 是最常用的方法，用于构建动态筛选条件。它能够优雅地解决条件分支爆炸的问题。

使用动态 LINQ 重写前面的示例：

```csharp
using System.Linq;
using Z.Expressions;

string filter = "x => true"; // 初始条件为真

if (onlyActive)
    filter += " && x.Status == 0"; // 假设枚举值 0 = IsActive

if (since is not null)
    filter += $@" && x.LastLogon >= DateTime.Parse(""{since:yyyy-MM-dd}"")";

if (!string.IsNullOrWhiteSpace(search))
    filter += $@" && x.Name.Contains(""{search}"")";

var list = await context.Customers
    .WhereDynamic(filter)
    .OrderBy(x => x.Name)
    .ToListAsync();
```

这种实现的优势在于：

- **单一查询管道**：无论筛选条件如何变化，查询的结构保持一致
- **无重复查询**：避免了针对不同条件组合编写多个查询
- **易于扩展**：添加新的筛选条件只需要在字符串中追加条件，无需改变查询形状

### 传递变量而非字面量

你不必将所有值都以字面量形式注入到字符串中。可以传递一个上下文对象（匿名类型、字典、ExpandoObject 或普通类），并在表达式内部通过名称引用其成员：

```csharp
var context = new
{
    IsActive = CustomerStatus.IsActive,
    LastMonth = DateTime.Now.AddMonths(-1)
};

var recentActive = await dbContext.Customers
    .WhereDynamic("x => x.Status == IsActive && x.LastLogon >= LastMonth", context)
    .ToListAsync();
```

这种方式更加安全和清晰，避免了字符串拼接可能带来的问题，同时也使表达式更易于阅读和维护。

### OrderByDynamic 和 ThenByDynamic：动态排序

在许多场景下，用户需要在运行时选择排序列和排序方向。使用动态排序可以轻松实现这一需求：

```csharp
string sort = sortColumn switch
{
    "Name"       => "x => x.Name",
    "LastLogon"  => "x => x.LastLogon",
    "TotalSpent" => "x => x.TotalSpent",
    _            => "x => x.Name" // 默认排序
};

var ordered = await context.Customers
    .OrderByDynamic(sort)
    .ThenByDynamic("x => x.CustomerID") // 次要排序键
    .ToListAsync();
```

这个实现使用了白名单模式，确保只有预定义的列才能用于排序，避免了潜在的安全风险。动态 LINQ 库提供了 `OrderByDynamic`、`ThenByDynamic` 以及它们的降序变体，专门设计用于"用户选择列"的场景。

### SelectDynamic：动态投影

对于导出功能、报表界面或轻量级 API 响应，你可能需要根据用户请求动态选择要返回的字段：

```csharp
// 客户端选择列："CustomerID,Name,Country"
var selectedColumns = new[] { "CustomerID", "Name", "Country" };
var allowedCols = new HashSet<string> { "CustomerID", "Name", "Email", "Country", "TotalSpent" };

var projections = selectedColumns
    .Select(c => c.Trim())
    .Where(c => allowedCols.Contains(c));

var selectExpr = "x => new { " +
    string.Join(", ", projections.Select(c => $"{c} = x.{c}")) +
    " }";

var rows = await context.Customers
    .WhereDynamic("x => x.Status == 0")
    .SelectDynamic(selectExpr)
    .ToListAsync();
```

这种方式特别适合需要灵活控制返回字段的场景，如数据导出、自定义报表等。EF Core 仍然能够处理这种动态投影的转换，生成高效的 SQL 查询。

### FirstOrDefaultDynamic：动态单一结果检索

当你需要根据运行时条件快速查找单条记录时，可以使用 `FirstOrDefaultDynamic`：

```csharp
var customer = await context.Customers
    .FirstOrDefaultDynamic("x => x.Email == \"stefan@thecodeman.net\" && x.Status == 0");
```

这个方法非常适合"打开特定结果"或基于运行时条件的验证检查场景。

### Execute：链式动态管道（谨慎使用）

如果你确实需要在单个动态字符串中执行多个 LINQ 步骤（筛选 → 排序 → 投影 → 物化），可以使用 `Execute` API：

```csharp
var env = new
{
    IsActive = CustomerStatus.IsActive,
    LastMonth = DateTime.Now.AddMonths(-1)
};

var result = context.Customers.Execute<IEnumerable>(
    "Where(x => x.Status == IsActive && x.LastLogon >= LastMonth)" +
    ".Select(x => new { x.CustomerID, x.Name })" +
    ".OrderBy(x => x.CustomerID).ToList()",
    env);
```

这是一个"逃生舱"——功能强大，但我更倾向于使用独立的 `*Dynamic` 方法，因为它们具有更好的可读性和组合性。过度使用 `Execute` 可能会使代码难以理解和调试。

## 实战模式与应用场景

### 管理后台查询构建器

在企业管理系统中，管理员通常需要灵活的查询能力。实现思路如下：

- UI 层提供字段、操作符和值的选择界面
- 后端将允许的字段和操作符映射到白名单，然后构建 `WhereDynamic` 表达式（必要时添加 `OrderByDynamic`）
- 结果：单一查询管道支持几乎无限的组合，无需条件分支爆炸

示例实现：

```csharp
public class QueryBuilder
{
    private readonly HashSet<string> _allowedFields = new()
    {
        "Status", "LastLogon", "Name", "Email", "Country"
    };

    private readonly Dictionary<string, string> _operatorMap = new()
    {
        ["equals"] = "==",
        ["contains"] = "Contains",
        ["greaterThan"] = ">",
        ["lessThan"] = "<"
    };

    public async Task<List<Customer>> BuildQuery(
        DbContext context,
        List<QueryCondition> conditions)
    {
        var filters = new List<string>();

        foreach (var condition in conditions)
        {
            if (!_allowedFields.Contains(condition.Field))
                continue;

            var op = _operatorMap.GetValueOrDefault(condition.Operator, "==");
            filters.Add($"x.{condition.Field} {op} {FormatValue(condition.Value)}");
        }

        var filter = filters.Any()
            ? "x => " + string.Join(" && ", filters)
            : "x => true";

        return await context.Customers
            .WhereDynamic(filter)
            .ToListAsync();
    }
}
```

### 市场部门细分规则

市场营销团队经常需要保存和复用客户细分规则。动态 LINQ 可以这样实现：

- 将细分规则保存为可读的表达式字符串（例如："活跃客户 AND 欧洲地区 AND (最近 90 天活跃 OR 消费 ≥ €500) AND 已订阅 AND 非测试账户"）
- 应用程序加载规则并通过 `WhereDynamic` 执行，然后持久化结果
- 结果：规则演变无需修改代码或重新部署

```csharp
public class SegmentManager
{
    public async Task<List<Customer>> ApplySegment(
        DbContext context,
        string segmentRule)
    {
        // 从数据库加载保存的细分规则
        // 示例规则："x.Status == 1 && x.Country == \"DE\" && x.LastPurchase >= DateTime.Now.AddDays(-90)"

        return await context.Customers
            .WhereDynamic(segmentRule)
            .OrderBy(x => x.CustomerID)
            .ToListAsync();
    }

    public async Task SaveSegment(string name, string rule)
    {
        // 验证规则语法
        // 保存到数据库
    }
}
```

### 多租户规则配置

在多租户 SaaS 应用中，不同租户可能需要略微不同的业务规则：

- 每个租户存储几个谓词表达式（或基本的允许/拒绝筛选器）
- 在请求时组合这些规则并动态应用
- 结果：更少的代码分支和功能标记，更清晰的发布模型

```csharp
public class TenantQueryService
{
    public async Task<List<Customer>> GetCustomers(
        DbContext context,
        int tenantId)
    {
        // 从配置加载租户特定的筛选规则
        var tenantRules = await LoadTenantRules(tenantId);

        var baseFilter = "x => x.TenantId == " + tenantId;

        if (!string.IsNullOrEmpty(tenantRules.AdditionalFilter))
        {
            baseFilter += " && " + tenantRules.AdditionalFilter;
        }

        return await context.Customers
            .WhereDynamic(baseFilter)
            .ToListAsync();
    }
}
```

## 安全防护与最佳实践

### 字段和操作符白名单

永远不要直接暴露整个数据模型。始终使用白名单将 UI 输入映射到允许的字段和操作符：

```csharp
private readonly HashSet<string> _allowedFields = new()
{
    "CustomerID", "Name", "Status", "LastLogon", "Country"
};

private readonly HashSet<string> _allowedOperators = new()
{
    "==", "!=", ">", "<", ">=", "<=", "Contains", "StartsWith"
};

public bool ValidateCondition(string field, string op)
{
    return _allowedFields.Contains(field) && _allowedOperators.Contains(op);
}
```

### 表达式验证

在执行之前验证表达式，拒绝包含未知标记或字段的表达式：

```csharp
public bool ValidateExpression(string expression)
{
    // 检查是否包含危险的方法调用
    var dangerousPatterns = new[] { "System.", "File.", "Directory.", "Process." };

    if (dangerousPatterns.Any(p => expression.Contains(p)))
        return false;

    // 可以添加更多验证逻辑
    return true;
}
```

### 保持在 IQueryable 上直到最后

在调用 `ToList()` 或 `ToListAsync()` 之前应用所有动态操作，这样 EF Core 才能将它们转换为 SQL：

```csharp
// 正确做法
var result = await context.Customers
    .WhereDynamic(filter)      // 仍在 IQueryable
    .OrderByDynamic(sort)      // 仍在 IQueryable
    .SelectDynamic(projection) // 仍在 IQueryable
    .ToListAsync();           // 此时才物化为内存中的列表

// 错误做法
var temp = await context.Customers.ToListAsync(); // 过早物化
var result = temp.WhereDynamic(filter); // 在内存中筛选，失去 SQL 优化
```

### 规范化值

使用 ISO 日期格式或通过参数对象传递值，而不是自由文本解析：

```csharp
// 推荐方式
var parameters = new
{
    StartDate = DateTime.Parse("2025-01-01"),
    EndDate = DateTime.Parse("2025-12-31")
};

var result = context.Orders
    .WhereDynamic("x => x.OrderDate >= StartDate && x.OrderDate <= EndDate", parameters);

// 避免这样
var filter = $"x => x.OrderDate >= DateTime.Parse(\"{userInput}\")"; // 潜在的注入风险
```

### 快照测试保存的规则

对关键的细分规则进行快照测试，加载 → 执行 → 断言计数和数据形状：

```csharp
[Fact]
public async Task SavedSegment_ReturnsExpectedResults()
{
    // Arrange
    var context = CreateTestContext();
    var segmentRule = "x => x.Status == 1 && x.Country == \"DE\"";

    // Act
    var results = await context.Customers
        .WhereDynamic(segmentRule)
        .ToListAsync();

    // Assert
    Assert.All(results, c =>
    {
        Assert.Equal(1, (int)c.Status);
        Assert.Equal("DE", c.Country);
    });
}
```

### 保持可读性

优先使用小型、可组合的字符串；将构建逻辑集中到辅助方法中：

```csharp
public class FilterBuilder
{
    private readonly List<string> _conditions = new();

    public FilterBuilder AddCondition(string condition)
    {
        if (!string.IsNullOrWhiteSpace(condition))
            _conditions.Add(condition);
        return this;
    }

    public string Build()
    {
        return _conditions.Any()
            ? "x => " + string.Join(" && ", _conditions)
            : "x => true";
    }
}

// 使用
var filter = new FilterBuilder()
    .AddCondition(onlyActive ? "x.Status == 1" : null)
    .AddCondition(since != null ? $"x.LastLogon >= DateTime.Parse(\"{since:yyyy-MM-dd}\")" : null)
    .Build();
```

### 何时不使用动态 LINQ

如果你只有 2-3 个固定的筛选条件且很少变化，静态 LINQ 仍然是最简单的选择（而且完全没问题）。动态 LINQ 的优势在可变性和可选性增长时才会显现。

对于简单场景，传统的条件分支可能更直观：

```csharp
// 简单场景，静态 LINQ 就足够了
var query = context.Customers.AsQueryable();

if (includeInactive)
    query = query.Where(x => x.Status != CustomerStatus.Deleted);
else
    query = query.Where(x => x.Status == CustomerStatus.Active);

return await query.ToListAsync();
```

## 总结

动态 LINQ 不是为了展示技巧，而是为了消除用户想要筛选的内容与开发者必须交付的功能之间的摩擦。

当规则存在于 UI 或数据库中，并在底层编译为真正的 LINQ 时，你可以用单一、清晰的管道替代条件分支森林和频繁部署，这个管道能够随着产品复杂度的增长而扩展。

管理后台、报表系统、保存的细分规则、多租户调整——这些都变成了配置问题，而不是工程冲刺任务。

如果你的筛选条件是用户定义的、租户定义的或不断变化的，`WhereDynamic`、`OrderByDynamic`、`SelectDynamic` 和 `FirstOrDefaultDynamic` 为你提供了所需的 80/20 解决方案：清晰的代码、运行时灵活性和 EF 级别的性能。

添加安全的白名单、验证输入、在物化之前保持所有操作在 `IQueryable` 上，你将拥有一个既强大又可预测的解决方案。

如果"我在交付功能，而不是重写查询"这个想法引起了共鸣，那么动态 LINQ 就是你应该采用的方向。记住：动态 LINQ 的价值在于将不断变化的业务规则从代码层面提升到配置层面，让技术团队能够专注于核心功能开发，而不是为每个筛选条件的微调而疲于奔命。
