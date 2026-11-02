---
pubDatetime: 2026-11-02T08:50:00+08:00
title: "C# 字符串里的孤立代理项，SIMD 怎么修"
description: "C# 字符串是 UTF-16，孤立代理项一旦写进存储或网络就会出错。这篇按 Daniel Lemire 的新实现讲清代理项的判定、常规修复为什么在 emoji 输入上掉到 0.4 GB/s，以及 SIMD 版本如何回到 53 GB/s。"
tags: ["CSharp", ".NET", "Unicode", "SIMD", "Performance"]
slug: "utf16-lone-surrogate-simd-csharp"
ogImage: "../../assets/1127/01-cover.jpg"
source: "https://lemire.me/blog/2026/09/26/how-fast-can-you-fix-a-utf-16-string-in-c/"
---

一段从聊天记录、旧数据库或者第三方接口拿来的字符串，里面可能藏着半个 emoji：一个高代理项，后面本该跟着配对的低代理项，实际跟着的却是下一个汉字。这样的串写进 JSON、转成 UTF-8、塞进数据库的 text 列，或者发给下游服务，有的组件抛异常，有的把它静默换成乱码，有的按字节截断后继续用。

C# 的 `string` 是 UTF-16，但从不保证良构。JavaScript 从 ES2024 起有 `String.prototype.toWellFormed()` 和 `isWellFormed()` 来处理这件事，C# 一直没有等价物。Daniel Lemire 把同一套算法做成了 C# 库 SimdUnicode 的一部分：良构输入原样返回、不分配新字符串；发现孤立代理项就换成 U+FFFD。用 SIMD 做校验时，全是合法代理对的 emoji 文本能跑到 53 GB/s，而只用公开 API 的常规写法是 0.39 GB/s。

## 什么样的字符串是坏的

UTF-16 把一个码位编码成一个或两个 16 位单元。基本多文种平面内的字符占一个单元；emoji 和更罕见的字符占两个，前面是高代理项（`U+D800`–`U+DBFF`），后面是低代理项（`U+DC00`–`U+DFFF`）。只有这一对同时出现、顺序正确，才构成一个合法字符。

按 Unicode 的定义，下面四种情况都属于非良构：

- 高代理项出现在字符串末尾，后面没有东西
- 高代理项后面跟的是普通字符，不是低代理项
- 低代理项前面没有高代理项陪它
- 两个代理项顺序反了：先低后高

这四种情况下，那两个 16 位单元不表示任何 Unicode 码位。修复的办法只有一个：把落单的代理项换成替换字符 U+FFFD（显示为一个带问号的菱形），它本身是合法码位，用来表示「这里原本有无法解码的数据」。

在 .NET 里制造这种字符串比想象中容易。`new string(...)`、字符串拼接、`Substring` 都不校验代理对，按长度截断一个含 emoji 的字符串，正好从中间切开一对代理项，就得到一个坏串。从字节数组解码、按固定长度切分日志字段、从老系统的 `NVARCHAR` 里读数据，都会遇到同样的情况。

## SimdUnicode 里的两个方法

SimdUnicode 原本做的是 UTF-8 校验，后来加了 UTF-16 良构化。API 在 `SimdUnicode.UTF16` 下，形状和 JavaScript 的两个方法一致：

```csharp
using SimdUnicode;

// 良构的字符串原样返回，不分配新对象
string fixedText = UTF16.ToWellFormed("ab\uD800cd"); // "ab\uFFFDcd"

// 只判断，不修复
bool ok = UTF16.IsWellFormed("ab\uD800cd"); // false
```

除了字符串版本，还有指针和缓冲区版本：`ToWellFormed(char* input, int length, char* output)` 可以做原地修复（输入输出同一块内存），`GetPointerToFirstInvalidChar` 返回第一个孤立代理项的位置，适合只想定位不想复制的场景。

实现上按 CPU 能力分派内核：x64 上有 AVX-512、AVX2、SSE4.1 三档，ARM64 用 NEON，运行时自动选择；实在没有可用指令集时，退回 .NET 自带的向量化 `IndexOfAnyInRange`。

项目接入要注意两点。库的 `TargetFramework` 是 `net10.0`，只能用在 .NET 10 及以上；官方没有发布 NuGet 包，接入方式是克隆仓库后添加项目引用。

