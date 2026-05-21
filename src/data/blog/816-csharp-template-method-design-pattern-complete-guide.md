---
pubDatetime: 2026-05-21T10:00:00+08:00
title: "C# 模板方法设计模式：完整指南与代码示例"
description: "深入讲解 C# 中的模板方法设计模式：抽象基类锁定算法骨架，子类填充可变步骤，钩子方法提供可选扩展点。包含数据处理管道完整实现、与策略模式的对比，以及依赖注入集成方式。"
tags: ["C#", ".NET", "设计模式", "模板方法", "行为模式"]
slug: "csharp-template-method-design-pattern-complete-guide"
ogImage: "../../assets/816/01-cover.png"
source: "https://www.devleader.ca/2026/05/20/template-method-design-pattern-in-c-complete-guide-with-examples"
---

当你需要一套固定的算法流程，但每个步骤的具体实现因情况而异，**模板方法设计模式**（Template Method Pattern）就是为这个场景而生的行为型模式。基类定义算法骨架——固定的执行顺序——把每个步骤的具体实现留给子类来填充。子类只负责细节，不改变整体流程。

这是 GoF（Gang of Four）经典目录里的行为型模式，对应的原则是好莱坞原则（Hollywood Principle）："不要来找我们，我们会去找你"——基类控制流程，子类提供实现。

## 模式结构

模板方法模式包含两个参与者：

**抽象类（Abstract Class）**：声明模板方法本身，以及它所调用的各个步骤。模板方法通常是非虚拟的（C# 里不加 `virtual`），或者显式标记为 `sealed`，防止子类改变步骤顺序。步骤分两种：
- `abstract` 方法：必须覆写，代表每个实现都不同的核心步骤
- `virtual` 方法（钩子）：有默认实现（通常为空），子类按需覆写

**具体类（Concrete Classes）**：继承抽象类，覆写 `abstract` 方法，按需覆写钩子。**绝不**覆写模板方法本身——子类只填步骤，不改顺序。

把它理解成菜谱框架：模板方法规定了"预热→备料→烹饪→摆盘→上菜"的顺序，每道菜都遵循这个顺序，但"备料"和"烹饪"的具体做法因菜品而异。框架是固定的，细节是可换的。

## C# 基础实现

以数据处理管道为例：不同数据源需要不同的解析和验证逻辑，但整体工作流——加载、验证、转换、导出——始终一致。

### 定义抽象基类

```csharp
using System;
using System.Collections.Generic;

public abstract class DataProcessor
{
    // 模板方法：定义固定顺序，子类不能覆写
    public void ProcessData()
    {
        IReadOnlyList<string> rawData = LoadData();
        IReadOnlyList<string> validData = ValidateData(rawData);
        IReadOnlyList<string> transformed = TransformData(validData);

        BeforeExport(transformed); // 钩子

        ExportData(transformed);

        Console.WriteLine("Processing complete.");
    }

    // 必须覆写的抽象步骤
    protected abstract IReadOnlyList<string> LoadData();
    protected abstract IReadOnlyList<string> ValidateData(IReadOnlyList<string> data);
    protected abstract IReadOnlyList<string> TransformData(IReadOnlyList<string> data);
    protected abstract void ExportData(IReadOnlyList<string> data);

    // 可选钩子：默认什么都不做
    protected virtual void BeforeExport(IReadOnlyList<string> data)
    {
        // 子类可以在导出前注入行为，默认为空
    }
}
```

`ProcessData` 就是模板方法，它定义了精确的执行顺序：加载→验证→转换→（可选钩子）→导出。子类无法改变这个顺序，只能实现各个步骤。`BeforeExport` 是钩子，默认为空实现，给子类一个可选的注入点。

### 创建具体子类

处理 CSV 数据的子类：

```csharp
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

public sealed class CsvDataProcessor : DataProcessor
{
    private readonly string _filePath;

    public CsvDataProcessor(string filePath)
    {
        _filePath = filePath;
    }

    protected override IReadOnlyList<string> LoadData()
    {
        Console.WriteLine($"Loading CSV from {_filePath}");
        return File.ReadAllLines(_filePath).ToList();
    }

    protected override IReadOnlyList<string> ValidateData(IReadOnlyList<string> data)
    {
        Console.WriteLine("Validating CSV rows...");
        return data
            .Where(line => !string.IsNullOrWhiteSpace(line))
            .ToList();
    }

    protected override IReadOnlyList<string> TransformData(IReadOnlyList<string> data)
    {
        Console.WriteLine("Trimming whitespace from CSV fields...");
        return data
            .Select(line => string.Join(",",
                line.Split(',').Select(f => f.Trim())))
            .ToList();
    }

    protected override void ExportData(IReadOnlyList<string> data)
    {
        Console.WriteLine($"Exporting {data.Count} cleaned CSV rows.");
    }
    // 没有覆写 BeforeExport：使用基类的空实现
}
```

处理 JSON 数据的子类，额外使用了 `BeforeExport` 钩子：

