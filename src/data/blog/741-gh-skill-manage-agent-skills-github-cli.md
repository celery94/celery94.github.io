---
pubDatetime: 2026-04-17T09:40:00+08:00
title: "用 GitHub CLI 管理 Agent Skills：gh skill 命令正式发布"
description: "GitHub CLI v2.90.0 新增 gh skill 命令，支持一键安装、更新、发布 agent skills，兼容 GitHub Copilot、Claude Code、Cursor 等多个 AI agent 宿主，并内置版本锁定和供应链完整性保障机制。"
tags: ["GitHub", "CLI", "AI", "Copilot", "Agent"]
slug: "gh-skill-manage-agent-skills-github-cli"
ogImage: "../../assets/741/01-cover.png"
source: "https://github.blog/changelog/2026-04-16-manage-agent-skills-with-github-cli/"
---

![用 GitHub CLI 管理 Agent Skills](../../assets/741/01-cover.png)

GitHub CLI v2.90.0 带来了一个新子命令：`gh skill`。它的目标是解决一个实际问题——当 AI agent skills 越来越多，如何在终端里快速找到、安装、更新、发布它们，而不需要手动复制文件或查文档。

## 什么是 Agent Skills

Agent skills 是一种可移植的指令包，包含脚本、配置和说明，用来教 AI agent 如何完成特定任务。它们遵循开放的 [Agent Skills 规范](https://agentskills.io/)，可以在 GitHub Copilot、Claude Code、Cursor、Codex、Gemini CLI 等多个宿主上运行。

## 安装技能

更新 GitHub CLI 到 v2.90.0 或更新版本后，可以用以下命令安装技能：

```bash
# 交互式浏览仓库中的技能并选择安装
gh skill install github/awesome-copilot

# 直接安装指定技能
gh skill install github/awesome-copilot documentation-writer

# 安装指定版本（@tag）
gh skill install github/awesome-copilot documentation-writer@v1.2.0

# 安装到指定提交（@sha）
gh skill install github/awesome-copilot documentation-writer@abc123def
```

技能会自动安装到对应 agent 宿主的正确目录。如果你需要指定 agent 和作用域：

```bash
gh skill install github/awesome-copilot documentation-writer --agent claude-code --scope user
```

目前支持的宿主如下：

| 宿主 | 安装命令示例 |
|------|------------|
| GitHub Copilot | `gh skill install OWNER/REPO SKILL` |
| Claude Code | `gh skill install OWNER/REPO SKILL --agent claude-code` |
| Cursor | `gh skill install OWNER/REPO SKILL --agent cursor` |
| Codex | `gh skill install OWNER/REPO SKILL --agent codex` |
| Gemini CLI | `gh skill install OWNER/REPO SKILL --agent gemini` |
| Antigravity | `gh skill install OWNER/REPO SKILL --agent antigravity` |

## 搜索技能

```bash
gh skill search mcp-apps
```

## 版本锁定与供应链安全

Agent skills 本质上是可执行的指令，直接影响 AI agent 的行为。一个在两次安装之间悄悄改变内容的技能，是真实的供应链风险。`gh skill` 用 GitHub 已有的机制来解决这个问题：

**版本锁定**：用 `--pin` 固定到某个 tag 或 commit SHA。被锁定的技能在执行 `gh skill update` 时会被跳过，升级变成主动操作而非被动接受。

```bash
# 锁定到发布 tag
gh skill install github/awesome-copilot documentation-writer --pin v1.2.0

# 锁定到提交，获得最高可复现性
gh skill install github/awesome-copilot documentation-writer --pin abc123def
```

**内容寻址变更检测**：每个已安装技能都记录了源目录的 git tree SHA。执行 `gh skill update` 时，本地 SHA 与远端比较，检测的是实际内容变化，而不只是版本号。

**可移植的溯源信息**：安装时，`gh skill` 会把仓库名、引用、tree SHA 直接写入 `SKILL.md` 的 frontmatter。溯源数据随技能文件一起移动，无论技能被复制到哪个项目，都能追踪来源并完成更新。

**不可变发布**：`gh skill publish` 提供启用[不可变发布](https://docs.github.com/repositories/releasing-projects-on-github/about-releases)的选项，一旦启用，即便仓库管理员也无法修改已发布版本，通过 tag 锁定安装的用户可以获得完整保护。

## 保持技能更新

```bash
# 交互式检查更新
gh skill update

# 更新指定技能
gh skill update git-commit

# 全量更新，不提示确认
gh skill update --all
```

`gh skill update` 会扫描所有已知 agent 宿主目录，从每个技能的 frontmatter 读取溯源元数据，然后对比上游是否有变更。

## 发布自己的技能

如果你维护了一个技能仓库，可以用 `gh skill publish` 验证技能是否符合 [agentskills.io 规范](https://agentskills.io/specification)，并检查远端仓库的安全设置（tag 保护、密钥扫描、代码扫描等）。

```bash
# 验证所有技能
gh skill publish

# 自动修复元数据问题
gh skill publish --fix
```

这些安全设置不是强制要求，但官方强烈建议开启，以提升技能仓库的供应链安全性。

## 安全提示

官方特别提醒：技能并未经过 GitHub 验证，安装前务必审查内容，可以使用 `gh skill preview` 命令查看技能的实际内容，避免安装含有 prompt 注入、隐藏指令或恶意脚本的技能。

`gh skill` 目前处于公开预览阶段，API 可能随时变更。

## 参考

- [原文：Manage agent skills with GitHub CLI](https://github.blog/changelog/2026-04-16-manage-agent-skills-with-github-cli/)
- [Agent Skills 规范](https://agentskills.io/)
- [agentskills.io 规范文档](https://agentskills.io/specification)
- [GitHub 不可变发布文档](https://docs.github.com/repositories/releasing-projects-on-github/about-releases)
- [GitHub Community 讨论](https://github.com/orgs/community/discussions)
