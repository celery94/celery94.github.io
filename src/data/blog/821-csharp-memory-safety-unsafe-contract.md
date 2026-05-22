---
pubDatetime: 2026-05-22T07:57:31+08:00
title: "C# 16 的 unsafe 要变成可审查的安全契约"
description: "Microsoft 正在改进 C# 的内存安全模型，计划让 unsafe 从指针语法标记扩展成可传播、可记录、可审查的调用方契约。新模型预计在 .NET 11 预览，在 .NET 12 进入生产发布。"
tags: ["CSharp", "DotNet", "内存安全", "语言设计"]
slug: "csharp-memory-safety-unsafe-contract"
ogImage: "../../assets/821/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/improving-csharp-memory-safety/"
---

Microsoft .NET 团队正在推进一项 C# 内存安全改进。核心变化是重新设计 `unsafe`：它不再只表示“这里可以用指针相关语法”，还要告诉调用方这里有安全义务需要满足。

这项工作名义上属于 C# 16，计划在 .NET 11 以预览形式发布，在 .NET 12 进入生产发布。早期编译器实现已经进入 Roslyn 主线。新模型一开始是 opt-in，也就是项目主动开启，后续可能成为默认行为。

## 背景

C# 本身已经有很强的安全基础。普通 safe code 里，变量要么引用活对象，要么是 `null`，要么已经离开作用域；新对象默认初始化；数组越界会抛出 `IndexOutOfRangeException`，不会读到未定义内存。

问题主要集中在 unsafe code。写 unsafe code 通常有两个原因：和 native code 互操作，或在少数场景里追求性能。这里编译器无法完全证明内存访问是否安全，责任就转移给开发者。

原文把核心不变量说得很清楚：每次内存访问都必须指向 live memory，也就是已经分配、已经初始化、访问时仍然可用的内存。读写任意内存会导致 Undefined Behavior，简称 UB，也是很多安全漏洞的来源。

## 旧模型的问题

C# 1.0 引入 `unsafe` 时，它主要用来建立 unsafe context。你可以把它放在类型、方法或方法内部 block 上。一旦进入这个 context，就可以使用指针声明、指针解引用、取地址、`stackalloc` 等能力。

这个模型能阻止普通 safe code 误用指针，但它对调用方契约表达不够清楚。比如一个方法内部调用了 `System.Runtime.CompilerServices.Unsafe` 或 `Marshal`，很多约束只能靠约定和注释传递。调用者看到方法签名时，不一定知道自己需要保证什么。

新模型想解决的就是这个问题：让不安全操作、调用方义务、边界处的验证理由都变得清楚。

## 新模型的四层

原文把新模型拆成四层。

第一层是内部 `unsafe { }` block。每个 unsafe 操作都要出现在局部 block 里，比如调用 unsafe member 或解引用指针。这样代码审查时能直接看到不安全操作在哪里。

第二层是传播。方法签名上加 `unsafe`，表示这个方法把内部 block 的义务继续发布给自己的调用方。换句话说，调用方在调用它时也要处理这份安全契约。

第三层是安全文档。每个 unsafe member 都应该带 `/// <safety>` 文档块，说明调用方要满足什么条件。分析器可以提示缺失的安全文档。

第四层是边界 suppression。一个方法内部可以有 `unsafe` block，但方法签名不标 `unsafe`。这表示它在边界处已经处理了下游 unsafe API 的义务，例如通过输入检查、静态推理或上游 API 保证，把不安全细节封在方法内部。

这套机制的价值在于形成一条能审查的推理链。谁制造了义务，谁传播了义务，谁在边界处处理了义务，都能在代码里看出来。

## 一个例子

原文用 `Encoding.GetString(byte*, int)` 举例。这个 API 接收一个 `byte*` 和一个长度：

```csharp
public unsafe string GetString(byte* bytes, int byteCount)
{
    ArgumentNullException.ThrowIfNull(bytes);

    ArgumentOutOfRangeException.ThrowIfNegative(byteCount);

    return string.CreateStringFromEncoding(bytes, byteCount, this);
}
```

这个签名表达了一个原始 buffer 和它的长度。方法体能检查空指针和负数长度，也能返回新的 `string`，从而消除 buffer 生命周期和别名问题。

但还有一件事它无法检查：从 `bytes` 开始的 `byteCount` 个字节必须真的可读。如果调用方传入的长度超过 buffer，decoder 可能读到不该读的内存。这就是调用方义务，适合写进 `/// <safety>`。

## 和 C# 1.0 的差异

新模型相对旧规则有几处重要变化。

