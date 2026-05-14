---
pubDatetime: 2026-05-14T10:00:00+08:00
title: ".NET 11 Process API 全面升级：一行代码告别死锁，苹果 Silicon 快 98 倍"
description: ".NET 11 对 System.Diagnostics.Process 进行多年来最大的一次更新，新增一行代码捕获进程输出的高层 API，彻底解决管道死锁问题，同时带来句柄继承控制、进程生命周期管理、NativeAOT 体积缩减以及最高 98 倍的性能提升。"
tags: [".NET", "C#", "Performance"]
slug: "dotnet-11-process-api-improvements"
ogImage: "../../assets/792/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/process-api-improvements-in-dotnet-11"
---

`System.Diagnostics.Process` 是 .NET 里启动和管理进程的核心类，但它一直存在几个让人头疼的问题：读取进程输出容易死锁、句柄继承行为难以控制、进程生命周期管理缺少原生支持。.NET 11 针对这些痛点做了多年来最大的一次更新。

这篇文章是对原文的中文梳理，覆盖所有新 API 和性能改进，按场景分块，让你快速找到自己关心的部分。

![.NET 11 Process API 升级封面：旧方法死锁 vs 新 API 一行搞定]( ../../assets/792/01-cover.png)

## 一张表看清所有新 API

| 功能 | API | 说明 |
|------|-----|------|
| 一行捕获输出 | `Process.RunAndCaptureText[Async]` | 启动进程、捕获 stdout/stderr、等待退出，一个调用搞定 |
| 一行等待退出 | `Process.Run[Async]` | 启动进程并等待退出，不捕获输出 |
| 即发即忘 | `Process.StartAndForget` | 启动进程，返回 PID，立即释放所有资源 |
| 无死锁输出读取 | `Process.ReadAllText/Bytes/Lines[Async]` | 用多路复用同时读取 stdout 和 stderr，避免管道缓冲区死锁 |
| 重定向到任意句柄 | `ProcessStartInfo.Standard[Input/Output/Error]Handle` | 把标准流重定向到文件、管道、null 或任意 `SafeFileHandle` |
| 控制句柄继承 | `ProcessStartInfo.InheritedHandles` | 精确指定子进程继承哪些句柄，防止意外泄漏 |
| 父退子死 | `ProcessStartInfo.KillOnParentExit` | 父进程退出时自动杀死子进程（Windows 和 Linux） |
| 分离进程 | `ProcessStartInfo.StartDetached` | 启动不依赖父进程的独立进程 |
| 轻量进程句柄 | `SafeProcessHandle.Start/WaitForExit/Kill/Signal` | 对裁剪友好的低层 API，不依赖 `Process` 类 |
| 进程退出详情 | `ProcessExitStatus` | 退出码、Unix 终止信号、是否因超时/取消被杀 |
| Null 句柄 | `File.OpenNullHandle()` | 丢弃所有写入，读取返回 EOF |
| 匿名管道 | `SafeFileHandle.CreateAnonymousPipe` | 创建带可选异步支持的连通管道对 |
| 控制台句柄 | `Console.OpenStandard[Input/Output/Error]Handle()` | 获取标准流的底层 OS 句柄 |
| 句柄类型检测 | `SafeFileHandle.Type` | 判断句柄是文件、管道、Socket 等 |

## 捕获进程输出为什么会死锁

管道有有限的缓冲区（Windows 通常 4 KB，Unix 通常 64 KB）。当子进程写入量超过缓冲区容量，且父进程没有同时读取时，子进程会被阻塞在写操作上。

下面这段代码看起来合理，但在输出量较大时会死锁：

```csharp
process.Start();
process.WaitForExit();

string output = process.StandardOutput.ReadToEnd();
string error = process.StandardError.ReadToEnd();
```

调换顺序也没用——`ReadToEnd` 会一直阻塞到流结束（即子进程关闭管道），所以读 stdout 时，没有人在读 stderr；一旦 stderr 把缓冲区写满，双方就互相等待，卡死了。

