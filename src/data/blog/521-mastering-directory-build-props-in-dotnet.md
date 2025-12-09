---
pubDatetime: 2025-12-09
title: "在 .NET 中掌握 Directory.Build.props"
description: "深入解析 Directory.Build.props 的强大功能，学习如何通过集中化配置简化 .NET 项目管理，统一代码风格，以及实现高效的版本控制。"
tags: [".NET", "MSBuild", "Architecture", "Productivity"]
slug: "mastering-directory-build-props-in-dotnet"
source: "https://thecodeman.net/posts/mastering-directory-build-props-in-dotnet"
---

# 在 .NET 中掌握 Directory.Build.props

## 引言

每一位 .NET 开发者最终都会遇到那堵“墙”：

- 解决方案中包含 20 多个项目。
- 20 多个项目里重复着相同的 `TargetFramework`、`Nullable` 和 `LangVersion` 配置。
- 20 多个地方需要手动开启 `TreatWarningsAsErrors`。
- 20 多个 `.csproj` 文件充斥着重复的 `PackageReference` 和构建设置。

当你想要调整一个设置时，你不得不花费大量时间在整个解决方案中逐个修改。

在 .NET 9（以及任何现代 SDK 风格的项目）中，有一个更好的方法：使用 `Directory.Build.props`。

通过这一个文件，你可以：

- 为目录树下的所有项目定义全局构建规则。
- 保持每个 `.csproj` 文件小巧且专注。
- 标准化代码风格、分析器和警告。
- 从一个地方控制所有程序集的版本和元数据。

本文将带你深入了解 `Directory.Build.props` 的工作原理，并通过一个实战场景展示如何利用它来清理和优化你的 .NET 解决方案。

## 什么是 Directory.Build.props？

`Directory.Build.props` 是一个 MSBuild 文件，MSBuild 会在加载你的项目文件之前自动导入它。你在其中定义的任何属性和项（Items）都将应用于该目录及其子目录下的所有项目。

导入过程的工作原理如下：

1.  当 MSBuild 加载一个项目（例如 `Api.csproj`）时，它首先导入 `Microsoft.Common.props`。
2.  `Microsoft.Common.props` 会从项目所在的文件夹开始，沿着目录树向上查找，寻找第一个 `Directory.Build.props` 文件。
3.  一旦找到，它就会导入该文件。
4.  `Directory.Build.props` 中定义的任何内容现在都可以在项目文件中使用了。

这意味着：

- 将 `Directory.Build.props` 放在解决方案根目录 → 下面的每个项目都会继承它。
- 在 `tests/` 目录下放另一个 `Directory.Build.props` → 测试项目可以在根配置的基础上添加额外的设置。
- 如果你在某个项目旁边放一个空的 `Directory.Build.props`，MSBuild 就会在那里停止向上搜索，从而有效地屏蔽上层的配置。

这在 .NET 9 中的工作方式与之前的现代 SDK 版本相同，但区别在于 .NET 9 项目通常更依赖于分析器、可空引用类型和现代构建特性，这使得集中化配置变得更加有价值。

## 实战场景：清理 .NET 9 微服务解决方案

想象一下，你正在处理一个结构如下的真实解决方案：

```text
src/
    Api/
        Api.csproj
    Worker/
        Worker.csproj
    Web/
        Web.csproj
tests/
    Api.Tests/
        Api.Tests.csproj
    Worker.Tests/
        Worker.Tests.csproj
    Shared.Testing/
        Shared.Testing.csproj
Directory.Build.props
tests/Directory.Build.props
```

**典型问题：**

- 每个项目都重复配置：
  ```xml
  <TargetFramework>net9.0</TargetFramework>
  <Nullable>enable</Nullable>
  <ImplicitUsings>enable</ImplicitUsings>
  ```
- 每个项目都复制：
  ```xml
  <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  <AnalysisLevel>latest</AnalysisLevel>
  ```
- 所有项目共享相同的公司元数据和仓库 URL。
- 测试项目重复引用 `xunit`、`FluentAssertions` 和 `coverlet.collector`。

如果你想将 `TargetFramework` 从 `net8.0` 更改为 `net9.0`，或者决定加强分析器规则，你必须手动更改每个 `.csproj`。

让我们用 `Directory.Build.props` 来解决这个问题。

## 步骤 1：创建解决方案级 Directory.Build.props

在解决方案根目录下，创建一个名为 `Directory.Build.props` 的文件：

