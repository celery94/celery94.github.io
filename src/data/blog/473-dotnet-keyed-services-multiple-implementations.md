---
pubDatetime: 2025-10-06
title: .NET Keyed Services：优雅解决同接口多实现的注册与选择
description: 深入探讨.NET 8引入的Keyed Services特性，通过实际案例展示如何优雅地注册和使用同一接口的多个实现，告别繁琐的工厂模式和条件判断。
tags: [".NET", "依赖注入", "设计模式", "最佳实践"]
slug: dotnet-keyed-services-multiple-implementations
---

在.NET开发中，我们经常会遇到这样的场景：同一个接口有多个不同的实现，而我们需要在运行时根据具体情况选择使用哪一个。传统的解决方案往往涉及复杂的工厂模式或大量的条件判断逻辑。而.NET 8引入的Keyed Services特性为这个常见问题提供了优雅的解决方案。

## 问题场景：多实现选择的困境

假设你正在构建一个文件存储服务，需要支持两种存储方式：

1. 本地磁盘存储：适用于开发环境或小规模应用
2. 云存储服务：适用于生产环境或需要高可用性的场景

这两种实现都遵循相同的接口`IStorageService`，但在不同的业务场景下，我们需要使用不同的实现。传统的做法可能是这样：

```csharp
// 定义统一的存储接口
public interface IStorageService
{
    Task<string> SaveFileAsync(Stream fileStream, string fileName);
    Task<Stream> GetFileAsync(string fileName);
    Task DeleteFileAsync(string fileName);
}

// 本地存储实现
public class LocalStorageService : IStorageService
{
    private readonly string _basePath;

    public LocalStorageService(IConfiguration configuration)
    {
        _basePath = configuration["Storage:LocalPath"] ?? "./uploads";
    }

    public async Task<string> SaveFileAsync(Stream fileStream, string fileName)
    {
        var fullPath = Path.Combine(_basePath, fileName);
        Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);

        using var fileWrite = File.Create(fullPath);
        await fileStream.CopyToAsync(fileWrite);

        return fullPath;
    }

    public async Task<Stream> GetFileAsync(string fileName)
    {
        var fullPath = Path.Combine(_basePath, fileName);
        return File.OpenRead(fullPath);
    }

    public async Task DeleteFileAsync(string fileName)
    {
        var fullPath = Path.Combine(_basePath, fileName);
        if (File.Exists(fullPath))
        {
            File.Delete(fullPath);
        }
    }
}

// 云存储实现
public class CloudStorageService : IStorageService
{
    private readonly string _connectionString;
    private readonly string _containerName;

    public CloudStorageService(IConfiguration configuration)
    {
        _connectionString = configuration["Storage:CloudConnectionString"]!;
        _containerName = configuration["Storage:ContainerName"] ?? "files";
    }

    public async Task<string> SaveFileAsync(Stream fileStream, string fileName)
    {
        // Azure Blob Storage 或 AWS S3 实现
        // 这里简化示例
        var blobClient = new BlobClient(_connectionString, _containerName, fileName);
        await blobClient.UploadAsync(fileStream, overwrite: true);

        return blobClient.Uri.ToString();
    }

    public async Task<Stream> GetFileAsync(string fileName)
    {
        var blobClient = new BlobClient(_connectionString, _containerName, fileName);
        var response = await blobClient.DownloadAsync();
        return response.Value.Content;
    }

    public async Task DeleteFileAsync(string fileName)
    {
        var blobClient = new BlobClient(_connectionString, _containerName, fileName);
        await blobClient.DeleteIfExistsAsync();
    }
}
```

### 传统解决方案的局限性

在没有Keyed Services之前,我们通常需要采用以下几种方式之一：

#### 方案一：使用工厂模式

