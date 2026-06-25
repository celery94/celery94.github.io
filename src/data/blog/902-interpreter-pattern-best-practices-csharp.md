---
pubDatetime: 2026-06-26T07:34:49+08:00
title: "Interpreter 模式最佳实践：让 C# 表达式解析代码干净且可维护"
description: "Interpreter 模式入门容易，但文法一膨胀代码就开始失控——解析逻辑混进表达式类，树结构无法调试，报错信息指不到问题根源。这篇文章梳理了 7 条 C# 下的最佳实践，覆盖文法设计、解析与求值分离、表达式树组织、缓存、错误处理、测试策略以及何时该换用解析器生成器。"
tags: ["Interpreter Pattern", "C#", "Design Patterns", "Best Practices", "DSL"]
slug: "interpreter-pattern-best-practices-csharp"
ogImage: "../../assets/902/01-cover.png"
source: "https://www.devleader.ca/2026/06/24/interpreter-pattern-best-practices-in-c-code-organization-and-maintainability/"
---

把 Interpreter 模式跑通不难——定义一个 `IExpression` 接口，写几个终结符和非终结符表达式类，对着上下文求值就行了。但文法一旦超过玩具示例，事情就开始崩：解析逻辑渗进表达式类里，表达式树 debug 不了，报错信息指不到任何有用的位置。

这篇文章针对这些维护性雷区，梳理了 Interpreter 模式在 C# 下的 7 条实践。不管你是在建规则引擎、配置 DSL 还是数学表达式求值器，这些做法能让代码保持干净和可预测。

## 先把文法写清楚

Interpreter 模式跟文法是一一对应的。文法里的每条规则，都是你代码里的一个类。这种映射既是模式最大的优势，也是最常见的陷阱——文法有歧义，表达式类就跟着歧义，而 debug 歧义的表达式树极其痛苦。

动手写任何代码之前，先写一份形式化文法。哪怕是一小段 BNF 风格的规范，也能迫使你提前想清楚运算符优先级、结合性和边界情况：

```
expression  ::= term (('+' | '-') term)*
term        ::= factor (('*' | '/') factor)*
factor      ::= NUMBER | '(' expression ')'
```

这份文法没有歧义。乘法比加法绑定更紧，括号覆盖优先级，每条规则恰好映射到一个类。

跳过了这一步、让文法在代码中隐式演化的后果：表达式类身兼多职，优先级规则随解析顺序漂移，整个代码库没人能讲清楚到底在解释什么语言。先写文法，保持短小。如果一条规则一句话解释不清，就继续拆。

## 把解析和求值彻底分开

Interpreter 模式在 C# 下影响最大的一条实践：在**解析**和**求值**之间画一条硬线。解析负责把原始输入（字符串、token、配置文件）变成表达式树，求值负责遍历这棵树产出结果。这两件事混在一起，代码就难测、难扩、难调试。

混在一起的典型写法：

```csharp
// 坏写法：解析和求值搅在一起
public class MixedEvaluator
{
    public double Evaluate(string input)
    {
        var tokens = input.Split(' ');
        var left = double.Parse(tokens[0]);
        var op = tokens[1];
        var right = double.Parse(tokens[2]);

        return op switch
        {
            "+" => left + right,
            "-" => left - right,
            _ => throw new InvalidOperationException(
                $"Unknown operator: {op}")
        };
    }
}
```

`"3 + 5"` 能跑，但一遇到嵌套表达式、运算符优先级或需要复用解析结果就崩。拆开之后是这样：

