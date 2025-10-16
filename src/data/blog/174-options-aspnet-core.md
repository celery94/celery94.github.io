---
pubDatetime: 2024-10-15
tags: [".NET", "ASP.NET Core"]
source: ""
author: Celery Liu
title: 在 ASP.NET Core 中使用 Options Pattern 配置
description: 在 ASP.NET Core 中使用 Options Pattern 配置
---

# 在 ASP.NET Core 中使用 Options Pattern 配置

在 ASP.NET Core 中，**Options Pattern** 提供了一种优雅的方式来管理应用程序中的配置项。通过将配置文件中的值映射到强类型的类，我们可以轻松地在代码中使用这些配置项，并利用依赖注入将其注入到服务或控制器中。本文将详细介绍如何在 ASP.NET Core 中设置和使用 Options Pattern，并确保配置项具有默认值。

## 1. **Options 类应该放在哪一层？**

在遵循 **Clean Architecture** 和 **DDD** 原则的项目中，`Options` 类通常应该放置在 **Infrastructure 层** 或 **Application 层**：

- **Infrastructure 层**：如果 `Options` 类代表与基础设施相关的配置，例如数据库连接或外部 API 的配置，应该放在基础设施层。
- **Application 层**：如果配置项与业务逻辑相关，例如影响某些业务操作的全局配置，则可以放在应用层。

通常，建议将大部分配置相关的 `Options` 类放置在 **Infrastructure 层**，以保持业务逻辑与外部配置的解耦。

## 2. **在 Application 层使用 Options Pattern**

### **配置 Options 类**

假设我们有一个用于管理资产的配置类 `AssetManagementOptions`：

```csharp
public class AssetManagementOptions
{
    public string DefaultCategory { get; set; }
    public int MaxAssetsPerPage { get; set; }
}
```

在 `Startup.cs` 或 `Program.cs` 中，通过 `IConfiguration` 绑定配置项：

```csharp
public void ConfigureServices(IServiceCollection services)
{
    services.Configure<AssetManagementOptions>(Configuration.GetSection("AssetManagement"));
}
```

### **在服务中使用 Options**

通过依赖注入，我们可以在服务中使用 `AssetManagementOptions`：

```csharp
public class AssetService
{
    private readonly AssetManagementOptions _options;

    public AssetService(IOptions<AssetManagementOptions> options)
    {
        _options = options.Value;
    }

    public void PerformOperation()
    {
        var defaultCategory = _options.DefaultCategory;
        var maxAssetsPerPage = _options.MaxAssetsPerPage;
    }
}
```

## 3. **为 Options 设置默认值**

为了确保某些配置项未被配置时仍有默认值，我们可以通过以下几种方式为 Options 设置默认值：

### **1. 在 Options 类中设置默认值**

可以直接在 `Options` 类的属性上设置默认值：

```csharp
public class AssetManagementOptions
{
    public string DefaultCategory { get; set; } = "General";
    public int MaxAssetsPerPage { get; set; } = 10;
}
```

### **2. 在 `Configure<TOptions>` 中设置默认值**

我们也可以在 `Startup.cs` 中使用 `Configure<TOptions>` 方法来设置默认值：

```csharp
services.Configure<AssetManagementOptions>(options =>
{
    options.DefaultCategory = "General";
    options.MaxAssetsPerPage = 10;
});
```

### **3. 自定义 IConfigureOptions**

可以实现 `IConfigureOptions<T>` 接口来设置默认值：

```csharp
public class AssetManagementOptionsSetup : IConfigureOptions<AssetManagementOptions>
{
    public void Configure(AssetManagementOptions options)
    {
        options.DefaultCategory = "General";
        options.MaxAssetsPerPage = 10;
    }
}
```

## 4. **从 IServiceCollection 获取 Options**

在某些情况下，你可能希望在 `ConfigureServices` 方法中直接从 `IServiceCollection` 获取 Options。以下是步骤：

```csharp
var serviceProvider = services.BuildServiceProvider();
var assetManagementOptions = serviceProvider.GetService<IOptions<AssetManagementOptions>>();
```

## 5. **总结**

通过 Options Pattern 和依赖注入，ASP.NET Core 提供了一种灵活且易于维护的方式来管理应用配置。无论是简单的配置管理还是复杂的业务逻辑，都可以使用 Options Pattern 提供的强类型配置类进行处理，同时通过默认值机制确保应用程序的鲁棒性。
