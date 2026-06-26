---
pubDatetime: 2026-06-26T08:06:07+08:00
title: "Vertical Slice Architecture 生产落地指南：.NET 项目结构的最佳布局"
description: "传统分层项目改一个 feature 要在 Controllers、Services、Repositories 之间来回跳。Vertical Slice Architecture 按 feature 组织代码——每个切片自包含 Endpoint、Handler、Mapping、Validators 四个文件，通过 marker 接口自动注册。这篇文章展示了一个久经验证的生产级 VSA 布局，覆盖切片内部结构、模块间通信、事件驱动和 PublicApi。"
tags:
  [
    "Vertical Slice Architecture",
    ".NET",
    "Architecture",
    "Modular Monolith",
    "C#",
  ]
slug: "vertical-slice-architecture-dotnet-production-layout"
ogImage: "../../assets/903/01-cover.png"
source: "https://antondevtips.com/blog/how-to-structure-production-apps-with-vertical-slice-architecture-in-dotnet-in-2026"
---

Vertical Slice Architecture（VSA）按 feature 而不是技术层组织项目。传统分层项目里，Controllers、Services、Repositories 各占一个文件夹，改一个功能要在三四个目录之间横跳。VSA 的做法是把一个 feature 需要的一切放在一起——endpoint、业务逻辑、校验、数据访问，都在同一个文件夹里。

这带来的好处很直接：feature 内部高内聚、feature 之间松耦合、代码导航更快、改一个 feature 不影响其他 feature。

我（原作者 Anton Martyniuk）在生产环境用 VSA 交付过不少系统，几年下来布局收敛到了一个固定形状，现在每个新项目都复用。这篇文章就展示这个布局——从切片内部结构到模块间通信。

## 生产级 VSA 布局总览

每个垂直切片放在以用例命名的文件夹里。市面上有三种常见风格：

**风格 1：每个类一个文件**

```
Features/
  CreateShipment/
    CreateShipmentRequest.cs
    CreateShipmentResponse.cs
    CreateShipmentEndpoint.cs
    CreateShipmentHandler.cs
    CreateShipmentValidator.cs
```

**风格 2：单文件 + 嵌套类**

```csharp
public static class CreateShipment
{
    public sealed record Request(...);
    public sealed record Response(...);
    public class Validator : AbstractValidator<Request> { }
    public static void MapEndpoint(WebApplication app) { ... }
    private static async Task<IResult> Handle() { ... }
}
```

**风格 3：按关注点拆分——这也是我在生产中用的**

结合前两种的优点：Request 和 Response 放在 Endpoint 文件里，文件数量不会太多，也不必把一切都嵌套在一个 static class 里。

以 "Create Shipment" 为例：

```
Features/
└── CreateShipment/
    ├── CreateShipment.Endpoint.cs
    ├── CreateShipment.Handler.cs
    ├── CreateShipment.Mapping.cs
    └── CreateShipment.Validators.cs
```

如果这个切片会发布事件给其他模块响应，再加一个 `Events/` 子文件夹：

```
Features/
└── CreateShipment/
    ├── CreateShipment.Endpoint.cs
    ├── CreateShipment.Handler.cs
    ├── CreateShipment.Mapping.cs
    ├── CreateShipment.Validators.cs
    └── Events/
        ├── ShipmentCreatedEvent.cs
        ├── UpdateStockEventHandler.cs
        └── CreateCarrierEventHandler.cs
```

命名规范用 `.` 后缀：`{Slice}.Endpoint.cs`、`{Slice}.Handler.cs`，方便在 IDE 搜索和文件树中快速定位。

## Endpoint 文件

Endpoint 文件包含 Request/Response records 和 Minimal API endpoint 类。Endpoint 的职责只有三件事：解析 HTTP 请求、跑校验、调 handler 并翻译成 HTTP 响应。

