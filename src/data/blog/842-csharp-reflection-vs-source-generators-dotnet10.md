---
pubDatetime: 2026-05-29T08:09:11+08:00
title: "Reflection vs Source Generators：.NET 10 里选谁，看你什么时候知道类型"
description: ".NET 10 里给框架级代码做类型扫描，反射和源生成器是两套答案。前者在运行时灵活但有开销、对 AOT 不友好，后者在编译期生成真实 C# 代码、零运行时开销且 AOT 友好。文章按 Dev Leader 的对比把两者并排过一遍，给出选型清单和混合用法。"
tags: ["C#", ".NET", ".NET 10", "Source Generators", "Reflection"]
slug: "csharp-reflection-vs-source-generators-dotnet10"
ogImage: "../../assets/842/01-cover.png"
source: "https://www.devleader.ca/2026/05/27/c-reflection-vs-source-generators-in-net-10-which-should-you-choose"
---

![运行时反射与编译期源生成器对照，中下连接桥提示混合策略](../../assets/842/01-cover.png)

写 .NET 框架级代码的人最后都要回答同一个问题：要按类型做不同行为，是用 `System.Reflection` 在运行时去翻元数据，还是用源生成器在编译期把代码先写出来？.NET 10 时代，这个选择关系到性能、AOT 兼容性、调试体验，甚至你能不能上 NativeAOT。Dev Leader 的这篇对比把两条路按维度并排放在一起。本文按原文的展开方式梳理一遍，并把关键代码完整保留。

## 两个工具解决的是同一类问题

反射和源生成器都在回答“怎么写出能针对不同类型表现不同行为的代码”，但它们工作在程序生命周期的不同阶段：

- **反射**：运行时读取已经编译进程序集的元数据
- **源生成器**：编译期接收源码的语法树和语义模型，发出新的 C# 源文件，跟你的代码一起被编译

阶段不同，后续的性能、AOT、可调试性、动态能力会一连串受影响。下面按 Dev Leader 给的顺序走完整套对比。

## 反射在做什么

反射给你的是**运行时访问程序集元数据的能力**。每个类名、属性类型、方法签名、特性都会进到元数据表，`System.Reflection` 让你在程序运行时去读、去操作。

常见用法：

```csharp
// Inspect type structure
Type type = typeof(OrderService);
PropertyInfo[] props = type.GetProperties();
MethodInfo[]   methods = type.GetMethods();
ConstructorInfo[] ctors = type.GetConstructors();

// Read and write property values dynamically
PropertyInfo prop = type.GetProperty("Status")!;
prop.SetValue(orderInstance, OrderStatus.Shipped);
object? value = prop.GetValue(orderInstance);

// Create instances without knowing the type at compile time
Type? serviceType = Type.GetType("MyApp.Services.OrderService, MyApp");
object instance = Activator.CreateInstance(serviceType!)!;

// Invoke methods by name
MethodInfo method = type.GetMethod("Process")!;
method.Invoke(instance, new object[] { orderId });
```

反射真正不可替代的特征是这一条：

> 它在运行时工作，处理编译时可能根本不存在的信息。

所以它能从磁盘加载一个程序集、扫出里面的类型并立刻使用——不需要你的代码事先知道这些类型存在。插件系统、脚本引擎、各种“开放式类型发现”的场景，本质都靠这个特征。

## 源生成器在做什么

源生成器是**带写权限的 Roslyn 分析器**：编译期运行，接收源码的语法树和语义模型，能产生额外的 C# 源文件一起被编译。

一个最直观的例子——给所有标了 `[GenerateSerializer]` 的类生成一个 `ToJson()`：

```csharp
// Your code -- just attribute marking, no implementation
[GenerateSerializer]
public sealed class Order
{
    public int Id { get; set; }
    public string CustomerName { get; set; } = "";
    public decimal Total { get; set; }
}

// What the source generator emits into your compilation (you never write this)
// Order.Generated.cs
partial class Order
{
    public string ToJson()
    {
        return $"{{\"Id\":{Id},\"CustomerName\":\"{CustomerName}\",\"Total\":{Total}}}";
    }
}
```

生成出来的就是普通 C# 代码：编译器照样看见、照样 JIT 或 AOT 编译。运行时**根本没有“生成器”这套东西在跑**——只剩生成器写出来后再被编译的代码。

