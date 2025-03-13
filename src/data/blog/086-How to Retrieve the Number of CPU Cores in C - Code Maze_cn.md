---
pubDatetime: 2024-04-06
tags: [C#]
source: https://code-maze.com/csharp-retrieve-the-number-of-cpu-cores/
author: Lennart Pries
title: 如何在C#中检索CPU核心数量
description: 本文探讨了我们在C#中检索CPU核心数量的方法，以及我们如何利用这些信息来优化代码
---

> ## 摘录
>
> 本文探讨了我们在C#中检索CPU核心数量的方法，以及我们如何利用这些信息来优化代码
>
> 原文 [How to Retrieve the Number of CPU Cores in C#](https://code-maze.com/csharp-retrieve-the-number-of-cpu-cores/)

---

在C#编程领域，理解底层硬件对于优化性能至关重要。一个基本方面是了解可用的CPU核心数量。在本文中，我们将探讨在C#中检索CPU核心数量的方法，深入研究`System.Environment`类和Windows WMI。

要下载本文的源代码，您可以访问我们的[GitHub仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/dotnet-platform-specific/RetrievalOfCpuCores)。

让我们开始吧。

## 检索CPU核心信息

首先，当谈到CPU核心数量时，有三个不同的术语。有**物理处理器**、**CPU核心**和**逻辑处理器**。它们在数量上有所不同，因此有不同的含义。

**物理处理器代表安装在主板上的有形芯片**，每个芯片包含多个能够独立执行指令的CPU核心。**另一方面，逻辑处理器是由诸如超线程之类的技术生成的虚拟实体。**每个核心能够同时处理多个线程。通常逻辑处理器的数量是其物理处理器数量的两倍。

我们从最简单的方式开始，检索逻辑处理器的数量：

```csharp
var cpuCount = Environment.ProcessorCount;
```

这种简洁的方法提供了一种快速检索逻辑处理器数量的手段。值得注意的是，这种方法是检索CPU核心信息的唯一适用于所有平台的方法，确保了统一性和易访问性。

## 检索WMI核心信息

**WMI**（Windows管理工具）核心信息是我们在C#中检索CPU核心数量的另一种方法，**但它仅在Windows机器上操作。**这种限制带来风险，尤其是许多服务器运行在Linux上。在开发开源代码或库时，独立性至关重要。确保跨不同操作系统的可访问性允许任何人使用和测试应用程序。然而，在特定情况下，利用WMI可能会有所帮助。

WMI核心信息通常来自操作系统的管理基础结构，为在Windows环境中检索有关硬件、软件和系统配置的数据提供了标准化接口。有了这个接口，我们可以获得高级CPU信息。如果我们想在Windows系统上检索物理处理器数量或核心数量，我们使用WMI接口。

首先，我们向项目引用添加NuGet包`System.Management.dll`：

```bash
Install-Package System.Management
```

有了这个，让我们看看我们如何检索核心数量。

### 检索核心数量

现在我们可以检索核心数量：

```csharp
public int GetNumberOfCores()
{
    if (!OperatingSystem.IsWindows())
    {
        throw new PlatformNotSupportedException();
    }
    var coreCount = 0;
    const string wmiQuery = "Select * from Win32_Processor";
    foreach (var item in new System.Management.ManagementObjectSearcher(wmiQuery).Get())
    {
        coreCount += int.Parse(item["NumberOfCores"].ToString());
    }
    return coreCount;
}
```

这里，我们定义了`GetNumberOfCores()`方法。如果平台不是Windows，我们抛出一个`PlatformNotSupportedException`。否则，我们继续计算总核心数量。

`System.Management.ManagementObjectSearcher`类是我们用来查询**Windows系统信息**的WMI API。我们循环遍历查询结果，并从WMI实例中检索`NumberOfCores`属性。

### 物理处理器

我们也可以获得物理处理器的数量：

```csharp
const string wmiQuery = "Select * from Win32_ComputerSystem";
public int GetPhysicalProcessors()
{
    if (!OperatingSystem.IsWindows())
    {
        throw a PlatformNotSupportedException();
    }
    foreach (var item in new System.Management.ManagementObjectSearcher(wmiQuery).Get())
    {
        return int.Parse(item["NumberOfProcessors"].ToString());
    }
    return 0;
}
```

这里，我们使用循环来获取执行查询`Select * from Win32_ComputerSystem`的`System.Management.ManagementObjectSearcher`的所有结果。然后，我们检索每个结果的`NumberOfProcessors`属性，它代表系统中存在的物理处理器数量。

### 逻辑处理器

我们也可以使用这个API来获取逻辑处理器的数量，而不是使用`Environment.ProcessorCount`：

```csharp
const string wmiQuery = "Select * from Win32_ComputerSystem";
public int GetLogicalProcessors()
{
    if (!OperatingSystem.IsWindows())
    {
        throw a PlatformNotSupportedException();
    }
    foreach (var item in new System.Management.ManagementObjectSearcher(wmiQuery).Get())
    {
        return int.Parse(item["NumberOfLogicalProcessors"].ToString());
    }
    return 0;
}
```

与我们之前的方法类似，我们使用循环从`ManagementObjectSearcher()`方法中获取结果。这次，我们检索`NumberOfLogicalProcessors`属性，代表系统中逻辑处理器的数量。

对于CPU核心信息检索，使用WMI提供了对系统硬件的高级见解，但**仅限于Windows环境，对于跨平台兼容性提出了挑战**。虽然WMI为访问CPU细节如物理处理器和核心提供了一个标准化的接口，但其依赖于Windows特定API需要在旨在更广泛平台支持的开源项目中仔细考虑。

## Windows中被排除的处理器

在Windows系统的CPU信息上下文中处理时，认识到Windows对处理器的不同处理至关重要。**兼容性问题、启动设置或其他因素可能会导致某些处理器被排除在某些功能或特性之外**。特定Windows版本，例如Windows 11，可能会由于兼容性要求而排除某些CPU。

为了深入了解处理器排除，我们可以使用`setupapi.dll`中可用的Windows API调用。这些调用允许我们发现被Windows明确排除的处理器。我们首先需要创建一些函数和结构，来获取这样的处理器：

```csharp
[DllImport("setupapi.dll", SetLastError = true)]
private static extern IntPtr SetupDiGetClassDevs(ref Guid ClassGuid,
    [MarshalAs(UnmanagedType.LPStr)] string enumerator,
    IntPtr hwndParent,
    int Flags);
[DllImport("setupapi.dll", SetLastError = true)]
private static extern int SetupDiDestroyDeviceInfoList(IntPtr DeviceInfoSet);
[DllImport("setupapi.dll", SetLastError = true)]
private static extern bool SetupDiEnumDeviceInfo(IntPtr DeviceInfoSet,
    int MemberIndex,
    ref SP_DEVINFO_DATA DeviceInterfaceData);
[StructLayout(LayoutKind.Sequential)]
private struct SP_DEVINFO_DATA
{
    public int cbSize;
    public Guid ClassGuid;
    public uint DevInst;
    public IntPtr Reserved;
}
private enum DIGCF
{
    DEFAULT = 0x1,
    PRESENT = 0x2,
    ALLCLASSES = 0x4,
    PROFILE = 0x8,
    DEVICEINTERFACE = 0x10,
}
```

这里，我们包括对`setupapi.dll`中函数的导入（`DllImport`）、一个结构（`SP_DEVINFO_DATA`）和一个枚举（`DIGCF`）。这些是我们需要的函数和类型，以便能够获得被排除处理器的数量。

现在，我们确定被排除的处理器：

```csharp
public int GetExcludedProcessors()
{
    if (!OperatingSystem.IsWindows())
    {
        throw new PlatformNotSupportedException();
    }
    var deviceCount = 0;
    var deviceList = IntPtr.Zero;
    var processorGuid = new Guid("{50127dc3-0f36-415e-a6cc-4cb3be910b65}");
    try
    {
        deviceList = SetupDiGetClassDevs(ref processorGuid, "ACPI", IntPtr.Zero, (int)DIGCF.PRESENT);
        for (var deviceNumber = 0; ; deviceNumber++)
        {
            var deviceInfo = new SP_DEVINFO_DATA();
            deviceInfo.cbSize = Marshal.SizeOf(deviceInfo);
            if (!SetupDiEnumDeviceInfo(deviceList, deviceNumber, ref deviceInfo))
            {
                deviceCount = deviceNumber;
                break;
            }
        }
    }
    finally
    {
        if (deviceList != IntPtr.Zero) { SetupDiDestroyDeviceInfoList(deviceList); }
    }
    return deviceCount;
}
```

这里，我们定义了`GetExcludedProcessors()`方法，我们使用**SetupApi**调用在Windows系统上检索被排除的处理器数量。

我们首先初始化变量并使用`SetupDiGetClassDevs()`方法获取设备信息。然后我们遍历设备并更新计数。最后，我们清理资源并返回处理器的计数。请注意，我们的方法提供了被**Windows排除的逻辑处理器的总数**。

## 应用和优化

在使用C#处理CPU信息时，理解如何优化性能至关重要。[多线程](https://code-maze.com/csharp-async-vs-multithreading/)是优化程序性能的一种方式。但要优化多线程代码，我们希望至少有与逻辑处理器数量相同的线程数量。

通过使用这种方法，我们可以最大化CPU的使用，因为每个处理器都分配了任务，并且我们在CPU核心之间分配工作负载以更快地执行。记住，CPU优化是性能和功耗效率之间的平衡。通过有效利用核心信息，我们创建的应用程序更加高效，最佳地使用可用资源。

## 结论

在C#编程中，性能优化常常取决于理解CPU核心的可用性。我们探索了物理处理器、CPU核心和逻辑处理器，每种都有其独特的重要性。通过C#和Windows WMI，我们发现了从Environment.ProcessorCount到WMI查询的检索CPU核心数量的方法。此外，我们讨论了从Windows系统中排除处理器的复杂性。

利用CPU核心数据进行应用程序优化至关重要。使多线程代码与逻辑处理器计数对齐，最大化系统潜力，实现性能与功耗效率的平衡。

掌握在C#中检索CPU核心信息使开发人员能够创建高效应用程序，最大化跨不同计算环境的资源利用。
