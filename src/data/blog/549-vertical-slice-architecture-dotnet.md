---
pubDatetime: 2026-02-24
title: ".NET 中的垂直切片架构：按功能组织代码"
description: "垂直切片架构（Vertical Slice Architecture）将某一功能的所有代码组织在一起，从 API 到数据库一步到位。本文介绍这种架构模式的核心原则、完整实现、常见模式以及在现有项目中的渐进式采用策略。"
tags: [".NET", "Architecture", "MediatR", "Clean Code"]
slug: "vertical-slice-architecture-dotnet"
source: "https://adrianbailador.github.io/blog/47-vertical-slice-architecture"
---

大多数 .NET 应用按水平层级来组织代码：表现层、业务逻辑层、数据访问层。但如果我们换一种思路，按业务功能来组织代码呢？

这就是垂直切片架构（Vertical Slice Architecture，简称 VSA），一种正在改变 .NET 应用结构方式的架构模式。

> 垂直切片架构把一个功能的全部代码放在一起（API → 逻辑 → 数据库）。不再需要跳转五个文件夹才能理解一个功能。

## 什么是垂直切片架构

垂直切片架构是一种代码组织模式，它把某一功能或用例所需的全部代码放在一起，从用户界面一直到数据库。

**核心概念**

把应用想象成一块蛋糕。传统架构是横着切：

- 顶层：表现层（Controllers、Views）
- 中间层：业务逻辑层（Services、Commands）
- 底层：数据访问层（Repositories、DbContext）

垂直切片架构是竖着切。每一个切片包含了某个具体功能所需的一切：

- 切片 1："创建产品" → 从 API 到数据库完整闭环
- 切片 2："发货" → 从 API 到数据库完整闭环
- 切片 3："用户注册" → 从 API 到数据库完整闭环

**为什么叫"垂直"**

一个垂直切片会贯穿所有层级来实现单一功能。当你需要为"创建产品"添加一个字段时，只需要修改 `Features/Products/Create/` 下的文件，不必在 Controllers → Services → Repositories 之间反复跳转。

## 项目结构

```
MyApp/
├── Features/
│   ├── Products/
│   │   ├── Create/
│   │   │   ├── CreateProduct.cs
│   │   │   └── CreateProductEndpoint.cs
│   │   ├── Update/
│   │   ├── Delete/
│   │   └── GetById/
│   ├── Orders/
│   │   ├── Create/
│   │   ├── Ship/
│   │   └── Cancel/
│   └── Customers/
├── Common/              # 仅存放真正共享的基础设施
│   ├── Behaviors/       # MediatR 管道行为
│   └── Results/
├── Data/
│   ├── AppDbContext.cs
│   └── Entities/
└── Program.cs
```

"创建产品"的所有代码都在同一个位置：`Features/Products/Create/`。

## 核心原则

**1. 功能优先的组织方式**

代码按"它做什么"（业务能力）来组织，而不是按"它属于哪一类"（技术角色）。

| 传统分层架构                        | 垂直切片架构                                        |
| ----------------------------------- | --------------------------------------------------- |
| `Controllers/ProductsController.cs` | `Features/Products/Create/CreateProduct.cs`         |
| `Services/ProductService.cs`        | `Features/Products/Create/CreateProductEndpoint.cs` |
| `Repositories/ProductRepository.cs` | （逻辑和数据访问都在切片内部）                      |

要理解"创建产品"，你只需要看一个文件夹，不用在三个不同文件夹里找三个文件。

**2. 高内聚、低耦合**

- 高内聚：相关代码放在一起。Command、验证和逻辑都在同一个文件或文件夹里，一眼就能看到完整画面。
- 低耦合：功能之间互不依赖。删除"创建产品"不会影响"发货"。每个功能可以独立演进。

**3. 最少的抽象**

只在确实存在共享行为时才创建抽象。在 VSA 中，我们通常在 Handler 中直接使用 `DbContext`。

不要这样做：

```csharp
// 为单一实现创建抽象层
public interface IProductRepository
{
    Task<Product> GetByIdAsync(int id);
}

public class ProductRepository : IProductRepository
{
    // 唯一的实现，永远不会被替换
}
```

应该这样做：

