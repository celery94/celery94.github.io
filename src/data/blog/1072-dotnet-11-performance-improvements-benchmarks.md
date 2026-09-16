---
pubDatetime: 2026-09-16T07:46:00+08:00
title: ".NET 11 性能改进：从 JIT 到类库的基准数据"
description: "微软 .NET 11 性能长文覆盖数百项改进。本文把它压成一张可决策的地图：JIT 与运行时的主线、类库中最值得关注的数字，以及运行时异步开关和硬件基线提高这两条真实门槛。"
tags: [".NET", ".NET 11", "性能优化", "JIT", "基准测试"]
slug: "dotnet-11-performance-improvements-benchmarks"
ogImage: "../../assets/1072/01-cover.jpg"
source: "https://devblogs.microsoft.com/dotnet/performance-improvements-in-net-11"
---

上游刚发布了一篇性能长文，列出几百项改进。作为读者，你真正要回答的是三个问题：**哪些收益不用改代码就能拿到？哪些必须显式打开开关？升级之前会撞到什么门槛？**

微软的 Stephen Toub 在 [Performance Improvements in .NET 11](https://devblogs.microsoft.com/dotnet/performance-improvements-in-net-11) 里按 JIT、启动、线程、数值、全球化、字符串、集合与 LINQ、I/O、网络、JSON、诊断、密码学逐节走了一遍，正文约 37 万字符，开篇借 Spinal Tap 那句「这些旋钮到 11」当作题眼：不是某一项魔法，而是一年攒下来的几百项小改动，每一项都在把整体推高一格。

下面不做逐节翻译。我按上面那三个问题把原文重新组织了一遍：先交代版本前提和两条门槛（这两块最容易在升级时踩到），再讲不用改代码的那一层，最后按影响面挑出类库里最值得你自己复测的几处。

## 先看清版本前提

在讨论任何百分比之前，有三件事需要先确定：

- **.NET 11 是 STS（标准期限支持）版本**：2026 年 11 月 10 日 GA，支持到 2028 年 11 月 9 日。当前 .NET 10 是 LTS，支持到 2028 年 11 月 14 日。也就是说升到 11 并不会缩短支持窗口，但也没有延长——如果不想每年跟版本，留在 .NET 10 LTS 是完全合理的选择。
- **文中的数字来自 RC1，不是 GA**：原文基准项目的 `net11.0` 目标固定到 `11.0.0-rc.1.26425.128`，对照组是 .NET 10 的最新补丁 `10.0.12`。写这篇时最新发布是 2026 年 9 月 8 日的 11.0.0-rc.1。
- **全部是微基准**：原文自己就提醒了，很多操作短到眨眼都来不及，结果会随硬件、操作系统、运行时配置和机器当时的负载变化。它的用途是解释「为什么快了」，不是给你一个可以照抄的性能预期。

## 门槛一：硬件基线提高了

这是最容易被忽略、后果又最硬的一条。.NET 11 更新了最低硬件要求：

| 平台                    | JIT/AOT 基线（原来 → 现在）     | ReadyToRun 目标（原来 → 现在） |
| ----------------------- | ------------------------------- | ------------------------------ |
| Windows / Linux x86/x64 | x86-64-v1 → **x86-64-v2**       | x86-64-v2 → **x86-64-v3**      |
| Windows Arm64           | armv8.0-a → **armv8.0-a + LSE** | armv8.0-a → armv8.2-a + RCPC   |
| Linux Arm64             | armv8.0-a（不变）               | armv8.0-a → armv8.0-a + LSE    |
| Apple（Arm64 与 x64）   | 不变                            | 不变                           |

x86-64-v2 意味着除了原有的 CMOV、CX8、SSE、SSE2，还要求 CX16、POPCNT、SSE3、SSSE3、SSE4.1、SSE4.2。这些指令集在 Windows 11 和 Windows 10 官方支持的 CPU 上本来就有，最后一次被淘汰的老芯片大约止于 2013 年——但如果你有仍然在服役的老服务器或者工控机，它就是硬门槛。

后果不是变慢，而是**跑不起来**：

```text
The current CPU is missing one or more of the baseline instruction sets.
```

这条改动也解释了一个常见疑问：为什么有些内建函数改进可以无条件应用。基线抬高之后，JIT 可以把一批指令集当作「一定有」来生成代码，不必再逐处做运行时探测。

## 门槛二：运行时异步还在预览开关后面

原文的 JIT 章节里，「Runtime Async」是最容易被误读的一节。

变更本身很大：过去是 C# 编译器为每个 `async` 方法生成状态机类，现在这件事交给 JIT 和运行时做——运行时自己跟踪异步执行，编译器不再生成状态机。收益是可测的（同一运行时内的 A/B 对比）：

| 场景              | 编译器状态机      | 运行时异步     | 比值 |
| ----------------- | ----------------- | -------------- | ---- |
| 同步完成的链      | 21.221 ns / 144 B | 6.151 ns / 0 B | 0.29 |
| 深度 10、无 yield | 19.469 μs         | 5.885 μs       | 0.30 |
| 二进制体积        | 10,752 B          | 5,632 B        | 0.52 |

**但它是预览特性**，需要显式选择：

```xml
<PropertyGroup>
  <Features>runtime-async=on</Features>
</PropertyGroup>
```

关于开关有两个细节值得记住：`net11.0` 项目不再需要 `<EnablePreviewFeatures>true</EnablePreviewFeatures>`；而 .NET 的**运行时类库自己**已经用 `runtime-async=on` 编译，类库里不再有编译器生成的状态机。这意味着升级后即使你不改项目文件，类库那条路径也已经在新模型上跑了——你的业务代码仍然是旧的编译方式。

还有覆盖范围：`async void`、异步迭代器和自定义 task-like builder 目前不在支持范围内。所以正确的动作不是「升级完就快」，而是**先量自己的异步热路径，再决定要不要开这个开关**。

## 不用改代码就能拿到的那一层

JIT 的改进最省事：同样的源码、同样的 IL，换个运行时就有收益。原文在这一节花了最多篇幅，几个代表性数字：

| 改动                                                                                             | 基准                        | .NET 10          | .NET 11        | 比值  |
| ------------------------------------------------------------------------------------------------ | --------------------------- | ---------------- | -------------- | ----- |
| 可空装箱纳入逃逸分析（[#122167](https://github.com/dotnet/runtime/pull/122167)）                 | `FormatNullableInt`         | 9.583 ns / 24 B  | 1.987 ns / 0 B | 0.21  |
| 条件逃逸分析支持链式 `GetEnumerator`（[#122946](https://github.com/dotnet/runtime/pull/122946)） | `ReadOnlyInstance`          | 13.874 ns / 32 B | 2.674 ns / 0 B | 0.19  |
| 委托/闭包去抽象                                                                                  | `NonShared`                 | 6.678 ns / 24 B  | 1.764 ns / 0 B | 0.26  |
| 边界检查消除                                                                                     | `Sum16`                     | 2.958 ns         | 1.828 ns       | 0.62  |
| 泛型路径上的序号查找                                                                             | `CountOrdinal_Generic`      | 59.24 ns / 288 B | 10.01 ns / 0 B | 0.17  |
| 写屏障与 GC                                                                                      | `CollectGen0`（100 万句柄） | 10.737 ms        | 310.7 μs       | 0.029 |

这一节的主线是「把编译器已知的事实一直传下去」：守卫式去虚拟化（GDV）猜出虚调用/接口调用的具体目标，逃逸分析判断新分配的对象有没有逃出当前方法，两者叠加之后，本来要上堆的临时对象被放到栈上甚至拆成标量——所以你能看到大量「时间降一半、分配直接归零」的组合。最后一行是 GC 侧的极端例子：100 万个句柄的 Gen0 回收，从 10.7 毫秒降到 310 微秒。

## 类库：最值得你自己复测的几处

原文对类库每个领域都给了数据。按「影响面 × 你可能正在用」排，下面几处最值得关注。

### 正则：本年度量级最大的意外

| 基准                    | .NET 10  | .NET 11  | 比值  |
| ----------------------- | -------- | -------- | ----- |
| `Match`                 | 861.9 μs | 9.251 μs | 0.011 |
| `Miss`                  | 861.4 μs | 9.647 μs | 0.011 |
| `IgnoreCaseAlternation` | 415.0 μs | 7.012 μs | 0.017 |

接近两个数量级。原因不是某一处神奇优化，而是一串叠加：整模式优化之后追加一遍最终清理（例如把公共的 `[ab]+` 分解开）、修正前缀提取（原来只提到 `htt` 而不是 `http`）、用 `SearchValues<string>` 搜索整个字面量前缀、证明循环之后可以直接测末位而不必回溯、给 `RegexOptions.Compiled` 补上 switch 分派、让编译后的反向引用改用 `SequenceEqual`（[#125289](https://github.com/dotnet/runtime/pull/125289) 等）。

如果你有跑在热路径上的正则，这是最值得重新量一次的地方——但要按你自己的模式量，别照搬这里的数字。

### LINQ 与 AsyncEnumerable：O(N²) 变 O(N)

`AppendChain` 从 8.253 ms 降到 28.49 μs，比值 0.00345——原文里量级最大的单项之一。原因是把同步 `Enumerable` 已有的扁平化拼接迭代器机制搬到了 `AsyncEnumerable`（[#122389](https://github.com/dotnet/runtime/pull/122389)）：1000 次 `Append` 的枚举从大约 50 万步降到大约 1000 步，复杂度直接降了一阶。

同步 LINQ 侧的改动更细碎：`MaxByte`（长度 64）7.827 ns → 2.059 ns（0.26），收尾阶段也保留向量指令；`Sum` 的溢出检测在累加后统一测一次并改用 span 遍历，`AppendSkipLastOrDefault` 44.89 ns → 16.32 ns（0.36）；另外新增了 `FullJoin`。

### 集合：「已知信息不要重复算」

- `ImmutableArray` 与 `List` 的 `SequenceEqual`：925.8 ns → 122.2 ns（0.13），让优化路径一直保持有效。
- `ImmutableSortedSet.SetEquals`：767.7 μs → 117.6 μs（0.15），分配从 430 KB 降到 0，直接线性比对两个有序序列。
- 空目标的 `UnionWith` 复用 `HashSet` 拷贝构造的快路径：46.207 μs → 2.433 μs（0.05）。
- 另外还有 `FrozenDictionary` 用源集合 count 预分配、`OrderedDictionary` 去掉二次哈希查找、`HashSet.Remove` 用无符号比较消除边界检查。

### 字符串与编码：UTF-8 与 Base64 的向量化

- Base64 解码：10.70 μs → 2.256 μs（0.21）。做法是复用现有解码 helper 实现按 4 读 3 写的就地解码。
- `Convert.ToBase64String` 的 `InsertLineBreaks` 走向量化 span 编码器：57 字节输入 60.95 ns → 23.91 ns（0.39）。
- UTF-8 侧：`Utf8GetCharCount` 443.5 ns → 210.6 ns（0.47），带代理对的校验 2.994 μs → 856.8 ns（0.29）。
- 还有一个不用改代码的编译器改进：`span[start..]` 现在直接降级为 `Slice(start)`，IL 从 21 字节降到 9 字节。

### JSON、诊断、密码学

| 领域         | 基准                   | .NET 10           | .NET 11         | 比值  |
| ------------ | ---------------------- | ----------------- | --------------- | ----- |
| JSON 写入    | `Write`                | 30.83 μs          | 7.875 μs        | 0.26  |
| 分布式追踪   | `ExtractTraceParent`   | 45.41 ns          | 9.137 ns        | 0.20  |
| 进程名查询   | `GetProcessName`       | 332.13 μs         | 11.90 μs        | 0.04  |
| 指标记录     | `Record`               | 17.16 ns / 72 B   | 4.511 ns / 0 B  | 0.26  |
| AES 密钥包装 | `EncryptKeyWrapPadded` | 2.497 ms / 264 KB | 111.3 μs / 88 B | 0.045 |

JSON 写入的收益来自把逐字符扫描换成批量扫描：为默认转义规则预计算 `SearchValues`，并且只把已知可写的范围交给转义 helper，让 JIT 一次证明能容纳、去掉逐字节的边界检查。诊断侧的思路是「不采集就不付费」，`Record` 那条路径现在完全不分配。密码学里最夸张的是 AES KeyWrap：Windows 实现原来每个块都新建再销毁原生 cipher，改成整次 wrap/unwrap 复用一个，分配从 264 KB 掉到 88 B。

### 网络与 I/O：减等待、减拷贝、减分配

网络侧有一个值得单独说的改动。原文给了一个「IPv6 连接卡住」的合成场景：

| 策略                        | 平均耗时   | 比值  |
| --------------------------- | ---------- | ----- |
| `ConnectAlgorithm.Default`  | 511.054 ms | 1.000 |
| `ConnectAlgorithm.Parallel` | 1.060 ms   | 0.002 |

**要把两个前提说清楚**：这是**显式选择**的新行为（默认仍是原来的顺序策略），而且原文自己标注了这个场景「有点合成」（A bit synthetic, but it conveys the idea）——它构造的是一个 IPv6 连接迟迟不响应的场景，不代表所有连接的普遍收益。真正的价值是：当一台机器 IPv6 配置有问题时，应用不必再把整个超时耗在前面。

其余几处：`Uri` 解析 547.6 ns → 386.9 ns（0.71），分配 936 B → 432 B（把 path/query/fragment 的归一化合并进一个 builder，最终字符串只创建一次）；`ZipArchive` 的中央目录缓冲改为从 `ArrayPool<byte>` 租借，553.5 ns → 258.1 ns（0.47），分配 5.05 KB → 1.13 KB。I/O 侧还新增了公开的 `DeflateEncoder`/`ZLibEncoder`/`GZipEncoder`，让你可以自带并复用缓冲，而不是每次构造编解码器。

### 数值与全球化

- `BigInteger` 的 limb 从 `uint` 改为 `nuint`，加上 Montgomery 乘法、滑动窗口 `ModPow`、直接 UTF-8 解析格式化等：大数十进制 `ToString` 从 135,894,135.4 ns（约 136 毫秒）降到 7,868,359.3 ns（约 7.9 毫秒），比值 0.058；`Parse` 0.43。
- `FormatSubnormal` 6.884 μs → 1.237 μs（0.18）；`TensorPrimitives.Asin` 向量化后 `AsinFloat` 33.72 μs → 8.240 μs（0.24）。
- 全球化：`ToUpperInvariant` 的 ASCII 长字符串 248.38 ns → 39.22 ns（0.16），做法是先走托管 ASCII 路径，避免或推迟 ICU 初始化；时区转换复用按年缓存的 transition 数据，`ConvertTimeFromUtc` 45.13 ns → 19.44 ns（0.43）。

## 怎么用自己的数据复现

原文的基准项目是自包含的，可以直接照这个骨架搭一个。关键在于**同一份代码多目标编译**：

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFrameworks>net11.0;net10.0</TargetFrameworks>
    <LangVersion>preview</LangVersion>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>
    <ServerGarbageCollection>true</ServerGarbageCollection>
    <SystemPackageVersion Condition="'$(TargetFramework)' == 'net10.0'">10.0.12</SystemPackageVersion>
    <SystemPackageVersion Condition="'$(TargetFramework)' == 'net11.0'">11.0.0-rc.1.26425.128</SystemPackageVersion>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="BenchmarkDotNet" Version="0.16.0-preview.1" />
    <PackageReference Include="System.IO.Hashing" Version="$(SystemPackageVersion)" />
    <PackageReference Include="System.Runtime.Caching" Version="$(SystemPackageVersion)" />
    <PackageReference Include="System.Numerics.Tensors" Version="$(SystemPackageVersion)" />
  </ItemGroup>
</Project>
```

跨运行时对比（同一份代码在 .NET 10 与 .NET 11 上各跑一遍）：

```bash
dotnet run -c Release -f net10.0 --filter "*" --runtimes net10.0 net11.0
```

只比较两种写法、不跨运行时：

```bash
dotnet run -c Release -f net11.0 --filter "*"
```

把原文里的 benchmark 换成你自己的热点方法就行。这一步比读一百个数字更有用：原文的每个数字都在解释一个机制，而机制有没有落在你的代码路径上，只有你自己的数据能回答。

关于本文的验证边界要说清楚：**我没有在本机复现这些数字**。本机只装了 .NET 10 的 SDK，没有安装 .NET 11 RC，而微基准的结果本来就强依赖具体机器。文中所有数字都逐行取自原文的基准表格（含 `Ratio` 列与分配列），我核对过基线行与结果行的对应关系，没有做换算，也没有把「比值」改写成百分比。

## 结论

把这篇长文读完，真正能落地的判断只有三条：

1. **免费的收益在 JIT 这一层。** 逃逸分析、去虚拟化、边界检查消除这类改动不需要你动源码，升级后自动生效——分配归零往往比时间下降更有价值，因为它的收益会随调用量线性放大。
2. **类库的收益集中在几个热点上。** 正则是本年度的量级之王，LINQ/AsyncEnumerable 的 `Append` 链修掉了复杂度问题，集合类靠「不重复算已知信息」拿到几倍提升。挑你正在用的那一个重新量一遍。
3. **两条门槛必须先确认。** CPU 是否满足 x86-64-v2（Windows Arm64 还要 LSE）决定了能不能跑；运行时异步仍在 `<Features>runtime-async=on</Features>` 这个预览开关后面，决定了要不要开。

最省事的下一步：用上面的双运行时骨架，把你自己的一个正则热点和一个 LINQ/异步枚举热点各跑一次对比。如果两处都没变化，那 .NET 11 对你的收益主要来自运行时和类库本身——留在哪个版本就该看支持周期，而不是这几百项里的某一项。

如果你也在做 AI 助手、开发工具或 .NET 工程实践，Aide Hub 会继续分享这类「先量、再改、最后再下结论」的落地经验。

## 参考

- [Performance Improvements in .NET 11 — Stephen Toub, .NET Blog](https://devblogs.microsoft.com/dotnet/performance-improvements-in-net-11)
- [.NET 11 release notes（含各版本发布时间与支持周期）— dotnet/core](https://github.com/dotnet/core/blob/main/release-notes/11.0/README.md)
- [What's new in .NET 11 runtime — Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/runtime)
- [Breaking change: minimum hardware requirements updated — Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/core/compatibility/jit/11/minimum-hardware-requirements)
- [dotnet/runtime#122167：可空装箱纳入逃逸分析](https://github.com/dotnet/runtime/pull/122167)
- [dotnet/runtime#122946：条件逃逸分析支持链式 GetEnumerator](https://github.com/dotnet/runtime/pull/122946)
- [dotnet/runtime#122389：AsyncEnumerable 的 Append 链扁平化](https://github.com/dotnet/runtime/pull/122389)
- [dotnet/runtime#106374：Socket.ConnectAsync 的并行连接策略](https://github.com/dotnet/runtime/pull/106374)
- [dotnet/runtime#125289：正则整模式优化后的最终清理](https://github.com/dotnet/runtime/pull/125289)
