---
pubDatetime: 2025-03-20
tags: [".NET", "DevOps"]
slug: ci-cd-github-actions-dotnet
source: https://www.milanjovanovic.tech/blog/how-to-build-ci-cd-pipeline-with-github-actions-and-dotnet
title: 🚀从零开始，使用GitHub Actions和.NET构建CI/CD管道
description: 探索如何通过CI/CD加速软件开发流程，使用GitHub Actions和.NET实现自动化构建、测试和部署，为您的项目带来更高效和可靠的发布体验。
---

# 🚀从零开始，使用GitHub Actions和.NET构建CI/CD管道

## 什么是CI/CD？

在现代软件开发中，持续集成（Continuous Integration, CI）和持续交付（Continuous Delivery, CD）是提高新功能交付频率的重要方法。通过在开发工作流中添加自动化，CI/CD能显著减少手动工作，让您专注于软件创作，确保更快速和可靠的发布。

## 为什么选择GitHub Actions？

GitHub Actions 是一个完全免费且易于使用的自动化工具。它允许您创建工作流，以实现对每次代码提交的构建、测试和部署。以下是我们将要介绍的内容：

- CI/CD与GitHub Actions简介
- 创建.NET的构建与测试管道
- 创建Azure App Service的部署管道

## 🛠️ 使用GitHub Actions实现持续集成

使用GitHub Actions，您可以轻松地为您的.NET项目创建持续集成工作流。例如，以下工作流将在代码提交到主分支时自动触发：

```yaml
name: Build & Test 🧪

on:
  push:
    branches:
      - main

env:
  DOTNET_VERSION: "7.0.x"

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3
      - name: Setup .NET 📦
        uses: actions/setup-dotnet@v3
        with:
          dotnet-version: ${{ env.DOTNET_VERSION }}
      - name: Install dependencies 📂
        run: dotnet restore WebApi
      - name: Build 🧱
        run: dotnet build WebApi --configuration Release --no-restore
      - name: Test 🧪
        run: dotnet test WebApi --configuration Release --no-build
```

## 🌐 部署到Azure的持续交付

通过GitHub Actions，实现自动化部署过程同样简单。以下是一个用于发布应用到Azure App Service实例的工作流：

```yaml
name: Publish 🚀

on:
  push:
    branches:
      - main

env:
  AZURE_WEBAPP_NAME: web-api
  AZURE_WEBAPP_PACKAGE_PATH: "./publish"
  DOTNET_VERSION: "7.0.x"

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3
      - name: Setup .NET 📦
        uses: actions/setup-dotnet@v3
        with:
          dotnet-version: ${{ env.DOTNET_VERSION }}
      - name: Build and Publish 📂
        run: |
          dotnet restore WebApi
          dotnet build WebApi -c Release --no-restore
          dotnet publish WebApi -c Release --no-build --output '${{ env.AZURE_WEBAPP_PACKAGE_PATH }}'
      - name: Deploy to Azure 🌌
        uses: azure/webapps-deploy@v2
        with:
          app-name: ${{ env.AZURE_WEBAPP_NAME }}
          publish-profile: ${{ secrets.AZURE_PUBLISH_PROFILE }}
          package: "${{ env.AZURE_WEBAPP_PACKAGE_PATH }}"
```

## 总结

通过引入CI/CD，您可以彻底改变您的开发流程，加快发布变更的速度。设置一次构建和部署管道后，您将为项目的整个生命周期受益。若想深入了解如何从头开始实施CI/CD管道，我为您准备了一段[视频教程](https://youtu.be/QP0pi7xe24s)，并提供了开源代码供您参考。

感谢您的阅读，希望对您有所帮助！😊