```csharp
// 在 Handler 中直接访问数据库
public class Handler : IRequestHandler<Query, Result<ProductDto>>
{
    private readonly AppDbContext _db;

    public async Task<Result<ProductDto>> Handle(Query request, CancellationToken ct)
    {
        var product = await _db.Products
            .Where(p => p.Id == request.Id)
            .Select(p => new ProductDto { Id = p.Id, Name = p.Name })
            .FirstOrDefaultAsync(ct);

        return product != null
            ? Result<ProductDto>.Success(product)
            : Result<ProductDto>.Failure("Product not found");
    }
}
```

如果你明天不会把数据库换成文本文件，那多半不需要 Repository 层。

**4. 允许适度重复，避免错误的抽象**

在切片之间复制一个 DTO 或一小段逻辑来保持切片独立，这完全可以接受。

```csharp
// Products/Create
var product = new Product {
    CreatedAt = DateTime.UtcNow,
    CreatedBy = _currentUser.Id
};

// Orders/Create - 代码相同，没问题！
var order = new Order {
    CreatedAt = DateTime.UtcNow,
    CreatedBy = _currentUser.Id
};
```

> "三次法则"：只有在 3 个以上的功能中使用了同样的代码时才提取公共逻辑，而不是提前。

为什么？因为这两个功能将来可能会各自变化。过早的抽象反而会引入耦合。

## 完整实现："创建产品"

下面用 MediatR 和 Minimal API 从头构建一个功能。

**第一步：Command 和 Handler**

```csharp
// Features/Products/Create/CreateProduct.cs

namespace MyApp.Features.Products.Create;

public static class CreateProduct
{
    // 请求
    public record Command(
        string Name,
        decimal Price,
        int CategoryId
    ) : IRequest<Result<int>>;

    // 验证规则
    public class Validator : AbstractValidator<Command>
    {
        public Validator()
        {
            RuleFor(x => x.Name).NotEmpty().MaximumLength(100);
            RuleFor(x => x.Price).GreaterThan(0).LessThan(1000000);
            RuleFor(x => x.CategoryId).GreaterThan(0);
        }
    }

    // 业务逻辑
    public class Handler : IRequestHandler<Command, Result<int>>
    {
        private readonly AppDbContext _db;
        private readonly ILogger<Handler> _logger;

        public Handler(AppDbContext db, ILogger<Handler> logger)
        {
            _db = db;
            _logger = logger;
        }

        public async Task<Result<int>> Handle(Command request, CancellationToken ct)
        {
            // 业务规则：分类必须存在
            var categoryExists = await _db.Categories
                .AnyAsync(c => c.Id == request.CategoryId, ct);

            if (!categoryExists)
                return Result<int>.Failure("Category not found");

            // 创建产品
            var product = new Product {
                Name = request.Name,
                Price = request.Price,
                CategoryId = request.CategoryId,
                CreatedAt = DateTime.UtcNow
            };

            _db.Products.Add(product);
            await _db.SaveChangesAsync(ct);

            _logger.LogInformation(
                "Created product {ProductId}: {ProductName}",
                product.Id, product.Name);

            return Result<int>.Success(product.Id);
        }
    }
}
```

所有内容在一个文件中：请求、验证和业务逻辑。不用打开多个文件就能理解整个功能。

**第二步：Endpoint**

```csharp
// Features/Products/Create/CreateProductEndpoint.cs

public class CreateProductEndpoint : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        app.MapPost("/api/products", async (
            CreateProduct.Command request,
            IMediator mediator,
            CancellationToken ct) =>
        {
            var result = await mediator.Send(request, ct);

            return result.IsSuccess
                ? Results.Created($"/api/products/{result.Value}", new { id = result.Value })
                : Results.BadRequest(new { error = result.Error });
        })
        .WithName("CreateProduct")
        .WithTags("Products");
    }
}
```

就这样！一个完整的功能只需要 2 个文件。

**第三步：支撑类型**

```csharp
// Common/Results/Result.cs

public class Result<T>
{
    public bool IsSuccess { get; }
    public T Value { get; }
    public string Error { get; }

    private Result(bool isSuccess, T value, string error)
    {
        IsSuccess = isSuccess;
        Value = value;
        Error = error;
    }

    public static Result<T> Success(T value) => new(true, value, string.Empty);
    public static Result<T> Failure(string error) => new(false, default!, error);
}
```

## 请求流转过程

来跟踪一个请求在系统中的完整流转：

