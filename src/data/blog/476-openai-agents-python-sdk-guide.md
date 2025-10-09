---
pubDatetime: 2025-10-09
title: OpenAI Agents SDK：构建生产级多智能体系统的 Python 框架
description: 深入探索 OpenAI Agents SDK for Python，一个轻量级但功能强大的多智能体编排框架。学习如何通过 Agent、Handoff、Guardrail 和 Session 等核心组件构建复杂的 AI 应用，掌握工具集成、会话管理、实时语音交互等生产实践技巧。
tags: ["AI", "Python", "OpenAI", "Agents", "LLM"]
slug: openai-agents-python-sdk-guide
source: https://github.com/openai/openai-agents-python
---

## 理解 OpenAI Agents SDK 的设计哲学

OpenAI Agents SDK 是一个专为构建多智能体（Multi-Agent）工作流而设计的 Python 框架。它是 OpenAI 早期实验性项目 Swarm 的生产级升级版本，旨在用最少的抽象层提供最大的灵活性。

### 核心设计原则

该 SDK 遵循两个关键设计原则：

**极简主义与实用主义的平衡**：SDK 提供了足够多的功能让开发者能够快速构建实用系统，但核心原语数量极少，学习成本低。开发者无需学习复杂的新抽象概念，而是利用 Python 原生特性来编排智能体工作流。

**开箱即用与深度定制并存**：默认配置即可运行良好，但开发者可以精确控制系统的每个行为细节。这种设计使得 SDK 既适合快速原型开发，也能支撑复杂的生产环境需求。

### 四大核心组件

SDK 的架构围绕四个基本构建块展开：

**Agents（智能体）**：本质上是配备了指令（instructions）、工具（tools）和配置参数的大语言模型。每个 Agent 都有明确的职责定义，通过 `name` 和 `instructions` 字段来描述其身份和行为准则。

**Handoffs（切换机制）**：这是一种特殊的工具调用类型，用于在不同 Agent 之间转移控制权。当某个 Agent 判断任务超出其能力范围时，可以主动将请求委派给更专业的 Agent 处理。

**Guardrails（护栏机制）**：用于验证输入和输出的安全检查系统。它可以在 Agent 执行前后并行运行验证逻辑，一旦检查失败立即中止执行，确保系统的安全性和可靠性。

**Sessions（会话管理）**：自动管理多轮对话中的历史记录。无需手动维护状态，SDK 会在 Agent 多次运行之间自动保留和传递上下文信息。

这些组件通过 Python 原生特性组合使用时，能够表达极其复杂的工具与智能体关系，而不会带来陡峭的学习曲线。

## 快速开始：从零搭建第一个 Agent

### 环境准备

首先创建 Python 虚拟环境并安装 SDK：

```bash
# 创建项目目录
mkdir my_agent_project
cd my_agent_project

# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装 SDK
pip install openai-agents
```

如果需要语音支持，可以安装可选依赖：

```bash
pip install 'openai-agents[voice]'
```

如果需要 Redis 会话存储支持：

```bash
pip install 'openai-agents[redis]'
```

### 配置 API 密钥

SDK 默认从环境变量读取 OpenAI API 密钥：

```bash
export OPENAI_API_KEY=sk-...
```

如果无法在启动前设置环境变量，可以在代码中配置：

```python
from agents import set_default_openai_key

set_default_openai_key("sk-...")
```

也可以配置自定义的 OpenAI 客户端实例：

```python
from openai import AsyncOpenAI
from agents import set_default_openai_client

custom_client = AsyncOpenAI(base_url="...", api_key="...")
set_default_openai_client(custom_client)
```

### Hello World 示例

最简单的 Agent 示例如下：

```python
from agents import Agent, Runner

# 创建一个基础助手 Agent
agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant"
)

# 同步运行 Agent
result = Runner.run_sync(
    agent,
    "Write a haiku about recursion in programming."
)

print(result.final_output)
# 输出示例：
# Code within the code,
# Functions calling themselves,
# Infinite loop's dance.
```

