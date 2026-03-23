---
pubDatetime: 2026-03-23T10:00:00+08:00
title: "在编码 Agent 中使用 Git：从基础操作到历史重写"
description: "Simon Willison 总结了如何配合 AI 编码 Agent 发挥 Git 的全部潜力——从常用提示词到撤销提交、bisect 调试、从旧仓库提取模块，让 Git 的高级功能对每个人都变得触手可及。"
tags: ["Git", "AI", "Coding Agent", "LLM", "Developer Tools"]
slug: "using-git-with-coding-agents"
ogImage: "../../assets/657/01-cover.png"
source: "https://simonwillison.net/guides/agentic-engineering-patterns/using-git-with-coding-agents/"
---

![在编码 Agent 中使用 Git](../../assets/657/01-cover.png)

Git 是和编码 Agent 配合工作的核心工具。代码放进版本控制，就意味着每一次变更都有记录，出问题随时可以追溯和回滚。更重要的是，所有主流编码 Agent 对 Git 的掌握程度相当深——不只是基本命令，连 bisect、reflog、rebase 这类高级用法也能轻松驾驭。

这篇文章整理自 Simon Willison 的 *Agentic Engineering Patterns* 指南中"Using Git with coding agents"章节，内容涵盖 Git 基础回顾、可以直接复用的提示词模板，以及如何借助 Agent 解锁历史重写这类平时让人望而却步的操作。

---

## Git 基础回顾

这里不是从零讲 Git，而是补充几个和 Agent 配合时用得上的前提。

- 每个 Git 项目是一个**仓库（repository）**，记录该目录下所有文件的变更历史
- 变更以**提交（commit）**为单位组织，每次提交有时间戳、作者和描述消息
- **分支（branch）**让你能并行构建多个特性，互不干扰，完成后再合并
- 仓库可以克隆到本地，克隆包含完整历史——浏览历史不需要网络请求，基本上是免费的
- 本地仓库可以推送到**远端（remote）**，GitHub 是最常用的托管服务

Agent 完全理解上面这些概念和对应术语，你直接用英文或中文描述意图就行，不需要背命令。

---

## 常用提示词

以下是 Simon Willison 总结的一组可以直接照搬的提示词，适用于大多数编码 Agent。

### 初始化和提交

```
Start a new Git repo here
```

在当前目录初始化仓库，Agent 会运行 `git init`。

```
Commit these changes
```

Agent 会把当前变更打包成一次提交，通常会自动生成一条有意义的提交消息。Willison 的原话：现在的前沿模型在写提交消息方面品味相当不错，他已经不再坚持自己写了。

### 快速了解近期进展

```
Review changes made today
```

或者"review recent changes"、"review last three commits"。在一个新的 Agent 会话开始时，让它跑一遍 `git log`，能快速把最近做了什么加载进上下文。后续你就可以接着讨论这些改动，而不用重新描述背景。

### 集成其他分支的变更

```
Integrate latest changes from main
```

不记得 merge、rebase、squash、fast-forward 的区别？可以先问：

```
Discuss options for integrating changes from main
```

Agent 会解释各种合并策略的利弊，帮你做决定。Git 里的操作几乎都可以撤销，试错成本很低。

### 解决 Git 乱局

```
Sort out this git mess for me
```

遇到 rebase 冲突、暂存区搞乱、拉取后一团糟——直接把这句话扔给 Agent。Willison 说这是他使用频率出乎意料地高的一句话。以前处理合并冲突是最耗时的工作之一，现在的 Agent 能理解新旧两侧代码的意图，配合自动化测试，把冲突处理得相当干净。

### 找回丢失的代码

```
Find and recover my code that does ...
```

如果某段已提交（或 `git stash` 过）的代码找不到了，Agent 可以搜索 reflog，也会翻查其他分支。告诉它你要找什么，让它去挖。

### 用 bisect 定位 Bug 引入点

```
Use git bisect to find when this bug was introduced: ...
```

`git bisect` 是 Git 最强的调试工具之一，但学习曲线较陡，很多人平时不用。它的原理是让你提供一个测试条件和一个提交区间，Git 用二分查找锁定"第一次出现这个 bug 的提交"。

用 Agent 处理 bisect 的模板代码，只需描述 bug 的表现，Agent 负责其余部分。这让 bisect 从偶尔能用升级成随手可用。

---

## 历史重写

Git 的提交历史不是固定不变的——数据本质上就是磁盘上的文件（存在隐藏的 `.git/` 目录里），Git 本身提供了修改历史的工具。

Willison 的建议是：**不要把 Git 历史当作真实发生的事情的永久记录，而应当把它看作对项目演进过程刻意编排的叙述。** 这个叙述是为了服务未来的开发，保留所有错误的记录未必有价值，仓库维护者可以做编辑决策。

编码 Agent 非常擅长处理下面这类操作。

### 撤销和改写提交

```
Undo last commit
```

提交完发现提交了不该提交的文件？`git reset --soft HEAD~1` 可以解决，但没多少人能背出来——现在也不需要了。

```
Remove uv.lock from that last commit
```

精细化修改提交内容，比如从上一次提交里删掉某个文件。

```
Combine last three commits with a better commit message
```

把多次提交合并成一个，同时优化消息描述。

### 从旧仓库提取模块到新仓库

Willison 常用的一个技巧：把一个大仓库里的某段代码提取出来，建成独立的新仓库，同时保留相关的提交历史。

```
Start a new repo at /tmp/distance-functions and build a Python library there
with the lib/distance_functions.py module from here - build a similar commit
history copying the author and commit dates in the new repo
```

以前做这类操作太麻烦，大多数人直接新建仓库，历史就丢掉了。现在不用妥协，Agent 可以帮你把提交历史一并迁移过去。

---

## 小结

Git 本来就是开发者工具箱里最重要的东西之一，配合编码 Agent 之后，那些平时记不住、用不熟的高级功能——bisect、rebase、history rewriting——变得触手可及。关键是知道这些能力存在，需要时告诉 Agent 你想做什么，而不是自己去查命令。

## 参考

- [Using Git with coding agents – Simon Willison's Weblog](https://simonwillison.net/guides/agentic-engineering-patterns/using-git-with-coding-agents/)
- [Agentic Engineering Patterns 系列指南](https://simonwillison.net/guides/agentic-engineering-patterns/)
