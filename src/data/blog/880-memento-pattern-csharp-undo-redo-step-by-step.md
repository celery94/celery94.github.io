---
pubDatetime: 2026-06-16T08:20:01+08:00
title: "C# 备忘录模式实战：一步步实现撤销与重做"
description: "备忘录模式适合在不暴露对象内部字段的前提下保存状态快照。本文用文本编辑器场景，按 IMemento 接口、Originator 私有快照、Caretaker 历史、撤销/重做双栈和 xUnit 测试几个步骤，带你写出一套可运行的 C# 实现。"
tags: ["C#", "设计模式", "备忘录模式", ".NET", "单元测试"]
slug: "memento-pattern-csharp-undo-redo-step-by-step"
ogImage: "../../assets/880/01-cover.png"
source: "https://www.devleader.ca/2026/06/15/how-to-implement-memento-pattern-in-c-stepbystep-guide"
---

备忘录模式（Memento Pattern）解决的是一个很常见的问题：你想把对象当前状态保存下来，之后能恢复回去，同时又不想把对象内部字段暴露给外部代码。

这篇原文偏实操，目标是从零写出一个支持撤销和重做的 C# 文本编辑器示例。它和上一篇偏完整概念拆解的文章不同，这里更适合照着代码走一遍：先定义快照接口，再让编辑器自己创建快照，接着用历史管理器保存快照，然后用两个栈实现 undo / redo。

## 前置知识

照着实现前，你最好熟悉这些基础：

- C# 接口与类：`IMemento` 会作为快照契约。
- 封装：外部代码不能直接读写快照里的真实状态。
- `Stack<T>`：撤销和重做会用两个栈配合。
- xUnit：测试通过公开属性验证恢复后的行为。
- .NET 8 或较新的 SDK：原文示例使用现代 C# 写法。

## 第一步：定义快照接口

快照接口只暴露给 Caretaker 管理历史时需要的信息。它不应该泄露真正的业务状态。

```csharp
public interface IMemento
{
    string Description { get; }

    DateTime CreatedAt { get; }
}
```

`Description` 可以用来显示或记录快照，`CreatedAt` 用来排序或清理旧快照。注意这里没有 `Content`、`CursorPosition` 之类的字段。Caretaker 能拿着快照排队、入栈、出栈，却不能改里面的状态。

这正是备忘录模式的关键边界：Originator 负责创建和读取快照，Caretaker 只负责保存快照。

## 第二步：让编辑器保存自己

Originator 是被保存和恢复状态的对象。这里用一个 `TextEditor`，它有两个状态：正文内容和光标位置。

```csharp
public sealed class TextEditor
{
    public string Content { get; private set; } = string.Empty;

    public int CursorPosition { get; private set; }

    public void Type(string text)
    {
        Content = Content.Insert(CursorPosition, text);
        CursorPosition += text.Length;
    }

    public void MoveCursor(int position)
    {
        if (position < 0 || position > Content.Length)
        {
            throw new ArgumentOutOfRangeException(
                nameof(position),
                "Cursor position is out of range.");
        }

        CursorPosition = position;
    }
}
```

接下来给它加上 `Save` 和 `Restore`。快照实现类放在 `TextEditor` 里面，做成 `private sealed class`：

```csharp
public IMemento Save()
{
    return new EditorMemento(Content, CursorPosition);
}

public void Restore(IMemento memento)
{
    if (memento is not EditorMemento editorMemento)
    {
        throw new ArgumentException(
            "Invalid memento type.",
            nameof(memento));
    }

    Content = editorMemento.SavedContent;
    CursorPosition = editorMemento.SavedCursorPosition;
}

private sealed class EditorMemento : IMemento
{
    public string SavedContent { get; }

    public int SavedCursorPosition { get; }

    public string Description =>
        $"Content length: {SavedContent.Length}, " +
        $"Cursor: {SavedCursorPosition}";

    public DateTime CreatedAt { get; } = DateTime.UtcNow;

    public EditorMemento(string content, int cursorPosition)
    {
        SavedContent = content;
        SavedCursorPosition = cursorPosition;
    }
}
```

