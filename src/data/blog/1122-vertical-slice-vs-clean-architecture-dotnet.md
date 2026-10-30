---
pubDatetime: 2026-10-30T09:30:00+08:00
title: ".NET 10 架构选型：整洁架构还是垂直切片"
description: "用同一个商品 API 搭出整洁架构、垂直切片和混合方案三套骨架，数清加一个接口到底要动几个文件、跨几个项目，并给出混合方案的项目划分、共享代码规则、架构测试写法与选型判断。"
tags: ["Clean Architecture", "Vertical Slice", ".NET", "ASP.NET Core", "架构"]
slug: "vertical-slice-vs-clean-architecture-dotnet"
ogImage: "../../assets/1122/01-cover.jpg"
source: "https://codewithmukesh.com/blog/clean-architecture-vs-vertical-slice-architecture/"
---

加一个「按 ID 查商品」的接口，整洁架构要你动 5 个文件、跨 3 个项目：查询对象、处理器、仓储接口、仓储实现，再加一行端点注册。换成纯垂直切片只要 2 个文件，代价是「价格必须大于零」这条规则会在 CreateProduct、ChangeProductPrice 以及之后每一个碰价格的处理器里各写一遍。

Mukesh Murugan 在同一个商品 API 上分别搭了这三种骨架，把每个方案要碰的文件数和项目数都数了出来。他的答案是两边都不取纯粹形态：保留 Domain 和 Infrastructure 项目，砍掉 Application 项目，把端点、请求、验证器、处理器塞进 Api 项目的一个 feature 文件夹。加接口通常只碰 1 个文件，业务规则仍然只写在一个地方。这套布局的前提是 API 里有真实业务规则要守；纯 CRUD、规则少的小项目，单项目的纯切片就够。

## 分组依据不同，守边界的东西也不同

整洁架构按技术层切：Domain、Application、Infrastructure、Presentation。依赖只能朝内指，业务规则在 Domain，Application 里的处理器只认接口，实现放在 Infrastructure。这套分层 Robert C. Martin 在 2012 年写过，微软的 Web 应用架构指南对 ASP.NET Core 的说法与此一致。

垂直切片按用例切：一个功能需要的端点、请求、处理器、响应放在同一个文件夹，甚至同一个文件里。

|                      | 整洁架构                 | 垂直切片              |
| -------------------- | ------------------------ | --------------------- |
| 代码按什么分组       | 技术层                   | 功能 / 用例           |
| 边界靠什么守         | 项目引用，编译器会拦住   | 团队纪律              |
| 加一个功能碰几个项目 | 3                        | 1                     |
| 业务规则住哪         | Domain 项目              | 切片作者放哪就在哪    |
| 擅长                 | 复杂领域、长期演进的系统 | CRUD 重、迭代快的产品 |
| 主要风险             | 仪式感和间接层           | 规则重复或散落在各处  |

「边界靠什么守」那一行最容易被跳过。项目引用是编译器帮你执行的约束，谁写下 `Application → Infrastructure` 的引用，构建就直接失败；垂直切片对「一个功能不能乱碰另一个功能」的约束，只能靠人和代码评审守。反过来，编译器也管不了「价格校验该写在实体还是处理器里」，这件事在哪套架构里都得靠判断。

## 同一个商品 API，三种项目骨架

三个方案共用同一套前提：.NET 10 SDK、跑在 `localhost:5432` 的 PostgreSQL（连接串写在 `appsettings.json`），以及对 Minimal API 和 EF Core 的基本熟悉。示例仓库里是三个独立解决方案，分别叫 CleanArchitecture、VerticalSlice、Hybrid。

原文写作时是 SDK 10.0.401、EF Core 10.0.12、FluentValidation 12.1.1；撰写这篇时 NuGet 上 EF Core 10 已到 10.0.14、FluentValidation 到 12.2.0、.NET SDK 到 10.0.403。这些补丁版本不影响本文的结构判断。

整洁架构是四个项目，依赖方向照惯例：

```
CleanArchitecture/
  CleanArchitecture.Domain/          # Product 实体
  CleanArchitecture.Application/     # 命令、查询、处理器、IProductRepository
  CleanArchitecture.Infrastructure/  # AppDbContext、ProductRepository
  CleanArchitecture.Api/             # ProductEndpoints.cs、Program.cs
```

Application 里只有 Domain 的引用，处理器想直接摸 `DbContext` 会编译不过，这是这套结构最实在的收益。代价是一次请求要跨五个文件才读得完：端点、命令、处理器、接口，最后再跳到 Infrastructure 看仓储实现。

纯垂直切片是一个项目，每个功能一个文件：

