---
pubDatetime: 2026-05-20T09:52:07+08:00
title: "C# 反射：.NET 10 完全指南"
description: "从 System.Reflection 核心 API 到性能优化，再到何时该换用源生成器或 [UnsafeAccessor]——一篇帮你真正用好 C# 反射的完整指南。"
tags: ["C#", ".NET", "反射", "性能优化", "源生成器"]
slug: "csharp-reflection-complete-net10-guide"
ogImage: "../../assets/812/01-cover.png"
source: "https://www.devleader.ca/2026/05/18/c-reflection-the-complete-net-10-guide"
---

C# 反射（Reflection）第一次被人发现时，总让人感觉找到了超能力：运行时检查任意类型、动态调用从未见过的方法、把字符串变成对象实例。然后你把它带进了生产环境，启动时间翻倍了。

这种张力——极度的灵活性 vs 真实的性能代价——正是这篇指南想讲清楚的。我们会覆盖核心 API、实用模式、.NET 10 的性能现状，以及最重要的一点：什么时候应该放下反射，改用更合适的工具。

> .NET 10 的 Native AOT 和裁剪工具可能会删除只通过反射访问的成员——后面会专门讲怎么处理这件事。

## 什么是 C# 反射

反射是程序在运行时检查并操作自身元数据的能力。在 .NET 里，这些元数据存在于程序集（Assembly）中——编译后的 `.dll` 和 `.exe` 文件不只包含 IL 代码，还携带丰富的类型信息：类名、属性名和类型、方法签名、特性、访问修饰符等。

`System.Reflection` 命名空间提供了查询这些信息的 API。你可以：

- 枚举程序集中包含的所有类型
- 检视任意类型的成员（属性、方法、字段、构造函数）
- 在对象实例上读写属性值
- 动态调用方法
- 根据运行时才知道的字符串名称创建类型实例

序列化库、依赖注入容器、ORM、测试框架都依赖反射。理解它，你才能更好地使用这些工具，也才能构建自己的灵活系统。

## 核心类型

### Type：反射的核心

`System.Reflection` 的所有操作都从 `System.Type` 出发。它描述一个类型的完整信息：名称、命名空间、基类、接口和所有成员。

获取 `Type` 的三种方式：

```csharp
// 1. typeof 运算符——编译时解析，类型已知时首选
Type t1 = typeof(string);

// 2. GetType() 实例方法——任何对象都有
string value = "hello";
Type t2 = value.GetType();

// 3. Type.GetType()——通过完全限定名，适合插件/动态场景
Type? t3 = Type.GetType("System.String");
Type? t4 = Type.GetType("MyApp.Services.OrderService, MyApp");
```

类型在编译时已知时，优先用 `typeof`——它避免了 `Type.GetType()` 的字符串解析开销，由编译器而非运行时负责解析。

### Assembly：类型的容器

`Assembly` 代表一个已加载的 .NET 二进制文件。枚举其中所有类型是插件系统和扩展框架的入口点。

```csharp
// 加载当前执行的程序集
Assembly current = Assembly.GetExecutingAssembly();

// 通过路径加载（插件场景）
Assembly plugin = Assembly.LoadFrom("/plugins/MyPlugin.dll");

// 获取程序集中所有公开类型
Type[] types = plugin.GetExportedTypes();

// 找到实现了特定接口的类型
Type targetInterface = typeof(IPlugin);
IEnumerable<Type> implementations = types
    .Where(t => !t.IsAbstract && targetInterface.IsAssignableFrom(t));
```

### PropertyInfo：读写属性值

`PropertyInfo` 代表类型上的单个属性，可以读取其名称、类型、是否有 getter 或 setter，以及在活跃实例上读写值。

