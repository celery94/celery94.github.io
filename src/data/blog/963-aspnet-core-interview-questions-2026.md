---
pubDatetime: 2026-07-22T04:56:44+08:00
title: "ASP.NET Core 面试 30 问：2026 年真会被问到的内部原理题"
description: "30 道 ASP.NET Core 内部原理面试题，涵盖托管、中间件管道、DI 生命周期、配置与选项、过滤器、请求生命周期六大类别，每道题都附面试官想听的答案、致命错误答法和追问方向。"
tags:
  - dotnet
  - aspnetcore
  - interview-questions
  - csharp
  - middleware
  - dependency-injection
slug: "aspnet-core-interview-questions-2026"
ogImage: "../../assets/963/01-cover.png"
source: "https://codewithmukesh.com/blog/aspnet-core-interview-questions/"
---

2026 年的 ASP.NET Core 面试，几乎没有人再问"什么是中间件"这种级别的题了。面试官问的都是内部原理题：你的 CORS 头在高负载下消失了、你的 singleton 捕获了一个 `DbContext` 然后跨请求污染了数据、你的 `IOptionsSnapshot` 注入不进 BackgroundService、你的自定义中间件流量一上来就抛 `ObjectDisposedException`。这些问题考察的是你对自己每天都在用的框架到底理解到什么程度，还是只认识模板脚手架搭出来的那层皮。

这篇文章整理了 **30 道 ASP.NET Core 面试题**，按真实技术面中常见的 6 个类别组织。每道题都不是定义题，而是场景题：一个真实场景、一个面试官想听的回答、一个让你被刷掉的错误答法、以及一个面试官大概率会接着问的追问。所有内容基于 **ASP.NET Core on .NET 10**。

## 什么样的回答才算"好的内部原理回答"？

好的内部原理回答会同时说出**机制**和**后果**。不是"中间件处理请求"，而是"中间件是一条 `RequestDelegate` 链，每个节点决定是否调用下一个，顺序决定了为什么 auth 必须在 routing 之后运行"。面试官在判断你有没有真正调试过框架，而不只是用过它。

下面的 30 道题按技术面的真实节奏分成 6 个板块。

---

## 一、托管、启动与 Host（Q1-Q4）

面试通常从这里开场——不是为了刁难你，而是看你是否真的理解自己的 `Program.cs` 在干什么。

### Q1：从 `CreateBuilder` 到 `app.Run()` 之间发生了什么？

`Program.cs` 有两个泾渭分明的阶段，`builder.Build()` 是分界线。

在此之前，你在**配置服务**：`WebApplication.CreateBuilder(args)` 搭好配置、日志和 DI 容器，然后你把注册写进 `builder.Services`。`builder.Build()` 锁定容器，生成 `WebApplication`。在此之后，你在**构建请求管道**：每个 `app.UseSomething()` 追加一层中间件，`app.Run()` 启动 Kestrel 并阻塞到关机。

理解这条分界线能解释一半初学者碰到的"为什么这样不生效"的 bug：`Build()` 之后不能再注册服务，也加不了中间件。

**致命错误答法**："它只是启动 web 服务器。" —— 只有最后一行是对的，忽略了整个 DI 容器和管道都在前面装配好。

**追问**："`CreateBuilder` 默认帮你配了什么？"

### Q2：为什么在 `builder.Build()` 之后注册服务会抛异常？

因为 `Build()` 把服务集合固化成**不可变的 ServiceProvider**。`Build()` 之前，`builder.Services` 只是一个可变的 `IServiceCollection` 描述符列表；`Build()` 读取、验证，生成根 `IServiceProvider`。在容器构建之后修改注册，意味着某些消费者能看到某个服务、另一些看不到，框架选择直接禁止。

**致命错误答法**："可以之后用 app 的 ServiceProvider 加。" —— 你可以从里面**解析**，但不能往已构建的容器里**注册**。

### Q3：Kestrel、IIS 和反向代理——你的应用到底是怎么被对外服务的？

