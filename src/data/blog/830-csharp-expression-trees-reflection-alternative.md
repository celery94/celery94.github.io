---
pubDatetime: 2026-05-26T20:00:00+08:00
title: "C# 表达式树替代反射：何时该做性能升级"
description: "反射每次调用都要重新验证、分派、装箱；表达式树把这些开销压缩到一次性的编译步骤，之后每次调用都是原生委托速度。本文介绍属性读写、构造工厂、方法调用四个场景的完整实现，以及一个泛型对象映射器示例，帮你判断什么时候该切换。"
tags: ["CSharp", "DotNet", "性能优化", "反射", "表达式树"]
slug: "csharp-expression-trees-reflection-alternative"
ogImage: "../../assets/830/01-cover.png"
source: "https://www.devleader.ca/2026/05/25/expression-trees-as-a-reflection-alternative-in-c-when-to-switch"
---

![C# 表达式树替代反射：何时该做性能升级](../../assets/830/01-cover.png)

写过序列化器、对象映射器或 DI 容器的人，大概都踩过同一个坑：`PropertyInfo.GetValue()` 调用一多，profiler 里出现一根明显的柱子。解法不难理解——把反射换成编译后的委托——但真正落地时往往没有一套顺手的代码。

这篇文章讲的就是这个转换过程：从原始反射，到表达式树，到编译缓存委托。原文作者给出了属性 getter、setter、构造工厂、方法调用四个场景的完整实现，以及一个把它们串起来的泛型对象映射器。

## 表达式树是什么

表达式树把代码表示成对象树——每个节点是一个 `Expression` 子类：`BinaryExpression`、`MethodCallExpression`、`MemberExpression`、`LambdaExpression` 等等。树本身只是在描述"要做什么计算"，`.Compile()` 才是把这个描述交给 JIT、生成真正的 IL、产出一个委托。

```csharp
using System.Linq.Expressions;

// 构建 (int x) => x * 2 的表达式树
ParameterExpression param = Expression.Parameter(typeof(int), "x");
BinaryExpression body = Expression.Multiply(param, Expression.Constant(2));
Expression<Func<int, int>> lambda = Expression.Lambda<Func<int, int>>(body, param);

// 编译一次，这是唯一的一次性开销
Func<int, int> doubler = lambda.Compile();

// 之后每次调用都没有反射开销
int result = doubler(7); // 14
```

关键点在于：`.Compile()` 触发运行时代码生成，只需要支付一次。把结果委托缓存起来，后续每次调用都是 JIT 编译后的原生速度。

反射的代价则不同。每次调用 `PropertyInfo.GetValue(obj)` 时，运行时都要：

- 验证属性是否存在于对象的实际类型上
- 通过虚调用链分派
- 对值类型装箱
- 返回 `object`

每次调用都重走一遍。表达式树把这些工作全部前置到一次性的 `.Compile()` 步骤里。

## 四步转换管线

把一个反射调用替换成编译委托的通用模式只有四步：

1. **获取 `MemberInfo`** — `PropertyInfo`、`MethodInfo`、`ConstructorInfo` 等，这是唯一需要用反射的地方，只做一次
2. **构建表达式树** — 用 `Expression.*` 工厂方法描述操作
3. **包装成 `LambdaExpression` 并调用 `.Compile()`**
4. **缓存委托** — 存到 `static` 字段、`ConcurrentDictionary<Type, Delegate>`，或 .NET 8+ 的 `FrozenDictionary<Type, Delegate>`（只读性能最佳）

```csharp
// 概念骨架
static TDelegate BuildAndCache<TDelegate>(Type type, string memberName)
    where TDelegate : Delegate
{
    // 第 1 步：一次反射
    var member = type.GetProperty(memberName) ?? throw new ArgumentException(...);

    // 第 2 步：构建表达式树
    var param = Expression.Parameter(typeof(object), "obj");
    var cast = Expression.Convert(param, type);
    var access = Expression.Property(cast, (PropertyInfo)member);
    var body = Expression.Convert(access, typeof(object));
    var lambda = Expression.Lambda<TDelegate>(body, param);

    // 第 3 步：编译
    return lambda.Compile();
}
```

下面逐个看四个常见场景。

## 编译属性 Getter

读取属性值是反射最常见的用途——ORM、映射器、序列化器都需要。下面是一个泛化的 getter，接受任意对象，返回属性值（以 `object` 形式）：

```csharp
using System.Linq.Expressions;
using System.Collections.Frozen;

public static class CompiledPropertyAccessor
{
    private static readonly ConcurrentDictionary<(Type, string), Func<object, object?>> _cache = new();

    public static Func<object, object?> GetGetter(Type type, string propertyName)
        => _cache.GetOrAdd((type, propertyName), static key =>
        {
            var (t, name) = key;
            var prop = t.GetProperty(name)
                ?? throw new ArgumentException($"Property '{name}' not found on {t.Name}");

            // 构建: (object obj) => (object)(((TOwner)obj).PropertyName)
            var objParam = Expression.Parameter(typeof(object), "obj");
            var typedAccess = Expression.Property(
                Expression.Convert(objParam, t),
                prop);
            var boxed = Expression.Convert(typedAccess, typeof(object));
            var lambda = Expression.Lambda<Func<object, object?>>(boxed, objParam);

            return lambda.Compile();
        });
}
```

使用方式直接：

```csharp
public sealed record Customer(string Name, int Age);

var customer = new Customer("Alice", 30);

var nameGetter = CompiledPropertyAccessor.GetGetter(typeof(Customer), "Name");
var ageGetter  = CompiledPropertyAccessor.GetGetter(typeof(Customer), "Age");

Console.WriteLine(nameGetter(customer)); // Alice
Console.WriteLine(ageGetter(customer));  // 30
```

每个属性的第一次调用支付编译成本，后续每次调用都是委托调用，没有反射。

如果需要强类型 getter 以避免值类型装箱，可以用泛型类型参数构建 `Func<TOwner, TProperty>` 版本。

## 编译属性 Setter

Setter 稍微复杂一点，需要用到 `Expression.Assign`，还需要注意 `record` 的 `init`-only 属性（它们没有普通的 setter）：

```csharp
public static class CompiledPropertySetter
{
    private static readonly ConcurrentDictionary<(Type, string), Action<object, object?>> _cache = new();

    public static Action<object, object?> GetSetter(Type type, string propertyName)
        => _cache.GetOrAdd((type, propertyName), static key =>
        {
            var (t, name) = key;
            var prop = t.GetProperty(name)
                ?? throw new ArgumentException($"Property '{name}' not found on {t.Name}");

            if (prop.SetMethod is null)
            {
                throw new InvalidOperationException($"Property '{name}' has no setter.");
            }

            // 构建: (object obj, object? value) => ((TOwner)obj).PropertyName = (TProp)value
            var objParam   = Expression.Parameter(typeof(object), "obj");
            var valueParam = Expression.Parameter(typeof(object), "value");

            var typedObj   = Expression.Convert(objParam, t);
            var typedValue = Expression.Convert(valueParam, prop.PropertyType);
            var propAccess = Expression.Property(typedObj, prop);
            var assign     = Expression.Assign(propAccess, typedValue);

            var lambda = Expression.Lambda<Action<object, object?>>(assign, objParam, valueParam);

            return lambda.Compile();
        });
}
```

对于 `init`-only 属性（.NET 10 的 record 里很常见），需要通过 `ConstructorInfo` 构建新实例，而不是修改现有实例——下一节讲的工厂就是这个用途。

## 编译构造工厂

`Activator.CreateInstance` 很方便，但每次调用都有反射开销。表达式树能给无参数和有参数构造函数都提供零额外开销的路径：

```csharp
public static class CompiledFactory
{
    // 无参数工厂
    public static Func<T> BuildFactory<T>()
    {
        var ctor = typeof(T).GetConstructor(Type.EmptyTypes)
            ?? throw new InvalidOperationException($"{typeof(T).Name} has no parameterless constructor.");

        var newExpr = Expression.New(ctor);
        var lambda  = Expression.Lambda<Func<T>>(newExpr);
        return lambda.Compile();
    }

    // 带参数工厂 — 支持任意构造函数签名
    public static Func<object[], object> BuildFactory(Type type, Type[] paramTypes)
    {
        var ctor = type.GetConstructor(paramTypes)
            ?? throw new InvalidOperationException($"No matching constructor found on {type.Name}.");

        // 构建: (object[] args) => new T((T0)args[0], (T1)args[1], ...)
        var argsParam = Expression.Parameter(typeof(object[]), "args");
        var ctorArgs  = paramTypes.Select((t, i) =>
            Expression.Convert(
                Expression.ArrayIndex(argsParam, Expression.Constant(i)),
                t) as Expression).ToArray();

        var newExpr = Expression.New(ctor, ctorArgs);
        var boxed   = Expression.Convert(newExpr, typeof(object));
        var lambda  = Expression.Lambda<Func<object[], object>>(boxed, argsParam);
        return lambda.Compile();
    }
}
```

```csharp
// 在启动时缓存——此后每次调用零分配
var customerFactory = CompiledFactory.BuildFactory<Customer>();
var c1 = customerFactory(); // 没有反射，没有装箱
```

## 编译方法调用

`MethodInfo.Invoke()` 是出了名的慢。`Expression.Call` 能把它替换成编译委托：

```csharp
public static class CompiledMethodInvoker
{
    public static Func<object, object?[], object?> Build(MethodInfo method)
    {
        var instanceParam = Expression.Parameter(typeof(object), "instance");
        var argsParam     = Expression.Parameter(typeof(object?[]), "args");

        var paramInfos = method.GetParameters();

        // 把每个参数从 object[] 转换为期望的参数类型
        var castArgs = paramInfos.Select((p, i) =>
            Expression.Convert(
                Expression.ArrayIndex(argsParam, Expression.Constant(i)),
                p.ParameterType) as Expression).ToArray();

        // 把实例转换为声明类型
        var instance = Expression.Convert(instanceParam, method.DeclaringType!);
        var call = method.ReturnType == typeof(void)
            ? (Expression)Expression.Block(
                Expression.Call(instance, method, castArgs),
                Expression.Constant(null, typeof(object)))
            : Expression.Convert(Expression.Call(instance, method, castArgs), typeof(object));

        var lambda = Expression.Lambda<Func<object, object?[], object?>>(
            call, instanceParam, argsParam);

        return lambda.Compile();
    }
}
```

静态方法的话，省略 instance 参数，改用 `Expression.Call(null, method, castArgs)`。

## 实战：泛型对象映射器

把上面这些组合成一个有实际用途的东西——一个把匹配属性从 source 对象复制到 destination 对象的映射器，这也是 AutoMapper 等库的核心机制：

```csharp
public sealed class ExpressionMapper<TSource, TDest>
    where TDest : new()
{
    private readonly List<Action<TSource, TDest>> _mappings;

    public ExpressionMapper()
    {
        _mappings = BuildMappings();
    }

    public TDest Map(TSource source)
    {
        var dest = new TDest();
        foreach (var mapping in _mappings)
        {
            mapping(source, dest);
        }
        return dest;
    }

    private static List<Action<TSource, TDest>> BuildMappings()
    {
        var sourceProps = typeof(TSource).GetProperties()
            .ToDictionary(p => p.Name);

        var destProps = typeof(TDest).GetProperties()
            .Where(p => p.CanWrite);

        var mappings = new List<Action<TSource, TDest>>();

        foreach (var destProp in destProps)
        {
            if (!sourceProps.TryGetValue(destProp.Name, out var sourceProp))
                continue;

            if (sourceProp.PropertyType != destProp.PropertyType)
                continue;

            // 构建: (TSource src, TDest dst) => dst.Prop = src.Prop
            var srcParam  = Expression.Parameter(typeof(TSource), "src");
            var dstParam  = Expression.Parameter(typeof(TDest), "dst");
            var getValue  = Expression.Property(srcParam, sourceProp);
            var setValue  = Expression.Assign(Expression.Property(dstParam, destProp), getValue);
            var lambda    = Expression.Lambda<Action<TSource, TDest>>(setValue, srcParam, dstParam);

            mappings.Add(lambda.Compile());
        }

        return mappings;
    }
}
```

注意这个实现只在构造函数里做了一次反射，编译了委托，然后 `Map()` 方法就不再调用任何反射 API。反射开销是一次性的启动成本。

```csharp
// 启动时（通常在 DI 注册阶段）
var mapper = new ExpressionMapper<CustomerEntity, CustomerDto>();

// 热路径 — 没有反射
var dto = mapper.Map(entity);
```

## 代价和适用边界

表达式树不是免费的。原文作者对代价有清醒的描述：

**代价：**
- **启动编译延迟** — `.Compile()` 触发运行时代码生成，大型类型可能增加几毫秒启动时间。在有冷启动敏感的 serverless 环境里要注意
- **代码复杂度** — 构建表达式树的代码比等价的反射代码更啰嗦，对没接触过 `System.Linq.Expressions` 的开发者不直观
- **调试困难** — 无法在运行时单步跟踪表达式树，只能检查树结构
- **NativeAOT 不兼容** — 表达式树本身作为数据结构是 AOT 安全的，但 `.Compile()` 执行运行时代码生成，**不支持 Native AOT**。AOT 目标应考虑 source generators 或 `UnsafeAccessor`

**优势：**
- 编译后每次调用的开销等同于直接调用方法
- 使用强类型泛型签名时，值类型不装箱
- 一套实现适用于所有类型，不需要为每种类型生成一个类

**甜蜜区：高频调用（序列化、映射、属性绑定），类型集合在启动后固定，但在编译时未知。**

## 什么情况下不该用

- **一次性或低频调用** — 启动阶段读一个配置值，直接用 `PropertyInfo.GetValue()` 就行，开销可以忽略，代码更清晰
- **编译时已知类型** — 如果映射的两种类型你自己拥有，直接写映射代码，直接属性赋值比编译委托更快
- **NativeAOT 目标** — .NET 10 的 trimmer 会在你的 AOT 项目里使用 `Expression.Compile()` 时发出警告
- **生命周期很短的进程** — CLI 工具或执行窗口极短的 Lambda，可能在 `.Compile()` 上花的时间比省下来的还多

对于只需要动态实例化、不需要走完整表达式树路径的场景，`Activator.CreateInstance` 和 `ConstructorInfo` 直接调用通常就够了。

## 与 .NET 10 的关系

表达式树 API 自 .NET Framework 3.5 以来基本稳定，.NET 10 没有根本改变它。.NET 10 带来的是更广的背景：

- **`FrozenDictionary<TKey, TValue>`**（.NET 8 引入）让只读委托缓存读性能更好，适合启动时填充、之后只读的场景
- **更完善的 NativeAOT 工具链**，让你在编译阶段就能发现误用了 `Expression.Compile()` 的地方
- **JIT 诊断改进**，表达式树编译后的委托在 profiler 里能更清晰地显示出来

## 选择参考

原文作者给了三个频率维度的判断：

- **高频、启动后类型固定** — 映射器、序列化器、属性绑定器。最清晰的使用场景，一次编译、无限调用
- **中频、类型多样** — 动态渲染任意类型表单的后台管理界面，每种类型只编译一次，总开销由不同类型数量决定，不是调用次数
- **低频或一次性** — 配置读取、诊断工具、迁移脚本。没有性能问题需要解决，直接用反射

还有一点值得注意：**source generators** 在表达式树适合但启动成本敏感的情况下是另一个选项。它们产出等委托速度的代码，且零启动成本，但代价是更复杂的构建管线，以及只能在编译时已知的类型上工作。

---

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [原文：Expression Trees as a Reflection Alternative in C#: When to Switch](https://www.devleader.ca/2026/05/25/expression-trees-as-a-reflection-alternative-in-c-when-to-switch)
- [Reflection in C#: 4 Simple But Powerful Code Examples](https://www.devleader.ca/2024/02/26/reflection-in-c-4-simple-but-powerful-code-examples)
- [Activator.CreateInstance in C# - A Quick Rundown](https://www.devleader.ca/2024/02/28/activatorcreateinstance-in-c-a-quick-rundown)
- [ConstructorInfo - How To Make Reflection in DotNet Faster for Instantiation](https://www.devleader.ca/2024/03/17/constructorinfo-how-to-make-reflection-in-dotnet-faster-for-instantiation)
- [Source Generation vs Reflection in Needlr](https://www.devleader.ca/2026/02/07/source-generation-vs-reflection-in-needlr-choosing-the-right-approach)
