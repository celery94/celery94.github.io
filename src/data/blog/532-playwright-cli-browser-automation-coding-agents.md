---
pubDatetime: 2026-01-31
title: "Playwright CLI：面向编码代理的高效浏览器自动化工具"
description: "Playwright CLI 是 Microsoft 推出的命令行界面工具，专为 Claude Code、GitHub Copilot 等编码代理优化，提供高度令牌高效的浏览器自动化能力。支持会话管理、多标签页操作、截图、网络监控等功能，通过 SKILL 机制无缝集成到代理工作流中。"
tags: ["Playwright", "CLI", "浏览器自动化", "AI", "测试"]
slug: "playwright-cli-browser-automation-coding-agents"
source: "https://github.com/microsoft/playwright-cli"
---

# Playwright CLI：面向编码代理的高效浏览器自动化工具

Microsoft 推出了 [Playwright CLI](https://github.com/microsoft/playwright-cli)，这是一个专为现代编码代理设计的命令行界面工具，它将 Playwright 的强大浏览器自动化能力以令牌高效的方式提供给 Claude Code、GitHub Copilot 和其他 AI 编码助手。

## 为什么选择 Playwright CLI 而非 MCP？

Playwright CLI 与 Playwright MCP（Model Context Protocol）在应用场景上有明显区别：

### CLI 优势：令牌效率

现代编码代理越来越倾向于使用基于 CLI 的工作流，通过 SKILL 方式暴露功能，而不是 MCP。原因在于：

- **令牌效率更高**：CLI 调用避免了加载庞大的工具模式（schema）和冗长的可访问性树到模型上下文中
- **简洁的命令**：通过专门构建的命令执行操作，大大减少令牌消耗
- **更适合高吞吐量场景**：在处理大型代码库、测试和推理时，需要在有限的上下文窗口内平衡浏览器自动化

### MCP 适用场景

MCP 仍然适用于以下特定的代理循环：

- 需要持久状态和丰富内省的场景
- 对页面结构进行迭代推理
- 探索性自动化、自愈测试或长时间运行的自主工作流
- 维护持续浏览器上下文的价值超过令牌成本考虑

了解更多关于 [Playwright MCP](https://github.com/microsoft/playwright-mcp) 的信息。

## 核心特性

- **令牌高效**：不强制将页面数据加载到 LLM 中
- **无缝集成**：与 Claude Code、GitHub Copilot 等编码代理完美配合
- **易于安装**：通过 npm 全局安装即可使用

## 环境要求

- Node.js 18 或更高版本
- Claude Code、GitHub Copilot 或其他编码代理

## 快速开始

### 安装

```bash
npm install -g @playwright/cli@latest
playwright-cli --help
```

如果需要强制覆盖旧的 MCP 包中的二进制文件：

```bash
npm install -g @playwright/cli@latest --force
```

### 基本使用

#### 无 SKILL 操作

直接使用 CLI，让代理自行读取帮助信息：

```
在 https://demo.playwright.dev/todomvc 上测试"添加待办事项"流程，使用 playwright-cli。
检查 playwright-cli --help 查看可用命令。
```

#### 安装 SKILL（推荐）

Claude Code、GitHub Copilot 等支持将 Playwright SKILL 安装到代理循环中。

**通过插件市场（推荐）：**

```bash
/plugin marketplace add microsoft/playwright-cli
/plugin install playwright-cli
```

**手动安装：**

```bash
mkdir -p .claude/skills/playwright-cli
curl -o .claude/skills/playwright-cli/SKILL.md \
  https://raw.githubusercontent.com/microsoft/playwright-cli/main/skills/playwright-cli/SKILL.md
```

## 实战演示

### 自动化测试示例

让代理测试 TodoMVC 应用：

```
使用 playwright 技能测试 https://demo.playwright.dev/todomvc/。
为所有成功和失败的场景截图。
```

### 手动命令示例

虽然代理会运行命令，但您也可以手动操作：

```bash
playwright-cli open https://demo.playwright.dev/todomvc/ --headed
playwright-cli type "买杂货"
playwright-cli press Enter
playwright-cli type "浇花"
playwright-cli press Enter
playwright-cli check e21
playwright-cli check e35
playwright-cli screenshot
```

## 核心功能

### 有头模式运行

默认情况下，Playwright CLI 以无头模式运行。如需查看浏览器窗口，添加 `--headed` 参数：

```bash
playwright-cli open https://playwright.dev --headed
```

### 会话管理

Playwright CLI 默认使用专用的持久化配置文件，这意味着 cookie 和其他存储状态在调用之间会被保留。您可以为不同项目使用不同的浏览器实例：

```bash
# 打开两个独立的浏览器会话
playwright-cli open https://playwright.dev
playwright-cli --session=example open https://example.com

# 查看所有会话
playwright-cli session-list
```

通过环境变量运行代理：

```bash
PLAYWRIGHT_CLI_SESSION=todo-app claude .
```

会话管理命令：

```bash
playwright-cli session-list              # 列出所有会话
playwright-cli session-stop [name]       # 停止会话
playwright-cli session-stop-all          # 停止所有会话
playwright-cli session-delete [name]     # 删除会话数据和配置文件
```

## 命令参考

### 核心操作

```bash
playwright-cli open <url>               # 打开 URL
playwright-cli close                    # 关闭页面
playwright-cli type <text>              # 在可编辑元素中输入文本
playwright-cli click <ref> [button]     # 在网页上执行点击
playwright-cli dblclick <ref> [button]  # 执行双击
playwright-cli fill <ref> <text>        # 填充文本到可编辑元素
playwright-cli drag <startRef> <endRef> # 拖放操作
playwright-cli hover <ref>              # 悬停在元素上
playwright-cli select <ref> <val>       # 在下拉框中选择选项
playwright-cli upload <file>            # 上传文件
playwright-cli check <ref>              # 勾选复选框或单选按钮
playwright-cli uncheck <ref>            # 取消勾选复选框
playwright-cli snapshot                 # 捕获页面快照以获取元素引用
playwright-cli eval <func> [ref]        # 在页面或元素上执行 JavaScript 表达式
playwright-cli dialog-accept [prompt]   # 接受对话框
playwright-cli dialog-dismiss           # 关闭对话框
playwright-cli resize <w> <h>           # 调整浏览器窗口大小
```

### 导航

```bash
playwright-cli go-back                  # 返回上一页
playwright-cli go-forward               # 前进到下一页
playwright-cli reload                   # 重新加载当前页面
```

### 键盘操作

```bash
playwright-cli press <key>              # 按键，例如 'a'、'ArrowLeft'
playwright-cli keydown <key>            # 按下键
playwright-cli keyup <key>              # 释放键
```

### 鼠标操作

```bash
playwright-cli mousemove <x> <y>        # 移动鼠标到指定位置
playwright-cli mousedown [button]       # 按下鼠标
playwright-cli mouseup [button]         # 释放鼠标
playwright-cli mousewheel <dx> <dy>     # 滚动鼠标滚轮
```

### 保存内容

```bash
playwright-cli screenshot [ref]         # 截取当前页面或元素的屏幕截图
playwright-cli pdf                      # 将页面保存为 PDF
```

### 标签页管理

```bash
playwright-cli tab-list                 # 列出所有标签页
playwright-cli tab-new [url]            # 创建新标签页
playwright-cli tab-close [index]        # 关闭浏览器标签页
playwright-cli tab-select <index>       # 选择浏览器标签页
```

### 开发者工具

```bash
playwright-cli console [min-level]      # 列出控制台消息
playwright-cli network                  # 列出页面加载以来的所有网络请求
playwright-cli run-code <code>          # 运行 Playwright 代码片段
playwright-cli tracing-start            # 开始跟踪记录
playwright-cli tracing-stop             # 停止跟踪记录
```

## 配置文件

Playwright CLI 可以使用 JSON 配置文件进行配置。通过 `--config` 命令行选项指定配置文件：

```bash
playwright-cli --config path/to/config.json open example.com
```

默认情况下，Playwright CLI 会从 `playwright-cli.json` 加载配置，因此无需每次都指定。

## 项目信息

- **许可证**：Apache-2.0
- **Star 数量**：1.9k+
- **使用者**：227 个项目
- **主要贡献者**：
  - Simon Knott (@Skn0tt)
  - Pavel Feldman (@pavelfeldman)
  - Salman Chishti (@salmanmkc)

## 总结

Playwright CLI 为现代编码代理提供了一个令牌高效的浏览器自动化解决方案。通过简洁的命令行界面和 SKILL 集成机制，它使得 AI 助手能够在有限的上下文窗口内高效地执行复杂的浏览器操作。无论是用于自动化测试、网页抓取还是端到端测试，Playwright CLI 都是一个值得尝试的强大工具。

更多信息请访问：

- [Playwright CLI GitHub 仓库](https://github.com/microsoft/playwright-cli)
- [Playwright 官方网站](https://playwright.dev/)
- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
