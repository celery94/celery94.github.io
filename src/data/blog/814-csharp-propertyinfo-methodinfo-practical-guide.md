---
pubDatetime: 2026-05-21T09:20:00+08:00
title: "C# PropertyInfo 与 MethodInfo：实用开发者指南"
description: "深入讲解 C# 反射中 PropertyInfo 和 MethodInfo 的核心用法，包括读写属性值、动态调用方法、处理泛型方法、性能缓存策略，以及 BindingFlags 的常见陷阱。"
tags: ["C#", ".NET", "反射", "PropertyInfo", "MethodInfo"]
slug: "csharp-propertyinfo-methodinfo-practical-guide"
ogImage: "../../assets/814/01-cover.png"
source: "https://www.devleader.ca/2026/05/20/propertyinfo-and-methodinfo-in-c-the-practical-developers-guide"
---

如果你曾经需要在运行时读写一个属性，而编译时根本不知道它的名字，那你已经遇到了 `PropertyInfo` 和 `MethodInfo` 的使用场景。这两种类型都来自 `System.Reflection` 命名空间，是 .NET 运行时类型检查的核心工具。ORM、序列化器、DI 容器、测试框架和插件系统，背后几乎都用到它们。

本文会把这两种类型讲清楚：怎么获取、怎么用、该注意什么性能问题，以及配套的 `FieldInfo`、`ConstructorInfo`、`EventInfo` 各自扮演什么角色。

## System.Reflection 的层次结构

在使用 `PropertyInfo` 和 `MethodInfo` 之前，先要明白它们在 `System.Reflection` 里的位置。.NET 的类型元数据以层级方式组织：

- **Assembly**：编译后的 `.dll` 或 `.exe`
- **Module**：程序集内的分区
- **Type**：类、结构体、接口、枚举或委托
- **MemberInfo**：所有成员的抽象基类
  - **PropertyInfo**：属性（含 `get`/`set` 访问器）
  - **MethodInfo**：方法
  - **FieldInfo**：字段
  - **EventInfo**：事件
  - **ConstructorInfo**：构造函数

你通过 `Type` 实例访问 `PropertyInfo` 和 `MethodInfo`，而 `Type` 来自 `typeof(MyClass)`、`instance.GetType()` 或 `Type.GetType("Namespace.ClassName")`。

## PropertyInfo 详解

`PropertyInfo` 表示运行时某个类或结构体上的单个属性。你可以用 `GetValue()` 读取属性值，用 `SetValue()` 写入，通过 `PropertyType` 检查类型，并确认 `get`/`set` 访问器是否存在。它还暴露了访问器对应的底层 `MethodInfo`——当你需要在方法级别检查可访问性时，这个细节很重要。

### 获取 PropertyInfo

```csharp
Type type = typeof(Person);

// 获取指定名称的属性
PropertyInfo? nameProp = type.GetProperty("Name");

// 获取所有公共实例属性
PropertyInfo[] allProps = type.GetProperties(
    BindingFlags.Public | BindingFlags.Instance);
```

不带 `BindingFlags` 的重载默认返回公共实例属性和静态属性。建议总是使用显式 `BindingFlags` 重载——范围更精确，意图也更清晰。

### 读写属性值

获取 `PropertyInfo` 引用后，`GetValue(object? obj)` 从给定实例读取属性当前值，`SetValue(object? obj, object? value)` 写入新值。两者都使用 `object?`，值类型在传入传出时会发生装箱拆箱。

如果 setter 是私有的或受保护的，`SetValue` 在某些运行时上下文下可能抛出 `MethodAccessException`。要可靠地操作私有 setter，需要显式用 `GetSetMethod(nonPublic: true)` 获取它，再通过该 `MethodInfo` 调用：

```csharp
public class Person
{
    public string Name { get; set; } = "";
    public int Age { get; private set; }

    public Person(string name, int age) { Name = name; Age = age; }
}

var person = new Person("Alice", 30);
Type type = typeof(Person);

// 读取
PropertyInfo nameProp = type.GetProperty("Name")!;
string? value = (string?)nameProp.GetValue(person);
Console.WriteLine(value); // "Alice"

// 写入（setter 是 public，可以直接用）
nameProp.SetValue(person, "Bob");
Console.WriteLine(person.Name); // "Bob"

// 用 NonPublic binding 访问私有 setter
PropertyInfo ageProp = type.GetProperty(
    "Age",
    BindingFlags.Public | BindingFlags.Instance)!;
MethodInfo? privateSetter = ageProp.GetSetMethod(nonPublic: true);
privateSetter?.Invoke(person, new object[] { 31 });
```

### CanRead 和 CanWrite

