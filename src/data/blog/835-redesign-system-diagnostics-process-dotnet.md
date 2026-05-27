---
title: "重新设计 System.Diagnostics.Process：用类型系统消除「只有启动者才能用」的陷阱"
description: "Raymond Chen 提出了一种 System.Diagnostics.Process 的假想重构方案：把 StandardOutput 等属性移到 Start() 的返回类型里，用编译器替代运行时异常来守护 API 正确使用顺序。.NET 11 也正在落实类似思路。"
pubDatetime: 2026-05-27T08:43:00+08:00
modDatetime: 2026-05-27T08:43:00+08:00
slug: redesign-system-diagnostics-process-dotnet
featured: false
draft: false
tags:
  - CSharp
  - dotnet
  - API Design
  - Process
ogImage: ../../assets/835/01-cover.png
---

## 目录

## 引言

如果你写过 C# 的进程管理代码，一定遇到过 `Process.StandardOutput` 这个"甜蜜陷阱"——它在所有 `Process` 实例上都可见，但只在**你自己调了 `Start()` 并且打开了输出重定向**的情况下才能用。一旦条件不满足，就会在运行时扔出 `InvalidOperationException`。

Raymond Chen 最近在 [The Old New Thing](https://devblogs.microsoft.com/oldnewthing/20260525-00/?p=112351) 上发表了一篇文章，提出了一种假想重构方案来根治这个问题。他的核心原则只有一句话：

> **要强制开发者按顺序做事，就让第二步依赖第一步产出的东西。**

这个思路简单得近乎常识，但放在 `Process` 类的背景下却格外有启发性——因为 .NET 团队实际上正在为 .NET 11 [重新设计这个 API](https://github.com/dotnet/runtime/issues/125838)。

## 问题出在哪里？

`System.Diagnostics.Process` 有两种获取方式：

1. **你自己 `Start()` 一个新进程**——此时你拥有标准句柄的所有权。
2. **通过 `GetProcessById()` 或 `GetProcesses()` 拿到别人已在跑的进程**——你只能查看进程信息（名称、PID、内存占用等），但无法读写标准句柄。

可惜，这两种场景共用同一个 `Process` 类。`StandardOutput`、`StandardError`、`StandardInput`、`BeginOutputReadLine()`、`OutputDataReceived` 等成员在任何实例上都**可见**，编译器不会报任何错，只有运行时才会告诉你"用错了"。

```csharp
// 这段代码编译毫无问题，运行时才炸
var proc = Process.GetProcessesByName("notepad")[0];
string output = proc.StandardOutput.ReadToEnd(); // 💥 InvalidOperationException
```

这就是 Raymond Chen 所说的 **attractive nuisance**（诱人的陷阱）。

## 假想重构方案

### 第一步：拆分类型

Raymond Chen 提出引入一个新类型 `ProcessStartResult`，让 `Start()` 返回它而不是直接返回 `Process`：

```csharp
public class ProcessStartResult
{
    public Process Process { get; }

    // 只有启动者才需要的属性
    public StreamWriter StandardInput { get; }
    public StreamReader StandardOutput { get; }
    public StreamReader StandardError { get; }

    // 异步读取
    public void BeginOutputReadLine();
    public void BeginErrorReadLine();
    public void CancelOutputRead();
    public void CancelErrorRead();

    // 事件
    public event DataReceivedEventHandler OutputDataReceived;
    public event DataReceivedEventHandler ErrorDataReceived;
}
```

调用方式变成：

```csharp
var result = Process.Start(startInfo);
var process = result.Process;          // 拿到 Process 引用
string output = result.StandardOutput.ReadToEnd(); // ✅ 类型安全
```

如果你是通过 `GetProcessById()` 拿到的 `Process`，根本**看不到** `StandardOutput` 这个属性——因为它不在 `Process` 类上了。

### 第二步：移除 StartInfo 属性

`Process` 类上还有一个 `StartInfo` 属性。它在已启动的进程上没有实际作用——修改它不会影响已在运行的进程。这个属性存在的唯一原因是一种"先配置再启动"的编程风格：

```csharp
// 旧 API 的风格
var proc = new Process();
proc.StartInfo.FileName = "cmd.exe";
proc.StartInfo.Arguments = "/c dir";
proc.Start();
```

在重构后，只需直接使用 `ProcessStartInfo` 对象即可：

```csharp
var startInfo = new ProcessStartInfo("cmd.exe", "/c dir");
var result = Process.Start(startInfo);
```

`StartInfo` 属性从 `Process` 类上消失，因为它对已启动的进程毫无意义。

## 设计原则提炼

整个重构背后是一条通用的 API 设计原则：

| 问题模式                      | 解法                                   |
| ----------------------------- | -------------------------------------- |
| 属性 / 方法只在特定条件下有效 | 把它们移到只有满足条件才能获得的类型上 |
| "先做 A 再做 B" 的顺序约束    | 让 B 所需的上下文由 A 的返回值提供     |

在这个案例中：

- **条件** = 你是进程的启动者
- **满足条件才能获得的类型** = `ProcessStartResult`
- **A** = `Process.Start()`
- **B 所需的上下文** = `StandardOutput` 等句柄

这样，编译器就能在**编译期**帮你拦住错误，而不是等到运行时才告诉你。

## .NET 11 的真实进展

值得注意的是，这不仅仅是一个思想实验。.NET 团队已经在 [dotnet/runtime#125838](https://github.com/dotnet/runtime/issues/125838) 中开始了对 `Process` API 的重新设计工作，目标是 .NET 11。虽然最终方案可能与 Raymond Chen 的假想设计有所不同，但核心思路——**把只有启动者才能用的成员从 Process 类中分离出来**——是一致的。

这说明社区和官方团队对这个问题的认知已经趋于统一：`Process` 类承担了太多职责，是时候拆分了。

## 总结

`System.Diagnostics.Process` 的设计问题在于**一个类型承载了两种身份**——进程信息查看者和进程启动者——而只有后者才需要标准句柄等功能。Raymond Chen 的重构方案用一个简单的类型拆分就解决了这个问题：让 `Start()` 返回 `ProcessStartResult`，把标准句柄放在里面。

下次你在设计 API 时遇到"这个方法只有在某种条件下才有效"的情况，不妨试试同样的思路：**不要用运行时异常来守护前置条件，让类型系统替你工作。**

## 参考资料

- [Raymond Chen - If I could redesign System.Diagnostics.Process](https://devblogs.microsoft.com/oldnewthing/20260525-00/?p=112351)
- [dotnet/runtime#125838 - Process API Redesign](https://github.com/dotnet/runtime/issues/125838)
