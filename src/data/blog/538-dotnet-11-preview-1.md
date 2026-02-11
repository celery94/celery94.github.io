---
pubDatetime: 2026-02-11
title: ".NET 11 Preview 1 发布：全面解析技术更新"
description: ".NET 11 首个预览版发布，带来运行时异步支持、WebAssembly上的CoreCLR、Zstandard压缩、BFloat16类型、ASP.NET Core新组件、MAUI的XAML源码生成等重大技术改进，涵盖库、运行时、SDK、C#、F#和Entity Framework Core的全方位更新。"
tags: [".NET", "C#", "ASP.NET Core", "Performance", "WebAssembly"]
slug: "dotnet-11-preview-1"
source: "https://devblogs.microsoft.com/dotnet/dotnet-11-preview-1"
---

# .NET 11 Preview 1 发布：全面解析技术更新

微软于 2026 年 2 月 10 日正式发布 **.NET 11 Preview 1**，这是继 .NET 10 之后的首个预览版本。本次更新涵盖运行时、库、SDK、语言特性、ASP.NET Core、Blazor、.NET MAUI 和 Entity Framework Core 等多个领域，带来了大量性能优化和新功能。

## 📚 库 (Libraries) 更新

### Zstandard 压缩支持

新增对 Zstandard (Zstd) 压缩算法的原生支持，这是一种由 Facebook 开发的高性能压缩算法，提供比传统 gzip 更好的压缩比和速度。开发者可以直接通过 .NET API 使用 Zstd 压缩和解压缩数据。

### BFloat16 浮点类型

引入 **BFloat16** (`Brain Floating Point`) 数据类型，这是机器学习领域广泛使用的 16 位浮点格式。相比标准的 Float16，BFloat16 保留了更大的指数范围，牺牲了精度，更适合深度学习模型的训练和推理场景。

### ZipArchiveEntry 改进

对 `ZipArchiveEntry` 类进行了增强，提供更灵活的压缩包条目管理能力，包括更好的元数据访问和性能优化。

### FrozenDictionary 集合表达式支持

`FrozenDictionary` 现在支持**集合表达式 (Collection Expressions)** 语法，可以使用更简洁的语法创建不可变字典：

```csharp
FrozenDictionary<string, int> lookup = [
    "apple" => 1,
    "banana" => 2,
    "cherry" => 3
];
```

### TimeZone 改进

时区处理 API 得到增强，提供更精确的时区转换和夏令时处理能力，改善跨时区应用的开发体验。

### Rune 支持扩展

`Rune` 类型（表示 Unicode 标量值）现在在 `String`、`StringBuilder` 和 `TextWriter` 中获得一致的支持，方便处理 Unicode 字符和 emoji 表情。

### MediaTypeMap 用于 MIME 类型查找

新增 `MediaTypeMap` 工具类，简化文件扩展名与 MIME 类型之间的映射查找，常用于 Web 开发和文件上传场景。

### HMAC 和 KMAC 验证 API

提供新的 **HMAC** (Hash-based Message Authentication Code) 和 **KMAC** (Keccak Message Authentication Code) 验证 API，增强密码学操作的易用性和安全性。

### 硬链接创建 API

新增文件系统硬链接 (hard link) 创建 API，允许创建指向同一文件数据的多个文件系统条目，适用于版本控制和备份场景。

### DivisionRounding 整数除法模式

新增 `DivisionRounding` 枚举，支持多种整数除法舍入模式（向上、向下、向零、向最近偶数等），提供更精确的整数运算控制。

### Happy Eyeballs 支持

`Socket.ConnectAsync` 现在支持 **Happy Eyeballs** 算法 (RFC 8305)，在同时尝试 IPv4 和 IPv6 连接时自动选择最快的连接方式，提升网络连接的可靠性和速度。

### 性能改进

库层面进行了多项性能优化，包括集合操作、字符串处理、序列化和 I/O 操作的性能提升。

## ⏱️ 运行时 (Runtime) 更新

### Runtime Async

引入**运行时级别的异步支持**，改进垃圾回收和线程调度的异步操作能力，减少阻塞，提升高并发应用的性能。

### CoreCLR on WebAssembly

**.NET 的 CoreCLR 运行时现在可以在 WebAssembly 上运行**，这是一个重大突破。相比之前仅支持的 Mono 运行时，CoreCLR 提供更好的性能和完整的 .NET 功能支持，使 Blazor WebAssembly 应用能够获得接近原生的执行速度。

