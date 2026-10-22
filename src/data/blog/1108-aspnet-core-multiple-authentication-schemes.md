---
pubDatetime: 2026-10-22T08:39:00+08:00
title: "ASP.NET Core 中同时支持多个认证方案"
description: "迁移身份提供方时，一个 ASP.NET Core BFF 应用里要并存两套 Cookie 认证方案：策略方案按请求分流，OIDC 登录后按声明写入目标方案，控制器再按方案授权，并处理登出与重定向。"
tags: ["ASP.NET Core", "Authentication", "OpenID Connect", "BFF"]
slug: "aspnet-core-multiple-authentication-schemes"
ogImage: "../../assets/1108/01-cover.jpg"
source: "https://damienbod.com/2026/10/12/use-multiple-schemes-in-an-asp-net-core-web-application/"
---

迁移身份提供方时，最容易低估的是过渡期：老用户还留在旧系统，新用户已经走新系统，两边都要访问同一组 API。

Damien Bowden 的做法是让一个 BFF（Backend for Frontend）应用同时保留新旧两套 Cookie 认证方案。请求进来时按 Cookie 选方案，OpenID Connect 登录完成后再把用户写进对应的那套方案。这样已有的授权代码一行都不用改。示例是 Angular 前端加 ASP.NET Core 后端。

背景是他要把一个大型应用迁到新的身份提供方，同时把在用的 OIDC 服务器收敛到一个。与其把多个方案合并成单一 Cookie 默认方案，不如先让多方案并存，等登录回调完成后再决定用哪套——改造量小得多。

核心结论一句话：**把默认认证方案换成一个只负责转发的策略方案，让每个请求自己决定用哪套 Cookie；挑战和登出仍然交给 OIDC。**

## 三个默认值决定谁来做认证

配置的关键不在 `AddCookie`，而在 `AddAuthentication` 的三个默认值：

```csharp
builder.Services.AddAuthentication(options =>
{
    options.DefaultScheme = "Unknown";
    options.DefaultChallengeScheme = OpenIdConnectDefaults.AuthenticationScheme;
    options.DefaultSignOutScheme = OpenIdConnectDefaults.AuthenticationScheme;
})
.AddPolicyScheme("Unknown", "Select SchemeOne/SchemeTwo", options =>
{
    options.ForwardDefaultSelector = context =>
    {
        if (context.Request.Cookies.ContainsKey("__Host-Http-one"))
            return "SchemeOne";

        if (context.Request.Cookies.ContainsKey("__Host-Http-two"))
            return "SchemeTwo";

        return "SchemeOne"; // fallback
    };
})
.AddCookie("SchemeOne", options =>
{
    options.Cookie.Name = "__Host-Http-one";
    options.Cookie.SameSite = SameSiteMode.Lax;
    options.EventsType = typeof(CookieEventHandler);
})
.AddCookie("SchemeTwo", options =>
{
    options.Cookie.Name = "__Host-Http-two";
    options.Cookie.SameSite = SameSiteMode.Lax;
    options.EventsType = typeof(CookieEventHandler);
})
.AddCookie("SchemeOidcAuth");
```

三个默认值各管一段：

- `DefaultScheme` 指向策略方案 `Unknown`，它只参与 `AuthenticateAsync` 这类默认认证操作；
- `DefaultChallengeScheme` 指向 OIDC，未登录时才跳去身份提供方；
- `DefaultSignOutScheme` 也指向 OIDC，登出时才会触发远端登出。

如果不显式设置后两个，未认证请求会走策略方案转发到某个 Cookie 方案，再由 Cookie 处理器跳转到 `LoginPath`。而 Cookie 认证默认的登录路径是 `/Account/Login`，一个纯 API 后端通常没有这个页面，结果就是 404 而不是登录。把挑战和登出钉在 OIDC 上，才是这套配置能跑起来的前提。

## 策略方案只看 Cookie 在不在

`ForwardDefaultSelector` 收到的是原始请求，它只判断请求里有没有对应的 Cookie，不解析、也不验证内容。真正解密票据、建立 `ClaimsPrincipal` 的是被选中的那个 Cookie 处理器。

这带来两个直接结果：

**一个请求只有一个 Cookie 方案参与认证。** 用户同时持有两套 Cookie 时，选择结果由判断顺序决定，先匹配到的那个生效。原文也强调这一点：虽然支持多方案，但单次请求的认证流程仍然只有一条。

