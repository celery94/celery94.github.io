---
pubDatetime: 2026-05-08T11:00:00+08:00
title: "Microsoft Agent Framework 持久化工作流详解：从控制台到 Azure Functions"
description: "Microsoft Agent Framework（MAF）提供了一套完整的工作流编程模型，支持顺序执行、并行扇出/扇入、人工审批、条件路由和子工作流。本文带你从零搭建一个简单的内存工作流，逐步添加持久化、并行 AI 智能体，再到 Azure Functions 云托管和 MCP 工具暴露。"
tags: ["CSharp", "dotnet", "AI", "AzureFunctions"]
slug: "microsoft-agent-framework-durable-workflows"
ogImage: "../../assets/783/01-cover.jpg"
source: "https://devblogs.microsoft.com/dotnet/durable-workflows-in-microsoft-agent-framework"
---

Microsoft Agent Framework（MAF）是微软开源的多语言 AI 智能体构建框架。它的工作流编程模型允许你把多个智能体和操作单元组合成多步流水线——定义有向图、指定边，框架负责执行、数据传递和错误传播。本文从一个最简单的控制台应用出发，逐步加上持久化、并行 AI 智能体和 Azure Functions 托管。

## 核心概念

### Executor：工作的基本单元

Executor 接受类型化输入、处理后产生输出，通过继承 `Executor<TInput, TOutput>` 来创建：

```csharp
using Microsoft.Agents.AI.Workflows;

internal sealed class OrderLookup()
    : Executor<OrderCancelRequest, Order>("OrderLookup")
{
    public override async ValueTask<Order> HandleAsync(
        OrderCancelRequest message,
        IWorkflowContext context,
        CancellationToken cancellationToken = default)
    {
        await Task.Delay(TimeSpan.FromMilliseconds(100), cancellationToken);
        return new Order(
            Id: message.OrderId,
            OrderDate: DateTime.UtcNow.AddDays(-1),
            IsCancelled: false,
            CancelReason: message.Reason,
            Customer: new Customer("Jerry", "jerry@example.com"));
    }
}

internal sealed class OrderCancel()
    : Executor<Order, Order>("OrderCancel")
{
    public override async ValueTask<Order> HandleAsync(
        Order message, IWorkflowContext context,
        CancellationToken cancellationToken = default)
    {
        await Task.Delay(TimeSpan.FromMilliseconds(200), cancellationToken);
        return message with { IsCancelled = true };
    }
}

internal sealed class SendEmail()
    : Executor<Order, string>("SendEmail")
{
    public override ValueTask<string> HandleAsync(
        Order message, IWorkflowContext context,
        CancellationToken cancellationToken = default)
        => ValueTask.FromResult(
            $"Cancellation email sent for order {message.Id} "
            + $"to {message.Customer.Email}.");
}
```

泛型类型参数定义了 Executor 的契约：`TInput` 是上一步传来的内容，`TOutput` 是向下游传递的内容。构造函数里的字符串（如 `"OrderLookup"`）是 Executor 在工作流中的唯一 ID。

### WorkflowBuilder：把 Executor 连成图

```csharp
OrderLookup orderLookup = new();
OrderCancel orderCancel = new();
SendEmail sendEmail = new();

// OrderLookup ──► OrderCancel ──► SendEmail
Workflow cancelOrder = new WorkflowBuilder(orderLookup)
    .WithName("CancelOrder")
    .WithDescription("Cancel an order and notify the customer")
    .AddEdge(orderLookup, orderCancel)
    .AddEdge(orderCancel, sendEmail)
    .Build();
```

每个 Executor 的 `TOutput` 必须与下游 Executor 的 `TInput` 匹配，框架在编译期做类型检查。

### 内存运行：最快上手方式

安装包：

```bash
dotnet add package Microsoft.Agents.AI
dotnet add package Microsoft.Agents.AI.Workflows
```

用 `InProcessExecution.RunStreamingAsync` 在进程内运行，返回 `StreamingRun` 对象，每一步完成时产生事件：

