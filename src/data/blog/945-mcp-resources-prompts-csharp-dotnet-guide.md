---
pubDatetime: 2026-07-16T13:54:28+08:00
title: "MCP Resources 与 Prompts：在 C# 中暴露数据和可复用模板"
description: "MCP 服务器不止 Tool 一种原语。本文用 C# 代码讲清楚 Resource（暴露可读数据）、Prompt（暴露可复用模板）和 Tool 三者的职责边界、实现方式和适用场景，附带可直接使用的代码示例。"
tags: ["MCP", "C#", ".NET", "MCP Resources", "MCP Prompts"]
slug: "mcp-resources-prompts-csharp-dotnet-guide"
ogImage: "../../assets/945/01-cover.png"
source: "https://www.devleader.ca/2026/07/15/mcp-resources-and-prompts-in-c-exposing-data-and-reusable-templates"
---

如果你已经在用 C# 写 MCP 服务器的 Tool，那你已经覆盖了"让模型调用服务器执行操作"这一块。但 MCP 协议里还有两个容易被跳过的原语：**Resource** 和 **Prompt**。它们的职责和 Tool 完全不同——Resource 给客户端提供**可读的上下文数据**，Prompt 给用户提供**可复用的对话模板**。Tool 是"帮模型做一件事"，Resource 是"让模型读一段内容"，Prompt 是"给用户一个可重复的工作流起点"。

这篇文章用 C# 官方 SDK（截至 2026 年 7 月最新稳定版 `1.4.0`）把 Resource 和 Prompt 的实现方式、设计决策和常见坑点过一遍。读完你会知道什么时候该用 Resource 而不是 Tool，什么时候该用 Prompt 而不是硬编码一段系统指令。

## Resource 的设计逻辑：被动数据源

