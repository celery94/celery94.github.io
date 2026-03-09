---
pubDatetime: 2026-03-09
title: "EF Core 的现代映射玩法"
description: "很多人对 EF Core 的印象还停留在实体、导航属性和外键那一层。可到了 EF Core 8 甚至 10，复杂属性、拥有实体、原始类型集合、视图映射、表拆分、阴影属性和属性包，已经把建模空间一下子拉宽了。"
tags: ["EF Core", ".NET", "ORM", "Database"]
slug: "modern-mapping-with-ef-core"
source: "https://developmentwithadot.blogspot.com/2026/02/modern-mapping-with-ef-core.html"
---

很多团队一说起 EF Core，脑子里还是那张老图：实体、主键、外键、`Include`，再加一点迁移。能跑，没问题，但视野会变窄。

麻烦就在这里。你的领域模型不只会长出“实体之间的关系”，它还会长出值对象、原始类型集合、只读投影、拆开的表结构、临时扩展字段，甚至那种根本不想专门写 CLR 类型的字典式数据。要是还拿十年前那套映射思路硬套，代码会越来越别扭。

Ricardo Peres 这篇文章有意思的地方，不是又列了一遍 API 名单，而是把 EF Core 这些年补齐的映射能力放在一条线上看。你会发现，EF Core 早就不是“把类映成表”这么简单了。

## 不是所有对象都该当实体

文章一开头先把对象分成了三类，这个切分很有用。

一类是单值类型，比如 `int`、`string`、`Guid`、`DateTime`。一类是有身份的对象，比如 `Customer`、`Order`、`Product`。还有一类经常被忽略，它们也有结构，也有多个属性，但没有独立身份，比如 `Address`、`Coordinate`。

这第三类对象，过去在 EF Core 里一直有点尴尬。你可以勉强把它们当实体，也可以靠转换器把它们塞成字符串，可两种办法都不自然。前者把不该有身份的东西硬做成身份对象，后者又把查询能力一起埋了。

这就是现代映射真正解决的问题：让模型语义和数据库映射别互相拖后腿。

## 复杂属性和拥有实体，差别不只是 API 名字

如果一个 `Customer` 只有一个地址，而且你根本不关心地址自己的身份，那它更像值对象，不像实体。

```csharp
public class Customer
{
    public int Id { get; set; }
    public Address Address { get; set; }
}

public class Address
{
    public string Street { get; set; }
    public string City { get; set; }
    public string Country { get; set; }
    public string POBox { get; set; }
}
```

到了 EF Core 8 之后，`ComplexProperty` 给这类模型一个更干净的位置：

```csharp
modelBuilder.Entity<Customer>()
    .ComplexProperty(x => x.Address);
```

它的含义很明确：`Address` 不是独立实体，没有自己的表，没有自己的键，它只是 `Customer` 的一部分。落库时，地址里的字段会直接展开到 `Customer` 表里。

很多人会问，那和 `OwnsOne` 有什么区别？区别在语义。

拥有实体（owned entity）虽然也能共享同一张表，但它本质上还是实体语义，哪怕键是隐藏的。官方文档也专门提醒过，同一个实例被多个拥有导航共享时，跟踪和保存会出问题。复杂属性就没有这层包袱，它更像真正的值对象。

文章里这个判断我很认同：你关心“值”，就用复杂属性；你关心“依附于聚合根但仍有实体语义”，再考虑拥有实体。名字看起来像亲戚，脾气差很多。

## 一旦是集合，存储策略立刻变了

单个复杂属性展开成列，很自然。可一旦 `Customer` 有多个地址，事情就没那么直给了。

```csharp
public class Customer
{
    public int Id { get; set; }
    public List<Address> Addresses { get; set; } = [];
}
```

在文章假定的 EF Core 10 场景里，这类复杂集合可以直接放进 JSON 列：

```csharp
modelBuilder.Entity<Customer>()
    .ComplexCollection(x => x.Addresses, options =>
    {
        options.ToJson();
    });
```

这里有个很现实的前提：数据库得支持 JSON 列，SQL Server 2025 这类新版本才会比较顺手，兼容级别也得跟上。老环境想照搬，十有八九会撞墙。

如果你用的是拥有实体集合，选择会更多一点。你可以继续放到拥有者表的 JSON 列里，也可以拆去单独的表：

```csharp
modelBuilder.Entity<Customer>()
    .OwnsMany(x => x.Addresses, options =>
    {
        options.HasKey("Id");
    });
```

