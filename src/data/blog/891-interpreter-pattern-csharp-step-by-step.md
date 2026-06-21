---
pubDatetime: 2026-06-21T15:24:50+08:00
title: "Interpreter Pattern in C#：从表达式到 AST 求值"
description: "这篇文章用一个小型算术表达式解释器讲清 Interpreter Pattern：定义表达式接口，拆出终结符和非终结符，加入变量上下文，再写 parser 和测试验证优先级与求值结果。"
tags: ["C#", "设计模式", "Interpreter Pattern", "AST", "单元测试"]
slug: "interpreter-pattern-csharp-step-by-step"
source: "https://www.devleader.ca/2026/06/20/how-to-implement-interpreter-pattern-in-c-stepbystep-guide"
ogImage: "../../assets/891/01-cover.png"
---

Interpreter Pattern 适合处理一种“小语言”：比如算术表达式、规则表达式、模板语法、查询条件、配置语法。它的核心做法很朴素：把语法规则变成类，把输入解析成一棵树，然后让树上的每个节点自己解释自己。

原文用 C# 写了一个算术表达式解释器。这个例子足够小，但关键零件都齐了：`IExpression`、终结符表达式、非终结符表达式、变量上下文、递归下降 parser，以及 xUnit 测试。读完后，你应该能自己扩展除法、取模、函数调用这类新规则。

## 适合什么场景

Interpreter Pattern 更适合语法清楚、规模可控、需要反复解析和求值的场景：

- 数学表达式求值器
- 规则引擎
- 查询语言处理
- 模板引擎
- 配置文件解析

如果语法很大、规则很多、错误恢复复杂，类层级会快速膨胀。那时可以考虑 ANTLR 这类 parser generator。Interpreter Pattern 的优势在于小而清楚，适合把“语法树如何执行”讲明白。

## 定义表达式接口

所有节点先共用一个接口：

```csharp
public interface IExpression
{
    double Interpret(InterpreterContext context);
}
```

`Interpret()` 接收一个 `InterpreterContext`，返回 `double`。数字、变量、加法、减法、乘法都实现这个接口。调用方不用关心当前节点是叶子节点还是组合节点，只管调用 `Interpret()`。

这里的 `InterpreterContext` 会在后面定义，它负责存放变量值，比如 `x = 10`、`y = 5`。

## 写终结符节点

终结符是语法树的叶子节点。它们不再包含其他表达式，解释时直接给出值。

### 数字节点

`NumberExpression` 包住一个常量数字：

```csharp
public sealed class NumberExpression : IExpression
{
    private readonly double _value;

    public NumberExpression(double value)
    {
        _value = value;
    }

    public double Interpret(InterpreterContext context)
    {
        return _value;
    }
}
```

### 变量节点

`VariableExpression` 保存变量名，求值时去上下文里查：

```csharp
public sealed class VariableExpression : IExpression
{
    private readonly string _name;

    public VariableExpression(string name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            throw new ArgumentException(
                "Variable name cannot be null or empty.",
                nameof(name));
        }

        _name = name;
    }

    public double Interpret(InterpreterContext context)
    {
        return context.GetVariable(_name);
    }
}
```

同一棵表达式树可以配不同上下文。比如树表示 `x + 3`，当 `x = 10` 时结果是 `13`，当 `x = 20` 时结果是 `23`。

## 写组合节点

非终结符节点会包含子表达式。加法、减法、乘法都可以写成左右两个孩子：

```csharp
public sealed class AddExpression : IExpression
{
    private readonly IExpression _left;
    private readonly IExpression _right;

    public AddExpression(IExpression left, IExpression right)
    {
        _left = left ?? throw new ArgumentNullException(nameof(left));
        _right = right ?? throw new ArgumentNullException(nameof(right));
    }

    public double Interpret(InterpreterContext context)
    {
        return _left.Interpret(context) + _right.Interpret(context);
    }
}
```

减法和乘法结构一样，只是运算符不同：

```csharp
public sealed class SubtractExpression : IExpression
{
    private readonly IExpression _left;
    private readonly IExpression _right;

    public SubtractExpression(IExpression left, IExpression right)
    {
        _left = left ?? throw new ArgumentNullException(nameof(left));
        _right = right ?? throw new ArgumentNullException(nameof(right));
    }

    public double Interpret(InterpreterContext context)
    {
        return _left.Interpret(context) - _right.Interpret(context);
    }
}

public sealed class MultiplyExpression : IExpression
{
    private readonly IExpression _left;
    private readonly IExpression _right;

    public MultiplyExpression(IExpression left, IExpression right)
    {
        _left = left ?? throw new ArgumentNullException(nameof(left));
        _right = right ?? throw new ArgumentNullException(nameof(right));
    }

    public double Interpret(InterpreterContext context)
    {
        return _left.Interpret(context) * _right.Interpret(context);
    }
}
```

这里的递归发生得很自然。`AddExpression` 调用左孩子和右孩子的 `Interpret()`，孩子可能是数字，也可能是另一棵子树。整棵树会从叶子一路算到根节点。

