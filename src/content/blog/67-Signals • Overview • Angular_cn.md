---
pubDatetime: 2024-03-27
tags: ["Angular", "Signals", "Overview"]
author: Angular
title: Signals • 概览 • Angular
description: Angular Signals 是一个系统，它可以精细地跟踪应用程序中的状态如何以及在何处被使用，从而允许框架优化渲染更新。
---

提示：在深入了解本综合指南之前，查看 Angular 的[基础知识](https://angular.dev/essentials/managing-dynamic-data)。

## 什么是 signals？

一个 **signal** 是一个围绕值的包装器，当该值改变时会通知感兴趣的消费者。Signals 可以包含任何值，从原始值到复杂的数据结构。

您通过调用 signal 的 getter 函数来读取 signal 的值，这允许 Angular 跟踪 signal 的使用位置。

Signals 可能是 _可写的_ 或 _只读的_。

### 可写的 signals

可写的 signals 提供了一个直接更新它们值的 API。您通过调用带有 signal 初始值的 `signal` 函数来创建可写的 signals：

```ts
const count = signal(0);

// Signals 是 getter 函数 - 调用它们读取它们的值。
console.log("计数是: " + count());
```

要改变可写 signal 的值，可以直接 `.set()`：

```ts
count.set(3);
```

或者使用 `.update()` 操作从前一个值计算新值：

```ts
// 将计数增加 1。
count.update(value => value + 1);
```

可写的 signals 有 `WritableSignal` 类型。

### 计算 signals

**计算 signal** 是从其他 signals 派生其值的只读 signals。您使用 `computed` 函数并指定一个派生来定义计算 signals：

```typescript
const count: WritableSignal<number> = signal(0);
const doubleCount: Signal<number> = computed(() => count() * 2);
```

`doubleCount` signal 依赖于 `count` signal。每当 `count` 更新时，Angular 知道 `doubleCount` 也需要更新。

#### 计算 signals 是懒计算且被记忆的

`doubleCount` 的派生函数直到您第一次读取 `doubleCount` 时才运行以计算其值。然后缓存计算出来的值，如果您再次读取 `doubleCount`，它将返回缓存的值而不重新计算。

如果您之后改变了 `count`，Angular 知道 `doubleCount` 的缓存值不再有效，下次您读取 `doubleCount` 时，它的新值将被计算。

因此，您可以在计算 signals 中安全地执行计算成本高的派生，例如过滤数组。

#### 计算 signals 不是可写的 signals

您不能直接给计算 signal 赋值。也就是说，

```ts
doubleCount.set(3);
```

会产生一个编译错误，因为 `doubleCount` 不是 `WritableSignal`。

#### 计算 signal 的依赖项是动态的

只有在派生过程中实际读取的 signals 被跟踪。例如，在这个计算中，只有当 `showCount` signal 为 true 时，`count` signal 才被读取：

```ts
const showCount = signal(false);
const count = signal(0);
const conditionalCount = computed(() => {
  if (showCount()) {
    return `计数是 ${count()}。`;
  } else {
    return "这里没有什么可看的！";
  }
});
```

当您读取 `conditionalCount` 时，如果 `showCount` 是 `false`，则返回 "这里没有什么可看的！" 消息，_不会_ 读取 `count` signal。这意味着如果您稍后更新 `count`，它将 _不会_ 导致 `conditionalCount` 的重新计算。

如果您将 `showCount` 设置为 `true` 然后再次读取 `conditionalCount`，派生将重新执行并取 `showCount` 为 `true` 的分支，返回显示 `count` 值的消息。改变 `count` 将使 `conditionalCount` 的缓存值失效。

注意，依赖项在派生过程中可以被移除和添加。如果您稍后将 `showCount` 再次设置为 `false`，那么 `count` 将不再被认为是 `conditionalCount` 的依赖项。

## 在 `OnPush` 组件中读取 signals

当您在 `OnPush` 组件模板中读取 signal 时，Angular 跟踪该 signal 作为该组件的依赖项。当该 signal 的值改变时，Angular 自动[标记](https://angular.dev/api/core/ChangeDetectorRef/#markforcheck)该组件，确保下次变更检测运行时更新它。有关 `OnPush` 组件的更多信息，请参考[跳过组件子树](https://angular.dev/best-practices/skipping-subtrees)指南。

## Effects

Signals 之所以有用，是因为它们在更改时会通知感兴趣的消费者。**effect** 是一个操作，当一个或多个 signal 值变化时就会运行。您可以使用 `effect` 函数创建一个 effect：

```ts
effect(() => {
  console.log(`当前计数是: ${count()}`);
});
```

Effects 总是会**至少运行一次。** 当一个 effect 运行时，它跟踪任何 signal 值读取。每当这些 signal 值中的任何一个改变时，effect 就会再次运行。与计算 signals 类似，effects 动态地跟踪它们的依赖项，并且只跟踪最近执行中读取的 signals。

Effects 总是以**异步方式执行**，在变更检测过程中。

### Effects 的用例

在大多数应用程序代码中很少需要 effects，但在特定情况下可能会很有用。这里有一些情况，其中 `effect` 可能是一个好的解决方案：

- 记录正在显示的数据及其更改时刻，无论是用于分析还是作为调试工具。
- 与 `window.localStorage` 保持数据同步。
- 添加无法用模板语法表达的自定义 DOM 行为。
- 对 `<canvas>`、图表库或其他第三方 UI 库执行自定义渲染。

<docs-callout critical title="何时不使用 effects">
避免使用 effects 来传播状态变化。这可能导致 `ExpressionChangedAfterItHasBeenChecked` 错误、无限循环更新或不必要的变更检测周期。

因为这些风险，Angular 默认情况下阻止您在 effects 中设置 signals。如果绝对必要，可以通过在创建 effect 时设置 `allowSignalWrites` 标志来启用它。

相反地，使用 `computed` signals 来模型化依赖于其他状态的状态。
</docs-callout>

### 注入上下文

默认情况下，您只能在[注入上下文](https://angular.dev/guide/di/dependency-injection-context)中创建一个 `effect()`（在有 `inject` 函数的地方）。满足此要求的最简单方法是在组件、指令或服务的 `constructor` 中调用 `effect`：

```ts
@Component({...})
export class EffectiveCounterComponent {
  readonly count = signal(0);
  constructor() {
    // 注册一个新的 effect。
    effect(() => {
      console.log(`计数是: ${this.count()}`);
    });
  }
}
```

或者，可以将 effect 分配给一个字段（这也给它提供了一个描述性名称）。

```ts
@Component({...})
export class EffectiveCounterComponent {
  readonly count = signal(0);

  private loggingEffect = effect(() => {
    console.log(`计数是: ${this.count()}`);
  });
}
```

要在构造函数之外创建一个 effect，您可以通过其选项将一个 `Injector` 传递给 `effect`：

```ts
@Component({...})
export class EffectiveCounterComponent {
  readonly count = signal(0);
  constructor(private injector: Injector) {}

  initializeLogging(): void {
    effect(() => {
      console.log(`计数是: ${this.count()}`);
    }, {injector: this.injector});
  }
}
```

### 销毁 effects

创建一个 effect 时，它会在其封闭上下文被销毁时自动销毁。这意味着在组件中创建的 effects 会在组件被销毁时销毁。指令、服务等中的 effects 也是如此。

Effects 返回一个 `EffectRef`，您可以使用它来手动销毁它们，通过调用 `.destroy()` 方法。您可以将此与 `manualCleanup` 选项结合使用，以创建一个持续到手动销毁为止的 effect。一定要小心清理这些不再需要的 effects。

## 高级主题

### Signal 等值函数

创建 signal 时，您可以选择提供一个等值函数，该函数用于检查新值是否实际上与前一个值不同。

```ts
import _ from "lodash";

const data = signal(["test"], { equal: _.isEqual });

// 即使这是一个不同的数组实例，深度等值函数将认为这些值是相等的，signal 不会触发任何更新。
data.set(["test"]);
```

等值函数可以提供给可写和计算 signals。

HELPFUL: 默认情况下，signals 使用引用等值（`===` 比较）。

### 不跟踪依赖项的读操作

极少数情况下，您可能希望在像 `computed` 或 `effect` 这样的反应式函数中执行可能读取 signals 的代码，_而不_ 创建依赖项。

例如，假设当 `currentUser` 更改时，应该记录 `counter` 的值。您可以创建一个 `effect`，它读取两个 signals：

```ts
effect(() => {
  console.log(`用户设置为 ${currentUser()}，计数器是 ${counter()}`);
});
```

这个示例将在 _任一_ `currentUser` 或 `counter` 更改时记录一条消息。然而，如果 effect 只应在 `currentUser` 更改时运行，则读取 `counter` 只是偶然的，而 `counter` 的更改不应记录新消息。

您可以通过调用带有 `untracked` 的 getter 来防止 signal 读取被跟踪：

```ts
effect(() => {
  console.log(`用户设置为 ${currentUser()}，计数器是 ${untracked(counter)}`);
});
```

当一个 effect 需要调用一些不应该作为依赖项的外部代码时，`untracked` 也很有用：

```ts
effect(() => {
  const user = currentUser();
  untracked(() => {
    // 如果 `loggingService` 读取 signals，它们不会被计算为此 effect 的依赖项。
    this.loggingService.log(`用户设置为 ${user}`);
  });
});
```

### Effect 清理函数

Effects 可能会启动长时间运行的操作，如果 effect 在第一个操作完成之前再次运行或被销毁，您应该取消这些操作。当您创建一个 effect 时，您的函数可以选择接受 `onCleanup` 函数作为其第一个参数。这个 `onCleanup` 函数让您注册一个在 effect 的下一次运行开始之前或 effect 被销毁时调用的回调。

```ts
effect(onCleanup => {
  const user = currentUser();

  const timer = setTimeout(() => {
    console.log(`1秒前，用户变成了 ${user}`);
  }, 1000);

  onCleanup(() => {
    clearTimeout(timer);
  });
});
```
