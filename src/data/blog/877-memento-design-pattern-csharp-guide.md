---
pubDatetime: 2026-06-15T07:59:46+08:00
title: "C# 备忘录模式完整指南：状态快照与回滚"
description: "备忘录模式是 GoF 行为型模式中专门解决状态保存与恢复的那一个。本文从三个角色（Originator / Memento / Caretaker）拆解，覆盖基础实现、撤销重做、序列化快照和嵌套类封装，附带完整 C# 代码。"
tags: ["C#", "设计模式", "备忘录模式", ".NET"]
slug: "memento-design-pattern-csharp-guide"
ogImage: "../../assets/877/01-cover.png"
source: "https://www.devleader.ca/2026/06/13/memento-design-pattern-in-c-complete-guide-with-examples"
---

你需要把一个对象的内部状态存下来，将来随时能恢复，但又不想把私有字段暴露给外部——这就是备忘录模式（Memento Pattern）精确解决的问题。

换个更具体的说法：你做文字编辑器要支持撤销，做游戏要支持存档，做工作流要支持事务回滚——这些场景的技术本质其实一样：在某个时间点给对象拍一张内部状态的快照，保存起来，必要时再还回去，并且外面的代码全程不知道对象肚子里有哪些字段。

这篇指南从备忘模式的三个角色出发，覆盖基础实现、撤销/重做系统、序列化快照、嵌套类封装，以及生产环境下的实际考量。每一步都附带可以直接跑的 C# 代码。

---

## 备忘录模式的三个角色

备忘录模式有三个参与者，各自职责分得很清楚：

**Originator（发起者）**：要被保存和恢复状态的那个对象。它是唯一知道内部结构的人，也只有它能创建和消费备忘录。

**Memento（备忘录）**：快照本身，是一个不透明的容器。Caretaker 可以持有它、传递它，但不能查看或修改里面的数据。

**Caretaker（看管者）**：负责存储备忘录，决定什么时候拍快照、什么时候恢复。它从不窥探备忘录的内部内容。

这三个角色像一套约定好的交接流程：Caretaker 说「帮我存一下」，Originator 就生成一个 Memento 交给 Caretaker；Caretaker 说「回到之前」，就把 Memento 还给 Originator 恢复。

---

## 什么时候该用

- **撤销/重做**：文字编辑器、绘图工具、表单编辑器里的每一步操作前都存一次状态
- **事务回滚**：操作执行一半失败了，用备忘录回到执行前的状态，不需要写复杂的补偿逻辑
- **存档/检查点**：游戏、长时间工作流、配置向导里定期存快照，用户随时回来
- **版本历史浏览**：文档编辑器里让用户在多个历史版本之间切换

不适合的场景：状态对象很大且快照频繁（内存受不了）、状态结构特别简单（就一个字段就别搬出整个模式了）、或者你只需要细粒度的变更追踪而不是完整快照。

---

## 基础实现

以文本编辑器为例子。编辑器有内容文本和光标位置两个状态字段，我们想随时存、随时恢复。

### 备忘录类

```csharp
public sealed class EditorMemento
{
    public string Content { get; }
    public int CursorPosition { get; }

    public EditorMemento(string content, int cursorPosition)
    {
        Content = content;
        CursorPosition = cursorPosition;
    }
}
```

### Originator（编辑器本身）

```csharp
public sealed class TextEditor
{
    public string Content { get; private set; }
    public int CursorPosition { get; private set; }

    public TextEditor()
    {
        Content = string.Empty;
        CursorPosition = 0;
    }

    public void Type(string text)
    {
        Content = Content.Insert(CursorPosition, text);
        CursorPosition += text.Length;
    }

    public void MoveCursor(int position)
    {
        if (position < 0 || position > Content.Length)
            throw new ArgumentOutOfRangeException(nameof(position));

        CursorPosition = position;
    }

    public EditorMemento Save()
    {
        return new EditorMemento(Content, CursorPosition);
    }

    public void Restore(EditorMemento memento)
    {
        Content = memento.Content;
        CursorPosition = memento.CursorPosition;
    }
}
```

