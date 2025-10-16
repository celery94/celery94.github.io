---
pubDatetime: 2025-06-21
tags: ["Productivity", "Tools"]
slug: entityframework-exceptions-intro
source: https://www.giorgi.dev/entity-framework/introducing-entityframework-exceptions/
title: 高效优雅地处理 Entity Framework Core 数据库异常 —— EntityFramework.Exceptions 深度解析
description: 本文系统介绍 EntityFramework.Exceptions 库的设计原理、使用方法及其在实际开发中的价值，帮助.NET开发者更高效、优雅地处理数据库操作异常。
---

# 高效优雅地处理 Entity Framework Core 数据库异常 —— EntityFramework.Exceptions 深度解析

## 引言

在基于 Entity Framework Core (EF Core) 进行数据访问时，异常处理往往是绕不开的痛点。EF Core 在数据库操作失败时，会统一抛出 `DbUpdateException`，但实际开发中我们常常需要区分：究竟是违反唯一约束、字段长度超限，还是空值插入非空字段等？每种场景都可能需要不同的业务逻辑响应。  
传统做法不仅冗余繁琐，还存在代码耦合度高、可移植性差等问题。  
本文将带你深入了解并掌握一款极具实用价值的开源库——[EntityFramework.Exceptions](https://github.com/Giorgi/EntityFramework.Exceptions)，它让 EF Core 异常处理变得简单优雅且易于维护。

---

## 背景与痛点

在日常的 EF Core 使用中，我们经常会遇到如下问题：

- 无论何种数据库错误，均被包装为 `DbUpdateException`。
- 若要区分是唯一约束冲突、字段过长、空值插入等错误，需要深入挖掘底层 `DbException` 并判定数据库厂商相关的错误码。
- 不同数据库（SQL Server、PostgreSQL、MySQL等）错误码各不相同，跨库迁移时异常处理代码需要全部重写。

### 现实案例

假设有如下 `Product` 表，其 `Name` 字段具备唯一约束，`Price` 字段为非空且类型为 decimal(5,2)。

```csharp
class DemoContext : DbContext
{
    public DbSet<Product> Products { get; set; }

    protected override void OnModelCreating(ModelBuilder builder)
    {
        builder.Entity<Product>().Property(b => b.Price).HasColumnType("decimal(5,2)").IsRequired();
        builder.Entity<Product>().Property(b => b.Name).IsRequired().HasMaxLength(15);
        builder.Entity<Product>().HasIndex(u => u.Name).IsUnique();
    }

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        optionsBuilder.UseSqlServer(@"Data Source=localhost;Initial Catalog=Test;Integrated Security=True;Connect Timeout=30;");
    }
}
```

假如插入两个同名产品：

```csharp
using (var demoContext = new DemoContext())
{
    demoContext.Products.Add(new Product { Name = "Moon Lamp", Price = 1 });
    demoContext.Products.Add(new Product { Name = "Moon Lamp", Price = 10 });

    try
    {
        demoContext.SaveChanges();
    }
    catch (DbUpdateException e)
    {
        var sqlException = e.GetBaseException() as SqlException;
        // 2601 是 SQL Server 唯一索引冲突错误码
        if (sqlException != null && sqlException.Number == 2601)
        {
            // 唯一索引被违反，给用户显示合适的提示信息
        }
    }
}
```

**问题显而易见：**

1. 代码冗余且可读性差；
2. 需要记忆和硬编码不同数据库的错误码；
3. 异常处理分散且难以维护。

---

## 技术原理解析

### EntityFramework.Exceptions 的设计思路

EntityFramework.Exceptions 旨在为不同类型的数据库异常提供统一的高层封装，让开发者只需捕获具体语义化的异常类型，而无需关注底层实现细节。

**核心机制：**

- 提供了继承自 `DbContext` 的基类 `ExceptionProcessorContext`。
- 在重写的 `SaveChanges` 方法中捕获所有数据库相关异常，并根据底层数据库错误类型及错误码，抛出诸如：
  - `UniqueConstraintException`（唯一约束冲突）
  - `CannotInsertNullException`（插入空值到非空列）
  - `MaxLengthExceededException`（超出字段最大长度）
  - `NumericOverflowException`（数值溢出）
- 对 SQL Server、PostgreSQL、MySQL 等主流数据库有完整兼容。

---

## 实现步骤与集成方法

### 1. 安装 NuGet 包

根据所用数据库，选择合适的包：

- [SQL Server](https://www.nuget.org/packages/EntityFrameworkCore.Exceptions.SqlServer)
- [PostgreSQL](https://www.nuget.org/packages/EntityFrameworkCore.Exceptions.PostgreSQL)
- [MySQL](https://www.nuget.org/packages/EntityFrameworkCore.Exceptions.MySQL)

以 SQL Server 为例：

```shell
dotnet add package EntityFrameworkCore.Exceptions.SqlServer
```

### 2. 修改 DbContext 基类

将你的 `DbContext` 继承自 `ExceptionProcessorContext`：

```csharp
class DemoContext : ExceptionProcessorContext
{
    public DbSet<Product> Products { get; set; }
}
```

### 3. 编写简洁异常处理逻辑

以唯一约束冲突为例：

```csharp
using (var demoContext = new DemoContext())
{
    demoContext.Products.Add(new Product { Name = "Moon Lamp", Price = 1 });
    demoContext.Products.Add(new Product { Name = "Moon Lamp", Price = 10 });

    try
    {
        demoContext.SaveChanges();
    }
    catch (UniqueConstraintException e)
    {
        // 唯一索引被违反。显示友好的提示信息
    }
}
```

再比如字段长度超限：

```csharp
using (var demoContext = new DemoContext())
{
    demoContext.Products.Add(new Product { Name = "Moon Lamp Change 3 Colors", Price = 1 });

    try
    {
        demoContext.SaveChanges();
    }
    catch (MaxLengthExceededException e)
    {
        // 字段长度超限。提示用户输入内容过长
    }
}
```

### 4. 支持多数据库切换

无论是 SQL Server、PostgreSQL 还是 MySQL，只需更换 NuGet 包，异常处理逻辑无需修改，实现了极高的可移植性和统一性。

---

## 实际应用案例

**应用场景1：表单录入校验**

后台数据保存时出现唯一约束冲突，直接捕获 `UniqueConstraintException` 并返回友好提示，无需区分底层数据库类型。

**应用场景2：批量导入数据**

批量插入时只需针对高层封装的异常做统一处理，避免了复杂且重复的数据库错误码分支判断。

---

## 常见问题与解决方案

### Q1：如何支持自定义异常类型或业务场景？

A：可以通过继承和扩展 ExceptionProcessorContext，实现自定义错误识别和封装。

### Q2：对性能有无明显影响？

A：仅在 SaveChanges 时发生异常才进行额外处理，对正常流程无影响；且原理简单明了，不影响性能。

### Q3：是否兼容未来 EF Core 版本？

A：官方库持续维护，并适配新版本 EF Core；建议关注[GitHub 仓库](https://github.com/Giorgi/EntityFramework.Exceptions)及时获取最新动态。

---

## 总结

EntityFramework.Exceptions 为 .NET 开发者提供了一套跨数据库、高可维护性、业务友好的异常处理解决方案。它极大简化了代码逻辑，提高了可读性和可维护性，是企业级项目推荐使用的实用工具。

**推荐做法：**

- 项目启动初期即集成该库，统一管理所有数据库异常。
- 多人协作团队应在编码规范中明确使用该库标准。
- 针对常见数据层错误，统一设计业务响应与用户提示。

如你觉得该项目有帮助，不妨去[GitHub 仓库](https://github.com/Giorgi/EntityFramework.Exceptions)点个 Star 支持作者！🌟

---

**参考链接：**

- [EntityFramework.Exceptions 官方文档](https://www.giorgi.dev/entity-framework/introducing-entityframework-exceptions/)
- [Giorgi Dalakishvili 的博客](https://www.giorgi.dev/)
- [EntityFramework.Exceptions GitHub 仓库](https://github.com/Giorgi/EntityFramework.Exceptions)