```csharp
var cancelRequest = new OrderCancelRequest(OrderId: "123", Reason: "Wrong color");

await using StreamingRun run =
    await InProcessExecution.RunStreamingAsync(cancelOrder, input: cancelRequest);

await foreach (WorkflowEvent evt in run.WatchStreamAsync())
{
    if (evt is ExecutorCompletedEvent completed)
        Console.WriteLine($"{completed.ExecutorId}: {completed.Data}");
}
```

不需要任何外部依赖，一个 `dotnet run` 就能跑起来。

## 添加持久化

内存运行器把所有状态保存在进程中，进程退出后状态全部丢失。`Microsoft.Agents.AI.DurableTask` 包在不改变工作流定义的前提下添加持久化能力：

- **有状态持久执行**：工作流可以在进程重启和故障后继续
- **自动检查点**：每一步完成后自动保存进度
- **分布式执行**：同一工作流的不同 Executor 可以在不同机器上运行
- **长时间运行**：工作流可以持续数分钟、数小时甚至数天
- **可观测性**：内置 Dashboard 监控和管理工作流执行

### 本地运行 DTS 模拟器

Durable Task Scheduler（DTS）负责持久化工作流状态和协调执行。本地开发用 Docker 一行启动：

```bash
docker run -d --name dts-emulator \
  -p 8080:8080 -p 8082:8082 \
  mcr.microsoft.com/dts/dts-emulator:latest
```

- 端口 8080：Scheduler 端点（应用连接此处）
- 端口 8082：Dashboard UI（浏览器打开 `http://localhost:8082`）

### 持久化控制台应用

安装额外包：

```bash
dotnet add package Microsoft.Agents.AI.DurableTask --prerelease
dotnet add package Microsoft.DurableTask.Client.AzureManaged
dotnet add package Microsoft.DurableTask.Worker.AzureManaged
dotnet add package Microsoft.Extensions.Hosting
```

**工作流定义完全不变**，只需换掉宿主方式：

```csharp
string dtsConnectionString =
    Environment.GetEnvironmentVariable(
        "DURABLE_TASK_SCHEDULER_CONNECTION_STRING")
    ?? "Endpoint=http://localhost:8080;TaskHub=default;Authentication=None";

// 工作流定义和之前完全一样
Workflow cancelOrder = new WorkflowBuilder(orderLookup)
    .WithName("CancelOrder")
    .WithDescription("Cancel an order and notify the customer")
    .AddEdge(orderLookup, orderCancel)
    .AddEdge(orderCancel, sendEmail)
    .Build();

// 用持久化运行时宿主
IHost host = Host.CreateDefaultBuilder(args)
    .ConfigureServices(services =>
    {
        services.ConfigureDurableWorkflows(
            workflowOptions =>
                workflowOptions.AddWorkflow(cancelOrder),
            workerBuilder: builder =>
                builder.UseDurableTaskScheduler(dtsConnectionString),
            clientBuilder: builder =>
                builder.UseDurableTaskScheduler(dtsConnectionString));
    })
    .Build();

await host.StartAsync();

try
{
    IWorkflowClient workflowClient =
        host.Services.GetRequiredService<IWorkflowClient>();

    OrderCancelRequest request = new(OrderId: "12345", Reason: "Wrong color");
    IAwaitableWorkflowRun run =
        (IAwaitableWorkflowRun)await workflowClient.RunAsync(cancelOrder, request);

    Console.WriteLine($"Workflow started with run id: {run.RunId}");
    string? result = await run.WaitForCompletionAsync<string>();
    Console.WriteLine($"Workflow completed. {result}");
}
finally
{
    await host.StopAsync();
}
```

`ConfigureDurableWorkflows` 把工作流注册到 Durable Task 运行时，把每个 Executor 映射为持久化 Activity。工作流完成后，在 Dashboard（`http://localhost:8082`）可以看到每一步的执行时间线和输入/输出详情。

**核心要点：同一份工作流定义，不同的运行时。换掉宿主，工作流就获得了持久化、检查点、可观测性和分布式执行能力，Executor 代码一行不改。**

## 扇出/扇入与 AI 智能体

需要多个智能体并行处理同一输入时，用扇出/扇入模式。`AddFanOutEdge` 把消息同时发给多个 Executor，`AddFanInBarrierEdge` 等所有 Executor 完成后再继续。

