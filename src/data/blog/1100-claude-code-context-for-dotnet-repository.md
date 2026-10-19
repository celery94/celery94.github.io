---
pubDatetime: 2026-10-19T08:18:00+08:00
title: "给 Claude Code 写对 .NET 仓库上下文"
description: "Claude Code 在 .NET 仓库里猜结构、乱加包版本、声称跑过测试？本文按官方文档核对加载规则，给出根 CLAUDE.md、按路径规则、AGENTS.md 与验证边界的可执行配置。"
tags: ["Claude Code", "CLAUDE.md", "AGENTS.md", ".NET", "AI Coding"]
slug: "claude-code-context-for-dotnet-repository"
ogImage: "../../assets/1100/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/17/give-claude-code-the-right-context-for-your-net-repository"
---

审查一个 agent 交上来的改动时，你发现它在 `csproj` 里加了一行带 `Version` 的 `PackageReference`。你的仓库用中央包管理，版本只写在 `Directory.Packages.props` 里，这一行现在和它打架。它没有恶意，只是照着熟悉的教程补了一个看起来正确的默认值。

这类补全不是模型能力问题，而是上下文问题。Nick Cosentino 在 Dev Leader 的这篇文章里给出一句很好用的判据：仓库上下文应该说明「什么是异常的、重要的、容易搞错的」，而不是复述仓库里每个文件，也不是规定一套应用根本没用的通用架构。

原文还标注了自己的边界：信息核对于 2026 年 10 月 9 日，加载与记忆行为对照过官方文档，但示例文件和命令没有实际执行。我在下面复述的同时，按当前官方文档核对了加载规则，并补上了原文没提的几个配置项。**版本号和产品行为都会变，看到这里时先跑一次 `/context` 确认。**

## 上下文不是护栏

官方 memory 文档把 CLAUDE.md 和自动记忆明确称作「上下文机制」，不是强制配置。文档还说得很具体：CLAUDE.md 的内容是在系统提示之后作为一条用户消息送进去的，模型会读、会尽量遵守，但没有严格合规的保证。

所以「不要执行数据库迁移」写在 CLAUDE.md 里，效果是影响 agent 想做什么；真正拦住动作的是另外两个东西：

- **PreToolUse hook**：无论模型怎么决定，工具调用前按你的规则拦下来。
- **权限规则**：settings 里的 `allow` / `ask` / `deny`，语法是 `Tool` 或 `Tool(specifier)`，例如 `Read(./.env)`、`Bash(dotnet ef database update)`。

把这三件事分开，才不会把一份 Markdown 描述成它提供不了的安全边界。同理，写「测试命令是 `dotnet test`」不等于这条命令被执行过。

上下文也不是证据。项目目标框架、SDK 版本、包版本都会变，写死在指令里的数字迟早过期。更好的写法是让 agent 去查：

```markdown
选 .NET API 前，先读 global.json 与受影响项目的 \*.csproj。
```

这句话能撑过一次框架升级，而散落在几份文档里的 `net8.0` 撑不过去。

## 先写清解决方案的真实形状

一个 .NET 仓库通常有多个应用、共享库、测试项目、构建脚本和中央配置文件。上下文的第一步是讲清它们的关系，不是给一套通用模板。

先确定入口：`.sln`、`.slnx`，还是仓库脚本。注意 `.slnx` 需要较新工具链——`.NET SDK 9.0.200` 起 CLI 才支持，Visual Studio 17.14 起该格式稳定可用；如果你的 CI 或同事的 IDE 还停留在旧版本，把这一点写进上下文，比让 agent 猜更有用。

然后确定版本归属，这是最容易出错的地方，因为四类文件回答四个不同问题：

| 文件                               | 回答什么问题               |
| ---------------------------------- | -------------------------- |
| `global.json`                      | 用哪个 SDK 版本            |
| `*.csproj` 的 `TargetFramework(s)` | 这个项目编译到哪个框架     |
| `Directory.Build.props`            | 全仓库共享的构建属性       |
| `Directory.Packages.props`         | 包版本（开启中央包管理时） |

在中央包管理下，`PackageReference` 不带 `Version` 是**正确**的写法。agent 如果不看这一点，就会为了「让示例完整」补一个冲突版本。所以指令要写成「改包引用前先读 `Directory.Packages.props`」，而不是把当前所有包版本抄进 CLAUDE.md——复制维护中的清单必然漂移。

还要区分 host 项目和共享库：两者的依赖方向与初始化责任不同。把 API 项目的启动配置要求套到工具库上，是最常见的无效指令。

## 一份可以改着用的根 CLAUDE.md

官方建议单个 CLAUDE.md 控制在 200 行以内（这是编辑建议，不是「199 行就能被完美遵守」的保证）。下面的例子是虚构的，文件名和路径必须换成你自己仓库的：

