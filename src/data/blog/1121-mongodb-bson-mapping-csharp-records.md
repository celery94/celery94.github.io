---
pubDatetime: 2026-10-29T08:07:06+08:00
title: "MongoDB BSON 映射：字段名、ID 与不可变记录"
description: "BSON 映射是 C# 对象与存储文档之间的契约。本文拆开字段名、ID 表示、不可变记录的创建路径、注册时机与多余字段策略，并给出一份可落成测试的兼容性检查清单。"
tags: ["MongoDB", "C#", ".NET", "BSON", "Serialization"]
slug: "mongodb-bson-mapping-csharp-records"
ogImage: "../../assets/1121/01-cover.png"
source: "https://www.devleader.ca/2026/10/28/mongodb-bson-mapping-in-c-typed-models-and-immutable-records"
---

集合里存的是 `displayName`，C# 属性叫 `DisplayName`。类型声明看起来完全够用，`ToBsonDocument()` 在本地也照常返回结果，可一读到这些旧文档，驱动就抛 `FormatException`，说字段对不上——除非映射里把这条对应关系写明。BSON 映射要回答的就是这一类问题：它是 C# 对象与存储文档之间的契约，不在类型声明里。

这份契约里有四个建模决定要显式写下来：字段名、不可变对象从哪里创建、ID 用哪种 BSON 类型表示、旧文档里多出来的字段怎么处理。另有一条约束属于装配阶段：映射必须在第一个使用者之前注册。Dev Leader 的这篇文章（Nick Cosentino，2026 年 10 月 28 日）逐项拆了这几件事，并且明确说明它的示例只做过源码审查、没有编译执行。这个边界值得注意，因为映射的坑大多出现在「已经存进去的历史文档」上，本机跑一次 round trip 证明不了。下面按这四条展开，注册时机放在中间单独说。

## 类型声明管不到存储里已有的文档

官方类映射指南的说法是：当类代表集合里的数据时，驱动会为它创建 class map，把文档字段接到成员上，再按成员类型选序列化器。存储类型和期望成员类型不兼容，反序列化就可能抛异常。

版本上有个时间差：原文以驱动 3.12.0 为基线，官方文档站的 API 链接现在仍指向它；NuGet 上的最新稳定版是 3.13.0，2026 年 10 月 23 日发布，本文提到的映射 API 在两个版本里都在。3.13.0 的 release notes 修了多项 CVE、收紧了非法 BSON 输入的校验，正好和这篇讲的序列化边界相关，生产环境没有理由留在旧版。运行时方面，3.x 从 .NET Framework 4.7.2 起支持，官方兼容表目前只写到 3.12。

文档形状是另一回事：编译器看不到那些已经存进去的 BSON。当前写入方一致，不代表历史文档一致：旧版本可能用别的字段名，另一个服务可能用不同的 BSON 类型写同一个字段，导入的数据可能缺少当前构造函数需要的成员。这些都不是 C# 能检查的东西。

所以要把三种形状分开看：应用模型、持久化的 BSON 文档、对外返回的 API 响应。它们可以共享字段，但用途不同。一个响应模型不该因为某个客户端字段改名，就顺带触发一次存储迁移。

## 字段名要显式写出来

官方 POCO 文档说明默认行为：属性名和大小写原样保留；也记录了用特性、约定或显式 class map 改掉它的机制。结果 `CustomerId` 和 `customerId` 在人眼里等价，在驱动眼里是两个字段。集合里存的是其中一个，代码里期望另一个，这个差异必须写进映射。C# 里改个属性名，应该被当作可能的存储契约变更来评审。

下面这段摘自原文，省略了 using、record 类型声明和控制台输出：

```csharp
BsonClassMap.RegisterClassMap<Customer>(map =>
{
    map.AutoMap();
    map.MapIdMember(customer => customer.Id);
    map.MapMember(customer => customer.DisplayName)
        .SetElementName("displayName");
    map.MapMember(customer => customer.LoyaltyPoints)
        .SetElementName("loyaltyPoints");
    map.MapCreator(customer => new Customer(
        customer.Id, customer.DisplayName, customer.LoyaltyPoints));
});

var customer = new Customer(ObjectId.GenerateNewId(), "Ada", 150);
var document = customer.ToBsonDocument();
var restored = BsonSerializer.Deserialize<Customer>(document);
```

`AutoMap` 先把成员按约定接一遍，`SetElementName` 覆盖字段名，`MapCreator` 指定反序列化时用哪个表达式创建对象。原文声明这些代码没有执行过，它展示的是文档里写明的 API 用法。真要抄，先在本地编译跑一遍。

## 不可变记录需要一条创建路径

