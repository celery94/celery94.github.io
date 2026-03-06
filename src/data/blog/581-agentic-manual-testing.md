---
pubDatetime: 2026-03-06
title: "代理式手工测试：代码会跑，代理才算真的开始工作"
description: "Simon Willison 这篇新文把一个现实问题说透了：自动化测试全绿，功能照样可能坏在启动、界面和交互细节上。让代理亲手运行 `python -c`、`curl`、Playwright 和可验证的测试笔记，才会把“看起来没问题”变成“真的跑过了”。"
tags: ["AI", "Agent", "Testing", "Playwright"]
slug: "agentic-manual-testing"
source: "https://simonwillison.net/guides/agentic-engineering-patterns/agentic-manual-testing/#atom-everything"
---

CI 刚跑完，整排绿色。你打开页面，菜单歪了；你点一下按钮，接口 500；你重启服务，应用直接挂掉。这样的场面，写过几年代码的人都见过。测试没有撒谎，只是它根本没覆盖到你真正关心的那一块。

Simon Willison 在 2026 年 3 月 6 日发布的《Agentic manual testing》说得很直接：编码代理最有价值的地方，不只是会写代码，而是会执行自己写出来的东西，并据此继续修。这个判断很关键。很多团队已经接受“让模型写代码”，还没真正接受“让代理自己把代码跑起来”。差别就在这里。

## 测试绿了，为什么我还是不信

单元测试当然重要。我自己也赞成把 red/green TDD 当成代理开发的默认手势，因为失败测试能把目标钉死，后面的实现空间再大，也不容易跑偏。但 Willison 提醒了另一件更现实的事：测试通过，只能说明你验证了某些假设，不能保证用户眼前的功能真的可用。

这就是代理式手工测试的价值。代理不是把代码贴出来就收工，它应该像一个不会嫌烦的初级同事那样，真的去运行、点击、请求、观察输出，再把新发现的问题送回自动化测试里。闭环才成立。

## 先让代理碰边界，再谈“完成”

文章里给了一组很实用的动作，而且都短得吓人。短，反而说明它们有用。你不需要给代理写一大段规范，只要把测试方式说清楚，它往往就会自己扩展出更多检查。

| 场景 | 让代理怎么试 | 你真正想确认什么 |
| --- | --- | --- |
| Python 函数 | 用 `python -c` 直接跑边界输入 | 返回值、异常、边界条件 |
| 其他语言函数 | 在临时目录写一个 demo 文件再编译运行 | 真实调用链有没有断 |
| JSON API | 启动开发服务器后用 `curl` 探索接口 | 状态码、字段结构、异常路径 |
| Web UI | 用 Playwright 或浏览器 CLI 走一遍流程 | 页面是否能用，布局是否跑偏 |

这里最有意思的是那个词：explore。你让代理“探索”一个 API，它通常不会只打一个 happy path 请求，而是会顺手试几个参数组合、几种失败情况、几个它怀疑会出错的分支。人类开发者会这样做，好的代理也该这样做。

原文里提到 Python 场景下可以直接要求：

```text
Try that new function on some edge cases using `python -c`
```

这个提示看起来很朴素，作用却很大。你把“写完代码”改成“把边界案例亲自跑一遍”，代理的注意力就会从语法正确，转到行为正确。方向完全不同。

## Web 界面最会骗人

后端开发者很容易对一排测试结果产生错觉，觉得系统已经稳了。真正会翻车的地方，往往是浏览器里那一层。布局错一格、按钮不可点、焦点跳错、懒加载没触发、弹窗挡住操作，这些问题都可能绕过现有测试。

Willison 在这一段把浏览器自动化讲得很明白。现在的代理很擅长控制真实浏览器，Playwright 已经足够强，很多时候你只要说一句“用 Playwright 测一下这个页面”，代理就知道该怎么开工。更进一步，还有专门为代理设计的 CLI 包装层，比如 Vercel 的 `agent-browser`，以及他自己的 `Rodney`。

他给出的 Rodney 提示词非常值得抄回自己的日常工作流：

```text
Start a dev server and then use `uvx rodney --help` to test the new homepage, look at screenshots to confirm the menu is in the right place
```

这个提示厉害的地方不在命令本身，而在它一次性交代了三件事：先把服务跑起来，再让工具自己解释能力，最后强制代理看截图确认视觉结果。你不是在问“这段代码对不对”，你是在问“用户看到的东西对不对”。这个转身非常值钱。

Rodney 的帮助信息也说明了这种工具为什么适合代理。它不只会打开页面、点击、输入，还能执行 JavaScript、截图、导出 PDF、读取可访问性树。手工测试到了这里，已经不只是“模拟点点点”，而是在收集可验证证据。

## 跑过还不够，得留下证据

很多代理工作在最后一步会露馅。它修了代码，声称测试过，描述听起来也头头是道，但你一追问“具体跑了什么、输出是什么、哪张截图能证明它真的看过页面”，空气就突然安静了。

Willison 为这个问题做了一个很聪明的小工具，叫 `Showboat`。它的思路我很喜欢：让代理一边测试，一边生成可复核的 Markdown 文档，把备注、命令和输出全部放进去。读文档的人既能理解过程，也能重新执行验证。

原文里的提示是：

```text
Run `uvx showboat --help` and then create a `notes/api-demo.md` showboat document and use it to test and document that new API.
```

Showboat 有三个核心命令：`note`、`exec` 和 `image`。其中最关键的是 `exec`，因为它会把命令和真实输出一起记录下来。代理想糊弄，就难了。它不能只写“接口返回正常”，它得把请求发出去，把结果贴进文档里。这个设计很朴素，也很狠。

我很认同这种做法。代理式开发的下一步，不是让代理说得更像人，而是让它留下更多可以被人检查的痕迹。文档、截图、命令输出、可访问性树，这些都算。只要证据链在，信任就有着力点。

## 真正该形成的闭环

手工测试不是自动化测试的替代品，它更像一张补盲网。代理通过 `python -c`、`curl`、浏览器自动化发现了新问题，下一步就该把这个问题收编进永久测试里。Willison 在文中又把 red/green TDD 拉了回来，我觉得这一步特别对。

流程应该长这样：先让代理把功能跑起来，撞到墙，定位问题，修复，然后新增能稳定复现这个问题的自动化测试。下一次再改到这里，团队就不用重复踩坑。代理式手工测试负责把盲点揪出来，TDD 负责把盲点焊死。配合起来，味道才对。

如果你已经在用编码代理，下一次别只说“把这个功能做完”。换成更具体的说法：把它跑起来、试试边界、看一眼页面、留下测试记录。很多本来会在评审或线上冒出来的问题，就会提前现形。代理开始自己验证的那一刻，才真的像个能合作的工程伙伴。规律很明确。

## 参考

- [原文](https://simonwillison.net/guides/agentic-engineering-patterns/agentic-manual-testing/) — Simon Willison
- [Red/green TDD](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/) — 代理先看失败测试，再实现代码
- [Playwright](https://playwright.dev/) — 浏览器自动化框架
- [Rodney help.txt](https://github.com/simonw/rodney/blob/main/help.txt) — 面向代理的浏览器自动化命令说明
- [Showboat help.txt](https://github.com/simonw/showboat/blob/main/help.txt) — 记录测试过程与输出的可执行文档工具