**Kestrel** 是内建、跨平台的 HTTP 服务器，它持有 socket，把原始 HTTP 转成 `HttpContext`。它可以直连互联网作为**边缘服务器**，也可以躲在**反向代理**（IIS、Nginx、YARP）后面，由代理负责 TLS 终结、负载均衡和静态文件。

要点：当你在代理后面时，代理走 localhost 跟 Kestrel 通信，你必须用 `UseForwardedHeaders` 才能拿到真实客户端 IP 和 scheme。Windows/IIS 环境下，ASP.NET Core Module 把请求转发进 Kestrel——IIS 不再运行你的应用，只是 Kestrel 的前置代理。搞错这点就是为什么"内部走 HTTP、外部走 HTTPS"会产生重定向死循环。

**致命错误答法**："IIS 运行应用。" —— 从 ASP.NET Core 起就不对了。

### Q4：什么是通用 Host，为什么 Web 应用和 Worker Service 用同一套 Host？

**Host** 是掌管应用生命周期的对象：DI 容器、配置、日志，以及跟随应用启停的 `IHostedService` 集合。`WebApplication` 建立在同一个通用 Host 之上——一个 Web 应用不过是一个额外跑了 Kestrel 和请求管道的 Host。Worker Service 用完全相同的 Host，只是没有 web 服务器。

**致命错误答法**："Web 应用和 Worker Service 完全不同。" —— 它们共享完全相同的托管基础，只有 web 服务器和管道不同。

---

## 二、中间件管道（Q5-Q10）

这是全 ASP.NET Core 面试中最稳的考点。请准备好解释顺序，以及至少一个"为什么这段代码坏了"的场景题。

### Q5：什么是中间件？管道怎么执行一个请求？

中间件是请求管道中的组件，每个组件拿到一个指向下一个组件的 `RequestDelegate`。每个中间件执行一段逻辑，然后决定是否调用 `next()` 继续往下传——或者直接短路返回。返回时，执行流逆向展开，`await next()` 之后的代码在响应冒泡回来的过程中执行。这就是**洋葱模型**：请求从每一层进去，响应逆向从每一层出来。

**致命错误答法**："中间件处理请求然后发回响应。" —— 漏掉了中间件是一个**链**，而且每个节点决定下一个是否执行。

### Q6：正确的中间件顺序是什么？为什么顺序重要？

顺序决定了行为，不是风格偏好。一个典型正确的顺序：异常处理最先（包裹下面所有层），然后 HSTS 和 HTTPS 重定向，静态文件，`UseRouting`，`UseCors`，`UseAuthentication`，`UseAuthorization`，最后才是端点。

每步的依赖关系：认证必须在授权之前，因为你得先知道用户是谁才能判断他能干什么。路由必须在认证之前，因为框架得先知道匹配到哪个端点、该端点需要什么认证策略。CORS 必须在认证之前，否则预检 `OPTIONS` 请求还没拿到 CORS 头就被拒绝了。

**致命错误答法**："顺序无所谓，框架会自己处理。" —— 顺序绝对有所谓，这是中间件第一大坑。

### Q7：`Use`、`Run` 和 `Map` 的区别？

`Use` 添加可以调用 `next` 继续管道执行的中间件。`Run` 添加**终结**中间件，永远不会调用 `next`，管道到此为止。`Map` 基于请求路径分叉管道，匹配某前缀的请求走独立的子管道。

`Run` 是产生响应的地方，它后面的所有中间件都不会执行。如果你不小心把 `Run` 放在管道中间，它后面的所有中间件会静默丢失。

**致命错误答法**："它们差不多。" —— 那你就解释不了为什么 `Run` 后面的中间件不执行。

### Q8：如何短路管道？在 `next()` 之后写响应有什么 bug？

短路的做法是**不调用 `next()`**——直接写响应（或设状态码）就返回。认证中间件就是这样不执行端点、直接返回 401 的。