不可变记录在驱动里不止一条创建路径。官方映射指南给了两条显式的：构造函数加 `[BsonConstructor]`，或者在 class map 里用 `MapCreator`；共同点是反序列化必须有一个受支持的方式来创建对象。positional record 不加任何标记通常也能反序列化，但走的是另一条路：驱动用 `FormatterServices.GetUninitializedObject` 造出实例，再通过 init setter 填值。主构造函数的函数体不会执行，你在 record 里写的校验、归一化逻辑因此被跳过。原文选择 `MapCreator`，就是为了让创建走自己写的表达式。

只读成员要额外留神。POCO 文档提醒过普通 getter-only 属性的问题：能序列化，不等于有反序列化路径。驱动默认约定包里还有一个 `ImmutableTypeClassMapConvention`（3.12 与 3.13 都有），会把「完全没有公开可写属性、构造参数名与属性名对应」的类型按那个构造函数映射；它在 API 参考和源码里，官方指南页没有专门介绍它。原文一律用显式 creator map，不依赖这些推断——好处是映射行为由自己写的 creator 表达式决定，不随驱动的推断规则变化。

还有一个容易混进来的东西：派生出来的展示字段。它可能对应用代码有用，但不该顺手存进去。如果确实要持久化，先决定它是权威数据还是派生值；否则将来计算逻辑一改，旧文档里的值会一直和新代码对不上。

## `Id` 这个名字不决定 BSON 类型

类映射文档写明：公有成员叫 `Id`、`id` 或 `_id` 时，默认映射到 BSON 的 `_id` 字段；显式 ID 映射也有对应 API。这回答了「哪个成员是 ID」，没有回答「ID 用什么 BSON 类型」。`ObjectId`、装着十六进制字符的字符串、`Guid`，是三种不同的表示。一个看起来像 ObjectId 的字符串，不会自动按 BSON ObjectId 存储，除非序列化器或表示规则做了这个选择。

原文用第二段示例把 C# 端的 `string` 显式存成 BSON ObjectId（同样省略了外围代码）：

```csharp
BsonClassMap.RegisterClassMap<Account>(map =>
{
    map.AutoMap();
    map.MapIdMember(account => account.Id)
        .SetSerializer(new StringSerializer(BsonType.ObjectId));
    map.MapMember(account => account.Name).SetElementName("name");
    map.MapCreator(account => new Account(account.Id, account.Name));
});

var account = new Account(ObjectId.GenerateNewId().ToString(), "Example account");
var document = account.ToBsonDocument();
var restored = BsonSerializer.Deserialize<Account>(document);
```

注意 ID 是在构造对象时生成好再传进去的。不可变记录没法在插入阶段被驱动改写字段，所以不能指望「插入时自动补一个 ObjectId」。如果 ID 本身是人工输入的可读字符串，就不该因为属性类型是 `string` 而套上 ObjectId 表示；存储契约要跟着业务上的标识含义走。查询也受这条约束——过滤条件里的 ID 表示必须和存储一致，否则查询写得再对也匹配不到文档。

## 映射要在第一个使用者之前注册

一次 `ToBsonDocument()` 调用、一次序列化器查找，都可能在任何数据库连接建立之前就需要映射。官方指南的要求正是这个方向：class map 要在需要它之前注册，并建议在初始化连接之前完成。这属于应用装配阶段的工作，不该放进每个请求处理器里。

所以注册点要放在一个可预期的启动边界上，覆盖到这些路径。原文还提醒了一句：它的示例是彼此独立的控制台程序。别把所有注册粘进同一个进程、对同一个类型反复注册，好像它们是按操作生效的配置；每个类型注册一次。

这个原则和依赖注入的装配有点像：消费者依赖之前，组合已经完成。但驱动这条时序规则来自类映射文档，不是 DI 带来的。

## 多余的字段：三种态度，先选边界

BSON 里出现没有对应成员的字段时，类映射文档给出的默认行为是抛异常（`FormatException`，信息里会写出对不上的字段名）；另外两种选择是忽略多余元素（`[BsonIgnoreExtraElements]` 或 `SetIgnoreExtraElements(true)`），以及把它们捕获到一个带 `[BsonExtraElements]` 的 `BsonDocument` 成员里（class map 里对应 `MapExtraElementsMember`）。

忽略多余字段能让读取方容忍更新的应用写出来的文档，代价是这些值不进入模型。读一遍再整体写回时，别假设那些没被捕获的字段会被保留；就算用捕获模式，官方文档也提到回写之后多余字段的顺序可能变化。严格读取能让意外字段更早暴露，代价是写方加字段时需要协调。这两种都不是通用架构结论。先把兼容边界说清楚，再选对应的映射行为。