```csharp
public class Order
{
    public int Id { get; set; }
    public string CustomerName { get; set; } = string.Empty;
    public decimal Total { get; private set; }
}

// 获取所有公开实例属性
PropertyInfo[] properties = typeof(Order).GetProperties();

foreach (PropertyInfo prop in properties)
{
    Console.WriteLine($"{prop.Name}: {prop.PropertyType.Name} " +
                      $"(CanRead={prop.CanRead}, CanWrite={prop.CanWrite})");
}

// 从实例读取值
var order = new Order { Id = 42, CustomerName = "Alice" };
PropertyInfo? idProp = typeof(Order).GetProperty("Id");
object? id = idProp?.GetValue(order);  // 返回 42（装箱为 object）

// 写入值
PropertyInfo? nameProp = typeof(Order).GetProperty("CustomerName");
nameProp?.SetValue(order, "Bob");
Console.WriteLine(order.CustomerName);  // Bob
```

### MethodInfo：动态调用方法

`MethodInfo` 代表一个方法，可以在运行时对实例调用它。

```csharp
public class Calculator
{
    public int Add(int a, int b) => a + b;
    private string FormatResult(int result) => $"Result: {result}";
}

var calc = new Calculator();
Type calcType = typeof(Calculator);

// 获取公开方法并调用
MethodInfo? addMethod = calcType.GetMethod("Add");
object? result = addMethod?.Invoke(calc, new object[] { 3, 4 });
Console.WriteLine(result);  // 7

// 使用 BindingFlags 访问私有方法
MethodInfo? formatMethod = calcType.GetMethod(
    "FormatResult",
    BindingFlags.NonPublic | BindingFlags.Instance);

object? formatted = formatMethod?.Invoke(calc, new object[] { 42 });
Console.WriteLine(formatted);  // Result: 42
```

### ConstructorInfo：控制实例化

`ConstructorInfo` 代表特定的构造函数重载，在需要精确选择构造函数或构建缓存快速实例化路径时很有用。

```csharp
public class Service
{
    public string Name { get; }

    public Service(string name)
    {
        Name = name;
    }
}

// 获取接受单个 string 参数的构造函数
ConstructorInfo? ctor = typeof(Service)
    .GetConstructor(new[] { typeof(string) });

object? instance = ctor?.Invoke(new object[] { "OrderService" });
if (instance is Service svc)
{
    Console.WriteLine(svc.Name);  // OrderService
}
```

## Activator.CreateInstance：快速实例化

需要在运行时创建只知道类型对象的实例时，`Activator.CreateInstance` 是最简洁的选项。

```csharp
// 使用默认构造函数创建
object? instance = Activator.CreateInstance(typeof(Order));

// 带构造函数参数
object? service = Activator.CreateInstance(
    typeof(Service),
    "MyService");

// 泛型版本——创建并返回有类型的结果
Order? order = Activator.CreateInstance<Order>();

// 通过类型名称创建（插件场景）
Type? pluginType = Type.GetType("MyPlugin.OrderProcessor, MyPlugin");
if (pluginType is not null)
{
    object? processor = Activator.CreateInstance(pluginType);
}
```

## BindingFlags：控制成员发现范围

默认情况下，`GetProperties()`、`GetMethods()` 等只返回公开实例成员。`BindingFlags` 让你扩大或缩小这个范围。

```csharp
// 全量——公开、非公开、实例、静态
MemberInfo[] allMembers = typeof(Order).GetMembers(
    BindingFlags.Public |
    BindingFlags.NonPublic |
    BindingFlags.Instance |
    BindingFlags.Static);

// 只查非公开实例字段（常用于测试内部状态）
FieldInfo[] privateFields = typeof(Order).GetFields(
    BindingFlags.NonPublic | BindingFlags.Instance);

// 静态方法
MethodInfo[] staticMethods = typeof(Order).GetMethods(
    BindingFlags.Public | BindingFlags.Static);
```

需要提醒的是：在生产代码中通过反射访问私有成员是代码坏味道。测试辅助代码里尚可接受，但如果你频繁地从外部深入你拥有的类型的私有状态，先检查一下这些成员是否应该通过一个设计合理的 API 暴露出来。

