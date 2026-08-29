---
pubDatetime: 2026-08-29T20:03:00+08:00
title: "ASP.NET Core Minimal API 过滤器实战"
description: "用 ASP.NET Core Minimal API Endpoint Filter 在处理程序前后执行校验、日志和响应控制，并掌握委托、IEndpointFilter、路由组、工厂及 .NET 10 内置校验的选择边界。"
tags: ["ASP.NET Core", ".NET", "Minimal API", "C#", "Endpoint Filter"]
slug: "aspnet-core-minimal-api-endpoint-filters"
ogImage: "../../assets/1035/01-cover.jpg"
source: "https://www.yogihosting.com/aspnet-core-minimal-api-filters/"
---

Minimal API 写到一定规模后，端点里很容易出现重复代码：先检查参数，再记录耗时，接着判断业务权限，最后才进入真正的处理逻辑。每个处理程序都复制一遍，会让路由定义越来越难读，错误响应也容易失去一致性。

Endpoint Filter 可以把这些与单个端点或一组端点相关的逻辑包在处理程序外层。它既能在处理程序之前检查已绑定的参数，也能提前返回结果，还能在处理完成后观察或替换响应。

它最值得掌握的地方有三个：

1. 调用 `next` 前后的代码形成一层包装。
2. 不调用 `next` 就会短路，处理程序不会执行。
3. 多个过滤器按注册顺序进入，再按相反顺序退出。

下面用一个订单接口把委托过滤器、`IEndpointFilter`、路由组和 .NET 10 内置校验串起来。示例已使用 .NET SDK 10.0.100 编译并实际请求验证。

## Endpoint Filter 适合解决什么问题

官方文档列出的典型用途包括参数校验、请求与响应日志、API 版本检查，以及响应行为控制。实际项目中，可以把它放在中间件与处理程序之间理解：

- **中间件** 面向整个 HTTP 请求管线，适合全局异常处理、CORS、认证和通用请求日志。
- **Endpoint Filter** 已经知道当前端点和绑定后的参数，适合端点级业务约束、参数检查、耗时记录与结果加工。
- **处理程序** 专注于当前用例本身，例如创建订单或读取数据库。

过滤器拿到的是 `EndpointFilterInvocationContext`。其中的 `HttpContext` 提供当前请求信息，`Arguments` 则按处理程序参数的声明顺序保存绑定结果。

## 最小示例：检查参数并短路

先创建项目：

```bash
dotnet new web -n EndpointFilterDemo
cd EndpointFilterDemo
```

一个局部规则可以直接写成委托：

```csharp
app.MapPost("/orders", (CreateOrderRequest request) =>
    TypedResults.Created(
        $"/orders/{Guid.NewGuid()}",
        new { request.ProductId, request.Quantity }))
    .AddEndpointFilter(async (context, next) =>
    {
        var request = context.GetArgument<CreateOrderRequest>(0);

        if (request.Quantity > 100)
        {
            return TypedResults.Problem(
                title: "Manual approval required",
                detail: "Orders above 100 units cannot be created directly.",
                statusCode: StatusCodes.Status422UnprocessableEntity);
        }

        return await next(context);
    });
```

`GetArgument<CreateOrderRequest>(0)` 读取处理程序的第一个参数。数量超过 100 时，过滤器直接返回 `422`，后面的处理程序不会运行。数量符合要求时，`next(context)` 把控制权交给下一层过滤器；如果没有更多过滤器，就进入路由处理程序。

这种写法适合只服务于一个端点的短规则。逻辑开始复用或需要依赖注入时，单独实现 `IEndpointFilter` 会更清楚。

## 可复用过滤器：IEndpointFilter

把数量规则提取为类：

