---
pubDatetime: 2026-03-18T12:49:35+08:00
title: "为 .NET HttpClient 实现 RFC 标准 HTTP 缓存"
description: "介绍如何通过 Meziantou.Framework.Http.Caching 包为 HttpClient 添加符合 RFC 7234 和 RFC 8246 标准的 HTTP 缓存支持，覆盖基础用法、依赖注入集成、客户端缓存指令和并发安全机制。"
tags: [".NET", "HttpClient", "HTTP", "Caching", "Performance", "ASP.NET Core"]
slug: "dotnet-httpclient-rfc-compliant-http-caching"
ogImage: "../../assets/649/01-cover.png"
source: "https://www.meziantou.net/implementing-rfc-compliant-http-caching-for-httpclient-in-dotnet.htm"
---

![HTTP 缓存层拦截网络请求示意图](../../assets/649/01-cover.png)

浏览器会自动处理 HTTP 缓存，但 .NET 的 `HttpClient` 不会。它默认把每个请求都独立发出去，不管服务器响应头里有没有 `Cache-Control: max-age=3600`，下一次请求还是直接打到服务器。

如果你的服务要频繁请求同一批外部 API，这意味着大量可以省掉的网络往返，全都实实在在地发生了。

`Meziantou.Framework.Http.Caching` 这个 NuGet 包填了这个空缺，完整实现了 RFC 7234（HTTP Caching）和 RFC 8246（`immutable` 指令）。把它作为 `DelegatingHandler` 插入 `HttpClient` 的处理链，后续的缓存存储、新鲜度计算、条件请求到缓存失效，都自动按 RFC 标准处理。

## HTTP 缓存的核心机制

在用包之前，先明确几个概念，因为它们直接对应代码里的配置项。

HTTP 缓存围绕响应头展开。服务器返回 `Cache-Control: max-age=300` 表示这个响应在 300 秒内视为"新鲜（fresh）"，客户端可以直接复用；`no-store` 则禁止任何缓存；`no-cache` 不是禁止缓存，而是要求每次使用前先向服务器验证；`immutable` 表示响应内容永远不变，不需要验证（即使 `max-age` 过期了也不用）。

条件请求是缓存复用的关键路径。响应过期时，客户端不用直接发完整请求，而是带上 `If-None-Match`（配合 ETag）或 `If-Modified-Since` 发一个条件请求。如果内容没变，服务器返回 `304 Not Modified`，不带响应体，客户端继续用本地缓存，节省了传输带宽。

这个标准交互流程是这样的：

1. 首次请求，服务器响应并带缓存头
2. 客户端缓存响应
3. 后续请求先检查缓存是否还新鲜
4. 新鲜就直接返回缓存；过期了发条件请求
5. 服务器返回 `304` 或新内容，更新缓存元数据

## 安装

```shell
dotnet add package Meziantou.Framework.Http.Caching
dotnet add package Meziantou.Framework.Http.Caching.InMemory
```

核心包提供接口和处理器，`InMemory` 包提供内存缓存实现。如果需要分布式缓存（比如 Redis），可以自行实现 `IHttpCacheStore` 接口。

## 基础用法

最简单的接入方式：创建缓存存储，把 `HttpCachingDelegateHandler` 包在 `HttpClientHandler` 外面。

```csharp
using Meziantou.Framework.Http.Caching;
using Meziantou.Framework.Http.Caching.InMemory;

var cacheStore = new InMemoryHttpCacheStore();
var cachingHandler = new HttpCachingDelegateHandler(new HttpClientHandler(), cacheStore);

using var httpClient = new HttpClient(cachingHandler);

// 第一次请求，命中服务器
var response1 = await httpClient.GetAsync("https://api.example.com/products");
// 第二次请求，如果响应还新鲜，直接从缓存返回
var response2 = await httpClient.GetAsync("https://api.example.com/products");
```

后续的缓存逻辑完全自动。处理器会解析 `Cache-Control`、`ETag`、`Last-Modified`，根据 RFC 规则决定是复用缓存、发条件请求，还是直接转发。

## 与依赖注入集成

在 ASP.NET Core 项目里，通过 `IHttpClientFactory` 注册：

