---
pubDatetime: 2025-06-09
tags: ["Performance", "Productivity", "Tools"]
slug: efcore-batching-performance
source: https://www.milanjovanovic.tech/blog/how-i-made-my-efcore-query-faster-with-batching
title: EF Core查询性能优化实战：如何用批处理让查询提速3.4倍
description: 通过实际案例，带你深入理解EF Core中批量查询（Batching）的应用，并掌握提升性能的实用技巧。适合.NET开发者与后端工程师阅读。
---

# EF Core查询性能优化实战：如何用批处理让查询提速3.4倍 🚀

> 作者：Milan Jovanović  
> 来源：[How I Made My EF Core Query 3.42x Faster With Batching](https://www.milanjovanovic.tech/blog/how-i-made-my-efcore-query-faster-with-batching)

## 引言：EF Core很强，但你用对了吗？🧐

在.NET开发中，Entity Framework Core（EF Core）无疑是最受欢迎的ORM之一。它让数据访问变得高效而优雅，但你是否遇到过性能瓶颈，让接口响应慢到抓狂？其实，EF Core只是工具，关键还在于你如何用。

今天，我们结合一个真实案例，来聊聊如何用一个简单的“批处理”思路，让你的查询速度提升**3.42倍**，甚至更多！

## 为什么原始查询会很慢？——代码分析与痛点 🔍

让我们先看一个常见但有“坑”的写法。假设你在做一个开票系统，需要为某个公司拉取最近10张发票，并获取每张发票下的明细行（LineItems）。

不少同学可能会写出如下代码（简化版）：

```csharp
app.MapGet("invoices/{companyId}", (
    long companyId,
    InvoiceService invoiceService,
    AppDbContext dbContext) =>
{
    IEnumerable<Invoice> invoices = invoiceService.GetForCompanyId(companyId, take: 10);

    var invoiceDtos = new List<InvoiceDto>();
    foreach (var invoice in invoices)
    {
        // ⚠️ 每次循环都查一次数据库
        var lineItemDtos = await dbContext.LineItems
            .Where(li => invoice.LineItemIds.Contains(li.Id))
            .Select(li => new LineItemDto { ... })
            .ToArrayAsync();

        invoiceDto.LineItems = lineItemDtos;
        invoiceDtos.Add(invoiceDto);
    }
    return invoiceDtos;
});
```

> **问题：** 上面的代码每处理一张发票，就对数据库发起一次查询。如果有10张发票，就有10次数据库往返（round trip）！如果发票更多，这种N+1问题会让你的接口速度雪崩。

## 批处理（Batching）优化思路：一次查完，快到飞起 🏎️

既然每次查都要往数据库跑一趟，那为什么不一次把所有明细行都查出来，然后用内存去组装数据呢？这样只需要**一次数据库查询**！

优化后的代码核心逻辑如下：

```csharp
app.MapGet("invoices/{companyId}", (
    long companyId,
    InvoiceService invoiceService,
    AppDbContext dbContext) =>
{
    IEnumerable<Invoice> invoices = invoiceService.GetForCompanyId(companyId, take: 10);

    long[] lineItemIds = invoices.SelectMany(i => i.LineItemIds).ToArray();

    // 🟢 一次性查出所有LineItems
    var lineItemDtos = await dbContext.LineItems
        .Where(li => lineItemIds.Contains(li.Id))
        .Select(li => new LineItemDto { ... })
        .ToListAsync();

    // 用字典快速索引
    Dictionary<long, LineItemDto> lineItemsDictionary = lineItemDtos.ToDictionary(li => li.Id);

    var invoiceDtos = new List<InvoiceDto>();
    foreach (var invoice in invoices)
    {
        invoiceDto.LineItems = invoice.LineItemIds.Select(li => lineItemsDictionary[li]).ToArray();
        invoiceDtos.Add(invoiceDto);
    }
    return invoiceDtos;
});
```

**关键点总结：**

- 只做一次数据库查询（极大减少往返次数）；
- 用字典在内存中高效分配数据；
- 数据量适中时，内存压力可控。

![流程对比图](https://www.milanjovanovic.tech/blogs/mnw_075/benchmark.png?imwidth=3840)
_图：批处理后，查询次数骤减，效率暴增_

## 实测效果：性能提升到底有多大？📈

用[BenchmarkDotNet](https://github.com/dotnet/BenchmarkDotNet)做基准测试，得到以下结论：

- **原始方式（foreach版本）**：1913.3 微秒
- **批处理优化后**：558.6 微秒

**提速比例高达 3.42 倍！**

> ⚡ 如果是远程数据库，提升会更明显，因为每一次网络延迟都会被放大。

## 注意事项与最佳实践 📝

虽然批处理思路很香，但也不是“银弹”。实践前请注意：

- **单次加载数据量不要太大**，否则内存压力过大，甚至拖垮应用；
- 对数据量很大的场景，可以考虑分页或分批处理；
- 最终优化效果要通过实际**Benchmark**验证，不要主观臆断；
- 充分理解业务和数据结构，灵活应用EF Core的特性。

## 总结与互动 🎉

批量查询是后端开发绕不开的性能话题，也是EF Core调优的必修课。只需简单重构，就能让接口速度翻倍甚至翻几倍。希望今天的案例对你有所启发。

你平时还遇到过哪些EF Core或ORM的性能坑？有试过别的高效“套路”吗？欢迎在评论区留言讨论，或者分享本文给你的同事和朋友，一起让.NET开发更高效！

---

**相关链接：**

- [EF Core官方文档](https://learn.microsoft.com/en-us/ef/core/)
- [更多性能调优技巧](https://entityframework-extensions.net/?utm_source=milanjovanovic&utm_medium=newsletter)
