---
pubDatetime: 2026-11-02T11:55:00+08:00
title: "C# 事件与委托：订阅边界、失败边界与生命周期"
description: "事件不是委托的别名。从类型与成员的区别出发，看清订阅权限、多播调用的失败点、async void 处理器和退订各自能保证什么，再决定通知 API 该把哪条边界写进文档。"
tags: ["C#", ".NET", "Events"]
slug: "csharp-events-delegates-subscription-boundaries"
ogImage: "../../assets/1131/01-cover.png"
source: "https://www.devleader.ca/2026/10/30/events-and-delegates-in-c-contracts-subscriptions-and-notification"
---

```csharp
public event EventHandler<RevisionRecordedArgs>? Recorded;

public void Record(string documentId)
{
    _revision++;
    Recorded?.Invoke(this, new RevisionRecordedArgs(documentId, _revision));
}
```

`Record` 返回之后，调用方到底有资格断定什么？某个处理器抛异常，异常会从这里冒出去，版本号却已经加过；处理器写成 `async void`，方法返回时它可能还在跑；订阅者忘了退订，只要发布者还活着，它就留在通知名单上。三个问题都不由 `event` 关键字回答。

把这段代码里的东西拆成四个角色，边界就清楚了：委托类型规定「什么样的调用算兼容」，事件成员规定「订阅从哪加、从哪减」，声明事件的类型持有触发权并决定通知落在操作的哪个时刻、失败如何传播，订阅者负责在需要的时间范围内保持注册。四者里只有委托和事件由语言强制；失败怎么算、完成怎么算、订阅何时结束，都要在代码里另外写清楚，不写，调用方就只能靠读实现来猜。

下面的示例参考 Nick Cosentino 在 Dev Leader 的文章（2026 年 10 月 30 日发布），多播调用的顺序、返回值和异常规则按 C# 语言规范核对，`async void` 的行为按 .NET 10 的异步返回类型文档核对。示例代码没有在本地编译执行，预期输出是按规范推出来的。

## 委托是调用契约，事件是订阅成员

`delegate void Notify(string message);` 声明了一个类型。实例可以指向静态方法、实例方法（连目标对象一起），也可以指向另一个委托组合出来的调用列表。规范把委托类型和委托实例分开写：类型管参数和返回值的兼容规则，实例管这一组具体方法。

`event` 声明的是成员。它的类型必须是一个委托类型，订阅由编译器或你写的 `add`/`remove` 访问器维护。在声明它的类型之外，代码只能 `+=` 和 `-=`：读不到底层的委托，不能整体替换，也不能调用它。发布者可以公开一个 `Record` 或 `Raise` 方法让外部间接触发通知，那时调用方用的是这个方法的契约，事件边界没有被绕过。

换成 `public EventHandler<RevisionRecordedArgs>? Recorded { get; set; }` 会松掉这层限制。setter 公开后，后来的订阅者能把之前的回调整体换掉；getter 公开后，谁拿到委托都能直接触发。属性写法在传递回调集合时是合理的，但它不提供事件的那些限制，相似语法不构成相同封装。

| 概念       | 定义了什么                   | 不保证什么                 |
| ---------- | ---------------------------- | -------------------------- |
| 委托类型   | 参数与返回值的兼容规则       | 某个具体方法已经注册       |
| 委托实例   | 一组可调用的方法与目标对象   | 投递可靠、重试、跨进程送达 |
| 事件成员   | 订阅入口和 add/remove 访问器 | 每个订阅者都成功执行       |
| 发布者方法 | 通知何时发生、按什么顺序发生 | 处理器失败后自动回滚       |

解耦也有它的边界。订阅者依然需要发布者实例或另一个订阅入口；双方还要对参数的含义达成一致。事件降低的是类型依赖，通信本身还得有人负责。

## `Record` 返回时，调用方能断定什么

完整例子把通知放在一次同步操作之后：先记录修订号，再通知。

