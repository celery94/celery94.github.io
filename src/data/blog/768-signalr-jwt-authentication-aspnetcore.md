---
pubDatetime: 2026-04-30T12:32:00+08:00
title: "在 ASP.NET Core 中为 SignalR Hub 添加 JWT 身份认证"
description: "SignalR 默认允许任意客户端连接 Hub，不做身份验证。本文从后端配置、Hub 授权、服务端流式推送，到 JavaScript 和 .NET 客户端接入，完整演示如何用 JWT 保护 SignalR 连接，并整理了六条生产环境安全实践。"
tags: ["ASP.NET Core", "SignalR", "JWT", "Authentication", "CSharp"]
slug: "signalr-jwt-authentication-aspnetcore"
ogImage: "../../assets/768/01-cover.png"
source: "https://antondevtips.com/blog/how-to-add-jwt-authentication-to-signalr-hubs-in-aspnetcore"
---

![在 ASP.NET Core 中为 SignalR Hub 添加 JWT 身份认证](../../assets/768/01-cover.png)

SignalR 让实时通信变得很简单——推送通知、流式数据、在线状态，几行代码就能跑起来。但默认情况下，任何客户端都可以连接你的 Hub，调用任何方法，接收任何消息，完全不需要身份验证。

在生产环境里这显然不够。你需要知道谁连进来了，哪些操作只有特定角色才能触发，还要能在日志里留下审计记录。JWT 是解决这个问题的标准方式，它同时支持 WebSocket、Server-Sent Events 和 Long Polling 三种传输协议。

这篇文章按照以下顺序展开：

- 为什么 SignalR 不能直接用 HTTP Header 传 Token
- 服务端配置 JWT 认证
- 构建带认证的 SignalR Hub 并实现服务端流
- Hub 方法上的基于角色的授权
- JavaScript 客户端接入
- .NET 客户端接入
- 六条生产安全实践

## 为什么不能只用 Authorization Header

标准 REST API 里，客户端把 JWT 放进 `Authorization: Bearer <token>` 请求头就行了。SignalR 在某些传输协议下不支持这样做。

浏览器原生的 WebSocket API 和 EventSource（Server-Sent Events）不允许设置自定义请求头。当客户端通过这两种方式连接 Hub 时，SignalR JavaScript 客户端会自动把 token 追加到 URL 查询参数里：

```
/hubs/stocks?access_token=<token>
```

这意味着服务端需要额外配置，从查询字符串里读取 token，而不是依赖默认的 Header 解析逻辑。

## 配置 JWT 认证

先注册 SignalR 服务，并确保中间件顺序正确：

```csharp
builder.Services.AddSignalR();

var app = builder.Build();

app.UseAuthentication();
app.UseAuthorization();

// 挂载 Hub
app.MapHub<StockPriceHub>("/hubs/stocks");
```

然后配置 JWT Bearer 认证，关键是加上 `OnMessageReceived` 事件处理器，让它从查询字符串中提取 token：

```csharp
builder.Services.AddAuthentication(options =>
{
    options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
    options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
})
.AddJwtBearer(options =>
{
    var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(authConfig.Key));

    options.TokenValidationParameters = new TokenValidationParameters
    {
        ValidateIssuer = true,
        ValidateAudience = true,
        ValidateLifetime = true,
        ValidateIssuerSigningKey = true,
        ValidIssuer = authConfig.Issuer,
        ValidAudience = authConfig.Audience,
        IssuerSigningKey = key
    };

    options.Events = new JwtBearerEvents
    {
        OnMessageReceived = context =>
        {
            var accessToken = context.Request.Query["access_token"];
            var path = context.HttpContext.Request.Path;

            if (!string.IsNullOrEmpty(accessToken) &&
                path.StartsWithSegments("/hubs"))
            {
                context.Token = accessToken;
            }

            return Task.CompletedTask;
        }
    };
});
```

几个要点：

- `OnMessageReceived` 在 JWT 中间件校验 token 之前触发，是注入 token 的正确时机
- token 提取范围限定在 `/hubs` 路径下，避免其他端点也从查询字符串读 token
- .NET 客户端（控制台应用、后台服务）可以正常设置 Header，不需要这个处理器