```
VerticalSlice/
  Features/Products/CreateProduct.cs   # 请求、响应、处理器、端点映射都在这里
```

读一个功能只开一个文件，没有只有一个实现的仓储接口，也不用来回切项目。问题出在 `Product` 上：属性全是 `public set`，实体自己没有任何行为，「价格必须大于零」这类规则没有地方可放，只能复制进每个碰价格的处理器。

## 加一个接口，成本差在最后两行

新增一个需要新数据访问方法的接口，比如「按 ID 查商品」，要创建或修改多少东西，作者数了一遍：

|                      | 整洁架构                                        | 垂直切片                  | 混合                    |
| -------------------- | ----------------------------------------------- | ------------------------- | ----------------------- |
| 解决方案里的项目数   | 4                                               | 1                         | 3                       |
| 示例里的 .cs 文件数  | 16                                              | 8                         | 17                      |
| 加一个接口要动的文件 | 5（查询、处理器、仓储接口、仓储实现、端点注册） | 2（功能文件、Program.cs） | 1（功能文件）           |
| 碰到的项目           | 3                                               | 1                         | 1（需要新业务规则时 2） |

混合方案的文件总数比整洁架构还多一个，多出来的部分是 Shared 里一次性的基础设施代码。日常成本落在表格最后两行：「加一个接口要动的文件」和「碰到的项目」。

作者还记了时间：同一种 CRUD 实体，整洁架构版本花了约 25 分钟，垂直切片版本约 8 分钟。这个对比要打个折：垂直切片那版直接跳过了业务规则，25 分钟和 8 分钟的差距里有一截来自少写规则，结构本身省下的没那么多。混合方案保住了大部分速度，同时把规则放回了实体。

只看文件数会漏掉更贵的成本。整洁架构的 5 个文件分布在 3 个项目里，改一个接口的输入输出要在项目之间跳，这种切换成本不会出现在任何统计里；垂直切片的 1 个文件省了跳转，但规则复制的代价要等到第二个、第三个处理器出现才显形，形式是一堆分散的 `if`。

## 砍掉 Application 项目的理由

端点和处理器已经住进同一个功能文件之后，Application 项目只剩两种结局。一种是变成纯转发的空壳，处理器除了调下一层什么都不做；另一种是把 feature 文件夹搬进 Application，于是它开始引用 ASP.NET Core，而依赖规则本来就是设来防这件事的。

所以混合方案干脆让 feature 文件夹留在 Api 项目里，处理器直接注入 `AppDbContext`。这个选择丢掉了「处理器碰不到 EF Core」的编译期保护，改用架构测试来补。

什么情况下该把 Application 项目请回来？当不止一个应用跑同一批用例时。比如 API 和后台 worker 都要「下单」，这段逻辑就得放在两边都能引用的项目里；Api 项目里的 feature 文件做不到这件事。

## Domain 里留下的是能自己守住的规则

Domain 项目是整洁架构里值得原样保留的部分：不引任何 NuGet 包，不引任何项目，规则长在实体上。

```csharp
public sealed class Product
{
    private Product() { }

    public Guid Id { get; private set; }
    public string Name { get; private set; } = string.Empty;
    public string Description { get; private set; } = string.Empty;
    public decimal Price { get; private set; }
    public int Stock { get; private set; }
    public DateTime CreatedAt { get; private set; }
    public uint Version { get; private set; }

    public static Product Create(string name, string description, decimal price, int stock)
    {
        if (string.IsNullOrWhiteSpace(name))
            throw new DomainException("Name is required.");

        if (price <= 0)
            throw new DomainException("Price must be greater than zero.");

        if (stock < 0)
            throw new DomainException("Stock cannot be negative.");

        return new Product
        {
            Id = Guid.CreateVersion7(),
            Name = name,
            Description = description,
            Price = price,
            Stock = stock,
            CreatedAt = DateTime.UtcNow
        };
    }

    public void RemoveStock(int quantity)
    {
        if (quantity <= 0)
            throw new DomainException("Quantity must be greater than zero.");

        if (quantity > Stock)
            throw new DomainException($"Cannot remove {quantity} items. Only {Stock} left in stock.");

        Stock -= quantity;
    }
}
```

setter 是私有的，任何处理器都没法写 `product.Price = -5`。所有改库存的路径都得过 `RemoveStock`，这条规则于是只有一个落点。

`Version` 是并发令牌。没有它，两个请求同时读到同一个库存值，都能通过检查，后保存的覆盖先保存的。作者记过一次运行：库存 3 的商品同时收到 6 个各扣 1 件的请求，有 4 个成功返回。这个属性用 `IsRowVersion()` 配置，Npgsql 把它映射到 PostgreSQL 的 `xmin` 系统列；行被改过之后 EF Core 抛 `DbUpdateConcurrencyException`，Shared 里的异常处理器把它转成 409，客户端可以重试。

