---
pubDatetime: 2026-03-27T09:40:00+08:00
title: "OpenAI Codex 插件机制详解：打包、分发与构建可复用工作流"
description: "本文介绍 OpenAI Codex Plugins 的核心概念与使用方式——包括插件包含什么、如何在 CLI 和应用中安装、如何创建本地插件、以及 plugin.json 清单的完整字段说明，帮助团队把工作流打包成可分发的插件。"
tags: ["OpenAI", "Codex", "AI编程", "插件", "MCP"]
slug: "openai-codex-plugins-build-and-distribute"
ogImage: "../../assets/682/01-cover.png"
source: "https://developers.openai.com/codex/plugins"
---

![OpenAI Codex Plugins 概念图](../../assets/682/01-cover.png)

Codex 的 Skills 功能让你可以在某个项目里定义专属工作流，但如果同样的技能想在多个项目或整个团队里复用，每次手动配置就很繁琐。Plugins 是 Codex 给这个场景提供的解法：把 Skills、App 集成和 MCP 服务器配置打包成一个可安装单元，一次配置、到处使用。

## 插件能包含什么

一个插件（Plugin）本质上是一个可安装的工作流包，可以包含三类组件：

- **Skills**：描述特定工作流的提示词，Codex 可以渐进式发现并调用它们
- **Apps**：可选的 App 集成或连接器映射
- **MCP Servers**：插件依赖的远程工具或共享上下文配置

官方说明还提到"更多插件组件即将推出"，说明这个体系还在扩展中。

## 安装和使用插件

### 在 Codex 应用中

OpenAI 维护了一个官方 Plugin Directory，里面是团队精选的插件，适合直接拿来用的现成工作流和 App 集成。在 Codex 应用内打开插件目录即可浏览安装。

### 在 CLI 中

在 Codex CLI 里运行以下命令打开插件管理界面：

```
codex
/plugins
```

### 本地加载插件

最快的方式是用内置的 `@plugin-creator` 技能来脚手架一个本地插件。它会自动创建所需的 `.codex-plugin/plugin.json` 清单文件，也可以生成一个本地 marketplace 条目用于测试。

如果你已经有一个来自其他地方的插件，或者自己构建好的插件，同样可以通过 `@plugin-creator` 把它加入本地 marketplace。

手动安装时，根据插件的访问范围选择对应的 marketplace 文件路径：

- **仓库级（Repo marketplace）**：`$REPO_ROOT/.agents/plugins/marketplace.json`，插件存放在 `$REPO_ROOT/plugins/`
- **个人级（Personal marketplace）**：`~/.agents/plugins/marketplace.json`

#### 仓库级手动安装步骤

**Step 1**：把插件文件夹复制到仓库

```bash
mkdir -p ./plugins
cp -R /absolute/path/to/my-plugin ./plugins/my-plugin
```

**Step 2**：新建或更新 `$REPO_ROOT/.agents/plugins/marketplace.json`，其中 `source.path` 用相对路径指向插件目录：

