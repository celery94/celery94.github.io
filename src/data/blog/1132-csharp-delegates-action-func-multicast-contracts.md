---
pubDatetime: 2026-11-03T08:52:00+08:00
title: "C# 委托：Action、Func 与多播调用契约"
description: "用一个返回 12 而不是 18 的多播例子，核对 Action、Func 的调用形状、方法组兼容规则、异常中断和最后一个返回值的来源，再决定回调 API 该写清哪条约定。"
tags: ["C#", ".NET", "Delegates"]
slug: "csharp-delegates-action-func-multicast-contracts"
ogImage: "../../assets/1132/01-cover.png"
source: "https://www.devleader.ca/2026/11/02/delegates-in-c-action-func-and-multicast-call-contracts"
---

```csharp
Func<int, int> calculate = AddTwo;
calculate += MultiplyByThree;

Console.WriteLine($"Direct result: {calculate(4)}");

static int AddTwo(int value) => value + 2;
static int MultiplyByThree(int value) => value * 3;
```

这段代码在 .NET SDK 10.0.402 上跑出来是 `Direct result: 12`。`AddTwo(4)` 算出 6，`MultiplyByThree(4)` 算出 12。要是多播调用像函数组合那样把上一个结果交给下一个，输出应该是 18；实际两个方法收到的都是调用方传的 4，返回值来自最后一项。

委托容易被当成函数指针，这个印象漏掉了两件事：一个实例可以装着多个方法，实例方法还会把目标对象一起带进来。类型负责兼容，实例负责名单，调用规则只覆盖顺序、返回值和异常怎么传。把这三层分开看，`Action`、`Func`、多播和返回 `Task` 的委托，差别就落在具体位置上了。文中示例的报错和输出都在 .NET SDK 10.0.402 上实测过。原文由 Nick Cosentino 发布在 Dev Leader，下文的多播和兼容规则已对照 C# 规范和 .NET 10 文档核对。

## 委托类型和委托实例是两件事

`delegate void Notify(string message);` 声明的是一个类型。写 `Notify notify = handler;` 才创建实例。类型决定哪些方法能赋进来，实例决定这一次调用会经过谁。

类型按名称区分。下面两个声明参数和返回值完全一样，仍然不能互相赋值：

```csharp
delegate void Notify(string message);
delegate void OtherNotify(string message);

OtherNotify other = message => Console.WriteLine(message);
Notify notify = other; // CS0029
```

编译器报的是 `CS0029: Cannot implicitly convert type 'OtherNotify' to 'Notify'`。规范把这叫名称等价：签名相同不会让两个类型通用。一个方法可以分别转成两种委托类型，那也是两次转换，说明不了类型之间可以互换。

这条规则在 API 边界上有用。`Action<string>` 和 `Notify` 的形状一样，但看到 `Notify` 的人会先问「通知谁、通知在什么时候发生」，看到 `Action<string>` 只会问「这个字符串是什么」。名字承担了一部分文档，泛型签名补不上。

## Action 和 Func 只描述调用形状

`Action<T>` 描述一个入参、无返回值的调用，`Func<T, TResult>` 描述一个入参、有返回值的调用；两者的其他重载只差参数个数，最多 16 个。日常回调多数直接用它们就够了。

它们都是委托类型，不是执行引擎：换用 `Action` 不会把调用挪到别的线程，也不会加超时或重试；被调方法同步抛出的异常，照样从调用点冒出来。

没有返回值不代表没有工作。`Action<Order>` 可以写库、发消息、改状态，签名只说了调用方不关心结果。有返回值也不代表只有一种解释：`Func<Order, bool>` 可能是校验，可能是「要不要拦截」，也可能只是查表命中。这层语义得由方法名和文档补。

需要 `ref` 或 `out` 参数时，`Action` 和 `Func` 表达不了，得自己声明类型：

```csharp
public delegate bool TryRead<T>(string text, out T value);
```

