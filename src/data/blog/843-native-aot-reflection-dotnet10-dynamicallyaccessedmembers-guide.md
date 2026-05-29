---
pubDatetime: 2026-05-29T14:25:00+08:00
title: ".NET 10 Native AOT 下让反射保持安全：DynamicallyAccessedMembers 实用指南"
description: "Native AOT 把不可达类型一并裁掉，反射在运行时就空手而归。本文按 Dev Leader 的思路梳理 IL2xxx 警告含义，演示用 [DynamicallyAccessedMembers]、[RequiresUnreferencedCode]、[RequiresDynamicCode] 把反射注解清楚，并给出 .NET 10 上的 AOT 兼容审计清单。"
tags: ["C#", ".NET", ".NET 10", "Native AOT", "Reflection"]
slug: "native-aot-reflection-dotnet10-dynamicallyaccessedmembers-guide"
ogImage: "../../assets/843/01-cover.png"
source: "https://www.devleader.ca/2026/05/28/making-reflection-native-aot-safe-in-net-10-dynamicallyaccessedmembers-guide"
---

![裁剪、保留成员、编译期生成三段式线稿封面](../../assets/843/01-cover.png)

把 .NET 10 的应用切到 Native AOT，多数人第一反应是一面墙的警告，第二反应可能是运行时直接崩。裁剪器（trimmer）会基于静态分析把它认为永远走不到的类型和成员删掉，而反射的工作方式就是绕开静态视野——结果就是 `Type.GetType` 返回 `null`，`Activator.CreateInstance` 抛 `TypeLoadException`，问题点常常和真实调用差好几层。

Dev Leader 的这篇指南把这件事拆得很直接：AOT 兼容不是“别用反射”，而是要把每一次反射讲清楚——告诉裁剪器哪些成员必须保留，或者诚实承认这段代码就是不适合裁剪。这篇文章按原文展开，把 `[DynamicallyAccessedMembers]`、`[RequiresUnreferencedCode]`、`[RequiresDynamicCode]` 三套注解和源生成器的位置说一遍，最后给一份能照着跑的审计清单。

## 反射和 Native AOT 为什么天生不合

Native AOT 的工作方式是：从入口点和静态构造器出发，沿着所有可以静态看到的引用做一次“根可达”分析，没标到的类型和成员就从产物里剪掉。这对启动速度、二进制大小和容器冷启动很友好，但反射本质是动态的——`Type.GetType("MyApp.SomeService")` 这种调用，裁剪器在发布期没法知道 `MyApp.SomeService` 是不是真的被用到，于是顺手把它删了。运行时这次反射要么拿到 `null`，要么抛一个不好定位的 `TypeLoadException`。

同样的问题会出现在：

- `Activator.CreateInstance(type)`，`type` 只在运行时才知道
- `MethodInfo.Invoke` 调用一个按名字找到的方法
- `typeof(T)` 中的 `T` 被层层透传却没有任何注解
- 表达式树编译（`Expression.Compile()`）这种运行时发射 IL 的场景

理解反射本身是另一件事。如果对反射 API 还不熟，先看一眼基础再回到 AOT 话题会更顺。

## 裁剪器到底做了什么

在 csproj 里开 `<PublishTrimmed>true</PublishTrimmed>` 或者 `<PublishAot>true</PublishAot>`，ILLink 这一层就接管编译产物。它跟踪静态方法调用、字段访问、类型引用——这部分它都看得见。它**看不见**的是“间接类型访问”：任何根据运行时字符串或某个运行时才确定的 `Type` 对象去解析类型 / 成员的代码。

碰到这种调用，裁剪器会发警告，格式大致是：

```text
IL2075: 'this' argument does not satisfy 'DynamicallyAccessedMembersAttribute' in call to
'System.Type.GetMethod(String)'. The return value of method
'System.Type.GetType(String)' does not have matching annotations.
```

警告并不可怕，可怕的是当成噪音忽略掉。每条 `IL2xxx` 都标出了一个具体位置，要你做出选择：补注解、改源生成器，或者承认这段代码就是不安全。

## 看懂 IL2xxx 警告

`IL2xxx` 警告码遵循一套统一含义，记住几个高频的就够日常使用：

- `IL2026`：调用了带 `[RequiresUnreferencedCode]` 的成员
- `IL2060`：调用了一个泛型方法，它的类型实参可能撑不过裁剪
- `IL2067` / `IL2068`：参数或返回值缺少 `[DynamicallyAccessedMembers]` 注解
- `IL2070` / `IL2072` / `IL2075`：反射 API 的 `this` 参数缺少所需注解
- `IL2111`：被反射引用的方法带 `[DynamicallyAccessedMembers]` 参数

