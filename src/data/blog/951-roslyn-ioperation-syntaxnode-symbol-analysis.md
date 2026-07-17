---
pubDatetime: 2026-07-17T14:35:42+08:00
title: "Roslyn 三层分析 API：SyntaxNode vs ISymbol vs IOperation 该怎么选"
description: "Roslyn 编译平台提供了三层分析 API：SyntaxNode、ISymbol 和 IOperation。每一层暴露的信息量和开销不同，选错层会导致分析器误报或漏报。本文对比三个 API 的能力边界、适用场景，并给出选择决策框架和代码示例。"
tags: ["Roslyn", "CSharp", ".NET", "Analyzer", "Compiler"]
slug: "roslyn-ioperation-syntaxnode-symbol-analysis"
ogImage: "../../assets/951/01-cover.jpg"
source: "https://www.devleader.ca/2026/07/16/ioperation-vs-syntaxnode-vs-symbol-in-roslyn-choosing-the-right-analysis-api"
---

你写好了第一个 Roslyn 分析器。`RegisterSyntaxNodeAction` 接上了，`DiagnosticDescriptor` 也定义好了，推到团队项目里。然后有人报 bug："分析器在正确代码上报错了"，或者"用了类型别名后它就漏掉了"。

你去排查，发现根因很简单——你用了语法分析去做需要语义支持的事情。

Roslyn 编译器平台对外暴露了三个不同的分析层，每一层给的信息量和性能开销都不一样。知道什么时候用哪一层，是写出可靠分析器和写出脆弱分析器之间的分水岭。

## 三层概览

Roslyn 编译器按阶段处理代码。每个阶段暴露的信息越来越丰富，但开销也越来越大：

| 层                | API                                                          | 能知道什么                 | 开销 |
| ----------------- | ------------------------------------------------------------ | -------------------------- | ---- |
| 语法（Syntax）    | `SyntaxNode`, `SyntaxToken`                                  | 文本、结构、空白           | 极低 |
| 符号（Symbol）    | `ISymbol`, `INamedTypeSymbol`, `IMethodSymbol`               | 类型、命名空间、声明、特性 | 中等 |
| 操作（Operation） | `IOperation`, `IInvocationOperation`, `IAssignmentOperation` | 语义、控制流、数据流       | 较高 |

可以这样理解：Syntax 层是读代码的原始文本——编译器知道代码长什么样，有什么 token，在哪一行，但还没解析任何类型名。Symbol 层是在解析之后——编译器已经把标识符绑定到了具体的声明上，知道 `var x = new Foo()` 里的 `Foo` 来自哪个程序集。IOperation 层则坐在两者之上：它表示代码**实际做了什么**，跟你用 C# 还是 VB 写的无关。

关键不是选一个就完事了——实际写分析器时经常三层都用。

## SyntaxNode：RegisterSyntaxNodeAction

`RegisterSyntaxNodeAction` 是几乎所有分析器作者的起点，它快、直观、足够应对一大类规则。

### 它能看到什么

`SyntaxNode` 是**具体语法树（CST）**的节点。和抽象语法树不同，CST 保留一切——空格、注释、标点。你源码里的每个 token 在这棵树里都有位置。

语法分析跑在编译器管线的最早期，没有语义信息可用——你不能在这里直接调 `GetTypeInfo()` 或 `GetSymbolInfo()`，除非显式去拿 SemanticModel。

### 它看不到什么

因为语法分析在名称绑定之前执行，编译器还没把标识符解析到具体声明。这是纯语法规则产生误报和漏报的根本原因：

- **类型解析**——你分不出 `System.String` 和一个本地 `String` 别名或自定义 `String` 类
- **重载解析**——你不知道调用的是哪个重载
- **继承成员**——你无法遍历继承链
- **隐式转换和强制转换**——编译器生成的操作不在语法树里

### 适合什么

当规则的正确性不依赖代码含义，只依赖代码说了什么时，用语法层。因为没有 SemanticModel 的开销，这些规则跑得最快，也最容易用裸语法树做单元测试：

- 风格和格式规则（空格、大括号位置、基于正则的命名模式）
- 结构模式约束（如"禁止超过两层的嵌套三元表达式"）
- 注释存在或缺失的检查
- 检测特定句法结构，不管类型

