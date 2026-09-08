---
pubDatetime: 2026-09-08T08:09:40+08:00
title: "别让 AI 选错 NuGet 包：四道仓库护栏"
description: "AI 代理按 2023 年的默认值选 .NET 库，而 AutoMapper、MediatR、MassTransit 已商业化。用 NuGet MCP Server、指令文件、构建门禁与中央包管理四道护栏挡住错误，附 2026 许可现状表。"
tags: ["NuGet", "AI Agent", ".NET 10", "Supply Chain"]
slug: "ai-agent-nuget-package-guardrails-dotnet"
ogImage: "../../assets/1058/01-cover.jpg"
source: "https://codewithmukesh.com/blog/ai-agent-nuget-package-guardrails-dotnet/"
---

你的 AI 编码代理选 .NET 库时，依据的是一份大约 2023 年的快照，按 2023 年的许可条款定价。它不知道 AutoMapper、MediatR、MassTransit 和 FluentAssertions 在那之后全部转向商业许可；更不可能知道你们公司的年收入——而正是这个数字决定你要不要付钱。

这不是靠提示词能补上的差距。Mukesh Murugan 在 [Stop Your AI Agent Picking the Wrong .NET Libraries](https://codewithmukesh.com/blog/ai-agent-nuget-package-guardrails-dotnet/) 里给出结论：**库选型已经变成许可与预算决策，而我们却把它交给一个只能看到代码的工具。这个差距应该补在仓库里，而不是聊天里。**

本文整理原文的三种出错方式、核对过的 2026 许可现状，以及四道可以今天就装上的护栏。

## 代理为什么选错：三种不同的错

把三种错法分开看，因为它们需要不同的修法。

**1. 旧但真实。** 包是真实的、广泛使用的、教程里推荐的——只是现在要花钱，或者免费线带着没人修补的通告。这是最常见的错误，也是最难在审查中发现的：代码看起来完全正常。

**2. 省略式错误。** 代理给框架早已内置的东西装包。限流、健康检查、JSON 序列化、HTTP 弹性、OpenAPI 文档生成，从 .NET 8 或 .NET 10 起都已经内置。这里加一个依赖是纯成本零收益，而审查中它同样隐形——一行 `PackageReference` 看起来像干活。

**3. 根本不存在的包。** 这是有硬数据的。[USENIX Security 2025 的一项研究](https://arxiv.org/abs/2406.10279)测试了 16 个模型、57.6 万个生成代码样本，发现 **19.7% 的包引用指向不存在的包**；商业模型明显更好，约 5.2%，开源权重模型高达 21.7%。更值得警惕的是构成：约 51% 是纯虚构，38% 是把两个真实包名焊接在一起的拼接，13% 是拼写变体——后两种看起来就像一个你依稀记得的包。

Slopsquatting 就是建在这种幻觉之上的攻击（由安全研究员 Seth Larson 命名）：模型幻觉出的名字会稳定复现，攻击者盯住一个尚不存在的合理名字抢先注册。有研究员在一个模型反复编造的名字下发布了一个无害空包，三个月内记录到 3 万多次下载。

NuGet 的处境要特别说清：它的 ID 命名空间是扁平、全局、先到先得的，没有 npm `@scope/` 那样把名字绑定到所有者的机制，所以「名字看起来官方」在 NuGet 上比开发者以为的更弱。前缀保留确实给已验证所有者一个徽章，但拦不住任何人注册一个未被保留的、听起来合理的 ID。

## 2026 许可现状：一张会过期的表

原文用 NuGet 注册 API 在 2026 年 8 月 29 日核对过这张表。读到这篇时请按当前状态再过一遍——这类信息正是会悄悄过期的那种：

| 包               | 最后免费版                       | 当前版 | 当前许可         |
| ---------------- | -------------------------------- | ------ | ---------------- |
| AutoMapper       | 14.0.0（2025-02-14，MIT）        | 16.2.0 | RPL-1.5 + 商业   |
| MediatR          | 12.5.0（2025-04-01，Apache-2.0） | 14.2.0 | RPL-1.5 + 商业   |
| MassTransit      | v8 线（Apache-2.0）              | 9.2.1  | 商业（Massient） |
| FluentAssertions | 7.x（Apache-2.0）                | 8.10.0 | Xceed 商业       |
| Polly            | 仍是 BSD-3-Clause                | 8.7.0  | BSD-3 + 维护费   |

决定是否花钱的细节：

- **AutoMapper 与 MediatR** 同属 Lucky Penny Software，条款一致：年总收入低于 500 万美元的组织、预算低于 500 万美元的非营利机构、教育与非生产用途，可用免费 Community 档；之上的商业许可从每年约 489 美元起步（Standard 档，1–10 名开发者）。源码按 RPL-1.5 发布，相互性许可与多数闭源产品不兼容。
- **MassTransit v9** 于 2026 年一季度以商业许可发布（Massient），公布价格约小企业 400 美元/月、大型企业 1200 美元/月，年收入约 100 万美元以下可享 100% 折扣。Apache 许可的 v8 线至少到 2026 年底仍收安全补丁——「留在 v8」买的是时间，不是答案。
- **FluentAssertions 8** 仅对开源与非商业用途免费。**AwesomeAssertions 9.6.0** 是 v7 线的社区分支，保持 Apache-2.0 且 API 兼容，需要离开时几乎是零成本迁移。
- **AutoMapper 14.0.0** 带有 CVE-2026-32933 / [GHSA-rvv3-g6hj-g44x](https://github.com/advisories/GHSA-rvv3-g6hj-g44x)（高危 DoS，CVSS 7.5），修复只在商业版 15.1.1 与 16.1.1，从未回移植；现在恢复它就会触发 NU1903 警告。

**Polly 的坑值得单独说。** Polly 采用 [Open Source Maintenance Fee](https://thepollyproject.org/2026/07/14/polly-osmf-announcement.html)，2026 年 7 月 14 日公布、11 月 16 日起执行：使用 Polly 的产品年收入至少 2 万美元的组织，每月每组织 20 美元；许可本身不变，仍是 BSD-3-Clause。个人、爱好者、学生、非营利组织与低于门槛的组织无需付费。容易踩的是：常见建议「用一方包 Microsoft.Extensions.Http.Resilience 代替裸 Polly」——它是 MIT，但会传递拉入 Polly.Core、Polly.Extensions、Polly.RateLimiting。也就是说，换到微软包并不会把 Polly 移出依赖图。公告没有明确回答传递消费者是否付费，所以「一方包绕过了费用」这个假设需要核实，而不是默认成立。

仍在免费、无需动作的：FluentValidation 12.1.1（Apache-2.0）、Serilog 4.4.0、Dapper 2.1.79、Riok.Mapperly 4.3.1、xunit.v3 4.0.0、Shouldly 4.3.0（BSD-3）、Mapster 10.0.12、WolverineFx 6.30.3、Rebus 8.9.3（MIT）。另一个反复出现的混淆：**FluentAssertions 商业化了，FluentValidation 没有**——不同项目、不同维护者、相似名字。别让代理（或匆匆扫视的审查者）把它们混为一谈。

## 在选库之前：确定需要这个包吗？

上面所有内容都默认「依赖是合理的，只是选哪个」。多数时候这个假设是错的。代理添加依赖时感受不到成本：传递依赖图、大版本升级税、CVE 面、以及新同事花二十分钟搞清映射逻辑在哪。一行 `PackageReference` 看起来像进展，代价几乎为零，而三年后移除它代价极高。

原文的过滤器，按顺序问：

1. **框架已经做了吗？** .NET 10 覆盖的能力远超多数人的包习惯，先查。
2. **50 行内能写出来并且我乐意维护吗？** 一个映射扩展方法、一个小的重试封装、一个分发器接口，常常比库需要的配置还少。
3. **它值得放在边界上吗？** 与外部世界打交道的库——序列化器、数据库驱动、消息传输、密码学——值得依赖，你不该手搓；只在内存里重排自己对象的库通常不值得。
4. **它商业化了或停止维护了怎么办？** 这曾是过度警惕的问题——但上面四个库在十八个月内给了答案。

第四问在 2025–2026 年变了：依赖风险从「被遗弃」变成「许可变化砸在一个已经承重的库上」，而迁移成本最高的时候恰恰是你最没有选择的时候。

## 四道护栏

### 护栏 1：给代理实时包数据

最高价值的修复是把猜测整个拿掉。微软发布 [NuGet MCP Server](https://learn.microsoft.com/en-us/nuget/concepts/nuget-mcp-server)（MCP 是代理调用外部工具的开放标准），让代理实时访问包版本与漏洞数据，而不是依赖记忆。Visual Studio 2026 已内置（Copilot Chat 工具菜单开关）；其他环境用 `mcp.json` 配置——它通过 `dnx` 命令运行，**需要 .NET 10 SDK**：

```json
{
  "servers": {
    "nuget": {
      "type": "stdio",
      "command": "dnx",
      "args": [
        "NuGet.Mcp.Server",
        "--source",
        "https://api.nuget.org/v3/index.json",
        "--yes"
      ]
    }
  }
}
```

接上之后，「修复我的包漏洞」「把包升到最新兼容版本」这类提示词就针对真实源和你的目标框架解决，而不是训练数据。它不解决许可问题——许可不是漏洞元数据——但整个「代理建议了一个不存在或早被取代的版本」这一类错误被移除了。

### 护栏 2：把决定写进仓库

每次会话手动纠正，迟早会在紧要的那次忘记。把决定放到每个会话都读的地方：`CLAUDE.md`（Claude Code）、`AGENTS.md` 或 `.github/copilot-instructions.md`（Copilot）：

```markdown
## Dependencies

不要在没有确认的情况下添加 NuGet 包。默认答复是「不」。

已定决定：

- 映射：Mapperly（Riok.Mapperly）。永远不用 AutoMapper。
- CQRS：src/Shared/Dispatch 里的手写分发器。永远不用 MediatR。
- 断言：AwesomeAssertions。永远不用 FluentAssertions v8+。
- 弹性：Microsoft.Extensions.Http.Resilience。
- 校验：FluentValidation（仍是 Apache-2.0，与 FluentAssertions 不是一回事）。

提交任何新包之前，请说明：许可、最新稳定版本、以及你首先排除的 .NET 10 内置方案。
```

最后一行干了大部分活：强制代理写清许可与内置替代方案，把一个隐形决定变成聊天里可见、可反驳的东西。这比「编译器已经强制的风格规则」有价值得多。

### 护栏 3：让构建强制执行

指令文件是指导性的，而指导会被无视——人类和代理都一样。构建是讲不进道理的地方。

**让有漏洞的包失败。** NuGet 审计默认已开启（`NuGetAudit` 默认 `true`；针对 net10.0 及以上，`NuGetAuditMode` 默认 `all`，即传递包也覆盖；旧目标框架默认只查直接引用）。默认不自动做的是让构建失败。加到 `Directory.Build.props`：

```xml
<Project>
  <PropertyGroup>
    <WarningsAsErrors>$(WarningsAsErrors);NU1903;NU1904</WarningsAsErrors>
  </PropertyGroup>
</Project>
```

NU1903 是严重、NU1904 是致命，中低危通告保持警告。保留 `$(WarningsAsErrors);` 前缀——丢掉它会把该属性已持有的内容替换掉而不是追加。如果本地构建因新通告失败太吵，文档化的做法是用 MSBuild 条件让它只在 CI 生效。

**让新增包成为可见的 diff。** 中央包管理把版本集中到仓库根的 `Directory.Packages.props`：

```xml
<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
    <CentralPackageTransitivePinningEnabled>true</CentralPackageTransitivePinningEnabled>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Riok.Mapperly" Version="4.3.1" />
    <PackageVersion Include="FluentValidation" Version="12.1.1" />
    <PackageVersion Include="Serilog.AspNetCore" Version="10.0.0" />
  </ItemGroup>
</Project>
```

安全价值不在版本管理，而在：代理不再能靠悄悄修改功能 diff 里某个 `.csproj` 添加依赖，它必须碰到审查者盯着的根级文件，任何新包都会在这个「列出你依赖什么」的文件里多出一行。

**把包锁定到源。** 包源映射是 .NET 对依赖混淆与 slopsquatting 的答案——声明每个包模式可以从哪个源还原，一个出现在公共源上、名字很像的包 ID，就满足不了映射到内部源的引用：

```xml
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
    <add key="internal" value="https://pkgs.mycompany.com/v3/index.json" />
  </packageSources>
  <packageSourceMapping>
    <packageSource key="nuget.org">
      <package pattern="*" />
    </packageSource>
    <packageSource key="internal">
      <package pattern="MyCompany.*" />
    </packageSource>
  </packageSourceMapping>
</configuration>
```

一旦存在 `packageSourceMapping`，包括传递包在内的每个包都必须匹配某个模式，无法映射的包会在还原时响亮地失败，而不是悄悄去公共源拿。两个注意点：上面的 `*` 通配符让 nuget.org 成为兜底，只想匹配 `*` 的包也能通过——想让它对未识别 ID 失败，就把真实前缀显式映射并去掉通配；另外包已在全局包缓存中时映射会被跳过，官方文档为此建议声明仓库本地的包目录。

### 护栏 4：读依赖 diff

这是唯一不能自动化的一步，也短到没有借口跳过。审查代理写的代码时，**先读 `Directory.Packages.props` 和任何 `.csproj` 变更，再看逻辑**。新包是带着多年尾巴的决定；一个写错的 if 是一分钟修掉的 bug。两者该得到的审查注意力差得很远，而人的本能恰好给反了。

遇到意外时这两条命令值得记住：

```bash
dotnet nuget why <project> <package>   # 它为什么在我的依赖图里
dotnet package list --vulnerable --include-transitive
```

`dotnet nuget why` 回答了以前要在 Solution Explorer 里点十分钟的问题，也是查「代理加的一个看着无害的包装进来十一个依赖」的最快方法。

## 我实际怎么用（分层）

不是每个项目都需要全部四道护栏：

- **个人项目或原型**：决定写进指令文件就行，爆炸半径是我自己。
- **有团队或客户的项目**：加中央包管理与 NU1903/NU1904 警告转错误——约十五分钟配置，覆盖两个真正花钱的失败模式：没人注意到的许可变化、带着已知通告上生产的包。
- **有私有源的**：才加包源映射。没有私有源就没有值得这个配置成本的依赖混淆风险。
- **NuGet MCP Server**：处处都开。没发现不良反应，而且它把一整类错误答案挡在前面，而不是事后发现。

## 排错：第一次开启会碰到的六件事

1. **NU1008**：启用了中央包管理但 `.csproj` 里还写着 `Version`。把 `Version` 从 `PackageReference` 上移除，在 `Directory.Packages.props` 加对应 `PackageVersion`；`PrivateAssets`、`IncludeAssets` 等保留在 PackageReference 上。
2. **NU1507**：配置了多个包源。中央包管理对多个源的歧义发出警告——这正是依赖混淆可利用的。加包源映射，或删到只剩一个源。这是护栏 3 两半互相指着对方。
3. **NU1109**：开了传递钉住，却把某包钉到比依赖要求的版本更低。钉住不允许降级，升级父包或钉更高。
4. **修不了的 NU1903**：通告真实、构建失败、又没有已修补版本。最后手段是 `NuGetAuditSuppress` 加通告 URL——它是全局抑制而不是只针对一个包，请当作一个带日期的决定，而不是修复：
   ```xml
   <ItemGroup>
     <NuGetAuditSuppress Include="https://github.com/advisories/GHSA-xxxx-xxxx-xxxx" />
   </ItemGroup>
   ```
5. **dnx 未被识别**：NuGet MCP Server 经 `dnx` 运行，它随 .NET 10 SDK 提供。先 `dotnet --info` 查 SDK 版本；GitHub Actions 里给 Copilot 编码代理跑它，也需要安装 .NET 10 的 setup 步骤。
6. **还原对从未引用的包失败**：`packageSourceMapping` 一旦存在，所有传递包都要匹配模式。用 `dotnet nuget why <project> <package>` 找到哪个顶层依赖把它带进来，然后映射其前缀。

## 十五分钟，从今天开始

这份清单里让人不舒服的部分是：**它其实跟 AI 无关。** 这些护栏本来就是一个 .NET 团队早该有的。代理没有制造许可动荡、幻觉包名或「给框架已有能力装库」的习惯，它只是提高了速度与音量，把一个慢动作问题变成你不得不面对的问题。

好的一面是修复都便宜、都一次性：十五分钟的 `Directory.Build.props` 与 `Directory.Packages.props` 覆盖真正花钱的失败模式；NuGet MCP Server 约两分钟；把库决定写进指令文件需要的时间就是决定它们的时间——反正你早晚要做。

真正无法自动化的是「要不要加这个依赖」的判断，它保持在你手里，并值得捍卫。想做个五分钟版？对你最不高兴移除的三个包跑一次 `dotnet nuget why`，然后核对它们**今天**的许可，而不是当初添加时的。

Aide Hub 会继续分享 AI 助手、开发工具与软件工程实践中的具体做法。

## 参考

- [codewithmukesh：Stop Your AI Agent Picking the Wrong .NET Libraries](https://codewithmukesh.com/blog/ai-agent-nuget-package-guardrails-dotnet/)
- [Microsoft Learn：Using the NuGet Model Context Protocol (MCP) Server](https://learn.microsoft.com/en-us/nuget/concepts/nuget-mcp-server)
- [USENIX Security 2025：We Have a Package for You!（包幻觉研究，arXiv:2406.10279）](https://arxiv.org/abs/2406.10279)
- [Polly：Introducing the Open Source Maintenance Fee for Polly](https://thepollyproject.org/2026/07/14/polly-osmf-announcement.html)
- [Microsoft Learn：.NET 10 SDK 起 dotnet restore 审计传递包](https://learn.microsoft.com/en-us/dotnet/core/compatibility/sdk/10.0/nugetaudit-transitive-packages)
- [GitHub：AwesomeAssertions（FluentAssertions v7 社区分支）](https://github.com/AwesomeAssertions/AwesomeAssertions)
- [GitHub Advisory：GHSA-rvv3-g6hj-g44x（AutoMapper）](https://github.com/advisories/GHSA-rvv3-g6hj-g44x)
