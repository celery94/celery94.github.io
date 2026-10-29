---
pubDatetime: 2026-10-29T07:54:16+08:00
title: "REA 让 agent 一天重做 PowerToys 取色器"
description: "REA 是给 AI agent 的逆向工程工具集。原文作者在 Windows 上装好它，一天内重建 PowerToys 取色器核心，核对 9 条结论并划出合规边界。"
tags: ["REA", "Claude Code", "Reverse Engineering", ".NET", "AI Agents"]
slug: "reverse-engineer-anything-rea"
ogImage: "../../assets/1120/01-cover.png"
source: "https://codewithmukesh.com/blog/reverse-engineer-anything-rea/"
---

把 `PowerToys.ColorPickerUI.dll` 交给 Claude Code，问它取色器按下鼠标那一刻调了哪些 Windows API，拿回来的是一串带编号的证据：`ShellExecuteExW` 启动 UI、`fMask` 是 `0x440`、`CopyFromScreen` 配合 `GetPixel` 读像素、剪贴板写入带重试。每条都附上被分析文件的 SHA-256、用的是哪个分析后端，以及一份「这条结论不知道什么」的说明。Mukesh Murugan 用 REA（Reverse Engineer Anything）走完这条链路，一天内用 .NET 10 把取色核心重做成小工具 hexgrab，再拿 PowerToys 0.98.0 的真实源码逐条对账：9 条结论，8 条全对，1 条部分对。

REA 是免费、MIT 许可的 CLI 加 MCP server，装一次就把一批逆向工程工具挂到 agent 身上。它不还原原始源码，也不能一键克隆别人的 app，交付的是「有证据的实现解释」。值得用与否取决于两个前提：目标在法律和许可证上允许你研究，以及你愿意花时间核对 agent 说出来的结论。后一个前提常被跳过，而这条工具链上最费工夫的恰恰是它。另外，这个项目在两周里从 6.4.0 跑到 6.8.0，安装要求、工具数量和 star 数都在变，涉及这些的数字下面都标了版本或采集日期。

## REA 把逆向工具挂进 agent 的上下文

拆开看，REA 由三块部件组成。第一块是 MCP server，MCP 是给 agent 挂新工具的开放协议，原文写作时的 6.4.0 暴露了 170 个工具，到 6.8.0 已经是 229 个，名字很直白：`open_binary`、`search_strings`、`procedure_pseudo_code`。第二块是一个 skill，教 agent 一套流程：先大范围扫，再收证据，把观察到的和猜到的分开，最后才动手写。第三块是分析后端：.NET 和 JavaScript 由 REA 直接读文件，原生代码交给外部反编译器。

每次工具调用返回一条证据记录，包含编号、被分析文件的 SHA-256、使用的后端、结果，以及限制说明。价值就在这条记录里。agent 说某个函数会启动另一个进程时，它能指回那条记录；你也能在采信之前自己去翻。

支持的输入大致分五类，各自需要的额外工具不同：

| 目标                        | 拿到什么                              | 额外需要                    |
| --------------------------- | ------------------------------------- | --------------------------- |
| .NET 程序集                 | 类型、方法、IL、对 Windows API 的调用 | 无                          |
| JavaScript 与 Electron 应用 | 模块、imports、source map、IPC 通道   | Node.js                     |
| 原生 EXE、DLL、Mach-O、ELF  | 伪代码、汇编、字符串、调用图          | Ghidra、IDA、Hopper 或 Kuna |
| 网站与 HAR 文件             | 页面结构、脚本、网络请求              | Chrome 系浏览器             |
| Android APK                 | Manifest、类、反编译方法              | JADX 和完整 JDK             |

客户端这边，6.4.0 的 setup 支持 17 个（Claude Code、Codex、Cursor、Gemini CLI、Claude Desktop 都在内），现在到 25 个；其余本地 MCP 客户端可以手动注册。原文的实验全部在 Claude Code 里完成。

## 走红的是新包装，拆解工具已经 35 岁

仓库 2026 年 4 月 14 日创建，第一个 npm 包 7 月 12 日发布，当时还只是 Hopper 的自动化层。到 10 月 11 日，rea-agents 已经发了 31 个版本，最新是 6.4.0。十月第一周，X 上几个大号转发后曲线陡了起来，有条帖子把那一刻叫作「Software is done」。10 月 9 日它成了 GitHub trending 第一，原作者四天后去查，数字是 192,024 stars、46,722 forks。

再往后就是另一条曲线了。2026 年 10 月 29 日查官方仓库，数字是 402,471 stars、100,891 forks，版本 6.8.0（10 月 25 日发布）。不到三周翻了一倍，这种项目最难写「最新情况」，只能把采集日期写清楚。

