---
pubDatetime: 2026-10-19T08:27:00+08:00
title: "MongoDB in C#：连接、映射与读取文档"
description: "MongoDB 在 C# 里最容易混的是四层：客户端归属、BSON 映射契约、读取结果形状、索引证据。本文对照官方文档与 3.12.0 驱动源码，给出可执行的代码和排错顺序。"
tags: ["MongoDB", "C#", ".NET", "BSON", "Data Access"]
slug: "mongodb-in-csharp-connecting-mapping-reading"
ogImage: "../../assets/1101/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/18/mongodb-in-c-connecting-mapping-and-reading-documents"
---

服务容器解析成功，`IMongoCollection<Order>` 也注入到位了，第一次 `Find` 却抛异常。更糟的情况是它没抛异常，只是把数据反序列化成了字段全空的对象。

问题不在驱动，而在于把四件不同的事当成了一个「连上数据库」的动作：客户端归谁、文档和 CLR 类型怎么对应、查询结果该长什么样、以及你凭什么认为索引起作用了。Nick Cosentino 在 Dev Leader 的这篇文章就是按这四层拆的，我按当前官方文档和 `MongoDB.Driver` 3.12.0 的源码核对了一遍，并补上了几个原文没展开的实现细节。

原文自己声明：示例经过源码审阅，但没有在真实 MongoDB 上执行。下面同样如此，代码可以直接改用，但别把「编译通过」当成「跑通」。

## 四层各管什么

先把职责分开，后面所有排错都靠这张表：

| 层         | 谁负责                             | 出问题的典型表现                          |
| ---------- | ---------------------------------- | ----------------------------------------- |
| 连接与归属 | 应用配置与容器                     | 解析成功但操作失败；误 dispose 共享客户端 |
| BSON 映射  | 类型定义与 class map               | 字段名对不上、类型不兼容、反序列化抛异常  |
| 读取形状   | filter / projection / sort / limit | 返回太多数据、顺序不稳定、缺字段          |
| 索引与证据 | 查询模式与 explain                 | 慢、扫全表，或「以为加了索引就快了」      |

驱动的分工是：客户端配置部署，`GetDatabase` 和 `GetCollection<T>` 只是拿到句柄，真正的往返发生在操作时。构造句柄不证明能读到文档——这正是「DI 通过、第一次查询失败」的来源。

## 客户端要有明确的归属

官方连接文档的建议很直接：`MongoClient` 用单例生命周期。这是一句有用的起点，不是「所有凭据、所有部署端点都必须共用一个全局客户端」的规定。

要把**生命周期**和**归属**分开看：生命周期说这个对象复用多久，归属说谁能结束它。一个收到共享客户端的请求处理器是借用者，即使它能看到 `Dispose()` 方法；在请求结束时 dispose，会把别的处理器还在用（并且内部连接池还在服务）的对象关掉。

v3 驱动让这件事更容易踩：`MongoClient` 实现 `IDisposable`，`IMongoClient` 也跟着暴露 `Dispose()`；dispose 之后再使用会抛 `ObjectDisposedException`。

更反直觉的是 dispose 到底做了什么。v3.12.0 的实现里，`Dispose` 调用 `_operationExecutor.Dispose()` 和 `_settings.ClusterSource.Return(_cluster)`——它把 cluster 交还给 cluster source，而不是销毁它。官方文档写得更明确：

> Disposing of MongoClient does not dispose of the cluster and the underlying connections. To dispose of these resources, call `ClusterRegistry.UnregisterAndDisposeCluster()`.

所以别把 `using var client = new MongoClient(...)` 读成「作用域结束就关闭所有连接」。在独立控制台程序里由程序持有客户端没问题；在 Web 应用里，容器的 singleton 才是持有者。

同一个应用如果真的有两套部署端点、不同凭据或不同安全边界，那就该是两个客户端，各有各的名字和归属。含糊地共用一个全局实例，通常是在掩盖一个本该显式配置的边界。