```csharp
public interface IStorageServiceFactory
{
    IStorageService GetStorageService(string storageType);
}

public class StorageServiceFactory : IStorageServiceFactory
{
    private readonly IServiceProvider _serviceProvider;

    public StorageServiceFactory(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public IStorageService GetStorageService(string storageType)
    {
        return storageType.ToLower() switch
        {
            "local" => _serviceProvider.GetService<LocalStorageService>()!,
            "cloud" => _serviceProvider.GetService<CloudStorageService>()!,
            _ => throw new ArgumentException($"Unknown storage type: {storageType}")
        };
    }
}

// 注册服务
services.AddScoped<LocalStorageService>();
services.AddScoped<CloudStorageService>();
services.AddScoped<IStorageServiceFactory, StorageServiceFactory>();

// 使用
public class DocumentService
{
    private readonly IStorageServiceFactory _storageFactory;

    public DocumentService(IStorageServiceFactory storageFactory)
    {
        _storageFactory = storageFactory;
    }

    public async Task SaveDocumentAsync(Stream content, string fileName, bool useCloud)
    {
        var storageService = _storageFactory.GetStorageService(useCloud ? "cloud" : "local");
        await storageService.SaveFileAsync(content, fileName);
    }
}
```

这种方式的问题在于：

- 需要创建额外的工厂接口和实现类
- 工厂内部包含字符串匹配逻辑，容易出错
- 代码冗长，增加了维护成本

#### 方案二：注入IEnumerable并手动筛选

```csharp
// 注册所有实现
services.AddScoped<IStorageService, LocalStorageService>();
services.AddScoped<IStorageService, CloudStorageService>();

// 使用时手动筛选
public class DocumentService
{
    private readonly IEnumerable<IStorageService> _storageServices;

    public DocumentService(IEnumerable<IStorageService> storageServices)
    {
        _storageServices = storageServices;
    }

    public async Task SaveDocumentAsync(Stream content, string fileName, bool useCloud)
    {
        // 这种方式需要额外的类型检查或标记接口
        var storageService = useCloud
            ? _storageServices.OfType<CloudStorageService>().First()
            : _storageServices.OfType<LocalStorageService>().First();

        await storageService.SaveFileAsync(content, fileName);
    }
}
```

这种方式的缺点：

- 依赖于具体类型，失去了接口抽象的优势
- 运行时类型检查容易出错
- 代码不够优雅和直观

## Keyed Services：优雅的解决方案

.NET 8引入的Keyed Services特性允许我们在注册服务时为每个实现指定一个键（key），然后在需要时通过键来获取特定的实现。这种方式简洁、类型安全，且不需要额外的工厂代码。

### 基础使用方法

使用Keyed Services只需要三个简单步骤：

#### 步骤1：使用键注册服务

```csharp
// Program.cs 或 Startup.cs
var builder = WebApplication.CreateBuilder(args);

// 使用键注册同一接口的不同实现
builder.Services.AddKeyedScoped<IStorageService, LocalStorageService>("local");
builder.Services.AddKeyedScoped<IStorageService, CloudStorageService>("cloud");
```

#### 步骤2：通过FromKeyedServices特性注入

```csharp
public class DocumentService
{
    private readonly IStorageService _localStorage;
    private readonly IStorageService _cloudStorage;

    public DocumentService(
        [FromKeyedServices("local")] IStorageService localStorage,
        [FromKeyedServices("cloud")] IStorageService cloudStorage)
    {
        _localStorage = localStorage;
        _cloudStorage = cloudStorage;
    }

    public async Task SaveDocumentAsync(Stream content, string fileName, bool useCloud)
    {
        var storageService = useCloud ? _cloudStorage : _localStorage;
        await storageService.SaveFileAsync(content, fileName);
    }
}
```

#### 步骤3：在需要时选择使用

现在你可以根据业务逻辑灵活选择使用哪个实现，而不需要任何工厂代码或条件判断。

### 在控制器中使用Keyed Services

在ASP.NET Core的控制器中，我们也可以轻松使用Keyed Services：