```markdown
# 仓库说明

## 地图

- 解决方案入口：OrderService.slnx
- 选 .NET API 前先读：global.json、受影响项目的 csproj 文件
- 改包引用前先读：Directory.Packages.props（中央包管理，版本只在这一处）
- API 代码：src/OrderService.Api
- HTTP 契约测试：tests/OrderService.Api.IntegrationTests

## 变更边界

- 保留现有鉴权、租户过滤与响应契约。
- 跟随相邻 endpoint 与测试的写法，不新造目录结构。
- 未经确认，不改包版本、数据库 schema、部署配置。
- 这些说明与仓库文件冲突时，报告冲突，不要自行选一个继续。

## 验证

- 构建与测试只在团队约定的验证环境执行。
- 汇报必须包含：commit、执行的命令、结果、以及没有覆盖的部分。
- 未实际执行的命令和示例，不得写成「已通过」。
```

这段的关键不是措辞漂亮，而是内容分成了两类：

- **稳定的契约**：「保留租户过滤」不会因为升级而失效。
- **易变的事实**：「当前 API 包版本是 X」明天就可能过期，所以只写「去哪读」。

`./CLAUDE.md` 和 `./.claude/CLAUDE.md` 两种位置都可以。个人偏好放 `CLAUDE.local.md`，记得加进 `.gitignore`。

## 加载到底发生了什么

这一节的细节决定了你写的指令会不会真的出现，原文核对得比较细，当前文档也一致：

- **启动时加载**：工作目录及所有祖先目录的 `CLAUDE.md` 和 `CLAUDE.local.md`。
- **拼接而不是覆盖**：所有被发现的文件依次拼进上下文，顺序从文件系统根目录到工作目录；同一目录内 `CLAUDE.local.md` 追加在 `CLAUDE.md` 之后。
- **子目录按需加载**：工作目录之下的 CLAUDE.md 不在启动时加载，而是等 agent 读、写或编辑该子目录里的文件时才加载（用 `cat`、`head` 这类命令读单个文件也算读）。

「拼接」这条最容易误解。嵌套文件不会因为离被编辑的文件更近就抹掉父级指令，互相矛盾的指令会同时存在于上下文里，文档也提醒 Claude 可能不一致地遵守它们。所以「最近的覆盖父级」这个假设不成立，冲突需要人工消除。

工作目录会同时影响发现范围和启动上下文：在测试项目里启动，能看到祖先目录的指令，但可能拿不到兄弟应用的信息。**从你希望 agent 理解的那个仓库边界启动，并在任务里点名涉及的区域。**

想确认到底加载了什么，用 `/context` 看 `Memory files` 列表。它是加载检查，不是遵守证明：文件名出现只说明内容可用，改动是否尊重了它，得看 diff。

仓库很大时还有几个不常被提到的开关：

- `claudeMdExcludes`：按路径或 glob 排除不该加载的 CLAUDE.md 和 rules，适合 monorepo 里别的团队的指令被误拾取的场景。
- 单文件上限 4 MiB，超过直接跳过；超过 200 行会在启动和 `/status` 里给警告。
- `@path` import 会在启动时展开（最多四跳），所以 import 只改善组织方式，**不减少上下文成本**。写在反引号里的 `@README` 不会被当成 import。
- 块级 HTML 注释（`<!-- ... -->`）在注入前会被剥离，可以拿来写维护备注；代码块内的注释保留。
- 用 `--add-dir` 加进来的目录，默认**不**加载它的 CLAUDE.md，需要设 `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`。

## AGENTS.md 今天怎么处理

很多仓库已经有 `AGENTS.md` 作为共享指令源。当前文档的规则比旧教程复杂，值得具体写清楚：

- **直读需要版本**：Claude Code 直接读 AGENTS.md 需要 v2.1.277 或更新版本。
- **默认被遮蔽**：默认情况下，只有在工作目录及其以上任何一层都没有 `CLAUDE.md`、`.claude/CLAUDE.md` 或 `CLAUDE.local.md` 时，才会读 AGENTS.md。
- **不算遮蔽的**：`~/.claude/CLAUDE.md`、组织下发的 managed CLAUDE.md、`.claude/rules/` 里的文件，都不影响 AGENTS.md 的加载。
- **`CLAUDE.local.md` 算遮蔽**：很多人为了存个人笔记建了这个文件，结果 AGENTS.md 不再被读。解法是把 `/config` 里的 Project instructions 改成 `claude-md-and-agents-md`。

Project instructions 的四个取值：`claude-md-or-agents-md`（默认）、`claude-md-and-agents-md`（两份都读，同目录内 CLAUDE.md 在前）、`claude-md`（只读 CLAUDE.md）、`managed-only`（只读组织下发的指令）。也可以写进 settings：