**没有匹配的 Cookie 时回退到 `SchemeOne`。** 这个回退不是「随便挑一套」，而是把匿名请求交给 `SchemeOne` 处理器，处理器找不到票据，判定为未认证，随后按默认挑战方案跳转 OIDC。所以第一次访问时的登录入口正好由这个回退兜住。

框架的转发顺序值得记一下，来自官方文档：`ForwardAuthenticate` / `ForwardChallenge` / `ForwardForbid` / `ForwardSignIn` / `ForwardSignOut` 优先，其次是 `ForwardDefaultSelector`，最后是 `ForwardDefault`，第一个非空值生效。策略方案默认会转发所有默认操作，所以前面显式设置的 `DefaultChallengeScheme` 和 `DefaultSignOutScheme` 把挑战和登出从转发链里摘了出去。

## `__Host-` 前缀不是随便起的名

两个 Cookie 用了 `__Host-` 前缀，浏览器对这类名字有硬性要求：必须带 `Secure`、必须由 HTTPS 页面下发、不能有 `Domain` 属性、`Path` 必须是 `/`。作用是把 Cookie 锁死在当前主机上，防止子域覆盖。

ASP.NET Core 这边，`CookieBuilder` 的 `Path` 默认就是 `/`，是否带 `Secure` 取决于 `SecurePolicy` 和请求是否 HTTPS，默认值是 `SameAsRequest`。也就是说，本地用 `http://localhost` 调试时这类 Cookie 不会按 `__Host-` 规则下发，浏览器会直接丢弃，表现成「登录成功但下一个请求又是未认证」。调试时请走 HTTPS 端点。

还有一个容易被忽略的点：`SameSite` 设成了 `Lax`。身份提供方跳回应用的那一步是一次跨站导航，`Lax` 允许这类顶层导航带上 Cookie；改成 `Strict`，回跳请求就带不上，登录会停在回调页反复重来。

关于数量，原文说这套方案用了「四个专用 Cookie 方案」，但对照仓库当前的 `Program.cs`，实际注册的是三个 Cookie 认证方案（`SchemeOne`、`SchemeTwo`、`SchemeOidcAuth`）加一个策略方案；另外防伪令牌单独用了一个 `__Host-Http-X-XSRF-TOKEN` Cookie，不属于认证方案。按仓库代码理解即可。

这两个 Cookie 方案都挂了同一个 `CookieEventHandler`。它的作用是处理身份提供方的 back-channel logout：在 `ValidatePrincipal` 里检查会话是否已被标记登出，一旦是，就同时 `SignOutAsync` 两个方案。多方案场景下，登出必须一套一套地清，漏一个就会留下仍然有效的会话。

## 登录回调决定落到哪套方案

OIDC 侧的关键配置是先登入一个中性的临时方案：

```csharp
.AddOpenIdConnect(options =>
{
    options.SignInScheme = "SchemeOidcAuth";

    options.Events = OidcEventHandlers.OidcEvents(builder.Configuration);

    options.ClientId = builder.Configuration["WebOidcClientId"];
    options.Authority = builder.Configuration["WebOidcAuthority"];
    options.ResponseType = OpenIdConnectResponseType.Code;

    options.SaveTokens = true;
    options.GetClaimsFromUserInfoEndpoint = true;
    options.MapInboundClaims = false;

    options.ClaimActions.MapUniqueJsonKey("loa", "loa");
    options.ClaimActions.MapUniqueJsonKey("loi", "loi");
    options.ClaimActions.MapUniqueJsonKey(JwtClaimTypes.Email, JwtClaimTypes.Email);

    options.PushedAuthorizationBehavior = PushedAuthorizationBehavior.Require;

    options.Scope.Add("scope2");
    options.TokenValidationParameters = new TokenValidationParameters
    {
        NameClaimType = "name"
    };
});
```

`SignInScheme` 指向 `SchemeOidcAuth`，而不是任何一套业务 Cookie 方案。OIDC 回调必须有个方案来接住票据；如果直接指向业务方案，票据会先落进那一套，再被事件处理器迁走，等于每次登录都先写错一次。用一个中性方案接住，再由事件处理器换到目标方案，意图清楚得多。

`MapInboundClaims = false` 加上 `MapUniqueJsonKey` 是为了保留原始 claim 名。默认的入站声明映射会把 JWT 里的短名改成 `ClaimTypes.*` 的长 URI，`loa` 这类自定义声明不显式映射就可能拿不到。

决定方案落在 `OnTokenValidated`：

