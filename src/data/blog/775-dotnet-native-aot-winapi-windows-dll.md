---
pubDatetime: 2026-05-06T16:40:00+08:00
title: "用 .NET Native AOT 构建 Windows WinAPI 风格的原生 DLL"
description: "本文介绍如何用 .NET Native AOT 将 C# 代码编译成原生 Windows DLL，供任何能调用 WinAPI 风格 StdCall DLL 的应用程序使用。包含项目配置、导出方法声明、字符串和结构体传参、构建命令，以及使用场景分析。"
tags: [".NET", "AOT", "C#", "Windows", "DLL", "P/Invoke"]
slug: "dotnet-native-aot-winapi-windows-dll"
ogImage: "../../assets/775/01-cover.png"
source: "https://weblog.west-wind.com/posts/2026/Mar/21/Using-NET-Native-AOT-to-build-Windows-WinAPI-Dlls"
---

![C# 代码通过 AOT 编译管线转换为原生 Windows DLL](../../assets/775/01-cover.png)

用 .NET 写系统级 DLL 一直不是件容易的事：要么借助 COM 接口，要么靠 wwDotnetBridge 这类宿主库来帮你"搭桥"。直到 Native AOT 成熟，才出现了另一条路——把 C# 代码直接编译成原生 Windows DLL，调用方只需遵循标准 WinAPI（StdCall）约定，根本不需要知道背后跑的是 .NET。

Rick Strahl 在他的博客里详细记录了这条路的走法和坑点。本文是对原文的中文整理，重点覆盖：项目配置、导出方法写法、字符串和结构体的传参方式，以及这个方案真正适合哪些场景。

## 为什么要这样做

Rick 的动机很具体：他有一批用 Visual Studio C++ 编译器构建的老旧 Windows DLL，维护成本高——每次 C++ SDK 或 MSVC 版本升级，依赖关系就可能乱掉。把这些 DLL 迁到 C# + AOT，可以彻底摆脱 C++ 工具链，用更熟悉的语言写逻辑。

他的测试调用方是 FoxPro（一门古老的桌面开发语言），但同样的原理适用于任何能调用 StdCall DLL 的语言或工具：Python、C、老版 VB，以及没有 COM 支持的嵌入式脚本环境。

## 项目配置

从一个普通的 Class Library 项目开始，在 `.csproj` 里加两个关键属性：

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>

    <!-- 关键配置 -->
    <PublishAot>true</PublishAot>
    <NativeLib>Shared</NativeLib>

    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>
  </PropertyGroup>
</Project>
```

- `PublishAot=true`：开启 AOT 编译
- `NativeLib=Shared`：告诉编译器把输出打包成共享库（即 `.dll`），而不是可执行文件
- `AllowUnsafeBlocks`：调用 P/Invoke 时几乎必然用到，建议直接开启

## 声明导出方法

给要导出的静态方法加上 `[UnmanagedCallersOnly]` 特性，指定入口点名称和调用约定：

```csharp
public static class Exports
{
    [UnmanagedCallersOnly(
        EntryPoint = "Add",
        CallConvs = new[] { typeof(CallConvStdcall) })]
    public static int Add(int a, int b)
    {
        return a + b;
    }
}
```

`CallConvStdcall` 对应 Windows WinAPI 风格，也是让导出函数在 DLL 符号表里可见的必要条件。

## 构建命令

普通的 `dotnet build` 只会产出托管 .NET DLL，**不会**生成原生二进制。要生成原生 DLL，必须用 `dotnet publish`：

```powershell
dotnet publish -c Release -r win-x64 /p:PublishAot=true
dotnet publish -c Release -r win-x86 /p:PublishAot=true
```

如果你同时要支持 32 位调用方（比如 FoxPro x86），就需要分别发布两个目标平台。

发布完成后，在 `publish` 目录里会看到对应的 `.dll` 文件。一个只包含基础语言特性、没有引入任何库的最小示例大约是 850KB；随着你引入的 .NET 类库增多，体积会快速增长，最终示例样本达到约 1.5MB。

## 字符串传参

和 C/C++ DLL 一样，字符串参数必须走指针。典型的 WinAPI 风格是：输入字符串作为指针读取，输出字符串作为预分配缓冲区由调用方传入：

```csharp
[UnmanagedCallersOnly(
    EntryPoint = "StringInStringOut",
    CallConvs = new[] { typeof(CallConvStdcall) })]
public static int StringInStringOut(IntPtr input, IntPtr output)
{
    string inputStr = Marshal.PtrToStringAnsi(input) ?? string.Empty;
    string outputStr = Marshal.PtrToStringAnsi(output) ?? string.Empty;

    if (outputStr.Length < 1)
        return 0;

    var result = inputStr + " !!!";
    WriteAnsiString(output, outputStr.Length, result);
    return outputStr.Length;
}
```

从 FoxPro 调用时，调用方需要预先分配输出缓冲区，然后按引用传入：

```foxpro
DECLARE integer StringInStringOut ;
     IN (lcDll) ;
     string input, string@ output

lcOutput = SPACE(255)
? StringInStringOut("Hello World. Time is: " + TIME(), @lcOutput)
? lcOutput
```

这和调用任何标准 Windows API 完全一致——没有任何 .NET 特有的魔法。

## 对象和结构体传参

如果需要传递复杂数据，最可控的方式是使用固定布局的结构体（`StructLayout`）：

```csharp
[StructLayout(LayoutKind.Sequential, Pack = 1, CharSet = CharSet.Ansi)]
public struct PersonInfo
{
    public int Id;
    public double Amount;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)]
    public string Name;
}

