---
pubDatetime: 2026-08-24T13:46:19+08:00
title: ".NET 用 AVX-512 加速 IPv4 解析"
description: "Daniel Lemire 用 C#、.NET 10 和 AVX-512 为常见 IPv4 点分十进制输入设计 SIMD 快路径，借助 masked load、点位模式和回退策略，把标准库基线的解析成本降到约三分之一。"
tags: ["C#", ".NET", "SIMD", "性能优化"]
slug: "dotnet-avx512-ipv4-parsing"
ogImage: "../../assets/1018/01-cover.png"
source: "https://lemire.me/blog/2026/08/19/parsing-ip-addresses-in-c-at-crazy-speeds/"
---

在普通业务里，解析一个 IP 地址通常只需要调用 `IPAddress.TryParse`。当程序要持续处理日志、代理请求、网络包或访问控制规则时，解析器可能进入非常热的循环，几十纳秒的差异也会累积成可见成本。

Daniel Lemire 最近用 C# 和 .NET 10 做了一个很有代表性的实验：只针对最常见的 IPv4 点分十进制形式，利用 AVX-512 一次处理多个字符，再把无法覆盖的输入交回标准库。原文报告的完整包装路径从 45.3 ns/地址降到 14.1 ns/地址，约有 3 倍差距。本文拆解这条路径的关键想法，也说明它的适用边界。

## 先把问题边界说清楚

最稳妥的基线仍然是标准库：

```csharp
if (IPAddress.TryParse(text, out var address))
{
    // 使用 address
}
```

`IPAddress.TryParse` 需要处理 IPv4、IPv6，以及一些不符合日常书写习惯的 IPv4 表达形式。高性能路径选择了更窄的目标：类似 `192.168.0.1` 或 `12.121.244.111` 的四段十进制文本，每段 1 到 3 位，中间有 3 个点。

这个限定很重要。只要输入超出快路径的约束，就交给标准库处理，整体 API 仍保持完整的 IP 地址语义。快路径服务的是常见数据，不承担重新实现全部解析规则的任务。

## C# 的第一道难题：输入是 UTF-16

SIMD 优化常从“同时加载一批 ASCII 字节”开始。C# 的 `char` 默认是 UTF-16，一个看起来只有 15 个字符的 IPv4 字符串，在内存里可能占用 30 个字节。直接把它当成连续 ASCII 字节处理，会把数据布局弄错。

原文的思路分成两步：先用 AVX-512 的 masked load 只加载字符串实际存在的字符，再把 UTF-16 的低位压缩成一组 ASCII 字节。核心片段可以简化成这样：

```csharp
unsafe
{
    Vector256<ushort> laneMask = Vector256.LessThan(
        CharLaneIndex,
        Vector256.Create((ushort)length));

    Vector256<ushort> chars = Avx512BW.VL.MaskLoad(
        (ushort*)pointer,
        laneMask,
        Vector256.Create((ushort)'0'));

    if (Avx512BW.VL
            .CompareGreaterThan(chars, Vector256.Create((ushort)0x7f))
            .ExtractMostSignificantBits() != 0)
    {
        return false;
    }

    Vector128<byte> ascii = Avx512BW.VL.ConvertToVector128Byte(chars);
}
```

`laneMask` 标记哪些字符位于输入范围内，其他位置不会从字符串边界外读取。随后检查每个 UTF-16 单元是否属于 ASCII 范围，再把数据收窄为适合后续处理的字节向量。

这类代码依赖指针和硬件指令，项目需要打开 `AllowUnsafeBlocks`，并以 `net10.0` 为目标框架。运行时还要检查 `Avx512BW.VL.IsSupported`，当前公开实现同时检查了 `Ssse3.IsSupported`。

## 81 种点位布局是一个小空间

一个常见 IPv4 地址有四个数字段，每段长度只有 1、2、3 位三种选择。因此，三个点的位置一共有：

```text
3 × 3 × 3 × 3 = 81
```

这让解析器可以把“点在哪里”变成一个很小的查表问题。算法大致按下面的顺序工作：

1. 把点的位置提取成位掩码。
2. 根据位掩码找到对应的布局编号和字节重排模式。
3. 减去字符 `'0'`，检查每个需要是数字的位置。
4. 将四段数字排列到固定位置，用向量乘加得到四个数值。
5. 检查每段是否超过 255、点的数量是否正确，以及是否出现非法字符。
6. 把四个字节合成一个 `uint`，再构造 `IPAddress`。

原文提到的 dot product 就发生在第 4 步。它把不同长度的数字段统一放进向量，通过预先准备的权重一次算出各段的十进制值。公开源码还提供了 table-free 变体，尝试用 `vpcompressb`、`vpermb` 和掩码运算减少查表依赖；这些版本适合继续研究，普通应用没有必要直接照抄。

## 用一个回退入口保留兼容性

高性能解析器最实用的结构，是把硬件快路径放在标准库前面：

```csharp
public static bool TryParse(
    ReadOnlySpan<char> text,
    out IPAddress? address)
{
    if (IsSupported && TryParseAvx512(text, out uint value))
    {
        address = new IPAddress(value);
        return true;
    }

    return IPAddress.TryParse(text, out address);
}
```