把领域语义放进类型名也有价值。`Func<Payment, bool>` 在代码里到处都是时，没人说得清 false 是拒绝还是「不用处理」。`PaymentPolicy` 这个名字会逼实现者先回答 false 的含义，再写方法体。

## 参数兼容看调用，不看方法名

把方法组转成委托时，编译器检查参数和返回值的兼容性，方法名和参数名都不参与判断。参数个数、`ref`/`out` 修饰符必须对上，引用类型之间允许的隐式转换可以放宽参数类型。

```csharp
Action<string> print = Handle;
print("text");

static void Handle(object value) => Console.WriteLine(value);
```

这段能编译，因为传进来的 `string` 本来就可以当 `object` 用。换成 `Action<int>` 就通不过：`int` 到 `object` 是装箱，不属于方法组转换接受的引用转换，编译器报 `CS0123`。

可选参数不会在转换时消失。下面这个方法的第二个参数有默认值，直接调用可以只写一个实参，转成 `Action<int>` 仍然不行：

```csharp
Action<int> act = WithDefault; // CS0123

static void WithDefault(int first, int second = 0)
{
    Console.WriteLine($"{first} {second}");
}
```

报错是 `No overload for 'WithDefault' matches delegate 'Action<int>'`。参数个数是签名的一部分，默认值只影响直接调用时的实参检查。要让委托带上固定实参，包一层 lambda 更直接。

还有一种情况容易看错：已经存在的委托值可以按变体规则赋值，但赋值成功不等于能合并。

```csharp
Action<object> acceptObject = value => Console.WriteLine(value);
Action<string> acceptString = acceptObject;

acceptString("text");
acceptString += text => Console.WriteLine(text);
```

`Action<string>` 那一行能通过，是因为 `Action<in T>` 支持逆变：接受 `object` 的委托可以当成接受 `string` 的委托使用。`acceptString("text")` 正常打印，接着 `+=` 抛出 `ArgumentException`，消息是 `Delegates must be of the same type.`。`acceptString` 的静态类型是 `Action<string>`，运行时对象还是 `Action<object>`，合并检查的是运行时类型。

## 多播只延长调用列表

`+=` 最终调用 `Delegate.Combine`，把两个非空委托的调用列表拼起来，生成一个新实例。原来的实例不变，这也是发布方可以先取局部副本、再触发一次通知的原因。

普通调用按列表顺序同步执行，每个方法收到同一组实参。有 `ref` 参数时，后面的方法能看到前面改过的值；没有 `ref` 时，各自拿到的都是调用方传进去的那份。

返回值只来自最后一项。正常走到最后一项，整体调用就返回那一项的结果；前面各项的返回值没有被谁收集，也没有聚合规则。

`GetInvocationList()` 返回的是数组，它不执行方法，也不汇总结果。想把每个方法的结果都拿到，只能自己遍历、自己调用、自己决定冲突怎么办。沿用开头的 `calculate`，把每个方法的返回值收进列表：

```csharp
var values = new List<int>();
foreach (Func<int, int> operation in calculate.GetInvocationList())
{
    values.Add(operation(4));
}

Console.WriteLine(string.Join(", ", values)); // 6, 12
```

两个结果都来自 4，前一个的输出没有流进后一个。

所以，多播不适合承载「必须有一个答案」的决策。三个校验器里有一个返回 false，整体该返回什么？第一个成功就停，还是全部跑完再合并？签名不回答这些问题，代码里必须写。

## 一个未捕获的异常就停住后面的调用

多播调用不是隔离执行。某一项抛出未捕获的异常，异常沿委托的调用者向上传播，后面的方法不会执行。

```csharp
var trace = new List<string>();
Action inspect = () => trace.Add("first");
inspect += Fail;
inspect += () => trace.Add("third");

try
{
    inspect();
}
catch (InvalidOperationException exception)
{
    trace.Add(exception.Message);
}

Console.WriteLine(string.Join(", ", trace));

static void Fail()
{
    throw new InvalidOperationException("second failed");
}
```

输出是 `first, second failed`，`third` 没有出现。`catch` 在调用方这一侧，拦得住异常，改不了已经跳过的第三项。