这就是复杂属性和拥有实体的第二层差异。复杂属性强调“它只能是拥有者内部的一部分”；拥有实体还能进一步演化成带独立存储形态的依赖对象。

选哪一个，不是看哪个更新潮，而是看你的对象到底有没有身份边界。

## 原始类型集合终于不用再手搓转换器

以前只要模型里出现 `List<string>`、`string[]`、`List<DateOnly>` 这种字段，很多人的第一反应都是：哦，又要写 `ValueConverter` 了。

现在不用急着受苦了。

```csharp
public class Product
{
    public int Id { get; set; }
    public List<string> Tags { get; set; } = [];
}
```

EF Core 现在能直接映射这类原始类型集合，通常会放进 JSON 列，而且还能查询：

```csharp
ctx.Products
    .Where(x => x.Tags.Contains("blue"))
    .ToList();
```

这类能力看起来像“省了点配置”，实际上影响很大。因为一旦框架知道集合里的元素类型，它就能生成更像样的 SQL。官方文档里举过不少例子，像 SQL Server 会把参数数组转成 JSON，再配合 `OPENJSON` 做过滤和比较；SQLite 则会用 `json_each` 或 `->>` 这类 JSON 操作。

不过也别一激动就把一切都塞成原始集合。标签、日期片段、小型枚举列表很适合。真正需要独立生命周期、需要约束、需要 join 的数据，老老实实建实体。能映射，不代表该这么建模。

## 视图、SQL 和函数，不必总让实体背锅

有些数据根本不是为了写回去，它们就是查询投影。

比如你想把 `Customer`、`Order`、`Product` 聚成一个只读结果：

```csharp
public record OrderCustomer(
    string CustomerName,
    DateTime OrderTimestamp,
    int ProductCount);
```

这时候强行给它做完整实体，经常是在给自己找麻烦。EF Core 提供了三条路：映射到视图、映射到一段 SQL、映射到表值函数。文章里分别用了 `ToView`、`ToSqlQuery` 和 `ToFunction`。

```csharp
modelBuilder.Entity<OrderCustomer>()
    .ToView("OrderCustomer")
    .HasNoKey();
```

`HasNoKey` 很关键，它等于在告诉 EF Core：别追踪，别更新，别幻想这个东西能 `SaveChanges`。

这类能力特别适合报表、后台列表、聚合读取模型。很多时候你真正需要的不是“更多实体”，而是一个说得清楚的只读模型。读模型和写模型别总绑成一坨，系统会轻松很多。

## 拆表这件事，EF Core 现在也玩得很熟

文章后半段讲了两个经常被忽略的能力：table splitting 和 entity splitting。

先看 table splitting。它的意思是，同一张表拆成两个实体来映射。比如 `Order` 只保留核心信息，`OrderDetail` 放次要细节。两者共用同一行数据，但在代码层面分成两个对象。这样你在大部分路径里只碰轻量对象，重信息只在需要时才进来。

```csharp
modelBuilder.Entity<Order>(x =>
{
    x.ToTable("Order");
});

modelBuilder.Entity<OrderDetail>(x =>
{
    x.ToTable("Order");
    x.HasOne(o => o.Order)
        .WithOne(o => o.Detail)
        .HasForeignKey<OrderDetail>(o => o.Id);
});
```

反过来，entity splitting 是把一个实体拆到多张表里。这个适合老库，也适合那种业务上永远成套出现、但物理上已经分表的数据结构。

```csharp
modelBuilder.Entity<Order>(x =>
{
    x.ToTable("Order")
        .SplitToTable("OrderDetail", y =>
        {
            y.Property(o => o.DispatchDate);
            y.HasOne(o => o.Customer).WithMany();
            y.HasMany(o => o.Products).WithMany();
        });
});
```

这两种映射都不是“炫技功能”。碰到遗留数据库、宽表、冷热字段分离、读写路径差异明显的场景，它们很实用。你不用为了迁就表结构，把领域模型写得像数据库注释。

## 阴影属性和索引器属性，适合那些你不想暴露出来的数据

有些列就是不想挂在实体公开 API 上，比如 `LastUpdated`、软删除标记、某些系统字段。这时候阴影属性（shadow property）很顺手：

```csharp
builder.Property<DateTime?>("LastUpdated")
    .HasDefaultValueSql("GETUTCDATE()")
    .ValueGeneratedOnAddOrUpdate();
```