根本原因几乎都一样：调用链里某处的 `Type` 值从“没有注解的位置”流到了“需要注解的反射 API”。修复思路也一样：把注解沿着调用图一路传到底。

## 主角：`[DynamicallyAccessedMembers]`

`DynamicallyAccessedMembersAttribute` 是你最常用的工具——而且它不是 .NET 10 新增的，从 .NET 5 起就存在。它可以贴在 `Type` 参数、字段、属性，或者泛型类型参数上，等于跟裁剪器说：“我要对这个类型做反射，下面这些成员请一定留下。”

```csharp
using System.Diagnostics.CodeAnalysis;

public static object CreateInstance(
    [DynamicallyAccessedMembers(DynamicallyAccessedMemberTypes.PublicConstructors)] Type type)
{
    return Activator.CreateInstance(type)!;
}
```

裁剪器读到这条注解，会做两件事：

1. 把该类型的公共构造函数保留下来
2. 强制每个调用点也满足同一个保留要求

注解会沿调用链自动传播。只要某个参数被 `[DynamicallyAccessedMembers]` 标了，裁剪器就要求所有传给它的值要么本身也有同样的注解，要么是裁剪器能直接看到的具体类型。

### `DynamicallyAccessedMemberTypes` 取值

枚举值用来精确表达“要保留什么”。要太多会让裁剪退化，要太少则运行时反射会失败。

| 取值 | 保留的内容 |
| --- | --- |
| `PublicConstructors` | 所有公共 `.ctor` 重载 |
| `NonPublicConstructors` | 所有非公共 `.ctor` 重载 |
| `PublicMethods` | 所有公共实例和静态方法 |
| `NonPublicMethods` | 所有非公共实例和静态方法 |
| `PublicFields` | 所有公共字段 |
| `NonPublicFields` | 所有非公共字段 |
| `PublicProperties` | 所有公共属性（含相关访问器） |
| `NonPublicProperties` | 所有非公共属性 |
| `PublicEvents` | 所有公共事件 |
| `Interfaces` | 所有实现的接口 |
| `All` | 全部成员；仅作最后手段 |

原则和 DI 生命周期类似：能写多具体就写多具体。`All` 是“我放弃”按钮，能让警告消失，但裁剪也基本失效。

## 例子一：给泛型工厂加注解

下面这段是典型反例：

```csharp
// ❌ 产生 IL2077，T 的构造函数可能被裁掉
public static T Create<T>() where T : class
{
    return (T)Activator.CreateInstance(typeof(T))!;
}
```

修法是把注解直接贴到泛型参数上：

```csharp
// ✅ trim-safe：裁剪器知道每个具体 T 都要保留公共构造函数
public static T Create<[DynamicallyAccessedMembers(DynamicallyAccessedMemberTypes.PublicConstructors)] T>()
    where T : class
{
    return (T)Activator.CreateInstance(typeof(T))!;
}
```

这告诉裁剪器：“`Create<MyClass>()` 这个调用一旦出现，`MyClass` 的公共构造函数必须保留。” 注解会顺着调用图反向传播到每个具体调用点。

如果是把 `Type` 直接当参数传的版本，注解就贴在参数上：

```csharp
public static object Create(
    [DynamicallyAccessedMembers(DynamicallyAccessedMemberTypes.PublicConstructors)] Type type)
{
    return Activator.CreateInstance(type)!;
}
```

## 例子二：给服务定位器加注解

按名字解析类型的服务定位器，是 AOT 路上最经典的一类坑：

```csharp
// ❌ 不安全：Type.GetType 和 Activator.CreateInstance 都是动态的
public static object Resolve(string typeName)
{
    var type = Type.GetType(typeName)
        ?? throw new InvalidOperationException($"Type not found: {typeName}");
    return Activator.CreateInstance(type)!;
}
```

`Type.GetType(string)` 是没法直接 trim-safe 的——裁剪器看不到字符串到底指哪个类型。两条可行路线：

**选项 A：用字典提前登记类型**

```csharp
private static readonly Dictionary<string, Type> _registry = new()
{
    ["EmailService"] = typeof(EmailService),
    ["SmsService"]   = typeof(SmsService),
};

public static object Resolve(string name)
{
    if (!_registry.TryGetValue(name, out var type))
        throw new KeyNotFoundException(name);

    return Activator.CreateInstance(type)!;
}
```

`typeof(EmailService)` 是裁剪器看得见的强引用，类型自然就被保留下来。

**选项 B：诚实地用 `[RequiresUnreferencedCode]` 标出去**