根本原因是**顺序读取两个流**。.NET 11 之前有两种解法，但都不够简洁：

**方法一：用异步 API 同时读取**

```csharp
process.Start();

Task<string> outputTask = process.StandardOutput.ReadToEndAsync();
Task<string> errorTask = process.StandardError.ReadToEndAsync();

await Task.WhenAll(outputTask, errorTask, process.WaitForExitAsync());

string output = await outputTask;
string error = await errorTask;
```

**方法二：用事件回调**

```csharp
StringBuilder stdOut = new(), stdErr = new();

process.OutputDataReceived += (sender, e) => stdOut.AppendLine(e.Data);
process.ErrorDataReceived += (sender, e) => stdErr.AppendLine(e.Data);

process.Start();
process.BeginOutputReadLine();
process.BeginErrorReadLine();
process.WaitForExit();
```

两种方式都有样板代码，性能也不是最优。

## 新 API：无死锁的输出读取

### ReadAllText 和 ReadAllTextAsync

`.NET 11` 给 `Process` 类加了 `ReadAllText` 和 `ReadAllTextAsync` 方法，在底层同时排空 stdout 和 stderr：

```csharp
public class Process
{
    public (string StandardOutput, string StandardError) ReadAllText(TimeSpan? timeout = default);
    public Task<(string StandardOutput, string StandardError)> ReadAllTextAsync(CancellationToken cancellationToken = default);
}
```

使用方式更直接：

```csharp
ProcessStartInfo startInfo = new("dotnet", "--help")
{
    RedirectStandardOutput = true,
    RedirectStandardError = true
};

using Process process = new() { StartInfo = startInfo };
process.Start();

(string output, string error) = process.ReadAllText();
process.WaitForExit();
```

### RunAndCaptureText：真正的一行代码

如果你只需要捕获输出然后等待进程退出（最常见的场景），`RunAndCaptureText` 把启动、读取、等待打包成一个调用：

```csharp
ProcessTextOutput output = Process.RunAndCaptureText("dotnet", ["--help"]);
```

`ProcessTextOutput` 包含 `StandardOutput`、`StandardError`、`ExitStatus`（含退出码、Unix 信号、是否被取消）和 `ProcessId`。

异步版本同理：

```csharp
ProcessTextOutput output = await Process.RunAndCaptureTextAsync("dotnet", ["--help"]);
```

不关心输出，只需要等待退出的场景用 `Process.Run`：

```csharp
ProcessExitStatus status = Process.Run("dotnet", ["build", "-c", "Release"]);
```

### ReadAllLines：按行读取，区分流

如果你需要逐行区分 stdout 和 stderr，用 `ReadAllLines` 或 `ReadAllLinesAsync`，返回 `ProcessOutputLine` 序列，每条记录携带 `Content` 和 `StandardError` 标志：

```csharp
using Process process = Process.Start("dotnet", "--help")!;
await foreach (ProcessOutputLine line in process.ReadAllLinesAsync())
{
    if (line.StandardError)
        Console.ForegroundColor = ConsoleColor.Red;

    Console.WriteLine(line.Content);
    Console.ResetColor();
}
```

### 超时和取消

所有新的读取方法都支持 `TimeSpan` 超时和 `CancellationToken`。超时或取消时分别抛出 `TimeoutException` 和 `OperationCanceledException`，高层的 `RunAndCaptureText[Async]` 和 `Run[Async]` 还会自动尝试杀死进程，避免留下僵尸进程。

### 底层：多路复用 + ArrayPool

同步的 `RunAndCaptureText` 和 `ReadAll[Bytes/Text]` 在底层用多路复用（Unix 上用 `poll`，Windows 上用 `WaitForMultipleObjects`）单线程同时读取两个流，并配合 `ArrayPool` 减少内存分配。

