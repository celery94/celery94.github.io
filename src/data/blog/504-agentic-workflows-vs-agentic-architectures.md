---
pubDatetime: 2025-10-24
title: 智能体工作流与智能体架构：理解 AI Agent 系统设计的两个关键维度
description: 深入解析 Agentic Workflows 和 Agentic Architectures 的本质区别，探讨如何在 AI Agent 系统设计中正确选择工作流模式与架构模式，并结合 .NET 生态实践提供实用的设计指导
tags: ["AI", "Agent", "Architecture", "Workflow", ".NET", "Azure"]
slug: agentic-workflows-vs-agentic-architectures
---

在当前的 AI 领域，"Agentic AI"（智能体 AI）已经成为最热门的话题之一。然而，许多开发者在讨论时会混淆两个重要的概念：**Agentic Workflows**（智能体工作流）和 **Agentic Architectures**（智能体架构）。尽管这两个术语经常被交替使用，但它们实际上代表了 AI Agent 系统设计的两个不同维度，理解它们的区别对于构建高效、可维护的智能体系统至关重要。

## 什么是 AI Agent（智能体）

在深入探讨工作流与架构的区别之前，我们首先需要明确什么是 AI Agent。根据 Microsoft 的定义，**AI Agent 是一个软件实体，能够自主或半自主地执行任务，通过接收输入、处理信息并采取行动来实现特定目标**。

一个现代的 AI Agent 系统通常包含以下核心组件：

1. **大语言模型 (LLM)**：作为 Agent 的"大脑"，负责推理和语言理解
2. **指令 (Instructions)**：定义 Agent 的目标、行为规范和约束条件
3. **工具 (Tools)**：Agent 可以调用的功能或 API，用于检索知识或执行操作
4. **记忆系统 (Memory)**：包括短期记忆（对话上下文）和长期记忆（知识库）

一个优秀的 Agent 能够：

- 接收非结构化的输入（如用户提示、警报或来自其他 Agent 的消息）
- 基于可用信息分析数据并做出决策
- 动态调整策略而无需持续的人工干预
- 通过工具调用与外部系统交互
- 在流动、动态和不可预测的环境中适应

## Agentic Workflows：定义"做什么"

**Agentic Workflows（智能体工作流）**关注的是 Agent 为实现目标而采取的**一系列步骤**，它回答的是"做什么"的问题——即实际的处理流程。

### 典型的工作流步骤

一个标准的 Agentic Workflow 通常包括以下步骤：

1. **规划创建 (Planning)**：使用 LLM 创建执行计划
2. **任务分解 (Task Decomposition)**：将复杂任务拆解为更小的子任务
3. **工具使用 (Tool Usage)**：调用外部工具（如互联网搜索、数据库查询、API 调用）
4. **反思与调整 (Reflection)**：评估执行结果，根据反馈调整计划

### 常见的工作流模式

在实际应用中，存在多种成熟的工作流模式，每种模式适用于不同的场景：

#### 1. 推理与规划模式

- **Self-ask**：Agent 显式地提出后续问题并自我回答
- **ReAct（Reason and Act）**：交替生成推理轨迹和任务特定操作
- **Plan and Solve**：先制定计划，再逐步执行子任务
- **Reflexion**：通过反思任务反馈信号来改进决策

#### 2. 编排模式

- **Sequential Orchestration（顺序编排）**：任务按固定顺序依次执行
- **Concurrent Orchestration（并发编排）**：多个任务并行处理
- **Handoff Orchestration（移交编排）**：任务在不同 Agent 间流转
- **Magentic Orchestration（磁性编排）**：基于能力匹配动态分配任务

### 工作流示例：RAG（检索增强生成）

以一个典型的 RAG 工作流为例：

```text
1. 接收用户查询
2. 将查询分解为更小的检索单元
3. 从知识库检索相关信息
4. 评估检索结果的相关性
5. 综合信息生成最终回答
6. （可选）反思回答质量并迭代优化
```

这个工作流描述了"做什么"，但并未规定"如何实现"——这正是架构层面的职责。

## Agentic Architectures：定义"如何做"

**Agentic Architectures（智能体架构）**关注的是**技术框架和系统设计**，它回答的是"如何做"的问题——即底层结构。

### 核心架构组件

一个完整的 Agentic Architecture 必然包含：

