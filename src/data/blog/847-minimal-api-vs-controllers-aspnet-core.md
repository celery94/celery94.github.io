---
pubDatetime: 2026-06-03T13:54:03+08:00
title: "Minimal API vs Controller：ASP.NET Core 中两种 API 风格怎么选"
description: "Minimal API 和 Controller 是 ASP.NET Core 中两种主流 API 构建方式。本文从语法、DI、过滤器、测试、规模化组织和 .NET 10 最新改进等维度做全面对比，给出一份实用的决策矩阵，帮你根据团队和项目实际情况作出选择。"
tags: ["ASP.NET Core", "Minimal API", "Web API", "C#", ".NET"]
slug: "minimal-api-vs-controllers-aspnet-core"
ogImage: "../../assets/847/01-cover.png"
source: "https://www.devleader.ca/2026/06/02/minimal-api-vs-controllers-in-aspnet-core-which-should-you-use"
---

在 ASP.NET Core 里新建一个 API 项目，第一个要面对的选择往往就是：用 Minimal API 还是 Controller？这个问题没有一刀切的答案，它跟你的团队规模、领域复杂度、以及你对代码"仪式感"的容忍度都有关系。

Controller 从 ASP.NET MVC 时代一路走到现在，积累了成熟的约定和工具链。Minimal API 则是 .NET 6 引入的轻量方案，用更函数式的语法剥掉了一堆样板代码。到了 .NET 10，Minimal API 的成熟度已经很高，功能差距大幅缩小——两种方式都不存在绝对的"谁更好"。

这篇文章把两种方式放在一起拆解，给出可对比的代码示例，帮你理清各自的优势和短板。


## 什么是最简 API

最简 API 让你直接在 `Program.cs`（或者任意你委托出去的方法）里用 `MapGet`、`MapPost`、`MapPut`、`MapDelete` 这类扩展方法定义 HTTP 端点。处理器可以是 lambda，也可以是命名方法组，参数会自动从路由、查询字符串、请求体或服务容器中绑定。没有 Controller 类，没有基类继承，也没有属性标记那一套。

路由分组（`RouteGroupBuilder`）让你把相关端点组织在同一个前缀下，同时统一施加中间件或过滤器。过滤器在 Minimal API 中走的是 `IEndpointFilter` 接口——一个单管道式的钩子，比 Controller 完整的过滤器管道简洁，但同时也意味着功能范围更窄。

```csharp
// Minimal API CRUD — .NET 10
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddScoped<IProductService, ProductService>();
var app = builder.Build();

var products = app.MapGroup("/api/products").WithTags("Products");
products.MapGet("/", async (IProductService svc) =>
    Results.Ok(await svc.GetAllAsync()));
products.MapGet("/{id:int}", async (int id, IProductService svc) =>
    await svc.GetByIdAsync(id) is { } product
        ? Results.Ok(product) : Results.NotFound());
products.MapPost("/", async (CreateProductRequest request, IProductService svc) =>
{
    var created = await svc.CreateAsync(request);
    return Results.CreatedAtRoute("GetProduct", new { id = created.Id }, created);
});
products.MapPut("/{id:int}", async (int id, UpdateProductRequest request, IProductService svc) =>
{
    var updated = await svc.UpdateAsync(id, request);
    return updated is null ? Results.NotFound() : Results.Ok(updated);
});
products.MapDelete("/{id:int}", async (int id, IProductService svc) =>
{
    var deleted = await svc.DeleteAsync(id);
    return deleted ? Results.NoContent() : Results.NotFound();
});
app.Run();
```

代码很紧凑。处理器参数由框架自动注入——服务从 DI 容器来，路由值按名称绑定，请求体从 JSON 反序列化。没有类结构上的累赘。

Minimal API 的魅力在于清晰和速度。对于只暴露少量端点的微服务，或者偏好函数式风格的团队，这种写法天然顺手，而且不会碍事。

## 什么是控制器

控制器是 ASP.NET Core 的传统方式，继承自 ASP.NET MVC。你创建一个继承 `ControllerBase` 的类，打上 `[ApiController]` 和 `[Route]` 属性，然后定义通过 `[HttpGet]`、`[HttpPost]` 等方法映射到 HTTP 动词的 Action 方法。`[ApiController]` 属性会激活一套约定：自动模型验证、对错误输入自动返回 400、以及绑定源推断。

