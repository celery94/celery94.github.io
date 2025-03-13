---
pubDatetime: 2024-11-04
tags: []
source: https://thecodeman.net/posts/securing-secrets-in-dotnet-with-azure-key-vault?utm_source=newsletter&utm_medium=email&utm_campaign=TheCodeMan%20Newsletter%20-%20Securing%20Secrets%20in%20.NET%208%20with%20Azure%20Key%20Vault
author: TheCodeMan
title: 在 .NET 8 中使用 Azure 密钥保管库保护机密
description: 了解如何使用 Azure 密钥保管库在 .NET 8 应用程序中安全地管理和访问机密。本指南涵盖了存储敏感数据的最佳实践、设置密钥保管库以及将其与 .NET 集成以实现安全和可扩展的应用程序。
---

### 背景

在传统应用程序中，敏感的配置数据，比如数据库连接字符串和API密钥，通常直接存储在像appconfig.json这样的配置文件中。

虽然这样很方便，但如果处理不当，会带来安全风险。

**Azure 密钥保管库** 提供了一种安全的托管解决方案用于机密存储，使我们可以将敏感数据从本地文件中取出，存储在安全的云环境中。

在本指南中，我们将演示如何在.NET 8应用程序中将机密从appconfig.json转移到Azure 密钥保管库。

### 没有Azure 密钥保管库的情况

假设我们有一个API，其配置文件appsettings.json内容如下：

```json
{
  "Config": {
    "Database": "mssqlConnectionString",
    "Redis": "redisConnectionString",
    "RedisPassword": "someDummyPassword"
  }
}
```

在您的Program.cs中，您可以按如下方式加载这些配置：

```csharp
var builder = WebApplication.CreateBuilder(args);

// 从appsettings.json加载配置
builder.Configuration.AddJsonFile("appsettings.json", optional: false, reloadOnChange: true);

// 注册服务
builder.Services.AddControllers();

// 访问配置设置并在需要时注册为服务
string databaseConnectionString = builder.Configuration["Config:Database"];
string redisConnectionString = builder.Configuration["Config:Redis"];
string redisPassword = builder.Configuration["Config:RedisPassword"];
```

### 为什么在appsettings.json中保存机密是个问题？

将连接字符串和密码等敏感数据存储在appsettings.json中存在几个风险：

**1\. 安全暴露：** appsettings.json文件是您应用程序源代码的一部分，因此任何有代码库访问权限的人都可以看到敏感信息。

**2\. 意外共享：** 如果您不小心将代码上传到公共代码库（如GitHub），那么appsettings.json中的所有机密就会变成公开可访问的。这可能导致数据泄露或未经授权的资源访问。

**3\. 合规风险：** 许多安全标准（如GDPR、HIPAA和PCI-DSS）要求敏感信息安全存储，而不是明文保存。将机密保存在appsettings.json中可能使您的应用程序不符合这些标准。

**4\. 环境特定的机密：** 不同的环境（开发、测试、生产）通常需要不同的机密。使用appsettings.json保存这些值需要您创建多个配置文件，这会增加管理的复杂性和泄漏的风险。

因此，您可以使用Azure 密钥保管库来存储这些机密。

让我们看看如何做到这一点。

### 第一步：设置Azure 密钥保管库

**1\. 创建Azure 密钥保管库：**