代价是：源生成器**看不到不在当前编译里的类型**。它能看见你的项目源码和所有传递引用，但看不见运行时才会加载进来的插件，也看不见某个字符串拼出来的类型名。

## 一张对比表

把两者按维度过一遍，差距集中在这几个点上：

| 特性                       | 反射                         | 源生成器                                      |
| -------------------------- | ---------------------------- | --------------------------------------------- |
| 运行阶段                   | 运行时                       | 编译期                                        |
| 单次调用性能               | 有调用开销（可缓存）         | 零运行时开销                                  |
| AOT / NativeAOT 支持       | 有限——动态调用会破坏 trimmer | 完整——生成代码可被静态分析                    |
| 处理“运行时才能确定的类型” | 支持                         | 不支持                                        |
| 调试                       | 运行时反射查看               | 普通调试器，生成文件在 IDE 里可见             |
| 错误反馈                   | 运行时异常                   | 编译期错误和警告                              |
| 代码复杂度                 | 中——API 熟悉                 | 高——要懂 Roslyn API                           |
| IDE 对生成代码的支持       | 无                           | 生成成员有完整 IntelliSense                   |
| 启动开销                   | 启动时读元数据               | 无（已经编译完）                              |
| 增量构建                   | 无                           | 有（`IIncrementalGenerator`）                 |
| 对 `sealed` 类型           | 可用                         | 可用                                          |
| 对私有成员                 | 可用（加 flag）              | 受限——默认无法跨程序集访问真正的 private 成员 |
| 适合插件/动态加载          | 可以                         | 不可以                                        |

## 什么时候选反射

判断标准只有一个：**类型集合在编译期不能完整确定**。

- **插件和扩展系统**：从某个目录加载 `.dll`，里面的类型在你编译时根本不存在；只有反射能发现并实例化它们。源生成器在这里帮不上忙
- **通用框架库**：发布给别人用的库（比如 NuGet 包），要能处理用户定义的任意类型——除非用户主动把生成器拉进自己的编译，否则你写的生成器跑不到他们的项目里
- **原型和探索型工具**：CLI 工具、测试 harness、admin 控制台需要内省一个正在跑的应用；这些场景里反射的开销可以忽略，灵活性才是要点
- **测试框架**：xUnit、NUnit、MSTest 都是按约定和特性用反射去发现测试类和方法，本质就是“运行时发现用户类型”
- **动态代理生成**：Castle DynamicProxy（Moq 内部用的）这种通过 `System.Reflection.Emit` 在运行时合成新代理类型，源生成器做不了——代理类型在编译期根本不存在

## 什么时候选源生成器

判断标准也只有一个：**要处理的类型集合在编译期已经全部已知，并且想要零运行时开销**。

- **JSON 序列化**：`System.Text.Json` 配合源生成器是范式级例子。`[JsonSerializable(typeof(MyType))]` 标好，生成器输出一个 `JsonSerializerContext` 子类，里面是为每个类型量身编出来的序列化/反序列化代码。没有运行时反射、没有启动开销、AOT 完全兼容；反射版本则会在首次使用时检视类型，长期是 AOT 场景下 trimmer 警告的常客
- **依赖注入注册**：业务应用的服务类型几乎都在编译期已知（极少有真要加载外部插件的）。源生成器可以把 `services.Add*()` 调用全部直接发出来，把启动期的反射扫描整段去掉。`Needlr` 就是冲这个价值点设计的
- **已知模式的样板代码**：仓储都长同一种接口、事件处理器都是同一种签名……这种地方让生成器按属性或命名约定一次发完，强类型、IDE 可见、运行时零开销
- **强类型资源访问、日志、映射**：`.NET` 内置的 `[LoggerMessage]` 就用源生成器生成优化过的日志调用。`Mapperly` 等映射库走的是同一条路

## 范式对照：`System.Text.Json`

反射和源生成器的取舍，在 `System.Text.Json` 上最直观：