“良构输入原样返回”这一点和 JavaScript 的实现不同。JS 的 `toWellFormed()` 即使输入已经良构，也仍会返回一个新字符串；这个 C# 版本会返回同一个实例，所以高频校验路径上它比 JS 版本更省内存分配。据作者和论文，同一套算法也被用进了 V8，Chrome 修复字符串走的就是这条路。

## 常规写法为什么慢

只用公开 .NET API 时，最直接的做法是「先判断是否良构，良构直接返回；否则拷贝一份，边扫描边修」。原文给出的参考实现是这样：

```csharp
static void Repair(ReadOnlySpan<char> input, Span<char> output)
{
    input.CopyTo(output);
    int i = NextError(output, 0);
    while (i >= 0)
    {
        output[i] = '\uFFFD';
        i = NextError(output, i + 1);
    }
}

// 返回 start 之后第一个孤立代理项的下标，没有则返回 -1
static int NextError(ReadOnlySpan<char> s, int start)
{
    int i = start;
    while (true)
    {
        int k = s.Slice(i).IndexOfAnyInRange('\uD800', '\uDFFF');
        if (k < 0) return -1;
        i += k;
        if (char.IsHighSurrogate(s[i]) && i + 1 < s.Length && char.IsLowSurrogate(s[i + 1]))
            i += 2; // 合法代理对，跳过
        else
            return i;
    }
}
```

原文页面上的代码块把三个字符字面量显示成了 `'uFFFD'`、`'uD800'`、`'uDFFF'`，反斜杠在排版时丢掉了，照抄编译不过；上面的版本补回了反斜杠。

这段代码的瓶颈在 emoji 文本上。`IndexOfAnyInRange` 本身是向量化的，找代理项很快，可它每命中一次，代码就要退回标量逻辑，检查后一个单元是不是配对的低代理项。纯英文和中文里代理项很少，这个代价可以忽略，实测能跑 33 GB/s；emoji 文本里几乎每两个单元就是一个代理项，向量搜索等于每个字符都要停下来，于是掉到 0.39 GB/s。

库的 README 里还列了两种更「地道」的写法，成绩更差：`string.Concat(s.EnumerateRunes())` 在 0.2 到 0.4 GB/s，走一遍 `Encoding.Unicode` 往返是 1.3 到 7 GB/s。

## SIMD 版本在判什么

这里的难点落在「配对」上。光找出代理项不够：单看某个单元是否落在 `U+D800`–`U+DFFF`，判断不了它有没有跟相邻单元组成合法字符。合法性取决于相邻两个单元的组合与顺序。

SIMD 版本一次读入一整块单元（AVX-512 一次 32 个 16 位单元，AVX2 是 16 个，NEON 是 8 个），在向量里同时算出两类掩码：哪些是高代理项，哪些是低代理项。思路大致是把高代理项的掩码朝相邻位置挪一位，和低代理项的掩码相与，得到「配对成功」的位置；再从全部代理项位置里减掉这些位置，剩下的就是孤立代理项，对应位置写 U+FFFD 即可（具体的移位与掩码顺序以实现为准）。整块不存在代理项时，走一条更快的分支，这也是它接近内存拷贝速度的原因。

![SIMD 分块检查代理项示意：整块被切成 16 位单元，成对的高、低代理项判为合法，落单的被标记并替换成 U+FFFD（概念示意）](../../assets/1127/02-illustration-simd-blocks.jpg)

校验版本（`IsWellFormed`）在遇到第一个孤立代理项时就可以返回，不必扫完；`ToWellFormed` 的缓冲区版本则要写满整块输出，所以它的上限是由内存带宽决定的，而不是判断逻辑。

## 数字怎么读

原文和库 README 里的测试都跑在 Intel Xeon Gold 6548N（Emerald Rapids，AVX-512）和 Apple M4 Max 上，.NET SDK 10.0.400（Linux）与 10.0.103（macOS）。单位是 UTF-16 输入的 GB/s，测试输入都是良构字符串。