```csharp
#nullable enable
using System;

var revisions = new RevisionLog();
EventHandler<RevisionRecordedArgs> handler = ShowRevision;

revisions.Recorded += handler;
revisions.Record("guide");
revisions.Recorded -= handler;
revisions.Record("guide");

static void ShowRevision(object? sender, RevisionRecordedArgs args)
{
    Console.WriteLine($"{args.DocumentId}: revision {args.Revision}");
}

public sealed class RevisionRecordedArgs : EventArgs
{
    public RevisionRecordedArgs(string documentId, int revision)
    {
        DocumentId = documentId;
        Revision = revision;
    }

    public string DocumentId { get; }
    public int Revision { get; }
}

public sealed class RevisionLog
{
    private int _revision;

    public event EventHandler<RevisionRecordedArgs>? Recorded;

    public void Record(string documentId)
    {
        if (string.IsNullOrWhiteSpace(documentId))
        {
            throw new ArgumentException("文档标识不能为空。", nameof(documentId));
        }

        _revision++;
        var args = new RevisionRecordedArgs(documentId, _revision);
        var handlers = Recorded;
        handlers?.Invoke(this, args);
    }
}
```

两次调用都会让 `_revision` 加一，第二次没有订阅者，计数照样前进。这是示例定下的契约，不是事件的通用要求：有些 API 在没有订阅者时选择不改变状态，那是它自己的规则，应当写在方法里，而不是让调用方从事件名猜。

`var handlers = Recorded;` 把这次触发要用的列表固定下来。委托实例创建后调用列表不再变化，`+=` 和 `-=` 产生的是新实例，所以这次调用用的是读到的那份。`Recorded?.Invoke(...)` 的求值同样只读一次字段；需要多次使用同一份列表（比如先判空、再遍历）时，局部变量才真正必要。

局部副本固定的只有列表，不包含发布者状态、订阅者状态，也不包含参数对象内部更深的引用。`DocumentId` 和 `Revision` 是只读属性，处理器换不掉这两个值；如果参数里装的是集合或领域对象，处理器照样可以改里面的内容。

失败边界也在这里。某个处理器抛出没被捕获的异常，异常会从 `Record` 冒出去，而 `_revision` 已经加过，没有回滚。事件不会为发布者和订阅者建立事务；要隔离观察者的失败，只能在发布者里写。

## 字段式事件省掉了样板，也藏起了策略

`public event EventHandler<RevisionRecordedArgs>? Recorded;` 是字段式声明。编译器生成委托存储和 add/remove 访问器，在声明类型内部可以把它当字段用，包括取局部副本。

自定义访问器是另一回事。`add` 和 `remove` 各是一个语句块，新委托放在隐式参数 `value` 里，可以转发给别的组件，也可以换成自己的存储。显式实现接口的事件在类里不能直接用事件名触发，那层限制由访问器决定。

读陌生 API 时，`+=` 只证明 add 访问器被调用了。它不证明实现会去重、会原样保存这个委托、用强引用持有订阅者，或者永不抛异常。这些属于访问器的实现和它承诺的契约。

线程安全的范围也常被放大。编译器生成的字段式访问器用原子交换更新存储，并发注册和退订不会丢更新；但这个保证只到访问器为止。处理器代码、参数对象里的可变状态、并发触发、自定义访问器的实现，都要各自处理。官方文档在讲自定义访问器时也建议先加锁再改列表。

订阅者多并不构成写自定义访问器的理由。需要去重、弱引用、把订阅转发给别的组件、或者必须限制回调数量时，才有具体契约要实现；多一层控制就多一层要维护的存储、身份和并发策略。

## 多播调用按注册顺序执行，遇到异常就停

组合委托会把调用列表拼接起来。普通多播调用按列表顺序同步执行，每个方法收到同一组参数；如果其中有引用参数，后面的方法能看到前面方法改过的值。

