---
pubDatetime: 2026-04-27T10:28:00+08:00
title: "意外打造出最快的 C# CSV 解析器"
description: "一次性能优化的完整旅程。从基础的字节扫描到 SIMD 向量指令，逐步优化 CSV 解析速度，最终击败现有高性能库。文中涵盖 UTF-8 编码原理、向量化指令、缓存优化等核心概念。"
tags: ["C#", "性能优化", "SIMD", "CSV解析", "高性能编程"]
slug: "turbo-csv-parser"
source: "https://bepis.io/blog/turbo-csv-parser"
---

有时候最好的发现来自无意间的实验。去年圣诞假期，我在州际长途车上有 24 小时的空闲时间，无聊之中随手翻起关于 UTF-8 编码的资料。我突然意识到一个从未在意的事实：所有传统的 ASCII 字符在 UTF-8 中都保持原样，以单个字节的形式存储。这意味着可以用超高效的技巧来扫描这些字符。

于是我开始写代码，试图尽可能快地计数这样的字符，最后竟然打磨出了一个相当高效的 CSV 解析器，其性能甚至超过了许多现有的库。

这篇文章记录了整个过程：我如何思考、实验、优化，以及最终达到什么样的性能水平。

## 第一部分：字符编码基础

要理解为什么我们能那么快地处理文本，首先要明白文本在计算机内存中是如何存储的。

### ASCII 的年代

这听起来像是计算机历史课，但很重要。计算机最小有意义的数据单位是字节，范围 0-255。而人类使用的字符远超过 256 个。这给工程师们出了一道难题：怎样用字节高效表示所有字符？

ASCII 是最早的解决方案。创于 1970 年代，用单个字节表示 128 个字符（7 位）。后来各国扩展为自己的字符集（代码页），例如中文、日文、俄文各有各的编码方式。最大的问题是：**文件不存储自己用了什么编码**。打开文件用错了编码，就会看到乱码（Mojibake）。

### Unicode 统一天下

到了 1990 年代，太混乱了。工程师们受够了几百种不同的编码，决定彻底改变方式：**给每个字符分配一个数字**（代码点），然后把这个数字转成字节。

最妙的是，为了向后兼容 ASCII，Unicode 设计了多种编码方式（UTF 家族）。其中最重要的是 UTF-8。

### UTF-8 的妙处

UTF-8 用**可变长度编码**。ASCII 范围的字符（0x00-0x7F）仍然是单字节，这样既保留了 ASCII 兼容性，又能表示 100 多万个字符。

编码规则很简单：看第一个字节的前几位，就知道这个字符占几个字节：

| 需要字节数 | 代码点范围 | 二进制结构 |
| --- | --- | --- |
| 1 字节 | U+0000 to U+007F | `0xxxxxxx` |
| 2 字节 | U+0080 to U+07FF | `110xxxxx 10xxxxxx` |
| 3 字节 | U+0800 to U+FFFF | `1110xxxx 10xxxxxx 10xxxxxx` |
| 4 字节 | U+10000 to U+10FFFF | `11110xxx 10xxxxxx 10xxxxxx 10xxxxxx` |

关键是：**所有 ASCII 范围的字符在 UTF-8 里都是单字节**。这就是我后来利用的关键性质。

## 第二部分：从基础循环到 SIMD

现在开始优化。问题很简单：给定 500MB 的 UTF-8 文本文件，如何最快地计数某个字符（比如逗号 `,`）的出现次数？

### 第一步：朴素实现（135ms）

```csharp
static int CountSoftware(ReadOnlySpan<byte> data)
{
  int count = 0;
  
  for (int i = 0; i < data.Length; i++)
  {
    if (data[i] == ',')
      count++;
  }
  
  return count;
}
```

简单直白，但每次数组访问 .NET 都会进行边界检查。

### 第二步：使用不安全指针（128ms）

```csharp
static unsafe int CountSoftwareUnsafe(ReadOnlySpan<byte> data)
{
  int count = 0;
  int length = data.Length;
  
  fixed (byte* ptr = data) 
    for (int i = 0; i < length; i++)
    {
      if (ptr[i] == ',')
        count++;
    }
  
  return count;
}
```

通过 `unsafe` 指针避免边界检查，快了 7ms。这提醒我们：即使看起来很小的开销，在紧循环里也能累积。

### 第三步：循环展开 4 倍（105ms）