```csharp
public interface IExpression
{
    double Interpret();
}

public sealed class NumberExpression : IExpression
{
    private readonly double _value;
    public NumberExpression(double value) => _value = value;
    public double Interpret() => _value;
}

public sealed class AddExpression : IExpression
{
    private readonly IExpression _left;
    private readonly IExpression _right;

    public AddExpression(IExpression left, IExpression right)
    {
        _left = left
            ?? throw new ArgumentNullException(nameof(left));
        _right = right
            ?? throw new ArgumentNullException(nameof(right));
    }

    public double Interpret()
        => _left.Interpret() + _right.Interpret();
}

// 解析器单独负责构建表达式树
public sealed class ExpressionParser
{
    public IExpression Parse(string input)
    {
        var tokens = input.Split(' ');
        var left = new NumberExpression(double.Parse(tokens[0]));
        var right = new NumberExpression(double.Parse(tokens[2]));

        return tokens[1] switch
        {
            "+" => new AddExpression(left, right),
            _ => throw new FormatException(
                $"Unsupported operator: {tokens[1]}")
        };
    }
}
```

拆开后，解析可以独立测试，求值可以独立测试。可以换解析器而不用动表达式类，可以缓存或序列化表达式树。两部分各自演进，模式才真正有了扩展性。

## 用 Composite 模式组织表达式树

Interpreter 模式的表达式树天然是递归的——一个 `SubtractExpression` 包含两个子表达式，每个子表达式又可能是另一个复合表达式或终结符值。这正是 Composite 模式管的事。

做法很直接：定义清晰的组件接口 `IExpression`，为终结符表达式创建叶子节点，为非终结符表达式创建复合节点：

```csharp
public interface IExpression
{
    double Interpret(
        IReadOnlyDictionary<string, double> context);
}

// 终结符表达式——叶子节点
public sealed class VariableExpression : IExpression
{
    private readonly string _name;

    public VariableExpression(string name)
    {
        _name = name
            ?? throw new ArgumentNullException(nameof(name));
    }

    public double Interpret(
        IReadOnlyDictionary<string, double> context)
    {
        if (!context.TryGetValue(_name, out var value))
        {
            throw new KeyNotFoundException(
                $"Variable '{_name}' is not defined.");
        }
        return value;
    }
}

// 非终结符表达式——复合节点
public sealed class MultiplyExpression : IExpression
{
    private readonly IExpression _left;
    private readonly IExpression _right;

    public MultiplyExpression(IExpression left, IExpression right)
    {
        _left = left
            ?? throw new ArgumentNullException(nameof(left));
        _right = right
            ?? throw new ArgumentNullException(nameof(right));
    }

    public double Interpret(
        IReadOnlyDictionary<string, double> context)
        => _left.Interpret(context) * _right.Interpret(context);
}
```

基于 Composite 的做法带来几个好处：表达式树可遍历、可打印、可变换；新增表达式类型不需要改已有类；每个节点的 `Interpret` 只关心自己的语义，复杂度均匀分布，不会集中在一个单体求值器里。

## 缓存已解析的表达式

解析通常是 Interpreter 模式管道里最贵的一步——切词、建树、校验结构，耗时远超遍历树产出结果。如果同样表达式用不同上下文反复求值（规则引擎、公式求值器），缓存解析好的表达式树就是最直接的性能收益。

把解析和求值拆开后，缓存就自然了：

```csharp
public sealed class CachingInterpreter
{
    private readonly ConcurrentDictionary<string, IExpression>
        _cache = new();
    private readonly ExpressionParser _parser;

    public CachingInterpreter(ExpressionParser parser)
    {
        _parser = parser
            ?? throw new ArgumentNullException(nameof(parser));
    }

    public double Evaluate(
        string expression,
        IReadOnlyDictionary<string, double> context)
    {
        var tree = _cache.GetOrAdd(
            expression,
            key => _parser.Parse(key));
        return tree.Interpret(context);
    }
}
```

`ConcurrentDictionary` 处理了缓存的线程安全问题。相同表达式字符串的每次调用都复用已有树，只跑求值阶段。这之所以可行，是因为设计良好的 Interpreter 模式中表达式树是无状态的——可变状态全在 context 字典里，不在树节点上。

如果文法产出的树很大、内存是个顾虑，可以用 Flyweight 模式减少重复分配。像 `NumberExpression(0)` 或 `NumberExpression(1)` 这样的公共子表达式可以跨树共享，不用每次解析都新建。

