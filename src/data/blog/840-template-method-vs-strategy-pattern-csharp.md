---
pubDatetime: 2026-05-29T08:00:05+08:00
title: "Template Method vs Strategy：C# 里两种“变中有不变”的算法骨架取舍"
description: "模板方法用继承锁住算法结构，策略模式用组合换实现，两者都能做到“主流程不变、个别步骤可换”。文章用同一个数据处理管道把两种写法拆开比一遍，并给出选型清单和组合使用的示例。"
tags: ["C#", ".NET", "设计模式", "Template Method", "Strategy"]
slug: "template-method-vs-strategy-pattern-csharp"
ogImage: "../../assets/840/01-cover.png"
source: "https://www.devleader.ca/2026/05/28/template-method-vs-strategy-pattern-in-c-key-differences-explained"
---

![模板方法的固定楼梯与策略模式的可拔插传送带对照](../../assets/840/01-cover.png)

写 C# 的人迟早会撞上同一道选择题：算法的主流程不想动，但里面某一步必须能换。Dev Leader 这篇 Template Method vs Strategy 的对比把两条路并排放在一起讲——一边靠继承锁住步骤顺序，一边靠组合让步骤可拔插。本文按原文的展开顺序梳理一遍，并把示例代码完整保留，方便直接对照自己手里的代码做判断。

## 两个模式解决的是同一类问题

定一段固定流程，但允许其中几步换不同实现。GoF 给出两种答案：

- **模板方法（Template Method）**：父类写好算法骨架，子类只重写允许变化的那几步
- **策略模式（Strategy）**：用接口约定每一步的行为，调用方在运行时注入不同实现

差别看似细微，影响范围却包括灵活度、约束力、可测试性和代码组织方式。下面用同一个“读 → 转换 → 写 → 记录完成”的数据处理管道，把两种写法分别走一遍。

## 模板方法：用继承锁住算法骨架

模板方法的核心是**父类拥有工作流**。它定义算法步骤的顺序，并在 `ProcessData` 里依次调用每一步；子类只能实现被声明为 `abstract` 的步骤，没法改变顺序、跳过步骤或塞进新步骤。

三个特点让它和其他行为型模式区分开：

- 父类定义算法的步骤顺序，并按顺序调用每一步
- 子类只重写自己需要定制的那几步
- 算法结构被锁在父类——子类无法重排、跳过或增加步骤

### C# 代码：用模板方法做数据处理

```csharp
public abstract class DataProcessor
{
    public void ProcessData()
    {
        string rawData = ReadData();
        string transformed = TransformData(rawData);
        WriteData(transformed);
        LogCompletion();
    }

    protected abstract string ReadData();

    protected abstract string TransformData(string data);

    protected abstract void WriteData(string data);

    private void LogCompletion()
    {
        Console.WriteLine("Data processing completed.");
    }
}
```

`ProcessData` 就是模板方法本身。它锁定了“读、转换、写、记录”这四步的顺序。子类只填空：

```csharp
public sealed class CsvDataProcessor : DataProcessor
{
    protected override string ReadData()
    {
        Console.WriteLine("Reading data from CSV file...");
        return "csv,raw,data";
    }

    protected override string TransformData(string data)
    {
        Console.WriteLine("Transforming CSV data...");
        return data.ToUpperInvariant();
    }

    protected override void WriteData(string data)
    {
        Console.WriteLine($"Writing to CSV output: {data}");
    }
}

public sealed class JsonDataProcessor : DataProcessor
{
    protected override string ReadData()
    {
        Console.WriteLine("Reading data from JSON source...");
        return "{\"value\": \"json_data\"}";
    }

    protected override string TransformData(string data)
    {
        Console.WriteLine("Transforming JSON data...");
        return data.Replace("json_data", "PROCESSED");
    }

    protected override void WriteData(string data)
    {
        Console.WriteLine($"Writing to JSON output: {data}");
    }
}
```

调用方什么都不需要知道：

```csharp
DataProcessor processor = new CsvDataProcessor();
processor.ProcessData();
// Reading data from CSV file...
// Transforming CSV data...
// Writing to CSV output: CSV,RAW,DATA
// Data processing completed.
```

注意 `LogCompletion` 是父类里的 `private` 方法——子类既不能重写也不能跳过。这种**结构层面的约束**正是模板方法的核心价值：每个 processor 都必然按 read → transform → write → log 的顺序走。

## 策略模式：用组合替换算法骨架的某几步

策略模式走的是相反的路：不靠继承变化行为，而是给每一步定义一个接口，把不同实现作为对象注入到上下文里。

三个特点：

- 接口约定每一步的行为契约
- 多个实现各自提供不同算法
- 客户端选择或注入策略，必要时还能运行时换掉

### C# 代码：用策略模式做同一个数据处理

先把三个步骤拆成接口：