用户请求：`POST /api/products`

```json
{
  "name": "Laptop",
  "price": 1299.99,
  "categoryId": 5
}
```

流转步骤：

1. **Endpoint 接收请求** → 反序列化为 `CreateProduct.Command`
2. **MediatR 管道启动** → `mediator.Send(request)`
3. **自动执行验证** → `ValidationBehavior` 拦截并运行 `CreateProduct.Validator`
   - 验证失败 → 返回 `400 Bad Request`
   - 验证通过 → 继续执行 Handler
4. **自动记录日志** → `LoggingBehavior` 记录请求信息
5. **Handler 执行** → 业务规则检查、数据库操作
6. **返回响应** → `Result<int>` 转换为 HTTP 响应
   - 成功 → `201 Created`
   - 失败 → `400 Bad Request`

关键点：验证和日志通过 MediatR 管道行为自动完成，不需要在每个 Handler 里手动编写。

## 使用 MediatR Behaviors 处理横切关注点

横切功能通过管道行为来处理，而不是通过继承或基类。

**验证行为**

```csharp
// Common/Behaviors/ValidationBehavior.cs

public class ValidationBehavior<TRequest, TResponse> : IPipelineBehavior<TRequest, TResponse>
    where TRequest : IRequest<TResponse>
{
    private readonly IEnumerable<IValidator<TRequest>> _validators;

    public async Task<TResponse> Handle(
        TRequest request,
        RequestHandlerDelegate<TResponse> next,
        CancellationToken ct)
    {
        if (!_validators.Any())
            return await next();

        var context = new ValidationContext<TRequest>(request);
        var failures = _validators
            .Select(v => v.Validate(context))
            .SelectMany(result => result.Errors)
            .Where(f => f != null)
            .ToList();

        if (failures.Any())
            throw new ValidationException(failures);

        return await next();
    }
}
```

**日志行为**

```csharp
// Common/Behaviors/LoggingBehavior.cs

public class LoggingBehavior<TRequest, TResponse> : IPipelineBehavior<TRequest, TResponse>
    where TRequest : IRequest<TResponse>
{
    private readonly ILogger<LoggingBehavior<TRequest, TResponse>> _logger;

    public async Task<TResponse> Handle(
        TRequest request,
        RequestHandlerDelegate<TResponse> next,
        CancellationToken ct)
    {
        _logger.LogInformation("Handling {RequestName}", typeof(TRequest).Name);
        var response = await next();
        _logger.LogInformation("Handled {RequestName}", typeof(TRequest).Name);
        return response;
    }
}
```

**在 Program.cs 中注册 Behaviors**

```csharp
builder.Services.AddMediatR(cfg =>
{
    cfg.RegisterServicesFromAssembly(typeof(Program).Assembly);
    cfg.AddBehavior(typeof(IPipelineBehavior<,>), typeof(LoggingBehavior<,>));
    cfg.AddBehavior(typeof(IPipelineBehavior<,>), typeof(ValidationBehavior<,>));
});
```

每个功能自动获得验证和日志能力，不需要修改任何 Handler。

## 测试策略

在 VSA 中，我们优先使用集成测试。由于切片是自包含的，使用真实（或内存）数据库测试 API 端点能以最小的成本获得最大的信心。

```csharp
public class CreateProductTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public CreateProductTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task CreateProduct_WithValidData_ReturnsCreated()
    {
        // Arrange
        var command = new {
            name = "Laptop",
            price = 999,
            categoryId = 1
        };

        // Act
        var response = await _client.PostAsJsonAsync("/api/products", command);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        var productId = await response.Content.ReadFromJsonAsync<int>();
        productId.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task CreateProduct_WithInvalidPrice_ReturnsBadRequest()
    {
        // Arrange
        var command = new {
            name = "Laptop",
            price = -10, // 无效价格
            categoryId = 1
        };

        // Act
        var response = await _client.PostAsJsonAsync("/api/products", command);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }
}
```

为什么选择集成测试？

- 端到端测试整个切片
- 验证所有组件协同工作
- 及早发现集成问题
- 更接近用户的真实使用方式

## 基础搭建

**必要的 NuGet 包**