## 最小的连接代码

```csharp
using System;
using MongoDB.Driver;

var connectionString = Environment.GetEnvironmentVariable("MONGODB_URI")
    ?? throw new InvalidOperationException("MONGODB_URI is required.");

using var client = new MongoClient(connectionString);
var database = client.GetDatabase("application");
var collection = database.GetCollection<MongoDB.Bson.BsonDocument>("orders");

Console.WriteLine(collection.CollectionNamespace.FullName);
```

这段只打印配置出来的命名空间。它刻意不声称数据库被连接过、集合存在、或者文档读得出来。连接串放环境变量或密钥管理里，不要出现在示例代码中——这也是原文特意提醒的一点。

## 把 BSON 映射写成显式契约

C# 用 BSON 序列化，不存在「任意 JSON 自动等于任意 CLR 类型」。驱动会为类型建 class map，把字段匹配到成员，再按成员类型选序列化器；存储里的类型不兼容，反序列化就会抛异常。

不可变 record 需要一个明确的创建路径。`MapCreator` 就是干这个的，配套还有构造函数相关的 attribute。对一个位置 record，显式注册能让「用哪个构造函数、字段叫什么」变成可见的约定，而不是依赖对 record 命名的猜测：

```csharp
using System;
using MongoDB.Bson;
using MongoDB.Bson.Serialization;

BsonClassMap.RegisterClassMap<Order>(map =>
{
    map.AutoMap();
    map.MapIdMember(order => order.Id);
    map.MapMember(order => order.CustomerId).SetElementName("customerId");
    map.MapMember(order => order.TotalCents).SetElementName("totalCents");
    map.MapCreator(order =>
        new Order(order.Id, order.CustomerId, order.TotalCents));
});

var order = new Order(ObjectId.GenerateNewId(), "customer-17", 4200);
var bson = order.ToBsonDocument();
var restored = BsonSerializer.Deserialize<Order>(bson);

Console.WriteLine(bson.ToJson());
Console.WriteLine(restored == order);

public sealed record Order(ObjectId Id, string CustomerId, long TotalCents);
```

几个值得注意的点：

- **ID 在序列化前自己生成**。这样就不用假设「插入后再改不可变对象」这条根本不存在的路径。
- **`customerId` 的映射写出来了**。你查询时用的是强类型表达式，但存进数据库的是这个字符串——它才是持久化契约。
- **注册要早**。官方引导建议在初始化连接前完成注册，别等第一次序列化再去补。

这里补一个原文没写、但很容易撞上的细节：同一个类型注册两次会失败。`RegisterClassMap` 内部是往字典里 `Add` 该类型，重复注册会直接报错；如果序列化器已经自动创建并冻结了这个 class map，再改它也会失败。所以要么在启动早期集中注册一次，要么用驱动提供的幂等版本 `TryRegisterClassMap`。

这也解释了为什么改一个 public 属性名不是「无害重构」：如果映射没保留旧名字，磁盘上的字段名就变了，历史文档还在用旧名。

本地做一次 `ToBsonDocument` / `Deserialize` 往返是有用的检查，因为它把映射问题和网络问题分开了。但它不证明历史文档的类型都兼容——历史数据只有真实数据能证明。

## 读取时把四个问题拆开

- **filter** 决定哪些文档匹配；
- **projection** 决定结果里有哪些字段；
- **sort** 决定顺序；
- **limit** 决定返回多少条，注意 **0 表示不限制**。

这四件事各自回答不同问题，混在一起就很难说清这次查询到底保证了什么。强类型的 `Project` 有一个重要特性：它的输出类型和集合的文档类型是两个类型，所以返回的本来就该是摘要模型，而不是半个 `Order`。