要命的 bug：一旦下游中间件已经开始写响应体，响应头就已经发出去了。如果你在 `await next()` 之后的回溯阶段试图改状态码或加响应头，会抛 `InvalidOperationException: response has already started`。所以修改响应的逻辑（改状态码、加响应头）必须放在调用 `next()` 之前。

**致命错误答法**："我在 `await next()` 之后设状态码。" —— 端点一旦写了东西就抛异常。

### Q9：异常处理中间件放哪里？.NET 10 改了什么？

放**最前面**（或接近最前面），因为中间件只能捕获注册在它**之后**的组件抛出的异常。把 `UseExceptionHandler` 放在顶部，它包裹整个请求；放晚了，就看不到前面中间件的失败。

2026 年的时间信号：.NET 10 中异常处理中间件**不再为被 `IExceptionHandler` 处理过的异常写诊断日志**，还新增了 `ExceptionHandlerOptions.SuppressDiagnosticsCallback` 按异常控制日志输出。之前即便异常已被处理，日志里还是像未处理一样刷屏。提这一点说明你跟进当前版本，而且理解异常处理是中间件层面的关注点，不是每个 Controller 里写 try/catch。

**致命错误答法**："我把每个 Controller Action 都包上 try/catch。" —— 集中化异常中间件就是为了替代这种做法。

### Q10：你的自定义中间件需要 Scoped 服务，为什么不能在构造函数里注入？

因为基于约定的中间件在应用启动时**实例化一次**，然后在所有请求上复用——本质上是个 singleton。如果你在构造函数中注入 scoped 服务（如 `DbContext`），你为整个应用生命周期捕获了一个实例：这就是**俘虏依赖**（captive dependency），带过来的是线程安全问题、过期数据和无限增长的变更追踪器。

正确做法是把 scoped 服务注入到 `InvokeAsync` 方法的参数中，框架会在每次请求时从当前请求的 scope 解析：

```csharp
public class AuditMiddleware(RequestDelegate next)
{
    public async Task InvokeAsync(HttpContext context, IAuditService audit)
    {
        await audit.RecordAsync(context.Request.Path);
        await next(context);
    }
}
```

**致命错误答法**："我把 `DbContext` 像普通类一样在构造函数注入。" —— 一个上下文在所有请求间共享。

---

## 三、依赖注入内部原理（Q11-Q15）

DI 是候选人用得最多、理解得最少的框架特性。这些问题区分"我会调 `AddScoped`"和"我知道容器拿它做了什么"。

### Q11：Transient vs Scoped vs Singleton——每种对状态和并发意味着什么？

- **Transient**：每次解析创建一个新实例，适合轻量无状态服务。
- **Scoped**：每个 scope 一个实例，在 web 应用中就是一个 HTTP 请求一个实例，适合在请求内共享但请求间隔离的东西，比如 `DbContext`。
- **Singleton**：整个应用生命周期一个实例，在所有请求和线程间共享，必须线程安全。

核心判断：**生命周期不是风格选择，是正确性决策**。因为 singleton 跨线程共享所以必须线程安全；因为 scoped 是 per-request 所以不能被更长生命周期的服务捕获。

**致命错误答法**："我什么都用 scoped 就安全了。" —— 无状态助手每次都多分配一次实例，而且一旦有 singleton 需要它你就又踩坑了。

### Q12：你把一个 Scoped 服务注入到 Singleton 里，会发生什么？容器怎么检测？

这就是**俘虏依赖**。Singleton 创建一次并永远持有它收到的实例，所以它捕获的 scoped 服务永远不会被替换——一个 `DbContext`、一个变更追踪器，跨所有请求共享。结果：线程安全违规、过期数据、无限制增长的变更追踪器。

容器的检测机制：在 `Development` 环境下，scope validation 默认开启，容器在应用启动时验证依赖图，如果 singleton 依赖 scoped 服务就抛异常。但在 `Production` 环境，出于启动性能考虑这个验证默认关闭——这正是这种 bug 能在本地通过、在线上爆炸的原因。修复方式是在 singleton 中注入 `IServiceScopeFactory`，每次工作单元创建独立 scope。