这些数字容易让人以为底层技术也是新的。原生代码这边，干重活的还是几十年前就有的工具：IDA 在 1991 年 5 月由 Ilfak Guilfanov 以共享软件形式发布，2008 年起由 Hex-Rays 维护；Ghidra 在 NSA 内部开发，源码注释能追到 1999 年，2019 年 3 月 5 日在 RSA 大会公开；Hopper 在 2012 年前后就已经是 macOS 上的常用反汇编器。把机器码翻成人能读的伪代码，这件事没有变化。

变的是谁在操作这些工具。以前你得自己判断该打开哪个函数、怎么跟交叉引用、怎么啃一堆没有名字的 C 代码；现在用自然语言提问，agent 去点、去翻、去写结论，门槛降了一大截。这个项目值钱的是 agent 与那些反编译器之间的那层胶水。

同一条时间线上还有件麻烦事。走红之后 GitHub 上冒出仿冒仓库，有的打着「REA zip 下载」的旗号。官方 README 专门警告过这一点：只认 `morluto/rea` 仓库、`rea.tools` 和 npm 上的 `rea-agents` 包，仓库名相似或 README 被抄过都不等于下载源可信。

## 装之前先确认你有权研究这个软件

REA 是工具，合法与否取决于你把镜头对准什么，以及你所在司法辖区的规定。原文把这段放在安装步骤之前，值得照做；下面这些是作者在原文里的判断，不构成法律意见。

先看许可证和协议。多数商业软件禁止逆向工程。作者本来想研究自己常用的听写软件 Wispr Flow，翻到服务条款 3.A 明写禁止反编译和逆向，于是换掉了目标。

版权是另一条线。从反编译结果里抄代码、图标或文案，哪怕动机是学习，也构成侵权。绕过许可证校验、DRM 或加密在很多国家另有专门规定，比如美国 DMCA 第 1201 条；被反复引用的互操作性例外（美国 1201(f)、欧盟 2009/24/EC 第 6 条）不等于允许你克隆一个产品。

他自己执行的规则有五条：

- 只研究宽松许可（MIT、Apache 2.0、BSD）的软件，或者你自己拥有的软件
- 用官方安装的版本，不用破解或泄漏的构建
- 自己写实现，绝不把反编译代码或素材粘进项目
- 注明来源项目，用自己的名字和品牌
- 即使目标是开源软件，也不绕过许可证校验、认证或 DRM

按这套规则，他选的实验目标是 Microsoft PowerToys 的取色器。它用 MIT 许可，源码公开，意味着 REA 的每条结论都能拿去和真实代码对账。能对账的目标才适合用来判断工具准不准，这一点比「能合法用」更实用。

## Windows 上的安装分四步

前置条件：Windows 11、Node.js（6.8.0 要求 22.23.4+、24.22.1+ 或 26.12.1+，带 npm）、一个编码 agent。JDK 不是必装项，只有分析 Android APK（JADX 要完整 JDK）和使用 Ghidra 时才需要。要碰原生 C/C++ 二进制，再加 Ghidra 12.x（至少 12.1）和 64 位 JDK 21 以上。

第一步装 CLI。原文钉了 6.4.0，现在没必要钉旧版：

```bash
npm install --global rea-agents
rea --version
```

钉 `@6.4.0` 会装到原文那个版本，Node 要求也低一档，但 6.8.0 新增的客户端和工具都拿不到。全局安装的好处是可以用 `rea update` 升级。

原文作者建议别用 npx，理由值得保留：他 dry-run 时看到 MCP server 被注册到了 npx 的临时缓存路径上，那个目录随时可能被清掉，注册就废了。官方 README 现在的快速开始是用 `npx rea-agents@latest setup`，跑一次看看可以，长期用还是全局装稳。

第二步先看安装计划，再执行。REA 会改你的 agent 配置，养成先看后写的习惯：

```bash
rea doctor
rea setup --client claude_code --dry-run
rea setup --client claude_code --yes
```

`rea doctor` 检查本机环境。dry run 会列出两件事：把 REA server 加进 `~/.claude.json`（备份到 `~/.claude.json.rea.backup`），以及把 skill 装到 `~/.claude/skills/reverse-engineer-anything`。`--client claude_code` 把改动限制在 Claude Code。

第三步只在需要原生分析时做。装 JDK 和 Ghidra，然后告诉 REA 它们在哪。Ghidra 从官方 releases 页下载解压包，最新稳定版是 12.2（2026 年 10 月 22 日），下面按解压到 `C:\tools` 的路径写，换成你自己的目录即可：

```bash
winget install Microsoft.OpenJDK.21
setx GHIDRA_INSTALL_DIR "C:\tools\ghidra_12.2_PUBLIC"
setx JAVA_HOME "C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot"
setx REA_ANALYSIS_PROVIDER ghidra
```

