---
pubDatetime: 2026-09-22T08:02:00+08:00
title: "ASP.NET Core CORS 配置顺序与生产排错"
description: "用官方文档和 CorsService 源码核对 CORS 中间件的顺序要求与凭证策略的报错位置，再处理 CDN 缓存与反向代理只在生产暴露的两个问题，附 curl 验证与排错对照表。"
tags: ["ASP.NET Core", "CORS", ".NET 10", "Web API", "安全"]
slug: "aspnet-core-cors-order-and-production-traps"
ogImage: "../../assets/1078/01-cover.jpg"
source: "https://codewithmukesh.com/blog/cors-in-aspnet-core/"
---

前端的登录表单发到 `https://api.acme.com/auth/login`，浏览器控制台里是一行每个 .NET 开发者都见过的错误：

```text
Access to fetch at 'https://api.acme.com/auth/login' from origin
'https://app.acme.com' has been blocked by CORS policy:
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

同一个请求在 Postman 里返回 200，部署状态健康，接口代码也没有问题。浏览器做的正是它该做的事，要改的是服务端。

Mukesh Murugan 在 [CORS in ASP.NET Core (.NET 10)](https://codewithmukesh.com/blog/cors-in-aspnet-core/) 里把这件事拆成了三层：CORS 到底保护谁、「配置」本身怎么写、以及只在真实基础设施前面才暴露的缓存与代理问题。他的判断很直接——中间件顺序写错和 `AllowAnyOrigin` 撞上 `AllowCredentials`，是生产环境里最常出现的两类 CORS 故障。

下面的重述保留了这个结构，并补上两处原文没有展开的内容：一是把 `Vary: Origin` 的判定逻辑对着 [aspnetcore 源码](https://github.com/dotnet/aspnetcore/blob/main/src/Middleware/CORS/src/Infrastructure/CorsService.cs)逐行核对，二是修正原文关于 `dotnet test` 的一处说法。

## CORS 不管什么

先把边界说清楚，后面的每个配置决定都由它推导出来。

源（origin）是协议、主机、端口的三元组。`https://app.acme.com`、`http://app.acme.com`、`https://app.acme.com:8443` 是三个不同的源。同源策略（Same-Origin Policy）从 1995 年就在浏览器里生效：A 源的页面上的 JavaScript 读不到 B 源的响应。没有它，`evil.com` 上的页面可以在你已登录的情况下 `fetch('https://bank.com/account')` 并把余额带走。

现代应用几乎必然是跨源的，SOP 会挡掉所有正常前端。CORS 就是「受控地开洞」：服务端用响应头告诉浏览器，哪些来源可以读我的响应、允许哪些方法和请求头。

这里有两个必须同时记住的事实：

- **执行者是浏览器，服务端只表达意图。** 服务端返回 `Access-Control-Allow-Origin: https://app.acme.com`，是给浏览器看的许可条；真正的拦截发生在浏览器里。
- **非浏览器客户端完全不受影响。** Postman、curl、Python 脚本、另一个服务调用你的 API 时，没有任何一层在执行 CORS。这正是「Postman 通、浏览器不通」的原因，也意味着 **CORS 不是 API 的安全边界**。

再往下分一层，跨源请求按是否触发预检分成两类，区别在于真实请求会不会被发出去：

|          | 触发条件                                                                                                                                                                                                                       | 真实请求是否发出                           |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| 简单请求 | 方法是 `GET`/`HEAD`/`POST`；脚本只设置了 `Accept`、`Accept-Language`、`Content-Language`、`Range`、`Content-Type` 这类安全列表头；`Content-Type` 为 `application/x-www-form-urlencoded`、`multipart/form-data` 或 `text/plain` | 直接发出。浏览器只拦响应，不拦请求         |
| 预检请求 | 带 JSON 体的 `POST`、任意 `PUT`/`DELETE`、带 `Authorization` 头等                                                                                                                                                              | 浏览器先发 `OPTIONS`，预检通过才发真实请求 |

这张表解释了一个容易被忽略的差别：简单请求的副作用可能已经落地，只是前端读不到响应；预检请求失败则连真实请求都不会发出去。这也是为什么 POST 订单这种接口，认证和校验一个都不能省。

## 三步配置，顺序写错就会出现假的 CORS 错误

每个支持 CORS 的 ASP.NET Core 应用都是同样的三步。