```json
{
  "pluginConfigs": {
    "cc-plugin-agents-md@builtin": {
      "options": { "instructionFiles": "claude-md-and-agents-md" }
    }
  }
}
```

注意插件标识本身也版本敏感：v2.1.285 起是 `cc-plugin-agents-md@builtin`，更早的版本是 `agents-md@builtin`。这类细节正是为什么「检查当前文档，再看会话里实际加载了什么」比抄一份配置更可靠。

当会话读不到 AGENTS.md 时（版本太旧、插件被关掉、或者是在 v2.1.281 之前跑在 Bedrock 上或关了遥测的会话），用 import：

```markdown
@AGENTS.md

## Claude 专用说明

沿用仓库现有的测试夹具，不要另建一套 harness。
```

import 和「在文字里请 agent 读 AGENTS.md」是两回事：import 在加载阶段就展开进上下文，而文字请求只是让内容「可获取」，agent 可能并不打开它。

取舍在于兼容性与重复：一行 import 能照顾旧会话，但两份独立维护的策略文件会漂移、会互相矛盾。仓库已经有唯一来源时，优先保留那一份。

Windows 上不要用 symlink 来省掉这行 import：创建符号链接需要管理员权限或开发者模式，而且没开 `core.symlinks` 的 Git 检出会把符号链接变成纯文本文件，clone 下来的是一个只有一行内容的假 CLAUDE.md。

## 把规则收窄到该管的代码

`.claude/rules/*.md` 是比根文件更适合放局部约定的位置。没有 `paths` 的规则随会话加载（优先级同 `.claude/CLAUDE.md`），带 `paths` 的规则只在 agent 用 Read/Write/Edit 访问匹配文件时加载。下面是一条针对 API 代码的示例：

```markdown
---
paths:
  - "src/OrderService.Api/**/*.cs"
---

# Endpoint 契约

- 保留 route group 的鉴权与租户范围。
- 错误响应沿用现有格式。
- 改验证默认值前，先检查 query 绑定。
- 可观察行为变化时，同步更新对应的 HTTP 契约测试。
```

`paths` 用的是 Claude 规则的 glob，不是 Windows shell 的通配；`{ts,tsx}` 这类花括号展开有预算上限，`[` 会被当成括号表达式（要匹配字面的方括号得转义）。规则文件里只有 `paths` 会被读取，其他 frontmatter 字段直接忽略。

两条边界要记住：

- 收窄规则能减少无关上下文，但**不能**藏全局约束。像「禁止写生产库」这种必须每会话生效的限制，属于根文件加权限规则，不属于某条 path-scoped rule。
- 复杂流程（多步发布、回归脚本）放 skill，不要塞进每条规则里。规则负责说明本地约定，执行边界交给运行时配置。

## 测试按它证明什么来描述

「用 xUnit」几乎不携带信息。一个解决方案里可以同时有隔离单元测试、组件测试、走真实 HTTP 的接口测试和浏览器测试，它们都用同一个测试框架，但证明的东西完全不同。

所以要指向代表性测试，而不是框架名。改 endpoint 校验时，应该看发真实请求穿过应用的测试，而不是只调用辅助方法的单元测试；纯计算逻辑则不需要完整的 HTTP 夹具。

执行约束要明确写出来。如果验证在远程环境跑，指令里就要说清证据从哪来、交接必须包含什么。否则 agent 很容易把「跑测试」悄悄改写成「在报告里写一条看起来合理的测试命令」。

失败路径的描述尤其值钱：拒绝输入、故障、取消这三类，需要不同的断言。一句「补充覆盖率」传达不了这些契约。

## 任务细节留在任务里

稳定的指令不该堆积每个 issue 的验收标准。一次性的 endpoint 修改放进 prompt 或任务说明里，写清输入边界和不能变的行为，例如：

- `pageSize=0` 必须返回现有的 400，而不是新造一个错误格式；
- 省略该参数时沿用现有默认值；
- 被拒绝的输入不产生数据库查询。

这些细节现在有用，但不属于未来每个关于这个仓库的会话。

同时要求 agent 在动手前暴露不确定性。如果两个测试暗示了不同的默认值，答案应该点出这个矛盾，而不是静默选一个；如果实现任务需要一个没被批准的依赖，它应该停在那条边界上说明原因。

上下文最有效的时刻，是产出可审查：受影响文件集合、从请求输入到服务层的调用链、验收标准与测试的对应关系。这些都是审查者能直接质疑的具体产物，比一段自信的总结有用得多。

## 自动记忆不是团队策略