## 让错误信息指向问题根源

Interpreter 模式处理的是用户或外部提供的输入，这种输入一定会出问题。变量未定义、运算符收到不兼容的类型、除以零——问题不是会不会出错，而是出错了能不能**报清楚**。

实践是：在离问题最近的地方抛出具体、描述性的异常，带上足够上下文让调用方能修：

```csharp
public sealed class DivideExpression : IExpression
{
    private readonly IExpression _left;
    private readonly IExpression _right;

    public DivideExpression(IExpression left, IExpression right)
    {
        _left = left
            ?? throw new ArgumentNullException(nameof(left));
        _right = right
            ?? throw new ArgumentNullException(nameof(right));
    }

    public double Interpret(
        IReadOnlyDictionary<string, double> context)
    {
        var divisor = _right.Interpret(context);
        if (divisor == 0)
        {
            throw new DivideByZeroException(
                "Division by zero in expression. " +
                "The right operand evaluated to 0.");
        }
        return _left.Interpret(context) / divisor;
    }
}

// 自定义异常，带位置信息
public class InterpreterException : Exception
{
    public int Position { get; }

    public InterpreterException(string message, int position)
        : base(message)
    {
        Position = position;
    }
}
```

自定义的 `InterpreterException` 带位置信息，调用方能精确知道原始输入中哪里出了问题。这对处理多行 DSL 或复杂公式的场景至关重要——没有位置追踪，用户看到"undefined variable"，根本不知道是 50 个 token 里哪个变量炸的。

解析阶段的错误要在解析时就拦下来，不要等到求值。检查括号是否匹配、是否有意料之外的 token、是否缺操作数——这些问题在解析阶段拒绝掉，远比求值到一半在表达式树深处抛 `NullReferenceException` 强。

## 为文法规则写测试

Interpreter 模式"一条规则一个类"的结构让它天然好测。每个表达式类都是小而聚焦的单元，只有一个 `Interpret` 方法。测试策略也很自然：终结符表达式单独测，非终结符表达式用已知子表达式注入测，解析器用已知输入输出对测。

先是终结符——没有依赖，最直接：

```csharp
public class NumberExpressionTests
{
    [Theory]
    [InlineData(0)]
    [InlineData(42.5)]
    [InlineData(-7)]
    public void Interpret_ReturnsStoredValue(double expected)
    {
        var expression = new NumberExpression(expected);
        var context = new Dictionary<string, double>();
        var result = expression.Interpret(context);
        Assert.Equal(expected, result);
    }
}

public class VariableExpressionTests
{
    [Fact]
    public void Interpret_VariableUndefined_Throws()
    {
        var expression = new VariableExpression("y");
        var context = new Dictionary<string, double>();
        Assert.Throws<KeyNotFoundException>(
            () => expression.Interpret(context));
    }
}
```

非终结符表达式，注入已知的子表达式而不是从字符串解析，把表达式逻辑和解析器行为隔离开：

```csharp
public class MultiplyExpressionTests
{
    [Fact]
    public void Interpret_MultipliesBothOperands()
    {
        var left = new NumberExpression(6);
        var right = new NumberExpression(7);
        var multiply = new MultiplyExpression(left, right);
        var context = new Dictionary<string, double>();
        var result = multiply.Interpret(context);
        Assert.Equal(42, result);
    }

    [Fact]
    public void Interpret_HandlesNestedExpressions()
    {
        // (2 + 3) * 4 = 20
        var add = new AddExpression(
            new NumberExpression(2),
            new NumberExpression(3));
        var multiply = new MultiplyExpression(
            add,
            new NumberExpression(4));
        var context = new Dictionary<string, double>();
        var result = multiply.Interpret(context);
        Assert.Equal(20, result);
    }
}
```

