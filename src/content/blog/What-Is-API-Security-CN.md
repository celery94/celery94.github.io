---
title: 什么是 API 安全？以及在ASP.NET Core WebAPI上的最佳实践
author: Celery Liu
pubDatetime: 2024-02-01
slug: what-is-api-security-and-best-practices-on-aspnet-core-webapi
featured: false
draft: false
tags:
  - ASP.NET
  - Core
  - WebAPI
  - RestAPI
description: 了解 API 安全的左移方法如何帮助团队捕获并修复 API 安全威胁。
---

# 什么是 API 安全？以及在ASP.NET Core WebAPI上的最佳实践

## API 安全的一些最佳实践是什么？

每个 API 都不尽相同，因此会有独特的安全需求。尽管如此，以下最佳实践可以帮助您避免上述讨论的安全漏洞——无论您的 API 类型或用例如何。

### **使用 HTTPS**

HTTPS 通过 SSL/TLS 加密并存储通过互联网传输的数据。它在保护敏感数据（如登录凭据和财务信息）中起着至关重要的作用，并且是许多监管标准遵从性的要求。

在 ASP.NET Core Web API 中启用 HTTPS 涉及几个关键步骤。ASP.NET Core 默认支持 HTTPS，并在开发过程中会自动生成自签名的证书。然而，在生产环境中，您应该使用有效的证书来确保最佳的安全性。以下是启用 HTTPS 的步骤：

1. **获取 SSL/TLS 证书**：

   - 对于生产环境，您应该从可靠的证书颁发机构（CA）获取一个证书。对于开发环境，ASP.NET Core 会自动创建和使用自签名的证书。

2. **配置 Kestrel 服务器以使用 HTTPS**：

   - 在 `appsettings.json` 或 `appsettings.Production.json` 文件中配置 Kestrel 服务器以使用 HTTPS。例如：

     ```json
     {
       "Kestrel": {
         "Endpoints": {
           "Https": {
             "Url": "https://localhost:5001",
             "Certificate": {
               "Path": "<path-to-your-certificate.pfx>",
               "Password": "<your-certificate-password>"
             }
           }
         }
       }
     }
     ```

     如果您使用的是 .pfx 文件，您需要指定证书的路径和密码。如果证书存储在证书存储中，则需要指定证书的名称和存储位置。

3. **在 `Startup.cs` 中强制 HTTPS**：

   - 在 `Startup.cs` 的 `Configure` 方法中，添加 `app.UseHttpsRedirection();` 来确保所有请求都被重定向到 HTTPS：

     ```csharp
     public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
     {
         // 其他配置...

         app.UseHttpsRedirection();

         // 其他配置...
     }
     ```

### **实施速率限制和节流**

速率限制是限制客户端在一定时间内对 API 发出请求次数的配额，它有助于保护 API 免受拒绝服务（DoS）攻击。速率限制通常与节流一起使用，节流通过降低请求处理的速率来帮助保存 API 的计算资源。

在 ASP.NET Core Web API 中实施速率限制和节流通常涉及以下步骤：

