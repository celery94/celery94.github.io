---
pubDatetime: 2025-08-11
tags: ["Angular", "Frontend", "Animations", "Web Development"]
slug: angular-20-2-native-animations
source: none
title: Angular 20.2 引入 Native Animations：更轻量、更现代的动画方式
description: Angular 20.2 推出 Native Animations，支持直接使用 HTML 属性和绑定语法实现入场、离场动画，无需依赖 @angular/animations 模块，让动画更轻量、高效、可维护。
---

# Angular 20.2 引入 Native Animations：更轻量、更现代的动画方式

Angular 团队在 20.2 版本中引入了一项重要更新——**Native Animations**。这意味着我们不再必须依赖 `@angular/animations` 模块，而是可以直接在模板中使用原生动画 API 来实现入场和离场效果。对于前端开发者来说，这不仅降低了动画的学习和使用门槛，也提升了性能与可维护性。

## 为什么需要 Native Animations

在此之前，Angular 的动画主要依赖 `@angular/animations` 模块，通过定义动画触发器和状态转换来实现。这种方式虽然功能强大，但存在几个问题：

- **额外依赖**：必须导入并注册 `@angular/animations`。
- **学习成本高**：需要掌握 Angular 特有的动画 DSL（领域特定语言）。
- **性能开销**：部分场景会引入额外的 JavaScript 处理，影响渲染性能。

Native Animations 则直接利用浏览器的原生 CSS 动画或 Web Animations API，无需额外依赖，也不需要编写复杂的动画触发器。

---

## 四种动画绑定方式

在 Angular 20.2 中，`animate.enter` 和 `animate.leave` 两个指令属性用于定义元素的入场与离场动画。它们支持四种绑定方式，满足不同场景的需求。

### 1. **字符串值绑定**（String Value）

直接使用动画类名或关键字：

```html
<img src="clouds.jpg" animate.enter="pop-in" animate.leave="pop-out" />
```

这种方式简单直观，适合静态动画定义。

---

### 2. **属性绑定**（Property Binding）

绑定到组件的类属性：

```html
<img
  src="clouds.jpg"
  [animate.enter]="enterClass"
  [animate.leave]="leaveClass"
/>
```

适用于动画类型可根据逻辑动态变化的场景。

---

### 3. **信号绑定**（Signal Binding）

支持绑定到 Angular **Signals**：

```html
<img
  src="clouds.jpg"
  [animate.enter]="enterClass()"
  [animate.leave]="leaveClass()"
/>
```

这种方式结合 Signals 的响应式特性，可以在状态变化时即时更新动画。

---

### 4. **事件绑定**（Event Binding）

可以通过事件绑定在动画生命周期中执行逻辑：

```html
<img
  src="clouds.jpg"
  (animate.enter)="animateEnter($event)"
  (animate.leave)="animateLeave($event)"
/>
```

适合需要在动画触发时执行额外业务逻辑的场景，例如数据加载、日志记录等。

---

## 与旧动画 API 对比

| 特性     | @angular/animations    | Native Animations  |
| -------- | ---------------------- | ------------------ |
| 依赖     | 需要额外模块           | 无需额外依赖       |
| 性能     | 可能有 JS 运算开销     | 基于浏览器原生动画 |
| 语法     | DSL + 触发器           | 直接绑定属性或类名 |
| 灵活性   | 功能强大，支持复杂序列 | 更适合简单高效动画 |
| 学习成本 | 高                     | 低                 |

Angular 团队已明确标注 **`@angular/animations` 将逐步废弃**，建议新项目优先使用 Native Animations。

---

## 原理拆解

Native Animations 实际上是 Angular 对 DOM 元素动画属性的一层封装。它在指令解析阶段，将 `animate.enter` 和 `animate.leave` 的值映射为 CSS 动画类名或直接调用 Web Animations API，并在元素进入或离开视图时自动应用。

这种做法让动画控制更贴近浏览器原生机制，减少了运行时的框架参与，从而获得更佳的性能。

---

## 实战示例

假设我们希望在图片进入时淡入，离开时淡出，可以这样写：

```html
<style>
  .fade-in {
    animation: fadeIn 0.5s forwards;
  }
  .fade-out {
    animation: fadeOut 0.5s forwards;
  }
  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @keyframes fadeOut {
    from {
      opacity: 1;
    }
    to {
      opacity: 0;
    }
  }
</style>

<img src="clouds.jpg" animate.enter="fade-in" animate.leave="fade-out" />
```

如果需要动态控制：

```ts
export class AppComponent {
  enterClass = "fade-in";
  leaveClass = "fade-out";
}
```

```html
<img
  src="clouds.jpg"
  [animate.enter]="enterClass"
  [animate.leave]="leaveClass"
/>
```

---

## 总结

Angular 20.2 的 Native Animations 是一次重要的现代化升级，它：

- 摆脱了 `@angular/animations` 的依赖
- 提供了更轻量、更直观的动画实现方式
- 保留了响应式和事件驱动的能力
- 利用浏览器原生动画机制提升性能

未来，建议开发者逐步迁移到这一新特性，既能提升性能，又能降低维护成本。