最后把解析器当作集成层来测——喂字符串输入，验证产出的表达式树得到的输出是否符合预期。这一步会抓住各个表达式单元测试可能漏掉的文法 bug，比如运算符优先级或结合性错误。

## 什么时候该换解析器生成器

Interpreter 模式适合小而稳定的文法。四个运算符加括号和变量的数学求值器用着舒服，十几个关键字的配置 DSL 也管得住。但每种文法都有一个复杂度阈值，超过之后 Interpreter 模式就不再是合适的工具。

这些信号说明你的实现已经超出模式的承载能力：

- **超过 15-20 个表达式类。**一条规则一个类的开销开始超过模式本身的简洁性。
- **文法规则有歧义。**你在解析器里写特殊逻辑来解决歧义，说明文法需要形式化工具。
- **解析对性能敏感。**手写递归下降解析器跑不过生成器产出的表驱动解析器。
- **需要错误恢复。**如果用户需要带建议和恢复能力的错误提示——像编程语言那样——Interpreter 模式基于异常的简单报错就不够用了。

到了这个阈值，考虑 [ANTLR](https://www.antlr.org/) 或 [Pidgin](https://github.com/benjamin-hodgson/Pidgin)（一个 C# 的轻量解析器组合子库）。ANTLR 从文法文件生成完整词法分析和语法分析器，产出可遍历的解析树。Pidgin 让你在 C# 代码里用小构件组合解析器——介于 Interpreter 模式和完整解析器生成器之间的中间地带。

过渡不需要一步到位。你可以保留 Interpreter 模式的表达式类继续做求值，只把解析层换成生成的解析器。已有的求值逻辑和测试套件不动，同时获得专用工具的语法处理能力。

## 把项目结构也组织好

最后一条实践：想清楚你的类住在项目的哪里。常见错误是把所有表达式类、解析器、上下文、缓存全倒进一个 namespace。五个类还好，二十个就崩了。

按职责组织：

```
Interpreter/
├── Expressions/
│   ├── IExpression.cs
│   ├── NumberExpression.cs
│   ├── VariableExpression.cs
│   ├── AddExpression.cs
│   ├── SubtractExpression.cs
│   ├── MultiplyExpression.cs
│   └── DivideExpression.cs
├── Parsing/
│   ├── Token.cs
│   ├── Tokenizer.cs
│   └── ExpressionParser.cs
├── Context/
│   └── InterpreterContext.cs
├── Caching/
│   └── CachingInterpreter.cs
└── Errors/
    └── InterpreterException.cs
```

每个文件夹对应一个独立关注点。Expressions 只管求值，Parsing 管文本到树的转换，Context 管运行时状态，Caching 管复用优化，Errors 管结构化反馈。新同事加入团队时，文件夹名就告诉他该看哪里、往哪放。

这种结构也方便用访问修饰符强制边界。把具体表达式类标 `internal`，只让解析器来创建它们。对外暴露 `IExpression` 和解析器作为公开 API，防止外部代码绕过解析器直接手工拼表达式树进而跳过校验。Interpreter 模式保持自包含——一个干净模块，窄公开面。

## 小结

这 7 条实践贯穿一个共同的主题：把文法在写代码之前形式化定义，把解析和求值彻底拆开，用 Composite 原则组织表达式树，把校验推到输入进入系统的边界（解析层），出错时带上位置信息。

Interpreter 模式在文法小、稳定、直接映射到类层级时最强。先从解决你问题的最简文法开始——几个终结符表达式、两三个运算符、一个直接的递归下降解析器。随着需求增长再加变量支持、缓存和更丰富的错误处理。当文法超出模式的承载，把解析层迁移到专用工具，同时保留久经考验的表达式类不动。目标不是最大化抽象，而是一个可预测、可独立测试、团队里每个开发者都容易扩展的解释器。

> 如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- [原文：Interpreter Pattern Best Practices in C#](https://www.devleader.ca/2026/06/24/interpreter-pattern-best-practices-in-c-code-organization-and-maintainability/)