### Interpreter Expansion

解释器功能扩展，提供更完整的 .NET 代码解释执行能力，适用于需要动态代码执行的场景，如脚本引擎和热更新系统。

### JIT 性能改进

**即时编译器 (JIT)** 进行了多项优化：

- 更好的内联决策
- 改进的循环优化
- 向量化增强
- 更高效的代码生成

### GC 堆硬限制 (32 位进程)

为 32 位进程引入 **GC 堆硬限制**配置选项，允许开发者明确控制垃圾回收器可以使用的最大内存量，防止内存溢出。

### RISC-V 和 s390x 架构支持

新增对 **RISC-V** 和 **s390x** (IBM Z 架构) 的支持，扩展 .NET 在嵌入式设备和大型主机系统的应用范围。

## 🛠️ SDK 更新

### dotnet run：交互式目标框架和设备选择

执行 `dotnet run` 时，如果项目配置了多个目标框架或设备，SDK 会提供交互式选择界面，无需手动指定参数：

```bash
$ dotnet run
1. net11.0
2. net11.0-android
3. net11.0-ios
Select target framework: _
```

### dotnet test：位置参数

`dotnet test` 命令现在支持位置参数，可以更简洁地指定测试项目或解决方案：

```bash
dotnet test MySolution.sln --filter "Category=Unit"
```

### dotnet watch：热重载增强

`dotnet watch` 工具获得两项重要改进：

1. **热重载引用变更**：修改项目引用时自动重新加载
2. **可配置端口**：允许自定义开发服务器端口，避免端口冲突

### 新代码分析器

SDK 集成了新的代码分析器，提供更多编码规范检查和性能优化建议。

## 🔨 MSBuild 更新

### Terminal Logger 改进

终端日志记录器提供更清晰的构建输出，改进进度显示和错误信息格式。

### MSBuild 语言和评估修复

修复了多个 MSBuild 语言解析和属性评估的 bug，提高构建稳定性。

### 新 API 和功能

为 MSBuild 扩展开发者提供新的 API，支持更灵活的构建定制。

### 性能改进

优化构建过程，特别是大型解决方案的增量构建性能。

## C# 语言特性

### Collection Expression Arguments

集合表达式现在可以直接作为方法参数传递，无需显式变量声明：

```csharp
ProcessItems([1, 2, 3, 4, 5]);

void ProcessItems(int[] items) { }
```

### Extended Layout Support

扩展的内存布局控制支持，允许更精细地控制结构体和类的内存排列，适用于互操作和性能关键场景。

## F# 语言特性

### 并行编译默认启用

F# 编译器现在**默认启用并行编译**，显著提升大型 F# 项目的编译速度。

### 计算表达式编译优化

针对大量使用计算表达式 (computation expressions) 的代码进行编译速度优化，减少编译时间。

### 新编译器标志

