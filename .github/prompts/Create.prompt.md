---
mode: agent
---

- 接收用户提供的网页 URL，使用playwright MCP获取该页面的主要内容（正文、标题、关键内容/图示）。
- 将图片保存到 src\assets\{编号}\ 下，并在正文中以相对路径引用该目录下的图片。
- 在充分理解的基础上进行深度改写与扩展：重组结构、补充背景/原理/对比/最佳实践与示例，输出一篇可发布的高质量技术分享文章。
- 使用context7 MCP进行内容理解与改写，确保内容准确且专业。
- 语言：中文，风格正式、专业、清晰，适合博客发布；尽量避免“流水账式”或“堆砌式”表述。
- 禁止整段复制粘贴原文；必须用自己的话重述与总结，确保不侵犯版权；保留专有名词的英文表述。
- 避免“列表堆砌”的写法，正文以段落阐述为主；如确有必要，可在局部使用小段落列表，但不要让整篇文章变成清单。
- 代码块需可复制运行或最小可验证；必要处添加注释与输入/输出说明。
- 引用外部资源时，务必标明出处，并确保链接有效。

文件与资源规范

- 文章保存路径：src\data\blog
- 文件名规则：{下一个自增编号}-{slug}.md（slug 用小写 kebab-case，仅含字母/数字/连字符；尽量英文，长度 < 60）
- 图片资源：若需插图，请将图片保存到 src\assets\{编号}\ 下，并在正文中以相对路径引用该目录下的图片；使用 Markdown 图片语法，并为每张图片提供有意义的 alt 文本。

Frontmatter 要求（与站点校验一致）

- 必填：pubDatetime（YYYY-MM-DD）、title、description（80-160 字）、tags（2-6 个）

SEO 与可读性

- title 准确凝练，不夸张；slug 与 title 语义一致。
- description 概括主题与价值，避免口号化；控制在 80-160 汉字。
- tags 选择领域相关、常用的标签（如 .NET、Azure、AI、Clean Architecture、Security、DevOps 等）。

输出要求

- 直接输出以下模板中的内容，不包含任何额外解释或多余文本。

---

pubDatetime: yyyy-MM-dd
title: 标题
description: 简短而完整的摘要（80-160 字）
tags: ["tag1", "tag2"]
slug: slug-in-kebab-case
source: https://original-article-url

---

# 标题

## 子标题 1

## 子标题 2
