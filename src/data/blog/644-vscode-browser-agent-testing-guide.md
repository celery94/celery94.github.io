---
pubDatetime: 2026-03-17T03:59:09+00:00
title: "VS Code 的 browser agent tools，开始让 agent 自己下场测页面"
description: "微软这篇 browser agent tools 指南表面上是在教你做一个计算器，实际更值得看的是另一层：Copilot agent 不只是写 HTML、CSS、JavaScript 了，它还能把页面打开、自己点按钮、检查结果、发现 bug，再回头把代码修掉。对前端来说，这比单纯多几个浏览器自动化工具更有意思。"
tags: ["AI", "VS Code", "GitHub Copilot", "Browser Automation"]
slug: "vscode-browser-agent-testing-guide"
ogImage: "../../assets/644/01-cover.png"
source: "https://code.visualstudio.com/docs/copilot/guides/browser-agent-testing-guide"
---

![VS Code browser agent testing 工作流概念图](../../assets/644/01-cover.png)

用 agent 写前端代码这件事，大家越来越不满足于「帮我把页面写出来」了。更直接的问题是：它写完之后，能不能自己把页面打开，点一遍，看看哪里坏了，再顺手修掉？

微软这篇 `Build and test web apps with browser agent tools`，表面上是个入门文档：开浏览器工具、做个计算器、让 agent 测试。但它摆出来的东西，比「自动点按钮」更值得注意。

Copilot agent 现在不只是会生成代码，还能参与前端里那段最烦又绕不过去的活：把页面打开，验证交互，发现问题，再回到代码改。

## 这篇文档到底在教什么

文档开头写得很直白：browser agent tools 可以让 agent 在一个闭环里构建和验证 web 应用。

具体来说，这些事它现在能自己来：

- **构建**：生成 HTML、CSS、JavaScript
- **打开页面**：在 VS Code 集成浏览器里运行
- **交互测试**：点击、输入、悬停、拖拽
- **观察结果**：读页面内容、看截图、看控制台报错
- **修复问题**：改代码
- **再次验证**：重新跑一遍

如果你平时已经在用 agent 写前端代码，会很容易发现这里的区别。

以前很多 AI 编程体验停在“代码我先给你写出来”，接下来要不要开页面、点一下按钮、看结果对不对、看控制台有没有炸，还是得你自己来。browser agent tools 的价值，就是把这段后半程也拉进去了。

对做前端的人来说，这个变化比较实在：「写了代码」和「让代码在浏览器里跑起来被检验」，开始能由同一个 agent 全程干了。

## 计算器例子虽然简单，但选得挺好

微软拿来演示的是一个 calculator。这个例子很小，但故意设计得很完整：

- 先让 agent 生成 `index.html`、`styles.css` 和 `script.js`
- 再让它在集成浏览器里把页面打开
- 然后检查加减乘除是不是都正常
- 接着故意把“除零保护”删掉
- 再让 agent 自己发现问题、改代码、重新验证

这套设计的好处就是，你不会被 demo 本身分散注意力。它没有拿一个复杂应用出来炫技，而是拿一个所有人都看得懂的页面，把 agent loop 一步步摆给你看。

特别是「删掉除零保护，再让 agent 自己修」这一段很说明问题。它展示的不是 agent 会写计算器，而是：**agent 碰到真实的 bug，顺着页面结果找回代码，自己把问题修掉。**

## 先开功能，再给工具权限

这篇指南里还有两个挺具体、也挺容易被跳过的细节。

一个是设置项：你得先打开 `workbench.browser.enableChatTools`。

另一个是工具权限：在 Chat 里切到 Agent 模式后，还要去 tools picker 里确认浏览器相关工具已经启用。

这两个步骤说明了一件事，微软并没有把“让 agent 操作浏览器”做成默认无感知能力，而是要求你明确打开。这个态度我觉得是对的。毕竟一旦 agent 能读页面、点页面、输入内容，它就已经不只是“生成文本”了。

## 这套工具已经够 agent 干活了

文档里列出来的工具其实相当完整：