控制器强制了一种以类为中心的结构，天然把相关端点组织在一起。这在有几十个端点的大项目里价值很大——每个端点知道自己该放在哪里。完整的过滤器管道（`IActionFilter`、`IExceptionFilter`、`IResourceFilter`、`IAuthorizationFilter`）让你对请求生命周期有精细的控制，这一点 Minimal API 目前无法完全复刻。

```csharp
// Controller CRUD — .NET 10
[ApiController]
[Route("api/[controller]")]
public sealed class ProductsController : ControllerBase
{
    private readonly IProductService _productService;

    public ProductsController(IProductService productService)
    {
        _productService = productService;
    }

    [HttpGet]
    public async Task<IActionResult> GetAll()
        => Ok(await _productService.GetAllAsync());

    [HttpGet("{id:int}", Name = "GetProduct")]
    public async Task<IActionResult> GetById(int id)
    {
        var product = await _productService.GetByIdAsync(id);
        return product is null ? NotFound() : Ok(product);
    }

    [HttpPost]
    public async Task<IActionResult> Create(CreateProductRequest request)
    {
        var created = await _productService.CreateAsync(request);
        return CreatedAtRoute("GetProduct", new { id = created.Id }, created);
    }

    [HttpPut("{id:int}")]
    public async Task<IActionResult> Update(int id, UpdateProductRequest request)
    {
        var updated = await _productService.UpdateAsync(id, request);
        return updated is null ? NotFound() : Ok(updated);
    }

    [HttpDelete("{id:int}")]
    public async Task<IActionResult> Delete(int id)
    {
        var deleted = await _productService.DeleteAsync(id);
        return deleted ? NoContent() : NotFound();
    }
}
```

逻辑上几乎一模一样。Controller 版本更啰嗦，但结构很明确——一个完全没接触过这个代码库的开发者也能立刻看懂。

## 多维度对比

两种方式在功能上是等价的，但在几个关键维度上有明显差异：

- **语法复杂度**：Minimal API 更低，lambda 和方法组即可；Controller 更高，要走类继承和属性标记
- **依赖注入**：Minimal API 用参数注入或 `RequestServices`；Controller 用构造器注入
- **过滤器支持**：Minimal API 走 `IEndpointFilter` 单管道；Controller 有完整的 Action / Exception / Resource / Authorization 过滤器管道
- **测试便利性**：Minimal API 用 `WebApplicationFactory` 干净利落；Controller 也可以用同一套工厂，还能单独对控制器做单元测试
- **OpenAPI 生成**：Minimal API 在 .NET 9+ 内置 `Microsoft.AspNetCore.OpenApi` 一等支持；Controller 主要靠 Swashbuckle / NSwag
- **规模化组织**：Minimal API 靠纪律和路由分组；Controller 天然被类结构约束
- **性能**：Minimal API 启动开销略低，AOT 友好；Controller 有少量反射开销
- **学习曲线**：Minimal API 对函数式开发者友好；Controller 对面向对象开发者友好

从表上看 Controller 似乎能力更强，在某些具体领域确实如此。但对大多数 API 来说，这些额外能力根本用不到，Minimal API 的简洁反而更实在。性能差异也不应该是首要考虑因素——应该从结构和可维护性出发做判断。

## 依赖注入：两种都行，略有不同

依赖注入在两种方式中都是一等公民。Controller 通过构造器注入接收服务，这是标准模式：DI 容器在每个请求上构建 Controller 实例，自动注入已注册的服务。

Minimal API 主要在处理器中直接用参数注入。当逻辑迁移到专门的服务类或处理器类时，标准的构造器注入同样适用。参数注入的方式其实更显式——你直接在签名里看到某个端点依赖什么。

```csharp
// Controller — 构造器注入
app.MapGet("/api/orders/{id:int}", async (
    int id,
    IOrderService orderService,
    ILogger<Program> logger) =>
{
    logger.LogInformation("Fetching order {OrderId}", id);
    var order = await orderService.GetAsync(id);
    return order is null ? Results.NotFound() : Results.Ok(order);
});
```

