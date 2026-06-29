---
pubDatetime: 2026-06-30T07:35:48+08:00
title: "Git 2.55 更新亮点：MIDX 增量重打包、git history fixup 与更多"
description: "Git 2.55 发布，带来增量多包索引的几何重打包、git history fixup 修复历史提交、Linux inotify 文件监控、并行钩子、位图生成提速近一倍和众多新特性。"
tags: ["Git", "Open Source", "DevTools"]
slug: "git-2-55-highlights"
ogImage: "../../assets/913/01-cover.png"
source: "https://github.blog/open-source/git/highlights-from-git-2-55/"
---

Git 2.55 发布了，来自 100 多位贡献者，其中 33 位是新人。以下是 GitHub 整理的本次最值得关注的特性和变更。

## 增量多包索引的几何重打包

Git 把仓库内容存储为独立的对象——commit、tree、blob——这些对象通常放在 packfile 里。大的仓库不会只有一个 packfile：随着时间推移，fetch、push、维护和重打包操作会留下许多 pack。

**多包索引**（MIDX）让 Git 可以通过一个索引跨多个 pack 查找对象，这对大仓库特别重要，也是 GitHub 仓库维护策略的基础。

Git 2.47 引入了**增量 MIDX**：把 MIDX 存成链状的层，每层覆盖一部分 pack。追加新层不会使旧层失效，所以 Git 可以在不重写整个仓库的 MIDX 的情况下给新 pack 建索引。

Git 2.55 教会了 `git repack` 直接写入增量 MIDX 链：

```bash
$ git repack --write-midx=incremental
$ git repack --write-midx=incremental --geometric=2 -d
```

`--geometric` 模式结合增量 MIDX 后，重打包不再是纯追加式的。Git 按配置的 `repack.midxSplitFactor` 决定相邻层是否应该被合并：如果较新层的累计对象数相对下一层长得足够大，Git 把它们合并成一个替换层；否则旧层保持不变。

结果是两层极端之间的折中：单体 MIDX 最小化查找复杂度但维护时需要大重写；纯追加式增量 MIDX 最小化每次写入但链可以无限增长。几何增量重打包保持层数对总对象数呈对数级，同时确保最新、最小的层比老的、大的层被更频繁地重写。

## git history fixup：修复更早的提交

打磨提交系列准备送审时经常会碰到：工作树里的改动其实属于更早的一个提交。以前的做法是创建 fixup 提交然后 autosquash：

```bash
$ git commit --fixup=<commit>
$ git rebase --autosquash <commit>^
```

Git 2.55 给实验性的 `git history` 命令新增了 `fixup` 子命令，把暂存区的改动应用到更早的提交上：

```bash
$ git history fixup <commit>
```

目标提交保留它的消息和作者信息（除非传了 `--reedit-message`），Git 重写后续提交，让分支以一个等价的、fix 在正确位置的历史结束。如果应用暂存改动会产生冲突，命令会直接中止而非把你留在一个有状态重写的中间。

## 其他值得关注的新特性

### 配置化钩子现在可以并行运行

Git 2.54 引入了基于配置的钩子，Git 2.55 允许兼容的钩子并行执行。声明 `hook.<name>.parallel = true` 后，独立的 pre-commit 钩子（比如 lint 和单元测试）可以同时跑。并发数可以用 `hook.jobs`、`hook.<event>.jobs` 或 `git hook run -j` 控制。

### 内置文件系统监控支持 Linux

`git status` 慢是常见痛点，而 `core.fsmonitor` 让 Git 可以问一个长期运行的守护进程哪些路径变了而不是扫描整个工作树。此前内置守护进程只有 macOS 和 Windows 支持，Git 2.55 通过 Linux inotify 扩展到了 Linux。

### 可达性位图生成速度翻倍

位图让 Git 不用从零遍历对象图就能回答"哪些对象可以从这个提交到达"，让对象遍历更快。Git 2.55 通过避免不必要的树递归、复用已计算位图、缓存对象位置等优化，在大仓库上将位图生成时间从约 **612 秒降到 294 秒**。

### --path-walk 支持过滤器

`git pack-objects --path-walk`（2.51 引入）按路径分组对象再做第二遍压缩。2.55 让它支持 `blob:none`、`tree:0`、`sparse:<oid>` 等过滤器，路径遍历重打包可在更多部分克隆和过滤 pack 的工作流中使用。

### git format-rev：标准输入流式格式化提交

新的实验命令，从标准输入读取提交并格式化。适合 `git last-modified` 等流式输出场景，不需要为每行 fork 一个 Git 进程：

```bash
$ git last-modified | git format-rev --stdin-mode=text --format=%an
```

### git checkout -m 内部使用 autostash

以前 `git checkout -m` 在遇到冲突时立即要求你解决。Git 2.55 在内部使用 autostash，把冲突的本地改动存成 stash 条目，可以立即解决也可以稍后重新应用。

### git push 支持远程组

远程组（配置为 `remotes.<name>`）以前只对 `git fetch` 可用。现在 `git push publish main` 会依次推到组里的每个远程。

### --graph-lane-limit 限制图宽度

`git log --graph` 在多分支仓库里图 lane 可以占满终端。`--graph-lane-limit=<n>` 把超出限制的 lane 替换为 `~`。

### --max-count-oldest 取最老的 N 个提交

`git log -n 10` 拿最近的 10 个，要最老的 10 个一直很别扭。新增 `--max-count-oldest=<n>` 直接选出范围内最老的 N 个提交。

### 服务端进度消息的终端控制字符过滤

fetch 和 push 时服务端的进度消息可能包含任意终端控制序列。Git 2.55 默认屏蔽了大部分控制字符，同时保留 ANSI 颜色序列。

### 改进 fetch 协商控制

新增对 fetch 协商中哪些引用参与的控制选项和 `remote.*` 配置，允许用户要求特定 ref 作为 have 行发送或把协商限制在某个引用集合内。

## 参考

- [Highlights from Git 2.55 — GitHub Blog](https://github.blog/open-source/git/highlights-from-git-2-55/)
- [Git 2.55 Release Notes](https://github.com/git/git/blob/v2.55.0/Documentation/RelNotes/2.55.0.adoc)
- [The Git repository](https://github.com/git/git)