```csharp
static unsafe int CountSoftwareUnsafeUnrolled4x(ReadOnlySpan<byte> data)
{
  int count = 0;
  int length = data.Length;
  
  fixed (byte* ptr = data)
  {
    int i = 0;
    
    for (; i + 3 < length; i += 4) 
    { 
      if (ptr[i] == ',') count++; 
      if (ptr[i + 1] == ',') count++; 
      if (ptr[i + 2] == ',') count++; 
      if (ptr[i + 3] == ',') count++; 
    } 
    
    for (; i < length; i++)
    {
      if (ptr[i] == ',')
        count++;
    }
  }
  
  return count;
}
```

循环本身的开销很大（分支检查、跳转等）。一次处理 4 个字节能减少这些开销。

到这里还是逐个处理字节。要真正加速，需要用硬件的并行能力。

### SIMD：单指令，多数据

SIMD 是现代 CPU 的杀手锏。一条指令可以对 16 或 32 个字节同时进行相同操作，而耗时和普通操作一样。想象长除法：一位一位算很慢，但如果能一次看完整个数字立刻得出答案，那就太快了。SIMD 就是这种能力。

### 第四步：SSE2 SIMD（46ms）

```csharp
static int CountSSE2(ReadOnlySpan<byte> data)
{
  var compareVector = Vector128.Create(',');
  
  int count = 0;
  int i = 0;
  
  for (i = 0; i + 15 < data.Length; i += 16) 
  {
    var dataVector = Vector128.Create(data.Slice(i, 16));
    var equal = Sse2.CompareEqual(compareVector, dataVector);
    var mask = (uint)Sse2.MoveMask(equal);
    
    while (mask != 0) 
    { 
      count += (int)(mask & 0x1);
      mask >>= 1; 
    } 
  }
  
  for (; i < data.Length; i++)
  {
    if (data[i] == ',')
      count++;
  }
  
  return count;
}
```

SSE2 是 2000 年引入的，处理 128 位（16 字节）数据。一次比较 16 个字节，立刻就快了 2.8 倍！

`Sse2.CompareEqual` 对相等的位置输出 255，用 `MoveMask` 把这个结果转成一个 16 位整数，每一位代表一个匹配位置。

### 第五步：AVX2（42ms）

```csharp
static int CountAvx2(ReadOnlySpan<byte> data)
{
  var compareVector = Vector256.Create(',');
  
  int count = 0;
  int i = 0;
  
  for (i = 0; i + 31 < data.Length; i += 32) 
  {
    var dataVector = Vector256.Create(data.Slice(i, 32));
    var equal = Avx2.CompareEqual(compareVector, dataVector);
    var mask = (uint)Avx2.MoveMask(equal);
    
    while (mask != 0)
    {
      count += (int)(mask & 0x1);
      mask >>= 1;
    }
  }
  
  for (; i < data.Length; i++)
  {
    if (data[i] == ',')
      count++;
  }
  
  return count;
}
```

AVX2（2011 年）处理 256 位（32 字节）数据。改进不如 SSE2 那么大，说明新的瓶颈在别处：循环里逐位处理 mask 的那部分。

### 第六步：AVX2 + POPCNT（13ms）

```csharp
static int CountAvx2Popcnt(ReadOnlySpan<byte> data)
{
  var compareVector = Vector256.Create(',');
  
  int count = 0;
  int i = 0;
  
  for (i = 0; i + 31 < data.Length; i += 32)
  {
    var dataVector = Vector256.Create(data.Slice(i, 32));
    var equal = Avx2.CompareEqual(compareVector, dataVector);
    var mask = (uint)Avx2.MoveMask(equal);
    
    count += BitOperations.PopCount(mask);
  }
  
  for (; i < data.Length; i++)
  {
    if (data[i] == ',')
      count++;
  }
  
  return count;
}
```

`PopCount` 是硬件实现的，一条指令统计 mask 中有多少个 1。比逐位循环快得多。性能从 42ms 跳到 13ms，10 倍的改进！

这就是优化的本质：找到真正的瓶颈，用硬件特性突破。

## 第三部分：实现 CSV 解析器

现在把这些技巧用到 CSV 上。CSV 解析需要识别三个结构字符：`,`（字段分隔）、`"` （转义）、`\n`（行分隔）。

规则是：
- 逗号标记字段结束
- 换行标记行结束
- 引号会转义所有结构字符，直到下一个引号
- 两个引号连续时，输出一个引号

