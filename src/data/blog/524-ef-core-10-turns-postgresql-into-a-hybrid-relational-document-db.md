---
pubDatetime: 2025-12-19
title: "EF Core 10 将 PostgreSQL 转变为混合关系-文档数据库"
description: "探索 EF Core 10 如何通过复杂类型（Complex Types）将 PostgreSQL JSONB 支持提升到新高度，实现灵活的混合数据模型、强大的 LINQ 查询转换和高性能批量更新。"
tags: ["EF Core", "PostgreSQL", "JSONB", ".NET", "Database"]
slug: "ef-core-10-turns-postgresql-into-a-hybrid-relational-document-db"
source: "https://trailheadtechnology.com/ef-core-10-turns-postgresql-into-a-hybrid-relational-document-db/"
---

# EF Core 10 将 PostgreSQL 转变为混合关系-文档数据库

现代 .NET 应用程序越来越需要存储不适合传统关系表结构的数据，无论是每个租户的自定义字段、不断演变的产品属性还是外部 API 载荷。在 EF Core 10 之前，处理这类灵活数据意味着笨拙的建模变通方法、原始 JSON 文本列或分散的 NoSQL 辅助存储。

在本文中，我将向你展示 EF Core 10 如何通过**复杂类型（Complex Types）**引入一种强大的新方式来映射 PostgreSQL 中的 JSONB 列。结合 PostgreSQL 高度优化的 JSONB 存储引擎，这使得能够清晰地建模灵活的、模式演化的数据，而不牺牲性能或可查询性。

## 为什么 JSONB 很重要

传统关系模型在应用程序需要存储以下内容时会遇到困难：

- **动态或租户特定字段**
- **分层或嵌套属性**
- **频繁变化的演进结构**
- **外部 API 载荷或元数据**

这正是 PostgreSQL JSONB 发挥作用的地方：你可以获得模式灵活性、原生索引、快速查询和完整的 ACID 保证，所有这些都在关系引擎内部。

## PostgreSQL 中的 JSON 与 JSONB

| 特性     | JSON     | JSONB        |
| -------- | -------- | ------------ |
| 存储     | 文本     | 二进制树     |
| 查询性能 | 慢       | 快           |
| 索引     | 无       | GIN/GiST     |
| 重复键   | 保留     | 最后一个获胜 |
| 解析成本 | 每次查询 | 插入时一次   |

**经验法则**：始终使用 JSONB，除非你需要保留格式，那么使用 JSON。

## EF Core 10 改变了 JSON 映射

