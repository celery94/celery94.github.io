---
pubDatetime: 2026-07-15T09:09:24+08:00
title: "Vertical Slice Architecture 怎么测：把切片当成功能来测"
description: "VSA 没有 Service 层可以 mock、没有 Repository 可以替换，这让习惯分层架构的开发者觉得难测。其实反过来：一个切片就是一个功能入口，你只需要从端点打到真实数据库就够了。这篇把夹具搭建、断言技巧、单元测试边界和架构测试一次说清楚。"
tags: ["Vertical Slice Architecture", "VSA", "集成测试", ".NET", "测试"]
slug: "how-to-test-vertical-slice-architecture"
ogImage: "../../assets/940/01-cover.png"
source: "https://milanjovanovic.tech/blog/how-to-test-vertical-slice-architecture"
---

每次写 Vertical Slice Architecture，总会收到同一类问题："行，但怎么测？"

这个疑问很自然，因为我们学测试的时候，周围全是分层架构：mock 掉 Repository，测 Service，断言 Service 调了 Repository。而在 VSA 里，没有 Service 层让你测，也经常没有 Repository 让你 mock。一个切片就是一次请求、一个 handler 加一次数据库操作，全放在一个地方。

很多人读到这儿就觉得垂直切片难测。其实正相反。你只需要停止"测层"，开始"测功能"。

## 切片就是测试单元

一个垂直切片有一个天然契约：请求从顶部进入，可观测的结果从底部出来——一个响应、加上数据库里几行记录、也许再加一条消息总线上的事件。

所以就用这个契约来测：

**一个切片 = 一组聚焦的测试，从端点打到数据库。**

不是 handler 测试配一个 mock 的 `DbContext`，也不是端点测试配一个 mock 的 handler。是整个切片，通过它的公开入口，打到真实数据库上。

如果你从分层架构转过来，这就像"只写集成测试"。本来就是，而且这才是关键：对于这类代码，测试金字塔并不适用。一个切片测试能一口气抓到写错的 SQL、写错的映射、写错的验证和写错的路由——这些事 mock 掉的单元测试一个都看不到。

## 让切片测试跑得动的两块拼图

两样东西让切片测试快到可以持续跑：`WebApplicationFactory` 在内存里托管应用，Testcontainers 用 Docker 提供真实基础设施。下面例子用 Postgres，但 Redis、消息代理或其他切片依赖的东西都一样。

共享夹具给整个测试类启动一次：

```csharp
public class ApiFixture : WebApplicationFactory<Program>, IAsyncLifetime
{
    private readonly PostgreSqlContainer _db = new PostgreSqlBuilder()
        .WithImage("postgres:17-alpine")
        .Build();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseSetting("ConnectionStrings:Database",
            _db.GetConnectionString());

        // 只 fake 你不拥有的东西（支付网关、邮件服务）
        builder.ConfigureTestServices(services =>
            services.AddSingleton<IEmailSender, FakeEmailSender>());
    }

    public async Task InitializeAsync()
    {
        await _db.StartAsync();

        using var scope = Services.CreateScope();
        await scope.ServiceProvider
            .GetRequiredService<AppDbContext>()
            .Database.MigrateAsync();
    }

    public new Task DisposeAsync() => _db.DisposeAsync().AsTask();
}
```

切片测试读起来像是在描述功能本身：

```csharp
public class CreateShipmentTests(ApiFixture api)
    : IClassFixture<ApiFixture>
{
    [Fact]
    public async Task Creates_shipment_and_persists_it()
    {
        var client = api.CreateClient();
        var orderId = Guid.NewGuid();

        var response = await client.PostAsJsonAsync("/shipments", new
        {
            OrderId = orderId,
            Address = "123 Main Street"
        });

        response.StatusCode.Should().Be(HttpStatusCode.Created);

        // 用新的 scope 读取，看到的是真正持久化的数据，
        // 不是 EF Core change tracker 里还在内存中的东西。
        using var scope = api.Services.CreateScope();
        var db = scope.ServiceProvider
            .GetRequiredService<AppDbContext>();
        var shipment = await db.Shipments
            .SingleAsync(s => s.OrderId == orderId);
        shipment.Status.Should().Be(ShipmentStatus.Pending);
    }

    [Fact]
    public async Task Rejects_a_shipment_without_an_address()
    {
        var client = api.CreateClient();
        var orderId = Guid.NewGuid();

        var response = await client.PostAsJsonAsync("/shipments",
            new { OrderId = orderId, Address = "" });

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);

        // 400 只是契约的一半；确认数据确实没落库。
        using var scope = api.Services.CreateScope();
        var db = scope.ServiceProvider
            .GetRequiredService<AppDbContext>();
        (await db.Shipments.AnyAsync(s => s.OrderId == orderId))
            .Should().BeFalse();
    }
}
```