## .NET 10 中的性能现状

反射相比直接代码执行确实慢——开销来自元数据查找、类型安全检查、值类型装箱以及无法内联。但这个差距在历代 .NET 版本中已经明显缩小，而且聪明地缓存可以消除大部分重复查找的成本。

### 朴素写法（代价昂贵）

```csharp
// 每次都调 GetProperty——每次都付元数据查找的代价
public object? ReadProperty(object instance, string propertyName)
{
    return instance.GetType()
        .GetProperty(propertyName)
        ?.GetValue(instance);
}
```

### 缓存反射（好多了）

```csharp
// 以 Type 为键缓存 PropertyInfo 数组——只查一次
private static readonly ConcurrentDictionary<Type, PropertyInfo[]> _propertyCache = new();

public PropertyInfo[] GetCachedProperties(Type type)
{
    return _propertyCache.GetOrAdd(
        type,
        t => t.GetProperties(BindingFlags.Public | BindingFlags.Instance));
}
```

### 升级到 FrozenDictionary（.NET 8 起可用）

如果你的缓存在启动时填充一次、之后只读，`FrozenDictionary<TKey, TValue>`（.NET 8 引入，.NET 9 和 .NET 10 进一步优化）能给你更快的查找速度，因为它针对只读访问模式优化，没有锁开销。

```csharp
using System.Collections.Frozen;

// 在启动时构建缓存
private static FrozenDictionary<Type, PropertyInfo[]> BuildPropertyCache(
    IEnumerable<Type> types)
{
    return types.ToFrozenDictionary(
        t => t,
        t => t.GetProperties(BindingFlags.Public | BindingFlags.Instance));
}

// 用法：_cache 是启动时初始化一次的字段
private readonly FrozenDictionary<Type, PropertyInfo[]> _cache;
```

反射元数据缓存正是 `FrozenDictionary` 的设计场景：写一次、读多次。

### 真正需要关注的成本

即使有了缓存，每次 `PropertyInfo.GetValue` 和 `SetValue` 调用仍然会装箱值类型并进行运行时类型检查。对于每秒处理成千上万对象的热路径，这些调用会累积起来。这就是下面替代方案的用武之地。

## 什么时候不该用反射

这可能是这篇指南最重要的部分。

### 编译时类型已知时

如果你在编译时就知道类型，用直接属性访问、接口或泛型。反射在这个场景里什么都买不到，只带来开销和脆弱性。

```csharp
// ❌ 不必要地使用反射
PropertyInfo? idProp = typeof(Order).GetProperty("Id");
int id = (int)idProp!.GetValue(order)!;

// ✅ 直接访问属性
int id = order.Id;
```

### 热路径上未先性能分析时

紧密循环中处理数万条记录的反射是延迟飙升的祸根。先用性能分析工具确认瓶颈。如果反射确实是瓶颈，再看下面的替代方案。

### 习惯性破坏封装时

如果你需要频繁从类外部访问私有状态，设计本身在向你说话。在用反射检查类型之前，先反思一下设计。

### 源生成器才是正确工具时

对于 DI 注册、序列化和编译时代码生成场景，源生成器在构建时生成与反射等价的代码——零运行时成本、完整的 AOT 兼容性，以及编译时而非运行时的错误提示。

## 替代方案

### 缓存委托和表达式树

从 `PropertyInfo` 编译一次 `Func<T, object>`，然后反复调用。经过 JIT 编译后，执行速度接近原生代码。

```csharp
using System.Linq.Expressions;

public static Func<T, object?> BuildGetter<T>(PropertyInfo prop)
{
    var param = Expression.Parameter(typeof(T), "obj");
    var access = Expression.Property(param, prop);
    var convert = Expression.Convert(access, typeof(object));
    return Expression.Lambda<Func<T, object?>>(convert, param).Compile();
}

// 构建一次，多次调用
Func<Order, object?> getTotal = BuildGetter<Order>(typeof(Order).GetProperty("Total")!);
object? total = getTotal(order);  // 快——已编译委托
```

