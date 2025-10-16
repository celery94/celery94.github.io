---
pubDatetime: 2025-04-13 09:12:16
tags: ["AI", "Frontend"]
slug: create-mcp-server-azure-ai-typescript
source: https://devblogs.microsoft.com/foundry/integrating-azure-ai-agents-mcp-typescript/
title: 🔗 用TypeScript打造Azure AI Agents的MCP服务器，轻松连接Claude Desktop！
description: 通过详细技术教程学习如何使用TypeScript创建一个Model Context Protocol (MCP)服务器，集成Azure AI Agents与Claude Desktop，实现桌面应用和AI服务的无缝交互。
---

# 用TypeScript打造Azure AI Agents的MCP服务器，轻松连接Claude Desktop！

如果你是一位对人工智能技术、TypeScript编程语言和Azure生态系统感兴趣的开发者，那么这篇文章将为你带来一份完整的技术指南，帮助你实现Azure AI Agents与桌面应用的完美结合。🤖✨

---

## 🌟 项目背景

### 什么是MCP服务器？

Model Context Protocol (MCP) 是一种标准化协议，用于连接强大的AI工具（如Azure AI Agents）与桌面应用程序（如Claude Desktop）。通过MCP，你可以轻松实现AI服务与桌面应用的交互，而无需复杂的自定义开发。

---

## 🧑‍💻 目标读者群体

以下人群将从这篇文章中获益：

- **熟悉TypeScript**和Node.js的开发者
- 对**Azure AI服务**和标准化协议感兴趣的技术人员
- 希望集成AI解决方案到桌面应用的架构师

---

## ❓ 为什么需要MCP？

Azure AI Agents功能强大，但将它们连接到桌面应用程序通常需要额外开发工作。MCP提供了一种标准化方法，使得Claude Desktop等客户端能够轻松地与Azure AI Agents交互。

---

## 🚀 快速开始：创建TypeScript MCP服务器

以下是详细的步骤指南：

### 步骤1️⃣：创建项目

在你的终端输入以下命令：

```bash
# 创建项目目录并初始化npm项目
mkdir azure-agent-mcp
cd azure-agent-mcp
npm init -y

# 安装必要依赖
npm install @modelcontextprotocol/sdk zod dotenv @azure/ai-projects @azure/identity

# 安装开发依赖
npm install -D typescript @types/node
```

### 步骤2️⃣：配置TypeScript

创建`tsconfig.json`文件：

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "node",
    "outDir": "./dist",
    "strict": true
  },
  "include": ["src/**/*"]
}
```

### 步骤3️⃣：环境设置

创建一个`.env`文件以存储Azure凭证：

```dotenv
PROJECT_CONNECTION_STRING=your-project-connection-string
DEFAULT_AGENT_ID=your-default-agent-id
```

---

## 🛠 核心功能实现

### 初始化MCP服务器

在`src/index.ts`中实现MCP服务器初始化逻辑：

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { AIProjectsClient } from "@azure/ai-projects";
import * as dotenv from "dotenv";

dotenv.config();

const PROJECT_CONNECTION_STRING = process.env.PROJECT_CONNECTION_STRING;

function initializeServer(): boolean {
  try {
    const credential = new DefaultAzureCredential();
    return !!AIProjectsClient.fromConnectionString(
      PROJECT_CONNECTION_STRING,
      credential
    );
  } catch (error) {
    console.error("初始化失败:", error.message);
    return false;
  }
}
```

---

## 📡 与Claude Desktop集成

配置Claude Desktop以连接MCP服务器。编辑`claude_desktop_config.json`文件：

```json
{
  "mcpServers": {
    "azure-agent": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/dist/index.js"],
      "env": {
        "PROJECT_CONNECTION_STRING": "your-project-connection-string",
        "DEFAULT_AGENT_ID": "your-default-agent-id"
      }
    }
  }
}
```

---

## 🔍 实用案例

一旦MCP服务器成功运行，你可以通过Claude Desktop执行以下操作：

1️⃣ **查询特定Agent**：  
在Claude中提问：“能否通过Azure Agent查询当前天气情况？”

2️⃣ **使用默认Agent**：  
例如提问：“能否总结一下今天的NBA新闻？”

3️⃣ **列出所有可用Agent**：  
在Claude中查看所有已注册的Azure AI Agent。

---

## ✅ 总结

通过本教程，你学会了如何使用TypeScript构建一个Azure AI Agents的MCP服务器，并成功集成到Claude Desktop。无论是构建专业的AI服务还是提高工具互操作性，这套技术解决方案都将为你打开新的可能性。

🎉 **现在，开始你的AI集成之旅吧！**

如果你喜欢本文，请分享给更多对AI技术感兴趣的小伙伴！🚀
