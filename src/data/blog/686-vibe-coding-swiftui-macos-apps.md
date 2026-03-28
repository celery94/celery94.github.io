---
pubDatetime: 2026-03-28T13:17:27+08:00
title: "用 AI Vibe Coding 写 SwiftUI 应用：两个 macOS 系统监控工具的实战体验"
description: "Simon Willison 用 Claude Code 在不懂 Swift 的情况下，用自然语言提示快速构建了两个 macOS 菜单栏应用：Bandwidther（网络带宽）和 Gpuer（GPU 内存监控），记录了整个 vibe coding 过程及关键经验。"
tags: ["AI", "SwiftUI", "macOS", "Vibe Coding", "Claude"]
slug: "vibe-coding-swiftui-macos-apps"
ogImage: "../../assets/686/01-cover.png"
source: "https://simonwillison.net/2026/Mar/27/vibe-coding-swiftui/"
---

Simon Willison 换了一台 128GB 的 M5 MacBook Pro，跑大型本地 LLM 的性能表现让他相当满意。但 macOS 自带的 Activity Monitor 让他越来越不耐烦——它看不清具体哪个进程在用网络，GPU 和统一内存的细节也藏得很深。于是他决定用 vibe coding 的方式，直接让 Claude Code 帮他写两个替代工具。

整个过程他几乎没看过 Swift 代码，但两个具备实用功能的 macOS 菜单栏应用就这样建成了。

![vibe coding macOS 应用封面图](../../assets/686/01-cover.png)

## 两个应用：Bandwidther 和 Gpuer

**Bandwidther** 是第一个，起因是想看看 Dropbox 在把文件从旧电脑同步过来时，走的是局域网还是互联网。

初始对话非常直接：

> "Show me how much network bandwidth is in use from this machine to the internet as opposed to local LAN"

然后：

> "mkdir /tmp/bandwidther and write a native Swift UI app in there that shows me these details on a live ongoing basis"

第一版就跑起来了。确认方向可行后，他接着让 Claude 提议可以加哪些功能——这里有个思路值得借鉴：让模型来推测"能做什么"，而不是自己去想。之后又是几轮迭代：加进程带宽、加反向 DNS 解析、调整为双栏布局，最后：

> "OK make it a task bar icon thing, when I click the icon I want the app to appear, the icon itself should be a neat minimal little thing"

变成了菜单栏应用。完整对话记录他已经开源，可以在 [simonw/bandwidther](https://github.com/simonw/bandwidther) 找到。

**Gpuer** 是第二个，几乎是同步进行的。Apple Silicon 的统一内存架构让 Activity Monitor 显示的数据很难解读，他想要一个能看清 GPU 利用率和内存分布的工具。

这次他用了一个技巧：把已经在开发中的 Bandwidther 作为参照：

> "Look at /tmp/bandwidther and then create a similar app in /tmp/gpuer which shows the information from above on an ongoing basis, or maybe does it better"

等 Bandwidther 更新成菜单栏模式后，他直接让 Gpuer 跟进：

> "Now take a look at recent changes in /tmp/bandwidther—that app now uses a sys tray icon, imitate that"

Simon 把这种方式叫做"recombine elements"（重组已有经验），是他在使用 AI 编程 agent 时最喜欢的技巧之一：把一个项目里已经验证可行的模式，让 AI 直接搬到另一个项目里。

Gpuer 的代码在 [simonw/gpuer](https://github.com/simonw/gpuer)。

## 这些应用值不值得信任

Simon 自己加了一句警告：他不懂 Swift，几乎没看代码，也不熟悉 macOS 系统内部的指标计算逻辑。他完全没有能力判断这些数字是否准确。

实际上，他在某天早上发现 Gpuer 报告只剩 5GB 内存，但 Activity Monitor 明显不是这个情况。他把截图粘贴给 Claude Code，Claude [调整了计算方式](https://github.com/simonw/gpuer/commit/a3cd655f5ccb274d3561e4cbfcc771b0bb7e256a)，新的数字"看起来"对了——但他还是不敢确定。

这是 vibe coding 很典型的局限：代码在跑，界面在刷，但如果你不懂底层，你根本不知道自己在看一个正确的结果还是一个看起来合理的错误。

> "I only shared them on GitHub because I think they're interesting as an example of what Claude can do with SwiftUI."

## 做下来学到的几件事

尽管对数字没有信心，但整个过程还是带来了一些具体的认知：

- 一个 SwiftUI 应用可以只靠一个文件完成大量功能。GpuerApp.swift 是 880 行，BandwidtherApp.swift 是 1063 行。
- 用 Swift 把终端命令包一层成 GUI，实现起来相当直接。
- Claude 对 SwiftUI 的设计审美出乎意料地好。
- 把应用变成菜单栏应用只需要额外几行代码。
- 全程不需要打开 Xcode。

这是他第二次尝试用 vibe coding 写 macOS 原生应用（[第一次是几周前做的一个演示工具](https://simonwillison.net/2026/Feb/25/present/)）。他的结论是：用 SwiftUI 写 macOS 应用是一个他以后应该纳入考虑的新选项。

对于想做类似尝试的开发者，有几点现实参考：Claude Code 对 SwiftUI 的掌握程度确实够用；整个应用放在单文件里让上下文管理变得简单；而"让 AI 参考另一个项目"的方式，在跨项目复用模式时效果很好。至于数字对不对、代码安不安全——那还是需要你自己懂才能判断。

## 参考

- [原文：Vibe coding SwiftUI apps is a lot of fun](https://simonwillison.net/2026/Mar/27/vibe-coding-swiftui/)
- [simonw/bandwidther on GitHub](https://github.com/simonw/bandwidther)
- [simonw/gpuer on GitHub](https://github.com/simonw/gpuer)
- [Bandwidther 构建对话记录](https://gisthost.github.io/?6e06d4724c64c10d1fc3fbe19d9c8575/index.html)
- [Gpuer 构建对话记录](https://gisthost.github.io/?71ffe216ceca8d7da59a07c478d17529)
