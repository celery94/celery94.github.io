---
pubDatetime: 2026-10-26T09:50:00+08:00
title: "CBOR 入门：.NET 里什么时候用它换掉 JSON"
description: "CBOR 用二进制编码 JSON 那套类型，.NET 只给 CborWriter 和 CborReader，没有对象映射。同一份数据实测 80 字节对 107 字节，文中拆开首字节、跑通读写代码，再说明什么条件下值得换掉 JSON。"
tags: [".NET", "CBOR", "序列化", "C#"]
slug: "cbor-in-dotnet"
ogImage: "../../assets/1117/01-cover.jpg"
source: "https://andrewlock.net/an-introduction-to-compact-binary-object-notation-in-dotnet/"
---

同一只狗的数据，用 `System.Text.Json` 序列化后去掉全部空白是 107 字节，用 CBOR 编一遍是 80 字节，`name`、`breed`、`age`、`toys`、`owner` 五个字段一个不少。CBOR（Concise Binary Object Representation）是 IETF 的二进制序列化标准（RFC 8949），和 JSON 一样自描述，但 .NET 的 `System.Formats.Cbor` 只提供 `CborWriter` 和 `CborReader` 两个底层类型，没有 `JsonSerializer` 那样的对象映射，每个字段都得手写读写。问题于是变成：为了省这点字节，值不值得写这些代码。

