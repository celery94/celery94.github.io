---
pubDatetime: 2026-03-23T11:00:00+08:00
title: ".NET 进程内同步 API 全览：从 lock 到 Barrier"
description: "系统梳理 .NET 进程内线程同步的全套 API——lock 语句、Lock/Monitor、Mutex、Semaphore、ReaderWriterLock、事件类、CountdownEvent、SpinLock、Barrier 等，附分类对照表与实用准则。"
tags: [".NET", "C#", "Threading", "Concurrency", "Synchronization"]
slug: "dotnet-synchronisation-apis-in-process"
ogImage: "../../assets/658/01-cover.png"
source: "https://developmentwithadot.blogspot.com/2026/02/net-synchronisation-apis-part-1-in.html"
---

![.NET 进程内同步 API](../../assets/658/01-cover.png)

多线程编程里，同步是绕不过去的话题。用不好，轻则数据错乱，重则程序卡死。这篇文章来自 Ricardo Peres 的系列博客 *Development with a Dot*，系统整理了 .NET 进程内（in-process）所有主要的同步原语，并给出分类对照和实用建议。

这是该系列第一篇，后续还会覆盖同机器上的跨进程同步和分布式同步。

---

## 为什么需要同步

多线程共享资源时，如果不加控制，会出现：

- **竞态条件**：两个线程同时修改同一份数据
- **数据损坏**：一个线程在另一个不知情的情况下改了共享数据
- **死锁**：两个或多个线程互相等待对方释放资源（同步机制本身也可能制造这个问题）

---

## 各类 API 详解

### lock 语句

`lock` 是 C# 语言内置的关键字，是 `Monitor` 或 `Lock` 类的语法糖，确保同一时刻只有一个线程执行代码块。即使块内抛出异常，锁也会被正确释放。

```csharp
object _lock = new object();

lock (_lock)
{
    // 临界区
}
```

注意：不要对 `this`、静态字段或类型本身加锁，这是常见的误用。

### Lock 类（.NET 8+）

从 .NET 8 起，如果 `lock` 的参数类型是 `Lock`，编译器会改用 `Lock.EnterScope()` 实现，返回一个 `Lock.Scope`（`ref struct`，`using` 结束时自动释放）：

```csharp
var lockObj = new Lock();

using (lockObj.EnterScope())
{
    // 临界区
}
```

`Lock.Scope` 不实现 `IDisposable`（因为是 `ref struct`），但 `using` 语句仍会隐式调用它的 `Dispose` 方法。

### Monitor

`Monitor` 是 `lock` 语句在 .NET 9 之前的底层实现，提供编程式访问：

```csharp
object _lock = new object();

try
{
    Monitor.Enter(_lock);
    // 临界区
}
finally
{
    Monitor.Exit(_lock);
}
```

`Monitor` 额外提供三个协作方法：

- `Wait`：释放锁，然后等待重新获取
- `Pulse` / `PulseAll`：通知第一个/所有等待锁的线程状态已变化

还有 `TryEnter`（.NET 9 新增），与 `Enter` 的区别在于：前者无法获得锁时立即返回（可带超时），后者会一直阻塞。

除非需要 `Pulse`/`Wait` 这类高级协作场景，否则直接用 `lock` 就够了。

### [MethodImpl] 特性

把 `[MethodImpl(MethodImplOptions.Synchronized)]` 加在方法上，效果等同于把整个方法体包在 `lock` 里：实例方法锁 `this`，静态方法锁类型本身。

```csharp
[MethodImpl(MethodImplOptions.Synchronized)]
public void SynchronizedMethod()
{
    // 临界区
}
```

这违反了"不要锁 `this`"的准则，但作为快速方案有其便利之处。

### Mutex

`Mutex` 提供互斥访问，确保同一时刻只有一个线程进入临界区。它工作在内核层，支持锁所有权（只有持锁线程才能释放），也是本系列后续跨进程同步的基础。

```csharp
using var mutex = new Mutex(initiallyOwned: false);

mutex.WaitOne();          // 获取锁（可带超时）
// 临界区
mutex.ReleaseMutex();     // 释放锁
```

`Mutex` 只提供同步方法，内核调用开销相对较大。

### Semaphore 与 SemaphoreSlim

`Semaphore` 允许设定最大并发访问数，是经典的计数信号量，工作在内核层：

```csharp
using var semaphore = new Semaphore(initialCount: 1, maximumCount: 3);

semaphore.WaitOne();
// 临界区
semaphore.Release(releaseCount: 1);
```

`SemaphoreSlim` 是用户级（纯托管代码）的轻量版本，主要优势是**支持异步等待**：

```csharp
using var semaphore = new SemaphoreSlim(initialCount: 1, maximumCount: 3);

await semaphore.WaitAsync();
// 临界区
semaphore.Release(releaseCount: 1);
```

与 `Mutex` 不同，`Semaphore` 没有锁所有权概念，任何线程都可以调用 `Release`。

### ReaderWriterLock 与 ReaderWriterLockSlim

这两个类支持**读写分离**：多个读者可并发持有读锁，但写锁是独占的。适合读多写少的场景。

`ReaderWriterLock`（内核级）：

```csharp
using var rwLock = new ReaderWriterLock();

// 读者
rwLock.AcquireReaderLock(Timeout.Infinite);
// ...读操作
rwLock.ReleaseReaderLock();

// 写者
rwLock.AcquireWriterLock(Timeout.Infinite);
// ...写操作
rwLock.ReleaseWriterLock();
```

还支持从读锁升级为写锁（`UpgradeToWriterLock`）然后降级（`DowngradeFromWriterLock`）。

`ReaderWriterLockSlim`（用户级）是推荐版本，提供 `TryEnter*` 系列方法，支持可升级读锁（`EnterUpgradeableReadLock`），并且支持异步场景。

