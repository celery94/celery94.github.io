---
pubDatetime: 2026-07-09T08:15:50+08:00
title: "一个 NuGet 包同时支持 .NET 6、.NET 8 和 .NET Standard"
description: "只改一个属性，就能让同一个 NuGet 包给 .NET 6、.NET 8 和老框架各自发一份专属程序集。本文讲清楚 TargetFrameworks 怎么配、条件编译怎么写、依赖怎么按框架隔离，以及打包后如何验证。"
tags: ["NuGet", ".NET", "多目标框架", ".NET Standard", "条件编译"]
slug: "multitarget-nuget-package-net6-net8-netstandard"
source: "https://www.devleader.ca/2026/07/08/how-to-multitarget-a-nuget-package-for-net-6-net-8-and-net-standard"
ogImage: "../../assets/934/01-cover.png"
---

如果你写过要给别人用的类库，多半遇到过这个问题：有人还在 .NET Framework 上跑，有人已经上 .NET 8，还有人卡在 .NET 6。你总不能为每个运行时单独发一个包。多目标（multi-target）打包就是解决这个的——一个 `.nupkg` 文件里塞进几份分别编译好的程序集，安装时 NuGet 自动挑最合适的那份给用户。

这篇讲清楚怎么把它配对：属性名怎么写、TFM 字符串怎么选、按框架分支的代码怎么用 `#if` 隔离、依赖怎么按框架挂、以及打包之后怎么确认输出没错。整套东西 .NET SDK 原生支持，不需要任何插件或自定义 MSBuild 脚本。

## 先分清 TargetFramework 和 TargetFrameworks

刚开始做多目标时，最常见的坑就是这个。`.csproj` 里有两个长得几乎一样的属性：

- `<TargetFramework>`（单数）——只针对**一个**框架
- `<TargetFrameworks>`（复数）——同时针对**多个**框架

这不是打字失误，两者也不能互换。.NET SDK 是专门检查复数形式来决定要不要为多个 TFM 构建的。如果你写成 `<TargetFramework>net6.0;net8.0</TargetFramework>`（单数加分号），构建会立刻失败，报一个无法识别框架标识符的错误。

用复数 `<TargetFrameworks>` 时，SDK 会按列表里的每个 TFM 各构建一次，每份输出落到自己的子目录里。打包时 NuGet 读取这些子目录名，在用户安装时挑最匹配的一份。整个机制就靠这个复数属性名撑着。

应用程序项目用单数没问题。但只要你打算把类库作为 NuGet 包分发，基本都该用复数。

## 常见的 TFM 标识符

配多目标包，第一件事是知道每个平台对应的 TFM 字符串。TFM（Target Framework Moniker，目标框架标识符）就是代表某个具体框架版本的短字符串。对现代 .NET 类库作者来说，最常用的是这些：

| TFM              | 说明                                                           |
| ---------------- | -------------------------------------------------------------- |
| `net6.0`         | .NET 6（LTS，支持到 2024 年 11 月）                            |
| `net7.0`         | .NET 7（STS，18 个月支持周期）                                 |
| `net8.0`         | .NET 8（LTS，支持到 2026 年 11 月）                            |
| `net9.0`         | .NET 9（STS，18 个月支持周期）                                 |
| `net10.0`        | .NET 10（LTS，2025 年 11 月发布）                              |
| `netstandard2.0` | .NET Standard 2.0——可跑在 .NET 4.6.1+、.NET Core 2.0+、Xamarin |
| `netstandard2.1` | .NET Standard 2.1——.NET Core 3.0+，**不支持** .NET Framework   |
| `net48`          | .NET Framework 4.8                                             |

LTS（长期支持）意味着三年官方支持，STS（标准支持）是 18 个月。对多数类库来说，盯住 LTS 版本再加一个 .NET Standard 2.0，就能用最小的维护成本换到最广的覆盖面。

有个关键区别要记住：`netstandard2.1` 不支持 .NET Framework。如果你需要 .NET Framework 用户能装你的包，正确选择是 `netstandard2.0`，而不是 `netstandard2.1`。

## 在 .csproj 里配多目标

配置从改一个属性开始。下面是一个同时支持 .NET 6、.NET 8 和 .NET Standard 2.0 的类库的写法：

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFrameworks>net6.0;net8.0;netstandard2.0</TargetFrameworks>
    <Nullable>enable</Nullable>
    <LangVersion>latest</LangVersion>
    <ImplicitUsings>enable</ImplicitUsings>

    <!-- 包元数据 -->
    <PackageId>MyAwesomeLibrary</PackageId>
    <Version>1.0.0</Version>
    <Authors>Your Name</Authors>
    <Description>A library that targets multiple .NET frameworks.</Description>
  </PropertyGroup>