所以「注册了处理器」和「一定会收到通知」是两件事。观察型通知希望一个订阅者出错不影响其他订阅者时，发布方要自己遍历 `GetInvocationList()`，对每一项决定捕获、记录还是中断，再把这个策略写进文档。语言不提供这个语义，策略得自己加。

## 实例方法把目标对象一起带进来

静态方法的委托只记方法，实例方法的委托还记着目标对象。只要委托可达，目标对象就可达。短命对象把处理器注册到长命对象上又不退订，目标就被留住了。

lambda 的捕获让这件事更难看出来。`Delegate.Target` 指向编译器生成的闭包对象，不是开发者心里的那个订阅者：

```csharp
var report = new ReportService();
Action handler = () => report.Generate();
Console.WriteLine(handler.Target?.GetType().Name);
```

打印出来是编译器给闭包生成的类型名，在输出里找不到 `ReportService`。所以排查内存问题时，看 `Target` 的类型只能定位到「谁被捕获了」，定位不到「业务上谁在订阅」。

退订时要拿回原来那个委托。命名方法可以按目标加方法匹配，写成 lambda 的处理器必须自己存下委托变量。每次重新写一遍相同的 lambda 源码，不能保证减掉的是同一条注册——无捕获的 lambda 可能被缓存，有捕获的每次都是新实例，结果取决于编译器实现，不该依赖。

## Func<Task> 也只交回最后一个任务

`Func<Task>` 组合起来照样遵守多播的返回规则：调用走到最后一项，返回它的 `Task`，前面几项的 `Task` 没有人持有。

```csharp
Func<Task> both = FirstAsync;
both += SecondAsync;
await both(); // 只等到 SecondAsync 的任务
```

要等全部完成，先遍历调用列表拿到每个 `Task`，再决定 `Task.WhenAll` 还是逐个 await，以及一个失败要不要取消其余的。这些是调用方新增的策略，组合委托本身不提供。

同步抛异常和异步失败落在不同位置。非 `async` 的方法返回 `Task` 时，可能在返回 `Task` 之前就抛异常，这时后面的方法同样不会执行；`async` 方法把失败放进返回的 `Task`，不 await 就看不到。

`async void` 更彻底：调用方没有 `Task` 可等，异常交给同步上下文，通常没人处理。事件签名固定为 `void` 时很难绕开这个形状，很多异步事件最后改成显式分发。

## 回调参数写进 API 之前

把一个委托参数放进公开 API 之前，先回答两个问题：这个调用允许失败几次，失败后还要不要继续；返回值是给一个决策者看，还是让一组观察者各自处理。

第一个问题决定直接调用还是遍历调用列表，第二个决定用 `Func<T, TResult>` 还是 `Action<T>`。两个都答不上来，多半是还不需要多播，一个接口方法或者构造函数参数会更清楚。

手上已经有 `+=` 的代码，可以拿两个简单方法试一次：传入 4，看返回 12 还是 18。如果代码里跑出 12，而调用方一直按 18 在理解，那段逻辑里就藏着一个没人写下来的假设。

## 参考

- [Delegates in C#: Action, Func, and Multicast Call Contracts](https://www.devleader.ca/2026/11/02/delegates-in-c-action-func-and-multicast-call-contracts)
- [Delegates — C# language specification](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/language-specification/delegates)
- [Method group conversions — C# language specification](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/language-specification/conversions#method-group-conversions)
- [Delegate.Combine method](https://learn.microsoft.com/en-us/dotnet/api/system.delegate.combine?view=net-10.0)
- [Action<T> delegate](https://learn.microsoft.com/en-us/dotnet/api/system.action-1?view=net-10.0)
- [Func<T, TResult> delegate](https://learn.microsoft.com/en-us/dotnet/api/system.func-2?view=net-10.0)
- [Variance in delegates](https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/concepts/covariance-contravariance/variance-in-delegates)
- [Async return types (C#)](https://learn.microsoft.com/en-us/dotnet/csharp/asynchronous-programming/async-return-types)