两种都能用。Minimal API 的参数注入在一个处理器需要四五个服务时会显得臃肿。这时候你可以考虑用基于类的方式，或者重构为指向服务类的方法组——保留 Minimal API 语法，但把实现从 `Program.cs` 搬出去。

## 测试体验

测试方面，Minimal API 用起来略简单一些。`WebApplicationFactory<TProgram>` 两种方式都适用，让你在进程内启动完整应用做集成测试。你对端点发出真实 HTTP 调用，不需要运行服务器，响应里包含完整的状态码和头信息。

Controller 还有一个额外优势：你可以写单元测试直接实例化 Controller、mock 它的依赖、然后像调用普通 C# 方法一样调用 Action。这对不经过完整 HTTP 管道、快速验证复杂逻辑的单元测试来说更快。Minimal API 的 lambda 处理器没有这个选项——你要么走 `WebApplicationFactory`，要么把逻辑抽到服务类里。

实际差距很小。通过 `WebApplicationFactory` 做集成测试是两种风格下的推荐做法，测试代码看起来完全一样，不管被测的是 Minimal API 还是 Controller。

## 过滤器：真正的差异点

这是 Controller 明显更强的地方。ASP.NET Core 的 Controller 过滤器管道包含五种类型：Authorization 过滤器、Resource 过滤器、Action 过滤器、Exception 过滤器和 Result 过滤器。每一种在请求生命周期的不同节点运行，可以短路管道。这给你非常精细的控制力，而且文档完备、团队普遍熟悉。

Minimal API 只有 `IEndpointFilter`，它在处理器执行前后提供一个钩子。你可以链多个过滤器，但它们都在管道同一个位置运行——处理器执行前和完成后。你无法用 `IEndpointFilter` 精确复刻 Resource 过滤器或 Exception 过滤器的语义。

对大多数 API 来说，`IEndpointFilter` 已经够用。日志、验证、响应塑形都能通过它完成。如果你的团队重度依赖自定义 Action 过滤器或 Exception 过滤器做横切关注点，Controller 会让你觉得更完整。

## 规模化组织代码

这是最诚实的权衡。只要你组织得用心，Minimal API 在中小型 API 上扩展得很漂亮。路由分组让你把相关端点聚在一起，统一施加授权策略和公用中间件。如果把端点按功能拆成扩展方法——`ProductEndpoints.cs`、`OrderEndpoints.cs`，每个文件注册自己的路由分组——代码会保持干净。

没有这份纪律的话，`Program.cs` 就会变成一堵 lambda 函数墙。这在真实项目中确实发生过。Controller 从结构上规避了这个问题：每个 Controller 文件天然有边界，类级属性作用于所有 Action，框架强制了一致的形态。

如果你在思考更大规模的组织方式，模块化单体（Modular Monolith）的思路在这里同样适用——无论你选 Minimal API 还是 Controller，真正的收益来自按功能而非技术层组织代码。

## .NET 10 的 Minimal API 改进

.NET 10 延续了从 .NET 8 开始对 Minimal API 的持续投入。OpenAPI 支持通过内置的 `Microsoft.AspNetCore.OpenApi` 包变成一等公民（.NET 9 首次引入内置支持，.NET 10 继续增强），`TypedResults` 让返回类型推断可靠且准确。过滤器的文档更好，行为更一致。

通过 `TypedResults.Problem` 和 `TypedResults.ValidationProblem` 提供的问题详情支持，让 Minimal API 在自动 400 处理上和 Controller 的 `[ApiController]` 拉平。Native AOT 兼容性大幅改善，Minimal API 现在是对启动时间敏感的、高性能力求裁剪的部署场景的正当选择。

规律很清楚：每个版本都在缩小 Minimal API 和 Controller 之间的功能差距。.NET 10 已经把差距显著缩小，过去一些避免在新项目中使用 Minimal API 的理由不再成立——但团队熟悉度、项目规模和组织的既有约定仍然重要。

## 怎么选：一份决策矩阵

两种方式都不是普适的最优解。更好的选择往往取决于项目上下文、团队经验和优先级。

**选 Minimal API 的场景：**

- 在构建一个功能面有限、专注的微服务
- 团队偏好函数式编程风格，不喜欢过多样板代码
- 需要 AOT 编译来优化启动时间或部署体积
- 在做原型开发或内部 API，对结构要求不高
- 想避免类继承层次和属性堆叠带来的认知负担