`CanRead` 和 `CanWrite` 只告诉你属性是否有 getter 或 setter，不反映可访问性——一个带私有 setter 的属性 `CanWrite` 仍然返回 `true`。要区分公共与非公共访问器，必须带 `nonPublic` 参数调用 `GetGetMethod()` 或 `GetSetMethod()`：

```csharp
PropertyInfo prop = typeof(Person).GetProperty("Age")!;

Console.WriteLine(prop.CanRead);  // true
Console.WriteLine(prop.CanWrite); // true —— setter 存在，只是私有

MethodInfo? publicSetter = prop.GetSetMethod(nonPublic: false);  // null
MethodInfo? anySetter    = prop.GetSetMethod(nonPublic: true);   // not null
```

### PropertyType

`PropertyType` 返回属性持有的运行时类型。在构建泛型映射器、验证器或序列化器时，常常需要根据属性类型分支——比如对 `DateTime` 和 `string` 属性采用不同的格式化逻辑，或者检测可空类型：

```csharp
PropertyInfo prop = typeof(Person).GetProperty("Age")!;
Console.WriteLine(prop.PropertyType.Name); // "Int32"

bool isNullable = Nullable.GetUnderlyingType(prop.PropertyType) != null;
```

### 实战示例：泛型属性复制器

下面是一个真实的应用场景——不管具体类型，把一个对象的同名属性复制给另一个对象：

```csharp
public static class PropertyCopier
{
    private static readonly ConcurrentDictionary<(Type, Type), (PropertyInfo Source, PropertyInfo Target)[]>
        _cache = new();

    public static void CopyProperties<TSource, TTarget>(TSource source, TTarget target)
        where TSource : class
        where TTarget : class
    {
        var key = (typeof(TSource), typeof(TTarget));
        var pairs = _cache.GetOrAdd(key, k => BuildPairs(k.Item1, k.Item2));

        foreach (var (srcProp, tgtProp) in pairs)
        {
            var value = srcProp.GetValue(source);
            tgtProp.SetValue(target, value);
        }
    }

    private static (PropertyInfo, PropertyInfo)[] BuildPairs(Type src, Type tgt)
    {
        var srcProps = src.GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Where(p => p.CanRead)
            .ToDictionary(p => p.Name);

        return tgt.GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Where(p => p.CanWrite && srcProps.ContainsKey(p.Name))
            .Select(p => (srcProps[p.Name], p))
            .ToArray();
    }
}
```

属性对在每种类型组合第一次使用时构建并缓存，后续调用只做 `GetValue`/`SetValue`，不再有元数据查找开销。

## MethodInfo 详解

`MethodInfo` 是表示可调用方法的反射类型。和 `PropertyInfo` 一样，通过 `Type` 对象获取。拿到 `MethodInfo` 后，你可以检查参数、返回类型、泛型参数，并通过 `Invoke()` 在运行时动态调用它。

### 获取 MethodInfo

```csharp
Type type = typeof(Calculator);

// 按名称获取（有重载时会失败）
MethodInfo? addMethod = type.GetMethod("Add");

// 按参数类型获取特定重载
MethodInfo? addInts = type.GetMethod("Add", new[] { typeof(int), typeof(int) });

// 获取所有公共实例方法
MethodInfo[] allMethods = type.GetMethods(
    BindingFlags.Public | BindingFlags.Instance);
```

当方法有重载时，`GetMethod(string name)` 会抛出 `AmbiguousMatchException`。只要方法可能被重载，就应该带上参数类型数组。

### 调用方法

`MethodInfo.Invoke(object? obj, object?[]? parameters)` 执行方法。实例方法传入目标对象，静态方法传入 `null`。返回值是 `object?`，需要强制转型。方法内部抛出的异常会被包装成 `TargetInvocationException`，应该在传播前解包：

```csharp
public class Calculator
{
    public int Add(int a, int b) => a + b;
    public static double Sqrt(double value) => Math.Sqrt(value);
}

var calc = new Calculator();
MethodInfo addMethod = typeof(Calculator).GetMethod("Add",
    new[] { typeof(int), typeof(int) })!;

// 实例方法：Invoke 第一个参数传目标对象
object? result = addMethod.Invoke(calc, new object[] { 3, 4 });
Console.WriteLine(result); // 7

// 静态方法：传 null 作为目标
MethodInfo sqrtMethod = typeof(Calculator).GetMethod("Sqrt")!;
object? sqrtResult = sqrtMethod.Invoke(null, new object[] { 16.0 });
Console.WriteLine(sqrtResult); // 4
```

### GetParameters 和 ReturnType

`GetParameters()` 返回 `ParameterInfo` 数组，每个元素携带参数名、类型（`ParameterType`）、位置和默认值。`ReturnType` 是表示返回类型的 `Type`，`void` 方法对应 `typeof(void)`：

