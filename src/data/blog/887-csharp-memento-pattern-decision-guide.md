---
pubDatetime: 2026-06-18T08:05:00+08:00
title: "C# Memento 模式：什么时候该用、什么时候不该用"
description: "一份结构化的决策指南：识别代码里需要 Memento 模式的信号（撤销/回滚、多字段状态、事务安全），对比 Command/序列化/Event Sourcing 的取舍，附带从前到后的完整重构实例和常见误用清单。"
tags: ["C#", "设计模式", "Memento", "行为型模式", "重构"]
slug: "csharp-memento-pattern-decision-guide"
source: "https://www.devleader.ca/2026/06/17/when-to-use-memento-pattern-in-c-decision-guide-with-examples"
ogImage: "../../assets/887/01-cover.png"
---

## 什么时候 Memento 是对的答案

任何允许用户修改状态的应用迟早会面对同一个问题：怎么让他们往回退一步。可能是撤销按钮，可能是表单向导里的"上一步"，也可能是一个多步操作验证失败后需要整体回滚的事务。答案往往涉及状态快照 — 这正是 Memento 模式做的事。

但 Memento 模式不是银弹。这篇文章提供一套结构化决策框架，帮你判断什么场景下它是最合适的工具，什么场景下选了它只是徒增复杂度。你会看到代码需要它的信号、具体适用场景、过犹不及的情况、决策检查清单，以及从烂代码到干净重构的完整示例。

![Memento 模式标题图](../../assets/887/02-memento-header.png)

## 代码在向你发信号

不是每个有状态的对象都需要 Memento 模式。但以下症状是强烈的提示：用状态快照来简化你的设计。

### 你需要撤销或回滚

如果你的应用需要把对象恢复到之前的状态 — 无论是显式的撤销按钮、"还原修改"操作、还是失败的事务恢复 — Memento 模式天然适用。它提供了一种正式的机制来捕获完整状态快照并回放。没有它，你只能在每个可能需要回滚的方法里散落状态恢复逻辑，或者重复写一堆字段赋值。

这和给单个属性重新赋值不一样。如果回滚意味着恢复一组协调的字段 — 内容加光标位置、余额加交易日志加状态标记 — 快照能保证这些字段之间的一致性。漏掉一个字段的部分回滚是状态损坏的温床。

### 状态复杂，逐操作逆向困难

有些操作很容易逆向。计数器递增？递减回去。列表追加？删掉最后一项。但很多真实场景的变更没这么干净。如果你的对象会计算派生值、在属性 setter 里触发副作用、或者在状态变化时重组内部数据结构，逐操作逆向会变得脆弱且容易出错。

Memento 模式直接绕开了这个问题。不用想怎么撤销每个单独操作，操作前把整个状态拍下来，失败后整体恢复回去。当状态转换涉及多个必须保持一致的互依字段时，这种方式尤其有价值。

### 你需要事务级别的安全保障

当一个多步骤操作必须完全成功或彻底回滚时，Memento 模式提供了一个干净的检查点机制。操作前存状态，尝试执行，失败时恢复。这和数据库事务的思路一脉相承，但是作用在对象层面。你不需要一个完整的事务框架 — 一个快照加一个条件恢复就够了。

这体现在批量配置更新、多字段表单提交、工作流步骤处理等场景里。任何一步失败，恢复检查点比试着手动逆向每个已完成步骤可靠得多。

### 外部代码不该知道对象的内部结构

封装是核心关注点。如果你发现自己为了给一个"历史管理器"克隆状态而暴露私有字段或写了一堆 public getter，这就是设计异味。Memento 模式让你在不破坏封装的前提下把状态外置 — 发起者（originator）创建一个不透明快照，只有它自己能读取；保管者（caretaker）负责存储和管理快照，但看不到内容。

## 适合 Memento 的具体场景

### 文本编辑器和文档编辑

任何支持撤销/重做的编辑器都是教科书级别的候选。编辑器在每次修改之前拍快照 — 键入、删除、格式化 — 推入历史栈。撤销弹出最近的快照并恢复。快照的内部结构对历史管理器完全不可见，它只需要存储和检索不透明的 memento 对象。

### 表单向导和多步工作流

用户需要前后导航的多步表单很适合 Memento。每次用户进入下一步时，拍下当前表单状态。如果他们返回上一步，恢复快照而不是试图从各种零散的来源重建字段值。这比跨步骤追踪单个字段变化更简单、更可靠。

### 游戏存档系统

游戏状态通常非常复杂 — 玩家位置、背包、血量、环境状态、任务进度。Memento 模式可以一次性把所有东西装进一个快照对象里，游戏引擎存到磁盘或保留在内存。快速存档和快速读档变得很简单：存档创建 memento，读档恢复 memento。

### 对象级别的事务回滚

