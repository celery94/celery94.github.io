---
pubDatetime: 2025-07-01
tags: [".NET", "C#"]
slug: source-generators-deep-dive
source: https://thecodeman.net/posts/source-generators-deep-dive
title: 深入理解 C# Source Generators：原理、实战与最佳实践
description: 本文全面梳理了 C# Source Generators 的发展、原理、实战应用及最佳实践，结合 C# 12 和 .NET 8 的最新增强特性，通过丰富实例与场景剖析，助力开发者高效利用代码生成提升开发效率与代码质量。
---

---

# 深入理解 C# Source Generators：原理、实战与最佳实践

## 引言：Source Generators 让 C# 编译器成为你的“代码助手”

C# 9 引入的 Source Generators 开启了 .NET 静态代码分析与编译期代码生成的新纪元。到了 C# 12 以及 .NET 8，Source Generators 在功能与性能层面又有了显著提升。本文将全面解析 Source Generators 的原理、关键能力、进阶用法和工程实践经验，让你能够像驾驭 Roslyn 一样驾驭自己的编译期代码生成流程。

## 什么是 Source Generators？

Source Generators 是 .NET 编译期间运行的小型程序，它们可以分析你的源代码并自动生成新的 C# 源文件。这些生成的代码会与项目中的原始代码一同参与编译。借助这一机制，开发者不仅可以消除重复性工作，还能实现强类型、静态检查的高级元编程（Metaprogramming），如代码样板自动化、静态校验、自动注册等。

**典型应用场景包括：**

- 自动代码样板（如实体、DTO、API 客户端等）生成
- 自动依赖注入注册代码生成
- 静态编译时校验（如属性约束、命名规范）
- 基于规范的序列化代码生成

## C# 12 及 .NET 8 中 Source Generators 的重要增强

随着 C# 12 和新一代 Roslyn API 的发布，Source Generators 获得了诸多新特性，主要包括：

**1. 增量生成器（Incremental Generators）**

增量生成器极大优化了生成器的性能，只有相关代码发生变更时才重新生成部分代码，极大减少了无谓的全量重编译。其本质在于构建了高效的依赖关系追踪和结果缓存机制。

**2. 源依赖分析与诊断能力升级**

C# 12 提供了更智能的依赖分析能力，编译器能精准定位哪些生成代码真正影响了主项目，提升了构建效率。诊断系统也更为友好，能够直接在 IDE 内高亮生成代码的问题，并给出详细的编译期错误或警告。

**3. Roslyn API 加强**

新版 API 开放了更多底层语法树（Syntax Tree）访问和编辑钩子，让高级场景（如代码重写、深度分析）成为可能。例如，可以更轻松地获取类型元数据、实现跨文件分析。

## 快速实践：自定义 Source Generator 的基本步骤

### 步骤一：创建生成器项目

创建一个 .NET Standard 类库（classlib）工程，并添加 `Microsoft.CodeAnalysis.CSharp` 包。

```shell
dotnet new classlib -n MySourceGenerator
dotnet add package Microsoft.CodeAnalysis.CSharp
```

### 步骤二：实现生成器逻辑

编写一个实现 `ISourceGenerator` 接口的类。下面是一个简单的“Hello World”代码生成器示例：

```csharp
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.Text;
using System.Text;

[Generator]
public class HelloWorldGenerator : ISourceGenerator
{
    public void Initialize(GeneratorInitializationContext context) { }

    public void Execute(GeneratorExecutionContext context)
    {
        string sourceCode = @"
            using System;
            namespace HelloWorldGenerated
            {
                public static class HelloWorld
                {
                    public static void SayHello() => Console.WriteLine(""Hello from the generated code!"");
                }
            }";
        context.AddSource("HelloWorldGenerated", SourceText.From(sourceCode, Encoding.UTF8));
    }
}
```

### 步骤三：在主项目中引用生成器

主项目需引用生成器项目，并在代码中直接使用生成的新类：

```csharp
using HelloWorldGenerated;
class Program
{
    static void Main(string[] args)
    {
        HelloWorld.SayHello();
    }
}
```

编译并运行后，即可在控制台看到由生成器生成的输出。

## 深度应用：典型进阶场景

### 1. 自动依赖注入代码生成

生成器可以自动分析实现某些接口的服务类，并生成依赖注入注册代码。这样，每次新增服务时，无需手动登记，只需规范命名和接口实现即可。

（示例代码已嵌入原文，略）

### 2. 编译期静态校验

通过生成器对带有特定 Attribute 的类进行校验。例如，强制要求某 Attribute 的类必须有无参构造函数，若不满足可抛出编译错误，提升代码规范性。

### 3. 自定义序列化逻辑生成

基于 Attribute 或接口自动为业务类生成高性能、结构化的序列化与反序列化代码，避免运行时反射带来的性能损耗。

### 4. API 客户端代码自动生成

可以根据 OpenAPI/Swagger 规范自动生成 API Client，使客户端代码与服务端保持同步，极大减少手动维护成本。

## 文件驱动型生成器（FileBasedGenerator）：用代码文件驱动代码生成

对于需要从现有代码文件（如 .cs 文件）读取内容并生成新逻辑的场景，可以在生成器中读取 `AdditionalFiles`，并基于其内容生成扩展代码。例如：

```csharp
var sourceFile = context.AdditionalFiles.FirstOrDefault(file => file.Path.EndsWith("MyClass.cs"));
if (sourceFile != null)
{
    var fileContent = sourceFile.GetText(context.CancellationToken)?.ToString();
    // 解析并生成新代码
}
```

这种模式可用于为已有类批量生成扩展方法、辅助工具等，提高代码自动化与一致性。

## 工程实践与最佳实践建议

**性能优化：** 尽量采用增量生成器，避免重复扫描和生成；仅生成必要的代码。

**可维护性：** 生成的代码要遵循项目编码规范，适当注释或文档化，便于后续维护。

**诊断友好：** 利用 C# 12 的诊断系统，为生成代码添加详细的编译期提示和错误，方便开发者定位问题。

**版本兼容：** 生成器升级时要保证兼容性，必要时提供迁移指导。

**源代码管理：** 避免将生成代码纳入版本库，推荐在构建时动态生成，保持主分支干净。

## 总结与展望

随着 C# 12 和 .NET 8 的不断演进，Source Generators 已成为开发者高效提升代码质量、减少重复劳动、提升编译期安全性的利器。从自动样板生成到编译期校验、从依赖注入自动化到 API Client 同步，Source Generators 拓宽了静态分析和元编程的边界。掌握并善用它们，将大幅提升团队的工程效率与代码质量。