### 事件类

事件类（`AutoResetEvent`、`ManualResetEvent`）是内核级对象，用于线程间信号通知：

- **`AutoResetEvent`**：收到信号后，释放一个等待线程，然后**自动重置**为未触发
- **`ManualResetEvent`**：收到信号后保持触发状态，直到手动调用 `Reset()`

```csharp
using var evt = new AutoResetEvent(initialState: false);

// 线程 A：等待信号
evt.WaitOne();

// 线程 B：发出信号
evt.Set();
```

`ManualResetEventSlim` 是用户级轻量版，行为与 `ManualResetEvent` 相同，但不支持跨进程。

也可以通过基类 `EventWaitHandle` 加 `EventResetMode` 标志来灵活选择模式。

### CountdownEvent

`CountdownEvent` 在被信号通知指定次数后，才释放所有等待线程：

```csharp
var countdown = new CountdownEvent(10);

// 等待方
countdown.Wait();

// 信号方（调用 10 次后等待方才会继续）
countdown.Signal();
```

没有锁所有权，任何线程都可以调用 `Signal`。

### SpinLock 与 SpinWait

这两个是用户级自旋原语，在锁竞争极低、持锁时间极短的场景下有性能优势，因为它们避免了线程上下文切换。

`SpinLock` 适合保护短小的临界区：

```csharp
var spinLock = new SpinLock();
var lockTaken = false;

try
{
    spinLock.Enter(ref lockTaken);
    // 临界区
}
finally
{
    if (lockTaken) spinLock.Exit();
}
```

`SpinWait` 适合等待某个条件成立：

```csharp
SpinWait.SpinUntil(() => someCondition, TimeSpan.FromSeconds(1));
```

### Barrier

`Barrier` 用于多个线程（参与者）在某个阶段完成后集体同步，再一起推进下一阶段：

```csharp
using var barrier = new Barrier(participantCount: 3, postPhaseAction: b =>
{
    // 每个阶段完成后执行的整合操作
});

Action participant = () =>
{
    // 做本阶段工作
    barrier.SignalAndWait(); // 等所有参与者到达后一起继续
};

Parallel.Invoke(participant, participant, participant);
```

每次所有参与者都调用 `SignalAndWait()` 后，屏障会递增 `CurrentPhaseNumber` 并重置，可无限复用。也可以动态增减参与者。

---

## 基类：WaitHandle 与 EventWaitHandle

`WaitHandle` 是 `AutoResetEvent`、`ManualResetEvent`、`Mutex`、`Semaphore` 的公共抽象基类，提供：

- `WaitOne`：等待单个对象
- `WaitAll`：等待所有对象
- `WaitAny`：等待任意一个，返回第一个就绪的索引

```csharp
Mutex[] mutexes = { ... };

WaitHandle.WaitAll(mutexes);
int first = WaitHandle.WaitAny(mutexes);
```

`EventWaitHandle` 是 `AutoResetEvent` 和 `ManualResetEvent` 的直接基类，定义了 `Set`、`Reset` 等方法。

---

## 死锁

死锁的常见原因：

- **循环等待**：线程 A 等 B 释放资源，线程 B 等 A 释放资源
- **加锁顺序不一致**：多个线程以不同顺序加同一批锁
- **锁使用不当**：忘记释放、重复获取、持锁时间过长
- **异步代码中使用同步阻塞调用**：如在 `async` 方法中调用 `.Wait()` 或 `.Result`

---

## 分类汇总

| 维度 | 单种模式 | 读写分离 |
|------|----------|----------|
| 访问模式 | lock/Lock/Monitor/Mutex/Semaphore/SemaphoreSlim/SpinLock/SpinWait/Event 类/Barrier | ReaderWriterLock/ReaderWriterLockSlim |

| 维度 | 同步 | 异步 |
|------|------|------|
| 是否支持异步 | lock/Monitor/Mutex/Semaphore/ReaderWriterLock/SpinLock/Event 类/CountdownEvent/Barrier | SemaphoreSlim/ReaderWriterLockSlim |

| 维度 | 内核级 | 用户级（托管） |
|------|--------|---------------|
| 运行层级 | Mutex/Semaphore/ReaderWriterLock/Event 类/CountdownEvent | Lock/Monitor/SemaphoreSlim/ReaderWriterLockSlim/SpinLock/SpinWait/Barrier |

---

## 使用建议

- **按需加锁**：锁有开销，只在真正需要时加
- **最小化持锁范围**：锁住尽量少的代码，尽早释放
- **统一加锁顺序**：跨线程获取多个锁时，始终保持相同顺序
- **优先用 Slim 版本**：`SemaphoreSlim` 优于 `Semaphore`，`ReaderWriterLockSlim` 优于 `ReaderWriterLock`（不需要跨进程时）
- **优先异步 API**：用 `async`/`await` 替代 `Thread.Sleep`、`.Wait()`、`.Result`
- **加超时**：使用 `TryEnter`、`WaitAsync(timeout)` 等带超时版本，避免无限阻塞
- **用线程安全集合**：`System.Collections.Concurrent` 中的集合已内置线程安全，优先于手动加锁
- **别忘了 Dispose**：实现了 `IDisposable` 的同步对象用完要释放

---

## 参考

- [.NET Synchronisation APIs - Part 1 - In-Process Synchronisation](https://developmentwithadot.blogspot.com/2026/02/net-synchronisation-apis-part-1-in.html)
- [Overview of Synchronization Primitives – Microsoft Docs](https://learn.microsoft.com/en-us/dotnet/standard/threading/overview-of-synchronization-primitives)
- [Managed Threading Best Practices – Microsoft Docs](https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices)