```csharp
MethodInfo method = typeof(Calculator).GetMethod("Add",
    new[] { typeof(int), typeof(int) })!;

Console.WriteLine(method.ReturnType.Name); // "Int32"

foreach (ParameterInfo param in method.GetParameters())
{
    Console.WriteLine($"{param.Name}: {param.ParameterType.Name}");
    // a: Int32
    // b: Int32
}
```

框架用这种方式构建动态方法分发器，在运行时验证参数兼容性。

### 泛型方法

对于泛型方法，`IsGenericMethodDefinition` 为 `true`。不能直接调用泛型方法定义，需要先调用 `MakeGenericMethod(typeof(T1), ...)` 得到封闭的具体 `MethodInfo`，再调用它。`MakeGenericMethod` 的结果要缓存——每次调用都涉及 JIT 工作：

```csharp
public class Box
{
    public T Wrap<T>(T value) => value;
}

MethodInfo wrapMethod = typeof(Box).GetMethod("Wrap")!;
Console.WriteLine(wrapMethod.IsGenericMethod);           // true
Console.WriteLine(wrapMethod.IsGenericMethodDefinition); // true

// 构造 int 的具体版本
MethodInfo wrapInt = wrapMethod.MakeGenericMethod(typeof(int));
var box = new Box();
int wrapped = (int)wrapInt.Invoke(box, new object[] { 42 })!;
```

### 实战示例：简单方法分发器

下面的分发器把缓存和调用模式整合到一个可复用组件里。它根据名称从任意对象解析方法，用 `(Type, string)` 键缓存 `MethodInfo`，并正确解包 `TargetInvocationException`，让调用方看到真正的错误——这是命令路由系统和动态插件分发器中的常见模式：

```csharp
public sealed class MethodDispatcher
{
    private readonly ConcurrentDictionary<(Type, string), MethodInfo?> _cache = new();

    public object? Dispatch(object target, string methodName, params object[] args)
    {
        var type = target.GetType();
        var key = (type, methodName);

        var method = _cache.GetOrAdd(key, k =>
            k.Item1.GetMethod(k.Item2, BindingFlags.Public | BindingFlags.Instance));

        if (method is null)
            throw new InvalidOperationException(
                $"Method '{methodName}' not found on '{type.Name}'.");

        try
        {
            return method.Invoke(target, args);
        }
        catch (TargetInvocationException tie)
        {
            System.Runtime.ExceptionServices.ExceptionDispatchInfo
                .Capture(tie.InnerException!)
                .Throw();
            return null; // unreachable
        }
    }
}
```

注意 `TargetInvocationException` 的解包方式——这是通过反射调用方法时传播异常的正确做法。

## FieldInfo 简览

`FieldInfo` 表示字段（不是属性）。字段是类上的直接内存槽，没有 getter/setter。API 和 `PropertyInfo` 类似，但没有 `CanRead`/`CanWrite`——字段总是可读可写的（除非是 `readonly`）。检查 `readonly` 字段用 `field.IsInitOnly`：

```csharp
public class Config
{
    public string ConnectionString = ""; // 字段，不是属性
}

FieldInfo field = typeof(Config).GetField("ConnectionString")!;
var config = new Config();

field.SetValue(config, "Server=localhost;Database=dev");
string? value = (string?)field.GetValue(config);
```

`FieldInfo` 反射访问速度比 `PropertyInfo` 略快（省去了方法分发），但字段在设计良好的类里通常是私有的。

## EventInfo 和 ConstructorInfo

**EventInfo** 表示 .NET 事件，可以在运行时添加或移除处理器——在需要动态事件绑定的插件系统或 UI 框架中很有用：

```csharp
EventInfo? clickEvent = typeof(Button).GetEvent("Click");
// clickEvent.AddEventHandler(button, handler);
// clickEvent.RemoveEventHandler(button, handler);
```

**ConstructorInfo** 表示构造函数，是 `Activator.CreateInstance` 底层的实现。缓存后直接调用 `ConstructorInfo.Invoke` 在反复使用的场景下可以比 `Activator.CreateInstance` 快：

```csharp
ConstructorInfo ctor = typeof(Person)
    .GetConstructor(new[] { typeof(string), typeof(int) })!;

Person person = (Person)ctor.Invoke(new object[] { "Charlie", 25 });
```

## 性能：为什么必须缓存

每次调用 `GetProperty()`、`GetMethod()`、`GetProperties()` 或 `GetMethods()` 都涉及：

- 在 CLR 内部元数据表中查找 `Type` 对象
- 分配结果对象
- 按 `BindingFlags` 过滤

这不是免费的。`GetProperties()` 每次调用都会分配新数组。

原则很简单：**查一次，存起来，多次读取。**

