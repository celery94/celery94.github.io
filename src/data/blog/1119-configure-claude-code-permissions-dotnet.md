---
pubDatetime: 2026-10-28T07:40:00+08:00
title: "Claude Code 的 .NET 权限该怎么配"
description: "一条 Bash(dotnet *) 把构建、测试、迁移和发布配成同一层权限。按操作效果分层，用 deny→ask→allow 的顺序写出一份能讲清楚的 .NET 仓库配置。"
tags: ["Claude Code", ".NET", "Security", "AI Agents", "Permissions"]
slug: "configure-claude-code-permissions-dotnet"
ogImage: "../../assets/1119/01-cover.png"
source: "https://www.devleader.ca/2026/10/27/configure-claude-code-permissions-for-net-development"
---

一条 `Bash(dotnet *)` 写进 `.claude/settings.json`，.NET 仓库里要用的命令看起来都放行了：`dotnet build`、`dotnet test`、`dotnet run`，连 `dotnet publish` 和 `dotnet ef database update` 也顺带过门。几条命令改动的对象完全不同：构建写 `bin/` 和 `obj/`，测试执行仓库里的代码，迁移改共享数据库，发布产物还可能被部署脚本直接接走。

Claude Code 的权限规则按 deny、ask、allow 的顺序匹配，先命中的那条决定结果，规则的宽窄不改变顺序。配置 .NET 仓库时，把读取、编辑、构建、测试、迁移、发布按实际效果分成几层，再决定哪层自动放行、哪层每次询问、哪层直接拒绝，比把命令列全更可靠。几个细节要先定下来：通配符写在哪、配置放在共享还是本机、Windows 上 PowerShell 命令要不要单独写规则、模式和无头运行各自改变什么。下面这些规则以 2026 年 10 月的官方权限文档为准。

## dotnet 后面的词才是权限单位

权限项按工具区分：`Read` 读文件、`Edit` 改文件、`Bash` 执行 shell，此外还有 WebFetch、MCP 等。`dotnet` 只是程序名，决定后果的是后面的子命令。

- `dotnet build` 执行 MSBuild 目标和项目里的自定义 target，写 `bin/` 与 `obj/`。`Directory.Build.targets` 或某个 NuGet 包可以在构建阶段跑任意任务，构建不等于只读。
- `dotnet test` 加载并运行测试程序集。测试夹具可能访问真实 API、数据库或消息队列，也可能启动容器。
- `dotnet run` 启动应用，可能占端口、连数据库、写本地状态。
- `dotnet ef migrations add` 和 `dotnet ef migrations script` 生成源码或 SQL 脚本，改的是工作区文件。
- `dotnet ef database update` 把迁移应用到数据库，改的是共享状态。
- `dotnet publish` 写发布目录，后续部署通常由另一个脚本或流水线接手。

命令名干净不代表它只做一件事。仓库里一条名字普通的脚本，可能顺手执行迁移或上传产物。按资源分类更可靠：命令只碰一次性 checkout 的，可以放行；会执行仓库代码的，至少留在 ask；碰到共享基础设施、需要凭据、或者结果难以回滚的，单独授权。

## 规则按 deny、ask、allow 的顺序匹配

官方权限文档把求值顺序写得很明确：deny、ask、allow，第一个命中的决定结果，规则的具体程度不参与排序。一条宽 deny `Bash(dotnet *)` 会盖住更窄的 allow `Bash(dotnet test *)`；反过来，一条 ask `Bash(dotnet test *)` 也会让更窄的 allow 失效。审查继承来的配置时这一点最容易误判：新加的精确 allow 不生效，通常是用户设置、项目设置或托管策略里已经有一条更宽的 ask 或 deny。

下面是一份很小的示例，只演示语法：

```json
{
  "permissions": {
    "allow": ["Bash(dotnet --info)", "Bash(dotnet restore *)"],
    "ask": ["Bash(dotnet ef *)", "Bash(dotnet publish *)"],
    "deny": ["Read(./.env)"]
  }
}
```

环境查询和包还原放行；迁移与发布留在 ask；`.env` 直接拒绝读取。`dotnet test` 放在 allow 还是 ask，取决于测试项目会不会连真实服务，后文单独说。

`.env` 这条 deny 很窄。它覆盖 Claude Code 内置的文件工具、它认识的文件命令（如 `cat`、`head`、`sed`）以及重定向目标，但不阻止任意子进程按自己的方式打开文件，也不构成沙箱。要挡住整个进程的文件访问，得靠 sandbox。另外 `.claudeignore` 目前没有作用，敏感文件要写进 `Read` deny 规则。

