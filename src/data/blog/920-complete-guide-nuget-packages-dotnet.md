---
pubDatetime: 2026-07-02T11:23:12+08:00
title: "NuGet 包创建完全指南：从 .csproj 到 CI 自动化发布"
description: "一份面向 .NET 开发者的 NuGet 包创建实战指南，覆盖项目元数据配置、dotnet pack 打包、版本管理、发布到 nuget.org 与私有源、GitHub Actions 自动化、本地测试以及 SourceLink 调试支持，每一步都有对应深度的延伸阅读入口。"
tags: ["NuGet", ".NET", "C#"]
slug: "complete-guide-nuget-packages-dotnet"
ogImage: "../../assets/920/01-cover.png"
source: "https://www.devleader.ca/2026/07/01/the-complete-guide-to-creating-nuget-packages-in-net"
---

如果你在 .NET 项目里用过 `dotnet add package`，你就已经消费过 NuGet 包。它是 .NET 生态里共享代码的标准单元——把编译好的程序集、元数据和依赖项打包成一个版本化的 `.nupkg` 文件，通过 nuget.org 或私有源分发出去。

会用包是一回事，会做包是另一回事。无论你是想发布开源库、在公司内部跨团队共享 SDK，还是给微服务之间提供签约的接口契约，创建 NuGet 包的流程本质上是一样的。这篇文章按从零到发布再到可调试的完整链路，串起每个环节的关键知识点。

## NuGet 包是什么