```csharp
[ApiController]
[Route("api/[controller]")]
public class FilesController : ControllerBase
{
    private readonly IStorageService _localStorage;
    private readonly IStorageService _cloudStorage;

    public FilesController(
        [FromKeyedServices("local")] IStorageService localStorage,
        [FromKeyedServices("cloud")] IStorageService cloudStorage)
    {
        _localStorage = localStorage;
        _cloudStorage = cloudStorage;
    }

    [HttpPost("upload")]
    public async Task<IActionResult> UploadFile(
        IFormFile file,
        [FromQuery] string storageType = "local")
    {
        var storageService = storageType.ToLower() switch
        {
            "cloud" => _cloudStorage,
            _ => _localStorage
        };

        using var stream = file.OpenReadStream();
        var path = await storageService.SaveFileAsync(stream, file.FileName);

        return Ok(new { FilePath = path, StorageType = storageType });
    }

    [HttpGet("{fileName}")]
    public async Task<IActionResult> DownloadFile(
        string fileName,
        [FromQuery] string storageType = "local")
    {
        var storageService = storageType.ToLower() switch
        {
            "cloud" => _cloudStorage,
            _ => _localStorage
        };

        var stream = await storageService.GetFileAsync(fileName);
        return File(stream, "application/octet-stream", fileName);
    }
}
```

### 动态解析Keyed Services

除了通过构造函数注入，我们还可以使用`IServiceProvider`动态解析带键的服务：

```csharp
public class DynamicStorageService
{
    private readonly IServiceProvider _serviceProvider;

    public DynamicStorageService(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public async Task<string> SaveFileAsync(
        Stream fileStream,
        string fileName,
        string storageKey)
    {
        // 动态获取指定键的服务
        var storageService = _serviceProvider.GetRequiredKeyedService<IStorageService>(storageKey);
        return await storageService.SaveFileAsync(fileStream, fileName);
    }

    public IStorageService GetStorageService(string key)
    {
        // 使用GetKeyedService可以处理键不存在的情况
        return _serviceProvider.GetKeyedService<IStorageService>(key)
            ?? throw new InvalidOperationException($"No storage service registered for key: {key}");
    }
}
```

## 实际应用场景

### 场景一：多支付网关集成

在电商系统中，通常需要集成多个支付网关以支持不同的支付方式：

```csharp
public interface IPaymentGateway
{
    Task<PaymentResult> ProcessPaymentAsync(PaymentRequest request);
    Task<RefundResult> RefundAsync(string transactionId, decimal amount);
}

public class StripePaymentGateway : IPaymentGateway
{
    private readonly StripeClient _stripeClient;

    public StripePaymentGateway(IConfiguration configuration)
    {
        _stripeClient = new StripeClient(configuration["Stripe:ApiKey"]);
    }

    public async Task<PaymentResult> ProcessPaymentAsync(PaymentRequest request)
    {
        // Stripe特定的支付处理逻辑
        var paymentIntent = await _stripeClient.CreatePaymentIntentAsync(
            request.Amount,
            request.Currency,
            request.PaymentMethodId);

        return new PaymentResult
        {
            Success = paymentIntent.Status == "succeeded",
            TransactionId = paymentIntent.Id
        };
    }

    public async Task<RefundResult> RefundAsync(string transactionId, decimal amount)
    {
        var refund = await _stripeClient.CreateRefundAsync(transactionId, amount);
        return new RefundResult { Success = refund.Status == "succeeded" };
    }
}

public class PayPalPaymentGateway : IPaymentGateway
{
    private readonly PayPalClient _paypalClient;

    public PayPalPaymentGateway(IConfiguration configuration)
    {
        _paypalClient = new PayPalClient(
            configuration["PayPal:ClientId"],
            configuration["PayPal:Secret"]);
    }

    public async Task<PaymentResult> ProcessPaymentAsync(PaymentRequest request)
    {
        // PayPal特定的支付处理逻辑
        var order = await _paypalClient.CreateOrderAsync(request);
        await _paypalClient.CaptureOrderAsync(order.Id);

        return new PaymentResult
        {
            Success = true,
            TransactionId = order.Id
        };
    }

    public async Task<RefundResult> RefundAsync(string transactionId, decimal amount)
    {
        var refund = await _paypalClient.RefundCaptureAsync(transactionId, amount);
        return new RefundResult { Success = refund.Status == "COMPLETED" };
    }
}

// 注册服务
builder.Services.AddKeyedScoped<IPaymentGateway, StripePaymentGateway>("stripe");
builder.Services.AddKeyedScoped<IPaymentGateway, PayPalPaymentGateway>("paypal");

// 订单处理服务
public class OrderService
{
    private readonly IServiceProvider _serviceProvider;

    public OrderService(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public async Task<PaymentResult> ProcessOrderAsync(Order order)
    {
        // 根据用户选择的支付方式获取对应的支付网关
        var paymentGateway = _serviceProvider.GetRequiredKeyedService<IPaymentGateway>(
            order.PaymentMethod.ToLower());

        var paymentRequest = new PaymentRequest
        {
            Amount = order.TotalAmount,
            Currency = order.Currency,
            PaymentMethodId = order.PaymentMethodId
        };

        return await paymentGateway.ProcessPaymentAsync(paymentRequest);
    }
}
```