1. **选择合适的中间件**：

   - ASP.NET Core 默认不提供内置的速率限制中间件，因此您通常需要依赖第三方库。一个流行的选择是 [`AspNetCoreRateLimit`](https://github.com/stefanprodan/AspNetCoreRateLimit)，它提供了 IP 速率限制和客户端速率限制。

2. **安装和配置 `AspNetCoreRateLimit`**：

   - 首先，通过 NuGet 安装 `AspNetCoreRateLimit` 包。
   - 在 `Startup.cs` 的 `ConfigureServices` 方法中添加和配置速率限制服务：

     ```csharp
     public void ConfigureServices(IServiceCollection services)
     {
         // 其他服务配置...

         // 添加内存缓存（AspNetCoreRateLimit 需要）
         services.AddMemoryCache();

         // 加载速率限制配置
         services.Configure<IpRateLimitOptions>(Configuration.GetSection("IpRateLimiting"));
         services.Configure<ClientRateLimitOptions>(Configuration.GetSection("ClientRateLimiting"));

         // 添加速率限制服务
         services.AddInMemoryRateLimiting();

         // 其他服务配置...
     }
     ```

3. **在 `Startup.cs` 中启用速率限制中间件**：

   - 在 `Configure` 方法中，添加 `app.UseIpRateLimiting();` 和/或 `app.UseClientRateLimiting();` 来启用中间件：

     ```csharp
     public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
     {
         // 其他中间件配置...

         // 启用 IP 速率限制
         app.UseIpRateLimiting();

         // 启用客户端速率限制
         app.UseClientRateLimiting();

         // 其他中间件配置...
     }
     ```

4. **配置速率限制规则**：

   - 在 `appsettings.json` 中配置速率限制规则。您可以设置全局规则，也可以为特定的 IP 或客户端 ID 设置更具体的规则。

     ```json
     {
       "IpRateLimiting": {
         "GeneralRules": [
           {
             "Endpoint": "*",
             "Period": "1m",
             "Limit": 100
           }
         ]
       },
       "ClientRateLimiting": {
         // 客户端速率限制配置...
       }
     }
     ```

### **验证并清理所有输入参数、头部和有效载荷：**

输入验证是确认发送到 API 的任何数据遵循预期格式和约束的过程，而清理有助于确保输入数据不包含有害字符。这些做法有助于保护 API 免受注入攻击，如 SQL 注入、跨站脚本和命令注入。

在 ASP.NET Core Web API 中验证和清理所有输入参数、头部和有效载荷是确保应用安全的重要步骤。这包括防止注入攻击、确保数据格式正确，以及防止恶意数据进入系统。以下是实施这些安全措施的步骤：

1. **使用模型验证**：

   - ASP.NET Core 提供了模型验证功能，通过 Data Annotations 可以轻松地在模型级别上实现输入验证。例如：

     ```csharp
     public class MyModel
     {
         [Required]
         [StringLength(100, MinimumLength = 3)]
         public string Name { get; set; }

         [Range(1, 100)]
         public int Age { get; set; }

         // 其他属性和验证...
     }
     ```

   - 在控制器中，使用 `ModelState.IsValid` 检查模型状态是否有效。

     ```csharp
     [HttpPost]
     public IActionResult Post([FromBody] MyModel model)
     {
         if (!ModelState.IsValid)
         {
             return BadRequest(ModelState);
         }

         // 处理有效的模型...
     }
     ```

2. **清理头部和有效载荷**：

   - 对于不通过模型验证的数据（如 HTTP 头部或自定义有效载荷），您需要手动验证和清理这些数据。
   - 使用白名单方法来验证数据，只允许已知安全的字符和格式。
   - 对于预期是特定类型（如数字、日期等）的数据，确保进行类型检查和格式验证。

3. **防止注入攻击**：

   - 对于任何注入到数据库或其他系统中的数据，确保使用参数化查询或 ORM（如 Entity Framework Core）来避免 SQL 注入等攻击。
   - 对于可能包含脚本或 HTML 的数据，确保进行适当的编码和/或清理以防止跨站脚本攻击（XSS）。

4. **使用安全库进行清理**：

   - 对于特定类型的清理任务，可以使用安全库（如 [HtmlSanitizer](https://github.com/mganss/HtmlSanitizer)）来清理 HTML 内容，以防止 XSS 攻击。

5. **限制大小和长度**：
   - 对于所有输入（包括文件上传），限制大小和长度以防止资源耗尽攻击。

### **监控您的 API 以寻找可疑活动：**

安全监控涉及持续监控 API 遥测数据，以便尽快发现安全威胁和违规行为。日志监控尤其重要，因为日志记录了系统中发生的每个活动——包括坏人的操作。

监控您的 ASP.NET Core Web API 以寻找可疑活动是保护您的应用程序安全的关键部分。实施有效的监控策略可以帮助您及时识别和响应安全威胁。以下是设置监控的步骤：

1. **使用日志记录**：

   - 在您的 API 中实现全面的日志记录。使用 ASP.NET Core 的内置日志功能或如 [Serilog](https://github.com/serilog/serilog)、[NLog](https://github.com/NLog/NLog) 等流行日志库。
   - 记录关键事件，包括身份验证失败、输入验证错误、异常、关键业务操作以及任何可能表示滥用或攻击的不寻常行为。

2. **集成应用程序性能管理（APM）工具**：

   - 使用像 Application Insights、New Relic、Datadog 等 APM 工具来监控应用程序的性能和健康状况。
   - 这些工具不仅可以帮助您监控应用程序性能，还可以提供关于异常行为的洞察，如突然的流量增加、响应时间变化等。

3. **实现实时监控和警报**：
   - 配置实时监控和警报机制，以便在检测到可疑活动时立即通知您。
   - 这可能包括异常流量模式、过多的错误率、连续的登录失败等。

### **实施基于角色的访问控制：**

基于角色的访问控制（RBAC）用于根据已认证用户的角色控制对 API 资源的访问。例如，拥有“管理员”角色的用户可能能够访问每个资源，而拥有“访客”角色的用户可能只能访问只读资源。这种方法提供了一种系统化的方式来保护 API 资源和数据免受未经授权的访问。

在 ASP.NET Core Web API 中实施基于角色的访问控制 (RBAC) 是一种管理用户访问权限的有效方法。这可以确保只有拥有适当角色的用户才能访问特定资源或执行特定操作。以下是实施 RBAC 的步骤：

1. **定义角色**：

   - 确定并定义您的应用程序中需要的角色。例如，您可能有 "Admin", "User", "ReadOnly" 等角色。
   - 在设计系统时，考虑将权限与角色分离，以便更灵活地管理权限。

2. **配置身份验证和授权**：

   - 在 `Startup.cs` 的 `ConfigureServices` 方法中配置身份验证服务，例如使用 JWT 令牌、Cookie 身份验证或其他机制。
   - 启用授权服务，并配置策略，以基于用户角色授予权限。

   ```csharp
   services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
       .AddJwtBearer(options =>
       {
           // 配置 JWT 选项...
       });

   services.AddAuthorization(options =>
   {
       options.AddPolicy("RequireAdministratorRole",
           policy => policy.RequireRole("Admin"));
       // 其他角色的策略...
   });
   ```

3. **分配角色到用户**：

   - 在用户注册或管理过程中，根据业务逻辑将角色分配给用户。
   - 如果您使用的是 `Microsoft.AspNetCore.Identity`，可以使用 `UserManager` 类来管理用户角色。

4. **在控制器或操作中应用角色控制**：

   - 使用 `[Authorize]` 属性在控制器或特定操作上强制实施角色控制。例如：

   ```csharp
   [Authorize(Roles = "Admin")]
   public class AdminController : ControllerBase
   {
       // 只有 Admin 角色的用户可以访问的操作
   }

   [Authorize(Roles = "Admin,User")]
   public ActionResult GetUserDetails()
   {
       // Admin 和 User 角色的用户可以访问
   }
   ```
