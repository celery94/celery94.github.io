---
pubDatetime: 2026-09-14T08:31:00+08:00
title: ".NET 11 RC1：亮点核对与 API 纠错"
description: "容器、DNS、崩溃报告、C# 15 union、WinForms kiosk：一篇 .NET 11 RC1 亮点文章里的每个特性，我都对着官方发布说明核了一遍。哪些是真的、哪些代码写错了、正确用法是什么，以及原文漏掉的开关与参数。"
tags: [".NET 11", "C# 15", "WinForms", "Cloud Native", "C#"]
slug: "dotnet-11-rc1-feature-check"
ogImage: "../../assets/1067/01-cover.jpg"
source: "https://www.gapvelocity.ai/blog/the-stuff-in-dotnet-11-that-i-think-is-interesting"
---

DeeDee Walsh 在 [The Stuff in .NET 11 That I Think is Interesting](https://www.gapvelocity.ai/blog/the-stuff-in-dotnet-11-that-i-think-is-interesting) 里挑的四个方向都很准：Linux 容器的暗角、用联合类型替掉企业代码里的继承仪式、CI 构建的浪费、以及 WinForms 的 kiosk 场景。这些确实是 .NET 11 RC 1（2026 年 9 月 8 日发布）的重点。

问题出在示例代码上。我照着官方文档和 release notes 把每一条核了一遍：**特性本身基本都真实存在，但两段 C# 示例的 API 是编的，那段崩溃报告输出也不是真实格式**。对准备升级的人来说，这个差别很关键——照抄示例会编译不过。下面按「先给结论 → 逐条核对 → 正确的用法」组织，顺带补上原文漏掉的开关和参数。

## 先给结论

| 原文的说法                                     | 核实结果                                         |
| ---------------------------------------------- | ------------------------------------------------ |
| Linux 上原生 DNS 记录解析                      | 真实，但 API 名字和用法要补全                    |
| Unix 上的进程内崩溃报告                        | 真实，但输出不是原文那种格式，且需要环境变量开启 |
| 进程信号与终止状态检查                         | 真实，原文没给出任何 API 名字                    |
| C# 15 unions + `System.Text.Json` 封闭类型多态 | 真实，但原文的 `union` 语法不是文档化的写法      |
| SDK 容器发布跳过重复层                         | 真实，但机制不是「digest-aware layer matching」  |
| MSBuild 原生 tar 任务                          | 真实，在 MSBuild 的 release notes 里             |
| `dotnet pack` 复用项目求值                     | 真实，在 NuGet 的 release notes 里               |
| WinForms kiosk 模式                            | 真实，但原文那段代码里的 API 完全不存在          |

八条里七条方向正确，这就是为什么值得单独写一篇来纠偏：错的不是判断，是可执行的细节。

## C# 15 union：方向对，语法不对

原文用这种写法举例：

```csharp
// 原文的写法
public union TransactionStatus
{
    Approved(string AuthorizationCode, decimal SettledAmount),
    Declined(string DeclineReason, bool IsRetryable),
    PendingReview(string CaseId)
}
```

C# 15 的 union 不是这个语法。case 类型要先各自声明，再在 union 声明里按位置列出来（[What's new in C# 15](https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-15)）：

```csharp
public record class Approved(string AuthorizationCode, decimal SettledAmount);
public record class Declined(string DeclineReason, bool IsRetryable);
public record class PendingReview(string CaseId);

public union TransactionStatus(Approved, Declined, PendingReview);
```

union 提供从每个 case 类型的隐式转换，并且编译器会检查 `switch` 是否覆盖了全部 case 类型。原文想要的那种「在 union 块里内联声明 case」的写法，在规范里不存在。

比 union 更贴近原文论点的是 C# 15 同时引入的 `closed` 修饰符。它才是真正把「类型集合在编译期固定」写进语言的那个特性：

```csharp
public closed record class GateState;
public record class Closed : GateState;
public record class Open(float Percent) : GateState;

string Describe(GateState state) => state switch
{
    Closed => "closed",
    Open(var percent) => $"{percent}% open",
    // 不需要 default 分支：GateState 的全部直接派生类型都已覆盖
};
```

`closed` 类只能在声明程序集内部被继承，直接派生类型的集合因此在编译期固定；它隐含 `abstract`，不能与 `sealed`、`static` 或显式 `abstract` 组合。注意派生不是传递的：如果某个中间层没标 `closed`，它在别的程序集里仍然可以被继续继承。

`System.Text.Json` 这一侧对得上原文的说法，但机制要准确描述：.NET 11 新增 `JsonSerializerOptions.InferClosedTypePolymorphism`，让序列化器**推断**封闭层级的泛型元数据，从而不必在每个基类型上标 `JsonDerivedType`；也可以只对单个层级开启：

```csharp
[JsonPolymorphic(InferClosedTypePolymorphism = true)]
public abstract record Shape;
public sealed record Circle(double Radius) : Shape;
public sealed record Square(double Side) : Shape;
```

显式注册的优先级仍然更高。此外 STJ 现在能直接序列化 C# union（`JsonTypeInfoKind.Union`、`JsonUnionAttribute`、`JsonUnionCaseInfo`、`JsonTypeClassifier`），对对象形状的 case，内置的 `JsonUnionTypeStructuralClassifier` 会按特征属性名挑出当前 case。

需要打折的是原文的这两句：**「零反射开销 / 生成直接分支表」和「彻底封死边界」**。官方文档只说到「不需要逐类型标注即可推断多态元数据」，没有承诺消除反射或改变序列化的安全模型。`$type` 注入确实是历史上的真实风险，但 `InferClosedTypePolymorphism` 解决的是标注负担，不是新增一道安全边界。真正的边界来自语言层的 `closed`——封闭层级不可能从其他程序集冒出新的派生类型。

最后是状态：官方把 union 标为 C# 语言预览特性，运行时侧的 `UnionAttribute` 和 `IUnion` 从 .NET 11 Preview 5 开始提供，规范里仍有部分特性尚未实现。

## WinForms kiosk：特性是真的，代码是编的

这一处最需要注意，因为原文的示例不但编译不过，还把能力说大了：

```csharp
// 原文的写法：这些 API 不存在
kioskWindow.EnableKioskMode(new KioskOptions
{
    SuppressSystemGestures = true,
    PreventTaskSwitching = true,
    RestrictEdgeSwipes = true
});
```

真实的 API 是一个**组件** `KioskModeManager`，通过 `ContainerControl` 属性挂到 `Form` 或 `UserControl` 上，可以放进设计器（[.NET 11 RC 1 的 WinForms release notes](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/winforms.md)）：

```csharp
using System.Windows.Forms;

ApplicationConfiguration.Initialize();

Form form = new() { Text = "Kiosk" };

using KioskModeManager kioskMode = new()
{
    ContainerControl = form,
    ToggleFullScreenKeys = Keys.F11,
    EscapeExitsFullScreen = true,
    TopMostInFullScreen = true,
    AlwaysOn = true,
    MousePointerAutoHideDelay = 3_000,
    FullScreen = true,
};

Application.Run(form);
```

它真正负责的是：保存和恢复窗口状态、全屏时保持置顶、阻止显示器与系统休眠、鼠标空闲一段时间后隐藏指针、以及处理进入和退出全屏的按键。`FullScreen` 支持数据绑定，`FullScreenChanged` 报告状态切换，`ToggleFullScreen()` 直接切换。

它**不**负责原文说的那些事：没有抑制系统手势、没有阻止 Alt+Tab、没有边界滑动手势限制。如果你的 kiosk 场景需要真正的操作系统级锁定，仍然得靠组策略、shell 替换或 Windows 的 assigned access，`KioskModeManager` 解决的是全屏应用自己的生命周期问题。

顺带说一句原文提到但没展开的：.NET 11 的现代视觉样式在 RC 1 稳定下来，这一轮修的是 `ComboBox` 的禁用色、下拉按钮颜色与文本布局，以及 `FlatStyle.System` 的设计时渲染、切换开关样式的 `CheckBox`/`RadioButton` 透明背景。原文用「modern visual styles for Windows Forms」一句带过，实际上它的内容比 kiosk 更接近日常可见的变化。

## 崩溃报告：别期待那段 `[CrashReport]` 输出

原文给了一段这样的示例输出：

```text
[CrashReport] Unhandled Fatal Exception: SIGSEGV (Address: 0x00007f9b4c00) ...
```

官方文档描述的机制不是这个形状。进程内崩溃报告会在进程终止前，把**托管栈跟踪、模块列表和关键运行时状态写到一个约定路径**，它取代的是此前由进程外监视器收集诊断的方式；因为很多东西只存在于垂死的进程内部，进程外收集会漏掉。这个能力最早来自移动平台，现在 Linux 和 macOS 也可用（[.NET 11 运行时文档](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/runtime.md)）。

真正需要记住的是开关，而原文完全没提：

```bash
# 未启用 DOTNET_DbgEnableMiniDump 时，用这两个环境变量选择进程内报告器
DOTNET_EnableCrashReport=1
# 或者只报告、不生成转储
DOTNET_EnableCrashReportOnly=1
```

启用 minidump 时仍然走原来的 `createdump` 路径。

对容器场景来说，「写到约定路径」其实比「打到 stderr」更合理：路径可以挂到临时卷上由 sidecar 收集，而 stderr 会被日志聚合器按行切碎，一份多行崩溃报告在里面很难读。原文担心的「pod 因为写转储被驱逐」也是真实问题——所以才有只报告不转储的选项，这一点原文没利用上。

## 容器与构建：原文漏掉的开关

原文把容器发布的改进描述成「digest-aware layer matching」，官方叫法是可复现发布加跳过冗余上传，机制有两层：

第一层是可复现：[设置 `SOURCE_DATE_EPOCH`](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/sdk.md) 为稳定的 Unix 时间戳，让相同输入的两次发布产出相同的镜像 digest。此前时间戳、归档头和目录枚举顺序在不同构建之间会变，digest 因此不稳定。

```bash
dotnet publish /t:PublishContainer \
  -p:ContainerRegistry=registry.example.com \
  -p:SOURCE_DATE_EPOCH="$(git log -1 --pretty=%ct)"
```

第二层才是省时间的那部分：远程推送前会检查计算出的镜像 manifest 是否已存在于目标仓库，存在则跳过 layer 与 config 的处理，但仍然应用所有请求的 tag。这个优化默认开启，用 `ContainerPushNoCache=true` 可以绕过；此外 SDK 仍会逐个检查 layer 和 config blob，已经存在的不重复上传。

另外两条原文列在表格里但没说清出处的，其实分属两个仓库：

- **MSBuild 新增创建和解压 tar 归档**——在 [MSBuild 的 release notes](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/msbuild.md) 里，同一批还有「向构建工具暴露 item glob 模式」。原文说的「不用再 shell 出去调 tar/7z」正是它的用途。
- **`dotnet pack` 复用已有项目求值**——在 [NuGet 的 release notes](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/nuget.md) 里，不是 SDK 的。原文说「50+ 项目的解决方案里每次 pack 都会重复求值项目图」是对的，但如果你按 SDK 去翻文档会找不到。

## DNS 与进程：把 API 名字补全

原文这两节的判断都对，只是没给出任何可以查的东西。补上：

**DNS 记录解析**（[libraries release notes](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/libraries.md)）：`System.Net.Dns` 增加了带类型的记录解析方法 `ResolveSrv`、`ResolveMx`、`ResolveTxt`、`ResolveCName`、`ResolvePtr`、`ResolveNs`，以及对应的 `Async` 版本；结果通过 `DnsResult<T>` 返回，包含记录、响应码和负缓存 TTL 元数据。新增的 `DnsResolver` 类提供同样的记录类型，但接受 `DnsResolverOptions`，可以指定自定义 DNS 服务器列表，而不是只用平台解析器配置。

原文说「原生解析」和「绕开操作系统解析器的怪癖」，落点就在最后这句：能自己指定 DNS 服务器。而真正值得强调的变化是——`DnsResolver` 和静态 `Dns.Resolve*` 方法**现在在 Linux 上也能用**，此前只有 Windows 和 macOS。

**进程信号与终止状态**：`Process` 直接暴露了信号与退出状态 API，不必再走 `SafeProcessHandle`。具体是 `Process.Signal(PosixSignal)` 发送 POSIX 信号，以及 `WaitForExitStatus`、`TryWaitForExitStatus(TimeSpan, out ProcessExitStatus)`、`WaitForExitStatusAsync(CancellationToken)` 返回 `ProcessExitStatus`——它区分正常退出和信号终止。原文说的「不再靠解析退出码猜是优雅退出还是被 kill」指的就是这个类型。

同一批改动里还有一批原文完全没提、但可能更常用的辅助方法：`Process.Run*` / `RunAsync*`、`RunAndCaptureText*` / `RunAndCaptureTextAsync*`、`ReadAllText` / `ReadAllBytes` / `ReadAllLines`（返回 `ProcessOutputLine`，能区分 stdout 与 stderr）、`StartAndForget*`，以及 `ProcessStartInfo.StartDetached`。以前要手接 `OutputDataReceived` 事件或写 P/Invoke 的场景，现在是一行。

## 升级前注意三件事

- RC 1 带 go-live 支持许可，可以在生产试用，但它是 RC 不是正式版。
- 检查 breaking changes。WinForms 这一轮移除了预览版才有的 `TreeView.NodeLeading` 属性、`NodeLeadingChanged` 事件和受保护的 `OnNodeLeadingChanged` 方法；针对 .NET 11 预览版编译过的代码必须先去干净。需要显式节点高度时改用 `TreeView.ItemHeight`。
- union、`closed` 属于 C# 15 的预览特性，需要 .NET 11 的 SDK；内存安全那一组改动还要显式把 `LangVersion` 设为 `preview` 并开启相应编译器特性。

版本预览期的文章难免有偏差，但代码示例的偏差代价最高——它会让人照抄一遍再回来找问题。Aide Hub 会继续在 .NET 与 C# 的新版本发布时做这类逐条核对，把「哪些是真的」和「正确写法是什么」分开写清楚。如果你在升级 .NET 11 时踩到本文没覆盖的坑，欢迎发来补充。

## 参考

- [The Stuff in .NET 11 That I Think is Interesting](https://www.gapvelocity.ai/blog/the-stuff-in-dotnet-11-that-i-think-is-interesting)（原文，DeeDee Walsh）
- [Announcing .NET 11 Release Candidate 1](https://devblogs.microsoft.com/dotnet/dotnet-11-rc-1/)
- [.NET 11 RC 1 release notes：libraries](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/libraries.md)
- [.NET 11 RC 1 release notes：runtime](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/runtime.md)
- [.NET 11 RC 1 release notes：SDK](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/sdk.md)
- [.NET 11 RC 1 release notes：WinForms](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/rc1/winforms.md)
- [What's new in C# 15](https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-15)
