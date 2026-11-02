---
pubDatetime: 2026-11-02T10:40:00+08:00
title: "C# 运算符：一条表达式要回答的四个问题"
description: "7/2 赋给 double 为什么还是 3？乘号优先级更高，为什么方法调用仍按从左到右执行？从操作数类型、分组、求值顺序到相等契约，用四个问题拆开 C# 运算符，让日常表达式能被解释，不必靠猜。"
tags: ["C#", ".NET", "Language Features"]
slug: "csharp-operators-types-evaluation-expressions"
ogImage: "../../assets/1130/01-cover.png"
source: "https://www.devleader.ca/2026/11/01/c-operators-evaluation-types-and-everyday-expressions"
---

```csharp
int completed = 7;
int capacity = 2;
double ratio = completed / capacity;
```

`ratio` 打印出来是 `3`。这里没有浮点精度问题，`double` 也没接错：两个 `int` 的除法在赋值发生之前就做完了，`double` 只来得及接住一个已经丢掉小数的结果。

类似的误读不只出现在除法上。几个方法调用拼成的四则运算，乘号优先级更高，调用顺序仍然是从左到右；`false && Check()` 右边的 `Check()` 根本不会执行；两个内容相同的字符串分别装进 `object` 变量再比较，结果可能变成 `False`。这些现象指向同一套读法：一条 C# 表达式要回答四个彼此独立的问题——每个操作数的编译期类型是什么、表达式按什么结构分组、哪些操作数真的会被求值、最后选中了哪个运算符。四条答案凑齐，代码的含义才是确定的。

下面按这四个问题拆开日常表达式。例子取自 Nick Cosentino 在 Dev Leader 的文章，技术结论按 Microsoft 语言规范核对，示例在 .NET 10（SDK 10.0.402）上实际运行过。截至 2026 年 11 月，.NET 10 与 C# 14 仍是当前正式组合（.NET 11 处于 RC2），这一层的运算符语义在版本之间基本稳定。

## 先看类型：除法在赋值之前已经算完

```csharp
int completed = 7;
int capacity = 2;

double afterIntegerDivision = completed / capacity;
double fractionalDivision = (double)completed / capacity;
decimal decimalDivision = (decimal)completed / capacity;

Console.WriteLine(afterIntegerDivision); // 3
Console.WriteLine(fractionalDivision); // 3.5
Console.WriteLine(decimalDivision); // 3.5
```

三行代码的区别只在转换位置。第一行用两个 `int` 相除，商是整除结果，再隐式转成 `double`；第二行先把左操作数转成 `double`，除法按浮点规则算。第三行用 `decimal` 算，输出同样是 `3.5`，底层的十进制精度另算。

整数除法向零取整，`7 / 2` 得 `3`，`-7 / 2` 得 `-3`。小于 `int` 的整型参与二元运算前会先提升：`byte` 与 `byte` 相加得到的是 `int`，再赋回 `byte` 才需要显式转换。这些规则都作用在运算符本身，接收结果的变量不参与运算类型的选择。

判断一个运算符在算什么，看它两侧的静态类型，不看左边声明。把转换放在除号后面，`(double)(completed / capacity)` 得到的是 `3`：括号里的整数除法先执行完，转换只是把已经丢掉的小数补不回来。

## 优先级决定分组，不决定谁先被调用

```csharp
int result = Read("first", 2) + Read("second", 3) * Read("third", 4);
Console.WriteLine(result);

int Read(string label, int value)
{
    Console.WriteLine(label);
    return value;
}
```

控制台依次输出 `first`、`second`、`third`，`result` 是 `14`。乘法确实先结合，`3 * 4` 先算出 `12` 再和 `2` 相加；三个方法的执行顺序却完全按书写顺序，从左到右。

语言规范把操作数求值和优先级分开写。操作数总是从左到右求值，优先级与结合性只决定这些值如何组合成子表达式。乘法优先级高，说的是 `3 * 4` 这个子表达式先成形，不意味着它的操作数比加法的左操作数先被调用。

结合性同理。赋值 `=` 和空合并 `??` 是右结合，那只影响分组：`a = b = c` 解析成 `a = (b = c)`。有人把右结合理解成「从右往左执行」，写出依赖求值顺序的代码，结果与预期相反。

属性 getter 和索引器都算「求值一个操作数」，它们在求值过程中可能改状态、抛异常、访问数据库；自定义运算符方法则在运算符被选中后才执行。审查带副作用的表达式时，把每个操作数当成一次调用来看，才能看清这一行按什么顺序做了几件事。

## 短路让右边的操作数根本不执行

```csharp
string input = "42";
bool valid = int.TryParse(input, out int number) && number > 0;

bool expensiveCheck = false && CheckRemoteState();

bool CheckRemoteState()
{
    Console.WriteLine("Check performed");
    return true;
}
```

`int.TryParse` 失败时 `number` 是 `0`；先解析、再判断，第二个操作数只在解析成功时才有执行的意义。第二个表达式里 `CheckRemoteState()` 不会被调用，控制台也不会出现 `Check performed`。

`&` 和 `|` 对 `bool` 是另一种行为：求值到它们时，两侧都要求值，不短路。`true & CheckRemoteState()` 会真的执行方法，最终结果仍然是 `true`；如果方法抛异常或改了状态，替换 `&&` 就会改变程序行为。

`bool?` 需要单独处理。`&` 和 `|` 对 `bool?` 走三值逻辑表，例如 `false & null` 得 `false`，`true & null` 得 `null`；`&&` 和 `||` 不能直接用于 `bool?`。要组合可空布尔值，先把 `null` 归一，或者显式写出三种情况。

## 相等取决于编译器选了哪个 `==` 契约