[UnmanagedCallersOnly(
    EntryPoint = "ProcessPerson",
    CallConvs = new[] { typeof(CallConvStdcall) })]
public static int ProcessPerson(IntPtr personPtr)
{
    if (personPtr == IntPtr.Zero)
        return -1;

    var person = Marshal.PtrToStructure<PersonInfo>(personPtr);

    person.Id += 100;
    person.Amount += 10.00;
    person.Name = "Updated from .NET";

    Marshal.StructureToPtr(person, personPtr, false);
    return person.Id - 100;
}
```

调用方需要自己按字节布局构造二进制缓冲区，读取时也要手动按偏移拆解。这并不比 C/C++ DLL 更优雅，但逻辑代码确实可以用 C# 写了。

## 这个方案适合哪些场景

Rick 自己的结论是：**使用场景相当窄**。

对于大多数有 COM 支持的环境（比如 Visual Basic、脚本语言），更推荐走传统的 COM 互操作路径，或者借助 [wwDotnetBridge](https://github.com/RickStrahl/wwDotnetBridge) 来宿主 .NET Runtime。这样可以获得更清晰的调用接口，性能损耗在 JIT 预热之后也几乎可以忽略。

AOT DLL 真正有价值的地方在于：

- **没有 COM 支持的调用环境**：Python、纯 C 程序、嵌入式脚本等
- **想彻底摆脱 C++ 工具链**：省去 MSVC、C++ SDK、ATL 等依赖的安装和版本维护
- **需要极小的启动开销**：原生 DLL 加载比 .NET Runtime 宿主快得多
- **某些引导层（bootstrapping）场景**：Rick 提到可能会用它重写 wwDotnetBridge 的 C++ 引导 DLL

但如果你的目标是让 DLL 回传一个 .NET 对象引用或使用完整的 .NET 运行时类库，目前 AOT 还没有内置机制，而且依赖越多 DLL 体积膨胀越快。

## 小结

用 .NET Native AOT 构建 WinAPI 风格 DLL 的完整步骤：

1. Class Library 项目，设置 `PublishAot=true` 和 `NativeLib=Shared`
2. 用 `[UnmanagedCallersOnly(CallConvs = new[] { typeof(CallConvStdcall) })]` 标记导出方法
3. 字符串和对象传参必须走指针和 `Marshal`，和 C DLL 没有区别
4. 用 `dotnet publish -r win-x64` 生成原生 DLL，按需发布多个平台
5. 适合场景：替换 C++ DLL、无 COM 调用环境、需要原生加载性能

这条路子并不神奇，依然要面对 C 风格接口的繁琐。但如果你正好要替换一批古老的 C/C++ DLL，又不想再折腾 C++ 工具链，.NET AOT 是个值得认真考虑的选项。

## 参考

- [Using .NET Native AOT to build Windows WinAPI Dlls（原文）](https://weblog.west-wind.com/posts/2026/Mar/21/Using-NET-Native-AOT-to-build-Windows-WinAPI-Dlls)
- [wwDotnetBridge - GitHub](https://github.com/RickStrahl/wwDotnetBridge)
- [vfp2c32 - FoxPro 结构体辅助库](https://github.com/ChristianEhlscheid/vfp2c32)
