---
pubDatetime: 2026-07-21T08:16:19+08:00
title: ".NET 私有 NuGet 源实战：Azure Artifacts 与 GitHub Packages"
description: "不是所有 NuGet 包都适合公开。本文覆盖 Azure Artifacts 和 GitHub Packages 两种私有源的配置方法，包括 nuget.config 设置、本地与 CI/CD 认证、以及多源混合使用的实践。"
tags: ["NuGet", "Azure Artifacts", "GitHub Packages", ".NET", "CI/CD"]
slug: "private-nuget-feeds-azure-artifacts-github-packages"
ogImage: "../../assets/954/01-cover.png"
source: "https://www.devleader.ca/2026/07/07/private-nuget-feeds-in-net-azure-artifacts-and-github-packages"
---

NuGet.org 是开源包的绝佳归宿，但不是所有包都该上去。内部公共库、跨微服务共享的专有代码、还没准备好公开发布的库——这些场景下，一个私有 NuGet 源才是正确的选择。

本文覆盖两种最常用的托管方案：Azure Artifacts 和 GitHub Packages。你会看到各自的源配置方式、本地和 CI/CD 认证怎么搞、以及怎么在同一个项目里同时使用公开和私有源。

## 什么时候不该用 NuGet.org

NuGet.org 是公开的。推上去的包全世界都能看到和下载——对开源工作来说完美，但日常团队场景往往会出问题：

- **专有业务逻辑**：包里有公司核心算法、数据模型或集成代码，公开等于送给竞争对手源代码。
- **尚未发布的库**：要在内部跨团队共享库，但还没到公开发布的阶段。私有源让内部团队马上能用。
- **内部工具和公共组件**：共享日志帮助器、基础测试夹具、内部 SDK 包装器——对组织内有用，对外部无关甚至会造成困惑。
- **合规审计要求**：部分组织有代码存放地的法律或监管要求。运行在你控制的（或云提供商订阅下的）基础设施上的私有源，比公共包仓库能更好满足这些要求。

简单说：私有源解决的问题是——在一个你定义的边界内可靠分发编译好的代码，而不暴露到边界之外。

## Azure Artifacts 作为私有 NuGet 源

Azure Artifacts 是 Azure DevOps 的一部分。如果你的团队已经在用 Azure DevOps 做源码管理、任务跟踪或流水线，那 Azure Artifacts 就在同一个生态里，是自然的第一选择。

### 源的范围：组织级 vs 项目级

**组织级源**对 Azure DevOps 组织内所有项目可见——适合多团队共享的内部包，比如通用日志库或共享 API 客户端。

**项目级源**只对单个 Azure DevOps 项目可见，更隔离，权限管理更容易。适合只在某个产品或团队内使用的包。

### 源 URL 格式

创建源之后，NuGet v3 源 URL 格式如下：

```
https://pkgs.dev.azure.com/{org}/{project}/_packaging/{feedName}/nuget/v3/index.json
```

组织级源（无项目）去掉 `/{project}` 段。

### 上游源

Azure Artifacts 的**上游源**值得单独提一句。配置上游源后，你的私有源可以代理转发对 NuGet.org（或其他 NuGet 源）的请求。意思是所有开发者从你私有源这一个源恢复包——即使那些包本身是公开的。Azure Artifacts 代取并缓存公开包。

这对公司防火墙配置和审计都有好处：所有在用包通过一个可审计的源获取。

## Azure Artifacts 认证配置

Azure Artifacts 使用 Microsoft Entra ID 做认证。最简单的方式是安装 **Azure Artifacts Credential Provider**：

```powershell
iex "& { $(irm https://aka.ms/install-artifacts-credprovider.ps1) }"
```

安装后，首次从 Azure Artifacts 源恢复包时会弹出交互式登录提示。

本地开发时可以直接把源 URL 加到用户级 `nuget.config` 并存储凭据：

```powershell
dotnet nuget add source "https://pkgs.dev.azure.com/myorg/myproject/_packaging/MyFeed/nuget/v3/index.json" `
    --name "MyAzureArtifactsFeed" `
    --username "myuser" `
    --password "MY_PERSONAL_ACCESS_TOKEN" `
    --store-password-in-clear-text
```

PAT 至少需要 Azure DevOps 中的 **Packaging (read)** 权限。

## GitHub Packages 作为私有 NuGet 源

GitHub Packages 内建在 GitHub 里。如果你的团队用 GitHub 管理代码，GitHub Packages 很自然地跟仓库搭配使用。

两个常见意外：

- **源的范围是按 owner**（用户或组织），不是按仓库。源 URL 是：

```
https://nuget.pkg.github.com/{OWNER}/index.json
```

- **GitHub Packages 需要认证才能读取包，即使是公开包**。你需要一个带 `read:packages` 权限的 GitHub PAT 才能从任何 GitHub Packages 源恢复包。跟 NuGet.org（公开包总是允许匿名读取）不同。

## nuget.config 多源配置

大多数实际项目同时用 NuGet.org 和一个或多个私有源。`nuget.config` 是声明所有这些源的地方。