```csharp
public interface IDataReader
{
    string ReadData();
}

public interface IDataTransformer
{
    string TransformData(string data);
}

public interface IDataWriter
{
    void WriteData(string data);
}
```

每个接口都可以有多个实现：

```csharp
public sealed class CsvReader : IDataReader
{
    public string ReadData()
    {
        Console.WriteLine("Reading data from CSV file...");
        return "csv,raw,data";
    }
}

public sealed class JsonReader : IDataReader
{
    public string ReadData()
    {
        Console.WriteLine("Reading data from JSON source...");
        return "{\"value\": \"json_data\"}";
    }
}

public sealed class UpperCaseTransformer : IDataTransformer
{
    public string TransformData(string data)
    {
        Console.WriteLine("Transforming to upper...");
        return data.ToUpperInvariant();
    }
}

public sealed class JsonFieldTransformer : IDataTransformer
{
    public string TransformData(string data)
    {
        Console.WriteLine("Transforming JSON fields...");
        return data.Replace("json_data", "PROCESSED");
    }
}

public sealed class ConsoleWriter : IDataWriter
{
    public void WriteData(string data)
    {
        Console.WriteLine($"Writing to console: {data}");
    }
}

public sealed class FileWriter : IDataWriter
{
    public void WriteData(string data)
    {
        Console.WriteLine($"Writing to file: {data}");
    }
}
```

上下文类负责把这些策略组合起来：

```csharp
public sealed class DataPipeline
{
    private readonly IDataReader _reader;
    private readonly IDataTransformer _transformer;
    private readonly IDataWriter _writer;

    public DataPipeline(
        IDataReader reader,
        IDataTransformer transformer,
        IDataWriter writer)
    {
        _reader = reader;
        _transformer = transformer;
        _writer = writer;
    }

    public void ProcessData()
    {
        string rawData = _reader.ReadData();
        string transformed = _transformer.TransformData(rawData);
        _writer.WriteData(transformed);
        Console.WriteLine("Data processing completed.");
    }
}
```

调用时可以任意搭配：

```csharp
var pipeline = new DataPipeline(
    new CsvReader(),
    new UpperCaseTransformer(),
    new FileWriter());

pipeline.ProcessData();
// Reading data from CSV file...
// Transforming to upper...
// Writing to file: CSV,RAW,DATA
// Data processing completed.
```

和模板方法的关键差别：在模板方法里，`CsvDataProcessor` 把读、转换、写三件事绑成了一个类；策略模式里，CSV 读取可以和任意 transformer、任意 writer 自由组合，换某一步不会牵动另外两步。

## 同一个问题，几个维度上的取舍

把两个版本并排比较，差距会落在几个具体维度上。

### 灵活度：策略胜

策略模式允许在运行时换掉单一步骤。你可以只换 reader、只换 transformer，或只换 writer，不影响其他两块。模板方法想换一种组合，就得新写一个子类。

当系统里已经有 DI 容器时，差距进一步放大——策略可以按配置、用户偏好或运行时条件解析出不同实现，模板方法很难走这条路。

### 约束力：模板方法胜

模板方法保证步骤顺序。父类按固定顺序调用 `ReadData`、`TransformData`、`WriteData`、`LogCompletion`，子类既不能跳过，也不能重排，更不能在中间插入新步骤。如果你的算法有“写完之后必须记录”“处理前必须校验”这类必须成立的不变式，模板方法是从结构上把违反这条规则的可能性堵死。

策略模式自己不保证顺序。`DataPipeline` 恰好按正确顺序调用三个策略，但完全可以再写一个上下文，把顺序换一种。**顺序的责任在上下文类，而不是在模式本身。**

### 可测试性：策略明显占优

策略模式里每个实现都是独立类，没有继承链。测 `UpperCaseTransformer` 只要传入字符串、断言输出即可。

模板方法的测试要走子类，但你要验证的行为是父类和子类共同决定的。父类的 `LogCompletion` 每次测试都会跑；想单独测某一步，常常要写测试专用子类，或把 `protected virtual` 暴露出来——摩擦更多。

### 代码重复：模板方法天然集中

模板方法适合放共享逻辑。`LogCompletion` 只写一次，所有子类都自动具备；以后想加一个统一的错误处理步骤，加在父类里所有子类都跟着升级。

策略模式如果多种组合都需要相同的横切逻辑，就有重复的风险——要么每个上下文类都写一次，要么用装饰器模式把策略包一层来注入日志、校验等横切能力。

## 什么时候用模板方法

- **算法结构已经稳定**。流程已经跑了几个月没改过步骤顺序，模板方法就是在把这种稳定写进类型系统。
- **必须强制步骤顺序**。系统正确性依赖于“先初始化连接再查询”“先校验再处理”这种顺序时，模板方法让违反顺序变得不可能。
- **前置或后置逻辑要集中放置**。所有变体都需要相同的 setup / teardown / 日志时，模板方法一次写完。
- **变体数量有限且稳定**。三四种已知变体、可预见的未来里不会爆炸，继承的开销可以接受。
- **真的是 is-a 关系**。`CsvDataProcessor` 确实就是一种 `DataProcessor`，继承能直接表达这层语义。