要加除法，可以照这个结构写 `DivideExpression`，再让 parser 识别 `/`。

## 准备上下文

上下文保存变量绑定，并在变量不存在时给出明确错误：

```csharp
public sealed class InterpreterContext
{
    private readonly Dictionary<string, double> _variables;

    public InterpreterContext()
    {
        _variables = new Dictionary<string, double>(
            StringComparer.OrdinalIgnoreCase);
    }

    public void SetVariable(string name, double value)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            throw new ArgumentException(
                "Variable name cannot be null or empty.",
                nameof(name));
        }

        _variables[name] = value;
    }

    public double GetVariable(string name)
    {
        if (!_variables.TryGetValue(name, out double value))
        {
            throw new KeyNotFoundException(
                $"Variable '{name}' is not defined.");
        }

        return value;
    }

    public bool HasVariable(string name)
    {
        return _variables.ContainsKey(name);
    }
}
```

原文这里用了 `StringComparer.OrdinalIgnoreCase`，所以 `x` 和 `X` 会指向同一个变量。这个选择适合简单表达式语言，但如果你的 DSL 对大小写敏感，可以换成默认比较器。

## 写一个 parser

手动拼表达式树可以验证思路，但真实输入通常是一段字符串。下面这个 parser 处理数字、变量、括号、加减乘，并让乘法优先级高于加减：

```csharp
public sealed class ExpressionParser
{
    private readonly string _input;
    private int _position;

    public ExpressionParser(string input)
    {
        _input = input ?? throw new ArgumentNullException(nameof(input));
    }

    public IExpression Parse()
    {
        IExpression result = ParseAddSubtract();
        SkipWhitespace();

        if (_position < _input.Length)
        {
            throw new FormatException(
                $"Unexpected character '{_input[_position]}' " +
                $"at position {_position}.");
        }

        return result;
    }

    private IExpression ParseAddSubtract()
    {
        IExpression left = ParseMultiply();

        while (true)
        {
            SkipWhitespace();

            if (_position >= _input.Length)
            {
                break;
            }

            char op = _input[_position];

            if (op != '+' && op != '-')
            {
                break;
            }

            _position++;
            IExpression right = ParseMultiply();

            left = op == '+'
                ? new AddExpression(left, right)
                : new SubtractExpression(left, right);
        }

        return left;
    }

    private IExpression ParseMultiply()
    {
        IExpression left = ParsePrimary();

        while (true)
        {
            SkipWhitespace();

            if (_position >= _input.Length || _input[_position] != '*')
            {
                break;
            }

            _position++;
            IExpression right = ParsePrimary();
            left = new MultiplyExpression(left, right);
        }

        return left;
    }

    private IExpression ParsePrimary()
    {
        SkipWhitespace();

        if (_position >= _input.Length)
        {
            throw new FormatException("Unexpected end of expression.");
        }

        if (_input[_position] == '(')
        {
            _position++;
            IExpression inner = ParseAddSubtract();
            SkipWhitespace();

            if (_position >= _input.Length || _input[_position] != ')')
            {
                throw new FormatException("Missing closing parenthesis.");
            }

            _position++;
            return inner;
        }

        if (char.IsDigit(_input[_position]) || _input[_position] == '.')
        {
            return ParseNumber();
        }

        if (char.IsLetter(_input[_position]))
        {
            return ParseVariable();
        }

        throw new FormatException(
            $"Unexpected character '{_input[_position]}' " +
            $"at position {_position}.");
    }

    private NumberExpression ParseNumber()
    {
        int start = _position;

        while (_position < _input.Length &&
               (char.IsDigit(_input[_position]) ||
                _input[_position] == '.'))
        {
            _position++;
        }

        string text = _input[start.._position];

        if (!double.TryParse(text, out double value))
        {
            throw new FormatException($"Invalid number '{text}'.");
        }

        return new NumberExpression(value);
    }

    private VariableExpression ParseVariable()
    {
        int start = _position;

        while (_position < _input.Length &&
               (char.IsLetterOrDigit(_input[_position]) ||
                _input[_position] == '_'))
        {
            _position++;
        }

        return new VariableExpression(_input[start.._position]);
    }

    private void SkipWhitespace()
    {
        while (_position < _input.Length &&
               char.IsWhiteSpace(_input[_position]))
        {
            _position++;
        }
    }
}
```

这个 parser 用的是递归下降：

- `ParseAddSubtract()` 处理低优先级的 `+` 和 `-`。
- `ParseMultiply()` 处理更高优先级的 `*`。
- `ParsePrimary()` 处理数字、变量和括号。

因此 `3 + 2 * x` 会被解析成 `3 + (2 * x)`。优先级已经写进树结构里，解释器求值时不需要再判断原始字符串里的顺序。

## 组装运行

设置变量，再把表达式字符串解析成树：

