---
pubDatetime: 2026-05-25T13:00:00+08:00
title: "C# 自定义特性实战：验证、插件注册和命令路由的完整实现"
description: "自定义特性是 C# 框架机制的底层基础——验证框架、MVC 路由和插件系统都依赖它。本文从 Attribute 的基础定义出发，通过验证约束、插件扫描和命令路由三个完整实例演示如何用反射读取运行时元数据，并介绍热路径下的缓存策略和源代码生成器的适用边界。"
tags: ["C#", "Reflection", ".NET", "Design Patterns"]
slug: "csharp-custom-attributes-reflection-practical-examples"
ogImage: "../../assets/829/01-cover.png"
source: "https://www.devleader.ca/2026/05/23/custom-attributes-in-c-build-apply-and-read-them-with-reflection"
---

`[HttpGet]`、`[Authorize]`、`[Required]` ——这些你在 ASP.NET Core 里每天用的特性，背后都是同一个机制：一个继承自 `System.Attribute` 的类、一段用反射读取它的运行时代码。理解这个机制之后，你可以给自己的代码加上同样的扩展点。

这篇文章从定义原则出发，完整展示如何在三个真实场景中构建和使用自定义特性：属性验证、插件注册和命令路由。

## 特性是什么，不是什么

特性是**元数据**，不是行为。它是一个继承自 `System.Attribute` 的类，可以附加在类、方法、属性、参数和程序集上。编译器在编译时把特性数据编码进程序集的元数据表，运行时不会有任何事情自动发生。

特性是被动的。它不拦截方法调用，不修改行为，不在附加时做任何事。只有当某段代码主动用反射去读取它时，它才产生效果。

这和 PostSharp 之类的 AOP 工具不同，也和 `MethodImpl` 这种会直接指示 JIT 的特性不同。你自己写的自定义特性通常都是纯元数据。

## 定义自定义特性类

每个自定义特性继承自 `System.Attribute`，并用 `[AttributeUsage]` 标注自身，控制它可以出现在哪里、能否重复应用：

```csharp
[AttributeUsage(
    AttributeTargets.Property,
    AllowMultiple = false,
    Inherited = true)]
public sealed class RequiredAttribute : Attribute
{
    public string ErrorMessage { get; }

    public RequiredAttribute(string errorMessage = "This field is required.")
    {
        ErrorMessage = errorMessage;
    }
}
```

几条命名和设计规范：

- 类名以 `Attribute` 结尾。应用时可以省略后缀（写 `[Required]` 而不是 `[RequiredAttribute]`），但类名本身应该带后缀。
- 除非打算继承，否则加 `sealed`。
- 构造函数参数必须是编译时常量：字面量、`typeof()`、`nameof()` 或枚举值。变量和方法返回值不允许。
- 通过命名参数（`[MyAttr(Name = "foo")]`）设置的属性必须有 public setter。

## AttributeUsage 的三个参数

`[AttributeUsage]` 控制三件事：

**`AttributeTargets`** 是一个标志枚举，指定允许应用的位置。常用值：

| 值 | 适用位置 |
|---|---|
| `Class` | 类声明 |
| `Method` | 方法声明 |
| `Property` | 属性声明 |
| `Parameter` | 方法/构造函数参数 |
| `Assembly` | 程序集级别 |
| `All` | 所有合法目标 |

可以组合：`AttributeTargets.Class | AttributeTargets.Interface`。

**`AllowMultiple`** 为 `true` 时，同一特性可以多次应用在同一目标上。对路由模板、允许的角色列表、命令别名这类场景很有用。默认 `false`。

**`Inherited`** 为 `true` 时，调用 `GetCustomAttributes(inherit: true)` 时会包含基类上的特性。默认 `true`，但注意这对属性和参数上的特性不生效，只对类和方法有效。

## 在各种代码元素上应用特性

```csharp
// 在类上
[PluginMetadata("OrderProcessor", Version = "1.0")]
public sealed class OrderProcessorPlugin : IPlugin { }

// 在方法上
[Command("greet")]
public void HandleGreet(string name) { }

// 在属性上（可以叠加）
[Required("Name is required.")]
[MaxLength(100)]
public string Name { get; set; } = string.Empty;

// 在参数上
public void Process([NotNull] string input) { }

// 在程序集上（通常放在 AssemblyInfo.cs，命名空间外面）
[assembly: AssemblyVersion("1.0.0.0")]
```

`AllowMultiple = true` 的特性可以在同一目标上多次出现。

## 用反射读取特性

读取特性的主要 API 在 `System.Reflection` 里。`Type`、`MethodInfo`、`PropertyInfo` 等都继承自 `MemberInfo`，都提供这些方法：

```csharp
// 读取单个特性，找不到时返回 null
RequiredAttribute? attr = propertyInfo.GetCustomAttribute<RequiredAttribute>();

// 读取同类型的所有特性（AllowMultiple 场景）
IEnumerable<MaxLengthAttribute> allAttrs =
    propertyInfo.GetCustomAttributes<MaxLengthAttribute>();

// 读取全部特性，非泛型版本
object[] allRaw = propertyInfo.GetCustomAttributes(inherit: true);
```

