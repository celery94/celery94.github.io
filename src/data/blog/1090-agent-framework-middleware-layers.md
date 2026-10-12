---
pubDatetime: 2026-10-12T08:50:00+08:00
title: "Agent Framework 三层中间件怎么选"
description: "ChatClient、Agent Run 与函数调用中间件不是二选一，而是套在模型调用、整轮运行和工具调用三层上的拦截点。本文用一个 Tavily 搜索日志的例子说明该把代码写在哪一层，以及流式输出、函数调用中间件的使用边界。"
tags: ["C#", ".NET", "AI Agent", "Microsoft Agent Framework"]
slug: "agent-framework-middleware-layers"
ogImage: "../../assets/1090/01-cover.jpg"
source: "https://jesseliberty.com/2026/08/08/chatclient-middleware-vs-agent-middleware/"
---

给多智能体应用加日志时，最容易卡住的地方不是写不出中间件，而是不知道该写在哪儿。写早了拿不到工具名，写晚了看不到实际发往模型的完整消息，接上流式输出之后日志还可能整段消失。

Jesse Liberty 在[原文](https://jesseliberty.com/2026/08/08/chatclient-middleware-vs-agent-middleware/)里把 Microsoft Agent Framework 的中间件分成 ChatClient Middleware 和 Agent Middleware 两类，并给了一段给单个 Agent 记录 Tavily 搜索调用的代码。他的例子跑得通，但官方文档现在把中间件明确列成三类。这个差异不是文字游戏，它直接决定你该把 `Use` 挂在哪一层。

## 中间件不是替代关系，是三层的拦截点

Microsoft Agent Framework 官方文档现在给出三类中间件：

1. Agent Run 中间件：拦截每一次 Agent 运行，可以检查和修改输入与输出。
2. 函数调用中间件（function calling middleware）：拦截 Agent 执行的每一次工具调用。
3. `IChatClient` 中间件：拦截发往 `IChatClient` 的调用，也就是真正发往模型的那些请求。

三者的关系是嵌套，而不是并列。一次典型的带工具调用请求会这样穿过它们：

```text
Agent Run 中间件
  └─ ChatClient 中间件（第一次模型调用：模型要求调用工具）
       └─ 函数调用中间件（执行 tavily_search）
  └─ ChatClient 中间件（第二次模型调用：把工具结果发回模型）
```

每次调用工具的循环里，ChatClient 中间件会执行两次而非一次。这个细节决定了中间件的选型：想在日志里看到「这一轮用户问了什么、Agent 最终答了什么」，用 Agent Run 中间件；想看到「每次发往模型的消息里到底有什么」，用 ChatClient 中间件。

原文把第二类称为「Agent Middleware」，这个说法容易让人以为只有两个层级。按官方文档的划分，Agent 这一层是 Agent Run 中间件，函数调用中间件是从 Agent 里单独拆出来的一层。

## ChatClient 中间件：看模型收到了什么

ChatClient 中间件挂在 `IChatClient` 上，用 builder 模式注册：

```csharp
var chatClient = new AIProjectClient(
        new Uri("<your-foundry-project-endpoint>"),
        new DefaultAzureCredential())
    .GetProjectOpenAIClient()
    .GetProjectResponsesClient()
    .AsIChatClient(deploymentName);

var middlewareEnabledChatClient = chatClient
    .AsBuilder()
    .Use(getResponseFunc: CustomChatClientMiddleware, getStreamingResponseFunc: null)
    .Build();

var agent = new ChatClientAgent(middlewareEnabledChatClient, instructions: "You are a helpful assistant.");
```

`CustomChatClientMiddleware` 的签名是四个参数，而不是原文里描述的「处理消息的函数」：

```csharp
async Task<ChatResponse> CustomChatClientMiddleware(
    IEnumerable<ChatMessage> messages,
    ChatOptions? options,
    IChatClient innerChatClient,
    CancellationToken cancellationToken)
{
    Console.WriteLine(messages.Count());
    var response = await innerChatClient.GetResponseAsync(messages, options, cancellationToken);
    Console.WriteLine(response.Messages.Count);
    return response;
}
```

注意 `innerChatClient` 这个参数。中间件链上的每个环节都拿到「下一个环节」，自己决定何时调用它，这正是可以修改请求和响应的原因。原文示例里 `getStreamingResponseFunc` 传了 `null`，官方文档对此有一条容易被忽略的说明：只提供非流式中间件时，Agent 会把它同时用于流式和流式调用，但流式会被降级成非流式执行来满足中间件的预期。如果应用依赖逐字输出，这个降级就是线上事故。

## Agent Run 中间件：看整轮运行

Agent Run 中间件挂在 Agent 上，用 `AsBuilder()` 注册：

```csharp
async Task<AgentResponse> CustomAgentRunMiddleware(
    IEnumerable<ChatMessage> messages,
    AgentSession? session,
    AgentRunOptions? options,
    AIAgent innerAgent,
    CancellationToken cancellationToken)
{
    Console.WriteLine(messages.Count());
    var response = await innerAgent.RunAsync(messages, session, options, cancellationToken);
    Console.WriteLine(response.Messages.Count);
    return response;
}
```

注册方式和 ChatClient 中间件长得很像，这也是容易混淆的地方：

```csharp
var middlewareEnabledAgent = originalAgent
    .AsBuilder()
    .Use(runFunc: CustomAgentRunMiddleware, runStreamingFunc: CustomAgentRunStreamingMiddleware)
    .Use(CustomFunctionCallingMiddleware)
    .Build();
```

同样的 `AsBuilder().Use()`，作用对象是 `IChatClient` 还是 `AIAgent`，得到的拦截层级完全不同。前者最容易踩的坑是 `Use` 的顺序：一个 builder 上注册多个中间件时，先注册的包在外层，后注册的在内层。

Agent Run 中间件能拿到 `session` 和 `AgentRunOptions`，这是它相对 ChatClient 中间件的主要优势。原文提到的会话信息、身份跟踪、token 预算管理都属于这一层——token 预算尤其如此，它要跨模型调用累计，不能在每个 ChatClient 调用里各算一份。

## 函数调用中间件：抓具体工具

函数调用中间件是原文里最有实操价值的一段。它的签名如下，注意第三个参数是 `next`，返回值类型是 `ValueTask<object?>`：

```csharp
async ValueTask<object?> CustomFunctionCallingMiddleware(
    AIAgent agent,
    FunctionInvocationContext context,
    Func<FunctionInvocationContext, CancellationToken, ValueTask<object?>> next,
    CancellationToken cancellationToken)
{
    Console.WriteLine($"Function Name: {context!.Function.Name}");
    var result = await next(context, cancellationToken);
    Console.WriteLine($"Function Call Result: {result}");
    return result;
}
```

Jesse 在演示程序里只改动了 `ResearcherAgent` 的构建代码，就实现了对 Tavily 工具的定向日志：

```csharp
.Use(async (agent, context, next, cancellationToken) =>
{
    if (context.Function.Name == tavilyTool.Name)
    {
        _logger.LogInformation(
            "Researcher invoking Tavily tool '{Tool}' with arguments {Arguments}",
            context.Function.Name,
            context.Arguments);
    }

    return await next(context, cancellationToken);
})
```

日志输出形如：

```text
[trace] → execute_tool tavily_search
info: BlogWriter.ResearcherAgent[0]
      Researcher invoking Tavily tool 'tavily_search' with arguments [query, ChatClient middleware vs Agent middleware Microsoft Agent Framework]
[trace] ← execute_tool tavily_search (1796 ms)
```

这段代码有两个值得注意的判断。第一，条件判断放在中间件里而不是拆成多个 Agent：日志需求只影响一个工具，没必要改动其他 Agent 的构建。第二，中间件在 `next` 之前记录参数，在 `next` 之后就能拿到结果——如果还需要记录耗时，把时间戳放在这两点之间即可。

原文给出的类写法把上下文类型写成 `AgentRunContext`，并用 `context.Result`。按当前官方文档，函数调用中间件的上下文类型是 `FunctionInvocationContext`，结果通过 `next` 的返回值传出。照着原文那段类定义抄会编译不过，直接用上面这段 lambda 或者按官方签名改成类都可以。

代码里的 `AIProjectClient`、`AsIChatClient`、`ChatClientAgent` 来自 `Microsoft.Extensions.AI` 与 `Microsoft.Agents.AI` 两个包，中间件的工厂方法在这些包的预览版本之间改过名字和参数。上面的签名对应 2026 年 8 月官方文档的状态，落到项目里之前先对一下自己锁定的包版本；`Use` 的具体重载以本地 IntelliSense 为准。

函数调用中间件还有一个当前限制：只对使用 `FunctionInvokingChatClient` 的 `AIAgent` 生效，例如 `ChatClientAgent`。换成自己实现的 Agent 循环，这一层就不会触发。

## 决定写在哪一层的三个问题

选层可以按这三个问题顺序判断：

- 需要看到每次发往模型的原始消息、或者要改写 `ChatOptions`：用 ChatClient 中间件。
- 需要跨多次模型调用统计 token、维护会话或身份：用 Agent Run 中间件。
- 只关心某个具体的工具被怎么调用、返回了什么：用函数调用中间件。

还有一个容易踩的边界：函数调用中间件可以把 `FunctionInvocationContext.Terminate` 设为 `true` 来终止工具调用循环。这能阻止框架把工具结果发回模型，但如果一次迭代里有多个待执行函数，剩余函数也可能被一并跳过，聊天历史里还会留下「有函数调用内容、没有函数结果内容」的不一致状态。这类终止逻辑上线前最好在真实会话里跑一遍完整多轮对话，确认历史仍然可用。

Aide Hub 会继续分享 AI 助手、开发工具和软件工程实践方面的内容，包括 Agent Framework 后续的完整示例。

## 参考

- [ChatClient Middleware vs. Agent Middleware — Jesse Liberty](https://jesseliberty.com/2026/08/08/chatclient-middleware-vs-agent-middleware/)
- [Agent Middleware — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/concepts/agents/middleware/?pivots=programming-language-csharp)
- [Middleware in Microsoft Agent Framework — Jesse Liberty](https://jesseliberty.com/2026/07/23/middleware-in-microsoft-agent-framework/)
- [JesseLiberty/blogMigration---public 演示程序](https://github.com/JesseLiberty/blogMigration---public)
- [microsoft/agent-framework .NET 示例](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples)
- [Custom IChatClient middleware — Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/ai/microsoft-extensions-ai#custom-ichatclient-middleware)