原文的第三段示例演示了一个刻意宽松的读取方（同样省略了 using）：

```csharp
BsonClassMap.RegisterClassMap<CustomerView>(map =>
{
    map.AutoMap();
    map.MapIdMember(customer => customer.Id);
    map.MapMember(customer => customer.DisplayName)
        .SetElementName("displayName");
    map.SetIgnoreExtraElements(true);
    map.MapCreator(customer =>
        new CustomerView(customer.Id, customer.DisplayName));
});

var document = new BsonDocument
{
    { "_id", ObjectId.GenerateNewId() },
    { "displayName", "Ada" },
    { "loyaltyPoints", 150 }
};

var view = BsonSerializer.Deserialize<CustomerView>(document);
Console.WriteLine(view.DisplayName);
Console.WriteLine(view.ToBsonDocument().ToJson());

public sealed record CustomerView(ObjectId Id, string DisplayName);
```

文档里带着 `loyaltyPoints`，view 里没有这个成员，于是被忽略。这是读取契约的演示，不要当成用残缺视图代替完整客户文档的理由。

## 本机 round trip 证明不了历史文档

BSON 映射的兼容性其实是几个独立问题：字段名没变吗？BSON 类型和选定的序列化器兼容吗？值缺失时对象还能构造吗？出现未知字段时应该怎样？应用对值的解释一致吗？

新构造一个对象、序列化再反序列化，只回答了其中一部分——它证明当前写方和当前读方在那个值上达成了一致，不证明能读旧版本的 fixture，也不证明能读另一个应用写的文档。

想让这套检查有未来价值，就从应用打算支持的版本里取有代表性的 BSON fixture，带上多余字段和真实的 ID 表示；可选字段要测缺失。只测一个永远会提供该值的新对象，这一整类情况都覆盖不到。本地 fixture 能隔离出序列化器的问题；真实集合才能说明线上文档是否满足这份契约。

也别为了让某个失败的例子通过就悄悄换序列化器。表示方式的改动会改变未来写方产生的 BSON，集合里可能因此混着两种形态，需要单独的兼容策略。

还有一条容易忽略：值的表示和值的含义是两件事。一个正确序列化的 `long`，可能代表完全错误的业务数量；一个正确存储的字符串，可能装的是另一个域的标识符。序列化验证技术形状，应用层的校验定义可接受的值。两层混在一起，「映射没问题」就会掩盖掉业务错误。

原文刻意没有讨论嵌入还是引用、也不涉及迁移基础设施，那些是更大的数据建模话题。它只下一个较窄的结论：序列化出来的成员契约，值得独立于领域对象的便利性单独评审。

## 把契约落成一组能跑的检查

回到开头那个 `displayName` 的例子。要确认这类问题，不需要先接数据库，用 BSON fixture 加一个测试项目就够：

- 从最老的集合里导出几条文档，转成 JSON 或 `.bson` 文件放进测试资源，作为历史形态的样本
- 每条 fixture 各写一个断言：用当前映射反序列化，检查字段值、ID 的 `BsonType`，以及缺字段时的行为
- 单独覆盖「多一个字段」「ID 是字符串但按 ObjectId 存」「可选字段缺失」「类型不兼容」四类情况，它们分别落在多余字段策略、ID 表示、构造路径和类型兼容四个位置
- 映射注册放在测试夹具的初始化里，一个类型一次，别在单个测试里重复注册

这组检查跑通，说明读取方对你收录的这几种历史形态有把握；跑不通，也正好定位到是名字、类型还是构造路径的问题。

改映射之前先看历史文档，是这份契约里最省事的习惯。把四件事写进一份决策记录——字段名、创建路径、ID 表示、多余字段策略——以后谁再改模型，都能看出这次改动会不会动到存储。

## 参考

- [MongoDB BSON Mapping in C#: Typed Models and Immutable Records](https://www.devleader.ca/2026/10/28/mongodb-bson-mapping-in-c-typed-models-and-immutable-records)
- [MongoDB C# Driver documentation](https://www.mongodb.com/docs/drivers/csharp/current/)
- [Class Mapping](https://www.mongodb.com/docs/drivers/csharp/current/serialization/class-mapping/)
- [POCOs](https://www.mongodb.com/docs/drivers/csharp/current/serialization/poco/)
- [ImmutableTypeClassMapConvention source](https://github.com/mongodb/mongo-csharp-driver/blob/v3.13.0/src/MongoDB.Bson/Serialization/Conventions/ImmutableTypeClassMapConvention.cs)
- [MongoDB.Driver on NuGet](https://www.nuget.org/packages/MongoDB.Driver)
- [mongo-csharp-driver releases](https://github.com/mongodb/mongo-csharp-driver/releases)
