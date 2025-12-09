---
agent: "agent"
tools:
  [
    "vscode",
    "execute",
    "read",
    "edit",
    "search",
    "web",
    "playwright/*",
    "microsoftdocs/mcp/*",
    "upstash/context7/*",
    "agent",
    "memory",
    "todo",
  ]
---

# 任务：将 URL 转换为高质量技术博客

你的目标是读取用户提供的 URL，提取核心价值内容，并将其重写为符合本博客风格的高质量技术文章。

## 1. 准备阶段

- **确定文章编号 (ID)**：
  - 使用 `ls src/data/blog` 查看现有文件。
  - 找到当前最大的编号（文件名格式为 `XXX-slug.md`）。
  - 新文章编号 = 最大编号 + 1（保持 3 位数字格式，例如 `095` -> `096`）。
- **确定 Slug**：
  - 将标题翻译为英文，并转换为 kebab-case（如 `clean-architecture-guide`）。
  - 仅使用小写字母、数字和连字符。

## 2. 内容获取与资源处理

- **获取内容**：使用 `playwright` 或 `web` 工具抓取 URL 的正文、代码和图表。
- **图片处理**（如果原文有价值的图表/截图）：
  - 创建目录：`src/assets/{ID}/`。
  - 将图片下载并保存到该目录。
  - 在 Markdown 中引用：`../../assets/{ID}/image-name.png`。
  - 为每张图片添加有意义的 `alt` 描述。

## 3. 内容重写规范

- **深度改写**：
  - **禁止**整段翻译或复制。必须理解后用自己的话重述。
  - **结构重组**：
    - **引言**：痛点、背景、本文解决的问题。
    - **核心原理**：深度解析，配合图表（如有）。
    - **实战代码**：提供可运行的代码片段，添加中文注释。
    - **总结**：优缺点、适用场景、最佳实践。
- **语言风格**：
  - 中文，专业、正式、流畅。
  - 保留专有名词英文（如 `Dependency Injection`, `Middleware`）。
  - 避免“流水账”或过度使用无意义的列表。

## 4. 文件输出

- **文件路径**：`src/data/blog/{ID}-{slug}.md`
- **Frontmatter 模板**：

```yaml
---
pubDatetime: YYYY-MM-DD # 当前日期
title: "文章标题（准确、吸引人）"
description: "文章摘要，概括核心价值（80-160字）"
tags: ["Tag1", "Tag2"] # 2-6个相关标签，如 .NET, Azure, Architecture
slug: "{slug}"
source: "{original_url}" # 原文链接
draft: false
---
# {Title}

## 引言
---
## {Section 1}
```

## 执行逻辑

1. **分析**：读取 URL，理解内容。
2. **规划**：确定 ID、Slug、大纲。
3. **资源**：下载必要图片。
4. **写作**：生成 Markdown 内容。
5. **保存**：写入文件。

请等待用户提供 URL，然后按照上述步骤执行。
