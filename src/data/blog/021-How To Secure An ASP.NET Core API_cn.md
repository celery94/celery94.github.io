---
pubDatetime: 2024-02-28
tags: [".NET", "ASP.NET Core", "API", "Security", "JWT"]
source: https://juliocasal.com/blog/Secure-AspNetCore-API
author: Julio Casal
title: 如何保护一个ASP.NET Core API
description: 如何保护一个ASP.NET Core API
---

# 如何保护一个ASP.NET Core API

> ## 摘录
>
> 原文：[How To Secure An ASP.NET Core API](https://juliocasal.com/blog/Secure-AspNetCore-API)

---

# 如何保护一个ASP.NET Core API

2023年8月5日

_阅读时间：5分钟_

今天，我将向你展示如何在几个简单的步骤中保护你的ASP.NET Core API。

现如今拥有一个安全的API是必须的。你就是不能未加保护就上线。

但是，了解正确的认证和授权机制可能有点棘手。

幸运的是，基于令牌的认证通过 JSON Web Tokens (JWT) 是大多数场景的绝佳选择，而且在ASP.NET Core中实现起来相当简单。

让我们看看如何做到。

### **什么是基于令牌的认证？**

基于令牌的认证是现代网络应用和API中广泛使用的一种方法，用于安全地验证用户并控制对资源的访问。

![](https://juliocasal.com/assets/images/token-based-auth.jpg)

它包括以下更广泛的步骤：

**1\. 请求授权**。客户端通过向认证服务器发送用户凭证，请求授权访问你的API。

**2\. 认证用户**。授权服务器通过登录页面或任何其他类型的认证机制对用户进行认证。

**3\. 生成访问令牌**。如果认证成功，授权服务器生成一个编码的JWT访问令牌，并将其返回给客户端。

**4\. 使用访问令牌**。客户端使用访问令牌来访问受保护的API资源。

**5\. 验证令牌并返回响应**。API解码并验证访问令牌，如果有效，它就返回请求的资源。

### **游戏API**

这是一个简单的ASP.NET Core API，它返回一个指定玩家的游戏列表：

```csharp
Dictionary<string, List<string>> gamesMap = new()
{
    {"player1", new List<string>(){"Street Fighter II", "Minecraft"}},
    {"player2", new List<string>(){"Forza Horizon 5", "FIFA 23"}}
};

var builder = WebApplication.CreateBuilder(args);

var app = builder.Build();

app.MapGet("/playergames", () => gamesMap);

app.Run();
```

让我们看看现在如何在几个简单的步骤中保护 **/playergames** 端点。

### **步骤1: 启用认证**

认证是确定用户身份的过程。

由于我们希望使用访问令牌启用对端点的认证，特别是JWT，让我们添加启用JWT承载认证策略的NuGet包：

```bat
dotnet add package Microsoft.AspNetCore.Authentication.JwtBearer
```

然后，让我们添加所需的JWT承载认证服务，这将允许我们的应用程序接受并验证传入的访问令牌：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddAuthentication().AddJwtBearer();

var app = builder.Build();
```

有了这个，我们就可以对传入的请求进行认证了。

### **步骤2: 要求授权**

授权是确定用户是否可以访问资源的过程。

我们需要告诉我们的应用哪些端点需要授权，以及使用何种授权策略。

在我们的案例中，我们想要为 **/playergames** 端点要求授权，也许我们可以从默认授权策略开始。

我们可以通过 **RequireAuthorization()** 方法来做到这一点：

```csharp
app.MapGet("/playergames", () => gamesMap)
   .RequireAuthorization();
```

这将确保任何没有经过认证的对该端点的请求都被拒绝。

然而，在我们可以使用那个方法之前，我们还需要添加所需的授权服务。

所以，让我们在AddAuthentication()调用后调用 **AddAuthorizationBuilder()**：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddAuthentication().AddJwtBearer();
builder.Services.AddAuthorizationBuilder();

var app = builder.Build();
```

### **步骤3: 确认未认证的调用被拒绝**

让我们看看在没有先认证的情况下尝试调用 **/playergames** 端点会发生什么。

所以，让我们在项目根目录中创建一个小的 **games.http** 文件，只包含这一行：

```
GET http://localhost:5026/playergames
```

如果你正在使用VS Code，可以通过安装VS Code的 [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) 扩展来使用该文件。

现在，让我们打开终端并运行我们的应用程序：

```
dotnet run
```

现在在 **games.http** 文件中点击 **Send Request**。

你应该会得到这个：

```bat
HTTP/1.1 401 Unauthorized
Content-Length: 0
Connection: close
Date: Wed, 02 Aug 2023 20:33:51 GMT
Server: Kestrel
WWW-Authenticate: Bearer
```

完美，请求以 **401 Unauthorized** 状态码被拒绝，正如它应该的那样。

让我们看看现在如何获得一个用于认证我们请求的访问令牌。

### **步骤4: 生成一个访问令牌**

通常，访问令牌由一个授权服务器生成，在将你的应用部署到生产环境之前，你肯定需要一个。

但为了简单起见，让我们使用内置的 [dotnet user-jwts 工具](https://learn.microsoft.com/aspnet/core/security/authentication/jwt-authn) 来快速生成一个令牌，特别是一个JWT，直接在我们的计算机上。

所以，停止你的应用并在终端中运行这个：

```bat
dotnet user-jwts create
```

你会得到类似这样的东西（为简洁起见，缩短了令牌）：

```bat
New JWT saved with ID 'a1f35af1'.
Name: julio

Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6Imp1bGlv...
```

这个长字符串是一个JWT，它包含了一些基本的声明，适用于本地开发。

如果你用像 [jwt.ms](https://jwt.ms) 这样的页面对其进行解码，你会看到类似这样的东西（为简洁起见，去掉了头部和签名）：

```json
{
  "unique_name": "julio",
  "sub": "julio",
  "jti": "a1f35af1",
  "aud": [
    "http://localhost:26691",
    "https://localhost:44374",
    "http://localhost:5026",
    "https://localhost:7109"
  ],
  "nbf": 1691011790,
  "exp": 1698960590,
  "iat": 1691011791,
  "iss": "dotnet-user-jwts"
}
```

所以，你获得了一个JWT，它颁发给了你（julio），适用于你的API配置的任何URL，由dotnet-user-jwts工具颁发。

为了与这个JWT相匹配，你执行的命令还为你的 **appsettings.Development.json** 文件添加了新的承载方案配置：

```json
"Authentication": {
  "Schemes": {
    "Bearer": {
      "ValidAudiences": [
        "http://localhost:26691",
        "https://localhost:44374",
        "http://localhost:5026",
        "https://localhost:7109"
      ],
      "ValidIssuer": "dotnet-user-jwts"
    }
  }
}
```

### **步骤5: 使用访问令牌**

有了新的JWT，修改你的 games.http 文件以包含带JWT的Authorization头：

```
GET http://localhost:5026/playergames
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6Imp1bGlv...
```

再次启动你的应用并在 .http 文件中点击 **Send Request**。

现在你应该得到这个：

```bat
HTTP/1.1 200 OK
Connection: close
Content-Type: application/json; charset=utf-8
Date: Wed, 02 Aug 2023 21:43:55 GMT
Server: Kestrel
Transfer-Encoding: chunked

{
  "player1": [
    "Street Fighter II",
    "Minecraft"
  ],
  "player2": [
    "Forza Horizon 5",
    "FIFA 23"
  ]
}
```

成功！

现在请求被认证过，你得到了 **200 OK**，以及JWT中玩家的游戏列表。

任务完成。