Windows 基准数据（1000 行输出）：

| 方法 | 均值 | 线程池工作项 | 分配内存 |
|------|------|------|------|
| Events（旧） | 71.21 ms | 2006 | 612.58 KB |
| ReadToEndAsync（旧） | 70.33 ms | 2004 | 636.67 KB |
| RunAndCaptureText（新） | 68.11 ms | — | 132.58 KB |
| RunAndCaptureTextAsync（新） | 70.66 ms | 2004 | 534.09 KB |

同步新方法速度略快，内存分配减少约 4.5 倍，并且完全不占用线程池。Linux 上内存节省 2–4 倍。

## 句柄继承控制

管道 EOF 的触发条件是**所有**指向写端的句柄都关闭。如果并发启动的兄弟进程或孙子进程意外继承了管道句柄，管道就永远不会到达 EOF，造成另一种死锁。

新的 `ProcessStartInfo.InheritedHandles` 属性让你精确控制子进程继承哪些句柄：

```csharp
public class ProcessStartInfo
{
    public IList<SafeHandle>? InheritedHandles { get; set; } = null;
}
```

- `null`（默认）：行为不变，继承所有可继承句柄
- 空列表：只继承标准句柄
- 指定列表：继承标准句柄加上列表中的句柄

Windows 上设置 `InheritedHandles` 后，并发启动多个进程时只需要读锁，不会相互阻塞，吞吐量大约翻倍（benchmark 显示 4.014 s → 1.958 s）。

> **注意**：列表中的句柄不应预先设置为可继承，避免被其他并发启动的进程意外拿到。目前支持 `SafeFileHandle` 和 `SafePipeHandle`。

## 重定向标准句柄

除了 `RedirectStandardOutput` / `RedirectStandardInput` / `RedirectStandardError` 这套布尔开关，.NET 11 加了三个 `SafeFileHandle` 属性，让你把标准流重定向到任意文件句柄：

```csharp
public class ProcessStartInfo
{
    public SafeFileHandle? StandardInputHandle { get; set; }
    public SafeFileHandle? StandardOutputHandle { get; set; }
    public SafeFileHandle? StandardErrorHandle { get; set; }
}
```

配套引入了几个辅助 API：

```csharp
// 创建一对匿名管道（可选异步）
SafeFileHandle.CreateAnonymousPipe(out SafeFileHandle readPipe, out SafeFileHandle writePipe,
    bool asyncRead = false, bool asyncWrite = false);

// 打开 null 句柄：写入丢弃，读取返回 EOF
File.OpenNullHandle();

// 获取控制台标准流的 OS 句柄
Console.OpenStandardInputHandle();
Console.OpenStandardOutputHandle();
Console.OpenStandardErrorHandle();
```

用 C# 实现 `ls /usr/bin | grep zip > output.txt` 的等价操作：

```csharp
SafeFileHandle.CreateAnonymousPipe(out SafeFileHandle readPipe, out SafeFileHandle writePipe);

using (readPipe)
using (writePipe)
using (SafeFileHandle outputFile = File.OpenHandle("output.txt", FileMode.Create, FileAccess.Write))
{
    ProcessStartInfo producer = new("ls", ["/usr/bin"])
    {
        StandardOutputHandle = writePipe
    };

    ProcessStartInfo consumer = new("grep", ["zip"])
    {
        StandardInputHandle = readPipe,
        StandardOutputHandle = outputFile,
    };

    using Process producerProcess = Process.Start(producer)!;
    writePipe.Dispose(); // 释放父进程的写端，让 grep 能感知到 EOF

    using Process consumerProcess = Process.Start(consumer)!;
    readPipe.Dispose();

    await producerProcess.WaitForExitAsync();
    await consumerProcess.WaitForExitAsync();
}
```

`SafeFileHandle` 还新增了：