第一步，注册策略：

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddCors(options =>
{
    options.AddPolicy("AcmeFrontend", policy =>
    {
        policy.WithOrigins("https://app.acme.com")
              .WithMethods("GET", "POST", "PUT", "DELETE")
              .WithHeaders("Authorization", "Content-Type")
              .SetPreflightMaxAge(TimeSpan.FromMinutes(10));
    });
});
```

这里用显式的 `WithMethods` 与 `WithHeaders`，而不是 `AllowAnyMethod`/`AllowAnyHeader`。两者的功能差别不大，但配置本身变成了一份意图声明：这个前端只用这些方法和这些头。哪天冒出一个没人加过的方法，这个信号值得查。

第二步，挂中间件——这一步的次序是硬要求：

```csharp
var app = builder.Build();

app.UseRouting();
app.UseCors("AcmeFrontend");
app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();
app.Run();
```

[官方文档](https://learn.microsoft.com/aspnet/core/security/cors?view=aspnetcore-10.0)对此的原话是：`UseCors` 必须放在 `UseRouting` 之后、`UseAuthorization` 之前。两个位置各有理由：

- 在 `UseRouting` 之后，是因为端点级策略（`RequireCors`、`[EnableCors]`）依赖已经解析出的端点元数据。
- 在 `UseAuthorization` 之前，是为了让未通过的请求也带上 CORS 头。

第二个理由对应的正是最常见的误诊。预检是一个 `OPTIONS` 请求，浏览器不会在它上面带凭证。如果认证中间件排在 CORS 前面，它会直接返回 401，CORS 中间件根本没机会写响应头，浏览器最后报给你的是 CORS 错误。你在错误信息里找不到任何和认证有关的线索，于是开始怀疑来源列表写错了。

第三步，把策略应用上去。三种方式选一种，保持一致：

```csharp
// 全局
app.UseCors("AcmeFrontend");

// 端点
app.MapGet("/api/products", (IProductService products, CancellationToken ct)
        => products.GetAllAsync(ct))
   .RequireCors("AcmeFrontend");

// 控制器
[EnableCors("AcmeFrontend")]
public class ProductsController : ControllerBase { }
```

官方文档在这里有两条明确提醒，值得单独记住：`[EnableCors]` 与中间件同时启用时**两个策略都会生效**，所以不要在同一个应用里混用两者；另外 `[DisableCors]` 关不掉由 `RequireCors` 开启的 CORS。

### 三种作用域怎么选

| 作用域                                  | 适用场景                                       | 代价                                   |
| --------------------------------------- | ---------------------------------------------- | -------------------------------------- |
| 默认策略 `AddDefaultPolicy`             | 单前端 + 单 API 的内部工具                     | 只有一个位置。第二个前端出现时没地方插 |
| 命名策略 `AddPolicy("Name")`            | 公有站点、管理后台、移动 Web 打在同一个 API 上 | 需要显式命名并在使用时引用             |
| 端点策略 `RequireCors` / `[EnableCors]` | 单个端点需要不同来源，例如公开 webhook 接收器  | 新端点容易漏配，必须专门测 `OPTIONS`   |

按逻辑客户端各配一个命名策略最省事：`AcmeFrontend`、`AcmeAdmin`、`AcmePublic`。默认策略槽位看起来整洁，但它是为「只有一个前端」这个不会长期成立的前提准备的。

## 来源列表应该来自配置，而不是代码

演示项目里把来源硬编码在 `Program.cs` 没问题，生产环境里同一个二进制要跑在 dev、staging、prod 三套环境上，来源列表就不能靠重新编译来改。

`appsettings.Production.json`：

```json
{
  "Cors": {
    "AcmeFrontend": {
      "Origins": ["https://app.acme.com", "https://admin.acme.com"],
      "AllowCredentials": true,
      "PreflightMaxAgeSeconds": 600
    }
  }
}
```

`Program.cs`：

```csharp
var corsSection = builder.Configuration.GetSection("Cors:AcmeFrontend");
var origins = corsSection.GetSection("Origins").Get<string[]>() ?? [];
var allowCredentials = corsSection.GetValue<bool>("AllowCredentials");
var maxAge = corsSection.GetValue<int>("PreflightMaxAgeSeconds");

