---
pubDatetime: 2024-06-07
tags: []
source: https://stefandjokic.tech/posts/the-service-collection-extension-pattern
author:
title: The ServiceCollection Extension Pattern
description: The IServiceCollection interface represents a contract for a collection of service descriptors, providing an abstraction to add, remove, and retrieve services.
---

# The ServiceCollection Extension Pattern

> ## 摘要
>
> **IServiceCollection 接口**代表了一系列服务描述符的契约，提供了一个用于添加、删除和检索服务的抽象。

---

### 背景

##### 在 .NET 环境中，依赖注入（DI）是一种基本的技术，帮助我们创建灵活、可测试和松耦合的代码。

##### 它是控制反转（IoC）原则的一个实例，创建对象的控制由容器或框架管理，而不是由类本身管理。

##### **IServiceCollection 接口**代表了一系列服务描述符的契约，提供了一个用于添加、删除和检索服务的抽象。

##### 这个接口在 Program.cs 类中变得非常重要。

##### 在这里，我们注入了应用程序所需的所有必要服务。

### ServiceCollection 扩展模式

##### 在较大的应用程序中，Program.cs 可能会变得臃肿和混乱。

##### 为了避免这种情况，我们可以利用一种称为**ServiceCollection 扩展模式**的模式。

##### 这种模式让我们将服务注册逻辑封装到单独的静态类中，提供一个更有条理和可读的结构。

##### 这种模式涉及在 **IServiceCollection 接口**上创建扩展方法。

##### 让我们看一个例子：

```csharp

public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddCustomServices(
        this IServiceCollection services)
    {
        services.AddScoped<IMyService, MyService>();
        services.AddSingleton<IOtherService, OtherService>();

        // ... 其他服务

        return services;
    }
}
```

##### 然后在你的 Program.cs 文件中，你可以这样利用这些扩展方法：

```csharp

builder.Services.AddCustomServices();
```

### 真实世界的例子

##### 我们可以进一步使用这种模式对我们的服务进行分类，例如，为不同类型或层次的服务创建不同的扩展方法。

##### 让我们考虑一个使用 Entity Framework Core 进行数据访问，Identity 进行身份验证和授权，并且还需要配置 CORS（跨域资源共享）的应用程序。

##### 以下是你在这种场景下如何应用 ServiceCollection 扩展模式的示例。

##### 数据库：

```csharp

public static IServiceCollection AddDatabase(
    this IServiceCollection services,
    string connectionString)
{
    services.AddDbContext<MyDbContext>(options => options.UseSqlServer(connectionString));

    return services;
}
```

##### 身份验证：

```csharp

public static IServiceCollection AddIdentityServices(
    this IServiceCollection services)
{
    services.AddIdentity<ApplicationUser, IdentityRole>()
        .AddEntityFrameworkStores<MyDbContext>()
        .AddDefaultTokenProviders();

    return services;
}
```

##### JWT 身份验证：

```csharp

public static IServiceCollection AddJwtAuthentication(
    this IServiceCollection services, IConfiguration configuration)
{
    var jwtSettings = configuration.GetSection("JwtSettings");
    var key = Encoding.ASCII.GetBytes(jwtSettings.GetValue<string>("Secret"));

    services.AddAuthentication(options =>
    {
        options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
        options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
    })
    .AddJwtBearer(options =>
    {
        options.RequireHttpsMetadata = false;
        options.SaveToken = true;
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(key),
            ValidateIssuer = false,
            ValidateAudience = false
        };
    });

    return services;
}
```

##### Cors 策略：

```csharp

public static IServiceCollection AddCorsPolicy(
    this IServiceCollection services,
    string policyName,
    string[] allowedOrigins)
{
    services.AddCors(options =>
    {
        options.AddPolicy(policyName,
            builder => builder.WithOrigins(allowedOrigins)
                     .AllowAnyMethod()
                     .AllowAnyHeader()
                     .AllowCredentials());
    });

    return services;
}
```

##### 然后在你的 Program.cs 文件中，你可以这样利用这些扩展方法：

```csharp

builder.Services.AddDatabase(Configuration.GetConnectionString("DefaultConnection"));
builder.Services.AddIdentityServices();
builder.Services.AddJwtAuthentication(Configuration);
builder.Services.AddCorsPolicy("MyPolicy", new[] { "http://example.com" });

// ... 其他配置
```

### 为什么我们要考虑使用它？

#### 1\. 组织和可读性

##### 在一个有无数服务的大型应用程序中，Program.cs 可能会迅速变得臃肿和混乱。

##### 这让开发人员难以一目了然地理解发生了什么。

##### 这提高了代码的可读性并易于理解，这在团队环境中特别有价值。

#### 2\. 封装

##### ServiceCollection 扩展模式遵循封装原则，这是面向对象编程的核心信条。

##### 封装使我们能够将服务注册的复杂性隐藏在一组方法后面。

##### 这将应用程序的其他部分与这些操作的复杂性屏蔽开来，并提供一个干净简单的接口来注册服务。

#### 3\. 可维护性

##### 应用程序随着时间推移必然会发展。

##### 你开始使用的服务可能不会是你结束时使用的服务。使用ServiceCollection 扩展模式，可以更容易地修改、添加或删除服务注册。

##### 由于你已经将服务注册逻辑进行了逻辑上的分隔，所以你可以在不必费力查找可能很大的 Program.cs 文件的情况下找到并更改特定的组。

#### 4\. 可重用性

##### 如果你在多个项目中使用相同的一组服务，可以在不同的应用程序中重用你的扩展方法。这减少了重复代码，节省时间并减少错误的可能性。

### 总结

##### ServiceCollection 扩展模式是保持 Program.cs 整洁和可维护的宝贵工具，特别适用于大型应用程序。

##### 通过将服务注册逻辑封装到单独的方法中，我们可以改善服务注册代码的组织和可读性。

##### 今天就介绍到这里。