```csharp
public sealed class JsonDataProcessor : DataProcessor
{
    private readonly string _filePath;

    public JsonDataProcessor(string filePath)
    {
        _filePath = filePath;
    }

    protected override IReadOnlyList<string> LoadData()
    {
        Console.WriteLine($"Loading JSON from {_filePath}");
        string content = File.ReadAllText(_filePath);
        return new List<string> { content };
    }

    protected override IReadOnlyList<string> ValidateData(IReadOnlyList<string> data)
    {
        Console.WriteLine("Validating JSON structure...");
        return data
            .Where(json => json.TrimStart().StartsWith("{")
                || json.TrimStart().StartsWith("["))
            .ToList();
    }

    protected override IReadOnlyList<string> TransformData(IReadOnlyList<string> data)
    {
        Console.WriteLine("Normalizing JSON whitespace...");
        return data
            .Select(json => json.Replace("\r\n", "\n"))
            .ToList();
    }

    protected override void ExportData(IReadOnlyList<string> data)
    {
        Console.WriteLine($"Exporting {data.Count} JSON document(s).");
    }

    // 覆写钩子：在导出前备份
    protected override void BeforeExport(IReadOnlyList<string> data)
    {
        Console.WriteLine("Backing up original JSON before export...");
    }
}
```

`JsonDataProcessor` 覆写了 `BeforeExport` 钩子来添加备份行为，`CsvDataProcessor` 完全不覆写它——依赖默认的空实现。两个类都遵循 `ProcessData` 定义的算法结构，但各步骤的实现完全不同。

客户端代码：

```csharp
DataProcessor csvProcessor = new CsvDataProcessor("data/input.csv");
csvProcessor.ProcessData();
// Loading CSV from data/input.csv
// Validating CSV rows...
// Trimming whitespace from CSV fields...
// Exporting 42 cleaned CSV rows.
// Processing complete.

DataProcessor jsonProcessor = new JsonDataProcessor("data/input.json");
jsonProcessor.ProcessData();
// Loading JSON from data/input.json
// Validating JSON structure...
// Normalizing JSON whitespace...
// Backing up original JSON before export...
// Exporting 1 JSON document(s).
// Processing complete.
```

客户端通过 `DataProcessor` 抽象类工作，调用 `ProcessData`，模板方法负责编排。客户端不知道也不关心运行的是哪个具体子类——只知道算法会按正确顺序执行。

## 钩子和可选步骤

钩子（Hook）是模板方法模式的核心特性。钩子是抽象基类里带有默认实现（通常为空）的虚拟方法，子类可以选择性覆写。

`abstract` 方法与钩子的区别：
- **`abstract` 方法**：必须覆写，代表算法中真正不可缺少且各实现不同的步骤
- **钩子（`virtual` 方法）**：可选，有默认行为，子类只在需要注入额外逻辑时才覆写

钩子还可以控制流程——常见模式是布尔型钩子，模板方法根据它决定是否执行可选步骤：

```csharp
public abstract class ReportGenerator
{
    public void GenerateReport()
    {
        GatherData();
        FormatReport();

        if (ShouldIncludeCharts())
        {
            AddCharts();
        }

        PublishReport();
    }

    protected abstract void GatherData();
    protected abstract void FormatReport();
    protected abstract void PublishReport();

    // 布尔钩子：默认不包含图表
    protected virtual bool ShouldIncludeCharts() => false;

    // 行为钩子：默认不添加图表
    protected virtual void AddCharts()
    {
        // Default: no charts added
    }
}
```

需要图表的子类同时覆写 `ShouldIncludeCharts`（返回 `true`）和 `AddCharts`（提供图表逻辑）；不需要图表的子类完全忽略这两个钩子。模板方法仍然是算法流程的唯一权威来源。

## 与依赖注入集成

在真实的 .NET 应用里，你会想把模板方法类注册到 DI 容器里。模板方法模式与 `IServiceCollection` 配合得很自然——注册具体子类，按抽象基类或共享接口解析：

```csharp
using Microsoft.Extensions.DependencyInjection;

var services = new ServiceCollection();

services.AddTransient<DataProcessor, CsvDataProcessor>(
    sp => new CsvDataProcessor("data/input.csv"));

var provider = services.BuildServiceProvider();

var processor = provider.GetRequiredService<DataProcessor>();
processor.ProcessData();
```

如果需要解析同一基类的多个实现，可以注册 `IEnumerable<DataProcessor>`：

```csharp
var services = new ServiceCollection();

services.AddTransient<DataProcessor>(
    sp => new CsvDataProcessor("data/input.csv"));
services.AddTransient<DataProcessor>(
    sp => new JsonDataProcessor("data/input.json"));

var provider = services.BuildServiceProvider();

IEnumerable<DataProcessor> processors = provider.GetServices<DataProcessor>();

foreach (DataProcessor processor in processors)
{
    processor.ProcessData();
}
```

这种方式可以按序处理所有注册的数据源，调用代码不需要知道有哪些具体处理器。新增数据源只需注册一个新子类——编排代码不变。