## 什么时候用策略

- **算法需要在运行时换**。用户可切换处理模式、按配置走不同算法、同一上下文在不同时间段要不同行为——策略可以直接换对象。
- **倾向于组合而非继承**。C# 只支持单继承，被模板方法基类用掉就没了，策略模式不占用这个名额。
- **变体之间没有可共享的公共逻辑**。十几个互不相干的 transformer，写十几个子类只会拉出一条又深又乱的继承链；策略让每个变体保持独立。
- **想通过 DI 注入算法**。策略模式本身就长成接口依赖的样子，DI 容器接得很顺；模板方法因为行为在继承链里，通过 DI 接入要绕路。

## 把两者组合：用模板方法定骨架，用策略换某步

这道选择题不必非黑即白。原文给出的常见做法是：父类用模板方法保证算法整体结构，单独某一步用策略接入。

定义一个变换步骤的策略接口和两个实现：

```csharp
public interface ITransformStrategy
{
    string Transform(string data);
}

public sealed class ToUpperStrategy : ITransformStrategy
{
    public string Transform(string data)
    {
        return data.ToUpperInvariant();
    }
}

public sealed class ReplaceTokenStrategy : ITransformStrategy
{
    private readonly string _oldToken;
    private readonly string _newToken;

    public ReplaceTokenStrategy(string oldToken, string newToken)
    {
        _oldToken = oldToken;
        _newToken = newToken;
    }

    public string Transform(string data)
    {
        return data.Replace(_oldToken, _newToken);
    }
}
```

父类还是模板方法：固定 `ProcessData` 的顺序，把 transform 步骤的实现委托给注入进来的策略：

```csharp
public abstract class HybridDataProcessor
{
    private readonly ITransformStrategy _strategy;

    protected HybridDataProcessor(ITransformStrategy strategy)
    {
        _strategy = strategy;
    }

    public void ProcessData()
    {
        string rawData = ReadData();
        string transformed = _strategy.Transform(rawData);
        WriteData(transformed);
        LogCompletion();
    }

    protected abstract string ReadData();

    protected abstract void WriteData(string data);

    private void LogCompletion()
    {
        Console.WriteLine("Hybrid processing completed.");
    }
}
```

子类负责读和写两步，变换步骤完全由策略决定：

```csharp
public sealed class CsvHybridProcessor : HybridDataProcessor
{
    public CsvHybridProcessor(ITransformStrategy strategy)
        : base(strategy)
    {
    }

    protected override string ReadData()
    {
        Console.WriteLine("Reading CSV...");
        return "csv,raw,data";
    }

    protected override void WriteData(string data)
    {
        Console.WriteLine($"Writing CSV output: {data}");
    }
}
```

调用时把策略当成可换的零件传进来：

```csharp
var processor = new CsvHybridProcessor(new ToUpperStrategy());
processor.ProcessData();
// Reading CSV...
// Writing CSV output: CSV,RAW,DATA
// Hybrid processing completed.

var anotherProcessor = new CsvHybridProcessor(
    new ReplaceTokenStrategy("raw", "CLEAN"));
anotherProcessor.ProcessData();
// Reading CSV...
// Writing CSV output: csv,CLEAN,data
// Hybrid processing completed.
```

这样得到的是**模板方法的约束力 + 策略模式的灵活性**：每个 processor 都还是按 read → transform → write → log 的顺序走；同时不需要为每一种 transform 变体再创建一个子类。

## 一个简化的选型清单

读完原文，可以记住几句话：

- 算法结构是否稳定，要不要在结构上强制顺序——选模板方法
- 算法的某些步骤需要运行时换，并希望通过 DI 注入——选策略
- 既要算法骨架不动，又要某一步可拔插——把两者合起来，模板方法守工作流，策略管那一步

写代码时不必为了用某个模式而用，看你的代码现在最痛的是什么：是“总有人把步骤顺序搞错”，还是“每加一种组合就多一个类”。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享能落地的工具教程、技术观察和项目经验。

## 参考

- 原文：[Template Method vs Strategy Pattern in C#: Key Differences Explained](https://www.devleader.ca/2026/05/28/template-method-vs-strategy-pattern-in-c-key-differences-explained)
- [Strategy Design Pattern in C#: Complete Guide With Examples](https://www.devleader.ca/2026/03/02/strategy-design-pattern-in-c-complete-guide-with-examples)
- [Decorator Design Pattern in C#: Complete Guide With Examples](https://www.devleader.ca/2026/03/14/decorator-design-pattern-in-c-complete-guide-with-examples)