```csharp
[RequiresUnreferencedCode("This method uses Type.GetType and is not trim-safe.")]
public static object Resolve(string typeName)
{
    var type = Type.GetType(typeName)
        ?? throw new InvalidOperationException($"Type not found: {typeName}");
    return Activator.CreateInstance(type)!;
}
```

第二种没有“修好”动态行为，但把风险显式地传播到每个调用点——这就引出了下一个注解。

## `[RequiresUnreferencedCode]`：承认这段不能裁

某些反射场景就是没法注解。比如从用户给的路径加载插件、按配置文件解析类型——你在编译期根本不知道要保留什么。这时候 `[RequiresUnreferencedCode]` 是诚实做法：

```csharp
[RequiresUnreferencedCode("Loads plugin types from external assemblies. Not compatible with trimming.")]
public IEnumerable<IPlugin> LoadPlugins(string pluginDirectory)
{
    // ... 程序集加载与反射 ...
}
```

它做三件事：

1. 抑制方法体内的 `IL2xxx` 警告（你已经承认了风险）
2. 在每个调用点发出 `IL2026` 警告，强制调用方也显式选择继续走这条路
3. 用机器可读的方式记录意图

如果某个调用点你确定安全，可以再用 `[UnconditionalSuppressMessage]` 抑制：

```csharp
[UnconditionalSuppressMessage("Trimming", "IL2026",
    Justification = "PluginHost is only used in non-AOT deployments.")]
public void Initialize()
{
    var plugins = LoadPlugins(_config.PluginDirectory);
    // ...
}
```

`[UnconditionalSuppressMessage]` 要省着用。每一个抑制都是你在跟裁剪器签字：“这块我担保。”

## `[RequiresDynamicCode]`：表达式树与运行时 IL

AOT 不仅裁代码，还**禁止运行时生成 IL**。这会牵连：

- `System.Linq.Expressions.Expression.Compile()`
- `System.Reflection.Emit`（`DynamicMethod`、`AssemblyBuilder` 等）
- 在动态类型上用 `Delegate.CreateDelegate`
- 某些内部自己发射代码的序列化器 / 映射器

对应的注解是 `[RequiresDynamicCode]`：

```csharp
[RequiresDynamicCode("Compiles expression trees at runtime. Not compatible with Native AOT.")]
public static Func<T, TResult> BuildAccessor<T, TResult>(string propertyName)
{
    var param = Expression.Parameter(typeof(T), "x");
    var body  = Expression.Property(param, propertyName);
    var lambda = Expression.Lambda<Func<T, TResult>>(body, param);
    return lambda.Compile(); // 这一行需要运行时生成代码
}
```

在 .NET 10 里，类似场景的 AOT 友好路线，基本就是**源生成器**或者编译期代码生成（Roslyn 分析器）。

## 源生成器：长期答案

`[DynamicallyAccessedMembers]` 是创可贴：架构改不动时拿来止血。源生成器是治疗方案：把反射搬到编译期，直接产出裁剪器能看到的静态代码。

比如本来要在启动时扫所有 `IValidator<T>` 实现并注册，可以让源生成器在编译期发出一个登记方法，把每个实现一个个写死进去。读起来是“反射”，跑起来是普通调用。

记住一句话——**反射放到构建期，而不是运行期**。

## .NET 10 上的 AOT 兼容审计清单

下面这一份是按原文整理的核查动作，建议作为升级 / 改造时的检查表使用。

### 1. 打开裁剪器警告

先在项目里把分析器开起来，把所有 `IL2xxx` 修干净再去想 AOT：

```xml
<PropertyGroup>
  <EnableTrimAnalyzer>true</EnableTrimAnalyzer>
</PropertyGroup>
```

也可以直接走 AOT 分析：

```xml
<PropertyGroup>
  <EnableAotAnalyzer>true</EnableAotAnalyzer>
</PropertyGroup>
```

### 2. 把反射 API 全找出来

grep 这些调用模式，每一条都是潜在警告点：

- `Type.GetType(`
- `Assembly.GetType(`
- `Activator.CreateInstance(`
- `GetMethod(`、`GetProperty(`、`GetField(`
- `MethodInfo.Invoke(`
- `Expression.Compile(`
- `Emit.`

### 3. 让注解贯穿调用链

任何流入反射 API 的 `Type` 参数都需要 `[DynamicallyAccessedMembers]`。从反射调用点反向追踪，途中每个携带 `Type` 的方法、属性、字段都要注解。中间漏一段，警告会从那一段冒出来。

### 4. 用 `typeof()` 直接引用替换 `Type.GetType(string)`

能换就换。把“字符串 → 类型”改成“字符串 → `typeof(...)` 表”，既比反射快，也对裁剪器友好。

