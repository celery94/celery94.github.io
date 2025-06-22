---
pubDatetime: 2025-06-22
tags: [CI/CD, .NET 9, GitHub Actions, Azure, DevOps]
slug: streamlining-dotnet9-deployment-github-actions-azure
source: https://www.milanjovanovic.tech/blog/streamlining-dotnet-9-deployment-with-github-actions-and-azure
title: 用 GitHub Actions 和 Azure 优雅实现 .NET 9 自动化部署 —— CI/CD 实践全解析
description: 本文系统讲解如何基于 GitHub Actions 与 Azure App Service，搭建健壮、自动化的 .NET 9 应用 CI/CD 流水线。从原理到实战，涵盖代码构建、自动化测试、部署、数据库迁移、代码覆盖率、多环境管控等关键环节，助力你从手工部署走向高效敏捷交付。
---

# 用 GitHub Actions 和 Azure 优雅实现 .NET 9 自动化部署 —— CI/CD 实践全解析

## 引言

还记得那些年，每次上线.NET应用都要手动编译、拷贝文件、远程执行脚本、祈祷一切顺利的日子吗？那种又累又慌的感觉，相信很多开发者都经历过。幸运的是，随着 CI/CD（持续集成/持续交付）理念的普及和工具链的完善，我们终于可以让“上线”变成一件无聊甚至令人愉悦的事。

本文将带你用最主流的组合 —— **GitHub Actions + Azure App Service**，为 .NET 9 应用打造一条专业、高效、可扩展的自动化交付流水线。内容涵盖：

- CI/CD 基本概念及价值
- 完整自动化流水线原理与流程
- 关键步骤与核心代码详解
- 数据库迁移、代码覆盖率、多环境发布等进阶实践
- 常见问题与最佳实践总结

无论你是刚接触自动化部署的新手，还是想提升现有流程的老兵，都能在本文中获得实用指导。

---

## 背景与核心理念

### 什么是 CI/CD？为什么每个 .NET 开发者都该关心？

**CI/CD** 是现代软件工程不可或缺的基石：

- **CI（Continuous Integration，持续集成）**：团队成员频繁将代码合并到主分支，并自动执行编译与测试，早发现问题。
- **CD（Continuous Delivery/Deployment，持续交付/部署）**：自动将通过测试的代码快速、安全地交付至生产或预发布环境。若自动推送到生产即为“持续部署”。

**主要优势：**

1. 快速反馈：数分钟内发现 BUG，不积压问题。
2. 稳定交付：小步快跑，风险可控，易于回滚。
3. 节省时间：重复劳动交给自动化，人专注于创造价值。
4. 环境一致：避免“在我电脑上没问题”的尴尬。

---

## 技术原理与方案架构

### 总体流程

我们以一个典型 ASP.NET Core Web API 项目为例，流水线大致分为如下阶段：

1. **拉取主分支代码**
2. **环境准备（如设置 .NET 版本）**
3. **依赖恢复（dotnet restore）**
4. **编译构建（dotnet build）**
5. **单元测试（dotnet test）**
6. **应用发布（dotnet publish）**
7. **产物归档（upload artifact）**
8. **自动部署到 Azure App Service**
9. **可选：数据库迁移、覆盖率统计、多环境部署等**