自动记忆是 Claude 自己写的笔记，存在机器本地：`~/.claude/projects/<project>/memory/`，里面一个 `MEMORY.md` 索引加若干主题文件；同一个 git 仓库的所有 worktree 共享同一份目录。

启动时只读 `MEMORY.md` 的前 200 行或 25KB，先到哪条算哪条。主题文件按需读取，所以埋在索引之外的一条记忆，不能假定每次会话都在场。

它能保存偏好和纠正，但团队策略需要明确的负责人和评审路径。重要约束不应该取决于某位同事的机器恰好攒下过一条笔记。

对过期笔记也要同样警惕：如果记忆说测试需要某个服务，而维护中的夹具已经换成了另一个，去读夹具，然后改笔记——不要为了让代码符合过时上下文而动能跑的代码。

## 出问题时先查什么

| 症状                          | 先查什么                                                                                                                                             |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| CLAUDE.md 好像没生效          | `/context` 的 Memory files 列表；文件是否在子目录（按需加载）；指令是否太泛；多份文件之间是否冲突                                                    |
| AGENTS.md 没被读取            | 工作目录及以上是否有 CLAUDE.md、`.claude/CLAUDE.md` 或 `CLAUDE.local.md`；`claude --version` 是否 ≥ v2.1.277；`/config` 的 Project instructions 取值 |
| 怀疑有冲突或过时指令          | `/doctor prompt-audit`（需要 v2.1.283 及以上），它会给出建议修改，不会自动改你的文件                                                                 |
| monorepo 里被别的团队指令干扰 | `claudeMdExcludes`                                                                                                                                   |
| 想知道规则何时、为何加载      | `InstructionsLoaded` hook，可以记录加载时间和原因                                                                                                    |

`/memory` 用来浏览和编辑记忆文件，`/context` 用来确认这次会话加载了什么。两个命令别混用：一个管内容，一个管加载。

## 常见问题

**CLAUDE.md 要把整个架构写进去吗？** 不要。保留简洁的仓库地图和稳定约束，其余用 import 或链接指向已维护的文档。把所有细节复制一遍，只会让过期内容更多。

**离得最近的指令文件会覆盖父级吗？** 当前文档描述的是拼接，不是覆盖。更靠后的内容读得更晚，但冲突指令同时存在，需要人来解决，而不是假设「就近优先」。

**Claude Code 会自动读 AGENTS.md 吗？** 在文档条件下会，取决于版本、插件状态，以及工作目录及以上是否存在 Claude 指令文件。用 `/context` 或 `/memory` 看实际结果，不要靠猜。

**path-scoped 规则算权限控制吗？** 不算。它只在匹配文件被访问时提供上下文。运行时权限、受限凭据和执行边界是另外的机制。

**.NET 仓库最有用的上下文是什么？** 真实的解决方案地图、版本归属、包管理约定、代表性测试，以及必须保留的契约。有用的上下文指向证据，不发明一套标准布局。

**.slnx 能直接用吗？** 需要 `.NET SDK 9.0.200` 及以上，Visual Studio 用 17.14 及以上更稳。旧工具链只能读 `.sln`，这种情况下让上下文明确写「不要假设 .slnx 存在」。

## 收尾

如果只想在半小时内改善现状，按这个顺序做：

1. 写一份不超过 200 行的根 CLAUDE.md，只放仓库地图、稳定契约和验证政策，所有易变事实改成「去哪读」。
2. 加一到两条 path-scoped rule，把 endpoint 契约和测试约定收窄到对应目录。
3. 把「必须拦住」的事情从 CLAUDE.md 搬到权限规则或 PreToolUse hook。
4. 在任务里写清验收标准，并要求 agent 报告命令、结果和未覆盖范围。

上下文写对之后，收益不是「agent 更自信」，而是**它的产出更容易被审查**：你能看出它读了什么、假设了什么、跳过了什么。这才是可用的证据。

如果你也在把 AI 编程工具接进 .NET 仓库，欢迎关注 Aide Hub。我们会继续分享 Claude Code、Copilot 这类工具在真实工程约束下的实际用法。

## 参考

- [Give Claude Code the Right Context for Your .NET Repository（原文，Nick Cosentino / Dev Leader）](https://www.devleader.ca/2026/10/17/give-claude-code-the-right-context-for-your-net-repository)
- [How Claude remembers your project（官方 memory 文档，CLAUDE.md / rules / AGENTS.md / auto memory）](https://code.claude.com/docs/en/memory)
- [Configure permissions（官方权限文档，allow / ask / deny 与规则语法）](https://code.claude.com/docs/en/permissions)
- [Introducing support for SLNX, a new, simpler solution file format in the .NET CLI（.slnx 支持从 SDK 9.0.200 开始）](https://devblogs.microsoft.com/dotnet/introducing-slnx-support-dotnet-cli/)
