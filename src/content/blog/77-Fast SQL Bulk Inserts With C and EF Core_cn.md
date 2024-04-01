---
pubDatetime: 2024-04-01
tags: [C#, EF Core, SQL, Dapper, Bulk Insert, SQL Server, Performance]
source: https://www.milanjovanovic.tech/blog/fast-sql-bulk-inserts-with-csharp-and-ef-core?utm_source=Twitter&utm_medium=social&utm_campaign=01.04.2024
author: Milan Jovanović
title: 使用C#和EF Core进行快速SQL批量插入
description: 探讨使用C#和EF Core进行快速批量插入SQL的各种方法，重点介绍了如Dapper、EF Core优化、EF Core Bulk Extensions和SQL批量复制等技术。
---

# 使用C#和EF Core进行快速SQL批量插入

> ## 摘要
>
> 探讨使用C#和EF Core进行快速批量插入SQL的各种方法，重点介绍了如Dapper、EF Core优化、EF Core Bulk Extensions和SQL批量复制等技术。
>
> 原文 [Fast SQL Bulk Inserts With C# and EF Core](https://www.milanjovanovic.tech/blog/fast-sql-bulk-inserts-with-csharp-and-ef-core?utm_source=Twitter&utm_medium=social&utm_campaign=01.04.2024) 由 [Milan Jovanović](https://www.milanjovanovic.tech/) 发表。

---

无论你是在构建数据分析平台、迁移遗留系统，还是在接纳大量新用户，你都可能需要在某个时刻将大量数据插入数据库。

一条一条地插入记录就像在慢动作中观看油漆干燥一样无聊。传统方法不合适。

因此，理解C#和EF Core的快速批量插入技术变得至关重要。

在今天的问题中，我们将探索在C#中执行批量插入的几个选项：

- Dapper
- EF Core
- EF Core Bulk Extensions
- SQL批量复制

示例基于`User`类和**SQL Server**中相应的`Users`表。

```csharp
public class User
{
    public int Id { get; set; }
    public string Email { get; set; }
    public string FirstName { get; set; }
    public string LastName { get; set; }
    public string PhoneNumber { get; set; }
}
```

这不是批量插入实现的完整列表。有一些我没有探索的选项，比如手动生成SQL语句和使用[表值参数](https://learn.microsoft.com/en-us/sql/relational-databases/tables/use-table-valued-parameters-database-engine?view=sql-server-ver16)。

## EF Core简单方法

让我们从一个简单的例子开始，使用EF Core。我们创建了一个`ApplicationDbContext`实例，添加了一个`User`对象，并调用`SaveChangesAsync`。这将逐个将记录插入数据库。换句话说，每个记录需要一次往返数据库。

```csharp
using var context = new ApplicationDbContext();

foreach (var user in GetUsers())
{
    context.Users.Add(user);

    await context.SaveChangesAsync();
}
```

结果如你所料，非常差：

```
EF Core - 一次添加一个并保存，对于100用户：20 ms
EF Core - 一次添加一个并保存，对于1,000用户：260 ms
EF Core - 一次添加一个并保存，对于10,000用户：8,860 ms
```

由于执行时间太长，我省略了`100,000`和`1,000,000`条记录的结果。

我们将用它作为一个“如何不做批量插入”的示例。

## Dapper简单插入

[Dapper](https://github.com/DapperLib/Dapper)是一个简单的.NET SQL到对象映射器。它允许我们轻松地将对象集合插入数据库。

我正在使用Dapper的特性来将一个集合展开到一个SQL `INSERT`语句中。

```csharp
using var connection = new SqlConnection(connectionString);
connection.Open();

const string sql =
    @"
    INSERT INTO Users (Email, FirstName, LastName, PhoneNumber)
    VALUES (@Email, @FirstName, @LastName, @PhoneNumber);
    ";

await connection.ExecuteAsync(sql, GetUsers());
```

结果比初始示例好得多：

```
Dapper - 范围插入，对于100用户：10 ms
Dapper - 范围插入，对于1,000用户：113 ms
Dapper - 范围插入，对于10,000用户：1,028 ms
Dapper - 范围插入，对于100,000用户：10,916 ms
Dapper - 范围插入，对于1,000,000用户：109,065 ms
```

## EF Core添加并保存

然而，EF Core还没有认输。第一个示例是故意实现得很差。EF Core可以将多个SQL语句批量处理，所以让我们利用这一点。

如果我们进行一个简单的改变，我们可以获得显著更好的性能。首先，我们将所有对象添加到`ApplicationDbContext`。然后，我们将只调用一次`SaveChangesAsync`。

EF将创建一个批量SQL语句 - 将许多`INSERT`语句组合在一起 - 并将它们一起发送到数据库。这减少了数据库的往返次数，给我们带来了性能提升。

```csharp
using var context = new ApplicationDbContext();

foreach (var user in GetUsers())
{
    context.Users.Add(user);
}

await context.SaveChangesAsync();
```

这种实现的基准测试结果如下：

```
EF Core - 全部添加并保存，对于100用户：2 ms
EF Core - 全部添加并保存，对于1,000用户：18 ms
EF Core - 全部添加并保存，对于10,000用户：203 ms
EF Core - 全部添加并保存，对于100,000用户：2,129 ms
EF Core - 全部添加并保存，对于1,000,000用户：21,557 ms
```

记住，Dapper需要**109秒**来插入`1,000,000`条记录。我们可以使用EF Core批量查询在**约21秒**内完成相同的操作。

## EF Core AddRange和Save

这是前一个示例的一个替代方案。与其为所有对象调用`Add`，不如调用`AddRange`并传入一个集合。

我想展示这个实现，因为我更喜欢它超过之前的那个。

```csharp
using var context = new ApplicationDbContext();

context.Users.AddRange(GetUsers());

await context.SaveChangesAsync();
```

结果与前一个示例非常相似：

```
EF Core - 添加范围并保存，对于100用户：2 ms
EF Core - 添加范围并保存，对于1,000用户：18 ms
EF Core - 添加范围并保存，对于10,000用户：204 ms
EF Core - 添加范围并保存，对于100,000用户：2,111 ms
EF Core - 添加范围并保存，对于1,000,000用户：21,605 ms
```

## EF Core Bulk Extensions

有一个很棒的库叫[EF Core Bulk Extensions](https://github.com/borisdj/EFCore.BulkExtensions)，我们可以使用它来进一步提升性能。你可以用这个库做很多事情，不仅仅是批量插入，所以我推荐探索它。这个库是开源的，并且如果你满足免费使用标准，就有社区许可。查看[许可部分](https://github.com/borisdj/EFCore.BulkExtensions?#license)了解更多细节。

对于我们的用例，`BulkInsertAsync`方法是一个绝佳的选择。我们可以传递对象集合，它将执行SQL批量插入。

```csharp
using var context = new ApplicationDbContext();

await context.BulkInsertAsync(GetUsers());
```

性能同样惊人：

```
EF Core - 批量扩展，对于100用户：1.9 ms
EF Core - 批量扩展，对于1,000用户：8 ms
EF Core - 批量扩展，对于10,000用户：76 ms
EF Core - 批量扩展，对于100,000用户：742 ms
EF Core - 批量扩展，对于1,000,000用户：8,333 ms
```

相比之下，我们需要**约21秒**的时间来使用EF Core批量查询插入`1,000,000`条记录。我们可以用[Bulk Extensions](https://github.com/borisdj/EFCore.BulkExtensions)库在短短**8秒**内完成相同的操作。

## SQL批量复制

最后，如果我们无法从EF Core获得所需的性能，我们可以尝试使用[`SqlBulkCopy`](https://learn.microsoft.com/en-us/dotnet/api/system.data.sqlclient.sqlbulkcopy)。SQL Server本地支持[批量复制操作](https://learn.microsoft.com/en-us/dotnet/framework/data/adonet/sql/bulk-copy-operations-in-sql-server)，所以让我们利用这一点。

这种实现比EF Core示例稍微复杂一些。我们需要配置`SqlBulkCopy`实例，并创建一个包含我们想要插入的对象的`DataTable`。

```csharp
using var bulkCopy = new SqlBulkCopy(ConnectionString);

bulkCopy.DestinationTableName = "dbo.Users";

bulkCopy.ColumnMappings.Add(nameof(User.Email), "Email");
bulkCopy.ColumnMappings.Add(nameof(User.FirstName), "FirstName");
bulkCopy.ColumnMappings.Add(nameof(User.LastName), "LastName");
bulkCopy.ColumnMappings.Add(nameof(User.PhoneNumber), "PhoneNumber");

await bulkCopy.WriteToServerAsync(GetUsersDataTable());
```

然而，性能非常快：

```
SQL批量复制，对于100用户：1.7 ms
SQL批量复制，对于1,000用户：7 ms
SQL批量复制，对于10,000用户：68 ms
SQL批量复制，对于100,000用户：646 ms
SQL批量复制，对于1,000,000用户：7,339 ms
```

以下是如何创建一个`DataTable`并用对象列表填充它的方法：

```csharp
DataTable GetUsersDataTable()
{
    var dataTable = new DataTable();

    dataTable.Columns.Add(nameof(User.Email), typeof(string));
    dataTable.Columns.Add(nameof(User.FirstName), typeof(string));
    dataTable.Columns.Add(nameof(User.LastName), typeof(string));
    dataTable.Columns.Add(nameof(User.PhoneNumber), typeof(string));

    foreach (var user in GetUsers())
    {
        dataTable.Rows.Add(
            user.Email, user.FirstName, user.LastName, user.PhoneNumber);
    }

    return dataTable;
}
```

## 结果

以下是所有批量插入实现的结果：

| 方法           | 数据量  | 速度           |
| -------------- | ------- | -------------- |
| EF_OneByOne    | 100     | 19.800 ms      |
| EF_OneByOne    | 1000    | 259.870 ms     |
| EF_OneByOne    | 10000   | 8,860.790 ms   |
| EF_OneByOne    | 100000  | N/A            |
| EF_OneByOne    | 1000000 | N/A            |
| Dapper_Insert  | 100     | 10.650 ms      |
| Dapper_Insert  | 1000    | 113.137 ms     |
| Dapper_Insert  | 10000   | 1,027.979 ms   |
| Dapper_Insert  | 100000  | 10,916.628 ms  |
| Dapper_Insert  | 1000000 | 109,064.815 ms |
| EF_AddAll      | 100     | 2.064 ms       |
| EF_AddAll      | 1000    | 17.906 ms      |
| EF_AddAll      | 10000   | 202.975 ms     |
| EF_AddAll      | 100000  | 2,129.370 ms   |
| EF_AddAll      | 1000000 | 21,557.136 ms  |
| EF_AddRange    | 100     | 2.035 ms       |
| EF_AddRange    | 1000    | 17.857 ms      |
| EF_AddRange    | 10000   | 204.029 ms     |
| EF_AddRange    | 100000  | 2,111.106 ms   |
| EF_AddRange    | 1000000 | 21,605.668 ms  |
| BulkExtensions | 100     | 1.922 ms       |
| BulkExtensions | 1000    | 7.943 ms       |
| BulkExtensions | 10000   | 76.406 ms      |
| BulkExtensions | 100000  | 742.325 ms     |
| BulkExtensions | 1000000 | 8,333.950 ms   |
| BulkCopy       | 100     | 1.721 ms       |
| BulkCopy       | 1000    | 7.380 ms       |
| BulkCopy       | 10000   | 68.364 ms      |
| BulkCopy       | 100000  | 646.219 ms     |
| BulkCopy       | 1000000 | 7,339.298 ms   |

## 总结

`SqlBulkCopy`在最大原始速度方面占据榜首。然而，[EF Core Bulk Extensions](https://github.com/borisdj/EFCore.BulkExtensions)在保持Entity Framework Core的易用性的同时，提供了惊人的性能。

最佳选择取决于你的项目具体需求：

- 只关心性能？`SqlBulkCopy`是你的解决方案。
- 需要出色的速度和简化的开发？EF Core是一个明智的选择。

我把决定权交给你，以决定哪个选项最适合你的使用案例。