你仍然能在跟踪器里访问它，也能在查询里用 `EF.Property`：

```csharp
var query = ctx.Products
    .Where(x => EF.Property<DateTime>(x, "LastUpdated").Year == 2025);
```

如果你希望实体本身像一个可扩展字典，那就可以走索引器属性：

```csharp
builder.IndexerProperty<string>("Colour");
builder.IndexerProperty<string>("Make");
```

配合 CLR 索引器，写法会很直接：

```csharp
public class Product
{
    private readonly Dictionary<string, object> _data = new();

    public object this[string key]
    {
        get => _data[key];
        set => _data[key] = value;
    }
}
```

这种设计很适合“字段集合会变，但你又不想每次都改实体类”的场景。动态商品属性、可配置扩展项、半结构化后台数据，都能用。

## 属性包实体，连 CLR 类都可以不写

再往前一步，EF Core 甚至允许你把一个实体直接建成 `Dictionary<string, object>`。这就是 property bag entity type，也叫 shared-type entity。

```csharp
public class Context : DbContext
{
    public DbSet<Dictionary<string, object>> KeyValuePairs =>
        Set<Dictionary<string, object>>("KeyValuePairs");

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.SharedTypeEntity<Dictionary<string, object>>(
            "KeyValuePairs",
            options =>
            {
                options.Property<int>("Id");
                options.Property<string>("A");
                options.Property<int>("B");
                options.Property<DateTime>("C");
                options.HasKey("Id");
            });
    }
}
```

这听起来有点野，但在某些场景真的有用。比如后台导入表、弱结构化扩展模型、临时适配外部数据源。

当然，它也不是银弹。官方文档明确写了限制：只有 `Dictionary<string, object>` 受支持，继承不支持，索引器导航不支持，很多强类型体验也没了。能用，但别把它当默认方案。你要的是弹性，不是把类型系统整个请出门。

## 什么时候该用哪一种

真到设计模型的时候，可以把选择压缩成下面这张表：

| 场景                             | 更合适的做法                            |
| -------------------------------- | --------------------------------------- |
| 没有身份、只表达值               | `ComplexProperty` / `ComplexCollection` |
| 依附于聚合根，但希望保留实体语义 | `OwnsOne` / `OwnsMany`                  |
| 少量原始值集合                   | 原始类型集合                            |
| 只读报表或聚合结果               | `ToView` / `ToSqlQuery` / `ToFunction`  |
| 一张表拆成多个对象               | Table splitting                         |
| 一个对象拆到多张表               | Entity splitting                        |
| 不想暴露系统字段                 | Shadow properties                       |
| 想让实体支持动态扩展键值         | Indexer properties                      |
| 连 CLR 类型都不想建              | Property bag entity types               |

这张表背后其实只有一个问题：你想表达的到底是身份、值，还是投影？一旦这个问题答对了，映射方式基本就不会离谱。

## EF Core 已经不是“轻量版 ORM”了

文章最后提到，EF Core 现在已经补上了很多过去更像 NHibernate 专长的能力。我觉得这话不夸张。

它当然还不是全能选手，也不是每一种映射都该拿出来用。但如果你还把 EF Core 理解成“只会普通 CRUD 的 ORM”，那判断会落后很多。复杂属性、JSON、表拆分、属性包这些能力一旦用对，建模自由度会高不少。

模型该表达业务，不该只是数据库的投影。EF Core 现在给你的工具，已经够把这件事做得更像样了。

## 参考

- [原文: Modern Mapping with EF Core](https://developmentwithadot.blogspot.com/2026/02/modern-mapping-with-ef-core.html) — Ricardo Peres
- [EF Core Owned Entity Types](https://learn.microsoft.com/en-us/ef/core/modeling/owned-entities) — 官方文档，解释 `OwnsOne`、`OwnsMany` 和限制
- [EF Core 8: Complex Types 与 Primitive Collections](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-8.0/whatsnew#value-objects-using-complex-types) — 官方文档，补充复杂类型和原始类型集合的行为
- [Advanced Table Mapping](https://learn.microsoft.com/en-us/ef/core/modeling/table-splitting) — 官方文档，说明 table splitting 与 entity splitting
- [Shadow and Indexer Properties](https://learn.microsoft.com/en-us/ef/core/modeling/shadow-properties#property-bag-entity-types) — 官方文档，说明阴影属性、索引器属性与属性包实体