builder.Services.AddCors(options =>
{
    options.AddPolicy("AcmeFrontend", policy =>
    {
        policy.WithOrigins(origins)
              .WithMethods("GET", "POST", "PUT", "DELETE", "PATCH")
              .WithHeaders("Authorization", "Content-Type", "X-Correlation-Id")
              .SetPreflightMaxAge(TimeSpan.FromSeconds(maxAge));

        if (allowCredentials)
        {
            policy.AllowCredentials();
        }
    });
});
```

Development 那份列 `https://localhost:5173`（Vite）或 `https://localhost:4200`（Angular CLI），staging 和 prod 只列真实部署的来源。

开发期还有一个更省事的选择：如果前端和后端只差一个端口，直接用前端 dev server 的代理把请求转给后端，浏览器看到的就是同源请求，CORS 全程不参与。这条路适合本地联调，但不要带进生产——生产环境里前端和 API 通常真的在不同域上。

## 通配符子域与动态谓词

多租户场景下每个客户拿到 `https://acme.tenant.myapp.com` 这样的子域，来源列表无法枚举。.NET 给了两个口子，风险差别很大。

**通配符子域**：`*` 必须真的写在 origin 字符串里，单独调用 `SetIsOriginAllowedToAllowWildcardSubdomains()` 没有任何效果，这一点官方文档写得很明确。协议和端口仍然精确匹配，`https://*.myapp.com` 不会接受 `http://acme.myapp.com`。

```csharp
options.AddPolicy("TenantApps", policy =>
{
    policy.WithOrigins("https://*.myapp.com")
          .SetIsOriginAllowedToAllowWildcardSubdomains()
          .WithMethods("GET", "POST", "PUT", "DELETE")
          .WithHeaders("Authorization", "Content-Type");
});
```

要说清楚的是，这等于把信任边界扩大到该域下的所有子域。任何能被第三方控制的子域——客户自建的 CNAME、被遗忘的 staging 主机、市场部门指向外部供应商的域名——都会继承这份 CORS 授权。子域接管就从「一次尴尬事故」升级成「API 被绕过」。只有子域全部由你自己的部署流水线创建时才值得用。

**动态谓词**：`SetIsOriginAllowed` 接受 `Func<string, bool>`，控制力最强，也最容易割到自己。

```csharp
options.AddPolicy("TenantApps", policy =>
{
    policy.SetIsOriginAllowed(origin =>
              Uri.TryCreate(origin, UriKind.Absolute, out var uri)
              && uri.Scheme == Uri.UriSchemeHttps
              && uri.Host.EndsWith(".myapp.com", StringComparison.OrdinalIgnoreCase))
          .AllowAnyHeader()
          .AllowAnyMethod();
});
```

两条纪律：

- **解析 origin，不要做字符串匹配。** `origin.Contains("myapp.com")` 会痛快地接受 `https://myapp.com.evil.com`。构造成 `Uri`，把主机和协议分开判断。
- **谓词的数据来源必须是部署期决策。** 从管理后台能编辑的数据库列里读允许来源，等于把一次管理员会话失陷变成永久的 CORS 绕过。

## 凭证：AllowAnyOrigin 撞上 AllowCredentials 是运行时报错

CORS 里的「凭证」指 cookie、HTTP 认证头、TLS 客户端证书。浏览器不会在跨源请求上自动带这些，除非三件事同时成立：

- 前端显式声明：`fetch(url, { credentials: 'include' })` 或 `axios.defaults.withCredentials = true`。
- 服务端返回 `Access-Control-Allow-Credentials: true`。
- 服务端返回的是具体来源，不能是 `*`。

如果同时调用 `AllowAnyOrigin()` 和 `AllowCredentials()`，框架会直接抛异常。这段代码在 `CorsService.EvaluatePolicy` 的开头：

```csharp
if (policy.AllowAnyOrigin && policy.SupportsCredentials)
{
    throw new ArgumentException(Resources.InsecureConfiguration, nameof(policy));
}
```

真正需要留意的是抛出时机：**它在请求时抛，不在启动时抛。** 应用正常启动、健康检查通过，第一个浏览器跨域请求进来才炸。这是框架在替你把关，因为 Fetch 标准本身就禁止通配符来源与凭证并存——否则互联网上任何站点都能借用户的登录态调用你的 API。

正确写法是把来源钉死：

```csharp
options.AddPolicy("AcmeAuthenticated", policy =>
{
    policy.WithOrigins("https://app.acme.com")
          .AllowAnyHeader()
          .AllowAnyMethod()
          .AllowCredentials();
});
```