[MCP 官方文档](https://modelcontextprotocol.io/docs/learn/server-concepts) 把 Resource 定义为"被动数据源"。这也是我在判断"这个东西该不该放 Resource"时反复用的那条线：**Resource 适合客户端列举、选择、读取后作为上下文传给模型的数据**。

典型场景：配置快照、文档页面、策略文件、构建元数据、数据库 schema 摘要、生成报告。客户端不是让服务器替用户"做一件事"，而是让服务器通过一个 URI 形态的合约**暴露数据**。

这对 .NET 开发者来说很自然。Resource URI 就像一个稳定的标识符，背后的 handler 照样可以用你现有的依赖注入、服务层、数据访问——只是 MCP 合约本身约定的是"读"，不是"写"或"执行"。

代价也很明显：Resource 是读导向的，不适合搜索、排序、触发工作流这类操作。如果你需要模型请求服务器干活，那还是 Tool。

## 直接 Resource：`[McpServerResource]` 固定 URI

官方 C# SDK 的属性路径是：类上标 `[McpServerResourceType]`，方法上标 `[McpServerResource]`。`McpServerResourceAttribute` 支持 `UriTemplate`、`Name`、`Title`、`MimeType`、`IconSource` 等属性。

直接 Resource 的 URI 是固定的，出现在客户端直接资源列表里，按 URI 读取即可。适合稳定文档或单例数据，标识符提前就知道。

```csharp
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;
using System.ComponentModel;
using System.Text.Json;

[McpServerResourceType]
public sealed class ApplicationResources
{
    [McpServerResource(
        UriTemplate = "config://app/settings",
        Name = "App Settings",
        MimeType = "application/json")]
    [Description("返回当前对 MCP 客户端可见的应用设置。")]
    public static TextResourceContents GetSettings()
    {
        var json = JsonSerializer.Serialize(new
        {
            Theme = "dark",
            Language = "zh-CN",
            FeatureFlags = new[] { "resources", "prompts" }
        });

        return new TextResourceContents
        {
            Uri = "config://app/settings",
            MimeType = "application/json",
            Text = json
        };
    }
}
```

返回 `TextResourceContents` 比返回裸字符串更好——URI 和 MIME 类型作为合约的一部分，能帮助客户端正确处理内容。

这里的设计问题不是"能不能暴露"，而是"客户端能不能把这段内容当成上下文理解"。一个设置文档、一个 schema 文件、一篇 Markdown 指南，合理。一个"刷新缓存"命令，不合理。

## 模板 Resource：URI 模板与参数化数据

模板 Resource 用 RFC 6570 URI 模板代替固定 URI。SDK 示例用 `UriTemplate = "docs://articles/{id}"` 这种写法。模板资源和直接资源在客户端是分开列举的，客户端可以发现有"一族"可读 URI 存在。

适合的场景：按 ID 读文章、按账号读客户档案、按构建 ID 读运行日志。URI 给客户端一个统一的方式来定位它要的数据，不用把读操作伪装成 Tool 调用。

```csharp
using ModelContextProtocol;
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;
using System.ComponentModel;

[McpServerResourceType]
public sealed class DocumentationResources
{
    [McpServerResource(UriTemplate = "docs://articles/{id}", Name = "Article")]
    [Description("按 ID 返回文章，内容为 Markdown。")]
    public static ResourceContents GetArticle(
        [Description("要读取的文章标识。")] string id)
    {
        var article = LoadArticle(id);

        if (article is null)
        {
            throw new McpException($"文章未找到: {id}");
        }

        return new TextResourceContents
        {
            Uri = $"docs://articles/{id}",
            MimeType = "text/markdown",
            Text = article
        };
    }

    private static string? LoadArticle(string id) =>
        id == "resources"
            ? "# MCP Resources

Resource 暴露可读上下文。"
            : null;
}
```

注意一个关键建模判断：这仍然是在**读内容**，不是把搜索端点伪装成 Resource。如果模型需要在语料库上做带排序、过滤、分页的搜索，Tool 的合约更诚实。如果应用或用户已经知道 URI 形态的标识，模板 Resource 就合适。

## 文本资源与二进制资源

MCP Resource 可以返回文本或二进制内容。SDK 里 `TextResourceContents` 对应文本资源，`BlobResourceContents` 对应二进制资源。

文本资源适用于 Markdown、JSON、纯文本、源码等你期望模型或客户端直接检查的内容。二进制资源适用于图片、PDF、压缩包、音频——关键是客户端需要字节流，MIME 类型有意义。SDK 里用 `BlobResourceContents.FromBytes(...)` 处理这条路径。

取舍在载荷大小和客户端支持。文本资源通常更容易摘要、分块、渲染。二进制资源依赖客户端知不知道拿这个 MIME 类型干什么。对大多数 agent 工作流，我会优先用文本资源，除非二进制产物本身就是关键上下文。

## 客户端如何列举和读取 Resource

客户端通过 `ListResourcesAsync()`、`ListResourceTemplatesAsync()` 和 `ReadResourceAsync(...)` 来发现和读取资源。服务器作者应该理解自己设计的客户体验。

```csharp
using System.Collections.Generic;
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;

IList<McpClientResource> resources = await client.ListResourcesAsync();
IList<McpClientResourceTemplate> templates =
    await client.ListResourceTemplatesAsync();

foreach (var resource in resources)
{
    Console.WriteLine($"{resource.Name}: {resource.Uri}");
}

foreach (var template in templates)
{
    Console.WriteLine($"{template.Name}: {template.UriTemplate}");
}

ReadResourceResult articleResult = await client.ReadResourceAsync(
    "docs://articles/{id}",
    new Dictionary<string, object?> { ["id"] = "resources" });

ReadResourceResult result =
    await client.ReadResourceAsync("config://app/settings");

foreach (var content in result.Contents)
{
    if (content is TextResourceContents text)
    {
        Console.WriteLine(text.Text);
    }
    else if (content is BlobResourceContents blob)
    {
        Console.WriteLine($"{blob.MimeType}: {blob.DecodedData.Length} bytes");
    }
}
```

模板资源需要同时传 URI 模板和参数字典，客户端会先格式化出具体 URI 再读取。这也是为什么描述和 MIME 类型很重要——客户端可能在选择器、命令面板或上下文 UI 里展示资源列表。命名模糊，客户体验也就模糊。

## Resource 订阅与变更通知

Resource 还可以支持订阅更新。SDK 文档描述了 `ResourceUpdatedNotification` 和 `ResourceListChangedNotification` 两种通知。但有一个重要约束：**非请求通知需要 stateful 模式或 stdio，无状态 HTTP 服务端推不了**。

在客户端需要感知之前选中资源已变更时用订阅：配置变了、运行状态更新、报告重新生成、文档被编辑。不要"因为 SDK 有所以加上"——订阅引入了生命周期和状态管理。

SDK 通过 `WithSubscribeToResourcesHandler(...)` 和 `WithUnsubscribeFromResourcesHandler(...)` 注册订阅处理器。特定资源变化时调用 `SendNotificationAsync(NotificationMethods.ResourceUpdatedNotification, ...)`。资源集合变化时发 `ResourceListChangedNotification`。

好处是客户端不用反复轮询就能刷新上下文。代价是你现在要管理会话、已订阅 URI、断开连接和通知行为。数据不常变的话，简单的按需读取可能就够了。

## MCP Prompt：用 `[McpServerPrompt]` 暴露可复用模板

Prompt 是另一个容易被忽略的原语。官方 C# SDK 的属性路径是：类上标 `[McpServerPromptType]`，方法上标 `[McpServerPrompt]`。

Prompt 不是 Tool。Prompt 不执行业务操作。它给用户或客户端一个**可复用的对话起点**，通常带参数。这很适合团队内标准化的代码审查、排查流程、迁移检查清单、特定领域分析。

```csharp
using Microsoft.Extensions.AI;
using ModelContextProtocol.Server;
using System.ComponentModel;

[McpServerPromptType]
public sealed class ReviewPrompts
{
    [McpServerPrompt]
    [Description("为 C# 代码片段创建聚焦的代码审查提示。")]
    public static IEnumerable<ChatMessage> CodeReview(
        [Description("审查聚焦点，如正确性或 API 设计。")]
        string focus,
        [Description("要审查的 C# 代码。")] string code) =>
        [
            new(ChatRole.User, $"""
                用以下聚焦点审查这段 C# 代码：{focus}。

                ~~~csharp
                {code}
                ~~~
                """),
            new(ChatRole.Assistant,
                "我会审查代码并先指出具体问题。")
        ];
}
```

SDK 支持返回 `ChatMessage` 实例（处理简单文本和图片内容），或者 `PromptMessage`（需要协议特定内容类型如嵌入式资源时）。大多数可复用模板场景，`IEnumerable<ChatMessage>` 是够用的起点。

## Prompt 参数与嵌入式资源消息

Prompt 参数应该显式且少。SDK 用 `[Description]` 标注参数，`GetPromptAsync` API 接受按参数名索引的参数字典。`McpServer`、进度、claims、取消令牌和 DI 服务等特殊参数可自动解析。

当 Prompt 需要嵌入 Resource 级别的上下文时，可以返回 `PromptMessage` 并带上 `EmbeddedResourceBlock`：

```csharp
using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;
using System.ComponentModel;

[McpServerPromptType]
public sealed class DocumentPrompts
{
    [McpServerPrompt]
    [Description("创建审查策略文档的提示模板。")]
    public static IEnumerable<PromptMessage> ReviewPolicy(
        [Description("策略文档标识。")] string documentId)
    {
        var markdown = LoadPolicy(documentId);

        return
        [
            new PromptMessage
            {
                Role = Role.User,
                Content = new TextContentBlock
                {
                    Text = "审查这份策略文档，检查模糊表述和缺失示例。"
                }
            },
            new PromptMessage
            {
                Role = Role.User,
                Content = new EmbeddedResourceBlock
                {
                    Resource = new TextResourceContents
                    {
                        Uri = $"policies://documents/{documentId}",
                        MimeType = "text/markdown",
                        Text = markdown
                    }
                }
            }
        ];
    }

    private static string LoadPolicy(string documentId) =>
        $"# 策略 {documentId}

所有生产变更需要评审。";
}
```

这不是替代 Resource，而是**把 Resource 内容嵌入一个特定可复用工作流**。如果客户端应该独立浏览和选择策略文档，建模为 Resource。如果工作流是"按这个指令审查策略"，Prompt 可以是更好的外层合约。

## Resource vs Tool vs Prompt：决策框架

这是我实际用的判断框架。

**如果能力是读取稳定或可寻址的数据，从 Resource 开始。** 客户端能列举、读取、决定包含多少上下文。直接 Resource 对应固定 URI，模板 Resource 对应带参数的 URI 族。

**如果能力是执行工作，从 Tool 开始。** 包括带排序的搜索、计算、API 调用、文件变更、数据库写入，或者有任何操作行为的场景。让 Tool 聚焦，但不要为了避开设计 Tool 把动作硬塞进 Resource。

**如果能力是标准化用户如何启动一个工作流，从 Prompt 开始。** Prompt 很适合带参数的可复用指令。不适合隐藏业务逻辑，因为客户端期望的是消息，不是操作。

边界情况最考验设计判断。"按 ID 查客户档案"大概率是 Resource。"查找有流失风险的客户"大概率是 Tool，因为隐含查询逻辑和排序。"分析此客户账户的续费风险"可能是 Prompt——如果用户先提供或选择账户上下文的话。

这个区分能落实，MCP 服务器对客户端、用户和模型的可用性都会好一截。

## 常见的实现坑

第一个坑是把所有东西建模成 Tool。Tool 最直观，但已知内容通常更适合 Resource 的方式暴露。

第二个坑是把动态搜索伪装成模板 Resource。如果用户输入任意过滤条件、排序规则和结果数量，Tool 合约更诚实。

第三个坑是忘了 Prompt 是面向用户的。参数模糊、消息泛泛的 Prompt 既难发现又难信任。

第四个坑是等到客户端需要通知时才考虑订阅。Resource 订阅、资源列表变更和 Prompt 列表变更很强大，但需要正确的服务端模式——无状态 HTTP 推不了通知。

## 参考

- [原文：MCP Resources and Prompts in C#](https://www.devleader.ca/2026/07/15/mcp-resources-and-prompts-in-c-exposing-data-and-reusable-templates)
- [MCP 官方 Server Concepts](https://modelcontextprotocol.io/docs/learn/server-concepts)
- [C# SDK Resource 文档](https://raw.githubusercontent.com/modelcontextprotocol/csharp-sdk/main/docs/concepts/resources/resources.md)
- [C# SDK Prompt 文档](https://raw.githubusercontent.com/modelcontextprotocol/csharp-sdk/main/docs/concepts/prompts/prompts.md)
- [NuGet: ModelContextProtocol](https://www.nuget.org/packages/ModelContextProtocol/)
- [McpClient API 参考](https://csharp.sdk.modelcontextprotocol.io/api/ModelContextProtocol.Client.McpClient.html)
- [RFC 6570 URI Template](https://datatracker.ietf.org/doc/html/rfc6570)