### 源生成器

源生成器在编译时运行，生成与反射等价的 C# 代码。`System.Text.Json` 的序列化就用了这个方案。这种方式替代了运行时程序集扫描，把代价从运行时移到了构建时。

### UnsafeAccessor（.NET 8+）

`[UnsafeAccessor]` 特性让你以原生速度访问你不拥有的类型的私有成员，同时完全兼容 AOT。当你以前会用反射访问内部状态时，这是更合适的工具。

```csharp
// 直接访问私有字段——无反射、无装箱、AOT 安全
[UnsafeAccessor(UnsafeAccessorKind.Field, Name = "_internalState")]
static extern ref string GetInternalState(MyType obj);
```

### 接口和泛型

最基础的替代方案：设计好你的抽象，让你不需要运行时类型发现。接口给你多态性，无需反射；泛型给你类型参数化的行为，无需 `object` 转型。

DI 容器里反射的作用，部分原因在于它要连接在编译时根本不可能知道的类型。但如果你同时控制合同的两端，通过暴露接口往往可以完全避免反射。

## 实战示例：属性映射器

把以上概念整合到一起：一个精简的属性映射器，把匹配的属性值从一个对象复制到另一个对象。这是反射真正合适的场景之一。

```csharp
public static class PropertyMapper
{
    // 以（源类型，目标类型）对为键缓存映射关系
    private static readonly ConcurrentDictionary<(Type, Type), (PropertyInfo Source, PropertyInfo Dest)[]>
        _mappingCache = new();

    public static void Map<TSource, TDest>(TSource source, TDest dest)
        where TSource : notnull
        where TDest : notnull
    {
        var key = (typeof(TSource), typeof(TDest));

        var mappings = _mappingCache.GetOrAdd(key, _ =>
        {
            var sourceProps = typeof(TSource)
                .GetProperties(BindingFlags.Public | BindingFlags.Instance)
                .Where(p => p.CanRead)
                .ToDictionary(p => p.Name);

            var destProps = typeof(TDest)
                .GetProperties(BindingFlags.Public | BindingFlags.Instance)
                .Where(p => p.CanWrite)
                .ToDictionary(p => p.Name);

            return sourceProps.Keys
                .Intersect(destProps.Keys)
                .Where(name => sourceProps[name].PropertyType
                    .IsAssignableTo(destProps[name].PropertyType))
                .Select(name => (sourceProps[name], destProps[name]))
                .ToArray();
        });

        foreach (var (srcProp, destProp) in mappings)
        {
            destProp.SetValue(dest, srcProp.GetValue(source));
        }
    }
}
```

每个类型对的映射关系只计算一次并缓存下来。后续调用只付 `GetValue`/`SetValue` 的代价，不再有元数据发现的开销。

## 常见问题

### typeof 和 GetType() 有什么区别

`typeof` 是编译时运算符，在编译阶段解析为 `System.Type`。`GetType()` 是 `object` 上的实例方法，在运行时解析为对象的实际类型——这在多态场景中很重要。如果 `Animal animal = new Dog()`，那么 `typeof(Animal)` 给你的是 `Animal` 的类型，而 `animal.GetType()` 给你的是 `Dog` 的类型。类型在编译时已知时用 `typeof`；需要实例的具体运行时类型时用 `GetType()`。

### .NET 10 中反射还慢吗

反射相比编译代码确实有开销——元数据查找、值类型装箱以及无法内联或优化。但 .NET 运行时在历代版本中显著改善了反射性能。最大的成本通常是重复的元数据发现。把 `PropertyInfo` 和 `MethodInfo` 实例缓存起来——读密集场景用 `FrozenDictionary`——可以消除大部分开销。追求绝对峰值吞吐时，从表达式树编译委托或换用源生成器。

### 反射能和 AOT 编译配合使用吗

