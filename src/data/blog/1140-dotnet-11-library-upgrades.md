---
pubDatetime: 2026-11-19T09:30:04+08:00
title: "05｜.NET 11 基础库：哪些自写工具可以退役？"
description: "用成绩导出验证 .NET 11 的 JSON Lines、内存流、Zstandard 和进程输出捕获。再用同一段代码对照 .NET 10 和 11 的数值转换，检查金额录入、对账结果和精确值断言是否受影响。"
tags: ["DotNet", "System.Text.Json", "Compression"]
slug: "dotnet-11-library-upgrades"
ogImage: "../../assets/1140/01-cover.jpg"
source: "https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/libraries"
---

课程对账完成后，服务逐条导出成绩、压缩文件，再让另一个进程处理归档。.NET 11 已经覆盖这几步所需的通用操作：JSON Lines 逐条写入，`ReadOnlyMemoryStream` 给内存数据提供只读流，`ZstandardStream` 负责压缩，`Process.RunAndCaptureTextAsync` 收集标准输出、错误和退出码。可以先替换最薄的自写封装，保留应用自己的格式与错误契约。

下面的程序验证两条记录能重新解压且内容逐字相同，并检查子进程失败的退出码和错误流。升级还有一项独立的回归要做。相同的输入经过 `decimal`、`double` 或 `BigInteger` 转换后，.NET 10 和 11 可能得到不同的末位。两段示例均用 SDK 11.0.100 验证，无需额外包。

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

若同时更换了压缩格式，旧客户端继续使用旧扩展名及媒体类型，等所有消费者读得懂新格式再切换默认。

## 升级回归要测类型转换的末位

.NET 11 调整了 `decimal` 与二进制浮点类型之间的转换，以及 `BigInteger` 到二进制浮点类型的转换。对有限且在目标范围内的值，转换会按源值的精确表示，直接舍入到目标类型中最接近的可表示值。旧实现有时会丢弃有效位，或者先转成中间类型再舍入一次。

导出样本里的 `Math.Round(2.5m)` 检查的是业务选用的中点规则。即使那组断言全部通过，读取金额时经过的 `double → decimal` 仍可能改变。可以把下面的代码放进同一个多目标控制台项目的 `Program.cs`。将项目文件中的单数 `TargetFramework` 改为 `<TargetFrameworks>net10.0;net11.0</TargetFrameworks>`，再分别执行 `dotnet run -c Release -f net10.0` 和 `dotnet run -c Release -f net11.0`。运行机器需要安装两个版本的运行时，输出的第一行可以核对实际运行版本。

```csharp
using System;
using System.Globalization;
using System.Numerics;
using System.Runtime.InteropServices;

var culture = CultureInfo.InvariantCulture;
Console.WriteLine(RuntimeInformation.FrameworkDescription);

var price = double.Parse("1.23", culture);
Console.WriteLine($"double -> decimal: {((decimal)price).ToString("G29", culture)}");

var justAboveMidpoint = decimal.Parse("1.0000000596046447753906250001", culture);
Console.WriteLine($"decimal -> float: 0x{BitConverter.SingleToInt32Bits((float)justAboveMidpoint):X8}");

var count = (BigInteger.One << 54) - 1;
Console.WriteLine($"BigInteger -> double: {((double)count).ToString("G17", culture)}");
```

| 输入与转换                                      | .NET 10.0.14        | .NET 11.0.0                     |
| ----------------------------------------------- | ------------------- | ------------------------------- |
| 把解析出来的 `double` 转成 `decimal`            | `1.23`              | `1.229999999999999982236431606` |
| 略高于中点的 `decimal` 转成 `float`，查看位模式 | `0x3F800000`        | `0x3F800001`                    |
| 把整数 2⁵⁴ − 1 转成 `double`                    | `18014398509481982` | `18014398509481984`             |

第一行的新版结果更接近 `double` 里存下来的那个近似值。旧转换保留 15 位有效数字，结果看起来和原始文本相同。第二行选的十进制数略高于 1 与下一个可表示 `float` 的中点，新转换选中了较大的那个。第三行的整数恰在两个相邻 `double` 的中点，新转换按中点取偶规则选中 2⁵⁴。示例用运行时解析和运算避开了编译器预先算好常量的情况。即使继续以 `net10.0` 为目标，用 .NET 11 SDK 重新编译也可能改变编译期常量转换的结果。

对账回归可以先从 CSV、JSON 和数据库映射里找经过 `float` 或 `double` 的路径。金额字面量用 `1.23m`，十进制文本按约定的区域格式直接解析成 `decimal`。对实际接收二进制浮点的接口，两版都跑正负值、中点两侧和大整数边界。金额按业务规则比较到约定的小数位，文件协议或精确值快照则比较转换后的位模式或序列化文本。

如果业务需要 IEEE 754 十进制浮点语义，`Decimal32`、`Decimal64` 和 `Decimal128` 分别提供 7、16 和 34 位有效数字。它们支持无穷和 NaN，采用的数值表示也与现有 `decimal` 字段不同。已有金额字段应继续使用既定的 `decimal` 契约。机器学习里常用的 `BFloat16` 仍是二进制浮点，`Complex<T>` 则让复数运算能选择不同的浮点类型作为实部和虚部。

## 参考

- [.NET 11 基础库变化](https://learn.microsoft.com/en-us/dotnet/core/whats-new/dotnet-11/libraries)
- [Microsoft 兼容性说明：Decimal 和 BigInteger 浮点转换](https://learn.microsoft.com/en-us/dotnet/core/compatibility/core-libraries/11/decimal-biginteger-floating-point-conversions)
- [NDepend：What’s new in .NET 11 Numerics](https://blog.ndepend.com/net-11-numerics/)
- [.NET 11 破坏性变更](https://learn.microsoft.com/en-us/dotnet/core/compatibility/11)
- [.NET 11 正式发布](https://devblogs.microsoft.com/dotnet/announcing-dotnet-11/)
