---
pubDatetime: 2026-04-01T10:55:00+08:00
title: "解决 Ghostty SSH 连接时 xterm-ghostty unknown terminal 报错"
description: "使用 Ghostty 终端 SSH 到远程服务器时，常见 'Error opening terminal: xterm-ghostty' 或 'WARNING: terminal is not fully functional' 报错。这篇文章解释了根本原因，并提供三种修复方案。"
tags: ["Ghostty", "SSH", "终端", "terminfo", "Linux"]
slug: "ghostty-ssh-terminfo-fix"
ogImage: "../../assets/700/01-cover.png"
source: "https://ghostty.org/docs/help/terminfo#ssh"
---

用 Ghostty 连 SSH 第一次进远程服务器，大概率会看到这样的报错：

```
Error opening terminal: xterm-ghostty.
missing or unsuitable terminal: xterm-ghostty
WARNING: terminal is not fully functional
```

这不是 Ghostty 的 bug，也不是服务器坏了。根本原因是 **terminfo 没有同步到远程机器**。这篇文章解释来龙去脉，然后给出三种修复方式。

## 为什么会出这个错

terminfo 是一个描述终端能力的数据库格式，告诉应用程序这个终端支持什么颜色、什么控制序列、光标怎么移动。Ghostty 用的 TERM 值是 `xterm-ghostty`，并且在安装时把对应的 terminfo 条目写到本机数据库里。

当你 SSH 到远程服务器，`TERM=xterm-ghostty` 这个环境变量也跟着传过去了，但远程服务器上没有这条 terminfo 记录，所以 `vim`、`tmux`、`less` 这类依赖 terminfo 的程序就会报错甚至拒绝启动。

> Ghostty 用 `xterm-ghostty` 而不是纯 `ghostty` 是有意为之——很多程序会 string match `TERM` 是否包含 `xterm` 来判断基础兼容性，纯 `ghostty` 会让太多程序出错。

## 方案一：把 terminfo 条目复制到远程机器（推荐）

一行命令搞定：

```bash
infocmp -x xterm-ghostty | ssh YOUR-SERVER -- tic -x -
```

这会把本机的 `xterm-ghostty` terminfo 定义通过管道传给远程服务器上的 `tic` 编译并安装。执行一次，之后所有连接这台机器都不再报错。

`tic` 优先写入系统路径 `/usr/share/terminfo`，没有权限时会退回 `$HOME/.terminfo`（目录需要存在）。

**macOS Sonoma 之前的用户注意**：系统自带的 `infocmp` 版本太旧，会输出 `Illegal character` 错误。需要先用 Homebrew 安装新版：

```bash
brew install ncurses
/opt/homebrew/opt/ncurses/bin/infocmp -x xterm-ghostty | ssh YOUR-SERVER -- tic -x -
```

## 方案二：SSH 配置降级 TERM（简单快速）

在 `~/.ssh/config` 里为指定主机设置回退值：

```
Host example.com
  SetEnv TERM=xterm-256color
```

需要 **OpenSSH 8.7 或更新版本**。这样连接时 TERM 会被替换成 `xterm-256color`，绝大多数服务器都有这个 terminfo，不会再报错。

代价是：彩色下划线、Ghostty 特有的终端功能在这台服务器上不可用，但日常使用完全够用。

## 方案三：Ghostty 自动处理（最省心）

在 Ghostty 配置文件里加一行：

```
shell-integration-features = ssh-terminfo,ssh-env
```

- `ssh-terminfo`：第一次连接新服务器时自动执行方案一，把 terminfo 条目装进去
- `ssh-env`：自动为 SSH 连接应用方案二的 TERM 降级配置

两个都启用时，Ghostty 会先尝试安装 terminfo，装不进去再自动 fallback 到降级。

## 顺带一提：sudo 也有同样问题

如果你在远程服务器上 sudo 后看到 `missing or unsuitable terminal: xterm-ghostty`，原因相同：sudo 默认会重置环境变量，`TERMINFO` 也跟着没了。

解决方式是在 Ghostty 配置里加：

```
shell-integration-features = sudo
```

这会把 sudo 别名为自动保留 `TERMINFO` 环境变量的版本。

## 总结

| 场景 | 推荐方案 |
|---|---|
| 你有权限写远程服务器，追求完整功能 | 方案一：`infocmp` 复制 terminfo |
| 服务器你没有 sudo 权限 | 方案二：SSH config SetEnv |
| 管理多台机器，不想手动操作 | 方案三：Ghostty shell-integration-features |
| 都要，自动判断 | `ssh-terminfo,ssh-env` 同时开启 |

Ghostty 的 terminfo 条目已经进了 ncurses 6.5-20241228，随着各发行版更新，这个问题会逐渐自然消失。但在那之前，上面这几行配置是最快的解法。

## 参考

- [Ghostty Terminfo 文档](https://ghostty.org/docs/help/terminfo#ssh)
- [shell-integration-features 配置参考](https://ghostty.org/docs/config/reference#shell-integration-features)
