---
pubDatetime: 2026-04-29T10:55:00+08:00
title: "用 .NET Native AOT 编写 Node.js 原生插件"
description: "C# Dev Kit 团队用 .NET Native AOT 替换 C++ node-gyp 插件的完整实战：从项目配置、N-API 入口点声明、P/Invoke 解析、字符串 marshalling，到从 TypeScript 调用 C# 原生函数的全流程。"
tags: ["dotnet", "NativeAOT", "Node.js", "CSharp", "Interop", "N-API"]
slug: "dotnet-native-aot-nodejs-addons"
ogImage: "../../assets/764/01-cover.png"
source: "https://devblogs.microsoft.com/dotnet/writing-nodejs-addons-with-dotnet-native-aot/"
---

![用 .NET Native AOT 编写 Node.js 原生插件](../../assets/764/01-cover.png)

C# Dev Kit 是一个 VS Code 扩展，前端是 TypeScript，运行在 Node.js 中。对于读取 Windows 注册表这类平台特定任务，团队过去一直用 C++ 写 Node.js 原生插件，并在安装时通过 node-gyp 编译。这条路是通的，但代价不小：每台开发者机器都要安装特定版本的 Python，CI 流水线需要维护这套依赖，新人入职还要花时间搭建他们永远不会直接用到的工具链。

.NET SDK 本来就是必备工具。为什么不用 C# 和 Native AOT 来替代？这篇文章来自 .NET 官方博客，作者 Drew Noakes（C# Dev Kit 的 Principal SWE）记录了整个替换过程和关键的技术细节。

## Node.js 原生插件的工作原理

Node.js 原生插件是一个共享库（Windows 上是 `.dll`，Linux 是 `.so`，macOS 是 `.dylib`），需要导出一个固定的入口点函数 `napi_register_module_v1`。Node.js 加载这个库时会调用该函数，插件在函数里注册它对外暴露的方法，之后 JavaScript 就能像普通模块一样使用它。

