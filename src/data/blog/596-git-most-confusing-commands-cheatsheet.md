---
pubDatetime: 2026-03-12
title: "Git 最容易混的 6 个命令，中文速查表"
description: "`checkout`、`switch`、`restore`、`reset`、`revert`、`clean` 总让人脑子打结。这篇速查表不讲 Git 历史八卦，只讲每个命令到底改哪里、什么时候该用、什么时候别手滑。"
tags: ["Git", "Developer Tools", "Version Control"]
slug: "git-most-confusing-commands-cheatsheet"
ogImage: "../../assets/596/01-cover.png"
source: "https://susam.net/git-checkout-reset-restore.html"
---

![Git 命令速查表概念图](../../assets/596/01-cover.png)

Git 最烦人的地方，不是它强，而是它老爱让几个命令长得像、作用范围却完全不同。你以为自己是在“撤销一下”，结果分支指针挪了，暂存区变了，工作区也一起被洗掉，整个人当场清醒。

这一页就是给这种时刻准备的。别硬背定义，先记住 Git 里有三块地方：**工作区**是你眼前的文件，**暂存区**是下一次 commit 准备提交的内容，**提交历史**是已经写进仓库的记录。大多数混乱，都是因为你没想清楚自己到底想改哪一层。

## 先看总表

| 命令           | 它主要动哪里                         | 最常见用途                | 危险等级 |
| -------------- | ------------------------------------ | ------------------------- | -------- |
| `git checkout` | 分支、也可能动工作区                 | 老式切分支、老式还原文件  | 中       |
| `git switch`   | 分支                                 | 切分支                    | 低       |
| `git restore`  | 工作区、暂存区                       | 丢掉修改、取消暂存        | 中       |
| `git reset`    | 分支指针、暂存区，有时连工作区一起动 | 回退、取消暂存、重置状态  | 高       |
| `git revert`   | 提交历史（通过新增一条反向提交）     | 安全撤销已经提交的改动    | 低       |
| `git clean`    | 未跟踪文件                           | 删除 build 产物、临时文件 | 高       |

如果你只想先有个不太会出事的判断，记这三句就够了：

- **切分支，用 `switch`**
- **改文件和暂存区，用 `restore`**
- **改历史和指针，再想 `reset`**

## 1. `git checkout`：Git 的老瑞士军刀

`checkout` 最大的问题，不是不好用，而是它以前什么都干。你可以拿它切分支，也可以拿它把文件改回去。一个命令塞了两种心智模型，初学者很容易被它拐进沟里。

```bash
git checkout feature/login
```

这是老派切分支写法。

```bash
git checkout -- src/app.js
git checkout .
```

这是老派还原文件写法，意思是从某个已知状态把文件内容覆盖回工作区。

今天再看，`checkout` 更像历史包袱。它还能用，但不再是最清楚的表达。

> 看到 `checkout`，先别急着敲。问自己一句：我是想切分支，还是想还原文件？

## 2. `git switch`：只管切分支，脑子轻松很多

`switch` 是 Git 后来补上的“分支专用命令”。它解决的不是功能缺失，而是语义太乱。现在你只要是切分支，优先用它，出错概率会低很多。

```bash
git switch main
git switch feature/login
git switch -c feature/payment
```

几个高频场景：

- `git switch main`，切到已有分支
- `git switch -c feature/payment`，创建并切到新分支
- `git switch -`，切回上一个分支

它不会像 `checkout` 那样顺便承担“还原文件”的职责，所以读命令时几乎没有歧义。

在 AI 辅助开发越来越普遍的今天，这种语义清晰的小改进反而更重要。人和智能体都更容易理解 `switch` 的意图，不容易把“切分支”和“恢复文件”混成一锅。

## 3. `git restore`：只处理文件和暂存区，不碰历史

如果你想撤销本地修改，或者把已经 `add` 进去的东西拿出来，`restore` 才是现在更顺手的工具。

### 丢掉工作区修改

```bash
git restore src/app.js
git restore .
```

这会把工作区文件恢复成“和暂存区一致”。注意，它默认动的是**工作区**，不是提交历史。

### 取消暂存，但保留本地修改

```bash
git restore --staged src/app.js
git restore --staged .
```

这相当于把文件从暂存区拿下来，但你写的内容还留在工作区，适合“刚才 `git add .` 手太快了”的场景。

### 工作区和暂存区一起恢复

```bash
git restore --worktree --staged .
```

这条就重了。它会把工作区和暂存区一起恢复到 `HEAD`，效果接近 `git reset --hard`，只是表达更直接。

Susam Pal 那篇文章最有用的部分，就是把这组映射写清楚了：

| 老写法             | 新写法                              | 实际效果               |
| ------------------ | ----------------------------------- | ---------------------- |
| `git checkout .`   | `git restore .`                     | 只重置工作区           |
| `git reset`        | `git restore --staged .`            | 只重置暂存区           |
| `git reset --hard` | `git restore --worktree --staged .` | 工作区和暂存区一起重置 |

