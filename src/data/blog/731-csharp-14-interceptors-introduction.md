---
pubDatetime: 2026-04-13T11:18:53+08:00
title: "C# 14 拦截器（Interceptors）：编译期调用替换机制详解"
description: "C# 14 正式将 Interceptors 升为稳定特性。这篇文章解释拦截器是什么、如何在编译期悄然替换特定调用点、与 Source Generator 的必然联系，以及它真正适合谁来用——不是日常业务代码，而是框架和库作者。"
tags: ["CSharp", "dotnet", ".NET 10", "Source Generator", "编译器"]
slug: "csharp-14-interceptors-introduction"
ogImage: "../../assets/731/01-cover.png"
source: "https://anthonygiretti.com/2025/11/15/c-14-introducing-interceptors/"
---

## 这个特性在解决什么问题

C# 14 和 .NET 10 将一个叫做 **Interceptor（拦截器）** 的特性升为正式稳定状态。它在 C# 12 时就以预览形式出现，用了两年时间才走到这一步。

拦截器能做的事情只有一件，但这件事很不寻常：**在编译期，将某个特定调用点的方法调用，悄然替换成另一个方法**——无需修改原有代码，无需接口，无需代理，也不带任何运行时开销。

## 一句话概念

拦截器向编译器说的是：「每次你在源码里的这个具体位置看到对方法 X 的调用，改成调用我。」

调用方写的是完全正常的代码。编译器在生成 IL 之前，就已经悄悄把那个调用点换掉了。编译出来的二进制里没有任何间接层，没有包装对象，也没有运行时性能损耗。

## 一个直观比喻

原作者的比喻很准确：这就像 GPS 在你出门之前就已经重新规划了路线，等你上车的时候，那条新路已经是唯一的路。原来那条路还在，只是你这次出行在计划阶段就被重定向了，不是在行驶过程中。

## 实际代码长什么样

假设你有一个库提供了 `Logger.Log` 方法，你的应用代码里这样调用它：

```csharp
// 开发者写的代码
Logger.Log("Order created", LogLevel.Information);
```

没有拦截器时，这个调用在运行时直接走 `Logger.Log`。有了拦截器之后，编译器会在生成 IL 之前，把这个调用点替换成一个生成的方法：

```csharp
// 编译进 IL 里的实际调用——开发者看不到
GeneratedInterceptors.Log_Intercepted_0("Order created", LogLevel.Information);
```

原始的 `Logger.Log` 在库里依然存在，但那个特定调用点永远不会再触达它，拦截器已经完全取而代之。

## 编译器怎么知道该拦截哪个调用点

这是拦截器最独特的地方。编译器拦截的不是**所有**对某个方法的调用，而是**源码里某个具体位置**的那一次调用。位置信息通过一个属性写在拦截器方法上：

```csharp
// 这个 attribute 编码了被拦截调用点的精确位置：
// 文件路径 + 行号 + 列号，压缩成一段 base64 字符串
[InterceptsLocationAttribute(1, "qjmcoI/hUdYHdlM5/alrVYsBAABPcmRlclNlcnZpY2UuY3M=")]
internal static void Log_Intercepted_0(string message, LogLevel level)
{
    // 替代逻辑——零分配、AOT 兼容、可加审计追踪等
    StructuredLogger.Write(level, message);
}
```

`[InterceptsLocationAttribute]` 的 `data` 参数是一个 base64 字符串，编码了文件路径、行号、列号和调用点内容的哈希值。这个值在每次构建时由编译器重新计算——这正是为什么拦截器**必须由 Source Generator 生成，不能手写**。

如果你硬编码这个 `data` 值，项目在当前状态下能编译，但只要有人在被拦截调用的上方添加一行代码，这个位置就失效了——不会有编译报错，只会有悄悄发生的运行时行为错误。

## 和其他机制的本质区别：编译期 vs 运行期

.NET 里大多数横切关注点的机制都在运行时工作，拦截器在编译时工作，这个区别带来了实质性的不同：