Originator 掌控了快照的创建和恢复两个方向。外部代码不需要知道编辑器里到底哪几个字段构成它的"状态"——这完全是 Originator 自己的事。

### Caretaker（历史管理器）

```csharp
public sealed class EditorHistory
{
    private readonly Stack<EditorMemento> _history = new();

    public void Save(TextEditor editor)
    {
        _history.Push(editor.Save());
    }

    public void Undo(TextEditor editor)
    {
        if (_history.Count == 0)
        {
            Console.WriteLine("Nothing to undo.");
            return;
        }

        EditorMemento memento = _history.Pop();
        editor.Restore(memento);
    }

    public bool HasHistory => _history.Count > 0;
}
```

### 串联起来

```csharp
TextEditor editor = new();
EditorHistory history = new();

history.Save(editor);
editor.Type("Hello, ");
Console.WriteLine($"Content: '{editor.Content}'");

history.Save(editor);
editor.Type("World!");
Console.WriteLine($"Content: '{editor.Content}'");

history.Undo(editor);
Console.WriteLine($"After undo: '{editor.Content}'");

history.Undo(editor);
Console.WriteLine($"After second undo: '{editor.Content}'");
```

输出：

```
Content: 'Hello, '
Content: 'Hello, World!'
After undo: 'Hello, '
After second undo: ''
```

Caretaker 管历史，编辑器自己管创建和消费快照，备忘录在两者之间当信使。三个角色各自的边界没有交叉。

---

## 撤销/重做：双栈结构

基础 Caretaker 只能撤销。完整撤销/重做需要两个栈——一个做 undo，一个做 redo。关键细节：**执行 undo 时先存当前状态到 redo 栈**，**执行新的操作时清空 redo 栈**。

```csharp
public sealed class UndoRedoManager
{
    private readonly Stack<EditorMemento> _undoStack = new();
    private readonly Stack<EditorMemento> _redoStack = new();

    public void SaveState(TextEditor editor)
    {
        _undoStack.Push(editor.Save());
        _redoStack.Clear();  // 新操作让 redo 历史失效
    }

    public void Undo(TextEditor editor)
    {
        if (_undoStack.Count == 0) return;

        _redoStack.Push(editor.Save());
        EditorMemento memento = _undoStack.Pop();
        editor.Restore(memento);
    }

    public void Redo(TextEditor editor)
    {
        if (_redoStack.Count == 0) return;

        _undoStack.Push(editor.Save());
        EditorMemento memento = _redoStack.Pop();
        editor.Restore(memento);
    }

    public bool CanUndo => _undoStack.Count > 0;
    public bool CanRedo => _redoStack.Count > 0;
}
```

用户撤销了几步之后又开始编辑新内容，redo 栈直接清空——这和你熟悉的每一个主流应用的撤销/重做行为一致。

---

## 序列化方式做备忘录

当对象状态很深或者带嵌套集合时，手动拷贝每个字段会很痛苦。这时候用序列化做备忘录就简单很多——把整个状态序列化为 JSON 字符串存起来，恢复时再反序列化回去。

```csharp
public sealed class GameCharacter
{
    public string Name { get; set; } = string.Empty;
    public int Health { get; set; }
    public int Level { get; set; }
    public List<string> Inventory { get; set; } = new();

    public string SaveToMemento()
    {
        var state = new CharacterState
        {
            Name = Name,
            Health = Health,
            Level = Level,
            Inventory = new List<string>(Inventory)
        };
        return JsonSerializer.Serialize(state);
    }

    public void RestoreFromMemento(string memento)
    {
        CharacterState? state =
            JsonSerializer.Deserialize<CharacterState>(memento);

        if (state is null)
            throw new InvalidOperationException(
                "Failed to deserialize memento.");

        Name = state.Name;
        Health = state.Health;
        Level = state.Level;
        Inventory = new List<string>(state.Inventory);
    }

    private sealed class CharacterState
    {
        public string Name { get; set; } = string.Empty;
        public int Health { get; set; }
        public int Level { get; set; }
        public List<string> Inventory { get; set; } = new();
    }
}
```

