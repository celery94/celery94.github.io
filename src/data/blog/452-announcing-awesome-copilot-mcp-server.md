---
pubDatetime: 2025-08-29
tags: [".NET", "AI", "DevOps", "Productivity"]
slug: announcing-awesome-copilot-mcp-server
source: https://devblogs.microsoft.com/blog/announcing-awesome-copilot-mcp-server
title: 发布 Awesome Copilot MCP Server：通过 MCP 服务器搜索和保存 GitHub Copilot 自定义配置
description: 微软宣布推出 Awesome Copilot MCP Server，这是一个简单的方式来搜索 GitHub Copilot 自定义配置并直接保存到您的代码库中。这个 MCP 服务器帮助开发者从数百个聊天模式、指令和提示中发现最适合的配置。
---

# 发布 Awesome Copilot MCP Server：通过 MCP 服务器搜索和保存 GitHub Copilot 自定义配置

今天，微软宣布推出 **Awesome Copilot MCP Server** —— 一个简单的方式来搜索 GitHub Copilot 自定义配置并直接从 MCP 服务器保存到您的代码库中。

## 背景介绍

在 7 月初，微软宣布了社区驱动的 **Awesome GitHub Copilot Customizations** 代码库。该代码库包含聊天模式、指令和提示，让您可以定制 GitHub Copilot 的 AI 响应，涵盖大量使用场景。然而，面对如此多的优秀选项，发现和比较合适的配置变得困难。

这篇博客文章将向您展示如何通过与 GitHub Copilot 聊天来发现这些极其有用的聊天模式、指令和提示，并结合 Awesome Copilot MCP 服务器来实现。

## 什么是聊天模式、指令和提示？

### 自定义聊天模式

自定义聊天模式定义聊天如何操作、可以使用哪些工具以及如何与代码库交互。每个聊天提示都在聊天模式的边界内运行，无需为每个请求配置工具和指令。通过这些自定义聊天模式，您可以创建前端开发人员聊天模式，其中 AI 只能生成和修改与前端应用程序开发相关的代码。

### 自定义指令

自定义指令定义生成代码、执行代码审查或生成提交消息等任务的常见指导原则或规则。自定义指令描述 AI 应该执行操作的条件——**如何**完成任务。通过这些自定义指令，您可以指定编码实践、首选技术或项目要求，确保生成的代码遵循您的标准。

### 提示

提示定义常见任务（如生成代码或执行代码审查）的可重用提示。提示是您可以直接在聊天中运行的独立提示。它们描述要执行的任务——**做什么**。可选地，您可以在提示中包含任务特定的指导原则，或者在提示文件中引用自定义指令。通过这些自定义提示，您可以为常见编码任务创建可重用的提示，如搭建新组件、API 路由或生成测试。

