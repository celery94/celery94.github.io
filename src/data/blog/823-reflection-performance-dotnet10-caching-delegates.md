---
pubDatetime: 2026-05-22T08:09:50+08:00
title: ".NET 10 反射性能：先缓存，再编译，再测量"
description: "Dev Leader 这篇文章把 .NET 10 里的反射性能拆开讲清楚：慢的通常是成员查找和 late-bound invocation，优化顺序是缓存 PropertyInfo、使用 FrozenDictionary、编译 delegate、必要时使用 UnsafeAccessor，并用 BenchmarkDotNet 验证。"
tags: ["DotNet", "CSharp", "Reflection", "性能优化"]
slug: "reflection-performance-dotnet10-caching-delegates"
ogImage: "../../assets/823/01-cover.png"
source: "https://www.devleader.ca/2026/05/21/reflection-performance-in-net-10-benchmarks-caching-and-delegates"
---

“Reflection is slow” 是 .NET 里很常见的一句话，但它太粗了。Dev Leader 这篇文章的价值在于把反射成本拆开：哪些操作确实贵，哪些操作只要缓存就够，哪些场景需要 compiled delegates 或 `[UnsafeAccessor]`。

更好的问题是：“这次反射调用是不是在热路径里”。热路径就是高频执行的位置，比如请求处理、序列化循环、逐行数据处理。如果只是后台管理工具、测试初始化、启动时加载配置，反射开销通常不值得专门优化。

## 慢在哪里

反射的成本主要分两类。

第一类是成员查找，比如 `GetProperty("Name")`、`GetMethod("Add")`、`GetProperties()`。这些调用要遍历 CLR 的元数据表，做过滤，并分配结果对象。`GetProperties()` 还会在每次调用时分配新的 `PropertyInfo[]`。

第二类是 late-bound invocation，也就是 `PropertyInfo.GetValue()`、`MethodInfo.Invoke()`、`ConstructorInfo.Invoke()`。这些调用通常会有值类型 boxing、参数验证、间接派发，而且不能被 JIT inline。

相比之下，拿到已经缓存的 `PropertyInfo` 引用很便宜；调用已经编译好的 `Func<>` delegate 也接近普通方法调用；`[UnsafeAccessor]` 在 JIT 编译后可以走直接访问路径。

## 先缓存元数据

最简单也最常见的优化，是把成员查找结果缓存起来。原文用一个 `UserMapper` 举例，原始写法每次 `Map()` 都调用 `GetProperties()`：

```csharp
foreach (var prop in user.GetType().GetProperties())
{
    result[prop.Name] = prop.GetValue(user);
}
```

这会在每次调用时重新分配 `PropertyInfo[]`，还要重复做元数据查找。

如果类型固定，可以把属性数组放到静态字段：

```csharp
private static readonly PropertyInfo[] _userProps =
    typeof(User).GetProperties(BindingFlags.Public | BindingFlags.Instance);
```

这样只在类首次加载时做一次查找。`GetValue()` 仍然有 late-bound 开销，但成员查找已经被消掉。

如果代码要处理多个类型，可以用 `ConcurrentDictionary<Type, PropertyInfo[]>` 按类型缓存：

```csharp
private static readonly ConcurrentDictionary<Type, PropertyInfo[]> _props = new();

public static PropertyInfo[] GetProperties(Type type) =>
    _props.GetOrAdd(
        type,
        t => t.GetProperties(BindingFlags.Public | BindingFlags.Instance));
```

`GetOrAdd` 是线程安全的，第一次访问某个类型时付出查找成本，后续直接读缓存。

## 只读缓存用 FrozenDictionary

`ConcurrentDictionary` 适合运行时持续读写。如果你的缓存在启动阶段构建好，之后不再修改，可以考虑 `FrozenDictionary<TKey, TValue>`。

`FrozenDictionary` 来自 `System.Collections.Frozen`，从 .NET 8 开始可用，在 .NET 10 中也完全支持。它面向只读、高频读取场景，构建后不可变，查找时能减少平均开销。

适合它的场景是：启动时扫描一批类型，构建反射缓存，然后运行期只读：

```csharp
private static readonly FrozenDictionary<Type, PropertyInfo[]> _props =
    types.ToFrozenDictionary(
        t => t,
        t => t.GetProperties(BindingFlags.Public | BindingFlags.Instance));
```

如果类型是运行时不断出现的动态集合，`ConcurrentDictionary` 更合适。如果类型集合在启动后稳定，`FrozenDictionary` 更干净。

## 热路径用 compiled delegate

缓存 `PropertyInfo` 只能消掉查找成本。`GetValue()` 本身仍然是 late-bound 调用。

如果 profiler 已经确认 `GetValue()` 或 `Invoke()` 在热路径里，可以用 expression tree 编译 delegate。原文给出的 getter 思路是：用 `Expression.Property` 构造访问表达式，再用 `Expression.Lambda(...).Compile()` 生成 `Func<TObject, TProperty>`。

