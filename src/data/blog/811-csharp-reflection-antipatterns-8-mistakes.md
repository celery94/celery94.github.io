---
pubDatetime: 2026-05-20T08:20:00+08:00
title: "C# 反射反模式：8 个会伤害你应用的错误"
description: "反射是 .NET 最强大的工具之一，但 8 种常见误用会带来性能悬崖、AOT 兼容性问题和难以排查的 bug。本文梳理这 8 个反模式及其修复方案，涵盖热路径缓存、编译委托、[UnsafeAccessor]、[DynamicallyAccessedMembers] 和源生成器。"
tags: ["C#", ".NET", "反射", "性能优化", "AOT"]
slug: "csharp-reflection-antipatterns-8-mistakes"
ogImage: "../../assets/811/01-cover.png"
source: "https://www.devleader.ca/2026/05/19/c-reflection-antipatterns-8-mistakes-that-will-hurt-your-app"
---

![C# 反射反模式封面：开发者踩坑与修复方案的漫画对比](../../assets/811/01-cover.png)

反射是 .NET 最灵活的能力之一。它让你在运行时检查类型、调用方法、读写属性，构建纯静态代码无法实现的动态系统。但正因如此，它也是最容易被滥用的工具。

一个不经意的 `GetProperties()` 调用，一个随手写的 `Invoke()`，积累下来就是一道你找不到根因的性能悬崖。本文梳理 .NET 10 代码库中最常见的 8 个反射反模式，以及每种的修复方案。

---

## 反模式 1：在热路径中使用反射

最常见的错误：在循环内部或每秒执行数千次的方法里调用反射。

**问题代码：**

```csharp
public void ProcessItems(IEnumerable<MyModel> items)
{
    foreach (var item in items)
    {
        // 每次迭代都触发一次完整的元数据查找
        var prop = item.GetType().GetProperty("Name");
        var value = prop?.GetValue(item);
        Console.WriteLine(value);
    }
}
```

`GetType().GetProperty("Name")` 在每次迭代都要遍历类型的元数据表，循环量一上来，开销迅速叠加。

**修复方式——缓存查找结果：**

```csharp
private static readonly PropertyInfo? _nameProp =
    typeof(MyModel).GetProperty("Name", BindingFlags.Public | BindingFlags.Instance);

public void ProcessItems(IEnumerable<MyModel> items)
{
    foreach (var item in items)
    {
        var value = _nameProp?.GetValue(item);
        Console.WriteLine(value);
    }
}
```

反射元数据查找第一次执行时相对昂贵。把结果缓存在静态字段或字典里，后续访问只是对已加载元数据的廉价比较。

---

## 反模式 2：反复调用 GetProperties() 不缓存

这是反模式 1 的近亲。`GetProperties()` 每次调用都会分配一个新数组。在每次请求或每条记录都调用的方法里，会持续产生需要 GC 清理的垃圾。

**问题代码：**

```csharp
public Dictionary<string, object?> ToDictionary(object obj)
{
    var result = new Dictionary<string, object?>();
    // 每次调用都分配新的 PropertyInfo[]
    foreach (var prop in obj.GetType().GetProperties())
    {
        result[prop.Name] = prop.GetValue(obj);
    }
    return result;
}
```

**修复方式——缓存数组：**

```csharp
private static readonly ConcurrentDictionary<Type, PropertyInfo[]> _propCache = new();

public Dictionary<string, object?> ToDictionary(object obj)
{
    var type = obj.GetType();
    var props = _propCache.GetOrAdd(
        type,
        t => t.GetProperties(BindingFlags.Public | BindingFlags.Instance));

    var result = new Dictionary<string, object?>(props.Length);
    foreach (var prop in props)
    {
        result[prop.Name] = prop.GetValue(obj);
    }
    return result;
}
```

在 .NET 10 中，如果缓存在启动时构建、之后不再写入，可以用 `System.Collections.Frozen` 的 `FrozenDictionary<Type, PropertyInfo[]>` 替代 `ConcurrentDictionary`。对于只读密集型查找场景，它能利用完美哈希实现更低的查找开销。

---

## 反模式 3：用反射调用，编译委托更合适

`PropertyInfo.GetValue` 和 `MethodInfo.Invoke` 是晚期绑定的。每次调用都经过装箱、参数验证和运行时分发。对于频繁调用的代码，可以付出一次编译委托的代价，然后以近原生速度调用。

**问题代码（被频繁调用）：**

```csharp
var method = typeof(Calculator).GetMethod("Add")!;
var result = method.Invoke(calculator, new object[] { 3, 4 });
```

**修复方式——编译一次，当委托调用：**

```csharp
// 构建一次并缓存
var param1 = Expression.Parameter(typeof(int), "a");
var param2 = Expression.Parameter(typeof(int), "b");
var instance = Expression.Constant(calculator);
var call = Expression.Call(instance, typeof(Calculator).GetMethod("Add")!, param1, param2);
var addDelegate = Expression.Lambda<Func<int, int, int>>(call, param1, param2).Compile();

// 之后以近原生速度调用
var result = addDelegate(3, 4);
```

编译后的委托首次编译开销在于 JIT，之后每次调用都近似原生方法调用。这种技术在序列化框架、ORM 和依赖注入容器中被广泛使用。

---

## 反模式 4：忽略 BindingFlags 获取过多成员

`GetProperties()`、`GetMethods()`、`GetMembers()` 不传 `BindingFlags` 时，会返回一个宽泛的默认集合。这几乎不是你想要的结果，而且浪费时间去过滤那些本不该被检索的成员。

**问题代码：**

```csharp
// 返回所有公共实例成员，包括继承来的
var props = type.GetProperties();
// 然后再过滤...
var ownProps = props.Where(p => p.DeclaringType == type).ToArray();
```

**修复方式——明确指定 BindingFlags：**

```csharp
// 只获取当前类型声明的公共实例属性，不含继承成员
var props = type.GetProperties(
    BindingFlags.Public |
    BindingFlags.Instance |
    BindingFlags.DeclaredOnly);
```

明确指定 `BindingFlags` 的主要好处是代码意图清晰和正确性——同时也省去了事后过滤的步骤。

---

## 反模式 5：未正确处理 TargetInvocationException

通过反射调用方法时，如果该方法抛异常，异常会被包裹在 `TargetInvocationException` 里。只捕获外层异常会丢失真正的错误；泛泛捕获 `Exception` 则可能吞掉不该吞的东西。

**问题代码：**

```csharp
try
{
    method.Invoke(target, args);
}
catch (Exception ex)
{
    // 这里记录的是包装器异常，不是真正的错误
    _logger.LogError(ex, "Method invocation failed");
}
```

**修复方式——解包内层异常：**

```csharp
try
{
    method.Invoke(target, args);
}
catch (TargetInvocationException tie)
{
    // 重新抛出，保留原始堆栈信息
    ExceptionDispatchInfo.Capture(tie.InnerException!).Throw();
}
```

用 `ExceptionDispatchInfo.Capture(...).Throw()` 保留原始堆栈，而不是创建一个新的。同时也要留意 `TargetParameterCountException` 和参数类型不匹配时的 `ArgumentException`。

---

## 反模式 6：用反射绕过访问修饰符

有时确实需要访问私有成员——测试代码、框架、遗留互操作。旧做法是带 `BindingFlags.NonPublic` 的 `SetValue` 或 `Invoke`。这还能用，但 .NET 8 引入了更干净的替代品：`[UnsafeAccessor]`。

**旧写法：**

```csharp
var field = typeof(SomeClass)
    .GetField("_privateField", BindingFlags.NonPublic | BindingFlags.Instance)!;
field.SetValue(instance, newValue);
```

**更好的写法（.NET 8+ / .NET 10）：**

```csharp
// 声明访问器——JIT 时编译器验证签名
[UnsafeAccessor(UnsafeAccessorKind.Field, Name = "_privateField")]
static extern ref int GetPrivateField(SomeClass instance);

// 像普通字段引用一样使用
GetPrivateField(instance) = newValue;
```

`[UnsafeAccessor]` JIT 编译后零开销——没有装箱，没有运行时元数据查找，JIT 甚至可以内联访问。只要目标类型和成员在编译期已知，它就是私有成员访问的首选。

---

## 反模式 7：AOT 场景未标注 [DynamicallyAccessedMembers]

Native AOT 编译（以及 .NET 10 独立发布时的 trimmer）会移除看起来不可达的代码。通过反射访问的类型如果没有静态引用，会在运行时悄无声息地失败——相关成员直接就不存在了。

**问题代码（无 AOT 注解）：**

```csharp
public object? CreateInstance(string typeName)
{
    var type = Type.GetType(typeName); // AOT：类型可能被裁剪掉
    return Activator.CreateInstance(type!);
}
```

**修复方式——标注以保留成员：**

```csharp
public object? CreateInstance(
    [DynamicallyAccessedMembers(DynamicallyAccessedMemberTypes.PublicConstructors)]
    Type type)
{
    return Activator.CreateInstance(type);
}
```

`[DynamicallyAccessedMembers]` 告诉 trimmer 传入的类型需要保留哪些成员。.NET 10 工具链在发布时会对缺少注解的反射调用点输出警告——在裁剪或 AOT 编译的应用里，这些警告会变成运行时错误。

---

## 反模式 8：用反射解决源生成器能解决的问题

这可能是影响最深远的反模式。很多开发者为之使用反射的场景——序列化、DI 注册、对象映射、验证——其实源生成器在编译期就能搞定。源生成器不产生任何运行时开销，生成的是普通 C# 代码。

动手写反射代码前，先问一下：**有没有源生成器已经解决了这个问题？**

- **序列化**：`System.Text.Json` 的源生成（`[JsonSerializable]`）完全替代了基于反射的序列化。
- **依赖注入**：可以通过源生成器在不使用反射的情况下注册服务。
- **程序集扫描**：在注册阶段而不是运行时做类型发现。

**应该避免的写法：**

```csharp
// 每次启动都扫描所有类型——发现所有 IPlugin 实现
var plugins = Assembly.GetExecutingAssembly()
    .GetTypes()
    .Where(t => typeof(IPlugin).IsAssignableFrom(t) && !t.IsInterface)
    .Select(t => (IPlugin)Activator.CreateInstance(t)!)
    .ToList();
```

**更好的做法——至少在启动时缓存结果，或用源生成器 / 显式代码注册：**

```csharp
// 执行一次，缓存结果。更好的方式：通过源生成器或显式代码注册。
private static readonly IReadOnlyList<Type> PluginTypes = Assembly
    .GetExecutingAssembly()
    .GetTypes()
    .Where(t => typeof(IPlugin).IsAssignableFrom(t) && !t.IsInterface)
    .ToList();
```

编译委托和 `[UnsafeAccessor]` 在需要真实吞吐量时都比裸反射快。当你能把工作移到编译期，源生成器比两者都强。

---

## 总结

反射是工具，不是拐杖。用得不慎，它会带来性能开销、AOT 不兼容，以及难以定位的 bug。

这 8 个反模式覆盖了真实 .NET 10 代码库中绝大多数反射问题：热路径查找、未缓存的 `GetProperties()`、晚期绑定调用、过宽的 `BindingFlags`、被吞掉的 `TargetInvocationException`、不必要的 `NonPublic` 访问、缺失的 AOT 注解，以及忽视源生成器。

每一个的修复方向都很明确：**缓存你查找的内容、编译你频繁调用的内容、为 trimmer 标注需要保留的内容、能在编译期解决的就别留到运行期。**

## 参考

- [C# Reflection Anti-Patterns: 8 Mistakes That Will Hurt Your App](https://www.devleader.ca/2026/05/19/c-reflection-antipatterns-8-mistakes-that-will-hurt-your-app)
- [Reflection in C#: 4 Simple But Powerful Code Examples](https://www.devleader.ca/2024/02/26/reflection-in-c-4-simple-but-powerful-code-examples)
- [ConstructorInfo - How To Make Reflection in DotNet Faster for Instantiation](https://www.devleader.ca/2024/03/17/constructorinfo-how-to-make-reflection-in-dotnet-faster-for-instantiation)
- [Source Generation vs Reflection in Needlr](https://www.devleader.ca/2026/02/07/source-generation-vs-reflection-in-needlr-choosing-the-right-approach)