</Project>
```

关键那一行是 `<TargetFrameworks>net6.0;net8.0;netstandard2.0</TargetFrameworks>`，分号分隔每个 TFM。其余的 SDK 全包了。

跑 `dotnet build` 时，SDK 会按顺序把项目构建三遍，每个 TFM 一遍。输出分别落在 `bin/Debug/net6.0/`、`bin/Debug/net8.0/`、`bin/Debug/netstandard2.0/`。之后 `dotnet pack` 会把它们组装进 `.nupkg` 里正确的目录结构。

开发时如果只想快速验证一个框架，可以只针对单个 TFM 构建：

```bash
dotnet build -f net8.0
dotnet test -f net8.0
```

`-f`（或 `--framework`）把构建限制到一个 TFM。迭代某个功能、不想每次都重建所有目标时，这个很省时间。

## 用 #if 做条件编译

当你需要为不同框架写不同实现时，多目标才真正显出威力。.NET SDK 会根据当前正在编译的 TFM 自动定义预处理符号，命名遵循 `[TFM]_OR_GREATER` 这种"版本及以上"的模式。

常用的符号有：

- `NET6_0_OR_GREATER`——.NET 6、7、8、9、10+ 都为真
- `NET8_0_OR_GREATER`——.NET 8、9、10+ 为真
- `NETSTANDARD2_0`——只在 .NET Standard 2.0 构建时为真
- `NETSTANDARD2_1`——只在 .NET Standard 2.1 构建时为真
- `NETFRAMEWORK`——任何 .NET Framework 目标都为真

举个实际例子。假设你的库封装了 `HttpClient`。.NET 5+ 提供了同步版本的 `HttpClient.Send(HttpRequestMessage)`，这个 API 在 .NET Standard 2.0 里没有。你可以按条件只在支持的框架上暴露它：

```csharp
using System.Net.Http;

public sealed class MyHttpWrapper
{
    private readonly HttpClient _client;

    public MyHttpWrapper(HttpClient client)
    {
        _client = client;
    }

    // 所有目标框架都可用
    public async Task<string> GetStringAsync(string url)
    {
        var response = await _client.GetAsync(url);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStringAsync();
    }

#if NET6_0_OR_GREATER
    // 只为矩阵里 .NET 6+ 的目标编译。HttpClient.Send 其实从 .NET 5 就有，
    // 但我们的矩阵从 net6.0 起步，所以守卫写 NET6_0_OR_GREATER。
    // 如果你的矩阵包含 net5.0，就改用 NET5_0_OR_GREATER。
    public string GetString(string url)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, url);
        var response = _client.Send(request);
        response.EnsureSuccessStatusCode();
        return response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
    }
#endif
}
```

这个 `#if NET6_0_OR_GREATER` 块会被编进矩阵里所有 .NET 6 及以上的目标——这里就是 `net6.0` 和 `net8.0`。`netstandard2.0` 那次构建会整块跳过。于是你的 .NET Standard 用户看到的是干净的 API，不会碰到他们平台上根本不存在的方法。

也可以串起来处理版本特定的分支：

```csharp
#if NET8_0_OR_GREATER
    // FrozenSet<T> 是 .NET 8 引入的——用它做零分配查找
    var lookup = items.ToFrozenSet();
#elif NET6_0_OR_GREATER
    // .NET 6 的退路——HashSet 就够了
    var lookup = new HashSet<string>(items);
#else
    // .NET Standard 2.0 的退路
    var lookup = new HashSet<string>(items);
#endif
```

条件块要小而聚焦。大段的 `#if` 代码会变得难读、难测、难维护。如果某个 TFM 需要的逻辑差异很大，考虑用分部类（partial class）或者一个适配层，别堆一墙预处理指令。

## 依赖按框架隔离

有时候你的库依赖的某个 NuGet 包只对特定目标有意义。比如某个兼容性垫片只有老运行时才需要，某个高性能库只能编在 .NET 8+ 上。你可以用 `Condition` 属性把任何 `<PackageReference>` 限定到特定 TFM：

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFrameworks>net6.0;net8.0;netstandard2.0</TargetFrameworks>
  </PropertyGroup>

  <ItemGroup>
    <!-- 所有目标都可用 -->
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
  </ItemGroup>

  <ItemGroup>
    <!-- System.Memory 为 .NET Standard 2.0 提供 Span<T> 兼容垫片 -->
    <PackageReference Include="System.Memory" Version="4.5.5"
      Condition="'$(TargetFramework)' == 'netstandard2.0'" />
  </ItemGroup>

  <ItemGroup>
    <!-- Microsoft.Extensions.ObjectPool 8.x 针对 .NET 8 API -->
    <PackageReference Include="Microsoft.Extensions.ObjectPool" Version="8.0.0"
      Condition="'$(TargetFramework)' == 'net8.0'" />
  </ItemGroup>