```json
{
  "name": "local-repo",
  "plugins": [
    {
      "name": "my-plugin",
      "source": {
        "source": "local",
        "path": "./plugins/my-plugin"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

**Step 3**：重启 Codex，确认插件在列表中出现。

`source.path` 是相对于 marketplace 文件所在目录来解析的，不是相对于 `.agents/plugins/` 文件夹。调整过插件内容后，更新 marketplace 条目指向的目录并重启 Codex，本地安装会读取新文件。

## Marketplace 元数据格式

marketplace.json 的完整格式：

```json
{
  "name": "openai-curated",
  "interface": {
    "displayName": "ChatGPT Official"
  },
  "plugins": [
    {
      "name": "my-plugin",
      "source": {
        "source": "local",
        "path": "./plugins/my-plugin"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

几个关键点：

- 顶层 `name` 是 marketplace 标识符
- `interface.displayName` 是 Codex 界面里显示的 marketplace 名称
- `policy.installation` 支持 `AVAILABLE`、`INSTALLED_BY_DEFAULT`、`NOT_AVAILABLE` 三个值
- `policy.authentication` 控制认证时机：安装时还是首次使用时

Codex 支持同时从三个来源读取 marketplace：官方精选目录、仓库级 marketplace、个人级 marketplace。

插件安装后缓存在 `~/.codex/plugins/cache/$MARKETPLACE_NAME/$PLUGIN_NAME/$VERSION/`，每个插件的启用/禁用状态存储在 `~/.codex/config.toml`。

## 构建和发布插件

### 什么时候用本地 Skills，什么时候用插件

| 场景 | 推荐 |
|------|------|
| 只针对一个仓库或一个工作流迭代 | 本地 Skills |
| 行为是个人的或项目特定的 | 本地 Skills |
| 在打包之前先验证想法 | 本地 Skills |
| 同一套技能在多个团队或项目中使用 | Plugin |
| 把 Skills、MCP 配置和 App 集成打包成一个安装单元 | Plugin |
| 需要稳定的版本化包给队友或 marketplace | Plugin |

官方的建议是：先在本地迭代，准备好分享时再打包成插件。

### 插件目录结构

每个插件必须有一个清单文件位于 `.codex-plugin/plugin.json`。完整结构如下：

```
my-plugin/
├── .codex-plugin/
│   └── plugin.json       ← 唯一必须的文件
├── skills/
│   └── my-skill/
│       └── SKILL.md
├── .mcp.json             ← MCP 服务器配置（可选）
├── .app.json             ← App 集成配置（可选）
└── assets/
    ├── icon.png
    └── logo.png
```

`.codex-plugin/` 目录里只放 `plugin.json`，其他所有内容放在插件根目录。

### 创建第一个插件

最简单的插件只需两步。

**Step 1**：创建插件目录和清单

```bash
mkdir -p my-first-plugin/.codex-plugin
```

`my-first-plugin/.codex-plugin/plugin.json`：

```json
{
  "name": "my-first-plugin",
  "version": "1.0.0",
  "description": "Reusable greeting workflow",
  "skills": "./skills/"
}
```

插件的 `name` 要用 kebab-case，它是插件标识符，也是组件命名空间的基础，后续版本更新时不要改名。

**Step 2**：在 `skills/<skill-name>/SKILL.md` 添加一个技能

```bash
mkdir -p my-first-plugin/skills/hello
```

`my-first-plugin/skills/hello/SKILL.md`：

```
---
name: hello
description: Greet the user with a friendly message.
---

Greet the user warmly and ask how you can help.
```

然后按照前面"本地加载插件"的步骤，把这个插件加进 marketplace 里，在 Codex 里安装即可。后续可以按需追加 MCP 配置、App 集成或 marketplace 元数据。

### 完整的 plugin.json 清单示例

发布给团队的插件通常比最简示例有更多字段：

```json
{
  "name": "my-plugin",
  "version": "0.1.0",
  "description": "Bundle reusable skills and app integrations.",
  "author": {
    "name": "Your team",
    "email": "team@example.com",
    "url": "https://example.com"
  },
  "homepage": "https://example.com/plugins/my-plugin",
  "repository": "https://github.com/example/my-plugin",
  "license": "MIT",
  "keywords": ["research", "crm"],
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "apps": "./.app.json",
  "interface": {
    "displayName": "My Plugin",
    "shortDescription": "Reusable skills and apps",
    "longDescription": "Distribute skills and app integrations together.",
    "developerName": "Your team",
    "category": "Productivity",
    "capabilities": ["Read", "Write"],
    "websiteURL": "https://example.com",
    "privacyPolicyURL": "https://example.com/privacy",
    "termsOfServiceURL": "https://example.com/terms",
    "defaultPrompt": [
      "Use My Plugin to summarize new CRM notes.",
      "Use My Plugin to triage new customer follow-ups."
    ],
    "brandColor": "#10A37F",
    "composerIcon": "./assets/icon.png",
    "logo": "./assets/logo.png",
    "screenshots": ["./assets/screenshot-1.png"]
  }
}
```

### 清单字段说明

**顶层字段**：
- `name`、`version`、`description`：标识插件
- `author`、`homepage`、`repository`、`license`、`keywords`：发布者和发现元数据
- `skills`、`mcpServers`、`apps`：指向各组件的路径（相对于插件根目录，以 `./` 开头）

**`interface` 字段**：
- `displayName`、`shortDescription`、`longDescription`：标题和描述文案
- `developerName`、`category`、`capabilities`：发布者和能力标签
- `websiteURL`、`privacyPolicyURL`、`termsOfServiceURL`：外部链接
- `defaultPrompt`、`brandColor`、`composerIcon`、`logo`、`screenshots`：建议提示词和视觉呈现

所有路径都要相对于插件根目录，并以 `./` 开头。视觉资产建议统一放在 `./assets/` 目录下。

## 关于发布到官方目录

目前，向官方 Plugin Directory 提交插件的功能"即将推出"，自助发布和管理功能也还在路上。现阶段可以先在本地或团队内部的 marketplace 中使用和打磨插件。

## 参考

- [Codex Plugins 官方文档](https://developers.openai.com/codex/plugins)
- [Codex Skills 文档](https://developers.openai.com/codex/skills)
- [Codex MCP 配置](https://developers.openai.com/codex/mcp)