断言里的两个细节值得留意。一是用**新的 scope** 去读，保证你看到的是真正持久化的数据，而不是 EF Core change tracker 还没刷盘的东西。二是按你发出去的 `OrderId` 过滤，而不是直接拿"库里的唯一一条记录"——这样即使未来有其他测试也在写同一个表，断言仍然站得住。

注意测试根本不知道切片内部用了 MediatR 还是原生端点，EF Core 还是 Dapper，一个文件还是三个文件。这种无知就是收益——**你重构切片里的任何东西，测试一行不用改。** 跟实现耦合的测试惩罚重构；跟行为耦合的测试成全重构。

关于速度：容器和 host 是每个测试类启动一次，不是每个测试。这套东西在我的机器上跑完只要几秒。Testcontainers 的复用技巧能让它持续保持这个速度。

数据库是共享的，要说清楚：同一个测试类里的每个测试都写同一个 Postgres，状态会残留。按 `OrderId` 过滤能让单条断言保持诚实，但凡是数记录条数或检查排序的测试都需要干净开局。在夹具上加一个小 helper 就行：

```csharp
public async Task ResetAsync()
{
    using var scope = Services.CreateScope();
    var db = scope.ServiceProvider
        .GetRequiredService<AppDbContext>();

    await db.Shipments.ExecuteDeleteAsync();
}
```

然后每个测试开头调一下。xUnit 按顺序跑同一个类里的测试，所以开头重置就能保证每次都是从已知状态起步：

```csharp
[Fact]
public async Task Creates_shipment_and_persists_it()
{
    await api.ResetAsync();
    // ...
}
```

## 单元测试仍然有它的位置

大多数切片很薄：验证、加载、变更、保存。切片测试能完整覆盖这些，再用 mock 去单元测试一个薄薄的 handler 只是在重复描述实现。

但有些切片里确实有真正的逻辑：定价规则、状态机、围绕业务日历的日期计算。遇到这种情况，不要走 HTTP 去测逻辑。把它抽到 domain 里——实体的一个方法、一个 domain service、一个普通类——在那里用单元测试穷举所有边界情况，没有任何基础设施。

边界很清楚：

- **切片测试**证明功能端到端能用：路由、验证、持久化、正常路径和重要的异常路径。
- **单元测试**用来锤那些有意思的领域逻辑，覆盖每一种边缘情况，纳秒级速度。

一个切片里没有复杂逻辑，它就不需要单元测试。

## 别让切片互相长到一起

还有一个常见退化模式：测试全绿、功能正常，半年后发现每个切片都悄悄引用了另外三个切片。切片的独立性是 VSA 值钱的地方，把它也纳入测试，用架构测试：

```csharp
[Fact]
public void Slices_should_not_reference_other_slices()
{
    var result = Types.InAssembly(typeof(Program).Assembly)
        .That().ResideInNamespace("Features.Shipments")
        .ShouldNot().HaveDependencyOn("Features.Invoicing")
        .GetResult();

    result.IsSuccessful.Should().BeTrue();
}
```

写起来不费事，但它把"不要耦合切片"从 code review 里的一句念叨变成了编译不过的硬约束。

## 小结

把测试单元选对之后，VSA 的测试就不再让人困惑：

1. **把切片当成功能来测**：真实 HTTP 进去，真实数据库出来，用 `WebApplicationFactory` + Testcontainers。
2. **只 fake 你不拥有的东西**。数据库是你的，测试里用的就是真实数据库。
3. **抽出来的领域逻辑用单元测试**，不要单元测试薄薄的 handler。
4. **架构测试**保证切片在代码量增长的过程中保持独立。

最终你拿到的是一套描述功能的测试，而不是描述分层的测试。它抗重构，而且抓到的 bug 就是会进生产的那些。

## 参考

- [原文链接](https://milanjovanovic.tech/blog/how-to-test-vertical-slice-architecture)
