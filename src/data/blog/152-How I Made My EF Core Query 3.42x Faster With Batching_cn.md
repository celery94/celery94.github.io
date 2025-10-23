---
pubDatetime: 2024-05-25
tags: ["Productivity", "Tools"]
source: https://www.milanjovanovic.tech/blog/how-i-made-my-efcore-query-faster-with-batching?utm_source=Twitter&utm_medium=social&utm_campaign=20.05.2024
author: Milan Jovanović
title: 如何通过批处理让我的 EF Core 查询快 3.42 倍
description: 如果你在构建 .NET 应用程序，EF Core 是一个非常棒的 ORM。今天，我会告诉你一个简单的想法，我用它获得了将近 4 倍的性能提升。
---

# 如何通过批处理让我的 EF Core 查询快 3.42 倍

> ## 摘要
>
> 如果你在构建 .NET 应用程序，EF Core 是一个非常棒的 ORM。今天，我会告诉你一个简单的想法，我用它获得了将近 4 倍的性能提升。
>
> 原文 [How I Made My EF Core Query 3.42x Faster With Batching](https://www.milanjovanovic.tech/blog/how-i-made-my-efcore-query-faster-with-batching?utm_source=Twitter&utm_medium=social&utm_campaign=20.05.2024) 由 [Milan Jovanović](https://www.milanjovanovic.tech/) 发表。

---

[EF Core](https://learn.microsoft.com/en-us/ef/core/) 是一个非常棒的 ORM，如果你在构建 .NET 应用程序。

但它和其他工具一样，你可能会以次优的方式使用它。

今天，我会告诉你一个简单的想法，我用它获得了将近 **4 倍的性能提升**。

我并不是说你会看到相同的结果，但理解这个想法会让你的查询更快。

## 为什么这个查询次优

这是我想用来解释这个强大想法的例子。它取自我正在处理的一个生产应用程序，但为了这个例子我简化了它。

我们使用 `InvoiceService` 获取某公司的一组发票。发票可能来自第三方 API 或其他持久化存储。我们缺乏详细的商品信息，因此我们查询数据库以填充缺失的数据。

下面高亮的 [LINQ 查询](https://learn.microsoft.com/en-us/ef/core/querying/) 本身并不差。它在一个数据库查询（往返）中返回所有商品。

但它缺少一个重要的意识，这可以解锁进一步的性能提升。

因为我们在迭代发票时，**我们多次查询数据库**。

```csharp
app.MapGet("invoices/{companyId}", (
    long companyId,
    InvoiceService invoiceService,
    AppDbContext dbContext) =>
{
    IEnumerable<Invoice> invoices = invoiceService.GetForCompanyId(
        companyId,
        take: 10);

    var invoiceDtos = new List<InvoiceDto>();
    foreach (var invoice in invoices)
    {
        var invoiceDto = new InvoiceDto
        {
            Id = invoice.Id,
            CompanyId = invoice.CompanyId,
            IssuedDate = invoice.IssuedDate,
            DueDate = invoice.DueDate,
            Number = invoice.Number
        };

        var lineItemDtos = await dbContext
            .LineItems
            .Where(li => invoice.LineItemIds.Contains(li.Id))
            .Select(li => new LineItemDto
            {
                Id = li.Id,
                Name = li.Name,
                Price = li.Price,
                Quantity = li.Quantity
            })
            .ToArrayAsync();

        invoiceDto.LineItems = lineItemDtos;

        invoiceDtos.Add(invoiceDto);
    }

    return invoiceDtos;
});
```

一旦你理解了这一点，解决方案就是应用一个简单的想法。

与其为每张发票获取商品，我们可以提前查询所有商品。

## 批处理来救场

这是相同的查询，但经过重构以仅查询一次商品。这意味着只有一次到数据库的往返。

最终设计有三个组件：

- 在一次数据库往返中查询所有 `LineItems`
- 创建一个 `LineItemDto` 字典以便快速查找

一旦我们有了字典，我们就可以循环遍历发票并分配商品。填充商品变成了一个字典查找（廉价）而不是数据库查询（昂贵）。

在决定这种解决方案是否可行之前，你还需要考虑一些事情。

你一次可以从数据库加载多少记录？

每张发票平均包含约 20 个商品，而我们只获取了十张发票。所以，我们从数据库加载了约 200 个商品。大多数应用程序可以处理这个负载。但如果你一次加载几千行，情况可能会有所不同。

```csharp
app.MapGet("invoices/{companyId}", (
    long companyId,
    InvoiceService invoiceService,
    AppDbContext dbContext) =>
{
    IEnumerable<Invoice> invoices = invoiceService.GetForCompanyId(
        companyId,
        take: 10);

    long[] lineItemIds = invoices
        .SelectMany(invoice => invoice.LineItemIds)
        .ToArray();

    var lineItemDtos = await dbContext
        .LineItems
        .Where(li => lineItemIds.Contains(li.Id))
        .Select(li => new LineItemDto
        {
            Id = li.Id,
            Name = li.Name,
            Price = li.Price,
            Quantity = li.Quantity
        })
        .ToListAsync();

    Dictionary<long, LineItemDto> lineItemsDictionary =
        lineItemDtos.ToDictionary(keySelector: li => li.Id);

    var invoiceDtos = new List<InvoiceDto>();
    foreach (var invoice in invoices)
    {
        var invoiceDto = new InvoiceDto
        {
            Id = invoice.Id,
            CompanyId = invoice.CompanyId,
            IssuedDate = invoice.IssuedDate,
            DueDate = invoice.DueDate,
            Number = invoice.Number,
            LineItems = invoice
                .LineItemIds
                .Select(li => lineItemsDictionary[li])
                .ToArray()
        };

        invoiceDtos.Add(invoiceDto);
    }

    return invoiceDtos;
})
```

## 快多少？

批处理变体似乎会更快，对吗？

我们在第一个版本中有 N 个查询（每个发票一个），在批处理版本中有一个查询。

以下是我使用 [BenchmarkDotNet](https://github.com/dotnet/BenchmarkDotNet) 得到的基准测试结果：

| 方法         | 平均       | 错误     | 标准差  | Gen0    | Gen1   | 分配     |
| ------------ | ---------- | -------- | ------- | ------- | ------ | -------- |
| ForeachQuery | 1,919.3 us | 10.00 us | 8.35 us | 19.5313 | 3.9063 | 359.4 KB |
| BatchedQuery | 558.6 us   | 2.62 us  | 2.19 us | 15.6250 | 1.9531 | 276.7 KB |

foreach 版本平均需要 **1913.3 us**（微秒）。  
批处理版本平均需要 **558.6 us**。

批处理版本快了 **3.42 倍**。这是在本地 SQL 数据库上的结果。

如果你在查询远程数据库，由于网络往返时间的影响，批处理版本应该会更快。当你有 N 个查询（foreach 版本）时，这种影响会迅速累积。

## 收获

这种方法的力量在于它的简单性和效率。通过批处理数据库查询，我们大大减少了往数据库的往返次数。这通常是最大的性能瓶颈之一。

但关键是要明白，这种方法并不是一刀切的解决方案。

EF Core 提供了许多功能和优化，但如何有效地使用它们，取决于开发人员。

最后，永远记住要进行测量和基准测试。我们在这个案例中看到的改进是通过基准测试量化的。没有正确的测量，很容易做出无意中降低性能的更改。