MAF 支持直接把 AI 智能体作为 Executor，`AsAIAgent` 扩展方法从 chat client 和系统提示词创建 Executor：

```csharp
AIAgent physicist = chatClient.AsAIAgent(
    "You are a physics expert. Be concise (2-3 sentences).",
    "Physicist");
AIAgent chemist = chatClient.AsAIAgent(
    "You are a chemistry expert. Be concise (2-3 sentences).",
    "Chemist");

// 工作流：ParseQuestion -> [Physicist, Chemist] -> Aggregator
Workflow workflow = new WorkflowBuilder(parseQuestion)
    .WithName("ExpertReview")
    .AddFanOutEdge(parseQuestion, [physicist, chemist])
    .AddFanInBarrierEdge([physicist, chemist], aggregator)
    .Build();
```

在 DTS 上运行时，Physicist 和 Chemist 可以分别在不同机器上执行。每个智能体的响应会被检查点保存，进程重启时已完成的智能体不会重新执行。

注册时用 `ConfigureDurableOptions` 而非 `ConfigureDurableWorkflows`，这是更通用的 API，可以在同一宿主里同时注册工作流和独立 AI 智能体：

```csharp
services.ConfigureDurableOptions(
    options => options.Workflows.AddWorkflow(workflow),
    workerBuilder: builder =>
        builder.UseDurableTaskScheduler(dtsConnectionString),
    clientBuilder: builder =>
        builder.UseDurableTaskScheduler(dtsConnectionString));
```

## 托管到 Azure Functions

`Microsoft.Agents.AI.Hosting.AzureFunctions` 包把 MAF 工作流接入 Azure Functions 运行时：

```bash
dotnet add package Microsoft.Agents.AI.Hosting.AzureFunctions
```

**为什么用 Azure Functions？**

- **无服务器弹性伸缩**：根据负载自动扩缩容，空闲时缩减到零，只为实际计算付费
- **内置 HTTP 端点**：每个注册的工作流自动获得 HTTP 触发器，无需手写控制器
- **MCP 工具支持**：一个开关即可把工作流暴露为 MCP 工具
- **零样板代码**：宿主包从工作流定义自动生成编排函数、Activity 函数和实体函数

完整的 `Program.cs`：

```csharp
using Microsoft.Agents.AI.Hosting.AzureFunctions;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Azure.Functions.Worker.Builder;
using Microsoft.Extensions.Hosting;

Workflow cancelOrder = new WorkflowBuilder(orderLookup)
    .WithName("CancelOrder")
    .WithDescription("Cancel an order and notify the customer")
    .AddEdge(orderLookup, orderCancel)
    .AddEdge(orderCancel, sendEmail)
    .Build();

using IHost app = FunctionsApplication
    .CreateBuilder(args)
    .ConfigureFunctionsWebApplication()
    .ConfigureDurableWorkflows(workflows => workflows.AddWorkflow(cancelOrder))
    .Build();

app.Run();
```

宿主层自动完成以下映射：

- 工作流 → 编排函数
- 每个 Executor → Activity 函数（自带重试、检查点和容错）
- 自动生成 HTTP 触发器：`POST /api/workflows/CancelOrder/run`

触发方式：

```http
# 异步触发，返回 202 Accepted + run ID
POST http://localhost:7071/api/workflows/CancelOrder/run
Content-Type: text/plain

12345
```

```http
# 同步触发，等待完成后返回结果
POST http://localhost:7071/api/workflows/CancelOrder/run
Content-Type: text/plain
x-ms-wait-for-response: true

12345
```

## Human-in-the-Loop（人工审批）

`RequestPort` 像 Executor 一样存在于图中，但它会暂停编排并等待外部响应。托管在 Azure Functions 上时，框架自动为每个 `RequestPort` 生成 HTTP 端点。

下面是一个费用报销工作流，含经理审批门和两个并行财务审批：

