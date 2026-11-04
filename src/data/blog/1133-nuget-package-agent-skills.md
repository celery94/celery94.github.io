---
pubDatetime: 2026-11-04T08:40:00+08:00
title: "NuGet 包分发 agent skill 的取用与成本"
description: "dotnet restore 会把包里的 SKILL.md 下载到全局缓存，agent 却读不到；用 dotnet-inspect 和 dotnet-package-skills 把它搬进仓库，再算清 token 成本。"
tags: ["NuGet", ".NET", "Agent Skills"]
slug: "nuget-package-agent-skills"
ogImage: "../../assets/1133/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/delivering-skills-in-nuget-packages"
---

`dotnet restore` 跑完，`~/.nuget/packages/markout/0.40.0/skills/markout/SKILL.md` 已经在磁盘上了。你的 agent 读不到它：编码助手只在当前仓库里找 skill 目录，而全局包缓存通常在仓库外面。

微软 .NET 团队的 Richard Lander 在 11 月 3 日的文章里报告了这件事的进展。skill 可以跟着 NuGet 包一起发，格式和 agentskills.io 规定的 `SKILL.md` 完全一样，restore 顺手就把它下载到本机；两个工具负责把它从缓存搬到 agent 会读的地方。文章后半段更值得看：skill 有 token 成本，写得不好会让 agent 更贵。

## 包版本永远比模型新，skill 补的是这一段

新发布的包版本永远比模型训练数据新。五分钟前推到 NuGet 上的版本，模型对它一无所知；registry 的长尾里还有大量包，模型连名字都没见过。把 skill 和二进制放进同一个包，等于每个版本都能带一份对应当前 API 的说明。

包里的 `README.md` 早就这么干了，区别在读者：README 给人看，`SKILL.md` 给 agent 看。

skill 也不必全文塞进上下文。按照 agentskills.io 的说明，agent 分三步使用 skill：启动时只加载每个 skill 的 `name` 和 `description`；任务匹配上描述，才把完整的 `SKILL.md` 读进上下文；需要时再执行附带的脚本。所以包里多一个 skill，平时只占几行元数据。这也意味着 `description` 写得含糊，skill 就一直不会被读到；写得宽泛，又会频繁误触发。

## restore 之后文件在，只是不在 agent 的搜索范围里

包里的 skill 放在 `skills/` 下面，每个 skill 一个独立子目录。restore 之后，markout 的那个落在 `~/.nuget/packages/markout/0.40.0/skills/markout/SKILL.md`。Lander 用几条命令确认这些文件确实被拉下来了：

```bash
$ cat ../../artifacts/obj/dotnet-inspect/project.assets.json | grep SKILL.md
        "skills/markout-built-in-shapes/SKILL.md",
        "skills/markout-composite-cells-cards/SKILL.md",
        "skills/markout-conditional-composition/SKILL.md",
        "skills/markout-output-formats/SKILL.md",
        "skills/markout/SKILL.md",
$ find ~/.nuget/packages/markout/0.40.0/ | grep SKILL.md
/Users/rich/.nuget/packages/markout/0.40.0/skills/markout/SKILL.md
/Users/rich/.nuget/packages/markout/0.40.0/skills/markout-built-in-shapes/SKILL.md
```

`project.assets.json` 里也列出了这些文件，所以 agent 其实能从包图里判断某个包有没有带 skill。这条路不直观，多数工具不会主动去翻。

全局包缓存是共享的，机器上所有项目用同一份 `~/.nuget/packages`，所以一个包里的 skill 物理上只需要一份。麻烦在于 agent 的搜索范围按仓库划定，它不会跑出仓库去找。这决定了后面那些工具只能做「复制」：`dotnet-package-skills` 的 README 专门解释了为什么不把文件直接挪走，因为移出全局缓存会被 NuGet 当成包损坏，还会顺带删掉其他项目正在用的那份。

## dotnet-inspect 查包里有什么

