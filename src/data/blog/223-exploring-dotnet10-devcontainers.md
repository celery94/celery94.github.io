---
pubDatetime: 2025-03-26 13:30:09
tags: [".NET", "AI"]
slug: exploring-dotnet10-devcontainers
source: https://devblogs.microsoft.com/dotnet/dotnet-in-dev-container/?hide_banner=true
title: 🚀探索最新.NET 10：使用开发容器实现高效环境隔离
description: 学习如何使用开发容器（Dev Containers）快速、安全地尝试最新的 .NET 10 预览版本，同时保持本地环境的清洁。详细教程带你掌握设置步骤、配置选项以及相关工具。
---

# 🚀探索最新.NET 10：使用开发容器实现高效环境隔离

.NET 团队刚刚发布了 .NET 10 的第二个预览版本，其中包含了一系列令人期待的新功能和改进✨。如果你想尝试这些新特性，但又不想对本地开发环境造成影响，那么 **开发容器（Dev Containers）** 将是你的理想选择！本教程将带你一步步设置和使用开发容器，快速开始尝试最新的 .NET 技术。

---

## 什么是开发容器（Dev Containers）？

开发容器是一种预配置的、隔离的开发环境，可以让开发者在不需要担心依赖冲突和配置问题的情况下轻松工作💻。它特别适合用于尝试新技术，因为它提供了一种一致且可复现的环境。

- 支持工具：包括 Visual Studio Code 和 GitHub Codespaces 等主流开发工具。
- 优势：快速搭建、云端支持、环境隔离。

👉 [了解更多关于 Dev Containers](https://containers.dev/)

---

## 🌟.NET 容器镜像类型

.NET 提供了多种容器镜像以满足不同需求，这些镜像发布在 [Microsoft Artifact Registry](https://mcr.microsoft.com/)，定期更新以确保安全和功能完善。

以下是常见的 .NET 容器类型及其用途：

| 容器类型      | 最适合用途   | 示例标签                                       | 说明                             |
| ------------- | ------------ | ---------------------------------------------- | -------------------------------- |
| SDK           | 开发         | `mcr.microsoft.com/dotnet/sdk:9.0`             | 包含完整的 SDK、运行时及开发工具 |
| Runtime       | 生产环境     | `mcr.microsoft.com/dotnet/runtime:9.0`         | 精简运行时镜像                   |
| ASP.NET       | Web 应用开发 | `mcr.microsoft.com/dotnet/aspnet:9.0`          | 包含 ASP.NET Core 运行时         |
| Nightly       | 测试预览版本 | `mcr.microsoft.com/dotnet/nightly/sdk:10.0`    | 最新预览构建                     |
| Dev Container | 本地开发环境 | `mcr.microsoft.com/devcontainers/dotnet:1-8.0` | 带有额外工具的预配置环境         |

---

## 🛠设置你的开发容器

以下是设置开发容器以尝试最新 .NET 版本的详细步骤：

### 1️⃣ 创建开发容器配置

在你的项目目录中创建 `.devcontainer` 文件夹，并添加 `devcontainer.json` 文件。推荐使用 Visual Studio Code 的 **Dev Containers 扩展** 来生成该配置文件。

操作步骤：

1. 打开 VS Code 的命令面板（`Ctrl+Shift+P`）。
2. 选择 “Dev Containers: Add Development Container Configuration Files…”。
3. 选择 “C#(.NET)” 模板，生成 `.devcontainer` 文件夹和 `devcontainer.json` 文件。

![添加 Dev Container 配置文件](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2025/03/AddConfigFiles.png)

### 2️⃣ 添加 Dockerfile

在 `.devcontainer` 文件夹中添加一个 `Dockerfile` 文件，用于定义基础镜像和安装所需的 .NET SDK 和运行时版本。

示例 Dockerfile：

```dockerfile
FROM mcr.microsoft.com/devcontainers/dotnet:1-8.0

# 安装当前的 .NET STS 版本
COPY --from=mcr.microsoft.com/dotnet/sdk:9.0 /usr/share/dotnet /usr/share/dotnet

# 安装最新的 .NET 10 预览版本
COPY --from=mcr.microsoft.com/dotnet/nightly/sdk:10.0.100-preview.2 /usr/share/dotnet /usr/share/dotnet
```

在 `devcontainer.json` 中引用 Dockerfile：

```json
"build": {
    "dockerfile": "./Dockerfile",
    "context": "."
},
```

📂 完整的配置文件可以参考 [aspnet-whats-new 项目仓库](https://github.com/mikekistler/aspnet-whats-new/tree/dotnet-10-preview2/.devcontainer)。

### 3️⃣ 自定义配置选项

你可以根据项目需求进一步定制 devcontainer.json 文件。例如：

- **安装扩展**：为开发容器安装 C# DevKit 扩展。

  ```json
  "extensions": [
      "ms-dotnettools.csdevkit"
  ]
  ```

- **启用额外功能**：添加 Azure CLI 工具。

  ```json
  "features": {
      "azure-cli": "latest"
  }
  ```

- **运行创建后命令**：安装额外工具，如 Entity Framework CLI。
  ```json
  "postCreateCommand": "dotnet tool install -g dotnet-ef"
  ```

更多选项请参考 [Dev Containers 功能文档](https://containers.dev/features)。

---

## 🚀启动你的开发容器

完成配置后，可以通过以下命令启动容器：

1. 使用 “Dev Containers: Open Folder in Container” 命令启动容器。
2. 验证安装的 .NET SDK 版本：
   ```bash
   dotnet --list-sdks
   ```

![验证 .NET SDK](https://devblogs.microsoft.com/dotnet/wp-content/uploads/sites/10/2025/03/DevContainerInVSCode.png)

注意事项：

- 容器镜像构建完成后会被缓存，你无需每次启动都重建。
- 如果需要更新基础镜像，可以使用 “Dev Containers: Rebuild Container Without Cache” 命令进行重建。

---

## 总结 🎉

开发容器是尝试最新 .NET 发布版本的绝佳方式，它能够提供一个隔离、安全且一致的环境，让你专注于新功能和技术的探索。无论你是想测试预览版还是为生产环境准备应用，开发容器都可以满足你的需求。

赶快动手试试吧！如果有任何问题或建议，欢迎留言与我们交流🙌！