```csharp
using System;
using MongoDB.Bson;
using MongoDB.Bson.Serialization;
using MongoDB.Driver;

BsonClassMap.RegisterClassMap<Order>(map =>
{
    map.AutoMap();
    map.MapIdMember(order => order.Id);
    map.MapMember(order => order.CustomerId).SetElementName("customerId");
    map.MapMember(order => order.TotalCents).SetElementName("totalCents");
    map.MapCreator(order =>
        new Order(order.Id, order.CustomerId, order.TotalCents));
});

var uri = Environment.GetEnvironmentVariable("MONGODB_URI")
    ?? throw new InvalidOperationException("MONGODB_URI is required.");

using var client = new MongoClient(uri);
var orders = client.GetDatabase("application").GetCollection<Order>("orders");
var filter = Builders<Order>.Filter.Eq(order => order.CustomerId, "customer-17");
var sort = Builders<Order>.Sort.Descending(order => order.TotalCents)
    .Ascending(order => order.Id);

var summaries = await orders.Find(filter)
    .Sort(sort)
    .Limit(20)
    .Project(order => new { order.Id, order.TotalCents })
    .ToListAsync();

foreach (var summary in summaries)
{
    Console.WriteLine($"{summary.Id}: {summary.TotalCents}");
}

public sealed record Order(ObjectId Id, string CustomerId, long TotalCents);
```

排序里带上 `Id` 不是为了好看。服务端排序文档说明：排序键相等的文档之间不保证稳定顺序，需要确定性就得把唯一字段加进去。注意这只保证「同一份数据下顺序确定」，它不会在你翻页期间冻结集合。

`ToListAsync` 和游标迭代也是两件事。一页有界的小结果用列表返回是合理的；大批量导出需要另外讨论内存和传输方式。别因为用了异步物化，就认为无界结果变安全了。

## 写入的语义不能互换

新建一个文档、修改匹配文档的某个字段、删除匹配文档，这三类操作的返回语义并不通用——原文的做法是把它们交给已有的插入、更新、删除教程，不在这里再抄一遍重载列表。

真正要养成的习惯是**先描述操作，再选方法**：是「创建一个文档」，还是「改掉匹配文档的一个字段」，还是「删除所有匹配文档」？然后用固定版本的文档核对返回契约。

还要把「请求的操作」和「服务端返回的证据」分开。一次方法调用不自动构成事务：当前的插入文档就演示了批量插入在后续一条失败时，前面已插入的文档仍然留在库里。API 调用成功和「文档确实按预期写进去了」是两种不同强度的证据。

## 索引要回答一个具体的查询问题

索引不是「让所有操作变快」的开关。写性能文档说得很清楚：每个索引都带来写开销——插入和删除要维护对应索引键，更新可能改动受影响的索引。

所以从查询形状出发：哪个字段是等值条件？哪些字段决定排序？有没有范围条件？需要返回哪些字段？等值-排序-范围（ESR）指南解释了为什么这三者的顺序对复合索引重要，也讨论了「把选择性范围放在排序字段之前」在什么情况下有用。

那套指南只帮你形成候选，不证明某个候选赢了。explain 文档描述了 plan 阶段，也提醒输出结构随查询引擎变化、还会变；看 plan 时要保留真实响应，而不是编一个整齐的 index scan 结论。

两条容易搞混的边界：

- projection 能让返回变小，但不证明查询被索引覆盖；
- limit 能限制返回条数，但不证明服务端只检查了那么多文档。

## 分层验证，别混成一次演示

这些验证问题需要不同的证据：

| 你想确认               | 该看什么                     |
| ---------------------- | ---------------------------- |
| 字段名和存储类型对不对 | 一次本地 BSON 往返           |
| 强类型表达式渲染成什么 | 把 filter 渲染成 BSON 看结果 |
| 到底返回了哪些文档     | 一次真实的数据库读取         |
| 服务端怎么处理这个查询 | 一次 explain 响应            |