### 场景二：多数据库支持

当应用需要支持多种数据库时，Keyed Services可以让切换变得简单：

```csharp
public interface IDatabaseProvider
{
    Task<IEnumerable<T>> QueryAsync<T>(string sql, object parameters);
    Task<int> ExecuteAsync(string sql, object parameters);
}

public class SqlServerProvider : IDatabaseProvider
{
    private readonly string _connectionString;

    public SqlServerProvider(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("SqlServer")!;
    }

    public async Task<IEnumerable<T>> QueryAsync<T>(string sql, object parameters)
    {
        using var connection = new SqlConnection(_connectionString);
        return await connection.QueryAsync<T>(sql, parameters);
    }

    public async Task<int> ExecuteAsync(string sql, object parameters)
    {
        using var connection = new SqlConnection(_connectionString);
        return await connection.ExecuteAsync(sql, parameters);
    }
}

public class PostgreSqlProvider : IDatabaseProvider
{
    private readonly string _connectionString;

    public PostgreSqlProvider(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("PostgreSql")!;
    }

    public async Task<IEnumerable<T>> QueryAsync<T>(string sql, object parameters)
    {
        using var connection = new NpgsqlConnection(_connectionString);
        return await connection.QueryAsync<T>(sql, parameters);
    }

    public async Task<int> ExecuteAsync(string sql, object parameters)
    {
        using var connection = new NpgsqlConnection(_connectionString);
        return await connection.ExecuteAsync(sql, parameters);
    }
}

// 注册
builder.Services.AddKeyedScoped<IDatabaseProvider, SqlServerProvider>("sqlserver");
builder.Services.AddKeyedScoped<IDatabaseProvider, PostgreSqlProvider>("postgresql");

// 使用配置决定默认数据库
var defaultDb = builder.Configuration["Database:Provider"] ?? "sqlserver";
builder.Services.AddScoped<IDatabaseProvider>(sp =>
    sp.GetRequiredKeyedService<IDatabaseProvider>(defaultDb));
```

### 场景三：多租户架构

在多租户SaaS应用中，不同租户可能需要不同的服务实现：

```csharp
public interface ITenantService
{
    Task<TenantConfiguration> GetConfigurationAsync(string tenantId);
    Task<bool> ValidateTenantAsync(string tenantId);
}

public class PremiumTenantService : ITenantService
{
    public async Task<TenantConfiguration> GetConfigurationAsync(string tenantId)
    {
        // 高级租户的配置：更多功能、更高限制
        return new TenantConfiguration
        {
            MaxUsers = 1000,
            MaxStorage = 1000 * 1024 * 1024 * 1024L, // 1TB
            Features = new[] { "advanced-analytics", "custom-branding", "api-access" }
        };
    }

    public async Task<bool> ValidateTenantAsync(string tenantId)
    {
        // 高级租户验证逻辑
        return true;
    }
}

public class StandardTenantService : ITenantService
{
    public async Task<TenantConfiguration> GetConfigurationAsync(string tenantId)
    {
        // 标准租户的配置：基础功能
        return new TenantConfiguration
        {
            MaxUsers = 50,
            MaxStorage = 10 * 1024 * 1024 * 1024L, // 10GB
            Features = new[] { "basic-features" }
        };
    }

    public async Task<bool> ValidateTenantAsync(string tenantId)
    {
        // 标准租户验证逻辑
        return true;
    }
}

// 注册
builder.Services.AddKeyedScoped<ITenantService, PremiumTenantService>("premium");
builder.Services.AddKeyedScoped<ITenantService, StandardTenantService>("standard");

// 中间件中根据租户类型注入对应服务
public class TenantMiddleware
{
    private readonly RequestDelegate _next;

    public TenantMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context, IServiceProvider serviceProvider)
    {
        var tenantId = context.Request.Headers["X-Tenant-Id"].FirstOrDefault();
        var tenantTier = await DetermineTenantTierAsync(tenantId);

        var tenantService = serviceProvider.GetRequiredKeyedService<ITenantService>(tenantTier);
        context.Items["TenantService"] = tenantService;

        await _next(context);
    }

    private async Task<string> DetermineTenantTierAsync(string? tenantId)
    {
        // 从数据库或缓存中获取租户级别
        return "standard"; // 简化示例
    }
}
```

