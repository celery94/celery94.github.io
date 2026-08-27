---
pubDatetime: 2026-08-27T08:24:09+08:00
title: "C# 获取机器逻辑处理器总数"
description: "在 .NET 中获取机器处理器数量时，Environment.ProcessorCount 代表当前进程可用资源，不等于主机总数。本文用 Windows、macOS、Linux 示例说明原生 API与容器边界。"
tags: ["C#", ".NET", "Performance", "Runtime", "Interop"]
slug: "dotnet-total-processor-count"
ogImage: "../../assets/1030/01-cover.jpg"
source: "https://andrewlock.net/finding-the-total-number-of-processors-on-a-machine-with-dotnet/"
---

在 .NET 中看到“处理器数量”时，最容易想到的是：

```csharp
var workerCount = Environment.ProcessorCount;
```

这行代码很适合估算当前进程可以使用的并行资源。可当问题变成“这台机器有多少个逻辑处理器”时，它可能给出另一种答案：进程亲和性、容器 CPU 限制和运行时策略都会影响返回值。

Andrew Lock 的[原文《Finding the total number of processors on a machine with .NET》](https://andrewlock.net/finding-the-total-number-of-processors-on-a-machine-with-dotnet/)围绕这个语义差异，分别讨论 Windows、macOS 和 Linux 的系统级查询。本文沿着这条主线整理一套可以运行的 .NET 6+ 示例，并补上几个实际开发中很容易遗漏的边界：

- 当前进程可调度的处理器数量，与操作系统报告的活动/在线逻辑处理器总数分开处理；
- Windows 需要查询所有 processor groups；
- Linux 的 /sys/devices/system/cpu/online 返回 CPU 列表，需要解析单个编号和闭区间；
- 容器、虚拟机、CPU 配额、热插拔和查询失败都需要明确处理。

## 先定义你要问的“处理器数量”

同一个“数量”可能对应四种不同问题：

| 你真正想知道的内容                  | 推荐入口                         | 返回值的含义                                                      |
| ----------------------------------- | -------------------------------- | ----------------------------------------------------------------- |
| 当前进程可以使用多少处理器          | Environment.ProcessorCount       | 运行时根据机器逻辑处理器、进程亲和性和 CPU 限制计算出的进程可用数 |
| 操作系统当前启用了多少逻辑处理器    | Windows、macOS、Linux 的原生入口 | OS 视角下的 active/online logical processors                      |
| 有多少物理核心、Socket 或 NUMA 节点 | 平台拓扑 API                     | 硬件拓扑信息，和逻辑处理器数量属于不同维度                        |
| 容器所在物理主机有多少处理器        | 宿主机代理、云平台或编排系统接口 | 容器内部通常无法可靠推断完整物理主机信息                          |

因此，本文的“机器总数”特指：**当前 OS 视角下处于 active/online 状态的逻辑处理器数量**。它既不代表物理核心数，也不承诺等于容器所在节点的完整 CPU 数量。

## Environment.ProcessorCount 到底返回什么

当前 .NET API 文档对 Environment.ProcessorCount 的定义是：返回当前进程可用的处理器数量。

在 Linux 和 macOS 上，运行时会考虑机器逻辑处理器数量、当前进程的 CPU affinity，以及 CPU 使用率限制。在 Windows 上，.NET 6 及更高版本也采用这套进程可用资源语义。CPU 使用率限制会向上取整到下一个整数。

还有两个时间点需要记住：

1. 这个属性的值在运行时启动时确定；
2. 进程运行期间，CPU affinity 或 CPU 限制发生变化时，属性值不会跟着重新计算。

这套行为对线程池、并行循环和默认并行度很有帮助。它让应用根据“当前进程可以使用的资源”做决策。若监控页面要展示“这台 OS 当前在线的逻辑 CPU 总数”，就应该查询对应平台的系统接口。

> 历史版本的 .NET Core 在容器识别和主机处理器数量方面存在差异。新代码应以目标运行时的官方文档为准，避免把旧版本行为当成今天所有环境的规则。

## 三个平台的查询路径

| 平台    | 查询入口                                      | 关注点                                                       |
| ------- | --------------------------------------------- | ------------------------------------------------------------ |
| Windows | GetActiveProcessorCount(ALL_PROCESSOR_GROUPS) | Windows processor group 可能把逻辑处理器分组，查询单组会漏数 |
| macOS   | sysctlbyname("hw.logicalcpu")                 | 获取当前启用的逻辑处理器核心数                               |
| Linux   | 读取 /sys/devices/system/cpu/online           | 文件内容是 CPU 编号列表，例如 0-3,8                          |

这些 API 的共同点是：它们报告的是平台当前可见的逻辑处理器状态。它们无法直接回答“有多少物理核心”，也不能绕过虚拟机或容器对硬件视图的限制。

## 创建一个最小项目

下面的示例使用 .NET 6+，不需要第三方包：

```powershell
dotnet new console -n HostProcessorCount
cd HostProcessorCount
```

把平台查询代码放入 HostLogicalProcessorCount.cs。

## 完整实现

### 公共结果类型和 Linux CPU 列表解析器

Linux 的 online 文件使用 CPU 列表格式。常见输入包括：

- 0
- 0-7
- 0-3,8,10-11

范围的两端都是包含值，所以 0-3 代表 4 个处理器。下面的解析器只负责计数；它假定输入来自内核提供的合法 CPU 列表，并拒绝空项、反向范围、负数和溢出。

```csharp
using System;
using System.IO;
using System.Runtime.InteropServices;

public enum ProcessorCountSource
{
    Windows,
    MacOS,
    Linux
}

public readonly record struct ProcessorCountReading(
    int Count,
    ProcessorCountSource Source);

public static class LinuxCpuListParser
{
    public static bool TryCount(ReadOnlySpan<char> contents, out int count)
    {
        count = 0;
        var remaining = contents.Trim();

        if (remaining.IsEmpty)
        {
            return false;
        }

        while (true)
        {
            var commaIndex = remaining.IndexOf(',');
            var token = commaIndex >= 0
                ? remaining[..commaIndex]
                : remaining;

            token = token.Trim();

            if (!TryCountToken(token, out var tokenCount) ||
                tokenCount > int.MaxValue - count)
            {
                count = 0;
                return false;
            }

            count += tokenCount;

            if (commaIndex < 0)
            {
                return count > 0;
            }

            remaining = remaining[(commaIndex + 1)..].TrimStart();

            if (remaining.IsEmpty)
            {
                count = 0;
                return false;
            }
        }
    }

    private static bool TryCountToken(
        ReadOnlySpan<char> token,
        out int count)
    {
        count = 0;

        var dashIndex = token.IndexOf('-');

        if (dashIndex < 0)
        {
            if (!int.TryParse(token, out var cpu) || cpu < 0)
            {
                return false;
            }

            count = 1;
            return true;
        }

        if (token[(dashIndex + 1)..].IndexOf('-') >= 0 ||
            !int.TryParse(token[..dashIndex], out var start) ||
            !int.TryParse(token[(dashIndex + 1)..], out var end) ||
            start < 0 ||
            end < start)
        {
            return false;
        }

        var spanLength = (long)end - start + 1;

        if (spanLength > int.MaxValue)
        {
            return false;
        }

        count = (int)spanLength;
        return true;
    }
}
```

这里有一个值得单独说明的选择：TryCount 返回 false 时把输出重置为 0。调用方因此不会把半个列表解析出来的结果误当成完整答案。

### Windows：查询所有 processor groups

Windows 的 GetActiveProcessorCount 接收一个 processor group 编号。传入 0xFFFF，也就是 ALL_PROCESSOR_GROUPS，即可请求系统中所有组的活动逻辑处理器数量。

Windows processor group 的设计与逻辑处理器调度有关。微软的[Processor Groups 文档](https://learn.microsoft.com/en-us/windows/win32/procthread/processor-groups)说明了逻辑处理器、处理器组和线程调度之间的关系。查询单个组时，高处理器数量机器可能出现结果偏小的问题。

```csharp
internal static class WindowsProcessorCount
{
    private const ushort AllProcessorGroups = 0xFFFF;

    public static bool TryGet(out int count)
    {
        var nativeCount = GetActiveProcessorCount(AllProcessorGroups);

        if (nativeCount == 0 || nativeCount > int.MaxValue)
        {
            count = 0;
            return false;
        }

        count = (int)nativeCount;
        return true;
    }

    [DllImport(
        "kernel32.dll",
        EntryPoint = "GetActiveProcessorCount",
        SetLastError = true)]
    private static extern uint GetActiveProcessorCount(
        ushort groupNumber);
}
```

原生函数返回 0 时表示调用失败。这里把失败保留为 false，调用方可以记录日志、报警或选择明确的降级策略。若需要读取 Windows 的原生错误码，应在 P/Invoke 调用后立即调用 .NET 6+ 的 [Marshal.GetLastPInvokeError](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.marshal.getlastpinvokeerror)。

### macOS：查询 hw.logicalcpu

Apple 的 sysctl 接口提供了系统能力信息。[hw.logicalcpu](https://developer.apple.com/documentation/kernel/1387446-sysctlbyname/determining_system_capabilities?changes=_2)代表当前启用的逻辑处理器核心数；hw.logicalcpu_max 代表系统支持的最大逻辑核心数。

本文要问的是当前 active 数量，所以读取 hw.logicalcpu：

```csharp
internal static class MacOsProcessorCount
{
    public static bool TryGet(out int count)
    {
        nuint size = (nuint)sizeof(int);
        var result = SysctlByName(
            "hw.logicalcpu",
            out var value,
            ref size,
            IntPtr.Zero,
            0);

        if (result != 0 || value <= 0)
        {
            count = 0;
            return false;
        }

        count = value;
        return true;
    }

    [DllImport(
        "libSystem.dylib",
        EntryPoint = "sysctlbyname",
        CharSet = CharSet.Ansi,
        CallingConvention = CallingConvention.Cdecl,
        SetLastError = true)]
    private static extern int SysctlByName(
        string name,
        out int oldp,
        ref nuint oldlenp,
        IntPtr newp,
        nuint newlen);
}
```

这里的 P/Invoke 签名对应 sysctlbyname 的“读取一个整数”用法：传入名称，给出输出缓冲区和缓冲区长度，最后两个参数使用空指针和 0 表示只读取。

如果应用还要展示 Foundation 层的结果，Apple 的 [ProcessInfo.activeProcessorCount](https://developer.apple.com/documentation/foundation/processinfo/activeprocessorcount?changes=la)也与 hw.logicalcpu 对应。保持一个入口即可，避免同一页面混用多个语义相近的字段。

### Linux：读取 online CPU 列表

Linux 内核会在 /sys/devices/system/cpu 下提供 CPU 状态文件。online 文件包含当前在线 CPU 的列表，形式类似 0-3,8-11,14,17。Linux 的 [CPU hotplug 文档](https://docs.kernel.org/5.15/core-api/cpu_hotplug.html)也展示了 online、possible、present 等状态文件之间的区别。

```csharp
internal static class LinuxProcessorCount
{
    private const string OnlineCpuPath =
        "/sys/devices/system/cpu/online";

    public static bool TryGet(out int count)
    {
        try
        {
            var contents = File.ReadAllText(OnlineCpuPath);
            return LinuxCpuListParser.TryCount(
                contents.AsSpan(),
                out count);
        }
        catch (IOException)
        {
            count = 0;
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            count = 0;
            return false;
        }
    }
}
```

这个实现将文件不可读、路径不存在和格式非法统一为失败结果。生产代码可以在 catch 中记录异常类型和路径，排查权限、精简容器镜像或挂载差异。

### 统一的平台分流入口

.NET 提供了按运行时平台判断的 API。先做平台判断，再调用对应的原生入口，避免在错误系统上尝试加载动态库：

```csharp
public static class HostLogicalProcessorCount
{
    public static bool TryGet(
        out ProcessorCountReading reading)
    {
        if (OperatingSystem.IsWindows() &&
            WindowsProcessorCount.TryGet(out var windowsCount))
        {
            reading = new ProcessorCountReading(
                windowsCount,
                ProcessorCountSource.Windows);
            return true;
        }

        if (OperatingSystem.IsMacOS() &&
            MacOsProcessorCount.TryGet(out var macOsCount))
        {
            reading = new ProcessorCountReading(
                macOsCount,
                ProcessorCountSource.MacOS);
            return true;
        }

        if (OperatingSystem.IsLinux() &&
            LinuxProcessorCount.TryGet(out var linuxCount))
        {
            reading = new ProcessorCountReading(
                linuxCount,
                ProcessorCountSource.Linux);
            return true;
        }

        reading = default;
        return false;
    }
}
```

把这些类型放在同一个 HostLogicalProcessorCount.cs 文件中即可。示例没有把失败自动改写成 Environment.ProcessorCount，因为两个值回答的问题不同。需要降级时，应由业务层决定，并在输出中标明实际使用的来源。

## 调用示例与跨平台自测

把下面的代码放入 Program.cs。默认运行会查询当前系统；传入 --parser-test 时，会在任何平台上测试 Linux 列表解析器，不需要 Linux 环境。

```csharp
using System;

internal static class Program
{
    public static int Main(string[] args)
    {
        if (Array.IndexOf(args, "--parser-test") >= 0)
        {
            RunParserTests();
            return 0;
        }

        if (HostLogicalProcessorCount.TryGet(out var reading))
        {
            Console.WriteLine(
                $"Host active/online logical processors: " +
                $"{reading.Count} ({reading.Source})");
            Console.WriteLine(
                $"Current process available processors: " +
                $"{Environment.ProcessorCount}");
            return 0;
        }

        Console.Error.WriteLine(
            "The host processor count could not be read.");
        return 1;
    }

    private static void RunParserTests()
    {
        var validCases = new[]
        {
            (Text: "0", Expected: 1),
            (Text: "0-3", Expected: 4),
            (Text: "0-3,8,10-11", Expected: 7),
            (Text: " 0-1, 4 \n", Expected: 3)
        };

        foreach (var test in validCases)
        {
            if (!LinuxCpuListParser.TryCount(
                    test.Text.AsSpan(),
                    out var actual) ||
                actual != test.Expected)
            {
                throw new InvalidOperationException(
                    $"Unexpected result for '{test.Text}': {actual}");
            }
        }

        var invalidCases = new[]
        {
            "",
            "3-1",
            "0-",
            "0,,1",
            "x"
        };

        foreach (var text in invalidCases)
        {
            if (LinuxCpuListParser.TryCount(
                    text.AsSpan(),
                    out _))
            {
                throw new InvalidOperationException(
                    $"Invalid input was accepted: '{text}'");
            }
        }

        Console.WriteLine("Linux CPU list parser tests passed.");
    }
}
```

运行两个命令：

```powershell
dotnet run -- --parser-test
dotnet run
```

预期结果包括：

- 解析器自测输出 Linux CPU list parser tests passed.；
- 在 Windows 上，默认运行会使用 GetActiveProcessorCount；
- 在 macOS 上，默认运行会使用 hw.logicalcpu；
- 在 Linux 上，默认运行会读取 online 文件；
- 两行输出会同时展示 host active/online 数量与当前进程可用数量。

这两个数字相同并不奇怪。进程没有额外 affinity、当前环境也没有更严格的 CPU 限制时，它们可能刚好一致。代码仍然保留两个来源，因为限制条件一旦出现，语义差异就会影响线程数、监控结果和容量判断。

## 为什么资源监控包不能直接替代

Microsoft.Extensions.Diagnostics.ResourceMonitoring 适合观察 CPU 使用率、内存压力等资源指标。它解决的是“资源用了多少、当前压力如何”这类问题。它的指标并不等价于“操作系统有多少在线逻辑处理器”。

可以按问题选择入口：

- 要计算 worker 数量：优先使用 Environment.ProcessorCount；
- 要展示主机 OS 的 active/online 逻辑处理器：使用本文的平台查询；
- 要展示 CPU 使用率或压力：使用资源监控包；
- 要展示物理拓扑：调用平台拓扑 API 或由主机侧系统提供数据。

把几个数值放到同一个监控面板时，字段名应包含来源和语义，例如 process_available_processors、host_online_logical_processors，避免只写 cpu_count。

## 容器和虚拟机里的边界

### 虚拟机

虚拟机里的 Windows、macOS 或 Linux 原生接口看到的是 guest OS 的处理器视图。它们通常反映虚拟机分配到的 vCPU 数量，不会返回底层物理服务器的完整 CPU 拓扑。

### 容器

容器里的“总数”有几种可能含义：

1. 容器当前可见的在线 CPU；
2. cgroup 允许容器使用的 CPU 集合；
3. CPU quota 换算出的时间预算；
4. 容器所在节点的 CPU 总量。

Linux cgroup v2 的 [cpuset.cpus.effective](https://docs.kernel.org/6.4/admin-guide/cgroup-v2.html)可表达实际授予 cgroup 的 CPU 集合。它和 /sys/devices/system/cpu/online 属于不同视图。CPU quota 也可能只限制时间份额，未必对应一个简单的连续 CPU 编号范围。

因此：

- 应用调度并行工作时，使用 Environment.ProcessorCount；
- 监控容器能看到哪些 online CPU 时，记录查询路径和挂载环境；
- 需要完整节点或物理服务器信息时，从节点代理、云平台或编排系统取得；
- 不要用容器内一个整数去推断物理机器的全部硬件。

## 缓存、热插拔与数据新鲜度

缓存策略取决于你要表达的内容：

- Environment.ProcessorCount 本身就是进程生命周期内的启动快照；
- Windows active processor、Linux online CPU 可能随硬件启停或系统配置变化；
- Linux 内核文档明确区分 online、possible、present 等集合，CPU hotplug 会改变状态；
- 启动诊断信息可以读取一次并缓存；
- 长时间运行的监控指标应按采样周期重新读取，并允许数量变化。

如果读 OS 接口失败，建议返回带状态的结果，例如 Success、Unavailable、InvalidData，同时保留平台和路径信息。简单返回 0 会让调用方误以为系统没有处理器。

示例中的 TryGet 为了保持代码短小只返回布尔值。正式服务可以把结果扩展成：

```text
Count: 16
Source: LinuxOnlineCpuSysfs
Status: Success
ObservedAt: 2026-08-27T00:24:09Z
```

时间戳尤其适合监控系统，因为它能说明这个数字何时被读取。

## P/Invoke 代码的维护要点

本文使用 DllImport，目标是兼容 .NET 6。微软的[P/Invoke 文档](https://learn.microsoft.com/en-us/dotnet/standard/native-interop/pinvoke)介绍了托管代码调用原生函数的基本方式。

如果项目只支持 .NET 7+，可以评估 [LibraryImport](https://learn.microsoft.com/en-us/dotnet/standard/native-interop/pinvoke-source-generation)源代码生成器。它在编译期生成互操作代码，减少运行时生成 IL stub 的工作，也更早暴露一部分签名问题。迁移时仍需逐项核对：

- 原生库名称和入口点；
- 参数宽度，例如 Windows 的 WORD 与 DWORD；
- 指针、长度和结构体布局；
- 字符集与调用约定；
- SetLastError 是否与错误读取方式匹配；
- 平台判断和裁剪/AOT 场景。

对于这样的小型只读查询，正确的原生签名和清晰的失败路径比追求更短的封装更重要。

## 常见问题

### Environment.ProcessorCount 能不能直接当机器总数？

如果你的问题是“当前进程适合开多少并行工作”，可以使用它。如果你的问题是“OS 当前 active/online 了多少逻辑处理器”，应使用平台查询。

### 逻辑处理器和物理核心有什么区别？

逻辑处理器是操作系统调度线程时看到的执行单元。一个物理核心可能对应多个逻辑处理器，也可能因为 BIOS、虚拟机配置或系统策略只启用其中一部分。物理核心、Socket、NUMA 节点需要另外的拓扑查询。

### Windows 为什么要传 0xFFFF？

Windows 使用 processor groups 管理逻辑处理器。传入 ALL_PROCESSOR_GROUPS 会把所有组的活动处理器加总，适合回答整台 Windows OS 的 active logical processor 数量。

### Linux 为什么解析 /sys，不直接调用 sysconf？

sysconf(\_SC_NPROCESSORS_ONLN) 也能查询当前在线处理器。本文选择 /sys，因为 CPU 列表格式直观，且可以保留具体在线编号。若项目已有稳定的 libc 互操作封装，也可以使用 [sysconf 的 \_SC_NPROCESSORS_ONLN 说明](https://www.man7.org/linux/man-pages/man3/sysconf.3.html)。选择一种经过测试的入口即可。

### 能不能把读取结果永久缓存？

启动信息和静态诊断通常可以缓存。需要反映 CPU hotplug、容器配置变化或长期运行状态时，应重新查询。缓存时间也要随业务含义记录下来。

### 原生查询失败时，是否应该回退到 Environment.ProcessorCount？

可以回退，但要把它标为 process-visible fallback，并记录失败原因。两个 API 的语义不同，静默替换会让监控和容量判断失去可解释性。

## 小结

在 .NET 中获取处理器数量，第一步是写清楚“谁能使用这些处理器”：

1. 当前进程的并行度：Environment.ProcessorCount；
2. Windows OS 的活动逻辑处理器：GetActiveProcessorCount(0xFFFF)；
3. macOS 的启用逻辑处理器：sysctlbyname("hw.logicalcpu")；
4. Linux 的在线逻辑处理器：解析 /sys/devices/system/cpu/online；
5. 物理拓扑和容器节点信息：使用相应的平台或主机侧接口；
6. 读取失败、热插拔、CPU quota 和缓存时效：都应在结果模型中留下可观察信息。

把进程资源、OS 在线状态、物理拓扑和容器配额分开，线程池配置、监控面板和容量计算才会使用正确的数字。

## 参考

- [Andrew Lock：Finding the total number of processors on a machine with .NET](https://andrewlock.net/finding-the-total-number-of-processors-on-a-machine-with-dotnet/)
- [.NET Environment.ProcessorCount](https://learn.microsoft.com/en-us/dotnet/api/system.environment.processorcount)
- [Windows GetActiveProcessorCount](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getactiveprocessorcount)
- [Windows Processor Groups](https://learn.microsoft.com/en-us/windows/win32/procthread/processor-groups)
- [Apple sysctlbyname 与系统能力](https://developer.apple.com/documentation/kernel/1387446-sysctlbyname/determining_system_capabilities?changes=_2)
- [Apple ProcessInfo.activeProcessorCount](https://developer.apple.com/documentation/foundation/processinfo/activeprocessorcount?changes=la)
- [Linux CPU hotplug 与 CPU 状态文件](https://docs.kernel.org/5.15/core-api/cpu_hotplug.html)
- [Linux cgroup v2 CPU 控制](https://docs.kernel.org/6.4/admin-guide/cgroup-v2.html)
- [.NET P/Invoke](https://learn.microsoft.com/en-us/dotnet/standard/native-interop/pinvoke)
- [.NET P/Invoke source generation](https://learn.microsoft.com/en-us/dotnet/standard/native-interop/pinvoke-source-generation)
