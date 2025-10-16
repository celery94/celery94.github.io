---
pubDatetime: 2025-09-11
tags: [".NET", "Performance"]
slug: net10-performance-improvements
source: https://devblogs.microsoft.com/dotnet/performance-improvements-in-net-10
title: .NET 10 性能改进：数百项优化带来的革命性提升
description: 深入解析 .NET 10 中的性能改进，涵盖 JIT 编译器优化、内存分配、边界检查、并发处理等多个方面的重大提升，为现代应用程序带来更快的执行速度和更高的效率。
---

# .NET 10 性能改进：数百项优化带来的革命性提升

.NET 10 的性能改进可以用一个生动的比喻来描述：就像19世纪冰雪王国的"冰王"Frederic Tudor，他通过系统性效率提升将原本风险极高的本地生意转变为可靠的全球贸易。Tudor 的成功并非源于一个突破性的大创意，而是来自大量小幅改进的复合效应——每个改进都放大了前一个的效果。

同样，软件开发中的重大性能飞跃很少来自单一的全面变更，而是来自数百或数千个有针对性的优化，这些优化复合起来产生变革性的效果。.NET 10 的性能故事不是关于某个迪士尼式的神奇想法，而是关于在这里谨慎削减几纳秒、在那里削减几十个字节，优化那些被执行万亿次的操作。

## JIT 编译器：核心优化引擎

在 .NET 的所有领域中，即时 (JIT) 编译器是最具影响力的组件之一。无论是小型控制台工具还是大规模企业服务，每个 .NET 应用程序最终都依赖 JIT 将中间语言 (IL) 代码转换为优化的机器代码。JIT 代码生成质量的任何提升都会产生涟漪效应，在整个生态系统中改善性能，而开发人员无需更改任何自己的代码甚至无需重新编译 C#。

### 抽象消除 (Deabstraction)

与许多语言一样，.NET 历史上存在"抽象开销"——在使用接口、迭代器和委托等高级语言特性时可能发生的额外分配和间接调用。每年，JIT 在优化抽象层方面越来越好，让开发人员能够编写简单的代码并仍然获得出色的性能。.NET 10 延续了这一传统，使得惯用的 C#（使用接口、`foreach` 循环、lambda 等）的运行速度更接近精心制作和手工调整代码的原始速度。

#### 对象栈分配

.NET 10 中抽象消除进展最令人兴奋的领域之一是扩展使用逃逸分析来启用对象的栈分配。逃逸分析是一种编译器技术，用于确定在方法中分配的对象是否逃逸该方法，即确定该对象在方法返回后是否可达（例如，通过存储在字段中或返回给调用者）或以运行时无法在方法内跟踪的方式使用（如传递给未知的被调用者）。

如果编译器可以证明对象不会逃逸，那么该对象的生命周期就受到方法的限制，它可以在栈上分配而不是在堆上分配。栈分配成本更低（仅仅是指针碰撞分配和方法退出时自动释放），并减少 GC 压力，因为对象不需要被 GC 跟踪。

.NET 9 已经引入了一些有限的逃逸分析和栈分配支持；.NET 10 将此功能显著扩展。JIT 现在能够对委托执行逃逸分析，特别是委托的 `Invoke` 方法不会藏匿 `this` 引用。如果逃逸分析可以证明委托的对象引用是其他没有逃逸的东西，委托就可以有效地消失。

### 边界检查优化

C# 是一种内存安全的语言，现代编程语言的一个重要组成部分。其关键组件是无法走出数组、字符串或跨度的开头或结尾。运行时确保任何此类无效尝试都会产生异常，而不是被允许执行无效的内存访问。

每个 .NET 版本都会找到并实现更多机会来避免那些以前生成的边界检查。.NET 10 延续了这一趋势。例如，现在 JIT 理解数学运算结果保证在边界内的情况。如果 `Log2` 的最大可能值在边界内，那么任何结果都保证在边界内。

### 虚拟化消除 (Devirtualization)

接口和虚拟方法是 .NET 和它所启用的抽象的关键方面。能够解开这些抽象并"去虚拟化"是 JIT 的一项重要工作，它在 .NET 10 中的能力有了显著飞跃。

虽然数组是 C# 和 .NET 提供的最核心特性之一，虽然 JIT 投入了大量精力并在优化数组的许多方面做得很好，但一个特定领域给它带来了痛苦：数组的接口实现。.NET 10 通过多个拉取请求解决了这个问题，使 JIT 能够对数组的接口方法实现进行去虚拟化。

这种改进的结果是，许多在 `ReadOnlyCollection<T>` 上使用 `foreach` 循环（通过其枚举器）与使用 `for` 循环（对每个元素进行索引）的性能比较中，现在更符合我们的预期，`for` 循环在 .NET 10 上是最快的。

## 性能优化实例

以下是一些具体的性能改进示例：

### 委托栈分配优化

在以下示例中，.NET 10 能够成功消除委托分配：