![CI/CD 流程图](https://www.milanjovanovic.tech/blogs/mnw_133/ci_cd_pipeline.png?imwidth=3840)
_图1：CI/CD 流程整体示意_

---

## 实现步骤详解

### 1. 配置 GitHub Actions 工作流

在项目根目录下新建 `.github/workflows/time-service-ci.yml` 文件：

```yaml
name: Time Service CI

on:
  workflow_dispatch: # 支持手动触发
  push:
    branches:
      - main # 推送到 main 分支时自动触发

env:
  AZURE_WEBAPP_NAME: time-service
  AZURE_WEBAPP_PACKAGE_PATH: "./Time.Api/publish"
  DOTNET_VERSION: "9.x"
  SOLUTION_PATH: "Time.Api.sln"
  API_PROJECT_PATH: "Time.Api"
  PUBLISH_DIR: "./publish"

jobs:
  build-and-test:
    name: Build and Test
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: ${{ env.DOTNET_VERSION }}

      - name: Restore
        run: dotnet restore ${{ env.SOLUTION_PATH }}

      - name: Build
        run: dotnet build ${{ env.SOLUTION_PATH }} --configuration Release --no-restore

      - name: Test
        run: dotnet test ${{ env.SOLUTION_PATH }} --configuration Release --no-restore --no-build --verbosity normal

      - name: Publish
        run: dotnet publish ${{ env.API_PROJECT_PATH }} --configuration Release --no-restore --no-build --property:PublishDir=${{ env.PUBLISH_DIR }}

      - name: Publish Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: webapp
          path: ${{ env.AZURE_WEBAPP_PACKAGE_PATH }}

  deploy:
    name: Deploy to Azure
    runs-on: ubuntu-latest
    needs: [build-and-test]

    steps:
      - name: Download artifact from build job
        uses: actions/download-artifact@v4
        with:
          name: webapp
          path: ${{ env.AZURE_WEBAPP_PACKAGE_PATH }}

      - name: Deploy
        uses: azure/webapps-deploy@v2
        with:
          app-name: ${{ env.AZURE_WEBAPP_NAME }}
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
          package: "${{ env.AZURE_WEBAPP_PACKAGE_PATH }}"
```

#### 核心点说明

- `workflow_dispatch` 允许手动运行，`push` 自动触发。
- 两大 Job 分工明确：`build-and-test` 负责编译/测试/产物归档；`deploy` 则拉取产物并部署到 Azure。
- `needs` 指定依赖关系，确保只有测试通过才会部署。
- `publish-profile` 使用 GitHub Secret 安全存储 Azure 发布凭据。

![GitHub Actions 工作流执行界面示例](https://www.milanjovanovic.tech/blogs/mnw_133/ci_cd_pipeline.png?imwidth=3840)
_图2：GitHub Actions 工作流运行界面_

---

### 2. 数据库迁移自动化实践

数据库结构变更若操作不当极易造成事故。推荐引入 **EF Core Migration Bundle** 自动化迁移：

```yaml
- name: Create migration bundle
  run: dotnet ef migrations bundle --project ${{ env.DATA_PROJECT }} --output ${{ env.MIGRATIONS_BUNDLE }}

- name: Apply migrations
  run: ${{ env.MIGRATIONS_BUNDLE }}
```

> 💡 _EF Core Migration Bundle 是 EF Core 6.0+ 新特性，可将所有迁移打包为独立可执行文件，便于流水线中自动执行。_

**安全建议：**

- 建议先在 Staging 环境演练，再上线生产。
- 对生产库务必提前备份，并考虑启用人工审核环节。

---

### 3. 集成代码覆盖率统计

良好的测试覆盖率是高质量代码的保障。以 [Codecov](https://about.codecov.io/) 为例：

```yaml
- name: Generate coverage report
  run: dotnet test ${{ env.SOLUTION_PATH }} /p:CollectCoverage=true /p:CoverletOutputFormat=cobertura

- name: Publish coverage report
  uses: codecov/codecov-action@v5
  with:
    files: ./**/coverage.cobertura.xml
    fail_ci_if_error: true
    token: ${{ secrets.CODECOV_TOKEN }}
```

> 📝 _可以设置阈值，低于指定覆盖率则流水线失败，从源头保障代码质量。_

---

### 4. 多环境分阶段部署（Staging/Production 等）

对于正式项目，分阶段部署与审批机制是必备：

```yaml
deploy-staging:
  name: Deploy to Staging
  environment: staging
  runs-on: ubuntu-latest
  needs: [build-and-test]
  steps:
    # 部署步骤...

deploy-production:
  name: Deploy to Production
  environment: production
  runs-on: ubuntu-latest
  needs: [deploy-staging]
  steps:
    # 部署步骤...
```

![多环境发布流程图（建议绘制一张包含开发、测试、预发布、生产各阶段和审批节点的流程图）](https://www.milanjovanovic.tech/blogs/mnw_133/ci_cd_pipeline.png?imwidth=3840)
_图3：多环境发布及审批机制示意_

可以在 GitHub Environments 设置：

- 必须审核人名单（如 DBA、安全人员）
- 部署延时等待窗口（回滚缓冲期）
- 限定仅特定分支可部署生产

---

## 常见问题与解决方案

| 问题                       | 解决方案                                                        |
| -------------------------- | --------------------------------------------------------------- |
| 秘钥泄漏风险               | 所有敏感凭据均放入 GitHub Secrets，不在代码库明文存储           |
| 数据库迁移失败导致回滚困难 | 严格 staging/production 隔离，生产前先演练并做好备份            |
| 覆盖率报告无数据或格式异常 | 检查测试命令参数和输出路径是否正确，Codecov Token 配置是否生效  |
| 多环境部署逻辑混乱         | 合理规划 Job/Environment 的依赖链，仅允许经过审核的变更进入生产 |

---

## 总结与最佳实践 🌟

1. **从痛点出发，小步快跑**。优先自动化最繁琐、最易错环节。
2. **安全第一**。凭据管理、审批机制、分环境管控不可少。
3. **质量内建**。全流程自动测试、覆盖率门槛、数据库变更同步推进。
4. **灵活扩展**。流水线应易于插拔新能力，如集成安全扫描、性能基准等。
5. **持续迭代**。随着团队与项目成长，不断完善和优化 CI/CD 流程。

---

## 附录与资源链接

- [GitHub Actions 官方文档](https://docs.github.com/en/actions)
- [Azure App Service 官方介绍](https://azure.microsoft.com/en-us/products/app-service)
- [EF Core Migration Bundle 使用详解](https://www.milanjovanovic.tech/blog/efcore-migrations-a-detailed-guide)
- [Codecov 集成指引](https://about.codecov.io/)
- [CI/CD 基础知识百科](https://en.wikipedia.org/wiki/CI/CD)

---

希望本文能助你开启真正高效、安全、现代化的 .NET 自动化交付之路！🚀 有问题欢迎留言交流，下期再见！
