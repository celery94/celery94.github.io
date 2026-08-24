---
pubDatetime: 2026-08-24T13:34:44+08:00
title: ".NET 数据格式与查询语言速查"
description: "同一份数据换一种形状，适合的查询方式也会变化。本文从 CSV、关系数据库、XML、JSON、文档数据库、图数据和二进制格式出发，梳理 .NET 工具与 LINQ 的边界，帮助你快速做出选型。"
tags: [".NET", "C#", "LINQ", "数据格式"]
slug: "dotnet-data-formats-query-languages"
ogImage: "../../assets/1017/01-cover.png"
source: "https://www.binaryintellect.net/articles/96302ce2-adbb-491e-8023-02a954cad1ef.aspx"
---

在 .NET 项目里，数据可能来自 CSV 文件、关系数据库、XML 文档、HTTP API、文档数据库或消息队列。它们都能被 C# 代码读取，可读、可写、可筛选的方式却差别很大。

Bipin Joshi 在《A Field Guide to .NET Data Formats》中给出一个很实用的观察：数据的形状会影响适合它的导航方式。本文沿着这个思路整理一份速查表，帮助你先看清数据结构，再决定使用哪种查询语言和 .NET 工具。文中的代码用于说明形状与边界，具体项目仍需结合数据量、约束和运行环境验证。

## 先看数据形状

可以先用下面这张表定位方向：

| 数据形态       | 常见语言或方式             | .NET 工具                         | 查询特点                      |
| -------------- | -------------------------- | --------------------------------- | ----------------------------- |
| CSV / 分隔文本 | 解析约定                   | CsvHelper                         | 逐行读取，转成对象后使用 LINQ |
| 关系数据库     | SQL                        | ADO.NET、Dapper、EF Core          | 集合过滤、连接和聚合          |
| XML 树         | XPath、XQuery、LINQ to XML | XDocument、LINQ to XML            | 沿节点层级遍历                |
| JSON 文档      | 类型反序列化、路径访问     | System.Text.Json、Newtonsoft.Json | 类型化或按路径读取            |
| 文档数据库     | 面向 JSON 的 SQL-like 语法 | Cosmos SDK、MongoDB Driver        | 在文档范围内筛选和投影        |
| 图数据         | GraphQL、Cypher、Gremlin   | Hot Chocolate、Neo4j Driver       | 沿关系遍历                    |
| 二进制格式     | 先反序列化                 | protobuf、MessagePack             | 还原对象后再查询              |
| 内存对象       | LINQ to Objects            | .NET 内置                         | 过滤、排序、投影和分组        |

这张表的重点在最后一列：查询语言并非只由“数据存在哪里”决定，还取决于数据内部的结构。平面文本缺少关系，树形文档需要路径，图数据把关系本身放在中心；当数据进入 C# 对象后，LINQ 又成为很多场景的共同接口。

## CSV：先解析，再用 LINQ

CSV 通常只有行、列和分隔符，缺少可供查询的正式模型。引号、换行、转义字符和列类型都可能让手写的 `String.Split` 变得脆弱。CsvHelper 这类库的价值，主要在于把文本稳定地映射成类型。

```csharp
using CsvHelper;
using System.Globalization;

using var reader = new StreamReader("orders.csv");
using var csv = new CsvReader(reader, CultureInfo.InvariantCulture);

var largeOrders = csv.GetRecords<Order>()
    .Where(order => order.Total > 100)
    .ToList();
```

这里的 `Where` 运行在已经解析出来的 `Order` 对象上。CSV 本身没有把 `Total > 100` 传给某个查询引擎，真正的查询发生在转换之后。

CSV 适合导入导出、日志和简单批处理。需要多表关系、事务或复杂聚合时，应该尽早把它导入更合适的数据存储。

## 关系数据库：让 LINQ 进入 SQL 世界

关系数据库的原生语言是 SQL。ADO.NET 让你直接编写 SQL，Dapper 提供轻量的对象映射，EF Core 则允许你用 LINQ 描述查询，再交给数据库提供程序翻译：

```csharp
var largeOrders = await dbContext.Orders
    .Where(order => order.Total > 100)
    .ToListAsync();
```