- 页面导航：`openBrowserPage`、`navigatePage`
- 页面读取：`readPage`、`screenshotPage`
- 用户交互：`clickElement`、`hoverElement`、`dragElement`、`typeInPage`、`handleDialog`
- 自定义自动化：`runPlaywrightCode`

你看这组接口，大概就能明白它不是在做一个“给 agent 看网页”的玩具功能，而是在给它一套能组合起来做事的浏览器动作。

这很重要，因为前端里很多问题不是靠读代码就能稳稳看出来的。你得真的把页面跑起来，点一下，输入一下，看看 DOM 变了没有，错误弹了没有，控制台吵起来没有。

有了这套工具之后，agent 至少不再只能站在代码旁边猜。它可以真的去碰页面。

## 安全边界写得很明白

这篇文档我很喜欢的一点，是它没有回避安全边界，而是写得挺清楚。

默认情况下，agent 自己打开的页面跑在私有、内存态、隔离的 session 里，不会和你别的标签页共享 cookies 或 storage。

这意味着什么？最直接的就是：你不用一上来就担心它摸到你平时浏览器里的登录态。

但文档也留了一个口子。如果你在集成浏览器里手动打开某个页面，然后点 `Share with Agent`，那 agent 就能接触这个页面，而且会带上你现有的 session、cookies 和登录状态。

这套设计我觉得挺合理：

- 默认隔离
- 主动分享才放权
- 共享状态和隔离状态分得很清楚

至少它不是那种“先全给，再让你自己祈祷别出事”的思路。

## 最适合它的，是这些验证任务

文档最后列了几种使用场景，我觉得基本都挺靠谱：

- 表单校验测试
- 响应式布局检查
- 登录流程测试
- 交互状态检查
- 可访问性审查

这些任务有个共同点：光看代码，不一定看得出来。

比如你写一个表单，代码表面上没问题，不代表错误提示真的会出现；你做一个响应式菜单，样式文件看着也没事，不代表窄屏下不会挤掉；你接一个登录流程，接口通了，也不代表跳转、错误提示、禁用态这些交互都对。

这类事情，本来就挺适合交给 agent 先跑一遍。不是因为它能替代完整测试，而是这些活重复、具体，结果也好判断：对就是对，错就是错。

## 分工边界开始松动

以前的习惯比较清楚：agent 负责写代码，开发者负责打开浏览器验收。browser agent tools 出来后，这个边界有了松动。

agent 先写，然后自己跑一轮 smoke check，把明显有问题的地方先找出来，人再接手做更细的判断。不是说测试思考可以不管了，离完整验收、复杂业务 E2E 都还远。只是第一轮的「页面跑起来有没有明显问题」，已经不必非得你亲自来了。

## 别把它想得太万能

这类能力现在很有意思，但边界也挺清楚。

今天它还是 **experimental**，文档和 integrated browser 页面都反复拿这个提醒你，接口和行为边界都还在变。

适合给它做的，是那些局部、明确、结果好判断的验证任务。测一个计算器、表单、登录页，比较顺手；想让它接管一整套复杂业务验收，还早。

它能看到页面，也不等于它理解页面。复杂状态、异步流程、多步交互这类场景，漏测和误判依然会有，别太寄望于它。

## 对前端开发者意味着什么

前端开发里最累的，其实不只是写页面，还有那堆反复的确认：点按钮、看状态、看报错、回去改、再点一遍。不复杂，就是烦。

browser agent tools 说的是，这里面有一部分现在可以先交给 agent 跑了。它打开页面、点交互、看报错，发现问题回到代码改，改完再来一遍。

> Copilot agent 开始能把页面打开，自己点一遍，带着结果再回到代码里去，而不只是把代码写给你看。

对做前端的人来说，这不只是多了几个新接口，更像是工作方式上开了一个小口子：**写完就测，测完就改，而且这轮循环开头那段，不一定非得是你。**

## 参考

- [Build and test web apps with browser agent tools](https://code.visualstudio.com/docs/copilot/guides/browser-agent-testing-guide) — Visual Studio Code Docs
- [Integrated browser in VS Code](https://code.visualstudio.com/docs/debugtest/integrated-browser) — Visual Studio Code Docs
- [Agents overview](https://code.visualstudio.com/docs/copilot/agents/overview) — Visual Studio Code Docs
