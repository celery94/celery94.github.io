---
pubDatetime: 2025-04-23 22:24:54
tags: [C#, EF Core, SQL, 性能优化, .NET, 批量插入, 数据库]
slug: fast-sql-bulk-inserts-dotnet-efcore
source: https://www.milanjovanovic.tech/blog/fast-sql-bulk-inserts-with-csharp-and-ef-core?utm_source=X&utm_medium=social&utm_campaign=21.04.2025
title: 用C#和EF Core实现高性能SQL批量插入全攻略
description: 针对.NET开发者，深入解析C#和EF Core在大规模数据插入场景下的多种高效实现方法，涵盖Dapper、EF Core批量、Bulk Extensions与SqlBulkCopy，并对比性能，助力数据库操作提速94%。
---

# 用C#和EF Core实现高性能SQL批量插入全攻略 🚀

## 引言：大数据量插入的烦恼，开发者的痛点

在大型业务系统、数据分析平台或用户量激增时，.NET开发者常常面临一个老生常谈却又避无可避的问题：**如何高效地把海量数据灌入数据库？**  
如果还在一条一条插，等得人都要怀疑人生了。别急！今天我们就用实际案例，带你揭秘C#和EF Core在大数据量插入下的性能优化“黑科技”，让你的Insert速度飙升14倍，节省94%的时间！

---

## 核心观点与结构梳理

本篇文章针对.NET开发者和对高性能数据库操作感兴趣的软件工程师，系统梳理了C#与EF Core批量插入的几种主流实现方法，并对每种方法进行了性能实测与对比：

- EF Core传统逐条插入
- Dapper插入
- EF Core批量AddRange插入
- EF Core Bulk Extensions库
- SqlBulkCopy原生批量插入

每一部分均配有简单易懂的代码示例、详细的性能对比表和实战场景建议，让你轻松选出最适合自己项目的方案。

---

## 一、EF Core传统写法：一条一条加，慢到怀疑人生 🐢

很多朋友用EF Core时都是这样写的：

```csharp
using var context = new ApplicationDbContext();
foreach (var user in GetUsers())
{
    context.Users.Add(user);
    await context.SaveChangesAsync();
}
```

**性能实测：**

- 100条：20ms
- 1,000条：260ms
- 10,000条：8,860ms
  > 100,000条、1,000,000条？等得花都谢了……

**结论：**  
这种写法是典型的“怎么别写怎么来”，每加一条都要往数据库跑一趟，效率感人。

---

## 二、Dapper简单插入：轻量高效

Dapper以轻便著称，插入时可以直接展开对象集合：

```csharp
using var connection = new SqlConnection(connectionString);
connection.Open();
const string sql = @"
    INSERT INTO Users (Email, FirstName, LastName, PhoneNumber)
    VALUES (@Email, @FirstName, @LastName, @PhoneNumber);";
await connection.ExecuteAsync(sql, GetUsers());
```

**性能实测：**

- 100条：10ms
- 1,000条：113ms
- 10,000条：1,028ms
- 100,000条：10,916ms
- 1,000,000条：109,065ms

**小结：**  
比逐条Save快多了，但面对百万级数据仍然吃力。

---

## 三、EF Core批量AddRange：高效但保持易用性

**改进版写法**，一次性AddRange然后SaveChangesAsync：

```csharp
using var context = new ApplicationDbContext();
context.Users.AddRange(GetUsers());
await context.SaveChangesAsync();
```

**性能实测：**

- 100条：2ms
- 1,000条：18ms
- 10,000条：204ms
- 100,000条：2,111ms
- 1,000,000条：21,605ms

> **提示**：比Dapper快了五倍，代码风格也更贴近Entity Framework的习惯。

---

## 四、EF Core Bulk Extensions库：速度更上一层楼 🔥

Bulk Extensions是社区极力推荐的高性能批量操作库，支持批量插入、更新、删除和合并等操作。

```csharp
using var context = new ApplicationDbContext();
await context.BulkInsertAsync(GetUsers());
```

**性能实测：**

- 100条：1.9ms
- 1,000条：8ms
- 10,000条：76ms
- 100,000条：742ms
- 1,000,000条：8,333ms

**小结：**  
比原生EF Core快近三倍，并且兼容EF Core生态，对大项目极为友好！

---

## 五、SqlBulkCopy原生批量插入：极致性能之选 ⚡

SqlBulkCopy为SQL Server的原生批量复制API，是极致速度的代表，但代码略复杂。

```csharp
using var bulkCopy = new SqlBulkCopy(ConnectionString);
bulkCopy.DestinationTableName = "dbo.Users";
// 映射字段
bulkCopy.ColumnMappings.Add(nameof(User.Email), "Email");
bulkCopy.ColumnMappings.Add(nameof(User.FirstName), "FirstName");
bulkCopy.ColumnMappings.Add(nameof(User.LastName), "LastName");
bulkCopy.ColumnMappings.Add(nameof(User.PhoneNumber), "PhoneNumber");
await bulkCopy.WriteToServerAsync(GetUsersDataTable());
```

> DataTable生成代码略，可参考下方完整实现。

**性能实测（全场最佳）：**

- 100条：1.7ms
- 1,000条：7ms
- 10,000条：68ms
- 100,000条：646ms
- 1,000,000条：7,339ms

---

## 六、性能横向对比一览表

| 方法           | 100        | 1,000      | 10,000     | 100,000    | 1,000,000    |
| -------------- | ---------- | ---------- | ---------- | ---------- | ------------ |
| EF_OneByOne    | 19.8 ms    | 259.9 ms   | 8,860.8 ms | N/A        | N/A          |
| Dapper_Insert  | 10.7 ms    | 113.1 ms   | 1,028 ms   | 10,916 ms  | 109,065 ms   |
| EF_AddRange    | 2.0 ms     | 17.9 ms    | 204 ms     | 2,111 ms   | 21,606 ms    |
| BulkExtensions | **1.9 ms** | **7.9 ms** | **76 ms**  | **742 ms** | **8,334 ms** |
| SqlBulkCopy    | **1.7 ms** | **7.4 ms** | **68 ms**  | **646 ms** | **7,339 ms** |

---

## 七、场景推荐与选择建议

- **极致性能优先？**  
   推荐用`SqlBulkCopy`，但代码相对复杂，不支持跨平台数据库。
- **追求开发效率+高性能？**  
   `EF Core Bulk Extensions`是首选，易于维护、功能强大。
- **轻量脚本、快速开发？**  
   `Dapper`或`EF Core AddRange`即可满足。

> `EF Core Bulk Extensions` 并非完全免费，商业项目需购买许可证。
>
> `SqlBulkCopy` 仅支持SQL Server，其他数据库请使用相应的批量插入API。
>
> `Dapper` 适合轻量级项目，Apache 2.0许可证。

---

## 八、结论与互动 🏁

C#和EF Core在应对大规模数据插入时，其实可以“飞起来”！关键在于方法选择和代码实现的小细节。希望本文的实测与对比，能帮助你为自己的项目选到最合适的那把“利剑”。

如果你在生产环境中遇到过大批量数据导入的瓶颈，欢迎在评论区留言分享你的经验和踩过的坑！  
你更倾向哪种方案？你的实际项目里有遇到什么“奇葩”需求吗？👇欢迎讨论&转发！
