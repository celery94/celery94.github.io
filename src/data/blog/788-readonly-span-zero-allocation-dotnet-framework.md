---
pubDatetime: 2026-05-11T09:40:00+08:00
title: "用 ReadOnlySpan<byte> 替掉 byte[]：零分配技巧，.NET Framework 也能用"
description: "Andrew Lock 介绍了一个编译器级别的优化：把 static readonly byte[] 字段改为 static ReadOnlySpan<byte> 属性，编译器会把数据直接嵌入 PE 程序集的 metadata，彻底消除堆分配。这是编译器特性，与运行时无关，.NET Framework 配合 System.Memory 包同样受益。文章还详细说明了三个必须满足的前提，以及哪些写法会意外触发分配的坑。"
tags: ["C#", "dotnet", "Performance", "Span"]
slug: "readonly-span-zero-allocation-dotnet-framework"
ogImage: "../../assets/788/01-cover.png"
source: "https://andrewlock.net/removingbyte-array-allocations-in-dotnet-framework-using-readonlyspan-t/"
---

如果你写过性能敏感的 .NET 代码，`Span<T>` 和 `ReadOnlySpan<T>` 大概率已经是你工具箱里的常客。它们提供了一种在不复制数据的前提下操作内存片段的方式，既适用于字符串切片，也适用于栈上分配的临时缓冲区。

但 Andrew Lock 最近介绍的一个用法值得单独拿出来说：把 `static readonly byte[]` 字段改写成 `static ReadOnlySpan<byte>` 属性，可以让编译器把数组内容直接嵌入 PE 程序集的 metadata，访问时不产生任何堆分配。而且这是**编译器特性**，不依赖特定运行时版本——哪怕是 .NET Framework，加上 `System.Memory` NuGet 包就能用。

![用 ReadOnlySpan<byte> 替掉 byte[] 零分配技巧封面](../../assets/788/01-cover.png)

## 为什么 byte[] 字段有初始化成本

先看传统写法：

```csharp
public static class MyStaticData
{
    private static readonly byte[] ByteField = new byte[] { 1, 2, 3, 4 };
}
```

这没什么问题，`static readonly` 保证数组只创建一次。但"只创建一次"意味着在第一次访问这个类型时，运行时要在堆上分配这个数组对象、填充数据、然后保存到字段里。对于小数组，开销微乎其微；但如果有很多这类字段，积累下来的初始化成本和 GC 压力是真实存在的。

## 改写方式：属性而非字段

从 C# 8.0 开始，换一种写法：

```csharp
public static class MyStaticData
{
    // 原来
    private static readonly byte[] ByteField = new byte[] { 1, 2, 3, 4 };

    // 改为
    private static ReadOnlySpan<byte> ReadOnlySpanProp => new byte[] { 1, 2, 3, 4 };
}
```

第一眼看到这里，你可能会担心：这个属性每次被调用都会 `new` 一个数组出来，不是更糟吗？

答案是：**不会**。编译器认识这个模式，会做以下处理：

1. 把 `byte[]` 字面量的数据嵌入最终程序集的 metadata（即 PE image 里）
2. 属性被调用时，不创建数组，而是创建一个指向程序集内置数据的 `ReadOnlySpan<byte>`

这个 span 指向的数据既不在堆上，也不在栈上，而是在**已经加载进内存的程序集本身**里。零分配，零启动开销，GC 完全看不到它。

## IL 说话：验证优化确实发生了

原文用 .NET Framework 4.8（配合 `System.Memory` NuGet 包）编译了这段代码，然后用 Rider 查看生成的 IL：

```il
// get_ReadOnlySpanProp 方法
IL_0000: ldsflda  int32 '<PrivateImplementationDetails>'::'9F64A747...'
// ↑ 加载程序集内嵌的数据地址
IL_0005: ldc.i4.4
// ↑ 加载长度 4
IL_0006: newobj   instance void [System.Memory]System.ReadOnlySpan`1<unsigned int8>::.ctor(void*, int32)
// ↑ 用指针 + 长度构建 ReadOnlySpan，不是 newarr！
IL_000b: ret
```

关键是**看不到 `newarr` 和 `InitializeArray()`**。数据已经嵌在程序集里，属性调用只是把指针和长度包进一个 span 结构体返回，整个过程零分配。这在 .NET Framework 上同样验证通过。

UTF-8 字符串字面量也走同样的路子：

```csharp
private static ReadOnlySpan<byte> ReadOnlySpanUtf8 => "Hello world"u8;
```

## 三条必须遵守的前提

Andrew Lock 在文章里特别强调：这个优化有严格的适用条件，违反其中任何一条，代码还是能编译，但实际上会走低效甚至很糟糕的路径。

### 1. 只适用 byte、sbyte、bool

编译器只对**单字节类型**做这个优化，原因是多字节类型（比如 `int`）存储时使用小端格式，在运行时加载时可能需要处理字节序问题。

如果你写：

```csharp
// ⚠️ 使用 int 而不是 byte
private static ReadOnlySpan<int> ReadOnlySpanPropInt => new int[] { 1, 2, 3, 4 };
```

在 .NET Framework 和 .NET 7 以下，编译器会改为缓存策略：第一次访问时创建数组，缓存在隐藏的静态字段里，后续复用。有启动成本，但不像每次都分配那么糟。

.NET 7+ 引入了 `RuntimeHelpers.CreateSpan`，补全了多字节类型的运行时支持，可以在 .NET 7+ 上对 `int[]` 也做到零分配——但那是**运行时特性**，在旧框架上不可用。

### 2. 所有值必须是编译时常量

这是最容易踩的坑。下面这段代码能编译，但不管在哪个 .NET 版本，都会**每次调用都分配一个新数组**：

```csharp
public static class MyStaticData
{
    private static readonly byte One = 1; // 注意：这是 readonly，不是 const