Caretaker 存的是字符串，按名字索引：

```csharp
public sealed class GameSaveManager
{
    private readonly Dictionary<string, string> _saves = new();

    public void SaveCheckpoint(string name, GameCharacter character)
    {
        _saves[name] = character.SaveToMemento();
    }

    public void LoadCheckpoint(string name, GameCharacter character)
    {
        if (!_saves.TryGetValue(name, out string? memento))
            return;

        character.RestoreFromMemento(memento);
    }

    public IReadOnlyCollection<string> ListCheckpoints()
    {
        return _saves.Keys;
    }
}
```

这种方式的优点：嵌套对象和集合自动处理、存档是人类可读的 JSON 方便调试、新增字段不需要改备忘录类。代价是序列化比直接字段拷贝慢。高频快照场景先做一次性能摸底再决定。

---

## 嵌套类封装：让备忘录彻底不透明

上面的基础实现里，备忘录属性是 public 的——任何拿到备忘录引用的代码都能读里面的数据。如果你需要更严格的封装，C# 的嵌套类可以做到 GoF 原意里的那种"完全不透明"。

```csharp
public sealed class Document
{
    private string _title;
    private string _body;
    private DateTime _lastModified;

    public Document(string title, string body)
    {
        _title = title;
        _body = body;
        _lastModified = DateTime.UtcNow;
    }

    public void UpdateTitle(string title)
    {
        _title = title;
        _lastModified = DateTime.UtcNow;
    }

    public IDocumentMemento Save()
    {
        return new DocumentMemento(_title, _body, _lastModified);
    }

    public void Restore(IDocumentMemento memento)
    {
        if (memento is not DocumentMemento dm)
            throw new ArgumentException("Invalid memento type.", nameof(memento));

        _title = dm.Title;
        _body = dm.Body;
        _lastModified = dm.LastModified;
    }

    private sealed class DocumentMemento : IDocumentMemento
    {
        public string Title { get; }
        public string Body { get; }
        public DateTime LastModified { get; }

        public DocumentMemento(string title, string body, DateTime lastModified)
        {
            Title = title;
            Body = body;
            LastModified = lastModified;
        }
    }
}

public interface IDocumentMemento
{
    // 故意留空——一个不透明的标记接口
}
```

`IDocumentMemento` 是一个没有任何成员的标记接口。外部代码只能拿着这个接口引用来传递，但完全读不到任何字段。只有 Document 自己可以把接口引用转型到私有的 `DocumentMemento` 类去访问属性。

Caretaker 操作的是接口，完全不了解里面装了什么：

```csharp
public sealed class DocumentHistory
{
    private readonly Stack<IDocumentMemento> _snapshots = new();

    public void Save(Document document)
    {
        _snapshots.Push(document.Save());
    }

    public void Undo(Document document)
    {
        if (_snapshots.Count == 0) return;

        IDocumentMemento memento = _snapshots.Pop();
        document.Restore(memento);
    }
}
```

这种实现多了一点点复杂度（嵌套类 + 空接口），换来的是最强的封装保证。Caretaker 没办法窥视备忘录内部，外部代码也没办法凭空构造伪造的快照。

---

## 利与弊

**好处：**