`unsafe` 类型修饰符会报错。unsafe 作用域会下移到方法、属性和字段，让契约离具体声明更近。

`unsafe` 不能放在 static constructor 或 finalizer 上，因为它们没有普通调用点，也就没有可以传播义务的位置。

`new()` 泛型约束只匹配 safe 的无参构造函数。如果某个类型的无参构造函数是 `unsafe`，它不能满足 `new()`。

新增 `safe` 关键字，用在编译器要求开发者显式选择的地方。原文提到当前主要是 `extern` 声明，包括 `LibraryImport` partial method，需要标记为 `safe` 或 `unsafe`。

方法签名上的指针类型本身不再自动传播 unsafe。真正 unsafe 的是指针解引用。也就是说，`byte*` 参数本身不会自动让调用方 unsafe，解引用或调用 unsafe member 才会触发相关规则。

## 项目级开关

新模型有两个项目级开关。

第一个是新的 opt-in 属性，正式名称会随 .NET 11 preview 落定。它决定是否使用新的 caller-unsafe 规则，也就是“什么算 unsafe”和“unsafe 如何传播”。

第二个是现有的 `<AllowUnsafeBlocks>`。它决定项目里是否允许 unsafe code。默认 `false` 时，编译器会拒绝 unsafe code。

这两者解决的问题不同。一个改变模型，一个控制是否允许 unsafe。原文特别强调，对 AI 生成代码来说，这一点很有用：如果项目没有打开 `AllowUnsafeBlocks=true`，编译器会直接拒绝 unsafe code。用编译错误拦住问题，比靠 code review 逐行找更可靠。

## 对 AI 生成代码的影响

原文把 AI 辅助开发也纳入讨论。AI 可以更快生成代码，软件生产速度上升后，人类审查压力也会变大。内存安全边界如果只靠约定，很容易漏掉。

新模型能把 unsafe 使用压缩到更明确的语法范围里。agent 生成代码时，如果调用 unsafe API，就要么向上传播 `unsafe`，要么在边界处用 guard 处理义务。`/// <safety>` 文档也能成为 API 级说明，告诉人类 reviewer 或代码审查 agent 应该检查什么。

当然，这不代表编译器能证明所有 unsafe code 正确。编译器可以要求边界和契约存在，但具体 guard 是否充分，仍然需要开发者理解和审查。

原文也指出 agent 可能绕开模型，比如把项目切回旧模型，或打开 `AllowUnsafeBlocks`。这类项目属性应该被 CI 和 review 明确保护，就像团队会保护 `TreatWarningsAsErrors` 一样。

## 迁移时怎么理解

这套变化会影响已有 unsafe code。迁移不是简单替换关键字，更像给 unsafe 代码补上结构化边界。

可以按这个顺序理解：

1. 找到所有 unsafe 操作，把它们收进局部 `unsafe { }` block。
2. 判断义务应该向调用方传播，还是在当前方法边界处处理。
3. 需要传播时，在 member 签名上标 `unsafe`，并写 `/// <safety>`。
4. 需要封住时，在方法内部加 guard，并用 `// SAFETY:` 说明这个 unsafe 操作依赖什么条件。
5. 检查项目级开关，避免无意间放宽 unsafe 使用。

原文提到 runtime 代码库里会逐步把 `Unsafe` 和 `Marshal` 相关 member 用新模型标注起来。这样 API 的不安全义务会更容易被调用者看见。

## 为什么这件事重要

内存安全这几年一直是行业和政府关注点。C#、Rust、Swift 都在试图保留低层能力，同时让不安全部分更明确。

C# 的方向比较务实：safe code 继续保持普通开发体验；需要 unsafe 的地方，用更严格的边界、传播和文档让风险可见。对大多数不启用 unsafe API 的开发者来说，开启新模型可能没有明显变化。对维护 runtime、interop、cryptography、high performance 代码的人来说，这会让审查工作更有结构。

这次变化的重点在于让 unsafe 更容易被看懂、被追踪、被审查。

## 参考

- [Improving C# Memory Safety](https://devblogs.microsoft.com/dotnet/improving-csharp-memory-safety/)
- [dotnet/runtime issue: Improving C# memory safety](https://github.com/dotnet/runtime/issues/125800)
- [C# caller-unsafe design note](https://github.com/dotnet/designs/blob/main/accepted/2025/memory-safety/caller-unsafe.md)
- [CISA: Memory Safe Languages](https://www.cisa.gov/resources-tools/resources/memory-safe-languages-reducing-vulnerabilities-modern-software-development)
