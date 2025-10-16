---
pubDatetime: 2024-03-28
tags: ["Productivity", "Tools", "Frontend"]
source: https://blog.angular-university.io/angular-signals/
author: Angular University
title: Angular Signals 完全指南
description: 一个关于如何在 Angular 应用程序中使用 Signals 的完全指南。学习 signals、它们的好处、最佳实践和模式，并避免最常见的陷阱。
---

> ## 摘要
>
> 一个关于如何在 Angular 应用程序中使用 Signals 的完全指南。学习 signals、它们的好处、最佳实践和模式，并避免最常见的陷阱。

---

Angular Signals 最初在 Angular 17 中引入，它们非常强大。

Signals 的整个目的是为开发者提供一种新的**易于使用的响应式基元**，可以用来以响应式风格构建应用程序。

Signals 有一个易于理解的 API，用于向框架报告数据变化，允许框架优化变化检测和重新渲染的方式，这种方式以前是不可能的。

有了 Signals，Angular 将能够精确地确定页面的哪些部分需要更新，并仅更新这些部分，不多也不少。

这与目前发生的情况形成对比，例如默认的变化检测，Angular 必须检查页面上的所有组件，即使它们消费的数据没有变化。

Signals 的一切都是关于使 DOM 的更新非常**细粒度**，这在当前的变化检测系统中是不可能的。

Signals 都是关于通过消除 Zone.js 来提高应用程序的运行时性能。

即使没有运行时性能的好处，Signals 也是以响应式风格构建应用程序的一个好方式。

Signals 还比使用 RxJS 在应用程序中传播数据变化时**更容易使用和理解**。

Signals 是改变游戏规则的，它们把 Angular 中的响应性提升到了一个全新的水平！

在本指南中，我们将详细探索 Signals API，解释 signals 通常如何工作，以及讨论你应该注意的最常见的陷阱。

> **注意：**Signals 尚未接入 Angular 变化检测系统。在这一点上，尽管大部分 Signals API 已经不再是开发者预览阶段，*但*目前还没有任何基于 signal 的组件。
> 这可能在 Angular 17.2 版本左右可用，待确认。
> 但这并不妨碍我们从现在开始就学习有关 signals 及其优势的知识，为即将到来的内容做准备。

## Table of Contents

本篇文章覆盖以下主题：

- 什么是 Signals？
- 如何读取 signal 的值？
- 如何修改 signal 的值？
- update() Signal API
- 使用 signals 而不是原始值的主要优势是什么？
- computed() Signal API
- 我们如何订阅一个 signal？
- 我们可以从计算 signal 中读取 signal 的值而不创建依赖么？
- 在创建计算 signal 时要注意哪些主要陷阱？
- signal 的依赖关系是否仅基于对计算函数的初始调用来确定？
- 带有数组和对象值的 signals
- 覆盖 signal 相等性检查
- 使用 effect() API 检测 signal 变化
- Signals 与变化检测之间的关系是什么？
- 如何修复错误 NG0600：不允许在 `computed` 或 `effect` 中写入 signals
- 如何在需要时从效果中设置 signals
- 默认效果清理机制
- 如何手动清理效果
- 在效果销毁时执行清理操作
- 只读 signals
- 在多个组件中使用 signal
- 如何创建基于 signal 的反应式数据服务
- Signals 和 OnPush 组件
- 我可以在组件/存储/服务之外创建 signals 吗？
- Signals 与 RxJs 的比较
- 总结

**注意**：如果你想了解关于 Angular 17 之外的其他功能，请查看以下文章：