当你需要尝试一个操作、失败时回滚 — 不涉及数据库事务 — Memento 提供了一个轻量级的检查点。存状态，尝试操作，异常时恢复。这在执行复杂计算或多字段原子更新的领域对象中很有用。

## 什么时候 Memento 是过度设计

### 对象已经是不可变的

如果你的对象是不可变的 — 比如用了 C# record 加 `with` 表达式 — 每次修改已经产生一个新实例。旧实例本身就是快照。你不需要单独的 memento 类、caretaker 或任何模式组件。保留旧对象的引用就行。

### 只需要重置一个值

如果回滚就是把一个属性设回原值，Memento 模式就是一个局部变量就能搞定的事却搞了一套基建。在计算前存一个 `previousBalance` 字段，比搭建整个 memento 基础设施更简单、更清晰、更快。模式是为了管理复杂度而存在的 — 不要为了用模式而制造复杂度。

### 每个操作都有干净的逆操作

当每个操作都有清晰、显而易见的逆操作 — 递增/递减、添加/删除、启用/禁用 — Command 模式可能是更好的选择。Command 存操作和它的逆向，比存完整状态快照更省内存。Memento 模式擅长的是当逐操作逆向不现实的场景，不是当它很简单的时候。

### 状态太大不适合内存快照

如果对象持有数 MB 的数据 — 大型集合、二进制 blob、深度嵌套对象图 — 完整状态快照会变成内存问题。每次快照都复制整份状态。对大型状态对象，考虑增量 diff 策略、压缩或基于磁盘的序列化，而不是内存 memento。

## 决策框架：你该用 Memento 吗

按顺序回答以下问题。大部分回答"是"，Memento 很可能就是正确答案。

- **需要恢复之前的状态吗？** Memento 的核心就是捕获和恢复状态。如果你的应用没有撤销、回滚、检查点或任何形式的状态恢复需求，不需要它。第一个过滤器 — 如果答案为否，停在这里。
- **状态是多字段或复杂的吗？** 如果恢复状态意味着重置多个协调字段，Memento 确保一致性。如果是单字段，局部变量更简单。
- **操作难以逐个逆向吗？** 如果你不能轻松为每个操作写"撤销" — 因为有派生计算、副作用或互依字段 — 完整状态快照比逐操作逆向更可靠。
- **封装重要吗？** 如果外部代码不该知道对象内部结构，Memento 保住了这道边界。caretaker 存储不透明快照，不访问私有状态。
- **状态够小能做快照吗？** 完整状态复制必须能舒舒服服地放在内存里。如果状态很大，评估部分快照、diff 或基于序列化的方案是否更合适。
- **会有多个快照吗？** 如果只需要一个检查点（操作前存，失败时恢复），完整的 memento 基建加 caretaker 和历史栈可能过重。简单的存/恢复不带 caretaker 也许就够了。

## 重构实例：从手动追踪到 Memento 模式

### 之前的代码：手动状态追踪的配置编辑器

这个配置编辑器试图通过手动追踪之前的值来支持撤销。它脆弱且不可扩展：

```csharp
public sealed class AppConfiguration
{
    public string Theme { get; set; } = "Light";
    public int FontSize { get; set; } = 14;
    public bool AutoSave { get; set; } = true;

    // 手动"撤销"字段 — 每个属性一个
    private string _previousTheme = "Light";
    private int _previousFontSize = 14;
    private bool _previousAutoSave = true;

    public void ApplyChanges(string theme, int fontSize, bool autoSave)
    {
        _previousTheme = Theme;
        _previousFontSize = FontSize;
        _previousAutoSave = AutoSave;

        Theme = theme;
        FontSize = fontSize;
        AutoSave = autoSave;
    }

    public void Undo()
    {
        Theme = _previousTheme;
        FontSize = _previousFontSize;
        AutoSave = _previousAutoSave;
    }
}
```

这里的问题很明显：只能撤销一层；加一个新属性要改三个地方 — 属性本身、备份字段、`ApplyChanges` 和 `Undo`；没有历史栈；类演化了就容易断。

### 之后的代码：完整撤销历史的 Memento 模式

```csharp
public interface IMemento
{
    string Description { get; }
}

public sealed class AppConfiguration
{
    public string Theme { get; private set; } = "Light";
    public int FontSize { get; private set; } = 14;
    public bool AutoSave { get; private set; } = true;

    public void ApplyChanges(string theme, int fontSize, bool autoSave)
    {
        Theme = theme;
        FontSize = fontSize;
        AutoSave = autoSave;
    }

    public IMemento Save()
    {
        return new ConfigMemento(Theme, FontSize, AutoSave);
    }

    public void Restore(IMemento memento)
    {
        if (memento is not ConfigMemento config)
            throw new ArgumentException("Invalid memento type.", nameof(memento));

        Theme = config.SavedTheme;
        FontSize = config.SavedFontSize;
        AutoSave = config.SavedAutoSave;
    }

    private sealed class ConfigMemento : IMemento
    {
        public string SavedTheme { get; }
        public int SavedFontSize { get; }
        public bool SavedAutoSave { get; }
        public string Description =>
            $"Theme={SavedTheme}, FontSize={SavedFontSize}, AutoSave={SavedAutoSave}";

        public ConfigMemento(string theme, int fontSize, bool autoSave)
        {
            SavedTheme = theme;
            SavedFontSize = fontSize;
            SavedAutoSave = autoSave;
        }
    }
}
```

