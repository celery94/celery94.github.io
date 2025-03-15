---
pubDatetime: 2025-03-15
tags: [CI/CD, .NET, GitHub Actions, Azure, Software Development]
slug: streamline-dotnet-9-deployment
source: https://www.milanjovanovic.tech/blog/streamlining-dotnet-9-deployment-with-github-actions-and-azure
title: 🚀 简化.NET 9 部署：使用GitHub Actions和Azure实现自动化
description: 探索如何通过GitHub Actions和Azure App Service构建高效的CI/CD流水线，为.NET 9应用提供快速、可靠的自动化部署。
---

# 🚀 简化.NET 9 部署：使用GitHub Actions和Azure实现自动化

在手动部署.NET应用的日子里，每次发布都是一次冒险：本地发布、文件传输到服务器、运行脚本，然后祈祷一切顺利。😅 如今，通过实施CI/CD流水线，部署已变得简单可靠，甚至有些无聊——而无聊的部署往往是成功的部署。

## 了解CI/CD的价值

CI/CD，即**持续集成**和**持续交付/部署**，对于.NET开发者至关重要。它不仅可以：

1. 提供更快的反馈，让你在几分钟内发现bug。
2. 提升发布稳定性，小改动更易于修复。
3. 节省时间，让自动化处理重复任务。
4. 保持一致的部署，消除“在我机器上正常”的问题。

## 我的GitHub Actions工作流

以下是我用于将简单的时间服务API部署到Azure App Service的工作流：

```yaml
# 工作流名称
name: Time Service CI

# 触发条件
on:
  workflow_dispatch:
  push:
    branches:
      - main

# 环境变量
env:
  AZURE_WEBAPP_NAME: time-service
  AZURE_WEBAPP_PACKAGE_PATH: "./Time.Api/publish"
  DOTNET_VERSION: "9.x"
  SOLUTION_PATH: "Time.Api.sln"
  API_PROJECT_PATH: "Time.Api"
  PUBLISH_DIR: "./publish"

# 工作任务
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

此工作流主要进行构建和测试代码，然后将其部署到Azure。通过GitHub Actions界面可以看到工作流运行的样子。

## 扩展你的CI/CD流水线

随着项目的发展，流水线也应不断扩展，以捕捉更多问题并提高质量标准：

### 数据库迁移

数据库迁移可能会对代码部署带来挑战。可以使用EF Core迁移包：

```yaml
- name: Create migration bundle
  run: dotnet ef migrations bundle --project ${{ env.DATA_PROJECT }} --output ${{ env.MIGRATIONS_BUNDLE }}

- name: Apply migrations
  run: ${{ env.MIGRATIONS_BUNDLE }}
```

这种方式让数据库架构与代码变更同步，减少人为干预。

### 代码覆盖率报告

生成并发布代码覆盖率报告，可以确保代码质量：

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

### 多环境部署

多环境部署允许更精细的控制：

```yaml
deploy-staging:
  name: Deploy to Staging
  environment: staging
  runs-on: ubuntu-latest
  needs: [build-and-test]
  steps:
    # Deployment steps...

deploy-production:
  name: Deploy to Production
  environment: production
  runs-on: ubuntu-latest
  needs: [deploy-staging]
  steps:
    # Deployment steps...
```

保护规则如必需审阅者、等待计时器和部署分支可以防止意外的生产环境变更。

## 总结

一个好的CI/CD流水线会随着项目一起成长。从简单开始，逐步添加功能以满足需求。初始设置虽然耗时，但长期收益巨大。我所在的团队现在可以每天多次部署，而不再是每几周一次，且生产问题更少。

想了解更多关于构建与CI/CD流程完美配合的强大API，请查看我的[Pragmatic REST APIs](https://www.milanjovanovic.tech/pragmatic-rest-apis)课程。

你的CI/CD设置是怎样的？欢迎分享你的.NET应用工作流定制经验！