1. **至少一个具备决策能力的 Agent**
2. **Agent 可以使用的工具集合**
3. **短期和长期记忆系统**
4. **消息传递机制**（Agent 间通信）
5. **状态管理**（检查点、恢复机制）

### 常见的架构模式

#### 1. Single-Agent Architecture（单 Agent 架构）

最简单的架构，一个 Agent 处理所有任务。适合相对简单、领域单一的场景。

```csharp
// 使用 Microsoft Agent Framework 创建单 Agent
AIAgent agent = new AzureOpenAIClient(
    new Uri("https://<myresource>.openai.azure.com"),
    new AzureCliCredential())
    .GetChatClient("gpt-4o-mini")
    .CreateAIAgent(new ChatClientAgentOptions()
    {
        Name = "HelpfulAssistant",
        Instructions = "You are a helpful assistant.",
        ChatOptions = chatOptions
    });

// 直接调用 Agent
Console.WriteLine(await agent.RunAsync("Tell me a joke about a pirate."));
```

#### 2. Router Architecture（路由架构）

使用一个主 Agent 作为路由器，根据请求类型将任务分发给专门的 Agent。

```csharp
// 创建专门的 Agent
AIAgent mathTutor = GetMathTutorAgent(chatClient);
AIAgent historyTutor = GetHistoryTutorAgent(chatClient);
AIAgent triageAgent = GetTriageAgent(chatClient);

// 构建 Handoff 工作流
var workflow = AgentWorkflowBuilder.StartHandoffWith(triageAgent)
    .WithHandoff(triageAgent, [mathTutor, historyTutor])  // Triage 可以路由到任一专家
    .WithHandoff(mathTutor, triageAgent)                 // 数学导师可以返回 triage
    .WithHandoff(historyTutor, triageAgent)              // 历史导师可以返回 triage
    .Build();
```

#### 3. Multi-Agent Architecture（多 Agent 架构）

多个 Agent 协同工作，每个 Agent 负责特定的子任务。可以是顺序执行、并发执行或混合模式。

```csharp
// 创建多个专业 Agent
AIAgent frenchAgent = GetFrenchTranslatorAgent(chatClient);
AIAgent spanishAgent = GetSpanishTranslatorAgent(chatClient);
AIAgent englishAgent = GetEnglishTranslatorAgent(chatClient);

// 构建顺序工作流
var workflow = new WorkflowBuilder(frenchAgent)
    .AddEdge(frenchAgent, spanishAgent)
    .AddEdge(spanishAgent, englishAgent)
    .Build();

// 或构建并发工作流
var concurrentWorkflow = AgentWorkflowBuilder.BuildConcurrent(
    new[] { frenchAgent, spanishAgent, englishAgent }
);
```

#### 4. Hierarchical Architecture（层级架构）

引入管理 Agent 协调其他 Agent，适合复杂的任务编排。

```csharp
// Magentic 编排示例：管理 Agent 协调多个专家 Agent
MagenticOrchestration orchestration = new(
    managerAgent,
    [researchAgent, calculationAgent, reportingAgent]
)
{
    LoggerFactory = this.LoggerFactory
};

string input = @"Prepare a comprehensive energy efficiency report 
                 comparing ResNet-50, BERT-base, and GPT-2 models...";

OrchestrationResult<string> result = await orchestration.InvokeAsync(input, runtime);
```

## 关键区别：工作流 vs 架构

理解这两者的区别至关重要，因为：

| 维度 | Agentic Workflows | Agentic Architectures |
|------|-------------------|----------------------|
| **关注点** | 执行步骤和逻辑流程 | 技术框架和系统结构 |
| **回答的问题** | "做什么" | "如何做" |
| **抽象层次** | 业务流程层 | 技术实现层 |
| **变化频率** | 相对稳定 | 可根据需求灵活调整 |
| **描述方式** | 步骤序列、决策树 | 组件图、架构图 |

**核心洞察**：**同一个工作流可以用不同的架构来实现**。这就像同一份菜谱（工作流）可以在不同的厨房设置（架构）中烹饪。

### 实际案例：RAG 工作流的不同架构实现

考虑前面提到的 RAG 工作流，它可以用多种架构实现：

#### 方案 A：单 Agent 架构

