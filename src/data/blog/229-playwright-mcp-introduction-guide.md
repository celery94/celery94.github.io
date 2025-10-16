---
pubDatetime: 2025-03-28 22:05:51
tags: ["AI", "Testing"]
slug: playwright-mcp-introduction-guide
source: https://github.com/microsoft/playwright-mcp
title: 探索Playwright MCP：下一代浏览器自动化与AI交互工具
description: Playwright MCP 是一款基于 Playwright 的 Model Context Protocol 服务器，提供快速、轻量级且适合 LLM 的浏览器自动化能力。本文详细介绍其功能特点、安装指南及使用方法，助力开发者优化网页交互流程。
---

# 探索Playwright MCP：下一代浏览器自动化与AI交互工具 🚀

随着浏览器自动化技术的飞速发展和人工智能工具的普及，如何高效地实现网页交互成为开发者们关注的焦点。今天要介绍的是一款创新工具—— **Playwright MCP**，它结合了 [Playwright](https://playwright.dev/) 的强大功能，为开发者提供了一种全新的方式来与网页进行交互。

## 什么是 Playwright MCP？🤔

**Playwright MCP（Model Context Protocol）** 是一个基于 Playwright 的服务器，专注于通过结构化的可访问性快照（而非截图或视觉模型）实现高效的浏览器自动化。它能够让大语言模型（LLM）在无需视觉模型的情况下，与网页进行交互。这一特性不仅提升了工具的运行效率，也消除了传统视觉模型常见的模糊性问题。

### 核心特点 ✨

1. **快速轻量**：利用 Playwright 的可访问性树，避免了像素级输入的复杂计算。
2. **LLM 友好**：无需视觉模型，通过结构化数据进行操作。
3. **确定性工具应用**：避免了基于截图方法中常见的不确定性。

---

## Playwright MCP 的应用场景 🔧

Playwright MCP 的灵活性使其适用于多种场景，包括但不限于：

- **网页导航和表单填写** 🖱️
- **结构化内容的数据提取** 📊
- **由 LLM 驱动的自动化测试** 🧪
- **通用浏览器交互代理** 🤖

无论是开发网页爬虫、测试自动化脚本，还是构建 AI 驱动的交互系统，Playwright MCP 都是一个强大的工具。

---

## 快速安装指南 📦

在 [Visual Studio Code](https://code.visualstudio.com/) 中安装 Playwright MCP 只需几步。您可以通过以下任意一种方式完成安装：

### 方法一：直接安装按钮 💡

使用以下按钮一键安装：

[![Install in VS Code Insiders](https://camo.githubusercontent.com/3b0d6acf63711603a87d99bd158c078b55e28dcdd9a05f22bd64abf6a5d1195d/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f56535f436f64655f496e7369646572732d56535f436f64655f496e7369646572733f7374796c653d666c61742d737175617265266c6162656c3d496e7374616c6c25323053657276657226636f6c6f723d323462666135)](https://insiders.vscode.dev/redirect?url=vscode-insiders%3Amcp%2Finstall%3F%257B%2522name%2522%253A%2522playwright%2522%252C%2522command%2522%253A%2522npx%2522%252C%2522args%2522%253A%255B%2522-y%2522%252C%2522%2540playwright%252Fmcp%2540latest%2522%255D%257D)

### 方法二：通过 CLI 安装 👨‍💻

使用 VS Code 的命令行界面安装：

```bash
# 对于 VS Code
code --add-mcp '{"name":"playwright","command":"npx","args":["@playwright/mcp@latest"]}'

# 对于 VS Code Insiders
code-insiders --add-mcp '{"name":"playwright","command":"npx","args":["@playwright/mcp@latest"]}'
```

完成后，Playwright MCP 服务器将可以在您的 VS Code 中配合 GitHub Copilot 使用。

---

## 用户数据目录路径 📂

Playwright MCP 默认会为 Chrome 浏览器创建新的用户配置文件，存储路径如下：

- Windows: `%USERPROFILE%\AppData\Local\ms-playwright\mcp-chrome-profile`
- macOS: `~/Library/Caches/ms-playwright/mcp-chrome-profile`
- Linux: `~/.cache/ms-playwright/mcp-chrome-profile`

如果需要清除离线状态，可以删除这些目录。

---

## 两种运行模式：Snapshot 与 Vision 🛠️

### 1. 快照模式（Snapshot Mode）

该模式使用可访问性快照完成操作，性能高且更稳定。常见操作包括：

- 浏览器导航（`browser_navigate`）
- 点击元素（`browser_click`）
- 填写表单（`browser_type`）
- 截取页面快照（`browser_snapshot`）

示例配置：

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

### 2. 视觉模式（Vision Mode）

该模式基于截图完成交互，适合需要基于坐标精确操作的场景。常见操作包括：

- 鼠标移动（`browser_move_mouse`）
- 坐标点击（`browser_click`）
- 截图捕捉（`browser_screenshot`）

启用视觉模式的示例配置：

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--vision"]
    }
  }
}
```

---

## Playwright MCP 的核心工具集 📜

以下为部分常用的工具命令：

| 工具名称                  | 描述               | 参数                       |
| ------------------------- | ------------------ | -------------------------- |
| `browser_navigate`        | 跳转到指定 URL     | `url` (字符串)             |
| `browser_click`           | 点击页面上的元素   | `element`, `ref`           |
| `browser_type`            | 在输入框中键入文本 | `element`, `ref`, `text`   |
| `browser_take_screenshot` | 捕捉页面截图       | 可选参数：返回 PNG 或 JPEG |
| `browser_wait`            | 等待指定时间       | `time` (秒数)              |

更多工具详情可参考官方文档：[GitHub - microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)

---

## 总结 🎯

Playwright MCP 是一个功能强大且灵活的浏览器自动化解决方案，它通过快照模式和视觉模式覆盖了各种复杂场景，特别适合那些需要与网页深度交互的开发者和测试工程师。如果您正在寻找一种高效的方式来实现网页自动化，那么不妨试试 Playwright MCP 吧！

还在等什么？现在就动手安装，体验下一代自动化工具的魅力吧！🎉