关键优化：**分两步**。第一步用 AVX2 快速扫描找出所有结构字符的位置，第二步才真正提取和解析字段内容。

```csharp
protected override int DetermineFields(ReadOnlySpan<byte> buffer)
{
  int fieldStart = 0;
  bool isEscaped = false;
  int fieldCount = 0;
  
  int i = 0;
  
  for (; i + 31 < buffer.Length; i += 32)
  {
    // 一次性扫描三种字符
    Vector256<byte> dataVector = Vector256.Create(buffer.Slice(i));
    
    uint separatorMask = (uint)Avx2.MoveMask(Avx2.CompareEqual(dataVector, separatorVector));
    uint escapeMask = (uint)Avx2.MoveMask(Avx2.CompareEqual(dataVector, escapeVector));
    uint newlineMask = (uint)Avx2.MoveMask(Avx2.CompareEqual(dataVector, newlineVector));
    
    var combinedMask = separatorMask | escapeMask | newlineMask;
    
    while (combinedMask != 0)
    {
      int index = BitOperations.TrailingZeroCount(combinedMask);
      uint bit = (1u << index);
      
      if ((escapeMask & bit) != 0) // 引号
      {
        isEscaped = !isEscaped;
        goto continueLoop;
      }
      
      if (isEscaped)
      {
        goto continueLoop; // 转义中，跳过所有结构字符
      }
      
      if ((separatorMask & bit) != 0) // 逗号
      {
        fieldInfo[fieldCount++] = (fieldStart, i + index - fieldStart, wasOnceEscaped);
        fieldStart = i + index + 1;
        wasOnceEscaped = false;
      }
      else if ((newlineMask & bit) != 0) // 换行
      {
        goto exit;
      }
      
      continueLoop:
      combinedMask &= ~bit;
    }
  }
  
  exit:
  fieldInfo[fieldCount++] = (fieldStart, endChar - fieldStart, wasOnceEscaped);
  return endChar;
}
```

这个设计巧妙之处在于：
1. 一次加载 32 字节数据
2. 三个 SIMD 比较同时进行，得到三个 mask
3. 合并 mask，逐个处理结构字符
4. 记录字段位置，但**不**处理字段内容（除非用户要求）
5. 这样避免了不必要的字符转换开销

### 处理转义和编码转换

当字段含有引号时，需要手动处理并进行 UTF-8 → UTF-16 转换（因为 C# 字符串是 UTF-16）：

```csharp
private int UnescapeField(Span<char> destination, (int offset, int length, bool isEscaped) info)
{
  if (!info.isEscaped)
  {
    // 无引号，用优化的内置转换
    return Encoding.UTF8.GetChars(new Span<byte>(bufferPtr + info.offset, info.length), destination);
  }
  
  // 有引号，自己处理
  int idx = 0;
  int rawLength = info.offset + info.length;
  
  for (int i = info.offset; i < rawLength; i++)
  {
    byte c = bufferPtr[i];
    if (c == '"')
    {
      // 跳过第一个引号，复制第二个（如果有）
      if (i != info.offset && i + 1 < rawLength)
      {
        var nextC = bufferPtr[i + 1];
        if ((nextC & 0x80) == 0) // 下一个不是多字节序列开始
        {
          destination[idx++] = (char)nextC;
          i++;
        }
      }
    }
    else if ((c & 0x80) != 0) // 多字节序列
    {
      // UTF-8 → UTF-16 转换（关键性质：2-3字节序列总是结果为单个 UTF-16 码元）
      var encodedLength = BitOperations.LeadingZeroCount((uint)(~c & 0xFF)) - 24;
      
      if (encodedLength == 2)
      {
        uint codePoint = (uint)((c & 0b0001_1111) << 6 | (bufferPtr[i + 1] & 0b0011_1111));
        destination[idx++] = (char)codePoint;
        i += 1;
      }
      else if (encodedLength == 3)
      {
        uint codePoint = (uint)((c & 0b0000_1111) << 12 |
                          (bufferPtr[i + 1] & 0b0011_1111) << 6 |
                          (bufferPtr[i + 2] & 0b0011_1111));
        destination[idx++] = (char)codePoint;
        i += 2;
      }
      else // 4 字节，需要代理对
      {
        uint codePoint = (uint)((c & 0b0000_0111) << 18 |
                          (bufferPtr[i + 1] & 0b0011_1111) << 12 |
                          (bufferPtr[i + 2] & 0b0011_1111) << 6 |
                          (bufferPtr[i + 3] & 0b0011_1111));
        
        codePoint -= 0x10000;
        destination[idx++] = (char)(ushort)((codePoint >> 10) + 0xD800);
        destination[idx++] = (char)(ushort)((codePoint & 0x3FF) + 0xDC00);
        i += 3;
      }
    }
    else // ASCII 单字节
    {
      destination[idx++] = (char)c;
    }
  }
  
  return idx;
}
```

