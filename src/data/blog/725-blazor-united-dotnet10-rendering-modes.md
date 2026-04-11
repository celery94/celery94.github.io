---
pubDatetime: 2026-04-11T09:00:00+08:00
title: ".NET 10 的 Blazor United 是什么——统一渲染模式详解"
description: "Blazor United 在 .NET 10 中将服务端渲染和 WebAssembly 融为一体，允许在同一应用里按组件选择渲染模式。本文介绍其工作原理、核心特性与实际适用场景。"
tags: ["Blazor", ".NET", "Web Development", "C#"]
slug: "blazor-united-dotnet10-rendering-modes"
ogImage: "../../assets/725/01-cover.png"
source: "https://www.c-sharpcorner.com/article/what-is-blazor-united-in-net-10-and-its-rendering-modes/"
---

![Blazor United in .NET 10 统一渲染模式封面图](../../assets/725/01-cover.png)

Web 应用开发长期面临一个取舍：要么用服务端渲染（首屏快、SEO 好），要么用客户端渲染（交互丰富、无需频繁往返服务器）。这两种方式过去在 Blazor 里是分开的——Blazor Server 和 Blazor WebAssembly 是两套独立的托管模型，混用就意味着拆成多个项目。

.NET 10 里的 **Blazor United** 解决了这个问题。它把两种渲染路径纳入同一个框架，让开发者可以在同一个应用里、甚至在同一个页面里按需选择渲染方式。

## 重新理解两种渲染模式

在看 Blazor United 之前，先把现有的两种渲染模式捋清楚。

### Blazor Server

Blazor Server 把应用逻辑都跑在服务端，浏览器只做一个轻量的 UI 终端。用户每次操作，都通过 **SignalR** 长连接把事件发给服务端，服务端处理后把 DOM 差量推回来。

```razor
<h3>Hello from Server</h3>
<button @onclick="Increment">Click me</button>

@code {
    int count = 0;
    void Increment() => count++;
}
```

这个模型的好处是首屏快（无需下载大 WASM 包）、支持完整的 .NET API，但代价是持续占用服务端资源，一旦连接断开，UI 就停了。

### Blazor WebAssembly

Blazor WebAssembly 把整个 .NET 运行时和应用代码下载到浏览器，然后直接在本地执行。好处是脱离服务器依赖、可以离线运行；缺点是首次下载体积不小，冷启动比 Blazor Server 慢。

这两种方式各有适合的场景，但开发者长期面临"只能二选一"的困境。

## Blazor United 怎么做到统一

Blazor United 的核心思路是：**渲染模式是组件级别的属性，而不是应用级别的约束**。这一改变带来了几个实际能力。

### 服务端预渲染 + 客户端接管

页面首次加载时走服务端渲染——HTML 直接从服务端吐出，浏览器立刻能显示内容，搜索引擎也能抓到完整的页面结构。

等 WebAssembly 运行时在后台加载完毕后，组件自动"激活"（hydration），把原来静态的 HTML 接管成可交互的 WASM 组件。整个过程对用户来说是无缝的——先看到页面，再拥有交互能力。

### 按组件设置渲染模式

这是 Blazor United 最直接的使用方式。每个组件可以通过 `@rendermode` 属性独立声明自己跑在哪里：

```razor
<!-- 这个组件用 WebAssembly 运行，适合需要富交互的场景 -->
<Counter @rendermode="InteractiveWebAssembly" />

<!-- 这个组件保持在服务端，适合需要访问数据库或保密逻辑的场景 -->
<OrderSummary @rendermode="InteractiveServer" />

<!-- 静态渲染，只需要展示，不需要交互 -->
<ProductDescription @rendermode="Static" />
```

开发者不再需要为了一个页面里的某个交互组件把整个应用迁到 WebAssembly。

### 统一代码库，告别多项目分裂

以前要在一个应用里同时支持 Blazor Server 和 WebAssembly，需要维护多个项目：一个 Client 项目、一个 Server 项目，共享代码放在单独的 Shared 项目。Blazor United 把这些合并到了单一项目结构，减少了大量重复配置。

## 真实场景：电商网站

用一个电商网站来理解三种渲染模式怎么配合使用：

| 页面 / 组件 | 渲染模式 | 原因 |
|---|---|---|
| 商品列表首页 | 服务端预渲染 | 首屏速度 + SEO 索引 |
| 商品详情页的加购按钮 | InteractiveWebAssembly | 实时交互，不依赖服务器连接 |
| 结账流程 | InteractiveServer | 涉及支付逻辑，必须在服务端处理 |
| 商品描述文本 | Static | 纯展示，无需任何交互 |

同一个应用，不同组件按需选择，没有折中。

## 适合用 Blazor United 的场景

Blazor United 在以下场景有明显的实际价值：

- **企业内部系统**：部分模块需要复杂交互，部分需要快速加载和权限控制
- **电商平台**：首页和列表页要 SEO，购物车和下单要实时交互
- **SEO 敏感的内容网站**：静态预渲染保证爬虫可读，动态组件提供用户体验
- **实时仪表盘**：数据展示可静态，控制面板可走服务端实时更新

## 几个值得注意的地方

Blazor United 目前还在演进阶段：

- 混合渲染模式在调试时比纯模式稍复杂，尤其是组件激活过程中的状态同步
- 团队需要理解三种渲染模式的约束，不同渲染环境下可用的 API 有差别（例如静态渲染模式里无法处理事件）
- 官方文档仍在完善，部分边缘行为需要实际验证

对于刚开始接触 Blazor 的团队，建议先理清每种模式的适用边界，再决定在具体项目里如何分配。

## 参考

- [What Is Blazor United in .NET 10 and Its Rendering Modes? - C# Corner](https://www.c-sharpcorner.com/article/what-is-blazor-united-in-net-10-and-its-rendering-modes/)