`inherit` 参数决定是否包含基类成员上的特性，大多数验证场景传 `true`。

## 实战一：属性验证

自定义特性最直接的用法是在属性上标注约束，再用一个 validator 在运行时检查：

```csharp
[AttributeUsage(AttributeTargets.Property)]
public sealed class RequiredAttribute : Attribute
{
    public string ErrorMessage { get; init; } = "This field is required.";
}

[AttributeUsage(AttributeTargets.Property)]
public sealed class MaxLengthAttribute : Attribute
{
    public int Length { get; }
    public MaxLengthAttribute(int length) => Length = length;
}
```

读取并执行约束的 validator：

```csharp
public static class ObjectValidator
{
    public static IReadOnlyList<string> Validate(object instance)
    {
        var errors = new List<string>();
        Type type = instance.GetType();

        foreach (PropertyInfo prop in type.GetProperties(
            BindingFlags.Public | BindingFlags.Instance))
        {
            object? value = prop.GetValue(instance);

            var required = prop.GetCustomAttribute<RequiredAttribute>();
            if (required is not null
                && string.IsNullOrWhiteSpace(value?.ToString()))
            {
                errors.Add($"{prop.Name}: {required.ErrorMessage}");
            }

            var maxLength = prop.GetCustomAttribute<MaxLengthAttribute>();
            if (maxLength is not null
                && value is string str
                && str.Length > maxLength.Length)
            {
                errors.Add(
                    $"{prop.Name}: Must be {maxLength.Length} characters or fewer.");
            }
        }

        return errors;
    }
}
```

使用方式：

```csharp
public sealed class CreateOrderRequest
{
    [Required]
    [MaxLength(200)]
    public string CustomerName { get; init; } = string.Empty;

    [Required]
    public string ProductId { get; init; } = string.Empty;
}

var request = new CreateOrderRequest { CustomerName = "", ProductId = "P001" };
var errors = ObjectValidator.Validate(request);
// errors 包含: "CustomerName: This field is required."
```

FluentValidation、DataAnnotations 以及 .NET 生态里所有基于特性的验证框架，本质上都是这个循环。

## 实战二：插件注册

加载外部程序集时需要找出所有插件类型，特性扫描是比标记接口更干净的注册方式：

```csharp
[AttributeUsage(
    AttributeTargets.Class,
    AllowMultiple = false,
    Inherited = false)]
public sealed class PluginMetadataAttribute : Attribute
{
    public string Name { get; }
    public string Description { get; init; } = string.Empty;
    public string Version { get; init; } = "1.0.0";

    public PluginMetadataAttribute(string name)
    {
        Name = name;
    }
}
```

扫描程序集发现所有插件：

```csharp
public static IReadOnlyList<(Type Type, PluginMetadataAttribute Metadata)>
    DiscoverPlugins(Assembly assembly)
{
    return assembly.GetTypes()
        .Where(t => t.IsClass && !t.IsAbstract)
        .Select(t => (
            Type: t,
            Metadata: t.GetCustomAttribute<PluginMetadataAttribute>()))
        .Where(x => x.Metadata is not null)
        .Select(x => (x.Type, Metadata: x.Metadata!))
        .ToList();
}
```

一个插件实现：

```csharp
[PluginMetadata(
    "OrderProcessor",
    Description = "Handles order processing pipeline",
    Version = "2.1.0")]
public sealed class OrderProcessorPlugin : IPlugin
{
    public void Execute(IPluginContext context) { /* ... */ }
}
```

这个模式不要求插件实现任何标记接口，注册信息（名称、版本、描述）直接附加在类型本身，扫描时一次性读取。

## 实战三：命令路由

CLI 工具和聊天机器人框架常用特性把字符串命令映射到处理方法：

```csharp
[AttributeUsage(AttributeTargets.Method, AllowMultiple = true)]
public sealed class CommandAttribute : Attribute
{
    public string Name { get; }
    public CommandAttribute(string name) => Name = name;
}
```

`AllowMultiple = true` 让同一方法可以绑定多个命令名。构建命令注册表：

```csharp
public sealed class CommandRegistry
{
    private readonly Dictionary<string, MethodInfo> _commands =
        new(StringComparer.OrdinalIgnoreCase);
    private readonly object _handler;

    public CommandRegistry(object handler)
    {
        _handler = handler;

        foreach (MethodInfo method in handler.GetType()
            .GetMethods(BindingFlags.Public | BindingFlags.Instance))
        {
            foreach (var attr in method.GetCustomAttributes<CommandAttribute>())
            {
                _commands[attr.Name] = method;
            }
        }
    }

    public bool TryInvoke(string commandName, string[] args)
    {
        if (!_commands.TryGetValue(commandName, out MethodInfo? method))
        {
            return false;
        }

        method.Invoke(_handler, new object[] { args });
        return true;
    }
}
```

处理器类：