这个例子展示了 SDK 的核心工作流：创建 Agent、通过 Runner 执行、获取结果。

## Agent 的配置与定制

### 基本配置属性

一个 Agent 最常用的配置项包括：

**name（必填）**：Agent 的唯一标识符，用于在日志和追踪中区分不同的 Agent。

**instructions**：也称为系统提示词或开发者消息，定义了 Agent 的行为规则、角色定位和响应风格。

**model**：指定使用的语言模型，默认使用 `gpt-5`。可以设置为 `gpt-5-mini`、`gpt-5-nano` 等不同规模的模型。

**tools**：Agent 可以调用的工具列表，用于扩展 Agent 的能力边界。

示例配置：

```python
from agents import Agent, ModelSettings, function_tool

@function_tool
def get_weather(city: str) -> str:
    """返回指定城市的天气信息"""
    return f"The weather in {city} is sunny"

agent = Agent(
    name="Haiku Agent",
    instructions="Always respond in haiku form",
    model="gpt-5-nano",
    tools=[get_weather],
)
```

### 模型设置调优

对于使用 GPT-5 系列推理模型（`gpt-5`、`gpt-5-mini`、`gpt-5-nano`）的场景，SDK 会自动应用合理的默认配置，将 `reasoning.effort` 和 `verbosity` 都设置为 `"low"` 以优化延迟。

如果需要自定义推理强度：

```python
from openai.types.shared import Reasoning
from agents import Agent, ModelSettings

agent = Agent(
    name="Deep Thinker",
    instructions="You analyze problems thoroughly.",
    model="gpt-5",
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high"),
        verbosity="high"
    )
)
```

### 动态指令生成

对于需要根据上下文动态调整行为的场景，可以使用可调用对象作为 instructions：

```python
from agents import Agent

def dynamic_instructions(context):
    """根据上下文生成指令"""
    return f"You are an expert in {context['domain']}. Help the user with their questions."

agent = Agent(
    name="Dynamic Assistant",
    instructions=lambda: dynamic_instructions({"domain": "machine learning"})
)
```

## 工具集成：扩展 Agent 能力

### 函数工具的自动转换

SDK 最强大的特性之一是能够将任意 Python 函数自动转换为 Agent 可调用的工具。使用 `@function_tool` 装饰器即可实现：

```python
from agents import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    return f"The weather in {city} is sunny."

agent = Agent(
    name="Weather Assistant",
    instructions="You help users check weather information.",
    tools=[get_weather],
)

result = Runner.run_sync(
    agent,
    "What's the weather in Tokyo?"
)
print(result.final_output)  # "The weather in Tokyo is sunny."
```

SDK 会自动完成以下工作：

- **工具名称**：从 Python 函数名自动生成（也可以手动指定）
- **工具描述**：从函数的 docstring 提取
- **参数模式**：根据函数的类型注解自动生成 JSON Schema
- **参数描述**：从 docstring 中解析出每个参数的说明

### 支持复杂类型

工具函数可以使用 Pydantic 模型来定义复杂的输入输出类型：

```python
from pydantic import BaseModel
from agents import function_tool

class WeatherQuery(BaseModel):
    city: str
    country: str
    unit: str = "celsius"

class WeatherResponse(BaseModel):
    temperature: float
    condition: str
    humidity: int

@function_tool
def get_detailed_weather(query: WeatherQuery) -> WeatherResponse:
    """获取详细的天气信息"""
    return WeatherResponse(
        temperature=25.5,
        condition="partly cloudy",
        humidity=65
    )
```

SDK 会自动进行输入验证和类型转换，确保传递给函数的参数类型正确。

### OpenAI 托管工具

SDK 还支持 OpenAI 平台提供的托管工具：

- **Web Search**：网络搜索与过滤
- **File Search**：文件内容搜索
- **Code Interpreter**：代码执行环境
- **Computer Use**：计算机操作能力
- **Image Generation**：图像生成功能

这些工具可以在 `examples/tools` 目录中找到详细使用示例。