deny 有两种写法，效果不同。`"deny": ["Bash"]` 写工具名，会把 Bash 工具从上下文里整个移除；`"deny": ["Bash(dotnet nuget push *)"]` 只拦匹配的命令，工具仍然可用。前者适合明确不需要 shell 的无头任务，后者适合仓库级基线。deny 在包括 `bypassPermissions` 在内的所有模式下都生效，allow 规则在 `bypassPermissions` 下不产生额外作用。

## 通配符要写在子命令后面

`*` 在规则里匹配任意文本，包括空格，所以 `Bash(dotnet test *)` 覆盖一组调用，`Bash(dotnet test)` 只匹配字面命令。位置也有讲究：`*` 放在子命令之后，规则的范围才是这个子命令。`Bash(dotnet *)` 把 install、restore、run、publish 全收进来，等于没有分类。

尾随 `*` 前面的空格是规则的一部分，`Bash(dotnet test *)` 同时匹配裸的 `dotnet test` 和带参数的 `dotnet test --filter X`，因为文档规定「空格加尾随星号」也匹配裸命令；`Bash(dotnet test:*)` 是等价的另一种写法，`:*` 只认末尾。换成 `Bash(dotnet test*)` 就没有这条空格约束，`dotnet testing` 这类前缀也会落进规则。

组合命令会被拆开检查。`dotnet build && dotnet publish` 里每个子命令都要通过自己的规则：发布那段没有对应规则时，整条命令不会静默执行，命中 ask 会弹出确认，命中 deny 则直接失败；`;`、`|`、`||` 同理。PowerShell 走另一套解析：读 PowerShell AST，按 `|`、`;`、`&&`、`||` 拆分，再把常用别名规范化，所以 `PowerShell(Get-ChildItem *)` 也匹配 `gci`、`ls`、`dir`，匹配本身不区分大小写。

规则匹配的是命令文本，命令换一种写法就不一定命中。`dotnet` 换成完整路径、外面包一层 `cmd /c` 或 `sh -c`，同一条规则就可能漏掉。文档自己也提醒，Bash 规则只覆盖 Claude 通常写出的调用形式，不能当成程序级沙箱；需要 OS 级别的约束时用 sandbox，两者是互补的层。开了 sandbox 并保留默认的 `autoAllowBashIfSandboxed` 时，即使写了裸 `Bash` 的 ask 规则，沙箱内的 shell 命令也不再弹窗，规则和 OS 层边界要一起看。

## 共享配置和本机配置分两个文件

`.claude/settings.json` 提交进仓库，代表团队基线；`.claude/settings.local.json` 放本机调整，不提交；用户设置 `~/.claude/settings.json` 跨项目生效。优先级从高到低是托管设置、命令行参数、项目本地、共享项目、用户设置，托管设置没有任何一层能覆盖。两个开发者行为不一致时，先比对解析后的规则，而不是只看仓库里那个文件。

`/permissions` 面板会列出每条规则和它来自哪个 `settings.json`。碰到「明明加了 allow 却还弹窗」，先在这里看是不是有更宽的 ask 或 deny 生效，再决定改哪一层。`claude doctor` 适合先确认配置能被解析、安装是否正常。

还有一种规则不是手写的。在 Bash 或 WebFetch 的弹窗里选「Yes, and don't ask again」之后，Claude Code 会把这条批准写进 `.claude/settings.local.json`，按仓库和命令永久生效；文件编辑的批准只持续到会话结束。Windows 上这个 local 文件留在 `.claude/settings.json` 旁边，而不是 git 仓库根目录，两个开发者看到的 local 规则位置可能不同。

工作区信任是另一道门。项目 `.claude/settings.json` 里的 `permissions.allow` 和 `additionalDirectories` 要等你接受该目录的信任对话框之后才生效，deny 和 ask 不受影响，因为它们只收紧权限。无头运行和 SDK 会话不会出现这个对话框，项目 allow 规则不会被采用，stderr 会留一条 workspace 未被信任的提示。这也是后文强调无头运行前先审查仓库配置的原因。

## acceptEdits 不会替你批准 dotnet test

权限模式决定什么时候询问，不改变命令的后果。当前文档列出这几种：

| 模式                | 对 .NET 任务意味着什么                                                                             |
| ------------------- | -------------------------------------------------------------------------------------------------- |
| `default`（Manual） | 每个工具第一次使用时询问，`dotnet` 命令按规则走                                                    |
| `acceptEdits`       | 自动接受文件编辑和 `mkdir`、`touch`、`mv`、`cp` 这类工作目录内的文件操作，shell 命令仍按原规则询问 |
| `plan`              | 读文件和只读 shell 用于探索，不编辑源码；启用 auto 模式时，分类器批准的命令也会运行                |
| `auto`              | 由后台分类器判断 shell 命令和网络请求是否符合你的请求                                              |
| `dontAsk`           | 把本该询问的调用直接拒绝，只放行无需批准的操作和已批准的工具                                       |
| `bypassPermissions` | 跳过常规权限提示，只该用在容器或 VM 这类隔离环境                                                   |