这段代码看起来像内存集合查询，执行位置却取决于 `dbContext.Orders` 的类型和查询提供程序。EF Core 会尽量把表达式转换为 SQL，在数据库端完成过滤；无法翻译的表达式可能导致运行时异常，顶层投影仍有有限的客户端计算空间。

因此，LINQ 在这里带来的是统一的表达方式，不能替你隐藏数据库的工作方式。需要关注生成的 SQL、索引、事务边界、分页和数据量。把 `IQueryable` 过早变成 `IEnumerable`，也可能让后续过滤回到应用进程，带来额外网络和内存开销。

关系数据库适合强关系、事务一致性、连接和集合聚合都很重要的场景。查询性能出现问题时，应回到 SQL 和执行计划检查，不能只看 C# 表达式是否简洁。

## XML：树结构决定导航方式

XML 的核心是层级。XPath 用路径表达“从哪里走到哪里”，LINQ to XML 则把这种遍历写成更熟悉的 C# 查询：

```csharp
using System.Xml.Linq;

var document = XDocument.Load("catalog.xml");

var fictionTitles = document
    .Descendants("book")
    .Where(book => (string?)book.Attribute("category") == "fiction")
    .Select(book => (string?)book.Element("title"))
    .Where(title => title is not null)
    .ToList();
```

如果使用 XPath，同一个意图可以写成类似 `//book[@category='fiction']/title` 的路径。两种方式都在遍历树，差别主要在表达习惯和后续处理方式。

LINQ to XML 适合配置文件、SOAP 消息、Office Open XML 和有明确层级的交换文档。处理来自不可信来源的 XML 时，需要额外配置安全的 `XmlReader`，不能只因为查询代码易读就跳过输入限制。

## JSON：类型化与动态访问的分界

JSON 在 API 和半结构化数据中很常见。形状稳定时，优先反序列化成类型；形状不稳定或只需读取少数字段时，可以使用 `JsonDocument`：

```csharp
using System.Text.Json;

var orders = JsonSerializer.Deserialize<List<Order>>(json) ?? [];
var largeOrders = orders.Where(order => order.Total > 100).ToList();

using var document = JsonDocument.Parse(json);
foreach (var order in document.RootElement.EnumerateArray())
{
    if (order.GetProperty("total").GetDecimal() > 100)
    {
        Console.WriteLine(order.GetProperty("id").GetString());
    }
}
```

`System.Text.Json` 提供序列化、反序列化和内存 DOM，适合 .NET 中的大多数 JSON 场景。类型化路径能得到编译期结构和更清晰的业务代码；动态路径更能容忍未知字段，却需要自己处理缺失属性、类型不匹配和大小写行为。

原文把 JSON 的“查询语言”概括为类型化访问、动态访问和 JSONPath 的组合。这里要注意一个边界：`System.Text.Json` 自身不提供完整的 JSONPath 查询语言，需要按需使用 `JsonDocument`，或选择提供路径查询能力的其他库。

## 文档数据库：像 SQL，规则仍属于文档模型

Cosmos DB 等文档数据库把 JSON 形状的数据作为主要存储单元，查询语法常常借用了 SQL 的外形：

```sql
SELECT o.id, o.total
FROM orders o
WHERE o.total > @minTotal
```

这种语法降低了上手门槛，数据模型仍然不同于关系数据库。字段可能缺失，嵌套对象和数组是常态；分区键、索引策略、跨分区查询与请求费用都会影响实际结果。

文档数据库适合文档边界清晰、结构变化较快、需要水平扩展的场景。使用前应先确定聚合根和访问模式，再设计分区与索引。把关系数据库的表连接习惯直接搬过来，通常会让数据模型和查询成本一起变复杂。

## 图数据：关系本身就是查询目标

在社交网络、推荐、依赖分析和欺诈识别中，记录之间的关系往往比单个记录的属性更重要。

GraphQL 适合让 API 客户端声明想要的嵌套结果，例如：

```graphql
query {
  order(id: "1001") {
    id
    total
    customer {
      name
      previousOrders(last: 5) {
        total
      }
    }
  }
}
```

GraphQL 更接近 API 查询语言，允许客户端选择返回形状；它与 Neo4j 使用的 Cypher、图遍历场景中的 Gremlin 不是同一种东西。使用 .NET 时，GraphQL 通常由 Hot Chocolate 等库暴露 schema，真正的图数据库查询仍由对应驱动和数据库负责。