```csharp
// Reflection-based -- convenient, but has startup cost and AOT warnings
var json = JsonSerializer.Serialize(myOrder);
var order = JsonSerializer.Deserialize<Order>(json);

// Source generator approach -- zero runtime reflection
[JsonSourceGenerationOptions(WriteIndented = true)]
[JsonSerializable(typeof(Order))]
[JsonSerializable(typeof(List<Order>))]
internal partial class AppJsonContext : JsonSerializerContext { }

// Usage -- compiled, AOT-safe, fast
var json = JsonSerializer.Serialize(myOrder, AppJsonContext.Default.Order);
var order = JsonSerializer.Deserialize(json, AppJsonContext.Default.Order);
```

源生成器版本：

- 编译期就发出每种类型对应的序列化逻辑
- 运行时没有反射调用
- NativeAOT trim 不出警告
- 生成的代码在 Solution Explorer 的 `Analyzers` 节点下能直接看到

反射版本写起来更省事，但代价是持续的运行时开销和 AOT 不兼容。.NET 10 里 `System.Text.Json` 的源生成器已经成熟到能覆盖几乎所有真实场景，反射版本基本只在原型阶段还有意义。

## 案例：Needlr 的取舍

Needlr 是一个 DI 注册库，把“类型发现”这件事从反射切到了源生成器，正好把这条权衡说清楚。

最初的反射方案在启动时用 `Assembly.GetTypes()` 扫所有程序集、再按特性找出要注册的服务。它能跑，但有两个问题：

- 启动延迟随被扫类型数线性增长
- 不兼容 AOT——trimmer 看不到哪些类型会通过 `GetTypes()` 被访问，可能把它们裁掉

源生成器方案换了根本模型：生成器在编译期跑，找出所有标了 `[AutoRegister]` 或符合命名约定的类型，发出一个注册方法，里面是显式的 `services.AddTransient<IMyService, MyService>()` 调用。启动时应用调用这个生成方法——没有反射、没有扫描、没有 AOT 问题。

## 混合策略：启动期用反射，热路径用源生成器

生产中的 .NET 10 应用更多是两者一起用：

- **源生成器**负责高频、编译期已知的路径：序列化、DI 注册、日志、映射
- **反射**负责低频、运行时动态的路径：插件加载、admin 工具、诊断接口

边界大致是：每个请求或每次热循环都要走的代码，把反射从里面拿掉；只有启动时跑一次或偶尔被 admin 触发的代码，反射放心用。

一个插件化应用里典型的混合写法：

```csharp
// Startup: reflection for plugin discovery (runs once)
var pluginTypes = pluginAssembly
    .GetTypes()
    .Where(t => typeof(IPlugin).IsAssignableFrom(t) && !t.IsAbstract);

foreach (var pluginType in pluginTypes)
{
    // Register each discovered plugin type
    services.AddSingleton(typeof(IPlugin), pluginType);
}

// Compile: source generator handles core application services
// (generated by Needlr or similar -- no startup reflection here)
services.AddGeneratedServices(); // auto-generated method

// Runtime: both paths converge -- DI resolves everything the same way
var plugins = serviceProvider.GetServices<IPlugin>();
```

启动期为插件付一次反射成本，主体注册走源生成器；运行时所有解析都过同一套已编译的 DI call site。

## 从反射迁移到源生成器的路径

把现有反射方案迁过来最好分步走：

1. **找出反射热点**：用 profiler 或在启动代码里加计时，找出真正主导启动时间或热路径执行时间的反射调用
2. **判断是否编译期已知**：对每个热点问一句——“源生成器能不能在编译期就知道要处理哪些类型？”能的话，迁移可行
3. **写源生成器**：Roslyn 源生成器 API 有学习曲线；`IIncrementalGenerator`（.NET 6+）是合适的起点。生成器读语法树和语义模型，找到目标类型，发出注册/初始化代码
4. **先两路并行**：把源生成器的产物和原反射代码并存，验证两边输出一致；确认无误再把反射路径删掉
5. **更新测试**：那些通过 mock 或拦截反射调用做断言的测试要改成直接调用生成代码

迁移工程量不小，但收益通常很显眼：启动更快、AOT 兼容、trimmer 输出更干净、错误反馈从运行时挪到编译期。

## .NET 10 下的 AOT 兼容性

NativeAOT 在 .NET 10 越来越主流：把应用编译成自包含的原生二进制，没有 JIT、没有 MSIL、运行时极薄。性能和部署收益很大，但兼容性约束很严格。

反射在 AOT 下能做的事很有限：