| 输入              | 校验：SimdUnicode | 校验：IndexOfAnyInRange | 写缓冲区：SimdUnicode | 写缓冲区：拷贝 + 扫描 | 纯拷贝 |
| ----------------- | ----------------- | ----------------------- | --------------------- | --------------------- | ------ |
| Emoji-Lipsum      | 53                | 0.39                    | 40                    | 0.39                  | 44     |
| Twitter.json      | 69                | 31                      | 26                    | 15                    | 28     |
| Latin-Lipsum      | 69                | 33                      | 43                    | 20                    | 46     |
| 短字符串（emoji） | 3.1               | 0.43                    | —                     | —                     | —      |

几处值得注意的地方：

- 差距最大的就是 emoji 输入，校验相差 130 倍以上；普通文本的差距在 2 倍左右。
- 写缓冲区的版本在 x64 上基本贴着纯拷贝跑，只比 memcpy 慢一点；emoji 输入是例外，因为它要写 U+FFFD。
- 字符串被切成 1 到 64 个单元的短串时，SimdUnicode 只是略快，emoji 上快 6 到 8 倍。真实业务里绝大多数字符串都是短的，不能只看大文本的数字。
- 如果输入里真的有孤立代理项需要修复（每百万单元 100 个左右），两种实现都受限于新字符串的分配，优化空间不在扫描本身。
- M4 Max 上趋势一致但幅度小一些：emoji 校验 52 对 2.0，Twitter.json 106 对 62。

这些是作者在自己的机器上跑出来的单机数据，不是独立复现；GB/s 的绝对值会随 CPU、编译选项和输入分布变化，值得看的是相对差距和量级。

## 你的代码该在哪里用它

先找边界。热点的事放一放，等 profiler 数据出来再说。需要良构保证的位置通常是：接收外部 JSON 或消息之后、写入数据库或对象存储之前、转换成 UTF-8 之前、做跨进程传输之前。这些地方用 `IsWellFormed` 做一次断言并记录日志，比在业务代码里到处防御更清楚。

只在确实是瓶颈时才换 SIMD 实现。判断方法很直接：把 `ToWellFormed` 的耗时放进 profiler，看它占不占得到可见比例；如果输入以短字符串为主，先看短字符串那一行的数字，收益可能没有大文本那么夸张。

不引入第三方库也有兜底，但要接受它的速度和细节：`Encoding.Unicode` 默认把无法解码的内容换成问号，想要 U+FFFD 得显式指定 `new DecoderReplacementFallback("\uFFFD")`；`Rune.DecodeFromUtf16` 返回 `OperationStatus`，循环里逐码位处理，遇到非法数据时按 `InvalidData` 分支自行换成 U+FFFD；`Utf8.FromUtf16` 默认 `replaceInvalidSequences: true`，转码时顺带把坏输入换成 U+FFFD，但输出是 UTF-8，不是修好的 `string`。这些路径都会分配新数组或新字符串，适合低频调用和测试断言。

对一个对外服务来说，收益更多体现在行为确定上：坏串在边界上被识别出来、被记录、被统一替换，不会等到下游某个组件用不同的方式处理，最后变成一条很难查的数据问题。

## 参考

- [How fast can you fix a UTF-16 string in C#?](https://lemire.me/blog/2026/09/26/how-fast-can-you-fix-a-utf-16-string-in-c/)
- [SimdUnicode 仓库](https://github.com/simdutf/SimdUnicode)
- [Clausecker & Lemire：Fixing ill-formed UTF-16 strings with SIMD instructions（Software: Practice and Experience, 2026）](https://arxiv.org/abs/2601.06349)
- [论文 DOI：10.1002/spe.70105](https://doi.org/10.1002/spe.70105)
- [Unicode FAQ：UTF-16 与代理项](https://www.unicode.org/faq/utf_bom.html#utf16-3)
- [Unicode 标准第 3 章：UTF-16 编码形式](https://www.unicode.org/versions/latest/core-spec/chapter-3/)
- [Rune.DecodeFromUtf16](https://learn.microsoft.com/en-us/dotnet/api/system.text.rune.decodefromutf16)
- [Utf8.FromUtf16](https://learn.microsoft.com/en-us/dotnet/api/system.text.unicode.utf8.fromutf16)
- [MemoryExtensions.IndexOfAnyInRange](https://learn.microsoft.com/en-us/dotnet/api/system.memoryextensions.indexofanyinrange)