```csharp
using System;
using System.Collections.Generic;

var observations = new List<string>();
Action<string> notify = message => observations.Add($"first: {message}");
notify += _ => throw new InvalidOperationException("第二个处理器失败。");
notify += message => observations.Add($"third: {message}");

try
{
    notify("revision recorded");
}
catch (InvalidOperationException exception)
{
    Console.WriteLine(exception.Message);
}

Console.WriteLine(string.Join(" | ", observations));
```

按规范，第一个处理器记录一条，第二个抛异常，第三个不会被调用，`observations` 里只有 `first: revision recorded`。`catch` 属于调用这个委托的代码，跟事件声明无关。

有返回值的时候，规则同样具体：正常走到最后一项，整体调用给出最后一项的返回值，前面各项的返回值不会被收集。`GetInvocationList()` 返回调用列表的数组，它不执行任何方法，也不替调用方汇总结果。想把每个处理器的结果都拿到，就得自己遍历、自己调用、自己决定冲突怎么处理。

这两条规则合起来，解释了为什么一个事件很难承载「必须有一个答案」的决策。

## 想让每个处理器都跑完，需要自己遍历

观察型的通知通常希望一个订阅者出错不影响其他订阅者。语言不提供这个语义，但可以把 `Record` 里那行调用换成一个自己写的私有方法：

```csharp
private void RaiseRecorded(RevisionRecordedArgs args)
{
    if (Recorded is not EventHandler<RevisionRecordedArgs> handlers)
    {
        return;
    }

    List<Exception>? failures = null;
    foreach (EventHandler<RevisionRecordedArgs> handler in handlers.GetInvocationList())
    {
        try
        {
            handler(this, args);
        }
        catch (Exception exception)
        {
            failures ??= new List<Exception>();
            failures.Add(exception);
        }
    }

    if (failures is not null)
    {
        throw new AggregateException("有订阅者处理修订通知时失败。", failures);
    }
}
```

这段代码换了契约：所有处理器都会执行，失败合并成一个 `AggregateException`，调用仍然是同步的，顺序仍然是注册顺序，但第一个失败不再中止后面的通知。这是新的行为，要写进方法的文档或注释；否则调用方会按普通事件的规则去推断，结果对不上。

还有另一种选择：不抛异常，把失败交给日志或遥测，让 `Record` 正常返回。哪一个对，取决于「观察者失败要不要让操作失败」。这个问题没有默认答案，只能由接口的使用者来定。

## `Closing` 不给否决权，`Closed` 也无法撤回

通知描述一件已经发生的事或一个正在发生的状态转换，决策问的是接下来该做什么。两者都能用委托表达，所有权却不同：一条修订记录允许零个观察者，一个权限判断通常要求恰好一个权威给出答案。

事件名不改变这层语义。叫 `Closing` 不会自动带来取消能力，发布者必须读一个决策值再决定是否继续；叫 `Closed` 之后发出的通知，也不该被解释成可以撤销已经完成的转换。命名帮助阅读，实际边界由实现和文档确定。

如果决策归一个协作者，返回值的委托或接口方法更直接。事件保留的是订阅模型，它不负责指出谁是决策者。这个区分只是设计选择，不构成「所有事件都该换成回调」的结论。

用可变参数把决定带回发布者也是可行写法，但要先回答两个问题：没人订阅时默认结论是什么，多个订阅者意见冲突时听谁的。答不上来，说明这里需要的是一个接口，而不是一组观察者。

## `async void` 处理器不会让调用方等到完成

`EventHandler` 的约定是返回 `void`。给兼容这个签名的处理器加上 `async`，得到的是 `async void`：调用方不能 `await` 它，它抛出的异常也不会作为 `Record` 调用里的异常被捕获，而是交给当前的同步上下文；没有同步上下文时，异常在 ThreadPool 上抛出，通常直接终止进程。

事件声明的委托类型可以换成返回 `Task` 的形状，但多播调用不会因此变成「等待全部完成」。直接调用组合委托，只返回最后一个处理器的 `Task`，前面几个各自在跑，没有人等它们。要等每一个，仍然得遍历：

