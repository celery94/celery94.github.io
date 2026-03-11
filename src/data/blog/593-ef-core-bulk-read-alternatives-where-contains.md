---
pubDatetime: 2026-03-11
title: "EF Core 里，`Where + Contains` 不是批量查询的终点"
description: "Anton Martyniuk 在一条赞助帖里演示了 EF Core 大批量查询的 5 个替代方案。真正值得记住的不是某个库名，而是一个判断：当 ID 列表上千、还伴随联表和同步任务时，`Contains` 往往已经不是合适的入口。"
tags: ["EF Core", "DotNet", "Database", "Performance"]
slug: "ef-core-bulk-read-alternatives-where-contains"
ogImage: "../../assets/593/01-cover.png"
source: "https://x.com/AntonMartyniuk/status/2031633480065417238"
---

![EF Core 大批量读取概念图](../../assets/593/01-cover.png)

很多人第一次写 EF Core 的批量查询，直觉都是这一句：先拿一组 ID，再来一个 `Where(...Contains(...))`。它不丑，也不神秘，而且在数据量不大时完全没问题。

问题出在它太容易被复制了。几十个 ID 能跑，几千个 ID 也许还能跑，于是这段写法慢慢从后台任务长进了同步流程、库存校验、目录对账、第三方数据导入，最后你才发现，真正拖垮接口的不是 LINQ 本身，而是你把一个适合小集合的模式，用到了大集合场景里。

Anton Martyniuk 最近在 X 上用一个赞助视频专门讲了这件事，配套给出了一个完整的示例仓库，演示如何用 EF Core Extensions 处理大批量读取。标题写得很猛，像在对 `Where + Contains` 宣战。我的判断更克制一点：**`Contains` 不是错，它只是有明确的适用边界。**

## 真正的问题，不是写法丑，是规模变了

先看最常见的版本：

```csharp
var products = await dbContext.Products
    .Where(p => productIds.Contains(p.Id))
    .ToListAsync();
```

如果 `productIds` 只有几十个，通常没什么可说的。可一旦集合上千，风险会开始叠加：

- SQL `IN (...)` 条件会越来越长，优化器和执行计划都更难受
- SQL Server 有 2100 个参数上限，到了这里你就不是慢不慢的问题，而是直接撞墙
- 你为了绕过去开始手动分批，查询代码会越来越像临时工脚手架
- 一旦查询还带 `Include`、额外过滤、排序，复杂度会一起放大

这就是很多 AI 代码建议容易误导人的地方。模型特别擅长补出这句 LINQ，因为它在局部上是正确的，也最像“正常 EF Core 代码”。但模型通常不知道你这组 ID 到底是 30 个，还是 30,000 个；也不知道它是页面筛选，还是夜间同步任务。

> AI 很会补出“能跑”的数据库代码，人要负责判断它能不能在真实数据规模下继续跑。

这点在今天反而更重要了。AI 已经把“写出一个查询”这件事变得很便宜，但数据库的约束、执行计划的代价、连接池的压力，这些底层规律一点也没变。

## 这 5 个方法，分别在解决什么问题

Anton 链接的示例仓库里，`BulkReadEfCoreExtensions` 这个项目把批量读取拆成了 5 个方法。它不是简单替换 `Contains`，而是把“你到底想匹配什么”分成了不同场景。

| 方法 | 适合场景 | 输入来源 | 返回结果 |
| --- | --- | --- | --- |
| `WhereBulkContains` | 从外部系统拿到一批主键，想查数据库里对应的实体 | 一组 ID | 数据库中的匹配实体 |
| `WhereBulkNotContains` | 想找“数据库里有哪些不在外部清单里” | 一组 ID | 数据库中的非匹配实体 |
| `BulkRead` | 输入不只是 ID，而是一组带字段的对象 | 对象列表 | 数据库中的匹配实体 |
| `WhereBulkContainsFilterList` | 想从输入列表里筛出“哪些已经存在” | 对象列表 | 输入列表对应的已存在项 |
| `WhereBulkNotContainsFilterList` | 想从输入列表里筛出“哪些还不存在” | 对象列表 | 输入列表对应的缺失项 |

这个拆法很有价值，因为它把“查数据库”变成了更明确的业务问题。比如商品目录同步时，你经常会同时遇到三类需求：

- 外部系统给你 5000 个商品 ID，你要把现有记录查出来
- 外部系统给你 2000 个停售 ID，你要找出数据库里剩下哪些商品还在卖
- 对方直接给你一批 `ProductCode + SupplierCode` 组合，你要判断哪些已存在、哪些要新建

这三件事看起来都像“查一下”，但实现思路和返回方向并不一样。

## 仓库里的例子，比帖子正文更值得看

示例仓库里最直观的一段，是 `WhereBulkContains`：

```csharp
app.MapGet("/products/where-bulk-contains", async (ShippingDbContext dbContext) =>
{
    var productIds = await GetProductIdsFromExternalSystem(dbContext);

    var products = await dbContext.Products
        .Include(product => product.Category)
        .WhereBulkContains(productIds, x => x.Id)
        .ToListAsync();

    return Results.Ok(products);
});
```