```csharp
private static async Task OnTokenValidatedHandler(TokenValidatedContext context,
    IConfiguration configuration)
{
    var applicationServices = context.HttpContext.RequestServices;
    if (context.Principal != null)
    {
        var loa = context.Principal?.FindFirst("loa")?.Value;
        var targetScheme = loa == "loa.400" ? "SchemeOne" : "SchemeTwo";

        await context.HttpContext.SignInAsync(targetScheme,
                  context.Principal!, context.Properties);

        await context.HttpContext.SignOutAsync("SchemeOidcAuth");
    }
}
```

读 `loa`（Level of Assurance）声明，满足特定等级的用户写进 `SchemeOne`，其余写进 `SchemeTwo`。代码随后调用 `SignOutAsync("SchemeOidcAuth")` 清理临时方案，避免回调票据以 Cookie 形式留在浏览器里。

原文提醒这只是演示逻辑。真实场景里更常见的是身份提供方联合（federation）：令牌里带一个 `idp` 声明，值指向下游的身份提供方，用这个值选择方案。生产环境还需要做 claims transformation，把不同来源的声明归一化，这部分示例里省略了，也正是迁移期最容易出问题的地方——同一个字段在两家 IdP 里的类型和取值可能完全不一样。

## 授权端按方案声明

控制器这边很直接：

```csharp
[ValidateAntiForgeryToken]
[Authorize(AuthenticationSchemes = "SchemeOne")]
[ApiController]
[Route("api/[controller]")]
public class SchemeOneController : ControllerBase
{
    [HttpGet]
    public IEnumerable<string> Get()
    {
        return new List<string> { "some data scheme 1",
          "more data", "loads of data" };
    }
}
```

`AuthenticationSchemes` 支持逗号分隔的多个方案。官方文档的说明是：授权中间件按列出的顺序，只要任一方案通过认证就放行；如果多个方案都建立了身份，会把身份合并进同一个 `ClaimsPrincipal`。只写一个方案时，只有那个处理器运行，其他方案的身份直接被忽略。

要求同时接受两套身份时就这样写：

```csharp
[Authorize(AuthenticationSchemes = "SchemeOne,SchemeTwo")]
```

权限判断本身仍然落在声明或数据库上，方案只决定「这份用户身份是从哪套 Cookie 来的」。这一点别搞混：方案不是权限模型，它只是身份的来源。

方案名是字符串字面量，拼错不会编译报错，只会在运行时表现为「一直未认证」。项目里建议定义成常量统一引用。

## 登出要一套一套地清

```csharp
[IgnoreAntiforgeryToken] // need to apply this to the form post request
[Authorize(AuthenticationSchemes = "SchemeOne,SchemeTwo")]
[HttpPost("Logout")]
public IActionResult Logout()
{
    return SignOut(
        new AuthenticationProperties { RedirectUri = "/" },
        // TODO which cookie scheme should be logged out
        "SchemeOne",
        "SchemeTwo",
        OpenIdConnectDefaults.AuthenticationScheme);
}
```

`SignOut` 接受多个方案名，这里把两套业务 Cookie 和 OIDC 一起登出。如果不把 OIDC 加进去，用户在本地登出了，但身份提供方那边的会话还在，下次登录会直接静默回跳。

代码里的 `TODO` 是原作者自己留的：到底该登出哪一套？在这套方案里答案比较清楚——用户自己知道当前是哪套，但服务端不一定，所以两套都清是最稳的。如果将来两套方案对应不同的 IdP，还得分别触发各自的远端登出。

`[IgnoreAntiforgeryToken]` 是因为应用注册了全局的 `AutoValidateAntiforgeryTokenAttribute`，登出这种表单 POST 也会被校验。Angular 前端如果把 token 放在 `X-XSRF-TOKEN` 头里，其实可以正常通过校验；忽略校验是为了演示简单，生产环境不该这么放开。

## API 请求不该被重定向到登录页

默认挑战方案是 OIDC，意味着未认证的 API 请求会收到 302，跳转到身份提供方。对浏览器导航这没问题，对 `HttpClient` 和 `fetch` 就很麻烦：请求跟着重定向跑到另一个源，脚本拿到的是 HTML 或者 CORS 错误，而不是一个明确的 401。

仓库里补了一个中间件来标记 AJAX 请求：