这里有个容易漏的动作：开新终端后要再跑一次 `rea setup --client claude_code --yes`。安装文档明确提醒过，只在终端里设置的环境变量不会传给 agent 拉起的 server；第二次 setup 会把 `GHIDRA_INSTALL_DIR` 和 `JAVA_HOME` 写进 MCP 注册信息，之后即使 agent 的环境里没有这些变量，REA 也能找到 Ghidra。

第四步重启 agent。MCP 工具只在会话启动时加载，不重启不会出现。之后用 `rea doctor` 和 `rea providers --json` 确认 Ghidra 被识别。

能装好不等于工具齐全，尤其在 Windows 上。原生分析官方仍标注为实验性：通过 Ghidra 的 P0 支持只开放 27 个只读操作，目标限定为 PE 文件，要求 Windows 10 以上 x64、Ghidra 12.x 和 64 位 JDK 21+，Hopper 则根本不能在 Windows 上装。作者在自己的 Windows 11 环境里只有 59 个工具可用（原文 6.4.0 共 170 个），这个数字和官方口径不是一回事，别拿来估算你能用多少。

## 一次取色操作留下哪些证据

PowerToys 的取色器由两部分组成：`PowerToys.ColorPickerUI.dll` 是 .NET 的 UI 程序集，`PowerToys.ColorPicker.dll` 是原生 C++ 模块。作者让 Claude Code 用 REA 把「点一下取色」从头到尾走一遍，每条结论都要给证据。

.NET 那一侧，`inspect_managed_native_boundaries` 列表把 UI 调用的每一个 Windows API 都列了出来。原生那一侧，REA 把 DLL 送进 Ghidra，先搜字符串，顺着交叉引用往上找，再把用到这些字符串的函数反编译出来。它还查出一件事：底层鼠标键盘钩子会把点击、Enter 和 Esc 吞掉，所以这些输入根本到不了下面的应用。

过程并不顺，三个地方值得记下来。第一次字符串搜索落进了一个日志封装函数里，实际调用启动 API 的代码在上一层调用者那里。按名字搜 `ShellExecuteExW` 会失败，因为 Ghidra 把导入命名成 `SHELL32.DLL::ShellExecuteExW` 这种形式，得按字符串或正则找。.NET 成员列表导出来有 2.7 MB，远超上下文能吃的量，最后是走 CLI 输出再用小脚本过滤。

两个动作可以固化成习惯：给 agent 的输出先想好怎么截断和过滤，符号名不要假设和源码里一样。

## 9 条结论里 8 条全对

作者拿 PowerToys 0.98.0 的源码逐条核对，结果如下：

| REA 的结论                                           | 核对结果                                 |
| ---------------------------------------------------- | ---------------------------------------- |
| UI 通过 `ShellExecuteExW` 启动，并带上模块自己的 PID | 正确                                     |
| `fMask` 为 `0x440`（NOCLOSEPROCESS 与 FLAG_NO_UI）   | 正确，值完全一致                         |
| UI 可执行文件是 `PowerToys.ColorPickerUI.exe`        | 正确                                     |
| 用命名事件显示和终止 UI                              | 正确                                     |
| 原生模块注册了热键                                   | 部分正确                                 |
| 用定时器按显示器刷新率轮询像素                       | 正确                                     |
| 像素通过 `CopyFromScreen` 和 `GetPixel` 读取         | 正确                                     |
| 剪贴板写入带 sleep 重试                              | 正确，但没给出 10 次 / 10 毫秒的具体参数 |
| 光标通过注册表和 `SPI_SETCURSORS` 替换               | 正确                                     |

核对对象固定在一个版本上，这件事本身有条件：0.98.0 是 2026 年 3 月的版本，现在 PowerToys 稳定版已经到 0.102.x，功能实现随时会动。做这类对照实验时，把被研究的版本写进笔记，否则结论没法复用。

那条「部分对」比错误更有信息量。模块确实处理热键，但注册热键的是 PowerToys runner，另一个可执行文件。REA 没看 runner，因为作者没把 runner 给它。

这条边界可以推广成一句用法：REA 的结论只覆盖你交给它的文件，给得越少，断点越靠前。想要完整答案，就把相关文件和它的启动方一起给。

## 哪些做法照搬 PowerToys，哪些必须自己定

hexgrab 是个小工具：按 Win + Shift + H，指向任意像素，点击，HEX 值进剪贴板。.NET 10 加 WPF，不用任何 NuGet 包，741 行 C#。安装、调查、第一个能跑的版本都发生在 2026 年 10 月 12 日这一天。

从 PowerToys 搬过来的两个做法都跟实际行为有关。第一个是按刷新率轮询，因为只监听鼠标移动会漏掉光标不动时的颜色变化，比如播放中的视频：

