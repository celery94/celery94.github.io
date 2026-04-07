---
pubDatetime: 2026-04-07T08:00:00+08:00
title: "C# 中为类实现通用 EqualityComparer"
description: "介绍一个基于反射和编译委托的通用 GenericEqualityComparer<T>，无需修改类定义即可为任意 C# 类提供按值比较。涵盖公有/私有属性与字段的配置、EqualityWrapper 操作符重载、LINQ 集成以及适用边界。"
tags: ["CSharp", "dotnet", "设计模式"]
slug: "generic-equalitycomparer-for-csharp-classes"
ogImage: "../../assets/715/01-cover.png"
source: "https://toreaurstad.blogspot.com/2026/03/generic-equalitycomparer-for-classes-in.html"
---

![C# 通用 EqualityComparer 封面](../../assets/715/01-cover.png)

C# 的 `class` 默认按引用比较——即使两个对象的每个字段完全相同，`==` 和 `Equals` 也会返回 `false`。想解决这个问题，通常需要在每个类里手写 `Equals` 和 `GetHashCode`，代码一多就很烦。

作者 Tore Aurstad 实现了一个 `GenericEqualityComparer<T>`，利用反射发现成员、再把访问器编译成委托缓存起来，一次初始化后就能高效地按值比较任意类。本文基于他的原文和 GitHub 仓库，完整介绍这个工具的设计、用法和适用场景。

源码仓库：[https://github.com/toreaurstadboss/GenericEqualityComparer](https://github.com/toreaurstadboss/GenericEqualityComparer)

## 问题背景

```csharp
var car1 = new Car { Make = "Toyota", Model = "Camry", Year = 2020 };
var car2 = new Car { Make = "Toyota", Model = "Camry", Year = 2020 };

Console.WriteLine(car1 == car2);       // False — 不同引用
Console.WriteLine(car1.Equals(car2));  // False — 同上
```

两个内容完全相同的 `Car` 实例被判定为不相等，因为 `class` 的默认相等语义是引用相等。

`record` 和 `struct` 已经内置了值语义，但对于不能改动的第三方类、大量 POCO/DTO、或者只想快速加一层值比较的场景，重新实现一遍 `Equals`/`GetHashCode` 代价不小。

## GenericEqualityComparer 的核心思路

`GenericEqualityComparer<T>` 实现 `IEqualityComparer<T>`，在构造时通过反射收集 `T` 的成员，再把每个成员的访问器编译成 `Func<T, object>` 委托并缓存。后续的每次 `Equals` 调用都走委托而非反射，开销可控。

```csharp
public class GenericEqualityComparer<T> : IEqualityComparer<T> where T : class
{
    private List<Func<T, object>> _propertyGetters = new();
    private List<Func<T, object>> _fieldGetters = new();

    public GenericEqualityComparer(
        bool includeFields = false,
        bool includePrivateProperties = false,
        bool includePrivateFields = false)
    {
        CreatePropertyGetters(includePrivateProperties);
        if (includeFields || includePrivateFields)
        {
            CreateFieldGetters(includePrivateFields);
        }
    }

    private void CreatePropertyGetters(bool includePrivateProperties)
    {
        var bindingFlags = BindingFlags.Instance | BindingFlags.Public;
        if (includePrivateProperties)
        {
            bindingFlags |= BindingFlags.NonPublic;
        }

        var props = typeof(T).GetProperties(bindingFlags)
                             .Where(m => m.GetMethod != null).ToList();

        foreach (var prop in props)
        {
            ParameterExpression parameter = Expression.Parameter(typeof(T), "p");
            MemberExpression propertyExpression = Expression.Property(parameter, prop.Name);
            Expression boxed = Expression.Convert(propertyExpression, typeof(object));
            Expression<Func<T, object>> getter = Expression.Lambda<Func<T, object>>(boxed, parameter);
            _propertyGetters.Add(getter.Compile());
        }
    }
    // CreateFieldGetters 结构类似，改用 Expression.Field
}
```

`Equals` 方法先处理空值和引用相等的快捷路径，再逐一用委托取出属性/字段值并比较：

```csharp
public bool Equals(T? x, T? y)
{
    if (x == null || y == null) return false;
    if (ReferenceEquals(x, y)) return true;
    if (x.GetType() != y.GetType()) return false;

    foreach (var accessor in _propertyGetters)
    {
        if (!accessor(x).Equals(accessor(y))) return false;
    }
    foreach (var accessor in _fieldGetters)
    {
        if (!accessor(x).Equals(accessor(y))) return false;
    }
    return true;
}
```

`GetHashCode` 用 `HashCode.Combine` 把所有成员值合并成一个哈希，每次最多 8 个以符合 `HashCode.Combine` 的参数限制。

## 快速上手

### 比较公有属性

```csharp
var comparer = new GenericEqualityComparer<Car>();

var car1 = new Car { Make = "Toyota", Model = "Camry", Year = 2020 };
var car2 = new Car { Make = "Toyota", Model = "Camry", Year = 2020 };
var car3 = new Car { Make = "Toyota", Model = "Corolla", Year = 2020 };

Console.WriteLine(comparer.Equals(car1, car2));  // True  — 所有属性匹配
Console.WriteLine(comparer.Equals(car1, car3));  // False — Model 不同
```

### 与 LINQ 或集合配合

因为 `GenericEqualityComparer<T>` 实现了 `IEqualityComparer<T>`，可以直接传给 LINQ 方法：

```csharp
var cars = new List<Car>
{
    new Car { Make = "Toyota", Model = "Camry",   Year = 2020 },
    new Car { Make = "Toyota", Model = "Camry",   Year = 2020 }, // 重复
    new Car { Make = "Toyota", Model = "Corolla", Year = 2021 },
};

var comparer = new GenericEqualityComparer<Car>();

var unique  = cars.Distinct(comparer).ToList();     // 2 项
var grouped = cars.GroupBy(c => c, comparer);
```

## 构造参数说明

| 参数 | 类型 | 作用 |
|---|---|---|
| `includeFields` | bool | 包含公有实例字段 |
| `includePrivateProperties` | bool | 包含私有实例属性 |
| `includePrivateFields` | bool | 包含私有实例字段（同时开启公有字段） |

三个参数默认均为 `false`，即只比较公有实例属性。

### 场景：包含私有字段

```csharp
public class Car
{
    public string Make  { get; set; } = string.Empty;
    public string Model { get; set; } = string.Empty;
    public int    Year  { get; set; }

    private string _secretAssemblyNumber = string.Empty;
    public void SetSecretAssemblyNumber(string number) => _secretAssemblyNumber = number;
}

var ford1 = new Car { Make = "Ford", Model = "Focus", Year = 2022 };
var ford2 = new Car { Make = "Ford", Model = "Focus", Year = 2022 };
ford1.SetSecretAssemblyNumber("ASM-001");
ford2.SetSecretAssemblyNumber("ASM-999");

var defaultComparer = new GenericEqualityComparer<Car>();
Console.WriteLine(defaultComparer.Equals(ford1, ford2));  // True（忽略私有字段）

var deepComparer = new GenericEqualityComparer<Car>(includePrivateFields: true);
Console.WriteLine(deepComparer.Equals(ford1, ford2));     // False（检测到差异）
```

### 场景：包含私有属性

```csharp
var defaultComparer = new GenericEqualityComparer<Bicycle>();
Console.WriteLine(defaultComparer.Equals(bike1, bike2));  // True

var deepComparer = new GenericEqualityComparer<Bicycle>(includePrivateProperties: true);
Console.WriteLine(deepComparer.Equals(bike1, bike2));     // False
```

## EqualityWrapper 和 == / != 操作符

C# 不允许在外部比较器类中重载泛型类型参数 `T` 的 `==` / `!=`。为此，`GenericEqualityComparer<T>` 提供了 `For(value)` 方法，返回一个 `EqualityWrapper<T>` 结构体。这个 wrapper 同时持有值和比较器，因此它的 `==` / `!=` 会委托给比较器，而不是走引用相等。

```csharp
public readonly struct EqualityWrapper<T> where T : class
{
    private readonly T _value;
    private readonly GenericEqualityComparer<T> _comparer;

    internal EqualityWrapper(T value, GenericEqualityComparer<T> comparer)
    {
        _value    = value;
        _comparer = comparer;
    }

    public static bool operator ==(EqualityWrapper<T> left, EqualityWrapper<T> right)
        => left._comparer.Equals(left._value, right._value);

    public static bool operator !=(EqualityWrapper<T> left, EqualityWrapper<T> right)
        => !(left == right);

    public override int GetHashCode() => _comparer.GetHashCode(_value);
}
```

### 基础操作符用法

```csharp
var comparer = new GenericEqualityComparer<Car>();

bool same      = comparer.For(car1) == comparer.For(car2);  // True
bool different = comparer.For(car1) != comparer.For(car3);  // True
```

### 检测私有成员差异

```csharp
var deepComparer = new GenericEqualityComparer<Car>(includePrivateFields: true);

if (deepComparer.For(ford1) != deepComparer.For(ford2))
{
    Console.WriteLine("Cars differ (private field detected)");
}
```

### 一致的哈希

`EqualityWrapper<T>` 重写了 `GetHashCode()`，与 `==` 保持一致，因此可以安全用作字典键或放入 HashSet：

```csharp
int hash1 = comparer.For(car1).GetHashCode();
int hash2 = comparer.For(car2).GetHashCode();

Console.WriteLine(hash1 == hash2);  // True — 相等对象，哈希相等
```

## 使用总结

| 需求 | 用法 |
|---|---|
| 比较公有属性 | `new GenericEqualityComparer<T>()` |
| 包含公有字段 | `new GenericEqualityComparer<T>(includeFields: true)` |
| 包含私有属性 | `new GenericEqualityComparer<T>(includePrivateProperties: true)` |
| 包含私有字段 | `new GenericEqualityComparer<T>(includePrivateFields: true)` |
| 使用 `==` / `!=` | `comparer.For(a) == comparer.For(b)` |
| 与 LINQ 配合 | `list.Distinct(comparer)` / `list.GroupBy(x => x, comparer)` |

## 不适合的场景

- **性能敏感热路径**：初始化时编译委托有一次开销，每次调用也比手写实现稍慢，不适合写入紧密循环或高频调用。
- **record 和 struct**：内置值语义，直接用 `==` 就够了。
- **你完全掌控的类**：首选显式实现 `Equals`/`GetHashCode` 或 `IEquatable<T>`，更可读，性能更好。

这个工具最合适的场景是：第三方类无法修改、大量自动生成的 POCO / DTO 需要快速加值比较、或者在测试代码中验证两个对象是否"内容一致"。

## 框架兼容性说明

当前实现依赖 `HashCode.Combine`，要求 .NET Standard 2.1 或 .NET Core 2.1 及更高版本。如果目标框架是 .NET Framework 4.8 或更早，可以用两个质数（初始值 17，乘数 31）自己实现 `GetHashCode`：

```csharp
private static int Combine(params object[] values)
{
    unchecked
    {
        int hash = 17;
        foreach (var v in values)
        {
            int h = v?.GetHashCode() ?? 0;
            hash = hash * 31 + h;
        }
        return hash;
    }
}
```

选 17 和 31 是为了在属性数量和值分布上提供足够的哈希扩散，避免对称值 `(a, b)` 与 `(b, a)` 产生相同哈希。

## 参考

- [Generic EqualityComparer for classes in C# - Tore Aurstad](https://toreaurstad.blogspot.com/2026/03/generic-equalitycomparer-for-classes-in.html)
- [GitHub 源码仓库：GenericEqualityComparer](https://github.com/toreaurstadboss/GenericEqualityComparer)