## Handoffs：多智能体协作机制

### 基本切换模式

Handoffs 是 SDK 实现多智能体协作的核心机制。当一个 Agent 遇到超出其能力范围的任务时，可以将请求切换给更合适的 Agent：

```python
from agents import Agent, Runner

# 创建专业领域 Agent
spanish_agent = Agent(
    name="Spanish Agent",
    instructions="You only speak Spanish.",
)

english_agent = Agent(
    name="English Agent",
    instructions="You only speak English",
)

# 创建路由 Agent，配置切换选项
triage_agent = Agent(
    name="Triage Agent",
    instructions="Handoff to the appropriate agent based on the language of the request.",
    handoffs=[spanish_agent, english_agent],
)

# 执行请求
result = Runner.run_sync(triage_agent, "Hola, ¿cómo estás?")
print(result.final_output)
# 输出：¡Hola! Estoy bien, gracias por preguntar. ¿Y tú, cómo estás?
```

在这个例子中，`triage_agent` 识别出用户使用的是西班牙语，自动将请求切换给 `spanish_agent` 处理。

### 切换描述的重要性

`handoff_description` 字段为 Agent 提供了选择切换目标的额外上下文信息：

```python
history_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You provide assistance with historical queries.",
)

math_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems.",
)

triage_agent = Agent(
    name="Homework Helper",
    instructions="Determine which specialist can best help with the question.",
    handoffs=[history_agent, math_agent]
)
```

语言模型会根据 `handoff_description` 的内容来判断应该切换到哪个 Agent。

### 切换提示词增强

SDK 提供了辅助函数来优化切换行为：

```python
from agents import Agent
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

spanish_agent = Agent(
    name="Spanish Assistant",
    handoff_description="Agent for Spanish language support",
    instructions=prompt_with_handoff_instructions(
        "You speak only Spanish. Be polite and concise."
    ),
)
```

`prompt_with_handoff_instructions` 会自动在指令中添加关于如何正确执行切换的说明，提高切换的准确性。

## 会话管理：跨轮对话的记忆机制

### 为什么需要 Session

在传统的无状态 API 调用中，每次请求都是孤立的，Agent 无法记住之前的对话内容。Session 机制通过自动管理对话历史，使得多轮交互成为可能。

### 快速开始使用 SQLite Session

SDK 内置了多种 Session 实现，最简单的是基于 SQLite 的本地存储：

```python
from agents import Agent, Runner, SQLiteSession

# 创建 Agent
agent = Agent(
    name="Assistant",
    instructions="Reply very concisely.",
)

# 创建会话实例
session = SQLiteSession("conversation_123")

# 第一轮对话
result = Runner.run_sync(
    agent,
    "What city is the Golden Gate Bridge in?",
    session=session
)
print(result.final_output)  # "San Francisco"

# 第二轮对话 - Agent 自动记住上下文
result = Runner.run_sync(
    agent,
    "What state is it in?",
    session=session
)
print(result.final_output)  # "California"

# 第三轮对话
result = Runner.run_sync(
    agent,
    "What's the population?",
    session=session
)
print(result.final_output)  # "Approximately 39 million"
```

在这个例子中，Agent 能够正确理解"它"指的是之前提到的加利福尼亚州，而"人口"指的是该州的人口，而非城市人口。

### 异步运行支持

Session 机制同时支持同步和异步运行：

```python
import asyncio

async def main():
    agent = Agent(
        name="Assistant",
        instructions="Be helpful and concise."
    )

    session = SQLiteSession("async_conversation")

    result = await Runner.run(
        agent,
        "Tell me about Python async/await",
        session=session
    )
    print(result.final_output)

asyncio.run(main())
```

### 多种 Session 后端

SDK 提供了多种 Session 存储后端供选择：

**SQLiteSession**：适合本地开发和单机部署，数据存储在本地数据库文件中。

**RedisSession**：适合分布式环境，支持多实例共享会话状态。