```csharp
// ✅ 正确：静态缓存，每个类型只查一次
private static readonly ConcurrentDictionary<Type, PropertyInfo[]> _cache = new();

PropertyInfo[] GetCachedProperties(Type t) =>
    _cache.GetOrAdd(t, type =>
        type.GetProperties(BindingFlags.Public | BindingFlags.Instance));

// ❌ 错误：每次调用都重新查找
PropertyInfo[] GetProperties(Type t) =>
    t.GetProperties(BindingFlags.Public | BindingFlags.Instance);
```

对于启动时写入、之后只读的缓存，`System.Collections.Frozen` 中的 `FrozenDictionary<Type, PropertyInfo[]>`（.NET 8+ / .NET 10 可用）在稳定读取阶段的查找开销比 `ConcurrentDictionary` 更低。

## BindingFlags 详解

`BindingFlags` 控制返回哪些成员。最重要的几个标志：

| 标志 | 作用 |
|---|---|
| `BindingFlags.Public` | 包含 public 成员 |
| `BindingFlags.NonPublic` | 包含 private/protected/internal 成员 |
| `BindingFlags.Instance` | 包含实例成员 |
| `BindingFlags.Static` | 包含静态成员 |
| `BindingFlags.DeclaredOnly` | 排除继承的成员 |
| `BindingFlags.FlattenHierarchy` | 包含继承的静态成员（少见）|

标志用按位 OR 组合。漏掉 `Instance` 或 `Static` 是常见 bug——`GetProperty("Name", BindingFlags.Public)` 不加 `BindingFlags.Instance` 对实例属性会返回 `null`：

```csharp
// ✅ 明确且正确
var prop = type.GetProperty("Name",
    BindingFlags.Public | BindingFlags.Instance);

// ⚠️ 即使属性存在也可能返回 null（缺少 Instance 标志）
var propBug = type.GetProperty("Name", BindingFlags.Public);
```

## 常见问题

**GetProperty 为什么返回 null，但属性明明存在？**
最常见的原因是 `BindingFlags` 不完整：只传 `BindingFlags.Public` 但没有加 `BindingFlags.Instance`，或者查的是基类属性但用了 `BindingFlags.DeclaredOnly`。

**PropertyInfo 和 MethodInfo 可以跨线程共享吗？**
可以。它们是不可变的元数据描述符，不持有实例状态，通过 `static readonly` 字段或 `ConcurrentDictionary` 跨线程共享是安全的，而且正是推荐的做法。

**Native AOT 能用反射吗？**
可以，但有条件。Native AOT 会裁剪掉看起来不可达的代码。通过反射访问的成员可能被删除，除非加上 `[DynamicallyAccessedMembers]` 注解、使用 `[RequiresUnreferencedCode]`，或配置裁剪根。.NET 10 的发布工具链会对不安全的反射模式发出警告。高性能 AOT 场景下，编译后的委托或源生成器通常是更好的替代方案。

**如何处理泛型方法？**
`IsGenericMethodDefinition` 为 `true` 时，不能直接调用，需要先用 `MakeGenericMethod(typeof(T1), typeof(T2), ...)` 构造封闭版本。把结果按类型参数组合缓存起来，避免重复 JIT 开销。

## 小结

`PropertyInfo` 和 `MethodInfo` 是动态 .NET 代码里最常遇到的两种反射类型。`PropertyInfo` 给你运行时的属性值、类型和访问器。`MethodInfo` 让你动态调用方法、检查签名、操作泛型方法。两者都适合缓存——查一次，反复用。

`FieldInfo`、`ConstructorInfo` 和 `EventInfo` 各自对应不同的成员类型，都通过 `Type` 对象访问。用好 `BindingFlags` 来精确控制返回范围，调用反射方法时记得处理 `TargetInvocationException`。

掌握这些工具，你就有能力构建从属性复制器到完整插件分发器的各种动态系统，同时把性能控制在可接受的范围内。

## 参考

- [PropertyInfo and MethodInfo in C#: The Practical Developer's Guide](https://www.devleader.ca/2026/05/20/propertyinfo-and-methodinfo-in-c-the-practical-developers-guide)
- [Reflection in C#: 4 Simple But Powerful Code Examples](https://www.devleader.ca/2024/02/26/reflection-in-c-4-simple-but-powerful-code-examples)
- [Activator.CreateInstance in C# - A Quick Rundown](https://www.devleader.ca/2024/02/28/activatorcreateinstance-in-c-a-quick-rundown)
- [Plugin Contracts and Interfaces in C#: Designing Extensible Plugin Systems](https://www.devleader.ca/2026/04/08/plugin-contracts-and-interfaces-in-c-designing-extensible-plugin-systems)