```csharp
string first = "devleader";
string second = string.Concat("dev", "leader");

Console.WriteLine(first == second); // True

object boxedFirst = first;
object boxedSecond = second;

Console.WriteLine(boxedFirst == boxedSecond); // False
```

两个变量指向的字符串内容一样，第一次比较得到 `True`，因为编译器选中的是 `string` 的 `==`，按序数、区分大小写比较内容。第二次比较的静态类型是 `object`，选中的是引用相等，两个运行时拼接出的字符串实例地址不同，结果是 `False`。

变量的声明类型参与了运算符选择。底层对象一直是同一个 `string`，编译器不会在运行时根据实际类型重新挑一个更合适的 `==`。类型一变，可用的运算符集合就跟着变。

字符串比较策略是另一层问题。先用这四个问题确定「这里比较的是内容」，再决定用 `string.Equals(a, b, StringComparison.OrdinalIgnoreCase)` 还是 `string.Compare` 处理区域性、大小写。`==` 只给出序数、区分大小写的结果。

`record` 会生成值相等成员，两个 `Person("Ada")` 实例按类型和字段值比较。普通 `struct` 没有自动获得 `==`：定义了 `struct Point` 之后写 `p1 == p2` 编译不过，除非自己实现 `operator ==`；它继承来的 `Equals` 和运算符是否存在是两件事。

## 转换、位运算和 checked 各管一层

转换改变值的表示，运算符在转换后的类型上工作。两件事经常一起出现，却不能互相解释。`(double)completed / capacity` 先把 `int` 转成 `double` 再除；用户定义转换能让包装类型参与运算，但包装类型上的 `+` 是否与底层数值的 `+` 同义，取决于它自己有没有定义运算符。

位运算同理。`&` 和 `|` 用在 `int` 或 `[Flags]` 枚举上是位模式操作，用在 `bool` 上是不短路的布尔组合。权限掩码记录「哪些位被置上」，条件判断问「命题真假」；把掩码当条件用，需要显式比较，例如 `(permissions & Permissions.Write) != Permissions.None`。

`checked` 是文本作用域。写在 checked 块里的适用整数运算溢出时抛 `OverflowException`，unchecked 则保留截断后的位；这个上下文不会顺着方法调用传下去，被调用方法里的算术按它自己定义处的上下文和编译设置处理。`decimal` 溢出总是抛异常，浮点溢出得到无穷大，这两类运算不适用整数那套 checked 规则。

C# 11 起用户定义运算符可以写成 checked 版本，被选中时执行对应的实现，运算符体不会因为声明了 checked 就自动进入 checked 上下文，语言也不强制它抛异常。C# 14 又允许把复合赋值、`++` 和 `--` 声明成实例成员，变量目标上实例版本优先于静态版本，自定义类型因此可以实现就地更新，而不必走「先算再赋回」。

C# 14 的扩展成员还带来扩展运算符。查找顺序有明确规定：只有找不到可适用的预定义运算符或非扩展的用户定义运算符时，才会考虑扩展运算符；扩展运算符也不支持隐式和显式转换。读陌生类型上的表达式时，这条规则能解释「为什么这段代码没有用上那个看起来更合适的扩展重载」。

## 用四个问题拆一条日常表达式

四个问题可以做成一张检查表，按顺序过一遍：

| 问题             | 该查的地方                                                 |
| ---------------- | ---------------------------------------------------------- |
| 谁在参与运算     | 每个操作数的编译期类型，包括属性、索引器、方法返回值的类型 |
| 如何分组         | 优先级与结合性，括号也是分组                               |
| 哪些操作数会执行 | 从左到右的求值顺序，加上 `&&`、`\|\|`、`?:` 等条件结构     |
| 结果是什么类型   | 被选中的运算符、数值提升、赋值时的转换                     |

![C# 表达式的四个问题：类型、分组、求值与结果（概念示意）](../../assets/1130/02-illustration-four-questions.png)

拿到一条读不出结论的表达式，先找四个问题里哪一个没有答案。多数时候卡在第一个：接收变量写的是 `double`，操作数却是两个 `int`。

具体做法有两种。把表达式临时改写成几个中间变量，每个中间值带上类型，分组、求值顺序和选中的操作就都摊开了；或者用能区分不同解释的输入跑一次测试。`7 / 2` 能暴露整数除法，`6 / 2` 不能；两个内容相同但来源不同的字符串能暴露引用比较，同一个字面量赋值两次不能。

括号和中间变量都该出现在有解释价值的地方。`(double)completed / capacity` 里的括号说明了「先转成浮点再除」，机械地给每个子表达式加括号只会让代码更难读。动手改写之前，先确认这行代码难读的原因：分组不清楚，还是操作数类型没写明白。

这套读法覆盖日常表达式，边界也要说清。`?:` 和 `??` 同样有条件求值：`a ?? b` 在 `a` 不为 `null` 时不求值 `b`。可空值类型的三值逻辑、用户自定义的 `true`/`false` 运算符会再叠一层规则；读到这类表达式时，把对应运算符的文档翻出来，再走一遍四个问题。

## 参考

- [C# Operators: Evaluation, Types, and Everyday Expressions](https://www.devleader.ca/2026/11/01/c-operators-evaluation-types-and-everyday-expressions)
- [Expressions — C# language specification](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/language-specification/expressions)
- [Arithmetic operators](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/arithmetic-operators)
- [Boolean logical operators](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/boolean-logical-operators)
- [Equality operators](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/equality-operators)
- [checked and unchecked statements](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/statements/checked-and-unchecked)
- [What's new in C# 14](https://learn.microsoft.com/en-us/dotnet/csharp/whats-new/csharp-14)
- [Extension operators (C# 14 proposal)](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/proposals/csharp-14.0/extension-operators)
- [Operator overloading](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/operator-overloading)
