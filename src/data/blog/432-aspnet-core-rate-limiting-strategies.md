---
pubDatetime: 2025-08-14
tags: [".NET", "ASP.NET Core", "C#"]
slug: aspnet-core-rate-limiting-strategies
source: N/A
title: ASP.NET Core 中的四种限流策略详解与代码实现
description: 详细解析 ASP.NET Core 中的 Fixed Window、Sliding Window、Token Bucket 和 Concurrency 限流策略，包括原理、适用场景与代码示例。
---

# ASP.NET Core 中的四种限流策略详解与代码实现

在高并发环境下，合理的限流策略能够保护系统资源、避免服务崩溃，并提升整体用户体验。ASP.NET Core 自 .NET 7 起集成了 `Microsoft.AspNetCore.RateLimiting` 库，涵盖多种主流限流算法，支持灵活扩展。本文将围绕四种常见的限流策略——固定窗口、滑动窗口、令牌桶和并发限制，深入讲解其实现原理、性能特点、适用场景，以及如何在 ASP.NET Core 中高效实现。

---

## 1. 固定窗口限流（Fixed Window Limiter）

固定窗口限流算法基于将时间划分为固定长度的间隔窗口（如 2 分钟），在每个窗口周期内限制请求数上限。超过阈值的请求会被拒绝，直到进入下一个时间窗口。

**核心原理：**

- 计数器在每个固定时间窗口开始时重置。
- 请求计数累积直到达到允许的阈值。
- 窗口末尾时计数器清零，重新统计。

```csharp
options.AddFixedWindowLimiter("fixed", opt =>
{
    opt.Window = TimeSpan.FromMinutes(2);  // 窗口周期
    opt.PermitLimit = 20;                   // 最大请求数
});
```

**性能特点：**

- 实现简单，资源消耗低。
- 在高并发突发请求时，可能会在窗口边界产生“突刺”流量。

**适用场景：**

- 适合流量相对稳定，极端突发少的业务。

**图示说明：**

```
|===== 20 req limit =====| 2 min |===== 20 req limit =====|
```

---

## 2. 滑动窗口限流（Sliding Window Limiter）

滑动窗口算法把整体时间窗口拆分为多个小段（如每 30 秒一段），对最近完整窗口内所有小段请求数求和，从而平滑流量峰值，避免固定窗口造成的边缘“突刺”。

**核心原理：**

- 维护多个子段请求计数。
- 每次请求时计算最近完整时间窗口所有子段请求总和。
- 窗口以小段单位不断滑动，避免请求集中在固定窗口边缘。

```csharp
options.AddSlidingWindowLimiter("sliding", opt =>
{
    opt.Window = TimeSpan.FromMinutes(2);   // 总窗口长度
    opt.PermitLimit = 20;                    // 最大请求数
    opt.SegmentsPerWindow = 4;               // 窗口分段数，每段 30 秒
});
```

**性能特点：**

- 减少突然流量峰值，提升请求平滑性。
- 计算复杂度高于固定窗口，需要维护多个计数器。

**适用场景：**

- 流量波动明显，要求平滑分布请求的业务。

**图示说明：**

```
[----][----][----][----]  ← 以 30 秒为单位滑动时间窗口
```

---

## 3. 令牌桶限流（Token Bucket Limiter）

令牌桶算法用于支持一定程度的突发流量，同时实现稳定流速。在固定时间间隔生成令牌，用户请求消耗令牌。令牌没了时请求被拒绝。

**核心原理：**

- 令牌桶容量限制最大突发量。
- 以固定频率向桶内添加令牌。
- 请求处理消耗一个令牌。

```csharp
options.AddTokenBucketLimiter("token", opt =>
{
    opt.TokenLimit = 15;                         // 桶容量
    opt.TokensPerPeriod = 1;                      // 令牌补充速率
    opt.ReplenishmentPeriod = TimeSpan.FromSeconds(1);  // 补充周期
});
```

**性能特点：**

- 支持短时间内请求突发。
- 需要对令牌生成和消耗进行同步控制。

**适用场景：**

- 支持用户突发请求，但整体保持平稳速率的接口。

**图示说明：**

```
令牌桶（容量 15）以每秒 1 个令牌速率补充
```

---

## 4. 并发限流（Concurrency Limiter）

并发限流限制同一时刻的请求数，防止服务器因资源争用（CPU、IO 等）而过载。请求超过限制则排队，队列满后拒绝。

**核心原理：**

- 维护一个同时处理请求的许可计数器。
- 超过许可数的请求进入排队等待。
- 队列达到上限拒绝后续请求。

```csharp
options.AddConcurrencyLimiter("concurrency", opt =>
{
    opt.PermitLimit = 5;   // 最大并发处理数
    opt.QueueLimit = 10;   // 等候队列大小
});
```

**性能特点：**

- 防止资源耗尽，保证系统稳定。
- 队列长时请求等待时间增长，可能影响体验。

**适用场景：**

- 适合依赖有限资源（数据库连接、外部服务）的场景中控制并发量。

**图示说明：**

```
正在处理: |||||
排队等待: ||||||||||
```

---

## 5. 实际应用与整合

在 ASP.NET Core 中，可通过 `RequireRateLimiting` 特性将不同限流策略关联至各自的 API 路由，实现灵活组合和精细化控制：

```csharp
app.MapGet("/fixed", () => "Fixed window response").RequireRateLimiting("fixed");
app.MapGet("/sliding", () => "Sliding window response").RequireRateLimiting("sliding");
app.MapGet("/token", () => "Token bucket response").RequireRateLimiting("token");
app.MapGet("/concurrency", () => "Concurrency response").RequireRateLimiting("concurrency");
```

此方式支持针对不同 API 选择最适合的限流方案，方便测试和调优。

---

**总结：**
通过深入理解各限流策略的原理和适用场景，开发者能在 ASP.NET Core 应用中灵活应用 `Microsoft.AspNetCore.RateLimiting` 实现高效流控，保障系统鲁棒性和响应性能。
