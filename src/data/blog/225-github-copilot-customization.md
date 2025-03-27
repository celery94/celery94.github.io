---
pubDatetime: 2025-03-27 12:21:22
tags: [GitHub Copilot, VS Code, 编程技巧, 人工智能]
slug: github-copilot-customization
source: https://code.visualstudio.com/blogs/2025/03/26/custom-instructions
title: 从智能到超智能！深度揭秘 GitHub Copilot 自定义指令的魔法🎩
description: 通过自定义配置和提示文件，全面解锁 GitHub Copilot 的潜能，让人工智能真正成为你的开发助手！
---

# 从智能到超智能！深度揭秘 GitHub Copilot 自定义指令的魔法🎩

现代开发者的工作已经离不开人工智能的辅助工具，而 Visual Studio Code 和 GitHub Copilot 的结合更是让这一趋势变得不可忽视。今天，我们将带你深入了解如何通过自定义指令和提示文件，让 GitHub Copilot 不再仅仅是一个代码生成工具，而是你的专属开发助手！

---

## 🚀 为什么需要自定义指令？

GitHub Copilot 的强大之处在于它能够根据你的输入生成相关代码，但有时我们发现它的响应可能不够精准或不符合团队的工作习惯。自定义指令的出现解决了这一问题：通过一系列简单的设置，你可以让 Copilot 更好地理解你的项目背景、代码风格以及工作流，从而提供更贴合需求的建议。

### 🤔 如何开始？

你只需创建一个 `.github/copilot-instructions.md` 文件即可开始。这是一个简单的 Markdown 文件，用来告诉 Copilot 项目背景和编码标准。例如：

```markdown
# Copilot Instructions

这个项目是一个任务管理的 Web 应用程序，基于 React 和 Node.js 构建，使用 MongoDB 作为数据库。

## 编码标准

- 使用 camelCase 命名变量和函数。
- 组件名称使用 PascalCase。
- 字符串统一使用单引号。
- 缩进采用 2 个空格。
- 回调函数使用箭头函数。
- 异步代码使用 async/await。
- 常量使用 const，可重赋值变量使用 let。
```

创建完成后，Copilot 会自动读取这些指令，无需额外配置。现在，你只需输入简短提示，例如 `尾递归`，它就会根据你的编码标准生成符合要求的代码。

![在 VS Code 中创建指令文件的截图](https://code.visualstudio.com/assets/blogs/2025/03/26/dot-github.jpg)

---

## 🎨 自定义所有功能！

GitHub Copilot 不仅可以生成代码，还能帮助完成提交消息、代码审查甚至测试生成。通过自定义工作空间设置，你可以让这些功能更加贴合团队需求。例如，我们可以个性化提交消息：

### 💬 自定义提交信息

打开 VS Code 的命令面板（快捷键：`Ctrl+Shift+P`），选择 **Preferences: Open Workspace Settings (JSON)**，并添加以下配置：

```json
{
  "github.copilot.chat.commitMessageGeneration.instructions": [
    {
      "text": "请详细描述文件更改的内容和原因，并使用大量 emoji。"
    }
  ]
}
```

保存设置后，当你让 Copilot 自动生成提交消息时，它会以更丰富的细节和有趣的 emoji 提供信息。

例如：
![自定义提交消息示例](https://code.visualstudio.com/assets/blogs/2025/03/26/git-commit.jpg)

---

## 📁 多文件支持：解锁更多可能性！

团队中可能存在多种语言或规范需求，例如 JavaScript、Python 和数据库设计标准。通过在 `.vscode/settings.json` 文件中配置多个指令文件，你可以将这些内容分开管理：

```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    {
      "file": "./docs/javascript-styles.md"
    },
    {
      "file": "./docs/database-styles.md"
    }
  ]
}
```

这种方式不仅提升了文档管理效率，还能让 Copilot 更好地理解不同领域的开发规范。

![多指令文件的配置示例](https://code.visualstudio.com/assets/blogs/2025/03/26/docs.jpg)

---

## 🌟 改变模型语气：为开发注入个性

如果你觉得模型的回答过于客套或不够直接，可以通过语气调整让它更加符合你的风格。以下是一些示例指令：

```markdown
- 如果用户指出错误，请基于事实回应，而不是直接道歉。
- 避免使用夸张或兴奋语气，专注任务本身。
- 回答时避免含有“您是对的”或“是的”这种附和语句。
```

甚至可以尝试一些有趣的方式，比如让它以 **俳句格式** 生成测试代码：

```markdown
- 用俳句格式生成测试。
- 使用 5-7-5 的音节结构。
- 运用自然主题和意象。
```

---

## ✨ 提示文件：团队协作的神器

提示文件（Prompt Files）是一种可复用的 Markdown 文件，用于定义复杂任务或团队共享的上下文。例如，创建一个描述用户数据库结构的提示文件：

```markdown
# 用户认证

我们的应用程序用户表包含以下字段：

- 标准用户信息：`name` 和唯一标识 `email`。
- 一个用于登录的“魔法链接”，包括 `GUID` 和过期时间。
- 社交登录账户 ID（支持 Microsoft、GitHub 和 Google）。
- 用户上次登录时间戳。
```

然后，你可以创建另一个文件引用这个结构来生成 TypeScript 接口：

```markdown
生成一个 TypeScript 接口，基于用户表结构。参考 [用户表结构](database_users.prompt.md)。
```

通过 VS Code 中的聊天界面，你可以轻松附加这些提示文件，让团队协作更高效。

![如何在聊天中使用提示文件](https://code.visualstudio.com/assets/blogs/2025/03/26/prompts.gif)

---

## 🎉 结语

GitHub Copilot 不仅仅是一个编程工具，它通过定制化变成了开发者工作流中不可或缺的一部分。通过自定义指令和提示文件，你可以让 AI 真正理解你的项目背景、风格偏好，甚至是团队协作中的独特需求。

快动手试试吧！相信它能为你的开发旅程注入新的动力。

💻 **Happy Coding!**
