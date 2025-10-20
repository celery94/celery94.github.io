---
pubDatetime: 2025-10-20
title: 深入理解 C# Dispose 模式：从基础实现到最佳实践
description: 全面解析 C# 中 IDisposable 接口的实现模式，涵盖基础 Dispose、完整 Dispose、继承场景与异步释放，帮助开发者正确管理非托管资源，避免内存泄漏。
tags: [".NET", "C#", "Best Practices", "Performance"]
slug: csharp-dispose-pattern-best-practices
source: https://blog.ivankahl.com/csharp-dispose-pattern
---

# 深入理解 C# Dispose 模式：从基础实现到最佳实践

## 引言

在 .NET 开发中，垃圾回收器（Garbage Collector，GC）为我们自动管理着托管内存，极大地简化了内存管理工作。然而，当应用程序使用非托管资源（如文件句柄、数据库连接、网络套接字等）时，GC 无法自动清理这些资源。这时就需要通过实现 `IDisposable` 接口来确保资源被正确释放，避免内存泄漏和资源耗尽。

本文将深入探讨 C# 中的 Dispose 模式，从基础实现到高级场景，帮助开发者掌握正确的资源管理方法。

## .NET 中的资源管理机制

### 托管内存与垃圾回收

.NET 运行时为应用程序的引用类型（Reference Types）管理着一个内存堆。运行时负责内存分配，而垃圾回收器负责自动回收不再使用的对象内存，并通过压缩堆来优化内存布局。这一机制让开发者无需手动释放内存。

引用类型是指其值存储在堆上而非栈上的类型。当将引用类型赋值给变量时，变量实际存储的是堆上对象的引用，而非对象本身。这与值类型（Value Types）不同，值类型的变量直接存储实际值。

### 非托管资源的挑战

尽管运行时管理着托管内存，但应用程序经常需要使用非托管资源。这些资源的内存位于运行时的控制和可见范围之外，包括文件句柄、数据库连接和网络套接字等。由于 GC 无法看到这些资源，就无法自动回收或压缩这些内存。因此，类本身需要负责释放这些非托管资源，以防止内存泄漏。

为了解决这个问题，.NET 提供了 `IDisposable` 接口来实现资源的确定性清理（Deterministic Cleanup）。通过实现该接口，开发者可以精确控制资源释放的时机。

## 基础 Dispose 模式：简单而实用的实现

### 典型场景：包装已有的 IDisposable 类

在大多数情况下，类需要处理的非托管资源已经被封装在实现了 `IDisposable` 接口的类中。例如，使用 `NpgsqlConnection` 类建立与 PostgreSQL 数据库的连接时，虽然数据库连接本身是非托管资源，但 `NpgsqlConnection` 类已经实现了 `Dispose()` 方法来管理这些资源。此时，你的类的 `Dispose()` 方法只需调用数据库连接的 `Dispose()` 方法即可。

下面是一个典型的实现示例：

```csharp
public class CustomerRepository : IDisposable
{
    private bool _disposed = false;
    private readonly NpgsqlConnection _connection;

    public CustomerRepository(string connectionString)
    {
        _connection = new NpgsqlConnection(connectionString);
        _connection.Open();
    }

    public Customer? Get(int id)
    {
        // 使用数据库连接查询客户信息
        using var command = new NpgsqlCommand("SELECT * FROM customers WHERE id = @id", _connection);
        command.Parameters.AddWithValue("id", id);

        using var reader = command.ExecuteReader();
        if (reader.Read())
        {
            return new Customer
            {
                Id = reader.GetInt32(0),
                Name = reader.GetString(1)
            };
        }

        return null;
    }

    public void Dispose()
    {
        // 检查是否已经释放，确保幂等性
        if (_disposed)
            return;

        _disposed = true;

        // 调用数据库连接的 Dispose() 方法进行清理
        _connection.Dispose();
    }
}
```

注意 `CustomerRepository.Dispose()` 方法如何调用底层数据库连接来释放资源。非托管资源已得到妥善处理，实现非常简单直接。

`_disposed` 字段用于跟踪 `Dispose()` 方法是否已被调用。这很重要，因为 `Dispose()` 方法应该始终是幂等的（Idempotent），即多次调用不应引发异常或产生副作用。

### 使用 using 语句自动释放资源