当问题的核心是“从这个节点沿关系走到哪里”，图数据模型才会体现优势。若关系只是偶尔通过外键查一次，关系数据库可能更直接。

## 二进制格式：先还原，再查询

Protocol Buffers 和 MessagePack 把重点放在体积、速度和跨进程传输上。二进制内容通常不适合直接阅读或临时查询，常见过程是先按照 schema 反序列化，再对得到的 CLR 对象使用普通 C# 代码：

```csharp
var order = Order.Parser.ParseFrom(binaryData);

if (order.Total > 100)
{
    // 这里已经回到普通对象处理
}
```

“二进制序列化”是一个类别，不等于可以直接使用任意历史序列化器。新项目应选择有明确 schema、版本策略和安全边界的格式；尤其不要把 `BinaryFormatter` 当作通用方案。传输协议还需要考虑字段兼容、未知字段、压缩和错误处理。

## 共同终点：LINQ to Objects

把 CSV 行、JSON 文档、数据库结果或 protobuf 消息还原成对象后，很多业务筛选都会回到同一种写法：

```csharp
var recentLargeOrders = orders
    .Where(order =>
        order.Total > 100 &&
        order.Date > DateTime.UtcNow.AddDays(-30))
    .OrderByDescending(order => order.Total)
    .Select(order => new { order.Id, order.Total })
    .ToList();
```

这解释了 LINQ 为什么像一层共同语言：它经常负责把已经进入内存的对象继续变换。它也可能被查询提供程序翻译成另一种语言，例如 EF Core 将部分 LINQ 表达式翻译成 SQL。两种情况下语法相似，执行位置和性能特征却不同。

可以用一个简单问题判断边界：这段查询发生在数据库、文档引擎、图引擎，还是已经在 C# 进程内？答案会影响索引、网络、内存、分页和错误处理。

## 一份可执行的选型顺序

面对新数据源时，可以按这个顺序检查：

1. **看形状**：平面行列、树、文档、关系、图，还是只适合传输的二进制。
2. **看查询位置**：数据源能否先过滤，还是只能完整加载后在内存中处理。
3. **看约束**：是否需要事务、schema、字段兼容、强一致或严格验证。
4. **看规模**：网络传输、分区、索引、内存和序列化成本分别在哪里发生。
5. **看失败方式**：解析失败、翻译失败、字段缺失和版本不兼容分别如何处理。

这份顺序比“统一使用 LINQ”更可靠。LINQ 可以统一一部分表达方式，数据源的真实规则仍需要被保留在设计和验证中。

## 小结

数据格式像不同地形：CSV 是平面行列，XML 是树，关系数据库强调集合和约束，JSON 与文档数据库围绕灵活文档，图数据把关系放到中心，二进制格式则优先服务于传输效率。理解这些差异后，工具选型会从“哪个库语法更顺手”变成“查询应该在哪里发生”。

原文最后预告，后续部分会继续讨论 LINQ 抽象在哪些地方会泄漏，以及向量嵌入和相似度搜索带来的新问题。这是原作者的后续主题预告，当前项目如果要使用向量检索，仍应单独验证索引、召回、成本和数据安全。

如果你在维护 .NET 数据访问层，可以先把一次真实查询从入口追到最终执行点：它在哪里解析、在哪里过滤、在哪里排序、在哪里付费。这个路径通常比单看 API 名称更能说明系统的实际行为。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践。

## 参考

- [A Field Guide to .NET Data Formats（原文，Bipin Joshi，2026-08-12）](https://www.binaryintellect.net/articles/96302ce2-adbb-491e-8023-02a954cad1ef.aspx)
- [原始入口链接（CSharp Digest）](https://csharpdigest.net/links/23034/1702724f-d69a-4a45-9063-b7a7f41f73f2/email)
- [JSON 序列化与反序列化概述 - Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/overview)
- [EF Core：客户端与服务端计算 - Microsoft Learn](https://learn.microsoft.com/en-us/ef/core/querying/client-eval)
- [LINQ to XML 查询 XML 树 - Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/linq/query-xml-trees-overview)
- [Cosmos DB 查询语言概述 - Microsoft Learn](https://learn.microsoft.com/en-us/cosmos-db/query/overview)
- [BinaryFormatter 安全指南 - Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/serialization/binaryformatter-security-guide)