这段代码有三个细节值得保留：

- `Save` 返回 `IMemento`，外部只看到窄接口。
- `EditorMemento` 是私有嵌套类，外部不能访问 `SavedContent`。
- `Restore` 会检查快照类型，避免把别的 Originator 的快照传进来。

快照对象创建后也不再变化，这能减少撤销时的意外。

## 第三步：加入历史管理器

Caretaker 保存快照，但不查看快照内部内容。最简单的版本可以用一个列表：

```csharp
public sealed class EditorHistory
{
    private readonly List<IMemento> _snapshots = new();

    public IReadOnlyList<IMemento> Snapshots => _snapshots;

    public void Push(IMemento memento)
    {
        if (memento is null)
        {
            throw new ArgumentNullException(nameof(memento));
        }

        _snapshots.Add(memento);
    }

    public IMemento? Pop()
    {
        if (_snapshots.Count == 0)
        {
            return null;
        }

        int lastIndex = _snapshots.Count - 1;
        IMemento memento = _snapshots[lastIndex];
        _snapshots.RemoveAt(lastIndex);

        return memento;
    }

    public void Clear()
    {
        _snapshots.Clear();
    }
}
```

使用时，状态变化后保存一次，回退时取出最近的快照并恢复：

```csharp
var editor = new TextEditor();
var history = new EditorHistory();

editor.Type("Hello");
history.Push(editor.Save());

editor.Type(", World!");
history.Push(editor.Save());

IMemento? snapshot = history.Pop();
if (snapshot is not null)
{
    editor.Restore(snapshot);
}
```

真实产品里，你可能还会给历史记录加上最大长度、磁盘存储或压缩策略。但这些变化都应该待在 Caretaker 内部，不要让编辑器去关心。

## 第四步：实现撤销

撤销的规则很直接：每次做会改变状态的操作前，先保存当前状态；用户撤销时，从栈里取出最近快照并恢复。

```csharp
public sealed class UndoableEditor
{
    private readonly TextEditor _editor;
    private readonly Stack<IMemento> _undoStack = new();

    public string Content => _editor.Content;

    public int CursorPosition => _editor.CursorPosition;

    public int UndoCount => _undoStack.Count;

    public UndoableEditor(TextEditor editor)
    {
        _editor = editor
            ?? throw new ArgumentNullException(nameof(editor));
    }

    public void Type(string text)
    {
        SaveForUndo();
        _editor.Type(text);
    }

    public bool Undo()
    {
        if (_undoStack.Count == 0)
        {
            return false;
        }

        IMemento snapshot = _undoStack.Pop();
        _editor.Restore(snapshot);

        return true;
    }

    private void SaveForUndo()
    {
        _undoStack.Push(_editor.Save());
    }
}
```

这里保存的是“操作前状态”。比如当前为空，输入 `Hello` 前先保存空状态；撤销时恢复这个空状态。这个时机很重要，保存错了就会出现“撤销后没变化”的问题。

## 第五步：加入重做

重做需要第二个栈。原文把规则讲得很清楚：

- 正常操作：当前状态进 undo 栈，执行操作，清空 redo 栈。
- Undo：当前状态进 redo 栈，从 undo 栈取快照恢复。
- Redo：当前状态进 undo 栈，从 redo 栈取快照恢复。

核心实现如下：

```csharp
public sealed class UndoRedoEditor
{
    private readonly TextEditor _editor;
    private readonly Stack<IMemento> _undoStack = new();
    private readonly Stack<IMemento> _redoStack = new();

    public string Content => _editor.Content;

    public int UndoCount => _undoStack.Count;

    public int RedoCount => _redoStack.Count;

    public UndoRedoEditor(TextEditor editor)
    {
        _editor = editor
            ?? throw new ArgumentNullException(nameof(editor));
    }

    public void Type(string text)
    {
        SaveForUndo();
        _editor.Type(text);
        _redoStack.Clear();
    }

    public bool Undo()
    {
        if (_undoStack.Count == 0)
        {
            return false;
        }

        _redoStack.Push(_editor.Save());
        IMemento snapshot = _undoStack.Pop();
        _editor.Restore(snapshot);

        return true;
    }

    public bool Redo()
    {
        if (_redoStack.Count == 0)
        {
            return false;
        }

        _undoStack.Push(_editor.Save());
        IMemento snapshot = _redoStack.Pop();
        _editor.Restore(snapshot);

        return true;
    }

    private void SaveForUndo()
    {
        _undoStack.Push(_editor.Save());
    }
}
```

