---
pubDatetime: 2025-06-03
tags: [".NET", "Performance"]
slug: high-performance-csv-import-with-dapper-plus
source: https://thecodeman.net/posts/building-high-performance-import-feature-with-dapper-plus
title: .NET大批量数据高性能导入实践：Dapper Plus全流程实战与性能对比
description: 面向.NET/C#中高级开发者，本文系统梳理如何用Dapper Plus实现高效CSV导入数据库的完整流程，并与传统Dapper做性能实测，帮助你攻克大数据量操作的瓶颈。
---

# .NET大批量数据高性能导入实践：Dapper Plus全流程实战与性能对比

## 引言：为什么要关注大批量数据导入？🚀

在日常.NET/C#开发工作中，很多中高级开发者都会遇到这样一个“痛点”——**需要将大量数据（比如CSV导出、第三方对接、定时同步等场景）高效地导入数据库**。刚开始，你可能用Dapper一条条插入，看似没毛病，结果数据量一大，程序“龟速前行”，用户体验直线下降，甚至API超时崩溃。

有没有更优雅、更高效的方式？这就是今天要分享的主角——**Dapper Plus**。本篇文章将以“CSV批量导入SQL Server”为例，系统演示高性能导入方案，并做详尽的性能对比和代码讲解，让你彻底告别慢吞吞的数据插入。

---

## 什么是Dapper Plus？它如何助你“提速”？⚡

[Dapper](https://github.com/DapperLib/Dapper)一直被认为是.NET世界里的高性能ORM“小钢炮”，查询和简单插入都非常快。但当你面对**上万、甚至上百万条数据**时，传统Dapper每插一次就要和数据库通讯一次（Round Trip），这直接成为性能瓶颈。

[Dapper Plus](https://dapper-plus.net/?utm_source=stefandjokic&utm_medium=newsletter&utm_campaign=dapperplus)的强大之处在于：它支持BulkInsert/BulkUpdate/BulkDelete等批量操作，将多条数据合并成一次数据库操作，大幅减少通讯次数。官方宣称插入10万条只需几秒，真正适合处理大体量数据的场景。

---

## 实战全流程：从CSV到SQL Server，一步到位

### 1. 定义数据实体：Product类

首先，创建与你CSV结构一致的实体类，比如`Product`：

```csharp
public class Product
{
    public int ProductId { get; set; }
    public string Name { get; set; }
    public string Category { get; set; }
    public decimal Price { get; set; }
    public bool InStock { get; set; }
}
```

### 2. 安装必要NuGet包

我们需要两个包：

- `Z.Dapper.Plus`（核心批量操作库）
- `CsvHelper`（CSV文件读取利器）

```
Install-Package Z.Dapper.Plus
Install-Package CsvHelper
```

> ⚠️ 温馨提示：Dapper Plus为商业软件，生产环境需购买许可，可免费试用。

### 3. 映射配置：告诉Dapper Plus你的表结构

```csharp
DapperPlusManager.Entity<Product>()
    .Table("Products")
    .Map(p => p.ProductId)
    .Map(p => p.Name)
    .Map(p => p.Category)
    .Map(p => p.Price)
    .Map(p => p.InStock);
```

> 这一步通常在应用启动时配置一次即可。

### 4. 读取CSV文件并转成实体集合

```csharp
using CsvHelper;
using System.Globalization;

public static List<Product> ParseCsv(string filePath)
{
    using var reader = new StreamReader(filePath);
    using var csv = new CsvReader(reader, CultureInfo.InvariantCulture);
    return csv.GetRecords<Product>().ToList();
}
```

### 5. 高效导入：同步与异步两种姿势

#### 同步BulkInsert

```csharp
public void ImportProducts(string csvFilePath, IDbConnection dbConnection)
{
    var products = ParseCsv(csvFilePath);

    try
    {
        dbConnection.BulkInsert(products);
        Console.WriteLine($"{products.Count} products imported successfully.");
    }
    catch (Exception ex)
    {
        Console.WriteLine("Something went wrong during bulk insert: " + ex.Message);
        // 可选：日志记录或重试
    }
}
```

#### 异步BulkInsert（推荐）

```csharp
public async Task ImportProductsAsync(
    string csvFilePath,
    IDbConnection dbConnection,
    CancellationToken cancellationToken)
{
    var products = ParseCsv(csvFilePath);

    try
    {
        cancellationToken.ThrowIfCancellationRequested();

        await dbConnection.BulkInsertAsync(products, cancellationToken);
        Console.WriteLine($"{products.Count} products imported successfully (async).");
    }
    catch (OperationCanceledException)
    {
        Console.WriteLine("Import was canceled.");
    }
    catch (Exception ex)
    {
        Console.WriteLine("Bulk insert failed: " + ex.Message);
    }
}
```

> 支持CancellationToken，可以优雅响应UI“取消”或任务超时。

### 6. 数据校验：保障导入质量

批量导入时更要注意脏数据过滤，例如：

```csharp
products = products
    .Where(p => !string.IsNullOrWhiteSpace(p.Name) && p.Price >= 0)
    .ToList();
```

高级一点可以分组错误并反馈用户：

```csharp
var invalidProducts = products.Where(p => p.Price < 0).ToList();
if (invalidProducts.Any())
{
    // 提示警告或记录日志
}
```

---

## 性能实测：“龟速”与“飞速”的真实对比🆚

为了让大家一目了然，我们分别用普通Dapper与Dapper Plus做批量插入，测试1,000/10,000/100,000三种规模的数据。

**测试环境说明：**

- 数据库：SQLite（也可换成SQL Server）
- 核心代码参考文末仓库链接

**代码核心片段**如下：

```csharp
public async Task InsertWithDapperAsync(List<Product> products)
{
    const string sql = "INSERT INTO Products (Name, Price) VALUES (@Name, @Price)";
    foreach (var product in products)
    {
        await _connection.ExecuteAsync(sql, product);
    }
}

public async Task InsertWithDapperPlusAsync(List<Product> products)
{
    await _connection.BulkInsertAsync(products);
}
```

**测试结果如下图所示：**

![批量插入性能对比](https://thecodeman.net/images/blog/posts/building-high-performance-import-feature-with-dapper-plus/performance.png)

> 可以看到：Dapper Plus插入10万条数据仅需几秒，而普通Dapper则要几十秒甚至分钟级差距。

---

## 总结&行动建议🔎

- **小规模操作（<千条）**：用Dapper即可，简洁灵活。
- **大数据量场景（万级、百万级）**：强烈推荐Dapper Plus，大幅节省时间和系统资源。
- **易集成、易维护**：API设计直观，易于融入现有项目架构。

更多实用[在线示例](https://dapper-plus.net/online-examples?utm_source=stefandjokic&utm_medium=newsletter&utm_campaign=dapperplus)和[完整源码](https://github.com/StefanTheCode/DapperPlusDemo)，欢迎大家参考实践！

---

## 互动时间💬

你在实际项目中遇到过哪些批量数据导入的挑战？是否尝试过类似的批量操作优化？欢迎在评论区留言，分享你的经验与疑问。觉得本文有帮助，记得点赞和转发给身边的.NET开发朋友！