```csharp
CreateApprovalRequest createRequest = new();
RequestPort<ApprovalRequest, ApprovalResponse> managerApproval =
    RequestPort.Create<ApprovalRequest, ApprovalResponse>("ManagerApproval");
PrepareFinanceReview prepareFinanceReview = new();
RequestPort<ApprovalRequest, ApprovalResponse> budgetApproval =
    RequestPort.Create<ApprovalRequest, ApprovalResponse>("BudgetApproval");
RequestPort<ApprovalRequest, ApprovalResponse> complianceApproval =
    RequestPort.Create<ApprovalRequest, ApprovalResponse>("ComplianceApproval");
ExpenseReimburse reimburse = new();

Workflow expenseApproval = new WorkflowBuilder(createRequest)
    .WithName("ExpenseReimbursement")
    .AddEdge(createRequest, managerApproval)
    .AddEdge(managerApproval, prepareFinanceReview)
    .AddFanOutEdge(prepareFinanceReview, [budgetApproval, complianceApproval])
    .AddFanInBarrierEdge([budgetApproval, complianceApproval], reimburse)
    .Build();
```

外部系统调用状态端点查看待审批请求，然后 POST 响应解除工作流阻塞：

```http
POST http://localhost:7071/api/workflows/ExpenseReimbursement/respond/{runId}
Content-Type: application/json

{
  "eventName": "ManagerApproval",
  "response": { "approved": true, "comments": "Looks good" }
}
```

## 把工作流暴露为 MCP 工具

设置 `exposeMcpToolTrigger: true`，工作流变为可调用的 MCP 工具，其他 AI 智能体或 MCP 兼容客户端（包括 GitHub Copilot、IDE 扩展等）可以发现并调用：

```csharp
.ConfigureDurableWorkflows(workflows =>
{
    workflows.AddWorkflow(orderLookupWorkflow,
        exposeStatusEndpoint: false,
        exposeMcpToolTrigger: true);
})
```

Functions 宿主在 `/runtime/webhooks/mcp` 生成远程 MCP 端点，工作流的 `.WithName()` 和 `.WithDescription()` 直接映射为 MCP 工具的名称和描述。

## 更多工作流模式

### 条件路由

`AddSwitch` 根据上一步输出路由到不同 Executor：

```csharp
builder.AddSwitch(spamDetector, switchBuilder =>
    switchBuilder
        .AddCase(
            result => result is DetectionResult r
                && r.Decision == SpamDecision.NotSpam,
            emailAssistant)
        .AddCase(
            result => result is DetectionResult r
                && r.Decision == SpamDecision.Spam,
            handleSpam)
        .WithDefault(handleUncertain));
```

### 共享状态

并行 Executor 可通过作用域键值状态共享数据：

```csharp
// 在一个 Executor 中写入
await context.QueueStateUpdateAsync(
    fileID, fileContent,
    scopeName: "FileContentState", cancellationToken);

// 在另一个 Executor 中读取
var fileContent = await context.ReadStateAsync<string>(
    message, scopeName: "FileContentState", cancellationToken);
```

### 子工作流

把一个工作流作为 Executor 嵌入另一个工作流，实现模块化分层架构：

```csharp
ExecutorBinding subWorkflowExecutor =
    subWorkflow.BindAsExecutor("TextProcessing");

var mainWorkflow = new WorkflowBuilder(prefix)
    .AddEdge(prefix, subWorkflowExecutor)
    .AddEdge(subWorkflowExecutor, postProcess)
    .WithOutputFrom(postProcess)
    .Build();
```

在持久化运行时上，子工作流作为子编排运行，结果正常传播。

## 参考

- [Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [工作流示例代码](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/03-workflows)
- [Azure Functions 托管示例](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/04-hosting/DurableWorkflows/AzureFunctions)
- [Microsoft.Agents.AI.DurableTask on NuGet](https://www.nuget.org/packages/Microsoft.Agents.AI.DurableTask)
- [Microsoft.Agents.AI.Hosting.AzureFunctions on NuGet](https://www.nuget.org/packages/Microsoft.Agents.AI.Hosting.AzureFunctions)
- [原文：Durable Workflows in the Microsoft Agent Framework](https://devblogs.microsoft.com/dotnet/durable-workflows-in-microsoft-agent-framework)