`_redoStack.Clear()` 很容易漏。用户撤销后如果又输入新内容，之前可重做的路径就应该失效。文本编辑器、设计工具、表格工具基本都遵守这个直觉。

## 第六步：写测试

因为快照内部是隐藏的，测试也不应该去窥探它。正确做法是通过公开属性验证行为。

```csharp
public class UndoRedoEditorTests
{
    [Fact]
    public void Undo_RestoresPreviousState()
    {
        var editor = new TextEditor();
        var undoRedo = new UndoRedoEditor(editor);

        undoRedo.Type("Hello");
        undoRedo.Type(" World");
        undoRedo.Undo();

        Assert.Equal("Hello", undoRedo.Content);
    }

    [Fact]
    public void Redo_RestoresUndoneState()
    {
        var editor = new TextEditor();
        var undoRedo = new UndoRedoEditor(editor);

        undoRedo.Type("Hello");
        undoRedo.Type(" World");
        undoRedo.Undo();
        undoRedo.Redo();

        Assert.Equal("Hello World", undoRedo.Content);
    }

    [Fact]
    public void NewAction_ClearsRedoStack()
    {
        var editor = new TextEditor();
        var undoRedo = new UndoRedoEditor(editor);

        undoRedo.Type("First");
        undoRedo.Type(" Second");
        undoRedo.Undo();
        undoRedo.Type(" Third");

        Assert.Equal(0, undoRedo.RedoCount);
        Assert.Equal("First Third", undoRedo.Content);
    }
}
```

还可以补这些边界：

- 空 undo 栈时，`Undo()` 返回 `false`。
- 空 redo 栈时，`Redo()` 返回 `false`。
- 连续多次撤销能回到初始状态。
- 每个测试都创建新对象，避免测试之间共享状态。

## 常见坑

**把快照内部暴露给 Caretaker。** 一旦 Caretaker 能读写真实状态，封装边界就被打破。私有嵌套类是 C# 里比较干净的写法。

**只复制引用。** 如果 Originator 里有 `List<T>`、`Dictionary<TKey, TValue>` 或可变对象，只把引用塞进快照会出错。原对象后续变化会影响快照，需要深拷贝或不可变对象。

**历史无限增长。** 每个快照都占内存。大文档、复杂对象、长时间编辑场景下，要限制 undo 栈大小，或改用增量 diff。

**新操作后忘记清空 redo。** 撤销后又输入新内容，旧 redo 路径应该作废。否则用户可能重做到一个已经不合理的状态。

**场景更适合 Command Pattern。** 如果操作天然可逆，比如“插入一行”“删除一个字符”，命令模式可能更省内存。备忘录模式更适合状态复杂、单个操作难以反向推导的对象。

## 结语

C# 里实现备忘录模式，最核心的做法是让 Originator 自己负责保存和恢复状态，让 Caretaker 只保存 `IMemento`，不要接触真实字段。

当你要做撤销/重做、检查点、状态回滚时，可以从这套结构开始：私有嵌套快照保护封装，undo / redo 双栈管理历史，再用测试覆盖空栈、新操作清空 redo、连续撤销这些边界。这样代码不复杂，行为也比较容易讲清楚。

如果你关注 AI 助手、开发工具和软件工程实践，可以关注 Aide Hub。这里会继续分享可操作的工具教程、技术观察和项目经验。

## 参考

- [How to Implement Memento Pattern in C#: Step-by-Step Guide](https://www.devleader.ca/2026/06/15/how-to-implement-memento-pattern-in-c-stepbystep-guide)