```csharp
public int Sum(int y)
{
    Func<int, int> addY = x => x + y;
    return DoubleResult(addY, y);
}

private int DoubleResult(Func<int, int> func, int arg)
{
    int result = func(arg);
    return result + result;
}
```

**性能对比：**
- .NET 9: 19.530 ns, 88 B 分配
- .NET 10: 6.685 ns, 24 B 分配（67% 性能提升，73% 内存减少）

### 数组栈分配

对于小型、本地使用的数组，.NET 10 现在可以将它们分配在栈上：

```csharp
public void Test()
{
    Process(new string[] { "a", "b", "c" });
}

static void Process(string[] inputs)
{
    foreach (string input in inputs)
    {
        Use(input);
    }
}
```

**性能对比：**
- .NET 9: 11.580 ns, 48 B 分配
- .NET 10: 3.960 ns, 0 B 分配（66% 性能提升，100% 内存减少）

### Stopwatch 优化

通过改进的内联和栈分配，现在可以零分配地使用 `Stopwatch`：

```csharp
public TimeSpan WithStartNew()
{
    Stopwatch sw = Stopwatch.StartNew();
    Nop();
    sw.Stop();
    return sw.Elapsed;
}
```

**性能对比：**
- .NET 9: 38.62 ns, 40 B 分配
- .NET 10: 28.21 ns, 0 B 分配（27% 性能提升，100% 内存减少）

## 序列化和文本处理

### System.Text.Json 改进

.NET 10 在 JSON 序列化方面有显著改进：

- **流式 Base64 编码**：新的 `WriteBase64StringSegment` 方法允许流式处理大型二进制数据，避免缓冲整个数据集
- **原始 UTF-8 访问**：`JsonMarshal.GetRawUtf8PropertyName` 方法提供对属性名称原始字节的访问
- **更好的错误处理**：改进的异常处理机制，提供更精确的错误信息

### 字符串插值优化

.NET 10 在字符串插值方面移除了各种空值检查，减少了插值操作的开销：

```csharp
public string Interpolate()
    => $"{_value} {_value} {_value} {_value}";
```

**性能对比：**
- .NET 9: 34.21 ns
- .NET 10: 29.47 ns（14% 性能提升）

## 密码学改进

.NET 10 大量投入后量子密码学 (PQC)，添加了对以下算法的支持：

- **ML-DSA**：NIST PQC 数字签名算法
- **Composite ML-DSA**：结合 ML-DSA 和经典加密算法的签名
- **SLH-DSA**：另一个 NIST PQC 签名算法
- **ML-KEM**：NIST PQC 密钥封装算法

在 OpenSSL 3.x 平台上，通过显式获取和缓存摘要实现来优化加密哈希操作：

```csharp
public void Hash()
    => SHA256.HashData(_src, _dst);
```

**性能对比（Linux/OpenSSL）：**
- .NET 9: 1,206.8 ns
- .NET 10: 960.6 ns（20% 性能提升）

## 其他性能改进

### 垃圾收集器优化

- **DATAS 调优**：改进动态适应应用程序大小的行为，减少不必要的收集，平滑暂停
- **新型 GC 句柄**：引入 `GCHandle<T>`、`PinnedGCHandle<T>` 和 `WeakGCHandle<T>`，减少开销

### Mono 解释器改进

- 为多个操作码添加了优化支持，包括开关、新数组和内存屏障
- 启用了更多 WebAssembly 操作的向量化，包括移位操作和各种数学函数

### 字符串和格式化

- `Type.AssemblyQualifiedName` 现在被缓存，避免重复计算
- 十六进制转换方法现在支持 UTF-8
- `DefaultInterpolatedStringHandler` 添加了 `Text` 属性以访问格式化文本

## 性能测试环境

所有基准测试都使用 BenchmarkDotNet 0.15.2 进行，在 Linux (Ubuntu 24.04.1) x64 处理器上运行。要复现这些结果，需要安装 .NET 9 和 .NET 10，并使用以下项目配置：

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFrameworks>net10.0;net9.0</TargetFrameworks>
    <LangVersion>Preview</LangVersion>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <ServerGarbageCollection>true</ServerGarbageCollection>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="BenchmarkDotNet" Version="0.15.2" />
  </ItemGroup>
</Project>
```

## 总结

.NET 10 的性能改进体现了微软对开发者体验和应用程序性能的持续承诺。通过数百个针对性优化的复合效应，.NET 10 为现实世界的应用程序提供了实质性的性能优势，无论是高吞吐量服务、交互式桌面应用程序还是资源受限的移动体验。

这些改进的最佳体验方式是亲自尝试 .NET 10 RC1。下载它，运行你的工作负载，测量影响，并分享你的体验。性能的提升不仅体现在基准测试中，更重要的是让真实应用程序更加响应、可扩展、可持续、经济，并最终让构建和使用变得更愉快。

就像 Tudor 的冰块能够在四个月的航行后到达加尔各答一样，.NET 10 的性能改进使以前不可想象的应用程序性能变为可能。这不是魔法，而是工程卓越的体现。