### 使用 Azure Artifacts

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" protocolVersion="3" />
    <add key="MyAzureArtifactsFeed"
         value="https://pkgs.dev.azure.com/myorg/myproject/_packaging/MyFeed/nuget/v3/index.json" />
  </packageSources>

  <packageSourceCredentials>
    <MyAzureArtifactsFeed>
      <add key="Username" value="optional-username" />
      <add key="ClearTextPassword" value="%AZURE_DEVOPS_TOKEN%" />
    </MyAzureArtifactsFeed>
  </packageSourceCredentials>
</configuration>
```

`%AZURE_DEVOPS_TOKEN%` 语法告诉 NuGet 在恢复时从环境变量读取，避免把真实凭据写在文件里。安装 credential provider 后，本地开发甚至可以省略整个 `<packageSourceCredentials>` 块。

### 使用 GitHub Packages

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" protocolVersion="3" />
    <add key="GitHubPackages"
         value="https://nuget.pkg.github.com/MyGitHubOrg/index.json" />
  </packageSources>

  <packageSourceCredentials>
    <GitHubPackages>
      <add key="Username" value="x-access-token" />
      <add key="ClearTextPassword" value="%NUGET_AUTH_TOKEN%" />
    </GitHubPackages>
  </packageSourceCredentials>
</configuration>
```

`Username` 为 `x-access-token` 是 GitHub 的标准值——它对 `GITHUB_TOKEN` 和 PAT 认证都生效。`NUGET_AUTH_TOKEN` 是约定俗成的环境变量名。

## 在 Visual Studio 和 CLI 中使用私有包

`nuget.config` 和认证配好后，从私有源消费包和从 NuGet.org 消费完全一样：

```bash
dotnet restore
dotnet add package MyCompany.SharedUtils --version 1.2.0
dotnet add package MyCompany.SharedUtils --source MyAzureArtifactsFeed
```

NuGet 按顺序搜索所有配置的源。不指定 `--source` 时，会在所有源里找。在 Visual Studio 中，NuGet 包管理器的源下拉框里会出现你的私有源——选中、搜包名、正常安装就行。

## CI/CD 中处理凭据

本地交互式登录不能在无头 CI 环境中工作，需要通过环境变量或流水线密钥传入凭据。

### GitHub Actions + GitHub Packages

最简场景：`GITHUB_TOKEN` 由 GitHub Actions 自动注入，对同一组织的包默认有 `read:packages` 权限：

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      packages: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '9.0.x'

      - name: Restore packages
        env:
          NUGET_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: dotnet restore

      - name: Build
        run: dotnet build --no-restore
```

### Azure Pipelines + Azure Artifacts

Azure Pipelines 通过 `NuGetAuthenticate` 任务原生支持 Azure Artifacts：

```yaml
steps:
  - task: NuGetAuthenticate@1
    displayName: 'Authenticate with Azure Artifacts'
  - script: dotnet restore
    displayName: 'Restore packages'
```

`NuGetAuthenticate` 自动为 `nuget.config` 中找到的所有 Azure Artifacts 源注入凭据，不需要手动设置令牌。

## Azure Artifacts vs GitHub Packages 对比

| | Azure Artifacts | GitHub Packages |
|---|---|---|
| **原生集成** | Azure DevOps | GitHub Actions |
| **认证** | Entra ID / PAT + credential provider | GitHub PAT (`read:packages`) |
| **读取权限** | 需组织成员或显式共享 | 即便是公开包也需要认证 |
| **上游源** | 支持 NuGet.org 代理 | 不支持 |
| **免费额度** | 每组织 2 GB，之后按用量计费 | 包含在 GitHub 计划中 |
| **CI 工具** | `NuGetAuthenticate` 任务 | `GITHUB_TOKEN` 内置密钥 |
| **源 URL 范围** | 按源（组织或项目级） | 按 owner（组织或用户） |

选 Azure Artifacts：团队已经在 Azure DevOps 工作、想要上游源代理、需要项目级源隔离。

选 GitHub Packages：团队在 GitHub 生态里、包跟特定仓库紧密关联、想要最简配置。

两者也可以同时用——`nuget.config` 里配多个源就好。

## 结语

私有 NuGet 源解决一个实际问题：在组织内部安全分发专有或未公开的 NuGet 包。Azure Artifacts 和 GitHub Packages 是两种主流方案，各自跟自己的 CI/CD 生态天然集成。

核心要点：
- Azure Artifacts 源 URL 格式是 `pkgs.dev.azure.com/{org}/{project}/_packaging/{feed}/nuget/v3/index.json`；安装 credential provider 搞定本地认证。
- GitHub Packages 始终需要认证——本地用带 `read:packages` 的 PAT，Actions 里用 `GITHUB_TOKEN`。
- `nuget.config` 可以同时声明多个源，NuGet.org、Azure Artifacts 和 GitHub Packages 混用不会冲突。
- CI 里用环境变量占位符（`%TOKEN_NAME%`）替代硬编码凭据。永远不要在仓库里提交真实令牌。

## 参考

- [原文：Private NuGet Feeds in .NET: Azure Artifacts and GitHub Packages](https://www.devleader.ca/2026/07/07/private-nuget-feeds-in-net-azure-artifacts-and-github-packages)