```python
from agents import RedisSession

session = RedisSession(
    session_id="user_123",
    redis_url="redis://localhost:6379"
)
```

**SQLAlchemySession**：支持各种关系型数据库（PostgreSQL、MySQL、SQLite 等）。

**EncryptedSession**：在存储前自动加密会话数据，提高安全性。

**OpenAI Session**：使用 OpenAI 平台提供的会话存储服务。

### 自定义 Session 实现

如果内置的 Session 实现不满足需求，可以实现自定义的存储逻辑：

```python
from agents.memory import Session
from typing import List

class MyCustomSession:
    """自定义 Session 实现"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        # 初始化自定义存储

    async def get_items(self, limit: int | None = None) -> List[dict]:
        """获取会话历史记录"""
        # 实现从存储中检索消息的逻辑
        pass

    async def add_items(self, items: List[dict]) -> None:
        """存储新的消息"""
        # 实现将消息保存到存储的逻辑
        pass

    async def pop_item(self) -> dict | None:
        """移除并返回最新的消息"""
        pass

    async def clear_session(self) -> None:
        """清空会话历史"""
        pass

# 使用自定义 Session
agent = Agent(name="Assistant")
result = await Runner.run(
    agent,
    "Hello",
    session=MyCustomSession("my_session")
)
```

只需实现 `Session` 协议要求的四个方法，就可以集成任何存储后端。

## Guardrails：输入输出安全防护

### 为什么需要 Guardrails

在生产环境中，仅依赖 Agent 的自主判断是不够的。Guardrails 提供了一个额外的安全层，可以在 Agent 执行前验证输入，在输出前检查结果，确保系统的安全性和合规性。

### 输入验证 Guardrail

输入 Guardrail 在请求到达 Agent 前执行，可以拒绝不安全或不合规的请求：

```python
from agents import Agent, Runner, function_tool

@function_tool
async def check_user_intent(user_input: str) -> bool:
    """验证用户输入是否安全"""
    # 检查是否包含恶意内容
    forbidden_keywords = ["hack", "exploit", "bypass"]
    return not any(keyword in user_input.lower() for keyword in forbidden_keywords)

agent = Agent(
    name="Secure Assistant",
    instructions="You are a helpful and secure assistant.",
    input_guardrails=[check_user_intent]
)

# 合法请求会正常执行
result = Runner.run_sync(agent, "How do I learn Python?")

# 不合法请求会被拦截
result = Runner.run_sync(agent, "How to hack a website?")
# 此请求会被 Guardrail 阻止
```

### 输出验证 Guardrail

输出 Guardrail 在 Agent 生成响应后执行，可以过滤敏感信息或验证输出格式：

```python
@function_tool
async def check_response_safety(response: str) -> bool:
    """验证响应内容是否安全"""
    # 检查是否泄露敏感信息
    sensitive_patterns = ["password", "credit card", "ssn"]
    return not any(pattern in response.lower() for pattern in sensitive_patterns)

agent = Agent(
    name="Safe Assistant",
    instructions="You help users but never reveal sensitive information.",
    output_guardrails=[check_response_safety]
)
```

### LLM 作为评判者

一种强大的 Guardrail 模式是使用另一个 LLM 来评估 Agent 的输出：

```python
from agents import Agent

judge_agent = Agent(
    name="Content Judge",
    instructions="Evaluate if the response is appropriate and helpful. Return 'PASS' or 'FAIL'."
)

@function_tool
async def llm_judge(response: str) -> bool:
    """使用 LLM 评估响应质量"""
    result = await Runner.run(
        judge_agent,
        f"Evaluate this response: {response}"
    )
    return "PASS" in result.final_output

main_agent = Agent(
    name="Main Assistant",
    instructions="You answer user questions.",
    output_guardrails=[llm_judge]
)
```

这种模式在需要复杂语义理解的场景中特别有用，例如判断回复是否符合品牌调性、是否包含偏见等。

## 实时语音交互能力

### Voice 模式快速入门

SDK 支持通过 TTS（Text-to-Speech）和 STT（Speech-to-Text）模型实现语音交互：