### 5. 真动态的代码用 `[RequiresUnreferencedCode]` 标清楚

别给自己一个安全错觉。先标出来，再决定是重构还是接受“这条路在 AOT 部署里不可用”。

### 6. 高频反射路径上评估源生成器

如果是序列化、对象映射这种每秒几千次的反射，源生成器既消掉性能开销，又顺手解决 AOT 兼容。

### 7. 真发布、真跑

警告干净不代表跑得起来。一定要真的发布一次再跑：

```bash
dotnet publish -r win-x64 --self-contained -p:PublishAot=true
```

把集成测试对着发布产物跑一遍。有些裁剪问题只在运行时暴露。

### 8. `rd.xml` 是最后退路

根描述文件可以兜住第三方库里那些没法在源码层注解的反射调用，但不要把它当首选。先把自己的代码注解干净，确实没办法再加 `rd.xml`，并把作用域写到最小，写清原因。

## 一些常见疑问

**`PublishTrimmed` 和 `PublishAot` 有什么区别？** `PublishTrimmed` 只是把 IL 裁剪应用到普通 .NET 运行时上，减小体积但仍然是 JIT。`PublishAot` 直接走 NativeAOT，编译成原生码并隐含裁剪，且不允许运行时生成 IL。在 .NET 10 里，对启动延迟敏感的场景一般直接奔着 `PublishAot`。

**`DynamicallyAccessedMemberTypes.All` 是不是能一键修好？** 它会让对应位置的警告消失，但同时强制所有传入类型保留全部成员，等于放弃了裁剪。短期止血可以，不要默认。

**乱抑制 `IL2026` 会怎样？** 编译过得去，运行时炸。常见症状是 `TypeNotFoundException`、`MissingMethodException`，或者 `GetMethod` 返回 `null` 引发的空引用。抑制是“我担保这条路径安全”的签字，不是消音器。

**第三方库还不支持 AOT 怎么办？** 几条路：升到带 AOT 注解的新版本（很多主流库在 .NET 8/9 已经补齐）；给作者提 issue 并在自己这边用 `[RequiresUnreferencedCode]` 标出来；换成 AOT 友好的替代（典型例子是用 `System.Text.Json` 替换 Newtonsoft.Json）；或者把 AOT 路径和插件 / interop 路径拆成两套发布配置。

**Native AOT 和依赖注入兼容吗？** 兼容。`Microsoft.Extensions.DependencyInjection` 从 .NET 8 起就 AOT 友好。关键是用 `AddSingleton<TInterface, TImplementation>()` 这种带具体类型参数的注册方式，让裁剪器静态看见类型。基于程序集扫描的自动注册需要走源生成器。

**是不是所有 .NET 10 应用都该上 AOT？** 不一定。Serverless、CLI、容器化微服务、移动 / 嵌入式这些对冷启动敏感的场景收益最大。长生命周期的 ASP.NET Core 服务，JIT 预热可以摊到几百万请求上，AOT 收益要权衡更严的约束、部分库的兼容性和更长的发布时间。先把依赖图盘清楚再决定。

## 写在最后

让 .NET 10 代码兼容 Native AOT，不是“别用反射”，而是要对裁剪器说清楚“我会用什么”。`[DynamicallyAccessedMembers]` 是精度工具，按需保留；`[RequiresUnreferencedCode]` 和 `[RequiresDynamicCode]` 是诚实标记，承认有些代码就是裁不动。长期方向是把反射搬到编译期——源生成器让你既有动态的写法，又没有运行时风险。新代码先按源生成器思路写，旧代码就跟着 `IL2xxx` 警告一条条过，每一条都对应一个明确动作。AOT 兼容性是一种日常纪律，等你把它放进开发流程，发布期的安全网才会一直干净。

如果你关注 AI 助手、开发工具和 .NET 软件工程实践，可以关注 Aide Hub，这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- 原文：[Making Reflection Native AOT Safe in .NET 10: DynamicallyAccessedMembers Guide](https://www.devleader.ca/2026/05/28/making-reflection-native-aot-safe-in-net-10-dynamicallyaccessedmembers-guide)
- 延伸：[Reflection in C#: 4 Simple But Powerful Code Examples](https://www.devleader.ca/2024/02/26/reflection-in-c-4-simple-but-powerful-code-examples)
- 延伸：[Activator.CreateInstance in C# - A Quick Rundown](https://www.devleader.ca/2024/02/28/activatorcreateinstance-in-c-a-quick-rundown)
- 延伸：[ConstructorInfo - How To Make Reflection in DotNet Faster for Instantiation](https://www.devleader.ca/2024/03/17/constructorinfo-how-to-make-reflection-in-dotnet-faster-for-instantiation)