```csharp
public static IApplicationBuilder UseNoUnauthorizedRedirect(
    this IApplicationBuilder applicationBuilder, params string[] segments)
{
    applicationBuilder.Use(async (httpContext, func) =>
    {
        if (segments.Any(s => httpContext.Request.Path.StartsWithSegments(s)))
        {
            httpContext.Request.Headers[HeaderNames.XRequestedWith] = "XMLHttpRequest";
        }

        await func();
    });

    return applicationBuilder;
}
```

它在 `/api` 路径上补 `X-Requested-With: XMLHttpRequest`，Cookie 处理器识别到 AJAX 请求时返回 401 而不是重定向。从 ASP.NET Core 10 起，已知的 API 端点默认就不再重定向到登录页，而是返回 401/403；这层手写逻辑在 .NET 10 上更多是兜底，不必再靠它来保证 API 返回 401。

不管用哪种方式，都建议在集成测试里盯住状态码：无 Cookie 请求 `/api/SchemeOne` 应该得到 401，而不是 302。

## 验证清单

按这套配置跑起来，下面几项能直接区分「真的工作了」和「看起来登录了」：

1. 用 `loa.400` 的用户登录，浏览器里应出现 `__Host-Http-one`，没有 `__Host-Http-two`；
2. 用其他等级的用户登录，两者反过来；
3. 只带 `__Host-Http-one` 调 `/api/SchemeTwo`，应返回 401；调 `/api/SchemeOne` 应返回 200；
4. 调登出接口后，两个 Cookie 都应被清空；
5. 在身份提供方侧触发 back-channel logout，下一次请求应被拒绝，而不是继续用旧票据；
6. 部署多实例时确认 Data Protection 密钥环共享，否则各实例签发的 Cookie 互相解不开。

第 6 条容易被忽略：Cookie 认证的安全性来自数据保护加密，多实例或容器重启后密钥环不一致，表现就是随机掉登录。

## 什么时候不该这么做

原文自己写了一句很实在的话：正常情况下不需要这样的配置，新项目用单一默认方案更合适。

这套方案适合的场景很窄：**迁移期，授权代码不想动，且两套身份必须同时在线。** 它不是一个值得长期保留的架构。两套方案共用同一份授权逻辑，看起来省事，实际把「这个用户属于哪套身份」的隐式状态留在了 Cookie 名里，排错时得先问「他拿的是哪个 Cookie」。

迁移结束时得能干净地拆掉：确认用户全部迁完、旧 IdP 可以下线、把两套 `AddCookie` 收敛成一套，再把 `AuthenticationSchemes` 里的双方案声明简化掉。

如果一开始就在设计阶段，更省事的方向是把差异往上收：在 IdP 侧做联合，用 claims transformation 把不同来源的身份统一成一套声明，应用里只保留一个 Cookie 方案。应用不该为身份提供方的迁移过程长期买单。

下次遇到迁移，先判断一件事：授权代码能不能不动。能不动，就用多方案过渡，同时写下退出条件；不能不动，就别引入第二套 Cookie，先把声明归一化做掉。

如果你也在处理身份迁移或者 BFF 架构，Aide Hub 会继续分享 AI 助手、开发工具与软件工程实践。

## 参考

- [Use multiple schemes in an ASP.NET Core Web application](https://damienbod.com/2026/10/12/use-multiple-schemes-in-an-asp-net-core-web-application/) — 原文，Damien Bowden，2026-10-12。多方案配置、回调选方案、登出与注意事项均出自此文。
- [damienbod/MultipleSchemeWithOidc](https://github.com/damienbod/MultipleSchemeWithOidc) — 示例代码仓库，本文的 `Program.cs`、`OidcEventHandlers.cs`、`CookieEventHandler.cs` 与登出实现均以仓库当前代码为准。
- [Policy schemes in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/security/authentication/policyschemes?view=aspnetcore-10.0) — 转发顺序与 `ForwardDefaultSelector` 的官方说明。
- [Authorize with a specific scheme in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/security/authorization/authorize-with-a-specific-scheme?view=aspnetcore-10.0) — `AuthenticationSchemes` 多方案授权与身份合并规则。
- [Use cookie authentication without ASP.NET Core Identity](https://learn.microsoft.com/en-us/aspnet/core/security/authentication/cookie?view=aspnetcore-10.0) — Cookie 认证配置、`LoginPath` 默认值、ASP.NET Core 10 起 API 端点返回 401/403 的变化、Data Protection 要求。
- [Set-Cookie header（MDN）](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie) — `__Host-` 前缀对 Secure、Path、Domain 的约束。