```bash
# 安装语音依赖
pip install 'openai-agents[voice]'
```

基本的语音 Agent 示例：

```python
import asyncio
import random
from agents import Agent, function_tool
from agents.voice import AudioInput, SingleAgentVoiceWorkflow, VoicePipeline

@function_tool
def get_weather(city: str) -> str:
    """获取城市天气"""
    conditions = ["sunny", "cloudy", "rainy", "snowy"]
    return f"The weather in {city} is {random.choice(conditions)}."

agent = Agent(
    name="Voice Assistant",
    instructions="You're speaking to a human, be polite and concise.",
    model="gpt-4.1",
    tools=[get_weather],
)

async def main():
    # 创建语音工作流
    workflow = SingleAgentVoiceWorkflow(agent)

    # 创建语音管道
    pipeline = VoicePipeline(
        workflow=workflow,
        input_audio_config={
            "sample_rate": 16000,
            "channels": 1,
        }
    )

    # 启动语音交互
    await pipeline.run()

asyncio.run(main())
```

### 流式语音处理

对于需要低延迟的场景，可以使用流式语音处理：

```python
from agents.voice import StreamingVoiceWorkflow

workflow = StreamingVoiceWorkflow(agent)

async def handle_audio_stream(audio_chunk):
    """处理音频流"""
    response = await workflow.process_audio(audio_chunk)
    # 实时播放响应音频
    play_audio(response.audio)
```

### Realtime API 集成

SDK 还支持 OpenAI 的 Realtime API，提供更低延迟的实时对话体验：

```python
from agents.realtime import RealtimeAgent, RealtimeRunner

async def main():
    # 创建实时 Agent
    agent = RealtimeAgent(
        name="Realtime Assistant",
        instructions="You are a helpful voice assistant. Keep responses brief.",
    )

    # 配置实时运行器
    runner = RealtimeRunner(
        starting_agent=agent,
        config={
            "model_settings": {
                "model_name": "gpt-realtime",
                "voice": "ash",
                "modalities": ["audio"],
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "semantic_vad",
                    "interrupt_response": True
                },
            }
        },
    )

    # 启动会话
    session = await runner.run()

    async with session:
        print("Realtime session started!")
        # 会话保持活跃，实时处理音频输入输出

asyncio.run(main())
```

## 追踪与可观测性

### 内置追踪功能

SDK 自带强大的追踪系统，可以可视化和调试 Agent 的执行流程。默认情况下，追踪功能已启用，每次运行都会生成追踪数据。

运行 Agent 后，控制台会显示追踪 URL：

```text
View trace: https://platform.openai.com/traces/abc123...
```

追踪 UI 会展示：

- **Agent 执行序列**：可视化 Agent 间的切换路径
- **工具调用详情**：每个工具调用的输入输出
- **耗时分析**：识别性能瓶颈
- **错误堆栈**：快速定位失败原因

### 禁用追踪

在某些场景下（如性能测试），可能需要禁用追踪：

```python
from agents import set_tracing_disabled

set_tracing_disabled(True)
```

### 自定义追踪处理器

可以实现自定义的追踪处理器来集成第三方监控系统：

```python
from agents import set_trace_processors

class CustomTraceProcessor:
    def process_trace(self, trace_data):
        # 发送到自定义监控系统
        send_to_monitoring(trace_data)

set_trace_processors([CustomTraceProcessor()])
```

### Agent 流程可视化

SDK 提供了工具来生成 Agent 网络拓扑图：

```python
from agents import Agent, function_tool
from agents.extensions.visualization import draw_graph

@function_tool
def get_weather(city: str) -> str:
    return f"Weather in {city} is sunny."

spanish_agent = Agent(
    name="Spanish Agent",
    instructions="You only speak Spanish.",
)

english_agent = Agent(
    name="English Agent",
    instructions="You only speak English",
)

triage_agent = Agent(
    name="Triage Agent",
    instructions="Route to appropriate language agent.",
    handoffs=[spanish_agent, english_agent],
    tools=[get_weather],
)

# 生成可视化图表
draw_graph(triage_agent, output_path="agent_graph.png")
```