这里的重点不是 API 名字更酷，而是它把“外部系统给了我一大组键”当成一个专门问题来处理。`WhereBulkNotContains` 也是同样的思路，只是方向反过来，用来找数据库中的差集。

另一个我觉得更实用的是 `BulkRead`：

```csharp
app.MapPost("/products/bulk-read", (ShippingDbContext dbContext, List<ProductInRequest> input) =>
{
    var products = dbContext.Products.BulkRead(input);
    return Results.Ok(products);
});
```

为什么这个方法更接近真实业务？因为很多对账任务拿到的根本不是单纯 ID，而是一组半结构化输入。仓库里的 `ProductInRequest` 就是一个很小但很真实的例子：

```csharp
public readonly record struct ProductInRequest(
    int Id,
    string? ProductCode,
    string? SupplierCode
);
```

这类输入在导入、同步、补数任务里特别常见。AI 当然也能帮你很快搭出这个 API 外壳，但**它不擅长主动提醒你“你应该按业务键匹配，而不是只按自增 ID 匹配”**。这仍然是人的设计工作。

## 为什么这套方案会更稳

EF Core Extensions 的思路，是把这些大集合匹配问题交给更适合的底层机制处理。根据官方文档，`WhereBulkContains` 这类方法会借助临时表来绕开参数数量限制，并支持更复杂的匹配方式。要注意，官方也明确说了，它**不一定比小集合上的 `Contains` 更快**；它真正的价值，是当输入规模和匹配条件开始失控时，你还能用更稳定的方式把查询写下去。

从工程角度看，真正值得记住的是这个原则：

> 当你的查询条件本身已经像一张“小表”时，就别再假装它只是一个普通的 `List<int>`。

一旦你接受这个判断，后面的选择其实不只一种：

- 你可以用商业库，把临时表、匹配、联接这些细节外包掉
- 你也可以自己走表值参数（TVP）、临时表、原始 SQL 或存储过程
- 如果数据库不是 SQL Server，约束和最优策略还会继续变化
- 这套 `Bulk Contains / BulkRead` 能力目前也有边界，官方文档提到主要支持 SQL Server 和 PostgreSQL

这就是今天看这条帖子最该补上的一层背景。原帖是赞助内容，推广的是具体产品；但对读者真正有用的，不是“记住这个库名”，而是“什么时候该升级思路”。

## 什么时候继续用 `Contains`，什么时候该换工具

如果你只是页面筛选、后台管理台的小批量操作，或者几十到几百个 ID 的普通查询，我不会急着把 `Contains` 打成反模式。它简单、可读、没有额外依赖，维护成本也低。

但如果你已经落在下面这些场景里，我会认真考虑换方案：

- 外部系统同步，一次要处理几千到几万条键
- 查询带 `Include`、排序、分页或额外业务过滤
- SQL Server 环境，已经明显接近参数上限
- 你不得不手动拆批，还要自己拼装结果
- 任务是对账、库存更新、商品目录同步这类长流程，而不是一次性的页面读取

这里最容易被 AI 带偏的地方，是它会优先给你最少改动的答案：继续 LINQ，继续分批，继续在应用层补丁。短期看很省事，长期看就是把数据库问题伪装成了 C# 问题。

## AI 时代，这类数据库判断反而更值钱

今天很多开发者第一次接触数据库性能问题，不是从生产事故开始，而是从 AI 生成的代码开始。模型很会给出“最像示例代码”的方案，于是大家更容易把局部最优当成全局最优。

这件事已经变了：写代码本身不再稀缺，**识别边界条件**才稀缺。

可没变的也很明确：

- 数据规模会继续决定方案优劣
- 数据库参数上限不会因为你用了 LLM 就变大
- 执行计划、索引、联接成本仍然要靠工程判断

所以现在更该关注什么？不是“AI 能不能写 EF Core 查询”，这个问题已经没什么信息量了。更重要的是：

- 你有没有给 AI 足够的业务规模上下文
- 你会不会把查询模式和真实数据量一起评审
- 当模型给出一个能跑的答案时，你是否会追问“它在 5000 条输入下还合理吗”

这才是今天数据库开发里最实际的能力差距。

## 最后一句实话

Anton 这条帖子的标题有点耸动，但它抓住了一个真实痛点：很多 EF Core 项目不是不会查数据，而是**到了大集合场景还在用小集合思维查数据**。

如果你现在就在做导入、同步、库存、目录或对账任务，别急着记库名，先问自己一句：我手里的这组条件，到底只是几个参数，还是已经接近一张表了？一旦答案是后者，`Where + Contains` 多半就该让位了。

## 参考

- [原帖：You still write a Where + Contains in EF Core?](https://x.com/AntonMartyniuk/status/2031633480065417238) — Anton Martyniuk，赞助内容
- [示例仓库：BulkReadEfCoreExtensions](https://github.com/anton-martyniuk/efcore-extensions-examples/tree/main/BulkReadEfCoreExtensions) — 包含 5 种批量读取示例
- [Entity Framework Extensions](https://entityframework-extensions.net/) — 官方站点与批量读取说明
- [Where Bulk Contains](https://entityframework-extensions.net/where-bulk-contains) — 官方方法说明
- [Bulk Read](https://entityframework-extensions.net/bulk-read) — 官方方法说明
