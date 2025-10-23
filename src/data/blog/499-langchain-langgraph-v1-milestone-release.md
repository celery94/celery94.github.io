---
pubDatetime: 2025-10-23
title: LangChain 与 LangGraph 正式发布 1.0 版本：生产级 AI Agent 框架的里程碑
description: LangChain 1.0 和 LangGraph 1.0 标志着开源 AI Agent 框架进入稳定生产阶段，提供了标准化的 Agent 构建抽象、中间件定制能力以及持久化运行时支持，为企业级应用奠定了坚实基础。
tags: ["AI", "LangChain", "LangGraph", "Agent", "Python", "JavaScript"]
slug: langchain-langgraph-v1-milestone-release
source: https://blog.langchain.com/langchain-langgraph-1dot0/
---

# LangChain 与 LangGraph 正式发布 1.0 版本：生产级 AI Agent 框架的里程碑

在经历了三年的迭代与社区反馈后，LangChain 团队正式发布了 LangChain 1.0 和 LangGraph 1.0 版本。这是两个框架的首个主要版本发布，标志着开源 AI Agent 开发进入了一个全新的成熟阶段。这次发布不仅体现了对稳定性的承诺（在 2.0 版本之前不会有破坏性变更），还推出了全新的统一文档站点，为开发者提供更好的学习体验。

## 两个框架的定位与协同

在深入探讨技术细节之前，理解这两个框架的核心定位至关重要：

**LangChain** 专注于提供高层抽象，让开发者能够以最快的速度构建 AI Agent。它采用标准化的工具调用架构，支持跨提供商的统一接口，并通过中间件机制实现深度定制。对于需要快速交付标准 Agent 功能的场景，LangChain 是理想选择。

**LangGraph** 则是一个更底层的框架和运行时环境，专为高度定制化和可控的 Agent 设计。它基于图执行模型，天然支持长时间运行的生产级 Agent，提供了持久化状态、可恢复执行以及人机协同等企业级特性。

两者的关系并非竞争而是互补：LangChain 的 Agent 实际上是构建在 LangGraph 运行时之上的。这意味着开发者可以从 LangChain 的高层 API 起步，当需求复杂度增加时，无缝迁移到 LangGraph 进行更精细的控制。由于图结构的可组合性，甚至可以在同一个应用中混合使用两种方式。

## LangChain 1.0：重新思考 Agent 构建抽象

### 三年反馈的沉淀

LangChain 自诞生以来一直致力于提供与 LLM 交互的高层接口和预构建的 Agent 模式。标准化的模型抽象和现成的 Agent 模式帮助开发者快速交付 AI 功能，同时避免供应商锁定。这在模型能力快速迭代的领域尤为重要。

然而，在过去三年中，团队收到了大量一致的反馈：

1. **抽象过重**：某些场景下的抽象层次过高，限制了灵活性
2. **包体积膨胀**：功能累积导致包的表面积变得难以管理
3. **定制能力不足**：当用例偏离预构建模式时，开发者往往不得不完全放弃框架，回退到原始的 LLM 调用

LangChain 1.0 正是对这些反馈的系统性回应。它在保留有效特性的同时，对不足之处进行了深度重构。

### 核心创新：create_agent 抽象

1.0 版本引入的 `create_agent` 函数是整个更新的核心。它建立在标准 Agent 循环之上，提供了既简洁又强大的接口：

```python
from langchain.agents import create_agent

weather_agent = create_agent(
    model="openai:gpt-5",
    tools=[get_weather],
    system_prompt="Help the user by fetching the weather in their city.",
)

result = weather_agent.invoke({"role": "user", "content": "what's the weather in SF?"})
```

**Agent 执行循环的工作原理**：

1. **初始化阶段**：选择模型、配置工具集、设定系统提示词
2. **执行阶段**：
   - 向模型发送请求
   - 模型返回工具调用或最终答案
   - 如果是工具调用，执行工具并将结果添加到对话上下文
   - 如果是最终答案，返回结果
   - 重复循环直到完成

底层实现基于 LangGraph 运行时，这与 `langgraph.prebuilts` 中已在生产环境运行一年的 `create_react_agent` 函数类似，但进行了显著改进。

### 中间件：Agent 定制的新范式

大多数 Agent 构建工具的局限在于缺乏定制能力。`create_agent` 通过引入**中间件（Middleware）**机制解决了这个根本问题。中间件提供了一系列钩子函数，允许在 Agent 循环的每个关键步骤进行干预和定制。

**内置中间件示例**：

**1. 人机协同（Human-in-the-Loop）**  
在工具执行前暂停 Agent，让用户审批、编辑或拒绝工具调用。这对于涉及外部系统交互、发送通信或执行敏感操作的 Agent 至关重要。