这是 .NET NativeAOT 的关键注意事项。反射依赖元数据，AOT 编译器如果判断某些类型或成员未被使用，可能会裁剪掉这些元数据。你需要用 `[DynamicallyAccessedMembers]` 特性标注代码，告诉裁剪工具哪些元数据需要保留，或者使用 `rd.xml` 根描述符文件。源生成器和 `[UnsafeAccessor]` 完全兼容 AOT，在裁剪场景下越来越成为首选。

### 什么时候用 Activator.CreateInstance 而不是 ConstructorInfo.Invoke

`Activator.CreateInstance` 是一次性或低频实例化的简洁 API。`ConstructorInfo.Invoke` 在需要精细控制构造函数选择（比如按参数类型选取特定重载）或构建缓存快速路径时更合适。对于高频实例化，考虑从 `ConstructorInfo` 编译一个委托并缓存，而不是在循环里直接调 `Invoke`。

### C# 反射有哪些安全风险

使用 `BindingFlags.NonPublic` 时，反射可以绕过访问修饰符（`private`、`protected`），破坏封装。.NET 5+ 不再支持部分信任和代码访问安全（CAS）。今天反射的安全关注点主要是绕过封装和访问私有状态——只在受控的基础设施代码中使用它。动态加载程序集（比如插件）时，你在执行来自潜在不可信来源的代码——验证插件签名，在隔离的 `AssemblyLoadContext` 实例中加载，对于强隔离需求考虑在独立进程中运行。永远不要从不可信用户能够影响的路径加载程序集。

### 性能敏感代码的最佳替代方案有哪些

四种替代方案覆盖大多数场景：第一，表达式树——从 `LambdaExpression` 编译出 `Func<T, TResult>`，以接近原生的速度调用；第二，源生成器——在编译时生成等价代码，零运行时开销；第三，`[UnsafeAccessor]`（.NET 8+）——以原生性能和完整 AOT 兼容性访问私有成员；第四，接口设计——反射存在的原因有时是缺少抽象层，加一个接口往往能完全消除对反射的需求。

## 小结

C# 反射是功能强大的运行时检查和调用 API，伴随着真实的权衡。核心类型——`Type`、`Assembly`、`PropertyInfo`、`MethodInfo`、`ConstructorInfo`——让你能访问单靠静态代码无法实现的元数据和运行时行为。插件系统、序列化、DI 容器和测试框架都依赖它。

但反射有代价：运行时开销、不加标注就不兼容 AOT、绕过有意为之的封装的风险。在 .NET 10 中，这些代价比以往都更低，而 `FrozenDictionary` 缓存、表达式树编译委托和源生成器给了你当反射开销不可接受时的出路。

用好反射的思维模型很简单：类型在编译时真的未知时才用反射。类型已知时，直接用类型。需要动态行为时，先分析性能——然后再决定用缓存、委托还是源生成器来达到你需要的性能指标。

## 参考

- [C# Reflection: The Complete .NET 10 Guide](https://www.devleader.ca/2026/05/18/c-reflection-the-complete-net-10-guide)
- [Reflection in C#: 4 Simple But Powerful Code Examples](https://www.devleader.ca/2024/02/26/reflection-in-c-4-simple-but-powerful-code-examples)
- [ConstructorInfo - How To Make Reflection in DotNet Faster for Instantiation](https://www.devleader.ca/2024/03/17/constructorinfo-how-to-make-reflection-in-dotnet-faster-for-instantiation)
- [Activator.CreateInstance in C# - A Quick Rundown](https://www.devleader.ca/2024/02/28/activatorcreateinstance-in-c-a-quick-rundown)
- [Plugin Architecture in C#: The Complete Guide to Extensible .NET Applications](https://www.devleader.ca/2026/04/07/plugin-architecture-in-c-the-complete-guide-to-extensible-net-applications)
- [Source Generation vs Reflection in Needlr: Choosing the Right Approach](https://www.devleader.ca/2026/02/07/source-generation-vs-reflection-in-needlr-choosing-the-right-approach)
