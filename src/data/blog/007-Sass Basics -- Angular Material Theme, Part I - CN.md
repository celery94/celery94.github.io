---
pubDatetime: 2024-02-05T16:53:06
tags: ["Productivity", "Tools", "Frontend"]
source: https://sass-lang.com/guide/
title: Sass：Sass 基础 -- Angular Material Theme, Part I
description: Angular Material 的主题 API 是用 Sass 构建的。你可以通过使用下面描述的预构建主题来不使用 Sass 而使用 Angular Material。然而，直接使用 Sass API 可以让你对应用程序中的样式拥有最大的控制权。
---

# Sass：Sass 基础 -- Angular Material Theme, Part I

> ## 摘要
>
> Angular Material 的主题 API 是用 Sass 构建的。你可以通过使用下面描述的预构建主题来不使用 Sass 而使用 Angular Material。然而，直接使用 Sass API 可以让你对应用程序中的样式拥有最大的控制权。
>
> 本文是 Sass 官方文档的翻译，原文链接在[这里](https://sass-lang.com/guide/)。

---

在你可以使用 Sass 之前，你需要在你的项目上设置它。如果你只是想在这里浏览，继续吧，但我们建议你先安装 Sass。如果你想学习如何设置一切，请[点击这里](https://sass-lang.com/install)。

## [预处理](https://sass-lang.com/guide//#preprocessing)

CSS 本身可以很有趣，但样式表正在变得越来越大，越来越复杂，也越来越难以维护。这就是预处理器可以帮忙的地方。Sass 有一些 CSS 中还不存在的功能，如嵌套、混入、继承，以及其他一些帮助你编写健壮、可维护 CSS 的巧妙工具。

一旦你开始使用 Sass，它会将你的预处理 Sass 文件保存为可以在网站中使用的普通 CSS 文件。

使这一切发生的最直接方式是在你的终端中。一旦安装了 Sass，你可以使用 `sass` 命令将你的 Sass 编译为 CSS。你需要告诉 Sass 从哪个文件构建，以及输出 CSS 到哪里。例如，在你的终端运行 `sass input.scss output.css` 会取一个 Sass 文件 `input.scss`，并将该文件编译为 `output.css`。

你也可以使用 `--watch` 标志来监视单个文件或目录。监视标志告诉 Sass 监视你的源文件的更改，并在你每次保存 Sass 时重新编译 CSS。如果你想要监视（而不是手动构建）你的 `input.scss` 文件，你只需在命令中添加监视标志，如下所示：

```shellsession
sass --watch input.scss output.css
```

你可以通过使用文件夹路径作为输入和输出，并用冒号分隔它们来监视和输出到目录。在这个例子中：

```shellsession
sass --watch app/sass:public/stylesheets
```

Sass 会监视 `app/sass` 文件夹中的所有文件的更改，并将 CSS 编译到 `public/stylesheets` 文件夹。

### 💡 趣事实：

Sass 有两种语法！SCSS 语法（`.scss`）是最常用的。它是 CSS 的超集，这意味着所有有效的 CSS 也是有效的 SCSS。缩进语法（`.sass`）较不常见：它使用缩进而不是大括号来嵌套语句，并使用换行符而不是分号来分隔它们。我们所有的示例都提供了两种语法。

---

## [变量](https://sass-lang.com/guide//#variables)

把变量想象成一种存储你想在整个样式表中重用的信息的方式。你可以存储诸如颜色、字体堆栈或任何你认为会想要重用的 CSS 值。Sass 使用 `$` 符号来创建一个变量。这里有一个例子：

### SCSS 语法

```scss
$font-stack: Helvetica, sans-serif;
$primary-color: #333;

body {
  font: 100% $font-stack;
  color: $primary-color;
}
```

### CSS 输出

```css
body {
  font:
    100% Helvetica,
    sans-serif;
  color: #333;
}
```

当 Sass 被处理时，它会取我们为 `$font-stack` 和 `$primary-color` 定义的变量，并输出带有我们变量值的普通 CSS。在处理品牌颜色并保持整个网站颜色一致性时，这可以非常强大。

---

## [嵌套](https://sass-lang.com/guide//#nesting)

当编写 HTML 时，你可能已经注意到它具有清晰的嵌套和视觉层次结构。另一方面，CSS 则没有。

Sass 允许你以一种遵循 HTML 相同视觉层次结构的方式嵌套你的 CSS 选择器。要知道，过度嵌套的规则会导致过度具体的 CSS，这可能难以维护，并且通常被认为是不好的实践。

考虑到这一点，这里有一个网站导航的一些典型样式的例子：

### SCSS 语法

```scss
nav {
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: inline-block;
  }

  a {
    display: block;
    padding: 6px 12px;
    text-decoration: none;
  }
}
```

### CSS 输出

```css
nav ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
nav li {
  display: inline-block;
}
nav a {
  display: block;
  padding: 6px 12px;
  text-decoration: none;
}
```

你会注意到 `ul`、`li` 和 `a` 选择器被嵌套在 `nav` 选择器内。这是一种组织你的 CSS 并使其更具可读性的好方法。

---

## [部分文件](https://sass-lang.com/guide//#partials)

你可以创建包含小段 CSS 的部分 Sass 文件，然后可以在其他 Sass 文件中包含这些文件。这是模块化你的 CSS 并帮助保持事物更易于维护的好方法。部分文件是以前导下划线命名的 Sass 文件。你可能会将其命名为像 `_partial.scss` 这样的名称。下划线让 Sass 知道该文件只是一个部分文件，并且不应该生成 CSS 文件。Sass 部分文件使用 `@use` 规则。

---

## [模块](https://sass-lang.com/guide//#modules)

你不必在单一文件中编写所有的 Sass。你可以使用 `@use` 规则以任何你想要的方式分割它。这个规则将另一个 Sass 文件作为*模块*加载，这意味着你可以在你的 Sass 文件中使用基于文件名的命名空间来引用其变量、[混入](https://sass-lang.com/guide//#mixins) 和 [函数](https://sass-lang.com/documentation/at-rules/function)。使用文件还会在你编译的输出中包含它生成的 CSS！

### SCSS 语法

```scss
// _base.scss
$font-stack: Helvetica, sans-serif;
$primary-color: #333;

body {
  font: 100% $font-stack;
  color: $primary-color;
}
```

```scss
// styles.scss
@use "base";

.inverse {
  background-color: base.$primary-color;
  color: white;
}
```

### CSS 输出

```css
body {
  font:
    100% Helvetica,
    sans-serif;
  color: #333;
}

.inverse {
  background-color: #333;
  color: white;
}
```

注意我们在 `styles.scss` 文件中使用了 `@use 'base';`。当你使用一个文件时，你不需要包含文件扩展名。Sass 很聪明，会为你弄清楚。

---

## [混入](https://sass-lang.com/guide//#mixins)

在 CSS 中，有些事情写起来有点乏味，尤其是与 CSS3 和许多供应商前缀有关。混入允许你创建一组你想在站点中重用的 CSS 声明。它有助于保持你的 Sass 非常 DRY。你甚至可以传入值，使你的混入更加灵活。这里是一个 `theme` 的例子。

### SCSS 语法

```scss
@mixin theme($theme: DarkGray) {
  background: $theme;
  box-shadow: 0 0 1px rgba($theme, 0.25);
  color: #fff;
}

.info {
  @include theme;
}
.alert {
  @include theme($theme: DarkRed);
}
.success {
  @include theme($theme: DarkGreen);
}
```

### CSS 输出

```css
.info {
  background: DarkGray;
  box-shadow: 0 0 1px rgba(169, 169, 169, 0.25);
  color: #fff;
}

.alert {
  background: DarkRed;
  box-shadow: 0 0 1px rgba(139, 0, 0, 0.25);
  color: #fff;
}

.success {
  background: DarkGreen;
  box-shadow: 0 0 1px rgba(0, 100, 0, 0.25);
  color: #fff;
}
```

要创建一个混入，你使用 `@mixin` 指令并给它一个名字。我们给我们的混入命名为 `theme`。我们也在括号内使用变量 `$theme`，这样我们就可以传入任何我们想要的 `theme`。在你创建混入后，你可以使用它作为一个 CSS 声明，以 `@include` 开始，后跟混入的名称。

---

## [扩展/继承](https://sass-lang.com/guide//#extend-inheritance)

使用 `@extend` 允许你从一个选择器共享一组 CSS 属性到另一个选择器。在我们的例子中，我们将创建一个简单的消息系列，用于错误、警告和成功消息，这使用了与扩展紧密相连的另一个特性，即占位符类。占位符类是一种特殊类型的类，只有在被扩展时才打印，可以帮助保持你的编译后的 CSS 整洁干净。

### SCSS 语法

```scss
/* 这个 CSS 会打印，因为 %message-shared 被扩展了。 */
%message-shared {
  border: 1px solid #ccc;
  padding: 10px;
  color: #333;
}

// 这个 CSS 不会打印，因为 %equal-heights 从未被扩展。
%equal-heights {
  display: flex;
  flex-wrap: wrap;
}

.message {
  @extend %message-shared;
}

.success {
  @extend %message-shared;
  border-color: green;
}

.error {
  @extend %message-shared;
  border-color: red;
}

.warning {
  @extend %message-shared;
  border-color: yellow;
}
```

### CSS 输出

```css
/* 这个 CSS 会打印，因为 %message-shared 被扩展了。 */
.warning,
.error,
.success,
.message {
  border: 1px solid #ccc;
  padding: 10px;
  color: #333;
}

.success {
  border-color: green;
}

.error {
  border-color: red;
}

.warning {
  border-color: yellow;
}
```

上面的代码的作用是告诉 `.message`、`.success`、`.error` 和 `.warning` 表现得就像 `%message-shared` 一样。这意味着 `%message-shared` 出现的任何地方，`.message`、`.success`、`.error` 和 `.warning` 也会出现。魔法发生在生成的 CSS 中，这些类将获得与 `%message-shared` 相同的 CSS 属性。这帮助你避免在 HTML 元素上写多个类名。

你可以扩展 Sass 中的大多数简单 CSS 选择器以及占位符类，但使用占位符是确保你不扩展在样式中其他地方嵌套的类的最简单方法，这可能导致你的 CSS 中出现意外的选择器。

注意，因为 `%equal-heights` 从未被扩展，所以 `%equal-heights` 中的 CSS 不会生成。

---

## [运算符](https://sass-lang.com/guide//#operators)

在你的 CSS 中进行数学运算非常有帮助。Sass 有一些标准的数学运算符，如 `+`、`-`、`*`、`math.div()` 和 `%`。在我们的例子中，我们将进行一些简单的数学运算，来计算 `article` 和 `aside` 的宽度。

### SCSS 语法

```scss
@use "sass:math";

.container {
  display: flex;
}

article[role="main"] {
  width: math.div(600px, 960px) * 100%;
}

aside[role="complementary"] {
  width: math.div(300px, 960px) * 100%;
  margin-left: auto;
}
```

### CSS 输出

```css
.container {
  display: flex;
}

article[role="main"] {
  width: 62.5%;
}

aside[role="complementary"] {
  width: 31.25%;
  margin-left: auto;
}
```

我们创建了一个基于 960px 的非常简单的流体网格。Sass 中的运算让我们可以轻松地将像素值转换为百分比。