```python
from langchain.agents.middleware import HumanInTheLoop

agent = create_agent(
    model="openai:gpt-4o",
    tools=[send_email, update_database],
    middleware=[HumanInTheLoop()],
)
```

**2. 上下文摘要（Summarization）**  
当消息历史接近上下文限制时，自动压缩历史记录，保留最近的消息同时摘要旧的上下文。这避免了 token 溢出错误，保持长时间会话的性能。

**3. 敏感信息过滤（PII Redaction）**  
使用模式匹配识别并过滤敏感信息（如电子邮件、电话号码、身份证号），然后再传递给模型。这有助于满足隐私法规要求，防止用户数据意外泄露。

**自定义中间件支持**：

开发者可以在 Agent 循环的多个切入点实现自定义逻辑：

- **before_model_call**：模型调用前的预处理
- **after_model_call**：模型响应后的后处理
- **before_tool_execution**：工具执行前的验证
- **after_tool_execution**：工具执行后的结果处理
- **on_error**：错误处理与恢复

这种细粒度的控制能力使得 LangChain 从一个简单的快速启动工具转变为能够处理复杂企业场景的生产级框架。

### 结构化输出生成的优化

在 1.0 版本中，结构化输出生成已整合到主模型-工具循环中，而非作为额外的步骤。这一改进带来了两个显著优势：

1. **降低延迟**：消除了额外的 LLM 调用
2. **降低成本**：减少了 token 消耗

开发者现在可以精细控制结构化输出的生成方式，可以选择通过工具调用实现，也可以使用提供商原生的结构化输出能力：

```python
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from pydantic import BaseModel

class WeatherReport(BaseModel):
    temperature: float
    condition: str

agent = create_agent(
    "openai:gpt-4o-mini",
    tools=[weather_tool],
    response_format=ToolStrategy(WeatherReport),
    prompt="Help the user by fetching the weather in their city.",
)
```

### 标准化内容块（Standard Content Blocks）

LangChain 的核心价值之一是提供跨提供商的统一接口。1.0 版本通过引入**标准化内容块**进一步强化了这一优势。

过去，切换模型或提供商常常会破坏流式输出、UI 前端和内存存储。新的 `.content_blocks` 属性提供了：

- **跨提供商的一致内容类型**：统一的数据结构
- **现代 LLM 能力支持**：推理轨迹、引用、工具调用（包括服务端工具调用）
- **类型化接口**：为复杂响应结构提供强类型支持
- **完全向后兼容**：不破坏现有代码

这使得 LangChain 能够与时俱进地支持推理、引用等现代 LLM 特性，同时最大限度减少破坏性变更。

### 包精简与向后兼容

LangChain 1.0 大幅缩减了包的作用域，聚焦于核心抽象。为了保持向后兼容性，旧功能被迁移到 `langchain-classic` 包中。

**主要变更**：

1. `create_agent` 在 LangChain 中引入，`langgraph.prebuilt` 中的 `create_react_agent` 被标记为过时
2. 放弃 Python 3.9 支持（2025年10月已 EOL），最低要求 Python 3.10+（Python 3.14 支持即将推出）
3. 包表面积大幅缩减，专注核心抽象，旧功能迁移至 `langchain-classic`

这种精简策略确保了框架既简洁又强大，为长期维护奠定了基础。

## LangGraph 1.0：生产级持久化 Agent 运行时

### 从原型到生产的关键缺失环节

AI Agent 正在从实验原型走向生产应用，但持久化、可观测性和人机协同控制等核心特性一直没有得到充分支持。LangGraph 1.0 通过强大的基于图的执行模型填补了这些空白。

**三大核心能力**：

**1. 持久化状态（Durable State）**  
Agent 的执行状态自动持久化。如果服务器在对话中途重启，或者长时间运行的工作流被中断，Agent 能够从中断点精确恢复，无需丢失上下文或强制用户重新开始。

这种能力对于企业应用至关重要。想象一个审批流程，可能跨越数天甚至数周，LangGraph 的持久化机制确保了流程的连续性。

**2. 内置持久化（Built-in Persistence）**  
无需编写自定义数据库逻辑即可在任意点保存和恢复 Agent 工作流。这使得跨多个会话运行的多日审批流程或后台任务变得简单。

**3. 人机协同模式（Human-in-the-Loop Patterns）**  
通过一流的 API 支持，可以暂停 Agent 执行以便人类审查、修改或批准。构建让人类保持对高风险决策控制权的系统变得轻而易举。

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

# 定义状态图
workflow = StateGraph(state_schema)

# 添加节点和边
workflow.add_node("process", process_node)
workflow.add_node("human_review", human_review_node)
workflow.add_edge("process", "human_review")