```xml
<Project>
  <!-- 仓库中所有 .NET 9 项目的共享配置 -->
  <PropertyGroup>

    <!-- 目标框架与语言特性 -->
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <LangVersion>latest</LangVersion>

    <!-- 代码质量 -->
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
    <AnalysisLevel>latest</AnalysisLevel>

    <!-- 程序集元数据 -->
    <Company>TheCodeMan</Company>
    <Authors>Stefan Djokic</Authors>
    <RepositoryUrl>https://github.com/thecodeman/your-repo</RepositoryUrl>
    <RepositoryType>git</RepositoryType>

    <!-- 输出布局 -->
    <AppendTargetFrameworkToOutputPath>false</AppendTargetFrameworkToOutputPath>
    <AppendRuntimeIdentifierToOutputPath>false</AppendRuntimeIdentifierToOutputPath>
    <BaseOutputPath>artifacts\bin\</BaseOutputPath>
    <BaseIntermediateOutputPath>artifacts\obj\</BaseIntermediateOutputPath>

  </PropertyGroup>

  <!-- 大多数项目共享的包 -->
  <ItemGroup>
    <PackageReference Include="Microsoft.Extensions.Logging.Abstractions" Version="9.0.0" />
    <PackageReference Include="Microsoft.Extensions.Options.ConfigurationExtensions" Version="9.0.0" />
  </ItemGroup>

</Project>
```

**这带来了什么改变？**

- 每个项目现在都以 `net9.0` 为目标，使用可空引用类型、隐式引用和最新的语言特性。
- 通过 `TreatWarningsAsErrors` 和 `AnalysisLevel` 在所有地方强制执行代码质量。
- 所有二进制文件都输出到 `artifacts\bin\` 和 `artifacts\obj\`，而不是分散在各个 `bin/Debug` 文件夹中。
- 通用的 `PackageReference` 不再需要在每个项目中重复。

现在，你原本臃肿的 `.csproj` 文件可以变得非常精简：

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <AssemblyName>MyCompany.Api</AssemblyName>
  </PropertyGroup>
</Project>
```

更整洁，更容易审查，也更难配置错误。

> **注意**：对于包管理本身（集中版本号），在现代 .NET 中通常会搭配 `Directory.Packages.props` 使用。`Directory.Build.props` 主要用于构建配置，虽然它可以包含 `PackageReference` 作为默认值，但不是专门用于集中包版本管理的。

## 步骤 2：添加测试专用的 Directory.Build.props

现在让我们区别对待测试项目：它们通常需要额外的包和稍微宽松的规则。

创建 `tests/Directory.Build.props`：

```xml
<Project>
  <!-- 对于测试项目，此文件会在根目录的 Directory.Build.props 之后导入 -->

  <PropertyGroup>

    <!-- 可选：测试可能不需要将所有警告视为错误 -->
    <TreatWarningsAsErrors>false</TreatWarningsAsErrors>

    <!-- 将这些程序集标记为测试项目 -->
    <IsTestProject>true</IsTestProject>

  </PropertyGroup>

  <ItemGroup>

    <!-- 共享的测试库 -->
    <PackageReference
        Include="xunit"
        Version="2.9.0" />

    <PackageReference
        Include="xunit.runner.visualstudio"
        Version="2.8.2" />

    <PackageReference
        Include="FluentAssertions"
        Version="6.12.0" />

    <PackageReference
        Include="coverlet.collector"
        Version="6.0.0">
      <PrivateAssets>all</PrivateAssets>
    </PackageReference>

  </ItemGroup>

</Project>
```

**现在的效果：**

- `tests/` 下的任何项目都会自动获得测试包。
- 你可以稍微放宽测试项目的规则（例如，不将警告视为错误），而不影响生产代码。
- 创建新的测试项目变得微不足道——`.csproj` 内部几乎不需要任何构建配置。

## 步骤 3：使用 Directory.Build.props 进行集中版本控制

另一个强大的用例是集中程序集版本控制。与其在每个项目中重复版本信息，不如定义一次，并通过 MSBuild 属性传递 CI 元数据。

扩展根目录的 `Directory.Build.props`：

```xml
<Project>
  <PropertyGroup>

    <!-- 整个解决方案的基础语义版本 -->
    <VersionPrefix>1.4.0</VersionPrefix>

    <!-- 可选的手动设置后缀，用于预发布版本 -->
    <VersionSuffix>beta</VersionSuffix>
    <!-- 例如 "", "beta", "rc1" -->

    <!-- 程序集版本 -->
    <AssemblyVersion>1.4.0.0</AssemblyVersion>

    <!-- FileVersion 可以包含来自 CI 的构建号 -->
    <FileVersion>1.4.0.$(BuildNumber)</FileVersion>

    <!-- InformationalVersion 是你在“产品版本”和 NuGet 中看到的 -->
    <InformationalVersion>$(VersionPrefix)-$(VersionSuffix)+build.$(BuildNumber)</InformationalVersion>

  </PropertyGroup>
</Project>
```

在 CI（GitHub Actions / Azure DevOps / GitLab）中，你可以传递 `BuildNumber`：

```bash
dotnet build MySolution.sln /p:BuildNumber=123
```