- `Type` 属性（`FileHandleType` 枚举）：判断句柄是普通文件、管道、Socket、字符设备等
- `IsAsync`：Unix 上检查是否设置了 `O_NONBLOCK`
- `RandomAccess` 的读写方法现在支持管道等不可寻址句柄

## 进程生命周期管理

### StartAndForget：即发即忘

`Process.Dispose` 不会杀死进程，只释放相关资源。`StartAndForget` 明确表达了"我不关心这个进程"的意图：

```csharp
int processId = Process.StartAndForget("notepad.exe");
```

### KillOnParentExit：父退子死

子进程在父进程退出后默认继续存活。`KillOnParentExit` 改变这个行为（支持 Windows 和 Linux/Android）：

```csharp
public class ProcessStartInfo
{
    [SupportedOSPlatform("windows")]  // .NET 11 Preview 4
    [SupportedOSPlatform("linux")]    // .NET 11 Preview 5
    [SupportedOSPlatform("android")]  // .NET 11 Preview 5
    public bool KillOnParentExit { get; set; }
}
```

- **Windows**：通过 Job Object 的 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 实现，孙子进程同样会被终止
- **Linux/Android**：通过 `PR_SET_PDEATHSIG` 发送 `SIGKILL`，.NET 运行时维护一个专用线程来确保行为正确

### StartDetached：彻底脱离父进程

`StartDetached = true` 让子进程在父进程退出、收到信号或终端关闭后仍然存活：

```csharp
public class ProcessStartInfo
{
    public bool StartDetached { get; set; }
}
```

Windows 内部使用 `DETACHED_PROCESS` 标志，Unix 使用 `setsid`。开启后如未指定标准句柄重定向，会自动把标准流重定向到 null 句柄，避免父进程句柄被意外保持打开。

## SafeProcessHandle：对裁剪友好的低层 API

当你需要绕过 `Process` 类（例如需要 P/Invoke `CreateProcessAsUser` 或自定义 `posix_spawn`）时，`SafeProcessHandle` 现在提供了一套完整的操作 API：

```csharp
public class SafeProcessHandle : SafeHandle
{
    public int ProcessId { get; }
    public void Kill();
    public bool Signal(PosixSignal signal);
    public static SafeProcessHandle Start(ProcessStartInfo startInfo);
    public bool TryWaitForExit(TimeSpan timeout, out ProcessExitStatus? exitStatus);
    public ProcessExitStatus WaitForExit();
    public Task<ProcessExitStatus> WaitForExitAsync(CancellationToken cancellationToken = default);
    public Task<ProcessExitStatus> WaitForExitOrKillOnCancellationAsync(CancellationToken cancellationToken);
    public ProcessExitStatus WaitForExitOrKillOnTimeout(TimeSpan timeout);
}
```

示例——先发 SIGTERM 等待，超时再 SIGKILL：

```csharp
[UnsupportedOSPlatform("windows")]
ProcessExitStatus TerminateProcess(Process process)
{
    process.SafeHandle.Signal(PosixSignal.SIGTERM);
    if (process.SafeHandle.TryWaitForExit(TimeSpan.FromSeconds(3), out ProcessExitStatus? exitStatus))
    {
        return exitStatus;
    }

    process.SafeHandle.Signal(PosixSignal.SIGKILL);
    return process.SafeHandle.WaitForExit();
}
```

或者超时自动杀死：

```csharp
using SafeProcessHandle processHandle = SafeProcessHandle.Start(new ProcessStartInfo("myapp.exe"));
ProcessExitStatus exitStatus = processHandle.WaitForExitOrKillOnTimeout(TimeSpan.FromMinutes(1));
if (exitStatus.Canceled)
{
    Console.WriteLine("The process was killed after timeout.");
}
```

### NativeAOT 体积比较