```csharp
public sealed record CreateShipmentRequest(
    string OrderId,
    Address Address,
    string Carrier,
    string ReceiverEmail,
    List<ShipmentItemRequest> Items);

public class CreateShipmentApiEndpoint : IApiEndpoint
{
    public void MapEndpoint(WebApplication app)
    {
        app.MapPost(RouteConsts.BaseRoute, Handle);
    }

    private static async Task<IResult> Handle(
        [FromBody] CreateShipmentRequest request,
        IValidator<CreateShipmentRequest> validator,
        ICreateShipmentHandler handler,
        CancellationToken cancellationToken)
    {
        var validationResult = await validator
            .ValidateAsync(request, cancellationToken);
        if (!validationResult.IsValid)
        {
            return Results.ValidationProblem(
                validationResult.ToDictionary());
        }

        var response = await handler
            .HandleAsync(request, cancellationToken);
        if (response.IsError)
        {
            return response.Errors.ToProblem();
        }

        return Results.Ok(response.Value);
    }
}
```

Endpoint 实现一个轻量的 marker 接口 `IApiEndpoint`，后面用它做自动注册：

```csharp
public interface IApiEndpoint
{
    void MapEndpoint(WebApplication app);
}
```

校验在 endpoint 里显式调用，不用 MediatR pipeline behavior。整个校验流程保持简单、可追踪。

`response.Errors.ToProblem()` 是一个扩展方法，把业务错误类型（Conflict、NotFound、Validation 等）映射到对应的 HTTP 状态码。

## Handler 文件

Handler 负责业务逻辑。这里不用 MediatR——只是实现 `IHandler` 这个 marker 接口的 plain class：

```csharp
public interface IHandler;
```

Handler 类通过构造注入拿 `DbContext`、跨模块 API、事件发布器和 logger：

```csharp
internal sealed class CreateShipmentHandler(
    ShipmentsDbContext context,
    IStockModuleApi stockApi,
    IEventPublisher eventPublisher,
    ILogger<CreateShipmentHandler> logger)
    : IHandler
{
    public async Task<Result<ShipmentResponse>> HandleAsync(
        CreateShipmentRequest request,
        CancellationToken cancellationToken)
    {
        var shipmentExists = await context.Shipments
            .AnyAsync(x => x.OrderId == request.OrderId,
                cancellationToken);

        if (shipmentExists)
        {
            return ShipmentErrors.AlreadyExists(request.OrderId);
        }

        var stockRequest = CreateCheckStockRequest(request);
        var stockResponse = await stockApi
            .CheckStockAsync(stockRequest, cancellationToken);
        if (!stockResponse.IsSuccess)
        {
            return stockResponse.Errors;
        }

        var shipmentNumber = new Faker().Commerce.Ean8();
        var shipment = request.MapToShipment(shipmentNumber);

        await context.Shipments.AddAsync(shipment, cancellationToken);
        await context.SaveChangesAsync(cancellationToken);

        var shipmentCreatedEvent =
            new ShipmentCreatedEvent(shipment);
        await eventPublisher.PublishAsync(
            shipmentCreatedEvent, cancellationToken);

        return shipment.MapToResponse();
    }
}
```

结构很直：没有多余接口、没有 command、没有 MediatR、没有"魔法导航"。就是对一个确定类的直接调用。

对于预期内的错误，handler 用 Result Pattern 而不是抛异常。模块的错误定义集中在一个静态类里，保持风格一致：

```csharp
internal static class ShipmentErrors
{
    private const string ErrorPrefix = "Shipments";

    internal static Error NotFound(string shipmentNumber) =>
        Error.NotFound(
            $"{ErrorPrefix}.{nameof(NotFound)}",
            $"Shipment with number '{shipmentNumber}' not found");

    internal static Error AlreadyExists(string orderId) =>
        Error.Conflict(
            $"{ErrorPrefix}.{nameof(AlreadyExists)}",
            $"Shipment for order '{orderId}' already exists");
}
```

