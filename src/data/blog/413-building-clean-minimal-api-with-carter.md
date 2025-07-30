---
pubDatetime: 2025-07-30
tags: [".NET", "Carter", "API", "Minimal API", "FluentValidation", "Mapster"]
slug: building-clean-minimal-api-with-carter
source: https://thecodeman.net/posts/building-clean-minimal-api-with-carter
title: 构建干净且极简的 .NET API —— 探索 Carter 实践
description: 深入介绍 Carter 如何帮助 .NET 8+ 项目构建结构清晰、易维护、可扩展的极简 API，包含项目实战与开发心得，适合希望提升API组织和代码整洁度的开发者。
---

---

# 构建干净且极简的 .NET API —— 探索 Carter 实践

随着 .NET 的不断发展，Minimal API（极简 API）因其轻量、灵活的特性而广受欢迎。然而，项目一旦变得庞大，Minimal API 也会面临路由分散、依赖注入重复、验证逻辑侵入等痛点。Carter 作为社区极具口碑的 API 组织框架，恰好为这些问题提供了解决方案。

## 为什么选择 Carter？

Minimal API 非常适合小型项目，但当业务复杂后，问题随之而来：路由分布于多个文件，依赖注入逻辑冗余，验证与映射逻辑夹杂在路由中，单元测试也变得不便。Carter 以模块化方式，将相关端点聚合于“模块”中，做到结构清晰、可测试且易于扩展，极大提升了可维护性。

Carter 本质上是 Minimal API 的增强版，并未引入传统 MVC 控制器的繁琐，依然保持极致轻量与灵活。

## 如何在 .NET 8+ 项目中集成 Carter

Carter 的上手非常简单，仅需通过 NuGet 安装即可：

```bash
dotnet add package Carter
```

## 项目结构设计

以一个典型的“产品管理”API为例，包含产品创建与查询，并配合 FluentValidation 做参数校验、Mapster 做 DTO-实体映射。推荐的项目结构如下：

```
MyApi/
├── Program.cs
├── Endpoints/
│   └── ProductModule.cs
├── Models/
│   ├── Product.cs
│   └── ProductDto.cs
├── Validators/
│   └── CreateProductDtoValidator.cs
```

### 核心代码详解

#### 模型定义（Models/Product.cs & ProductDto.cs）

```csharp
namespace MyApi.Models;
public class Product
{
    public Guid Id { get; set; }
    public string Name { get; set; } = default!;
    public decimal Price { get; set; }
}

public record CreateProductDto(string Name, decimal Price);
```

#### 参数验证（Validators/CreateProductDtoValidator.cs）

借助 FluentValidation，实现参数的约束校验：

```csharp
using FluentValidation;
using MyApi.Models;
namespace MyApi.Validators;
public class CreateProductDtoValidator : AbstractValidator<CreateProductDto>
{
    public CreateProductDtoValidator()
    {
        RuleFor(x => x.Name).NotEmpty().MaximumLength(100);
        RuleFor(x => x.Price).GreaterThan(0);
    }
}
```

#### Carter 模块化端点（Endpoints/ProductModule.cs）

Carter 的精髓在于“模块”（Module），每个模块实现 `ICarterModule` 接口，将所有相关 API 聚合于一处。服务注入与逻辑处理一气呵成：

```csharp
using Carter;
using FluentValidation;
using Mapster;
using Microsoft.AspNetCore.Http.HttpResults;
using MyApi.Models;
namespace MyApi.Endpoints;
public class ProductModule : ICarterModule
{
    private static readonly List<Product> _products = [];
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        app.MapGet("/products", () => _products);

        app.MapPost("/products", async (
            CreateProductDto dto,
            IValidator<CreateProductDto> validator) =>
        {
            var validationResult = await validator.ValidateAsync(dto);
            if (!validationResult.IsValid)
            {
                var errors = validationResult.Errors
                    .ToDictionary(e => e.PropertyName, e => e.ErrorMessage);
                return Results.BadRequest(errors);
            }
            var product = dto.ToProduct<Product>();
            product.Id = Guid.NewGuid();
            _products.Add(product);
            return Results.Created($"/products/{product.Id}", product);
        });
    }
}
```

#### 程序入口（Program.cs）

只需一句 `app.MapCarter()`，所有模块自动注册，Startup 代码极其精简：

```csharp
using Carter;
using FluentValidation;
using MyApi.Models;
using MyApi.Validators;
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddCarter();
builder.Services.AddScoped<IValidator<CreateProductDto>, CreateProductDtoValidator>();
var app = builder.Build();
app.MapCarter(); // 自动映射所有 Carter 模块
app.Run();
```

## Carter 带来的开发体验提升

Carter 最打动开发者的，是其带来的结构整洁与模块解耦。每一个业务模块有自己的归属，依赖注入、校验、日志等可自由注入端点，完全兼容 Vertical Slice、CQRS、Minimal API 等现代架构风格。

它几乎没有性能开销，所有路由最终都是 Minimal API 格式，无需担心扩展性与测试性。更重要的是，测试 Carter 模块非常直观，没有黑魔法或繁琐的反射机制。

无论你用的是 FluentValidation、Mapster、MediatR、Dapper 还是 EF Core，Carter 都能自然兼容，无额外侵入。

## 实践中的注意事项与对比

Carter 虽然轻巧灵活，但也有需要权衡的地方：

- 社区体量和文档丰富度暂不如 MVC 主流框架，部分问题需参考源码或社区 issue。
- 路由全部手动定义，缺少 `[HttpGet]`、`[Route]` 这类注解，部分开发者需要时间适应。
- 复杂模型绑定（如 `[FromBody]`、`[FromQuery]`）没有自动属性，完全沿用 Minimal API 的绑定方式。
- 项目结构需自行设计，缺乏强制规范。
- 诸如 `[Authorize]`、模型验证过滤器等属性需开发者主动集成。

总体来看，Carter 更适合对 API 结构有追求，且不怕动手组织项目的开发者。如果你已经厌倦了 Program.cs 中冗长混乱的路由定义，或者 MVC Controller 无法满足你的精简需求，Carter 无疑是极佳的选择。

## 总结与建议

Carter 在极简 API 的基础上，恰到好处地引入了结构化与模块化，既不会回到冗长 Controller 的世界，也保留了最灵活的 API 设计体验。对于需要长期演进、业务逐步复杂的 .NET 项目，Carter 可以帮助你优雅扩展、保持项目的整洁可控。

如需进一步深入，建议结合 Vertical Slice、CQRS 等架构实践，发挥 Carter 的最大威力。如果你正在苦恼于 Minimal API 失控的项目结构，不妨尝试 Carter —— 或许你会爱上那种“代码变干净了”的感觉。