在使用实现了 `IDisposable` 的类时，应该使用 `using` 语句块，它会在代码块结束时自动调用 `Dispose()` 方法：

```csharp
using (var repository = new CustomerRepository(_connectionString))
{
    var customer = repository.Get(123);
    // 使用 repository 进行操作...
} // 在这里自动调用 repository.Dispose()
```

你也可以使用简化的 `using` 声明语法，此时 `Dispose()` 方法将在包围代码块结束时被调用：

```csharp
private Customer? FindCustomer(int id)
{
    // 使用 using var 创建 repository
    using var repository = new CustomerRepository(_connectionString);

    return repository.Get(id);
} // 函数返回后自动调用 repository.Dispose()
```

在上面的代码片段中，`Dispose()` 方法会在函数返回后自动调用。

### 级联 Dispose 调用的重要性

每当你的类拥有（owns）实现了 `IDisposable` 的对象时，必须实现 `IDisposable` 接口并在自己的 `Dispose()` 方法中调用这些对象的 `Dispose()` 方法，以确保正确的清理。这种级联调用确保了资源释放的完整性。

但需要注意的是，如果你的类不拥有该资源（例如，通过构造函数注入的依赖项），则不需要负责释放它。

## 完整 Dispose 模式：直接处理非托管资源

### 何时需要完整模式

基础 Dispose 模式足以满足大多数场景。但在某些情况下，你可能需要直接处理非托管资源（即它们没有被封装在 `IDisposable` 类中）。此时需要考虑更多的实现细节。

下面是一个直接处理 Windows 文件句柄的完整实现示例：

```csharp
using Microsoft.Win32.SafeHandles;
using System.ComponentModel;
using System.Runtime.InteropServices;

public class UnmanagedFileHandler : IDisposable
{
    // 原始的非托管资源指针
    private IntPtr _handle;

    // 托管资源
    private readonly MemoryStream _buffer;

    private bool _disposed = false;

    // 为清晰起见，使用常量表示无效句柄值
    private static readonly IntPtr INVALID_HANDLE_VALUE = new(-1);

    // 从 Windows API 导入 CreateFile 函数
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateFile(
        string lpFileName,
        uint dwDesiredAccess,
        uint dwShareMode,
        IntPtr lpSecurityAttributes,
        uint dwCreationDisposition,
        uint dwFlagsAndAttributes,
        IntPtr hTemplateFile);

    // 导入 CloseHandle 函数
    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseHandle(IntPtr hObject);

    // Windows API 的文件访问常量
    private const uint GENERIC_WRITE = 0x40000000;
    private const uint CREATE_ALWAYS = 2;
    private const uint NO_SHARING = 0;
    private const uint DEFAULT_ATTRIBUTES = 0;

    public UnmanagedFileHandler(string filePath)
    {
        // 调用非托管 Windows API 获取文件句柄
        _handle = CreateFile(
            filePath,
            GENERIC_WRITE,
            NO_SHARING,
            IntPtr.Zero,
            CREATE_ALWAYS,
            DEFAULT_ATTRIBUTES,
            IntPtr.Zero);

        _buffer = new MemoryStream();

        // 检查句柄是否有效，如果无效则抛出异常
        if (_handle == INVALID_HANDLE_VALUE)
            throw new Win32Exception(
                Marshal.GetLastWin32Error(),
                "Failed to create the file handle.");
    }

    // 文件操作方法...

    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    ~UnmanagedFileHandler()
    {
        Dispose(false);
    }

    protected virtual void Dispose(bool disposing)
    {
        if (_disposed)
            return;

        if (disposing)
        {
            // 如果从 Dispose() 调用，则释放托管资源
            _buffer.Dispose();
        }

        // 始终释放非托管资源
        if (_handle != IntPtr.Zero && _handle != INVALID_HANDLE_VALUE)
        {
            CloseHandle(_handle);
            _handle = IntPtr.Zero;
        }

        _disposed = true;
    }
}
```

### 理解完整模式的关键要素

这段代码包含了几个重要的概念：

**1. 非托管资源的直接管理**

类中的 `IntPtr` 指向一个文件，通过 Windows 底层的 `CreateFile` 方法创建。这个指针是必须手动清理的非托管资源。

**2. 托管与非托管资源的混合**