**跨模块调用走 PublicApi。**handler 不碰 Stocks 模块的任何 internal 实现，只通过 `IStockModuleApi` 调用。这个接口由独立的 `Modules.Stocks.PublicApi` 项目对外暴露。

**事件在持久化后发布。**shipment 落库后再发 `ShipmentCreatedEvent`，其他切片和模块可以响应这个事件，而 handler 不需要知道它们的存在。

## Mapping 和 Validation

对象映射全部手写，用静态扩展方法，不用 AutoMapper 或 Mapster：

```csharp
internal static class CreateShipmentMappingExtensions
{
    public static Shipment MapToShipment(
        this CreateShipmentRequest request) { ... }

    public static ShipmentResponse MapToResponse(
        this Shipment shipment) { ... }
}
```

手写映射有两个好处：完全显式——能直接导航到并看清楚每一步；没有反射开销。如果某个映射被多个切片复用，就挪到模块的 `Shared/` 文件夹，不重复。

校验用 FluentValidation，一个切片的所有 validator 放在一个文件里：

```csharp
public class CreateShipmentRequestValidator
    : AbstractValidator<CreateShipmentRequest>
{
    public CreateShipmentRequestValidator()
    {
        RuleFor(s => s.OrderId).NotEmpty();
        RuleFor(s => s.Carrier).NotEmpty();
        RuleFor(s => s.ReceiverEmail).NotEmpty();
        RuleFor(s => s.Items).NotEmpty();

        RuleFor(s => s.Address)
            .Cascade(CascadeMode.Stop)
            .NotNull()
            .SetValidator(new AddressValidator());
    }
}
```

## 模块内的 Shared 文件夹

同一个模块里多个切片会共用一些东西：路由常量、错误定义、响应类型。这些放在模块 `Features/` 下的 `Shared/` 文件夹里：

```
Features/
├── CreateShipment/
├── DispatchShipment/
├── GetShipmentByNumber/
└── Shared/
    ├── Errors/
    │   └── ShipmentErrors.cs
    ├── Requests/
    │   └── ShipmentItemRequest.cs
    ├── Responses/
    │   ├── ShipmentResponse.cs
    │   └── ShipmentItemResponse.cs
    └── Routes/
        └── RouteConsts.cs
```

路由常量集中管理，修改时不用在多个切片文件里搜索：

```csharp
internal static class RouteConsts
{
    internal const string BaseRoute = "/api/shipments";
    internal const string GetByNumber =
        $"{BaseRoute}/{{shipmentNumber}}";
    internal const string CancelShipment =
        $"{BaseRoute}/cancel/{{shipmentNumber}}";
}
```

## Endpoint、Handler 和 Validator 的自动注册

每个切片至少四个文件——如果每个都手动在 `Program.cs` 里注册，DI 代码会爆炸。这里用反射扫描程序集并自动注册。

**Endpoint 注册：**

```csharp
public static IServiceCollection
    RegisterApiEndpointsFromAssemblyContaining(
        this IServiceCollection services, Type marker)
{
    var assembly = marker.Assembly;
    var endpointTypes = assembly.GetTypes()
        .Where(t => t.IsAssignableTo(typeof(IApiEndpoint))
            && t is { IsClass: true, IsAbstract: false });

    var descriptors = endpointTypes
        .Select(type => ServiceDescriptor.Transient(
            typeof(IApiEndpoint), type))
        .ToArray();

    services.TryAddEnumerable(descriptors);
    return services;
}

public static WebApplication MapApiEndpoints(
    this WebApplication app)
{
    var endpoints = app.Services
        .GetRequiredService<IEnumerable<IApiEndpoint>>();
    foreach (var endpoint in endpoints)
    {
        endpoint.MapEndpoint(app);
    }
    return app;
}
```

**Handler 注册：**