```csharp
sealed class QuantityLimitFilter(
    ILogger<QuantityLimitFilter> logger) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var request = context.GetArgument<CreateOrderRequest>(0);

        if (request.Quantity > 100)
        {
            logger.LogWarning(
                "Order quantity {Quantity} requires manual approval",
                request.Quantity);

            return TypedResults.Problem(
                title: "Manual approval required",
                detail: "Orders above 100 units cannot be created directly.",
                statusCode: StatusCodes.Status422UnprocessableEntity);
        }

        return await next(context);
    }
}
```

通过泛型扩展方法挂到端点：

```csharp
app.MapPost("/orders", CreateOrder)
    .AddEndpointFilter<QuantityLimitFilter>();
```

过滤器构造函数可以取得日志记录器等已注册依赖。框架会创建过滤器实例，因此通常无需把过滤器类型另行注册成服务。

如果过滤器自身需要可变状态，要先考虑并发请求。更稳妥的做法是让过滤器保持无状态，把请求级状态放进局部变量或作用域服务。

## 在处理程序之后记录耗时

调用 `next` 之前可以观察请求，调用完成后则可以处理结果。下面的过滤器用 `finally` 保证成功、短路和异常路径都能记录耗时：

```csharp
using System.Diagnostics;

sealed class RequestTimingFilter(
    ILogger<RequestTimingFilter> logger) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var stopwatch = Stopwatch.StartNew();

        try
        {
            return await next(context);
        }
        finally
        {
            logger.LogInformation(
                "{Method} {Path} took {ElapsedMilliseconds} ms",
                context.HttpContext.Request.Method,
                context.HttpContext.Request.Path,
                stopwatch.ElapsedMilliseconds);
        }
    }
}
```

如果需要修改处理结果，可以先保存 `await next(context)` 的返回值，再根据类型决定是否替换。不要假设所有处理程序都返回同一种具体类型；Minimal API 可能返回字符串、普通对象或各种 `IResult` 实现。

## 多个过滤器如何执行

假设按下面顺序注册：

```csharp
app.MapGet("/demo", Handler)
    .AddEndpointFilter<FirstFilter>()
    .AddEndpointFilter<SecondFilter>()
    .AddEndpointFilter<ThirdFilter>();
```

执行顺序是：

```text
First 进入
  Second 进入
    Third 进入
      Handler
    Third 退出
  Second 退出
First 退出
```

官方文档把进入阶段描述为 FIFO，退出阶段描述为 FILO。它与多层函数包装很相似：先注册的过滤器位于外层，后注册的过滤器靠近处理程序。

顺序会影响结果。认证或通用日志通常应位于外层，参数校验可以放在业务处理之前；如果某个过滤器短路，位于它内层的过滤器与处理程序都不会执行，已经进入的外层过滤器仍会继续执行退出部分。

## 给一组端点添加过滤器

订单相关路由可以通过 `MapGroup` 共用过滤器：

```csharp
var orders = app.MapGroup("/orders")
    .AddEndpointFilter<RequestTimingFilter>();

orders.MapPost("/", CreateOrder)
    .AddEndpointFilter<QuantityLimitFilter>();

orders.MapGet("/{id:guid}", GetOrder);
```

`RequestTimingFilter` 会应用到组内所有端点，`QuantityLimitFilter` 只应用到创建订单。请求 `POST /orders` 时，路由组过滤器先进入，端点过滤器随后进入；返回时顺序相反。

路由组适合共享稳定规则。不要把只适用于某个参数位置的过滤器直接挂到包含多种处理程序签名的整个组，否则 `GetArgument<T>(index)` 可能读到错误参数或抛出异常。

## 参数位置变化时使用过滤器工厂

`GetArgument<T>(0)` 简单直接，也依赖处理程序签名保持不变。多个端点的参数顺序不同，或过滤器需要先检查处理程序元数据时，可以使用 `AddEndpointFilterFactory`。

工厂在创建端点管线时读取 `MethodInfo`，提前找到目标参数位置：