```csharp
var context = new InterpreterContext();
context.SetVariable("x", 10);
context.SetVariable("y", 5);
context.SetVariable("z", 3);

string[] expressions =
[
    "x + y",
    "x - y * z",
    "( x + y ) * z",
    "x * y + z",
    "42",
    "x"
];

foreach (string text in expressions)
{
    var parser = new ExpressionParser(text);
    IExpression tree = parser.Parse();
    double result = tree.Interpret(context);

    Console.WriteLine($"{text} = {result}");
}
```

输出结果：

```text
x + y = 15
x - y * z = -5
( x + y ) * z = 45
x * y + z = 53
42 = 42
x = 10
```

`x - y * z` 等于 `-5`，因为 `y * z` 先算，实际是 `10 - (5 * 3)`。`( x + y ) * z` 等于 `45`，因为括号改变了树结构。

也可以绕过 parser，直接用代码拼树：

```csharp
IExpression manualTree = new MultiplyExpression(
    new AddExpression(
        new VariableExpression("x"),
        new NumberExpression(10)),
    new SubtractExpression(
        new VariableExpression("y"),
        new NumberExpression(2)));

double result = manualTree.Interpret(context);
Console.WriteLine(result); // 60
```

这种写法适合表达式来自代码、配置对象或 UI 拖拽编辑器的情况。

## 补上测试

Interpreter Pattern 的测试很好拆。每个节点类都很小，可以单独测；parser 则用输入和结果一起测：

```csharp
using Xunit;

public class InterpreterTests
{
    [Fact]
    public void NumberExpression_ReturnsConstantValue()
    {
        var expr = new NumberExpression(42);
        var context = new InterpreterContext();

        double result = expr.Interpret(context);

        Assert.Equal(42, result);
    }

    [Fact]
    public void VariableExpression_ReturnsContextValue()
    {
        var context = new InterpreterContext();
        context.SetVariable("x", 7);
        var expr = new VariableExpression("x");

        double result = expr.Interpret(context);

        Assert.Equal(7, result);
    }

    [Theory]
    [InlineData("3 + 4", 7)]
    [InlineData("10 - 3", 7)]
    [InlineData("2 * 5", 10)]
    [InlineData("2 + 3 * 4", 14)]
    [InlineData("( 2 + 3 ) * 4", 20)]
    public void Parser_EvaluatesCorrectly(
        string input,
        double expected)
    {
        var parser = new ExpressionParser(input);
        IExpression tree = parser.Parse();
        var context = new InterpreterContext();

        double result = tree.Interpret(context);

        Assert.Equal(expected, result);
    }

    [Fact]
    public void Parser_WithVariables_EvaluatesCorrectly()
    {
        var context = new InterpreterContext();
        context.SetVariable("x", 10);
        context.SetVariable("y", 5);

        var parser = new ExpressionParser("x + y * 2");
        IExpression tree = parser.Parse();

        double result = tree.Interpret(context);

        Assert.Equal(20, result);
    }

    [Fact]
    public void Parser_InvalidInput_ThrowsFormatException()
    {
        var parser = new ExpressionParser("3 + + 4");

        Assert.Throws<FormatException>(() => parser.Parse());
    }
}
```

这组测试覆盖了三层：叶子节点、组合运算、parser 集成。原文还特别强调了两个错误路径：未定义变量应该抛异常，非法输入也应该抛异常。解释器越靠近用户输入，错误信息越要清楚。

## 扩展边界

增加新操作时，做两件事：

1. 新建一个实现 `IExpression` 的类，比如 `DivideExpression`。
2. 更新 parser，让它识别 `/` 并创建对应节点。

如果你需要对同一棵树做很多操作，比如求值、格式化、优化、生成 SQL，Visitor Pattern 会更合适。Interpreter Pattern 把求值逻辑放在节点类里，结构直接，适合操作数量少的场景。

性能方面，小到中等深度的树通常没问题。很深的树会带来递归调用开销。如果表达式执行非常频繁，可以考虑缓存子表达式结果，或者把表达式树编译成 delegate。

## 实践建议

这个例子的关键不在算术本身，而在拆分方式：

- 语法节点用接口统一。
- 叶子节点直接给值。
- 组合节点递归调用子节点。
- 上下文承载运行时变量。
- parser 负责把字符串变成树。
- 测试同时覆盖节点、优先级和错误输入。

当你需要实现一套小型规则语言时，可以先按这个形状搭起来。等语法变复杂，再考虑把 parser 替换成更专业的工具。

这篇内容适合收藏，因为它是一条能照着写的实现路径。它也能帮你判断：当需求只是简单规则或表达式求值时，Interpreter Pattern 足够清楚；当语法开始膨胀时，就该及时换工具。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能直接用于项目的工具教程、技术观察和项目经验。

## 参考

- [How to Implement Interpreter Pattern in C#: Step-by-Step Guide](https://www.devleader.ca/2026/06/20/how-to-implement-interpreter-pattern-in-c-stepbystep-guide)
- [ANTLR](https://www.antlr.org/)