- `--disableLanguageFeature`：禁用特定语言特性，用于兼容性测试
- `--typecheck-only`：FSI (F# Interactive) 仅执行类型检查，不执行代码

### ML 兼容性移除

移除了传统 ML 语言的兼容性支持，简化编译器实现。

## Visual Basic

Preview 1 中 Visual Basic 没有新的语言特性或破坏性变更，主要集中于质量改进和 bug 修复。

## 🌐 ASP.NET Core & Blazor 更新

### EnvironmentBoundary 组件

新增 `<EnvironmentBoundary>` 组件，允许在 Blazor 应用中明确标记运行环境边界（服务器端/客户端），改善组件渲染控制。

### Label 组件用于表单

Blazor 新增 `<Label>` 组件，提供更好的表单可访问性支持：

```razor
<Label For="userName">用户名</Label>
<InputText @bind-Value="userName" id="userName" />
```

### DisplayName 组件

新增 `<DisplayName>` 组件，自动从模型元数据中提取显示名称，简化表单开发。

### QuickGrid OnRowClick 事件

`QuickGrid` 组件新增 `OnRowClick` 事件，支持行点击交互：

```razor
<QuickGrid Items="products" OnRowClick="HandleRowClick">
    <!-- columns -->
</QuickGrid>
```

### 相对导航 RelativeToCurrentUri

Blazor 导航服务新增 `RelativeToCurrentUri` 选项，支持相对于当前页面的 URL 导航，简化 SPA 路由逻辑。

### SignalR ConfigureConnection

为交互式服务器组件提供 `ConfigureConnection` API，允许自定义 SignalR 连接配置（如超时、重连策略）。

### IHostedService 支持 Blazor WebAssembly

Blazor WebAssembly 现在支持 `IHostedService`，可以在客户端运行后台服务，实现定时任务、轮询等功能。

### OpenAPI 二进制文件响应支持

OpenAPI 架构生成器现在支持二进制文件响应类型（如文件下载），自动生成正确的 `application/octet-stream` 架构。

### IOutputCachePolicyProvider

新增 `IOutputCachePolicyProvider` 接口，允许动态提供输出缓存策略，实现更灵活的缓存控制。

### WSL 中自动信任开发证书

在 WSL (Windows Subsystem for Linux) 环境中，开发 HTTPS 证书现在可以自动信任，无需手动配置。

## 📱 .NET MAUI 更新

### XAML 源代码生成默认启用

**.NET MAUI 默认启用 XAML 源代码生成**，将 XAML 编译为 C# 代码，提升应用启动速度和运行时性能。

### .NET for Android

#### CoreCLR 默认启用

Android 应用现在**默认使用 CoreCLR 运行时**（替代 Mono），显著提升性能和内存效率。

#### dotnet run 增强

`dotnet run` 命令对 Android 应用进行了优化，支持更快的部署和调试体验。

## 🖥️ Windows Forms

Preview 1 集中于质量改进和 bug 修复，没有重大新功能。

## 🖥️ Windows Presentation Foundation (WPF)

主要进行质量改进，修复了在 **Windows 10** 上使用 Fluent 设计窗口背景和 backdrop 的问题。

## 🎁 Entity Framework Core 更新

### TPT/TPC 继承的复杂类型和 JSON 列

使用 **TPT** (Table Per Type) 或 **TPC** (Table Per Concrete Type) 继承策略的实体类型，现在支持复杂类型和 JSON 列映射。

### 一步创建和应用迁移

新命令简化迁移工作流，允许在单个步骤中创建迁移并应用到数据库：

```bash
dotnet ef migrations add-and-update InitialCreate
```

### Azure Cosmos DB 改进

#### 事务批处理

支持 Cosmos DB 的事务批处理 API，在单个事务中执行多个操作，保证原子性。

#### 批量执行

新增批量执行支持，显著提升大量数据写入的性能。

#### 会话令牌管理

改进会话令牌 (session token) 的管理，提供更好的一致性控制和性能优化。

## 📦 容器镜像

Preview 1 没有引入新的容器镜像特性，继续使用 .NET 10 的容器化最佳实践。

## 🚀 开始使用

要体验 .NET 11 Preview 1，请访问 [.NET 11 下载页面](https://dotnet.microsoft.com/download/dotnet/11.0) 安装 SDK。

### 开发工具

- **Windows 用户**：推荐安装 [Visual Studio 2026 Insiders](https://visualstudio.microsoft.com/insiders)
- **跨平台开发**：使用 [Visual Studio Code](https://code.visualstudio.com/) + [C# Dev Kit](https://marketplace.visualstudio.com/items?itemName=ms-dotnettools.csdevkit) 扩展

## 总结

.NET 11 Preview 1 在性能、开发体验和平台支持方面都带来了显著改进：

- **性能提升**：CoreCLR on WebAssembly、JIT 优化、并行编译
- **新功能**：Zstandard 压缩、BFloat16 类型、HMAC/KMAC API
- **开发体验**：SDK 交互式选择、热重载增强、MAUI XAML 源码生成
- **架构支持**：RISC-V、s390x、改进的 WebAssembly 支持
- **框架增强**：ASP.NET Core 新组件、EF Core Cosmos DB 改进

作为首个预览版本，建议开发者在测试环境中尝试这些新特性，并向 .NET 团队提供反馈。正式版预计在 2026 年 11 月发布。

---

**相关链接**：

- [完整发布说明](https://github.com/dotnet/core/blob/main/release-notes/11.0/preview/preview1/README.md)
- [.NET 11 下载](https://dotnet.microsoft.com/download/dotnet/11.0)
- [Visual Studio 2026 Insiders](https://visualstudio.microsoft.com/insiders)