**致命错误答法**："没什么，正常工作。" —— 在 demo 里能跑，在并发下污染数据。

**追问**："为什么 Production 环境默认关闭 scope validation？"

### Q13：同一个接口注册了三次，解析它得到什么？

解析 `INotifier` 得到**最后一个注册的**实现——容器对单次解析采用 last-wins 策略。但解析 `IEnumerable<INotifier>` 会拿到**全部三个**，按注册顺序。这就是内建的"执行所有 handler"模式。

**致命错误答法**："会抛异常因为你注册了两次。" —— 不会；多重注册是合法的，正是 `IEnumerable<T>` 注入的运作方式。

### Q14：Keyed Service 解决了什么问题？

Keyed Service（.NET 8 起）让你用**不同 key 注册同一接口的多个实现**，并按 key 精确解析某一个——而不是注入 `IEnumerable<T>` 再手动过滤，或手写工厂方法。

```csharp
builder.Services.AddKeyedScoped<IPaymentGateway, StripeGateway>("stripe");
builder.Services.AddKeyedScoped<IPaymentGateway, PayPalGateway>("paypal");

public class Checkout([FromKeyedServices("stripe")] IPaymentGateway gateway) { }
```

需要提的 trade-off：key 重新引入了字符串耦合，所以只在真正"N 选 1 按名称"的场景使用（支付提供商、缓存后端），当实现角色确实不同时优先用不同接口。

### Q15：谁负责 Dispose 容器创建的服务？什么时候？

容器销毁它自己创建的东西，绑定于创建它的 scope。**Scoped** 可释放对象在 scope 结束时释放——对 web 请求就是请求结束时。**Transient** 可释放对象从 scope 解析出来也会被追踪并随 scope 一起释放，这点经常出乎意料：transient `IDisposable` 不是马上回收的，而是撑到 scope 关闭。**Singleton** 在根 Provider 被释放时释放，即应用关闭。

值得点明的坑：如果你自己 new 实例然后用 `AddSingleton(myInstance)` 注册，容器**不会**释放它——你拥有它的生命周期，因为它是你创建的。另外从根 Provider 解析出来的 transient 可释放对象会一直活到应用关闭，如果从 singleton 大量解析它们就是缓慢的内存泄漏。

**致命错误答法**："垃圾回收器处理释放。" —— GC 回收内存，不调用 `Dispose`。容器负责释放，而且只释放它创建的东西。

---

## 四、配置与选项（Q16-Q19）

配置题考察你是否在多个环境部署过，还是只在 `localhost` 上跑过。

### Q16：两个配置源设了同一个 Key，谁赢？

配置是分层的，**后面的 provider 覆盖前面的**。`CreateBuilder` 设置的默认顺序：`appsettings.json` → `appsettings.{Environment}.json` → User Secrets（Development 环境）→ 环境变量 → 命令行参数。所以环境变量赢 `appsettings.json`，命令行参数赢一切。

这样设计的理由：你可以把安全默认值写在 `appsettings.json` 里，然后不修改文件就按环境覆盖——容器把 `ConnectionStrings__Default` 设成环境变量，它就覆盖源码里登记的默认值。

**致命错误答法**："`appsettings.json` 总是赢的，因为它是配置文件。" —— 反了；它是最底层，被环境变量和命令行覆盖。

### Q17：`IOptions` vs `IOptionsSnapshot` vs `IOptionsMonitor`——分别什么时候用？

三者都从 `IConfiguration` 读取强类型配置（Options 模式），区别在生命周期和重载行为：

- **`IOptions<T>`**：singleton，计算一次，永不重载——适合运行时不能变的配置。
- **`IOptionsSnapshot<T>`**：scoped，每请求重新计算一次，能感知请求间的配置变更——因为它是 scoped，不能注入 singleton。
- **`IOptionsMonitor<T>`**：singleton，暴露当前值外加变更回调，配置变更实时生效——在 singleton 和 BackgroundService 里该用它。