dotnet-inspect 是查包和程序集元数据的命令行工具，仓库在 richlander/dotnet-inspect，运行需要 .NET 10 SDK 或更高版本：

```bash
dotnet tool install -g dotnet-inspect
```

`-S Skills` 只挑出 skill 那一段，不让其余输出占上下文：

```bash
$ dotnet-inspect package markout -S Skills
path    size
skills/markout-built-in-shapes/SKILL.md 9457
skills/markout-composite-cells-cards/SKILL.md   6764
skills/markout-conditional-composition/SKILL.md 4978
skills/markout-output-formats/SKILL.md  7744
skills/markout/SKILL.md 8551
```

要读内容，用 `--row` 选中一行，再 `--print -12` 打出前 12 行：

```bash
dotnet-inspect package markout -S Skills --row 4 --print -12
```

它也能直接读项目文件。`dotnet-inspect project scratch.csproj -S Skills` 会输出一张 Markdown 表，每个直接依赖的 skill 占一行，列出包名、版本、路径、大小、名称和 description。agent 可以把这张表打进自己的上下文，也可以写到文件里再检索，或者提交进仓库。

## dotnet-package-skills 负责把副本放进仓库

dotnet-inspect 只读不写。要让 skill 长期留在仓库、被 agent 稳定读到，用 dotnet-package-skills。它由 NuGet 团队维护，目前在 NuGet 上只有预发布版本，安装时要加 `--prerelease`：

```bash
dotnet tool install --global dotnet-package-skills --prerelease
cd /path/to/your/repo
dotnet-package-skills install
```

默认写入 `.agents/skills/`，同时生成清单 `.dotnet-package-skills.json`，记录每个 skill 来自哪个包的哪个版本。`list` 只看不写。包升级后，同一个 `install` 会用新版本的 skill 覆盖旧文件；包彻底离开项目时，才由 `uninstall --stale` 删除对应目录。

包引用可能因为一次重构中途消失，自动清理会丢东西。所以删除始终是一条你主动跑的命令，还可以先加 `--dry-run` 看会动到什么。

skill 放在哪，各家约定还不一样。dotnet/runtime 用 `.github/skills`，dotnet-package-skills 默认 `.agents/skills`，也可以用 `--destination .claude/skills` 指到别处。

这个目录要不要提交，两种做法都有人用。提交进去，团队和 CI 不用跑任何命令就有 skill；加进 `.gitignore`，每台机器自己刷新。选一个写进贡献指南，别让下一个人来猜。

Lander 在评论区说明过，原文只讲到 skill 能随包发，agent 怎么实际加载是下一篇的内容。上面这几步是照两个工具当前的 README 补的。

## 维护者这边：skill 目录怎么命名

包里的每个 skill 必须有自己的一级子目录，工具不会去发现一个孤零零的 `skills/SKILL.md`。建议把包名小写后作为前缀：

```text
skills/contoso.widgets-widget-usage/SKILL.md
skills/contoso.widgets-widget-testing/SKILL.md
```

前缀解决的是撞名。同一台机器上，很多包的 skill 会落进同一个 `.agents/skills`，两个包都叫 `usage` 就直接冲突，工具会跳过全部冲突项并报错。

打进 nupkg 靠一条 MSBuild 项：

```xml
<ItemGroup>
  <None Include="skills/**/*"
        Pack="true"
        PackagePath="skills/%(RecursiveDir)%(Filename)%(Extension)" />
</ItemGroup>
```

## 原文那个漏洞检查 skill 在旧 SDK 上会失败

Lander 用一段漏洞检查 skill 做示例，里面让 agent 执行：

```bash
dotnet package list --vulnerable --include-transitive
```

这条命令有两个版本门槛。名词在前的写法 `dotnet package list` 是 .NET 10 引入的，.NET 9 SDK 及更早要用 `dotnet list package`。`--vulnerable` 本身要求 SDK 9.0.300 以上。照着抄之前先确认 SDK 版本，否则 agent 拿到的是一条命令不存在，或者一个无法识别的选项。