值得用的场景比想象中窄。两端都由你控制、数据里二进制和小值占比高时，CBOR 划算；给前端或第三方提供 API、需要抓包就能看懂报文时，继续用 JSON 更省事。Andrew Lock 在 10 月 20 日的[原文](https://andrewlock.net/an-introduction-to-compact-binary-object-notation-in-dotnet/)里介绍了这个格式和它的 .NET 用法。下面的代码都在 .NET 10 上跑过；字节结构、三条实测报错和包版本核对是原文没展开的部分。

## 省下来的 27 字节都是格式开销

把 80 字节拆开看，其中 64 字节是键名和字符串值本身的字符，12 字节是每个字符串前面的长度头，3 字节是 map 和数组的长度标记，剩下 1 字节是整数 `8`。JSON 那份的 107 字节里，同样这 64 个字符之外，多出来的是 24 个引号、6 个冒号、6 个逗号、6 个括号和 1 个数字字符。

27 字节的差距全部来自格式开销，数据本身一点没被压缩。换成中文场景也一样：字符「鹅」在 CBOR 里是 `63 E9 B9 85`，一个长度头加三个 UTF-8 字节，在 JSON 里是带引号的五个字节。文本占比高的数据，CBOR 顶多省掉引号和分隔符。

JSON 不擅长表示的数据才会拉开差距。原文举了两个：

- 布尔值 `true` 在 JSON 里占 4 个字节，`false` 占 5 个字节，用来表达 1 bit。CBOR 分别是 `F5` 和 `F4`，各 1 字节。
- JSON 没有二进制类型，二进制数据要编码成 base64，体积涨约 33%，解码端还要多一次转换。CBOR 有字节串类型，四个字节的 `DE AD BE EF` 编码成 `44 DE AD BE EF`，只多一个长度头。

布尔值多、二进制数据多、小整数多，CBOR 的优势才明显。反过来，如果 payload 是一堆中文文本和长键名，换格式只是在跟引号较劲。

## 首字节同时给出类型和长度

每一段 CBOR 数据都是一个「头字节 + 可选后续字节」。头字节高 3 位是 major type，低 5 位给长度或数值；低 5 位是 24、25、26、27 时，后面分别跟 1、2、4、8 字节表示更大的长度或数值，是 31 则表示不定长。八个 major type 覆盖了 JSON 的全部类型，外加字节串、tag 和浮点：

| 高 3 位 | 类型        | 本文例子里的字节           |
| ------- | ----------- | -------------------------- |
| 0       | 无符号整数  | `08` = 8，`19 03E8` = 1000 |
| 1       | 负整数      | `20` = -1                  |
| 2       | 字节串      | `44 DEADBEEF`              |
| 3       | 文本串      | `64 6E616D65` = "name"     |
| 4       | 数组        | `83` = 3 项                |
| 5       | map         | `A5` = 5 个键值对          |
| 6       | tag         | 本文未用                   |
| 7       | 简单值/浮点 | `F5` = true                |

拿开头的 `A5 64 6E616D65 65 476F6F7365 ...` 对照：`A5` 拆成二进制是 `101 00101`，高三位 `101` 是 5（map），低五位 `00101` 是 5 项；接着的 `64` 是 `011 00100`，文本串、长度 4，后面四个字节正是 `name`。解码器读一个字节就知道接下来是整数还是字符串、要分配多大缓冲区、能跳过多少字节。JSON 做不到这一点，它得一路扫到引号或括号才知道字段在哪结束。

不定长是另一个 JSON 没有的能力。长度事先不知道时可以写成 `BF ... FF`，`BF` 开始、`FF` 结束，适合流式写入；代价是读的时候不能预先知道条目数。

## 装包之后先用三十行代码编一遍

前置条件很简单：.NET SDK 8 或更新，本文在 SDK 10.0.402 上验证。CBOR 不在共享框架里，新建一个 net10.0 控制台项目、不加包直接 `using System.Formats.Cbor;`，编译会报 `CS0234: The type or namespace name 'Cbor' does not exist in the namespace 'System.Formats'`。

```bash
dotnet new console -o cbor-demo
cd cbor-demo
dotnet add package System.Formats.Cbor
```

原文把官方支持算作 .NET 10 的新增能力，NuGet 的版本列表对不上：`5.0.0` 就已经是正式版，这个包一直独立分发，版本号跟着运行时走，写作时的正式版是 10.0.14（2026 年 10 月 25 日）。它同时面向 net8.0、netstandard2.0 和 .NET Framework 4.6.2，老项目也能用。

把下面这段放进 `Program.cs`，它写的是开头那只狗：

```csharp
using System.Formats.Cbor;

var writer = new CborWriter();

// map 的条目数必须事先说清楚
writer.WriteStartMap(5);

writer.WriteTextString("name");
writer.WriteTextString("Goose");

writer.WriteTextString("breed");
writer.WriteTextString("Labrador");

writer.WriteTextString("age");
writer.WriteUInt32(8);

writer.WriteTextString("toys");
writer.WriteStartArray(3);
writer.WriteTextString("ducky");
writer.WriteTextString("flamingo");
writer.WriteTextString("ice-cream");
writer.WriteEndArray();

writer.WriteTextString("owner");
writer.WriteStartMap(1);
writer.WriteTextString("name");
writer.WriteTextString("Sock");
writer.WriteEndMap();

writer.WriteEndMap();

byte[] encoded = writer.Encode();
Console.WriteLine(encoded.Length);                     // 80
Console.WriteLine(Convert.ToHexString(encoded));
```

输出的十六进制和原文逐字节一致：

```text
A5646E616D6565476F6F7365656272656564684C61627261646F7263616765
0864746F797383656475636B7968666C616D696E676F696963652D63726561
6D656F776E6572A1646E616D6564536F636B
```

`WriteStartMap` 和 `WriteStartArray` 要求传条目数，写多了或写少了，`Encode()` 时都会抛异常，这一点比 JSON 严格。`Encode()` 返回 `byte[]`，也可以用 `Encode(Span<byte>)` 把结果写进自己准备的缓冲区。条目数确实不知道时传 `null`，写成不定长。

控制行为的参数在构造函数上：`new CborWriter(CborConformanceMode.Lax, convertIndefiniteLengthEncodings: true, allowMultipleRootLevelValues: true)`。原文展示的 `CborWriterOptions` 类在 10.0.14 里还不存在，我用 10.0.14 编译会报 `CS0246`，它要到 11.0.0 的预览/Rc 版本才有，属性叫 `MaxDepth`，另外多了 `InitialCapacity`。照着原文的代码在稳定版上跑，这一处会卡住。

## 读的时候长度要自己数

`CborReader` 的构造函数接收 `ReadOnlyMemory<byte>`，上一步 `Encode()` 返回的 `byte[]` 可以直接传，`stackalloc` 出来的 `Span<byte>` 则不行。读取的代码比写入长得多，每个字段该用哪个 `Read*` 方法、要不要给键分配字符串，都得自己决定：

```csharp
using System.Formats.Cbor;

byte[] encoded = Convert.FromHexString(
    "A5646E616D6565476F6F7365656272656564684C61627261646F72636167650864746F7973836564"
        + "75636B7968666C616D696E676F696963652D637265616D656F776E6572A1646E616D6564536F636B"
);

var reader = new CborReader(encoded);
int mapCount = reader.ReadStartMap() ?? throw new InvalidOperationException("不定长 map");

// 复用同一块 char 缓冲区，避免给每个键分配字符串
Span<char> keyBuffer = stackalloc char[16];
for (int i = 0; i < mapCount; i++)
{
    if (!reader.TryReadTextString(keyBuffer, out int length))
        throw new InvalidOperationException("key 太长");

    ReadOnlySpan<char> key = keyBuffer[..length];
    switch (key)
    {
        case "name":
            Console.WriteLine($"name: {reader.ReadTextString()}");
            break;
        case "breed":
            Console.WriteLine($"breed: {reader.ReadTextString()}");
            break;
        case "age":
            Console.WriteLine($"age: {reader.ReadInt32()}");
            break;
        case "toys":
            Console.WriteLine("toys:");
            int arrayCount = reader.ReadStartArray() ?? 0;
            for (int item = 0; item < arrayCount; item++)
                Console.WriteLine($"- {reader.ReadTextString()}");
            reader.ReadEndArray();
            break;
        default:
            // 不认识就整段跳过，跳过前可以把原始字节留下来
            string raw = Convert.ToHexString(reader.ReadEncodedValue().Span);
            Console.WriteLine($"unknown '{key}': {raw}");
            break;
    }
}
reader.ReadEndMap();
Console.WriteLine($"bytes remaining: {reader.BytesRemaining}");
```

输出：

```text
name: Goose
breed: Labrador
age: 8
toys:
- ducky
- flamingo
- ice-cream
unknown 'owner': A1646E616D6564536F636B
bytes remaining: 0
```

`owner` 没有对应的 case，落进 default 分支，`ReadEncodedValue()` 把整个嵌套 map 连同它的键值读出来并跳过去，没有解析也没有丢位置，`BytesRemaining` 收尾为 0。这段代码能在遇到未知字段后继续读下去，靠的就是这个能力。

如果要写真正通用的解码器，`PeekState()` 能先看下一个 token 是 `TextString` 还是 `StartMap`，再决定调哪个方法，不必预先假设数据结构。零反射、零中间对象是这套写法的回报，代价就是上面这些手写的分支。

## 三条实测会踩的坑

`WriteStartMap()` 没有无参重载。想写不定长 map 得显式传 `null`，写成 `WriteStartMap()` 会直接编译失败：`CS7036: There is no argument given that corresponds to the required parameter 'definiteLength'`。

`ReadStartMap()` 返回的是 `int?`，不定长 map 时是 `null`。用 `var` 接住再写 `for (int i = 0; i < mapCount; i++)` 能编译通过，但循环一次都不执行，值全被跳过，随后 `ReadEndMap()` 抛 `InvalidOperationException: Not at end of the indefinite-length data item.`。异常出现在收尾那一行，离漏读的地方已经隔了一层。

一个文档默认只能有一个根值。连续写两个顶层值会抛 `InvalidOperationException: Adding a CBOR data item to the current context exceeds its definite length.`，需要构造时打开 `allowMultipleRootLevelValues: true`。这个选项不是摆设，ASP.NET Core 的 DBSC 实现里就用到它。

## 同一份数据，canonical 模式给出不同字节

同样的写法和同样的数据，只把构造函数换成 `new CborWriter(CborConformanceMode.Canonical)`，输出就变了：

```text
A56361676508646E616D6565476F6F736564746F797383656475636B7968666C616D696E676F6969
63652D637265616D656272656564684C61627261646F72656F776E6572A1646E616D6564536F636B
```

`age` 跑到了最前面。canonical 模式要求 map 的键按编码后的字节排序，效果上是短键名在前、等长时按字节序，所以 `age`（4 字节）排在 `name`（5 字节）前面。

四个模式层层收紧：`Lax` 只要求格式良好；`Strict` 额外禁止重复键、要求简单值用最短编码、UTF-8 合法；`Canonical` 再加上整数最短编码、键排序、不定长转定长；`Ctap2Canonical` 更进一步，不允许 tag、也不改动浮点表示，用于 CTAP2/WebAuthn。

这个差异决定了一个容易翻车的边界：如果要对编出来的字节做签名、哈希或做缓存键，必须固定 conformance mode。同一份逻辑数据在 `Lax` 和 `Canonical` 下字节不同，签名自然对不上。反过来，读取时传 `Canonical` 只是校验输入是否合规，不会把已有数据修正成规范形式。

## CBOR 已经在你的依赖树里

.NET 生态里 CBOR 并不冷门，很多包直接依赖它：WebAuthn/passkey 的 `Fido2` 库、COSE 签名的 `System.Security.Cryptography.Cose`、`Yubico.YubiKey`，以及 AWS SDK 的 `AWSSDK.Extensions.CborProtocol`。用 passkey 登录的应用，底层早就在读写 CBOR 了。

原文里还有一个例子。ASP.NET Core 在 .NET 11 预览版里实现 DBSC（Device Bound Session Credentials）时，用 `CborWriter` 把 claim uid 和 session id 写成两个平级的文本值，打开 `allowMultipleRootLevelValues: true`，再用 Data Protection 加密、base64url 编码塞进 cookie：

```csharp
var writer = new CborWriter(allowMultipleRootLevelValues: true);
writer.WriteTextString(claimUid);
writer.WriteTextString(sessionId);
byte[] payload = writer.Encode(); // 69 "claim-uid" 6A "session-id"，21 字节
```

这段没有模拟 JSON 的 map 结构，只是把两个值首尾相接，得到相当于 `<claimUid><sessionId>` 的二进制。既然这份数据只给同一个应用读，省掉的键名和结构就都是净赚。这也是判断要不要用 CBOR 的一个参照：只要生产者与消费者是同一套代码，格式可以随意压到最紧。

## 换掉 JSON 的条件

先看两端。消费者只有你自己的代码时，CBOR 的不可读是可控成本；一旦有前端、第三方或运维需要直接看报文，二进制会把每次排查都变成一次解码，这个成本通常比省下的几十字节贵。

再看数据。二进制、布尔、枚举、小整数占比高，收益明显；中文文本和长键名占大头时，前面算过，80 字节里有 64 字节是原样照搬的字符，真正能让格式省下来的空间本来就只剩十几个字节。

如果追求的是极致体积和强 schema，protobuf 比 CBOR 更合适。CBOR 的卖点在于自描述：不需要两边共享 `.proto`，任何实现都能解析；代价是键名重复出现，体积比 protobuf 大。中间路线才是 CBOR 的位置。

具体怎么做决定：从生产环境抓一条真实 payload，把同一个对象各编一遍，比较字节数。数字差距不到两成，多半不值得换。决定换之后，把 conformance mode 钉死成 `Canonical` 或 `Ctap2Canonical` 并写进测试，否则某天换个构造函数，签名字节就悄悄变了。

## 参考

- [An introduction to Compact Binary Object Representation (CBOR) in .NET — Andrew Lock](https://andrewlock.net/an-introduction-to-compact-binary-object-notation-in-dotnet/)
- [RFC 8949: Concise Binary Object Representation (CBOR)](https://www.rfc-editor.org/rfc/rfc8949.html)
- [System.Formats.Cbor 命名空间文档](https://learn.microsoft.com/en-us/dotnet/api/system.formats.cbor)
- [System.Formats.Cbor · NuGet](https://www.nuget.org/packages/System.Formats.Cbor/)
- [CBOR 在线转换与解码](https://cbor.me/)
- [Exploring the .NET 11 preview 8: experimental support for Device Bound Session Credentials in ASP.NET Core](https://andrewlock.net/exploring-the-dotnet-11-preview-8-experimental-support-for-device-bound-session-credentials-in-aspnetcore/)