顺带澄清一个常见混淆：`Authorization: Bearer <jwt>` 严格来说不算 CORS 定义里的凭证，但它的存在会触发预检，所以策略里必须有 `WithHeaders("Authorization")`。而 `AllowCredentials()` 要不要加，取决于 JWT 存在哪里——存在 `localStorage` 里由前端显式附加，不需要；存在 `HttpOnly` cookie 里由浏览器自动发送，就需要。

## 只在生产出现的第一个问题：Vary: Origin

这是最容易通过代码评审、通过所有测试、然后在生产里跨租户泄漏的问题。

`Access-Control-Allow-Origin` 的值取决于请求的 `Origin` 头。任何位于 API 和浏览器之间、按 URL 做键的缓存——输出缓存、响应缓存中间件、CDN、反向代理——都可能把一份带着 `Access-Control-Allow-Origin: https://app.acme.com` 的响应，原样发给来自 `https://admin.acme.com` 的浏览器。

`Vary: Origin` 就是解法，它让缓存按请求的 `Origin` 分键。ASP.NET Core 会替你发这个头，但不是所有情况。源码里的判定是这样的：

```csharp
if (policy.AllowAnyOrigin)
{
    result.AllowedOrigin = CorsConstants.AnyOrigin;
    result.VaryByOrigin = policy.SupportsCredentials;
}
else
{
    var origin = headers.Origin;
    result.AllowedOrigin = origin;
    result.VaryByOrigin = policy.Origins.Count > 1 || !policy.IsDefaultIsOriginAllowed;
}
```

第二行是关键：**只有一个来源、且使用默认匹配函数的策略，`VaryByOrigin` 为 `false`，不发 `Vary: Origin`。** 单独看这是对的——只有一个允许来源，这个头的值只可能有一个，没什么可 vary 的。只有当第二份策略、第二个来源，或某个控制器上的 `[EnableCors]` 让同一个 URL 出现第二个可能值时，它才开始出错，而缓存对此一无所知。

| 配置                              | 是否发出 `Vary: Origin`                   | 风险                                   |
| --------------------------------- | ----------------------------------------- | -------------------------------------- |
| 单一来源 + 默认匹配               | 否                                        | 单独安全；同路由出现第二个策略即失效   |
| 两个及以上来源                    | 是                                        | 框架已正确处理                         |
| `SetIsOriginAllowed` / 通配符子域 | 是（`IsDefaultIsOriginAllowed` 为 false） | 已处理，但缓存键按来源展开，命中率下降 |
| `AllowAnyOrigin()` 且无凭证       | 否                                        | 安全，值是常量 `*`                     |
| `AllowAnyOrigin()` + 凭证         | 不适用                                    | 直接抛异常                             |

处理方式有三条：

- **把 `UseCors` 放在 `UseResponseCaching` 和 `UseOutputCache` 之前。** CORS 必须先写完响应头，后面才有中间件决定要不要缓存这份响应。
- **带凭证的响应根本不要缓存。** 策略上有 `AllowCredentials()` 就说明响应是用户专属的，标 `no-store` 最省心。
- **在边缘验证，而不是在应用里。** 用两个不同的 `Origin` 各请求一次，比较返回的头：

```bash
curl -sI https://api.acme.com/api/products \
  -H "Origin: https://app.acme.com" | grep -i "access-control-allow-origin\|vary\|age"
curl -sI https://api.acme.com/api/products \
  -H "Origin: https://admin.acme.com" | grep -i "access-control-allow-origin\|vary\|age"
```

第二次返回了第一个来源，说明缓存条目已经被污染。非零的 `Age` 配上不匹配的来源，基本可以确诊。

## 只在生产出现的第二个问题：重复的响应头

容器化的 API 通常跑在 nginx、YARP、Ingress 或 API 网关后面，而这些层自己也能加 CORS 头。当代理加了 `Access-Control-Allow-Origin`，ASP.NET Core 也加了一次，浏览器看到两个值，直接把整个响应拒掉：

```text
The 'Access-Control-Allow-Origin' header contains multiple values
'https://app.acme.com, https://app.acme.com', but only one is allowed.
```

注意两个值往往完全相同——两层都配置正确、彼此一致，响应照样失败。这就是它特别耗时的原因。规则很简单：**CORS 只由一层负责。** 选应用层，把 nginx 里的 `add_header` 删掉，让策略和依赖它的代码一起进版本控制。只有在代理后面挂着一个自己不会做 CORS 的服务时，才把这件事交给代理。