```bash
# MediatR，用于请求/响应模式
dotnet add package MediatR

# FluentValidation，用于验证
dotnet add package FluentValidation
dotnet add package FluentValidation.DependencyInjectionExtensions

# Carter，用于组织 Minimal API（可选）
dotnet add package Carter

# Entity Framework Core
dotnet add package Microsoft.EntityFrameworkCore
dotnet add package Microsoft.EntityFrameworkCore.SqlServer
```

**Program.cs 配置**

```csharp
var builder = WebApplication.CreateBuilder(args);

// 数据库
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("DefaultConnection")));

// MediatR 及管道行为
builder.Services.AddMediatR(cfg =>
{
    cfg.RegisterServicesFromAssembly(typeof(Program).Assembly);
    cfg.AddBehavior(typeof(IPipelineBehavior<,>), typeof(LoggingBehavior<,>));
    cfg.AddBehavior(typeof(IPipelineBehavior<,>), typeof(ValidationBehavior<,>));
});

// FluentValidation
builder.Services.AddValidatorsFromAssemblyContaining<Program>();

// Carter（如果使用的话）
builder.Services.AddCarter();

var app = builder.Build();

app.UseHttpsRedirection();
app.MapCarter(); // 映射所有端点

app.Run();
```

## 常见模式

**模式一：查询功能（只读）**

```csharp
// Features/Products/GetById/GetProduct.cs

public static class GetProduct
{
    public record Query(int Id) : IRequest<Result<ProductDto>>;

    public record ProductDto(int Id, string Name, decimal Price, string CategoryName);

    public class Handler : IRequestHandler<Query, Result<ProductDto>>
    {
        private readonly AppDbContext _db;

        public async Task<Result<ProductDto>> Handle(Query request, CancellationToken ct)
        {
            var product = await _db.Products
                .Where(p => p.Id == request.Id)
                .Select(p => new ProductDto(
                    p.Id,
                    p.Name,
                    p.Price,
                    p.Category.Name
                ))
                .FirstOrDefaultAsync(ct);

            return product != null
                ? Result<ProductDto>.Success(product)
                : Result<ProductDto>.Failure("Product not found");
        }
    }
}
```

要点：

- 使用 `Select` 只投影需要的数据
- 返回 DTO 而不是实体
- 每个查询针对具体用例做优化

**模式二：列表/搜索功能**

```csharp
// Features/Products/List/ListProducts.cs

public static class ListProducts
{
    public record Query(
        int Page = 1,
        int PageSize = 20,
        string? SearchTerm = null,
        int? CategoryId = null
    ) : IRequest<Result<PagedResult<ProductDto>>>;

    public record ProductDto(int Id, string Name, decimal Price);

    public record PagedResult<T>(List<T> Items, int TotalCount, int Page, int PageSize);

    public class Handler : IRequestHandler<Query, Result<PagedResult<ProductDto>>>
    {
        private readonly AppDbContext _db;

        public async Task<Result<PagedResult<ProductDto>>> Handle(
            Query request,
            CancellationToken ct)
        {
            var query = _db.Products.AsQueryable();

            // 应用筛选条件
            if (!string.IsNullOrWhiteSpace(request.SearchTerm))
                query = query.Where(p => p.Name.Contains(request.SearchTerm));

            if (request.CategoryId.HasValue)
                query = query.Where(p => p.CategoryId == request.CategoryId.Value);

            // 获取总数
            var totalCount = await query.CountAsync(ct);

            // 分页
            var items = await query
                .Skip((request.Page - 1) * request.PageSize)
                .Take(request.PageSize)
                .Select(p => new ProductDto(p.Id, p.Name, p.Price))
                .ToListAsync(ct);

            return Result<PagedResult<ProductDto>>.Success(
                new PagedResult<ProductDto>(items, totalCount, request.Page, request.PageSize));
        }
    }
}
```

**模式三：使用领域事件的功能**

