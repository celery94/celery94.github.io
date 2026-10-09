---
pubDatetime: 2026-10-09T08:51:33+08:00
title: "WinDbg MCP：用自然语言调试崩溃转储"
description: "WinDbg 新增 MCP 服务，AI 客户端可直接操作真实调试会话。这篇整理接入步骤、安全模式实际拦住了什么、Diagnostician 的五阶段诊断流程，以及四项故障排查。"
tags: ["WinDbg", "MCP", "调试", "AI 编程助手", "Windows"]
slug: "windbg-mcp-natural-language-debugging"
ogImage: "../../assets/1087/01-cover.jpg"
source: "https://devblogs.microsoft.com/performance-diagnostics/introducing-windbg-mcp-debug-with-natural-language-grounded-in-evidence/"
---

WinDbg 过去的使用门槛在于：你得知道该跑哪条命令、怎么看它的输出、下一步该验证什么。这些都得现场决定。现在微软把 WinDbg 接进了 Model Context Protocol（MCP），AI 客户端可以直接驱动一个真实的调试会话，你用自然语言提问，命令在 WinDbg 里可见地执行。

[原文](https://devblogs.microsoft.com/performance-diagnostics/introducing-windbg-mcp-debug-with-natural-language-grounded-in-evidence/)是 Shanthi Rajan 在 2026 年 10 月 6 日发布的 WinDbg MCP 介绍，覆盖了是什么、五步上手、Diagnostician 技能、架构和内置安全保护。这篇在三处做了补充：**原文没写的启用顺序要求**（顺序错了保护会降级）、**官方文档里明确记载的管理员权限陷阱**（会让连接直接失败），以及**两个安全开关实际拦住了什么**。这些是照着原文步骤做时最容易卡住的地方。

## 先说三个最容易踩的坑

**第一，`File > Settings > MCP service settings > Enable Secure Mode for MCP Server` 的勾选状态会被对话框改写。** 启动 MCP 服务时弹出的「Privacy and Security Warning」里有一个默认勾选的 `Enable secure mode when the MCP server starts`。在这个对话框里清除或勾选它，会同步写回上面的设置项，也就是说这一次的选择会成为以后每次启动的默认值。

**第二，WinDbg 不要以管理员身份运行。** 官方故障排查文档里有一条独立条目：当 WinDbg 以管理员权限运行时，AI 客户端通过代理连接会失败并报 **Access denied**。解决办法是关掉提权的 WinDbg，重新以普通权限启动，再开 MCP 服务。需要提权调试的场景和 WinDbg MCP 目前是冲突的。

**第三，连接目标的顺序决定你拿到的是完整保护还是部分保护。** 官方给安全模式定了两档：先在 WinDbg 里启动 MCP 服务、再附加或加载调试目标，得到的是 **Full secure mode**；如果已经连上目标才启动服务，WinDbg 进入 **Partial secure mode** 并弹警告。原文只是提了一句「先启动 MCP 再连目标可获完整安全模式」，没有说明这两档的实际差别。要修正只能重启 WinDbg 重来。

这三条合起来意味着：正确的顺序是**先建独立会话时把顺序做对，再用普通权限启动**，而不是按直觉先打开 dump 再点 MCP 服务。

## 五步接上 AI 客户端

原文给出的流程和官方文档一致：

1. 打开 WinDbg，进入 **MCP service settings**，勾选 **Enable Server**，在 **Client** 列表里选 **VS Code** 或 **GitHub Copilot CLI**。
2. 点 **Install MCP**，把 WinDbg 注册到所选客户端，完成客户端弹出的确认。
3. 点 **MCP Service**，阅读「Privacy and Security Warning」，确认 **Secure Mode** 选项后选 **Yes** 启动服务。
4. 加载或附加到调试目标。
5. 点 **Open Chat** 开始对话。

前置条件里有两项容易漏掉：WinDbg 版本需为 **1.2610.1001.0 或更高**（Microsoft Store 或 [WinDbg 下载页](https://aka.ms/windbg/download)获取）；组织若启用了 WinDbg 受限模式，MCP 控件会被隐藏或禁用，这时你连按钮都看不到。

### 怎么确认真的连上了

原文没写验证方法，官方文档有一步很快的检查：

1. 看 WinDbg 状态栏是否显示 **AI client connected to MCP server**。
2. 在 AI 客户端里发一句：`Use WinDbg MCP to report the current target type and execution state.`
3. 核对客户端报告的目标类型和执行状态是否和 WinDbg 窗口里显示的一致。

第 3 步是关键。如果客户端回的东西和 WinDbg 界面对不上，说明它没在查真实会话，这时候后面的所有分析都不可信。

### 装了多个 WinDbg 会话怎么办

原文提到「如果有多个会话，可以选择要调查的那个」，但没有给操作方式。官方文档里有一组连接工具，而且**要通过 AI 客户端对话来调用，不要直接把这些名字敲进 WinDbg**：

| 工具                 | 用途                                                          |
| -------------------- | ------------------------------------------------------------- |
| `list_sessions`      | 列出所有启动了 MCP 服务的 WinDbg 会话，并报告每个会话是否可用 |
| `connect_session`    | 按进程 ID 把代理连接到指定会话                                |
| `disconnect_session` | 断开代理与当前会话的连接                                      |

代理的行为是：**只检测到一个可用会话时自动连接；检测到多个时保持断开，等你显式指定。** 如果某个会话显示不可用，通常是另一个 AI 客户端正连着它——一个 WinDbg 会话同时只允许一个活动的 MCP 客户端。

## 安全保护实际拦住了什么

原文列了日志、Secure Mode、XPIA 三项，措辞都是效果描述。官方文档给了具体边界，这些决定了你第一次用会不会被卡住。

### Secure Mode 挡的是命令，不是间接行为

Secure Mode 限制的是能加载或执行不受信任代码、启动进程、执行不安全文件操作的调试器功能。官方点名的例子是它会**阻止 `.shell` 这类高风险命令**。

它的生命周期也有两个特点：**一旦激活就无法关闭，直到重启 WinDbg**；而且**停止 MCP 服务不会解除它**。所以如果你先开了 Secure Mode 又想关掉，唯一路径是重启 WinDbg；重启后要记得在设置里清除 `Enable Secure Mode for MCP Server`。另外有个容易搞混的点——**关闭 XPIA 保护不会同时关闭 Secure Mode**，两者是独立的开关。

官方还给了一条需要认真读的警告：**不启用 Secure Mode 时，AI 客户端直接执行的命令仍然受限，但间接行为不受限。** 举例来说，如果 AI 客户端设了一个断点、而断点命中时会执行某条命令，那条命令会以你的完整权限运行。这条间接路径是评估「要不要关掉 Secure Mode」时最该考虑的点。

### XPIA 保护可能让操作直接失败

跨提示注入攻击（XPIA）保护的机制是：WinDbg 把某些操作标记为受保护操作，用 AI 客户端配置的模型服务去分类该操作的调试器输出，判定为潜在不安全的内容会被拦下。

这里有个比「降低保护」更硬的后果：**XPIA 保护依赖 MCP sampling。** 如果 AI 客户端不支持、或者其配置和组织策略不允许 MCP sampling，分类就无法执行，而**受保护操作会直接失败，不返回任何输出**。不是警告，不是降级，是没有结果。

这解释了原文一句容易被跳过的说明：VS Code 和 GitHub Copilot CLI 是目前官方支持的客户端，因为它们支持 MCP sampling。其他 MCP 兼容客户端（原文点名 Codex 和 Claude Code）可以按自定义配置尽力尝试，但**要关闭 XPIA 保护才能工作**——而从上面这条机制看，更准确的说法是：客户端不支持 sampling 时，受保护操作根本拿不到输出，只能靠关掉保护绕过去。

`windbg` 插件的官方 README 把这件事写得更直白：让 Claude Code 使用 WinDbg MCP 而不被拦截，需要在 `WinDbg > Settings > MCP` 里**同时清除** `Enable Cross Prompt Injection Mitigation` 和 `Enable Secure Mode for MCP Server`；如果 Secure Mode 已经激活，还得重启 WinDbg（因为它不会自动解除）。README 自己也加了警告：这两个都是安全保护，只应在你被授权暴露 dump、命令输出、源码和提示词的受信任会话里关闭，用完后重新打开。

### 架构上的一条边界

官方画出了完整的连接路径：AI 模型服务 ↔ AI 客户端 ↔ `DbgX.Mcp.Proxy.exe`（stdio MCP）↔ 本地按进程命名管道 ↔ WinDbg MCP 服务器。

对使用者来说，这个链路里值得记住的是：**调试器连接始终是本地和内存内的**，只有拿到会话信息之后的 AI 请求会发往模型服务。官方也提示 MCP 诊断日志本身可能包含调试器命令和目标数据，需要按敏感数据处理。

## Diagnostician：把调试变成可复现的流程

Diagnostician 是这次随 WinDbg MCP 一起给出的插件，它带来的不是新的调试能力，而是一套**反对「模式匹配当结论」的方法论**。

### 安装

它属于公开的 `win-dev-skills` 目录里的 `windbg` 插件。前置条件是 Git、GitHub Copilot CLI、WinDbg 已加载目标、MCP 服务已连接：

```powershell
copilot plugin marketplace add microsoft/win-dev-skills
copilot plugin install windbg@win-dev-skills
```

这两条是一次性配置。之后新开 Copilot CLI 会话，用原文给的那句提示词开始：

```text
Root cause the dump in the debugger. Let the diagnostician orchestrate the
debugging session, test alternative explanations, and state what evidence is
missing.
```

### 五个阶段和三档推理路径

每次诊断都走一个 **hypothesis-test-pivot** 循环：**OBSERVE**（解析 dump/trace 类型、架构、栈、代码、寄存器、资源状态和证据局限）→ **HYPOTHESIZE**（形成一个具体可检验的主假设和若干备选）→ **TEST**（找出能证实或否证每个假设的证据）→ **EVALUATE**（把证据分成已支持、已被否证、推断、缺失）→ **CONCLUDE 或 PIVOT**（给出结论和验证计划，或者推翻重来）。

推理路径按初始匹配的置信度分三档：

| 路径           | 初始置信度     | 行为                                             |
| -------------- | -------------- | ------------------------------------------------ |
| Fast           | ≥ 80%          | 把强匹配当假设，验证必要证据并检查备选后才下结论 |
| Validate       | 40–79%         | 领先假设和至少一个合理备选都走完整循环           |
| Full-reasoning | < 40% 或无匹配 | 从观察出发构建备选，显式保留不确定性             |

插件 README 对置信度有一句重要限定：**它是解释辅助，不是测量出来的概率**；初始匹配度再高也不能跳过证据，更不能因为某个模块出现在栈上就归咎于它。

### 报告里有什么

原文提到「Copilot CLI 能写文件时会输出 Markdown 报告到 `.diagnoses\<short-id>\<yyyyMMdd-HHmmss>.md`」，但没有说报告结构。用完整提示词跑时，报告固定包含这些 H2 小节：`Analysis`、`Root Cause`、`Fix`、`Reasoning Chain`、`Alternatives Considered`、`Trigger Verification`、`Mermaid`、`Contrarian Verdict`、`JSON Output Contract Summary`。

其中两个小节是质量控制的关键：

- **`Trigger Verification` 必须是一张表**，把观察到的证据、矛盾证据、缺失证据、以及验证修复方案所需的动作分开列出。
- **`Contrarian Verdict` 来自一个独立的对抗性审核子代理。** 完整提示词会同时触发对抗审核和验证这两道门。而且插件明确规定：如果宿主环境跑不了独立子代理，代理必须**声明这个限制**，不能用自己的内联自审冒充。

还有一条硬约束：**只要还有未检验的合理备选，就不能把根因定稿。** 证据不足时状态应写 `candidate-pending-verification`，并指明下一步需要什么证据。

### 它覆盖什么、不覆盖什么

插件按 bug 家族组织技能，分用户态和内核态两组。

用户态（含 UMDF 驱动宿主）：

| 技能                                        | 适用场景                                    |
| ------------------------------------------- | ------------------------------------------- |
| `windbg-user-exception-triage`              | 建立异常上下文，分类原生进程崩溃            |
| `windbg-user-heap-corruption-investigation` | 使用已释放内存、重复释放、越界写            |
| `windbg-user-wait-chain-analysis`           | 应用/服务/驱动/COM/RPC 等待链到阻塞点或环   |
| `windbg-user-ttd-reverse-debugging-triage`  | 在用户态 TTD 录制里找更早的写入、释放和调用 |
| `windbg-user-virtual-memory-exhaustion`     | 区分地址空间压力、碎片、提交压力和配额      |
| `windbg-user-mutex-held-across-co-await`    | 协程挂起点上持有线程亲和锁                  |

内核态：

| 技能                                 | 适用场景                                       |
| ------------------------------------ | ---------------------------------------------- |
| `windbg-kernel-bugcheck-triage`      | 解码 bugcheck，恢复原始异常或陷阱上下文        |
| `windbg-kernel-verifier-triage`      | 解读 Driver Verifier 违规和可用的 I/O 验证证据 |
| `windbg-kernel-irp-lifecycle-triage` | 未完成 I/O、完成/取消归属、电源 IRP            |
| `windbg-kernel-lock-deadlock-triage` | 构建内核 owner/waiter 图，调查锁顺序反转       |

适用范围上有一条需要明确：**这是 Windows 原生调试的指引，不是托管的 .NET 诊断包。** 如果你要查的是 .NET 应用的 GC、线程池或托管异常，这套技能不在覆盖范围内。插件里也没有专门的 C++ 抛出对象或 XAML stowed exception 解码器——`windbg-user-exception-triage` 会记录这个边界，然后按证据继续推理，而不是硬套一个不存在的技能。

另外，**插件本身不含 MCP 服务器**。它只提供诊断方法和技能；调试器连接来自你另行配置的 WinDbg MCP 集成。这意味着技能在支持 skill 的宿主上可以独立使用——你需要自己执行它建议的命令，再把输出贴回去。

## 出问题时先查这四项

官方有一份独立的故障排查文档，原文没有引用。按症状对应：

| 症状                               | 常见原因                                                   | 处理                                                                                     |
| ---------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| 客户端 MCP 服务器列表里没有 WinDbg | `Install MCP` 没注册成功，或客户端没重新加载配置           | 重启客户端，在 **MCP service settings** 里重新选客户端并再点一次 **Install MCP**         |
| 找不到想要的 WinDbg 会话           | 目标窗口没启动 **MCP Service**，或存在多个会话无法自动选择 | 在目标窗口启动 MCP 服务，然后让客户端用 `list_sessions` 和 `connect_session` 指定进程 ID |
| 会话不可用                         | 另一个 AI 客户端正连着它                                   | 在已连接的客户端执行 `disconnect_session`，再用目标客户端重连                            |
| 连接报 **Access denied**           | WinDbg 以管理员权限运行                                    | 关闭提权的 WinDbg，以普通权限重启后重开 MCP 服务                                         |

如果 `Install MCP` 反复失败，官方给了手动注册的兜底做法：在 **MCP service settings** 里选 **Custom**，点 **Copy to Clipboard** 拿到代理命令路径，然后把它写进工作区的 `.vscode/mcp.json`：

```json
{
  "servers": {
    "WinDbg": {
      "type": "stdio",
      "command": "C:\\path\\to\\DbgX.Mcp.Proxy.exe",
      "args": []
    }
  }
}
```

把 `command` 换成剪贴板里的真实路径，然后重启 VS Code。

## 要不要现在就用

按当前信息可以这样判断：

- **值得试**：你平时就在用 WinDbg 分析 dump，且目标数据允许发给模型服务。收益最直接的是省掉「先查哪条命令」的往返，以及让 AI 在 WinDbg 里可见地执行命令供你复核。
- **先解决前提**：目标涉及客户环境、内存内容或私有符号。这时要先确认组织是否允许、以及 Secure Mode 和 XPIA 是否都要保持开启——两个都开着是默认状态，也是最保守的状态。
- **暂时不适合**：组织启用了 WinDbg 受限模式，或者你的调试场景必须提权运行 WinDbg。前者会让 MCP 控件不可见，后者目前会直接连接失败。
- **不要抱错期望**：这是原生 Windows 调试工具，不是 .NET 托管诊断方案；也不要用它替代对根因的验证——原文和官方文档都反复强调，**AI 生成的结论不是权威结果**，要对照 WinDbg 里的目标状态和实际证据来确认。

最后一条实操建议来自插件对「状态改变型操作」的定位：启用 Application Verifier 或 Page Heap、改配置、抓 trace、强制崩溃这类动作，**默认需要你显式授权**，而且插件的默认姿态是只读诊断。如果你是第一次跑，不妨就让它只产出诊断和验证计划，改动交给下一轮。

## 参考

- [Introducing WinDbg MCP: Debug with natural language, grounded in evidence（原文）](https://devblogs.microsoft.com/performance-diagnostics/introducing-windbg-mcp-debug-with-natural-language-grounded-in-evidence/)
- [Set up and use WinDbg MCP](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/set-up-windbg-mcp)
- [WinDbg MCP overview](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/windbg-mcp-overview)
- [Troubleshoot WinDbg MCP setup and connection issues](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/troubleshoot-windbg-mcp-setup-connection-issues)
- [WinDbg: Restricted mode](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/windbg-restricted-mode-preview)
- [win-dev-skills：windbg 插件 README](https://github.com/microsoft/win-dev-skills/blob/main/plugins/windbg/README.md)
- [WinDbg Feedback repository](https://github.com/microsoft/WinDbg-Feedback/issues)