# 使用持久化检查点
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# 执行可恢复的工作流
result = app.invoke(initial_state, config={"thread_id": "session-123"})
```

### 设计哲学与行业验证

LangGraph 的设计哲学源于对 Agent 执行模型的第一性原理思考。经过一年多的迭代，以及被 Uber、LinkedIn、Klarna 等公司广泛采用后，它已经证明了自己在生产环境中的可靠性。

1.0 版本的发布标志着持久化 Agent 框架领域的首个稳定主版本，这对于生产就绪的 AI 系统来说是一个重大里程碑。

### 破坏性变更与迁移

LangGraph 1.0 保持了完全的向后兼容性。唯一值得注意的变更是 `langgraph.prebuilt` 模块的弃用，其增强功能已迁移到 `langchain.agents`。

## 如何选择：LangChain vs LangGraph

两个框架的选择取决于具体场景和需求复杂度。最大的优势在于它们的无缝集成：从 LangChain 的高层 API 开始，在需要更多控制时平滑过渡到 LangGraph。

### 选择 LangChain 1.0 的场景

- 需要快速交付标准 Agent 模式
- Agent 符合默认循环（模型 → 工具 → 响应）
- 基于中间件的定制已足够
- 优先考虑高层抽象而非底层控制

### 选择 LangGraph 1.0 的场景

- 工作流混合了确定性组件和 Agent 组件
- 长时间运行的业务流程自动化
- 需要严格监督/人机协同的敏感工作流
- 高度定制或复杂的工作流
- 需要精确控制延迟和成本的应用

### 混合使用策略

由于 LangChain Agent 构建在 LangGraph 之上，且图结构是可组合的，开发者可以在同一应用中混合使用两种方法。例如，在自定义 LangGraph 工作流中嵌入通过 `create_agent` 创建的 Agent：

```python
from langchain.agents import create_agent
from langgraph.graph import StateGraph

# 创建高层 Agent
qa_agent = create_agent(
    model="openai:gpt-4o",
    tools=[search_tool, calculator],
)

# 将其作为节点嵌入到复杂工作流中
workflow = StateGraph(state_schema)
workflow.add_node("qa_agent", lambda state: qa_agent.invoke(state))
workflow.add_node("custom_logic", custom_processing)
workflow.add_edge("qa_agent", "custom_logic")
```

## 安装与迁移指南

### 安装命令

**Python**:

```bash
# 安装或升级 LangChain
uv pip install --upgrade langchain

# 安装经典版本（向后兼容）
uv pip install langchain-classic

# 安装或升级 LangGraph
uv pip install --upgrade langgraph
```

**JavaScript**:

```bash
# LangChain
npm install @langchain/langchain@latest
npm install @langchain/langchain-classic

# LangGraph
npm install @langchain/langgraph@latest
```

### 迁移资源

官方提供了详细的迁移资源：

- **Python 发布概览**: [https://docs.langchain.com/oss/python/releases/langchain-v1](https://docs.langchain.com/oss/python/releases/langchain-v1)
- **JavaScript 发布概览**: [https://docs.langchain.com/oss/javascript/releases/langchain-v1](https://docs.langchain.com/oss/javascript/releases/langchain-v1)
- **Python 迁移指南**: [https://docs.langchain.com/oss/python/migrate/langchain-v1](https://docs.langchain.com/oss/python/migrate/langchain-v1)
- **JavaScript 迁移指南**: [https://docs.langchain.com/oss/javascript/migrate/langchain-v1](https://docs.langchain.com/oss/javascript/migrate/langchain-v1)

## 统一文档站点

LangChain 团队推出了全新的统一文档站点 [docs.langchain.com](https://docs.langchain.com)。这是首次将所有 LangChain 和 LangGraph 文档（涵盖 Python 和 JavaScript）整合到一个站点中，提供：

- 并行代码示例（Python 和 JavaScript 对照）
- 共享的概念指南
- 整合的 API 参考
- 更直观的导航结构
- 深入的教程，涵盖常见 Agent 架构

这种统一体验大大降低了学习曲线，让开发者能更快地找到需要的信息。

## 展望未来

LangChain 和 LangGraph 的 1.0 发布不仅是技术上的里程碑，更是对社区和企业用户的承诺。随着每月 9000 万次下载量，以及在 Uber、JP Morgan、Blackrock、Cisco 等企业的生产应用中运行，这两个框架已经证明了自己的价值。

1.0 版本带来的稳定性承诺意味着企业可以更放心地在生产环境中采用这些框架。无论是快速原型开发还是大规模生产部署，LangChain 和 LangGraph 都提供了从入门到精通的完整路径。

对于正在探索 AI Agent 开发的团队，这是一个绝佳的起点。从 `create_agent` 的简洁抽象开始，随着需求的增长逐步深入到 LangGraph 的强大能力，构建真正满足业务需求的智能系统。