### 示例：检测字段声明中的 var

```csharp
[DiagnosticAnalyzer(LanguageNames.CSharp)]
public sealed class NoVarInFieldsAnalyzer : DiagnosticAnalyzer
{
    private static readonly DiagnosticDescriptor Rule = new(
        id: "DL0001",
        title: "字段声明中不要使用 var",
        messageFormat: "字段 '{0}' 使用了 var，请使用显式类型",
        category: "Style",
        defaultSeverity: DiagnosticSeverity.Warning,
        isEnabledByDefault: true);

    public override ImmutableArray<DiagnosticDescriptor> SupportedDiagnostics =>
        ImmutableArray.Create(Rule);

    public override void Initialize(AnalysisContext context)
    {
        context.ConfigureGeneratedCodeAnalysis(GeneratedCodeAnalysisFlags.None);
        context.EnableConcurrentExecution();

        // 纯语法 — 不需要 SemanticModel
        context.RegisterSyntaxNodeAction(
            AnalyzeFieldDeclaration,
            SyntaxKind.FieldDeclaration);
    }

    private static void AnalyzeFieldDeclaration(SyntaxNodeAnalysisContext ctx)
    {
        var fieldDecl = (FieldDeclarationSyntax)ctx.Node;
        var typeSyntax = fieldDecl.Declaration.Type;

        if (typeSyntax is IdentifierNameSyntax { IsVar: true })
        {
            var name = fieldDecl.Declaration.Variables
                .FirstOrDefault()?.Identifier.Text ?? "unknown";
            ctx.ReportDiagnostic(Diagnostic.Create(
                Rule, typeSyntax.GetLocation(), name));
        }
    }
}
```

这个规则完全在语法层工作。它不需要知道 `var` 解析到什么类型——字段声明里出现 `var` 本身就是违规。

## ISymbol：RegisterSymbolAction

当你需要跟类型系统打交道时——检查一个类的基类、根据返回类型验证方法命名、或者确认某个符号上是否有某个特性——就该用 `RegisterSymbolAction`。

### Symbol 层给你什么

`ISymbol` 是根接口。C# 程序里每个命名元素都有对应的 Symbol：命名空间、类型、方法、属性、字段、参数、局部变量。做分析器最常用的派生接口：

- `INamedTypeSymbol`——类、接口、结构体、枚举、委托。暴露 `.BaseType`、`.Interfaces`、`.GetMembers()`
- `IMethodSymbol`——方法。暴露 `.ReturnType`、`.Parameters`、`.IsAsync`、`.MethodKind`
- `IPropertySymbol`——属性。暴露 `.GetMethod`、`.SetMethod`、`.IsIndexer`
- `IFieldSymbol`——字段。暴露 `.IsConst`、`.IsReadOnly`

这些信息等价于运行时的反射能力，但零运行时开销。

### 适合什么

当规则的正确性依赖**已解析的声明**而非原始文本时，用 Symbol 层：

- 基于类型或修饰符的命名约定（如接口必须以 `I` 开头）
- 检查 `sealed` 类型是否实现了不该实现的接口
- 验证特定 Symbol 上有无特性
- 检查类型的成员完整性和正确性

### 示例：接口命名规则

```csharp
context.RegisterSymbolAction(AnalyzeNamedType, SymbolKind.NamedType);

private static void AnalyzeNamedType(SymbolAnalysisContext ctx)
{
    var type = (INamedTypeSymbol)ctx.Symbol;

    if (type.TypeKind != TypeKind.Interface) return;

    if (!type.Name.StartsWith("I", StringComparison.Ordinal))
    {
        ctx.ReportDiagnostic(Diagnostic.Create(
            Rule, type.Locations.FirstOrDefault(), type.Name));
    }
}
```

这在语法层做不到，因为你需要知道**哪些类型声明是接口**——而 `type.TypeKind == TypeKind.Interface` 需要语义绑定。

## IOperation：RegisterOperationAction