如果目的是让每一步都能看清，用 `default` 并只放行少量命令，比把所有 dotnet 命令塞进 allow 更容易审查。`acceptEdits` 适合连续改文件的场景，但它不批准 shell 命令，`dotnet test` 该问还是会问。`dontAsk` 的行为是「拒绝而不是卡住」，把它用在脚本里之前，先确认任务缺哪些权限。

当前版本的默认模式值得单独留意：交互式终端和 VS Code 会话从 v2.1.283 起默认进入 auto，`claude -p` 和 SDK 在未指定模式时从 Manual 开始。想复现「每一步都问」，不要依赖版本默认值，显式传 `--permission-mode default`，或在设置文件顶层写 `"defaultMode": "default"`。另外，项目设置和本机设置里的 `defaultMode` 只能设成 `default`、`acceptEdits`、`plan` 这类值，`auto` 和 `bypassPermissions` 会被静默忽略，要从用户设置、托管设置或命令行指定。

模式也不改变内置只读命令的待遇：`ls`、`cat`、`grep`、`find`、只读形式的 `git` 等命令在任何模式下通常都不弹窗，少数情况例外，比如 Windows 上参数里带 UNC 路径的命令。`dotnet --info` 不在这个集合里，仍然需要 allow 规则。

## 无头运行读仓库配置，却不弹信任对话框

`claude -p` 和 SDK 会话不显示工作区信任对话框，项目里的 hooks 和 `.mcp.json` 服务器照常加载，即使这个目录从未被信任。交互式会话里「先审查再批准服务器」的步骤在这里不存在。把仓库配置当成可执行输入来审查，而不是当成注释。`-p` 在未指定模式时从 Manual 开始，每条命令仍按当时的规则判断。

几个能收窄边界的参数：

- `--setting-sources user`：不读项目设置文件和 `.mcp.json`，只保留用户设置。
- `--settings '{"disableAllHooks": true}'`：本次运行关掉 hooks。只在用户设置里写不够，因为项目设置的优先级更高。
- `--bare`：跳过 hooks、skills、自定义命令、subagents、plugins、`.mcp.json` 服务器、memory 和 `CLAUDE.md` 的自动发现，认证要求也不同（不读订阅登录和系统钥匙串，需要显式提供 API key）；代价是上下文要自己提供。
- `--allowedTools 'Read'`：本次会话只为 Read 预先放行；无头环境里，其他需要批准的工具拿不到确认。

示例（未执行，只示意参数组合）：

```powershell
claude --bare -p 'Summarize the public API in C:\work\Shipping\src\Shipping.Domain. Do not edit files or run commands.' --allowedTools 'Read'
```

自然语言里的「不要改文件」不构成强制约束，真正起作用的是 `--allowedTools` 和当时的权限规则。`--allowedTools` 也不能覆盖托管设置里的 deny。

无头运行最容易被忽略的是环境本身。runner 上有数据库连接串、部署令牌、发布凭据，权限配得再细也拦不住一个被允许的 `dotnet ef database update`。把生产凭据从开发 runner 上移走，比在规则里叠字符串更可靠。

## 迁移和发布各自需要一次授权

EF Core 的迁移分两步：`dotnet ef migrations add` 生成迁移文件，改的是源码；`dotnet ef database update` 把迁移应用到数据库，改的是共享状态。批准前者不等于批准后者，两者的执行身份也可以不同。生成脚本、在评审环境应用、再由发布流程应用到生产，是三种权限。

发布同理。`dotnet publish` 只产出目录，部署是下一个动作。预览环境部署和生产发布的目标、版本、授权人都应该写清楚。模型说任务完成，不代表有人批准了发布。

MCP 是第三条授权通道。一个叫 `get_report` 的工具可能带着凭据调用业务代码；客户端权限只约束调用，服务端的认证和授权仍然要自己做。MCP 工具规则按 `mcp__服务器__工具` 命名，`mcp__*` 可以整组 deny，allow 通配只支持写在具体的服务器前缀之后。

## 被拒绝时先定位拦在哪一层

命令被拒绝，先看实际发出的工具调用，而不是猜规则写错了：

1. 工具名对不对。规则写的是 `Bash(dotnet build *)`，这次调用如果来自 PowerShell 工具就不会命中；Windows 上两种 shell 都可能出现，要给 PowerShell 单独写规则。
2. 命令文本对不对。精确规则遇到不同参数就不匹配，`*` 的位置和空格都会影响结果。
3. 有没有更宽的 ask 或 deny。用户设置、项目设置、托管策略都可能先命中，`/permissions` 会显示来源。
4. 工作区信任是否已接受。项目 allow 规则在未信任时被忽略，只在 stderr 留一条警告。
5. 托管策略是否禁止。托管设置的 deny 不能被项目设置或命令行覆盖。

