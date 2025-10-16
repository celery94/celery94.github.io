---
pubDatetime: 2024-10-21
tags: [".NET", "Architecture"]
source: https://devblogs.microsoft.com/dotnet/mongodb-ef-core-provider-whats-new/
author: Rishit Bhatia
title: MongoDB EF Core Provider 有哪些新功能？ - .NET 博客
description: MongoDB EF Core Provider 的最新更新带来了对更改跟踪、索引创建、复杂查询和事务的改进。
---

> 这是来自 Rishit Bhatia 和 Luce Carter 的客座文章。Rishit 是 MongoDB 的高级产品经理，专注于 .NET 开发者体验，在转向产品管理之前已经有多年 C# 实战经验。Luce 是 MongoDB 的开发者倡导者、Microsoft MVP，热爱编程、阳光和学习。本文由 Microsoft .NET 团队审阅以确保 EF Core 的准确性。

MongoDB 的 EF Core provider 在 2024 年 5 月已[正式发布](https://www.mongodb.com/blog/post/mongodb-provider-entity-framework-core-now-generally-available)。自六个月前首次发布预览版以来，我们取得了很大的进展。我们希望分享一些有趣的功能，这些功能是在与 Microsoft 的 .NET 数据和实体框架团队合作下才得以实现的。

在本文中，我们将使用 [MongoDB EF Core provider](https://www.mongodb.com/docs/drivers/csharp/current/) 和 [MongoDB Atlas](https://www.mongodb.com/products/platform/atlas-database) 展示以下功能：

- 添加属性到实体和更改跟踪
- 利用逃生舱创建索引
- 执行复杂查询
- 事务和乐观并发

与本博客相关的代码可以在 [Github](https://github.com/mongodb-developer/efcore_highlights) 上找到。开始的样板代码在“start”分支中。包含所有功能亮点的完整代码在“main”分支中。

## 前置条件

我们将使用 [示例数据集](https://www.mongodb.com/docs/atlas/sample-data/)——具体来说，是 MongoDB Atlas 上 _sample_mflix_ 数据库中的电影集合。在本例中，要设置带有示例数据的 Atlas 集群，可以按照[文档](https://www.mongodb.com/docs/atlas/getting-started/)中的步骤进行。我们将创建一个简单的 .NET 控制台应用程序来开始使用 MongoDB EF Core provider。有关详细信息，可以查看[快速入门指南](https://www.mongodb.com/docs/entity-framework/current/quick-start/)。

此时，您应该已经连接到 Atlas，并能够输出快速入门指南中读取的电影情节。

## 功能亮点

### 添加属性和更改跟踪

MongoDB 文档模型的优势之一是支持灵活的模式。这与 EF Core 支持的代码优先方法相结合，使您可以动态向实体添加属性。为了展示这一点，我们将向模型类添加一个新的可空布尔属性 `adapted_from_book`。这将使我们的模型类如下所示：

```csharp
public class Movie
{
    public ObjectId Id { get; set; }

    [BsonElement("title")]
    public string Title { get; set; }

    [BsonElement("rated")]
    public string Rated { get; set; }

    [BsonElement("plot")]
    public string Plot { get; set; }

    [BsonElement("adaptedFromBook")]
    public bool? AdaptedFromBook { get; set; }
}
```

现在，我们将为找到的电影实体设置这个新添加的属性，并在保存更改后查看 [EF Core 的更改跟踪](https://learn.microsoft.com/ef/core/change-tracking/) 的实际效果。为此，我们将在打印电影情节后添加以下代码行：

```csharp
movie.AdaptedFromBook = false;
await db.SaveChangesAsync();
```

在运行程序之前，让我们前往 Atlas 中的集合，找到这部电影，以确保我们要创建的新字段 `adapted_from_book` 在数据库中不存在。为此，只需转到 Atlas Web UI 中的集群并选择浏览集合。

![Atlas UI 中显示的浏览集合按钮](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2024/10/mongodb-atlas-browse-collections-ui.png)

然后，从 _sample_mflix_ 数据库中选择电影集合。在过滤器选项卡中，我们可以使用以下查询找到我们的电影：

```json
{ "title": "Back to the Future" }
```

这应该能找到我们的电影，并且我们可以确认我们打算添加的新字段确实没有显示。

![示例电影文档](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2024/10/mongodb-sample-movie-document.png)

接下来，让我们为刚刚添加的两行代码添加一个断点，以确保我们可以实时跟踪更改。选择开始调试按钮以运行应用程序。当第一个断点命中时，我们可以看到本地字段值已被分配。

![从调试器查看的本地电影字段内容](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2024/10/mongodb-contents-movie-field-view-debugger.png)

继续并检查数据库中的文档。我们可以看到新字段尚未被添加。让我们跳过保存更改调用，这将结束程序。此时，如果我们检查数据库中的文档，我们将注意到新字段已被添加，如下所示！

![添加了新字段的先前文档示例](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2024/10/mongodb-new-document-field-adapted.png)

### 索引管理

MongoDB EF Core provider 构建在现有的 [.NET/C# 驱动](https://www.mongodb.com/docs/drivers/csharp/current/)之上。这种架构的一个优势是我们可以重用已为 `DbContext` 创建的 `MongoClient`，以利用 MongoDB 的开发者数据平台提供的其他功能。这包括但不限于 [索引管理](https://www.mongodb.com/docs/drivers/csharp/upcoming/fundamentals/indexes/#list-indexes)、[Atlas Search](https://www.mongodb.com/docs/drivers/csharp/upcoming/fundamentals/atlas-search/) 和 [Vector Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/tutorials/vector-search-quick-start/)。

我们将在这个应用程序中使用驱动创建一个新索引。首先，我们将列出集合中的索引，以查看哪些索引已经存在。MongoDB 默认在 `_id` 字段上创建索引。我们将创建一个辅助函数来打印索引：

```csharp
var moviesCollection = client.GetDatabase("sample_mflix").GetCollection<Movie>("movies");
Console.WriteLine("Before creating a new Index:");
PrintIndexes();

void PrintIndexes()
{
    var indexes = moviesCollection.Indexes.List();
    foreach (var index in indexes.ToList())
    {
        Console.WriteLine(index);
    }
}
```

预期输出如下所示：

```
{ "v" : 2, "key" : { "_id" : 1 }, "name" : "_id_" }
```

现在，我们将在集合中的标题和评级字段上创建一个[复合索引](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-compound/)，并再次打印索引。

```csharp
var moviesIndex = new CreateIndexModel<Movie>(Builders<Movie>.IndexKeys
    .Ascending(m => m.Title)
    .Ascending(x => x.Rated));
await moviesCollection.Indexes.CreateOneAsync(moviesIndex);

Console.WriteLine("After creating a new Index:");
PrintIndexes();
```

我们可以看到一个名为 `title_1_rated_1` 的新索引已被创建。

```
After creating a new Index:
{ "v" : 2, "key" : { "_id" : 1 }, "name" : "_id_" }
{ "v" : 2, "key" : { "title" : 1, "rated" : 1 }, "name" : "title_1_rated_1" }
```

### 数据查询

由于 EF Core 已经支持语言集成查询（LINQ）语法，因此在 C# 中编写强类型查询变得很容易。基于我们模型类中可用的字段，我们可以尝试从集合中找到一些有趣的电影。假设我想找到所有评级为“PG-13”、情节中包含“shark”一词的电影，但我希望它们按标题字段排序。我可以通过以下查询轻松实现：

```csharp
var myMovies = await db.Movies
    .Where(m => m.Rated == "PG-13" && m.Plot.Contains("shark"))
    .OrderBy(m => m.Title)
    .ToListAsync();

foreach (var m in myMovies)
{
    Console.WriteLine(m.Title);
}
```

然后我们可以使用上面的代码打印查询并使用 `dotnet run` 运行程序以查看结果。我们应该能够在控制台中看到从我们的集合中的 20K+ 部电影中打印出的两个电影名称，如下所示。

```
Jaws: The Revenge
Shark Night 3D
```

如果你希望看到发送到服务器的查询，在这种情况下是 MQL，那么可以在 DbContext 的 `Create` 函数中启用日志记录，如下所示：

```csharp
public static MflixDbContext Create(IMongoDatabase database) =>
    new(new DbContextOptionsBuilder<MflixDbContext>()
        .UseMongoDB(database.Client, database.DatabaseNamespace.DatabaseName)
        .LogTo(Console.WriteLine)
        .EnableSensitiveDataLogging()
        .Options);
```

这样，当我们再次运行程序时，可以在详细日志中看到如下内容：

```
Executed MQL query
sample_mflix.movies.aggregate([{ "$match" : { "rated" : "PG-13", "plot" : /shark/s } }, { "$sort" : { "title" : 1 } }])
```

### 自动事务和乐观并发

是的，你没看错！MongoDB EF Core provider 从 8.1.0 版本开始支持事务和乐观并发。这意味着默认情况下，`SaveChanges` 和 `SaveChangesAsync` 是事务性的。这将使在生产级工作负载中发生任何故障时自动回滚操作，并确保所有操作通过[乐观并发](https://en.wikipedia.org/wiki/Optimistic_concurrency_control)得到满足。

如果你想关闭事务，可以在调用任何 `SaveChanges` 操作之前在初始化阶段这样做。

```csharp
db.Database.AutoTransactionBehavior = AutoTransactionBehavior.Never;
```

该 provider 支持两种乐观并发的方法，具体取决于你的要求，分别是通过并发检查或行版本。你可以在[文档](https://www.mongodb.com/docs/entity-framework/current/fundamentals/optimistic-concurrency/)中了解更多信息。我们将使用 RowVersion 来演示此用例。这利用了模型类中的 `Version` 字段，该字段将由 MongoDB EF Provider 自动更新。要添加版本，我们在模型类中添加以下内容。

```csharp
[Timestamp]
public long? Version { get; set; }
```

首先，让我们创建一个名为 `myMovie` 的新电影实体，如下所示，并将其添加到 `DbSet`，然后调用 `SaveChangesAsync`。

```csharp
Movie myMovie1 = new Movie {
    Title = "The Rise of EF Core 1",
    Plot = "Entity Framework (EF) Core 是流行的 Entity Framework 数据访问技术的轻量级、可扩展、开源和跨平台版本。",
    Rated = "G"
};

db.Movies.Add(myMovie1);
await db.SaveChangesAsync();
```

现在，让我们创建一个与上面类似的新 `DbContext`。我们可以将数据库创建移到一个变量中，这样我们就不必再次定义数据库名称。使用这个新上下文，让我们为我们的电影添加续集并将其添加到 DbSet。我们还将添加第三部分（是的，这是一个三部曲），但是使用与第二个电影实体相同的 ID 添加到这个新上下文中，然后保存我们的更改。

```csharp
var dbContext2 = MflixDbContext.Create(database);
dbContext2.Database.AutoTransactionBehavior = AutoTransactionBehavior.Never;
var myMovie2 = new Movie { Title = "The Rise of EF Core 2" };
dbContext2.Movies.Add(myMovie2);

var myMovie3 = new Movie { Id = myMovie2.Id, Title = "The Rise of EF Core 3" };
dbContext2.Movies.Add(myMovie3);
await dbContext2.SaveChangesAsync();
```

由于现在支持事务，我们后两部电影实体的第二组操作不应该通过，因为我们尝试添加它们时使用了已经存在的 `_id`。我们应该看到一个异常，并且事务应该被回滚，因此数据库中只会看到一部电影。让我们运行并查看是否属实。

我们确实看到一个异常，并且我们可以确认数据库中只插入了一部电影（第一部分）。

![由于要添加的文档具有与现有文档相同的 id，事务抛出的异常](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2024/10/mongodb-transaction-exception.png)

以下显示数据库中只有一个文档，因为事务被回滚。

![由于事务被回滚，数据库中只有一个文档](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2024/10/mongodb-transaction-rollback.png)

别担心，我们会正确地将我们的三部曲添加到数据库中。让我们移除我们的第三个实体上的 `_id` 分配，让 MongoDB 自动为我们插入。

```csharp
var myMovie3 = new Movie { Title = "The Rise of EF Core 3" };
```

重新运行程序后，我们可以看到所有实体都已添加到数据库中。

![由于修复了重复的 id 问题，数据库中的三部曲所有三部电影](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2024/10/mongodb-duplicate-exception-fix.png)

## 总结

我们使用 [MongoDB EF Core provider](https://www.mongodb.com/docs/drivers/csharp/current/) 和 [MongoDB Atlas](https://www.mongodb.com/products/platform/atlas-database) 展示了不同的功能，例如动态向实体添加属性、利用逃生舱创建索引、通过 LINQ 执行复杂查询，以及演示新增的事务和乐观并发支持。

## 了解更多

要了解更多关于 EF Core 和 MongoDB 的信息：

- 查看 [EF Core 文档](https://learn.microsoft.com/ef/core/) 以了解更多关于使用 EF Core 访问各种数据库的信息。
- 查看 [MongoDB 文档](https://www.mongodb.com/docs/) 以了解更多关于在任何平台上使用 MongoDB 的信息。
- 查看 [MongoDB EF Core provider 文档](https://www.mongodb.com/docs/entity-framework/current/quick-start/) 以获取更多入门信息。
- 在 Microsoft YouTube 频道上观看关于 [EF Core 9: Evolving Data Access in .NET](https://www.youtube.com/watch?v=LuvdiUggQrU&list=PLdo4fOcmZ0oUZz7p8H1HsQjgv5tRRIvAS&index=19) 的演讲。