## Keyed Services的进阶特性

### 使用AnyKey获取所有实现

有时我们需要获取某个接口的所有已注册实现。Keyed Services提供了特殊的`KeyedService.AnyKey`来实现这一需求：

```csharp
public class NotificationService
{
    private readonly IEnumerable<INotificationProvider> _allProviders;

    public NotificationService(
        [FromKeyedServices(KeyedService.AnyKey)] IEnumerable<INotificationProvider> allProviders)
    {
        _allProviders = allProviders;
    }

    public async Task SendToAllChannelsAsync(string message)
    {
        var tasks = _allProviders.Select(provider =>
            provider.SendAsync(message));

        await Task.WhenAll(tasks);
    }
}
```

### 组合使用命名和键控服务

在复杂场景中，我们可以结合使用默认注册和键控注册：

```csharp
// 注册默认实现（用于最常见的场景）
builder.Services.AddScoped<IStorageService, LocalStorageService>();

// 同时注册键控实现（用于特殊场景）
builder.Services.AddKeyedScoped<IStorageService, LocalStorageService>("local");
builder.Services.AddKeyedScoped<IStorageService, CloudStorageService>("cloud");
builder.Services.AddKeyedScoped<IStorageService, BackupStorageService>("backup");

// 使用时可以灵活选择
public class DocumentManager
{
    private readonly IStorageService _defaultStorage;
    private readonly IStorageService _backupStorage;

    public DocumentManager(
        IStorageService defaultStorage, // 注入默认实现
        [FromKeyedServices("backup")] IStorageService backupStorage) // 注入特定键的实现
    {
        _defaultStorage = defaultStorage;
        _backupStorage = backupStorage;
    }

    public async Task SaveWithBackupAsync(Stream content, string fileName)
    {
        // 保存到默认存储
        await _defaultStorage.SaveFileAsync(content, fileName);

        // 同时备份
        content.Position = 0; // 重置流位置
        await _backupStorage.SaveFileAsync(content, $"backup/{fileName}");
    }
}
```

### 生命周期管理

Keyed Services支持所有标准的服务生命周期：

```csharp
// Transient：每次请求都创建新实例
builder.Services.AddKeyedTransient<ICache, MemoryCache>("memory");

// Scoped：每个请求作用域内共享实例
builder.Services.AddKeyedScoped<IStorageService, LocalStorageService>("local");

// Singleton：整个应用程序生命周期内单例
builder.Services.AddKeyedSingleton<ILogger, FileLogger>("file");
```

## 最佳实践与注意事项

### 键的命名约定

为了保持代码的可维护性，建议遵循以下键命名约定：

```csharp
// 使用常量定义键，避免魔法字符串
public static class StorageKeys
{
    public const string Local = "local";
    public const string Cloud = "cloud";
    public const string Backup = "backup";
}

// 注册时使用常量
builder.Services.AddKeyedScoped<IStorageService, LocalStorageService>(StorageKeys.Local);
builder.Services.AddKeyedScoped<IStorageService, CloudStorageService>(StorageKeys.Cloud);

// 使用时也使用常量
public class DocumentService
{
    public DocumentService(
        [FromKeyedServices(StorageKeys.Local)] IStorageService localStorage,
        [FromKeyedServices(StorageKeys.Cloud)] IStorageService cloudStorage)
    {
        // ...
    }
}
```