```csharp
public static IServiceCollection
    RegisterHandlersFromAssemblyContaining(
        this IServiceCollection services, Type marker)
{
    var assembly = marker.Assembly;
    var handlerTypes = assembly.GetTypes()
        .Where(t => t is { IsClass: true, IsAbstract: false }
            && t.IsAssignableTo(typeof(IHandler))
            && !t.IsAssignableTo(typeof(IEventHandler)));

    foreach (var implementationType in handlerTypes)
    {
        var interfaceType = implementationType
            .GetInterfaces()
            .FirstOrDefault(i =>
                i != typeof(IHandler)
                && i.IsAssignableTo(typeof(IHandler)));

        if (interfaceType is not null)
        {
            services.AddScoped(interfaceType, implementationType);
        }
    }
    return services;
}
```

新增一个切片时不需要碰任何 DI 注册代码——只要类实现了 `IHandler` 或 `IApiEndpoint`，就会被自动发现。

## 切片间的事件通信

切片和模块之间通过事件和方法调用通信。"Create Shipment" 完成后，需要更新库存（Stocks 模块）和注册承运商（Carriers 模块）。事件和 handler 各占一个文件，放在切片内的 `Events/` 子文件夹：

```csharp
public sealed class UpdateStockEventHandler(
    IStockModuleApi stockApi,
    ILogger<UpdateStockEventHandler> logger)
    : IEventHandler<ShipmentCreatedEvent>
{
    public async Task HandleAsync(
        ShipmentCreatedEvent @event,
        CancellationToken cancellationToken)
    {
        var updateRequest = CreateDecreaseStockRequest(
            @event.Shipment);
        var response = await stockApi.DecreaseStockAsync(
            updateRequest, cancellationToken);

        if (!response.IsSuccess)
        {
            throw new Exception(
                $"Failed to update stock: {response.Errors}");
        }
    }
}
```

事件通过 `IEventPublisher` 派发。发布者不知道谁在监听，监听者不依赖发布者——典型的松耦合。

## 模块间通过 PublicApi 通信

在 Modular Monolith 里，模块不能碰彼此的 internal 实现。模块之间只通过公开接口或事件通信。每个模块有一个独立的 `Modules.{Module}.PublicApi` 项目，里面只有接口和对应的 request/response record：

```csharp
public interface IStockModuleApi
{
    Task<Result<Success>> CheckStockAsync(
        CheckStockRequest request,
        CancellationToken cancellationToken);

    Task<Result<Success>> DecreaseStockAsync(
        DecreaseStockRequest request,
        CancellationToken cancellationToken);
}
```

Shipments 模块只引用 `Modules.Stocks.PublicApi`，不能引用 Stock 的 domain entity、DbContext 或 internal service。`IStockModuleApi` 的实现放在 Stock 模块内部，标记为 `internal sealed`。

这给了你微服务的分离好处（清晰契约、不共享内部实现），同时保持单体部署的简单。如果将来把某个模块拆成独立服务，PublicApi 契约不用动，只换底层传输实现。

## 小结

这个切片布局现在是我每个新 .NET 项目的起点：

- 一个 feature 一个文件夹，以用例命名
- 每个切片四个文件：`Endpoint`、`Handler`、`Mapping`、`Validators`
- 需要事件时加 `Events/` 子文件夹
- 手动 handler，`IHandler` marker 接口，不用 MediatR
- Minimal API endpoint，`IApiEndpoint` marker 接口
- FluentValidation 在 endpoint 里显式调用
- Handler 直接拿 `DbContext`，不套 Repository
- `Result<T>` 处理业务错误，不用异常
- 模块内 `Shared/` 文件夹放跨切片共用物
- 跨模块调用只走 `PublicApi` 项目
- Endpoint 和 handler 反射自动注册

实际效果：导航快、团队内可预测、调试直接（没有装饰器、没有魔法）、测试简单、第三方依赖少。

> 如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [原文：How to Structure Production Apps with Vertical Slice Architecture in .NET in 2026](https://antondevtips.com/blog/how-to-structure-production-apps-with-vertical-slice-architecture-in-dotnet-in-2026)