## 构建带认证的 Hub

### Step 1：创建 Hub 类

用 `[Authorize]` 标注整个 Hub 类，要求所有连接必须携带有效 JWT。没有合法 token 的请求会直接收到 401 Unauthorized，连接被拒绝。

```csharp
[Authorize]
public class StockPriceHub(
    StockService stockService,
    ILogger<StockPriceHub> logger) : Hub
{
    // 用 ConnectionId 跟踪每个客户端的订阅状态
    private static readonly ConcurrentDictionary<string, HashSet<string>> Subscriptions = new();

    public override Task OnConnectedAsync()
    {
        var userId = Context.User?.FindFirst(ClaimTypes.Email)?.Value ?? "unknown";
        logger.LogInformation("User '{User}' connected with ConnectionId: {ConnectionId}",
            userId, Context.ConnectionId);

        Subscriptions[Context.ConnectionId] = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        return base.OnConnectedAsync();
    }

    public override Task OnDisconnectedAsync(Exception? exception)
    {
        var userId = Context.User?.FindFirst(ClaimTypes.Email)?.Value ?? "unknown";
        logger.LogInformation("User '{User}' disconnected. ConnectionId: {ConnectionId}",
            userId, Context.ConnectionId);

        Subscriptions.Remove(Context.ConnectionId);

        return base.OnDisconnectedAsync(exception);
    }
}
```

在 Hub 内部，通过 `Context.User` 就能拿到当前连接用户的所有 JWT Claims——和在 Controller 或 Minimal API 里的用法完全一致。

### Step 2：订阅与取消订阅

客户端调用这两个方法来选择关注哪些股票代码：

```csharp
public async Task Subscribe(string symbol)
{
    var normalizedSymbol = symbol.ToUpperInvariant();
    var availableSymbols = StockService.GetAvailableSymbols();

    if (!availableSymbols.Contains(normalizedSymbol))
    {
        await Clients.Caller.SendAsync("Error",
            $"Symbol '{symbol}' is not available. Available symbols: {string.Join(", ", availableSymbols)}");
        return;
    }

    if (Subscriptions.TryGetValue(Context.ConnectionId, out var symbols))
    {
        symbols.Add(normalizedSymbol);
    }

    var userId = Context.User?.FindFirst(ClaimTypes.Email)?.Value;
    logger.LogInformation("User '{User}' subscribed to {Symbol}", userId, normalizedSymbol);

    await Clients.Caller.SendAsync("Subscribed", normalizedSymbol);
}

public async Task Unsubscribe(string symbol)
{
    var normalizedSymbol = symbol.ToUpperInvariant();

    if (Subscriptions.TryGetValue(Context.ConnectionId, out var symbols))
    {
        symbols.Remove(normalizedSymbol);
    }

    var userId = Context.User?.FindFirst(ClaimTypes.Email)?.Value;
    logger.LogInformation("User '{User}' unsubscribed from {Symbol}", userId, normalizedSymbol);

    await Clients.Caller.SendAsync("Unsubscribed", normalizedSymbol);
}
```

收到无效代码时，用 `Clients.Caller.SendAsync` 把错误信息发回给当前调用方，其他客户端不受影响。

### Step 3：服务端流式推送

SignalR 支持服务端流，方法返回 `IAsyncEnumerable<T>` 即可。客户端发起订阅后，服务器持续推送股价数据：

```csharp
public async IAsyncEnumerable<StockPriceEvent> StreamStockPrices(
    [EnumeratorCancellation] CancellationToken cancellationToken)
{
    HashSet<string> subscribedSymbols = Subscriptions.TryGetValue(Context.ConnectionId, out var symbols)
        ? new HashSet<string>(symbols, StringComparer.OrdinalIgnoreCase)
        : new HashSet<string>(StringComparer.OrdinalIgnoreCase);

    var userId = Context.User?.FindFirst(ClaimTypes.Email)?.Value;

    await foreach (var stockPrice in stockService.StreamPrices(subscribedSymbols, cancellationToken))
    {
        yield return stockPrice;
    }
}
```

