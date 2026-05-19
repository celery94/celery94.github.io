---
pubDatetime: 2026-05-19T07:48:38+08:00
title: ".NET 10 NuGet 包裁剪：减少 70% 误报漏洞，restore 最多快 50%"
description: ".NET 10 默认开启 NuGet 包裁剪（Package Pruning），在 restore 时自动移除 .NET 运行时已内置的包。Microsoft 遥测显示，与旧默认值相比，传递性漏洞误报减少 70%，restore 时间最多降低 50%。"
tags: ["dotnet", "NuGet", "dotnet10", "安全"]
slug: "nuget-package-pruning-dotnet-10"
ogImage: "../../assets/808/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/nuget-package-pruning-in-dotnet-10/"
---

![NuGet 包裁剪封面](../../assets/808/01-cover.png)

如果你在 .NET 项目上跑过 NuGet Audit 或漏洞扫描器，大概见过一批针对从未显式安装的传递性包的警告。其中很多是 `System.Text.Json`、`System.Text.Encodings.Web` 这类——它们早已被更新版本的 .NET 运行时库提供，扫描器报出的是误报。

.NET 10 把两件事变成了默认行为：`NuGetAuditMode` 设为 `all`（审计传递依赖），以及**包裁剪**（`RestoreEnablePackagePruning=true`）——在 restore 时把运行时已内置的包从依赖图里移除。Microsoft 遥测显示，采用新默认值的项目，传递性漏洞报告比旧默认值减少了 **70%**。

## 问题的根源

nuget.org 上大量类库为了兼容性仍然以 `netstandard2.0` 为目标，并带着 `System.Memory`、`System.Text.Json` 等依赖——这些包如今已是 .NET 运行时库的一部分。随着平台演进，曾经独立发布的包会逐步并入运行时。`System.IO.Pipelines` 就是典型：最初是独立 NuGet 包，后来成了平台内置组件。

这就导致了三个问题：

- **误报漏洞警告**：某个平台内置包发布 CVE 时，NuGet Audit 会把它作为传递性漏洞报出来，即使 .NET 运行时已提供了修复版本。包在图里，但应用实际用的不是那个版本。
- **更大的 restore 图**：更多包意味着更多下载、更多图条目、更多噪音。
- **过时的包引用**：旧版包留在图里，即使应用实际运行时用的是 .NET 运行时的内置实现。

## 包裁剪是什么

包裁剪在 restore 时从 NuGet 依赖图中移除平台内置包。.NET SDK 内置了一份每个目标框架所提供包的列表，以及对应的最高版本。如果某个传递依赖在该范围内，NuGet 就将其裁剪掉。

例如，`net8.0` 包含 `System.Text.Json 8.0.x`，所以当目标是 `net8.0` 时，传递依赖的 `System.Text.Json 9.0.0` **不会**被裁剪（平台提供的版本不够新）。

裁剪时的行为分两种：

- **传递性包**：直接从图中移除，不下载、不出现在 restore 输出里、不被 audit 报出。
- **直接 `PackageReference`**：NuGet 自动应用 `PrivateAssets='all'` 和 `IncludeAssets='none'`，明确表示将使用运行时版本，该包不会流入发布的 nuspec。引用会留在项目文件里，直到你手动删除。

当某个直接引用在所有目标框架里都可裁剪时，NuGet 会发出 **NU1510** 警告，提示可以将其从项目文件中移除。

## Before / After 对比

以一个面向 `net10.0`、引用了 `Microsoft.Extensions.AI` 和 `NuGet.Protocol` 的项目为例：

**裁剪前**，`dotnet list package --include-transitive` 会看到：

```
Sample.csproj : warning NU1903: Package 'System.Formats.Asn1' 6.0.0 has a known high severity vulnerability

Transitive Package                                           Resolved
> System.Diagnostics.DiagnosticSource                        10.0.0
> System.Formats.Asn1                                        6.0.0   ← 有漏洞，误报
> System.Text.Json                                           10.0.0
> System.Threading.Channels                                  10.0.0
...（共 18 个传递依赖）
```

**裁剪后**，`System.Formats.Asn1` 从传递图中消失，漏洞警告消失。`System.Diagnostics.DiagnosticSource`、`System.Text.Json`、`System.Threading.Channels` 等平台内置包也一并被裁剪：

```
Transitive Package                                           Resolved
> Microsoft.Extensions.AI.Abstractions                       10.0.1
> Microsoft.Extensions.Caching.Abstractions                  10.0.0
> ...
> System.Numerics.Tensors                                    10.0.0
> System.Security.Cryptography.Pkcs                          6.0.4
> System.Security.Cryptography.ProtectedData                 4.4.0
...（共 14 个传递依赖，减少 4 个平台内置包）
```

依赖树更深、引用了更多平台内置包的项目，裁剪效果会更显著。

## .NET 10 里的变化

包裁剪最初在 .NET SDK 9.0.200 作为可选功能发布。**在 .NET 10，它成为默认体验。**

对于目标框架包含 `net10.0` 或更高版本的项目：

- 包裁剪默认启用
- 在裁剪范围内的直接 `PackageReference` 会被自动私有化，NU1510 信号提示可完全移除的引用
- 多目标项目中，只要有一个目标框架是 `net10.0+`，裁剪就会应用到所有目标框架

与此同时，`NuGetAuditMode` 在 .NET 10 默认改为 `all`，即默认审计传递依赖。两者配合：裁剪把平台内置包从图中移除，审计范围扩展到剩余的传递依赖，让你看到的是应用**真正使用**的包里存在的实际漏洞。

Microsoft 遥测数据：

- 启用默认配置的项目，传递性漏洞报告减少 **70%**
- 启用裁剪后，restore 成功率可测量地高于未启用时
- 单项目维度，包裁剪可减少 restore 时间最多 **50%**

如果需要手动配置，对应的属性是：

```xml
<!-- .NET 10 默认值 -->
<PropertyGroup>
  <NuGetAuditMode>all</NuGetAuditMode>
  <RestoreEnablePackagePruning>true</RestoreEnablePackagePruning>
</PropertyGroup>
```

## 总结

包裁剪让 NuGet 依赖图更真实地反映应用实际依赖的内容。在 .NET 10 里，这意味着：

- 传递性漏洞误报大幅减少（遥测 -70%）
- restore 图更小，速度更快（最多 -50%）
- 审计结果更可操作，聚焦于真实依赖

随着更多包并入 .NET 运行时库，裁剪会持续把依赖图集中在真实依赖上，而不是平台已内置的冗余引用。

## 参考

- [NuGet Package Pruning: Cleaner Dependencies and Actionable Vulnerability Reports - .NET Blog](https://devblogs.microsoft.com/dotnet/nuget-package-pruning-in-dotnet-10/)
- [NuGet 包裁剪文档](https://learn.microsoft.com/en-us/nuget/consume-packages/package-pruning)