- [Angular @if: 完全指南](https://blog.angular-university.io/angular-if/)
- [Angular @for: 完全指南](https://blog.angular-university.io/angular-for/)
- [Angular @switch: 完全指南](https://blog.angular-university.io/angular-switch/)
- [Angular @defer: 完全指南](https://blog.angular-university.io/angular-defer/)

如果你想了解有关 Signal 输入的信息，请查看：

[Angular Signal Inputs: 完全指南](https://blog.angular-university.io/angular-signal-inputs/)

## 什么是 Signals？

简而言之，信号是代表一个值的响应式基元，它允许我们以受控方式更改该值，并随时间跟踪其变化。

Signals 不是 Angular 独有的新概念。在其他框架中，它们已经存在多年，有时在不同的名称下。

为了更好地理解 signals，让我们从一个尚未使用 signals 的简单示例开始，然后使用 Signals API 重写相同的示例。

首先，假设我们有一个简单的 Angular 组件，带有一个计数器变量：

```ts
@Component(
    selector: "app",
    template: `
<h1>当前计数器的值 {{counter}}</h1>
<button (click)="increment()">增加</button>
`)
export class AppComponent {

    counter: number = 0;

    increment() {
        this.counter++;
    }

}
```

如你所见，这是一个非常简单的组件。

它只是显示一个计数器的值，并且有一个按钮来增加计数器。这个组件使用 Angular 默认的变化检测机制。

这意味着，`{{counter}}`表达式以及页面上的任何其他表达式都会在每次事件之后检查变化，例如点击增加按钮。

如你所想象的，这可能是尝试检测页面上需要更新的内容的一种潜在低效方式。

对于我们的组件来说，这种方法实际上甚至是必要的，因为我们使用了可变的普通 JavaScript 成员变量如 `counter` 来存储我们的状态。

因此，当事件发生时，页面上的**任何东西**都可能影响了那些数据。

此外，点击增加按钮可能很容易触发页面上其他地方的变化，而不仅仅是在这个组件内部。

例如，想象一下我们会调用一个影响页面多个部分的共享服务。

使用默认的变化检测，Angular 无法准确知道页面上发生了什么变化，这就是为什么我们不能对发生了什么做出任何假设，我们需要检查**一切**！

因为我们不能保证哪些可能或可能没有改变，我们需要扫描整个组件树和每个组件上的所有表达式。

使用默认的变化检测，别无他法。

但这就是 Signals 来拯救的地方！

这是相同的简单示例，但这次使用 Signals API 重写：

```ts
@Component(
    selector: "app",
    template: `
<h1>当前计数器的值 {{counter()}}</h1>
<button (click)="increment()">增加</button>
`)
export class AppComponent {

  counter = signal(0);

  constructor() {
    console.log(`计数器的值: ${this.counter()}`)
  }

  increment() {
    console.log(`更新计数器...`)
    this.counter.set(this.counter() + 1);
  }
}
```

如你所见，基于 signal 的组件版本看起来没有太大差异。

主要区别是我们现在使用 `signal()` API 将我们的计数器值包装在一个 signal 中，而不是仅仅使用一个普通的 `counter` JavaScript 成员变量。

这个 signal 代表计数器的值，从零开始。

我们可以看到这个 signal 就像一个我们想要跟踪的值的容器。

## 如何读取一个 signal 的值？

signal 包装了它代表的值，但我们可以随时调用 signal 作为一个函数来获取那个值，不传递任何参数。

注意 signal-based 版本的 AppComponent 的构造函数中的代码：

```ts
constructor() {
    console.log(`计数器的值: ${this.counter()}`)
}
```

如你所见，通过调用 `counter()`，我们得到了包装在 signal 中的值，这种情况下将解析为零（signal 的初始值）。

## 如何修改一个 signal 的值？

有几种不同的方式来改变一个 signal 的值。

在我们的例子中，我们在实现计数器增加函数时使用了 `set()` API：

```ts
increment() {
    console.log(`更新计数器...`);
    this.counter.set(this.counter() + 1);
}
```

我们可以使用 `set()` API 设置任何我们需要的值到 signal 中，只要该值与 signal 的初始值类型相同。

所以在我们计数器 signal 的情况下，我们只能设置数字，因为 signal 的初始值是零。

## update signal API

除了 `set()` API，我们还可以使用 `update()` API。

让我们使用它来重写我们的计数器增加函数：

```ts
increment() {
    console.log(`更新计数器...`);
    this.counter.update(counter => counter + 1);
}
```

如你所见，update API 接受一个函数，该函数接收当前 signal 的值作为输入参数，然后返回 signal 的新值。

增加方法的两个版本都是等效的，同样工作得很好。

## 使用 signals 而不是原始值的主要优势是什么？

到这一点，我们现在可以看到一个 signal 只是一个值的轻量级包装器或容器。

那么使用它的优势是什么呢？

主要优势是我们可以在 signal 值发生变化时得到通知，然后对新的 signal 值做出响应。

这与我们仅使用原始值作为计数器的情况不同。

使用原始值，我们没有办法得知一个值何时发生变化。

但使用 Signals？简单！

这正是首先使用 signals 的全部意义所在。

## `computed()` Signal API

signals 可以基于其他 signals 创建和派生。当一个 signal 更新时，所有依赖它的 signals 都会自动更新。

例如，假设我们希望在我们的组件上有一个派生计数器，它是计数器值乘以 10 的值。

我们可以使用 `computed()` API 基于我们的计数器 signal 创建一个派生 signal：

```ts
@Component(
    selector: "app",
    template: `

  <h3>计数器的值 {{counter()}}</h3>

  <h3>计数器 10 倍: {{derivedCounter()}}</h3>

  <button (click)="increment()">增加</button>

    `)
export class AppComponent {

    counter = signal(0);

    derivedCounter = computed(() => {

        return this.counter() * 10;

    })

    increment() {

        console.log(`更新计数器...`)

        this.counter.set(this.counter() + 1);

    }

}
```

computed API 的工作方式是接收一个或多个源 signals，并创建一个新的 signal。

当源 signal 变化时（在我们的例子中是计数器 signal），derivedCounter 计算 signal 也会立即更新。

因此，当我们点击“增加”按钮时，计数器将具有初始值 1，derivedCounter 将为 10，然后 2 和 20，3 和 30，等等。

## 我们如何订阅一个 signal？

注意，derivedCounter signal _没有_ 以任何显式方式订阅源计数器 signal。

它唯一做的就是在其计算函数内调用源 signal `counter()`。

但这就是我们需要做的一切来将两个 signals 链接在一起！

现在，每当源计数器 signal 有一个新值时，派生 signal 也会自动更新。

这一切听起来有点奇妙，所以让我们来详细解释一下发生了什么：

- 每当我们创建一个计算 signal 时，传递给 `computed()` 的函数至少会被调用一次，以确定派生 signal 的初始值
- Angular 正在跟踪计算函数被调用的情况，并记录下当时它知道的其他被使用的 signals。
- Angular 将注意到，当计算 derivedCounter 的值时，signal 获取函数 `counter()` 被调用了。
- 因此，Angular 现在知道两个 signals 之间存在依赖关系，所以每当计数器 signal 用新值设置时，派生的 `derivedCounter` 也将被更新

如你所见，这样框架就拥有了关于哪些 signals 依赖于其他 signals 的所有信息。

Angular 知道整个 signal 依赖树，知道一个 signal 的值如何影响应用程序的所有其他 signals。

## 我们可以从计算 signal 中读取一个 signal 的值而不创建依赖么？

在某些高级场景中，我们可能希望从另一个计算 signal 中读取一个 signal 的值，但不创建两个 signals 之间的任何依赖。

这种需求应该很少见，但如果你遇到需要这样做的情况，下面是如何做到的方法：

```ts
@Component(
    selector: "app",
    template: `
  <h3>计数器的值 {{counter()}}</h3>
  <h3>计数器 10 倍: {{derivedCounter()}}</h3>
    `)
export class AppComponent {

    counter = signal(0);

    derivedCounter = computed(() => {

        return untracked(this.counter) * 10;

    })

}
```

通过使用 untracked API，我们可以访问计数器 signal 的值，而不在计数器和 derivedCounter signal 之间创建依赖。

注意，这个 untracked 功能是一种高级功能，如果需要的话，应该很少使用。

如果你发现自己经常使用这个功能，那么可能有些不对劲。

## 在创建计算 signals 时要注意哪些主要陷阱？

为了让一切顺利进行，我们需要确保以某种方式计算我们的派生 signals。

记住，Angular 只会认为一个 signal 依赖于另一个，如果它注意到一个 signal 被用来计算另一个信号的值。

这意味着我们需要在计算函数内引入条件逻辑时小心。

这里是事情可能轻易出错的一个例子：

```ts
@Component(
    selector: "app",
    template: `

  <h3>计数器的值 {{counter()}}</h3>

  <h3>派生计数器: {{derivedCounter()}}</h3>

  <button (click)="increment()">增加</button>

  <button (click)="multiplier = 10">
    将倍数设置为 10
  </button>

`)
export class AppComponent {

    counter = signal(0);

    multiplier: number = 0;

    derivedCounter = computed(() => {

        if (this.multiplier < 10) {
            return 0
        }
        else {
            return this.counter() * this.multiplier;
        }
    })

    increment() {

        console.log(`更新计数器...`)

        this.counter.set(this.counter() + 1);

    }

}
```

正如您在这个示例中看到的，`compute`函数中包含了一些条件逻辑。

我们像之前一样调用了`counter()`源信号，但只有在满足特定条件时才这样做。

这个逻辑的目的是动态地通过一些用户操作（比如点击"设置乘数为10"按钮）来设定乘数的值。

但是，这个逻辑并**不**如预期那样工作！

如果你运行它，计数器本身仍会被递增。

但是表达式 `{{derivedCounter()}}` 在点击"设置乘数为10"按钮前后，都会被评估为零。

问题是，在我们计算派生值时，最初并没有调用`counter()`。

调用`counter()`的操作在一个`else`分支内，这个分支最初不会被执行。

因此Angular不知道计数器信号和派生计数器信号之间存在依赖关系。

Angular将它们视为两个完全独立的信号，之间没有任何联系。

这就是为什么当我们更新计数器的值时，派生计数器不会被更新。

这意味着我们在定义计算信号时需要小心一些。

如果一个派生信号依赖于一个源信号，我们需要确保每次调用计算函数时都调用源信号。

否则，两个信号之间的依赖性会被打破。

这并不意味着我们计算函数内部不能有任何条件分支。

例如，以下代码将正确工作：

```ts
@Component(
    selector: "app",
    template: `

  <h3>计数器值 {{counter()}}</h3>

  <h3>派生计数器: {{derivedCounter()}}</h3>

  <button (click)="increment()">递增</button>

  <button (click)="multiplier = 10">
    设置乘数为10
  </button>

`)
export class AppComponent {

    counter = signal(0);

    multiplier: number = 0;

    derivedCounter = computed(() => {
        if (this.counter() == 0) {
            return 0
        }
        else {
            return this.counter() * this.multiplier;
        }
    })

    increment() {

        console.log(`正在更新计数器...`)

        this.counter.set(this.counter() + 1);

    }

}
```

在此版本的代码中，我们的计算函数现在在每次调用时都会调用`this.counter()`。

因此Angular现在可以识别出两个信号之间的依赖关系，代码按预期运行。

这意味着在第一次点击"设置乘数为10"按钮后，乘数将被正确应用。

## 信号依赖关系是否仅基于对计算函数的初始调用来确定？

不，相反，派生信号的依赖关系是根据其最后计算出的值动态识别的。

因此，每次调用计算函数时，都会重新识别计算信号的源信号。

这意味着信号的依赖关系是动态的，它们不是信号生命周期内固定不变的。

再次强调，这意呀着我们在定义派生信号时需要小心处理任何条件逻辑。

## 带有数组和对象值的信号

到目前为止，我们展示的示例中的信号都是基本类型，比如数字。

但是，如果我们定义一个值为数组或对象的信号会发生什么呢？

数组和对象的工作方式与基本类型基本相同，但有几点需要注意。

例如，让我们来看一个信号的值是数组，另一个信号的值是对象的情况：

```ts
@Component(
    selector: "app",
    template: `

  <h3>列表值: {{list()}}</h3>

  <h3>对象标题: {{object().title}}</h3>

`)
export class AppComponent {

    list = signal([
        "Hello",
        "World"
    ]);

    object = signal({
       id: 1,
       title: "Angular入门"
    });

    constructor() {

        this.list().push("Again");

        this.object().title = "覆盖标题";
    }

}
```

关于这些信号，并没有什么特别之处，我们可以像往常一样通过调用信号作为函数来访问它们的值。

但值得注意的关键一点是，与基本值不同，**没有什么能阻止我们通过直接调用push方法或直接修改对象属性来直接修改** 数组的内容。

因此，在这个示例中，屏幕上生成的输出将是：

- 列表的情况为："Hello", "World", "Again"
- 对象标题的情况为："覆盖标题"

当然，这并*不是*使用信号的目的！

相反，我们想通过始终使用`set()`和`update()` API来更新信号的值。

这样，我们就有机会让所有派生信号更新自己，并在页面上反映这些更改。

通过直接访问信号值并直接修改它的值，我们绕过了整个信号系统，并可能导致各种问题。

值得记住的是，我们应该避免直接修改信号值，而应该始终使用Signals API。

值得一提的是，目前Signals API中没有防止这种误用的保护机制，比如预先冻结数组或对象值。

## 覆盖信号相等性检查

关于数组或对象信号的另一件值得一提的事情是，默认的相等性检查是"==="。

这个相等性检查很重要，因为只有当我们试图发出的新值与前一个值不同时，信号才会发出新值。

如果我们试图发出的值被认为与前一个值相同，那么Angular将*不会*发出新的信号值。

这是一种性能优化，可能防止在我们系统地发出相同值的情况下页面不必要地重新渲染。

然而，默认行为是基于"==="引用相等性的，这不允许我们识别功能上相同的数组或对象。

如果我们想这样做，我们需要覆盖信号相等性函数并提供我们的实现。

为了理解这一点，让我们从一个仍然使用默认相等性检查的信号对象的简单示例开始。

然后我们从中创建一个派生信号：

```ts
@Component(
    selector: "app",
    template: `

  <h3>对象标题: {{title()}}</h3>

  <button (click)="updateObject()">更新</button>

`)
export class AppComponent {

    object = signal({
            id: 1,
            title: "Angular入门"
        });

    title = computed(() => {

        console.log(`调用computed()函数...`)

        const course = this.object();

        return course.title;

    })

    updateObject() {

      // 我们通过设置相同的对象
      // 来检验派生的标题信号是否会
      // 重新计算
      this.object.set({
        id: 1,
        title: "Angular入门"
      });

    }

}
```

在这个例子中，如果我们多次点击更新按钮，我们会在控制台上获得多行日志：

```bash
调用computed()函数...
调用computed()函数...
调用computed()函数...
调用computed()函数...
等。
```

这是因为默认的"==="无法检测到我们传递给对象信号的值在功能上等同于当前值。

因此，信号会认为这两个值是不同的，因此任何依赖于对象信号的计算信号也会被计算。

如果我们想避免这种情况，我们需要将我们的相等性函数传递给信号：

```ts
object = signal(
  { id: 1, title: "Angular入门" },
  {
    equal: (a, b) => {
      return a.id === b.id && a.title == b.title;
    },
  }
);
```

有了这个相等性函数，我们现在基于其属性值进行深度比较。

使用这个新的相等性函数，无论我们点击更新按钮多少次，派生信号只会被计算一次：

```bash
调用computed()函数...
```

值得一提的是，在大多数情况下，我们*不应该*为我们的信号提供这种类型的相等性函数。

实际上，默认的相等性检查工作得很好，使用自定义的相等性检查很少会有任何明显的区别。

编写这种类型的自定义相等性检查可能会导致可维护性问题和各种奇怪的bug，比如如果我们给对象添加了一个属性并忘记更新比较函数。

相等性函数在这个指南中只是为了完整性，在您需要它们的罕见情况下提到，但总的来说，对于大多数用例，没有必要使用这个功能。

## 使用`effect()` API检测信号变化

使用`computed` API向我们展示了信号的一个最有趣的属性之一，即我们可以某种方式检测到它们的变化。

毕竟，这正是`computed()` API所做的，对吧？

它检测到源信号已更改，并响应地计算派生信号的值。

但是，如果我们不是为了计算一个依赖信号的新值，而只是为了某种其他原因检测到值发生了变化，该怎么办？

想象一下，您处于需要检测一个信号（或一组信号）的值更改以执行某种副作用的情况，这不会修改其他信号。

这可能是例如：

- 使用日志库记录一些信号的值
- 将信号的值导出到localStorage或cookie
- 在后台默默地将信号的值保存到数据库
- 等等。

所有这些场景都可以使用`effect()` API实现：

```ts
// 每当使用的任何信号的值更改时，效果将被重新运行。
effect(() => {
  // 我们只需在此效果内部
  // 使用源信号
  const currentCount = this.counter();

  const derivedCounter = this.derivedCounter();

  console.log(`当前值: ${currentCount} 
    ${derivedCounter}`);
});
```

只要计数器或派生计数器信号发出新值，此效果就会向控制台打印出日志语句。

请注意，当声明效果时，此效果函数至少会运行一次。

这个初始运行让我们确定效果的初始依赖关系。

就像`computed()` API的情况一样，效果的信号依赖关系是根据效果函数的最后一次调用动态确定的。

## 信号与变更检测之间的关系是什么？

我想你可以看出这个话题的方向了......

信号使我们能够轻松跟踪应用数据的变化。

现在想象一下：假设我们将**所有**我们的应用数据放在信号中！

首先要提到的一点是，由于这样做，应用的代码不会变得更复杂。

Signals API和信号概念非常直观，因此一个到处使用信号的代码库仍将保持相当可读性。

不过，那样的应用代码阅读起来不会像仅仅使用普通的Javascript成员变量作为应用数据那样简单。

那么好处是什么呢？

我们为什么要切换到基于信号的方式来处理我们的数据？

优势在于，有了信号，我们可以轻松地检测应用数据的任何部分何时发生变化，并自动更新任何依赖关系。

现在想象一下，Angular的变更检测被接入到您应用的信号中，Angular知道每个信号在哪些组件和表达式中被使用。

这将使Angular确切地知道应用中哪些数据发生了变化，以及响应新信号值需要更新哪些组件和表达式。

将不再需要检查整个组件树，像默认的变更检测那样！

如果我们向Angular保证所有的应用数据都放在信号中，Angular突然就拥有了进行最优化变更检测和重新渲染所需的所有信息。

Angular将知道如何以最优化的方式更新页面以显示最新数据。

这就是使用信号的主要性能好处！

只需将我们的数据包装在一个信号中，我们就使Angular能够在DOM更新方面为我们提供尽可能最优的性能。

现在，您已经对信号如何工作以及它们为什么有用有了相当好的了解。

现在的问题是，如何正确使用它们？

在讨论如何在应用中使用信号的一些常见模式之前，让我们先快速完成对`effect()` API的介绍。

## 修复错误NG0600：默认情况下，不允许在`computed`或`effect`中更改信号值。

默认情况下，Angular不允许从效果函数内部更改信号值。

因此，例如，我们不能这样做：

```ts
@Component({...})
export class CounterComponent {
  counter = signal(0);

  constructor() {
    effect(() => {
      this.counter.set(1);
    });
  }
}
```

这段代码默认情况下是不被允许的，而且出于非常好的理由。

在这个特定示例的情况下，这甚至会创建一个无限循环并破坏整个应用程序！

## 如何在需要时从内部设置信号的效果

然而，在某些情况下，我们仍然希望能够从效果内部更新其他信号。

为了允许这样做，我们可以将选项`allowSignalWrites`传递给`effect`：

```ts
@Component({...})
export class CounterComponent {
  count = signal(0);

  constructor() {

    effect(() => {
      this.count.set(1);
    },
        {
            allowSignalWrites: true
        });

  }
}
```

然而，这个选项需要非常小心地使用，并且只在特殊情况下使用。

在大多数情况下，您不应该需要这个选项。如果您发现自己在系统地使用这个选项，请重新审视应用的设计，因为可能出了问题。

## 默认的效果清理机制

效果是一个响应信号值变化而被调用的函数。

就像任何函数一样，它可以通过闭包在应用中的其他变量上创建引用。

这意味着，就像任何函数一样，我们需要注意使用效果时不小心创建潜在的内存泄漏。

为了帮助应对这一点，Angular将默认根据使用效果的上下文自动清理效果函数。

因此，例如，如果您在组件内创建效果，当组件被销毁时，Angular会清理效果，对于指令等也是如此。

## 如何手动清理效果

但有时候，出于某些原因，你可能想要手动清理你的效应。

这只在极少数情况下是必要的。

如果你在应用程序中到处手动系统地清理效果，可能有些地方不对劲。

但在需要的情况下，可以通过在首次创建时返回的 `EffectRef` 实例上调用 `destroy` 来手动销毁一个 `effect()`。

在这些情况下，你可能还想通过使用 `manualCleanup` 选项来禁用默认的清理行为：

```ts
@Component({...})
export class CounterComponent {

  count = signal(0);

  constructor() {

    const effectRef = effect(() => {

      console.log(`current value: ${this.count()}`);
    },
        {
            manualCleanup: true
        });

    // 我们可以在任何时间手动销毁效果
    effectRef.destroy();
  }
}
```

`manualCleanup` 标志禁用默认的清理机制，让我们可以完全控制效果何时被销毁。

`effectRef.destroy()` 方法将销毁效果，从任何即将执行的调度中移除它，并清理对效果函数范围外的变量的任何引用，可能防止内存泄露。

## 当效果被销毁时执行清理操作

有时仅仅从内存中移除效果函数对于彻底清理是不够的。

在某些情况下，当效果被销毁时，我们可能想执行某种清理操作，如关闭网络连接或释放一些资源。

为了支持这些用例，我们可以向效果传递一个 `onCleanup` 回调函数：

```ts
@Component({...})
export class CounterComponent {

  count = signal(0);

  constructor() {

    effect((onCleanup) => {

      console.log(`current value: ${this.count()}`);

      onCleanup(() => {
        console.log("在此处执行清理操作");
      });
    });
  }
}
```

这个函数将在清理发生时被调用。

在 `onCleanup` 函数内部，我们可以进行任何我们想要的清理，例如：

- 取消订阅一个observable
- 关闭网络或数据库连接
- 清除setTimeout或setInterval
- 等等。

现在让我们探索更多与信号相关的概念，然后展示在应用程序中使用信号时你可能需要的一些常见模式。

## 只读信号

我们已经在使用只读信号了，即使没有注意到。

这些是不能改变值的信号。它们相当于JavaScript语言中的 `const`。

> 只读信号可以被访问以读取它们的值，但不能通过set或update方法改变。只读信号没有任何内置机制来防止它们的值被深层次地修改。- [Angular repo](https://github.com/angular/angular/blob/main/packages/core/primitives/signals/README.md?ref=blog.angular-university.io)

只读信号可以通过以下方式创建：

- `computed()`
- `signal.asReadonly()`

让我们尝试改变一个派生信号的值，看看会发生什么：

```ts
@Component(
    selector: "app",
    template: `

  <h3>Counter value {{counter()}}</h3>

  <h3>Derived counter: {{derivedCounter()}}</h3>

`)
export class AppComponent {

    counter = signal(0);

    derivedCounter = computed(() => this.counter() * 10)

    constructor() {

        // 这按预期工作
        this.counter.set(5);

        // 这将抛出一个编译错误
        this.derivedCounter.set(50);

    }

}
```

正如我们所看到的，我们可以为counter信号设置新值，这是一个普通的可写信号。

但我们不能在派生的Counter信号上设置值，因为 `set()` 和  
`update()` API都不可用。

这意味着derivedCounter是一个只读信号。

如果需要，你可以很容易地从一个可写信号派生一个只读信号：

```ts
@Component(
    selector: "app",
    template: `

  <h3>Counter value {{counter()}}</h3>

`)
export class AppComponent {

    counter = signal(0);


    constructor() {

        const readOnlyCounter = this.counter.asReadonly();

        // 这将抛出一个编译错误
        readOnlyCounter.set(5);

    }

}
```

注意，反过来是不可能的：你没有API可以从一个只读信号创建一个可写信号。

为了做到这一点，你必须使用只读信号的当前值创建一个新信号。

## 在多个组件中使用信号

现在让我们来谈谈一些你可以在应用程序中使用信号的常见模式。

如果信号仅在组件内部使用，那么最好的解决方案是将其转换成成员变量，正如我们到目前为止所做的那样。

但如果信号数据在应用程序的不同地方需要怎么办？

好吧，没有什么可以阻止我们创建一个信号并在多个组件中使用它。

当信号更改时，使用该信号的所有组件都会被更新。

```ts
// main.ts
import { signal } from "@angular/core";

export const count = signal(0);
```

如你所见，我们的信号在一个单独的文件中，因此我们可以在任何需要它的组件中导入它。

让我们创建两个使用 `count` 信号的组件。

```ts
// app.component.ts
import { Component } from "@angular/core";
import { count } from "./main";

@Component({
  selector: "app",
  template: `
    <div>
      <p>Counter: {{ count() }}</p>
      <button (click)="increment()">从HundredIncrComponent增加</button>
    </div>
  `,
})
export class HundredIncrComponent {
  count = count;

  increment() {
    this.count.update(value => value + 100);
  }
}
```

在这里，我们导入了 `count` 信号并在这个组件中使用它，我们可以用相同的方式在应用程序中的任何其他组件中做同样的事情。

在一些简单的场景中，这可能就是你所需要的全部。

然而，我认为对于大多数应用程序来说，这种方法将不够充分。

这有点像在Javascript中使用全局可变变量。

任何人都可以改变它，或者在信号的情况下，通过调用  
`set()` 来发射一个新值。

我认为，在大多数情况下，这都不是一个好主意，出于全局可变变量通常不是好主意的相同原因。

我们想确保对这个信号的访问某种程度上是封装的并且在控制之下，而不是让任何人都可以不受限制地访问这个信号。

## 如何创建基于信号的响应式数据服务

在多个组件中共享一个可写信号的最简单模式是将信号包装在一个数据服务中，如下所示：

```ts
@Injectable({
  providedIn: "root",
})
export class CounterService {
  // 这是私有的可写信号
  private counterSignal = signal(0);

  // 这是公共的只读信号
  readonly counter = this.counterSignal.asReadonly();

  constructor() {
    // 在这里注入你需要的任何依赖
  }

  // 任何需要修改信号的人
  // 需要以一种控制的方式来做
  incrementCounter() {
    this.counterSignal.update(val => val + 1);
  }
}
```

这种模式非常类似于使用RxJs和BehaviorSubject的可观察数据服务（参见[指南](https://blog.angular-university.io/how-to-build-angular2-apps-using-rxjs-observable-data-services-pitfalls-to-avoid/)），如果你熟悉那种模式的话。

不同之处在于，这个服务更直观易懂，这里没有太多高级概念。

我们可以看到，可写信号counterSignal被服务私有化了。

任何需要信号值的人都可以通过它的公共只读对应物，counter成员变量来获取。

而且，任何需要修改计数器值的人只能通过incrementCounter公共方法以一种受控方式来做。

这样，任何验证或错误处理的业务逻辑都可以添加到方法中，没有人可以绕过它们。

想象一下，如果有一个规则说计数器不能超过100。

使用这种模式，我们可以很容易地在incrementCounter方法中的一个地方实现它，而不是在应用程序的每个地方重复那个逻辑。

我们也可以更好地重构和维护应用程序。

如果我们想找出应用程序中所有正在增加计数器的部分，我们只需使用我们的IDE找到incrementCounter方法的使用即可。

如果我们只是直接给予对信号的直接访问，这种类型的代码分析将不可能。

另外，如果信号需要访问任何依赖才能正常工作，那些可以在构造函数中接收，就像在任何其他服务中一样。

这里运作的一个原则是封装原则。

我们不想让应用程序的任何部分都可以自由地发出信号的新值，我们只想以一种受控的方式允许这样做。

所以总的来说，如果你在多个组件中有一个共享的信号，对于大多数情况，你可能更好地使用这种模式，而不是直接给予对可写信号的访问。

## Signals和OnPush组件

`OnPush` 组件只在它们的输入属性改变，或当通过 `async` 管道订阅的Observables发射新值时更新。

它们不会在输入属性变动时更新。

现在 `OnPush` 组件也与信号集成在一起了。

当在一个组件上使用信号时，Angular将该组件标记为信号的依赖。当信号改变时，组件会被重新渲染。

对于 `OnPush` 组件，当绑定到它的信号更新时，它们也会被重新渲染：

```ts
@Component({
  selector: "counter",
  template: `
    <h1>Counter</h1>
    <p>Count: {{ count() }}</p>
    <button (click)="increment()">增加</button>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CounterComponent {
  count = signal(0);
  increment() {
    this.count.update(value => value + 1);
  }
}
```

在这个例子中，如果我们点击增加按钮，组件将被重新渲染，意味着Signals与 `OnPush` 直接集成。

这意味着我们不再需要注入 `ChangeDetectorRef` 并调用  
`markForCheck`，来更新这种情况下的 `OnPush` 组件。

考虑下面一个不使用信号的例子：

```ts
@Component({
  selector: "app",
  standalone: true,
  template: ` 数字: {{ num }} `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
class ExampleComponent {
  num = 1;
  private cdr = inject(ChangeDetectorRef);
  ngOnInit() {
    setInterval(() => {
      this.num = this.num + 1;
      this.cdr.markForCheck();
    }, 1000);
  }
}
```

正如你所看到的，这一切都更复杂了，为了同等的功能。基于信号的版本要简单得多。

## 我可以在组件/存储/服务之外创建信号吗？

当然！你可以在任何你想要的地方创建信号。没有约束说信号需要在组件、存储或服务内部。

我们之前已经演示了这一点。这就是信号的美妙之处和强大之处。不过在大多数情况下，你可能想要像我们所见的那样将信号封装在服务中。

## Signals与RxJs的比较

Signals不是RxJs的直接替代品，但在我们通常需要RxJs的某些情况下，它们提供了一个更易于使用的替代品。

例如，当需要透明地将数据变化传播到应用程序的多个部分时，signals是RxJS行为主题的一个很好的替代品。

我希望你喜欢这篇文章，为了在新的类似文章发布时得到通知，我邀请你订阅我们的新闻通讯：

## 总结

在这篇指南中，我们探索了Angular Signals API和一种新的反应性原语：信号。

我们已经了解到，通过使用信号来跟踪我们应用程序的所有状态，我们使Angular能够轻松知道视图的哪些部分需要更新。

总之，Signals的**主要目标**是：

- 提供一种新的反应性原语，它更容易理解，使我们能够更轻松地以反应式风格构建应用程序。
- 避免不需要重新渲染的组件的不必要的重新渲染。
- 避免检查数据未变化的组件的不必要检查。

Signals API使用起来非常简单，但要注意一些你可能会遇到的常见陷阱：

- 在定义效果或计算信号时，小心在条件块内读取源信号的值
- 在使用数组或对象信号时，避免直接改变信号值
- 除非必要，不要过度使用提供自己的相等性函数或进行手动效果清理等高级功能。默认行为在大多数情况下应该工作得很好。

我邀请你在你的应用程序中尝试Signals，亲自看看它的魔力！