如果用户没有订阅任何代码，`subscribedSymbols` 为空，`StockService` 会推送所有股票的数据。`StockService` 注册为 Singleton，所有连接共享同一个价格数据源。

## 基于角色的方法级授权

`[Authorize]` 标注在类上，要求所有用户都已认证。如果某些操作只有管理员才能执行，可以在具体方法上加授权策略：

```csharp
[Authorize("Admin")]
public async Task BroadcastMessage(string message)
{
    var adminEmail = Context.User?.FindFirst(ClaimTypes.Email)?.Value;
    logger.LogInformation("Admin '{Admin}' broadcasting message: {Message}", adminEmail, message);

    await Clients.All.SendAsync("SystemMessage", message);
}

[Authorize("Admin")]
public int GetConnectedUsersCount()
{
    return Subscriptions.Count;
}
```

`"Admin"` 策略在 `Program.cs` 中注册：

```csharp
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("Admin", policy => policy.RequireRole("Admin"));
});
```

如果非 Admin 用户调用这两个方法，SignalR 会向调用方返回错误，但连接保持打开，不影响其他方法的调用。

有时授权逻辑比角色检查更复杂，也可以在方法内部直接读取 Claims：

```csharp
public async Task SomeMethod()
{
    var email = Context.User?.FindFirst(ClaimTypes.Email)?.Value;
    var isAdmin = Context.User?.IsInRole("Admin") ?? false;
    var userId = Context.User?.FindFirst(ClaimTypes.NameIdentifier)?.Value;

    if (isAdmin)
    {
        // Admin 专属逻辑
    }
}
```

## JavaScript 客户端接入

### Step 1：安装 SignalR 客户端包

```bash
npm install @microsoft/signalr
```

### Step 2：获取 JWT Token

连接 Hub 之前，先通过登录端点取得 token：

```javascript
const API_URL = 'http://localhost:5000';
let token = null;

async function login(email, password) {
    const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });

    if (response.ok) {
        const data = await response.json();
        token = data.token;
    }
}
```

### Step 3：建立连接

用 `accessTokenFactory` 提供 token。SignalR 在每次 HTTP 请求（包括 WebSocket 握手）之前都会调用这个工厂函数：

```javascript
let connection = new signalR.HubConnectionBuilder()
    .withUrl(`${API_URL}/hubs/stocks`, {
        accessTokenFactory: () => token
    })
    .withAutomaticReconnect()
    .configureLogging(signalR.LogLevel.Information)
    .build();

await connection.start();
```

`withAutomaticReconnect()` 开启断线自动重连，每次重连时都会再次调用 `accessTokenFactory`。如果 token 有过期风险，可以在工厂函数里刷新：

```javascript
accessTokenFactory: async () => {
    if (isTokenExpired(token)) {
        token = await refreshToken();
    }
    return token;
}
```

### Step 4：注册事件处理器并调用 Hub 方法

```javascript
// 处理服务器推送的事件
connection.on('Subscribed', (symbol) => {
    console.log('Subscribed to:', symbol);
});

connection.on('Error', (message) => {
    console.error('Hub error:', message);
});

connection.on('SystemMessage', (message) => {
    console.log('System:', message);
});

connection.onclose(() => {
    console.log('Disconnected from hub');
});

// 调用 Hub 方法
const symbols = await connection.invoke('GetAvailableSymbols');
await connection.invoke('Subscribe', 'MSFT');
await connection.invoke('Subscribe', 'AAPL');
await connection.invoke('Unsubscribe', 'AAPL');
```

### Step 5：接收流式数据

```javascript
const subscription = connection.stream('StreamStockPrices')
    .subscribe({
        next: (event) => {
            console.log(`${event.symbol}: $${event.price} at ${event.timestamp}`);
        },
        error: (err) => {
            console.error('Stream error:', err);
        },
        complete: () => {
            console.log('Stream completed');
        }
    });

// 停止接收时：
subscription.dispose();
```

## .NET 客户端接入

从 .NET 应用（控制台、后台服务、微服务）连接 Hub，安装客户端包：