经典陷阱：把 `IOptionsSnapshot` 注入 `BackgroundService` 或任何 singleton，要么失败要么捕获过期 scope。长生命周期服务要获取新配置，用 `IOptionsMonitor`。

**致命错误答法**："它们可以互换，我用哪个自动补全出来就用哪个。" —— 它们有不同生命周期，混用会破坏重载或破坏 DI。

### Q18：怎么让错误配置在启动时就失败，而不是半夜三点才爆？

校验 options 并**强制在启动时执行校验**。光绑定不校验——一个缺失的连接字符串只是绑定到 null，在首次使用时才炸，这就是半夜三点的 P1 事故。

正确做法是附加 Data Annotation 或委托校验，然后调用 `ValidateOnStart()`，让应用拒绝用无效配置启动：

```csharp
builder.Services.AddOptions<SmtpOptions>()
    .Bind(builder.Configuration.GetSection("Smtp"))
    .ValidateDataAnnotations()
    .Validate(o => o.Port > 0, "SMTP port must be set")
    .ValidateOnStart();
```

原则很简单：**在部署时有真人在看的时候快速失败、大声失败**，而不是等到运行时客户触发故障路径。这是用一次失败的部署换取一次线上事故。

**致命错误答法**："我在服务里用到配置值的时候再检查。" —— 把失败推迟到运行时。

### Q19：应用怎么选取 `appsettings.Production.json`？环境名从哪来的？

环境名来自 `ASPNETCORE_ENVIRONMENT` 环境变量（或 `DOTNET_ENVIRONMENT`）。Host 在启动时读取它，然后配置系统自动把 `appsettings.{Environment}.json` 叠在 `appsettings.json` 上面。所以设 `ASPNETCORE_ENVIRONMENT=Production` 就加载 `appsettings.Production.json`；不设则默认 `Production`。

代码里 `app.Environment.IsDevelopment()` 读的是同一个值——它同时驱动配置加载、开发者异常页面开关以及你自己的环境分支逻辑。一个环境变量控制配置、错误页和你的所有环境判断。

**致命错误答法**："部署前换一下应用读取的配置文件。" —— 不用换文件；设一个环境变量，框架自动叠加正确的文件。

---

## 五、过滤器与模型绑定（Q20-Q24）

这一块考察你是否理解中间件之上那层——理解 action、参数和结果的管道层。

### Q20：中间件还是过滤器——怎么选？

中间件作用于**每一个请求**，对 action、模型绑定、`ModelState` 一无所知——它只看到原始 `HttpContext`。过滤器在 MVC/Endpoint 层**内部**运行，在路由和模型绑定之后，拥有 action 感知的上下文：已绑定的参数、选中的 action、即将返回的结果。

我的判断规则：适用于整个应用、不需要 action 细节的横切关注点——日志、压缩、CORS、异常处理——放中间件。需要检查 action 参数或短路特定端点结果的关注点——校验、action 级授权策略、响应塑形——放过滤器。选错层意味着要么你看不到需要的数据（中间件），要么你对非 MVC 请求跑了不该跑的逻辑。

**致命错误答法**："它们干同一件事，随便挑。" —— 它们在不同管道阶段运行、拥有不同上下文，这一点正是全部区别。

### Q21：过滤器的执行顺序是什么？短路在哪发生？

过滤器按固定管道执行：**Authorization** 过滤器最先，然后是 **Resource** 过滤器，然后是模型绑定，然后是 **Action** 过滤器（在 action 前后），然后是 **Exception** 过滤器，最后是 **Result** 过滤器（包裹结果执行）。任何过滤器都可以短路：Authorization 过滤器设置 result 就会阻止下面所有步骤执行——`[Authorize]` 就是这样在执行 action 之前拦截的。

细节考点：同类型过滤器在"进入"时按外到内、在"退出"时按内到外执行，再加上 scope（Global / Controller / Action）和 `Order` 属性共同决定顺序。