| 类型 | .NET 版本 | OS | 体积（字节） | vs .NET 10 Process |
|------|----------|-----|------|------|
| Process | .NET 10 | Windows x64 | 1,730,048 | baseline |
| Process | .NET 11 | Windows x64 | 1,389,056 | **-19.7%** |
| SafeProcessHandle | .NET 11 | Windows x64 | 1,178,624 | **-31.9%** |
| Process | .NET 10 | Linux x64 | 2,113,808 | baseline |
| Process | .NET 11 | Linux x64 | 2,043,768 | **-3.3%** |
| SafeProcessHandle | .NET 11 | Linux x64 | 1,816,504 | **-14.1%** |

## 值得关注的性能改进

### Windows 并发启动可扩展性提升 1.8x

`BeginOutputReadLine` / `BeginErrorReadLine` 过去会在每个进程上阻塞两个线程池线程。.NET 11 中，Windows 上的匿名管道用具名管道实现，读端以异步 IO 打开，写端以同步 IO 打开，彻底消除了线程池阻塞。

300 个进程并发启动（每个输出 1000 行）的对比：

| Runtime | 均值 | 比值 |
|---------|------|------|
| .NET 10 | 5.307 s | 1.00 |
| .NET 11 | 2.936 s | 0.57 |

### Apple Silicon 进程启动快 98 倍

实现 `InheritedHandles` 促使苹果平台从 `fork` + `exec` 切换到 `posix_spawn`，带来了意外的性能红利：

| 方法 | 工具链 | 均值 | 比值 |
|------|--------|------|------|
| Start | .NET 11 (posix_spawn) | 122.0 μs | 1.00 |
| Start | .NET 10 (fork+exec) | 12,043.2 μs | **98.86x** |
| StartAndWaitForExit | .NET 11 | 1,246.5 μs | 1.00 |
| StartAndWaitForExit | .NET 10 | 8,945.9 μs | **7.18x** |

（Apple M4，macOS Sequoia 15.4.1）

### Unix 内存分配减少 30–50%

Apple M2 上的测试数据：

| 方法 | .NET 11 分配 | .NET 10 分配 | 比值 |
|------|------|------|------|
| StartAndWaitForExit | 15.83 KB | 23.92 KB | **-34%** |
| Start | 15.83 KB | 23.98 KB | **-34%** |

## 小结

.NET 11 的 Process API 更新解决了几个长期存在的实际问题：

- **死锁**：`RunAndCaptureText` 系列方法在底层做了正确的事，不需要开发者自己协调异步任务
- **句柄泄漏**：`InheritedHandles` 让你精确控制哪些句柄传给子进程
- **生命周期管理**：`KillOnParentExit`、`StartDetached`、`StartAndForget` 覆盖了常见场景
- **性能**：Apple Silicon 快 98 倍、Windows 并发提升 1.8 倍、Unix 内存减少 30–50%
- **裁剪**：`SafeProcessHandle` 是 NativeAOT 场景下更小的替代选项

所有改进目前已在 **.NET 11 Preview 4/5** 中可用。如果你有反馈或发现问题，可以在 [dotnet/runtime](https://github.com/dotnet/runtime/issues) 提 issue。

## 参考

- [Process API Improvements in .NET 11](https://devblogs.microsoft.com/dotnet/process-api-improvements-in-dotnet-11) — Adam Sitnik, Microsoft .NET Blog
- [.NET 11 Preview 4 发布公告](https://devblogs.microsoft.com/dotnet/dotnet-11-preview-4/)
- [PR: Process.ReadAllText](https://github.com/dotnet/runtime/pull/126942)
- [PR: Process.RunAndCaptureText](https://github.com/dotnet/runtime/pull/127210)
- [PR: ProcessStartInfo.InheritedHandles](https://github.com/dotnet/runtime/pull/126318)
- [PR: ProcessStartInfo.KillOnParentExit (Windows)](https://github.com/dotnet/runtime/pull/126699)
- [PR: Apple Silicon posix_spawn](https://github.com/dotnet/runtime/pull/126063)
