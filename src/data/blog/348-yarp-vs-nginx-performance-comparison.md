---
pubDatetime: 2025-05-31
tags: [.NET, YARP, Nginx, 性能对比, API网关, 反向代理, 架构]
slug: yarp-vs-nginx-performance-comparison
source: https://www.milanjovanovic.tech/blog/yarp-vs-nginx-a-quick-performance-comparison
title: YARP vs Nginx——.NET高性能API网关实战对比
description: 针对.NET中高级开发者，深入对比YARP与Nginx作为反向代理在高并发场景下的性能表现，助你科学选型API网关。
---

# YARP vs Nginx——.NET高性能API网关实战对比

## 引言：API网关之争，YARP还是Nginx？🤔

在现代微服务架构中，API网关/反向代理的性能直接决定了系统的吞吐与响应速度。对于.NET开发者来说，选择微软推出的 **YARP (Yet Another Reverse Proxy)** 还是业界经典的 **Nginx**，一直是架构设计时的热门话题。

但“孰优孰劣”不能只凭口碑，必须用数据说话。本文基于同一API、相同硬件环境与一致的压力测试工具，对YARP和Nginx进行了系统性性能对比，希望为追求高性能、易集成的.NET技术团队提供一手参考。

> 本文适合：中高级.NET开发人员、关注API网关/反向代理性能的架构师与DevOps专家。

---

## 正文

### 测试方案设计：公平决斗，单点突破

#### 测试API极简设计

为了让对比聚焦在网关本身，而非后端业务处理，我们采用了极其简单的.NET API：

```csharp
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.MapGet("/hello", () =>
{
    return Results.Ok("Hello world!");
});

app.Run();
```

如此设计确保了“谁快谁慢”归因于代理层，而非后端服务处理能力。

#### YARP配置：.NET生态天然亲和

YARP集成非常友好，尤其适合.NET项目：

```csharp
builder.Services
    .AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));

app.MapReverseProxy();
```

**配置片段**（JSON）：

```json
{
  "ReverseProxy": {
    "Routes": {
      "default": {
        "ClusterId": "hello",
        "Match": { "Path": "{**catch-all}" }
      }
    },
    "Clusters": {
      "hello": {
        "Destinations": {
          "destination1": {
            "Address": "http://hello.api:8080"
          }
        }
      }
    }
  }
}
```

> 想深入了解YARP负载均衡与鉴权，可参考[相关实践](https://www.milanjovanovic.tech/blog/horizontally-scaling-aspnetcore-apis-with-yarp-load-balancing)。

#### Nginx配置：Docker一把梭，经典不变

Nginx同样使用Docker快速部署，并设置最小可用配置实现与YARP功能等价：

```nginx
http {
    upstream backend {
        server hello.api:8080;
    }

    server {
        listen 80;
        location / {
            proxy_pass http://backend;
        }
    }
}
```

**Docker Compose整合**（节选）：

```yaml
services:
  yarp.proxy:
    ...
    ports:
      - 3000:8080
  nginx.proxy:
    ...
    ports:
      - '3001:80'
```

#### 压力测试工具：k6标准化打靶

采用[k6](https://k6.io/)进行并发压测，分别针对YARP和Nginx端口发起同量级请求。

> 主要参数：10/50/100/200 VUs，每个VUs发起1000次请求。

---

### 性能数据：YARP vs Nginx，一图胜千言 📊

#### RPS（每秒请求数）对比

| VUs | YARP RPS | NGINX RPS |
| --- | -------- | --------- |
| 10  | 12692    | 9756      |
| 50  | 27080    | 10614     |
| 100 | 32432    | 10324     |
| 200 | 36662    | 10169     |

![YARP vs Nginx RPS对比图](https://www.milanjovanovic.tech/blogs/mnw_144/rps_comparison.png?imwidth=3840)

> **解读**：YARP吞吐量随着并发提升显著增长，而Nginx基本保持在1万上下。

#### p90/p95 延迟对比（单位：ms）

| VUs | YARP p90 | NGINX p90 | YARP p95 | NGINX p95 |
| --- | -------- | --------- | -------- | --------- |
| 10  | 1.04     | 1.10      | 1.06     | 1.52      |
| 50  | 2.70     | 5.23      | 3.18     | 5.68      |
| 100 | 4.66     | 10.61     | 5.43     | 10.96     |
| 200 | 7.77     | 21.23     | 8.81     | 21.92     |

![p90延迟对比](https://www.milanjovanovic.tech/blogs/mnw_144/p90_comparison.png?imwidth=3840)
![p95延迟对比](https://www.milanjovanovic.tech/blogs/mnw_144/p95_comparison.png?imwidth=3840)

> **解读**：并发压力上升时，YARP延迟依然可控；Nginx则线性增加，差距明显。

---

### 深度剖析：为何YARP表现优异？

- **吞吐扩展性**：YARP依托于.NET Core高性能Kestrel服务器，线程模型与异步IO设计更适合现代硬件。
- **低延迟响应**：得益于紧密集成与极简中间件链路，YARP响应时延始终优于Nginx。
- **开发者体验**：.NET生态无缝接入、统一配置风格、支持代码级自定义扩展，省心省力。

> ⚠️ 注意：本文测试基于默认配置，Nginx如做极致调优有提升空间，但“即开即用”场景下YARP优势明显。

---

## 结论与实践建议 🏆

### 核心结论

- **YARP 是.NET高并发场景下的首选API网关**，性能领先Nginx约3~4倍，延迟更低；
- **Nginx仍然稳定可靠**，但其传统模型难以突破吞吐瓶颈，适用性更广泛但对.NET项目有一定“割裂感”；
- **开发体验加分项**：YARP更贴合.NET团队日常运维与CI/CD流程。

### 落地建议

- 若你的项目以.NET为主、追求极致性能和易维护性，推荐优先考虑YARP；
- 若跨语言后端/已有大量Nginx运维经验，Nginx依然值得采用——但务必结合实际业务场景做专项测试。

---

## 写在最后｜欢迎交流你的看法！

你在实际项目中用过YARP或Nginx吗？有遇到什么性能瓶颈或踩坑经验？欢迎在评论区留言交流👇，或转发给你的架构小伙伴共同探讨！

如果你觉得本文有用，请点个赞或分享，让更多.NET技术人受益！🚀
