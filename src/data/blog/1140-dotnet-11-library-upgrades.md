---
pubDatetime: 2026-11-19T09:30:04+08:00
title: "05｜.NET 11 基础库：哪些自写工具可以退役？"
description: "用成绩导出验证 .NET 11 内置的 JSON Lines、内存流、Zstandard 和进程输出捕获。提供可以运行的来回压缩和退出码检查，说明带换行的记录、失败路径及数值舍入如何做回归。"
tags: ["DotNet", "System.Text.Json", "Compression"]
slug: "dotnet-11-library-upgrades"
ogImage: "../../assets/1140/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/libraries"
---

课程对账完成后，服务逐条导出成绩、压缩文件，再让另一个进程处理归档。.NET 11 已经覆盖这几步所需的通用操作：JSON Lines 逐条写入，`ReadOnlyMemoryStream` 给内存数据提供只读流，`ZstandardStream` 负责压缩，`Process.RunAndCaptureTextAsync` 收集标准输出、错误和退出码。可以先替换最薄的自写封装，保留应用自己的格式与错误契约。

下面的程序验证两条记录能重新解压且内容逐字相同，检查子进程失败的退出码和错误流，也固定一条小数中点的舍入规则。示例使用 .NET 11.0.100，基础库来自框架，无需额外包。

## 逐行写入并校验解压内容

把代码保存为 `Export.cs`，在该目录执行 `dotnet run --file Export.cs`。示例的子进程也从当前目录启动该文件，传入 `--fail` 后立即退出。

```csharp
using System.Diagnostics;
using System.IO.Compression;
using System.Text.Json;
using System.Text.Json.Serialization;

if (args is ["--fail"])
{
    Console.Error.WriteLine("invalid fixture");
    return 7;
}

using var archive = new MemoryStream();
await using (var compress = new ZstandardStream(archive, CompressionMode.Compress, leaveOpen: true))
    await JsonSerializer.SerializeAsyncEnumerable(
        compress, Rows(), ExportJson.Default.ExportRow, topLevelValues: true);

using var bytes = new ReadOnlyMemoryStream(archive.ToArray());
using var decompress = new ZstandardStream(bytes, CompressionMode.Decompress);
using var reader = new StreamReader(decompress);
string text = await reader.ReadToEndAsync();
if (text != "{\"id\":\"S01\",\"score\":90}\n{\"id\":\"S02\",\"score\":88}\n")
    throw new InvalidDataException(text);
Console.Write(text);

var child = await Process.RunAndCaptureTextAsync(
    "dotnet", ["run", "--file", "Export.cs", "--", "--fail"]);
if (child.ExitStatus.ExitCode != 7 || !child.StandardError.Contains("invalid fixture"))
    throw new InvalidOperationException(child.StandardError);
Console.WriteLine($"exit={child.ExitStatus.ExitCode}");

if (Math.Round(2.5m) != 2m || Math.Round(2.5m, MidpointRounding.AwayFromZero) != 3m)
    throw new InvalidOperationException("Unexpected rounding convention.");
return 0;

static async IAsyncEnumerable<ExportRow> Rows()
{
    yield return new("S01", 90);
    await Task.Yield();
    yield return new("S02", 88);
}

public sealed record ExportRow(string Id, int Score);
[JsonSourceGenerationOptions(JsonSerializerDefaults.Web)]
[JsonSerializable(typeof(ExportRow))]
internal partial class ExportJson : JsonSerializerContext;
```

本机运行得到两行 JSON，后面是 `exit=7`。测试把末尾的 LF 也纳入对照。JSON Lines 适用于逐条解析或写入的消费者，换成 JSON 数组会改变文件协议。设置 `topLevelValues: true` 后每条值紧跟 LF，序列化器忽略缩进配置。字符串里的换行会被 JSON 转义，读方仍应逐行解析 JSON，再把字段里的转义还原。

用于验证的 `archive.ToArray()` 会复制数据，适合这个只有两行的小例子。批量导出可以直接写入文件或远端流。若调用方已经持有 `ReadOnlyMemory<byte>`，可直接用只读适配器交给接受 `Stream` 的组件。内存流还有 `WritableMemoryStream`、`ReadOnlySequenceStream` 与 `StringStream`，替换时先检查长度是否固定、是否支持定位及底层缓冲区是否继续被写入。

## 归档失败与子进程失败要分别处理

压缩流须在读取归档前完成释放，让缓冲数据和帧尾写完。正式作业用临时文件生成归档，回读验证通过后再交付文件。给消费端做截断样本、空输入和取消测试。解压解出了几条记录时仍可能遇到后续错误，批量导入要有自己的完整性检查和重试粒度。

外部进程用参数列表区分可执行文件和输入，保留退出码供调用方决定重试。报告 stderr 时按应用约定处理敏感信息。会产生大量输出的子进程更适合逐行消费，避免运行完才将全部内容积存在内存。取消、进程启动失败、非零退出和业务文件校验失败是四个可分别测试的分支。

财务或成绩计算要写清楚舍入规则。样本用 2.5 验证中点取偶数与远离零两种口径。实际升级按已有业务规则再加负数、精度边界、解析失败和旧存档往返样例。若同时更换了压缩格式，旧客户端继续使用旧扩展名及媒体类型，等所有消费者读得懂新格式再切换默认。

## 参考

- [.NET 11 基础库变化](https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/libraries)
- [.NET 11 破坏性变更](https://learn.microsoft.com/en-us/dotnet/core/compatibility/11)
- [.NET 11 正式发布](https://devblogs.microsoft.com/dotnet/announcing-dotnet-11/)