一个 NuGet 包本质上是一个版本化的 ZIP 文件（`.nupkg`），里面装着编译好的程序集、描述元数据和依赖项的清单文件，还可以附带文档、构建脚本等可选项。公共注册中心是 [nuget.org](https://www.nuget.org)——你在终端里运行 `dotnet add package` 时，默认就是从这里拉包的。

包的内部结构和依赖解析逻辑决定了消费者最终拉取到什么样的程序集组合，了解 `.nupkg` 内部格式对排查依赖冲突很有帮助。延伸阅读：[What Is a NuGet Package? The .nupkg Format and Registry Explained](https://www.devleader.ca/2026/06/18/what-is-a-nuget-package-the-nupkg-format-and-registry-explained/)。

## 创建第一个 NuGet 包

现代 .NET 项目用 SDK 风格的 `.csproj` 文件，包元数据可以直接写在项目文件里，不需要额外的 `.nuspec` 文件。

一个最小可用的 `.csproj` 配置如下：

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>

    <!-- NuGet 包身份信息 -->
    <PackageId>MyCompany.MyLibrary</PackageId>
    <Version>1.0.0</Version>
    <Description>一个通用的字符串操作工具库。</Description>
    <Authors>Nick Cosentino</Authors>

    <!-- 可发现性与许可 -->
    <PackageTags>string utilities dotnet csharp</PackageTags>
    <PackageLicenseExpression>MIT</PackageLicenseExpression>
    <RepositoryUrl>https://github.com/mycompany/mylibrary</RepositoryUrl>
  </PropertyGroup>

</Project>
```

元数据配置好之后，一行命令就能生成 `.nupkg`：

```bash
dotnet pack --configuration Release --output ./nupkgs
```

几个容易踩的坑：

- `PackageId` 和程序集名称是不同的概念，前者是 NuGet 源上的唯一标识，后者是 `.dll` 文件名——两者可以不一致。
- `dotnet pack` 默认用的是 Debug 配置，但推到 nuget.org 时应该用 Release 构建。
- 一个解决方案包含多个项目时，只有标记了 `<IsPackable>true</IsPackable>` 的项目才会被 `dotnet pack` 打包。

完整操作指南：[How to Create a NuGet Package in C# with dotnet pack](https://www.devleader.ca/2026/06/19/how-to-create-a-nuget-package-in-csharp-with-dotnet-pack/)。

## 包元数据与可发现性

包发布出去之后，元数据就是它的"门面"。别人在 nuget.org 搜索时看到的是 `PackageId` 和 `Description` 的组合，找到后第一眼看到的是渲染好的 README。元数据填得好不好，直接影响下载量和信任度。

关键字段一览：

| 字段                       | 作用                                                                 |
| -------------------------- | -------------------------------------------------------------------- |
| `PackageId`                | nuget.org 上的唯一标识，建议带命名空间前缀（如 `MyCompany.Feature`） |
| `Description`              | 用一句话说清楚这个包做什么，会出现在 IDE 提示和 nuget.org 页面       |
| `PackageTags`              | 空格分隔的标签，直接影响搜索排名                                     |
| `PackageReadmeFile`        | 渲染在包页面的 README，在安装前就能让开发者判断是否合用              |
| `PackageIcon`              | 包内嵌的图标，在搜索结果和 IDE 里展示                                |
| `PackageProjectUrl`        | 仓库或文档链接                                                       |
| `PackageLicenseExpression` | SPDX 许可标识，如 `MIT`、`Apache-2.0`、`GPL-3.0-only`                |

好的元数据不仅帮助人类快速评估一个包，也是品质信号。一个描述清晰、标签准确、附带 README 的包，比一个缺胳膊少腿的包更容易被收藏和采纳。

延伸阅读：[NuGet Package Metadata Best Practices: README, Icon, and Tags](https://www.devleader.ca/2026/06/20/nuget-package-metadata-best-practices-readme-icon-and-tags/)。

## 版本管理

NuGet 遵循 SemVer 2.0：`MAJOR.MINOR.PATCH[-prerelease][+build]`。

- 有**破坏性变更**时，升 `MAJOR`
- 有**向后兼容的新功能**，升 `MINOR`
- **纯修复**，升 `PATCH`
- 还在预览阶段，加预发布后缀（`-beta.1`、`-rc.2`）

一个实践层面的建议：做自动化发布的团队，与其直接在 `.csproj` 写死 `<Version>`，不如拆成 `<VersionPrefix>` + `<VersionSuffix>`。这样 CI 流水线可以动态注入预发布标签而不用改项目文件。

版本号不只是技术约定——它是你和消费者之间的沟通方式。消费者看到版本号就知道这次更新是安全修复还是需要改代码。配套的 changelog 和 `[Obsolete]` 属性则负责把迁移的跨度说清楚。

延伸阅读：[NuGet Versioning with SemVer in .NET](https://www.devleader.ca/2026/06/22/nuget-versioning-with-semver-in-net/)。

## 发布到 nuget.org

把 `.nupkg` 推到 nuget.org 的核心命令：

```bash
dotnet nuget push ./nupkgs/MyCompany.MyLibrary.1.0.0.nupkg \
  --api-key $NUGET_API_KEY \
  --source https://api.nuget.org/v3/index.json
```

几个需要提前知道的事：

- 需要 nuget.org 账号并生成带了作用域限制的 API key——建议限定到具体的包 ID 或前缀。
- `PackageId` 在 nuget.org 上是全局唯一的，先到先得。
- 已发布的包**不能删除**，只能 unlist（取消列表）。别人知道确切版本号的话仍然能下载到。所以版本策略要想清楚再发。

首发之前还可以在 nuget.org 上预留包 ID 前缀（如 `MyCompany.*`），这会标一个 verified 的勾，防止别人抢注。

延伸阅读：[How to Publish a NuGet Package to NuGet.org](https://www.devleader.ca/2026/06/23/how-to-publish-a-nuget-package-to-nuget-org/)。

## 私有 NuGet 源

不是所有包都适合公开。内部工具库、专有 SDK、预发布版本应该用私有源，团队可见但不对外。

.NET 生态里两大主流选择：

- **Azure Artifacts**——Azure DevOps 的一部分，支持 NuGet、npm、Maven 等，和 Azure Pipelines 及 RBAC 深度集成。
- **GitHub Packages**——GitHub 内置的包注册中心，和 GitHub Actions 及仓库权限天然打通。

两者都走标准 NuGet 协议，`dotnet nuget push` 和 `dotnet add package` 的用法完全一样——只是把源 URL 换成私有地址。

私有源还有一个架构层面的价值：在微服务或多团队组织里，用 NuGet 包分发接口契约，是一种干净且版本化的跨服务通信方式。比如插件架构场景下，把插件契约打成 NuGet 包分发，每个消费方拿到的都是同一份带版本的接口定义。

延伸阅读：[Private NuGet Feeds with Azure Artifacts and GitHub Packages](https://www.devleader.ca/2026/06/24/private-nuget-feeds-with-azure-artifacts-and-github-packages/)。

## 多框架支持

一个包同时支持多个 .NET 运行时的情况很常见。SDK 风格的项目里，把 `<TargetFramework>` 改成 `<TargetFrameworks>` 就行：

```xml
<TargetFrameworks>net8.0;net10.0;netstandard2.0</TargetFrameworks>
```

这样 `dotnet pack` 打出一个 `.nupkg`，内部包含针对每个目标框架的 `lib` 文件夹，NuGet 会自动为消费者的项目选择合适的程序集。

多目标构建会带来额外复杂度：需要 `#if` 预处理指令处理不同框架的 API 差异；测试要覆盖每个目标框架；`netstandard2.0` 能用的 API 远少于 `net8.0`，要写条件实现。

做多框架支持之前先想清楚：谁在用这个包？一个面向内部 Azure 服务的工具大概不需要 `netstandard2.0`。一个被既有 .NET Framework 和现代 .NET 8 应用同时消费的通用库则几乎必须支持。

延伸阅读：[Multi-Targeting Your NuGet Package for .NET 6, .NET 8, and .NET Standard](https://www.devleader.ca/2026/06/25/multi-targeting-your-nuget-package-for-net6-net8-and-netstandard/)。

## 用 GitHub Actions 自动化发布

手动 `dotnet pack` + `dotnet nuget push` 对第一次发布来说还行，对之后的每一次发布都是一个风险点——错了分支、忘了升版本号、构建环境不一致，出问题的概率随着发布次数增加。

GitHub Actions 把发布流程变成可复现的自动化流水线。核心 workflow 模板：

```yaml
name: Publish NuGet Package

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: "8.0.x"

      - name: Restore dependencies
        run: dotnet restore

      - name: Build
        run: dotnet build --configuration Release --no-restore

      - name: Pack
        run: dotnet pack --configuration Release --no-build --output ./nupkgs

      - name: Push
        run: |
          dotnet nuget push ./nupkgs/*.nupkg \
            --api-key ${{ secrets.NUGET_API_KEY }} \
            --source https://api.nuget.org/v3/index.json \
            --skip-duplicate
```

这个 workflow 在 tag 推送时触发（比如 `v1.2.0`），用 `actions/setup-dotnet@v4` 设置 .NET SDK，然后恢复依赖、构建、打包、推送。API key 存在 GitHub Secrets 里，绝不进代码仓库。

注意 `--skip-duplicate` 参数——同一版本的 workflow 重复运行时不抛错，可以直接跳过。

生产级发布还要考虑 MinVer 或 Nerdbank.GitVersioning 这类工具做基于 tag 的版本自动化、针对 pre-release 分支的独立流水线、多项目方案的处理和自动生成 changelog。

延伸阅读：[Automating NuGet Publishing with GitHub Actions](https://www.devleader.ca/2026/06/26/automating-nuget-publishing-with-github-actions/)。

## 发布前先在本地测试

NuGet 包开发里最常见的一个错误是只测源码项目，不测打出来的包。两者不是一回事。

消费者装的是编译后的程序集，不是源文件。依赖项走的是 NuGet 解析图，不是项目引用。文件路径行为也不同。源码里跑着完全正常的库，从 feed 装完之后出奇怪问题，不罕见。

发布到 nuget.org 或私有源之前，按这个清单走一遍：

1. **本地打包**：`dotnet pack --configuration Release`，解压 `.nupkg`，确认里面装的是正确的程序集，没有不该出现的构建产物。
2. **添加本地源**：`dotnet nuget add source ./nupkgs --name local`，把打包输出目录注册成本地 NuGet 源。
3. **以包形式测试**：新建一个测试用的消费者项目，通过本地源引用你的包（不要用 `<ProjectReference>`），模拟真实的安装体验。
4. **验证公开 API**：确认公开的类型、命名空间和方法签名和你文档里写的一致。

特别的，如果你的包是 source generator（源生成器），它会在消费者编译期间执行——这会引入普通库包不存在的失败模式。发布前更需要在消费者项目中跑一整套编译测试。

延伸阅读：[How to Test and Debug Your NuGet Package Locally](https://www.devleader.ca/2026/06/27/how-to-test-and-debug-your-nuget-package-locally/)。

## SourceLink 与符号包

当别人装了你的包之后遇到 bug，他们想在自己的调试器里步进到你的源码。没有 SourceLink 和符号包，这就是做不到的——他们只能对着反编译出来的 IL 干瞪眼。

SourceLink 是一个把源码控制元数据嵌入程序集的标准。当调试器请求某个包内方法的源文件时，它直接从你的 GitHub 仓库拉取构建时的那份精确代码。消费者无需任何手动配置。

给 GitHub 托管的项目启用 SourceLink，核心步骤就两步。先加一个包引用：

```xml
<PackageReference Include="Microsoft.SourceLink.GitHub" Version="8.0.0" PrivateAssets="all" />
```

> 到 [nuget.org](https://www.nuget.org/packages/Microsoft.SourceLink.GitHub) 查看最新版本号替换上面的 `8.0.0`。

再补上这些构建属性：

```xml
<PropertyGroup>
  <PublishRepositoryUrl>true</PublishRepositoryUrl>
  <EmbedUntrackedSources>true</EmbedUntrackedSources>
  <DebugType>embedded</DebugType>
</PropertyGroup>
```

符号包（`.snupkg`）是配套部分。它和主包一起推送到 nuget.org，包含 `.pdb` 调试符号文件。nuget.org 自带符号服务器——消费者配好符号源之后就能直接步进到你的库里调试。

SourceLink + 符号包的组合把 NuGet 包从"黑盒"变成开发者可以信任、调试和贡献的透明模块。对于生产级库来说，这是品质信号，也是实用刚需。

延伸阅读：[NuGet SourceLink and Symbol Packages in .NET](https://www.devleader.ca/2026/06/28/nuget-sourcelink-and-symbol-packages-in-net/)。

## 常见问题

**`PackageId` 和 `AssemblyName` 的区别？**

`PackageId` 是 NuGet 源上的标识，你在 `dotnet add package MyCompany.MyLibrary` 里输入的就是它。`AssemblyName` 是包里编译出的 `.dll` 文件名。一个包可以包含多个程序集，两者不一定相同。建议在 `.csproj` 里显式设置 `PackageId`，精确控制消费者和 nuget.org 看到的名字。

**一个 NuGet 包里能塞多个项目吗？**

可以，但不常见，而且往往是功能膨胀的信号。标准做法是一个项目一个包。如果确实需要捆绑多个程序集，可以用项目引用并加上 `<PrivateAssets>all</PrivateAssets>` 把引用的程序集打进包里。在此之前先想想：拆成多个包是不是对消费者更好。

**如何处理破坏性变更？**

严格遵循 SemVer：任何破坏 API 的变更升 MAJOR 版本。维护 changelog 告诉消费者改了什么、为什么改。如果要重命名或删除公开类型，先用 `[Obsolete]` 属性标记为过时，给消费者升级的窗口期，下一个大版本再移除。在小版本或补丁版本里引入破坏性变更会迅速消耗信任。

**`.nuspec` 和 `.csproj` 该用哪个？**

现代 SDK 风格的项目，所有内容写在 `.csproj` 的 `Package*` 属性里就够了。`.nuspec` 是旧方式，只在非 SDK 项目或者需要复杂文件映射、`.csproj` 表达不了的场景下才需要。今天新起一个 NuGet 包，就用 `.csproj`。

**需要给包签名吗？**

可选，但高信任场景下推荐。签名能证明包来自某个发布者且未被篡改。nuget.org 支持作者签名（你自己提供证书）和仓库签名（发布时由 nuget.org 自动施加）。开源包的话，nuget.org 自动施加的仓库签名通常就够了。

**`dotnet pack` 怎么处理传递依赖？**

`dotnet pack` 只把直接 `PackageReference` 记录到包的依赖元数据里。传递依赖由 NuGet 在消费者安装时自行解析，不打包进 `.nupkg`。这保持了包的轻量，避免了版本冲突。如果想把某个依赖作为内部实现细节私有化（消费者看不到），加上 `<PrivateAssets>all</PrivateAssets>`。

**发布前能不能预览 NuGet 包？**

能，而且每次都应该做。`dotnet pack` 之后把输出目录注册成本地源：`dotnet nuget add source ./nupkgs --name local-test`，再建一个消费者项目按 ID 引用这个包。这能让你在碰到 nuget.org 之前就抓到元数据错误、资源缺失和依赖解析异常。

## 收尾

NuGet 包生态是 .NET 最强大的基础设施之一。从小的工具库到跨全球团队分发的复杂多目标 SDK，全都走同一条路径：项目元数据、`dotnet pack`、版本化的 `.nupkg`、推到源。

这份指南覆盖了完整链路：理解包的格式 → 配好元数据 → 用 SemVer 做版本沟通 → 本地测试包而不是项目 → 用 GitHub Actions 自动化发布 → 配好 SourceLink 让消费者可调试。每个环节都有对应的深度文章，需要深挖时不会无路可走。

如果你关注 .NET 开发、工程实践和工具链，可以关注 Aide Hub。这里会继续分享能落地的技术教程和开发经验。

## 参考

- [The Complete Guide to Creating NuGet Packages in .NET — Dev Leader](https://www.devleader.ca/2026/07/01/the-complete-guide-to-creating-nuget-packages-in-net)
- [What Is a NuGet Package? The .nupkg Format and Registry Explained](https://www.devleader.ca/2026/06/18/what-is-a-nuget-package-the-nupkg-format-and-registry-explained/)
- [How to Create a NuGet Package in C# with dotnet pack](https://www.devleader.ca/2026/06/19/how-to-create-a-nuget-package-in-csharp-with-dotnet-pack/)
- [NuGet Package Metadata Best Practices: README, Icon, and Tags](https://www.devleader.ca/2026/06/20/nuget-package-metadata-best-practices-readme-icon-and-tags/)
- [NuGet Versioning with SemVer in .NET](https://www.devleader.ca/2026/06/22/nuget-versioning-with-semver-in-net/)
- [How to Publish a NuGet Package to NuGet.org](https://www.devleader.ca/2026/06/23/how-to-publish-a-nuget-package-to-nuget-org/)
- [Private NuGet Feeds with Azure Artifacts and GitHub Packages](https://www.devleader.ca/2026/06/24/private-nuget-feeds-with-azure-artifacts-and-github-packages/)
- [Multi-Targeting Your NuGet Package for .NET 6, .NET 8, and .NET Standard](https://www.devleader.ca/2026/06/25/multi-targeting-your-nuget-package-for-net6-net8-and-netstandard/)
- [Automating NuGet Publishing with GitHub Actions](https://www.devleader.ca/2026/06/26/automating-nuget-publishing-with-github-actions/)
- [How to Test and Debug Your NuGet Package Locally](https://www.devleader.ca/2026/06/27/how-to-test-and-debug-your-nuget-package-locally/)
- [NuGet SourceLink and Symbol Packages in .NET](https://www.devleader.ca/2026/06/28/nuget-sourcelink-and-symbol-packages-in-net/)