```csharp
services.AddSingleton<IHttpCacheStore, InMemoryHttpCacheStore>();
services.AddTransient<HttpCachingDelegateHandler>();

services.AddHttpClient("ProductApi")
    .AddHttpMessageHandler<HttpCachingDelegateHandler>();
```

需要自定义缓存行为时，可以在注册时传入 `HttpCachingOptions`：

```csharp
services.AddSingleton<IHttpCacheStore, InMemoryHttpCacheStore>();

services.AddHttpClient("ProductApi")
    .AddHttpMessageHandler(sp =>
    {
        var cacheStore = sp.GetRequiredService<IHttpCacheStore>();
        var options = new HttpCachingOptions
        {
            MaximumResponseSize = 1024 * 1024, // 最大缓存 1 MB 的响应
            ShouldCacheResponse = response =>
            {
                if (!response.IsSuccessStatusCode) return false;
                if (response.Headers.Contains("X-No-Cache")) return false;
                return true;
            }
        };
        return new HttpCachingDelegateHandler(cacheStore, options);
    });
```

`ShouldCacheResponse` 让你可以用业务逻辑控制哪些响应值得存，比如跳过带特定头的响应，或者只缓存特定状态码。

## 客户端缓存指令

RFC 7234 里的 `Cache-Control` 不只是服务器能用，客户端发请求时也可以带。这个包对请求级别的 `Cache-Control` 指令也有完整支持。

**强制重新验证**，跳过本地缓存直接问服务器：

```csharp
using var request = new HttpRequestMessage(HttpMethod.Get, "https://api.example.com/products");
request.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true };
using var response = await httpClient.SendAsync(request);
// 注意：如果响应标记了 immutable 且还新鲜，仍然会从缓存返回
```

**接受过期响应**，在更关注可用性而非新鲜度的场景：

```csharp
request.Headers.CacheControl = new CacheControlHeaderValue
{
    MaxStale = true,
    MaxStaleLimit = TimeSpan.FromMinutes(5) // 最多接受过期 5 分钟的缓存
};
```

**只用缓存，不发网络请求**。用 `only-if-cached` 指令，如果没有缓存就返回 `504 Gateway Timeout`，不会发出真正的 HTTP 请求：

```csharp
request.Headers.CacheControl = new CacheControlHeaderValue { OnlyIfCached = true };
using var response = await httpClient.SendAsync(request);

if (response.StatusCode == HttpStatusCode.GatewayTimeout)
{
    // 没有可用的缓存响应
}
```

这个模式适合离线优先的场景，或者你希望某些操作在没缓存时明确失败、而不是等待网络超时。

## 并发安全

`HttpCachingDelegateHandler` 是线程安全的，可以在多线程并发使用。它内部还处理了"缓存踩踏（cache stampede）"问题：当多个线程同时请求同一个 URL 且缓存刚好过期时，不会同时发出多个请求，而是协调成只有一个请求真正发出，其余等待复用结果。内置的 `InMemoryHttpCacheStore` 也是按并发安全设计的。

## 适用范围

这个包适合调用外部 API 的服务端代码，比如：

- 频繁查询第三方 REST API（汇率、天气、配置数据）
- 多个服务共用同一批数据源
- 需要在网络故障时降级到过期缓存

如果是浏览器里的请求，浏览器本⾝已经有标准 HTTP 缓存了。如果是服务端对自己数据库的访问，HTTP 缓存不适用，应该用 `IMemoryCache`、`IDistributedCache` 这类机制。

## 参考

- [Implementing RFC-compliant HTTP caching for HttpClient in .NET](https://www.meziantou.net/implementing-rfc-compliant-http-caching-for-httpclient-in-dotnet.htm) — Gérald Barré (meziantou)
- [RFC 7234: HTTP Caching Specification](https://www.rfc-editor.org/rfc/rfc7234.html)
- [RFC 8246: HTTP Immutable Responses](https://www.rfc-editor.org/rfc/rfc8246.html)
- [Meziantou.Framework.Http.Caching NuGet Package](https://www.nuget.org/packages/Meziantou.Framework.Http.Caching)
- [Source Code on GitHub](https://github.com/meziantou/Meziantou.Framework/tree/main/src/Meziantou.Framework.Http.Caching)