## 一个功能切片里有什么

混合方案的 CreateProduct.cs，请求、响应、验证器、端点、处理器全在一个文件：

```csharp
public static class CreateProduct
{
    public sealed record Request(string Name, string Description, decimal Price, int Stock);

    public sealed record Response(Guid Id, string Name, string Description, decimal Price, int Stock, DateTime CreatedAt);

    internal sealed class Validator : AbstractValidator<Request>
    {
        public Validator()
        {
            RuleFor(x => x.Name).NotEmpty().MaximumLength(200);
            RuleFor(x => x.Description).MaximumLength(1000);
        }
    }

    internal sealed class Endpoint : IEndpoint
    {
        public void MapEndpoint(IEndpointRouteBuilder app) =>
            app.MapPost("/api/products", Handle)
                .AddEndpointFilter<ValidationFilter<Request>>()
                .ProducesValidationProblem()
                .WithName(nameof(CreateProduct))
                .WithTags("Products");
    }

    internal static async Task<Created<Response>> Handle(Request request, AppDbContext db, CancellationToken cancellationToken)
    {
        var product = Product.Create(request.Name, request.Description, request.Price, request.Stock);

        db.Products.Add(product);
        await db.SaveChangesAsync(cancellationToken);

        var response = new Response(product.Id, product.Name, product.Description, product.Price, product.Stock, product.CreatedAt);
        return TypedResults.Created($"/api/products/{product.Id}", response);
    }
}
```

处理器调 `Product.Create`，不自己给属性赋值。这一行是混合方案和纯垂直切片的分水岭：规则回到实体，切片只负责编排。

没有 MediatR。`Handle` 是静态方法，直接传给 `MapPost`，依赖注入和模型绑定 Minimal API 已经做了。真需要管道行为（日志、事务）的时候，加一个小分发器就够，不必为此引入完整的 mediator。验证器接在 `ValidationFilter<TRequest>` 上，这是个通用端点过滤器，校验失败时返回 400 和验证错误详情。

## 切片靠一个 IEndpoint 接口注册

每个切片带一个嵌套的 `Endpoint` 类，实现 Shared 里这个小接口：

```csharp
public interface IEndpoint
{
    void MapEndpoint(IEndpointRouteBuilder app);
}
```

启动时 `AddEndpoints` 扫程序集，把所有 `IEndpoint` 实现注册进容器，`MapEndpoints` 逐个调 `MapEndpoint`。这就是「加功能只碰一个文件」成立的原因：不用回头改 Program.cs，也不用维护一张集中的路由表。

## 输入校验和业务规则的分界线

混合方案里有两种检查，分开才有效。

输入校验管请求的形状：必填、最大长度。由切片的验证器做，跑在处理器之前；空名字返回 400，响应体里的 `title` 是 `One or more validation errors occurred.`。

业务规则管业务允许什么：价格大于零、库存够扣。这些长在实体上。

价格填 0 能通过输入校验，然后被领域规则挡下来。Shared 里的 `DomainExceptionHandler` 把它转成 Problem Details：

```json
{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.1",
  "title": "Business rule violated",
  "status": 400,
  "detail": "Price must be greater than zero."
}
```

作者提醒过一句：示例用异常表达业务规则，只是为了把代码压短；违反业务规则是预期内的结果，用 Result 返回值比抛异常更合适。往下再追一层，异常会把正常分支和真实故障混进同一条日志，处理器也没法用类型告诉调用方「这里可能失败」。示例可以这么写，生产代码建议换掉。

## Shared 文件夹该放什么

多数讲垂直切片的文章到这里会说「共享代码放 Shared」，然后没了。没有规则约束，这个文件夹会慢慢长成新的一层 Services，应用又变回分层结构，只是这次没人计划过。

作者给了五条规则：

1. 业务规则永远不进 Shared。带 `if` 判断业务允许什么的代码，属于 Domain 实体。
2. Shared 只放技术代码。示例里是 `IEndpoint`、端点发现、`ValidationFilter`、两个异常处理器和一个分页辅助类。
3. 功能之间不互相调用。两个切片的查询很像就复制，等到第三个切片也需要时再提取。
4. 不要有 Services 文件夹。Shared 里出现 `ProductService`，通常意味着功能文件夹正在退回分层。
5. 能用测试守的都用测试守。代码评审会漏，CI 里挂掉的测试不会。

第 3 条最容易吵起来。两个切片各有一条五行的相似查询，让它们各自演化是可控的；一条查询被六个功能共用，改它就得同时验证六个功能。作者的选择是把修改半径压小，代价是重复。这个取舍在功能数少、变化快的时候成立，等共享查询真的稳定下来，再提取也不迟。