```csharp
orders.AddEndpointFilterFactory((factoryContext, next) =>
{
    var parameters = factoryContext.MethodInfo.GetParameters();
    var requestIndex = Array.FindIndex(
        parameters,
        parameter => parameter.ParameterType == typeof(CreateOrderRequest));

    if (requestIndex < 0)
    {
        return next;
    }

    return async invocationContext =>
    {
        var request = invocationContext
            .GetArgument<CreateOrderRequest>(requestIndex);

        if (request.Quantity > 100)
        {
            return TypedResults.Problem(
                title: "Manual approval required",
                statusCode: StatusCodes.Status422UnprocessableEntity);
        }

        return await next(invocationContext);
    };
});
```

参数反射只在管线创建阶段完成，请求到来后直接使用已找到的索引。工厂也可以根据方法特性、返回类型或端点元数据决定是否生成过滤逻辑。

## .NET 10：常规校验先用 AddValidation

早期 Minimal API 项目经常自己编写 Endpoint Filter 处理 DataAnnotations。.NET 10 已经提供内置校验，可以先注册：

```csharp
builder.Services.AddValidation();
```

再给请求类型添加规则：

```csharp
using System.ComponentModel.DataAnnotations;

public sealed class CreateOrderRequest
{
    [Required]
    public string ProductId { get; init; } = string.Empty;

    [Range(1, 1000)]
    public int Quantity { get; init; }
}
```

框架会为相关端点加入内置验证过滤器。DataAnnotations 校验失败时返回 `400 Bad Request` 和错误明细。`Quantity > 100` 这类业务规则仍然可以由自定义过滤器返回 `422`，两者职责清楚：

- `AddValidation()` 处理必填、范围等声明式输入规则。
- 自定义 Endpoint Filter 处理业务约束、外部检查和端点级响应控制。

内置校验使用源生成器，只发现调用 `AddValidation()` 所在程序集中的相关类型。如果端点定义在独立类库，需要在那个程序集内提供调用 `AddValidation()` 的扩展方法，再由宿主调用它。

## 完整可运行示例

下面的 `Program.cs` 包含内置校验、路由组耗时记录和业务数量限制：

```csharp
using System.ComponentModel.DataAnnotations;
using System.Diagnostics;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddValidation();

var app = builder.Build();

var orders = app.MapGroup("/orders")
    .AddEndpointFilter<RequestTimingFilter>();

orders.MapPost("/", (CreateOrderRequest request) =>
    TypedResults.Created(
        $"/orders/{Guid.NewGuid()}",
        new { request.ProductId, request.Quantity }))
    .AddEndpointFilter<QuantityLimitFilter>();

app.Run();

sealed class RequestTimingFilter(
    ILogger<RequestTimingFilter> logger) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var stopwatch = Stopwatch.StartNew();

        try
        {
            return await next(context);
        }
        finally
        {
            logger.LogInformation(
                "{Method} {Path} took {ElapsedMilliseconds} ms",
                context.HttpContext.Request.Method,
                context.HttpContext.Request.Path,
                stopwatch.ElapsedMilliseconds);
        }
    }
}

sealed class QuantityLimitFilter(
    ILogger<QuantityLimitFilter> logger) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext context,
        EndpointFilterDelegate next)
    {
        var request = context.GetArgument<CreateOrderRequest>(0);

        if (request.Quantity > 100)
        {
            logger.LogWarning(
                "Order quantity {Quantity} requires manual approval",
                request.Quantity);

            return TypedResults.Problem(
                title: "Manual approval required",
                detail: "Orders above 100 units cannot be created directly.",
                statusCode: StatusCodes.Status422UnprocessableEntity);
        }

        return await next(context);
    }
}

public sealed class CreateOrderRequest
{
    [Required]
    public string ProductId { get; init; } = string.Empty;

    [Range(1, 1000)]
    public int Quantity { get; init; }
}
```

运行应用：

```bash
dotnet run
```

根据终端显示的地址发送三次请求。

合法输入返回 `201 Created`：

