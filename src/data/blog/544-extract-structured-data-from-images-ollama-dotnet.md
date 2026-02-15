---
pubDatetime: 2026-02-15
title: "在 .NET 中使用 Ollama 从图片提取结构化数据"
description: "通过 Ollama 在本地运行视觉模型，配合 Microsoft.Extensions.AI 和 OllamaSharp，实现从收据图片中提取商品名称、数量和价格等结构化数据，并反序列化为强类型 C# 对象。"
tags: [".NET", "AI", "Ollama", "LLM"]
slug: "extract-structured-data-from-images-ollama-dotnet"
source: "https://www.milanjovanovic.tech/blog/how-to-extract-structured-data-from-images-using-ollama-in-dotnet"
---

视觉模型（LLM）能否从杂货店收据中解析出结构化数据？不只是描述图片内容，还要真正提取出商品明细、数量和价格，生成干净的 JSON，并且全部在本地通过 [Ollama](https://ollama.com/) 和 llama3.2-vision 模型完成。

本文将介绍以下内容：

- 在 .NET 中配置 Ollama 视觉模型
- 向模型发送图片并获取结构化输出
- 通过迭代系统提示词提高准确性
- 将 LLM 响应反序列化为强类型 C# 对象
- 测试结果的一致性

## 配置 Ollama 与 Microsoft.Extensions.AI

[Ollama](https://ollama.com/) 可以在本地运行大语言模型。拉取模型的方式和拉取 Docker 镜像一样简单：

```bash
ollama pull llama3.2-vision:latest

# 在本地运行模型
ollama run llama3.2-vision:latest
```

在 .NET 端，[Microsoft.Extensions.AI](https://learn.microsoft.com/en-us/dotnet/ai/ai-extensions) 提供了统一的 `IChatClient` 接口，可以与任何 LLM 提供商对接。配合 [OllamaSharp](https://github.com/awaescher/OllamaSharp)，配置非常简洁：

```csharp
var builder = Host.CreateApplicationBuilder();

builder.Services.AddChatClient(
    new OllamaApiClient(
        new Uri("http://localhost:11434"),
        "llama3.2-vision:latest"));

var app = builder.Build();

var chatClient = app.Services.GetRequiredService<IChatClient>();
```

这样就得到了一个由本地视觉模型驱动的 `IChatClient`，不需要管理任何 API 密钥或云依赖。

`IChatClient` 的优势在于它与提供商无关。如果以后想切换到 OpenAI 或 Azure，应用代码无需改动。

## 向模型发送图片

最简单的尝试：发送一张收据图片并询问其中的内容。

```csharp
var message = new ChatMessage(
    ChatRole.User, "What's in this image?");

message.Contents.Add(
    new DataContent(
        File.ReadAllBytes("receipts/receipt_1.png"),
        "image/png"));

var response = await chatClient.GetResponseAsync([message]);

Console.WriteLine(response.Text);
```

读取图片字节，用 `DataContent` 包装并指定 MIME 类型，然后附加到 `ChatMessage` 中。

模型返回的原始文本响应：

```
This image appears to be a receipt or invoice in a foreign language, likely Russian
or another Slavic language. The document is in black and white and features a large
QR code at the bottom. The text is in a blocky, old-style font and includes several
columns of numbers and words...
```

模型正确识别出这是一张收据并列出了上面的商品。在零微调的情况下能做到这一点，令人印象深刻。但如果想要提取结构化数据，纯文本描述还不够用。

## 请求 JSON 输出

文本描述在程序中没什么用。所以改为请求结构化 JSON：

```csharp
var message = new ChatMessage(ChatRole.User,
    @"""
    Extract all line items from this receipt.
    Respond in JSON format with this structure:
    {
        "items": [
            {
                "name": "item name",
                "quantity": 1.500,
                "unitPrice": 0.00,
                "totalPrice": 0.00
            }
        ],
        "subtotal": 0.00
    }
    """);
message.Contents.Add(
    new DataContent(
        File.ReadAllBytes("receipts/receipt_1.png"),
        "image/png"));

var response = await chatClient.GetResponseAsync([message]);

Console.WriteLine(response.Text);
```

模型返回的结果：

```json
{
    "items": [
        {
            "name": "limun /kg (A)",
            "quantity": 280.00,
            "unitPrice": 1.105,
            "totalPrice": 309.40
        },
        {
            "name": "salata /kom (A)",
            "quantity": 70.00,
            "unitPrice": 3.00,
            "totalPrice": 210.00
        },
        {
            "name": "susam 100g trpeza /kom (A)",
            "quantity": 90.00,
            "unitPrice": 1.00,
            "totalPrice": 90.00
        }
    ],
    "subtotal": 609.40
}
```

第一次尝试效果就出奇地好。模型返回了包含商品名称、数量和价格的 JSON。部分数量略有偏差，但整体结构是正确的。

## 迭代系统提示词

当模型读错数字或对数值四舍五入时，修复方法不是改 C# 代码，而是调整系统提示词。

系统提示词是给模型设置对话上下文的初始指令。注意下面代码中的 `ChatRole.System`。经过几轮迭代后，系统提示词看起来像一份规格说明文档：

```csharp
var systemMessage = new ChatMessage(ChatRole.System,
    @"""
    You are a receipt parsing assistant. Extract all line items from the receipt image.
    For each line item, extract the name, quantity, unit price, and total price.
    Quantity can be a decimal number (e.g. weight in kg like 0.550 or 1.105).
    Extract the subtotal which is the final total amount shown on the receipt.
    IMPORTANT: Read every digit exactly as printed on the receipt.
    Pay very close attention to each decimal digit - do NOT round or approximate.
    For example, if the receipt shows 1.105, report exactly 1.105, not 1.1 or 1.2.
    Verify that quantity * unitPrice = totalPrice for each line item.
    Don't invent items that aren't on the receipt.

    DECIMAL FORMAT: Receipts may use different number formats depending on locale.
    - Some use period as decimal separator: 7,499.00
    - Some use comma as decimal separator: 7.499,00
    First, detect which format the receipt uses by examining the numbers on it.
    Then, always output numbers in the JSON using a period as the decimal separator.
    For example: 7499.00, not 7.499,00 or 7,499.00.
    """);
```

提示词中的每条指令都对应着模型曾经犯过的错误：

- "完全按照收据上印刷的数字读取"：因为模型会把 `1.105` 四舍五入成 `1.1`
- "不要凭空编造商品"：模型曾经产生幻觉，返回了收据上不存在的商品
- 整个小数格式部分：因为测试用的收据使用逗号作为小数分隔符（欧洲格式），模型经常把千位分隔符和小数点搞混

每次提示词迭代就像一次调试过程，只不过用的是文字。

## 强类型响应

这里 [Microsoft.Extensions.AI](https://www.milanjovanovic.tech/blog/working-with-llms-in-dotnet-using-microsoft-extensions-ai) 展现了它的价值。

不需要手动解析原始 JSON 字符串，直接调用 `GetResponseAsync<T>` 就能拿到强类型对象：

```csharp
var response = await chatClient.GetResponseAsync<Receipt>(
    [systemMessage, message],
    new ChatOptions { Temperature = 0 });

if (response.Result is { } receipt)
{
    Console.WriteLine(
        $"\nExtracted {receipt.Items.Count} line items:");

    foreach (var item in receipt.Items)
    {
        Console.WriteLine(
            $"  {item.Name} - " +
            $"Qty: {item.Quantity} x {item.UnitPrice:C}" +
            $" = {item.TotalPrice:C}");
    }

    Console.WriteLine($"  Subtotal: {receipt.Subtotal:C}");
}
```

`Receipt` 和 `LineItem` 类是普通的 C# 对象：

```csharp
public class Receipt
{
    public List<LineItem> Items { get; set; } = [];
    public decimal Subtotal { get; set; }
}

public class LineItem
{
    public string Name { get; set; } = string.Empty;
    public decimal Quantity { get; set; }
    public decimal UnitPrice { get; set; }
    public decimal TotalPrice { get; set; }
}
```

库会自动生成 JSON Schema，发送给模型，然后反序列化响应。直接返回一个 `Receipt` 对象。

这里还将 `Temperature` 设为 0，使输出尽可能确定。对于数据提取场景，准确性是首要目标。

## 测试一致性

需要验证的一个问题：对同一张收据用同样的提示词发送五次，能否得到相同的结果？

```csharp
const int runs = 5;
Console.WriteLine($"\n--- Consistency test ({runs} runs) ---");

var results = new List<Receipt>();
for (int i = 0; i < runs; i++)
{
    Console.WriteLine($"\nRun {i + 1}...");
    var testResponse = await chatClient.GetResponseAsync<Receipt>(
        [systemMessage, message],
        new ChatOptions { Temperature = 0 });

    if (testResponse.Result is { } r)
    {
        results.Add(r);
        Console.WriteLine(
            $"  Items: {r.Items.Count}, " +
            $"Subtotal: {r.Subtotal:C}");

        foreach (var item in r.Items)
        {
            Console.WriteLine(
                $"    {item.Name} - " +
                $"Qty: {item.Quantity} x {item.UnitPrice:C}" +
                $" = {item.TotalPrice:C}");
        }
    }
}
```

然后将每次运行的结果与基准进行比较：

```csharp
var baseline = results[0];
for (int i = 1; i < results.Count; i++)
{
    bool match = baseline.Subtotal == results[i].Subtotal
        && baseline.Items.Count == results[i].Items.Count
        && baseline.Items.Zip(results[i].Items).All(pair =>
            pair.First.Name == pair.Second.Name
            && pair.First.Quantity == pair.Second.Quantity
            && pair.First.UnitPrice == pair.Second.UnitPrice
            && pair.First.TotalPrice == pair.Second.TotalPrice);

    Console.WriteLine(
        $"  Run 1 vs Run {i + 1}: " +
        $"{(match ? "MATCH" : "DIFFERENT")}");
}
```

Temperature 设为 0 有帮助，但视觉模型并非完全确定性的。大多数运行结果一致，个别存在差异，通常是读错了某个数字，或者商品名称略有不同。

使用 LLM 时需要记住这一点：它们是概率系统。即使 Temperature 为 0，相同的输入也可能产生稍微不同的输出。如果需要保证准确性，需要在此基础上增加验证层。

## 后续扩展方向

收据扫描器只是起点。拿到图片的结构化数据之后，可以在此基础上构建更多功能：

- 个人财务追踪器：扫描收据、存储数据，让模型自动分类购买项目（杂货、家居、电子产品等）
- 周/月消费汇总：本月杂货花了多少？和上月相比如何？
- 多收据聚合：扫描出差的一堆收据，生成费用报告
- 价格追踪：检测常去商店的商品是否涨价
- 语义搜索：通过嵌入结构化数据，按商品或价格区间搜索历史收据

视觉模型完成了最难的部分：将非结构化图片转化为结构化数据。之后的工作就是常规的应用开发了。

## 总结

在本地通过 Ollama 运行视觉模型的配置很简单。`Microsoft.Extensions.AI` 和 `OllamaSharp` 让 .NET 集成变得简洁。你能得到一个与提供商无关的 `IChatClient`，并且支持强类型响应。

系统提示词是整个方案中工作量最大的部分。提示词里的每一行都是模型犯错后添加的纠正指令。

如果想自己试试：

1. 安装 [Ollama](https://ollama.com/)
2. 拉取视觉模型：`ollama pull llama3.2-vision:latest`
3. 创建 .NET 控制台应用，添加 `OllamaSharp` 和 `Microsoft.Extensions.AI` NuGet 包
4. 对准一张收据，看看模型返回什么