**致命错误答法**："过滤器就是在 action 之前运行。" —— 有的在前、有的在后、有的包裹结果，而且 Authorization 最先。

### Q22：Action Filter vs Endpoint Filter——Minimal API 的对应物是什么？

Action Filter 属于 MVC/Controller 管道。**Endpoint Filter** 是 Minimal API 的对应物——包裹 route handler 的执行，在模型绑定后运行，能检查和修改已绑定参数及结果：

```csharp
app.MapPost("/orders", (Order o) => Results.Ok(o))
   .AddEndpointFilter(async (ctx, next) =>
   {
       var result = await next(ctx);
       return result;
   });
```

它们服务于相同的架构目的——绑定后的、端点感知的横切逻辑——区别只是给 Minimal API 用的。Endpoint Filter 同样运行在路由/端点层内部，像 Action Filter 一样能看到中间件看不到的绑定参数。

**致命错误答法**："Minimal API 不支持过滤器。" —— 支持；Endpoint Filter 是 .NET 7 起加入的对应物。

### Q23：模型绑定怎么决定从哪里读取参数？

模型绑定用一套**绑定源**和固定优先级把请求数据映射到参数。简单类型先从路由值读，再读 query string。复杂类型的行为取决于控制器：标记 `[ApiController]` 的 Web API 控制器（以及 Minimal API）推断请求体为 JSON，普通 MVC 控制器则默认从表单字段读取——这就是 `[ApiController]` 属性为什么重要。你可以显式指定：`[FromRoute]`、`[FromQuery]`、`[FromBody]`、`[FromHeader]`、`[FromForm]`、`[FromServices]`。

关键坑：**每个请求只能有一个参数从 body 绑定**，因为 body 是只读一次的前向流。给两个参数都标 `[FromBody]`，第二个什么也拿不到。

**致命错误答法**："它就把参数名跟 JSON 字段名对上。" —— 忽略了路由、query、header 多种来源和单 body 参数规则。

### Q24：.NET 10 中怎么不用 FluentValidation 就在 Minimal API 里校验输入？

.NET 10 为 Minimal API 新增了**内建校验**。调用 `AddValidation()` 注册校验服务，框架会自动装配一个 Endpoint Filter，用 `System.ComponentModel.DataAnnotations` 特性校验参数——而且这些特性现在支持 **record 类型**，所以请求 DTO 保持简洁：

```csharp
builder.Services.AddValidation();
app.MapPost("/products", (Product p) => Results.Ok(p));

public record Product([Required] string Name, [Range(1, 1000)] int Quantity);
```

失败时返回 `400` 带 Problem Details，可通过 `IProblemDetailsService` 自定义响应。该提的 trade-off：Data Annotation 覆盖常见场景，但跨字段规则或复杂条件逻辑我还是会用 FluentValidation。知道现在有内建路径是 2026 年的时间信号——在 .NET 10 之前 Minimal API 完全没有任何内建校验。

**致命错误答法**："Minimal API 不能校验，得手动做。" —— .NET 10 之前是对的，现在 `AddValidation()` 是内建的。

---

## 六、请求生命周期与后台工作（Q25-Q30）

这是技术面中偏 Senior 的部分。这些题问的是运行时模型——线程、上下文、生命周期——这些是复制粘贴式知识会露馅的地方。

### Q25：什么是 `HttpContext`，它的生命周期多长，为什么捕获它是 bug？

`HttpContext` 是 per-request 对象，持有关于当前请求和响应的所有信息——请求头、认证用户、请求级 ServiceProvider、body 流。它的生命周期恰好是**一个请求**：Kestrel 接受请求时创建，响应完成时释放。它**不是线程安全**的，请求结束之后**无效**。

所以捕获它是 bug：如果你把 `HttpContext`（或它的 `User`、`Request`）存到字段、静态变量或延后执行的闭包里——比如后台 continuation、fire-and-forget 任务——你就在碰一个已释放的对象，要么抛 `ObjectDisposedException`，要么读到垃圾数据。如果需要请求结束后用请求数据，应该**在请求存活期间把值拷贝出来**传递，永远不要传递 context 本身。