```csharp
AIAgent ragAgent = chatClient.CreateAIAgent(
    instructions: @"You are a RAG assistant. For each query:
                    1. Break down the query
                    2. Retrieve relevant information
                    3. Evaluate relevance
                    4. Generate answer",
    tools: [searchTool, databaseTool]
);
```

#### 方案 B：多 Agent 架构

```csharp
AIAgent queryAnalyzer = GetQueryAnalyzerAgent(chatClient);
AIAgent retriever = GetRetrieverAgent(chatClient);
AIAgent evaluator = GetEvaluatorAgent(chatClient);
AIAgent synthesizer = GetSynthesizerAgent(chatClient);

var workflow = new WorkflowBuilder(queryAnalyzer)
    .AddEdge(queryAnalyzer, retriever)
    .AddEdge(retriever, evaluator)
    .AddEdge(evaluator, synthesizer)
    .Build();
```

两种方案实现了相同的工作流，但架构截然不同。选择哪种架构取决于：

- **复杂度**：任务是否复杂到需要专门的 Agent
- **可维护性**：多 Agent 更模块化，但增加了协调开销
- **性能需求**：单 Agent 通信开销低，多 Agent 可并行处理
- **团队能力**：多 Agent 需要更强的系统设计能力

## 在 .NET 生态中的实践

### Azure Logic Apps 中的 Agent Workflows

Azure Logic Apps 提供了两种 Agent 工作流类型：

1. **Autonomous Agents（自主 Agent）**：无需人工交互，适合完全自动化的场景
2. **Conversational Agents（对话 Agent）**：支持人工交互，适合需要人类在环的场景

```csharp
// 在 Azure Logic Apps 中创建自主 Agent
PersistentAgent agent = agentClient.Administration.CreateAgent(
    model: modelDeploymentName,
    name: "mortgage-loan-agent",
    instructions: @"You are a mortgage loan agent that:
                    1. Reviews loan applications
                    2. Collects financial information
                    3. Assesses eligibility
                    4. Makes approval decisions",
    tools: [new CodeInterpreterToolDefinition()]
);
```

### Microsoft Agent Framework 中的 Workflows

Microsoft Agent Framework 明确区分了 AI Agent 和 Workflow：

- **AI Agent**：由 LLM 驱动，步骤动态确定
- **Workflow**：预定义的操作序列，可包含 Agent 作为组件

```csharp
// 构建带有分支逻辑的复杂工作流
WorkflowBuilder builder = new(emailAnalysisExecutor);
builder.AddSwitch(emailAnalysisExecutor, switchBuilder =>
    switchBuilder
        .AddCase(
            GetCondition(expectedDecision: SpamDecision.NotSpam),
            emailAssistantExecutor
        )
        .AddCase(
            GetCondition(expectedDecision: SpamDecision.Spam),
            handleSpamExecutor
        )
        .WithDefault(
            handleUncertainExecutor
        )
)
.AddEdge(emailAssistantExecutor, sendEmailExecutor)
.WithOutputFrom(handleSpamExecutor, sendEmailExecutor, handleUncertainExecutor);

var workflow = builder.Build();
```

### 状态管理与检查点

在长时间运行的工作流中，检查点机制至关重要：

```csharp
// 创建支持检查点的工作流执行
var checkpointManager = CheckpointManager.Default;
var checkpoints = new List<CheckpointInfo>();

Checkpointed<StreamingRun> checkpointedRun = await InProcessExecution
    .StreamAsync(workflow, input, checkpointManager);

// 监听事件并保存检查点
await foreach (WorkflowEvent evt in checkpointedRun.Run.WatchStreamAsync())
{
    if (evt is SuperStepCompletedEvent superStepEvt)
    {
        var checkpoint = superStepEvt.CompletionInfo?.Checkpoint;
        if (checkpoint is not null)
        {
            checkpoints.Add(checkpoint);
            Console.WriteLine($"Checkpoint {checkpoints.Count} created.");
        }
    }
}

// 从检查点恢复执行
if (checkpoints.Count > 5)
{
    await checkpointedRun.RestoreCheckpointAsync(checkpoints[5]);
}
```

## 设计决策指南

### 何时选择哪种架构

#### 选择单 Agent 架构的场景

- 任务相对简单，逻辑清晰
- 延迟敏感，需要快速响应
- 团队规模小，希望降低系统复杂度
- 成本敏感（减少 LLM 调用次数）

