---
pubDatetime: 2025-08-22
tags: ["Productivity", "Tools", "Frontend"]
slug: js-event-target
source: null
title: 深入理解 JavaScript 的 event.target
description: 本文详细解析了 JavaScript 中 event.target 的特性、与 event.currentTarget 的区别，并结合事件委托的实用案例，帮助开发者高效处理 DOM 事件。
---

---

# 深入理解 JavaScript 的 event.target

在 JavaScript 的事件处理机制中，`event.target` 是一个非常重要的属性。它是 `Event` 对象的一个属性，用于指向**触发事件的具体 DOM 元素**。理解并正确使用 `event.target`，不仅能帮助我们获取用户实际交互的元素，还能写出更高效的事件处理逻辑。

## event.target 的特性

首先，我们需要明确 `event.target` 的几个核心特性：

**指向实际触发事件的元素**
当一个事件在 DOM 树中冒泡或捕获时，`event.target` 始终指向用户最初交互的那个元素，而不是绑定事件监听器的元素。比如，用户点击了一个按钮，即使监听器绑定在父容器上，`event.target` 依旧会指向按钮。

**只读属性**
`event.target` 由浏览器设置，是只读的，开发者无法直接修改它。它的值在事件发生时就已经固定。

**与 event.currentTarget 的区别**
`event.currentTarget` 表示当前绑定监听器的元素，而 `event.target` 表示用户实际操作的元素。这一区别在事件冒泡或委托时尤为重要。

举个例子：

- 如果一个点击事件绑定在 `<ul>` 上，用户点击 `<li>` 元素：

  - `event.target` → `<li>`（实际点击的元素）
  - `event.currentTarget` → `<ul>`（绑定事件监听器的元素）

## 事件委托（Event Delegation）

`event.target` 的应用场景之一是**事件委托**。在复杂的页面中，我们往往有多个子元素需要响应事件，如果为每个子元素都绑定事件监听器，不仅影响性能，也会增加内存开销。

事件委托的做法是：
把事件监听器绑定在它们的父容器上，利用事件冒泡机制，通过 `event.target` 来判断用户操作的是哪个子元素。

### 示例：代办事项列表

假设我们有一个待办事项列表，每一项都有一个复选框。我们希望用户勾选后，该事项可以被标记为完成。

HTML 代码：

```html
<ul id="to-do-list">
  <li class="todo-item">
    <input type="checkbox" id="item1" />
    <label for="item1">Buy groceries</label>
  </li>
  <li class="todo-item">
    <input type="checkbox" id="item2" />
    <label for="item2">Finish JavaScript project</label>
  </li>
</ul>
```

JavaScript 代码：

```javascript
const todolist = document.getElementById("to-do-list");

todolist.addEventListener("change", function (event) {
  if (event.target.type === "checkbox") {
    const listItem = event.target.closest(".todo-item");
    if (event.target.checked) {
      listItem.classList.add("completed");
    } else {
      listItem.classList.remove("completed");
    }
  }
});
```

在这个例子中，`<ul>` 作为事件监听器的挂载点，而通过 `event.target` 我们能精准识别被点击的复选框，并给对应的 `<li>` 元素添加或移除 `completed` 样式。

## 为什么使用事件委托？

事件委托的优势在于性能和可维护性：

- **减少事件监听器数量**：不必为每个子元素单独绑定事件。
- **动态元素支持**：即使新添加的子元素也能自动响应事件，而无需额外绑定。
- **内存优化**：避免过多的事件绑定带来的资源消耗。

## 总结

`event.target` 是 JavaScript 事件机制中获取用户操作元素的关键属性，配合事件委托可以显著提升代码的性能和简洁度。掌握 `event.target` 与 `event.currentTarget` 的区别，是编写健壮、高效 DOM 事件处理代码的基础。

在实际项目中，推荐优先使用事件委托来管理列表项、菜单、按钮组等场景，这不仅能减少重复代码，还能更好地应对动态 DOM 的变化。