- 读取元数据可以（要写 trimmer 标注）
- 动态调用（`MethodInfo.Invoke`、用字符串的 `Activator.CreateInstance`、`Expression.Compile`）要么被限制、要么直接没了
- trimmer 会按静态分析积极裁剪没被引用到的成员；通过反射动态发现的类型如果没标 `[DynamicallyAccessedMembers]`，可能被悄悄裁掉

源生成器按设计就 AOT 兼容——它发出的是真实的 C# 代码，静态分析能看见，trimmer 能正确跟踪。**如果 AOT 在你的 .NET 10 路线图里，源生成器就不只是优选，常常是必备。**

## FAQ

**反射和源生成器在 C# 里的核心差别是什么？**

反射在运行时检视已编译程序集的元数据；源生成器在编译期发出额外的 C# 源码，跟你的项目一起被编译。反射能处理任何类型，包括动态加载进来的；源生成器只看得到当前编译里的类型，但运行时零开销。

**在 .NET 10 下源生成器是不是一定更快？**

热路径上是的——生成代码没有运行时反射开销。但源生成器编译会增加构建时间；很大的代码库里生成文件多了之后，构建时间会明显增长。运行时收益基本能覆盖构建期成本，但极大工程值得自己测一遍。

**同一个项目里能不能两个一起用？**

能，而且这是推荐做法。高频、编译期已知的路径用源生成器（序列化、DI 注册、日志），低频或真正动态的路径用反射（插件加载、admin 工具、诊断内省）。

**源生成器和 NativeAOT 兼容吗？**

兼容，它本来就是写 AOT 友好代码的主力工具之一。生成器发出真实 C# 代码，trimmer 能静态分析、确认哪些类型在用；而反射的动态调用会让类型被裁掉，进而在 NativeAOT 下运行时失败。

**`System.Text.Json` 用源生成器会更快吗？**

会，而且差距可测。生成版本的 `JsonSerializerContext` 完全跳过运行时类型检视，对启动敏感的应用和高吞吐 API 差距明显。.NET 10 下，新项目推荐默认走源生成器路径，也是因为它兼容 AOT。

**什么时候不应该用源生成器？**

需要处理的类型在编译期未知就别用——比如加载外部程序集的插件系统、和任意用户类型打交道的通用库、需要内省运行中应用的工具。还有那种偶发、小量的操作，用 Roslyn 写一个生成器不值当。

**如何在 .NET 10 下上手写源生成器？**

新建一个目标 `netstandard2.0` 的类库（源生成器分析器程序集的常见兼容目标），引用 `Microsoft.CodeAnalysis.CSharp`，实现 `IIncrementalGenerator` 并加 `[Generator]`。最顺手的入口是 `SyntaxProvider.ForAttributeWithMetadataName`，专门找标了某个特性的类型。Microsoft 文档和 `dotnet/roslyn-sdk` 仓库里的 samples 是当前 API 最准的参考。

## 一句话总结

反射和源生成器在回答同一个问题：你**什么时候**才能知道要处理哪些类型？

- 编译期就知道——多数业务应用就是这种——优先选源生成器；零运行时开销、AOT 兼容、编译期就能拿到错误反馈，外加更好的 IDE 支持
- 只有运行时才能知道——插件、动态加载、通用框架库——继续用反射；配合“反射一次、永久缓存”的写法，依然实用
- 大部分 .NET 10 应用最终是混合：90% 编译期已知走源生成器，10% 真动态留给反射

理解两者的边界，比凭习惯固定选一个更值得花时间。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- 原文：[C# Reflection vs Source Generators in .NET 10: Which Should You Choose?](https://www.devleader.ca/2026/05/27/c-reflection-vs-source-generators-in-net-10-which-should-you-choose)
- [C# Source Generators: A Complete Guide to Compile-Time Code Generation](https://www.devleader.ca/2026/03/16/c-source-generators-a-complete-guide-to-compile-time-code-generation)
- [Source Generation vs Reflection in Needlr](https://www.devleader.ca/2026/02/07/source-generation-vs-reflection-in-needlr-choosing-the-right-approach)
- [Plugin Architecture in C#: The Complete Guide to Extensible .NET Applications](https://www.devleader.ca/2026/04/07/plugin-architecture-in-c-the-complete-guide-to-extensible-net-applications)
