---
pubDatetime: 2025-04-26
tags: ["Productivity", "Tools"]
slug: seeding-in-efcore9
source: twitter
author: Celery Liu
title: 🚀EF Core 9 全新数据库种子功能解析：UseSeeding & UseAsyncSeeding
description: 深度解读EF Core 9中新增的UseSeeding与UseAsyncSeeding方法，详述其原理、用法与实际代码示例，帮助开发者高效初始化数据库数据。
---

# 🚗 EF Core 9 新特性：数据库种子数据的便捷管理

Entity Framework Core（简称EF Core）作为.NET平台主流的ORM框架，其每次版本更新都会带来实用性提升。EF Core 9 引入的 UseSeeding 和 UseAsyncSeeding 方法，为数据库初始化（种子数据 Seeding）带来了极大便利。本文将解析相关技术细节与实现方式，助你快速掌握这项新功能。

## 🌱 什么是数据库种子（Seeding）？

数据库种子是指在数据库创建或迁移时，自动插入一批预置的初始数据。例如，插入默认的用户、产品、角色等，这在开发、测试和生产环境都非常实用。

传统的EF Core种子方式一般在`OnModelCreating`里通过`HasData`方法实现，但灵活性有限，无法执行复杂逻辑或异步操作。

## 🆕 EF Core 9 新增功能概述

### UseSeeding 和 UseAsyncSeeding 方法

EF Core 9为`DbContext`配置引入了两个全新扩展方法：

- **UseSeeding**：用于同步方式插入种子数据。
- **UseAsyncSeeding**：用于异步方式插入种子数据，适合I/O密集型或需等待外部资源的场景。

它们均可在注册`DbContext`时灵活配置，无需更改实体配置或模型定义。

## 🛠️ 技术实现与代码分析

### 1. 基础配置流程

注册`DbContext`时，链式调用`UseSeeding`和`UseAsyncSeeding`：

```csharp
builder.Services.AddDbContext<CarDbContext>((serviceProvider, options) =>
{
    options
        .UseNpgsql(builder.Configuration["DatabaseConnectionString"])
        .UseSeeding((context, _) => { /*...*/ })
        .UseAsyncSeeding(async (context, _, cancellationToken) => { /*...*/ });
});
```

#### 技术细节说明：

- `UseNpgsql`：指定使用PostgreSQL数据库，并传入连接字符串。
- `UseSeeding`/`UseAsyncSeeding`：接收一个Lambda表达式，参数包括当前上下文对象（context），以及可选参数。
- 同步与异步可并存，满足不同业务需求。

### 2. 种子数据的判重与插入

```csharp
var demoCar = context.Set<Car>().FirstOrDefault(b => b.Id == 101);
if (demoCar == null)
{
    context.Set<Car>().Add(new Car { Id = 101, Make = "Tesla", Model = "Model S" });
    context.SaveChanges();
}
```

- **判重逻辑**：先查询目标表是否已有指定数据（如ID=101的汽车），避免重复插入。
- **数据插入**：不存在则新增数据，再调用保存方法写入数据库。

### 3. 异步方式优势

异步版本采用`await`关键字和异步API：

```csharp
var demoCar = await context.Set<Car>().FirstOrDefaultAsync(b => b.Id == 101);
if (demoCar == null)
{
    context.Set<Car>().Add(new Car { Id = 101, Make = "Tesla", Model = "Model S" });
    await context.SaveChangesAsync();
}
```

- **异步查询与保存**：提升应用响应能力，防止阻塞主线程，非常适合云原生、Web API等高并发场景。
- **cancellationToken**参数：支持取消操作，增强健壮性。

## 🏆 技术优势总结

- **高灵活性**：不受限于模型定义，可自由编写复杂逻辑，如多表关联、外部接口取数等。
- **支持异步**：符合现代.NET开发趋势，提高性能与扩展性。
- **易于维护**：种子逻辑集中在配置代码，便于调整与管理。

## 📚 应用场景举例

- 自动插入管理员账户、默认配置项等关键数据。
- 多租户应用下，为每个新租户初始化独立基础数据。
- 与外部系统对接时，动态获取并插入初始数据。

## 📝 总结

EF Core 9 的 UseSeeding 和 UseAsyncSeeding 方法，极大简化了数据库初始数据管理流程，为.NET开发者带来更灵活、更强大的种子数据解决方案。无论是本地开发还是生产部署，都能让你的数据库初始化变得更加得心应手。

如果你正在使用EF Core，不妨尝试升级到最新版本，体验这项便捷高效的新特性吧！