类还创建了一个 `MemoryStream` 作为缓冲区。虽然这也是非托管资源，但由于 `MemoryStream` 类实现了 `IDisposable`，只需调用其 `Dispose()` 方法即可。

**3. 重载的 Dispose 方法**

引入了新的 `Dispose(bool disposing)` 方法，用于清理托管和非托管资源。该方法可以从两个地方调用：`IDisposable.Dispose()` 方法或类的终结器（Finalizer）。

### 终结器的作用

终结器（Finalizer）是 C# 中析构函数的另一个名称，其签名简洁：`~ClassName() {}`。GC 在回收对象内存之前会调用终结器。

当调用 `Dispose(bool disposing)` 方法时，`disposing` 参数的值取决于调用来源：

- 当从 `IDisposable.Dispose()` 调用时，`disposing` 为 `true`，表示应清理托管和非托管资源
- 当从终结器调用时，`disposing` 为 `false`，因此只清理非托管资源。这是因为 GC 会终结所拥有的托管资源，无需手动调用它们的 `Dispose()` 方法

### 性能优化：抑制终结器

在 `Dispose()` 方法中调用 `GC.SuppressFinalize()` 告诉 GC 不需要调用该类的终结器方法。这对性能至关重要，因为终结器的执行效率并不高。

当 GC 遇到需要回收的带有终结器的类时，它首先将该终结器放入队列中稍后执行，以防止当前 GC 运行被立即调用终结器而延迟。当前 GC 运行结束后，才执行终结器。只有在终结器执行后，该类才有资格被回收。

通过抑制类的终结器，该类的内存可以立即被回收，而无需等待终结器先执行。这显著提高了性能和资源回收效率。

### 支持继承的设计

`Dispose(bool disposing)` 方法被标记为 `virtual`，这是为了支持类继承场景。下一节将详细说明为什么这对于 `IDisposable` 的类继承是必要的。

## 处理继承场景：子类的资源释放

### 子类资源的级联清理

如果子类继承自实现了 `IDisposable` 的父类，并且子类使用了自己的非托管资源，那么子类的资源也需要被清理，同时还要清理父类的资源。

由于 `Dispose(bool disposing)` 方法是 `virtual` 的，子类可以在类被释放时执行自己的清理逻辑。下面是一个继承示例：

```csharp
public class LogFileHandler : UnmanagedFileHandler
{
    private bool _disposed = false;
    private readonly MemoryStream _logBuffer;

    public LogFileHandler(string filePath) : base(filePath)
    {
        _logBuffer = new MemoryStream();
    }

    public void WriteLog(string message)
    {
        // 写入日志到缓冲区...
    }

    // 重写父类的 Dispose 方法来清理额外的资源
    protected override void Dispose(bool disposing)
    {
        if (_disposed)
            return;

        _disposed = true;

        if (disposing)
        {
            // 释放额外的托管资源
            _logBuffer.Dispose();
        }

        // 此子类中没有需要清理的非托管资源

        // 调用基类的 Dispose 方法
        base.Dispose(disposing);
    }
}
```

`LogFileHandler` 类有自己的 `MemoryStream` 字段用于缓冲日志消息。由于这个资源实现了 `IDisposable` 接口，`LogFileHandler` 必须重写父类的 `Dispose(bool disposing)` 方法来释放缓冲区。在重写方法时，必须调用基类的 `Dispose(bool disposing)` 方法。

由于 `Dispose(bool disposing)` 方法已经在基类的 `IDisposable.Dispose()` 和终结器中被调用，因此在 `LogFileHandler` 类中无需再次实现它们。

### 密封类的简化处理

如果你的 `IDisposable` 类永远不会被继承，可以将类标记为 `sealed` 并从 `Dispose(bool disposing)` 方法中移除 `virtual` 标志，简化实现。

## Dispose 模式的最佳实践

### 1. 确保幂等性

`Dispose()` 方法的调用应该始终是幂等的，以避免抛出异常。如果在释放属性时将其设置为无效值（如 `null`），可能会导致问题：

```csharp
// 不好的做法
public void Dispose()
{
    _connection.Dispose();
    _connection = null; // 可能导致下次调用时出现 NullReferenceException
}
```

如果因为某种原因再次调用上述 `Dispose()` 方法，将抛出 `NullReferenceException`，因为 `_connection` 已被设置为 `null`。