生成的图表会清晰展示 Agent 之间的切换关系和工具配置。

## 高级模式与最佳实践

### 确定性工作流

对于需要严格控制执行顺序的场景，可以使用确定性工作流模式：

```python
async def deterministic_workflow(user_input: str):
    # 步骤 1: 分析输入
    analysis_agent = Agent(
        name="Analyzer",
        instructions="Analyze the user request and extract key information."
    )
    analysis = await Runner.run(analysis_agent, user_input)

    # 步骤 2: 数据收集
    data_agent = Agent(
        name="Data Collector",
        instructions="Gather relevant data based on the analysis."
    )
    data = await Runner.run(data_agent, analysis.final_output)

    # 步骤 3: 生成响应
    response_agent = Agent(
        name="Responder",
        instructions="Generate final response using collected data."
    )
    response = await Runner.run(response_agent, data.final_output)

    return response.final_output
```

### Agent 作为工具

Agent 本身可以作为工具被其他 Agent 使用：

```python
# 创建专家 Agent
code_expert = Agent(
    name="Code Expert",
    instructions="You are an expert in writing Python code."
)

# 将 Agent 包装为工具
@function_tool
async def ask_code_expert(question: str) -> str:
    """咨询代码专家"""
    result = await Runner.run(code_expert, question)
    return result.final_output

# 主 Agent 使用专家作为工具
main_agent = Agent(
    name="Main Assistant",
    instructions="You help users with various tasks.",
    tools=[ask_code_expert]
)
```

### 并行 Agent 执行

对于独立的子任务，可以并行执行多个 Agent 以提高效率：

```python
import asyncio

async def parallel_execution(query: str):
    search_agent = Agent(
        name="Search Agent",
        instructions="Search for information online."
    )

    analysis_agent = Agent(
        name="Analysis Agent",
        instructions="Analyze data patterns."
    )

    # 并行执行
    results = await asyncio.gather(
        Runner.run(search_agent, query),
        Runner.run(analysis_agent, query)
    )

    return {
        "search_result": results[0].final_output,
        "analysis_result": results[1].final_output
    }
```

### 条件工具使用

根据上下文动态启用或禁用工具：

```python
def get_available_tools(user_tier: str):
    """根据用户等级返回可用工具"""
    basic_tools = [search_web, summarize_text]
    premium_tools = [advanced_analysis, custom_report]

    if user_tier == "premium":
        return basic_tools + premium_tools
    return basic_tools

agent = Agent(
    name="Adaptive Assistant",
    instructions="Help users with available tools.",
    tools=get_available_tools(current_user.tier)
)
```

### 流式输出处理

对于需要实时反馈的场景，可以使用流式输出：

```python
async def stream_response(agent: Agent, user_input: str):
    """流式处理 Agent 响应"""
    async for chunk in Runner.stream(agent, user_input):
        if chunk.type == "text":
            print(chunk.content, end="", flush=True)
        elif chunk.type == "tool_call":
            print(f"\n[Calling tool: {chunk.tool_name}]")
```

## 与第三方模型集成

### 使用 LiteLLM

SDK 支持通过 LiteLLM 集成 100+ 种不同的语言模型：

```python
from agents import Agent, set_default_openai_api

# 配置使用 LiteLLM
set_default_openai_api("chat_completions")

# 使用非 OpenAI 模型
agent = Agent(
    name="Claude Agent",
    instructions="You are a helpful assistant.",
    model="claude-3-opus-20240229"
)
```

### 自定义模型提供者

可以实现自定义的模型提供者来集成任意 LLM 服务：

```python
from agents.models import ModelProvider

class MyModelProvider(ModelProvider):
    async def complete(self, messages, **kwargs):
        # 调用自定义 LLM API
        response = await my_llm_api.complete(messages)
        return response

# 注册自定义提供者
agent = Agent(
    name="Custom Model Agent",
    instructions="You are helpful.",
    model_provider=MyModelProvider()
)
```