**结果：**

- 所有项目共享一致的版本控制。
- 更改一次 `VersionPrefix` 即可升级整个解决方案。
- 通过控制从 CI 传递的属性，你可以区分内部发布版本和部署版本。

## 步骤 4：集中强制代码风格和分析器

你可能已经在使用 `.editorconfig` 了。但是分析器和构建级别的强制执行仍然存在于 MSBuild 中。

`Directory.Build.props` 是连接它们的完美场所：

```xml
<Project>
  <PropertyGroup>

    <!-- 全局强制执行分析器 -->
    <AnalysisLevel>latest</AnalysisLevel>
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>

    <!-- 将所有分析器诊断视为错误（除非被覆盖） -->
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>

  </PropertyGroup>

  <ItemGroup>

    <!-- 示例分析器包 -->
    <PackageReference
        Include="Roslynator.Analyzers"
        Version="4.12.0"
        PrivateAssets="all" />

    <PackageReference
        Include="SerilogAnalyzer"
        Version="0.15.0"
        PrivateAssets="all" />

  </ItemGroup>

</Project>
```

**现在：**

- 每个项目都使用相同的分析器级别和代码风格强制执行。
- 你不必记得在每个 `.csproj` 中添加分析器包。
- 如果有人违反规则，构建就会失败，无论他们的 IDE 设置如何——这对于 CI 和团队一致性来说非常完美。

如果某个特定项目确实需要放宽某些限制，你仍然可以在本地覆盖：

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>

    <!-- 选择退出此项目的全局警告即错误设置 -->
    <TreatWarningsAsErrors>false</TreatWarningsAsErrors>

  </PropertyGroup>
</Project>
```

## 步骤 5：分层与作用域：多个 Directory.Build.props 文件

你不局限于只有一个 props 文件。MSBuild 允许你创建一个 `Directory.Build.props` 文件的层级结构，它会在从项目位置向上遍历目录时选取它找到的第一个文件。

**常见模式：**

- **解决方案根目录**：所有项目的核心设置。
- **src/Directory.Build.props**：仅用于生产代码的设置和包。
- **tests/Directory.Build.props**：仅用于测试的包和宽松规则。
- **tools/Directory.Build.props**：用于不需要分析器或警告即错误的小型 CLI 工具。

**示例结构：**

```text
Directory.Build.props         // 全局默认值
src/Directory.Build.props     // 生产代码的覆盖
tests/Directory.Build.props   // 测试代码的覆盖
tools/Directory.Build.props   // 小型内部工具的覆盖
```

一个 `src/Directory.Build.props` 可能看起来像这样：

```xml
<Project>
  <PropertyGroup>

    <!-- 仅用于生产代码 -->
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
    <GenerateDocumentationFile>true</GenerateDocumentationFile>

    <NoWarn>CS1591</NoWarn>
    <!-- 但不要求到处都有 XML 文档 -->

  </PropertyGroup>
</Project>
```

如果你真的需要一个项目**不继承**任何根级别的 props，你可以在该项目文件夹中创建一个空的 `Directory.Build.props`：

```xml
<Project>
  <!-- 故意留空以停止从父级 props 继承 -->
</Project>
```

这是因为 MSBuild 在从项目目录向上遍历时，会在找到第一个 `Directory.Build.props` 时停止。

## Directory.Build.props vs Directory.Build.targets

文档中经常提到的另一个文件是 `Directory.Build.targets`。简而言之：

- **Directory.Build.props**：用于属性和项，在构建**早期**导入。非常适合配置和元数据。
- **Directory.Build.targets**：用于目标（Targets）和自定义构建操作，在构建**后期**导入。非常适合自定义构建步骤（例如，构建后运行工具、生成工件等）。

本文主要关注 props，但当你想要集中化“构建后执行此操作”的逻辑时，请记住 `Directory.Build.targets`。

## 总结

`Directory.Build.props` 是那些默默解决大量痛点的功能之一：

- 它保持你的 `.csproj` 文件简短、可读且专注。
- 它让你在整个 .NET 9 解决方案中强制执行一致的规则。
- 它集中了版本控制和元数据。
- 它为你提供了一种清晰的方式来区分 `src/`、`tests/` 和其他区域。

一旦你采用了它，添加新项目就变得几乎微不足道——不再需要从某个“模板”项目复制设置，也不会忘记开启可空引用类型或分析器。

如果你今天已经在与一个庞大的解决方案作斗争：

1.  在根目录添加一个 `Directory.Build.props`。
2.  将 `TargetFramework`、`Nullable`、`ImplicitUsings` 和分析器设置移动到其中。
3.  添加一个 `tests/Directory.Build.props` 用于通用的测试包。
4.  清理你的 `.csproj` 文件，直到它们变得“无聊”为止。

未来的你（以及你的队友）会感谢你的。