最佳做法是使用私有 `_disposed` 字段来跟踪是否已经执行过释放：

```csharp
// 正确的做法
public void Dispose()
{
    if (_disposed)
        return;

    _disposed = true;

    _connection.Dispose();
    _connection = null;
}
```

现在，如果多次调用该方法，它会提前返回，避免重复执行清理逻辑。

### 2. 终结器中不要抛出异常

在实现释放资源的终结器时，避免抛出任何异常至关重要，因为它们可能产生意想不到的副作用，甚至导致整个应用程序崩溃。

始终尽可能防御性地编写终结器，防止未处理的异常浮出水面。

### 3. 级联释放所拥有的资源

任何拥有实现了 `IDisposable` 的资源的类都必须实现 `IDisposable` 接口，并在自己的 `Dispose()` 方法中调用这些资源的 `Dispose()` 方法。如果不这样做，拥有的资源将不会被释放，可能导致内存泄漏。

### 4. 始终调用基类的 Dispose

如果类继承自另一个实现了 `IDisposable` 的类，确保重写 `Dispose(bool disposing)` 方法以释放继承类中的任何非托管资源。

同时，始终从重写的方法中调用基类的 `Dispose(bool disposing)` 方法。

### 5. 使用 SafeHandle 管理非托管资源

如果你的类直接处理非托管资源（即资源没有现有的 `IDisposable` 包装器，如 `IntPtr`），则需要完整的 Dispose 模式。然而，.NET 运行时提供了 `SafeHandle` 类，可以将任何原始非托管 `IntPtr` 包装在 `IDisposable` 中。这些包装类为你管理指针，意味着你的类只需要实现基础 Dispose 模式。

官方文档详细介绍了 SafeHandles 以及它们如何简化类的释放。

### 6. 使用 IAsyncDisposable 进行异步释放

当你的类持有的资源在清理期间涉及异步操作（如关闭数据库连接或释放锁）时，应该实现 `IAsyncDisposable` 接口而不是（或除了）`IDisposable`。这允许非阻塞清理，保持应用程序的响应性。

`IAsyncDisposable` 接口要求实现一个 `ValueTask DisposeAsync()` 方法：

```csharp
public class CustomerRepository : IAsyncDisposable
{
    private readonly NpgsqlConnection _connection;
    private readonly MemoryStream _buffer;

    public CustomerRepository(string connectionString)
    {
        _connection = new NpgsqlConnection(connectionString);
        _buffer = new MemoryStream();
    }

    public async ValueTask DisposeAsync()
    {
        // 实现异步清理逻辑
        await _connection.DisposeAsync();

        // 同时实现同步清理
        _buffer.Dispose();
    }
}
```

使用 `IAsyncDisposable` 类与使用 `IDisposable` 类类似，只需在 `using` 语句中添加 `await`：

```csharp
await using (var repository = new CustomerRepository(_connectionString))
{
    // 使用 repository
} // 自动调用 repository.DisposeAsync()
```

或使用简化语法：

```csharp
await using var repository = new CustomerRepository(_connectionString);
// 使用 repository
// 作用域结束时自动调用 DisposeAsync()
```

## 总结

虽然 .NET 的垃圾回收器在管理内存方面表现出色，但它无法清理非托管资源，如底层文件句柄或数据库连接。`IDisposable` 接口帮助确保所有托管和非托管资源都能被确定性地清理。

在大多数情况下，你会使用第一种简单的基础实现。然而，如果需要手动清理非托管资源，则需要更多的代码来实现完整的 Dispose 模式。

通过正确实现 `IDisposable` 接口，你将减少潜在的内存泄漏，从而构建出更稳健可靠的应用程序。记住以下关键要点：

- 对于包装了 `IDisposable` 资源的类，使用基础 Dispose 模式
- 对于直接处理非托管资源的类，使用完整 Dispose 模式
- 确保 `Dispose()` 方法的幂等性
- 在继承场景中正确重写和调用基类方法
- 对于异步清理操作，考虑实现 `IAsyncDisposable`
- 使用 `SafeHandle` 简化非托管指针的管理

掌握 Dispose 模式是成为优秀 .NET 开发者的重要一步，它能帮助你编写更高质量、更可靠的代码。