```bash
curl -i -X POST http://localhost:5000/orders/ \
  -H 'Content-Type: application/json' \
  -d '{"productId":"P-100","quantity":2}'
```

超过业务限制返回 `422 Unprocessable Entity`，创建处理程序不会执行：

```bash
curl -i -X POST http://localhost:5000/orders/ \
  -H 'Content-Type: application/json' \
  -d '{"productId":"P-100","quantity":101}'
```

违反 DataAnnotations 时，由 .NET 10 内置校验返回 `400 Bad Request`：

```bash
curl -i -X POST http://localhost:5000/orders/ \
  -H 'Content-Type: application/json' \
  -d '{"productId":"","quantity":0}'
```

终端还会出现 `RequestTimingFilter` 写入的耗时日志。这样可以同时确认过滤器的进入、短路和退出路径。

## 认证与授权不要重复实现

Endpoint Filter 能访问 `HttpContext.User`，适合在身份已经确认后检查资源归属等业务规则。例如，只有订单创建者可以修改某张订单。

账号身份验证、角色和声明策略应继续使用 ASP.NET Core 的认证与授权系统，并通过 `RequireAuthorization()` 应用到端点或路由组。这样可以复用认证处理程序、授权服务和一致的失败响应。自定义过滤器只补充与当前资源相关的细粒度检查。

类似地，全局异常响应优先使用异常处理中间件。只有某类端点确实需要独立转换结果时，才在 Endpoint Filter 中捕获或替换响应。

## 常见错误

### 忘记调用 next

过滤器没有返回结果，也没有调用 `next(context)`，管线就无法进入下一层。短路应该有明确的状态码和错误体。

### 写死参数索引

处理程序参数增加或调换后，`GetArgument<T>(0)` 可能失效。只服务一个稳定签名时可以固定索引；覆盖多个签名时用过滤器工厂预先查找位置。

### 过滤器顺序与预期不符

多个过滤器的退出顺序与进入顺序相反。日志、异常转换和结果加工互相依赖时，先画出包装层次再决定注册顺序。

### 把所有逻辑都塞进过滤器

过滤器适合短小、可复用的端点边界逻辑。核心业务规则仍应放在应用服务或领域代码中，否则业务只能通过 HTTP 管线复用，也更难单独测试。

### 用过滤器替代认证系统

手工读取 Header 或自己解析令牌会绕开框架已有的安全处理。先使用标准认证与授权，再在过滤器中补充资源归属等业务判断。

## 选择方式

可以按下面的规则开始：

- 只影响一个端点、代码很短：使用委托过滤器。
- 多个端点复用，或需要构造函数依赖：实现 `IEndpointFilter`。
- 一组路由共享稳定规则：把过滤器加到 `MapGroup`。
- 需要检查处理程序签名或缓存反射结果：使用 `AddEndpointFilterFactory`。
- .NET 10 的必填、范围等 DataAnnotations：优先使用 `AddValidation()`。
- 全局 HTTP 行为：使用中间件。
- 身份、角色与声明策略：使用认证和授权系统。

先选一个重复参数检查最多的端点，把规则提取成过滤器，再用成功、短路和异常三条路径验证执行顺序。确认边界合适后，再扩展到路由组，通常比一开始给所有端点套同一组过滤器更稳妥。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践。如果你正在整理 Minimal API，可以先统计端点里重复出现的校验与日志代码，再判断哪些适合提取为过滤器。

## 参考

- [Filters in ASP.NET Core Minimal API（YogiHosting 原文）](https://www.yogihosting.com/aspnet-core-minimal-api-filters/)
- [Filters in Minimal API apps（Microsoft Learn）](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/min-api-filters)
- [Route handlers in Minimal API apps（Microsoft Learn）](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/route-handlers)
- [Validation in ASP.NET Core（Microsoft Learn）](https://learn.microsoft.com/en-us/aspnet/core/validation/overview)
- [Authentication and authorization in Minimal APIs（Microsoft Learn）](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/security)