`IOperation` 是信息密度最高的分析层。它表示**绑定的语义树**：在所有类型推断、重载解析、隐式转换和编译器生成代码都应用之后，你的代码实际在做什么。这是用来发现真实语义 bug 的层。

### IOperation 给你什么

每个语句和表达式都有对应的 `IOperation` 表示。常见的：

- `IInvocationOperation`——方法调用。暴露 `.TargetMethod`（完全解析的 `IMethodSymbol`）、`.Arguments`、`.Instance`
- `IAssignmentOperation`——赋值。暴露 `.Target` 和 `.Value`
- `IBinaryOperation`——二元运算符。暴露 `.LeftOperand`、`.RightOperand`、`.OperatorKind`
- `ILocalReferenceOperation`——局部变量引用
- `IReturnOperation`——return 语句。暴露 `.ReturnedValue`
- `IConditionalOperation`——if/三元。暴露 `.Condition`、`.WhenTrue`、`.WhenFalse`

IOperation 层的一个关键优势是**语言无关**。同样的 `IInvocationOperation` 结构，不管是 C# 还是 VB 产生的都一样，你可以写一条规则跨两种语言工作。

### 适合什么

- 检测特定 API 的方法调用（如 async 代码中的 `Thread.Sleep`）
- 发现违反不变量的赋值（如把可变对象赋给只读上下文）
- 跨语言的共享库规则
- 任何不归约到纯语法或命名检查的语义 bug 模式

### 示例：检测 async 方法中的 Thread.Sleep

```csharp
[DiagnosticAnalyzer(LanguageNames.CSharp)]
public sealed class NoThreadSleepInAsyncAnalyzer : DiagnosticAnalyzer
{
    public override void Initialize(AnalysisContext context)
    {
        context.ConfigureGeneratedCodeAnalysis(GeneratedCodeAnalysisFlags.None);
        context.EnableConcurrentExecution();

        context.RegisterOperationAction(
            AnalyzeInvocation, OperationKind.Invocation);
    }

    private static void AnalyzeInvocation(OperationAnalysisContext ctx)
    {
        var invocation = (IInvocationOperation)ctx.Operation;
        var method = invocation.TargetMethod;

        if (!method.Name.Equals("Sleep", StringComparison.Ordinal))
            return;

        if (!method.ContainingType.ToDisplayString().Equals(
                "System.Threading.Thread", StringComparison.Ordinal))
            return;

        if (ctx.ContainingSymbol is IMethodSymbol { IsAsync: true })
        {
            ctx.ReportDiagnostic(Diagnostic.Create(
                Rule, invocation.Syntax.GetLocation()));
        }
    }
}
```

和语法方式的本质区别：`invocation.TargetMethod` 给你的是**完全解析的** `IMethodSymbol`。不存在歧义——`Sleep` 就是 `System.Threading.Thread.Sleep`，不会是别的东西。编译器已经帮你把解析做完了。

## 合起来用：三层组合

实际的分析器很少只待在一层。一个常见模式是：

1. **CompilationStartAction**—解析一次特性类型 Symbol，注册逐块的子分析
2. **OperationBlockStartAction**—用 `blockStart.OwningSymbol` 限定分析范围（如只分析 `[ApiController]` 类型的 public async 方法）
3. **OperationAction**—检测目标调用，用 `operation.Syntax.GetLocation()` 报告位置

下面是一个组合示例：检查标了 `[ApiController]` 的类中，每个 public async 方法是否调用了 `Thread.Sleep`。

```csharp
context.RegisterCompilationStartAction(compilationStart =>
{
    var apiControllerAttr = compilationStart.Compilation
        .GetTypeByMetadataName(
            "Microsoft.AspNetCore.Mvc.ApiControllerAttribute");

    if (apiControllerAttr is null) return;

    compilationStart.RegisterOperationBlockStartAction(blockStart =>
    {
        if (blockStart.OwningSymbol is not IMethodSymbol
        {
            IsAsync: true,
            DeclaredAccessibility: Accessibility.Public,
            ContainingType: INamedTypeSymbol owningType
        }) return;

        bool isApiController = owningType.GetAttributes().Any(a =>
            SymbolEqualityComparer.Default.Equals(
                a.AttributeClass, apiControllerAttr));

        if (!isApiController) return;

        blockStart.RegisterOperationAction(opCtx =>
        {
            var invocation = (IInvocationOperation)opCtx.Operation;
            var method = invocation.TargetMethod;

            if (method.Name == "Sleep" &&
                method.ContainingType.ToDisplayString() ==
                    "System.Threading.Thread")
            {
                opCtx.ReportDiagnostic(Diagnostic.Create(
                    Rule, invocation.Syntax.GetLocation()));
            }
        }, OperationKind.Invocation);
    });
});
```