```csharp
public static Func<TObject, TProperty> BuildGetter<TObject, TProperty>(
    PropertyInfo property)
{
    var param = Expression.Parameter(typeof(TObject), "obj");
    var body = Expression.Property(param, property);
    var convert = Expression.Convert(body, typeof(TProperty));

    return Expression
        .Lambda<Func<TObject, TProperty>>(convert, param)
        .Compile();
}
```

使用时只在启动或缓存初始化时编译一次：

```csharp
PropertyInfo nameProp = typeof(User).GetProperty("Name")!;
Func<User, string> getName = BuildGetter<User, string>(nameProp);

string name = getName(user);
```

后续调用就是普通 delegate 调用，避免每次 `GetValue()` 的间接开销。setter 也可以用同样方式编译成 `Action<TObject, TProperty>`。

如果类型和属性只能在运行时决定，也可以编译 `Func<object, object?>` 这类通用 getter，但值类型仍可能发生 boxing。性能要求高时，强类型 delegate 更好。

## 特定私有成员用 UnsafeAccessor

`[UnsafeAccessor]` 是 .NET 8 引入的 attribute，可以为私有字段或方法生成运行时提供的直接 accessor。它不走反射查找，不做 late-bound dispatch，也不需要每次查 metadata。

原文示例是访问 `BankAccount` 的私有字段 `_balance`：

```csharp
using System.Runtime.CompilerServices;

public class BankAccount
{
    private decimal _balance;

    public BankAccount(decimal initial) => _balance = initial;
    public decimal Balance => _balance;
}

[UnsafeAccessor(UnsafeAccessorKind.Field, Name = "_balance")]
static extern ref decimal GetBalance(BankAccount account);
```

然后可以直接改字段：

```csharp
var account = new BankAccount(100m);
GetBalance(account) = 200m;
Console.WriteLine(account.Balance);
```

这适合测试辅助、框架内部适配、高性能内部代码。它要求目标类型在编译期已知，也要求签名和成员名严格匹配。纯动态场景仍然更适合 compiled delegates 或其他反射方案。

## 什么时候够快

可以按这张简单表判断：

| 场景                                           | 建议                                      |
| ---------------------------------------------- | ----------------------------------------- |
| 启动时配置、插件加载、测试初始化               | 普通反射通常够用                          |
| 每秒几千次以下，且主要耗时在 I/O、网络、数据库 | 缓存 `PropertyInfo`/`MethodInfo` 通常够用 |
| 序列化、ORM、data mapper、每个请求都跑的循环   | 考虑 compiled delegates                   |
| 编译期已知类型上的私有成员访问                 | 可以考虑 `[UnsafeAccessor]`               |
| 类型和成员在编译期已知，且要兼容 AOT/trimming  | 优先考虑 source generator                 |

Native AOT 和 trimming 要单独注意。反射访问到的成员可能在发布时被裁掉，需要 `[DynamicallyAccessedMembers]`、`rd.xml` roots，或者改成 source generator / 显式代码。

## 用 BenchmarkDotNet 测

原文建议不要凭感觉判断。BenchmarkDotNet 是 .NET 微基准常用工具。对反射来说，关键是把一次性初始化和每次调用成本分开。

一个合理的 benchmark 应该包括：

- `[MemoryDiagnoser]`：观察每次操作分配，尤其是 boxing
- `[GlobalSetup]`：把缓存和 delegate 编译放在测量前
- direct access 作为 baseline
- Release 模式运行：`dotnet run -c Release`

原文的比较对象包括：

- direct access
- uncached reflection
- cached reflection
- compiled delegate

这样测出来的重点在于同一环境下几种策略的相对差异，而非某个绝对数字。CPU、CLR 版本和具体 workload 都会影响结果。

## 实用顺序

可以把优化顺序记成一条阶梯：

1. 先确认反射是否在热路径里。
2. 如果只是重复查找成员，先缓存 `PropertyInfo` / `MethodInfo`。
3. 如果缓存只读且启动后不变，换成 `FrozenDictionary`。
4. 如果 `GetValue()` / `Invoke()` 仍然是瓶颈，编译 delegate。
5. 如果是编译期已知类型的私有成员访问，评估 `[UnsafeAccessor]`。
6. 如果能在编译期生成代码，优先考虑 source generator。
7. 每一步都用 BenchmarkDotNet 验证。

反射不是不能用。真正要避免的是在热路径里重复做查找、重复做 late-bound invocation，还不测量。

## 参考

- [Reflection Performance in .NET 10: Benchmarks, Caching, and Delegates](https://www.devleader.ca/2026/05/21/reflection-performance-in-net-10-benchmarks-caching-and-delegates)
- [Reflection in C#: 4 Simple But Powerful Code Examples](https://www.devleader.ca/2024/02/26/reflection-in-c-4-simple-but-powerful-code-examples)
- [BenchmarkDotNet](https://benchmarkdotnet.org/)
- [UnsafeAccessorAttribute](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.unsafeaccessorattribute)