## 边界靠架构测试守

整洁架构用项目引用守边界。混合方案只有 Domain 和 Infrastructure 有这层保护，Api 项目内部没有任何东西阻止 `Features/Orders` 引用 `Features/Products`。

补上这一层的是架构测试。示例里 4 个测试，NetArchTest 1.3.2 + xUnit v3，分别断言：Domain 不依赖任何其他项目和 EF Core / ASP.NET Core；Infrastructure 不依赖 Api；Shared 不依赖任何 feature；一个 feature 文件夹不依赖另一个。

大致的形状是这样，这段是按 NetArchTest 常见写法补的示意，不是原文代码：

```csharp
var result = Types.InAssembly(typeof(Program).Assembly)
    .That().ResideInNamespace("Hybrid.Api.Features.Products")
    .ShouldNot().HaveDependencyOn("Hybrid.Api.Features.Orders")
    .GetResult();

Assert.True(result.IsSuccessful, string.Join(", ", result.FailingTypeNames ?? []));
```

作者验证过这条规则真的会响：临时加了一个 `Features/Orders/PlaceOrder.cs`，里面引用 `GetProductById.Response`。项目照样编译通过，测试跑挂了：

```
Hybrid.ArchitectureTests.ArchitectureTests.Features_Should_Not_Depend_On_Other_Features [FAIL]
  Violations: Hybrid.Api.Features.Orders.PlaceOrder
Hybrid.ArchitectureTests  Total: 4, Errors: 0, Failed: 1, Skipped: 0, Not Run: 0
```

这套测试有两个明确漏网的地方。一是 feature 测试比的是 `Features.Products` 和 `Features.Orders` 这种文件夹级别，同一个文件夹里两个切片互相引用它看不出来；二是没有测试能判断 Shared 里的某个类是不是藏了业务规则。作者把这两种代码都塞进示例试过，4 个测试全部通过。这两块只能留给代码评审。

## 这套方案什么时候不够用

作者说他还没撞到这套布局的上限，所以下面这些是观察信号，不是结论。

Shared 的文件数超过最大的 feature 文件夹，说明业务逻辑大概已经渗进去了。两个应用需要同一批用例时，Application 项目就该回来。

团队开始互相踩，下一步是模块化单体：每个模块有自己的 Domain、Infrastructure 和 feature 文件夹。作者的 fullstackhero 开源项目 2021 年起步时是整洁架构，现在是跑在 .NET 10 上的模块化单体，每个模块内部用垂直切片。

## 五类项目，各自选哪套

| 你的情况                                | 选什么                                     |
| --------------------------------------- | ------------------------------------------ |
| 小型 CRUD、规则少、1–3 个人             | 纯垂直切片，单项目                         |
| 有真实业务规则的产品 API                | 混合：Domain + Infrastructure + 功能文件夹 |
| API 和 worker / gRPC 服务共用同一批用例 | 整洁架构，保留 Application 项目            |
| 复杂领域、大量不变量、长期系统、大团队  | 整洁架构，或模块化单体里的混合模块         |
| 多个团队各管一块业务                    | 模块化单体，每个模块内部用切片             |

## 先改目录，还是先补测试

原文的默认答案是三个项目加功能文件夹，并且第一天就把架构测试加上。在有人破坏规则之前把规则钉住，比事后补便宜得多。

先把 Api 项目里按层分的文件夹整体换成一个功能一个文件。这一步只改文件位置，不动行为，风险低；加一个接口时开一个文件夹就够，不用再翻三个项目。测试放在第二步，因为边界测试要先有稳定的命名空间可断言。

两种情况下别急着改。一种是纯 CRUD、业务规则少、团队 1–3 人，纯垂直切片就够了，加 Domain 项目只是多一层；另一种是已经有两个应用在共用同一批用例，这时候别搬目录，先把 Application 项目留下。

该盯的信号不在目录结构上：如果 Shared 里已经开始长出一个 `ProductService`，先拆这个，再谈目录怎么分。

## 参考

- [Vertical Slice vs Clean Architecture in .NET 10 - What I Use](https://codewithmukesh.com/blog/clean-architecture-vs-vertical-slice-architecture/)
- [示例仓库：clean-architecture-vs-vertical-slice-architecture](https://github.com/codewithmukesh/dotnet-webapi-zero-to-hero-course/tree/main/modules/08-architecture-best-practices/clean-architecture-vs-vertical-slice-architecture)
- [Microsoft：Common web application architectures](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures)
- [NetArchTest](https://github.com/BenMorris/NetArchTest)
- [ASP.NET Core Minimal API filters](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/min-api-filters)
