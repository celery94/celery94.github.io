---
pubDatetime: 2025-04-17 08:23:06
tags: ["Productivity", "Tools"]
slug: azure-functions-mcp-guide
source: https://devblogs.microsoft.com/dotnet/build-mcp-remote-servers-with-azure-functions/
title: 🔥让MCP服务器轻松上云！Azure Functions最新实验功能全解析
description: 深入解析如何使用Azure Functions快速构建远程MCP服务器，让AI工具集成更高效！探索MCP协议、功能实现及GitHub Copilot的完美结合。
---

# 🔥让MCP服务器轻松上云！Azure Functions最新实验功能全解析

在AI技术大潮中，**模型上下文协议（Model Context Protocol，简称MCP）**无疑是软件开发领域的热门话题。而今天，我们将探索一种全新的方式：利用Azure Functions构建远程MCP服务器，让工具集成更加简单高效。🤖🚀

---

## 什么是MCP协议？🧠

MCP是一种帮助AI应用程序与工具进行交互的规范。通常，这些工具会提供核心业务功能，例如访问API以存储或检索Azure Blob Storage中的数据。

📌 MCP的核心目标是让LLM（大语言模型）知道何时以及如何调用这些工具。但由于它只是一个规范，开发者需要自己实现相关功能。这就需要写大量的“管道代码”，而这正是Azure Functions能够帮你解决的问题。

---

## 为什么选择远程MCP服务器？🌐

传统上，MCP服务器多运行在本地，例如通过VS Code或Docker容器搭建。但这种方式存在两个问题：

1. **部署麻烦**：每台电脑都需要安装同样版本的MCP服务器，团队协作时管理起来非常繁琐。
2. **扩展性不足**：本地服务器限制了跨地域和环境的使用。

利用远程MCP服务器，可以轻松解决这些痛点！只需一个支持服务端事件（SSE）的远程端点即可运行，而Azure Functions正是理想选择。

---

## Azure Functions与MCP的完美结合✨

Azure Functions是一种基于事件的无服务器产品。它的突出特点是通过简单的特性（attribute）定义，可以轻松集成其他Azure服务。例如，通过`[BlobOutput(blobPath)]`属性定义，函数返回值即可直接写入指定路径的Blob Storage。

现在，Azure Functions新增了实验性预览功能，只需添加一个`[MCPToolTrigger]`属性，就能将函数变成MCP服务器！下面让我们通过一个示例来了解具体操作。

---

## 示例：构建一个Azure Functions MCP服务器🛠️

### 功能概述

这个示例实现了两项功能：

1. 保存代码片段到Azure Blob Storage中。
2. 根据名称检索保存的代码片段。

示例代码库：[Remote MCP Functions Sample](https://aka.ms/cadotnet/mcp/functions/remote-sample)

---

### 核心代码解析

#### 保存代码片段到Blob Storage

```csharp
[Function(nameof(SaveSnippet))]
[BlobOutput(BlobPath)]
public string SaveSnippet(
    [McpToolTrigger(SaveSnippetToolName, SaveSnippetToolDescription)]
        ToolInvocationContext context,
    [McpToolProperty(SnippetNamePropertyName, PropertyType, SnippetNamePropertyDescription)]
        string name,
    [McpToolProperty(SnippetPropertyName, PropertyType, SnippetPropertyDescription)]
        string snippet
)
{
    return snippet;
}
```

🔍 **关键点**：

- `[McpToolTrigger]`：定义函数为可被MCP客户端调用的工具。
- `[McpToolProperty]`：声明函数需要的参数，包括名称和代码片段内容。
- `[BlobOutput]`：将返回值直接存储到Azure Blob。

#### 检索代码片段

```csharp
[Function(nameof(GetSnippet))]
public object GetSnippet(
    [McpToolTrigger(GetSnippetToolName, GetSnippetToolDescription)]
        ToolInvocationContext context,
    [BlobInput(BlobPath)] string snippetContent
)
{
    return snippetContent;
}
```

🔍 **关键点**：

- `[BlobInput]`：根据定义的路径直接读取存储的Blob内容并返回。
- 路径定义方式：通过`mcptoolargs`动态拼接名称。

---

### 如何部署到Azure？🚀

使用[Azure Developer CLI](https://learn.microsoft.com/azure/developer-cli/)（azd），只需一行命令即可完成部署：

```bash
azd up
```

⚠️ **注意**：如果不想使用Azure，可选择本地运行，通过[步骤说明](https://github.com/Azure-Samples/remote-mcp-functions-dotnet?tab=readme-ov-file#prepare-your-local-environment)启动函数应用。

---

## 在VS Code中消费远程MCP服务器🖥️

### 配置步骤

1. 安装GitHub Copilot扩展。
2. 使用命令面板输入`> MCP: Add Server...`。
3. 选择`HTTP (server-sent events)`。
4. 输入服务器URL（包括`/runtime/webhooks/mcp/sse`后缀）。
5. 保存配置文件到工作区，更新`.vscode/mcp.json`以支持动态系统密钥提示。

### 成功连接后的效果

当连接到远程MCP服务器后，你会看到可用的工具列表，并能够让Copilot通过自然语言指令调用这些工具。比如：

💬 **指令示例**：

- 保存代码片段：`Save the highlighted code and call it my-snippet`.
- 插入代码片段：`Put my-snippet at the cursor`.

Copilot会智能地识别并执行相关工具调用，让开发过程更加流畅！

---

## 总结📌

通过Azure Functions和MCP协议，你可以轻松构建强大的远程服务器，支持AI工具高效集成。搭配GitHub Copilot等客户端，整个开发体验将更加顺畅、智能化。✨

赶快尝试吧，[点击获取完整代码](https://aka.ms/cadotnet/mcp/functions/remote-sample)，或者观看完整教程视频，一步步掌握这项新技术！

> 💡 **拓展阅读**：了解更多关于[MCP协议](https://devblogs.microsoft.com/dotnet/tag/mcp/)和[Azure Functions](https://azure.microsoft.com/en-us/)的信息，让你的开发技能更上一层楼！
