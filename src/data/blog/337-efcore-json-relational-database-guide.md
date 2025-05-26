---
pubDatetime: 2025-05-26
tags: [EF Core, JSON, 数据库, .NET, 后端开发, PostgreSQL, SQL Server, MySQL]
slug: efcore-json-relational-database-guide
source: https://blog.elmah.io/storing-json-data-in-relational-databases-using-ef-core/
title: EF Core 玩转 JSON：在 PostgreSQL、SQL Server 和 MySQL 中高效存储与查询 JSON 数据
description: 本文针对.NET开发者与后台程序员，详细讲解如何使用EF Core在主流关系型数据库（PostgreSQL、SQL Server、MySQL）中存储和查询JSON数据，配合代码实战与效果截图，助力项目快速落地。
---

# EF Core 玩转 JSON：在 PostgreSQL、SQL Server 和 MySQL 中高效存储与查询 JSON 数据

在现代后端开发中，灵活的数据结构和高效的数据存储方式越来越受关注。无论是日志、配置项，还是动态扩展的业务字段，JSON 都成为了不可或缺的数据格式。而.NET 程序员更是希望能用熟悉的 EF Core 一把梭，将 JSON 对象优雅地落地到主流关系型数据库。今天我们就来带你一步步实操：EF Core 如何在 PostgreSQL、SQL Server 和 MySQL 中玩转 JSON 存储与查询！🚀