- 进入[Azure门户](https://portal.azure.com/)并搜索“密钥保管库”。
- 点击**创建**并配置密钥保管库的设置：
  - **资源组：** 选择一个现有的或创建一个新的资源组。
  - **密钥保管库名称：** 提供一个唯一的密钥保管库名称。
  - **区域：** 选择离您的应用程序最近的区域。
  - **定价层：** 您可以选择免费层。

![Azure Portal](https://thecodeman.net/images/blog/posts/securing-secrets-in-dotnet-with-azure-key-vault/azure-portal.png)

**2\. 访问策略（可选）：**

- 进入密钥保管库设置中的**访问策略**。
- 点击**添加访问策略**并选择必要的权限：
  - **获取**和**列出**机密（根据使用情况可能需要其他权限）。
  - **选择主体：** 添加您的应用程序身份（通常是用于在Azure中运行的应用程序的服务主体）或您自己的账户用于开发目的。

**3\. 添加机密：**

- 进入**机密**部分并点击**生成/导入**。
- 命名您的机密（例如，DatabaseConnectionString）并添加机密值（例如，您的数据库连接字符串）。
- 保存机密。

![Azure Add Secrets](https://thecodeman.net/images/blog/posts/securing-secrets-in-dotnet-with-azure-key-vault/add-secrets.png)

在这个示例中，我添加了**Config--Database**机密。

为什么是“--”？

在Azure 密钥保管库中，使用--（双连字符）语法表示与.NET应用程序集成时的**嵌套配置结构**。

![Azure Create Secret](https://thecodeman.net/images/blog/posts/securing-secrets-in-dotnet-with-azure-key-vault/create-secret.png)

有了这些Azure设置，我们就可以转到Visual Studio并编写一些代码了。

### 第二步：配置.NET以使用Azure 密钥保管库

在.NET 8中，使用Azure.Extensions和Microsoft.Extensions.Configuration包可以轻松集成Azure 密钥保管库。

**1\. 安装必要的包：** 使用NuGet将以下包添加到您的项目中：

- Azure.Identity
- Azure.Extensions.AspNetCore.Configuration.Secrets

**2\. 配置托管身份（可选）：** 如果您的应用程序托管在Azure上（例如，在App Service或Azure VM中），您可以使用托管身份简化身份验证。在访问策略中为此身份分配权限。- 在我们的情况下，您可以跳过这个测试。

**3\. 在Program.cs中添加密钥保管库配置：** 更新您的Program.cs以包含密钥保管库配置：

```csharp
string environment = Environment.GetEnvironmentVariable("ENVIRONMENT");
string jsonFile = $"appsettings.{environment}.json";

builder.Configuration
       .AddJsonFile("appsettings.json", optional: false, reloadOnChange: true)
       .AddJsonFile(jsonFile, optional: true);

string? keyVaultUrl = builder.Configuration["KeyVault"];

var credentials = new DefaultAzureCredential ();
builder.Configuration.AddAzureKeyVault(new Uri(keyVaultUrl), credentials);
```

#### **代码解释：**

**1\. 确定环境：**

**• Environment.GetEnvironmentVariable("ENVIRONMENT"):**

这行代码从操作系统中检索ENVIRONMENT环境变量，指示应用程序运行在哪个环境（例如，开发、暂存或生产）。

**• string jsonFile = $"appsettings.{environment}.json";:**

使用环境值，这行代码构建一个环境特定的配置文件名，例如appsettings.Development.json或appsettings.Production.json。

**2\. 加载配置文件：**

**• .AddJsonFile("appsettings.json", optional: false, reloadOnChange: true):**

这行告诉应用程序加载主配置文件appsettings.json。optional: false参数意味着这个文件必须存在。reloadOnChange: true启用文件更改时的自动重载，因此应用程序无需重启即可获取更新。

**• .AddJsonFile(jsonFile, optional: true):**

这里，它加载环境特定的配置文件（例如，appsettings.Development.json）。设置optional: true意味着这个文件不是必需的；如果找不到，应用程序将继续运行。这种设置允许您在需要时使用环境特定的值覆盖appsettings.json中的设置。

**3\. 检索密钥保管库URL：**

**• string? keyVaultUrl = builder.Configuration\["KeyVault"\];:**

在加载配置文件后，这行代码从本地配置中访问KeyVault条目。此条目应包含Azure 密钥保管库的URL，例如[https://mykeyvault.vault.azure.net/](https://mykeyvault.vault.azure.net/)。这是连接到密钥保管库以检索机密所必需的。

**_注意：如果每个环境有单独创建的Azure服务，每个环境的单个文件将有自己的密钥保管库链接 - 开发有自己的Azure，测试有自己的，等等。_**

**4\. 将Azure 密钥保管库添加到配置中：**

**• var credentials = new DefaultAzureCredential();:**

这行初始化了DefaultAzureCredential，这是Azure身份库中的一个类。DefaultAzureCredential尝试使用多种方法与Azure进行身份验证，例如使用Azure CLI、环境变量、托管身份（在Azure中运行时）等。它通过根据环境自动选择最合适的身份验证方法来简化身份验证过程。

**• builder.Configuration.AddAzureKeyVault(new Uri(keyVaultUrl), credentials);:**

这行将Azure 密钥保管库作为配置源添加。使用keyVaultUrl和凭据，它连接到密钥保管库，将所有可用的机密加载到应用程序的配置中。这样，应用程序可以像访问任何其他配置设置一样访问密钥保管库中的机密。

#### 配置如何协同工作

1\. 应用程序首先从appsettings.json和可选的环境特定配置文件加载设置。

2\. 然后，它从配置中检索密钥保管库URL。

3\. 最后，它使用DefaultAzureCredential连接到Azure 密钥保管库，并将密钥保管库添加为配置提供程序，允许从密钥保管库中存储的机密像在appsettings.json中定义的一样被访问。

### 第三步：在您的应用程序中访问机密

设置密钥保管库后，保管库中定义的所有机密都会自动加载到应用程序的IConfiguration中。您可以像它们仍在appconfig.json中一样在代码中访问它们。

```csharp
public class MyService
{
    private readonly string _database;
    private readonly string _redis;

    public MyService(IConfiguration configuration)
    {
        // 从密钥保管库中检索机密
        _database = configuration["Config:Database"];
        _redis = configuration["Config:Redis"];
    }

    // 在您的应用程序逻辑中使用机密
}
```

这样，您只需编译一次查询，然后使用不同的参数执行它，而无需每次都重新编译。

### 总结

在现代应用程序中，保护敏感数据（如数据库连接字符串、API密钥和其他机密）至关重要。

Azure 密钥保管库提供了一种安全且集中的解决方案，使.NET 8应用程序能够有效地管理机密。

通过遵循本指南，您已经学会了：

- 如何设置密钥保管库
- 将其与.NET集成
- 配置您的应用程序以使用appsettings.json和环境特定设置。
- 此外，使用DefaultAzureCredential简化了身份验证
- 使设置适应本地和云环境。

通过实施这些做法，您的.NET 8应用程序将更加安全、可维护，并符合行业标准。

使用Azure 密钥保管库不仅有助于保护敏感信息，还为跨不同环境的配置管理带来了灵活性。

在继续使用.NET和Azure服务构建安全、可扩展的应用程序时，请牢记这些技术。

今天就到这里。
