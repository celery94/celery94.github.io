---
pubDatetime: 2025-04-01 12:26:21
tags: ["Productivity", "Tools"]
slug: git-who-command-line-tool
source: https://github.com/sinclairtarget/git-who
title: 🚀 深度解读 `git-who`：一个比 `git blame` 更强大的代码分析工具
description: 了解如何使用 `git-who` 进行代码库贡献者分析，追踪整个文件树的作者信息，提高代码协作效率。
---

# 🚀 深度解读 `git-who`：一个比 `git blame` 更强大的代码分析工具

在软件开发过程中，你是否曾想过这样的问题：“到底是谁写了这段代码？谁是某个模块的主要维护者？”今天我们为大家介绍一款开源命令行工具——`git-who`，它能轻松回答这些问题，并比 `git blame` 提供更广泛的分析功能。

![工具界面截图](https://github.com/sinclairtarget/git-who/raw/master/screenshots/vanity.png)

## 🧐 什么是 `git-who`？

`git-who` 是一款命令行工具，专注于分析代码库的贡献者信息。与 `git blame` 的单文件行级别分析不同，`git-who` 更注重整个文件树或组件的贡献者分布情况。你可以快速了解谁是某个子系统的主要开发者，以及具体的代码贡献情况。

核心功能包括：

- 按作者划分贡献情况。
- 提供多个视图：贡献表格、文件树和时间线。
- 支持过滤选项：按路径、日期范围和作者筛选。
- 集成 `.mailmap` 和 `.git-blame-ignore-revs` 文件，优化作者归属。

## 📦 安装指南

### 方法一：预编译二进制文件

访问 [GitHub Releases](https://github.com/sinclairtarget/git-who/releases)，下载适合你的系统的二进制文件。

### 方法二：使用包管理器

#### Mac OS

通过 Homebrew 安装：

```bash
brew install git-who
```

#### Arch Linux

在 AUR 上获取：[AUR Package](https://aur.archlinux.org/packages/git-who)。

### 方法三：Docker 安装

如果你不想直接安装，可以使用 Docker 容器运行 `git-who`：

1. 构建镜像：
   ```bash
   docker build -t git-who -f docker/Dockerfile .
   ```
2. 使用 Docker 运行：
   ```bash
   docker run --rm -it -v "$(pwd)":/git -v "$HOME":/root git-who who
   ```

### 方法四：源码编译

你需要安装 Go、Ruby 和 Rake 工具：

```bash
git clone git@github.com:sinclairtarget/git-who.git
cd git-who
rake
./git-who --version
```

## 🛠️ 使用方法详解

`git-who` 提供了三个子命令，分别用于不同视角的贡献者分析：

### 📊 表格模式：`table`

默认子命令会输出一个表格，展示每位作者的贡献情况，包括最近编辑时间、提交次数等：

```bash
git who
```

输出示例：

```
┌─────────────────────────────────────┐
│Author           Last Edit   Commits │
├─────────────────────────────────────┤
│Guido van Rossum 2 mon. ago   11,213 │
│Victor Stinner   1 week ago    7,193 │
│Fred Drake       13 yr. ago    5,465 │
│...3,026 more...                     │
└─────────────────────────────────────┘
```

支持按路径过滤：

```bash
git who Tools/
```

以及按分支或版本号过滤：

```bash
git who v3.7.1
```

#### 🌟 可选参数：

- `-m`: 按最后编辑时间排序。
- `-l`: 按修改的代码行数排序。
- `-f`: 按修改的文件数排序。
- `-n <数字>`: 输出更多行，`-n 0` 显示所有结果。

---

### 🌲 文件树模式：`tree`

打印文件树并标注每个路径的主要贡献者。默认根据提交次数计算：

```bash
git who tree Parser/
```

输出示例：

```
Parser/.........................Guido van Rossum (182)
├── lexer/......................Pablo Galindo Salgado (5)
│   ├── buffer.c................Lysandros Nikolaou (1)
│   └── state.h.................Pablo Galindo Salgado (1)
└── token.c.....................Pablo Galindo Salgado (2)
```

可以使用 `-a` 参数强制显示所有文件，包括已删除的历史文件：

```bash
git who tree -a Parser/
```

#### 🌟 可选参数：

- `-d <深度>`: 限制显示深度。
- `-l`: 按修改行数统计贡献者。
- `-f`: 按修改文件数统计贡献者。

---

### ⏳ 时间线模式：`hist`

绘制年度或月份贡献时间线，显示主要贡献者及其提交比例：

```bash
git who hist
```

输出示例：

```
2023 ┤ ###---------------                    Victor Stinner (556)
2024 ┤ ##-----------------                   Serhiy Storchaka (321)
2025 ┤ #                                     Bénédikt Tran (27)
```

支持按路径或版本过滤贡献时间线：

```bash
git who hist v3.12.0.. iOS/
```

#### 🌟 可选参数：

- `-l`: 按修改行数显示时间线。

---

## 🔍 高级功能

### 🧹 作者归属优化：Git Mailmap 支持

对于使用多个名字或邮箱地址的开发者，可以通过 `.mailmap` 文件统一归属。具体配置方式参考 [Git mailmap 文档](https://git-scm.com/docs/gitmailmap)。

### 🚫 忽略提交：Git Blame Ignore Revs 支持

通过 `.git-blame-ignore-revs` 文件，可以忽略格式化等无实际改动意义的提交。这些提交不会计入统计。

### 🔧 过滤选项

支持以下过滤条件：

- `--author` 和 `--nauthor`: 包含或排除特定作者。
- `--since` 和 `--until`: 按日期范围筛选提交。

例如，仅显示 Guido van Rossum 最近九个月的修改路径：

```bash
git who tree -d 1 --since "nine months ago" --author "Guido van Rossum"
```

## 🤔 与 `git blame` 的比较

虽然两者都用于分析代码历史，但侧重点不同：

- **`git blame`**：告诉你每行代码的最近编辑者。
- **`git-who`**：关注整体模块或文件树的贡献情况，更适合大范围分析。

举例说明：
如果某文件被 Bob 修改多次，但 Alice 最近做了一次格式化，`git blame` 会将大部分行归属于 Alice，而 `git-who` 会认为 Bob 是主要贡献者。

综合来看，两个工具各有优势，可结合使用获得完整视图。

---

## 🌟 总结

无论你是开源项目维护者，还是团队协作中的代码审查员，`git-who` 都是一款不可多得的利器。它不仅帮助你快速了解代码库的历史，还能优化协作流程，提升开发效率。

赶快试试吧！🎉

👉 项目地址：[GitHub - git-who](https://github.com/sinclairtarget/git-who)  
👉 更多文档：[Who Will Maintain Vim? A Demo of Git Who](https://sinclairtarget.com/blog/2025/03/who-will-maintain-vim-a-demo-of-git-who/)