两个相关的代理坑：

- **`OPTIONS` 根本没到应用。** 有些网关自己应答或直接丢弃 `OPTIONS`。如果预检返回的东西不像你的应用会发出的，就在容器端口上直接 curl 应用做对比。
- **TLS 终止导致协议不匹配。** 代理终止 HTTPS 后以明文 HTTP 转发，应用拼出的重定向地址协议是错的，来源也就匹配不上。在 `UseCors` 之前接上 `UseForwardedHeaders` 并启用 `ForwardedHeaders.XForwardedProto`。

## 七种能稳定复现的配置错误

| 配置错误                                                         | 表现                                                                   | 修法                                                          |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------- |
| 生产环境用 `AllowAnyOrigin()`                                    | 开发期最快「修好」报错的方式，然后被带进生产                           | 按环境钉住具体来源                                            |
| `AllowAnyOrigin` + `AllowCredentials`，或干脆反射请求的 `Origin` | 后者绕过了框架检查，效果等同                                           | 换成 `WithOrigins(...)` 具体列表                              |
| 允许来源来自运行时可编辑的数据                                   | 一次管理员失陷变成永久 CORS 绕过                                       | 视为部署期设置                                                |
| `UseCors` 放在 `UseAuthentication` 之后                          | 预检 `OPTIONS` 被 401 拦掉，浏览器报成 CORS 错误                       | `UseRouting → UseCors → UseAuthentication → UseAuthorization` |
| 忘记 `WithExposedHeaders`                                        | 自定义响应头在 DevTools 里能看到，`response.headers.get()` 却是 `null` | 显式暴露，例如 `Content-Disposition`、`X-Total-Count`         |
| 不设 `SetPreflightMaxAge`                                        | 每次触发 CORS 的调用都多一次 `OPTIONS`                                 | 设 600 秒起步                                                 |
| 把 CORS 当安全边界                                               | 浏览器读不到响应，但脚本照样能下单                                     | 认证、授权、校验、限流一个都不能省                            |

有一项值得单独展开，因为它不像 CORS 问题：**跨源下载文件时文件名丢失**。`Content-Disposition` 不在浏览器默认暴露的安全列表里，所以下载能成功，存下来的却是一个没有扩展名的 `download`：

```csharp
options.AddPolicy("AcmeFrontend", policy =>
{
    policy.WithOrigins("https://app.acme.com")
          .WithExposedHeaders("Content-Disposition", "X-Total-Count", "X-Correlation-Id");
});
```

排查这类问题时要记住那个割裂感：头就在网络上，DevTools 里看得见，但前端代码读不到。浏览器默认只暴露 `Cache-Control`、`Content-Language`、`Content-Length`、`Content-Type`、`Expires`、`Last-Modified`、`Pragma` 这几个。

## 验证：一条 curl 加一组集成测试

预检是最快的复现方式，不需要浏览器：

```bash
curl -i -X OPTIONS https://api.acme.com/api/products \
  -H "Origin: https://app.acme.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: authorization, content-type"
```

配置正确时返回 `204 No Content`（或 `200 OK`），并带上 `Access-Control-Allow-Origin`、`Access-Control-Allow-Methods` 和 `Access-Control-Allow-Headers`。

把预检固化成测试更划算，每个允许来源一条、再加一条已知被拒绝的来源：

```csharp
[Fact]
public async Task Preflight_FromAllowedOrigin_Returns204()
{
    using var factory = new WebApplicationFactory<Program>();
    using var client = factory.CreateClient();

    var request = new HttpRequestMessage(HttpMethod.Options, "/api/products");
    request.Headers.Add("Origin", "https://app.acme.com");
    request.Headers.Add("Access-Control-Request-Method", "POST");
    request.Headers.Add("Access-Control-Request-Headers", "authorization");

    var response = await client.SendAsync(request);

    Assert.Equal(HttpStatusCode.NoContent, response.StatusCode);
    Assert.Contains(
        "https://app.acme.com",
        response.Headers.GetValues("Access-Control-Allow-Origin"));
}
```

两个和 CORS 无关但会先把你拦住的坑。第一个是 `WebApplicationFactory<Program>` 需要 `Program` 从测试项目可见，而顶级语句生成的类是 `internal`，在 `Program.cs` 末尾加一行 `public partial class Program { }` 或配置 `InternalsVisibleTo` 即可，否则报的编译错误和 CORS 毫无关系。

