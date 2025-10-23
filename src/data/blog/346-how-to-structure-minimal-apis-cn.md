---
pubDatetime: 2025-05-31
tags: [".NET", "ASP.NET Core"]
slug: how-to-structure-minimal-apis-cn
source: https://www.milanjovanovic.tech/blog/how-to-structure-minimal-apis
title: .NET Minimal APIs 项目结构最佳实践：从入门到进阶
description: 面向.NET开发者，深入解析Minimal APIs的项目结构优化，从简单实现到模块化扩展，助力高效API开发。
---

# .NET Minimal APIs 项目结构最佳实践：从入门到进阶

## 引言：Minimal APIs 的流行与挑战

自.NET 6 推出 Minimal APIs 以来，这一轻量级的API开发方式迅速受到后端开发者的关注。无需传统Controller层的“繁文缛节”，只需几行代码就能定义REST接口，开发体验极为丝滑。但伴随着项目规模增长，许多开发者遇到一个现实问题：**Minimal APIs 的项目结构该如何设计，才能既保持简洁，又易于维护？**

今天我们就以一线技术博主[Milan Jovanović](https://www.milanjovanovic.tech/)的经验为例，系统梳理 Minimal APIs 的结构化最佳实践，帮助你在新旧API架构之间优雅转身。

---

## Minimal APIs 快速入门

首先，我们来看一个最基础的 Minimal API 示例：

```csharp
var builder = WebApplication.CreateBuilder(args);

// 省略EF和服务配置...

var app = builder.Build();

app.MapGet("/products", async (AppDbContext dbContext) =>
{
    return Results.Ok(await dbContext.Products.ToListAsync());
});

app.MapPost("/products", async (Product product, AppDbContext dbContext) =>
{
    dbContext.Products.Add(product);
    await dbContext.SaveChangesAsync();
    return Results.Ok(product);
});

app.Run();
```

通过`MapGet`和`MapPost`等扩展方法，我们很快就能实现REST风格的接口。依赖注入和异步编程的支持，也让业务代码自然流畅。

---

## 隐患初现：Minimal API 难维护之痛

如果你的API只有三五个端点，这样写当然没问题。但随着业务增长，所有接口都堆在`Program.cs`文件里，很快会变成难以维护的“意大利面”代码。常见的痛点有：

- 代码量激增，逻辑难以聚合
- 各类端点分组混乱，业务边界模糊
- 新人接手成本高、易误改

**那么，如何让Minimal APIs也拥有优雅可维护的结构？**

---

## 方法一：扩展方法分组，让结构更清晰

一种简单但有效的方式，是利用C#扩展方法为每个业务领域分组API端点。例如：

```csharp
public static class ProductsModule
{
    public static void RegisterProductsEndpoints(this IEndpointRouteBuilder endpoints)
    {
        endpoints.MapGet("/products", ...);
        endpoints.MapPost("/products", ...);
    }
}
```

然后在主程序中注册：

```csharp
app.RegisterProductsEndpoints();
```

这样，每个模块的端点都收敛到独立文件，结构更清晰。缺点是每加一个模块，都需要手动注册，维护时也要注意同步。

---

## 方法二：Carter库加持，模块化你的Minimal API

如果你想进一步解耦、自动化注册端点，可以试试[Carter](https://github.com/CarterCommunity/Carter)这个开源库。Carter鼓励你用面向模块的方式组织代码：

```csharp
public class ProductsModule : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        app.MapGet("/products", ...);
        app.MapPost("/products", ...);
    }
}
```

只需在服务注册和启动时加入Carter：

```csharp
builder.Services.AddCarter();
app.MapCarter();
```

这样每次新建模块，只需实现`ICarterModule`，Carter会自动发现并注册所有端点，无需手动调用。

---

## 实战建议：何时选择Minimal APIs？

Milan Jovanović认为：  
Minimal APIs 经过数代进化，非常适合**微服务**和**中小型应用**。如果你的系统不大、功能单一，希望快速上线、易于调整，Minimal APIs绝对值得一试。对于超大型项目或多团队协作场景，则建议继续采用传统Controller+分层架构，保证可扩展性与团队协作效率。

---

## 总结与互动

Minimal APIs极大降低了API开发门槛，但**项目结构设计不能“最小化”**！通过合理分组、模块化、或引入第三方库如Carter，你可以让极简代码也具备优雅可维护性。

👀 **你在实际项目中遇到过Minimal APIs结构混乱的问题吗？有无其他好用的组织方式？**  
欢迎在评论区分享你的心得，也可以点赞、转发本文，让更多.NET开发者受益！