```csharp
// Features/Orders/Create/CreateOrder.cs

public static class CreateOrder
{
    public record Command(int CustomerId, List<OrderItemDto> Items) : IRequest<Result<int>>;

    public class Handler : IRequestHandler<Command, Result<int>>
    {
        private readonly AppDbContext _db;
        private readonly IMediator _mediator;

        public async Task<Result<int>> Handle(Command request, CancellationToken ct)
        {
            var order = new Order
            {
                CustomerId = request.CustomerId,
                Status = OrderStatus.Pending,
                CreatedAt = DateTime.UtcNow
            };

            _db.Orders.Add(order);
            await _db.SaveChangesAsync(ct);

            // 发布事件，其他功能可以响应
            await _mediator.Publish(new OrderCreated(order.Id, request.Items), ct);

            return Result<int>.Success(order.Id);
        }
    }
}

// Features/Inventory/ReserveStock/OrderCreatedHandler.cs

public class OrderCreatedHandler : INotificationHandler<OrderCreated>
{
    private readonly AppDbContext _db;

    public async Task Handle(OrderCreated notification, CancellationToken ct)
    {
        // 在自己的功能中更新库存
        foreach (var item in notification.Items)
        {
            var product = await _db.Products.FindAsync(item.ProductId, ct);
            if (product != null)
                product.ReservedStock += item.Quantity;
        }

        await _db.SaveChangesAsync(ct);
    }
}
```

关键点：各功能保持解耦，但可以通过 MediatR 通知来响应彼此的事件。

## 在现有应用中落地

VSA 最大的优势是你今天就可以开始，不需要重写任何代码。

**渐进式采用策略**

第一阶段：共存（第 1-2 个月）

保留原有的分层代码，新功能用切片方式构建。两者可以共存：

```
MyApp/
├── Controllers/          # 旧的分层代码，照常运行
│   ├── ProductsController.cs
│   └── OrdersController.cs
├── Services/             # 旧的分层代码，照常运行
│   ├── ProductService.cs
│   └── OrderService.cs
├── Repositories/         # 旧的分层代码，照常运行
│   └── ProductRepository.cs
├── Features/             # 新的切片，从这里开始！
│   ├── Shipping/
│   │   ├── CalculateRate/
│   │   └── TrackPackage/
│   └── Notifications/
│       └── SendEmail/
```

好处：对现有功能零风险、团队逐步学习 VSA、新功能交付更快、便于回退。

第二阶段：有选择地迁移（第 3-6 个月）

每次迁移一个功能，先从简单的 CRUD 开始：

```
// 第一步：选择一个简单功能
// 优先考虑的候选：
// - 最近新增的功能（较少的历史包袱）
// - 频繁变动的功能
// - 依赖较少的简单 CRUD

// 第二步：创建切片
Features/Products/Archive/ArchiveProduct.cs

// 第三步：充分测试

// 第四步：只有新代码上线后才删除旧代码
```

第三阶段：长期共存（持续进行）

6 个月后的状态：

- 70-80% 基于切片
- 20-30% 仍然是分层架构
- 这完全没问题！

如果旧代码运行正常，不必强制迁移。把精力集中在新功能的切片化开发上。

何时停止迁移：

- 功能逻辑复杂但运行良好
- 迁移成本大于收益
- 功能很少变化
- 团队还没有足够适应

## 常见陷阱（及如何避免）

**1. "Shared"文件夹陷阱**

开始使用 VSA 时最常见的问题：把太多东西塞进 Common 文件夹。

问题：你看到两个功能都要发邮件，就立刻创建了一堆共享代码：

```
Common/
├── Services/
│   └── EmailService.cs
├── DTOs/
│   ├── ProductDto.cs         # 其实是某个功能专用的！
│   └── OrderDto.cs           # 其实也是某个功能专用的！
├── Validators/
│   └── CreateOrderValidator.cs  # 功能专用！
└── Helpers/
    └── (其他所有东西)
```

不知不觉中，`Common` 就变成了垃圾堆，功能之间也因此紧密耦合。

解决方案的核心规则：共享基础设施，复制业务逻辑。

可以共享：

```
Common/
├── Behaviors/              # MediatR 管道（日志、验证）
├── Results/               # 通用 Result<T> 类型
├── Interfaces/
│   ├── IEmailSender.cs    # 外部服务接口
│   └── IFileStorage.cs
└── Extensions/
    └── ValidationExtensions.cs  # 简单的可复用验证规则
```

这些是真正适用于所有功能的横切关注点。

不应共享：

- 功能之间的 DTO（每个功能应有自己的）
- 功能之间的业务逻辑（宁可重复也不要共享）
- 功能专用的验证器
- "Helpers"或"Utilities"文件夹

即使多个功能操作同一个数据库实体，也不意味着它们要共享 DTO：

