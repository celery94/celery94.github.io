---
pubDatetime: 2026-04-13T21:30:00+08:00
title: "Azure MCP Server 2.0 正式发布：自托管远程部署与 276 个 Azure 工具"
description: "Azure MCP Server 2.0 稳定版发布，核心亮点是支持自托管远程 MCP 服务器，276 个工具覆盖 57 项 Azure 服务。支持 VS Code、Visual Studio、IntelliJ 等 IDE，以及 GitHub Copilot CLI 和 Claude Code，适合团队和企业级云自动化场景。"
tags: ["Azure", "MCP", "AI Agent", "DevTools"]
slug: "azure-mcp-server-2-0-stable-release"
ogImage: "../../assets/733/01-cover.jpg"
source: "https://devblogs.microsoft.com/azure-sdk/announcing-azure-mcp-server-2-0-stable-release"
---

Azure MCP Server 2.0 稳定版正式发布。这个版本的核心变化不是工具数量的增加，而是部署模式的转变：它现在可以作为远程 MCP 服务器运行，支持团队和企业集中管理和部署。

![Azure MCP Server 2.0 封面](../../assets/733/01-cover.jpg)

## 这是什么

Azure MCP Server 是一个实现了 Model Context Protocol（MCP）规范的开源服务器，让 AI 智能体和开发工具可以通过统一的接口调用 Azure 资源。

当前版本包含 **276 个 MCP 工具，覆盖 57 项 Azure 服务**，支持从资源配置、部署、监控到运维诊断的完整场景。你可以在 IDE 里直接用它，也可以在 CLI 工具里调用，或者把它作为独立服务部署在团队内部。

## 2.0 的核心变化：自托管远程服务器

1.x 版本主要定位为本地开发工具。2.0 的重点是让它可以作为远程 MCP 服务器运行，成为团队或企业内部的共享服务。

**自托管远程模式**支持多种认证方式，可以根据你的环境和安全策略灵活选择：

- **Managed Identity**：在 Microsoft Foundry 等 Azure 托管环境中推荐使用
- **On-Behalf-Of (OBO) 流程**：也称为 OpenID Connect delegation，可以以已登录用户的身份安全调用 Azure API

典型场景包括：为开发者和内部 Agent 系统提供共享 Azure MCP 访问入口、在企业网络和策略边界内运行、集中管理租户上下文和订阅默认配置、以及集成到 CI/CD 和自动化流水线。

## 安全加固

2.0 在安全性上做了针对性改进，主要面向远程托管场景：

- 更强的端点验证
- 针对查询类工具的常见注入模式防护
- 开发环境的隔离控制收紧

这些改动让 Azure MCP 在本地运行时更安全，在远程共享服务模式下也更适合生产使用。

## 支持的开发工具

Azure MCP Server 2.0 支持多种主流开发环境：

**IDE 集成**（作为扩展使用）：
- Visual Studio Code
- Visual Studio
- IntelliJ
- Eclipse
- Cursor

**命令行 Agent 工具**：GitHub Copilot CLI、Claude Code

此外，你也可以直接运行独立的本地服务器，或者按照 2.0 的重点——把它自托管为远程 MCP 服务器。

## 其他改进

**性能和可靠性**：对依赖多个 MCP 工具集的场景有明显优化，容器镜像体积也有所减小。

**主权云支持**：可以配置为在 Azure US Government 和 Azure 中国（由世纪互联运营）环境中运行，适合有合规边界要求的部署。

**工具生态优化**：持续改进工具描述的清晰度，统一校验逻辑，合并冗余操作，提升 Agent 选取工具的准确性。

## 如何开始

- [GitHub 仓库](https://github.com/Azure/azure-mcp)
- [Docker 镜像](https://mcr.microsoft.com/artifact/mar/azure-mcp)
- [提交 Issue](https://github.com/Azure/azure-mcp/issues)

如果只是想在本地试用，可以直接通过 VS Code 或 Cursor 的 MCP 扩展安装。如果需要为团队提供集中访问，2.0 的远程自托管模式是专门为这个场景设计的。

## 参考

- [Announcing Azure MCP Server 2.0 Stable Release](https://devblogs.microsoft.com/azure-sdk/announcing-azure-mcp-server-2-0-stable-release)
- [Azure MCP Server GitHub 仓库](https://github.com/Azure/azure-mcp)