- **动态代理**（Castle Windsor、Autofac）：在应用启动时用反射和 IL emit 生成包装类，需要虚方法或接口，不兼容 Native AOT。
- **IL 织入**（PostSharp、Fody）：在编译后重写 IL，不需要接口，但对源码和 IDE 完全不透明。
- **拦截器**（C# 14）：在编译期、IL 生成之前替换调用点，无反射，无虚分发，无运行时开销，完全兼容 Native AOT，且在生成的 `.g.cs` 文件里可见。

经过拦截器替换的调用，在编译后的二进制里与直接写那个替代方法毫无区别。

## 适合用来做什么

原作者明确指出：拦截器不是日常编码的通用工具，它面向的是**库和框架作者**，用于在不改变开发者体验的前提下，透明地优化或增强调用点。几个具体场景：

**零分配日志**：把 `ILogger.LogInformation(message, args)` 替换成预编译的 `LoggerMessage.Define` 委托，消除每次调用时 `params object[]` 带来的装箱。

**自动注入请求头**：拦截每一处 `HttpClient.SendAsync` 调用，注入关联 ID（correlation ID），无需开发者记得注册 `DelegatingHandler`。

**Native AOT 支持**：把依赖反射的调用在编译期替换成源码生成的等价实现，让以前无法 AOT 的代码开箱可用。ASP.NET Core 内部已经在 Minimal API 路由上这样做了。

**编译期配置校验**：拦截配置访问，在构建时就验证 `appsettings.json` 里的 key 是否存在，把运行时 `null` 异常变成编译报错。

**透明遥测**：在特定调用点包一层 OpenTelemetry `Activity` span，不污染业务逻辑。

## 它不是什么

同样重要的是弄清楚拦截器不适合做什么：

**它不是依赖注入的替代品。** 拦截器在编译时针对特定调用点工作，无法根据运行时条件或配置动态切换实现。

**它不应该手写。** `[InterceptsLocationAttribute]` 里的位置编码只要源文件被修改就会变，只有 Source Generator 才能可靠地维护它。

**它不会拦截某个方法的所有调用。** 每个拦截器只针对一个具体调用点——同一个方法在十处被调用，就需要十个拦截器（Generator 会自动生成）。

**谁该直接用拦截器？** 如果你在构建 NuGet 包、框架或内部平台库，想要透明地优化或增强消费者代码，拦截器是为你设计的。如果你在写应用业务逻辑，你会通过使用的库间接受益于拦截器，而不是自己写。

## 与 Source Generator 的关系

实践中，每一个拦截器都由 Source Generator 生成。Generator 的职责是：遍历消费者项目的语法树，找到目标调用点，通过 `SemanticModel.GetInterceptableLocation()` 向 Roslyn 获取编码后的位置，然后输出一个包含替代方法和正确 `[InterceptsLocationAttribute]` 值的 C# 文件。

消费者项目需要在 `.csproj` 里声明 Generator 的命名空间，将其加入 `<InterceptorsNamespaces>`。这是一个有意为之的安全机制——第三方包不能在你不知情的情况下悄然拦截你的调用。

拦截器和 Source Generator 的关系不是偶然的，而是设计使然。拦截器给了 Source Generator 一个之前缺失的能力：**修改已有的调用点**，而不仅仅是在旁边新增代码。

## 小结

Interceptor 是一个编译期调用点替换机制。它让 Source Generator 能够透明地把特定方法调用换成另一套实现，零运行时开销、完整的 Native AOT 兼容性，消费者代码一行不改。它不是 DI 替代方案，不是通用 AOP 工具，也不是拿来手写的东西。它是一个精准、手术式的机制，供框架和库作者在不触碰任何业务逻辑的前提下，优化或增强整个代码库里的调用点。

下一篇文章里，原作者将把这个机制带入实战：构建一个 Source Generator，拦截所有 `HttpClient.SendAsync` 调用，自动注入关联请求头——不需要 `DelegatingHandler`，不需要手动串联，开发者也无法意外遗漏。

## 参考

- [C# 14: Introducing Interceptors – Anthony Giretti's .NET blog](https://anthonygiretti.com/2025/11/15/c-14-introducing-interceptors/)
- [C# 14: Interceptors in practice with automatic correlation headers](https://anthonygiretti.com/2025/11/15/c-14-interceptors-in-practice-with-automatic-correlation-headers/)