**致命错误答法**："我持有 `HttpContext` 引用以便在后台任务里用。" —— 那个引用在请求完成瞬间就失效了。

### Q26：一个请求内所有代码跑在同一个线程上吗？`await` 时会发生什么？

不会。一个请求**不绑定到某个固定线程**。当你的代码遇到真实 I/O 的 `await` 时，线程被释放回线程池，I/O 完成后 `await` 的延续可能恢复到**不同**的线程。这种线程跳跃正是 async 能支撑高并发的核心——线程不是在干等数据库。

显示深度的细节：ASP.NET Core **没有** `SynchronizationContext`，不像老 ASP.NET。所以没有"UI 线程"需要 marshal 回去，`ConfigureAwait(false)` 在应用代码里不是正确性要求。任何假定请求内线程亲和力的代码——`[ThreadStatic]`、期望同线程的锁——都是错误的。请求级状态存在 DI 或 `HttpContext.Items` 里，而不是线程上。

**致命错误答法**："一个请求从头到尾跑在一个线程上。" —— 任何 async 代码都不对；延续可能恢复在另一个线程上。

### Q27：你需要在 Singleton 服务里拿到当前用户，怎么做？有什么坑？

注入 `IHttpContextAccessor`，在需要的时候读 `HttpContextAccessor.HttpContext`。它可以从 singleton 使用，因为它不捕获 context——它在每次访问时解析**当前**请求的 context，背后靠的是跟随 async 调用链流动的 `AsyncLocal`。

需要点明的坑：没有活跃请求时（BackgroundService、应用启动阶段），它返回 `null`，需要空值守卫。它有来自 `AsyncLocal` 查寻的微小性能开销，不要到处撒。而且必须调用 `AddHttpContextAccessor()` 注册。更干净的做法是尽量在请求级 layer 把用户信息作为参数传进来，而不是在 singleton 深处通过 ambient context 去拿。

**致命错误答法**："我直接把 `HttpContext` 注入到 singleton 里。" —— 不行；`HttpContext` 没有注册，即使注册了也是俘虏依赖。`IHttpContextAccessor` 才是安全的间接层。

### Q28：.NET 10 里未认证 API 调用返回 401 而不是重定向到登录页，怎么回事？

这是 .NET 10 中 Cookie 认证的一个**真实行为变更**。过去未认证请求会触发 **302 重定向到登录页**——即使对 API 端点也是，而这对 API 是错误的：JSON 客户端要的是 `401`，不是 HTML 登录页。在 .NET 10 中，对**已知 API 端点**的请求现在返回 `401`/`403` 而不是重定向。

判断逻辑：新的 `IApiEndpointMetadata` 标记识别 API 端点，它自动应用到 `[ApiController]` action、读写 JSON 的 Minimal API、使用 `TypedResults` 的端点以及 SignalR。框架能区分"这是 API 调用"和"这是浏览器页面"并正确响应。如果你需要旧的重定向行为，可以覆写 `OnRedirectToLogin`。知道这个变更是一个很强的时效信号，说明你理解认证是管道行为而不只是 `[Authorize]`。

**致命错误答法**："这 401 一定是我认证配置的 bug。" —— 这是 .NET 10 的有意变更；API 端点不再拿登录重定向。

### Q29：你的 BackgroundService 需要 DbContext，为什么直接注入是陷阱？关机怎么处理？

`BackgroundService` 注册为 **singleton**——它存活于整个应用生命周期。`DbContext` 是 scoped。在构造函数注入上下文就是俘虏依赖：一个上下文永远不释放，变更追踪器无限增长，跨所有循环迭代共享。正确模式是注入 `IServiceScopeFactory`，每次工作单元创建新 scope：

```csharp
public class Worker(IServiceScopeFactory scopeFactory) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            using var scope = scopeFactory.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            // 每次迭代都是新鲜、短暂的上下文
            await Task.Delay(1000, stoppingToken);
        }
    }
}
```