如果您对这些概念不熟悉，可以查看 VS Code 文档中关于[聊天模式](https://code.visualstudio.com/docs/copilot/chat/chat-modes)、[自定义指令](https://code.visualstudio.com/docs/copilot/copilot-customization#_custom-instructions)和[提示文件](https://code.visualstudio.com/docs/copilot/copilot-customization#_prompt-files-experimental)的内容。

Awesome Copilot 代码库中有数百个这样的自定义聊天模式、指令和提示，MCP 服务器帮助您找到最佳的配置。

## 安装 Awesome Copilot MCP Server

### 前置要求

安装需要 Docker Desktop 已安装并运行，因为该服务器在容器中运行。

### 安装步骤

安装这个 MCP 服务器非常简单。点击以下按钮可以直接在 VS Code 中安装：

- [在 VS Code 中安装](https://aka.ms/awesome-copilot/mcp/vscode)
- [在 VS Code Insiders 中安装](https://aka.ms/awesome-copilot/mcp/vscode-insiders)

或者，将以下配置添加到您的 MCP 服务器配置中：

```json
{
  "servers": {
    "awesome-copilot": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "ghcr.io/microsoft/mcp-dotnet-samples/awesome-copilot:latest"
      ]
    }
  }
}
```

还有其他安装此 MCP 服务器的方法。更多信息请访问这个 [GitHub 代码库](https://aka.ms/awesome-copilot/mcp)。

## 使用 Awesome Copilot MCP Server

这个 MCP 服务器提供两个工具和一个提示：

### 工具

- `#search_instructions`：基于提供的关键词搜索 GitHub Copilot 自定义配置
- `#load_instruction`：加载特定的 GitHub Copilot 自定义配置

### 提示

- `/mcp.awesome-copilot.get_search_prompt`：提供搜索 GitHub Copilot 自定义配置的提示

### 使用步骤

1. **启动搜索提示**
   安装并运行此 MCP 服务器后，在 GitHub Copilot Chat 窗口中调用提示：

   ```
   /mcp.awesome-copilot.get_search_prompt
   ```

2. **输入搜索关键词**
   系统会提示您输入搜索关键词。例如，输入 "python" 作为关键词。

3. **查看搜索结果**
   系统会生成以下格式的提示，并连接到 MCP 服务器进行搜索：

   > 请搜索所有与搜索关键词 `python` 相关的聊天模式、指令和提示。以下是要遵循的流程：
   >
   > 1. 使用 `awesome-copilot` MCP 服务器
   > 2. 搜索提供关键词的所有聊天模式、指令和提示
   > 3. 在用户要求之前，不要从 MCP 服务器加载任何聊天模式、指令或提示
   > 4. 扫描 `.github/chatmodes`、`.github/instructions` 和 `.github/prompts` 目录中的本地聊天模式、指令和提示 markdown 文件
   > 5. 将现有的聊天模式、指令和提示与搜索结果进行比较
   > 6. 以表格格式提供结构化响应，包括是否已存在、模式（chatmodes、instructions 或 prompts）、文件名、标题和描述

4. **查看结果表格**
   搜索结果将以表格格式显示：

   | 存在 | 模式         | 文件名            | 标题      | 描述  |
   | ---- | ------------ | ----------------- | --------- | ----- |
   | ✅   | chatmodes    | chatmode1.json    | 聊天模式1 | 描述1 |
   | ❌   | instructions | instruction1.json | 指令1     | 描述1 |
   | ✅   | prompts      | prompt1.json      | 提示1     | 描述1 |

   其中 ✅ 表示该项目已存在于代码库中，❌ 表示不存在。

5. **保存配置文件**
   如果找到合适的自定义配置，只需回复文件名（例如 `python.instructions.md`）即可加载并保存。

   **提示**：如果您找到合适的自定义配置，请回复文件名（例如 `python.instructions.md`）来加载并保存它。

6. **确认保存**
   内容加载后，会保存到相应的目录中，如 `.github/instructions/python.instructions.md`。如果想保存其他文件，再次输入文件名即可。

## 亲自尝试！

现在轮到您了！在您的本地机器上安装这个 MCP 服务器，通过服务器搜索 GitHub Copilot 自定义配置并保存它！

## 更多资源

如果您想了解更多关于 .NET 中 MCP 的信息，以下是一些值得探索的额外资源：

- [Awesome Copilot](https://aka.ms/awesome-copilot)
- [Awesome Copilot MCP Server](https://aka.ms/awesome-copilot/mcp)
- [Let's Learn MCP](https://aka.ms/letslearnmcp)
- [MCP Workshop in .NET](https://aka.ms/mcp-workshop/dotnet)
- [MCP Samples in .NET](https://aka.ms/mcp/dotnet/samples)
- [MCP Samples](https://github.com/modelcontextprotocol/csharp-sdk/tree/main/samples)

## 总结

Awesome Copilot MCP Server 为开发者提供了一个强大而简单的工具，通过 Model Context Protocol (MCP) 来发现和管理 GitHub Copilot 的自定义配置。这个工具解决了在众多优秀自定义配置中发现和比较合适选项的难题，让开发者能够：

- 通过关键词搜索相关的聊天模式、指令和提示
- 直接在 GitHub Copilot Chat 中预览配置内容
- 一键将有用的配置保存到本地代码库

随着 AI 辅助开发工具的普及，像这样的 MCP 服务器展示了如何通过标准化协议来扩展和增强 AI 助手的能力，为开发者提供更加个性化和高效的编程体验。