```csharp
public static int GetPrimaryRefreshRate()
{
    var mode = new DEVMODEW { dmSize = 220 };
    if (EnumDisplaySettingsW(null, ENUM_CURRENT_SETTINGS, ref mode) && mode.dmDisplayFrequency > 1)
    {
        return (int)mode.dmDisplayFrequency;
    }

    return 60;
}
```

第二个是剪贴板写入重试，最多 10 次、每次停 10 毫秒，数值和 PowerToys 一样。剪贴板是全机共享资源，另一个应用正开着它时会被锁住几毫秒。

剩下的决定只能自己做。PowerToys 有 runner、插件模块和独立的 UI 进程，因为它要承载几十个工具；hexgrab 是单应用，所以用一个 .NET 进程调 `RegisterHotKey` 并自己持有 UI。他也没抄光标替换：PowerToys 会在取色期间改系统光标方案，中途崩溃的话光标就留在改过的状态，小工具不值得承担这个风险。同样为了减少依赖，他没引入 NuGet 包，Windows API 一律用 `LibraryImport` 声明。

验证方式也是一项设计。他写了个 PowerShell 端到端脚本，开一个纯蓝色窗口，向 hexgrab 发送真实热键、点击和按键，检查六件事：点击复制 `#3366CC`、这次点击被钩子吞掉、Esc 取消、Enter 复制、取色后钩子被移除、光标不动时颜色变化仍能被捕捉。六项在 Windows 11、125% 缩放下全部通过。

## 写代码变便宜之后，什么还贵

一个取色器很小，一天的实验也不等于一个产品，但方向值得记住：理解和复现的成本在下降。原作者列的几项并没有跟着降。

设计判断是其中一项。REA 给他的是事实，砍掉 runner、把 UI 并进单进程、不动用户的光标方案，都是经验带来的选择。运维成熟度更难补：PowerToys 有安装器、自动更新、设置应用、多语言、无障碍支持和固定团队发布，hexgrab 一样都没有。成本也会拉开距离，功能相同的两个 app，云账单、数据库费用和 token 预算可以差很多。品牌和分发同样在名单上：PowerToys 来自微软、有签名、用户默认信任；hexgrab 的 exe 一运行就触发 SmartScreen 警告，因为它没签名，也没人认识这个作者。最后是选题，REA 能告诉你一个功能怎么实现，不能告诉你人们需要哪个功能。

我的判断比原文收一点。功能级重建的成本下降，最直接受益的场景是读没有源码的东西：遗留的内部程序、只有 DLL 的第三方 SDK、离职同事留下的构建产物。这类目标你本来就有权研究，省掉的是「找谁问」这一步。拿它重做一个商业竞品，法律风险通常比技术难度更早拦住你；原文的 PowerToys 例子成立，前提正是它开源。至于「代码不再是护城河」，对个人工具大致成立；对需要长期运行和信任的产品，门槛从「能不能写出来」挪到了「能不能一直跑对、让人敢装」。

## 先拿一个能对账的目标做小实验

想试的话，第一次别从 Ghidra 开始。找一个 MIT 或 Apache 许可、源码公开的小工具，装完 REA 后只给它一两个文件，问一个答案可验证的问题，比如「这个按钮点击后调用哪个 API」。拿到结论去源码里对一遍，再决定要不要为原生分析装 JDK 和 Ghidra。一次这样的小实验，时间成本远低于一上来就配齐原生分析环境，换来的是你对它在自己技术栈上准确率的直觉。

几条边界先记住。版本换代很快，别人给的数字要连着版本一起看。Windows 上的原生分析仍是实验状态，官方只开放 27 个只读操作、且只处理 PE 文件。单个命令的输出可能大到塞不进上下文，2.7 MB 那种量级要先走 CLI 再过滤。结论只覆盖你给它的文件。

下次遇到一个只有 DLL、没有源码的依赖，先问它一句，再翻源码对账。你能接受的误差范围，决定它值不值得进你的工作流。

## 参考

- [REA (Reverse Engineer Anything): What It Is, How I Used It](https://codewithmukesh.com/blog/reverse-engineer-anything-rea/)
- [morluto/rea](https://github.com/morluto/rea)
- [rea-agents on npm](https://www.npmjs.com/package/rea-agents)
- [REA installation docs](https://github.com/morluto/rea/blob/main/docs/installation.md)
- [iammukeshm/hexgrab](https://github.com/iammukeshm/hexgrab)
- [hexgrab v0.1.0 release](https://github.com/iammukeshm/hexgrab/releases/tag/v0.1.0)
- [microsoft/PowerToys](https://github.com/microsoft/PowerToys)
- [PowerToys LICENSE (MIT)](https://github.com/microsoft/PowerToys/blob/main/LICENSE)
- [Ghidra releases](https://github.com/NationalSecurityAgency/ghidra/releases)
- [star-history: morluto/rea](https://star-history.com/#morluto/rea&Date)
