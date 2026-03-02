---
pubDatetime: 2026-03-02
title: "用 Portable PDB 在运行时获取方法的源码位置"
description: "CallerFilePath 只能在编译期拿到调用点的位置，如果你想在运行时拿到任意方法的源文件路径和行号，Portable PDB 提供了另一条路。本文用 System.Reflection.Metadata 演示完整实现。"
tags: [".NET", "C#", "调试", "反射", "PDB"]
slug: "portable-pdb-method-location-dotnet"
source: "https://www.meziantou.net/retrieve-method-source-file-location-at-runtime-using-portable-pdbs-in-dotnet.htm"
---

有时候你需要知道某个方法定义在哪个源文件的哪一行，不是在调用点，而是在方法本身定义的地方。

一个典型场景是快照测试工具。[Meziantou.Framework.InlineSnapshotTesting](https://www.meziantou.net/inline-snapshot-testing-in-dotnet.htm) 在测试运行时需要找到断言所在的源文件，这样它才能直接把新的快照写回去。`[CallerFilePath]` 在这里帮不上忙，因为你拿到的是调用者的位置，不是被测方法的定义位置。这就是 Portable PDB 登场的地方。

## 编译期方案的边界

`[CallerMemberName]`、`[CallerFilePath]`、`[CallerLineNumber]` 这三个 Attribute 是编译器在编译时填入的，只能用于日志这类"我知道调用点在哪"的场景：

```csharp
void Log(string message,
    [CallerMemberName] string memberName = "",
    [CallerFilePath] string filePath = "",
    [CallerLineNumber] int lineNumber = 0)
{
    Console.WriteLine($"{filePath}:{lineNumber} ({memberName}): {message}");
}

void DoWork()
{
    Log("Starting work"); // 输出: Program.cs:10 (DoWork): Starting work
}
```

这种写法要修改方法签名，且只能拿到调用点信息。如果你想拿到任意 `MethodInfo` 的定义位置，就得换一条路。

## PDB 文件里有什么

PDB（Program Database）文件是编译器生成的调试信息，它把编译后的 IL 指令映射回源代码。里面有源文件路径、每条指令对应的行号、局部变量名称等信息。

.NET 有两种 PDB 格式。旧格式（Windows PDB）只能在 Windows 上用；Portable PDB 是跨平台格式，可以嵌入程序集，体积也更小，是现代 .NET 项目的默认选项。

项目文件里可以控制 PDB 的分发方式：

```xml
<!-- 独立 .pdb 文件（默认） -->
<PropertyGroup>
  <DebugType>portable</DebugType>
</PropertyGroup>

<!-- 嵌入程序集内，部署时只需一个文件 -->
<PropertyGroup>
  <DebugType>embedded</DebugType>
</PropertyGroup>
```

嵌入模式让部署更简单，代价是程序集体积变大。

## 运行时读取源码位置

核心依赖是 `System.Reflection.Metadata`，先加包：

```xml
<PackageReference Include="System.Reflection.Metadata" Version="9.*" />
```

下面是完整实现：

```csharp
public static (string FilePath, SequencePoint SequencePoint)? GetMethodLocation(this MethodInfo methodInfo)
{
    ArgumentNullException.ThrowIfNull(methodInfo);

    var location = methodInfo.DeclaringType?.Assembly.Location;
    if (string.IsNullOrEmpty(location))
        return null;

    using var fs = File.OpenRead(location);
    using var reader = new PEReader(fs);

    // 先找嵌入式 PDB
    var pdbReaderProvider = reader.ReadDebugDirectory()
        .Where(entry => entry.Type == DebugDirectoryEntryType.EmbeddedPortablePdb)
        .Select(entry => reader.ReadEmbeddedPortablePdbDebugDirectoryData(entry))
        .FirstOrDefault();
    try
    {
        if (pdbReaderProvider is null)
        {
            // 嵌入式找不到，尝试同目录下的 .pdb 文件
            if (!reader.TryOpenAssociatedPortablePdb(location, File.OpenRead, out pdbReaderProvider, out _))
            {
                pdbReaderProvider?.Dispose();
                return null;
            }

            if (pdbReaderProvider is null)
                return null;
        }

        var pdbReader = pdbReaderProvider.GetMetadataReader();
        var methodHandle = MetadataTokens.MethodDefinitionHandle(methodInfo.MetadataToken);
        var methodDebugInfo = pdbReader.GetMethodDebugInformation(methodHandle);
        if (!methodDebugInfo.SequencePointsBlob.IsNil)
        {
            var sequencePoints = methodDebugInfo.GetSequencePoints();
            var firstSequencePoint = sequencePoints.FirstOrDefault();
            if (firstSequencePoint.Document.IsNil == false)
            {
                var document = pdbReader.GetDocument(firstSequencePoint.Document);
                var filePath = pdbReader.GetString(document.Name);
                return (filePath, firstSequencePoint);
            }
        }

        return null;
    }
    finally
    {
        pdbReaderProvider?.Dispose();
    }
}
```

逻辑分三步：

**找 PDB**：先检查程序集的 Debug Directory，看有没有嵌入式 Portable PDB。没有的话，调用 `TryOpenAssociatedPortablePdb` 去找同目录下的独立 `.pdb` 文件。

**拿 Sequence Points**：Sequence Points 是 IL 指令到源码行的映射表。用 `MetadataToken` 定位方法，再从 PDB 里取出这个方法的所有 Sequence Points，第一个通常就对应方法的开头。

**拿文件路径**：每个 Sequence Point 有一个 Document 引用，从里面取出 `Name` 字段就是源文件的完整路径。

## 实际用起来

```csharp
using System.Reflection;

class Program
{
    static void Main()
    {
        var method = typeof(Program).GetMethod(nameof(SampleMethod));
        var location = method.GetMethodLocation();

        if (location.HasValue)
        {
            Console.WriteLine($"Method: {method.Name}");
            Console.WriteLine($"File: {location.Value.FilePath}");
            Console.WriteLine($"Line: {location.Value.SequencePoint.StartLine}");
            Console.WriteLine($"Column: {location.Value.SequencePoint.StartColumn}");
        }
        else
        {
            Console.WriteLine("Location information not available");
        }
    }

    public static void SampleMethod()
    {
        Console.WriteLine("Hello, World!");
    }
}
```

输出：

```
Method: SampleMethod
File: C:\Projects\MyApp\Program.cs
Line: 23
Column: 5
```

## 生产环境的注意事项

这套方案有一个前提：PDB 得在。生产部署通常为了安全或减小体积会去掉 PDB，这时候方法会直接返回 `null`，调用方要做好处理。如果你的工具必须依赖源码位置（比如快照测试），确保在发布配置里也打开了 PDB 生成，或者选择嵌入模式。