再加上管理撤销栈的 caretaker：

```csharp
public sealed class ConfigurationManager
{
    private readonly AppConfiguration _config;
    private readonly Stack<IMemento> _undoStack = new();

    public ConfigurationManager(AppConfiguration config)
    {
        _config = config ?? throw new ArgumentNullException(nameof(config));
    }

    public void ApplyChanges(string theme, int fontSize, bool autoSave)
    {
        _undoStack.Push(_config.Save()); // 改之前先拍快照
        _config.ApplyChanges(theme, fontSize, autoSave);
    }

    public bool Undo()
    {
        if (_undoStack.Count == 0) return false;

        var snapshot = _undoStack.Pop();
        _config.Restore(snapshot);
        return true;
    }
}
```

使用方式：

```csharp
var config = new AppConfiguration();
var manager = new ConfigurationManager(config);

manager.ApplyChanges("Dark", 16, false);
manager.ApplyChanges("HighContrast", 18, true);

Console.WriteLine(config.Theme); // HighContrast

manager.Undo();
Console.WriteLine(config.Theme); // Dark

manager.Undo();
Console.WriteLine(config.Theme); // Light
```

重构后的版本支持无限层撤销，状态封装在私有嵌套类里，加一个新配置属性只需改动 originator 和它的 memento — 不用改每个碰状态的函数。caretaker 完全不关心快照里有什么。

## Memento 与其他方案的对比

| 维度     | Memento              | Command             | 序列化                     | Event Sourcing      |
| -------- | -------------------- | ------------------- | -------------------------- | ------------------- |
| 存储什么 | 完整状态快照         | 操作 + 逆操作       | 序列化状态（JSON/binary）  | 事件序列            |
| 撤销机制 | 恢复快照             | 执行逆命令          | 反序列化前一状态           | 重放到某一点        |
| 内存成本 | 每快照完整复制       | 每命令很小          | 每快照完整复制（在磁盘上） | 随事件数增长        |
| 封装性   | 强 — 私有嵌套类      | 中等 — 命令知道操作 | 弱 — 序列化器访问字段      | 中等 — 事件是公开的 |
| 复杂度   | 低到中               | 中等                | 低（依赖工具）             | 高                  |
| 最适合   | 复杂状态、多字段回滚 | 可逆的离散操作      | 持久化到磁盘               | 完整审计追踪、重放  |

Memento 捕获的是状态"曾是什么"。Command 捕获的是"发生了什么"。操作是离散且容易取逆的，Command 更省内存。状态复杂、操作难以逆向的，Memento 更简单可靠。

## 误用信号

即使 Memento 模式很强大，以下情况说明你可能用错了它：

- **你在给从不变化的状态拍快照。** 如果对象初始化之后实际上只读，捕获 memento 毫无意义。
- **你的 memento 复制了整个领域模型。** 如果 memento 类镜像了 originator 的每个字段，而且 originator 很大，每个快照把内存翻一倍。考虑是不是真的需要完整快照。
- **你给只需要一个检查点的对象建了完整历史栈。** 如果唯一场景是"在风险操作前存，失败时恢复"，简单的存/恢复就够了，不需要栈和 caretaker。
- **caretaker 在检查 memento 的内容。** 如果 caretaker 读快照里的状态来做决策，你已经打破了封装的契约。caretaker 应该把 memento 当作不透明令牌处理。
- **最常见错误：捕获引用而非值。** 如果 originator 持有可变集合或对象，memento 必须深拷贝它们。否则快照后的修改会悄悄破坏 memento 里的数据。

## 参考

- [When to Use Memento Pattern in C#: Decision Guide with Examples](https://www.devleader.ca/2026/06/17/when-to-use-memento-pattern-in-c-decision-guide-with-examples)
- [Command Design Pattern in C#](https://www.devleader.ca/2026/04/14/command-design-pattern-in-c-complete-guide-with-examples)
- [State Design Pattern in C#](https://www.devleader.ca/2026/04/19/state-design-pattern-in-c-complete-guide-with-examples)
- [Strategy Design Pattern in C#](https://www.devleader.ca/2026/03/02/strategy-design-pattern-in-c-complete-guide-with-examples)