    // ⚠️ 危险！每次调用属性都新建一个 byte[]
    private static ReadOnlySpan<byte> ReadOnlySpanPropNonConstant
        => new byte[] { One, 2, 3, 4 };
}
```

`One` 是 `static readonly` 字段，不是编译时常量（`const`），编译器无法把它嵌入程序集。IL 里会出现 `newarr` + `stelem`，意味着每次属性被访问都要在堆上建一个新数组。这比原来的 `static readonly byte[]` 还糟糕。

### 3. 必须用 ReadOnlySpan<T>，不能用 Span<T>

类似的坑：

```csharp
// ⚠️ 每次调用都分配新数组
private static Span<byte> SpanProp => new byte[] { 1, 2, 3, 4 };
```

因为 `Span<T>` 是可变的，编译器无法共享不可变数据的指针，只能每次新建数组。代码审查时很难发现，因为外观上和 `ReadOnlySpan<byte>` 版本几乎一样。

## 集合表达式：静态属性场景的安全网

C# 的集合表达式（collection expressions）在**静态属性**场景下能帮你捕捉上面的错误：

```csharp
// 以下两行均无法编译 → CS9203 错误（这正是我们想要的）
private static ReadOnlySpan<byte> Bad1 => [One, 2, 3, 4]; // 非常量，编译失败
private static Span<byte> Bad2 => [1, 2, 3, 4];           // Span<T>，编译失败
```

错误信息是 `CS9203: A collection expression of type 'ReadOnlySpan<byte>' cannot be used in this context because it may be exposed outside of the current scope.`

这个编译错误是"好的失败"，在代码审查之前就挡住了问题。

**注意**：这个保护只在**静态属性**场景生效。对于局部变量，集合表达式在 .NET Framework 和 .NET 7 及以下仍可能导致分配，不会在编译时报错：

```csharp
public static void TestData()
{
    // 这些在 .NET Framework 上都会分配！
    ReadOnlySpan<int> intArray = [1, 2, 3, 4];       // int 类型，需要 .NET 7+
    ReadOnlySpan<byte> nonConstantArray = [One, 2, 3, 4]; // 非常量，需要 .NET 8+
    Span<byte> spanArray = [1, 2, 3, 4];              // Span<T>，会分配
}
```

## 什么时候值得做这个改造

原文给出的判断思路：

- `byte[]`、`sbyte[]`、`bool[]` 的 `static readonly` 字段 → **直接改，有收益，兼容所有框架**
- `int[]` 等多字节类型 → 只在 .NET 7+ 有收益；如果还要兼容旧框架，考虑是否值得改
- 局部变量 → 收益场景更少见，通常考虑 `stackalloc` 更合适

集合表达式能在静态属性场景挡住非常量和 `Span<T>` 的错误，但不能在局部变量场景提供同样的保护。换言之，目前没有自动的保障机制能挡住所有边界情况。社区里有相关的 analyzer 提案（见参考链接），但截至目前尚未内置。

## 小结

这个技巧的本质：**C# 编译器在发现 `static ReadOnlySpan<byte> Prop => new byte[]{...}` 模式时，会把数组内容直接嵌入程序集，访问时只创建一个轻量的 span 结构体指向它**。零堆分配，零 GC 压力，而且和 .NET Framework 完全兼容（加 `System.Memory` 包即可）。

三个前提记牢：只用 `byte`/`sbyte`/`bool`，只用编译时常量，只用 `ReadOnlySpan<T>` 不用 `Span<T>`。在静态属性场景用集合表达式能帮你在编译期捕捉两类错误，但不能覆盖所有情况。

对于有大量静态只读字节数据（比如查表、常量掩码、UTF-8 路径）的库代码，这是一个值得做的改动。

## 参考

- [原文：Removing byte[] allocations in .NET Framework using ReadOnlySpan\<T\>](https://andrewlock.net/removingbyte-array-allocations-in-dotnet-framework-using-readonlyspan-t/)
- [System.Memory NuGet 包](https://www.nuget.org/packages/System.Memory)
- [UTF-8 字符串字面量（C# 11）](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/proposals/csharp-11.0/utf8-string-literals)
- [API Proposal: RuntimeHelpers.CreateSpan](https://github.com/dotnet/runtime/issues/60948)
- [Analyzer 提案：数组转 Span 的意外分配](https://github.com/dotnet/runtime/issues/69577)
- [ReadOnlySpan 从静态数据初始化的语言设计讨论](https://github.com/dotnet/csharplang/issues/5295)