**选 Controller 的场景：**

- 团队规模大，成员 .NET 经验参差不齐——类结构对多数开发者来说是熟悉的模式
- 领域复杂度高，需要完整的过滤器管道处理横切关注点
- 在已有项目中工作，而且项目已经在用 Controller
- 团队遵循强面向对象约定，偏好显式的类架构
- 需要 `[ApiController]` 的整套行为，不想自己重新实现

容易被忽略的一点：你可以在同一个应用里混用两种方式。一个 ASP.NET Core 应用可以同时有 Controller 端点和 Minimal API 端点，互不干扰。这让你在老项目里为新功能用 Minimal API，同时保留已有的 Controller——一种在棕地项目里逐步引入绿地功能的做法。

## 不止是 API 风格的选择

Minimal API 还是 Controller，本质上不是对错问题，而是适配问题。Minimal API 提供简洁、低开销和函数式风格。Controller 提供结构、更丰富的过滤器管道和大型团队依赖的约定。在 .NET 10 中，两者都足够成熟、有足够好的支持，都能构建生产级 API。

如果你今天开一个新项目，先想清楚团队规模、领域复杂度和你是更看重简洁还是显式结构。拿不准的时候，Minimal API 是专注型服务的合理默认选择，而 Controller 对复杂的、多人维护的应用来说仍然是稳妥之选。

## 常见问题

### 能在同一个项目里混用 Minimal API 和 Controller 吗？

可以，这是完全支持的配置。ASP.NET Core 路由对两种风格一视同仁，`AddControllers()` 和 Minimal API 端点注册可以并存，互不冲突。

这在迁移场景里尤其有用。你可以为新端点引入 Minimal API，同时不动已有的 Controller 端点。后续可以逐步把 Controller 端点迁到 Minimal API——也可以就让混合状态保持下去，如果团队用着顺手的话。

### Minimal API 比 Controller 性能更好吗？

性能差异确实存在，但对多数负载来说很小。Minimal API 启动开销略低，因为它跳过了 Controller 发现过程中的反射逻辑。在 AOT 编译场景下，Minimal API 优势更明显——Controller 管道对反射的依赖在裁剪时更难处理。

对于稳态吞吐量——应用预热后的每秒请求数——大多数基准测试中差异可以忽略。两种方式都快到瓶颈几乎总在数据库或外部服务上，而不是框架路由开销。

### Minimal API 支持像 [ApiController] 那样的模型验证吗？

不自动支持。Controller 的 `[ApiController]` 属性提供自动模型验证：如果 `ModelState.IsValid` 为 false，框架在 Action 运行前就返回 400。Minimal API 没有这个内置行为。

你可以通过 `IEndpointFilter` 和 FluentValidation 这样的验证库来复刻。.NET 10 也改进了 Minimal API 的内置验证辅助功能。虽然不如 Controller 那样全自动，但不需要太多额外代码就能实现。

### 怎么给 Minimal API 加日志？

加日志的方式一样——把 `ILogger<T>` 或 `ILogger` 作为参数注入端点处理器，或者注入到端点委托的服务类中。`ILogger` 抽象不关心自己是在 Controller 里还是 lambda 处理器里被消费。

如果你在搭结构化日志，配置流程和用 Minimal API 还是 Controller 完全无关——日志中间件位于应用级别，不是端点级别。

### 应该用路由分组还是独立文件来组织 Minimal API 端点？

两个都用。路由分组提供前缀和共享配置——授权、限流、OpenAPI 标签。独立文件提供组织结构。常见模式是每个功能领域创建一个扩展方法，接收 `RouteGroupBuilder` 或 `WebApplication` 并注册端点，然后在 `Program.cs` 里调用每个扩展方法。

这种做法让 `Program.cs` 保持整洁，每个功能有自己的文件，不增加任何框架复杂度。对中型 API 扩展良好，新成员也容易导航。

## 参考

- [Minimal API vs Controllers in ASP.NET Core: Which Should You Use? — Dev Leader](https://www.devleader.ca/2026/06/02/minimal-api-vs-controllers-in-aspnet-core-which-should-you-use)