## 适合使用的场景

模板方法模式在以下场景里是很好的选择：

- **数据处理管道**：多个数据源需要同样的工作流（加载→验证→转换→导出），但各自的解析和验证逻辑不同
- **文件解析**：需要处理不同格式（CSV、XML、JSON、Parquet），但整体解析生命周期一致——打开→读取标头→解析行→关闭
- **报告生成**：不同报告类型遵循同样的生成流程（采集数据→格式化→可选图表→发布），但采集和格式化方式各异
- **游戏 AI 回合逻辑**：角色遵循同样的回合结构（评估→选择行动→执行→结束回合），但每类角色的评估和行动逻辑不同
- **测试 Fixture**：测试的 Setup 和 Teardown 有固定结构，但具体步骤因测试类别而异

## 不适合使用的场景

如果算法结构本身在各实现之间发生变化——不只是步骤的实现不同，而是步骤的顺序和组合都不同——模板方法就变成了限制而不是帮助。这种情况下，**策略模式**通常更合适，因为它通过组合替换整个算法，而不是通过继承锁定固定序列。

当继承层次变得很深时也要小心。如果你发现自己在构建多层抽象基类链，每层都添加自己的模板方法钩子，这时应该考虑组合方案是否更好。

## 模板方法 vs 策略模式

两者都处理"变化的行为"，常被混淆，但解决的是不同的问题：

| 维度 | 模板方法 | 策略模式 |
|---|---|---|
| 机制 | 继承 | 组合 |
| 算法结构 | 编译时由基类固定 | 运行时可整体替换 |
| 自定义方式 | 创建新子类覆写步骤 | 注入不同策略对象 |
| 控制粒度 | 高，基类控制整个序列 | 低，上下文完全委托给策略 |

实用判断：
- 算法有**固定结构**，只有少数步骤有变化 → 模板方法
- 算法本身**需要整体替换**，或需要运行时通过依赖注入切换 → 策略模式
- 两者可以结合：用模板方法固定整体工作流，在需要运行时灵活性的个别步骤里注入策略对象

装饰器模式（Decorator）也值得一提：当你想在不修改类的情况下给对象添加行为时，装饰器更合适——它包装现有对象，而不是定义固定的算法骨架。

## 常见问题

**怎么防止子类覆写模板方法？**  
在 C# 里，非虚拟方法默认就不能被覆写。如果需要更明确，可以把模板方法标记为 `sealed`（当它在父类里是 `virtual` 或 `override` 时）。目标是确保子类只能自定义各个步骤，不能改变整体算法流程。

**钩子是什么？**  
钩子是抽象基类里带有默认实现（通常为空）的虚拟方法，子类可以选择性覆写。常见用途包括前置处理、后置处理、日志记录，或控制可选步骤是否执行的布尔判断。

**能用接口代替抽象类吗？**  
技术上可以——C# 8 起接口支持默认方法实现，因此可以在接口里定义模板方法。但抽象类是约定俗成的选择，因为它更清晰地表达了基于继承的设计意图，并为共享状态和辅助方法提供了自然的容身之所。

**模板方法违反"组合优于继承"原则吗？**  
模板方法确实使用继承，但用法是受控的——基类定义固定结构，子类只自定义特定扩展点。只要继承层次保持浅层（抽象基类下只有一层具体子类），模式就工作良好。如果你发现自己在构建深层继承链，或者需要运行时灵活性，再考虑重构到策略模式等组合方案。

**怎么支持开闭原则？**  
模板方法让你通过创建新子类来扩展行为，而不需要修改基类或已有子类。基类里的模板方法对修改是关闭的——顺序不变。新行为通过新的具体类来添加，不触碰已有的经过测试的代码。

## 小结

C# 的模板方法设计模式是一个务实的行为型模式：锁定算法结构，让各步骤的实现保持灵活。基类持有顺序，子类填入细节，钩子提供可选扩展点——调用代码不需要知道运行的是哪个具体实现。

识别场景的方法很简单：找代码库里多个类遵循同样工作流但步骤实现不同的地方，找那些在类之间重复出现的方法调用序列——那就是等待被提取到模板方法里的算法骨架。用依赖注入管理具体子类，在需要广播通知的场景里搭配观察者模式（Observer Pattern）。

## 参考

- [Template Method Design Pattern in C#: Complete Guide with Examples](https://www.devleader.ca/2026/05/20/template-method-design-pattern-in-c-complete-guide-with-examples)
- [Strategy Design Pattern in C#: Complete Guide with Examples](https://www.devleader.ca/2026/03/02/strategy-design-pattern-in-c-complete-guide-with-examples)
- [Decorator Design Pattern in C#: Complete Guide](https://www.devleader.ca/2026/03/14/decorator-design-pattern-in-c-complete-guide-with-examples)
- [The Big List of Design Patterns](https://www.devleader.ca/2023/12/31/the-big-list-of-design-patterns-everything-you-need-to-know)