</Project>
```

`Condition` 用的是 MSBuild 的属性语法。`'$(TargetFramework)'` 在每一次构建时会求值为当前正在构建的那个 TFM。`System.Memory` 只在构建 `netstandard2.0` 时被拉进来，.NET 8 用户的传递依赖图里根本看不到它。

这对用户很重要。你每加一个无条件的依赖，所有用户不管什么运行时都会背上它。把依赖收窄到需要的框架，能让包保持轻量，也避免下游项目里的版本冲突。

## 怎么选目标框架组合

做多目标包最重要的决定之一，是到底要包含哪些 TFM。不是每个库都得覆盖所有框架。目标越多，构建越慢，维护成本越高。给一个务实的判断框架：

**想要最广覆盖，就带上 .NET Standard 2.0。** 它能跑在 .NET Framework 4.6.1+、.NET Core 2.0+、Xamarin 上。现有 .NET 生态里相当大一部分都能装 `netstandard2.0` 的包。

**当库能从新 API、性能改进（比如免兼容包的 `Span<T>`）或平台特性中获益时，带上现代 LTS 版本**（net6.0、net8.0）。.NET 8 用户会拿到专门为他们编的程序集，没有垫片开销。

**跳过中间的 STS 版本**（net7.0、net9.0），除非你有绑定到那个确切版本的 API 需求。`_OR_GREATER` 的约定意味着跑 .NET 7 的用户会直接用你的 `net6.0` 程序集——照样能跑，没把谁晾着。

给新库一个稳妥的起步组合：

```xml
<TargetFrameworks>net8.0;net6.0;netstandard2.0</TargetFrameworks>
```

这覆盖了拿最新 API 的 .NET 8 用户、在长期部署里的 .NET 6 用户，以及通过 .NET Standard 2.0 兜底的其他所有人。要注意 .NET 6 LTS 已在 2024 年 11 月结束——如果你是在 2026 年中开新库，把 `net6.0` 换成 `net10.0`（2025 年 11 月发布）是更面向未来的选择。矩阵保持精简，能直接减少 CI 构建时间和你要排查的问题面。

## .NET Standard 2.0：兼容性基线

.NET Standard 2.0 值得单独说，因为它是 .NET 生态里覆盖最广的一层兼容层。它定义了一套通用 API 契约，任何符合它的运行时都必须实现。正是这套契约，让同一份 `netstandard2.0` 程序集能跑在：

- .NET Framework 4.6.1、4.7.x、4.8.x
- .NET Core 2.0、2.1、3.0、3.1
- .NET 5、6、7、8、9、10
- Xamarin iOS、Android、macOS
- Unity（有一些限制）

代价是 API 面更小。你会失去免兼容包的 `Span<T>`、`IAsyncEnumerable<T>`（在 netstandard2.0 上要靠 `Microsoft.Bcl.AsyncInterfaces` 这个 NuGet 包，而不是 BCL 内置）、高性能形态的 `System.Text.Json`，以及很多较新的 BCL 类型。写性能敏感的代码时，这些都是实打实的限制。

.NET Standard 2.1 把 API 面扩大了不少——但它永久放弃了 .NET Framework 支持。.NET 团队明确说过 .NET Framework 永远不会实现 .NET Standard 2.1。所以只要你的用户里还有人在乎 .NET Framework，`netstandard2.0` 就是兼容目标的天花板。

如果你在做一个会被其他库依赖的抽象层或工具库，用 `netstandard2.0` 作基线能保证最大的可组合性。

## 源生成器的多目标注意点

源生成器（source generator）有它自己的多目标要求，虽然值得单开一篇细讲。源生成器项目必须专门针对 `netstandard2.0`，因为 Roslyn（编译器宿主）就这么要求。这跟你主库支持的最终用户 TFM 是两回事。你的生成器和你的库可以有不同的 `<TargetFrameworks>` 值，这是正常的。

## 打包后验证输出

跑完 `dotnet pack`，要确认生成的 `.nupkg` 里确实为每个目标都放了程序集。多目标包只有在每个列出的 TFM 都在 `lib/` 里有自己的程序集时才算正确——少任何一个，那个平台的用户装包时就会报"没有兼容框架"的错。

`.nupkg` 本质就是个 ZIP。你可以改名成 `.zip` 用资源管理器打开，或者用 NuGet Package Explorer，也可以直接在命令行里查。

一个针对 `net6.0;net8.0;netstandard2.0` 的包，`lib/` 结构应该长这样：

```
MyAwesomeLibrary.1.0.0.nupkg
└── lib/
    ├── net6.0/
    │   └── MyAwesomeLibrary.dll
    ├── net8.0/
    │   └── MyAwesomeLibrary.dll
    └── netstandard2.0/
        └── MyAwesomeLibrary.dll