```csharp
// Data/Entities/Product.cs - 共享的数据库实体
public class Product
{
    public int Id { get; set; }
    public string Name { get; set; }
    public decimal Price { get; set; }
}

// Features/Products/Create/CreateProduct.cs
public record Command(string Name, decimal Price); // 只包含创建所需的字段

// Features/Products/List/ListProducts.cs
public record ProductDto(int Id, string Name, decimal Price); // 跟 Command 不同！

// Features/Products/GetDetails/GetProductDetails.cs
public record DetailedProductDto(
    int Id,
    string Name,
    decimal Price,
    string Description,
    List<ReviewDto> Reviews
); // 完全不同！
```

检查你的 Common 文件夹是否健康：

- 健康的标志：少于 10 个文件、没有业务逻辑、没有功能专用的代码
- 问题的标志：超过 20 个文件、有 Helpers 文件夹、有 DTO、功能严重依赖它

当拿不准时，问自己："这是基础设施还是业务逻辑？"基础设施可以放 Common（也许），业务逻辑一定放在对应的 Feature 里。

**2. 业务逻辑泄露到 Endpoint 中**

错误做法：在 Minimal API 或 Controller 中放 `if/else` 业务规则。

```csharp
// 不要这样做
app.MapPost("/api/products", async (CreateProductRequest request, AppDbContext db) =>
{
    // 业务逻辑跑到 Endpoint 里了！
    if (string.IsNullOrEmpty(request.Name))
        return Results.BadRequest("Name is required");

    if (request.Price <= 0)
        return Results.BadRequest("Price must be positive");

    var product = new Product { ... };
    db.Products.Add(product);
    await db.SaveChangesAsync();

    return Results.Created(...);
});
```

正确做法：Endpoint 应该是一个薄包装层。它唯一的职责是接收请求然后调用 `mediator.Send()`。

```csharp
// 应该这样做
app.MapPost("/api/products", async (CreateProduct.Command request, IMediator mediator) =>
{
    var result = await mediator.Send(request);
    return result.IsSuccess ? Results.Created(...) : Results.BadRequest(result.Error);
});
```

所有业务逻辑和验证都留在 Handler 和 Validator 中。

**3. 创建"上帝切片"**

错误做法：创建一个叫 `ProductManagement` 的切片来处理创建、更新、删除、列表、搜索、导出、导入。

```
Features/
└── Products/
    └── ProductManagement/     # "上帝切片"
        └── ProductManager.cs   # 2000行代码
```

正确做法：拆分！每个用例都是独立的切片。

```
Features/
└── Products/
    ├── Create/               # 单一职责
    ├── Update/               # 单一职责
    ├── Delete/               # 单一职责
    ├── List/                 # 单一职责
    └── Search/               # 单一职责
```

**4. 过早提取公共代码**

错误做法：看到类似的代码出现两次就立刻提取到 Common。

```
// 两个功能有类似的验证
// Features/Products/Create - 验证价格
// Features/Orders/Create - 验证总价

// 不要立刻创建：
// Common/Validators/MoneyValidator.cs
```

正确做法：等到第三次使用时再提取（三次法则）。这些代码可能会各自变化：

- Products 可能需要按分类设置不同的价格规则
- Orders 可能需要区分批发和零售的不同规则

复制粘贴两次，第三次再提取。

## 适用场景

适合使用 VSA 的场景：

- CRUD 密集型应用：电商、CMS、管理后台
- 微服务：每个服务天然地按功能组织
- 拥有大量端点的 API：方便定位和修改特定操作
- 重视开发速度的团队：更少的仪式感 = 更快的交付
- 演进式系统：当你不确定系统会如何发展时

需要考虑其他方案的场景：

- 复杂的共享领域逻辑：需要聚合根等重度领域建模
- 频繁替换基础设施：多数据库提供商的切换需求
- 构建框架或类库：可复用性比功能开发速度更重要

## 关键要点

1. **按功能组织，而非按层级**：一个功能就是一个文件夹
2. **高内聚、低耦合**：功能自包含且互相独立
3. **最少的抽象**：只在确实存在共享行为时才创建
4. **渐进式采用**：今天就用切片构建新功能，逐步迁移旧代码
5. **共享基础设施，复制业务逻辑**：保持 Common 文件夹精简
6. **MediatR Behaviors 处理横切关注点**：验证和日志自动完成
7. **集成测试提供最高信心**：端到端测试完整的切片