- **封装保护**：Originator 内部状态始终不对外暴露。外部代码接触的是不透明快照，永远看不到被保存的字段
- **Originator 变简单**：Originator 不需要自己管历史。它只需要知道怎么拍快照和怎么从快照恢复。历史管理是 Caretaker 的工作
- **关注点清晰分离**：三个角色各管各的——Originator 管状态，Memento 带数据，Caretaker 管历史
- **历史管理灵活**：Memento 是独立对象，可以放栈里、放字典里、存到磁盘上。Caretaker 可以换任意历史策略但不需要动 Originator 的代码

**代价：**

- **内存消耗**：每个备忘录都是完整快照。状态大并且快照频率高的时候内存会迅速增长。限深、增量快照可以缓解
- **维护负担**：Originator 增加或删除字段时，备忘录类也要跟着改。状态字段越多，这份耦合的维护成本越大
- **Caretaker 生命周期管理**：Caretaker 必须决定保留多少快照、什么时候丢弃旧的。没有淘汰策略，历史会无限增长

---

## 常见问题

**Q：备忘录模式跟简单克隆有什么区别？**

简单克隆（`ICloneable` 或拷贝构造函数）适用于一次性的备份。备忘录模式多了结构化——它把快照和 Originator 清楚分开，提供了历史管理的干净接口，还能精确控制到底哪些状态被捕捉。如果你在做撤销/重做或存档系统，备忘录模式的结构化回报来得很快。

**Q：备忘录模式怎么保持封装？**

通过让备忘录内部数据只对 Originator 可见。最严格的实现里，备忘录是 Originator 内部的 private nested class，外部代码（包括 Caretaker）只能通过一个没有任何成员的标记接口来持有它。Caretaker 可以存、可以取，但不能读也不能改内部的任何东西。

**Q：备忘录模式和命令模式做撤销的区别？**

命令模式通过存储逆向操作来实现撤销——每个命令知道怎么反转自己。备忘录模式通过存储状态快照来实现撤销——直接把对象恢复到之前的状态。命令模式在状态大的时候更省内存（只存变更部分），备忘录模式实现更简单（不需要给每个操作写反向逻辑）。实践中两者经常组合：命令负责动作执行，备忘录负责在命令执行前拍快照。

**Q：怎么控制备忘录的内存使用？**

几个可用策略：给历史数量设上限（超出门槛移除最旧的）；使用增量备忘录只存变更部分而非完整快照；对快照做压缩或序列化减小内存占用；实现分层淘汰策略——近的快照存完整细节，旧的快照合并或丢弃。

**Q：备忘录能持久化到磁盘或数据库吗？**

可以。序列化方式的备忘录就是为这个设计的。把 Originator 的状态序列化为 JSON、XML 或二进制格式，存到文件或数据库里。注意版本问题——如果 Originator 的状态结构在存档和加载之间变了，需要一个处理旧格式快照的迁移策略。

**Q：备忘录模式怎么和依赖注入配合？**

Caretaker 可以注册为 scoped 或 singleton 服务，取决于历史是要按请求还是全局保存。Originator 一般是你的领域对象，由业务逻辑创建，不从容器解析。如果需要持久化，可以把存储服务注入到 Caretaker 里。Memento 对象本身就是普通数据载体，不需要 DI 注册。

---

## 小结

备忘录模式是行为型模式里职责最清楚的那一个：Originator 创建和消费快照，Memento 带着状态走，Caretaker 管历史。三个角色边界分明，实现也不复杂。

在你自己的代码库里找一下——有没有手动逐字段做备份的代码？有没有临时变量存状态等"万一出事就恢复"的操作？这些都可以用备忘录模式整理成一套清楚的结构。

如果和命令模式搭配，能做出完整的撤销/重做流水线；和中介者模式搭配，能在多个对象之间协调状态快照。

---

## 参考

- [Memento Design Pattern in C# — Dev Leader](https://www.devleader.ca/2026/06/13/memento-design-pattern-in-c-complete-guide-with-examples)
- [Design Patterns: Elements of Reusable Object-Oriented Software (GoF)](https://en.wikipedia.org/wiki/Design_Patterns)
