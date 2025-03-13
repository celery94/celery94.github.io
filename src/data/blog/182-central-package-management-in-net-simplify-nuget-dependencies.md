---
pubDatetime: 2024-12-07
tags: []
source: https://www.milanjovanovic.tech/blog/central-package-management-in-net-simplify-nuget-dependencies
author: Milan Jovanović
title: .NET中的中央包管理 - 简化NuGet依赖
description: 在多个 .NET 项目中管理 NuGet 包曾经是一个版本不匹配和维护麻烦的噩梦，但中央包管理 (CPM) 提供了一个强大的解决方案，让你可以从单一真实来源控制所有包版本。了解 CPM 如何简化你的依赖管理，防止版本冲突，并使你的 .NET 开发工作流程更加顺畅。
---

# .NET中的中央包管理 - 简化NuGet依赖

我还记得那时候在多个项目中管理NuGet包是多么麻烦。你知道我在说什么——打开一个大型解决方案，发现每个项目都使用了同一个包的不同版本。真是糟糕透了！

让我向你展示一下.NET中的**中央包管理**（CPM）如何一劳永逸地解决这个问题。

## [我们需要解决的问题](#the-problem-we-need-to-solve)

我经常处理包含很多项目的解决方案。有些解决方案常常包含30个或更多项目。每个项目都需要类似Serilog或Polly这样的包。我创建的大多数测试项目依赖于xUnit。在使用CPM之前，跟踪包版本是一团糟：

- 一个项目使用Serilog `4.1.0`
- 另一个使用Serilog `4.0.2`
- 不知为何，还有一个使用Serilog `3.1.1`

这会导致真正的问题。不同版本可能表现不同，导致难以追踪的奇怪错误。我浪费了很多时间来修复由版本不匹配引起的问题。

## [中央包管理如何提供帮助](#how-central-package-management-helps)

把CPM想象成你所有包版本的控制中心。你不需要在每个项目中设置版本，只需在一个地方设置一次。然后，你只需引用想要使用的包，而无需指定版本。就这么简单。

以下是你使用[中央包管理](https://learn.microsoft.com/en-us/nuget/consume-packages/central-package-management)所需的条件：

- NuGet 6.2或更新版本
- .NET SDK 6.0.300或更新版本
- 如果你使用Visual Studio，需要2022 17.2或更新版本

## [设置步骤](#setting-it-up)

让我告诉你如何设置CPM。这比你想象的要简单。

1.  首先，在解决方案的主文件夹中创建一个名为`Directory.Packages.props`的文件：

```
<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Newtonsoft.Json" Version="13.0.3" />
    <PackageVersion Include="Serilog" Version="4.1.0" />
    <PackageVersion Include="Polly" Version="8.5.0" />
  </ItemGroup>
</Project>
```

注意使用`PackageVersion`定义NuGet依赖项。

2.  在你的项目文件中，可以使用`PackageReference`列出包而无需版本组件：

```
<ItemGroup>
  <PackageReference Include="Newtonsoft.Json" />
  <PackageReference Include="AutoMapper" />
  <PackageReference Include="Polly" />
</ItemGroup>
```

就这样！现在你所有的项目都将使用相同的包版本。

## [你可以做的酷事](#cool-things-you-can-do)

### [某个项目需要不同版本？](#need-a-different-version-for-one-project)

有时候你可能需要特定项目使用不同的版本。没问题！只需在你的项目文件中添加：

```
<PackageReference Include="Serilog" VersionOverride="3.1.1" />
```

`VersionOverride`属性让你可以定义你想使用的特定版本。

### [想在每个项目中都使用一个包？](#want-a-package-in-every-project)

如果你有每个项目都需要的包，你可以让它们变成全局的。在你的props文件中定义一个`GlobalPackageReference`：

```
<ItemGroup>
  <GlobalPackageReference Include="SonarAnalyzer.CSharp" Version="10.3.0.106239" />
</ItemGroup>
```

现在每个项目都会自动获取这个包！

## [将现有项目迁移到中央包管理](#migrating-existing-projects-to-central-package-management)

1.  在解决方案根目录下创建`Directory.Packages.props`文件
2.  将所有包版本从你的`.csproj`文件中移动
3.  从`PackageReference`元素中移除版本属性
4.  构建你的解决方案并修复任何版本冲突
5.  在提交之前彻底测试

这是一个列出你解决方案中所有NuGet包版本的Powershell脚本：

```
# 扫描所有.csproj文件并聚合唯一的包版本
$packages = Get-ChildItem -Filter *.csproj -Recurse |
    Get-Content |
    Select-String -Pattern '<PackageReference Include="([^"]+)" Version="([^"]+)"' -AllMatches |
    ForEach-Object { $_.Matches } |
    Group-Object { $_.Groups[1].Value } |
    ForEach-Object { @{
        Name = $_.Name
        Versions = $_.Group.ForEach({ $_.Groups[2].Value }) | Select-Object -Unique
    }} |
    Sort-Object { $_.Name }

# 显示结果
$packages | ForEach-Object {
    "$($_.Name) versions:"
    $_.Versions | ForEach-Object { "  $_" }
}
```

## [何时应该使用CPM？](#when-should-you-use-cpm)

我没有看到不默认使用它的理由。

我建议在以下情况下使用CPM：

- 你有很多共享包的项目
- 你厌倦了修复与版本相关的错误
- 你想确保每个人都使用相同的版本

我最近在一个包含30个项目的解决方案中添加了CPM。

结果是：

- 减少了合并冲突
- 及早发现版本问题
- 让新团队成员更容易上手

这在从.NET 8迁移到.NET 9时特别有用。

你可以将CPM与[**构建配置和静态代码分析**](https://www.milanjovanovic.tech/blog/improving-code-quality-in-csharp-with-static-code-analysis)结合使用。

## [总结](#wrapping-up)

关于**中央包管理**成功的建议：

1.  当你将CPM添加到现有解决方案时，独立进行更改/PR
2.  如果你覆盖了一个版本，添加一个注释说明原因
3.  定期检查你的包版本以获取更新
4.  只有在真正需要的时候才将包设置为全局

自从我开始使用中央包管理后，管理NuGet包变得容易多了。就像拥有一个所有包版本的单一真实来源。
