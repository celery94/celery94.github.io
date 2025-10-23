---
pubDatetime: 2025-08-08
tags: ["Productivity", "Tools", "Frontend"]
slug: angular-20-2-zoneless-signals
source: 本文基于 Angular 官方更新内容与社区讨论整理
title: Angular 20.2 稳定发布 Zoneless 模式，Signals 全面接管异步变更检测
description: Angular 20.2 将 Zoneless 模式稳定化，提升性能的同时，配合 Signals 解决 setTimeout、Promise 等异步操作不触发视图更新的问题。
---

# Angular 20.2 稳定发布 Zoneless 模式，Signals 全面接管异步变更检测

Angular 20.2 带来了一个影响深远的更新：**Zoneless 模式正式稳定**。这意味着 Angular 在运行时将不再依赖 Zone.js 来自动跟踪异步任务的完成，从而触发变更检测。

这一改变对性能、架构灵活性、以及开发模式都有重要影响。然而，它也带来一个直接问题：某些异步操作（如 `setTimeout`、`Promise`）将不再自动更新 UI。幸运的是，Angular 引入的 **Signals API** 为此提供了优雅的解决方案。

---

## Zoneless 模式是什么？

传统的 Angular 应用依赖 **Zone.js** 拦截浏览器的异步 API（如 `setTimeout`、`addEventListener`、XHR 请求等），并在任务完成时触发一次全局变更检测。这种机制虽然简单直接，但会带来额外的性能开销，并且在某些场景下会触发不必要的更新。

Zoneless 模式的核心思想是——**Angular 不再依赖 Zone.js**，而是要求开发者显式声明状态变化，从而让框架有的放矢地更新 UI。

---

## Zoneless 模式下的问题

在 Zoneless 模式中，Angular **不会自动追踪** 某些异步事件。例如：

```ts
template: `
  {{ login }}
`;

login = "guest";

setTimeout(() => {
  this.login = "admin";
}, 2000);
```

在 Zone.js 环境中，这段代码会在 2 秒后自动刷新模板。但在 Zoneless 模式下，**UI 不会更新**，因为 Angular 不知道 `login` 发生了变化。

---

## Signals 让变更检测重新工作

Angular 20.2 建议在 Zoneless 模式下使用 **Signals** 来显式声明可响应的状态。改写上面的代码：

```ts
import { signal } from "@angular/core";

template: `
  {{ login() }}
`;

login = signal("guest");

setTimeout(() => {
  this.login.set("admin");
}, 2000);
```

区别在于：

- `login` 变成了一个信号（`signal`），是一个可追踪的响应式值。
- 调用 `login()` 会在模板中订阅它，一旦值变化，模板会自动更新。
- 调用 `login.set(...)` 明确告诉 Angular 有状态变化。

这样，即使在 Zoneless 模式下，Angular 也能精准追踪并更新 UI。

---

## 性能与架构的变化

Zoneless 模式的好处非常明显：

1. **性能提升**：移除 Zone.js 监控的全局副作用，减少不必要的变更检测。
2. **更可控的更新**：只在信号状态变化时更新视图，而非每个异步事件后全局扫描。
3. **架构灵活性**：可以与其他响应式状态管理工具（如 RxJS、MobX、NgRx）更自然地集成。

不过，这也意味着开发者需要更有意识地管理 UI 状态，否则可能出现 UI 不刷新的“静态页面”问题。

---

## 迁移建议

对于准备升级到 Angular 20.2 并使用 Zoneless 模式的项目，可以遵循以下迁移路径：

- **逐步引入 Signals**：先将频繁变化的核心状态迁移为信号，再逐步替换其他状态。
- **替代 `ngZone.run`**：过去依赖 `ngZone.run()` 手动触发变更检测的地方，可改用信号更新。
- **与 RxJS 集成**：将流数据转换为信号（`toSignal()`），实现无 Zone.js 的响应式 UI。

---

## 总结

Angular 20.2 的 Zoneless 模式稳定化，是 Angular 生态向“显式状态驱动 UI”理念的一次重大转型。借助 Signals，开发者既能摆脱 Zone.js 带来的性能负担，又能在无侵入的情况下维持响应式的用户体验。

未来的 Angular 应用，将更多依赖这种显式状态声明方式，类似 React 的 Hooks 和 Vue 的响应式系统，但依然保留 Angular 模板语法的优势。