写进 skill 时把两种写法都列出来更稳：

```bash
dotnet package list --vulnerable --include-transitive  # .NET 10 SDK
dotnet list package --vulnerable --include-transitive  # .NET 9 SDK 及更早
```

写 skill 时把命令和它依赖的 SDK 版本放在一起。skill 会被丢进很多陌生的环境，读它的人不会先猜你的工具链。

## skill 让人更贵的几种情况

skill 想带来两个好处：答对（efficacy）和答得便宜（efficiency）。Lander 的团队试下来，这两件事都不保证，写得差、没测过的 skill 会同时反向。

在 frontier 模型上，他们没找到多少提升空间。模型本来就会翻 NuGet 缓存、读 README，甚至写个临时程序去反射程序集元数据，靠这种办法自己把包的用法摸出来。问题出在成本：这类探索花掉的 token 不少，月度预算有限时，不想让 agent 每次都重新探索一遍。

换到弱一些的模型，差距明显：答对的比例下降，波动也大，主要原因是模型对 skill 里写的步骤遵循度不够。

他们拿帕累托效率当纠偏工具，原则是「不要造成伤害」。原本的想法是用 skill 把中档模型拉到 frontier 水平，实测不现实：同一套 skill 要发给所有模型，给 Haiku 省 50% 的 token、却让 Opus 多花 10%，这笔交易是亏的，因为 Opus 的 token 单价高得多。所以他们的测试重心放在 frontier 模型上，只用便宜模型测 skill 被列为反模式。

对维护者来说，这条结论不太舒服。你的用户里既有 frontier 模型也有便宜模型，而 skill 只有一套。要么按 frontier 模型调，接受弱模型收益不稳；要么为弱模型写得更细，同时接受强模型那边多付的 token。

## markdown 从惰性资产变成会执行的指令

维护者往包里放 markdown 已经十几年了，那些文件一直是无害的：没人读，读了也不会照着做。agent 改变了这一点，包里的 `README.md` 和 `SKILL.md` 会被当作指令读进去，再被执行。

Lander 给消费者的建议没有变：只从你信任的维护者那里装包。`dotnet-package-skills` 的 README 说得更细：包里的 skill 是第三方写的指令，属于软件供应链的一部分，装之前像审一个依赖那样审一遍。工具本身只做复制，不解释内容。

对「包里能带 skill」这件事的谨慎态度也就说得通了。skill 能省掉 agent 反复摸索包用法的时间，也能让一个你不信任的包在你机器上获得执行上下文。

## 先看手上有没有，再决定发不发

消费侧：跑一次 `dotnet-package-skills list`，看依赖里有没有带 skill 的包。有的话再决定要不要 install，一旦进了 `.agents/skills`，agent 启动时就会把它算进候选。

维护侧：先把 `description` 写准，那是 agent 一定会读的一行；再想清楚这个 skill 替代的是哪段重复探索。在没有 eval 门槛之前，宁可先不发。一个让 agent 多花 20% token 又答不准的 skill，比不发更难被人发现。

两个工具都还在 0.x，接口和默认路径会变。本文的命令和版本门槛按 2026-11-04 的 NuGet 页面与官方文档核对。

## 参考

- [Delivering Skills in NuGet packages](https://devblogs.microsoft.com/dotnet/delivering-skills-in-nuget-packages)
- [Agent Skills 规范与说明](https://agentskills.io/home)
- [dotnet-package-skills](https://www.nuget.org/packages/dotnet-package-skills)
- [dotnet-inspect](https://www.nuget.org/packages/dotnet-inspect)
- [Markout](https://www.nuget.org/packages/Markout)
- [dotnet package list 命令文档](https://learn.microsoft.com/dotnet/core/tools/dotnet-package-list)
- [dotnet/runtime 的 `.github/skills`](https://github.com/dotnet/runtime/tree/main/.github/skills)
- [dotnet/skills marketplace](https://github.com/dotnet/skills)