这里有两层保护：CPU 不支持所需指令集时直接回退，输入不符合严格点分十进制规则时也回退。IPv6、非典型 IPv4 写法和 SIMD 路径无法接受的字符串，都能继续由标准库处理。

这个设计还降低了部署风险。调用方只面对一个方法，机器能力探测和输入分类都藏在实现内部；新代码可以逐步替换热路径，其他地方继续使用熟悉的 BCL API。

## 基准数字应该怎样解读

原文的测试生成了 10,000 个随机 32 位地址，把文本重复解析 20,000,000 次，并在每次构造 `IPAddress`。测试机器是 Intel Xeon Gold 6548N，运行 .NET 10：

| 实现                 | ns/地址 | 每秒百万地址 |
| -------------------- | ------: | -----------: |
| `IPAddress.TryParse` |    45.3 |         22.1 |
| AVX-512 + fallback   |    14.1 |         71.1 |

原文因此给出了约 3 倍的加速结论。作者公开代码目录中的当前 `results.txt` 又记录了一组结果：`IPAddress.TryParse` 为 46.23 ns，`Ipv4Parser.TryParse` 为 16.52 ns，约为 2.80 倍；只测不分配 `IPAddress` 的核心函数，当前结果最低约 6.24 ns。

两组数字来自具体机器、运行时、代码版本和测量方式。它们可以说明优化方向的潜力，不能直接当作所有 CPU 的承诺。尤其要区分两种成本：完整 API 包含对象构造和包装开销，纯解析内核更接近 SIMD 算法本身的速度。

## 正确性要先于纳秒

这类优化最容易被忽略的部分是输入覆盖范围。建议至少保留下面几组验证：

- 用标准库结果做差分测试，覆盖合法和非法输入
- 单独测试 1 到 3 位的四段组合、边界值 0 和 255
- 测试前导零、连续点、尾随点、非 ASCII 字符和超长输入
- 测试 IPv6 与非典型 IPv4，确认它们会走回退路径
- 在支持和不支持 AVX-512 的机器上分别运行
- 把解析内核、`IPAddress` 对象分配和完整业务流程分开测量

公开仓库的当前结果记录了 300 万个随机字符串的差分 fuzz、1 万个随机 dotted-quad，以及 0 个失败样本。这样的测试记录比单个漂亮的吞吐数字更能说明实现是否可用。

还要注意 masked load 的边界语义。它解决的是“只读取有效字符”的问题，不能替应用程序解决指针生命周期、跨线程访问或输入缓冲区本身失效的问题。`unsafe` 代码需要和普通业务代码一样接受审查。

## 什么时候值得使用

这条路线适合以下场景：

- 每秒处理数百万条 IP 文本，解析已经出现在性能分析的热点中
- 运行环境可控，能够确认目标 CPU 与 .NET 版本支持所需指令集
- 团队愿意维护 SIMD 代码、差分测试和回退逻辑
- 业务可以明确区分常见 IPv4 与完整 IP 地址语义

配置文件、低频 API 参数和普通日志处理通常不需要这份复杂度。先使用 `IPAddress.TryParse`，只有基准证明解析本身值得优化时，再引入硬件专用路径。优化后还要重新测量完整业务链路，确认收益没有被对象分配、字符串获取或网络等待吞掉。

## 小结

这篇实验的价值在于展示了一条完整的性能优化链路：缩小输入范围、识别数据布局、用 masked load 避免越界读取、用少量布局表处理结构差异、用向量运算完成校验，最后保留标准库回退。

它也提醒我们，C# 性能代码的边界已经延伸到硬件指令集。代码可以很快，适用范围仍需要写清楚；基准可以很亮眼，正确性和部署条件仍决定它能否进入生产环境。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践。

## 参考

- [Parsing IP addresses in C# at crazy speeds（原文，Daniel Lemire，2026-08-19）](https://lemire.me/blog/2026/08/19/parsing-ip-addresses-in-c-at-crazy-speeds/)
- [原文配套源码目录](https://github.com/lemire/Code-used-on-Daniel-Lemire-s-blog/tree/master/2026/08/19)
- [Ipv4Parser.cs](https://github.com/lemire/Code-used-on-Daniel-Lemire-s-blog/blob/master/2026/08/19/Ipv4Parser.cs)
- [公开基准与正确性结果 results.txt](https://github.com/lemire/Code-used-on-Daniel-Lemire-s-blog/blob/master/2026/08/19/results.txt)
- [IPAddress.TryParse - Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/api/system.net.ipaddress.tryparse?view=net-10.0)
- [Avx512BW.MaskLoad - Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.intrinsics.x86.avx512bw.maskload?view=net-10.0)
- [在 .NET 中使用 SIMD 与硬件内在函数 - Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/standard/simd)
- [Parsing IPv4 addresses crazily fast（前一篇 SIMD 实验）](https://lemire.me/blog/2023/06/08/parsing-ip-addresses-crazily-fast/)
- [Modern vector programming with masked loads and stores](https://lemire.me/blog/2022/11/08/modern-vector-programming-with-masked-loads-and-stores/)