第二个是运行方式。原文的说法是：xUnit v3 的测试项目本身就是可执行文件，运行器编译在内，所以用 `dotnet run --project YourProject.Tests` 而不是 `dotnet test`，理由是「.NET 10 SDK 废弃了 `dotnet test` 依赖的 VSTest 桥」。

前半句成立，后半句需要更正。按 [官方迁移指南](https://learn.microsoft.com/dotnet/core/testing/migrating-vstest-microsoft-testing-platform)，.NET 10 SDK 只是为 Microsoft.Testing.Platform（MTP）提供了**原生** `dotnet test` 支持，而且需要显式开启——在 `global.json` 里加一行：

```json
{
  "test": {
    "runner": "Microsoft.Testing.Platform"
  }
}
```

没有这一行，`dotnet test` 仍然走 VSTest 路径，VSTest 也并没有被移除。所以结论应该改成：xUnit v3 项目用 `dotnet run --project` 是最直接的方式；想继续用 `dotnet test`，就在 `global.json` 里显式切到 MTP，此时 `-t`、`--filter`、`--logger` 这些参数需要按 MTP 的对应选项替换。

## 排错对照表

| 你看到的错误                                                                                           | 先检查什么                                                                                                     |
| ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| `No 'Access-Control-Allow-Origin' header is present`                                                   | 有没有策略命中这个来源；`UseCors` 是否在管道里、是否排在了认证之后                                             |
| `The CORS protocol does not allow specifying a wildcard (any) origin and credentials at the same time` | 同时开了 `AllowAnyOrigin()` 和 `AllowCredentials()`；注意这是请求时报错，不是启动时报错                        |
| `Response to preflight request doesn't pass access control check: It does not have HTTP ok status`     | `OPTIONS` 返回了 4xx/5xx：认证中间件跑到 CORS 前面、全局异常处理把 CORS 错误变成 500，或路由没匹配上 `OPTIONS` |
| `Request header field X-Custom-Header is not allowed`                                                  | 前端发了策略里没声明的头，补进 `WithHeaders(...)`                                                              |
| 自定义响应头在 JS 里读不到                                                                             | 头不在安全列表里，补进 `WithExposedHeaders(...)`                                                               |
| `header contains multiple values`                                                                      | 代理和应用都在加 CORS 头，只保留一层                                                                           |
| Postman 正常、浏览器报错                                                                               | 这是预期行为，Postman 不是浏览器，修在服务端                                                                   |

## 结语

CORS 配置得好时会彻底消失：前端正常工作，API 保持解耦，浏览器做它该做的事。配置得随意时，它就变成团队第一次上线那周被搜索最多的那个报错。

需要长期记住的模型只有一句：**CORS 是服务端与浏览器之间的契约，不是 API 前面的防火墙。** 具体到 ASP.NET Core，落到四个动作上——按环境钉住来源、用命名策略、把 `UseCors` 放在 `UseRouting` 之后与 `UseAuthentication` 之前、永远不要同时开 `AllowAnyOrigin()` 和 `AllowCredentials()`。然后在前面还有缓存或代理时，额外确认 `Vary: Origin` 在边缘确实存在，并且只有一层在写 CORS 头。

认证、限流、输入校验和每个端点上的授权，仍然要各自做好。CORS 只是安全姿态里的一层。

Aide Hub 会继续整理这类把框架行为核对到源码、再落到生产排错步骤的实践，覆盖 .NET、AI 助手与软件工程。

## 参考

- [CORS in ASP.NET Core (.NET 10) - Cross-Origin Done Right](https://codewithmukesh.com/blog/cors-in-aspnet-core/)（原文，Mukesh Murugan）
- [Enable Cross-Origin Requests (CORS) in ASP.NET Core](https://learn.microsoft.com/aspnet/core/security/cors?view=aspnetcore-10.0)
- [CorsService.cs（aspnetcore 源码）](https://github.com/dotnet/aspnetcore/blob/main/src/Middleware/CORS/src/Infrastructure/CorsService.cs)
- [Migrate from VSTest to Microsoft.Testing.Platform (MTP)](https://learn.microsoft.com/dotnet/core/testing/migrating-vstest-microsoft-testing-platform)
- [Cross-Origin Resource Sharing (CORS) - MDN](https://developer.mozilla.org/docs/Web/HTTP/CORS)
- [Fetch Standard - CORS protocol](https://fetch.spec.whatwg.org/#http-cors-protocol)