### 错误处理

当请求的键不存在时，`GetRequiredKeyedService`会抛出异常。在某些场景下，使用`GetKeyedService`并处理null值可能更合适：

```csharp
public class ResilientStorageService
{
    private readonly IServiceProvider _serviceProvider;

    public ResilientStorageService(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public async Task<string> SaveFileAsync(Stream fileStream, string fileName, string preferredStorage)
    {
        // 尝试使用首选存储
        var storageService = _serviceProvider.GetKeyedService<IStorageService>(preferredStorage);

        if (storageService == null)
        {
            // 回退到默认存储
            storageService = _serviceProvider.GetKeyedService<IStorageService>(StorageKeys.Local)
                ?? throw new InvalidOperationException("No storage service available");
        }

        try
        {
            return await storageService.SaveFileAsync(fileStream, fileName);
        }
        catch (Exception ex)
        {
            // 如果首选存储失败，尝试备用存储
            var backupService = _serviceProvider.GetKeyedService<IStorageService>(StorageKeys.Backup);
            if (backupService != null && backupService != storageService)
            {
                fileStream.Position = 0;
                return await backupService.SaveFileAsync(fileStream, fileName);
            }

            throw;
        }
    }
}
```

### 性能考虑

Keyed Services的解析性能与普通服务解析相当，不会带来显著的性能开销。但是，如果在热路径上频繁解析服务，考虑将解析结果缓存：

```csharp
public class CachedStorageResolver
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ConcurrentDictionary<string, IStorageService> _cache = new();

    public CachedStorageResolver(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public IStorageService GetStorageService(string key)
    {
        return _cache.GetOrAdd(key, k =>
            _serviceProvider.GetRequiredKeyedService<IStorageService>(k));
    }
}
```

### 测试支持

在单元测试中，Keyed Services同样易于使用：

```csharp
[Test]
public async Task SaveDocument_UsingCloudStorage_ShouldSucceed()
{
    // Arrange
    var services = new ServiceCollection();
    var mockCloudStorage = new Mock<IStorageService>();
    mockCloudStorage
        .Setup(s => s.SaveFileAsync(It.IsAny<Stream>(), It.IsAny<string>()))
        .ReturnsAsync("https://cloud.storage/file.txt");

    services.AddKeyedScoped(StorageKeys.Cloud, (sp, key) => mockCloudStorage.Object);

    var serviceProvider = services.BuildServiceProvider();

    var documentService = new DocumentService(
        null!,
        serviceProvider.GetRequiredKeyedService<IStorageService>(StorageKeys.Cloud));

    // Act
    using var stream = new MemoryStream();
    var result = await documentService.SaveDocumentAsync(stream, "test.txt", true);

    // Assert
    Assert.That(result, Is.EqualTo("https://cloud.storage/file.txt"));
    mockCloudStorage.Verify(s => s.SaveFileAsync(It.IsAny<Stream>(), "test.txt"), Times.Once);
}
```

## 与其他模式的对比

### Keyed Services vs 工厂模式

**工厂模式：**

- ❌ 需要额外的工厂接口和实现
- ❌ 包含字符串匹配和条件判断逻辑
- ❌ 增加代码量和维护成本
- ✅ 可以包含复杂的创建逻辑
- ✅ 支持参数化创建

**Keyed Services：**

- ✅ 框架内置，无需额外代码
- ✅ 类型安全，编译时检查
- ✅ 简洁优雅，易于维护
- ❌ 不支持复杂的创建逻辑
- ❌ 不支持参数化创建

**选择建议：** 对于简单的多实现选择场景，优先使用Keyed Services。如果需要复杂的创建逻辑或参数化创建，考虑工厂模式。

### Keyed Services vs 策略模式

**策略模式：**

- ✅ 符合开闭原则，易于扩展
- ✅ 可以包含上下文相关的选择逻辑
- ❌ 需要额外的策略管理器
- ❌ 代码相对复杂

**Keyed Services：**