把这些混进一次演示，出问题时就找不到位置：模型反序列化失败，改索引没用；查询返回太多，改客户端注册生命周期也不会凭空多出 projection。**先给失败分类，是这个工作流最实际的好处。**

真要连数据库验证，可以用 Testcontainers 起一个临时实例——原文把这件事交给了作者已有的 `Testcontainers.MongoDb` 教程，本文不重复，也不暗示已经启动过临时数据库。

## 常见问题

**`MongoClient` 到底连了什么？** 客户端代表对一个部署的访问权，database 和 collection 句柄只是标明操作发往哪里，强类型集合再额外带上文档的序列化契约。创建这些对象不等于成功执行过一次查询。

**每个请求都该 new 一个 `MongoClient` 吗？** 官方建议单例复用。一套应用配置通常共用长生命周期的客户端，请求处理器借它用。有独立配置时才需要独立客户端——重点是让归属显式，而不是默认按请求构造。

**文档可以用不可变 record 吗？** 可以，但必须给出反序列化的创建路径，`MapCreator` 让它显式；还要决定 ID 怎么生成、CLR 成员名怎么映射到 BSON 字段。一个 record 声明本身不是兼容性检查。

**projection 会改变存储的文档吗？** 不会。读投影只描述返回形状，可以把完整文档变成摘要。别把「部分读取模型」和「用来整体替换文档的对象」混成同一个类型。

**加索引会让插入更快吗？** 不会，索引要维护写开销。读的收益要能覆盖这笔成本。explain 能帮你看查询计划，但一份生成的索引定义本身不等于测出的改进。

**这些示例在真实 MongoDB 上跑过吗？** 没有。它们对照了官方文档和带版本的驱动源码，运行时行为、部署兼容性和真实查询计划都没有验证，需要在单独授权的环境里补。

## 收尾

把这篇折成可执行的顺序：

1. 定归属：容器里 singleton 持有 `MongoClient`，请求处理器只借用；要知道 `Dispose()` 不销毁 cluster。
2. 定契约：用 `BsonClassMap` + `MapCreator` 把不可变模型、ID 生成和字段名写成显式约定，启动早期注册一次。
3. 定形状：filter / projection / sort / limit 分别写清，limit 用正数，排序补唯一字段。
4. 定证据：映射问题看 BSON 往返，查询问题看真实读取，性能问题看 explain，别互相顶替。

MongoDB 在 C# 里的难点从来不是 API 数量，而是每一层各自能证明什么。把这条线画清楚之后，加一个 `InsertOne`、换一种读法、调一个索引，都不会再混成「反正连上数据库了」。

如果你也在 .NET 项目里用 MongoDB，欢迎关注 Aide Hub。我们会继续分享驱动细节、测试夹具和真实工程约束下的数据访问实践。

## 参考

- [MongoDB in C#: Connecting, Mapping, and Reading Documents（原文，Nick Cosentino / Dev Leader）](https://www.devleader.ca/2026/10/18/mongodb-in-c-connecting-mapping-and-reading-documents)
- [Create a MongoClient（官方连接文档：singleton 建议与 Dispose 语义）](https://www.mongodb.com/docs/drivers/csharp/current/connect/mongoclient/)
- [Class Mapping（官方 class map、MapCreator 与序列化规则）](https://www.mongodb.com/docs/drivers/csharp/current/serialization/class-mapping/)
- [Find Documents（官方查询文档：游标与物化的区别）](https://www.mongodb.com/docs/drivers/csharp/current/crud/query/find/)
- [cursor.limit()（0 表示不限制）](https://www.mongodb.com/docs/manual/reference/method/cursor.limit/)
- [cursor.sort()（排序键相等时不保证稳定顺序）](https://www.mongodb.com/docs/manual/reference/method/cursor.sort/)
- [The ESR Guideline（复合索引顺序）](https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/)
- [Explain Results（plan 结构随查询引擎变化）](https://www.mongodb.com/docs/manual/reference/explain-results/)