[![EF Core 存储 JSON 数据示意图](https://blog.elmah.io/content/images/2025/05/storing-json-data-in-relational-databases-using-ef-core-o-1.png)](https://blog.elmah.io/content/images/2025/05/storing-json-data-in-relational-databases-using-ef-core-o-1.png)

## 引言：为什么要在关系型数据库中存储 JSON？

JSON（JavaScript Object Notation）是一种轻量级、结构化的数据交换格式，常用于API通信、配置文件、日志等场景。它不仅可读性强，而且灵活性高，尤其适合保存一些结构不固定或者需要频繁变更的字段。

对于.NET开发者来说，如何把这种灵活的数据格式优雅地映射到传统的关系型数据库？EF Core 正好提供了极佳的解决方案。本篇文章将以代码和图示，带你快速掌握三大主流数据库（PostgreSQL、SQL Server、MySQL）下的实战操作。

---

## 核心内容详解

### 1️⃣ PostgreSQL——天然支持 JSONB，效率杠杠的

PostgreSQL 是目前对 JSON 支持最强大的关系型数据库之一，`jsonb` 类型不仅支持索引，还能高效查询。

**实操步骤：**

1. 安装 NuGet 包：

   ```bash
   dotnet add package Npgsql.EntityFrameworkCore.PostgreSQL
   dotnet add package Microsoft.EntityFrameworkCore.Design
   ```

2. 定义实体模型：

   ```csharp
   public class LogEntry
   {
       public int Id { get; set; }
       public LogDetail? Details { get; set; }
   }
   public class LogDetail
   {
       public string? Level { get; set; }
       public string? Message { get; set; }
       public DateTime Timestamp { get; set; }
   }
   ```

3. 配置 DbContext，并将 `Details` 属性映射为 `jsonb`：

   ```csharp
   modelBuilder.Entity<LogEntry>(entity =>
   {
       entity.Property(e => e.Details)
           .HasColumnType("jsonb")
           .HasConversion(
               v => JsonSerializer.Serialize(v, new JsonSerializerOptions()),
               v => JsonSerializer.Deserialize<LogDetail>(v, new JsonSerializerOptions())
           );
   });
   ```

4. 插入和查询 JSON 数据：

   ```csharp
   db.Logs.Add(new LogEntry
   {
       Details = new LogDetail
       {
           Level = "Info",
           Message = "Application started",
           Timestamp = DateTime.UtcNow
       }
   });
   db.SaveChanges();

   var infoLogs = db.Logs.Where(l => l.Details!.Level == "Info").ToList();
   ```

5. 迁移 & 查看效果：

   ```bash
   dotnet ef migrations add InitJsonTable
   dotnet ef database update
   ```

[![控制台输出示例](https://blog.elmah.io/content/images/2025/05/output.png)](https://blog.elmah.io/content/images/2025/05/output.png)

[![PostgreSQL 数据库截图](https://blog.elmah.io/content/images/2025/05/output-1.png)](https://blog.elmah.io/content/images/2025/05/output-1.png)

---

### 2️⃣ SQL Server——用 nvarchar(max) 灵活存储

SQL Server 虽然没有专门的 JSON 类型，但可以用 `nvarchar(max)` 存储 JSON 字符串，通过 EF Core 的自定义转换很容易实现。

**实操步骤：**

1. 安装 NuGet 包：

   ```bash
   dotnet add package Microsoft.EntityFrameworkCore.SqlServer
   dotnet add package Microsoft.EntityFrameworkCore.Design
   ```

2. 实体定义同上。

3. DbContext 配置：

   ```csharp
   modelBuilder.Entity<LogEntry>(entity =>
   {
       entity.Property(e => e.Details)
             .HasColumnType("nvarchar(max)")
             .HasConversion(
                 v => JsonSerializer.Serialize(v, new JsonSerializerOptions()),
                 v => JsonSerializer.Deserialize<LogDetail>(v!, new JsonSerializerOptions())
             );
   });
   ```

4. 插入和查询数据：

   ```csharp
   db.Logs.Add(new LogEntry
   {
       Details = new LogDetail
       {
           Level = "Error",
           Message = "Failed to connect",
           Timestamp = DateTime.UtcNow
       }
   });
   db.SaveChanges();

   var errorLogs = db.Logs.Where(l => l.Details!.Level == "Error").ToList();
   ```

[![SQL Server 控制台输出示例](https://blog.elmah.io/content/images/2025/05/output-2.png)](https://blog.elmah.io/content/images/2025/05/output-2.png)

---

### 3️⃣ MySQL——专属 JSON 类型，查询强大

MySQL 8+ 支持原生 `json` 类型，适合对 JSON 内容有索引和路径查询需求的场景。

**实操步骤：**

1. 安装 NuGet 包：

   ```bash
   dotnet add package Pomelo.EntityFrameworkCore.MySql
   dotnet add package Microsoft.EntityFrameworkCore.Design
   ```

2. 实体定义同上。

3. DbContext 配置：

   ```csharp
   modelBuilder.Entity<LogEntry>(entity =>
   {
       entity.Property(e => e.Details)
             .HasColumnType("json")
             .HasConversion(
                 v => JsonSerializer.Serialize(v, new JsonSerializerOptions()),
                 v => JsonSerializer.Deserialize<LogDetail>(v!, new JsonSerializerOptions())
             );
   });
   ```

4. 插入和查询数据：

   ```csharp
   db.Logs.Add(new LogEntry
   {
       Details = new LogDetail
       {
           Level = "Warning",
           Message = "Disk space low",
           Timestamp = DateTime.UtcNow
       }
   });
   db.SaveChanges();

   var warningLogs = db.Logs.Where(l => l.Details!.Level == "Warning").ToList();
   ```

[![MySQL 控制台输出示例](https://blog.elmah.io/content/images/2025/05/output-3.png)](https://blog.elmah.io/content/images/2025/05/output-3.png)

---

## 总结与实践建议

现代关系型数据库都已经支持或间接支持 JSON 数据类型，通过 EF Core 的灵活配置，我们可以轻松实现：

- PostgreSQL 用 jsonb，查询和索引一流；
- SQL Server 用 nvarchar(max)，兼容性强；
- MySQL 用 json，原生支持 JSON 查询语法。

无论你是构建日志系统、动态配置还是复杂的可扩展业务表结构，都可以大胆用起来！⚡️

---

## 你的项目中用到 JSON 存储了吗？欢迎留言交流经验！

你在使用 EF Core + JSON 时遇到过哪些坑？或者还有哪些好用的技巧和场景？欢迎在评论区留言讨论！如果本文对你有帮助，别忘了点赞、转发给更多.NET小伙伴，让我们一起提升开发效率！👏
