---
pubDatetime: 2024-02-06
tags: ["Productivity", "Tools", "Frontend"]
title: 如何创建多样式主题 -- Angular Material Theme, Part II
description: 为 Angular Material 创建多个自定义主题涉及几个关键步骤。Angular Material 的主题系统基于 Google 的 Material Design 构建，允许你为你的应用制定一个反映你品牌的视觉语言。以下是为你的 Angular Material 应用创建多个自定义主题的方法：
---

为 Angular Material 创建多个自定义主题涉及几个关键步骤。Angular Material 的主题系统基于 Google 的 Material Design 构建，允许你为你的应用制定一个反映你品牌的视觉语言。以下是为你的 Angular Material 应用创建多个自定义主题的方法：

### 1. 设置你的 Angular 项目

首先，确保你的 Angular 项目已经设置好并且安装了 Angular Material。如果你还没有安装 Angular Material，可以通过运行以下命令来安装：

```bash
ng add @angular/material
```

### 2. 创建自定义主题文件

对于你想要创建的每个主题，你需要一个单独的 SCSS 文件。你可以将这些文件存储在一个专门的文件夹中，比如 `src/themes/`。例如，要创建两个自定义主题，你可能会有：

- `src/themes/light.scss`
- `src/themes/dark.scss`

### 3. 定义你的主题

在每个主题文件中，你将定义你的自定义主题。每个主题文件通常包括：

- **为主色、辅助色和警告色定义的调色板**。
- **使用 `mat.define-light-theme()` 或 `mat.define-dark-theme()` 函数创建的主题对象**，具体取决于你想要的是亮色主题还是暗色主题。
- **排版配置**（可选），包括字体大小、字体重量和行高等，你可以为不同的文本元素（如标题、正文文本和按钮标签）定义排版样式。
- **密度** （可选），自定义密度（Density）允许你调整组件的大小和间距，以适应不同的设计语言和屏幕密度。
- **自定义组件主题**（可选）。

这里是一个自定义亮色主题的例子：

```scss
@use "@angular/material" as mat;

// 定义颜色调色板
$primary: mat.define-palette(mat.$indigo-palette);
$accent: mat.define-palette(mat.$pink-palette, A200, A100, A400);
$warn: mat.define-palette(mat.$red-palette);

// 定义自定义排版配置
$custom-typography: mat.define-typography-config(
  $font-family: "Roboto, sans-serif",
  $headline-1: mat.define-typography-level(32px, 48px, 700),
  $headline-2: mat.define-typography-level(24px, 36px, 500),
  $body-1: mat.define-typography-level(16px, 24px, 400),
  // 更多自定义设置...
);

// 创建主题
$theme: mat.define-light-theme(
  (
    color: (
      primary: $primary,
      accent: $accent,
      warn: $warn,
    ),
    typography: $custom-typography,
    density: -2,
  )
);

// 包含所有组件主题
@include mat.all-component-themes($theme);
```

#### 3.1 定义自己的调色板

调色板是一组颜色，用于定义你的应用的主色、辅助色和警告色。你可以使用 Angular Material 的 `mat.define-palette()` 函数来定义你的调色板。这个函数接受一个基础调色板（如 `$my-palette`）和一个可选的颜色映射对象作为参数。例如：

```scss
$md-primary: (
  50: #e5e8f1,
  100: #bec5dd,
  200: #939fc6,
  300: #6879af,
  400: #475c9d,
  500: #273f8c,
  600: #233984,
  700: #1d3179,
  800: #17296f,
  900: #0e1b5c,
  A100: #91a1ff,
  A200: #5e75ff,
  A400: #2b49ff,
  A700: #1233ff,
  contrast: (
    50: #000000,
    100: #000000,
    200: #000000,
    300: #ffffff,
    400: #ffffff,
    500: #ffffff,
    600: #ffffff,
    700: #ffffff,
    800: #ffffff,
    900: #ffffff,
    A100: #000000,
    A200: #ffffff,
    A400: #ffffff,
    A700: #ffffff,
  ),
);
$primary: mat.define-palette(mat.$md-palette);
```

这是一个 Material Design Palette 生成器，你可以使用它来生成你自己的调色板。

[Material Design Color Generator](http://mcg.mbitson.com/)

Material Design 官方也有一个调色板生成器，你可以使用它来生成你自己的调色板。

[Tools for picking colors](https://m2.material.io/design/color/the-color-system.html#tools-for-picking-colors)

### 4. 应用主题

要使用你的主题，你需要根据应用于应用中更高级别元素（通常是 `<body>` 或 `<app-root>`）的类条件性地加载它们。你可以使用一些 TypeScript 和 Angular 绑定动态切换主题。

首先，使用 Angular Material 的 `@import` 规则将每个主题的 CSS 添加到全局样式文件（`styles.scss`）中，并用你将用作该主题标记的类将它们包围起来：

```scss
@import "themes/light.scss";
@import "themes/dark.scss";

.light-theme {
  @include light;
}

.dark-theme {
  @include dark;
}
```

然后，在你的组件或服务中，你可以通过改变 `<body>` 元素上的类来切换主题：

```typescript
switchTheme(themeName: string) {
  document.body.className = themeName;
}
```

调用 `switchTheme('light-theme')` 或 `switchTheme('dark-theme')` 来切换不同的主题。

### 5. 定义light和dark主题，并且自动切换

你可以使用 Angular Material 的 `mat.define-light-theme()` 和 `mat.define-dark-theme()` 函数来定义你的亮色和暗色主题。这些函数接受一个主题配置对象作为参数，该对象包含颜色、排版和密度配置。

接下来，在Angular中根据用户的系统偏好或者一个切换按钮来改变主题。

自动检测系统主题偏好：可以通过监听prefers-color-scheme来实现。

```typescript
import { Component, HostBinding } from "@angular/core";

@Component({
  selector: "app-root",
  templateUrl: "./app.component.html",
  styleUrls: ["./app.component.css"],
})
export class AppComponent {
  @HostBinding("class") className = "";

  constructor() {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
    this.toggleTheme(prefersDark.matches);

    // 监听系统主题变化
    prefersDark.addEventListener("change", mediaQuery =>
      this.toggleTheme(mediaQuery.matches)
    );
  }

  toggleTheme(isDark: boolean) {
    this.className = isDark ? "dark-theme" : "light-theme";
  }
}
```

### 6. 多主题的提示

- **全局与组件样式**：记住 Angular 默认封装样式。使用全局样式进行主题设计。
- **优化**：考虑动态加载主题以减少初始加载时间。
- **无障碍性**：确保你的主题保持无障碍的对比度比例并遵守 WCAG 指南。

按照这些步骤，你可以为你的 Angular Material 应用创建一个多功能且视觉上吸引人的应用，这个应用与你的品牌和用户体验目标相符。