## 实用工具与调试技巧

### REPL 交互式测试

SDK 提供了 `run_demo_loop` 工具用于快速测试 Agent 行为：

```python
import asyncio
from agents import Agent, run_demo_loop

async def main():
    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant."
    )
    await run_demo_loop(agent)

asyncio.run(main())
```

运行后会启动一个交互式命令行界面，可以直接输入消息与 Agent 对话。输入 `quit`、`exit` 或按 `Ctrl-D` 退出。

### 详细日志输出

启用详细日志以获取更多调试信息：

```python
from agents import enable_verbose_stdout_logging

enable_verbose_stdout_logging()
```

### 使用量追踪

追踪 API 调用的 token 使用量：

```python
result = await Runner.run(agent, "Hello")

print(f"Prompt tokens: {result.usage.prompt_tokens}")
print(f"Completion tokens: {result.usage.completion_tokens}")
print(f"Total tokens: {result.usage.total_tokens}")
```

### 处理文件输入

Agent 可以直接处理本地或远程文件：

```python
result = await Runner.run(
    agent,
    [
        {
            "role": "user",
            "content": [
                {"type": "input_file", "file_url": "https://example.com/doc.pdf"}
            ],
        },
        {
            "role": "user",
            "content": "Can you summarize this document?",
        },
    ],
)
```

## 生产部署注意事项

### 错误处理策略

实现健壮的错误处理机制：

```python
from agents import Agent, Runner

async def safe_run(agent: Agent, user_input: str):
    try:
        result = await Runner.run(agent, user_input)
        return result.final_output
    except Exception as e:
        # 记录错误
        logger.error(f"Agent execution failed: {e}")
        # 返回降级响应
        return "I apologize, but I encountered an error. Please try again."
```

### 超时控制

为 Agent 执行设置超时限制：

```python
import asyncio

async def run_with_timeout(agent: Agent, user_input: str, timeout: int = 30):
    try:
        result = await asyncio.wait_for(
            Runner.run(agent, user_input),
            timeout=timeout
        )
        return result.final_output
    except asyncio.TimeoutError:
        return "Request timed out. Please try a simpler query."
```

### 成本优化

使用较小的模型处理简单任务：

```python
# 简单任务使用 nano 模型
simple_agent = Agent(
    name="Simple Assistant",
    instructions="Answer basic questions concisely.",
    model="gpt-5-nano"
)

# 复杂任务使用完整模型
complex_agent = Agent(
    name="Expert Assistant",
    instructions="Provide detailed analysis.",
    model="gpt-5"
)
```

### 会话清理

定期清理过期的会话数据：

```python
async def cleanup_old_sessions(session_store):
    """清理超过 30 天未使用的会话"""
    cutoff_date = datetime.now() - timedelta(days=30)
    await session_store.delete_sessions_before(cutoff_date)
```

## 总结

OpenAI Agents SDK 通过极简的设计理念和强大的功能组合，为构建生产级多智能体系统提供了理想的开发框架。其核心优势包括：

**学习曲线平缓**：仅需掌握 Agent、Handoff、Guardrail 和 Session 四个核心概念，即可构建复杂的 AI 应用。

**Python 原生集成**：充分利用 Python 的异步特性、类型系统和生态系统，无需学习新的编程范式。

**灵活的可扩展性**：从简单的单 Agent 应用到复杂的多 Agent 编排，从本地开发到分布式部署，SDK 都能提供良好支持。

**完善的工具生态**：自动工具转换、会话管理、追踪可视化、语音交互等功能开箱即用。

**生产环境就绪**：内置的错误处理、安全防护、性能追踪等特性确保系统的稳定性和可靠性。

无论是构建智能客服系统、自动化工作流、研究助手还是复杂的决策支持系统，OpenAI Agents SDK 都能提供坚实的技术基础。通过合理运用其提供的各项能力，开发者可以快速实现从原型到生产的完整交付流程。
