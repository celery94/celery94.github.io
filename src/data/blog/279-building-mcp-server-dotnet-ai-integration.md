---
pubDatetime: 2025-04-21 10:15:14
tags: [MCP, .NET, 人工智能, LLM, 编程, 工具集成, Cursor IDE]
slug: building-mcp-server-dotnet-ai-integration
source: https://engincanveske.substack.com/p/building-your-first-mcp-server-with?utm_source=bonobopress&utm_medium=newsletter&utm_campaign=2040
title: 手把手：用.NET搭建你的第一个 MCP Server，并集成到 AI 代码编辑器
description: 深入浅出介绍Model Context Protocol (MCP) 原理、架构，以及如何使用.NET快速搭建MCP Server，并无缝对接到 Cursor IDE，实现AI与外部工具和数据的高效集成。
---

# 手把手：用.NET搭建你的第一个 MCP Server，并集成到 AI 代码编辑器

## 引言：LLM连接现实世界的“桥梁”

随着大语言模型（LLM）在软件开发中的普及，越来越多的开发者希望让AI不再是“知识孤岛”，而能直接调用各种工具和API，实现真正的智能化协作。🌉

Model Context Protocol（MCP）应运而生，它为AI模型与外部数据、服务之间建立了一套标准、安全的交互协议。你是否也想让AI帮你查询数据库、调用第三方服务，甚至获取系统当前时间？本教程将带你用.NET构建一个MCP Server，并通过Cursor IDE实现端到端集成，让你的AI工具真正“活起来”！

---

## 一、什么是 Model Context Protocol（MCP）？

MCP（Model Context Protocol）是Anthropic提出的一种开放协议，旨在让开发者能够方便、安全地实现AI与各种工具、数据源之间的双向通信。

**核心思想：**

- **MCP Server**：对外暴露功能或数据（比如查询数据库、获取实时天气）。
- **MCP Client**：连接到指定的MCP Server，作为中间人协调AI与Server的通信（例如Cursor IDE）。
- **MCP Host**：最终消费这些服务的应用（如Claude Desktop、IDE等）。

---

## 二、为何需要 MCP？来看个实际例子

假设你在Cursor IDE里问：“现在上海时间几点？”很多AI模型默认无法联网，无法获得实时数据。这时，只需让AI调用一个MCP Server，由Server查时间再返回答案，问题迎刃而解！

如果没有MCP，AI获取外部数据就会异常繁琐且不安全。有了MCP——

- 数据访问结构化、安全、可控
- 各种工具与API轻松标准接入
- 客户端（如IDE）和AI之间只需关注协议对接

---

## 三、用.NET开发你的第一个 MCP Server

### 1. 新建项目

首先，新建一个.NET控制台应用：

```bash
dotnet new console -n McpTimeServer
```

### 2. 安装依赖

通过NuGet添加 `ModelContextProtocol` 包：

```bash
dotnet add package ModelContextProtocol
```

这个包提供了构建MCP Server/Client以及与LLMs集成所需的全部API。

### 3. 编写 MCP Server 主程序

打开 `Program.cs`，更新为如下内容：

```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = Host.CreateEmptyApplicationBuilder(null);

// 注册 MCP server 服务
builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()     // 使用标准输入输出通信
    .WithToolsFromAssembly();       // 自动发现并注册 MCP 工具

var app = builder.Build();
await app.RunAsync();
```

这一小段代码就完成了Server主架构的搭建。下面我们来实现实际功能。

### 4. 实现自定义工具类

新建 `TimeTools.cs`，实现如下：

```csharp
[McpServerToolType]
public static class TimeTools
{
    [McpServerTool, Description("获取当前时间")]
    public static string GetCurrentTime()
    {
        return DateTimeOffset.Now.ToString();
    }

    [McpServerTool, Description("按时区获取当前时间")]
    public static string GetTimeInTimezone(string timezone)
    {
        try
        {
            var tz = TimeZoneInfo.FindSystemTimeZoneById(timezone);
            return TimeZoneInfo.ConvertTime(DateTimeOffset.Now, tz).ToString();
        }
        catch
        {
            return "Invalid timezone specified";
        }
    }
}
```

- 用 `[McpServerToolType]` 标注类，表示这是 MCP 工具集合。
- 每个 `[McpServerTool]` 方法都可被AI客户端调用。

---

## 四、将 MCP Server 集成进 Cursor IDE

### 步骤一：配置 Cursor IDE

1. 打开Cursor设置（顶部菜单 File -> Preferences -> Cursor Settings 或右上角齿轮图标）。
2. 在设置窗口找到“MCP”部分，点击“Add new global MCP server”。
3. 在弹出的 `mcp.json` 配置文件中添加如下内容：

```json
{
  "mcpServers": {
    "timeServer": {
      "command": "dotnet",
      "args": [
        "run",
        "--project",
        "path/to/your/McpTimeServer", // 替换为你的项目绝对路径
        "--no-build"
      ]
    }
  }
}
```

![Cursor IDE中的 MCP 设置界面](https://substackcdn.com/image/fetch/w_1456,c_limit,f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F2dea573d-5c51-44d0-a3f6-622f47fb9396_946x1105.png)

### 步骤二：测试你的 MCP Server

1. 保存配置后回到Cursor设置页，在MCP区启用新Server（点击刷新按钮即可）。
2. 在聊天窗口尝试提问：“现在纽约时间几点？”
3. AI就会通过你刚刚实现的 MCP Server 调用 `GetTimeInTimezone`，返回实时答案！

![成功调用并返回结果](https://substackcdn.com/image/fetch/w_1456,c_limit,f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F88c9a8ef-5d85-4e63-bc1e-1533bd5876a7_1444x550.png)

---

## 五、总结与拓展思考

通过本文，你已经掌握了：

✅ MCP 的基本原理和架构  
✅ 用.NET快速搭建可用的 MCP Server  
✅ 如何将其无缝对接进 Cursor IDE，实现AI与外部世界的数据交互

这只是起点！你可以基于这个框架继续扩展——比如接入数据库查询、企业内部接口、IoT设备等，让AI成为你开发流程里真正的超级助手！

---

> 🚀 **你的AI工具还想集成哪些功能？欢迎评论区留言交流！**  
> 👉 如果觉得有用，也欢迎转发给对 MCP 感兴趣的小伙伴！
>
> MCP 让 AI 不止于“问答”，而是你代码世界里的“万能工匠”！