```bash
dotnet add package Microsoft.AspNetCore.SignalR.Client
```

.NET 客户端可以直接设置 HTTP Header，不需要查询字符串传 token。用 `AccessTokenProvider` 属性提供 token：

```csharp
using Microsoft.AspNetCore.SignalR.Client;

var token = "your-jwt-token-here"; // 从登录端点获取

var connection = new HubConnectionBuilder()
    .WithUrl("https://localhost:5001/hubs/stocks", options =>
    {
        options.AccessTokenProvider = () => Task.FromResult(token)!;
    })
    .WithAutomaticReconnect()
    .Build();

// 注册事件处理
connection.On<string>("SystemMessage", message =>
{
    Console.WriteLine($"System: {message}");
});

// 启动连接
await connection.StartAsync();
Console.WriteLine("Connected to hub");

// 订阅并开启流
await connection.InvokeAsync("Subscribe", "MSFT");

var stream = connection.StreamAsync<StockPriceEvent>("StreamStockPrices");

await foreach (var price in stream)
{
    Console.WriteLine($"{price.Symbol}: ${price.Price} at {price.Timestamp:HH:mm:ss}");
}

record StockPriceEvent(string Id, string Symbol, decimal Price, DateTime Timestamp);
```

## 生产环境安全实践

### 1. 防止 Token 写入日志

浏览器用 WebSocket 或 SSE 连接时，token 出现在 URL 查询字符串里。ASP.NET Core 默认在 `Information` 级别记录完整请求 URL，这意味着 JWT token 可能大量出现在日志文件中。

通过调整日志级别来屏蔽这类请求日志：

```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore.Hosting": "Warning",
      "Microsoft.AspNetCore.Routing": "Warning"
    }
  }
}
```

### 2. 强制使用 HTTPS

token 在查询字符串中传输，没有 HTTPS 加密，网络上的任何人都能看到明文 token。生产环境中：

```csharp
app.UseHttpsRedirection();
```

### 3. 正确配置 CORS

SignalR 需要特定的 CORS 设置，只允许已知的前端来源：

```csharp
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowFrontend", policy =>
    {
        policy
            .WithOrigins("https://yourfrontend.com")
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
    });
});
```

不要在生产环境用 `AllowAnyOrigin()`。CORS 对 WebSocket 连接本身不生效，但握手阶段的 HTTP 请求会受到 CORS 保护。

### 4. 处理 Token 过期

JWT 验证只在连接建立时发生一次。WebSocket 连接打开之后，服务器不会持续校验 token 有效性——这意味着持有过期 token 的用户在连接断开前仍然可以接收数据。

用 `CloseOnAuthenticationExpiration` 让服务器在 token 过期时主动关闭连接：

```csharp
app.MapHub<StockPriceHub>("/hubs/stocks", options =>
{
    options.CloseOnAuthenticationExpiration = true;
});
```

客户端配合 `accessTokenFactory` 在重连时自动刷新 token，可以做到无感续期。

### 5. 不要对外暴露 ConnectionId

`ConnectionId` 是每个连接的内部标识符。在 ASP.NET Core 3.0 之后，SignalR 已经引入了独立的 `ConnectionToken` 防止伪造攻击，但仍建议不要在 Hub 方法返回值或 API 响应中主动暴露它。

### 6. 限制消息大小

SignalR 默认最大消息为 32 KB。根据业务需要调整，同时防止恶意客户端发送超大消息耗尽服务器内存：

```csharp
builder.Services.AddSignalR(options =>
{
    options.MaximumReceiveMessageSize = 64 * 1024; // 64 KB
});
```

## 参考

- [How to Add JWT Authentication to SignalR Hubs in ASP.NET Core](https://antondevtips.com/blog/how-to-add-jwt-authentication-to-signalr-hubs-in-aspnetcore) — Anton Martyniuk
- [Authentication and Authorization Best Practices in ASP.NET Core](https://antondevtips.com/blog/authentication-and-authorization-best-practices-in-aspnetcore)
- [Real-Time Server-Sent Events in ASP.NET Core](https://antondevtips.com/blog/real-time-server-sent-events-in-asp-net-core)