```csharp
public event Func<object?, RevisionRecordedArgs, Task>? RecordedAsync;

public async Task RecordAsync(string documentId)
{
    _revision++;
    var args = new RevisionRecordedArgs(documentId, _revision);

    if (RecordedAsync is not Func<object?, RevisionRecordedArgs, Task> handlers)
    {
        return;
    }

    foreach (Func<object?, RevisionRecordedArgs, Task> handler in handlers.GetInvocationList())
    {
        await handler(this, args).ConfigureAwait(false);
    }
}
```

这里逐个等待，顺序和同步版本一致，第一个失败仍然会中止后面的处理器。要让失败互不影响，就像上一节那样给每个调用套一层 `try`。无论哪种写法，事件的委托类型和触发方法的返回类型都变了，框架事件常见的 `void` 约定不再适用。

退订也不会取消已经派发出去的工作。取消是协作式的，需要 `CancellationToken` 和一个明确的所有者。撤掉订阅只影响之后的通知，正在跑的处理器该跑完还是跑完。所以「操作完成」这四个字，在异步通知里必须先定义：是状态改完了，还是所有观察者都处理完了。

## 退订改变的是下一次通知的名单

普通事件用委托持有实例处理器的目标对象。发布者可达，订阅者就被留住；这个订阅只在视图或会话存活期间有用时，就需要一个对应的结束点，语言不会替你判断订阅者已经不需要通知了。

命名方法可以用同一个目标加同一个方法减掉。匿名处理器必须保存到委托变量里才能可靠地退订。重复写一段看起来一样的 lambda 源码不可靠：无捕获的 lambda，编译器可能缓存同一个委托实例，让 `-=` 碰巧生效；有捕获时，每次求值都是新实例。依赖这种行为等于依赖编译器实现。

可达性的说法也要带上限定。可达的发布者会留住订阅者；发布者和订阅者互相引用、但整体已经不可达时，不会仅仅因为事件就永久留在内存里。事件声明本身不决定回收时机。

退订是对未来名单的修改，不是停机屏障。发布者可能已经取到了快照，处理器可能已经开始执行。需要「停止并排空」时，那是一个额外的生命周期契约：谁发起停止、在途的通知怎么处理、停止完成后怎么通知调用方，都得单独实现。

## 写通知 API 前要定的五件事

下面这些问题，答案应该落在代码或文档里，而不是留给读者从事件名推断：

- 谁有权限触发通知：事件声明在哪个类型里，是否另外公开了一个 `Raise` 方法。
- 通知发生在状态改变之前还是之后：`Record` 里 `_revision++` 和 `Invoke` 的先后。
- 一个处理器失败要不要阻止其余处理器：直接调用，还是遍历 `GetInvocationList()` 并逐个隔离。
- 操作返回时异步工作完成了吗：`void` 处理器，还是返回 `Task` 并逐个等待。
- 订阅在什么时刻必须结束：视图、会话或连接的生命周期，以及有没有停止并清空的操作。

下一个类要加 `event` 时，先把这五句话写出来。第四条答不上来，说明「完成」还没定义，先用一个返回 `Task` 的方法会更清楚；第一条答不上来，多半是想要一个回调列表，属性或者构造函数参数就够了。事件本身不复杂，复杂的是它周围那些没人写下来的约定。

## 参考

- [Events and Delegates in C#: Contracts, Subscriptions, and Notification](https://www.devleader.ca/2026/10/30/events-and-delegates-in-c-contracts-subscriptions-and-notification)
- [Delegates — C# language specification](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/language-specification/delegates)
- [Classes — C# language specification（15.8 Events）](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/language-specification/classes#158-events)
- [Async return types (C#)](https://learn.microsoft.com/en-us/dotnet/csharp/asynchronous-programming/async-return-types)
- [How to: implement custom event accessors](https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/events/how-to-implement-custom-event-accessors)
- [event keyword (C# reference)](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/keywords/event)