在 .NET 10 之前，JSONB 映射需要[拥有实体（owned entities）](https://learn.microsoft.com/en-us/ef/core/modeling/owned-entities)，这会导致：

- 令人困惑的所有权语义
- 影子主键
- 冗长的配置
- 不支持 `ExecuteUpdate`

### .NET 10 解决方案：复杂类型

EF Core 10 引入了**复杂类型**，提供：

- 值类型语义
- 更清晰的配置
- 自动嵌套集合
- 完整的 LINQ → JSONB 转换
- 使用 `ExecuteUpdate` 进行批量 JSON 更新
- 可选的复杂类型（`Address?`）

**配置示例**：

```csharp
modelBuilder.Entity<Product>()
    .ComplexProperty(p => p.Specs, b => b.ToJson());
```

就是这样——EF Core 自动处理嵌套结构。

## 在 EF Core 10 中查询 JSONB

EF Core 现在直接将复杂的 LINQ 查询转换为 PostgreSQL JSONB 操作符，如 `->`、`->>`、`@>`。

### 按 JSON 属性过滤

```csharp
var items = await context.Products
    .Where(p => p.Specs.Brand == "Apple")
    .ToListAsync();
```

### 按嵌套数字字段过滤

```csharp
var results = await context.Products
    .Where(p => p.Specs.RAM >= 16)
    .ToListAsync();
```

### 查询 JSON 数组

```csharp
var items = await context.Products
    .Where(p => p.Specs.Features.Contains("Waterproof"))
    .ToListAsync();
```

## 使用 ExecuteUpdate 进行批量 JSON 更新（EF Core 10）

EF Core 10 为 JSONB 带来了真正的批量更新支持：

```csharp
await context.Products
    .ExecuteUpdateAsync(s =>
        s.SetProperty(p => p.Metadata.Views,
                      p => p.Metadata.Views + 1));
```

### 性能比较（10,000 行）

| 方法               | 耗时      | 内存 | SQL 语句 |
| ------------------ | --------- | ---- | -------- |
| Load + SaveChanges | 5–10s     | 高   | 10,000   |
| ExecuteUpdate      | 100–200ms | 低   | 1        |

这对于分析计数器、状态更新、元数据更改等是一个巨大的改进。

## JSONB 何时是正确选择

在以下情况下使用 JSONB：

### ✔ 模式灵活

元数据、偏好设置、工作流定义、配置。

### ✔ 分层

不适合关系表的嵌套对象或列表。

### ✔ 频繁演进

无需迁移即可更改的动态字段。

### ✔ 半结构化或外部

Webhook 载荷、API 响应、集成。

### ✔ 基于快照

审计跟踪、版本历史、修订日志。

## 何时不使用 JSONB

在以下情况下避免使用 JSONB：

### ❌ 稳定的核心域数据

关系列更快且强制执行约束。

### ❌ 外键关系

JSONB 无法强制执行引用完整性。

### ❌ 大量连接工作负载

对关系字段的 JOIN 优于 JSON 提取。

### ❌ 高写入 OLTP 工作负载

更新 JSONB 会重写整个文档。

## 正确索引 JSONB

没有索引，JSONB 查询会迅速降级。

### GIN 索引（最常见）

```sql
CREATE INDEX idx_specs_gin ON products USING gin (specs);
```

### 特定字段的表达式索引

```sql
CREATE INDEX idx_brand ON products ((specs ->> 'Brand'));
```

使用 GIN 进行包含查询，使用表达式索引过滤特定键。

## 设计混合架构（推荐方法）

最强大的架构结合了关系和 JSONB 风格：

### 关系列用于：

- 稳定字段
- 频繁查询的属性
- 连接和外键

### JSONB 用于：

- 可选字段
- 动态或租户特定属性
- 元数据、偏好设置和工作流

**示例模型**：

```csharp
public class Product
{
    public int Id { get; set; }
    public string Category { get; set; } = null!;
    public decimal Price { get; set; }

    // 灵活层
    public ProductSpecifications Specs { get; set; } = new();
}
```

这为你提供了模式安全性和灵活性。

## 性能总结

### JSONB 更快的场景：

- 包含查询（`@>`）
- 读取整个文档
- 避免一些表连接

### JSONB 更慢的场景：

- 大型数据集上的聚合
- 频繁更新大型文档
- 复杂的 JOIN 逻辑
- 需要严格关系约束的查询

## 实际示例：EF Core 配置

```csharp
modelBuilder.Entity<Order>(entity =>
{
    entity.ComplexProperty(o => o.Metadata, b => b.ToJson());
    entity.ComplexCollection(o => o.Items, b => b.ToJson());
});
```

### 查询

```csharp
var orders = await context.Orders
    .Where(o => o.Items.Any(i => i.UnitPrice > 100))
    .ToListAsync();
```

### 批量更新

```csharp
await context.Orders
    .Where(o => o.Metadata.Status == "Pending")
    .ExecuteUpdateAsync(s =>
        s.SetProperty(p => p.Metadata.Status, "Processing"));
```

## 总结

EF Core 10 最终通过**复杂类型**提供了一种清晰、强大且一流的方式来使用 PostgreSQL JSONB。

### 关键要点

- **复杂类型是 .NET 10 中 JSON 映射的新标准**
- **JSONB 非常适合灵活、演进、分层的数据**
- **`ExecuteUpdate` 提高了 JSON 更新的性能**
- **使用混合关系 + JSONB 模型以获得最佳架构**
- **JSONB 很强大——但不能取代关系设计**

当策略性地使用时，JSONB 成为构建现代、灵活应用程序的 .NET 开发人员可用的最有效工具之一。

如果你的团队正在考虑 PostgreSQL JSONB、评估混合模型或规划现代化工作，正确的架构可以帮助你避免常见陷阱并充分发挥这项技术的潜力。
