---
pubDatetime: 2024-04-30
tags: [".NET", "C#"]
source: https://code-maze.com/csharp-create-a-zip-file-in-memory/
author: Matjaz Prtenjak
title: 如何在 C# 中创建内存中的 Zip 文件
description: 探索创建内存中 Zip 文件的选项，并使用 REST 协议传输它们，以写入数据库。
---

> ## 摘要
>
> 探索创建内存中 Zip 文件的选项，并使用 REST 协议传输它们，以写入数据库。
>
> 原文链接：[How to Create a Zip File in Memory In C#](https://code-maze.com/csharp-create-a-zip-file-in-memory/)

---

在本文中，我们将研究如何在 C# 中创建内存中的 Zip 文件。

之前，我们讨论了如何在 .NET 中创建和读取 Zip 文件，在我们的[在 C#/.NET 中处理 Zip 文件](https://code-maze.com/csharp-zip-files/) 文章中，因此我们建议您查看该文章以熟悉如何处理 Zip 文件。

要下载本文的源代码，您可以访问我们的 [GitHub 仓库](https://github.com/CodeMazeBlog/CodeMazeGuides/tree/main/files-csharp/InMemoryZipFilesInNet)。

## 内存中的 Zip 文件

首先要问的问题是，**“我们为什么需要创建一个内存中的 Zip 文件？”**

为了使 Zip 文件有用，我们通常需要将其存储在某个地方。然而，不总是必需将其存储在文件系统上。我们可以选择**将其存储在数据库中或通过 REST API 等方法直接传输给客户。**

如果我们打算通过 REST 调用发送它，那么在文件系统上临时存储它是不必要的。

本文将专注于这个场景。

### 创建内存中的 Zip 文件

但在一切之前，让我们指出“大象”并展示**我们如何在内存中创建 Zip 文件。**

不再拖延，我们将展示在内存中创建 Zip 文件的方法并讨论其内部工作原理。

借助之前提到的文章，其中我们使用了 `Stream`，我们可以推导出使用 `MemoryStream` 在内存中创建数据，从而在内存中创建 Zip 文件：

```csharp
public static MemoryStream Create(string content)
{
    var stream = new MemoryStream();
    using (var archive = new ZipArchive(stream, ZipArchiveMode.Create, true))
    {
        var fileName = $"FileInsideZip.txt";
        using var inZipFile = archive.CreateEntry(fileName).Open();
        using var fileStreamWriter = new StreamWriter(inZipFile);
        fileStreamWriter.Write(content);
    }
    _ = stream.Seek(0, SeekOrigin.Begin);
    return stream;
}
```

要创建一个 Zip 文件，我们需要一个 `Stream` 来存储数据。由于我们希望将数据存储在内存中，所以我们将使用 `MemoryStream`。

正如我们在前一篇文章中看到的，我们使用 `ZipArchive` 类来创建 Zip 文件，因此我们将一个类型为 `ZipArchive` 的变量挂钩到内存流上。之后，我们只需要向 Zip 归档添加数据。

但是，在返回给调用者之前，我们将进一步讨论一个小细节，因为我们需要将流指针移动到流的开头。

**就是这样。我们有了一个内存中的 Zip 文件并且可以将其返回给调用者。**

### 为内存中的 Zip 文件准备项目

为了设置我们的 REST API，我们将使用 `webapi` 模板与最少的 API 实现：

```bash
dotnet new webapi -o InMemoryZipFilesInNet
```

为了增强我们示例的真实感，我们将模拟开发一个应用程序，该应用程序生成一个包含程序内各个服务数据的 Zip 文件。

**我们的应用程序将利用多个服务。** 每当调用者调用我们的端点时，我们将创建一个包含每项服务数据的 Zip 文件。

所有服务都将遵循相同的 `IService` 接口，使我们能够检索数据：

```csharp
public interface IService
{
    public string Name { get; }
    public string GetData();
}
```

我们将使用 `Name` 属性作为 Zip 文件内的文件名，使用 `GetData()` 方法作为文件的内容。

让我们还创建三个服务：`FileService`、`DbService` 和 `TimeService` 并将**它们纳入我们的依赖注入容器**：

```csharp
builder.Services.AddScoped<IService, FileService>();
builder.Services.AddScoped<IService, DbService>();
builder.Services.AddScoped<IService, TimeService>();
```

我们将从文件系统返回 Zip 文件作为 `Stream` 和 `byte[]`。

为此，让我们根据它们的预期功能命名方法：

```csharp
public interface IGetFile
{
    string ContentType { get; }
    Stream GenerateFileOnFlyReturnStream();
    byte[] GenerateFileOnFlyReturnBytes();
}
```

使用 `ContentType` 属性，我们将设置内容类型，在我们的示例中将为 `"application/zip."`

到目前为止，我们已经很好地准备了一切，可以编写创建 Zip 文件的代码了，这是**我们程序的核心。**

要开始一切，我们必须创建一个实现 `IGetFile` 接口的类。然后，我们可以通过依赖注入注入这个类的实例，并且一切都将工作。

### GetZipFile 类

现在是创建实现 `IGetFile` 接口的 `GetZipFile` 类的时候了：

```csharp
public class GetZipFile(IEnumerable<IService> allServices) : IGetFile
{
    private readonly IService[] _allServices = allServices.ToArray();
    public string ContentType => "application/zip";
    public Stream GenerateFileOnFlyReturnStream() =>
        GetServicesAsZipStream(_allServices);
    public byte[] GenerateFileOnFlyReturnBytes() =>
        GetServicesAsZipBytes(_allServices);
}
```

在这里，我们定义了 `GetZipFile` 类，它有一个接受 `IEnumerable<IService>` 的[主构造器](https://code-maze.com/csharp-primary-constructors-for-classes-and-structs/)，并将接受我们的 `FileService`、`DbService` 和 `TimeService` 类。

我们所有示例的内容类型都是相同的，因此只设置一次。

### 生成 Zip 流的助手方法

让我们为我们的程序创建一个名为 `GenerateArchive()` 的助手方法。它将创建一个 Zip `Stream`。**现在 `Stream` 的类型并不重要；这就是它的美妙之处:**

```csharp
private static void GenerateArchive(Stream stream, IService[] services)
{
    using var archive = new ZipArchive(stream, ZipArchiveMode.Create, true);
    foreach (IService service in services)
    {
        var name = $"{service.Name}.txt";
        var content = service.GetData();
        using var inZipFile = archive.CreateEntry(name).Open();
        using var fileStreamWriter = new StreamWriter(inZipFile);
        fileStreamWriter.Write(content);
    }
}
```

我们使用 `Stream` 创建一个 `ZipArchive` 对象，这个 `Stream` 我们稍后将作为参数传递给我们的方法。

之后，我们调用每个服务并从服务处获取文件名和文件内容。我们创建一个 Zip 条目并将其写入 Zip 文件。就是这些了。现在我们在磁盘上有了一个 Zip 文件。

### 即时生成 Zip 文件

我们已经知道如何通过 `Stream` 创建 Zip 文件了。提供一个 `MemoryStream` 对象给我们的 `GenerateArchive()` 方法将导致 Zip 文件存储在内存中：

```csharp
private static MemoryStream GetServicesAsZipStream(IService[] services)
{
    var stream = new MemoryStream();
    GenerateArchive(stream, services);
    _ = stream.Seek(0, SeekOrigin.Begin);
    return stream;
}
```

在这里，我们有了一个更简单的方法。我们不必提供 `FileStream`；我们不必在磁盘上找到一个位置。**我们只是创建并返回一个 `MemoryStream`。**

**这是我们一直在寻找的方法**，它具备了一切。我们在内存中创建我们的归档，使用我们服务的动态数据作为一个现实的示例。

只有一个重要的注意事项。当我们写入 `MemoryStream` 时，我们从开始移动到结束。对于我们写入的每个字节，我们都在向前移动指针。因此，**如果我们想将其返回给调用者，我们必须首先用 `Seek()` 方法调用遍历到开始位置**；否则，我们的调用者将什么也得不到。

### 返回字节数组

在这里我们可以停止，因为我们已经看到了如何在内存中创建 Zip 文件以及为什么这样做。但正如提到的，通过网络发送文件并不是内存中 Zip 文件的唯一用途。

**有时，我们可能想要在内存中创建一个 Zip 文件并将其写入数据库。** 通常，我们无法将 `Stream` 写入数据库，但我们可以轻松地在数据库中存储原始字节。

这最后一个例子将作为内存中 Zip 文件的其他用例的入口：

```csharp
private static byte[] GetServicesAsZipBytes(IService[] services)
{
    var stream = new MemoryStream();
    GenerateArchive(stream, services);
    return stream.ToArray();
}
```

这几乎是最简单的方法，因为我们花时间并准备了一切非常好。

它与上一个非常相似，因为我们再次创建了一个 `MemoryStream`。这一次，虽然，我们不是返回一个 `MemoryStream`，**而是将流转换为 `byte[]`。**

这次，没有必要遍历到开始，因为我们正在调用 `ToArray()` 方法。

## 通过 REST API 返回内存中的 Zip 文件

现在我们已经完成了准备工作，我们的下一步是确定**如何从我们的 REST 端点发送文件给调用者。**

在 .NET 的最小化 API 中，我们使用 `Microsoft.AspNetCore.Http.Results` 类来从我们的端点传输数据：

```csharp
app.MapGet("/test-file", () =>
    Results.File(MemoryZipFile.Create("Test"), "application/zip", "TestFile.zip"));
app.MapGet("/create-in-memory-zip-file", (IGetFile zipFile) =>
    Results.File(zipFile.GenerateFileOnFlyReturnStream(), zipFile.ContentType, "GenerateOnFly.zip"));
app.MapGet("/create-in-memory-zip-file-as-byte-array", (IGetFile zipFile) =>
    Results.File(zipFile.GenerateFileOnFlyReturnBytes(), zipFile.ContentType, "GenerateOnFlyAsByteArray.zip"));
```

如您所见，我们使用 `Results` 类中的 `File` 方法将创建的 zip 文件返回给客户端。

## 返回较大的文件

我们通常生成 Zip 文件是因为我们有大量数据需要传输。在这种情况下，我们应该使用非阻塞的[异步代码](https://code-maze.com/asynchronous-programming-with-async-and-await-in-asp-net-core/)。

目标是使用非阻塞代码准备数据，并尽可能少地使用内存来传输文件。

我们不会深入讨论所有细节，因为这不是一篇关于使用 REST 协议传输文件或异步编程的文章，但让我们看一个例子：

```csharp
app.MapGet("/downloading-bigger-file", async (HttpResponse response, IGetFile zipFile) =>
{
    var zipStream = await zipFile.GenerateFileOnFlyReturnStreamAsync();
    zipStream.Position = 0;
    response.ContentType = zipFile.ContentType;
    ContentDispositionHeaderValue contentDisposition = new ContentDispositionHeaderValue("attachment")
    {
        FileName = "BigFile.zip"
    };
    response.Headers[HeaderNames.ContentDisposition] = contentDisposition.ToString();
    await zipStream.CopyToAsync(response.Body);
});
```

首先，我们使用非阻塞代码准备 Zip 文件。虽然我们可以并行生成数据，但创建 Zip 文件必须是顺序的，**因为 `ZipArchive` 不是线程安全的！**

在我们准备好数据流之后，我们可以直接将 Zip 流复制到 REST 调用的输出流中，因为这将使用最少量的内存。

通过将 `Content-Disposition` 标头设置为“附件”，**客户端知道应该提示用户保存内容为文件而不是直接在浏览器中显示它。**

**这样的方法可能会显着减少高容量服务器上服务较大文件时的内存占用**，例如。

## 内存中 Zip 文件的额外考虑

软件开发的现实往往呈现**需要仔细考虑的挑战。**

生成内存中 Zip 文件的一个主要问题是内存使用。虽然现代系统通常具有大量**可用内存**，但非常大的文件仍然会对资源造成压力。

可能需要在磁盘上创建文件。此外，启用范围处理允许调用者重试下载或下载文件的特定部分，这对于高效处理大文件至关重要。

我们在示例中忽视的另一个重要事项是错误处理和日志记录。因为我们忽略了这部分编程，示例都很小并且易于遵循。

但实际上，我们必须考虑**重试失败的 I/O 操作、日志记录和错误处理。**

## 结论

使用 `ZipArchive` 类和 `MemoryStream`，在内存中生成 Zip 文件相对简单。

然而，在文件对于内存来说太大的情况下，可能需要在磁盘上创建它们。在这种情况下，管理磁盘使用是至关重要的。文件可以在传输后删除，脚本或批处理可以用来确保有效的清理，同时避免与正在进行的操作发生冲突。