这里的技巧是：如果没有引号，直接用 .NET 的优化转换（它深入运行时）；如果有引号，自己处理时顺便做转换，避免二次扫描。

### 处理 UTF-16 输入

但 C# 本身用的是 UTF-16。如果输入是 C# 字符串该怎么办？

不能简单地按 UTF-16 逐字节扫描，因为 ASCII 字符的编码完全不同。但我想到了一个技巧：用 `Avx2.PackUnsignedSaturate` 把 16 位值"压缩"成 8 位，ASCII 范围的字符保持不变，超出范围的饱和到 255。这样就能继续用 SIMD 逻辑：

```csharp
Vector256<short> dataVector1 = Avx.LoadVector256((short*)bufferPtr + i);
Vector256<short> dataVector2 = Avx.LoadVector256((short*)bufferPtr + i + 16);

Vector256<byte> packedData = Avx2.PackUnsignedSaturate(dataVector1, dataVector2);

Vector256<byte> dataVector = Avx2.Permute4x64(packedData.AsUInt64(), 0b11_01_10_00).AsByte();

// 然后照常处理...
```

## 第四部分：性能基准

我创建了一个全面的测试套件，包括：

**真实数据**：
- Reddit 数据（宽列、多种数据类型、人类文本）
- Pokédex 数据（非拉丁 Unicode 字符）
- 金融数据（大量数字、少量文本）

**合成数据**：
- 基础 4 列数据集（数字 0-2000）
- 短数据集（50 行，测试开销）
- 有引号数据集（每个字段都有引号）
- 极端数据集（大量引号和转义）

结果：在 70 个测试中，我的库在 **41 个**上速度最快。

### 为什么胜过 Sep（前任最快库）？

1. **UTF-8 vs UTF-16**：Sep 总是先转换到 UTF-16，浪费时间。我的库可以直接处理 UTF-8。

2. **缓存压力**：我的库只有 16KB，Sep 有 163KB。代码越小，L1 缓存（32-64KB）就越有空间保存数据。Sep 的巨大热循环可能导致缓存溢出，频繁访问内存。

3. **过度优化的局限**：Sep 微优化了每一个细节，但这有两个问题：
   - 容易陷入局部最优（山顶问题）
   - 限制了编译器和运行时的优化空间
   
   我的代码更直白，让 .NET 有更多优化余地。每次新的 .NET 版本发布都会带来新的优化，我的设计能够受益。

4. **硬件差异**：在 AVX-512 和 ARM 上，Sep 可能更快。我没有这些硬件来测试。

## 第五部分：关键收获

这个项目教会我几个重要的东西：

1. **理解基础很重要**。不理解 UTF-8 怎么工作，就不会想到这个优化。

2. **测量很重要**。很多假设在实际数据上不成立。

3. **平衡指导和自由**。过度微优化会陷入死胡同。有时候"写清楚代码，让编译器去优化"反而更快。

4. **专注真正的瓶颈**。从 135ms 到 42ms 靠的是 SIMD，剩下的 29ms 优化只是螺蛳壳里做道场。

## 现在

库已开源在 [GitHub](https://github.com/bbepis/FourLambda.Csv)。

我还在打磨另外两个项目：一个是高性能 JSON 解析器，另一个是 Reed-Solomon 纠错编码库。

另外我也在写关于其他高性能工具的文章，比如一个 MySQL 数据导入工具（比现存工具快 16 倍）。

感谢阅读！

---

## 参考

- [原文：How I accidentally made the fastest C# CSV parser](https://bepis.io/blog/turbo-csv-parser)
- [FourLambda.Csv GitHub 仓库](https://github.com/bbepis/FourLambda.Csv)
- [CSV 解析基准测试](https://bepis.io/csv-benchmark/)