- ✅ 更简洁的实现
- ✅ 利用DI容器管理
- ❌ 选择逻辑需要在外部处理
- ✅ 可以与策略模式结合使用

**选择建议：** Keyed Services可以作为策略模式的实现基础，两者并不互斥。在需要复杂选择逻辑时，可以使用Keyed Services注册策略，用策略管理器选择。

## 迁移现有代码

如果你的项目中已经使用了工厂模式或其他方式来处理多实现问题，迁移到Keyed Services是相对简单的：

### 步骤1：识别工厂方法

找出所有用于选择服务实现的工厂方法：

```csharp
// 旧代码
public class StorageServiceFactory : IStorageServiceFactory
{
    public IStorageService GetStorageService(string type)
    {
        return type switch
        {
            "local" => _serviceProvider.GetService<LocalStorageService>(),
            "cloud" => _serviceProvider.GetService<CloudStorageService>(),
            _ => throw new ArgumentException()
        };
    }
}
```

### 步骤2：更新服务注册

将原来的注册方式改为使用键注册：

```csharp
// 移除工厂注册
// services.AddScoped<IStorageServiceFactory, StorageServiceFactory>();

// 添加键控服务注册
services.AddKeyedScoped<IStorageService, LocalStorageService>("local");
services.AddKeyedScoped<IStorageService, CloudStorageService>("cloud");
```

### 步骤3：更新使用代码

将工厂调用改为使用`FromKeyedServices`或`GetKeyedService`：

```csharp
// 旧代码
public class DocumentService
{
    private readonly IStorageServiceFactory _factory;

    public DocumentService(IStorageServiceFactory factory)
    {
        _factory = factory;
    }

    public async Task SaveAsync(Stream content, string fileName, string storageType)
    {
        var storage = _factory.GetStorageService(storageType);
        await storage.SaveFileAsync(content, fileName);
    }
}

// 新代码
public class DocumentService
{
    private readonly IServiceProvider _serviceProvider;

    public DocumentService(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public async Task SaveAsync(Stream content, string fileName, string storageType)
    {
        var storage = _serviceProvider.GetRequiredKeyedService<IStorageService>(storageType);
        await storage.SaveFileAsync(content, fileName);
    }
}
```

### 步骤4：逐步迁移

不需要一次性迁移所有代码。可以先保留工厂模式，在工厂内部使用Keyed Services：

```csharp
public class StorageServiceFactory : IStorageServiceFactory
{
    private readonly IServiceProvider _serviceProvider;

    public StorageServiceFactory(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    public IStorageService GetStorageService(string type)
    {
        // 内部使用Keyed Services
        return _serviceProvider.GetRequiredKeyedService<IStorageService>(type);
    }
}
```

这样可以在保持向后兼容的同时，逐步将各个模块迁移到直接使用Keyed Services。

## 总结

Keyed Services是.NET 8中一个强大而优雅的特性，它为处理同一接口的多个实现提供了框架级的解决方案。相比传统的工厂模式或手动筛选方式，Keyed Services具有以下优势：

**核心优势：**

- **简洁性**：无需编写额外的工厂代码，减少样板代码
- **类型安全**：在编译时而非运行时捕获错误
- **可读性**：意图明确，代码更易理解和维护
- **灵活性**：支持多种注入方式和生命周期管理
- **可测试性**：易于在单元测试中模拟和替换

**适用场景：**

- 多种支付网关、通知渠道、存储服务等第三方集成
- 多租户架构中不同租户级别的服务差异
- 多数据库或多数据源支持
- 根据配置或运行时条件选择不同的算法实现
- 功能开关和A/B测试场景

**使用建议：**

- 使用常量而非魔法字符串定义键
- 合理处理键不存在的情况
- 在简单场景优先使用Keyed Services，复杂场景结合其他模式
- 保持键的命名清晰且有意义
- 在热路径上考虑缓存解析结果

Keyed Services不是万能的，但它确实解决了一个非常常见的问题。当你发现自己在编写工厂代码或大量if-else来选择服务实现时，考虑一下Keyed Services是否能让你的代码更加简洁优雅。

掌握Keyed Services，让你的.NET应用架构更加灵活而不失简洁。