`claude doctor` 用来检查安装和解析后的配置，`/permissions` 用来看规则和来源。定位之后只改那条出问题的边界：缺一个 `dotnet test` 就加一条窄的 allow，或者把测试留在 ask；不要因为一次测试被拦，就把 build、包管理、数据库、发布全部放行。拒绝本身是信息，说明任务碰到了当前边界之外的动作。

## 一份可以起步的 .NET 配置

前置条件：Claude Code 已安装并能在仓库根目录启动；仓库有自己的 `.claude/` 目录；配置文件里不放任何凭据。下面这份是语法示例，没有在具体项目里逐条执行过，先在测试仓库里验证再合并：

在仓库根目录创建 `.claude/settings.json`：

```json
{
  "permissions": {
    "allow": [
      "Bash(dotnet --info)",
      "Bash(dotnet restore *)",
      "Bash(dotnet build *)",
      "Bash(dotnet test *)",
      "PowerShell(dotnet --info)",
      "PowerShell(dotnet restore *)",
      "PowerShell(dotnet build *)",
      "PowerShell(dotnet test *)"
    ],
    "ask": [
      "Bash(dotnet run *)",
      "Bash(dotnet ef *)",
      "Bash(dotnet publish *)",
      "Bash(dotnet nuget push *)",
      "PowerShell(dotnet run *)",
      "PowerShell(dotnet ef *)",
      "PowerShell(dotnet publish *)",
      "PowerShell(dotnet nuget push *)"
    ],
    "deny": ["Read(./.env)", "Read(./**/*.pfx)", "Read(./secrets/**)"]
  }
}
```

这里把 restore、build、test 放进 allow，前提是仓库和本机环境可信、测试不依赖真实生产服务。如果测试夹具会连共享数据库或外部 API，把 `dotnet test` 移回 ask。run、ef、publish、nuget push 都需要单独判断：运行应用会占端口、碰数据库，迁移和发布会改共享状态。

保存后按顺序验证：

1. 在 Claude Code 里输入 `/permissions`，确认每一条都在列表里，来源是 `.claude/settings.json`。
2. 让 Claude 运行 `dotnet --info`，预期直接执行，不弹窗。
3. 让 Claude 运行 `dotnet build` 和 `dotnet test`，预期直接执行；如果仍然询问，先确认这次调用来自 Bash 还是 PowerShell，再看规则来源。
4. 让 Claude 运行 `dotnet ef database update --help`，预期弹出确认，因为命中了 `Bash(dotnet ef *)` 或 `PowerShell(dotnet ef *)`。
5. 让 Claude 读取 `.env`，预期被拒绝，提示来自 `Read` deny 规则。
6. 改动 JSON 后运行 `claude doctor`，确认配置仍能解析。

常见问题大多出在文件本身和规则写法上。JSON 不支持注释和尾逗号，写错一处整份配置都可能解析失败，启动时的 invalid settings 提示或 `claude doctor` 会指出来。规则写了 `Bash` 而实际调用走 PowerShell，命令会照旧弹窗。项目 allow 规则没生效，先检查工作区信任。

还有几处边界容易误判。想让 `Read(./.env)` 挡住脚本自己打开文件，做不到，需要 sandbox 或把凭据从环境里移除。路径规则用 gitignore 语法，Windows 路径会先归一化成 POSIX 形式，`C:\Users\alice` 对应 `/c/Users/alice`，绝对路径要写成 `//c/...`；写 `Write(...)` 的路径规则永远不会匹配，改文件用 `Edit(...)`。

## 先整理出最近一周跑过的 dotnet 命令

从仓库里实际跑过的命令开始，比抄一份别人的 allow 列表可靠。把最近一周用到的命令列出来，按「只碰工作区」「会执行仓库代码」「会碰共享状态」分三堆：第一堆放 allow，第二堆留在 ask 或按条件放行，第三堆单独授权，凭据留在另一个执行身份里。然后把这份表写进 `.claude/settings.json`，在 `/permissions` 里过一遍来源，再用 `dotnet --info`、`dotnet build`、`dotnet ef database update --help`、读 `.env` 四种动作验证边界。

一份好的权限表能回答三个问题：这条命令为什么被放行、它会碰到哪个环境、谁批准了它。答不上来的规则，先放回 ask。

## 参考

- [Configure Claude Code Permissions for .NET Development](https://www.devleader.ca/2026/10/27/configure-claude-code-permissions-for-net-development)
- [Claude Code permissions](https://code.claude.com/docs/en/permissions)
- [Permission modes](https://code.claude.com/docs/en/permission-modes)
- [Settings files and precedence](https://code.claude.com/docs/en/settings)
- [Headless mode](https://code.claude.com/docs/en/headless)
- [Bash sandbox](https://code.claude.com/docs/en/sandboxing)