让这一切成为可能的接口是 [N-API](https://nodejs.org/api/n-api.html)（也叫 Node-API）——一套稳定的、ABI 兼容的 C API。N-API 不关心共享库用哪种语言编写，只要导出正确的符号、调用正确的函数即可。Native AOT 恰好能生成带有任意原生入口点的共享库，完全符合这个要求。

## 项目文件

项目文件只需两行关键配置：

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <PublishAot>true</PublishAot>
    <AllowUnsafeBlocks>true</AllowUnsafeBlocks>
  </PropertyGroup>
</Project>
```

`PublishAot` 告诉 SDK 在发布时生成共享库。`AllowUnsafeBlocks` 是必须的，因为 N-API interop 要用到函数指针和 fixed 缓冲区。

## 模块入口点

Node.js 要求共享库导出 `napi_register_module_v1`。在 C# 中，用 `[UnmanagedCallersOnly]` 就能做到：

```csharp
public static unsafe partial class RegistryAddon
{
    [UnmanagedCallersOnly(
        EntryPoint = "napi_register_module_v1",
        CallConvs = [typeof(CallConvCdecl)])]
    public static nint Init(nint env, nint exports)
    {
        Initialize();

        RegisterFunction(
            env,
            exports,
            "readStringValue"u8,
            &ReadStringValue);

        return exports;
    }
}
```

这里用到了几个 C# 特性：

- `nint` 是原生大小整数，等价于 `intptr_t`，用来传递 N-API 句柄
- `"readStringValue"u8` 是 UTF-8 字符串字面量，产生 `ReadOnlySpan<byte>`，可以直接传给 N-API，无需编码转换或堆分配
- `[UnmanagedCallersOnly]` 告诉 AOT 编译器用指定的入口点名称和调用约定导出该方法

每次 `RegisterFunction` 调用都会把一个 C# 函数指针绑定到 JavaScript `exports` 对象上的命名属性，这样 TypeScript 中调用 `addon.readStringValue(...)` 就会直接调用对应的 C# 方法，在进程内完成。

## 从 .NET 调用 N-API

N-API 函数由 `node.exe` 本身导出，不需要链接额外的库，而是需要在运行时从宿主进程解析。用 `[LibraryImport]` 声明 P/Invoke，库名写 `"node"`，然后通过 `NativeLibrary.SetDllImportResolver` 注册一个自定义解析器，把它重定向到宿主进程：

```csharp
private static void Initialize()
{
    NativeLibrary.SetDllImportResolver(
        System.Reflection.Assembly.GetExecutingAssembly(),
        ResolveDllImport);

    static nint ResolveDllImport(
        string libraryName,
        Assembly assembly,
        DllImportSearchPath? searchPath)
    {
        if (libraryName is not "node")
            return 0;

        return NativeLibrary.GetMainProgramHandle();
    }
}
```

有了这个解析器，运行时就知道所有 `"node"` 导入要从宿主进程查找。N-API 的 P/Invoke 声明如下：

```csharp
private static partial class NativeMethods
{
    [LibraryImport("node", EntryPoint = "napi_create_string_utf8")]
    internal static partial Status CreateStringUtf8(
        nint env, ReadOnlySpan<byte> str, nuint length, out nint result);

    [LibraryImport("node", EntryPoint = "napi_create_function")]
    internal static unsafe partial Status CreateFunction(
        nint env, ReadOnlySpan<byte> utf8name, nuint length,
        delegate* unmanaged[Cdecl]<nint, nint, nint> cb,
        nint data, out nint result);

    [LibraryImport("node", EntryPoint = "napi_get_cb_info")]
    internal static unsafe partial Status GetCallbackInfo(
        nint env, nint cbinfo, ref nuint argc,
        Span<nint> argv, nint* thisArg, nint* data);

    // ... 其他 N-API 函数
}
```

源码生成的 `[LibraryImport]` 负责 marshalling：`ReadOnlySpan<byte>` 映射为 `const char*`，函数指针直接透传，生成的代码天然支持 trimming。

注册函数到 exports 对象的辅助方法：

```csharp
private static unsafe void RegisterFunction(
    nint env, nint exports, ReadOnlySpan<byte> name,
    delegate* unmanaged[Cdecl]<nint, nint, nint> callback)
{
    NativeMethods.CreateFunction(env, name, (nuint)name.Length, callback, 0, out nint fn);
    NativeMethods.SetNamedProperty(env, exports, name, fn);
}
```

## 字符串 Marshalling

interop 的大部分工作是在 JavaScript 和 .NET 之间传递字符串。N-API 使用 UTF-8，转换思路很直接，但需要缓冲区。下面是从 JavaScript 读取字符串参数的辅助方法：

```csharp
private static unsafe string? GetStringArg(nint env, nint cbinfo, int index)
{
    nuint argc = (nuint)(index + 1);
    Span<nint> argv = stackalloc nint[index + 1];
    NativeMethods.GetCallbackInfo(env, cbinfo, ref argc, argv, null, null);

    if ((int)argc <= index)
        return null;

    // 查询 UTF-8 字节长度
    NativeMethods.GetValueStringUtf8(env, argv[index], null, 0, out nuint len);

    int bufLen = (int)len + 1;
    byte[]? rented = null;
    Span<byte> buf = bufLen <= 512
        ? stackalloc byte[bufLen]
        : (rented = ArrayPool<byte>.Shared.Rent(bufLen));

    try
    {
        fixed (byte* pBuf = buf)
            NativeMethods.GetValueStringUtf8(env, argv[index], pBuf, len + 1, out _);

        return Encoding.UTF8.GetString(buf[..(int)len]);
    }
    finally
    {
        if (rented is not null)
            ArrayPool<byte>.Shared.Return(rented);
    }
}
```

先查长度，再分配缓冲区（小字符串用 `stackalloc`，大字符串从 `ArrayPool` 租用），读完字节后解码成 .NET `string`。

返回字符串到 JavaScript 是反向操作，把 .NET `string` 编码为 UTF-8 缓冲区再传给 `napi_create_string_utf8`：

```csharp
private static nint CreateString(nint env, string value)
{
    int byteCount = Encoding.UTF8.GetByteCount(value);

    byte[]? rented = null;
    Span<byte> buf = byteCount <= 512
        ? stackalloc byte[byteCount]
        : (rented = ArrayPool<byte>.Shared.Rent(byteCount));

    try
    {
        Encoding.UTF8.GetBytes(value, buf);
        NativeMethods.CreateStringUtf8(
            env, buf[..byteCount], (nuint)byteCount, out nint result);
        return result;
    }
    finally
    {
        if (rented is not null)
            ArrayPool<byte>.Shared.Return(rented);
    }
}
```

两个方向都用 `Span<T>`、`stackalloc` 和 `ArrayPool` 来避免对典型字符串长度的堆分配。有了这两个辅助方法，后续的导出函数就不用再操心 marshalling 细节了。

## 实现导出函数

有了 N-API 管道层，实现具体的导出函数就很直接了。下面这个函数读取 Windows 注册表中的字符串值并作为字符串返回给 JavaScript：

```csharp
[UnmanagedCallersOnly(CallConvs = [typeof(CallConvCdecl)])]
private static nint ReadStringValue(nint env, nint info)
{
    try
    {
        var keyPath = GetStringArg(env, info, 0);
        var valueName = GetStringArg(env, info, 1);

        if (keyPath is null || valueName is null)
        {
            ThrowError(env, "Expected two string arguments: keyPath, valueName");
            return 0;
        }

        using var key = Registry.CurrentUser.OpenSubKey(keyPath, writable: false);

        return key?.GetValue(valueName) is string value
            ? CreateString(env, value)
            : GetUndefined(env);
    }
    catch (Exception ex)
    {
        ThrowError(env, $"Registry read failed: {ex.Message}");
        return 0;
    }
}
```

每个导出函数的结构都是这样：先读参数，做实际工作，然后返回结果。需要特别注意异常处理——`[UnmanagedCallersOnly]` 方法中未处理的异常会导致宿主进程崩溃。这里统一 catch 后通过 `ThrowError` 转发给 JavaScript，调用端会收到标准的 JavaScript `Error`。

这个例子也说明了为什么原生插件有价值：Node.js 没有内建的 Windows 注册表访问能力，而用原生插件就能直接调用 .NET 的 `Microsoft.Win32.Registry`，以很小的代码量把结果暴露给 JavaScript。

## 从 TypeScript 调用

先用 `dotnet publish` 构建，会输出平台对应的共享库（Windows 上是 `.dll`，Linux 上是 `.so`，macOS 上是 `.dylib`）。按惯例 Node.js 把以 `.node` 结尾的路径视为原生插件，把输出文件重命名为 `MyNativeAddon.node` 即可。

先声明 TypeScript 接口：

```typescript
interface RegistryAddon {
    readStringValue(keyPath: string, valueName: string): string | undefined;
}
```

然后用 `require()` 加载：

```typescript
const registry = require('./native/win32-x64/RegistryAddon.node') as RegistryAddon

const sdkPath = registry.readStringValue(
    'SOFTWARE\\dotnet\\Setup\\InstalledVersions\\x64\\sdk',
    'InstallLocation')
```

这样就完成了：TypeScript 调用，C# 响应，全在同一个进程内。虽然这个注册表插件是 Windows 专属，但同样的 Native AOT + N-API 方案在 Windows、Linux、macOS 上都能运行。

## 跨平台注意事项

Native AOT 不支持跨平台编译。如果需要支持多个操作系统，就需要对应的构建环境（Windows 机器出 `.dll`，Linux 机器出 `.so`，macOS 机器出 `.dylib`）。N-API 本身是跨平台的，代码逻辑无需修改。

## 有没有现成的高层库

已经有 [node-api-dotnet](https://github.com/microsoft/node-api-dotnet) 这个项目，提供了更高层的 .NET/JavaScript interop 框架，处理了很多样板代码，也支持更丰富的场景。C# Dev Kit 团队只需要少量函数，用薄薄的 N-API 封装层就够了，避免引入额外依赖。如果需要从 JavaScript 调用整个 .NET 类，或者处理从 JavaScript 到 .NET 的回调，这类库值得考虑。

## 实际收益

最直接的好处是简化了贡献者的开发环境。现在 `yarn install` 只需要 Node.js、C++ 工具链和 .NET SDK——这些原本就是必备工具，不再需要为了一个插件去装特定版本的 Python。CI 流水线也随之变简单。

性能方面和 C++ 实现相当。Native AOT 生成优化后的原生代码，对于这类工作（字符串 marshalling、注册表访问），实践中没有明显差距。.NET 运行时会带来 GC 和略大的内存占用，但在长期运行的 VS Code 扩展进程里可以忽略。

更长远的可能性：团队目前把大量 .NET 工作负载跑在独立进程里，通过管道通信。既然 Native AOT 能生成直接加载进 Node.js 进程的共享库，未来就有机会把部分逻辑搬进进程内，省去序列化和进程管理的开销。

## 参考

- [Writing Node.js addons with .NET Native AOT](https://devblogs.microsoft.com/dotnet/writing-nodejs-addons-with-dotnet-native-aot/)
- [native-aot-node-addon-demo（示例仓库）](https://github.com/drewnoakes/native-aot-node-addon-demo)
- [N-API 官方文档](https://nodejs.org/api/n-api.html)
- [.NET Native AOT 部署文档](https://learn.microsoft.com/dotnet/core/deploying/native-aot/)
- [node-api-dotnet](https://github.com/microsoft/node-api-dotnet)