关于关机：Host 发出 `stoppingToken` 信号，你的循环应该观察它并在关机超时内干净退出——这就是优雅关机。忽略 token 意味着进行中的工作在超时后被强制终止。

**致命错误答法**："我把 `DbContext` 直接注入 BackgroundService。" —— 俘虏依赖；污染状态而且永远不释放上下文。

### Q30：完整走一遍：一个请求从 Socket 到你的端点经历了什么？

这是综合题，能干净走完证明你理解了整个运行时：

1. **Kestrel** 接受 TCP 连接，把原始 HTTP 解析成 `HttpContext`，分配一个请求级 `IServiceProvider`。
2. 请求进入**中间件管道**，按注册顺序——异常处理、HTTPS、静态文件等依次执行。
3. `UseRouting` 把请求匹配到端点；`UseAuthentication` 和 `UseAuthorization` 为该端点建立并检查身份。
4. 到达端点后，**模型绑定**把请求数据读入你的参数，**过滤器 / Endpoint Filter** 管道包裹 handler 执行。
5. 你的 **handler** 执行，从请求级 Provider 解析 scoped 服务。
6. 结果写入响应，执行**逆向展开**沿着中间件回溯，最后请求 scope 释放——释放 scoped 服务和 `DbContext`。

价值在于展示每一层在正确时间点介入，以及 DI scope、路由、管道各在哪一步产生作用。如果你能把这套讲出来，前面每一道题都在这段叙事里有自己的位置。

**致命错误答法**："请求进来，我的 Controller 执行。" —— 跳过了 Kestrel、管道、路由、绑定和 scope 释放——整个框架。

---

## 5 个让 .NET 开发者被刷掉的 ASP.NET Core 面试错误

面试过大量 .NET 开发者后，以下是在内部原理轮上毁掉一个本来不错的候选人的典型模式：

1. **把中间件顺序当风格问题。** 如果你解释不了为什么 auth 运行在 routing 之后、CORS 运行在 auth 之前，面试官会认定你从未调试过管道。
2. **不理解 DI 生命周期。** "我全都用 scoped" 或 "singleton 可以复用嘛"，然后不知道俘虏依赖是什么——说明你从未追踪过一个并发 bug 的根因。
3. **认为一个请求就是一条线程。** 假定线程亲和力——用 `[ThreadStatic]`、期望 `HttpContext` 能在后台任务中用——暴露了你根本不理解 async 的实际执行方式。
4. **落后了两个大版本。** 还在提 `Startup.cs` 的 `Configure`/`ConfigureServices`、`IHostBuilder` 啰嗦写法、或"Minimal API 不能校验"——告诉面试官你的知识停在了 .NET 8 之前。
5. **只背定义，不说机制。** "中间件处理请求"是及格回答。"中间件是一条 `RequestDelegate` 链，每个节点决定是否调用下一个"是优秀回答。

## 核心要点

- **管道是核心概念。** 中间件顺序、短路的洋葱模型解释了大多数 ASP.NET Core 行为——先吃透它。
- **DI 生命周期是正确性决策，不是风格偏好。** 俘虏依赖、scope validation 和释放归属权是区分中级和高级的问题。
- **配置和 Option 考察部署经验。** Provider 优先级、`IOptionsSnapshot` vs `IOptionsMonitor`、`ValidateOnStart` 来自于多环境实战。
- **了解 .NET 10 的变更。** Minimal API 内建校验、Cookie 认证的 401-vs-redirect 变更、异常处理诊断变更，这些是面试官会听的时效信号。
- **每个优秀回答都说出机制。** 先说框架底层做了什么，再说后果，最后说你的默认做法。

---

如果你关注 .NET 开发、技术面试和软件工程实践，可以关注 **Aide Hub**。这里会持续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [30 ASP.NET Core Interview Questions That Actually Get Asked in 2026 — Code with Mukesh](https://codewithmukesh.com/blog/aspnet-core-interview-questions/)
