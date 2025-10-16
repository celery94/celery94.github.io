---
pubDatetime: 2025-05-31
tags: [".NET", "ASP.NET Core"]
slug: auto-register-minimal-apis-aspnetcore
source: https://www.milanjovanovic.tech/blog/automatically-register-minimal-apis-in-aspnetcore
title: ASP.NET Core Minimal API 自动注册实践：优雅、高效、可维护的项目架构
description: 深度解析如何利用反射与抽象自动注册ASP.NET Core Minimal API，提升代码可维护性，减少重复劳动，并结合实用图例和扩展方案，助力中高级后端开发者构建高质量API项目。
---

# ASP.NET Core Minimal API 自动注册实践：优雅、高效、可维护的项目架构

## 引言

在ASP.NET Core项目日益壮大的今天，Minimal API凭借其轻量、高效的特性，成为了众多后端开发者的新宠。但随着API数量增多，传统的 `app.MapGet`、`app.MapPost` 等手动注册方式不但繁琐，还让项目维护变得异常头疼。有没有办法让API注册变得自动化、结构化，并且便于团队协作和长期维护呢？🤔

本篇文章将带你深入探索如何通过简单的抽象和反射机制，实现Minimal API的自动注册。无论你是追求极致架构之美的中高级开发者，还是在实际项目中饱受“重复劳动”困扰的后端同仁，这份指南都值得收藏！

## 为什么要自动注册Minimal API？

手动注册每个API端点会导致什么？

- **重复代码**，不利于后期维护和扩展。
- `Program.cs` 或入口文件变得臃肿。
- 团队协作时，容易遗漏或出错。

虽然我们可以借助扩展方法来分组管理，但本质上还是把控制器的“重”搬到了Minimal API里，缺乏灵活性。那么，有没有更优雅的方式呢？答案就是——每个Endpoint组件化，再用自动化机制批量注册！

## 设计理念：以“端点”为切片

每个Minimal API Endpoint都应该被视为独立的功能单元，这与[Vertical Slice Architecture](https://www.milanjovanovic.tech/blog/vertical-slice-architecture)的思想不谋而合。这样做能让业务逻辑分割更清晰，代码可维护性提升一个维度。

**核心抽象：IEndpoint**

我们定义一个接口，每个Endpoint只需实现这个接口即可：

```csharp
public interface IEndpoint
{
    void MapEndpoint(IEndpointRouteBuilder app);
}
```

举例，一个获取粉丝统计信息的Endpoint如下：

```csharp
public class GetFollowerStats : IEndpoint
{
    public void MapEndpoint(IEndpointRouteBuilder app)
    {
        app.MapGet("users/{userId}/followers/stats", async (
            Guid userId,
            ISender sender) =>
        {
            var query = new GetFollowerStatsQuery(userId);

            Result<FollowerStatsResponse> result = await sender.Send(query);

            return result.Match(Results.Ok, CustomResults.Problem);
        })
        .WithTags(Tags.Users);
    }
}
```

> ⛔ **注意：** 每个实现类建议只注册一个端点，这样结构才干净、解耦。

## 反射魔法：自动发现与依赖注入

通过反射，我们能在程序启动时自动扫描所有实现了 `IEndpoint` 接口的类，并把它们加入依赖注入容器。这样，无需手动new对象或硬编码类型，系统会自动帮我们“找人办事”。

```csharp
public static IServiceCollection AddEndpoints(
    this IServiceCollection services,
    Assembly assembly)
{
    ServiceDescriptor[] serviceDescriptors = assembly
        .DefinedTypes
        .Where(type => type is { IsAbstract: false, IsInterface: false } &&
                       type.IsAssignableTo(typeof(IEndpoint)))
        .Select(type => ServiceDescriptor.Transient(typeof(IEndpoint), type))
        .ToArray();

    services.TryAddEnumerable(serviceDescriptors);

    return services;
}
```

在 `Program.cs` 只需一行：

```csharp
builder.Services.AddEndpoints(typeof(Program).Assembly);
```

## 全自动注册API：一步到位！

接下来，通过一个扩展方法，批量将所有Endpoint注册到Web应用中。如果有需要，比如添加统一的路由前缀、认证、API版本控制，也都可以在这里集中处理。

```csharp
public static IApplicationBuilder MapEndpoints(
    this WebApplication app,
    RouteGroupBuilder? routeGroupBuilder = null)
{
    IEnumerable<IEndpoint> endpoints = app.Services
        .GetRequiredService<IEnumerable<IEndpoint>>();

    IEndpointRouteBuilder builder =
        routeGroupBuilder is null ? app : routeGroupBuilder;

    foreach (IEndpoint endpoint in endpoints)
    {
        endpoint.MapEndpoint(builder);
    }

    return app;
}
```

示例整合（支持API版本前缀）：

```csharp
WebApplicationBuilder builder = WebApplication.CreateBuilder(args);

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddEndpoints(typeof(Program).Assembly);

WebApplication app = builder.Build();

ApiVersionSet apiVersionSet = app.NewApiVersionSet()
    .HasApiVersion(new ApiVersion(1))
    .ReportApiVersions()
    .Build();

RouteGroupBuilder versionedGroup = app
    .MapGroup("api/v{version:apiVersion}")
    .WithApiVersionSet(apiVersionSet);

app.MapEndpoints(versionedGroup);

app.Run();
```

## 性能与扩展思考

✨ 这种自动化方案极大地提升了开发效率和代码可维护性，但要注意：

- **反射**虽然强大，但可能影响应用启动时的性能。如果项目极大，可考虑使用**Source Generator**提前生成注册代码。
- 市场上还有其他成熟方案值得参考，比如 [FastEndpoints](https://fast-endpoints.com/) 和 [Carter](https://github.com/CarterCommunity/Carter)。

## 结语

通过本篇内容，你不仅学会了如何“低成本”地自动注册Minimal API，更能为你的ASP.NET Core项目带来结构上的跃迁。自动化≠偷懒，而是把精力聚焦于核心业务，让代码优雅且高可维护！