这也是 Git 近几年一个很实际的变化。命令没有更强，但边界更清楚了。AI 可以帮你补命令，真正减少事故的，还是这种清晰的概念分层。

## 4. `git reset`：威力很大，因为它会动“指针”

`reset` 是最容易让人手心出汗的命令之一，因为它不只是“撤销改动”，它本质上是在改 **HEAD 和当前分支指针的位置**。

### 最温和的用法：取消暂存

```bash
git reset
git reset HEAD src/app.js
```

这是很多人最常用的场景，把暂存区恢复到 `HEAD`，工作区内容保留。

### 回退提交，但保留文件改动

```bash
git reset --soft HEAD~1
```

回退一个 commit，但改动还留在暂存区，适合“提交信息写烂了，我想重提一次”。

### 回退提交，保留工作区改动

```bash
git reset --mixed HEAD~1
```

`--mixed` 是默认模式。commit 没了，暂存区也回去了，但文件内容还在工作区。

### 全部硬回退

```bash
git reset --hard HEAD~1
```

这条会直接把提交、暂存区、工作区一起回退。没推送前它很爽，推送后乱用它，队友会想把你也一起 reset 掉。

> `reset` 不是不能用，而是每次用之前都要先说清楚：我到底是在改提交历史，还是只想处理暂存区？

AI 时代这条反而更值得提醒。智能体很会补全命令，但它未必知道你是不是已经 push、是不是在共享分支、是不是还有没备份的本地文件。这类判断，暂时还得人来兜底。

## 5. `git revert`：已经提交出去的改动，优先想它

如果某个 commit 已经推送到了远端，而且别人可能基于它继续工作，优先考虑 `revert`，不是 `reset`。

```bash
git revert <commit>
```

它不会改写历史，而是新增一个“反向提交”，把之前那个 commit 的效果抵消掉。这样做的好处很现实：

- 历史连续，团队容易理解
- 不会强迫别人 rebase 或强制同步
- 出问题时也更容易追查

很多 Git 新手以为“撤销一个 commit”就该 `reset`。其实一旦 commit 已公开，`revert` 往往才是成熟团队的默认答案。

这也是一个今天依然没变的原则：**AI 可以加快你写提交、整理 diff、解释冲突，但公共历史要不要改写，仍然是协作判断，不是补全判断。**

## 6. `git clean`：专门处理 Git 不跟踪的垃圾

你 build 之后冒出来一堆临时文件、缓存目录、产物文件，这些不在 Git 跟踪范围内，`restore` 和 `reset` 都不会管。这时候才轮到 `clean`。

```bash
git clean -n
```

先预演，看看它准备删什么。

```bash
git clean -f
```

删除未跟踪文件。

```bash
git clean -fd
```

连未跟踪目录一起删。

```bash
git clean -fdx
```

连 `.gitignore` 忽略的文件也删，比如 `node_modules`、构建缓存。这条很猛，只有你真的想把工作区洗干净时再用。

`clean` 的坑在于，它动的是 Git 视角里的“陌生文件”。这些文件虽然没进仓库，但可能正好是你手工放进去的测试数据、下载的补丁、还没来得及 add 的脚本。先 `-n` 再决定，是最基本的礼貌。

## 什么时候该用哪个

如果你只想快速定位，按这个顺序想：

| 你的目标                 | 优先命令                      |
| ------------------------ | ----------------------------- |
| 切到另一个分支           | `git switch`                  |
| 创建并切到新分支         | `git switch -c <branch>`      |
| 丢掉某个文件的本地修改   | `git restore <file>`          |
| 取消暂存                 | `git restore --staged <file>` |
| 回退本地提交，重写历史   | `git reset`                   |
| 撤销一个已经 push 的提交 | `git revert <commit>`         |
| 删除未跟踪文件和目录     | `git clean -fd`               |

## 一句话速记版

- **`switch`**：分支切换器
- **`restore`**：文件和暂存区修复器
- **`reset`**：历史和指针改造器
- **`revert`**：公共历史安全撤销器
- **`clean`**：工作区垃圾清理器
- **`checkout`**：历史遗留多面手，现在尽量少碰

Git 这些命令看上去像一锅面，其实只要先分清工作区、暂存区、历史，很多事就不乱了。今天 AI 已经能替你补出大半条命令，但“我想动哪一层、这次回退会不会影响别人”这类问题，还是工程判断本身。这个部分，没过时，短时间内也不会。

## 参考

- [Git Checkout, Reset and Restore](https://susam.net/git-checkout-reset-restore.html) — Susam Pal
- [git-restore Documentation](https://git-scm.com/docs/git-restore) — Git
- [git-switch Documentation](https://git-scm.com/docs/git-switch) — Git
- [git-reset Documentation](https://git-scm.com/docs/git-reset) — Git
- [git-revert Documentation](https://git-scm.com/docs/git-revert) — Git
- [git-clean Documentation](https://git-scm.com/docs/git-clean) — Git