#### 选择多 Agent 架构的场景

- 任务复杂，涉及多个专业领域
- 需要高度的模块化和可维护性
- 不同子任务可以并行处理
- 需要灵活地替换或升级特定模块
- 团队有足够的系统设计能力

### 工作流设计的最佳实践

1. **明确定义每个步骤的输入和输出**：使用强类型确保消息流正确传递
2. **适当使用反思机制**：允许 Agent 评估和调整执行计划
3. **实现错误处理和补偿逻辑**：为长时间运行的工作流提供回滚机制
4. **合理使用检查点**：在关键步骤保存状态，支持恢复和调试
5. **监控和可观测性**：记录每个步骤的执行情况，便于问题定位

```csharp
// 使用事件监听实现可观测性
await foreach (WorkflowEvent evt in run.WatchStreamAsync())
{
    switch (evt)
    {
        case ExecutorCompletedEvent executorEvt:
            logger.LogInformation($"Executor {executorEvt.ExecutorId} completed.");
            break;
        case AgentRunUpdateEvent updateEvt:
            logger.LogInformation($"{updateEvt.ExecutorId}: {updateEvt.Data}");
            break;
        case WorkflowOutputEvent outputEvt:
            logger.LogInformation($"Workflow output: {outputEvt.Data}");
            break;
    }
}
```

## 实际应用案例

### 案例 1：订单履行系统

**工作流（What）**：

1. 与客户对话，回答产品问题
2. 创建订单（必要时移交给人工）
3. 提供 24/7 支持，智能升级

**架构选择（How）**：

- **初期**：单 Agent 架构，处理简单的订单流程
- **扩展后**：多 Agent 架构，包括客服 Agent、订单 Agent、升级 Agent

### 案例 2：设施工作单管理

**工作流（What）**：

1. 与员工对话，提供服务请求选项
2. 根据选择开立工作单
3. 将工作单发送给相应的服务团队
4. 更新工作进度和状态
5. 完成后关闭工作单并通知相关方

**架构选择（How）**：

- **路由架构**：一个主 Agent 根据请求类型路由到不同的服务团队 Agent
- **层级架构**：引入管理 Agent 协调多个服务团队 Agent

### 案例 3：抵押贷款处理系统

**工作流（What）**：

1. 与客户对话，回答问题
2. 审查贷款申请
3. 收集财务信息以评估资格
4. 检索和分析风险数据
5. 在必要时引入人工审查
6. 批准或拒绝申请
7. 向相关方通知决策

**架构选择（How）**：

- **混合架构**：主流程使用单 Agent，但将风险评估和人工审查作为独立的 Agent 或工具集成

## 总结

理解 **Agentic Workflows** 和 **Agentic Architectures** 的区别是构建成功 AI Agent 系统的关键：

- **工作流**回答"做什么"，描述业务流程和逻辑步骤
- **架构**回答"如何做"，定义技术框架和系统结构
- **同一个工作流可以用多种架构实现**，选择取决于具体需求

在 .NET 生态中，Microsoft 提供了丰富的工具和框架来支持 Agent 开发：

- **Azure Logic Apps**：适合企业级集成场景
- **Microsoft Agent Framework**：提供类型安全的工作流编排
- **Semantic Kernel**：支持多种编排模式（Sequential、Concurrent、Handoff、Magentic）

清晰地区分工作流和架构，有助于：

1. **设计更灵活的系统**：可以独立优化流程和架构
2. **选择合适的实现方案**：根据场景选择最匹配的架构
3. **更清晰地沟通**：避免团队讨论中的术语混淆
4. **提升可维护性**：模块化的架构更易于演进

随着 AI Agent 技术的不断成熟，正确理解和运用这些概念将成为每个 AI 工程师的必备技能。无论你选择哪种工作流模式和架构模式，关键是要根据实际业务需求做出明智的权衡。

## 参考资源

- [Microsoft Agent Framework Documentation](https://learn.microsoft.com/en-us/agent-framework/)
- [Azure Logic Apps Agent Workflows](https://learn.microsoft.com/en-us/azure/logic-apps/agent-workflows-concepts)
- [Semantic Kernel Agent Orchestration](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-orchestration/)
- [AI Agents in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/ai-agents)