```

用 PowerShell 在 `dotnet pack` 之后从命令行验证：

```powershell
# 以 Release 配置打包
dotnet pack -c Release

# 查看 .nupkg 里 lib/ 目录的内容
$pkg = Get-Item ./bin/Release/*.nupkg | Select-Object -First 1
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($pkg.FullName)
$zip.Entries | Where-Object { $_.FullName -match '^lib/' } | Select-Object FullName
$zip.Dispose()

# 预期输出：
# lib/net6.0/MyAwesomeLibrary.dll
# lib/net8.0/MyAwesomeLibrary.dll
# lib/netstandard2.0/MyAwesomeLibrary.dll
```

如果 `lib/` 里少了某个 TFM，那个平台的用户装包时就会在安装环节报"没有兼容框架"。这个检查几秒钟就能做，发布前跑一下，能省掉推一个坏包的麻烦。

你也可以用最小详细度构建，顺便数一下成功的次数：

```bash
dotnet build -v minimal
```

配了三个 TFM，你应该看到三趟独立的构建各自成功完成。如果哪个 TFM 编译失败，输出会在打包前把出错的地方列出来。

## 常见问题

**TargetFramework 和 TargetFrameworks 有什么区别？**
单数只为一个平台构建，复数在一条命令里为多个平台构建。单数形式带分号（`net6.0;net8.0`）会立刻构建报错——SDK 不会把单数里的分号当列表解析。想多目标，永远用复数。

**能不能不用条件编译就做多目标？**
能。如果你的公开 API 在所有目标框架上完全一致，也没用到任何 TFM 特定的 API，就不需要任何 `#if`。把框架列进 `<TargetFrameworks>`，SDK 会各构建一遍，不用改代码。只有当实现要按 TFM 分叉时，才需要条件编译。

**带上 netstandard2.0 会让 .NET 8 用户拿到更慢的程序集吗？**
不会。只要你在 `<TargetFrameworks>` 里也列了 `net8.0`，NuGet 会为每个用户挑最具体的匹配。.NET 8 项目拿到 `net8.0` 程序集，`netstandard2.0` 那份只给那些匹配不上更具体 TFM 的运行时用。多目标始终是增量的，你不会因为顺带支持旧平台而惩罚现代用户。

**新库在 2026 年最少该支持哪些 TFM？**
一个务实的最小组合是 `net8.0;net10.0;netstandard2.0`，覆盖两个当前 LTS 版本，其余（含 .NET Framework）用 .NET Standard 2.0 兜底。加 `net6.0` 已经不推荐了，它的 LTS 支持在 2024 年 11 月就结束了。随着 LTS 周期关闭，你可以在库的下一个大版本里逐步删掉旧 TFM。

## 小结

多目标打包归根结底就是几个刻意的决定：`<TargetFrameworks>` 里列哪些 TFM、哪里需要 `#if` 分叉框架特定代码、怎么用 `Condition` 把依赖按框架隔离、以及发布前怎么验证 `.nupkg` 的 `lib/` 结构。

起步组合建议：用 .NET Standard 2.0 换广兼容，再至少带一个当前 LTS 版本拿新 API。用 `NET6_0_OR_GREATER`、`NET8_0_OR_GREATER` 这类符号在平台 API 有差异的地方分支。用 `Condition` 收窄依赖，让用户的依赖图保持精简。最后验证打包输出，确认所有该有的 `lib/` 子目录都在，再推到 NuGet.org。

## 参考

- [How to Multi-Target a NuGet Package for .NET 6, .NET 8, and .NET Standard](https://www.devleader.ca/2026/07/08/how-to-multitarget-a-nuget-package-for-net-6-net-8-and-net-standard)
- [The Complete Guide to Creating NuGet Packages in .NET](https://www.devleader.ca/2026/07/01/the-complete-guide-to-creating-nuget-packages-in-net)
  </content>
  </invoke>
