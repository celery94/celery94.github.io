---
pubDatetime: 2026-04-29T10:23:00+08:00
title: "C# Flags 枚举：用位运算组合枚举值"
description: "详细讲解 C# [Flags] 枚举的声明规则、位运算操作（设置、检测、清除、切换标志），以及序列化、常见错误和真实权限系统示例，帮助你正确选用 Flags 枚举。"
tags: ["CSharp", "dotnet", "枚举", "Language Features", "Bitwise"]
slug: "csharp-enum-flags-bitwise-operations"
ogImage: "../../assets/763/01-cover.png"
source: "https://www.devleader.ca/2026/04/28/c-enum-flags-combining-values-with-bitwise-operations"
---

![C# Flags 枚举：用位运算组合枚举值](../../assets/763/01-cover.png)

普通枚举一次只能存一个值。但有时变量需要同时表达多个状态——用户可以同时拥有 `Read` 和 `Write` 权限，而不是只能二选一。这正是 C# `[Flags]` 枚举的用武之地。

`[Flags]` 属性把一个普通枚举变成位字段（bitfield）。每个成员对应一个独立的比特位，可以单独开关。用按位 OR 组合多个成员，用按位 AND 检测单个成员，`ToString()` 自动输出有意义的名称而不是数字。这篇文章从声明规则讲到真实场景，覆盖全部常用操作。

## 什么是 Flags 枚举

Flags 枚举是一个加了 `[Flags]` 属性的普通枚举，每个成员都被赋予 2 的幂次方值。因为 2 的幂次方之间没有重叠的位，任意组合都会产生唯一的整数：

```csharp
None    = 0  = 0000
Read    = 1  = 0001
Write   = 2  = 0010
Execute = 4  = 0100
```

`Read | Write` 的结果是 `0001 | 0010 = 0011 = 3`，可以唯一还原出"Read 和 Write 都设置了"这个信息。

没有 `[Flags]`，技术上也能对枚举做位运算，但 `ToString()` 会输出数字而非标志名，工具和序列化框架也会忽略这个设计意图。

## 声明 Flags 枚举

```csharp
[Flags]
public enum FileAccess
{
    None      = 0,
    Read      = 1,            // 0001
    Write     = 2,            // 0010
    Execute   = 4,            // 0100
    ReadWrite = Read | Write  // 0011 -- 复合便捷值
}
```

声明时有三条规则：

1. **包含 `None = 0`**：表示"没有任何标志"，对默认初始化和清除操作很重要。
2. **每个独立标志使用 2 的幂次方**：`1, 2, 4, 8, 16...`
3. **复合便捷值用命名成员组合**，不要直接写原始整数：`ReadWrite = Read | Write` 比 `ReadWrite = 3` 更清晰。

一个常见错误是连续写 `1, 2, 3, 4`：

```csharp
// 错误 -- 3 与 1|2 的结果相同，无法区分
[Flags]
public enum Permissions
{
    Read    = 1,
    Write   = 2,
    Execute = 3,  // 应该是 4！
    Delete  = 4   // 应该是 8！
}
```

`Execute = 3` 时，你永远无法判断一个变量是持有"Execute"还是"Read 和 Write"。独立标志必须用 2 的幂次方。

## 设置与组合标志

用按位 OR 组合多个标志：

```csharp
// 授予 Read 和 Execute 权限
FileAccess access = FileAccess.Read | FileAccess.Execute;
Console.WriteLine(access);      // "Read, Execute"（因为有 [Flags]）
Console.WriteLine((int)access); // 5（0001 | 0100 = 0101）

// 追加一个标志
access |= FileAccess.Write;
Console.WriteLine(access);  // "Read, Write, Execute"

// 移除一个标志
access &= ~FileAccess.Write;
Console.WriteLine(access);  // "Read, Execute"
```

`|=` 追加标志；`&= ~flag` 移除标志。波浪号 `~` 是按位 NOT，把目标位取反后再 AND，只清除那一位。

## 检测标志是否设置

两种方式：按位 AND 或 `HasFlag()`：

```csharp
FileAccess access = FileAccess.Read | FileAccess.Execute;

// 按位 AND -- 明确，无额外开销
bool canRead    = (access & FileAccess.Read)    != 0;  // true
bool canWrite   = (access & FileAccess.Write)   != 0;  // false
bool canExecute = (access & FileAccess.Execute) != 0;  // true

// HasFlag -- 可读性好，旧运行时有装箱开销
bool alsoCanRead = access.HasFlag(FileAccess.Read);    // true
```

`HasFlag` 从 .NET Framework 4 开始提供。在现代 .NET（5+）中，JIT 经常内联 `HasFlag`，性能和按位 AND 相当。不过在极度性能敏感的热路径上，按位 AND 仍是最安全的选择。

检测是否**全部设置**：

```csharp
FileAccess required = FileAccess.Read | FileAccess.Write;
bool hasAll = (access & required) == required;
```

检测是否**任意一个设置**：

```csharp
bool hasAny = (access & required) != 0;
```

## 清除与切换标志

```csharp
FileAccess access = FileAccess.Read | FileAccess.Write | FileAccess.Execute;

// 移除 Write
access &= ~FileAccess.Write;
Console.WriteLine(access);  // "Read, Execute"

// 清空所有标志
access = FileAccess.None;

// 切换标志（无论当前状态，翻转它）
access ^= FileAccess.Read;
Console.WriteLine(access);  // "Read"（原来关，现在开）
access ^= FileAccess.Read;
Console.WriteLine(access);  // "None"（原来开，现在关）
```

XOR（`^=`）切换的应用场景不多，但在不想先判断当前状态就直接翻转时很方便——比如实现 UI 中的"启用/禁用"开关。

## ToString() 与解析

加了 `[Flags]` 后，`ToString()` 输出逗号分隔的标志名列表：

```csharp
FileAccess access = FileAccess.Read | FileAccess.Execute;

Console.WriteLine(access.ToString());    // "Read, Execute"
Console.WriteLine(access.ToString("G")); // "Read, Execute"（通用格式）
Console.WriteLine(access.ToString("D")); // "5"（十进制）
Console.WriteLine(access.ToString("F")); // "Read, Execute"（Flags 格式）
Console.WriteLine(access.ToString("X")); // "00000005"（十六进制）
```

没有 `[Flags]` 时，`access.ToString()` 只输出 `"5"`。

解析和普通枚举一样：

```csharp
if (Enum.TryParse<FileAccess>("Read, Execute", out FileAccess parsed))
{
    Console.WriteLine(parsed);        // "Read, Execute"
    Console.WriteLine((int)parsed);   // 5
}

if (Enum.TryParse<FileAccess>("ReadWrite", out FileAccess rw))
{
    Console.WriteLine(rw.HasFlag(FileAccess.Read));   // true
    Console.WriteLine(rw.HasFlag(FileAccess.Write));  // true
}
```

## 底层类型用 long 的场景

默认 `int` 提供 32 位，但最高位（`1 << 31`）会产生负值。实际可用的独立标志数量限制在 31 个。需要更多时，换用 `long`：

```csharp
[Flags]
public enum LargePermissions : long
{
    None         = 0L,
    Permission1  = 1L << 0,
    Permission2  = 1L << 1,
    // ...
    Permission63 = 1L << 62
}
```

用 `1L << n` 语法清晰明了。直接写 `1 << 31` 会因为有符号溢出产生 -2147483648；换 `long` 后要用 `1L << 31` 才能避免这个问题。

实践中，如果一个枚举的标志超过 20-30 个，通常说明设计需要重新审视——可以考虑把标志拆分成多个职责更集中的小枚举。

## Flags 枚举 vs 普通枚举

| 场景 | 用 Flags | 用普通枚举 |
|------|---------|-----------|
| 变量只持有一个值 | 否 | 是 |
| 变量可以同时持有多个值 | 是 | 否 |
| 示例：DayOfWeek | 否（一次只能是一天） | 是 |
| 示例：工作日组合（周一+周二+周三） | 是 | 否 |
| 示例：HttpMethod | 否 | 是 |
| 示例：FileAccess | 是 | 否 |

一个快速判断：变量能否同时合理地是"X 又是 Y"？能——用 Flags；不能——用普通枚举。

## 序列化 Flags 枚举

`System.Text.Json` 配合 `JsonStringEnumConverter` 会把 Flags 枚举序列化为逗号分隔的名称字符串：

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

var options = new JsonSerializerOptions
{
    Converters = { new JsonStringEnumConverter() }
};

FileAccess access = FileAccess.Read | FileAccess.Execute;

string json = JsonSerializer.Serialize(access, options);
Console.WriteLine(json);  // "Read, Execute"

FileAccess deserialized = JsonSerializer.Deserialize<FileAccess>(json, options)!;
Console.WriteLine(deserialized.HasFlag(FileAccess.Read));    // true
Console.WriteLine(deserialized.HasFlag(FileAccess.Execute)); // true
```

在设计 API 时，字符串枚举序列化优于整数序列化：payload 自带文档含义，客户端代码也不会依赖内部数值。

## 真实示例：用户权限系统

Flags 枚举最常见的实际用途是权限系统：

```csharp
[Flags]
public enum UserPermission
{
    None         = 0,
    ViewContent  = 1 << 0,   // 1
    CreatePost   = 1 << 1,   // 2
    EditPost     = 1 << 2,   // 4
    DeletePost   = 1 << 3,   // 8
    ManageUsers  = 1 << 4,   // 16
    AdminAccess  = 1 << 5,   // 32

    // 复合角色
    Contributor  = ViewContent | CreatePost,
    Editor       = Contributor | EditPost | DeletePost,
    Admin        = Editor | ManageUsers | AdminAccess
}

public class User
{
    public UserPermission Permissions { get; set; }

    public bool Can(UserPermission permission)
        => Permissions.HasFlag(permission);
}

// 使用示例
var user = new User { Permissions = UserPermission.Contributor };

Console.WriteLine(user.Can(UserPermission.ViewContent));  // true
Console.WriteLine(user.Can(UserPermission.ManageUsers));  // false

// 授予权限
user.Permissions |= UserPermission.EditPost;
Console.WriteLine(user.Can(UserPermission.EditPost));     // true

// 撤销权限
user.Permissions &= ~UserPermission.EditPost;
Console.WriteLine(user.Can(UserPermission.EditPost));     // false
```

这是一个整洁高效的权限模型：数据库只需要存一个整数列，权限检查是一次位运算，`Editor`、`Admin` 等复合角色让代码保持可读性。

## 常见错误

**不使用 2 的幂次方**：`1, 2, 3, 4` 这样的值会产生歧义组合。改用 `1, 2, 4, 8` 或 `1 << n` 语法。

**忘记 `None = 0`**：没有 `None` 时，无法表达"没有任何标志"，`default(MyFlags)` 是一个没有名称的 `0`，在 switch 语句和 `HasFlag` 检查时会出问题。

**用 `== 0` 而不是检查 `None` 成员**：`access == FileAccess.None` 比 `(int)access == 0` 在语义上更清晰。

**在非 2 的幂次方枚举上加 `[Flags]`**：`[Flags]` 只是文档和格式化提示，C# 不会阻止你——但 `ToString()` 会输出令人困惑的结果，组合操作语义也会不明确。

## 参考

- [C# Enum Flags: Combining Values with Bitwise Operations](https://www.devleader.ca/2026/04/28/c-enum-flags-combining-values-with-bitwise-operations)
- [C# Enum Complete Guide](https://www.devleader.ca/2026/04/26/c-enum-complete-guide-to-enumerations-in-net)
- [How to Use Enum in C#](https://www.devleader.ca/2026/04/27/how-to-use-enum-in-c-declaration-values-and-best-practices)
