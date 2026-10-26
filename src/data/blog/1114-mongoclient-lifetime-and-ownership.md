---
pubDatetime: 2026-10-26T08:15:00+08:00
title: "MongoClient 单例之后：Dispose 释放了什么"
description: "MongoClient 注册成单例几乎是共识，但 Dispose 并不会释放底层集群和连接池。本文拆开容器所有权、集群注册表和请求借用者三层，附无服务器环境下构造、句柄与查询的实测对照。"
tags: ["MongoDB", "ASP.NET Core", ".NET", "Dependency Injection"]
slug: "mongoclient-lifetime-and-ownership"
ogImage: "../../assets/1114/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/23/mongoclient-in-aspnet-core-lifetime-and-resource-ownership"
---

`IMongoClient` 注册成单例，几乎每篇 ASP.NET Core + MongoDB 的教程都这么写。于是很容易顺手得出第二个结论：应用关闭时 DI 容器会释放这个单例，连接也就干净地关掉了。

第二句不成立。从 v3 起 `MongoClient` 实现了 `IDisposable`，容器确实会释放它自己创建的那个 client，但官方文档写明：释放 `MongoClient` 不会释放它背后的 cluster 和底层连接。

多出来的这一层，就是 Nick Cosentino 这篇 [MongoClient in ASP.NET Core: Lifetime and Resource Ownership](https://www.devleader.ca/2026/10/23/mongoclient-in-aspnet-core-lifetime-and-resource-ownership) 要拆的东西。单例解决「一个应用复用同一个 client」，资源所有权解决「谁在什么时候释放 client 背后的东西」。两件事混在一起，代码里会出现两类错误：在请求里释放共享的 client，或者没确认其他借用者就手动拆掉集群。

原文是读文档和源码写成的，示例没有执行。能测的部分我测了：构造 client、拿句柄、真正发查询，在一台没有 MongoDB 服务器的机器上分别是什么结果。下面按注册、借用、释放的顺序重述，最后留一张分层核对的表。

## 单例解决复用，不解决所有权

`MongoClient` 挂着集群、连接池和监控，不适合按请求创建。官方连接文档的建议是给它一个 singleton 生命周期，让整个应用复用一个 client。

那句话后面还有半句：长期持有也可能带来内存占用和未释放的资源。这半句经常被省略，但它恰好说明这里有两道题——前半句解决复用，后半句要靠所有权来说清。

复用也不强制整条调用链单例。`OrderReader` 可以是 scoped，拿当前用户、租户、请求上下文；把「当前用户 ID」存进注册成单例的仓储字段，两个并发请求会互相看见对方的身份。

## 注册时让配置失败发生在启动时

原文的注册写法很短，重点在把配置错误挡在启动阶段：

```csharp
var builder = WebApplication.CreateBuilder(args);
var uri = builder.Configuration["Mongo:ConnectionString"]
    ?? throw new InvalidOperationException(
        "Mongo:ConnectionString is required.");
var databaseName = builder.Configuration["Mongo:Database"]
    ?? throw new InvalidOperationException(
        "Mongo:Database is required.");

builder.Services.AddSingleton<IMongoClient>(_ => new MongoClient(uri));
builder.Services.AddSingleton<IMongoDatabase>(services =>
    services.GetRequiredService<IMongoClient>().GetDatabase(databaseName));
```

不要写 `?? "mongodb://localhost:27017"`。这个兜底会把「生产环境配置丢了」变成「连上了一个碰巧存在的本地库」，错误从启动报错变成运行时的空结果或超时，定位成本高得多。

这两行注册还写明了所有者：client 由容器创建。Microsoft 的 [DI 指南](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines)把容器创建的实例和外部传入的实例分开处理，前者由容器负责清理，后者不归容器管。所以 `AddSingleton<IMongoClient>(_ => new MongoClient(uri))` 的所有者是容器，而 `AddSingleton<IMongoClient>(alreadyCreatedClient)` 不是。

微软的 [ASP.NET Core + MongoDB 教程](https://learn.microsoft.com/en-us/aspnet/core/tutorials/first-mongo-app)走的是另一种写法：把 `BooksService` 注册成单例，在服务的构造函数里 `new MongoClient(uri)`。生命周期建议一样，所有者换了人——client 由 service 创建，释放责任也跟着转到 service 身上。照抄之前先确认那个 service 有没有实现 `IDisposable`。

## 句柄不是连接

原文重点提醒过：`GetDatabase` 会复用 client 的集群和操作执行器，它不是「打开一个请求级连接」。我把这句话验证了一遍。

环境：Windows 11，.NET SDK 10.0.402，MongoDB.Driver 3.13.0，本机没有运行 MongoDB 服务，27017 端口拒绝连接；连接串是 `mongodb://127.0.0.1:27017/?serverSelectionTimeoutMS=1000`。

| 动作        | 具体调用                                                      | 结果                                          | 耗时                                 |
| ----------- | ------------------------------------------------------------- | --------------------------------------------- | ------------------------------------ |
| 构造 client | `new MongoClient(uri)`                                        | 成功，不抛异常                                | 首次 104–276 ms，同进程再建 0.1–1 ms |
| 取句柄      | `GetDatabase("app")`、`GetCollection<BsonDocument>("orders")` | 成功，不抛异常；`db.Client` 就是同一个 client | 1.4–2.9 ms                           |
| 真正查询    | `CountDocumentsAsync(Filter.Empty)`                           | 抛 `System.TimeoutException`                  | 约 1035 ms                           |

三条结果连起来看：构造 client、拼出 database 和 collection 句柄全部在毫秒级完成；第一次真正发查询，才等到 1 秒 server selection 超时。访问发生在操作那一步，句柄只是命名空间加类型。

超时的异常类型值得单独记一笔。`System.TimeoutException` 不是 `MongoException` 的子类，`catch (MongoException)` 捕不到它。我用同一个调用分别试了两个 catch 分支，只有 `catch (TimeoutException)` 命中。异常消息是 `A timeout occurred after 1008ms selecting a server using CompositeServerSelector{...}`，cluster 状态是 `Disconnected`。

把句柄当成就绪检查，是这类代码最常见的误判：`GetDatabase` 返回了对象，说明配置拼装成功，说明不了凭据有效、目标可达，也说明不了存储的文档能反序列化成你的模型。

## 请求服务只是借用者

scoped 服务可以注入单例 client，自己挑数据库和集合，再暴露一个窄操作。它持有引用，不代表它拥有背后的资源：

```csharp
builder.Services.AddSingleton<IMongoClient>(_ => new MongoClient(uri));
builder.Services.AddScoped<OrderReader>();

app.MapGet("/orders/{id}", async (
    string id, OrderReader reader, CancellationToken cancellationToken) =>
{
    var order = await reader.FindAsync(id, cancellationToken);
    return order is null
        ? Results.NotFound()
        : Results.Text(order.ToJson(), "application/json");
});

public sealed class OrderReader(IMongoClient client)
{
    private readonly IMongoCollection<BsonDocument> _orders =
        client.GetDatabase("application").GetCollection<BsonDocument>("orders");

    public Task<BsonDocument?> FindAsync(string id, CancellationToken cancellationToken)
    {
        var filter = Builders<BsonDocument>.Filter.Eq("_id", id);
        return _orders.Find(filter).FirstOrDefaultAsync(cancellationToken);
    }
}
```

这里没有谁去释放 client。请求取消交给操作本身，`FindAsync` 在查不到时返回 null，handler 把它和「数据库异常」区分开，不把异常吞成空结果。

反过来也常见：在 handler 里 `using var client = new MongoClient(uri)`，请求结束就释放。这个写法每请求建一个 client，释放时又把它从注册表里借来的集群还回去，至于关掉了什么，取决于当时的共享情况。请求结束和资源所有者结束是两个事件，代码最好让它们保持分开。

## 容器释放 client 时发生了什么

所有权在 DI 里可以观察。用工厂注册 `AddSingleton<IMongoClient>(_ => new MongoClient(uri))` 之后，两个独立 scope 解析出的 client 是同一个实例，database 句柄也是；释放第一个 scope，client 照常可用——scope 是借用者，不拥有单例。

真正的释放发生在 provider（在应用里是 host）释放的时候。容器工厂创建的那个 client 会被 `Dispose()`，之后再调 `GetDatabase` 或发查询，抛的是 `ObjectDisposedException: Cannot access a disposed object`，`Object name: 'MongoClient'`。

换个注册方式就不同：把外部已经建好的 client 直接 `AddSingleton(existingClient)` 注册进去，provider 释放后它仍然可用。我用一个自定义 `IDisposable` 做过对照，容器工厂创建的实例 Dispose 被调用了 1 次，外部注册的实例 0 次。

`MongoClient` 在这个版本只实现 `IDisposable`，没有实现 `IAsyncDisposable`，`await using` 用不了。

这些现象证明到哪一步为止：`ObjectDisposedException` 说明 .NET 对象被标记为已释放，不能说明服务端的 socket、心跳和连接池已经回收。后者要看到驱动内部和服务器侧的状态，在一台没有 MongoDB 的机器上做不到。

## Dispose 的边界要按驱动版本读

从 v3.0 起 `MongoClient` 实现了 `IDisposable`。这个事实容易让人把释放方法当成「关闭」方法，官方文档说的却是另一件事：释放 client 不会释放 cluster 和底层连接，那些资源要走 `ClusterRegistry.UnregisterAndDisposeCluster`。

源码也对得上。`Dispose(bool)` 里做的是释放操作执行器、通过 `ClusterSource.Return(_cluster)` 把 cluster 还回去、释放加密控制器（如果存在），然后标记自己已释放——没有 `_cluster.Dispose()`。注册表维护一张按 cluster key 分组的字典，需要时创建或复用，只有注销方法会把条目移出并真正释放集群。默认的 cluster source 让「还回去」变成一次空操作，集群继续留在注册表缓存里。

所以「host 释放了 client」和「host 释放了集群」是两句不同的话。第一句在注册代码里就能看到，第二句要看还有没有别的 client 共用、以及用的是哪个 cluster source。

版本这块补一句：原文基线的驱动是 3.12.0，写这篇时 NuGet 上已经是 3.13.0。两个版本的 disposal 相关源码逐字节相同，上面这些行为对最新版同样成立。

## 共享集群让顺手关掉变危险

设想你的服务注册了一个 client，另一个库（缓存、审计、某个 SDK）用等价配置也建了一个。如果基础设施被共用，服务集合里那个可见的 client 只是所有权图的一部分。这时手动释放共享集群，可能把另一个借用者的连接一起拆掉。

另一个方向的错误同样常见：看到两个 `MongoClient` 对象，就断言它们各自独占一套连接。应用层的对象身份证明不了基础设施的独立所有权。

注册表按 cluster key 复用是真的，但 key 由具体设置算出来，不是 URI 字符串本身；「同一个连接串就等于同一个池」不能随口承诺。确认不了共享范围，就把不确定性写进文档，而不是加一段无条件的关闭回调。

## 换配置是替换，不是请求状态

构造函数拿的是 settings 的冻结副本。client 建好之后再去改原来那个 `MongoClientSettings` 实例，不会重新配置它。

这条我也测了：把 `ServerSelectionTimeout` 从 1000 ms 改成 200 ms 之后，已创建的 client 查询仍然等了 1039 ms；构造前就设成 300 ms 的对照组，查询 312 ms 就超时。

所以凭据轮换、换集群、改超时，都需要一个明确的替换方案：什么时候建新 client，旧 client 由谁释放，切换期间还在用旧 client 的请求怎么办。这些属于应用级输入，不该由请求参数驱动；按请求改共享对象的字段，等于把并发安全交给运气。

## 四层问题分开验证

配置解析、DI 解析、服务端访问、关闭行为是四层，各自的测试不能互换。能解析出 `OrderReader`，只证明 DI 能拼出对象图；能跑通一条 count，只证明那个环境和权限下访问通了；host 停止不抛异常，也不证明集群被释放了。

原文给了一张边界表，我按自己的理解重排了一版：

| 对象或关系      | 能证明什么                  | 不能证明什么          |
| --------------- | --------------------------- | --------------------- |
| 容器创建的单例  | 应用级复用，容器释放 client | 独占集群和连接        |
| 请求级 reader   | 更短命的借用者              | 有权释放借来的 client |
| database 句柄   | 数据库名配置正确            | 服务端可达、凭据有效  |
| collection 句柄 | 集合名和文档类型            | 存储文档符合契约      |
| 注册表中的集群  | 同配置可能复用基础设施      | 只有一个 client 依赖  |

## 先说清谁拥有，再写关闭代码

回到开头那个问题：请求里的服务要不要释放 client。答案取决于所有者是谁。client 由容器创建，就由容器释放；请求服务只借引用。写不出这句所有权归属时，先别加清理代码。

下次提交 `AddSingleton<IMongoClient>`，在 PR 描述里补两句：谁创建它，还有谁可能共用同一个集群。两句都能写清楚，那段「顺手 unregister」就没有必要；写不清楚，就把不确定性留在文档里，等一个真实的关闭需求出现再处理。

如果业务确实需要隔离，比如多租户连不同集群、或者安全边界不同，那就在注册处显式建多个 client，各自有明确的所有者，比在一个 client 上做条件分支清楚得多。

## 参考

- [原文：MongoClient in ASP.NET Core: Lifetime and Resource Ownership](https://www.devleader.ca/2026/10/23/mongoclient-in-aspnet-core-lifetime-and-resource-ownership)
- [Create a MongoClient（MongoDB C# Driver 连接指南）](https://www.mongodb.com/docs/drivers/csharp/current/connect/mongoclient/)
- [ClusterRegistry.UnregisterAndDisposeCluster() API](https://mongodb.github.io/mongo-csharp-driver/3.12.0/api/MongoDB.Driver/MongoDB.Driver.ClusterRegistry.UnregisterAndDisposeCluster.html)
- [MongoClient.cs（v3.12.0 源码）](https://raw.githubusercontent.com/mongodb/mongo-csharp-driver/v3.12.0/src/MongoDB.Driver/MongoClient.cs)
- [Dependency injection guidelines（实例由谁释放）](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines)
- [Create a web API with ASP.NET Core and MongoDB](https://learn.microsoft.com/en-us/aspnet/core/tutorials/first-mongo-app)