```csharp
public sealed class BotCommandHandler
{
    [Command("help")]
    [Command("?")]  // AllowMultiple = true 才允许这样写
    public void HandleHelp(string[] args)
    {
        Console.WriteLine("Available commands: help, greet, status");
    }

    [Command("greet")]
    public void HandleGreet(string[] args)
    {
        string name = args.Length > 0 ? args[0] : "World";
        Console.WriteLine($"Hello, {name}!");
    }
}
```

`HandleHelp` 同时响应 `help` 和 `?` 两个命令名，这是 `AllowMultiple = true` 的直接体现。

## 热路径要缓存反射结果

`GetCustomAttribute<T>()` 每次调用都会扫描成员的元数据。在验证场景中，如果每秒要验证数千个对象，这个开销会积累起来。

解决方法：按 `Type` 或 `MemberInfo` 缓存结果：

```csharp
public static class AttributeCache
{
    private static readonly ConcurrentDictionary<PropertyInfo, RequiredAttribute?>
        _required = new();

    public static RequiredAttribute? GetRequired(PropertyInfo prop)
        => _required.GetOrAdd(
            prop,
            static p => p.GetCustomAttribute<RequiredAttribute>());
}
```

第一次调用时通过反射读取，结果存入 `ConcurrentDictionary`。后续调用直接返回缓存值，不再走反射。这个模式适用于所有在热路径里读取特性的场景。

也可以在类型首次被验证时一次性扫描所有属性上的特性，把结果存进一个按 `Type` 索引的静态字典，比逐属性缓存更彻底。

## 源代码生成器：在编译期处理特性

反射读取特性是运行时操作，每次都有开销。.NET 的 Roslyn 源代码生成器让你在编译期处理特性并生成代码，运行时完全不需要反射。

选哪种方式取决于场景：

- **插件系统**：类型在运行时从外部程序集动态加载，只能用反射。
- **你自己控制的类型**：如果所有类型都是源代码形式、性能要求高，源代码生成器更合适。

源代码生成器更复杂，需要实现 `IIncrementalGenerator`，但生成的代码没有任何反射开销。性能敏感的框架（如 AOT 场景）通常会这样做。

## 几个常见问题

**特性的构造函数可以传变量吗**：不可以。必须是编译时常量：字符串字面量、数值字面量、`typeof()`、`nameof()` 或枚举值。原因是编译器在编译时就把参数编码进元数据，这时还不存在运行时值。

**应用了不允许的特性会怎样**：编译时报错。C# 编译器会检查 `AttributeUsage` 限定的范围，如果你把一个只允许用在属性上的特性用在方法上，编译器会拒绝并提示类似 `Attribute 'RequiredAttribute' is not valid on this declaration type.` 的错误。

**只想检查特性是否存在，不需要读取数据怎么做**：用 `IsDefined`，比 `GetCustomAttribute` 稍快：

```csharp
bool hasRequired = propertyInfo.IsDefined(
    typeof(RequiredAttribute),
    inherit: true);
```

**`GetCustomAttribute` 是线程安全的吗**：是的。.NET 的反射 API 读取元数据是线程安全的，程序集加载后元数据是只读的，多个线程可以并发读取同一个 `MemberInfo` 上的特性。

**基类上的特性怎么读取**：调用 `GetCustomAttributes` 或 `IsDefined` 时传 `inherit: true`，反射会遍历继承链包含基类成员上的特性。注意这只对类和方法有效，`PropertyInfo.GetCustomAttributes(inherit: true)` 不会自动遍历基类属性链。

## 结语

C# 自定义特性的核心模式三步：继承 `Attribute` 定义类、用 `[AttributeUsage]` 限定范围、运行时用 `GetCustomAttribute<T>()` 读取。

验证、插件注册和命令路由覆盖了大多数真实场景，它们的核心代码结构都一样：获取类型的成员，检查每个成员上有没有目标特性，根据特性数据执行逻辑。

热路径里要缓存反射结果。类型源代码可控且性能要求高时，考虑把反射替换为源代码生成器。特性本身是被动的——在你主动读取它们之前，什么都不会发生。

如果你关注 C#、.NET 开发实践和工具效率，可以关注 Aide Hub。这里会持续分享能落地的技术教程和工程经验。

## 参考

- [Custom Attributes in C#: Build, Apply, and Read Them with Reflection](https://www.devleader.ca/2026/05/23/custom-attributes-in-c-build-apply-and-read-them-with-reflection)
- [Reflection in C#: 4 Simple But Powerful Code Examples](https://www.devleader.ca/2024/02/26/reflection-in-c-4-simple-but-powerful-code-examples)
- [Plugin Architecture in C#: The Complete Guide to Extensible .NET Applications](https://www.devleader.ca/2026/04/07/plugin-architecture-in-c-the-complete-guide-to-extensible-net-applications)
- [Source Generation vs Reflection in Needlr](https://www.devleader.ca/2026/02/07/source-generation-vs-reflection-in-needlr-choosing-the-right-approach)
