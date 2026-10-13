---
pubDatetime: 2026-10-13T07:58:00+08:00
title: "任何编码 Agent 都适用的可复核工作流"
description: "把仓库任务交给编码 agent 后，怎么判断它说的「已完成」是真的？本文拆解环境、权限、契约、证据四道关口，并对比 Claude Code、Codex 与 Copilot 的实现。"
tags: ["AI 编程", "Claude Code", "Codex", "GitHub Copilot", "软件工程"]
slug: "reviewable-repository-workflow-any-agent"
ogImage: "../../assets/1093/01-cover.jpg"
source: "https://www.devleader.ca/2026/10/12/claude-code-for-net-developers-a-reviewable-repository-workflow"
---

`pageSize` 参数需要加一条校验：小于 1 或大于 100 的请求直接拒绝，不要转发给查询服务。你把这个任务交给终端里的编码 agent，它读了 handler、改了验证逻辑、补了测试，最后回一句「已完成，测试通过」。

这句话里藏着四个未经证实的主张：它在哪个环境里跑的、它有权改哪些文件、它实现的是不是你要的行为、那条通过的测试到底测了什么。Dev Leader 的 Nick Cosentino 在 2026 年 10 月写的 [Claude Code for .NET Developers](https://www.devleader.ca/2026/10/12/claude-code-for-net-developers-a-reviewable-repository-workflow) 把这类任务拆成一条可复核的循环：先确定环境，再定位代码，写清契约，授出有限权限，最后检查证据。原文以 Claude Code 和 .NET 为例，但循环里的每一步都不是某个产品的特性。

本文按同样的思路重新组织，并把它扩展到任意编码 agent：Claude Code、OpenAI Codex、GitHub Copilot 在这一层的差别是配置方式和默认值，不是工作流本身。四道关口走完，文末附一张按关口排的对照表。

## 一句话的核心结论

**Agent 的能力不等于证据。** 它能读仓库，不代表它找到了全部约束；它能改 handler，不代表调用方还兼容；它能跑测试命令，不代表那条回归被测到了。可复核的工作流，就是让 agent 把这些区别分别报告出来，而不是压成一句 done。

判断标准只有一条：**当 agent 说完成了，你能不能指出每一条结论对应的可复查事实。** 能，就可以合并；不能，就要补一次取证，而不是再问它一句「你确定吗」。

## 关口一：先确定谁在执行

一个 .NET 解决方案里可能同时有 Windows 编辑器、终端、WSL 和远程 CI。Agent 实际执行命令的那个环境，决定了它能用哪些可执行文件和沙箱，**不要从 IDE 里选中的 SDK 反推 agent 的 SDK**。

Claude Code 官方的[沙箱文档](https://code.claude.com/docs/en/sandboxing)说得很直接：沙箱在 macOS、Linux 和 WSL2 上生效，**在原生 Windows 上命令不受沙箱保护**，想在 Windows 机器上用沙箱就得在 WSL2 里运行。OpenAI Codex 走的是另一条路，[Windows 支持原生沙箱实现](https://learn.chatgpt.com/docs/agent-approvals-security)（MXC，以及作为回退的 elevated / unelevated），不再必须依赖 WSL，但 WSL1 自 0.115 版本起已不再支持。两者都是产品边界，你需要的动作是**确认自己落在哪一边**，而不是照着别人的教程改自己仓库的操作系统要求。

接管任务前，先在目标检出目录里收集一份最小基线：

```powershell
Set-Location 'C:\repos\OrderService'
git status --short
Get-Command dotnet
dotnet --info
```

这三条命令各自回答不同的问题：git status 说明当前有哪些未提交改动，Get-Command 说明这个 shell 实际解析到哪个可执行文件，dotnet --info 记录运行时与 SDK 版本。它们都不能证明项目能编译，也不能证明集成依赖可用，那要靠构建和测试，属于后面的关口。

**保留别人未提交的改动。** 如果同事正在改一个响应模型，agent 不能把这份工作当成噪音清理掉。用单独的 worktree 隔离新改动是可以的，但基线仍然重要：被审查的提交和文件，必须和做验证的环境对得上。

顺带一个容易踩的坑：官方文档里的 VS Code 扩展和 JetBrains 插件是两个确切的集成；**Visual Studio 不等于 VS Code**。在 Visual Studio 旁边开一个终端，并不能得到一个 Visual Studio 原生扩展。

## 关口二：让仓库先把上下文说清楚

仓库上下文干两件事：给出稳定约束，帮 agent 找到对的证据。对 .NET 来说，有用的信息包括解决方案入口、目标框架、SDK 选择文件、中央包管理文件、测试项目，以及 endpoint 契约放在哪里。

好消息是这一层正在收敛到 `AGENTS.md`。Claude Code 的[记忆文档](https://code.claude.com/docs/en/memory)现在明确支持它：默认情况下，当工作目录及其上层目录里没有 `CLAUDE.md`、`.claude/CLAUDE.md` 或 `CLAUDE.local.md` 时，它直接读 `AGENTS.md`；也可以在 `/config` 里把 Project instructions 设成 `claude-md-and-agents-md`，让两者都加载。Codex 的 [AGENTS.md 链](https://learn.chatgpt.com/docs/config-file/config-reference)是另一种做法：全局用 `~/.codex/AGENTS.override.md` 或 `AGENTS.md`，项目里从根目录往下逐层找、每层最多取一个文件、越靠近当前目录的越优先，总大小默认限制在 32 KiB。GitHub Copilot 的做法是在同一份文件里按顺序取，[目录树中最近的 `AGENTS.md` 优先](https://docs.github.com/en/copilot/concepts/prompting/response-customization)。

三个产品都读同一份文件，这已经很接近「写一次、处处可用」。但**指令文件是上下文，不是访问控制**。Claude Code 的文档把这句话说得很清楚：`CLAUDE.md` 是在系统提示之后作为用户消息下发的，模型会尽量遵守，但没有严格合规保证，冲突或模糊的指令尤其如此。Copilot 的文档也提醒，custom instructions 由于 AI 的非确定性，不会每次都严格按同样方式执行。

写「永远不要改迁移脚本」，你得到的是行为倾向，不是操作系统边界。真正要拦，得用运行时的强制机制——Claude Code 的文档给出的答案很具体：想在任何情况下阻止某个动作，用 `PreToolUse` hook，而不是指令；Codex 给的答案是把项目标记为 `trust_level = "untrusted"`，或者干脆不给它网络和写权限。

所以指令要写成**可验证**的句子，这也是各家文档一致的写法：

- 写 `使用 2 空格缩进`，不写 `注意代码格式`
- 写 `提交前运行 npm test`，不写 `改完要测一下`
- 写 `API handler 放在 src/api/handlers/`，不写 `保持文件组织清晰`

仓库里已经有维护好的指令文件时，不要因为换了个 agent 名字就再写一份策略文档。先确认当前版本的加载规则，再决定要不要合并。

## 关口三：把验收标准写成客户端能观察到的行为

「加个校验」不是验收标准。对这个 `pageSize` 任务，可执行的写法是：

> 用现有的 API 错误格式拒绝小于 1 或大于 100 的 pageSize；保持省略参数时的默认行为、认证、租户隔离、排序和成功响应结构不变；非法值不得到达查询服务；按现有测试约定补回归覆盖。如果实现需要改 schema、加包或改认证，停止并报告。

注意「保持省略参数时的默认行为」这一条。一个可选查询参数现在可能默认 20，把它改成必填会破坏客户端，哪怕 0 和 101 的测试全绿。**需求要同时写出兼容路径，不能只写新的错误路径。**

验收标准应该描述客户端或协作者能观察到的结果，而不是描述改哪个文件。改一个行为可能同时涉及 endpoint、回归测试和 API 文档，所以向 agent 要的是**受影响文件集合的说明**，而不是一个「只改一个文件」的硬限制。目标是完整的最小改动，不是为了 diff 好看而留下半截修复。

## 关口四：分清「写了规则」和「有权限」

这一条最容易被混淆。运行时的权限规则和文档里的文字是两种东西：**权限由运行时执行，文档只影响模型的选择。** 装包、跑构建、执行集成测试、应用迁移、发布，这些不是同一类「开发者命令」，它们的影响范围和需要的凭据都不同。

各家的执行机制不同，但都落在「沙箱 + 审批」这两层上：

- Claude Code 把规则分成 allow、ask、deny 三类，并且 [deny 先于 ask 和 allow 求值](https://code.claude.com/docs/en/permissions)：命中顺序只有一种，「更具体的规则」不会改变顺序，allow 规则也无法从 deny 里挖出例外。做一个只读探查会话，可以在设置里整体禁掉内置 shell 工具：

```json
{
  "permissions": {
    "deny": ["Bash", "PowerShell"]
  }
}
```

这段配置只演示「整体禁用一个工具」的语法，**它不是一个完整的安全策略**：文件工具、MCP server、hook 和插件进程都还各自需要单独看。它也不适合日常开发会话，因为禁掉 shell 就同时失去了命令行探查能力。

- Codex 默认在 `workspace-write` 下**关掉网络访问**，需要显式打开 `sandbox_workspace_write.network_access`；更值得注意的是它对可写根目录里的**受保护路径**处理——即使工作区可写，`<root>/.git`、`.agents`、`.codex` 在沙箱策略里仍然是只读的，而且是递归只读。这正好回答了「agent 能不能顺手改掉 git 目录或者自己的配置」这类问题：能不能，取决于运行时策略，而不是你写在提示词里的那句话。
- Copilot cloud agent 跑在自己的临时环境里，由 GitHub Actions 提供，[默认用防火墙限制它的互联网访问](https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/risks-and-mitigations)。这份文档同时提醒，防火墙有几条限制：只作用于 agent 启动的进程（Bash 工具，不含 MCP server）、只在 GitHub Actions 设备内生效、存在被绕过的可能，**不应被视为完整的安全方案**。
- 命令行侧，Copilot CLI 的 `--allow-tool`、`--deny-tool`、`--allow-all-tools` 是运行时开关，其中 `--deny-tool` 优先级高于 allow 类选项；`--allow-all`（别名 `--yolo`）会把工具、路径和 URL 全部放开。企业管理员可以用 `permissions.disableBypassPermissionsMode` 在启动时压制这些放行开关。

三条通用的判断规则：

**不要用命令行前缀的 deny 规则去假装覆盖所有等价写法。** Claude Code 的权限页有张很实在的表：`Bash(curl *)` 能挡住 `curl https://example.com`，挡不住 `/usr/bin/curl ...` 或者 `sh -c 'curl ...'`。文档的原话是，前缀规则覆盖的是「Claude 通常会写出的调用形式」，**它不是把这个程序围起来的安全边界**。Codex 的文档同样说明命令前缀规则可以被绕过。真正可靠的边界来自凭据和运行环境隔离。

**记住沙箱的作用范围。** Claude Code 的 Bash 沙箱只覆盖 shell 命令及其子进程，文件工具、MCP server、hook 与语言服务器都在沙箱之外。Codex 的网络代理同样只过滤本地命令沙箱内的流量，不过滤 web 搜索、MCP 连接或云端任务。两家文档都提醒，过滤的是流量本身而不是内容，别把它当成完整的隔离方案。

**云端 agent 的权限边界往往写死在产品里。** Copilot cloud agent 只能推送到单个分支、不能直接执行 `git push`，也[不能批准或合并自己的 pull request](https://docs.github.com/en/copilot/responsible-use/agents)；agent 改动的 workflow 不会自动运行，需要具备写权限的用户点下 Approve and run workflows。这些限制是可以直接引用的、可验证的边界，比任何提示词都可靠。

## 关口五：把语言服务器当成早期反馈，不要当成构建

Claude Code 的[代码智能插件](https://code.claude.com/docs/en/plugins/code-intelligence)里有一个官方 `csharp-lsp` 插件，它对接的语言服务器是单独的 `csharp-ls` 二进制：**装插件不会装二进制，装二进制也不会装插件**。二进制用 `dotnet tool install --global csharp-ls` 安装（插件自身的说明写的是 .NET SDK 6.0 或以上），插件在会话里用 `/plugin install csharp-lsp@claude-plugins-official` 安装。装好之后 agent 能在编辑文件后拿到诊断，并按符号跳转，而不是靠文本搜索找定义。

这对 C# 很实用，但它替代不了编译：

- 诊断只反映语言服务器实际加载的那个工作区配置，而且插件说明里只承诺 `.cs` 文件的诊断与跳转。多目标框架、条件编译、自定义 MSBuild 目标都可能让它和 CI 的结论不一致。官方文档也没有对 `.sln` 或 .NET Framework 项目做任何承诺。
- 官方文档写明，**云会话里不会启动插件的语言服务器**，所以「本地能跳转」不能当成云端行为的前提。
- 文本搜索仍然不可替代：路由字符串、配置键、SQL、文档都靠它。健康的方式是把几种证据源合起来用，而不是把某一种导航工具当万能钥匙。

Agent 报告一条诊断结论时，问清楚它是哪个环境产出的。编辑器、插件语言服务器和 CI 编译给出不同答案，是值得追查的分歧，不是让你挑一个绿色的结果相信。

## 关口六：让交接报告对得上契约

一份有用的完成报告应该把每条需求连到证据上。对 `pageSize` 这个任务，这意味着一条**真的构造或发送了非法输入**的测试，断言拒绝发生，并在契约要求时确认下游查询没有被调用。

只验证 mock 返回预设对象的那种「绿测试」证明不了 endpoint 行为；同理，一个通过的 handler 单元测试也证明不了路由绑定、授权和序列化组合起来会产生预期的 HTTP 响应。看到测试名字很自信不代表什么，要看它实际执行了什么。

执行证据至少包含五项：**命令、版本、环境、结果，以及没有覆盖到的部分。** 如果执行被禁止或者环境不可用，报告必须说明这一点——「写了示例」和「示例跑通了」是两个不同的状态。Codex 的文档把这个习惯写成了流程建议：像对待任何 PR 一样对待 agent 的建议，跑定向验证、审查 diff、在提交信息里记录决策。

人工审查最后看 diff 本身：授权是否保留、持久化行为是否变化、响应结构是否兼容、校验分支是否完整、有没有夹带无关依赖升级。测试全绿有帮助，但它不替代这一步。

如果希望这件事不依赖人的记性，Claude Code 的[最佳实践](https://code.claude.com/docs/en/best-practices)给了一个可复制的做法：用 `Stop` hook 把检查脚本挂在回合结束前，**脚本不过就不允许这一轮结束**。这类确定性关卡比「请在提交前跑测试」这句话有效得多——后者的执行者是模型，前者的执行者是运行时。

## 换成别的 agent，四道关口怎么排

把上面的循环抽象掉产品名，就是四个问题：**它在哪跑、它能读什么、你在授权什么、证据长什么样。** 不同工具在这几层上的实现如下（截至 2026 年 10 月，均取自各官方文档）：

| 关口     | Claude Code                                                                     | OpenAI Codex                                                                                                   | GitHub Copilot                                                                                                  |
| -------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 共享指令 | `CLAUDE.md`，没有 `CLAUDE.md` 时才读 `AGENTS.md`；`.claude/rules/` 可按路径生效 | `AGENTS.md` 逐层查找，每层一个文件，越靠近当前目录越优先；`~/.codex/config.toml` 加项目级 `.codex/config.toml` | `.github/copilot-instructions.md`、`.github/instructions/**/*.instructions.md`、`AGENTS.md`，个人与组织级各一层 |
| 权限机制 | allow / ask / deny，deny 优先；权限模式；`/sandbox`                             | 沙箱模式加审批策略，`--ask-for-approval`、`--sandbox`、`--dangerously-bypass-approvals-and-sandbox`            | 工具审批提示；`--allow-tool`、`--deny-tool`、`--allow-all`；云端另有固定边界                                    |
| 执行环境 | Bash 沙箱覆盖 macOS / Linux / WSL2，原生 Windows 不受沙箱保护                   | macOS 用 Seatbelt，Linux 用 bwrap 加 seccomp，Windows 原生支持并保留回退实现                                   | 云端任务在临时 GitHub Actions 环境执行，网络默认受防火墙限制                                                    |
| 默认边界 | 沙箱默认关闭，需 `/sandbox` 或 `sandbox.enabled` 打开                           | 默认工作区可写、网络关闭；可写根目录里 `.git`、`.agents`、`.codex` 仍只读                                      | cloud agent 单分支、不能合并自己的 PR、workflow 需人工放行                                                      |
| 证据形态 | 要求报告命令、版本、环境与未覆盖部分                                            | 建议按 PR 流程验证、审查 diff、记录决策                                                                        | PR diff、会话日志、审计日志；提交信息里链接 agent 会话                                                          |

表格里的产品细节会随版本变化，所以更稳的做法是**只记四道关口，把工具细节当成实现**。换工具时重新确认一次默认值，特别是默认的沙箱状态和默认的审批策略——这两项决定了 agent 在你机器上第一次执行命令时的实际权力。

## 其他 agent 也是同一套动作

同样的四道关口在别的工具上是同一套动作，只是名字不同：

- **Gemini CLI** 用 `GEMINI.md` 作为上下文文件（可通过 `context.fileName` 改），用 `--sandbox` 选择隔离后端，后端可以是 macOS Seatbelt、Docker / Podman、Windows 原生或 gVisor。
- **Cursor** 把规则放在 `.cursor/rules` 下的 `.mdc` 文件里（普通的 `.md` 会被忽略），终端权限走 Run Modes，配置项是 `autoRun.allow_instructions` / `block_instructions`——用自然语言描述允许和禁止，而不是命令前缀列表。
- **Aider** 是 git 优先的路线：默认自动提交每次改动，配置按 home、git 根目录、当前目录的顺序加载，`--yes` 可以把所有确认一次性放行。

这几家的默认值差异很大，正好说明为什么「默认审批策略」值得单独确认一次。

## 常见问题

**Agent 会自动了解整个解决方案吗？** 它能读也能导航仓库文件，但这不等于它检查了所有相关契约。给它解决方案入口，然后要一条穿过受影响代码的具体追踪。

**仓库指令能拦住数据库写入吗？** 不能。指令是上下文，不是强制。用运行时权限、受约束的工具和最小权限凭据，并且把外部工具也纳入审查范围。

**C# 语言服务器诊断能替代编译吗？** 不能。诊断只对语言服务器加载的那个工作区给早期反馈；编译和测试在目标环境里回答引用、构建配置和行为的问题。

**应该只让 agent 改一个文件吗？** 不一定。一个行为可能同时涉及 endpoint、测试和文档。把范围限制在完整的行为上，然后审查它给出的受影响文件说明。

**云端 agent 和自己终端里的 agent，边界一样吗？** 不一样，通常云端的边界更硬。Copilot cloud agent 不能批准或合并自己的 PR，也没有 `git push`；Codex 在本地默认就是工作区可写加网络关闭。这些是产品写死的限制，比本地会话里的提示词可靠，值得优先利用。

## 收尾

Nick 在原文结尾把这件事总结成一句话：**环境决定可用工具，上下文决定约束，请求定义行为，权限划定授权，验证和审查决定结果到底证明了什么。** 这套模型把注意力留在应用契约上，而不是留在 agent 的自信程度上。

三个可以直接落地的动作：

1. **给仓库写一份最小指令文件**：构建命令、测试命令、目标框架、endpoint 契约位置。控制在 200 行以内，超出就拆成按路径生效的规则。
2. **确认默认审批策略**：哪些命令直接放行、哪些必须先问、哪些永久拒绝。沙箱是不是开着、网络是不是通着，都要自己看一眼，别等出事再补。
3. **把交接报告的格式定下来**：改了哪些文件、每条验收标准对应哪条证据、跑了什么命令、还有什么不确定。

一个小的、能解释清楚、有证据支撑的改动，比一次只会说「工具跑完了」的大重构好维护得多。

如果你也在用编码 agent 做日常开发，欢迎关注 Aide Hub。我们会继续分享 AI 助手、开发工具和软件工程实践的一手内容。

## 参考

- [Claude Code for .NET Developers: A Reviewable Repository Workflow（原文，Nick Cosentino）](https://www.devleader.ca/2026/10/12/claude-code-for-net-developers-a-reviewable-repository-workflow)
- [Claude Code：权限配置](https://code.claude.com/docs/en/permissions)
- [Claude Code：Bash 沙箱](https://code.claude.com/docs/en/sandboxing)
- [Claude Code：记忆与 CLAUDE.md / AGENTS.md](https://code.claude.com/docs/en/memory)
- [Claude Code：代码智能插件](https://code.claude.com/docs/en/plugins/code-intelligence)
- [Claude Code：最佳实践](https://code.claude.com/docs/en/best-practices)
- [Codex：沙箱与审批](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Codex：配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [GitHub Copilot：自定义指令与优先级](https://docs.github.com/en/copilot/concepts/prompting/response-customization)
- [GitHub Copilot：agent 的风险与缓解](https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/risks-and-mitigations)
- [GitHub Copilot：负责任地使用 agent](https://docs.github.com/en/copilot/responsible-use/agents)