`RegisterCompilationStartAction` 让你解析一次 `apiControllerAttr`，在每次调用时直接复用，而不需要每次都调用 `GetTypeByMetadataName`。

## 性能注意点

Roslyn 分析器在编辑器的每次按键时都在跑，每个回调必须快速返回。

**最重要的模式**：用 `RegisterCompilationStartAction` 包裹昂贵的一次性查询，内层 action 只做廉价比较。

```csharp
context.RegisterCompilationStartAction(compilationStart =>
{
    var threadType = compilationStart.Compilation
        .GetTypeByMetadataName("System.Threading.Thread");

    if (threadType is null) return; // 库没引用，跳过整个分析器

    compilationStart.RegisterOperationAction(opCtx =>
    {
        var invocation = (IInvocationOperation)opCtx.Operation;
        if (SymbolEqualityComparer.Default.Equals(
                invocation.TargetMethod.ContainingType, threadType))
        {
            // ...
        }
    }, OperationKind.Invocation);
});
```

另外记得在长遍历中检查 `context.CancellationToken.ThrowIfCancellationRequested()`：当用户继续编辑时，Roslyn 会取消旧的分析，过期的分析跑下去只是浪费 CPU。

## 选择决策框架

动手前先问自己：这条规则到底在检查什么？

- **格式、空白、结构模式、纯文本特征**→ SyntaxNode 层（`RegisterSyntaxNodeAction`）
- **命名约定、类型层次、特性存在性、成员检查**→ Symbol 层（`RegisterSymbolAction`）
- **方法调用语义、参数值、数据流、async 模式、跨语言**→ IOperation 层（`RegisterOperationAction`）
- **跨文件聚合、项目级检查**→ `RegisterCompilationStartAction` + 嵌套 action + `RegisterCompilationEndAction`
- **语义分析中需要精确诊断位置**→ IOperation 找到违规，`operation.Syntax.GetLocation()` 报告

不确定时，从 Symbol 层开始。它覆盖最常见的需求——"我想检查这个类型或方法的一些信息"——而不用承担 IOperation 的全部开销。

## 小结

Syntax 分析快且简单，适合风格和结构规则。Symbol 分析引入了类型解析和声明检查，覆盖命名约定和类型层次。IOperation 分析站在最顶层：暴露代码的完整语义意图，捕捉跨语言模式，是所有依赖"代码做了什么"而非"代码长什么样"的规则的正确选择。

从同时使用三层开始：用 Symbol action 圈定分析范围，用 IOperation 检测违规，用 Syntax 报告准确位置。用 `RegisterCompilationStartAction` 包裹昂贵查询，注意 CancellationToken。这个模式覆盖了 .NET 10 下绝大多数实际分析器规则。

如果你需要搭建完整分析器项目的脚手架、NuGet 打包等细节，可以回看 [Roslyn Analyzers 完全指南](https://www.devleader.ca/2026/07/11/roslyn-analyzers-in-c-the-complete-guide)。

如果你关注 .NET 开发、编译器工具链和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [IOperation vs SyntaxNode vs Symbol in Roslyn - Dev Leader](https://www.devleader.ca/2026/07/16/ioperation-vs-syntaxnode-vs-symbol-in-roslyn-choosing-the-right-analysis-api)
- [Roslyn Analyzers in C#: The Complete Guide - Dev Leader](https://www.devleader.ca/2026/07/11/roslyn-analyzers-in-c-the-complete-guide)
- [Build Your First Roslyn Analyzer - Dev Leader](https://www.devleader.ca/2026/07/12/build-your-first-roslyn-analyzer-in-c-diagnostics-and-code-fix-walkthrough)
